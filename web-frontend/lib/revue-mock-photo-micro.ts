/**
 * «La photo» and «Le micro» in the DEV-ONLY mock (`/revue?mock=1&photo=1` or `&micro=1`,
 * `lib/revue-mock.ts`, WIRE §12).
 *
 * The material of «La Fête de la musique» transcribed from
 * `app/services/revue/evergreen/photo/evergreen-fete-de-la-musique.json` and
 * `…/micro/evergreen-fete-de-la-musique.json`, and the learner's loops scripted with the replay
 * rules of `photo_loop.py` and `micro_loop.py` (two tries, nothing before it is earned, the
 * slips kept for «Relis tes questions»). The two pictures are neutral placeholders (data URIs,
 * nothing fetched) with Commons-shaped credits; the interview's matcher is a small port of
 * `micro.match` (the question word, then the content words). The shuffles are fixed: the mock is
 * a screen to look at, not a second implementation. Wire JSON in and out.
 */

import { marksWire, notesWire, proofread } from './revue-mock-comptoir';
import type { RubriqueContext } from './revue-mock-rubriques';

type Json = Record<string, any>;
type Lang = 'en' | 'de' | 'fr';
type Band = 'A1' | 'A2' | 'B1' | 'B2';
type T = { fr: string; en: string; de: string };

