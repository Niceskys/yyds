/**
 * UI 展示层 ViewModel。
 *
 * 这一层只服务渲染：
 * - 不包含任何游戏规则计算；
 * - 不复制完整 API schema；
 * - B4 接入真实 API 时由 API Adapter 产出同样的 ViewModel。
 */
import type { MatchLifecycle, MatchResult, RuleSubmissionCode, TeamId } from './types';

export interface StatViewModel {
  key: string;
  label: string;
  value: string;
}

export interface StrategyViewModel {
  label: string;
  statusLabel: string | null;
  degraded: boolean;
  shortTermGoalLabel: string | null;
  weaponPreferenceLabel: string | null;
  riskBudgetLabel: string | null;
  targetDistance: number | null;
  debugRaw: string | null;
}

export interface TeamViewModel {
  team: TeamId;
  teamLabel: string;
  hp: number;
  position: { row: number; col: number };
  positionLabel: string;
  strategy: StrategyViewModel | null;
  stats: StatViewModel[];
}

export interface CellViewModel {
  row: number;
  col: number;
  team: TeamId | null;
  teamLabel: string | null;
  hp: number | null;
}

export interface BoardViewModel {
  rows: number;
  cols: number;
  /** cells[rowIndex][colIndex]，0-based 仅存在于渲染层。 */
  cells: CellViewModel[][];
}

export interface EscalationViewModel {
  level: number;
  levelLabel: string;
  noDamageStreak: number;
  nextLevelAt: number | null;
  roundsUntilNextLevel: number | null;
  hint: string;
}

export interface RuleViewModel {
  ruleId: string;
  playerText: string;
  effectSummary: string | null;
}

export interface EventViewModel {
  id: string;
  kind: string;
  label: string;
  detail: string | null;
  isUnknown: boolean;
}

export interface ActionViewModel {
  summary: string;
  attackLabel: string | null;
  moveLabel: string;
}

export interface RoundViewModel {
  roundNo: number;
  strategies: { RED: StrategyViewModel | null; BLUE: StrategyViewModel | null };
  actions: { RED: ActionViewModel; BLUE: ActionViewModel };
  events: EventViewModel[];
  resultLabel: string | null;
}

export interface DecisionViewModel {
  afterRound: number | null;
  canSubmitRule: boolean;
  canAdvance: boolean;
  ruleChangedThisIntermission: boolean;
}

export interface MatchViewModel {
  matchId: string;
  schemaVersion: string;
  lifecycle: MatchLifecycle;
  lifecycleLabel: string;
  revision: number;
  /** 下一次将要解析的 Engine 回合号（不代表已完成回合数）。 */
  roundNo: number;
  completedRounds: number;
  scoreRounds: number;
  ruleChangeCount: number;
  board: BoardViewModel;
  teams: { RED: TeamViewModel; BLUE: TeamViewModel };
  activeRule: RuleViewModel | null;
  escalation: EscalationViewModel;
  decision: DecisionViewModel;
  resultLabel: string | null;
  result: MatchResult | null;
  debugRaw: string | null;
}

export interface RuleFeedbackViewModel {
  accepted: boolean;
  code: RuleSubmissionCode | string;
  codeLabel: string;
  message: string;
  suggestedRephrase: string | null;
  acceptedRuleText: string | null;
  statChangeSummary: string[];
}

export interface GameErrorViewModel {
  code: string;
  message: string;
  retryable: boolean;
}

interface ReplayEntryBaseViewModel {
  key: string;
  kindLabel: string;
  headline: string;
  lines: string[];
}

export interface ReplayRoundEntryViewModel extends ReplayEntryBaseViewModel {
  kind: 'ROUND';
  roundNo: number;
  beforeBoard: BoardViewModel;
  afterBoard: BoardViewModel;
  teamsBefore: { RED: TeamViewModel; BLUE: TeamViewModel };
  teamsAfter: { RED: TeamViewModel; BLUE: TeamViewModel };
  activeRule: RuleViewModel | null;
  escalation: EscalationViewModel;
  strategies: { RED: StrategyViewModel | null; BLUE: StrategyViewModel | null };
  actions: { RED: ActionViewModel; BLUE: ActionViewModel };
  events: EventViewModel[];
  resultLabel: string | null;
}

export interface ReplayIntermissionEntryViewModel extends ReplayEntryBaseViewModel {
  kind: 'INTERMISSION';
  afterRound: number;
  choiceLabel: string;
  submittedPlayerText: string | null;
  submissionResultLabel: string | null;
  acceptedRule: RuleViewModel | null;
  activeRuleBefore: RuleViewModel | null;
  activeRuleAfter: RuleViewModel | null;
  ruleChangeCountAfter: number;
}

export type ReplayEntryViewModel =
  | ReplayRoundEntryViewModel
  | ReplayIntermissionEntryViewModel;

export interface ReplayViewModel {
  matchId: string;
  terminalResultLabel: string | null;
  scoreRounds: number;
  ruleChangeCount: number;
  entries: ReplayEntryViewModel[];
}
