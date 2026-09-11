import { useMemo, useRef, useState } from 'react';
import { GameScreen } from './components/GameScreen';
import { ReplayView } from './components/ReplayView';
import { StartScreen } from './components/StartScreen';
import type { MatchApiAdapter } from './contract/apiAdapter';
import {
  HttpMatchApiAdapter,
  isRevisionConflict,
  shouldReuseIdempotencyKey,
  toSafeGameError,
} from './contract/httpApiAdapter';
import {
  buildMatchViewModel,
  buildRoundViewModel,
  buildRuleFeedbackViewModel,
} from './contract/mockAdapter';
import { buildReplayViewModel } from './contract/replayAdapter';
import type { MatchSnapshot } from './contract/types';
import type {
  GameErrorViewModel,
  ReplayViewModel,
  RoundTransitionViewModel,
  RoundViewModel,
  RuleFeedbackViewModel,
} from './contract/viewModel';

type Screen = 'start' | 'game' | 'replay';
type MutationKind = 'rule' | 'advance';

interface RetryMutation {
  kind: MutationKind;
  fingerprint: string;
  key: string;
}

export interface AppProps {
  api?: MatchApiAdapter;
  idempotencyKeyFactory?: () => string;
  roundTransitionDurationMs?: number;
}

/** 仅开发模式附加内部原始值；生产构建不显示。 */
const DEBUG = import.meta.env.DEV;

const defaultApi = new HttpMatchApiAdapter({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '',
});

function createDefaultIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function degradedRoundNotice(round: {
  strategies: { RED: { degraded: boolean }; BLUE: { degraded: boolean } };
}): string | null {
  if (round.strategies.RED.degraded || round.strategies.BLUE.degraded) {
    return '本回合有一方模型不可用，已使用降级策略继续完成对局。';
  }
  return null;
}

