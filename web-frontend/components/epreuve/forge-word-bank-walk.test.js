// node --test components/epreuve/forge-word-bank-walk.test.js
//
// La Forge's word bank is the system's word bank, the one the browser walk taps.
//
// Main's 7-day walk stood 10 s on «La Forge · Build: "We are 50 years old." Tap the
// words» and never reached the recap. The walk taps a word bank by one selector
// (e2e/lib/driver.mjs WORD_BANK_TILE, the system's `av2-tiles__bank`), and La Forge
// drew its own bank twice, by hand, as an `ep-typecase` div the selector did not
// match: the drill's «Build» item (pages/atelier.tsx) and «Correct the sentence»
// (ForgeFollowUp.tsx). Its day-4 visit to La Forge stopped silently in front of the
// first «Build» item; on day 5 the day's own grammar step opened the same item.
//
// Past the bank, a missed «Build» line waits for «Copy the correction»: «Continue»
// comes only once the corrected line is retyped and compared, and the walk had no hand
// for that field either.
//
// One bank component (EpTypecase) for every Forge bank, and the walk's selectors
// checked against what the components render, so a Forge step the walk cannot get
// past cannot come back unnoticed.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');
const { pathToFileURL } = require('node:url');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const Ep = require('./Epreuve.tsx');

const h = React.createElement;

/** The walk's own selectors, read from the walk (an ES module). */
async function walkDriver() {
  return import(pathToFileURL(path.join(WEB_ROOT, 'e2e/lib/driver.mjs')).href);
}
async function walkTileSelector() {
  return (await walkDriver()).WORD_BANK_TILE;
}

/** Every opening tag in `html` whose name is `tag` and whose classes hold `cls`. */
function tagsWithClass(html, tag, cls) {
  return [...html.matchAll(new RegExp(`<${tag}\\b([^>]*)>`, 'g'))]
    .map((m) => m[1])
    .filter((attrs) => ((/class="([^"]*)"/.exec(attrs) || [])[1] || '').split(/\s+/).includes(cls));
}
/** The class names a selector names, in order (`.a b.c:not(...)` → a, c). */
const classesOf = (selector) => [...selector.replace(/:not\([^)]*\)/g, '').matchAll(/\.([\w-]+)/g)].map((m) => m[1]);

/** `.bank button.tile:not([disabled])` → { bank, tile }; any other shape fails loudly. */
function parseTileSelector(selector) {
  const m = /^\.([\w-]+) button\.([\w-]+):not\(\[disabled\]\)$/.exec(selector);
  assert.ok(m, `the walk's word-bank selector changed shape («${selector}»): update this guard with it`);
  return { bank: m[1], tile: m[2] };
}

/** The idle tiles the selector reaches in a rendered fragment (a nested-div-free bank). */
function tappable(html, { bank, tile }) {
  const banks = [...html.matchAll(/<div class="([^"]*)"[^>]*>([\s\S]*?)<\/div>/g)].filter((m) =>
    m[1].split(/\s+/).includes(bank),
  );
  return banks.flatMap((m) =>
    [...m[2].matchAll(/<button([^>]*)>([\s\S]*?)<\/button>/g)]
      .filter((b) => {
        const cls = (/class="([^"]*)"/.exec(b[1]) || [])[1] || '';
        return cls.split(/\s+/).includes(tile) && !/\sdisabled=/.test(b[1]);
      })
      .map((b) => b[2].replace(/<[^>]+>/g, '').trim()),
  );
}

test('La Forge draws its word bank as one component, the bank the walk taps', async () => {
  const selector = parseTileSelector(await walkTileSelector());
  const html = renderToStaticMarkup(
    h(
      Ep.EpShell,
      { language: 'en' },
      h(
        Ep.EpTypecase,
        null,
        h(Ep.EpSlug, { onClick: () => {} }, 'Nous'),
        h(Ep.EpSlug, { onClick: () => {} }, 'avons'),
        h(Ep.EpSlug, { spent: true, disabled: true, onClick: () => {} }, 'cinquante'),
      ),
    ),
  );
  assert.deepEqual(
    tappable(html, selector),
    ['Nous', 'avons'],
    `the walk taps «${selector.bank} … ${selector.tile}»; La Forge's bank rendered: ${html}`,
  );
});

test('no Forge page draws a word bank of its own', () => {
  // Every surface that sets words with EpSlug takes them from EpTypecase; the
  // bank's markup lives in Epreuve.tsx alone.
  const roots = ['pages', 'components'].map((dir) => path.join(WEB_ROOT, dir));
  const files = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.tsx$/.test(entry.name)) files.push(full);
    }
  };
  roots.forEach(walk);
  const home = path.join(WEB_ROOT, 'components/epreuve/Epreuve.tsx');
  // The class still styles the bank (a page's CSS may name it); only drawing it is EpTypecase's.
  const drawsTypecase = /className=\{?["'`][^"'`]*\bep-typecase\b/;
  const handDrawn = files.filter((file) => file !== home && drawsTypecase.test(fs.readFileSync(file, 'utf8')));
  assert.deepEqual(handDrawn.map((f) => path.relative(WEB_ROOT, f)), [], 'a Forge word bank drawn by hand, not with EpTypecase');
  const banksWithoutTypecase = files.filter((file) => {
    if (file === home) return false;
    const source = fs.readFileSync(file, 'utf8');
    // A bank's slug is the one that is not `set` in the line.
    const bankSlugs = [...source.matchAll(/<EpSlug\b([\s\S]*?)>/g)].filter((m) => !/\bset\b/.test(m[1]));
    return bankSlugs.length > 0 && !source.includes('<EpTypecase');
  });
  assert.deepEqual(
    banksWithoutTypecase.map((f) => path.relative(WEB_ROOT, f)),
    [],
    'words to tap that are not in EpTypecase',
  );
});

