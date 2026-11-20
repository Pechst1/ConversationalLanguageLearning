/**
 * «Le fil» · the first three screens.
 *
 * «Lire»: the story's picture, the dateline, the lead at the learner's band (every
 * word tappable, «Traduire», ▶), the source; «Au fil →».
 *
 * «Remettre en ordre»: Romy's line, the four dispatches as they came in. Without
 * drag: the number on a dispatch selects it and a second number swaps the two, or
 * ↑ / ↓ move one place (44 px each). «Vérifier l'ordre» sends the order; a wrong one
 * names the first dispatch out of place and the one it comes after (from the
 * dispatches' own names, in the learner's language), never the solution; the
 * second wrong one shows the right order. Two tries at most.
 *
 * «Les mots du fil»: A1 puts its four words on the dispatches (tap a dispatch, then a
 * word); from A2 each dispatch offers three words, one per place in a story. A miss
 * says what the word means (its gloss) and what the dispatch needs; the second miss
 * shows the right words.
 */

import React, { useEffect, useState } from 'react';

import { Action, ArrowRightIcon, IconAction } from '@/components/atelier-v2/ui';
import type { LineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import type { RvFilBody, RvFilView } from '@/lib/revue-fil-types';
import type { RvGloss, RvLanguage, RvSessionView } from '@/lib/revue-types';

import type { ComptoirCopy } from '../comptoir/comptoir-copy';
import { ComptoirPicture, ListenChip, RomyLine } from '../comptoir/RvComptoirParts';
import { fill, type RevueCopy } from '../revue-copy';
import { RvGallery } from '../RvGallery';
import { RvGlossText, RvSourceLine, RvTranslate, type RvWordEvent } from '../RvThread';
import { FIL_FR, FIL_LINES, type FilCopy } from './fil-copy';
import { allPicked, missText, move, orderHintText, swap } from './fil-model';

/** What each screen is given by `RvFil`. */
export type FilStepProps = {
  session: RvSessionView;
  view: RvFilView;
  chrome: RvLanguage;
  copy: RevueCopy;
  ccopy: ComptoirCopy;
  fcopy: FilCopy;
  /** The reasons (the order's, a missed word's, a refused telling's): the mother tongue, as the
   * counter's whys, while the chrome is French from B1. */
  xcopy: FilCopy;
  glossLanguage: RvLanguage;
  glosses: RvGloss[];
  voice: LineVoice;
  pending: string | null;
  readOnly: boolean;
  onAct: (body: RvFilBody, key: string) => Promise<boolean>;
  onContinue: () => void;
  wordFor: (speakerId: string | null, speakerName?: string) => (event: RvWordEvent) => void;
  notice: React.ReactNode;
  footRef: React.Ref<HTMLDivElement>;
};

// ---------------------------------------------------------------------------
// «Lire»
// ---------------------------------------------------------------------------

export function RvFilRead(props: FilStepProps) {
  const { session, view, copy, ccopy, glossLanguage, glosses, voice, pending, readOnly, onContinue, wordFor, notice, footRef } = props;
  const lead = view.read.lead;
  const source = view.read.sources[0] ?? null;
  return (
    <>
      <div className="rv-body ct-body" data-step="read">
        <ComptoirPicture url={session.stage.plateUrl} credit={session.stage.plateKind === 'story'} />
        <RvGallery pictures={session.stage.pictures} mainUrl={session.stage.plateUrl} copy={copy} />
        <section className="rv-lead ct-lead" aria-label={copy.lead_kicker}>
          <p className="rv-lead__k">
            {copy.lead_kicker}
            {view.read.datelineFr && (
              <>
                {' · '}
                <span lang="fr">{view.read.datelineFr}</span>
              </>
            )}
          </p>
          <p className="rv-lead__fr" lang="fr">
            <RvGlossText text={lead.fr} glosses={glosses} mode={session.plan.support.glosses} glossLanguage={glossLanguage} onWord={wordFor(null)} />
          </p>
          <RvTranslate
            textFr={lead.fr}
            translation={lead.tr}
            glossLanguage={glossLanguage}
            copy={copy}
            before={<ListenChip voice={voice} voiceKey={`fl-lead-${session.id}`} textFr={lead.fr} castId="romy_tremblay" copy={copy} ccopy={ccopy} />}
          />
          {source && <RvSourceLine source={source} copy={copy} />}
        </section>
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          <Action tone="primary" lang="fr" pending={pending === 'open'} pendingLabel={FIL_FR.press} disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
            {FIL_FR.press}
          </Action>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «Remettre en ordre»
// ---------------------------------------------------------------------------

function StripText({ textFr, tr, props }: { textFr: string; tr: string | null; props: FilStepProps }) {
  const { glosses, glossLanguage, copy, wordFor } = props;
  return (
    <div className="fl-strip__text">
      <p className="fl-strip__fr" lang="fr">
        <RvGlossText text={textFr} glosses={glosses} mode="tap" glossLanguage={glossLanguage} onWord={wordFor(null)} />
      </p>
      <RvTranslate textFr={textFr} translation={tr} glossLanguage={glossLanguage} copy={copy} />
    </div>
  );
}

export function RvFilOrder(props: FilStepProps) {
  const { view, copy, fcopy, xcopy, glossLanguage, pending, readOnly, onAct, onContinue, notice, footRef } = props;
  const order = view.order!;
  const shownKeys = order.strips.map((strip) => strip.key);
  const start = order.placed.length === 4 ? order.placed : shownKeys;
  const [arrangement, setArrangement] = useState<string[]>(start);
  const [selected, setSelected] = useState<number | null>(null);
  const placedKey = order.placed.join('');
  useEffect(() => {
    if (order.placed.length === 4) setArrangement(order.placed);
    setSelected(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placedKey, order.tries]);
  const rows = order.resolved ? order.solution : arrangement;
  const byKey = new Map(order.strips.map((strip) => [strip.key, strip]));
  const busy = readOnly || pending !== null;
  const misplaced = !order.resolved && order.hint ? order.hint.key : null;
  // The server keeps one try per arrangement: the same order again would answer nothing.
  const unchanged = order.tries > 0 && arrangement.join('') === placedKey;

  const pick = (index: number) => {
    if (busy || order.resolved) return;
    if (selected === null) setSelected(index);
    else {
      setArrangement((current) => swap(current, selected, index));
      setSelected(null);
    }
  };

  return (
    <>
      <div className="rv-body ct-body" data-step="order">
        <RomyLine line={FIL_LINES.order_ask} props={props} />
        {!order.resolved && <p className="ct-hint">{fcopy.order_task}</p>}
        <ol className="fl-strips" aria-label={FIL_FR.name}>
          {rows.map((key, index) => {
            const strip = byKey.get(key);
            if (!strip) return null;
            return (
              <li key={key} className="fl-strip" data-key={key} data-selected={selected === index ? '' : undefined} data-misplaced={misplaced === key ? '' : undefined}>
                <button
                  type="button"
                  className="fl-strip__n"
                  aria-pressed={selected === index}
                  aria-label={`${index + 1}`}
                  disabled={busy || order.resolved}
                  onClick={() => pick(index)}
                >
                  {index + 1}
                </button>
                <StripText textFr={strip.text.fr} tr={strip.text.tr} props={props} />
                {!order.resolved && (
                  <span className="fl-strip__moves">
                    <IconAction label={fcopy.move_up} disabled={busy || index === 0} onClick={() => setArrangement((current) => move(current, index, -1))}>
                      <span aria-hidden="true">↑</span>
                    </IconAction>
                    <IconAction label={fcopy.move_down} disabled={busy || index === rows.length - 1} onClick={() => setArrangement((current) => move(current, index, 1))}>
                      <span aria-hidden="true">↓</span>
                    </IconAction>
                  </span>
                )}
              </li>
            );
          })}
        </ol>
        {misplaced && order.hint && (
          <p className="ct-why fl-hint" data-ct-anchor="nearest">
            {orderHintText(xcopy, order.strips, order.hint, glossLanguage)}
          </p>
        )}
        {order.resolved && (
          <p className="ct-why" data-ct-anchor="nearest">
            {order.correct ? fcopy.order_right : fcopy.order_shown}
          </p>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {order.resolved ? (
            <Action tone="primary" disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
              {copy.continue}
            </Action>
          ) : (
            <>
              {unchanged && <p className="ct-foot__hint">{fcopy.order_unchanged}</p>}
              <p className="ct-foot__hint">{fill(fcopy.try_n, { n: String(order.tries + 1), max: String(order.maxTries) })}</p>
              <Action tone="primary" pending={pending === 'order'} pendingLabel={fcopy.order_check} disabled={busy || unchanged} onClick={() => void onAct({ act: 'order', order: arrangement }, 'order')}>
                {fcopy.order_check}
              </Action>
            </>
          )}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «Les mots du fil»
// ---------------------------------------------------------------------------

export function RvFilWords(props: FilStepProps) {
  const { view, copy, fcopy, xcopy, glossLanguage, pending, readOnly, onAct, onContinue, notice, footRef } = props;
  const words = view.words!;
  const start = (words.resolved ? words.solution : words.picked).length === 4 ? (words.resolved ? words.solution : words.picked) : [null, null, null, null];
  const [picks, setPicks] = useState<Array<string | null>>(start);
  const [slot, setSlot] = useState<number>(0);
  const pickedKey = words.picked.join('|');
  const wordsUnchanged = !words.resolved && words.tries > 0 && picks.join('|') === pickedKey;
  useEffect(() => {
    if (words.resolved && words.solution.length === 4) setPicks(words.solution);
    else if (words.picked.length === 4) setPicks(words.picked);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickedKey, words.resolved]);
  const byId = new Map(words.connectors.map((connector) => [connector.id, connector]));
  const busy = readOnly || pending !== null || words.resolved;
  const missAt = new Map(words.resolved ? [] : words.misses.map((miss) => [miss.position, miss]));

  const place = (id: string) => {
    if (busy) return;
    setPicks((current) => {
      const next = current.map((value) => (value === id ? null : value));
      const target = next[slot] === null ? slot : next.findIndex((value) => value === null);
      if (target < 0) return current;
      next[target] = id;
      const empty = next.findIndex((value) => value === null);
      setSlot(empty < 0 ? target : empty);
      return next;
    });
  };

  return (
    <>
      <div className="rv-body ct-body" data-step="words" data-input={words.input}>
        <RomyLine line={FIL_LINES.words_ask} props={props} />
        {!words.resolved && <p className="ct-hint">{words.input === 'place' ? fcopy.words_task_place : fcopy.words_task_choose}</p>}
        <ol className="fl-strips" aria-label={FIL_FR.name}>
          {words.strips.map((strip, index) => {
            const picked = picks[index] ? byId.get(picks[index] as string) : null;
            return (
              <li key={index} className="fl-strip" data-miss={missAt.has(index) ? '' : undefined}>
                {words.input === 'place' ? (
                  <button
                    type="button"
                    className="fl-slot"
                    lang="fr"
                    aria-pressed={!busy && slot === index}
                    disabled={busy}
                    onClick={() => {
                      setSlot(index);
                      if (picks[index]) setPicks((current) => current.map((value, at) => (at === index ? null : value)));
                    }}
                  >
                    {picked ? picked.fr : fcopy.slot_empty}
                  </button>
                ) : (
                  <span className="fl-options" role="radiogroup" aria-label={`${index + 1}`}>
                    {(words.options[index] ?? []).map((id) => (
                      <button
                        key={id}
                        type="button"
                        role="radio"
                        className="fl-option"
                        lang="fr"
                        aria-checked={picks[index] === id}
                        disabled={busy}
                        onClick={() => setPicks((current) => current.map((value, at) => (at === index ? id : value)))}
                      >
                        {byId.get(id)?.fr ?? id}
                      </button>
                    ))}
                  </span>
                )}
                <StripText textFr={strip.fr} tr={strip.tr} props={props} />
                {missAt.has(index) && (
                  <p className="ct-why fl-miss" data-ct-anchor="nearest">
                    {missText(xcopy, missAt.get(index) as (typeof words.misses)[number])}
                  </p>
                )}
                {words.resolved && picked?.tr && (
                  <p className="ct-why" lang={glossLanguage}>
                    <b lang="fr">{picked.fr}</b> · {picked.tr}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
        {words.input === 'place' && !words.resolved && (
          <div className="ct-bank" role="group" aria-label={fcopy.word_label}>
            {words.connectors.map((connector) => (
              <button key={connector.id} type="button" className="ct-bank__b" lang="fr" aria-pressed={picks.includes(connector.id)} disabled={busy} onClick={() => place(connector.id)}>
                {connector.fr}
              </button>
            ))}
          </div>
        )}
        {words.resolved && (
          <p className="ct-why" data-ct-anchor="nearest">
            {words.correct ? fcopy.words_right : fcopy.words_shown}
          </p>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {words.resolved ? (
            <Action tone="primary" disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
              {copy.continue}
            </Action>
          ) : (
            <>
              {wordsUnchanged && <p className="ct-foot__hint">{fcopy.words_unchanged}</p>}
              <p className="ct-foot__hint">{fill(fcopy.try_n, { n: String(words.tries + 1), max: String(words.maxTries) })}</p>
              <Action
                tone="primary"
                pending={pending === 'words'}
                pendingLabel={fcopy.words_check}
                disabled={busy || !allPicked(picks) || wordsUnchanged}
                onClick={() => allPicked(picks) && void onAct({ act: 'words', picks }, 'words')}
              >
                {fcopy.words_check}
              </Action>
            </>
          )}
        </div>
      )}
    </>
  );
}
