/**
 * WP-34 — «Apportez votre français»: the Courrier's intake surface.
 *
 * Same harness as `components/atelier-v2/ui/atelier-v2-ui.test.js`: a plain node
 * script with `node:assert/strict` and sucrase, so it adds no test framework and
 * no dependency.
 *
 * These are failure-mode tests, not snapshots. What they hold down:
 *
 *   1. one primary press per screen — the composition rule the whole design
 *      system rests on, and the one a new surface breaks first;
 *   2. «Non lu» is a real state: no summary, no facts, no task, and a retry;
 *   3. the card is French, and a gloss the app's own lexicon did not supply is
 *      labelled rather than passed off as the app's;
 *   4. the new CSS is theme-token-only, so dark mode comes free and cannot
 *      drift — the exact bug `globals.css` shipped once;
 *   5. every new rule is scoped `.av2 .cr-…` and can never reach a legacy page;
 *   6. status is never colour alone;
 *   7. the allowance is said in a sentence, never as a bare number.
 *
 * Run: `node components/courrier/courrier-intake.test.js`
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const courrier = require('./Courrier.tsx');
const {
  CrArtefactCard,
  CrArtefactTaskCard,
  CrArtefactUnread,
  CrIntakeEntry,
  crIntakeCapLine,
} = courrier;

const { AtelierV2Root } = require('@/components/atelier-v2/ui/AtelierV2Root.tsx');

const SOURCE = fs.readFileSync(path.join(HERE, 'Courrier.tsx'), 'utf8');
const h = React.createElement;
// WP-82: the intake's chrome follows the root's chrome language. These checks
// hold down the French (B1+) reading inside a French root, whose wrapper is
// peeled off so an empty component still renders as ''. English and German
// are covered by `courrier-language.test.js`.
const render = (element) =>
  renderToStaticMarkup(h(AtelierV2Root, { language: 'fr' }, element))
    .replace(/^<div[^>]*>/, '')
    .replace(/<\/div>$/, '');
const text = (html) => html.replace(/<[^>]+>/g, '');

const CAP = { limit: 5, used: 1, remaining: 4, enabled: true };

const MENU_ARTEFACT = {
  id: 'a1',
  status: 'read',
  source_kind: 'image',
  source_text: 'Café des Trois Ponts — Formule du midi',
  artefact: {
    type: 'menu',
    type_label_fr: 'Un menu',
    title_fr: 'Formule du midi',
    summary_fr: 'C’est le menu du midi. La formule coûte 14,50 euros.',
    summary_bounded: true,
    key_facts: [{ label_fr: 'Formule', value_fr: '14,50 €' }],
    glossed_words: [
      { word: 'velouté', gloss: 'Cremesuppe', gloss_language: 'de', gloss_source: 'vocabulary' },
      { word: 'gratin', gloss: 'baked dish', gloss_language: 'en', gloss_source: 'model' },
      { word: 'purée', gloss: '', gloss_source: 'none' },
    ],
    band: 'A2',
  },
  task: {
    kind: 'decide',
    kind_label_fr: 'Choisir',
    instruction_fr: 'Commandez votre formule du midi auprès du serveur.',
    counterpart_fr: 'le serveur',
    register: 'vous',
    success_fr: 'Le serveur sait ce que vous prenez.',
  },
  mission_id: 'm1',
  queued_word_count: 3,
};

let checks = 0;
function check(label, fn) {
  fn();
  checks += 1;
  console.log(`  ok  ${label}`);
}

// ===========================================================================
// 1. one primary press per screen
// ===========================================================================

check('the two ways in are two secondary buttons, and neither is a press', () => {
  // WP-45, `Documents.dc.html`: «Coller un texte» and «Photographier» choose
  // *how* the document arrives. Before one is chosen there is nothing to read,
  // so the screen carries no primary at all.
  const html = render(h(CrIntakeEntry, { cap: CAP, onRead: () => {} }));
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 0);
  assert.equal((html.match(/av2-btn--secondary/g) || []).length, 2);
  assert.match(html, /Coller un texte/);
  assert.match(html, /Photographier/);
  assert.match(html, /Le Courrier · Vos documents/);
  assert.match(html, /on le lit avec vous/);
  // The well is there for the screen reader but closed until it is asked for.
  assert.match(html, /id="cr-intake-text"[^>]*hidden/);
});

check('choosing «coller un texte» opens the well and the one primary press', () => {
  const html = render(h(CrIntakeEntry, { cap: CAP, onRead: () => {}, pasteOpen: true }));
  const primaries = html.match(/av2-btn--primary/g) || [];
  assert.equal(primaries.length, 1, 'the entry must have exactly one 3D press');
  assert.match(html, /Faire lire/);
  assert.ok(!/id="cr-intake-text"[^>]*hidden/.test(html), 'the well is open');
});

check('the read artefact carries the screen\'s one primary, and its task none', () => {
  // WP-45 moves «Répondre à …» inside the card: the document is read, and what
  // is owed is an answer to whoever sent it.
  const card = render(h(CrArtefactCard, { artefact: MENU_ARTEFACT, onDelete: () => {} }));
  assert.equal((card.match(/av2-btn--primary/g) || []).length, 1);
  assert.match(card, /Répondre à le serveur/);
  assert.match(card, /href="\/missions\?mission=m1"/);
  // Without a mission the server never made, the card offers no press at all.
  const orphan = render(
    h(CrArtefactCard, { artefact: { ...MENU_ARTEFACT, mission_id: null } }),
  );
  assert.equal((orphan.match(/av2-btn--primary/g) || []).length, 0);
  // The separate task card still owns its press only when a page asks for one.
  const task = render(h(CrArtefactTaskCard, { task: MENU_ARTEFACT.task, onStart: () => {} }));
  assert.equal((task.match(/av2-btn--primary/g) || []).length, 1);
  assert.match(task, /Répondre/);
});

check('the primary is disabled until there is a document to read', () => {
  const html = render(h(CrIntakeEntry, { cap: CAP, onRead: () => {}, pasteOpen: true }));
  assert.match(html, /Faire lire[\s\S]*$/);
  assert.match(html, /disabled=""/);
});

check('a learner at the cap cannot start a read at all', () => {
  const html = render(
    h(CrIntakeEntry, {
      cap: { limit: 5, used: 5, remaining: 0, enabled: true },
      onRead: () => {},
      pasteOpen: true,
    }),
  );
  assert.match(html, /Vous avez fait lire tous vos documents de la semaine/);
  assert.match(html, /disabled=""/);
});

check('the privacy line is on the same line as the allowance', () => {
  const html = render(h(CrIntakeEntry, { cap: CAP, onRead: () => {} }));
  assert.match(html, /privés, supprimables, jamais dans le feuilleton/);
});

check('the artefact label names the type, the counterpart and the date', () => {
  const html = render(h(CrArtefactCard, { artefact: { ...MENU_ARTEFACT, created_at: '2026-09-12T09:00:00Z' } }));
  // The type and the counterpart keep their own `lang="fr"`; the line reads as one.
  assert.match(text(html), /Un menu · le serveur · reçue le 12 sept/);
  assert.match(html, /<span lang="fr">Un menu<\/span>/);
  // A document with no date simply drops the clause rather than guessing one.
  const undated = render(h(CrArtefactCard, { artefact: MENU_ARTEFACT }));
  assert.ok(!/reçue le/.test(undated));
});

check('the glossed words are chips, French in the serif, gloss beside it', () => {
  const html = render(h(CrArtefactCard, { artefact: MENU_ARTEFACT }));
  assert.equal((html.match(/class="cr-art-word"/g) || []).length, 3);
  assert.match(html, /<b lang="fr">velouté<\/b>/);
});

// ===========================================================================
// 2. «Non lu» is a real state
// ===========================================================================

check('an unread photo says what to do about it, and offers a retry', () => {
  const html = render(h(CrArtefactUnread, { sourceKind: 'image', onRetry: () => {} }));
  assert.match(html, /Non lu/);
  assert.match(html, /Reprenez la photo/);
  assert.match(html, /Réessayer/);
  // No summary, no facts, no task may be invented for a document nobody read.
  assert.ok(!/cr-art-facts/.test(html));
  assert.ok(!/cr-art-task/.test(html));
  assert.match(html, /role="status"/);
});

check('an unread paste gets its own sentence, not the photo one', () => {
  const html = render(h(CrArtefactUnread, { sourceKind: 'text', onRetry: () => {} }));
  assert.ok(!/Reprenez la photo/.test(html));
  assert.match(html, /Réessayez dans un instant/);
});

check('a task with no instruction renders nothing rather than an empty card', () => {
  assert.equal(render(h(CrArtefactTaskCard, { task: null })), '');
  assert.equal(render(h(CrArtefactTaskCard, { task: { kind: 'reply' } })), '');
});

// ===========================================================================
// 3. French, and an honest gloss
// ===========================================================================

check('the artefact card is French and marks a gloss the lexicon did not supply', () => {
  const html = render(h(CrArtefactCard, { artefact: MENU_ARTEFACT }));
  assert.match(html, /Un menu/);
  assert.match(html, /Formule du midi/);
  assert.match(html, /Les mots que vous ne connaissiez pas/);
  // The app's own gloss is shown in the language it is actually in.
  assert.match(html, /lang="de"[^>]*>Cremesuppe/);
  // A model gloss standing in for a missing entry is labelled, not disguised.
  assert.match(html, /hors lexique/);
  // A word with no gloss at all says so rather than rendering an empty span.
  assert.match(html, /traduction indisponible/);
  assert.match(html, /résumé abrégé/);
});

check('the delete control says what it takes with it', () => {
  const html = render(h(CrArtefactCard, { artefact: MENU_ARTEFACT, onDelete: () => {} }));
  assert.match(html, /Supprimer ce document et sa tâche/);
  const without = render(h(CrArtefactCard, { artefact: MENU_ARTEFACT }));
  assert.ok(!/Supprimer/.test(without));
});

check('no English reaches the learner-facing copy of the new surface', () => {
  const html = [
    render(h(CrIntakeEntry, { cap: CAP, onRead: () => {} })),
    render(h(CrArtefactCard, { artefact: MENU_ARTEFACT, onDelete: () => {} })),
    render(h(CrArtefactTaskCard, { task: MENU_ARTEFACT.task, onStart: () => {} })),
    render(h(CrArtefactUnread, { onRetry: () => {} })),
  ].join('\n');
  // The glosses themselves are deliberately in the learner's language; the
  // chrome is not. These are words the chrome would have used if it drifted.
  for (const english of ['Read', 'Delete', 'Retry', 'Photograph ', 'Reply</', 'Answer']) {
    assert.ok(!html.includes(english), `chrome drifted to English: ${english}`);
  }
});

// ===========================================================================
// 4/5. the stylesheet cannot drift, and cannot escape
// ===========================================================================

const STYLE_BLOCK = SOURCE.slice(SOURCE.indexOf('export function CourrierStyles'));
const INTAKE_CSS = STYLE_BLOCK.slice(
  STYLE_BLOCK.indexOf('WP-34 «Apportez votre français»'),
  STYLE_BLOCK.indexOf('/* loading */'),
);

