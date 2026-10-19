/**
 * «Au comptoir» in the DEV-ONLY mock (`/revue?mock=1&comptoir=1`, `lib/revue-mock.ts`).
 *
 * The Céline story's takes — written by the takes desk (claude-haiku-5-5, 2026-10-19
 * comparison run) and checked by hand: no «mon cher» to the learner, Romy never answers
 * the learner as if they were Gus — and the learner's loop scripted with the same replay
 * rules as `app/services/revue/comptoir_loop.py`: the step follows from the acts, nothing
 * is sent before its step, two tries at the intox, Romy's edit by a small table (the
 * backend's fake provider's), the guest's last word by chip. Wire JSON (snake_case) in
 * and out, so the page runs through the real parsers.
 */

type Json = Record<string, any>;
type Lang = 'en' | 'de' | 'fr';
type Band = 'A1' | 'A2' | 'B1' | 'B2';
type T = { fr: string; en: string; de: string };
type Stance = 'pour' | 'contre' | 'nuance';

const t = (fr: string, en: string, de: string): T => ({ fr, en, de });

export const STANCES: Stance[] = ['pour', 'contre', 'nuance'];
const STEPS = ['read', 'takes', 'intox', 'opinion', 'page'] as const;
const MAX_TRIES = 2;

export const COMPTOIR_NAME_FR: Record<string, string> = {
  romy_tremblay: 'Romy',
  augustin_de_roncourt: 'Gus',
  margaux_barman: 'Margaux',
  lila_bonnet: 'Lila',
  marin_leveque: 'Marin',
  landlord_marchand: 'M. Marchand',
};
const ROLE_FR: Record<string, string> = {
  romy_tremblay: 'journaliste',
  augustin_de_roncourt: 'consultant',
  margaux_barman: 'Le Mistral',
  lila_bonnet: 'prof',
  marin_leveque: 'ONG',
  landlord_marchand: 'propriétaire',
};

export type MockTakes = {
  question: T;
  guests: Array<{ id: string; stance: Stance; take: { a1: T; a2: T; b1: T }; quote: T }>;
  intox: { by: string; wrong_fr: string; right_fr: string; claim_id: string; distractor_fr: string; ask: T; caught: T; bands: string[] } | null;
  reasons: Record<Stance, T[]>;
  frames: Record<Stance, T>;
  bank: T[];
  phrase: { a1: T; a2: T; b1: T; b2: T };
  replies: Record<Stance, { by: string; line: T; comeback: T }>;
};

