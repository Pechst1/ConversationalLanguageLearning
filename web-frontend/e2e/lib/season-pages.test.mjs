import assert from 'node:assert/strict';
import test from 'node:test';

import { daysSeen, fold, pageLines, SEASON_PAGES } from './season-pages.mjs';

test('every tentpole the walk looks for is a line of the season, with its other levels', () => {
  for (const page of SEASON_PAGES) {
    const lines = pageLines(page);
    assert.ok(lines.length >= 3, `${page.key}: ${lines.join(' | ')}`);
    assert.ok(lines[0].includes(fold(page.line)), page.key);
  }
});

test('#717: T2 served at A1 is seen on its day', () => {
  // What the server served on day 9 of the 11 Nov walk: the A1 caption of t2.a.
  const t2a = SEASON_PAGES.find((page) => page.key === 't2.a');
  const pages = [
    { day: 7, text: 'Read again — Mon grand-père a tout l’immeuble, sauf le premier étage.' },
    { day: 9, text: 'Là-haut\nMercredi. Ton billet est pour aujourd’hui. Tu es encore là.\nLila\nCroissants, café. On entre ?' },
  ];
  assert.deepEqual(daysSeen(t2a, pages), [9]);
  const t2b = SEASON_PAGES.find((page) => page.key === 't2.b');
  assert.deepEqual(daysSeen(t2b, [{ day: 10, text: 'Lila\nLila Bonnet. Architecte.' }]), [10]);
});

test('a page the walk never read is seen on no day', () => {
  const t2a = SEASON_PAGES.find((page) => page.key === 't2.a');
  assert.deepEqual(daysSeen(t2a, [{ day: 8, text: 'Un silence. Gus répète un discours sur des fiches.' }]), []);
});
