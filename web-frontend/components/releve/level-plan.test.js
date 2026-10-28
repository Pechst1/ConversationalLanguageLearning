// node --test components/releve/level-plan.test.js
//
// The level plan as Fortschritt prints it (2026-10-24). Owner: «we always know
// exactly at which level the learner is currently so that he also knows that
// exactly and knows what he has to do and how much time he has to invest to
// advance further». The numbers are the server's (`GET /progress/level`); these
// tests pin what the card says with them, in the three chrome languages, and
// the honesty rules: no gauge, forecast or goal date against a level the app
// has not measured (WP-25), no épreuve promised «in the story» unless the story
// stages it (WP-94).

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

const { LEVEL_PLAN_COPY, levelPlanCopy, fill } = require('./level-plan-copy.ts');
const { levelPlanView, planDay, planDuration, ruleTitle } = require('./level-plan-model.ts');

const holes = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',');
const code = (file) =>
  fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');

const TODAY = new Date('2026-10-24T09:00:00Z');

function rule(id, stage, fields = {}) {
  return {
    id,
    external_id: `unit-${id}`,
    name: `Unit ${id}`,
    titles: { en: `Rule ${id}`, de: `Regel ${id}`, fr: `Règle ${id}` },
    stage,
    missing: [],
    owed_today: null,
    earliest_held_on: null,
    introduce_from: null,
    held_on: null,
    ...fields,
  };
}

function measuredPlan(overrides = {}) {
  return {
    version: 'level-plan-v1',
    generated_at: '2026-10-24T09:00:00+00:00',
    band: 'A1.1',
    next_band: 'A1.2',
    percent: 42,
    label: 'A1.1 · 42 %',
    estimate_source: 'measured',
    verified: true,
    placement_taken_at: null,
    goal: { band: 'B1.1', bands_left: 4, words_left: 1240, units_left: 46, weeks: 30 },
    ladder: [
      { band: 'A1.1', state: 'current', on: null, goal: false },
      { band: 'A1.2', state: 'ahead', on: null, goal: false },
      { band: 'A2.1', state: 'ahead', on: null, goal: false },
      { band: 'A2.2', state: 'ahead', on: null, goal: false },
      { band: 'B1.1', state: 'ahead', on: null, goal: true },
    ],
    rules: {
      held: 3,
      required: 8,
      total: 9,
      to_go: 5,
      met: false,
      practising: 2,
      introduced: 1,
      not_started: 3,
      owed_today: 1,
      per_week: 5,
      items: [
        rule(11, 'practising', {
          owed_today: 'free_use',
          missing: [{ code: 'free_use_first', not_before: null }],
          earliest_held_on: '2026-10-31',
        }),
        rule(12, 'practising', {
          missing: [{ code: 'spaced', not_before: '2026-11-04' }],
          earliest_held_on: '2026-11-04',
        }),
        rule(13, 'introduced', { earliest_held_on: '2026-11-07' }),
        rule(14, 'new', { introduce_from: '2026-10-24', earliest_held_on: '2026-11-07' }),
        rule(15, 'new', { introduce_from: '2026-10-25' }),
        rule(16, 'new', { introduce_from: '2026-10-27' }),
        rule(1, 'held', { held_on: '2026-10-02' }),
        rule(2, 'held', { held_on: '2026-10-09' }),
        rule(3, 'held', { held_on: '2026-10-12' }),
      ],
    },
    words: {
      known: 120,
      required: 253,
      total: 316,
      to_go: 133,
      met: false,
      on_the_way: 40,
      not_met: 156,
      new_needed: 93,
      from_reading: 0,
      per_day: 20,
      days_for_new: 5,
    },
    epreuve: { band: 'A1.1', state: 'locked', attempts: 0, retry_after: null, staged_in_story: true, can_dos: 6 },
    time: {
      status: 'measured',
      range_days: [30, 49],
      dates: ['2026-11-23', '2026-12-12'],
      capped: false,
      earliest_days: 14,
      earliest_on: '2026-11-07',
      minutes_per_day: 18,
      minutes_source: 'measured',
      planned_minutes_per_day: 22,
      hours: [9, 15],
      active_days: 11,
      active_days_required: 7,
      pace: 'normal',
      pace_chosen: true,
      words_per_day: 20,
      rules_per_week: 5,
    },
    invested: {
      band_since: '2026-09-30',
      band_minutes: 200,
      band_days: 12,
      scenes_minutes: 120,
      forge_minutes: 50,
      words_minutes: 30,
      recent_minutes_per_day: 18.4,
    },
    skills: {
      words: { covered: null, working: 'A1.1', percent: 47, list_ends: false },
      rules: { covered: null, working: 'A1.1', percent: 37, list_ends: false },
    },
    evidence: { attempts_required: 40, attempts_counted: 52 },
    can_dos: { stamped: 2, total: 6, next: null },
    ...overrides,
  };
}

