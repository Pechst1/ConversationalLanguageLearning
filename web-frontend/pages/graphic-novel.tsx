/* Le Feuilleton — the episode page, on the Claude design (Atelier V2).
 *
 * One phone-first column. The page owns the data flow (load, create, resume,
 * submit, complete, the 409 contracts) and hands every readable scene to the
 * paged `FeuilletonReader`; the states around the reader are drawn from the
 * design's FEUILLETON artboard (kicker + one Garamond headline, the blue story
 * hero with its paper-on-blue press, paper rows with an ink done badge, a
 * dashed locked row for a genuinely delayed episode) and its SESSION chrome
 * (notices, the hatched "sous presse" plate). Every rule below is an `--av2-*`
 * token, written `.av2 .gn-…`. */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { StoryEpisodeReader } from '@/components/atelier-v2/journey/StoryEpisodeReader';
import type { StoryEpisode } from '@/types/daily-journey';
import {
  Action,
  ArrowRightIcon,
  AtelierV2Root,
  CheckIcon,
  Chip,
  IconAction,
  LockIcon,
  Notice,
  Portrait,
  ShapeToken,
  Skeleton,
  SpinnerToken,
  StopIcon,
} from '@/components/atelier-v2/ui';
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
type DayProgressFlag = Parameters<typeof writeLocalDayProgressFlag>[0];
type ServerDayProgressCandidate = {
  progress?: Partial<Record<DayProgressFlag, boolean>> | null;
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

  const targetVocabulary = useMemo(() => sceneTargetVocabulary(scene), [scene]);
  const sceneNeedsGenerationPolling = useMemo(() => (
    Boolean(scene?.id)
    && ['writing', 'generating'].includes(String(scene?.status || ''))
  ), [scene]);

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
  const readerIndex = clampStageIndex(stageIndex, readerStages.length);
  // The illustrated-page render mode composes one printed page for the whole
  // scene; the reader shows it as the plate of every panel that has no art of
  // its own.
  const pageArt = scene?.script_payload?.render_mode === 'page'
    ? resolveMediaUrl(scene.script_payload?.page_image?.url)
    : null;

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

  /* ---- which face the page shows ------------------------------------------ */
  const scenePressing = Boolean(
    scene && (scene.status === 'writing' || (scene.status === 'generating' && !(scene.panels || []).length)),
  );
  const readerMounted = !loading && !generationFailure && !scenePressing
    && (Boolean(storyEpisode) || Boolean(scene && readerStages.length > 0));
  const nextBeat = scene ? feuilletonNextBeat(scene, targetVocabulary) : { href: null, label: '' };
  const showEditionTools = Boolean(
    scene && !scene.serial_thread_id && !['writing', 'generating'].includes(scene.status),
  );
  const head = pageHead({ loading, generationFailure, scene, scenePressing, canonicalBeat });

  return (
    <>
      <FeuilletonReaderStyles />
      <FeuilletonStyles />
      <AtelierV2Root
        as="main"
        aria-label="Mode Feuilleton"
        className={`fr-page gn-page feuilleton-page ${scene ? 'has-scene' : ''}`}
      >
        <header className="fr-page-head gn-head">
          {/* the one Garamond italic headline on this screen — the reader
              carries its own once it is mounted */}
          {!readerMounted && (
            <div>
              <div className="k">{head.kicker}</div>
              <h1>{head.title}</h1>
            </div>
          )}
          <nav className="gn-seg" aria-label="Le Feuilleton">
            <Link href="/graphic-novel" aria-current="page">L’épisode</Link>
            <Link href="/serial">La saison</Link>
            <Link href="/serial/cast">Les personnages</Link>
          </nav>
          {(showEditionTools || (!scene && !loading)) && (
            <div className="gn-actions" aria-label="Actions de lecture du Feuilleton">
              <Link className="av2-btn av2-btn--quiet av2-btn--inline" href="/atelier">
                {scene ? 'Retour à l’Atelier' : 'Retour à La Une'}
              </Link>
              {scene && showEditionTools && (
                <Action
                  tone="quiet"
                  inline
                  disabled={creating || scene.status === 'writing'}
                  pending={creating || scene.status === 'writing'}
                  pendingLabel="Recherche du fil"
                  onClick={openCanonicalBeat}
                  iconAfter={<ArrowRightIcon size={14} />}
                >
                  Reprendre l’histoire
                </Action>
              )}
            </div>
          )}
        </header>

        {creating && (
          <ComposingNotice panelCount={panelCount} renderMode={renderMode} />
        )}

        {!scene && visibleThreadContext && (
          <TodayThreadBanner context={visibleThreadContext} />
        )}

        {loading ? (
          <div className="gn-skeleton" aria-live="polite" aria-busy="true">
            <span className="fr-sr">
              Ouverture du Feuilleton. Recherche de l’édition en cours. Si aucune n’est prête, un seul bouton permettra de la composer.
            </span>
            <Skeleton height={200} radius={24} />
            <Skeleton height={80} radius={16} />
            <Skeleton height={80} radius={16} />
          </div>
        ) : generationFailure ? (
          <EditionPreparing failure={generationFailure} onRetry={canonicalBeat ? openCanonicalBeat : () => createScene()} creating={creating} />
        ) : scene && scenePressing ? (
          <EditionWriting scene={scene} />
        ) : storyEpisode ? (
          <div className="gn-reader">
            <StoryEpisodeReader
              episode={storyEpisode}
              mode="replay"
              onExit={() => { void router.push('/serial'); }}
              nextHref="/serial"
              nextLabel="Retour à la saison"
            />
          </div>
        ) : scene && readerStages.length > 0 ? (
          <>
            <div className="gn-reader">
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
                completeLabel="Terminer l’épisode"
                filed={scene.status === 'completed'}
                nextHref={nextBeat.href}
                nextLabel={nextBeat.label}
                pageArt={pageArt}
                renderStageTools={(stage) => (stage.kind === 'panel' ? <PanelAudioButton panel={panelById(scene, stage.panelId)} /> : null)}
                taskNote={(task) => String(task.recommendation_reason?.text || '').trim()}
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
                    {scene.status === 'generating' && <EditionArtProgress scene={scene} />}
                    {!scene.serial_thread_id && <StandaloneBrief scene={scene} />}
                    <ReaderCastLink scene={scene} />
                  </>
                )}
              />
            </div>
            <EpisodeAudioControls scene={scene} />
            <FeuilletonEnd scene={scene} />
          </>
        ) : scene ? (
          <EditionWithoutPlates scene={scene} completing={completing} onComplete={completeScene} />
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
      </AtelierV2Root>
      <PhoneProductNav active="feuilleton" />
    </>
  );
}

