// node --test components/epreuve/forge-drills.test.js
//
// La Forge's formats on screen (owner, 2026-10-18: «more diverse exercise
// formats, a bit more fun»):
//   1. «Tape la forme»: a French field with the accents a phone hides;
//   2. «Dictée»: the sentence heard, at speed or slower;
//   3. «Trouve l'erreur»: each word a tap; a fixed word shows what it was;
//   4. «Rafale»: four judgements, one tap each, then four marks and a time;
//   5. each new format names itself, and the page wires each one in.

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
const Drills = require('./ForgeDrills.tsx');
const { forgeCopy } = require('@/lib/forge-copy.ts');

const h = React.createElement;
const text = (html) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
const render = (language, node) => renderToStaticMarkup(h(Ep.EpShell, { language }, node));
const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
const DRILLS = fs.readFileSync(path.join(__dirname, 'ForgeDrills.tsx'), 'utf8');

// ---------------------------------------------------------------------------
// 1 · «Tape la forme»
// ---------------------------------------------------------------------------

test('the typed field is French, never corrected by the phone, with the accents on a bar', () => {
  const fc = forgeCopy('de');
  const html = render('de', h(Drills.ForgeTypedField, { value: 'mang', onChange: () => undefined, copy: fc }));
  assert.match(html, /<input class="forge-typed__input" type="text" lang="fr" placeholder="Hier eintippen" aria-label="Tipp die fehlende Form ein\." autoComplete="off" autoCorrect="off" autoCapitalize="none" spellcheck="false" enterKeyHint="done" value="mang"\/>/);
  assert.match(html, /<div class="forge-accents" role="group" aria-label="Akzente">/);
  assert.equal((html.match(/class="forge-accent"/g) || []).length, 10);
  assert.match(html, /<button type="button" class="forge-accent" lang="fr">é<\/button>/);

  const checked = render('de', h(Drills.ForgeTypedField, { value: 'mangé', onChange: () => undefined, submitted: true, verdict: 'right', copy: fc }));
  assert.match(checked, /<div class="forge-typed" data-verdict="right">/);
  assert.match(checked, /readonly=""/);
  assert.doesNotMatch(checked, /forge-accents/, 'no accents once checked');
});

// ---------------------------------------------------------------------------
// 2 · «Dictée»
// ---------------------------------------------------------------------------

test('a dictation plays the sentence, or plays it slower', () => {
  const html = render('fr', h(Drills.ForgeListen, { text: 'Hier, il est venu.', copy: forgeCopy('fr') }));
  assert.match(html, /<button type="button" class="forge-listen__play">/);
  assert.match(text(html), /Écouter Plus lent/);
  // The sentence itself is never printed: it is heard.
  assert.doesNotMatch(html, /il est venu/);
});

test('a dictation asks for the server voice on the tap, never as it shows', () => {
  // Nothing is synthesized, or paid for, before the learner wants it: on a
  // deployment without a server voice, every dictation shown answered 500.
  const hook = DRILLS.slice(DRILLS.indexOf('function useFrenchVoice('), DRILLS.indexOf('export function ForgeListen('));
  const [mount, tap] = hook.split('const play = ');
  assert.doesNotMatch(mount, /synthesize\(/);
  assert.match(tap, /asked\.current = synthesize\(text\)/);
  // Kept once it has come: a replay, or «Plus lent», plays inside its own tap.
  assert.match(tap, /if \(clip\.current\) \{\s*sound\(clip\.current\);\s*return;\s*\}/);
  // The next sentence starts silent, even when this one's voice never came.
  assert.match(mount, /setPlaying\(false\);\s*\}, \[text\]\);/);
});

// ---------------------------------------------------------------------------
// 3 · «Trouve l'erreur»
// ---------------------------------------------------------------------------

