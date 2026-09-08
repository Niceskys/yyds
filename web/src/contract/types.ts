/**
 * 临时 UI 侧契约类型（mock 阶段）。
 *
 * ⚠️ 非 canonical source。
 * 唯一权威定义在 `src/rules_beyond/api_contract.py`（Pydantic）。
 * B4 接入真实 API 时，本文件必须由 OpenAPI generated types 替换，
 * 不允许长期人工维护第二套 API schema。
 *
 * 这里只声明前端读取 fixture / 未来 API 响应所需的字段，
 * 不承载任何游戏规则判断逻辑。
 */

export type TeamId = 'RED' | 'BLUE';
export type WeaponId = 'BOW' | 'KNIFE';
export type Direction = 'UP' | 'DOWN' | 'LEFT' | 'RIGHT';
export type StrategyIntent = 'PRESSURE' | 'KITE' | 'EVADE' | 'HOLD';
export type StrategyStatus =
  | 'ACCEPTED'
  | 'FALLBACK_MODEL_ERROR'
  | 'FALLBACK_PROTOCOL_ERROR';
export type WeaponPreference = 'KNIFE' | 'BOW' | 'ADAPTIVE';
export type RiskBudget = 'LOW' | 'MEDIUM' | 'HIGH';
export type ShortTermGoal = 'DAMAGE' | 'SURVIVE' | 'TRIGGER_RULE' | 'DENY_RULE';
export type MatchLifecycle =
  | 'RUNNING'
  | 'PLAYER_DECISION'
  | 'TERMINAL'
  | 'FAILED_RECOVERABLE';
export type MatchResult =
  | 'RED_WIN'
  | 'BLUE_WIN'
  | 'DRAW_MUTUAL_DEATH'
  | 'TIMEOUT';
export type RuleSubmissionCode =
  | 'ACCEPTED'
  | 'NO_CANDIDATE'
  | 'RULE_REJECTED'
  | 'FAITHFULNESS_REJECTED'
  | 'MODEL_UNAVAILABLE'
  | 'RULE_SUBMISSION_NOT_ALLOWED'
  | 'MATCH_TERMINAL'
  | 'REVISION_CONFLICT';
export type RuleEffectType =
  | 'MOVE_RANGE_ADD'
  | 'KNIFE_RANGE_ADD'
  | 'BOW_RANGE_ADD'
  | 'KNIFE_DAMAGE_ADD'
  | 'BOW_DAMAGE_ADD'
  | 'BOW_HIT_MULTIPLIER'
  | 'WEAPON_COOLDOWN';
export type IntermissionChoice = 'CONTINUE' | 'RULE_ATTEMPT';

export interface Position {
  row: number;
  col: number;
}

export interface BoardSize {
  rows: number;
  cols: number;
}

export interface UnitPublicView {
  team: TeamId;
  hp: number;
  position: Position;
}

export interface TeamUnitMap {
  RED: UnitPublicView;
  BLUE: UnitPublicView;
}

export interface PublicStrategyDecision {
  plan_version?: string;
  status?: StrategyStatus;
  intent?: StrategyIntent;
  target_distance?: number | null;
  weapon_preference?: WeaponPreference | null;
  risk_budget?: RiskBudget | null;
  short_term_goal?: ShortTermGoal | null;
  horizon_rounds?: number | null;
  contingency?: Record<string, string> | null;
  degraded?: boolean;
}

export interface TeamLatestStrategyMap {
  RED: PublicStrategyDecision | null;
  BLUE: PublicStrategyDecision | null;
}

export interface TeamRoundStrategyMap {
  RED: PublicStrategyDecision;
  BLUE: PublicStrategyDecision;
}

/**
 * 公共有效属性。
 * `conflict_level` / `hard_liveness` 属于机器可用状态，
 * 普通玩家 UI 不直接展示（只在 adapter 中读取用于过滤，不渲染）。
 */
export interface EffectiveStatsPublicView {
  move_range: number;
  knife_range: number;
  bow_range: number;
  knife_damage: number;
  bow_damage: number;
  bow_hit_multiplier: number;
  bow_hit_floor: number;
  cooldown_weapons: WeaponId[];
  conflict_level: number;
  hard_liveness: boolean;
}

export interface TeamStatsMap {
  RED: EffectiveStatsPublicView;
  BLUE: EffectiveStatsPublicView;
}