/* The kicker and the headline for the faces the reader does not own. */
function pageHead({
  loading,
  generationFailure,
  scene,
  scenePressing,
  canonicalBeat,
}: {
  loading: boolean;
  generationFailure: Record<string, any> | null;
  scene: GraphicNovelScene | null;
  scenePressing: boolean;
  canonicalBeat: SerialToday | null;
}): { kicker: string; title: string } {
  if (loading) return { kicker: 'Le feuilleton', title: 'Ouverture de l’épisode…' };
  if (generationFailure) return { kicker: 'Le feuilleton · avis de la rédaction', title: 'L’édition n’a pas pu paraître.' };
  if (scene && scenePressing) {
    const printing = scene.status === 'generating';
    return {
      kicker: `${readerEpisodeLabel(scene as any)} · ${printing ? 'impression en cours' : 'rédaction en cours'}`,
      title: printing ? 'Les planches s’impriment' : 'L’édition se compose',
    };
  }
  if (scene) return { kicker: readerEpisodeLabel(scene as any), title: scene.title || 'Le feuilleton' };
  if (canonicalBeat?.kind === 'feuilleton' || canonicalBeat?.kind === 'mission') {
    return { kicker: `Le feuilleton · Saison ${serialSeasonNumber(canonicalBeat)}`, title: 'L’épisode du jour' };
  }
  return { kicker: 'Le feuilleton · hors édition', title: 'Le supplément illustré' };
}

function panelById(scene: GraphicNovelScene, panelId: string): GraphicNovelPanel | null {
  return (scene.panels || []).find((panel) => String(panel.id) === String(panelId)) || null;
}

/* Where the story goes after this episode — read from the server's own hook.
   When the payload names no next beat, the reader offers nothing rather than
   promising a chapter that does not exist. The mission route carries the
   edition's concepts, words and errata so Le Courrier can pick them up. */
