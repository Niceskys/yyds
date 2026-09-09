/**
 * Replay Adapter：ReplaySnapshot → 展示模型。
 *
 * 时间线严格消费后端 ReplaySnapshot 已给出的公开事实：
 *   ROUND → INTERMISSION → ROUND → ...
 * 不重新模拟 Engine，不重新调用模型，不展示 chain-of-thought / private memory。
 */
import { presentEvents } from './eventLabels';
import {
  labelMatchResult,
  labelSubmissionCode,
  labelTeam,
} from './labels';
import {
  buildActionViewModel,
  buildBoardViewModel,
  buildEscalationViewModel,
  buildMatchViewModel,
  buildRuleViewModel,
  buildStrategyViewModel,
  buildTeamViewModel,
} from './mockAdapter';
import type { MatchSnapshot, ReplayEntry, ReplaySnapshot } from './types';
import type {
  ReplayEntryViewModel,
  ReplayIntermissionEntryViewModel,
  ReplayRoundEntryViewModel,
  ReplayViewModel,
} from './viewModel';

function roundEntryLines(
  entry: Extract<ReplayEntry, { entry_type: 'ROUND' }>,
  debug: boolean,
): string[] {
  const lines: string[] = [];
  (['RED', 'BLUE'] as const).forEach((team) => {
    const strategy = buildStrategyViewModel(entry.strategies[team], debug);
    const action = buildActionViewModel(entry.actions[team]);
    lines.push(
      `${labelTeam(team)}：策略「${strategy?.label ?? '暂无公开策略'}」，行动「${action.summary}」`,
    );
  });
  presentEvents(entry.events, debug).forEach((event) => {
    lines.push(event.detail ? `事件：${event.label}（${event.detail}）` : `事件：${event.label}`);
  });
  lines.push(
    `回合结束生命值：红方 ${entry.post_round_units.RED.hp}，蓝方 ${entry.post_round_units.BLUE.hp}`,
  );
  const resultLabel = labelMatchResult(entry.result);
  if (resultLabel) lines.push(`对局结果：${resultLabel}`);
  return lines;
}

function buildRoundEntryViewModel(
  entry: Extract<ReplayEntry, { entry_type: 'ROUND' }>,
  index: number,
  debug: boolean,
): ReplayRoundEntryViewModel {
  const before = buildMatchViewModel(entry.pre_round, { debug });
  const afterSnapshot: MatchSnapshot = {
    ...entry.pre_round,
    units: entry.post_round_units,
    effective_stats: entry.effective_stats,
    latest_strategy: entry.strategies,
    battle_escalation: entry.battle_escalation,
    result: entry.result,
  };
  return {
    key: `round-${entry.round_no}-${index}`,
    kind: 'ROUND',
    kindLabel: '回合',
    headline: `第 ${entry.round_no} 回合`,
    lines: roundEntryLines(entry, debug),
    roundNo: entry.round_no,
    beforeBoard: before.board,
    afterBoard: buildBoardViewModel(afterSnapshot),
    teamsBefore: before.teams,
    teamsAfter: {
      RED: buildTeamViewModel(
        'RED',
        entry.post_round_units.RED,
        entry.effective_stats.RED,
        entry.strategies.RED,
        debug,
      ),
      BLUE: buildTeamViewModel(
        'BLUE',
        entry.post_round_units.BLUE,
        entry.effective_stats.BLUE,
        entry.strategies.BLUE,
        debug,
      ),
    },
    activeRule: buildRuleViewModel(entry.pre_round.active_rule),
    escalation: buildEscalationViewModel(entry.battle_escalation),
    strategies: {
      RED: buildStrategyViewModel(entry.strategies.RED, debug),
      BLUE: buildStrategyViewModel(entry.strategies.BLUE, debug),
    },
    actions: {
      RED: buildActionViewModel(entry.actions.RED),
      BLUE: buildActionViewModel(entry.actions.BLUE),
    },
    events: presentEvents(entry.events, debug),
    resultLabel: labelMatchResult(entry.result),
  };
}

function intermissionEntryLines(
  entry: Extract<ReplayEntry, { entry_type: 'INTERMISSION' }>,
): string[] {
  const lines: string[] = [];
  if (entry.choice === 'CONTINUE') {
    lines.push('玩家选择：不修改规则，继续下一回合');
  } else {
    lines.push(`玩家尝试规则：${entry.submitted_player_text ?? '（未记录文本）'}`);
    if (entry.submission_public_code) {
      lines.push(`提交结果：${labelSubmissionCode(entry.submission_public_code)}`);
    }
    if (entry.accepted_rule) {
      lines.push(`已生效规则：${entry.accepted_rule.player_text}`);
    }
  }
  const before = entry.active_rule_before?.player_text ?? '无';
  const after = entry.active_rule_after?.player_text ?? '无';
  lines.push(`公共规则：${before} → ${after}`);
  lines.push(`规则制定次数：${entry.rule_change_count_after}`);
  return lines;
}

function buildIntermissionEntryViewModel(
  entry: Extract<ReplayEntry, { entry_type: 'INTERMISSION' }>,
  index: number,
): ReplayIntermissionEntryViewModel {
  return {
    key: `intermission-${entry.after_round}-${index}`,
    kind: 'INTERMISSION',
    kindLabel: '回合间',
    headline: `第 ${entry.after_round} 回合后 · 玩家决策`,
    lines: intermissionEntryLines(entry),
    afterRound: entry.after_round,
    choiceLabel: entry.choice === 'CONTINUE' ? '继续下一回合' : '尝试制定规则',
    submittedPlayerText: entry.submitted_player_text,
    submissionResultLabel: entry.submission_public_code
      ? labelSubmissionCode(entry.submission_public_code)
      : null,
    acceptedRule: buildRuleViewModel(entry.accepted_rule),
    activeRuleBefore: buildRuleViewModel(entry.active_rule_before),
    activeRuleAfter: buildRuleViewModel(entry.active_rule_after),
    ruleChangeCountAfter: entry.rule_change_count_after,
  };
}

export function buildReplayViewModel(
  replay: ReplaySnapshot,
  debug: boolean,
): ReplayViewModel {
  const entries: ReplayEntryViewModel[] = replay.timeline.map((entry, index) =>
    entry.entry_type === 'ROUND'
      ? buildRoundEntryViewModel(entry, index, debug)
      : buildIntermissionEntryViewModel(entry, index),
  );
  return {
    matchId: replay.match_id,
    terminalResultLabel: labelMatchResult(replay.terminal_result),
    scoreRounds: replay.score_rounds,
    ruleChangeCount: replay.rule_change_count,
    entries,
  };
}
