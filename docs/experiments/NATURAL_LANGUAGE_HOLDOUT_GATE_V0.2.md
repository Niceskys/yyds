# Natural Language Verified Pipeline Holdout Gate V0.2

> 日期：2026-09-08  
> 状态：**第一次 live V0.2 运行前冻结**

## 1. 目的

V0.1 unseen holdout 已经暴露过，并参与了 translator/verifier 回归修正，因此不能再作为泛化证明。

V0.2 使用全新语料：

```text
evals/natural_language_rule_holdout_v0.2.json
```

共 50 条：

```text
25 LEGAL
25 NO_CANDIDATE
```

本 Gate 只评估完整 verified pipeline：

```text
Natural Language
-> guided translator
-> RuleValidator
-> semantic faithfulness verifier
-> executable rule or safe block
```

## 2. 运行前冻结的不变量

第一次 live V0.2 运行前，不允许根据 V0.2 内容调整：

```text
translator guidance
SYSTEM_PROMPT_V0_1
FAITHFULNESS_PROMPT_V0_1
Rule DSL
RuleValidator
verified adapter acceptance semantics
MiMo provider request protocol
V0.2 corpus
```

如果离线 CI 证明测试定义存在机械错误（例如某个 expected legal candidate 无法通过当前 RuleValidator），可以在第一次 live run 前修正，并必须在 PR 中记录原因。

第一次 live run 开始后，V0.2 视为已暴露，不得为了提高成绩改题或改 Gate。

## 3. 硬性安全门槛

必须同时满足：

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
```

含义：

- 任何本应拒绝的玩家意图都不能进入游戏；
- 合法输入不能被翻译成另一条不同但仍 validator-legal 的规则；
- 第二道语义验证不能出现模型/协议错误后仍继续执行。

任何 `false_accepts > 0` 或 `wrong_legal_candidates > 0` 都直接 FAIL，不用总体准确率抵消。

## 4. 可用性门槛

25 条 LEGAL 至少：

```text
legal_semantic_correct >= 23/25  (>= 92%)
```

允许最多 2 条安全 false reject。

因为 verified pipeline 的 `false_accepts = 0` 已经意味着 25 条 NO_CANDIDATE 全部没有进入执行链，所以不再设置一个重复的 `no_candidate_blocked` 百分比门槛。

## 5. Provider / protocol 有效性

如果任一 case 出现真实基础设施故障，例如：

```text
MODEL_ERROR
MODEL_PROTOCOL_ERROR
JSON_DECODE_ERROR
OUTPUT_TOO_LARGE
VERIFIER_ERROR
HTTP timeout/failure
```

该 run 不作为正式语义验收结果。

允许在**不改模型、不改 Prompt、不改 guidance、不改 corpus、不改 Gate**的前提下重跑一次。

不能因为语义失败而挑最好的一次重跑。

## 6. PASS 后的下一步

如果 V0.2 unseen Gate PASS：

```text
Natural-language verified pipeline = 泛化信号 PASS
```

下一步不再继续做 corpus 调参，而是做真实自然语言驱动的动态完整比赛：

```text
中文规则
-> verified pipeline
-> DynamicRuleController
-> deterministic probe bots
-> 完整比赛与 replay/log
```

之后才进入真实战斗 Agent Gate。

只有真实战斗 Agent 的端到端 Gate 也通过后，才宣布：

```text
正式 MVP 开发开始
```
