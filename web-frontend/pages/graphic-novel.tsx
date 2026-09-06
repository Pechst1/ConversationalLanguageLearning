import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';
import { ArrowRight, Check, Loader2, Pause, Send, Volume2, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { StoryEpisodeReader } from '@/components/atelier-v2/journey/StoryEpisodeReader';
import type { StoryEpisode } from '@/types/daily-journey';
import {
  FeuilletonStyles as SupplementStyles,
  FeMastheadBar,
  FeMasthead,
  FePreviously,
  FeRelChip,
  FeAudioBar,
  FeCliff,
  FePanel,
  FeDialogue,
  FeTask,
  FeSectionNav,
  FeSkeleton,
  FeNotice,
  FeContinuation,
  FeFiled,
  type FeDialogueLine,
} from '@/components/feuilleton/Feuilleton';
import {
  FeuilletonReader,
  FeuilletonReaderStyles,
  attemptsByTaskId,
  buildReaderStages,
  clampStageIndex,
  emptyReaderPosition,
  liveTaskId as resolveLiveTaskId,
  normalizeReaderPosition,
  readerEpisodeLabel,
  readerLocation,
  readerPreviously,
  readerStorageKey,
  resolveFurthest,
  resolveStartIndex,
  type ReaderStage,
} from '@/components/feuilleton/reader';
import { writeLocalDayProgressFlag } from '@/lib/atelier-next';
import { glossFromMap } from '@/lib/glosses';
import { panelImageUrl } from '@/lib/graphic-novel-images';
import { resolveMediaUrl } from '@/lib/media-url';
import { clearResumeActivity, readLocalJson, saveResumeActivity, writeLocalJson } from '@/lib/pilot-resilience';
import apiService, {
  GraphicNovelAttemptResult,
  GraphicNovelCompleteResult,
  GraphicNovelPanel,
  GraphicNovelScene,
  GraphicNovelToday,
  MissionTargetVocabulary,
  SerialCastMember,
  SerialToday,
} from '@/services/api';

type OverlayTask = Record<string, any> & { panel?: GraphicNovelPanel | null };
type PanelBubble = {
  speaker?: string;
  speaker_id?: string;
  fr?: string;
  en?: string;
  x?: number;
  y?: number;
  tone?: string;
  accent_color?: string;
  accent_colour?: string;
};
type PanelCount = 4 | 6 | 8;
type StoryQuality = 'standard' | 'premium';
type HumorStyle = 'dry' | 'satirical' | 'absurd';
type ExperienceMode = 'study' | 'reward';
type RenderMode = 'page' | 'panels';
type ImageQuality = 'low' | 'medium' | 'high';
type FeuilletonVocabularyItem = MissionTargetVocabulary & Record<string, any>;
type FeuilletonThreadContext = {
  summary: string;
  chips: { key: string; label: string; value: string; tone: 'red' | 'blue' | 'yellow' }[];
} | null;
type TaskSubmitError = { taskId: string; message: string } | null;
type MobileTaskStop = {
  id: string;
  elementId: string;
  label: string;
  title: string;
  subtitle: string;
  tasks: OverlayTask[];
  panel?: GraphicNovelPanel | null;
};
type DayProgressFlag = Parameters<typeof writeLocalDayProgressFlag>[0];
type ServerDayProgressCandidate = {
  progress?: Partial<Record<DayProgressFlag, boolean>> | null;
};
type ChoiceOptionView = {
  value: string;
  label: string;
  text: string;
  en: string;
};

function hasServerDayProgressFlag(candidate: unknown, flag: DayProgressFlag) {
  const progress = (candidate as ServerDayProgressCandidate | null)?.progress;
  return Boolean(progress && typeof progress[flag] === 'boolean');
}

async function writeSideQuestProgressFlag(flag: DayProgressFlag) {
  try {
    const atelierToday = await apiService.getAtelierToday();
    if (hasServerDayProgressFlag(atelierToday, flag)) return;
  } catch (error) {
    console.error(error);
  }
  writeLocalDayProgressFlag(flag);
}

function sceneRouteQuery(scene: GraphicNovelScene): Record<string, string | number> {
  const query: Record<string, string | number> = { scene: scene.id };
  if (scene.serial_thread_id) query.serial_thread_id = scene.serial_thread_id;
  if (typeof scene.episode_index === 'number') query.episode_index = scene.episode_index;
  if (scene.mission_id) query.mission_id = scene.mission_id;
  return query;
}

function routeForSerialBeat(serial: SerialToday | null | undefined): string | null {
  if (!serial?.thread_id || typeof serial.episode_index !== 'number') return null;
  if (serial.kind === 'mission') {
    return routeWithQuery('/missions', [
      ['serial_thread_id', serial.thread_id],
      ['episode_index', serial.episode_index],
      ['mission', serial.mission_id || undefined],
    ]);
  }
  if (serial.kind === 'feuilleton') {
    return routeWithQuery('/graphic-novel', [
      ['serial_thread_id', serial.thread_id],
      ['episode_index', serial.episode_index],
      ['scene', serial.scene_id || undefined],
    ]);
  }
  return null;
}

export default function GraphicNovelPage() {
  const router = useRouter();
  const [today, setToday] = useState<GraphicNovelToday | null>(null);
  const [canonicalBeat, setCanonicalBeat] = useState<SerialToday | null>(null);
  const [scene, setScene] = useState<GraphicNovelScene | null>(null);
  // A story-engine episode opened by its scene id. Replay-only here: reading
  // never completes it, and responding goes through the daily journey.
  const [storyEpisode, setStoryEpisode] = useState<StoryEpisode | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [submittingTask, setSubmittingTask] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [taskSubmitError, setTaskSubmitError] = useState<TaskSubmitError>(null);
  const [generationFailure, setGenerationFailure] = useState<Record<string, any> | null>(null);
  const [panelCount, setPanelCount] = useState<PanelCount>(6);
  const [storyQuality, setStoryQuality] = useState<StoryQuality>('standard');
  const [humorStyle, setHumorStyle] = useState<HumorStyle>('satirical');
  const experienceMode: ExperienceMode = 'study';
  const [renderMode, setRenderMode] = useState<RenderMode>('panels');
  const [serialReaderMode, setSerialReaderMode] = useState<'vertical' | 'page'>('vertical');
  const [imageQuality, setImageQuality] = useState<ImageQuality>('medium');
  // Paged reader position. `stageIndex` is where the learner is; `furthest` is
  // the deepest point they have reached, which is what lets a revisit be shown
  // as a revisit instead of guessed at.
  const [stageIndex, setStageIndex] = useState(0);
  const [furthestStage, setFurthestStage] = useState(0);
  const [positionRestoredFor, setPositionRestoredFor] = useState<string | null>(null);
  // The API answers 409 when the scene the learner is holding has been
  // superseded by a rebuild. That is a real state, not a failure to hide.
  const [sceneSuperseded, setSceneSuperseded] = useState(false);
  const autoCreateContextRef = useRef<string | null>(null);
  const routeQuery = useMemo(
    () => (router.isReady ? mergedRouteQuery(router.query, router.asPath) : {}),
    [router.asPath, router.isReady, router.query],
  );
  const routeSceneId = typeof routeQuery.scene === 'string' ? routeQuery.scene : null;
  const contextSceneKey = graphicNovelContextKey(routeQuery);
  const incomingThreadContext = useMemo(() => feuilletonThreadContextFromQuery(routeQuery), [routeQuery]);
  const [threadContext, setThreadContext] = useState<FeuilletonThreadContext>(null);
  const visibleThreadContext = threadContext || incomingThreadContext;
  const serialReadFirst = Boolean(scene?.serial_thread_id);

  const targetVocabulary = useMemo(() => sceneTargetVocabulary(scene), [scene]);
  const sceneNeedsGenerationPolling = useMemo(() => (
    Boolean(scene?.id)
    && ['writing', 'generating'].includes(String(scene?.status || ''))
  ), [scene]);
  const mobileTaskStops = useMemo(() => buildMobileTaskStops(scene), [scene]);
  const attemptsByTask = useMemo(() => {
    const map: Record<string, Record<string, any>> = {};
    (scene?.attempts || []).forEach((attempt) => {
      if (attempt.task_id) map[attempt.task_id] = attempt;
    });
    return map;
  }, [scene?.attempts]);
  const mobileCountableTasks = useMemo(
    () => mobileTaskStops.flatMap((stop) => stop.tasks).filter((task) => task.id),
    [mobileTaskStops],
  );
  const mobileSubmittedCount = useMemo(
    () => mobileCountableTasks.filter((task) => attemptsByTask[task.id]).length,
    [attemptsByTask, mobileCountableTasks],
  );
  // The one learning action still due: the bottom bar's only job is to reach it.
  const nextPendingTask = useMemo(
    () => mobileCountableTasks.find((task) => !attemptsByTask[task.id]) || null,
    [attemptsByTask, mobileCountableTasks],
  );
  const activeTaskId = nextPendingTask?.id ? String(nextPendingTask.id) : null;
  const nextTaskElementId = useMemo(() => {
    if (!nextPendingTask?.id) return null;
    return findMobileTaskStop(mobileTaskStops, String(nextPendingTask.id))?.elementId || null;
  }, [mobileTaskStops, nextPendingTask]);

  /* ---- paged reader model -------------------------------------------------
     Derived from the scene the server sent and nothing else: no fixture, no
     placeholder panel, no synthesised beat. */
  const readerStages: ReaderStage[] = useMemo(() => buildReaderStages(scene as any), [scene]);
  const readerStageKeys = useMemo(() => readerStages.map((entry) => entry.key), [readerStages]);
  const readerAttempts = useMemo(() => attemptsByTaskId(scene as any), [scene]);
  const readerLiveTaskId = useMemo(
    () => resolveLiveTaskId(readerStages, readerAttempts),
    [readerAttempts, readerStages],
  );
  // The illustrated-page render mode composes one printed page; it keeps its own
  // presentation. Everything else reads as paged panels.
  const usesPagedReader = readerStages.length > 0 && scene?.script_payload?.render_mode !== 'page';
  const readerIndex = clampStageIndex(stageIndex, readerStages.length);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    try {
      if (routeSceneId) {
        let loaded: GraphicNovelScene;
        try {
          loaded = await apiService.getGraphicNovelScene(routeSceneId);
        } catch (sceneError: any) {
          // An engine-managed scene answers 409 `story_episode_route`: this is
          // a route transition to the read-only projection, not a superseded
          // scene to regenerate (ENGINE-FRONTEND-CONTRACT §6).
          const detail = sceneError?.response?.data?.detail;
          if (Number(sceneError?.response?.status || 0) === 409 && detail?.code === 'story_episode_route') {
            const episode = await apiService.getStoryEpisode(routeSceneId);
            setStoryEpisode(episode);
            setScene(null);
            setGenerationFailure(null);
            return;
          }
          throw sceneError;
        }
        setStoryEpisode(null);
        setScene(loaded);
        setGenerationFailure(loaded.status === 'failed' ? {
          code: 'feuilleton_generation_failed',
          message: loaded.script_payload?.generation_error || "L’édition n’a pas pu être composée.",
        } : null);
        return;
      }
      if (contextSceneKey) {
        const next = await apiService.getGraphicNovelToday();
        setToday(next);
        setCanonicalBeat(null);
        setScene(null);
        setGenerationFailure(null);
        return;
      }
      const [serialResult, editionsResult] = await Promise.allSettled([
        apiService.getSerialToday(),
        apiService.getGraphicNovelToday(),
      ]);
      const next = editionsResult.status === 'fulfilled' ? editionsResult.value : null;
      setToday(next);
      if (serialResult.status === 'fulfilled') {
        const serial = serialResult.value;
        setCanonicalBeat(serial);
        if (serial.kind === 'feuilleton' && serial.scene_id) {
          let loaded: GraphicNovelScene | null = null;
          try {
            loaded = await apiService.getGraphicNovelScene(serial.scene_id);
          } catch (sceneError: any) {
            // A superseded (pre-rebuild) scene answers 409. The episode is still the
            // learner's episode: drop the stale scene reference so the L'ÉPISODE
            // tab offers to recompose it instead of spinning on a load that can
            // never succeed.
            const status = Number(sceneError?.response?.status || 0);
            console.warn('Feuilleton scene could not be loaded', status, sceneError);
            setCanonicalBeat({ ...serial, scene_id: null, status: status === 409 ? 'available' : serial.status });
            setScene(null);
            setGenerationFailure(status === 409 ? null : {
              code: 'feuilleton_scene_unavailable',
              message: "La planche de l’épisode n’a pas pu être ouverte. Relancez l’édition.",
            });
            return;
          }
          setScene(loaded);
          setGenerationFailure(loaded.status === 'failed' ? {
            code: 'feuilleton_generation_failed',
            message: loaded.script_payload?.generation_error || "L’édition n’a pas pu être composée.",
          } : null);
        } else {
          setScene(null);
          // "delayed" is a state of the serial episode, not a generation failure of
          // this page: the L'ÉPISODE tab renders its own press notice from
          // canonicalBeat (SerialEpisodeDelayed), so the episode keeps its folio.
          setGenerationFailure(null);
        }
        return;
      }
      setCanonicalBeat(null);
      setScene(next?.active_scene || next?.available_scene || null);
      setGenerationFailure(null);
    } catch (error) {
      console.error(error);
      setToday(null);
      setCanonicalBeat(null);
      setScene(null);
      setGenerationFailure(null);
    } finally {
      setLoading(false);
    }
  }, [contextSceneKey, routeSceneId]);

  useEffect(() => {
    if (!router.isReady) return;
    void loadInitial();
  }, [loadInitial, router.isReady]);

  useEffect(() => {
    if (!router.isReady || routeSceneId || !contextSceneKey || loading || creating) return;
    if (autoCreateContextRef.current === contextSceneKey) return;
    autoCreateContextRef.current = contextSceneKey;
    const serialThreadId = typeof routeQuery.serial_thread_id === 'string' ? routeQuery.serial_thread_id : null;
    if (serialThreadId) {
      void openSerialSceneFromQuery(serialThreadId);
      return;
    }
    void createScene();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contextSceneKey, creating, loading, routeSceneId, router.isReady]);

  useEffect(() => {
    if (!router.isReady || !incomingThreadContext) return;
    setThreadContext(incomingThreadContext);
  }, [incomingThreadContext, router.isReady]);

  /* Restore the saved draft AND the saved place, once per scene, as soon as the
     server has told us what the stages are. Identity-first (stage key), so a
     panel whose art lands late cannot move the learner somewhere else. */
  useEffect(() => {
    if (!scene?.id) return;
    if (positionRestoredFor === scene.id) return;
    if (scene.status !== 'completed' && !readerStageKeys.length) return;
    const saved = scene.status === 'completed'
      ? emptyReaderPosition()
      : normalizeReaderPosition(readLocalJson(readerStorageKey(scene.id), {}));
    if (Object.keys(saved.answers).length) {
      setAnswers((current) => ({ ...saved.answers, ...current }));
    }
    const start = resolveStartIndex(saved, readerStageKeys);
    setStageIndex(start);
    setFurthestStage(resolveFurthest(saved, readerStageKeys, start));
    setPositionRestoredFor(scene.id);
    if (scene.status !== 'completed') {
      saveResumeActivity({
        href: `/graphic-novel?scene=${scene.id}`,
        kind: 'reader',
        entityId: scene.id,
      });
      window.requestAnimationFrame(() => window.scrollTo({ top: Number(saved.scrollY || 0) }));
    }
  }, [positionRestoredFor, readerStageKeys, scene?.id, scene?.status]);

  useEffect(() => {
    if (!scene?.id) return;
    setPositionRestoredFor((current) => (current === scene.id ? current : null));
    setSceneSuperseded(false);
  }, [scene?.id]);

  /* Persist draft + place. Writing on every stage change is what makes the
     position survive a reload and a round trip into the word-help sheet. */
  useEffect(() => {
    if (!scene?.id || scene.status === 'completed') return;
    if (positionRestoredFor !== scene.id) return;
    const key = readerStorageKey(scene.id);
    const persist = () => writeLocalJson(key, {
      answers,
      scrollY: window.scrollY,
      stageIndex: readerIndex,
      stageKey: readerStageKeys[readerIndex] ?? null,
      furthest: furthestStage,
    });
    const onScroll = () => window.requestAnimationFrame(persist);
    persist();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      persist();
    };
  }, [answers, furthestStage, positionRestoredFor, readerIndex, readerStageKeys, scene?.id, scene?.status]);

  const onReaderIndexChange = useCallback((next: number) => {
    setStageIndex(next);
    setFurthestStage((current) => Math.max(current, next));
  }, []);

  useEffect(() => {
    if (!scene?.id || !sceneNeedsGenerationPolling) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const loaded = await apiService.getGraphicNovelScene(scene.id);
        if (cancelled) return;
        if (loaded.status === 'failed') {
          setGenerationFailure({
            code: 'feuilleton_generation_failed',
            message: loaded.script_payload?.generation_error || "L’édition n’a pas pu être composée.",
          });
        } else if (loaded.status === 'writing' && feuilletonGenerationIsStalled(loaded)) {
          setGenerationFailure({
            code: 'feuilleton_generation_stalled',
            message: "La rédaction a dépassé son délai. Vous pouvez relancer cette édition sans perdre votre progression.",
          });
        } else {
          setGenerationFailure(null);
        }
        setScene(loaded);
      } catch (error: any) {
        // 409 = this scene has been superseded by a rebuild. Say so and stop
        // polling; never keep spinning on a load that can never succeed, and
        // never silently swap the learner onto a different episode.
        if (Number(error?.response?.status || 0) === 409) {
          cancelled = true;
          setSceneSuperseded(true);
          return;
        }
        console.error(error);
      }
    };
    const timer = window.setInterval(() => {
      if (cancelled) {
        window.clearInterval(timer);
        return;
      }
      void poll();
    }, scene?.status === 'writing' ? 1500 : 3500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [scene?.id, scene?.status, sceneNeedsGenerationPolling]);

  async function openCanonicalBeat() {
    setCreating(true);
    const toastId = toast.loading('Retrouver le fil de votre histoire…');
    try {
      const serial = await apiService.getSerialToday();
      setCanonicalBeat(serial);
      if (String(serial.status || '') === 'journey_required') {
        // Engine-managed learner: the story is today's journey (contract §5).
        toast.success('La suite se joue dans la journée du jour.', { id: toastId });
        await router.push(String((serial as any).continue_href || '/atelier'));
        return;
      }
      if (serial.kind === 'feuilleton' && serial.scene_id) {
        const loaded = await apiService.getGraphicNovelScene(serial.scene_id);
        setScene(loaded);
        setGenerationFailure(null);
        await router.replace({ pathname: '/graphic-novel', query: sceneRouteQuery(loaded) }, undefined, { shallow: true });
        toast.success('L’épisode canonique est ouvert.', { id: toastId });
        return;
      }
      if (serial.kind === 'feuilleton' && serial.status === 'delayed') {
        toast.dismiss(toastId);
        await createScene({
          serial_thread_id: serial.thread_id,
          episode_index: serial.episode_index,
          force_new: true,
        });
        return;
      }
      const nextRoute = routeForSerialBeat(serial);
      if (nextRoute) {
        toast.success(serial.kind === 'mission' ? 'La suite se joue dans la mission du jour.' : 'L’édition reprend.', { id: toastId });
        await router.push(nextRoute);
        return;
      }
      toast.dismiss(toastId);
      await createScene({
        serial_thread_id: serial.thread_id,
        episode_index: serial.episode_index,
        force_new: false,
      });
    } catch (error) {
      console.error(error);
      toast.error('Impossible de retrouver le fil canonique.', { id: toastId });
    } finally {
      setCreating(false);
    }
  }

  async function createScene(extra?: Record<string, any>) {
    setCreating(true);
    if (!scene) setGenerationFailure(null);
    const toastId = toast.loading('Composition de l’édition. Les planches paraîtront une à une.');
    try {
      const conceptIds = queryList(routeQuery.concept_id).map(Number).filter(Boolean);
      const errataIds = queryList(routeQuery.erratum_id);
      const vocabularyIds = queryList(routeQuery.vocabulary_id).map(Number).filter(Boolean);
      const atelierSessionId = typeof routeQuery.atelier_session_id === 'string' ? routeQuery.atelier_session_id : undefined;
      const missionId = typeof routeQuery.mission === 'string'
        ? routeQuery.mission
        : typeof routeQuery.mission_id === 'string'
          ? routeQuery.mission_id
          : undefined;
      const serialThreadId = typeof routeQuery.serial_thread_id === 'string' ? routeQuery.serial_thread_id : undefined;
      const episodeIndex = Number(routeQuery.episode_index);
      const next = await apiService.createGraphicNovelScene({
        cadence: atelierSessionId ? 'post_session' : 'ad_hoc',
        atelier_session_id: atelierSessionId,
        mission_id: missionId,
        serial_thread_id: serialThreadId,
        episode_index: Number.isFinite(episodeIndex) ? episodeIndex : undefined,
        preferred_concept_ids: conceptIds.length ? conceptIds : undefined,
        preferred_errata_ids: errataIds.length ? errataIds : undefined,
        target_vocabulary_ids: vocabularyIds.length ? vocabularyIds : undefined,
        // News is opt-in per authored episode brief only; a standalone edition is
        // a self-contained fictional micro-story and must never pull live news.
        use_news: false,
        panel_count: panelCount,
        story_quality: storyQuality,
        humor_style: humorStyle,
        experience_mode: experienceMode,
        render_mode: renderMode,
        image_quality: imageQuality,
        public_figure_mode: 'named_context',
        force_new: Boolean(scene),
        refresh_news: false,
        async_generation: true,
        ...extra,
      });
      setThreadContext(feuilletonThreadContextFromQuery(routeQuery));
      setScene(next);
      setGenerationFailure(null);
      router.replace({ pathname: '/graphic-novel', query: sceneRouteQuery(next) }, undefined, { shallow: true });
      toast.success(
        next.status === 'writing'
          ? 'Édition lancée. La lecture reste ouverte pendant le travail de la presse.'
          : next.status === 'generating'
            ? 'Récit prêt. Les planches s’impriment.'
            : 'Le Feuilleton est prêt.',
        { id: toastId },
      );
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      if (Number(error?.response?.status || 0) === 409 && detail?.code === 'story_journey_required') {
        // The story continues through today's journey; there is no scene to
        // compose here and nothing to retry (ENGINE-FRONTEND-CONTRACT §6).
        toast.success('La suite se joue dans la journée du jour.', { id: toastId });
        await router.push(String(detail.continue_href || '/atelier'));
        return;
      }
      if (detail?.code === 'feuilleton_generation_failed') {
        if (scene) {
          setGenerationFailure(null);
        } else {
          setGenerationFailure(detail);
        }
      }
      const message = error instanceof Error && error.message === 'Network Error'
        ? 'Le Feuilleton n’a pas pu être créé. Les planches sont peut-être encore sous presse ; réessayez dans un instant.'
        : detail?.code === 'feuilleton_generation_failed'
          ? 'La rédaction n’a pas livré un Feuilleton complet.'
          : 'Le Feuilleton n’a pas pu être créé.';
      toast.error(message, { id: toastId });
    } finally {
      setCreating(false);
    }
  }

  async function openSerialSceneFromQuery(serialThreadId: string) {
    try {
      const episodeIndex = Number(routeQuery.episode_index);
      const serial = await apiService.getSerialToday();
      const sameThread = serial?.thread_id === serialThreadId;
      const sameEpisode = !Number.isFinite(episodeIndex) || serial?.episode_index === episodeIndex;
      if (sameThread && sameEpisode && serial.kind === 'feuilleton' && serial.scene_id) {
        let loaded: GraphicNovelScene | null = null;
        try {
          loaded = await apiService.getGraphicNovelScene(serial.scene_id);
        } catch (sceneError: any) {
          // Superseded scene (409): fall back to the episode card rather than
          // composing an unrelated standalone edition.
          console.warn('Feuilleton scene could not be loaded', sceneError?.response?.status, sceneError);
          setCanonicalBeat({ ...serial, scene_id: null, status: 'available' });
          setScene(null);
          setGenerationFailure(null);
          await router.replace({ pathname: '/graphic-novel' }, undefined, { shallow: true });
          return;
        }
        setThreadContext(feuilletonThreadContextFromQuery(routeQuery));
        setScene(loaded);
        setGenerationFailure(null);
        await router.replace({ pathname: '/graphic-novel', query: sceneRouteQuery(loaded) }, undefined, { shallow: true });
        return;
      }
      if (sameThread && sameEpisode && serial.kind === 'feuilleton' && serial.status === 'delayed') {
        // Same contract as loadInitial: the delayed episode stays an episode.
        setCanonicalBeat(serial);
        setScene(null);
        setGenerationFailure(null);
        return;
      }
      if (sameThread && sameEpisode && serial.kind === 'mission' && serial.mission_id) {
        const query: Record<string, string | number> = {
          serial_thread_id: serial.thread_id,
          episode_index: serial.episode_index,
          mission: serial.mission_id,
        };
        await router.replace({ pathname: '/missions', query }, undefined, { shallow: false });
        return;
      }
    } catch (error) {
      console.error(error);
    }
    void createScene();
  }

  async function submitTask(task: OverlayTask) {
    if (!scene) return;
    const taskId = String(task.id || '');
    const answer = (answers[taskId] || '').trim();
    if (!answer) {
      setTaskSubmitError({ taskId, message: 'Écrivez ou choisissez d’abord une réponse.' });
      toast.error('Écrivez ou choisissez d’abord une réponse.');
      return;
    }
    setTaskSubmitError(null);
    setSubmittingTask(taskId);
    try {
      const result: GraphicNovelAttemptResult = await apiService.submitGraphicNovelAttempt(scene.id, {
        task_id: taskId,
        answer_payload: { answer },
      });
      setScene(result.scene);
      setTaskSubmitError(null);
    } catch (error: any) {
      // 409 here means the episode is already closed or has been superseded.
      // The learner's draft stays on screen; nothing is retried into a second
      // attempt on a beat that no longer accepts one.
      if (Number(error?.response?.status || 0) === 409) {
        setSceneSuperseded(true);
        setTaskSubmitError({
          taskId,
          message: 'Cet épisode a été remplacé ou déjà classé. Votre texte est conservé ; rouvrez l’épisode courant.',
        });
        return;
      }
      setTaskSubmitError({ taskId, message: 'La correction n’a pas pu être transmise. Réessayez.' });
      toast.error('La correction du Feuilleton n’a pas pu être transmise.');
    } finally {
      setSubmittingTask(null);
    }
  }

  async function completeScene() {
    if (!scene) return false;
    // Completion is a mutation, and it happens exactly once. Revisiting a filed
    // episode reads it; it never files it again.
    if (scene.status === 'completed' || completing) return false;
    setCompleting(true);
    try {
      const result: GraphicNovelCompleteResult = await apiService.completeGraphicNovelScene(scene.id);
      setScene(result.scene);
      window.localStorage.removeItem(`pilot:reader:${scene.id}`);
      clearResumeActivity('reader');
      await writeSideQuestProgressFlag('feuilletonDone');
      toast.success('Feuilleton terminé.');
      const nextRoute = routeForSerialBeat(result.next_serial);
      void router.push(nextRoute || '/atelier');
      return true;
    } catch {
      toast.error('Le Feuilleton n’a pas pu être terminé.');
      return false;
    } finally {
      setCompleting(false);
    }
  }

  return (
    <>
      <FeuilletonStyles />
      <SupplementStyles />
      <FeuilletonReaderStyles />
      <main aria-label="Mode Feuilleton" className={`feuilleton-page ${scene ? 'has-scene' : ''} ${serialReadFirst ? 'is-serial' : ''}`}>
        <div className="fn-spread fn-grid">
          <section className="fn-main">
            <div className="fe-embed"><FeMastheadBar /><FeSectionNav active="episode" /></div>
            {scene && !scene.serial_thread_id && !['writing', 'generating'].includes(scene.status) && (
              <div className="feuilleton-reader-tools" aria-label="Contrôles de l’édition">
                <Link href="/atelier">Retour à l’Atelier</Link>
                <button
                  className="new-edition"
                  type="button"
                  disabled={creating || scene.status === 'writing'}
                  onClick={openCanonicalBeat}
                >
                  {creating || scene.status === 'writing' ? <Loader2 className="spin" size={13} /> : <ArrowRight size={13} />}
                  {creating || scene.status === 'writing' ? 'Recherche du fil' : 'Reprendre l’histoire'}
                </button>
              </div>
            )}
            {scene && !scene.serial_thread_id && !['writing', 'generating'].includes(scene.status) && (
              <div className="feuilleton-mobile-edition-tools" aria-label="Contrôles de l’édition">
                <Link href="/atelier">Atelier</Link>
                <button
                  className="new-edition"
                  type="button"
                  disabled={creating || scene.status === 'writing'}
                  onClick={openCanonicalBeat}
                >
                  {creating || scene.status === 'writing' ? <Loader2 className="spin" size={13} /> : <ArrowRight size={13} />}
                  <span>{creating || scene.status === 'writing' ? 'Recherche' : 'Suite canonique'}</span>
                </button>
              </div>
            )}
            {!scene && (
              <div className="fn-title">
                <div>
                  <div className="t-mono">Le Feuilleton · hors édition</div>
                  <h1>Le supplément illustré</h1>
                </div>
                <div className="create-console">
                  <Link className="btn atelier-return" href="/atelier">
                    Retour à La Une <ArrowRight size={14} />
                  </Link>
                </div>
              </div>
            )}

            {creating && (
              <GenerationProgress
                imageQuality={imageQuality}
                panelCount={panelCount}
                renderMode={renderMode}
              />
            )}

            {!scene && visibleThreadContext && (
              <TodayThreadBanner context={visibleThreadContext} />
            )}

            {loading ? (
              <div className="paper loading feuilleton-loading" aria-live="polite">
                <Loader2 className="spin" />
                <span className="loading-label">Ouverture du Feuilleton</span>
                <p className="mobile-loading-copy">Recherche de l’édition en cours. Si aucune n’est prête, un seul bouton permettra de la composer.</p>
                <div className="mobile-loading-stack" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            ) : generationFailure ? (
              <EditionPreparing failure={generationFailure} onRetry={canonicalBeat ? openCanonicalBeat : () => createScene()} creating={creating} />
            ) : scene && (scene.status === 'writing' || (scene.status === 'generating' && !(scene.panels || []).length)) ? (
              <EditionWriting scene={scene} />
            ) : storyEpisode ? (
              <StoryEpisodeReader
                episode={storyEpisode}
                mode="replay"
                onExit={() => { void router.push('/serial'); }}
                nextHref="/serial"
                nextLabel="Retour à la saison"
              />
            ) : scene && usesPagedReader ? (
              <>
                <FeuilletonReader
                  episodeLabel={readerEpisodeLabel(scene as any)}
                  title={scene.title || 'Le feuilleton'}
                  location={readerLocation(scene as any)}
                  previously={readerPreviously(scene as any)}
                  stages={readerStages}
                  index={readerIndex}
                  furthest={furthestStage}
                  onIndexChange={onReaderIndexChange}
                  answers={answers}
                  setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                  onSubmit={(task) => void submitTask(task as OverlayTask)}
                  submittingTask={submittingTask}
                  attemptsByTask={readerAttempts}
                  submitError={taskSubmitError}
                  liveTaskId={readerLiveTaskId}
                  onExit={() => { void router.push('/atelier'); }}
                  onComplete={scene.status === 'completed' ? null : () => { void completeScene(); }}
                  completing={completing}
                  filed={scene.status === 'completed'}
                  nextHref={feuilletonNextBeat(scene).href}
                  nextLabel={feuilletonNextBeat(scene).label}
                  banner={(
                    <>
                      {sceneSuperseded && (
                        <div className="fr-notice is-stale" role="status">
                          <h2>Cette édition a été remplacée.</h2>
                          <p>
                            Votre lecture et vos réponses restent ici. L’épisode courant du feuilleton
                            peut être rouvert quand vous voulez.
                          </p>
                          <button
                            type="button"
                            className="fr-btn is-action"
                            disabled={creating}
                            onClick={() => void openCanonicalBeat()}
                          >
                            {creating ? 'Recherche…' : 'Rouvrir l’épisode courant'}
                          </button>
                        </div>
                      )}
                      {scene.status === 'generating' && <ReaderArtProgress scene={scene} />}
                      <ReaderCastLink scene={scene} />
                    </>
                  )}
                />
                <EpisodeAudioControls scene={scene} />
              </>
            ) : scene ? (
              <>
                {scene.status === 'generating' && <EditionArtProgress scene={scene} />}
                {!serialReadFirst && <StandaloneReaderMast scene={scene} />}
                {serialReadFirst ? (
                  <SerialSceneReader
                    scene={scene}
                    readerMode={serialReaderMode}
                    setReaderMode={setSerialReaderMode}
                    answers={answers}
                    setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                    onSubmit={submitTask}
                    submittingTask={submittingTask}
                    attemptsByTask={attemptsByTask}
                    submitError={taskSubmitError}
                    activeTaskId={activeTaskId}
                  />
                ) : scene.script_payload?.render_mode === 'page' ? (
                  <div id="reading-panels">
                    <PageScene
                      scene={scene}
                      answers={answers}
                      setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                      onSubmit={submitTask}
                      submittingTask={submittingTask}
                      attemptsByTask={attemptsByTask}
                      submitError={taskSubmitError}
                      activeTaskId={activeTaskId}
                    />
                  </div>
                ) : (
                  <section className="panel-grid" id="reading-panels">
                    {(scene.panels || []).map((panel) => (
                      <PanelCard
                        key={panel.id}
                        panel={panel}
                        answers={answers}
                        setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                        onSubmit={submitTask}
                        submittingTask={submittingTask}
                        attemptsByTask={attemptsByTask}
                        submitError={taskSubmitError}
                        activeTaskId={activeTaskId}
                      />
                    ))}
                  </section>
                )}
                <EpisodeAudioControls scene={scene} />
                <SerialFinalAct
                  scene={scene}
                  answers={answers}
                  setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                  onSubmit={submitTask}
                  submittingTask={submittingTask}
                  attemptsByTask={attemptsByTask}
                  submitError={taskSubmitError}
                  activeTaskId={activeTaskId}
                />
                <FeuilletonCliffhangerHero scene={scene} />
                <FeuilletonEnd
                  scene={scene}
                  vocabulary={targetVocabulary}
                  completing={completing}
                  onComplete={completeScene}
                />
                <MobileReadingBar
                  nextTaskElementId={nextTaskElementId}
                  onExit={() => {
                    void router.push('/atelier');
                  }}
                />
              </>
            ) : (
              <EpisodeTabSurface
                canonicalBeat={canonicalBeat}
                creating={creating}
                onCreate={() => createScene()}
                onOpenSerial={openCanonicalBeat}
                today={today}
                threadContext={visibleThreadContext}
              />
            )}
          </section>
        </div>
      </main>
      <PhoneProductNav active="feuilleton" />
    </>
  );
}