function feuilletonNextBeat(
  scene: GraphicNovelScene,
  vocabulary: FeuilletonVocabularyItem[],
): { href: string | null; label: string } {
  const hook = scene.hook || scene.script_payload?.hook || scene.recap?.hook || {};
  const items = sceneVocabularyRecapItems(scene, vocabulary);
  const vocabularyIds = items.map((item) => Number(item.word_id)).filter((item) => Number.isFinite(item));
  const conceptIds = (scene.selected_concept_ids || []).slice(0, 4);
  const errataIds = (scene.target_errata_ids || []).slice(0, 2);
  const nextEpisode = typeof scene.episode_index === 'number' ? scene.episode_index + 1 : undefined;
  const nextBeatIsMission = hook?.next_beat_kind === 'mission';
  const missionPairs: Array<[string, string | number | null | undefined]> = [
    ['mission', scene.mission_id || undefined],
    ['atelier_session_id', scene.atelier_session_id || undefined],
    ['serial_thread_id', scene.serial_thread_id || undefined],
    ['episode_index', nextEpisode],
    ...conceptIds.map((id): [string, number] => ['concept_id', id]),
    ...vocabularyIds.slice(0, 4).map((id): [string, number] => ['vocabulary_id', id]),
    ...errataIds.map((id): [string, string] => ['erratum_id', String(id)]),
  ];
  const readerPairs: Array<[string, string | number | null | undefined]> = [
    ['serial_thread_id', scene.serial_thread_id || undefined],
    ['episode_index', nextEpisode],
  ];
  if (nextBeatIsMission) {
    return { href: routeWithQuery('/missions', missionPairs), label: 'Agir dans Le Courrier' };
  }
  if (!scene.serial_thread_id) return { href: null, label: '' };
  return { href: routeWithQuery('/graphic-novel', readerPairs), label: 'Lire le prochain épisode' };
}

/* ---- notices around the reader --------------------------------------------- */

/* The same real numbers as before, in the reader's own surface. */
function EditionArtProgress({ scene }: { scene: GraphicNovelScene }) {
  const panels = scene.panels || [];
  const ready = panels.filter((panel) => Boolean(panelImageUrl(panel))).length;
  return (
    <div className="fr-notice" role="status" aria-live="polite">
      <p>
        <b>L’histoire est prête.</b> Les illustrations s’impriment en arrière-plan —{' '}
        {ready} sur {panels.length}.
      </p>
    </div>
  );
}

/* A standalone edition's public synopsis, when the brief has one worth printing. */
function StandaloneBrief({ scene }: { scene: GraphicNovelScene }) {
  const brief = feuilletonPublicBrief(scene.brief);
  if (!brief) return null;
  return <p className="gn-brief">{brief}</p>;
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
  const closeness = Number(member.relationship?.closeness || 0);
  return (
    <div className="fr-tools">
      <Link
        className="fr-chip"
        href="/serial/cast"
        aria-label={`Relation avec ${member.name} : ${register}, proximité ${closeness} sur 5`}
      >
        <Portrait name={member.name} size="sm" />
        {member.name} · vous vous dites « {register} »
      </Link>
    </div>
  );
}

/* While a composition request is in flight. No fake step ladder, no
   percentage: the request either returns a scene or an error. */
function ComposingNotice({ panelCount, renderMode }: { panelCount: PanelCount; renderMode: RenderMode }) {
  const visualTarget = renderMode === 'page' ? 'la page illustrée' : `${panelCount} planches`;
  return (
    <div className="gn-stack">
      <Notice shape="story" live="status">
        <p className="gn-inflight"><SpinnerToken /> Composition de l’édition</p>
        <p>
          Écriture du ressort, puis impression de {visualTarget}. Les images demandent le plus de temps ;
          gardez cet écran ouvert, la lecture s’ouvre dès que la scène est prête.
        </p>
      </Notice>
    </div>
  );
}