/** Céline Dion's last Paris concert (the desk prompt's own story), at the counter. */
export const CELINE_TAKES: MockTakes = {
  question: t('Céline revient en mai 2027 : ça te plaît ?', 'Céline is back in May 2027: do you like that?', 'Céline kommt im Mai 2027 zurück: Gefällt dir das?'),
  guests: [
    {
      id: 'romy_tremblay',
      stance: 'pour',
      take: {
        a1: t("Je suis pour ! Voyons donc, c'est une bonne nouvelle.", "I'm for it! Come on, it's good news.", 'Ich bin dafür! Ach komm, das ist eine gute Nachricht.'),
        a2: t(
          "Voyons donc, c'est une bonne nouvelle ! Je veux être là en mai 2027. Gus, tu vas encore bouder ?",
          "Come on, that's good news! I want to be there in May 2027. Gus, are you going to sulk again?",
          'Ach komm, das ist eine gute Nachricht! Ich will im Mai 2027 dabei sein. Gus, schmollst du wieder?',
        ),
        b1: t(
          'Je suis pour, parce que plus de 500 000 personnes ont prouvé que Paris aime vraiment la chanteuse. Mais Gus va bouder, je le sais.',
          "I'm for it, because more than 500,000 people proved that Paris really loves the singer. But Gus will sulk, I know it.",
          'Ich bin dafür, weil mehr als 500 000 Menschen bewiesen haben, dass Paris die Sängerin wirklich liebt. Aber Gus wird schmollen, das weiß ich.',
        ),
      },
      quote: t('Bonne nouvelle, voyons donc !', 'Good news, come on!', 'Gute Nachricht, ach komm!'),
    },
    {
      id: 'lila_bonnet',
      stance: 'nuance',
      take: {
        a1: t('Ça dépend, mon chou. Mes élèves chantent Céline à la récré.', 'It depends, sweetheart. My pupils sing Céline at break time.', 'Kommt drauf an, mein Schatz. Meine Schüler singen Céline in der Pause.'),
        a2: t(
          "Ça dépend, mon chou ! Un concert, c'est bien, mais pas trop. Gus, arrête de faire la tête.",
          'It depends, sweetheart! A concert is good, but not too much. Gus, stop sulking.',
          'Kommt drauf an, mein Schatz! Ein Konzert ist schön, aber nicht zu oft. Gus, hör auf zu schmollen.',
        ),
        b1: t(
          "Ça dépend : d'un côté, mes élèves dansent sur les chansons de Céline, et de l'autre, ils ne dorment plus. Romy, tu es trop sérieuse, mon chou.",
          "It depends: on the one hand, my pupils dance to Céline's songs; on the other, they don't sleep anymore. Romy, you're too serious, sweetheart.",
          'Kommt drauf an: Einerseits tanzen meine Schüler zu Célines Liedern, andererseits schlafen sie nicht mehr. Romy, du bist zu ernst, mein Schatz.',
        ),
      },
      quote: t("Un concert, c'est bien, mais pas trop.", 'A concert is fine, but not too much.', 'Ein Konzert ist schön, aber nicht zu oft.'),
    },
    {
      id: 'augustin_de_roncourt',
      stance: 'contre',
      take: {
        a1: t("Je suis contre. Fini, le 12 octobre ! J'aime le calme.", "I'm against it. Over, on 12 October! I like calm.", 'Ich bin dagegen. Vorbei, am 12. Oktober! Ich mag die Ruhe.'),
        a2: t(
          'Le dernier concert, le 12 octobre ? Trop de bruit pour moi. Je préfère mon canapé et le calme.',
          'The last concert, on 12 October? Too much noise for me. I prefer my sofa and calm.',
          'Das letzte Konzert, am 12. Oktober? Zu viel Lärm für mich. Ich bevorzuge mein Sofa und die Ruhe.',
        ),
        b1: t(
          "Je suis contre, parce que le dernier concert, le 12 octobre, a fini dans une foule énorme. Laisse-moi t'expliquer la vie : je préfère le silence.",
          'I\'m against it, because the last concert, on 12 October, ended in a huge crowd. Let me explain life to you: I prefer silence.',
          'Ich bin dagegen, weil das letzte Konzert am 12. Oktober in einer riesigen Menge endete. Lass mich dir das Leben erklären: Ich ziehe die Stille vor.',
        ),
      },
      quote: t('Le silence, toujours.', 'Silence, always.', 'Stille, immer.'),
    },
  ],
  intox: {
    by: 'augustin_de_roncourt',
    wrong_fr: 'le 12 octobre',
    right_fr: 'le 17 octobre',
    claim_id: 'c1',
    distractor_fr: 'en mai 2027',
    ask: t('Quelle date, en vrai ?', 'Which date, really?', 'Welches Datum, wirklich?'),
    caught: t('Le 17, le 12… Un vrai artiste ne compte pas les jours.', 'The 17th, the 12th… A true artist doesn\'t count the days.', 'Der 17., der 12.… Ein echter Künstler zählt die Tage nicht.'),
    bands: ['a1', 'a2', 'b1'],
  },
  reasons: {
    pour: [
      t('sa voix est belle', 'her voice is beautiful', 'ihre Stimme ist schön'),
      t('les fans sont heureux', 'the fans are happy', 'die Fans sind glücklich'),
      t('Paris aime la chanteuse', 'Paris loves the singer', 'Paris liebt die Sängerin'),
    ],
    contre: [
      t('les billets coûtent trop', 'the tickets cost too much', 'die Karten kosten zu viel'),
      t('la foule me fatigue', 'crowds tire me out', 'die Menge macht mich müde'),
      t('le bruit me gêne', 'the noise bothers me', 'der Lärm stört mich'),
    ],
    nuance: [
      t("c'est bien, mais pas trop", "it's good, but not too much", 'es ist gut, aber nicht zu viel'),
      t('ça dépend des billets', 'it depends on the tickets', 'es kommt auf die Karten an'),
      t("une fois, c'est bien", 'once is fine', 'einmal ist gut'),
    ],
  },
  frames: {
    pour: t("À mon avis, c'est une bonne nouvelle, parce que", "In my opinion, it's good news, because", 'Meiner Meinung nach ist das eine gute Nachricht, weil'),
    contre: t("À mon avis, ce n'est pas une bonne nouvelle, parce que", "In my opinion, it's not good news, because", 'Meiner Meinung nach ist das keine gute Nachricht, weil'),
    nuance: t('À mon avis, ça dépend, parce que', 'In my opinion, it depends, because', 'Meiner Meinung nach kommt es darauf an, weil'),
  },
  bank: [
    t('sa voix', 'her voice', 'ihre Stimme'),
    t('les billets', 'the tickets', 'die Karten'),
    t('la foule', 'the crowd', 'die Menge'),
    t('le bruit', 'the noise', 'der Lärm'),
    t('trop cher', 'too expensive', 'zu teuer'),
    t('revenir', 'to come back', 'zurückkommen'),
  ],
  phrase: {
    a1: t('Je suis pour… / Je suis contre…', "I'm for… / I'm against…", 'Ich bin dafür… / Ich bin dagegen…'),
    a2: t('À mon avis…, parce que…', 'In my opinion…, because…', 'Meiner Meinung nach…, weil…'),
    b1: t("Je ne suis pas d'accord avec…, parce que…", "I don't agree with…, because…", 'Ich bin nicht einverstanden mit…, weil…'),
    b2: t('Certes…, mais…', 'Admittedly…, but…', 'Zwar…, aber…'),
  },
  replies: {
    pour: {
      by: 'augustin_de_roncourt',
      line: t(
        'Une foule énorme en mai ? Tu rêves ! Moi, je reste chez moi avec mon champagne.',
        'A huge crowd in May? Dream on! I stay home with my champagne.',
        'Eine riesige Menge im Mai? Träum weiter! Ich bleibe mit meinem Champagner zu Hause.',
      ),
      comeback: t("Toi, tu n'as jamais vu une vraie fête !", "You've never seen a real party!", 'Du hast noch nie ein echtes Fest gesehen!'),
    },
    contre: {
      by: 'romy_tremblay',
      line: t('Voyons donc ! Tu as peur de la foule ? Ou du bruit ?', 'Come on! Are you scared of the crowd? Or the noise?', 'Ach komm! Hast du Angst vor der Menge? Oder vor dem Lärm?'),
      comeback: t('Non, mais les billets sont trop chers !', 'No, but the tickets are too expensive!', 'Nein, aber die Karten sind zu teuer!'),
    },
    nuance: {
      by: 'augustin_de_roncourt',
      line: t("Ça dépend ? Les indécis n'ont jamais de champagne. Décide-toi !", 'It depends? The undecided never get champagne. Make up your mind!', 'Kommt drauf an? Unentschlossene bekommen nie Champagner. Entscheide dich!'),
      comeback: t('Le champagne attendra, Gus !', 'The champagne can wait, Gus!', 'Der Champagner kann warten, Gus!'),
    },
  },
};

