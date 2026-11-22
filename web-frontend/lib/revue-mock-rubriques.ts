/**
 * «Le titre» and «L'intox express» in the DEV-ONLY mock (`/revue?mock=1&titre=1` or
 * `&intox=1`, `lib/revue-mock.ts`, WIRE §11).
 *
 * The material of «La Fête de la musique» transcribed from
 * `app/services/revue/evergreen/titre/evergreen-fete-de-la-musique.json` and
 * `…/intox/evergreen-fete-de-la-musique.json`, and the learner's loops scripted with the
 * replay rules of `titre_loop.py` and `intox_loop.py`: the step follows from the acts; a
 * wrong headline's role and why only once picked, never the honest one before the step is
 * resolved; the trap graded against the stored words; «À toi» from tiles (A1), the frame (A2)
 * or free (B1+), marked by the comptoir mock's small table (with «Le pourquoi» when
 * `&pourquoi=1`) and fixed by the learner; five statements one at a time, nothing past a
 * statement's text before it is answered; the false ones corrected by picking (A1–A2) or
 * rewriting (B1+). The shuffles are fixed (the server's are per session): the mock is a
 * screen to look at, not a second implementation. Wire JSON in and out.
 */

import { marksWire, notesWire, proofread } from './revue-mock-comptoir';

type Json = Record<string, any>;
type Lang = 'en' | 'de' | 'fr';
type Band = 'A1' | 'A2' | 'B1' | 'B2';
type T = { fr: string; en: string; de: string };
type ByBand = { a1: T; a2: T; b1: T };
type Headline = { role: 'honest' | 'exaggerated' | 'off'; claim_id: string; why: T | null; text: ByBand };
type Statement = {
  text: ByBand;
  claim_id: string;
  true: boolean;
  why: T;
  quote_fr: string;
  source_name: string;
  settles_fr: string;
  wrong_fr: string | null;
  right_fr: string | null;
  distractor_fr: string | null;
  fixed: ByBand | null;
};

const t = (fr: string, en: string, de: string): T => ({ fr, en, de });

// --- the material (transcribed) ------------------------------------------------

