# B5A Core Causal-feedback Motion Acceptance — 2026-09-12

状态：**COMPLETE / UI PRESENTATION GATE PASSED**  
跟踪 Issue：[#63](https://github.com/Niceskys/yyds/issues/63)

## 交付范围

B5A 以四个独立前端增量完成：

| 增量 | PR | 结果 |
|---|---:|---|
| B5A.1 回合因果过渡 | #67 | 使用 advance 前后 authoritative snapshot 展示公开行动、位置与 HP 变化 |
| B5A.2 规则结果反馈 | #68 | 区分 accepted、rejected、MODEL_UNAVAILABLE，并展示 accepted 后公开属性变化 |
| B5A.3 战局升温反馈 | #69 | authoritative escalation 变化提示与 reduced-motion 兼容 |
| B5A.4 Replay 过渡 | #71 | 时间线节点方向过渡、明确前后节点、快速选择以最后节点为准 |

四个增量均限于前端表现层。没有修改 Engine、Planner、Rule DSL、revision / idempotency 或 public contract。

## Replay 最终验证

PR #71 merge：`0aed04097a9b25baa9caa25ce4b461823f6cd0ae`

自动化：

```text
npm.cmd run contract:check             PASS
npm.cmd run typecheck                  PASS
npm.cmd run test -- --reporter=dot     PASS — 7 files / 54 tests
npm.cmd run build                      PASS — 49 modules
GitHub frontend workflow               PASS — run #36
GitHub tests workflow                  PASS — run #194
```

真实 Chromium 使用 canonical `replay_terminal.json` 经现有 Replay Adapter / ViewModel / React 路径验证：

- 相邻节点显示明确的前一节点 → 当前节点关系；
- 正向切换计算样式为 `replay-detail-forward`；
- 快速连续选择后最终选中并完整呈现最后一次 authoritative 节点；
- `prefers-reduced-motion: reduce` 下计算样式为 `animation-name: none`；
- 最终页面仍展示 ReplaySnapshot 中的回合、规则、行动和结果，不构造中间战局事实。

## Gate 结论

```text
ROUND_CAUSAL_FEEDBACK = PASS
RULE_OUTCOME_FEEDBACK = PASS
ESCALATION_FEEDBACK = PASS
REPLAY_TRANSITION = PASS
REDUCED_MOTION = PASS
AUTHORITATIVE_FINAL_STATE = PASS
FRONTEND_CI = PASS
UI_PRESENTATION_GATE = PASSED
```

B5A 完成后，下一阶段是冻结 M2 Agent A/B/C 实验设计。M2 实现仍需新的任务 Issue，并遵守 `DEVELOPER_A_GATE.md`；本 Gate 不自动解锁 Developer A。
