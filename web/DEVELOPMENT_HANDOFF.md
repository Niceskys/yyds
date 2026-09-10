# Developer B Handoff

## 当前基线

- integration baseline: `main@78b63ed704890ea3cd664c552784eada1e6ff409`
- working branch: `frontend/openapi-types-prep-v02`
- current task: Issue #55 — B4 前置：OpenAPI generated TypeScript types + transport-neutral API Adapter 边界
- contract version: `mvp-v0.2`
- B0 App Shell: DONE（PR #43）
- B1 fixture UI: DONE（PR #43）
- B3 selectable Replay: DONE（PR #47）
- Issue #45 npm audit: DONE（PR #54，merge `6818dd58bdbe15b48e08fbb0320365a1c178edb9`）
- Shared OpenAPI snapshot: DONE（Issue #56 / PR #57，merge `78b63ed704890ea3cd664c552784eada1e6ff409`）
- B4 real HTTP integration: **BLOCKED**；Developer A A3 仍由 `DEVELOPER_A_GATE.md` 标记 `PAUSED_BY_OWNER`

## Issue #55：B4 前置实现

### 1. OpenAPI 派生链

公共契约权威链现在固定为：

```text
src/rules_beyond/api_contract.py              # canonical Pydantic source
        ↓
src/rules_beyond/openapi_contract.py          # canonical OpenAPI generator
        ↓
contracts/openapi/mvp-v0.2.json               # checked-in derived snapshot
        ↓ openapi-typescript 7.13.0
web/src/contract/generated/api.ts              # generated TypeScript, DO NOT EDIT
        ↓
web/src/contract/types.ts                      # thin aliases only
        ↓
Adapter / ViewModel / React
```

Shared PR #57 已加入 `tests/test_openapi_snapshot.py`，保证 checked-in OpenAPI JSON 必须结构等于 `contract_app.openapi()`；它不是第二 canonical source。

### 2. TypeScript generator

精确锁定：

```text
openapi-typescript = 7.13.0
```

`web/package.json`：

```text
npm run contract:generate
npm run contract:check
```

其中：

```text
contract:generate
→ openapi-typescript ../contracts/openapi/mvp-v0.2.json -o src/contract/generated/api.ts

contract:check
→ 重新生成
→ git diff --exit-code -- src/contract/generated/api.ts
```

Node 20 GitHub runner 已实际生成成功；一次性 bootstrap workflow 已删除，不会进入最终 PR。

### 3. 手写 contract 已收缩

`web/src/contract/types.ts` 不再人工声明完整：

```text
MatchSnapshot
AdvanceResult
RuleSubmissionResult
ReplaySnapshot
ErrorEnvelope
以及其公共嵌套 DTO
```

现在这些类型全部是：

```ts
components['schemas'][...]
```

的薄 alias。

由于 OpenAPI 对带默认值/nullable 字段可能生成 optional property，presentation adapter 只在 ViewModel 边界做安全归一化，例如：

```text
cooldown_weapons ?? []
move_path ?? []
after_round ?? null
suggested_rephrase ?? null
event.details ?? {}
Replay optional nullable fields ?? null
```

这不是重新定义 API schema，也不改变游戏语义。

### 4. API Adapter seam

新增：

```text
web/src/contract/apiAdapter.ts
```

transport-neutral `MatchApiAdapter` 包含冻结五个操作：

```text
createMatch(seed?)
getMatch(matchId)
submitRule({ matchId, expectedRevision, idempotencyKey, playerText })
advanceMatch({ matchId, expectedRevision, idempotencyKey })
getReplay(matchId)
```

mutation command 的 `expectedRevision` 直接引用 generated request schema；`idempotencyKey` 明确存在于 transport command。

**当前没有实现 fetch、base URL、CORS、HTTP status → UX 映射，也没有真实请求。**

### 5. Mock / Replay 兼容

现有链仍保持：

```text
checked-in fixtures
→ mock/fixture adapter
→ presentation ViewModel
→ React
```

没有删除：

```text
MockScenarioBar
mock/scenarios.ts
fixtures
```

也没有让前端模拟 Engine、规则合法性、命中率、有效属性、战局升温或胜负。

