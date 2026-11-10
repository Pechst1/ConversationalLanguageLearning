// S4 stage 4 — «Aide», the Help place in Réglages.
//
// A short FAQ from a copy table (en, de, fr, tu/du), the existing feedback
// sheet, and the legal contact address. The feedback sheet records whether the
// learner wants a reply; nothing sends one.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');
const { HELP_COPY, HELP_QUESTION_IDS, helpCopy } = require('./help-copy.ts');

const WEB = path.join(__dirname, '..');
const read = (relative) => fs.readFileSync(path.join(WEB, relative), 'utf8');

const flat = (value, prefix = '') =>
  typeof value === 'string'
    ? [[prefix, value]]
    : Object.entries(value).flatMap(([k, v]) => flat(v, prefix ? `${prefix}.${k}` : k));

test('every language answers every question, in the same order', () => {
  for (const language of ['en', 'de', 'fr']) {
    const copy = HELP_COPY[language];
    assert.deepEqual(copy.faq.map((item) => item.id), [...HELP_QUESTION_IDS], language);
    for (const [key, value] of flat(copy)) assert.ok(value.trim(), `${language}.${key} is empty`);
  }
  assert.equal(helpCopy('de-AT').headline, 'Hilfe');
  assert.equal(helpCopy('pt').headline, HELP_COPY.en.headline, 'an unknown language falls back to English');
});

test('the learner is addressed with tu and du, and German is not French', () => {
  const fr = JSON.stringify(HELP_COPY.fr);
  const de = JSON.stringify(HELP_COPY.de);
  assert.doesNotMatch(fr, /\b(vous|votre|vos)\b|\b(choisissez|saisissez|envoyez|écrivez)\b/i);
  assert.doesNotMatch(de, /\b(Sie|Ihr|Ihre|Ihnen)\b/);
  for (const [index, item] of HELP_COPY.fr.faq.entries()) {
    assert.notEqual(HELP_COPY.de.faq[index].a, item.a, item.id);
    assert.notEqual(HELP_COPY.en.faq[index].a, item.a, item.id);
  }
});

test('the FAQ quotes the labels the app really shows', () => {
  const auth = read('lib/auth-copy.ts');
  const settings = read('lib/settings-copy.ts');
  const feedback = read('components/feedback/feedback-copy.ts');
  const quoted = (text) => [...text.matchAll(/«\s?([^»]+?)\s?»/g)].map((match) => match[1]);
  for (const language of ['en', 'de', 'fr']) {
    for (const item of HELP_COPY[language].faq) {
      for (const label of quoted(item.a)) {
        assert.ok(
          auth.includes(`'${label}'`) || settings.includes(`'${label}'`) || feedback.includes(`'${label}'`),
          `${language}/${item.id} quotes «${label}», which no copy table shows`,
        );
      }
    }
  }
});

test('the Help page is a child of Réglages with the feedback sheet and the contact address', () => {
  const page = read('pages/help.tsx');
  assert.match(page, /helpCopy\(language\)/);
  assert.match(page, /new Event\(FEEDBACK_OPEN_EVENT\)/, 'the same feedback sheet');
  assert.match(page, /mailto:\$\{LEGAL_CONTACT\}/, 'the legal contact address');
  assert.match(read('pages/settings.tsx'), /router\.push\('\/help'\)/);
  const places = read('lib/places.ts');
  assert.match(places, /route: '\/help',[\s\S]{0,120}kind: 'child',\s*parent: '\/settings'/);
  // JSX text between tags would be words outside the copy table.
  const source = page.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '').replace(/<style[\s\S]*<\/style>/, '');
  assert.doesNotMatch(source, /[^=]>\s*[A-Za-z][a-z]+\s+[a-z]+[^<{]*</, 'help.tsx prints words of its own');
});

test('the feedback sheet asks whether to answer and sends the wish', () => {
  const widget = read('components/feedback/FeedbackWidget.tsx');
  assert.match(widget, /wants_reply: wantsReply/);
  assert.match(widget, /aria-pressed=\{wantsReply\}/);
  assert.match(read('services/api.ts'), /wants_reply\?: boolean/);
  assert.doesNotMatch(widget, /sendReply|reply_sent|replyTo/, 'reply sending is not built');
});
