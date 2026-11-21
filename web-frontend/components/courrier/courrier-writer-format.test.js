// node --test components/courrier/courrier-writer-format.test.js
//
// #953 — a friend's note in tu is answered as a message, not as a formal e-mail.
//
// The walk of 20 Nov read «Un mot de Marin» (tu, chat bubbles) above a composer
// that said «Deine E-Mail · Ein Betreff, eine Anrede, der Text, ein Gruß.» and
// «E-Mail senden». The server now hands a tu writer's letter over as
// `chat_message` (tests/test_courrier_writer_format_953.py); these tests hold the
// screen's side: the page reads that shape through one module, and the composer
// for it says «Deine Antwort» / «Senden». An agency in vous keeps its e-mail.

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

const { formatComposerCopy, missionFormat, missionWriting, submitLabel } = require('./mission-format.ts');
const { courrierCopy } = require('./courrier-copy.ts');

const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'missions.tsx'), 'utf8');

// What serialize_mission returns for Marin's note: the server's shape, chat.
const MARIN = {
  id: 'm-953',
  mission_format: 'chat_message',
  prompt_payload: {
    mission_format: 'email_formal',
    custom_context: { source: 'story_born', relationship: 'marin', register: 'tu / registre familier' },
    messenger: { contact_name: 'Marin', channel_label: 'Message', target_register: 'tu / registre familier' },
  },
};
const AGENCY = {
  id: 'm-953-vous',
  mission_format: 'email_formal',
  prompt_payload: { mission_format: 'email_formal', target_register: 'vous / administrative formal' },
};

function composer(mission, lang) {
  const t = courrierCopy(lang);
  const format = missionFormat(mission);
  return { ...formatComposerCopy(format, missionWriting(mission), t), send: submitLabel(format, t) };
}

test('Marin’s tu note asks for «Deine Antwort» and sends with «Senden»', () => {
  const de = composer(MARIN, 'de');
  assert.equal(de.label, 'Deine Antwort');
  assert.equal(de.send, 'Senden');
  assert.equal(de.instruction, '');
  assert.doesNotMatch(`${de.label} ${de.instruction} ${de.send}`, /E-Mail|Betreff|Anrede/);
  assert.equal(composer(MARIN, 'en').send, 'Send');
  assert.equal(composer(MARIN, 'fr').label, 'Ta réponse');
});

test('a vous agency’s letter keeps the e-mail frame', () => {
  const de = composer(AGENCY, 'de');
  assert.equal(de.label, 'Deine E-Mail');
  assert.equal(de.send, 'E-Mail senden');
});

test('the page reads the shape through the shared module, not a copy of its own', () => {
  assert.match(PAGE, /from '@\/components\/courrier\/mission-format'/);
  assert.doesNotMatch(PAGE, /function (missionFormat|formatComposerCopy|submitLabel)\(/);
});
