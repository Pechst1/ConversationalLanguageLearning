/**
 * DEV ONLY · «Papier · les rendez-vous» in the scripted mock (`/revue?mock=1&rdv=1`,
 * `/revue/une?mock=1`): wraps the mock transport of `lib/revue-mock.ts` and answers the new
 * routes, everything else passes through untouched.
 *
 * «Trois mots» is built the server's way from the mock session's own close (its kept words,
 * then its vocabulary; the gap from a sentence of the story's summary that holds one of them);
 * the regular's line and the week's front page are canned and say so (`mock` in their ids).
 */

import { castDisplayName } from './cast-faces';
import type { RevueTransport } from './revue-api';

type Json = Record<string, any>;
type Mode = 'comptoir' | 'fil' | 'titre' | 'intox' | 'photo' | 'micro' | 'chat';

const KEYS = ['a', 'b', 'c'] as const;
const CUES = ['1', '2', '3'] as const;

function fold(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/’/g, "'").toLowerCase();
}
function bare(fr: string): string {
  const value = fr.trim();
  if (/^l['’]/i.test(value)) return value.slice(2);
  const [head, ...rest] = value.split(' ');
  return ['le', 'la', 'les', 'un', 'une', 'des', 'du'].includes(head.toLowerCase()) && rest.length ? rest.join(' ') : value;
}
function find(sentence: string, word: string): [number, number] | null {
  const re = new RegExp(`(?<![\\p{L}])${fold(word).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\p{L}])`, 'u');
  const m = re.exec(fold(sentence));
  return m ? [m.index, m.index + m[0].length] : null;
}

const LINES: Record<Mode, Json> = {
  comptoir: {
    template_id: 'mock.opinion.contre_moi',
    speaker_id: 'augustin_de_roncourt',
    speaker_fr: castDisplayName('augustin_de_roncourt'),
    fr: "La dernière fois, tu étais contre moi. Et aujourd'hui ?",
    en: 'Last time, you were against me. And today?',
    de: 'Letztes Mal warst du gegen mich. Und heute?',
    fact: 'stance',
  },
  titre: {
    template_id: 'mock.titre.honnete',
    speaker_id: 'romy_tremblay',
    speaker_fr: castDisplayName('romy_tremblay'),
    fr: 'Mardi, ton titre était honnête. Encore un ?',
    en: 'On Tuesday, your headline was honest. Another one?',
    de: 'Am Dienstag war deine Schlagzeile ehrlich. Noch eine?',
    fact: 'headline',
  },
  intox: {
    template_id: 'mock.intox.score',
    speaker_id: 'romy_tremblay',
    speaker_fr: castDisplayName('romy_tremblay'),
    fr: 'Hier, tu as trouvé 4 sur 5. On refait ?',
    en: 'Yesterday, you got 4 out of 5. Shall we go again?',
    de: 'Gestern hattest du 4 von 5. Noch einmal?',
    fact: 'intox_score',
  },
  fil: {
    template_id: 'mock.fil.encore',
    speaker_id: 'romy_tremblay',
    speaker_fr: castDisplayName('romy_tremblay'),
    fr: 'Hier, tu as raconté le fil. Encore un ?',
    en: 'Yesterday, you told the wire. Another one?',
    de: 'Gestern hast du die Meldungen erzählt. Noch einmal?',
    fact: 'fil',
  },
  photo: {
    template_id: 'mock.photo.apres_micro',
    speaker_id: 'romy_tremblay',
    speaker_fr: castDisplayName('romy_tremblay'),
    fr: 'Jeudi, tu as interviewé Lila. Aujourd’hui, une photo.',
    en: 'On Thursday, you interviewed Lila. Today, a photo.',
    de: 'Am Donnerstag hast du Lila interviewt. Heute ein Foto.',
    fact: 'micro',
  },
  micro: {
    template_id: 'mock.micro.apres_photo',
    speaker_id: 'romy_tremblay',
    speaker_fr: castDisplayName('romy_tremblay'),
    fr: 'Hier, ta légende était dans le journal. Aujourd’hui, prends le micro.',
    en: 'Yesterday, your caption was in the paper. Today, take the microphone.',
    de: 'Gestern war deine Bildunterschrift in der Zeitung. Heute nimmst du das Mikrofon.',
    fact: 'photo',
  },
  chat: {},
};

type Round = { words: Json[]; answer: Record<string, string>; cues: Json[]; gap: Json | null; matches: Json[]; gaps: Json[] };

function view(id: string, r: Round): Json {
  const matchDone = r.matches.some((m) => m.correct) || r.matches.length >= 2;
  const last = r.matches[r.matches.length - 1] ?? null;
  const gapDone = r.gaps.some((g) => g.correct) || r.gaps.length >= 2;
  const lastGap = r.gaps[r.gaps.length - 1] ?? null;
  const gap = r.gap
    ? {
        source: 'summary',
        before_fr: r.gap.before,
        after_fr: r.gap.after,
        tries: r.gaps.length,
        resolved: gapDone,
        correct: gapDone && lastGap ? lastGap.correct : null,
        miss: lastGap && !lastGap.correct ? { word_key: lastGap.word, gloss: r.words[KEYS.indexOf(lastGap.word)].gloss } : null,
        solution: gapDone ? KEYS[r.gap.index] : null,
        sentence_fr: gapDone ? r.gap.sentence : null,
      }
    : null;
  return {
    session_id: id,
    step: !matchDone ? 'match' : gap && !gapDone ? 'gap' : 'done',
    words: r.words.map((w, i) => ({ key: KEYS[i], fr: w.fr, bare_fr: bare(w.fr), gloss: matchDone ? w.gloss : null })),
    cues: r.cues,
    match: {
      tries: r.matches.length,
      resolved: matchDone,
      correct: matchDone && last ? last.correct : null,
      misses: last && !last.correct ? last.misses : [],
      solution: matchDone ? r.answer : null,
    },
    gap,
    kept_now: 0,
  };
}

function build(session: Json): Round | null {
  const closing = session.closing;
  if (!closing) return null;
  const seen = new Set<string>();
  const pool: Json[] = [];
  for (const w of [...(closing.kept?.words ?? []), ...(session.plan?.vocabulary ?? [])]) {
    const key = fold(bare(String(w.fr ?? '')));
    if (!w.fr || !w.gloss || seen.has(key)) continue;
    seen.add(key);
    pool.push({ fr: w.fr, gloss: w.gloss });
  }
  if (pool.length < 3) return null;
  const words = pool.slice(0, 3);
  let gap: Json | null = null;
  const sentences: string[] = String(session.dossier?.summary_fr ?? '').match(/[^.!?…]+[.!?…]*\s*/g) ?? [];
  for (const sentence of sentences.map((s) => s.trim())) {
    for (let i = 0; i < 3 && !gap; i += 1) {
      const span = find(sentence, bare(words[i].fr));
      if (span && words.every((w, j) => j === i || !find(sentence, bare(w.fr)))) {
        gap = { index: i, before: sentence.slice(0, span[0]), after: sentence.slice(span[1]), sentence };
      }
    }
    if (gap) break;
  }
  const order = [1, 2, 0];
  const answer: Record<string, string> = {};
  const cues = order.map((wordIndex, position) => {
    answer[KEYS[wordIndex]] = CUES[position];
    return { key: CUES[position], kind: 'gloss', text: words[wordIndex].gloss, picture: null };
  });
  return { words, answer, cues, gap, matches: [], gaps: [] };
}

/** The week's six pieces (one per rubrique), the order the server composes them in; `items` takes the first n. */
const UNE_POOL: Json[] = [
  { session_id: 'mock-1', rubrique: 'titre', role: 'headline', story_title_fr: 'La Fête de la musique', text_fr: 'La Fête de la musique est gratuite pour tous',
    score: null, total: null, corrections_fr: [], stance: null, filed_on: '2026-11-17', filed_weekday_fr: 'mardi',
    picture: { kind: 'illustration', url: '/assets/serial/locations/le_mistral-counter.webp', width: 1536, height: 1024, alt_fr: '', caption_fr: null,
      credit_fr: 'Illustration · Le Papier', licence: null, licence_url: null, source_url: null } },
  { session_id: 'mock-2', rubrique: 'opinion', role: 'vox', story_title_fr: 'Le marché de Noël', text_fr: "À mon avis, c'est une bonne idée pour le quartier.",
    score: null, total: null, corrections_fr: [], stance: 'pour', picture: null, filed_on: '2026-11-18', filed_weekday_fr: 'mercredi' },
  { session_id: 'mock-3', rubrique: 'fil', role: 'brief', story_title_fr: 'Le bac', text_fr: "Le bac est créé en 1808. Le premier bac a lieu en 1809. En 2023, presque tous les candidats réussissent.",
    score: null, total: null, corrections_fr: [], stance: null, picture: null, filed_on: '2026-11-16', filed_weekday_fr: 'lundi' },
  { session_id: 'mock-4', rubrique: 'photo', role: 'caption', story_title_fr: "Le marché d'Aligre", text_fr: 'Au premier plan, on voit des fruits. Le marché ouvre six matins sur sept.',
    score: null, total: null, corrections_fr: [], stance: null, filed_on: '2026-11-20', filed_weekday_fr: 'vendredi',
    picture: { kind: 'illustration', url: '/assets/serial/locations/marche_canal.webp', width: 1536, height: 1024, alt_fr: '', caption_fr: null,
      credit_fr: 'Illustration · Le Papier', licence: null, licence_url: null, source_url: null } },
  { session_id: 'mock-5', rubrique: 'intox', role: 'rectificatif', story_title_fr: 'La Fête de la musique', text_fr: '4 sur 5, 1 intox corrigée',
    score: 4, total: 5, corrections_fr: ['La fête a lieu le 21 juin.'], stance: null, picture: null, filed_on: '2026-11-19', filed_weekday_fr: 'jeudi' },
  { session_id: 'mock-6', rubrique: 'micro', role: 'quote', story_title_fr: 'La grève du métro', text_fr: 'Pourquoi est-ce que vous faites grève ? Combien de temps est-ce que ça dure ?',
    score: null, total: null, corrections_fr: [], stance: null, picture: null, filed_on: '2026-11-21', filed_weekday_fr: 'samedi' },
];
const UNE_LEXIQUE = ['la fête', 'gratuit', 'le marché', 'le quartier', 'le bac', 'réussir', 'la grève', 'au premier plan'];

/** «La une de la semaine» of the mock: the first `n` pieces of the week (3 by default). */
function uneOf(n: number): Json {
  const items = UNE_POOL.slice(0, Math.max(0, Math.min(UNE_POOL.length, n)));
  const filed = new Set(items.map((item) => item.rubrique)).size;
  return {
    week: { iso: '2026-W47', label: 'Semaine 47', range: 'du 16 au 22 novembre' },
    dateline_fr: 'Semaine 47 · du 16 au 22 novembre',
    items,
    lexique: items.length ? UNE_LEXIQUE.slice(0, Math.min(UNE_LEXIQUE.length, 2 + items.length)) : [],
    rubriques_filed: filed,
    rubriques_total: 6,
    pieces: items.length,
    due_today: false,
  };
}

const CARTE: Json = {
  rubriques: [
    { rubrique: 'opinion', pieces: 2, first_on: '2026-11-02' },
    { rubrique: 'fil', pieces: 0, first_on: null },
    { rubrique: 'titre', pieces: 1, first_on: '2026-11-17' },
    { rubrique: 'intox', pieces: 1, first_on: '2026-11-19' },
    { rubrique: 'photo', pieces: 0, first_on: null },
    { rubrique: 'micro', pieces: 0, first_on: null },
  ],
  pieces: 4,
  since: '2026-11-02',
};

function notFound(): never {
  throw Object.assign(new Error('Not Found'), { response: { status: 404, data: { detail: 'Not Found' } } });
}

/** The mock transport with the rendez-vous routes; `enabled: false` answers them 404 as the switches off do. */
export function withRdvMock<T extends RevueTransport>(inner: T, { enabled = true, items = 3 }: { enabled?: boolean; items?: number } = {}): T {
  const rounds: Record<string, Round | null> = {};
  const session = async (id: string): Promise<Json> => (await inner.get(`/revue/sessions/${encodeURIComponent(id)}`)) as Json;
  const roundOf = async (id: string) => {
    if (!(id in rounds) || rounds[id] === null) rounds[id] = build(await session(id));
    return rounds[id];
  };
  const match = (url: string) => /^\/revue\/sessions\/([^/]+)\/(souvenir|trois-mots)$/.exec(url);
  return {
    ...inner,
    async get(url: string) {
      const m = match(url);
      if (m || url.startsWith('/revue/une') || url === '/revue/carte-de-presse') {
        if (!enabled) notFound();
        if (url.startsWith('/revue/une')) return uneOf(items);
        if (url === '/revue/carte-de-presse') return CARTE;
        const id = decodeURIComponent(m![1]);
        if (m![2] === 'souvenir') {
          const s = await session(id);
          const line = LINES[(s.mode as Mode) ?? 'chat'];
          return { line: line && line.fr ? { ...line, about_session_id: 'mock-past' } : null };
        }
        const r = await roundOf(id);
        return { round: r ? view(id, r) : null, error: null };
      }
      return inner.get(url);
    },
    async post(url: string, body: unknown) {
      const m = match(url);
      if (!m) return inner.post(url, body);
      if (!enabled) notFound();
      const id = decodeURIComponent(m[1]);
      const r = await roundOf(id);
      if (!r) return { round: null, error: 'out_of_order' };
      const b = body as Json;
      if (b.act === 'match') {
        const pairs = b.pairs as Record<string, string>;
        const misses = KEYS.filter((k) => pairs[k] !== r.answer[k]).map((k) => ({ word_key: k, cue_key: pairs[k] }));
        r.matches.push({ correct: misses.length === 0, misses });
      } else if (r.gap) {
        r.gaps.push({ word: b.word, correct: KEYS.indexOf(b.word) === r.gap.index });
      }
      return { round: view(id, r), error: null };
    },
  } as T;
}
