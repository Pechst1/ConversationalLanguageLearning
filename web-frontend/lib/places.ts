/**
 * S4 stage 1 — the register of places.
 *
 * Every route under `pages/` is one row here: what the learner calls it in each
 * language, what kind of place it is, which place it belongs to, the one gate that
 * shows it, and where it is opened from. Before this file nobody could answer «what
 * can a learner open today, and from where» without reading the code.
 *
 * What reads it:
 *   · the tab bar and the masthead (`lib/product-shell.ts`: tabs, their lit routes,
 *     the routes that draw their own shell, the Réglages children);
 *   · `components/auth/RouteAuthGate.tsx` (which routes are readable signed out);
 *   · `lib/places.test.js`, which fails when a file in `pages/` is not here, when a
 *     learner place has no entry point, when a dev place could reach a release build,
 *     and when `next.config.js`'s legacy redirects or the native prune list
 *     (`scripts/native-export-policy.mjs`) disagree with this table. Those two are
 *     plain Node files that cannot import TypeScript, so they are checked, not derived.
 *
 * The register does not hide, merge or rename anything. Which places stay is the
 * owner's decision; this is the list it is made from.
 */
import { QUARTIER_VISIBLE, STORY_FEATURE_VISIBLE } from './launch-flags';

export type PlaceLanguage = 'en' | 'de' | 'fr';

/**
 * - `tab`: one of the four tabs.
 * - `child`: opened from a tab (or from Réglages) and belongs to it.
 * - `step`: a full-screen step of the day.
 * - `account`: the front door, sign-in and Réglages.
 * - `legal`: the privacy policy and the terms, readable signed out.
 * - `dev`: a gallery or QA sheet; never in a release build.
 * - `alias`: a page that renders nothing of its own and forwards to `forwardsTo`;
 *   only old links reach it, so it needs no entry point of its own.
 * - `error`: the 404 and 500 pages (S4 stage 2); Next opens them itself.
 */
export type PlaceKind = 'tab' | 'child' | 'step' | 'account' | 'legal' | 'dev' | 'alias' | 'error';

export type PlaceSection = 'atelier' | 'missions' | 'feuilleton' | 'notebook';

/** The one gate that shows a place. */
export type PlaceGate =
  /** Shown to every signed-in learner (or to everyone, if `access` says so). */
  | { kind: 'always' }
  /** A build-time switch in `launch-flags.json`. */
  | { kind: 'launch_flag'; flag: 'storyFeatureVisible' | 'quartierVisible' }
  /**
   * A backend setting. The client does not see it yet: the server answers 404 or
   * leaves the entry out. One client gate across these needs the switches in the
   * today envelope (S4 target structure A, not built in stage 1).
   */
  | { kind: 'server'; setting: string }
  /** The account's role (`GET /users/me` → `role`). */
  | { kind: 'role'; role: 'admin' }
  /** A development build only: `getStaticProps` returns `notFound` in production. */
  | { kind: 'dev_build' };

/** Who may open it: anyone, signed-out only (sign-in, sign-up), or a signed-in learner. */
export type PlaceAccess = 'public' | 'guest_only' | 'signed_in';

/**
 * Where a place is opened from. A file entry names a repo-relative file that must
 * contain the route (or `needle`, when the file builds the path from parts). The
 * other entries are the ways in that no file in this repo holds.
 */
export type PlaceEntry =
  | { file: string; needle?: string }
  | { via: 'tab_bar' | 'start_url' | 'auth_gate' | 'app_store_listing' | 'framework' };

export type Place = {
  /** The Next.js pathname, exactly as `router.pathname` prints it. */
  route: string;
  name: Record<PlaceLanguage, string>;
  kind: PlaceKind;
  parent?: string;
  /** The tab lit while this place is open. */
  section?: PlaceSection;
  /** The page draws its own chrome (no app masthead). */
  ownShell?: boolean;
  access: PlaceAccess;
  gate: PlaceGate;
  entries: PlaceEntry[];
  /** `alias` only: where the page sends the learner. */
  forwardsTo?: string;
};

