// node --test components/epreuve/forge-speaker-label.test.js
//
// #951 — La Forge's dialogue prompt printed «A classmate asks:», then two bare
// lines «Lila» and «tu», then «Tu as des frères ou des sœurs ?». The speaker's
// name and the register were two separate items above the quote, and a learner
// read «Lila / tu» as part of the question. The speaker is one label at the head
// of the quote; the register rides inside it and is never a line of its own.

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
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const Ep = require('./Epreuve.tsx');
const { promptParts } = require('@/lib/prompt-parts.ts');

const PROMPT = 'A classmate asks: « Tu as des frères ou des sœurs ? » Answer in one sentence.';
const decode = (s) => s.replace(/&#x27;/g, "'").replace(/&amp;/g, '&');

/** The children of an element, as top-level text runs: what a reader sees as separate lines. */
function topLevelTexts(html) {
  const texts = [];
  let depth = 0;
  let current = '';
  for (const part of html.split(/(<[^>]+>)/)) {
    if (!part) continue;
    if (part.startsWith('</')) {
      depth -= 1;
      if (depth === 0) {
        texts.push(current.trim());
        current = '';
      }
    } else if (part.startsWith('<')) {
      if (!part.endsWith('/>')) depth += 1;
    } else {
      current += part;
      if (depth === 0 && part.trim()) texts.push(part.trim());
    }
  }
  return texts.filter(Boolean);
}

test('the speaker is one label at the head of the quote, the register inside it', () => {
  const html = decode(
    renderToStaticMarkup(
      React.createElement(Ep.EpScenePrompt, {
        text: PROMPT,
        split: promptParts(PROMPT),
        lang: 'en',
        speaker: { name: 'Lila', register: 'tu' },
      }),
    ),
  );
  const who = /<figcaption[^>]*>([\s\S]*?)<\/figcaption>/.exec(html);
  assert.ok(who, 'the speaker sits in the speech figure, beside the quote');
  // One label: the figcaption holds one item, and it reads «Lila · tu».
  const items = topLevelTexts(who[1]);
  assert.deepEqual(items, ['Lila · tu']);
  assert.equal((html.match(/Lila/g) || []).length, 1, 'the speaker is named once');
  // «tu» is never an element of its own: every element that holds it holds the name too.
  for (const match of html.matchAll(/<(span|em|p|div)[^>]*>([^<]*)<\/\1>/g)) {
    assert.notEqual(match[2].trim(), 'tu', `a bare «tu»: ${match[0]}`);
  }
  assert.match(html, /<blockquote[^>]*>«\s?Tu as des frères ou des sœurs\s?\?\s?»<\/blockquote>/);
});

test('without a quote, the conversation byline is one label too', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  const at = page.indexOf('className="ep-character-byline"');
  const byline = page.slice(at, page.indexOf('</div>', at));
  assert.match(byline, /<span>\s*\{character\.name\}\s*<em lang="fr">\{` · \$\{String\(character\.register \|\| 'vous'\)\}`\}<\/em>\s*<\/span>/);
  assert.doesNotMatch(byline, /<\/span>\s*<em/);
});
