# M1 Integrated Playable Acceptance — 2026-09-10 首轮记录

状态：**IN PROGRESS / GATE 1 NOT PASSED**  
跟踪 Issue：[#64](https://github.com/Niceskys/yyds/issues/64)  
基线：`main@19505a70e10f640e31f34465c48b0651b2d5e7b7`

## 1. 本轮结论

本轮确认当前 V0.2 工程纵向切片能够通过真实 HTTP 完成一局，并且主要异常语义符合冻结 Contract；没有发现需要修复的产品代码问题。

但本轮没有取得：

1. 可见浏览器点击/截图证据；
2. 真实 MiMo/GLM Provider 的整局证据。

因此：

```text
TECHNICAL_HTTP_SLICE = PASS
REAL_BROWSER_VISIBLE_FLOW = BLOCKED_BY_EXECUTION_ENVIRONMENT
LIVE_PROVIDER_FLOW = NOT_RUN_NO_CREDENTIAL
GATE_1 = NOT_PASSED
DEVELOPER_A_GATE = PAUSED_BY_OWNER
B5A_ISSUE_63 = BLOCKED
```

确定性 Provider 结果不能描述成“真实模型已通过”，HTTP client / jsdom 结果也不能描述成“真实可见浏览器已通过”。

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

## 7. 阻塞项

### 可见浏览器

FastAPI 与 Vite 均能在执行容器启动，但 ChatGPT Cloud Browser 访问容器本地地址时返回：

```text
net::ERR_BLOCKED_BY_CLIENT
```

因此本轮无法在同一环境完成真实点击与截图。

### Live Provider

当前执行环境没有 `MIMO_API_KEY` 或 `ZHIPU_API_KEY`。仓库 Secret 不得读取或输出，生产 runtime 当前又要求 `MIMO_API_KEY`，所以未运行 live Provider 整局。

## 8. 下一步与 Gate

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
