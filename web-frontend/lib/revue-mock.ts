/**
 * WP-119 phase 1 · Le Papier de Romy — a DEV-ONLY scripted server.
 *
 * `/revue?mock=1` (never in a production build: `pages/revue.tsx` only loads this
 * module when `NODE_ENV !== 'production'`) talks to this in-memory transport
 * instead of the API. It answers every route of WP-119-WIRE.md with **wire JSON**
 * (snake_case), so the page runs through the same parsers as against the real
 * backend, and the E-3 walk can drive the whole encounter without a model.
 *
 * Fixtures: three evergreen dossiers transcribed from
 * `app/services/revue/evergreen/*.json` (marché du dimanche — the recommended one,
 * grève des transports, Fête de la musique), with their real claims, quotes,
 * sources and uncertainties.
 *
 * The scripted Romy (the acceptance test of WP-119 §1):
 *   1. the first turn puts two claims on the table («Merci ! Voilà ce qu'on sait.»);
 *   2. a question containing «prix» (or one an uncertainty of the dossier covers)
 *      gets «Et là, je n'ai rien.» + an `uncertainty` item, and the open question
 *      is kept; the quick replies lead with «On formule la question»;
 *   3. otherwise she answers from the claim the question overlaps most, «Plus»
 *      adds the next claim; two «je ne comprends pas» in a row simplify (shift);
 *   4. at 80 % of the budget a `bouclage` shift + steer line, at 100 % `boucle`;
 *   5. make: the reader question is recommended when a question was kept; Romy's
 *      proposal keeps the learner's words (contribution spans); the headline
 *      choice has exactly one headline the claims support;
 *   6. close: a dispatch whose headline carries the learner's question, marked.
 *
 * State lives in memory and in `sessionStorage` (try/catch), so reloading the page
 * replays the session — the resume contract, in miniature.
 */

import type { RevueTransport } from './revue-api';
import { createRevueClient, type RevueClient } from './revue-api';

type Json = Record<string, any>;
type Lang = 'en' | 'de' | 'fr';
type Band = 'A1' | 'A2' | 'B1' | 'B2';

// ---------------------------------------------------------------------------
// Fixtures (transcribed from app/services/revue/evergreen/*.json)
// ---------------------------------------------------------------------------

type MockClaim = { id: string; kind: 'fact' | 'interpretation' | 'forecast'; fr: string; quote: string; source_id: string; attributed_to?: string };
type MockDossier = {
  id: string;
  title_fr: string;
  short_fr: string;
  summary_fr: string;
  topic: string;
  place: { id: string; name_fr: string; plate: string; plate_place_id: string; real: boolean; dress: string };
  narration: [string, string];
  place_note: string | null;
  angle: { id: string; fr: string; purpose: string };
  claims: MockClaim[];
  sources: Array<{ id: string; name: string; url: string; published_at: string }>;
  uncertainties: string[];
  vocabulary: Array<{ fr: string; claim_id: string; en: string; de: string; gloss_fr: string }>;
  headlines: Array<{ id: string; text_fr: string; correct?: boolean }>;
  headline_claim: string;
  reader_question_fr: string;
};

const MARCHE: MockDossier = {
  id: 'evergreen-marche-du-dimanche',
  title_fr: 'Le marché du dimanche à Aligre',
  short_fr: 'Le marché d’Aligre',
  summary_fr:
    "Paris a 91 marchés. Celui d'Aligre, dans le 12e arrondissement, ouvre six matins sur sept, week-end compris. Il y a un marché couvert et un marché en plein air.",
  topic: 'food',
  place: { id: 'marche_aligre', name_fr: "Le marché d'Aligre, un matin", plate: '/assets/serial/locations/marche_canal.webp', plate_place_id: 'marche_canal', real: false, dress: 'apron' },
  narration: [
    'Un dimanche matin, entre les cagettes de poireaux et de clémentines.',
    "Romy t'attend devant un étal, son carnet ouvert.",
  ],
  place_note: "On n'est pas à Aligre, hein : c'est le marché du canal. Mais ça se passe pareil.",
  angle: { id: 'a1', fr: 'Faire ses courses au marché : comment ça marche', purpose: 'understand_change' },
  claims: [
    { id: 'c1', kind: 'fact', fr: 'Paris compte 91 marchés.', quote: 'les 91 marchés de Paris font vivre la ville au quotidien', source_id: 'marche_paris' },
    {
      id: 'c2',
      kind: 'fact',
      fr: "Le marché d'Aligre, dans le 12e arrondissement, a lieu tous les matins, six jours sur sept.",
      quote: "Le marché d’Aligre se déroule tous les matins sauf le lundi place d'Aligre et rue d'Aligre, dans le 12e arrondissement de Paris.",
      source_id: 'marche_wikipedia_aligre',
    },
    {
      id: 'c3',
      kind: 'fact',
      fr: 'Il y a un marché couvert, le marché Beauvau, ouvert toute la journée, et un marché en plein air, ouvert seulement le matin.',
      quote:
        'le marché couvert dont le nom est marché Beauvau ou marché Beauvau-Saint-Antoine, ouvert toute la journée et situé dans la moitié ouest de la place d\'Aligre, et le marché découvert, ouvert uniquement le matin',
      source_id: 'marche_wikipedia_aligre',
    },
    {
      id: 'c4',
      kind: 'interpretation',
      fr: "Pour la Ville de Paris, les marchés sont des lieux de vie où l'on trouve à la fois de la convivialité et du savoir-faire.",
      quote: 'les marchés sont des lieux de vie incontournables, où se mêlent convivialité et savoir-faire',
      source_id: 'marche_paris',
      attributed_to: 'la Ville de Paris',
    },
  ],
  sources: [
    { id: 'marche_paris', name: 'Ville de Paris (paris.fr)', url: 'https://www.paris.fr/pages/les-marches-parisiens-2428', published_at: '2026-09-23' },
    {
      id: 'marche_wikipedia_aligre',
      name: 'Wikipédia, « Marché d\'Aligre »',
      url: 'https://fr.wikipedia.org/w/index.php?title=March%C3%A9_d%27Aligre&oldid=233954957',
      published_at: '2026-03-10',
    },
  ],
  uncertainties: [
    "Les sources ne disent pas si les prix au marché sont plus bas qu'au supermarché.",
    "Les sources ne disent pas si les horaires changent pendant les fêtes de fin d'année.",
  ],
  vocabulary: [
    { fr: 'arrondissement', claim_id: 'c2', en: 'district', de: 'Bezirk', gloss_fr: 'quartier de Paris' },
    { fr: 'matins', claim_id: 'c2', en: 'mornings', de: 'Vormittage', gloss_fr: 'débuts de journée' },
    { fr: 'marché couvert', claim_id: 'c3', en: 'covered market', de: 'Markthalle', gloss_fr: 'marché sous un toit' },
    { fr: 'en plein air', claim_id: 'c3', en: 'outdoors', de: 'im Freien', gloss_fr: 'dehors' },
    { fr: 'savoir-faire', claim_id: 'c4', en: 'know-how', de: 'Können', gloss_fr: 'talent du métier' },
  ],
  headlines: [
    { id: 'h1', text_fr: "À Aligre, le marché n'ouvre que le dimanche" },
    { id: 'h2', text_fr: 'À Aligre, le marché ouvre six matins sur sept', correct: true },
    { id: 'h3', text_fr: "À Aligre, il n'y a plus de marché couvert" },
  ],
  headline_claim: 'c2',
  reader_question_fr: "Est-ce que les prix au marché sont plus bas qu'au supermarché ?",
};

