// node --test components/revue/rubriques/rubriques.test.js
//
// «Le titre» and «L'intox express» (WIRE §11, 2026-11-20), the client:
//
//   1. the model: the shown step never ahead of the server's, the trap's taps, the A1
//      headline as the server builds it, the quote's settling words lit, the score;
//   2. the wire: real views (fixtures/rubriques-sessions.json, dumped from the backend's
//      loops) parsed; nothing says which headline is honest or which statement is false
//      before it is resolved; act bodies in snake_case through ONE route;
//   3. the player rendered from those views at A1 (en), A2 (de) and B1 (fr chrome): one
//      chrome language, at most two buttons in a foot, no solution before the retry, the
//      quote with its source, «La page».

const assert = require('node:assert/strict');
const { test } = require('node:test');

const setup = require('../revue-test-setup');

const { h, render, fixture } = setup;
const visibleText = (html) => setup.visibleText(html.replace(/<style[\s\S]*?<\/style>/g, ' '));

const types = require('../../../lib/revue-types.ts');
const rtypes = require('../../../lib/revue-rubriques-types.ts');
const { createRevueClient, parseRubriqueResult } = require('../../../lib/revue-api.ts');
const model = require('./rubriques-model.ts');
const { rubriqueCopy } = require('./rubriques-copy.ts');
const { RvRubrique } = require('../index.ts');

const SESSIONS = fixture('rubriques-sessions');
const session = (name) => types.parseSessionView(SESSIONS[name]);
const screen = (name) => render(h(RvRubrique, { client: {}, session: session(name), onExit: () => {}, onReleve: () => {} }));

function footButtons(html) {
  const at = html.lastIndexOf('class="rv-foot');
  if (at < 0) return 0;
  return (html.slice(at).match(/<button/g) || []).length;
}

// ---------------------------------------------------------------------------
// 1. The model
// ---------------------------------------------------------------------------

test('the shown step is never ahead of the server, and the last screen holds «Voir la page»', () => {
  const titre = { step: 'trap', steps: ['read', 'three', 'trap', 'build', 'page'] };
  assert.equal(model.openingStep(titre, false), 'trap');
  assert.equal(model.openingStep({ ...titre, step: 'page' }, false), 'build');
  assert.equal(model.openingStep(titre, true), 'page');
  assert.equal(model.clampStep(titre, 'build', false), 'trap');
  assert.equal(model.clampStep(titre, 'three', false), 'three');
  const intox = { step: 'page', steps: ['read', 'round', 'fix', 'page'] };
  assert.equal(model.openingStep(intox, false), 'fix');
  assert.equal(model.nextStep(intox, 'round'), 'fix');
});

test('the trap toggles taps; the A1 headline builds as the server builds it', () => {
  assert.deepEqual(model.toggle([], 4), [4]);
  assert.deepEqual(model.toggle([6, 4], 5), [4, 5, 6]);
  assert.deepEqual(model.toggle([4, 5], 4), [5]);
  assert.equal(model.a1Headline('La Fête de la musique', 'est gratuite'), 'La Fête de la musique est gratuite');
  assert.equal(model.a1Headline('La fête', null), '');
  assert.ok(model.saysTooMuch('La fête plaît à TOUT le monde', 'tout le monde'));
  assert.ok(!model.saysTooMuch('La fête plaît à beaucoup de monde', 'tout le monde'));
});

test('a quote lights the words that settle it, and lights nothing when they are not in it', () => {
  const lit = model.settledSegments('la première Fête est lancée le 21 juin 1982', 'le 21 juin 1982');
  assert.deepEqual(lit.filter((s) => s.wrong).map((s) => s.text), ['le 21 juin 1982']);
  assert.ok(model.settledSegments('Le résultat dépasse toutes les espérances.', '').every((s) => !s.wrong));
  assert.equal(model.scoreText(rubriqueCopy('fr'), { round: { score: 3, total: 5 } }), '3 sur 5');
  assert.equal(model.scoreText(rubriqueCopy('de'), { round: { score: 3, total: 5 } }), '3 von 5');
  const round = { round: { current: 'b', cards: [{ key: 'a', answer: 'vrai' }, { key: 'b', answer: null }] } };
  assert.equal(model.lastAnswered(round), 'a', 'a resume shows the last verdict first');
  assert.equal(model.shownCard(round, null).key, 'b', '«Phrase suivante» shows the current one');
});

