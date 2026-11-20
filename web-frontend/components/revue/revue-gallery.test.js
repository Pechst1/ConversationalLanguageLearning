// node --test components/revue/revue-gallery.test.js
//
// «Papier · photos» (owner, 2026-11-20) · the story's gallery.
//
//   1. the wire's `stage.pictures` parse (kind, url, size, alt, caption, credit,
//      licence, links); an older stage parses to no pictures; a non-https link is dropped;
//   2. the strip leaves out the picture already printed (the plate) and repeats none;
//      with the default switches (the painted picture alone) it is empty and nothing renders;
//   3. a photo carries its licence and source links, an illustration none;
//   4. RvGallery prints every credit line, the links open in a new tab, a caption is the alt;
//   5. the «Lire» screen of the comptoir player and the Une card show the strip only when
//      there is more than the first picture; the chat stage's arrival shows it too;
//   6. every new chrome string exists in fr, de and en.

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { h, render, visibleText, fixture } = require('./revue-test-setup');

const types = require('../../lib/revue-types.ts');
const { createMockRevueClient } = require('../../lib/revue-mock.ts');
const { revueCopy } = require('./revue-copy.ts');
const { galleryStrip, pictureLinks } = require('./revue-gallery.ts');
const { RvGallery } = require('./RvGallery.tsx');
const { RvUneCard, RvEncounter } = require('./index.ts');
const { RvComptoirRead } = require('./comptoir/RvComptoirRead.tsx');
const { comptoirCopy } = require('./comptoir/comptoir-copy.ts');
const { sessionGlosses } = require('./revue-model.ts');

const FR = revueCopy('fr');
const STORY = '/media/graphic-novel/revue-stories/evergreen-marche-du-dimanche-0123456789abcdef.webp';
const SHOT = '/media/graphic-novel/revue-stories/evergreen-marche-du-dimanche-2-fedcba9876543210.webp';
const PHOTO = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Marche_d'Aligre.jpg/1280px-Marche_d'Aligre.jpg";
const WIRE_PICTURES = [
  { kind: 'illustration', url: STORY, width: 1536, height: 1024, alt_fr: '', caption_fr: null, credit_fr: 'Illustration · Le Papier', licence: null, licence_url: null, source_url: null },
  { kind: 'illustration', url: SHOT, width: 1536, height: 1024, alt_fr: '', caption_fr: null, credit_fr: 'Illustration · Le Papier', licence: null, licence_url: null, source_url: null },
  {
    kind: 'photo', url: PHOTO, width: 1280, height: 960, alt_fr: "Marché d'Aligre", caption_fr: "Marché d'Aligre",
    credit_fr: 'Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons', licence: 'CC BY-SA 4.0',
    licence_url: 'https://creativecommons.org/licenses/by-sa/4.0', source_url: "https://commons.wikimedia.org/wiki/File:Marche_d'Aligre.jpg",
  },
];
const RAW_STAGE = {
  place_id: 'marche_aligre', place_fr: "Le marché d'Aligre, un matin", plate_url: STORY, plate_place_id: 'marche_aligre',
  place_is_real: true, dress: 'coat', cast: [{ id: 'romy_tremblay', hold: 'notebook' }, { id: 'user', hold: null }], plate_kind: 'story',
};

test('the wire\'s pictures parse; an older stage has none; only https links pass', () => {
  const stage = types.parseStage({ ...RAW_STAGE, pictures: WIRE_PICTURES });
  assert.equal(stage.pictures.length, 3);
  assert.deepEqual(stage.pictures[2], {
    kind: 'photo', url: PHOTO, width: 1280, height: 960, altFr: "Marché d'Aligre", captionFr: "Marché d'Aligre",
    creditFr: 'Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons', licence: 'CC BY-SA 4.0',
    licenceUrl: 'https://creativecommons.org/licenses/by-sa/4.0', sourceUrl: "https://commons.wikimedia.org/wiki/File:Marche_d'Aligre.jpg",
  });
  assert.deepEqual(types.parseStage(RAW_STAGE).pictures, [], 'an older payload: no pictures');
  const unsafe = types.parseStage({ ...RAW_STAGE, pictures: [{ ...WIRE_PICTURES[2], licence_url: 'javascript:alert(1)', source_url: 'http://x' }, { kind: 'photo' }] });
  assert.equal(unsafe.pictures.length, 1, 'a picture without a url is dropped');
  assert.equal(unsafe.pictures[0].licenceUrl, null);
  assert.equal(unsafe.pictures[0].sourceUrl, null);
});

