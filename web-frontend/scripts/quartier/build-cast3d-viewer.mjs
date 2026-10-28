// Le Quartier · one self-contained HTML page to look at the cast in the round (three.js, the cast's
// sculpting and faces, and the app's two typefaces inlined), to open in any browser or share.
//   node scripts/quartier/build-cast3d-viewer.mjs [out.html] [--fragment]
// --fragment leaves out the document's skeleton (doctype, head, body), for a host that adds its own.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { build } from 'esbuild';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..', '..');
const args = process.argv.slice(2);
const fragment = args.includes('--fragment');
const out = path.resolve(args.find((a) => !a.startsWith('--')) ?? path.join(web, 'out-quartier', 'la-troupe-en-relief.html'));

const result = await build({
  entryPoints: [path.join(here, 'cast3d-viewer.ts')],
  bundle: true,
  write: false,
  format: 'iife',
  platform: 'browser',
  target: ['safari15', 'chrome100'],
  jsx: 'automatic',
  minify: true,
  legalComments: 'none',
  tsconfig: path.join(web, 'tsconfig.json'),
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'warning',
});
const js = result.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');

const font = (family, style, weight, file) => {
  const b64 = fs.readFileSync(path.join(web, 'public', 'fonts', file)).toString('base64');
  return `@font-face{font-family:'${family}';font-style:${style};font-weight:${weight};font-display:swap;src:url(data:font/woff2;base64,${b64}) format('woff2');}`;
};
const fonts = [font('AtelierSerif', 'italic', '400 800', 'eb-garamond-italic-latin.woff2'), font('AtelierSans', 'normal', '400 700', 'instrument-sans-latin.woff2')].join('');

const style = `<style>
${fonts}
/* Layout: the stage is the proof on the press bed; the controls sit beside it like labelled type cases. */
:root {
  --bg: #f1ece1;
  --card: #f8f3e8;
  --ink: #14110d;
  --ink-2: #4a4538;
  --muted: #6f6857;
  --line: #e2d9c6;
  --edge: #d1c5ab;
  --accent: #b8290f;
  --stage: #e9e2d3;
  /* the cards on the stage stay paper and ink, as the quarter's speech cards do, whatever the theme */
  --paper: #f8f3e8;
  --paper-ink: #14110d;
  --paper-muted: #5f5848;
  --serif: 'AtelierSerif', 'EB Garamond', Georgia, 'Times New Roman', serif;
  --sans: 'AtelierSans', 'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0d1430; --card: #18214a; --ink: #f1ece1; --ink-2: #d5ccb8; --muted: #a49c8a;
    --line: #2a3566; --edge: #060a1c; --accent: #f3c318; --stage: #1b2552; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0d1430; --card: #18214a; --ink: #f1ece1; --ink-2: #d5ccb8; --muted: #a49c8a;
  --line: #2a3566; --edge: #060a1c; --accent: #f3c318; --stage: #1b2552; color-scheme: dark;
}
html, body { height: 100%; }
body { background: var(--bg); color: var(--ink); font-family: var(--sans); font-size: 15px; line-height: 1.45; }
.app {
  min-height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: "head" "stage" "panel";
  gap: 16px;
  padding-block: 16px 28px;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  box-sizing: border-box;
}
.head { grid-area: head; display: grid; gap: 6px; }
.kicker { margin: 0; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-family: var(--serif); font-style: italic; font-weight: 500; font-size: clamp(2rem, 7vw, 2.9rem); line-height: 1; letter-spacing: -0.01em; text-wrap: balance; }
.lede { margin: 2px 0 0; max-width: 60ch; color: var(--ink-2); }
.stage {
  grid-area: stage;
  position: relative;
  width: 100%;
  max-width: 100%;
  aspect-ratio: 4 / 5;
  max-height: 76svh;
  border-radius: 6px;
  overflow: hidden;
  background: var(--stage);
  box-shadow: 0 0 0 1px var(--line), 0 3px 0 var(--edge);
  touch-action: none;
  cursor: grab;
  outline: none;
}
.stage:active { cursor: grabbing; }
.stage:focus-visible { box-shadow: 0 0 0 2px var(--accent), 0 3px 0 var(--edge); }
.stage canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
.who {
  position: absolute;
  left: 12px;
  bottom: 12px;
  max-width: calc(100% - 24px);
  display: grid;
  gap: 2px;
  padding: 9px 13px 10px;
  background: var(--paper);
  color: var(--paper-ink);
  border-radius: 4px;
  box-shadow: 0 2px 0 rgba(20, 17, 13, 0.28);
  pointer-events: none;
}
.who-name { font-family: var(--serif); font-style: italic; font-size: 1.45rem; line-height: 1.05; }
.who-role { font-size: 0.8rem; color: var(--paper-muted); }
.hint {
  position: absolute;
  top: 10px;
  right: 10px;
  max-width: calc(100% - 20px);
  margin: 0;
  text-align: right;
  font-size: 0.75rem;
  color: var(--paper-ink);
  pointer-events: none;
}
.hint { transition: opacity 0.6s ease; }
.hint.gone { opacity: 0; }
.hint span { display: inline-block; padding: 5px 9px; border-radius: 999px; background: color-mix(in srgb, var(--paper) 86%, transparent); }
@media (max-width: 600px) {
  .who { left: 10px; bottom: 10px; padding: 7px 11px 8px; }
  .who-name { font-size: 1.2rem; }
  .who-role { font-size: 0.75rem; }
}
.note { position: absolute; inset: 0; margin: 0; display: grid; place-items: center; padding: 24px; text-align: center; color: var(--ink-2); }
.panel { grid-area: panel; display: grid; gap: 18px; align-content: start; min-width: 0; }
.group { display: grid; gap: 9px; min-width: 0; }
h2 { margin: 0; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
.chips { display: flex; flex-wrap: wrap; gap: 7px; }
.chip {
  font: 500 0.875rem/1 var(--sans);
  padding: 9px 12px 10px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--card);
  color: var(--ink);
  box-shadow: 0 2px 0 var(--edge);
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.chip:active { transform: translateY(2px); box-shadow: 0 0 0 var(--edge); }
.chip[aria-pressed="true"] { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.chip:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.chip:disabled { opacity: 0.45; cursor: not-allowed; }
.chip.square { border-radius: 6px; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex: none; box-shadow: 0 0 0 1.5px var(--card); }
.chip[aria-pressed="true"] .dot { box-shadow: 0 0 0 1.5px var(--bg); }
.foot { margin: 4px 0 0; font-size: 0.8rem; color: var(--muted); max-width: 60ch; }
@media (min-width: 900px) {
  .app {
    height: 100%;
    grid-template-columns: minmax(0, 1fr) 380px;
    grid-template-rows: auto minmax(0, 1fr);
    grid-template-areas: "stage head" "stage panel";
    column-gap: 28px;
    padding-block: 20px;
  }
  .stage { aspect-ratio: auto; max-height: none; height: 100%; }
  .panel { overflow-y: auto; padding-bottom: 8px; }
}
@media (prefers-reduced-motion: reduce) { .chip:active { transform: none; } }
</style>`;

