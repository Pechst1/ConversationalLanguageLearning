// node --test components/epreuve/forge-beauty.test.js
//
// WP-S6 — La Forge, beauty and clarity; owner, 2026-10-18 — less on every
// screen («too much text»), a progress one can read.
//
//   1. the head: the rule's name once, its level («Level 3», a tap explains
//      it) and «La règle» — no step line, no épreuve link, no surface name;
//   2. one human progress: a quiet bar and «3/12» in the top bar; the rule's
//      level as six plain segments, not a staircase of shapes;
//   3. the chrome follows the language rule (A1 en, A2 de, B1 fr);
//   4. the screen: the goal comes before the box the answer goes in, the
//      «Manqué» note, «sûr / pas sûr» and the épreuve link are gone from it;
//   5. the recap: each rule's level, what changed, two proof lines, the next
//      review — and the épreuve, offered every few days;
//   6. the new CSS: tokens only (no hex), no strokes, the footer band as wide
//      as the content, a sticky top bar;
//   7. item-bank cues render in the learner's language when offered.

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
const { FORGE_COPY, forgeCopy } = require('@/lib/forge-copy.ts');
const P = require('@/lib/forge-progress.ts');
const { chromeLanguage } = require('@/lib/language-rule.ts');

const h = React.createElement;
const text = (html) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
const SESSION = PAGE.slice(PAGE.indexOf('function SessionView('), PAGE.indexOf('function ActionRow('));

function renderHead(language, { rung = 2, eyebrow = null } = {}) {
  const fc = forgeCopy(language);
  const forge = { length: 12, answered: 2, next: { position: 2, length: 12 } };
  const count = P.seanceCount(forge);
  return renderToStaticMarkup(
    h(Ep.EpShell, { language },
      h(Ep.EpTopbar, {
        groups: [{ total: 20, set: 0 }],
        cap: ['0/20', ''],
        middle: h(Forge.ForgeProgress, { n: count.n, total: count.total, label: P.seanceCountText(fc, forge) }),
        run: 0,
      }),
      h(Forge.ForgeHead, {
        copy: fc,
        title: 'Le passé composé avec avoir',
        rung,
        eyebrow,
        ruleLabel: 'Rule',
        onRule: () => undefined,
      }),
    ),
  );
}

// ---------------------------------------------------------------------------
// 1 · the head
// ---------------------------------------------------------------------------

test('the head is the rule once, its level and «La règle»: no step line, no épreuve link', () => {
  const html = renderHead('en');
  assert.equal((html.match(/Le passé composé avec avoir/g) || []).length, 1, 'the rule is named once');
  assert.match(html, /<p class="forge-head__rule" lang="fr">Le passé composé avec avoir<\/p>/);
  assert.match(html, /<button type="button" class="forge-head__level" aria-expanded="false" aria-label="Your level on this rule: 3 of 6\. Tap to see how it works\.">/);
  assert.match(html, /<span class="forge-head__level-n">Level 3<\/span>/);
  assert.match(text(html), /Rule/);
  for (const gone of ['Step 3 of 6', 'Test out', 'Next rule', 'With ', 'La Forge']) {
    assert.ok(!text(html).includes(gone), `«${gone}» is gone from the screen`);
  }
  assert.doesNotMatch(html, /forge-stair|forge-combo|forge-count|forge-change/);
});

test('a test-out names itself where the level was', () => {
  const html = renderHead('en', { eyebrow: forgeCopy('en').test_out_eyebrow });
  assert.match(html, /<p class="forge-head__eyebrow">Test out<\/p>/);
  assert.doesNotMatch(html, /forge-head__level/);
});

test('the level explains itself in a sentence, in every language', () => {
  for (const language of ['en', 'de', 'fr']) {
    const explain = FORGE_COPY[language].level_explain;
    assert.match(explain, /1/);
    assert.match(explain, /6/);
  }
  // #402: a miss keeps the level (owner decision #88), so the default legend says so;
  // «un de moins» is only for a server whose rule takes a level away (`level_explain_down`).
  assert.equal(FORGE_COPY.fr.level_explain, 'Ton niveau sur cette règle, de 1 à 6. Juste : un de plus. Faux : le niveau reste, et la règle revient bientôt.');
  assert.equal(FORGE_COPY.fr.level_explain_down, 'Ton niveau sur cette règle, de 1 à 6. Juste : un de plus. Faux : un de moins, et la règle revient bientôt.');
  // The head explains it unasked the first time (a device remembers it).
  const source = fs.readFileSync(path.join(__dirname, 'Forge.tsx'), 'utf8');
  assert.match(source, /const LEVEL_EXPLAINED = 'forge\.level-explained';/);
  assert.match(source, /\{explain && !eyebrow && <p className="forge-head__explain">\{levelExplain\(copy, levelRule\)\}<\/p>\}/);
});

