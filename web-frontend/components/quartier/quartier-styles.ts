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
.qz [data-char='passant'] { --qz-accent: #3d5a8c; }
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
  z-index: 10;
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
button.qz-you { font: inherit; font-size: 17px; color: var(--qz-ink); text-align: left; cursor: pointer; }
.qz-mend { display: block; margin-top: 6px; padding-top: 6px; border-top: 1.5px dashed var(--qz-line-2); font-size: 15px; }
.qz-mend s { color: var(--qz-red); text-decoration-thickness: 2px; }
.qz-mend small { display: block; margin-top: 3px; font-size: 12.5px; line-height: 1.4; color: var(--qz-muted); }
.qz-you .qz-more { right: 12px; bottom: 8px; }

/* ---- where to go ----------------------------------------------------------------------------- */
.qz-goal {
  position: absolute;
  /* centred in the room the thumb stick leaves on its right */
  left: calc(50% + 66px);
  bottom: calc(var(--qz-bottom) + 22px);
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  animation: qz-in 260ms ease both;
  width: max-content;
  max-width: calc(100% - 162px);
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
.qz-again { margin: 6px 0 0; font-size: 13px; font-weight: 700; color: var(--qz-red); }
.qz-help-hint { margin: 10px 0 0; padding: 8px 12px; border-left: 4px solid var(--qz-accent); background: var(--qz-card); border-radius: 0 12px 12px 0; font-size: 14px; line-height: 1.4; color: var(--qz-ink-2); }
.qz-chip--word { border-style: dashed; }
.qz-failed { margin: 8px 0; font-size: 13px; color: var(--qz-red); }
.qz-sheet .qz-write { margin-top: 12px; }
.qz-help { display: block; margin: 10px auto 0; background: transparent; text-decoration: underline; text-underline-offset: 3px; }
.qz-help:disabled { opacity: 0.45; }
.qz-aide { flex: none; padding: 9px 12px; background: var(--qz-line); }
.qz-dots { display: inline-flex; gap: 3px; }
.qz-dots i { width: 5px; height: 5px; border-radius: 999px; background: currentColor; animation: qz-dot 1s ease-in-out infinite; }
.qz-dots i:nth-child(2) { animation-delay: 0.15s; }
.qz-dots i:nth-child(3) { animation-delay: 0.3s; }
.qz-dots--ink { color: var(--qz-muted); padding: 6px 0; }
@keyframes qz-dot { 0%, 100% { opacity: 0.25; transform: translateY(0); } 50% { opacity: 1; transform: translateY(-2px); } }

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
  padding: calc(var(--qz-top) + 60px) 24px calc(var(--qz-bottom) + 24px);
  text-align: center;
  z-index: 5;
}
.qz-cover--paper { background: var(--qz-paper); }
.qz-cover--night { background: linear-gradient(180deg, rgba(8, 12, 34, 0.25) 0%, rgba(8, 12, 34, 0.72) 70%); }
.qz-cover--day { background: linear-gradient(180deg, rgba(20, 17, 13, 0.06) 0%, rgba(20, 17, 13, 0.55) 72%); }
.qz-cover .qz-ride { margin: 4px 0 0; font-family: var(--qz-serif); font-style: italic; font-size: 17px; color: var(--qz-ink-2); }
.qz-cover .qz-ride small { display: block; margin-top: 4px; font-family: inherit; font-style: normal; font-size: 13px; color: var(--qz-muted); }
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

/* ---- walking out of a scene ------------------------------------------------------------------- */
.qz-leave {
  height: 38px;
  flex: none;
  margin-right: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 999px;
  padding: 0 14px 0 11px;
  background: color-mix(in srgb, var(--qz-card) 88%, transparent);
  color: var(--qz-ink);
  font-weight: 700;
  font-size: 13px;
  box-shadow: 0 2px 0 var(--qz-line-2);
  cursor: pointer;
  animation: qz-in 260ms ease both;
}
.qz-leave svg { width: 17px; height: 17px; }
.qz-leave:active { transform: translateY(2px); box-shadow: none; }

/* ---- the moment before the bell: a caption with a way on ---------------------------------------- */
.qz-moment {
  position: absolute;
  left: 14px;
  right: 14px;
  top: calc(var(--qz-top) + 68px);
  margin: 0 auto;
  max-width: 420px;
  background: var(--qz-yellow);
  border-radius: 4px;
  box-shadow: 3px 3px 0 var(--qz-ink);
  padding: 12px 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  animation: qz-in 260ms ease both;
}
.qz-moment p { margin: 0; flex: 1 1 190px; font-family: var(--qz-serif); font-style: italic; font-size: 17px; line-height: 1.3; }
.qz-moment small { flex: 1 1 100%; order: 2; font-size: 13px; line-height: 1.4; color: var(--qz-ink-2); }
.qz-moment .qz-primary { order: 3; margin-left: auto; padding: 9px 16px; font-size: 14px; }

/* ---- a line someone says as you pass --------------------------------------------------------- */
.qz-bark {
  position: absolute;
  left: 50%;
  top: calc(var(--qz-top) + 64px);
  width: max-content;
  max-width: min(320px, calc(100% - 32px));
  background: var(--qz-card);
  border-radius: 16px 16px 16px 4px;
  padding: 8px 12px;
  border-left: 4px solid var(--qz-accent);
  box-shadow: 0 8px 22px rgba(5, 8, 24, 0.35);
  pointer-events: none;
  animation: qz-bark 6s ease both;
  z-index: 5;
}
.qz-bark b { display: block; font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase; color: var(--qz-accent); }
.qz-bark span { font-size: 15.5px; line-height: 1.35; }
.qz-bark small { display: block; font-size: 12.5px; color: var(--qz-muted); margin-top: 2px; }

/* ---- talking to someone ----------------------------------------------------------------------- */
.qz-talk { max-height: 74%; overflow-y: auto; touch-action: pan-y; overscroll-behavior: contain; }
.qz-talk-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.qz-talk .qz-ask { display: flex; align-items: center; gap: 8px; margin: 0; }
.qz-talk .qz-ask i { width: 10px; height: 10px; border-radius: 999px; background: var(--qz-accent); }
.qz-talk-you { margin: 0 0 8px; font-size: 14px; line-height: 1.4; color: var(--qz-muted); }
.qz-talk-you b { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; margin-right: 6px; color: var(--qz-ink-2); }
.qz-talk-lines { display: grid; gap: 8px; margin-bottom: 4px; border-left: 4px solid var(--qz-accent); padding-left: 12px; }
.qz-talk-line { animation: qz-in 240ms ease both; }
.qz-talk-line .qz-direction { margin: 0 0 2px; }
.qz-talk .qz-line { font-size: 18px; }
.qz-x {
  width: 36px;
  height: 36px;
  flex: none;
  border-radius: 999px;
  border: 0;
  background: var(--qz-card);
  color: var(--qz-ink);
  display: grid;
  place-items: center;
  box-shadow: 0 2px 0 var(--qz-line-2);
  cursor: pointer;
}
.qz-x svg { width: 16px; height: 16px; }

/* ---- a text on your phone ----------------------------------------------------------------------- */
.qz-phone {
  position: absolute;
  left: 12px;
  right: 12px;
  top: calc(var(--qz-top) + 58px);
  margin: 0 auto;
  max-width: 420px;
  z-index: 30;
  background: var(--qz-card);
  border-radius: 20px;
  padding: 10px 12px 12px;
  box-shadow: 0 14px 34px rgba(5, 8, 24, 0.5);
  animation: qz-drop 340ms cubic-bezier(0.2, 0.9, 0.3, 1.2) both;
}
.qz-phone-head { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--qz-ink-2); margin-bottom: 8px; }
.qz-phone-head svg { width: 16px; height: 16px; flex: none; }
.qz-phone-head b { color: var(--qz-ink); }
.qz-phone-head span { color: var(--qz-muted); font-size: 12px; margin-right: auto; }
.qz-phone .qz-x { width: 30px; height: 30px; box-shadow: none; background: var(--qz-line); }
.qz-bubble { margin: 0 0 6px; width: fit-content; max-width: 82%; background: var(--qz-line); border-radius: 16px 16px 16px 4px; padding: 8px 12px; font-size: 16px; line-height: 1.35; animation: qz-in 220ms ease both; }
.qz-bubble small { display: block; font-size: 12.5px; color: var(--qz-muted); margin-top: 2px; }
.qz-bubble--me { margin-left: auto; background: var(--qz-blue); color: #f8f3e8; border-radius: 16px 16px 4px 16px; }
.qz-phone .qz-chips { margin: 8px 0; }

/* ---- the end card's tonight and tomorrow; what happened while you were away -------------------------- */
.qz-card--end { max-height: 100%; overflow-y: auto; touch-action: pan-y; }
.qz-card-row { display: flex; gap: 6px; margin-top: 8px; }
.qz-card .qz-card-row .qz-quiet { flex: 1; margin-top: 0; width: auto; padding: 9px 4px; background: var(--qz-line); }
.qz-recap { text-align: left; margin: 2px 0 16px; }
.qz-recap h2, .qz-carnet h2 { margin: 0 0 8px; font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--qz-red); }
.qz-recap ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 7px; }
.qz-recap li { position: relative; padding-left: 14px; font-family: var(--qz-serif); font-style: italic; font-size: 16px; line-height: 1.35; }
.qz-recap li::before { content: ''; position: absolute; left: 0; top: 0.55em; width: 6px; height: 6px; border-radius: 999px; background: var(--qz-red); }
.qz-recap small, .qz-carnet small, .qz-map small { display: block; font-family: var(--qz-sans); font-style: normal; font-size: 12.5px; line-height: 1.4; color: var(--qz-muted); margin-top: 2px; }

