import type { GameErrorViewModel } from '../contract/viewModel';

interface StartScreenProps {
  onStart: () => void;
  loading?: boolean;
  error?: GameErrorViewModel | null;
}

export function StartScreen({ onStart, loading = false, error = null }: StartScreenProps) {
  return (
    <main className="start-screen">
      <h1 className="start-screen__title">《规则之外》</h1>
      <p className="start-screen__subtitle">
        你无法直接指挥棋子，只能改写红蓝双方共同遵守的公共规则。
      </p>
      <p className="start-screen__hint">
        红方与蓝方会各自为了获胜行动，而你的目标是让这场战斗持续更久。
      </p>
      <button
        type="button"
        className="btn btn--primary"
        onClick={onStart}
        disabled={loading}
      >
        {loading ? '正在创建对局…' : '开始游戏'}
      </button>
      {error ? (
        <div className="feedback feedback--error" data-testid="start-error">
          <p className="feedback__headline">暂时无法开始</p>
          <p className="feedback__message">{error.message}</p>
          {error.retryable ? (
            <p className="feedback__suggest">可以稍后再次点击“开始游戏”。</p>
          ) : null}
        </div>
      ) : null}
    </main>
  );
}
