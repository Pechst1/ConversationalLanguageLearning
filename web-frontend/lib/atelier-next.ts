import type { AtelierSessionStart, AtelierToday } from '@/services/api';
import type { ScenarioKey, TodayEnvelope } from '@/types/daily-journey';
import { STORY_FEATURE_VISIBLE } from './launch-flags';

export const REVIEW_THRESHOLD = 1;
export const DAY_PROGRESS_STORAGE_PREFIX = 'atelier:progress';

export interface DayProgress {
  sessionStatus: 'none' | 'active' | 'completed';
  errataDue: number;
  vocabularyDue: number;
  missionDone: boolean;
  missionSuggested: boolean;
  libraryDone: boolean;
  librarySuggested: boolean;
  feuilletonDone: boolean;
  studioDone: boolean;
  studioSuggested: boolean;
  sessionDone?: boolean;
  timeBudgetMinutes?: number;
  estimatedTotalMinutes?: number;
  estimatedRemainingMinutes?: number;
  filed?: boolean;
  nodes?: Array<{
    id: string;
    label: string;
    estimatedMinutes: number;
    /** Drills the session node really contains, from the server's own plan. */
    plannedDrills?: number;
    done?: boolean;
    suggested?: boolean;
  }>;
}

/**
 * Atelier V2 daily-journey branches (WP-07).
 *
 * These sit **in front of** the legacy chain below and only ever apply when
 * `TodayEnvelope.enabled === true`. With the capability off the resolver must
 * return exactly what it returned before this branch existed.
 */
export type JourneyRecommendedAction =
  | { kind: 'journey_resume'; journeyId: string; status: 'active' | 'paused'; scenarioKey: ScenarioKey; titleFr: string }
  | { kind: 'journey_preparing'; journeyId: string; retryAllowed: boolean; retryAfterSeconds: number }
  | {
      kind: 'journey_unavailable';
      journeyId: string;
      retryAllowed: boolean;
      retryAfterSeconds: number;
      /**
       * An unavailable generation is not a finished day: the legacy chain's own
       * answer travels with the branch so the UI can offer retry *and* fall
       * through, exactly as CONTRACT-FREEZE requires.
       */
      fallback: LegacyRecommendedAction;
    }
  | { kind: 'journey_start'; scenarioKey: ScenarioKey; titleFr: string; estimatedSeconds: number };

export type LegacyRecommendedAction =
  | { kind: 'resume_session'; conceptIndex: number; round: string; mode?: string; itemIndex?: number }
  | { kind: 'start_session' }
  | { kind: 'review'; errataDue: number; vocabularyDue: number }
  | { kind: 'mission'; query: string }
  | { kind: 'studio' }
  | { kind: 'library'; bookId: string; episodeIndex: number; href: string; title?: string; bookTitle?: string }
  | { kind: 'feuilleton'; query: string }
  | { kind: 'serial'; threadId: string; episodeKind: 'mission' | 'feuilleton'; query: string }
  | { kind: 'rest' };

export type RecommendedAction = LegacyRecommendedAction | JourneyRecommendedAction;

type DayProgressFlag = 'missionDone' | 'feuilletonDone';

interface ServerDayProgress {
  errataDue?: number;
  vocabularyDue?: number;
  missionDone?: boolean;
  missionSuggested?: boolean;
  libraryDone?: boolean;
  librarySuggested?: boolean;
  feuilletonDone?: boolean;
  studioDone?: boolean;
  studioSuggested?: boolean;
  sessionDone?: boolean;
  timeBudgetMinutes?: number;
  estimatedTotalMinutes?: number;
  estimatedRemainingMinutes?: number;
  filed?: boolean;
  nodes?: DayProgress['nodes'];
}

interface SerialEpisodeEnvelope {
  thread_id?: string;
  kind?: 'mission' | 'feuilleton' | string;
  mission_id?: string | null;
  scene_id?: string | null;
  episode_index?: number | null;
}

interface LibraryEpisodeEnvelope {
  book_id?: string;
  order_index?: number | null;
  episode_index?: number | null;
  href?: string | null;
  title?: string | null;
  book_title?: string | null;
}

type AtelierTodayWithProgress = AtelierToday & {
  progress?: ServerDayProgress | null;
  serial_episode?: SerialEpisodeEnvelope | null;
  serial?: SerialEpisodeEnvelope | null;
  library_episode?: LibraryEpisodeEnvelope | null;
};