const A1_OPENERS: Record<Stance, string> = { pour: 'Je suis pour', contre: 'Je suis contre', nuance: 'Ça dépend' };
const COMEBACK_CHIPS: T[] = [t('Pas du tout !', 'Not at all!', 'Überhaupt nicht!'), t('Un peu…', 'A little…', 'Ein bisschen…')];
const LAST_WORDS: Record<string, T> = {
  0: t('Ah bon ? On en reparle demain !', "Really? We'll talk about it again tomorrow!", 'Ach ja? Darüber reden wir morgen weiter!'),
  1: t('Ha ! Je le savais.', 'Ha! I knew it.', 'Ha! Ich wusste es.'),
  2: t('Touché.', 'Touché.', 'Touché.'),
  free: t('Touché. On en reparle demain !', "Touché. We'll talk about it again tomorrow!", 'Touché. Darüber reden wir morgen weiter!'),
};
/** The backend fake provider's edit table (`encounter._FAKE_EDITS`), plus the mock page's «sa voix est très beau». */
const EDITS: Array<[RegExp, string, Record<Lang, string>]> = [
  [/\b[Ll]e gens\b/g, 'les gens', { en: 'plural: les gens', de: 'Plural: les gens', fr: 'pluriel : les gens' }],
  [/\bsont content\b/g, 'sont contents', { en: 'agreement: plural', de: 'Angleichung: Plural', fr: 'accord : pluriel' }],
  [/\bvoix est (tr[eè]s )?beau\b/g, 'voix est $1belle', { en: '«la voix» is feminine', de: '«la voix» ist feminin', fr: '« la voix » est féminin' }],
  [/\btres\b/g, 'très', { en: 'accent', de: 'Akzent', fr: 'accent' }],
  [/\ba Paris\b/g, 'à Paris', { en: 'accent: à', de: 'Akzent: à', fr: 'accent : à' }],
];

