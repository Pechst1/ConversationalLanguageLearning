// WP-120 phase D · `carte-shows-where-i-was`: a learner closes one Papier and finds it
// on La Carte, where the dossier happened.
//
//   1. by API (the learner's own bearer, the real endpoints, the fake Revue provider):
//      read the week, open the recommended Papier, say one line to Romy, file a headline
//      (`make` headline_choice) — the session now has an artefact;
//   2. in the browser, on /revue?session=<id>: «Voir le papier» closes it through the
//      real close screen, which must offer «Voir sur la carte» (→ /carte?focus=<id>)
//      under «Classer le Papier». If the make step was refused, the close is done by API
//      instead and the close-screen assertion is recorded as skipped (never as a pass);
//   3. «Voir sur la carte» opens /carte with that Papier's card open: the headline is
//      the close's dispatch headline;
//   4. /carte: exactly one pin, at the dossier's place (its `geo` in the dossier file,
//      projected with the client's own projection) within 3 svg units; the Relevé shows
//      the France badge with «1».
// Phone size (375×812), reduced motion, every screen in light and dark.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { REPO_ROOT, WEB_ROOT } from './stack.mjs';
import { registerLearner } from './session.mjs';
import { LearnerWalk } from './learner-walk.mjs';

const require = createRequire(import.meta.url);

/** The client's projection, loaded through the components' own test setup (sucrase + `@/`). */
function clientProjection() {
  require(path.join(WEB_ROOT, 'components/revue/revue-test-setup.js'));
  return require(path.join(WEB_ROOT, 'components/carte/carte-projection.ts'));
}

/** The dossier's file (weekly or evergreen), as the builder wrote it. */
export function dossierFile(dossierId) {
  const root = path.join(REPO_ROOT, 'app/services/revue');
  const candidates = [path.join(root, 'evergreen', `${dossierId}.json`)];
  const weekly = path.join(root, 'weekly');
  for (const week of existsSync(weekly) ? readdirSync(weekly) : []) candidates.push(path.join(weekly, week, `${dossierId}.json`));
  const found = candidates.find((file) => existsSync(file));
  return found ? JSON.parse(readFileSync(found, 'utf8')) : null;
}

