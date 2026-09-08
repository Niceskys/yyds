# MVP 第一批任务板

本文件只列“现在立刻做什么”，完整边界见 `MVP_PARALLEL_DEVELOPMENT_PLAN.md`。

## Developer A — Backend / AI

### A0 — API Contract V0.1

分支建议：

```text
backend/api-contract-v01
```

产出：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

必须冻结：

- create match；
- get match snapshot；
- submit public rule；
- advance one round；
- get replay；
- public strategy intent；
- rule rejection public error shape；
- private Agent memory / hidden reasoning 不出现在 API。

完成后开 PR，Developer B 以此 contract 为唯一接口依据。

### A1 — Match Application Service

分支建议：

```text
backend/match-service
```

在 HTTP 层与 Engine 之间增加 service，不让 route 直接操作 Engine 内部对象。

### A2 — FastAPI Vertical Slice

分支建议：

```text
backend/fastapi-shell
```

以 A0 contract 为准实现最小 API。

---

## Developer B — Frontend

### B0 — React/Vite App Shell

分支建议：

```text
frontend/app-shell
```

新建 `web/`，搭建 React + TypeScript + Vite。

暂时使用 fixture，不等待后端完成。

### B1 — Game Board + Status

分支建议：

```text
frontend/game-board
```

实现：

- 5×5 棋盘；
- RED / BLUE unit；
- HP；
- round；
- active rule；
- rule phase due；
- public strategy intent。

### B2 — Rule Panel

分支建议：

```text
frontend/rule-panel
```

实现：

- 中文规则输入；
- accepted；
- rejected；
- retry / rephrase 提示；
- 只在 rule phase due 时可提交。

前端不自行判断规则是否合法。

---

## 两人第一个同步点

只有一个：

```text
A0 API Contract V0.1 merge
```

在此之前 B 用本地 fixture 开发；之后 B 将 fixture 类型调整到 contract。

不要让 B 等 A 完成全部 FastAPI，也不要让 A 为 UI 细节修改 Engine。
