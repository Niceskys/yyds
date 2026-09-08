# Live Natural-Language Benchmark Runbook

> 目的：让不熟悉命令行的协作者通过 GitHub UI 安全运行真实模型语料测试。
>
> 当前 live provider：**MiMo China Token Plan**。智谱 Provider 保留，API 恢复后可用同一 corpus 比较。

## 1. 当前推荐：MiMo China Token Plan

官方 OpenAI 兼容 Base URL：

```text
https://token-plan-cn.xiaomimimo.com/v1
```

当前 benchmark 默认模型：

```text
mimo-v2.5-pro
```

真实 Token Plan Key 不进入仓库。

## 2. 只需要配置一次 GitHub Secret

在 GitHub 仓库：

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

名称必须是：

```text
MIMO_API_KEY
```

值填写 Token Plan 页面提供的专属 key（通常为 `tp-...`）。

注意：

- 不要把 Key 写进 Issue / PR / README；
- 不要提交 `.env`；
- 不要把 Key 发给其他 AI 作为普通聊天文本；
- Workflow 日志不会主动输出 Key；
- Token Plan Key 与按量付费 Key 是两套独立凭证，不要混用。

## 3. 运行 MiMo benchmark

```text
Actions
→ live-natural-language-benchmark
→ Run workflow
```

保持：

```text
provider = mimo
model = mimo-v2.5-pro
```

然后点击运行。

该 workflow 只有手动触发，不会因为普通 push / PR 自动消耗 Token Plan 额度。

## 4. 查看结果

运行完成后，在该 Workflow Run 页面底部下载 Artifact：

```text
natural-language-benchmark
```

其中：

```text
result.json
```

包含 18 条固定语料的完整评分。

重点先看：

```text
false_accepts
wrong_legal_candidates
false_rejects
decision_accuracy
legal_semantic_correct
```

不要只看 `exact_accuracy`。

其中最危险的是：

```text
false_accepts > 0
```

即本应拒绝的玩家意图被模型偷偷改写成合法 Candidate。

## 5. 可选：比较 mimo-v2.5

如果 `mimo-v2.5-pro` 已跑完，可以再次 Run workflow：

```text
provider = mimo
model = mimo-v2.5
```

必须使用同一 commit / 同一份 corpus，再比较结果。

## 6. 智谱恢复后的比较

智谱 API 可用后，可以配置：

```text
ZHIPU_API_KEY
```

然后运行：

```text
provider = zhipu
model = glm-5.1
```

MiMo 暂代 GLM 不代表永久替换。是否切回或继续使用 MiMo，必须基于同一 corpus 和后续端到端对局数据决定。

## 7. 当前 Gate

在真实结果出来前：

```text
MiMo Provider implementation = 完成后可合并
MiMo live validation = 未完成
```

因此仍不能宣布正式 MVP 开发开始。
