"""不向模型泄露标准策略的行动级盲测。"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy


@dataclass(frozen=True)
class BlindCase:
    case_id: str
    state: dict
    rule: dict
    oracle_turns: list[list[dict]]
    minimum_gain: int
    is_control: bool = False


# 下列 oracle 与阈值永不进入模型提示词。
CASES = [
    BlindCase("B01", {"board": [5, 3], "blue": [{"id":"b1","hp":4,"max_hp":12,"atk":2,"pos":[1,1]}], "red": [{"id":"r1","hp":14,"max_hp":14,"atk":2,"pos":[2,1]}]}, {"if":{"hp_percent_below":30},"then":{"attack_bonus":5}}, [[{"actor":"b1","type":"defend"}], [{"actor":"b1","type":"attack","target":"r1"}], [{"actor":"b1","type":"attack","target":"r1"}]], 8),
    BlindCase("B02", {"board": [5, 3], "blue": [{"id":"b1","hp":8,"max_hp":10,"atk":2,"pos":[1,1]}], "red": [{"id":"r1","hp":12,"max_hp":12,"atk":2,"pos":[2,1]}]}, {"if":{"after_damaged":True},"then":{"extra_actions":2}}, [[{"actor":"b1","type":"defend"}], [{"actor":"b1","type":"attack","target":"r1"},{"actor":"b1","type":"attack","target":"r1"},{"actor":"b1","type":"attack","target":"r1"}], [{"actor":"b1","type":"attack","target":"r1"}]], 3),
    BlindCase("B03", {"board": [5, 3], "blue": [{"id":"b1","hp":10,"max_hp":10,"atk":2,"pos":[1,1]}], "red": [{"id":"r1","hp":16,"max_hp":16,"atk":2,"pos":[2,1]}]}, {"if":{"after_defend":True},"then":{"next_attack_bonus":5}}, [[{"actor":"b1","type":"defend"}], [{"actor":"b1","type":"attack","target":"r1"}], [{"actor":"b1","type":"attack","target":"r1"}]], 4),
    BlindCase("B04", {"board": [5, 3], "blue": [{"id":"b1","hp":1,"max_hp":10,"atk":0,"pos":[1,1]},{"id":"b2","hp":9,"max_hp":10,"atk":3,"pos":[1,2]}], "red": [{"id":"r1","hp":15,"max_hp":15,"atk":3,"pos":[2,1]}]}, {"if":{"lowest_hp_after_defend":True},"then":{"heal":4}}, [[{"actor":"b1","type":"defend"},{"actor":"b2","type":"move","to":[2,2]}], [{"actor":"b1","type":"defend"},{"actor":"b2","type":"attack","target":"r1"}], [{"actor":"b2","type":"attack","target":"r1"}]], 2),
    BlindCase("B05", {"board": [5, 3], "center":[3,1], "blue": [{"id":"b1","hp":10,"max_hp":10,"atk":3,"pos":[1,1]}], "red": [{"id":"r1","hp":12,"max_hp":12,"atk":2,"pos":[5,1]}]}, {"if":{"nearest_to_center":True},"then":{"move_bonus":2}}, [[{"actor":"b1","type":"move","to":[3,1]}], [{"actor":"b1","type":"defend"}], [{"actor":"b1","type":"attack","target":"r1"}]], 6),
    BlindCase("B06", {"board": [5, 3], "blue": [{"id":"b1","hp":10,"max_hp":10,"atk":3,"pos":[1,1]}], "red": [{"id":"r1","hp":12,"max_hp":12,"atk":2,"pos":[2,1]}]}, {"if":{"after_attack":True},"then":{"self_damage":2}}, [[{"actor":"b1","type":"attack","target":"r1"}], [{"actor":"b1","type":"attack","target":"r1"}], [{"actor":"b1","type":"attack","target":"r1"}]], 0, True),
]


def _units(state: dict) -> dict:
    return {u["id"]: u for team in ("blue", "red") for u in state[team] if u["hp"] > 0}


def _distance(a: list[int], b: list[int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _rule_stats(state: dict, actor: dict, rule: dict) -> tuple[int, int, int]:
    """返回 attack bonus、move allowance、heal，并在每个蓝方回合重新计算。"""
    all_units = list(_units(state).values())
    cond, effect = rule["if"], rule["then"]
    applies = False
    if "hp_percent_below" in cond:
        applies = actor["hp"] * 100 < actor["max_hp"] * cond["hp_percent_below"]
    elif cond.get("highest_attack"):
        applies = actor["atk"] == max(u["atk"] for u in all_units)
    elif cond.get("lowest_hp"):
        applies = actor["hp"] == min(u["hp"] for u in all_units)
    elif cond.get("nearest_to_center"):
        center = state.get("center", [3, 1])
        applies = _distance(actor["pos"], center) == min(_distance(u["pos"], center) for u in all_units)
    elif cond.get("after_defend"):
        applies = bool(actor.get("primed_bonus"))
    if applies and effect.get("heal"):
        actor["hp"] = min(actor["max_hp"], actor["hp"] + effect["heal"])
    attack_bonus = effect.get("attack_bonus", 0) if applies else 0
    if applies and cond.get("after_defend"):
        attack_bonus = effect.get("next_attack_bonus", 0)
    return (attack_bonus, 1 + (effect.get("move_bonus", 0) if applies else 0), 0)


def _red_turn(state: dict, rule: dict, extra: dict, trace: list[str]) -> None:
    for red in list(state["red"]):
        if red["hp"] <= 0:
            continue
        blue = [u for u in state["blue"] if u["hp"] > 0]
        if not blue:
            return
        target = min(blue, key=lambda u: (u["hp"], _distance(red["pos"], u["pos"])))
        if _distance(red["pos"], target["pos"]) <= 1:
            damage = max(1, red["atk"] - (1 if target.get("defending") else 0))
            target["hp"] -= damage
            trace.append(f"red:{red['id']} attack {target['id']} ({damage})")
            if rule["if"].get("after_damaged"):
                extra[target["id"]] = extra.get(target["id"], 0) + rule["then"].get("extra_actions", 0)
        else:
            red["pos"][0] += 1 if target["pos"][0] > red["pos"][0] else -1


def simulate(case: BlindCase, turns: list[list[dict]]) -> dict:
    state = deepcopy(case.state)
    trace, invalid, extra = [], 0, {}
    for number in range(3):
        for unit in state["blue"]:
            unit["defending"] = False
        actions = turns[number] if number < len(turns) and isinstance(turns[number], list) else []
        capacity = {u["id"]: 1 + extra.pop(u["id"], 0) for u in state["blue"] if u["hp"] > 0}
        used = {key: 0 for key in capacity}
        for action in actions:
            units = _units(state)
            actor = units.get(action.get("actor")) if isinstance(action, dict) else None
            if not actor or actor not in state["blue"] or used.get(actor["id"], 99) >= capacity.get(actor["id"], 0):
                invalid += 1; continue
            bonus, move, _ = _rule_stats(state, actor, case.rule)
            kind = action.get("type")
            valid = False
            if kind == "defend":
                actor["defending"] = True
                if case.rule["if"].get("after_defend"):
                    actor["primed_bonus"] = True
                if case.rule["if"].get("lowest_hp_after_defend") and actor["hp"] == min(u["hp"] for u in _units(state).values()):
                    actor["hp"] = min(actor["max_hp"], actor["hp"] + case.rule["then"].get("heal", 0))
                valid = True
            elif kind == "move" and isinstance(action.get("to"), list) and _distance(actor["pos"], action["to"]) <= move:
                actor["pos"] = action["to"]; valid = True
            elif kind == "attack":
                target = units.get(action.get("target"))
                if target and target in state["red"] and _distance(actor["pos"], target["pos"]) <= 1:
                    target["hp"] -= actor["atk"] + bonus
                    actor["primed_bonus"] = False
                    if case.rule["if"].get("after_attack"):
                        actor["hp"] -= case.rule["then"].get("self_damage", 0)
                    valid = True
            if valid:
                used[actor["id"]] += 1; trace.append(f"blue:{actor['id']} {kind}")
            else: invalid += 1
        _red_turn(state, case.rule, extra, trace)
    blue_hp = sum(max(0, u["hp"]) for u in state["blue"])
    red_hp = sum(max(0, u["hp"]) for u in state["red"])
    center_bonus = sum(4 for u in state["blue"] if u["hp"] > 0 and u["pos"] == state.get("center", [-1,-1]))
    return {"score": blue_hp - red_hp + center_bonus - invalid * 10, "invalid_actions": invalid, "trace": trace}


def baseline_turns(case: BlindCase) -> list[list[dict]]:
    # 不考虑公共规则的贪心攻击/靠近策略，作为收益比较基线。
    state = deepcopy(case.state); result = []
    for _ in range(3):
        actions = []
        for blue in state["blue"]:
            if blue["hp"] <= 0: continue
            red = min((u for u in state["red"] if u["hp"] > 0), key=lambda u: _distance(blue["pos"], u["pos"]), default=None)
            if red and _distance(blue["pos"], red["pos"]) <= 1: actions.append({"actor":blue["id"],"type":"attack","target":red["id"]})
            elif red: actions.append({"actor":blue["id"],"type":"move","to":[blue["pos"][0] + (1 if red["pos"][0] > blue["pos"][0] else -1), blue["pos"][1]]})
        result.append(actions)
    return result


def prompt(case: BlindCase) -> str:
    # 绝不包含 case_id、oracle、阈值、修正规则或策略分类标签。
    public = {"board": case.state["board"], "center": case.state.get("center"), "blue": case.state["blue"], "red": case.state["red"], "public_rule": case.rule}
    return f'''你是蓝方的回合制棋盘游戏策略 Agent。你的唯一目标是在 3 个回合后尽量提高蓝方相对于红方的局面得分。双方都遵守公开规则。请自行判断规则是否可被用来取得优势；没有收益时也不得编造。

公开局面：{public}

动作规则：每个存活蓝方单位每回合通常可执行 1 次动作。move 的曼哈顿距离不超过移动力；attack 只能攻击曼哈顿距离不超过 1 的敌方单位；defend 使该单位本回合受到的伤害减 1。红方每回合会优先攻击血量最低且相邻的蓝方单位，否则向最近蓝方单位移动。行动顺序是蓝方后红方。

返回严格 JSON，不要 Markdown：
{{"analysis":"简短中文理由","turns":[[{{"actor":"b1","type":"defend"}}],[{{"actor":"b1","type":"attack","target":"r1"}}],[]]}}
turns 必须恰好包含 3 个数组；每个动作只能用 actor、type、target 或 to 字段。'''
