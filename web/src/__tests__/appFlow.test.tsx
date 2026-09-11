import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from '../App';
import type {
  AdvanceMatchCommand,
  MatchApiAdapter,
  SubmitRuleCommand,
} from '../contract/apiAdapter';
import { MatchApiRequestError } from '../contract/httpApiAdapter';
import {
  loadAdvanceResult,
  loadMatchSnapshot,
  loadReplay,
  loadRuleSubmission,
} from '../contract/fixtures';
import type {
  AdvanceResult,
  CreateMatchRequest,
  MatchSnapshot,
  PublicStrategyDecision,
  ReplaySnapshot,
  RuleSubmissionResult,
} from '../contract/types';

interface ApiBehavior {
  create?: (seed?: CreateMatchRequest['seed']) => Promise<MatchSnapshot>;
  getMatch?: (matchId: string) => Promise<MatchSnapshot>;
  submitRule?: (command: SubmitRuleCommand) => Promise<RuleSubmissionResult>;
  advance?: (command: AdvanceMatchCommand) => Promise<AdvanceResult>;
  replay?: (matchId: string) => Promise<ReplaySnapshot>;
}

function makeRecordingApi(behavior: ApiBehavior = {}) {
  const calls = {
    create: [] as Array<CreateMatchRequest['seed'] | undefined>,
    getMatch: [] as string[],
    submitRule: [] as SubmitRuleCommand[],
    advance: [] as AdvanceMatchCommand[],
    replay: [] as string[],
  };

  const adapter: MatchApiAdapter = {
    async createMatch(seed) {
      calls.create.push(seed);
      return behavior.create?.(seed) ?? loadMatchSnapshot('match_initial');
    },
    async getMatch(matchId) {
      calls.getMatch.push(matchId);
      return behavior.getMatch?.(matchId) ?? loadMatchSnapshot('match_player_decision');
    },
    async submitRule(command) {
      calls.submitRule.push(command);
      return behavior.submitRule?.(command) ?? loadRuleSubmission('rule_accepted');
    },
    async advanceMatch(command) {
      calls.advance.push(command);
      return behavior.advance?.(command) ?? loadAdvanceResult();
    },
    async getReplay(matchId) {
      calls.replay.push(matchId);
      return behavior.replay?.(matchId) ?? loadReplay();
    },
  };

  return { adapter, calls };
}

function sequentialKeyFactory() {
  let count = 0;
  return () => {
    count += 1;
    return `test-key-${count}`;
  };
}

function degradedStrategy(strategy: PublicStrategyDecision | null): PublicStrategyDecision {
  if (!strategy) throw new Error('test fixture expected a public strategy');
  return {
    ...strategy,
    status: 'FALLBACK_MODEL_ERROR',
    degraded: true,
  };
}

async function startGame(
  api: MatchApiAdapter,
  keyFactory = sequentialKeyFactory(),
  roundTransitionDurationMs = 0,
) {
  render(
    <App
      api={api}
      idempotencyKeyFactory={keyFactory}
      roundTransitionDurationMs={roundTransitionDurationMs}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: '开始游戏' }));
  await screen.findByTestId('board-grid');
}

