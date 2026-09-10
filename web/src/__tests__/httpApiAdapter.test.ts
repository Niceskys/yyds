import { describe, expect, it } from 'vitest';
import type { AdvanceMatchCommand, SubmitRuleCommand } from '../contract/apiAdapter';
import {
  HttpMatchApiAdapter,
  INVALID_RESPONSE_CODE,
  MatchApiRequestError,
  NETWORK_ERROR_CODE,
  shouldReuseIdempotencyKey,
  toSafeGameError,
} from '../contract/httpApiAdapter';
import {
  loadAdvanceResult,
  loadErrorEnvelope,
  loadMatchSnapshot,
  loadReplay,
  loadRuleSubmission,
} from '../contract/fixtures';

interface RecordedRequest {
  input: RequestInfo | URL;
  init?: RequestInit;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('HttpMatchApiAdapter', () => {
  it('把五个 frozen operation 映射到正确 URL / method / body / Idempotency-Key', async () => {
    const payloads: unknown[] = [
      loadMatchSnapshot('match_initial'),
      loadMatchSnapshot('match_initial'),
      loadRuleSubmission('rule_accepted'),
      loadAdvanceResult(),
      loadReplay(),
    ];
    const requests: RecordedRequest[] = [];
    const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ input, init });
      return jsonResponse(payloads.shift());
    }) as typeof fetch;
    const api = new HttpMatchApiAdapter({
      baseUrl: 'https://game.example/',
      fetchImpl,
    });

    await api.createMatch(42);
    await api.getMatch('match/a b');
    const rule: SubmitRuleCommand = {
      matchId: 'match/a b',
      expectedRevision: 1,
      idempotencyKey: 'rule-key',
      playerText: '双方移动距离增加1格。',
    };
    await api.submitRule(rule);
    const advance: AdvanceMatchCommand = {
      matchId: 'match/a b',
      expectedRevision: 2,
      idempotencyKey: 'advance-key',
    };
    await api.advanceMatch(advance);
    await api.getReplay('match/a b');

    expect(requests.map((request) => String(request.input))).toEqual([
      'https://game.example/api/v1/matches',
      'https://game.example/api/v1/matches/match%2Fa%20b',
      'https://game.example/api/v1/matches/match%2Fa%20b/rules',
      'https://game.example/api/v1/matches/match%2Fa%20b/advance',
      'https://game.example/api/v1/matches/match%2Fa%20b/replay',
    ]);
    expect(requests.map((request) => request.init?.method ?? 'GET')).toEqual([
      'POST',
      'GET',
      'POST',
      'POST',
      'GET',
    ]);

    expect(JSON.parse(String(requests[0].init?.body))).toEqual({ seed: 42 });
    expect(JSON.parse(String(requests[2].init?.body))).toEqual({
      expected_revision: 1,
      player_text: '双方移动距离增加1格。',
    });
    expect(JSON.parse(String(requests[3].init?.body))).toEqual({ expected_revision: 2 });

    const ruleHeaders = new Headers(requests[2].init?.headers);
    const advanceHeaders = new Headers(requests[3].init?.headers);
    expect(ruleHeaders.get('Idempotency-Key')).toBe('rule-key');
    expect(advanceHeaders.get('Idempotency-Key')).toBe('advance-key');
    expect(ruleHeaders.get('Content-Type')).toBe('application/json');
  });

  it('解析 ErrorEnvelope，但展示层只使用本地安全中文文案', async () => {
    const fixture = loadErrorEnvelope();
    const responseWithSensitiveMessage = {
      ...fixture,
      error: {
        ...fixture.error,
        message: 'raw provider body api-key SECRET',
      },
    };
    const fetchImpl = (async () => jsonResponse(responseWithSensitiveMessage, 409)) as typeof fetch;
    const api = new HttpMatchApiAdapter({ fetchImpl });

    let caught: unknown;
    try {
      await api.advanceMatch({
        matchId: 'match_fixture_001',
        expectedRevision: 0,
        idempotencyKey: 'same-key',
      });
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(MatchApiRequestError);
    expect(caught).toMatchObject({
      code: 'REVISION_CONFLICT',
      retryable: true,
      status: 409,
    });
    const safe = toSafeGameError(caught);
    expect(safe.message).toContain('对局状态已经变化');
    expect(safe.message).not.toContain('SECRET');
    expect(shouldReuseIdempotencyKey(caught)).toBe(false);
  });

  it('非 ErrorEnvelope 的 5xx 不把 raw body 暴露给 UI', async () => {
    const fetchImpl = (async () =>
      new Response('provider raw secret stack trace', {
        status: 502,
        headers: { 'Content-Type': 'text/plain' },
      })) as typeof fetch;
    const api = new HttpMatchApiAdapter({ fetchImpl });

    let caught: unknown;
    try {
      await api.getMatch('match_fixture_001');
    } catch (error) {
      caught = error;
    }

    expect(caught).toMatchObject({ code: INVALID_RESPONSE_CODE, retryable: true, status: 502 });
    const safe = toSafeGameError(caught);
    expect(safe.message).toBe('游戏服务返回异常，请稍后重试。');
    expect(safe.message).not.toContain('provider raw secret');
  });

  it('网络结果未知时标记为 retryable，并允许同一次用户意图复用 key', async () => {
    const fetchImpl = (async () => {
      throw new Error('network secret URL');
    }) as typeof fetch;
    const api = new HttpMatchApiAdapter({ fetchImpl });

    let caught: unknown;
    try {
      await api.advanceMatch({
        matchId: 'match_fixture_001',
        expectedRevision: 0,
        idempotencyKey: 'same-key',
      });
    } catch (error) {
      caught = error;
    }

    expect(caught).toMatchObject({ code: NETWORK_ERROR_CODE, retryable: true, status: null });
    expect(shouldReuseIdempotencyKey(caught)).toBe(true);
    expect(toSafeGameError(caught).message).not.toContain('network secret URL');
  });

  it('200 但 body 不是 JSON 时按安全 protocol failure 处理', async () => {
    const fetchImpl = (async () =>
      new Response('not-json secret', {
        status: 200,
        headers: { 'Content-Type': 'text/plain' },
      })) as typeof fetch;
    const api = new HttpMatchApiAdapter({ fetchImpl });

    await expect(api.getReplay('match_fixture_001')).rejects.toMatchObject({
      code: INVALID_RESPONSE_CODE,
      retryable: true,
      status: 200,
    });
  });
});
