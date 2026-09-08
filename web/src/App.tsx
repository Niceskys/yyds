import { useState } from 'react';
import { StartScreen } from './components/StartScreen';

type Screen = 'start' | 'game';

/**
 * B0 App Shell。
 * 本提交只交付《规则之外》初始页与页面切换；
 * 游玩界面（棋盘 / 红蓝面板 / 规则输入）由后续 B1 提交填充。
 */
export function App() {
  const [screen, setScreen] = useState<Screen>('start');

  if (screen === 'start') {
    return (
      <div className="app">
        <StartScreen onStart={() => setScreen('game')} />
      </div>
    );
  }

  return (
    <div className="app">
      <main className="game">
        <p>游玩界面正在开发中（B1）。</p>
      </main>
    </div>
  );
}
