# 本机修改版变更报告（云端测试分支）

日期：2026-09-13  
目标分支：`codex/cloud-stability-test-20260913`  
本机快照提交：`2f0c5e951551593e143016e69838a460ca3dce4d`

## 1. 报告目的

本分支是用户本机 `D:\tokens-competition` 当前工作版本的脱敏、隔离快照，
用于代码审阅与后续云端测试。它不包含 API key、`.env`、`.git`、Python
虚拟环境、前端依赖、构建产物、本地运行数据或测试缓存。

本分支使用独立根提交建立，未修改 `main`，未创建 Pull Request。本报告只描述
本次本机修改，不把历史实验文档中的结论重新解释为当前测试结果。

## 2. 修改摘要

本次修改包含两个相互独立的功能目标：

1. 将游戏运行时从 MiMo 专用配置扩展为可配置的 OpenAI-compatible 模型接口，
   并对比赛要求使用的 GLM-5.1 做协议适配。
2. 修复双方重复争抢同一空格后同时停留、攻击失效并可能反复循环的问题。

公共 HTTP API 路径、请求体、响应模型和 OpenAPI V0.2 契约没有改变。

## 3. OpenAI-compatible 与 GLM-5.1 适配

### 3.1 新增通用模型适配器

新增：

- `src/rules_beyond/openai_compatible_provider.py`
- `tests/test_openai_compatible_provider.py`

适配器同时实现规则生成与双方策略生成所需协议，支持配置：

- `MODEL_API_KEY`
- `MODEL_API_MODEL`
- `MODEL_API_BASE_URL`
- `MODEL_API_AUTH_HEADER`
- `MODEL_API_AUTH_SCHEME`
- `MODEL_API_JSON_MODE`
- `MODEL_API_TOKEN_FIELD`
- `MODEL_API_TIMEOUT_SECONDS`

如果三个核心 `MODEL_API_*` 配置均未提供，运行时仍保留原有 MiMo 配置作为
兼容回退。只提供部分核心配置时会在启动阶段明确报错，避免静默混用两套配置。

### 3.2 GLM-5.1 特殊请求规则

模型名严格为 `glm-5.1`（忽略大小写）时：

- 发送 `thinking: {"type": "disabled"}`；
- 发送 `response_format: {"type": "json_object"}`；
- `max_tokens` 不低于 1024；
- 保持非流式 Chat Completions 请求。

这样做是为了让策略和规则模型返回程序能够校验的小型 JSON 对象，减少思考文本、
Markdown 或非结构化输出造成的 `FALLBACK_PROTOCOL_ERROR`。

### 3.3 传输与密钥安全

通用适配器增加了以下保护：

- 远程地址只允许 HTTPS；本机回环地址可使用 HTTP，便于本地兼容服务调试；
- URL 不允许嵌入用户名或密码，也不允许 fragment；
- 只跟随严格同源重定向，避免认证头被发送到其他源；
- 模型响应限制为 1 MiB；
- 网络错误、超时、HTTP 错误和非法 JSON 转换为受控 Provider 异常；
- 错误信息不包含 API key、认证头、完整提示词或模型响应正文；
- 支持从 JSON 代码围栏中提取正文，兼容部分模型的常见返回形式。

### 3.4 运行与文档

更新了：

- `.env.example`
- `README.md`
- `docs/PLAYTEST_QUICKSTART.md`
- `scripts/start-local-playtest.ps1`
- `src/rules_beyond/api_runtime.py`
- `src/rules_beyond/api_server.py`
- `src/rules_beyond/__init__.py`

本地启动脚本现在可以交互输入接口地址、模型名和密钥；密钥不写入仓库文件。

## 4. 同格争抢循环修复

### 4.1 新裁定规则

当且仅当双方在同一移动子步都主动进入同一个原本为空的格子时：

1. 使用 `(match_seed + round_no) % 2` 决定本回合移动优先方；
2. 结果为 `0` 时 RED 优先，结果为 `1` 时 BLUE 优先；
3. 优先方进入目标格，另一方保持原位；
4. 双方停止本回合剩余移动路径；
5. 攻击继续按照裁定后的最终位置结算。

该规则不使用额外随机数，因而相同种子、回合和动作仍可完全复现，并且优先权会
逐回合交替。

事件类型继续使用 `SAME_DESTINATION_CONFLICT`，新增公开详情：

```json
{
  "winner": "RED",
  "blocked": "BLUE",
  "resolution": "PRIORITY_ENTRY"
}
```

保留已有事件类型可避免破坏 API 与回放消费者。新版前端会显示“同格争抢已裁定”
及优先方；缺少新字段的历史回放仍使用旧文案。

### 4.2 明确保留的规则

以下行为没有改变：

