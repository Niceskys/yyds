# Developer B Handoff

## 当前基线

- branch: `frontend/app-shell-v02`
- latest commit: 见 `git log -1`（本文件随每次 Developer B 提交同步更新）
- contract version: `mvp-v0.2`
- current task: B1 — fixture adapter + UI ViewModel

## 已完成

- B0：React + TypeScript + Vite 应用外壳，初始页《规则之外》+「开始游戏」。
- B1（数据层）：fixture 读取、临时 UI 契约类型、中文映射、事件展示、Mock Adapter、ViewModel、Mock 场景。

## 本次提交

### Commit

`PENDING`（提交后见 `git log -1`）

### 完成内容

- 建立 `contract fixture → adapter → UI ViewModel → React components` 数据流中的 adapter 层。
- 直接读取仓库 canonical `contracts/fixtures/mvp-v0.2/`，不在 web/ 复制第二套 fixture。
- 集中管理中文映射（策略 / 阵营 / 武器 / 结果 / 战局升温）。
- 有效属性使用白名单，`conflict_level` / `hard_liveness` 不进入 ViewModel 展示字段。
- 未知 `RoundEventPublicView.kind` 提供安全 fallback。
- 注册 8 个 V0.2 fixture 对应的 Mock 场景。

### 主要修改文件

- `web/src/contract/types.ts`（临时，待 OpenAPI 替换）
- `web/src/contract/labels.ts`、`eventLabels.ts`、`fixtures.ts`
- `web/src/contract/viewModel.ts`、`mockAdapter.ts`、`replayAdapter.ts`
- `web/src/mock/scenarios.ts`

### 验证

- `npm run typecheck` → PASS
- `npm run test` → PASS（本提交尚无测试文件）
- `npm run build` → PASS

## 当前可运行状态

```bash
cd web && npm install && npm run dev
```

- 初始页可进入游玩界面占位；数据层已可解析全部 8 个 V0.2 fixture。
- 棋盘 / 面板 / 规则输入由下一个提交接入。

## 尚未完成

- B1 UI：5×5 棋盘、红蓝面板、顶部状态、规则输入、终局与 Replay 组件。
- B1 测试。
- B4：真实 API 接入。

## 已知问题 / 技术债

- `web/src/contract/types.ts` 是临时手写类型，必须由 OpenAPI generated types 替换。
- 本提交只有数据层，UI 尚未消费。

## 下一步

1. 渲染 5×5 棋盘与红蓝状态面板。
2. 接入规则输入 / 提交 / 继续下一回合与终局状态。
3. 补充关键 UI 状态测试。

## 下一位开发者必须先读

1. `docs/GAMEPLAY_FLOW_V0.2.md`
2. `docs/MVP_API_CONTRACT_V0.2.md`
3. `contracts/README.md`
4. `web/DEVELOPMENT_HANDOFF.md`
5. 最近 5 个 Git commits