const GREVE: MockDossier = {
  id: 'evergreen-greve-transports',
  title_fr: 'Un jour de grève dans les transports',
  short_fr: 'La grève',
  summary_fr:
    "En France, les grèves dans les métros et les trains reviennent souvent. Elles suivent des règles : un préavis, une déclaration des grévistes, un plan de transport. On parle souvent de « service minimum », mais ce n'est pas une vraie obligation.",
  topic: 'work',
  place: { id: 'quai_metro_greve', name_fr: 'Un quai de métro un matin de grève', plate: '/assets/serial/locations/metro_platform.webp', plate_place_id: 'metro_platform', real: false, dress: 'coat' },
  narration: ['Un quai de métro, tôt le matin. Le panneau annonce de longues attentes.', 'Romy est assise sur un banc, son carnet sur les genoux.'],
  place_note: "Ce n'est pas un jour de grève aujourd'hui, hein. Mais imagine ce quai à moitié vide.",
  angle: { id: 'a1', fr: 'Comment se passe un jour de grève pour un voyageur', purpose: 'understand_change' },
  claims: [
    {
      id: 'c1',
      kind: 'fact',
      fr: 'Dans les transports publics, un préavis de grève doit être déposé au moins cinq jours avant le début de la grève.',
      quote: 'préavis de grève déposé au moins 5 jours francs avant le début de la grève',
      source_id: 'greve_ecologie',
    },
    {
      id: 'c2',
      kind: 'fact',
      fr: 'Chaque salarié qui veut faire grève doit le dire 48 heures avant, pour que le service soit réorganisé sur les lignes les plus importantes.',
      quote:
        "La loi instaure l'obligation pour les salariés d'indiquer quarante-huit heures à l'avance qu'ils ont l'intention de faire grève pour permettre aux collectivités locales de réorganiser le service sur les dessertes les plus importantes",
      source_id: 'greve_wikipedia_service_minimum',
    },
    {
      id: 'c3',
      kind: 'fact',
      fr: 'La loi organise les transports pendant une grève, mais elle ne crée pas une vraie obligation de service minimum.',
      quote: 'en cas de grève sans mettre en place une véritable obligation de service minimum',
      source_id: 'greve_wikipedia_service_minimum',
    },
    {
      id: 'c4',
      kind: 'interpretation',
      fr: 'Pour les syndicats de salariés et les partis de gauche, le service minimum remet en cause le droit de grève.',
      quote:
        'La critique du service minimum est faite, essentiellement, par les syndicats de salariés et les partis de gauche. Selon eux, le service minimum remet en cause le droit de grève, qui a valeur constitutionnelle.',
      source_id: 'greve_wikipedia_service_minimum',
      attributed_to: 'les syndicats de salariés et les partis de gauche',
    },
  ],
  sources: [
    {
      id: 'greve_ecologie',
      name: 'Ministère de la Transition écologique (ecologie.gouv.fr)',
      url: 'https://www.ecologie.gouv.fr/politiques-publiques/questions-sociales-generales-du-transport-ferroviaire',
      published_at: '2018-05-25',
    },
    {
      id: 'greve_wikipedia_service_minimum',
      name: 'Wikipédia, « Service minimum »',
      url: 'https://fr.wikipedia.org/w/index.php?title=Service_minimum&oldid=239788633',
      published_at: '2026-09-24',
    },
  ],
  uncertainties: [
    'Les sources ne disent pas quand aura lieu la prochaine grève, ni quelles lignes seront touchées.',
    'Les sources ne disent pas combien de trains roulent un jour de grève : cela dépend du plan de transport.',
  ],
  vocabulary: [
    { fr: 'préavis', claim_id: 'c1', en: 'notice', de: 'Vorankündigung', gloss_fr: 'annonce faite avant' },
    { fr: 'grève', claim_id: 'c1', en: 'strike', de: 'Streik', gloss_fr: 'arrêt du travail' },
    { fr: 'salarié', claim_id: 'c2', en: 'employee', de: 'Angestellter', gloss_fr: 'personne payée par un employeur' },
    { fr: 'service minimum', claim_id: 'c3', en: 'minimum service', de: 'Notbetrieb', gloss_fr: 'le service qui reste' },
    { fr: 'syndicats', claim_id: 'c4', en: 'unions', de: 'Gewerkschaften', gloss_fr: 'groupes de salariés' },
  ],
  headlines: [
    { id: 'h1', text_fr: 'Grève : un préavis de cinq jours au moins', correct: true },
    { id: 'h2', text_fr: 'Grève : aucun préavis, les salariés arrêtent quand ils veulent' },
    { id: 'h3', text_fr: 'Grève : la loi impose un vrai service minimum' },
  ],
  headline_claim: 'c1',
  reader_question_fr: 'Est-ce que le prix du billet est remboursé un jour de grève ?',
};

