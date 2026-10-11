/* 2026-10-01 · Settings in one place on every tab, plus the quick sheet behind the mark.
 *   node --test components/layout/shell-corner.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '../..');
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

test('the four tabs all carry the same settings corner', () => {
  for (const file of [
    'components/atelier-v2/home/HomeScreen.tsx',
    'components/feuilleton/archive/FeuilletonArchive.tsx',
    'pages/missions.tsx',
    'pages/notebook.tsx',
  ]) {
    assert.match(read(file), /<ShellCorner\b/, file);
  }
});

test('the streak no longer takes the gear away on La Une', () => {
  const home = read('components/atelier-v2/home/HomeScreen.tsx');
  assert.doesNotMatch(home, /streak > 0 \? \([\s\S]{0,400}\) : \(\s*<Link className="av2-icon-btn" href=\{settingsHref\}/);
  assert.match(home, /<ShellCorner href=\{settingsHref\} label=\{copy\.settings\} \/>\s*\{streak > 0 \?/);
});

test('the La Une mark opens the quick settings', () => {
  const home = read('components/atelier-v2/home/HomeScreen.tsx');
  assert.match(home, /className="av2-home__mark-btn"[\s\S]*onClick=\{\(\) => setQuickOpen\(true\)\}/);
  assert.match(home, /<QuickSettings open=\{quickOpen\}/);
  const sheet = read('components/layout/QuickSettings.tsx');
  assert.match(sheet, /setArtSet\(option\.value\)/);
  assert.match(sheet, /href="\/settings"/);
});

test('the gear is a cog, not a sun', () => {
  const shapes = read('components/atelier-v2/ui/Shapes.tsx');
  const gear = shapes.slice(shapes.indexOf('export const GearIcon'), shapes.indexOf('export const GearIcon') + 1200);
  assert.doesNotMatch(gear, /M12 2\.8v3/, 'the eight-ray sun is gone');
  assert.match(gear, /a2 2 0 1 1/, 'toothed outline');
});
