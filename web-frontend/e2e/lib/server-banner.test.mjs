// node --test e2e/lib/server-banner.test.mjs
//
// `no-server-banner-while-typing` (#794). The walk reads the whole screen's text, and that
// text holds the scene: French a learner is reading. On 14 Nov main's season walk failed
// because Marin asked «Tu aides le serveur ?» — a waiter, not a server. The check must find
// the app's own connection sentences, in every interface language, and nothing a story says.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { SERVER_BANNER } from './assertions.mjs';

const COPY = new URL('../../components/atelier-v2/journey/journey-copy.ts', import.meta.url);
// The keys whose sentence tells the learner an answer has not reached the server, or is on its
// way there: what the check is for. offline_* sit in `.journey-connection`, read by element.
const BANNER_KEYS = ['transport_error', 'transport_error_plain', 'pending_sync', 'syncing'];

/** Each language table's sentence for `key`, read from the copy the app ships. */
function shipped(key) {
  const src = readFileSync(COPY, 'utf8');
  const out = {};
  for (const lang of ['EN', 'DE', 'FR']) {
    const table = src.slice(src.indexOf(`const ${lang}: CopyTable = {`));
    const m = table.match(new RegExp(`\\n  ${key}: '((?:[^'\\\\]|\\\\.)*)'`));
    assert.ok(m, `${lang}.${key} not found in journey-copy.ts`);
    out[lang] = m[1];
  }
  return out;
}

test('scene and lesson text that names a serveur is not a server banner', () => {
  const screens = [
    // walk-main-23-season-b, day 9, 549ed357205c: the Forge's example sentence.
    'La Forge · Forge today’s rule 20/24 Finish Review · due today Le, la, les as object pronouns Level 6 The rule Marin tu Marin: « Tu aides le serveur ? » (Do you help the waiter?)',
    // walk-main-21-season-b, day 6: a scene exchange.
    'Scene · Step 5 of 10 Le quai de Valmy Lila Exchange 2 of 3 Lila: Tu m’aides ? You: Oui, je peux vous aider samedi. Lila: Merci. Et après, on fait quoi ? Lila: Le serveur du café nous attend.',
    'Le serveur apporte deux cafés. Il a déjà envoyé la note.',
    // German scene glosses and lesson copy say «gesendet» and «Server» too.
    'Der Kellner hat die Rechnung schon gesendet. Feedback gesendet.',
  ];
  for (const text of screens) assert.equal(SERVER_BANNER.test(text), false, `matched story text: «${text}»`);
});

test('every connection sentence the app ships is a server banner, in every language', () => {
  for (const key of BANNER_KEYS) {
    for (const [lang, sentence] of Object.entries(shipped(key))) {
      assert.ok(SERVER_BANNER.test(sentence), `${lang}.${key} «${sentence}» is not caught`);
      assert.ok(SERVER_BANNER.test(`Scene · Step 5 of 10 Lila: Merci. ${sentence} Check`), `${lang}.${key} not caught on a screen`);
    }
  }
});

test('the walk’s check reads the banner element and the banner sentence, not the scene', async () => {
  const { serverBanner } = await import('./assertions.mjs');
  const scene = 'Marin: « Tu aides le serveur ? »';
  assert.equal(serverBanner({ connection: [], text: scene }), false);
  assert.equal(serverBanner({ connection: ['offline_cached'], text: scene }), true);
  assert.equal(serverBanner({ connection: [], text: `${scene} Le serveur n’a pas reçu cela. Réessaie.` }), true);
});