// ---------------------------------------------------------------------------
// 2. The wire
// ---------------------------------------------------------------------------

test('a titre session parses, and nothing says which headline is honest before it is resolved', () => {
  const s = session('titre_a1_three');
  assert.equal(s.mode, 'titre');
  assert.equal(s.intox, null);
  assert.deepEqual(s.titre.steps, ['read', 'three', 'trap', 'build', 'page']);
  assert.equal(s.titre.three.headlines.length, 3);
  assert.ok(s.titre.three.headlines.every((h) => h.role === null && h.why === null));
  assert.equal(s.titre.three.solution, null);
  assert.equal(s.titre.trap, null);
  const wrong = session('titre_a1_three_wrong').titre.three;
  const picked = wrong.headlines.filter((h) => h.role);
  assert.equal(picked.length, 1);
  assert.equal(picked[0].role, 'off');
  assert.ok(picked[0].why.tr && picked[0].claim.id);
  assert.equal(wrong.solution, null);
  assert.ok(!JSON.stringify(SESSIONS.titre_a1_three).includes('honest'), 'the raw view says nothing either');
  const page = session('titre_a1_page');
  assert.equal(page.closing.titrePage.headlineFr, 'La Fête de la musique est gratuite');
  assert.equal(page.closing.filPage, null);
  assert.equal(page.artifact.kind, 'titre');
});

test('an intox session parses, and a statement says nothing past its text before it is answered', () => {
  const s = session('intox_a1_round');
  assert.equal(s.mode, 'intox');
  assert.deepEqual(s.intox.steps, ['read', 'round', 'fix', 'page']);
  assert.equal(s.intox.round.cards.length, 5);
  assert.ok(s.intox.round.cards.every((c) => c.true === null && c.quote === null && c.wrongFr === null));
  assert.equal(s.intox.round.current, 'a');
  const miss = session('intox_a1_round_miss').intox.round.cards[0];
  assert.equal(miss.correct, false);
  assert.ok(miss.quote && miss.quote.sourceName && miss.why.tr);
  const fix = session('intox_a1_fix_miss').intox.fix;
  assert.equal(fix.input, 'pick');
  assert.equal(fix.items[0].tries, 1);
  assert.equal(fix.items[0].rightFr, null, 'no solution before the retry');
  const page = session('intox_a1_page');
  assert.equal(page.closing.intoxPage.lines.length, 5);
  assert.equal(page.closing.intoxPage.score, 4);
  assert.equal(page.artifact.kind, 'intox');
});

test('acts go out in snake_case through one route, and a refusal comes back with its code', async () => {
  assert.deepEqual(rtypes.rubriqueBodyWire({ act: 'trap', words: [4, 5] }), { act: 'trap', words: [4, 5] });
  assert.deepEqual(rtypes.rubriqueBodyWire({ act: 'answer', key: 'a', value: 'faux' }), { act: 'answer', key: 'a', value: 'faux' });
  assert.deepEqual(rtypes.rubriqueBodyWire({ act: 'build_fix', text: 'x', mode: 'voice' }), { act: 'build_fix', text: 'x', mode: 'voice' });
  const result = parseRubriqueResult({ session: SESSIONS.titre_a2_build, error: { code: 'says_too_much' } });
  assert.deepEqual(result.error, { code: 'says_too_much', key: null, count: null });
  assert.ok(types.RV_MADE_KINDS.includes('titre') && types.RV_MADE_KINDS.includes('intox'));
  const posted = [];
  const client = createRevueClient({
    get: async () => ({ data: {} }),
    post: async (url, body) => {
      posted.push([url, body]);
      return { data: { session: SESSIONS.intox_a1_round, error: null } };
    },
  });
  await client.rubrique('abc', { act: 'answer', key: 'a', value: 'vrai' });
  assert.match(posted[0][0], /\/revue\/sessions\/abc\/rubrique$/);
  assert.equal(types.parseRevueError(409, { detail: { code: 'revue_intox_out_of_order' } }).code, 'revue_intox_out_of_order');
});

