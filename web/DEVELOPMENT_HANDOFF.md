# Developer B Handoff

## 当前基线

- branch: `frontend/app-shell-v02`
- latest commit: 见 `git log -1`（本文件随每次 Developer B 提交同步更新）
- contract version: `mvp-v0.2`
- current task: B0 — React/Vite App Shell

## 已完成

- B0：React + TypeScript + Vite 应用外壳（TypeScript strict）。
- 初始页《规则之外》+「开始游戏」，无登录/注册/排行榜/商店/设置。
- `npm run dev / typecheck / test / build` 脚本。
- vitest + @testing-library 配置（本提交尚无测试用例）。

## 本次提交

### Commit

`PENDING`（提交后见 `git log -1`）

### 完成内容

- 建立 `web/` Vite + React + TS 工程。
- 初始页与「开始游戏」页面切换（游玩界面为 B1 占位）。

### 主要修改文件

- `web/package.json`、`web/tsconfig.json`、`web/vite.config.ts`、`web/index.html`
- `web/src/main.tsx`、`web/src/App.tsx`、`web/src/components/StartScreen.tsx`、`web/src/styles/app.css`
- `web/README.md`、`web/DEVELOPMENT_HANDOFF.md`

### 验证

- `npm run typecheck` → PASS
- `npm run test` → PASS（本提交尚无测试文件）
- `npm run build` → PASS

## 当前可运行状态

```bash
cd web && npm install && npm run dev
```

- 初始页显示《规则之外》与「开始游戏」。
- 点击「开始游戏」进入游玩界面占位（棋盘 / 红蓝面板由下一个 B1 提交填充）。

## 尚未完成

- B1：fixture adapter、5×5 棋盘、红蓝面板、规则输入、终局与 Replay。
- B4：真实 API 接入（等 Developer A 的 FastAPI vertical slice）。
- 前端 CI（Issue #42）：等 `web/` 进入 main 后再处理。

## 已知问题 / 技术债

- 游玩界面当前只是占位，不具备 B1 功能。
- 本提交不包含任何测试用例。

## 下一步

1. 增加 fixture 读取 + mock adapter + UI ViewModel 层。
2. 渲染 5×5 棋盘与红蓝状态面板。
3. 接入规则输入 / 提交 / 继续下一回合与终局状态。

## 下一位开发者必须先读

1. `docs/GAMEPLAY_FLOW_V0.2.md`
2. `docs/MVP_API_CONTRACT_V0.2.md`
3. `contracts/README.md`
4. `web/DEVELOPMENT_HANDOFF.md`
5. 最近 5 个 Git commits
