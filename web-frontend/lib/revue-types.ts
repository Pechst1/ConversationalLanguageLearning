/**
 * WP-119 phases 1–2 · Le Papier de Romy — the wire, in the client's own shapes.
 * Phase 2 («Les invités», WIRE §6): `reason` on fallback lines, the `guest`
 * item, Romy's `make_intro` / `make_done` lines, the rubric evidence
 * (`revue-rubric-v1`), `headline_write` and `short_report`, and the vignette a
 * close mints (WP-120, `closing.vignette`).
 * WP-119 §8.4 (the story's own picture): `stage.plate_kind` / `picture_words`, Romy's
 * `look` line, the `caption` make («La légende») and the dispatch's picture and caption.
 * «Au comptoir» (WIRE §9, owner 2026-10-19): the session's `mode` and `comptoir` view,
 * the act route's result, «La page» on the close, the story card's question of the day.
 *
 * The server speaks `snake_case` (docs/implementation/atelier-v2/WP-119-WIRE.md,
 * app/schemas/revue.py); the components read `camelCase`. Every response goes
 * through one parser below, so a field the wire renames breaks here, in one
 * place, and the node tests (components/revue/revue-wire.test.js) parse every
 * example of the wire document.
 *
 * Pure: no React, no network. `lib/revue-api.ts` is the client, `lib/revue-mock.ts`
 * the dev-only scripted server.
 */

export type RvSpan = [number, number];

export type RvTopic = 'food' | 'culture' | 'city' | 'sport' | 'nature' | 'work' | 'politics';
export type RvClaimKind = 'fact' | 'interpretation' | 'forecast';
export type RvDress = 'coat' | 'suit' | 'apron' | 'raincoat' | 'sport' | 'scarf_only' | 'chef' | 'hi_vis';
export type RvBeat = 'arrive' | 'facts' | 'pursue' | 'make' | 'close';
export type RvRoomPhase = 'open' | 'bouclage' | 'boucle';
export type RvMakeKind = 'headline_choice' | 'headline_write' | 'reader_question' | 'short_report' | 'caption';
export const RV_MAKE_KINDS = ['headline_choice', 'headline_write', 'reader_question', 'short_report', 'caption'] as const;
/** What a session files: a make, or `opinion` («Au comptoir»: the learner's quote in Romy's vox pop, never offered as a make). */
export type RvMadeKind = RvMakeKind | 'opinion';
export const RV_MADE_KINDS = [...RV_MAKE_KINDS, 'opinion'] as const;
export type RvLanguage = 'en' | 'de' | 'fr';
export type RvPurpose = 'understand_change' | 'explain_disagreement' | 'choose_angle' | 'prepare_dispatch';
/** `look` (§8.4): on arrival, Romy points at the story's picture with the words it shows. */
export type RvLineRole = 'purpose' | 'place_note' | 'look' | 'reply' | 'steer' | 'fallback' | 'make_intro' | 'make_done' | 'close';
/** §8.4: what the site's plate is — the story's own picture, a painted place, a season plate, a stand-in. */
export type RvPlateKind = 'story' | 'painted' | 'season' | 'stand_in';
/** WIRE §6.1: why an authored line stands in. Set on every `fallback` line (and on a guest's authored line). */
export type RvFallbackReason = 'model_down' | 'knowledge_refused' | 'budget' | 'no_match';
export type RvGuestMove = 'enter' | 'follow_up' | 'disagree' | 'moved';
export type RvGuestPosition = 'for' | 'against' | 'moved';
export type RvOutcome = 'correct' | 'incorrect' | 'unscored';
export type RvFactFit = 'supported' | 'unsupported' | 'contradicted' | 'not_applicable';
export type RvRegisterNote = 'ok' | 'vous_to_tu' | 'tu_to_vous';
export type RvShiftReason = 'simplify' | 'angle' | 'bouclage' | 'boucle';

export type RvWeek = { iso: string; label: string; range: string };
export type RvSource = { id: string; name: string; url: string; publishedAt: string };
export type RvClaim = {
  id: string;
  kind: RvClaimKind;
  fr: string;
  quote: string;
  attributedTo: string | null;
  source: RvSource;
};
export type RvGloss = { fr: string; gloss: string; claimId: string };
export type RvStageMember = { id: string; hold: string | null };
export type RvStage = {
  placeId: string;
  placeFr: string;
  plateUrl: string | null;
  platePlaceId: string;
  placeIsReal: boolean;
  dress: RvDress;
  cast: RvStageMember[];
  /** WP-119 phase 4 (§12.7): the second view, shown from the guest's entrance (or `make`) on. */
  plateUrlSecond?: string | null;
  plateSwitched?: boolean;
  /** §8.4: `story` when `plateUrl` is the story's own picture (painted once, for every learner). */
  plateKind: RvPlateKind;
  /** §8.4: in a session, the words the story's picture shows, glossed (they lead the vocabulary). */
  pictureWords: RvGloss[];
};
export type RvStoryCard = {
  dossierId: string;
  titleFr: string;
  /** Home's news card (2026-10-18): six words or fewer; null before the dossier's leads were written. */
  headlineFr: string | null;
  summaryFr: string;
  topic: RvTopic;
  placeFr: string;
  plateUrl: string | null;
  evergreen: boolean;
  stage: RvStage;
  /** «Au comptoir»: the question of the day and the three regulars (seat order); null with the switch off. */
  questionFr: string | null;
  cast: string[] | null;
};
export type RvSupport = {
  glosses: 'shown' | 'tap' | 'none';
  translation: 'one_tap' | 'on_request' | 'none';
  readingTargetWords: number;
  vocabTarget: number;
  level: number;
};
export type RvRoom = { used: number; phase: RvRoomPhase; remainingTurns: number };
export type RvMade = { kind: RvMadeKind; textFr: string; contribution: RvSpan[]; learnerFr: string | null };
export type RvDispatch = {
  kickerFr: string;
  headlineFr: string;
  bodyFr: string[];
  contribution: RvSpan[];
  bylineFr: string;
  sources: RvSource[];
  /** §8.4: the story's picture printed with the dispatch, under its caption (the learner's when `captionByLearner`). */
  pictureUrl: string | null;
  captionFr: string | null;
  captionByLearner: boolean;
};
export type RvQuickReply = { label: string; sendFr: string };

// ---------------------------------------------------------------------------
// The thread (WIRE §2)
// ---------------------------------------------------------------------------

