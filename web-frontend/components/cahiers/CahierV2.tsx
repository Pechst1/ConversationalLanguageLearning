/**
 * Le Cahier — Atelier V2 (the design's NOTEBOOK artboard, `data-screen-label="Cahier"`).
 *
 * Read from `docs/design-reference/claude/Atelier App.dc.html`:
 *
 *   * kicker "54 concepts · 12 vus" + the one Garamond-italic headline "Le cahier";
 *   * a segmented pill (`#e8e0cf` = --av2-line, radius 999, 3px padding; the
 *     active tab is an ink face with paper text) — "Règles | Mots";
 *   * a 44px search well (card colour, radius 14, muted placeholder, 2.4-stroke
 *     search glyph);
 *   * a horizontally scrolling row of level chips (active = blue face, paper text);
 *   * concept rows: card colour, radius 16, padding 14/16; a 36px glyph token —
 *     circle for "en cours" (blue), radius-8 square for done (ink) or fragile
 *     (red), a line-coloured circle for "à venir"; 15px/600 title; 12px muted
 *     meta; three 5px bars 34px wide, filled in the row's own colour.
 *
 * The design has no artboard for the concept fiche, Le Relevé or the library,
 * so those are extended from the same primitives (`Surface`, `Action`,
 * `StateBlock`, `ProgressRule`, the shape tokens); the gaps are recorded in
 * the migration report.
 *
 * Every rule below is `.av2 .nb-…` (0,2,0) so it outranks the legacy element
 * resets, and every colour, radius and font is a `--av2-*` token — dark mode
 * comes from the tokens. Used only by the notebook cluster (`pages/notebook`,
 * `pages/grammar`, `components/releve`).
 */
import React from 'react';
import Link from 'next/link';

import { ArrowLeftIcon, Chip } from '@/components/atelier-v2/ui';

export type CahierMode = 'grammar' | 'vocabulary' | 'releve' | 'library';

export const CAHIER_MODE_LABELS: Record<CahierMode, string> = {
  grammar: 'Règles',
  vocabulary: 'Mots',
  releve: 'Relevé',
  library: 'Livres',
};

/* ---------- head: kicker + the one headline + the segmented pill ---------- */
export function CahierHead({
  kicker,
  title = 'Le cahier',
  children,
}: {
  kicker: string;
  title?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="nb-head">
      <div className="nb-head__main">
        <p className="nb-kicker">{kicker}</p>
        <h1 className="av2-headline av2-headline--screen">{title}</h1>
      </div>
      {children}
    </header>
  );
}

/* ---------- the segmented pill ----------
   Tabs are buttons when `onSelect` is given (the /notebook shell keeps the mode
   in state and mirrors it into the query) and links when `hrefFor` is given
   (the direct /grammar and /vocabulary routes). */
export function NotebookModeTabs({
  active,
  library = false,
  onSelect,
  hrefFor,
}: {
  active: CahierMode;
  library?: boolean;
  onSelect?: (mode: CahierMode) => void;
  hrefFor?: (mode: CahierMode) => string;
}) {
  const modes: CahierMode[] = ['grammar', 'vocabulary', 'releve'];
  if (library) modes.push('library');
  return (
    <div className="nb-modes" role="tablist" aria-label="Rubriques du cahier">
      {modes.map((mode) =>
        hrefFor ? (
          <Link
            key={mode}
            role="tab"
            className="nb-modes__tab"
            aria-selected={mode === active}
            aria-current={mode === active ? 'page' : undefined}
            href={hrefFor(mode)}
          >
            {CAHIER_MODE_LABELS[mode]}
          </Link>
        ) : (
          <button
            key={mode}
            type="button"
            role="tab"
            className="nb-modes__tab"
            aria-selected={mode === active}
            onClick={() => onSelect?.(mode)}
          >
            {CAHIER_MODE_LABELS[mode]}
          </button>
        ),
      )}
    </div>
  );
}

