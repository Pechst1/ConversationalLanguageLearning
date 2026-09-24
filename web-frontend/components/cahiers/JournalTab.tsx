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
 * Chrome: av2 tokens only, pill sentence-case actions, dark mode from the
 * tokens. Styles are `.av2 .jn-*` (0,2,0) like the rest of the Cahier.
 *
 * WP-82: the screen's own words (instructions, verdicts, states, buttons) come
 * from `cahier-copy.ts` in the chrome language of the surrounding
 * `AtelierV2Root` — the learner's language up to A2, French from B1. The
 * prompt, the reaction, the scene reveal, the corrections and the learner's
 * own paragraph are content and stay French.
 */
import React, { useCallback, useEffect, useState } from 'react';

import {
  Action,
  Correction,
  Notice,
  ScreenFoot,
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

import { cahierCopy, fill, useCahierCopy, type CahierCopy } from './cahier-copy';

type JournalCopy = CahierCopy['journal'];
const FRENCH_JOURNAL: JournalCopy = cahierCopy('fr').journal;

/* ---------- pure helpers, exported so they can be pinned ---------- */

/** How the story label reads above the headline. Never any authored scene text.
 *
 *  WP-45 puts it in the artboard's order — «Hier · Le Mistral · avec Augustin»:
 *  when, where, who. The place is a bare name rather than «à …» because it is a
 *  label, not a sentence. */
export function cueLine(entry: JournalEntryView | null | undefined, t: JournalCopy = FRENCH_JOURNAL): string {
  if (!entry) return '';
  const who = entry.cue?.character_name?.trim();
  const where = entry.cue?.location_name?.trim();
  const days = entry.cue?.days_ago;
  const when = days == null ? null : days <= 1 ? t.yesterday : fill(t.days_ago, { n: days });
  return [when, where || null, who ? fill(t.with, { name: who }) : null].filter(Boolean).join(' · ');
}

/** What the field says before the learner writes, in the artboard's shape
 *  («Hier, Augustin…»). Falls back to the day alone when the server sent no
 *  character: an invented name would be scene text. */
export function entryPlaceholder(entry: JournalEntryView | null | undefined): string {
  const who = entry?.cue?.character_name?.trim();
  return who ? `Hier, ${who}…` : 'Hier, …';
}

/** The content-recall sentence. Never a score out of ten, never a grade. */
export function recallLine(entry: JournalEntryView | null | undefined, t: JournalCopy = FRENCH_JOURNAL): string | null {
  const recall = entry?.content_recall;
  if (!recall) return null;
  if (recall.status !== 'scored') {
    return t.recall_unscored;
  }
  const found = recall.matched?.length || 0;
  const total = recall.facts_total || 0;
  if (total === 0) return null;
  if (found === total) return fill(t.recall_all, { found, total });
  if (found === 0) return fill(t.recall_none, { total });
  return fill(t.recall_some, { found, total });
}

/** The verdict line for the writing itself, in the chrome language. */
export function correctionLine(entry: JournalEntryView | null | undefined, t: JournalCopy = FRENCH_JOURNAL): string {
  const correction = entry?.correction;
  if (!correction || correction.assessment_status !== 'checked') {
    return t.correction_unavailable;
  }
  if (!correction.errata?.length) return t.correction_clean;
  if (correction.errata.length === 1) return t.correction_one;
  return fill(t.correction_many, { n: correction.errata.length });
}

export function wordCount(text: string): number {
  return String(text || '').trim().split(/\s+/).filter(Boolean).length;
}

/* ---------- the tab ---------- */

export default function JournalTab() {
  const copy = useCahierCopy();
  const t = copy.journal;
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
      setError(t.send_failed);
    } finally {
      setPending(null);
    }
  }, [draft, entry, t]);

  const skip = useCallback(async () => {
    if (!entry) return;
    setPending('skip');
    setError(null);
    try {
      setState(await api.skipJournalEntry(entry.id));
    } catch {
      setError(t.busy_failed);
    } finally {
      setPending(null);
    }
  }, [entry, t]);

  const answerFollowup = useCallback(async () => {
    if (!followup) return;
    setPending('followup');
    setError(null);
    try {
      setState(await api.answerJournalFollowup(followup.entry_id, followDraft));
      setFollowDraft('');
    } catch {
      setError(t.busy_failed);
    } finally {
      setPending(null);
    }
  }, [followDraft, followup, t]);

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
          title={t.load_failed_title}
          body={t.load_failed_body}
          action={{ label: copy.cahier.retry, onSelect: () => void load(), tone: 'secondary' }}
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
          <p className="av2-label">{t.followup_kicker}</p>
          <p className="jn-ask" lang="fr">
            {followup.prompt_fr}
          </p>
          {textAnswerField({
            label: t.followup_label,
            value: followDraft,
            placeholder: t.followup_placeholder,
            rows: 2,
            disabled: pending === 'followup',
            onChange: setFollowDraft,
          })}
          <Action
            tone="secondary"
            inline
            pending={pending === 'followup'}
            pendingLabel={t.sending}
            disabled={!followDraft.trim()}
            onClick={() => void answerFollowup()}
          >
            {t.reply}
          </Action>
        </Surface>
      )}

      {!entry && (
        <StateBlock
          tone="empty"
          title={t.empty_title}
          body={t.empty_body}
        />
      )}

      {entry && entry.status === 'skipped' && (
        <StateBlock
          tone="empty"
          title={t.skipped_title}
          body={t.skipped_body}
        />
      )}

      {/* ---- writing: the cue only, never the scene ---- */}
      {/* WP-45 draws this state on `Journal.dc.html`: a blue story label, the
          one 30px headline, the body, the taller «Hier, en français» field, the
          dashed note about the corrections, and then a screen foot. No card —
          the artboard sets this state straight on the paper, because it is the
          screen rather than one block on it. */}
      {entry && !written && entry.status !== 'skipped' && (
        <>
          <section className="jn-write" aria-label={t.headline}>
            <p className="av2-label av2-label--story">{cueLine(entry, t) || t.cue_fallback}</p>
            <h2 className="av2-headline">{t.headline}</h2>
            <p className="jn-lead" lang="fr">
              {entry.prompt_fr}
            </p>
            <div className="jn-entry-field">
              {textAnswerField({
                label: t.field_label,
                value: draft,
                placeholder: entryPlaceholder(entry),
                rows: 6,
                disabled: pending === 'write',
                onChange: setDraft,
              })}
            </div>
            <Surface tone="outline">
              <p className="jn-hint">{t.hint}</p>
            </Surface>
            <p className="jn-count" aria-live="polite">
              {fill(t.word_count, { n: wordCount(draft), min: minWords })}
            </p>
          </section>
          {/* The screen foot. Last in the flow, so the action is never under the
              phone tab bar (WP-39's CTA finding). */}
          <ScreenFoot className="jn-foot">
            <Action
              tone="primary"
              pending={pending === 'write'}
              pendingLabel={t.correcting}
              disabled={wordCount(draft) < minWords}
              onClick={() => void submit()}
            >
              {t.send}
            </Action>
            {/* A caption, not a control: it says what «Envoyer» does next, and
                there is nothing to press before the entry is sent. The artboard
                underlines it; an underline that opens nothing is a false
                affordance, so it is drawn quiet instead. */}
            <p className="jn-foot__note">{t.foot_note}</p>
            <Action
              tone="quiet"
              pending={pending === 'skip'}
              pendingLabel="…"
              onClick={() => void skip()}
            >
              {t.skip}
            </Action>
          </ScreenFoot>
        </>
      )}

      {/* ---- after: the learner's own text, then the two verdicts ---- */}
      {entry && written && (
        <>
          <Surface as="section" tone="paper" shape="card" className="jn-card">
            <p className="av2-label">{cueLine(entry, t) || t.entry_fallback}</p>
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
            <p className="av2-label">{t.french_label}</p>
            {entry.correction?.assessment_status === 'unavailable' ? (
              <Notice tone="quiet" live="status">
                {correctionLine(entry, t)}
              </Notice>
            ) : (
              <>
                <p className="jn-verdict">{correctionLine(entry, t)}</p>
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
                      {showAll ? t.hide_detail : t.show_all}
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
                      ? t.errata_one
                      : fill(t.errata_many, { n: entry.errata_recorded })}
                  </p>
                )}
              </>
            )}
          </Surface>

          <Surface as="section" tone="paper" shape="card" className="jn-card">
            <p className="av2-label">{t.recall_label}</p>
            <p className="jn-verdict">{recallLine(entry, t) || t.recall_empty}</p>
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
              <p className="av2-label">{t.reveal_label}</p>
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
      /* Canvas note «note-pied»: below 760px the shell draws a fixed four-tab
         bar over the Cahier, so the tab reserves its height and the foot — the
         last thing in this flow — lands above it instead of under it. */
      @media (max-width: 760px) {
        .av2 .jn-wrap { padding-bottom: var(--phone-bottom-nav-space, 0px); }
      }
      /* The writing state, on Journal.dc.html: straight on the paper, 14px
         between the label, the headline, the body, the field and the note. */
      .av2 .jn-write { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
      .av2 .jn-lead {
        margin: 0;
        font-size: var(--av2-t-body); /* design 15px */
        line-height: 1.45;
        color: var(--av2-ink-2);
        overflow-wrap: anywhere;
      }
      /* «Hier, en français» — the artboard draws this one field 150px tall,
         because the entry is the whole point of the screen. Everything else
         about it is the shared av2 field. */
      .av2 .jn-entry-field .av2-field__control { min-height: 150px; }
      /* The screen foot. Same rule as the other companion screens: a hairline,
         the paper ground, 14px and the safe area — but in flow, never fixed.
         The wrapper is the shared ScreenFoot (WP-43); this only stacks its
         children. */
      .av2 .jn-foot {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 4px;
        margin-top: 2px;
      }
      .av2 .jn-foot__note {
        margin: 0;
        min-height: var(--av2-tap);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: var(--av2-t-label);
        font-weight: 600;
        line-height: 1.45;
        color: var(--av2-ink-2);
        text-align: center;
      }
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
