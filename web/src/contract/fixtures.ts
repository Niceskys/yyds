/**
 * V0.2 fixture 读取入口。
 *
 * fixture 的 canonical 位置在仓库根目录：
 *   contracts/fixtures/mvp-v0.2/
 * web/ 内不复制第二套数据，避免与后端生成器漂移。
 */
import type {
  AdvanceResult,
  ErrorEnvelope,
  MatchSnapshot,
  ReplaySnapshot,
  RuleSubmissionResult,
} from './types';

/** 相对仓库根目录的 canonical fixture 目录。 */
export const FIXTURE_DIR = 'contracts/fixtures/mvp-v0.2';

export const FIXTURE_FILE_NAMES = {
  match_initial: 'match_initial.json',
  match_player_decision: 'match_player_decision.json',
  rule_accepted: 'rule_accepted.json',
  rule_rejected: 'rule_rejected.json',
  match_terminal: 'match_terminal.json',
  error_revision_conflict: 'error_revision_conflict.json',
  advance_round: 'advance_round.json',
  replay_terminal: 'replay_terminal.json',
} as const;

export type FixtureName = keyof typeof FIXTURE_FILE_NAMES;

// 注意：import.meta.glob 只接受字面量，不能用变量拼接。
const fixtureModules = import.meta.glob('../../../contracts/fixtures/mvp-v0.2/*.json', {
  eager: true,
  import: 'default',
}) as Record<string, unknown>;

export function fixtureFileName(name: FixtureName): string {
  return FIXTURE_FILE_NAMES[name];
}

export function fixtureDisplayPath(name: FixtureName): string {
  return `${FIXTURE_DIR}/${FIXTURE_FILE_NAMES[name]}`;
}

/** 读取一个 checked-in V0.2 fixture。找不到时明确抛错，不静默返回空对象。 */
export function loadFixture<T>(name: FixtureName): T {
  const fileName = FIXTURE_FILE_NAMES[name];
  const entry = Object.entries(fixtureModules).find(([path]) =>
    path.endsWith(`/${fileName}`),
  );
  if (!entry) {
    throw new Error(`未找到 V0.2 fixture: ${fixtureDisplayPath(name)}`);
  }
  return entry[1] as T;
}

export function loadMatchSnapshot(name: FixtureName): MatchSnapshot {
  return loadFixture<MatchSnapshot>(name);
}

export function loadRuleSubmission(name: FixtureName): RuleSubmissionResult {
  return loadFixture<RuleSubmissionResult>(name);
}

export function loadAdvanceResult(): AdvanceResult {
  return loadFixture<AdvanceResult>('advance_round');
}

export function loadReplay(): ReplaySnapshot {
  return loadFixture<ReplaySnapshot>('replay_terminal');
}

export function loadErrorEnvelope(): ErrorEnvelope {
  return loadFixture<ErrorEnvelope>('error_revision_conflict');
}