test('the three tables are complete and fill the same placeholders', () => {
  const fr = LEVEL_PLAN_COPY.fr;
  for (const language of ['en', 'de']) {
    const table = LEVEL_PLAN_COPY[language];
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const [key, value] of Object.entries(table)) {
      assert.ok(String(value).trim(), `${language}.${key} is empty`);
      assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
    }
  }
});

test('German says du, French says tu', () => {
  const de = Object.values(LEVEL_PLAN_COPY.de).join(' ');
  assert.doesNotMatch(de, /\b(Sie|Ihr|Ihre|Ihren|Ihrem)\b/);
  assert.match(de, /\bdu\b|\bdein/);
  const fr = Object.values(LEVEL_PLAN_COPY.fr).join(' ');
  assert.doesNotMatch(fr, /\bvous\b|\bvotre\b|\bvos\b/i);
});

test('a measured learner reads the band, its percent and the next one', () => {
  const view = levelPlanView(measuredPlan(), 'en', TODAY);
  assert.equal(view.headline, 'A1.1 · 42 %');
  assert.equal(view.verified, true);
  assert.equal(view.percent, 42);
  assert.equal(view.percentLabel, 'Level A1.1: 42 %');
  assert.match(view.percentRule, /90 %.*10 %/);
  assert.equal(view.next, 'Next level: A1.2');
  assert.equal(view.evidence, null);
  assert.equal(view.soFar, null);
  assert.deepEqual(
    view.ladder.map((step) => [step.band, step.state, step.goal]),
    [
      ['A1.1', 'current', false],
      ['A1.2', 'ahead', false],
      ['A2.1', 'ahead', false],
      ['A2.2', 'ahead', false],
      ['B1.1', 'ahead', true],
    ],
  );
  assert.equal(view.ladder[0].label, 'A1.1, you are here');
  assert.equal(view.ladder[4].label, 'B1.1, ahead, goal');
});

test('what the next band needs: rules and words, item by item, and today', () => {
  const view = levelPlanView(measuredPlan(), 'en', TODAY);
  assert.equal(view.needsTitle, 'To move up to A1.2');
  const [rules, words] = view.criteria;
  assert.equal(rules.label, 'Rules held');
  assert.equal(rules.value, '3 of 8 needed · 9 in the level');
  assert.deepEqual([rules.have, rules.need, rules.met], [3, 8, false]);
  assert.deepEqual(rules.notes, ['2 practising · 1 introduced · 3 not met yet']);
  assert.equal(words.value, '120 of 253 needed · 316 in the level');
  assert.deepEqual(words.notes, [
    '40 more are on their way in your reviews.',
    '93 still to meet: about 5 days at 20 new words a day.',
  ]);
  assert.deepEqual(view.test, { label: 'Level test', value: 'once the rules and the words are covered', ready: false });
  assert.equal(view.today, 'Today 1 rule can take a step towards “held”: Rule 11.');
});

test('today names three rules, then counts the rest', () => {
  const plan = measuredPlan();
  plan.rules.items = plan.rules.items.map((item) =>
    item.stage === 'practising' || item.stage === 'introduced' || item.id === 1 ? { ...item, owed_today: 'spaced' } : item,
  );
  plan.rules.items.push(rule(17, 'practising', { owed_today: 'spaced' }));
  const view = levelPlanView(plan, 'en', TODAY);
  assert.equal(view.today, 'Today 5 rules can take a step towards “held”: Rule 11; Rule 12; Rule 13 and 2 more.');
});

