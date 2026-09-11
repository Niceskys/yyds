# Developer A Execution Gate

> **Developer A / 后端 AI 在进行任何非 trivial 开发前必须先检查本文件。**
>
> 本文件只决定“现在允许 Developer A 做什么”，不替代 `AI_DEVELOPER_START_HERE.md`、当前里程碑、Issue、contract 或 handoff。

## CURRENT STATUS

```text
DEVELOPER_A_GATE = PAUSED_BY_OWNER
LAST_COMPLETED_TASK = A3 FastAPI V0.2 five-route vertical slice
LAST_COMPLETED_ISSUE = #53
LAST_COMPLETED_PR = #59
A3_MERGE = b79b1da08a3ff5801b286b5f970f7e371fd85a08
B4_MERGE = 8769649cf587862b72f241fc64b531e5fdbbdbe6
CURRENT_APPROVED_BACKEND_TASK = NONE
LAST_SHARED_GATE = M1 Integrated Playable Acceptance / Issue #64 / PASSED
CURRENT_FRONTEND_TASK = B5A / Issue #63 / READY_FOR_DEVELOPER_B
DEVELOPER_A_ACTION_ON_B5A = NONE
DO_NOT_START = true
DO_NOT_START_NEW_TASK = true
```

## 当前项目工程状态

```text
A0 DynamicRuleController V0.2                         DONE
A1 MatchApplicationService                            DONE
A2 Repository / revision / lock / idempotency         DONE
A3 FastAPI five-route vertical slice                  DONE — PR #59

B0/B1 React/Vite + fixture UI                         DONE
B3 Replay                                             DONE
B4 real HTTP integration                              DONE — PR #61
M1 technical HTTP slice                                PASS — Issue #64
M1 browser/live-provider Gate                          PASS — Issue #64 / PR #65
B5A core causal-feedback motion / Issue #63            READY_FOR_DEVELOPER_B
```

工程纵向切片已经接通。当前阶段不再是继续补 A0–A3 后端功能，而是进入新的 MVP 验收 / 实验阶段。

M1 最终记录见 `docs/experiments/M1_INTEGRATED_PLAYABLE_ACCEPTANCE_2026-09-10.md`。真实 Chromium + live MiMo 已完成规则拒绝、规则接受、5 回合终局与 authoritative Replay；M1 GATE 1 已通过。Developer A 仍保持暂停，因为 B5A 是纯 Developer B 表现层任务，不构成新的后端授权。

Issue #63 已由 Shared Review 放行为 Developer B 当前表现层任务，不是 Developer A 授权。B5A 放行不会自动解锁 Developer A。

## Developer A 当前允许

```text
读取最新 main
读取本 Gate / AI_DEVELOPER_START_HERE.md / 当前里程碑文档
查看 A0–A3 handoff 与 Shared Review 结果
做只读分析
回答问题
为新的、尚未批准的任务提供方案评估
```

## Developer A 当前禁止

```text
继续向旧 backend/fastapi-v02 等历史分支 push
重新开始 A0 / A1 / A2 / A3
开始旧 Day 4 / Day 5
开始任何新的 backend feature
修改 Developer B web/**
擅自扩大 public schema / OpenAPI
擅自修改 gameplay / Engine / Controller cadence / Rule DSL / Validator
重写 A1/A2 revision / lock / idempotency
引入 DB / Redis / Celery / WebSocket / 账号 / leaderboard
以旧聊天、旧 Issue 或旧 handoff 中的 READY 文案作为授权
```

## 已冻结的关键语义

- strategy provider/model failure → HTTP 200 `AdvanceResult`；失败方 public strategy `degraded=true`，使用 public fallback status；
- rule provider/model failure → HTTP 200 `RuleSubmissionResult`，`accepted=false`、`public_code=MODEL_UNAVAILABLE`，revision / rule_change_count 不增加；
- `503 INTERNAL_ERROR retryable=true` 仅用于真正的 `RecoverableMatchFailure`；
- OpenAPI/public schema 以当前 canonical contract 为准；
- revision / Idempotency-Key / per-match lock 语义不得在新任务中悄悄改写；
- Round 1 前无玩家规则，每个非终局完整回合后进入玩家决策；不得恢复旧 Phase 0 / 每 3 回合规则阶段。

## 后续解锁规则

只有项目负责人 / Shared Review 完成以下步骤后，Developer A 才能恢复非 trivial backend 工作：

1. 基于最新 `main` 创建一个**新的** Developer A Issue；
2. 明确该 Issue 的目标、边界、验证条件和是否影响 public contract；
3. 将本文件更新为：

```text
DEVELOPER_A_GATE = READY
CURRENT_APPROVED_BACKEND_TASK = <new task>
DO_NOT_START = false
DO_NOT_START_NEW_TASK = false
```

4. 在对应 Issue 留下明确的 `READY — 可以开始` 评论；
5. Developer A 从最新 remote main 新建分支，不能从旧工作区/旧分支继续。

旧聊天、旧 Day 4/Day 5 计划、旧 READY 评论都不能视为新授权。
