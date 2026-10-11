/* The archive's own rules (WP-96/97): the chapter folds, the planche's reply,
 * the colophon, the tome, the margin note, the trust marks, «Précédemment».
 *
 * Tokens only (`--av2-*`, `styles/atelier-v2.css`): Garamond for the story and
 * the printed marks, Instrument Sans for the chrome, the av2 colour roles, no
 * new font and no new colour. Every rule is written `.av2 .fa-…` so it sits
 * under the page resets. Reduce Motion removes the fold's ease. The rows reuse
 * the season list's `.fr-row` (reader-styles.tsx). */

import React from 'react';

export function ArchiveStyles() {
  return (
    <style jsx global>{`
      .av2 .fa-seg {
        display: flex;
        gap: 2px;
        margin-top: 14px;
        padding: 3px;
        border-radius: var(--av2-r-pill);
        background: var(--av2-card);
      }
      .av2 .fa-seg a {
        flex: 1 1 0;
        min-height: var(--av2-tap);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0 10px;
        border-radius: var(--av2-r-pill);
        color: var(--av2-ink);
        font-family: var(--av2-sans);
        font-size: var(--av2-t-body-lg);
        font-weight: 700;
        text-align: center;
        text-decoration: none;
        overflow-wrap: anywhere;
      }
      .av2 .fa-seg a[aria-current='page'] { background: var(--av2-ink); color: var(--av2-on-ink); }
      .av2 .fa-seg a:focus-visible { outline: 3px solid var(--av2-focus); outline-offset: 2px; }

      .av2 .fa-volume { display: flex; flex-direction: column; gap: 14px; margin-top: 18px; }

      /* ---- a finished season: the tome ---- */
      .av2 .fa-tome {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        padding: 18px 16px;
        border-radius: var(--av2-r-hero);
        background: var(--av2-card);
        text-align: center;
      }
      .av2 .fa-tome .av2-seal { margin: 0 auto; }
      .av2 .fa-tome__title {
        margin: 0;
        font-family: var(--av2-serif);
        font-style: italic;
        font-weight: 600;
        font-size: var(--av2-t-title);
        line-height: 1.1;
        color: var(--av2-ink);
      }

      /* ---- WP-98: a new season opens a new volume ---- */
      .av2 .fa-volume-new { display: flex; flex-direction: column; gap: 14px; }
      .av2 .fa-volume-new__head {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 18px 0 14px;
        border-top: 2px solid var(--av2-ink);
        border-bottom: 1px solid var(--av2-line-2);
      }
      .av2 .fa-volume-new__head > * { margin: 0; }
      .av2 .fa-volume-new__title { font-style: italic; }
      .av2 .fa-volume-new__logline { color: var(--av2-ink-2); }

      /* ---- a chapter: a fold ---- */
      .av2 .fa-chapter { border-top: 1px solid var(--av2-line-2); padding-top: 4px; }
      .av2 .fa-chapter__head {
        width: 100%;
        min-height: var(--av2-tap);
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 10px 2px;
        border: 0;
        background: transparent;
        color: var(--av2-ink);
        text-align: left;
        font: inherit;
        cursor: pointer;
      }
      .av2 .fa-chapter__head:focus-visible { outline: 3px solid var(--av2-focus); outline-offset: 2px; border-radius: 8px; }
      .av2 .fa-chapter__id { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
      .av2 .fa-chapter__kicker { font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
      .av2 .fa-chapter__kicker[data-current='true'] { color: var(--av2-blue); }
      .av2 .fa-chapter__title {
        font-family: var(--av2-serif);
        font-style: italic;
        font-weight: 600;
        font-size: var(--av2-t-title);
        line-height: 1.1;
        overflow-wrap: anywhere;
      }
      .av2 .fa-chapter__fold {
        flex: none;
        margin-top: 6px;
        width: 12px;
        height: 12px;
        border-radius: 2px;
        background: var(--av2-ink);
        transition: transform 180ms ease;
      }
      .av2 .fa-chapter__head[aria-expanded='true'] .fa-chapter__fold { transform: rotate(45deg); }
      .av2 .fa-chapter__body { padding-bottom: 8px; }
      .av2 .fa-chapter__body .fr-rows { padding-top: 4px; }

      /* the digest line «question → résolution» */
      .av2 .fa-digest {
        margin: 0;
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: var(--av2-t-body-lg);
        line-height: 1.35;
        color: var(--av2-ink-2);
        overflow-wrap: anywhere;
      }
      .av2 .fa-sr {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
        white-space: nowrap;
        border: 0;
      }
      .av2 .fa-digest__arrow { color: var(--av2-blue); font-style: normal; }

      /* ---- the colophon ---- */
      .av2 .fa-colophon {
        margin: 18px 0 6px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        text-align: center;
      }
      .av2 .fa-colophon__end {
        font-family: var(--av2-serif);
        font-style: italic;
        font-weight: 600;
        font-size: var(--av2-t-rule);
        color: var(--av2-ink);
      }
      .av2 .fa-colophon__rule { width: 48px; height: 2px; background: var(--av2-ink); border: 0; margin: 0; }

      /* ---- one planche, reread ---- */
      .av2 .fa-day { display: flex; flex-direction: column; gap: 14px; margin-top: 12px; }
      .av2 .fa-back {
        align-self: flex-start;
        min-height: var(--av2-tap);
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--av2-ink);
        font-size: var(--av2-t-body-lg);
        font-weight: 700;
        text-decoration: none;
      }
      .av2 .fa-back:focus-visible { outline: 3px solid var(--av2-focus); outline-offset: 2px; border-radius: 8px; }
      /* WP-109: today's episode, first — the one way into the story from here. */
      .av2 .fa-today {
        display: flex; flex-direction: column; gap: 10px;
        margin: 0 0 20px; padding: 16px 18px 18px;
        border-radius: var(--av2-r-card); background: var(--av2-card);
      }
      .av2 .fa-today h2 { margin: 0; }
      .av2 .fa-today p { margin: 0; }
      .av2 .fa-today__cast { display: flex; gap: 6px; margin: 0; padding: 0; list-style: none; }
      .av2 .fa-today .av2-btn { align-self: stretch; justify-content: center; margin-top: 4px; }
      .av2 .fa-plate { border-radius: var(--av2-r-card); overflow: hidden; background: var(--av2-card); }
      .av2 .fa-plate img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; }
      .av2 .fa-plate__body { padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 8px; }
      .av2 .fa-reply {
        padding: 16px 18px;
        border-radius: var(--av2-r-card);
        background: var(--av2-card);
        display: flex;
        flex-direction: column;
        gap: 8px;
        scroll-margin-top: 16px;
      }
      .av2 .fa-reply__line {
        margin: 0;
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: var(--av2-t-option);
        line-height: 1.3;
        color: var(--av2-ink);
        overflow-wrap: anywhere;
      }
      .av2 .fa-ending {
        margin: 0;
        font-family: var(--av2-serif);
        font-size: var(--av2-t-body-lg);
        line-height: 1.45;
        color: var(--av2-ink);
      }

      /* ---- a margin note ---- */
      .av2 .fa-margins { display: flex; flex-direction: column; gap: 6px; margin: 10px 0 0; padding: 0; list-style: none; }
      .av2 .fa-margin {
        margin: 0;
        padding: 4px 0 4px 12px;
        border-left: 3px solid var(--av2-blue);
      }
      .av2 .fa-margin__link,
      .av2 .fa-margin__static {
        display: block;
        min-height: var(--av2-tap);
        padding: 6px 0;
        color: var(--av2-ink-2);
        text-decoration: none;
        font-size: var(--av2-t-body-lg);
        line-height: 1.35;
      }
      .av2 .fa-margin__link:focus-visible { outline: 3px solid var(--av2-focus); outline-offset: 2px; border-radius: 6px; }
      .av2 .fa-margin__text { font-family: var(--av2-serif); font-style: italic; }
      .av2 .fa-margin__ref { font-family: var(--av2-sans); font-weight: 700; font-size: var(--av2-t-label); color: var(--av2-blue); white-space: nowrap; }
      .av2 .fa-margin__link .fa-margin__ref { text-decoration: underline; text-underline-offset: 3px; }

      /* ---- le trombinoscope ---- */
      .av2 .fa-cast { display: flex; flex-direction: column; gap: 10px; padding: 18px 0 0; }
      .av2 .fa-card { display: flex; flex-direction: column; gap: 12px; }
      .av2 .fa-card__top { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; min-width: 0; }
      .av2 .fa-card__id { flex: 1 1 9rem; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
      .av2 .fa-portrait {
        flex: none;
        display: grid;
        place-items: center;
        width: 64px;
        height: 64px;
        border-radius: 999px;
        overflow: hidden;
        background: var(--cast-accent, var(--av2-char-default));
        color: var(--av2-on-dark);
        font-family: var(--av2-serif);
        font-style: italic;
        font-weight: 600;
        font-size: var(--av2-t-title);
      }
      .av2 .fa-portrait img { width: 100%; height: 100%; object-fit: cover; display: block; }
      .av2 .fa-portrait--me { background: var(--av2-card); color: var(--av2-ink); }
      .av2 .cast-me .av2-label, .av2 .cast-me .av2-body, .av2 .cast-me .av2-headline { color: inherit; }
      .av2 .cast-me .av2-chip { flex: none; white-space: nowrap; background: var(--av2-card); color: var(--av2-ink); }
      .av2 .cast-me__body { display: flex; flex-direction: column; gap: 10px; }
      .av2 .cast-me__body .av2-field__label { color: inherit; }
      .av2 .cast-me__actions { display: flex; flex-wrap: wrap; gap: 10px; }
      .av2 .cast-me__actions > .av2-btn { flex: 1 1 10rem; width: auto; }
      .av2 .fa-known-block { display: flex; flex-direction: column; gap: 6px; }
      .av2 .av2-recap__volume { display: flex; flex-direction: column; align-items: center; gap: 10px; text-align: center; }
      .av2 .fa-register { margin: 0; font-size: var(--av2-t-label); font-weight: 700; color: var(--av2-ink-2); }
      .av2 .fa-register[data-register='tu'] { color: var(--av2-blue); }
      .av2 .fa-trust-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
      .av2 .fa-trust { display: inline-flex; gap: 6px; align-items: center; }
      .av2 .fa-trust i {
        display: block;
        width: 12px;
        height: 12px;
        border-radius: 999px;
        box-sizing: border-box;
      }
      .av2 .fa-trust i[data-mark='filled'] { background: var(--av2-blue); box-shadow: 0 2px 0 var(--av2-blue-deep); }
      .av2 .fa-trust i[data-mark='empty'] { background: transparent; border: 2px solid var(--av2-line-2); }
      .av2 .fa-known { display: flex; flex-direction: column; gap: 6px; margin: 0; padding: 0; list-style: none; }
      .av2 .fa-known li { display: flex; gap: 10px; align-items: baseline; }
      .av2 .fa-known__date { flex: none; min-width: 4.5em; font-size: var(--av2-t-label); font-weight: 700; color: var(--av2-muted); }
      .av2 .fa-known__text { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body-lg); line-height: 1.35; color: var(--av2-ink); }

      /* ---- «Précédemment» ---- */
      .av2 .fa-previously {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 16px 18px 18px;
        border-radius: var(--av2-r-card);
        background: var(--av2-card);
        border-top: 3px solid var(--av2-ink);
      }
      .av2 .fa-previously__list { display: flex; flex-direction: column; gap: 6px; margin: 0; padding: 0; list-style: none; }
      .av2 .fa-previously__list .fr-line {
        margin: 0;
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: var(--av2-t-body-lg);
        line-height: 1.4;
        color: var(--av2-ink);
      }
      .av2 .fa-previously__list .fr-word {
        border: 0;
        padding: 0;
        margin: 0;
        background: none;
        font: inherit;
        color: inherit;
        cursor: pointer;
        text-decoration: underline dotted var(--av2-line-2);
        text-underline-offset: 4px;
      }

      @media (prefers-reduced-motion: reduce) {
        .av2 .fa-chapter__fold { transition: none; }
      }
    `}</style>
  );
}

export default ArchiveStyles;
