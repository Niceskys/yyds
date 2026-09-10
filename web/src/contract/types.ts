/**
 * 前端公共契约类型入口。
 *
 * Canonical source：`src/rules_beyond/api_contract.py`
 * 派生 OpenAPI：`contracts/openapi/mvp-v0.2.json`
 * 机器生成 TS：`./generated/api.ts`
 *
 * 本文件只提供薄 alias / presentation typing glue，不再人工维护第二套 API schema。
 * `generated/api.ts` 禁止手工编辑。
 */
import type { components } from './generated/api';

type Schemas = components['schemas'];

export type TeamId = Schemas['TeamPublic'];
export type WeaponId = Schemas['WeaponPublic'];
export type Direction = Schemas['DirectionPublic'];
export type StrategyIntent = Schemas['StrategyIntentPublic'];
export type StrategyStatus = Schemas['StrategyDecisionStatusPublic'];
export type WeaponPreference = Schemas['WeaponPreferencePublic'];
export type RiskBudget = Schemas['RiskBudgetPublic'];
export type ShortTermGoal = Schemas['ShortTermGoalPublic'];
export type MatchLifecycle = Schemas['MatchLifecycle'];
export type MatchResult = Schemas['MatchResultPublic'];
export type RuleSubmissionCode = Schemas['RuleSubmissionCode'];
export type RuleEffectType = Schemas['RuleEffectTypePublic'];
export type IntermissionChoice = Schemas['IntermissionChoicePublic'];
export type ErrorCode = Schemas['ErrorCode'];

export type Position = Schemas['PositionSnapshot'];
export type BoardSize = Schemas['BoardSnapshot'];
export type UnitPublicView = Schemas['UnitSnapshot'];
export type TeamUnitMap = Schemas['TeamUnitMap'];
export type PublicStrategyDecision = Schemas['PublicStrategyDecision'];
export type TeamLatestStrategyMap = Schemas['TeamLatestStrategyMap'];
export type TeamRoundStrategyMap = Schemas['TeamRoundStrategyMap'];
export type EffectiveStatsPublicView = Schemas['EffectiveStatsPublicView'];
export type TeamStatsMap = Schemas['TeamStatsMap'];
export type BattleEscalationSnapshot = Schemas['BattleEscalationSnapshot'];
export type PlayerDecisionSnapshot = Schemas['PlayerDecisionSnapshot'];
export type RuleEffectPublicView = Schemas['RuleEffectPublicView'];
export type RuleAstPublicView = Schemas['RuleAstPublicView'];
export type RulePublicView = Schemas['RulePublicView'];
export type MatchSnapshot = Schemas['MatchSnapshot'];
export type ActionPublicView = Schemas['ActionPublicView'];
export type TeamActionMap = Schemas['TeamActionMap'];
export type RoundEventPublicView = Schemas['RoundEventPublicView'];
export type RoundExecutionPublicView = Schemas['RoundExecutionPublicView'];
export type AdvanceResult = Schemas['AdvanceResult'];
export type RuleSubmissionResult = Schemas['RuleSubmissionResult'];
export type ErrorEnvelope = Schemas['ErrorEnvelope'];
export type CreateMatchRequest = Schemas['CreateMatchRequest'];
export type AdvanceRequest = Schemas['AdvanceRequest'];
export type RuleSubmissionRequest = Schemas['RuleSubmissionRequest'];
export type GameConfigPublicView = Schemas['GameConfigPublicView'];
export type ReplayRoundEntry = Schemas['ReplayRoundEntry'];
export type ReplayIntermissionEntry = Schemas['ReplayIntermissionEntry'];
export type ReplayEntry = ReplayRoundEntry | ReplayIntermissionEntry;
export type ReplaySnapshot = Schemas['ReplaySnapshot'];
