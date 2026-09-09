import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { App } from '../App';

describe('初始页 → 游玩页', () => {
  it('初始页只显示《规则之外》与开始游戏', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: '《规则之外》' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始游戏' })).toBeInTheDocument();
    // 不做登录 / 排行 / 商店 / 设置
    expect(screen.queryByText('登录')).toBeNull();
    expect(screen.queryByText('排行榜')).toBeNull();
    expect(screen.queryByText('商店')).toBeNull();
  });

  it('点击开始游戏进入游玩界面并渲染棋盘', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '开始游戏' }));
    expect(screen.getByTestId('board-grid')).toBeInTheDocument();
    expect(screen.getByTestId('completed-rounds')).toBeInTheDocument();
    expect(screen.getByTestId('rule-change-count')).toBeInTheDocument();
    expect(screen.getByTestId('active-rule')).toBeInTheDocument();
    expect(screen.getByTestId('escalation')).toBeInTheDocument();
  });

  it('开始游戏后处于第 1 回合结算完成的玩家决策阶段', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '开始游戏' }));
    expect(screen.getByTestId('lifecycle')).toHaveTextContent('等待你的决策');
    expect(screen.getByTestId('rule-input')).not.toBeDisabled();
    expect(screen.getByTestId('advance-round')).not.toBeDisabled();
  });

  it('开始游戏后保留第 1 回合实际行动和公开事件', () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: '开始游戏' }));
    expect(screen.getByTestId('round-summary')).toHaveTextContent('第 1 回合结果');
    expect(screen.getByTestId('action-RED')).toHaveTextContent('使用弓箭攻击');
    expect(screen.getByTestId('round-summary')).toHaveTextContent('公开事件');
  });
});