test('each word of the sentence is a tap; the gesture is said until it is made', () => {
  const fc = forgeCopy('fr');
  const html = render('fr', h(Drills.ForgeSpot, { sentence: 'Elle n’a pas une idée.', edits: {}, onEdits: () => undefined, copy: fc }));
  assert.match(html, /<p class="forge-spot__line" lang="fr">/);
  assert.equal((html.match(/class="forge-spot__word"/g) || []).length, 5);
  assert.match(html, /<span class="forge-spot__punct">\.<\/span>/);
  assert.match(html, /<p class="forge-spot__hint">Touche le mot faux et corrige-le\.<\/p>/);
  assert.doesNotMatch(html, /forge-spot__undo/);

  const fixed = render('fr', h(Drills.ForgeSpot, { sentence: 'Elle n’a pas une idée.', edits: { 3: 'd’' }, onEdits: () => undefined, copy: fc }));
  assert.match(fixed, /data-edited="true"><s class="forge-spot__was">une<\/s><span class="forge-spot__now">d’<\/span><\/button>/);
  assert.match(fixed, /class="forge-spot__undo">Annuler<\/button>/);
  assert.doesNotMatch(fixed, /forge-spot__hint/);

  const checked = render('fr', h(Drills.ForgeSpot, { sentence: 'Elle n’a pas une idée.', edits: { 3: 'd’' }, onEdits: () => undefined, submitted: true, copy: fc }));
  assert.equal((checked.match(/class="forge-spot__word"[^>]*disabled=""/g) || []).length, 5);
  assert.doesNotMatch(checked, /forge-spot__undo|forge-spot__hint/);
});

// ---------------------------------------------------------------------------
// 4 · «Rafale»
// ---------------------------------------------------------------------------

const BURST = [
  { id: 'j-1', prompt: 'Il a mangé une pomme.', labels: ['Correct', 'À corriger'] },
  { id: 'j-2', prompt: 'Elle a allé au marché.', labels: ['Correct', 'À corriger'] },
  { id: 'j-3', prompt: 'Nous avons fini.', labels: ['Correct', 'À corriger'] },
  { id: 'j-4', prompt: 'Tu as venu hier.', labels: ['Correct', 'À corriger'] },
];

test('a rafale poses one sentence at a time, four dots, two answers in the learner’s language', () => {
  const html = render('de', h(Drills.ForgeRafale, { items: BURST, copy: forgeCopy('de'), onDone: () => undefined, resendLabel: 'Prüfen' }));
  assert.match(html, /Richtig oder falsch\? Vier Sätze, so schnell du kannst\./);
  assert.match(html, /<ol class="forge-rafale__dots" aria-label="1 von 4">/);
  assert.equal((html.match(/<li/g) || []).length, 4);
  assert.match(html, /<li data-state="now"><\/li>/);
  assert.match(html, /Il a mangé une pomme\./);
  assert.doesNotMatch(html, /Elle a allé/, 'one sentence at a time');
  assert.equal((html.match(/class="av2-choice ep-opt"/g) || []).length, 2);
  // Nothing to resend before the four are picked.
  assert.doesNotMatch(html, /Prüfen/);
});

test('the rafale’s result: four marks, the fixes, the score and the time', () => {
  const fc = forgeCopy('fr');
  const rows = [
    { itemId: 'j-1', sentence: 'Il a mangé une pomme.', answer: 'Correct', expected: 'Correct', correct: true, correctedFr: null },
    { itemId: 'j-2', sentence: 'Elle a allé au marché.', answer: 'Correct', expected: 'À corriger', correct: false, correctedFr: 'Elle est allée au marché.' },
    { itemId: 'j-3', sentence: 'Nous avons fini.', answer: 'Correct', expected: 'Correct', correct: true, correctedFr: null },
    { itemId: 'j-4', sentence: 'Tu as venu hier.', answer: 'À corriger', expected: 'À corriger', correct: true, correctedFr: 'Tu es venu hier.' },
  ];
  const html = render('fr', h(Drills.ForgeRafaleResult, { rows, items: BURST, ms: 7420, copy: fc, cheer: '3 d’affilée', onNext: () => undefined, nextLabel: 'Continuer' }));
  assert.match(html, /class="ep-feedback forge-rafale-result" data-verdict="wrong"/);
  assert.equal((html.match(/data-correct="true"/g) || []).length, 3);
  assert.match(html, /<p class="forge-rafale__fix" lang="fr">Elle est allée au marché\.<\/p>/);
  assert.match(text(html), /3 sur 4 en 7,4 s/);
  assert.match(text(html), /en 7,4 s · 3 d’affilée/);
  assert.match(text(html), /Continuer/);

  const perfect = render('fr', h(Drills.ForgeRafaleResult, { rows: rows.map((row) => ({ ...row, correct: true })), items: BURST, copy: fc, onNext: () => undefined, nextLabel: 'Continuer' }));
  assert.match(perfect, /data-verdict="correct"/);
  assert.match(text(perfect), /Quatre sur quatre !/);
});

