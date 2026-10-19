/* Ton personnage · the learner's character: its record, its drawing, the editor and the profile.
 *   node --test components/avatar/avatar.test.js
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

require('../../node_modules/sucrase/register/ts');
require('../../node_modules/sucrase/register/tsx');

const ROOT = path.resolve(__dirname, '../..');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
global.React = React;

const {
  AVATAR_SLOTS,
  AVATAR_TOGGLES,
  DEFAULT_AVATAR,
  EYE_COLOURS,
  FABRICS,
  HAIR_COLOURS,
  REWARDS,
  SKINS,
  SLOT_OPTIONS,
  isLocked,
  normalizeAvatar,
  randomAvatar,
  readAvatar,
  sameAvatar,
} = require('@/lib/avatar.ts');
const {
  AVATAR_STORAGE_KEY,
  avatarStateFrom,
  fetchLearnerAvatar,
  saveFailure,
  saveLearnerAvatar,
} = require('@/lib/learner-avatar.ts');
const { clearPilotResilience } = require('@/lib/pilot-resilience.ts');
const { resetOncePerLoad } = require('@/lib/once-per-load.ts');
const api = require('@/services/api.ts').default;
const { Avatar, AvatarDisc } = require('./Avatar.tsx');
const { AvatarEditor, EDITOR_TABS, SLOT_VIEW, reactionFor, tabForSlot } = require('./AvatarEditor.tsx');
const { AVATAR_COPY } = require('./avatar-copy.ts');

const COLOUR_SLOTS = ['skin', 'hairColor', 'eyeColor', 'hatColor', 'topColor'];
const ALL_ITEMS = Object.keys(REWARDS);
const holes = (s) => (String(s).match(/\{\w+\}/g) || []).sort().join(',');

/** A seeded dice, so a failure names the same roll every time. */
function dice(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

test('every slot has choices, and the default record wears the first plain one of each', () => {
  for (const slot of AVATAR_SLOTS) {
    assert.ok(SLOT_OPTIONS[slot].length >= 2, slot);
    assert.ok(SLOT_OPTIONS[slot].includes(DEFAULT_AVATAR[slot]), slot);
    assert.equal(isLocked(slot, DEFAULT_AVATAR[slot]), false, `${slot}: the default is never an earned piece`);
  }
  assert.equal(DEFAULT_AVATAR.v, 1);
  for (const id of SLOT_OPTIONS.skin) assert.ok(SKINS[id], id);
  for (const id of SLOT_OPTIONS.hairColor) assert.ok(HAIR_COLOURS[id], id);
  for (const id of SLOT_OPTIONS.eyeColor) assert.ok(EYE_COLOURS[id], id);
  for (const id of [...SLOT_OPTIONS.hatColor, ...SLOT_OPTIONS.topColor]) assert.ok(FABRICS[id], id);
});

test('each earned piece is a choice of its own slot, won by one achievement', () => {
  const achievements = new Set();
  for (const [item, reward] of Object.entries(REWARDS)) {
    assert.ok(SLOT_OPTIONS[reward.slot].includes(item), `${item} is a ${reward.slot}`);
    assert.ok(!achievements.has(reward.achievement), `${reward.achievement} gives one piece`);
    achievements.add(reward.achievement);
    assert.equal(isLocked(reward.slot, item, []), true);
    assert.equal(isLocked(reward.slot, item, [item]), false);
  }
  // the owner's example: helping fifty times wins a bracelet
  assert.deepEqual(REWARDS.bracelet, { slot: 'wrist', achievement: 'helps_50' });
});

test('a stored record is made safe: unknown ids dropped, pieces not held taken off', () => {
  assert.equal(readAvatar(null), null);
  assert.equal(readAvatar([]), null);
  const odd = normalizeAvatar({ v: 1, hair: 'mohawk', hat: 'beret', hairColor: 'bleu', freckles: 'yes', extra: 'x' });
  assert.equal(odd.hair, DEFAULT_AVATAR.hair);
  assert.equal(odd.hat, 'beret');
  assert.equal(odd.hairColor, 'bleu');
  assert.equal(odd.freckles, false);
  assert.ok(!('extra' in odd));
  const dressed = { ...DEFAULT_AVATAR, wrist: 'bracelet', glasses: 'soleil' };
  assert.equal(normalizeAvatar(dressed).wrist, 'bracelet', 'drawing a record keeps what it wears');
  const held = normalizeAvatar(dressed, ['soleil']);
  assert.equal(held.wrist, 'aucun');
  assert.equal(held.glasses, 'soleil');
  assert.ok(sameAvatar(normalizeAvatar(DEFAULT_AVATAR), DEFAULT_AVATAR));
});

test('a roll of the dice never puts on a piece the learner has not won', () => {
  for (let seed = 1; seed <= 200; seed += 1) {
    const rolled = randomAvatar(dice(seed), []);
    for (const slot of AVATAR_SLOTS) {
      assert.ok(SLOT_OPTIONS[slot].includes(rolled[slot]), `${seed}:${slot}`);
      assert.equal(isLocked(slot, rolled[slot], []), false, `${seed}:${slot}=${rolled[slot]}`);
    }
  }
});

test('every choice of every slot draws, with no stray colour and nothing that cannot stop moving', () => {
  for (const slot of AVATAR_SLOTS) {
    for (const value of SLOT_OPTIONS[slot]) {
      const html = renderToStaticMarkup(React.createElement(Avatar, { config: { ...DEFAULT_AVATAR, [slot]: value }, crop: 'full', size: 120, still: true }));
      assert.ok(html.startsWith('<svg'), `${slot}=${value}`);
      assert.ok(!html.includes('NaN'), `${slot}=${value} has a NaN`);
      assert.ok(!html.includes('undefined'), `${slot}=${value} has an undefined`);
    }
  }
  for (const key of AVATAR_TOGGLES) {
    const html = renderToStaticMarkup(React.createElement(Avatar, { config: { ...DEFAULT_AVATAR, [key]: !DEFAULT_AVATAR[key] }, still: true }));
    assert.ok(html.startsWith('<svg'), key);
  }
  const moving = renderToStaticMarkup(React.createElement(Avatar, { config: DEFAULT_AVATAR, gesture: 'signature' }));
  assert.match(moving, /prefers-reduced-motion/, 'every motion stops for Reduce Motion');
});

test('the disc is a face, or a «+» when there is no character yet', () => {
  const empty = renderToStaticMarkup(React.createElement(AvatarDisc, { config: null }));
  assert.match(empty, /data-avatar-disc="plus"/);
  assert.match(empty, /av-disc--empty/);
  const face = renderToStaticMarkup(React.createElement(AvatarDisc, { config: DEFAULT_AVATAR }));
  assert.match(face, /data-avatar-disc="face"/);
  assert.match(face, /<svg/);
});

test('the copy tables are complete in three languages and fill the same placeholders', () => {
  const fr = AVATAR_COPY.fr;
  for (const language of ['en', 'de']) {
    const table = AVATAR_COPY[language];
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort(), language);
    for (const key of Object.keys(fr)) {
      if (typeof fr[key] === 'string') assert.equal(holes(table[key]), holes(fr[key]), `${language}.${key}`);
      else assert.deepEqual(Object.keys(table[key]).sort(), Object.keys(fr[key]).sort(), `${language}.${key}`);
    }
  }
  for (const language of ['fr', 'en', 'de']) {
    const table = AVATAR_COPY[language];
    for (const slot of AVATAR_SLOTS) {
      assert.ok(table[`sec_${slot}`], `${language}: sec_${slot}`);
      if (COLOUR_SLOTS.includes(slot)) {
        if (slot !== 'skin') for (const id of SLOT_OPTIONS[slot]) assert.ok(table.colours[id], `${language}: colour ${id}`);
      } else {
        for (const value of SLOT_OPTIONS[slot]) assert.ok(table.parts[`${slot}.${value}`], `${language}: ${slot}.${value}`);
      }
    }
    for (const reward of Object.values(REWARDS)) assert.ok(table.earn[reward.achievement], `${language}: earn ${reward.achievement}`);
    for (const key of AVATAR_TOGGLES) assert.ok(table[`toggle_${key}`], `${language}: toggle_${key}`);
  }
});

