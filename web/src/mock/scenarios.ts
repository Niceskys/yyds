/**
 * B1 Mock 场景。
 *
 * 每个场景对应 contracts/fixtures/mvp-v0.2/ 中的一个 canonical fixture，
 * 让 UI 在没有真实后端（B4 之前）时也能覆盖
 * initial / PLAYER_DECISION / accepted / rejected / terminal / replay 状态。
 */
import {
  loadAdvanceResult,
  loadErrorEnvelope,
  loadMatchSnapshot,
  loadReplay,
  loadRuleSubmission,
} from '../contract/fixtures';
import {
  buildAdvanceViewModel,
  buildErrorViewModel,
  buildMatchViewModel,
  buildRuleFeedbackViewModel,
} from '../contract/mockAdapter';
import { buildReplayViewModel } from '../contract/replayAdapter';
import type {
  GameErrorViewModel,
  MatchViewModel,
  ReplayViewModel,
  RoundViewModel,
  RuleFeedbackViewModel,
} from '../contract/viewModel';

export type ScenarioId =
  | 'initial'
  | 'advance_round'
  | 'player_decision'
  | 'rule_accepted'
  | 'rule_rejected'
  | 'terminal'
  | 'revision_conflict'
  | 'replay_terminal';

export interface MockScenario {
  id: ScenarioId;
  label: string;
  description: string;
  /** 对应的 canonical fixture 相对路径，便于开发时核对数据来源。 */
  fixture: string;
}

export const MOCK_SCENARIOS: MockScenario[] = [
  {
    id: 'initial',
    label: '初始状态',
    description: '对局刚创建，第 1 回合尚未结算',
    fixture: 'contracts/fixtures/mvp-v0.2/match_initial.json',
  },
  {
    id: 'advance_round',
    label: '第 1 回合结算',
    description: '推进一个完整回合后的结果',
    fixture: 'contracts/fixtures/mvp-v0.2/advance_round.json',
  },
  {
    id: 'player_decision',
    label: '回合间决策',
    description: '可以提交规则或直接继续',
    fixture: 'contracts/fixtures/mvp-v0.2/match_player_decision.json',
  },
  {
    id: 'rule_accepted',
    label: '规则成功',
    description: '本回合间规则已生效，输入锁定',
    fixture: 'contracts/fixtures/mvp-v0.2/rule_accepted.json',
  },
  {
    id: 'rule_rejected',
    label: '规则被拒',
    description: '规则被拒绝，可以修改后重试',
    fixture: 'contracts/fixtures/mvp-v0.2/rule_rejected.json',
  },
  {
    id: 'terminal',
    label: '终局',
    description: '对局结束，禁止继续提交或推进',
    fixture: 'contracts/fixtures/mvp-v0.2/match_terminal.json',
  },
  {
    id: 'revision_conflict',
    label: '状态冲突',
    description: 'revision 冲突错误信封',
    fixture: 'contracts/fixtures/mvp-v0.2/error_revision_conflict.json',
  },
  {
    id: 'replay_terminal',
    label: '终局回放',
    description: 'ROUND → INTERMISSION → ROUND 时间线',
    fixture: 'contracts/fixtures/mvp-v0.2/replay_terminal.json',
  },
];

export interface GameViewState {
  match: MatchViewModel;
  lastRound: RoundViewModel | null;
  feedback: RuleFeedbackViewModel | null;
  error: GameErrorViewModel | null;
  replay: ReplayViewModel | null;
}

export function buildScenarioState(id: ScenarioId, debug: boolean): GameViewState {
  const empty: Pick<GameViewState, 'lastRound' | 'feedback' | 'error' | 'replay'> = {
    lastRound: null,
    feedback: null,
    error: null,
    replay: null,
  };

  switch (id) {
    case 'initial':
      return {
        ...empty,
        match: buildMatchViewModel(loadMatchSnapshot('match_initial'), { debug }),
      };
    case 'advance_round': {
      const advance = buildAdvanceViewModel(loadAdvanceResult(), { debug });
      return { ...empty, match: advance.match, lastRound: advance.round };
    }
    case 'player_decision':
      return {
        ...empty,
        match: buildMatchViewModel(loadMatchSnapshot('match_player_decision'), { debug }),
      };
    case 'rule_accepted': {
      const submission = loadRuleSubmission('rule_accepted');
      return {
        ...empty,
        match: buildMatchViewModel(submission.match, { debug }),
        feedback: buildRuleFeedbackViewModel(
          submission,
          loadMatchSnapshot('match_player_decision'),
        ),
      };
    }
    case 'rule_rejected': {
      const submission = loadRuleSubmission('rule_rejected');
      return {
        ...empty,
        match: buildMatchViewModel(submission.match, { debug }),
        feedback: buildRuleFeedbackViewModel(submission),
      };
    }
    case 'terminal':
      return {
        ...empty,
        match: buildMatchViewModel(loadMatchSnapshot('match_terminal'), { debug }),
      };
    case 'revision_conflict':
      return {
        ...empty,
        match: buildMatchViewModel(loadMatchSnapshot('match_player_decision'), { debug }),
        error: buildErrorViewModel(loadErrorEnvelope()),
      };
    case 'replay_terminal':
      return {
        ...empty,
        match: buildMatchViewModel(loadMatchSnapshot('match_terminal'), { debug }),
        replay: buildReplayViewModel(loadReplay(), debug),
      };
    default: {
      const exhaustive: never = id;
      throw new Error(`未知 Mock 场景：${String(exhaustive)}`);
    }
  }
}

export function findScenario(id: ScenarioId): MockScenario {
  const scenario = MOCK_SCENARIOS.find((item) => item.id === id);
  if (!scenario) throw new Error(`未注册的 Mock 场景：${id}`);
  return scenario;
}
