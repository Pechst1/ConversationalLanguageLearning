/**
 * «Le fil» in the DEV-ONLY mock (`/revue?mock=1&fil=1`, `lib/revue-mock.ts`).
 *
 * The wire of «Le bac» transcribed from `app/services/revue/evergreen/fil/evergreen-bac.json`
 * and the learner's loop scripted with the replay rules of `app/services/revue/fil_loop.py`:
 * the step follows from the acts; the order graded with the first strip out of place and
 * never the solution before the second try; the sequence words placed (A1) or chosen (A2+)
 * with the missed word's gloss; the telling from tiles (A1, correct by construction), the
 * two frames (A2) or free with two sequence words (B1+); from A2 Romy marks by the comptoir
 * mock's small table and the learner fixes (with «Le pourquoi» when `&pourquoi=1`); «La
 * page» at the close. The shuffles are fixed (the server's are per session): the mock is a
 * screen to look at, not a second implementation. Wire JSON in and out.
 */

import { marksWire, notesWire, proofread } from './revue-mock-comptoir';

type Json = Record<string, any>;
type Lang = 'en' | 'de' | 'fr';
type Band = 'A1' | 'A2' | 'B1' | 'B2';
type T = { fr: string; en: string; de: string };
type Role = 'first' | 'middle' | 'last';

const t = (fr: string, en: string, de: string): T => ({ fr, en, de });
const STEPS = ['read', 'order', 'words', 'tell', 'page'] as const;
const KEYS = ['a', 'b', 'c', 'd'] as const;
const MAX_TRIES = 2;
const FIX_TRIES = 2;
const A2_PART_MIN_WORDS = 2;
const A2_MIN_WORDS = 5;
const FREE_MIN_WORDS = 12;
const FREE_MIN_CONNECTORS = 2;
const ROLES: Role[] = ['first', 'middle', 'middle', 'last'];

export const FIL_CLOSE_LINE = 'Merci ! Le fil est remis en ordre, et ton récit est dans le journal.';
export const FIL_KICKER = 'Le fil de Romy';

type Strip = { a1: T; a2: T; b1: T; label: T; tile: T };
const STRIPS: Strip[] = [
  {
    a1: t('Le baccalauréat naît en 1808.', 'The baccalauréat is born in 1808.', 'Das Abitur entsteht 1808.'),
    a2: t('Le baccalauréat est créé en 1808.', 'The baccalauréat is created in 1808.', 'Das Abitur wird 1808 geschaffen.'),
    b1: t(
      "Le baccalauréat, l'examen de la fin du lycée, est créé en 1808.",
      'The baccalauréat, the exam at the end of secondary school, is created in 1808.',
      'Das Abitur, die Prüfung am Ende des Gymnasiums, wird 1808 geschaffen.',
    ),
    label: t('la création', 'the creation', 'die Gründung'),
    tile: t('le baccalauréat naît en 1808', 'the baccalauréat is born in 1808', 'das Abitur entsteht 1808'),
  },
  {
    a1: t('Les élèves passent le premier bac en 1809.', 'Pupils sit the first bac in 1809.', 'Schüler legen 1809 das erste Abitur ab.'),
    a2: t('Le premier bac a lieu en 1809.', 'The first bac takes place in 1809.', 'Das erste Abitur findet 1809 statt.'),
    b1: t(
      "En 1809, les premiers candidats passent l'examen du baccalauréat.",
      'In 1809, the first candidates sit the baccalauréat exam.',
      '1809 legen die ersten Kandidaten die Abiturprüfung ab.',
    ),
    label: t('le premier examen', 'the first exam', 'die erste Prüfung'),
    tile: t('les élèves passent le premier bac en 1809', 'pupils sit the first bac in 1809', 'Schüler legen 1809 das erste Abitur ab'),
  },
  {
    a1: t('En 2023, 95,7 % des candidats réussissent le bac.', 'In 2023, 95.7% of candidates pass the bac.', '2023 bestehen 95,7 % der Kandidaten das Abitur.'),
    a2: t('En 2023, le taux de réussite au bac est de 95,7 %.', 'In 2023, the bac pass rate is 95.7%.', '2023 liegt die Erfolgsquote beim Abitur bei 95,7 %.'),
    b1: t(
      'En 2023, le taux de réussite au bac atteint 95,7 %, contre 75,5 % en 1990.',
      'In 2023, the bac pass rate reaches 95.7%, against 75.5% in 1990.',
      '2023 erreicht die Erfolgsquote beim Abitur 95,7 %, gegenüber 75,5 % im Jahr 1990.',
    ),
    label: t('la réussite', 'the pass rate', 'die Erfolgsquote'),
    tile: t('le taux de réussite atteint 95,7 %', 'the pass rate reaches 95.7%', 'die Erfolgsquote erreicht 95,7 %'),
  },
  {
    a1: t('En 2027, le Grand oral compte moins.', 'In 2027, the Grand oral counts for less.', '2027 zählt das Grand oral weniger.'),
    a2: t('En 2027, le coefficient du Grand oral passe de 10 à 8.', 'In 2027, the weighting of the Grand oral goes from 10 to 8.', '2027 sinkt die Gewichtung des Grand oral von 10 auf 8.'),
    b1: t(
      'À partir de 2027, le coefficient du Grand oral passe de 10 à 8 pour le bac général.',
      'From 2027, the weighting of the Grand oral goes from 10 to 8 for the general bac.',
      'Ab 2027 sinkt die Gewichtung des Grand oral im allgemeinen Abitur von 10 auf 8.',
    ),
    label: t('le changement', 'the change', 'die Änderung'),
    tile: t('le Grand oral compte moins en 2027', 'the Grand oral counts for less in 2027', 'das Grand oral zählt 2027 weniger'),
  },
];

