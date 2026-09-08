# Developer B Handoff

## 当前基线

- branch: `frontend/app-shell-v02`
- latest commit: 见 `git log -1`（本文件随每次 Developer B 提交同步更新）
- contract version: `mvp-v0.2`
- current task: B1 — 5×5 棋盘 + 红蓝状态面板

## 已完成

- B0：React + TypeScript + Vite 应用外壳，初始页《规则之外》+「开始游戏」。
- B1（数据层）：fixture 读取、临时 UI 契约类型、中文映射、事件展示、Mock Adapter、ViewModel、Mock 场景。
- B1（棋盘与状态）：5×5 棋盘、红蓝面板、顶部状态、战局升温、本回合结果与公开事件。

## 本次提交

### Commit

`PENDING`（提交后见 `git log -1`）

### 完成内容

- 棋盘按 `board.rows` / `board.cols` 渲染，不硬编码 5×5；公共 1-based 坐标只在渲染边界转 0-based。
- 红方 / 蓝方面板：生命值、当前策略、实际行动、当前有效属性。
- 顶部状态：已完成回合、规则制定次数、当前公共规则、战局升温。
- 本回合结果 + 公开事件（中文，未知事件安全 fallback）。
- Mock 场景切换条（8 个 V0.2 fixture）。

### 主要修改文件

- `web/src/components/Board.tsx`、`TeamPanel.tsx`、`TopStatusBar.tsx`、`EscalationPanel.tsx`、`EventList.tsx`、`RoundSummary.tsx`、`MockScenarioBar.tsx`、`GameScreen.tsx`
- `web/src/App.tsx`

### 验证

- `npm run typecheck` → PASS
- `npm run test` → PASS（本提交尚无测试文件）
- `npm run build` → PASS

## 当前可运行状态

```bash
cd web && npm install && npm run dev
```

- 初始页可进入游玩界面；顶部状态 + 红蓝面板 + 5×5 棋盘 + 本回合结果可渲染。
- 可通过顶部场景条切换 8 个 V0.2 fixture。
- 规则输入 / 提交 / 继续下一回合 / 终局 / 回放由下一提交接入。

## 尚未完成

- B1：规则输入 / 提交 / 继续下一回合 / accepted / rejected / terminal 控件。
- B3：Replay 页面接入。
- B1 测试。
- B4：真实 API 接入。

## 已知问题 / 技术债

- `web/src/contract/types.ts` 是临时手写类型，必须由 OpenAPI generated types 替换。
- `MockScenarioBar` 与 `web/src/mock/scenarios.ts` 是开发演示代码，B4 接入真实 API 后删除。

## 下一步

1. 接入规则输入 / 提交 / 继续下一回合与 accepted / rejected / terminal 状态。
2. 接入 Replay 页面。
3. 补充关键 UI 状态测试。

## 下一位开发者必须先读

1. `docs/GAMEPLAY_FLOW_V0.2.md`
2. `docs/MVP_API_CONTRACT_V0.2.md`
3. `contracts/README.md`
4. `web/DEVELOPMENT_HANDOFF.md`
5. 最近 5 个 Git commits
