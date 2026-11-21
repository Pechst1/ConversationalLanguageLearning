// node --test components/cahiers/cahier-rule-title.test.js
//
// #561 (root cause #522): one rule, one name. The rule card, the recall headers and
// La Forge call a rule by its title in the learner's chrome language
// (`concept_title(concept, language)`, sent as `title_native`). The re-test of
// 10 Nov found the Cahier's rule list, its rule page and the Éclair pair label
// still printing `title_fr` («Je suis, tu es : les pronoms et être») to a German
// learner who had just met «Ich bin, du bist: Subjektpronomen und être».
//   1. the Cahier's rule list and rule page name the rule in the chrome language
//      (de, en), and in French for French chrome;
//   2. the Éclair pair label on the grammar map does the same;
//   3. the guard: no learner-facing component under pages/ or components/cahiers/
//      reads `title_fr` outside a fixed list of reviewed exceptions.

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
const stub = (request, exports) => {
  const file = Module._resolveFilename(request, module, false);
  require.cache[file] = { id: file, filename: file, loaded: true, exports };
};
const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

// The page reads its data through SWR and its place through the router: hand it
// the notebook rows (and its rule page) as SWR's answer, so the page is what is tested.
const swrData = { notebook: [], detail: null };
stub('swr', {
  __esModule: true,
  default: (key) => {
    const name = Array.isArray(key) ? key[0] : key;
    const data = name === '/grammar/notebook' ? swrData.notebook : name === '/grammar/notebook/detail' ? swrData.detail : undefined;
    return { data, error: undefined, isLoading: false, mutate: async () => undefined };
  },
});
const routerQuery = { value: {} };
stub('next/router', {
  __esModule: true,
  default: { push: async () => true, replace: async () => true },
  useRouter: () => ({ push: async () => true, replace: async () => true, query: routerQuery.value, pathname: '/grammar' }),
});
stub('next/head', { __esModule: true, default: () => null });

const learnerLanguage = require('@/lib/learner-language.ts');
const chrome = { value: 'de' };
learnerLanguage.useChromeLanguage = () => chrome.value;

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

// The page opens a rule from the URL in an effect, which a static render never
// runs: hand the surface its selected rule as the first `useState(null)` (the
// selected id) instead.
const seed = { selectedId: null };
const realUseState = React.useState;
React.useState = (initial) => {
  if (seed.selectedId !== null && initial === null) {
    const value = seed.selectedId;
    seed.selectedId = null;
    return [value, () => {}];
  }
  return realUseState(initial);
};
const { GrammarNotebookSurface } = require('../../pages/grammar.tsx');
const GM = require('./GrammarMap.tsx');

const h = React.createElement;

// FR2_A11_ETRE's three titles, as the walk of 6 Nov saw them.
const TITLES = {
  fr: 'Je suis, tu es : les pronoms et être',
  de: 'Ich bin, du bist: Subjektpronomen und être',
  en: 'I am, you are: subject pronouns and être',
};

function notebookRow(language) {
  return {
    id: 11,
    external_id: 'FR2_A11_ETRE',
    language: 'fr',
    name: 'Subject pronouns and être',
    display_title: 'Subject pronouns and être',
    title_fr: TITLES.fr,
    // The server's `concept_title(concept, chrome language)` (#561).
    title_native: TITLES[language],
    level: 'A1',
    category: 'verbs',
    is_foundation: true,
    active: true,
    mastery: 2,
    state: 'in_arbeit',
    state_label: 'En route',
    stage: 'practising',
    level_band: 'A1.1',
    sub_band: 'A1.1',
    due_errata_count: 0,
    recent_errata_count: 1,
  };
}

function renderCahier(language, { page = false } = {}) {
  chrome.value = language;
  const row = notebookRow(language);
  swrData.notebook = [row];
  swrData.detail = page ? { ...row, main_traps: [], anchor_examples: [], exercise_tags: [], due_errata: [], recent_errata: [] } : null;
  routerQuery.value = page ? { concept: String(row.id) } : {};
  seed.selectedId = page ? row.id : null;
  return renderToStaticMarkup(h(GrammarNotebookSurface, { embedded: true }));
}

