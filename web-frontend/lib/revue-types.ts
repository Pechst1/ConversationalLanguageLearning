/**
 * WP-119 phase 1 · La Revue de Romy — the wire, in the client's own shapes.
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
export type RvMakeKind = 'headline_choice' | 'reader_question';
export type RvLanguage = 'en' | 'de' | 'fr';
export type RvPurpose = 'understand_change' | 'explain_disagreement' | 'choose_angle' | 'prepare_dispatch';
export type RvLineRole = 'purpose' | 'place_note' | 'reply' | 'steer' | 'fallback' | 'close';
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
};
export type RvStoryCard = {
  dossierId: string;
  titleFr: string;
  summaryFr: string;
  topic: RvTopic;
  placeFr: string;
  plateUrl: string | null;
  evergreen: boolean;
  stage: RvStage;
};
export type RvSupport = {
  glosses: 'shown' | 'tap' | 'none';
  translation: 'one_tap' | 'on_request' | 'none';
  readingTargetWords: number;
  vocabTarget: number;
  level: number;
};
export type RvRoom = { used: number; phase: RvRoomPhase; remainingTurns: number };
export type RvMade = { kind: RvMakeKind; textFr: string; contribution: RvSpan[]; learnerFr: string | null };
export type RvDispatch = {
  kickerFr: string;
  headlineFr: string;
  bodyFr: string[];
  contribution: RvSpan[];
  bylineFr: string;
  sources: RvSource[];
};
export type RvQuickReply = { label: string; sendFr: string };

// ---------------------------------------------------------------------------
// The thread (WIRE §2)
// ---------------------------------------------------------------------------

type ItemBase = { id: string; seq: number; at: string };
export type RvNarrationItem = ItemBase & { kind: 'narration'; textFr: string };
export type RvSummaryItem = ItemBase & { kind: 'summary'; speaker: string; textFr: string };
export type RvLineItem = ItemBase & {
  kind: 'line';
  speaker: string;
  role: RvLineRole;
  textFr: string;
  translation: string | null;
  glosses: RvGloss[];
};
export type RvMineItem = ItemBase & { kind: 'mine'; textFr: string; mode: 'text' | 'voice' };
export type RvClaimsItem = ItemBase & { kind: 'claims'; claims: RvClaim[] };
export type RvUncertaintyItem = ItemBase & { kind: 'uncertainty'; textFr: string };
export type RvShiftItem = ItemBase & { kind: 'shift'; reason: RvShiftReason; angle: { id: string; fr: string } | null };
export type RvMadeItem = ItemBase & { kind: 'made'; made: RvMade };

export type RvThreadItem =
  | RvNarrationItem
  | RvSummaryItem
  | RvLineItem
  | RvMineItem
  | RvClaimsItem
  | RvUncertaintyItem
  | RvShiftItem
  | RvMadeItem;

export const RV_ITEM_KINDS = ['narration', 'summary', 'line', 'mine', 'claims', 'uncertainty', 'shift', 'made'] as const;

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
export type RvKeptWord = { fr: string; gloss: string; claimId: string; used: boolean };
export type RvClosing = {
  romyLineFr: string;
  dispatch: RvDispatch;
  kept: { words: RvKeptWord[]; claims: RvClaim[] };
  questionKeptFr: string | null;
  colophonFr: string;
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
  artifact: RvMade | null;
  closing: RvClosing | null;
};
export type RvEvidence = { outcome: 'correct' | 'incorrect' | 'unscored'; capabilityKnown: boolean; grader: string };
export type RvTurnResult = {
  items: RvThreadItem[];
  beat: RvBeat;
  room: RvRoom;
  support: RvSupport;
  quickReplies: RvQuickReply[];
  steerToMake: boolean;
  evidence: RvEvidence;
};
export type RvHeadlineOption = { id: string; textFr: string };
export type RvMakeOption =
  | { kind: 'headline_choice'; options: RvHeadlineOption[] }
  | { kind: 'reader_question'; seedFr: string | null; uncertaintyFr: string | null };
export type RvMakeOffer = { recommended: RvMakeKind; options: RvMakeOption[] };
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
};
export type RvMakeResult =
  | RvPickResult
  | { kind: 'reader_question'; draft: RvQuestionDraftData }
  | { kind: 'reader_question'; made: RvMade };
export type RvCloseResult = { session: RvSessionView; closing: RvClosing };

// Request bodies (camelCase in, snake_case on the wire — see revue-api.ts).
export type RvStartBody = { week?: string; dossierId?: string; freeRequest?: string; angleId?: string };
export type RvTurnBody = { text: string; mode?: 'text' | 'voice'; clientTurnId?: string };
export type RvMakeBody =
  | { kind: 'headline_choice'; action: 'pick'; optionId: string }
  | { kind: 'reader_question'; action: 'propose'; text?: string }
  | { kind: 'reader_question'; action: 'send'; textFr: string };

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
  | 'revue_unknown_option'
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
      'revue_unknown_option',
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

export function parseStage(raw: Json): RvStage {
  return {
    placeId: str(raw.place_id),
    placeFr: str(raw.place_fr),
    plateUrl: strOrNull(raw.plate_url),
    platePlaceId: str(raw.plate_place_id),
    placeIsReal: Boolean(raw.place_is_real),
    dress: oneOf(raw.dress, DRESSES, 'coat'),
    cast: list(raw.cast, (member) => ({ id: str(member.id), hold: strOrNull(member.hold) })),
  };
}

const TOPICS = ['food', 'culture', 'city', 'sport', 'nature', 'work', 'politics'] as const;

export function parseStoryCard(raw: Json): RvStoryCard {
  return {
    dossierId: str(raw.dossier_id),
    titleFr: str(raw.title_fr),
    summaryFr: str(raw.summary_fr),
    topic: oneOf(raw.topic, TOPICS, 'city'),
    placeFr: str(raw.place_fr),
    plateUrl: strOrNull(raw.plate_url),
    evergreen: Boolean(raw.evergreen),
    stage: parseStage(isObject(raw.stage) ? raw.stage : {}),
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

const MAKE_KINDS = ['headline_choice', 'reader_question'] as const;

export function parseMade(raw: Json): RvMade {
  return {
    kind: oneOf(raw.kind, MAKE_KINDS, 'headline_choice'),
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
  };
}

export function parseQuickReply(raw: Json): RvQuickReply {
  return { label: str(raw.label), sendFr: str(raw.send_fr) };
}

const ROLES = ['purpose', 'place_note', 'reply', 'steer', 'fallback', 'close'] as const;

/** One thread item; an unknown `kind` (a later phase's `guest`) is dropped, never guessed. */
export function parseThreadItem(raw: Json): RvThreadItem | null {
  const base = { id: str(raw.id), seq: num(raw.seq), at: str(raw.at) };
  switch (raw.kind) {
    case 'narration':
      return { ...base, kind: 'narration', textFr: str(raw.text_fr) };
    case 'summary':
      return { ...base, kind: 'summary', speaker: str(raw.speaker) || 'romy_tremblay', textFr: str(raw.text_fr) };
    case 'line':
      return {
        ...base,
        kind: 'line',
        speaker: str(raw.speaker) || 'romy_tremblay',
        role: oneOf(raw.role, ROLES, 'reply'),
        textFr: str(raw.text_fr),
        translation: strOrNull(raw.translation),
        glosses: list(raw.glosses, parseGloss),
      };
    case 'mine':
      return { ...base, kind: 'mine', textFr: str(raw.text_fr), mode: raw.mode === 'voice' ? 'voice' : 'text' };
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
      words: list(kept.words, (word) => ({ fr: str(word.fr), gloss: str(word.gloss), claimId: str(word.claim_id), used: Boolean(word.used) })),
      claims: list(kept.claims, parseClaim),
    },
    questionKeptFr: strOrNull(raw.question_kept_fr),
    colophonFr: str(raw.colophon_fr) || 'La suite la semaine prochaine.',
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
    artifact: isObject(raw.artifact) ? parseMade(raw.artifact) : null,
    closing: isObject(raw.closing) ? parseClosing(raw.closing) : null,
  };
}