/* L'ÉPISODE — the tab's decision tree.
     · feuilleton episode with a scene   → the reader (handled upstream)
     · feuilleton episode, no scene yet  → SerialEpisodeLead (the story hero)
     · episode status "delayed"          → SerialEpisodeDelayed (locked row + retry)
     · episode status "completed"        → SerialEpisodeFiled (done row + LA SAISON)
     · mission beat                      → the canonical handoff (story hero)
     · no serial thread at all           → the standalone supplément empty state
   In every serial case the supplément stays reachable, as one quiet row. */
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
    // The story engine manages this learner's episode; it opens in the séance.
    const inJourney =
      status === 'journey_required' || Boolean((canonicalBeat as Record<string, any>).story_engine);
    return (
      <>
        {inJourney ? (
          <SerialEpisodeInJourney beat={canonicalBeat} creating={creating} onOpenSerial={onOpenSerial} />
        ) : status === 'delayed' ? (
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

function serialBeatArt(beat: SerialToday): string | null {
  const record = beat as SerialToday & Record<string, any>;
  return resolveMediaUrl(firstString(record.lead_image_url, record.thumbnail_url));
}

/* The cast of a beat, as paper chips with the character's portrait. */
function CastChips({ names, label }: { names: string[]; label: string }) {
  if (!names.length) return null;
  return (
    <div className="gn-cast" aria-label={label}>
      {names.map((name) => (
        <span className="fr-chip" key={name}>
          <Portrait name={name} size="sm" />
          {name}
        </span>
      ))}
    </div>
  );
}

/* The serial episode of the day, before its planches are on the desk — the
   design's blue story hero, its CTA the one tactile press on this screen. */
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
  const art = serialBeatArt(beat);
  return (
    <section className="fr-hero" aria-label="Épisode du Feuilleton">
      <div className="art">
        {art ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={art} alt="" />
        ) : (
          <span>L’illustration de cet épisode n’est pas encore parue.</span>
        )}
      </div>
      <div className="body">
        <div className="k">Épisode {number} · {pressing ? 'sous presse' : 'aujourd’hui'}</div>
        <h2>{pressing ? 'L’épisode du jour est sous presse.' : 'L’épisode du jour vous attend.'}</h2>
        <p className="gn-hero-p">{pressing
          ? 'La rédaction compose la planche. Rouvrez dans un instant : votre place dans la saison est gardée.'
          : serialBeatStoryPressure(beat)}</p>
        <CastChips names={names} label="Personnages de cet épisode" />
        <button className="cta gn-hero-cta" type="button" disabled={creating} onClick={onOpenSerial}>
          {creating ? <SpinnerToken /> : null}
          {creating ? 'Recherche du fil' : pressing ? 'Voir où en est l’épisode' : 'Ouvrir l’épisode du jour'}
          {creating ? null : <ArrowRightIcon size={18} />}
        </button>
        <p className="gn-hero-small">C’est l’épisode annoncé à La Une. Il continue votre saison ; il n’en ouvre pas une autre.</p>
      </div>
    </section>
  );
}

/* The engine-managed learner's episode lives inside the day's séance: the
   backend answers `journey_required`, or serialises the episode with a
   `story_engine` stamp and `continue_href: /atelier`. Promising "l'épisode du
   jour vous attend" here and then landing on the Atelier made the page tell
   the learner where they were going only after they had gone (WP-20 D-13). */
function SerialEpisodeInJourney({
  beat,
  creating,
  onOpenSerial,
}: {
  beat: SerialToday;
  creating: boolean;
  onOpenSerial: () => void;
}) {
  const number = serialEpisodeNumber(beat);
  const names = serialBeatCharacterNames(beat);
  const art = serialBeatArt(beat);
  return (
    <section className="fr-hero" aria-label="Épisode du Feuilleton">
      <div className="art">
        {art ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={art} alt="" />
        ) : (
          <span>L’illustration de cet épisode n’est pas encore parue.</span>
        )}
      </div>
      <div className="body">
        <div className="k">Épisode {number} · dans la séance</div>
        <h2>L’épisode du jour se lit dans la séance.</h2>
        <p className="gn-hero-p">
          Votre histoire se joue avant de se lire : l’épisode s’ouvre au début de la séance du jour,
          pas ici. Cette page garde les archives.
        </p>
        <CastChips names={names} label="Personnages de cet épisode" />
        <button className="cta gn-hero-cta" type="button" disabled={creating} onClick={onOpenSerial}>
          {creating ? <SpinnerToken /> : null}
          {creating ? 'Recherche du fil' : 'Ouvrir la séance du jour'}
          {creating ? null : <ArrowRightIcon size={18} />}
        </button>
        <p className="gn-hero-small">C’est l’épisode annoncé à La Une. Il continue votre saison ; il n’en ouvre pas une autre.</p>
      </div>
    </section>
  );
}

