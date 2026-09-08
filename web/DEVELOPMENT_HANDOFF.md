# Developer B Handoff

## 当前基线

- branch: `frontend/app-shell-v02`
- latest commit: 见 `git log -1`（本文件随每次 Developer B 提交同步更新）
- contract version: `mvp-v0.2`
- current task: B1 — 规则输入 / 终局 / Replay 接入

## 已完成

- B0：React + TypeScript + Vite 应用外壳，初始页《规则之外》+「开始游戏」。
- B1（数据层）：fixture 读取、临时 UI 契约类型、中文映射、事件展示、Mock Adapter、ViewModel、Mock 场景。
- B1（棋盘与状态）：5×5 棋盘、红蓝面板、顶部状态、战局升温、本回合结果与公开事件。
- B1（交互）：规则输入 / 提交 / 继续下一回合，accepted / rejected / terminal 状态。
- B3（基础）：Replay 时间线页面。

## 本次提交

### Commit

`PENDING`（提交后见 `git log -1`）

### 完成内容

- 规则输入 / 提交 / 继续下一回合按钮状态严格来自 `PlayerDecisionSnapshot`。
- accepted：锁定规则输入，仍可继续下一回合；rejected：允许修改后重试，不增加规则制定次数。
- terminal：禁止提交与推进，显示玩家成绩（本局持续回合数 / 规则制定次数）。
- Replay 页面按 `ROUND → INTERMISSION → ROUND` 顺序渲染，第一条是第 1 回合。
- 不展示 chain-of-thought / private memory / provider 原始错误 / 内部字段名。

### 主要修改文件

- `web/src/components/RulePanel.tsx`、`ResultBanner.tsx`、`ReplayView.tsx`、`GameScreen.tsx`
- `web/src/App.tsx`

### 验证

- `npm run typecheck` → PASS
- `npm run test` → PASS（本提交尚无测试文件）
- `npm run build` → PASS

## 当前可运行状态

```bash
cd web && npm install && npm run dev
```

- 初始页 → 游玩界面；顶部状态 + 红蓝面板 + 5×5 棋盘 + 本回合结果 + 规则输入。
- 顶部「开发演示数据（V0.2 fixture）」可切换 8 个场景。
- Mock 提交结果可在「规则成功 / 规则被拒」之间切换；提交与继续只切换本地 fixture 并显示 Mock 提示。
- 终局可进入「本局回放」。

## 尚未完成

- B1 测试（下一个提交）。
- B2 收尾：接入真实 API 后需带 `expected_revision` 与 `Idempotency-Key`。
- B4：真实 API Adapter + OpenAPI generated types。
- 前端 CI（Issue #42）：等 `web/` 进入 main 后再处理。

## 已知问题 / 技术债

- `web/src/contract/types.ts` 是临时手写类型，必须由 OpenAPI generated types 替换。
- `MockScenarioBar` 与 `web/src/mock/scenarios.ts` 是开发演示代码，B4 接入真实 API 后删除。
- 棋盘使用 CSS `aspect-ratio: 1 / 1`，窄屏棋盘尺寸尚未做上限优化。

## 下一步

1. 补充关键 UI 状态测试。
2. 与 Developer A 确认 FastAPI vertical slice 可调用后，实现 `apiAdapter`。
3. 用 OpenAPI 生成 TypeScript 类型，删除临时 `types.ts`。

## 下一位开发者必须先读

1. `docs/GAMEPLAY_FLOW_V0.2.md`
2. `docs/MVP_API_CONTRACT_V0.2.md`
3. `contracts/README.md`
4. `web/DEVELOPMENT_HANDOFF.md`
5. 最近 5 个 Git commits
