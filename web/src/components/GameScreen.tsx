import type { ReactNode } from 'react';
import { Board } from './Board';
import { RoundSummary } from './RoundSummary';
import { TeamPanel } from './TeamPanel';
import { TopStatusBar } from './TopStatusBar';
import type { MatchViewModel, RoundViewModel } from '../contract/viewModel';

export interface GameScreenProps {
  match: MatchViewModel;
  lastRound: RoundViewModel | null;
  mockBar: ReactNode;
}

/**
 * B1 第一阶段：顶部状态 + 红蓝面板 + 棋盘 + 本回合结果。
 * 规则输入 / 终局 / 回放由下一提交接入。
 */
export function GameScreen({ match, lastRound, mockBar }: GameScreenProps) {
  return (
    <main className="game">
      {mockBar}
      <TopStatusBar match={match} onOpenReplay={null} />
      <div className="game__board-row">
        <TeamPanel team={match.teams.RED} action={lastRound?.actions.RED ?? null} />
        <Board board={match.board} />
        <TeamPanel team={match.teams.BLUE} action={lastRound?.actions.BLUE ?? null} />
      </div>
      <RoundSummary round={lastRound} />
    </main>
  );
}
