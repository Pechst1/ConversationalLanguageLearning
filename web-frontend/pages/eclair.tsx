/* WP-S7 — Éclair: a 60-second minimal-pair sprint between two contrasting rules.

   Three screens, one Garamond line each at most:
     ready    «Éclair» (the one Garamond line), the pair, its best, «Start»
     playing  the clock, the live score, the cue in the chrome language and the
              two French sentences; every tap is graded here at once (the keys
              came with the items) and felt (lib/feel: haptic + sound per the
              Réglages toggle)
     done     «n right in one minute.» (the Garamond line), the best for the
              pair, «Play again» (the one primary) and «Back to the rules»
   The server files the round (re-grades by its keys, writes the evidence at
   the discriminate rung with the forge's caps, keeps the best per pair). */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';

import { Action, AtelierV2Root, CrossIcon, IconAction, Notice, ProgressRule } from '@/components/atelier-v2/ui';
import {
  ECLAIR_SECONDS,
  eclairCue,
  eclairScore,
  gradeEclair,
  roundOver,
  secondsLeft,
  type EclairAnswer,
  type EclairResult,
  type EclairRound,
} from '@/lib/eclair';
import { feel } from '@/lib/feel';
import { useChromeLanguage } from '@/lib/learner-language';
import { fillMomentum, momentumCopy } from '@/lib/momentum-copy';
import api from '@/services/api';

type Phase = 'ready' | 'starting' | 'playing' | 'saving' | 'done' | 'failed';

const BACK_HREF = '/notebook?mode=grammar';