const HEADLINES: Headline[] = [
  { role: 'honest', claim_id: 'c2', why: null, text: { a1: t("Une fête gratuite pour toutes les musiques", "A free festival for every kind of music", "Ein kostenloses Fest für jede Musik"), a2: t("Une fête gratuite et ouverte à toutes les musiques", "A free festival, open to every kind of music", "Ein kostenloses Fest, offen für jede Musik"), b1: t("Le 21 juin, une fête gratuite et ouverte à toutes les musiques", "On 21 June, a free festival open to every kind of music", "Am 21. Juni ein kostenloses Fest, offen für jede Musik") } },
  { role: 'exaggerated', claim_id: 'c3', why: t("Pas tout le monde : la fête fait du bruit, et il y a de nombreuses plaintes.", "Not everyone: the festival makes noise, and there are many complaints.", "Nicht allen: Das Fest macht Lärm, und es gibt viele Beschwerden."), text: { a1: t("La fête plaît à tout le monde", "Everyone likes the festival", "Das Fest gefällt allen"), a2: t("Le 21 juin, tout le monde aime la fête", "On 21 June, everyone loves the festival", "Am 21. Juni lieben alle das Fest"), b1: t("Fête de la musique : une nuit qui plaît à tout le monde", "Fête de la musique: a night everyone likes", "Fête de la musique: eine Nacht, die allen gefällt") } },
  { role: 'off', claim_id: 'c1', why: t("C'est vrai, mais ce titre parle du jour, pas de la fête ni de la musique.", "True, but this headline is about the day, not about the festival or the music.", "Stimmt, aber diese Schlagzeile spricht vom Tag, nicht vom Fest oder der Musik."), text: { a1: t("Le jour le plus long de l'année", "The longest day of the year", "Der längste Tag des Jahres"), a2: t("Le 21 juin, jour le plus long de l'année", "21 June, the longest day of the year", "Der 21. Juni, der längste Tag des Jahres"), b1: t("Le 21 juin 1982 était le jour le plus long de l'année", "21 June 1982 was the longest day of the year", "Der 21. Juni 1982 war der längste Tag des Jahres") } },
];
const WRONG_FR = "tout le monde";
const BUILD = {
  subjects: [t("La Fête de la musique", "The Fête de la musique", "Die Fête de la musique"), t("Le 21 juin, la fête", "On 21 June, the festival", "Am 21. Juni das Fest")],
  facts: [t("est gratuite", "is free", "ist kostenlos"), t("est ouverte à toutes les musiques", "is open to every kind of music", "ist offen für jede Musik"), t("fait aussi du bruit", "also makes noise", "macht auch Lärm")],
  frame: t("La Fête de la musique", "The Fête de la musique", "Die Fête de la musique"),
};
const TITRE_PHRASE = { a1: t("La fête est…", "The festival is…", "Das Fest ist…"), a2: t("… et …", "… and …", "… und …"), b1: t("… : … mais …", "… : … but …", "… : … aber …") };
const STATEMENTS: Statement[] = [
  {
    text: { a1: t("La première fête a lieu en 1982.", "The first festival takes place in 1982.", "Das erste Fest findet 1982 statt."), a2: t("La première Fête de la musique a lieu le 21 juin 1982.", "The first Fête de la musique takes place on 21 June 1982.", "Die erste Fête de la musique findet am 21. Juni 1982 statt."), b1: t("La première Fête de la musique a eu lieu le 21 juin 1982.", "The first Fête de la musique took place on 21 June 1982.", "Die erste Fête de la musique fand am 21. Juni 1982 statt.") },
    claim_id: 'c1',
    true: true,
    why: t("La première fête a bien eu lieu le 21 juin 1982.", "The first festival really did take place on 21 June 1982.", "Das erste Fest fand tatsächlich am 21. Juni 1982 statt."),
    quote_fr: "la première Fête de la musique est lancée le 21 juin 1982, jour symbolique du solstice d’été, le plus long de l’année dans l’hémisphère Nord",
    source_name: "Ministère de la Culture (fetedelamusique.culture.gouv.fr)",
    settles_fr: "le 21 juin 1982",
    wrong_fr: null,
    right_fr: null,
    distractor_fr: null,
    fixed: null,
  },
  {
    text: { a1: t("La fête a lieu le 14 juillet.", "The festival takes place on 14 July.", "Das Fest findet am 14. Juli statt."), a2: t("La Fête de la musique a lieu le 14 juillet.", "The Fête de la musique takes place on 14 July.", "Die Fête de la musique findet am 14. Juli statt."), b1: t("La fête a lieu le 14 juillet, le jour le plus long de l'année.", "The festival takes place on 14 July, the longest day of the year.", "Das Fest findet am 14. Juli statt, dem längsten Tag des Jahres.") },
    claim_id: 'c1',
    true: false,
    why: t("La fête a lieu le 21 juin, le jour le plus long, pas le 14 juillet.", "The festival is on 21 June, the longest day, not on 14 July.", "Das Fest ist am 21. Juni, dem längsten Tag, nicht am 14. Juli."),
    quote_fr: "la première Fête de la musique est lancée le 21 juin 1982, jour symbolique du solstice d’été, le plus long de l’année dans l’hémisphère Nord",
    source_name: "Ministère de la Culture (fetedelamusique.culture.gouv.fr)",
    settles_fr: "le 21 juin 1982",
    wrong_fr: "le 14 juillet",
    right_fr: "le 21 juin",
    distractor_fr: "en 1982",
    fixed: { a1: t("La fête a lieu le 21 juin.", "The festival takes place on 21 June.", "Das Fest findet am 21. Juni statt."), a2: t("La Fête de la musique a lieu le 21 juin.", "The Fête de la musique takes place on 21 June.", "Die Fête de la musique findet am 21. Juni statt."), b1: t("La fête a lieu le 21 juin, le jour le plus long de l'année.", "The festival takes place on 21 June, the longest day of the year.", "Das Fest findet am 21. Juni statt, dem längsten Tag des Jahres.") },
  },
  {
    text: { a1: t("La fête est gratuite.", "The festival is free.", "Das Fest ist kostenlos."), a2: t("La fête est gratuite et ouverte à toutes les musiques.", "The festival is free and open to every kind of music.", "Das Fest ist kostenlos und offen für jede Musik."), b1: t("La Fête de la musique est gratuite et ouverte à toutes les musiques.", "The Fête de la musique is free and open to every kind of music.", "Die Fête de la musique ist kostenlos und offen für jede Musik.") },
    claim_id: 'c2',
    true: true,
    why: t("La fête est bien gratuite, pour toutes les musiques.", "The festival really is free, for every kind of music.", "Das Fest ist wirklich kostenlos, für jede Musik."),
    quote_fr: "La Fête sera gratuite, ouverte à toutes les musiques « sans hiérarchie de genres et de pratiques » et à tous les français.",
    source_name: "Ministère de la Culture (fetedelamusique.culture.gouv.fr)",
    settles_fr: "La Fête sera gratuite, ouverte à toutes les musiques",
    wrong_fr: null,
    right_fr: null,
    distractor_fr: null,
    fixed: null,
  },
  {
    text: { a1: t("Selon les voisins, la fête est un succès.", "According to the neighbours, the festival is a success.", "Laut den Nachbarn ist das Fest ein Erfolg."), a2: t("Selon les voisins, la première fête est un très grand succès.", "According to the neighbours, the first festival is a very big success.", "Laut den Nachbarn ist das erste Fest ein sehr großer Erfolg."), b1: t("Selon les voisins, le succès de la première édition a dépassé toutes les espérances.", "According to the neighbours, the success of the first edition went beyond all hopes.", "Laut den Nachbarn hat der Erfolg der ersten Ausgabe alle Erwartungen übertroffen.") },
    claim_id: 'c4',
    true: false,
    why: t("C'est le ministère de la Culture qui parle de succès, pas les voisins.", "It is the Ministry of Culture that speaks of a success, not the neighbours.", "Das Kulturministerium spricht von einem Erfolg, nicht die Nachbarn."),
    quote_fr: "Le résultat dépasse toutes les espérances.",
    source_name: "Ministère de la Culture (fetedelamusique.culture.gouv.fr)",
    settles_fr: "Le résultat dépasse toutes les espérances",
    wrong_fr: "les voisins",
    right_fr: "le ministère de la Culture",
    distractor_fr: "les musiciens",
    fixed: { a1: t("Selon le ministère de la Culture, la fête est un succès.", "According to the Ministry of Culture, the festival is a success.", "Laut dem Kulturministerium ist das Fest ein Erfolg."), a2: t("Selon le ministère de la Culture, la première fête est un très grand succès.", "According to the Ministry of Culture, the first festival is a very big success.", "Laut dem Kulturministerium ist das erste Fest ein sehr großer Erfolg."), b1: t("Selon le ministère de la Culture, le succès de la première édition a dépassé toutes les espérances.", "According to the Ministry of Culture, the success of the first edition went beyond all hopes.", "Laut dem Kulturministerium hat der Erfolg der ersten Ausgabe alle Erwartungen übertroffen.") },
  },
  {
    text: { a1: t("La fête fait aussi du bruit.", "The festival also makes noise.", "Das Fest macht auch Lärm."), a2: t("La fête fait du bruit, et il y a beaucoup de plaintes.", "The festival makes noise, and there are many complaints.", "Das Fest macht Lärm, und es gibt viele Beschwerden."), b1: t("La Fête de la musique provoque aussi du bruit et de nombreuses plaintes.", "The Fête de la musique also causes noise and many complaints.", "Die Fête de la musique verursacht auch Lärm und viele Beschwerden.") },
    claim_id: 'c3',
    true: true,
    why: t("La fête fait bien du bruit, et il y a de nombreuses plaintes.", "The festival does make noise, and there are many complaints.", "Das Fest macht tatsächlich Lärm, und es gibt viele Beschwerden."),
    quote_fr: "La Fête de la musique est source de nuisances sonores avérées et fait l'objet de nombreuses plaintes.",
    source_name: "Wikipédia, « Fête de la musique »",
    settles_fr: "nuisances sonores avérées et fait l'objet de nombreuses plaintes",
    wrong_fr: null,
    right_fr: null,
    distractor_fr: null,
    fixed: null,
  },
];
const INTOX_PHRASE = { a1: t("C'est faux.", "That's false.", "Das stimmt nicht."), a2: t("Ce n'est pas…, c'est…", "It isn't…, it's…", "Es ist nicht…, es ist…"), b1: t("En réalité, …", "In reality, …", "In Wirklichkeit …") };

