# Handoff — AI developer entry + validation history

日期：2026-09-08

## 1. 为什么需要这次变更

项目已经从核心验证阶段切换到正式 MVP 开发，并开始双人 + 多 AI 并行协作。

检查最新 `main` 时发现两个继承风险：

1. 根 README 仍停留在非常早期状态，甚至写着“当前仓库仍没有可运行 Game Engine”；
2. 验证证据分散在 experiments、handoffs、PR、Actions artifact 和聊天上下文里，新 AI 很难快速还原“为什么架构变成现在这样”。

因此本分支建立统一入口和证据索引。

## 2. 本分支做了什么

### 新增

```text
AI_DEVELOPER_START_HERE.md
docs/VALIDATION_HISTORY.md
```

### 更新

```text
README.md
```

## 3. `AI_DEVELOPER_START_HERE.md` 的职责

它是新的 AI / 新开发者第一入口，明确：

- 当前是正式 MVP 开发；
- 当前架构；
- source of truth 优先级；
- V0.1 不可擅自修改的基线；
- Developer A / B ownership；
- 热点文件；
- 测试 / PR / handoff 协议；
- 已知 false reject 债务；
- 明确禁止 AI 擅自做的事项。

后续任何 AI 开始非 trivial 工作前，应优先读取该文件。

## 4. `docs/VALIDATION_HISTORY.md` 的职责

它不是原始日志复制，而是测试与架构决策的总索引。

记录：

```text
假设
→ 测试
→ PASS / FAIL
→ 发现的问题
→ 架构修正
→ 新 regression / unseen Gate
→ 当前可依赖结论
```

特别保留：

- natural-language semantic laundering 风险；
- Holdout V0.1 FAIL；
- V0.2 OR→AND FAIL；
- V0.3 unseen PASS；
- Dynamic NL Match V0.1 FAIL；
- Dynamic NL Match V0.2 safe false reject FAIL；
- Agent / Planner Gate 定义修正；
- live Agent / Planner PASS；
- 正式 MVP 开发触发依据。

## 5. README 修正

README 已从旧验证阶段更新到真实当前状态：

```text
正式 MVP 产品开发
```

并增加：

- AI developer first-read 链接；
- validation history 链接；
- 当前架构；
- 当前产品 baseline；
- 已验证结论；
- 未解决问题；
- 双人分工；
- 当前 MVP 主线。

## 6. 明确没有修改

本分支没有修改：

- Engine；
- Rule DSL；
- Validator；
- DynamicRuleController；
- natural-language Prompt；
- Faithfulness Verifier；
- Agent；
- Planner；
- API 实现；
- frontend 实现；
- 产品规则数值。

## 7. 后续不要重复做什么

不要再创建另一份功能重复的：

```text
AI_GUIDE.md
AGENTS_README.md
TEST_HISTORY.md
PROJECT_CONTEXT_FOR_AI.md
```

如果缺内容，优先维护：

```text
AI_DEVELOPER_START_HERE.md
docs/VALIDATION_HISTORY.md
```

避免入口文档再次分裂。

## 8. 下一步

本 PR 合并后：

1. Developer A 可以开始 `MVP_API_CONTRACT_V0.1`；
2. Developer B 可以开始 `frontend/app-shell` fixture/mock；
3. 可以并行启动第二轮独立深度研究，但研究目标应改为 MVP readiness / architecture / product / competition audit，而不是重复第一次创意可行性审计。
