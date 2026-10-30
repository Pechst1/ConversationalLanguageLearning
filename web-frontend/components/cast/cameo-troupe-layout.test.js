// node --test components/cast/cameo-troupe-layout.test.js
//
// #359: on the Done screen the troupe's «End of the session» tag sat to the
// right of centre, over the right half of the cast, instead of over the middle
// of it. The tag was `position: absolute` with `left: 50%; transform:
// translateX(-50%)`, but its own pop-in animation also sets `transform`, so the
// animation's `scale(1)` replaced the centring for good. The tag now lives in
// the troupe's own flow, so it is centred by layout and the troupe's box
// contains it: it cannot land on a bubble.
//
// This draws the real CameoLayer markup (a finale cameo, as `decideCameo`
// makes it) with the real stylesheet in Chromium at 375 × 812 and measures it.
// Where no Chromium is installed the layout check is skipped; the stylesheet
// contract below always runs.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

// A static render runs no effects, so the layer would draw nothing: hand it the
// finale as its first state («shown»), and render the layer itself.
const cameoLib = require('../../lib/cameo.ts');
const { cameo } = cameoLib.decideCameo(cameoLib.INITIAL_CAMEO_STATE, { type: 'finale', lead: null }, Date.now());
const realUseState = React.useState;
let seeded = false;
React.useState = (initial) => {
  if (!seeded && initial === null) {
    seeded = true;
    return [cameo, () => {}];
  }
  return realUseState(initial);
};
const { CameoLayer } = require('./CameoLayer.tsx');

function layerMarkup() {
  seeded = false;
  const original = console.error;
  console.error = () => {};
  try {
    return renderToStaticMarkup(React.createElement(CameoLayer));
  } finally {
    console.error = original;
  }
}

const CSS = fs.readFileSync(path.join(WEB_ROOT, 'styles', 'cameo.css'), 'utf8');

function chromiumPath() {
  const candidates = [process.env.WALK_CHROMIUM, process.env.PLAYWRIGHT_CHROMIUM];
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, '/opt/pw-browsers', path.join(process.env.HOME || '', '.cache', 'ms-playwright')];
  for (const root of roots.filter(Boolean)) {
    try {
      for (const dir of fs.readdirSync(root).filter((d) => /^chromium-\d+$/.test(d))) {
        candidates.push(path.join(root, dir, 'chrome-linux64', 'chrome'));
      }
    } catch {
      // no browsers here
    }
  }
  return candidates.find((file) => file && fs.existsSync(file)) || null;
}

test('the finale cameo is a troupe with its tag', () => {
  assert.equal(cameo.kind, 'troupe');
  assert.equal(cameo.trigger, 'finale');
  const html = layerMarkup();
  assert.match(html, /class="cameo-troupe"/);
  assert.match(html, /class="cameo-reason"[^>]*>End of the session</);
});

test('the troupe’s tag is laid out in the troupe, not hung over it', () => {
  // The old rule: out of flow, centred by a transform its own animation replaces.
  const rule = (CSS.replace(/\/\*[\s\S]*?\*\//g, '').match(/\.cameo-troupe\s*>\s*\.cameo-reason\s*\{[^}]*\}/) || [''])[0];
  assert.doesNotMatch(rule, /position:\s*absolute/, 'an out-of-flow tag can land on the bubbles');
  assert.doesNotMatch(rule, /translateX\(-50%\)/, 'the pop-in animation replaces a transform used for centring');
});

test('at 375 × 812 the «End of the session» tag is centred over the cast and clear of every bubble', async (t) => {
  const executablePath = chromiumPath();
  if (!executablePath) return t.skip('no Chromium installed');
  let chromium;
  try {
    ({ chromium } = require(path.join(WEB_ROOT, 'node_modules/playwright-core')));
  } catch {
    return t.skip('playwright-core is not installed');
  }
  const browser = await chromium.launch({ executablePath });
  try {
    const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
    await page.setContent(`<!doctype html><html><head><style>body{margin:0}${CSS}</style></head><body>${layerMarkup()}</body></html>`);
    // The hops, bows and the tag's pop-in all end inside this.
    await page.waitForTimeout(3000);
    const boxes = await page.evaluate(() => {
      const box = (el) => {
        const r = el.getBoundingClientRect();
        return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
      };
      return {
        tag: box(document.querySelector('.cameo-reason')),
        bubbles: [...document.querySelectorAll('.cameo-bubble')].map(box),
        members: [...document.querySelectorAll('.cameo-troupe__member')].map(box),
      };
    });
    const { tag, bubbles, members } = boxes;
    assert.ok(bubbles.length >= 4, `the finale has a cast (${bubbles.length} bubbles)`);

    const castLeft = Math.min(...members.map((m) => m.left));
    const castRight = Math.max(...members.map((m) => m.right));
    const tagMid = (tag.left + tag.right) / 2;
    const castMid = (castLeft + castRight) / 2;
    assert.ok(
      Math.abs(tagMid - castMid) <= 6,
      `the tag is centred over the cast: its middle is at x=${Math.round(tagMid)}, the cast's at x=${Math.round(castMid)} (tag ${Math.round(tag.left)}–${Math.round(tag.right)})`,
    );
    assert.ok(tag.left >= 0 && tag.right <= 375, 'the tag stays on screen');

    for (const bubble of bubbles) {
      const apart = bubble.top >= tag.bottom + 4 || bubble.left >= tag.right || bubble.right <= tag.left;
      assert.ok(apart, `the tag (y ${Math.round(tag.top)}–${Math.round(tag.bottom)}) touches a bubble (y ${Math.round(bubble.top)}–${Math.round(bubble.bottom)})`);
    }
    for (const member of members) {
      assert.ok(tag.bottom <= member.top + 1, `the tag sits above every figure, not over one (tag bottom ${Math.round(tag.bottom)}, figure top ${Math.round(member.top)})`);
    }
  } finally {
    await browser.close();
  }
});