export function serialActionFromToday(
  today: AtelierToday | null,
  session: AtelierSessionStart | null,
): Extract<RecommendedAction, { kind: 'serial' }> | null {
  const serialEpisode = (today as AtelierTodayWithProgress | null)?.serial_episode
    || (today as AtelierTodayWithProgress | null)?.serial
    || null;
  if (!serialEpisode?.thread_id || (serialEpisode.kind !== 'mission' && serialEpisode.kind !== 'feuilleton')) {
    return null;
  }
  return {
    kind: 'serial',
    threadId: serialEpisode.thread_id,
    episodeKind: serialEpisode.kind,
    query: serialQueryString(serialEpisode),
  };
}

/**
 * The daily journey's own legacy-session resume, kept **orthogonal** to every
 * journey branch: when it is non-null the UI must always surface a separately
 * labelled resume for that old Atelier session, whichever branch won.
 */
export function legacyResumeEntry(
  envelope: TodayEnvelope | null | undefined,
): { href: string; sessionId: string } | null {
  const resume = envelope?.legacy_resume;
  return resume ? { href: resume.href, sessionId: resume.session_id } : null;
}

/**
 * The capability-aware branch, frozen in CONTRACT-FREEZE.md's "Frontend
 * recommendation precedence (WP-07 / WP-08)". Returns `null` when nothing in
 * the journey wins and the legacy chain must answer instead.
 */
export function resolveJourneyNext(
  envelope: TodayEnvelope | null | undefined,
  fallback: LegacyRecommendedAction,
): JourneyRecommendedAction | null {
  if (!envelope || envelope.enabled !== true) return null;

  const journey = envelope.journey;
  if (journey) {
    // 1. An open journey is resumed, never restarted.
    if (journey.status === 'active' || journey.status === 'paused') {
      return {
        kind: 'journey_resume',
        journeyId: journey.id,
        status: journey.status,
        scenarioKey: journey.scenario.scenario_key,
        titleFr: journey.scenario.title_fr,
      };
    }
    // 2. Preparing shows the server's retry hint. Never start a second one.
    if (journey.status === 'preparing') {
      return {
        kind: 'journey_preparing',
        journeyId: journey.id,
        retryAllowed: journey.retry?.allowed ?? true,
        retryAfterSeconds: journey.retry?.after_seconds ?? 3,
      };
    }
    // 3. Unavailable offers retry AND falls through: it is not a finished day.
    if (journey.status === 'unavailable') {
      return {
        kind: 'journey_unavailable',
        journeyId: journey.id,
        retryAllowed: journey.retry?.allowed ?? false,
        retryAfterSeconds: journey.retry?.after_seconds ?? 30,
        fallback,
      };
    }
    // 4. completed / ended_early: the day's journey is done. Fall through to the
    //    legacy chain for optional practice. Re-entering it is a read and must
    //    not inflate progress or streaks, so no journey branch is returned.
    return null;
  }

  // 5. No journey, but today's scenario is offered.
  if (envelope.available) {
    return {
      kind: 'journey_start',
      scenarioKey: envelope.available.scenario_key,
      titleFr: envelope.available.title_fr,
      estimatedSeconds: envelope.available.estimated_seconds,
    };
  }

  // 6. Anything else: the existing legacy chain, unchanged.
  return null;
}

export function resolveRecommendedNext(
  today: AtelierToday | null,
  session: AtelierSessionStart | null,
  progress: DayProgress,
  journeyEnvelope?: TodayEnvelope | null,
): RecommendedAction {
  const legacy = resolveLegacyRecommendedNext(today, session, progress);
  // With `enabled === false` (or no envelope at all) this returns exactly what
  // the resolver returned before the daily journey existed.
  return resolveJourneyNext(journeyEnvelope, legacy) ?? legacy;
}