const FETE: MockDossier = {
  id: 'evergreen-fete-de-la-musique',
  title_fr: 'La Fête de la musique',
  short_fr: 'La Fête de la musique',
  summary_fr:
    'Le 21 juin, des musiciens amateurs et professionnels jouent gratuitement dans les rues, les bars et sur les places. La fête existe depuis 1982. Elle plaît à beaucoup de monde, mais elle fait aussi du bruit, et certains voisins se plaignent.',
  topic: 'culture',
  place: { id: 'place_fete_musique', name_fr: 'Une petite place parisienne le soir du 21 juin', plate: '/assets/serial/locations/le_mistral-counter.webp', plate_place_id: 'le_mistral', real: false, dress: 'coat' },
  narration: ['Le Mistral, un soir de juin. Dehors, on installe une petite scène.', 'Romy t’attend au comptoir, son carnet ouvert.'],
  place_note: "On n'est pas sur la place, hein. Mais d'ici, on entend déjà la batterie.",
  angle: { id: 'a1', fr: 'Ce qui se passe dans la rue le 21 juin', purpose: 'understand_change' },
  claims: [
    {
      id: 'c1',
      kind: 'fact',
      fr: "La première Fête de la musique a eu lieu le 21 juin 1982, le jour le plus long de l'année.",
      quote: 'la première Fête de la musique est lancée le 21 juin 1982, jour symbolique du solstice d’été, le plus long de l’année dans l’hémisphère Nord',
      source_id: 'fetemusique_culture',
    },
    {
      id: 'c2',
      kind: 'fact',
      fr: 'La fête est gratuite et ouverte à toutes les musiques.',
      quote: 'La Fête sera gratuite, ouverte à toutes les musiques « sans hiérarchie de genres et de pratiques » et à tous les français.',
      source_id: 'fetemusique_culture',
    },
    {
      id: 'c3',
      kind: 'fact',
      fr: 'La fête provoque aussi du bruit, et de nombreuses plaintes.',
      quote: "La Fête de la musique est source de nuisances sonores avérées et fait l'objet de nombreuses plaintes.",
      source_id: 'fetemusique_wikipedia',
    },
    {
      id: 'c4',
      kind: 'interpretation',
      fr: 'Selon le ministère de la Culture, le succès de la première édition, en 1982, a dépassé toutes les espérances.',
      quote: 'Le résultat dépasse toutes les espérances.',
      source_id: 'fetemusique_culture',
      attributed_to: 'le ministère de la Culture',
    },
  ],
  sources: [
    {
      id: 'fetemusique_culture',
      name: 'Ministère de la Culture (fetedelamusique.culture.gouv.fr)',
      url: 'https://fetedelamusique.culture.gouv.fr/actualites/historique-de-la-fete-de-la-musique',
      published_at: '2025-02-03',
    },
    { id: 'fetemusique_wikipedia', name: 'Wikipédia, « Fête de la musique »', url: 'https://fr.wikipedia.org/w/index.php?title=F%C3%AAte_de_la_musique&oldid=238264404', published_at: '2026-07-31' },
  ],
  uncertainties: [
    'Les sources ne disent pas combien de concerts il y a eu en 2026.',
    'Les sources ne disent pas si les villes vont limiter davantage les horaires de la musique dans la rue.',
  ],
  vocabulary: [
    { fr: 'gratuite', claim_id: 'c2', en: 'free', de: 'kostenlos', gloss_fr: 'sans payer' },
    { fr: 'bruit', claim_id: 'c3', en: 'noise', de: 'Lärm', gloss_fr: 'son fort' },
    { fr: 'plaintes', claim_id: 'c3', en: 'complaints', de: 'Beschwerden', gloss_fr: 'reproches' },
    { fr: 'le plus long', claim_id: 'c1', en: 'the longest', de: 'der längste', gloss_fr: 'qui dure le plus' },
    { fr: 'espérances', claim_id: 'c4', en: 'hopes', de: 'Erwartungen', gloss_fr: 'ce qu’on espère' },
  ],
  headlines: [
    { id: 'h1', text_fr: 'Le 21 juin, la musique est payante' },
    { id: 'h2', text_fr: 'Le 21 juin, une fête gratuite et ouverte à toutes les musiques', correct: true },
    { id: 'h3', text_fr: 'Le 21 juin, aucune plainte pour le bruit' },
  ],
  headline_claim: 'c2',
  reader_question_fr: 'Est-ce que les concerts sont plus nombreux cette année ?',
};

const DOSSIERS: MockDossier[] = [MARCHE, GREVE, FETE];

const WEEK = { iso: '2026-W40', label: 'Semaine 40', range: 'du 28 sept. au 4 oct.' };

// Romy's authored lines (the same French as app/services/revue/encounter.py).
const FALLBACK_LINE = 'Je ne sais pas encore. On regarde ce que disent les sources ?';
const STEER_LINE = 'Il me reste peu de place dans la colonne : on fait le titre, ou la question pour les lecteurs ?';
const FINAL_LINE = "La colonne est pleine ! On boucle avec ce qu'on a : le titre, ou la question pour les lecteurs ?";
const KEPT_LINE = 'Bonne question. Je la garde pour la semaine prochaine : on boucle avec ce qu\'on a ?';
const SIMPLIFY_LEAD = 'Pardon, je vais trop vite.';
const PURPOSE_LINES: Record<string, string> = {
  understand_change: 'Je dois expliquer ça à mes lecteurs de Montréal : « {angle} ». Tu m’aides ?',
  explain_disagreement: 'Les gens ne sont pas d’accord, et je dois l’expliquer : « {angle} ». Tu m’aides ?',
  choose_angle: 'Je ne sais pas par quel bout prendre l’histoire : « {angle} ». Tu m’aides à choisir ?',
  prepare_dispatch: 'Je dois écrire trois lignes là-dessus : « {angle} ». Tu m’aides ?',
};
const CLOSE_LINES: Record<string, string> = {
  reader_question: "J'ai mis ta question dans ma liste pour la rédaction. Je la garde.",
  headline_choice: 'Je garde ton titre. Il part avec mon papier.',
  none: "Les sources ne m'ont pas tout dit, mais on a de quoi écrire trois lignes.",
};
const QR_AGREE = { label: "D'accord, je t'aide.", send_fr: "D'accord, je t'aide." };
const QR_MORE = { label: 'Plus', send_fr: "Dis-m'en plus." };
export const MOCK_FORMULATE_FR = 'On formule la question ensemble ?';
const QR_FORMULATE = { label: 'On formule la question', send_fr: MOCK_FORMULATE_FR };
const QR_UNDERSTOOD = { label: "Ah, d'accord", send_fr: "Ah, d'accord." };
const QR_SIMPLER = { label: 'Encore plus simple', send_fr: "Encore plus simple, s'il te plaît." };

