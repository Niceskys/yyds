import type { MatchViewModel } from '../contract/viewModel';

interface ResultBannerProps {
  match: MatchViewModel;
  onRestart: () => void;
  onOpenReplay: (() => void) | null;
}

export function ResultBanner({ match, onRestart, onOpenReplay }: ResultBannerProps) {
  if (!match.resultLabel) return null;
  return (
    <section className="result-banner" data-testid="result-banner">
      <h2 className="result-banner__title">{match.resultLabel}</h2>
      <p className="result-banner__score">本局持续：{match.scoreRounds} 回合</p>
      <p className="result-banner__score">规则制定：{match.ruleChangeCount} 次</p>
      <div className="result-banner__actions">
        <button type="button" className="btn btn--primary" onClick={onRestart}>
          重新开始
        </button>
        {onOpenReplay ? (
          <button type="button" className="btn btn--secondary" onClick={onOpenReplay}>
            查看本局回放
          </button>
        ) : null}
      </div>
    </section>
  );
}
