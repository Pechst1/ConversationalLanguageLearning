// node --test components/revue/vignette.test.js
//
// WP-120 phase B · RvVignette, the composed stamp.
//
//   1. each ring draws its colour role (ink · blue · red) through data-ring;
//   2. the pictogram is sanitised client-side: a hostile SVG loses its script,
//      external image, handlers, style and text, the shapes stay;
//   3. the three sizes (28 / 64 / 160 px), the week on the ring, the place in
//      Garamond, the kept mark, the stamping class;
//   4. the wire parser and the client's `vignettes()` call.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const { h, render, WEB_ROOT } = require('./revue-test-setup');

const { RvVignette } = require('./RvVignette.tsx');
const model = require('./vignette-model.ts');
const types = require('../../lib/revue-types.ts');
const { createRevueClient } = require('../../lib/revue-api.ts');

const PICTO =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
  '<circle cx="50" cy="50" r="20" fill="#1D3A8A"/>' +
  '<rect x="40" y="60" width="20" height="8" rx="2" fill="#D8321A"/>' +
  '<path d="M50 30L60 45L40 45Z" fill="#F3C318"/></svg>';

const BASE = { week: '2026-W40', placeLabelFr: "Le marché d'Aligre", ring: 'headline', keptContribution: false, pictogramSvg: PICTO };

test('each ring is drawn with its colour role', () => {
  for (const ring of ['headline', 'question', 'report']) {
    const html = render(h(RvVignette, { ...BASE, ring }));
    assert.match(html, new RegExp(`data-ring="${ring}"`));
    assert.match(html, /class="rv-vignette__band"/);
    assert.match(html, /class="rv-vignette__inner"/);
  }
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles', 'revue.css'), 'utf8');
  assert.match(css, /\.rv-vignette__band \{ fill: var\(--av2-ink\); \}/);
  assert.match(css, /\[data-ring='question'\] \.rv-vignette__band \{ fill: var\(--av2-blue\); \}/);
  assert.match(css, /\[data-ring='report'\] \.rv-vignette__band \{ fill: var\(--av2-red\); \}/);
  assert.match(css, /prefers-reduced-motion: reduce\) \{ \.av2 \.rv-vignette--stamping \.rv-vignette__stamp \{ animation: none; \}/);
  assert.match(css, /animation: rv-stamp 0\.3s/);
});

test('the pictogram is inlined, sanitised', () => {
  const html = render(h(RvVignette, BASE));
  assert.match(html, /<svg class="rv-vignette__picto"[^>]*viewBox="0 0 100 100"/);
  assert.ok(html.includes('<circle cx="50" cy="50" r="20" fill="#1D3A8A"/>'));
  assert.ok(html.includes('<path d="M50 30L60 45L40 45Z" fill="#F3C318"/>'));
});

test('a hostile svg loses its script, image, handlers, styles and text', () => {
  const hostile =
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100" onload="alert(1)">' +
    '<script>alert("x")</script><script type="text/javascript"><![CDATA[ steal() ]]></script>' +
    '<style>circle{fill:url(javascript:alert(1))}</style>' +
    '<image href="https://evil.example/p.png" xlink:href="https://evil.example/p.png" width="100" height="100"/>' +
    '<foreignObject><div>hi</div></foreignObject>' +
    '<circle cx="50" cy="50" r="20" fill="#1D3A8A" onclick="alert(2)" style="fill:red" id="x"/>' +
    '<path d="javascript:alert(3)" fill="#D8321A"/>' +
    '<rect x="40" y="60" width="20" height="8" fill="url(#evil)"/>' +
    '<text x="10" y="10">Vote</text>' +
    '<a href="https://evil.example"><ellipse cx="50" cy="70" rx="10" ry="4" fill="#14110D"/></a>' +
    '</svg>';
  const inner = model.sanitisePictogram(hostile);
  assert.equal(
    inner,
    '<circle cx="50" cy="50" r="20" fill="#1D3A8A"/><ellipse cx="50" cy="70" rx="10" ry="4" fill="#14110D"/>',
  );
  const html = render(h(RvVignette, { ...BASE, pictogramSvg: hostile }));
  for (const bad of ['<script', 'alert', 'evil.example', '<image', '<text x="10"', 'onclick', 'onload', 'style=', 'Vote', 'foreignObject', 'javascript']) {
    assert.ok(!html.includes(bad), `${bad} must not survive`);
  }
  assert.equal(model.sanitisePictogram(null), '');
  assert.equal(model.sanitisePictogram('<script>alert(1)</script>'), '');
  assert.equal(model.sanitisePictogram('<path fill="#14110D"/>'), '', 'a path without d is dropped');
});

