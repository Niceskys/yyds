# Live Natural-Language Benchmark Runbook

> 目的：让不熟悉命令行的协作者通过 GitHub UI 安全运行真实智谱语料测试。

## 1. 只需要配置一次 Secret

在 GitHub 仓库：

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

名称必须是：

```text
ZHIPU_API_KEY
```

值填写智谱 BigModel API Key。

注意：

- 不要把 Key 写进 Issue / PR / README；
- 不要提交 `.env`；
- 不要把 Key 发给其他 AI 作为普通聊天文本；
- Workflow 日志不会主动输出 Key。

## 2. 运行 GLM-5.1

```text
Actions
→ live-natural-language-benchmark
→ Run workflow
```

model 保持：

```text
glm-5.1
```

然后点击运行。

该 workflow 只有手动触发，不会因为普通 push / PR 自动产生 API 费用。

## 3. 查看结果

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

## 4. 比较 GLM-5.2

如果 GLM-5.1 已跑完，可以再次 Run workflow，把 model 改成：

```text
glm-5.2
```

必须使用同一版仓库 / 同一份 corpus，再比较结果。

## 5. 当前 Gate

在真实结果出来前：

```text
Provider implementation = 已完成
Provider live validation = 未完成
```

因此还不能进入端到端自然语言动态比赛，也不能宣布正式 MVP 开发开始。
