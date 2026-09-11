import type { EscalationViewModel } from '../contract/viewModel';

interface EscalationPanelProps {
  escalation: EscalationViewModel;
  previous?: EscalationViewModel | null;
}

/**
 * 战局升温。
 * 只展示后端给出的 level / no_damage_streak / rounds_until_next_level，
 * 不在前端重新计算等级，也不展示 hard_liveness / conflict_level 字段名。
 */
export function EscalationPanel({ escalation, previous = null }: EscalationPanelProps) {
  const levelChanged = previous !== null && previous.level !== escalation.level;
  const streakChanged =
    previous !== null && previous.noDamageStreak !== escalation.noDamageStreak;
  const changed = levelChanged || streakChanged;
  const className = [
    'escalation',
    changed ? 'escalation--changed' : '',
    levelChanged ? 'escalation--level-changed' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={className}
      data-testid="escalation"
      data-level={escalation.level}
      data-changed={changed ? 'true' : 'false'}
    >
      <div className="escalation__summary">
        <span className="escalation__title">战局升温</span>
        <span className="escalation__level">{escalation.levelLabel}</span>
        <span className="escalation__streak">
          连续无伤害：{escalation.noDamageStreak} 回合
        </span>
      </div>
      <span className="escalation__hint">{escalation.hint}</span>
      {changed && previous ? (
        <p
          className="escalation__change"
          data-testid="escalation-change"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <strong>{levelChanged ? '升温等级发生变化' : '升温进度发生变化'}</strong>
          <span>
            等级 {previous.levelLabel} → {escalation.levelLabel}；连续无伤害{' '}
            {previous.noDamageStreak} → {escalation.noDamageStreak} 回合
          </span>
        </p>
      ) : null}
    </div>
  );
}