### 6. CI drift gate

`.github/workflows/frontend.yml` 现在：

- `contracts/openapi/mvp-v0.2.json` 变动也会触发 frontend CI；
- `npm ci` 后先执行 `npm run contract:check`；
- 然后才执行 typecheck / tests / production build。

因此后端同步 OpenAPI snapshot 后如果忘记更新 `generated/api.ts`，前端 CI 会失败。

### 7. 测试

新增：

```text
web/src/__tests__/generatedContract.test.ts
```

覆盖：

1. canonical fixture 可通过 generated `MatchSnapshot / AdvanceResult / RuleSubmissionResult / ReplaySnapshot` alias；
2. adapter seam 五个操作可实现；
3. rule mutation command 明确携带 `expectedRevision + idempotencyKey + playerText`；
4. advance mutation command 明确携带 `expectedRevision + idempotencyKey`。

现有 privacy / Replay / fixture tests 保持，不放松断言。

最终正式 CI 测试数以 Issue #55 PR 的 GitHub Actions 为准。

## npm dependency audit 状态

Issue #45 已使用最小 patch 完成：

```text
vite   5.4.11 → 5.4.21
vitest 2.1.8  → 2.1.9
```

完整记录：`web/NPM_AUDIT_2026-09-09.md`。

Issue #55 加入 `openapi-typescript@7.13.0` 后，Node 20 runner 的真实 `npm audit --json` 仍为：

```text
5 package nodes
3 moderate
1 high
1 critical
```

与 #45 合并后的已知状态一致；没有新增 high / critical。剩余均为已记录的 Vite/Vitest dev/build/test-only major-upgrade 风险。

不得执行 `npm audit fix --force`。

## 当前已完成能力

- React/Vite 应用外壳与中文游玩 UI；
- fixture → adapter → ViewModel → React 单向数据流；
- Round 1 无 pre-game rule；
- accepted/rejected/terminal 状态；
- 5×5 board / HP / strategy / action / rule / rule count / 战局升温；
- selectable Replay timeline；
- privacy whitelist；
- 正式 frontend CI；
- npm audit 最小 patch + residual-risk record；
- checked-in OpenAPI derived snapshot + Python parity gate；
- OpenAPI generated TS contract；
- transport-neutral five-operation adapter seam。

## 当前 Mock 限制

- “继续下一回合”仍复用静态 `advance_round.json`，不会真的推进任意回合；这是有意限制，前端不得模拟 Engine。
- MockScenarioBar / scenarios 仍保留，直到真实 B4 完成。

## Developer A 当前状态

```text
A0 DynamicRuleController V0.2                 DONE
A1 MatchApplicationService                    DONE
A2 repository / revision / lock / idempotency DONE
A3 FastAPI five-route vertical slice          PAUSED_BY_OWNER
```

根目录：

```text
DEVELOPER_A_GATE.md
```

仍是 authoritative execution gate。

因此即使前端 generated contract / adapter seam 已准备好，**不得提前实现真实 HTTP adapter**。必须等：

```text
DEVELOPER_A_GATE = READY
A3 Issue #53 实现完成
A3 PR 经审核并 merge
```

之后才进入真正 B4。

## 后续仍未完成

1. Issue #55：等待正式 frontend CI / PR review / merge。
2. A3：仍暂停。
3. B4 real HTTP adapter：A3 merge 后实现 `fetch`、错误处理、真实 create/rule/advance/replay flow。
4. B4 完成后再删除临时 mock scenario machinery。
5. 前端工具链 major 升级（Vite ≥6.4.3 / Vitest ≥4.1.11）保持独立任务，不混入 B4。

## 下一位开发者必须先读

1. `DEVELOPER_A_GATE.md`
2. `docs/GAMEPLAY_FLOW_V0.2.md`
3. `docs/MVP_API_CONTRACT_V0.2.md`
4. `contracts/README.md`
5. `contracts/openapi/mvp-v0.2.json`
6. `web/DEVELOPMENT_HANDOFF.md`
7. `web/NPM_AUDIT_2026-09-09.md`
8. Issue #38、#53、#55、#56
9. 最近 5–10 个 main commits
