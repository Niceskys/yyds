# Rule DSL + Validator V0.1 实现说明

> 状态：Implementation note  
> 依据：`docs/P0_RULE_FREEZE_V0.1.md` 第 4–6 章  
> 本文件不修改游戏设计，只说明本阶段代码已经做到什么、还没做到什么。

## 已实现

### RuleAST 固定结构

```json
{
  "version": "v0.1",
  "target": "ALL_UNITS",
  "conditions": [],
  "effect": {},
  "duration": "UNTIL_REPLACED"
}
```

支持规范中列出的 11 类 Condition 与 7 类 Effect。

### Deterministic Validator

当前检查：

- 根对象字段完整且不能带未知字段；
- `version = v0.1`；
- `target = ALL_UNITS`；
- `duration = UNTIL_REPLACED`；
- 0–2 个 Condition；
- 不支持 OR / NOT / 嵌套条件；
- Condition / Effect 白名单；
- HP / distance / round / consecutive 阈值；
- effect 应用到当前 GameConfig 后的普通模式数值边界；
- `WEAPON_COOLDOWN` 只能指定 KNIFE/BOW 且只能 1 回合；
- `delta=0`、`multiplier=1` 等明显 no-effect；
- 部分直接矛盾条件；
- RED/BLUE target、绝对位置条件、winner/HP/revive/max-rounds/liveness 等能力不能进入白名单。

Validator 不调用 LLM，也不修改 GameState。

## 一个需要明确记录的边界：BOW_HIT_MULTIPLIER(0)

冻结规范规定：

```text
base probability
→ × player multiplier
→ clamp(0.05, 1.0)
→ anti-stall
```

因此：

```text
BOW_HIT_MULTIPLIER(0)
```

在普通模式中的最终概率会被 clamp 到 5%，而不是 0%。

冻结规范只给出了**最终命中率 5%..100%**，没有额外给出 raw multiplier 的最小/最大范围。

所以当前 Validator：

- 接受有限数值 multiplier；
- `multiplier=1` 作为 NO_EFFECT_RULE 拒绝；
- 不允许任何直接设置命中率的非白名单 effect；
- 真正的 5%..100% clamp 将在 Rule Evaluator / Engine integration 阶段实现并测试。

如果团队未来希望规定 `multiplier > 0` 或其他 raw multiplier 范围，应作为独立规范变更，而不是在 Validator 内偷偷添加设计规则。

## 当前还没有实现

### 1. Rule Evaluator

目前 RuleAST 通过 Validator 后还不会真正修改：

- move range；
- weapon range；
- damage；
- bow probability；
- cooldown。

这是下一阶段。

### 2. 历史型 Condition 的运行时状态

以下 Condition 已能被解析和验证，但尚未运行时求值：

```text
DID_NOT_MOVE_LAST_ROUND
LAST_ATTACK_WEAPON_IS
CONSECUTIVE_BOW_MISS_GTE
CONSECUTIVE_SAME_WEAPON_USE_GTE
```

因为当前 GameState 还没有冻结这些公开历史字段的数据结构。

下一阶段必须先给公开历史定义唯一状态，再实现 evaluator，不能让不同模块自己从 Event Log 猜。

### 3. Ex-Ante Symmetry 的运行时 metamorphic test

当前 DSL 通过白名单天然排除了：

- faction id；
- unit id；
- absolute row/col；
- spawn-side 条件。

这建立了结构层的 faction neutrality。

但规范要求的：

```text
swap team + mirror board
```

metamorphic test 必须在 Rule Evaluator 实现后才能真正验证“同一规则对镜像状态产生镜像效果”。

因此当前阶段不能声称完整 symmetry runtime test 已完成。

## 下一步

```text
冻结 Public Rule History State
→ Deterministic Rule Evaluator
→ Rule + Engine integration
→ symmetry metamorphic tests
→ dynamic-rule simulation
```

在这些完成以前仍不接 GLM。
