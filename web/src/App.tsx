import { useMemo, useState } from 'react';
import { GameScreen } from './components/GameScreen';
import { MockScenarioBar } from './components/MockScenarioBar';
import { ReplayView } from './components/ReplayView';
import { StartScreen } from './components/StartScreen';
import { loadReplay } from './contract/fixtures';
import { buildReplayViewModel } from './contract/replayAdapter';
import { buildScenarioState } from './mock/scenarios';
import type { ScenarioId } from './mock/scenarios';

type Screen = 'start' | 'game' | 'replay';
type SubmissionMode = 'accepted' | 'rejected';

/** 仅开发模式附加内部原始值；生产构建不显示。 */
const DEBUG = import.meta.env.DEV;

export function App() {
  const [screen, setScreen] = useState<Screen>('start');
  const [scenario, setScenario] = useState<ScenarioId>('player_decision');
  const [submissionMode, setSubmissionMode] = useState<SubmissionMode>('accepted');
  const [ruleText, setRuleText] = useState('');
  const [mockNotice, setMockNotice] = useState<string | null>(null);

  const state = useMemo(() => buildScenarioState(scenario, DEBUG), [scenario]);
  const replay = useMemo(
    () => state.replay ?? buildReplayViewModel(loadReplay(), DEBUG),
    [state.replay],
  );

  const handleStart = () => {
    // 产品流程：创建对局 → 第 1 回合自动执行 → 进入玩家决策阶段。
    // Mock 阶段直接展示“第 1 回合已结算”的 PLAYER_DECISION fixture。
    setScenario('player_decision');
    setRuleText('');
    setMockNotice(null);
    setScreen('game');
  };

  const handleSelectScenario = (id: ScenarioId) => {
    setScenario(id);
    setRuleText('');
    setMockNotice(null);
    setScreen('game');
  };

  const handleSubmitRule = () => {
    if (!state.match.decision.canSubmitRule) return;
    setScenario(submissionMode === 'accepted' ? 'rule_accepted' : 'rule_rejected');
    setMockNotice(
      'Mock 模式：已用对应 fixture 模拟规则提交结果，B4 接入真实 API 后改为调用规则接口。',
    );
  };

  const handleAdvance = () => {
    if (!state.match.decision.canAdvance) return;
    setScenario('advance_round');
    setMockNotice(
      'Mock 模式：已模拟推进一个完整回合，B4 接入真实 API 后改为调用推进接口。',
    );
  };

  const handleRestart = () => {
    setScenario('player_decision');
    setRuleText('');
    setMockNotice(null);
    setScreen('start');
  };

  const openReplay = state.match.resultLabel ? () => setScreen('replay') : null;

  if (screen === 'start') {
    return (
      <div className="app">
        <StartScreen onStart={handleStart} />
      </div>
    );
  }

  if (screen === 'replay') {
    return (
      <div className="app">
        <ReplayView replay={replay} onBack={() => setScreen('game')} />
      </div>
    );
  }

  return (
    <div className="app">
      <GameScreen
        match={state.match}
        lastRound={state.lastRound}
        feedback={state.feedback}
        error={state.error}
        mockNotice={mockNotice}
        ruleText={ruleText}
        onRuleTextChange={setRuleText}
        onSubmitRule={handleSubmitRule}
        onAdvance={handleAdvance}
        onRestart={handleRestart}
        onOpenReplay={openReplay}
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