type ItemBase = { id: string; seq: number; at: string };
export type RvNarrationItem = ItemBase & { kind: 'narration'; textFr: string };
/** What happened (2026-10-18): the lead at the learner's band, shown as text, read aloud on a tap. */
export type RvSummaryItem = ItemBase & {
  kind: 'summary';
  speaker: string;
  textFr: string;
  translation: string | null;
  glosses: RvGloss[];
};
export type RvLineItem = ItemBase & {
  kind: 'line';
  speaker: string;
  role: RvLineRole;
  textFr: string;
  translation: string | null;
  glosses: RvGloss[];
  /** Phase 2: set on every `fallback` line, null on every other. */
  reason: RvFallbackReason | null;
};
/** WIRE §6.2: a guest speaks (one guest per Papier). */
export type RvGuestItem = ItemBase & {
  kind: 'guest';
  castId: string;
  textFr: string;
  move: RvGuestMove;
  position: RvGuestPosition | null;
  /** On `enter` only, when the line does not already say it: the caption under the guest. */
  reasonFr: string | null;
  /** An authored line stands in (`model_down` | `knowledge_refused`). */
  reason: RvFallbackReason | null;
  glosses: RvGloss[];
};
/** `registerNote`: the rubric's note on this line, replayed by the server (WIRE §2), so it survives a reload. */
export type RvMineItem = ItemBase & { kind: 'mine'; textFr: string; mode: 'text' | 'voice'; registerNote: Exclude<RvRegisterNote, 'ok'> | null };
export type RvClaimsItem = ItemBase & { kind: 'claims'; claims: RvClaim[] };
export type RvUncertaintyItem = ItemBase & { kind: 'uncertainty'; textFr: string };
export type RvShiftItem = ItemBase & { kind: 'shift'; reason: RvShiftReason; angle: { id: string; fr: string } | null };
export type RvMadeItem = ItemBase & { kind: 'made'; made: RvMade };

export type RvThreadItem =
  | RvNarrationItem
  | RvSummaryItem
  | RvLineItem
  | RvGuestItem
  | RvMineItem
  | RvClaimsItem
  | RvUncertaintyItem
  | RvShiftItem
  | RvMadeItem;

export const RV_ITEM_KINDS = ['narration', 'summary', 'line', 'guest', 'mine', 'claims', 'uncertainty', 'shift', 'made'] as const;

// ---------------------------------------------------------------------------
// Endpoint shapes (WIRE §3)
// ---------------------------------------------------------------------------

export type RvResume = {
  sessionId: string;
  dossierId: string;
  titleFr: string;
  startedAt: string;
  beat: RvBeat;
  openQuestionFr: string | null;
};
export type RvFiled = {
  sessionId: string;
  dossierId: string;
  titleFr: string;
  closedAt: string;
  made: RvMade | null;
  dispatch: RvDispatch | null;
};
export type RvOffer = {
  week: RvWeek;
  recommended: RvStoryCard | null;
  recommendedReason: 'topic_least_recent' | 'interests' | 'first';
  alternatives: RvStoryCard[];
  evergreenOnly: boolean;
  resume: RvResume | null;
  filed: RvFiled | null;
};
/** `GET /revue/week`: a 404 (the flag is off) is `{ enabled: false }`, never an error. */
export type RvWeekResult = { enabled: false } | { enabled: true; offer: RvOffer };

export type RvMatchResult = { match: string | null; romyLineFr: string | null };

export type RvAngle = { id: string; fr: string; purpose: RvPurpose };
export type RvPlan = {
  band: 'A1' | 'A2' | 'B1' | 'B2';
  uiLanguage: RvLanguage;
  glossLanguage: RvLanguage;
  chosenBy: 'learner' | 'recommended';
  angle: RvAngle;
  support: RvSupport;
  vocabulary: RvGloss[];
  makeOptions: RvMakeKind[];
  budget: { turns: number; minutes: number };
};
export type RvDossierView = {
  id: string;
  titleFr: string;
  summaryFr: string;
  topic: string;
  evergreen: boolean;
  sources: RvSource[];
};
/** `outcome`: the rubric's best outcome for the word over the session, stored at close (WIRE §3.8); null when never graded. */
export type RvKeptWord = { fr: string; gloss: string; claimId: string; used: boolean; outcome: RvOutcome | null };
export type RvClosing = {
  romyLineFr: string;
  dispatch: RvDispatch;
  kept: { words: RvKeptWord[]; claims: RvClaim[] };
  questionKeptFr: string | null;
  colophonFr: string;
  /** WP-120: the vignette the close minted; null when the server sent none (the close shows no stamp). */
  vignette: RvVignetteView | null;
  /** «Au comptoir»: «La page»; null for a chat session. */
  comptoirPage: RvComptoirPage | null;
};
export type RvSessionView = {
  id: string;
  week: RvWeek;
  status: 'active' | 'closed' | 'abandoned';
  startedAt: string;
  closedAt: string | null;
  dossier: RvDossierView;
  plan: RvPlan;
  stage: RvStage;
  beat: RvBeat;
  room: RvRoom;
  thread: RvThreadItem[];
  quickReplies: RvQuickReply[];
  steerToMake: boolean;
  /** The learner typed or said a line of their own (a chip is not one): «Écrire le papier» waits for it. */
  ownLine: boolean;
  artifact: RvMade | null;
  closing: RvClosing | null;
  /** «Au comptoir»: fixed at the start for the session's life; `chat` with the switch off. */
  mode: 'chat' | 'comptoir';
  comptoir: RvComptoirView | null;
};
export type RvWordEvidence = { fr: string; outcome: RvOutcome; capabilityKnown: boolean };
/** WIRE §6.3 · the Papier rubric (`revue-rubric-v1`). */
export type RvEvidence = {
  outcome: RvOutcome;
  capabilityKnown: boolean;
  grader: string;
  words: RvWordEvidence[];
  factFit: RvFactFit;
  registerNote: RvRegisterNote;
  pending?: boolean;
};
export type RvTurnResult = {
  items: RvThreadItem[];
  beat: RvBeat;
  room: RvRoom;
  support: RvSupport;
  quickReplies: RvQuickReply[];
  steerToMake: boolean;
  ownLine: boolean;
  evidence: RvEvidence;
};
export type RvHeadlineOption = { id: string; textFr: string };
/**
 * §8.4 «La légende»: the caption under the story's picture. Every band writes it (2026-10-23),
 * `maxWords` at most, with the picture's words as chips. `options` (A1–A2): three captions to
 * choose from instead, only after a refused try (the answer stays on the server until the pick).
 */
export type RvCaptionOffer = {
  kind: 'caption';
  format: 'choice' | 'write';
  pictureUrl: string;
  options: RvHeadlineOption[];
  words: RvGloss[];
  maxWords: number;
};
export type RvMakeOption =
  | { kind: 'headline_choice'; options: RvHeadlineOption[] }
  | { kind: 'headline_write'; maxWords: number }
  | { kind: 'reader_question'; seedFr: string | null; uncertaintyFr: string | null }
  | { kind: 'short_report'; seconds: number }
  | RvCaptionOffer;
