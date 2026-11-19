// node --test components/atelier-v2/journey/goal-meaning-marked.test.js
//
// R5 (CI walk «en + B1», 19 Nov): «The neighbours have run out of milk? Construis la phrase :
// « I'll bring them some this afternoon. » Un mot est en trop.» — the meaning quoted in a
// French goal is the learner's own language and carries `lang`; the French ask stays interface.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const frame = require('./drill-frame.ts');
const steps = require('./JourneySteps.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const { ForgeGoalLine } = require('@/components/epreuve/ForgeFollowUp.tsx');
const { EpShell } = require('@/components/epreuve/Epreuve.tsx');

const h = React.createElement;
const GOAL = "The neighbours have run out of milk? Construis la phrase : « I'll bring them some this afternoon. » Un mot est en trop.";
const MARKS = [
  { text: 'The neighbours have run out of milk?', lang: 'en' },
  { text: "I'll bring them some this afternoon.", lang: 'en' },
];

test('La Forge marks the meaning and the line said before it; the French ask stays unmarked', () => {
  const goal = frame.drillGoalLine({ goal_native: GOAL, goal_native_marks: MARKS });
  const html = renderToStaticMarkup(h(EpShell, { language: 'fr' }, h(ForgeGoalLine, { goal })));
  assert.match(html, /<span lang="en">The neighbours have run out of milk\?<\/span> Construis la phrase : « <span lang="en">I(&#x27;|')ll bring them some this afternoon\.<\/span> » Un mot est en trop\./);
});

test('an item without marks renders as before', () => {
  const goal = frame.drillGoalLine({ goal_native: GOAL });
  const html = renderToStaticMarkup(h(EpShell, { language: 'fr' }, h(ForgeGoalLine, { goal })));
  assert.doesNotMatch(html, /lang="en"/);
});

test('a day drill’s French goal marks an English quote, never a French one', () => {
  const copy = journeyCopy('fr');
  const english = { kind: 'goal', text: "Écris correctement ce que tu as dit : « The yard sale? Shall we tell him after work? »" };
  const html = renderToStaticMarkup(h(steps.DrillGoalLine, { goal: english, copy }));
  assert.match(html, /« <span lang="en">The yard sale\? Shall we tell him after work\?<\/span> »/);
  const french = { kind: 'goal', text: 'Reconstruis la phrase de la scène avec « la clé ».' };
  assert.doesNotMatch(renderToStaticMarkup(h(steps.DrillGoalLine, { goal: french, copy })), /<span lang=/);
  assert.deepEqual(frame.quotedMeaningMarks(english.text, 'fr'), [], 'a French speaker’s page marks nothing');
});

// R5 (CI walk «en + B1», day 3): «Corrige la phrase · It should say: "…"» — the follow-up's
// French goal quotes the meaning in the learner's language, marked.
test('the «Corrige la phrase» follow-up marks the meaning its French goal quotes', () => {
  const { classifyRepair } = require('@/lib/forge-followup.ts');
  const { ForgeFollowUp } = require('@/components/epreuve/ForgeFollowUp.tsx');
  const meaning = "I'm going to the town hall to renew my passport.";
  const { followUp } = classifyRepair(
    { id: 'j1', prompt: 'Je vais à la mairie pour renouvelle mon passeport.' },
    {
      corrected_fr: 'Je vais à la mairie pour renouveler mon passeport.',
      follow_up: {
        kind: 'correct_it',
        source_fr: 'Je vais à la mairie pour renouvelle mon passeport.',
        goal_native: `La phrase veut dire : « ${meaning} »`,
        goal_native_marks: [{ text: meaning, lang: 'en' }],
        accepted_fr: ['Je vais à la mairie pour renouveler mon passeport.'],
      },
    },
  );
  assert.deepEqual(followUp.goalMarks, [{ text: meaning, lang: 'en' }]);
  const html = renderToStaticMarkup(
    h(EpShell, { language: 'fr' }, h(ForgeFollowUp, { followUp, draft: { text: '', tiles: [], outcome: null }, onDraft: () => undefined })),
  );
  assert.match(html, /La phrase veut dire : « <span lang="en">I(&#x27;|')m going to the town hall to renew my passport\.<\/span> »/);
});
