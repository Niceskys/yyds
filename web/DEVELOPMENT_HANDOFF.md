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
- B3 基础：Replay 时间线按 `ROUND → INTERMISSION → ROUND` 顺序渲染，第一条是第 1 回合。
- 未知 `RoundEventPublicView.kind` 走安全 fallback「发生新的战斗事件」。

## 本次提交

### Commit

`PENDING`（提交后见 `git log -1`）

### 完成内容

- 增加 vitest + @testing-library 测试（28 个用例），覆盖初始页、按钮状态、棋盘坐标、
  中文映射、隐藏内部字段、未知事件 fallback、Replay 顺序。

### 主要修改文件

- `web/src/__tests__/*.test.ts(x)`
- `web/vitest.setup.ts`
- `web/DEVELOPMENT_HANDOFF.md`

### 验证

- `npm run typecheck` → PASS
- `npm run test` → PASS（5 个测试文件 / 28 个用例）
- `npm run build` → PASS

## 当前可运行状态

```bash
cd web && npm install && npm run dev
```

- 初始页：显示《规则之外》与「开始游戏」；点击进入游玩界面。
- 游玩界面：顶部状态 + 红蓝面板 + 5×5 棋盘 + 本回合结果 + 规则输入区。
- 页面顶部有「开发演示数据（V0.2 fixture）」切换条，可切换 8 个 fixture 场景：
  初始状态 / 第 1 回合结算 / 回合间决策 / 规则成功 / 规则被拒 / 终局 / 状态冲突 / 终局回放。
- Mock 提交结果可在「规则成功 / 规则被拒」之间切换；提交与「继续下一回合」目前只切换
  本地 fixture 状态并显示 Mock 提示，不调用任何后端。
- 终局状态下可进入「本局回放」查看 Replay 时间线。

## 尚未完成

- B2 收尾：接入真实 API 后，提交 / 推进需要带 `expected_revision` 与 `Idempotency-Key`。
- B4：真实 API Adapter + OpenAPI generated types（替换 `src/contract/types.ts` 的临时类型）。
- B3 完整版：逐回合棋盘回放、事件筛选、规则效果对比。
- 前端 CI（Issue #42）：等 `web/` 进入 main 后再处理，本分支未修改 `.github/workflows/**`。

## 已知问题 / 技术债

- `src/contract/types.ts` 是**临时**手写类型，仅为 mock 阶段服务，必须由 OpenAPI generated types 替换。
- `src/components/MockScenarioBar.tsx` 与 `src/mock/scenarios.ts` 是开发演示代码，B4 接入真实 API 后删除。
- 棋盘使用 CSS `aspect-ratio: 1 / 1`，尚未针对窄屏做棋盘尺寸上限优化。
- 未引入状态管理库；当前 `useState` 足够，后续如接入真实 API 再评估。

## 下一步

1. 与 Developer A 确认 FastAPI vertical slice 可调用后，实现 `apiAdapter`（复用同一 ViewModel）。
2. 用 OpenAPI 生成 TypeScript 类型，删除临时 `types.ts`。
3. 增加提交规则 / 推进回合的错误处理（revision conflict、幂等重试）。
4. 处理 Issue #42 的前端 CI（在 `web/` 进入 main 之后）。

## 下一位开发者必须先读

1. `docs/GAMEPLAY_FLOW_V0.2.md`
2. `docs/MVP_API_CONTRACT_V0.2.md`
3. `contracts/README.md`
4. `web/DEVELOPMENT_HANDOFF.md`
5. 最近 5 个 Git commits