test('the strip leaves out the picture already printed and repeats none', () => {
  const pictures = types.parseStage({ ...RAW_STAGE, pictures: [...WIRE_PICTURES, WIRE_PICTURES[1]] }).pictures;
  assert.deepEqual(galleryStrip(pictures, STORY).map((p) => p.url), [SHOT, PHOTO]);
  assert.deepEqual(galleryStrip(pictures, null).map((p) => p.url), [STORY, SHOT, PHOTO]);
  // The default switches: the painted picture alone, and it is the plate — nothing more to show.
  const alone = types.parseStage({ ...RAW_STAGE, pictures: WIRE_PICTURES.slice(0, 1) }).pictures;
  assert.deepEqual(galleryStrip(alone, STORY), []);
  assert.equal(render(h(RvGallery, { pictures: alone, mainUrl: STORY, copy: FR })), '');
  assert.equal(render(h(RvGallery, { pictures: [], mainUrl: null, copy: FR })), '');
});

test('a photo links its licence and its source; an illustration links nothing', () => {
  const [illustration, , photo] = types.parseStage({ ...RAW_STAGE, pictures: WIRE_PICTURES }).pictures;
  assert.deepEqual(pictureLinks(illustration, FR), []);
  assert.deepEqual(pictureLinks(photo, FR), [
    { kind: 'licence', href: 'https://creativecommons.org/licenses/by-sa/4.0', label: 'CC BY-SA 4.0' },
    { kind: 'source', href: "https://commons.wikimedia.org/wiki/File:Marche_d'Aligre.jpg", label: 'Source' },
  ]);
  // A public-domain photo whose licence link is its page: one link, named «Licence».
  const pd = { ...photo, licence: null, licenceUrl: photo.sourceUrl };
  assert.deepEqual(pictureLinks(pd, revueCopy('de')).map((link) => link.label), ['Lizenz']);
});

test('RvGallery prints every credit, the links open in a new tab, a caption is the alt', () => {
  const pictures = types.parseStage({ ...RAW_STAGE, pictures: WIRE_PICTURES }).pictures;
  const html = render(h(RvGallery, { pictures, mainUrl: STORY, copy: FR }));
  const text = visibleText(html);
  assert.match(html, /aria-label="Les images du sujet"/);
  assert.equal((html.match(/rv-gallery__item/g) || []).length, 2);
  assert.ok(text.includes('Illustration · Le Papier'));
  assert.ok(text.includes('Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons'));
  assert.ok(text.includes("Marché d'Aligre"), 'the caption is printed');
  assert.match(html, /alt="Marché d&#x27;Aligre"/);
  assert.match(html, /alt=""/, 'an illustration stays decorative');
  assert.match(html, /href="https:\/\/creativecommons.org\/licenses\/by-sa\/4.0" target="_blank" rel="noopener noreferrer"/);
  assert.match(html, /<span class="av2-sr"> \(nouvel onglet\)<\/span>/);
  assert.match(html, /referrerPolicy="no-referrer"|referrerpolicy="no-referrer"/);
});

async function comptoirSession(pictures) {
  const client = createMockRevueClient({ persist: false, comptoir: true, band: 'A2', language: 'en', pictures: true });
  await client.week();
  const session = await client.start();
  return { ...session, stage: { ...session.stage, pictures: types.parseStage({ ...RAW_STAGE, plate_url: session.stage.plateUrl, pictures }).pictures } };
}

function readProps(session) {
  const chrome = session.plan.uiLanguage;
  return {
    session, view: session.comptoir, copy: revueCopy(chrome), ccopy: comptoirCopy(chrome), glossLanguage: session.plan.glossLanguage,
    glosses: sessionGlosses(session), voice: { speak: () => {}, stop: () => {}, speakingKey: null, supported: false, progress: 0 },
    pending: null, readOnly: false, onAct: async () => true, onContinue: () => {}, wordFor: () => () => {}, notice: null, footRef: null,
  };
}