export type MockComptoirState = {
  vote: Stance | null;
  reactions: Record<string, 'agree' | 'disagree'>;
  tries: string[];
  found: boolean;
  fix: Json | null;
  opinion: Json | null;
  comeback: Json | null;
};

export function newComptoirState(): MockComptoirState {
  return { vote: null, reactions: {}, tries: [], found: false, fix: null, opinion: null, comeback: null };
}

/** What the view needs from the session around it. */
export type ComptoirContext = {
  takes: MockTakes;
  band: Band;
  language: Lang;
  sessionId: string;
  closed: boolean;
  datelineFr: string;
  lead: T | { fr: string };
  sources: Json[];
  claim: (id: string) => Json | null;
  fail: (status: number, detail: unknown) => Error;
};

const key = (band: Band) => (band === 'A1' ? 'a1' : band === 'A2' ? 'a2' : 'b1') as 'a1' | 'a2' | 'b1';
const tr = (text: T | { fr: string } | null | undefined, language: Lang): Json => {
  if (!text) return { fr: '', tr: null };
  return { fr: text.fr, tr: language === 'fr' ? null : (text as T)[language] ?? null };
};
const typography = (text: string) => text.replace(/\s*([?!;:])/g, ' $1').replace(/\s+/g, ' ').trim();
const sentenceEnd = (text: string) => {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean && !/[.!?…»]$/.test(clean) ? `${clean}.` : clean;
};
const fold = (text: string) =>
  text
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’`]/g, "'")
    .toLowerCase();
const sentences = (text: string) => text.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g)?.map((s) => s.trim()).filter(Boolean) ?? [text];
const words = (text: string) => (text.match(/[A-Za-zÀ-ÖØ-öø-ÿŒœ\d]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*/g) || []).length;

export function intoxFor(takes: MockTakes, band: Band) {
  return takes.intox && takes.intox.bands.includes(key(band)) ? takes.intox : null;
}

export function stepsFor(takes: MockTakes, band: Band): string[] {
  return STEPS.filter((step) => step !== 'intox' || intoxFor(takes, band) !== null);
}

export function stepOf(state: MockComptoirState, takes: MockTakes, band: Band, closed: boolean): string {
  if (closed) return 'page';
  if (!state.vote) return 'read';
  if (Object.keys(state.reactions).length < takes.guests.length) return 'takes';
  if (intoxFor(takes, band) && !state.fix) return 'intox';
  if (!state.opinion || !state.comeback) return 'opinion';
  return 'page';
}

const whoResolved = (state: MockComptoirState) => state.found || state.tries.length >= MAX_TRIES;

function compactQuote(take: string, planted: string | null): string {
  const rows = sentences(take);
  let index = rows.findIndex((row) => planted && fold(row).includes(fold(planted)));
  if (index < 0) index = Math.max(0, rows.findIndex((row) => words(row) >= 4));
  let quote = rows[index];
  if (words(quote) < 6 && index + 1 < rows.length) quote = `${quote} ${rows[index + 1]}`;
  return quote;
}

function options(intox: NonNullable<MockTakes['intox']>, seed: string): string[] {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash % 2 ? [intox.distractor_fr, intox.right_fr] : [intox.right_fr, intox.distractor_fr];
}

function gradeFix(intox: NonNullable<MockTakes['intox']>, body: Json): boolean {
  if (typeof body.value === 'string') return fold(body.value).replace(/[ .!]+$/, '') === fold(intox.right_fr);
  const text = fold(String(body.text || ''));
  const cut = text.lastIndexOf(', pas ');
  const head = cut > 0 ? text.slice(0, cut) : text;
  const digits = (value: string) => new Set(value.match(/\d+/g) || []);
  const right = digits(intox.right_fr);
  if (right.size) {
    const said = digits(head);
    return Array.from(right).every((n) => said.has(n)) && !Array.from(digits(intox.wrong_fr)).some((n) => said.has(n) && !right.has(n));
  }
  return head.includes(fold(intox.right_fr).replace(/^(le|la|les|l') /, ''));
}

const quoteOf = (takes: MockTakes, id: string, text: string) => {
  const guest = takes.guests.find((g) => g.id === id);
  return { cast_id: id, name_fr: COMPTOIR_NAME_FR[id] ?? id, role_fr: ROLE_FR[id] ?? '', stance: guest?.stance ?? 'nuance', quote_fr: text };
};

export function comptoirView(state: MockComptoirState, ctx: ComptoirContext): Json {
  const { takes, band, language } = ctx;
  const step = stepOf(state, takes, band, ctx.closed);
  const order = STEPS.indexOf(step as (typeof STEPS)[number]);
  const intox = intoxFor(takes, band);
  const lower = band === 'A1' || band === 'A2';
  const reacted = Object.keys(state.reactions).length >= takes.guests.length;
  let intoxView: Json | null = null;
  if (intox && reacted && order >= STEPS.indexOf('intox')) {
    const resolved = whoResolved(state);
    const liar = COMPTOIR_NAME_FR[intox.by];
    intoxView = {
      quotes: takes.guests.map((g) => quoteOf(takes, g.id, compactQuote(g.take[key(band)].fr, g.id === intox.by ? intox.wrong_fr : null))),
      tries: state.tries,
      resolved,
      found: resolved ? state.found : null,
      by: resolved ? intox.by : null,
      hint_claim: state.tries.some((id) => id !== intox.by) ? ctx.claim(intox.claim_id) : null,
      ask: resolved ? tr(intox.ask, language) : null,
      options: resolved && lower ? options(intox, ctx.sessionId) : [],
      prefill_fr: resolved && !lower ? typography(`C'est faux, ${liar} ! C'est …, pas ${intox.wrong_fr}.`) : null,
      fix: state.fix
        ? {
            correct: Boolean(state.fix.correct),
            answer_fr: String(state.fix.answer_fr || ''),
            line_fr: typography(`C'est faux, ${liar} ! C'est ${intox.right_fr}, pas ${intox.wrong_fr}.`),
            wrong_fr: intox.wrong_fr,
            right_fr: intox.right_fr,
            claim: ctx.claim(intox.claim_id),
            caught: tr(intox.caught, language),
          }
        : null,
    };
  }
  const opponents = Object.fromEntries(STANCES.map((stance) => [stance, takes.replies[stance].by]));
  const kit =
    order >= STEPS.indexOf('opinion')
      ? {
          input: band === 'A1' ? 'tiles' : band === 'A2' ? 'frame' : 'free',
          phrase: tr(takes.phrase[band === 'B2' ? 'b2' : key(band)], language),
          reasons: Object.fromEntries(STANCES.map((stance) => [stance, takes.reasons[stance].map((row) => tr(row, language))])),
          frames: Object.fromEntries(STANCES.map((stance) => [stance, tr(takes.frames[stance], language)])),
          bank: band === 'A2' ? takes.bank.map((row) => tr(row, language)) : [],
          opponents,
        }
      : null;
  let opinion: Json | null = null;
  if (state.opinion) {
    const stance = state.opinion.stance as Stance;
    const reply = state.opinion.reply as { by: string } & T;
    opinion = {
      stance,
      learner_fr: state.opinion.learner_fr,
      edited_fr: state.opinion.edited_fr,
      notes: state.opinion.notes,
      reply: { by: reply.by, name_fr: COMPTOIR_NAME_FR[reply.by] ?? reply.by, line: tr(reply, language) },
      comebacks: lower ? [...COMEBACK_CHIPS, takes.replies[stance].comeback].map((row) => tr(row, language)) : [],
      comeback: state.comeback
        ? { text_fr: state.comeback.text_fr, index: state.comeback.index ?? null, last_word: tr(state.comeback.last_word, language) }
        : null,
    };
  }
  return {
    step,
    steps: stepsFor(takes, band),
    band: key(band),
    question: tr(takes.question, language),
    read: { dateline_fr: ctx.datelineFr, lead: tr(ctx.lead, language), sources: ctx.sources.slice(0, 1) },
    cast: takes.guests.map((g) => ({
      id: g.id,
      name_fr: COMPTOIR_NAME_FR[g.id] ?? g.id,
      role_fr: ROLE_FR[g.id] ?? '',
      stance: g.stance,
      take: tr(g.take[key(band)], language),
      reaction: state.reactions[g.id] ?? null,
    })),
    has_intox: intox !== null,
    vote: state.vote,
    intox: intoxView,
    kit,
    opinion,
  };
}

function edit(text: string, language: Lang): { edited: string; notes: Json[] } {
  let out = text;
  const notes: Json[] = [];
  for (const [pattern, fixed, why] of EDITS) {
    if (!pattern.test(out)) continue;
    pattern.lastIndex = 0;
    out = out.replace(pattern, fixed);
    if (notes.length < 2) notes.push({ span_fr: fixed.replace('$1', ''), why: why[language] });
  }
  out = out.charAt(0).toUpperCase() + out.slice(1);
  return { edited: typography(sentenceEnd(out)), notes };
}

/** One act (WIRE §9.3): mutates `state`; returns `error_fr` for an act the learner can fix on the same screen. */
export function applyComptoirAct(state: MockComptoirState, body: Json, ctx: ComptoirContext): string | null {
  const { takes, band } = ctx;
  const act = String(body.act || '');
  const step = stepOf(state, takes, band, ctx.closed);
  const outOfOrder = () => ctx.fail(409, { code: 'revue_comptoir_out_of_order', step, act });
  const bad = () => ctx.fail(422, { code: 'revue_comptoir_bad_act', act });
  if (ctx.closed) throw outOfOrder();
  const intox = intoxFor(takes, band);
  if (act === 'vote') {
    if (!STANCES.includes(body.value)) throw bad();
    if (state.opinion) throw outOfOrder();
    state.vote = body.value;
    return null;
  }
  if (act === 'react') {
    const index = takes.guests.findIndex((g) => g.id === body.guest_id);
    if (index < 0 || (body.value !== 'agree' && body.value !== 'disagree')) throw bad();
    if (!state.vote || state.opinion || takes.guests.slice(0, index).some((g) => !state.reactions[g.id])) throw outOfOrder();
    state.reactions[body.guest_id] = body.value;
    return null;
  }
  if (act === 'intox_who') {
    if (!takes.guests.some((g) => g.id === body.guest_id)) throw bad();
    if (step !== 'intox' || !intox || whoResolved(state)) throw outOfOrder();
    state.tries.push(body.guest_id);
    state.found = state.found || body.guest_id === intox.by;
    return null;
  }
  if (act === 'intox_fix') {
    if (state.fix) return null;
    if (step !== 'intox' || !intox || !whoResolved(state)) throw outOfOrder();
    const lower = band === 'A1' || band === 'A2';
    if (lower && !options(intox, ctx.sessionId).includes(body.value)) throw bad();
    const text = String(body.text || '').trim();
    if (!lower && (!text || text.includes('…'))) return 'Complète la phrase : c’est quoi, en vrai ?';
    state.fix = { correct: gradeFix(intox, lower ? { value: body.value } : { text }), answer_fr: lower ? body.value : text };
    return null;
  }
  if (act === 'opinion') {
    if (state.opinion) return null;
    if (step !== 'opinion') throw outOfOrder();
    const stance = (STANCES.includes(body.value) ? body.value : state.vote) as Stance;
    let learner = '';
    if (band === 'A1') {
      const reasons = takes.reasons[stance];
      if (typeof body.reason_index !== 'number' || !reasons[body.reason_index]) return 'Choisis une raison.';
      const reason = reasons[body.reason_index].fr;
      const parce = /^[aeiouyàâéèêîôû]/i.test(reason) ? `parce qu'${reason}` : `parce que ${reason}`;
      learner = typography(`${A1_OPENERS[stance]}, ${parce}.`);
    } else {
      const text = String(body.text || '').replace(/\s+/g, ' ').trim();
      if (!text) return 'Écris ta raison : quelques mots suffisent.';
      if (band === 'A2') {
        const frame = takes.frames[stance].fr;
        learner = fold(text).startsWith(fold(frame).slice(0, 12)) ? sentenceEnd(text) : sentenceEnd(`${frame} ${text}`);
      } else {
        learner = sentenceEnd(text);
      }
    }
    const desk = takes.replies[stance];
    const fixed = band === 'A1' ? { edited: learner, notes: [] } : edit(learner, ctx.language);
    state.vote = state.vote ?? stance;
    state.opinion = { stance, learner_fr: learner, edited_fr: fixed.edited, notes: fixed.notes, reply: { by: desk.by, ...desk.line } };
    return null;
  }
  if (act === 'comeback') {
    if (state.comeback) return null;
    if (!state.opinion) throw outOfOrder();
    const stance = state.opinion.stance as Stance;
    if (band === 'A1' || band === 'A2') {
      const chips = [...COMEBACK_CHIPS, takes.replies[stance].comeback];
      if (typeof body.index !== 'number' || !chips[body.index]) throw bad();
      state.comeback = { text_fr: chips[body.index].fr, index: body.index, last_word: LAST_WORDS[body.index] };
    } else {
      const text = String(body.text || '').trim();
      if (!text) return 'Écris une phrase pour répondre.';
      state.comeback = { text_fr: sentenceEnd(text), index: null, last_word: LAST_WORDS.free };
    }
    return null;
  }
  throw bad();
}