/** A few of Romy's fixed lines, translated (A1 shows them one tap away). */
const TRANSLATIONS: Record<string, { en: string; de: string }> = {
  'Merci ! Voilà ce qu’on sait.': { en: 'Thanks! Here is what we know.', de: 'Danke! Das wissen wir.' },
  "Et là, je n'ai rien. Les sources ne le disent pas. On formule la question ensemble ?": {
    en: "And there, I've got nothing. The sources don't say. Shall we phrase the question together?",
    de: 'Und da habe ich nichts. Die Quellen sagen es nicht. Formulieren wir die Frage zusammen?',
  },
  [SIMPLIFY_LEAD]: { en: "Sorry, I'm going too fast.", de: 'Entschuldige, ich bin zu schnell.' },
};

const BUDGET_TURNS = 6;
const ROOM_LINES = 7;

// ---------------------------------------------------------------------------
// Session state
// ---------------------------------------------------------------------------

type MockSession = {
  id: string;
  dossierId: string;
  chosenBy: 'learner' | 'recommended';
  band: Band;
  language: Lang;
  seq: number;
  thread: Json[];
  turnsUsed: number;
  shown: string[];
  openQuestion: string | null;
  openUncertainty: string | null;
  /** What the learner wrote for the reader question (propose). */
  draftLearner?: string | null;
  confused: number;
  supportLevel: number;
  steered: boolean;
  final: boolean;
  makeStarted: boolean;
  artifact: Json | null;
  closing: Json | null;
  startedAt: string;
  closedAt: string | null;
  turnIds: Record<string, Json>;
  /** What Romy's last turn did (the quick replies follow it, as the server's state does). */
  flags?: { uncertainty: boolean; simplified: boolean; proposes: boolean };
};

export type MockOptions = {
  /** The learner's chrome / gloss language. */
  language?: Lang;
  /** A1 shows glosses and translations; A2 (default) tap-glosses. */
  band?: Band;
  /** Milliseconds before each answer (0 in tests). */
  latency?: number;
  /** `GET /revue/week` answers 404, as with the flag off. */
  disabled?: boolean;
  /** Keep state in sessionStorage so a reload replays it (default true in the browser). */
  persist?: boolean;
  /** The clock (tests). */
  now?: () => Date;
};

const STORAGE_KEY = 'revue-mock-v1';

