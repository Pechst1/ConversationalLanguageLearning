/**
 * WP-120 phase C · La Carte — the wire of `GET /revue/carte`, parsed.
 *
 * The server answers snake_case (`app/schemas/revue_carte.py`); the client reads
 * camelCase. Parsing is defensive: a pin without numeric coordinates is dropped,
 * unknown precisions fall back to `city`, a malformed vignette becomes `null`
 * (the map then draws a plain pin).
 */

export type CartePrecision = 'exact' | 'city' | 'region';
export type CarteRing = 'headline' | 'question' | 'report';
export type CarteLevel = 'france' | 'idf' | 'paris';
export type CarteLanguage = 'en' | 'de' | 'fr';

export type CarteVignette = {
  ring: CarteRing;
  keptContribution: boolean;
  pictogramSvg: string;
};

export type CartePin = {
  sessionId: string;
  dossierId: string;
  /** ISO week, `2026-W40`. */
  week: string;
  closedAt: string | null;
  placeLabelFr: string;
  lat: number;
  lon: number;
  precision: CartePrecision;
  level: CarteLevel;
  headlineFr: string;
  keptWords: string[];
  contributionKind: string | null;
  contributionFr: string | null;
  /** `[start, end)` character spans of the learner's own words in `contributionFr`. */
  contributionSpans: Array<[number, number]>;
  questionFr: string | null;
  plateUrl: string | null;
  vignette: CarteVignette | null;
};

export type CarteQuartierPlace = {
  id: string;
  nameFr: string;
  labelFr: string;
  lat: number;
  lon: number;
  plateUrl: string | null;
};

export type CarteCounts = { france: number; idf: number; paris: number; unplaced: number };

export type CarteView = {
  pins: CartePin[];
  quartier: CarteQuartierPlace[];
  counts: CarteCounts;
};

export type CarteResult = { enabled: true; view: CarteView } | { enabled: false };

type Raw = Record<string, unknown>;

const isObject = (value: unknown): value is Raw => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
const str = (value: unknown): string => (typeof value === 'string' ? value : value == null ? '' : String(value));
const strOrNull = (value: unknown): string | null => (typeof value === 'string' && value.trim() ? value : null);
const num = (value: unknown): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null);

const PRECISIONS: readonly CartePrecision[] = ['exact', 'city', 'region'];
const RINGS: readonly CarteRing[] = ['headline', 'question', 'report'];
const LEVELS: readonly CarteLevel[] = ['france', 'idf', 'paris'];

export function parseCarteVignette(raw: unknown): CarteVignette | null {
  if (!isObject(raw)) return null;
  const ring = RINGS.includes(raw.ring as CarteRing) ? (raw.ring as CarteRing) : null;
  if (!ring) return null;
  return { ring, keptContribution: raw.kept_contribution === true, pictogramSvg: str(raw.pictogram_svg) };
}

function parseSpans(raw: unknown): Array<[number, number]> {
  if (!Array.isArray(raw)) return [];
  const spans: Array<[number, number]> = [];
  for (const span of raw) {
    if (Array.isArray(span) && span.length === 2) {
      const [a, b] = [num(span[0]), num(span[1])];
      if (a != null && b != null && b > a) spans.push([a, b]);
    }
  }
  return spans;
}

export function parseCartePin(raw: unknown): CartePin | null {
  if (!isObject(raw)) return null;
  const lat = num(raw.lat);
  const lon = num(raw.lon);
  const sessionId = strOrNull(raw.session_id);
  if (lat == null || lon == null || !sessionId) return null;
  return {
    sessionId,
    dossierId: str(raw.dossier_id),
    week: str(raw.week),
    closedAt: strOrNull(raw.closed_at),
    placeLabelFr: str(raw.place_label_fr),
    lat,
    lon,
    precision: PRECISIONS.includes(raw.precision as CartePrecision) ? (raw.precision as CartePrecision) : 'city',
    level: LEVELS.includes(raw.level as CarteLevel) ? (raw.level as CarteLevel) : 'france',
    headlineFr: str(raw.headline_fr),
    keptWords: Array.isArray(raw.kept_words) ? raw.kept_words.map(str).filter(Boolean) : [],
    contributionKind: strOrNull(raw.contribution_kind),
    contributionFr: strOrNull(raw.contribution_fr),
    contributionSpans: parseSpans(raw.contribution_spans),
    questionFr: strOrNull(raw.question_fr),
    plateUrl: strOrNull(raw.plate_url),
    vignette: parseCarteVignette(raw.vignette),
  };
}

export function parseCarteQuartier(raw: unknown): CarteQuartierPlace | null {
  if (!isObject(raw)) return null;
  const lat = num(raw.lat);
  const lon = num(raw.lon);
  const id = strOrNull(raw.id);
  if (lat == null || lon == null || !id) return null;
  return { id, nameFr: str(raw.name_fr), labelFr: str(raw.label_fr) || str(raw.name_fr), lat, lon, plateUrl: strOrNull(raw.plate_url) };
}

export function parseCarteView(raw: unknown): CarteView {
  const body = isObject(raw) ? raw : {};
  const pins = (Array.isArray(body.pins) ? body.pins : []).map(parseCartePin).filter((p): p is CartePin => p !== null);
  const quartier = (Array.isArray(body.quartier) ? body.quartier : [])
    .map(parseCarteQuartier)
    .filter((p): p is CarteQuartierPlace => p !== null);
  const counts = isObject(body.counts) ? body.counts : {};
  return {
    pins,
    quartier,
    counts: {
      france: num(counts.france) ?? pins.length,
      idf: num(counts.idf) ?? pins.filter((p) => p.level !== 'france').length,
      paris: num(counts.paris) ?? pins.filter((p) => p.level === 'paris').length,
      unplaced: num(counts.unplaced) ?? 0,
    },
  };
}

export class CarteError extends Error {
  status: number;

  constructor(status: number) {
    super(`carte ${status}`);
    this.name = 'CarteError';
    this.status = status;
  }
}
