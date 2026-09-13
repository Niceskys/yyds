# M1 Integrated Playable Acceptance — 2026-09-10 首轮记录

状态：**COMPLETE / GATE 1 PASSED（2026-09-11 Shared Review）**
跟踪 Issue：[#64](https://github.com/Niceskys/yyds/issues/64)  
最终验收基线：`main@42a66d538c13f0a9f46b0af1322e2baac703209c`

> 第 2–8 节保留 2026-09-10 首轮部分验收记录；第 9 节记录 2026-09-11 在 Windows 本地浏览器与 live MiMo 上补齐 Gate 的最终证据。

## 1. 本轮结论

首轮确认当前 V0.2 工程纵向切片能够通过真实 HTTP 完成一局，并且主要异常语义符合冻结 Contract。

但本轮没有取得：

1. 可见浏览器点击/截图证据；
2. 真实 MiMo/GLM Provider 的整局证据。

首轮结论为：

```text
TECHNICAL_HTTP_SLICE = PASS
REAL_BROWSER_VISIBLE_FLOW = BLOCKED_BY_EXECUTION_ENVIRONMENT
LIVE_PROVIDER_FLOW = NOT_RUN_NO_CREDENTIAL
GATE_1 = NOT_PASSED
DEVELOPER_A_GATE = PAUSED_BY_OWNER
B5A_ISSUE_63 = BLOCKED
```

确定性 Provider 结果不能描述成“真实模型已通过”，HTTP client / jsdom 结果也不能描述成“真实可见浏览器已通过”。

2026-09-11 已在真实 Chromium + live MiMo 环境补齐上述两项，并修复真实浏览器暴露的 native fetch receiver 缺陷（PR #65）。最终结论见第 9 节。

## 2. 环境与基线

```text
date = 2026-09-10
python = 3.12.14
node = 24.19.0
npm = 11.9.0
seed = 1270000
```

本地工作区在验收前后均无产品源码修改。临时启动器、确定性 Provider 和 smoke client 均位于仓库外，不进入提交。

## 3. 静态与自动化门槛

```text
python -m pytest              PASS — 308 tests
npm run contract:check        PASS
npm run typecheck             PASS
npm run test                  PASS — 7 files / 45 tests
npm run build                 PASS — Vite 5.4.21 / 48 modules
```

Python 测试有 2 条 FastAPI/Starlette TestClient 的第三方弃用警告；不影响本轮功能结论，暂不进行无关依赖升级。

## 4. 真实 HTTP 纵向闭环

运行链：

```text
HTTP client
→ Vite dev server /api proxy
→ FastAPI V0.2 five routes
→ InMemoryMatchRepository
→ MatchApplicationService
→ DynamicRuleController
→ isolated strategy agents
→ deterministic planner
→ Engine
→ authoritative MatchSnapshot / ReplaySnapshot
```

除 Provider transport 使用仓库外临时确定性双桩外，其余均走正式生产应用路径。

结果：

```text
completed_rounds = 4
score_rounds = 4
terminal_result = RED_WIN
replay_entries = 9
```

已验证：

- 初始状态 revision=0、completed_rounds=0、active_rule=null；
- Round 1 前规则不可提交；
- Round 1 后进入 PLAYER_DECISION；
- 同一 Idempotency-Key 重试返回相同 advance 结果；
- stale revision 返回 409，GET 可取得权威最新状态；
- rejected 规则不增加 revision，仍可重试；
- accepted 规则增加 revision / rule_change_count，但不自动 advance；
- 可持续推进至 terminal；
- terminal 后 mutation 被拒绝；
- Replay 的 result / score / rule count 与 Match 一致；
- Replay 同时包含 ROUND 与 INTERMISSION；
- public Replay 不包含 private memory、raw model output、system prompt、API key、chain-of-thought 或 traceback。

## 5. Provider 异常语义

通过真实 HTTP 单独验证：

```text
strategy provider failure
→ HTTP 200
→ round 正常完成
→ FALLBACK_MODEL_ERROR
→ degraded=true
→ raw private error 不泄漏
PASS

rule provider failure
→ HTTP 200
→ MODEL_UNAVAILABLE
→ accepted=false
→ revision 不增加
→ rule_change_count 不增加
→ 同一 intermission 仍可再次提交
→ raw private error 不泄漏
PASS
```

## 6. 前端回归证据

现有 45 个 Vitest 测试覆盖：

- 初始页与开始游戏；
- Round 1 前规则输入禁用；
- accepted 后不自动推进；
- 503 不推进本地 snapshot，未知结果重试复用 key；
- 409 GET resync 且不自动重放；
- strategy fallback 中文非阻断提示；
- MODEL_UNAVAILABLE 可重试；
- loading 状态防止重复 mutation；
- Replay 通过 adapter 获取，不从当前 UI state 反推。

这些属于组件/应用回归证据，不替代真实可见浏览器验收。

## 7. 首轮阻塞项（2026-09-11 已解除）

### 可见浏览器

FastAPI 与 Vite 均能在执行容器启动，但 ChatGPT Cloud Browser 访问容器本地地址时返回：

```text
net::ERR_BLOCKED_BY_CLIENT
```

因此本轮无法在同一环境完成真实点击与截图。

### Live Provider

当前执行环境没有 `MIMO_API_KEY` 或 `ZHIPU_API_KEY`。仓库 Secret 不得读取或输出，生产 runtime 当前又要求 `MIMO_API_KEY`，所以未运行 live Provider 整局。

## 8. 首轮下一步与 Gate（历史状态）

M1 关闭前仍需：

1. 在可访问的临时部署或本地浏览器完成可见整局；
2. 使用安全注入的真实 Provider Secret 至少完成一局；
3. 记录 provider、model、seed、回合数、fallback 和 Replay；
4. 复核错误与 Replay 无隐私/secret 泄漏；
5. hosted CI 保持全绿；
6. 在 Issue #64 留最终 smoke 记录。

在此之前：

```text
GATE 1 = NOT PASSED
Developer A = PAUSED_BY_OWNER
Issue #63 / B5A = BLOCKED_BY_M1_GATE
```

## 9. 2026-09-11 最终真实浏览器 + live MiMo 验收

环境与最终基线：

```text
main = 42a66d538c13f0a9f46b0af1322e2baac703209c
OS = Windows
Python = 3.14.5
Node = 24.16.0
npm = 11.13.0
provider = MiMo China Token Plan
model = mimo-v2.5-pro
create seed = null（runtime-selected）
```

真实运行链：

```text
Chromium browser
→ Vite /api proxy
→ FastAPI V0.2
→ InMemoryMatchRepository
→ MatchApplicationService
→ live MiMo rule / strategy providers
→ deterministic planner / Engine
→ authoritative Replay GET
```

真实 HTTP 与可见 UI 结果：

```text
POST /api/v1/matches                              201
POST /api/v1/matches/{id}/advance                 200 x5
POST /api/v1/matches/{id}/rules (rejected)        200
POST /api/v1/matches/{id}/rules (accepted)        200
GET  /api/v1/matches/{id}/replay                  200

completed_rounds = 5
score_rounds = 5
terminal_result = DRAW / both eliminated
rule_change_count = 1
replay_entries = 11
```

逐项确认：

- 初始 revision=0、completed_rounds=0，Round 1 前规则输入禁用；
- live MiMo Round 1 正常完成并进入 `PLAYER_DECISION`；
- `让红方直接获胜` 被安全拒绝，revision 保持 1，可继续改写；
- `双方移动距离增加1格。` 被接受，revision=2、rule_change_count=1，双方移动距离从 1 变为 2；
- accepted 后没有自动 advance；
- 继续至第 5 回合终局，双方生命值均为 0，submit / advance 均禁用；
- Replay 真实 GET，11 个 ROUND / INTERMISSION 节点与终局、成绩、规则次数一致；
- 普通 UI 未出现 API key、raw provider body、stack、private memory、system prompt 或 chain-of-thought；
- hosted frontend / Python CI 在 PR #65 与 merge main 上均通过。

真实浏览器同时暴露 PR #65 修复项：原实现把 native `fetch` 作为 `this.fetchImpl(...)` 调用，Chromium 在请求发出前因错误 receiver 失败。修复后真实浏览器闭环通过，并增加 receiver regression；前端测试由 45 增至 46。

剩余 `RULE_MODIFIER_APPLIED` 玩家文案走安全 unknown-event fallback，不泄漏私有数据、不影响权威状态或完整游玩。它作为 B5A 表现层改进项处理，不构成 M1 integrity blocker。

最终 Shared Review：

```text
TECHNICAL_HTTP_SLICE = PASS
REAL_BROWSER_VISIBLE_FLOW = PASS
LIVE_PROVIDER_FLOW = PASS
ERROR_AND_PRIVACY_SEMANTICS = PASS
HOSTED_CI = PASS
GATE_1 = PASSED
M1_STATUS = COMPLETE
DEVELOPER_A_GATE = PAUSED_BY_OWNER
B5A_ISSUE_63 = READY_FOR_DEVELOPER_B
```