/* ---- ton carnet, and the map: a page over the street ------------------------------------------------ */
.qz-carnet,
.qz-map {
  position: absolute;
  inset: 0;
  z-index: 40;
  background: rgba(8, 10, 24, 0.55);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  animation: qz-fade 200ms ease both;
}
.qz-carnet-page,
.qz-map-page {
  width: 100%;
  max-width: 560px;
  max-height: calc(100% - var(--qz-top) - 20px);
  overflow-y: auto;
  background: var(--qz-paper);
  border-radius: 22px 22px 0 0;
  padding: 0 18px calc(var(--qz-bottom) + 22px);
  box-shadow: 0 -12px 40px rgba(5, 8, 24, 0.45);
  animation: qz-up 300ms ease both;
  touch-action: pan-y;
  overscroll-behavior: contain;
}
.qz-carnet-head { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; justify-content: space-between; padding: 16px 0 8px; background: var(--qz-paper); }
.qz-carnet-head .qz-h { margin: 0; font-size: 30px; }
.qz-carnet section { margin: 16px 0 0; }
.qz-people { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.qz-people li { display: flex; gap: 12px; align-items: flex-start; background: var(--qz-card); border-radius: 16px; padding: 10px 12px; border-left: 4px solid var(--qz-accent); box-shadow: 0 2px 0 var(--qz-line-2); }
.qz-portrait { width: 52px; height: 52px; flex: none; border-radius: 999px; overflow: hidden; background: color-mix(in srgb, var(--qz-accent) 14%, var(--qz-paper)); display: grid; place-items: center; }
.qz-portrait svg { width: 52px; height: auto; display: block; }
.qz-people b { display: block; font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--qz-accent); }
.qz-people p { margin: 2px 0 0; font-family: var(--qz-serif); font-style: italic; font-size: 17px; line-height: 1.3; }
.qz-people .qz-note { font-size: 15px; color: var(--qz-ink-2); }
.qz-did { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.qz-did li { font-family: var(--qz-serif); font-style: italic; font-size: 16px; line-height: 1.35; padding: 0 0 8px; border-bottom: 1px solid var(--qz-line); }
.qz-did em { display: block; font-family: var(--qz-sans); font-style: normal; font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--qz-muted); margin-top: 3px; }
.qz-pocket { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 10px; }
.qz-pocket li { display: flex; align-items: center; gap: 10px; background: var(--qz-card); border-radius: 14px; padding: 6px 12px 6px 6px; box-shadow: 0 2px 0 var(--qz-line-2); font-family: var(--qz-serif); font-style: italic; font-size: 15px; }
.qz-places { list-style: none; margin: 0 0 12px; padding: 0; display: grid; gap: 8px; }
.qz-places li { background: var(--qz-card); border-radius: 14px; padding: 10px 12px; box-shadow: 0 2px 0 var(--qz-line-2); }
.qz-places li[data-status='locked'] { opacity: 0.62; }
.qz-places b { font-family: var(--qz-serif); font-style: italic; font-size: 18px; font-weight: 500; }
.qz-places p { margin: 3px 0 0; font-size: 13.5px; line-height: 1.4; color: var(--qz-ink-2); }
.qz-tag { display: inline-block; margin-left: 8px; vertical-align: 2px; font-size: 10.5px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 7px; border-radius: 999px; background: var(--qz-line); color: var(--qz-ink-2); }
[data-status='en_chantier'] > .qz-tag { background: var(--qz-yellow); color: var(--qz-ink); }
.qz-wide { width: 100%; padding: 13px 18px; }
.qz-empty { font-family: var(--qz-serif); font-style: italic; color: var(--qz-muted); margin: 0; }
.qz-carnet-foot { margin-top: 18px; text-align: center; }

