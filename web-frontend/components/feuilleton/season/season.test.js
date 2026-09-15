/* The Feuilleton tab's season page (WP-44).
 *   node --test components/feuilleton/season/season.test.js
 *
 * What is pinned here:
 *   · the season's own lines — label, today, a read row's second line;
 *   · the empty state is one honest sentence, not a placeholder episode;
 *   · the page shows no art it does not have, and no striped stand-in;
 *   · the season endpoint reads story state and never writes it.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

require('../../../node_modules/sucrase/register/ts');
require('../../../node_modules/sucrase/register/tsx');

const ROOT = path.resolve(__dirname, '../../..');
const REPO = path.resolve(ROOT, '..');

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  if (request === 'next/link') {
    return originalResolve.call(
      this,
      path.join(ROOT, 'components/feuilleton/reader/__fixtures__/next-link-stub.js'),
      ...rest,
    );
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
global.React = React;

const model = require('./season-model.ts');
const { SeasonPage } = require('./SeasonPage.tsx');

const season = {
  thread_id: 't1',
  season_number: 1,
  chapter: { number: 1, title_fr: 'S’installer, avec complications' },
  today: {
    scene_id: 's4',
    number: 4,
    title_fr: 'Un prêt théâtral',
    brief_fr: 'Augustin propose vingt euros pour le plombier — contre une promesse.',
    image_url: '/assets/serial/mistral.jpg',
    character: 'Augustin',
    location: 'Le Mistral',
    status: 'available',
  },
  commitments: [{ id: 'e1:commitment:0', text_fr: 'Rembourser Marin vingt euros demain matin.' }],
  read_episodes: [
    {
      scene_id: 's3',
      number: 3,
      title_fr: 'La fuite',
      brief_fr: '',
      image_url: '/assets/serial/appartement.jpg',
      character: 'Lila',
      location: 'l’appartement',
      status: 'completed',
    },
    {
      scene_id: 's2',
      number: 2,
      title_fr: 'Un rendez-vous au comptoir',
      brief_fr: '',
      image_url: null,
      character: '',
      location: '',
      status: 'completed',
    },
  ],
};

function render(payload) {
  return renderToStaticMarkup(
    React.createElement(SeasonPage, { season: payload, onOpenSeance: () => {} }),
  );
}

test('the season says which season, which chapter and what it is called', () => {
  assert.equal(model.seasonStoryLabel(season), 'Saison 1 · chapitre 1 · S’installer, avec complications');
  assert.equal(model.seasonStoryLabel({ ...season, chapter: null }), 'Saison 1');
  assert.equal(
    model.seasonStoryLabel({ ...season, season_number: 2, chapter: { number: 3, title_fr: '' } }),
    'Saison 2 · chapitre 3',
  );
});

test("today's episode says where it is played, and never opens itself", () => {
  assert.equal(model.seasonTodayLabel(season.today), 'Aujourd’hui · épisode 4 · se joue dans la séance');
  const html = render(season);
  assert.ok(html.includes('Ouvrir la séance'), html.slice(0, 300));
  assert.ok(html.includes('Un prêt théâtral'));
  assert.ok(html.includes('se joue dans la séance'));
});

test('a read row names the person and the place, and omits what is unknown', () => {
  assert.equal(model.seasonEpisodeMeta(season.read_episodes[0]), 'avec Lila · l’appartement');
  assert.equal(model.seasonEpisodeMeta(season.read_episodes[1]), '');
  assert.equal(model.seasonEpisodeMeta({ character: '', location: 'Le Mistral' }), 'Le Mistral');
});

test('the read episodes are listed with their thumbnails and link to the replay', () => {
  const html = render(season);
  assert.ok(html.includes('Épisode 3'), html.slice(0, 400));
  assert.ok(html.includes('/assets/serial/appartement.jpg'));
  assert.ok(html.includes('/graphic-novel?scene=s3'));
  assert.ok(html.includes('avec Lila'));
});

test('an episode without art gets no art, not a placeholder', () => {
  const html = render({ ...season, read_episodes: [season.read_episodes[1]] });
  assert.ok(!/img[^>]+wp44-read__art/.test(html), 'no <img> is invented for a row with no image');
  assert.ok(!html.includes('pas encore parue'), 'the apology is gone');
  assert.ok(!html.includes('repeating-linear-gradient'), 'no striped placeholder');
});

test('with nothing read the page says so in one sentence', () => {
  const empty = { ...season, today: null, commitments: [], read_episodes: [] };
  assert.equal(model.seasonHasNothingRead(empty), true);
  assert.equal(model.seasonHasStory(empty), false);
  const html = render(empty);
  assert.ok(html.includes('Votre première scène s’ouvre dans la séance.'), html);
  assert.ok(!html.includes('Ouvrir la séance'), 'nothing to open, so no button');
  assert.ok(!html.includes('Engagement en cours'));
});

test('an open commitment is shown as open, and only while it is open', () => {
  const html = render(season);
  assert.ok(html.includes('Engagement en cours'));
  assert.ok(html.includes('Rembourser Marin vingt euros demain matin.'));
  const none = render({ ...season, commitments: [] });
  assert.ok(!none.includes('Engagement en cours'));
});

test('the season endpoint reads story state and writes none of it', () => {
  const source = fs.readFileSync(path.join(REPO, 'app/services/serial.py'), 'utf8');
  const start = source.indexOf('    def season_page(');
  assert.ok(start > 0, 'season_page must exist');
  const end = source.indexOf('\n    def episode_archive(', start);
  const body = source.slice(start, end > start ? end : undefined);
  // Call shapes, not mentions: the docstring is allowed to say what it does
  // not do, and saying so is half the point of it.
  for (const forbidden of [
    'get_or_create_thread(',
    'db.add(',
    'db.commit(',
    'db.flush(',
    'thread.state =',
    'thread.current_episode_index =',
    'start_feuilleton_beat(',
    'start_next_beat(',
  ]) {
    assert.ok(!body.includes(forbidden), `season_page must not call ${forbidden}`);
  }

  const endpoint = fs.readFileSync(path.join(REPO, 'app/api/v1/endpoints/serial.py'), 'utf8');
  const route = endpoint.indexOf('@router.get("/season")');
  assert.ok(route > 0, 'the season route must exist');
  const handler = endpoint.slice(route, endpoint.indexOf('@router.', route + 10));
  assert.ok(handler.includes('season_page'));
  assert.ok(!handler.includes('get_or_create_thread('));
});

test('the page component starts nothing: one route out, no create call', () => {
  const source = fs.readFileSync(path.join(__dirname, 'SeasonPage.tsx'), 'utf8');
  for (const forbidden of ['apiService', 'createGraphicNovelScene', 'advance(', 'useEffect(']) {
    assert.ok(!source.includes(forbidden), `the season page must not reach for ${forbidden}`);
  }
});
