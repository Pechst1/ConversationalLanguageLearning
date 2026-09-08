/* Scoped styles for the Feuilleton reader and the season list.
 *
 * One system, not two: every colour, font, radius and press below is an
 * `--av2-*` token from `styles/atelier-v2.css`, so the reader and the daily
 * session agree in light and in dark. The `--fr-*` names are kept only as
 * local aliases, so the component markup (and the tests that assert on its
 * classes) did not have to change.
 *
 * Every rule is written `.av2 .fr-…` (0,2,0). That is deliberate: the reader
 * is mounted inside `pages/graphic-novel.tsx`, whose page-level reset
 * `.feuilleton-page button { border: 0; background: transparent }` is (0,1,1)
 * and used to strip every option card and button of its face. The caller
 * wraps the reader in `<AtelierV2Root>`, which supplies `.av2`.
 */

export function FeuilletonReaderStyles() {
  return (
    <style jsx global>{`
      .av2 .fr-reader,
      .av2.fr-page,
      .av2 .fr-page,
      .av2 .fr-sheet-root {
        --fr-paper: var(--av2-paper);
        --fr-card: var(--av2-card);
        --fr-line: var(--av2-line);
        --fr-line-2: var(--av2-line-2);
        --fr-ink: var(--av2-ink);
        --fr-ink-2: var(--av2-ink-2);
        --fr-muted: var(--av2-muted);
        --fr-red: var(--av2-red);
        --fr-red-shadow: var(--av2-red-deep);
        --fr-on-red: var(--av2-on-red);
        --fr-blue: var(--av2-blue);
        /* the Feuilleton's story surface: the design's filled blue card. In
           dark the accent lifts and its label flips to ink, exactly as every
           other blue surface in the system does. */
        --fr-story-bg: var(--av2-blue);
        --fr-story-fg: var(--av2-on-blue);
        --fr-story-press: var(--av2-line-2);
        --fr-yellow: var(--av2-yellow);
        --fr-green: var(--av2-green);
        --fr-on-green: var(--av2-on-green);
        --fr-focus: var(--av2-focus);
        /* character accents — the serial world bible, one system with the UI */
        --char-romy: #1d3a8a;
        --char-marin: #2c6a5d;
        --char-lila: #c2890f;
        --char-gus: #8a2f2a;
        --char-margaux: #a85d24;
        --char-marchand: #5b5346;
        --char-toi: var(--fr-ink);
        --fr-accent: var(--fr-muted);
        /* two fonts only — the vendored faces, never a name that falls back */
        --fr-sans: var(--av2-sans);
        --fr-serif: var(--av2-serif);
        --fr-press: var(--av2-press-dur) ease;
        font-family: var(--fr-sans);
        color: var(--fr-ink);
      }
      /* Character accents lifted for dark, on the same three conditions the
         av2 tokens use, so a character keeps its colour whichever way the
         theme was chosen. */
      :root[data-theme='dark'] .av2:not(.av2--light) .fr-reader,
      :root[data-theme='dark'] .av2:not(.av2--light) .fr-sheet-root,
      .av2--dark .fr-reader,
      .av2--dark .fr-sheet-root {
        --char-romy: #7c9bff;
        --char-marin: #5fb3a1;
        --char-lila: #e0ad3e;
        --char-gus: #d97a72;
        --char-margaux: #d68f52;
        --char-marchand: #a89b86;
      }
      @media (prefers-color-scheme: dark) {
        :root[data-theme='system'] .av2:not(.av2--light) .fr-reader,
        :root:not([data-theme]) .av2:not(.av2--light) .fr-reader,
        :root[data-theme='system'] .av2:not(.av2--light) .fr-sheet-root,
        :root:not([data-theme]) .av2:not(.av2--light) .fr-sheet-root {
          --char-romy: #7c9bff;
          --char-marin: #5fb3a1;
          --char-lila: #e0ad3e;
          --char-gus: #d97a72;
          --char-margaux: #d68f52;
          --char-marchand: #a89b86;
        }
      }

      .av2 .fr-reader [data-char='romy'] { --fr-accent: var(--char-romy); }
      .av2 .fr-reader [data-char='marin'] { --fr-accent: var(--char-marin); }
      .av2 .fr-reader [data-char='lila'] { --fr-accent: var(--char-lila); }
      .av2 .fr-reader [data-char='gus'] { --fr-accent: var(--char-gus); }
      .av2 .fr-reader [data-char='margaux'] { --fr-accent: var(--char-margaux); }
      .av2 .fr-reader [data-char='marchand'] { --fr-accent: var(--char-marchand); }
      .av2 .fr-reader [data-char='toi'] { --fr-accent: var(--char-toi); }

      .av2.fr-scope { display: block; width: 100%; min-width: 0; background: transparent; }

      .av2 .fr-reader {
        display: flex;
        flex-direction: column;
        gap: 0;
        width: 100%;
        max-width: 560px;
        margin: 0 auto;
        padding: 0 16px;
        box-sizing: border-box;
        overflow-x: clip;
      }

      /* ---- top bar: quit · story progress rail · counter ---- */
      .av2 .fr-bar {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 0 14px;
      }
      .av2 .fr-icon-btn {
        width: 44px;
        height: 44px;
        flex: none;
        padding: 0;
        border: 0;
        border-radius: 999px;
        background: var(--fr-card);
        color: var(--fr-ink);
        display: grid;
        place-items: center;
        cursor: pointer;
        transition: transform var(--fr-press);
      }
      .av2 .fr-icon-btn:active { transform: scale(0.94); }
      .av2 .fr-rail {
        flex: 1 1 auto;
        min-width: 0;
        height: 14px;
        border-radius: 7px;
        background: var(--fr-line);
        overflow: hidden;
      }
      .av2 .fr-rail i {
        display: block;
        height: 100%;
        border-radius: 7px;
        background: var(--fr-blue);
        transition: width 0.35s cubic-bezier(0.2, 0.8, 0.2, 1);
      }
      .av2 .fr-count {
        flex: none;
        font-size: 0.8125rem;
        font-weight: 700;
        color: var(--fr-muted);
        font-variant-numeric: tabular-nums;
      }

      /* ---- running head: eyebrow + the ONE Garamond italic headline ---- */
      .av2 .fr-head { padding: 2px 0 14px; }
      .av2 .fr-eyebrow {
        margin: 0;
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--fr-muted);
      }
      .av2 .fr-title {
        margin: 3px 0 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: var(--av2-t-screen);
        line-height: 1;
        color: var(--fr-ink);
        text-wrap: pretty;
        overflow-wrap: anywhere;
      }
      .av2 .fr-previously {
        margin: 8px 0 0;
        font-size: 0.8125rem;
        line-height: 1.45;
        color: var(--fr-muted);
      }

      /* ---- the stage: one panel at a time ---- */
      .av2 .fr-stage {
        display: flex;
        flex-direction: column;
        gap: 14px;
        touch-action: pan-y;
      }
      .av2 .fr-stage:focus-visible { outline: 3px solid var(--fr-focus); outline-offset: 6px; border-radius: 24px; }

      .av2 .fr-plate {
        position: relative;
        margin: 0;
        border-radius: var(--av2-r-hero);
        overflow: hidden;
        background: var(--fr-story-bg);
        aspect-ratio: 1 / 1;
        max-block-size: min(44vh, 400px);
      }
      .av2 .fr-plate img {
        display: block;
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      .av2 .fr-plate.is-printing,
      .av2 .fr-plate.is-missing {
        display: grid;
        place-items: center;
        text-align: center;
        padding: 20px;
        aspect-ratio: 16 / 9;
      }
      /* the design's hatched "illustration" placeholder, on the story surface */
      .av2 .fr-plate.is-printing {
        background: repeating-linear-gradient(
          135deg,
          var(--fr-story-bg) 0 8px,
          color-mix(in srgb, var(--fr-story-bg) 88%, var(--fr-story-fg)) 8px 16px
        );
        color: var(--fr-story-fg);
      }
      .av2 .fr-plate.is-missing {
        background: transparent;
        border: 2px dashed var(--fr-line-2);
        color: var(--fr-muted);
      }
      .av2 .fr-plate .fr-plate-note {
        font-size: 0.8125rem;
        font-weight: 600;
        max-width: 30ch;
        line-height: 1.4;
      }
      .av2 .fr-plate.is-printing .fr-plate-note { opacity: 0.92; }

      /* ---- speech: accent identifies the speaker before the name is read ---- */
      .av2 .fr-speech {
        background: var(--fr-card);
        border-radius: 18px;
        padding: 14px 16px;
        border-left: 4px solid var(--fr-accent);
      }
      .av2 .fr-speaker {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 0 6px;
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--fr-accent);
      }
      .av2 .fr-speaker .glyph {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--fr-accent);
        flex: none;
      }
      .av2 .fr-line {
        margin: 0;
        font-size: 1rem;
        line-height: 1.5;
        color: var(--fr-ink);
      }
      .av2 .fr-line + .fr-speaker { margin-top: 12px; }
      .av2 .fr-line-en {
        margin: 4px 0 0;
        font-size: 0.875rem;
        line-height: 1.45;
        color: var(--fr-muted);
      }
      .av2 .fr-caption {
        margin: 0;
        font-size: 0.875rem;
        line-height: 1.5;
        color: var(--fr-ink-2);
        padding: 0 2px;
      }

      /* tappable word */
      .av2 .fr-word {
        border: 0;
        background: transparent;
        padding: 0;
        margin: 0;
        font: inherit;
        color: inherit;
        cursor: pointer;
        border-bottom: 1px dotted color-mix(in srgb, var(--fr-muted) 60%, transparent);
        border-radius: 3px;
      }
      .av2 .fr-word:hover { background: color-mix(in srgb, var(--fr-yellow) 34%, transparent); }
      .av2 .fr-word:focus-visible { outline: 2px solid var(--fr-focus); outline-offset: 2px; }

      .av2 .fr-tools {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }
      .av2 .fr-chip {
        min-height: 44px;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 0 14px;
        border: 0;
        border-radius: 999px;
        background: var(--fr-card);
        color: var(--fr-ink);
        font-family: var(--fr-sans);
        font-size: 0.8125rem;
        font-weight: 700;
        text-decoration: none;
        cursor: pointer;
        transition: transform var(--fr-press);
      }
      .av2 .fr-chip:active { transform: scale(0.96); }
      .av2 .fr-chip .sq {
        width: 8px;
        height: 8px;
        border-radius: 2px;
        background: var(--fr-yellow);
        flex: none;
      }
      .av2 .fr-chip[aria-pressed='true'],
      .av2 .fr-chip[data-active='true'] { background: var(--fr-ink); color: var(--av2-on-ink); }

      /* ---- browse vs act: a revisit is stated, never re-played ---- */
      .av2 .fr-state {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin: 0;
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--fr-muted);
      }
      .av2 .fr-state .tok {
        width: 18px;
        height: 18px;
        border-radius: 5px;
        background: var(--fr-ink);
        color: var(--av2-on-ink);
        display: grid;
        place-items: center;
        flex: none;
      }
      .av2 .fr-state.is-live { color: var(--fr-red); }
      .av2 .fr-state.is-live .tok {
        border-radius: 999px;
        background: var(--fr-red);
      }

      /* ---- the learner's action ---- */
      .av2 .fr-act {
        background: var(--fr-card);
        border-radius: 18px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .av2 .fr-act.is-read { background: transparent; border: 2px dashed var(--fr-line-2); }
      .av2 .fr-act .fr-prompt {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-size: 1.25rem;
        line-height: 1.25;
        color: var(--fr-ink);
      }
      .av2 .fr-act .fr-prompt-en {
        margin: -4px 0 0;
        font-size: 0.8125rem;
        color: var(--fr-muted);
      }
      /* the server's "because" line: one small graphite note, never a second prompt */
      .av2 .fr-act .fr-prompt-note {
        margin: -4px 0 0;
        font-size: 0.8125rem;
        line-height: 1.4;
        color: var(--fr-muted);
      }
      /* the illustrated-page edition's composed page keeps its own ratio */
      .av2 .fr-plate.is-page { aspect-ratio: auto; max-block-size: none; background: var(--fr-card); }
      .av2 .fr-plate.is-page img { height: auto; object-fit: contain; }
      .av2 .fr-options {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      /* the design's option card: 2px edge, 16px radius, Garamond italic,
         0 3px 0 press, selected = blue edge + blue dot */
      .av2 .fr-option {
        min-height: max(44px, 3.5rem);
        padding: 12px 18px;
        border: 2px solid var(--fr-line-2);
        border-radius: var(--av2-r-button);
        background: var(--fr-card);
        color: var(--fr-ink);
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: var(--av2-t-option);
        line-height: 1.3;
        text-align: left;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        box-shadow: 0 3px 0 var(--fr-line-2);
        transition: transform var(--fr-press), box-shadow var(--fr-press), background 0.15s, border-color 0.15s;
        overflow-wrap: anywhere;
      }
      .av2 .fr-option .dot {
        width: 22px;
        height: 22px;
        border-radius: 999px;
        background: transparent;
        flex: none;
      }
      .av2 .fr-option[aria-pressed='true'] {
        border-color: var(--fr-blue);
        box-shadow: 0 3px 0 var(--fr-blue);
      }
      .av2 .fr-option[aria-pressed='true'] .dot { background: var(--fr-blue); }
      .av2 .fr-option:not(:disabled):active { transform: translateY(3px); box-shadow: 0 0 0 transparent; }
      /* a locked option keeps its label legible: the affordance goes, not the text */
      .av2 .fr-option:disabled { cursor: default; box-shadow: none; opacity: 1; color: var(--fr-ink); }

      .av2 .fr-field {
        width: 100%;
        min-height: 3.5rem;
        border: 2px solid transparent;
        border-radius: var(--av2-r-button);
        background: var(--fr-card);
        color: var(--fr-ink);
        font-family: var(--fr-sans);
        font-size: var(--av2-t-body-lg); /* never below 16px: iOS zooms */
        line-height: 1.45;
        padding: 14px 16px;
        resize: vertical;
      }
      .av2 .fr-field::placeholder { color: var(--fr-muted); }
      .av2 .fr-field:focus { border-color: var(--fr-blue); outline: 0; }
      .av2 .fr-field:focus-visible { outline: 0; border-color: var(--fr-blue); }

      .av2 .fr-feedback {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        margin: 0;
        font-size: 0.875rem;
        line-height: 1.45;
        color: var(--fr-ink-2);
        animation: av2-pop 0.3s;
      }
      .av2 .fr-feedback .tok {
        width: 30px;
        height: 30px;
        flex: none;
        border-radius: 999px;
        display: grid;
        place-items: center;
        background: var(--fr-green);
        color: var(--fr-on-green);
      }
      .av2 .fr-feedback.is-branch .tok { background: var(--fr-blue); color: var(--fr-story-fg); }
      .av2 .fr-feedback.is-wrong .tok { background: var(--fr-red); color: var(--fr-on-red); }
      .av2 .fr-feedback b {
        display: block;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: var(--av2-t-option);
        line-height: 1.15;
        color: var(--fr-green);
      }
      .av2 .fr-feedback.is-branch b { color: var(--fr-blue); }
      .av2 .fr-feedback.is-wrong b { color: var(--fr-red-shadow); }

      /* ---- buttons ---- */
      .av2 .fr-btn {
        min-height: max(44px, 3rem);
        border: 0;
        border-radius: var(--av2-r-button);
        padding: 0.5rem 18px;
        font-family: var(--fr-sans);
        font-size: var(--av2-t-body-lg);
        font-weight: 700;
        line-height: 1.25;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        background: var(--fr-card);
        color: var(--fr-ink);
        text-decoration: none;
        transition: transform var(--fr-press), box-shadow var(--fr-press), background 0.2s;
        overflow-wrap: anywhere;
      }
      /* disabled dims the face, never the label */
      .av2 .fr-btn:disabled { cursor: not-allowed; background: var(--fr-line); color: var(--fr-ink-2); box-shadow: none; }
      /* secondary press: 4px, like every paper-faced row in the design */
      .av2 .fr-btn[data-press='3d'] { box-shadow: 0 var(--av2-press-md) 0 var(--fr-line-2); }
      .av2 .fr-btn[data-press='3d']:active:not(:disabled) { transform: translateY(var(--av2-press-md)); box-shadow: 0 0 0 transparent; }
      /* the single tactile primary: the design's 56px / 17px red action */
      .av2 .fr-btn.is-action {
        min-height: max(44px, 3.5rem);
        background: var(--fr-red);
        color: var(--fr-on-red);
        font-size: var(--av2-t-action);
      }
      .av2 .fr-btn.is-action:disabled { background: var(--fr-line); color: var(--fr-ink-2); }
      .av2 .fr-btn.is-action[data-press='3d'] { box-shadow: 0 var(--av2-press) 0 var(--fr-red-shadow); }
      .av2 .fr-btn.is-action[data-press='3d']:active:not(:disabled) { transform: translateY(var(--av2-press)); }
      .av2 .fr-btn.is-quiet { background: transparent; color: var(--fr-ink-2); font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }
      .av2 .fr-btn .av2-btn__spinner { flex: none; }
      .av2 .fr-btn:focus-visible,
      .av2 .fr-icon-btn:focus-visible,
      .av2 .fr-chip:focus-visible,
      .av2 .fr-option:focus-visible,
      .av2 .fr-dot:focus-visible,
      .av2 .fr-row:focus-visible,
      .av2 .fr-sheet-close:focus-visible {
        outline: 3px solid var(--fr-focus);
        outline-offset: 2px;
      }

      /* ---- foot navigation: previous · shape tokens · next ---- */
      .av2 .fr-nav {
        position: sticky;
        bottom: 0;
        z-index: 2;
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 18px;
        padding: 10px 0 max(14px, env(safe-area-inset-bottom, 0px));
        background: linear-gradient(to bottom, transparent, var(--fr-paper) 18%);
      }
      .av2 .fr-nav-row {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .av2 .fr-nav-row .fr-btn { flex: 0 0 auto; }
      .av2 .fr-nav-row .fr-prev { width: 3rem; padding: 0; }
      .av2 .fr-nav-row .fr-next { flex: 1 1 auto; min-width: 0; }
      .av2 .fr-dots {
        list-style: none;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0;
        margin: 0;
        padding: 0;
        overflow-x: auto;
        overscroll-behavior-x: contain;
        scrollbar-width: none;
        max-width: 100%;
      }
      .av2 .fr-dots::-webkit-scrollbar { display: none; }
      /* 44×44 so every jump target meets the touch minimum; the strip scrolls
         rather than shrinking them when an episode has many panels. */
      .av2 .fr-dot {
        width: 44px;
        height: 44px;
        border: 0;
        background: transparent;
        display: grid;
        place-items: center;
        cursor: pointer;
        flex: none;
        padding: 0;
      }
      .av2 .fr-dot .glyph {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--fr-line-2);
        transition: background 0.2s, transform 0.2s;
      }
      /* Bauhaus vocabulary: ink square = read, blue circle = here,
         hollow = not yet, red triangle = the closing beat */
      .av2 .fr-dot[data-state='read'] .glyph { border-radius: 2px; background: var(--fr-ink); }
      .av2 .fr-dot[data-state='current'] .glyph { background: var(--fr-blue); transform: scale(1.5); }
      .av2 .fr-dot[data-kind='resolution'] .glyph {
        border-radius: 0;
        background: var(--fr-line-2);
        clip-path: polygon(50% 0, 100% 100%, 0 100%);
        width: 12px;
        height: 11px;
      }
      .av2 .fr-dot[data-kind='resolution'][data-state='read'] .glyph { background: var(--fr-ink); }
      .av2 .fr-dot[data-kind='resolution'][data-state='current'] .glyph { background: var(--fr-red); transform: scale(1.2); }

      /* ---- honest notices ---- */
      .av2 .fr-notice {
        border-radius: 18px;
        padding: 16px;
        margin: 0;
        background: var(--fr-card);
        display: flex;
        flex-direction: column;
        gap: 10px;
        color: var(--fr-ink);
      }
      .av2 .fr-notice.is-stale { border: 2px dashed var(--fr-line-2); background: transparent; }
      .av2 .fr-notice h2 {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: 1.375rem;
        line-height: 1.1;
      }
      .av2 .fr-notice p { margin: 0; font-size: 0.875rem; line-height: 1.5; color: var(--fr-ink-2); }

      .av2 .fr-sr {
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

      /* ---- bottom sheet — the app's one sheet spec ---- */
      .av2 .fr-sheet-root {
        position: fixed;
        inset: 0;
        z-index: 90;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
      }
      .av2 .fr-scrim {
        position: absolute;
        inset: 0;
        border: 0;
        padding: 0;
        background: rgba(20, 17, 13, 0.35);
        cursor: pointer;
        animation: av2-fade 0.2s;
      }
      .av2 .fr-sheet {
        position: relative;
        background: var(--fr-paper);
        color: var(--fr-ink);
        border-radius: var(--av2-r-sheet) var(--av2-r-sheet) 0 0;
        padding: 10px var(--av2-gutter) calc(24px + var(--av2-safe-bottom));
        max-height: 88vh;
        overflow-y: auto;
        animation: av2-rise 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
      }
      .av2 .fr-handle {
        width: 40px;
        height: 5px;
        border-radius: 3px;
        background: var(--fr-line-2);
        margin: 0 auto 18px;
      }
      .av2 .fr-sheet-head {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 12px;
      }
      .av2 .fr-sheet-head .lede { min-width: 0; }
      .av2 .fr-sheet-head .k {
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--fr-muted);
      }
      .av2 .fr-sheet-head h2 {
        margin: 3px 0 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: var(--av2-t-head);
        line-height: 1;
        overflow-wrap: anywhere;
      }
      .av2 .fr-sheet-close {
        flex: none;
        min-height: 44px;
        min-width: 44px;
        padding: 0 16px;
        border: 0;
        border-radius: 999px;
        background: var(--fr-card);
        color: var(--fr-ink);
        font-family: var(--fr-sans);
        font-size: 0.9375rem;
        font-weight: 700;
        cursor: pointer;
      }
      .av2 .fr-sheet-body {
        margin-top: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .av2 .fr-gloss {
        margin: 0;
        font-size: 1.0625rem;
        line-height: 1.45;
        color: var(--fr-ink);
      }
      .av2 .fr-quote {
        margin: 0;
        background: var(--fr-card);
        border-radius: 16px;
        padding: 14px 16px;
        border-left: 4px solid var(--fr-blue);
      }
      .av2 .fr-quote .fr-quote-k {
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--fr-muted);
        margin: 0 0 6px;
      }
      .av2 .fr-quote .fr-quote-fr {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-size: 1.125rem;
        line-height: 1.35;
        color: var(--fr-ink);
      }
      .av2 .fr-quote .fr-quote-en {
        margin: 6px 0 0;
        font-size: 0.875rem;
        color: var(--fr-muted);
      }
      .av2 .fr-sheet-note { margin: 0; font-size: 0.875rem; color: var(--fr-muted); line-height: 1.5; }

      /* ================= the season list ("Le feuilleton") =================
         Verbatim from the design's FEUILLETON artboard: kicker + one Garamond
         italic headline, a blue story hero with a paper-on-blue 3D press, then
         read episodes as paper rows with an ink "done" badge. */
      .av2.fr-page,
      .av2 .fr-page {
        width: 100%;
        max-width: 560px;
        margin: 0 auto;
        padding: 0 16px 28px;
        box-sizing: border-box;
        overflow-x: clip;
      }
      .av2 .fr-page-head { padding: calc(20px + env(safe-area-inset-top, 0px)) 0 0; }
      .av2 .fr-page-head .k { font-size: 0.8125rem; font-weight: 600; color: var(--fr-muted); }
      .av2 .fr-page-head h1 {
        margin: 3px 0 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: var(--av2-t-screen);
        line-height: 1;
        color: var(--fr-ink);
      }

      .av2 .fr-hero {
        margin-top: 18px;
        background: var(--fr-story-bg);
        color: var(--fr-story-fg);
        border-radius: var(--av2-r-hero);
        overflow: hidden;
      }
      .av2 .fr-hero .art {
        aspect-ratio: 16 / 9;
        display: grid;
        place-items: center;
        background: repeating-linear-gradient(
          135deg,
          var(--fr-story-bg) 0 8px,
          color-mix(in srgb, var(--fr-story-bg) 88%, var(--fr-story-fg)) 8px 16px
        );
        color: var(--fr-story-fg);
        font-size: 0.8125rem;
        font-weight: 600;
        text-align: center;
        padding: 12px;
      }
      .av2 .fr-hero .art img { width: 100%; height: 100%; object-fit: cover; display: block; }
      .av2 .fr-hero .body { padding: 16px 18px 18px; }
      .av2 .fr-hero .k { font-size: 0.75rem; font-weight: 700; opacity: 0.85; }
      .av2 .fr-hero h2 {
        margin: 6px 0 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 600;
        font-size: var(--av2-t-title);
        line-height: 1.1;
        color: inherit;
        text-wrap: pretty;
      }
      /* paper face on the blue card, 48px, 4px press — as drawn */
      .av2 .fr-hero .cta {
        margin-top: 14px;
        min-height: 48px;
        width: 100%;
        border: 0;
        border-radius: 14px;
        background: var(--fr-card);
        color: var(--fr-story-bg);
        font-family: var(--fr-sans);
        font-size: 0.9375rem;
        font-weight: 700;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        text-decoration: none;
        box-shadow: 0 var(--av2-press-md) 0 var(--fr-story-press);
        transition: transform var(--fr-press), box-shadow var(--fr-press);
      }
      .av2 .fr-hero .cta:active { transform: translateY(var(--av2-press-md)); box-shadow: 0 0 0 transparent; }
      .av2 .fr-hero .cta:focus-visible { outline: 3px solid var(--fr-card); outline-offset: 3px; }

      .av2 .fr-rows { display: flex; flex-direction: column; gap: 8px; padding: 18px 0 0; }
      .av2 .fr-row {
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 80px;
        background: var(--fr-card);
        border-radius: var(--av2-r-card);
        padding: 12px 14px;
        color: var(--fr-ink);
        text-decoration: none;
        transition: transform var(--fr-press);
      }
      .av2 .fr-row:active { transform: scale(0.985); }
      .av2 .fr-row .thumb {
        width: 56px;
        height: 56px;
        flex: none;
        border-radius: 12px;
        background: var(--fr-line);
        overflow: hidden;
      }
      .av2 .fr-row .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
      .av2 .fr-row .meta { flex: 1 1 auto; min-width: 0; }
      .av2 .fr-row .k { display: block; font-size: 0.75rem; font-weight: 700; color: var(--fr-muted); }
      .av2 .fr-row .t {
        display: block;
        margin-top: 2px;
        font-family: var(--fr-serif);
        font-style: italic;
        font-size: 1.125rem;
        line-height: 1.15;
        overflow-wrap: anywhere;
      }
      .av2 .fr-row .done {
        width: 26px;
        height: 26px;
        flex: none;
        border-radius: 6px;
        background: var(--fr-ink);
        color: var(--av2-on-ink);
        display: grid;
        place-items: center;
      }
      .av2 .fr-row .go { flex: none; color: var(--fr-muted); display: grid; place-items: center; }
      .av2 .fr-row.is-locked {
        background: transparent;
        border: 2px dashed var(--fr-line-2);
        color: var(--fr-muted);
      }
      .av2 .fr-row.is-locked .thumb { background: transparent; display: grid; place-items: center; }

      .av2 .fr-empty {
        margin-top: 18px;
        background: var(--fr-card);
        border-radius: var(--av2-r-episode);
        padding: 22px 20px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .av2 .fr-empty h2 {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: var(--av2-t-title);
        line-height: 1.1;
        color: var(--fr-ink);
      }
      .av2 .fr-empty p { margin: 0; font-size: 0.875rem; line-height: 1.5; color: var(--fr-ink-2); }

      .av2 .fr-skeleton { display: flex; flex-direction: column; gap: 8px; padding: 18px 0 0; }
      .av2 .fr-skeleton i {
        display: block;
        height: 80px;
        border-radius: var(--av2-r-card);
        background: linear-gradient(90deg, var(--fr-line) 25%, var(--fr-card) 37%, var(--fr-line) 63%);
        background-size: 400% 100%;
        animation: av2-shimmer 1.4s ease infinite;
      }

      @media (prefers-reduced-motion: reduce) {
        .av2 .fr-reader .fr-btn:active,
        .av2 .fr-reader .fr-option:active,
        .av2 .fr-page .fr-row:active,
        .av2 .fr-page .cta:active { transform: none; }
      }

      @media (min-width: 720px) {
        .av2 .fr-reader, .av2.fr-page, .av2 .fr-page { max-width: 620px; padding-left: 24px; padding-right: 24px; }
        .av2 .fr-plate { max-block-size: min(52vh, 460px); }
      }
    `}</style>
  );
}

export default FeuilletonReaderStyles;