// --- shared ------------------------------------------------------------------------

export const TITRE_CLOSE_LINE = 'Merci ! Ton titre est en une, et il dit vrai.';
export const INTOX_CLOSE_LINE = "Bien joué ! L'intox est démontée, et ta page est dans le journal.";
const MAX_TRIES = 2;
const FIX_TRIES = 2;
const MAX_WORDS = 12;
const MIN_WORDS = 3;
const WRITE_MIN_WORDS = 4;
const TITRE_STEPS = ['read', 'three', 'trap', 'build', 'page'] as const;
const INTOX_STEPS = ['read', 'round', 'fix', 'page'] as const;
/** Shown order (fixed): headline indices under a, b, c; statement indices under a … e. */
const HEAD_ORDER = [2, 0, 1];
const HEAD_KEYS = ['a', 'b', 'c'];
const CARD_ORDER = [4, 1, 2, 3, 0];
const CARD_KEYS = ['a', 'b', 'c', 'd', 'e'];
const TRAP_STOP = new Set('le la les l de du des d un une a au aux en dans sur et'.split(' '));

const bandKey = (band: Band) => (band === 'A1' ? 'a1' : band === 'A2' ? 'a2' : 'b1') as 'a1' | 'a2' | 'b1';
const tr = (text: T, language: Lang) => ({ fr: text.fr, tr: language === 'fr' ? null : text[language] });
const fold = (text: string) => text.normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[’`]/g, "'").toLowerCase();
const typography = (text: string) => text.replace(/\s*([?!;:])/g, ' $1').replace(/\s+/g, ' ').trim();
const wordsOf = (text: string) => text.match(/[A-Za-zÀ-ÖØ-öø-ÿŒœ\d'’-]+/g) || [];
const wordCount = (text: string) => (text.match(/[A-Za-zÀ-ÖØ-öø-ÿŒœ\d]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*/g) || []).length;
const headlineText = (text: string) => typography(text.replace(/\s+/g, ' ').trim().replace(/[\s.]+$/, ''));
const proofKey = (text: string) => {
  const flat = text.normalize('NFC').replace(/[’`]/g, "'").replace(/[^A-Za-zÀ-ÖØ-öø-ÿŒœ0-9']+/g, ' ').trim();
  return flat.charAt(0).toLowerCase() + flat.slice(1);
};
const contains = (text: string, needle: string) => Boolean(needle) && fold(text).includes(fold(needle));
const numbers = (text: string) => new Set(text.match(/\d+/g) || []);

export type RubriqueContext = {
  band: Band;
  language: Lang;
  closed: boolean;
  titleFr: string;
  datelineFr: string;
  lead: { fr: string; tr: string | null };
  sources: Json[];
  /** The claim as the wire carries it (`rv_claim`), by id. */
  claim: (id: string) => Json | null;
  /** Every claim's French (the number check). */
  claimsFr: string[];
  fail: (status: number, detail: unknown) => Error;
  pourquoi?: boolean;
  /** «La règle» (`&regle=1`): the marks name their grammar concept. */
  regle?: boolean;
};

const read = (ctx: RubriqueContext) => ({ dateline_fr: ctx.datelineFr, lead: ctx.lead, sources: ctx.sources.slice(0, 1) });

// --- «Le titre» ----------------------------------------------------------------------

export type MockTitreState = { opened: boolean; picks: Json[]; traps: Json[]; build: Json | null; fixes: Json[] };
export const newTitreState = (): MockTitreState => ({ opened: false, picks: [], traps: [], build: null, fixes: [] });

const threeResolved = (s: MockTitreState) => s.picks.some((p) => p.correct) || s.picks.length >= MAX_TRIES;
const trapResolved = (s: MockTitreState) => s.traps.some((p) => p.correct) || s.traps.length >= MAX_TRIES;
const exaggerated = () => HEADLINES.find((h) => h.role === 'exaggerated') as Headline;
const honest = () => HEADLINES.find((h) => h.role === 'honest') as Headline;
const titreProof = (s: MockTitreState) => {
  if (!s.build) return null;
  const latest = s.fixes.length ? s.fixes[s.fixes.length - 1] : s.build;
  const texts = s.fixes.filter((fix) => fix.text_fr).map((fix) => String(fix.text_fr));
  const draft = texts.length ? texts[texts.length - 1] : String(s.build.learner_fr);
  const proof = String(latest.proof);
  const target = String(latest.target_fr || '');
  const printed = proof === 'marked' ? null : proof === 'as_written' ? draft : target || draft;
  return { proof, draft, marks: proof === 'marked' ? (latest.marks as Json[]) : [], tries: texts.length, target, printed };
};
const titreRounds = (s: MockTitreState): Json[][] =>
  [s.build, ...s.fixes].filter((row): row is Json => Boolean(row) && row?.proof === 'marked' && Array.isArray(row?.marks)).map((row) => row.marks);

export function titreStepOf(s: MockTitreState, closed: boolean): string {
  if (closed) return 'page';
  if (!s.opened) return 'read';
  if (!threeResolved(s)) return 'three';
  if (!trapResolved(s)) return 'trap';
  const proof = titreProof(s);
  if (!proof || proof.proof === 'marked') return 'build';
  return 'page';
}

/** The trap's words that say too much (indices), as `titre_loop.wrong_span`. */
function wrongSpan(headline: string): number[] {
  const words = wordsOf(headline).map(fold);
  const needle = wordsOf(WRONG_FR).map(fold);
  for (let start = 0; start + needle.length <= words.length; start += 1) {
    if (needle.every((w, i) => words[start + i] === w)) return needle.map((_, i) => start + i);
  }
  return [];
}

const buildInput = (band: Band) => (band === 'A1' ? 'tiles' : band === 'A2' ? 'frame' : 'free');

export function titreView(s: MockTitreState, ctx: RubriqueContext): Json {
  const { band, language } = ctx;
  const k = bandKey(band);
  const step = titreStepOf(s, ctx.closed);
  const at = TITRE_STEPS.indexOf(step as (typeof TITRE_STEPS)[number]);
  let three: Json | null = null;
  if (at >= 1) {
    const resolved = threeResolved(s);
    const picked = s.picks.map((p) => String(p.key));
    three = {
      by: { id: 'augustin_de_roncourt', name_fr: 'Gus', role_fr: 'consultant' },
      headlines: HEAD_ORDER.map((index, position) => {
        const headline = HEADLINES[index];
        const key = HEAD_KEYS[position];
        const open = resolved || (picked.includes(key) && headline.role !== 'honest');
        return {
          key,
          text: tr(headline.text[k], language),
          role: open ? headline.role : null,
          why: open && headline.why ? tr(headline.why, language) : null,
          claim: open && headline.why ? ctx.claim(headline.claim_id) : null,
        };
      }),
      tries: s.picks.length,
      max_tries: MAX_TRIES,
      picked,
      resolved,
      correct: resolved ? s.picks.some((p) => p.correct) : null,
      solution: resolved ? HEAD_KEYS[HEAD_ORDER.indexOf(HEADLINES.indexOf(honest()))] : null,
    };
  }
  let trap: Json | null = null;
  if (at >= 2) {
    const text = exaggerated().text[k];
    const resolved = trapResolved(s);
    const last = s.traps[s.traps.length - 1];
    const correct = s.traps.some((p) => p.correct);
    trap = {
      headline: tr(text, language),
      words: wordsOf(text.fr).map((fr, index) => ({ index, fr })),
      tries: s.traps.length,
      max_tries: MAX_TRIES,
      picked: last ? last.words : [],
      fine: last && !correct ? last.fine : [],
      resolved,
      correct: resolved ? correct : null,
      solution: resolved ? wrongSpan(text.fr) : [],
      why: resolved && exaggerated().why ? tr(exaggerated().why as T, language) : null,
      claim: resolved ? ctx.claim(exaggerated().claim_id) : null,
    };
  }
  let build: Json | null = null;
  if (at >= 3) {
    const input = buildInput(band);
    const proof = titreProof(s);
    build = {
      input,
      phrase: tr(TITRE_PHRASE[k], language),
      subjects: input === 'tiles' ? BUILD.subjects.map((row) => tr(row, language)) : [],
      facts: input === 'tiles' ? BUILD.facts.map((row) => tr(row, language)) : [],
      frame: input === 'frame' ? tr(BUILD.frame, language) : null,
      max_words: MAX_WORDS,
      avoid_fr: WRONG_FR,
      learner_fr: s.build ? s.build.learner_fr : null,
      draft_fr: proof ? proof.draft : null,
      proof: proof ? proof.proof : null,
      marks: proof ? marksWire(proof.marks, language, Boolean(ctx.pourquoi), Boolean(ctx.regle)) : [],
      tries: proof ? proof.tries : 0,
      max_tries: FIX_TRIES,
      printed_fr: proof ? proof.printed : null,
    };
    const notes = proof ? notesWire(titreRounds(s), proof.proof, language, ctx.lead.fr, Boolean(ctx.pourquoi), Boolean(ctx.regle)) : [];
    if (notes.length) build.notes = notes;
  }
  return { step, steps: [...TITRE_STEPS], band: k, title_fr: ctx.titleFr, read: read(ctx), three, trap, build };
}

/** Romy's edit of a headline (the comptoir mock's table, no final stop). */
/**
 * The headline's own slips the counter's table does not know (seen in the mock, 2026-11-21: «La
 * fête est gratuit pour les musicien amateurs» was printed «relu par Romy»): the agreement of an
 * adjective after «est», a plural noun after «les».
 */
const HEADLINE_EDITS: Array<[RegExp, (word: string) => string]> = [
  [/(\b(?:fête|musique|place)\s+est\s+)(gratuit|ouvert|grand|petit)\b/gi, (word) => `${word}e`],
  [/(\bles\s+)(musicien|voisin|habitant|candidat|élève)\b/gi, (word) => `${word}s`],
];

function edit(learner: string): { proof: string; target: string; marks: Json[] } {
  const out = proofread(learner);
  const marks = [...out.marks];
  let target = out.target;
  for (const [pattern, fix] of HEADLINE_EDITS) {
    pattern.lastIndex = 0;
    let match = pattern.exec(learner);
    while (match) {
      const start = match.index + match[1].length;
      const span = match[2];
      if (!marks.some((m) => start < Number(m.start) + String(m.span_fr).length && Number(m.start) < start + span.length)) {
        marks.push({ span_fr: span, start, kind: 'accord', fix_fr: fix(span) });
      }
      match = pattern.exec(learner);
    }
    target = target.replace(pattern, (_whole: string, keep: string, word: string) => keep + fix(word));
  }
  marks.sort((a, b) => Number(a.start) - Number(b.start));
  return { proof: marks.length ? 'marked' : 'clean', target: headlineText(target), marks };
}

function headlineProblem(text: string, ctx: RubriqueContext): Json | null {
  const count = wordCount(text);
  if (count < MIN_WORDS) return { code: 'too_short', count: MIN_WORDS };
  if (count > MAX_WORDS) return { code: 'too_long', count: MAX_WORDS };
  if (contains(text, WRONG_FR)) return { code: 'says_too_much' };
  const known = numbers(ctx.claimsFr.join(' '));
  if (Array.from(numbers(text)).some((n) => !known.has(n))) return { code: 'number_not_in_claims' };
  return null;
}

/** One act (WIRE §11.2): mutates `s`; returns the reason for an act the learner can fix on the same screen. */
export function applyTitreAct(s: MockTitreState, body: Json, ctx: RubriqueContext): Json | null {
  const { band } = ctx;
  const k = bandKey(band);
  const act = String(body.act || '');
  const step = titreStepOf(s, ctx.closed);
  const outOfOrder = () => ctx.fail(409, { code: 'revue_titre_out_of_order', step, act });
  const bad = () => ctx.fail(422, { code: 'revue_titre_bad_act', act });
  if (ctx.closed) throw outOfOrder();
  if (act === 'open') {
    s.opened = true;
    return null;
  }
  if (act === 'pick') {
    const key = String(body.key || '');
    const position = HEAD_KEYS.indexOf(key);
    if (position < 0) throw bad();
    if (threeResolved(s) || s.picks.some((p) => p.key === key)) return null;
    if (!s.opened) throw outOfOrder();
    const headline = HEADLINES[HEAD_ORDER[position]];
    s.picks.push({ key, role: headline.role, correct: headline.role === 'honest' });
    return null;
  }
  if (act === 'trap') {
    const text = exaggerated().text[k].fr;
    const picked: number[] = Array.from(new Set<number>((Array.isArray(body.words) ? body.words : []).map(Number))).sort((a, b) => a - b);
    if (!picked.length) return { code: 'pick_words' };
    if (picked.some((i) => i < 0 || i >= wordsOf(text).length)) throw bad();
    if (trapResolved(s) || (s.traps.length && s.traps[s.traps.length - 1].words.join() === picked.join())) return null;
    if (!threeResolved(s)) throw outOfOrder();
    const span = wrongSpan(text);
    const words = wordsOf(text);
    const fine = picked.filter((i) => !span.includes(i));
    const meaningful = span.filter((i) => !TRAP_STOP.has(fold(words[i])));
    s.traps.push({ words: picked, fine, correct: picked.length > 0 && !fine.length && picked.some((i) => meaningful.includes(i)) });
    return null;
  }
  if (act === 'build') {
    if (s.build) return null;
    if (!trapResolved(s)) throw outOfOrder();
    const input = buildInput(band);
    if (input === 'tiles') {
      const parts: number[] = Array.isArray(body.parts) ? body.parts.map(Number) : [];
      if (parts.length !== 2 || !BUILD.subjects[parts[0]] || !BUILD.facts[parts[1]]) return { code: 'pick_tiles' };
      const learner = headlineText(`${BUILD.subjects[parts[0]].fr} ${BUILD.facts[parts[1]].fr}`);
      s.build = { learner_fr: learner, typed_fr: '', proof: 'clean', target_fr: learner, marks: [] };
      return null;
    }
    const typed = String(body.text || '').replace(/\s+/g, ' ').trim();
    let learner = headlineText(typed);
    if (input === 'frame') {
      const head = BUILD.frame.fr;
      learner = fold(learner).startsWith(fold(head)) ? learner.charAt(0).toUpperCase() + learner.slice(1) : headlineText(`${head} ${learner}`);
    }
    const problem = headlineProblem(learner, ctx);
    if (problem) return problem;
    const check = edit(learner);
    s.build = { learner_fr: learner, typed_fr: typed, proof: check.proof, target_fr: check.target, marks: check.marks };
    return null;
  }
  if (act === 'build_fix') {
    const proof = titreProof(s);
    if (!proof) throw outOfOrder();
    if (proof.proof !== 'marked') return null;
    if (body.value === 'romy') {
      if (proof.tries < 1) throw outOfOrder();
      s.fixes.push({ by: 'romy', proof: 'corrected', target_fr: proof.target });
      return null;
    }
    const learner = headlineText(String(body.text || ''));
    const problem = headlineProblem(learner, ctx);
    if (problem) return problem;
    if (proofKey(learner) === proofKey(proof.draft)) return { code: 'nothing_changed' };
    const tries = proof.tries + 1;
    if (proofKey(learner) === proofKey(proof.target)) {
      s.fixes.push({ text_fr: learner, typed_fr: learner, proof: 'fixed', target_fr: proof.target });
      return null;
    }
    const again = edit(learner);
    const next = again.proof === 'clean' ? 'fixed' : tries >= FIX_TRIES ? 'corrected' : 'marked';
    s.fixes.push({ text_fr: learner, typed_fr: learner, proof: next, target_fr: again.target, marks: next === 'marked' ? again.marks : [] });
    return null;
  }
  throw bad();
}

/** «La page» of «Le titre» (no model call): the headline must be settled. */
export function titreClose(s: MockTitreState, ctx: RubriqueContext): { page: Json; dispatch: Json; printed: string; own: string; proof: string } {
  const proof = titreProof(s);
  if (!proof || proof.proof === 'marked') throw ctx.fail(409, { code: 'revue_titre_out_of_order', step: titreStepOf(s, false), act: 'close' });
  const k = bandKey(ctx.band);
  const printed = String(proof.printed || '');
  const own = [s.build?.typed_fr, ...s.fixes.map((fix) => fix.typed_fr)].filter(Boolean).join(' ');
  const page = {
    headline_fr: printed,
    proof: proof.proof,
    dateline_fr: ctx.datelineFr,
    lead_fr: ctx.lead.fr,
    honest_fr: honest().text[k].fr,
    phrase_fr: TITRE_PHRASE[k].fr,
    words: [],
  };
  const dispatch = {
    kicker_fr: 'Le titre de Romy',
    headline_fr: printed,
    body_fr: [ctx.lead.fr],
    contribution: [],
    byline_fr: `Romy Tremblay, avec toi · d'après ${ctx.sources.map((src) => String(src.name)).join(' et ')}`,
    sources: ctx.sources,
  };
  return { page, dispatch, printed, own, proof: proof.proof };
}

// --- «L'intox express» ------------------------------------------------------------------

export type MockIntoxState = { opened: boolean; answers: Record<string, Json>; fixes: Record<string, Json[]> };
export const newIntoxState = (): MockIntoxState => ({ opened: false, answers: {}, fixes: {} });

const statementAt = (key: string) => STATEMENTS[CARD_ORDER[CARD_KEYS.indexOf(key)]];
const falseKeys = () => CARD_KEYS.filter((key) => !statementAt(key).true);
const currentKey = (s: MockIntoxState) => CARD_KEYS.find((key) => !s.answers[key]) ?? null;
const fixResolved = (s: MockIntoxState, key: string) => (s.fixes[key] || []).some((row) => row.correct) || (s.fixes[key] || []).length >= MAX_TRIES;
const fixInput = (band: Band) => (band === 'A1' || band === 'A2' ? 'pick' : 'write');
const optionsFor = (statement: Statement, key: string) =>
  key.charCodeAt(0) % 2 ? [statement.right_fr as string, statement.distractor_fr as string] : [statement.distractor_fr as string, statement.right_fr as string];
const quoteOf = (statement: Statement) => ({ quote_fr: statement.quote_fr, settles_fr: statement.settles_fr, source_name: statement.source_name });

export function intoxStepOf(s: MockIntoxState, closed: boolean): string {
  if (closed) return 'page';
  if (!s.opened) return 'read';
  if (currentKey(s)) return 'round';
  if (!falseKeys().every((key) => fixResolved(s, key))) return 'fix';
  return 'page';
}

/** A B1+ correction is right when it says the right words and no longer the false ones. */
const writtenRight = (text: string, statement: Statement) =>
  contains(text, statement.right_fr || '') && !contains(text, statement.wrong_fr || '');

export function intoxView(s: MockIntoxState, ctx: RubriqueContext): Json {
  const { band, language } = ctx;
  const k = bandKey(band);
  const step = intoxStepOf(s, ctx.closed);
  const at = INTOX_STEPS.indexOf(step as (typeof INTOX_STEPS)[number]);
  let round: Json | null = null;
  if (at >= 1) {
    const cards = CARD_KEYS.map((key) => {
      const statement = statementAt(key);
      const answer = s.answers[key];
      const card: Json = { key, text: tr(statement.text[k], language), answer: null, true: null, correct: null, why: null, quote: null, wrong_fr: null };
      if (answer) {
        Object.assign(card, {
          answer: answer.value,
          true: statement.true,
          correct: answer.correct,
          why: tr(statement.why, language),
          quote: !statement.true || !answer.correct ? quoteOf(statement) : null,
          wrong_fr: statement.wrong_fr,
        });
      }
      return card;
    });
    const answered = Object.keys(s.answers).length;
    const score = Object.values(s.answers).filter((row) => row.correct).length;
    round = { cards, current: currentKey(s), score, answered, total: CARD_KEYS.length };
  }
  let fix: Json | null = null;
  if (at >= 2) {
    const input = fixInput(band);
    fix = {
      input,
      phrase: tr(INTOX_PHRASE[k], language),
      items: falseKeys().map((key) => {
        const statement = statementAt(key);
        const rows = s.fixes[key] || [];
        const resolved = fixResolved(s, key);
        return {
          key,
          text: tr(statement.text[k], language),
          wrong_fr: statement.wrong_fr,
          options: input === 'pick' ? optionsFor(statement, key) : [],
          quote: quoteOf(statement),
          tries: rows.length,
          max_tries: MAX_TRIES,
          attempts: rows.map((row) => String(row.value || row.text || '')),
          resolved,
          correct: resolved ? rows.some((row) => row.correct) : null,
          right_fr: resolved ? statement.right_fr : null,
          fixed: resolved && statement.fixed ? tr(statement.fixed[k], language) : null,
        };
      }),
    };
  }
  return { step, steps: [...INTOX_STEPS], band: k, title_fr: ctx.titleFr, read: read(ctx), round, fix };
}

export function applyIntoxAct(s: MockIntoxState, body: Json, ctx: RubriqueContext): Json | null {
  const act = String(body.act || '');
  const step = intoxStepOf(s, ctx.closed);
  const outOfOrder = () => ctx.fail(409, { code: 'revue_intox_out_of_order', step, act });
  const bad = () => ctx.fail(422, { code: 'revue_intox_bad_act', act });
  if (ctx.closed) throw outOfOrder();
  if (act === 'open') {
    s.opened = true;
    return null;
  }
  if (act === 'answer') {
    const key = String(body.key || '');
    const value = String(body.value || '');
    if (!CARD_KEYS.includes(key) || (value !== 'vrai' && value !== 'faux')) throw bad();
    if (s.answers[key]) return null;
    if (!s.opened || key !== currentKey(s)) throw outOfOrder();
    s.answers[key] = { value, correct: (value === 'vrai') === statementAt(key).true };
    return null;
  }
  if (act === 'fix') {
    const key = String(body.key || '');
    if (!falseKeys().includes(key)) throw bad();
    if (currentKey(s)) throw outOfOrder();
    if (fixResolved(s, key)) return null;
    const statement = statementAt(key);
    const rows = (s.fixes[key] = s.fixes[key] || []);
    if (fixInput(ctx.band) === 'pick') {
      const value = String(body.value || '');
      if (!optionsFor(statement, key).includes(value)) throw bad();
      if (rows.some((row) => row.value === value)) return null;
      rows.push({ value, correct: value === statement.right_fr });
      return null;
    }
    const text = String(body.text || '').replace(/\s+/g, ' ').trim();
    if (wordCount(text) < WRITE_MIN_WORDS) return { code: 'too_short', count: WRITE_MIN_WORDS };
    rows.push({ text, correct: writtenRight(text, statement) });
    return null;
  }
  throw bad();
}

/** «La page» of «L'intox express» (no model call): both corrections settled. */
export function intoxClose(s: MockIntoxState, ctx: RubriqueContext): { page: Json; dispatch: Json; own: string } {
  if (intoxStepOf(s, false) !== 'page') throw ctx.fail(409, { code: 'revue_intox_out_of_order', step: intoxStepOf(s, false), act: 'close' });
  const k = bandKey(ctx.band);
  const lines = CARD_KEYS.map((key) => {
    const statement = statementAt(key);
    const rows = s.fixes[key] || [];
    const right = rows.find((row) => row.correct);
    return {
      text_fr: statement.fixed ? statement.fixed[k].fr : statement.text[k].fr,
      was_false: !statement.true,
      wrong_fr: statement.wrong_fr,
      answered_right: Boolean(s.answers[key]?.correct),
      learner_fr: right && right.text ? String(right.text) : null,
      fixed_right: statement.true ? null : Boolean(right),
    };
  });
  const score = Object.values(s.answers).filter((row) => row.correct).length;
  const own = lines.map((line) => line.learner_fr).filter(Boolean).join(' ');
  const page = {
    title_fr: ctx.titleFr,
    dateline_fr: ctx.datelineFr,
    lines,
    score,
    total: CARD_KEYS.length,
    fixed: lines.filter((line) => line.fixed_right).length,
    phrase_fr: INTOX_PHRASE[k].fr,
    words: [],
  };
  const dispatch = {
    kicker_fr: "L'intox express de Romy",
    headline_fr: ctx.titleFr,
    body_fr: lines.map((line) => line.text_fr),
    contribution: [],
    byline_fr: `${own ? 'Romy Tremblay, avec toi' : 'Romy Tremblay'} · d'après ${ctx.sources.map((src) => String(src.name)).join(' et ')}`,
    sources: ctx.sources,
  };
  return { page, dispatch, own };
}
