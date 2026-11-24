// node --test components/courrier/courrier-format.test.js
//
// #953 (child of #147) — walks of 20 and 22 Nov (A1, German chrome): «Un mot de Marin»,
// two chat lines in tu, opened the composer as «Deine E-Mail · Ein Betreff, eine Anrede,
// der Text, ein Gruß» with «E-Mail senden». The server now holds a letter's shape to its
// writer's register; a letter stored before that still says `email_formal`, so the page
// reads the same rule: a writer in tu gets the chat composer, a writer in vous keeps
// the e-mail frame.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const Module = require('node:module');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const WRITING = { title: '', instruction: '', placeholder: '' };

// The letter the walk opened: a story letter from Marin, in tu, stored as `email_formal`.
const MARIN = {
  mission_format: 'email_formal',
  prompt_payload: {
    mission_format: 'email_formal',
    target_register: 'tu / registre familier',
    messenger: { contact_name: 'Marin', channel_label: 'Message', target_register: 'tu / registre familier' },
  },
};

const MAIRIE = {
  mission_format: 'email_formal',
  prompt_payload: {
    mission_format: 'email_formal',
    target_register: 'vous / administrative formal',
    messenger: { contact_name: 'Accueil Mairie' },
  },
};

test('a friend\'s note in tu opens «Deine Antwort» and «Senden», not the e-mail frame', () => {
  const { missionFormat, formatComposerCopy, submitLabel } = require('./courrier-format.ts');
  const { courrierCopy } = require('./courrier-copy.ts');
  const de = courrierCopy('de');

  const format = missionFormat(MARIN);
  const copy = formatComposerCopy(format, WRITING, de);

  assert.equal(copy.label, 'Deine Antwort', `Marin's tu note opens «${copy.label}»`);
  assert.equal(copy.instruction, '', `Marin's tu note asks for «${copy.instruction}»`);
  assert.doesNotMatch(copy.placeholder, /Objet|Madame/);
  assert.equal(submitLabel(format, de), 'Senden');
});

test('a form from a writer in tu is a message too', () => {
  const { missionFormat } = require('./courrier-format.ts');
  const form = { ...MARIN, mission_format: 'admin_form', prompt_payload: { ...MARIN.prompt_payload, mission_format: 'admin_form' } };
  assert.equal(missionFormat(form), 'chat_message');
});

test('a writer in vous keeps the e-mail frame', () => {
  const { missionFormat, formatComposerCopy, submitLabel } = require('./courrier-format.ts');
  const { courrierCopy } = require('./courrier-copy.ts');
  const de = courrierCopy('de');

  const format = missionFormat(MAIRIE);

  assert.equal(format, 'email_formal');
  assert.equal(formatComposerCopy(format, WRITING, de).label, 'Deine E-Mail');
  assert.equal(submitLabel(format, de), 'E-Mail senden');
});

test('the tu reading follows the server\'s: «informal» is tu, «formal» and «polite» are not', () => {
  const { writerSaysTu } = require('./courrier-format.ts');
  assert.equal(writerSaysTu('tu / warm informal'), true);
  assert.equal(writerSaysTu('tu / friendly neighbour'), true);
  assert.equal(writerSaysTu('vous / warm but polite'), false);
  assert.equal(writerSaysTu('polite formal'), false);
  assert.equal(writerSaysTu('attitude polie'), false);
  assert.equal(writerSaysTu(undefined), false);
});