test('how long: the estimate, its basis, the rules’ floor, the minutes and the pace', () => {
  const view = levelPlanView(measuredPlan(), 'en', TODAY);
  assert.equal(
    view.time.estimate,
    `Estimate: 30 to 49 days at your pace, between ${planDay('2026-11-23', 'en')} and ${planDay('2026-12-12', 'en')}.`,
  );
  assert.equal(view.time.basis, 'Measured on your last two weeks.');
  assert.ok(view.time.earliest.startsWith(`Not before ${planDay('2026-11-07', 'en')}, however much you practise`));
  assert.equal(
    view.time.cost,
    'At your 18 minutes a day (your average over two weeks), that is about 9 to 15 hours of practice.',
  );
  assert.equal(view.time.pace, 'Your pace: Normal · 20 new words a day · 5 new rules a week');
  assert.equal(view.time.changePace, 'Change pace');
  assert.equal(view.goal, 'Your goal B1.1: 1,240 words and 46 rules to go, in ≈ 7 months at your pace.');
  // An abbreviated day at the end of the sentence keeps one full stop («12. Dez.», «12 déc.»).
  for (const language of ['de', 'fr']) {
    const estimate = levelPlanView(measuredPlan(), language, TODAY).time.estimate;
    assert.ok(estimate.endsWith(`${planDay('2026-12-12', language)}`), estimate);
    assert.ok(!estimate.endsWith('..'), estimate);
  }
});

test('before seven active days the estimate is the plan’s, and says when it will be measured', () => {
  const plan = measuredPlan();
  plan.time = { ...plan.time, status: 'plan', minutes_source: 'plan', minutes_per_day: 22, active_days: 3, hours: [11, 11] };
  const view = levelPlanView(plan, 'en', TODAY);
  assert.ok(view.time.estimate.startsWith('Estimate from your plan: 30 to 49 days'));
  assert.equal(view.time.basis, 'From 7 active days on, it is measured on your own practice (3 so far).');
  assert.equal(view.time.cost, 'At the 22 minutes a day your plan takes, that is about 11 hours of practice.');
});

test('a capped estimate promises neither a date nor hours', () => {
  const plan = measuredPlan();
  plan.time = { ...plan.time, capped: true, range_days: [730, 730], hours: null };
  const view = levelPlanView(plan, 'en', TODAY);
  assert.equal(view.time.estimate, 'Estimate: more than two years at this pace.');
  assert.equal(view.time.earliest, null);
  assert.equal(view.time.cost, null);
});

test('the rules one by one: owed today, on their way, not met yet, held', () => {
  const view = levelPlanView(measuredPlan(), 'en', TODAY);
  assert.equal(view.rules.title, 'The rules of A1.1 (9)');
  const rows = Object.fromEntries(view.rules.rows.map((row) => [row.id, row]));
  assert.equal(rows[11].tone, 'owed');
  assert.equal(
    rows[11].note,
    `can take a step today · Still needed: one unaided use in a reply · held on ${planDay('2026-10-31', 'en')} at the earliest`,
  );
  assert.equal(rows[12].tone, 'progress');
  assert.match(rows[12].note, /^practising · Still needed: one successful review, from /);
  assert.equal(rows[13].note, `introduced · held on ${planDay('2026-11-07', 'en')} at the earliest`);
  assert.equal(rows[14].tone, 'new');
  assert.equal(rows[14].note, `not met yet · arrives around ${planDay('2026-10-24', 'en')} at your pace`);
  assert.equal(rows[1].tone, 'held');
  assert.equal(rows[1].note, `held since ${planDay('2026-10-02', 'en')}`);
  // The order is the server's: owed first, held last.
  assert.deepEqual(view.rules.rows.map((row) => row.id), [11, 12, 13, 14, 15, 16, 1, 2, 3]);
});