test('the editor offers every slot and every switch, each on one tab, framed on its own view', () => {
  const offered = new Set();
  const switches = new Set();
  for (const tab of EDITOR_TABS) {
    for (const section of tab.sections) {
      if (section.slot) {
        assert.ok(!offered.has(section.slot), `${section.slot} twice`);
        offered.add(section.slot);
      }
      if (section.keys) section.keys.forEach((key) => switches.add(key));
    }
  }
  assert.deepEqual([...offered].sort(), [...AVATAR_SLOTS].sort());
  assert.deepEqual([...switches].sort(), [...AVATAR_TOGGLES].sort());
  for (const slot of AVATAR_SLOTS) assert.ok(SLOT_VIEW[slot], slot);
  assert.equal(tabForSlot('wrist'), 'extras');
  assert.equal(tabForSlot('hairColor'), 'hair');
  // a new piece is shown off; a hat is greeted with a wave
  assert.equal(reactionFor('wrist').gesture, 'montre');
  assert.equal(reactionFor('hat').gesture, 'salut');
});

test('the editor draws the character, its tabs, and a padlock with the way to win each earned piece', () => {
  const html = renderToStaticMarkup(
    React.createElement(AvatarEditor, {
      copy: AVATAR_COPY.fr,
      initial: DEFAULT_AVATAR,
      unlocked: ['montre'],
      rewards: [
        { item: 'bracelet', slot: 'wrist', achievement_key: 'helps_50', name: 'L’entraide', description: null, tier: 'silver', current: 23, target: 50, unlocked: false, unlocked_at: null },
        { item: 'montre', slot: 'wrist', achievement_key: 'session_streak_3', name: 'Trois jours', description: null, tier: 'bronze', current: 3, target: 3, unlocked: true, unlocked_at: null },
      ],
      initialTab: 'extras',
      onSave: async () => ({ error: null }),
      onDone: () => {},
    }),
  );
  assert.match(html, /role="tablist"/);
  assert.match(html, /C’est moi !/);
  assert.match(html, /Au hasard/);
  // the bracelet is locked, with how far the learner is; the watch, won, is not
  assert.match(html, /aria-label="Bracelet brésilien · À gagner · 23 sur 50"/);
  assert.match(html, /23\/50/);
  assert.match(html, /aria-label="Montre"/);
  assert.ok(!html.includes('aria-label="Montre · À gagner'));
  // the close button only outside onboarding (no onClose given here)
  assert.ok(!html.includes('aria-label="Fermer"'));
  const first = renderToStaticMarkup(
    React.createElement(AvatarEditor, {
      copy: AVATAR_COPY.en,
      initial: DEFAULT_AVATAR,
      unlocked: [],
      rewards: [],
      first: true,
      onSave: async () => ({ error: null }),
      onClose: () => {},
      onDone: () => {},
    }),
  );
  assert.match(first, /Make your character/);
  assert.ok(!first.includes('aria-label="Close"'), 'onboarding has no way out but making one');
});

