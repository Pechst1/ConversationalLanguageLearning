/**
 * «Trois mots» (2026-11-21, `REVUE_TROIS_MOTS_ENABLED`) — the closing round, the first block of
 * «La page» once the Papier is closed.
 *
 * 1. Match: three French words, three cues (a picture of the story that names the word, else its
 *    meaning in the mother tongue). Tap a cue: it goes to the first word still without one; tap a
 *    word to let its cue go. «Vérifier» once all three are matched. A miss says, in the mother
 *    tongue, which pairs were wrong — never which cue was right — and the second try is the last:
 *    then the solution with each word's meaning.
 * 2. The gap: one sentence of the story's own text with a word taken out; pick it among the three.
 *    A miss says what the picked word means; after the second, the sentence whole.
 *
 * `RvTroisMotsSlot` asks the server for the round and draws NOTHING when the switch is off, the
 * read fails, the session has no round, or a reopened page finds it already done. Markup is
 * semantic and the CSS minimal (`tm-*`, a few rules on the av2 tokens): the Papier's print art
 * direction styles it afterwards.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';

import { Action } from '@/components/atelier-v2/ui';
import { resolveMediaUrl } from '@/lib/media-url';
import type { RvLanguage } from '@/lib/revue-types';
import type { RdvClient, RvTmCue, RvTmWordKey, RvTroisMots, RvTroisMotsBody } from '@/lib/revue-rdv';

import { bringIntoView } from '../comptoir/scroll';
import { PpCutting } from '../papier/PapierPrint';
import { RDV_FR, fillRdv, rdvCopy, type RdvCopy } from './rdv-copy';
import { complete, gapMissLine, keepRight, missLines, pairCue, shownPairs, unpair, type Pairs } from './rdv-model';
import { useRdv } from './RdvContext';

export type RvTroisMotsViewProps = {
  round: RvTroisMots;
  /** The learner's pairs before they are checked. */
  pairs: Pairs;
  /** The chrome (`plan.ui_language`). */
  copy: RdvCopy;
  /** The reasons: the mother tongue. */
  xcopy: RdvCopy;
  pending: boolean;
  onPairs: (pairs: Pairs) => void;
  onAct: (body: RvTroisMotsBody) => void;
};

/** A picture cue: the story's picture in a small press frame, its credit printed under it. */
function CueBody({ cue, copy }: { cue: RvTmCue; copy: RdvCopy }) {
  if (cue.kind === 'picture' && cue.picture) {
    const src = resolveMediaUrl(cue.picture.url) ?? cue.picture.url;
    return (
      <span className="tm-cue__pic pp-tm-pic">
        <span className="pp-tm-pic__frame">
          {/* eslint-disable-next-line @next/next/no-img-element -- a story picture, already sized */}
          <img src={src} alt={cue.picture.altFr || copy.tm_picture_cue} loading="lazy" decoding="async" />
        </span>
        <span className="tm-cue__credit pp-tm-pic__credit" lang="fr">
          {cue.picture.creditFr}
        </span>
      </span>
    );
  }
  return <span className="tm-cue__text">{cue.text}</span>;
}

/**
 * «Papier · la belle édition»: three words set as a small dictionary — each an entry, its
 * headword in the serif, its sense set beside it once matched (a blank rule until then, the
 * cue picture in its press frame when it is one); the cues are the slips to set; the gap
 * sentence a cutting from the article with the gap as a blank rule.
 */
