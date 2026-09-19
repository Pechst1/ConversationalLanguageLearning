const assert = require('node:assert/strict');
const fs = require('fs');
const Module = require('module');
const path = require('path');
const { test } = require('node:test');
const ts = require('typescript');

function load() {
  const helperPath = path.join(__dirname, 'media-url.ts');
  const source = fs.readFileSync(helperPath, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019 },
  });
  const helperModule = new Module(helperPath);
  helperModule._compile(compiled.outputText, helperPath);
  return helperModule.exports;
}

const { resolveMediaUrl, normalizeLegacySerialAsset } = load();

test('a stale .png serial asset from an old world-bible copy resolves to the .webp that exists', () => {
  assert.equal(
    resolveMediaUrl('/assets/serial/locations/le_mistral-booth.png'),
    '/assets/serial/locations/le_mistral-booth.webp',
  );
  assert.equal(
    normalizeLegacySerialAsset('assets/serial/characters/lila_bonnet/model-sheet.png'),
    'assets/serial/characters/lila_bonnet/model-sheet.webp',
  );
  assert.equal(
    resolveMediaUrl('/assets/serial/props/le_mistral_booth.PNG?v=2'),
    '/assets/serial/props/le_mistral_booth.webp?v=2',
  );
});

test('current .webp paths and everything outside the serial folder pass through untouched', () => {
  assert.equal(
    resolveMediaUrl('/assets/serial/locations/brocante.webp'),
    '/assets/serial/locations/brocante.webp',
  );
  assert.equal(resolveMediaUrl('/assets/other/thing.png'), '/assets/other/thing.png');
  assert.equal(resolveMediaUrl('https://cdn.example.test/serial/x.png'), 'https://cdn.example.test/serial/x.png');
  assert.equal(resolveMediaUrl('data:image/png;base64,abc'), 'data:image/png;base64,abc');
  assert.equal(resolveMediaUrl(''), null);
  assert.equal(resolveMediaUrl(null), null);
});

test('generated panels under /media keep resolving against the API origin', () => {
  const value = resolveMediaUrl('/media/graphic-novel/scenes/1/panel.webp');
  assert.ok(value.endsWith('/media/graphic-novel/scenes/1/panel.webp'));
});