const file = (path: string, needle?: string): PlaceEntry => (needle ? { file: path, needle } : { file: path });
const ALWAYS: PlaceGate = { kind: 'always' };
const DEV: PlaceGate = { kind: 'dev_build' };
const STORY: PlaceGate = { kind: 'launch_flag', flag: 'storyFeatureVisible' };
const server = (setting: string): PlaceGate => ({ kind: 'server', setting });
const same = (name: string): Record<PlaceLanguage, string> => ({ en: name, de: name, fr: name });

/*
 * The four tab names are French in every language: the learner is reading a French
 * publication (WP-109). So are the names of the paper's own rubrics (La Revue, La
 * Radio, Le Correcteur…). The account places follow the learner's language.
 */
export const PLACES: Place[] = [
  // ── The front door and the account ────────────────────────────────────────
  {
    route: '/',
    name: { en: 'Welcome', de: 'Willkommen', fr: 'Bienvenue' },
    kind: 'account',
    access: 'public',
    gate: ALWAYS,
    entries: [{ via: 'start_url' }],
  },
  {
    route: '/auth/signin',
    name: { en: 'Sign in', de: 'Anmelden', fr: 'Connexion' },
    kind: 'account',
    access: 'guest_only',
    gate: ALWAYS,
    entries: [{ via: 'auth_gate' }, file('web-frontend/pages/index.tsx'), file('web-frontend/lib/session-recovery.ts'), file('web-frontend/pages/settings.tsx')],
  },
  {
    route: '/auth/signup',
    name: { en: 'Create an account', de: 'Konto anlegen', fr: 'Créer un compte' },
    kind: 'account',
    parent: '/auth/signin',
    access: 'guest_only',
    gate: ALWAYS,
    entries: [file('web-frontend/pages/index.tsx'), file('web-frontend/pages/auth/signin.tsx')],
  },
  {
    route: '/auth/forgot-password',
    name: { en: 'Forgot password', de: 'Passwort vergessen', fr: 'Mot de passe oublié' },
    kind: 'account',
    parent: '/auth/signin',
    access: 'public',
    gate: ALWAYS,
    entries: [file('web-frontend/pages/auth/signin.tsx')],
  },
  {
    route: '/settings',
    name: { en: 'Settings', de: 'Einstellungen', fr: 'Réglages' },
    kind: 'account',
    access: 'signed_in',
    gate: ALWAYS,
    entries: [
      file('web-frontend/components/layout/EditorialMasthead.tsx'),
      file('web-frontend/components/layout/ShellCorner.tsx'),
      file('web-frontend/components/avatar/ProfileTab.tsx'),
    ],
  },
  {
    route: '/dossier',
    name: { en: 'Your file', de: 'Deine Akte', fr: 'Ton dossier' },
    kind: 'child',
    parent: '/settings',
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/pages/settings.tsx'), file('web-frontend/components/releve/Releve.tsx'), file('web-frontend/pages/atelier.tsx')],
  },
  {
    route: '/repetition',
    name: { en: 'Rehearsal', de: 'Probe', fr: 'La répétition' },
    kind: 'child',
    parent: '/settings',
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/pages/settings.tsx'), file('web-frontend/lib/can-dos.ts'), file('app/tasks/notifications.py')],
  },
  {
    route: '/pilot-ops',
    name: { en: 'Pilot operations', de: 'Pilotbetrieb', fr: 'Pilotage' },
    kind: 'account',
    parent: '/settings',
    access: 'signed_in',
    gate: { kind: 'role', role: 'admin' },
    entries: [file('web-frontend/pages/settings.tsx')],
  },

  // ── La Une and what opens from it ─────────────────────────────────────────
  {
    route: '/atelier',
    name: same('La Une'),
    kind: 'tab',
    section: 'atelier',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [{ via: 'tab_bar' }],
  },
  {
    route: '/audio-session',
    name: { en: 'Audio session', de: 'Hörsitzung', fr: 'Séance audio' },
    kind: 'step',
    parent: '/atelier',
    section: 'atelier',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/pages/atelier.tsx')],
  },
  {
    route: '/vocabulary/review',
    name: { en: 'Words to review', de: 'Wörter wiederholen', fr: 'Les mots à revoir' },
    kind: 'step',
    parent: '/atelier',
    section: 'atelier',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [
      file('web-frontend/lib/continue-learning.ts'),
      file('web-frontend/components/lexique/MotsDuJour.tsx'),
      file('web-frontend/components/onboarding/FirstDayRoute.tsx'),
      file('web-frontend/pages/vocabulary.tsx'),
    ],
  },
  {
    route: '/bibliotheque',
    name: same('Bibliothèque'),
    kind: 'child',
    parent: '/notebook',
    section: 'atelier',
    ownShell: true,
    access: 'signed_in',
    gate: STORY,
    entries: [file('web-frontend/pages/notebook.tsx'), file('web-frontend/components/stories/ChapterCompletionModal.tsx')],
  },
  {
    route: '/bibliotheque/[storyId]',
    name: same('Bibliothèque'),
    kind: 'child',
    parent: '/bibliotheque',
    section: 'atelier',
    ownShell: true,
    access: 'signed_in',
    gate: STORY,
    entries: [file('web-frontend/components/stories/ChapterCompletionModal.tsx'), file('web-frontend/components/stories/StorySessionLayout.tsx')],
  },
  {
    route: '/bibliotheque/[storyId]/chapter/[chapterId]',
    name: same('Bibliothèque'),
    kind: 'step',
    parent: '/bibliotheque/[storyId]',
    section: 'atelier',
    ownShell: true,
    access: 'signed_in',
    gate: STORY,
    entries: [file('web-frontend/components/stories/ChapterCompletionModal.tsx', '/chapter/')],
  },
  {
    route: '/revue',
    name: same('La Revue'),
    kind: 'step',
    parent: '/atelier',
    ownShell: true,
    access: 'signed_in',
    gate: server('REVUE_ENABLED'),
    entries: [file('web-frontend/components/revue/revue-home.ts')],
  },
  {
    route: '/radio',
    name: same('La Radio'),
    kind: 'step',
    parent: '/atelier',
    ownShell: true,
    access: 'signed_in',
    gate: server('REVUE_RADIO_ENABLED'),
    entries: [file('web-frontend/lib/radio-une.ts')],
  },
  {
    route: '/correcteur',
    name: same('Le Correcteur'),
    kind: 'step',
    parent: '/atelier',
    ownShell: true,
    access: 'signed_in',
    gate: server('REVUE_CORRECTEUR_ENABLED'),
    entries: [file('web-frontend/lib/correcteur-une.ts')],
  },
  {
    route: '/appel',
    name: { en: 'The call', de: 'Der Anruf', fr: 'L’appel' },
    kind: 'step',
    parent: '/atelier',
    ownShell: true,
    access: 'signed_in',
    gate: server('ATELIER_CALLS_ENABLED'),
    entries: [file('web-frontend/components/appels/IncomingCall.tsx'), file('app/services/serial_notifications.py')],
  },
  {
    route: '/fertig',
    name: { en: 'Done for today', de: 'Fertig für heute', fr: 'Fini pour aujourd’hui' },
    kind: 'step',
    parent: '/atelier',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/lib/day-plan.ts'), file('web-frontend/pages/atelier.tsx'), file('app/services/daily_session.py')],
  },
  {
    route: '/placement',
    name: { en: 'Placement', de: 'Einstufung', fr: 'Le placement' },
    kind: 'step',
    parent: '/atelier',
    access: 'signed_in',
    gate: ALWAYS,
    entries: [
      file('web-frontend/components/onboarding/PlacementOfferChip.tsx'),
      file('web-frontend/components/onboarding/PlacementDayEndOffer.tsx'),
      file('web-frontend/pages/settings.tsx'),
      file('web-frontend/pages/dossier.tsx'),
    ],
  },
  {
    route: '/quartier',
    name: same('Le Quartier'),
    kind: 'step',
    parent: '/atelier',
    ownShell: true,
    access: 'signed_in',
    gate: { kind: 'launch_flag', flag: 'quartierVisible' },
    entries: [file('web-frontend/components/atelier-v2/home/HomeScreen.tsx')],
  },
  {
    route: '/mur',
    name: same('Le mur du Mistral'),
    kind: 'child',
    parent: '/atelier',
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/components/cast/items/MurEntry.tsx')],
  },

  // ── Feuilleton ─────────────────────────────────────────────────────────────
  {
    route: '/graphic-novel',
    name: same('Feuilleton'),
    kind: 'tab',
    section: 'feuilleton',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [{ via: 'tab_bar' }],
  },
  {
    route: '/serial',
    name: same('Feuilleton'),
    kind: 'alias',
    parent: '/graphic-novel',
    section: 'feuilleton',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    // The new-episode push still sends `/serial` (app/tasks/notifications.py).
    entries: [file('app/tasks/notifications.py')],
    forwardsTo: '/graphic-novel',
  },
  {
    route: '/serial/cast',
    name: same('Les personnages'),
    kind: 'alias',
    parent: '/graphic-novel',
    section: 'feuilleton',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [],
    forwardsTo: '/graphic-novel',
  },
  {
    route: '/serial/episode',
    name: same('Feuilleton'),
    kind: 'alias',
    parent: '/graphic-novel',
    section: 'feuilleton',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [],
    forwardsTo: '/serial/episode/[index]',
  },
  {
    // Still renders beside the Feuilleton archive that replaced it (S4 flaw 1).
    route: '/serial/episode/[index]',
    name: { en: 'Episode replay', de: 'Folge nachlesen', fr: 'Relire l’épisode' },
    kind: 'child',
    parent: '/graphic-novel',
    section: 'feuilleton',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('app/services/serial.py', '/serial/episode/')],
  },

  // ── Courrier ───────────────────────────────────────────────────────────────
  {
    route: '/missions',
    name: same('Courrier'),
    kind: 'tab',
    section: 'missions',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [{ via: 'tab_bar' }],
  },

  // ── Cahier ─────────────────────────────────────────────────────────────────
  {
    route: '/notebook',
    name: same('Cahier'),
    kind: 'tab',
    section: 'notebook',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [{ via: 'tab_bar' }],
  },
  {
    route: '/grammar',
    name: { en: 'Grammar', de: 'Grammatik', fr: 'La grammaire' },
    kind: 'child',
    parent: '/notebook',
    section: 'notebook',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [
      file('web-frontend/components/mobile/NotebookModeSwitch.tsx'),
      file('web-frontend/components/cahiers/CahierV2.tsx'),
      file('web-frontend/components/atelier-v2/rule/RuleCard.tsx'),
    ],
  },
  {
    route: '/vocabulary',
    name: { en: 'Vocabulary', de: 'Wortschatz', fr: 'Le lexique' },
    kind: 'child',
    parent: '/notebook',
    section: 'notebook',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/components/mobile/NotebookModeSwitch.tsx')],
  },
  {
    route: '/vocabulary/conjugation',
    name: { en: 'Conjugation', de: 'Konjugation', fr: 'La conjugaison' },
    kind: 'child',
    parent: '/vocabulary',
    section: 'notebook',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/pages/vocabulary.tsx')],
  },
  {
    route: '/vocabulary/verification',
    name: { en: 'Level check', de: 'Niveau-Check', fr: 'La vérification' },
    kind: 'step',
    parent: '/vocabulary',
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/components/atelier-v2/band-check/BandCheckEntry.tsx')],
  },
  {
    route: '/eclair',
    name: same('Éclair'),
    kind: 'step',
    parent: '/notebook',
    section: 'notebook',
    ownShell: true,
    access: 'signed_in',
    gate: server('ATELIER_ECLAIR_ENABLED'),
    entries: [file('web-frontend/lib/grammar-map.ts')],
  },
  {
    route: '/carte',
    name: same('La Carte'),
    kind: 'child',
    parent: '/notebook',
    ownShell: true,
    access: 'signed_in',
    gate: server('REVUE_ENABLED'),
    entries: [file('web-frontend/components/carte/CarteBadge.tsx'), file('web-frontend/components/revue/RvClose.tsx')],
  },
  {
    route: '/personnage',
    name: { en: 'Your character', de: 'Deine Figur', fr: 'Ton personnage' },
    kind: 'child',
    parent: '/notebook',
    ownShell: true,
    access: 'signed_in',
    gate: ALWAYS,
    entries: [file('web-frontend/components/avatar/ProfileTab.tsx'), file('web-frontend/lib/onboarding-signup.ts')],
  },

  // ── Legal ──────────────────────────────────────────────────────────────────
  {
    route: '/privacy',
    name: { en: 'Privacy policy', de: 'Datenschutz', fr: 'Confidentialité' },
    kind: 'legal',
    ownShell: true,
    access: 'public',
    gate: ALWAYS,
    entries: [{ via: 'app_store_listing' }, file('web-frontend/pages/settings.tsx', "legalHref('privacy'"), file('web-frontend/components/legal/LegalPage.tsx', 'legalHref(other')],
  },
  {
    route: '/terms',
    name: { en: 'Terms', de: 'Nutzungsbedingungen', fr: 'Conditions d’utilisation' },
    kind: 'legal',
    ownShell: true,
    access: 'public',
    gate: ALWAYS,
    entries: [{ via: 'app_store_listing' }, file('web-frontend/pages/settings.tsx', "legalHref('terms'"), file('web-frontend/components/legal/LegalPage.tsx', 'legalHref(other')],
  },

  // ── Errors (S4 stage 2): readable signed out, drawn without the masthead ──
  {
    route: '/404',
    name: { en: 'Nothing here', de: 'Hier ist nichts', fr: 'Rien ici' },
    kind: 'error',
    ownShell: true,
    access: 'public',
    gate: ALWAYS,
    entries: [{ via: 'framework' }],
  },
  {
    route: '/500',
    name: { en: 'Unavailable', de: 'Nicht verfügbar', fr: 'Indisponible' },
    kind: 'error',
    ownShell: true,
    access: 'public',
    gate: ALWAYS,
    entries: [{ via: 'framework' }],
  },

  // ── Development only (pruned from the native export) ───────────────────────
  ...([
    ['/atelier-v2-gallery', 'public'],
    ['/cameo-gallery', 'public'],
    ['/personnage-gallery', 'public'],
    ['/troupe-vivante', 'public'],
    ['/mobile-visual-qa', 'public'],
    ['/dev/miss-layout', 'public'],
    ['/dev/styleguide', 'signed_in'],
  ] as const).map(([route, access]): Place => ({
    route,
    name: same(route.slice(1)),
    kind: 'dev',
    access,
    gate: DEV,
    entries: [],
  })),
];

