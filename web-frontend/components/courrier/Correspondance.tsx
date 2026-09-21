/* Atelier V2 — LE COURRIER · la correspondance (WP-65, surface for WP-64).
 *
 * WP-64 made a letter a fact in the story: a correspondent with an identity and
 * a mood, letters that come in chains, a soft deadline, a lapse that cools
 * somebody rather than failing the learner, and a debrief with nothing in it
 * that was not counted. None of that had a surface. This file is the surface.
 *
 * Presentational only, and deliberately free of `services/api`: every component
 * takes the shape the payload already has, so the node suite can render them
 * without pulling axios into a test process, and so no card here can invent a
 * field the server did not send. The fetching lives in `courrier-waiting.tsx`.
 *
 * Three rules it keeps, all from `docs/design-overhaul-2026-08-31.md`:
 *
 *   1. one primary press per screen — nothing here is a press. The correspondent
 *      card, the thread and the debrief are surfaces to read; the day's press is
 *      the reply in the composer, and the letter waiting on La Une is a row;
 *   2. honest numbers only — every figure comes from `recap.measured`, which the
 *      corrector counted. The old `readiness.overall` (`55 + words * 0.45`) is
 *      gone and nothing here replaces it with another formula;
 *   3. a deadline is said softly and a lapse is never a fail screen: «Répondez
 *      avant jeudi, si vous pouvez.», and a letter left unanswered says who
 *      noticed, not what the learner lost.
 *
 * Every rule below is written `.av2 .cr-…` (0,2,0) so a legacy page reset such
 * as `.atelier-page button { background: transparent }` (0,1,1) cannot reach it.
 */

import React from 'react';
import Link from 'next/link';

import { ArrowRightIcon, Chip, Portrait, ShapeToken } from '@/components/atelier-v2/ui';

/* ---------- the shapes WP-64 serialises (`_courrier_fields`) ----------
   Structural, not imported: a component that only reads `name` should not make
   the whole mission type a dependency of the design system. */

export type CrLetterOutcome = 'kept' | 'partial' | 'missed' | 'ignored' | string;
export type CrLetterOrigin = 'courrier' | 'chain' | 'story_born' | string;

export type CrCorrespondentView = {
  id?: string | null;
  name?: string | null;
  role?: string | null;
  initials?: string | null;
  /** WP-61's feeling, already written as one French line by the server. */
  mood_line?: string | null;
};

export type CrChainView = {
  id?: string | null;
  index?: number | null;
  total?: number | null;
};

export type CrThreadLetter = {
  mission_id?: string | null;
  title?: string | null;
  summary_fr?: string | null;
  outcome?: CrLetterOutcome | null;
  stakes_level?: number | null;
  chain_index?: number | null;
  at?: string | null;
};

export type CrMeasured = {
  objectives_met?: number;
  objectives_total?: number;
  objectives_met_all?: number;
  objectives_all?: number;
  repairs?: number;
  phrases_saved?: number;
  replies?: number;
  words_written?: number;
};

/* ---------- the French for an outcome ----------
   Four words for four states. `kept` is the only one that celebrates; the other
   three describe, because a letter half answered is a thing that happened, not
   a grade. `ignored` is what a lapse leaves behind and is never «échec». */

const OUTCOME_COPY: Record<string, { label: string; mark: 'done' | 'action' | 'story' }> = {
  kept: { label: 'Parole tenue', mark: 'done' },
  partial: { label: 'En partie', mark: 'story' },
  missed: { label: 'Manqué cette fois', mark: 'action' },
  ignored: { label: 'Restée sans réponse', mark: 'story' },
};

export function crOutcomeLabel(outcome?: CrLetterOutcome | null): string | null {
  const copy = OUTCOME_COPY[String(outcome || '')];
  return copy ? copy.label : null;
}

export function crOutcomeMark(outcome?: CrLetterOutcome | null): 'done' | 'action' | 'story' {
  return (OUTCOME_COPY[String(outcome || '')] || OUTCOME_COPY.partial).mark;
}