.qz-map-frame { position: relative; aspect-ratio: 1; width: 100%; max-height: 54vh; margin: 2px auto 0; background: #e3d8c0; border-radius: 16px; overflow: hidden; box-shadow: inset 0 0 0 1.5px var(--qz-line-2); }
.qz-map-frame svg { width: 100%; height: 100%; display: block; }
.qz-map-land path { fill: #f5efe1; stroke: #cbbd9f; stroke-width: 1; vector-effect: non-scaling-stroke; }
.qz-map-seine { fill: none; stroke: #9db4d6; stroke-linecap: round; stroke-linejoin: round; }
.qz-map-canal { fill: none; stroke: #5f84c0; stroke-linecap: round; stroke-linejoin: round; }
.qz-map-canal--covered { stroke: #9db4d6; }
.qz-map-labels text { fill: #b5a98e; font-family: var(--qz-sans); font-weight: 700; pointer-events: none; }
.qz-pin { cursor: pointer; }
.qz-pin-hit { fill: transparent; }
.qz-pin-dot { fill: var(--qz-red); stroke: #f8f3e8; }
.qz-pin[data-status='en_chantier'] .qz-pin-dot { fill: var(--qz-yellow); stroke: var(--qz-ink); }
.qz-pin[data-status='locked'] .qz-pin-dot { fill: #f8f3e8; stroke: #b9ad92; }
.qz-pin-scaffold { stroke: var(--qz-ink); fill: none; stroke-linecap: round; }
.qz-pin-ring { fill: none; stroke: var(--qz-red); transform-box: fill-box; transform-origin: center; animation: qz-pulse 1.8s ease-out infinite; }
.qz-pin text { font-family: var(--qz-serif); font-style: italic; fill: var(--qz-ink); paint-order: stroke; stroke: #f5efe1; stroke-linejoin: round; pointer-events: none; }
.qz-pin[data-status='locked'] text { fill: var(--qz-muted); }
.qz-pin[data-picked] text { text-decoration: underline; }
.qz-map-zoom { position: absolute; right: 10px; bottom: 10px; box-shadow: 0 2px 0 var(--qz-line-2); }
.qz-map-card { margin-top: 12px; background: var(--qz-card); border-radius: 16px; padding: 12px 14px; box-shadow: 0 2px 0 var(--qz-line-2); animation: qz-in 220ms ease both; }
.qz-map-card > .qz-tag { margin: 0; }
.qz-map-card h2 { margin: 6px 0 2px; font-family: var(--qz-serif); font-style: italic; font-weight: 500; font-size: 22px; }
.qz-map-card p { margin: 4px 0 0; font-size: 14px; line-height: 1.4; color: var(--qz-ink-2); }
.qz-map-card .qz-ride { font-family: var(--qz-serif); font-style: italic; font-size: 16px; color: var(--qz-ink); }
.qz-map-card .qz-note { font-size: 13px; color: var(--qz-muted); }
.qz-map-card .qz-primary { margin-top: 12px; }

@keyframes qz-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@keyframes qz-up { from { transform: translateY(100%); } to { transform: none; } }
@keyframes qz-bars { from { transform: scaleY(0); } to { transform: none; } }
@keyframes qz-bark { 0% { opacity: 0; transform: translate(-50%, -6px); } 6% { opacity: 1; transform: translate(-50%, 0); } 86% { opacity: 1; transform: translate(-50%, 0); } 100% { opacity: 0; transform: translate(-50%, 0); } }
@keyframes qz-drop { from { opacity: 0; transform: translateY(-14px); } to { opacity: 1; transform: none; } }
@keyframes qz-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes qz-pulse { from { transform: scale(0.6); opacity: 0.9; } to { transform: scale(1.5); opacity: 0; } }
@keyframes qz-nudge { 0%, 100% { transform: translate(0, 0) rotate(-45deg); } 50% { transform: translate(3px, 0) rotate(-45deg); } }
.qz-goal, .qz-you { transform-origin: bottom center; }
.qz-goal { animation-name: qz-goal-in; }
@keyframes qz-goal-in { from { opacity: 0; transform: translate(-50%, 6px); } to { opacity: 1; transform: translate(-50%, 0); } }
@media (prefers-reduced-motion: reduce) {
  .qz *, .qz *::before, .qz *::after { animation-duration: 1ms !important; animation-delay: 0ms !important; transition-duration: 1ms !important; }
  .qz-bark { animation: none !important; transform: translateX(-50%); }
}
`;