- 一方进入另一方仍占据的格子时，移动方受阻；
- 双方直接交换位置时，双方移动受阻；
- 任意裁定后两个单位均不得重叠；
- 非法移动路径仍会被归一化处理；
- 攻击合法性始终根据移动结束后的最终位置判断。

因此，本次修改只解决“双方主动争抢同一个空格”的循环，不扩大到其他碰撞类型，
降低了修改引擎核心语义的风险。

### 4.3 涉及文件

- `src/rules_beyond/engine.py`
- `src/rules_beyond/rule_engine.py`
- `web/src/contract/eventLabels.ts`
- `web/src/__tests__/mockAdapter.test.ts`
- `tests/test_movement.py`
- `tests/test_rule_runtime.py`
- `tests/test_strategy_agent.py`
- `docs/P0_RULE_FREEZE_V0.1.md`
- `docs/GAME_DESIGN_V0.1.md`

## 5. 测试与确定性基准

### 5.1 新增或增强的回归覆盖

测试覆盖了：

- 同一空格优先方正确进入；
- 优先权逐回合交替；
- 同一种子和回合结果可复现；
- 第二移动子步发生争抢；
- 冲突后停止双方剩余路径；
- 进入占位格仍被阻挡；
- 直接交换仍被阻挡；
- 裁定后合法攻击不会被取消；
- 截图场景中双方 `PRESSURE`、向中心移动并使用刀攻击时，不再产生
  `INVALID_ATTACK` 循环；
- 规则运行时的 `DID_NOT_MOVE` 等条件根据实际裁定结果计算；
- 前端兼容新事件详情和旧回放事件。

### 5.2 基准文件

历史基准 `docs/baseline/BASELINE_12000_2026-09-07.json` 保持不变。新增：

- `docs/baseline/BASELINE_12000_2026-09-13.json`

`tests/test_baseline_snapshot.py` 已指向新基准。新基准反映同格争抢规则变化后的预期
确定性行为，不应由普通测试自动覆盖；今后更新仍需人工审核差异。

## 6. 已有验证证据

以下结果是在用户后来要求“不得在本机继续运行测试”之前完成的本地验证，不是本次
云端测试结果：

- 后端：320 项 pytest 测试通过；
- 前端：7 个测试文件、55 项 Vitest 测试通过；
- TypeScript 与 Vite 生产构建通过；
- 12,000 局确定性基准比较通过；
- `git diff --check` 未发现补丁格式错误，仅有 Windows 行尾转换提示；
- 后端仅出现两个第三方依赖弃用警告，不是测试失败。

本报告提交时，尚未取得独立云端运行器的执行结果。不得把上述本地验证描述成
云端验证。

## 7. 兼容性与运行影响

### 不受影响

- V0.2 公共 HTTP API 和 OpenAPI 契约；
- 规则 DSL 与 Validator 的允许能力；
- 最大回合、伤害、射程等基础配置；
- 历史 MiMo 配置方式；
- 使用旧格式 `SAME_DESTINATION_CONFLICT` 事件的回放显示。

### 有意改变

- 同一空格争抢不再默认双方都停留；
- 争抢后的双方站位、攻击结果和大规模模拟统计会相应变化；
- 新运行方式可通过 `MODEL_API_*` 使用 GLM-5.1 或其他兼容接口。

### 剩余风险

- 尚未使用真实 GLM-5.1 API 做比赛前门禁；当前只验证了请求构造和假传输；
- OpenAI-compatible 服务之间可能存在非标准响应差异；
- 内存仓库不会自动清理已结束比赛，长期公网服务可能线性增长；
- 规则文本、幂等键和比赛数量尚未建立完整的产品级资源上限；
- 直接交换仍会产生 `SWAP_CONFLICT`，这是保留的规则，不是本次回归；
- 独立云端全量测试仍待可用的云端代码运行环境执行。

## 8. 开发者复核建议

审阅者应按以下顺序检查：

1. 确认检出的提交属于 `codex/cloud-stability-test-20260913`，不要误用 `main`；
2. 检查通用模型适配器不会在异常和日志中暴露认证信息；
3. 检查 GLM-5.1 请求字段是否与比赛使用的服务端点一致；
4. 检查同格优先权只作用于“双方主动进入同一空格”；
5. 检查 RuleAwareGameEngine 与 GameEngine 使用完全相同的优先权计算；
6. 检查前端对新旧冲突事件均可显示；
7. 运行不需要 API 的后端、前端、契约和确定性基准测试；
8. 真实 GLM-5.1 测试必须使用独立密钥环境，禁止把密钥写入仓库或报告。

## 9. 当前结论

本分支适合用于开发者代码审阅和无 API 的独立测试。已有验证表明核心修改没有破坏
现有后端、前端和契约测试，但在真实 GLM-5.1 门禁及独立云端稳定性测试完成前，
不应仅依据本报告宣称达到正式比赛发布标准。
