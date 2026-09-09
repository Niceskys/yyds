import { MOCK_SCENARIOS } from '../mock/scenarios';
import type { ScenarioId } from '../mock/scenarios';

interface MockScenarioBarProps {
  current: ScenarioId;
  onSelect: (id: ScenarioId) => void;
  submissionMode: 'accepted' | 'rejected';
  onSubmissionModeChange: (mode: 'accepted' | 'rejected') => void;
}

/**
 * 开发演示用的 fixture 场景切换器（B4 接入真实 API 后移除）。
 * 让 B1 阶段能在没有后端的情况下覆盖全部关键 UI 状态。
 */
export function MockScenarioBar({
  current,
  onSelect,
  submissionMode,
  onSubmissionModeChange,
}: MockScenarioBarProps) {
  return (
    <div className="mock-bar" data-testid="mock-scenario-bar">
      <span className="mock-bar__title">开发演示数据（V0.2 fixture）</span>
      <div className="mock-bar__buttons">
        {MOCK_SCENARIOS.map((scenario) => (
          <button
            key={scenario.id}
            type="button"
            className={
              scenario.id === current
                ? 'chip chip--active'
                : 'chip'
            }
            title={`${scenario.description}（${scenario.fixture}）`}
            onClick={() => onSelect(scenario.id)}
          >
            {scenario.label}
          </button>
        ))}
      </div>
      <label className="mock-bar__mode">
        Mock 提交结果：
        <select
          value={submissionMode}
          onChange={(event) =>
            onSubmissionModeChange(event.target.value === 'rejected' ? 'rejected' : 'accepted')
          }
        >
          <option value="accepted">规则成功</option>
          <option value="rejected">规则被拒</option>
        </select>
      </label>
    </div>
  );
}
