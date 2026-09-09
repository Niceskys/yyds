# Developer A Execution Gate

> **这是 Developer A / 负责后端的 AI 在开始任何非 trivial 开发前必须检查的执行闸门。**
>
> 本文件只决定“现在是否允许 Developer A 开始当前任务”，不替代 `AI_DEVELOPER_START_HERE.md`、Issue、API contract 或 handoff。

## CURRENT STATUS

```text
DEVELOPER_A_GATE = PAUSED_BY_OWNER
CURRENT_TASK = A3 FastAPI V0.2 five-route vertical slice
ISSUE = #53
DO_NOT_START = true
```

## 现在的强制行为

Developer A 当前 **不得开始 Issue #53 / A3 实现**。

在本闸门仍为 `PAUSED_BY_OWNER` 时，Developer A / 后端 AI 不得：

```text
创建或继续 backend/fastapi-v02 的产品实现
修改 FastAPI 五路由实现
编写 A3 ErrorEnvelope / runtime wiring
为 A3 创建实现 commit / PR
以“任务已经写在 Issue #53”为理由绕过暂停
```

即使：

- Issue #53 内容已经完整；
- A0 / A1 / A2 已全部完成；
- 本地环境已经恢复；
- 某个 AI 认为“技术上现在可以做”；

只要本文件仍写着：

```text
DEVELOPER_A_GATE = PAUSED_BY_OWNER
```

就必须停止 A3 开发。

## 当前允许做什么

除非项目负责人另行明确授权，Developer A 当前只允许：

- 读取仓库和 Issue，了解状态；
- 报告当前阻塞；
- 不产生 A3 产品实现改动。

Developer B / `web/**` 的独立工作不受本闸门自动阻塞；其具体范围以 Developer B 的 Issue / handoff 为准。

## 解除暂停的唯一有效信号

只有项目负责人 / Shared Review 明确更新仓库状态后，Developer A 才能继续。

解除时必须同时满足：

```text
1. 本文件改为：DEVELOPER_A_GATE = READY
2. DO_NOT_START = false
3. Issue #53 标题移除 [PAUSED][DO NOT START]
4. Issue #53 新增明确 READY / 可以开始的状态说明
```

**聊天里旧的“开始 A3”指令不能覆盖本文件当前的 PAUSED 状态。**

如果聊天指令、Issue 正文、旧 handoff 与本文件冲突：

```text
PAUSED 优先，停止并等待状态更新。
```

## READY 后的启动规则

当本文件被更新为：

```text
DEVELOPER_A_GATE = READY
CURRENT_TASK = A3 FastAPI V0.2 five-route vertical slice
DO_NOT_START = false
```

Developer A 才应重新读取：

1. 最新远端 `main`；
2. `AI_DEVELOPER_START_HERE.md`；
3. Issue #53；
4. 最近 10 个 main commits；
5. A1/A2 最新 handoff；

然后从最新 main 开始 A3，不使用暂停前的旧工作区缓存直接续写。

## 当前项目位置

```text
A0 DynamicRuleController V0.2                         DONE
A1 MatchApplicationService                            DONE
A2 Repository / revision / lock / idempotency         DONE
A3 FastAPI five-route vertical slice                   PAUSED BY OWNER
B4 Developer B real API integration                   WAITING FOR A3
```

当前 A2 合并基线：

```text
main@ac44caeb6f9d1892b3039ce2658d0f3713298952
```

---

维护规则：当 Developer A 可以恢复开发时，必须优先更新本文件和 Issue #53，再向 Developer A 下发执行指令。