test('time put in: the band’s minutes, by surface, and what is not counted', () => {
  const view = levelPlanView(measuredPlan(), 'en', TODAY);
  assert.equal(view.invested.title, 'Time put in');
  assert.deepEqual(view.invested.lines, [
    `3 h 20 min at A1.1 since ${planDay('2026-09-30', 'en')}, on 12 days.`,
    'Scenes 2 h · La Forge 50 min · Words 30 min',
    'Lately: 18 minutes a day on average.',
    'Time in Le Courrier and Le Papier is not counted yet.',
  ]);
  const fresh = measuredPlan();
  fresh.invested = { band_since: null, band_minutes: 0, band_days: 0, scenes_minutes: 0, forge_minutes: 0, words_minutes: 0, recent_minutes_per_day: 0 };
  assert.deepEqual(levelPlanView(fresh, 'en', TODAY).invested.lines, [
    'No practice time measured yet at A1.1.',
    'Time in Le Courrier and Le Papier is not counted yet.',
  ]);
});

test('each criterion on its own', () => {
  const plan = measuredPlan();
  plan.skills = {
    words: { covered: 'A2.1', working: 'A2.2', percent: 64, list_ends: false },
    rules: { covered: null, working: 'A1.1', percent: 37, list_ends: false },
  };
  assert.deepEqual(levelPlanView(plan, 'en', TODAY).skills.lines, [
    'Words: A2.1 covered, 64 % of A2.2.',
    'Rules: 37 % of A1.1.',
    'Your level moves up once both are covered and its level test is passed.',
  ]);
  plan.skills.words = { covered: 'B1.2', working: null, percent: null, list_ends: true };
  assert.equal(levelPlanView(plan, 'en', TODAY).skills.lines[0], 'Words: B1.2 covered; the core word list ends there.');
});

test('WP-25: a declared level shows its counts as «so far», with no gauge, forecast or goal date', () => {
  const plan = measuredPlan({
    band: 'B1.1',
    next_band: 'B1.2',
    label: 'B1.1 · 0 %',
    percent: 0,
    estimate_source: 'declared',
    verified: false,
    evidence: { attempts_required: 40, attempts_counted: 12 },
  });
  const view = levelPlanView(plan, 'en', TODAY);
  assert.equal(view.headline, 'B1.1');
  assert.equal(view.percentRule, null);
  assert.equal(view.soFar, 'So far in the app:');
  assert.equal(
    view.evidence,
    'L’Atelier measures your level after 40 marked answers within two weeks; 12 so far.',
  );
  assert.equal(view.time.estimate, 'A time to the next level comes once L’Atelier has measured yours.');
  assert.equal(view.time.basis, null);
  assert.equal(view.time.cost, null);
  assert.equal(view.time.earliest, null);
  assert.equal(view.goal, null);
  assert.equal(view.skills, null);
  // The pace and the time put in are the learner's own, measured or chosen: they stay.
  assert.ok(view.time.pace);
  assert.ok(view.invested.lines[0].startsWith('3 h 20 min'));
  // The card draws a bar only when verified (LevelPlanCard).
  assert.match(code('LevelPlanCard.tsx'), /view\.verified && criterion\.need > 0 &&/);
  assert.match(code('LevelPlanCard.tsx'), /view\.verified && <ProgressRule value=\{view\.percent\}/);
});

test('WP-94: the épreuve comes «in the story» only when the story stages it', () => {
  const ready = (staged) =>
    levelPlanView(measuredPlan({ epreuve: { band: 'A1.1', state: 'ready', attempts: 0, staged_in_story: staged } }), 'en', TODAY)
      .test;
  assert.deepEqual(ready(true), { label: 'Level test', value: 'ready: it comes up in the story', ready: true });
  assert.equal(ready(false).value, 'ready: everything it asks for is covered');
  for (const language of ['en', 'de', 'fr']) {
    const copy = levelPlanCopy(language);
    assert.doesNotMatch(copy.test_ready, /story|Geschichte|histoire/, language);
  }
  const failed = levelPlanView(
    measuredPlan({ epreuve: { band: 'A1.1', state: 'failed', attempts: 1, retry_after: '2026-10-30T10:00:00+00:00' } }),
    'en',
    TODAY,
  ).test;
  assert.equal(failed.value, `retake from ${planDay('2026-10-30', 'en')}`);
});

