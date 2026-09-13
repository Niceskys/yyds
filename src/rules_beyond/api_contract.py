from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

SCHEMA_VERSION = "mvp-v0.2"
REPLAY_VERSION = "replay-v0.2"
EVENT_VERSION = "event-v0.1"
CURRENT_PLAN_VERSION = "intent-v0.1"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TeamPublic(str, Enum):
    RED = "RED"
    BLUE = "BLUE"


class DirectionPublic(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class WeaponPublic(str, Enum):
    KNIFE = "KNIFE"
    BOW = "BOW"


class MatchResultPublic(str, Enum):
    RED_WIN = "RED_WIN"
    BLUE_WIN = "BLUE_WIN"
    DRAW_MUTUAL_DEATH = "DRAW_MUTUAL_DEATH"
    TIMEOUT = "TIMEOUT"


class MatchLifecycle(str, Enum):
    RUNNING = "RUNNING"
    PLAYER_DECISION = "PLAYER_DECISION"
    TERMINAL = "TERMINAL"
    FAILED_RECOVERABLE = "FAILED_RECOVERABLE"


class RuleTargetPublic(str, Enum):
    ALL_UNITS = "ALL_UNITS"


class RuleDurationPublic(str, Enum):
    UNTIL_REPLACED = "UNTIL_REPLACED"


class RuleConditionTypePublic(str, Enum):
    SELF_HP_LTE = "SELF_HP_LTE"
    SELF_HP_GTE = "SELF_HP_GTE"
    SELF_HP_LT_OPPONENT = "SELF_HP_LT_OPPONENT"
    SELF_HP_GT_OPPONENT = "SELF_HP_GT_OPPONENT"
    DISTANCE_LTE = "DISTANCE_LTE"
    DISTANCE_GTE = "DISTANCE_GTE"
    ROUND_GTE = "ROUND_GTE"
    DID_NOT_MOVE_LAST_ROUND = "DID_NOT_MOVE_LAST_ROUND"
    LAST_ATTACK_WEAPON_IS = "LAST_ATTACK_WEAPON_IS"
    CONSECUTIVE_BOW_MISS_GTE = "CONSECUTIVE_BOW_MISS_GTE"
    CONSECUTIVE_SAME_WEAPON_USE_GTE = "CONSECUTIVE_SAME_WEAPON_USE_GTE"


class RuleEffectTypePublic(str, Enum):
    MOVE_RANGE_ADD = "MOVE_RANGE_ADD"
    KNIFE_RANGE_ADD = "KNIFE_RANGE_ADD"
    BOW_RANGE_ADD = "BOW_RANGE_ADD"
    KNIFE_DAMAGE_ADD = "KNIFE_DAMAGE_ADD"
    BOW_DAMAGE_ADD = "BOW_DAMAGE_ADD"
    BOW_HIT_MULTIPLIER = "BOW_HIT_MULTIPLIER"
    WEAPON_COOLDOWN = "WEAPON_COOLDOWN"


class RuleWeaponPublic(str, Enum):
    KNIFE = "KNIFE"
    BOW = "BOW"
    NONE = "NONE"


class StrategyIntentPublic(str, Enum):
    PRESSURE = "PRESSURE"
    KITE = "KITE"
    EVADE = "EVADE"
    HOLD = "HOLD"


class StrategyDecisionStatusPublic(str, Enum):
    ACCEPTED = "ACCEPTED"
    FALLBACK_MODEL_ERROR = "FALLBACK_MODEL_ERROR"
    FALLBACK_PROTOCOL_ERROR = "FALLBACK_PROTOCOL_ERROR"


class WeaponPreferencePublic(str, Enum):
    KNIFE = "KNIFE"
    BOW = "BOW"
    ADAPTIVE = "ADAPTIVE"


class RiskBudgetPublic(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ShortTermGoalPublic(str, Enum):
    DAMAGE = "DAMAGE"
    SURVIVE = "SURVIVE"
    TRIGGER_RULE = "TRIGGER_RULE"
    DENY_RULE = "DENY_RULE"


class RuleSubmissionCode(str, Enum):
    ACCEPTED = "ACCEPTED"
    NO_CANDIDATE = "NO_CANDIDATE"
    RULE_REJECTED = "RULE_REJECTED"
    FAITHFULNESS_REJECTED = "FAITHFULNESS_REJECTED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RULE_SUBMISSION_NOT_ALLOWED = "RULE_SUBMISSION_NOT_ALLOWED"
    MATCH_TERMINAL = "MATCH_TERMINAL"
    REVISION_CONFLICT = "REVISION_CONFLICT"


class ErrorCode(str, Enum):
    REVISION_CONFLICT = "REVISION_CONFLICT"
    RULE_SUBMISSION_NOT_ALLOWED = "RULE_SUBMISSION_NOT_ALLOWED"
    ADVANCE_NOT_ALLOWED = "ADVANCE_NOT_ALLOWED"
    MATCH_TERMINAL = "MATCH_TERMINAL"
    MATCH_NOT_FOUND = "MATCH_NOT_FOUND"
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
    INVALID_REQUEST = "INVALID_REQUEST"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class PositionSnapshot(ContractModel):
    row: int = Field(ge=1)
    col: int = Field(ge=1)


class UnitSnapshot(ContractModel):
    team: TeamPublic
    hp: int = Field(ge=0)
    position: PositionSnapshot


class BoardSnapshot(ContractModel):
    rows: int = Field(ge=1)
    cols: int = Field(ge=1)


class EffectiveStatsPublicView(ContractModel):
    move_range: int = Field(ge=0)
    knife_range: int = Field(ge=0)
    bow_range: int = Field(ge=0)
    knife_damage: int = Field(ge=0)
    bow_damage: int = Field(ge=0)
    bow_hit_multiplier: float = Field(ge=0.0)
    bow_hit_floor: float = Field(ge=0.0, le=1.0)
    cooldown_weapons: list[WeaponPublic] = Field(default_factory=list)
    conflict_level: int = Field(ge=0, le=4)
    hard_liveness: bool


class RuleConditionPublicView(ContractModel):
    type: RuleConditionTypePublic
    value: int | None = None
    weapon: RuleWeaponPublic | None = None


class RuleEffectPublicView(ContractModel):
    type: RuleEffectTypePublic
    delta: int | None = None
    multiplier: float | None = None
    weapon: RuleWeaponPublic | None = None
    rounds: int | None = None


class RuleAstPublicView(ContractModel):
    version: str
    target: RuleTargetPublic
    conditions: list[RuleConditionPublicView]
    effect: RuleEffectPublicView
    duration: RuleDurationPublic


class RulePublicView(ContractModel):
    rule_id: str = Field(min_length=1)
    player_text: str
    ast: RuleAstPublicView


class PublicStrategyDecision(ContractModel):
    plan_version: str = Field(default=CURRENT_PLAN_VERSION, min_length=1)
    status: StrategyDecisionStatusPublic
    intent: StrategyIntentPublic
    target_distance: int | None = Field(default=None, ge=1)
    weapon_preference: WeaponPreferencePublic | None = None
    risk_budget: RiskBudgetPublic | None = None
    short_term_goal: ShortTermGoalPublic | None = None
    horizon_rounds: int | None = Field(default=None, ge=1, le=3)
    contingency: dict[str, str] | None = None
    degraded: bool = False


class TeamUnitMap(ContractModel):
    RED: UnitSnapshot
    BLUE: UnitSnapshot


class TeamStatsMap(ContractModel):
    RED: EffectiveStatsPublicView
    BLUE: EffectiveStatsPublicView


class TeamLatestStrategyMap(ContractModel):
    RED: PublicStrategyDecision | None
    BLUE: PublicStrategyDecision | None


class TeamRoundStrategyMap(ContractModel):
    RED: PublicStrategyDecision
    BLUE: PublicStrategyDecision


class PlayerDecisionSnapshot(ContractModel):
    after_round: int | None = Field(default=None, ge=1)
    can_submit_rule: bool
    rule_changed_this_intermission: bool
    can_advance: bool


class BattleEscalationSnapshot(ContractModel):
    level: int = Field(ge=0, le=4)
    no_damage_streak: int = Field(ge=0)
    next_level_at_no_damage: int | None = Field(default=None, ge=1)
    rounds_until_next_level: int | None = Field(default=None, ge=0)
    hard_liveness_active: bool


class MatchSnapshot(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    match_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    lifecycle: MatchLifecycle
    seed: int
    round_no: int = Field(ge=1)
    completed_rounds: int = Field(ge=0)
    score_rounds: int = Field(ge=0)
    rule_change_count: int = Field(ge=0)
    board: BoardSnapshot
    units: TeamUnitMap
    active_rule: RulePublicView | None
    player_decision: PlayerDecisionSnapshot
    effective_stats: TeamStatsMap
    latest_strategy: TeamLatestStrategyMap
    battle_escalation: BattleEscalationSnapshot
    result: MatchResultPublic | None


class CreateMatchRequest(ContractModel):
    seed: int | None = None


class RuleSubmissionRequest(ContractModel):
    expected_revision: int = Field(ge=0)
    player_text: str = Field(min_length=1)


class RuleSubmissionResult(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    accepted: bool
    public_code: RuleSubmissionCode
    message: str
    suggested_rephrase: str | None = None
    candidate_preview: RuleAstPublicView | None = None
    rule_id: str | None = None
    match: MatchSnapshot


class ActionPublicView(ContractModel):
    move_path: list[DirectionPublic] = Field(default_factory=list)
    attack: WeaponPublic | None = None


class TeamActionMap(ContractModel):
    RED: ActionPublicView
    BLUE: ActionPublicView


class RoundEventPublicView(ContractModel):
    event_version: Literal[EVENT_VERSION] = EVENT_VERSION
    kind: str = Field(min_length=1)
    actor: TeamPublic | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)


class AdvanceRequest(ContractModel):
    expected_revision: int = Field(ge=0)


class RoundExecutionPublicView(ContractModel):
    round_no: int = Field(ge=1)
    strategies: TeamRoundStrategyMap
    actions: TeamActionMap
    events: list[RoundEventPublicView]


class AdvanceResult(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    round: RoundExecutionPublicView
    match: MatchSnapshot


class GameConfigPublicView(ContractModel):
    rows: int = Field(ge=1)
    cols: int = Field(ge=1)
    initial_hp: int = Field(ge=1)
    max_rounds: int = Field(ge=1)
    late_game_hard_round: int = Field(ge=1)
    base_move_range: int = Field(ge=0)
    base_knife_range: int = Field(ge=0)
    base_bow_range: int = Field(ge=0)
    knife_damage: int = Field(ge=0)
    bow_damage: int = Field(ge=0)


class IntermissionChoicePublic(str, Enum):
    CONTINUE = "CONTINUE"
    RULE_ATTEMPT = "RULE_ATTEMPT"


class ReplayIntermissionEntry(ContractModel):
    entry_type: Literal["INTERMISSION"] = "INTERMISSION"
    after_round: int = Field(ge=1)
    choice: IntermissionChoicePublic
    submitted_player_text: str | None = None
    submission_public_code: RuleSubmissionCode | None = None
    accepted_rule_id: str | None = None
    accepted_rule: RulePublicView | None = None
    active_rule_before: RulePublicView | None = None
    active_rule_after: RulePublicView | None = None
    rule_change_count_after: int = Field(ge=0)


class ReplayRoundEntry(ContractModel):
    entry_type: Literal["ROUND"] = "ROUND"
    round_no: int = Field(ge=1)
    pre_round: MatchSnapshot
    strategies: TeamRoundStrategyMap
    actions: TeamActionMap
    events: list[RoundEventPublicView]
    post_round_units: TeamUnitMap
    battle_escalation: BattleEscalationSnapshot
    effective_stats: TeamStatsMap
    result: MatchResultPublic | None


ReplayEntry = Annotated[
    ReplayIntermissionEntry | ReplayRoundEntry,
    Field(discriminator="entry_type"),
]


class ReplaySnapshot(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    replay_version: Literal[REPLAY_VERSION] = REPLAY_VERSION
    match_id: str = Field(min_length=1)
    seed: int
    initial_config: GameConfigPublicView
    timeline: list[ReplayEntry]
    terminal_result: MatchResultPublic | None
    score_rounds: int = Field(ge=0)
    rule_change_count: int = Field(ge=0)


class ErrorDetail(ContractModel):
    code: ErrorCode
    message: str
    retryable: bool


class ErrorEnvelope(ContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    error: ErrorDetail