test('sizes: pin 28, seal 64, large 160; the week on the ring; the place beneath', () => {
  assert.deepEqual(model.VIGNETTE_SIZE_PX, { pin: 28, seal: 64, large: 160 });

  const pin = render(h(RvVignette, { ...BASE, size: 'pin' }));
  assert.match(pin, /width="28" height="28"/);
  assert.ok(!pin.includes('rv-vignette__week'), 'no lettering at pin size');
  assert.ok(!pin.includes('figcaption'), 'no caption at pin size');
  assert.match(pin, /aria-label="Vignette, semaine 40 · Le marché d&#x27;Aligre · tu as fait un titre"/);

  const seal = render(h(RvVignette, { ...BASE, size: 'seal' }));
  assert.match(seal, /width="64" height="64"/);
  assert.match(seal, /<text class="rv-vignette__week"[^>]*>40<\/text>/);
  assert.match(seal, /<figcaption class="rv-vignette__place" lang="fr"[^>]*>Le marché d&#x27;Aligre<\/figcaption>/);

  const large = render(h(RvVignette, { ...BASE, size: 'large', stamping: true }));
  assert.match(large, /width="160" height="160"/);
  assert.match(large, /<textPath[^>]*>semaine 40<\/textPath>/);
  assert.match(large, /class="rv-vignette rv-vignette--large rv-vignette--stamping"/);

  assert.match(render(h(RvVignette, BASE)), /width="64"/, 'seal is the default');
});

test('the kept mark appears only when the contribution was kept', () => {
  assert.ok(!render(h(RvVignette, BASE)).includes('rv-vignette__kept'));
  const kept = render(h(RvVignette, { ...BASE, ring: 'question', keptContribution: true }));
  assert.match(kept, /class="rv-vignette__kept"/);
  assert.match(kept, /data-kept=""/);
  assert.match(kept, /tu as fait une question de lecteur · ta part est dans la dépêche/);
});

test('week numbers and labels', () => {
  assert.equal(model.weekNumber('2026-W40'), 40);
  assert.equal(model.weekNumber('2026-W03'), 3);
  assert.equal(model.weekNumber('W40'), null);
  assert.equal(model.isVignetteRing('report'), true);
  assert.equal(model.isVignetteRing('trophy'), false);
});

test('the wire parser and the client call', async () => {
  const wire = {
    vignettes: [
      {
        id: 'v1', session_id: 's1', dossier_id: 'd1', week: '2026-W40', place_label_fr: 'Le marché',
        ring: 'question', kept_contribution: true, pictogram_svg: PICTO, headline_fr: 'Les prix', minted_at: '2026-10-01T09:00:00Z',
      },
      { id: 'v2', ring: 'trophy' },
    ],
  };
  const parsed = types.parseVignettes(wire);
  assert.equal(parsed.length, 2);
  assert.deepEqual(parsed[0], {
    id: 'v1', sessionId: 's1', dossierId: 'd1', week: '2026-W40', placeLabelFr: 'Le marché', ring: 'question',
    keptContribution: true, pictogramSvg: PICTO, headlineFr: 'Les prix', mintedAt: '2026-10-01T09:00:00Z',
  });
  assert.equal(parsed[1].ring, 'headline', 'an unknown ring reads as headline');

  const calls = [];
  const client = createRevueClient({ get: async (url) => (calls.push(url), wire), post: async () => ({}) });
  const list = await client.vignettes();
  assert.deepEqual(calls, ['/revue/vignettes']);
  assert.equal(list[0].ring, 'question');
});