/** The pre-V2 chain, unchanged. Kept exported so the branch above can defer to it. */
export function resolveLegacyRecommendedNext(
  today: AtelierToday | null,
  session: AtelierSessionStart | null,
  progress: DayProgress,
): LegacyRecommendedAction {
  if (progress.sessionStatus === 'active') {
    return {
      kind: 'resume_session',
      conceptIndex: session?.current_position?.concept_index ?? 0,
      round: session?.current_position?.round || 'recognize',
      mode: session?.current_position?.mode,
      itemIndex: session?.current_position?.item_index ?? 0,
    };
  }

  if (progress.sessionStatus === 'none') {
    return { kind: 'start_session' };
  }

  const serialAction = serialActionFromToday(today, session);
  const serialActionDone = serialAction
    ? serialAction.episodeKind === 'mission' ? progress.missionDone : progress.feuilletonDone
    : false;
  // An unread episode is the strongest pull in the day. A *read* one used to keep
  // winning this branch for the rest of the day, which buried review, the written
  // mission and the voice studio behind a CTA that reopened finished reading.
  if (serialAction && !serialActionDone) {
    return serialAction;
  }

  if (progress.errataDue + progress.vocabularyDue >= REVIEW_THRESHOLD) {
    return { kind: 'review', errataDue: progress.errataDue, vocabularyDue: progress.vocabularyDue };
  }

  if (!progress.missionDone && progress.missionSuggested) {
    return { kind: 'mission', query: dayQueryString(session, today) };
  }

  // Speaking is prescribed on the days the written mission is not (see
  // `studio_suggested` in the day-progress endpoint), so the habit the product is
  // named for gets a turn in the plan instead of living on an unlinked page.
  if (!progress.studioDone && progress.studioSuggested) {
    return { kind: 'studio' };
  }

  const libraryEpisode = STORY_FEATURE_VISIBLE
    ? (today as AtelierTodayWithProgress | null)?.library_episode || null
    : null;
  if (STORY_FEATURE_VISIBLE && !progress.libraryDone && progress.librarySuggested && libraryEpisode?.book_id) {
    const episodeIndex = Number(libraryEpisode.episode_index ?? libraryEpisode.order_index ?? 0);
    const href = libraryEpisode.href
      || `/notebook?mode=library&book=${libraryEpisode.book_id}&episode=${Number.isFinite(episodeIndex) ? episodeIndex : 0}`;
    return {
      kind: 'library',
      bookId: libraryEpisode.book_id,
      episodeIndex: Number.isFinite(episodeIndex) ? episodeIndex : 0,
      href,
      title: libraryEpisode.title || undefined,
      bookTitle: libraryEpisode.book_title || undefined,
    };
  }

  if (!progress.feuilletonDone) {
    return { kind: 'feuilleton', query: dayQueryString(session, today) };
  }

  // Everything prescribed is filed: the thread stays open for a reread rather
  // than the day ending on a dead end.
  if (serialAction) {
    return serialAction;
  }

  return { kind: 'rest' };
}

export function serialQueryString(
  episode: SerialEpisodeEnvelope,
): string {
  const params = new URLSearchParams();
  if (episode.thread_id) params.set('serial_thread_id', episode.thread_id);
  if (episode.episode_index !== null && episode.episode_index !== undefined) {
    params.set('episode_index', String(episode.episode_index));
  }
  if (episode.kind === 'mission' && episode.mission_id) {
    params.set('mission', episode.mission_id);
  } else if (episode.mission_id) {
    params.set('mission_id', episode.mission_id);
  }
  if (episode.kind === 'feuilleton' && episode.scene_id) {
    params.set('scene', episode.scene_id);
  } else if (episode.scene_id) {
    params.set('scene_id', episode.scene_id);
  }
  const value = params.toString();
  return value ? `?${value}` : '';
}

export function dayQueryString(
  session: AtelierSessionStart | null,
  today: AtelierToday | null,
): string {
  const params = new URLSearchParams();
  const conceptId = session?.current_position?.concept_id ?? session?.concepts?.[0]?.id ?? today?.concepts?.[0]?.id;

  if (conceptId) params.set('concept_id', String(conceptId));
  if (session?.session_id) params.set('atelier_session_id', session.session_id);

  const value = params.toString();
  return value ? `?${value}` : '';
}

export function dayProgressStorageKey(date = new Date()): string {
  return `${DAY_PROGRESS_STORAGE_PREFIX}:${date.toISOString().slice(0, 10)}`;
}

export function readLocalDayProgressFlags(date = new Date()): Pick<DayProgress, 'missionDone' | 'feuilletonDone'> {
  if (typeof window === 'undefined') {
    return { missionDone: false, feuilletonDone: false };
  }

  try {
    const parsed = JSON.parse(window.localStorage.getItem(dayProgressStorageKey(date)) || '{}') as Partial<DayProgress>;
    return {
      missionDone: Boolean(parsed.missionDone),
      feuilletonDone: Boolean(parsed.feuilletonDone),
    };
  } catch {
    return { missionDone: false, feuilletonDone: false };
  }
}

