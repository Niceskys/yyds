import { EscalationPanel } from './EscalationPanel';
import type { MatchViewModel } from '../contract/viewModel';

interface TopStatusBarProps {
  match: MatchViewModel;
  onOpenReplay: (() => void) | null;
}

/**
 * 顶部状态区。
 * 已完成回合、规则制定次数、当前公共规则、战局升温全部直接读取后端字段，
 * 前端不做任何推断。
 */
export function TopStatusBar({ match, onOpenReplay }: TopStatusBarProps) {
  const activeRuleText = match.activeRule
    ? match.activeRule.playerText
    : '暂无（本局尚未制定规则）';
  const roundHint =
    match.lifecycle === 'PLAYER_DECISION'
      ? `已完成第 ${match.completedRounds} 回合，等待你的决策`
      : match.lifecycle === 'RUNNING'
        ? `第 ${match.roundNo} 回合进行中`
        : `已完成 ${match.completedRounds} 回合`;

  return (
    <header className="top-status">
      <div className="top-status__headline">
        <h1 className="top-status__title">《规则之外》</h1>
        <span className="top-status__lifecycle" data-testid="lifecycle">
          {match.lifecycleLabel}
        </span>
      </div>
      <div className="top-status__metrics">
        <div className="metric">
          <span className="metric__label">对局进度</span>
          <span className="metric__value">{roundHint}</span>
        </div>
        <div className="metric" data-testid="completed-rounds">
          <span className="metric__label">已完成回合</span>
          <span className="metric__value">{match.completedRounds}</span>
        </div>
        <div className="metric" data-testid="rule-change-count">
          <span className="metric__label">规则制定次数</span>
          <span className="metric__value">{match.ruleChangeCount}</span>
        </div>
        <div className="metric metric--wide" data-testid="active-rule">
          <span className="metric__label">当前公共规则</span>
          <span className="metric__value">{activeRuleText}</span>
        </div>
      </div>
      <EscalationPanel escalation={match.escalation} />
      {onOpenReplay ? (
        <button type="button" className="btn btn--ghost" onClick={onOpenReplay}>
          查看本局回放
        </button>
      ) : null}
      {match.debugRaw ? <p className="debug-raw">调试：{match.debugRaw}</p> : null}
    </header>
  );
}
