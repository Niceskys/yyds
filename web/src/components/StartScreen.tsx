interface StartScreenProps {
  onStart: () => void;
}

export function StartScreen({ onStart }: StartScreenProps) {
  return (
    <main className="start-screen">
      <h1 className="start-screen__title">《规则之外》</h1>
      <p className="start-screen__subtitle">
        你无法直接指挥棋子，只能改写红蓝双方共同遵守的公共规则。
      </p>
      <p className="start-screen__hint">
        红方与蓝方会各自为了获胜行动，而你的目标是让这场战斗持续更久。
      </p>
      <button type="button" className="btn btn--primary" onClick={onStart}>
        开始游戏
      </button>
    </main>
  );
}
