// node --test e2e/lib/server-banner.test.mjs
//
// `no-server-banner-while-typing` (#794). The walk's screen text holds the scene: French a
// learner is reading. On 14 Nov main's season walk failed because Marin asked «Tu aides le
// serveur ?» (a waiter, not a server). The check reads the banner elements the app marks
// (components/atelier-v2/journey/connection-banner.test.js holds the app to that), and no
// word of the scene.
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { bannersOn, serverBanner } from './assertions.mjs';

const screen = (text, extra = {}) => ({ text, connection: [], connectionBanners: [], ...extra });

test('scene and lesson text that names a serveur is not a server banner', () => {
  const screens = [
    // walk-main-23-season-b, day 9, 549ed357205c: the Forge's example sentence.
    'La Forge · Forge today’s rule 20/24 Finish Review · due today Le, la, les as object pronouns Level 6 The rule Marin tu Marin: « Tu aides le serveur ? » (Do you help the waiter?)',
    // walk-main-21-season-b, day 6: a scene exchange.
    'Scene · Step 5 of 10 Le quai de Valmy Lila Exchange 2 of 3 Lila: Tu m’aides ? You: Oui, je peux vous aider samedi. Lila: Merci. Et après, on fait quoi ? Lila: Le serveur du café nous attend.',
    'Le serveur apporte deux cafés. Il a déjà envoyé la note.',
    // German glosses and lesson copy say «gesendet» and «Server» too.
    'Der Kellner hat die Rechnung schon gesendet. Feedback gesendet. Der Server im Café ist nett.',
    // Even the app's own sentence, quoted as text with no marker, is not what the check reads.
    'Lila: « Le serveur n’a pas reçu cela. » — Elle rit.',
  ];
  for (const text of screens) assert.equal(serverBanner(screen(text)), false, `read story text as a banner: «${text}»`);
});

test('a marked banner or the session notice is a server banner, whatever the text', () => {
  const scene = 'Marin: « Tu aides le serveur ? »';
  assert.equal(serverBanner(screen(scene, { connectionBanners: ['transport_error'] })), true);
  assert.equal(serverBanner(screen(scene, { connectionBanners: ['syncing'] })), true);
  assert.equal(serverBanner(screen(scene, { connection: ['offline_cached'] })), true);
  assert.equal(bannersOn(screen(scene, { connection: ['pending_sync'], connectionBanners: ['pending_sync'] })), 'pending_sync');
});

test('a snapshot from an older driver (no connectionBanners) still reads the notice', () => {
  assert.equal(serverBanner({ text: 'x', connection: [] }), false);
  assert.equal(serverBanner({ text: 'x', connection: ['syncing'] }), true);
});