/* Where the story goes after this episode — read from the server's own hook, in
   the reader's visual system. When the payload names no next beat, the reader
   offers nothing rather than promising a chapter that does not exist. */
function feuilletonNextBeat(scene: GraphicNovelScene): { href: string | null; label: string } {
  const hook = scene.hook || scene.script_payload?.hook || scene.recap?.hook || {};
  const nextIsMission = hook?.next_beat_kind === 'mission';
  const nextEpisode = typeof scene.episode_index === 'number' ? scene.episode_index + 1 : undefined;
  if (nextIsMission) {
    return {
      href: routeWithQuery('/missions', [
        ['mission', scene.mission_id || undefined],
        ['atelier_session_id', scene.atelier_session_id || undefined],
        ['serial_thread_id', scene.serial_thread_id || undefined],
        ['episode_index', nextEpisode],
      ]),
      label: 'Agir dans Le Courrier',
    };
  }
  if (!scene.serial_thread_id) return { href: null, label: '' };
  return {
    href: routeWithQuery('/graphic-novel', [
      ['serial_thread_id', scene.serial_thread_id],
      ['episode_index', nextEpisode],
    ]),
    label: 'Lire le prochain épisode',
  };
}

/* The same real numbers as the legacy notice, in the reader's own surface. */
function ReaderArtProgress({ scene }: { scene: GraphicNovelScene }) {
  const panels = scene.panels || [];
  const ready = panels.filter((panel) => Boolean(panelImageUrl(panel))).length;
  return (
    <div className="fr-notice" role="status" aria-live="polite">
      <p>
        L’histoire est complète et lisible. Les illustrations s’impriment en arrière-plan —{' '}
        {ready} sur {panels.length}.
      </p>
    </div>
  );
}

