import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { GameScreen } from '../components/GameScreen';
import { buildScenarioState } from '../mock/scenarios';
import type { ScenarioId } from '../mock/scenarios';

function renderScenario(id: ScenarioId, ruleText = '') {
  const state = buildScenarioState(id, false);
  const onRuleTextChange = vi.fn();
  const onSubmitRule = vi.fn();
  const onAdvance = vi.fn();
  render(
    <GameScreen
      match={state.match}
      lastRound={state.lastRound}
      feedback={state.feedback}
      error={state.error}
      mockNotice={null}
      ruleText={ruleText}
      onRuleTextChange={onRuleTextChange}
      onSubmitRule={onSubmitRule}
      onAdvance={onAdvance}
      onRestart={vi.fn()}
      onOpenReplay={null}
      mockBar={null}
    />,
  );
  return { onRuleTextChange, onSubmitRule, onAdvance };
}

describe('游玩主界面', () => {
  it('按 fixture 渲染 5×5 棋盘与红蓝单位坐标', () => {
    renderScenario('player_decision');
    const grid = screen.getByTestId('board-grid');
    expect(grid).toHaveAttribute('data-rows', '5');
    expect(grid).toHaveAttribute('data-cols', '5');
    expect(screen.getByTestId('cell-3-2')).toHaveAttribute('data-team', 'RED');
    expect(screen.getByTestId('cell-3-5')).toHaveAttribute('data-team', 'BLUE');
    expect(screen.getByTestId('cell-1-1')).toHaveAttribute('data-team', 'EMPTY');
    expect(screen.getByTestId('hp-RED')).toHaveTextContent('生命值 4');
  });

  it('PLAYER_DECISION 状态允许提交规则与继续', () => {
    renderScenario('player_decision', '双方移动距离增加 1 格');
    expect(screen.getByTestId('rule-input')).not.toBeDisabled();
    expect(screen.getByTestId('submit-rule')).not.toBeDisabled();
    expect(screen.getByTestId('advance-round')).not.toBeDisabled();
    expect(screen.getByTestId('completed-rounds')).toHaveTextContent('1');
    expect(screen.getByTestId('rule-change-count')).toHaveTextContent('0');
  });

  it('规则为空时提交按钮不可用', () => {
    renderScenario('player_decision', '   ');
    expect(screen.getByTestId('submit-rule')).toBeDisabled();
  });

  it('accepted：锁定规则输入但保留继续下一回合', () => {
    renderScenario('rule_accepted', '双方移动距离增加 1 格');
    expect(screen.getByTestId('rule-input')).toBeDisabled();
    expect(screen.getByTestId('submit-rule')).toBeDisabled();
    expect(screen.getByTestId('advance-round')).not.toBeDisabled();
    expect(screen.getByTestId('rule-feedback')).toHaveTextContent('规则已生效');
    expect(screen.getByTestId('rule-change-count')).toHaveTextContent('1');
    expect(screen.getByTestId('active-rule')).toHaveTextContent('双方移动距离增加1格');
  });

  it('rejected：保留规则输入、显示失败信息且不增加规则制定次数', () => {
    renderScenario('rule_rejected', '双方移动距离增加 1 格');
    expect(screen.getByTestId('rule-input')).not.toBeDisabled();
    expect(screen.getByTestId('rule-change-count')).toHaveTextContent('0');
    expect(screen.getByTestId('rule-feedback')).toHaveTextContent('无法生成可用规则');
    expect(screen.getByTestId('rule-feedback')).toHaveTextContent('可以试试这样说');
  });

  it('terminal：禁止提交与推进，并显示玩家成绩', () => {
    renderScenario('terminal');
    expect(screen.getByTestId('rule-input')).toBeDisabled();
    expect(screen.getByTestId('submit-rule')).toBeDisabled();
    expect(screen.getByTestId('advance-round')).toBeDisabled();
    expect(screen.getByTestId('result-banner')).toHaveTextContent('红方胜利');
    expect(screen.getByTestId('result-banner')).toHaveTextContent('本局持续：2 回合');
  });

  it('第 1 回合结算场景展示本回合结果与事件', () => {
    renderScenario('advance_round');
    expect(screen.getByTestId('round-summary')).toHaveTextContent('第 1 回合结果');
    expect(screen.getByTestId('event-list')).toHaveTextContent('造成伤害');
    expect(screen.getByTestId('action-RED')).toHaveTextContent('使用弓箭攻击');
  });

  it('普通 UI 不出现内部实现字段与英文枚举', () => {
    renderScenario('player_decision');
    const text = document.body.textContent ?? '';
    expect(text).not.toContain('conflict_level');
    expect(text).not.toContain('hard_liveness');
    expect(text).not.toContain('BattleEscalationSnapshot');
    expect(text).not.toContain('PRESSURE');
    expect(text).not.toContain('KITE');
    expect(text).toContain('逼近进攻');
    expect(text).toContain('保持距离');
    expect(text).toContain('战局升温');
  });

  it('输入内容会回传给上层', () => {
    const { onRuleTextChange } = renderScenario('player_decision');
    fireEvent.change(screen.getByTestId('rule-input'), {
      target: { value: '双方弓箭射程增加 1 格' },
    });
    expect(onRuleTextChange).toHaveBeenCalledWith('双方弓箭射程增加 1 格');
  });
});
