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
  /** WP-121: the dossier place (the review's key). */
  placeId: string | null;
  /** WP-121 A.2: due words met here (on the place's newest pin only). */
  dueWords: number;
  /** WP-121 B: «Relire ta question» (eligible) or «Relue le …» (read). */
  relecture: CarteRelectureMark | null;
};

export type CarteRelectureMark = { state: 'eligible' | 'read'; readAt: string | null };

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
  /** WP-121 A.2: every due word met in a pinned Papier. */
  dueTotal: number;
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
    placeId: strOrNull(raw.place_id),
    dueWords: Math.max(0, Math.floor(num(raw.due_words) ?? 0)),
    relecture: parseRelectureMark(raw.relecture),
  };
}

export function parseRelectureMark(raw: unknown): CarteRelectureMark | null {
  if (!isObject(raw) || (raw.state !== 'eligible' && raw.state !== 'read')) return null;
  return { state: raw.state, readAt: strOrNull(raw.read_at) };
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
    dueTotal: num(body.due_total) ?? pins.reduce((sum, p) => sum + p.dueWords, 0),
  };
}

// ---------------------------------------------------------------------------
// WP-121 A.3 · reviewing «ici» (`GET /revue/carte/review/{place_id}`, `POST …/grade`)
// ---------------------------------------------------------------------------

export type CarteReviewFormat = 'match_pairs' | 'word_bank' | 'unscramble' | 'dictation';

export type CarteReviewWord = {
  progressId: string;
  wordId: number;
  word: string;
  gloss: string;
  /** The claim the word was kept with. */
  sentenceFr: string;
  /** Who carried the word in the thread, and the line. */
  speakerId: string;
  speakerName: string;
  lineFr: string;
  sessionId: string;
  week: string;
};

export type CarteReviewOption = { id: string; text_fr: string; side: 'fr' | 'native' | null };

export type CarteReviewItem = {
  id: string;
  taskType: CarteReviewFormat;
  progressIds: string[];
  promptFr: string | null;
  /** snake_case on purpose: the journey's recall components read `RecallOption`. */
  options: CarteReviewOption[];
  answerKey: { version: number; salt: string; digests: string[] } | null;
  audioUrl: string | null;
};

export type CarteReview = {
  placeId: string;
  placeLabelFr: string;
  plateUrl: string | null;
  week: string;
  headlineFr: string | null;
  words: CarteReviewWord[];
  items: CarteReviewItem[];
};

export type CarteReviewResult = { progressId: string; wordId: number; correct: boolean; rating: number; dueAt: string | null };

export type CarteReviewGrade = { itemId: string; taskType: string; results: CarteReviewResult[]; remaining: number };

export type CarteReviewAnswer = { itemId: string; tileIds?: string[]; text?: string; assisted?: boolean };

const FORMATS: readonly CarteReviewFormat[] = ['match_pairs', 'word_bank', 'unscramble', 'dictation'];

export function parseCarteReview(raw: unknown): CarteReview {
  const body = isObject(raw) ? raw : {};
  const words = (Array.isArray(body.words) ? body.words : []).filter(isObject).map((w) => ({
    progressId: str(w.progress_id),
    wordId: num(w.word_id) ?? 0,
    word: str(w.word),
    gloss: str(w.gloss),
    sentenceFr: str(w.sentence_fr),
    speakerId: str(w.speaker_id) || 'romy_tremblay',
    speakerName: str(w.speaker_name) || 'Romy',
    lineFr: str(w.line_fr) || str(w.sentence_fr),
    sessionId: str(w.session_id),
    week: str(w.week),
  }));
  const items = (Array.isArray(body.items) ? body.items : [])
    .filter(isObject)
    .filter((i) => FORMATS.includes(i.task_type as CarteReviewFormat))
    .map((i) => {
      const key = isObject(i.answer_key) && Array.isArray(i.answer_key.digests) ? i.answer_key : null;
      return {
        id: str(i.id),
        taskType: i.task_type as CarteReviewFormat,
        progressIds: Array.isArray(i.progress_ids) ? i.progress_ids.map(str) : [],
        promptFr: strOrNull(i.prompt_fr),
        options: (Array.isArray(i.options) ? i.options : []).filter(isObject).map(
          (o): CarteReviewOption => ({
            id: str(o.id),
            text_fr: str(o.text_fr),
            side: o.side === 'fr' || o.side === 'native' ? o.side : null,
          }),
        ),
        answerKey: key
          ? { version: num(key.version) ?? 1, salt: str(key.salt), digests: (key.digests as unknown[]).map(str) }
          : null,
        audioUrl: strOrNull(i.audio_url),
      };
    });
  return {
    placeId: str(body.place_id),
    placeLabelFr: str(body.place_label_fr),
    plateUrl: strOrNull(body.plate_url),
    week: str(body.week),
    headlineFr: strOrNull(body.headline_fr),
    words,
    items,
  };
}

