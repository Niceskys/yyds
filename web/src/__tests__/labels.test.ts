import { describe, expect, it } from 'vitest';
import {
  STRATEGY_LABELS,
  TEAM_LABELS,
  WEAPON_LABELS,
  formatPercent,
  labelStrategy,
  labelTeam,
  labelWeapon,
} from '../contract/labels';

describe('中文映射', () => {
  it('策略四枚举映射到规定的中文文案', () => {
    expect(STRATEGY_LABELS.PRESSURE).toBe('逼近进攻');
    expect(STRATEGY_LABELS.KITE).toBe('保持距离');
    expect(STRATEGY_LABELS.EVADE).toBe('躲避保命');
    expect(STRATEGY_LABELS.HOLD).toBe('原地应对');
  });

  it('阵营与武器映射', () => {
    expect(TEAM_LABELS.RED).toBe('红方');
    expect(TEAM_LABELS.BLUE).toBe('蓝方');
    expect(WEAPON_LABELS.BOW).toBe('弓箭');
    expect(WEAPON_LABELS.KNIFE).toBe('刀');
    expect(labelTeam('RED')).toBe('红方');
    expect(labelWeapon('BOW')).toBe('弓箭');
  });

  it('未知值走安全 fallback，不直接暴露英文内部值', () => {
    expect(labelStrategy(undefined)).toBeNull();
    expect(labelStrategy('SOMETHING_NEW')).toBe('未知');
    expect(labelWeapon('LASER')).toBe('未知');
  });

  it('百分比格式化', () => {
    expect(formatPercent(0)).toBe('0%');
    expect(formatPercent(0.25)).toBe('25%');
    expect(formatPercent(1)).toBe('100%');
  });
});