const t = (fr: string, en: string, de: string): T => ({ fr, en, de });
const bandKey = (band: Band) => (band === 'A1' ? 'a1' : band === 'A2' ? 'a2' : 'b1') as 'a1' | 'a2' | 'b1';
const tr = (text: T, language: Lang) => ({ fr: text.fr, tr: language === 'fr' ? null : text[language] });
const fold = (text: string) => text.normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[’`]/g, "'").toLowerCase();
const typography = (text: string) => text.replace(/\s*([?!;:])/g, ' $1').replace(/\s+/g, ' ').trim();
const wordCount = (text: string) => (text.match(/[A-Za-zÀ-ÖØ-öø-ÿŒœ\d]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*/g) || []).length;
const numbers = (text: string) => new Set(text.match(/\d+/g) || []);
const proofKey = (text: string) => {
  const flat = text.normalize('NFC').replace(/[’`]/g, "'").replace(/[^A-Za-zÀ-ÖØ-öø-ÿŒœ0-9']+/g, ' ').trim();
  return flat.charAt(0).toLowerCase() + flat.slice(1);
};
const read = (ctx: RubriqueContext) => ({ dateline_fr: ctx.datelineFr, lead: ctx.lead, sources: ctx.sources.slice(0, 1) });
const MAX_TRIES = 2;
const FIX_TRIES = 2;

// --- a proof trail (as rubrique_proof.Trail) -----------------------------------------

type Trail = { first: Json | null; fixes: Json[] };
function proofOf(trail: Trail) {
  if (!trail.first) return null;
  const latest = trail.fixes.length ? trail.fixes[trail.fixes.length - 1] : trail.first;
  const texts = trail.fixes.filter((fix) => fix.text_fr).map((fix) => String(fix.text_fr));
  const draft = texts.length ? texts[texts.length - 1] : String(trail.first.learner_fr);
  const proof = String(latest.proof);
  const target = String(latest.target_fr || '');
  const printed = proof === 'marked' ? null : proof === 'as_written' ? draft : target || draft;
  return { proof, draft, marks: proof === 'marked' ? (latest.marks as Json[]) : [], tries: texts.length, target, printed };
}
const roundsOf = (trail: Trail): Json[][] =>
  [trail.first, ...trail.fixes].filter((row): row is Json => Boolean(row) && row?.proof === 'marked' && Array.isArray(row?.marks)).map((row) => row.marks);
function proofWire(trail: Trail, ctx: RubriqueContext): Json {
  const proof = proofOf(trail);
  const out: Json = {
    draft_fr: proof ? proof.draft : null,
    proof: proof ? proof.proof : null,
    marks: proof ? marksWire(proof.marks, ctx.language, Boolean(ctx.pourquoi)) : [],
    tries: proof ? proof.tries : 0,
    max_tries: FIX_TRIES,
    printed_fr: proof ? proof.printed : null,
  };
  const notes = proof ? notesWire(roundsOf(trail), proof.proof, ctx.language, ctx.lead.fr, Boolean(ctx.pourquoi)) : [];
  if (notes.length) out.notes = notes;
  return out;
}
function edit(learner: string): { proof: string; target: string; marks: Json[] } {
  const out = proofread(learner);
  return { proof: out.marks.length ? 'marked' : 'clean', target: typography(out.target), marks: out.marks };
}
/** One fix of Romy's marks (as `rubrique_proof.fix_row`); returns a refusal or null. */
function fixInto(trail: Trail, body: Json, check: (text: string) => Json | null, shape: (text: string) => string, fail: () => Error): Json | null {
  const proof = proofOf(trail);
  if (!proof) throw fail();
  if (proof.proof !== 'marked') return null;
  if (body.value === 'romy') {
    if (proof.tries < 1) throw fail();
    trail.fixes.push({ by: 'romy', proof: 'corrected', target_fr: proof.target });
    return null;
  }
  const learner = shape(String(body.text || ''));
  const problem = check(learner);
  if (problem) return problem;
  if (proofKey(learner) === proofKey(proof.draft)) return { code: 'nothing_changed' };
  const tries = proof.tries + 1;
  if (proofKey(learner) === proofKey(proof.target)) {
    trail.fixes.push({ text_fr: learner, typed_fr: learner, proof: 'fixed', target_fr: proof.target });
    return null;
  }
  const again = edit(learner);
  const next = again.proof === 'clean' ? 'fixed' : tries >= FIX_TRIES ? 'corrected' : 'marked';
  trail.fixes.push({ text_fr: learner, typed_fr: learner, proof: next, target_fr: again.target, marks: next === 'marked' ? again.marks : [] });
  return null;
}

// --- «La photo»: the material ------------------------------------------------------

const placeholder = (label: string, sky: string, ground: string, shape: string) =>
  `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 213" role="img" aria-label="${label}"><rect width="320" height="213" fill="${sky}"/><rect y="150" width="320" height="63" fill="${ground}"/>${shape}</svg>`,
  )}`;
const PICTURES = [
  {
    ref: 'photo-1',
    kind: 'photo',
    url: placeholder('Photo (placeholder)', '#B7BCC4', '#6F757E', '<rect x="30" y="60" width="70" height="90" fill="#F1ECE1" opacity=".5"/><rect x="120" y="40" width="80" height="110" fill="#F1ECE1" opacity=".4"/><rect x="220" y="70" width="70" height="80" fill="#F1ECE1" opacity=".5"/>'),
    credit_fr: 'Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons',
    licence: 'CC BY-SA 4.0',
    licence_url: 'https://creativecommons.org/licenses/by-sa/4.0/',
    source_url: 'https://commons.wikimedia.org/wiki/File:Example.jpg',
    width: 1280,
    height: 853,
    seen: [t('Paris', 'Paris', 'Paris')],
  },
  {
    ref: 'photo-2',
    kind: 'photo',
    url: placeholder('Photo (placeholder)', '#C9C1B1', '#8C8475', '<ellipse cx="160" cy="130" rx="46" ry="52" fill="#F1ECE1" opacity=".55"/><rect x="152" y="20" width="16" height="80" fill="#F1ECE1" opacity=".55"/>'),
    credit_fr: 'Photo · Dominique Exemple · CC0 · Wikimedia Commons',
    licence: 'CC0',
    licence_url: 'https://creativecommons.org/publicdomain/zero/1.0/',
    source_url: 'https://commons.wikimedia.org/wiki/File:Example_2.jpg',
    width: 1280,
    height: 853,
    seen: [t('une guitare', 'a guitar', 'eine Gitarre'), t('une guitare acoustique', 'an acoustic guitar', 'eine Akustikgitarre')],
  },
];
const LEAD = 'photo-2';
type ByBand = { a1: T; a2: T; b1: T };
type Caption = { role: 'right' | 'wrong' | 'other'; text: ByBand; why: T | null; wrong_fr?: string; right_fr?: string; distractor_fr?: string; fixed?: ByBand };
const CAPTIONS: Caption[] = [
  {
    role: 'right',
    why: null,
    text: {
      a1: t('Une guitare : la fête est gratuite.', 'A guitar: the festival is free.', 'Eine Gitarre: Das Fest ist kostenlos.'),
      a2: t('Une guitare pour la fête, gratuite et ouverte à toutes les musiques.', 'A guitar for the festival, free and open to all kinds of music.', 'Eine Gitarre für das Fest, kostenlos und offen für alle Musik.'),
      b1: t('Une guitare acoustique : la fête est gratuite et ouverte à toutes les musiques.', 'An acoustic guitar: the festival is free and open to all kinds of music.', 'Eine Akustikgitarre: Das Fest ist kostenlos und offen für alle Musikrichtungen.'),
    },
  },
  {
    role: 'wrong',
    wrong_fr: 'le 14 juillet',
    right_fr: 'le 21 juin',
    distractor_fr: 'en 1982',
    why: t('La fête a lieu le 21 juin, pas le 14 juillet.', 'The festival is on 21 June, not on 14 July.', 'Das Fest ist am 21. Juni, nicht am 14. Juli.'),
    text: {
      a1: t('Une guitare : la fête a lieu le 14 juillet.', 'A guitar: the festival is on 14 July.', 'Eine Gitarre: Das Fest ist am 14. Juli.'),
      a2: t('Une guitare pour la première fête, le 14 juillet.', 'A guitar for the first festival, on 14 July.', 'Eine Gitarre für das erste Fest, am 14. Juli.'),
      b1: t('Une guitare acoustique : la première fête a eu lieu le 14 juillet 1982.', 'An acoustic guitar: the first festival took place on 14 July 1982.', 'Eine Akustikgitarre: Das erste Fest fand am 14. Juli 1982 statt.'),
    },
    fixed: {
      a1: t('Une guitare : la fête a lieu le 21 juin.', 'A guitar: the festival is on 21 June.', 'Eine Gitarre: Das Fest ist am 21. Juni.'),
      a2: t('Une guitare pour la première fête, le 21 juin.', 'A guitar for the first festival, on 21 June.', 'Eine Gitarre für das erste Fest, am 21. Juni.'),
      b1: t('Une guitare acoustique : la première fête a eu lieu le 21 juin 1982.', 'An acoustic guitar: the first festival took place on 21 June 1982.', 'Eine Akustikgitarre: Das erste Fest fand am 21. Juni 1982 statt.'),
    },
  },
  {
    role: 'other',
    why: t('Cette légende parle de l’autre photo, Paris. Ici, on voit une guitare.', 'This caption is about the other photo, Paris. Here you see a guitar.', 'Diese Bildunterschrift gehört zum anderen Foto, Paris. Hier sieht man eine Gitarre.'),
    text: {
      a1: t('Paris et la Fête de la musique.', 'Paris and the Fête de la musique.', 'Paris und die Fête de la musique.'),
      a2: t('Paris : ici aussi, la fête est ouverte à toutes les musiques.', 'Paris: here too, the festival is open to all kinds of music.', 'Paris: Auch hier ist das Fest offen für alle Musikrichtungen.'),
      b1: t('Paris : dans la ville aussi, la fête est gratuite et ouverte à toutes les musiques.', 'Paris: in the city too, the festival is free and open to all kinds of music.', 'Paris: Auch in der Stadt ist das Fest kostenlos und offen für alle Musikrichtungen.'),
    },
  },
];
const PHOTO_FACTS = [
  t('La fête est gratuite.', 'The festival is free.', 'Das Fest ist kostenlos.'),
  t('La fête est ouverte à toutes les musiques.', 'The festival is open to all kinds of music.', 'Das Fest ist offen für alle Musikrichtungen.'),
  t('La première fête date du 21 juin 1982.', 'The first festival dates from 21 June 1982.', 'Das erste Fest war am 21. Juni 1982.'),
];
const PHOTO_FRAME = t('Au premier plan, on voit', 'In the foreground, you can see', 'Im Vordergrund sieht man');
const PHOTO_PHRASE = {
  a1: t('Sur la photo, on voit…', 'In the photo, you can see…', 'Auf dem Foto sieht man…'),
  a2: t('Au premier plan, …', 'In the foreground, …', 'Im Vordergrund …'),
  b1: t('À l’arrière-plan, …', 'In the background, …', 'Im Hintergrund …'),
};
export const PHOTO_CLOSE_LINE = 'Belle légende ! Ta photo est dans le journal.';
const PHOTO_STEPS = ['read', 'planche', 'legende', 'build', 'page'] as const;
/** The per-session shuffles, fixed: the pictures (a = Paris, b = the guitar), the words, the captions. */
const PICTURE_KEYS: Record<string, string> = { 'photo-1': 'a', 'photo-2': 'b' };
const SEEN_WORDS: Array<{ text: T; own: boolean }> = [
  { text: PICTURES[1].seen[1], own: true },
  { text: PICTURES[0].seen[0], own: false },
  { text: PICTURES[1].seen[0], own: true },
];
const CAPTION_ORDER = [2, 0, 1];
const CAPTION_KEYS = ['a', 'b', 'c'];

export type MockPhotoState = { opened: boolean; chooses: Json[]; seens: Json[]; captions: Json[]; fixes: Json[]; build: Json | null; buildFixes: Json[] };
export const newPhotoState = (): MockPhotoState => ({ opened: false, chooses: [], seens: [], captions: [], fixes: [], build: null, buildFixes: [] });

const resolved = (rows: Json[]) => rows.some((row) => row.correct) || rows.length >= MAX_TRIES;
const correct = (rows: Json[]) => rows.some((row) => row.correct);
const pictureWire = (picture: (typeof PICTURES)[number]) => ({
  key: PICTURE_KEYS[picture.ref],
  kind: picture.kind,
  url: picture.url,
  credit_fr: picture.credit_fr,
  licence: picture.licence,
  licence_url: picture.licence_url,
  source_url: picture.source_url,
  width: picture.width,
  height: picture.height,
});
const pictureByKey = (key: string) => PICTURES.find((p) => PICTURE_KEYS[p.ref] === key) ?? null;
const photoInput = (band: Band) => (band === 'A1' ? 'tiles' : band === 'A2' ? 'frame' : 'free');
const fixInput = (band: Band) => (band === 'A1' || band === 'A2' ? 'pick' : 'write');
const wrongCaption = () => CAPTIONS.find((c) => c.role === 'wrong') as Caption;

export function photoStepOf(s: MockPhotoState, closed: boolean): string {
  if (closed) return 'page';
  if (!s.opened) return 'read';
  if (!(resolved(s.chooses) && resolved(s.seens))) return 'planche';
  if (!(resolved(s.captions) && resolved(s.fixes))) return 'legende';
  const proof = proofOf({ first: s.build, fixes: s.buildFixes });
  if (!proof || proof.proof === 'marked') return 'build';
  return 'page';
}

export function photoView(s: MockPhotoState, ctx: RubriqueContext): Json {
  const { band, language } = ctx;
  const k = bandKey(band);
  const step = photoStepOf(s, ctx.closed);
  const at = PHOTO_STEPS.indexOf(step as (typeof PHOTO_STEPS)[number]);
  let planche: Json | null = null;
  if (at >= 1) {
    const done = resolved(s.chooses);
    const last = s.chooses.length && !correct(s.chooses) ? s.chooses[s.chooses.length - 1] : null;
    const picked = last ? pictureByKey(String(last.key)) : null;
    let seen: Json | null = null;
    if (done) {
      const own = SEEN_WORDS.map((row, i) => (row.own ? i : -1)).filter((i) => i >= 0);
      const lastSeen = s.seens.length ? s.seens[s.seens.length - 1] : null;
      const sres = resolved(s.seens);
      const pickedWords: number[] = lastSeen ? lastSeen.words : [];
      seen = {
        words: SEEN_WORDS.map((row, index) => ({ index, text: tr(row.text, language) })),
        tries: s.seens.length,
        max_tries: MAX_TRIES,
        picked: pickedWords,
        elsewhere: lastSeen && !correct(s.seens) ? pickedWords.filter((i) => !own.includes(i)) : [],
        missing: lastSeen && !correct(s.seens) ? own.filter((i) => !pickedWords.includes(i)).length : 0,
        resolved: sres,
        correct: sres ? correct(s.seens) : null,
        solution: sres ? own : [],
      };
    }
    planche = {
      headline_fr: ctx.titleFr,
      pictures: PICTURES.map(pictureWire),
      tries: s.chooses.length,
      max_tries: MAX_TRIES,
      picked: s.chooses.map((c) => String(c.key)),
      shows: picked ? picked.seen.map((row) => tr(row, language)) : [],
      resolved: done,
      correct: done ? correct(s.chooses) : null,
      solution: done ? PICTURE_KEYS[LEAD] : null,
      seen,
    };
  }
  let legende: Json | null = null;
  if (at >= 2) {
    const done = resolved(s.captions);
    const picked = s.captions.map((c) => String(c.key));
    const wrong = wrongCaption();
    const fres = resolved(s.fixes);
    legende = {
      picture: pictureWire(PICTURES[1]),
      captions: CAPTION_ORDER.map((index, position) => {
        const caption = CAPTIONS[index];
        const key = CAPTION_KEYS[position];
        const open = done || picked.includes(key);
        return { key, text: tr(caption.text[k], language), role: open ? caption.role : null, why: open && caption.why ? tr(caption.why, language) : null };
      }),
      tries: s.captions.length,
      max_tries: MAX_TRIES,
      picked,
      resolved: done,
      correct: done ? correct(s.captions) : null,
      solution: done ? CAPTION_KEYS[CAPTION_ORDER.indexOf(1)] : null,
      fix: done
        ? {
            input: fixInput(band),
            text: tr(wrong.text[k], language),
            wrong_fr: wrong.wrong_fr,
            options: fixInput(band) === 'pick' ? [wrong.distractor_fr, wrong.right_fr] : [],
            tries: s.fixes.length,
            max_tries: MAX_TRIES,
            attempts: s.fixes.map((row) => String(row.value || row.text || '')),
            resolved: fres,
            correct: fres ? correct(s.fixes) : null,
            right_fr: fres ? wrong.right_fr : null,
            fixed: fres && wrong.fixed ? tr(wrong.fixed[k], language) : null,
          }
        : null,
    };
  }
  let build: Json | null = null;
  if (at >= 3) {
    const input = photoInput(band);
    build = {
      input,
      phrase: tr(PHOTO_PHRASE[k], language),
      choices: PICTURES.map((p) => ({ picture: pictureWire(p), seen: p.seen.map((row) => tr(row, language)) })),
      facts: input === 'tiles' ? PHOTO_FACTS.map((row) => tr(row, language)) : [],
      frame: input === 'frame' ? tr(PHOTO_FRAME, language) : null,
      max_words: input === 'free' ? 30 : 20,
      picture: s.build ? s.build.key : null,
      learner_fr: s.build ? s.build.learner_fr : null,
      ...proofWire({ first: s.build, fixes: s.buildFixes }, ctx),
    };
  }
  return { step, steps: [...PHOTO_STEPS], band: k, title_fr: ctx.titleFr, read: read(ctx), planche, legende, build };
}

const nounsOf = (text: string) =>
  new Set(
    fold(text)
      .split(/[^a-z0-9']+/)
      .map((w) => w.replace(/^(l|d)'/, ''))
      .filter((w) => w.length >= 3 && !['les', 'des', 'une', 'the', 'and'].includes(w))
      .map((w) => (w.length > 4 && /[sx]$/.test(w) ? w.slice(0, -1) : w).slice(0, 5)),
  );
const mentions = (text: string, seen: T[]) => seen.some((row) => Array.from(nounsOf(row.fr)).every((w) => nounsOf(text).has(w)));

function captionProblem(text: string, picture: (typeof PICTURES)[number], input: string, ctx: RubriqueContext): Json | null {
  const count = wordCount(text);
  const max = input === 'free' ? 30 : 20;
  if (count < 3) return { code: 'too_short', count: 3 };
  if (count > max) return { code: 'too_long', count: max };
  const known = numbers(ctx.claimsFr.join(' '));
  if (Array.from(numbers(text)).some((n) => !known.has(n))) return { code: 'number_not_in_claims' };
  const sentences = text.split(/(?<=[.!?…])\s+/).filter(Boolean);
  if (input === 'free' && sentences.length < 2) return { code: 'two_sentences', count: 2 };
  if (!mentions(input === 'free' ? sentences[0] : text, picture.seen)) return { code: 'name_what_you_see' };
  if (input === 'free' && !/f[eê]te|musique|juin|gratuit|1982/i.test(sentences.slice(1).join(' '))) return { code: 'say_the_news' };
  if (fold(text).includes(fold(String(wrongCaption().wrong_fr)))) return { code: 'wrong_fact' };
  return null;
}
const shapeCaption = (typed: string, input: string) => {
  let text = typed.replace(/\s+/g, ' ').trim();
  if (input === 'frame' && !fold(text).startsWith(fold(PHOTO_FRAME.fr))) text = `${PHOTO_FRAME.fr} ${text}`;
  if (text && !/[.!?…]$/.test(text)) text += '.';
  return typography(text.charAt(0).toUpperCase() + text.slice(1));
};

export function applyPhotoAct(s: MockPhotoState, body: Json, ctx: RubriqueContext): Json | null {
  const { band } = ctx;
  const act = String(body.act || '');
  const step = photoStepOf(s, ctx.closed);
  const outOfOrder = () => ctx.fail(409, { code: 'revue_photo_out_of_order', step, act });
  const bad = () => ctx.fail(422, { code: 'revue_photo_bad_act', act });
  if (ctx.closed) throw outOfOrder();
  if (act === 'open') {
    s.opened = true;
    return null;
  }
  if (act === 'choose') {
    const picture = pictureByKey(String(body.key || ''));
    if (!picture) throw bad();
    if (resolved(s.chooses) || s.chooses.some((c) => c.key === body.key)) return null;
    if (!s.opened) throw outOfOrder();
    s.chooses.push({ key: body.key, correct: picture.ref === LEAD });
    return null;
  }
  if (act === 'seen') {
    const words: number[] = Array.from(new Set<number>((body.words || []).map(Number))).sort((a, b) => a - b);
    if (!words.length) return { code: 'pick_words' };
    if (resolved(s.seens) || (s.seens.length && JSON.stringify(s.seens[s.seens.length - 1].words) === JSON.stringify(words))) return null;
    if (!resolved(s.chooses)) throw outOfOrder();
    const own = SEEN_WORDS.map((row, i) => (row.own ? i : -1)).filter((i) => i >= 0);
    s.seens.push({ words, correct: JSON.stringify(words) === JSON.stringify(own) });
    return null;
  }
  if (act === 'caption') {
    const position = CAPTION_KEYS.indexOf(String(body.key || ''));
    if (position < 0) throw bad();
    if (resolved(s.captions) || s.captions.some((c) => c.key === body.key)) return null;
    if (step !== 'legende') throw outOfOrder();
    s.captions.push({ key: body.key, correct: CAPTIONS[CAPTION_ORDER[position]].role === 'wrong' });
    return null;
  }
  if (act === 'caption_fix') {
    if (step !== 'legende' || !resolved(s.captions)) throw outOfOrder();
    if (resolved(s.fixes)) return null;
    const wrong = wrongCaption();
    if (fixInput(band) === 'pick') {
      const value = String(body.value || '');
      if (![wrong.right_fr, wrong.distractor_fr].includes(value)) throw bad();
      s.fixes.push({ value, correct: value === wrong.right_fr });
      return null;
    }
    const text = String(body.text || '').trim();
    if (wordCount(text) < 4) return { code: 'too_short', count: 4 };
    const head = fold(text).split(', pas ')[0];
    s.fixes.push({ text, correct: head.includes(fold(String(wrong.right_fr))) && !head.includes(fold(String(wrong.wrong_fr))) });
    return null;
  }
  if (act === 'build') {
    if (s.build) return null;
    if (step !== 'build') throw outOfOrder();
    const picture = pictureByKey(String(body.key || ''));
    if (!picture) return { code: 'pick_picture' };
    const input = photoInput(band);
    if (input === 'tiles') {
      const parts: number[] = Array.isArray(body.parts) ? body.parts.map(Number) : [];
      if (parts.length !== 2 || !picture.seen[parts[0]] || !PHOTO_FACTS[parts[1]]) return { code: 'pick_tiles' };
      const learner = `Sur la photo, on voit ${picture.seen[parts[0]].fr}. ${PHOTO_FACTS[parts[1]].fr.replace(/[\s.]+$/, '')}.`;
      s.build = { key: body.key, learner_fr: learner, typed_fr: '', proof: 'clean', target_fr: learner, marks: [] };
      return null;
    }
    const typed = String(body.text || '');
    const learner = shapeCaption(typed, input);
    const problem = captionProblem(learner, picture, input, ctx);
    if (problem) return problem;
    const check = edit(learner);
    s.build = { key: body.key, learner_fr: learner, typed_fr: typed.trim(), proof: check.proof, target_fr: check.target, marks: check.marks };
    return null;
  }
  if (act === 'build_fix') {
    const picture = s.build ? pictureByKey(String(s.build.key)) : null;
    if (!picture) throw outOfOrder();
    const input = photoInput(band);
    const trail = { first: s.build, fixes: s.buildFixes };
    return fixInto(trail, body, (text) => captionProblem(text, picture, input === 'free' ? 'free' : 'frame', ctx), (text) => shapeCaption(text, 'free'), outOfOrder);
  }
  throw bad();
}

export function photoClose(s: MockPhotoState, ctx: RubriqueContext): { page: Json; dispatch: Json; printed: string; own: string; proof: string } {
  const proof = proofOf({ first: s.build, fixes: s.buildFixes });
  if (!proof || proof.proof === 'marked') throw ctx.fail(409, { code: 'revue_photo_out_of_order', step: photoStepOf(s, false), act: 'close' });
  const k = bandKey(ctx.band);
  const picture = pictureByKey(String(s.build?.key)) ?? PICTURES[1];
  const printed = String(proof.printed || '');
  const own = [s.build?.typed_fr, ...s.buildFixes.map((fix) => fix.typed_fr)].filter(Boolean).join(' ');
  const page = { title_fr: ctx.titleFr, dateline_fr: ctx.datelineFr, picture: pictureWire(picture), caption_fr: printed, proof: proof.proof, phrase_fr: PHOTO_PHRASE[k].fr, words: [] };
  const dispatch = {
    kicker_fr: 'La photo de Romy',
    headline_fr: ctx.titleFr,
    body_fr: [printed, picture.credit_fr],
    contribution: [],
    byline_fr: `Romy Tremblay, avec toi · d'après ${ctx.sources.map((src) => String(src.name)).join(' et ')}`,
    sources: ctx.sources,
  };
  return { page, dispatch, printed, own, proof: proof.proof };
}

