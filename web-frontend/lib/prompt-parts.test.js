// node --test lib/prompt-parts.test.js
//
// Owner, 2026-11-13: the situation and the instruction are prose; only the quoted line
// is set as speech. The parser cuts at the first quoted line and gives up (null) when
// there is none, so the screen falls back to the single headline.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.join(__dirname, '..', 'node_modules/sucrase/register/ts'));
const { promptParts } = require('./prompt-parts.ts');

test('the owner’s prompt: situation, the quoted line, the instruction', () => {
  assert.deepEqual(
    promptParts('À la gare, ton amie te dit : « Le train part dans dix minutes ! » Réponds-lui en disant ce que tu dois faire.'),
    {
      situation: 'À la gare, ton amie te dit :',
      quote: 'Le train part dans dix minutes !',
      instruction: 'Réponds-lui en disant ce que tu dois faire.',
    },
  );
});

test('German and English quotes cut the same way', () => {
  assert.equal(promptParts('Am Bahnhof sagt deine Freundin: „Der Zug fährt gleich ab!“ Antworte ihr.').quote, 'Der Zug fährt gleich ab!');
  assert.equal(promptParts('Your friend says: “The train leaves in ten minutes!” Answer her.').instruction, 'Answer her.');
  assert.equal(promptParts('Lila asks: "Tu viens ce soir ?"').situation, 'Lila asks:');
});

test('no quoted line keeps the single headline', () => {
  assert.equal(promptParts('Dis ce que tu fais ce week-end.'), null);
  assert.equal(promptParts('« Le train part dans dix minutes ! »'), null);
  assert.equal(promptParts('Utilise le mot « gare » dans ta phrase.'), null);
  assert.equal(promptParts(''), null);
  assert.equal(promptParts(null), null);
});