type Connector = T & { role: Role };
const c = (fr: string, en: string, de: string, role: Role): Connector => ({ fr, en, de, role });
const CONNECTORS: Record<'a1' | 'a2' | 'b1', Connector[]> = {
  a1: [c("d'abord", 'first', 'zuerst', 'first'), c('ensuite', 'next', 'danach', 'middle'), c('puis', 'then', 'dann', 'middle'), c('enfin', 'finally', 'schließlich', 'last')],
  a2: [
    c("d'abord", 'first', 'zuerst', 'first'),
    c('au début', 'at the start', 'am Anfang', 'first'),
    c('ensuite', 'next', 'danach', 'middle'),
    c('puis', 'then', 'dann', 'middle'),
    c('après', 'after that', 'nachher', 'middle'),
    c('enfin', 'finally', 'schließlich', 'last'),
    c('finalement', 'in the end', 'am Ende', 'last'),
  ],
  b1: [
    c("tout d'abord", 'first of all', 'zunächst', 'first'),
    c('au départ', 'at the outset', 'anfangs', 'first'),
    c('par la suite', 'later on', 'in der Folge', 'middle'),
    c('ensuite', 'next', 'danach', 'middle'),
    c('puis', 'then', 'dann', 'middle'),
    c('en fin de compte', 'in the end', 'letzten Endes', 'last'),
    c('pour finir', 'to finish', 'zum Schluss', 'last'),
    c('finalement', 'in the end', 'am Ende', 'last'),
  ],
};
const FRAMES: T[] = [t("D'abord, le baccalauréat", 'First, the baccalauréat', 'Zuerst das Abitur'), t('Enfin, le Grand oral', 'Finally, the Grand oral', 'Schließlich das Grand oral')];
const PHRASE: Record<'a1' | 'a2' | 'b1', T> = {
  a1: t("D'abord…, ensuite…", 'First…, next…', 'Zuerst…, danach…'),
  a2: t("D'abord…, puis…, enfin…", 'First…, then…, finally…', 'Zuerst…, dann…, schließlich…'),
  b1: t("Tout d'abord…, par la suite…, en fin de compte…", 'First of all…, later on…, in the end…', 'Zunächst…, in der Folge…, letzten Endes…'),
};
/** The order the strips are shown in (true indices): fixed here, never already in order. */
const SHOWN = [2, 0, 3, 1];
/** A1's four words as the chips show them (never already in order). */
const CHIPS = ['enfin', 'd-abord', 'ensuite', 'puis'];
/** From A2: three words per strip, one per role. */
const OPTIONS: Record<'a2' | 'b1', string[][]> = {
  a2: [
    ['ensuite', 'au-debut', 'finalement'],
    ['enfin', 'puis', 'd-abord'],
    ['au-debut', 'finalement', 'apres'],
    ['ensuite', 'enfin', 'd-abord'],
  ],
  b1: [
    ['par-la-suite', 'tout-d-abord', 'pour-finir'],
    ['en-fin-de-compte', 'puis', 'au-depart'],
    ['au-depart', 'ensuite', 'finalement'],
    ['tout-d-abord', 'en-fin-de-compte', 'par-la-suite'],
  ],
};

