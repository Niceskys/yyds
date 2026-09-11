import { describe, expect, it } from 'vitest';
import { loadMatchSnapshot, loadReplay, loadRuleSubmission } from '../contract/fixtures';
import { buildReplayViewModel } from '../contract/replayAdapter';
import { presentEvent } from '../contract/eventLabels';
import {
  buildActionViewModel,
  buildBoardViewModel,
  buildMatchViewModel,
  buildRoundViewModel,
  buildRuleFeedbackViewModel,
} from '../contract/mockAdapter';
import type { RoundExecutionPublicView } from '../contract/types';

describe('fixture → ViewModel adapter', () => {
  it('从 match_initial 读取棋盘尺寸与红蓝坐标', () => {
    const snapshot = loadMatchSnapshot('match_initial');
    const board = buildBoardViewModel(snapshot);

    expect(board.rows).toBe(5);
    expect(board.cols).toBe(5);
    expect(board.cells).toHaveLength(5);
    expect(board.cells[0]).toHaveLength(5);

    // 公共坐标 1-based：红方 (row=3, col=2)，蓝方 (row=3, col=5)
    expect(board.cells[2][1].team).toBe('RED');
    expect(board.cells[2][1].hp).toBe(4);
    expect(board.cells[2][4].team).toBe('BLUE');
    expect(board.cells[0][0].team).toBeNull();
  });

  it('顶层状态直接读取后端字段，不自行推理', () => {
    const view = buildMatchViewModel(loadMatchSnapshot('match_player_decision'));
    expect(view.completedRounds).toBe(1);
    expect(view.ruleChangeCount).toBe(0);
    expect(view.roundNo).toBe(2);
    expect(view.decision.canSubmitRule).toBe(true);
    expect(view.decision.canAdvance).toBe(true);
    expect(view.decision.afterRound).toBe(1);
    expect(view.escalation.level).toBe(0);
    expect(view.escalation.levelLabel).toBe('0级');
  });

  it('有效属性不包含 conflict_level / hard_liveness', () => {
    const view = buildMatchViewModel(loadMatchSnapshot('match_player_decision'));
    const keys = view.teams.RED.stats.map((stat) => stat.key);
    expect(keys).not.toContain('conflict_level');
    expect(keys).not.toContain('hard_liveness');

    const serialized = JSON.stringify(view);
    expect(serialized).not.toContain('conflict_level');
    expect(serialized).not.toContain('hard_liveness');
    expect(serialized).not.toContain('BattleEscalationSnapshot');
  });

  it('策略映射为中文，普通模式不输出内部枚举', () => {
    const view = buildMatchViewModel(loadMatchSnapshot('match_player_decision'), {
      debug: false,
    });
    expect(view.teams.RED.strategy?.label).toBe('逼近进攻');
    expect(view.teams.BLUE.strategy?.label).toBe('保持距离');
    expect(view.teams.BLUE.strategy?.weaponPreferenceLabel).toBe('偏向弓箭');
    expect(view.teams.BLUE.strategy?.shortTermGoalLabel).toBe('优先保命');
    expect(JSON.stringify(view)).not.toContain('PRESSURE');
  });

  it('规则成功 fixture 会锁定规则输入但允许继续', () => {
    const submission = loadRuleSubmission('rule_accepted');
    const view = buildMatchViewModel(submission.match);
    expect(view.decision.canSubmitRule).toBe(false);
    expect(view.decision.ruleChangedThisIntermission).toBe(true);
    expect(view.decision.canAdvance).toBe(true);
    expect(view.ruleChangeCount).toBe(1);
    expect(view.activeRule?.playerText).toBe('双方移动距离增加1格');
  });

  it('规则被拒 fixture 不增加规则制定次数并保留重试空间', () => {
    const submission = loadRuleSubmission('rule_rejected');
    const view = buildMatchViewModel(submission.match);
    expect(submission.accepted).toBe(false);
    expect(view.ruleChangeCount).toBe(0);
    expect(view.decision.canSubmitRule).toBe(true);

    const feedback = buildRuleFeedbackViewModel(submission);
    expect(feedback.accepted).toBe(false);
    expect(feedback.codeLabel).toBe('无法生成可用规则');
    expect(feedback.suggestedRephrase).toBe('双方的移动距离增加1格');
  });

  it('accepted feedback 只展示 authoritative 公开属性前后变化', () => {
    const submission = loadRuleSubmission('rule_accepted');
    const feedback = buildRuleFeedbackViewModel(
      submission,
      loadMatchSnapshot('match_player_decision'),
    );
    expect(feedback.statChangeSummary).toEqual([
      '红方：移动距离 1 格 → 2 格',
      '蓝方：移动距离 1 格 → 2 格',
    ]);
  });

  it('RULE_MODIFIER_APPLIED 使用公开 modifier 生成安全中文文案', () => {
    const event = presentEvent(
      {
        event_version: 'event-v0.1',
        kind: 'RULE_MODIFIER_APPLIED',
        actor: 'RED',
        details: {
          move_range_add: 1,
          bow_hit_multiplier: 1.5,
          cooldown_weapons: ['BOW'],
        },
      },
      0,
      false,
    );
    expect(event.label).toBe('公共规则生效');
    expect(event.detail).toBe('红方：移动距离 +1，弓箭命中倍率 ×1.5，冷却武器：弓箭');
    expect(event.isUnknown).toBe(false);
  });

  it('终局禁止提交与推进，并给出玩家成绩', () => {
    const view = buildMatchViewModel(loadMatchSnapshot('match_terminal'));
    expect(view.lifecycle).toBe('TERMINAL');
    expect(view.decision.canSubmitRule).toBe(false);
    expect(view.decision.canAdvance).toBe(false);
    expect(view.resultLabel).toBe('红方胜利');
    expect(view.scoreRounds).toBe(2);
  });

  it('行动展示使用中文武器名', () => {
    expect(buildActionViewModel({ attack: 'BOW', move_path: [] }).summary).toBe(
      '未移动，使用弓箭攻击',
    );
    expect(
      buildActionViewModel({ attack: 'KNIFE', move_path: ['LEFT', 'UP'] }).summary,
    ).toBe('移动 左 → 上，使用刀攻击');
    expect(buildActionViewModel({ attack: null, move_path: [] }).summary).toBe('未移动');
  });

  it('未知事件走安全 fallback，不崩溃', () => {
    const round: RoundExecutionPublicView = {
      round_no: 7,
      strategies: {
        RED: {
          plan_version: 'intent-v0.1',
          status: 'ACCEPTED',
          intent: 'HOLD',
          degraded: false,
        },
        BLUE: {
          plan_version: 'intent-v0.1',
          status: 'ACCEPTED',
          intent: 'EVADE',
          degraded: false,
        },
      },
      actions: {
        RED: { attack: null, move_path: [] },
        BLUE: { attack: null, move_path: [] },
      },
      events: [
        {
          event_version: 'event-v0.1',
          kind: 'BRAND_NEW_EVENT',
          actor: null,
          details: {},
        },
      ],
    };
    const view = buildRoundViewModel(round, false);
    expect(view.events).toHaveLength(1);
    expect(view.events[0].label).toBe('发生新的战斗事件');
    expect(view.events[0].isUnknown).toBe(true);
    expect(view.events[0].detail).toBeNull();

    const debugView = buildRoundViewModel(round, true);
    expect(debugView.events[0].detail).toBe('未知事件：BRAND_NEW_EVENT');
  });

  it('Replay 时间线第一条是 ROUND 1', () => {
    const replay = buildReplayViewModel(loadReplay(), false);
    expect(replay.entries[0].kindLabel).toBe('回合');
    expect(replay.entries[0].headline).toBe('第 1 回合');
    expect(replay.entries[1].kindLabel).toBe('回合间');
    expect(replay.entries[1].headline).toBe('第 1 回合后 · 玩家决策');
    expect(replay.terminalResultLabel).toBe('红方胜利');
  });
});