// ---------------------------------------------------------------------------
// 5 · names and wiring
// ---------------------------------------------------------------------------

test('each new format names itself above the exercise', () => {
  const names = { typed: 'Tape la forme', dictation: 'Dictée', spot: 'Trouve l’erreur', mine: 'Ta phrase', rafale: 'Rafale' };
  for (const [drill, name] of Object.entries(names)) {
    const html = render('fr', h(Forge.ForgeDrillTag, { drill, copy: forgeCopy('fr') }));
    assert.match(html, new RegExp(`<p class="forge-tag" data-drill="${drill}"><span class="forge-tag__mark" aria-hidden="true"></span><span>${name}</span></p>`));
  }
});

test('the page poses each format: typed, dictation, spot and mine, rafale', () => {
  const recognize = PAGE.slice(PAGE.indexOf('function RecognizePanel('), PAGE.indexOf('function TransformPanel('));
  assert.match(recognize, /\{drill === 'typed' \? \(\s*<ForgeTypedField/);
  assert.match(recognize, /const dictation = mode === 'word_bank' && drill === 'dictation';/);
  assert.match(recognize, /\{dictation && <ForgeListen text=\{dictationText\(item\)\} copy=\{fc\} synthesize=\{synthesizeFrench\} \/>\}/);
  // The sentence is heard: its meaning waits for the answer.
  assert.match(recognize, /goal=\{dictation && !submitted \? \{ kind: 'goal', text: fc\.hint_dictation \} : buildGoal\}/);
  // One voice function for the page, so a sentence is fetched once.
  assert.match(PAGE, /^const synthesizeFrench = \(text: string\) => apiService\.synthesizeSpeech\(text\);$/m);

  const transform = PAGE.slice(PAGE.indexOf('function TransformPanel('), PAGE.indexOf('function itemFeedback('));
  assert.match(transform, /const spotted = drill === 'spot' \|\| drill === 'mine';/);
  assert.match(transform, /updateAnswer\(item\.id, spotChanged\(tokens, edits\) \? spotAnswer\(tokens, edits\) : ''\);/);
  // The right line once: a miss reads it in its correction, a right answer hears it.
  assert.match(transform, /const modelAudio = submitted && !\(drill && correction\?\.verdict !== 'correct'\) && /);

  const session = PAGE.slice(PAGE.indexOf('function SessionView('), PAGE.indexOf('function ActionRow('));
  assert.match(session, /\{isNamedDrill\(drill\) && \(drill !== 'rafale' \|\| rafale\) && <ForgeDrillTag drill=\{drill\} copy=\{fc\} \/>\}/);
  assert.match(session, /picked=\{round === 'recognize' \? drill !== 'typed' \|\| typedAsIs : round === 'transform' && Boolean\(drill\)\}/);
  assert.match(session, /<ForgeRafale\s+key=\{burstItemKey\(servedBurst\)\}/);
  assert.match(session, /\{round === 'recognize' && !rafale && \(/);
  assert.match(session, /\{!rafale && <ExerciseFeedbackMoment/);
  // The four are one attempt, named by the lead and their count: their ids
  // ride in the payload, since four of them overflow the exercise id's column.
  assert.match(PAGE, /burst: ids,\n\s+exerciseId: scopedExerciseId\(activeConcept, 'recognize', 'classify', `\$\{ids\[0\]\}\+\$\{ids\.length\}`\),/);
  assert.match(PAGE, /answer_payload: overrides\?\.burst \? \{ answers: itemAnswers, burst: overrides\.burst \} : \{ answers: itemAnswers \},/);
  assert.match(PAGE, /onSubmitBurst=\{submitForgeBurst\}/);
});
