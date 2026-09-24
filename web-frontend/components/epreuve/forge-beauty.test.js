// node --test components/epreuve/forge-beauty.test.js
//
// WP-S6 — La Forge, beauty and clarity.
//
//   1. the head: the step label and «Test out this rule» are separate elements
//      («Step 3 of 6 · buildTest out this rule» ran together);
//   2. one human progress: the rule's staircase (6 steps in the rule's shape)
//      and a quiet «n of N» — no «Recognize · Word bank · 1/3», no «0/20»;
//   3. the surface is «La Forge», its chrome follows the language rule
//      (A1 en, A2 de, B1 fr); a rule change gets its small card;
//   4. the recap: each rule's shape, the step reached, what changed, two proof
//      lines and the next review — under one Garamond line, no tally;
//   5. the new CSS: tokens only (no hex), no strokes on tiles or shapes, the
//      footer band as wide as the content, a sticky top bar;
//   6. item-bank cues render in the learner's language when offered.

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

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const Ep = require('./Epreuve.tsx');
const Forge = require('./Forge.tsx');
const { FORGE_COPY, forgeCopy, fillForge } = require('@/lib/forge-copy.ts');
const P = require('@/lib/forge-progress.ts');
const { chromeLanguage } = require('@/lib/language-rule.ts');

const h = React.createElement;
const text = (html) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();

function renderHead(language, { rung = 2, rungName = 'build', testOut = true } = {}) {
  const fc = forgeCopy(language);
  return renderToStaticMarkup(
    h(Ep.EpShell, { language },
      h(Ep.EpTopbar, {
        groups: [{ total: 20, set: 0 }],
        cap: ['0/20', ''],
        middle: h(Forge.ForgeCount, { copy: fc, count: P.seanceCountText(fc, { length: 12, answered: 2, next: { position: 2, length: 12 } }) }),
      }),
      h(Forge.ForgeHead, {
        copy: fc,
        title: 'Genre et nombre',
        shape: 'square',
        rung,
        step: P.stepText(fc, rung, rungName),
        stairLabel: fillForge(fc.stair_label, { n: rung + 1, rung: fc.rungs[rungName] }),
        ruleLabel: 'Rule',
        onRule: () => undefined,
        testOut: testOut ? { onClick: () => undefined } : null,
      }),
    ),
  );
}

// ---------------------------------------------------------------------------
// 1 · the head
// ---------------------------------------------------------------------------

test('the step label and «Test out this rule» are separate, structured elements', () => {
  const html = renderHead('en');
  assert.match(html, /<p class="forge-head__step"><span>Step 3 of 6 · build<\/span><\/p>/);
  assert.match(html, /<button type="button" class="forge-head__test-out">Test out this rule<\/button>/);
  // The step's paragraph closes before the action starts: they never run together.
  const step = html.match(/<p class="forge-head__step">([\s\S]*?)<\/p>/)[1];
  assert.doesNotMatch(step, /Test out/);
  assert.doesNotMatch(text(html), /buildTest/);
});

// ---------------------------------------------------------------------------
// 2 · one human progress
// ---------------------------------------------------------------------------

test('the top bar reads «La Forge · 3 of 12», not the machine counter', () => {
  const html = renderHead('en');
  assert.match(html, /<span class="forge-count__name">La Forge<\/span><span class="forge-count__n">3 of 12<\/span>/);
  assert.doesNotMatch(html, /0\/20/);
  assert.doesNotMatch(html, /ep-stick/);
});

test('the staircase is six steps in the rule\'s shape: ink, colour, ghosts', () => {
  const html = renderHead('en', { rung: 2 });
  const stair = html.match(/<svg class="forge-stair"[^>]*>([\s\S]*?)<\/svg>/);
  assert.ok(stair, 'the staircase is drawn');
  assert.match(stair[0], /data-shape="square"/);
  assert.match(stair[0], /role="img" aria-label="The rule’s staircase: step 3 of 6, build"/);
  const states = [...stair[1].matchAll(/data-state="(\w+)"/g)].map((m) => m[1]);
  assert.deepEqual(states, ['done', 'done', 'current', 'todo', 'todo', 'todo']);
  assert.equal((stair[1].match(/<rect /g) || []).length, 6);
  assert.deepEqual(P.staircase(9), ['done', 'done', 'done', 'done', 'done', 'current']);
  assert.deepEqual(P.staircase('x'), ['current', 'todo', 'todo', 'todo', 'todo', 'todo']);
});

