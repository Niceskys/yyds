# Zhipu Rule Provider V0.1

> 状态：真实 Provider 实现基线；尚未用真实 API Key 跑 live benchmark  
> 日期：2026-09-08

## 1. 目的

把 `RuleCandidateModel` 接到智谱 BigModel 官方 Chat Completions API，但保持权限边界：

```text
Player text
→ ZhipuRuleCandidateModel
→ raw JSON-mode response text
→ NaturalLanguageRuleAdapter
→ CANDIDATE / NO_CANDIDATE envelope
→ RuleValidator
```

Provider 不接收 GameState，也没有 Engine / DynamicRuleController 写权限。

## 2. 官方 API 基线

当前实现使用：

```text
POST https://open.bigmodel.cn/api/paas/v4/chat/completions
Authorization: Bearer <API_KEY>
```

请求关键参数：

```json
{
  "model": "glm-5.1",
  "thinking": {"type": "disabled"},
  "response_format": {"type": "json_object"},
  "stream": false,
  "max_tokens": 1024
}
```

选择原因：

- 项目当前设计基线是 GLM-5.1；
- 规则结构化是短、窄任务，不需要默认开启深度思考；
- JSON mode 可减少 Markdown / 解释文字等格式失败；
- 模型名保持可配置，后续可在同一语料集上比较 GLM-5.1 / GLM-5.2。

官方文档：

```text
https://docs.bigmodel.cn/cn/api/introduction
https://docs.bigmodel.cn/cn/guide/models/text/glm-5.1
https://docs.bigmodel.cn/cn/guide/capabilities/struct-output
```

## 3. 为什么不直接引入 SDK

V0.1 使用 Python 标准库 HTTP，而不是 `zai-sdk`。

目的：

- 少一个外部版本依赖；
- Provider 接口足够简单；
- 更容易在测试中替换 HTTP Transport；
- 核心 Engine 不受 Provider SDK 版本变化影响。

未来如果 SDK 明显降低维护成本，可以另 PR 替换，但行为契约不能改变。

## 4. Secret 管理

只允许：

```text
ZHIPU_API_KEY
```

从环境变量或运行时构造参数传入。

仓库新增：

```text
.gitignore
.env.example
```

`.env` / `.env.*` 默认被忽略。

禁止：

- 把 API Key 写进 Python 文件；
- 写进测试 fixture；
- 写进 README / handoff；
- 写进 GitHub commit / PR body；
- 把 Authorization header 输出到 benchmark JSON。

## 5. 模型选择

默认：

```text
glm-5.1
```

可通过：

```text
ZHIPU_RULE_MODEL
```

或 benchmark CLI 的 `--model` 覆盖。

GLM-5.2 已经发布，但当前不自动升级。模型切换必须使用固定语料集对比，而不是按“更新=一定更适合”推断。

## 6. 固定语料集

文件：

```text
evals/natural_language_rule_corpus_v0.1.json
```

当前 18 条：

```text
8 条明确合法
10 条 NO_CANDIDATE / 非法 / 模糊 / Prompt Injection
```

覆盖：

- HP 条件；
- 距离条件；
- 历史条件；
- 回合条件；
- cooldown；
- 阵营偏置；
- 回血；
- 修改最大回合；
- 直接死亡；
- 绝对坐标；
- 模糊描述；
- Prompt Injection；
- 任意代码式效果。

## 7. Benchmark 指标

不要只看一个总分。

输出至少区分：

```text
exact_accuracy
  = exact candidate / reason-code 是否完全符合预期

decision_accuracy
  = 该生成 Candidate 时是否生成；该拒绝时是否 NO_CANDIDATE

legal_semantic_correct
  = 明确合法规则是否映射成预期 DSL

no_candidate_decision_correct
  = 非法/模糊输入是否安全拒绝

false_accepts
  = 本应拒绝，却被模型“洗白”为合法 Candidate

false_rejects
  = 本应合法，却没有生成 Candidate

wrong_legal_candidates
  = 生成了合法 Candidate，但语义不是预期规则
```

其中 `false_accepts` 是高风险指标。

## 8. 运行 live benchmark

先在本地安全注入：

```text
ZHIPU_API_KEY=<your key>
ZHIPU_RULE_MODEL=glm-5.1
```

然后：

```bash
python -m rules_beyond.natural_language_benchmark
```

对比其他模型：

```bash
python -m rules_beyond.natural_language_benchmark --model glm-5.2
```

当前仓库不在 CI 中运行 live benchmark，因为 CI 没有理由默认持有真实 API Key，也不应该让普通 PR 自动产生模型费用。

## 9. 当前未完成

- 尚未真实调用 GLM-5.1；
- 尚无真实结构化成功率；
- 尚未比较 GLM-5.1 / GLM-5.2；
- 尚未定义 retry；
- 尚未进入端到端自然语言动态比赛；
- 尚未接两个真实 LLM 战斗 Agent。

所以 Provider 代码合并后，项目仍然是 Validation 阶段。

## 10. 下一 Gate

必须取得 live corpus 数据后再判断：

```text
Provider implementation
→ live 18-case corpus
→ 检查 false_accepts / semantic errors / protocol failures
→ 必要时改 Prompt 或 Provider 参数
→ 再次 benchmark
```

只有模型的真实表现达到可接受程度，才能进入自然语言动态对局验证。
