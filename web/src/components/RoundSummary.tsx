import { EventList } from './EventList';
import type { RoundViewModel } from '../contract/viewModel';

interface RoundSummaryProps {
  round: RoundViewModel | null;
}

export function RoundSummary({ round }: RoundSummaryProps) {
  if (!round) {
    return (
      <section className="round-summary">
        <h2 className="round-summary__title">本回合结果</h2>
        <p className="round-summary__empty">等待第一个回合结算。</p>
      </section>
    );
  }
  return (
    <section className="round-summary" data-testid="round-summary">
      <h2 className="round-summary__title">第 {round.roundNo} 回合结果</h2>
      <div className="round-summary__grid">
        <div>
          <h3 className="round-summary__label">公开策略</h3>
          <p>红方：{round.strategies.RED?.label ?? '暂无公开策略'}</p>
          <p>蓝方：{round.strategies.BLUE?.label ?? '暂无公开策略'}</p>
        </div>
        <div>
          <h3 className="round-summary__label">实际行动</h3>
          <p>红方：{round.actions.RED.summary}</p>
          <p>蓝方：{round.actions.BLUE.summary}</p>
        </div>
      </div>
      <h3 className="round-summary__label">公开事件</h3>
      <EventList events={round.events} emptyText="本回合没有公开战斗事件。" />
      {round.resultLabel ? (
        <p className="round-summary__result">对局结果：{round.resultLabel}</p>
      ) : null}
    </section>
  );
}
