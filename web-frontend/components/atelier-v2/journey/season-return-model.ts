/**
 * WP-98 «La saison suivante» and WP-99 «Le facteur et les dépêches» — the
 * pure half.
 *
 * Three editorial states the day can open on, read defensively from payloads
 * that older servers send without them:
 *
 *   · «Entre-temps» (`journey.absence`) — a returning learner reads one page,
 *     «Pendant votre absence», before the day's first step: a greeting with a
 *     face, up to five dated lines of what happened meanwhile, and the letters
 *     that lapsed («courrier en souffrance»). Once per journey, never day 1.
 *   · «Nouvelle saison» (`season_premiere`) — the day's first screen is a front
 *     page: «Saison N», the title, the logline, a poster cut from the day's
 *     first panel (art that already exists; nothing is generated for it).
 *   · The interlude (`interlude`) — between two seasons Home says so honestly,
 *     with the date the story comes back, and offers the practice that exists.
 *
 * Also here: which teaser «La suite demain» prints (the engine's
 * `next_teaser_fr` first), and where a tapped push lands (`lib/push-deep-link`
 * holds the route table; this file holds none of it).
 *
 * No React, no storage of its own (the storage is passed in), no network —
 * `season-return.test.js` pins every rule.
 */

import type { ControlLanguage, JourneyRecap, RecapTeaser } from '@/types/daily-journey';

// ---------------------------------------------------------------------------
// Readers
// ---------------------------------------------------------------------------

const text = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');
const textOrNull = (value: unknown): string | null => text(value) || null;
const list = (value: unknown): any[] => (Array.isArray(value) ? value : []);
const DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** A learner-local `YYYY-MM-DD` (the first ten characters of an ISO stamp), or `null`. */
export function calendarDate(value: unknown): string | null {
  const raw = text(value).slice(0, 10);
  const match = raw.match(DATE);
  if (!match) return null;
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return raw;
}

// ---------------------------------------------------------------------------
// «Entre-temps» — WP-99
// ---------------------------------------------------------------------------

/** At most five lines of what happened meanwhile — a page, never a feed. */
export const ENTRE_TEMPS_MAX_LINES = 5;

export type EntreTempsLine = {
  textFr: string;
  /** YYYY-MM-DD, or `null` when the server sent no readable date. */
  date: string | null;
  characterId: string | null;
};

export type LapsedLetter = {
  missionId: string;
  /** '' when the server could not name the correspondent. */
  correspondentName: string;
  /** The letter in the Courrier. */
  href: string;
};

export type AbsenceView = {
  days: number;
  greetingFr: string | null;
  /** Whose greeting it is — for the face. `null` prints the greeting without one. */
  characterId: string | null;
  characterName: string | null;
  lines: EntreTempsLine[];
  letters: LapsedLetter[];
};

type AbsenceSource = {
  absence?: unknown;
  scenario?: { character_id?: string | null; character_name?: string | null } | null;
} | null | undefined;

/** The Courrier's own address for one letter (the same `courrier-waiting` uses). */
export function courrierLetterHref(missionId: string | number | null | undefined): string {
  const id = text(missionId === null || missionId === undefined ? '' : String(missionId));
  return id ? `/missions?mission=${encodeURIComponent(id)}` : '/missions';
}

/**
 * The absence a snapshot carries, or `null`.
 *
 * `null` too when there is nothing to print: an absence with no greeting, no
 * line and no lapsed letter would be an empty page with a button on it. Lines
 * are sorted oldest first (a chronicle reads forward) and cut at five, keeping
 * the most recent five; a line without a readable date counts as the oldest.
 */
export function absenceOf(source: AbsenceSource): AbsenceView | null {
  const raw = source?.absence;
  if (!raw || typeof raw !== 'object') return null;
  const absence = raw as Record<string, unknown>;
  const days = Math.max(0, Math.trunc(Number(absence.days) || 0));
  const greetingFr = textOrNull(absence.greeting_fr);
  const lines = list(absence.entre_temps)
    .map((line: any): EntreTempsLine | null => {
      const textFr = text(line?.text_fr);
      if (!textFr) return null;
      return { textFr, date: calendarDate(line?.date), characterId: textOrNull(line?.character_id) };
    })
    .filter((line): line is EntreTempsLine => Boolean(line));
  // Undated lines (an older server) read first, as the oldest; dated lines
  // follow in date order (a stable sort keeps same-day lines as sent).
  const ordered = [
    ...lines.filter((line) => !line.date),
    ...lines.filter((line) => line.date).sort((a, b) => (a.date! < b.date! ? -1 : a.date! > b.date! ? 1 : 0)),
  ].slice(-ENTRE_TEMPS_MAX_LINES);
  const seen = new Set<string>();
  const letters = list(absence.lapsed_letters)
    .map((letter: any): LapsedLetter | null => {
      const missionId = text(letter?.mission_id === undefined || letter?.mission_id === null ? '' : String(letter.mission_id));
      const correspondentName = text(letter?.correspondent_name);
      if (!missionId || seen.has(missionId)) return null;
      seen.add(missionId);
      return { missionId, correspondentName, href: courrierLetterHref(missionId) };
    })
    .filter((letter): letter is LapsedLetter => Boolean(letter));
  if (!greetingFr && !ordered.length && !letters.length) return null;
  // Whose face: the absence's own speaker when the server names one, else
  // the day's counterpart (who greets the learner back into the scene).
  const characterId =
    textOrNull(absence.character_id) ?? (greetingFr ? textOrNull(source?.scenario?.character_id) : null);
  const characterName =
    textOrNull(absence.character_name) ?? (greetingFr ? textOrNull(source?.scenario?.character_name) : null);
  return { days, greetingFr, characterId, characterName, lines: ordered, letters };
}