/* The relationship the learner has actually built with the character in this
   episode. Best effort: the read never blocks on it, and nothing is shown when
   the server has no cast for this thread. */
function ReaderCastLink({ scene }: { scene: GraphicNovelScene }) {
  const [member, setMember] = useState<SerialCastMember | null>(null);
  const episodeIndex = typeof scene.episode_index === 'number' ? scene.episode_index : null;
  useEffect(() => {
    if (episodeIndex === null) return undefined;
    let alive = true;
    apiService.getSerialCast()
      .then((data) => {
        if (!alive) return;
        const inEpisode = (data.cast || []).filter((candidate) =>
          (candidate.episodes || []).some((episode) => episode.episode_index === episodeIndex));
        setMember([...inEpisode].sort(
          (a, b) => Number(b.relationship?.closeness || 0) - Number(a.relationship?.closeness || 0),
        )[0] || null);
      })
      .catch(() => { /* best effort */ });
    return () => { alive = false; };
  }, [episodeIndex]);
  if (!member) return null;
  const register = String(member.relationship?.register || 'vous').toLowerCase() === 'tu' ? 'tu' : 'vous';
  return (
    <div className="fr-tools">
      <Link className="fr-chip" href="/serial/cast">
        <span className="sq" aria-hidden="true" />
        {member.name} · vous vous dites « {register} »
      </Link>
    </div>
  );
}

function GenerationProgress({
  imageQuality,
  panelCount,
  renderMode,
}: {
  imageQuality: ImageQuality;
  panelCount: PanelCount;
  renderMode: RenderMode;
}) {
  const visualTarget = renderMode === 'page' ? 'la page illustrée' : `${panelCount} planches`;
  return (
    <section className="paper generation-progress" aria-live="polite">
      <Loader2 className="spin" size={18} />
      <div>
        <strong>Écriture du ressort, puis impression de {visualTarget}</strong>
        <p>Les images demandent le plus de temps. La qualité {imageQuality} reste active pour garder les planches lisibles.</p>
        <div className="mobile-generation-steps" aria-label="Progression de l’impression">
          <span className="active">Récit</span>
          <span className="active">Planches</span>
          <span>Tâches</span>
        </div>
        <p className="mobile-generation-note">Gardez cet écran ouvert. Les tâches paraissent dès que la scène est prête.</p>
      </div>
    </section>
  );
}

/* L'ÉPISODE — the tab's decision tree.
   The FEUILLETON door used to open straight onto the standalone "supplément"
   compose-a-scene state, even for a learner whose day carries a serial episode
   (the one La Une advertises as "LE FEUILLETON · ÉPISODE N"). The serial beat is
   now the tab's primary face:
     · feuilleton episode with a scene   → the reader (handled upstream: the scene
                                           is loaded in loadInitial and rendered)
     · feuilleton episode, no scene yet  → SerialEpisodeLead (open / follow press)
     · episode status "delayed"          → SerialEpisodeDelayed (press notice + retry)
     · episode status "completed"        → SerialEpisodeFiled (filed + LA SAISON)
     · mission beat                      → the canonical handoff (unchanged)
     · no serial thread at all           → the standalone supplément empty state
   In every serial case the supplément stays reachable, but as a margin note. */
function EpisodeTabSurface({
  canonicalBeat,
  creating,
  onCreate,
  onOpenSerial,
  today,
  threadContext,
}: {
  canonicalBeat: SerialToday | null;
  creating: boolean;
  onCreate: () => void;
  onOpenSerial: () => void;
  today: GraphicNovelToday | null;
  threadContext: FeuilletonThreadContext;
}) {
  const canonicalRoute = routeForSerialBeat(canonicalBeat);
  if (canonicalBeat?.kind === 'feuilleton') {
    const status = String(canonicalBeat.status || '');
    return (
      <>
        {status === 'delayed' ? (
          <SerialEpisodeDelayed beat={canonicalBeat} creating={creating} onRetry={onOpenSerial} />
        ) : status === 'completed' ? (
          <SerialEpisodeFiled beat={canonicalBeat} onOpenSerial={onOpenSerial} />
        ) : (
          <SerialEpisodeLead beat={canonicalBeat} creating={creating} onOpenSerial={onOpenSerial} />
        )}
        <SupplementAside creating={creating} onCreate={onCreate} />
      </>
    );
  }
  if (canonicalBeat?.kind === 'mission' && canonicalRoute) {
    return (
      <>
        <CanonicalMissionHandoff canonicalBeat={canonicalBeat} canonicalRoute={canonicalRoute} />
        <SupplementAside creating={creating} onCreate={onCreate} />
      </>
    );
  }
  return (
    <FeuilletonEmptyState
      creating={creating}
      onCreate={onCreate}
      today={today}
      threadContext={threadContext}
    />
  );
}

function serialEpisodeNumber(beat: SerialToday) {
  return typeof beat.episode_index === 'number' ? beat.episode_index + 1 : 1;
}

function serialSeasonNumber(beat: SerialToday) {
  const world = beat.thread?.world_bible;
  const season = Number(world?.season_number);
  return Number.isFinite(season) && season > 0 ? season : 1;
}

/* The serial episode of the day, before its planches are on the desk. */
function SerialEpisodeLead({
  beat,
  creating,
  onOpenSerial,
}: {
  beat: SerialToday;
  creating: boolean;
  onOpenSerial: () => void;
}) {
  const number = serialEpisodeNumber(beat);
  const pressing = ['generating', 'writing'].includes(String(beat.status || ''));
  const names = serialBeatCharacterNames(beat);
  return (
    <section className="canonical-beat-handoff serial-episode-lead" aria-label="Épisode du Feuilleton">
      <div className="canonical-beat-number">
        <span>SAISON {serialSeasonNumber(beat)}</span>
        <strong>{String(number).padStart(2, '0')}</strong>
        <em>ÉPISODE</em>
      </div>
      <div className="canonical-beat-copy">
        <span className="t-mono">LE FEUILLETON · ÉPISODE {number}</span>
        <h2>{pressing ? 'L’épisode du jour est sous presse.' : 'L’épisode du jour vous attend.'}</h2>
        <p>{pressing
          ? 'La rédaction compose la planche. Rouvrez dans un instant : votre place dans la saison est gardée.'
          : serialBeatStoryPressure(beat)}</p>
        {names.length > 0 && (
          <div className="canonical-cast" aria-label="Personnages de cet épisode">
            {names.map((name) => <span key={name}>{name}</span>)}
          </div>
        )}
        <button className="canonical-beat-cta" type="button" disabled={creating} onClick={onOpenSerial}>
          {creating ? <Loader2 className="spin" size={16} /> : null}
          {pressing ? 'Voir où en est l’épisode' : 'Ouvrir l’épisode du jour'}
          {creating ? null : <ArrowRight size={18} />}
        </button>
        <small>C’est l’épisode annoncé à La Une. Il continue votre saison ; il n’en ouvre pas une autre.</small>
      </div>
    </section>
  );
}

/* Honest press notice for an episode the backend reports as "delayed". */
function SerialEpisodeDelayed({
  beat,
  creating,
  onRetry,
}: {
  beat: SerialToday;
  creating: boolean;
  onRetry: () => void;
}) {
  const number = serialEpisodeNumber(beat);
  return (
    <section className="fe-embed serial-episode-notice" aria-label="Épisode retardé du Feuilleton">
      <FeNotice
        label={`Le Feuilleton · Épisode ${number}`}
        msg="L’épisode est retardé — la rédaction met la planche sous presse."
        onRetry={creating ? undefined : onRetry}
        retryLabel="Réessayer"
      />
      <div className="edition-actions">
        {creating && <span className="edition-retrying"><Loader2 className="spin" size={14} /> Nouvelle tentative</span>}
        <Link className="edition-link" href="/serial">Relire la saison <ArrowRight size={13} /></Link>
        <Link className="edition-link" href="/atelier">Retour à La Une <ArrowRight size={13} /></Link>
      </div>
    </section>
  );
}

/* The episode of the day has already been read and filed into the season. */
function SerialEpisodeFiled({ beat, onOpenSerial }: { beat: SerialToday; onOpenSerial: () => void }) {
  const number = serialEpisodeNumber(beat);
  return (
    <section className="fe-embed serial-episode-filed" aria-label="Épisode classé du Feuilleton">
      <FeFiled label={`Classé · Épisode ${number}`} />
      <h2>L’épisode du jour est classé.</h2>
      <p>Il a rejoint la saison reliée. La suite paraîtra au prochain épisode.</p>
      <FeContinuation
        readNext="Reprendre le fil"
        actIn="Ouvrir la saison reliée"
        onReadNext={onOpenSerial}
        actInHref="/serial"
      />
    </section>
  );
}

/* The standalone supplément is optional and secondary wherever a serial thread
   exists: a margin note under the episode, never the tab's default face. */
function SupplementAside({ creating, onCreate }: { creating: boolean; onCreate: () => void }) {
  return (
    <aside className="supplement-aside" aria-label="Supplément illustré du Feuilleton">
      <span className="t-mono">En marge</span>
      <button type="button" className="supplement-link" disabled={creating} onClick={onCreate}>
        {creating ? <Loader2 className="spin" size={13} /> : null}
        <span>{creating ? 'Composition en cours' : 'Le supplément illustré'}</span>
        {creating ? null : <ArrowRight size={13} />}
      </button>
      <p>Une scène composée à la demande, en marge du feuilleton. Elle ne change rien à la saison.</p>
    </aside>
  );
}

function CanonicalMissionHandoff({
  canonicalBeat,
  canonicalRoute,
}: {
  canonicalBeat: SerialToday;
  canonicalRoute: string;
}) {
  if (canonicalBeat?.kind === 'mission' && canonicalRoute) {
    const names = serialBeatCharacterNames(canonicalBeat);
    const storyPressure = serialBeatStoryPressure(canonicalBeat);
    return (
      <section className="canonical-beat-handoff" aria-label="Prochain acte du Feuilleton">
        <div className="canonical-beat-number">
          <span>SAISON 1</span>
          <strong>{String(canonicalBeat.episode_index + 1).padStart(2, '0')}</strong>
          <em>ACTE</em>
        </div>
        <div className="canonical-beat-copy">
          <span className="t-mono">VOTRE HISTOIRE · MAINTENANT</span>
          <h2>La suite se joue avant de se lire.</h2>
          <p>{storyPressure}</p>
          {names.length > 0 && (
            <div className="canonical-cast" aria-label="Personnages de cet acte">
              {names.map((name) => <span key={name}>{name}</span>)}
            </div>
          )}
          <Link className="canonical-beat-cta" href={canonicalRoute}>
            Ouvrir la mission du jour <ArrowRight size={18} />
          </Link>
          <small>Votre réponse deviendra la conséquence du prochain épisode. Aucun récit parallèle ne sera créé.</small>
        </div>
      </section>
    );
  }
  return null;
}

/* No serial thread at all — the supplément keeps its original first-run face. */
function FeuilletonEmptyState({
  creating,
  onCreate,
  today,
  threadContext,
}: {
  creating: boolean;
  onCreate: () => void;
  today: GraphicNovelToday | null;
  threadContext: FeuilletonThreadContext;
}) {
  const recommendation = today?.recommendation || {};
  const seedLabel = threadContext
    ? 'Fil de l’Atelier prêt'
    : recommendation?.reason
      ? 'Sujet du jour prêt'
      : 'Lecture facultative';
  const seedCopy = threadContext?.summary
    || recommendation?.reason
    || 'Composez une édition pour une courte pause de lecture. La feuille de tâches n’apparaît qu’avec les planches.';
  return (
    <section className="paper empty-state feuilleton-empty-state" data-feuilleton-empty="true" aria-label="Feuilleton sans édition">
      <div className="empty-state-copy">
        <span className="t-mono">{seedLabel}</span>
        <h2>Aucune scène sur le pupitre.</h2>
        <p>{seedCopy}</p>
      </div>
      <div className="mobile-empty-task-note" role="note">
        <strong>Feuille de tâches verrouillée</strong>
        <span>Les tâches se déplient sous les planches une fois l’édition composée.</span>
      </div>
      {creating ? (
        <div className="feuilleton-empty-status" aria-live="polite">
          <Loader2 className="spin" size={14} />
          COMPOSITION EN COURS
        </div>
      ) : (
        <button aria-label="Composer une nouvelle scène du Feuilleton" className="btn red" onClick={onCreate}>
          Composer la première scène <ArrowRight size={14} />
        </button>
      )}
    </section>
  );
}

function serialBeatCharacterNames(serial: SerialToday) {
  const required = Array.isArray(serial.brief_payload?.required_cast)
    ? serial.brief_payload?.required_cast.map(String)
    : [];
  const world = serial.thread?.world_bible || {};
  const cast = Array.isArray(world.cast) ? world.cast : [];
  const namesById: Record<string, string> = {
    landlord_marchand: 'M. Marchand',
    marin_leveque: 'Marin',
    lila_bonnet: 'Lila',
    romy_tremblay: 'Romy',
    augustin_de_roncourt: 'Gus',
    margaux_barman: 'Margaux',
  };
  cast.forEach((member: Record<string, any>) => {
    if (member?.id && member?.name) namesById[String(member.id)] = String(member.name);
  });
  return required.map((id: string) => namesById[id] || id.replace(/_/g, ' ')).slice(0, 3);
}