test('each rule has one of the three rule shapes (ink stays «done»)', () => {
  assert.equal(P.ruleShape({ category: 'Verbs' }), 'triangle');
  assert.equal(P.ruleShape({ category: 'Tenses' }), 'triangle');
  assert.equal(P.ruleShape({ category: 'Articles' }), 'square');
  assert.equal(P.ruleShape({ category: 'Agreement' }), 'square');
  assert.equal(P.ruleShape({ category: 'Pronouns' }), 'circle');
  assert.equal(P.ruleShape({ category: 'Negation' }), 'circle');
  assert.equal(P.ruleShape(null), 'circle');
});

test('the séance count is the item on screen of the séance, never 0', () => {
  assert.deepEqual(P.seanceCount({ length: 12, answered: 0, next: { position: 0, length: 12 } }), { n: 1, total: 12 });
  assert.deepEqual(P.seanceCount({ length: 12, answered: 5, next: { position: 5, length: 12 } }), { n: 6, total: 12 });
  assert.deepEqual(P.seanceCount({ length: 12, answered: 12, finished: true, next: null }), { n: 12, total: 12 });
  assert.equal(P.seanceCount(null), null);
});

test('the page draws the forge head instead of the eyebrow and concept row', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  const session = page.slice(page.indexOf('function SessionView('), page.indexOf('function ActionRow('));
  const forgeBranch = session.indexOf('{forge ? (');
  assert.ok(forgeBranch > 0, 'the head forks on the forge');
  assert.ok(session.indexOf('<ForgeHead', forgeBranch) > forgeBranch);
  // The legacy eyebrow (round · mode · i/n) only renders in the other branch.
  assert.ok(session.indexOf('<EpEyebrow', forgeBranch) > session.indexOf('<ForgeHead', forgeBranch));
  assert.match(session, /middle=\{forge \? <ForgeCount copy=\{fc\} count=\{seanceCountText\(fc, forge\)\} \/> : undefined\}/);
  // The «More practice» strip never sits over a forge séance.
  assert.match(page, /\{practiceMode && !forge && \(/);
  // One Garamond line: no lock headline, and the legacy rule panel in the sans.
  assert.match(session, /className=\{forge \? 'ep-sheet forge-sheet' : 'ep-sheet'\}/);
  assert.match(session, /\{activeLock && currentSubmitted && !forge && \(/);
});

// ---------------------------------------------------------------------------
// 3 · the language rule and the rule change
// ---------------------------------------------------------------------------

const EXPECTED = {
  en: { step: 'Step 3 of 6 · build', count: '3 of 12', action: 'Test out this rule', next: 'Next rule' },
  de: { step: 'Stufe 3 von 6 · bauen', count: '3 von 12', action: 'Diese Regel direkt prüfen', next: 'Nächste Regel' },
  fr: { step: 'Marche 3 sur 6 · construire', count: '3 sur 12', action: 'Passer l’épreuve de la règle', next: 'Règle suivante' },
};

for (const [level, control, language] of [['A1.1', 'en', 'en'], ['A2', 'de', 'de'], ['B1', 'en', 'fr'], ['B1.2', 'de', 'fr']]) {
  test(`a ${level} learner (${control}) reads La Forge's chrome in ${language}`, () => {
    const resolved = chromeLanguage(control, level);
    assert.equal(resolved, language);
    const html = renderHead(resolved);
    const fc = forgeCopy(resolved);
    const change = renderToStaticMarkup(
      h(Ep.EpShell, { language: resolved }, h(Forge.ForgeRuleChange, { copy: fc, title: 'Le passé composé', shape: 'triangle' })),
    );
    const want = EXPECTED[language];
    assert.ok(text(html).includes(want.step), text(html));
    assert.ok(text(html).includes(want.count));
    assert.ok(text(html).includes(want.action));
    assert.ok(text(change).includes(want.next));
    // «La Forge» is the place's name in every language.
    assert.ok(text(html).includes('La Forge'));
    // No other language's chrome leaks in.
    for (const [other, words] of Object.entries(EXPECTED)) {
      if (other === language) continue;
      assert.ok(!text(html).includes(words.action), `${language} shows ${other}'s «${words.action}»`);
    }
    // The rule's name is French content, marked as such.
    assert.match(html, /<p class="forge-head__rule" lang="fr">Genre et nombre<\/p>/);
  });
}

test('the surface is «La Forge» / «Forge today\'s rule» in the three tables', () => {
  assert.equal(FORGE_COPY.en.surface_action, 'Forge today’s rule');
  assert.equal(FORGE_COPY.de.surface_action, 'Regel des Tages schmieden');
  assert.equal(FORGE_COPY.fr.surface_action, 'Forger la règle du jour');
  for (const language of ['en', 'de', 'fr']) assert.equal(FORGE_COPY[language].surface_name, 'La Forge');
});

test('a rule change is the first item of another rule, never the séance\'s first', () => {
  assert.equal(P.ruleChanged(null, { position: 0, conceptId: 1 }), false);
  assert.equal(P.ruleChanged({ position: 0, conceptId: 1 }, { position: 1, conceptId: 2 }), true);
  assert.equal(P.ruleChanged({ position: 1, conceptId: 2 }, { position: 2, conceptId: 2 }), false);
  assert.equal(P.ruleChanged({ position: 1, conceptId: 2 }, { position: 1, conceptId: 2 }), false);
});

test('the rule-change card names the rule, draws its shape, and seats a coach', () => {
  const fc = forgeCopy('en');
  const html = renderToStaticMarkup(
    h(Ep.EpShell, { language: 'en' },
      h(Forge.ForgeRuleChange, { copy: fc, title: 'Le passé composé', shape: 'triangle', coach: { id: 'margaux_barman', name: 'Margaux' } }),
    ),
  );
  assert.match(html, /class="forge-change__shape" data-shape="triangle"/);
  assert.match(html, /<p class="forge-change__rule" lang="fr">Le passé composé<\/p>/);
  assert.match(html, /With Margaux/);
  assert.match(html, /ob-portrait/);
  // Sans: the card never adds a second Garamond headline.
  assert.doesNotMatch(html, /av2-headline/);
});

// ---------------------------------------------------------------------------
// 4 · the recap
// ---------------------------------------------------------------------------

const RECAP = {
  forge: {
    rules: [
      {
        concept_id: 7,
        rung: 3,
        rung_name: 'transform',
        stage_before: 'introduced',
        stage: 'practising',
        held_today: false,
        next_due: '2026-09-27T08:00:00+00:00',
        proof: [
          { fr: 'Une petite table blanche.', fixed: false },
          { fr: 'Des chaises vertes.', fixed: true },
          { fr: 'Un troisième qui ne se montre pas.', fixed: false },
        ],
      },
      { concept_id: 9, rung: 5, rung_name: 'free_use', stage_before: 'practising', stage: 'held', held_today: true, next_due: '2026-10-09T08:00:00+00:00', proof: [] },
      { concept_id: 11, rung: 1, rung_name: 'discriminate', stage_before: 'practising', stage: 'practising', next_due: '2026-09-20T08:00:00+00:00', proof: [] },
    ],
  },
};
const CONCEPTS = [
  { id: 7, category: 'Agreement', name: 'Gender and number', title_fr: 'Genre et nombre' },
  { id: 9, category: 'Verbs', name: 'Present of être', title_fr: 'Le présent d’être' },
  { id: 11, category: 'Negation', name: 'ne … pas', title_fr: 'La négation' },
];
const NOW = new Date('2026-09-24T12:00:00+02:00');

test('the recap rows carry the shape, the step reached, what changed, proof and the next review', () => {
  const fc = forgeCopy('en');
  const rows = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, fc, 'en', NOW);
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map((r) => r.shape), ['square', 'triangle', 'circle']);
  assert.equal(rows[0].step, 'Step 4 of 6 · transform');
  assert.equal(rows[0].change, 'introduced → proficient');
  assert.equal(rows[0].proof.length, 2);
  assert.match(rows[0].due, /^Next review Sun,? 27 Sept?/);
  assert.equal(rows[1].change, 'Held from today');
  assert.equal(rows[2].change, 'Still proficient');
  assert.equal(rows[2].due, 'Next review today');
  const de = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, forgeCopy('de'), 'de', NOW);
  assert.equal(de[0].change, 'eingeführt → sicher');
  const fr = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, forgeCopy('fr'), 'fr', NOW);
  assert.equal(fr[1].change, 'Tenue dès aujourd’hui');
});

