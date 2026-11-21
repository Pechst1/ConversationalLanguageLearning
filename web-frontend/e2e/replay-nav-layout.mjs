#!/usr/bin/env node
// R2 · the archive reader's «Weiter» is not under the tab bar at phone size.   (from web-frontend/)
//
//   node e2e/replay-nav-layout.mjs
//   CHROMIUM_PATH=/path/to/chrome node e2e/replay-nav-layout.mjs      (when Playwright's own build is absent)
//
// Real play (17 Nov, a1-d2-replay-nav-overlap.png): the archive's replay at /graphic-novel,
// 375x812, drew the story reader's pinned foot navigation (dots, ‹, «Weiter») under the fixed
// four-tab bar; the tap went to the bar. No server: one static page carries the real
// stylesheets (styles/globals.css's phone tokens, styles/atelier-v2.css, the reader's own
// `reader-styles.tsx`) around the reader's foot navigation and the tab bar, in the
// miss-layout style: bounding boxes, at 375x812 and 375x667, asserting that
//   * «Weiter» and the dots end above the tab bar's top edge;
//   * the element at «Weiter»'s centre is «Weiter» itself (not the bar);
//   * without a tab bar (the journey session) the navigation keeps its place at the bottom.
// Exit 1 on a failure.
import { chromium } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { WEB_ROOT } from './lib/stack.mjs';

const read = (rel) => readFileSync(path.join(WEB_ROOT, rel), 'utf8');
const readerTsx = read('components/feuilleton/reader/reader-styles.tsx');
const readerCss = readerTsx.slice(readerTsx.indexOf('{`') + 2, readerTsx.lastIndexOf('`}'));
// Only the custom properties of globals.css (its Tailwind layers need the build).
const globals = read('styles/globals.css');
const rootVars = globals.slice(globals.indexOf(':root {'), globals.indexOf('}', globals.indexOf(':root {')) + 1);
const tokens = read('styles/atelier-v2.css');

function html(withBar) {
  const dots = Array.from({ length: 17 }, (_, i) => `<li><button class="fr-dot" data-state="${i ? 'ahead' : 'current'}"><span class="glyph"></span></button></li>`).join('');
  const bar = withBar
    ? `<nav class="av2 av2-tabbar phone-product-nav fixed" aria-label="Primary">${['Une', 'Feuilleton', 'Courrier', 'Cahier']
        .map((label) => `<a class="av2-tabbar__tab" href="#"><span class="av2-tab__pill"></span><span>${label}</span></a>`)
        .join('')}</nav>`
    : '';
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>*, ::before, ::after { box-sizing: border-box; } /* Tailwind's preflight, as in the app */</style>
<style>${rootVars}</style><style>${tokens}</style><style>${readerCss}</style></head>
<body style="margin:0"><div class="app-root"><div class="av2"><section class="fr-reader" data-story="true">
<div style="height:1400px">panel</div>
<nav class="fr-nav" aria-label="nav"><ol class="fr-dots">${dots}</ol>
<div class="fr-nav-row"><button class="fr-btn fr-prev">‹</button><button id="next" class="fr-btn fr-next">Weiter</button></div></nav>
</section></div>${bar}</div></body></html>`;
}

const failures = [];
const check = (ok, label) => {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${label}`);
  if (!ok) failures.push(label);
};

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
try {
  for (const height of [812, 667]) {
    const page = await browser.newPage({ viewport: { width: 375, height } });
    await page.setContent(html(true));
    const next = await page.locator('#next').boundingBox();
    const dots = await page.locator('.fr-dots').boundingBox();
    const bar = await page.locator('nav[aria-label="Primary"]').boundingBox();
    check(Boolean(next && bar && next.y + next.height <= bar.y), `375x${height}: «Weiter» ends above the tab bar (${next?.y + next?.height} ≤ ${bar?.y})`);
    check(Boolean(dots && bar && dots.y + dots.height <= bar.y), `375x${height}: the dots end above the tab bar`);
    const hit = await page.evaluate(() => {
      const box = document.getElementById('next').getBoundingClientRect();
      return document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)?.id || null;
    });
    check(hit === 'next', `375x${height}: a tap on «Weiter» reaches «Weiter» (${hit})`);

    await page.setContent(html(false));
    const alone = await page.locator('#next').boundingBox();
    check(Boolean(alone && alone.y + alone.height > height - 40), `375x${height}: without a tab bar the navigation stays at the bottom`);
    await page.close();
  }
} finally {
  await browser.close();
}
if (failures.length) {
  console.error(`\n${failures.length} layout check(s) failed`);
  process.exit(1);
}
console.log('\nreplay navigation clear of the tab bar');