check('the intake stylesheet exists and is not empty', () => {
  assert.ok(INTAKE_CSS.length > 500, 'the WP-34 CSS block was not found');
});

check('every intake colour is a theme token, so dark mode cannot drift', () => {
  const literals = INTAKE_CSS.match(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/g) || [];
  assert.deepEqual(literals, [], `hard-coded colours in the WP-34 CSS: ${literals}`);
  // And it really does use the tokens that have a dark counterpart.
  for (const token of ['--av2-card', '--av2-ink', '--av2-muted', '--av2-paper']) {
    assert.ok(INTAKE_CSS.includes(token), `missing token ${token}`);
  }
});

check('every intake rule is scoped and cannot reach a legacy page', () => {
  const selectors = INTAKE_CSS.match(/^\s*\.[^{]+\{/gm) || [];
  assert.ok(selectors.length > 10);
  for (const selector of selectors) {
    assert.ok(
      selector.trim().startsWith('.av2 '),
      `unscoped rule would leak to legacy pages: ${selector.trim()}`,
    );
  }
});

check('every intake class in the markup has a rule behind it', () => {
  const html = [
    render(h(CrIntakeEntry, { cap: CAP, onRead: () => {}, error: 'Photo trop lourde.' })),
    render(h(CrArtefactCard, { artefact: MENU_ARTEFACT, onDelete: () => {} })),
    render(h(CrArtefactTaskCard, { task: MENU_ARTEFACT.task, onStart: () => {} })),
    render(h(CrArtefactUnread, { onRetry: () => {}, onDelete: () => {} })),
  ].join('\n');
  const used = new Set();
  for (const match of html.matchAll(/class="([^"]+)"/g)) {
    for (const name of match[1].split(/\s+/)) {
      if (name.startsWith('cr-intake') || name.startsWith('cr-art')) used.add(name);
    }
  }
  assert.ok(used.size > 8);
  for (const name of used) {
    assert.ok(INTAKE_CSS.includes(`.${name}`), `class .${name} has no rule`);
  }
});

// ===========================================================================
// 6/7. status is never colour alone, and the allowance is a sentence
// ===========================================================================

check('the unread and error states carry words, not just a colour', () => {
  const error = render(
    h(CrIntakeEntry, { cap: CAP, onRead: () => {}, error: 'La photo est trop lourde.' }),
  );
  assert.match(error, /role="alert"/);
  assert.match(error, /La photo est trop lourde/);
  const unread = render(h(CrArtefactUnread, {}));
  assert.match(unread, /Non lu/);
});

check('the allowance is a French sentence, in every state', () => {
  assert.match(crIntakeCapLine({ limit: 5, used: 0, remaining: 5, enabled: true }), /5 documents/);
  assert.match(crIntakeCapLine({ limit: 5, used: 4, remaining: 1, enabled: true }), /un document/);
  assert.match(crIntakeCapLine({ limit: 5, used: 5, remaining: 0, enabled: true }), /tous vos documents/);
  assert.match(crIntakeCapLine({ limit: 0, used: 0, remaining: 0, enabled: false }), /désactivée/);
  assert.match(crIntakeCapLine(null), /désactivée/);
});

check('the photo input accepts only formats the vision call can read', () => {
  const html = render(h(CrIntakeEntry, { cap: CAP, onRead: () => {} }));
  assert.match(html, /accept="image\/jpeg,image\/png,image\/webp,image\/heic,image\/heif"/);
  assert.match(html, /type="file"/);
});

console.log(`\n${checks} checks passed — courrier intake (WP-34)`);