/** `intro`: Romy's `make_intro` line, written once on the first GET (phase 2). */
export type RvMakeOffer = { recommended: RvMakeKind; options: RvMakeOption[]; intro: RvLineItem | null };
export type RvQuestionDraftData = {
  learnerFr: string;
  proposalFr: string;
  contribution: RvSpan[];
  whyNative: string | null;
};
export type RvPickResult = {
  kind: 'headline_choice';
  correct: boolean;
  answerId: string;
  evidence: { claimId: string; quote: string; source: RvSource };
  made: RvMade;
  /** Phase 2: Romy's `make_done` line. */
  line: RvLineItem | null;
};
export type RvWriteResult = {
  kind: 'headline_write';
  /** false: a shown claim contradicts it — nothing filed, write again. */
  accepted: boolean;
  evidence: RvEvidence;
  made: RvMade | null;
  line: RvLineItem | null;
};
export type RvReportResult = { kind: 'short_report'; evidence: RvEvidence; made: RvMade; line: RvLineItem | null };
/**
 * «La légende» filed (or refused). `choice`: `correct` and `answerId` (a pick files the caption
 * the picture shows, never credited to the learner); `write`: the rubric's `evidence`, and
 * `accepted` false when a claim contradicts it or it is too short (nothing filed: write again;
 * at A1–A2 `options` are the three captions to pick from instead).
 */
export type RvCaptionResult = {
  kind: 'caption';
  format: 'choice' | 'write';
  accepted: boolean;
  correct: boolean | null;
  answerId: string | null;
  evidence: RvEvidence | null;
  made: RvMade | null;
  line: RvLineItem | null;
  options: RvHeadlineOption[];
};
export type RvMakeResult =
  | RvPickResult
  | RvWriteResult
  | RvReportResult
  | RvCaptionResult
  | { kind: 'reader_question'; draft: RvQuestionDraftData }
  | { kind: 'reader_question'; made: RvMade; line: RvLineItem | null };
export type RvCloseResult = { session: RvSessionView; closing: RvClosing };

// Request bodies (camelCase in, snake_case on the wire — see revue-api.ts).
export type RvStartBody = { week?: string; dossierId?: string; freeRequest?: string; angleId?: string };
export type RvTurnBody = { text: string; mode?: 'text' | 'voice'; clientTurnId?: string };
export type RvMakeBody =
  | { kind: 'headline_choice'; action: 'pick'; optionId: string }
  | { kind: 'reader_question'; action: 'propose'; text?: string }
  | { kind: 'reader_question'; action: 'send'; textFr: string }
  | { kind: 'headline_write'; action: 'write'; textFr: string }
  | { kind: 'short_report'; action: 'report'; transcript: string; mode?: 'voice' | 'text' }
  | { kind: 'caption'; action: 'caption'; optionId: string }
  | { kind: 'caption'; action: 'caption'; textFr: string };

// ---------------------------------------------------------------------------
// Errors (WIRE §4)
// ---------------------------------------------------------------------------

export type RvErrorCode =
  | 'revue_disabled'
  | 'revue_session_not_found'
  | 'revue_dossier_not_found'
  | 'revue_session_active'
  | 'revue_week_filed'
  | 'revue_session_closed'
  | 'revue_make_unavailable'
  | 'revue_make_needs_a_line'
  | 'revue_caption_write_first'
  | 'revue_unknown_option'
  | 'revue_not_comptoir'
  | 'revue_comptoir_session'
  | 'revue_comptoir_out_of_order'
  | 'revue_comptoir_bad_act'
  | 'unauthorized'
  | 'validation'
  | 'rate_limited'
  | 'network'
  | 'server';

export class RevueError extends Error {
  status: number;
  code: RvErrorCode;
  sessionId: string | null;
  dossierId: string | null;
  makeKind: string | null;

  constructor(status: number, code: RvErrorCode, extra: { sessionId?: string | null; dossierId?: string | null; kind?: string | null } = {}) {
    super(`revue ${status} ${code}`);
    this.name = 'RevueError';
    this.status = status;
    this.code = code;
    this.sessionId = extra.sessionId ?? null;
    this.dossierId = extra.dossierId ?? null;
    this.makeKind = extra.kind ?? null;
  }
}

/** One wire error (status + `detail`) → a typed `RevueError`. */
export function parseRevueError(status: number, data: unknown): RevueError {
  const detail = isObject(data) ? (data as Record<string, unknown>).detail : undefined;
  if (isObject(detail)) {
    const d = detail as Record<string, unknown>;
    const code = typeof d.code === 'string' ? d.code : '';
    const known: RvErrorCode[] = [
      'revue_session_not_found',
      'revue_dossier_not_found',
      'revue_session_active',
      'revue_week_filed',
      'revue_session_closed',
      'revue_make_unavailable',
      'revue_make_needs_a_line',
      'revue_caption_write_first',
      'revue_unknown_option',
      'revue_not_comptoir',
      'revue_comptoir_session',
      'revue_comptoir_out_of_order',
      'revue_comptoir_bad_act',
      'rate_limited',
    ];
    if ((known as string[]).includes(code)) {
      return new RevueError(status, code as RvErrorCode, {
        sessionId: str(d.session_id) || null,
        dossierId: str(d.dossier_id) || null,
        kind: str(d.kind) || null,
      });
    }
  }
  if (status === 404) return new RevueError(404, 'revue_disabled');
  if (status === 401) return new RevueError(401, 'unauthorized');
  if (status === 422) return new RevueError(422, 'validation');
  if (status === 429) return new RevueError(429, 'rate_limited');
  if (status === 0) return new RevueError(0, 'network');
  return new RevueError(status, 'server');
}

// ---------------------------------------------------------------------------
// Parsers: wire (snake_case, unknown) → client (camelCase, typed)
// ---------------------------------------------------------------------------

type Json = Record<string, any>;

function isObject(value: unknown): value is Json {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
function str(value: unknown): string {
  return typeof value === 'string' ? value : value == null ? '' : String(value);
}
function strOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}
function num(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}
function list<T>(value: unknown, parse: (row: Json) => T): T[] {
  return Array.isArray(value) ? value.filter(isObject).map(parse) : [];
}
function spans(value: unknown): RvSpan[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((span) => Array.isArray(span) && span.length === 2)
    .map((span) => [num(span[0]), num(span[1])] as RvSpan)
    .filter(([start, end]) => end > start);
}
function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return (allowed as readonly string[]).includes(value as string) ? (value as T) : fallback;
}

export function parseWeek(raw: Json): RvWeek {
  return { iso: str(raw.iso), label: str(raw.label), range: str(raw.range) };
}

export function parseSource(raw: Json): RvSource {
  return { id: str(raw.id), name: str(raw.name), url: str(raw.url), publishedAt: str(raw.published_at) };
}

export function parseClaim(raw: Json): RvClaim {
  return {
    id: str(raw.id),
    kind: oneOf(raw.kind, ['fact', 'interpretation', 'forecast'] as const, 'fact'),
    fr: str(raw.fr),
    quote: str(raw.quote),
    attributedTo: strOrNull(raw.attributed_to),
    source: parseSource(isObject(raw.source) ? raw.source : {}),
  };
}

export function parseGloss(raw: Json): RvGloss {
  return { fr: str(raw.fr), gloss: str(raw.gloss), claimId: str(raw.claim_id) };
}

