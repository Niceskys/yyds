import type { TeamId } from '../contract/types';
import type { RoundTransitionViewModel, TeamViewModel } from '../contract/viewModel';

interface RoundTransitionProps {
  transition: RoundTransitionViewModel;
}

function positionChange(before: TeamViewModel, after: TeamViewModel): string {
  if (before.position.row === after.position.row && before.position.col === after.position.col) {
    return `位置保持在 ${after.positionLabel}`;
  }
  return `${before.positionLabel} → ${after.positionLabel}`;
}

function hpChange(before: TeamViewModel, after: TeamViewModel): string {
  const delta = after.hp - before.hp;
  if (delta === 0) return `生命值保持 ${after.hp}`;
  const signedDelta = delta > 0 ? `+${delta}` : `${delta}`;
  return `生命值 ${before.hp} → ${after.hp}（${signedDelta}）`;
}

function TeamTransition({
  team,
  transition,
}: {
  team: TeamId;
  transition: RoundTransitionViewModel;
}) {
  const before = transition.before.teams[team];
  const after = transition.after.teams[team];
  const action = transition.round.actions[team];
  return (
    <article className={`round-transition__team round-transition__team--${team.toLowerCase()}`}>
      <h3>{after.teamLabel}</h3>
      <p className="round-transition__action">{action.summary}</p>
      <p>{positionChange(before, after)}</p>
      <p className={before.hp === after.hp ? '' : 'round-transition__hp-change'}>
        {hpChange(before, after)}
      </p>
    </article>
  );
}

/**
 * 只比较 advance 前后两份公开 authoritative snapshot，不推导伤害、命中或结算顺序。
 * 动画顺序是阅读提示，不代表 Engine 行动优先级。
 */
export function RoundTransition({ transition }: RoundTransitionProps) {
  return (
    <section
      className="round-transition"
      data-testid="round-transition"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="round-transition__header">
        <div>
          <span className="round-transition__eyebrow">权威回合结算</span>
          <h2>第 {transition.round.roundNo} 回合发生了什么</h2>
        </div>
        <ol className="round-transition__stages" aria-label="回合演出阶段">
          <li>公开行动</li>
          <li>战斗事件</li>
          <li>权威状态</li>
        </ol>
      </div>
      <div className="round-transition__teams">
        <TeamTransition team="RED" transition={transition} />
        <TeamTransition team="BLUE" transition={transition} />
      </div>
      <p className="round-transition__footnote">
        画面正在呈现服务端返回结果；演出顺序不代表行动优先级。
      </p>
    </section>
  );
}