// ---------------------------------------------------------------------------
// «Nouvelle saison» — WP-98
// ---------------------------------------------------------------------------

export type SeasonPremiereView = {
  number: number;
  titleFr: string;
  loglineFr: string | null;
};

/** The premiere a payload carries, or `null`. A premiere without a number or a title is none. */
export function seasonPremiereOf(source: { season_premiere?: unknown } | null | undefined): SeasonPremiereView | null {
  const raw = source?.season_premiere;
  if (!raw || typeof raw !== 'object') return null;
  const premiere = raw as Record<string, unknown>;
  const number = Math.trunc(Number(premiere.number));
  const titleFr = text(premiere.title_fr);
  if (!Number.isFinite(number) || number < 1 || !titleFr) return null;
  return { number, titleFr, loglineFr: textOrNull(premiere.logline_fr) };
}

type TodaySource = {
  season_premiere?: unknown;
  interlude?: unknown;
  journey?: { season_premiere?: unknown; interlude?: unknown } | null;
} | null | undefined;

/** Today's premiere: the journey's once it exists, else the envelope's own. */
export function todayPremiere(
  envelope: TodaySource,
  journey?: { season_premiere?: unknown } | null,
): SeasonPremiereView | null {
  return (
    seasonPremiereOf(journey ?? null)
    ?? seasonPremiereOf(envelope?.journey ?? null)
    ?? seasonPremiereOf(envelope ?? null)
  );
}

type PanelLike = { image_url?: string | null } | null | undefined;
type StepLike = { kind?: string; prompt?: unknown };

/**
 * The poster: the day's first panel, art that already exists. In order — the
 * story episode's first drawn panel, the first scene's own first panel, the
 * scene's image, the scenario's. `null` when none exists: the front page then
 * prints without a poster, never with a placeholder.
 */
export function premierePoster(
  journey: { steps?: StepLike[] | null; scenario?: { image_url?: string | null } | null } | null | undefined,
  episodePanels?: PanelLike[] | null,
): string | null {
  const fromEpisode = list(episodePanels).map((panel) => textOrNull(panel?.image_url)).find(Boolean);
  if (fromEpisode) return fromEpisode;
  const scene = list(journey?.steps).find((step: StepLike) => step?.kind === 'scene') as StepLike | undefined;
  const prompt = (scene?.prompt ?? null) as { image_url?: unknown; panels?: unknown } | null;
  const fromPanels = list(prompt?.panels).map((panel: PanelLike) => textOrNull(panel?.image_url)).find(Boolean);
  return fromPanels ?? textOrNull(prompt?.image_url) ?? textOrNull(journey?.scenario?.image_url);
}

// ---------------------------------------------------------------------------
// The interlude — WP-98
// ---------------------------------------------------------------------------

export type InterludeView = {
  /** YYYY-MM-DD: the day the story comes back; `null` when the server has none to give. */
  returnsOn: string | null;
  /** One French line on why — story, printed as such. */
  reasonFr: string | null;
};

/**
 * The interlude a payload carries, or `null`. With a readable return date the
 * card says «l’histoire reprend le …»; without one it says only that the
 * serial is taking a break — never a date it was not given.
 */
export function interludeOf(source: { interlude?: unknown } | null | undefined): InterludeView | null {
  const raw = source?.interlude;
  if (!raw || typeof raw !== 'object') return null;
  const interlude = raw as Record<string, unknown>;
  return { returnsOn: calendarDate(interlude.returns_on), reasonFr: textOrNull(interlude.reason_fr) };
}

/** The interlude's one headline, in the chrome language: the date when there is one. */
export function interludeHeadline(
  interlude: InterludeView,
  copy: { interlude_returns: string; interlude_paused: string },
  language: unknown,
): string {
  const date = interlude.returnsOn ? longDate(interlude.returnsOn, language) : '';
  return date ? copy.interlude_returns.replace('{date}', date) : copy.interlude_paused;
}

/** Today's interlude: the envelope's, else the journey's. */
export function todayInterlude(envelope: TodaySource, journey?: { interlude?: unknown } | null): InterludeView | null {
  return interludeOf(envelope ?? null) ?? interludeOf(journey ?? null) ?? interludeOf(envelope?.journey ?? null);
}

export type InterludePractice = { id: 'forge' | 'courrier' | 'relecture'; href: string };

/**
 * What there is to do between two seasons — only what exists: La Forge when
 * the server offers today's block, the Courrier, and the archive to reread.
 */
