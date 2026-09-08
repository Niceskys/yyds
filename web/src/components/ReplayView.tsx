import type { ReplayViewModel } from '../contract/viewModel';

interface ReplayViewProps {
  replay: ReplayViewModel;
  onBack: () => void;
}

/**
 * B3 基础结构：按后端给出的时间线顺序展示公开信息。
 * 不重新调用模型，不展示 chain-of-thought / private memory。
 */
export function ReplayView({ replay, onBack }: ReplayViewProps) {
  return (
    <main className="replay">
      <header className="replay__header">
        <h1 className="replay__title">本局回放</h1>
        <button type="button" className="btn btn--secondary" onClick={onBack}>
          返回对局
        </button>
      </header>
      <p className="replay__summary">
        对局结果：{replay.terminalResultLabel ?? '未知'}　·　本局持续：{replay.scoreRounds} 回合
        　·　规则制定：{replay.ruleChangeCount} 次
      </p>
      <ol className="replay__timeline" data-testid="replay-timeline">
        {replay.entries.map((entry) => (
          <li className="replay__entry" key={entry.key} data-kind={entry.kindLabel}>
            <div className="replay__entry-head">
              <span className="replay__entry-kind">{entry.kindLabel}</span>
              <span className="replay__entry-title">{entry.headline}</span>
            </div>
            <ul className="replay__lines">
              {entry.lines.map((line, index) => (
                <li key={`${entry.key}-${index}`}>{line}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </main>
  );
}