const DRESSES = ['coat', 'suit', 'apron', 'raincoat', 'sport', 'scarf_only', 'chef', 'hi_vis'] as const;
const PLATE_KINDS = ['story', 'painted', 'season', 'stand_in'] as const;

export function parseStage(raw: Json): RvStage {
  return {
    placeId: str(raw.place_id),
    placeFr: str(raw.place_fr),
    plateUrl: strOrNull(raw.plate_url),
    platePlaceId: str(raw.plate_place_id),
    placeIsReal: Boolean(raw.place_is_real),
    dress: oneOf(raw.dress, DRESSES, 'coat'),
    cast: list(raw.cast, (member) => ({ id: str(member.id), hold: strOrNull(member.hold) })),
    // Phase 4: only when the wire carries them (nothing invented for an older payload).
    ...(raw.plate_url_second !== undefined ? { plateUrlSecond: strOrNull(raw.plate_url_second) } : {}),
    ...(raw.plate_switched !== undefined ? { plateSwitched: Boolean(raw.plate_switched) } : {}),
    // §8.4: an older payload (no `plate_kind`) is a season plate with no picture words.
    plateKind: oneOf(raw.plate_kind, PLATE_KINDS, 'season'),
    pictureWords: list(raw.picture_words, parseGloss),
  };
}

const TOPICS = ['food', 'culture', 'city', 'sport', 'nature', 'work', 'politics'] as const;

export function parseStoryCard(raw: Json): RvStoryCard {
  return {
    dossierId: str(raw.dossier_id),
    titleFr: str(raw.title_fr),
    headlineFr: strOrNull(raw.headline_fr),
    summaryFr: str(raw.summary_fr),
    topic: oneOf(raw.topic, TOPICS, 'city'),
    placeFr: str(raw.place_fr),
    plateUrl: strOrNull(raw.plate_url),
    evergreen: Boolean(raw.evergreen),
    stage: parseStage(isObject(raw.stage) ? raw.stage : {}),
    questionFr: strOrNull(raw.question_fr) || null,
    cast: Array.isArray(raw.cast) ? raw.cast.filter((id: unknown): id is string => typeof id === 'string') : null,
  };
}

export function parseSupport(raw: Json): RvSupport {
  return {
    glosses: oneOf(raw.glosses, ['shown', 'tap', 'none'] as const, 'tap'),
    translation: oneOf(raw.translation, ['one_tap', 'on_request', 'none'] as const, 'on_request'),
    readingTargetWords: num(raw.reading_target_words, 90),
    vocabTarget: num(raw.vocab_target, 5),
    level: num(raw.level),
  };
}

const BEATS = ['arrive', 'facts', 'pursue', 'make', 'close'] as const;

export function parseRoom(raw: Json): RvRoom {
  return {
    used: Math.max(0, Math.min(7, num(raw.used))),
    phase: oneOf(raw.phase, ['open', 'bouclage', 'boucle'] as const, 'open'),
    remainingTurns: Math.max(0, num(raw.remaining_turns)),
  };
}

const MAKE_KINDS = RV_MAKE_KINDS;

export function parseMade(raw: Json): RvMade {
  return {
    kind: oneOf(raw.kind, RV_MADE_KINDS, 'headline_choice'),
    textFr: str(raw.text_fr),
    contribution: spans(raw.contribution),
    learnerFr: strOrNull(raw.learner_fr),
  };
}

export function parseDispatch(raw: Json): RvDispatch {
  return {
    kickerFr: str(raw.kicker_fr),
    headlineFr: str(raw.headline_fr),
    bodyFr: Array.isArray(raw.body_fr) ? raw.body_fr.map(str) : [],
    contribution: spans(raw.contribution),
    bylineFr: str(raw.byline_fr),
    sources: list(raw.sources, parseSource),
    pictureUrl: strOrNull(raw.picture_url) || null,
    // A caption is printed only under a picture.
    captionFr: raw.picture_url ? strOrNull(raw.caption_fr) || null : null,
    captionByLearner: Boolean(raw.picture_url) && raw.caption_by_learner === true,
  };
}

export function parseQuickReply(raw: Json): RvQuickReply {
  return { label: str(raw.label), sendFr: str(raw.send_fr) };
}

const ROLES = ['purpose', 'place_note', 'look', 'reply', 'steer', 'fallback', 'make_intro', 'make_done', 'close'] as const;
const REASONS = ['model_down', 'knowledge_refused', 'budget', 'no_match'] as const;
const MOVES = ['enter', 'follow_up', 'disagree', 'moved'] as const;
const POSITIONS = ['for', 'against', 'moved'] as const;
const OUTCOMES = ['correct', 'incorrect', 'unscored'] as const;

function reasonOrNull(value: unknown): RvFallbackReason | null {
  return (REASONS as readonly unknown[]).includes(value) ? (value as RvFallbackReason) : null;
}

/** A `line` item (also `RvMakeOffer.intro` and a make result's `line`). */
export function parseLineItem(raw: Json): RvLineItem {
  return {
    id: str(raw.id),
    seq: num(raw.seq),
    at: str(raw.at),
    kind: 'line',
    speaker: str(raw.speaker) || 'romy_tremblay',
    role: oneOf(raw.role, ROLES, 'reply'),
    textFr: str(raw.text_fr),
    translation: strOrNull(raw.translation),
    glosses: list(raw.glosses, parseGloss),
    reason: reasonOrNull(raw.reason),
  };
}

/** One thread item; an unknown `kind` (a later phase's) is dropped, never guessed. */
export function parseThreadItem(raw: Json): RvThreadItem | null {
  const base = { id: str(raw.id), seq: num(raw.seq), at: str(raw.at) };
  switch (raw.kind) {
    case 'narration':
      return { ...base, kind: 'narration', textFr: str(raw.text_fr) };
    case 'summary':
      return {
        ...base,
        kind: 'summary',
        speaker: str(raw.speaker) || 'romy_tremblay',
        textFr: str(raw.text_fr),
        translation: strOrNull(raw.translation),
        glosses: list(raw.glosses, parseGloss),
      };
    case 'line':
      return parseLineItem(raw);
    case 'guest':
      return {
        ...base,
        kind: 'guest',
        castId: str(raw.cast_id),
        textFr: str(raw.text_fr),
        move: oneOf(raw.move, MOVES, 'follow_up'),
        position: (POSITIONS as readonly unknown[]).includes(raw.position) ? (raw.position as RvGuestPosition) : null,
        reasonFr: strOrNull(raw.reason_fr),
        reason: reasonOrNull(raw.reason),
        glosses: list(raw.glosses, parseGloss),
      };
    case 'mine':
      return {
        ...base,
        kind: 'mine',
        textFr: str(raw.text_fr),
        mode: raw.mode === 'voice' ? 'voice' : 'text',
        registerNote: raw.register_note === 'vous_to_tu' || raw.register_note === 'tu_to_vous' ? raw.register_note : null,
      };
    case 'claims':
      return { ...base, kind: 'claims', claims: list(raw.claims, parseClaim) };
    case 'uncertainty':
      return { ...base, kind: 'uncertainty', textFr: str(raw.text_fr) };
    case 'shift':
      return {
        ...base,
        kind: 'shift',
        reason: oneOf(raw.reason, ['simplify', 'angle', 'bouclage', 'boucle'] as const, 'simplify'),
        angle: isObject(raw.angle) ? { id: str(raw.angle.id), fr: str(raw.angle.fr) } : null,
      };
    case 'made':
      return { ...base, kind: 'made', made: parseMade(isObject(raw.made) ? raw.made : {}) };
    default:
      return null;
  }
}