export default function EclairPage() {
  const router = useRouter();
  const language = useChromeLanguage();
  const copy = momentumCopy(language);
  const pair = typeof router.query.pair === 'string' ? router.query.pair : undefined;

  const [phase, setPhase] = useState<Phase>('ready');
  const [round, setRound] = useState<EclairRound | null>(null);
  const [answers, setAnswers] = useState<EclairAnswer[]>([]);
  const [flash, setFlash] = useState<{ label: string; correct: boolean } | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [result, setResult] = useState<EclairResult | null>(null);
  const filing = useRef(false);

  const start = useCallback(async () => {
    setPhase('starting');
    setAnswers([]);
    setResult(null);
    setFlash(null);
    filing.current = false;
    try {
      const next = await api.startEclair(pair ? { pair } : {});
      setRound(next);
      const t0 = Date.now();
      setStartedAt(t0);
      setNow(t0);
      setPhase('playing');
    } catch (error) {
      console.error(error);
      setPhase('failed');
    }
  }, [pair]);

  // The clock: a quarter-second tick while playing.
  useEffect(() => {
    if (phase !== 'playing') return;
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [phase]);

  const file = useCallback(async (final: EclairAnswer[]) => {
    if (!round || filing.current) return;
    filing.current = true;
    setPhase('saving');
    try {
      const filed = await api.finishEclair(round.eclair_id, {
        answers: final.map(({ id, answer }) => ({ id, answer })),
        elapsed_ms: startedAt ? Math.min(ECLAIR_SECONDS * 1000, Date.now() - startedAt) : undefined,
      });
      setResult(filed);
      feel('complete');
    } catch (error) {
      console.error(error);
      // The round still ends on the local count; the server keeps nothing.
      const score = eclairScore(final);
      setResult({ pair: round.pair, score, answered: final.length, best_before: round.best, best: Math.max(round.best, score), new_best: score > round.best });
    }
    setPhase('done');
  }, [round, startedAt]);

  const items = round?.items ?? [];
  const index = answers.length;
  const item = items[index] ?? null;
  const left = startedAt ? secondsLeft(startedAt, now, round?.seconds ?? ECLAIR_SECONDS) : ECLAIR_SECONDS;

  useEffect(() => {
    if (phase === 'playing' && roundOver(startedAt, now, answers.length, items.length, round?.seconds ?? ECLAIR_SECONDS)) {
      void file(answers);
    }
  }, [phase, startedAt, now, answers, items.length, round, file]);

  const choose = (label: string) => {
    if (!item || phase !== 'playing' || flash) return;
    const correct = gradeEclair(item, label);
    feel(correct ? 'correct' : 'wrong');
    setFlash({ label, correct });
    window.setTimeout(() => {
      setFlash(null);
      setAnswers((previous) => [...previous, { id: item.id, answer: label, correct }]);
    }, correct ? 180 : 420);
  };

  const score = eclairScore(answers);
  const names = round?.rules?.length
    ? fillMomentum(copy.eclair_pair_label, { a: round.rules[0]?.title_fr || '', b: round.rules[1]?.title_fr || '' })
    : null;

  return (
    <>
      <Head>
        <title>{`${copy.eclair_name} · L’Atelier`}</title>
      </Head>
      <EclairStyles />
      <AtelierV2Root as="main" language={language} className="ecl" aria-label={copy.eclair_name}>
        <header className="ecl-top">
          <IconAction label={copy.eclair_back} onClick={() => void router.push(BACK_HREF)}>
            <CrossIcon size={16} />
          </IconAction>
          {phase === 'playing' && (
            <>
              <div className="ecl-clock">
                <ProgressRule value={left} max={round?.seconds ?? ECLAIR_SECONDS} label={fillMomentum(copy.eclair_time_left, { s: left })} />
              </div>
              <p className="ecl-live" aria-live="off">{fillMomentum(copy.eclair_score_live, { n: score })}</p>
            </>
          )}
        </header>

        {(phase === 'ready' || phase === 'starting' || phase === 'failed') && (
          <section className="ecl-body">
            <h1 className="av2-headline av2-headline--screen">{copy.eclair_name}</h1>
            {names && <p className="ecl-pair" lang="fr">{names}</p>}
            <p className="ecl-hint">{copy.eclair_hint}</p>
            {phase === 'failed' && (
              <Notice tone="alert" live="alert" shape="action">
                <p>{copy.eclair_failed_start}</p>
              </Notice>
            )}
            <Action tone="primary" pending={phase === 'starting'} pendingLabel={copy.eclair_starting} onClick={() => void start()}>
              {copy.eclair_start}
            </Action>
            <Link className="ecl-back" href={BACK_HREF}>{copy.eclair_back}</Link>
          </section>
        )}

        {phase === 'playing' && item && (
          <section className="ecl-body ecl-play">
            <p className="ecl-cue">{eclairCue(item, language) || copy.eclair_question}</p>
            <div className="ecl-options" role="group" aria-label={copy.eclair_question}>
              {item.labels.map((label) => {
                const state = flash?.label === label ? (flash.correct ? 'right' : 'wrong') : flash && !flash.correct && label === item.correct_answer ? 'answer' : undefined;
                return (
                  <button
                    key={`${item.id}:${label}`}
                    type="button"
                    className="ecl-option"
                    data-state={state}
                    lang="fr"
                    onClick={() => choose(label)}
                    disabled={Boolean(flash)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {(phase === 'saving' || phase === 'done') && (
          <section className="ecl-body" aria-live="polite">
            <h1 className="av2-headline av2-headline--screen">
              {fillMomentum(copy.eclair_done_title, { n: result?.score ?? score })}
            </h1>
            {names && <p className="ecl-pair" lang="fr">{names}</p>}
            {result ? (
              <p className="ecl-hint">
                {fillMomentum(copy.eclair_done_sub, { answered: result.answered, best: result.best })}
              </p>
            ) : (
              <p className="ecl-hint">{copy.eclair_saving}</p>
            )}
            {result?.new_best && result.score > 0 && (
              <p className="ecl-best"><span className="ecl-best__mark" aria-hidden="true" />{copy.eclair_new_best}</p>
            )}
            <Action tone="primary" disabled={phase === 'saving'} onClick={() => void start()}>
              {copy.eclair_again}
            </Action>
            <Link className="ecl-back" href={BACK_HREF}>{copy.eclair_back}</Link>
          </section>
        )}
      </AtelierV2Root>
    </>
  );
}

/* Tokens only; no border on a shape, no stroke. */
function EclairStyles() {
  return (
    <style jsx global>{`
.av2.ecl { min-height: 100vh; min-height: 100dvh; background: var(--av2-paper); display: flex; flex-direction: column; }
.av2 .ecl-top {
  position: sticky;
  top: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: calc(12px + env(safe-area-inset-top, 0px)) var(--av2-gutter) 10px;
  background: var(--av2-paper);
}
.av2 .ecl-clock { flex: 1 1 auto; min-width: 0; }
.av2 .ecl-live { flex: none; margin: 0; font-size: var(--av2-t-label); font-weight: 700; color: var(--av2-ink); font-variant-numeric: tabular-nums; }
.av2 .ecl-body { display: flex; flex-direction: column; gap: 16px; padding: 12px var(--av2-gutter) calc(24px + var(--av2-safe-bottom, 0px)); max-width: 560px; width: 100%; margin: 0 auto; box-sizing: border-box; }
.av2 .ecl-pair { margin: 0; font-size: var(--av2-t-body); font-weight: 700; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .ecl-hint { margin: 0; font-size: var(--av2-t-body); color: var(--av2-ink-2); }
.av2 .ecl-back { align-self: center; min-height: var(--av2-tap); display: inline-flex; align-items: center; color: var(--av2-ink-2); font-weight: 600; font-size: var(--av2-t-label); text-decoration: underline; text-underline-offset: 3px; }
.av2 .ecl-cue { margin: 0; font-size: var(--av2-t-body); font-weight: 600; color: var(--av2-ink-2); overflow-wrap: anywhere; }
.av2 .ecl-options { display: flex; flex-direction: column; gap: 12px; }
.av2 .ecl-option {
  min-height: 64px;
  padding: 14px 16px;
  border: 0;
  border-radius: var(--av2-r-tile);
  background: var(--av2-card);
  box-shadow: 0 var(--av2-press-sm, 3px) 0 var(--av2-line-2);
  color: var(--av2-ink);
  font: 600 var(--av2-t-option)/1.3 var(--av2-sans);
  text-align: left;
  cursor: pointer;
  overflow-wrap: anywhere;
  transition: background-color 0.12s ease, transform 0.08s ease;
}
.av2 .ecl-option:active { transform: translateY(2px); box-shadow: 0 1px 0 var(--av2-line-2); }
.av2 .ecl-option:disabled { cursor: default; }
.av2 .ecl-option[data-state='right'] { background: var(--av2-tint-correct); }
.av2 .ecl-option[data-state='wrong'] { background: var(--av2-tint-wrong); }
.av2 .ecl-option[data-state='answer'] { background: var(--av2-tint-correct); }
.av2 .ecl-best { margin: 0; display: inline-flex; align-items: center; gap: 8px; font-size: var(--av2-t-label); font-weight: 700; color: var(--av2-ink); }
.av2 .ecl-best__mark { width: 14px; height: 14px; border-radius: 3px; background: var(--av2-yellow); }
@media (prefers-reduced-motion: reduce) {
  .av2 .ecl-option { transition: none; }
  .av2 .ecl-option:active { transform: none; }
}
    `}</style>
  );
}
