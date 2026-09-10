import { describe, expect, it } from 'vitest';

import type { components } from '../contract/generated/api';
import type {
  AdvanceResult,
  MatchSnapshot,
  ReplaySnapshot,
  RuleSubmissionResult,
} from '../contract/types';
import type {
  AdvanceMatchCommand,
  MatchApiAdapter,
  SubmitRuleCommand,
} from '../contract/apiAdapter';
import {
  loadAdvanceResult,
  loadMatchSnapshot,
  loadReplay,
  loadRuleSubmission,
} from '../contract/fixtures';

describe('generated OpenAPI contract boundary', () => {
  it('公共 DTO alias 直接兼容 generated schema', () => {
    const match: MatchSnapshot = loadMatchSnapshot('match_player_decision');
    const generatedMatch: components['schemas']['MatchSnapshot'] = match;

    const advance: AdvanceResult = loadAdvanceResult();
    const generatedAdvance: components['schemas']['AdvanceResult'] = advance;

    const rule: RuleSubmissionResult = loadRuleSubmission('rule_accepted');
    const generatedRule: components['schemas']['RuleSubmissionResult'] = rule;

    const replay: ReplaySnapshot = loadReplay();
    const generatedReplay: components['schemas']['ReplaySnapshot'] = replay;

    expect(generatedMatch.schema_version).toBe('mvp-v0.2');
    expect(generatedAdvance.schema_version).toBe('mvp-v0.2');
    expect(generatedRule.schema_version).toBe('mvp-v0.2');
    expect(generatedReplay.replay_version).toBe('replay-v0.2');
  });

  it('adapter seam 保留五个操作与 mutation revision/idempotency 参数', async () => {
    let lastRuleCommand: SubmitRuleCommand | null = null;
    let lastAdvanceCommand: AdvanceMatchCommand | null = null;

    const adapter: MatchApiAdapter = {
      async createMatch() {
        return loadMatchSnapshot('match_initial');
      },
      async getMatch() {
        return loadMatchSnapshot('match_player_decision');
      },
      async submitRule(command) {
        lastRuleCommand = command;
        return loadRuleSubmission('rule_accepted');
      },
      async advanceMatch(command) {
        lastAdvanceCommand = command;
        return loadAdvanceResult();
      },
      async getReplay() {
        return loadReplay();
      },
    };

    const created = await adapter.createMatch(123);
    const current = await adapter.getMatch(created.match_id);
    const rule = await adapter.submitRule({
      matchId: current.match_id,
      expectedRevision: current.revision,
      idempotencyKey: 'rule-test-key',
      playerText: '移动距离增加1格。',
    });
    const advanced = await adapter.advanceMatch({
      matchId: rule.match.match_id,
      expectedRevision: rule.match.revision,
      idempotencyKey: 'advance-test-key',
    });
    const replay = await adapter.getReplay(advanced.match.match_id);

    expect(lastRuleCommand).toEqual({
      matchId: current.match_id,
      expectedRevision: current.revision,
      idempotencyKey: 'rule-test-key',
      playerText: '移动距离增加1格。',
    });
    expect(lastAdvanceCommand).toEqual({
      matchId: rule.match.match_id,
      expectedRevision: rule.match.revision,
      idempotencyKey: 'advance-test-key',
    });
    expect(replay.replay_version).toBe('replay-v0.2');
  });
});
