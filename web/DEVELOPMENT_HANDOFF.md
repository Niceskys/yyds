# Developer B Handoff

## 当前基线 / 状态

- B4 integration baseline: `main@cfd143098571513bcadc54e0f3eb382cde421e5c`
- A3 merge: `b79b1da08a3ff5801b286b5f970f7e371fd85a08`（PR #59）
- B4 branch: `frontend/real-api-v02`
- B4 Issue: #60
- B4 PR: #61 `feat(frontend): B4 integrate real V0.2 HTTP API`
- B4 code HEAD before this handoff: `38b034a9f65c6a2e9da31607e4acc1ebfe067c9c`
- current Developer B state: **B4 IMPLEMENTED — PR review**
- contract version: `mvp-v0.2`

已完成：

```text
B0 App Shell                     DONE — PR #43
B1 fixture-driven UI             DONE — PR #43
B3 selectable Replay             DONE — PR #47
frontend CI                      DONE — PR #44
npm audit attribution/min patch  DONE — PR #54 / Issue #45
checked-in OpenAPI snapshot       DONE — PR #57 / Issue #56
generated TS + API seam          DONE — PR #58 / Issue #55
B4 real HTTP integration         IMPLEMENTED — PR #61 review
```

## 公共契约权威链

```text
src/rules_beyond/api_contract.py
        ↓
src/rules_beyond/openapi_contract.py
        ↓
contracts/openapi/mvp-v0.2.json
        ↓ openapi-typescript 7.13.0
web/src/contract/generated/api.ts
        ↓
web/src/contract/types.ts
        ↓
MatchApiAdapter
        ↓
HttpMatchApiAdapter / presentation adapters
        ↓
React
```

不要手写第二套 DTO。`contract:check` 仍是 generated TS drift gate。

## B4 正式运行路径

生产 App 已从 mock/scenario 驱动切为：

```text
FastAPI V0.2
→ HttpMatchApiAdapter
→ generated DTO aliases
→ existing ViewModel builders
→ React
```

`App.tsx` 正式运行路径不再 import：

```text
MockScenarioBar
mock/scenarios
fixture loaders
advance_round.json
rule_accepted.json
rule_rejected.json
match_terminal.json
```

这些 mock/fixture 资产仍保留用于 contract / ViewModel regression tests，不是 runtime state source。

## 五个真实 HTTP 操作

`web/src/contract/httpApiAdapter.ts` 实现 #55 冻结的 `MatchApiAdapter`：

```text
createMatch(seed?)
  POST /api/v1/matches

getMatch(matchId)
  GET /api/v1/matches/{match_id}

submitRule({ matchId, expectedRevision, idempotencyKey, playerText })
  POST /api/v1/matches/{match_id}/rules
  Header: Idempotency-Key

advanceMatch({ matchId, expectedRevision, idempotencyKey })
  POST /api/v1/matches/{match_id}/advance
  Header: Idempotency-Key

getReplay(matchId)
  GET /api/v1/matches/{match_id}/replay
```

transport 只做 HTTP 翻译和安全响应边界，不计算 gameplay。

成功响应至少检查：

```text
JSON object
schema_version = mvp-v0.2
```

这只是版本 sanity check，不是前端再维护一份 schema。

## 正式游玩流程

当前 App authoritative flow：

```text
开始游戏
→ createMatch
→ RUNNING / revision 0 / completed_rounds 0
→ 第 1 回合前规则输入禁用
→ 用户点击“继续下一回合”
→ advanceMatch
→ Round 1 完整完成
→ PLAYER_DECISION
→ rejected / MODEL_UNAVAILABLE 可再次提交
→ accepted 后规则输入由服务端 decision 锁定，但不自动 advance
→ 用户再次 Continue
→ 下一完整 Round
→ ...
→ TERMINAL
```

前端不自行执行/推导：

```text
Engine legality
命中率
rule validation
有效属性
ebattle escalation
terminal result
revision + 1
```

## Revision / Idempotency-Key

权威 revision 永远取当前服务端 DTO。

规则：

```text
新的用户 mutation 意图
→ 新 Idempotency-Key

同一次 mutation 因网络错误 / 503 / 结果未知重试
→ 保留原 snapshot
→ 复用同一个 Idempotency-Key

HTTP 200 正常业务结果（含 MODEL_UNAVAILABLE）
→ 本次 mutation 已确定完成
→ 清除旧 key
→ 再次提交属于新意图，用新 key

409 REVISION_CONFLICT
→ 不重放旧 mutation
→ 清除旧 key
→ GET 最新 MatchSnapshot
→ UI 重新同步 authoritative state
```

mutation pending 时规则提交和 advance 同时禁用，避免同一 revision 上并发生成多个不同 key。

## Provider failure 的最终前端语义

### Strategy provider/model failure

A3 authoritative：

```text
HTTP 200 AdvanceResult
round 正常提交
PublicStrategyDecision.status = FALLBACK_MODEL_ERROR 或其他 public fallback status
degraded = true
```

B4：

- 不显示 HTTP error；
- round / actions / events 正常展示；
- RulePanel 显示非阻断提示“已使用降级策略继续完成对局”；
- TeamPanel 在 `degraded=true` 时显示中文 public `statusLabel`，例如“模型不可用，已回退”；
- 不显示 raw enum / provider exception。

### Rule provider/model failure

A3 authoritative：

```text
HTTP 200 RuleSubmissionResult
accepted = false
public_code = MODEL_UNAVAILABLE
revision 不增加
rule_change_count 不增加
can_submit_rule = true
```

B4：

- 作为正常业务反馈展示；
- 显示“规则模型暂时不可用”；
- 规则输入保持可提交；
- 不当作 503；
- 下一次重新提交生成新 Idempotency-Key，避免 A2 replay 旧 MODEL_UNAVAILABLE 结果。

