import type {
  AdvanceRequest,
  AdvanceResult,
  CreateMatchRequest,
  MatchSnapshot,
  ReplaySnapshot,
  RuleSubmissionRequest,
  RuleSubmissionResult,
} from './types';

/**
 * Transport-neutral command for a public rule mutation.
 *
 * `expectedRevision` comes from the frozen request body contract while
 * `idempotencyKey` represents the required `Idempotency-Key` transport header.
 * No HTTP behavior is implemented in this prep stage.
 */
export interface SubmitRuleCommand {
  matchId: string;
  expectedRevision: RuleSubmissionRequest['expected_revision'];
  idempotencyKey: string;
  playerText: RuleSubmissionRequest['player_text'];
}

/** Transport-neutral command for advancing exactly one complete round. */
export interface AdvanceMatchCommand {
  matchId: string;
  expectedRevision: AdvanceRequest['expected_revision'];
  idempotencyKey: string;
}

/**
 * Stable frontend seam for the five frozen V0.2 match operations.
 *
 * Current fixture/mock flows may implement or adapt to this boundary later.
 * The real HTTP implementation is intentionally blocked until Developer A A3
 * is READY and merged.
 */
export interface MatchApiAdapter {
  createMatch(seed?: CreateMatchRequest['seed']): Promise<MatchSnapshot>;
  getMatch(matchId: string): Promise<MatchSnapshot>;
  submitRule(command: SubmitRuleCommand): Promise<RuleSubmissionResult>;
  advanceMatch(command: AdvanceMatchCommand): Promise<AdvanceResult>;
  getReplay(matchId: string): Promise<ReplaySnapshot>;
}