// ---------------------------------------------------------------------------
// 3. The player
// ---------------------------------------------------------------------------

const GERMAN_CHROME = /\b(Weiter|Prüfen|Übersetzen|Meine Schlagzeile senden)\b/;
const ENGLISH_CHROME = /\b(Continue|Check|Translate|Send my headline|Reread the article)\b/;

test('«Le titre» A1 (en): Gus proposes three, a wrong pick says why with its claim, never the solution', () => {
  let html = screen('titre_a1_read');
  assert.match(visibleText(html), /Aux titres/);
  assert.ok(footButtons(html) <= 2);

  html = screen('titre_a1_three');
  let text = visibleText(html);
  assert.match(text, /Gus a encore trois idées de titres/);
  assert.match(text, /suggests three headlines/);
  assert.match(text, /Pick the honest headline/);
  assert.match(text, /Try 1 of 2/);
  assert.doesNotMatch(text, /Here is the honest headline|Honest/);
  assert.doesNotMatch(text, GERMAN_CHROME);
  assert.ok(footButtons(html) <= 2);

  html = screen('titre_a1_three_wrong');
  text = visibleText(html);
  assert.match(text, /Not this one\./);
  assert.match(text, /True, but this headline is about the day/);
  assert.match(text, /Misses the news/);
  assert.match(text, /21 juin 1982/, 'the claim that settles it');
  assert.match(text, /Try 2 of 2/);
  assert.doesNotMatch(text, /Here is the honest headline|That's the honest headline/);
});

test('«Le titre» A1 (en): the trap names the true words after a miss, then the tiles build the headline', () => {
  let html = screen('titre_a1_trap');
  let text = visibleText(html);
  assert.match(text, /Tap the word or words that say too much/);
  assert.equal((html.match(/class="rb-trap__w"/g) || []).length, 7);
  html = screen('titre_a1_trap_miss');
  text = visibleText(html);
  assert.match(text, /Not these words: “fête”\./);
  assert.doesNotMatch(text, /These are the words that say too much/);
  assert.doesNotMatch(html, /data-wrong/, 'no solution before the retry');

  html = screen('titre_a1_build');
  text = visibleText(html);
  assert.match(text, /The subject/);
  assert.match(text, /La Fête de la musique/);
  assert.match(text, /Send my headline/);
  assert.ok(footButtons(html) <= 2);

  html = screen('titre_a1_page');
  text = visibleText(html);
  // «La belle édition»: the kicker says the headline is the learner's; the sources are a short list.
  assert.match(text, /Your headline/);
  assert.match(text, /La Fête de la musique est gratuite/);
  assert.match(text, /Romy Tremblay, avec toi d'après Ministère de la Culture/);
  assert.ok(footButtons(html) <= 2);
});

test('«Le titre» A2 (de): the frame without the words that said too much, Romy marks without the answer', () => {
  let html = screen('titre_a2_build');
  let text = visibleText(html);
  assert.match(text, /Beende die Schlagzeile/);
  assert.match(text, /Ohne „tout le monde“/);
  assert.match(text, /La Fête de la musique…/);
  assert.doesNotMatch(text, ENGLISH_CHROME);

  html = screen('titre_a2_marked');
  text = visibleText(html);
  assert.match(text, /Presque/);
  assert.match(html, /<mark class="ct-mark" data-kind="accord">/);
  assert.doesNotMatch(text, /les gens sont contents/, 'no solution before the retry');
  assert.ok(footButtons(html) <= 2);
});

test('«Le titre» B1: the chrome is French from B1', () => {
  const text = visibleText(screen('titre_b1_build'));
  assert.match(text, /Écris ton titre : 12 mots au plus/);
  assert.match(text, /Sans « tout le monde »/);
  assert.doesNotMatch(text, ENGLISH_CHROME);
});

test('«L’intox express» A1 (en): one statement at a time, two big buttons, the story one tap away', () => {
  let html = screen('intox_a1_round');
  let text = visibleText(html);
  assert.match(text, /Cinq phrases sur l’article/);
  assert.match(text, /0 of 5/);
  assert.match(text, /Reread the article/);
  assert.match(text, /1 \/ 5/);
  assert.equal((html.match(/class="ct-vote rb-vote"/g) || []).length, 2);
  assert.match(text, /Vrai/);
  assert.match(text, /Faux/);
  assert.doesNotMatch(text, /It's false|It's true/);
  assert.equal(footButtons(html), 2);

  html = screen('intox_a1_round_miss');
  text = visibleText(html);
  assert.match(text, /Not quite\./);
  assert.match(html, /class="rb-quote__lit"/);
  assert.match(text, /Next statement/);
  assert.ok(footButtons(html) <= 2);
});

test('«L’intox express» A1 (en): the corrections pick, a miss sends back to the quote, then «La page»', () => {
  let html = screen('intox_a1_fix');
  let text = visibleText(html);
  assert.match(text, /Make it true: pick the right words/);
  assert.equal((html.match(/class="ct-opt"/g) || []).length, 4);
  assert.match(html, /class="ct-strike"/);
  assert.equal(footButtons(html), 0, '«Voir la page» once both are settled');

  html = screen('intox_a1_fix_miss');
  text = visibleText(html);
  assert.match(text, /Not yet: read the quote again\. Try 2 of 2/);
  assert.doesNotMatch(text, /The right answer/);

  html = screen('intox_a1_page');
  text = visibleText(html);
  assert.match(text, /L'intox express de Romy|L’intox express de Romy/);
  assert.match(text, /4 sur 5/);
  assert.doesNotMatch(text, /14 juillet a lieu|Selon les voisins, la fête est un succès\./);
  assert.ok(footButtons(html) <= 2);
});

test('«L’intox express» B1: the chrome is French, the statements are rewritten', () => {
  const html = screen('intox_b1_fix');
  const text = visibleText(html);
  assert.match(text, /Réécris la phrase pour qu’elle soit vraie/);
  assert.equal((html.match(/class="ct-opt"/g) || []).length, 0);
  assert.doesNotMatch(text, ENGLISH_CHROME);
});

// Follow-up (integration): «À toi» uses «Le pourquoi»'s explained marks as the counter and
// «Le fil» do — each mark a button opening its rule in the mother tongue, never the answer;
// the settled headline with its notes.
test('«Le titre» A2 (de) with «Le pourquoi»: the marks open their rule, the settled headline carries its notes', () => {
  const raw = JSON.parse(JSON.stringify(SESSIONS.titre_a2_marked));
  const why = 'Im Französischen richten sich Artikel und Adjektiv in der Zahl nach dem Nomen.';
  raw.titre.build.marks = raw.titre.build.marks.map((mark) => ({ ...mark, why }));
  let html = render(h(RvRubrique, { client: {}, session: types.parseSessionView(raw), onExit: () => {} }));
  assert.equal((html.match(/class="ct-mark ct-mark--why"/g) || []).length, 2, 'each mark is a button');
  assert.doesNotMatch(visibleText(html), /les gens|contents/, 'no solution before the retry');

  const settled = JSON.parse(JSON.stringify(SESSIONS.titre_a2_marked));
  Object.assign(settled.titre.build, {
    proof: 'fixed',
    marks: [],
    draft_fr: 'La Fête de la musique est gratuite et les gens sont contents',
    printed_fr: 'La Fête de la musique est gratuite et les gens sont contents',
    tries: 1,
    notes: [{ span_fr: 'le', kind: 'accord', why: `${why.slice(0, -1)}: «les gens».`, example_fr: null, rule_id: 'plural_s' }],
  });
  html = render(h(RvRubrique, { client: {}, session: types.parseSessionView(settled), onExit: () => {} }));
  assert.match(html, /class="ct-notes"/);
  assert.match(visibleText(html), /Nomen: «les gens»/);
});

// 22 Nov (a real run): the edit call came back empty, the learner's headline printed unread
// under «tel que tu l'as écrit» and Romy closed on «… et il dit vrai». An unread proof now
// says so in the learner's language, and her closing line for it never says it is right.
const AS_WRITTEN_CLOSE_FR = 'Merci ! Ton titre est en une, tel que tu l’as écrit : je n’ai pas pu le relire cette fois.';

test('«Le titre»: a headline Romy could not read says so, and her thanks never say it is right', () => {
  const { COMPTOIR_LINES, unreadLine, closeLineIn } = require('../comptoir/comptoir-copy.ts');
  for (const language of ['fr', 'en', 'de']) assert.ok(COMPTOIR_LINES.proof_unread[language], language);
  assert.equal(unreadLine('as_written', false), COMPTOIR_LINES.proof_unread);
  assert.equal(unreadLine('as_written', true), null, 'A1 tiles are never checked');
  assert.equal(unreadLine('clean', false), null);
  assert.equal(
    closeLineIn(AS_WRITTEN_CLOSE_FR, 'de').tr,
    'Danke! Deine Schlagzeile steht auf der Titelseite, so wie du sie geschrieben hast: Ich konnte sie diesmal nicht korrekturlesen.',
  );
  assert.equal(closeLineIn(AS_WRITTEN_CLOSE_FR, 'fr').tr, null);
  assert.equal(closeLineIn('Une ligne inconnue.', 'en').tr, null);

  const raw = JSON.parse(JSON.stringify(SESSIONS.titre_a2_marked));
  Object.assign(raw.titre.build, { proof: 'as_written', marks: [], printed_fr: raw.titre.build.draft_fr });
  const text = visibleText(render(h(RvRubrique, { client: {}, session: types.parseSessionView(raw), onExit: () => {} })));
  assert.match(text, /je n’ai pas pu te relire cette fois/);
  assert.match(text, /tel que tu l’as écrit/);

  const page = JSON.parse(JSON.stringify(SESSIONS.titre_a1_page));
  page.closing.romy_line_fr = AS_WRITTEN_CLOSE_FR;
  page.status = 'active'; // the close as the learner meets it (a session reopened later shows the page alone)
  const html = render(h(RvRubrique, { client: {}, session: types.parseSessionView(page), onExit: () => {} }));
  const shown = visibleText(html);
  assert.match(shown, /je n’ai pas pu le relire cette fois/);
  assert.doesNotMatch(shown, /il dit vrai/);
});

// Follow-up (integration): «Lire» shows the story's other pictures as the other assignments do.
test('«Le titre» and «L’intox express»: «Lire» shows the story’s other pictures, each with its credit', () => {
  for (const name of ['titre_a1_read', 'intox_a1_round']) {
    const raw = JSON.parse(JSON.stringify(SESSIONS[name]));
    const mode = raw.mode;
    raw[mode].step = 'read';
    const plate = '/media/graphic-novel/revue-stories/evergreen-fete-de-la-musique-0123456789abcdef.webp';
    raw.stage.plate_url = plate;
    raw.stage.plate_kind = 'story';
    raw.stage.pictures = [
      { kind: 'illustration', url: plate, alt_fr: '', credit_fr: 'Illustration · Le Papier' },
      {
        kind: 'photo', url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Fete.jpg/1280px-Fete.jpg', alt_fr: 'Une scène', caption_fr: 'Une scène',
        credit_fr: 'Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons', licence: 'CC BY-SA 4.0',
        licence_url: 'https://creativecommons.org/licenses/by-sa/4.0', source_url: 'https://commons.wikimedia.org/wiki/File:Fete.jpg',
      },
    ];
    const html = render(h(RvRubrique, { client: {}, session: types.parseSessionView(raw), onExit: () => {} }));
    assert.match(html, /rv-gallery/, name);
    assert.equal((html.match(/rv-gallery__item/g) || []).length, 1, `${name}: the plate is not repeated`);
    assert.match(visibleText(html), /Photo · Camille Exemple · CC BY-SA 4\.0 · Wikimedia Commons/);
    assert.ok(html.indexOf('ct-pic') < html.indexOf('rv-lead') && html.indexOf('rv-lead') < html.indexOf('class="rv-gallery"'), `${name}: the lead before the strip`);
  }
  assert.doesNotMatch(screen('titre_a1_read'), /rv-gallery/, 'no strip without other pictures');
});

// Follow-up (integration, as «Le fil» 4788a650): from B1 the chrome is French but every
// explanation is in the mother tongue; below B1 both are the mother tongue.
test('from B1 the reasons are in the mother tongue while the chrome stays French', () => {
  const b1 = (name, edit = () => {}) => {
    const raw = JSON.parse(JSON.stringify(SESSIONS[name]));
    Object.assign(raw.plan, { ui_language: 'fr', gloss_language: 'en' });
    edit(raw);
    return visibleText(render(h(RvRubrique, { client: {}, session: types.parseSessionView(raw), onExit: () => {} })));
  };
  let text = b1('titre_a1_three_wrong');
  assert.match(text, /Not this one\./);
  assert.doesNotMatch(text, /Pas celui-là/);
  assert.match(text, /Vérifier/, 'the chrome stays French');
  text = b1('titre_a1_trap_miss');
  assert.match(text, /Not these words: “fête”\./);
  assert.doesNotMatch(text, /Pas ces mots-là/);
  text = b1('titre_a1_trap_miss', (raw) => {
    const trap = raw.titre.trap;
    Object.assign(trap, { resolved: true, correct: true, solution: [4, 5, 6], fine: [], why: { fr: 'Pas tout le monde.', tr: 'Not everyone.' } });
  });
  assert.match(text, /Not everyone\./);
  for (const code of ['says_too_much', 'number_not_in_claims', 'nothing_changed']) {
    assert.equal(model.refusalCopy(code, rubriqueCopy('fr'), rubriqueCopy('en')), rubriqueCopy('en'), `${code} is a reason`);
  }
  for (const code of ['too_short', 'too_long', 'pick_words', 'pick_tiles']) {
    assert.equal(model.refusalCopy(code, rubriqueCopy('fr'), rubriqueCopy('en')), rubriqueCopy('fr'), `${code} is an instruction`);
  }
});

// Seen in a browser (2026-11-20, 375 × 812, A1 de / A2 de / B1 en): what the words said.
test('the verdicts and reasons say what they mean', () => {
  // «Nicht ganz. Das stimmt.» read as «not quite — that's right»: the verdict names the statement.
  for (const lang of ['fr', 'en', 'de']) {
    const copy = rubriqueCopy(lang);
    assert.doesNotMatch(`${copy.verdict_wrong} ${copy.was_true}`, /Das stimmt\.|C'est vrai\.|It's true\./, lang);
    assert.match(copy.was_true, /Satz|statement|phrase/, lang);
    assert.match(copy.was_false, /Satz|statement|phrase/, lang);
    // A wrong pick of the off headline said «says something the article doesn't: True, but…».
    assert.doesNotMatch(copy.three_wrong, /:$/, `${lang}: the lead-in claims nothing about the headline`);
    // After a miss on «nuit», «the article does say these: nuit» was false: the article never says «nuit».
    assert.doesNotMatch(copy.trap_fine, /article/i, lang);
    // «Take those words out» named none: the refusal names them.
    assert.match(copy.errors.says_too_much, /\{avoid\}/, lang);
  }
  assert.match(model.errorText(rubriqueCopy('de'), { code: 'says_too_much', key: null, count: null }, 'tout le monde'), /„tout le monde“/);
  let html = screen('intox_a1_round_miss');
  assert.match(visibleText(html), /Not quite\. The statement is true\./);
  const raw = JSON.parse(JSON.stringify(SESSIONS.titre_a1_three_wrong));
  html = render(h(RvRubrique, { client: {}, session: types.parseSessionView(raw), onExit: () => {} }));
  assert.match(html, /<p class="ct-why"[^>]*>Not this one\.<\/p>/, 'the lead-in is its own line');
});

// Seen at 375 px: «à» and «le» in «Le piège» were 35 and 37 px wide.
test('the trap words are at least 44 px both ways', () => {
  const css = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', '..', '..', 'styles', 'revue-rubriques.css'), 'utf8');
  const rule = css.match(/\.rb-trap__w \{([^}]*)\}/);
  assert.ok(rule, 'the rule exists');
  assert.match(rule[1], /min-width: var\(--av2-tap\);/);
  assert.match(rule[1], /min-height: var\(--av2-tap\);/);
});

// Seen in a browser: «La page» reprinted the story's lead with no source.
test('«La page» names its sources under both assignments', () => {
  for (const name of ['titre_a1_page', 'intox_a1_page']) {
    const raw = JSON.parse(JSON.stringify(SESSIONS[name]));
    raw.closing.dispatch.byline_fr = "Romy Tremblay, avec toi · d'après Ministère de la Culture et Wikipédia";
    const text = visibleText(render(h(RvRubrique, { client: {}, session: types.parseSessionView(raw), onExit: () => {} })));
    assert.match(text, /d'après Ministère de la Culture et Wikipédia/, name);
  }
});

// Seen at 375 px (B1 en): after a miss the field was empty; the learner retyped the whole sentence.
test('«Corrige» B1: after a miss the field keeps the learner\'s sentence to edit', () => {
  const raw = JSON.parse(JSON.stringify(SESSIONS.intox_b1_fix));
  const item = raw.intox.fix.items[0];
  Object.assign(item, { tries: 1, attempts: ['La fête a lieu le 14 juin.'], resolved: false });
  const html = render(h(RvRubrique, { client: {}, session: types.parseSessionView(raw), onExit: () => {} }));
  assert.match(html, /<textarea[^>]*>La fête a lieu le 14 juin\.<\/textarea>/);
});

// Seen at 375 × 812 (A1 de, A2 de, B1 en): the player never scrolled — a new screen opened
// where the last one was (Romy's line cut under the head), and a wrong pick's why or the
// honest headline's verdict landed under the foot. It now scrolls as the counter does.
test('every act moves the progress the player scrolls on, and the newest part comes into the band', () => {
  const keys = ['titre_a1_three', 'titre_a1_three_wrong', 'titre_a1_trap', 'titre_a1_trap_miss', 'titre_a1_build', 'titre_a2_marked',
    'intox_a1_round', 'intox_a1_round_miss', 'intox_a1_fix', 'intox_a1_fix_miss'].map((name) => model.rubriqueProgress(session(name)));
  assert.equal(new Set(keys).size, keys.length, 'each state its own key');
  const scroll = require('../comptoir/scroll.ts');
  assert.equal(scroll.anchorDelta(900, 1000, 70, 740, 'nearest'), 260, 'a why under the foot comes up');
  assert.equal(scroll.anchorDelta(200, 300, 70, 740, 'nearest'), 0, 'already in view: no scroll');
  assert.equal(scroll.anchorDelta(500, 1500, 70, 740, 'nearest'), 430, 'a tall part stops with its top under the head');
  assert.equal(scroll.anchorDelta(50, 100, 70, 740, 'start'), -20);
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, 'RvRubrique.tsx'), 'utf8');
  assert.match(src, /bringNewestIntoView\(/, 'the player brings the newest part into view');
  assert.match(src, /scrollTo\(\{ top: 0 \}\)/, 'a new screen starts at its top');
});
