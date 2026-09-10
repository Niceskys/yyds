/**
 * Mock Adapter：canonical V0.2 contract 对象 → UI ViewModel。
 *
 * 这里是唯一允许直接访问 fixture / contract 字段的地方。
 * React 组件只消费 ViewModel，不再散落 `snapshot.xxx.yyy` 访问，
 * 以便 B4 把本文件替换成 API Adapter 而不重写 UI。
 *
 * 本文件不做任何游戏规则计算：
 * - 不判断规则是否合法；
 * - 不计算命中率；
 * - 不推导战局升温等级；
 * - 不推导胜负。
 * 只读取后端/ fixture 已经给出的公开字段并做中文映射与过滤。
 */
import { presentEvents } from './eventLabels';
import {
  ESCALATION_LEVEL_LABELS,
  UNKNOWN_LABEL,
  formatPercent,
  formatSigned,
  labelDirection,
  labelLifecycle,
  labelMatchResult,
  labelRiskBudget,
  labelRuleEffectType,
  labelShortTermGoal,
  labelStrategy,
  labelStrategyStatus,
  labelSubmissionCode,
  labelTeam,
  labelWeapon,
  labelWeaponPreference,
} from './labels';
import type {
  ActionPublicView,
  AdvanceResult,
  BattleEscalationSnapshot,
  EffectiveStatsPublicView,
  ErrorEnvelope,
  MatchSnapshot,
  PlayerDecisionSnapshot,
  PublicStrategyDecision,
  RoundExecutionPublicView,
  RulePublicView,
  RuleSubmissionResult,
  TeamId,
  UnitPublicView,
} from './types';
import type {
  ActionViewModel,
  BoardViewModel,
  CellViewModel,
  DecisionViewModel,
  EscalationViewModel,
  GameErrorViewModel,
  MatchViewModel,
  RoundViewModel,
  RuleFeedbackViewModel,
  RuleViewModel,
  StatViewModel,
  StrategyViewModel,
  TeamViewModel,
} from './viewModel';

export interface AdapterOptions {
  /** 开发调试模式：允许附加原始内部值。默认 false。 */
  debug?: boolean;
}

function strategyDebugRaw(strategy: PublicStrategyDecision | null): string | null {
  if (!strategy) return null;
  return `intent=${strategy.intent ?? '-'} status=${strategy.status ?? '-'}`;
}

export function buildStrategyViewModel(
  strategy: PublicStrategyDecision | null,
  debug: boolean,
): StrategyViewModel | null {
  if (!strategy) return null;
  const intentLabel = labelStrategy(strategy.intent);
  return {
    label: intentLabel ?? '暂无公开策略',
    statusLabel: labelStrategyStatus(strategy.status),
    degraded: strategy.degraded === true,
    shortTermGoalLabel: labelShortTermGoal(strategy.short_term_goal),
    weaponPreferenceLabel: labelWeaponPreference(strategy.weapon_preference),
    riskBudgetLabel: labelRiskBudget(strategy.risk_budget),
    targetDistance: strategy.target_distance ?? null,
    debugRaw: debug ? strategyDebugRaw(strategy) : null,
  };
}

/**
 * 有效属性白名单。
 * conflict_level / hard_liveness 明确不在此列表内：
 * 它们是公共 contract 的机器状态，但普通玩家 UI 不展示。
 */
function buildStatsViewModel(stats: EffectiveStatsPublicView): StatViewModel[] {
  const cooldownWeapons = stats.cooldown_weapons ?? [];
  const cooldown =
    cooldownWeapons.length > 0
      ? cooldownWeapons.map((weapon) => labelWeapon(weapon)).join('、')
      : '无';
  return [
    { key: 'move_range', label: '移动距离', value: `${stats.move_range} 格` },
    { key: 'knife_range', label: '刀攻击距离', value: `${stats.knife_range} 格` },
    { key: 'bow_range', label: '弓箭射程', value: `${stats.bow_range} 格` },
    { key: 'knife_damage', label: '刀伤害', value: `${stats.knife_damage}` },
    { key: 'bow_damage', label: '弓箭伤害', value: `${stats.bow_damage}` },
    {
      key: 'bow_hit_floor',
      label: '弓箭最低命中率',
      value: formatPercent(stats.bow_hit_floor),
    },
    {
      key: 'bow_hit_multiplier',
      label: '弓箭命中倍率',
      value: `×${stats.bow_hit_multiplier}`,
    },
    { key: 'cooldown_weapons', label: '冷却中武器', value: cooldown },
  ];
}