function serialBeatStoryPressure(serial: SerialToday) {
  const brief = serial.brief_payload || {};
  const plot = brief.a_plot || {};
  const required = Array.isArray(brief.required_cast) ? brief.required_cast.map(String) : [];
  const previous = String(serial.previously || serial.hook_from_previous?.text || '').trim();
  if (previous) return `Précédemment : ${previous}`;
  if (required.includes('landlord_marchand')) {
    return 'Votre message à M. Marchand doit régler le problème de l’appartement. Sa réponse deviendra la première conséquence du Feuilleton.';
  }
  const stage = String(plot.stage_summary || plot.summary || '').trim();
  const looksEnglish = /\b(the|your|with|must|will|from|into|about)\b/i.test(stage);
  if (stage && !looksEnglish) return stage;
  return 'Une réponse réelle doit faire avancer la situation. Le prochain épisode montrera exactement ce qu’elle a changé.';
}


// The sticky bar carries the single action that matters: leave the reader, and
// — only while one is due — reach the one learning action. No progress counters.
function MobileReadingBar({
  nextTaskElementId,
  onExit,
}: {
  nextTaskElementId: string | null;
  onExit: () => void;
}) {
  return (
    <nav className="mobile-reading-bar" aria-label="Actions de lecture du Feuilleton">
      <button type="button" onClick={onExit}>
        <X size={12} /> Quitter
      </button>
      {nextTaskElementId && (
        <button className="primary" type="button" onClick={() => scrollToFeuilletonSection(nextTaskElementId)}>
          Votre réplique <ArrowRight size={12} />
        </button>
      )}
    </nav>
  );
}

function SerialSceneReader({
  scene,
  readerMode,
  setReaderMode,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  submitError,
  activeTaskId,
}: {
  scene: GraphicNovelScene;
  readerMode: 'vertical' | 'page';
  setReaderMode: (mode: 'vertical' | 'page') => void;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  submitError: TaskSubmitError;
  /* Only the next unanswered action is live; the rest of the read stays clean. */
  activeTaskId: string | null;
}) {
  const hasComicPage = Boolean(scene.script_payload?.page_image?.url || scene.script_payload?.render_mode === 'page');
  const activeMode = hasComicPage ? readerMode : 'vertical';
  return (
    <section className="serial-reader" id="reading-panels" aria-label="Lecteur de l’épisode">
      <SerialReaderMast scene={scene} />
      {hasComicPage && (
        <div className="serial-reader-toggle" role="tablist" aria-label="Mode de lecture">
          <button
            aria-selected={activeMode === 'vertical'}
            className={activeMode === 'vertical' ? 'active' : ''}
            onClick={() => setReaderMode('vertical')}
            role="tab"
            type="button"
          >
            Défilement
          </button>
          <button
            aria-selected={activeMode === 'page'}
            className={activeMode === 'page' ? 'active' : ''}
            onClick={() => setReaderMode('page')}
            role="tab"
            type="button"
          >
            Page illustrée
          </button>
        </div>
      )}
      {activeMode === 'page' ? (
        <PageScene
          scene={scene}
          answers={answers}
          setAnswer={setAnswer}
          onSubmit={onSubmit}
          submittingTask={submittingTask}
          attemptsByTask={attemptsByTask}
          submitError={submitError}
          activeTaskId={activeTaskId}
        />
      ) : (
        <div className="serial-panel-stack">
          {(scene.panels || []).map((panel) => (
            <SerialPanel
              key={panel.id}
              panel={panel}
              answers={answers}
              setAnswer={setAnswer}
              onSubmit={onSubmit}
              submittingTask={submittingTask}
              attemptsByTask={attemptsByTask}
              submitError={submitError}
              activeTaskId={activeTaskId}
            />
          ))}
        </div>
      )}
    </section>
  );
}

// Unifies the four-route Feuilleton IA: the reader, the season archive, and the
// cast are one section of the paper, so each is reachable from the others.
// Rendered here and mirrored on /serial and /serial/cast.
// Surfaces the relationship the learner has built with the character in this
// episode (register + closeness) so the bond is felt while reading/acting, not
// only on the cast page. Self-contained: fetches the current thread cast once
// and matches the member appearing in this episode with the closest bond.
function characterInitial(value?: string | null): string {
  const text = String(value || '').trim();
  return text ? text.charAt(0).toUpperCase() : '?';
}

// Surfaces the relationship the learner has built with the character in this
// episode (register + closeness) so the bond is felt while reading/acting, not
// only on the cast page. Redrawn onto the shared supplement FeRelChip; still
// self-contained (best-effort fetch, links to the cast).
function SerialRelationshipChip({ scene }: { scene: GraphicNovelScene }) {
  const [member, setMember] = useState<SerialCastMember | null>(null);
  const episodeIndex = typeof scene.episode_index === 'number' ? scene.episode_index : null;
  useEffect(() => {
    if (episodeIndex === null) return;
    let alive = true;
    apiService.getSerialCast()
      .then((data) => {
        if (!alive) return;
        const inEpisode = (data.cast || []).filter((candidate) =>
          (candidate.episodes || []).some((episode) => episode.episode_index === episodeIndex));
        const primary = [...inEpisode].sort(
          (a, b) => Number(b.relationship?.closeness || 0) - Number(a.relationship?.closeness || 0),
        )[0] || null;
        setMember(primary);
      })
      .catch(() => { /* relationship cue is best-effort; the read never blocks on it */ });
    return () => { alive = false; };
  }, [episodeIndex]);

  if (!member) return null;
  const register = String(member.relationship?.register || 'vous').toLowerCase() === 'tu' ? 'tu' : 'vous';
  const closeness = Number(member.relationship?.closeness || 0);
  return (
    <Link
      href="/serial/cast"
      className="serial-rel-chip"
      aria-label={`Relation avec ${member.name} : ${register}, proximité ${closeness} sur 5`}
    >
      <FeRelChip
        char={member.id}
        accent={member.accent_colour}
        name={member.name}
        ini={characterInitial(member.name)}
        register={register}
        closeness={closeness}
      />
    </Link>
  );
}


/* ONE compact Feuilleton header: the folio kicker (section · saison · épisode),
   the serif title, one dateline (lieu · date), the relationship cue, and
   "Précédemment" as one quiet italic line when a previous hook exists.
   Gone: the second "Saison 1" in the dateline, and the "Cette semaine ·
   l’actualité française du jour" news kicker — news is opt-in per authored
   brief (audit P0.1) and its label must never print without a news panel. */
function SerialReaderMast({ scene }: { scene: GraphicNovelScene }) {
  const episodeNo = typeof scene.episode_index === 'number' ? scene.episode_index + 1 : 1;
  const loc = serialLocation(scene);
  const dateLabel = feuilletonEditionDate(scene) || "Aujourd’hui";
  const previously = serialPreviouslyText(scene);
  return (
    <header className="fe-embed serial-reader-mast">
      <FeMasthead
        season={1}
        index={episodeNo}
        title={scene.title || 'Le feuilleton'}
        dateline={[loc, dateLabel].filter(Boolean) as string[]}
      />
      <div className="serial-mast-rel">
        <SerialRelationshipChip scene={scene} />
      </div>
      {previously && <FePreviously>{previously}</FePreviously>}
    </header>
  );
}

function StandaloneReaderMast({ scene }: { scene: GraphicNovelScene }) {
  const dateLabel = feuilletonEditionDate(scene) || "Aujourd’hui";
  const brief = feuilletonPublicBrief(scene.brief);
  return (
    <header className="fe-embed standalone-reader-mast">
      <FeMasthead
        season={null}
        index="du jour"
        title={scene.title || 'Le Feuilleton'}
        dateline={[dateLabel]}
        progress={scene.status === 'completed' ? 100 : 42}
        progressRed={scene.status !== 'completed'}
      />
      {brief && <p>{brief}</p>}
    </header>
  );
}

/* ONE panel = the art (or one quiet "sous presse" plate), one numeral, the
   dialogue as lines with canonical short names, and a caption only when it adds
   something the dialogue does not. No per-panel kicker, credit line, direction
   slug, duplicate numeral, vocabulary chip or task-sheet launcher. */
function SerialPanel({
  panel,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  submitError,
  activeTaskId,
}: {
  panel: GraphicNovelPanel;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  submitError: TaskSubmitError;
  /* Only the next unanswered action is live; the rest of the read stays clean. */
  activeTaskId: string | null;
}) {
  const overlay = panel.overlay_payload || {};
  const tasks = ((overlay.tasks || []) as OverlayTask[]).map((task) => ({ ...task, panel }));
  const stop = panelTaskStop(panel, tasks);
  const imageUrl = resolveMediaUrl(panelImageUrl(panel));
  const printing = !imageUrl && panel.generation_metadata?.image_status === 'queued';
  const who = serialPanelCharacter(panel);
  const lines = panelDialogueLines(panel);
  const caption = additivePanelCaption(panel, lines);
  const [translated, setTranslated] = useState(false);
  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.34, delay: (panel.panel_index || 1) * 0.05 }}
      className="fe-embed fe-story-panel"
      data-char={who}
      data-mobile-task-stop={stop.id}
      id={stop.elementId}
    >
      <FePanel
        imageUrl={imageUrl}
        imageAlt=""
        status={printing ? 'generating' : undefined}
        caption={caption}
        capNum={String(panel.panel_index || 1).padStart(2, '0')}
      />
      <FeDialogue
        char={who}
        lines={lines}
        translated={translated}
        onTranslate={() => setTranslated((current) => !current)}
      />
      <PanelTask
        tasks={tasks}
        answers={answers}
        setAnswer={setAnswer}
        onSubmit={onSubmit}
        submittingTask={submittingTask}
        attemptsByTask={attemptsByTask}
        submitError={submitError}
        activeTaskId={activeTaskId}
      />
    </motion.article>
  );
}

/* The one quiet inline action under a panel: kicker → prompt → input → Envoyer
   → one response. (Was: a task-sheet launcher with counters, then a repeated
   uppercase prompt, then the prompt again inside the controls.) */
function PanelTask({
  tasks,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  submitError,
  activeTaskId,
  kicker = 'Votre réplique',
}: {
  tasks: OverlayTask[];
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  submitError: TaskSubmitError;
  activeTaskId: string | null;
  kicker?: string;
}) {
  // Answered actions stay visible with their response; of the unanswered ones,
  // only the next in reading order is live (audit checklist #11).
  const validTasks = tasks
    .filter((task) => task.id)
    .filter((task) => attemptsByTask[task.id] || String(task.id) === activeTaskId);
  if (!validTasks.length) return null;
  return (
    <div className="serial-act" data-char="toi">
      <FeTask kicker={kicker}>
        {validTasks.map((task) => (
          <TaskControls
            key={task.id}
            task={task}
            value={answers[task.id] || ''}
            setValue={(value) => setAnswer(task.id, value)}
            onSubmit={() => onSubmit(task)}
            submitting={submittingTask === task.id}
            attempt={attemptsByTask[task.id]}
            submitError={submitError}
          />
        ))}
      </FeTask>
    </div>
  );
}

function SerialFinalAct({
  scene,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  submitError,
  activeTaskId,
}: {
  scene: GraphicNovelScene;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  submitError: TaskSubmitError;
  /* Only the next unanswered action is live; the rest of the read stays clean. */
  activeTaskId: string | null;
}) {
  if (scene.script_payload?.experience_mode === 'reward') return null;
  const task = finalSceneTask(scene);
  if (!task?.id) return null;
  const stop = finalTaskStop(scene, task);
  return (
    <section
      className="fe-embed serial-final-act"
      id={stop.elementId}
      data-mobile-task-stop={stop.id}
      aria-label="Dernière réplique"
    >
      <PanelTask
        kicker="Dernière réplique"
        tasks={[task]}
        answers={answers}
        setAnswer={setAnswer}
        onSubmit={onSubmit}
        submittingTask={submittingTask}
        attemptsByTask={attemptsByTask}
        submitError={submitError}
        activeTaskId={activeTaskId}
      />
    </section>
  );
}