const rowTitles = (html) => [...html.matchAll(/<span class="nb-row__title"[^>]*>([^<]*)<\/span>/g)].map((m) => m[1]);
const unescape = (text) => text.replace(/&#x27;/g, "'").replace(/&amp;/g, '&');

// ---------------------------------------------------------------------------
// 1 · the Cahier's rule list and rule page
// ---------------------------------------------------------------------------

for (const language of ['de', 'en']) {
  test(`the Cahier's rule list names the rule as the rule card does, in ${language} chrome`, () => {
    const titles = rowTitles(renderCahier(language)).map(unescape);
    assert.deepEqual(
      titles,
      [TITLES[language]],
      `a ${language} learner's Cahier list says ${JSON.stringify(titles)}, the rule card «${TITLES[language]}»`,
    );
  });

  test(`the Cahier's rule page is headed by the rule card's title, in ${language} chrome`, () => {
    const html = renderCahier(language, { page: true });
    const heading = html.match(/<h2 class="av2-headline av2-headline--title"( lang="(\w+)")?>([^<]*)<\/h2>/);
    assert.ok(heading, 'the rule page has no heading');
    assert.equal(unescape(heading[3]), TITLES[language], `a ${language} learner's rule page is headed «${unescape(heading[3])}»`);
    assert.equal(heading[2], language, 'the heading is marked as the language it is written in');
  });
}

test('a French-chrome learner still reads the French title, marked lang="fr"', () => {
  assert.deepEqual(rowTitles(renderCahier('fr')).map(unescape), [TITLES.fr]);
  assert.match(renderCahier('fr'), /<span class="nb-row__title" lang="fr">/);
  const html = renderCahier('fr', { page: true });
  assert.match(html, /<h2 class="av2-headline av2-headline--title" lang="fr">Je suis, tu es : les pronoms et être<\/h2>/);
});

// ---------------------------------------------------------------------------
// 2 · the Éclair pair label
// ---------------------------------------------------------------------------

function mapPayload(language) {
  const rules = [
    { concept_id: 1, title_fr: 'Les articles définis', title_native: { de: 'Bestimmte Artikel', en: 'Definite articles', fr: 'Les articles définis' }[language] },
    { concept_id: 2, title_fr: 'Les articles indéfinis', title_native: { de: 'Unbestimmte Artikel', en: 'Indefinite articles', fr: 'Les articles indéfinis' }[language] },
  ];
  return {
    catalog: 'v2',
    bands: [{ band: 'A1.1', rules: rules.map((rule) => ({ ...rule, category: 'Articles', stage: 'introduced', rung: 1 })) }],
    eclair: { unlocked: true, pairs: [{ pair: '1-2', concept_ids: [1, 2], rules, best: 0, plays: 0 }] },
    features: { combo: true, eclair: true, grammar_map: true, mastery_rewards: true },
  };
}

function eclairLabel(language) {
  const html = renderToStaticMarkup(
    h(GM.GrammarMapView, { payload: mapPayload(language), language, selectedId: null, onSelect: () => undefined, onOpenPage: () => undefined }),
  );
  const match = html.match(/<span class="gm-eclair__names"( lang="(\w+)")?>([^<]*)<\/span>/);
  assert.ok(match, 'the map shows no Éclair pair');
  return { text: unescape(match[3]), lang: match[2] };
}

test('the Éclair pair label names both rules in the chrome language', () => {
  assert.deepEqual(eclairLabel('de'), { text: 'Bestimmte Artikel oder Unbestimmte Artikel', lang: 'de' });
  assert.deepEqual(eclairLabel('en'), { text: 'Definite articles or Indefinite articles', lang: 'en' });
  assert.deepEqual(eclairLabel('fr'), { text: 'Les articles définis ou Les articles indéfinis', lang: 'fr' });
});

// ---------------------------------------------------------------------------
// 3 · the guard
// ---------------------------------------------------------------------------

/**
 * Every `title_fr` a learner-facing file under pages/ or components/cahiers/ may
 * read, with why. A rule's name goes through `ruleTitle` (lib/grammar-map.ts) or
 * La Forge's `displayConceptTitle`, which put the chrome-language title first. The
 * other entries are not rule names: an episode's, a scene's or a keepsake's title
 * is French content at every level. This list may only shrink; a new rule title
 * read straight from `title_fr` is the bug of #561 coming back.
 */
const ALLOWED_TITLE_FR = [
  { file: 'pages/atelier.tsx', line: 'concept.title_native || concept.title_fr', why: 'La Forge’s rule title helper: chrome title first' },
  { file: 'pages/atelier.tsx', line: "native !== String(concept?.title_fr || '')", why: 'the lang of that helper’s title' },
  { file: 'pages/atelier.tsx', line: 'now localizes rule_panel.title, and title_fr is', why: 'a comment' },
  { file: 'pages/atelier.tsx', line: '|| activeConcept?.title_fr', why: 'the French miss line under rule_panel.title (#522)' },
  { file: 'pages/atelier.tsx', line: '?.title_fr || req.label', why: 'the legacy produce exercise’s French requirement chips (#522)' },
  { file: 'pages/quartier.tsx', line: 'title: s.title_fr,', why: 'a Quartier scene title: French content' },
  { file: 'pages/quartier.tsx', line: 'today.page.title_fr ||', why: 'the episode title: French content', count: 2 },
  { file: 'components/cahiers/JournalTab.tsx', line: 'entry.reveal.title_fr', why: 'a journal reveal’s French title', count: 2 },
];

function sourceFiles(dir) {
  const out = [];
  for (const entry of fs.readdirSync(path.join(WEB_ROOT, dir), { withFileTypes: true })) {
    const relative = path.posix.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...sourceFiles(relative));
    else if (/\.tsx?$/.test(entry.name) && !/\.test\./.test(entry.name)) out.push(relative);
  }
  return out;
}