test('«Lire» shows the strip under the story\'s picture only when there is more to show', async () => {
  const plain = await comptoirSession([]);
  assert.doesNotMatch(render(h(RvComptoirRead, readProps(plain))), /rv-gallery/);
  const more = await comptoirSession(WIRE_PICTURES.map((p, i) => (i === 0 ? { ...p, url: plain.stage.plateUrl } : p)));
  const html = render(h(RvComptoirRead, readProps(more)));
  assert.match(html, /aria-label="Pictures of the story"/);
  assert.ok(html.indexOf('ct-pic') < html.indexOf('rv-gallery'), 'the first picture as today, the strip after it');
  assert.equal((html.match(/rv-gallery__item/g) || []).length, 2);
});

test('the Une card adds a compact strip only when the story has other pictures', () => {
  const offer = types.parseOffer(fixture('mock-wire').offer);
  const card = (story) => render(h(RvUneCard, { story, week: offer.week, state: 'offer', onOpen: () => {}, onOtherSubject: () => {}, copy: FR }));
  const base = card(offer.recommended);
  assert.doesNotMatch(base, /rv-gallery/, 'no pictures: the card is what it was');
  const mainUrl = offer.recommended.plateUrl ?? offer.recommended.stage.plateUrl;
  const pictures = types.parseStage({ ...RAW_STAGE, plate_url: mainUrl, pictures: WIRE_PICTURES.map((p, i) => (i === 0 ? { ...p, url: mainUrl } : p)) }).pictures;
  const html = card({ ...offer.recommended, stage: { ...offer.recommended.stage, pictures } });
  assert.match(html, /class="rv-gallery" data-size="compact"/);
  assert.ok(visibleText(html).includes('Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons'));
});

test('the chat stage shows the strip on arrival', async () => {
  const client = createMockRevueClient({ persist: false, band: 'A2', language: 'en', pictures: true });
  await client.week();
  const session = await client.start();
  const withPictures = { ...session, stage: { ...session.stage, pictures: types.parseStage({ ...RAW_STAGE, pictures: WIRE_PICTURES }).pictures } };
  const html = render(h(RvEncounter, { client, session: withPictures, onExit: () => {}, onReleve: () => {} }));
  assert.match(html, /class="rv-gallery"/);
  assert.doesNotMatch(render(h(RvEncounter, { client, session, onExit: () => {}, onReleve: () => {} })), /rv-gallery/);
});

test('every new chrome string exists in fr, de and en', () => {
  for (const key of ['gallery_label', 'picture_source', 'picture_licence', 'new_tab']) {
    const values = ['fr', 'de', 'en'].map((language) => revueCopy(language)[key]);
    assert.ok(values.every((value) => typeof value === 'string' && value.trim()), key);
  }
  assert.notEqual(revueCopy('de').gallery_label, revueCopy('en').gallery_label);
});

// Seen in a browser at 375 px (2026-11-20, Papier · together): the links' screen-reader
// words (`.av2-sr`, absolutely placed) escaped the strip's own scroll and widened the whole
// page to 769 px on a phone; the licence and source links were 16 px tall.
test('the strip holds its own overflow (the page never widens) and its links are 44 px targets', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const css = fs.readFileSync(path.join(__dirname, '..', '..', 'styles', 'revue.css'), 'utf8');
  const rule = (selector) => (css.match(new RegExp(`\\.av2 ${selector.replace(/[.]/g, '\\.')} \\{([^}]*)\\}`)) || [])[1] || '';
  assert.match(rule('.rv-gallery__strip'), /position: relative;/, 'the containing block of the sr-only words');
  assert.match(rule('.rv-gallery__strip'), /overflow-x: auto;/);
  assert.match(rule('.rv-gallery__link'), /min-height: var\(--av2-tap\);/);
  assert.match(rule('.rv-gallery__link'), /display: inline-flex;/);
});