export function parseThread(value: unknown): RvThreadItem[] {
  return list(value, parseThreadItem).filter((item): item is RvThreadItem => item !== null);
}

export function parseOffer(raw: Json): RvOffer {
  const resume = isObject(raw.resume) ? raw.resume : null;
  const filed = isObject(raw.filed) ? raw.filed : null;
  return {
    week: parseWeek(isObject(raw.week) ? raw.week : {}),
    recommended: isObject(raw.recommended) ? parseStoryCard(raw.recommended) : null,
    recommendedReason: oneOf(raw.recommended_reason, ['topic_least_recent', 'interests', 'first'] as const, 'first'),
    alternatives: list(raw.alternatives, parseStoryCard),
    evergreenOnly: Boolean(raw.evergreen_only),
    resume: resume
      ? {
          sessionId: str(resume.session_id),
          dossierId: str(resume.dossier_id),
          titleFr: str(resume.title_fr),
          startedAt: str(resume.started_at),
          beat: oneOf(resume.beat, BEATS, 'arrive'),
          openQuestionFr: strOrNull(resume.open_question_fr),
        }
      : null,
    filed: filed
      ? {
          sessionId: str(filed.session_id),
          dossierId: str(filed.dossier_id),
          titleFr: str(filed.title_fr),
          closedAt: str(filed.closed_at),
          made: isObject(filed.made) ? parseMade(filed.made) : null,
          dispatch: isObject(filed.dispatch) ? parseDispatch(filed.dispatch) : null,
        }
      : null,
  };
}

export function parseMatch(raw: Json): RvMatchResult {
  return { match: strOrNull(raw.match), romyLineFr: strOrNull(raw.romy_line_fr) };
}

export function parseClosing(raw: Json): RvClosing {
  const kept = isObject(raw.kept) ? raw.kept : {};
  return {
    romyLineFr: str(raw.romy_line_fr),
    dispatch: parseDispatch(isObject(raw.dispatch) ? raw.dispatch : {}),
    kept: {
      words: list(kept.words, (word) => ({
        fr: str(word.fr),
        gloss: str(word.gloss),
        claimId: str(word.claim_id),
        used: Boolean(word.used),
        outcome: word.outcome === 'correct' || word.outcome === 'incorrect' || word.outcome === 'unscored' ? word.outcome : null,
      })),
      claims: list(kept.claims, parseClaim),
    },
    questionKeptFr: strOrNull(raw.question_kept_fr),
    colophonFr: str(raw.colophon_fr) || 'La suite la semaine prochaine.',
    vignette: isObject(raw.vignette) ? parseVignette(raw.vignette) : null,
    comptoirPage: isObject(raw.comptoir_page) ? parseComptoirPage(raw.comptoir_page) : null,
  };
}

const LANGUAGES = ['en', 'de', 'fr'] as const;

export function parseSessionView(raw: Json): RvSessionView {
  const plan = isObject(raw.plan) ? raw.plan : {};
  const dossier = isObject(raw.dossier) ? raw.dossier : {};
  const angle = isObject(plan.angle) ? plan.angle : {};
  const budget = isObject(plan.budget) ? plan.budget : {};
  return {
    id: str(raw.id),
    week: parseWeek(isObject(raw.week) ? raw.week : {}),
    status: oneOf(raw.status, ['active', 'closed', 'abandoned'] as const, 'active'),
    startedAt: str(raw.started_at),
    closedAt: strOrNull(raw.closed_at),
    dossier: {
      id: str(dossier.id),
      titleFr: str(dossier.title_fr),
      summaryFr: str(dossier.summary_fr),
      topic: str(dossier.topic),
      evergreen: Boolean(dossier.evergreen),
      sources: list(dossier.sources, parseSource),
    },
    plan: {
      band: oneOf(plan.band, ['A1', 'A2', 'B1', 'B2'] as const, 'A2'),
      uiLanguage: oneOf(plan.ui_language, LANGUAGES, 'en'),
      glossLanguage: oneOf(plan.gloss_language, LANGUAGES, 'en'),
      chosenBy: plan.chosen_by === 'learner' ? 'learner' : 'recommended',
      angle: {
        id: str(angle.id),
        fr: str(angle.fr),
        purpose: oneOf(angle.purpose, ['understand_change', 'explain_disagreement', 'choose_angle', 'prepare_dispatch'] as const, 'understand_change'),
      },
      support: parseSupport(isObject(plan.support) ? plan.support : {}),
      vocabulary: list(plan.vocabulary, parseGloss),
      makeOptions: Array.isArray(plan.make_options)
        ? plan.make_options.filter((kind: unknown): kind is RvMakeKind => (MAKE_KINDS as readonly unknown[]).includes(kind))
        : [],
      budget: { turns: num(budget.turns, 10), minutes: num(budget.minutes, 12) },
    },
    stage: parseStage(isObject(raw.stage) ? raw.stage : {}),
    beat: oneOf(raw.beat, BEATS, 'arrive'),
    room: parseRoom(isObject(raw.room) ? raw.room : {}),
    thread: parseThread(raw.thread),
    quickReplies: list(raw.quick_replies, parseQuickReply),
    steerToMake: Boolean(raw.steer_to_make),
    ownLine: raw.own_line === true,
    artifact: isObject(raw.artifact) ? parseMade(raw.artifact) : null,
    closing: isObject(raw.closing) ? parseClosing(raw.closing) : null,
    // A comptoir session without its view is drawn as a chat: never a player with nothing to show.
    mode: raw.mode === 'comptoir' && isObject(raw.comptoir) ? 'comptoir' : 'chat',
    comptoir: raw.mode === 'comptoir' && isObject(raw.comptoir) ? parseComptoirView(raw.comptoir) : null,
  };
}

/** The rubric (WIRE §6.3); a phase-1 payload (no words, no fit) reads as `not_applicable` / `ok`. */
export function parseEvidence(raw: Json): RvEvidence {
  return {
    outcome: oneOf(raw.outcome, OUTCOMES, 'unscored'),
    capabilityKnown: Boolean(raw.capability_known),
    grader: str(raw.grader),
    words: list(raw.words, (word) => ({
      fr: str(word.fr),
      outcome: oneOf(word.outcome, OUTCOMES, 'unscored'),
      capabilityKnown: Boolean(word.capability_known),
    })),
    factFit: oneOf(raw.fact_fit, ['supported', 'unsupported', 'contradicted', 'not_applicable'] as const, 'not_applicable'),
    registerNote: oneOf(raw.register_note, ['ok', 'vous_to_tu', 'tu_to_vous'] as const, 'ok'),
    // WP-119 §10e.8: the critic answers on the next turn; not graded yet, never "wrong".
    pending: Boolean(raw.pending),
  };
}