function titleFrReads() {
  const reads = [];
  for (const file of [...sourceFiles('pages'), ...sourceFiles('components/cahiers')]) {
    fs.readFileSync(path.join(WEB_ROOT, file), 'utf8').split('\n').forEach((text, index) => {
      const count = (text.match(/\btitle_fr\b/g) || []).length;
      if (count) reads.push({ file, line: index + 1, text: text.trim(), count });
    });
  }
  return reads;
}

test('no learner-facing component under pages/ or components/cahiers/ names a rule from title_fr', () => {
  const unlisted = titleFrReads().filter(
    (read) => !ALLOWED_TITLE_FR.some((allowed) => allowed.file === read.file && read.text.includes(allowed.line)),
  );
  assert.deepEqual(
    unlisted.map((read) => `${read.file}:${read.line}  ${read.text}`),
    [],
    'These lines read `title_fr` directly. A rule is named with ruleTitle(rule, language) from '
      + 'lib/grammar-map.ts (the chrome-language title the rule card shows); French content that is '
      + 'not a rule name goes on ALLOWED_TITLE_FR with its reason.',
  );
});

test('every allowed title_fr read still exists, as often as listed (the list only shrinks)', () => {
  const reads = titleFrReads();
  const stale = ALLOWED_TITLE_FR.filter((allowed) => {
    const found = reads
      .filter((read) => read.file === allowed.file && read.text.includes(allowed.line))
      .reduce((sum, read) => sum + read.count, 0);
    return found !== (allowed.count || 1);
  });
  assert.deepEqual(stale.map((allowed) => `${allowed.file}: ${allowed.line}`), [], 'update or drop these entries');
});