test('the walk copies a Forge correction by the classes the repair renders', async () => {
  const { FORGE_REPAIR } = await walkDriver();
  const fix = 'Tu as peur ce soir, Marin ?';
  const html = renderToStaticMarkup(
    h(
      Ep.EpShell,
      { language: 'en' },
      h(
        'div',
        null,
        h(Ep.EpGalley, { anchor: 'Avoir' }, h(Ep.EpLineFix, { old: 'Tu ? as peur, soir Marin es ce', fix })),
        h(Ep.EpRepair, { target: fix, typed: '', status: null, onChange: () => {}, onSubmit: () => {} }),
      ),
    ),
  );
  const [openCls] = classesOf(FORGE_REPAIR.open);
  const open = tagsWithClass(html, '[a-z]+', openCls);
  assert.equal(open.length, 1, `the open repair («${FORGE_REPAIR.open}») is not on the miss: ${html}`);
  assert.ok(!/data-status="ok"/.test(open[0]), 'an unanswered repair is open');

  const fieldTag = /^(\w+)\./.exec(FORGE_REPAIR.field)[1];
  const fields = tagsWithClass(html, fieldTag, classesOf(FORGE_REPAIR.field)[0]);
  assert.equal(fields.length, 1, `the walk types into «${FORGE_REPAIR.field}»: ${html}`);
  assert.ok(!/\sdisabled=/.test(fields[0]), 'the repair field is enabled');

  const submitTag = /^(\w+)\./.exec(FORGE_REPAIR.submit)[1];
  assert.equal(
    tagsWithClass(html, submitTag, classesOf(FORGE_REPAIR.submit)[0]).length,
    1,
    `the walk taps «${FORGE_REPAIR.submit}»: ${html}`,
  );

  const [galley, line] = classesOf(FORGE_REPAIR.correction);
  const galleyAt = html.search(new RegExp(`class="[^"]*\\b${galley}\\b`));
  const lineMatch = new RegExp(`<p class="[^"]*\\b${line}\\b[^"]*"[^>]*>([^<]*)</p>`).exec(html);
  assert.ok(galleyAt >= 0 && lineMatch && lineMatch.index > galleyAt, `the correction («${FORGE_REPAIR.correction}») is printed in its card: ${html}`);
  assert.equal(lineMatch[1].replace(/&#x27;/g, "'"), fix, 'the line the walk copies is the correction');
});

test('the walk answers «Trouve l’erreur» by the classes ForgeSpot renders', async () => {
  // Main's 7-day walk stood 10 s on La Forge's «Trouve l'erreur» (B1 day 3, 11/12) and
  // never reached the recap: the walk had no hand for ForgeSpot.
  const { FORGE_SPOT } = await walkDriver();
  assert.ok(FORGE_SPOT, 'the walk defines how it answers «Trouve l’erreur» (e2e/lib/driver.mjs FORGE_SPOT)');
  const Drills = require('./ForgeDrills.tsx');
  const { forgeCopy } = require('@/lib/forge-copy.ts');
  const copy = forgeCopy('fr');
  const render = (edits) =>
    renderToStaticMarkup(
      h(Ep.EpShell, { language: 'fr' }, h(Drills.ForgeSpot, { sentence: 'Il est parti sans disant au revoir.', edits, onEdits: () => undefined, copy })),
    );

  const wordTag = /^(\w+)\./.exec(FORGE_SPOT.word)[1];
  const [wordCls] = classesOf(FORGE_SPOT.word);
  const fresh = tagsWithClass(render({}), wordTag, wordCls);
  assert.ok(fresh.length >= 6, `the walk taps a word by «${FORGE_SPOT.word}»`);
  assert.ok(fresh.every((attrs) => !/\sdisabled=/.test(attrs)), 'the words of an open item can be tapped');

  const edited = tagsWithClass(render({ 4: 'dire' }), wordTag, classesOf(FORGE_SPOT.edited)[0]).filter((attrs) =>
    /data-edited="true"/.test(attrs),
  );
  assert.equal(edited.length, 1, `the walk reads a word it already changed by «${FORGE_SPOT.edited}»`);

  // The field opens only while a word is edited (component state); its markup is ForgeSpot's own.
  const fieldTag = /^(\w+)\./.exec(FORGE_SPOT.field)[1];
  const source = fs.readFileSync(path.join(__dirname, 'ForgeDrills.tsx'), 'utf8');
  assert.match(
    source,
    new RegExp(`<${fieldTag}\\s+className="${classesOf(FORGE_SPOT.field)[0]}"`),
    `the walk types into «${FORGE_SPOT.field}»`,
  );
});