test('the server’s answer becomes the hook’s state, and a refused piece is told apart', () => {
  const state = avatarStateFrom({ avatar: { v: 1, hair: 'afro' }, unlocked: ['montre', 3], rewards: [] });
  assert.equal(state.avatar.hair, 'afro');
  assert.deepEqual(state.unlocked, ['montre']);
  assert.equal(state.load, 'ready');
  assert.equal(avatarStateFrom({ avatar: null, unlocked: [], rewards: [] }).avatar, null);
  assert.deepEqual(saveFailure({ response: { status: 403, data: { detail: { code: 'avatar_item_locked', item: 'bracelet' } } } }), {
    ok: false,
    reason: 'locked',
    item: 'bracelet',
  });
  assert.deepEqual(saveFailure({ response: { status: 500 } }), { ok: false, reason: 'failed' });
  assert.deepEqual(saveFailure(new Error('offline')), { ok: false, reason: 'failed' });
});

/** A `localStorage` stand-in with the key walk the sign-out sweep uses. */
function memoryStore() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
    key: (index) => [...map.keys()][index] ?? null,
    get length() {
      return map.size;
    },
  };
}

test('the cached character is swept with the other learner caches at sign-out', () => {
  const store = memoryStore();
  store.setItem(AVATAR_STORAGE_KEY, JSON.stringify({ avatar: { v: 1 }, unlocked: ['montre'] }));
  store.setItem('atelier.theme', 'dark');
  clearPilotResilience(store);
  assert.equal(store.getItem(AVATAR_STORAGE_KEY), null, 'a second account must not start from this character');
  assert.equal(store.getItem('atelier.theme'), 'dark', 'device preferences stay');
});

test('a save is never undone by the read it overtook, nor by a read shared from before it', async () => {
  const before = { avatar: null, unlocked: [], rewards: [] };
  const saved = { avatar: { v: 1, hair: 'afro' }, unlocked: [], rewards: [] };
  const original = { get: api.getAvatar, put: api.saveAvatar };
  let release = null;
  api.getAvatar = () => new Promise((resolve) => (release = () => resolve(before)));
  api.saveAvatar = async () => saved;
  try {
    resetOncePerLoad();
    const overtaken = fetchLearnerAvatar();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal((await saveLearnerAvatar({ ...DEFAULT_AVATAR, hair: 'afro' })).ok, true);
    release();
    assert.equal(await overtaken, null, 'the read that started before the save is dropped');
    api.getAvatar = async () => saved;
    assert.equal((await fetchLearnerAvatar()).avatar.hair, 'afro', 'a screen mounted after the save reads afresh');
  } finally {
    api.getAvatar = original.get;
    api.saveAvatar = original.put;
    resetOncePerLoad();
  }
});

test('the styles use the design tokens, never a raw colour', () => {
  const styles = fs.readFileSync(path.join(__dirname, 'AvatarStyles.tsx'), 'utf8');
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(styles));
  assert.ok(!/rgba?\(/.test(styles));
});

test('the Cahier opens «Moi» from the learner’s disc, and sign-up makes the character first', () => {
  const notebook = fs.readFileSync(path.join(ROOT, 'pages/notebook.tsx'), 'utf8');
  assert.ok(notebook.includes("explicitMode === 'moi'"));
  assert.ok(notebook.includes('<ProfileTab />'));
  assert.ok(notebook.includes("onOpen={() => switchMode('moi')}"));
  const signup = fs.readFileSync(path.join(ROOT, 'pages/auth/signup.tsx'), 'utf8');
  assert.ok(signup.includes('router.replace(firstStop)'));
  const editor = fs.readFileSync(path.join(ROOT, 'pages/personnage.tsx'), 'utf8');
  assert.ok(editor.includes('sanitizeAuthCallbackUrl(router.query.next'), 'the way out is a same-site path');
});