function scrollToFeuilletonSection(id: string) {
  if (typeof document === 'undefined') return;
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function TodayThreadBanner({ context }: { context: FeuilletonThreadContext }) {
  if (!context) return null;
  return (
    <aside className="today-thread-banner" aria-label="Fil du jour">
      <div>
        <span className="t-mono">FIL DU JOUR</span>
        <strong>Scène issue de l’Atelier</strong>
        <p>{context.summary}</p>
      </div>
      <div className="today-thread-chips">
        {context.chips.map((chip) => (
          <span key={chip.key} className={`today-thread-chip ${chip.tone}`}>
            {chip.label}
            <b>{chip.value}</b>
          </span>
        ))}
      </div>
    </aside>
  );
}

function EditionPreparing({
  failure,
  onRetry,
  creating,
}: {
  failure?: Record<string, any> | null;
  onRetry: () => void;
  creating: boolean;
}) {
  // A delayed serial episode is no longer routed here — it keeps its folio in the
  // L'ÉPISODE tab (SerialEpisodeDelayed). This notice now only covers a genuine
  // composition failure of the edition in hand.
  const rawMessage = String(failure?.message || '').trim();
  const message = !rawMessage || /feuilleton generation failed/i.test(rawMessage)
    ? "L’édition n’a pas pu être composée. Votre progression n’a pas été modifiée."
    : rawMessage;
  return (
    <section className="fe-embed edition-preparing">
      <FeNotice
        label="Avis de la rédaction"
        msg={message}
        onRetry={creating ? undefined : onRetry}
        retryLabel="Relancer l’édition"
      />
      <div className="edition-actions">
        {creating && <span className="edition-retrying"><Loader2 className="spin" size={14} /> Relance en cours</span>}
        <Link className="edition-link" href="/grammar">Ouvrir le carnet <ArrowRight size={13} /></Link>
        <Link className="edition-link" href="/atelier">Retour à l’Atelier <ArrowRight size={13} /></Link>
      </div>
    </section>
  );
}

function EditionWriting({ scene }: { scene: GraphicNovelScene }) {
  const printing = scene.status === 'generating';
  return (
    <section className="fe-embed edition-writing" aria-live="polite" aria-label="Edition en préparation">
      <FeMasthead
        index={typeof scene.episode_index === 'number' ? scene.episode_index + 1 : 'du jour'}
        title={printing ? 'Les planches s’impriment' : 'L’édition se compose'}
        dateline={["Aujourd’hui", printing ? 'Impression en cours' : 'Rédaction en cours']}
        progress={printing ? 64 : 24}
        progressRed
      />
      <FeSkeleton press="— la rédaction assemble le récit —" />
      <div className="edition-writing-note">
        <span className="edition-writing-pulse" aria-hidden="true" />
        <div>
          <strong>{printing ? 'Le récit est prêt.' : 'Le récit arrive d’abord.'}</strong>
          <p>{printing
            ? 'Les planches sont en cours d’impression. Cette page se met à jour automatiquement.'
            : 'Les planches seront imprimées ensuite. Cette page se met à jour automatiquement.'}</p>
        </div>
        <Link href="/atelier">Retour à l’Atelier</Link>
      </div>
    </section>
  );
}

function EditionArtProgress({ scene }: { scene: GraphicNovelScene }) {
  const panels = scene.panels || [];
  const ready = panels.filter((panel) => Boolean(panelImageUrl(panel))).length;
  return (
    <div className="fe-embed edition-art-progress" role="status" aria-live="polite">
      <Loader2 className="spin" size={14} />
      <div>
        <strong>L’histoire est prête.</strong>
        <span>Les planches s’impriment en arrière-plan · {ready}/{panels.length}</span>
      </div>
    </div>
  );
}


function PageScene({
  scene,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  submitError,
  activeTaskId,
}: {
  scene: GraphicNovelScene;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  submitError: TaskSubmitError;
  /* Only the next unanswered action is live; the rest of the read stays clean. */
  activeTaskId: string | null;
}) {
  const pageUrl = resolveMediaUrl(scene.script_payload?.page_image?.url);
  return (
    <section className="page-scene">
      <div className="fe-embed">
        <FePanel imageUrl={pageUrl} imageAlt="" status={pageUrl ? undefined : 'generating'} />
      </div>
      <div className="annotation-grid">
        {(scene.panels || []).map((panel) => (
          <PanelAnnotation
            key={panel.id}
            panel={panel}
            answers={answers}
            setAnswer={setAnswer}
            onSubmit={onSubmit}
            submittingTask={submittingTask}
            attemptsByTask={attemptsByTask}
            submitError={submitError}
            activeTaskId={activeTaskId}
          />
        ))}
      </div>
    </section>
  );
}

/* The illustrated-page mode annotates the printed page: the same one numeral,
   dialogue lines and additive caption as the scrolling reader — no second
   presentation system. */
function PanelAnnotation({
  panel,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  submitError,
  activeTaskId,
}: {
  panel: GraphicNovelPanel;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  submitError: TaskSubmitError;
  /* Only the next unanswered action is live; the rest of the read stays clean. */
  activeTaskId: string | null;
}) {
  const tasks = ((panel.overlay_payload?.tasks || []) as OverlayTask[]).map((task) => ({ ...task, panel }));
  const stop = panelTaskStop(panel, tasks);
  const who = serialPanelCharacter(panel);
  const lines = panelDialogueLines(panel);
  const caption = additivePanelCaption(panel, lines);
  const [translated, setTranslated] = useState(false);
  return (
    <article className="fe-embed panel-annotation" id={stop.elementId} data-mobile-task-stop={stop.id} data-char={who}>
      <div className="fe-cap">
        <div className="n">{String(panel.panel_index || 1).padStart(2, '0')}</div>
        <div className="c">{caption || panel.beat}</div>
      </div>
      <PanelAudioButton panel={panel} />
      <FeDialogue
        char={who}
        lines={lines}
        translated={translated}
        onTranslate={() => setTranslated((current) => !current)}
      />
      <PanelTask
        tasks={tasks}
        answers={answers}
        setAnswer={setAnswer}
        onSubmit={onSubmit}
        submittingTask={submittingTask}
        attemptsByTask={attemptsByTask}
        submitError={submitError}
        activeTaskId={activeTaskId}
      />
    </article>
  );
}

function PanelCard({
  panel,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  submitError,
  activeTaskId,
}: {
  panel: GraphicNovelPanel;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  submitError: TaskSubmitError;
  /* Only the next unanswered action is live; the rest of the read stays clean. */
  activeTaskId: string | null;
}) {
  return (
    <SerialPanel
      panel={panel}
      answers={answers}
      setAnswer={setAnswer}
      onSubmit={onSubmit}
      submittingTask={submittingTask}
      attemptsByTask={attemptsByTask}
      submitError={submitError}
      activeTaskId={activeTaskId}
    />
  );
}

function panelAudioUrl(panel: GraphicNovelPanel) {
  const url = panel.audio_payload?.url;
  return typeof url === 'string' && url.trim() ? url : '';
}

function PanelAudioButton({ panel }: { panel: GraphicNovelPanel }) {
  const audioUrl = panelAudioUrl(panel);
  const [playing, setPlaying] = useState(false);
  if (!audioUrl) return null;
  const play = async () => {
    setPlaying(true);
    try {
      const player = new Audio(audioUrl);
      player.onended = () => setPlaying(false);
      player.onerror = () => setPlaying(false);
      await player.play();
    } catch (error) {
      console.error(error);
      setPlaying(false);
      toast.error('Cette planche n’a pas pu être lue.');
    }
  };
  return (
    <button className="panel-audio-button" type="button" onClick={play} disabled={playing} aria-label={`Play panel ${panel.panel_index}`}>
      {playing ? <Pause size={14} /> : <Volume2 size={14} />}
    </button>
  );
}

function EpisodeAudioControls({ scene }: { scene: GraphicNovelScene }) {
  const audioPanels = (scene.panels || []).filter((panel) => panelAudioUrl(panel));
  const [playing, setPlaying] = useState(false);
  const playerRef = useRef<HTMLAudioElement | null>(null);
  useEffect(() => () => {
    playerRef.current?.pause();
    playerRef.current = null;
  }, []);
  if (!audioPanels.length) return null;

  const stop = () => {
    playerRef.current?.pause();
    playerRef.current = null;
    setPlaying(false);
  };

  const playFrom = async (index = 0) => {
    const panel = audioPanels[index];
    const url = panel ? panelAudioUrl(panel) : '';
    if (!url) {
      setPlaying(false);
      return;
    }
    playerRef.current?.pause();
    const player = new Audio(url);
    playerRef.current = player;
    player.onended = () => {
      if (index + 1 < audioPanels.length) {
        void playFrom(index + 1);
      } else {
        setPlaying(false);
        playerRef.current = null;
      }
    };
    player.onerror = () => {
      setPlaying(false);
      playerRef.current = null;
      toast.error('L’audio de l’épisode n’a pas pu être lu.');
    };
    setPlaying(true);
    await player.play();
  };

  const ticks = audioPanels.length > 1
    ? audioPanels.map((_, index) => Math.round((index / audioPanels.length) * 100))
    : [];
  const planches = `${audioPanels.length} planche${audioPanels.length === 1 ? '' : 's'}`;
  return (
    <div className="fe-embed episode-audio" aria-label="Écouter l’épisode">
      <FeAudioBar
        playing={playing}
        title="Écouter l’épisode"
        onToggle={() => (playing ? stop() : void playFrom(0))}
        at={playing ? 6 : 0}
        ticks={ticks}
        time={planches}
        now={playing ? <><b>Lecture</b> — planches narrées</> : undefined}
      />
    </div>
  );
}

function stripInternalSourceLanguage(text: unknown) {
  return String(text || '')
    .replace(/^Safe political news seed for\s+\d{4}-\d{2}-\d{2}:\s*/i, '')
    .replace(/^(résumé|resume|summary|titre|title)\s*[:：]\s*/i, '')
    .replace(/\b(source_policy|safe political|fictionalize|fictionalise)\b[:\s][^.;]*/gi, '')
    .replace(/\s*The scene should fictionalize[^.]*\./gi, '')
    .replace(/\s*avoid depicting real politicians[^.]*\./gi, '')
    .replace(/\s*keep the humour dry rather than cruel\.?/gi, '')
    .replace(/[{}[\]"]/g, '')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

function feuilletonPublicBrief(brief: unknown) {
  const text = stripInternalSourceLanguage(brief).trim();
  if (!text) return '';
  if (/(the gag|le gag|visual premise|headline mechanic|why this source|satire comes from|fictionalise|fictionalize|safe political)/i.test(text)) {
    return '';
  }
  return text;
}

function mentionsParentheses(text: unknown) {
  return /parenth[eè]ses|parentheses/i.test(String(text || ''));
}

function hasParentheticalCue(text: unknown) {
  return /\([^)]+\)/.test(String(text || ''));
}

function displayTaskInstruction(task: Record<string, any>) {
  let instruction = String(task.instruction || '').trim();
  if (mentionsParentheses(instruction) && !hasParentheticalCue(task.prompt)) {
    instruction = 'Complétez la phrase avec la forme correcte.';
  }
  // The old code appended "Utilisez clairement : clear invitation · tu register · …"
  // which mixed French and English internal feature codes into one cluttered line.
  // The French instruction already states the task, so we leave it clean.
  return instruction || 'Complétez la tâche.';
}

// Human label for the task kind, so the card never shows a raw enum like
// "SHORT_SENTENCE". Prefer a real provided label; never the snake_case task_type.
// Canonical short display name: the generator writes "Romane « Romy » Tremblay"
// into speaker fields; the page never prints more than the short name.
function shortSpeakerName(value: unknown): string {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const nickname = raw.match(/[«"“']\s*([^»"”']+?)\s*[»"”']/);
  if (nickname) return nickname[1].trim();
  const cleaned = raw.replace(/\s+/g, ' ');
  const known = [
    ['romane', 'Romy'], ['romy', 'Romy'], ['marin', 'Marin'], ['lila', 'Lila'],
    ['augustin', 'Gus'], ['gus', 'Gus'], ['margaux', 'Margaux'], ['marchand', 'M. Marchand'],
  ];
  const lowered = cleaned.toLowerCase();
  const match = known.find(([needle]) => lowered.includes(needle));
  if (match) return match[1];
  return cleaned.split(' ')[0];
}

// The panel's dialogue, printed exactly once. Blank lines never survive.
function panelDialogueLines(panel: GraphicNovelPanel): FeDialogueLine[] {
  const bubbles = ((panel.overlay_payload?.bubbles || []) as PanelBubble[])
    .filter((bubble) => String(bubble?.fr || '').trim());
  return bubbles.map((bubble) => ({
    who: shortSpeakerName(bubble.speaker) || undefined,
    fr: String(bubble.fr).trim(),
    en: String(bubble.en || '').trim() || undefined,
  }));
}

// A caption prints only when it adds something the dialogue does not.
function additivePanelCaption(panel: GraphicNovelPanel, lines: FeDialogueLine[]) {
  const caption = String(panel.overlay_payload?.caption?.fr || '').trim();
  if (!caption) return lines.length ? '' : String(panel.beat || '').trim();
  const spoken = lines.map((line) => normalizeReaderText(line.fr));
  return spoken.includes(normalizeReaderText(caption)) ? '' : caption;
}

function normalizeReaderText(value: unknown) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

// The task says its prompt once, in sentence case.
function taskPromptLine(task: Record<string, any>) {
  const prompt = String(task.prompt || '').trim();
  return prompt || displayTaskInstruction(task);
}

// One short French response: the story consequence for a branch, the repair for
// a correction, otherwise nothing.
function correctionLine(correction: Record<string, any> | null | undefined) {
  if (!correction) return '';
  if (correctionIsBranch(correction)) return String(correction.why || '').trim();
  if (correctionIsPositive(correction)) return String(correction.why || '').trim();
  return String(correction.corrected_answer || correction.repair || correction.why || '').trim();
}

// If a credit line is needed after the last panel, it is one sentence — no deck
// names, no English labels, no word dump (the words stay linked to the deck).
function feuilletonCreditLine(scene: GraphicNovelScene) {
  const credit = (scene.recap?.vocabulary_credit || {}) as Record<string, any>;
  const total = ['seen_context', 'recognized', 'produced_correct', 'produced_incorrect']
    .reduce((sum, key) => sum + Number(credit[key] || 0), 0);
  if (!total) return '';
  return total === 1
    ? 'Un mot de cette édition rejoint votre révision.'
    : `${total} mots de cette édition rejoignent votre révision.`;
}

// Always-available "translate to English" affordance. Uses a supplied translation
// when present, otherwise fetches one on demand.
function TaskTranslate({ french, supplied }: { french: string; supplied?: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(supplied || '');
  const [loading, setLoading] = useState(false);
  if (!french.trim()) return null;
  const reveal = async () => {
    setOpen(true);
    if (!text) {
      setLoading(true);
      try {
        setText(await apiService.translateToEnglish(french));
      } catch {
        setText('');
      } finally {
        setLoading(false);
      }
    }
  };
  return (
    <div className="task-translate">
      <button type="button" className="task-translate-btn" onClick={() => (open ? setOpen(false) : reveal())}>
        {open ? 'Masquer la traduction' : 'Traduire'}
      </button>
      {open && <p className="task-translate-text">{loading ? 'Traduction…' : text || 'Traduction indisponible.'}</p>}
    </div>
  );
}

function choiceOptionView(option: unknown): ChoiceOptionView | null {
  if (typeof option === 'string') {
    const text = option.trim();
    if (!text) return null;
    const match = text.match(/^([A-Da-d])\s*[:.)-]\s*(.+)$/);
    if (match) {
      return { value: match[1].toUpperCase(), label: match[1].toUpperCase(), text: match[2].trim(), en: '' };
    }
    return { value: text, label: text.length <= 3 ? text : '', text, en: '' };
  }
  if (!option || typeof option !== 'object') return null;
  const record = option as Record<string, any>;
  const value = String(record.value || record.id || record.label || '').trim();
  const label = String(record.label || value).trim();
  const text = String(record.fr || record.text || record.line || label || value).trim();
  if (!value || !text) return null;
  return {
    value,
    label,
    text,
    en: String(record.en || record.translation || '').trim(),
  };
}

function correctionIsPositive(correction: Record<string, any> | null | undefined) {
  // A narrative branch is authorship, never a wrong answer: it reads as accepted.
  return (
    correction?.verdict === 'correct'
    || correction?.verdict === 'accepted'
    || correction?.verdict === 'branch'
  );
}

function correctionIsBranch(correction: Record<string, any> | null | undefined) {
  return correction?.verdict === 'branch' || correction?.grading_mode === 'branch';
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

function serialLocation(scene: GraphicNovelScene) {
  const source = scene.source_snapshot || {};
  const serialContext = scene.script_payload?.serial_context || {};
  const brief = scene.script_payload?.episode_brief || scene.script_payload?.brief_payload || {};
  return firstString(
    source.location_name,
    source.location,
    serialContext.location,
    brief.location,
    brief.setting,
    scene.script_payload?.location,
    'Paris',
  );
}

function serialPreviouslyText(scene: GraphicNovelScene) {
  const serialContext = scene.script_payload?.serial_context || {};
  const hookFromPrevious = serialContext.hook_from_previous || scene.script_payload?.hook_from_previous || {};
  const source = scene.source_snapshot || {};
  return firstString(
    hookFromPrevious.text,
    hookFromPrevious.teaser,
    source.previously,
    source.previous_hook,
  );
}

function serialCharacterKey(value: unknown) {
  const text = String(value || '').toLowerCase();
  if (text.includes('marchand') || text.includes('landlord') || text.includes('propriétaire')) return 'marchand';
  if (text.includes('marin')) return 'marin';
  if (text.includes('lila')) return 'lila';
  if (text.includes('gus') || text.includes('augustin')) return 'gus';
  if (text.includes('margaux')) return 'margaux';
  if (text.includes('romy') || text.includes('romane')) return 'romy';
  if (text.includes('toi') || text.includes('you') || text.includes('user')) return 'toi';
  return '';
}

function panelBubbleCharacter(bubble: PanelBubble) {
  return serialCharacterKey(bubble.speaker_id) || serialCharacterKey(bubble.speaker) || 'toi';
}

function serialPanelCharacter(panel: GraphicNovelPanel) {
  const bubbles = (panel.overlay_payload?.bubbles || []) as PanelBubble[];
  const bubbleCharacter = bubbles.map(panelBubbleCharacter).find(Boolean);
  return bubbleCharacter || serialCharacterKey(`${panel.title} ${panel.beat}`) || 'romy';
}

/* ONE prompt, said once and in sentence case; the optional "because" line stays
   as one small graphite note; one Envoyer; one response. (Was: a kind label, the
   instruction, an uppercase shout of the same prompt, the prompt again, a deck
   chip, a vocabulary badge, an errata counter and a verdict enum.) */
function TaskControls({
  task,
  value,
  setValue,
  onSubmit,
  submitting,
  attempt,
  submitError,
}: {
  task: OverlayTask;
  value: string;
  setValue: (value: string) => void;
  onSubmit: () => void;
  submitting: boolean;
  attempt?: Record<string, any>;
  submitError?: TaskSubmitError;
}) {
  const correction = attempt?.correction;
  const isChoice = task.task_type === 'choice';
  const isClosed = task.task_type === 'cloze' || isChoice;
  const choiceOptions = Array.isArray(task.options)
    ? task.options.map(choiceOptionView).filter(Boolean) as ChoiceOptionView[]
    : [];
  const hasOptions = choiceOptions.length > 0;
  const isCorrect = correctionIsPositive(correction);
  const isBranch = correctionIsBranch(correction);
  const prompt = taskPromptLine(task);
  const promptTranslation = task.prompt_translation || task.translation || task.prompt_en;
  const reason = String(task.recommendation_reason?.text || '').trim();
  const feedback = correctionLine(correction);
  const errored = submitError?.taskId === String(task.id || '');
  const submittedLabel = correction ? (isBranch ? 'Choix fait' : isCorrect ? 'Acceptée' : 'Reprise classée') : 'Envoyée';
  return (
    <div className={`task-box ${!correction ? '' : isBranch ? 'branch' : isCorrect ? 'positive' : 'negative'}`}>
      <p className="task-prompt">{prompt}</p>
      <TaskTranslate french={prompt} supplied={promptTranslation} />
      {reason && <p className="task-reason">{reason}</p>}
      {hasOptions && (
        <div className="option-row">
          {choiceOptions.map((option) => (
            <button
              key={option.value}
              className={value === option.value ? 'selected' : ''}
              onClick={() => setValue(option.value)}
              type="button"
            >
              {option.text}
            </button>
          ))}
        </div>
      )}
      {isChoice && hasOptions ? null : isClosed ? (
        <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="Votre réponse" />
      ) : (
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={task.placeholder || 'Écrivez une phrase courte.'}
        />
      )}
      <button className="btn solid" disabled={submitting || Boolean(attempt)} onClick={onSubmit} type="button">
        {attempt ? submittedLabel : submitting ? 'Relecture…' : 'Envoyer'} <Send size={13} />
      </button>
      {correction && (
        <p className={`inline-feedback ${isBranch ? 'branch' : isCorrect ? 'positive' : 'negative'}`} role="status">
          <strong>{isCorrect ? <Check size={14} /> : <X size={14} />}
            {isBranch ? 'Choix pris en compte' : isCorrect ? 'Acceptée' : 'Reprise classée'}
          </strong>
          {feedback && <span>{feedback}</span>}
        </p>
      )}
      {errored && (
        <p className="inline-feedback negative" role="status">
          <span>{submitError?.message}</span>
        </p>
      )}
    </div>
  );
}

function FeuilletonCliffhangerHero({ scene }: { scene: GraphicNovelScene }) {
  const hook = scene.hook || scene.script_payload?.hook || scene.recap?.hook || {};
  const question = String(hook?.unresolved_question || hook?.teaser || '').trim();
  const beat = String(hook?.text || '').trim();
  if (!question && !beat) return null;
  const who = feuilletonCliffhangerCharacter(scene, hook);
  // The teaser is a sentence, so it is set as one — never in uppercase.
  const demain = beat && question && question !== beat ? beat : undefined;
  return (
    <div className="fe-embed feuilleton-cliffhanger" data-char={who} aria-label="À suivre">
      <FeCliff kicker="À suivre" hook={question || beat} demain={demain} />
    </div>
  );
}

/* The end of the episode is one action, not four cards. (Was: a completion card
   with panel/task counters, a lexical summary with deck names and English
   labels, a two-beat continuation block, and a duplicate complete row.) */
function FeuilletonEnd({
  scene,
  vocabulary,
  completing,
  onComplete,
}: {
  scene: GraphicNovelScene;
  vocabulary: FeuilletonVocabularyItem[];
  completing: boolean;
  onComplete: () => void | Promise<unknown>;
}) {
  const filed = scene.status === 'completed';
  const hook = scene.hook || scene.script_payload?.hook || scene.recap?.hook || {};
  const items = sceneVocabularyRecapItems(scene, vocabulary);
  const vocabularyIds = items.map((item) => Number(item.word_id)).filter((item) => Number.isFinite(item));
  const conceptIds = (scene.selected_concept_ids || []).slice(0, 4);
  const errataIds = (scene.target_errata_ids || []).slice(0, 2);
  const nextBeatIsMission = hook?.next_beat_kind === 'mission';
  const missionPairs: Array<[string, string | number | null | undefined]> = [
    ['mission', scene.mission_id || undefined],
    ['atelier_session_id', scene.atelier_session_id || undefined],
    ['serial_thread_id', scene.serial_thread_id || undefined],
    ['episode_index', typeof scene.episode_index === 'number' ? scene.episode_index + 1 : undefined],
    ...conceptIds.map((id): [string, number] => ['concept_id', id]),
    ...vocabularyIds.slice(0, 4).map((id): [string, number] => ['vocabulary_id', id]),
    ...errataIds.map((id): [string, string] => ['erratum_id', String(id)]),
  ];
  const readerPairs: Array<[string, string | number | null | undefined]> = [
    ['serial_thread_id', scene.serial_thread_id || undefined],
    ['episode_index', typeof scene.episode_index === 'number' ? scene.episode_index + 1 : undefined],
  ];
  const nextBeatLabel = nextBeatIsMission ? 'Agir dans Le Courrier' : 'Lire le prochain épisode';
  const nextBeatHref = nextBeatIsMission
    ? routeWithQuery('/missions', missionPairs)
    : routeWithQuery('/graphic-novel', readerPairs);
  const creditLine = feuilletonCreditLine(scene);
  return (
    <section className="feuilleton-end" aria-label="Fin de l’épisode">
      {filed && (
        <div className="fe-embed">
          <FeFiled label={`Classé · Épisode ${typeof scene.episode_index === 'number' ? scene.episode_index + 1 : ''}`.trim()} />
        </div>
      )}
      {filed && creditLine && <p className="feuilleton-credit-line">{creditLine}</p>}
      {filed ? (
        <Link className="btn solid lg" href={nextBeatHref}>
          {nextBeatLabel} <ArrowRight size={15} />
        </Link>
      ) : (
        <button className="btn solid lg" type="button" disabled={completing} onClick={() => void onComplete()}>
          {completing ? 'Classement…' : 'Terminer l’épisode'} <Check size={15} />
        </button>
      )}
    </section>
  );
}

function feuilletonCliffhangerCharacter(scene: GraphicNovelScene, hook: Record<string, any>) {
  const finalPanel = [...(scene.panels || [])].sort((left, right) => (right.panel_index || 0) - (left.panel_index || 0))[0];
  const bubbles = (finalPanel?.overlay_payload?.bubbles || []) as PanelBubble[];
  const text = [
    hook?.speaker,
    hook?.teaser,
    hook?.text,
    hook?.unresolved_question,
    finalPanel?.title,
    finalPanel?.beat,
    ...bubbles.map((bubble) => bubble.speaker),
  ].filter(Boolean).join(' ').toLowerCase();
  if (text.includes('marchand') || text.includes('propriétaire')) return 'marchand';
  if (text.includes('marin')) return 'marin';
  if (text.includes('lila')) return 'lila';
  if (text.includes('gus') || text.includes('augustin')) return 'gus';
  if (text.includes('margaux')) return 'margaux';
  if (text.includes('romy') || text.includes('romane')) return 'romy';
  return 'romy';
}

function taskStopSafeId(value: string) {
  return String(value).replace(/[^a-zA-Z0-9_-]/g, '-');
}

function mobileTaskStopDomId(stopId: string) {
  return `mobile-story-stop-${taskStopSafeId(stopId)}`;
}

function panelTaskStop(panel: GraphicNovelPanel, tasks: OverlayTask[]): MobileTaskStop {
  const id = `panel-${taskStopSafeId(String(panel.id || panel.panel_index))}`;
  return {
    id,
    elementId: mobileTaskStopDomId(id),
    label: `Planche ${panel.panel_index}`,
    title: panel.title || `Planche ${panel.panel_index}`,
    subtitle: panel.beat || 'Un moment du récit avec sa propre reprise.',
    tasks,
    panel,
  };
}

function finalTaskStop(scene: GraphicNovelScene, task: OverlayTask): MobileTaskStop {
  const id = `scene-final-${taskStopSafeId(String(scene.id || task.id))}`;
  return {
    id,
    elementId: mobileTaskStopDomId(id),
    label: 'Dernière réplique',
    title: 'Terminer la scène',
    subtitle: String(task.prompt_body || task.prompt || 'Écrivez une dernière phrase française qui fait basculer la scène.'),
    tasks: [{ ...task, panel: null }],
    panel: null,
  };
}

function finalSceneTask(scene: GraphicNovelScene): OverlayTask | null {
  const task = scene.script_payload?.final_prompt;
  if (scene.script_payload?.experience_mode === 'reward') return null;
  return task?.id ? { ...task, panel: null } : null;
}

function buildMobileTaskStops(scene: GraphicNovelScene | null): MobileTaskStop[] {
  if (!scene || scene.script_payload?.experience_mode === 'reward') return [];
  const panelStops = (scene.panels || [])
    .map((panel) => {
      const tasks = ((panel.overlay_payload?.tasks || []) as OverlayTask[]).map((task) => ({ ...task, panel }));
      return panelTaskStop(panel, tasks);
    })
    .filter((stop) => stop.tasks.some((task) => task.id));
  const finalTask = finalSceneTask(scene);
  return finalTask ? [...panelStops, finalTaskStop(scene, finalTask)] : panelStops;
}

function findMobileTaskStop(stops: MobileTaskStop[], taskId: string) {
  return stops.find((stop) => stop.tasks.some((task) => String(task.id) === taskId)) || null;
}

function extractTasks(scene: GraphicNovelScene | null): OverlayTask[] {
  if (!scene) return [];
  if (scene.script_payload?.experience_mode === 'reward') return [];
  const panelTasks = (scene.panels || []).flatMap((panel) => ((panel.overlay_payload?.tasks || []) as OverlayTask[]).map((task) => ({ ...task, panel })));
  const finalPrompt = finalSceneTask(scene);
  return finalPrompt ? [...panelTasks, finalPrompt] : panelTasks;
}

function sceneTargetVocabulary(scene: GraphicNovelScene | null): FeuilletonVocabularyItem[] {
  if (!scene) return [];
  const script = scene.script_payload || {};
  const rawItems = [
    ...(Array.isArray(scene.target_vocabulary) ? scene.target_vocabulary : []),
    ...(Array.isArray(script.target_vocabulary) ? script.target_vocabulary : []),
    ...extractTasks(scene).map(vocabularyItemFromTask).filter(Boolean),
  ] as FeuilletonVocabularyItem[];
  return mergeVocabularyItems(rawItems);
}

function sceneVocabularyRecapItems(scene: GraphicNovelScene, vocabulary: FeuilletonVocabularyItem[]) {
  const taskItems = extractTasks(scene).map(vocabularyItemFromTask).filter(Boolean) as FeuilletonVocabularyItem[];
  return mergeVocabularyItems([...vocabulary, ...taskItems]);
}

function vocabularyItemFromTask(task: Record<string, any>): FeuilletonVocabularyItem | null {
  if (!task) return null;
  const nested = Array.isArray(task.target_vocabulary)
    ? task.target_vocabulary.map(vocabularyItemFromRecord).filter(Boolean)
    : [];
  if (nested.length) return nested[0] as FeuilletonVocabularyItem;
  if (!task.vocabulary_task && !task.target_word_id && !task.target_word) return null;
  return vocabularyItemFromRecord({
    word_id: task.target_word_id || task.word_id,
    word: task.target_word || task.word || task.expected_answer,
    translation: task.target_translation || task.target_word_translation || task.translation,
    bucket: task.target_bucket || task.bucket || 'target',
    scheduler: task.target_scheduler || task.scheduler || 'explicit',
    example_sentence: task.example_sentence || task.hints?.example_sentence,
    example_translation: task.example_translation || task.hints?.example_translation,
  });
}

function vocabularyItemFromRecord(record: Record<string, any> | null | undefined): FeuilletonVocabularyItem | null {
  if (!record || typeof record !== 'object') return null;
  const translations = record.translations && typeof record.translations === 'object' ? record.translations : {};
  const wordId = Number(record.word_id || record.target_word_id || record.id || 0);
  const word = String(record.word || record.target_word || record.term || '').trim();
  const translation = String(
    record.translation
    || record.target_translation
    || record.target_word_translation
    || glossFromMap(translations)
    || '',
  ).trim();
  if (!word) return null;
  return {
    ...record,
    word_id: Number.isFinite(wordId) ? wordId : 0,
    word,
    translation,
  };
}

function mergeVocabularyItems(items: Array<FeuilletonVocabularyItem | null | undefined>) {
  const map = new Map<string, FeuilletonVocabularyItem>();
  items.forEach((item) => {
    if (!item?.word) return;
    const key = item.word_id ? `id:${item.word_id}` : `word:${normalizeVocabularyLookupText(item.word)}`;
    const existing = map.get(key);
    map.set(key, {
      ...item,
      ...existing,
      word: existing?.word || item.word,
      translation: existing?.translation || item.translation,
      bucket: existing?.bucket || item.bucket,
      scheduler: existing?.scheduler || item.scheduler,
      example_sentence: existing?.example_sentence || item.example_sentence,
      example_translation: existing?.example_translation || item.example_translation,
    });
  });
  return Array.from(map.values());
}

function normalizeVocabularyLookupText(value: unknown) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’]/g, "'")
    .toLowerCase()
    .replace(/[^a-z0-9' -]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function routeWithQuery(path: string, pairs: Array<[string, string | number | null | undefined]>) {
  const params = new URLSearchParams();
  pairs.forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    const text = String(value).trim();
    if (!text) return;
    params.append(key, text);
  });
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function feuilletonEditionDate(scene: GraphicNovelScene) {
  const source = scene.source_snapshot || {};
  const item = (source.items || [])[0] || {};
  return formatFeuilletonDate(source.date || item.published_at || source.fetched_at || scene.created_at);
}

function formatFeuilletonDate(value: unknown) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
  const date = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date(raw);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

type RouterQueryLike = Record<string, string | string[] | undefined>;

function queryFromAsPath(asPath?: string): RouterQueryLike {
  const queryString = asPath?.split('?')[1]?.split('#')[0];
  if (!queryString) return {};
  const params = new URLSearchParams(queryString);
  const parsed: RouterQueryLike = {};
  params.forEach((value, key) => {
    const existing = parsed[key];
    if (!existing) {
      parsed[key] = value;
    } else if (Array.isArray(existing)) {
      parsed[key] = [...existing, value];
    } else {
      parsed[key] = [existing, value];
    }
  });
  return parsed;
}

function mergedRouteQuery(query: RouterQueryLike, asPath?: string): RouterQueryLike {
  const parsed = queryFromAsPath(asPath);
  return {
    ...parsed,
    ...query,
  };
}

function queryList(value: string | string[] | undefined): string[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function feuilletonThreadContextFromQuery(query: RouterQueryLike): FeuilletonThreadContext {
  const grammarCount = queryList(query.concept_id).length;
  const errataCount = queryList(query.erratum_id).length;
  const vocabularyCount = queryList(query.vocabulary_id).length;
  const missionId = typeof query.mission === 'string'
    ? query.mission
    : typeof query.mission_id === 'string'
      ? query.mission_id
      : '';
  const atelierSessionId = typeof query.atelier_session_id === 'string' ? query.atelier_session_id : '';
  const serialThreadId = typeof query.serial_thread_id === 'string' ? query.serial_thread_id : '';
  const chips: NonNullable<FeuilletonThreadContext>['chips'] = [];

  if (grammarCount) chips.push({ key: 'grammar', label: 'Grammaire', value: formatContextCount(grammarCount, 'point'), tone: 'blue' });
  if (vocabularyCount) chips.push({ key: 'vocabulary', label: 'Lexique', value: formatContextCount(vocabularyCount, 'mot'), tone: 'yellow' });
  if (errataCount) chips.push({ key: 'errata', label: 'Errata', value: formatContextCount(errataCount, 'repair'), tone: 'red' });
  if (missionId) chips.push({ key: 'mission', label: 'Mission', value: shortContextId(missionId), tone: 'blue' });
  if (serialThreadId) chips.push({ key: 'serial', label: 'Fil du récit', value: shortContextId(serialThreadId), tone: 'yellow' });
  if (atelierSessionId) chips.push({ key: 'atelier-session', label: 'Séance Atelier', value: shortContextId(atelierSessionId), tone: 'red' });
  if (!chips.length) return null;

  const sources = [
    atelierSessionId ? 'la séance Atelier' : '',
    serialThreadId ? 'le fil du récit' : '',
    missionId ? 'mission' : '',
    grammarCount ? `${grammarCount} point${grammarCount === 1 ? '' : 's'} de grammaire` : '',
    vocabularyCount ? `${vocabularyCount} mot${vocabularyCount === 1 ? '' : 's'} de lexique` : '',
    errataCount ? `${errataCount} ${errataCount === 1 ? 'erratum' : 'errata'}` : '',
  ].filter(Boolean);

  return {
    summary: `Cette édition est issue de ${joinContextSources(sources)} dans le fil d’apprentissage du jour.`,
    chips,
  };
}

function formatContextCount(count: number, singular: string) {
  return `${count} ${singular}${count === 1 ? '' : 's'}`;
}

function shortContextId(value: string) {
  const clean = value.trim();
  if (!clean) return '';
  if (clean.length <= 12) return clean;
  return clean.slice(0, 8);
}

function joinContextSources(items: string[]) {
  if (items.length <= 1) return items[0] || 'Atelier';
  if (items.length === 2) return `${items[0]} et ${items[1]}`;
  return `${items.slice(0, -1).join(', ')} et ${items[items.length - 1]}`;
}

function graphicNovelContextKey(query: RouterQueryLike) {
  const keys = ['atelier_session_id', 'mission', 'mission_id', 'concept_id', 'erratum_id', 'vocabulary_id'];
  const serialKeys = ['serial_thread_id', 'episode_index'];
  const parts = [...keys, ...serialKeys].flatMap((key) => queryList(query[key]).map((value) => `${key}:${value}`));
  return parts.length ? parts.join('|') : '';
}

function feuilletonGenerationIsStalled(scene: GraphicNovelScene) {
  if (!scene.started_at) return false;
  const startedAt = new Date(scene.started_at).getTime();
  return Number.isFinite(startedAt) && Date.now() - startedAt > 6 * 60 * 1000;
}

function FeuilletonStyles() {
  return (
    <style jsx global>{`
      .feuilleton-page {
        /* Consume the theme-aware global tokens so the reader honours light/dark
           (globals.css). The reader previously hardcoded a light palette AND
           re-aliased the --app-* tokens to it, forcing light everywhere — that is
           removed. Local names are kept as thin aliases so the rest of this large
           stylesheet's var(--paper)/var(--ink)/... references resolve through the
           theme tokens with no layout change. */
        --paper: var(--app-paper);
        --paper-2: var(--app-paper-2);
        --paper-3: var(--app-paper-3);
        --sheet: var(--app-sheet);
        --ink: var(--app-ink);
        --ink-2: var(--app-ink-2);
        --ink-3: var(--app-ink-3);
        --red: var(--app-red);
        --blue: var(--app-blue);
        --yellow: var(--app-yellow);
        --green: var(--app-green);
        --serif: var(--app-serif);
        --grotesk: "Inter", "Helvetica Neue", Arial, sans-serif;

        min-height: 100vh;
        background: var(--paper);
        color: var(--ink);
        font-family: var(--grotesk);
        overflow-x: hidden;
      }
      .feuilleton-page * { box-sizing: border-box; }
      .feuilleton-page img { max-width: 100%; }
      .feuilleton-page button, .feuilleton-page input, .feuilleton-page textarea { font: inherit; color: inherit; }
      .feuilleton-page button { border: 0; background: transparent; cursor: pointer; }
      .fn-spread { box-sizing: border-box; width: min(1320px, 100%); margin: 0 auto; padding: 0 clamp(22px, 4vw, 48px); }
      /* .btn is left out of this marginalia group: actions carry the soft
         journal treatment (pill, sentence case) set on .btn below. */
      .t-mono { font-size: 10px; letter-spacing: .13em; text-transform: uppercase; font-weight: 900; text-decoration: none; }
      .red { color: var(--red); }
      .fn-grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 28px; padding-top: 34px; padding-bottom: 80px; align-items: start; }
      .fn-main { min-width: 0; display: grid; gap: 24px; }
      .feuilleton-page.has-scene .fn-grid {
        width: min(920px, 100%);
        grid-template-columns: minmax(0, 1fr);
      }
      .feuilleton-reader-tools {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 8px;
        margin-top: -12px;
      }
      .feuilleton-reader-tools a, .feuilleton-reader-tools button {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        min-height: 34px;
        border: 1px solid var(--ink);
        padding: 7px 10px;
        color: var(--ink);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .1em;
        text-decoration: none;
        text-transform: uppercase;
      }
      .feuilleton-reader-tools .new-edition { background: var(--red); color: var(--app-sheet); }
      .feuilleton-reader-tools button:disabled { cursor: wait; opacity: .6; }
      .feuilleton-mobile-edition-tools { display: none; }
      .standalone-reader-mast {
        border: 1.5px solid var(--ink);
        background: var(--sheet);
      }
      .standalone-reader-mast > p {
        max-width: 680px;
        margin: 0 auto;
        padding: 14px 22px 18px;
        font-family: var(--serif);
        font-size: 17px;
        font-style: italic;
        line-height: 1.45;
        text-align: center;
        color: var(--ink-2);
      }
      .edition-writing {
        max-width: 720px;
        margin: 0 auto;
        border: 1.5px solid var(--ink);
        background: var(--sheet);
      }
      .edition-writing .fe-skel { margin: 18px; }
      .edition-writing-note {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        align-items: center;
        gap: 12px;
        margin: 0 18px 18px;
        padding: 12px 14px;
        border-top: 1px solid var(--ink);
        border-bottom: 1px solid var(--ink);
      }
      .edition-writing-pulse {
        width: 10px;
        height: 24px;
        background: var(--red);
        animation: feuilleton-press-pulse 1.1s ease-in-out infinite alternate;
      }
      @keyframes feuilleton-press-pulse { from { transform: scaleY(.4); opacity: .45; } to { transform: scaleY(1); opacity: 1; } }
      .edition-writing-note strong { display: block; font-family: var(--serif); font-size: 16px; font-style: italic; }
      .edition-writing-note p { margin: 3px 0 0; color: var(--ink-2); font-size: 12px; line-height: 1.4; }
      .edition-writing-note a { color: var(--ink); font-size: 9px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
      .edition-art-progress {
        max-width: 720px;
        margin: 0 auto 14px;
        padding: 11px 14px;
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        align-items: center;
        gap: 11px;
        border: 1px solid var(--ink);
        border-left: 5px solid var(--red);
        background: var(--sheet);
      }
      .edition-art-progress strong {
        display: block;
        font-family: var(--serif);
        font-size: 15px;
        font-style: italic;
      }
      .edition-art-progress span {
        display: block;
        margin-top: 2px;
        color: var(--ink-2);
        font-size: 9px;
        font-weight: 800;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .fe-story-panel {
        min-width: 0;
        border-bottom: 1px solid var(--paper-3);
        padding-bottom: 12px;
      }
      .fe-story-panel .fe-panel { margin: 18px 0 10px; }
      .serial-act .fe-task { margin: 10px 0 18px; }
      .edition-preparing { max-width: 700px; margin: 0 auto; }
      .edition-preparing .edition-actions { margin-top: 14px; }
      .edition-retrying { display: inline-flex; align-items: center; gap: 8px; font-size: 10px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
      /* supplement masthead embed — the shared FeMasthead / FePreviously / FeRelChip
         dropped into the reader via .fe-embed (see components/feuilleton). */
      .serial-reader-mast .serial-mast-rel { display: flex; justify-content: center; padding: 12px 18px 0; }
      .serial-reader-mast .serial-rel-chip { text-decoration: none; color: inherit; }
      .fn-title { display: flex; align-items: end; justify-content: space-between; gap: 24px; border-bottom: 4px solid var(--ink); padding-bottom: 20px; }
      .fn-title h1 {
        margin: 8px 0 0;
        font-family: var(--serif);
        font-size: clamp(30px, 4.2vw, 46px);
        line-height: 1;
        letter-spacing: 0;
        font-style: italic;
        font-weight: 700;
      }
      .create-console { display: grid; gap: 9px; justify-items: end; min-width: min(480px, 100%); }
      .atelier-return { color: var(--ink); text-decoration: none; }
      .paper { background: var(--paper-2); border: 2px solid var(--ink); position: relative; }
      .loading, .empty-state { min-height: 240px; display: grid; place-items: center; gap: 14px; font-size: 10px; letter-spacing: .14em; font-weight: 900; text-transform: uppercase; }
      .feuilleton-empty-state {
        place-items: initial;
        align-content: center;
        justify-items: stretch;
        padding: 28px 32px;
        background: var(--paper);
        letter-spacing: 0;
        text-align: left;
        text-transform: none;
      }
      .empty-state-copy {
        display: grid;
        gap: 8px;
        max-width: 640px;
      }
      .empty-state-copy h2 {
        margin: 0;
        font-family: var(--serif);
        font-size: clamp(30px, 4vw, 42px);
        font-style: italic;
        font-weight: 700;
        letter-spacing: 0;
        line-height: 1;
      }
      .empty-state-copy p {
        margin: 0;
        color: var(--ink-2);
        font-size: 16px;
        font-weight: 700;
        line-height: 1.45;
      }
      .feuilleton-empty-status {
        min-height: 50px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        border: 1px solid var(--ink);
        background: var(--paper-2);
        color: var(--ink-2);
        padding: 0 16px;
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .canonical-beat-handoff {
        display: grid;
        grid-template-columns: 142px minmax(0, 1fr);
        min-height: 330px;
        border: 1.5px solid var(--ink);
        background: var(--sheet);
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 18%, transparent);
      }
      .canonical-beat-number {
        display: grid;
        grid-template-rows: auto 1fr auto;
        align-items: center;
        justify-items: center;
        gap: 12px;
        border-right: 1px solid var(--ink);
        background: var(--ink);
        color: var(--paper);
        padding: 22px 12px;
      }
      .canonical-beat-number span, .canonical-beat-number em {
        font-size: 9px;
        font-style: normal;
        font-weight: 900;
        letter-spacing: .14em;
        text-transform: uppercase;
      }
      .canonical-beat-number strong {
        font-family: var(--serif);
        font-size: 68px;
        font-style: italic;
        font-weight: 600;
        line-height: 1;
      }
      .canonical-beat-copy {
        align-content: center;
        display: grid;
        gap: 14px;
        padding: 34px 40px;
      }
      .canonical-beat-copy h2 {
        max-width: 560px;
        margin: 0;
        font-family: var(--serif);
        font-size: 42px;
        font-style: italic;
        font-weight: 650;
        line-height: .98;
      }
      .canonical-beat-copy p {
        max-width: 610px;
        margin: 0;
        color: var(--ink-2);
        font-size: 16px;
        line-height: 1.5;
      }
      .canonical-cast {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
      }
      .canonical-cast span {
        border: 1px solid var(--ink);
        padding: 5px 8px;
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
      }
      /* Primary action, soft: pill geometry, solid ink on paper, sentence case. */
      .canonical-beat-cta {
        display: inline-flex;
        width: fit-content;
        min-height: 54px;
        align-items: center;
        justify-content: center;
        gap: 16px;
        border-radius: 999px;
        border: 1px solid var(--ink);
        background: var(--ink);
        color: var(--paper);
        padding: 0 22px;
        font-size: var(--t-body);
        font-weight: 600;
        letter-spacing: .01em;
        text-transform: none;
        text-decoration: none;
        transition: background .16s ease, color .16s ease;
      }
      .canonical-beat-cta:active:not(:disabled) { background: var(--paper-2); color: var(--ink); }
      /* Same specificity fix as .btn — .feuilleton-page button sets font: inherit. */
      .feuilleton-page .canonical-beat-cta {
        color: var(--paper);
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em; text-transform: none;
      }
      .canonical-beat-copy small {
        max-width: 560px;
        color: var(--ink-3);
        font-size: 11px;
        font-weight: 750;
        line-height: 1.4;
      }
      /* L'ÉPISODE — the serial beat, primary. Shares the canonical handoff
         furniture so the two serial faces read as one section. */
      .serial-episode-lead .canonical-beat-cta:disabled {
        opacity: .5;
        cursor: not-allowed;
      }
      .serial-episode-notice {
        display: grid;
        gap: 16px;
        padding: 26px 0 0;
      }
      .serial-episode-notice .fe-notice { margin: 0; }
      .serial-episode-notice .edition-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 18px;
        min-width: 0;
      }
      .serial-episode-filed {
        display: grid;
        justify-items: start;
        gap: 12px;
        border: 1.5px solid var(--ink);
        background: var(--sheet);
        padding: 26px 28px 24px;
      }
      .serial-episode-filed h2 {
        margin: 0;
        font-family: var(--serif);
        font-size: clamp(26px, 3.2vw, 36px);
        font-style: italic;
        font-weight: 700;
        line-height: 1.02;
      }
      .serial-episode-filed p {
        margin: 0;
        max-width: 560px;
        color: var(--ink-2);
        font-size: 16px;
        line-height: 1.45;
      }
      .serial-episode-filed .fe-cont {
        width: 100%;
        margin-inline: 0;
      }
      /* The optional supplément, demoted to a margin note under the episode. */
      .supplement-aside {
        display: grid;
        justify-items: start;
        gap: 6px;
        margin-top: 20px;
        border-top: 1px solid var(--paper-3);
        padding-top: 14px;
      }
      .supplement-aside .t-mono { color: var(--ink-3); }
      .supplement-link {
        display: inline-flex;
        align-items: center;
        gap: 9px;
        min-height: 32px;
        border-bottom: 1px solid var(--ink-3);
        color: var(--ink-2);
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
      }
      .supplement-link:hover:not(:disabled) { border-color: var(--ink); color: var(--ink); }
      .supplement-link:disabled { opacity: .55; cursor: not-allowed; }
      .supplement-aside p {
        margin: 0;
        max-width: 520px;
        color: var(--ink-3);
        font-size: 13px;
        font-weight: 650;
        line-height: 1.4;
      }
      .generation-progress {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 18px 22px;
        border-left: 7px solid var(--blue);
        background: var(--paper);
      }
      .generation-progress strong {
        display: block;
        font-size: 12px;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .generation-progress p {
        margin: 4px 0 0;
        color: var(--ink-2);
        line-height: 1.35;
      }
      .edition-preparing {
        padding: 34px;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 28px;
        align-items: end;
        background: var(--paper);
      }
      .edition-preparing h2 {
        margin: 8px 0 10px;
        font-family: var(--serif);
        font-size: clamp(28px, 3.8vw, 42px);
        line-height: 1;
        letter-spacing: 0;
        font-style: italic;
        font-weight: 700;
      }
      .edition-preparing p {
        margin: 0;
        max-width: 620px;
        color: var(--ink-2);
        font-size: 17px;
        line-height: 1.45;
      }
      .edition-actions {
        display: grid;
        gap: 10px;
        min-width: 240px;
      }
      .edition-link {
        display: inline-flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        min-height: 34px;
        border-bottom: 1px solid var(--ink-3);
        color: var(--ink-2);
        padding: 4px 0;
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .1em;
        text-decoration: none;
        text-transform: uppercase;
      }
      .edition-link:hover { border-color: var(--ink); color: var(--ink); }
      /* Soft journal action: pill geometry, sentence case, ink/outline pair. */
      .btn {
        display: inline-flex; align-items: center; justify-content: center; gap: 9px;
        min-height: 54px; padding: 0 22px; border-radius: 999px;
        border: 1px solid var(--ink); background: transparent; color: var(--ink);
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em;
        text-transform: none; text-decoration: none;
        transition: background .16s ease, color .16s ease;
      }
      /* .feuilleton-page button (font: inherit) is 0, 1, 1 and outranks .btn
         at 0, 1, 0, so the action type has to be restated one level up or the
         pills inherit whatever kicker type surrounds them. */
      .feuilleton-page .btn {
        color: var(--ink);
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em; text-transform: none;
      }
      .btn:active:not(:disabled) { background: var(--paper-2); color: var(--ink); }
      .btn:disabled { opacity: .5; cursor: not-allowed; }
      .btn.red, .btn.solid { background: var(--ink); border-color: var(--ink); color: var(--paper); }
      .btn.red:active:not(:disabled), .btn.solid:active:not(:disabled) { background: var(--paper-2); color: var(--ink); }
      .btn.lg { min-height: 56px; padding-inline: 28px; }
      .kicker { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
      .kicker span { border: 1px solid var(--ink); padding: 5px 8px; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; }
      .today-thread-banner {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 16px;
        align-items: center;
        max-width: 780px;
        margin-top: 16px;
        border: 1px solid var(--ink);
        border-left: 7px solid var(--red);
        background: var(--sheet);
        padding: 14px 16px;
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--yellow) 42%, transparent);
      }
      .today-thread-banner strong {
        display: block;
        margin-top: 5px;
        font-family: var(--serif);
        font-size: 25px;
        font-style: italic;
        line-height: 1;
      }
      .today-thread-banner p {
        margin: 6px 0 0;
        color: var(--ink-2);
        font-size: 14px;
        line-height: 1.35;
      }
      .today-thread-chips {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 7px;
        max-width: 360px;
      }
      .today-thread-chip {
        display: inline-flex;
        align-items: baseline;
        gap: 7px;
        border: 1px solid var(--ink);
        background: var(--paper);
        padding: 5px 8px;
        font-size: 9px;
        letter-spacing: .1em;
        text-transform: uppercase;
        font-weight: 900;
      }
      .today-thread-chip b {
        font-size: 12px;
        letter-spacing: 0;
        text-transform: none;
      }
      .today-thread-chip.red { box-shadow: inset 4px 0 0 var(--red); }
      .today-thread-chip.blue { box-shadow: inset 4px 0 0 var(--blue); }
      .today-thread-chip.yellow { box-shadow: inset 4px 0 0 var(--yellow); }
      .mobile-reading-bar, .mobile-generation-steps, .mobile-generation-note, .mobile-loading-copy, .mobile-loading-stack, .mobile-empty-task-note {
        display: none;
      }
      .feuilleton-page.is-serial .fn-grid {
        width: min(760px, 100%);
        grid-template-columns: minmax(0, 1fr);
        gap: 0;
        padding-top: 22px;
      }
      .feuilleton-page.is-serial .fn-main {
        gap: 18px;
      }
      .serial-reader {
        border: 1.5px solid var(--ink);
        background: var(--paper);
        overflow: hidden;
      }
      .serial-reader-toggle {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 16px 18px 2px;
        border: 1px solid var(--ink);
        background: var(--paper);
      }
      .serial-reader-toggle button {
        min-height: 40px;
        border-right: 1px solid var(--ink);
        color: var(--ink);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .serial-reader-toggle button:last-child {
        border-right: 0;
      }
      .serial-reader-toggle button.active {
        background: var(--ink);
        color: var(--paper);
      }
      .serial-panel-stack {
        display: grid;
        gap: 0;
        padding: 0 18px 10px;
      }
      .serial-act .task-box, .serial-final-act .task-box {
        border-left-color: var(--char-toi);
        background: var(--paper);
      }
      .serial-final-act {
        margin: 0;
      }
      .serial-reader .page-scene {
        padding: 18px;
      }
      .feuilleton-cliffhanger {
        margin: 0;
        border: 0;
      }
      .page-scene { display: grid; gap: 20px; }
      .annotation-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
      .panel-annotation {
        padding: 18px;
        display: grid;
        gap: 12px;
        background: var(--paper);
        border: 2px solid var(--ink);
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 18%, transparent);
        transition: transform 0.25s cubic-bezier(0.165, 0.84, 0.44, 1), box-shadow 0.25s cubic-bezier(0.165, 0.84, 0.44, 1);
      }
      .panel-annotation:hover {
        transform: translateY(-4px) scale(1.01);
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 18%, transparent);
      }
      .panel-annotation > p { margin: 0; color: var(--ink-2); line-height: 1.4; }
      /* One column: the standalone edition reads with the same rhythm as the serial stack. */
      .panel-grid { display: grid; gap: 8px; width: min(760px, 100%); margin: 0 auto; }
      .panel-audio-button {
        display: inline-grid;
        place-items: center;
        flex: 0 0 auto;
        width: 30px;
        height: 30px;
        border: 1.5px solid var(--ink);
        background: var(--paper);
        color: var(--blue);
        box-shadow: inset 0 -1px 0 color-mix(in srgb, var(--ink) 18%, transparent);
      }
      .panel-audio-button:disabled {
        color: var(--ink-3);
        box-shadow: none;
      }
      .episode-audio {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        padding: 16px 18px;
        background: var(--paper);
      }
      .episode-audio div {
        display: grid;
        gap: 4px;
      }
      .episode-audio strong {
        font-family: var(--serif);
        font-size: 24px;
        font-style: italic;
        line-height: 1;
      }
      .episode-audio button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 9px;
        border: 2px solid var(--ink);
        background: var(--ink);
        color: var(--paper);
        min-height: 42px;
        padding: 0 14px;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
        white-space: nowrap;
      }
      .task-box { display: grid; gap: 12px; border-left: 4px solid var(--blue); background: var(--paper-2); padding: 14px; }
      .task-reason {
        margin: -4px 0 0;
        color: var(--ink-3);
        font-family: var(--serif);
        font-size: 12px;
        font-style: italic;
        line-height: 1.4;
      }
      .task-prompt { margin: 0; font-family: var(--serif); font-size: 21px; font-style: italic; }
      .task-translate { display: grid; gap: 6px; }
      .task-translate-btn {
        justify-self: start;
        padding: 0;
        border: 0;
        background: transparent;
        cursor: pointer;
        color: var(--blue);
        font-size: 10px;
        font-family: var(--mono);
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .task-translate-text { margin: 0; color: var(--ink-2); font-family: var(--sans); font-size: 14px; font-style: normal; line-height: 1.4; }
      .option-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
      .option-row button {
        min-height: 56px; border: 1px solid var(--ink); background: var(--paper); padding: 10px 12px;
        text-align: left; font-family: var(--serif); font-size: 18px; font-style: italic; line-height: 1.16;
      }
      .option-row button.selected { background: var(--ink); color: var(--paper); }
      .task-box input, .task-box textarea { width: 100%; border: 1px solid var(--ink); background: var(--paper); padding: 11px 12px; outline: none; box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 18%, transparent); font-family: var(--serif); font-size: 20px; font-style: italic; }
      .task-box textarea { min-height: 100px; resize: vertical; }
      .inline-feedback {
        margin: 0; display: grid; gap: 4px; border-left: 3px solid var(--blue);
        background: var(--sheet); padding: 9px 12px; line-height: 1.4;
      }
      .inline-feedback strong { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; letter-spacing: .04em; }
      .inline-feedback span { color: var(--ink-2); font-size: 14px; }
      .inline-feedback.positive, .inline-feedback.branch { border-left-color: var(--green); }
      .inline-feedback.negative { border-left-color: var(--red); }

      /* THE END OF THE EPISODE — one action, and at most one credit sentence. */
      .feuilleton-end { display: grid; justify-items: center; gap: 12px; padding: 20px 18px 24px; }
      .feuilleton-credit-line {
        margin: 0; max-width: 34ch; text-align: center;
        color: var(--ink-3); font-family: var(--serif); font-style: italic; font-size: 15px; line-height: 1.4;
      }
      .spin { animation: spin 1s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @media (max-width: 980px) {
        .fn-grid, .panel-grid, .annotation-grid { grid-template-columns: 1fr; }
        .fn-title { align-items: flex-start; flex-direction: column; }
        .create-console { width: 100%; justify-items: stretch; }
      }
      @media (max-width: 900px) {
        .feuilleton-reader-tools { display: none; }
        .feuilleton-page {
          padding-bottom: calc(var(--phone-bottom-nav-space) + 18px);
        }
        .feuilleton-page .fe-embed > .fe-secnav {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 0;
          border-bottom: 1px solid var(--ink);
          background: transparent;
          padding: 0;
        }
        .feuilleton-page .fe-embed > .fe-secnav a {
          min-width: 0;
          padding: 10px 4px 8px;
          overflow: hidden;
          text-align: center;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 8.5px;
          letter-spacing: .08em;
        }
        .feuilleton-page .feuilleton-mobile-edition-tools {
          display: grid;
          grid-template-columns: .65fr 1fr 1.35fr;
          border: 1px solid var(--ink);
          background: var(--sheet);
        }
        .feuilleton-page .feuilleton-mobile-edition-tools a, .feuilleton-page .feuilleton-mobile-edition-tools button {
          display: inline-flex;
          min-width: 0;
          min-height: 36px;
          align-items: center;
          justify-content: center;
          gap: 5px;
          border-right: 1px solid var(--ink);
          padding: 6px;
          overflow: hidden;
          color: var(--ink);
          font-size: 8.5px;
          font-weight: 900;
          letter-spacing: .07em;
          line-height: 1.1;
          text-align: center;
          text-decoration: none;
          text-overflow: ellipsis;
          text-transform: uppercase;
          white-space: nowrap;
        }
        .feuilleton-page .feuilleton-mobile-edition-tools .new-edition {
          border-right: 0;
          background: var(--red);
          color: var(--app-sheet);
        }
        .feuilleton-page .feuilleton-mobile-edition-tools button:disabled {
          cursor: wait;
          opacity: .6;
        }
        .fn-spread {
          padding-inline: var(--phone-gutter);
          max-width: var(--app-viewport-width);
          overflow-x: hidden;
        }
        .fn-grid {
          gap: 18px;
          padding-top: 16px;
          padding-bottom: var(--phone-bottom-nav-space);
          width: 100%;
          max-width: 100%;
          overflow-x: hidden;
        }
        .fn-main {
          gap: 16px;
          width: 100%;
          max-width: 100%;
          overflow-x: hidden;
        }
        .fn-title {
          display: grid;
          gap: 14px;
          padding-bottom: 16px;
          border-bottom-width: 1px;
        }
        .feuilleton-page.has-scene .fn-title {
          display: none;
        }
        .fn-title h1 {
          font-size: 38px;
          line-height: .94;
        }
        .create-console {
          gap: 0;
          min-width: 0;
          justify-items: stretch;
        }
        .feuilleton-page .btn {
          width: 100%;
          min-width: 0;
          min-height: 56px;
          padding-inline: 12px;
          white-space: normal;
          text-align: center;
        }
        .feuilleton-page .generation-progress {
          align-items: flex-start;
          padding: 14px;
        }
        .feuilleton-page .generation-progress > svg {
          flex: 0 0 auto;
          margin-top: 2px;
        }
        .feuilleton-page .generation-progress strong {
          font-size: 11px;
          line-height: 1.25;
        }
        .feuilleton-page .mobile-generation-steps {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 6px;
          margin-top: 12px;
        }
        .feuilleton-page .mobile-generation-steps span {
          min-width: 0;
          border: 1px solid var(--ink);
          background: var(--paper-2);
          padding: 7px 6px;
          text-align: center;
          font-size: 9px;
          letter-spacing: .08em;
          text-transform: uppercase;
          font-weight: 900;
        }
        .feuilleton-page .mobile-generation-steps span.active {
          background: var(--ink);
          color: var(--paper);
        }
        .feuilleton-page .mobile-generation-note {
          display: block;
          margin-top: 10px;
          color: var(--blue);
          font-size: 12px;
          font-weight: 800;
          line-height: 1.35;
        }
        .feuilleton-page .feuilleton-loading {
          align-content: center;
          justify-items: stretch;
          min-height: 270px;
          padding: 18px;
          border-width: 1px;
          background: var(--sheet);
          text-align: left;
        }
        .feuilleton-page .feuilleton-loading > .spin {
          justify-self: center;
        }
        .feuilleton-page .loading-label {
          justify-self: center;
        }
        .feuilleton-page .mobile-loading-copy {
          display: block;
          max-width: 320px;
          margin: 0 auto;
          color: var(--ink-2);
          font-size: 13px;
          font-weight: 700;
          letter-spacing: 0;
          line-height: 1.35;
          text-align: center;
          text-transform: none;
        }
        .feuilleton-page .mobile-loading-stack {
          display: grid;
          gap: 10px;
          width: min(100%, 320px);
          margin: 8px auto 0;
        }
        .feuilleton-page .mobile-loading-stack span {
          display: block;
          height: 14px;
          border: 1px solid rgba(20,17,13,.25);
          background: linear-gradient(90deg, rgba(20,17,13,.08), rgba(20,17,13,.02), rgba(20,17,13,.08));
          background-size: 220% 100%;
          animation: feuilleton-sheen 1.35s ease-in-out infinite;
        }
        .feuilleton-page .mobile-loading-stack span:nth-child(2) {
          width: 84%;
        }
        .feuilleton-page .mobile-loading-stack span:nth-child(3) {
          width: 62%;
        }
        .feuilleton-page .empty-state {
          min-height: 300px;
          padding: 22px;
          text-align: left;
          align-content: center;
          place-items: initial;
        }
        .feuilleton-page .empty-state p {
          margin: 0;
          line-height: 1.35;
        }
        .feuilleton-page .empty-state-copy {
          max-width: none;
        }
        .feuilleton-page .empty-state-copy h2 {
          font-size: 31px;
        }
        .feuilleton-page .canonical-beat-handoff {
          grid-template-columns: 78px minmax(0, 1fr);
          min-height: 360px;
          box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 18%, transparent);
        }
        .feuilleton-page .canonical-beat-number {
          padding: 18px 8px;
        }
        .feuilleton-page .canonical-beat-number strong {
          font-size: 48px;
        }
        .feuilleton-page .canonical-beat-number span, .feuilleton-page .canonical-beat-number em {
          font-size: 8px;
          letter-spacing: .09em;
          writing-mode: vertical-rl;
        }
        .feuilleton-page .canonical-beat-copy {
          gap: 13px;
          padding: 24px 18px;
        }
        .feuilleton-page .canonical-beat-copy h2 {
          font-size: 32px;
        }
        .feuilleton-page .canonical-beat-copy p {
          font-size: 14px;
          line-height: 1.4;
        }
        .feuilleton-page .canonical-beat-cta {
          width: 100%;
          min-height: 58px;
          justify-content: space-between;
          padding: 0 22px;
          font-size: var(--t-body);
          line-height: 1.25;
        }
        .feuilleton-page .mobile-empty-task-note {
          display: grid;
          gap: 4px;
          width: 100%;
          border: 1px solid var(--ink);
          border-left: 5px solid var(--blue);
          background: var(--sheet);
          padding: 11px 12px;
          letter-spacing: 0;
          text-transform: none;
        }
        .feuilleton-page .mobile-empty-task-note strong {
          font-size: 12px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .feuilleton-page .mobile-empty-task-note span {
          color: var(--ink-2);
          font-size: 13px;
          font-weight: 700;
          line-height: 1.35;
        }
        .feuilleton-page .edition-preparing {
          grid-template-columns: 1fr;
          padding: 0;
          background: transparent;
        }
        .feuilleton-page .edition-actions {
          grid-template-columns: repeat(2, minmax(0, 1fr));
          min-width: 0;
        }
        .feuilleton-page .edition-preparing .fe-notice {
          margin: 0;
        }
        .feuilleton-page .edition-retrying {
          grid-column: 1 / -1;
        }
        .feuilleton-page .serial-episode-notice {
          padding-top: 18px;
        }
        .feuilleton-page .serial-episode-notice .fe-notice {
          margin: 0;
        }
        .feuilleton-page .serial-episode-filed {
          padding: 20px 16px 18px;
        }
        .feuilleton-page .serial-episode-filed h2 {
          font-size: 28px;
        }
        .feuilleton-page .serial-episode-filed p {
          font-size: 14px;
        }
        .feuilleton-page .supplement-aside {
          margin-top: 16px;
          padding-top: 12px;
        }
        .feuilleton-page .supplement-link {
          min-height: 44px;
          font-size: 10px;
        }
        .feuilleton-page .kicker {
          display: none;
        }
        .feuilleton-page .kicker span {
          flex: 0 0 auto;
          white-space: nowrap;
        }
        .feuilleton-page .today-thread-banner {
          grid-template-columns: 1fr;
          gap: 12px;
          margin-top: 12px;
          padding: 13px;
          border-left-width: 5px;
          box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--yellow) 42%, transparent);
        }
        .feuilleton-page .today-thread-banner strong {
          font-size: 23px;
        }
        .feuilleton-page .today-thread-banner p {
          font-size: 13px;
        }
        .feuilleton-page .today-thread-chips {
          justify-content: flex-start;
          max-width: 100%;
        }
        .feuilleton-page .today-thread-chip {
          max-width: 100%;
        }
        .feuilleton-page .today-thread-chip b {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .feuilleton-page.is-serial {
          padding-bottom: calc(var(--phone-bottom-nav-space) + 10px);
        }
        .feuilleton-page.is-serial .fn-grid {
          width: 100%;
          padding-top: 0;
        }
        .feuilleton-page .serial-reader {
          margin-inline: calc(0px - var(--phone-gutter));
          border-left: 0;
          border-right: 0;
        }
        .feuilleton-page .serial-reader-toggle {
          margin-left: var(--phone-gutter);
          margin-right: var(--phone-gutter);
        }
        .feuilleton-page .serial-reader .page-scene {
          padding: 14px;
        }
        .feuilleton-page .panel-grid {
          gap: 16px;
        }
        .feuilleton-page .page-scene {
          gap: 16px;
        }
        .feuilleton-page .annotation-grid {
          gap: 12px;
        }
        .feuilleton-page .panel-annotation {
          max-width: 100%;
          min-width: 0;
          border-width: 1px;
        }
        .feuilleton-page .panel-audio-button {
          width: 34px;
          height: 34px;
        }
        .feuilleton-page .episode-audio {
          display: grid;
          gap: 12px;
          padding: 14px;
        }
        .feuilleton-page .episode-audio button {
          width: 100%;
        }
        .feuilleton-page .serial-act > .fe-task {
          margin: 10px 0 16px;
        }
        .feuilleton-page .task-box {
          min-width: 0;
          padding: 12px;
          gap: 10px;
        }
        .feuilleton-page .task-prompt, .feuilleton-page .task-box input, .feuilleton-page .task-box textarea {
          font-size: 18px;
          overflow-wrap: anywhere;
        }
        .feuilleton-page .option-row {
          display: grid;
          grid-template-columns: 1fr;
        }
        .feuilleton-page .option-row button {
          width: 100%;
          text-align: left;
          overflow-wrap: anywhere;
        }
        .feuilleton-page .task-box input, .feuilleton-page .task-box textarea {
          box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--ink) 18%, transparent);
        }
        .feuilleton-page .mobile-reading-bar {
          position: fixed;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 91;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          min-height: var(--phone-bottom-nav-space);
          padding: 8px 10px calc(8px + var(--phone-safe-bottom-space));
          background: var(--paper);
          border: 0;
          border-top: 1px solid var(--ink);
          box-shadow: none;
          backdrop-filter: none;
        }
        .feuilleton-page .mobile-reading-bar button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          min-height: 44px;
          min-width: 80px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
          font-size: 10px;
          letter-spacing: .13em;
          text-transform: uppercase;
          font-weight: 900;
        }
        .feuilleton-page .mobile-reading-bar button.primary {
          background: var(--ink);
          color: var(--paper);
        }
      }
      @keyframes feuilleton-sheen {
        0% { background-position: 140% 0; }
        100% { background-position: -80% 0; }
      }
      @keyframes feuilleton-task-sheet {
        from { opacity: 0; transform: translateY(100%); }
        to { opacity: 1; transform: translateY(0); }
      }
      @keyframes feuilleton-task-scrim {
        from { background: rgba(20,17,13,0); }
        to { background: rgba(20,17,13,.4); }
      }
      @keyframes feuilleton-feedback-slip {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }
    `}</style>
  );
}
