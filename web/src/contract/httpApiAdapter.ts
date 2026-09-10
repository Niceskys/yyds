import type {
  AdvanceResult,
  CreateMatchRequest,
  ErrorEnvelope,
  MatchSnapshot,
  ReplaySnapshot,
  RuleSubmissionResult,
} from './types';
import type {
  AdvanceMatchCommand,
  MatchApiAdapter,
  SubmitRuleCommand,
} from './apiAdapter';

export const NETWORK_ERROR_CODE = 'NETWORK_ERROR';
export const INVALID_RESPONSE_CODE = 'INVALID_RESPONSE';

export interface HttpMatchApiAdapterOptions {
  /** Empty means same-origin. Production should normally use same-origin or an injected base URL. */
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export class MatchApiRequestError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly status: number | null;

  constructor(options: {
    code: string;
    message: string;
    retryable: boolean;
    status?: number | null;
  }) {
    super(options.message);
    this.name = 'MatchApiRequestError';
    this.code = options.code;
    this.retryable = options.retryable;
    this.status = options.status ?? null;
  }
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!isRecord(value) || value.schema_version !== 'mvp-v0.2') return false;
  const error = value.error;
  return (
    isRecord(error) &&
    typeof error.code === 'string' &&
    typeof error.message === 'string' &&
    typeof error.retryable === 'boolean'
  );
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * Real transport for the five frozen V0.2 match operations.
 *
 * It deliberately does not derive gameplay state. Its only responsibilities are:
 * URL/method/header/body translation, safe response parsing and transport errors.
 */
export class HttpMatchApiAdapter implements MatchApiAdapter {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: HttpMatchApiAdapterOptions = {}) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl ?? '');
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  createMatch(seed?: CreateMatchRequest['seed']): Promise<MatchSnapshot> {
    const body: CreateMatchRequest = { seed: seed ?? null };
    return this.request<MatchSnapshot>('/api/v1/matches', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  getMatch(matchId: string): Promise<MatchSnapshot> {
    return this.request<MatchSnapshot>(`/api/v1/matches/${encodeURIComponent(matchId)}`);
  }

  submitRule(command: SubmitRuleCommand): Promise<RuleSubmissionResult> {
    return this.request<RuleSubmissionResult>(
      `/api/v1/matches/${encodeURIComponent(command.matchId)}/rules`,
      {
        method: 'POST',
        headers: { 'Idempotency-Key': command.idempotencyKey },
        body: JSON.stringify({
          expected_revision: command.expectedRevision,
          player_text: command.playerText,
        }),
      },
    );
  }

  advanceMatch(command: AdvanceMatchCommand): Promise<AdvanceResult> {
    return this.request<AdvanceResult>(
      `/api/v1/matches/${encodeURIComponent(command.matchId)}/advance`,
      {
        method: 'POST',
        headers: { 'Idempotency-Key': command.idempotencyKey },
        body: JSON.stringify({ expected_revision: command.expectedRevision }),
      },
    );
  }

  getReplay(matchId: string): Promise<ReplaySnapshot> {
    return this.request<ReplaySnapshot>(
      `/api/v1/matches/${encodeURIComponent(matchId)}/replay`,
    );
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        ...init,
        headers: {
          Accept: 'application/json',
          ...(init.body ? { 'Content-Type': 'application/json' } : {}),
          ...init.headers,
        },
      });
    } catch {
      throw new MatchApiRequestError({
        code: NETWORK_ERROR_CODE,
        message: '无法连接到游戏服务。',
        retryable: true,
      });
    }

    const payload = await readJson(response);
    if (!response.ok) {
      if (isErrorEnvelope(payload)) {
        throw new MatchApiRequestError({
          code: payload.error.code,
          // Keep the server message inside the transport error for diagnostics only.
          // The React layer maps known codes to local safe Chinese copy before display.
          message: payload.error.message,
          retryable: payload.error.retryable,
          status: response.status,
        });
      }
      throw new MatchApiRequestError({
        code: INVALID_RESPONSE_CODE,
        message: '游戏服务返回了无法识别的错误。',
        retryable: response.status >= 500,
        status: response.status,
      });
    }

    if (payload === null) {
      throw new MatchApiRequestError({
        code: INVALID_RESPONSE_CODE,
        message: '游戏服务返回了无法识别的数据。',
        retryable: true,
        status: response.status,
      });
    }
    return payload as T;
  }
}

const SAFE_ERROR_MESSAGES: Record<string, string> = {
  MATCH_NOT_FOUND: '对局不存在或已经失效。',
  REVISION_CONFLICT: '对局状态已经变化，已尝试刷新最新状态。',
  IDEMPOTENCY_KEY_REQUIRED: '操作标识缺失，请重新尝试。',
  INVALID_REQUEST: '提交内容无效，请检查后重试。',
  MATCH_TERMINAL: '对局已经结束，不能再执行这个操作。',
  RULE_SUBMISSION_NOT_ALLOWED: '当前阶段不能提交规则。',
  ADVANCE_NOT_ALLOWED: '当前阶段不能继续下一回合。',
  INTERNAL_ERROR: '本回合未安全完成，请稍后重试。',
  [NETWORK_ERROR_CODE]: '无法连接到游戏服务，请检查连接后重试。',
  [INVALID_RESPONSE_CODE]: '游戏服务返回异常，请稍后重试。',
};

export function toSafeGameError(error: unknown): {
  code: string;
  message: string;
  retryable: boolean;
} {
  if (error instanceof MatchApiRequestError) {
    return {
      code: error.code,
      message: SAFE_ERROR_MESSAGES[error.code] ?? '操作未完成，请稍后重试。',
      retryable: error.retryable,
    };
  }
  return {
    code: NETWORK_ERROR_CODE,
    message: SAFE_ERROR_MESSAGES[NETWORK_ERROR_CODE],
    retryable: true,
  };
}

export function shouldReuseIdempotencyKey(error: unknown): boolean {
  return (
    error instanceof MatchApiRequestError &&
    error.retryable &&
    error.code !== 'REVISION_CONFLICT'
  );
}

export function isRevisionConflict(error: unknown): boolean {
  return error instanceof MatchApiRequestError && error.code === 'REVISION_CONFLICT';
}