export function parseCarteReviewGrade(raw: unknown): CarteReviewGrade {
  const body = isObject(raw) ? raw : {};
  return {
    itemId: str(body.item_id),
    taskType: str(body.task_type),
    results: (Array.isArray(body.results) ? body.results : []).filter(isObject).map((r) => ({
      progressId: str(r.progress_id),
      wordId: num(r.word_id) ?? 0,
      correct: r.correct === true,
      rating: num(r.rating) ?? 0,
      dueAt: strOrNull(r.due_at),
    })),
    remaining: num(body.remaining) ?? 0,
  };
}

// ---------------------------------------------------------------------------
// WP-121 B · La Relecture (`/revue/relecture/*`)
// ---------------------------------------------------------------------------

export type RelectureFlag = 'register' | 'grammar';
export type RelectureSpan = { start: number; end: number; flag: RelectureFlag };

export type RelectureOffer = {
  sessionId: string;
  week: string;
  kind: 'question' | 'headline';
  dossierTitleFr: string;
  promptFr: string;
  placeLabelFr: string;
  plateUrl: string | null;
  closedAt: string | null;
};

export type RelectureSide = { labelFr: string; textFr: string; spans: RelectureSpan[] };

export type RelecturePair = {
  sessionId: string;
  offer: RelectureOffer;
  then: RelectureSide;
  now: RelectureSide;
  romyLineFr: string;
  askedAt: string;
};

export function parseRelectureOffer(raw: unknown): RelectureOffer | null {
  if (!isObject(raw) || !strOrNull(raw.session_id)) return null;
  return {
    sessionId: str(raw.session_id),
    week: str(raw.week),
    kind: raw.kind === 'headline' ? 'headline' : 'question',
    dossierTitleFr: str(raw.dossier_title_fr),
    promptFr: str(raw.prompt_fr),
    placeLabelFr: str(raw.place_label_fr),
    plateUrl: strOrNull(raw.plate_url),
    closedAt: strOrNull(raw.closed_at),
  };
}

function parseSide(raw: unknown): RelectureSide {
  const side = isObject(raw) ? raw : {};
  const spans = (Array.isArray(side.spans) ? side.spans : [])
    .filter(isObject)
    .map((s) => ({ start: num(s.start) ?? 0, end: num(s.end) ?? 0, flag: (s.flag === 'register' ? 'register' : 'grammar') as RelectureFlag }))
    .filter((s) => s.end > s.start);
  return { labelFr: str(side.label_fr), textFr: str(side.text_fr), spans };
}

export function parseRelecturePair(raw: unknown): RelecturePair | null {
  if (!isObject(raw)) return null;
  const offer = parseRelectureOffer(raw.offer);
  if (!offer) return null;
  return {
    sessionId: str(raw.session_id) || offer.sessionId,
    offer,
    then: parseSide(raw.then),
    now: parseSide(raw.now),
    romyLineFr: str(raw.romy_line_fr),
    askedAt: str(raw.asked_at),
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
