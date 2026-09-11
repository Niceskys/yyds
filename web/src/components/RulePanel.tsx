import type {
  DecisionViewModel,
  GameErrorViewModel,
  RuleFeedbackViewModel,
} from '../contract/viewModel';

interface RulePanelProps {
  decision: DecisionViewModel;
  ruleText: string;
  onRuleTextChange: (value: string) => void;
  onSubmitRule: () => void;
  onAdvance: () => void;
  feedback: RuleFeedbackViewModel | null;
  error: GameErrorViewModel | null;
  notice: string | null;
  submittingRule?: boolean;
  advancing?: boolean;
}

/**
 * 规则输入 / 提交 / 继续下一回合。
 *
 * 业务可用性只来自 PlayerDecisionSnapshot；loading 只用于阻止同一 authoritative
 * revision 上发生并发 mutation，前端不推导游戏规则或自行推进 revision。
 */
export function RulePanel({
  decision,
  ruleText,
  onRuleTextChange,
  onSubmitRule,
  onAdvance,
  feedback,
  error,
  notice,
  submittingRule = false,
  advancing = false,
}: RulePanelProps) {
  const beforeFirstRound = decision.afterRound === null;
  const mutationPending = submittingRule || advancing;
  const inputDisabled = !decision.canSubmitRule || mutationPending;
  const submitDisabled =
    !decision.canSubmitRule || ruleText.trim().length === 0 || mutationPending;
  const advanceDisabled = !decision.canAdvance || mutationPending;
  const feedbackTone = feedback?.accepted
    ? 'accepted'
    : feedback?.code === 'MODEL_UNAVAILABLE'
      ? 'unavailable'
      : 'rejected';
  const feedbackMarker =
    feedbackTone === 'accepted' ? '✓' : feedbackTone === 'unavailable' ? '…' : '×';
  const feedbackGuidance = feedback?.accepted
    ? '规则已锁定；查看属性变化后，仍需点击“继续下一回合”。'
    : feedback?.code === 'MODEL_UNAVAILABLE'
      ? '本次没有修改公共规则；你可以保留原文稍后重试。'
      : '本次没有修改公共规则；请根据提示改写后重试。';

  let inputHint: string;
  if (beforeFirstRound) {
    inputHint = '第 1 回合开始前不能制定规则，请先观察一轮基线战斗。';
  } else if (decision.ruleChangedThisIntermission) {
    inputHint = '本回合间规则已生效，规则输入已锁定。你可以点击“继续下一回合”。';
  } else if (!decision.canSubmitRule) {
    inputHint = '当前阶段不能提交规则。';
  } else if (mutationPending) {
    inputHint = '正在等待游戏服务确认本次操作，请勿重复提交。';
  } else {
    inputHint = '你可以提交一条同时约束红蓝双方的公共规则，或直接继续下一回合。';
  }

  return (
    <section className="rule-panel">
      <h2 className="rule-panel__title">公共规则</h2>
      <label className="rule-panel__label" htmlFor="rule-input">
        规则内容
      </label>
      <textarea
        id="rule-input"
        data-testid="rule-input"
        className="rule-panel__input"
        rows={2}
        placeholder="例如：双方移动距离增加 1 格"
        value={ruleText}
        disabled={inputDisabled}
        onChange={(event) => onRuleTextChange(event.target.value)}
      />
      <p className="rule-panel__hint" data-testid="rule-input-hint">
        {inputHint}
      </p>
      <div className="rule-panel__actions">
        <button
          type="button"
          className="btn btn--primary"
          data-testid="submit-rule"
          disabled={submitDisabled}
          onClick={onSubmitRule}
        >
          {submittingRule ? '正在提交…' : '提交规则'}
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          data-testid="advance-round"
          disabled={advanceDisabled}
          onClick={onAdvance}
        >
          {advancing ? '正在结算…' : '继续下一回合'}
        </button>
      </div>

      {notice ? (
        <p className="rule-panel__notice" data-testid="game-notice">
          {notice}
        </p>
      ) : null}

      {feedback ? (
        <div
          className={`feedback feedback--${feedbackTone}`}
          data-testid="rule-feedback"
          data-feedback-tone={feedbackTone}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <div className="feedback__status-row">
            <span className="feedback__marker" aria-hidden="true">
              {feedbackMarker}
            </span>
            <p className="feedback__headline">{feedback.codeLabel}</p>
          </div>
          <p className="feedback__message">{feedback.message}</p>
          {feedback.acceptedRuleText ? (
            <p className="feedback__rule">已生效规则：{feedback.acceptedRuleText}</p>
          ) : null}
          {feedback.suggestedRephrase ? (
            <p className="feedback__suggest">
              可以试试这样说：{feedback.suggestedRephrase}
            </p>
          ) : null}
          {feedback.statChangeSummary.length > 0 ? (
            <ul className="feedback__stats" aria-label="公开属性变化">
              {feedback.statChangeSummary.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}
          <p className="feedback__guidance" data-testid="rule-feedback-guidance">
            {feedbackGuidance}
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="feedback feedback--error" data-testid="game-error">
          <p className="feedback__headline">操作未完成</p>
          <p className="feedback__message">{error.message}</p>
          {error.retryable ? (
            <p className="feedback__suggest">这是可恢复错误，可以使用同一次操作重试。</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
