// node --test components/atelier-v2/journey/epreuve.test.js
//
// WP-94 «Numéro spécial» + WP-95 «Le Carnet» — the rendered surfaces:
//   1. the day's card on a special edition: the kicker (French, a place name)
//      and the can-dos in the chrome language; an ordinary day has neither;
//   2. the recap on `passed`: one oversized seal stamped with the band just
//      closed, the host's line, the whole cast happy in one row, the level-up
//      once, one primary; on `failed`: the kind line and the date, no red;
//   3. the Carnet: stamped rows are seals with face, scene, date and quote;
//      unstamped rows are quiet; «Essayez-le pour de vrai» → Répétition;
//      a future band is locked with no try link.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { JourneyRecap } = require('./JourneyRecap.tsx');
const { JourneyTodayCard } = require('./JourneyTodayCard.tsx');
const state = require('./journey-state.ts');
const { CarnetView } = require('../../cahiers/CarnetTab.tsx');
const { AtelierV2Root } = require('../ui/index.ts');
const { carnetModel, readCanDos } = require('@/lib/can-dos.ts');

const h = React.createElement;
const text = (html) =>
  html.replace(/<span class="av2-sr">[\s\S]*?<\/span>/g, ' ').replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/\s+/g, ' ').trim();

const CAN_DOS = [
  { id: 'cafe', title_fr: 'commander au café', title_native: 'order at a café' },
  { id: 'prix', title_fr: 'demander un prix et payer', title_native: 'ask a price and pay' },
];

const SCENARIO = {
  scenario_key: 'k', content_version: '1', title_fr: 'La soirée du Mistral', objective_key: 'o',
  objective_native: 'Show what you can do.', level_band: 'A1', character_id: 'margaux_barman',
  character_name: 'Margaux', location_id: 'l', location_name: 'Le Mistral', image_url: null,
  serial_thread_id: null, serial_episode_id: null, estimated_seconds: 540,
};

function card(language, special) {
  const available = special ? { ...SCENARIO, special: 'epreuve', epreuve: { band: 'A1.1', can_dos: CAN_DOS } } : SCENARIO;
  const envelope = {
    contract_version: 1, enabled: true, control_language: language, local_date: '2026-09-28', timezone: 'Europe/Paris',
    journey: null, available, legacy_resume: null, practice_href: '/atelier?mode=practice', because: null, is_warm: false,
  };
  const controller = {
    phase: state.phaseFromEnvelope(envelope), feedback: { kind: 'idle' }, envelope, journey: null, step: null,
    respondPrompt: null, controlLanguage: language, legacyResume: null, progress: state.journeyProgress(null),
    busy: false, help: null, actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  };
  return renderToStaticMarkup(h(JourneyTodayCard, { controller, onOpen: () => {} }));
}

test('the day card on a special edition: the kicker and the can-dos, in the chrome language', () => {
  const fr = card('fr', true);
  assert.match(fr, /<span class="av2-special__kicker" lang="fr" data-special-kicker="">Numéro spécial<\/span>/);
  assert.match(text(fr), /Aujourd’hui, montrez que vous savez : commander au café · demander un prix et payer/);
  assert.match(fr, /data-special="epreuve"/);
  const en = text(card('en', true));
  assert.match(en, /Numéro spécial · Le Mistral/);
  assert.match(en, /Today, show that you can: order at a café · ask a price and pay/);
  // One press on the card, still.
  assert.equal((card('en', true).match(/av2-btn--primary/g) || []).length, 1);
  const plain = card('fr', false);
  assert.doesNotMatch(plain, /Numéro spécial|data-special/);
});

const JOURNEY = {
  id: 'j', contract_version: 1, revision: 1, status: 'completed', local_date: '2026-09-28', timezone: 'Europe/Paris',
  budget_seconds: 600, estimated_active_seconds: 540, current_step_id: null, scenario: SCENARIO, steps: [], recap: null,
  retry: null, edition_no: 12, streak: { days: 12, today_done: true, freeze_available: false, freeze_used_on: null },
  special: 'epreuve', epreuve: { band: 'A1.2', can_dos: CAN_DOS },
};

function recap(result, language = 'fr') {
  const payload = {
    completion_kind: 'complete', objective_outcome: 'met', practiced_targets: [], capability_evidence: [],
    next_focus: null, collectible_ids: [], story_outcome: null, active_seconds: 560,
    level_up: result === 'passed' ? { from_level: 'A1.2', to_level: 'A2.1', mastered_vocabulary: 300, mastered_grammar: 20 } : null,
    epreuve_result: result,
    epreuve_line_fr: result === 'passed' ? 'Toute la troupe lève son verre !' : null,
  };
  return renderToStaticMarkup(
    h(AtelierV2Root, { language }, h(JourneyRecap, { journey: JOURNEY, recap: payload, language, onExit: () => {} })),
  );
}