/** One sentence under the seal, saying what the word above it means. */
export function crOutcomeSentence(outcome: CrLetterOutcome | null | undefined, name?: string | null): string | null {
  const who = String(name || '').trim();
  switch (String(outcome || '')) {
    case 'kept':
      return who
        ? `Vous avez fait ce que ${who} demandait.`
        : 'Vous avez fait ce que la lettre demandait.';
    case 'partial':
      return 'Une partie de ce qu’on vous demandait est passée ; le reste attend.';
    case 'missed':
      return 'Ce qu’on vous demandait n’est pas passé cette fois.';
    case 'ignored':
      return 'La lettre est restée sans réponse.';
    default:
      return null;
  }
}

/* ---------- «2ᵉ lettre sur 3» ----------
   French ordinals, written out rather than computed with a library: `1ʳᵉ`
   because «lettre» is feminine, `2ᵉ` for everything after. A chain of one is
   not a chain and prints nothing. */

const ORDINALS = ['', '1ʳᵉ', '2ᵉ', '3ᵉ', '4ᵉ', '5ᵉ', '6ᵉ'];

export function crChainLabel(chain?: CrChainView | null): string | null {
  const total = Number(chain?.total || 0);
  const index = Number(chain?.index || 0);
  if (!chain || total <= 1 || index < 1) return null;
  const ordinal = ORDINALS[index] || `${index}ᵉ`;
  return `${ordinal} lettre sur ${total}`;
}

/* ---------- the soft deadline ----------
   Never a countdown, never a colour: one sentence that ends in «si vous pouvez».
   A deadline already past prints nothing — the letter has lapsed and the lapse
   notice says so in its own words. */

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

export function crExpiryLine(expiresAt?: string | null, now: Date = new Date()): string | null {
  if (!expiresAt) return null;
  const due = new Date(expiresAt);
  if (Number.isNaN(due.getTime())) return null;
  const days = Math.round((startOfDay(due) - startOfDay(now)) / 86400000);
  if (days < 0) return null;
  if (days === 0) return 'Répondez aujourd’hui, si vous pouvez.';
  if (days === 1) return 'Répondez d’ici demain, si vous pouvez.';
  if (days <= 6) {
    const weekday = new Intl.DateTimeFormat('fr-FR', { weekday: 'long' }).format(due);
    return `Répondez avant ${weekday}, si vous pouvez.`;
  }
  const date = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long' }).format(due);
  return `Répondez avant le ${date}, si vous pouvez.`;
}

/** «12 sept.» — the date a past letter was filed, or nothing at all. */
export function crShortDate(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' }).format(date);
}

/* ---------- the measured rows ----------
   `recap.measured` (WP-64) and nothing else. A row whose number is zero still
   prints when it is an objective count — «0 objectif sur 2 tenu» is a fact the
   learner is owed — while an empty repair or word count simply has no row. */

export function crMeasuredRows(measured?: CrMeasured | null): { label: string; value: string }[] {
  if (!measured) return [];
  const rows: { label: string; value: string }[] = [];
  const total = Number(measured.objectives_total || 0);
  if (total > 0) {
    const met = Number(measured.objectives_met || 0);
    rows.push({
      label: 'Objectifs tenus',
      value: `${met} sur ${total}`,
    });
  }
  const repairs = Number(measured.repairs || 0);
  if (repairs > 0) {
    rows.push({ label: 'Réparations', value: `${repairs} enregistrée${repairs === 1 ? '' : 's'}` });
  }
  const saved = Number(measured.phrases_saved || 0);
  if (saved > 0) {
    rows.push({ label: 'Phrases mises de côté', value: `${saved}` });
  }
  const words = Number(measured.words_written || 0);
  if (words > 0) {
    rows.push({ label: 'Mots écrits', value: `${words}` });
  }
  return rows;
}

/* ---------- the correspondent ----------
   Who is writing, how they feel, which letter of the affair this is, and by
   when. Above the thread of letters already exchanged with the same person. */