test('above B1 the word list ends and only the rules are counted', () => {
  const plan = measuredPlan({ band: 'B2.1', next_band: 'B2.2' });
  plan.words = { ...plan.words, known: 0, required: 0, total: 0, met: true };
  const view = levelPlanView(plan, 'en', TODAY);
  assert.deepEqual(view.criteria.map((item) => item.key), ['rules']);
  assert.equal(view.wordsNote, 'Above B1 the core word list ends: the rules and the level test decide.');
});

test('the top band has no next one', () => {
  const view = levelPlanView(measuredPlan({ band: 'C1.2', next_band: null, goal: null }), 'en', TODAY);
  assert.equal(view.next, 'The top of the ladder.');
  assert.equal(view.needsTitle, 'To complete C1.2');
});

test('German and French chrome: their words, their titles, their durations', () => {
  const de = levelPlanView(measuredPlan(), 'de', TODAY);
  assert.equal(de.next, 'Nächstes Niveau: A1.2');
  assert.equal(de.criteria[0].label, 'Gefestigte Regeln');
  assert.deepEqual(de.criteria[0].notes, ['2 in Übung · 1 eingeführt · 3 noch nicht kennengelernt']);
  assert.equal(de.time.pace, 'Dein Tempo: Normal · 20 neue Wörter am Tag · 5 neue Regeln pro Woche');
  assert.equal(de.goal, 'Dein Ziel B1.1: noch 1.240 Wörter und 46 Regeln, bei deinem Tempo in ≈ 7 Monaten.');
  assert.ok(de.invested.lines[0].startsWith('3 Std. 20 Min. bei A1.1 seit dem '));
  assert.ok(de.invested.lines[0].endsWith(', an 12 Tagen.'));

  const fr = levelPlanView(measuredPlan(), 'fr', TODAY);
  assert.equal(fr.needsTitle, 'Pour passer à A1.2');
  assert.deepEqual(fr.criteria[0].notes, ['2 en route · 1 découverte · 3 pas encore découvertes']);
  assert.equal(fr.time.pace, 'Ton rythme : Normal · 20 mots nouveaux par jour · 5 règles nouvelles par semaine');
  // Counts in the chrome language's own digits: «1 240» with a narrow no-break space.
  assert.ok(fr.goal.includes('1\u202f240'));
  const row = fr.rules.rows.find((item) => item.id === 11);
  assert.deepEqual([row.title, row.lang], ['Règle 11', 'fr']);
  assert.equal(levelPlanView(measuredPlan(), 'en', TODAY).rules.rows[0].lang, undefined);
});

test('durations, days and titles', () => {
  assert.equal(planDuration(45, 'en'), '45 min');
  assert.equal(planDuration(60, 'en'), '1 h');
  assert.equal(planDuration(200, 'en'), '3 h 20 min');
  assert.equal(planDuration(200, 'de'), '3 Std. 20 Min.');
  assert.equal(planDuration(200, 'fr'), '3 h 20');
  assert.equal(planDay(null, 'en'), null);
  assert.equal(planDay('not a day', 'en'), null);
  assert.equal(planDay('2026-11-07', 'en'), new Date('2026-11-07T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }));
  assert.deepEqual(ruleTitle({ name: 'Unit', titles: { en: 'Articles' } }, 'de'), { title: 'Articles', lang: undefined });
  assert.deepEqual(ruleTitle({ name: 'Unit', titles: {} }, 'fr'), { title: 'Unit', lang: undefined });
  assert.equal(fill('{a} {b}', { a: 1 }), '1 {b}');
});

test('Fortschritt reads the plan, keeps its fallback, and the card reads nothing itself', () => {
  const releve = code('Releve.tsx');
  assert.match(releve, /api\.getLevelPlan\(\)/);
  assert.match(releve, /<LevelPlanCard/);
  // The coverage rendering stays as the fallback when the plan cannot be read.
  assert.match(releve, /\{!unverified && \(coursWords\[1\] > 0 \|\| coursRules\[1\] > 0\) && \(/);
  const card = code('LevelPlanCard.tsx');
  assert.doesNotMatch(card, /api\.|fetch\(/);
  assert.match(card, /<TempoSheet/);
  assert.doesNotMatch(card, /#[0-9a-fA-F]{3,8}\b/);
  assert.doesNotMatch(code('level-plan-model.ts'), /Math\.random|Date\.now\(\)/);
});
