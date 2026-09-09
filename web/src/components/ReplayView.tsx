import { useState } from 'react';
import { Board } from './Board';
import { EscalationPanel } from './EscalationPanel';
import { EventList } from './EventList';
import type {
  ActionViewModel,
  ReplayEntryViewModel,
  ReplayIntermissionEntryViewModel,
  ReplayRoundEntryViewModel,
  ReplayViewModel,
  RuleViewModel,
  TeamViewModel,
} from '../contract/viewModel';

interface ReplayViewProps {
  replay: ReplayViewModel;
  onBack: () => void;
}

function ruleLabel(rule: RuleViewModel | null): string {
  return rule?.playerText ?? '无';
}

function ReplayTeamCard({ team, action }: { team: TeamViewModel; action: ActionViewModel }) {
  return (
    <section className={`replay-team replay-team--${team.team.toLowerCase()}`}>
      <div className="replay-team__headline">
        <strong>{team.teamLabel}</strong>
        <span>生命值 {team.hp}</span>
      </div>
      <p>位置：{team.positionLabel}</p>
      <p>公开策略：{team.strategy?.label ?? '暂无公开策略'}</p>
      <p>实际行动：{action.summary}</p>
      <dl className="stats replay-team__stats">
        {team.stats.map((stat) => (
          <div className="stats__row" key={stat.key}>
            <dt className="stats__label">{stat.label}</dt>
            <dd className="stats__value">{stat.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function ReplayRoundDetail({ entry }: { entry: ReplayRoundEntryViewModel }) {
  return (
    <section className="replay__detail" data-testid="replay-selected-detail">
      <div className="replay__detail-head">
        <div>
          <span className="replay__entry-kind">回合</span>
          <h2>{entry.headline}</h2>
        </div>
        {entry.resultLabel ? <strong className="replay__result">{entry.resultLabel}</strong> : null}
      </div>

      <div className="replay__rule-card">
        <span>本回合公共规则</span>
        <strong>{ruleLabel(entry.activeRule)}</strong>
        {entry.activeRule?.effectSummary ? <small>{entry.activeRule.effectSummary}</small> : null}
      </div>

      <div className="replay__boards">
        <section className="replay__board-card">
          <h3>回合开始</h3>
          <p>
            红方 {entry.teamsBefore.RED.hp} HP · {entry.teamsBefore.RED.positionLabel}；蓝方{' '}
            {entry.teamsBefore.BLUE.hp} HP · {entry.teamsBefore.BLUE.positionLabel}
          </p>
          <Board board={entry.beforeBoard} />
        </section>
        <section className="replay__board-card">
          <h3>回合结束</h3>
          <p>
            红方 {entry.teamsAfter.RED.hp} HP · {entry.teamsAfter.RED.positionLabel}；蓝方{' '}
            {entry.teamsAfter.BLUE.hp} HP · {entry.teamsAfter.BLUE.positionLabel}
          </p>
          <Board board={entry.afterBoard} />
        </section>
      </div>

      <div className="replay__teams">
        <ReplayTeamCard team={entry.teamsAfter.RED} action={entry.actions.RED} />
        <ReplayTeamCard team={entry.teamsAfter.BLUE} action={entry.actions.BLUE} />
      </div>

      <section className="replay__events">
        <h3>本回合公开事件</h3>
        <EventList events={entry.events} emptyText="本回合没有公开战斗事件。" />
      </section>

      <EscalationPanel escalation={entry.escalation} />
    </section>
  );
}

function ReplayIntermissionDetail({
  entry,
}: {
  entry: ReplayIntermissionEntryViewModel;
}) {
  return (
    <section className="replay__detail" data-testid="replay-selected-detail">
      <div className="replay__detail-head">
        <div>
          <span className="replay__entry-kind">回合间</span>
          <h2>{entry.headline}</h2>
        </div>
      </div>

      <div className="replay__decision-grid">
        <div className="metric">
          <span className="metric__label">玩家选择</span>
          <span className="metric__value">{entry.choiceLabel}</span>
        </div>
        <div className="metric">
          <span className="metric__label">规则制定次数</span>
          <span className="metric__value">{entry.ruleChangeCountAfter}</span>
        </div>
        <div className="metric metric--wide">
          <span className="metric__label">公共规则变化</span>
          <span className="metric__value">
            {ruleLabel(entry.activeRuleBefore)} → {ruleLabel(entry.activeRuleAfter)}
          </span>
        </div>
      </div>

      {entry.submittedPlayerText ? (
        <div className="replay__rule-card">
          <span>玩家提交</span>
          <strong>{entry.submittedPlayerText}</strong>
          {entry.submissionResultLabel ? <small>提交结果：{entry.submissionResultLabel}</small> : null}
        </div>
      ) : (
        <p className="replay__empty">本次没有提交新规则，直接继续下一回合。</p>
      )}

      {entry.acceptedRule ? (
        <div className="replay__rule-card replay__rule-card--accepted">
          <span>本次生效规则</span>
          <strong>{entry.acceptedRule.playerText}</strong>
          {entry.acceptedRule.effectSummary ? <small>{entry.acceptedRule.effectSummary}</small> : null}
        </div>
      ) : null}
    </section>
  );
}

function ReplayDetail({ entry }: { entry: ReplayEntryViewModel }) {
  return entry.kind === 'ROUND' ? (
    <ReplayRoundDetail entry={entry} />
  ) : (
    <ReplayIntermissionDetail entry={entry} />
  );
}

/**
 * B3：按 authoritative ReplaySnapshot 逐节点浏览公开战局事实。
 * 不重新调用模型、不重新模拟 Engine，也不展示 chain-of-thought / private memory。
 */
export function ReplayView({ replay, onBack }: ReplayViewProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(replay.entries[0]?.key ?? null);
  const selectedEntry = replay.entries.find((entry) => entry.key === selectedKey) ?? replay.entries[0] ?? null;

  return (
    <main className="replay">
      <header className="replay__header">
        <div>
          <h1 className="replay__title">本局回放</h1>
          <p className="replay__summary">
            对局结果：{replay.terminalResultLabel ?? '未知'}　·　本局持续：{replay.scoreRounds} 回合
            　·　规则制定：{replay.ruleChangeCount} 次
          </p>
        </div>
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          返回对局
        </button>
      </header>

      <div className="replay__workspace">
        <nav className="replay__timeline-panel" aria-label="回放时间线">
          <h2>时间线</h2>
          <ol className="replay__timeline" data-testid="replay-timeline">
            {replay.entries.map((entry) => {
              const selected = entry.key === selectedEntry?.key;
              return (
                <li key={entry.key}>
                  <button
                    type="button"
                    className={`replay__entry${selected ? ' replay__entry--selected' : ''}`}
                    aria-pressed={selected}
                    onClick={() => setSelectedKey(entry.key)}
                  >
                    <span className="replay__entry-head">
                      <span className="replay__entry-kind">{entry.kindLabel}</span>
                      <span className="replay__entry-title">{entry.headline}</span>
                    </span>
                    <span className="replay__entry-preview">{entry.lines[0]}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        {selectedEntry ? (
          <ReplayDetail entry={selectedEntry} />
        ) : (
          <section className="replay__detail replay__empty">暂无可回放的公开时间线。</section>
        )}
      </div>
    </main>
  );
}
