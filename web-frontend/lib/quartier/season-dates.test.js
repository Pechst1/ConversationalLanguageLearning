// node --test lib/quartier/season-dates.test.js
//
// The quarter's own copy renders the season's date tokens by the server's rule
// (app/services/season/dates.py): the same dates for the same starts, and no token left.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { renderText, shiftDays } = require('./season-dates.ts');
const { OfflineStory, pageOfCopy } = require('./story.ts');

// Expected values printed by app/services/season/dates.py for the same starts.
const SERVER = [
  ['2026-11-11', 0, 'mercredi 11 novembre', 'mercredi 18 novembre', 'Mercredi 2 décembre', 'Mittwoch, 2. Dezember'],
  ['2026-11-14', 0, 'mercredi 11 novembre', 'mercredi 18 novembre', 'Mercredi 2 décembre', 'Mittwoch, 2. Dezember'],
  ['2026-11-15', 7, 'mercredi 18 novembre', 'mercredi 25 novembre', 'Mercredi 9 décembre', 'Mittwoch, 9. Dezember'],
  ['2026-11-19', 7, 'mercredi 18 novembre', 'mercredi 25 novembre', 'Mercredi 9 décembre', 'Mittwoch, 9. Dezember'],
  ['2026-11-24', 14, 'mercredi 25 novembre', 'mercredi 2 décembre', 'Mercredi 16 décembre', 'Mittwoch, 16. Dezember'],
  ['2026-12-01', 21, 'mercredi 2 décembre', 'mercredi 9 décembre', 'Mercredi 23 décembre', 'Mittwoch, 23. Dezember'],
];

const local = (iso) => {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
};

test('the copy shifts its dates as the server does', () => {
  for (const [start, shift, day1, ticket, moved, movedDe] of SERVER) {
    assert.equal(shiftDays(local(start)), shift, start);
    assert.equal(renderText('{date:2026-11-11}', shift), day1);
    assert.equal(renderText('{date:2026-11-18}', shift), ticket);
    assert.equal(renderText('{date:2026-12-02|fr-cap}', shift), moved);
    assert.equal(renderText('{date:2026-12-02|de}', shift), movedDe);
  }
  assert.equal(renderText('{date:2026-12-01|fr-dm} {date:2026-11-13|fr-abbr} {date:2026-11-11|en-dm} {date:2026-11-11|de-dm}'), '1er décembre 13 nov. 11 November 11. November');
});

test('no date token reaches the learner from the quarter\'s own copy', () => {
  for (const level of ['a2', 'b1']) {
    for (const native of ['en', 'de']) {
      const page = pageOfCopy(undefined, { level, native, start: local('2026-11-24') });
      const text = JSON.stringify(page);
      assert.ok(!text.includes('{date'), `${level}/${native}`);
      assert.equal(page.story_date_fr, 'mercredi 25 novembre');
      const story = new OfflineStory({ level, native, start: local('2026-11-24') });
      assert.ok(!JSON.stringify(story).includes('{date'), `${level}/${native} offline story`);
    }
  }
  assert.ok(!JSON.stringify(pageOfCopy()).includes('{date'), 'no start: today');
});