/** «La page» and the dispatch (spec §3 step 5): no model call; the opinion must be given. */
export function comptoirClose(state: MockComptoirState, ctx: ComptoirContext & { lead: { fr: string }; kicker?: string; words: string[] }): { page: Json; dispatch: Json } {
  const { takes, band } = ctx;
  if (!state.opinion) throw ctx.fail(409, { code: 'revue_comptoir_out_of_order', step: stepOf(state, takes, band, false), act: 'close' });
  const stance = state.opinion.stance as Stance;
  const intox = intoxFor(takes, band);
  const votes: Record<Stance, number> = { pour: 0, contre: 0, nuance: 0 };
  for (const g of takes.guests) votes[g.stance] += 1;
  votes[stance] += 1;
  const standfirst = sentences(ctx.lead.fr)[0] ?? ctx.lead.fr;
  const claim = intox ? ctx.claim(intox.claim_id) : null;
  const edited = String(state.opinion.edited_fr);
  const page = {
    question_fr: takes.question.fr,
    dateline_fr: ctx.datelineFr,
    standfirst_fr: standfirst,
    quotes: takes.guests.map((g) => quoteOf(takes, g.id, g.quote.fr)),
    mine: { cast_id: 'user', name_fr: 'Toi', role_fr: '', stance, quote_fr: edited },
    votes,
    intox: intox && state.fix
      ? { by: intox.by, name_fr: COMPTOIR_NAME_FR[intox.by], wrong_fr: intox.wrong_fr, right_fr: intox.right_fr, source_name: String(claim?.source?.name ?? '') }
      : null,
    phrase_fr: takes.phrase[band === 'B2' ? 'b2' : key(band)].fr,
    words: ctx.words,
  };
  const dispatch = {
    kicker_fr: 'Le micro-trottoir de Romy',
    headline_fr: takes.question.fr,
    body_fr: [standfirst, `Toi : « ${edited} »`],
    contribution: [],
    byline_fr: `Romy Tremblay, avec toi · d'après ${ctx.sources.map((s) => String(s.name)).join(' et ')}`,
    sources: ctx.sources,
  };
  return { page, dispatch };
}

