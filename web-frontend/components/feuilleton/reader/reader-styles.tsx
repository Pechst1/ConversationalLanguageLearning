/* Scoped styles for the Feuilleton reader.
 *
 * Derived from the Claude overhaul system (Atelier App.dc.html), not from the
 * `ref/*.png` renders — those are board 0, "current build, recreated from
 * source", i.e. the before. The system, verbatim: two fonts only, Garamond
 * italic for the one headline per screen and Instrument Sans for everything
 * else, sentence case, no tracked caps; rounded 16–24px surfaces instead of
 * ruled boxes; the Bauhaus mark's four shapes as progress tokens; one tactile
 * 3D-press button per screen; red = action, blue = story/info, yellow = reward,
 * ink = done.
 *
 * Everything is prefixed `.fr-` and lives under `.fr-reader`, so nothing here
 * can reach the existing `.fe-*` supplement primitives or subagent A's
 * `components/atelier-v2/ui`. When A's tokens land these locals should be
 * deleted in favour of theirs — see the handoff.
 */

export function FeuilletonReaderStyles() {
  return (
    <style jsx global>{`
      .fr-reader,
      .fr-page,
      .fr-sheet-root {
        /* grounds and lines — the design's exact values, via the app tokens so
           the learner's dark/light setting still works */
        --fr-paper: var(--app-paper, #f1ece1);
        --fr-card: var(--app-sheet, #f8f3e8);
        --fr-line: var(--app-paper-2, #e8e0cf);
        --fr-line-2: var(--app-paper-3, #d8cdb6);
        --fr-ink: var(--app-ink, #14110d);
        --fr-ink-2: var(--app-ink-2, #4a4538);
        --fr-muted: var(--app-ink-3, #6f6857);
        --fr-red: var(--app-red, #d8321a);
        --fr-red-shadow: #9c2411;
        --fr-blue: var(--app-blue, #1d3a8a);
        /* the Feuilleton's own story surface: a filled blue card with paper
           text. Kept off --app-blue because the dark theme lightens that token
           and paper-on-light-blue would not carry the text. */
        --fr-story-bg: #1d3a8a;
        --fr-story-fg: #f8f3e8;
        --fr-story-press: #cfc4ad;
        --fr-yellow: var(--app-yellow, #f3c318);
        --fr-green: #2c6a5d;
        /* character accents — the serial world bible, one system with the UI */
        --char-romy: #1d3a8a;
        --char-marin: #2c6a5d;
        --char-lila: #c2890f;
        --char-gus: #8a2f2a;
        --char-margaux: #a85d24;
        --char-marchand: #5b5346;
        --char-toi: var(--fr-ink);
        --fr-accent: var(--fr-muted);
        /* two fonts only */
        --fr-sans: 'Instrument Sans', var(--app-grotesk, 'Inter'), system-ui, sans-serif;
        --fr-serif: var(--app-serif, 'EB Garamond'), Georgia, serif;
        --fr-press: 0.08s ease;
        font-family: var(--fr-sans);
        color: var(--fr-ink);
      }
      :root[data-theme='dark'] .fr-reader,
      :root[data-theme='dark'] .fr-page,
      :root[data-theme='dark'] .fr-sheet-root {
        --fr-story-bg: #1b2a5c;
        --fr-story-fg: #f5efe1;
        --fr-story-press: #10193a;
        --char-romy: #7c9bff;
        --char-marin: #5fb3a1;
        --char-lila: #e0ad3e;
        --char-gus: #d97a72;
        --char-margaux: #d68f52;
        --char-marchand: #a89b86;
        --fr-red-shadow: #7d1d0d;
      }

      .fr-reader [data-char='romy'] { --fr-accent: var(--char-romy); }
      .fr-reader [data-char='marin'] { --fr-accent: var(--char-marin); }
      .fr-reader [data-char='lila'] { --fr-accent: var(--char-lila); }
      .fr-reader [data-char='gus'] { --fr-accent: var(--char-gus); }
      .fr-reader [data-char='margaux'] { --fr-accent: var(--char-margaux); }
      .fr-reader [data-char='marchand'] { --fr-accent: var(--char-marchand); }
      .fr-reader [data-char='toi'] { --fr-accent: var(--char-toi); }

      .fr-reader {
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
      .fr-reader *,
      .fr-sheet-root * { box-sizing: border-box; }

      /* ---- top bar: quit · story progress rail · counter ---- */
      .fr-bar {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 0 14px;
      }
      .fr-icon-btn {
        width: 44px;
        height: 44px;
        flex: none;
        border: 0;
        border-radius: 999px;
        background: var(--fr-card);
        color: var(--fr-ink);
        display: grid;
        place-items: center;
        cursor: pointer;
        transition: transform var(--fr-press);
      }
      .fr-icon-btn:active { transform: scale(0.94); }
      .fr-rail {
        flex: 1 1 auto;
        min-width: 0;
        height: 14px;
        border-radius: 7px;
        background: var(--fr-line);
        overflow: hidden;
      }
      .fr-rail i {
        display: block;
        height: 100%;
        border-radius: 7px;
        background: var(--fr-blue);
        transition: width 0.35s cubic-bezier(0.2, 0.8, 0.2, 1);
      }
      .fr-count {
        flex: none;
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--fr-muted);
        font-variant-numeric: tabular-nums;
      }

      /* ---- running head: eyebrow + the ONE Garamond italic headline ---- */
      .fr-head { padding: 2px 0 14px; }
      .fr-eyebrow {
        margin: 0;
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--fr-muted);
      }
      .fr-title {
        margin: 3px 0 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: clamp(1.625rem, 7.6vw, 2rem);
        line-height: 1.05;
        color: var(--fr-ink);
        text-wrap: pretty;
      }
      .fr-previously {
        margin: 8px 0 0;
        font-size: 0.8125rem;
        line-height: 1.45;
        color: var(--fr-muted);
      }

      /* ---- the stage: one panel at a time ---- */
      .fr-stage {
        display: flex;
        flex-direction: column;
        gap: 14px;
        touch-action: pan-y;
      }
      .fr-stage:focus-visible { outline: 3px solid var(--fr-blue); outline-offset: 6px; border-radius: 24px; }

      .fr-plate {
        position: relative;
        margin: 0;
        border-radius: 24px;
        overflow: hidden;
        background: var(--fr-blue);
        aspect-ratio: 1 / 1;
        max-block-size: min(44vh, 400px);
      }
      .fr-plate img {
        display: block;
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      .fr-plate.is-printing,
      .fr-plate.is-missing {
        display: grid;
        place-items: center;
        text-align: center;
        padding: 20px;
        aspect-ratio: 16 / 9;
      }
      .fr-plate.is-printing {
        background: repeating-linear-gradient(135deg, #27479a 0 8px, #2b4da4 8px 16px);
        color: #f8f3e8;
      }
      .fr-plate.is-missing {
        background: transparent;
        border: 2px dashed var(--fr-line-2);
        color: var(--fr-muted);
      }
      .fr-plate .fr-plate-note {
        font-size: 0.8125rem;
        font-weight: 600;
        max-width: 30ch;
        line-height: 1.4;
      }
      .fr-plate.is-printing .fr-plate-note { opacity: 0.92; }

      /* ---- speech: accent identifies the speaker before the name is read ---- */
      .fr-speech {
        background: var(--fr-card);
        border-radius: 18px;
        padding: 14px 16px;
        border-left: 4px solid var(--fr-accent);
      }
      .fr-speaker {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 0 6px;
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--fr-accent);
      }
      .fr-speaker .glyph {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--fr-accent);
        flex: none;
      }
      .fr-line {
        margin: 0;
        font-size: 1rem;
        line-height: 1.5;
        color: var(--fr-ink);
      }
      .fr-line + .fr-speaker { margin-top: 12px; }
      .fr-line-en {
        margin: 4px 0 0;
        font-size: 0.875rem;
        line-height: 1.45;
        color: var(--fr-muted);
      }
      .fr-caption {
        margin: 0;
        font-size: 0.875rem;
        line-height: 1.5;
        color: var(--fr-ink-2);
        padding: 0 2px;
      }

      /* tappable word */
      .fr-word {
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
      .fr-word:hover { background: color-mix(in srgb, var(--fr-yellow) 34%, transparent); }
      .fr-word:focus-visible { outline: 2px solid var(--fr-blue); outline-offset: 2px; }

      .fr-tools {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }
      .fr-chip {
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
        font-weight: 600;
        cursor: pointer;
        transition: transform var(--fr-press);
      }
      .fr-chip:active { transform: scale(0.96); }
      .fr-chip .sq {
        width: 8px;
        height: 8px;
        border-radius: 2px;
        background: var(--fr-yellow);
        flex: none;
      }
      .fr-chip[aria-pressed='true'],
      .fr-chip[data-active='true'] { background: var(--fr-ink); color: var(--fr-card); }

      /* ---- browse vs act: a revisit is stated, never re-played ---- */
      .fr-state {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--fr-muted);
      }
      .fr-state .tok {
        width: 18px;
        height: 18px;
        border-radius: 5px;
        background: var(--fr-ink);
        display: grid;
        place-items: center;
        flex: none;
      }
      .fr-state.is-live { color: var(--fr-red); }
      .fr-state.is-live .tok {
        border-radius: 999px;
        background: var(--fr-red);
      }

      /* ---- the learner's action ---- */
      .fr-act {
        background: var(--fr-card);
        border-radius: 18px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .fr-act.is-read { background: transparent; border: 1px solid var(--fr-line); }
      .fr-act .fr-prompt {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-size: 1.25rem;
        line-height: 1.25;
        color: var(--fr-ink);
      }
      .fr-act .fr-prompt-en {
        margin: -4px 0 0;
        font-size: 0.8125rem;
        color: var(--fr-muted);
      }
      .fr-options {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .fr-option {
        min-height: 56px;
        padding: 12px 16px;
        border: 2px solid var(--fr-line-2);
        border-radius: 16px;
        background: var(--fr-paper);
        color: var(--fr-ink);
        font-family: var(--fr-serif);
        font-style: italic;
        font-size: 1.125rem;
        line-height: 1.25;
        text-align: left;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        box-shadow: 0 3px 0 var(--fr-line-2);
        transition: transform var(--fr-press), box-shadow var(--fr-press), background 0.15s;
      }
      .fr-option .dot {
        width: 22px;
        height: 22px;
        border-radius: 999px;
        background: var(--fr-line);
        flex: none;
      }
      .fr-option[aria-pressed='true'] {
        border-color: var(--fr-blue);
        box-shadow: 0 3px 0 var(--fr-blue);
        background: color-mix(in srgb, var(--fr-blue) 8%, var(--fr-paper));
      }
      .fr-option[aria-pressed='true'] .dot { background: var(--fr-blue); }
      .fr-option:active { transform: translateY(3px); box-shadow: 0 0 0 transparent; }
      .fr-option:disabled { cursor: default; opacity: 0.75; box-shadow: none; }
      .fr-option:disabled:active { transform: none; }

      .fr-field {
        width: 100%;
        min-height: 56px;
        border: 2px solid var(--fr-line-2);
        border-radius: 16px;
        background: var(--fr-paper);
        color: var(--fr-ink);
        font-family: var(--fr-sans);
        font-size: 1rem;
        line-height: 1.45;
        padding: 14px 16px;
        resize: vertical;
      }
      .fr-field:focus-visible { outline: 2px solid var(--fr-blue); outline-offset: 1px; border-color: var(--fr-blue); }

      .fr-feedback {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        margin: 0;
        font-size: 0.875rem;
        line-height: 1.45;
        color: var(--fr-ink-2);
      }
      .fr-feedback .tok {
        width: 26px;
        height: 26px;
        flex: none;
        border-radius: 999px;
        display: grid;
        place-items: center;
        background: var(--fr-green);
        color: var(--fr-card);
      }
      .fr-feedback.is-branch .tok { background: var(--fr-blue); }
      .fr-feedback.is-wrong .tok { background: var(--fr-red); }
      .fr-feedback b {
        display: block;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: 1.125rem;
        line-height: 1.1;
        color: var(--fr-ink);
      }

      /* ---- buttons ---- */
      .fr-btn {
        min-height: 48px;
        border: 0;
        border-radius: 16px;
        padding: 0 18px;
        font-family: var(--fr-sans);
        font-size: 0.9375rem;
        font-weight: 700;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        background: var(--fr-card);
        color: var(--fr-ink);
        transition: transform var(--fr-press), box-shadow var(--fr-press), background 0.2s;
      }
      .fr-btn:disabled { cursor: default; opacity: 0.55; }
      /* the single tactile 3D press on the screen */
      .fr-btn[data-press='3d'] { box-shadow: 0 5px 0 var(--fr-line-2); }
      .fr-btn[data-press='3d']:active:not(:disabled) { transform: translateY(5px); box-shadow: 0 0 0 transparent; }
      .fr-btn.is-action { background: var(--fr-red); color: #fff; }
      .fr-btn.is-action[data-press='3d'] { box-shadow: 0 5px 0 var(--fr-red-shadow); }
      .fr-btn.is-quiet { background: transparent; color: var(--fr-muted); font-weight: 600; }
      .fr-btn:focus-visible,
      .fr-icon-btn:focus-visible,
      .fr-chip:focus-visible,
      .fr-option:focus-visible,
      .fr-dot:focus-visible,
      .fr-sheet-close:focus-visible {
        outline: 3px solid var(--fr-blue);
        outline-offset: 2px;
      }

      /* ---- foot navigation: previous · shape tokens · next ---- */
      .fr-nav {
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
      .fr-nav-row {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .fr-nav-row .fr-btn { flex: 0 0 auto; }
      .fr-nav-row .fr-next { flex: 1 1 auto; min-width: 0; }
      .fr-dots {
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
      .fr-dots::-webkit-scrollbar { display: none; }
      /* 44×44 so every jump target meets the touch minimum; the strip scrolls
         rather than shrinking them when an episode has many panels. */
      .fr-dot {
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
      .fr-dot .glyph {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--fr-line-2);
        transition: background 0.2s, transform 0.2s;
      }
      /* Bauhaus vocabulary: ink square = read, blue circle = here,
         hollow = not yet, red triangle = the closing beat */
      .fr-dot[data-state='read'] .glyph { border-radius: 2px; background: var(--fr-ink); }
      .fr-dot[data-state='current'] .glyph { background: var(--fr-blue); transform: scale(1.5); }
      .fr-dot[data-kind='resolution'] .glyph {
        border-radius: 0;
        background: transparent;
        width: 0;
        height: 0;
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
        border-bottom: 11px solid var(--fr-line-2);
      }
      .fr-dot[data-kind='resolution'][data-state='read'] .glyph { border-bottom-color: var(--fr-ink); }
      .fr-dot[data-kind='resolution'][data-state='current'] .glyph { border-bottom-color: var(--fr-red); transform: scale(1.2); }

      /* ---- honest notices ---- */
      .fr-notice {
        border-radius: 18px;
        padding: 16px;
        background: var(--fr-card);
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .fr-notice.is-stale { border: 2px dashed var(--fr-line-2); background: transparent; }
      .fr-notice h2 {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: 1.375rem;
        line-height: 1.1;
      }
      .fr-notice p { margin: 0; font-size: 0.875rem; line-height: 1.5; color: var(--fr-ink-2); }

      .fr-sr {
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
      .fr-sheet-root {
        position: fixed;
        inset: 0;
        z-index: 90;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
      }
      .fr-scrim {
        position: absolute;
        inset: 0;
        border: 0;
        padding: 0;
        background: rgba(20, 17, 13, 0.35);
        cursor: pointer;
        animation: fr-fade 0.2s;
      }
      .fr-sheet {
        position: relative;
        background: var(--fr-paper);
        border-radius: 28px 28px 0 0;
        padding: 10px 20px max(24px, env(safe-area-inset-bottom, 0px));
        max-height: min(78vh, 620px);
        overflow-y: auto;
        animation: fr-rise 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
      }
      .fr-handle {
        width: 40px;
        height: 5px;
        border-radius: 3px;
        background: var(--fr-line-2);
        margin: 0 auto 18px;
      }
      .fr-sheet-head {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 12px;
      }
      .fr-sheet-head .lede { min-width: 0; }
      .fr-sheet-head .k {
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--fr-muted);
      }
      .fr-sheet-head h2 {
        margin: 3px 0 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: 1.875rem;
        line-height: 1;
        overflow-wrap: anywhere;
      }
      .fr-sheet-close {
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
        font-weight: 600;
        cursor: pointer;
      }
      .fr-sheet-body {
        margin-top: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .fr-gloss {
        margin: 0;
        font-size: 1.0625rem;
        line-height: 1.45;
        color: var(--fr-ink);
      }
      .fr-quote {
        margin: 0;
        background: var(--fr-card);
        border-radius: 16px;
        padding: 14px 16px;
        border-left: 4px solid var(--fr-blue);
      }
      .fr-quote .fr-quote-k {
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--fr-muted);
        margin: 0 0 6px;
      }
      .fr-quote .fr-quote-fr {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-size: 1.125rem;
        line-height: 1.35;
        color: var(--fr-ink);
      }
      .fr-quote .fr-quote-en {
        margin: 6px 0 0;
        font-size: 0.875rem;
        color: var(--fr-muted);
      }
      .fr-sheet-note { margin: 0; font-size: 0.875rem; color: var(--fr-muted); line-height: 1.5; }

      /* ================= the season list ("Le feuilleton") =================
         Verbatim from the design's FEUILLETON artboard: kicker + one Garamond
         italic headline, a blue story hero with a paper-on-blue 3D press, then
         read episodes as paper rows with an ink "done" badge. */
      .fr-page {
        width: 100%;
        max-width: 560px;
        margin: 0 auto;
        padding: 0 16px 28px;
        box-sizing: border-box;
        overflow-x: clip;
      }
      .fr-page *,
      .fr-page *::before,
      .fr-page *::after { box-sizing: border-box; }
      .fr-page-head { padding: 20px 0 0; }
      .fr-page-head .k { font-size: 0.8125rem; font-weight: 600; color: var(--fr-muted); }
      .fr-page-head h1 {
        margin: 3px 0 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: clamp(1.75rem, 8vw, 2rem);
        line-height: 1;
      }

      .fr-hero {
        margin-top: 18px;
        background: var(--fr-story-bg);
        color: var(--fr-story-fg);
        border-radius: 24px;
        overflow: hidden;
      }
      .fr-hero .art {
        aspect-ratio: 16 / 9;
        display: grid;
        place-items: center;
        background: repeating-linear-gradient(135deg, #27479a 0 8px, #2b4da4 8px 16px);
        color: var(--fr-story-fg);
        font-size: 0.8125rem;
        text-align: center;
        padding: 12px;
      }
      .fr-hero .art img { width: 100%; height: 100%; object-fit: cover; display: block; }
      .fr-hero .body { padding: 16px 18px 18px; }
      .fr-hero .k { font-size: 0.75rem; font-weight: 700; opacity: 0.85; }
      .fr-hero h2 {
        margin: 6px 0 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 600;
        font-size: 1.5rem;
        line-height: 1.1;
      }
      .fr-hero .cta {
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
        box-shadow: 0 4px 0 var(--fr-story-press);
        transition: transform var(--fr-press), box-shadow var(--fr-press);
      }
      .fr-hero .cta:active { transform: translateY(4px); box-shadow: 0 0 0 transparent; }
      .fr-hero .cta:focus-visible { outline: 3px solid var(--fr-card); outline-offset: 3px; }

      .fr-rows { display: flex; flex-direction: column; gap: 8px; padding: 18px 0 0; }
      .fr-row {
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 80px;
        background: var(--fr-card);
        border-radius: 16px;
        padding: 12px 14px;
        color: var(--fr-ink);
        text-decoration: none;
        transition: transform var(--fr-press);
      }
      .fr-row:active { transform: scale(0.98); }
      .fr-row:focus-visible { outline: 3px solid var(--fr-blue); outline-offset: 2px; }
      .fr-row .thumb {
        width: 56px;
        height: 56px;
        flex: none;
        border-radius: 12px;
        background: var(--fr-line);
        overflow: hidden;
      }
      .fr-row .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
      .fr-row .meta { flex: 1 1 auto; min-width: 0; }
      .fr-row .k { display: block; font-size: 0.75rem; font-weight: 700; color: var(--fr-muted); }
      .fr-row .t {
        display: block;
        margin-top: 2px;
        font-family: var(--fr-serif);
        font-style: italic;
        font-size: 1.125rem;
        line-height: 1.15;
        overflow-wrap: anywhere;
      }
      .fr-row .done {
        width: 26px;
        height: 26px;
        flex: none;
        border-radius: 6px;
        background: var(--fr-ink);
        display: grid;
        place-items: center;
      }
      .fr-row.is-locked {
        background: transparent;
        border: 2px dashed var(--fr-line-2);
        color: var(--fr-muted);
      }
      .fr-row.is-locked .thumb { background: transparent; display: grid; place-items: center; }

      .fr-empty {
        margin-top: 18px;
        background: var(--fr-card);
        border-radius: 22px;
        padding: 22px 20px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .fr-empty h2 {
        margin: 0;
        font-family: var(--fr-serif);
        font-style: italic;
        font-weight: 500;
        font-size: 1.5rem;
        line-height: 1.1;
      }
      .fr-empty p { margin: 0; font-size: 0.875rem; line-height: 1.5; color: var(--fr-ink-2); }

      .fr-skeleton { display: flex; flex-direction: column; gap: 8px; padding: 18px 0 0; }
      .fr-skeleton i {
        display: block;
        height: 80px;
        border-radius: 16px;
        background: var(--fr-card);
      }

      @keyframes fr-rise {
        from { transform: translateY(18px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
      }
      @keyframes fr-fade {
        from { opacity: 0; }
        to { opacity: 1; }
      }

      @media (prefers-reduced-motion: reduce) {
        .fr-reader *,
        .fr-page *,
        .fr-sheet-root * {
          animation-duration: 0.001ms !important;
          animation-iteration-count: 1 !important;
          transition-duration: 0.001ms !important;
        }
        .fr-reader .fr-btn:active,
        .fr-reader .fr-option:active,
        .fr-page .fr-row:active,
        .fr-page .cta:active { transform: none; }
      }

      @media (min-width: 720px) {
        .fr-reader, .fr-page { max-width: 620px; padding-left: 24px; padding-right: 24px; }
        .fr-plate { max-block-size: min(52vh, 460px); }
      }
    `}</style>
  );
}

export default FeuilletonReaderStyles;
