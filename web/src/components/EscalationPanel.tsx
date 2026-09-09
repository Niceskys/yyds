import type { EscalationViewModel } from '../contract/viewModel';

interface EscalationPanelProps {
  escalation: EscalationViewModel;
}

/**
 * 战局升温。
 * 只展示后端给出的 level / no_damage_streak / rounds_until_next_level，
 * 不在前端重新计算等级，也不展示 hard_liveness / conflict_level 字段名。
 */
export function EscalationPanel({ escalation }: EscalationPanelProps) {
  return (
    <div className="escalation" data-testid="escalation">
      <span className="escalation__title">战局升温</span>
      <span className="escalation__level">{escalation.levelLabel}</span>
      <span className="escalation__streak">
        连续无伤害：{escalation.noDamageStreak} 回合
      </span>
      <span className="escalation__hint">{escalation.hint}</span>
    </div>
  );
}
