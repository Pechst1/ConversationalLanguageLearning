const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { transform } = require('sucrase');
const axios = require('axios');

function handler() {
  const filename = path.resolve(__dirname, '../pages/api/anki.ts');
  const compiled = new Module(filename, module);
  compiled.filename = filename;
  compiled.paths = module.paths;
  compiled._compile(transform(fs.readFileSync(filename, 'utf8'), {
    transforms: ['typescript', 'imports'],
  }).code, filename);
  return compiled.exports.default;
}

test('production Anki bridge returns 404 without contacting localhost', async () => {
  const previous = process.env.NODE_ENV;
  const original = axios.post;
  let calls = 0;
  axios.post = async () => { calls += 1; throw new Error('must not contact localhost'); };
  process.env.NODE_ENV = 'production';
  const res = { status(code) { this.code = code; return this; }, end() { this.ended = true; } };
  try {
    await handler()({ method: 'POST', body: { action: 'deleteDecks' } }, res);
    assert.equal(res.code, 404);
    assert.equal(res.ended, true);
    assert.equal(calls, 0);
  } finally {
    axios.post = original;
    if (previous === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previous;
  }
});

test('production rewrites never expose AnkiConnect', async () => {
  const previous = process.env.NODE_ENV;
  const configPath = require.resolve('../next.config.js');
  process.env.NODE_ENV = 'production';
  delete require.cache[configPath];
  try {
    const config = require(configPath);
    const rewrites = config.rewrites ? await config.rewrites() : [];
    assert.equal(rewrites.some((rewrite) => rewrite.source === '/anki-connect'), false);
    assert.equal(rewrites.some((rewrite) => rewrite.destination.includes(':8765')), false);
  } finally {
    delete require.cache[configPath];
    if (previous === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previous;
  }
});
