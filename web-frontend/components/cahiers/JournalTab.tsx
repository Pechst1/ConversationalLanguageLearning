/**
 * WP-30 — «Le journal de bord», the Cahier's fourth tab.
 *
 * The learner writes yesterday's scene from memory, in French, and *then* reads
 * it back. Everything about this screen follows from that one sentence:
 *
 *   * **While writing, there is no scene on screen.** The cue block prints the
 *     character, the place and how long ago — the three things the server sends
 *     in `entry.cue`. The reveal is a different object (`entry.reveal`) that the
 *     API only attaches once the entry has text, so this component cannot leak
 *     it early even by accident: before submission there is nothing to render.
 *   * **One correction up front, the rest on demand.** `correction.foreground`
 *     is shown as a single `<Correction>`; the full list is behind a
 *     «Tout voir» disclosure, so a strict corrector preference is never
 *     silently reduced to one line.
 *   * **Two verdicts, never merged.** The French and what was remembered are
 *     two separate blocks with two separate sentences. Correct French about the
 *     wrong evening must not read as a pass.
 *   * **An ungraded entry says so.** `assessment_status === 'unavailable'` gets
 *     a French sentence and keeps the learner's own paragraph on screen. It is
 *     never dressed as a verdict, and it never turns into a red mark.
 *
 * Chrome: av2 tokens only, French copy, pill sentence-case actions, dark mode
 * from the tokens. Styles are `.av2 .jn-*` (0,2,0) like the rest of the Cahier.
 */
import React, { useCallback, useEffect, useState } from 'react';

import {
  Action,
  Correction,
  Notice,
  ShapeToken,
  Skeleton,
  StateBlock,
  Surface,
  textAnswerField,
} from '@/components/atelier-v2/ui';
import api, {
  type JournalCorrectionItem,
  type JournalEntryView,
  type JournalEnvelope,
} from '@/services/api';

/* ---------- pure helpers, exported so they can be pinned ---------- */

/** How the cue reads under the kicker. Never any authored scene text. */
export function cueLine(entry: JournalEntryView | null | undefined): string {
  if (!entry) return '';
  const who = entry.cue?.character_name?.trim();
  const where = entry.cue?.location_name?.trim();
  const days = entry.cue?.days_ago;
  const when = days == null ? null : days <= 1 ? 'hier' : `il y a ${days} jours`;
  return [when, who ? `avec ${who}` : null, where ? `à ${where}` : null]
    .filter(Boolean)
    .join(' · ');
}

/** The content-recall sentence. Never a score out of ten, never a grade. */
export function recallLine(entry: JournalEntryView | null | undefined): string | null {
  const recall = entry?.content_recall;
  if (!recall) return null;
  if (recall.status !== 'scored') {
    return 'Cette scène n’a rien de noté à retrouver : rien à vérifier ici.';
  }
  const found = recall.matched?.length || 0;
  const total = recall.facts_total || 0;
  if (total === 0) return null;
  if (found === total) return `Vous avez retrouvé tout ce que la scène avait retenu (${found}/${total}).`;
  if (found === 0) return `Rien de ce que la scène avait retenu n’apparaît (0/${total}).`;
  return `Vous avez retrouvé ${found} élément(s) sur ${total}.`;
}

/** The French verdict line for the writing itself. */
export function correctionLine(entry: JournalEntryView | null | undefined): string {
  const correction = entry?.correction;
  if (!correction || correction.assessment_status !== 'checked') {
    return 'La correction n’a pas pu être faite. Votre texte est gardé tel quel.';
  }
  if (!correction.errata?.length) return 'Rien à corriger dans ce texte.';
  if (correction.errata.length === 1) return 'Une chose à revoir.';
  return `${correction.errata.length} choses à revoir.`;
}

export function wordCount(text: string): number {
  return String(text || '').trim().split(/\s+/).filter(Boolean).length;
}

/* ---------- the tab ---------- */