/**
 * Old paths that are not pages. `next.config.js` redirects each of them; the
 * register test checks that the two lists are the same and that every target is a
 * place here.
 */
export const LEGACY_PATHS: string[] = [
  '/dashboard',
  '/sessions',
  '/practice',
  '/daily-practice',
  '/progress',
  '/achievements',
  '/almanac',
  '/learn',
  '/learn/:path*',
  '/index',
  '/stories',
  '/stories/:path*',
  '/story/:id',
  '/atelier/auth/signin',
  '/atelier/auth/signup',
];

const BY_ROUTE = new Map(PLACES.map((place) => [place.route, place]));

export function placeFor(route: string): Place | undefined {
  return BY_ROUTE.get(route);
}

/**
 * Whether the page exists in this build at all. Server and role gates are not
 * build gates: the page is built and the server answers.
 */
export function placeInBuild(place: Place): boolean {
  const development = process.env.NODE_ENV !== 'production';
  switch (place.gate.kind) {
    case 'dev_build':
      return development;
    case 'launch_flag':
      return place.gate.flag === 'storyFeatureVisible' ? STORY_FEATURE_VISIBLE : QUARTIER_VISIBLE || development;
    default:
      return true;
  }
}

export function placesInBuild(): Place[] {
  return PLACES.filter(placeInBuild);
}

/** Routes readable without an account (sign-in and sign-up included). */
export function publicRoutes(): string[] {
  return PLACES.filter((place) => place.access !== 'signed_in').map((place) => place.route);
}

/** Routes a signed-in learner is sent away from (back to their callback). */
export function guestOnlyRoutes(): string[] {
  return PLACES.filter((place) => place.access === 'guest_only').map((place) => place.route);
}
