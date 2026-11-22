/**
 * «La dictée de Romy» (2026-11-22, `REVUE_VOIX_ENABLED`) — the reading screen's optional closer:
 * one sentence of the lead, read by the newsroom's voice, written by the learner, graded by the
 * radio's adapter of the journey's dictation grader (no model call).
 *
 * Folded at first into one printed line («La dictée de Romy — une phrase du chapeau, à
 * l'oreille»). Opened, the lead above is covered (its lines ruled, not set) so the sentence is
 * written from the ear, not copied. A miss shows Romy's proof marks on the learner's own words
 * (`RvProofMarks`, the counter's) and never the sentence; the sentence and the grader's note come
 * after the second try, or once it is right. Only offered when a real clip can be made.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';

import { textAnswerField } from '@/components/atelier-v2/ui/Choice';
import type { VxDicteeResult } from '@/lib/revue-voix';

import { comptoirCopy } from '../comptoir/comptoir-copy';
import { RvProofMarks } from '../comptoir/RvProofMarks';
import { fillVoix, VOIX_FR } from './voix-copy';
import { useVoixScope } from './VoixContext';

const KEY = 'vx-dictee';

export function VxDictee() {
  const scope = useVoixScope();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [result, setResult] = useState<VxDicteeResult | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const rootRef = useRef<HTMLElement | null>(null);

  const resolved = Boolean(result?.resolved);
  const dictee = scope?.manifest.dictee ?? null;
  // While the learner writes, the lead above is covered: the sentence comes from the ear. Once
  // the dictée cannot be offered (a clip failed: it renders nothing), the lead is uncovered at
  // once — no half state. The body is remembered, so it is uncovered even when this unmounts.
  const covering = open && !resolved && Boolean(dictee) && !scope?.failed;
  const bodyRef = useRef<Element | null>(null);
  useEffect(() => {
    const body = rootRef.current?.closest('.rv-body') ?? bodyRef.current;
    if (!body) return undefined;
    bodyRef.current = body;
    if (covering) body.setAttribute('data-vx-dictee', '');
    else body.removeAttribute('data-vx-dictee');
    return () => body.removeAttribute('data-vx-dictee');
  }, [covering]);

  const speak = useCallback(() => {
    if (!scope || !dictee) return;
    if (scope.voice.speakingKey === KEY) scope.voice.stop();
    else scope.voice.speak({ key: KEY, text_fr: dictee.textFr, character_id: scope.manifest.newsreaderId });
  }, [dictee, scope]);

  if (!scope || !dictee || scope.failed) return null;
  const { copy } = scope;
  const marksCopy = comptoirCopy(scope.motherTongue);
  const speaking = scope.voice.speakingKey === KEY;
  const attempt = result && !result.resolved ? result.attempt + 1 : 1;

  const submit = async () => {
    const value = text.trim();
    if (!value || pending) return;
    setPending(true);
    setFailed(false);
    try {
      setResult(await scope.client.dictee(scope.sessionId, value, attempt));
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  };

  if (!open) {
    return (
      <section className="vx-dictee" data-state="folded" aria-label={VOIX_FR.dictee_title} ref={rootRef}>
        <p className="vx-dictee__k" lang="fr">
          {VOIX_FR.dictee_title}
        </p>
        <p className="vx-dictee__offer">{copy.dictee_offer}</p>
        <p className="vx-dictee__tools">
          <button
            type="button"
            className="vx-link"
            onClick={() => {
              setOpen(true);
              speak();
            }}
          >
            {copy.dictee_start}
          </button>
        </p>
      </section>
    );
  }

  return (
    <section className="vx-dictee" data-state={resolved ? 'done' : 'open'} aria-label={VOIX_FR.dictee_title} ref={rootRef}>
      <p className="vx-dictee__k" lang="fr">
        {VOIX_FR.dictee_title}
      </p>
      {!resolved && <p className="vx-dictee__task">{copy.dictee_task}</p>}
      <p className="vx-dictee__tools">
        <button type="button" className="vx-link vx-link--play" aria-pressed={speaking} onClick={speak}>
          <span className="vx-tri" aria-hidden="true" />
          {result || speaking ? copy.dictee_again : copy.dictee_hear}
        </button>
      </p>
      {result && result.marks.length > 0 && (
        <div className="vx-dictee__proof ct-paper">
          <RvProofMarks
            key={`marks-${result.attempt}`}
            draftFr={result.answerFr}
            marks={result.marks}
            kindLabels={marksCopy.mark_kinds}
            copy={marksCopy.pourquoi}
            whyLanguage={scope.motherTongue}
            idPrefix="vx"
          />
        </div>
      )}
      {result && !resolved && (
        <p className="vx-dictee__say" role="status">
          {copy.dictee_marked} {fillVoix(copy.dictee_try, { n: String(attempt), max: String(result.maxTries) })}
        </p>
      )}
      {resolved && result && (
        <div className="vx-dictee__done" role="status">
          <p className="vx-dictee__verdict" data-outcome={result.outcome}>
            {result.outcome === 'met' ? copy.dictee_met : result.outcome === 'partially_met' ? copy.dictee_accents : copy.dictee_shown}
          </p>
          {result.outcome !== 'met' && result.expectedFr && (
            <p className="vx-dictee__line" lang="fr">
              {result.expectedFr}
            </p>
          )}
          {result.note && result.outcome !== 'met' && <p className="vx-dictee__note" lang={scope.motherTongue}>{result.note}</p>}
        </div>
      )}
      {!resolved && (
        <form
          className="vx-dictee__form pp-notebook"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {textAnswerField({
            label: copy.dictee_field,
            value: text,
            placeholder: copy.dictee_placeholder,
            rows: 2,
            disabled: pending,
            onChange: setText,
          })}
          {failed && <p className="vx-dictee__say">{copy.dictee_failed}</p>}
          <p className="vx-dictee__tools">
            <button type="submit" className="vx-link vx-link--submit" aria-busy={pending || undefined} disabled={!text.trim() || pending}>
              {copy.dictee_check}
            </button>
          </p>
        </form>
      )}
      {resolved && (
        <p className="vx-dictee__tools">
          <button type="button" className="vx-link" onClick={() => setOpen(false)}>
            {copy.dictee_close}
          </button>
        </p>
      )}
    </section>
  );
}

/** The slot a reading screen calls: nothing without the voice. */
export function VxDicteeSlot() {
  const scope = useVoixScope();
  if (!scope?.manifest.dictee) return null;
  return <VxDictee />;
}