export type MockFilState = { opened: boolean; orders: Json[]; words: Json[]; tell: Json | null; fixes: Json[] };
export function newFilState(): MockFilState {
  return { opened: false, orders: [], words: [], tell: null, fixes: [] };
}

export type FilContext = {
  band: Band;
  language: Lang;
  closed: boolean;
  titleFr: string;
  datelineFr: string;
  lead: { fr: string; tr: string | null };
  sources: Json[];
  fail: (status: number, detail: unknown) => Error;
  pourquoi?: boolean;
  /** «La règle» (`&regle=1`): the marks name their grammar concept. */
  regle?: boolean;
};

const bandKey = (band: Band) => (band === 'A1' ? 'a1' : band === 'A2' ? 'a2' : 'b1') as 'a1' | 'a2' | 'b1';
const tr = (text: T, language: Lang) => ({ fr: text.fr, tr: language === 'fr' ? null : text[language] });
const fold = (text: string) => text.normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[’`]/g, "'").toLowerCase();
const idOf = (fr: string) => fold(fr).replace(/[^a-z]+/g, '-').replace(/^-|-$/g, '');
const cap = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
const typography = (text: string) => text.replace(/\s*([?!;:])/g, ' $1').replace(/\s+/g, ' ').trim();
const sentenceEnd = (text: string) => {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean && !/[.!?…»]$/.test(clean) ? `${clean}.` : clean;
};
const wordCount = (text: string) => (text.match(/[A-Za-zÀ-ÖØ-öø-ÿŒœ\d]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*/g) || []).length;
const proofKey = (text: string) => {
  const flat = text.normalize('NFC').replace(/[’`]/g, "'").replace(/[^A-Za-zÀ-ÖØ-öø-ÿŒœ0-9']+/g, ' ').trim();
  return flat.charAt(0).toLowerCase() + flat.slice(1);
};

/** True index → the letter it is shown under. */
const keyOf = (index: number) => KEYS[SHOWN.indexOf(index)];
const indexOf = (key: string) => SHOWN[KEYS.indexOf(key as (typeof KEYS)[number])];
const rows = (band: Band) => {
  const out = new Map<string, Connector>();
  for (const row of [...CONNECTORS[bandKey(band)], ...CONNECTORS.a2, ...CONNECTORS.b1, ...CONNECTORS.a1]) if (!out.has(idOf(row.fr))) out.set(idOf(row.fr), row);
  return out;
};
const place = (band: Band) => band === 'A1';
const solutionWords = (band: Band): string[] => {
  const byId = rows(band);
  if (place(band)) {
    const out: string[] = [];
    for (const role of ROLES) out.push(CHIPS.find((id) => byId.get(id)?.role === role && !out.includes(id)) as string);
    return out;
  }
  return OPTIONS[bandKey(band) as 'a2' | 'b1'].map((options, p) => options.find((id) => byId.get(id)?.role === ROLES[p]) as string);
};

const orderResolved = (s: MockFilState) => s.orders.some((row) => row.correct) || s.orders.length >= MAX_TRIES;
const wordsResolved = (s: MockFilState) => s.words.some((row) => row.correct) || s.words.length >= MAX_TRIES;
const proofOf = (s: MockFilState) => {
  if (!s.tell) return null;
  const latest = s.fixes.length ? s.fixes[s.fixes.length - 1] : s.tell;
  const texts = s.fixes.filter((fix) => fix.text_fr).map((fix) => String(fix.text_fr));
  const draft = texts.length ? texts[texts.length - 1] : String(s.tell.learner_fr);
  const proof = String(latest.proof);
  const target = String(latest.target_fr || '');
  const printed = proof === 'marked' ? null : proof === 'as_written' ? typography(sentenceEnd(draft)) : target || typography(sentenceEnd(draft));
  return { proof, draft, marks: proof === 'marked' ? (latest.marks as Json[]) : [], tries: texts.length, target, printed };
};
const rounds = (s: MockFilState): Json[][] =>
  [s.tell, ...s.fixes].filter((row): row is Json => Boolean(row) && row?.proof === 'marked' && Array.isArray(row?.marks)).map((row) => row.marks);

export function filStepOf(s: MockFilState, closed: boolean): string {
  if (closed) return 'page';
  if (!s.opened) return 'read';
  if (!orderResolved(s)) return 'order';
  if (!wordsResolved(s)) return 'words';
  const proof = proofOf(s);
  if (!proof || proof.proof === 'marked') return 'tell';
  return 'page';
}

const connectorView = (row: Connector, language: Lang, open: boolean) => ({
  id: idOf(row.fr),
  fr: row.fr,
  tr: open && language !== 'fr' ? row[language] : null,
  role: open ? row.role : null,
});
const tellInput = (band: Band) => (band === 'A1' ? 'tiles' : band === 'A2' ? 'frames' : 'free');

export function filView(s: MockFilState, ctx: FilContext): Json {
  const { band, language } = ctx;
  const step = filStepOf(s, ctx.closed);
  const at = STEPS.indexOf(step as (typeof STEPS)[number]);
  const k = bandKey(band);
  let order: Json | null = null;
  if (at >= 1) {
    const last = s.orders[s.orders.length - 1];
    const resolved = orderResolved(s);
    const correct = s.orders.some((row) => row.correct);
    order = {
      strips: SHOWN.map((index) => ({ key: keyOf(index), text: tr(STRIPS[index][k], language), label: tr(STRIPS[index].label, language) })),
      tries: s.orders.length,
      max_tries: MAX_TRIES,
      placed: last ? last.order : [],
      hint: last && last.hint && !correct ? last.hint : null,
      resolved,
      correct: resolved ? correct : null,
      solution: resolved ? [0, 1, 2, 3].map(keyOf) : [],
    };
  }
  let words: Json | null = null;
  if (at >= 2) {
    const byId = rows(band);
    const resolved = wordsResolved(s);
    const last = s.words[s.words.length - 1];
    const ids = place(band) ? CHIPS : Array.from(new Set(OPTIONS[k as 'a2' | 'b1'].flat()));
    words = {
      input: place(band) ? 'place' : 'choose',
      strips: STRIPS.map((strip) => tr(strip[k], language)),
      connectors: ids.map((id) => connectorView(byId.get(id) as Connector, language, resolved)),
      options: place(band) ? [] : OPTIONS[k as 'a2' | 'b1'],
      tries: s.words.length,
      max_tries: MAX_TRIES,
      picked: last ? last.picks : [],
      misses:
        last && !last.correct
          ? (last.misses as Json[]).map((miss) => {
              const row = byId.get(miss.id) as Connector;
              return { ...miss, fr: row.fr, tr: language === 'fr' ? null : row[language] };
            })
          : [],
      resolved,
      correct: resolved ? s.words.some((row) => row.correct) : null,
      solution: resolved ? solutionWords(band) : [],
    };
  }
  let tell: Json | null = null;
  if (at >= 3) {
    const input = tellInput(band);
    const proof = proofOf(s);
    tell = {
      input,
      phrase: tr(PHRASE[k], language),
      tiles: input === 'tiles' ? [0, 1, 2, 3].map((index) => ({ key: keyOf(index), text: tr(STRIPS[index].tile, language) })) : [],
      connectors: CONNECTORS[k].map((row) => connectorView(row, language, true)),
      frames: input === 'frames' ? FRAMES.map((frame) => tr(frame, language)) : [],
      min_words: input === 'frames' ? A2_MIN_WORDS : input === 'free' ? FREE_MIN_WORDS : 0,
      min_connectors: input === 'free' ? FREE_MIN_CONNECTORS : 0,
      learner_fr: s.tell ? s.tell.learner_fr : null,
      draft_fr: proof ? proof.draft : null,
      proof: proof ? proof.proof : null,
      marks: proof ? marksWire(proof.marks, language, Boolean(ctx.pourquoi), Boolean(ctx.regle)) : [],
      tries: proof ? proof.tries : 0,
      max_tries: FIX_TRIES,
      printed_fr: proof ? proof.printed : null,
    };
    const notes = proof ? notesWire(rounds(s), proof.proof, language, STRIPS.map((strip) => strip[k].fr).join(' '), Boolean(ctx.pourquoi), Boolean(ctx.regle)) : [];
    if (notes.length) tell.notes = notes;
  }
  return {
    step,
    steps: [...STEPS],
    band: k,
    title_fr: ctx.titleFr,
    read: { dateline_fr: ctx.datelineFr, lead: ctx.lead, sources: ctx.sources.slice(0, 1) },
    order,
    words,
    tell,
  };
}

/** The distinct sequence words `text` uses (any band's; «tout d'abord» counts once). */
export function filConnectorsUsed(text: string): string[] {
  const folded = ` ${fold(text)} `;
  const seen: string[] = [];
  for (const row of [...CONNECTORS.b1, ...CONNECTORS.a2, ...CONNECTORS.a1]) {
    const word = fold(row.fr);
    if (!seen.includes(word) && new RegExp(`(?<![\\p{L}-])${word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\p{L}-])`, 'u').test(folded)) seen.push(word);
  }
  return seen.filter((w) => !seen.some((other) => other !== w && other.includes(w)));
}

function check(learner: string): { proof: string; target: string; marks: Json[] } {
  const out = proofread(learner);
  return { proof: out.marks.length ? 'marked' : 'clean', target: out.target, marks: out.marks };
}

/** One act (WIRE §10.3): mutates `s`; returns the reason for an act the learner can fix on the same screen. */
export function applyFilAct(s: MockFilState, body: Json, ctx: FilContext): Json | null {
  const { band } = ctx;
  const act = String(body.act || '');
  const step = filStepOf(s, ctx.closed);
  const outOfOrder = () => ctx.fail(409, { code: 'revue_fil_out_of_order', step, act });
  const bad = () => ctx.fail(422, { code: 'revue_fil_bad_act', act });
  if (ctx.closed) throw outOfOrder();
  const byId = rows(band);
  if (act === 'open') {
    s.opened = true;
    return null;
  }
  if (act === 'order') {
    const keys: string[] = Array.isArray(body.order) ? body.order.map(String) : [];
    if ([...keys].sort().join() !== KEYS.join()) throw bad();
    const last = s.orders[s.orders.length - 1];
    if (orderResolved(s) || (last && last.order.join() === keys.join())) return null;
    if (!s.opened) throw outOfOrder();
    const truth = keys.map(indexOf);
    const slot = truth.findIndex((index, at) => index !== at);
    s.orders.push(slot < 0 ? { order: keys, correct: true, hint: null } : { order: keys, correct: false, hint: { key: keys[slot], after_key: keyOf(slot) } });
    return null;
  }
  if (act === 'words') {
    const picks: string[] = Array.isArray(body.picks) ? body.picks.map(String) : [];
    const last = s.words[s.words.length - 1];
    if (wordsResolved(s) || (last && last.picks.join() === picks.join())) return null;
    if (!orderResolved(s)) throw outOfOrder();
    if (picks.length !== 4 || picks.some((id) => !id)) return { code: 'pick_all' };
    const allowed = place(band) ? [...picks].sort().join() === [...CHIPS].sort().join() : picks.every((id, p) => OPTIONS[bandKey(band) as 'a2' | 'b1'][p].includes(id));
    if (!allowed) throw bad();
    const misses = picks
      .map((id, position) => ({ position, id, role: (byId.get(id) as Connector).role, needs: ROLES[position] }))
      .filter((miss) => miss.role !== miss.needs);
    s.words.push({ picks, correct: !misses.length, misses });
    return null;
  }
  if (act === 'tell') {
    if (s.tell) return null;
    if (!wordsResolved(s)) throw outOfOrder();
    const input = tellInput(band);
    let learner = '';
    let typed = '';
    let proof = { proof: 'clean', target: '', marks: [] as Json[] };
    if (input === 'tiles') {
      const parts: string[] = Array.isArray(body.parts) ? body.parts.map(String) : [];
      const first = byId.get(parts[0]);
      const second = byId.get(parts[2]);
      if (parts.length !== 4 || !first || !second || !KEYS.includes(parts[1] as never) || !KEYS.includes(parts[3] as never)) return { code: 'tell_pick_all' };
      const one = indexOf(parts[1]);
      const two = indexOf(parts[3]);
      if (one === two) return { code: 'tell_same', key: parts[1] };
      if (one > two) return { code: 'tell_order', key: parts[1], after_key: parts[3] };
      if (first.role === 'last') return { code: 'tell_last_first', key: parts[0] };
      if (first.role === 'middle' && one === 0) return { code: 'tell_starts_middle', key: parts[0] };
      if (second.role === 'first') return { code: 'tell_first_second', key: parts[2] };
      learner = typography(`${cap(first.fr)}, ${STRIPS[one].tile.fr}. ${cap(second.fr)}, ${STRIPS[two].tile.fr}.`);
      proof = { proof: 'clean', target: learner, marks: [] };
    } else if (input === 'frames') {
      const texts: string[] = (Array.isArray(body.texts) ? body.texts : []).map((row: unknown) => String(row || '').replace(/\s+/g, ' ').trim());
      const counts = texts.map(wordCount);
      if (counts.length !== 2 || Math.min(...counts) < A2_PART_MIN_WORDS || counts[0] + counts[1] < A2_MIN_WORDS) return { code: 'too_short', count: A2_MIN_WORDS };
      typed = texts.join(' ');
      learner = typography(
        FRAMES.map((frame, i) => {
          const text = texts[i].replace(/[ .!…]+$/, '');
          return fold(text).startsWith(fold(frame.fr).slice(0, 10)) ? `${cap(text)}.` : `${frame.fr} ${text}.`;
        }).join(' '),
      );
      proof = check(learner);
    } else {
      typed = String(body.text || '').replace(/\s+/g, ' ').trim();
      if (wordCount(typed) < FREE_MIN_WORDS) return { code: 'too_short', count: FREE_MIN_WORDS };
      if (filConnectorsUsed(typed).length < FREE_MIN_CONNECTORS) return { code: 'need_connectors', count: FREE_MIN_CONNECTORS };
      learner = sentenceEnd(typed);
      proof = check(learner);
    }
    s.tell = { learner_fr: learner, typed_fr: typed, proof: proof.proof, target_fr: proof.target, marks: proof.marks };
    return null;
  }
  if (act === 'tell_fix') {
    const proof = proofOf(s);
    if (!proof) throw outOfOrder();
    if (proof.proof !== 'marked') return null;
    if (body.value === 'romy') {
      if (proof.tries < 1) throw outOfOrder();
      s.fixes.push({ by: 'romy', proof: 'corrected', target_fr: proof.target });
      return null;
    }
    const text = String(body.text || '').replace(/\s+/g, ' ').trim();
    const floor = band === 'A2' ? A2_MIN_WORDS : FREE_MIN_WORDS;
    if (wordCount(text) < floor) return { code: 'too_short', count: floor };
    const learner = sentenceEnd(text);
    if (proofKey(learner) === proofKey(proof.draft)) return { code: 'nothing_changed' };
    const tries = proof.tries + 1;
    if (proofKey(learner) === proofKey(proof.target)) {
      s.fixes.push({ text_fr: learner, typed_fr: text, proof: 'fixed', target_fr: proof.target });
      return null;
    }
    const again = check(learner);
    const next = again.proof === 'clean' ? 'fixed' : tries >= FIX_TRIES ? 'corrected' : 'marked';
    s.fixes.push({ text_fr: learner, typed_fr: text, proof: next, target_fr: again.target, marks: next === 'marked' ? again.marks : [] });
    return null;
  }
  throw bad();
}

/** «La page» (no model call): the telling must be settled. */
export function filClose(s: MockFilState, ctx: FilContext): { page: Json; dispatch: Json; printed: string; own: string; proof: string } {
  const proof = proofOf(s);
  if (!proof || proof.proof === 'marked') throw ctx.fail(409, { code: 'revue_fil_out_of_order', step: filStepOf(s, false), act: 'close' });
  const k = bandKey(ctx.band);
  const byId = rows(ctx.band);
  const right = s.words.find((row) => row.correct);
  const ids: string[] = right ? right.picks : solutionWords(ctx.band);
  const texts = STRIPS.map((strip) => strip[k].fr);
  const printed = String(proof.printed || '');
  const own = [s.tell?.typed_fr, ...s.fixes.map((fix) => fix.typed_fr)].filter(Boolean).join(' ');
  const page = {
    title_fr: ctx.titleFr,
    dateline_fr: ctx.datelineFr,
    strips: ids.map((id, i) => ({ connector_fr: cap((byId.get(id) as Connector).fr), text_fr: texts[i] })),
    mine_fr: printed,
    proof: proof.proof,
    phrase_fr: PHRASE[k].fr,
    words: [],
  };
  const credited = own !== '' && fold(own).split(/\W+/).some((word) => word.length > 2 && fold(printed).includes(word));
  const dispatch = {
    kicker_fr: FIL_KICKER,
    headline_fr: ctx.titleFr,
    body_fr: [...texts, `Toi : « ${printed} »`],
    contribution: [],
    byline_fr: `${credited ? 'Romy Tremblay, avec toi' : 'Romy Tremblay'} · d'après ${ctx.sources.map((src) => String(src.name)).join(' et ')}`,
    sources: ctx.sources,
  };
  return { page, dispatch, printed, own, proof: proof.proof };
}