export function App({
  api = defaultApi,
  idempotencyKeyFactory = createDefaultIdempotencyKey,
  roundTransitionDurationMs = 1000,
}: AppProps = {}) {
  const [screen, setScreen] = useState<Screen>('start');
  const [snapshot, setSnapshot] = useState<MatchSnapshot | null>(null);
  const [lastRound, setLastRound] = useState<RoundViewModel | null>(null);
  const [roundTransition, setRoundTransition] = useState<RoundTransitionViewModel | null>(null);
  const [feedback, setFeedback] = useState<RuleFeedbackViewModel | null>(null);
  const [error, setError] = useState<GameErrorViewModel | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [replay, setReplay] = useState<ReplayViewModel | null>(null);
  const [ruleText, setRuleText] = useState('');
  const [startLoading, setStartLoading] = useState(false);
  const [mutationPending, setMutationPending] = useState<MutationKind | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);
  const retryMutationRef = useRef<RetryMutation | null>(null);

  const match = useMemo(
    () => (snapshot ? buildMatchViewModel(snapshot, { debug: DEBUG }) : null),
    [snapshot],
  );

  const acquireMutationKey = (kind: MutationKind, fingerprint: string): string => {
    const pending = retryMutationRef.current;
    if (pending && pending.kind === kind && pending.fingerprint === fingerprint) {
      return pending.key;
    }
    const key = idempotencyKeyFactory();
    retryMutationRef.current = { kind, fingerprint, key };
    return key;
  };

  const clearRetryMutation = () => {
    retryMutationRef.current = null;
  };

  const handleStart = async () => {
    if (startLoading) return;
    setStartLoading(true);
    setError(null);
    try {
      const created = await api.createMatch();
      setSnapshot(created);
      setLastRound(null);
      setRoundTransition(null);
      setFeedback(null);
      setNotice(null);
      setReplay(null);
      setRuleText('');
      clearRetryMutation();
      setScreen('game');
    } catch (caught) {
      setError(toSafeGameError(caught));
    } finally {
      setStartLoading(false);
    }
  };

  const resyncAfterRevisionConflict = async (matchId: string) => {
    try {
      const latest = await api.getMatch(matchId);
      setSnapshot(latest);
      // MatchSnapshot cannot reconstruct the authoritative execution detail or
      // previous submission result. Clear stale presentation state instead of
      // pairing old round/feedback data with the newly resynced snapshot.
      setLastRound(null);
      setRoundTransition(null);
      setFeedback(null);
      setReplay(null);
    } catch {
      // Preserve the original authoritative snapshot and original conflict message.
      // A failed resync must never expose a second raw transport error or guess state.
    }
  };

  const handleMutationFailure = async (caught: unknown, matchId: string) => {
    setError(toSafeGameError(caught));
    setNotice(null);
    if (isRevisionConflict(caught)) {
      clearRetryMutation();
      await resyncAfterRevisionConflict(matchId);
      return;
    }
    if (!shouldReuseIdempotencyKey(caught)) {
      clearRetryMutation();
    }
  };

  const handleSubmitRule = async () => {
    if (!snapshot || mutationPending || !snapshot.player_decision.can_submit_rule) return;
    const playerText = ruleText.trim();
    if (!playerText) return;

    const fingerprint = `rule:${snapshot.match_id}:${snapshot.revision}:${playerText}`;
    const idempotencyKey = acquireMutationKey('rule', fingerprint);
    setMutationPending('rule');
    setError(null);
    setNotice(null);

    try {
      const result = await api.submitRule({
        matchId: snapshot.match_id,
        expectedRevision: snapshot.revision,
        idempotencyKey,
        playerText,
      });
      clearRetryMutation();
      setSnapshot(result.match);
      setFeedback(buildRuleFeedbackViewModel(result));
      setReplay(null);
      if (result.public_code === 'MODEL_UNAVAILABLE') {
        setNotice('规则模型暂时不可用，本次没有修改公共规则，你可以稍后重新提交。');
      }
    } catch (caught) {
      await handleMutationFailure(caught, snapshot.match_id);
    } finally {
      setMutationPending(null);
    }
  };

  const handleAdvance = async () => {
    if (
      !snapshot ||
      mutationPending ||
      roundTransition ||
      !snapshot.player_decision.can_advance
    )
      return;

    const fingerprint = `advance:${snapshot.match_id}:${snapshot.revision}`;
    const idempotencyKey = acquireMutationKey('advance', fingerprint);
    setMutationPending('advance');
    setError(null);
    setFeedback(null);
    setNotice(null);

    try {
      const result = await api.advanceMatch({
        matchId: snapshot.match_id,
        expectedRevision: snapshot.revision,
        idempotencyKey,
      });
      clearRetryMutation();
      const round = buildRoundViewModel(result.round, DEBUG);
      const reducedMotion =
        typeof window !== 'undefined' &&
        typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      setSnapshot(result.match);
      setLastRound(round);
      setReplay(null);
      setNotice(degradedRoundNotice(result.round));
      if (!reducedMotion && roundTransitionDurationMs > 0) {
        setRoundTransition({
          before: buildMatchViewModel(snapshot, { debug: DEBUG }),
          after: buildMatchViewModel(result.match, { debug: DEBUG }),
          round,
        });
        await new Promise<void>((resolve) => {
          window.setTimeout(resolve, roundTransitionDurationMs);
        });
        setRoundTransition(null);
      }
    } catch (caught) {
      await handleMutationFailure(caught, snapshot.match_id);
    } finally {
      setMutationPending(null);
    }
  };

  const handleOpenReplay = async () => {
    if (!snapshot || replayLoading) return;
    setReplayLoading(true);
    setError(null);
    try {
      const result = await api.getReplay(snapshot.match_id);
      setReplay(buildReplayViewModel(result, DEBUG));
      setScreen('replay');
    } catch (caught) {
      setError(toSafeGameError(caught));
    } finally {
      setReplayLoading(false);
    }
  };

  const handleRestart = () => {
    setSnapshot(null);
    setLastRound(null);
    setRoundTransition(null);
    setFeedback(null);
    setError(null);
    setNotice(null);
    setReplay(null);
    setRuleText('');
    setMutationPending(null);
    clearRetryMutation();
    setScreen('start');
  };

  if (screen === 'start') {
    return (
      <div className="app">
        <StartScreen onStart={() => void handleStart()} loading={startLoading} error={error} />
      </div>
    );
  }

  if (screen === 'replay' && replay) {
    return (
      <div className="app">
        <ReplayView replay={replay} onBack={() => setScreen('game')} />
      </div>
    );
  }

  if (!match) {
    return (
      <div className="app">
        <StartScreen onStart={() => void handleStart()} loading={startLoading} error={error} />
      </div>
    );
  }

  return (
    <div className="app">
      <GameScreen
        match={match}
        lastRound={lastRound}
        roundTransition={roundTransition}
        feedback={feedback}
        error={error}
        notice={notice}
        ruleText={ruleText}
        onRuleTextChange={setRuleText}
        onSubmitRule={() => void handleSubmitRule()}
        onAdvance={() => void handleAdvance()}
        onRestart={handleRestart}
        onOpenReplay={() => void handleOpenReplay()}
        submittingRule={mutationPending === 'rule'}
        advancing={mutationPending === 'advance'}
        replayLoading={replayLoading}
      />
    </div>
  );
}
