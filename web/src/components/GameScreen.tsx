import { Board } from './Board';
import { ResultBanner } from './ResultBanner';
import { RoundTransition } from './RoundTransition';
import { RoundSummary } from './RoundSummary';
import { RulePanel } from './RulePanel';
import { TeamPanel } from './TeamPanel';
import { TopStatusBar } from './TopStatusBar';
import type {
  GameErrorViewModel,
  MatchViewModel,
  RoundViewModel,
  RuleFeedbackViewModel,
  RoundTransitionViewModel,
} from '../contract/viewModel';

export interface GameScreenProps {
  match: MatchViewModel;
  lastRound: RoundViewModel | null;
  roundTransition?: RoundTransitionViewModel | null;
  feedback: RuleFeedbackViewModel | null;
  error: GameErrorViewModel | null;
  notice: string | null;
  ruleText: string;
  onRuleTextChange: (value: string) => void;
  onSubmitRule: () => void;
  onAdvance: () => void;
  onRestart: () => void;
  onOpenReplay: (() => void) | null;
  submittingRule?: boolean;
  advancing?: boolean;
  replayLoading?: boolean;
}

export function GameScreen({
  match,
  lastRound,
  roundTransition = null,
  feedback,
  error,
  notice,
  ruleText,
  onRuleTextChange,
  onSubmitRule,
  onAdvance,
  onRestart,
  onOpenReplay,
  submittingRule = false,
  advancing = false,
  replayLoading = false,
}: GameScreenProps) {
  const settlingRound = roundTransition !== null;
  return (
    <main className="game">
      <TopStatusBar
        match={match}
        onOpenReplay={onOpenReplay}
        replayLoading={replayLoading}
        previousEscalation={roundTransition?.before.escalation ?? null}
      />
      <div className="game__board-row">
        <TeamPanel
          team={match.teams.RED}
          action={lastRound?.actions.RED ?? null}
          settling={settlingRound}
        />
        <Board board={match.board} settling={settlingRound} />
        <TeamPanel
          team={match.teams.BLUE}
          action={lastRound?.actions.BLUE ?? null}
          settling={settlingRound}
        />
      </div>
      {roundTransition ? <RoundTransition transition={roundTransition} /> : null}
      <RoundSummary round={lastRound} />
      <ResultBanner match={match} onRestart={onRestart} onOpenReplay={onOpenReplay} />
      <RulePanel
        decision={match.decision}
        ruleText={ruleText}
        onRuleTextChange={onRuleTextChange}
        onSubmitRule={onSubmitRule}
        onAdvance={onAdvance}
        feedback={feedback}
        error={error}
        notice={notice}
        submittingRule={submittingRule}
        advancing={advancing}
      />
    </main>
  );
}