export function buildTeamViewModel(
  team: TeamId,
  unit: UnitPublicView,
  stats: EffectiveStatsPublicView,
  strategy: PublicStrategyDecision | null,
  debug: boolean,
): TeamViewModel {
  return {
    team,
    teamLabel: labelTeam(team),
    hp: unit.hp,
    position: { row: unit.position.row, col: unit.position.col },
    positionLabel: `第 ${unit.position.row} 行，第 ${unit.position.col} 列`,
    strategy: buildStrategyViewModel(strategy, debug),
    stats: buildStatsViewModel(stats),
  };
}

/**
 * 棋盘渲染。
 * 公共坐标 1-based、row 1 在顶部；0-based 只允许存在于这里和 React 渲染层。
 */
export function buildBoardViewModel(
  snapshot: MatchSnapshot,
): BoardViewModel {
  const { rows, cols } = snapshot.board;
  const cells: CellViewModel[][] = [];
  for (let rowIndex = 0; rowIndex < rows; rowIndex += 1) {
    const rowCells: CellViewModel[] = [];
    for (let colIndex = 0; colIndex < cols; colIndex += 1) {
      rowCells.push({
        row: rowIndex + 1,
        col: colIndex + 1,
        team: null,
        teamLabel: null,
        hp: null,
      });
    }
    cells.push(rowCells);
  }
  (Object.keys(snapshot.units) as TeamId[]).forEach((team) => {
    const unit = snapshot.units[team];
    const arrayRow = unit.position.row - 1;
    const arrayCol = unit.position.col - 1;
    const cell = cells[arrayRow]?.[arrayCol];
    if (cell) {
      cell.team = team;
      cell.teamLabel = labelTeam(team);
      cell.hp = unit.hp;
    }
  });
  return { rows, cols, cells };
}

/** 战局升温：只解释后端给出的 level / streak / rounds_until_next_level。 */
export function buildEscalationViewModel(
  escalation: BattleEscalationSnapshot,
): EscalationViewModel {
  const levelLabel = ESCALATION_LEVEL_LABELS[escalation.level] ?? UNKNOWN_LABEL;
  const roundsUntilNextLevel = escalation.rounds_until_next_level ?? null;
  let hint: string;
  if (escalation.hard_liveness_active || escalation.level >= 4) {
    hint = '已进入最高升温等级：双方弓箭射程与最低命中率被提高，并可能被强制使用弓箭。';
  } else if (roundsUntilNextLevel === null) {
    hint = '暂无进一步升温信息。';
  } else if (roundsUntilNextLevel <= 0) {
    hint = '下一次无伤害结算后，战局将继续升温。';
  } else {
    hint = `再持续 ${roundsUntilNextLevel} 回合无伤害，战局将进一步升温。`;
  }
  return {
    level: escalation.level,
    levelLabel,
    noDamageStreak: escalation.no_damage_streak,
    nextLevelAt: escalation.next_level_at_no_damage ?? null,
    roundsUntilNextLevel,
    hint,
  };
}

export function buildRuleViewModel(rule: RulePublicView | null): RuleViewModel | null {
  if (!rule) return null;
  const effect = rule.ast.effect;
  const parts: string[] = [labelRuleEffectType(effect.type)];
  if (typeof effect.delta === 'number') parts.push(formatSigned(effect.delta));
  if (typeof effect.multiplier === 'number') parts.push(`×${effect.multiplier}`);
  if (effect.weapon && effect.weapon !== 'NONE') {
    parts.push(`目标武器：${labelWeapon(effect.weapon)}`);
  }
  if (typeof effect.rounds === 'number') parts.push(`持续 ${effect.rounds} 回合`);
  return {
    ruleId: rule.rule_id,
    playerText: rule.player_text,
    effectSummary: parts.join(' '),
  };
}

export function buildActionViewModel(action: ActionPublicView | null): ActionViewModel {
  if (!action) {
    return { summary: '本回合暂无公开行动', attackLabel: null, moveLabel: '未移动' };
  }
  const movePath = action.move_path ?? [];
  const moveLabel =
    movePath.length > 0
      ? `移动 ${movePath.map(labelDirection).join(' → ')}`
      : '未移动';
  const attackLabel = action.attack ? `使用${labelWeapon(action.attack)}攻击` : null;
  return {
    summary: attackLabel ? `${moveLabel}，${attackLabel}` : moveLabel,
    attackLabel,
    moveLabel,
  };
}

