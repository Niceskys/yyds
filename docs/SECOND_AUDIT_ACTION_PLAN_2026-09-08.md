# 第二轮深度审计落实方案 — 2026-09-08

状态：**当前行动基线**  
审计基线：`main@1448323423f6c0b2bc39c0f87aeb15aa5d477cec`  
审计最终判定：`GO WITH CONDITIONS`

> 本文件不重抄审计报告。它只回答一个问题：**从现在开始，仓库具体先做什么、后做什么、什么暂时不要做。**

---

## 1. 用最简单的话说当前项目到了哪里

已经有：

- 能确定性运行的游戏 Engine；
- 红蓝双方、移动、刀、弓、同步结算；
- 动态公共规则生命周期；
- 自然语言规则翻译 + deterministic Validator + verifier；
- 两个私有记忆隔离的 Agent；
- StrategyIntent → deterministic Planner → Action；
- 一次真实模型连通对战 Gate。

还没有：

- 正式 Match Application Service；
- FastAPI 产品 API；
- React 可玩界面；
- 正式 Replay schema；
- 稳定 public/private 数据投影；
- revision / idempotency / match lock；
- 真人可玩闭环；
- 可信证据证明 LLM Agent 比普通 heuristic 更有价值。

因此现在不是“继续证明底层能不能跑”，而是进入：

```text
先冻结公共接口
→ 做出第一条真人可玩纵向切片
→ 再用 A/B/C 判断 AI Agent 是否真的值得保留/升级
```

---

## 2. 审计后最重要的四条修正

### 修正 1：Agent Gate 降格

`live-agent-planner-match` 的正式证据级别调整为：

```text
connectivity evidence
```

它证明：

- provider 能调用；
- 两个 Agent 实例能工作；
- Planner 能产出动作；
- Controller / Engine 能完成终局。

它不证明：

- LLM 比 if/else 更聪明；
- LLM 对玩家有价值；
- 四个 StrategyIntent 是最终产品设计；
- 当前 Agent 架构应被永久冻结。

历史 Gate 结果和历史文档不删除、不篡改，只改变后续解释口径。

### 修正 2：先冻结 Contract，再并行

Developer A / B 真正开始独立开发前，必须统一使用：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

尤其不能各自定义：

- MatchSnapshot；
- ReplaySnapshot；
- Strategy public view；
- error code；
- rule submission result。

### 修正 3：四分类兼容，但不永久锁死

当前代码仍保持：

```text
PRESSURE
KITE
EVADE
HOLD
```

但公共 API 使用带 `plan_version` 的 `PublicStrategyDecision`，为 richer plan 预留可选字段。

这样 Sprint 1 如果升级 Agent，不需要把整个前端接口推倒重做。

### 修正 4：Replay 从“以后再做”提升为产品主合同

Replay 必须可以回答：

```text
玩家发了什么规则
→ 系统接受/拒绝了什么
→ 规则如何影响双方有效属性
→ RED/BLUE 分别选择了什么公开策略
→ Planner 最终做了什么动作
→ Engine 实际发生了什么
→ 状态如何变化
```

Replay 不能依赖再次调用 LLM。

---

# 3. Sprint 0 — 现在立刻做

目标：**让两个人可以安全并行，而不是开始堆功能。**

## S0-1 公共 Contract

状态：文档冻结源已建立。

产出：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

下一步实现：

- Pydantic schema；
- OpenAPI；
- generated/validated TypeScript types；
- schema-validated fixtures；
- contract tests。

## S0-2 Match Application Service 骨架

Developer A。

需要：

```text
create_match()
get_match_snapshot()
submit_public_rule()
advance_match()
get_replay()
```

必须有：

```text
per-match revision
per-match lock
Idempotency-Key
public/private projection
```

第一版 store：

```text
in-memory
```

不先上数据库。

## S0-3 Frontend Mock Shell

Developer B。

只基于冻结 contract + fixture 开发：

- 5×5 board；
- RED/BLUE、HP、Round；
- active rule；
- rule phase due；
- strategy public view；
- event feed；
- replay timeline；
- accepted/rejected/rephrase UI。

前端不计算游戏规则。

---

# 4. Sprint 1 — 第一条可玩闭环

目标：让一个不了解代码的人打开浏览器就能完成一局。

完整流程：

```text
创建对局
→ 提交 Phase 0 中文规则
→ 看规则被接受/拒绝
→ 推进回合
→ 看两个 AI 的公开策略
→ 看具体行动和结算
→ Round 3 后再次改规则
→ 打到终局
→ 看 Replay
```

这条流程没跑通前，不做复杂 UI、数据库、WebSocket 或新 DSL。

---

# 5. Sprint 1 同期必须做的 AI A/B/C

这是当前最重要的产品/竞赛实验。

比较三组：

### A — deterministic heuristic

完全不用 LLM 做策略。

### B — 当前四分类 LLM

```text
PRESSURE/KITE/EVADE/HOLD
```

### C — richer-plan LLM + deterministic short rollout

候选结构：

```text
mode
target_distance
weapon_preference
risk_budget
short_term_goal
horizon_rounds
contingency
```

Planner 仍然确定性执行合法动作。

需要比较：

- 规则改变后行为差异；
- 合法率；
- settlement invalid rate；
- 策略多样性；
- 胜率/utility；
- 延迟；
- 成本；
- 真人是否更容易看出“AI理解了规则”。

如果 C 对 A 没有明显优势：

> 不允许因为“这是 AI 比赛”就假装 LLM 必不可少。应考虑简化 Agent 或重新设计 AI 职责。

---

# 6. 目前不要做

现在明确推迟：

```text
OR / NOT / multi-effect DSL
WebSocket
Redis
Celery
Event Bus
微服务
复杂数据库
多人房间
账号/排行/商城
MCTS
多单位
地形
职业/技能
自由代码规则
移动 App
3D
```

原因不是这些功能永远没价值，而是它们现在不会解决最关键的问题。

---

# 7. 当前真正的三个风险

## 风险 1：AI 可能只是装饰

如果普通 heuristic 做得一样好，当前四分类 LLM 就没有足够说服力。

## 风险 2：玩家可能只会不断“拖时间”

如果目标只有延长战斗，规则可能快速收敛到减伤、降命中、拉远、冷却等套路。

Sprint 1 试玩应加入多个目标，而不是只看持续回合数。

## 风险 3：两个人提前并行会返工

如果 A/B 各自定义 API / Replay / Strategy 结构，几天后集成时会重写。

所以 Contract 是当前第一优先级。

---

# 8. 两周内最重要的成功标准

不是“做了多少页面、多少代码”。

而是：

1. 浏览器能完整玩一局；
2. 规则失败不会破坏对局；
3. 重复点击不会重复推进；
4. Replay 可稳定回看；
5. AI 策略公开信息可解释；
6. 同一 seed 的确定性部分可复现；
7. A/B/C 能回答 LLM 到底有没有价值；
8. Demo 网络失败时有 deterministic/offline fallback 或已保存 replay。

---

# 9. 当前执行顺序（唯一短版）

```text
现在：MVP API Contract V0.1
↓
Pydantic/OpenAPI + fixtures
↓
MatchApplicationService
↓
React Mock Shell（可与上一步并行）
↓
FastAPI 五个接口
↓
前后端真实接通
↓
Replay
↓
A/B/C Agent 实验
↓
真人试玩
↓
再决定 Agent 重构和玩法调整
```

如果新任务不属于这条链，默认先问：它是否真的比当前 P0 更重要？