export function writeLocalDayProgressFlag(flag: DayProgressFlag, value = true, date = new Date()) {
  if (typeof window === 'undefined') return;

  try {
    const key = dayProgressStorageKey(date);
    const parsed = JSON.parse(window.localStorage.getItem(key) || '{}') as Partial<DayProgress>;
    window.localStorage.setItem(key, JSON.stringify({ ...parsed, [flag]: value }));
  } catch {
    // Keep local writes best-effort for old tabs and temporary offline UI.
  }
}

export function buildDayProgress(input: {
  today: AtelierToday | null;
  session: AtelierSessionStart | null;
  vocabularyDue?: number | null;
}): DayProgress {
  const { today, session, vocabularyDue } = input;
  const serverProgress = (today as AtelierTodayWithProgress | null)?.progress;
  const localProgress = readLocalDayProgressFlags();
  const serverVocabularyDue = Number(serverProgress?.vocabularyDue ?? 0);
  const contextVocabularyDue = Number(vocabularyDue ?? 0);
  const resolvedVocabularyDue = Math.max(
    Number.isFinite(serverVocabularyDue) ? serverVocabularyDue : 0,
    Number.isFinite(contextVocabularyDue) ? contextVocabularyDue : 0,
  );
  const serverNodes = serverProgress?.nodes || [];
  const visibleServerNodes = STORY_FEATURE_VISIBLE
    ? serverNodes
    : serverNodes.filter((node) => node.id !== 'library');
  const hiddenLibraryMinutes = STORY_FEATURE_VISIBLE
    ? 0
    : serverNodes
        .filter((node) => node.id === 'library')
        .reduce((total, node) => total + Math.max(0, Number(node.estimatedMinutes || 0)), 0);
  const hasVocabularyNode = visibleServerNodes.some((node) => node.id === 'vocabulary');
  const addVocabularyNode = resolvedVocabularyDue > 0 && !hasVocabularyNode;
  const nodes = addVocabularyNode
    ? [
        {
          id: 'vocabulary',
          label: 'Vocabulary',
          estimatedMinutes: 4,
          done: false,
          suggested: true,
        },
        ...visibleServerNodes,
      ]
    : visibleServerNodes;
  const extraVocabularyMinutes = addVocabularyNode ? 4 : 0;
  const status = session?.status;
  const sessionStatus = status === 'active' || status === 'in_progress'
    ? 'active'
    : session?.current_position?.round === 'complete' || status === 'completed'
      ? 'completed'
      : 'none';

  return {
    sessionStatus,
    errataDue: Number(serverProgress?.errataDue ?? today?.summary?.due_errata ?? today?.due_errata?.length ?? 0),
    vocabularyDue: resolvedVocabularyDue,
    missionDone: Boolean(serverProgress?.missionDone ?? localProgress.missionDone),
    missionSuggested: Boolean(serverProgress?.missionSuggested ?? false),
    libraryDone: STORY_FEATURE_VISIBLE
      ? Boolean(serverProgress?.libraryDone ?? !(today as AtelierTodayWithProgress | null)?.library_episode)
      : true,
    librarySuggested: STORY_FEATURE_VISIBLE
      ? Boolean(serverProgress?.librarySuggested ?? Boolean((today as AtelierTodayWithProgress | null)?.library_episode))
      : false,
    feuilletonDone: Boolean(serverProgress?.feuilletonDone ?? localProgress.feuilletonDone),
    studioDone: Boolean(serverProgress?.studioDone ?? false),
    studioSuggested: Boolean(serverProgress?.studioSuggested ?? false),
    sessionDone: Boolean(serverProgress?.sessionDone ?? sessionStatus === 'completed'),
    timeBudgetMinutes: Number(serverProgress?.timeBudgetMinutes ?? 20),
    estimatedTotalMinutes: Math.max(0, Number(serverProgress?.estimatedTotalMinutes ?? 20) - hiddenLibraryMinutes) + extraVocabularyMinutes,
    estimatedRemainingMinutes: Math.max(0, Number(serverProgress?.estimatedRemainingMinutes ?? 20) - hiddenLibraryMinutes) + extraVocabularyMinutes,
    filed: Boolean(serverProgress?.filed ?? false),
    nodes,
  };
}
