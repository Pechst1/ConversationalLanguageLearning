/**
 * WP-144 «La page verticale» — styles. av2 only: the reader's `--fr-*` aliases
 * of the av2 tokens, EB Garamond and Instrument Sans, the existing press depths.
 * No new font, no new colour. Every movement stops under Reduce Motion.
 */

// The node suites compile JSX to the classic runtime.
import React from 'react';

export function VerticalPageStyles() {
  return (
    <style jsx global>{`
      /* The reader's chrome: the bar (44 px + 20 px + the notch) and the pinned nav
         (dots, ← / Weiter, its padding and the home indicator). The panel is the
         screen between them. */
      .av2 .fr-reader[data-layout='vertical'] {
        --vp-bar: calc(64px + env(safe-area-inset-top, 0px));
        --vp-nav: calc(128px + env(safe-area-inset-bottom, 0px));
      }
      .av2 .fr-reader[data-layout='vertical'] .fr-stage {
        position: relative;
        gap: 10px;
      }
      /* «Déjà lu» / «À vous» ride on the panel's top edge instead of pushing it down. */
      .av2 .fr-reader[data-layout='vertical'] .fr-stage > .fr-state {
        position: absolute;
        top: 10px;
        right: 0;
        z-index: 4;
        margin: 0;
        padding: 4px 10px 4px 6px;
        border-radius: 999px;
        background: var(--fr-paper);
        box-shadow: 0 2px 0 var(--fr-line-2);
      }

      .av2 .vp-panel {
        position: relative;
        overflow: hidden;
        isolation: isolate;
        height: calc(100dvh - var(--vp-bar) - var(--vp-nav));
        min-height: 380px;
        background: var(--fr-story-bg);
        border-radius: 16px;
      }
      @media (max-width: 599px) {
        /* full-bleed: the panel spans the phone, edge to edge */
        .av2 .fr-reader[data-layout='vertical'] { overflow-x: visible; }
        .av2 .vp-panel {
          width: 100vw;
          max-width: none;
          margin-inline: calc(50% - 50vw);
          border-radius: 0;
        }
      }
      @media (min-width: 600px) {
        /* a wider screen keeps the page's proportion: never wider than 9:16 is tall */
        .av2 .vp-panel { max-height: calc(min(100%, 560px) * 16 / 9); }
      }

      /* ---- the picture: plate, cast, camera ---- */
      .av2 .vp-camera {
        position: absolute;
        inset: 0;
        z-index: 0;
      }
      .av2 .vp-plate {
        position: absolute;
        inset: 0;
        display: block;
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      .av2 .vp-plate--none { background: var(--fr-story-bg); }
      .av2 .vp-plate[data-pending='true'] { filter: grayscale(1) contrast(1.08) brightness(1.06); }
      .av2 .vp-cast {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 45%;
      }
      .av2 .vp-tails {
        position: absolute;
        left: 0;
        top: 0;
        z-index: 1;
        pointer-events: none;
        overflow: visible;
      }
      .av2 .vp-tail { fill: var(--fr-card); }

      /* ---- paper (WP-144b): balloons, captions, tails and the docked sheet stay
         light in dark mode, as in a printed comic. The element is its own light
         av2 root (class "av2 av2--light"), so every token below is the light one. */
      .av2 .vp-paper {
        --fr-paper: var(--av2-paper);
        --fr-card: var(--av2-card);
        --fr-line: var(--av2-line);
        --fr-line-2: var(--av2-line-2);
        --fr-ink: var(--av2-ink);
        --fr-ink-2: var(--av2-ink-2);
        --fr-muted: var(--av2-muted);
        --fr-red: var(--av2-red);
        --fr-red-shadow: var(--av2-red-deep);
        --fr-blue: var(--av2-blue);
        --fr-focus: var(--av2-focus);
        --fr-accent: var(--av2-muted);
        /* the character accents at their light values (reader-styles.tsx) */
        --char-romy: #1d3a8a;
        --char-marin: #2c6a5d;
        --char-lila: #c2890f;
        --char-gus: #8a2f2a;
        --char-margaux: #a85d24;
        --char-marchand: #5b5346;
        --char-toi: var(--av2-ink);
      }
      .av2 .vp-tails.vp-paper { background: none; min-width: 0; }

      /* ---- balloons and captions ---- */
      .av2 .vp-balloon,
      .av2 .vp-caption {
        position: absolute;
        z-index: 2;
        box-sizing: border-box;
        width: max-content;
        min-width: 0;
        overflow-wrap: anywhere;
      }
      .av2 .vp-balloon {
        max-width: min(calc(100% - 24px), 19em);
        padding: 9px 14px 11px;
        border-radius: 18px;
        background: var(--fr-card);
        color: var(--fr-ink);
        box-shadow: 0 var(--av2-press-sm) 0 var(--fr-line-2);
      }
      /* the line being heard: its speaker's accent under the balloon */
      .av2 .vp-balloon[data-speaking='true'] { box-shadow: 0 var(--av2-press-sm) 0 var(--fr-accent); }
      .av2 .vp-who {
        display: block;
        margin: 0 0 2px;
        padding: 0;
        border: 0;
        background: none;
        font-family: var(--fr-sans);
        font-size: 0.75rem;
        font-weight: 700;
        line-height: 1.3;
        color: var(--fr-accent);
        text-align: left;
      }
      button.vp-who {
        position: relative;
        cursor: pointer;
      }
      /* a 44 px target around a small name */
      button.vp-who::after {
        content: '';
        position: absolute;
        inset: -14px -10px;
      }
      button.vp-who:focus-visible { outline: 2px solid var(--fr-focus); outline-offset: 2px; border-radius: 4px; }
      .av2 .vp-line {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: 1.125rem;
        line-height: 1.3;
        color: var(--fr-ink);
      }
      /* WP-144b: a balloon with its speaker's face, when no figure stands on the plate */
      .av2 .vp-portrait-row { display: flex; align-items: flex-start; gap: 10px; }
      .av2 .vp-portrait-row__text { min-width: 0; }
      .av2 .vp-en { margin: 3px 0 0; font-size: 0.8125rem; line-height: 1.4; }

      /* the learner's own line: the bottom edge, the point of view; red press, as everywhere it is you */
      .av2 .vp-balloon--you {
        /* WP-144b: docked at the bottom edge, full width minus the gutters, no tail */
        width: calc(100% - 24px);
        max-width: none;
        border-radius: 18px 18px 4px 18px;
        box-shadow: 0 var(--av2-press-sm) 0 var(--fr-red);
      }
      .av2 .vp-balloon--you .vp-who { color: var(--fr-red); text-align: right; }
      .av2 .vp-balloon--you .vp-line { font-family: var(--fr-sans); font-style: normal; font-size: 1.0625rem; }

      /* narration: a rectangular caption box, top left, on paper */
      .av2 .vp-caption {
        max-width: min(calc(100% - 24px), 22em);
        padding: 8px 12px 9px;
        border-radius: 6px;
        background: var(--fr-paper);
        color: var(--fr-ink);
        box-shadow: 0 2px 0 var(--fr-line-2);
      }
      .av2 .vp-caption__eyebrow {
        margin: 0 0 2px;
        font-size: 0.75rem;
        font-weight: 700;
        line-height: 1.3;
        color: var(--fr-blue);
      }
      .av2 .vp-caption__title {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: 1.75rem;
        line-height: 1.05;
        color: var(--fr-ink);
        text-wrap: balance;
      }
      .av2 .vp-caption__line {
        margin: 0;
        font-size: 0.9375rem;
        line-height: 1.45;
        color: var(--fr-ink-2);
      }
      .av2 .vp-caption__line--silent { font-style: italic; }

      /* ---- arrival ---- */
      .av2 .vp-panel [data-shown='false'] {
        opacity: 0;
        pointer-events: none;
      }
      .av2 .vp-panel [data-unrevealed],
      .av2 .vp-sheet [data-unrevealed] { opacity: 0; }

      /* ---- the overflow sheet: docked under the faces, or under the panel ---- */
      .av2 .vp-sheet {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .av2 .vp-sheet[data-sheet='dock'] {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 3;
        overflow-y: auto;
        overscroll-behavior: contain;
        padding: 12px 16px 14px;
        border-radius: 18px 18px 0 0;
        background: var(--fr-paper);
        box-shadow: 0 -2px 0 var(--fr-line-2);
      }
      .av2 .vp-sheet[data-sheet='below'],
      .av2 .vp-fallback {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-top: 10px;
      }
      .av2 .vp-sheet__row { min-width: 0; }
      .av2 .vp-sheet__row[data-kind='you'] .vp-who { color: var(--fr-red); }
      .av2 .vp-sheet__row[data-kind='you'] .vp-line { font-family: var(--fr-sans); font-style: normal; }

      /* ---- measuring: every entry at its natural size, invisible ---- */
      .av2 .vp-measure {
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
        height: 0;
        overflow: visible;
        visibility: hidden;
        pointer-events: none;
        z-index: -1;
      }
      .av2 .vp-measure > * { left: 0; top: 0; }

      @media (prefers-reduced-motion: no-preference) {
        .av2 .vp-camera[data-push='in'] { animation: vp-push 18s ease-out both; }
        .av2 .vp-plate[data-pan='slow'] { animation: fr-slow-pan 14s ease-in-out infinite alternate; transform-origin: 30% 50%; }
        .av2 .vp-balloon,
        .av2 .vp-caption,
        .av2 .vp-sheet__row { transition: opacity 0.24s ease, transform 0.24s ease; }
        .av2 .vp-panel .vp-balloon[data-shown='false'] { transform: translateY(6px) scale(0.97); }
        .av2 .vp-panel [data-unrevealed] + *,
        .av2 .vp-panel .fr-word,
        .av2 .vp-panel .vp-line span { transition: opacity 0.12s linear; }
        @keyframes vp-push {
          from { transform: scale(1); }
          to { transform: scale(1.06); }
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .av2 .vp-camera,
        .av2 .vp-plate { animation: none !important; transform: none !important; }
        .av2 .vp-panel [data-unrevealed] { opacity: 1; }
      }
    `}</style>
  );
}

export default VerticalPageStyles;
