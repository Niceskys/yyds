# Developer B Handoff

## 当前基线

- integration baseline: `main@49322f3f`（PR #43 已使用 merge commit 合并，Developer B 的 10 条提交历史全部保留）
- contract version: `mvp-v0.2`
- B0: 完成并已合并
- B1: 完成并已合并
- B3: 仅基础 Replay 时间线完成
- B4: 未开始，等待 Developer A 的真实 FastAPI vertical slice
- Shared frontend CI: `ci/frontend-v02` / Issue #42，本次共享基础设施变更加入正式 CI

## 已完成

- React + TypeScript + Vite 应用外壳，初始页《规则之外》+「开始游戏」。
- fixture → adapter → ViewModel → React 组件的单向数据流。
- 棋盘按 `board.rows` / `board.cols` 渲染；公共坐标保持 1-based，row 1 在顶部、col 1 在左侧。
- 红方 / 蓝方面板：生命值、当前策略、实际行动、当前有效属性。
- 顶部状态：已完成回合、规则制定次数、当前公共规则、战局升温。
- 规则输入 / 提交 / 继续下一回合按钮状态只来自 `PlayerDecisionSnapshot`。
- accepted / rejected / terminal 三类状态渲染。
- 中文映射集中在 `src/contract/labels.ts`。
- `conflict_level` / `hard_liveness` / `hard_liveness_active` 不直接进入普通玩家 UI。
- 开始游戏后消费 `advance_round.json`：第 1 回合自动完成后进入首次 `PLAYER_DECISION`，同时保留 Round 1 的公开策略、实际行动和公开事件。
- `src/styles/app.css` 已补齐，覆盖首页、棋盘、状态面板、规则区、回放和移动端布局。
- npm 自动生成的 `package-lock.json` 已入库，可使用 `npm ci` 重现依赖。
- Replay 基础时间线按后端 `ROUND / INTERMISSION` 顺序展示，第一条为 Round 1。
- 未知 `RoundEventPublicView.kind` 使用安全 fallback。
- PR #43 合并前已在 GitHub hosted runner 真实验证：`npm ci`、typecheck、29/29 tests、production build 全部 PASS。
- 正式 frontend CI 由 `.github/workflows/frontend.yml` 提供；除 `web/**` 外，V0.2 fixture 变化也会触发检查。

## 最近关键提交

- `9a8150b` — feat(frontend): bootstrap React/Vite app shell with start screen
- `ad5cfa7` — feat(frontend): add V0.2 fixture adapter and UI view model layer
- `0e2b97d` — feat(frontend): render board and red/blue status panels from V0.2 fixtures
- `6449098` — feat(frontend): wire rule submission, terminal result and replay timeline
- `9f18392` — test(frontend): cover B1 UI states, coordinates and privacy boundaries
- `58b1256` — docs(frontend): record Developer B commit history in handoff
- `e246668` — docs(frontend): note missing package-lock.json as a follow-up
- `9b116076` — fix(frontend): add missing app stylesheet
- `0dc0790c` — build(frontend): lock B0/B1 npm dependencies
- `1a18fd4` — fix(frontend): preserve round-one execution details on start
- `49322f3f` — merge PR #43, preserve full Developer B history

## 当前可运行状态

```bash
cd web
npm ci
npm run dev
```

验证命令：

```bash
npm run typecheck
npm run test
npm run build
```

当前 Mock 行为：

- 初始页显示《规则之外》与「开始游戏」。
- 点击开始游戏后消费 `advance_round.json`，表示 Round 1 自动完成并进入首次玩家决策阶段。
- 游玩界面显示顶部状态、红蓝面板、棋盘、本回合结果、规则输入区。
- 开发演示条可切换 8 个 V0.2 fixture 场景。
- Mock 提交 / 推进只切换 fixture，不调用真实后端。
- 终局可进入 Replay 基础时间线。

## 尚未完成

- B2 收尾：真实提交 / 推进时携带 `expected_revision` 与 `Idempotency-Key`，并处理服务端错误。
- B3 完整版：逐回合棋盘回放、事件筛选、规则效果对比。
- B4：真实 API Adapter + OpenAPI generated types。
- B4 完成后删除 Mock 专用 `MockScenarioBar` / `mock/scenarios.ts`，并删除临时手写 `src/contract/types.ts`。

## 已知问题 / 技术债

- `src/contract/types.ts` 是 **TEMPORARY / NON-CANONICAL**，禁止继续扩张成第二套长期 API schema；B4 必须由 OpenAPI generated types 替换。
- Mock 的“继续下一回合”当前复用固定 `advance_round.json`，不会真实增加回合号；前端不得自行模拟 Engine/回合逻辑。
- npm audit 在 PR #43 验证时报告 4 个传递依赖问题（2 moderate / 1 high / 1 critical）；未使用 `npm audit fix --force` 擅自升级，需单独评估具体包和生产影响。
- 当前 `useState` 足够，未引入额外状态管理库。

## 下一步

1. 完成并合并 Issue #42 的 frontend CI；该 CI 必须执行 `npm ci` + typecheck + test + build。
2. 核验 Developer A 最新进度，只有真实 FastAPI vertical slice 可调用后才进入 B4。
3. B4 使用 OpenAPI 生成 TypeScript 类型，并通过 API Adapter 复用现有 ViewModel / React 组件。
4. 增加 revision conflict、幂等重试、服务端失败的用户级错误处理。
5. 单独审计 npm audit 报告，不与功能 PR 混合做强制依赖升级。

## 下一位开发者必须先读

1. `docs/GAMEPLAY_FLOW_V0.2.md`
2. `docs/MVP_API_CONTRACT_V0.2.md`
3. `contracts/README.md`
4. `web/DEVELOPMENT_HANDOFF.md`
5. Issue #38、Issue #42
6. 最近 5–10 个 Git commits