describe('真实 API 游玩流程', () => {
  it('初始页只显示产品入口，不出现 mock 场景控制', () => {
    const { adapter } = makeRecordingApi();
    render(<App api={adapter} />);
    expect(screen.getByRole('heading', { name: '《规则之外》' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始游戏' })).toBeInTheDocument();
    expect(screen.queryByText(/Mock/)).toBeNull();
    expect(screen.queryByText('排行榜')).toBeNull();
  });

  it('开始游戏只 create match；第 1 回合前规则不可提交，继续按钮可用', async () => {
    const { adapter, calls } = makeRecordingApi();
    await startGame(adapter);

    expect(calls.create).toHaveLength(1);
    expect(calls.advance).toHaveLength(0);
    expect(screen.getByTestId('lifecycle')).toHaveTextContent('战斗进行中');
    expect(screen.getByTestId('completed-rounds')).toHaveTextContent('0');
    expect(screen.getByTestId('rule-input')).toBeDisabled();
    expect(screen.getByTestId('submit-rule')).toBeDisabled();
    expect(screen.getByTestId('advance-round')).not.toBeDisabled();
    expect(screen.getByTestId('rule-input-hint')).toHaveTextContent('第 1 回合开始前不能制定规则');
  });

  it('第一次继续真实调用 advance，完成 Round 1 后进入 PLAYER_DECISION', async () => {
    const { adapter, calls } = makeRecordingApi();
    await startGame(adapter);

    fireEvent.click(screen.getByTestId('advance-round'));

    await waitFor(() => expect(screen.getByTestId('completed-rounds')).toHaveTextContent('1'));
    expect(calls.advance).toEqual([
      {
        matchId: 'match_fixture_001',
        expectedRevision: 0,
        idempotencyKey: 'test-key-1',
      },
    ]);
    expect(screen.getByTestId('lifecycle')).toHaveTextContent('等待你的决策');
    expect(screen.getByTestId('rule-input')).not.toBeDisabled();
    expect(screen.getByTestId('round-summary')).toHaveTextContent('第 1 回合结果');
    expect(screen.getByTestId('round-summary')).toHaveTextContent('公开事件');
  });

  it('accepted rule 是独立 mutation，不自动推进下一回合，并使用新的 key', async () => {
    const { adapter, calls } = makeRecordingApi();
    await startGame(adapter);
    fireEvent.click(screen.getByTestId('advance-round'));
    await waitFor(() => expect(screen.getByTestId('rule-input')).not.toBeDisabled());

    fireEvent.change(screen.getByTestId('rule-input'), {
      target: { value: '双方移动距离增加1格。' },
    });
    fireEvent.click(screen.getByTestId('submit-rule'));

    await waitFor(() => expect(screen.getByTestId('rule-change-count')).toHaveTextContent('1'));
    expect(calls.advance).toHaveLength(1);
    expect(calls.submitRule).toHaveLength(1);
    expect(calls.submitRule[0].expectedRevision).toBe(1);
    expect(calls.submitRule[0].idempotencyKey).toBe('test-key-2');
    expect(screen.getByTestId('rule-feedback')).toHaveTextContent('规则已生效');
    expect(screen.getByTestId('advance-round')).not.toBeDisabled();
  });

  it('503 不推进本地 snapshot；用户重试同一次 advance 时复用 Idempotency-Key', async () => {
    let attempts = 0;
    const { adapter, calls } = makeRecordingApi({
      async advance() {
        attempts += 1;
        if (attempts === 1) {
          throw new MatchApiRequestError({
            code: 'INTERNAL_ERROR',
            message: 'raw provider detail must stay hidden',
            retryable: true,
            status: 503,
          });
        }
        return loadAdvanceResult();
      },
    });
    await startGame(adapter);

    fireEvent.click(screen.getByTestId('advance-round'));
    await screen.findByTestId('game-error');
    expect(screen.getByTestId('completed-rounds')).toHaveTextContent('0');
    expect(screen.getByTestId('game-error')).toHaveTextContent('本回合未安全完成，请稍后重试');
    expect(document.body.textContent).not.toContain('raw provider detail');

    fireEvent.click(screen.getByTestId('advance-round'));
    await waitFor(() => expect(screen.getByTestId('completed-rounds')).toHaveTextContent('1'));
    expect(calls.advance).toHaveLength(2);
    expect(calls.advance[0].idempotencyKey).toBe('test-key-1');
    expect(calls.advance[1].idempotencyKey).toBe('test-key-1');
  });

  it('409 revision conflict 不自动重放旧 mutation，而是 GET 最新 snapshot', async () => {
    const { adapter, calls } = makeRecordingApi({
      async advance() {
        throw new MatchApiRequestError({
          code: 'REVISION_CONFLICT',
          message: 'developer-only revision details',
          retryable: true,
          status: 409,
        });
      },
      async getMatch() {
        return loadMatchSnapshot('match_player_decision');
      },
    });
    await startGame(adapter);

    fireEvent.click(screen.getByTestId('advance-round'));

    await waitFor(() => expect(screen.getByTestId('completed-rounds')).toHaveTextContent('1'));
    expect(calls.advance).toHaveLength(1);
    expect(calls.getMatch).toEqual(['match_fixture_001']);
    expect(screen.getByTestId('game-error')).toHaveTextContent('对局状态已经变化');
    expect(document.body.textContent).not.toContain('developer-only revision details');
  });

  it('strategy fallback 是 200 正常 round，并以中文非阻断提示展示', async () => {
    const base = loadAdvanceResult();
    const degradedLatest = degradedStrategy(base.match.latest_strategy.RED);
    const degradedRound = degradedStrategy(base.round.strategies.RED);
    const degraded: AdvanceResult = {
      ...base,
      match: {
        ...base.match,
        latest_strategy: {
          ...base.match.latest_strategy,
          RED: degradedLatest,
        },
      },
      round: {
        ...base.round,
        strategies: {
          ...base.round.strategies,
          RED: degradedRound,
        },
      },
    };
    const { adapter } = makeRecordingApi({ advance: async () => degraded });
    await startGame(adapter);

    fireEvent.click(screen.getByTestId('advance-round'));

    await screen.findByTestId('game-notice');
    expect(screen.getByTestId('game-notice')).toHaveTextContent('已使用降级策略继续完成对局');
    expect(screen.queryByTestId('game-error')).toBeNull();
    expect(document.body.textContent).toContain('模型不可用，已回退');
  });

  it('MODEL_UNAVAILABLE 是 200 业务结果：不增加 revision/rule count，仍允许重新提交', async () => {
    const rejected = loadRuleSubmission('rule_rejected');
    const modelUnavailable: RuleSubmissionResult = {
      ...rejected,
      public_code: 'MODEL_UNAVAILABLE',
      message: '模型暂时不可用，请稍后重试。',
      suggested_rephrase: null,
    };
    const { adapter, calls } = makeRecordingApi({
      submitRule: async () => modelUnavailable,
    });
    await startGame(adapter);
    fireEvent.click(screen.getByTestId('advance-round'));
    await waitFor(() => expect(screen.getByTestId('rule-input')).not.toBeDisabled());

    fireEvent.change(screen.getByTestId('rule-input'), {
      target: { value: '双方移动距离增加1格。' },
    });
    fireEvent.click(screen.getByTestId('submit-rule'));

    await waitFor(() => expect(screen.getByTestId('rule-feedback')).toHaveTextContent('规则模型暂时不可用'));
    expect(screen.getByTestId('rule-feedback')).toHaveAttribute(
      'data-feedback-tone',
      'unavailable',
    );
    expect(screen.getByTestId('rule-feedback-guidance')).toHaveTextContent(
      '本次没有修改公共规则',
    );
    expect(screen.queryByTestId('game-notice')).toBeNull();
    expect(screen.getByTestId('rule-change-count')).toHaveTextContent('0');
    expect(screen.getByTestId('rule-input')).not.toBeDisabled();
    expect(calls.submitRule).toHaveLength(1);
    expect(calls.submitRule[0].expectedRevision).toBe(1);
  });

  it('mutation loading 阻止重复点击生成多个不同 key', async () => {
    let resolveAdvance!: (value: AdvanceResult) => void;
    const pending = new Promise<AdvanceResult>((resolve) => {
      resolveAdvance = resolve;
    });
    const { adapter, calls } = makeRecordingApi({ advance: async () => pending });
    await startGame(adapter);

    const advanceButton = screen.getByTestId('advance-round');
    fireEvent.click(advanceButton);
    expect(advanceButton).toBeDisabled();
    fireEvent.click(advanceButton);
    expect(calls.advance).toHaveLength(1);

    await act(async () => {
      resolveAdvance(loadAdvanceResult());
      await pending;
    });
    await waitFor(() => expect(screen.getByTestId('completed-rounds')).toHaveTextContent('1'));
  });

  it('回合演出展示公开因果变化，并在结束前阻止重复 mutation', async () => {
    const { adapter, calls } = makeRecordingApi();
    await startGame(adapter, sequentialKeyFactory(), 60);

    fireEvent.click(screen.getByTestId('advance-round'));

    const transition = await screen.findByTestId('round-transition');
    expect(transition).toHaveTextContent('第 1 回合发生了什么');
    expect(transition).toHaveTextContent('公开行动');
    expect(transition).toHaveTextContent('位置保持在 第 3 行，第 2 列');
    expect(transition).toHaveTextContent('生命值保持 4');
    expect(transition).toHaveTextContent('生命值 4 → 3（-1）');
    const advanceButton = screen.getByTestId('advance-round');
    expect(advanceButton).toBeDisabled();
    fireEvent.click(advanceButton);
    expect(calls.advance).toHaveLength(1);

    await waitFor(() => expect(screen.queryByTestId('round-transition')).toBeNull());
    expect(screen.getByTestId('completed-rounds')).toHaveTextContent('1');
    expect(advanceButton).not.toBeDisabled();
  });

  it('advance 返回升温变化时只在回合演出期展示提示', async () => {
    const base = loadAdvanceResult();
    const escalated: AdvanceResult = {
      ...base,
      match: {
        ...base.match,
        battle_escalation: {
          ...base.match.battle_escalation,
          level: 1,
          no_damage_streak: 3,
          next_level_at_no_damage: 6,
          rounds_until_next_level: 3,
        },
      },
    };
    const { adapter } = makeRecordingApi({ advance: async () => escalated });
    await startGame(adapter, sequentialKeyFactory(), 60);

    fireEvent.click(screen.getByTestId('advance-round'));

    const change = await screen.findByTestId('escalation-change');
    expect(change).toHaveTextContent('等级 0级 → 1级');
    expect(screen.getByTestId('escalation')).toHaveAttribute('data-level', '1');
    await waitFor(() => expect(screen.queryByTestId('escalation-change')).toBeNull());
    expect(screen.getByTestId('escalation')).toHaveAttribute('data-changed', 'false');
  });

  it('reduced-motion 下直接显示 authoritative snapshot，不等待演出', async () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({ matches: true }),
    );
    try {
      const { adapter } = makeRecordingApi();
      await startGame(adapter, sequentialKeyFactory(), 1000);

      fireEvent.click(screen.getByTestId('advance-round'));

      await waitFor(() => expect(screen.getByTestId('completed-rounds')).toHaveTextContent('1'));
      expect(screen.queryByTestId('round-transition')).toBeNull();
      expect(screen.getByTestId('advance-round')).not.toBeDisabled();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('查看回放调用真实 getReplay，而不是从当前 UI 状态反推', async () => {
    const { adapter, calls } = makeRecordingApi();
    await startGame(adapter);

    fireEvent.click(screen.getByRole('button', { name: '查看本局回放' }));

    await screen.findByRole('heading', { name: '本局回放' });
    expect(calls.replay).toEqual(['match_fixture_001']);
    expect(screen.getByTestId('replay-timeline')).toBeInTheDocument();
  });
});
