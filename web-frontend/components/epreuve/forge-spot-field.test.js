// node --test components/epreuve/forge-spot-field.test.js
//
// #335 «Find the mistake»: a learner tapped «la» in «Margaux aime la huile
// d'olive.» and typed «l'»; the field had opened holding «la» with the caret at
// its end, so the word became «lal'». Tapping a word to replace it must leave the
// field holding the word *selected*, so that what is typed replaces it.
//
// This drives the real ForgeSpot in a real browser (Chromium from Playwright):
// a click on the word, real key presses, the answer the page would send. The
// screen's own modules are compiled for the browser; only the heavy neighbours
// ForgeSpot does not use (the Épreuve shell, the shared UI kit) are stubbed.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test, before, after } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
const { transform } = require(path.join(WEB_ROOT, 'node_modules/sucrase'));

const STUBS = new Set([
  '@/components/atelier-v2/ui',
  '@/components/epreuve/Epreuve',
  '@/lib/classification-copy',
]);

/** The module and everything it imports from this app, compiled to CommonJS for the page. */
function bundle(entry) {
  const modules = {};
  const visit = (file) => {
    const id = path.relative(WEB_ROOT, file);
    if (modules[id] !== undefined) return id;
    modules[id] = '';
    const source = fs.readFileSync(file, 'utf8');
    modules[id] = transform(source, { transforms: ['typescript', 'jsx', 'imports'], production: true }).code;
    const requires = [...modules[id].matchAll(/require\(["']([^"']+)["']\)/g)].map((m) => m[1]);
    for (const request of requires) {
      if (STUBS.has(request)) continue;
      const target = request.startsWith('@/')
        ? path.join(WEB_ROOT, request.slice(2))
        : request.startsWith('.') ? path.resolve(path.dirname(file), request) : null;
      if (!target) continue;
      const found = ['.ts', '.tsx', '.js'].map((ext) => target + ext).find((candidate) => fs.existsSync(candidate));
      assert.ok(found, `cannot find ${request} from ${id}`);
      visit(found);
    }
    return id;
  };
  visit(entry);
  return modules;
}

function pageFor(modules) {
  const react = fs.readFileSync(path.join(WEB_ROOT, 'node_modules/react/umd/react.development.js'), 'utf8');
  const dom = fs.readFileSync(path.join(WEB_ROOT, 'node_modules/react-dom/umd/react-dom.development.js'), 'utf8');
  return `<!doctype html><html><head><meta charset="utf-8"></head><body>
<div id="root"></div><output id="answer"></output><button id="elsewhere" type="button">elsewhere</button>
<script>${react}</script><script>${dom}</script>
<script>
const SOURCES = ${JSON.stringify(modules)};
const STUBS = ${JSON.stringify([...STUBS])};
const cache = {};
function resolve(from, request) {
  if (request.startsWith('@/')) return request.slice(2);
  const parts = from.split('/').slice(0, -1).concat(request.split('/'));
  const out = [];
  for (const part of parts) { if (part === '..') out.pop(); else if (part !== '.') out.push(part); }
  return out.join('/');
}
function load(id) {
  if (cache[id]) return cache[id].exports;
  const file = Object.keys(SOURCES).find((key) => key.replace(/\\.(ts|tsx|js)$/, '') === id);
  const module = (cache[id] = { exports: {} });
  const run = new Function('require', 'module', 'exports', SOURCES[file]);
  run((request) => {
    if (request === 'react') return window.React;
    if (STUBS.includes(request)) return {};
    return load(resolve(file, request));
  }, module, module.exports);
  return module.exports;
}
const React = window.React;
const { ForgeSpot } = load('components/epreuve/ForgeDrills');
const { spotTokens, spotAnswer, spotChanged } = load('lib/forge-drills');
const { forgeCopy } = load('lib/forge-copy');
function Harness() {
  const sentence = "Margaux aime la huile d'olive.";
  const [edits, setEdits] = React.useState({});
  const tokens = spotTokens(sentence);
  document.getElementById('answer').textContent = spotChanged(tokens, edits) ? spotAnswer(tokens, edits) : '';
  return React.createElement(ForgeSpot, { sentence, edits, onEdits: setEdits, copy: forgeCopy('en'), fixWords: 2 });
}
ReactDOM.render(React.createElement(Harness), document.getElementById('root'));
</script></body></html>`;
}

let browser;
let page;
let skip = false;
let html = '';
const errors = [];
/** A new page for each test: a document written twice keeps its first `const`s. */
async function fresh() {
  if (page) await page.close();
  page = await browser.newPage();
  page.setDefaultTimeout(5000);
  page.on('pageerror', (error) => errors.push(error.message));
  await page.setContent(html);
  assert.deepEqual(errors, [], 'the page loads the real ForgeSpot without errors');
}

before(async () => {
  const { chromium } = require(path.join(WEB_ROOT, 'node_modules/playwright-core'));
  // The Chromium Playwright installed, else the Chrome a CI runner ships with.
  const launches = [process.env.WALK_CHROMIUM ? { executablePath: process.env.WALK_CHROMIUM } : {}, { channel: 'chrome' }];
  let failure = '';
  for (const options of launches) {
    try {
      browser = await chromium.launch(options);
      break;
    } catch (error) {
      failure = String(error.message).split('\n')[0];
    }
  }
  if (!browser) {
    // On CI a missing browser is a red build, not a skipped test.
    assert.ok(!process.env.CI, `no browser to drive: ${failure}`);
    skip = `no browser to drive: ${failure}`;
    return;
  }
  html = pageFor(bundle(path.join(WEB_ROOT, 'components/epreuve/ForgeDrills.tsx')));
});

after(async () => {
  if (browser) await browser.close();
});

const word = (text) => page.locator('.forge-spot__word', { hasText: new RegExp(`^${text}$`) });
const answer = () => page.locator('#answer').innerText();

test('a tapped word opens with its text selected, so typing replaces it', async (t) => {
  if (skip) return t.skip(skip);
  await fresh();
  await word('la').click();
  const field = page.locator('.forge-spot__input');
  assert.equal(await field.inputValue(), 'la');
  const selection = await field.evaluate((input) => [input.selectionStart, input.selectionEnd]);
  assert.deepEqual(selection, [0, 2], 'the whole word is selected when the field opens');
});

test('typing «l\'» over «la» builds «l\'huile», never «lal\'»', async (t) => {
  if (skip) return t.skip(skip);
  await fresh();
  await word('la').click();
  await page.keyboard.type("l'");
  assert.equal(await page.locator('.forge-spot__input').inputValue(), "l'", 'the field holds what was typed, not the old word with it');
  await page.keyboard.press('Enter');
  assert.equal(await answer(), "Margaux aime l'huile d'olive.");
});

test('a word fixed once opens selected again', async (t) => {
  if (skip) return t.skip(skip);
  await fresh();
  await word('la').click();
  await page.keyboard.type('le');
  await page.locator('#elsewhere').click();
  assert.equal(await answer(), "Margaux aime le huile d'olive.");
  await page.locator('.forge-spot__word[data-edited="true"]').click();
  await page.keyboard.type("l'");
  await page.keyboard.press('Enter');
  assert.equal(await answer(), "Margaux aime l'huile d'olive.");
});

test('leaving the field untouched changes nothing', async (t) => {
  if (skip) return t.skip(skip);
  await fresh();
  await word('huile').click();
  await page.locator('#elsewhere').click();
  assert.equal(await answer(), '');
});