### 真正 RecoverableMatchFailure

```text
HTTP 503
INTERNAL_ERROR
retryable = true
```

B4：

- 显示本地固定安全中文：“本回合未安全完成，请稍后重试。”；
- 不用 response 推测 mutation 是否完成；
- 保留原 authoritative snapshot；
- 同一次用户动作 retry 复用同 key。

## ErrorEnvelope / privacy

`HttpMatchApiAdapter` 集中解析 transport / ErrorEnvelope；React 不散落 HTTP status 判断。

本地安全文案覆盖：

```text
MATCH_NOT_FOUND
REVISION_CONFLICT
IDEMPOTENCY_KEY_REQUIRED
INVALID_REQUEST
MATCH_TERMINAL
RULE_SUBMISSION_NOT_ALLOWED
ADVANCE_NOT_ALLOWED
INTERNAL_ERROR
NETWORK_ERROR
INVALID_RESPONSE
```

server `error.message` 不直接用于玩家展示；未知/非规范 response 也只显示固定安全文案。

普通 UI 继续不得出现：

```text
private_memory
raw_model_output
system_prompt
provider raw body
API key
stack / traceback
conflict_level
hard_liveness
hard_liveness_active
```

## Replay

正式 Replay：

```text
GET /api/v1/matches/{match_id}/replay
→ ReplaySnapshot
→ existing Replay Adapter
→ Replay ViewModel
→ Replay UI
```

不从当前 React state 反推 replay，不重新模拟 Engine/events，不调用模型。

## 本地开发连接

Backend：

```bash
python -m rules_beyond.api_server --host 127.0.0.1 --port 8000
```

Frontend dev server 默认：

```text
/api/*
→ Vite proxy
→ http://127.0.0.1:8000
```

可通过：

```text
VITE_BACKEND_PROXY_TARGET
```

覆盖 dev proxy target。

browser/runtime API base：

```text
VITE_API_BASE_URL
```

未配置时使用 same-origin。Production code 不硬编码 `127.0.0.1:8000`。

没有为 B4 擅自新增 `CORS *`。

## B4 测试 / CI

新增/更新 frontend regression：

```text
App real flow
- create only：不自动跑 Round 1
- first advance → Round 1 / PLAYER_DECISION
- accepted rule 不 auto-advance
- 503 保留 snapshot + same-key retry
- 409 resync，不 auto replay old mutation
- degraded strategy 是 200 正常 round
- MODEL_UNAVAILABLE 是 200 business result
- duplicate mutation loading guard
- Replay 真实调用 getReplay

HttpMatchApiAdapter
- 五路由 URL/method/body/header
- snake_case request body
- Idempotency-Key
- ErrorEnvelope safe parsing
- malformed 5xx 不泄露 raw body
- network unknown result retryable
- malformed successful payload rejected

Component regressions
- fixture 只作为 UI/ViewModel test input
- terminal mutation disabled
- unknown event fallback
- privacy whitelist
```

PR #61 code HEAD `38b034a9...` 正式 hosted CI：

```text
npm ci                  PASS
npm run contract:check  PASS
npm run typecheck       PASS
npm run test            PASS — 7 files / 45 tests
npm run build           PASS — Vite 5.4.21 / 48 modules
Python tests            PASS
```

production bundle at that HEAD：

```text
JS  173.64 kB / gzip 56.58 kB
CSS   8.90 kB / gzip  2.52 kB
```

当前 npm audit 仍为 Issue #45 已记录并接受的 dev-tooling 状态：

```text
5 package nodes
3 moderate
1 high
1 critical
```

B4 未修改依赖，也没有运行 `npm audit fix --force`。

## Mock 收口状态

正式 runtime 已脱离 mock/scenario，但以下测试资产暂时保留：

```text
contracts/fixtures/mvp-v0.2/**
web/src/mock/**
MockScenarioBar component
```

原因：它们仍服务 fixture / presentation regression。由于 production App 不 import，它们不会驱动正式游玩，也会被正常 tree-shaking 排除。

后续若做代码清理，可以单独删除无调用的 dev-only MockScenarioBar/scenario UI；不要为了“清理”删除 canonical shared fixtures。

## Developer A 当前状态

根目录 `DEVELOPER_A_GATE.md`：

```text
DEVELOPER_A_GATE = PAUSED_BY_OWNER
LAST_COMPLETED_TASK = A3 FastAPI V0.2 five-route vertical slice
DO_NOT_START = true
```

A0/A1/A2/A3 全部 DONE。Developer A 不应开始旧 Day 4/Day 5 或任何新后端任务，直到项目负责人批准新的 Issue。

## Remaining / merge gate

PR #61 在 merge 前只剩：

1. 本 handoff commit 的 hosted CI 继续全绿；
2. Shared Review 确认最终 diff 仅 frontend scope；
3. PR 标记 Ready；
4. merge #61；
5. Issue #60 完成；
6. 若无其他 B blocker，Issue #38 可作为 Developer B V0.2 主任务关闭。

没有 `CONTRACT CHANGE REQUIRED`。

## 下一位 Developer B 必须先读

1. `DEVELOPER_A_GATE.md`
2. Issue #60 / PR #61
3. PR #59 / A3 handoff
4. `docs/GAMEPLAY_FLOW_V0.2.md`
5. `docs/MVP_API_CONTRACT_V0.2.md`
6. `contracts/README.md`
7. `contracts/openapi/mvp-v0.2.json`
8. `web/DEVELOPMENT_HANDOFF.md`
9. `web/NPM_AUDIT_2026-09-09.md`
10. 最近 5–10 个 main commits
