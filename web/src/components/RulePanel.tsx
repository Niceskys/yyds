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
  mockNotice: string | null;
}

/**
 * 规则输入 / 提交 / 继续下一回合。
 *
 * 按钮状态只来自 PlayerDecisionSnapshot：
 * can_submit_rule / rule_changed_this_intermission / can_advance。
 * 前端不根据 completed_rounds / lifecycle / rule_change_count 自行推理。
 */
export function RulePanel({
  decision,
  ruleText,
  onRuleTextChange,
  onSubmitRule,
  onAdvance,
  feedback,
  error,
  mockNotice,
}: RulePanelProps) {
  const beforeFirstRound = decision.afterRound === null;
  const inputDisabled = !decision.canSubmitRule;
  const submitDisabled = !decision.canSubmitRule || ruleText.trim().length === 0;

  let inputHint: string;
  if (beforeFirstRound) {
    inputHint = '第 1 回合开始前不能制定规则，请先观察一轮基线战斗。';
  } else if (decision.ruleChangedThisIntermission) {
    inputHint = '本回合间规则已生效，规则输入已锁定。你可以点击“继续下一回合”。';
  } else if (!decision.canSubmitRule) {
    inputHint = '当前阶段不能提交规则。';
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
          提交规则
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          data-testid="advance-round"
          disabled={!decision.canAdvance}
          onClick={onAdvance}
        >
          继续下一回合
        </button>
      </div>

      {mockNotice ? (
        <p className="rule-panel__notice" data-testid="mock-notice">
          {mockNotice}
        </p>
      ) : null}

      {feedback ? (
        <div
          className={
            feedback.accepted
              ? 'feedback feedback--accepted'
              : 'feedback feedback--rejected'
          }
          data-testid="rule-feedback"
        >
          <p className="feedback__headline">{feedback.codeLabel}</p>
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
            <ul className="feedback__stats">
              {feedback.statChangeSummary.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <div className="feedback feedback--error" data-testid="game-error">
          <p className="feedback__headline">操作未完成</p>
          <p className="feedback__message">{error.message}</p>
          {error.retryable ? (
            <p className="feedback__suggest">这是可恢复错误，可以稍后重试。</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