// --- «Le micro»: the material --------------------------------------------------------

type Fact = { ask: string; keywords: string[]; hole: T; tile: T; frame: T; answer: ByBand; value_fr: string; source: number };
const FACTS: Fact[] = [
  {
    ask: 'quand', keywords: ['première', 'eu lieu'], value_fr: 'le 21 juin 1982', source: 0,
    hole: t('Quand, la première fête ?', 'When was the first festival?', 'Wann war das erste Fest?'),
    tile: t('Quand est-ce que la première fête a eu lieu ?', 'When did the first festival take place?', 'Wann hat das erste Fest stattgefunden?'),
    frame: t('Quand est-ce que', 'When', 'Wann'),
    answer: {
      a1: t('Le 21 juin 1982, mon chou ! La première fête.', 'On 21 June 1982, sweetie! The first festival.', 'Am 21. Juni 1982, Schätzchen! Das erste Fest.'),
      a2: t("Mais arrête, c'est évident : la première Fête de la musique, c'est le 21 juin 1982.", "Come on, it's obvious: the first Fête de la musique was on 21 June 1982.", 'Ach komm, das ist doch klar: Die erste Fête de la musique war am 21. Juni 1982.'),
      b1: t("Mais arrête, c'est évident : la première Fête de la musique a eu lieu le 21 juin 1982, le jour le plus long de l'année.", "Come on, it's obvious: the first Fête de la musique took place on 21 June 1982, the longest day of the year.", 'Ach komm, das ist doch klar: Die erste Fête de la musique fand am 21. Juni 1982 statt, am längsten Tag des Jahres.'),
    },
  },
  {
    ask: 'pourquoi', keywords: ['jour', 'long', '21 juin'], value_fr: "le jour le plus long de l'année", source: 0,
    hole: t('Pourquoi le 21 juin ?', 'Why 21 June?', 'Warum der 21. Juni?'),
    tile: t("Pourquoi est-ce que la fête a lieu le 21 juin ?", 'Why does the festival take place on 21 June?', 'Warum findet das Fest am 21. Juni statt?'),
    frame: t('Pourquoi est-ce que', 'Why', 'Warum'),
    answer: {
      a1: t("C'est le jour le plus long de l'année !", "It's the longest day of the year!", 'Das ist der längste Tag des Jahres!'),
      a2: t("Parce que le 21 juin, c'est le jour le plus long de l'année. Logique, non ?", 'Because 21 June is the longest day of the year. Makes sense, right?', 'Weil der 21. Juni der längste Tag des Jahres ist. Logisch, oder?'),
      b1: t("Mais arrête, c'est évident : la fête tombe le 21 juin parce que c'est le jour le plus long de l'année.", "Come on, it's obvious: the festival falls on 21 June because it's the longest day of the year.", 'Ach komm, das ist doch klar: Das Fest ist am 21. Juni, weil das der längste Tag des Jahres ist.'),
    },
  },
  {
    ask: 'combien', keywords: ['gratuite', 'coûte'], value_fr: 'gratuite', source: 0,
    hole: t('Combien ça coûte ?', 'How much does it cost?', 'Wie viel kostet es?'),
    tile: t('Combien coûte la fête ?', 'How much does the festival cost?', 'Wie viel kostet das Fest?'),
    frame: t('Combien coûte', 'How much is', 'Wie viel kostet'),
    answer: {
      a1: t('Rien du tout ! La fête est gratuite.', 'Nothing at all! The festival is free.', 'Gar nichts! Das Fest ist kostenlos.'),
      a2: t('Rien, mon chou ! La fête est gratuite, on ne paie pas pour écouter.', "Nothing, sweetie! The festival is free, you don't pay to listen.", 'Nichts, Schätzchen! Das Fest ist kostenlos, man zahlt nicht fürs Zuhören.'),
      b1: t('Rien du tout, mon chou : la fête est gratuite. Tu écoutes ce que tu veux sans payer.', 'Nothing at all, sweetie: the festival is free. You listen to whatever you like without paying.', 'Gar nichts, Schätzchen: Das Fest ist kostenlos. Du hörst, was du willst, ohne zu zahlen.'),
    },
  },
  {
    ask: 'quoi', keywords: ['musiques', 'ouverte'], value_fr: 'toutes les musiques', source: 0,
    hole: t('Quelles musiques ?', 'Which music?', 'Welche Musik?'),
    tile: t("Quelles musiques est-ce qu'on peut écouter ?", 'Which kinds of music can you hear?', 'Welche Musik kann man hören?'),
    frame: t('Quelles musiques est-ce que', 'Which music', 'Welche Musik'),
    answer: {
      a1: t('Toutes les musiques, mon chou ! La fête est ouverte.', 'All kinds of music, sweetie! The festival is open.', 'Alle Musikrichtungen, Schätzchen! Das Fest ist offen.'),
      a2: t("Mais arrête, c'est évident : la fête est ouverte à toutes les musiques, sans exception.", "Come on, it's obvious: the festival is open to all kinds of music, no exceptions.", 'Ach komm, das ist doch klar: Das Fest ist offen für alle Musikrichtungen, ohne Ausnahme.'),
      b1: t('Toutes les musiques ! La fête est ouverte à toutes les musiques, et en plus, elle est gratuite.', "All kinds of music! The festival is open to all kinds of music, and on top of that it's free.", 'Alle Musikrichtungen! Das Fest ist offen für alle Musikrichtungen, und außerdem ist es kostenlos.'),
    },
  },
  {
    ask: 'pourquoi', keywords: ['plaintes', 'bruit'], value_fr: 'du bruit', source: 1,
    hole: t('Pourquoi des plaintes ?', 'Why the complaints?', 'Warum die Beschwerden?'),
    tile: t("Pourquoi est-ce qu'il y a des plaintes ?", 'Why are there complaints?', 'Warum gibt es Beschwerden?'),
    frame: t("Pourquoi est-ce qu'il y a", 'Why are there', 'Warum gibt es'),
    answer: {
      a1: t('À cause du bruit ! Il y a de nombreuses plaintes.', 'Because of the noise! There are many complaints.', 'Wegen des Lärms! Es gibt viele Beschwerden.'),
      a2: t('Parce que la fête fait du bruit, mon chou. Alors il y a de nombreuses plaintes.', 'Because the festival makes noise, sweetie. So there are many complaints.', 'Weil das Fest Lärm macht, Schätzchen. Deshalb gibt es viele Beschwerden.'),
      b1: t("La musique, c'est joli, mais la fête provoque aussi du bruit, et il y a de nombreuses plaintes.", 'Music is lovely, but the festival also causes noise, and there are many complaints.', 'Musik ist schön, aber das Fest macht auch Lärm, und es gibt viele Beschwerden.'),
    },
  },
  {
    ask: 'comment', keywords: ['succès', 'première édition', 'espérances'], value_fr: 'toutes les espérances', source: 0,
    hole: t('Comment, la première édition ?', 'How did the first edition go?', 'Wie war die erste Ausgabe?'),
    tile: t("Comment est-ce que la première édition s'est passée ?", 'How did the first edition go?', 'Wie ist die erste Ausgabe gelaufen?'),
    frame: t('Comment est-ce que', 'How', 'Wie'),
    answer: {
      a1: t('Un grand succès ! Au-delà de toutes les espérances.', 'A big success! Beyond all expectations.', 'Ein großer Erfolg! Über alle Erwartungen hinaus.'),
      a2: t('Selon le ministère de la Culture, le succès a dépassé toutes les espérances. Pas mal, non ?', 'According to the Ministry of Culture, the success exceeded all expectations. Not bad, right?', 'Laut Kulturministerium hat der Erfolg alle Erwartungen übertroffen. Nicht schlecht, oder?'),
      b1: t("D'après le ministère de la Culture, le succès de la première édition, en 1982, a dépassé toutes les espérances.", 'According to the Ministry of Culture, the success of the first edition, in 1982, exceeded all expectations.', 'Laut Kulturministerium hat der Erfolg der ersten Ausgabe 1982 alle Erwartungen übertroffen.'),
    },
  },
];
const SHRUG: ByBand = {
  a1: t('Ça, je ne sais pas, mon chou.', "That, I don't know, sweetie.", 'Das weiß ich nicht, Schätzchen.'),
  a2: t("Bon, ça, je ne sais pas. L'article ne le dit pas.", "Well, that I don't know. The article doesn't say.", 'Tja, das weiß ich nicht. Der Artikel sagt es nicht.'),
  b1: t("Toi, tu me poses des colles ! Ça, je ne sais pas, et l'article ne le dit pas.", "You and your tricky questions! That I don't know, and the article doesn't say.", 'Du stellst mir aber Fangfragen! Das weiß ich nicht, und der Artikel sagt es nicht.'),
};
const MICRO_PHRASE = {
  a1: t('Quand… ? · Combien… ?', 'When…? · How many…?', 'Wann…? · Wie viele…?'),
  a2: t('Pourquoi est-ce que… ?', 'Why…?', 'Warum…?'),
  b1: t('Est-ce que vous pourriez me dire… ?', 'Could you tell me…?', 'Könnten Sie mir sagen, …?'),
};
const WITNESS = { id: 'lila_bonnet', name_fr: 'Lila', role_fr: 'prof' };
export const MICRO_CLOSE_LINE = 'Super interview ! Tes questions et ses réponses sont dans le journal.';
const MICRO_STEPS = ['read', 'prepare', 'interview', 'notes', 'review', 'page'] as const;
/** Fixed per-session order of the holes (the server's is per session). */
const HOLE_ORDER = [2, 0, 4, 3, 1, 5];
const HOLE_KEYS = ['a', 'b', 'c', 'd', 'e', 'f'];
const factOf = (key: string) => FACTS[HOLE_ORDER[HOLE_KEYS.indexOf(key)]];
const keyOf = (index: number) => HOLE_KEYS[HOLE_ORDER.indexOf(index)];