export function CrCorrespondent({
  correspondent,
  chain,
  expiresAt,
  history = [],
  lapsed = false,
  showMood = true,
  now,
}: {
  correspondent?: CrCorrespondentView | null;
  chain?: CrChainView | null;
  expiresAt?: string | null;
  history?: CrThreadLetter[];
  lapsed?: boolean;
  /** False once the letter is answered: the debrief below owns the mood line
   *  there, and says when it was measured. Two copies would read as two
   *  different moments. */
  showMood?: boolean;
  /** Test seam only; the screen always means "today". */
  now?: Date;
}) {
  const name = String(correspondent?.name || '').trim();
  if (!name) return null;
  const role = String(correspondent?.role || '').trim();
  const mood = showMood ? String(correspondent?.mood_line || '').trim() : '';
  const chainLabel = crChainLabel(chain);
  const expiry = lapsed ? null : crExpiryLine(expiresAt, now);
  const past = (history || []).filter((letter) => String(letter?.summary_fr || letter?.title || '').trim());
  return (
    <section className="cr-corr" aria-label={`Votre correspondance avec ${name}`}>
      <CourrierCorrespondanceStyles />
      <p className="cr-corr-head">
        <Portrait name={name} size="sm" />
        <span className="cr-corr-who">
          <b lang="fr">{name}</b>
          {role && <span lang="fr"> · {role}</span>}
        </span>
        {chainLabel && (
          <Chip tone="quiet" className="cr-corr-chain">
            <span lang="fr">{chainLabel}</span>
          </Chip>
        )}
      </p>
      {mood && (
        <p className="cr-corr-mood" lang="fr">
          <ShapeToken kind="story" size="sm" />
          <span>{mood}</span>
        </p>
      )}
      {expiry && (
        <p className="cr-corr-when" lang="fr">
          {expiry}
        </p>
      )}
      {past.length > 0 && (
        <div className="cr-corr-thread">
          <p className="cr-corr-k">
            {past.length === 1 ? 'Votre lettre précédente' : `Vos ${past.length} lettres précédentes`}
          </p>
          <ol>
            {past.map((letter, index) => {
              const outcome = crOutcomeLabel(letter.outcome);
              const date = crShortDate(letter.at);
              return (
                <li key={String(letter.mission_id || index)}>
                  <span className="cr-corr-past" lang="fr">
                    {String(letter.summary_fr || letter.title || '').trim()}
                  </span>
                  <span className="cr-corr-meta">
                    {date && <span>{date}</span>}
                    {outcome && (
                      <span className="cr-corr-verdict">
                        <ShapeToken kind={crOutcomeMark(letter.outcome)} size="sm" />
                        {outcome}
                      </span>
                    )}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}

/* ---------- a letter that lapsed ----------
   WP-64 marks an overdue chain letter `lapsed` and cools the correspondent by
   one; the next letter from that person mentions it once and then it is water
   under the bridge. So this is not a failure screen and carries no retry: it
   says what happened, who noticed, and that they will write again. */

export function CrLapsedNotice({ name }: { name?: string | null }) {
  const who = String(name || '').trim();
  return (
    <section className="cr-lapsed" role="status" aria-label="Lettre sans réponse">
      <CourrierCorrespondanceStyles />
      <p className="cr-lapsed-k">
        <ShapeToken kind="story" size="sm" />
        <span>Restée sans réponse</span>
      </p>
      <p className="cr-lapsed-body" lang="fr">
        {who
          ? `Le délai est passé et ${who} n’a rien reçu. Ce n’est pas grave : ${who} en dira un mot dans sa prochaine lettre.`
          : 'Le délai est passé. Ce n’est pas grave : votre correspondant en dira un mot dans sa prochaine lettre.'}
      </p>
    </section>
  );
}

/* ---------- the honest debrief ----------
   What replaced `recap.readiness`. Everything printed here was counted:
   the outcome comes from the corrector's per-objective `met` flags, the rows
   from `recap.measured`, and the last block from the event the letter actually
   wrote into the story (`recap.story_event.summary_fr`).

   `moodLine` is labelled «à la réception de votre lettre», not «maintenant»,
   because the payload carries the mood the letter was *written* with: WP-64
   stamps `prompt_payload.correspondence` at creation and the writeback that
   moves the mood runs after. Printing it as the character's current opinion
   would be exactly the invented number this package removed. */

export function CrDebrief({
  outcome,
  measured,
  correspondent,
  storySummary,
  moodAfter,
}: {
  outcome?: CrLetterOutcome | null;
  measured?: CrMeasured | null;
  correspondent?: CrCorrespondentView | null;
  /** `recap.story_event.summary_fr` — the fact this letter left in the story. */
  storySummary?: string | null;
  /** `recap.correspondent_mood_after` — the mood once the letter has landed. */
  moodAfter?: string | null;
}) {
  const label = crOutcomeLabel(outcome);
  const rows = crMeasuredRows(measured);
  const name = String(correspondent?.name || '').trim();
  const after = String(moodAfter || '').trim();
  const mood = after || String(correspondent?.mood_line || '').trim();
  const story = String(storySummary || '').trim();
  if (!label && rows.length === 0 && !story && !mood) return null;
  const sentence = crOutcomeSentence(outcome, name);
  return (
    <section className="cr-debrief" aria-label="Ce que cette lettre a donné">
      <CourrierCorrespondanceStyles />
      {label && (
        <p className="cr-debrief-verdict">
          <ShapeToken kind={crOutcomeMark(outcome)} size="sm" />
          <b lang="fr">{label}</b>
        </p>
      )}
      {sentence && <p className="cr-debrief-sub" lang="fr">{sentence}</p>}
      {rows.length > 0 && (
        <dl className="cr-debrief-rows">
          {rows.map((row) => (
            <div key={row.label}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {(story || mood) && (
        <div className="cr-debrief-story">
          {story && (
            <>
              <p className="cr-debrief-k">
                {name ? `Ce que ${name} retient` : 'Ce que votre correspondant retient'}
              </p>
              <p className="cr-debrief-line" lang="fr">{story}</p>
            </>
          )}
          {mood && (
            <p className="cr-debrief-mood" lang="fr">
              <span className="cr-debrief-when">{after ? 'Depuis votre lettre — ' : 'À la réception de votre lettre — '}</span>
              {mood}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

/* ---------- «Une lettre vous attend» ----------
   The row that carries the Courrier onto a screen that is not the Courrier:
   La Une's second action and the Feuilleton's margin. A row, never a press —
   the single-CTA rule means the day already has its one red press elsewhere,
   and the same `.av2-row` the other quiet Home entries use, so it cannot drift
   from them. */

export function CrLetterRow({
  name,
  hint,
  href = '/missions',
  label = 'Une lettre vous attend',
}: {
  name?: string | null;
  hint?: string | null;
  href?: string;
  label?: string;
}) {
  const who = String(name || '').trim();
  const line = String(hint || '').trim() || (who ? `${who} attend votre réponse.` : 'Le Courrier vous attend.');
  return (
    <Link className="av2-row cr-letter-row" href={href} aria-label={`${label} — ${line}`}>
      <CourrierCorrespondanceStyles />
      {who && <Portrait name={who} size="sm" />}
      <span className="av2-row__main">
        <span className="av2-label">{label}</span>
        <span className="av2-label cr-letter-hint" lang="fr">{line}</span>
      </span>
      <ArrowRightIcon size={18} />
    </Link>
  );
}

/** The hint under «Une lettre vous attend», built from what the letter is.
 *  A chain says which instalment; a story-born letter says it comes from the
 *  feuilleton; anything else says who is waiting. Never all three at once. */
export function crLetterHint({
  name,
  chain,
  origin,
  expiresAt,
  now,
}: {
  name?: string | null;
  chain?: CrChainView | null;
  origin?: CrLetterOrigin | null;
  expiresAt?: string | null;
  now?: Date;
}): string {
  const who = String(name || '').trim();
  const clauses: string[] = [];
  const chainLabel = crChainLabel(chain);
  if (chainLabel) clauses.push(who ? `${chainLabel}, de ${who}` : chainLabel);
  else if (String(origin || '') === 'story_born') {
    clauses.push(who ? `${who} vous écrit après l’épisode` : 'Quelqu’un vous écrit après l’épisode');
  } else if (who) clauses.push(`${who} attend votre réponse`);
  const expiry = crExpiryLine(expiresAt, now);
  if (expiry) clauses.push(expiry.replace(/^Répondez/, 'répondez').replace(/\.$/, ''));
  if (!clauses.length) return 'Le Courrier vous attend.';
  return `${clauses.join(' · ')}.`;
}

/* ============================================================
   Styles — `.av2 .cr-…` (0,2,0), `--av2-*` tokens only, sizes in rem, so dark
   mode comes free and no legacy element reset can outrank them. Mounted by the
   components themselves: styled-jsx dedupes one global block by content, so a
   screen that shows three of these ships one copy of the CSS and neither the
   Feuilleton nor La Une has to remember to import a stylesheet.
   ============================================================ */
export function CourrierCorrespondanceStyles() {
  return (
    <style jsx global>{`
      /* the correspondent */
      .av2 .cr-corr {
        display: flex; flex-direction: column; gap: 8px;
        padding: 14px 16px; border-radius: var(--av2-r-tile); background: var(--av2-card);
      }
      .av2 .cr-corr-head { margin: 0; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
      .av2 .cr-corr-who { flex: 1 1 auto; min-width: 0; font-size: var(--av2-t-label); color: var(--av2-muted); }
      .av2 .cr-corr-who b { font-weight: 700; color: var(--av2-ink); }
      .av2 .cr-corr-chain { flex: none; }
      .av2 .cr-corr-mood {
        margin: 0; display: flex; align-items: flex-start; gap: 8px;
        font-family: var(--av2-serif); font-style: italic;
        font-size: var(--av2-t-body); line-height: 1.4; color: var(--av2-blue);
      }
      .av2 .cr-corr-mood .av2-shape { margin-top: 5px; flex: none; }
      .av2 .cr-corr-when { margin: 0; font-size: var(--av2-t-label); line-height: 1.4; color: var(--av2-ink-2); }
      .av2 .cr-corr-thread { display: flex; flex-direction: column; gap: 6px; padding-top: 2px; }
      .av2 .cr-corr-k { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
      .av2 .cr-corr-thread ol { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
      .av2 .cr-corr-thread li {
        display: flex; flex-direction: column; gap: 2px;
        padding: 8px 12px; border-radius: var(--av2-r-card); background: var(--av2-paper);
      }
      .av2 .cr-corr-past { font-size: var(--av2-t-label); line-height: 1.4; color: var(--av2-ink); }
      .av2 .cr-corr-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 10px; font-size: var(--av2-t-meta); color: var(--av2-muted); }
      .av2 .cr-corr-verdict { display: inline-flex; align-items: center; gap: 6px; }

      /* a lapsed letter — a fact, not a failure */
      .av2 .cr-lapsed {
        display: flex; flex-direction: column; gap: 6px;
        padding: 14px 16px; border-radius: var(--av2-r-tile); background: var(--av2-card);
      }
      .av2 .cr-lapsed-k { margin: 0; display: flex; align-items: center; gap: 8px; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
      .av2 .cr-lapsed-body { margin: 0; font-size: var(--av2-t-body); line-height: 1.45; color: var(--av2-ink-2); }

      /* the honest debrief */
      .av2 .cr-debrief {
        display: flex; flex-direction: column; gap: 8px;
        padding: 14px 16px; border-radius: var(--av2-r-tile); background: var(--av2-card);
      }
      .av2 .cr-debrief-verdict { margin: 0; display: flex; align-items: center; gap: 8px; font-size: var(--av2-t-action); color: var(--av2-ink); }
      .av2 .cr-debrief-verdict b { font-weight: 700; }
      .av2 .cr-debrief-sub { margin: 0; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2); }
      .av2 .cr-debrief-rows { margin: 0; display: flex; flex-direction: column; gap: 2px; }
      .av2 .cr-debrief-rows > div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; min-height: 34px; font-size: var(--av2-t-label); }
      .av2 .cr-debrief-rows dt { color: var(--av2-muted); }
      .av2 .cr-debrief-rows dd { margin: 0; font-weight: 700; color: var(--av2-ink); text-align: right; font-variant-numeric: tabular-nums; }
      .av2 .cr-debrief-story { display: flex; flex-direction: column; gap: 4px; padding-top: 2px; }
      .av2 .cr-debrief-k { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
      .av2 .cr-debrief-line { margin: 0; font-size: var(--av2-t-body); line-height: 1.45; color: var(--av2-ink); }
      .av2 .cr-debrief-mood {
        margin: 0; font-family: var(--av2-serif); font-style: italic;
        font-size: var(--av2-t-body); line-height: 1.4; color: var(--av2-blue);
      }
      .av2 .cr-debrief-when { font-family: var(--av2-sans); font-style: normal; font-size: var(--av2-t-meta); color: var(--av2-muted); }

      /* the waiting letter, as a row */
      .av2 .cr-letter-row { text-decoration: none; }
      .av2 .cr-letter-row .av2-portrait { flex: none; }
      .av2 .cr-letter-hint { display: block; font-weight: 400; }
    `}</style>
  );
}
