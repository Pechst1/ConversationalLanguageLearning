/**
 * Ton personnage — the editor's (`.pe-…`), the profile's (`.mo-…`) and the disc's (`.av-disc`)
 * styles. Every rule is under `.av2`, every colour, radius and type size an `--av2-*` token, so
 * dark mode comes with the tokens. The character's own colours are drawn, not styled.
 */
import React from 'react';

export function AvatarStyles() {
  return (
    <style jsx global>{`
      /* The character stands on a lit set: in the dark theme its ground is lifted towards the
         ink, so black hair and a navy coat read against it as well as cream ones do. */
      .av2 { --av-set: var(--av2-card); --av-set-glow: var(--av2-paper); }
      :root[data-theme='dark'] .av2:not(.av2--light),
      .av2--dark {
        --av-set: color-mix(in srgb, var(--av2-ink-2) 30%, var(--av2-card));
        --av-set-glow: color-mix(in srgb, var(--av2-ink-2) 44%, var(--av2-card));
      }
      @media (prefers-color-scheme: dark) {
        :root[data-theme='system'] .av2:not(.av2--light),
        :root:not([data-theme]) .av2:not(.av2--light) {
          --av-set: color-mix(in srgb, var(--av2-ink-2) 30%, var(--av2-card));
          --av-set-glow: color-mix(in srgb, var(--av2-ink-2) 44%, var(--av2-card));
        }
      }

      /* ---- the disc: a face, or a «+» ---- */
      .av2 .av-disc {
        position: relative;
        display: inline-grid;
        place-items: center;
        flex: none;
        overflow: hidden;
        border-radius: 50%;
        background: var(--av-set);
        box-shadow: inset 0 0 0 1px var(--av2-line);
        color: var(--av2-ink-2);
      }
      .av2 .av-disc > svg { display: block; }
      .av2 .av-disc--empty { box-shadow: inset 0 0 0 2px var(--av2-line-2); background: var(--av2-paper); }
      .av2 .nb-head__row { display: flex; align-items: center; gap: 12px; margin-top: 3px; }
      .av2 .nb-head__row .av2-headline { margin-top: 0; }
      .av2 .nb-disc {
        display: inline-flex;
        padding: 3px;
        border: 0;
        border-radius: 50%;
        background: transparent;
        cursor: pointer;
      }
      .av2 .nb-disc[aria-current='page'] { box-shadow: 0 0 0 2px var(--av2-ink); }
      .av2 .nb-disc:focus-visible { outline: 2px solid var(--av2-focus); outline-offset: 2px; }

      /* ---- the editor ---- */
      body:has(.pe-page) { background: var(--app-paper); }
      .av2.pe-page { display: block; width: 100%; }
      .av2 .pe {
        display: flex;
        flex-direction: column;
        width: 100%;
        max-width: 720px;
        min-height: 100vh;
        min-height: 100dvh;
        margin: 0 auto;
      }
      @media (min-height: 600px) {
        .av2 .pe { height: 100vh; height: 100dvh; }
        .av2 .pe-panel { flex: 1 1 auto; min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
      }
      .av2 .pe-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        padding: calc(14px + env(safe-area-inset-top, 0px)) var(--av2-gutter) 0;
      }
      .av2 .pe-top__titles { min-width: 0; }
      .av2 .pe-title { margin: 0; font-size: var(--av2-t-title); line-height: 1.1; }
      .av2 .pe-lede { margin: 4px 0 0; font-size: var(--av2-t-label); color: var(--av2-muted); }
      .av2 .pe-close { box-shadow: 0 0 0 1px var(--av2-line); }

      .av2 .pe-stage,
      .av2 .mo-hero__stage {
        position: relative;
        display: flex;
        flex: none;
        align-items: flex-end;
        justify-content: center;
        overflow: hidden;
        border-radius: var(--av2-r-hero);
        background:
          radial-gradient(ellipse 60% 70% at 50% 34%, var(--av-set-glow) 0%, transparent 70%),
          var(--av-set);
        box-shadow: inset 0 0 0 1px var(--av2-line);
      }
      .av2 .pe-stage { height: clamp(190px, 29vh, 320px); margin: 10px var(--av2-gutter) 0; }
      .av2 .pe-stage__floor,
      .av2 .mo-hero__floor {
        position: absolute;
        left: 50%;
        bottom: 5%;
        width: 40%;
        height: 7%;
        transform: translateX(-50%);
        border-radius: 50%;
        background: var(--av2-line);
      }
      .av2 .pe-stage .pe-stage__figure,
      .av2 .mo-hero__stage .mo-hero__figure {
        position: relative;
        z-index: 1;
        width: auto;
        height: 94%;
        margin-bottom: 3%;
      }
      .av2 .pe-stage__wait { width: 30%; height: 70%; margin-bottom: 8%; border-radius: 40% 40% 12px 12px; background: var(--av2-line); }

      .av2 .pe-tabs {
        display: flex;
        flex: none;
        gap: 6px;
        overflow-x: auto;
        padding: 12px var(--av2-gutter) 6px;
        scrollbar-width: none;
      }
      .av2 .pe-tabs::-webkit-scrollbar { display: none; }
      .av2 .pe-tab {
        flex: none;
        min-height: 40px;
        padding: 0 14px;
        border: 0;
        border-radius: var(--av2-r-pill);
        background: var(--av2-card);
        color: var(--av2-ink);
        box-shadow: inset 0 0 0 1px var(--av2-line);
        font: 600 var(--av2-t-label) / 1 var(--av2-sans);
        cursor: pointer;
      }
      .av2 .pe-tab[aria-selected='true'] { background: var(--av2-ink); color: var(--av2-on-ink); box-shadow: none; }
      .av2 .pe-tab:focus-visible,
      .av2 .pe-tile:focus-visible,
      .av2 .pe-swatch:focus-visible,
      .av2 .pe-toggle:focus-visible { outline: 2px solid var(--av2-focus); outline-offset: 2px; }

      .av2 .pe-panel { padding: 4px var(--av2-gutter) 12px; }
      .av2 .pe-section { margin: 10px 0 0; }
      .av2 .pe-section__h {
        margin: 0 0 8px;
        font-size: var(--av2-t-meta);
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--av2-muted);
      }
      .av2 .pe-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(84px, 1fr)); gap: 8px; }
      .av2 .pe-tile {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        min-width: 0;
        padding: 6px 4px 8px;
        border: 0;
        border-radius: var(--av2-r-tile);
        background: var(--av2-card);
        box-shadow: inset 0 0 0 1px var(--av2-line);
        color: var(--av2-ink);
        cursor: pointer;
        transition: transform var(--av2-press-dur);
      }
      .av2 .pe-tile:active { transform: scale(0.96); }
      .av2 .pe-tile[aria-pressed='true'] { box-shadow: inset 0 0 0 3px var(--av2-ink); }
      .av2 .pe-tile__art { display: block; width: 72px; height: 72px; overflow: hidden; border-radius: 12px; background: var(--av-set); }
      .av2 .pe-tile__name {
        max-width: 100%;
        overflow: hidden;
        font-size: var(--av2-t-meta);
        line-height: 1.2;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--av2-ink-2);
      }
      .av2 .pe-tile--locked .pe-tile__art { opacity: 0.42; filter: grayscale(0.6); }
      .av2 .pe-tile__lock {
        position: absolute;
        top: 5px;
        right: 5px;
        display: inline-flex;
        align-items: center;
        gap: 3px;
        padding: 3px 6px;
        border-radius: var(--av2-r-pill);
        background: var(--av2-yellow);
        color: var(--av2-on-yellow);
        font-size: 0.6875rem;
        font-weight: 700;
        line-height: 1;
      }
      .av2 .pe-zoom { position: relative; display: block; overflow: hidden; }
      .av2 .pe-zoom > svg { max-width: none; }

      .av2 .pe-swatches { display: flex; flex-wrap: wrap; gap: 4px; }
      .av2 .pe-swatch {
        display: inline-grid;
        place-items: center;
        width: var(--av2-tap);
        height: var(--av2-tap);
        padding: 0;
        border: 0;
        border-radius: 50%;
        background: transparent;
        cursor: pointer;
      }
      .av2 .pe-swatch__dot {
        display: block;
        width: 34px;
        height: 34px;
        border-radius: 50%;
        box-shadow: inset 0 0 0 1px var(--av2-line-2);
      }
      .av2 .pe-swatch[aria-pressed='true'] .pe-swatch__dot { box-shadow: 0 0 0 3px var(--av2-paper), 0 0 0 5px var(--av2-ink); }

      .av2 .pe-toggles { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0 0; }
      .av2 .pe-toggle {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        min-height: var(--av2-tap);
        padding: 0 14px 0 10px;
        border: 0;
        border-radius: var(--av2-r-pill);
        background: var(--av2-card);
        box-shadow: inset 0 0 0 1px var(--av2-line);
        color: var(--av2-ink);
        font: 600 var(--av2-t-label) / 1 var(--av2-sans);
        cursor: pointer;
      }
      .av2 .pe-toggle__box {
        display: inline-grid;
        place-items: center;
        width: 22px;
        height: 22px;
        border-radius: 7px;
        box-shadow: inset 0 0 0 2px var(--av2-line-2);
        font-size: 0.8125rem;
      }
      .av2 .pe-toggle[aria-pressed='true'] .pe-toggle__box { background: var(--av2-ink); color: var(--av2-on-ink); box-shadow: none; }
      .av2 .pe-note { margin: 12px 0 0; font-size: var(--av2-t-label); color: var(--av2-muted); }

      .av2 .pe-foot {
        flex: none;
        padding: 8px var(--av2-gutter) calc(12px + env(safe-area-inset-bottom, 0px));
        border-top: 1px solid var(--av2-line);
        background: var(--av2-paper);
      }
      @media (max-height: 599px) {
        .av2 .pe-foot { position: sticky; bottom: 0; }
      }
      .av2 .pe-foot__msg { min-height: 1.25em; margin: 0 0 8px; font-size: var(--av2-t-label); color: var(--av2-ink-2); }
      .av2 .pe-foot__err { color: var(--av2-red-deep); }
      .av2 .pe-foot__row { display: flex; align-items: center; gap: 10px; }
      .av2 .pe-foot__row > .av2-btn:not(.av2-btn--inline) { flex: 1 1 auto; }
      .av2 .pe-foot__row > .av2-btn--inline { flex: none; white-space: nowrap; }

      /* ---- the profile (Le Cahier · Moi) ---- */
      .av2 .mo { display: grid; gap: 16px; padding: 4px 0 8px; }
      .av2 .mo-hero { display: flex; align-items: center; gap: 16px; }
      .av2 .mo-hero--wait { min-height: 260px; border-radius: var(--av2-r-hero); background: var(--av2-card); }
      .av2 .mo-hero__stage { width: 46%; max-width: 220px; height: 260px; }
      .av2 .mo-hero__side { display: grid; justify-items: start; gap: 6px; min-width: 0; flex: 1 1 auto; }
      .av2 .mo-hero__name { margin: 0; overflow-wrap: anywhere; }
      .av2 .mo-hero__meta { margin: 0; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-muted); }
      .av2 .mo-hero__edit { margin-top: 6px; text-decoration: none; }

      .av2 .mo-make {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 16px;
        border-radius: var(--av2-r-hero);
        background: var(--av2-card);
        box-shadow: inset 0 0 0 2px var(--av2-line);
      }
      .av2 .mo-make__plus {
        display: inline-grid;
        place-items: center;
        flex: none;
        width: 112px;
        height: 112px;
        border-radius: 50%;
        background: var(--av2-paper);
        box-shadow: inset 0 0 0 3px var(--av2-line-2);
        color: var(--av2-ink);
      }
      .av2 .mo-make__plus:focus-visible { outline: 2px solid var(--av2-focus); outline-offset: 3px; }
      .av2 .mo-make__text { display: grid; justify-items: start; gap: 8px; min-width: 0; }
      .av2 .mo-make__text .av2-headline { margin: 0; }
      .av2 .mo-make__body { margin: 0; font-size: var(--av2-t-body); color: var(--av2-ink-2); }
      .av2 .mo-make__text .av2-btn { text-decoration: none; }

      .av2 .mo-block { padding: 14px 16px 16px; border-radius: var(--av2-r-card); background: var(--av2-card); }
      .av2 .mo-block__head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
      .av2 .mo-block__h { margin: 0; font-family: var(--av2-serif); font-size: var(--av2-t-title); font-weight: 600; line-height: 1.1; }
      .av2 .mo-count { font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-muted); white-space: nowrap; }
      .av2 .mo-lede { margin: 4px 0 12px; font-size: var(--av2-t-label); color: var(--av2-muted); }
      .av2 .mo-err { margin: 8px 0; font-size: var(--av2-t-label); color: var(--av2-red-deep); }

      .av2 .mo-name {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 4px 12px;
        margin: 10px 0 0;
        padding: 0 0 10px;
        border-bottom: 1px solid var(--av2-line);
      }
      .av2 .mo-name__l { flex: 0 0 6rem; font-size: var(--av2-t-label); color: var(--av2-muted); }
      .av2 .mo-name__v { flex: 1 1 6rem; min-width: 0; font-weight: 600; overflow-wrap: anywhere; }
      .av2 .mo-name__none { font-weight: 400; color: var(--av2-muted); }
      .av2 .mo-name__edit {
        min-height: var(--av2-tap);
        padding: 0 4px;
        border: 0;
        background: none;
        color: var(--av2-blue-deep);
        font: 600 var(--av2-t-label) / 1 var(--av2-sans);
        cursor: pointer;
      }
      .av2 .mo-name__input {
        flex: 1 1 10rem;
        min-width: 0;
        min-height: var(--av2-tap);
        padding: 0 12px;
        border: 0;
        border-radius: 12px;
        background: var(--av2-paper);
        box-shadow: inset 0 0 0 1px var(--av2-line-2);
        color: var(--av2-ink);
        font: 400 var(--av2-t-body) / 1.2 var(--av2-sans);
      }
      .av2 .mo-name__actions { display: flex; gap: 8px; flex: 1 1 100%; justify-content: flex-end; }
      .av2 .mo-lines { margin: 0; }
      .av2 .mo-line { display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--av2-line); }
      .av2 .mo-line dt { flex: 0 0 6rem; font-size: var(--av2-t-label); color: var(--av2-muted); }
      .av2 .mo-line dd { margin: 0; font-weight: 600; }
      .av2 .mo-settings {
        display: inline-flex;
        align-items: center;
        min-height: var(--av2-tap);
        margin-top: 4px;
        color: var(--av2-blue-deep);
        font-size: var(--av2-t-label);
        font-weight: 600;
      }

      .av2 .mo-wardrobe { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
      .av2 .mo-piece {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 10px 8px 8px;
        border-radius: var(--av2-r-tile);
        background: var(--av2-paper);
      }
      .av2 .mo-piece__art { position: relative; flex: none; width: 84px; height: 84px; overflow: hidden; border-radius: 12px; background: var(--av-set); }
      .av2 .mo-piece:not(.mo-piece--won) .mo-piece__art > .pe-zoom,
      .av2 .mo-piece:not(.mo-piece--won) .mo-piece__art > svg { opacity: 0.5; filter: grayscale(0.6); }
      .av2 .mo-piece__lock {
        position: absolute;
        right: 5px;
        bottom: 5px;
        display: inline-grid;
        place-items: center;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: var(--av2-yellow);
        color: var(--av2-on-yellow);
      }
      .av2 .mo-piece__main { display: grid; gap: 4px; min-width: 0; flex: 1 1 auto; }
      .av2 .mo-piece__name { font-weight: 700; }
      .av2 .mo-piece__how { font-size: var(--av2-t-label); color: var(--av2-ink-2); }
      .av2 .mo-piece__progress { display: flex; align-items: center; gap: 8px; }
      .av2 .mo-bar { position: relative; flex: 1 1 auto; height: 8px; overflow: hidden; border-radius: var(--av2-r-pill); background: var(--av2-line); }
      .av2 .mo-bar__fill { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background: var(--av2-yellow-deep); }
      .av2 .mo-piece__count { font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); white-space: nowrap; }
      .av2 .mo-piece__yours { font-size: var(--av2-t-label); font-weight: 700; color: var(--av2-green-deep); }
      .av2 .mo-piece__wear {
        justify-self: start;
        min-height: 36px;
        padding: 0 14px;
        border: 0;
        border-radius: var(--av2-r-pill);
        background: var(--av2-ink);
        color: var(--av2-on-ink);
        font: 700 var(--av2-t-label) / 1 var(--av2-sans);
        cursor: pointer;
      }
      .av2 .mo-piece__wear[aria-pressed='true'] { background: var(--av2-card); color: var(--av2-ink); box-shadow: inset 0 0 0 2px var(--av2-ink); }
      .av2 .mo-piece__wear:disabled { cursor: progress; }
    `}</style>
  );
}

export default AvatarStyles;