export function parseTurnResult(raw: Json): RvTurnResult {
  return {
    items: parseThread(raw.items),
    beat: oneOf(raw.beat, BEATS, 'pursue'),
    room: parseRoom(isObject(raw.room) ? raw.room : {}),
    support: parseSupport(isObject(raw.support) ? raw.support : {}),
    quickReplies: list(raw.quick_replies, parseQuickReply),
    steerToMake: Boolean(raw.steer_to_make),
    ownLine: raw.own_line === true,
    evidence: parseEvidence(isObject(raw.evidence) ? raw.evidence : {}),
  };
}

export function parseMakeOffer(raw: Json): RvMakeOffer {
  const options: RvMakeOption[] = [];
  for (const option of Array.isArray(raw.options) ? raw.options.filter(isObject) : []) {
    if (option.kind === 'headline_choice') {
      options.push({ kind: 'headline_choice', options: list(option.options, (row) => ({ id: str(row.id), textFr: str(row.text_fr) })) });
    } else if (option.kind === 'headline_write') {
      options.push({ kind: 'headline_write', maxWords: Math.max(1, num(option.max_words, 14)) });
    } else if (option.kind === 'reader_question') {
      options.push({ kind: 'reader_question', seedFr: strOrNull(option.seed_fr), uncertaintyFr: strOrNull(option.uncertainty_fr) });
    } else if (option.kind === 'short_report') {
      options.push({ kind: 'short_report', seconds: Math.max(1, num(option.seconds, 30)) });
    } else if (option.kind === 'caption' && str(option.picture_url)) {
      // «La légende» without its picture would be a caption under nothing: absent.
      const format = option.format === 'write' ? 'write' : 'choice';
      const captions = list(option.options, (row) => ({ id: str(row.id), textFr: str(row.text_fr) }));
      if (format === 'choice' && captions.length < 2) continue;
      options.push({
        kind: 'caption',
        format,
        pictureUrl: str(option.picture_url),
        options: captions,
        words: list(option.words, parseGloss),
        maxWords: Math.max(1, num(option.max_words, 16)),
      });
    }
    // An unknown kind is absent here, never greyed.
  }
  const recommended = oneOf(raw.recommended, MAKE_KINDS, 'headline_choice');
  return { recommended, options, intro: isObject(raw.intro) ? parseLineItem(raw.intro) : null };
}

export function parseMakeResult(raw: Json): RvMakeResult {
  const line = isObject(raw.line) ? parseLineItem(raw.line) : null;
  if (raw.kind === 'headline_choice') {
    const evidence = isObject(raw.evidence) ? raw.evidence : {};
    return {
      kind: 'headline_choice',
      correct: Boolean(raw.correct),
      answerId: str(raw.answer_id),
      evidence: { claimId: str(evidence.claim_id), quote: str(evidence.quote), source: parseSource(isObject(evidence.source) ? evidence.source : {}) },
      made: parseMade(isObject(raw.made) ? raw.made : {}),
      line,
    };
  }
  if (raw.kind === 'headline_write') {
    return {
      kind: 'headline_write',
      accepted: raw.accepted === true,
      evidence: parseEvidence(isObject(raw.evidence) ? raw.evidence : {}),
      made: isObject(raw.made) ? parseMade(raw.made) : null,
      line,
    };
  }
  if (raw.kind === 'short_report') {
    return {
      kind: 'short_report',
      evidence: parseEvidence(isObject(raw.evidence) ? raw.evidence : {}),
      made: parseMade(isObject(raw.made) ? raw.made : {}),
      line,
    };
  }
  if (raw.kind === 'caption') {
    return {
      kind: 'caption',
      format: raw.format === 'write' ? 'write' : 'choice',
      accepted: raw.accepted === true,
      correct: typeof raw.correct === 'boolean' ? raw.correct : null,
      answerId: strOrNull(raw.answer_id),
      evidence: isObject(raw.evidence) ? parseEvidence(raw.evidence) : null,
      made: isObject(raw.made) ? parseMade(raw.made) : null,
      line,
      options: list(raw.options, (row) => ({ id: str(row.id), textFr: str(row.text_fr) })).filter((row) => row.id && row.textFr),
    };
  }
  if (isObject(raw.draft)) {
    return {
      kind: 'reader_question',
      draft: {
        learnerFr: str(raw.draft.learner_fr),
        proposalFr: str(raw.draft.proposal_fr),
        contribution: spans(raw.draft.contribution),
        whyNative: strOrNull(raw.draft.why_native),
      },
    };
  }
  return { kind: 'reader_question', made: parseMade(isObject(raw.made) ? raw.made : {}), line };
}

export function parseCloseResult(raw: Json): RvCloseResult {
  return {
    session: parseSessionView(isObject(raw.session) ? raw.session : {}),
    closing: parseClosing(isObject(raw.closing) ? raw.closing : {}),
  };
}

// Request bodies → wire.

export function startBodyWire(body: RvStartBody): Json {
  const wire: Json = {};
  if (body.week) wire.week = body.week;
  if (body.dossierId) wire.dossier_id = body.dossierId;
  if (body.freeRequest) wire.free_request = body.freeRequest;
  if (body.angleId) wire.angle_id = body.angleId;
  return wire;
}

export function turnBodyWire(body: RvTurnBody): Json {
  const wire: Json = { text: body.text, mode: body.mode ?? 'text' };
  if (body.clientTurnId) wire.client_turn_id = body.clientTurnId;
  return wire;
}

export function makeBodyWire(body: RvMakeBody): Json {
  if (body.action === 'pick') return { kind: body.kind, action: body.action, option_id: body.optionId };
  if (body.action === 'caption') {
    return 'optionId' in body
      ? { kind: body.kind, action: body.action, option_id: body.optionId }
      : { kind: body.kind, action: body.action, text_fr: body.textFr };
  }
  if (body.action === 'propose') return body.text ? { kind: body.kind, action: body.action, text: body.text } : { kind: body.kind, action: body.action };
  if (body.action === 'report') return { kind: body.kind, action: body.action, transcript: body.transcript, mode: body.mode ?? 'voice' };
  return { kind: body.kind, action: body.action, text_fr: body.textFr };
}

// ---------------------------------------------------------------------------
// WP-120 · the vignettes (`GET /revue/vignettes`)
// ---------------------------------------------------------------------------

export type RvVignetteRing = 'headline' | 'question' | 'report';
export type RvVignetteView = {
  id: string;
  sessionId: string;
  dossierId: string;
  /** ISO week, `2026-W40`. */
  week: string;
  placeLabelFr: string;
  ring: RvVignetteRing;
  keptContribution: boolean;
  /** House-grammar SVG; `RvVignette` sanitises it again before inlining. */
  pictogramSvg: string;
  headlineFr: string;
  mintedAt: string;
};