// ---------------------------------------------------------------------------
// 2 · one human progress
// ---------------------------------------------------------------------------

test('the top bar is a quiet bar and «3/12», not the machine counter or the surface name', () => {
  const html = renderHead('en');
  assert.match(html, /role="progressbar" aria-label="3 of 12" aria-valuemin="0" aria-valuemax="12" aria-valuenow="3"/);
  assert.match(html, /<span class="forge-progress__fill" style="width:25%"><\/span>/);
  assert.match(html, /<span class="forge-progress__n" aria-hidden="true">3\/12<\/span>/);
  assert.doesNotMatch(html, /0\/20/);
  assert.doesNotMatch(html, /ep-stick/);
  assert.doesNotMatch(text(html), /La Forge/);
});

test('the level is six plain segments lit up to the rule’s own', () => {
  assert.deepEqual(P.levelSegments(2), [true, true, true, false, false, false]);
  assert.deepEqual(P.levelSegments(9), [true, true, true, true, true, true]);
  assert.deepEqual(P.levelSegments('x'), [true, false, false, false, false, false]);
  assert.equal(P.levelText(forgeCopy('en'), 2), 'Level 3');
  assert.equal(P.levelText(forgeCopy('fr'), 5), 'Niveau 6');
  assert.equal(P.levelText(forgeCopy('de'), -1), 'Stufe 1');
});

