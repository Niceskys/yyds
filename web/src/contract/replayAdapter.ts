/**
 * Replay Adapter：ReplaySnapshot → 展示模型（B3 基础结构）。
 *
 * 时间线严格按后端给出的顺序渲染：
 *   ROUND → INTERMISSION → ROUND → ...
 * 第一条必须是 ROUND 1（V0.2 不存在 Round 1 之前的规则阶段）。
 * 这里不重新调用模型，也不展示 chain-of-thought / private memory。
 */
import { presentEvents } from './eventLabels';
import {
  labelMatchResult,
  labelSubmissionCode,
  labelTeam,
} from './labels';
import { buildActionViewModel, buildStrategyViewModel } from './mockAdapter';
import type { ReplayEntry, ReplaySnapshot } from './types';
import type { ReplayEntryViewModel, ReplayViewModel } from './viewModel';

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
  const events = presentEvents(entry.events, debug);
  events.forEach((event) => {
    lines.push(event.detail ? `事件：${event.label}（${event.detail}）` : `事件：${event.label}`);
  });
  lines.push(
    `回合结束生命值：红方 ${entry.post_round_units.RED.hp}，蓝方 ${entry.post_round_units.BLUE.hp}`,
  );
  const resultLabel = labelMatchResult(entry.result);
  if (resultLabel) lines.push(`对局结果：${resultLabel}`);
  return lines;
}

function intermissionEntryLines(
  entry: Extract<ReplayEntry, { entry_type: 'INTERMISSION' }>,
): string[] {
  const lines: string[] = [];
  if (entry.choice === 'CONTINUE') {
    lines.push('玩家选择：不修改规则，继续下一回合');
  } else {
    lines.push(
      `玩家尝试规则：${entry.submitted_player_text ?? '（未记录文本）'}`,
    );
    if (entry.submission_public_code) {
      lines.push(`提交结果：${labelSubmissionCode(entry.submission_public_code)}`);
    }
    if (entry.accepted_rule) {
      lines.push(`已生效规则：${entry.accepted_rule.player_text}`);
    }
  }
  if (entry.active_rule_before && entry.active_rule_after) {
    lines.push(
      `公共规则：${entry.active_rule_before.player_text} → ${entry.active_rule_after.player_text}`,
    );
  } else if (!entry.active_rule_before && entry.active_rule_after) {
    lines.push(`公共规则：无 → ${entry.active_rule_after.player_text}`);
  }
  lines.push(`规则制定次数：${entry.rule_change_count_after}`);
  return lines;
}

export function buildReplayViewModel(
  replay: ReplaySnapshot,
  debug: boolean,
): ReplayViewModel {
  const entries: ReplayEntryViewModel[] = replay.timeline.map((entry, index) => {
    if (entry.entry_type === 'ROUND') {
      return {
        key: `round-${entry.round_no}-${index}`,
        kindLabel: '回合',
        headline: `第 ${entry.round_no} 回合`,
        lines: roundEntryLines(entry, debug),
      };
    }
    return {
      key: `intermission-${entry.after_round}-${index}`,
      kindLabel: '回合间',
      headline: `第 ${entry.after_round} 回合后 · 玩家决策`,
      lines: intermissionEntryLines(entry),
    };
  });
  return {
    matchId: replay.match_id,
    terminalResultLabel: labelMatchResult(replay.terminal_result),
    scoreRounds: replay.score_rounds,
    ruleChangeCount: replay.rule_change_count,
    entries,
  };
}
