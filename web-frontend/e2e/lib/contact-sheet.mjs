import { writeFileSync } from 'node:fs';
import path from 'node:path';

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export function writeContactSheet({ outDir, shots, findings, meta }) {
  const failures = findings.failures;
  const summary = findings.summary();
  const groups = new Map();
  for (const s of shots) {
    const key = `${s.lang} · ${s.level} · day ${s.day}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(s);
  }
  const rows = [...groups.entries()]
    .map(
      ([title, list]) => `<section><h2>${esc(title)}</h2><div class="row">${list
        .map(
          (s) => `<figure><div class="pair"><a href="${esc(s.light)}"><img loading="lazy" src="${esc(s.light)}" alt=""></a><a href="${esc(s.dark)}"><img loading="lazy" src="${esc(s.dark)}" alt=""></a></div><figcaption>${esc(s.kind)}${s.note ? ` — ${esc(s.note)}` : ''}</figcaption></figure>`,
        )
        .join('')}</div></section>`,
    )
    .join('\n');
  const fail = failures.length
    ? `<table><tr><th>Assertion</th><th>Where</th><th>Detail</th></tr>${failures
        .map((f) => `<tr><td>${esc(f.id)}</td><td>${esc(JSON.stringify(f.where))}</td><td>${esc(f.detail)}</td></tr>`)
        .join('')}</table>`
    : '<p>No failed assertions.</p>';
  const sum = `<table><tr><th>Assertion</th><th>Pass</th><th>Fail</th></tr>${summary
    .map((r) => `<tr class="${r.fail ? 'bad' : ''}"><td>${esc(r.id)}</td><td>${r.pass}</td><td>${r.fail}</td></tr>`)
    .join('')}</table>`;
  const html = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Walk contact sheet</title>
<style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif}body{margin:16px;background:Canvas;color:CanvasText}
h1{font-size:1.3rem}h2{font-size:1rem;margin:1.5rem 0 .4rem}.row{display:flex;flex-wrap:wrap;gap:10px}
figure{margin:0;width:260px}.pair{display:flex;gap:2px}.pair img{width:128px;border:1px solid #8884;display:block}
figcaption{font-size:.75rem;opacity:.75;padding-top:2px}table{border-collapse:collapse;font-size:.8rem;margin:.5rem 0}
td,th{border:1px solid #8886;padding:3px 8px;text-align:left;vertical-align:top}tr.bad td{background:#f003}
</style>
<h1>Walk contact sheet</h1><p>${esc(meta)}</p>
<h2>Failed assertions (${failures.length})</h2>${fail}
<h2>Assertion summary</h2>${sum}
${rows}`;
  writeFileSync(path.join(outDir, 'index.html'), html);
}
