# Developer B Handoff

## 当前基线 / 状态

- B4 merge baseline: `main@8769649cf587862b72f241fc64b531e5fdbbdbe6`
- A3 merge: `b79b1da08a3ff5801b286b5f970f7e371fd85a08`（PR #59）
- B4 Issue: #60 — **DONE**
- B4 PR: #61 `feat(frontend): B4 integrate real V0.2 HTTP API` — **MERGED**
- B4 reviewed code HEAD: `3473bbbea6c0578e942197871ed2894e6fc39654`
- B4 merge commit: `8769649cf587862b72f241fc64b531e5fdbbdbe6`
- current Developer B state: **V0.2 FRONTEND DONE**
- M1 browser/live-provider acceptance: **PASSED** — Issue #64 / PR #65
- B5A status: **COMPLETE / UI PRESENTATION GATE PASSED** — Issue #63 / PR #71
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
B4 real HTTP integration         DONE — PR #61 / Issue #60
B5A.1 round causal transition    DONE — current increment / Issue #63
B5A.2 rule causal feedback       DONE — current increment / Issue #63
B5A.3 escalation change feedback DONE — PR #69 / Issue #63
B5A.4 Replay transition           DONE — PR #71 / Issue #63
```

Developer B V0.2 主任务与 B5A 均已完成；M1 GATE 1、B5A UI PRESENTATION GATE 已通过。下一项实现工作必须来自 M2/M3 证据并建立新的 Issue。

B5A.1 已增加约 1 秒的回合因果过渡：只比较 advance 前后两份公开 authoritative snapshot，展示红蓝公开行动、坐标与生命变化；演出期间继续锁住 mutation，`prefers-reduced-motion` 下直接落到权威结果。

B5A.2 已把 accepted / rejected / MODEL_UNAVAILABLE 分为成功、拒绝、暂时不可用三种克制反馈；accepted 使用提交前后 authoritative snapshot 精确列出公开属性变化，且明确不会自动推进。`RULE_MODIFIER_APPLIED` 现使用公开 modifier payload 生成安全中文文案。

B5A.3 已把战局升温变化接入回合因果过渡：只比较 advance 前后公开 authoritative escalation 的等级与连续无伤害回合，等级或进度变化时显示短暂的橙色边缘脉冲和可读变化行，并在 reduced-motion 下关闭脉冲。修正了 escalation 组件 class 与既有样式选择器不一致的问题；不新增或修改 public contract。

B5A.4 已完成 Replay 时间线过渡：只切换 ReplaySnapshot 产生的现有节点，显示前一节点到当前节点的关系；快速连续选择同步落到最后选中的 authoritative 节点，`prefers-reduced-motion` 下关闭动画。最终验收见 `docs/experiments/B5A_CORE_CAUSAL_FEEDBACK_ACCEPTANCE_2026-09-12.md`。

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

## 正式运行路径

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

这些 mock / fixture 资产仍保留用于 contract / ViewModel regression tests，不是 runtime state source。

## 五个真实 HTTP 操作

`web/src/contract/httpApiAdapter.ts` 实现冻结的 `MatchApiAdapter`：

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

transport 只负责 HTTP 翻译和安全响应边界，不计算 gameplay。成功响应至少要求是 JSON object 且 `schema_version = mvp-v0.2`；这是版本 sanity check，不是前端维护第二套 schema。

## 正式游玩流程

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

前端不得自行执行或推导：

```text
Engine legality
命中率
rule validation
有效属性
battle escalation
terminal result
revision + 1
```

## Revision / Idempotency-Key

权威 revision 永远取当前服务端 DTO。

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
→ 清空旧 lastRound / rule feedback presentation state
→ UI 重新同步 authoritative state
```

mutation pending 时规则提交和 advance 同时禁用，避免同一 revision 上并发生成多个不同 key。

## Provider failure 的前端语义

### Strategy provider/model failure

```text
HTTP 200 AdvanceResult
round 正常提交
PublicStrategyDecision.status = public fallback status
degraded = true
```

前端：