export function interludePractice(forgeHref: string | null | undefined): InterludePractice[] {
  const forge = text(forgeHref);
  return [
    ...(forge.startsWith('/') ? [{ id: 'forge' as const, href: forge }] : []),
    { id: 'courrier', href: '/missions' },
    { id: 'relecture', href: '/graphic-novel' },
  ];
}

// ---------------------------------------------------------------------------
// Dates in words
// ---------------------------------------------------------------------------

const MONTHS: Record<ControlLanguage, string[]> = {
  fr: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  de: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
};

function lang(language: unknown): ControlLanguage {
  const raw = text(language).slice(0, 2).toLowerCase();
  return raw === 'en' || raw === 'de' ? raw : 'fr';
}

/**
 * «12 octobre» / «October 12» / «12. Oktober», and «1er octobre» on the first.
 * Read as a calendar date, never through `Date`, so no timezone can move it.
 * An unreadable date is ''.
 */
export function longDate(date: unknown, language: unknown = 'fr'): string {
  const value = calendarDate(date);
  if (!value) return '';
  const [, month, day] = value.split('-').map(Number);
  const l = lang(language);
  const name = MONTHS[l][month - 1];
  if (l === 'en') return `${name} ${day}`;
  if (l === 'de') return `${day}. ${name}`;
  return `${day === 1 ? '1er' : day} ${name}`;
}

// ---------------------------------------------------------------------------
// Which page opens the day — the prelude
// ---------------------------------------------------------------------------

export type DayPrelude = 'entre_temps' | 'premiere';

type PreludeJourney = {
  id?: string;
  status?: string;
  current_step_id?: string | null;
  steps?: Array<{ id?: string; status?: string }> | null;
  cast_intro?: unknown;
  absence?: unknown;
  season_premiere?: unknown;
  scenario?: { character_id?: string | null; character_name?: string | null } | null;
} | null | undefined;

/** The day has not moved yet: its first step is the open one and nothing is resolved. */
export function journeyAtFirstStep(journey: PreludeJourney): boolean {
  const steps = list(journey?.steps);
  if (!journey || journey.status !== 'active' || !steps.length) return false;
  if (steps.some((step) => step?.status === 'completed' || step?.status === 'skipped')) return false;
  return Boolean(journey.current_step_id) && steps[0]?.id === journey.current_step_id;
}

/**
 * The pages to show before the day's first step, in order: «Entre-temps»
 * first (the learner is welcomed back), then the season's front page.
 *
 *   · never on day 1 (the cast is being introduced; there is no «meanwhile»);
 *   · only while the day stands at its first step (a resume goes straight on);
 *   · each once per journey (`seen`), so «Plus tard» or a reload never loops.
 */
export function dayPreludes(journey: PreludeJourney, seen: (kind: DayPrelude) => boolean): DayPrelude[] {
  if (!journeyAtFirstStep(journey)) return [];
  const firstDay = Array.isArray(journey?.cast_intro) && journey!.cast_intro.length > 0;
  const out: DayPrelude[] = [];
  if (!firstDay && absenceOf(journey ?? null) && !seen('entre_temps')) out.push('entre_temps');
  if (seasonPremiereOf(journey ?? null) && !seen('premiere')) out.push('premiere');
  return out;
}

type StorageLike = Pick<Storage, 'getItem' | 'setItem'> | null | undefined;

const SEEN_PREFIX = 'atelier.prelude.';

export function preludeKey(kind: DayPrelude, journeyId: string): string {
  return `${SEEN_PREFIX}${kind}.${journeyId}`;
}

/** Device memory: has this page been read (or skipped) for this journey? Unreadable → not seen. */
export function preludeSeen(storage: StorageLike, kind: DayPrelude, journeyId: string | null | undefined): boolean {
  if (!journeyId) return false;
  try {
    return storage?.getItem(preludeKey(kind, journeyId)) === '1';
  } catch {
    return false;
  }
}

export function rememberPreludeSeen(storage: StorageLike, kind: DayPrelude, journeyId: string | null | undefined): void {
  if (!journeyId) return;
  try {
    storage?.setItem(preludeKey(kind, journeyId), '1');
  } catch {
    // Not remembered: the page may show once more on a reload. Harmless.
  }
}

// ---------------------------------------------------------------------------
// «La suite demain» — the teaser the recap and Home print
// ---------------------------------------------------------------------------

/**
 * The teaser for tomorrow, the engine's own first. WP-99's engine writes
 * `next_teaser_fr` per resolution (guarded to name an open thread); an older
 * recap carries only `teaser` (engine → resolution → authored). The speaker of
 * the structured teaser signs the engine's line when there is one.
 */
export function recapTeaserOf(recap: (JourneyRecap & { next_teaser_fr?: unknown }) | null | undefined): RecapTeaser | null {
  if (!recap) return null;
  const structured = recap.teaser && text(recap.teaser.text_fr) ? recap.teaser : null;
  const engine = text(recap.next_teaser_fr);
  if (engine) {
    return {
      text_fr: engine,
      character_id: structured?.character_id ?? null,
      character_name: structured?.character_name ?? null,
      source: 'engine',
    };
  }
  return structured;
}
