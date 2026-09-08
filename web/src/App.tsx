import { useMemo, useState } from 'react';
import { GameScreen } from './components/GameScreen';
import { MockScenarioBar } from './components/MockScenarioBar';
import { StartScreen } from './components/StartScreen';
import { buildScenarioState } from './mock/scenarios';
import type { ScenarioId } from './mock/scenarios';

type Screen = 'start' | 'game';

/** 仅开发模式附加内部原始值；生产构建不显示。 */
const DEBUG = import.meta.env.DEV;

export function App() {
  const [screen, setScreen] = useState<Screen>('start');
  const [scenario, setScenario] = useState<ScenarioId>('player_decision');
  const [submissionMode, setSubmissionMode] = useState<'accepted' | 'rejected'>('accepted');

  const state = useMemo(() => buildScenarioState(scenario, DEBUG), [scenario]);

  const handleStart = () => {
    // 产品流程：创建对局 → 第 1 回合自动执行 → 进入玩家决策阶段。
    // Mock 阶段直接展示“第 1 回合已结算”的 PLAYER_DECISION fixture。
    setScenario('player_decision');
    setScreen('game');
  };

  const handleSelectScenario = (id: ScenarioId) => {
    setScenario(id);
    setScreen('game');
  };

  if (screen === 'start') {
    return (
      <div className="app">
        <StartScreen onStart={handleStart} />
      </div>
    );
  }

  return (
    <div className="app">
      <GameScreen
        match={state.match}
        lastRound={state.lastRound}
        mockBar={
          <MockScenarioBar
            current={scenario}
            onSelect={handleSelectScenario}
            submissionMode={submissionMode}
            onSubmissionModeChange={setSubmissionMode}
          />
        }
      />
    </div>
  );
}
