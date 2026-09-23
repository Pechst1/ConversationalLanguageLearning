// node --test components/atelier-v2/journey/cast-reacts.test.js
//
// WP-D2 (the cast reacts) and WP-D7 (the tile's mould, the sealed letter).
//
//   1. `CastPortrait` and `moodForVerdict` live in the av2 kit and `lib/`;
//      onboarding imports them from there and the old path still resolves;
//   2. the respond step says the character's line in a bubble beside their
//      face, which swaps to the verdict's mood; a stranger gets an initial;
//   3. «Marin vous sourit ↑» under a correct verdict, never under a wrong one;
//   4. the recap's mood line is a chip beside the face;
//   5. a placed tile leaves a same-text mould, so the bank never reflows;
//   6. the envelope is shapes and tokens only: no image, no stroke, no hex.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const faces = require('@/lib/cast-faces.ts');
const taste = require('@/lib/onboarding-taste.ts');
const ui = require('@/components/atelier-v2/ui');
const steps = require('./JourneySteps.tsx');
const replyStage = require('./ReplyStage.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const { JourneyRecap } = require('./JourneyRecap.tsx');
const courrier = require('@/components/courrier/Courrier.tsx');

const EN = journeyCopy('en');
const h = React.createElement;
const read = (file) => fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');

// ===========================================================================
// 1. Where the face lives
// ===========================================================================

test('CastPortrait lives in the av2 kit; onboarding imports it and moodForVerdict from there', () => {
  assert.equal(typeof ui.CastPortrait, 'function');
  const legacy = require('@/components/onboarding/Portrait.tsx');
  assert.equal(legacy.CastPortrait, ui.CastPortrait, 'the old path is a re-export, not a second face');
  const tasteSource = read('components/onboarding/Taste.tsx');
  assert.match(tasteSource, /from '@\/components\/atelier-v2\/ui\/CastPortrait'/);
  assert.match(tasteSource, /import \{ moodForVerdict \} from '@\/lib\/cast-faces'/);
  assert.equal(taste.moodForVerdict, faces.moodForVerdict, 'one map, re-exported');
  assert.equal(faces.moodForVerdict('pending'), 'neutral');
  assert.equal(faces.moodForVerdict('correct'), 'happy');
  assert.equal(faces.moodForVerdict('wrong'), 'cross');
  assert.equal(faces.expressionForMood('touched'), 'moved', 'the fourth face, when the story says so');
  assert.equal(faces.expressionForMood('warmer'), 'happy', 'warmth alone is not «moved»');
});

test('a ringed portrait wears its own --char-* accent, even from an id alone', () => {
  const html = renderToStaticMarkup(h(ui.CastPortrait, { characterId: 'augustin_de_roncourt', ring: true }));
  assert.ok(html.includes('data-edge="char"'));
  assert.ok(html.includes('--av2-char:var(--char-gus'), html);
  const stranger = renderToStaticMarkup(h(ui.CastPortrait, { characterId: '', name: 'Clerk', ring: true }));
  assert.ok(!stranger.includes('.webp'), 'a stranger keeps the initial disc');
  assert.ok(stranger.includes('>C</span>'));
});

// ===========================================================================
// 2. The respond step: the line in a bubble, the face reacting
// ===========================================================================

function respondStep(prompt = {}) {
  return {
    id: 'step-respond',
    ordinal: 3,
    kind: 'respond',
    status: 'active',
    estimated_seconds: 120,
    assistance_used: [],
    prompt: {
      character_id: 'marin',
      character_name: 'Marin',
      character_line_fr: 'Alors, vous prenez quoi ?',
      objective_native: 'Order a coffee.',
      targets: [],
      input_modes: ['text'],
      help_available: [],
      turn_index: 0,
      ...prompt,
    },
  };
}

const respondProps = (step, feedback = { kind: 'idle' }) => ({
  step,
  copy: EN,
  busy: false,
  feedback,
  help: null,
  onHelp() {},
  onSubmit() {},
  onContinue() {},
});

const graded = (verdict) => ({
  kind: 'graded',
  verdict,
  result: { character_reply_fr: null, correction: null },
  replySource: 'unknown',
});

test('the character line sits in the bubble beside their face, which swaps with the verdict', () => {
  const idle = renderToStaticMarkup(h(steps.RespondStepView, respondProps(respondStep())));
  assert.match(idle, /class="av2-speech" data-mood="neutral"/);
  assert.match(idle, /av2-speech__bubble"><h2 class="av2-headline" lang="fr">Alors, vous prenez quoi\u202f\?<\/h2>/);
  assert.ok(idle.includes('marin_leveque/portrait-neutral.webp'));
  assert.ok(idle.includes('data-size="md"'), 'the speaker is the md portrait');
  assert.equal(idle.split('.webp').length - 1, 1, 'one face for the speaker, not a byline disc too');

  const right = renderToStaticMarkup(h(steps.RespondStepView, respondProps(respondStep(), graded('correct'))));
  assert.match(right, /class="av2-speech" data-mood="happy"/);
  assert.ok(right.includes('marin_leveque/portrait-happy.webp'));
  const wrong = renderToStaticMarkup(h(steps.RespondStepView, respondProps(respondStep(), graded('wrong'))));
  assert.ok(wrong.includes('marin_leveque/portrait-cross.webp'));

  const stranger = renderToStaticMarkup(
    h(steps.RespondStepView, respondProps(respondStep({ character_id: 'clerk', character_name: 'Clerk' }))),
  );
  assert.ok(stranger.includes('av2-speech'), 'a stranger still speaks in the bubble');
  assert.ok(!stranger.includes('.webp'), 'with the initial disc, never a borrowed face');
});

test('a letter day keeps its subject headline and gets no bubble', () => {
  const html = renderToStaticMarkup(
    h(
      steps.RespondStepView,
      respondProps(
        respondStep({
          letter: {
            correspondent_id: 'lila',
            correspondent_name: 'Lila',
            subject_fr: 'Ta visite',
            body_fr: 'Coucou, tu passes samedi ?',
            objective_native: 'Answer Lila.',
          },
        }),
      ),
    ),
  );
  assert.ok(!html.includes('av2-speech'), 'no portrait in a card that has no character line');
  assert.ok(html.includes('Ta visite'));
});

test('the bubble has the design shape and the face pops only on a verdict', () => {
  const css = read('styles/atelier-v2.css');
  const block = css.slice(css.indexOf('WP-D2 — the cast reacts'));
  assert.match(block, /\.av2-speech__bubble \{[^}]*border-radius: 20px 20px 20px 6px;[^}]*background: var\(--av2-card\);/);
  assert.match(block, /\.av2-speech:not\(\[data-mood='neutral'\]\) \.av2-speech__face \{ animation: av2-pop/);
  // Reduce Motion: the global `.av2 *` rule collapses every animation.
  assert.match(css, /prefers-reduced-motion: reduce\) \{\s*\.av2 \*,/);
});

// ===========================================================================
// 3. «Marin vous sourit ↑»
// ===========================================================================

test('a correct verdict adds «Marin vous sourit ↑»; a wrong one does not', () => {
  const band = (verdict) =>
    renderToStaticMarkup(
      h(steps.JourneyFeedbackView, {
        feedback: graded(verdict),
        copy: EN,
        onContinue() {},
        onRetry() {},
        onDismiss() {},
        speaker: { id: 'marin', name: 'Marin' },
      }),
    );
  const right = band('correct');
  assert.ok(right.includes('av2-smiles'));
  assert.ok(right.includes('Marin smiles at you'), 'in the chrome language (English by default)');
  assert.ok(right.indexOf('av2-feedback') < right.indexOf('av2-smiles'), 'under the band');
  assert.ok(!band('wrong').includes('av2-smiles'));
  assert.ok(!band('supported').includes('av2-smiles'), 'only a clean correct');
  assert.equal(replyStage.smileLine('Marin', 'fr'), 'Marin vous sourit');
  assert.equal(replyStage.smileLine('Marin', 'de'), 'Marin lächelt Sie an');
  assert.equal(replyStage.smileLine('', 'fr'), null);
});

// ===========================================================================
// 4. The recap: the face and the mood chip
// ===========================================================================

test('the recap puts the mood in a chip beside the face and the callback line', () => {
  const journey = {
    id: 'j1',
    status: 'completed',
    steps: [],
    scenario: { character_id: 'marin', character_name: 'Marin' },
  };
  const recap = {
    mood: { character_id: 'marin', character_name: 'Marin', mood: 1, shift: 'warmer' },
    story_outcome: { callback_fr: 'Marin garde votre table.' },
  };
  const html = renderToStaticMarkup(h(JourneyRecap, { journey, recap, language: 'fr' }));
  const face = html.slice(html.indexOf('av2-reward__face'));
  assert.ok(face.includes('portrait-happy.webp'));
  assert.match(face, /av2-reward__mood" data-mood="up"><span class="av2-chip">/);
  assert.ok(face.includes('Marin garde votre table.'));
});

// ===========================================================================
// 5. The tile's mould
// ===========================================================================

const OPTIONS = [
  { id: 'a', textFr: 'je' },
  { id: 'b', textFr: 'voudrais' },
  { id: 'c', textFr: 'un café' },
];
const tiles = (placed) =>
  renderToStaticMarkup(
    h(ui.WordTiles, {
      options: OPTIONS,
      placed,
      label: 'Build it',
      emptyHint: 'Tap the words',
      removeLabel: 'Remove last',
      onPlace() {},
      onRemoveLast() {},
    }),
  );
const bankOf = (html) => html.slice(html.indexOf('av2-tiles__bank'));
/** Every slot in the bank, in order, as `state:text`. */
const slots = (html) =>
  [...bankOf(html).matchAll(/class="av2-tile( av2-tile--mould)?"[^>]*>(?:<span[^>]*>)?([^<]*)/g)].map(
    (match) => `${match[1] ? 'mould' : 'tile'}:${match[2]}`,
  );

test('placing and removing tiles never moves the other tiles', () => {
  const none = slots(tiles([]));
  const one = slots(tiles(['b']));
  const two = slots(tiles(['b', 'a']));
  assert.deepEqual(none, ['tile:je', 'tile:voudrais', 'tile:un café']);
  assert.deepEqual(one, ['tile:je', 'mould:voudrais', 'tile:un café'], 'the slot stays, with the same word to hold its width');
  assert.deepEqual(two, ['mould:je', 'mould:voudrais', 'tile:un café']);
  assert.deepEqual(slots(tiles([])), none, 'removing brings the tile back to the same place');
});

test('a mould is hidden from assistive tech; placed words are selected tiles, read as one sentence', () => {
  const html = tiles(['b', 'a']);
  assert.match(bankOf(html), /av2-tile--mould" data-state="mould" aria-hidden="true"><span class="av2-tile__ghost"/);
  const line = html.slice(html.indexOf('av2-tiles__line'), html.indexOf('av2-tiles__bank'));
  assert.ok(line.includes('<span class="av2-sr">voudrais je</span>'));
  assert.equal(line.split('data-state="placed"').length - 1, 2);

  const css = read('styles/atelier-v2.css');
  assert.match(css, /\.av2 \.av2-tile\[data-state='placed'\] \{\s*border-color: var\(--av2-blue\);/, 'the selected style: a blue edge');
  assert.match(css, /\.av2 \.av2-tile--mould \{[^}]*border: 2px dashed var\(--av2-line-2\);/);
  assert.match(css, /\.av2 \.av2-tile__ghost \{ visibility: hidden; \}/, 'the ghost word keeps the width');
});

// ===========================================================================
// 6. The sealed letter
// ===========================================================================

test('the envelope is shapes and tokens only, sealed with the sender’s ringed face', () => {
  const html = renderToStaticMarkup(h(courrier.CrEnvelope, { senderId: 'marin_leveque', senderName: 'Marin' }));
  assert.match(html, /role="img" aria-label="Une lettre scellée, de Marin"/);
  assert.ok(html.includes('class="cr-env-body"') && html.includes('class="cr-env-flap"') && html.includes('class="cr-env-stamp"'));
  assert.ok(!/stroke/i.test(html.replace(/<style[\s\S]*?<\/style>/g, '')), 'no shape is outlined');
  assert.ok(html.includes('data-edge="char"') && html.includes('marin_leveque/portrait-neutral.webp'));
  const images = html.match(/<img /g) || [];
  assert.equal(images.length, 1, 'the only image is the sender’s face; the envelope is drawn');

  const styles = renderToStaticMarkup(h(courrier.CrEnvelopeStyles));
  assert.ok(!/#[0-9a-f]{3,8}\b/i.test(styles), 'no hex colour: tokens only, so dark mode follows');
  assert.ok(!/stroke/i.test(styles));
  assert.match(styles, /\.cr-env-body \{ fill: var\(--av2-card\); \}/);
  assert.match(styles, /\.cr-env-stamp \{ fill: var\(--av2-red\); \}/);

  const anonymous = renderToStaticMarkup(h(courrier.CrEnvelope, {}));
  assert.ok(!anonymous.replace(/<style[\s\S]*?<\/style>/g, '').includes('cr-env-seal'), 'no sender, no invented seal');
});

test('«Lire et répondre» carries minutes only when the server gave them', () => {
  assert.equal(courrier.crReadAndReplyLabel(8), 'Lire et répondre · 8 min');
  assert.equal(courrier.crReadAndReplyLabel(null), 'Lire et répondre');
  assert.equal(courrier.crReadAndReplyLabel(0), 'Lire et répondre');
  const page = read('pages/serial/index.tsx');
  assert.match(page, /heroIsLetter \? \(\s*<CrEnvelope/, 'the Feuilleton hero draws a waiting letter as the envelope');
});
