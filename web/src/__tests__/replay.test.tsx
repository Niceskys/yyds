import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReplayView } from '../components/ReplayView';
import { loadReplay } from '../contract/fixtures';
import { buildReplayViewModel } from '../contract/replayAdapter';

function renderReplay() {
  const replay = buildReplayViewModel(loadReplay(), false);
  render(<ReplayView replay={replay} onBack={vi.fn()} />);
  return screen.getByTestId('replay-timeline');
}

describe('B3 Replay 逐节点浏览', () => {
  it('时间线保持 ROUND → INTERMISSION → ROUND 顺序，并默认选择第 1 回合', () => {
    const timeline = renderReplay();
    const nodes = within(timeline).getAllByRole('button');
    expect(nodes).toHaveLength(4);
    expect(nodes[0]).toHaveTextContent('第 1 回合');
    expect(nodes[1]).toHaveTextContent('第 1 回合后 · 玩家决策');
    expect(nodes[2]).toHaveTextContent('第 1 回合后 · 玩家决策');
    expect(nodes[3]).toHaveTextContent('第 2 回合');
    expect(nodes[0]).toHaveAttribute('aria-pressed', 'true');
    const detail = screen.getByTestId('replay-selected-detail');
    expect(detail).toHaveTextContent('回合开始');
    expect(detail).toHaveTextContent('回合结束');
  });

  it('第 1 回合展示 authoritative pre/post 棋盘与生命值', () => {
    renderReplay();
    const detail = screen.getByTestId('replay-selected-detail');
    const boards = within(detail).getAllByTestId('board-grid');
    expect(boards).toHaveLength(2);
    expect(within(boards[0]).getByTestId('cell-3-5')).toHaveTextContent('生命 4');
    expect(within(boards[1]).getByTestId('cell-3-5')).toHaveTextContent('生命 3');
    expect(within(boards[0]).getByTestId('cell-3-2')).toHaveTextContent('生命 4');
    expect(within(boards[1]).getByTestId('cell-3-2')).toHaveTextContent('生命 4');
  });

  it('可切换规则尝试、继续和第 2 回合，并展示规则变化与生效属性', () => {
    const timeline = renderReplay();
    const nodes = within(timeline).getAllByRole('button');
    fireEvent.click(nodes[1]);
    let detail = screen.getByTestId('replay-selected-detail');
    expect(detail).toHaveTextContent('尝试制定规则');
    expect(detail).toHaveTextContent('双方移动距离增加1格');
    expect(detail).toHaveTextContent('无 → 双方移动距离增加1格');
    fireEvent.click(nodes[2]);
    detail = screen.getByTestId('replay-selected-detail');
    expect(detail).toHaveTextContent('继续下一回合');
    expect(detail).toHaveTextContent('本次没有提交新规则');
    fireEvent.click(nodes[3]);
    detail = screen.getByTestId('replay-selected-detail');
    expect(detail).toHaveTextContent('第 2 回合');
    expect(detail).toHaveTextContent('本回合公共规则');
    expect(detail).toHaveTextContent('双方移动距离增加1格');
    expect(within(detail).getAllByText('2 格').length).toBeGreaterThanOrEqual(2);
    expect(detail).toHaveTextContent('红方胜利');
  });

  it('相邻节点切换显示权威节点关系和前后方向', () => {
    const timeline = renderReplay();
    const nodes = within(timeline).getAllByRole('button');
    fireEvent.click(nodes[1]);
    expect(screen.getByText(/回放节点：第 1 回合 → 第 1 回合后 · 玩家决策/)).toBeInTheDocument();
    expect(screen.getByTestId('replay-detail-transition')).toHaveAttribute('data-direction', 'forward');
    fireEvent.click(nodes[0]);
    expect(screen.getByTestId('replay-detail-transition')).toHaveAttribute('data-direction', 'backward');
    expect(nodes[0]).toHaveAttribute('aria-pressed', 'true');
  });

  it('快速连续选择时最终只呈现最后选择的 authoritative 节点', () => {
    const timeline = renderReplay();
    const nodes = within(timeline).getAllByRole('button');
    fireEvent.click(nodes[1]);
    fireEvent.click(nodes[3]);
    fireEvent.click(nodes[2]);
    expect(screen.getByTestId('replay-selected-detail')).toHaveTextContent('继续下一回合');
    expect(screen.getByTestId('replay-detail-transition')).toHaveAttribute('data-entry-key', 'intermission-1-2');
    expect(nodes[2]).toHaveAttribute('aria-pressed', 'true');
    expect(nodes[0]).toHaveAttribute('aria-pressed', 'false');
    expect(nodes[1]).toHaveAttribute('aria-pressed', 'false');
    expect(nodes[3]).toHaveAttribute('aria-pressed', 'false');
  });

  it('回放不展示 chain-of-thought / private memory 或内部机器字段', () => {
    renderReplay();
    const text = document.body.textContent ?? '';
    expect(text).not.toContain('chain-of-thought');
    expect(text).not.toContain('private memory');
    expect(text).not.toContain('PRESSURE');
    expect(text).not.toContain('conflict_level');
    expect(text).not.toContain('hard_liveness');
    expect(text).not.toContain('hard_liveness_active');
  });
});

