# Developer B Handoff

## 当前基线

- integration baseline: `main@34df26d0d5fbda010b2ffed59df556246b34c0e6`
- current Developer B state: **WAITING FOR A3 MERGE**
- contract version: `mvp-v0.2`
- B0 App Shell: DONE（PR #43）
- B1 fixture UI: DONE（PR #43）
- B3 selectable Replay: DONE（PR #47）
- Issue #45 npm audit: DONE（PR #54）
- Shared OpenAPI snapshot: DONE（Issue #56 / PR #57）
- B4-prep generated TS + API adapter seam: DONE（Issue #55 / PR #58，merge `d34fa5cf6e301c585f662fd964e998820827e0dc`）
- B4 real HTTP integration: **BLOCKED UNTIL A3 PR MERGES**

## 当前架构边界

公共契约权威链：

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

Mock 链继续保留：

```text
checked-in fixtures
→ mock/fixture adapter
→ presentation ViewModel
→ React
```

前端不得计算/推导：

```text
Engine legality
hit probability
battle escalation
terminal result
effective stats
rule validity
```

普通玩家 UI 继续隐藏：

```text
conflict_level
hard_liveness
hard_liveness_active
private_memory
raw_model_output
system_prompt
provider body
stack / traceback
```

## B4-prep（已合并）

### Generated contract

精确锁定：

```text
openapi-typescript = 7.13.0
```

脚本：

```text
npm run contract:generate
npm run contract:check
```

`contract:check` 会重新生成 `web/src/contract/generated/api.ts` 并用 `git diff --exit-code` 检查漂移。

`web/src/contract/types.ts` 已不再人工维护完整 `MatchSnapshot / AdvanceResult / RuleSubmissionResult / ReplaySnapshot / ErrorEnvelope`，只从 generated `components['schemas'][...]` 建薄 alias。

### API adapter seam

`web/src/contract/apiAdapter.ts` 定义 transport-neutral `MatchApiAdapter`：

```text
createMatch(seed?)
getMatch(matchId)
submitRule({ matchId, expectedRevision, idempotencyKey, playerText })
advanceMatch({ matchId, expectedRevision, idempotencyKey })
getReplay(matchId)
```

当前仍**没有**真实 `fetch` / base URL / CORS / HTTP error UX；这些属于 A3 merge 后的 B4。

### CI

`.github/workflows/frontend.yml`：

```text
npm ci
→ npm run contract:check
→ typecheck
→ tests
→ production build
```

`contracts/openapi/mvp-v0.2.json` 变化也会触发 frontend CI。

PR #58 最终正式 CI：

```text
contract:check PASS
typecheck PASS
6 test files / 33 tests PASS
production build PASS
Python tests PASS
```

## npm audit 状态

Issue #45 已做最小 patch：

```text
vite   5.4.11 → 5.4.21
vitest 2.1.8  → 2.1.9
```

加入 `openapi-typescript@7.13.0` 后，runner 实际状态仍是：

```text
5 package nodes
3 moderate
1 high
1 critical
```

没有新增 high / critical。完整风险记录见 `web/NPM_AUDIT_2026-09-09.md`。不得执行 `npm audit fix --force`。

## 当前 UI / Mock 能力

- 初始页《规则之外》+ 开始游戏；
- Round 1 无 pre-game rule；
- 5×5 board / HP / public strategy / action / rule / rule count / 战局升温；
- accepted / rejected / terminal 状态；
- selectable Replay timeline；
- fixture → adapter → ViewModel → React；
- privacy whitelist；
- `MockScenarioBar` / `mock/scenarios.ts` / fixtures 仍保留。

Mock 的“继续下一回合”仍复用静态 `advance_round.json`，不会真实推进任意回合；这是有意限制，前端不得模拟 Engine。

## Developer A 当前状态

2026-09-10 Shared Review 已完成 MiMo/provider runtime 只读审计并解除 Gate。

权威状态：

```text
A0 DynamicRuleController V0.2                 DONE
A1 MatchApplicationService                    DONE
A2 repository / revision / lock / idempotency DONE
A3 FastAPI five-route vertical slice          READY
```

根目录 `DEVELOPER_A_GATE.md` 当前：

```text
DEVELOPER_A_GATE = READY
CURRENT_TASK = A3 FastAPI V0.2 five-route vertical slice
ISSUE = #53
DO_NOT_START = false
```

Gate 解除提交：

```text
34df26d0d5fbda010b2ffed59df556246b34c0e6
```

Issue #53 标题已改为 `[READY][Developer A]`，并有新的 READY 评论。A3 启动时必须从最新 main 新建 `backend/fastapi-v02`。

A3 额外启动约束已写入 Gate / #53：

- production `MIMO_BASE_URL` 必须 HTTPS；
- 防止携带 `api-key` 的 urllib 请求跨主机 redirect；
- TestClient 所需 `httpx` 必须显式加入 dev dependency；
- A3 必须提供真正可启动给 B4 使用的 ASGI server 入口 + runtime dependency；
- import/OpenAPI export 不得依赖 `MIMO_API_KEY`；
- A3 不得自行改 `web/**` 或 public OpenAPI；需要改 contract 时必须 `CONTRACT CHANGE REQUIRED` 交 Shared Review 同步 snapshot + generated TS。

## Developer B 下一步

**现在不要实现真实 HTTP adapter。**

等待：

```text
A3 implementation
→ A3 PR
→ Shared Review 审核五路由 / ErrorEnvelope / idempotency / provider safety / runnable server
→ A3 merge
```

之后 Developer B 才进入 B4：

```text
真实 HTTP MatchApiAdapter
→ create match
→ Round 1 advance
→ accepted/rejected rule submit
→ next advance
→ snapshot/replay
→ revision + Idempotency-Key + ErrorEnvelope UX
→ 最终删除 MockScenarioBar / mock scenarios（确认真实 flow 稳定后）
```

B4 优先采用 Vite dev proxy / 同源部署方式；不要在没有需要时扩大 CORS。

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
