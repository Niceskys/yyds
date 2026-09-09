/**
 * 公共 enum → 中文产品文案的唯一映射表。
 *
 * 普通玩家界面不直接显示英文内部值；未知值一律走安全 fallback，
 * 只有在开发调试模式（debug=true）才附加原始值。
 */
import type {
  Direction,
  MatchLifecycle,
  MatchResult,
  RiskBudget,
  RuleEffectType,
  RuleSubmissionCode,
  ShortTermGoal,
  StrategyIntent,
  StrategyStatus,
  TeamId,
  WeaponId,
  WeaponPreference,
} from './types';

export const UNKNOWN_LABEL = '未知';

export const TEAM_LABELS: Record<TeamId, string> = {
  RED: '红方',
  BLUE: '蓝方',
};

export const STRATEGY_LABELS: Record<StrategyIntent, string> = {
  PRESSURE: '逼近进攻',
  KITE: '保持距离',
  EVADE: '躲避保命',
  HOLD: '原地应对',
};

export const WEAPON_LABELS: Record<WeaponId, string> = {
  BOW: '弓箭',
  KNIFE: '刀',
};

export const WEAPON_PREFERENCE_LABELS: Record<WeaponPreference, string> = {
  BOW: '偏向弓箭',
  KNIFE: '偏向刀',
  ADAPTIVE: '视情况切换',
};

export const LIFECYCLE_LABELS: Record<MatchLifecycle, string> = {
  RUNNING: '战斗进行中',
  PLAYER_DECISION: '等待你的决策',
  TERMINAL: '对局已结束',
  FAILED_RECOVERABLE: '对局出现可恢复问题',
};

export const MATCH_RESULT_LABELS: Record<MatchResult, string> = {
  RED_WIN: '红方胜利',
  BLUE_WIN: '蓝方胜利',
  DRAW_MUTUAL_DEATH: '双方同归于尽',
  TIMEOUT: '达到本局最高回合数',
};

export const STRATEGY_STATUS_LABELS: Record<StrategyStatus, string> = {
  ACCEPTED: '正常',
  FALLBACK_MODEL_ERROR: '模型不可用，已回退',
  FALLBACK_PROTOCOL_ERROR: '模型输出异常，已回退',
};

export const SHORT_TERM_GOAL_LABELS: Record<ShortTermGoal, string> = {
  DAMAGE: '追求伤害',
  SURVIVE: '优先保命',
  TRIGGER_RULE: '触发规则',
  DENY_RULE: '阻止对手触发规则',
};

export const RISK_BUDGET_LABELS: Record<RiskBudget, string> = {
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
};

export const DIRECTION_LABELS: Record<Direction, string> = {
  UP: '上',
  DOWN: '下',
  LEFT: '左',
  RIGHT: '右',
};

export const RULE_EFFECT_TYPE_LABELS: Record<RuleEffectType, string> = {
  MOVE_RANGE_ADD: '移动距离增加',
  KNIFE_RANGE_ADD: '刀攻击距离增加',
  BOW_RANGE_ADD: '弓箭射程增加',
  KNIFE_DAMAGE_ADD: '刀伤害增加',
  BOW_DAMAGE_ADD: '弓箭伤害增加',
  BOW_HIT_MULTIPLIER: '弓箭命中倍率调整',
  WEAPON_COOLDOWN: '武器冷却',
};

export const RULE_SUBMISSION_CODE_LABELS: Record<RuleSubmissionCode, string> = {
  ACCEPTED: '规则已生效',
  NO_CANDIDATE: '无法生成可用规则',
  RULE_REJECTED: '规则被拒绝',
  FAITHFULNESS_REJECTED: '规则与原意不一致',
  MODEL_UNAVAILABLE: '规则模型暂时不可用',
  RULE_SUBMISSION_NOT_ALLOWED: '当前阶段不能提交规则',
  MATCH_TERMINAL: '对局已结束',
  REVISION_CONFLICT: '对局状态已经变化',
};

/** 战局升温等级文案。level 只从后端读取，前端不重新计算。 */
export const ESCALATION_LEVEL_LABELS: Record<number, string> = {
  0: '0级',
  1: '1级',
  2: '2级',
  3: '3级',
  4: '4级',
};

export function labelTeam(team: TeamId): string {
  return TEAM_LABELS[team] ?? UNKNOWN_LABEL;
}

export function labelStrategy(intent: string | null | undefined): string | null {
  if (!intent) return null;
  return STRATEGY_LABELS[intent as StrategyIntent] ?? UNKNOWN_LABEL;
}

export function labelWeapon(weapon: string | null | undefined): string | null {
  if (!weapon) return null;
  return WEAPON_LABELS[weapon as WeaponId] ?? UNKNOWN_LABEL;
}

export function labelWeaponPreference(
  value: string | null | undefined,
): string | null {
  if (!value) return null;
  return WEAPON_PREFERENCE_LABELS[value as WeaponPreference] ?? UNKNOWN_LABEL;
}

export function labelShortTermGoal(
  value: string | null | undefined,
): string | null {
  if (!value) return null;
  return SHORT_TERM_GOAL_LABELS[value as ShortTermGoal] ?? UNKNOWN_LABEL;
}

export function labelRiskBudget(value: string | null | undefined): string | null {
  if (!value) return null;
  return RISK_BUDGET_LABELS[value as RiskBudget] ?? UNKNOWN_LABEL;
}

export function labelStrategyStatus(
  value: string | null | undefined,
): string | null {
  if (!value) return null;
  return STRATEGY_STATUS_LABELS[value as StrategyStatus] ?? UNKNOWN_LABEL;
}

export function labelDirection(direction: string): string {
  return DIRECTION_LABELS[direction as Direction] ?? UNKNOWN_LABEL;
}

export function labelMatchResult(
  result: string | null | undefined,
): string | null {
  if (!result) return null;
  return MATCH_RESULT_LABELS[result as MatchResult] ?? UNKNOWN_LABEL;
}

export function labelLifecycle(lifecycle: MatchLifecycle): string {
  return LIFECYCLE_LABELS[lifecycle] ?? UNKNOWN_LABEL;
}

export function labelRuleEffectType(type: string): string {
  return RULE_EFFECT_TYPE_LABELS[type as RuleEffectType] ?? UNKNOWN_LABEL;
}

export function labelSubmissionCode(code: string): string {
  return RULE_SUBMISSION_CODE_LABELS[code as RuleSubmissionCode] ?? UNKNOWN_LABEL;
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatSigned(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`;
}