export default function JournalTab() {
  const [state, setState] = useState<JournalEnvelope | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [draft, setDraft] = useState('');
  const [followDraft, setFollowDraft] = useState('');
  const [pending, setPending] = useState<'write' | 'skip' | 'followup' | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    return api
      .getJournalState()
      .then((payload) => {
        setState(payload);
        setFailed(false);
      })
      .catch(() => {
        setState(null);
        setFailed(true);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const entry = state?.entry ?? null;
  const followup = state?.followup ?? null;
  const minWords = state?.min_entry_words ?? 8;
  const written = Boolean(entry?.entry_text);

  const submit = useCallback(async () => {
    if (!entry) return;
    setPending('write');
    setError(null);
    try {
      const next = await api.writeJournalEntry(entry.id, draft);
      setState(next);
      setDraft('');
      setShowAll(false);
    } catch {
      setError('L’entrée n’a pas pu être envoyée. Réessayez.');
    } finally {
      setPending(null);
    }
  }, [draft, entry]);

  const skip = useCallback(async () => {
    if (!entry) return;
    setPending('skip');
    setError(null);
    try {
      setState(await api.skipJournalEntry(entry.id));
    } catch {
      setError('Impossible pour l’instant. Réessayez.');
    } finally {
      setPending(null);
    }
  }, [entry]);

  const answerFollowup = useCallback(async () => {
    if (!followup) return;
    setPending('followup');
    setError(null);
    try {
      setState(await api.answerJournalFollowup(followup.entry_id, followDraft));
      setFollowDraft('');
    } catch {
      setError('Impossible pour l’instant. Réessayez.');
    } finally {
      setPending(null);
    }
  }, [followDraft, followup]);

  if (loading) {
    return (
      <div className="jn-wrap">
        <Skeleton height={120} />
        <Skeleton height={180} />
        <JournalStyles />
      </div>
    );
  }

  if (failed) {
    return (
      <div className="jn-wrap">
        <StateBlock
          tone="error"
          title="Le journal n’a pas pu être ouvert"
          body="La connexion a échoué. Rien n’est perdu."
          action={{ label: 'Réessayer', onSelect: () => void load(), tone: 'secondary' }}
        />
        <JournalStyles />
      </div>
    );
  }

  return (
    <div className="jn-wrap">
      {error && (
        <Notice tone="alert" live="alert" shape="action">
          {error}
        </Notice>
      )}

      {/* ---- the +7-day line, above the day's entry: it is one question ---- */}
      {followup && !followup.answered && (
        <Surface as="section" tone="paper" shape="card" className="jn-card">
          <p className="av2-label">Une semaine plus tard</p>
          <p className="jn-ask" lang="fr">
            {followup.prompt_fr}
          </p>
          {textAnswerField({
            label: 'Votre réponse, en une phrase',
            value: followDraft,
            placeholder: 'Une phrase suffit.',
            rows: 2,
            disabled: pending === 'followup',
            onChange: setFollowDraft,
          })}
          <Action
            tone="secondary"
            inline
            pending={pending === 'followup'}
            pendingLabel="Envoi…"
            disabled={!followDraft.trim()}
            onClick={() => void answerFollowup()}
          >
            Répondre
          </Action>
        </Surface>
      )}

      {!entry && (
        <StateBlock
          tone="empty"
          title="Rien à raconter aujourd’hui"
          body="Le journal s’ouvre le lendemain d’une scène. Revenez demain."
        />
      )}

      {entry && entry.status === 'skipped' && (
        <StateBlock
          tone="empty"
          title="Entrée passée"
          body="Cette scène ne sera plus proposée. La prochaine arrivera demain."
        />
      )}

      {/* ---- writing: the cue only, never the scene ---- */}
      {entry && !written && entry.status !== 'skipped' && (
        <Surface as="section" tone="paper" shape="card" className="jn-card">
          <p className="av2-label">{cueLine(entry) || 'La scène d’hier'}</p>
          <h2 className="jn-title">De mémoire</h2>
          <p className="jn-ask" lang="fr">
            {entry.prompt_fr}
          </p>
          <p className="jn-hint">
            La scène reste fermée jusqu’à votre envoi : c’est le but.
          </p>
          {textAnswerField({
            label: 'Votre entrée',
            value: draft,
            placeholder: 'Deux à quatre phrases…',
            rows: 5,
            disabled: pending === 'write',
            onChange: setDraft,
          })}
          <p className="jn-count" aria-live="polite">
            {wordCount(draft)} mot(s) · {minWords} au minimum
          </p>
          <div className="jn-actions">
            <Action
              tone="primary"
              pending={pending === 'write'}
              pendingLabel="Correction en cours…"
              disabled={wordCount(draft) < minWords}
              onClick={() => void submit()}
            >
              Envoyer et relire la scène
            </Action>
            <Action
              tone="quiet"
              inline
              pending={pending === 'skip'}
              pendingLabel="…"
              onClick={() => void skip()}
            >
              Passer cette scène
            </Action>
          </div>
        </Surface>
      )}

      {/* ---- after: the learner's own text, then the two verdicts ---- */}
      {entry && written && (
        <>
          <Surface as="section" tone="paper" shape="card" className="jn-card">
            <p className="av2-label">{cueLine(entry) || 'Votre entrée'}</p>
            <p className="jn-entry" lang="fr">
              {entry.entry_text}
            </p>
          </Surface>

          {entry.reaction_fr && (
            <Surface as="section" tone="outline" shape="card" className="jn-card jn-card--react">
              <ShapeToken kind="story" size="lg" />
              <p className="jn-react" lang="fr">
                {entry.reaction_fr}
              </p>
            </Surface>
          )}

          <Surface as="section" tone="paper" shape="card" className="jn-card">
            <p className="av2-label">Le français</p>
            {entry.correction?.assessment_status === 'unavailable' ? (
              <Notice tone="quiet" live="status">
                {correctionLine(entry)}
              </Notice>
            ) : (
              <>
                <p className="jn-verdict">{correctionLine(entry)}</p>
                {entry.correction?.foreground && (
                  <Correction
                    label={entry.correction.foreground.label}
                    spanFr={entry.correction.foreground.span_fr}
                    correctedFr={entry.correction.foreground.corrected_fr}
                    noteNative={entry.correction.foreground.note_native}
                  />
                )}
                {(entry.correction?.errata?.length || 0) > 1 && (
                  <>
                    <Action
                      tone="quiet"
                      inline
                      aria-expanded={showAll}
                      onClick={() => setShowAll((value) => !value)}
                    >
                      {showAll ? 'Masquer le détail' : 'Tout voir'}
                    </Action>
                    {showAll && (
                      <ul className="jn-list">
                        {(entry.correction?.errata || []).map(
                          (item: JournalCorrectionItem, index: number) => (
                            <li key={`${item.span_fr}-${index}`}>
                              <Correction
                                label={item.label}
                                spanFr={item.span_fr}
                                correctedFr={item.corrected_fr}
                                noteNative={item.note_native}
                              />
                            </li>
                          ),
                        )}
                      </ul>
                    )}
                  </>
                )}
                {entry.errata_recorded > 0 && (
                  <p className="jn-hint">
                    {entry.errata_recorded === 1
                      ? 'Une faute est notée au Relevé et reviendra dans une scène.'
                      : `${entry.errata_recorded} fautes sont notées au Relevé et reviendront dans une scène.`}
                  </p>
                )}
              </>
            )}
          </Surface>

          <Surface as="section" tone="paper" shape="card" className="jn-card">
            <p className="av2-label">Ce dont vous vous souvenez</p>
            <p className="jn-verdict">{recallLine(entry) || 'Rien à vérifier ici.'}</p>
            {(entry.content_recall?.missed?.length || 0) > 0 && (
              <ul className="jn-list jn-list--facts">
                {(entry.content_recall?.missed || []).map((fact, index) => (
                  <li key={`${fact.key || index}`} lang="fr">
                    {fact.text_fr}
                  </li>
                ))}
              </ul>
            )}
          </Surface>

          {entry.reveal && (
            <Surface as="section" tone="outline" shape="card" className="jn-card">
              <p className="av2-label">La scène, telle qu’elle était</p>
              {entry.reveal.title_fr && <h2 className="jn-title">{entry.reveal.title_fr}</h2>}
              {entry.reveal.setup_fr && (
                <p className="jn-scene" lang="fr">
                  {entry.reveal.setup_fr}
                </p>
              )}
              {entry.reveal.character_line_fr && (
                <p className="jn-scene jn-scene--line" lang="fr">
                  « {entry.reveal.character_line_fr} »
                </p>
              )}
              {entry.reveal.callback_fr && (
                <p className="jn-scene" lang="fr">
                  {entry.reveal.callback_fr}
                </p>
              )}
            </Surface>
          )}
        </>
      )}
      <JournalStyles />
    </div>
  );
}

/* ============================================================
   Styles — `.av2 .jn-*` only, tokens only, dark from the tokens.
   ============================================================ */
export function JournalStyles() {
  return (
    <style jsx global>{`
      .av2 .jn-wrap { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
      .av2 .jn-card { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
      .av2 .jn-card--react { flex-direction: row; align-items: flex-start; gap: 12px; }
      .av2 .jn-title {
        margin: 0;
        font-family: var(--av2-serif);
        font-style: italic;
        font-weight: 600;
        font-size: var(--av2-t-body-lg);
        line-height: 1.2;
        color: var(--av2-ink);
      }
      .av2 .jn-ask {
        margin: 0;
        font-size: var(--av2-t-body-lg);
        line-height: 1.35;
        color: var(--av2-ink);
        overflow-wrap: anywhere;
      }
      .av2 .jn-hint { margin: 0; font-size: var(--av2-t-meta); line-height: 1.4; color: var(--av2-muted); }
      .av2 .jn-count { margin: 0; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }
      .av2 .jn-verdict { margin: 0; font-size: var(--av2-t-body); line-height: 1.4; color: var(--av2-ink); }
      .av2 .jn-entry {
        margin: 0;
        font-family: var(--av2-serif);
        font-size: var(--av2-t-body-lg);
        line-height: 1.5;
        color: var(--av2-ink);
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      .av2 .jn-react { margin: 0; flex: 1 1 auto; min-width: 0; font-size: var(--av2-t-body); line-height: 1.4; color: var(--av2-ink); overflow-wrap: anywhere; }
      .av2 .jn-scene { margin: 0; font-size: var(--av2-t-body); line-height: 1.5; color: var(--av2-ink-2); overflow-wrap: anywhere; }
      .av2 .jn-scene--line { font-family: var(--av2-serif); font-style: italic; color: var(--av2-ink); }
      .av2 .jn-actions { display: flex; flex-direction: column; align-items: stretch; gap: 8px; }
      .av2 .jn-list { display: flex; flex-direction: column; gap: 10px; margin: 0; padding: 0; list-style: none; }
      .av2 .jn-list--facts li {
        padding-left: 12px;
        border-left: 3px solid var(--av2-line);
        font-size: var(--av2-t-body);
        line-height: 1.4;
        color: var(--av2-ink-2);
        overflow-wrap: anywhere;
      }
    `}</style>
  );
}