/* Honest press notice for an episode the backend reports as "delayed": the
   design's dashed locked row, then one retry. */
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
    <section className="gn-stack" aria-label="Épisode retardé du Feuilleton">
      <div className="fr-rows">
        <div className="fr-row is-locked">
          <span className="thumb" aria-hidden="true"><LockIcon size={22} /></span>
          <span className="meta">
            <span className="k">Épisode {number} · retardé</span>
            <span className="t">Sous presse</span>
          </span>
        </div>
      </div>
      <Notice shape="action" live="status">
        <p className="gn-strong">Le Feuilleton · Épisode {number}</p>
        <p>L’épisode est retardé — la rédaction met la planche sous presse.</p>
        <Action tone="primary" inline pending={creating} pendingLabel="Nouvelle tentative" onClick={onRetry}>
          Réessayer
        </Action>
      </Notice>
      <div className="gn-links">
        <Link className="av2-btn av2-btn--quiet av2-btn--inline" href="/serial">Relire la saison</Link>
        <Link className="av2-btn av2-btn--quiet av2-btn--inline" href="/atelier">Retour à La Une</Link>
      </div>
    </section>
  );
}

/* The episode of the day has already been read and filed into the season:
   a read row with the ink done badge. */
function SerialEpisodeFiled({ beat, onOpenSerial }: { beat: SerialToday; onOpenSerial: () => void }) {
  const number = serialEpisodeNumber(beat);
  return (
    <section className="gn-stack" aria-label="Épisode classé du Feuilleton">
      <div className="fr-rows">
        <Link className="fr-row" href="/serial">
          <span className="thumb" aria-hidden="true" />
          <span className="meta">
            <span className="k">Épisode {number} · classé</span>
            <span className="t">L’épisode du jour est classé.</span>
          </span>
          <span className="done" aria-hidden="true"><CheckIcon size={14} /></span>
        </Link>
      </div>
      <div className="fr-notice" role="status">
        <p>Il a rejoint la saison reliée. La suite paraîtra au prochain épisode.</p>
        <Action tone="story" inline onClick={onOpenSerial} iconAfter={<ArrowRightIcon size={18} />}>
          Reprendre le fil
        </Action>
      </div>
      <div className="gn-links">
        <Link className="av2-btn av2-btn--quiet av2-btn--inline" href="/serial">Ouvrir la saison reliée</Link>
      </div>
    </section>
  );
}

/* The standalone supplément is optional and secondary wherever a serial thread
   exists: one quiet row under the episode, never the tab's default face. */
function SupplementAside({ creating, onCreate }: { creating: boolean; onCreate: () => void }) {
  return (
    <aside className="fr-rows" aria-label="Supplément illustré du Feuilleton">
      <button type="button" className="fr-row gn-row-btn" disabled={creating} onClick={onCreate}>
        <span className="thumb gn-thumb-token" aria-hidden="true"><ShapeToken kind="reward" /></span>
        <span className="meta">
          <span className="k">En marge</span>
          <span className="t">{creating ? 'Composition en cours' : 'Le supplément illustré'}</span>
        </span>
        <span className="go" aria-hidden="true">{creating ? <SpinnerToken /> : <ArrowRightIcon size={18} />}</span>
      </button>
      <p className="gn-note">Une scène composée à la demande, en marge du feuilleton. Elle ne change rien à la saison.</p>
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
    const art = serialBeatArt(canonicalBeat);
    return (
      <section className="fr-hero" aria-label="Prochain acte du Feuilleton">
        <div className="art">
          {art ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={art} alt="" />
          ) : (
            <span>Votre histoire · maintenant</span>
          )}
        </div>
        <div className="body">
          <div className="k">Acte {canonicalBeat.episode_index + 1} · maintenant</div>
          <h2>La suite se joue avant de se lire.</h2>
          <p className="gn-hero-p">{storyPressure}</p>
          <CastChips names={names} label="Personnages de cet acte" />
          <Link className="cta gn-hero-cta" href={canonicalRoute}>
            Ouvrir la mission du jour <ArrowRightIcon size={18} />
          </Link>
          <p className="gn-hero-small">Votre réponse deviendra la conséquence du prochain épisode. Aucun récit parallèle ne sera créé.</p>
        </div>
      </section>
    );
  }
  return null;
}