- 不显示 HTTP error；
- round / actions / events 正常展示；
- 显示非阻断中文降级提示；
- TeamPanel 可显示中文 public `statusLabel`；
- 不显示 raw enum / provider exception。

### Rule provider/model failure

```text
HTTP 200 RuleSubmissionResult
accepted = false
public_code = MODEL_UNAVAILABLE
revision 不增加
rule_change_count 不增加
can_submit_rule = true
```

前端把它当正常业务反馈；规则输入保持可提交；下一次重新提交生成新 Idempotency-Key。

### RecoverableMatchFailure

```text
HTTP 503
INTERNAL_ERROR
retryable = true
```

前端保留原 authoritative snapshot；显示固定安全中文；同一次用户动作 retry 复用同 key。

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

server `error.message` 不直接作为玩家文案。普通 UI 不得出现：

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
→ Replay Adapter
→ Replay ViewModel
→ Replay UI
```

不从当前 React state 反推 Replay，不重新模拟 Engine / events，不调用模型。

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

配置：

```text
VITE_BACKEND_PROXY_TARGET  # dev proxy target
VITE_API_BASE_URL          # browser/runtime API base
```

`VITE_API_BASE_URL` 未配置时使用 same-origin。Production code 不硬编码 `127.0.0.1:8000`，B4 没有新增 `CORS *`。

## 最终 B4 验证

最终 reviewed HEAD `3473bbbea6c0578e942197871ed2894e6fc39654` 在 merge 前反复通过 hosted CI：

```text
npm ci                  PASS
npm run contract:check  PASS
npm run typecheck       PASS
npm run test            PASS — 7 files / 45 tests
npm run build           PASS — Vite 5.4.21 / 48 modules
Python tests            PASS
```

PR #61 最终 diff 仅 `web/**`；没有修改 backend、`api_contract.py`、OpenAPI snapshot、generated TS、Engine、CORS 或 canonical fixtures。没有 `CONTRACT CHANGE REQUIRED`。

当前 npm audit 仍为 Issue #45 已记录并接受的 dev-tooling 风险状态；不要使用 `npm audit fix --force` 做无关大版本升级。

## Mock / regression 资产

正式 runtime 已脱离 mock/scenario，但以下测试资产暂时保留：

```text
contracts/fixtures/mvp-v0.2/**
web/src/mock/**
MockScenarioBar component
```

它们仅服务 fixture / presentation regression，不驱动正式 App。后续若清理无调用的 dev-only mock UI，应单独开 Issue；不要删除 canonical shared fixtures。

## Developer A 当前状态

根目录 `DEVELOPER_A_GATE.md` 仍是新的后端工作执行门。A0/A1/A2/A3 已完成；不要仅凭旧 Issue / chat / handoff 文案重启旧 Developer A 任务。任何新后端工作必须先读取当前 gate 并获得明确的新任务授权。

## 后续工作规则

B0–B4、M1 与 B5A 已完成。当前先冻结 M2 Agent A/B/C 实验设计：

1. 先固定比较组、场景、seed、指标、样本量、失败统计和 Gate 2 判定规则；
2. 未创建新的 Developer A Issue 并更新 `DEVELOPER_A_GATE.md` 前，不实现实验 harness 或 richer-plan Agent；
3. 若修改 public contract，先声明 `CONTRACT CHANGE REQUIRED`，不要在前端私自补字段；
4. 保持 `contract:check` / typecheck / tests / production build 全绿；
5. 不把代码清理、安全依赖升级和新产品功能混进实验任务。

## 下一位 Developer B 必须先读

1. `DEVELOPER_A_GATE.md`
2. `web/DEVELOPMENT_HANDOFF.md`
3. `docs/GAMEPLAY_FLOW_V0.2.md`
4. `docs/MVP_API_CONTRACT_V0.2.md`
5. `contracts/README.md`
6. `contracts/openapi/mvp-v0.2.json`
7. `web/NPM_AUDIT_2026-09-09.md`
8. Issue #63 / #64 与 PR #65 的放行和验收上下文
9. 最近 5–10 个 main commits