export type MockMicroState = { opened: boolean; chosen: string[]; asks: Json[]; notes: Record<string, Json[]>; review: Json | null; fixes: Json[] };
export const newMicroState = (): MockMicroState => ({ opened: false, chosen: [], asks: [], notes: {}, review: null, fixes: [] });

const spent = (s: MockMicroState) => s.asks.filter((a) => a.spent).length;
const free = (s: MockMicroState) => (s.asks.length ? Boolean(s.asks[s.asks.length - 1].spent) : true);
const obtained = (s: MockMicroState) => s.asks.filter((a) => a.kind === 'answer').map((a) => String(a.fact));
const noteResolved = (s: MockMicroState, key: string) => resolved(s.notes[key] || []);
const askInput = (band: Band) => (band === 'A1' ? 'tiles' : band === 'A2' ? 'frame' : 'free');
const noteInput = (band: Band) => (band === 'A1' || band === 'A2' ? 'pick' : 'write');
const questionsOf = (s: MockMicroState) => s.asks.filter((a) => a.kind === 'answer').map((a) => String(a.text_fr));

export function microStepOf(s: MockMicroState, closed: boolean): string {
  if (closed) return 'page';
  if (!s.opened) return 'read';
  if (s.chosen.length < 3) return 'prepare';
  if (spent(s) < 3) return 'interview';
  if (!obtained(s).every((key) => noteResolved(s, key))) return 'notes';
  const proof = proofOf({ first: s.review, fixes: s.fixes });
  if (!proof || proof.proof === 'marked') return 'review';
  return 'page';
}

