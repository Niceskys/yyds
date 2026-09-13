import type { ActionViewModel, TeamViewModel } from '../contract/viewModel';

interface TeamPanelProps {
  team: TeamViewModel;
  action: ActionViewModel | null;
  settling?: boolean;
}

export function TeamPanel({ team, action, settling = false }: TeamPanelProps) {
  const strategy = team.strategy;
  return (
    <section
      className={`team-panel team-panel--${team.team.toLowerCase()}${settling ? ' team-panel--settling' : ''}`}
      aria-label={team.teamLabel}
    >
      <header className="team-panel__header">
        <h2 className="team-panel__title">{team.teamLabel}</h2>
        <span className="team-panel__hp" data-testid={`hp-${team.team}`}>
          生命值 {team.hp}
        </span>
      </header>
      <p className="team-panel__position">{team.positionLabel}</p>

      <div className="team-panel__block">
        <h3 className="team-panel__label">当前策略</h3>
        {strategy ? (
          <ul className="team-panel__strategy">
            <li className="team-panel__strategy-main">
              {strategy.label}
              {strategy.degraded ? '（已回退）' : ''}
            </li>
            {strategy.degraded && strategy.statusLabel ? (
              <li>策略状态：{strategy.statusLabel}</li>
            ) : null}
            {strategy.shortTermGoalLabel ? (
              <li>本回合目标：{strategy.shortTermGoalLabel}</li>
            ) : null}
            {strategy.weaponPreferenceLabel ? (
              <li>武器倾向：{strategy.weaponPreferenceLabel}</li>
            ) : null}
            {strategy.riskBudgetLabel ? (
              <li>风险倾向：{strategy.riskBudgetLabel}</li>
            ) : null}
            {strategy.targetDistance !== null ? (
              <li>目标距离：{strategy.targetDistance} 格</li>
            ) : null}
            {strategy.debugRaw ? (
              <li className="debug-raw">调试：{strategy.debugRaw}</li>
            ) : null}
          </ul>
        ) : (
          <p className="team-panel__empty">暂无公开策略</p>
        )}
      </div>

      <div className="team-panel__block">
        <h3 className="team-panel__label">实际行动</h3>
        <p className="team-panel__action" data-testid={`action-${team.team}`}>
          {action ? action.summary : '本回合尚未产生公开行动'}
        </p>
      </div>

      <div className="team-panel__block">
        <h3 className="team-panel__label">当前有效属性</h3>
        <dl className="stats" data-testid={`stats-${team.team}`}>
          {team.stats.map((stat) => (
            <div className="stats__row" key={stat.key}>
              <dt className="stats__label">{stat.label}</dt>
              <dd className="stats__value">{stat.value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
