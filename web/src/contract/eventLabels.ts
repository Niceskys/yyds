/**
 * RoundEventPublicView.kind 的中文展示。
 *
 * kind 是开放字符串（有意保留的兼容边界），因此这里使用
 * 已知映射 + 安全 fallback，而不是封闭 enum。
 * 未知事件不得让页面崩溃，也不得暴露 provider 原始错误。
 */
import { formatSigned, labelTeam, labelWeapon } from './labels';
import type { EventViewModel } from './viewModel';
import type { RoundEventPublicView, TeamId } from './types';

export const UNKNOWN_EVENT_LABEL = '发生新的战斗事件';

interface EventPresentation {
  label: string;
  detail: string | null;
}

function asTeam(value: unknown): TeamId | null {
  return value === 'RED' || value === 'BLUE' ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' ? value : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function teamName(value: unknown): string {
  const team = asTeam(value);
  return team ? labelTeam(team) : '未知一方';
}

/** 已知事件的展示逻辑。每个分支只读取 details 中已公开的字段。 */
const KNOWN_PRESENTERS: Record<
  string,
  (event: RoundEventPublicView) => EventPresentation
> = {
  RULE_MODIFIER_APPLIED: (event) => {
    const details = event.details ?? {};
    const parts: string[] = [];
    const additiveModifiers: Array<[string, string]> = [
      ['move_range_add', '移动距离'],
      ['knife_range_add', '刀攻击距离'],
      ['bow_range_add', '弓箭射程'],
      ['knife_damage_add', '刀伤害'],
      ['bow_damage_add', '弓箭伤害'],
    ];
    additiveModifiers.forEach(([key, label]) => {
      const value = asNumber(details[key]);
      if (value !== null && value !== 0) parts.push(`${label} ${formatSigned(value)}`);
    });
    const multiplier = asNumber(details.bow_hit_multiplier);
    if (multiplier !== null && multiplier !== 1) {
      parts.push(`弓箭命中倍率 ×${multiplier}`);
    }
    if (Array.isArray(details.cooldown_weapons) && details.cooldown_weapons.length > 0) {
      const weapons = details.cooldown_weapons
        .map(asString)
        .filter((weapon): weapon is string => weapon !== null)
        .map(labelWeapon);
      if (weapons.length > 0) parts.push(`冷却武器：${weapons.join('、')}`);
    }
    return {
      label: '公共规则生效',
      detail: `${teamName(event.actor)}：${parts.length > 0 ? parts.join('，') : '规则条件已触发'}`,
    };
  },
  ATTACK_RESOLVED: (event) => {
    const details = event.details ?? {};
    const weapon = labelWeapon(asString(details.weapon));
    const hit = details.hit;
    const parts: string[] = [];
    if (weapon) parts.push(`武器：${weapon}`);
    if (typeof hit === 'boolean') parts.push(hit ? '命中' : '未命中');
    const distance = asNumber(details.distance);
    if (distance !== null) parts.push(`距离：${distance} 格`);
    return {
      label: '攻击结算',
      detail: parts.length > 0 ? parts.join('，') : null,
    };
  },
  DAMAGE_APPLIED: (event) => {
    const details = event.details ?? {};
    const amount = asNumber(details.amount);
    const before = asNumber(details.hp_before);
    const after = asNumber(details.hp_after);
    const attacker = teamName(event.actor ?? details.attacker);
    const target = teamName(details.target);
    const parts: string[] = [];
    if (amount !== null) parts.push(`造成 ${amount} 点伤害`);
    if (before !== null && after !== null) {
      parts.push(`生命值 ${before} → ${after}`);
    }
    return {
      label: '造成伤害',
      detail: parts.length > 0 ? `${attacker} 对 ${target} ${parts.join('，')}` : null,
    };
  },
  INVALID_ATTACK: () => ({
    label: '无效攻击',
    detail: null,
  }),
  FORCED_BOW: () => ({
    label: '强制使用弓箭',
    detail: '战局升温导致本回合强制远程攻击',
  }),
  SAME_DESTINATION_CONFLICT: () => ({
    label: '同格争抢冲突',
    detail: '双方试图移动到同一格，动作被重新结算',
  }),
  SWAP_CONFLICT: () => ({
    label: '换位冲突',
    detail: '双方试图互换位置，动作被重新结算',
  }),
  MATCH_TIMEOUT: () => ({
    label: '达到本局最高回合数',
    detail: null,
  }),
  MATCH_TERMINAL: () => ({
    label: '对局结束',
    detail: null,
  }),
};

export const KNOWN_EVENT_KINDS = Object.keys(KNOWN_PRESENTERS);

/** 单个事件 → 展示模型。未知 kind 走安全 fallback。 */
export function presentEvent(
  event: RoundEventPublicView,
  index: number,
  debug: boolean,
): EventViewModel {
  const presenter = KNOWN_PRESENTERS[event.kind];
  if (!presenter) {
    return {
      id: `${event.kind}-${index}`,
      kind: event.kind,
      label: UNKNOWN_EVENT_LABEL,
      detail: debug ? `未知事件：${event.kind}` : null,
      isUnknown: true,
    };
  }
  const presentation = presenter(event);
  return {
    id: `${event.kind}-${index}`,
    kind: event.kind,
    label: presentation.label,
    detail: presentation.detail,
    isUnknown: false,
  };
}

export function presentEvents(
  events: RoundEventPublicView[],
  debug: boolean,
): EventViewModel[] {
  return events.map((event, index) => presentEvent(event, index, debug));
}
