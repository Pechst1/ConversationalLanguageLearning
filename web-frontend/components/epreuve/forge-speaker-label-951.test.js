// node --test components/epreuve/forge-speaker-label-951.test.js
//
// #951 (live walk 20 Nov 2026), La Forge item 5/6: «A classmate asks:» was followed by
// two bare lines «Lila» and «tu», then «Tu as des frères ou des sœurs ?». The speaker's
// name and the register chip were laid out as separate flex items, so each read as its own
// line and a learner took «Lila / tu» for part of the question.
//
// Done when: a dialogue item with a speaker and a register shows the speaker once, as one
// label next to the quote, and the register is never a loose «tu» line of its own.

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
const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');

const PROMPT = 'A classmate asks: « Tu as des frères ou des sœurs ? » Answer in one full sentence.';
const strip = (html) => html.replace(/<[^>]+>/g, '').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');

// Every element of the render with the text it shows (tags stripped), innermost first.
function elements(html) {
  const out = [];
  const stack = [];
  const tag = /<(\/?)([a-z0-9]+)([^>]*?)(\/?)>/g;
  let m;
  while ((m = tag.exec(html))) {
    const [, closing, name, attrs, selfClosing] = m;
    if (selfClosing || ['img', 'br', 'input'].includes(name)) continue;
    if (!closing) {
      stack.push({ name, attrs, start: tag.lastIndex });
      continue;
    }
    const open = stack.pop();
    out.push({ name, attrs: open.attrs, text: strip(html.slice(open.start, m.index)).trim() });
  }
  return out;
}

function renderDialogue(register) {
  return renderToStaticMarkup(
    React.createElement(Ep.EpScenePrompt, {
      text: PROMPT,
      split: promptParts(PROMPT),
      lang: 'en',
      speaker: { name: 'Lila', register },
    }),
  );
}

test('#951 the register is never a loose line of its own under the speaker', () => {
  for (const register of ['tu', 'vous']) {
    const html = renderDialogue(register);
    const loose = elements(html).filter((el) => el.text === register);
    assert.deepEqual(
      loose.map((el) => `<${el.name}${el.attrs}>${el.text}`),
      [],
      `«${register}» is rendered as an element of its own, a bare line a learner reads as part of the question: ${html}`,
    );
  }
});

test('#951 the speaker is named once, as one label next to the quote', () => {
  const html = renderDialogue('tu');
  const text = strip(html);
  assert.equal(text.split('Lila').length - 1, 1, `the speaker is named exactly once: ${text}`);
  const figure = /<figure class="ep-speech">([\s\S]*)<\/figure>/.exec(html);
  assert.ok(figure, 'the quoted line is set as speech');
  const caption = /<figcaption[^>]*>([\s\S]*?)<\/figcaption>/.exec(figure[1]);
  assert.ok(caption, 'the speaker labels the speech figure, next to the quote');
  // The caption holds one label: the name and what the register means, read as one phrase.
  const labels = elements(caption[1]).filter((el) => /class="ep-speaker"/.test(el.attrs));
  assert.equal(labels.length, 1, `one speaker label in the caption: ${caption[1]}`);
  assert.match(labels[0].text, /^Lila · \S/, `the label reads «Lila · …» on one line: ${labels[0].text}`);
  assert.ok(figure[1].indexOf('</figcaption>') < figure[1].indexOf('<blockquote'), 'the label stands right before the quote');
});

test('#951 the register reads as a phrase in every chrome language', () => {
  const { speakerLabelNote } = require('./epreuve-copy.ts');
  const { epreuveCopy } = require('./epreuve-copy.ts');
  for (const lang of ['en', 'de', 'fr']) {
    const copy = epreuveCopy(lang);
    for (const register of ['tu', 'vous']) {
      const note = speakerLabelNote(copy, register);
      assert.ok(note && note.split(/\s+/).length >= 2, `${lang}/${register}: «${note}» says what the register means`);
    }
    assert.equal(speakerLabelNote(copy, ''), '', `${lang}: no register, no note`);
  }
});

test('#951 the conversation byline uses the same speaker label, not its own name and chip', () => {
  const ladder = PAGE.slice(PAGE.indexOf('function OutputLadderPanel('), PAGE.indexOf('function ProducePanel('));
  const byline = ladder.slice(ladder.indexOf('<div className="ep-character-byline"'), ladder.indexOf('</div>', ladder.indexOf('<div className="ep-character-byline"')));
  assert.doesNotMatch(byline, /<em lang="fr">\{String\(character\.register/, 'the byline does not set the register as a chip of its own');
  assert.match(byline, /<EpSpeakerLabel\b/, 'the byline reads the one speaker label');
});