const STOP = new Set('le la les l un une des de du d au aux a en dans sur par pour et ou est sont c ce cette ces qui que qu il elle ils elles on se s sa son ses leur leurs avec sans plus moins tres pas ne n y'.split(' '));
const QWORDS = new Set('qui que quoi quand combien pourquoi comment quel quelle quels quelles est-ce vous tu pouvez peux dire savoir'.split(' '));
function stems(text: string): Set<string> {
  const out = new Set<string>();
  for (const raw of fold(text).match(/[0-9]+|[a-z]+(?:['-][a-z]+)*/g) || []) {
    const word = raw.replace(/^(l|d|qu|j|n|s|c|m|t)'/, '');
    if (/^[0-9]/.test(word)) out.add(word);
    else if (word.length >= 4 && !STOP.has(word) && !QWORDS.has(word)) out.add((word.length > 4 && /[sx]$/.test(word) ? word.slice(0, -1) : word).slice(0, 5));
  }
  return out;
}
function questionWord(text: string): string | null {
  const tokens = text.toLowerCase().replace(/’/g, "'").match(/[a-zà-ÿœ']+/g) || [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token === 'où' || token === "d'où") return 'ou';
    const f = fold(token);
    if (f.startsWith("qu'est") || (f.startsWith("qu'") && index === 0)) return 'quoi';
    if (['combien', 'pourquoi', 'comment', 'quand', 'quoi'].includes(f)) return f;
    if (['quel', 'quelle', 'quels', 'quelles'].includes(f)) return 'quel';
    if (f === 'qui' && index <= 1) return 'qui';
  }
  return null;
}
const asks = (q: string | null, ask: string) => (q === 'quel' ? !['pourquoi', 'comment'].includes(ask) : q === ask);
/** The port of `micro.match`: the question word and the content words (kept small). */
function matchFact(text: string, chosen: number[]): number | 'ambiguous' | null {
  const q = questionWord(text);
  const words = stems(text);
  const weak = new Set(Array.from(words).map((w) => w.slice(0, 4)));
  const hits = FACTS.map((fact) => {
    const own = stems(fact.keywords.join(' '));
    const strong = Array.from(own).filter((w) => words.has(w)).length;
    const loose = q && asks(q, fact.ask) ? Array.from(own).filter((w) => weak.has(w.slice(0, 4))).length : 0;
    return strong || loose;
  });
  let candidates: number[] = [];
  const withHits = hits.map((n, i) => (n > 0 ? i : -1)).filter((i) => i >= 0);
  const generic = stems('La Fête de la musique');
  if (withHits.length) {
    const asked = withHits.filter((i) => q && asks(q, FACTS[i].ask));
    const pool = asked.length ? asked : withHits;
    const best = Math.max(...pool.map((i) => hits[i]));
    candidates = pool.filter((i) => hits[i] === best);
  } else if (q && q !== 'quel' && Array.from(words).every((w) => generic.has(w))) {
    candidates = FACTS.map((f, i) => (f.ask === q ? i : -1)).filter((i) => i >= 0);
  }
  if (candidates.length > 1) {
    const mine = candidates.filter((i) => chosen.includes(i));
    if (mine.length) candidates = mine;
  }
  if (!candidates.length) return null;
  return candidates.length === 1 ? candidates[0] : 'ambiguous';
}
function slipsOf(text: string, fact: Fact | null): string[] {
  const tokens = text.toLowerCase().replace(/’/g, "'").match(/[a-zà-ÿœ'-]+/g) || [];
  const q = questionWord(text);
  const out: string[] = [];
  const [first = '', second = '', third = ''] = tokens;
  const pronouns = 'je tu il elle on nous vous ils elles'.split(' ');
  if (tokens.length >= 3 && q && !['qui', 'quel'].includes(q) && ['combien', 'pourquoi', 'comment', 'quand', 'où'].includes(first) && !fold(text).includes('est-ce') && pronouns.includes(second) && !third.includes('-')) out.push('inversion');
  if (fact && q && q !== 'quel' && q !== fact.ask) out.push('question_word');
  return out;
}
const noteOptions = (index: number) => {
  const value = FACTS[index].value_fr;
  const others = FACTS.filter((_, i) => i !== index).map((f) => f.value_fr).filter((v) => v !== value);
  return [others[(index + 1) % others.length], value, others[(index + 3) % others.length]].filter((v, i, all) => all.indexOf(v) === i);
};

export function microView(s: MockMicroState, ctx: RubriqueContext): Json {
  const { band, language } = ctx;
  const k = bandKey(band);
  const step = microStepOf(s, ctx.closed);
  const at = MICRO_STEPS.indexOf(step as (typeof MICRO_STEPS)[number]);
  const got = obtained(s);
  const hole = (key: string) => ({ key, hole: tr(factOf(key).hole, language), filled: got.includes(key) });
  const prepare = at >= 1 ? { holes: HOLE_KEYS.map(hole), chosen: s.chosen, need: 3 } : null;
  let interview: Json | null = null;
  if (at >= 2) {
    const input = askInput(band);
    interview = {
      witness: WITNESS,
      input,
      phrase: tr(MICRO_PHRASE[k], language),
      holes: s.chosen.map(hole),
      tiles: input === 'tiles' ? s.chosen.filter((key) => !got.includes(key)).map((key) => ({ key, text: tr(factOf(key).tile, language) })) : [],
      frames: input === 'frame' ? Array.from(new Map(s.chosen.map((key) => [factOf(key).frame.fr, tr(factOf(key).frame, language)])).values()) : [],
      turns: s.asks.map((a) => ({
        question_fr: a.text_fr,
        answer: tr(a.fact ? factOf(String(a.fact)).answer[k] : SHRUG[k], language),
        kind: a.kind,
        spent: a.spent,
        hole_key: a.fact ?? null,
      })),
      spent: spent(s),
      total: 3,
      free: free(s),
      done: spent(s) >= 3,
    };
  }
  let notes: Json | null = null;
  if (at >= 3) {
    const input = noteInput(band);
    notes = {
      input,
      items: got.map((key) => {
        const rows = s.notes[key] || [];
        const done = noteResolved(s, key);
        const fact = factOf(key);
        return {
          key,
          hole: tr(fact.hole, language),
          answer: tr(fact.answer[k], language),
          options: input === 'pick' ? noteOptions(HOLE_ORDER[HOLE_KEYS.indexOf(key)]) : [],
          tries: rows.length,
          max_tries: MAX_TRIES,
          attempts: rows.map((r) => String(r.value || r.text || '')),
          resolved: done,
          correct: done ? correct(rows) : null,
          value_fr: done ? fact.value_fr : null,
        };
      }),
    };
  }
  let review: Json | null = null;
  if (at >= 4) {
    const answered = s.asks.filter((a) => a.kind === 'answer');
    review = {
      input: askInput(band) === 'tiles' ? 'tiles' : 'write',
      questions: questionsOf(s),
      hints: askInput(band) === 'tiles' ? [] : answered.flatMap((a, index) => (a.slips || []).map((code: string) => ({ index, code }))),
      ...proofWire({ first: s.review, fixes: s.fixes }, ctx),
    };
  }
  return { step, steps: [...MICRO_STEPS], band: k, title_fr: ctx.titleFr, read: read(ctx), prepare, interview, notes, review };
}

const shapeQuestion = (text: string) => {
  let value = typography(text.replace(/\s+/g, ' ').trim());
  value = value.charAt(0).toUpperCase() + value.slice(1);
  return /\?\s*$/.test(value) ? value : typography(`${value.replace(/[\s.!]+$/, '')} ?`);
};
const isQuestion = (text: string) => /\?\s*$/.test(text.trim()) || questionWord(text) !== null || /^est-ce qu/.test(fold(text.trim()));

export function applyMicroAct(s: MockMicroState, body: Json, ctx: RubriqueContext): Json | null {
  const { band } = ctx;
  const act = String(body.act || '');
  const step = microStepOf(s, ctx.closed);
  const outOfOrder = () => ctx.fail(409, { code: 'revue_micro_out_of_order', step, act });
  const bad = () => ctx.fail(422, { code: 'revue_micro_bad_act', act });
  if (ctx.closed) throw outOfOrder();
  if (act === 'open') {
    s.opened = true;
    return null;
  }
  if (act === 'prepare') {
    const keys: string[] = Array.from(new Set<string>((body.keys || []).map(String)));
    if (keys.some((key) => !HOLE_KEYS.includes(key))) throw bad();
    if (s.chosen.length) return null;
    if (!s.opened) throw outOfOrder();
    if (keys.length !== 3) return { code: 'pick_three', count: 3 };
    s.chosen = keys;
    return null;
  }
  if (act === 'ask') {
    if (step !== 'interview') {
      if (spent(s) >= 3) return null;
      throw outOfOrder();
    }
    const input = askInput(band);
    let text: string;
    let index: number | null;
    if (input === 'tiles') {
      const key = String(body.key || '');
      if (!s.chosen.includes(key)) throw bad();
      text = factOf(key).tile.fr;
      index = HOLE_ORDER[HOLE_KEYS.indexOf(key)];
    } else {
      const raw = String(body.text || '').replace(/\s+/g, ' ').trim();
      text = shapeQuestion(raw);
      const count = wordCount(text);
      if (count < 2) return { code: 'too_short', count: 2 };
      if (count > 20) return { code: 'too_long', count: 20 };
      if (!isQuestion(raw)) return { code: 'not_a_question' };
      const found = matchFact(text, s.chosen.map((key) => HOLE_ORDER[HOLE_KEYS.indexOf(key)]));
      // an ambiguous question: the mock's «model» says «none» (the shrug)
      index = found === 'ambiguous' ? null : found;
    }
    if (s.asks.length && fold(String(s.asks[s.asks.length - 1].text_fr)) === fold(text)) return null;
    const key = index === null ? null : keyOf(index);
    const got = obtained(s);
    const kind = key && !got.includes(key) ? 'answer' : key ? 'again' : 'shrug';
    const isSpent = kind === 'answer' ? true : !free(s);
    s.asks.push({ text_fr: text, fact: key, kind, spent: isSpent, slips: input !== 'tiles' && kind === 'answer' ? slipsOf(text, index === null ? null : FACTS[index]) : [] });
    return null;
  }
  if (act === 'note') {
    const key = String(body.key || '');
    if (['read', 'prepare', 'interview'].includes(step)) throw outOfOrder();
    if (!obtained(s).includes(key)) throw bad();
    if (noteResolved(s, key)) return null;
    const fact = factOf(key);
    const rows = (s.notes[key] = s.notes[key] || []);
    if (noteInput(band) === 'pick') {
      const value = String(body.value || '');
      if (!noteOptions(HOLE_ORDER[HOLE_KEYS.indexOf(key)]).includes(value)) throw bad();
      if (rows.length && rows[rows.length - 1].value === value) return null;
      rows.push({ value, correct: value === fact.value_fr });
      return null;
    }
    const text = String(body.text || '').trim();
    if (!text) return { code: 'too_short', count: 1 };
    rows.push({ text, correct: fold(text).includes(fold(fact.value_fr).replace(/^(le |la |les |l'|du |de la |a |à )/, '')) });
    return null;
  }
  if (act === 'review') {
    if (s.review) return null;
    if (step !== 'review') throw outOfOrder();
    const draft = questionsOf(s).join(' ');
    if (askInput(band) === 'tiles') {
      s.review = { learner_fr: draft, typed_fr: '', proof: 'clean', target_fr: draft, marks: [] };
      return null;
    }
    const check = edit(draft);
    s.review = { learner_fr: draft, typed_fr: '', proof: check.proof, target_fr: check.target, marks: check.marks };
    return null;
  }
  if (act === 'review_fix') {
    const count = questionsOf(s).length;
    const trail = { first: s.review, fixes: s.fixes };
    return fixInto(
      trail,
      body,
      (text) => ((text.match(/[^?]+\?/g) || []).length === count ? null : { code: 'keep_questions', count }),
      (text) => typography(text.replace(/\s+/g, ' ').trim()),
      outOfOrder,
    );
  }
  throw bad();
}

export function microClose(s: MockMicroState, ctx: RubriqueContext): { page: Json; dispatch: Json; own: string; proof: string } {
  if (microStepOf(s, false) !== 'page') throw ctx.fail(409, { code: 'revue_micro_out_of_order', step: microStepOf(s, false), act: 'close' });
  const k = bandKey(ctx.band);
  const proof = proofOf({ first: s.review, fixes: s.fixes });
  const asked = questionsOf(s);
  const printedRows = (String(proof?.printed || '').match(/[^?]+\?/g) || []).map((q) => q.trim());
  const printed = printedRows.length === asked.length ? printedRows : asked;
  const keys = obtained(s);
  const lines = keys.map((key, index) => ({
    question_fr: printed[index] ?? '',
    answer_fr: factOf(key).answer[k].fr,
    source_name: String(ctx.sources[Math.min(factOf(key).source, ctx.sources.length - 1)]?.name ?? ''),
  }));
  const own = [s.review?.typed_fr, ...s.fixes.map((fix) => fix.typed_fr)].filter(Boolean).join(' ') || (askInput(ctx.band) === 'tiles' ? '' : asked.join(' '));
  const page = {
    title_fr: ctx.titleFr,
    dateline_fr: ctx.datelineFr,
    witness: WITNESS,
    byline_fr: 'Propos recueillis par toi',
    lines,
    notes: keys.map((key) => ({ hole_fr: factOf(key).hole.fr, value_fr: factOf(key).value_fr, right: correct(s.notes[key] || []) })),
    proof: proof?.proof ?? 'clean',
    phrase_fr: MICRO_PHRASE[k].fr,
    words: [],
  };
  const dispatch = {
    kicker_fr: `L'interview · ${WITNESS.name_fr}`,
    headline_fr: ctx.titleFr,
    body_fr: lines.map((line) => `${line.question_fr} — ${line.answer_fr}`),
    contribution: [],
    byline_fr: `Propos recueillis par toi · d'après ${ctx.sources.map((src) => String(src.name)).join(' et ')}`,
    sources: ctx.sources,
  };
  return { page, dispatch, own, proof: proof?.proof ?? 'clean' };
}
