// #144 / #128 / #106 — one register setting for how the app addresses the learner.
//
// French chrome says «tu», German says «du» (owner decision, 14 Oct 2026). This test
// reads every copy table and the other files that print French or German to the
// learner and fails on «vous»/«votre»/«vos», on an imperative in -ez/-tes, and on
// «Sie»/«Ihr». Quoted material («…», „…“) is exempt: it names a form, it does not
// address anyone. A character's own line may say «vous» where the scene calls for it;
// those live in story data from the server, not in these tables.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');
const { LEARNER_ADDRESS, learnerAddress } = require('./learner-address.ts');

const ROOT = path.join(__dirname, '..');

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules' || entry.name === '.next' || entry.name === '__fixtures__') continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/-copy\.ts$/.test(entry.name)) out.push(full);
  }
  return out;
}

const COPY_TABLES = [...walk(path.join(ROOT, 'lib')), ...walk(path.join(ROOT, 'components'))];
const OTHER_FILES = [
  'lib/first-steps.ts',
  'lib/onboarding-taste.ts',
  'lib/onboarding-signup.ts',
  'lib/atelier-errors.ts',
  'lib/day-session.ts',
  'lib/session-recovery.ts',
  'lib/kept-words.ts',
  'lib/push-opt-in.ts',
  'lib/rule-card.ts',
  'components/atelier-v2/journey/rule-test-out.ts',
  'components/atelier-v2/journey/ReplyStage.tsx',
  'components/stories/StoryProgressOverview.tsx',
  'pages/atelier.tsx',
  'pages/missions.tsx',
  'pages/vocabulary/review.tsx',
].map((file) => path.join(ROOT, file));

// Keys that name the tu/vous distinction itself, and lines of in-scene dialogue.
const NAMES_THE_REGISTER = /\b(register_vous|cast_all_vous|tu_to_vous|vous_to_tu|register_label|cast_link|character\.register)\b/;
const SCENE_DIALOGUE = /s’il vous plaît|Vous prenez quoi|Je vous |vous pouvez me répondre|includes\('vous'\)/;
// Legal text is a reviewed document, not chrome (lib/legal-content.json).
const QUOTED = /«[^»]*»|„[^“”]*[“”]|“[^”]*”/g;

const FRENCH_ADDRESS = new RegExp(
  [
    String.raw`\b(?:vous|votre|vos|dites|redites)\b`,
    // imperatives and 2nd-person plurals in -ez (Réessayez, Écrivez, Choisissez) — not chez/assez/nez
    String.raw`\b(?!chez\b|assez\b|nez\b|rez\b|rendez\b)[A-Za-zÀ-ÿ]{2,}ez\b`,
  ].join('|'),
  'gi',
);
const GERMAN_ADDRESS = new RegExp(
  [
    String.raw`\b(?:Ihr|Ihre|Ihren|Ihrer|Ihrem|Ihres|Ihnen)\b`,
    String.raw`\b[A-ZÄÖÜ][a-zäöüß]+(?:en|n) Sie\b`,
    String.raw`\b(?:damit|dass|wenn|woher|wohin|ob|wo|was|wie|wann|warum|weil|sobald|falls|bevor|und|oder|aber|haben|können|möchten|sind|werden|müssen|wollen|dürfen|sollen) Sie\b`,
  ].join('|'),
  'g',
);

function offenders(file) {
  const found = [];
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (/^(\/\/|\*|\/\*|\{\/\*)/.test(trimmed)) return;
    if (NAMES_THE_REGISTER.test(line) || SCENE_DIALOGUE.test(line)) return;
    const text = line.replace(QUOTED, ' ').replace(/rendez-vous/gi, ' ');
    for (const [name, pattern] of [['fr', FRENCH_ADDRESS], ['de', GERMAN_ADDRESS]]) {
      pattern.lastIndex = 0;
      const hits = text.match(pattern);
      if (hits) found.push(`${path.relative(ROOT, file)}:${index + 1} [${name}] ${hits.join(', ')} :: ${trimmed.slice(0, 100)}`);
    }
  });
  return found;
}

test('the setting is tu for French and du for German', () => {
  assert.deepEqual({ ...LEARNER_ADDRESS }, { fr: 'tu', de: 'du' });
  assert.equal(learnerAddress('fr'), 'tu');
  assert.equal(learnerAddress('de-DE'), 'du');
  assert.equal(learnerAddress('en'), null);
  assert.equal(learnerAddress(undefined), null);
});

test('the browser and the server hold the same setting', () => {
  const server = fs.readFileSync(path.join(ROOT, '..', 'app', 'services', 'address.py'), 'utf8');
  const match = server.match(/LEARNER_ADDRESS[^=]*=\s*\{([^}]*)\}/);
  assert.ok(match, 'app/services/address.py defines LEARNER_ADDRESS');
  const pairs = Object.fromEntries([...match[1].matchAll(/"(\w+)":\s*"(\w+)"/g)].map((m) => [m[1], m[2]]));
  assert.deepEqual(pairs, { ...LEARNER_ADDRESS });
});

test('the scan reads the copy tables it is meant to', () => {
  assert.ok(COPY_TABLES.length >= 25, `expected the copy tables, found ${COPY_TABLES.length}`);
  for (const file of OTHER_FILES) assert.ok(fs.existsSync(file), `${file} exists`);
});

test('the scan catches what it is meant to', () => {
  const sample = (text) => {
    const stripped = text.replace(QUOTED, ' ');
    FRENCH_ADDRESS.lastIndex = 0;
    GERMAN_ADDRESS.lastIndex = 0;
    return [...(stripped.match(FRENCH_ADDRESS) || []), ...(stripped.match(GERMAN_ADDRESS) || [])];
  };
  assert.deepEqual(sample('Dites qui vous êtes et pourquoi vous êtes là'), ['Dites', 'vous', 'vous']);
  assert.deepEqual(sample('Réessayez dans un instant'), ['Réessayez']);
  assert.deepEqual(sample('Ausgewählt, damit Sie die Wörter Ihrer Ausgabe anwenden'), ['damit Sie', 'Ihrer']);
  assert.deepEqual(sample('Dis « vous » ou « tu » : réessaie.'), []);
  assert.deepEqual(sample('Sie feiern deine Serie und platzen ins Bild'), []);
});

test('no copy table addresses the learner with vous, votre, Sie or Ihr', () => {
  const found = [...COPY_TABLES, ...OTHER_FILES].flatMap(offenders);
  assert.deepEqual(found, [], `learner-facing text uses the wrong register:\n${found.join('\n')}`);
});
