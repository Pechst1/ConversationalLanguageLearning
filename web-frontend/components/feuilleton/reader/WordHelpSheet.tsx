/* Word help — a bottom sheet on the app's single sheet spec: scrim
   rgba(20,17,13,.35), paper ground, 28px top radius, 40×5 handle, at-rise in.

   It is help, never a graded task: opening it changes no server state, records
   no attempt, and — crucially — does not move the learner's place in the
   episode. Closing it returns focus to the word that was tapped.

   Honest about what it knows: a word with no dictionary entry says so, and
   offers the line's translation instead of inventing a gloss. */

import { useCallback, useEffect, useRef, useState } from 'react';

import { learnerGloss } from '@/lib/glosses';
import apiService from '@/services/api';

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
};

type GlossState =
  | { kind: 'loading' }
  | { kind: 'gloss'; text: string }
  | { kind: 'sentence'; text: string }
  | { kind: 'none' };

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

export function WordHelpSheet({
  request,
  onClose,
}: {
  request: WordHelpRequest | null;
  onClose: () => void;
}) {
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const [gloss, setGloss] = useState<GlossState>({ kind: 'loading' });
  const [sentenceEn, setSentenceEn] = useState('');

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
  const sentence = request?.sentence || '';
  const suppliedEn = request?.sentenceEn || '';

  useEffect(() => {
    if (!term) return undefined;
    let alive = true;
    setGloss({ kind: 'loading' });
    setSentenceEn(suppliedEn);
    (async () => {
      try {
        const entry = (await apiService.lookupVocabulary(term)) as Record<string, any>;
        const text = learnerGloss(entry as any, '');
        if (!alive) return;
        if (text) {
          setGloss({ kind: 'gloss', text });
          return;
        }
      } catch {
        /* 404 is the ordinary answer for a word that is not a catalogue entry. */
      }
      if (!alive) return;
      // No dictionary entry: translate the line instead of guessing the word.
      if (suppliedEn) {
        setGloss({ kind: 'sentence', text: suppliedEn });
        return;
      }
      if (!sentence) {
        setGloss({ kind: 'none' });
        return;
      }
      try {
        const translated = await apiService.translateToEnglish(sentence);
        if (!alive) return;
        if (translated) {
          setSentenceEn(translated);
          setGloss({ kind: 'sentence', text: translated });
        } else {
          setGloss({ kind: 'none' });
        }
      } catch {
        if (alive) setGloss({ kind: 'none' });
      }
    })();
    return () => {
      alive = false;
    };
  }, [sentence, suppliedEn, term]);

  const handleScrim = useCallback(() => onClose(), [onClose]);

  if (!request) return null;

  return (
    <div className="fr-sheet-root" data-char={request.character || undefined}>
      <button type="button" className="fr-scrim" aria-label="Fermer l’aide" onClick={handleScrim} />
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
            <div className="k">Aide au mot</div>
            <h2 id="fr-word-title">{request.surface}</h2>
          </div>
          <button type="button" className="fr-sheet-close" onClick={onClose} ref={closeRef}>
            Fermer
          </button>
        </div>
        <div className="fr-sheet-body">
          <p className="fr-gloss" aria-live="polite">
            {gloss.kind === 'loading' && 'Recherche…'}
            {gloss.kind === 'gloss' && gloss.text}
            {gloss.kind === 'sentence' && 'Pas d’entrée pour ce mot seul — voici la phrase.'}
            {gloss.kind === 'none' && 'Aucune traduction disponible pour l’instant.'}
          </p>
          {sentence && (
            <blockquote className="fr-quote">
              <p className="fr-quote-k">
                {request.speaker ? `Dans la réplique de ${request.speaker}` : 'Dans la planche'}
              </p>
              <p className="fr-quote-fr">« {sentence} »</p>
              {sentenceEn && <p className="fr-quote-en">{sentenceEn}</p>}
            </blockquote>
          )}
          <p className="fr-sheet-note">
            Consulter l’aide ne compte pas comme une réponse et ne fait pas avancer l’épisode.
          </p>
        </div>
      </div>
    </div>
  );
}

export default WordHelpSheet;
