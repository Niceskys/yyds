# 《规则之外》前端（Developer B）

React + TypeScript + Vite。B0–B4 与 M1 已完成，正式 runtime 已接入 FastAPI V0.2；B5A.1–B5A.3 因果反馈已合并，当前剩余 Replay before/after 过渡。

## 当前状态

```text
B0 React/Vite App Shell                  DONE
B1 fixture-driven product UI             DONE
B3 Replay UI                             DONE
OpenAPI generated TypeScript + API seam  DONE
B4 real HTTP frontend integration        DONE — PR #61
M1 Integrated Playable Acceptance        PASSED — Issue #64
B5A.1 round causal transition            DONE — Issue #63
B5A.2 rule causal feedback               DONE — Issue #63
B5A.3 escalation change feedback         DONE — Issue #63
B5A Replay before/after transition       REMAINING — Issue #63
```

B5A 只改善 authoritative 状态变化的可读性，不改变 Engine、Planner、Rule DSL、revision/idempotency 或 public contract。

## 开发

```bash
cd web
npm install
npm run dev        # http://localhost:5173
npm run typecheck  # tsc --noEmit
npm run test       # vitest run
npm run build      # tsc --noEmit && vite build
```

真实 HTTP 模式还需要启动仓库中的 FastAPI 服务。首次试玩优先使用根目录 [`scripts/start-local-playtest.ps1`](../scripts/start-local-playtest.ps1)；完整说明见 [`docs/PLAYTEST_QUICKSTART.md`](../docs/PLAYTEST_QUICKSTART.md)。开发任务边界仍以根目录 `AI_DEVELOPER_START_HERE.md`、`docs/MVP_NEXT_MILESTONE_2026-09-10.md` 和本目录 `DEVELOPMENT_HANDOFF.md` 为准。

## 正式数据流

```text
FastAPI V0.2
  → HttpMatchApiAdapter
  → generated OpenAPI TypeScript DTO aliases
  → UI ViewModel
  → React components
```

Canonical contract 来源：

```text
src/rules_beyond/api_contract.py
  → contracts/openapi/mvp-v0.2.json
  → web/src/contract/generated/api.ts
```

前端不得复制或手写第二套正式 API schema。

## Fixture / Mock 的用途

仓库仍保留：

```text
contracts/fixtures/mvp-v0.2/
web/src/mock/
```

它们用于测试、回归和离线 UI 场景覆盖，不再是正式 runtime 的默认数据源。不得把保留 mock 理解为 B4 尚未完成。

## 边界

- 前端不计算规则合法性、命中率、有效属性、战局升温等级或终局结果；
- 按钮状态只来自 `PlayerDecisionSnapshot`；
- authoritative revision、position、HP、result 和 Replay 均以服务端响应为准；
- 普通玩家 UI 不展示 `conflict_level` / `hard_liveness` 等内部字段名；
- 不展示 chain-of-thought、private memory、provider 原始错误、API key 或 stack；
- 409 revision conflict 先重新获取权威 snapshot，不自动重放旧 mutation；
- 同一次未知结果重试复用原 Idempotency-Key；
- accepted 规则后不自动推进，玩家仍需点击“继续下一回合”。

## 当前任务边界

M1 只验证真实可玩闭环和异常恢复，可以修复验收中发现的 integration bug，但不做复杂动效重构。

后续核心因果反馈动画已记录在 [Issue #63](https://github.com/Niceskys/yyds/issues/63)：

- 回合移动、攻击、命中/未命中和生命值变化；
- 规则 accepted/rejected/MODEL_UNAVAILABLE 的反馈；
- 战局升温提示；
- Replay before/after 过渡；
- `prefers-reduced-motion` 与防重复 mutation 测试。

## 目录

```text
src/api/          正式 HTTP adapter / runtime seam
src/contract/     generated DTO aliases、adapter、ViewModel、中文映射
src/mock/         Mock 场景与回归支持
src/components/   展示组件
src/__tests__/    关键 UI、contract、runtime 状态测试
```

开发上下文与交接记录见 [`DEVELOPMENT_HANDOFF.md`](./DEVELOPMENT_HANDOFF.md)。