export function RvTroisMotsView({ round, pairs, copy, xcopy, pending, onPairs, onAct }: RvTroisMotsViewProps) {
  const matchOpen = !round.match.resolved;
  const shown = shownPairs(round, pairs);
  const misses = missLines(round, xcopy);
  const cueOf = (word: RvTmWordKey) => round.cues.find((c) => c.key === shown[word]) ?? null;
  const gap = round.gap;
  const gapMiss = gapMissLine(round, xcopy);
  return (
    <section className="tm pp-tm" aria-labelledby={`tm-${round.sessionId}`} data-tm-step={round.step}>
      <h2 className="tm__k" id={`tm-${round.sessionId}`} lang="fr">
        {RDV_FR.trois_mots}
      </h2>

      {/* 1 · Match */}
      <p className="tm__task">{copy.tm_task_match}</p>
      <ol className="tm-words pp-dict">
        {round.words.map((word, index) => {
          const cue = cueOf(word.key);
          return (
            <li key={word.key} className="tm-word pp-entry" data-paired={cue ? '' : undefined} data-cue={cue?.kind}>
              <span className="pp-entry__n" aria-hidden="true">
                {index + 1}
              </span>
              <button
                type="button"
                className="tm-word__btn pp-entry__hw"
                disabled={!matchOpen || !pairs[word.key] || pending}
                onClick={() => onPairs(unpair(pairs, word.key))}
                aria-label={`${fillRdv(copy.tm_word_n, { n: index + 1 })} : ${word.fr}`}
              >
                <span lang="fr">{word.fr}</span>
              </button>
              <span className="tm-word__cue pp-entry__sense">
                {cue ? (
                  cue.kind === 'picture' ? (
                    <CueBody cue={cue} copy={copy} />
                  ) : (
                    <span className="pp-entry__gloss">{cue.text}</span>
                  )
                ) : (
                  <>
                    <span className="pp-blank" data-wide="" aria-hidden="true" />
                    <span className="tm-word__none av2-sr">{copy.tm_unpaired}</span>
                  </>
                )}
                {round.match.resolved && word.gloss && cue?.kind === 'picture' ? <span className="pp-entry__gloss"> {word.gloss}</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
      {matchOpen && (
        <ul className="tm-cues pp-slips">
          {round.cues.map((cue) => {
            const used = Object.values(pairs).includes(cue.key);
            return (
              <li key={cue.key} data-kind={cue.kind}>
                <button type="button" className="tm-cue pp-slip" aria-pressed={used} disabled={pending} onClick={() => onPairs(pairCue(pairs, cue.key))}>
                  <CueBody cue={cue} copy={copy} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {misses.length > 0 && (
        <div className="tm-why ct-why" role="status">
          {misses.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {matchOpen && <p>{xcopy.tm_try_again}</p>}
        </div>
      )}
      {round.match.resolved && (
        <p className="tm-verdict" data-correct={round.match.correct ? '' : undefined}>
          {round.match.correct ? copy.tm_match_right : copy.tm_match_shown}
        </p>
      )}
      {matchOpen && (
        <Action tone="primary" disabled={!complete(pairs) || pending} pending={pending} pendingLabel={copy.tm_check} onClick={() => complete(pairs) && onAct({ act: 'match', pairs })}>
          {copy.tm_check}
        </Action>
      )}

      {/* 2 · The gap: a cutting from the article, the gap a blank rule */}
      {gap && round.match.resolved && (
        <div className="tm-gap">
          <p className="tm__task">{copy.tm_task_gap}</p>
          <PpCutting seed={`${round.sessionId}:gap`} className="tm-gap__s">
            <blockquote className="pp-tm-cutting" lang="fr">
              {gap.resolved && gap.sentenceFr ? (
                <>
                  {gap.beforeFr}
                  <mark className="pp-tm-word">{round.words.find((w) => w.key === gap.solution)?.bareFr ?? ''}</mark>
                  {gap.afterFr}
                </>
              ) : (
                <>
                  {gap.beforeFr}
                  <span className="tm-gap__blank pp-blank" data-wide="" role="img" aria-label="…">
                    ____
                  </span>
                  {gap.afterFr}
                </>
              )}
            </blockquote>
          </PpCutting>
          {!gap.resolved && (
            <div className="tm-gap__opts pp-slips" role="group" aria-label={copy.tm_task_gap}>
              {round.words.map((word) => (
                <button key={word.key} type="button" className="pp-slip" lang="fr" disabled={pending} onClick={() => onAct({ act: 'gap', word: word.key })}>
                  {word.bareFr}
                </button>
              ))}
            </div>
          )}
          {gapMiss && (
            <div className="tm-why ct-why" role="status">
              <p>{gapMiss}</p>
              {!gap.resolved && <p>{xcopy.tm_try_again}</p>}
            </div>
          )}
          {gap.resolved && (
            <p className="tm-verdict" data-correct={gap.correct ? '' : undefined}>
              {gap.correct ? copy.tm_gap_right : copy.tm_gap_shown}
            </p>
          )}
        </div>
      )}

      {round.step === 'done' && <p className="tm-done">{copy.tm_done}</p>}
    </section>
  );
}

export type RvTroisMotsProps = {
  client: RdvClient;
  sessionId: string;
  chrome: RvLanguage;
  mother: RvLanguage;
  /** Given: drawn as is (tests). */
  initial?: RvTroisMots | null;
};

/** The round with its state: fetched once, each act sent and the server's view kept. */
export function RvTroisMots({ client, sessionId, chrome, mother, initial }: RvTroisMotsProps) {
  const [round, setRound] = useState<RvTroisMots | null>(initial ?? null);
  const [hidden, setHidden] = useState(initial === undefined ? true : !initial);
  const [pairs, setPairs] = useState<Pairs>({});
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (initial !== undefined) return undefined;
    let alive = true;
    client
      .troisMots(sessionId)
      .then((result) => {
        if (!alive) return;
        const next = result?.round ?? null;
        setRound(next);
        // A reopened page whose round is done: nothing to play again.
        setHidden(!next || next.step === 'done');
      })
      .catch(() => {
        // The round is an extra: a failing read leaves «La page» as it was.
      });
    return () => {
      alive = false;
    };
  }, [client, sessionId, initial]);

  const onAct = useCallback(
    async (body: RvTroisMotsBody) => {
      if (pending) return;
      setPending(true);
      try {
        const result = await client.troisMotsAct(sessionId, body);
        if (result.round) setRound(result.round);
        if (body.act === 'match' && result.round && !result.round.match.resolved) setPairs(keepRight(body.pairs, result.round));
      } catch {
        // Kept quiet: the learner can try again.
      } finally {
        setPending(false);
      }
    },
    [client, pending, sessionId],
  );

  // The round arrives after «La page» has scrolled to its clipping: bring the round's top under
  // the sticky head once, so the first block is what the learner sees first.
  const box = useRef<HTMLDivElement | null>(null);
  const shown = !hidden && Boolean(round);
  useEffect(() => {
    if (!shown || initial !== undefined || !box.current || typeof document === 'undefined') return;
    bringIntoView(box.current, document.querySelector<HTMLElement>('.rv-top'), document.querySelector<HTMLElement>('.rv-foot'), 'start');
    // Once, when it first shows.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown]);

  if (hidden || !round) return null;
  return (
    <div ref={box} className="tm-slot">
      <RvTroisMotsView round={round} pairs={pairs} copy={rdvCopy(chrome)} xcopy={rdvCopy(mother)} pending={pending} onPairs={setPairs} onAct={(body) => void onAct(body)} />
    </div>
  );
}

/** The slot «La page» calls: the round when the page's provider has a client, else nothing. */
export function RvTroisMotsSlot({ sessionId, chrome, mother, closed }: { sessionId: string; chrome: RvLanguage; mother: RvLanguage; closed: boolean }) {
  const rdv = useRdv();
  if (!rdv || !closed) return null;
  return <RvTroisMots client={rdv} sessionId={sessionId} chrome={chrome} mother={mother} />;
}

export default RvTroisMots;