export const COMPTOIR_CLOSE_LINE = 'Merci ! Ta voix est dans le micro-trottoir.';

/** The Céline story's picture in the mock: the concept page's drawn concert (a stand-in for the morning's print). */
export const CELINE_PICTURE_URL =
  "data:image/svg+xml,%3Csvg viewBox=%220 0 320 180%22 xmlns=%22http://www.w3.org/2000/svg%22 role=%22img%22 aria-label=%22Illustration: a singer on stage in front of a crowd holding up phone lights%22%3E %3Crect width=%22320%22 height=%22180%22 fill=%22#1b2a5c%22/%3E %3Cg fill=%22#f5efe1%22 opacity=%22.7%22%3E%3Ccircle cx=%2222%22 cy=%2218%22 r=%221.2%22/%3E%3Ccircle cx=%2248%22 cy=%2240%22 r=%221%22/%3E%3Ccircle cx=%22290%22 cy=%2222%22 r=%221.3%22/%3E%3Ccircle cx=%22270%22 cy=%2252%22 r=%221%22/%3E%3Ccircle cx=%22300%22 cy=%2270%22 r=%221%22/%3E%3Ccircle cx=%2234%22 cy=%2270%22 r=%221%22/%3E%3C/g%3E %3Cpath d=%22M28 118 L38 52 L41 52 L44 30 L46 30 L49 52 L52 52 L62 118 Z M36 92 L54 92 L52 86 L38 86 Z%22 fill=%22#14204a%22/%3E %3Cpolygon points=%2296,0 112,0 176,118 128,118%22 fill=%22#f3c318%22 opacity=%22.22%22/%3E %3Cpolygon points=%22210,0 226,0 196,118 146,118%22 fill=%22#f3c318%22 opacity=%22.22%22/%3E %3Ccircle cx=%22160%22 cy=%2284%22 r=%2234%22 fill=%22#f3c318%22 opacity=%22.22%22/%3E %3Crect x=%220%22 y=%22118%22 width=%22320%22 height=%2210%22 fill=%22#14110d%22/%3E %3Crect x=%220%22 y=%22128%22 width=%22320%22 height=%223%22 fill=%22#d8321a%22/%3E %3Cpath d=%22M151 80 Q160 76 169 80 L180 118 L140 118 Z%22 fill=%22#f5efe1%22/%3E %3Crect x=%22157.5%22 y=%2274%22 width=%225%22 height=%227%22 fill=%22#e3b48c%22/%3E %3Ccircle cx=%22160%22 cy=%2269%22 r=%227%22 fill=%22#e3b48c%22/%3E %3Cpath d=%22M152.5 70 Q153 60 160 60.5 Q168 60 168 70 Q166 64 160 64 Q154 64 152.5 70 Z%22 fill=%22#5a3420%22/%3E %3Cpath d=%22M168 82 L176 74%22 stroke=%22#e3b48c%22 stroke-width=%223%22 stroke-linecap=%22round%22/%3E %3Crect x=%22173%22 y=%2270%22 width=%223%22 height=%227%22 rx=%221.2%22 fill=%22#14110d%22 transform=%22rotate(35 174 73)%22/%3E %3Cg fill=%22#14110d%22%3E %3Ccircle cx=%2218%22 cy=%22152%22 r=%229%22/%3E%3Ccircle cx=%2244%22 cy=%22148%22 r=%229%22/%3E%3Ccircle cx=%2272%22 cy=%22154%22 r=%229%22/%3E%3Ccircle cx=%2298%22 cy=%22149%22 r=%229%22/%3E%3Ccircle cx=%22126%22 cy=%22153%22 r=%229%22/%3E%3Ccircle cx=%22152%22 cy=%22148%22 r=%229%22/%3E%3Ccircle cx=%22180%22 cy=%22153%22 r=%229%22/%3E%3Ccircle cx=%22206%22 cy=%22149%22 r=%229%22/%3E%3Ccircle cx=%22234%22 cy=%22154%22 r=%229%22/%3E%3Ccircle cx=%22260%22 cy=%22148%22 r=%229%22/%3E%3Ccircle cx=%22288%22 cy=%22153%22 r=%229%22/%3E%3Ccircle cx=%22312%22 cy=%22149%22 r=%229%22/%3E %3Crect x=%220%22 y=%22160%22 width=%22320%22 height=%2220%22/%3E %3C/g%3E %3Cg stroke=%22#14110d%22 stroke-width=%225%22 stroke-linecap=%22round%22%3E%3Cpath d=%22M50 150 L58 128%22/%3E%3Cpath d=%22M146 150 L138 130%22/%3E%3Cpath d=%22M212 152 L222 131%22/%3E%3Cpath d=%22M266 150 L274 129%22/%3E%3Cpath d=%22M104 151 L98 132%22/%3E%3C/g%3E %3Cg fill=%22#f3c318%22%3E%3Crect x=%2256%22 y=%22122%22 width=%225%22 height=%228%22 rx=%221%22/%3E%3Crect x=%22135%22 y=%22124%22 width=%225%22 height=%228%22 rx=%221%22/%3E%3Crect x=%22220%22 y=%22125%22 width=%225%22 height=%228%22 rx=%221%22/%3E%3Crect x=%22272%22 y=%22123%22 width=%225%22 height=%228%22 rx=%221%22/%3E%3Crect x=%2295%22 y=%22126%22 width=%225%22 height=%228%22 rx=%221%22/%3E%3C/g%3E %3C/svg%3E";
