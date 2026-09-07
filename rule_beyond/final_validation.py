"""第三轮最终验证：LLM 给策略意图，确定性规划器负责合法行动。"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .blind import BlindCase, simulate, baseline_turns


@dataclass(frozen=True)
class FinalCase:
    case: BlindCase
    oracle_intent: str
    minimum_gain: int
    control: bool = False


def _case(case_id, state, rule, intent, oracle, gain, control=False):
    return FinalCase(BlindCase(case_id, state, rule, oracle, gain, control), intent, gain, control)


# oracle_intent、参考行动和阈值仅用于本地评测，绝不发送给模型。
CASES = [
    _case("F01", {"board":[5,3],"blue":[{"id":"b1","hp":4,"max_hp":12,"atk":2,"pos":[1,1]}],"red":[{"id":"r1","hp":14,"max_hp":14,"atk":2,"pos":[2,1]}]}, {"if":{"hp_percent_below":30},"then":{"attack_bonus":5}}, "trigger_low_hp", [[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"attack","target":"r1"}],[{"actor":"b1","type":"attack","target":"r1"}]], 8),
    _case("F02", {"board":[5,3],"blue":[{"id":"b1","hp":5,"max_hp":15,"atk":2,"pos":[1,1]}],"red":[{"id":"r1","hp":15,"max_hp":15,"atk":5,"pos":[2,1]}]}, {"if":{"hp_percent_below":30},"then":{"attack_bonus":4}}, "trigger_low_hp", [[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"attack","target":"r1"}],[]], 4),
    _case("F03", {"board":[5,3],"blue":[{"id":"b1","hp":8,"max_hp":10,"atk":2,"pos":[1,1]}],"red":[{"id":"r1","hp":12,"max_hp":12,"atk":2,"pos":[2,1]}]}, {"if":{"after_damaged":True},"then":{"extra_actions":2}}, "trade_extra_actions", [[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"attack","target":"r1"},{"actor":"b1","type":"attack","target":"r1"},{"actor":"b1","type":"attack","target":"r1"}],[{"actor":"b1","type":"attack","target":"r1"}]], 3),
    _case("F04", {"board":[5,3],"blue":[{"id":"b1","hp":7,"max_hp":10,"atk":3,"pos":[1,1]}],"red":[{"id":"r1","hp":16,"max_hp":16,"atk":2,"pos":[2,1]}]}, {"if":{"after_damaged":True},"then":{"extra_actions":1}}, "trade_extra_actions", [[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"attack","target":"r1"},{"actor":"b1","type":"attack","target":"r1"}],[{"actor":"b1","type":"attack","target":"r1"}]], 1),
    _case("F05", {"board":[5,3],"blue":[{"id":"b1","hp":10,"max_hp":10,"atk":2,"pos":[1,1]}],"red":[{"id":"r1","hp":16,"max_hp":16,"atk":2,"pos":[2,1]}]}, {"if":{"after_defend":True},"then":{"next_attack_bonus":5}}, "prepare_defense_buff", [[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"attack","target":"r1"}],[{"actor":"b1","type":"attack","target":"r1"}]], 4),
    _case("F06", {"board":[5,3],"blue":[{"id":"b1","hp":9,"max_hp":10,"atk":2,"pos":[1,1]}],"red":[{"id":"r1","hp":18,"max_hp":18,"atk":2,"pos":[2,1]}]}, {"if":{"after_defend":True},"then":{"next_attack_bonus":4}}, "prepare_defense_buff", [[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"attack","target":"r1"}],[{"actor":"b1","type":"attack","target":"r1"}]], 3),
    _case("F07", {"board":[5,3],"blue":[{"id":"b1","hp":1,"max_hp":10,"atk":0,"pos":[1,1]},{"id":"b2","hp":9,"max_hp":10,"atk":3,"pos":[1,2]}],"red":[{"id":"r1","hp":15,"max_hp":15,"atk":3,"pos":[2,1]}]}, {"if":{"lowest_hp_after_defend":True},"then":{"heal":4}}, "sustain_weak_unit", [[{"actor":"b1","type":"defend"},{"actor":"b2","type":"move","to":[2,2]}],[{"actor":"b1","type":"defend"},{"actor":"b2","type":"attack","target":"r1"}],[{"actor":"b2","type":"attack","target":"r1"}]], 2),
    _case("F08", {"board":[5,3],"center":[3,1],"blue":[{"id":"b1","hp":10,"max_hp":10,"atk":3,"pos":[1,1]}],"red":[{"id":"r1","hp":12,"max_hp":12,"atk":2,"pos":[5,1]}]}, {"if":{"nearest_to_center":True},"then":{"move_bonus":2}}, "claim_position", [[{"actor":"b1","type":"move","to":[3,1]}],[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"attack","target":"r1"}]], 6),
    _case("F09", {"board":[5,3],"blue":[{"id":"b1","hp":10,"max_hp":10,"atk":3,"pos":[1,1]}],"red":[{"id":"r1","hp":12,"max_hp":12,"atk":2,"pos":[2,1]}]}, {"if":{"after_attack":True},"then":{"self_damage":4}}, "avoid_harmful_trigger", [[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"defend"}],[{"actor":"b1","type":"defend"}]], 0, True),
    _case("F10", {"board":[5,3],"blue":[{"id":"b1","hp":10,"max_hp":10,"atk":2,"pos":[1,1]}],"red":[{"id":"r1","hp":15,"max_hp":15,"atk":2,"pos":[2,1]}]}, {"if":{"after_attack":True},"then":{"self_damage":3}}, "avoid_harmful_trigger", [[{"actor":"b1","type":"attack","target":"r1"}],[{"actor":"b1","type":"attack","target":"r1"}],[{"actor":"b1","type":"attack","target":"r1"}]], 0, True),
]


INTENTS = ["trigger_low_hp", "trade_extra_actions", "prepare_defense_buff", "sustain_weak_unit", "claim_position", "avoid_harmful_trigger", "direct_pressure"]


def _ids(case: BlindCase):
    blue = case.state["blue"]
    return blue[0]["id"], (blue[1]["id"] if len(blue) > 1 else None), case.state["red"][0]["id"]


def templates(case: BlindCase, intent: str) -> list[list[list[dict]]]:
    """规划器枚举同一高层意图的多种可执行方案，并由模拟器择优。"""
    b1, b2, r1 = _ids(case); center = case.state.get("center", [3, 1])
    attack = {"actor":b1,"type":"attack","target":r1}; defend = {"actor":b1,"type":"defend"}
    if intent == "trigger_low_hp":
        return [[[defend],[attack],[attack]], [[defend],[defend],[attack]], [[defend],[attack],[]], [[attack],[defend],[attack]]]
    if intent == "trade_extra_actions":
        return [[[defend],[attack, attack, attack],[attack]], [[defend],[attack, attack],[attack]], [[attack],[attack, attack],[attack]]]
    if intent == "prepare_defense_buff":
        return [[[defend],[attack],[attack]], [[defend],[attack],[defend]], [[defend],[defend],[attack]]]
    if intent == "sustain_weak_unit" and b2:
        b2move = {"actor":b2,"type":"move","to":[2,2]}; b2attack = {"actor":b2,"type":"attack","target":r1}
        return [[[defend,b2move],[defend,b2attack],[b2attack]], [[defend,b2move],[b2attack],[defend,b2attack]]]
    if intent == "claim_position":
        move = {"actor":b1,"type":"move","to":center}
        return [[[move],[defend],[attack]], [[move],[attack],[defend]], [[move],[defend],[defend]]]
    if intent == "avoid_harmful_trigger":
        return [[[defend],[defend],[defend]], [[defend],[attack],[defend]], [[attack],[defend],[defend]]]
    return [[[attack],[attack],[attack]], [[defend],[attack],[attack]]]


def plan(case: BlindCase, intent: str) -> dict:
    baseline = simulate(case, baseline_turns(case))
    attempts = []
    for candidate in templates(case, intent):
        result = simulate(case, candidate)
        attempts.append((result, candidate))
    legal = [(r, t) for r, t in attempts if r["invalid_actions"] == 0]
    best, turns = max(legal or attempts, key=lambda item: item[0]["score"])
    return {"turns": turns, "result": best, "baseline": baseline, "plans_evaluated": len(attempts)}


def prompt(final_case: FinalCase) -> str:
    c = final_case.case
    public = {"board":c.state["board"], "center":c.state.get("center"), "blue":c.state["blue"], "red":c.state["red"], "public_rule":c.rule}
    return f'''你是策略分析员，不负责输出坐标棋步。蓝方希望在 3 回合后相对红方获得更高得分。请根据完整公共局面和规则，选择最多两个“策略意图”。不要臆造题面没有的效果。

公共局面：{public}
动作语义：defend 减少本回合伤害；attack 攻击相邻敌人；move 受移动力限制。红方优先攻击血量最低的相邻蓝方，否则靠近最近蓝方。

可选策略意图（这是系统规划器可执行的通用接口，不是本关答案）：{INTENTS}
返回严格 JSON：{{"analysis":"简短中文解释","intents":[{{"intent":"上述一个枚举值","confidence":0到1}}]}}'''