const body = `<div class="app">
  <header class="head">
    <p class="kicker">Le Quartier · cast in the round</p>
    <h1>La troupe en relief</h1>
    <p class="lede">The season's eight main characters, sculpted for the 3D Paris and printed in its ink. Turn them round, give them a mood, make them act.</p>
  </header>
  <section class="stage" id="stage" tabindex="0" aria-label="3D stage: drag to turn, pinch or scroll to come closer, arrow keys work too">
    <canvas id="stage-canvas"></canvas>
    <div class="who" aria-live="polite"><span class="who-name" id="who-name">Margaux</span><span class="who-role" id="who-role"></span></div>
    <p class="hint" id="hint"><span>Drag to turn · pinch to come closer · double-tap to reset</span></p>
    <p class="note" id="stage-note" hidden></p>
  </section>
  <section class="panel" aria-label="Controls">
    <div class="group">
      <h2>Who</h2>
      <div class="chips" id="people-row"></div>
      <div id="variant-row" hidden><div class="chips" id="variant-chips"></div></div>
    </div>
    <div class="group">
      <h2>Mood</h2>
      <div class="chips" id="mood-row"></div>
    </div>
    <div class="group">
      <h2>Gesture</h2>
      <div class="chips" id="gesture-row"></div>
    </div>
    <div class="group">
      <h2>Act</h2>
      <div class="chips">
        <button type="button" class="chip" id="act-talk">Talk</button>
        <button type="button" class="chip" id="act-bow">Bow</button>
        <button type="button" class="chip" id="act-hop">Hop</button>
        <button type="button" class="chip" id="act-walk">Walk a loop</button>
      </div>
      <div class="chips" role="group" aria-label="Standing or sitting">
        <button type="button" class="chip square" data-row="seat" data-value="off" aria-pressed="true">Standing</button>
        <button type="button" class="chip square" data-row="seat" data-value="on" aria-pressed="false">Sitting</button>
      </div>
    </div>
    <div class="group">
      <h2>Light</h2>
      <div class="chips" role="group" aria-label="Light">
        <button type="button" class="chip square" data-row="light" data-value="matin" aria-pressed="false">Morning</button>
        <button type="button" class="chip square" data-row="light" data-value="nuit" aria-pressed="false">Night on the quai</button>
        <button type="button" class="chip square" data-row="light" data-value="cafe" aria-pressed="false">Inside Le Mistral</button>
      </div>
    </div>
    <p class="foot">Each person is one skinned mesh of 8,000 to 17,000 triangles on a twenty-bone skeleton, with their face printed from the app's own drawings. In the game they stand in Le Mistral in place of the paper cards.</p>
  </section>
</div>`;

const head = `<title>La troupe en relief</title>
<meta name="claude:viewport-fit-sides" content="cover">
${style}`;
const html = fragment
  ? `${head}
${body}
<script>${js}</script>
`
  : `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
${head}
</head>
<body>
${body}
<script>${js}</script>
</body>
</html>
`;
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, html);
console.log(`wrote ${path.relative(process.cwd(), out)} (${(html.length / 1024 / 1024).toFixed(2)} MB)`);
