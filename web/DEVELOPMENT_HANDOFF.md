# Developer B Handoff

## 当前基线

- integration baseline: `main@29eeb1950d911acba292625b30a38cc7857a87b9`
- working branch: `frontend/npm-audit-v02`
- current task: Issue #45 — 前端 npm audit 依赖漏洞审计与最小升级
- contract version: `mvp-v0.2`
- B0: 完成并已合并（PR #43）
- B1: 完成并已合并（PR #43）
- B3: 完成并已合并（PR #47，merge `6a930d7ae67dbc5d703bae15d669545fc272fc4e`）
- B4: **未开始且当前阻塞**；Developer A 的 A3 由根目录 `DEVELOPER_A_GATE.md` 暂停（`PAUSED_BY_OWNER`）
- Shared frontend CI: `.github/workflows/frontend.yml` 已进入 main

## 已完成

- React + TypeScript + Vite 应用外壳，初始页《规则之外》+「开始游戏」。
- fixture → adapter → ViewModel → React 组件的单向数据流。
- 棋盘按 `board.rows` / `board.cols` 渲染；公共坐标保持 1-based。
- 红蓝状态、当前规则、回合、规则制定次数、战局升温与规则输入交互。
- accepted / rejected / terminal 三类状态渲染。
- 中文映射集中管理；普通玩家 UI 不直接展示 `conflict_level` / `hard_liveness` / `hard_liveness_active`。
- 开始游戏后消费 `advance_round.json`，保留 Round 1 的公开策略、实际行动和事件。
- npm canonical `package-lock.json` 已入库；正式 frontend CI 使用 `npm ci` + typecheck + test + build。
- B3 基础时间线第一条固定为 Round 1，不存在 Round 1 前规则阶段。

## 本次 Issue #45 实现

- 分支：`frontend/npm-audit-v02`（基于 `main@29eeb1950`）
- 完整审计记录：`web/NPM_AUDIT_2026-09-09.md`
- 最小升级：`vite` 5.4.11 → 5.4.21、`vitest` 2.1.8 → 2.1.9（均为同 major patch，精确版本锁定）
- 结果：advisory 16 → 6（移除 critical `GHSA-9crc-q9x8-hgqq` + 9 条 vite dev-server advisory）
- 未升级：vite 6/7/8、vitest 3/4、esbuild override；原因与触发条件见审计文档
- 验证：`npm ci` / `typecheck` / 31 tests / `build` 全部 PASS；生产 bundle 哈希未变（`index-DQ3Uz6FI.js`）
- 未执行 `npm audit fix --force`；未修改 backend / contracts / 业务 UI
- B4 仍 blocked

## B3 实现（已合并）

Commit：`b2da3c9` — `feat(frontend): add selectable V0.2 replay inspection`

### Replay Adapter / ViewModel

只消费 authoritative `ReplaySnapshot` 公共字段，不重新模拟 Engine：

- `ROUND.pre_round` → 回合开始棋盘 / 状态；
- `ROUND.post_round_units` → 回合结束棋盘 / HP / 位置；
- `ROUND.strategies / actions / events` → 公开策略、实际行动、公开事件；
- `ROUND.effective_stats / battle_escalation` → 当前有效属性与战局升温展示；
- `INTERMISSION.active_rule_before / active_rule_after` → 公共规则变化；
- `choice / submitted_player_text / submission_public_code` → 玩家回合间决策。

### Replay UI

- 左侧/顶部时间线可选择任一 `ROUND` / `INTERMISSION` 节点；
- 默认选择第一条 Round 1；
- Round 节点同时显示“回合开始 / 回合结束”棋盘；
- 显示红蓝 HP、位置、公开策略、实际行动、有效属性、公开事件、战局升温；
- Intermission 节点显示玩家选择、规则制定次数、公共规则 before → after、提交结果；
- 移动端降为单列布局；
- 不调用模型，不展示 chain-of-thought / private memory。

### 测试

`replay.test.tsx` 从 2 个基础测试升级为 4 个 B3 测试：

1. 时间线顺序 + 默认选择 Round 1；
2. Round 1 pre/post 棋盘与 HP；
3. 规则尝试 → continue → Round 2 节点切换，检查规则变化与移动距离 2 格；
4. 隐私边界。

合并前正式 frontend CI 预期：

```text
npm ci
npm run typecheck
npm run test   # 预计 5 文件 / 31 用例
npm run build
```

## 当前可运行状态

```bash
cd web
npm ci
npm run dev
```

当前 Mock 行为：

- 初始页 → Round 1 自动完成 → PLAYER_DECISION；
- Mock 提交 / 推进只切换 canonical fixture，不调用真实后端；
- 终局进入 Replay 后可逐节点检查公开战局事实；
- Replay 不自行推导规则是否合法、命中率、有效属性、升温或胜负。

## 尚未完成

- B3：不做动画插值/自动播放进度条；如果后续需要，应另立产品任务。
- B2 收尾：真实提交 / 推进时携带 `expected_revision` 与 `Idempotency-Key`，并处理服务端错误。
- B4：真实 API Adapter + OpenAPI generated types。
- B4 后删除 `MockScenarioBar` / `mock/scenarios.ts` 和临时手写 `src/contract/types.ts`。

## Developer A 当前同步状态

2026-09-09 核验：

- A0 DynamicRuleController V0.2：DONE（已合并）；
- A1 MatchApplicationService：DONE（PR #50，main@a932100）；
- A2 repository / revision / lock / idempotency：DONE（PR #52，main@ac44caeb）；
- A3 FastAPI five-route vertical slice（Issue #53）：**PAUSED_BY_OWNER**，见根目录 `DEVELOPER_A_GATE.md`。

因此 B4 不得提前开始；必须等 `DEVELOPER_A_GATE.md` 改为 `READY` 且 A3 合并后，再进入 B4。

## 已知问题 / 技术债

- `src/contract/types.ts` 是 **TEMPORARY / NON-CANONICAL**；B4 必须由 OpenAPI generated types 替换。
- Mock 的“继续下一回合”复用固定 `advance_round.json`，不会真实增加回合号；不得在前端模拟 Engine。
- npm audit（Issue #45）：已用最小 patch 升级（vite 5.4.21 / vitest 2.1.9），advisory 16 → 6；剩余 6 条全部位于 dev/build/test 工具链且默认流程不可达，风险接受记录见 `web/NPM_AUDIT_2026-09-09.md`。

## 下一步

1. Issue #45 PR（`frontend/npm-audit-v02`）通过正式 frontend CI 后等待 owner 复审，**不自动 merge**。
2. Developer A 的 A3 仍由 `DEVELOPER_A_GATE.md` 暂停；解除后按 Issue #53 推进。
3. A3 真实 FastAPI vertical slice 可调用且合并后，再进入 B4。
4. 前端工具链 major 升级（vite ≥ 6.4.3 / vitest ≥ 4.1.11）另立任务，不在本次 PR 内。

## 下一位开发者必须先读

1. `docs/GAMEPLAY_FLOW_V0.2.md`
2. `docs/MVP_API_CONTRACT_V0.2.md`
3. `contracts/README.md`
4. `web/DEVELOPMENT_HANDOFF.md`
5. `web/NPM_AUDIT_2026-09-09.md`
6. Issue #37、#38、#45、#46、#53
7. 最近 5–10 个 Git commits