export function parseVignette(raw: Json): RvVignetteView {
  return {
    id: str(raw.id),
    sessionId: str(raw.session_id),
    dossierId: str(raw.dossier_id),
    week: str(raw.week),
    placeLabelFr: str(raw.place_label_fr),
    ring: oneOf(raw.ring, ['headline', 'question', 'report'] as const, 'headline'),
    keptContribution: raw.kept_contribution === true,
    pictogramSvg: str(raw.pictogram_svg),
    headlineFr: str(raw.headline_fr),
    mintedAt: str(raw.minted_at),
  };
}

export function parseVignettes(raw: Json): RvVignetteView[] {
  return list(raw.vignettes, parseVignette);
}

// ---------------------------------------------------------------------------
// «Au comptoir» (WIRE §9, owner 2026-10-19)
// ---------------------------------------------------------------------------

export type RvComptoirStep = 'read' | 'takes' | 'intox' | 'opinion' | 'page';
export type RvStance = 'pour' | 'contre' | 'nuance';
export const RV_COMPTOIR_STEPS = ['read', 'takes', 'intox', 'opinion', 'page'] as const;
export const RV_STANCES = ['pour', 'contre', 'nuance'] as const;
/** A line and its translation in the learner's gloss language (null for French). */
export type RvComptoirText = { fr: string; tr: string | null };
export type RvComptoirCast = {
  id: string;
  nameFr: string;
  roleFr: string;
  stance: RvStance;
  /** The take at the learner's band. */
  take: RvComptoirText;
  reaction: 'agree' | 'disagree' | null;
};
export type RvComptoirQuote = { castId: string; nameFr: string; roleFr: string; stance: RvStance; quoteFr: string };
export type RvComptoirFix = {
  correct: boolean;
  answerFr: string;
  /** The right sentence, always: «C'est faux, Gus ! C'est six jours sur sept, pas sept jours sur sept.» */
  lineFr: string;
  wrongFr: string;
  rightFr: string;
  claim: RvClaim | null;
  caught: RvComptoirText;
};
/** Step 3. `by` and the options are absent until the liar is named (or two tries are used); B1+ write the correction. */
export type RvComptoirIntox = {
  quotes: RvComptoirQuote[];
  tries: string[];
  resolved: boolean;
  found: boolean | null;
  by: string | null;
  hintClaim: RvClaim | null;
  ask: RvComptoirText | null;
  options: string[];
  fix: RvComptoirFix | null;
};
export type RvComptoirKit = {
  input: 'tiles' | 'frame' | 'free';
  phrase: RvComptoirText;
  reasons: Record<RvStance, RvComptoirText[]>;
  frames: Record<RvStance, RvComptoirText>;
  bank: RvComptoirText[];
  /** Who answers a learner on each side (B1: «Réponds à …»). */
  opponents: Record<RvStance, string>;
};
/** What Romy marks: the kind of slip, never the answer. */
export type RvComptoirMarkKind = 'accord' | 'conjugaison' | 'genre' | 'orthographe' | 'mot' | 'ordre' | 'manque';
export const RV_COMPTOIR_MARK_KINDS = ['accord', 'conjugaison', 'genre', 'orthographe', 'mot', 'ordre', 'manque'] as const;
/**
 * Where the opinion stands before print (2026-10-23): `clean` nothing to fix, `marked` Romy's
 * marks to fix, `fixed` the learner fixed them, `corrected` Romy fixed what was left after the
 * tries, `as_written` no check ran (printed as the learner wrote it, never «relu par Romy»).
 */
export type RvComptoirProof = 'clean' | 'marked' | 'fixed' | 'corrected' | 'as_written';
export const RV_COMPTOIR_PROOFS = ['clean', 'marked', 'fixed', 'corrected', 'as_written'] as const;
export type RvComptoirMark = { spanFr: string; start: number; kind: RvComptoirMarkKind };
export type RvComptoirComeback = { textFr: string; index: number | null; lastWord: RvComptoirText };
export type RvComptoirOpinion = {
  stance: RvStance;
  /** The sentence as first given (with the A2 frame). */
  learnerFr: string;
  /** The learner's words at their last try. */
  draftFr: string;
  proof: RvComptoirProof;
  /** `marked`: what to fix in `draftFr`. */
  marks: RvComptoirMark[];
  tries: number;
  maxTries: number;
  /** What goes to print, once settled (null while `marked`). */
  printedFr: string | null;
  /** The regular's answer, once the sentence is printed. */
  reply: { by: string; nameFr: string; line: RvComptoirText } | null;
  /** A1–A2: the three comeback chips; empty from B1 (one free line). */
  comebacks: RvComptoirText[];
  comeback: RvComptoirComeback | null;
};
export type RvComptoirView = {
  step: RvComptoirStep;
  /** The dots: five, or four when the band has no intox. */
  steps: RvComptoirStep[];
  band: 'a1' | 'a2' | 'b1';
  question: RvComptoirText;
  read: { datelineFr: string; lead: RvComptoirText; sources: RvSource[] };
  cast: RvComptoirCast[];
  hasIntox: boolean;
  vote: RvStance | null;
  intox: RvComptoirIntox | null;
  kit: RvComptoirKit | null;
  opinion: RvComptoirOpinion | null;
};
export type RvComptoirVotes = Record<RvStance, number>;
export type RvComptoirPage = {
  questionFr: string;
  datelineFr: string;
  standfirstFr: string;
  quotes: RvComptoirQuote[];
  mine: RvComptoirQuote;
  /** How the learner's quote reached print (null on a page closed before 2026-10-23). */
  proof: RvComptoirProof | null;
  votes: RvComptoirVotes;
  intox: { by: string; nameFr: string; wrongFr: string; rightFr: string; sourceName: string } | null;
  phraseFr: string;
  words: string[];
};
/** `errorFr`: why an act the learner can fix was not recorded, said on the same screen. */
export type RvComptoirResult = { session: RvSessionView; errorFr: string | null };
export type RvComptoirBody =
  | { act: 'vote'; value: RvStance }
  | { act: 'react'; guestId: string; value: 'agree' | 'disagree' }
  | { act: 'intox_who'; guestId: string }
  | { act: 'intox_fix'; value: string }
  | { act: 'intox_fix'; text: string; mode?: 'text' | 'voice' }
  | { act: 'opinion'; value: RvStance; reasonIndex: number }
  | { act: 'opinion'; value: RvStance; text: string; mode?: 'text' | 'voice' }
  | { act: 'opinion_fix'; text: string; mode?: 'text' | 'voice' }
  | { act: 'opinion_fix'; value: 'romy' }
  | { act: 'comeback'; index: number }
  | { act: 'comeback'; text: string; mode?: 'text' | 'voice' };

