# Developer A Execution Gate

> **Developer A / 后端 AI 在进行任何非 trivial 开发前必须先检查本文件。**
>
> 本文件只决定“现在允许 Developer A 做什么”，不替代 `AI_DEVELOPER_START_HERE.md`、Issue、contract 或 handoff。

## CURRENT STATUS

```text
DEVELOPER_A_GATE = REVIEW_FIX_IN_PROGRESS_BY_SHARED_REVIEW
CURRENT_TASK = A3 PR #59 review-fix
ISSUE = #53
PR = #59
WORKING_BRANCH = backend/fastapi-v02
DEVELOPER_A_SHOULD_PUSH = false
DO_NOT_START_NEW_TASK = true
```

## 当前授权

Shared Review 正在直接代为完成 PR #59 的最后 review-fix。Developer A **当前不要向 `backend/fastapi-v02` 推送任何提交**，避免覆盖或冲突。

Developer A 现在只允许：

```text
读取最新 main / 本 Gate / Issue #53 / PR #59
查看 Shared Review 的最新评论与提交
报告状态或发现问题
```

Developer A 当前禁止：

```text
向 backend/fastapi-v02 push
重新开始 A3
新建另一个 A3 分支或 PR
开始旧 Day 4 / Day 5
开始新的 backend feature
修改 Developer B web/**
扩大 public schema / OpenAPI
重写 A1/A2 revision / lock / idempotency
修改 gameplay / Engine / Controller cadence / Rule DSL / Validator
引入 DB / Redis / Celery / WebSocket / 账号 / leaderboard
```

## Shared Review 当前正在完成的唯一修复

PR #59 主体已通过复审，只补 B4-facing provider failure 语义锁定：

1. strategy provider/model failure → HTTP 200 `AdvanceResult`，失败方 `status=FALLBACK_MODEL_ERROR`、`degraded=true`，round 正常提交；
2. rule provider/model failure → HTTP 200 `RuleSubmissionResult`，`accepted=false`、`public_code=MODEL_UNAVAILABLE`，revision/rule_change_count 不增加；
3. `503 INTERNAL_ERROR retryable=true` 仅用于真正的 `RecoverableMatchFailure`；
4. 修正 A3 handoff / PR 描述中把 provider failure 一概写成 503 的错误文案；
5. 不修改 public schema、OpenAPI、A1/A2 或 `web/**`。

## 当前项目位置

```text
A0 DynamicRuleController V0.2                         DONE
A1 MatchApplicationService                            DONE
A2 Repository / revision / lock / idempotency         DONE
A3 FastAPI five-route vertical slice                   REVIEW FIX IN PROGRESS — PR #59
B4 Developer B real HTTP integration                  BLOCKED — Issue #60
```

PR #59 修复完成并经 CI/Shared Review 通过后，才会重新更新本 Gate。Developer A 不应根据旧聊天或旧 READY 文案继续推送。