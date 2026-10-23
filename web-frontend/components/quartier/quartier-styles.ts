/**
 * Le Quartier · the screen's styles, as a string the screen prints into a <style> tag (so the
 * standalone build carries them too). Every colour and face is an `--av2-*` token of
 * `styles/atelier-v2.css`, with the token's light value as the fallback: over a night street the
 * cards are the Feuilleton's cards, paper and ink, whatever the phone's theme.
 */
export const QUARTIER_CSS = `
.qz {
  --qz-paper: var(--av2-paper, #f1ece1);
  --qz-card: #f8f3e8;
  --qz-line: #e8e0cf;
  --qz-line-2: #d8cdb6;
  --qz-ink: #14110d;
  --qz-ink-2: #4a4538;
  --qz-muted: #6f6857;
  --qz-red: #d8321a;
  --qz-red-deep: #9c2411;
  --qz-blue: #1d3a8a;
  --qz-yellow: #f3c318;
  --qz-green: #2c6a5d;
  --qz-serif: 'AtelierSerif', 'EB Garamond', Georgia, 'Times New Roman', serif;
  --qz-sans: 'AtelierSans', 'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --qz-top: env(safe-area-inset-top, 0px);
  --qz-bottom: env(safe-area-inset-bottom, 0px);
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: #0d1430;
  color: var(--qz-ink);
  font-family: var(--qz-sans);
  -webkit-user-select: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  touch-action: none;
}
.qz [data-char='gus'] { --qz-accent: #8a2f2a; }
.qz [data-char='marin'] { --qz-accent: #2c6a5d; }
.qz [data-char='lila'] { --qz-accent: #c2890f; }
.qz [data-char='margaux'] { --qz-accent: #a85d24; }
.qz [data-char='camille'] { --qz-accent: #5b5346; }
.qz [data-char='toi'] { --qz-accent: #14110d; }
.qz-canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; touch-action: none; }
.qz :where(button) { font: inherit; color: inherit; -webkit-tap-highlight-color: transparent; }

/* ---- the bar along the top ---------------------------------------------------------------- */
.qz-top {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  padding: calc(var(--qz-top) + 10px) 12px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}
.qz-top > * { pointer-events: auto; }
.qz-round {
  width: 38px;
  height: 38px;
  flex: none;
  border-radius: 999px;
  border: 0;
  background: color-mix(in srgb, var(--qz-card) 88%, transparent);
  color: var(--qz-ink);
  display: grid;
  place-items: center;
  box-shadow: 0 2px 0 var(--qz-line-2);
  cursor: pointer;
}
.qz-round:active { transform: translateY(2px); box-shadow: 0 0 0 var(--qz-line-2); }
.qz-round[aria-pressed='false'] { opacity: 0.62; }
.qz-round svg { width: 18px; height: 18px; }
.qz-round .qz-lang { font-size: 11px; font-weight: 700; letter-spacing: 0.04em; }
.qz-title {
  flex: 1;
  min-width: 0;
  text-align: center;
  color: #f8f3e8;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.qz-title em { font-family: var(--qz-serif); font-size: 15px; font-weight: 500; letter-spacing: 0; }
.qz-progress {
  position: absolute;
  left: 16px;
  right: 16px;
  top: calc(var(--qz-top) + 54px);
  height: 3px;
  border-radius: 3px;
  background: rgba(248, 243, 232, 0.22);
  overflow: hidden;
  pointer-events: none;
}
.qz-progress i { display: block; height: 100%; background: var(--qz-yellow); transition: width 600ms ease; }

/* ---- the caption: a box of the comic's own, top of the frame ------------------------------- */
.qz-caption {
  position: absolute;
  left: 14px;
  right: 14px;
  top: calc(var(--qz-top) + 68px);
  margin: 0 auto;
  max-width: 420px;
  border: 0;
  text-align: left;
  background: var(--qz-yellow);
  color: var(--qz-ink);
  padding: 12px 14px 12px;
  border-radius: 4px;
  box-shadow: 3px 3px 0 var(--qz-ink);
  font-family: var(--qz-serif);
  font-style: italic;
  font-size: 18px;
  line-height: 1.35;
  cursor: pointer;
  animation: qz-in 260ms ease both;
}
.qz-caption small { display: block; margin-top: 6px; font-family: var(--qz-sans); font-style: normal; font-size: 13px; line-height: 1.4; color: var(--qz-ink-2); }

/* ---- a line: the reader's speech card, at the bottom ---------------------------------------- */
.qz-speech {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: calc(var(--qz-bottom) + 18px);
  margin: 0 auto;
  max-width: 440px;
  border: 0;
  text-align: left;
  background: var(--qz-card);
  border-radius: 18px;
  padding: 14px 16px 14px;
  border-left: 5px solid var(--qz-accent);
  box-shadow: 0 10px 30px rgba(10, 12, 30, 0.35), 0 2px 0 var(--qz-line-2);
  cursor: pointer;
  animation: qz-in 220ms ease both;
}
.qz-speaker { display: flex; align-items: center; gap: 8px; margin: 0 0 6px; font-size: 12px; font-weight: 700; letter-spacing: 0.03em; color: var(--qz-accent); text-transform: uppercase; }
.qz-speaker i { width: 10px; height: 10px; border-radius: 999px; background: var(--qz-accent); flex: none; }
.qz-direction { font-family: var(--qz-serif); font-style: italic; font-weight: 400; text-transform: none; letter-spacing: 0; color: var(--qz-muted); font-size: 14px; }
.qz-line { margin: 0; font-size: 17px; line-height: 1.45; color: var(--qz-ink); }
.qz-native { margin: 5px 0 0; font-size: 14px; line-height: 1.4; color: var(--qz-muted); }
.qz-more { position: absolute; right: 14px; bottom: 10px; width: 8px; height: 8px; border-right: 2px solid var(--qz-muted); border-bottom: 2px solid var(--qz-muted); transform: rotate(-45deg); animation: qz-nudge 1.4s ease-in-out infinite; }

/* ---- your balloon --------------------------------------------------------------------------- */
.qz-you {
  position: absolute;
  right: 16px;
  bottom: calc(var(--qz-bottom) + 30px);
  max-width: 76%;
  background: var(--qz-card);
  border: 2px solid var(--qz-ink);
  border-radius: 20px 20px 4px 20px;
  padding: 10px 14px;
  font-size: 17px;
  line-height: 1.4;
  animation: qz-in 200ms ease both;
}
.qz-you b { display: block; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--qz-muted); margin-bottom: 2px; }

/* ---- where to go ----------------------------------------------------------------------------- */
.qz-goal {
  position: absolute;
  left: 50%;
  bottom: calc(var(--qz-bottom) + 22px);
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  animation: qz-in 260ms ease both;
  width: max-content;
  max-width: calc(100% - 150px);
}
.qz-goal-label {
  background: var(--qz-card);
  border-radius: 999px;
  padding: 8px 14px;
  font-family: var(--qz-serif);
  font-style: italic;
  font-size: 18px;
  box-shadow: 0 2px 0 var(--qz-line-2);
  text-align: center;
}
.qz-goal-label small { display: block; font-family: var(--qz-sans); font-style: normal; font-size: 12px; color: var(--qz-muted); }
.qz-goal-actions { display: flex; gap: 8px; align-items: center; }
.qz-primary {
  border: 0;
  background: var(--qz-red);
  color: #f8f3e8;
  border-radius: 999px;
  padding: 11px 18px;
  font-weight: 700;
  font-size: 15px;
  box-shadow: 0 3px 0 var(--qz-red-deep);
  cursor: pointer;
}
.qz-primary:active { transform: translateY(3px); box-shadow: 0 0 0 var(--qz-red-deep); }
.qz-primary:disabled { opacity: 0.45; }
.qz-quiet {
  border: 0;
  background: color-mix(in srgb, var(--qz-card) 82%, transparent);
  border-radius: 999px;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--qz-ink-2);
  cursor: pointer;
}

/* ---- the thumb stick ------------------------------------------------------------------------ */
.qz-stick {
  position: absolute;
  left: 18px;
  bottom: calc(var(--qz-bottom) + 22px);
  width: 112px;
  height: 112px;
  border-radius: 999px;
  background: rgba(248, 243, 232, 0.16);
  border: 1.5px solid rgba(248, 243, 232, 0.5);
  touch-action: none;
}
.qz-stick i {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 46px;
  height: 46px;
  margin: -23px 0 0 -23px;
  border-radius: 999px;
  background: var(--qz-card);
  box-shadow: 0 2px 0 var(--qz-line-2);
}

/* ---- the answer sheet ------------------------------------------------------------------------ */
.qz-sheet {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--qz-paper);
  border-radius: 22px 22px 0 0;
  padding: 10px 16px calc(var(--qz-bottom) + 14px);
  box-shadow: 0 -10px 30px rgba(10, 12, 30, 0.35);
  animation: qz-up 280ms ease both;
  max-width: 560px;
  margin: 0 auto;
}
.qz-sheet::before { content: ''; display: block; width: 38px; height: 4px; border-radius: 4px; background: var(--qz-line-2); margin: 0 auto 10px; }
.qz-ask { margin: 0 0 4px; font-size: 12px; font-weight: 700; color: var(--qz-accent); text-transform: uppercase; letter-spacing: 0.03em; }
.qz-task { margin: 0; font-family: var(--qz-serif); font-style: italic; font-size: 19px; line-height: 1.3; }
.qz-task-native { margin: 4px 0 0; font-size: 13px; color: var(--qz-muted); }
.qz-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.qz-chip {
  border: 1.5px solid var(--qz-line-2);
  background: var(--qz-card);
  border-radius: 14px;
  padding: 8px 12px;
  font-size: 14px;
  line-height: 1.3;
  text-align: left;
  cursor: pointer;
}
.qz-chip:active { background: var(--qz-line); }
.qz-write { display: flex; gap: 8px; align-items: center; }
.qz-write input {
  flex: 1;
  min-width: 0;
  border: 2px solid var(--qz-ink);
  border-radius: 999px;
  padding: 12px 16px;
  font: inherit;
  font-size: 17px;
  background: var(--qz-card);
  color: var(--qz-ink);
  outline: none;
  -webkit-user-select: text;
  user-select: text;
}
.qz-write input:focus { box-shadow: 0 0 0 3px color-mix(in srgb, var(--qz-blue) 35%, transparent); }
.qz-send { width: 48px; height: 48px; border-radius: 999px; padding: 0; display: grid; place-items: center; }
.qz-send svg { width: 20px; height: 20px; }

/* ---- a silent panel: the frame narrows ------------------------------------------------------ */
.qz-letterbox::before,
.qz-letterbox::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  height: 11%;
  background: #0b0a08;
  animation: qz-bars 500ms ease both;
  pointer-events: none;
}
.qz-letterbox::before { top: 0; }
.qz-letterbox::after { bottom: 0; }
.qz-hint {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(var(--qz-bottom) + 14px);
  text-align: center;
  color: rgba(248, 243, 232, 0.8);
  font-size: 12px;
  letter-spacing: 0.04em;
  pointer-events: none;
  animation: qz-in 400ms 1.2s ease both;
}

/* ---- cards over the whole frame: loading, title, end ---------------------------------------- */
.qz-cover {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  padding: calc(var(--qz-top) + 24px) 24px calc(var(--qz-bottom) + 24px);
  text-align: center;
}
.qz-cover--paper { background: var(--qz-paper); }
.qz-cover--night { background: linear-gradient(180deg, rgba(8, 12, 34, 0.25) 0%, rgba(8, 12, 34, 0.72) 70%); }
.qz-card {
  width: 100%;
  max-width: 360px;
  background: var(--qz-card);
  border-radius: 22px;
  padding: 26px 22px 22px;
  box-shadow: 0 16px 40px rgba(5, 8, 24, 0.45), 0 3px 0 var(--qz-line-2);
  animation: qz-in 320ms ease both;
}
.qz-kicker { margin: 0; font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--qz-red); }
.qz-h { margin: 6px 0 4px; font-family: var(--qz-serif); font-style: italic; font-weight: 500; font-size: 34px; line-height: 1.05; }
.qz-date { margin: 0 0 14px; font-family: var(--qz-serif); font-style: italic; color: var(--qz-muted); font-size: 17px; }
.qz-cando { margin: 0 0 18px; font-size: 14px; line-height: 1.45; color: var(--qz-ink-2); }
.qz-card .qz-primary { width: 100%; padding: 14px 18px; font-size: 16px; }
.qz-card .qz-quiet { margin-top: 10px; width: 100%; background: transparent; }
.qz-howto { margin: 14px 0 0; font-size: 12px; color: var(--qz-muted); line-height: 1.45; }
.qz-bar { height: 4px; border-radius: 4px; background: var(--qz-line); overflow: hidden; margin: 16px 0 8px; }
.qz-bar i { display: block; height: 100%; background: var(--qz-red); transition: width 200ms ease; }
.qz-loading-label { font-family: var(--qz-serif); font-style: italic; color: var(--qz-muted); font-size: 16px; margin: 0; }
.qz-met {
  position: absolute;
  left: 50%;
  top: calc(var(--qz-top) + 70px);
  transform: translateX(-50%);
  background: var(--qz-card);
  border-radius: 999px;
  padding: 6px 14px;
  font-weight: 700;
  font-size: 13px;
  color: var(--qz-accent);
  box-shadow: 0 2px 0 var(--qz-line-2);
  animation: qz-in 200ms ease both;
  pointer-events: none;
}
.qz-stats {
  position: absolute;
  right: 10px;
  top: calc(var(--qz-top) + 64px);
  font: 11px/1.35 ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #f8f3e8;
  background: rgba(0, 0, 0, 0.45);
  padding: 4px 6px;
  border-radius: 6px;
  pointer-events: none;
  white-space: pre;
}

@keyframes qz-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@keyframes qz-up { from { transform: translateY(100%); } to { transform: none; } }
@keyframes qz-bars { from { transform: scaleY(0); } to { transform: none; } }
@keyframes qz-nudge { 0%, 100% { transform: translate(0, 0) rotate(-45deg); } 50% { transform: translate(3px, 0) rotate(-45deg); } }
.qz-goal, .qz-you { transform-origin: bottom center; }
.qz-goal { animation-name: qz-goal-in; }
@keyframes qz-goal-in { from { opacity: 0; transform: translate(-50%, 6px); } to { opacity: 1; transform: translate(-50%, 0); } }
@media (prefers-reduced-motion: reduce) {
  .qz *, .qz *::before, .qz *::after { animation-duration: 1ms !important; animation-delay: 0ms !important; transition-duration: 1ms !important; }
}
`;
