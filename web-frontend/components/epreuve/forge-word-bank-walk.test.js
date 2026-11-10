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
const os = require('node:os');
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
/**
 * What the walk knows about La Forge (lib/forge-walk.mjs): its selectors and the decision
 * whether a visit that stopped changing has ended or stalled. A module of its own, outside
 * e2e/, so that these tests (and scripts/loop/red_green.py) can run and prove it.
 */
async function forgeWalk() {
  const file = path.join(WEB_ROOT, 'lib/forge-walk.mjs');
  assert.ok(fs.existsSync(file), 'the walk\'s La Forge selectors and stall decision are a unit-tested module: lib/forge-walk.mjs');
  return import(pathToFileURL(file).href);
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
  const { FORGE_REPAIR } = await forgeWalk();
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
  const { FORGE_SPOT } = await forgeWalk();
  assert.ok(FORGE_SPOT, 'the walk defines how it answers «Trouve l’erreur» (lib/forge-walk.mjs FORGE_SPOT)');
  const Drills = require('./ForgeDrills.tsx');
  const { forgeCopy } = require('@/lib/forge-copy.ts');
  const copy = forgeCopy('fr');
  const render = (edits) =>
    renderToStaticMarkup(
      h(Ep.EpShell, { language: 'fr' }, h(Drills.ForgeSpot, { sentence: 'Elle n’a pas une idée.', edits, onEdits: () => undefined, copy })),
    );

  const wordTag = /^(\w+)\./.exec(FORGE_SPOT.word)[1];
  const [wordCls] = classesOf(FORGE_SPOT.word);
  const fresh = tagsWithClass(render({}), wordTag, wordCls);
  assert.ok(fresh.length >= 4, `the walk taps a word by «${FORGE_SPOT.word}»`);
  assert.ok(fresh.every((attrs) => !/\sdisabled=/.test(attrs)), 'the words of an open item can be tapped');

  const edited = tagsWithClass(render({ 3: 'd’' }), wordTag, classesOf(FORGE_SPOT.edited)[0]).filter((attrs) =>
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

test('the walk corrects a judged sentence by the classes ForgeFollowUp renders', async () => {
  // After a right «Needs fixing» the sheet's «Continue» waits for «Correct the sentence»
  // (pages/atelier.tsx `followGate`): a Forge visit that cannot check it stands still.
  const { WORD_BANK_TILE } = await walkDriver();
  const { FORGE_FOLLOW } = await forgeWalk();
  assert.ok(FORGE_FOLLOW, 'the walk defines how it answers «Correct the sentence» (lib/forge-walk.mjs FORGE_FOLLOW)');
  const { ForgeFollowUp, FOLLOW_UP_EMPTY } = require('./ForgeFollowUp.tsx');
  const spec = {
    kind: 'correct_it',
    sourceFr: 'Lila demande un café à son ami.',
    goalNative: null,
    correctedFr: 'Lila a demandé un café à son ami.',
    accepted: ['Lila a demandé un café à son ami.'],
  };
  const render = (followUp, draft = FOLLOW_UP_EMPTY) =>
    renderToStaticMarkup(h(Ep.EpShell, { language: 'de' }, h(ForgeFollowUp, { followUp, draft, onDraft: () => {} })));
  const selector = parseTileSelector(WORD_BANK_TILE);
  const openCls = classesOf(FORGE_FOLLOW.open)[0];
  const isOpen = (html) => tagsWithClass(html, 'section', openCls).some((attrs) => /data-outcome="open"/.test(attrs));

  // Tiles: the walk taps them in the follow-up's bank, then the follow-up's own check.
  const tiles = render({ ...spec, options: ['Lila', 'a', 'demandé', 'un café', 'à son ami.'] }, { ...FOLLOW_UP_EMPTY, placed: [0] });
  assert.ok(isOpen(tiles), `the open follow-up is «${FORGE_FOLLOW.open}»: ${tiles}`);
  assert.deepEqual(tappable(tiles, selector), ['a', 'demandé', 'un café', 'à son ami.'], 'the walk taps the follow-up\'s idle tiles');
  const [actions, bar] = classesOf(FORGE_FOLLOW.check);
  const checks = [...tiles.matchAll(new RegExp(`<div class="[^"]*\\b${actions}\\b[^"]*">([\\s\\S]*?)</div>`, 'g'))]
    .flatMap((m) => tagsWithClass(m[1], 'button', bar));
  assert.equal(checks.length, 1, `the walk checks by «${FORGE_FOLLOW.check}»: ${tiles}`);
  assert.ok(!/\sdisabled=/.test(checks[0]), 'with a tile set, the check can be tapped');

  // A field: the walk retypes the quoted sentence into it.
  const field = render({ ...spec, options: null });
  assert.equal(tagsWithClass(field, 'textarea', classesOf(FORGE_FOLLOW.field)[0]).length, 1, `the walk types into «${FORGE_FOLLOW.field}»: ${field}`);
  const quote = new RegExp(`<blockquote class="[^"]*\\b${classesOf(FORGE_FOLLOW.quote)[0]}\\b[^"]*"[^>]*>([\\s\\S]*?)</blockquote>`).exec(field);
  assert.ok(quote, `the walk reads the sentence from «${FORGE_FOLLOW.quote}»`);
  assert.equal(quote[1].replace(/<span class="av2-sr">[\s\S]*?<\/span>/, '').replace(/<[^>]+>/g, '').replace(/&#x27;/g, "'").replace(/ | /g, ' ').trim(), spec.sourceFr);

  // Once checked the step is settled: nothing is left open for the walk.
  assert.ok(!isOpen(render({ ...spec, options: null }, { ...FOLLOW_UP_EMPTY, text: 'x', outcome: 'revealed' })), 'a settled follow-up is not open');
});

test('the walk answers a La Forge judgement and a pick by the choice and the check the page renders', () => {
  // «Ist der Satz richtig?» / «Is this sentence correct?» (pages/atelier.tsx) offers its
  // labels as EpOpt; the walk taps `.av2-choice:not([disabled])` and then the primary check
  // (an EpBar). Both are the components' own classes.
  const html = renderToStaticMarkup(
    h(Ep.EpShell, { language: 'en' },
      h(Ep.EpOpts, null, h(Ep.EpOpt, null, 'Correct'), h(Ep.EpOpt, null, 'Needs fixing')),
      h(Ep.EpBar, null, 'Check')),
  );
  assert.equal(tagsWithClass(html, 'button', 'av2-choice').filter((attrs) => !/\sdisabled=/.test(attrs)).length, 2, `the walk taps a judgement by .av2-choice: ${html}`);
  assert.equal(tagsWithClass(html, 'button', 'av2-btn--primary').length, 1, `the walk checks by .av2-btn--primary: ${html}`);
});

// The even-day La Forge visit used to stop when the screen stood still for 10 s
// (`if (entry && sameFor > 40) break;`) with no finding and no screenshot, whatever the
// screen was. A Forge step the walk had no hand for stayed invisible until a later day's
// own grammar step opened the same kind of item. These tests drive the walk's real visit
// loop (LearnerWalk.playJourney) over a stand-in page that shows one fixed screen.

/** The fields of a driver snapshot the visit loop reads; `over` is the screen under test. */
function stillScreen(over) {
  return {
    url: '/atelier?mode=forge', text: 'La Forge · Build: "We are 50 years old." Tap the words', nonFrText: '',
    buttons: [{ text: 'Check', cls: 'ep-bar', disabled: true, y: 700, h: 44 }], choices: 0, whoSaid: 0, tiles: 0, tappableTiles: 0, tilesBox: 0, textarea: 0, dictation: 0, match: 0,
    goal: [], bodyLg: [], headline: [], stepLabel: '', dataStep: [], graded: [], connection: [], dataStates: [],
    reader: [], thread: 0, recap: 0, castIntro: 0, homeDone: false, forgeStep: 0, pending: false, epFeedback: [],
    frTexts: [], threadCue: '', fieldEnabled: false, layout: {}, theme: 'light', scrollW: 375, innerW: 375,
    ...over,
  };
}

async function visitFindings(screen) {
  const { LearnerWalk } = await import(pathToFileURL(path.join(WEB_ROOT, 'e2e/lib/learner-walk.mjs')).href);
  // A page that finds nothing to tap and never changes: every locator is empty.
  const none = new Proxy(function none() {}, {
    get: (_, key) => (key === 'count' ? async () => 0 : key === 'then' ? undefined : none),
    apply: () => none,
  });
  const page = {
    goto: async () => {},
    locator: () => none,
    evaluate: async () => screen,
    emulateMedia: async () => {},
    screenshot: async () => {},
  };
  const failed = [];
  const shots = { root: os.tmpdir(), list: [] };
  const walk = new LearnerWalk({
    page,
    findings: { check: (name, ok, detail, where) => ok || failed.push({ name, detail, where }) },
    outDir: fs.mkdtempSync(path.join(os.tmpdir(), 'forge-visit-')),
    lang: 'en', level: 'A2', stack: { web: 'http://walk.invalid' }, shots, scale: 1,
  });
  await walk.playJourney({ maxSeconds: 30, entry: '/atelier?mode=forge', label: 'forge-' });
  return { failed, shots: shots.list };
}

test('the stall decision of a Forge visit: stuck on an exercise is a stall, any other quiet end is not', async () => {
  const { forgeVisitEnd, FORGE_VISIT_QUIET } = await forgeWalk();
  const exercise = { forgeExercise: true, pending: false, text: 'La Forge · Build: "We are 50 years old." Tap the words' };
  // Still within the quiet period: the visit goes on, whatever is on screen.
  assert.equal(forgeVisitEnd(exercise, FORGE_VISIT_QUIET), null);
  assert.equal(forgeVisitEnd(exercise, 3), null);
  // Quiet for 10 s on an exercise nobody answered: a stall that names the screen.
  const stalled = forgeVisitEnd(exercise, FORGE_VISIT_QUIET + 1);
  assert.equal(stalled.stalled, true, 'an exercise the walk could not get past is a stall');
  assert.match(stalled.detail, /Build: "We are 50 years old\."/);
  assert.match(stalled.detail, /10s/);
  // The séance simply has nothing left: an end, not a stall.
  const empty = forgeVisitEnd({ forgeExercise: false, pending: false, text: 'La Forge · Rien à faire pour le moment' }, 41);
  assert.deepEqual(empty && empty.stalled, false);
  // An exercise the server is still working on is waiting, not stuck.
  assert.equal(forgeVisitEnd({ ...exercise, pending: true }, 41).stalled, false);
});

test('a Forge visit that stops on an exercise it cannot answer fails the walk, with a screenshot', async () => {
  const [stalled, plain, waiting] = await Promise.all([
    visitFindings(stillScreen({ forgeExercise: true })),
    visitFindings(stillScreen({ forgeExercise: false, text: 'La Forge · Rien à faire pour le moment' })),
    visitFindings(stillScreen({ forgeExercise: true, pending: true })),
  ]);
  const ways = stalled.failed.filter((f) => f.name === 'a-way-forward');
  assert.equal(ways.length, 1, `a stall on a La Forge exercise is a finding: ${JSON.stringify(stalled.failed)}`);
  assert.match(ways[0].detail, /Build: "We are 50 years old\."/, 'the finding names the screen');
  assert.ok(stalled.shots.some((shot) => shot.kind === 'stuck'), 'the stall is shot');
  // Not every quiet end is a stall: no exercise on screen, or one the server is still working on.
  assert.deepEqual(plain.failed, [], 'a visit that ends on a screen with no exercise is not a finding');
  assert.deepEqual(waiting.failed, [], 'an exercise waiting on the server is not stuck');
});
