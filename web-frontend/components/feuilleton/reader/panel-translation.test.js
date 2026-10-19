/* «Traduire la case» on demand — run with:
 *   node --test components/feuilleton/reader/panel-translation.test.js
 */

const test = require('node:test');
const assert = require('node:assert/strict');

require('../../../node_modules/sucrase/register/ts');

const {
  panelHasText,
  panelTextsToTranslate,
  panelTranslationState,
  textsToRequest,
  translatedStage,
} = require('./panel-translation.ts');

const CAPTION = 'Le café est presque vide ; seule une lampe brûle encore derrière le comptoir.';

function panel(overrides = {}) {
  return {
    kind: 'panel', key: 'panel:p', ordinal: 1, panelId: 'p', panelIndex: 0, title: '', beat: '',
    imageUrl: '', artStatus: 'ready', character: 'gus', caption: CAPTION, tasks: [],
    lines: [
      { key: 'l0', who: 'Gus', fr: 'Tu reviens tard, toi.', en: '', character: 'gus' },
      { key: 'l1', who: 'Gus', fr: 'Assieds-toi.', en: 'Setz dich.', character: 'gus' },
      { key: 'l2', who: 'Toi', fr: 'Je cherche Odile.', en: '', character: 'toi', you: true },
    ],
    ...overrides,
  };
}

test('only the French without a translation is asked for; the learner’s own line never', () => {
  assert.deepEqual(panelTextsToTranslate(panel()), [CAPTION, 'Tu reviens tard, toi.']);
});

test('a fully translated panel asks for nothing and is ready at once', () => {
  const stage = panel({ caption: '', lines: [panel().lines[1]] });
  assert.deepEqual(panelTextsToTranslate(stage), []);
  assert.equal(panelTranslationState(stage, {}), 'ready');
});

test('a request in flight is not sent twice; a failed one is asked again', () => {
  const stage = panel();
  assert.deepEqual(textsToRequest(stage, { [CAPTION]: { state: 'loading' } }), ['Tu reviens tard, toi.']);
  assert.deepEqual(textsToRequest(stage, { [CAPTION]: { state: 'failed' } }), [CAPTION, 'Tu reviens tard, toi.']);
});

test('what arrives fills the narration and the lines; a supplied translation is kept', () => {
  const stage = panel();
  const table = {
    [CAPTION]: { state: 'ready', text: 'Das Café ist fast leer.' },
    'Tu reviens tard, toi.': { state: 'ready', text: 'Du kommst spät zurück.' },
    'Assieds-toi.': { state: 'ready', text: 'should not replace' },
  };
  const shown = translatedStage(stage, table);
  assert.equal(shown.captionEn, 'Das Café ist fast leer.');
  assert.equal(shown.lines[0].en, 'Du kommst spät zurück.');
  assert.equal(shown.lines[1].en, 'Setz dich.');
  assert.equal(shown.lines[2].en, '');
  assert.equal(panelTranslationState(stage, table), 'ready');
  assert.equal(translatedStage(stage, {}), stage, 'nothing arrived: the same panel object');
});

test('loading wins over failed; failed is said once everything has settled', () => {
  const stage = panel();
  assert.equal(panelTranslationState(stage, {}), 'loading');
  assert.equal(panelTranslationState(stage, { [CAPTION]: { state: 'failed' }, 'Tu reviens tard, toi.': { state: 'loading' } }), 'loading');
  assert.equal(panelTranslationState(stage, { [CAPTION]: { state: 'failed' }, 'Tu reviens tard, toi.': { state: 'ready', text: 'x' } }), 'failed');
});

test('a silent panel has nothing to translate', () => {
  assert.equal(panelHasText(panel({ caption: '', lines: [] })), false);
  assert.equal(panelHasText(panel({ caption: '', lines: [panel().lines[2]] })), false, 'only your own line');
  assert.equal(panelHasText(panel()), true);
});