/* ---------- search well ---------- */
export function CahierSearch({
  placeholder,
  value,
  onChange,
}: {
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="nb-search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" aria-hidden="true" focusable="false">
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-3.5-3.5" />
      </svg>
      <input
        type="search"
        className="nb-search__input"
        placeholder={placeholder}
        aria-label={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

/* ---------- filter chips (levels, "à revoir") ---------- */
export type CahierChip = { id: string; label: string; count?: number | null };
export function CahierChips({
  chips,
  active,
  onSelect,
  label = 'Filtrer',
}: {
  chips: CahierChip[];
  active: string;
  onSelect: (id: string) => void;
  label?: string;
}) {
  return (
    <div className="nb-chips" role="group" aria-label={label}>
      {chips.map((chip) => (
        <Chip
          key={chip.id}
          tone={chip.id === active ? 'story' : 'plain'}
          aria-pressed={chip.id === active}
          onClick={() => onSelect(chip.id)}
        >
          {chip.label}
          {chip.count != null ? ` · ${chip.count}` : ''}
        </Chip>
      ))}
    </div>
  );
}

/* ---------- the live line under the filters ---------- */
export function CahierLiveLine({
  text,
  clearable = false,
  onClear,
}: {
  text: string;
  clearable?: boolean;
  onClear?: () => void;
}) {
  return (
    <div className="nb-live" aria-live="polite">
      <span>{text}</span>
      {clearable && (
        <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline" onClick={onClear}>
          Effacer les filtres
        </button>
      )}
    </div>
  );
}

/* ---------- concept row ----------
   `tone` decides the glyph shape and the bar colour: blue circle = en cours,
   ink square = maîtrisé, red square = fragile / à revoir, line circle = à venir.
   `bars` is the number of filled bars (0–3), always derived from real mastery
   by the caller — never a decorative fill. */
export type ConceptTone = 'progress' | 'done' | 'fragile' | 'new';
export function ConceptRow({
  title,
  meta,
  glyph,
  tone,
  bars,
  ariaLabel,
  onSelect,
}: {
  title: string;
  meta: string;
  glyph: string;
  tone: ConceptTone;
  bars: number;
  ariaLabel: string;
  onSelect: () => void;
}) {
  return (
    <button type="button" className="nb-row" data-tone={tone} aria-label={ariaLabel} onClick={onSelect}>
      <span className="nb-row__glyph" aria-hidden="true">{glyph}</span>
      <span className="nb-row__main">
        <span className="nb-row__title">{title}</span>
        <span className="nb-row__meta">{meta}</span>
      </span>
      <span className="nb-row__bars" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <i key={index} data-on={index < bars ? 'true' : undefined} />
        ))}
      </span>
    </button>
  );
}

/* ---------- section head (fiche sections, Le Relevé) ---------- */
export function NbSectionHead({ t, n = null }: { t: string; n?: string | null }) {
  return (
    <div className="nb-sechead">
      <h2 className="nb-sechead__t">{t}</h2>
      {n && <span className="nb-sechead__n">{n}</span>}
    </div>
  );
}

/* ---------- back control (fiche → index) ---------- */
export function NbBack({ label, onBack }: { label: string; onBack: () => void }) {
  return (
    <button type="button" className="nb-back" onClick={onBack}>
      <ArrowLeftIcon size={18} /> {label}
    </button>
  );
}

/* ============================================================
   Styles — `.av2 .nb-*` only. Tokens only. Sizes in rem where
   the text-size setting should move them.
   ============================================================ */
