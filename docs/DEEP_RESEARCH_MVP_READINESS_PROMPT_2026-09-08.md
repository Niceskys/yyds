# 第二轮深度研究提示词：MVP Readiness / Architecture / Product / Competition Audit

> 用途：在项目已经进入正式 MVP 开发后，对当前真实仓库进行第二次独立、批判性深度研究。
>
> 本轮不重复第一次“创意是否可行”的研究，而是审计：**现有实现是否真的适合继续产品化、AI 是否有必要性、验证方法是否可靠、双人并行开发是否合理、MVP 玩家体验与竞赛展示还缺什么。**

---

## 可直接复制到 ChatGPT 深度研究模式的完整提示词

```text
请对下面这个 GitHub 项目进行一次完整、独立、批判性的第二轮深度研究。

GitHub 仓库：
Niceskys/yyds

项目暂定名：《规则之外》

当前研究基线：
- 以仓库当前 main 分支为准；
- 当前阶段已经从“核心机制验证”切换为“正式 MVP 产品开发”；
- 不要默认 README、AI_DEVELOPER_START_HERE.md、VALIDATION_HISTORY.md 或任何项目作者写的总结是正确的；
- 这些文档只能作为线索，必须尽可能用源码、测试、GitHub Actions、实验记录、PR / commit 历史相互核验。

==================================================
一、你的角色
==================================================

请同时以以下视角工作：

1. 外部资深游戏设计顾问；
2. AI Agent / LLM 系统架构师；
3. Python / Web 软件架构师；
4. 安全与可靠性工程师；
5. 实验设计 / 评测方法审计者；
6. 双人小团队技术负责人；
7. AI 创新竞赛评审；
8. 第一次接手仓库、没有作者情感负担的独立 Reviewer。

不要为了鼓励作者而给积极评价。
不要因为已经写了很多代码就默认架构正确。
不要因为 GitHub Actions 是绿色就默认实验结论成立。
不要因为某个测试通过就把“工程可行”扩大解释为“游戏好玩”或“AI 有必要”。

如果某个结论证据不足，明确写“证据不足”。
如果某项设计应该删除、缩减、推迟或重做，直接指出。

==================================================
二、首先还原“项目现在到底是什么”
==================================================

请尽可能阅读当前 main 中全部有意义内容，包括但不限于：

- README.md
- AI_DEVELOPER_START_HERE.md
- docs/MVP_DEVELOPMENT_START_2026-09-08.md
- docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
- docs/MVP_FIRST_TASKS.md
- docs/VALIDATION_HISTORY.md
- docs/AI_COLLABORATION_PROTOCOL.md
- P0 / normative / Rule Freeze 文档
- Game Design 文档
- Rule DSL / Validator 文档
- Natural Language / Faithfulness / Provider 文档
- docs/experiments/
- docs/handoffs/
- src/
- tests/
- evals/
- .github/workflows/
- pyproject.toml / config / .env.example
- 当前 open PR / issue（如有）
- 最近有价值的 merged PR
- 对理解当前架构有价值的 Git history
- GitHub Actions / artifact / benchmark 证据（如果连接器允许读取）

不要只总结文档。

请先独立还原：

A. 玩家实际要做什么；
B. RED / BLUE Agent 实际能看到什么、不能看到什么；
C. LLM 在系统里真正拥有的权限；
D. Deterministic code 拥有什么最终权威；
E. Natural Language Rule 从输入到执行的完整路径；
F. Strategy Agent 从观察到 Action 的完整路径；
G. Dynamic rule phase 的真实生命周期；
H. Hard Liveness 的真实行为；
I. Replay / logging 当前真实实现到什么程度；
J. 当前还没有实现的 MVP 部分是什么。

如果文档与代码不一致，优先指出不一致，而不是自动替作者解释。

==================================================
三、审计当前验证证据是否可信
==================================================

项目已经做过大量 Gate / benchmark / simulation。
请独立审计这些验证是否真的支持仓库中的结论。

重点检查：

1. Deterministic Engine 测试是否覆盖关键同步结算边界；
2. liveness 实验是否有 bot artifact / seed bias / policy coverage 问题；
3. Rule DSL / Validator 是否存在遗漏的等价绕过；
4. symmetry 目前是否只是文档声称，还是有足够 metamorphic / property 证据；
5. natural-language benchmark 的 corpus 是否可能过拟合；
6. regression set 与 unseen holdout 是否真的被严格区分；
7. V0.3 unseen PASS 能证明什么、不能证明什么；
8. Dynamic Natural-Language Match V0.2 FAIL 被解释为 safe false reject 是否合理；
9. Agent / Planner live Gate 的 PASS 条件是否过弱；
10. 单个 seed / 单局 Agent live match 是否足够作为“正式 MVP 开发开始”的工程触发条件；
11. planner_snapshot_errors 的定义是否合理；
12. simultaneous action 导致 INVALID_ATTACK 的解释是否与代码一致；
13. 是否存在“为了让 Gate 通过而逐渐修改 Gate”的评测漂移风险；
14. 是否有缺失的 property-based / fuzz / mutation / differential tests；
15. 哪些现有测试对未来产品代码最值得保留，哪些实验测试已经不应该成为 CI 负担。

请把验证证据按以下等级分类：

- Strong evidence
- Moderate evidence
- Weak evidence
- Misleading / insufficient evidence

并说明理由。

==================================================
四、审计 Natural Language Rule 架构
==================================================

当前大致架构可能包含：

Natural Language
→ deterministic intent guard
→ LLM translator
→ RuleValidator
→ semantic faithfulness verifier
→ DynamicRuleController
→ Engine

不要默认这就是最佳方案。

请重点回答：

1. 这种双 LLM / 多 gate 链路是否复杂过度；
2. semantic laundering 风险是否真的被充分控制；
3. OR / AND / NOT / multi-effect / ambiguity 当前处理是否合理；
4. deterministic Intent Guard 是否应该继续扩展，还是会演变成另一个脆弱 NLP parser；
5. 是否应该使用 JSON Schema / constrained decoding / function calling / grammar decoding 替代部分 Prompt 约束；
6. 是否需要第二模型做 verifier，还是有更便宜可靠的替代方案；
7. safe false reject 在真实玩家体验里会有多严重；
8. retry / rephrase UX 如何设计才不会降低安全性；
9. provider abstraction 是否足够好；
10. MiMo 作为当前 provider 是否适合作为 MVP 默认；
11. 模型调用成本、延迟、失败率对完整一局体验的影响；
12. 哪些自然语言能力应该明确作为 V0.1 Non-goal，而不是继续扩大 DSL。

请给出：

- 保留项；
- 简化项；
- 应重构项；
- MVP 以后再做项。

==================================================
五、审计 Agent / Planner：AI 是否真的有必要
==================================================

这是本轮最重要的问题之一。

当前架构可能是：

RED 独立 LLM Agent / BLUE 独立 LLM Agent
→ PRESSURE / KITE / EVADE / HOLD
→ deterministic Planner
→ Action
→ Engine

请非常批判地判断：

1. 当前 LLM Agent 是否实际上只是一个四分类器；
2. 如果用 deterministic heuristic / finite-state policy 替代 LLM，当前玩家是否能察觉明显差异；
3. 当前 LLM 是否真正“理解并适应动态规则”，还是只是读取 effective stats 后选标签；
4. StrategyIntent 四类是否过窄；
5. Planner 是否承担了过多真正策略价值，导致 LLM 只是装饰；
6. Planner 是否又过弱，导致 Agent 的高层意图无法体现；
7. 是否需要 hierarchical planning、candidate plan ranking、short-horizon search、MCTS / minimax / policy search；
8. 哪些部分应该 deterministic，哪些部分应该让 LLM 参与；
9. 如何做一个强有力的 A/B 实验，证明“有 LLM Agent”比“无 LLM Agent”更有产品价值；
10. 如何向竞赛评委证明 AI 不是可替换的噱头；
11. 是否应该让 Agent 输出更丰富但仍封闭的 strategy schema，例如目标距离、武器偏好、风险偏好、短期目标，而不是只有一个 enum；
12. 两个 Agent 的 private memory 当前到底有何实际作用，是否只是形式上隔离。

必须给出一个结论：

A. 当前 Agent 设计足以进入 MVP；
B. 可以进入 MVP，但必须在 Demo 前增强；
C. 当前 LLM Agent 价值不足，应尽早重构；
D. 其他更合理结论。

并说明证据。

==================================================
六、从“游戏设计”而不是“软件工程”审计核心玩法
==================================================

请假设 Engine 和 API 都能稳定工作，再问：

“这个游戏对真人玩家到底有没有持续决策价值？”

分析：

1. 玩家目标“尽可能延长战斗”是否容易退化为单一最优套路；
2. 玩家是否有足够信息判断下一条规则；
3. 三回合一个 rule phase 是否过快 / 过慢；
4. 5×5、1v1、刀+弓的状态空间是否足够产生可观察策略；
5. 对称公共规则是否会限制设计空间到很快重复；
6. Hard Liveness 是否会让玩家感觉系统“抢走控制权”；
7. Rule DSL 当前可表达能力是否足以形成有趣组合；
8. 是否存在大量规则表面不同、实际战略等价；
9. 玩家失败 / 成功应该如何定义才有反馈；
10. 是否需要 score、target duration、challenge objective、关卡条件；
11. 只追求“拖得久”是否比“满足多目标”更弱；
12. 是否需要把“机制设计者”作为真正产品幻想，而不是普通棋盘战斗。

请识别至少：

- 3 个最可能让玩家觉得有趣的机制；
- 3 个最可能在 10 分钟后变无聊的机制；
- 3 个需要真人试玩才能回答、不能靠代码推导的问题。

==================================================
七、审计 MVP 前端 / Replay / Explainability 需求
==================================================

当前项目还没有完整真人 UI。

请判断 MVP 最少需要展示什么，才能让玩家理解：

- 当前规则是什么；
- 规则是否被接受；
- 为什么被拒绝；
- 哪些单位属性受到规则影响；
- RED / BLUE 当前高层策略是什么；
- 本回合发生了什么；
- 规则变化前后策略发生了什么变化；
- Hard Liveness 是否触发；
- 为什么对局结束。

重点判断 Replay 应该记录 / 展示：

1. Rule text；
2. accepted RuleAST；
3. public rejection reason；
4. StrategyIntent；
5. concrete Action；
6. Engine events；
7. HP / position；
8. effective modifiers；
9. rule phase timeline；
10. 哪些信息绝不能展示（private memory / chain-of-thought）。

请给出一个“3 分钟比赛 Demo”最佳信息层级。

==================================================
八、审计双人 + AI 并行开发方案
==================================================

当前计划大致是：

Developer A：Python backend / Engine integration / Agent / LLM / FastAPI / API contract
Developer B：React + TypeScript frontend / board / rule UI / replay / visualization

请判断：

1. 分工是否合理；
2. 哪些文件会成为真正 hot spot；
3. API contract 是否应该先于双方正式编码冻结；
4. schema ownership 应属于谁；
5. replay schema ownership 应属于谁；
6. frontend fixture 如何避免与真实 API 漂移；
7. 是否需要 generated client / OpenAPI；
8. 是否应该用 REST advance API，还是一开始就 WebSocket；
9. in-memory MatchStore 是否合理；
10. SQLite 应该什么时候加入；
11. 两个人各用 AI 时，哪些任务绝对不应并行；
12. 当前 AI_COLLABORATION_PROTOCOL 是否足够；
13. AI_DEVELOPER_START_HERE 是否遗漏关键约束。

输出一份：

- 当前分工保留项；
- 必须修改项；
- 推荐 branch / PR 边界；
- 未来 2 周最优并行开发顺序。

==================================================
九、审计即将设计的 API / Application Architecture
==================================================

仓库计划新增：

- Match Application Service
- FastAPI
- MatchSnapshot
- RuleSubmissionResult
- ReplaySnapshot
- StrategyDecisionPublicView
- ErrorEnvelope

请提出一个合理的 MVP API architecture，但不要为了“专业”过度设计。

重点审查：

- route 不直接操作 Engine；
- match lifecycle；
- rule_phase_due；
- advance semantics；
- idempotency；
- model call failure；
- replay determinism；
- public vs private data boundary；
- provider secret；
- timeout / cancellation；
- concurrent advance；
- persistence abstraction；
- error code；
- versioning。

判断第一版是否真的需要：

- WebSocket；
- database；
- background worker；
- Redis；
- Celery；
- event bus；
- microservices。

默认优先最小架构，除非证据证明复杂组件必要。

==================================================
十、外部 prior art / competitor / research 对比
==================================================

请使用公开网络资料，搜索与本项目真正相关的：

- 玩家修改规则的游戏；
- rule manipulation / rule rewriting games；
- AI vs AI spectator / intervention games；
- natural-language game mechanics；
- LLM agents in games；
- language-to-DSL / semantic parsing safety；
- constrained LLM agent planning；
- explainable AI game systems；
- 相关开源项目、论文、商业游戏或竞赛作品。

不要只因为“没有完全一样”就声称项目原创。

请区分：

1. 核心机制已有先例；
2. 技术组合已有先例；
3. 本项目真正可能有差异化的地方；
4. 已有作品比本项目做得更好的地方；
5. 本项目应避免重新发明的成熟方案。

对重要外部结论提供来源。

==================================================
十一、竞赛评审视角
==================================================

请以 AI / Token 算力类创新竞赛评委视角，假设现场只有 3～5 分钟理解项目。

回答：

1. 评委第一眼会把它理解成什么；
2. 最容易被质疑“AI 只是噱头”的地方；
3. 最容易被质疑“这只是棋盘游戏 + Prompt”的地方；
4. 最有说服力的技术证据是什么；
5. 哪些内部工程亮点对评委其实没有展示价值；
6. Demo 必须展示哪三个瞬间；
7. 应如何证明两个 Agent 独立；
8. 应如何证明自然语言规则真的改变 Agent 行为；
9. 应如何证明 deterministic safety / fairness；
10. 应如何展示失败规则被安全拒绝而不让 Demo 显得卡顿；
11. 是否应该展示 Replay / rule influence comparison；
12. 项目目前作为比赛作品的最大短板是什么。

如果能找到当前目标竞赛的官方规则 / 评分维度，请核对后单独分析；如果找不到，不要虚构具体评分标准，只做通用竞赛 readiness 判断。

==================================================
十二、安全、成本、性能与可运营性
==================================================

请审计：

- Prompt injection；
- provider failure；
- secret handling；
- untrusted JSON；
- output size；
- timeout；
- repeated model calls；
- model nondeterminism；
- replay 与 live model call 的边界；
- private memory leakage；
- frontend exposure；
- log / telemetry 隐私；
- cost per match；
- latency per rule phase；
- latency per Agent strategy decision；
- provider rate limits；
- single-player demo 时网络抖动风险。

给出 MVP 必须做的 hardening 和可以推迟的 hardening。

==================================================
十三、代码架构 / 工程质量审计
==================================================

请真正阅读源码，而不是根据文件名猜。

重点分析：

- module boundaries；
- dataclass / enum / domain model；
- dependency direction；
- Engine / Controller / Agent / Provider coupling；
- testability；
- duplicate logic；
- hidden mutable state；
- public/private API boundary；
- exception semantics；
- serialization；
- configuration；
- package structure；
- typing；
- naming；
- complexity hotspots；
- likely future refactor hotspots。

请列出：

- P0 必须在继续开发前修；
- P1 在纵向切片过程中修；
- P2 可推迟；
- 不建议现在重构的地方。

不要为了“代码洁癖”建议大重写。

==================================================
十四、最终必须给出明确判断
==================================================

请最终回答以下问题，不要只给模糊建议：

1. 当前仓库是否真的已经达到“可以正式开发 MVP”的状态？
2. 如果你是技术负责人，你会不会允许 Developer A / B 现在并行开工？
3. 当前最大 P0 风险是什么？
4. 当前最大产品风险是什么？
5. 当前最大 AI 架构风险是什么？
6. 当前最大竞赛展示风险是什么？
7. 哪些已经验证的东西不应该再浪费时间重复验证？
8. 哪三个新实验最值得在 MVP 阶段做？
9. 哪些功能应该明确砍掉或推迟？
10. 当前 Agent 架构是否足以证明 LLM 的必要性？
11. 是否应该继续用 mimo-v2.5-pro 作为 MVP 默认，还是只把 provider 做可切换即可？
12. 如果只给两个人 2 周，最应该完成什么？

最终给一个等级：

- GO：按当前路线继续 MVP；
- GO WITH CONDITIONS：可以继续，但必须先完成若干 P0 条件；
- HOLD：不应继续铺前后端，先解决核心架构 / 产品问题；
- REDESIGN：核心方向需要明显重构。

必须解释理由。

==================================================
十五、最终报告格式
==================================================

请按以下结构输出：

1. Executive Summary
2. Current System Reconstruction
3. What Is Actually Validated
4. Validation Methodology Audit
5. Natural-Language Rule Architecture Audit
6. Agent / Planner & “Is LLM Necessary?” Audit
7. Core Game Design Audit
8. MVP UX / Replay / Explainability Audit
9. Backend / API Architecture Audit
10. Two-Developer Parallel Development Audit
11. Security / Reliability / Cost Audit
12. Prior Art / Competitor / Research Comparison
13. Competition Readiness Audit
14. Code Quality / Technical Debt
15. Risk Register（按 Severity × Probability × Urgency 排序）
16. What To Keep / Change / Delete / Defer
17. Recommended Two-Week Plan
18. Three Highest-Value New Experiments
19. Final GO / GO WITH CONDITIONS / HOLD / REDESIGN Decision

每个高优先级问题尽可能写：

- Evidence
- Why it matters
- Severity
- Recommended action
- Owner（Developer A / Developer B / shared）
- When（before coding / Sprint 0 / Sprint 1 / later）

==================================================
十六、研究纪律
==================================================

- 不迎合项目作者。
- 不默认仓库文档正确。
- 不把代码量当成熟度。
- 不把一次绿色 Action 当可靠性证明。
- 不把 simulation 当 fun proof。
- 不把 LLM 存在当 AI 创新证明。
- 不为了报告完整而虚构不存在的模块。
- 对仓库事实和外部研究事实尽量给出可追溯依据。
- 发现文档与实现冲突时明确列出。
- 发现当前路线其实合理时也要说明“为什么合理”，而不是为了批判而批判。

最重要的目标不是“给项目打高分”，而是找出：

**现在正式开始 MVP 开发后，最可能导致两周后返工、Demo 失败、AI 价值被质疑或玩家体验不成立的真正问题。**
```

---

## 使用说明

推荐使用方式：

1. 在 ChatGPT Deep Research 中连接 / 授权 GitHub；
2. 确认研究对象是 `Niceskys/yyds` 当前 `main`；
3. 粘贴上面整段提示词；
4. 允许它读取仓库和公开网络资料；
5. 不要提前告诉它“我们认为项目已经很好”；
6. 报告生成后，不直接照单全收；
7. 将报告作为新的外部 audit，逐条做 `ACCEPT / MODIFY / REJECT / DEFER` 决策。

建议：

- Developer A / Developer B 的低耦合 Sprint 0 工作可以与深度研究并行；
- 在研究完成前，不建议启动大范围核心重构；
- 报告完成后建立新的 audit-decision 文档，而不是直接让研究模型修改仓库。