export function buildRoundViewModel(
  round: RoundExecutionPublicView,
  debug: boolean,
): RoundViewModel {
  return {
    roundNo: round.round_no,
    strategies: {
      RED: buildStrategyViewModel(round.strategies.RED, debug),
      BLUE: buildStrategyViewModel(round.strategies.BLUE, debug),
    },
    actions: {
      RED: buildActionViewModel(round.actions.RED),
      BLUE: buildActionViewModel(round.actions.BLUE),
    },
    events: presentEvents(round.events, debug),
    resultLabel: null,
  };
}

export function buildDecisionViewModel(
  decision: PlayerDecisionSnapshot,
): DecisionViewModel {
  return {
    afterRound: decision.after_round ?? null,
    canSubmitRule: decision.can_submit_rule,
    canAdvance: decision.can_advance,
    ruleChangedThisIntermission: decision.rule_changed_this_intermission,
  };
}

export type BuildMatchOptions = AdapterOptions;

export function buildMatchViewModel(
  snapshot: MatchSnapshot,
  options: BuildMatchOptions = {},
): MatchViewModel {
  const debug = options.debug === true;
  return {
    matchId: snapshot.match_id,
    schemaVersion: snapshot.schema_version,
    lifecycle: snapshot.lifecycle,
    lifecycleLabel: labelLifecycle(snapshot.lifecycle),
    revision: snapshot.revision,
    roundNo: snapshot.round_no,
    completedRounds: snapshot.completed_rounds,
    scoreRounds: snapshot.score_rounds,
    ruleChangeCount: snapshot.rule_change_count,
    board: buildBoardViewModel(snapshot),
    teams: {
      RED: buildTeamViewModel(
        'RED',
        snapshot.units.RED,
        snapshot.effective_stats.RED,
        snapshot.latest_strategy.RED,
        debug,
      ),
      BLUE: buildTeamViewModel(
        'BLUE',
        snapshot.units.BLUE,
        snapshot.effective_stats.BLUE,
        snapshot.latest_strategy.BLUE,
        debug,
      ),
    },
    activeRule: buildRuleViewModel(snapshot.active_rule),
    escalation: buildEscalationViewModel(snapshot.battle_escalation),
    decision: buildDecisionViewModel(snapshot.player_decision),
    resultLabel: labelMatchResult(snapshot.result),
    result: snapshot.result,
    debugRaw: debug
      ? `lifecycle=${snapshot.lifecycle} revision=${snapshot.revision} round_no=${snapshot.round_no}`
      : null,
  };
}

export function buildAdvanceViewModel(
  result: AdvanceResult,
  options: AdapterOptions = {},
): { match: MatchViewModel; round: RoundViewModel } {
  const debug = options.debug === true;
  return {
    match: buildMatchViewModel(result.match, { debug }),
    round: buildRoundViewModel(result.round, debug),
  };
}

/** 规则提交结果 → 反馈 ViewModel。 */
export function buildRuleFeedbackViewModel(
  result: RuleSubmissionResult,
): RuleFeedbackViewModel {
  const statChangeSummary: string[] = [];
  if (result.accepted) {
    (['RED', 'BLUE'] as TeamId[]).forEach((team) => {
      const stats = result.match.effective_stats[team];
      statChangeSummary.push(
        `${labelTeam(team)}：移动距离 ${stats.move_range} 格，弓箭射程 ${stats.bow_range} 格，弓箭最低命中率 ${formatPercent(stats.bow_hit_floor)}`,
      );
    });
  }
  return {
    accepted: result.accepted,
    code: result.public_code,
    codeLabel: labelSubmissionCode(result.public_code),
    message: result.message,
    suggestedRephrase: result.suggested_rephrase ?? null,
    acceptedRuleText: result.accepted ? (result.match.active_rule?.player_text ?? null) : null,
    statChangeSummary,
  };
}

export function buildErrorViewModel(error: ErrorEnvelope): GameErrorViewModel {
  return {
    code: error.error.code,
    message: error.error.message,
    retryable: error.error.retryable,
  };
}
