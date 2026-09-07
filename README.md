# 规则之外（暂定名）

> 一个以“自然语言动态规则 + 双 AI 独立对抗”为核心机制的策略游戏。

## 项目一句话说明

真人玩家不直接控制角色，而是在战斗过程中为**红蓝双方同时颁布公共规则**；红方 AI 与蓝方 AI 在**思想、记忆完全隔离**的条件下，各自以“尽可能高概率并尽可能快地消灭对方”为目标自主决策。真人玩家则尝试通过不断改变双方共同遵守的规则，在避免无意义永久停滞的前提下尽可能延长对局。

对局允许产生明确的 terminal result，包括：

- 单方胜利；
- 双方同归于尽；
- 达到最大回合后的超时。

V0.1 对 Agent terminal utility、anti-stall/liveness、同步移动 occupancy、Rule DSL 最小语义和规则对称性已经形成 P0 冻结规范；这些规范是 Engine MVP 的实现基线，但具体平衡数值仍需 simulation 验证。

这不是“玩家操控棋子打 AI”的游戏，也不是“两个大模型随意聊天式对战”。核心体验是：

**制定规则 → AI 适应规则并博弈 → 玩家观察行为变化 → 再次改规则 → 博弈继续。**

## 当前版本

当前设计基线为 **V0.1 Draft**，目标是先做出可运行、可验证、可展示的最小完整游戏循环。

V0.1 暂定：

- 5×5 方格地图；
- 红蓝双方各 1 个单位（1v1）；
- 每个单位拥有刀和弓；
- 双方 AI 独立上下文、独立记忆，不共享内部推理；
- 双方同步决策，由确定性游戏引擎统一结算；
- 真人玩家定期输入一条自然语言公共规则；
- 大模型负责理解自然语言规则与高层策略推理；
- 规则验证器和游戏引擎负责合法性、数值计算和最终状态，不允许大模型直接修改游戏状态。

> 注意：地图大小、HP、伤害、射程、回合上限、anti-stall 阈值等目前属于**待模拟验证参数**，不是最终平衡结论。

## V0.1 P0 Rule Freeze

以下五个此前阻断 Engine 的核心语义已经形成唯一实现基线：

1. **Agent terminal utility**：使用显式词典序效用，确定 `WIN / DRAW_MUTUAL_DEATH / LOSS / TIMEOUT` 的比较关系；
2. **Liveness**：采用分级 anti-stall，并保留不可被玩家规则取消的 Hard Liveness 系统兜底；
3. **同步移动 occupancy**：`STAY` 产生占位意图，多子步移动按 joint transition 同步结算；
4. **Rule DSL**：V0.1 使用封闭、有限、可验证的 AST 语义，GLM 只负责生成候选 AST；
5. **规则对称性**：同时要求 faction neutrality 与 ex-ante symmetry，V0.1 暂不开放绝对位置条件。

完整冻结规范：

**[`docs/P0_RULE_FREEZE_V0.1.md`](docs/P0_RULE_FREEZE_V0.1.md)**

这并不表示玩法已经被证明平衡，只表示开发者不再需要自行猜测上述五类核心语义。

## 开发人员必读

完整设计草案：

**[`docs/GAME_DESIGN_V0.1.md`](docs/GAME_DESIGN_V0.1.md)**

深度研究后的客观审计决策：

**[`docs/RESEARCH_AUDIT_DECISIONS_2026-09-07.md`](docs/RESEARCH_AUDIT_DECISIONS_2026-09-07.md)**

P0 冻结规范：

**[`docs/P0_RULE_FREEZE_V0.1.md`](docs/P0_RULE_FREEZE_V0.1.md)**

如果 `GAME_DESIGN_V0.1.md` 与 `P0_RULE_FREEZE_V0.1.md` 在以下范围冲突：

- terminal utility；
- anti-stall / liveness；
- movement occupancy；
- Rule DSL V0.1；
- symmetry；

则以 **`P0_RULE_FREEZE_V0.1.md` 为准**。

## 当前开发原则

1. **游戏引擎是最终裁判。** AI 只能提出行动，不能直接写入棋盘、HP、伤害等状态。
2. **规则必须满足公开且可验证的公平约束。** 仅“不写 RED/BLUE”不足以证明对称；需要结构化 Validator 和对称性测试。
3. **两个 AI 必须隔离。** 只能看到公共状态和公开历史，不能读取对方内部思考、计划或私人记忆。
4. **先完成 1v1 MVP。** 暂不加入职业、障碍、复杂地形、道具、多人单位等扩展机制。
5. **先验证基础战斗，再扩展规则库。** 当前目标是让无玩家干预时的基础战斗具有合理时长、可终止性和可理解策略。
6. **自然语言不直接执行。** 玩家输入必须先被结构化，再经过规则验证器检查，只有合法结构化规则才能进入游戏引擎。
7. **LLM 与 Engine 解耦。** 不调用 LLM 时，使用 fake/recorded model output 也应能测试完整引擎与 Replay 链路。
8. **先模拟再扩展。** 对“5×5 是否合适”“玩家是否会形成单一拖延策略”“anti-stall 阈值是否合理”等问题，用批量模拟与试玩数据判断，不把研究推测直接当结论。
9. **规范优先于实现猜测。** Engine 遇到规范未定义行为时，不允许自行发明语义。

## 当前推荐开发顺序

```text
P0 Rule Freeze（当前已形成规范）
→ Deterministic Engine
→ Engine Unit Tests
→ Simple Bots + Simulation Harness
→ 验证 liveness / symmetry / balance
→ Rule DSL + Validator 实现
→ GLM Rule Interpreter
→ 双 Agent + Planner
→ Replay / Frontend
→ Competition Hardening
```

## 当前项目状态

**阶段：P0 Rule Freeze 已形成实现基线；下一阶段进入 Deterministic Engine + Unit Tests。**

当前仓库仍没有可运行 Game Engine，因此不能声称核心平衡、Agent 隔离、GLM 运行态作用、Replay 可复现或竞赛硬性要求已经被代码验证。