test('the recap renders one card per rule with its staircase, and no tally', () => {
  const fc = forgeCopy('en');
  const rows = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, fc, 'en', NOW);
  const html = renderToStaticMarkup(
    h(Ep.EpShell, { language: 'en' },
      h(Ep.EpBatStage, { title: fc.recap_title }),
      h(Forge.ForgeRecapRules, { copy: fc, rows, proofRight: 'right', proofFixed: 'fixed' }),
    ),
  );
  assert.equal((html.match(/class="forge-recap__rule"/g) || []).length, 3);
  assert.equal((html.match(/class="forge-stair"/g) || []).length, 3);
  assert.match(html, /Today’s rules, forged\./);
  assert.match(html, /introduced → proficient/);
  assert.match(html, /<span lang="fr">Une petite table blanche\.<\/span>/);
  assert.doesNotMatch(html, /Un troisième/);
  assert.doesNotMatch(html, /ep-tally/);
  // One Garamond line: the headline; the rules are set in the sans.
  assert.equal((html.match(/class="av2-headline/g) || []).length, 1);

  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  const recap = page.slice(page.indexOf('function RecapModal('), page.indexOf('function recapActionLabel('));
  assert.match(recap, /\{forgeRows\.length \? \(/);
  assert.ok(recap.indexOf('<ForgeRecapRules') < recap.indexOf('<EpTally'), 'the tally is only the legacy branch');
  assert.match(recap, /title=\{forgeRows\.length \? fc\.recap_title : undefined\}/);
});

// ---------------------------------------------------------------------------
// 5 · the CSS
// ---------------------------------------------------------------------------

function styleBlock(source) {
  const start = source.indexOf('<style jsx global>{`');
  return source.slice(start, source.indexOf('`}</style>', start));
}

test('the forge CSS is tokens only and draws no strokes', () => {
  const css = styleBlock(fs.readFileSync(path.join(__dirname, 'Forge.tsx'), 'utf8'));
  assert.ok(css.length > 500);
  assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, 'no hex colour');
  assert.doesNotMatch(css, /rgba?\(|hsla?\(/, 'no raw colour');
  assert.doesNotMatch(css, /\boutline\s*:/);
  for (const match of css.matchAll(/\bstroke(?:-width)?\s*:\s*([^;]+);/g)) assert.equal(match[1].trim(), 'none');
  for (const match of css.matchAll(/\bborder(?:-[a-z]+)?\s*:\s*([^;]+);/g)) {
    if (/radius/.test(match[0])) continue;
    assert.match(match[1].trim(), /^(0|none)$/, match[0]);
  }
});

test('Épreuve: stroke-less word tiles, a full-width footer band, a sticky top bar, no gap', () => {
  const source = fs.readFileSync(path.join(__dirname, 'Epreuve.tsx'), 'utf8');
  const css = styleBlock(source);
  assert.match(css, /\.av2 \.ep-slug\.av2-tile \{ border: 0; \}/);
  assert.match(css, /\.av2 \.ep-slug\.av2-tile\[data-state='placed'\] \{ background: var\(--av2-blue\);/);
  assert.doesNotMatch(css, /\.ep-slug[^{]*\{[^}]*border(?:-color)?\s*:\s*(?![\s0])[^;}]+/);
  const foot = css.match(/\.av2 \.ep-foot \{([^}]*)\}/)[1];
  assert.match(foot, /max-width: none;/);
  assert.match(foot, /width: calc\(100% \+ 2 \* var\(--av2-gutter\)\);/);
  assert.match(foot, /margin: auto calc\(-1 \* var\(--av2-gutter\)\) 0;/);
  const top = css.match(/\.av2 \.ep-top \{([^}]*)\}/)[1];
  assert.match(top, /position: sticky;/);
  assert.match(top, /top: 0;/);
  assert.match(top, /background: var\(--av2-paper\);/);
  assert.match(css, /\.av2 \.ep-sheet > \.ep-feedback:last-child \{ flex: 0 0 auto; \}/);
  // The WP-S6 additions use tokens only.
  const additions = css.split('WP-S6').slice(1).map((chunk) => chunk.slice(0, 900)).join('\n');
  assert.doesNotMatch(additions, /#[0-9a-fA-F]{3,8}\b/);
});

// ---------------------------------------------------------------------------
// 6 · cues in the learner's language
// ---------------------------------------------------------------------------

test('a bank cue renders in the learner\'s language when the payload offers it', () => {
  const pair = {
    prompt: 'Which sentence says: "the table"',
    prompt_l10n: { en: 'Which sentence says: "the table"', de: 'Welcher Satz bedeutet: „the table“', fr: 'Quelle phrase veut dire : « the table »' },
  };
  assert.equal(P.localizedCue(pair, 'prompt', 'de'), 'Welcher Satz bedeutet: „the table“');
  assert.equal(P.localizedCue(pair, 'prompt', 'fr'), 'Quelle phrase veut dire : « the table »');
  assert.equal(P.cueIsLocalized(pair, 'prompt', 'de'), true);
  // An LLM item (a French sentence to judge) has no table: its own string, French.
  const judged = { prompt: 'La table est petite.' };
  assert.equal(P.localizedCue(judged, 'prompt', 'de'), 'La table est petite.');
  assert.equal(P.cueIsLocalized(judged, 'prompt', 'de'), false);

  const html = renderToStaticMarkup(h(Ep.EpShell, { language: 'de' }, h(Ep.EpPrompt, { lang: 'de' }, P.localizedCue(pair, 'prompt', 'de'))));
  assert.match(html, /<div class="av2-headline ep-line" lang="de">Welcher Satz/);

  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.match(page, /localizedCue\(item, 'prompt', cueLanguage\)/);
  assert.match(page, /localizedCue\(item, 'instruction', cueLanguage\)/);
  assert.match(page, /localizedCue\(produce, 'prompt', cueLanguage\)/);
});
