# Developer A Execution Gate

> **这是 Developer A / 负责后端的 AI 在开始任何非 trivial 开发前必须检查的执行闸门。**
>
> 本文件只决定“现在是否允许 Developer A 开始当前任务”，不替代 `AI_DEVELOPER_START_HERE.md`、Issue、API contract 或 handoff。

## CURRENT STATUS

```text
DEVELOPER_A_GATE = READY
CURRENT_TASK = A3 FastAPI V0.2 five-route vertical slice
ISSUE = #53
DO_NOT_START = false
```

## 当前授权

Developer A 现在可以开始 Issue #53 / A3，实现必须从最新远端 `main` 创建新的工作分支，不能继续使用暂停前缓存的工作区。

当前集成基线在解除 Gate 时为：

```text
main@d34fa5cf6e301c585f662fd964e998820827e0dc
```

开始前仍必须重新读取远端 `main`；如果 main 已前进，以最新远端为准。

## A3 启动前必须重新读取

1. `DEVELOPER_A_GATE.md`
2. `AI_DEVELOPER_START_HERE.md`
3. Issue #53 及其最新 READY 评论
4. `docs/GAMEPLAY_FLOW_V0.2.md`
5. `docs/MVP_API_CONTRACT_V0.2.md`
6. A1/A2 handoff
7. `contracts/README.md`
8. 最近 10 个 main commits

建议工作分支：

```text
backend/fastapi-v02
```

## Shared Review 的 Provider/runtime 启动补充约束

2026-09-10 在解除暂停前已对现有 MiMo provider 与 A1/A2 wiring 做只读审计。A3 除原 Issue #53 外必须同时满足以下要求：

### 1. MiMo API key transport hardening

现有 provider 使用同步 `urllib`，把 `api-key` 放在 HTTP Header 中；`MIMO_BASE_URL` 当前仅要求非空。

Production runtime 必须：

- 拒绝非 HTTPS 的 `MIMO_BASE_URL`；
- 防止带 `api-key` 的请求被自动跨主机 redirect 后继续发送；
- 不把 API key、请求 Header、provider raw body、system prompt 或 private memory 写入日志 / ErrorEnvelope。

允许为完成此安全边界做**最小 provider transport hardening + tests**；这不构成 gameplay / public API scope expansion。

### 2. HTTP TestClient 依赖必须显式

Issue #53 要求 FastAPI `TestClient` HTTP 测试，而当前 `pyproject.toml` 的 dev 依赖只有 `pytest`。

A3 可以且应加入测试所需的 `httpx` dev dependency；不要依赖 runner 恰好预装。

### 3. A3 必须真正可供 B4 启动

A3 完成后不能只有 TestClient。必须提供可执行的本地 ASGI server 入口与文档化启动命令，使 Developer B 能真实发 HTTP 请求。

如果仓库缺少 ASGI server runtime dependency，应加入最小、明确的 runtime dependency（例如 uvicorn 或等价方案），不要要求开发者依赖全局安装。

同时：

- import / OpenAPI export 不得要求 `MIMO_API_KEY`；
- runtime repository/provider 只能在真正启动 runtime 时构建；
- 不增加第六个业务 route，不用 health route 绕过冻结五路由约束。

### 4. OpenAPI / frontend generated contract 协调

Developer B 的 #55 已合并，当前存在：

```text
contracts/openapi/mvp-v0.2.json
→ web/src/contract/generated/api.ts
```

以及 Python snapshot parity + frontend `contract:check` drift gate。

因此 A3 **不得顺手改变 public OpenAPI schema / paths / response contract**。如果实现过程中认为必须改 OpenAPI：

```text
CONTRACT CHANGE REQUIRED
```

停止自行修改 `web/**`，在 PR/Issue 报告最小差异，由 Shared Review 统一更新 snapshot + generated TS。

运行时返回既有规范要求的 400/409/503 ErrorEnvelope 不代表必须在 A3 顺手扩大 OpenAPI 文档；优先保持 checked-in snapshot 稳定。

## 仍然禁止

A3 不得：

```text
修改 Engine gameplay
修改 Controller cadence
修改 Rule DSL / Validator
重新实现 A1/A2 revision / lock / idempotency
修改 web/**
实现 Developer B B4
引入 DB / Redis / Celery / WebSocket
实现账号 / leaderboard
无需求扩大 CORS / 部署范围
```

## 当前项目位置

```text
A0 DynamicRuleController V0.2                         DONE
A1 MatchApplicationService                            DONE
A2 Repository / revision / lock / idempotency         DONE
A3 FastAPI five-route vertical slice                   READY
B4 Developer B real API integration                   WAITING FOR A3 MERGE
```

---

维护规则：如果 A3 再次需要暂停，必须先把本文件恢复为 `PAUSED_BY_OWNER` + `DO_NOT_START = true`，并同步 Issue #53。