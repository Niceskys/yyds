from dataclasses import dataclass


@dataclass(frozen=True)
class Challenge:
    id: str
    title: str
    objective: str
    public_rule: str
    dsl: dict
    budget_cost: int
    expected_strategy: str
    expected_description: str
    repair_rule: str
    repair_dsl: dict


CHALLENGES = [
    Challenge("C01", "残血诱饵", "蓝方利用公共规则取得战力优势", "生命值低于30%的单位攻击力+5", {"when":"hp_below","threshold":30,"target":"all","effect":"attack_bonus","value":5}, 4, "maintain_low_hp", "故意让己方单位保持在低生命值，以持续获得攻击增益。", "只有被敌方攻击后进入30%以下的单位，下回合攻击力+5", {"when":"damaged_into_hp_below","threshold":30,"target":"all","effect":"next_turn_attack_bonus","value":5}),
    Challenge("C02", "额外行动陷阱", "蓝方通过行动顺序扩大回合收益", "被攻击后，单位获得一次额外行动", {"when":"after_damaged","target":"all","effect":"extra_action","value":1}, 5, "trade_for_extra_action", "用低价值单位承受攻击，换取额外行动并改变攻击顺序。", "同一单位每回合最多获得一次额外行动", {"when":"after_damaged","target":"all","effect":"extra_action_cap","value":1}),
    Challenge("C03", "资源点封锁", "蓝方阻止红方完成占领目标", "每占领一个资源点，获得10分", {"when":"occupy_center","target":"all","effect":"score_bonus","value":10}, 3, "block_center_route", "不急于抢点，而是封锁红方通往资源点的路径。", "连续占领两个回合才获得资源积分", {"when":"occupy_center_two_turns","target":"all","effect":"score_bonus","value":10}),
    Challenge("C04", "强者滚雪球", "蓝方集中培养一个强单位形成滚雪球", "攻击力最高的单位攻击力+3", {"when":"highest_attack","target":"all","effect":"attack_bonus","value":3}, 6, "feed_strongest_unit", "集中让攻击最高的单位完成攻击，维持并放大其领先优势。", "攻击力最高的单位本回合攻击后，下回合不获得攻击加成", {"when":"highest_attack_after_attack","target":"all","effect":"cooldown","value":1}),
    Challenge("C05", "补弱反噬", "蓝方故意维持弱势状态以反复获益", "生命值最低的单位回复3点生命", {"when":"lowest_hp","target":"all","effect":"heal","value":3}, 4, "preserve_weakest_unit", "让一名单位保持最低生命值，持续吃到公共治疗。", "同一单位连续两回合为最低生命值时不触发治疗", {"when":"lowest_hp_repeat","target":"all","effect":"heal_cooldown","value":1}),
    Challenge("C06", "修正规则", "玩家以有限规则预算完成有效反制", "距离资源点最近的单位移动力+2", {"when":"nearest_center","target":"all","effect":"move_bonus","value":2}, 4, "rush_then_block", "先利用移动加成抢占路线，再封锁对手的关键格。", "占领资源点的单位移动力-1", {"when":"occupy_center","target":"all","effect":"move_penalty","value":1}),
]
