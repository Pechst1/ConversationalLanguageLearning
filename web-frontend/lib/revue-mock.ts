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
 * Phase 2 («Les invités», WIRE §6):
 *   7. the guest: Margaux enters on the price question (from the second learner
 *      turn, with her reason), disagrees once on the learner's next real turn,
 *      and changes her mind after a point the learner makes (a sentence, not a
 *      question); she stands beside Romy in `stage.cast` from her entrance on;
 *   8. fallback reasons: the column-full line is `budget`, a free request that
 *      matches nothing is `no_match`, Romy's «Je ne sais pas encore» is
 *      `knowledge_refused`, and a learner turn containing «[panne]» plays the
 *      model being down (`model_down`, dev only);
 *   9. the rubric (`revue-rubric-v1`): per plan word, fact fit, register note
 *      («vous» to Romy → `vous_to_tu`);
 *  10. make: Romy's `make_intro` (once, on the first GET) and `make_done` lines;
 *      `&band=B1` adds `headline_write` (14 words) and `short_report` (30 s);
 *  11. close mints a WP-120 vignette (ring by what was made, the topic's
 *      authored fallback pictogram from app/services/revue/evergreen/pictograms),
 *      and `GET /revue/vignettes` lists them.
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
  /** `known: false` — no can-do lists the word: a correct use is sent `unscored` (the Credit check). */
  vocabulary: Array<{ fr: string; claim_id: string; en: string; de: string; gloss_fr: string; known?: boolean }>;
  headlines: Array<{ id: string; text_fr: string; correct?: boolean }>;
  headline_claim: string;
  reader_question_fr: string;
  /** Phrases a shown claim contradicts (the rubric's `contradicted`). */
  contradictions?: string[];
  /** Phase 2: the dossier's guest and their scripted lines. */
  guest?: { cast_id: string; enter: string; reason_fr: string; disagree: string; moved: string };
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
    { fr: 'savoir-faire', claim_id: 'c4', en: 'know-how', de: 'Können', gloss_fr: 'talent du métier', known: false },
  ],
  headlines: [
    { id: 'h1', text_fr: "À Aligre, le marché n'ouvre que le dimanche" },
    { id: 'h2', text_fr: 'À Aligre, le marché ouvre six matins sur sept', correct: true },
    { id: 'h3', text_fr: "À Aligre, il n'y a plus de marché couvert" },
  ],
  headline_claim: 'c2',
  reader_question_fr: "Est-ce que les prix au marché sont plus bas qu'au supermarché ?",
  contradictions: ["que le dimanche", 'plus de marché couvert', 'le lundi aussi', 'tous les jours'],
  guest: {
    cast_id: 'margaux_barman',
    enter: "Les prix ? Moi, je viens ici tous les dimanches pour le bar. Ce n'est pas toujours moins cher.",
    reason_fr: 'Elle achète les citrons du bar ici, chaque dimanche.',
    disagree: "Je ne suis pas d'accord. Au marché, on paie aussi la qualité.",
    moved: "Bon. Vu comme ça, tu n'as pas tort.",
  },
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

