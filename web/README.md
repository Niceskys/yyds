# 《规则之外》前端（Developer B）

React + TypeScript + Vite。当前阶段：**B1（fixture 驱动的 Mock UI）**，尚未接入真实后端。

## 开发

```bash
cd web
npm install
npm run dev        # http://localhost:5173
npm run typecheck  # tsc --noEmit
npm run test       # vitest run
npm run build      # tsc --noEmit && vite build
```

## 数据来源

UI 直接读取仓库内 canonical fixture：

```text
contracts/fixtures/mvp-v0.2/
```

不在 `web/` 内复制第二套 fixture 或第二套 API schema。数据流：

```text
contract fixture
  → mock adapter（src/contract/mockAdapter.ts）
  → UI ViewModel（src/contract/viewModel.ts）
  → React components
```

B4 接入真实 API 时，只需把 `mock adapter` 替换为 `API adapter`，并改用
`src/rules_beyond/api_contract.py` 生成的 OpenAPI TypeScript 类型。

## 边界

- 前端不计算规则合法性、命中率、有效属性、战局升温等级或终局结果；
- 按钮状态只来自 `PlayerDecisionSnapshot`；
- 普通玩家 UI 不展示 `conflict_level` / `hard_liveness` / `BattleEscalationSnapshot` 等内部字段名；
- 不展示 chain-of-thought、private memory、provider 原始错误。

## 目录

```text
src/contract/     类型（临时）、fixture 读取、中文映射、adapter、ViewModel
src/mock/         Mock 场景（对应 8 个 V0.2 fixture）
src/components/   展示组件（纯 props 驱动）
src/__tests__/    关键 UI 状态测试
```

开发上下文与交接记录见 [`DEVELOPMENT_HANDOFF.md`](./DEVELOPMENT_HANDOFF.md)。