function fold(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[’‘`´]/g, "'");
}

const STOP = new Set(
  'les des une est que qui pour dans sur avec pas plus par aux ces son ses sont elle ils mais ont tout tous cette ete etre avoir quoi comment pourquoi combien quand quel quelle est-ce ce ca la le un et ou on il de du en au a je tu me te ne y'.split(' '),
);

function words(text: string): string[] {
  return (fold(text).match(/[a-z0-9]+(?:-[a-z0-9]+)*/g) || []).filter((word) => word.length > 2 && !STOP.has(word));
}

function overlap(a: string, b: string): number {
  const set = new Set(words(b));
  return words(a).filter((word) => set.has(word)).length;
}

/** The learner's words inside `text`, as [start, end] spans (merged across spaces and apostrophes). */
export function contributionSpans(text: string, learner: string | null): Array<[number, number]> {
  if (!learner) return [];
  const token = /[A-Za-zÀ-ÖØ-öø-ÿœŒ0-9]+(?:-[A-Za-zÀ-ÖØ-öø-ÿœŒ0-9]+)*/g;
  const mine = new Set((fold(learner).match(/[a-z0-9]+(?:-[a-z0-9]+)*/g) || []).map((word) => word));
  const out: Array<[number, number]> = [];
  let match: RegExpExecArray | null;
  while ((match = token.exec(text))) {
    if (!mine.has(fold(match[0]))) continue;
    const start = match.index;
    const end = start + match[0].length;
    const last = out[out.length - 1];
    if (last && /^[\s'’]*$/.test(text.slice(last[1], start))) last[1] = end;
    else out.push([start, end]);
  }
  return out;
}

function frenchQuestion(text: string): { fr: string; addedLead: boolean } {
  let body = text.trim().replace(/\s*[?.!]+$/, '').trim();
  if (!body) return { fr: '', addedLead: false };
  const lead = /^(est-ce|pourquoi|comment|combien|quand|où|ou |qui|quel|quelle|qu'|qu’)/i.test(body);
  if (lead) {
    body = body.charAt(0).toUpperCase() + body.slice(1);
    return { fr: `${body} ?`, addedLead: false };
  }
  return { fr: `Est-ce que ${body.charAt(0).toLowerCase()}${body.slice(1)} ?`, addedLead: true };
}

/** Looks French enough to keep as the proposal; otherwise Romy writes the dossier's question. */
function looksFrench(text: string): boolean {
  const t = ` ${fold(text)} `;
  const fr = [' le ', ' la ', ' les ', ' est ', ' des ', ' du ', ' que ', ' plus ', ' au ', ' un ', ' une ', ' prix '].filter((w) => t.includes(w)).length;
  const other = [' the ', ' is ', ' are ', ' die ', ' der ', ' das ', ' ist ', ' sind ', ' wird ', ' und ', ' preise ', ' price'].filter((w) => t.includes(w)).length;
  return fr >= other;
}

// ---------------------------------------------------------------------------
// The transport
// ---------------------------------------------------------------------------

type HttpError = Error & { response: { status: number; data: unknown } };

function httpError(status: number, detail: unknown): HttpError {
  const error = new Error(`mock ${status}`) as HttpError;
  error.response = { status, data: { detail } };
  return error;
}

export function createMockRevueTransport(options: MockOptions = {}): RevueTransport & { reset: () => void } {
  const language: Lang = options.language ?? 'en';
  const band: Band = options.band ?? 'A2';
  const latency = options.latency ?? 0;
  const now = options.now ?? (() => new Date());
  const persist = options.persist ?? typeof window !== 'undefined';
  let sessions: Record<string, MockSession> = {};

  if (persist) {
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY);
      if (raw) sessions = JSON.parse(raw) as Record<string, MockSession>;
    } catch {
      sessions = {};
    }
  }
  const save = () => {
    if (!persist) return;
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch {
      /* private mode: memory only */
    }
  };

  const dossierById = (id: string) => DOSSIERS.find((d) => d.id === id) ?? null;
  const allSessions = () => Object.keys(sessions).map((id) => sessions[id]);
  const active = () => allSessions().find((s) => !s.closing) ?? null;
  const filed = () => allSessions().find((s) => Boolean(s.closing)) ?? null;

  // --- wire builders -------------------------------------------------------

  const sourceOf = (d: MockDossier, id: string) => {
    const s = d.sources.find((row) => row.id === id) ?? d.sources[0];
    return { id: s.id, name: s.name, url: s.url, published_at: s.published_at };
  };
  const claimWire = (d: MockDossier, c: MockClaim) => ({
    id: c.id,
    kind: c.kind,
    fr: c.fr,
    quote: c.quote,
    attributed_to: c.attributed_to ?? null,
    source: sourceOf(d, c.source_id),
  });
  const glossOf = (v: MockDossier['vocabulary'][number], lang: Lang) => ({ fr: v.fr, gloss: lang === 'de' ? v.de : lang === 'fr' ? v.gloss_fr : v.en, claim_id: v.claim_id });
  const stageOf = (d: MockDossier) => ({
    place_id: d.place.id,
    place_fr: d.place.name_fr,
    plate_url: d.place.plate,
    plate_place_id: d.place.plate_place_id,
    place_is_real: d.place.real,
    dress: d.place.dress,
    cast: [
      { id: 'romy_tremblay', hold: 'notebook' },
      { id: 'user', hold: null },
    ],
  });
  const cardOf = (d: MockDossier) => ({
    dossier_id: d.id,
    title_fr: d.title_fr,
    summary_fr: d.summary_fr,
    topic: d.topic,
    place_fr: d.place.name_fr,
    plate_url: d.place.plate,
    evergreen: true,
    stage: stageOf(d),
  });
  const supportOf = (s: MockSession) => {
    const a1 = s.band === 'A1' || s.supportLevel > 0;
    const b1 = s.band === 'B1' || s.band === 'B2';
    return {
      glosses: a1 ? 'shown' : s.band === 'B2' ? 'none' : 'tap',
      translation: a1 ? 'one_tap' : b1 ? 'none' : 'on_request',
      reading_target_words: s.band === 'A1' ? 60 : s.band === 'A2' ? 90 : s.band === 'B1' ? 140 : 200,
      vocab_target: b1 ? 7 : 5,
      level: s.supportLevel,
    };
  };
  const roomOf = (s: MockSession) => {
    const ratio = s.turnsUsed / BUDGET_TURNS;
    return {
      used: Math.min(ROOM_LINES, Math.floor((s.turnsUsed * ROOM_LINES) / BUDGET_TURNS)),
      phase: ratio >= 1 ? 'boucle' : ratio >= 0.8 ? 'bouclage' : 'open',
      remaining_turns: Math.max(0, BUDGET_TURNS - s.turnsUsed),
    };
  };
  const beatOf = (s: MockSession) =>
    s.closing ? 'close' : s.makeStarted || s.artifact ? 'make' : s.turnsUsed === 0 ? 'arrive' : s.turnsUsed === 1 ? 'facts' : 'pursue';

  const stamp = () => now().toISOString();
  const nextSeq = (s: MockSession) => {
    s.seq += 1;
    return s.seq;
  };
  const glossesIn = (s: MockSession, d: MockDossier, text: string) => {
    const folded = fold(text);
    return d.vocabulary.filter((v) => folded.includes(fold(v.fr))).map((v) => glossOf(v, s.language));
  };
  const line = (s: MockSession, d: MockDossier, seq: number, role: string, text: string, suffix = '') => {
    const support = supportOf(s);
    const translated = TRANSLATIONS[text];
    const lang = s.language === 'fr' ? null : s.language;
    return {
      id: `${seq}${suffix}`,
      seq,
      at: stamp(),
      kind: 'line',
      speaker: 'romy_tremblay',
      role,
      text_fr: text,
      translation: support.translation !== 'none' && translated && lang ? translated[lang] : null,
      glosses: glossesIn(s, d, text),
    };
  };
  const quickOf = (s: MockSession, last: { uncertainty: boolean; simplified: boolean; proposes: boolean }) => {
    if (s.closing) return [];
    if (s.turnsUsed === 0) return [QR_AGREE];
    const room = roomOf(s);
    if (room.phase !== 'open') return s.artifact ? [] : [QR_MORE];
    if (last.simplified) return [QR_UNDERSTOOD, QR_SIMPLER];
    if (last.uncertainty || last.proposes) return [QR_FORMULATE, QR_MORE];
    return [QR_MORE];
  };
  const NO_FLAGS = { uncertainty: false, simplified: false, proposes: false };

  const viewOf = (s: MockSession) => {
    const d = dossierById(s.dossierId) as MockDossier;
    const room = roomOf(s);
    return {
      id: s.id,
      week: WEEK,
      status: s.closing ? 'closed' : 'active',
      started_at: s.startedAt,
      closed_at: s.closedAt,
      dossier: { id: d.id, title_fr: d.title_fr, summary_fr: d.summary_fr, topic: d.topic, evergreen: true, sources: d.sources },
      plan: {
        band: s.band,
        ui_language: s.language,
        gloss_language: s.language,
        chosen_by: s.chosenBy,
        angle: d.angle,
        support: supportOf(s),
        vocabulary: d.vocabulary.map((v) => glossOf(v, s.language)),
        make_options: ['headline_choice', 'reader_question'],
        budget: { turns: BUDGET_TURNS, minutes: 12 },
      },
      stage: stageOf(d),
      beat: beatOf(s),
      room,
      thread: s.thread,
      quick_replies: quickOf(s, s.flags ?? NO_FLAGS),
      steer_to_make: room.phase !== 'open' && !s.artifact && !s.closing,
      artifact: s.artifact,
      closing: s.closing,
    };
  };

  // --- routes ---------------------------------------------------------------

  const offer = () => {
    const current = active();
    const done = filed();
    return {
      week: WEEK,
      recommended: cardOf(MARCHE),
      recommended_reason: 'interests',
      alternatives: [cardOf(GREVE), cardOf(FETE)],
      evergreen_only: true,
      resume: current
        ? {
            session_id: current.id,
            dossier_id: current.dossierId,
            title_fr: (dossierById(current.dossierId) as MockDossier).title_fr,
            started_at: current.startedAt,
            beat: beatOf(current),
            open_question_fr: current.openQuestion,
          }
        : null,
      filed: done
        ? {
            session_id: done.id,
            dossier_id: done.dossierId,
            title_fr: (dossierById(done.dossierId) as MockDossier).title_fr,
            closed_at: done.closedAt,
            made: done.artifact,
            dispatch: done.closing?.dispatch ?? null,
          }
        : null,
    };
  };

  const matchText = (text: string): MockDossier | null => {
    let best: MockDossier | null = null;
    let score = 0;
    for (const d of DOSSIERS) {
      const value = overlap(text, `${d.title_fr} ${d.summary_fr} ${d.angle.fr} ${d.topic}`);
      if (value > score) {
        best = d;
        score = value;
      }
    }
    return best;
  };
  const missLine = () => `Je n'ai que ça cette semaine, désolée. « ${MARCHE.title_fr} », ça te dit ?`;

  const start = (body: Json) => {
    const current = active();
    if (current) throw httpError(409, { code: 'revue_session_active', session_id: current.id });
    const done = filed();
    if (done) throw httpError(409, { code: 'revue_week_filed', session_id: done.id });
    let d: MockDossier | null = null;
    let chosenBy: 'learner' | 'recommended' = 'recommended';
    let miss = false;
    if (body.dossier_id) {
      d = dossierById(String(body.dossier_id));
      if (!d) throw httpError(404, { code: 'revue_dossier_not_found', dossier_id: body.dossier_id });
      chosenBy = 'learner';
    } else if (body.free_request) {
      d = matchText(String(body.free_request));
      if (d) chosenBy = 'learner';
      else miss = true;
    }
    d = d ?? MARCHE;
    const s: MockSession = {
      id: `mock-${Math.random().toString(36).slice(2, 10)}`,
      dossierId: d.id,
      chosenBy,
      band,
      language,
      seq: 0,
      thread: [],
      turnsUsed: 0,
      shown: [],
      openQuestion: null,
      openUncertainty: null,
      confused: 0,
      supportLevel: 0,
      steered: false,
      final: false,
      makeStarted: false,
      artifact: null,
      closing: null,
      startedAt: stamp(),
      closedAt: null,
      turnIds: {},
    };
    const seq = nextSeq(s);
    const at = stamp();
    d.narration.forEach((text, index) => s.thread.push({ id: `${seq}.n${index}`, seq, at, kind: 'narration', text_fr: text }));
    if (d.place_note && !d.place.real) s.thread.push(line(s, d, seq, 'place_note', d.place_note, '.p'));
    if (miss) s.thread.push(line(s, d, seq, 'fallback', missLine(), '.m'));
    s.thread.push(line(s, d, seq, 'purpose', PURPOSE_LINES[d.angle.purpose].replace('{angle}', d.angle.fr)));
    s.thread.push({ id: `${seq}.s`, seq, at, kind: 'summary', speaker: 'romy_tremblay', text_fr: d.summary_fr });
    sessions[s.id] = s;
    save();
    return viewOf(s);
  };

  const sessionOr404 = (id: string) => {
    const s = sessions[id];
    if (!s) throw httpError(404, { code: 'revue_session_not_found' });
    return s;
  };

  const showClaims = (s: MockSession, d: MockDossier, ids: string[], items: Json[]) => {
    const fresh = ids.filter((id) => !s.shown.includes(id));
    if (!fresh.length) return;
    s.shown.push(...fresh);
    const seq = nextSeq(s);
    items.push({ id: String(seq), seq, at: stamp(), kind: 'claims', claims: fresh.map((id) => claimWire(d, d.claims.find((c) => c.id === id) as MockClaim)) });
  };

  const turn = (id: string, body: Json) => {
    const s = sessionOr404(id);
    if (s.closing) throw httpError(409, { code: 'revue_session_closed' });
    const text = String(body.text || '').trim();
    if (!text || text.length > 600) throw httpError(422, [{ loc: ['body', 'text'], msg: 'invalid' }]);
    const turnId = body.client_turn_id ? String(body.client_turn_id) : '';
    if (turnId && s.turnIds[turnId]) return s.turnIds[turnId];

    const d = dossierById(s.dossierId) as MockDossier;
    const items: Json[] = [];
    const mineSeq = nextSeq(s);
    items.push({ id: String(mineSeq), seq: mineSeq, at: stamp(), kind: 'mine', text_fr: text, mode: body.mode === 'voice' ? 'voice' : 'text' });
    const wasBoucle = s.turnsUsed >= BUDGET_TURNS;
    s.turnsUsed += 1;
    const folded = fold(text);
    const flags = { uncertainty: false, simplified: false, proposes: false };
    const reply = (text_fr: string, role = 'reply') => {
      const seq = nextSeq(s);
      items.push(line(s, d, seq, role, text_fr));
      return seq;
    };
    const unshown = d.claims.filter((c) => !s.shown.includes(c.id));
    const question = /\?\s*$/.test(text) || /^(est-ce|pourquoi|comment|combien|quand|qui|quel)/.test(folded);

    if (wasBoucle) {
      // After 100 % Romy no longer calls the model: she keeps the question.
      if (question) s.openQuestion = text;
      reply(KEPT_LINE, 'steer');
    } else if (/comprends pas|pas compris|plus simple|je comprends rien/.test(folded)) {
      s.confused += 1;
      if (s.confused >= 2 && s.supportLevel === 0) {
        s.supportLevel = 1;
        const seq = nextSeq(s);
        items.push({ id: String(seq), seq, at: stamp(), kind: 'shift', reason: 'simplify', angle: null });
        reply(SIMPLIFY_LEAD);
        const first = d.claims[0];
        reply(first.fr.split(',')[0].replace(/\.$/, '') + '.');
        flags.simplified = true;
      } else {
        reply(`Je reformule : ${d.claims[0].fr}`);
      }
    } else if (folded.includes('formule la question') || folded.includes('on l\'ecrit')) {
      s.confused = 0;
      reply("D'accord. Écris-la comme elle te vient, même dans ta langue : je t'aide pour le français.");
      flags.proposes = true;
    } else if (!s.shown.length) {
      s.confused = 0;
      reply('Merci ! Voilà ce qu’on sait.');
      showClaims(s, d, d.claims.slice(0, 2).map((c) => c.id), items);
    } else if (folded.includes('prix') || (question && d.uncertainties.some((u) => overlap(text, u) >= 2))) {
      s.confused = 0;
      const uncertainty =
        d.uncertainties.find((u) => (folded.includes('prix') ? fold(u).includes('prix') : overlap(text, u) >= 2)) ??
        'Les sources ne disent rien sur les prix.';
      const seq = reply("Et là, je n'ai rien. Les sources ne le disent pas. On formule la question ensemble ?");
      items.push({ id: `${seq}.u`, seq, at: stamp(), kind: 'uncertainty', text_fr: uncertainty });
      s.openQuestion = text;
      s.openUncertainty = uncertainty;
      flags.uncertainty = true;
    } else if (/dis-m'en plus|^plus\b|en plus/.test(folded)) {
      s.confused = 0;
      const next = unshown[0];
      if (next) {
        reply(next.kind === 'interpretation' ? `Il y a aussi un avis, d'après ${next.attributed_to}.` : 'Il y a autre chose.');
        showClaims(s, d, [next.id], items);
      } else {
        reply("C'est tout ce que disent mes sources. On en fait quelque chose ?");
        flags.proposes = true;
      }
    } else {
      s.confused = 0;
      const ranked = d.claims.map((c) => ({ c, score: overlap(text, c.fr) })).sort((a, b) => b.score - a.score);
      if (ranked[0].score > 0) {
        const best = ranked[0].c;
        reply(best.kind === 'interpretation' ? `D'après ${best.attributed_to}, oui.` : 'Oui, mes sources le disent.');
        showClaims(s, d, [best.id], items);
      } else if (question) {
        reply("Bonne question. Mes sources ne le disent pas. On l'écrit pour les lecteurs ?");
        s.openQuestion = text;
        flags.proposes = true;
      } else {
        reply(unshown[0] ? 'Je note. Et tu savais ça ?' : FALLBACK_LINE);
        if (unshown[0]) showClaims(s, d, [unshown[0].id], items);
      }
    }

    // The column: 80 % → bouclage and a steer, 100 % → bouclé.
    const room = roomOf(s);
    if (!wasBoucle && room.phase === 'boucle' && !s.final) {
      s.final = true;
      s.steered = true;
      const seq = nextSeq(s);
      items.push({ id: String(seq), seq, at: stamp(), kind: 'shift', reason: 'boucle', angle: null });
      reply(FINAL_LINE, 'steer');
    } else if (room.phase === 'bouclage' && !s.steered) {
      s.steered = true;
      const seq = nextSeq(s);
      items.push({ id: String(seq), seq, at: stamp(), kind: 'shift', reason: 'bouclage', angle: null });
      reply(STEER_LINE, 'steer');
    }

    s.thread.push(...items);
    s.flags = flags;
    const result = {
      items,
      beat: beatOf(s),
      room,
      support: supportOf(s),
      quick_replies: quickOf(s, flags),
      steer_to_make: room.phase !== 'open' && !s.artifact,
      evidence: { outcome: 'unscored', capability_known: false, grader: 'revue-unscored-adapter-v1' },
    };
    if (turnId) s.turnIds[turnId] = result;
    save();
    return result;
  };

  const makeOffer = (id: string) => {
    const s = sessionOr404(id);
    if (s.closing) throw httpError(409, { code: 'revue_session_closed' });
    const d = dossierById(s.dossierId) as MockDossier;
    s.makeStarted = true;
    save();
    return {
      recommended: s.openQuestion ? 'reader_question' : 'headline_choice',
      options: [
        { kind: 'headline_choice', options: d.headlines.map((h) => ({ id: h.id, text_fr: h.text_fr })) },
        { kind: 'reader_question', seed_fr: s.openQuestion, uncertainty_fr: s.openUncertainty },
      ],
    };
  };

  const why = (lang: Lang, addedLead: boolean) => {
    if (!addedLead) {
      return { en: 'Romy kept your words and set the punctuation.', de: 'Romy behält deine Wörter und setzt die Zeichen.', fr: 'Romy garde tes mots et met la ponctuation.' }[lang];
    }
    return {
      en: '«Est-ce que» turns a sentence into a question, without changing its order.',
      de: '„Est-ce que“ macht aus einem Satz eine Frage, ohne die Wortstellung zu ändern.',
      fr: '« Est-ce que » transforme une phrase en question, sans changer l’ordre.',
    }[lang];
  };

  const make = (id: string, body: Json) => {
    const s = sessionOr404(id);
    if (s.closing) throw httpError(409, { code: 'revue_session_closed' });
    const d = dossierById(s.dossierId) as MockDossier;
    s.makeStarted = true;
    const fileMade = (made: Json) => {
      s.artifact = made;
      const seq = nextSeq(s);
      s.thread.push({ id: String(seq), seq, at: stamp(), kind: 'made', made });
    };
    if (body.action === 'pick') {
      const option = d.headlines.find((h) => h.id === body.option_id);
      if (!option) throw httpError(422, { code: 'revue_unknown_option' });
      const answer = d.headlines.find((h) => h.correct) as MockDossier['headlines'][number];
      const claim = d.claims.find((c) => c.id === d.headline_claim) as MockClaim;
      const correct = option.id === answer.id;
      const made = { kind: 'headline_choice', text_fr: answer.text_fr, contribution: correct ? [[0, answer.text_fr.length]] : [], learner_fr: null };
      fileMade(made);
      save();
      return { kind: 'headline_choice', correct, answer_id: answer.id, evidence: { claim_id: claim.id, quote: claim.quote, source: sourceOf(d, claim.source_id) }, made };
    }
    if (body.action === 'propose') {
      const learner = String(body.text || s.openQuestion || '').trim();
      s.draftLearner = learner;
      const french = looksFrench(learner);
      const q = french ? frenchQuestion(learner) : { fr: d.reader_question_fr, addedLead: false };
      save();
      return {
        kind: 'reader_question',
        draft: {
          learner_fr: learner,
          proposal_fr: q.fr,
          contribution: contributionSpans(q.fr, learner),
          why_native: french ? why(s.language, q.addedLead) : null,
        },
      };
    }
    if (body.action === 'send') {
      const textFr = String(body.text_fr || '').trim();
      if (!textFr) throw httpError(422, [{ loc: ['body', 'text_fr'], msg: 'empty' }]);
      const learner = s.draftLearner || s.openQuestion;
      const made = { kind: 'reader_question', text_fr: textFr, contribution: contributionSpans(textFr, learner ?? textFr), learner_fr: learner ?? textFr };
      fileMade(made);
      save();
      return { kind: 'reader_question', made };
    }
    throw httpError(422, [{ loc: ['body'], msg: 'unknown action' }]);
  };

  const close = (id: string) => {
    const s = sessionOr404(id);
    const d = dossierById(s.dossierId) as MockDossier;
    if (!s.closing) {
      const made = s.artifact;
      const kind = made ? String(made.kind) : 'none';
      const shown = d.claims.filter((c) => s.shown.includes(c.id));
      let headline = d.short_fr;
      let contribution: Array<[number, number]> = [];
      if (made && kind === 'reader_question') {
        const prefix = `${d.short_fr} : `;
        const question = String(made.text_fr);
        const asked = `${question.charAt(0).toLowerCase()}${question.slice(1)}`;
        headline = `${prefix}${asked}`;
        // Only the question is the learner's: Romy's prefix is never marked.
        contribution = contributionSpans(asked, made.learner_fr ?? question).map(([a, b]) => [a + prefix.length, b + prefix.length] as [number, number]);
      } else if (made) {
        headline = String(made.text_fr);
        contribution = (made.contribution as Array<[number, number]>) || [];
      }
      const body = shown.slice(0, 2).map((c) => c.fr);
      while (body.length < 2) body.push(d.claims[body.length].fr);
      body.push(
        kind === 'reader_question'
          ? `Reste une question de lecteur : ${String(made?.text_fr || '').replace(/^Est-ce que /, '').replace(/ \?$/, '')} ?`
          : 'La suite la semaine prochaine, avec les lecteurs.',
      );
      const usedSources = d.sources.filter((src) => shown.some((c) => c.source_id === src.id));
      const sources = (usedSources.length ? usedSources : d.sources).map((src) => sourceOf(d, src.id));
      const mine = s.thread.filter((item) => item.kind === 'mine').map((item) => fold(String(item.text_fr))).join(' ');
      s.closing = {
        romy_line_fr: CLOSE_LINES[kind] ?? CLOSE_LINES.none,
        dispatch: {
          kicker_fr: `Le Papier de Romy · ${WEEK.label.toLowerCase()}`,
          headline_fr: headline,
          body_fr: body,
          contribution,
          byline_fr: `Romy Tremblay, avec toi · d'après ${sources.map((src) => src.name.replace(/\s*\(.*\)$/, '')).join(' et ')}`,
          sources,
        },
        kept: {
          words: d.vocabulary.map((v) => ({ ...glossOf(v, s.language), used: mine.includes(fold(v.fr)) })),
          claims: shown.map((c) => claimWire(d, c)),
        },
        question_kept_fr: kind === 'reader_question' ? null : s.openQuestion,
        colophon_fr: 'La suite la semaine prochaine.',
      };
      s.closedAt = stamp();
      save();
    }
    return { session: viewOf(s), closing: s.closing };
  };

  const route = (method: 'GET' | 'POST', url: string, body: Json): unknown => {
    const path = url.replace(/\?.*$/, '');
    if (method === 'GET' && path === '/revue/week') {
      if (options.disabled) throw httpError(404, 'Not Found');
      return offer();
    }
    if (options.disabled) throw httpError(404, 'Not Found');
    if (method === 'POST' && path === '/revue/match') {
      const d = matchText(String(body.text || ''));
      return d ? { match: d.id, romy_line_fr: null } : { match: null, romy_line_fr: missLine() };
    }
    if (method === 'POST' && path === '/revue/sessions') return start(body);
    const m = path.match(/^\/revue\/sessions\/([^/]+)(?:\/(turns|make|close))?$/);
    if (m) {
      const id = decodeURIComponent(m[1]);
      if (method === 'GET' && !m[2]) return viewOf(sessionOr404(id));
      if (method === 'POST' && m[2] === 'turns') return turn(id, body);
      if (method === 'GET' && m[2] === 'make') return makeOffer(id);
      if (method === 'POST' && m[2] === 'make') return make(id, body);
      if (method === 'POST' && m[2] === 'close') return close(id);
    }
    throw httpError(404, 'Not Found');
  };

  const answer = async (method: 'GET' | 'POST', url: string, body: unknown) => {
    if (latency > 0) await new Promise((resolve) => setTimeout(resolve, latency));
    // A deep copy: the caller never shares objects with the mock's state.
    return JSON.parse(JSON.stringify(route(method, url, (body as Json) || {})));
  };

  return {
    get: (url) => answer('GET', url, null),
    post: (url, body) => answer('POST', url, body),
    reset: () => {
      sessions = {};
      if (persist) {
        try {
          window.sessionStorage.removeItem(STORAGE_KEY);
        } catch {
          /* ignore */
        }
      }
    },
  };
}

/** The mock as a `RevueClient` — the same interface as `revueClient()`. */
export function createMockRevueClient(options: MockOptions = {}): RevueClient & { reset: () => void } {
  const transport = createMockRevueTransport(options);
  return { ...createRevueClient(transport), reset: transport.reset };
}

export const MOCK_DOSSIER_IDS = DOSSIERS.map((d) => d.id);