export function CahierStyles() {
  return (
    <style jsx global>{`
      body { background: var(--app-paper); }
      .av2.nb-page {
        display: block;
        width: 100%;
        max-width: 720px;
        margin: 0 auto;
        min-height: calc(100vh - var(--phone-bottom-nav-space, 0px));
        padding: 0 0 24px;
      }

      /* ---- head ---- */
      .av2 .nb-head {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        justify-content: space-between;
        gap: 12px;
        padding: calc(18px + env(safe-area-inset-top, 0px)) var(--av2-gutter) 0;
      }
      .av2 .nb-head__main { min-width: 0; flex: 1 1 12rem; }
      .av2 .nb-kicker { margin: 0; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-muted); }
      .av2 .nb-head .av2-headline { margin-top: 3px; }

      .av2 .nb-modes {
        display: inline-flex;
        flex: none;
        max-width: 100%;
        padding: 3px;
        border-radius: var(--av2-r-pill);
        background: var(--av2-line);
        overflow-x: auto;
        scrollbar-width: none;
      }
      .av2 .nb-modes::-webkit-scrollbar { display: none; }
      .av2 .nb-modes__tab {
        flex: 1 1 auto;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: var(--av2-tap);
        padding: 0 0.8125rem;
        border: 0;
        border-radius: var(--av2-r-pill);
        background: transparent;
        color: var(--av2-ink);
        font-family: inherit;
        font-size: var(--av2-t-meta);
        font-weight: 700;
        line-height: 1.2;
        text-decoration: none;
        white-space: nowrap;
        cursor: pointer;
      }
      .av2 .nb-modes__tab[aria-selected='true'] { background: var(--av2-ink); color: var(--av2-on-ink); }

      /* ---- body column ---- */
      .av2 .nb-body { display: flex; flex-direction: column; gap: 12px; padding: 18px var(--av2-gutter) 0; }
      .av2 .nb-embed { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
      .av2 .nb-embed .vocab-page { min-height: auto; padding: 0; background: transparent; }

      /* ---- the bound feuilleton clipping ---- */
      .av2 a.nb-feuille { text-decoration: none; }
      .av2 .nb-feuille__title { display: block; font-size: var(--av2-t-body); font-weight: 600; line-height: 1.25; }

      /* ---- search well ---- */
      .av2 .nb-search {
        display: flex;
        align-items: center;
        gap: 10px;
        min-height: var(--av2-tap);
        padding: 0 14px;
        border-radius: 0.875rem;
        background: var(--av2-card);
        color: var(--av2-muted);
        cursor: text;
      }
      .av2 .nb-search svg { flex: none; }
      .av2 .nb-search__input {
        flex: 1 1 auto;
        min-width: 0;
        min-height: var(--av2-tap);
        padding: 0;
        border: 0 !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        background: transparent;
        color: var(--av2-ink);
        font-family: inherit;
        font-size: var(--av2-t-body-lg);
        line-height: 1.3;
        outline: none;
        -webkit-appearance: none;
        appearance: none;
      }
      .av2 .nb-search__input:focus { box-shadow: none !important; outline: none; }
      .av2 .nb-search__input::placeholder { color: var(--av2-muted); opacity: 1; }
      .av2 .nb-search:focus-within { outline: 3px solid var(--av2-focus); outline-offset: 2px; }

      /* ---- chips ---- */
      .av2 .nb-chips {
        display: flex;
        gap: 6px;
        margin: 0 calc(-1 * var(--av2-gutter));
        padding: 2px var(--av2-gutter);
        overflow-x: auto;
        scrollbar-width: none;
      }
      .av2 .nb-chips::-webkit-scrollbar { display: none; }
      .av2 .nb-chips .av2-chip { flex: none; white-space: nowrap; padding: 4px 0.8125rem; }

      /* ---- live line ---- */
      .av2 .nb-live {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        font-size: var(--av2-t-meta);
        font-weight: 600;
        color: var(--av2-muted);
      }

      /* ---- concept rows ---- */
      .av2 .nb-list { display: flex; flex-direction: column; gap: 8px; }
      .av2 .nb-row {
        display: flex;
        align-items: center;
        gap: 14px;
        width: 100%;
        min-height: var(--av2-tap);
        padding: 14px 16px;
        border: 0;
        border-radius: var(--av2-r-card);
        background: var(--av2-card);
        color: var(--av2-ink);
        font-family: inherit;
        text-align: left;
        text-decoration: none;
        cursor: pointer;
        transition: transform var(--av2-press-dur);
      }
      .av2 .nb-row:active { transform: scale(0.985); }
      .av2 .nb-row__glyph {
        flex: none;
        display: grid;
        place-items: center;
        width: 2.25rem;
        height: 2.25rem;
        border-radius: 8px;
        background: var(--av2-ink);
        color: var(--av2-on-ink);
        font-family: var(--av2-serif);
        font-style: italic;
        font-weight: 600;
        font-size: 1rem;
        line-height: 1;
      }
      .av2 .nb-row[data-tone='progress'] .nb-row__glyph { border-radius: var(--av2-r-pill); background: var(--av2-blue); color: var(--av2-on-blue); }
      .av2 .nb-row[data-tone='fragile'] .nb-row__glyph { background: var(--av2-red); color: var(--av2-on-red); }
      .av2 .nb-row[data-tone='new'] .nb-row__glyph { border-radius: var(--av2-r-pill); background: var(--av2-line); color: var(--av2-muted); }
      .av2 .nb-row__main { flex: 1 1 auto; min-width: 0; }
      .av2 .nb-row__title { display: block; font-size: var(--av2-t-body); font-weight: 600; line-height: 1.2; overflow-wrap: anywhere; }
      .av2 .nb-row__meta { display: block; margin-top: 3px; font-size: var(--av2-t-meta); line-height: 1.3; color: var(--av2-muted); overflow-wrap: anywhere; }
      .av2 .nb-row__bars { flex: none; display: flex; gap: 3px; width: 2.125rem; }
      .av2 .nb-row__bars i { flex: 1 1 0; height: 0.3125rem; border-radius: 3px; background: var(--av2-line); }
      .av2 .nb-row__bars i[data-on='true'] { background: var(--av2-ink); }
      .av2 .nb-row[data-tone='progress'] .nb-row__bars i[data-on='true'] { background: var(--av2-blue); }
      .av2 .nb-row[data-tone='fragile'] .nb-row__bars i[data-on='true'] { background: var(--av2-red); }
      .av2 .nb-row__pct { flex: none; font-family: var(--av2-serif); font-style: italic; font-weight: 600; font-size: var(--av2-t-body-lg); color: var(--av2-ink); }

      /* ---- section heads ---- */
      .av2 .nb-sechead { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
      .av2 .nb-sechead__t { margin: 0; font-family: inherit; font-size: var(--av2-t-body); font-weight: 700; line-height: 1.3; color: var(--av2-ink); }
      .av2 .nb-sechead__n { font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); white-space: nowrap; }

      /* ---- fiche ---- */
      .av2 .nb-back {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        align-self: flex-start;
        min-height: var(--av2-tap);
        padding: 0 8px 0 0;
        border: 0;
        border-radius: 4px;
        background: transparent;
        color: var(--av2-ink-2);
        font-family: inherit;
        font-size: var(--av2-t-label);
        font-weight: 600;
        cursor: pointer;
      }
      .av2 .nb-fiche { display: flex; flex-direction: column; gap: 12px; }
      .av2 .nb-fiche__head { display: flex; flex-direction: column; gap: 8px; }
      .av2 .nb-fiche__tags { display: flex; flex-wrap: wrap; gap: 6px; }
      .av2 .nb-fiche__status { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
      .av2 .nb-fiche__status .av2-progress { flex: 1 1 8rem; }
      .av2 .nb-sec { display: flex; flex-direction: column; gap: 8px; }
      .av2 .nb-rule { margin: 0; font-size: var(--av2-t-rule); color: var(--av2-ink); }
      .av2 .nb-ex { margin: 0; font-size: var(--av2-t-body-lg); color: var(--av2-ink); }
      .av2 .nb-trap { display: flex; align-items: flex-start; gap: 10px; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2); }
      .av2 .nb-trap .av2-shape { margin-top: 4px; }
      .av2 .nb-motif { margin: 0; font-size: var(--av2-t-label); line-height: 1.5; color: var(--av2-ink-2); white-space: pre-wrap; overflow-wrap: anywhere; }
      .av2 .nb-err { display: flex; flex-direction: column; }
      .av2 .nb-err__row { display: flex; align-items: flex-start; gap: 10px; padding: 10px 0 0; margin-top: 10px; border-top: 1px solid var(--av2-line); }
      .av2 .nb-err__row:first-child { margin-top: 0; padding-top: 0; border-top: 0; }
      .av2 .nb-err__row .av2-shape { margin-top: 5px; }
      .av2 .nb-err__q { flex: 1 1 auto; min-width: 0; font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body-lg); line-height: 1.3; color: var(--av2-ink); overflow-wrap: anywhere; }
      .av2 .nb-err__q s { text-decoration-color: var(--av2-red); }
      .av2 .nb-err__q b { font-weight: 700; color: var(--av2-green); }
      .av2 .nb-err__d { flex: none; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); white-space: nowrap; }
      .av2 .nb-notes__text { margin: 0; font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body-lg); line-height: 1.4; color: var(--av2-ink-2); overflow-wrap: anywhere; }
      .av2 .nb-notes__text[data-empty='true'] { color: var(--av2-muted); }
      .av2 .nb-notes__bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
      .av2 .nb-notes__state { margin-left: auto; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }
      .av2 .nb-notes__state[data-tone='alert'] { color: var(--av2-red); }
      .av2 .nb-notes__state[data-tone='story'] { color: var(--av2-blue); }
      .av2 .nb-field {
        display: block;
        width: 100%;
        min-height: 6rem;
        padding: 0.75rem 1rem;
        border: 2px solid transparent !important;
        border-radius: var(--av2-r-card) !important;
        box-shadow: none !important;
        background: var(--av2-card);
        color: var(--av2-ink);
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: var(--av2-t-body-lg);
        line-height: 1.45;
        resize: vertical;
      }
      .av2 .nb-field:focus { border-color: var(--av2-blue) !important; box-shadow: none !important; outline: none; }
      .av2 .nb-field--sans { font-family: inherit; font-style: normal; }
      .av2 .nb-field--line { min-height: 3rem; resize: none; }
      .av2 a.nb-cta { text-decoration: none; }

      /* ---- Le Relevé ---- */
      .av2 .nb-rv { display: flex; flex-direction: column; gap: 16px; }
      .av2 .nb-rv__sec { display: flex; flex-direction: column; gap: 10px; }
      .av2 .nb-rv__status { margin: 4px 0 0; }
      .av2 .nb-rv__tracks { display: flex; flex-direction: column; gap: 10px; margin-top: 6px; }
      .av2 .nb-rv__track { display: grid; grid-template-columns: 3.25rem minmax(0, 1fr); align-items: center; gap: 10px; }
      .av2 .nb-rv__track > span { font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-ink-2); }
      .av2 .nb-lines { display: flex; flex-direction: column; }
      .av2 .nb-line { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid var(--av2-line); }
      .av2 .nb-line:first-child { padding-top: 0; border-top: 0; }
      .av2 .nb-line__l { font-size: var(--av2-t-label); line-height: 1.3; color: var(--av2-ink-2); }
      .av2 .nb-line__n { flex: none; font-family: var(--av2-serif); font-style: italic; font-weight: 700; font-size: var(--av2-t-rule); line-height: 1; color: var(--av2-ink); font-variant-numeric: tabular-nums; white-space: nowrap; }
      .av2 .nb-line__n[data-zero='true'] { color: var(--av2-muted); }
      .av2 .nb-gap { margin: 0; font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body); line-height: 1.4; color: var(--av2-muted); }
      .av2 .nb-bar { display: flex; gap: 2px; height: 0.875rem; border-radius: 7px; overflow: hidden; background: var(--av2-line); }
      .av2 .nb-bar i { display: block; min-width: 4px; height: 100%; }
      .av2 .nb-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }
      .av2 .nb-legend span { display: inline-flex; align-items: center; gap: 6px; font-variant-numeric: tabular-nums; }
      .av2 .nb-legend i { flex: none; width: 10px; height: 10px; border-radius: 3px; background: var(--av2-line-2); }
      .av2 .nb-bar i[data-tone='new'], .av2 .nb-legend i[data-tone='new'] { background: var(--av2-line-2); }
      .av2 .nb-bar i[data-tone='fragile'], .av2 .nb-legend i[data-tone='fragile'] { background: var(--av2-red); }
      .av2 .nb-bar i[data-tone='building'], .av2 .nb-legend i[data-tone='building'] { background: var(--av2-blue); }
      .av2 .nb-bar i[data-tone='solid'], .av2 .nb-legend i[data-tone='solid'] { background: var(--av2-blue-deep); }
      .av2 .nb-bar i[data-tone='mastered'], .av2 .nb-legend i[data-tone='mastered'] { background: var(--av2-ink); }
      .av2 .nb-piece { display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; border-top: 1px solid var(--av2-line); }
      .av2 .nb-piece:first-child { padding-top: 0; border-top: 0; }
      .av2 .nb-piece .av2-shape { margin-top: 3px; }
      .av2 .nb-piece__main { flex: 1 1 auto; min-width: 0; }
      .av2 .nb-piece__t { display: block; font-size: var(--av2-t-body); font-weight: 600; line-height: 1.25; }
      .av2 .nb-piece__m { display: block; margin-top: 2px; font-size: var(--av2-t-meta); line-height: 1.35; color: var(--av2-muted); }
      .av2 .nb-piece__d { flex: none; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); white-space: nowrap; }
      .av2 .nb-foot {
        margin: 8px 0 0;
        padding-top: 14px;
        border-top: 1px solid var(--av2-line-2);
        text-align: center;
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: 0.875rem;
        line-height: 1.4;
        color: var(--av2-muted);
      }

      /* ---- La Bibliothèque (flag-gated) ---- */
      .av2 .nb-lib { display: flex; flex-direction: column; gap: 12px; }
      .av2 .nb-lib__grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; align-items: start; }
      @media (min-width: 720px) {
        .av2 .nb-lib__grid { grid-template-columns: minmax(14rem, 22rem) minmax(0, 1fr); }
      }
      .av2 .nb-lib__reader { display: flex; flex-direction: column; gap: 12px; }
      .av2 .nb-lib__passage { margin: 0; font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-option); line-height: 1.5; color: var(--av2-ink); }
      .av2 .nb-lib__passage p { margin: 0 0 14px; }
      .av2 .nb-lib__passage p:last-child { margin-bottom: 0; }
      .av2 .nb-lib__consignes { display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; }
      .av2 .nb-lib__stage { display: flex; flex-direction: column; gap: 10px; }
      .av2 .nb-lib__prompt { margin: 0; font-size: var(--av2-t-body-lg); font-weight: 600; line-height: 1.35; color: var(--av2-ink); }
      .av2 .nb-lib__evidence { margin: 0; padding: 10px 12px; border-radius: var(--av2-r-card); background: var(--av2-card); font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body-lg); line-height: 1.4; color: var(--av2-ink-2); }
      .av2 .nb-lib__criteria { margin: 0; padding-left: 18px; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2); }
      .av2 .nb-lib__actions { display: flex; justify-content: flex-end; }
    `}</style>
  );
}