function stanceOf(value: unknown): RvStance {
  return oneOf(value, RV_STANCES, 'nuance');
}
function comptoirText(value: unknown): RvComptoirText {
  const row = isObject(value) ? value : {};
  return { fr: str(row.fr), tr: strOrNull(row.tr) || null };
}
function byStance<T>(value: unknown, parse: (row: unknown) => T): Record<RvStance, T> {
  const row = isObject(value) ? value : {};
  return { pour: parse(row.pour), contre: parse(row.contre), nuance: parse(row.nuance) };
}
function parseComptoirQuote(raw: Json): RvComptoirQuote {
  return { castId: str(raw.cast_id), nameFr: str(raw.name_fr), roleFr: str(raw.role_fr), stance: stanceOf(raw.stance), quoteFr: str(raw.quote_fr) };
}

export function parseComptoirView(raw: Json): RvComptoirView {
  const read = isObject(raw.read) ? raw.read : {};
  const intox = isObject(raw.intox) ? raw.intox : null;
  const fix = intox && isObject(intox.fix) ? intox.fix : null;
  const kit = isObject(raw.kit) ? raw.kit : null;
  const opinion = isObject(raw.opinion) ? raw.opinion : null;
  const reply = opinion && isObject(opinion.reply) ? opinion.reply : {};
  const comeback = opinion && isObject(opinion.comeback) ? opinion.comeback : null;
  const steps = Array.isArray(raw.steps)
    ? raw.steps.filter((step: unknown): step is RvComptoirStep => (RV_COMPTOIR_STEPS as readonly unknown[]).includes(step))
    : [];
  return {
    step: oneOf(raw.step, RV_COMPTOIR_STEPS, 'read'),
    steps: steps.length ? steps : [...RV_COMPTOIR_STEPS],
    band: oneOf(raw.band, ['a1', 'a2', 'b1'] as const, 'a2'),
    question: comptoirText(raw.question),
    read: { datelineFr: str(read.dateline_fr), lead: comptoirText(read.lead), sources: list(read.sources, parseSource) },
    cast: list(raw.cast, (row) => ({
      id: str(row.id),
      nameFr: str(row.name_fr),
      roleFr: str(row.role_fr),
      stance: stanceOf(row.stance),
      take: comptoirText(row.take),
      reaction: row.reaction === 'agree' || row.reaction === 'disagree' ? row.reaction : null,
    })),
    hasIntox: Boolean(raw.has_intox),
    vote: raw.vote == null ? null : stanceOf(raw.vote),
    intox: intox
      ? {
          quotes: list(intox.quotes, parseComptoirQuote),
          tries: Array.isArray(intox.tries) ? intox.tries.map(str) : [],
          resolved: Boolean(intox.resolved),
          found: typeof intox.found === 'boolean' ? intox.found : null,
          by: strOrNull(intox.by) || null,
          hintClaim: isObject(intox.hint_claim) ? parseClaim(intox.hint_claim) : null,
          ask: isObject(intox.ask) ? comptoirText(intox.ask) : null,
          options: Array.isArray(intox.options) ? intox.options.map(str).filter(Boolean) : [],
          fix: fix
            ? {
                correct: Boolean(fix.correct),
                answerFr: str(fix.answer_fr),
                lineFr: str(fix.line_fr),
                wrongFr: str(fix.wrong_fr),
                rightFr: str(fix.right_fr),
                claim: isObject(fix.claim) ? parseClaim(fix.claim) : null,
                caught: comptoirText(fix.caught),
              }
            : null,
        }
      : null,
    kit: kit
      ? {
          input: oneOf(kit.input, ['tiles', 'frame', 'free'] as const, 'frame'),
          phrase: comptoirText(kit.phrase),
          reasons: byStance(kit.reasons, (rows) => (Array.isArray(rows) ? rows.filter(isObject).map(comptoirText) : [])),
          frames: byStance(kit.frames, comptoirText),
          bank: Array.isArray(kit.bank) ? kit.bank.filter(isObject).map(comptoirText) : [],
          opponents: byStance(kit.opponents, str),
        }
      : null,
    opinion: opinion
      ? {
          stance: stanceOf(opinion.stance),
          learnerFr: str(opinion.learner_fr),
          draftFr: str(opinion.draft_fr) || str(opinion.learner_fr),
          proof: oneOf(opinion.proof, RV_COMPTOIR_PROOFS, 'as_written'),
          marks: list(opinion.marks, (row) => ({
            spanFr: str(row.span_fr),
            start: typeof row.start === 'number' ? row.start : 0,
            kind: oneOf(row.kind, RV_COMPTOIR_MARK_KINDS, 'mot'),
          })).filter((mark) => mark.spanFr),
          tries: num(opinion.tries),
          maxTries: num(opinion.max_tries) || 2,
          printedFr: strOrNull(opinion.printed_fr) || null,
          reply: reply && isObject(opinion.reply) ? { by: str(reply.by), nameFr: str(reply.name_fr), line: comptoirText(reply.line) } : null,
          comebacks: Array.isArray(opinion.comebacks) ? opinion.comebacks.filter(isObject).map(comptoirText) : [],
          comeback: comeback
            ? { textFr: str(comeback.text_fr), index: typeof comeback.index === 'number' ? comeback.index : null, lastWord: comptoirText(comeback.last_word) }
            : null,
        }
      : null,
  };
}

export function parseComptoirPage(raw: Json): RvComptoirPage {
  const votes = isObject(raw.votes) ? raw.votes : {};
  const intox = isObject(raw.intox) ? raw.intox : null;
  return {
    questionFr: str(raw.question_fr),
    datelineFr: str(raw.dateline_fr),
    standfirstFr: str(raw.standfirst_fr),
    quotes: list(raw.quotes, parseComptoirQuote),
    mine: parseComptoirQuote(isObject(raw.mine) ? raw.mine : {}),
    proof: raw.proof == null ? null : oneOf(raw.proof, RV_COMPTOIR_PROOFS, 'as_written'),
    votes: { pour: num(votes.pour), contre: num(votes.contre), nuance: num(votes.nuance) },
    intox: intox
      ? { by: str(intox.by), nameFr: str(intox.name_fr), wrongFr: str(intox.wrong_fr), rightFr: str(intox.right_fr), sourceName: str(intox.source_name) }
      : null,
    phraseFr: str(raw.phrase_fr),
    words: Array.isArray(raw.words) ? raw.words.map(str).filter(Boolean) : [],
  };
}

export function parseComptoirResult(raw: Json): RvComptoirResult {
  return { session: parseSessionView(isObject(raw.session) ? raw.session : {}), errorFr: strOrNull(raw.error_fr) || null };
}

export function comptoirBodyWire(body: RvComptoirBody): Json {
  const wire: Json = { act: body.act };
  if ('guestId' in body) wire.guest_id = body.guestId;
  if ('value' in body) wire.value = body.value;
  if ('text' in body) wire.text = body.text;
  if ('reasonIndex' in body) wire.reason_index = body.reasonIndex;
  if ('index' in body) wire.index = body.index;
  if ('mode' in body && body.mode) wire.mode = body.mode;
  return wire;
}
