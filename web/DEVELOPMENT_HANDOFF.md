# Developer B Handoff

## 当前基线

- branch: `frontend/app-shell-v02`
- latest commit: 见 `git log -1`（本文件随每次 Developer B 提交同步更新）
- contract version: `mvp-v0.2`
- current task: B1 — 使用 V0.2 fixture 的 Mock 游玩界面（+ B3 Replay 基础结构）

## 已完成

- B0：React + TypeScript + Vite 应用外壳，初始页《规则之外》+「开始游戏」，无登录/排行/商店/设置。
- B1：fixture → adapter → ViewModel → 组件的单向数据流，未在组件内散落 `fixture.xxx` 访问。
- B1：5×5 棋盘按 `board.rows` / `board.cols` 渲染，公共坐标 1-based、row 1 在顶部、col 1 在左侧。
- B1：红方 / 蓝方面板（生命值、当前策略、实际行动、当前有效属性）。
- B1：顶部状态（已完成回合、规则制定次数、当前公共规则、战局升温）。
- B1：规则输入 / 提交 / 继续下一回合，按钮状态只来自 `PlayerDecisionSnapshot`。
- B1：accepted / rejected / terminal 三种状态渲染。
- B1：中文映射集中管理（`src/contract/labels.ts`）。
- B1：`conflict_level` / `hard_liveness` / `BattleEscalationSnapshot` 不进入玩家可见 UI。
- B1：`src/styles/app.css` 已补齐，覆盖首页、棋盘、状态面板、规则区、回放与移动端响应式布局。
- B1：已提交 npm 生成的 `package-lock.json`，依赖安装可使用 `npm ci` 重现。
- B3 基础：Replay 时间线按 `ROUND → INTERMISSION → ROUND` 顺序渲染，第一条是第 1 回合。
- 未知 `RoundEventPublicView.kind` 走安全 fallback「发生新的战斗事件」。

## 本次提交

### Commit

见下方「提交记录」最后一行。

### 完成内容

- 加入 npm 自动生成的 `web/package-lock.json`（lockfileVersion 3）。
- package-lock 由 GitHub hosted runner 基于当前 `web/package.json` 生成，未手写、未裁剪平台依赖。
- 在全新依赖安装下真实执行 `npm ci`、typecheck、28 个前端测试与 production build。
- 将此前“缺少 package-lock.json”的技术债标记为已解决。

### 主要修改文件

- `web/package-lock.json`
- `web/DEVELOPMENT_HANDOFF.md`

### 验证

GitHub hosted runner（Node 20.20.2 / npm 10.8.2）：

- `npm install --package-lock-only` → PASS
- `npm ci` → PASS
- `npm run typecheck` → PASS
- `npm run test` → PASS（5 文件 / 28 用例）
- `npm run build` → PASS

说明：首次远端构建暴露出 `src/main.tsx` 引用但未提交的 `src/styles/app.css`；已在前一提交 `9b116076` 修复，随后完整 runner 验证通过。

## 提交记录

- `9a8150b` — feat(frontend): bootstrap React/Vite app shell with start screen
- `ad5cfa7` — feat(frontend): add V0.2 fixture adapter and UI view model layer
- `0e2b97d` — feat(frontend): render board and red/blue status panels from V0.2 fixtures
- `6449098` — feat(frontend): wire rule submission, terminal result and replay timeline
- `9f18392` — test(frontend): cover B1 UI states, coordinates and privacy boundaries
- `58b1256` — docs(frontend): record Developer B commit history in handoff
- `e246668` — docs(frontend): note missing package-lock.json as a follow-up
- `9b116076` — fix(frontend): add missing app stylesheet
- 本次提交 — build(frontend): lock B0/B1 npm dependencies

## 当前可运行状态

```bash
cd web
npm ci
npm run dev
```

- 初始页：显示《规则之外》与「开始游戏」；点击后模拟第 1 回合自动完成并进入首次玩家决策阶段。
- 游玩界面：顶部状态 + 红蓝面板 + 棋盘 + 本回合结果 + 规则输入区。
- 页面顶部有「开发演示数据（V0.2 fixture）」切换条，可切换 8 个 fixture 场景：
  初始状态 / 第 1 回合结算 / 回合间决策 / 规则成功 / 规则被拒 / 终局 / 状态冲突 / 终局回放。
- Mock 提交结果可在「规则成功 / 规则被拒」之间切换；提交与「继续下一回合」目前只切换本地 fixture 状态并显示 Mock 提示，不调用任何后端。
- 终局状态下可进入「本局回放」查看 Replay 时间线。

## 尚未完成

- B2 收尾：接入真实 API 后，提交 / 推进需要带 `expected_revision` 与 `Idempotency-Key`。
- B4：真实 API Adapter + OpenAPI generated types（替换 `src/contract/types.ts` 的临时类型）。
- B3 完整版：逐回合棋盘回放、事件筛选、规则效果对比。
- 前端 CI（Issue #42）：等本 PR 合并进入 `main` 后单独处理，不与 B0/B1 业务提交混合。

## 已知问题 / 技术债

- `src/contract/types.ts` 是**临时**手写类型，仅为 mock 阶段服务，必须由 OpenAPI generated types 替换；禁止继续扩张成第二套长期 API schema。
- `src/components/MockScenarioBar.tsx` 与 `src/mock/scenarios.ts` 是开发演示代码，B4 接入真实 API 后删除。
- 当前 npm 审计在 runner 上报告 4 个传递依赖漏洞（2 moderate / 1 high / 1 critical）；本轮未使用 `npm audit fix --force` 擅自升级依赖，后续应单独评估是否影响浏览器生产包与测试工具链。
- 未引入状态管理库；当前 `useState` 足够，后续如接入真实 API 再评估。

## 下一步

1. 等 PR #43 最终审核并合并，不继续在本分支堆 B4 功能。
2. PR #43 合并后处理 Issue #42：新增 frontend CI，执行 `npm ci` + typecheck + test + build。
3. 与 Developer A 确认 FastAPI vertical slice 可调用后，实现 `apiAdapter`（复用同一 ViewModel）。
4. 用 OpenAPI 生成 TypeScript 类型，删除临时 `types.ts`。
5. 增加提交规则 / 推进回合的错误处理（revision conflict、幂等重试）。

## 下一位开发者必须先读

1. `docs/GAMEPLAY_FLOW_V0.2.md`
2. `docs/MVP_API_CONTRACT_V0.2.md`
3. `contracts/README.md`
4. `web/DEVELOPMENT_HANDOFF.md`
5. 最近 5 个 Git commits