/* No serial thread at all — the supplément keeps its first-run face. */
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
    <section className="fr-empty gn-empty" data-feuilleton-empty="true" aria-label="Feuilleton sans édition">
      <p className="av2-label">{seedLabel}</p>
      <h2>Aucune scène sur le pupitre.</h2>
      <p>{seedCopy}</p>
      <Notice tone="quiet" shape="done" live="status">
        <p>
          <b>Feuille de tâches verrouillée</b>
          {' — '}
          Les tâches se déplient sous les planches une fois l’édition composée.
        </p>
      </Notice>
      {creating ? (
        <p className="gn-inflight" aria-live="polite">
          <SpinnerToken /> Composition en cours
        </p>
      ) : (
        <button
          aria-label="Composer une nouvelle scène du Feuilleton"
          className="fr-btn is-action"
          data-press="3d"
          type="button"
          onClick={onCreate}
        >
          Composer la première scène <ArrowRightIcon size={18} />
        </button>
      )}
    </section>
  );
}

/* A scene the server returned with nothing to read: no panel, no hook, no
   closing action. Stated, and closable, rather than an empty reader. */
function EditionWithoutPlates({
  scene,
  completing,
  onComplete,
}: {
  scene: GraphicNovelScene;
  completing: boolean;
  onComplete: () => void | Promise<unknown>;
}) {
  const filed = scene.status === 'completed';
  return (
    <section className="fr-empty gn-empty" role="status">
      <h2>Cette édition est parue sans planche.</h2>
      <p>La rédaction n’a rien livré à lire pour cette scène.</p>
      {!filed && (
        <button
          type="button"
          className="fr-btn is-action"
          data-press="3d"
          disabled={completing}
          onClick={() => void onComplete()}
        >
          {completing ? <SpinnerToken /> : <CheckIcon size={16} />}
          {completing ? 'Classement…' : 'Terminer l’épisode'}
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

/* The seeded learning thread this edition will be composed from. */
function TodayThreadBanner({ context }: { context: FeuilletonThreadContext }) {
  if (!context) return null;
  return (
    <aside className="gn-thread" aria-label="Fil du jour">
      <Notice shape="story" live="status">
        <p className="av2-label av2-label--story">Fil du jour</p>
        <p className="gn-thread-title">Scène issue de l’Atelier</p>
        <p>{context.summary}</p>
        <div className="gn-today-thread-chips">
          {context.chips.map((chip) => (
            <Chip
              key={chip.key}
              tone={chip.tone === 'yellow' ? 'reward' : chip.tone === 'blue' ? 'story' : 'plain'}
              icon={<ShapeToken kind={chip.tone === 'red' ? 'action' : chip.tone === 'blue' ? 'story' : 'reward'} size="sm" />}
            >
              {chip.label} <b>{chip.value}</b>
            </Chip>
          ))}
        </div>
      </Notice>
    </aside>
  );
}

/* A genuine composition failure of the edition in hand. A delayed serial
   episode is not routed here — it keeps its folio (SerialEpisodeDelayed). */
function EditionPreparing({
  failure,
  onRetry,
  creating,
}: {
  failure?: Record<string, any> | null;
  onRetry: () => void;
  creating: boolean;
}) {
  const rawMessage = String(failure?.message || '').trim();
  const message = !rawMessage || /feuilleton generation failed/i.test(rawMessage)
    ? "L’édition n’a pas pu être composée. Votre progression n’a pas été modifiée."
    : rawMessage;
  return (
    <section className="gn-stack" aria-label="Avis de la rédaction">
      <Notice tone="alert" live="alert" shape="action">
        <p className="gn-strong">Avis de la rédaction</p>
        <p>{message}</p>
        <Action tone="primary" inline pending={creating} pendingLabel="Relance en cours" onClick={onRetry}>
          Relancer l’édition
        </Action>
      </Notice>
      <div className="gn-links">
        <Link className="av2-btn av2-btn--quiet av2-btn--inline" href="/grammar">Ouvrir le carnet</Link>
        <Link className="av2-btn av2-btn--quiet av2-btn--inline" href="/atelier">Retour à l’Atelier</Link>
      </div>
    </section>
  );
}

/* The edition is still being written or its first plates printed: the design's
   hatched "sous presse" plate and the real state, never a percentage. */
function EditionWriting({ scene }: { scene: GraphicNovelScene }) {
  const printing = scene.status === 'generating';
  const panels = scene.panels || [];
  const ready = panels.filter((panel) => Boolean(panelImageUrl(panel))).length;
  return (
    <section className="gn-stack" aria-live="polite" aria-label="Edition en préparation">
      <figure className="fr-plate is-printing">
        <figcaption className="fr-plate-note">
          {printing ? 'Les planches sont sous presse.' : 'La rédaction assemble le récit.'}
        </figcaption>
      </figure>
      <div className="fr-notice" role="status">
        <p className="gn-strong">{printing ? 'Le récit est prêt.' : 'Le récit arrive d’abord.'}</p>
        <p>
          {printing
            ? `Les planches sont en cours d’impression${panels.length ? ` — ${ready} sur ${panels.length}` : ''}. Cette page se met à jour automatiquement.`
            : 'Les planches seront imprimées ensuite. Cette page se met à jour automatiquement.'}
        </p>
      </div>
      <div className="gn-links">
        <Link className="av2-btn av2-btn--quiet av2-btn--inline" href="/atelier">Retour à l’Atelier</Link>
      </div>
    </section>
  );
}

/* ---- audio ------------------------------------------------------------------ */

function panelAudioUrl(panel: GraphicNovelPanel | null | undefined) {
  const url = panel?.audio_payload?.url;
  return typeof url === 'string' && url.trim() ? url : '';
}

function PlayGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M7 4l13 8-13 8z" />
    </svg>
  );
}

/* One panel's narration, in the reader's tools row. */
function PanelAudioButton({ panel }: { panel: GraphicNovelPanel | null }) {
  const audioUrl = panelAudioUrl(panel);
  const [playing, setPlaying] = useState(false);
  if (!panel || !audioUrl) return null;
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
    <IconAction
      label={`Écouter la planche ${panel.panel_index}`}
      className="gn-play"
      onClick={play}
      disabled={playing}
      aria-pressed={playing}
    >
      {playing ? <StopIcon size={16} /> : <PlayGlyph />}
    </IconAction>
  );
}

/* The whole episode, narrated planche by planche. */
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

  const planches = `${audioPanels.length} planche${audioPanels.length === 1 ? '' : 's'} narrée${audioPanels.length === 1 ? '' : 's'}`;
  return (
    <div className="gn-audio" aria-label="Écouter l’épisode">
      <IconAction
        label={playing ? 'Arrêter la lecture' : 'Écouter l’épisode'}
        className="gn-play"
        aria-pressed={playing}
        onClick={() => (playing ? stop() : void playFrom(0))}
      >
        {playing ? <StopIcon size={16} /> : <PlayGlyph />}
      </IconAction>
      <div className="gn-audio-meta">
        <p className="gn-strong">{playing ? 'Lecture en cours' : 'Écouter l’épisode'}</p>
        <Chip tone="quiet" icon={<ShapeToken kind="story" size="sm" />}>{planches}</Chip>
      </div>
    </div>
  );
}