export function parseTurnResult(raw: Json): RvTurnResult {
  const evidence = isObject(raw.evidence) ? raw.evidence : {};
  return {
    items: parseThread(raw.items),
    beat: oneOf(raw.beat, BEATS, 'pursue'),
    room: parseRoom(isObject(raw.room) ? raw.room : {}),
    support: parseSupport(isObject(raw.support) ? raw.support : {}),
    quickReplies: list(raw.quick_replies, parseQuickReply),
    steerToMake: Boolean(raw.steer_to_make),
    evidence: {
      outcome: oneOf(evidence.outcome, ['correct', 'incorrect', 'unscored'] as const, 'unscored'),
      capabilityKnown: Boolean(evidence.capability_known),
      grader: str(evidence.grader),
    },
  };
}

export function parseMakeOffer(raw: Json): RvMakeOffer {
  const options: RvMakeOption[] = [];
  for (const option of Array.isArray(raw.options) ? raw.options.filter(isObject) : []) {
    if (option.kind === 'headline_choice') {
      options.push({ kind: 'headline_choice', options: list(option.options, (row) => ({ id: str(row.id), textFr: str(row.text_fr) })) });
    } else if (option.kind === 'reader_question') {
      options.push({ kind: 'reader_question', seedFr: strOrNull(option.seed_fr), uncertaintyFr: strOrNull(option.uncertainty_fr) });
    }
    // A phase-2 kind is never sent; if one were, it is absent here, never greyed.
  }
  const recommended = oneOf(raw.recommended, MAKE_KINDS, 'headline_choice');
  return { recommended, options };
}

export function parseMakeResult(raw: Json): RvMakeResult {
  if (raw.kind === 'headline_choice') {
    const evidence = isObject(raw.evidence) ? raw.evidence : {};
    return {
      kind: 'headline_choice',
      correct: Boolean(raw.correct),
      answerId: str(raw.answer_id),
      evidence: { claimId: str(evidence.claim_id), quote: str(evidence.quote), source: parseSource(isObject(evidence.source) ? evidence.source : {}) },
      made: parseMade(isObject(raw.made) ? raw.made : {}),
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
  return { kind: 'reader_question', made: parseMade(isObject(raw.made) ? raw.made : {}) };
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
  if (body.action === 'propose') return body.text ? { kind: body.kind, action: body.action, text: body.text } : { kind: body.kind, action: body.action };
  return { kind: body.kind, action: body.action, text_fr: body.textFr };
}
