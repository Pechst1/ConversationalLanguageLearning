/* Word help — a bottom sheet on the app's single sheet spec: scrim
   rgba(20,17,13,.35), paper ground, 28px top radius, 40×5 handle, at-rise in.

   It is help, never a graded task: opening it changes no server state, records
   no attempt, and — crucially — does not move the learner's place in the
   episode. Closing it returns focus to the word that was tapped.

   Honest about what it knows: a word with no dictionary entry is read in its
   sentence (`/atelier/gloss`: its meaning here, its dictionary form); failing
   that, the sheet says so and offers the line's translation instead of
   inventing a gloss (the order: `word-help.ts`).

   WP-91 «Les voix»: the word says itself — a small «Écouter le mot» beside it,
   in the device's French voice (no server needed, works offline). */

import { useCallback, useEffect, useRef, useState } from 'react';

import { journeyCopy } from '@/components/atelier-v2/journey/journey-copy';
import { useLineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { canKeep, keepCopy, keepRefusal, keepStatusLine, type KeepState } from '@/lib/kept-words';
import { useLearnerLanguage } from '@/lib/learner-language';
import apiService from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { fillReaderCopy, readerCopy } from './reader-copy';
import { resolveWordHelp, type WordHelpGloss } from './word-help';

export type WordHelpRequest = {
  /** the surface form as printed */
  surface: string;
  /** the normalized form to look up */
  term: string;
  /** the line the word came from */
  sentence: string;
  /** the line's translation, when the payload already carried one */
  sentenceEn?: string;
  /** who said it, for the accent scope */
  character?: string;
  speaker?: string;
  /** WP-78: today's journey, when the word was tapped inside its scene. */
  journeyId?: string | null;
  /** WP-115a: who said the line, its panel and audio key — a kept word remembers them. */
  speakerId?: string | null;
  panelId?: string;
  lineKey?: string;
  /** 2026-10-19: the meaning the surface already knows (Le Papier's target words): shown at once, no lookup. */
  knownGloss?: string | null;
  /** The language `knownGloss` is written in (whether «Garder» may keep it). */
  knownGlossLanguage?: string | null;
};

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

export function WordHelpSheet({
  request,
  onClose,
  language = null,
  note,
  quoteLabel,
}: {
  request: WordHelpRequest | null;
  onClose: () => void;
  /** WP-82: the chrome's language; absent keeps French. */
  language?: ControlLanguage | null;
  /** The footnote; absent: the reader's («… ne fait pas avancer l'épisode»); `null`: none (Le Papier has no episode). */
  note?: string | null;
  /** Over the quoted line when it has no speaker; absent: the reader's «Dans la planche». */
  quoteLabel?: string;
}) {
  const t = readerCopy(language);
  const keepT = keepCopy(language);
  // The learner's own language (not the chrome's): the one a kept word's meaning must be in.
  const learnerLanguage = useLearnerLanguage();
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const [gloss, setGloss] = useState<WordHelpGloss>({ kind: 'loading' });
  const [sentenceEn, setSentenceEn] = useState('');
  const [keep, setKeep] = useState<KeepState>({ kind: 'idle' });
  const voice = useLineVoice();
  const sayLabel = journeyCopy(language ?? 'fr').word_listen;

  const open = Boolean(request);

  /* Remember what had focus, move focus into the sheet, restore on close. */
  useEffect(() => {
    if (!open) return undefined;
    restoreRef.current = (document.activeElement as HTMLElement) || null;
    const timer = window.setTimeout(() => closeRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(timer);
      const target = restoreRef.current;
      restoreRef.current = null;
      if (target && document.contains(target)) target.focus();
    };
  }, [open]);

  /* Escape closes; Tab is trapped inside the sheet. */
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const root = sheetRef.current;
      if (!root) return;
      const focusables = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (node) => node.offsetParent !== null || node === document.activeElement,
      );
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => document.removeEventListener('keydown', onKeyDown, true);
  }, [onClose, open]);

  /* Hold the page still behind the sheet. */
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  const term = request?.term || '';
  const surface = request?.surface || '';
  const sentence = request?.sentence || '';
  const suppliedEn = request?.sentenceEn || '';
  const knownGloss = request?.knownGloss || '';
  const knownGlossLanguage = request?.knownGlossLanguage ?? null;

  useEffect(() => {
    if (!term) return undefined;
    let alive = true;
    setKeep({ kind: 'idle' });
    setSentenceEn(suppliedEn);
    setGloss({ kind: 'loading' });
    // A meaning the surface already knows is shown as is (below): nothing to ask.
    if (knownGloss) return undefined;
    void resolveWordHelp({ term, surface, sentence, sentenceEn: suppliedEn }, apiService).then((answer) => {
      if (!alive) return;
      setGloss(answer.gloss);
      setSentenceEn(answer.sentenceEn);
    });
    return () => {
      alive = false;
    };
  }, [knownGloss, sentence, suppliedEn, surface, term]);

  const handleScrim = useCallback(() => onClose(), [onClose]);

  /* WP-78 «Garder»: the word joins the learner's Lexique with this sentence. */
  const keepWord = useCallback(async () => {
    if (!request) return;
    setKeep({ kind: 'saving' });
    try {
      const kept = await apiService.keepWord({
        term: request.term,
        sentence: request.sentence,
        surface: request.surface,
        journey_id: request.journeyId ?? null,
        speaker_id: request.speakerId ?? null,
        panel_id: request.panelId ?? null,
        line_key: request.lineKey ?? null,
      });
      setKeep({ kind: 'kept', already: Boolean(kept?.already_kept) });
    } catch (error) {
      const refusal = keepRefusal(error, language);
      setKeep({ kind: 'refused', message: refusal.message, retryable: refusal.retryable });
    }
  }, [language, request]);

  if (!request) return null;
  // Known at once (no «Recherche…» frame before it); «Garder» keeps it like a catalogue meaning.
  const shown: WordHelpGloss = knownGloss ? { kind: 'gloss', text: knownGloss, language: knownGlossLanguage } : gloss;

  return (
    <div className="fr-sheet-root" data-char={request.character || undefined}>
      <button type="button" className="fr-scrim" aria-label={t.help_close_label} onClick={handleScrim} />
      <div
        className="fr-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="fr-word-title"
        ref={sheetRef}
      >
        <div className="fr-handle" aria-hidden="true" />
        <div className="fr-sheet-head">
          <div className="lede">
            <div className="k">{t.help_kicker}</div>
            <h2 id="fr-word-title" lang="fr">{request.surface}</h2>
          </div>
          {/* One group: when the word and both buttons do not fit on a phone's row, the
              buttons move under the word together, instead of the word breaking into letters. */}
          <div className="fr-sheet-tools">
            {voice.supported && (
              <button
                type="button"
                className="av2-say"
                aria-pressed={voice.speakingKey === `word:${request.surface}`}
                onClick={() => voice.speak({ key: `word:${request.surface}`, text_fr: request.surface })}
              >
                <span className="av2-say__glyph" aria-hidden="true" />
                {sayLabel}
              </button>
            )}
            <button type="button" className="fr-sheet-close" onClick={onClose} ref={closeRef}>
              {t.help_close}
            </button>
          </div>
        </div>
        <div className="fr-sheet-body">
          <p className="fr-gloss" aria-live="polite">
            {shown.kind === 'loading' && t.help_searching}
            {(shown.kind === 'gloss' || shown.kind === 'context') && shown.text}
            {shown.kind === 'sentence' && t.help_sentence_only}
            {shown.kind === 'none' && t.no_translation}
          </p>
          {shown.kind === 'context' && shown.lemma && (
            <p className="fr-gloss-lemma">
              {t.help_lemma} <span lang="fr">{shown.lemma}</span>
            </p>
          )}
          {sentence && (
            <blockquote className="fr-quote">
              <p className="fr-quote-k">
                {request.speaker ? fillReaderCopy(t.help_in_line_of, { name: request.speaker }) : quoteLabel ?? t.help_in_panel}
              </p>
              <p className="fr-quote-fr">« {sentence} »</p>
              {sentenceEn && <p className="fr-quote-en">{sentenceEn}</p>}
            </blockquote>
          )}
          {/* A meaning read in the sentence is no catalogue row: the server could not keep it. */}
          {canKeep(shown.kind, sentence, shown.kind === 'gloss' ? shown.language : null, learnerLanguage) && (
            <div className="fr-keep">
              {keep.kind === 'idle' || keep.kind === 'saving' || (keep.kind === 'refused' && keep.retryable) ? (
                <button
                  type="button"
                  className="fr-keep-btn"
                  onClick={() => void keepWord()}
                  disabled={keep.kind === 'saving'}
                >
                  {keep.kind === 'saving' ? keepT.saving : keepT.action}
                </button>
              ) : null}
              {keep.kind !== 'idle' && keep.kind !== 'saving' && (
                <p
                  className="fr-keep-status"
                  role="status"
                  data-keep-result={keep.kind === 'kept' ? 'kept' : keep.retryable ? 'retry' : 'refused'}
                >
                  {keepStatusLine(keep, language)}
                </p>
              )}
            </div>
          )}
          {note !== null && note !== '' && <p className="fr-sheet-note">{note ?? t.help_note}</p>}
        </div>
      </div>
    </div>
  );
}

export default WordHelpSheet;