test('passed: one oversized seal with the band closed, the host line, the whole cast happy, level-up once', () => {
  const html = recap('passed');
  assert.equal((html.match(/class="av2-seal"/g) || []).length, 1, 'the épreuve seal replaces the day seal');
  assert.match(html, /class="av2-seal" data-size="xl"/);
  assert.match(html, /aria-label="Sceau du numéro spécial · A1\.2 bouclé"/);
  assert.match(html, />A1\.2 · 28 sept\.</);
  assert.match(html, />Numéro spécial</);
  assert.match(text(html), /A1\.2, bouclé/);
  assert.match(text(html), /Toute la troupe lève son verre/);
  const cast = html.match(/<ul class="av2-epreuve__cast"[\s\S]*?<\/ul>/)[0];
  assert.equal((cast.match(/data-mood="happy"/g) || []).length, 6, 'the whole cast, delighted');
  assert.equal((html.match(/A1\.2 → A2\.1/g) || []).length, 1, 'the level-up line once');
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
});

test('failed: kind, dated, no red and no seal of shame', () => {
  const html = recap('failed');
  assert.match(html, /data-epreuve-failed=""/);
  assert.match(text(html), /Pas encore cette fois/);
  assert.match(text(html), /La prochaine édition spéciale : dans 7 jours \(5 octobre\)/);
  assert.doesNotMatch(html, /data-size="xl"/);
  const block = html.match(/<div class="av2-surface[^"]*av2-epreuve--failed[\s\S]*?data-epreuve-next[^<]*<\/p>/)[0];
  assert.doesNotMatch(block, /red|alert|action/i, 'no red, no alert tone');
  assert.match(text(recap('failed', 'de')), /Die nächste Sonderausgabe: in 7 Tagen \(5\. Oktober\)/);
  // An ordinary day: neither.
  const plain = renderToStaticMarkup(
    h(AtelierV2Root, { language: 'fr' }, h(JourneyRecap, { journey: { ...JOURNEY, special: null, epreuve: null }, recap: { completion_kind: 'complete', objective_outcome: 'met', practiced_targets: [], capability_evidence: [], next_focus: null, collectible_ids: [], story_outcome: null, active_seconds: 300 }, language: 'fr' })),
  );
  assert.doesNotMatch(plain, /data-epreuve|data-size="xl"/);
});

const PAYLOAD = readCanDos({
  current_band: 'A1.1',
  bands: [
    {
      band: 'A1.1',
      can_dos: [
        { ...CAN_DOS[0], stamped_at: '2026-09-28', source: 'scene', scene_title_fr: 'Vous avez commandé au comptoir', character_id: 'margaux_barman', quote_fr: 'Un café, s’il vous plaît.' },
        { ...CAN_DOS[1], stamped_at: null },
      ],
    },
    { band: 'A1.2', can_dos: [{ id: 'chemin', title_fr: 'demander son chemin', title_native: 'ask the way' }] },
  ],
});

function carnet(band, language = 'fr') {
  return renderToStaticMarkup(h(AtelierV2Root, { language }, h(CarnetView, { model: carnetModel(PAYLOAD, band, language), language })));
}

test('the Carnet: stamps pressed as seals with face, scene, date and quote; the rest quiet', () => {
  const html = carnet(null);
  assert.match(html, /data-stamped="true"[\s\S]*class="av2-seal-mini" data-state="earned"/);
  assert.match(html, /data-stamped="false"[\s\S]*class="av2-seal-mini" data-state="future"/);
  assert.match(text(html), /Vous avez commandé au comptoir — Margaux, 28 sept\./);
  assert.match(html, /class="av2-carnet__quote" lang="fr">«\s?Un café, s’il vous plaît\.\s?»/);
  assert.match(html, /data-size="xs"/);
  assert.match(text(html), /1 sur 2 tamponnés/);
  assert.equal((html.match(/href="\/repetition\?situation=/g) || []).length, 2);
  assert.match(text(html), /Essayez-le pour de vrai/);
  // No gauge: no progress bar, no percent.
  assert.doesNotMatch(html, /role="progressbar"/);
  assert.doesNotMatch(text(html.replace(/<style>[\s\S]*?<\/style>/g, ' ')), /%/);
  // The band switcher: the future is locked, calmly, with no try link.
  assert.match(html, /aria-pressed="true" data-state="current"/);
  const locked = carnet('A1.2');
  assert.match(text(locked), /A1\.2 s’ouvre quand A1\.1 est bouclé/);
  assert.doesNotMatch(locked, /\/repetition/);
  // English chrome keeps the French title beside it.
  const en = carnet(null, 'en');
  assert.match(text(en), /order at a café/);
  assert.match(en, /lang="fr">commander au café</);
});
