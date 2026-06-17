const assert = require('assert');
const fs = require('fs');
const Module = require('module');
const path = require('path');
const ts = require('typescript');

const helperPath = path.join(__dirname, 'graphic-novel-images.ts');
const source = fs.readFileSync(helperPath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2019,
  },
});
const helperModule = new Module(helperPath);
helperModule._compile(compiled.outputText, helperPath);

const { panelImageUrl } = helperModule.exports;

assert.strictEqual(
  panelImageUrl({ image_url: ' /media/graphic-novel/scenes/1/panel.png ' }),
  '/media/graphic-novel/scenes/1/panel.png',
);
assert.strictEqual(
  panelImageUrl({ image_url: 'data:image/png;base64,abc123' }),
  'data:image/png;base64,abc123',
);
assert.strictEqual(
  panelImageUrl({ image_url: '', image_payload: { url: 'https://cdn.example.test/panel.webp' } }),
  'https://cdn.example.test/panel.webp',
);
assert.strictEqual(panelImageUrl({ image_payload: { url: null } }), '');
assert.strictEqual(panelImageUrl(null), '');

console.log('graphic-novel-images helper tests passed');