test('each rule keeps one of the three rule shapes for the grammar map (ink stays «done»)', () => {
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
  const forgeBranch = SESSION.indexOf('{forge ? (');
  assert.ok(forgeBranch > 0, 'the head forks on the forge');
  assert.ok(SESSION.indexOf('<ForgeHead', forgeBranch) > forgeBranch);
  // The legacy eyebrow (round · mode · i/n) only renders in the other branch.
  assert.ok(SESSION.indexOf('<EpEyebrow', forgeBranch) > SESSION.indexOf('<ForgeHead', forgeBranch));
  assert.match(SESSION, /<ForgeProgress n=\{forgeProgress\?\.n \?\? 0\} total=\{forgeProgress\?\.total \?\? 0\} label=\{seanceCountText\(fc, forge, activeItemId\)\} \/>/);
  // The «More practice» strip never sits over a forge séance.
  assert.match(PAGE, /\{practiceMode && !forge && \(/);
  // One Garamond line: no lock headline, and the legacy rule panel in the sans.
  assert.match(SESSION, /className=\{forge \? 'ep-sheet forge-sheet' : 'ep-sheet'\}/);
  assert.match(SESSION, /\{activeLock && currentSubmitted && !forge && \(/);
});

// ---------------------------------------------------------------------------
// 3 · the language rule
// ---------------------------------------------------------------------------

const EXPECTED = {
  en: { level: 'Level 3', count: '3 of 12', drill: 'Find the mistake' },
  de: { level: 'Stufe 3', count: '3 von 12', drill: 'Finde den Fehler' },
  fr: { level: 'Niveau 3', count: '3 sur 12', drill: 'Trouve l’erreur' },
};

for (const [level, control, language] of [['A1.1', 'en', 'en'], ['A2', 'de', 'de'], ['B1', 'en', 'fr'], ['B1.2', 'de', 'fr']]) {
  test(`a ${level} learner (${control}) reads La Forge's chrome in ${language}`, () => {
    const resolved = chromeLanguage(control, level);
    assert.equal(resolved, language);
    const html = renderHead(resolved);
    const tag = renderToStaticMarkup(h(Ep.EpShell, { language: resolved }, h(Forge.ForgeDrillTag, { drill: 'spot', copy: forgeCopy(resolved) })));
    const want = EXPECTED[language];
    assert.ok(text(html).includes(want.level), text(html));
    assert.match(html, new RegExp(`aria-label="${want.count}"`));
    assert.ok(text(tag).includes(want.drill), text(tag));
    // No other language's chrome leaks in.
    for (const [other, words] of Object.entries(EXPECTED)) {
      if (other === language) continue;
      assert.ok(!text(html).includes(words.level), `${language} shows ${other}'s «${words.level}»`);
    }
  });
}

test('the surface is «La Forge» / «Forge today\'s rule» in the three tables', () => {
  assert.equal(FORGE_COPY.en.surface_action, 'Forge today’s rule');
  assert.equal(FORGE_COPY.de.surface_action, 'Regel des Tages schmieden');
  assert.equal(FORGE_COPY.fr.surface_action, 'Forger la règle du jour');
  for (const language of ['en', 'de', 'fr']) assert.equal(FORGE_COPY[language].surface_name, 'La Forge');
  // Announced for the outline, never printed on every screen.
  assert.match(SESSION, /<h1 className="av2-sr">\{forge \? `\$\{fc\.surface_name\} · \$\{fc\.surface_action\}` : t\.screen_name\}<\/h1>/);
});

// ---------------------------------------------------------------------------
// 4 · the screen: less on it, the goal first
// ---------------------------------------------------------------------------

test('the forge screen draws no «Manqué» note, no «sûr / pas sûr», no rule twice', () => {
  assert.match(SESSION, /const provenance = !forge && roundOrdinal === 1/);
  assert.match(SESSION, /const feedbackRule = currentFeedback && !currentFeedback\.correct && !forge/);
  // Every ladder but the paragraph's asks no confidence in the forge.
  assert.equal((SESSION.match(/onPickConfidence=\{forge \? undefined : onPickConfidence\}/g) || []).length, 3);
  assert.match(PAGE, /\{onPickConfidence && <EpConfidence value=\{confidence\} onPick=\{onPickConfidence\} \/>\}/);
  // The épreuve is a quiet line in the opened rule sheet only.
  assert.match(SESSION, /\{forge && !forgeTestOut && ruleExpanded && !ruleIntro && onTestOut && \(/);
});

test('a minimal pair in the forge asks once: its goal, then the two sentences', () => {
  const recognize = PAGE.slice(PAGE.indexOf('function RecognizePanel('), PAGE.indexOf('function TransformPanel('));
  assert.match(recognize, /\{!\(pair && goal && drill\) && \(\s*<EpPrompt lang=/);
});

test('a correction in the forge does not name the rule the head already names', () => {
  const title = 'Le plus-que-parfait : le passé du passé';
  const why = 'Tu as choisi « elle lisait déjà » ; il faut « elle avait déjà lu » ici. Règle\u00a0: Le plus-que-parfait : le passé du passé.';
  assert.equal(P.withoutRuleReference(why, title), 'Tu as choisi « elle lisait déjà » ; il faut « elle avait déjà lu » ici.');
  assert.equal(P.withoutRuleReference('You chose x. Rule: Si type 1.', 'Si type 1'), 'You chose x.');
  assert.equal(P.withoutRuleReference('Falsch. Regel: Das Passé composé.', 'Das passé composé'), 'Falsch.');
  // Another rule, or no rule on screen: the line stays whole.
  assert.equal(P.withoutRuleReference(why, 'L’imparfait'), why);
  assert.equal(P.withoutRuleReference(why, null), why);
  assert.equal(P.correctionAnchor(` ${title} `, title), undefined);
  assert.equal(P.correctionAnchor('Accord du participe', title), 'Accord du participe');
  assert.equal(P.correctionAnchor(title, null), title);
  assert.equal(P.correctionAnchor('', title), undefined);
  assert.match(SESSION, /ruleShown=\{forge \? activeConceptTitle : null\}/);
  assert.match(PAGE, /why=\{display\(printableWhy\(withoutRuleReference\(issue\.why_wrong \|\| feedback\.why \|\| '', ruleShown\)\)\)\}/);
});

test('the goal comes before the box the answer goes in', () => {
  const recognize = PAGE.slice(PAGE.indexOf('function RecognizePanel('), PAGE.indexOf('function TransformPanel('));
  for (const mode of ['fill', 'word_bank', 'classify']) {
    const start = recognize.indexOf(`{mode === '${mode}' && `);
    assert.ok(start > 0, mode);
    const branch = recognize.slice(start, start + 2600);
    const goal = branch.indexOf('<ForgeGoalLine');
    assert.ok(goal > 0, `${mode} states its goal`);
    assert.ok(goal < branch.indexOf('<EpPrompt'), `${mode}: the goal is above the box`);
  }
  // A word bank says its cue and its goal once, above the box.
  assert.match(recognize, /const buildGoal = itemGoal\(item, ''\) \?\? \(buildCue \? \{ kind: 'goal' as const, text: buildCue \} : null\);/);
  const transform = PAGE.slice(PAGE.indexOf('function TransformPanel('), PAGE.indexOf('function itemFeedback('));
  const classic = transform.slice(transform.lastIndexOf('<ForgeGoalLine'));
  assert.ok(classic.indexOf('<EpPrompt') > 0, 'a rewrite states its goal above its sentence');
  assert.ok(transform.indexOf('<ForgeGoalLine goal={goal} />') < transform.indexOf('<ForgeSpot'), 'a spot states its goal above its sentence');
});

// ---------------------------------------------------------------------------
// 5 · the recap
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
    test_out_offer: { concept_id: 7, rung: 3, short: true, items: 3 },
  },
};
const CONCEPTS = [
  { id: 7, category: 'Agreement', name: 'Gender and number', title_fr: 'Genre et nombre' },
  { id: 9, category: 'Verbs', name: 'Present of être', title_fr: 'Le présent d’être' },
  { id: 11, category: 'Negation', name: 'ne … pas', title_fr: 'La négation' },
];
const NOW = new Date('2026-09-24T12:00:00+02:00');

test('the recap rows carry the level reached, what changed, proof and the next review', () => {
  const fc = forgeCopy('en');
  const rows = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, fc, 'en', NOW);
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map((r) => r.level), ['Level 4', 'Level 6', 'Level 2']);
  assert.equal(rows[0].shape, undefined, 'no shape');
  assert.equal(rows[0].change, 'introduced → practising');
  assert.equal(rows[0].proof.length, 2);
  assert.match(rows[0].due, /^Next review Sun,? 27 Sept?/);
  assert.equal(rows[1].change, 'Held from today');
  assert.equal(rows[2].change, 'Still practising');
  assert.equal(rows[2].due, 'Next review today');
  const de = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, forgeCopy('de'), 'de', NOW);
  assert.equal(de[0].change, 'eingeführt → in Übung');
  // A rule not held is never «mastered» beside the épreuve that would make it so.
  for (const language of ['en', 'de', 'fr']) {
    const { stages } = forgeCopy(language);
    assert.doesNotMatch([stages.new, stages.introduced, stages.practising].join(' | '), /held|tenue|acquis|maîtris|mastered|proficient|gefestigt|sicher/i, language);
  }
  assert.equal(forgeCopy('fr').stages.practising, 'en route');
  assert.equal(de[0].level, 'Stufe 4');
  const fr = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, forgeCopy('fr'), 'fr', NOW);
  assert.equal(fr[1].change, 'Tenue dès aujourd’hui');
});

test('the recap renders one card per rule with its level, and no tally', () => {
  const fc = forgeCopy('en');
  const rows = P.recapRuleRows(RECAP, CONCEPTS, (c) => c.title_fr, fc, 'en', NOW);
  const html = renderToStaticMarkup(
    h(Ep.EpShell, { language: 'en' },
      h(Ep.EpBatStage, { title: fc.recap_title }),
      h(Forge.ForgeRecapRules, { copy: fc, rows, proofRight: 'right', proofFixed: 'fixed' }),
    ),
  );
  assert.equal((html.match(/class="forge-recap__rule"/g) || []).length, 3);
  assert.equal((html.match(/class="forge-level" data-size="sm"/g) || []).length, 3);
  assert.doesNotMatch(html, /forge-stair/);
  assert.match(html, /Today’s rules, forged\./);
  assert.match(html, /introduced → practising/);
  assert.match(html, /<span>Level 4<\/span>/);
  assert.match(html, /<span lang="fr">Une petite table blanche\.<\/span>/);
  assert.doesNotMatch(html, /Un troisième/);
  assert.doesNotMatch(html, /ep-tally/);
  // One Garamond line: the headline; the rules are set in the sans.
  assert.equal((html.match(/class="av2-headline/g) || []).length, 1);

  const recap = PAGE.slice(PAGE.indexOf('function RecapModal('), PAGE.indexOf('function recapActionLabel('));
  assert.match(recap, /\{forgeRows\.length \? \(/);
  assert.ok(recap.indexOf('<ForgeRecapRules') < recap.indexOf('<EpTally'), 'the tally is only the legacy branch');
  assert.match(recap, /title=\{forgeRows\.length \? fc\.recap_title : undefined\}/);
});

test('the recap offers the épreuve every few days, for one rule, in a few questions', () => {
  const fc = forgeCopy('fr');
  const html = renderToStaticMarkup(
    h(Ep.EpShell, { language: 'fr' },
      h(Forge.ForgeTestOutOffer, { copy: fc, title: 'Genre et nombre', items: 3, onStart: () => undefined }),
    ),
  );
  assert.match(html, /<section class="forge-offer" aria-label="Prêt pour l’épreuve \?">/);
  assert.match(html, /<p class="forge-offer__rule" lang="fr">Genre et nombre<\/p>/);
  assert.match(html, /3 questions\. Réussie, la règle est acquise\./);
  assert.match(html, /forge-offer__go">Passer l’épreuve<\/button>/);
  const pending = renderToStaticMarkup(
    h(Ep.EpShell, { language: 'fr' },
      h(Forge.ForgeTestOutOffer, { copy: fc, title: 'Genre et nombre', items: 3, pending: true, onStart: () => undefined }),
    ),
  );
  assert.match(pending, /disabled="" aria-busy="true">Préparation de l’épreuve…<\/button>/);

  const recap = PAGE.slice(PAGE.indexOf('function RecapModal('), PAGE.indexOf('function recapActionLabel('));
  assert.match(recap, /const offer = onTestOut \? testOutOffer\(recap\) : null;/);
  assert.match(recap, /\{offer && offerTitle && onTestOut && \(/);
  assert.match(PAGE, /startTestOut\(conceptId, \{ short: true, source: 'forge' \}\)/);
});

// ---------------------------------------------------------------------------
// 6 · the CSS
// ---------------------------------------------------------------------------

function styleBlock(source) {
  const start = source.indexOf('<style jsx global>{`');
  return source.slice(start, source.indexOf('`}</style>', start));
}

for (const file of ['Forge.tsx', 'ForgeDrills.tsx']) {
  test(`the forge CSS (${file}) is tokens only and draws no strokes`, () => {
    const css = styleBlock(fs.readFileSync(path.join(__dirname, file), 'utf8'));
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
}

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
  // #89: the bar follows the visual viewport when the iOS keyboard pans it; 0px everywhere else.
  assert.match(top, /top: var\(--app-viewport-offset-top, 0px\);/);
  assert.match(top, /background: var\(--av2-paper\);/);
  assert.match(css, /\.av2 \.ep-sheet > \.ep-feedback:last-child \{ flex: 0 0 auto; \}/);
  // The WP-S6 additions use tokens only.
  const additions = css.split('WP-S6').slice(1).map((chunk) => chunk.slice(0, 900)).join('\n');
  assert.doesNotMatch(additions, /#[0-9a-fA-F]{3,8}\b/);
});

// QA-FORGE (2026-10-03): at phone width the top bar's count ran into its
// neighbours. The bar takes what is left; the count never shrinks or wraps.
test('the top bar progress fits a phone: the bar shrinks, the count stays whole', () => {
  const css = styleBlock(fs.readFileSync(path.join(WEB_ROOT, 'components/epreuve/Forge.tsx'), 'utf8'));
  assert.match(css, /\.av2 \.forge-progress \{ flex: 1 1 auto; min-width: 0;/);
  assert.match(css, /\.av2 \.forge-progress__track \{ position: relative; flex: 1 1 auto;/);
  assert.match(css, /\.av2 \.forge-progress__n \{ flex: none;/);
});

// ---------------------------------------------------------------------------
// 7 · cues in the learner's language
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

  assert.match(PAGE, /localizedCue\(item, 'prompt', cueLanguage\)/);
  assert.match(PAGE, /localizedCue\(item, 'instruction', cueLanguage\)/);
  assert.match(PAGE, /localizedCue\(produce, 'prompt', cueLanguage\)/);
});
