import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReplayView } from '../components/ReplayView';
import { loadReplay } from '../contract/fixtures';
import { buildReplayViewModel } from '../contract/replayAdapter';

describe('B3 Replay 基础结构', () => {
  it('时间线按 ROUND → INTERMISSION → ROUND 顺序渲染，第一条是第 1 回合', () => {
    const replay = buildReplayViewModel(loadReplay(), false);
    render(<ReplayView replay={replay} onBack={vi.fn()} />);

    const entries = screen.getAllByRole('listitem');
    expect(entries[0]).toHaveTextContent('第 1 回合');
    expect(screen.getByTestId('replay-timeline')).toHaveTextContent('第 1 回合后 · 玩家决策');
    expect(screen.getByTestId('replay-timeline')).toHaveTextContent('已生效规则');
    expect(screen.getByTestId('replay-timeline')).toHaveTextContent('红方胜利');
  });

  it('回放不展示 chain-of-thought / private memory', () => {
    const replay = buildReplayViewModel(loadReplay(), false);
    render(<ReplayView replay={replay} onBack={vi.fn()} />);
    const text = document.body.textContent ?? '';
    expect(text).not.toContain('chain-of-thought');
    expect(text).not.toContain('private memory');
    expect(text).not.toContain('PRESSURE');
  });
});