/** WP-120 · the authored fallback pictograms (app/services/revue/evergreen/pictograms/*.svg, newlines folded). */
const PICTOGRAMS: Record<string, string> = {
  city: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect x="30" y="18" width="40" height="52" rx="2" fill="#C2890F"/><path d="M36 34 Q36 24 50 24 Q64 24 64 34 L64 66 L36 66 Z" fill="#1D3A8A"/><rect x="49" y="24" width="2" height="42" fill="#F1ECE1"/><rect x="36" y="42" width="28" height="2" fill="#F1ECE1"/><rect x="26" y="64" width="48" height="4" rx="1" fill="#14110D"/><rect x="28" y="77" width="44" height="3" rx="1" fill="#14110D"/><rect x="35" y="68" width="2" height="9" fill="#14110D"/><rect x="42" y="68" width="2" height="9" fill="#14110D"/><rect x="49" y="68" width="2" height="9" fill="#14110D"/><rect x="56" y="68" width="2" height="9" fill="#14110D"/><rect x="63" y="68" width="2" height="9" fill="#14110D"/></svg>',
  culture: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M50 38 Q34 30 20 34 L20 72 Q34 68 50 76 Q66 68 80 72 L80 34 Q66 30 50 38 Z" fill="#1D3A8A"/><path d="M48 39 Q36 33 24 36 L24 68 Q36 65 48 71 Z" fill="#F1ECE1"/><path d="M52 39 Q64 33 76 36 L76 68 Q64 65 52 71 Z" fill="#F1ECE1"/><rect x="29" y="44" width="14" height="2" fill="#14110D"/><rect x="29" y="51" width="14" height="2" fill="#14110D"/><rect x="57" y="44" width="14" height="2" fill="#14110D"/><rect x="57" y="51" width="10" height="2" fill="#14110D"/><path d="M62 66 L62 80 L65 77 L68 80 L68 65 Z" fill="#D8321A"/></svg>',
  food: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M36.6 76.2 L76.2 36.6 Q76.9 23.1 63.4 23.8 L23.8 63.4 Q23.1 76.9 36.6 76.2 Z" fill="#C2890F"/><path d="M36.6 76.2 L76.2 36.6 L72.6 33 L33 72.6 Z" fill="#F3C318"/><path d="M34 56.2 L45.6 59.1 L44.8 62.2 L33.2 59.3 Z" fill="#F1ECE1"/><path d="M43.9 46.3 L55.5 49.2 L54.7 52.3 L43.1 49.4 Z" fill="#F1ECE1"/><path d="M53.8 36.4 L65.4 39.3 L64.6 42.4 L53 39.5 Z" fill="#F1ECE1"/></svg>',
  nature: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M50 14 C74 28 78 58 50 82 C22 58 26 28 50 14 Z" fill="#2C6A5D"/><path d="M49 26 L51 26 L51.5 80 L48.5 80 Z" fill="#F1ECE1"/><path d="M50 44 L64 36 L65 38 L50 48 Z" fill="#F1ECE1"/><path d="M50 44 L36 36 L35 38 L50 48 Z" fill="#F1ECE1"/><path d="M50 58 L64 50 L65 52 L50 62 Z" fill="#F1ECE1"/><path d="M50 58 L36 50 L35 52 L50 62 Z" fill="#F1ECE1"/><path d="M48.5 80 L51.5 80 L52.5 88 L47.5 88 Z" fill="#14110D"/></svg>',
  politics: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect x="40" y="18" width="20" height="26" fill="#F1ECE1" stroke="#14110D" stroke-width="2"/><path d="M45 24 L47 24 L55 34 L53 34 Z" fill="#D8321A"/><path d="M53 24 L55 24 L47 34 L45 34 Z" fill="#D8321A"/><rect x="24" y="42" width="52" height="36" rx="2" fill="#1D3A8A"/><rect x="20" y="38" width="60" height="8" rx="2" fill="#14110D"/><rect x="38" y="40.5" width="24" height="3" fill="#F1ECE1"/><rect x="40" y="56" width="20" height="12" rx="2" fill="#F1ECE1"/></svg>',
  sport: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="34" fill="#F1ECE1" stroke="#14110D" stroke-width="3"/><path d="M50 40 L59.5 46.9 L55.9 58.1 L44.1 58.1 L40.5 46.9 Z" fill="#14110D"/><path d="M50 18.5 L56.2 23 L53.8 30.3 L46.2 30.3 L43.8 23 Z" fill="#14110D"/><path d="M80 40.3 L77.6 47.5 L70 47.5 L67.6 40.3 L73.8 35.8 Z" fill="#14110D"/><path d="M68.5 75.5 L60.9 75.5 L58.5 68.2 L64.7 63.7 L70.9 68.2 Z" fill="#14110D"/><path d="M31.5 75.5 L29.1 68.2 L35.3 63.7 L41.5 68.2 L39.1 75.5 Z" fill="#14110D"/><path d="M20 40.3 L26.2 35.8 L32.4 40.3 L30 47.5 L22.4 47.5 Z" fill="#14110D"/></svg>',
  work: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M22 62 C22 32 78 32 78 62 Z" fill="#F3C318"/><rect x="45" y="38" width="10" height="24" rx="3" fill="#C2890F"/><rect x="16" y="60" width="68" height="8" rx="4" fill="#C2890F"/><rect x="26" y="70" width="48" height="3" rx="1.5" fill="#14110D"/><circle cx="34" cy="53" r="4" fill="#1D3A8A"/></svg>',
};

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
  headline_write: 'Ton titre part tel quel avec mon papier. Je n’y touche pas.',
  short_report: 'Ton reportage part avec mon papier. À Montréal, on va t’entendre.',
  none: "Les sources ne m'ont pas tout dit, mais on a de quoi écrire trois lignes.",
};
// Phase 2 · Romy's lines around the make (WIRE §6.4).
const INTRO_LINES: Record<string, string> = {
  headline_choice: "Il me faut un titre. J'en ai trois : un seul dit vrai.",
  headline_write: "Il me faut un titre. Tu l'écris ? Court, et vrai.",
  reader_question: "Ta question, on la pose aux lecteurs ? On l'écrit ensemble.",
  short_report: 'Raconte-moi ce que tu vois, trente secondes, comme à la radio.',
};
const DONE_LINES = {
  pick_right: "Je le prends. C'est notre titre.",
  pick_wrong: "Je garde celui-là : c'est ce que disent les sources.",
  send: "C'est parti pour la rédaction.",
  write: "Je le prends. C'est ton titre.",
  write_rejected: 'Attention : les sources disent autre chose. Tu réessaies ?',
  report: "C'est enregistré. Je le mets dans mon papier.",
};
const HEADLINE_WORDS = 14;
const REPORT_SECONDS = 30;
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
  /** Phase 2: the guest on stage (one per Papier). */
  guest?: { castId: string; lines: number; disagreed: boolean; moved: boolean } | null;
  /** Phase 2: Romy's make intro, written once on the first GET. */
  intro?: Json | null;
  /** WP-120: the vignette minted at the close. */
  vignette?: Json | null;
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
  const stageOf = (d: MockDossier, s?: MockSession) => ({
    place_id: d.place.id,
    place_fr: d.place.name_fr,
    plate_url: d.place.plate,
    plate_place_id: d.place.plate_place_id,
    place_is_real: d.place.real,
    dress: d.place.dress,
    // A guest on stage stands right after Romy (WIRE §1, phase 2).
    cast: [
      { id: 'romy_tremblay', hold: 'notebook' },
      ...(s?.guest ? [{ id: s.guest.castId, hold: null }] : []),
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
  const isB1 = (s: MockSession) => s.band === 'B1' || s.band === 'B2';
  const line = (s: MockSession, d: MockDossier, seq: number, role: string, text: string, suffix = '', reason: string | null = null) => {
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
      reason,
    };
  };

  /** WIRE §6.3 · the rubric, scripted: plan words, fact fit, register. */
  const grade = (s: MockSession, d: MockDossier, text: string, question: boolean) => {
    const folded = fold(text);
    const wordRows = d.vocabulary.map((v) => {
      const used = folded.includes(fold(v.fr));
      const known = v.known !== false;
      // The Credit check: a correct use no can-do lists is `unscored`, never mastery.
      return { fr: v.fr, outcome: used && known ? 'correct' : 'unscored', capability_known: known };
    });
    const contradicted = (d.contradictions ?? []).some((phrase) => folded.includes(fold(phrase)));
    const supported = d.claims.some((c) => overlap(text, c.fr) >= 2);
    const factFit = contradicted ? 'contradicted' : question ? 'not_applicable' : supported ? 'supported' : words(text).length >= 3 ? 'unsupported' : 'not_applicable';
    const anyRight = wordRows.some((w) => w.outcome === 'correct');
    const usedKnown = d.vocabulary.some((v) => v.known !== false && folded.includes(fold(v.fr)));
    const vous = /(^|[^a-z])vous([^a-z]|$)/.test(folded.replace(/s'il vous plait/g, ''));
    return {
      outcome: contradicted ? 'incorrect' : anyRight ? 'correct' : 'unscored',
      capability_known: usedKnown,
      grader: 'revue-rubric-v1',
      words: wordRows,
      fact_fit: factFit,
      register_note: vous ? 'vous_to_tu' : 'ok',
    };
  };
  const guestItem = (s: MockSession, d: MockDossier, move: string, text: string, position: string, reasonFr: string | null = null) => {
    const seq = nextSeq(s);
    return { id: String(seq), seq, at: stamp(), kind: 'guest', cast_id: d.guest?.cast_id ?? 'margaux_barman', text_fr: text, move, position, reason_fr: reasonFr, reason: null, glosses: glossesIn(s, d, text) };
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
        make_options: isB1(s) ? ['headline_choice', 'headline_write', 'reader_question', 'short_report'] : ['headline_choice', 'reader_question'],
        budget: { turns: BUDGET_TURNS, minutes: 12 },
      },
      stage: stageOf(d, s),
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
      guest: null,
      intro: null,
      vignette: null,
    };
    const seq = nextSeq(s);
    const at = stamp();
    d.narration.forEach((text, index) => s.thread.push({ id: `${seq}.n${index}`, seq, at, kind: 'narration', text_fr: text }));
    if (d.place_note && !d.place.real) s.thread.push(line(s, d, seq, 'place_note', d.place_note, '.p'));
    if (miss) s.thread.push(line(s, d, seq, 'fallback', missLine(), '.m', 'no_match'));
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
    const reply = (text_fr: string, role = 'reply', reason: string | null = null) => {
      const seq = nextSeq(s);
      items.push(line(s, d, seq, role, text_fr, '', reason));
      return seq;
    };
    const unshown = d.claims.filter((c) => !s.shown.includes(c.id));
    const question = /\?\s*$/.test(text) || /^(est-ce|pourquoi|comment|combien|quand|qui|quel)/.test(folded);

    const modelDown = text.includes('[panne]');
    let confusedTurn = false;
    let formulateTurn = false;
    if (wasBoucle) {
      // After 100 % Romy no longer calls the model: she keeps the question (WIRE §6: `fallback`, `budget`).
      if (question) s.openQuestion = text;
      reply(KEPT_LINE, 'fallback', 'budget');
    } else if (modelDown) {
      // Dev only: the provider is down. Her authored line, the reason coded.
      reply(FALLBACK_LINE, 'fallback', 'model_down');
    } else if (/comprends pas|pas compris|plus simple|je comprends rien/.test(folded)) {
      confusedTurn = true;
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
      formulateTurn = true;
      s.confused = 0;
      reply("D'accord. Écris-la comme elle te vient, même dans ta langue : je t'aide pour le français.");
      flags.proposes = true;
    } else if (!s.shown.length) {
      s.confused = 0;
      reply('Merci ! Voilà ce qu’on sait.');
      showClaims(s, d, d.claims.slice(0, 2).map((c) => c.id), items);
    } else if (question && (folded.includes('prix') || d.uncertainties.some((u) => overlap(text, u) >= 2))) {
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
        if (unshown[0]) reply('Je note. Et tu savais ça ?');
        else reply(FALLBACK_LINE, 'fallback', 'knowledge_refused');
        if (unshown[0]) showClaims(s, d, [unshown[0].id], items);
      }
    }

    // The guest (WIRE §6.2): enters in `pursue` only, never once the column is full;
    // then a follow-up / a disagreement / a change of mind, at most three lines.
    const g = d.guest;
    const quick = [QR_AGREE, QR_MORE, QR_FORMULATE, QR_UNDERSTOOD, QR_SIMPLER].some((q) => fold(q.send_fr) === folded);
    if (g && !wasBoucle && !modelDown) {
      if (!s.guest && flags.uncertainty && s.turnsUsed >= 2) {
        s.guest = { castId: g.cast_id, lines: 0, disagreed: false, moved: false };
        items.push(guestItem(s, d, 'enter', g.enter, 'against', g.reason_fr));
      } else if (s.guest && !s.guest.moved && s.guest.lines < 3 && !quick && !formulateTurn && !confusedTurn) {
        if (!s.guest.disagreed) {
          s.guest.disagreed = true;
          s.guest.lines += 1;
          items.push(guestItem(s, d, 'disagree', g.disagree, 'against'));
        } else if (!question && words(text).length >= 4) {
          s.guest.moved = true;
          s.guest.lines += 1;
          items.push(guestItem(s, d, 'moved', g.moved, 'moved'));
        }
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
      evidence: grade(s, d, text, question),
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
    const b1 = isB1(s);
    const recommended = s.openQuestion ? 'reader_question' : b1 ? 'headline_write' : 'headline_choice';
    // Romy's intro is written once, on the first GET, and replays as a thread item.
    if (!s.intro) {
      const seq = nextSeq(s);
      s.intro = line(s, d, seq, 'make_intro', INTRO_LINES[recommended]);
      s.thread.push(s.intro);
    }
    save();
    return {
      recommended,
      options: [
        { kind: 'headline_choice', options: d.headlines.map((h) => ({ id: h.id, text_fr: h.text_fr })) },
        ...(b1 ? [{ kind: 'headline_write', max_words: HEADLINE_WORDS }] : []),
        { kind: 'reader_question', seed_fr: s.openQuestion, uncertainty_fr: s.openUncertainty },
        ...(b1 ? [{ kind: 'short_report', seconds: REPORT_SECONDS }] : []),
      ],
      intro: s.intro,
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
    const done = (text: string) => {
      const seq = nextSeq(s);
      const item = line(s, d, seq, 'make_done', text);
      s.thread.push(item);
      return item;
    };
    if ((body.kind === 'headline_write' || body.kind === 'short_report') && !isB1(s)) {
      throw httpError(409, { code: 'revue_make_unavailable', kind: body.kind });
    }
    if (body.action === 'pick') {
      const option = d.headlines.find((h) => h.id === body.option_id);
      if (!option) throw httpError(422, { code: 'revue_unknown_option' });
      const answer = d.headlines.find((h) => h.correct) as MockDossier['headlines'][number];
      const claim = d.claims.find((c) => c.id === d.headline_claim) as MockClaim;
      const correct = option.id === answer.id;
      const made = { kind: 'headline_choice', text_fr: answer.text_fr, contribution: correct ? [[0, answer.text_fr.length]] : [], learner_fr: null };
      fileMade(made);
      const doneLine = done(correct ? DONE_LINES.pick_right : DONE_LINES.pick_wrong);
      save();
      return { kind: 'headline_choice', correct, answer_id: answer.id, evidence: { claim_id: claim.id, quote: claim.quote, source: sourceOf(d, claim.source_id) }, made, line: doneLine };
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
      const doneLine = done(DONE_LINES.send);
      save();
      return { kind: 'reader_question', made, line: doneLine };
    }
    if (body.action === 'write') {
      const textFr = String(body.text_fr || '').trim();
      if (!textFr || textFr.length > 160) throw httpError(422, [{ loc: ['body', 'text_fr'], msg: 'invalid' }]);
      const evidence = grade(s, d, textFr, false);
      if (evidence.fact_fit === 'contradicted') {
        // Not filed: a shown claim contradicts it. Romy says so; the learner writes again.
        const doneLine = done(DONE_LINES.write_rejected);
        save();
        return { kind: 'headline_write', accepted: false, evidence, made: null, line: doneLine };
      }
      const made = { kind: 'headline_write', text_fr: textFr, contribution: [[0, textFr.length]], learner_fr: textFr };
      fileMade(made);
      const doneLine = done(DONE_LINES.write);
      save();
      return { kind: 'headline_write', accepted: true, evidence, made, line: doneLine };
    }
    if (body.action === 'report') {
      const transcript = String(body.transcript || '').trim();
      if (!transcript || transcript.length > 1200) throw httpError(422, [{ loc: ['body', 'transcript'], msg: 'invalid' }]);
      const evidence = grade(s, d, transcript, false);
      const made = { kind: 'short_report', text_fr: transcript, contribution: [[0, transcript.length]], learner_fr: transcript };
      fileMade(made);
      const doneLine = done(DONE_LINES.report);
      save();
      return { kind: 'short_report', evidence, made, line: doneLine };
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
      } else if (made && kind !== 'short_report') {
        headline = String(made.text_fr);
        contribution = (made.contribution as Array<[number, number]>) || [];
      }
      // A report is not a headline: the dispatch keeps Romy's own, and quotes the report.
      const reported = kind === 'short_report' ? String(made?.text_fr || '').split(/(?<=[.!?])\s/)[0].split(/\s+/).slice(0, 20).join(' ') : '';
      const body = shown.slice(0, 2).map((c) => c.fr);
      while (body.length < 2) body.push(d.claims[body.length].fr);
      body.push(
        kind === 'reader_question'
          ? `Reste une question de lecteur : ${String(made?.text_fr || '').replace(/^Est-ce que /, '').replace(/ \?$/, '')} ?`
          : kind === 'short_report'
            ? `Sur place, un lecteur raconte : « ${reported.replace(/[.!?]$/, '')} ».`
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
      // WP-120 §4.3: the close mints the vignette (ring by what was made).
      s.vignette = {
        id: `vig-${s.id}`,
        session_id: s.id,
        dossier_id: d.id,
        week: WEEK.iso,
        place_label_fr: d.place.name_fr.split(',')[0],
        ring: kind === 'reader_question' ? 'question' : kind === 'short_report' ? 'report' : 'headline',
        kept_contribution: kind === 'short_report' ? true : contribution.length > 0,
        pictogram_svg: PICTOGRAMS[d.topic] ?? PICTOGRAMS.city,
        headline_fr: headline,
        minted_at: stamp(),
      };
      s.closing.vignette = s.vignette;
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
    if (method === 'GET' && path === '/revue/vignettes') {
      const minted = allSessions()
        .map((row) => row.vignette)
        .filter((v): v is Json => Boolean(v))
        .sort((a, b) => String(b.minted_at).localeCompare(String(a.minted_at)));
      return { vignettes: minted };
    }
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