/* ---- the end of the episode ------------------------------------------------- */

/* Once filed, the episode closes on the ink "done" state and at most one
   credit sentence. The next beat is the reader's own closing action. */
function FeuilletonEnd({ scene }: { scene: GraphicNovelScene }) {
  const filed = scene.status === 'completed';
  if (!filed) return null;
  const creditLine = feuilletonCreditLine(scene);
  const number = typeof scene.episode_index === 'number' ? ` · Épisode ${scene.episode_index + 1}` : '';
  return (
    <section className="gn-end" aria-label="Fin de l’épisode">
      <p className="fr-state">
        <span className="tok" aria-hidden="true"><CheckIcon size={11} /></span>
        Classé{number}
      </p>
      {creditLine && <p className="gn-credit">{creditLine}</p>}
    </section>
  );
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

/* ---- pure helpers ----------------------------------------------------------- */

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

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

function finalSceneTask(scene: GraphicNovelScene): OverlayTask | null {
  const task = scene.script_payload?.final_prompt;
  if (scene.script_payload?.experience_mode === 'reward') return null;
  return task?.id ? { ...task, panel: null } : null;
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

/* ---- the page's own rules — `.av2 .gn-…`, tokens only ------------------------ */
function FeuilletonStyles() {
  return (
    <style jsx global>{`
      .av2.gn-page {
        min-height: 100vh;
        padding-bottom: calc(28px + var(--phone-bottom-nav-space, 88px));
      }
      .av2 .gn-head { display: flex; flex-direction: column; gap: 14px; }
      /* the cross-route IA as the design's segmented pill */
      .av2 .gn-seg {
        display: flex;
        gap: 2px;
        padding: 3px;
        border-radius: var(--av2-r-pill);
        background: var(--av2-card);
      }
      .av2 .gn-seg a {
        flex: 1 1 0;
        min-height: var(--av2-tap);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0 10px;
        border-radius: var(--av2-r-pill);
        color: var(--av2-ink);
        font-size: var(--av2-t-label);
        font-weight: 700;
        text-align: center;
        text-decoration: none;
        overflow-wrap: anywhere;
      }
      .av2 .gn-seg a[aria-current='page'] { background: var(--av2-ink); color: var(--av2-on-ink); }
      .av2 .gn-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
      .av2 .gn-stack { display: flex; flex-direction: column; gap: 12px; margin-top: 18px; }
      .av2 .gn-links { display: flex; flex-wrap: wrap; gap: 4px 8px; }
      .av2 .gn-strong { margin: 0; font-weight: 700; color: var(--av2-ink); }
      .av2 .gn-inflight { display: flex; align-items: center; gap: 8px; margin: 0; font-weight: 700; color: var(--av2-ink); }
      .av2 .gn-note { margin: 2px 4px 0; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-muted); }
      .av2 .gn-brief { margin: 0 0 12px; font-size: var(--av2-t-label); line-height: 1.5; color: var(--av2-ink-2); }
      .av2 .gn-skeleton { display: flex; flex-direction: column; gap: 8px; margin-top: 18px; }

      /* the reader sits in the page column; it does not add its own gutter */
      .av2 .gn-reader { margin-top: 6px; }
      .av2 .gn-reader .fr-reader { max-width: none; padding-left: 0; padding-right: 0; }

      /* the seeded learning thread */
      .av2 .gn-thread { margin-top: 18px; }
      .av2 .gn-thread-title {
        margin: 0;
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: var(--av2-t-rule);
        line-height: 1.15;
        color: var(--av2-ink);
      }
      .av2 .gn-today-thread-chips { display: flex; flex-wrap: wrap; gap: 6px; }
      .av2 .gn-today-thread-chips b { font-weight: 400; }

      /* the story hero's extensions: a body line, the cast, one small note */
      .av2 .gn-hero-p { margin: 8px 0 0; font-size: var(--av2-t-body); line-height: 1.45; color: inherit; opacity: 0.92; }
      .av2 .gn-hero-small { margin: 10px 0 0; font-size: var(--av2-t-meta); line-height: 1.4; color: inherit; opacity: 0.85; }
      .av2 .gn-cast { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
      .av2 .gn-cast .fr-chip { min-height: 36px; padding-left: 8px; }
      /* disabled dims the face, never the label */
      .av2 .gn-hero-cta:disabled {
        cursor: progress;
        background: var(--av2-line);
        color: var(--av2-ink-2);
        box-shadow: none;
        transform: none;
      }

      /* a paper row as a button */
      .av2 .gn-row-btn { width: 100%; border: 0; font: inherit; text-align: left; cursor: pointer; }
      .av2 .gn-row-btn:disabled { cursor: progress; }
      .av2 .gn-row-btn:disabled .t { color: var(--av2-ink-2); }
      .av2 .gn-thumb-token { display: grid; place-items: center; }

      .av2 .gn-empty { gap: 12px; }

      /* narration */
      .av2 .gn-audio {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 14px;
        padding: 10px 12px;
        border-radius: var(--av2-r-card);
        background: var(--av2-card);
      }
      .av2 .gn-audio-meta { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
      .av2 .gn-play[aria-pressed='true'] { background: var(--av2-ink); color: var(--av2-on-ink); }
      .av2 .gn-play svg { display: block; }

      /* the end */
      .av2 .gn-end { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 18px 0 6px; }
      .av2 .gn-credit {
        margin: 0;
        max-width: 34ch;
        text-align: center;
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: var(--av2-t-body);
        line-height: 1.4;
        color: var(--av2-muted);
      }
    `}</style>
  );
}