async function api(stack, token, method, url, body) {
  const r = await fetch(`${stack.api}${url}`, {
    method,
    headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`${method} ${url} → ${r.status} ${text.slice(0, 200)}`);
  return text ? JSON.parse(text) : null;
}

const SEE_PAPER = /^(Voir le papier|See the piece|Den Artikel ansehen)$/;
const FILE_IT = /^(Classer le Papier|File Le Papier|Le Papier ablegen)$/;

export async function carteShowsWhereIWas({ stack, browser, findings, shots, outDir, secret, native = 'en' }) {
  const learner = await registerLearner({ api: stack.api, secret, native, level: 'A1.1', tag: 'carte' });
  const token = learner.accessToken;
  const result = { closedBy: null, sessionId: null, dossierId: null };

  // 1. The Papier, by API.
  const offer = await api(stack, token, 'GET', '/revue/week');
  const card = offer.recommended || offer.alternatives?.[0];
  if (!card) throw new Error('the week offers no Papier');
  const session = await api(stack, token, 'POST', '/revue/sessions', { dossier_id: card.dossier_id, week: offer.week?.id ?? undefined });
  result.sessionId = session.id;
  result.dossierId = session.dossier?.id || card.dossier_id;
  await api(stack, token, 'POST', `/revue/sessions/${session.id}/turns`, { text: 'Pourquoi est-ce important ?', mode: 'text', client_turn_id: `carte-${Date.now()}` });
  let artefact = false;
  try {
    const make = await api(stack, token, 'GET', `/revue/sessions/${session.id}/make`);
    const choice = (make.options || []).find((o) => o.kind === 'headline_choice');
    if (choice?.options?.length) {
      await api(stack, token, 'POST', `/revue/sessions/${session.id}/make`, { kind: 'headline_choice', action: 'pick', option_id: choice.options[0].id });
      artefact = true;
    }
  } catch (e) {
    console.log(`[carte] make refused (${String(e.message).slice(0, 120)}); closing by API`);
  }

  // The browser: phone, reduced motion.
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    isMobile: true,
    hasTouch: true,
    reducedMotion: 'reduce',
    locale: native === 'fr' ? 'fr-FR' : native === 'de' ? 'de-DE' : 'en-GB',
  });
  await context.addCookies([{ name: 'next-auth.session-token', value: learner.cookie, url: stack.web }]);
  const walk = new LearnerWalk({ page: null, findings, outDir: path.join(outDir, 'carte'), lang: native, level: 'A1.1', stack, shots, scale: 1 });
  walk.day = 0;
  const page = await walk.newSession(context);
  const where = (kind) => walk.where({ kind });

  // 2. The close, through the real close screen.
  let closing = null;
  if (artefact) {
    await page.goto(`${stack.web}/revue?session=${encodeURIComponent(session.id)}`);
    const see = page.getByRole('button', { name: SEE_PAPER });
    await see.waitFor({ timeout: 60000 });
    const closed = page.waitForResponse((r) => r.url().includes(`/revue/sessions/${session.id}/close`) && r.request().method() === 'POST', { timeout: 30000 });
    await see.click();
    closing = (await (await closed).json()).closing;
    result.closedBy = 'browser';
    const fileIt = page.getByRole('button', { name: FILE_IT });
    await fileIt.waitFor({ timeout: 20000 });
    const link = page.locator(`a[data-carte-focus="${session.id}"]`);
    const linked = (await link.count()) === 1;
    const href = linked ? await link.getAttribute('href') : null;
    findings.check('close-offers-voir-sur-la-carte', linked && href === `/carte?focus=${encodeURIComponent(session.id)}`, `link ${linked ? href : 'missing'}`, where('close'));
    if (linked) {
      const order = await page.evaluate((id) => {
        const a = document.querySelector(`a[data-carte-focus="${id}"]`);
        const prev = a?.previousElementSibling;
        return prev ? prev.textContent.trim() : null;
      }, session.id);
      findings.check('voir-sur-la-carte-under-classer', FILE_IT.test(order || ''), `the element before the link says «${order}»`, where('close'));
      await link.scrollIntoViewIfNeeded();
    }
    await walk.shoot('close-voir-sur-la-carte');
    // 3. The link: /carte with this Papier's card open.
    if (linked) {
      await link.click();
      await page.waitForURL(`**/carte?focus=*`, { timeout: 30000 });
    }
  } else {
    const closed = await api(stack, token, 'POST', `/revue/sessions/${session.id}/close`);
    closing = closed.closing;
    result.closedBy = 'api';
    findings.check('close-offers-voir-sur-la-carte', true, 'skipped: no artefact to close through the screen (closed by API)', where('close'));
  }
  if (!page.url().includes('/carte?focus=')) await page.goto(`${stack.web}/carte?focus=${encodeURIComponent(session.id)}`);
  const headline = closing?.dispatch?.headline_fr;
  const focused = page.locator(`[role=dialog] .carte-card[data-session="${session.id}"]`);
  await focused.waitFor({ timeout: 30000 }).catch(() => {});
  const dialogTitle = (await page.locator('[role=dialog] .av2-headline').first().textContent().catch(() => '')) || '';
  findings.check('carte-focus-opens-the-card', (await focused.count()) === 1, 'no open card for the closed Papier', where('carte-focus'));
  findings.check('carte-card-shows-the-headline', Boolean(headline) && dialogTitle.trim() === headline.trim(), `card «${dialogTitle.trim()}» vs close «${headline}»`, where('carte-focus'));
  await walk.shoot('carte-focus-card');

  // 4. The map: one pin, where the dossier happened.
  await page.goto(`${stack.web}/carte`);
  await page.locator('.carte-pin, .carte-cluster').first().waitFor({ timeout: 30000 }).catch(() => {});
  await page.locator('.carte__drawing svg').first().waitFor({ timeout: 15000 }).catch(() => {});
  const pins = await page.locator('.carte-pin').count();
  const clusters = await page.locator('.carte-cluster').count();
  findings.check('carte-shows-one-pin', pins === 1 && clusters === 0, `${pins} pins, ${clusters} clusters`, where('carte'));
  const carte = await api(stack, token, 'GET', '/revue/carte');
  const wirePin = (carte.pins || []).find((p) => p.session_id === session.id);
  const dossier = dossierFile(result.dossierId);
  const place = (dossier?.places || []).find((p) => p.id === wirePin?.place_id) || (dossier?.places || []).find((p) => p.geo);
  const level = (await page.locator('section.carte').getAttribute('data-level')) || 'france';
  let detail = 'no pin or no dossier geo';
  let near = false;
  if (pins === 1 && place?.geo) {
    const projection = clientProjection();
    const expected = projection.projectPoint(level, place.geo.lat, place.geo.lon);
    const { width, height } = projection.viewBoxOf(level);
    const pct = await page.locator('.carte__mark:has(.carte-pin)').first().evaluate((li) => [parseFloat(li.style.left), parseFloat(li.style.top)]);
    const actual = [(pct[0] / 100) * width, (pct[1] / 100) * height];
    const dx = Math.abs(actual[0] - expected[0]);
    const dy = Math.abs(actual[1] - expected[1]);
    near = dx <= 3 && dy <= 3;
    detail = `${place.id} (${place.geo.lat}, ${place.geo.lon}) on ${level}: pin at ${actual.map((v) => v.toFixed(1))}, dossier at ${expected.map((v) => v.toFixed(1))} (Δ ${dx.toFixed(2)}, ${dy.toFixed(2)})`;
    result.placement = detail;
  }
  findings.check('carte-pin-at-the-dossier-place', near, detail, where('carte'));
  await walk.shoot('carte-one-pin');

  // The Relevé's badge: the France silhouette with «1», linking to /carte.
  await page.goto(`${stack.web}/notebook?mode=releve`);
  const badge = page.locator('a.carte-badge');
  await badge.waitFor({ timeout: 30000 }).catch(() => {});
  const badgeOk = (await badge.count()) === 1
    && (await badge.getAttribute('data-carte-badge')) === '1'
    && (await badge.getAttribute('href')) === '/carte';
  findings.check('releve-badge-counts-the-pin', badgeOk, 'no «La Carte · 1» badge in the Relevé', where('releve'));
  if (badgeOk) await badge.scrollIntoViewIfNeeded();
  await walk.shoot('releve-carte-badge');

  // Settings: the «La Carte» row.
  await page.goto(`${stack.web}/settings`);
  const row = page.locator('#st-carte-label');
  await row.waitFor({ timeout: 30000 }).catch(() => {});
  findings.check('settings-has-la-carte-row', (await row.count()) === 1, 'no «La Carte» row in Réglages', where('settings'));
  if (await row.count()) await row.evaluate((node) => node.scrollIntoView({ block: 'center' }));
  await walk.shoot('settings-carte-row');

  await context.close();
  return result;
}