export interface BattleEscalationSnapshot {
  level: number;
  no_damage_streak: number;
  next_level_at_no_damage: number | null;
  rounds_until_next_level: number | null;
  hard_liveness_active: boolean;
}

export interface PlayerDecisionSnapshot {
  after_round: number | null;
  can_submit_rule: boolean;
  rule_changed_this_intermission: boolean;
  can_advance: boolean;
}

export interface RuleEffectPublicView {
  type: RuleEffectType;
  delta?: number | null;
  multiplier?: number | null;
  weapon?: 'KNIFE' | 'BOW' | 'NONE' | null;
  rounds?: number | null;
}

export interface RuleAstPublicView {
  version: string;
  target: 'ALL_UNITS';
  conditions: Array<{
    type: string;
    value?: number | null;
    weapon?: 'KNIFE' | 'BOW' | 'NONE' | null;
  }>;
  effect: RuleEffectPublicView;
  duration: 'UNTIL_REPLACED';
}

export interface RulePublicView {
  rule_id: string;
  player_text: string;
  ast: RuleAstPublicView;
}

export interface MatchSnapshot {
  schema_version: 'mvp-v0.2';
  match_id: string;
  revision: number;
  lifecycle: MatchLifecycle;
  seed: number;
  round_no: number;
  completed_rounds: number;
  score_rounds: number;
  rule_change_count: number;
  board: BoardSize;
  units: TeamUnitMap;
  active_rule: RulePublicView | null;
  player_decision: PlayerDecisionSnapshot;
  effective_stats: TeamStatsMap;
  latest_strategy: TeamLatestStrategyMap;
  battle_escalation: BattleEscalationSnapshot;
  result: MatchResult | null;
}

export interface ActionPublicView {
  move_path: Direction[];
  attack: WeaponId | null;
}

export interface TeamActionMap {
  RED: ActionPublicView;
  BLUE: ActionPublicView;
}

export interface RoundEventPublicView {
  event_version: string;
  kind: string;
  actor: TeamId | null;
  details: Record<string, unknown>;
}

export interface RoundExecutionPublicView {
  round_no: number;
  strategies: TeamRoundStrategyMap;
  actions: TeamActionMap;
  events: RoundEventPublicView[];
}

export interface AdvanceResult {
  schema_version: 'mvp-v0.2';
  round: RoundExecutionPublicView;
  match: MatchSnapshot;
}

export interface RuleSubmissionResult {
  schema_version: 'mvp-v0.2';
  accepted: boolean;
  public_code: RuleSubmissionCode;
  message: string;
  suggested_rephrase: string | null;
  candidate_preview: RuleAstPublicView | null;
  rule_id: string | null;
  match: MatchSnapshot;
}

export interface ErrorEnvelope {
  schema_version: 'mvp-v0.2';
  error: {
    code: string;
    message: string;
    retryable: boolean;
  };
}

export interface GameConfigPublicView {
  rows: number;
  cols: number;
  initial_hp: number;
  max_rounds: number;
  late_game_hard_round: number;
  base_move_range: number;
  base_knife_range: number;
  base_bow_range: number;
  knife_damage: number;
  bow_damage: number;
}

export interface ReplayRoundEntry {
  entry_type: 'ROUND';
  round_no: number;
  pre_round: MatchSnapshot;
  strategies: TeamRoundStrategyMap;
  actions: TeamActionMap;
  events: RoundEventPublicView[];
  post_round_units: TeamUnitMap;
  battle_escalation: BattleEscalationSnapshot;
  effective_stats: TeamStatsMap;
  result: MatchResult | null;
}

export interface ReplayIntermissionEntry {
  entry_type: 'INTERMISSION';
  after_round: number;
  choice: IntermissionChoice;
  submitted_player_text: string | null;
  submission_public_code: RuleSubmissionCode | null;
  accepted_rule_id: string | null;
  accepted_rule: RulePublicView | null;
  active_rule_before: RulePublicView | null;
  active_rule_after: RulePublicView | null;
  rule_change_count_after: number;
}

export type ReplayEntry = ReplayRoundEntry | ReplayIntermissionEntry;

export interface ReplaySnapshot {
  schema_version: 'mvp-v0.2';
  replay_version: 'replay-v0.2';
  match_id: string;
  seed: number;
  initial_config: GameConfigPublicView;
  timeline: ReplayEntry[];
  terminal_result: MatchResult | null;
  score_rounds: number;
  rule_change_count: number;
}
