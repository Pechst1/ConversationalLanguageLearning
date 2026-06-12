import type { AtelierSessionStart, AtelierToday } from '@/services/api';

export const REVIEW_THRESHOLD = 1;
export const DAY_PROGRESS_STORAGE_PREFIX = 'atelier:progress';

export interface DayProgress {
  sessionStatus: 'none' | 'active' | 'completed';
  errataDue: number;
  vocabularyDue: number;
  missionDone: boolean;
  feuilletonDone: boolean;
}

export type RecommendedAction =
  | { kind: 'resume_session'; conceptIndex: number; round: string; mode?: string }
  | { kind: 'start_session' }
  | { kind: 'review'; errataDue: number; vocabularyDue: number }
  | { kind: 'mission'; query: string }
  | { kind: 'feuilleton'; query: string }
  | { kind: 'serial'; threadId: string; episodeKind: 'mission' | 'feuilleton'; query: string }
  | { kind: 'rest' };

type DayProgressFlag = 'missionDone' | 'feuilletonDone';

interface ServerDayProgress {
  errataDue?: number;
  vocabularyDue?: number;
  missionDone?: boolean;
  feuilletonDone?: boolean;
}

interface SerialEpisodeEnvelope {
  thread_id?: string;
  kind?: 'mission' | 'feuilleton' | string;
  mission_id?: string | null;
  scene_id?: string | null;
  episode_index?: number | null;
}

type AtelierTodayWithProgress = AtelierToday & {
  progress?: ServerDayProgress | null;
  serial_episode?: SerialEpisodeEnvelope | null;
  serial?: SerialEpisodeEnvelope | null;
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

export function resolveRecommendedNext(
  today: AtelierToday | null,
  session: AtelierSessionStart | null,
  progress: DayProgress,
): RecommendedAction {
  if (progress.sessionStatus === 'active') {
    return {
      kind: 'resume_session',
      conceptIndex: session?.current_position?.concept_index ?? 0,
      round: session?.current_position?.round || 'recognize',
      mode: session?.current_position?.mode,
    };
  }

  if (progress.sessionStatus === 'none') {
    return { kind: 'start_session' };
  }

  const serialAction = serialActionFromToday(today, session);
  if (serialAction) {
    return serialAction;
  }

  if (progress.errataDue + progress.vocabularyDue >= REVIEW_THRESHOLD) {
    return { kind: 'review', errataDue: progress.errataDue, vocabularyDue: progress.vocabularyDue };
  }

  if (!progress.missionDone) {
    return { kind: 'mission', query: dayQueryString(session, today) };
  }

  if (!progress.feuilletonDone) {
    return { kind: 'feuilleton', query: dayQueryString(session, today) };
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
  const status = session?.status;
  const sessionStatus = status === 'active' || status === 'in_progress'
    ? 'active'
    : session?.current_position?.round === 'complete' || status === 'completed'
      ? 'completed'
      : 'none';

  return {
    sessionStatus,
    errataDue: Number(serverProgress?.errataDue ?? today?.summary?.due_errata ?? today?.due_errata?.length ?? 0),
    vocabularyDue: Number(serverProgress?.vocabularyDue ?? vocabularyDue ?? 0),
    missionDone: Boolean(serverProgress?.missionDone ?? false),
    feuilletonDone: Boolean(serverProgress?.feuilletonDone ?? false),
  };
}
