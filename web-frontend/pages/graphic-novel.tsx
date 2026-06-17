import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';
import { ArrowRight, Check, Loader2, Pause, PlayCircle, Send, Sparkles, Volume2, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import { ContinuationCard, MobileBottomSheet, RedInkRepairSlip, VocabularyCreditBadge } from '@/components/mobile';
import { writeLocalDayProgressFlag } from '@/lib/atelier-next';
import { panelImageUrl } from '@/lib/graphic-novel-images';
import apiService, {
  GraphicNovelAttemptResult,
  GraphicNovelPanel,
  GraphicNovelScene,
  GraphicNovelToday,
  MissionTargetVocabulary,
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

export default function GraphicNovelPage() {
  const router = useRouter();
  const [today, setToday] = useState<GraphicNovelToday | null>(null);
  const [scene, setScene] = useState<GraphicNovelScene | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [submittingTask, setSubmittingTask] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [lastCorrection, setLastCorrection] = useState<Record<string, any> | null>(null);
  const [taskSubmitError, setTaskSubmitError] = useState<TaskSubmitError>(null);
  const [generationFailure, setGenerationFailure] = useState<Record<string, any> | null>(null);
  const [activeMobileTaskId, setActiveMobileTaskId] = useState<string | null>(null);
  const [mobileTaskFlyoutOpen, setMobileTaskFlyoutOpen] = useState(false);
  const [revealedMobileStopIds, setRevealedMobileStopIds] = useState<string[]>([]);
  const [showMobileTranslations, setShowMobileTranslations] = useState(false);
  const [panelCount, setPanelCount] = useState<PanelCount>(6);
  const [storyQuality, setStoryQuality] = useState<StoryQuality>('standard');
  const [humorStyle, setHumorStyle] = useState<HumorStyle>('satirical');
  const experienceMode: ExperienceMode = 'study';
  const [renderMode, setRenderMode] = useState<RenderMode>('panels');
  const [serialReaderMode, setSerialReaderMode] = useState<'vertical' | 'page'>('vertical');
  const [imageQuality, setImageQuality] = useState<ImageQuality>('medium');
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

  const tasks = useMemo(() => extractTasks(scene), [scene]);
  const targetVocabulary = useMemo(() => sceneTargetVocabulary(scene), [scene]);
  const sceneNeedsImagePolling = useMemo(() => (
    Boolean(scene?.id)
    && scene?.status === 'generating'
    && (
      scene.script_payload?.render_mode === 'page'
        ? !scene.script_payload?.page_image?.url
        : (scene.panels || []).some((panel) => !panelImageUrl(panel))
    )
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
  const nextMobileTaskId = useMemo(
    () => mobileCountableTasks.find((task) => !attemptsByTask[task.id])?.id || mobileCountableTasks[0]?.id || null,
    [attemptsByTask, mobileCountableTasks],
  );
  const activeMobileTask = useMemo(
    () => mobileCountableTasks.find((task) => String(task.id) === activeMobileTaskId) || mobileCountableTasks.find((task) => String(task.id) === nextMobileTaskId) || null,
    [activeMobileTaskId, mobileCountableTasks, nextMobileTaskId],
  );
  const activeMobileTaskStop = useMemo(
    () => activeMobileTask ? findMobileTaskStop(mobileTaskStops, String(activeMobileTask.id)) : null,
    [activeMobileTask, mobileTaskStops],
  );

  const openMobileTask = useCallback((taskId?: string | null, options: { scroll?: boolean } = {}) => {
    const safeTaskId = taskId ? String(taskId) : '';
    if (!safeTaskId) return;
    const stop = findMobileTaskStop(mobileTaskStops, safeTaskId);
    if (!stop) {
      setMobileTaskFlyoutOpen(false);
      return;
    }
    setActiveMobileTaskId(safeTaskId);
    setMobileTaskFlyoutOpen(true);
    if (options.scroll) {
      window.setTimeout(() => scrollToFeuilletonSection(stop.elementId), 0);
    }
  }, [mobileTaskStops]);

  const closeMobileTaskFlyout = useCallback(() => {
    setMobileTaskFlyoutOpen(false);
  }, []);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    try {
      if (routeSceneId) {
        const loaded = await apiService.getGraphicNovelScene(routeSceneId);
        setScene(loaded);
        setGenerationFailure(null);
        return;
      }
      const next = await apiService.getGraphicNovelToday();
      setToday(next);
      setScene(contextSceneKey ? null : next.active_scene || next.available_scene || null);
      setGenerationFailure(null);
    } catch (error) {
      console.error(error);
      setToday(null);
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

  useEffect(() => {
    setActiveMobileTaskId(null);
    setMobileTaskFlyoutOpen(false);
    setRevealedMobileStopIds([]);
  }, [scene?.id]);

  useEffect(() => {
    if (!taskSubmitError?.taskId) return;
    openMobileTask(taskSubmitError.taskId);
  }, [openMobileTask, taskSubmitError?.taskId]);

  useEffect(() => {
    if (!scene?.id || !sceneNeedsImagePolling) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const loaded = await apiService.getGraphicNovelScene(scene.id);
        if (!cancelled) setScene(loaded);
      } catch (error) {
        console.error(error);
      }
    };
    const timer = window.setInterval(() => {
      void poll();
    }, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [scene?.id, sceneNeedsImagePolling]);

  useEffect(() => {
    if (typeof window === 'undefined' || !scene || !mobileTaskStops.length) return;
    const media = window.matchMedia('(max-width: 760px)');
    if (!media.matches) return;
    const elements = mobileTaskStops
      .map((stop) => document.querySelector<HTMLElement>(`[data-mobile-task-stop="${stop.id}"]`))
      .filter(Boolean) as HTMLElement[];
    if (!elements.length) return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      const stopId = visible?.target.getAttribute('data-mobile-task-stop');
      if (!stopId) return;
      window.setTimeout(() => {
        setRevealedMobileStopIds((current) => (
          current.includes(stopId) ? current : [...current, stopId]
        ));
      }, 150);
    }, { rootMargin: '-18% 0px -42% 0px', threshold: [0.35, 0.55, 0.75] });
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [scene, mobileTaskStops]);

  async function createScene(extra?: Record<string, any>) {
    setCreating(true);
    if (!scene) setGenerationFailure(null);
    const toastId = toast.loading('Writing the edition. Art will appear panel by panel.');
    try {
      const conceptIds = queryList(routeQuery.concept_id).map(Number).filter(Boolean);
      const errataIds = queryList(routeQuery.erratum_id);
      const vocabularyIds = queryList(routeQuery.vocabulary_id).map(Number).filter(Boolean);
      const atelierSessionId = typeof routeQuery.atelier_session_id === 'string' ? routeQuery.atelier_session_id : undefined;
      const missionId = typeof routeQuery.mission_id === 'string' ? routeQuery.mission_id : undefined;
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
        use_news: true,
        panel_count: panelCount,
        story_quality: storyQuality,
        humor_style: humorStyle,
        experience_mode: experienceMode,
        render_mode: renderMode,
        image_quality: imageQuality,
        public_figure_mode: 'named_context',
        force_new: true,
        refresh_news: true,
        ...extra,
      });
      setThreadContext(feuilletonThreadContextFromQuery(routeQuery));
      setScene(next);
      setGenerationFailure(null);
      setLastCorrection(null);
      router.replace({ pathname: '/graphic-novel', query: sceneRouteQuery(next) }, undefined, { shallow: true });
      toast.success(next.status === 'generating' ? 'Script ready. Art is printing.' : 'Feuilleton ready.', { id: toastId });
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      if (detail?.code === 'feuilleton_generation_failed') {
        if (scene) {
          setGenerationFailure(null);
        } else {
          setGenerationFailure(detail);
        }
      }
      const message = error instanceof Error && error.message === 'Network Error'
        ? 'Could not create Feuilleton. The image request may still be running; reload in a moment.'
        : detail?.code === 'feuilleton_generation_failed'
          ? 'The service did not return a complete Feuilleton.'
          : 'Could not create Feuilleton.';
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
        const loaded = await apiService.getGraphicNovelScene(serial.scene_id);
        setThreadContext(feuilletonThreadContextFromQuery(routeQuery));
        setScene(loaded);
        setGenerationFailure(null);
        await router.replace({ pathname: '/graphic-novel', query: sceneRouteQuery(loaded) }, undefined, { shallow: true });
        return;
      }
      if (sameThread && sameEpisode && serial.kind === 'feuilleton' && serial.status === 'delayed') {
        setScene(null);
        setGenerationFailure({
          code: 'serial_edition_delayed',
          message: "L'édition de demain est retardée.",
        });
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
      setTaskSubmitError({ taskId, message: 'Write or choose an answer first.' });
      toast.error('Write or choose an answer first.');
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
      setLastCorrection(result.correction ? { ...result.correction, task_id: taskId } : null);
      setTaskSubmitError(null);
    } catch {
      setTaskSubmitError({ taskId, message: 'The correction could not be submitted. Try once more.' });
      toast.error('The Feuilleton correction could not be submitted.');
    } finally {
      setSubmittingTask(null);
    }
  }

  async function completeScene() {
    if (!scene) return false;
    setCompleting(true);
    try {
      const result = await apiService.completeGraphicNovelScene(scene.id);
      setScene(result.scene);
      await writeSideQuestProgressFlag('feuilletonDone');
      toast.success('Feuilleton complete.');
      void router.push('/atelier');
      return true;
    } catch {
      toast.error('Could not complete Feuilleton.');
      return false;
    } finally {
      setCompleting(false);
    }
  }

  return (
    <>
      <FeuilletonStyles />
      <main className={`feuilleton-page ${scene ? 'has-scene' : ''} ${serialReadFirst ? 'is-serial' : ''}`}>
        <EditorialMasthead
          active="studio"
          hideMobileNav={!!scene}
          mobileAction={(
            <div className="feuilleton-mobile-actions">
              <Link className="feuilleton-mobile-today" href="/atelier" aria-label="Back to today">
                Today
              </Link>
              {scene && (
                <button
                  aria-label={showMobileTranslations ? 'Hide English translations' : 'Show English translations'}
                  aria-pressed={showMobileTranslations}
                  className={`feuilleton-mobile-en-toggle ${showMobileTranslations ? 'active' : ''}`}
                  type="button"
                  onClick={() => setShowMobileTranslations((current) => !current)}
                >
                  {showMobileTranslations ? 'EN ●' : 'EN'}
                </button>
              )}
              {scene && (
                <button
                  aria-label="Create a new Feuilleton scene"
                  className="feuilleton-mobile-new-scene"
                  disabled={creating}
                  type="button"
                  onClick={() => createScene()}
                >
                  {creating ? <Loader2 className="spin" size={13} /> : <Sparkles size={13} />}
                  <span>{creating ? 'Making' : 'New'}</span>
                </button>
              )}
            </div>
          )}
        />

        <div className="fn-spread fn-grid">
          <section className="fn-main">
            {(!scene || !serialReadFirst) && (
              <div className="fn-title">
                <div>
                  <div className="t-mono">ATELIER DETOUR</div>
                  <h1>Feuilleton</h1>
                </div>
                <div className="create-console">
                  <Link className="btn atelier-return" href="/atelier">
                    BACK TO TODAY <ArrowRight size={14} />
                  </Link>
                  {!scene?.serial_thread_id && (
                    <>
                      <div className="preset-row" aria-label="Feuilleton mode">
                        <button
                          className={storyQuality === 'standard' && renderMode === 'panels' && imageQuality === 'medium' ? 'active' : ''}
                          type="button"
                          onClick={() => {
                            setPanelCount(6);
                            setStoryQuality('standard');
                            setRenderMode('panels');
                            setImageQuality('medium');
                          }}
                        >
                          Daily <span>panels · medium · study</span>
                        </button>
                      </div>
                      <div className="seg-row" aria-label="Panel count">
                        {([4, 6, 8] as PanelCount[]).map((count) => (
                          <button key={count} className={panelCount === count ? 'active' : ''} onClick={() => setPanelCount(count)} type="button">
                            {count} <span>{count === 4 ? 'quick' : count === 6 ? 'standard' : 'long'}</span>
                          </button>
                        ))}
                      </div>
                      <button className="btn red" disabled={creating} onClick={() => createScene()}>
                        {creating ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
                        {creating ? 'GENERATING PANELS' : 'NEW SCENE'} <ArrowRight size={14} />
                      </button>
                    </>
                  )}
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
                <span className="loading-label">LOADING FEUILLETON</span>
                <p className="mobile-loading-copy">Looking for an active edition. If none is ready, you will get one clear create button instead of a phantom task sheet.</p>
                <div className="mobile-loading-stack" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            ) : generationFailure ? (
              <EditionPreparing failure={generationFailure} onRetry={() => createScene()} creating={creating} />
            ) : scene ? (
              <>
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
                    onOpenMobileTask={openMobileTask}
                    revealedMobileStopIds={revealedMobileStopIds}
                    showMobileTranslations={showMobileTranslations}
                    targetVocabulary={targetVocabulary}
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
                      onOpenMobileTask={openMobileTask}
                      revealedMobileStopIds={revealedMobileStopIds}
                      showMobileTranslations={showMobileTranslations}
                      targetVocabulary={targetVocabulary}
                      readFirst={false}
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
                        onOpenMobileTask={openMobileTask}
                        revealed={revealedMobileStopIds.includes(panelTaskStop(panel, []).id)}
                        showMobileTranslations={showMobileTranslations}
                        targetVocabulary={targetVocabulary}
                        readFirst={false}
                      />
                    ))}
                  </section>
                )}
                {!serialReadFirst && <SceneBrief scene={scene} threadContext={visibleThreadContext} />}
                <EpisodeAudioControls scene={scene} />
                {serialReadFirst ? (
                  <SerialFinalAct
                    scene={scene}
                    answers={answers}
                    setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                    onSubmit={submitTask}
                    submittingTask={submittingTask}
                    attemptsByTask={attemptsByTask}
                    onOpenMobileTask={openMobileTask}
                    targetVocabulary={targetVocabulary}
                  />
                ) : (
                  <>
                    <FinalTask
                      scene={scene}
                      answers={answers}
                      setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                      onSubmit={submitTask}
                      submittingTask={submittingTask}
                      attemptsByTask={attemptsByTask}
                      targetVocabulary={targetVocabulary}
                    />
                    <MobileFinalTaskCard
                      scene={scene}
                      attemptsByTask={attemptsByTask}
                      onOpenMobileTask={openMobileTask}
                    />
                  </>
                )}
                <FeuilletonCliffhangerHero scene={scene} />
                <PostSceneVocabularySummary scene={scene} vocabulary={targetVocabulary} />
                {!scene.serial_thread_id && (
                  <FeuilletonContinuationCard scene={scene} vocabulary={targetVocabulary} />
                )}
                <MobileCompletionCard
                  scene={scene}
                  submittedCount={mobileSubmittedCount}
                  taskCount={mobileCountableTasks.length}
                  onComplete={async () => {
                    if (scene.status !== 'completed') {
                      await completeScene();
                      return;
                    }
                    await writeSideQuestProgressFlag('feuilletonDone');
                    void router.push('/atelier');
                  }}
                  completing={completing}
                />
                <div className="complete-row">
                  <Link className="btn" href="/atelier">
                    BACK TO TODAY <ArrowRight size={14} />
                  </Link>
                  <button className="btn solid lg" disabled={completing || scene.status === 'completed'} onClick={completeScene}>
                    {scene.status === 'completed' ? 'FEUILLETON COMPLETE' : 'COMPLETE FEUILLETON'} <Check size={15} />
                  </button>
                </div>
                <MobileTaskFlyIn
                  task={mobileTaskFlyoutOpen ? activeMobileTask : null}
                  stop={activeMobileTaskStop}
                  answers={answers}
                  setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                  onSubmit={submitTask}
                  submittingTask={submittingTask}
                  attemptsByTask={attemptsByTask}
                  recentCorrection={lastCorrection}
                  submitError={taskSubmitError}
                  onClose={closeMobileTaskFlyout}
                  onOpenTask={openMobileTask}
                  nextTaskId={nextMobileTaskId}
                  targetVocabulary={targetVocabulary}
                />
                <MobileReadingBar
                  panelCount={(scene.panels || []).length}
                  submittedCount={mobileSubmittedCount}
                  taskCount={mobileCountableTasks.length}
                  nextTaskId={nextMobileTaskId}
                  onOpenTask={() => openMobileTask(nextMobileTaskId, { scroll: true })}
                  onExit={() => {
                    void router.push('/atelier');
                  }}
                />
              </>
            ) : (
              <FeuilletonEmptyState
                creating={creating}
                onCreate={() => createScene()}
                today={today}
                threadContext={visibleThreadContext}
              />
            )}
          </section>

          <aside className="fn-side">
            <QueueCard today={today} scene={scene} onSelect={setScene} />
            <TargetCard scene={scene} tasks={tasks} attemptsByTask={attemptsByTask} />
            <CorrectionStack scene={scene} correction={lastCorrection} />
          </aside>
        </div>
      </main>
    </>
  );
}

function MobileCorrectionNote({ correction }: { correction: Record<string, any> | null }) {
  if (!correction) return null;
  const verdict = String(correction.verdict || 'submitted').replace(/_/g, ' ');
  const isPositive = correctionIsPositive(correction);
  const errataCount = Array.isArray(correction.errata) ? correction.errata.length : 0;
  const targetSentence = correction.corrected_answer || correction.target_sentence;
  return (
    <div className={`mobile-correction-note ${isPositive ? 'positive' : ''}`} role="status">
      <strong>{isPositive ? <Check size={14} /> : <X size={14} />}{isPositive ? 'Accepted' : verdict}</strong>
      {targetSentence && !isPositive && <span><b>Target.</b> {targetSentence}</span>}
      {correction.repair ? <span>{correction.repair}</span> : correction.why ? <span>{correction.why}</span> : <span>Feedback saved.</span>}
      <VocabularyCreditBadge correction={correction} compact labelMode="word" labelPrefix="Vocabulary · " />
      {!isPositive && <em>+{errataCount || 1} erratum</em>}
    </div>
  );
}

function MobileTaskFlyIn({
  task,
  stop,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  recentCorrection,
  submitError,
  onClose,
  onOpenTask,
  nextTaskId,
  targetVocabulary,
}: {
  task: OverlayTask | null;
  stop: MobileTaskStop | null;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  recentCorrection: Record<string, any> | null;
  submitError: TaskSubmitError;
  onClose: () => void;
  onOpenTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  nextTaskId: string | null;
  targetVocabulary: FeuilletonVocabularyItem[];
}) {
  if (!task?.id || !stop) return null;
  const taskId = String(task.id);
  const attempt = attemptsByTask[task.id];
  const recentTaskCorrection = recentCorrection && String(recentCorrection.task_id || '') === taskId ? recentCorrection : null;
  const visibleCorrection = attempt?.correction || recentTaskCorrection;
  const nextInStop = stop.tasks.find((item) => item.id && !attemptsByTask[item.id] && String(item.id) !== taskId);
  const nextTask = nextInStop || (nextTaskId && nextTaskId !== taskId ? { id: nextTaskId } as OverlayTask : null);
  return (
    <MobileBottomSheet
      as="aside"
      ariaLabel="Story task"
      onClose={onClose}
      eyebrow={stop.label}
      title={stop.title}
      description={stop.subtitle}
      displayTitle={false}
      closeLabel="Close task"
      sheetClassName="mobile-task-flyin"
    >
        <div className="mobile-task-sheet-status" aria-live="polite">
          <span>{attempt ? 'Submitted' : 'Panel repair'}</span>
          <strong>{attempt ? taskSheetFeedbackTitle(visibleCorrection) : 'Answer at this story moment'}</strong>
        </div>
        <MobileCorrectionNote correction={visibleCorrection} />
        <TaskControls
          task={task}
          value={answers[task.id] || ''}
          setValue={(value) => setAnswer(task.id, value)}
          onSubmit={() => onSubmit(task)}
          submitting={submittingTask === task.id}
          attempt={attempt}
          targetVocabulary={targetVocabulary}
        />
        {submitError?.taskId === taskId && (
          <div className="mobile-submit-error" role="status">
            <span>{submitError.message}</span>
            <button type="button" onClick={() => onSubmit(task)}>Retry</button>
          </div>
        )}
        <footer>
          <button type="button" onClick={() => scrollToFeuilletonSection(stop.elementId)}>Story moment</button>
          <button type="button" disabled={!nextTask?.id} onClick={() => onOpenTask(String(nextTask?.id || ''), { scroll: true })}>
            Next task
          </button>
        </footer>
    </MobileBottomSheet>
  );
}

function MobileStoryTaskLauncher({
  stop,
  attemptsByTask,
  onOpenMobileTask,
  revealed,
}: {
  stop: MobileTaskStop;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  revealed: boolean;
}) {
  const validTasks = stop.tasks.filter((task) => task.id);
  if (!validTasks.length) return null;
  const pending = validTasks.filter((task) => !attemptsByTask[task.id]).length;
  const reviewed = validTasks.length - pending;
  const firstTask = validTasks.find((task) => !attemptsByTask[task.id]) || validTasks[0];
  const launcherCopy = mobileTaskLauncherCopy(validTasks, attemptsByTask);
  return (
    <button
      className={`mobile-story-task-launcher ${pending ? '' : 'complete'} ${revealed ? 'revealed' : ''}`}
      aria-hidden={!revealed}
      aria-label={`${stop.label} story task sheet`}
      tabIndex={revealed ? 0 : -1}
      type="button"
      onClick={() => onOpenMobileTask(String(firstTask?.id || ''), { scroll: false })}
    >
      <span>{stop.label} · {reviewed}/{validTasks.length} reviewed</span>
      <strong>{launcherCopy.title}</strong>
      <small>{launcherCopy.detail}</small>
    </button>
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
  const visualTarget = renderMode === 'page' ? 'a full comic page' : `${panelCount} image panels`;
  return (
    <section className="paper generation-progress" aria-live="polite">
      <Loader2 className="spin" size={18} />
      <div>
        <strong>Writing the gag, then generating {visualTarget}</strong>
        <p>The image model is the slow part. {imageQuality} quality stays on so the reading panels remain legible.</p>
        <div className="mobile-generation-steps" aria-label="Generation progress">
          <span className="active">Script</span>
          <span className="active">Panels</span>
          <span>Tasks</span>
        </div>
        <p className="mobile-generation-note">Keep this screen open. Panel task buttons appear only after a real scene exists.</p>
      </div>
    </section>
  );
}

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
    ? 'Atelier thread ready'
    : recommendation?.reason
      ? 'Current-events seed ready'
      : 'Optional reading mode';
  const seedCopy = threadContext?.summary
    || recommendation?.reason
    || 'Create an edition when you want a short reading break. Until panels exist, there is no task sheet to open.';
  return (
    <section className="paper empty-state feuilleton-empty-state" data-feuilleton-empty="true" aria-label="Feuilleton empty state">
      <div className="empty-state-copy">
        <span className="t-mono">{seedLabel}</span>
        <h2>No scene on the stand.</h2>
        <p>{seedCopy}</p>
      </div>
      <div className="mobile-empty-task-note" role="note">
        <strong>Task sheet locked</strong>
        <span>Panel tasks unlock below the episode panels after the edition is generated.</span>
      </div>
      <button className="btn red" disabled={creating} onClick={onCreate}>
        {creating ? <Loader2 className="spin" size={14} /> : null}
        {creating ? 'CREATING SCENE' : 'CREATE FIRST SCENE'} <ArrowRight size={14} />
      </button>
    </section>
  );
}

function MobileReadingBar({
  panelCount,
  submittedCount,
  taskCount,
  nextTaskId,
  onOpenTask,
  onExit,
}: {
  panelCount: number;
  submittedCount: number;
  taskCount: number;
  nextTaskId: string | null;
  onOpenTask: () => void;
  onExit: () => void;
}) {
  const hasPendingTask = Boolean(nextTaskId) && submittedCount < taskCount;
  return (
    <nav className="mobile-reading-bar" aria-label="Feuilleton reading actions">
      <button type="button" onClick={onExit}>
        <X size={12} /> Exit
      </button>
      <div>
        <span className="t-mono-low">Reading · {panelCount} panels</span>
        <strong>{taskCount ? `${submittedCount}/${taskCount} tasks` : 'Reading only'}</strong>
      </div>
      <button className="primary" type="button" disabled={!hasPendingTask} onClick={onOpenTask}>
        {hasPendingTask ? 'Task' : 'Done'} <ArrowRight size={12} />
      </button>
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
  onOpenMobileTask,
  revealedMobileStopIds,
  showMobileTranslations,
  targetVocabulary,
}: {
  scene: GraphicNovelScene;
  readerMode: 'vertical' | 'page';
  setReaderMode: (mode: 'vertical' | 'page') => void;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  revealedMobileStopIds: string[];
  showMobileTranslations: boolean;
  targetVocabulary: FeuilletonVocabularyItem[];
}) {
  const hasComicPage = Boolean(scene.script_payload?.page_image?.url || scene.script_payload?.render_mode === 'page');
  const activeMode = hasComicPage ? readerMode : 'vertical';
  return (
    <section className="serial-reader s-feuil" id="reading-panels" aria-label="Serial episode reader">
      <SerialReaderMast scene={scene} />
      {hasComicPage && (
        <div className="serial-reader-toggle" role="tablist" aria-label="Reader mode">
          <button
            aria-selected={activeMode === 'vertical'}
            className={activeMode === 'vertical' ? 'active' : ''}
            onClick={() => setReaderMode('vertical')}
            role="tab"
            type="button"
          >
            Vertical
          </button>
          <button
            aria-selected={activeMode === 'page'}
            className={activeMode === 'page' ? 'active' : ''}
            onClick={() => setReaderMode('page')}
            role="tab"
            type="button"
          >
            Comic page
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
          onOpenMobileTask={onOpenMobileTask}
          revealedMobileStopIds={revealedMobileStopIds}
          showMobileTranslations={showMobileTranslations}
          targetVocabulary={targetVocabulary}
          readFirst
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
              onOpenMobileTask={onOpenMobileTask}
              revealed={revealedMobileStopIds.includes(panelTaskStop(panel, []).id)}
              showMobileTranslations={showMobileTranslations}
              targetVocabulary={targetVocabulary}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function SerialReaderMast({ scene }: { scene: GraphicNovelScene }) {
  const episodeNo = typeof scene.episode_index === 'number' ? scene.episode_index + 1 : 1;
  const loc = serialLocation(scene);
  const dateLabel = feuilletonEditionDate(scene) || 'Today';
  const news = serialNewsLine(scene);
  const previously = serialPreviouslyText(scene);
  return (
    <>
      <header className="s-mast serial-reader-mast">
        <div className="kicker">Le Feuilleton</div>
        <div className="title">{scene.title || 'The serial'}</div>
        <div className="dateline">
          <span>Épisode {episodeNo}</span>
          {loc && <><i /><span>{loc}</span></>}
          <i />
          <span>{dateLabel}</span>
        </div>
      </header>
      {news && (
        <aside className="s-news" data-char="romy">
          <span className="lbl">Cette semaine</span>
          <span className="txt">{news}</span>
        </aside>
      )}
      {previously && (
        <aside className="s-prev" aria-label="Previously on the serial">
          <div className="ph">
            <span className="tag">Previously on</span>
            <span className="tag stamp2">Ép. {Math.max(1, episodeNo - 1)}</span>
          </div>
          <div className="pb">{previously}</div>
        </aside>
      )}
    </>
  );
}

function SerialPanel({
  panel,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  onOpenMobileTask,
  revealed,
  showMobileTranslations,
  targetVocabulary,
}: {
  panel: GraphicNovelPanel;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  revealed: boolean;
  showMobileTranslations: boolean;
  targetVocabulary: FeuilletonVocabularyItem[];
}) {
  const overlay = panel.overlay_payload || {};
  const tasks = ((overlay.tasks || []) as OverlayTask[]).map((task) => ({ ...task, panel }));
  const stop = panelTaskStop(panel, tasks);
  const caption = overlay.caption || {};
  const bubbles = (overlay.bubbles || []) as PanelBubble[];
  const panelVocabulary = panelVocabularyMatches(panel, tasks, targetVocabulary);
  const imageUrl = panelImageUrl(panel);
  const isQueuedArt = !imageUrl && panel.generation_metadata?.image_status === 'queued';
  const shouldUseFallback = isFallbackPanel(panel) || !imageUrl;
  const who = serialPanelCharacter(panel);
  const captionText = String(caption.fr || panel.beat || '').trim();
  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.34, delay: (panel.panel_index || 1) * 0.05 }}
      className="s-panel serial-panel"
      data-char={who}
      data-mobile-task-stop={stop.id}
      id={stop.elementId}
    >
      <div className={`s-art ${shouldUseFallback ? 'fallback-panel' : 'generated-panel'}`}>
        {shouldUseFallback ? (
          <ComicFallbackPanel panel={panel} queued={isQueuedArt} />
        ) : (
          <Image
            src={imageUrl}
            alt=""
            fill
            sizes="(max-width: 760px) calc(100vw - 36px), 720px"
            unoptimized
          />
        )}
        <span className="frame-note">{serialPanelFrame(panel)}</span>
        <BubbleOverlay bubbles={bubbles} showMobileTranslations={showMobileTranslations} />
      </div>
      {captionText && (
        <div className="s-cap">
          <span className="n">{String(panel.panel_index || 1).padStart(2, '0')}</span>
          <span className="c">{captionText}</span>
        </div>
      )}
      <PanelVocabularyMarker items={panelVocabulary} />
      {bubbles.some((bubble) => bubble?.fr) && (
        <details className="mobile-panel-dialogue serial-dialogue">
          <summary>Dialogue transcript</summary>
          <BubbleTranscript bubbles={bubbles} showMobileTranslations={showMobileTranslations} />
        </details>
      )}
      {caption.en && (
        <details className={`caption-translation serial-caption-translation ${showMobileTranslations ? 'mobile-en-visible' : ''}`} open={showMobileTranslations || undefined}>
          <summary>Translation</summary>
          <p className="caption-en">{caption.en}</p>
        </details>
      )}
      <SerialTaskEmbed
        stop={stop}
        tasks={tasks}
        answers={answers}
        setAnswer={setAnswer}
        onSubmit={onSubmit}
        submittingTask={submittingTask}
        attemptsByTask={attemptsByTask}
        onOpenMobileTask={onOpenMobileTask}
        revealed={revealed}
        targetVocabulary={targetVocabulary}
      />
    </motion.article>
  );
}

function SerialTaskEmbed({
  stop,
  tasks,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  onOpenMobileTask,
  revealed,
  targetVocabulary,
}: {
  stop: MobileTaskStop;
  tasks: OverlayTask[];
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  revealed: boolean;
  targetVocabulary: FeuilletonVocabularyItem[];
}) {
  const validTasks = tasks.filter((task) => task.id);
  if (!validTasks.length) return null;
  const firstTask = validTasks[0];
  return (
    <div className="s-fork serial-act">
      <div className="fh">
        <span className="s-ava sm" data-char="toi">T</span>
        <span className="q"><b>You write the next line.</b> {serialTaskPrompt(firstTask)}</span>
      </div>
      <MobileStoryTaskLauncher stop={stop} attemptsByTask={attemptsByTask} onOpenMobileTask={onOpenMobileTask} revealed={revealed} />
      <div className="serial-act-body">
        {validTasks.map((task) => (
          <TaskControls
            key={task.id}
            task={task}
            value={answers[task.id] || ''}
            setValue={(value) => setAnswer(task.id, value)}
            onSubmit={() => onSubmit(task)}
            submitting={submittingTask === task.id}
            attempt={attemptsByTask[task.id]}
            targetVocabulary={targetVocabulary}
          />
        ))}
      </div>
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
  onOpenMobileTask,
  targetVocabulary,
}: {
  scene: GraphicNovelScene;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  targetVocabulary: FeuilletonVocabularyItem[];
}) {
  const task = finalSceneTask(scene);
  if (!task?.id) return null;
  const stop = finalTaskStop(scene, task);
  return (
    <section className="s-fork serial-final-act" id={stop.elementId} data-mobile-task-stop={stop.id} aria-label="Final serial act">
      <div className="fh">
        <span className="s-ava sm" data-char="toi">T</span>
        <span className="q"><b>You write the next line.</b> {serialTaskPrompt(task)}</span>
      </div>
      <MobileStoryTaskLauncher stop={stop} attemptsByTask={attemptsByTask} onOpenMobileTask={onOpenMobileTask} revealed />
      <div className="serial-act-body">
        <TaskControls
          task={task}
          value={answers[task.id] || ''}
          setValue={(value) => setAnswer(task.id, value)}
          onSubmit={() => onSubmit(task)}
          submitting={submittingTask === task.id}
          attempt={attemptsByTask[task.id]}
          targetVocabulary={targetVocabulary}
        />
      </div>
    </section>
  );
}

function MobileCompletionCard({
  scene,
  submittedCount,
  taskCount,
  onComplete,
  completing,
}: {
  scene: GraphicNovelScene;
  submittedCount: number;
  taskCount: number;
  onComplete: () => void | Promise<void>;
  completing: boolean;
}) {
  const panelCount = (scene.panels || []).length;
  const allTasksDone = taskCount === 0 || submittedCount >= taskCount;
  if (!panelCount || !allTasksDone) return null;
  const filed = scene.status === 'completed';
  return (
    <section className="paper mobile-completion-card" aria-label="Feuilleton completion">
      <span className="t-mono">{filed ? 'Edition filed' : 'Ready to file'}</span>
      <h3>{filed ? 'All panels saved.' : 'All panels read.'}</h3>
      <div className="mobile-completion-stats">
        <div>
          <strong>{panelCount}/{panelCount}</strong>
          <span>panels read</span>
        </div>
        <div>
          <strong>{taskCount ? `${submittedCount}/${taskCount}` : '0'}</strong>
          <span>{taskCount ? 'tasks done' : 'panel tasks'}</span>
        </div>
      </div>
      <p><b>Takeaway.</b> {completionTakeaway(scene)}</p>
      <button className="btn solid" type="button" disabled={completing} onClick={onComplete}>
        {filed ? 'Back to Atelier' : completing ? 'Saving' : 'Complete and return'} <ArrowRight size={13} />
      </button>
    </section>
  );
}

function scrollToFeuilletonSection(id: string) {
  if (typeof document === 'undefined') return;
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function SceneBrief({ scene, threadContext }: { scene: GraphicNovelScene; threadContext: FeuilletonThreadContext }) {
  const source = scene.source_snapshot || {};
  const sourceItem = (source.items || [])[0] || {};
  const showSource = Boolean(source.mode && source.mode !== 'atelier_curated' && (source.title || sourceItem.title));
  const imageStatus = sceneImageStatus(scene);
  const script = scene.script_payload || {};
  const cost = script.estimated_cost || {};
  const sourceCopy = feuilletonSourceCopy(source, script);
  const publicBrief = feuilletonPublicBrief(scene.brief);
  const targetVocabulary = sceneTargetVocabulary(scene);
  const isSerial = Boolean(scene.serial_thread_id);
  return (
    <section className="paper scene-brief">
      {!isSerial && (
        <div className="kicker">
          <span>{scene.cadence}</span>
          {script.panel_count && <span>{script.panel_count} panels</span>}
          {script.experience_mode && <span>{script.experience_mode}</span>}
          {script.render_mode && <span>{script.render_mode}</span>}
          {script.image_quality && <span>{script.image_quality} image</span>}
          {script.story_quality && <span>{script.story_quality} story</span>}
          {cost.total_estimated_usd && <span>~${Number(cost.total_estimated_usd).toFixed(2)}</span>}
          <span className={imageStatus.isFallback ? 'fallback' : ''}>{imageStatus.label}</span>
        </div>
      )}
      <h2>{scene.title}</h2>
      {scene.status === 'generating' && (
        <div className="edition-printing" role="status">
          <Loader2 className="spin" size={14} />
          <span>The script is readable now. The art is arriving panel by panel.</span>
        </div>
      )}
      <EditionMeta scene={scene} sourceCopy={sourceCopy} isSerial={isSerial} />
      {!isSerial && <TodayThreadBanner context={threadContext} />}
      {isSerial && <SerialPreviously scene={scene} />}
      {!isSerial && publicBrief && <p>{publicBrief}</p>}
      <FeuilletonVocabularyStrip vocabulary={targetVocabulary} />
      {showSource && (
        isSerial ? (
          <div className="source-card compact-source">
            <span className="t-mono">ACTUALITÉ</span>
            <strong>{sourceCopy.titleFr}</strong>
            <div className="source-meta">
              <span>{source.source || sourceItem.source || 'Source'}</span>
              {(source.url || sourceItem.url) && <a href={source.url || sourceItem.url} target="_blank" rel="noreferrer">Source</a>}
            </div>
          </div>
        ) : (
          <div className="source-card">
            <div className="t-mono">ACTUALITÉ</div>
            <strong>{sourceCopy.titleFr}</strong>
            <p>{sourceCopy.summaryFr}</p>
            {(sourceCopy.titleEn || sourceCopy.summaryEn) && (
              <details className="source-translation">
                <summary>English</summary>
                {sourceCopy.titleEn && <strong>{sourceCopy.titleEn}</strong>}
                {sourceCopy.summaryEn && <p>{sourceCopy.summaryEn}</p>}
              </details>
            )}
            <div className="source-meta">
              <span>{source.source || sourceItem.source || 'Source'}</span>
              {(source.url || sourceItem.url) && <a href={source.url || sourceItem.url} target="_blank" rel="noreferrer">Ouvrir la source ↗</a>}
            </div>
          </div>
        )
      )}
    </section>
  );
}

function TodayThreadBanner({ context }: { context: FeuilletonThreadContext }) {
  if (!context) return null;
  return (
    <aside className="today-thread-banner" aria-label="Today's Thread context">
      <div>
        <span className="t-mono">Today&apos;s Thread</span>
        <strong>Scene seeded from Atelier</strong>
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

function EditionMeta({
  scene,
  sourceCopy,
  isSerial = false,
}: {
  scene: GraphicNovelScene;
  sourceCopy: ReturnType<typeof feuilletonSourceCopy>;
  isSerial?: boolean;
}) {
  const source = scene.source_snapshot || {};
  const dateLabel = feuilletonEditionDate(scene);
  const synopsis = feuilletonSynopsis(scene, sourceCopy);
  if (isSerial) {
    // Reader-facing serial: a clean dateline only — no issue hash, no spoiler synopsis.
    const episodeIndex = typeof scene.episode_index === 'number' ? scene.episode_index : null;
    return (
      <div className="edition-meta" aria-label="Edition">
        <div>
          <Link href="/serial">Season 1</Link>
          {episodeIndex !== null && <Link href={`/serial/episode/${episodeIndex}`}>Épisode {episodeIndex + 1}</Link>}
          {dateLabel && <span>{dateLabel}</span>}
        </div>
      </div>
    );
  }
  return (
    <div className="edition-meta" aria-label="Edition metadata">
      <div>
        <span>Issue {feuilletonIssueNumber(scene)}</span>
        {dateLabel && <span>{dateLabel}</span>}
        {(source.source || source.mode) && <span>{source.source || source.mode}</span>}
      </div>
      {synopsis && <p><b>Synopsis.</b> {synopsis}</p>}
    </div>
  );
}

function SerialPreviously({ scene }: { scene: GraphicNovelScene }) {
  const serialContext = (scene.script_payload || {}).serial_context || {};
  const previously = (serialContext.hook_from_previous || {}).text
    || (scene.source_snapshot || {}).previously
    || null;
  if (!previously || typeof previously !== 'string') return null;
  return (
    <aside className="serial-previously" aria-label="Previously">
      <span className="t-mono-low">Previously</span>
      <p>{previously}</p>
      <style jsx>{`
        .serial-previously { display: grid; gap: 4px; margin: 2px 0 4px; padding-left: 11px; border-left: 3px solid var(--char-romy, var(--blue, #1d3a8a)); }
        .serial-previously .t-mono-low { font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--char-romy, var(--blue, #1d3a8a)); }
        .serial-previously p { margin: 0; font-style: italic; line-height: 1.4; color: var(--ink-2, #4a4538); }
      `}</style>
    </aside>
  );
}

function FeuilletonVocabularyStrip({ vocabulary }: { vocabulary: FeuilletonVocabularyItem[] }) {
  const items = vocabulary.filter((item) => item.word).slice(0, 4);
  if (!items.length) return null;
  return (
    <details className="feuilleton-vocabulary-strip" aria-label="Target vocabulary">
      <summary>
        <span className="t-mono">{items.length} mots en jeu</span>
        <strong>{items.map((item) => item.word).join(' · ')}</strong>
      </summary>
      <div>
        {items.map((item) => (
          <Link
            key={vocabularyItemKey(item)}
            href={vocabularyDetailHref(item)}
            title={`Open ${item.word} in the vocabulary notebook`}
          >
            <span>{vocabularySourceLabel(item)}</span>
            <strong>{item.word}</strong>
            {item.translation && <em>{item.translation}</em>}
          </Link>
        ))}
      </div>
    </details>
  );
}

function PanelVocabularyMarker({ items }: { items: FeuilletonVocabularyItem[] }) {
  if (!items.length) return null;
  return (
    <div className="context-vocabulary-marker" aria-label="Vocabulary context markers">
      <span>Context</span>
      {items.slice(0, 2).map((item) => (
        <Link key={vocabularyItemKey(item)} href={vocabularyDetailHref(item)}>
          <strong>{item.word}</strong>
          <em>{vocabularySourceLabel(item)}</em>
        </Link>
      ))}
    </div>
  );
}

function TaskVocabularyMarker({ items }: { items: FeuilletonVocabularyItem[] }) {
  if (!items.length) return null;
  return (
    <div className="task-vocabulary-marker" aria-label="Task vocabulary source">
      {items.slice(0, 1).map((item) => (
        <Link key={vocabularyItemKey(item)} href={vocabularyDetailHref(item)}>
          <span>{vocabularySourceLabel(item)}</span>
          <strong>{item.word}</strong>
          {item.translation && <em>{item.translation}</em>}
        </Link>
      ))}
    </div>
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
  const delayed = failure?.code === 'serial_edition_delayed';
  return (
    <section className="paper edition-preparing">
      <div>
        <div className="t-mono">{delayed ? 'TOMORROW’S EDITION' : 'TODAY’S EDITION'}</div>
        <h2>{delayed ? "L'édition de demain est retardée." : 'No complete edition returned.'}</h2>
        <p>{delayed ? 'The story desk did not have a live writer, so the serial paused instead of replaying old radiator copy.' : 'This state is reserved for hard service failures, not a quality judgment. Try again, or continue in Atelier while the image service catches up.'}</p>
      </div>
      <div className="edition-actions">
        <button className="btn red" disabled={creating} onClick={onRetry}>
          {creating ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
          TRY AGAIN
        </button>
        <Link className="btn solid" href="/grammar">OPEN NOTEBOOK <ArrowRight size={13} /></Link>
        <Link className="btn" href="/atelier">BACK TO ATELIER <ArrowRight size={13} /></Link>
      </div>
    </section>
  );
}

function PageScene({
  scene,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  onOpenMobileTask,
  revealedMobileStopIds,
  showMobileTranslations,
  targetVocabulary,
  readFirst = false,
}: {
  scene: GraphicNovelScene;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  revealedMobileStopIds: string[];
  showMobileTranslations: boolean;
  targetVocabulary: FeuilletonVocabularyItem[];
  readFirst?: boolean;
}) {
  const pageImage = scene.script_payload?.page_image;
  const pageFallback = Boolean(pageImage?.fallback_used);
  const fallbackPanel = (scene.panels || [])[0] || {
    id: 'fallback-page',
    panel_index: 1,
    title: 'Fallback page',
    beat: '',
    image_prompt: '',
    image_payload: {},
    overlay_payload: {},
    generation_metadata: {},
  };
  return (
    <section className="page-scene">
      <article className="paper comic-page-card">
        <div className={`comic-page-image ${pageFallback ? 'fallback-panel' : ''}`}>
          {pageImage?.url ? (
            <Image
              src={pageImage.url}
              alt=""
              width={1400}
              height={1980}
              sizes="(max-width: 760px) calc(100vw - 44px), 900px"
              unoptimized
            />
          ) : <ComicFallbackPanel panel={fallbackPanel as GraphicNovelPanel} />}
        </div>
        <div className="comic-page-caption">
          <span className="t-mono">COMIC PAGE</span>
          <p>Dialogue and exercises stay in Atelier overlays so the page can remain visually clean and reliable.</p>
        </div>
      </article>
      <section className="annotation-grid">
        {(scene.panels || []).map((panel) => (
          <PanelAnnotation
            key={panel.id}
            panel={panel}
            answers={answers}
            setAnswer={setAnswer}
            onSubmit={onSubmit}
            submittingTask={submittingTask}
            attemptsByTask={attemptsByTask}
            onOpenMobileTask={onOpenMobileTask}
            revealed={revealedMobileStopIds.includes(panelTaskStop(panel, []).id)}
            showMobileTranslations={showMobileTranslations}
            targetVocabulary={targetVocabulary}
            readFirst={readFirst}
          />
        ))}
      </section>
    </section>
  );
}

function PanelAnnotation({
  panel,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  onOpenMobileTask,
  revealed,
  showMobileTranslations,
  targetVocabulary,
  readFirst = false,
}: {
  panel: GraphicNovelPanel;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  revealed: boolean;
  showMobileTranslations: boolean;
  targetVocabulary: FeuilletonVocabularyItem[];
  readFirst?: boolean;
}) {
  const overlay = panel.overlay_payload || {};
  const tasks = (overlay.tasks || []) as OverlayTask[];
  const mobileTasks: OverlayTask[] = tasks.map((task) => ({ ...task, panel }));
  const stop = panelTaskStop(panel, mobileTasks);
  const caption = overlay.caption || {};
  const bubbles = (overlay.bubbles || []) as PanelBubble[];
  const panelVocabulary = panelVocabularyMatches(panel, mobileTasks, targetVocabulary);
  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: (panel.panel_index || 1) * 0.08 }}
      className="paper panel-annotation"
      id={readFirst ? `reading-${stop.elementId}` : stop.elementId}
      data-mobile-task-stop={readFirst ? undefined : stop.id}
    >
      <div className="panel-head">
        <span className="t-mono">PANEL {panel.panel_index}</span>
        <strong>{panel.title}</strong>
        <PanelAudioButton panel={panel} />
      </div>
      <PanelVocabularyMarker items={panelVocabulary} />
      <BubbleTranscript bubbles={bubbles} showMobileTranslations={showMobileTranslations} />
      {caption.fr ? (
        <CaptionBlock caption={caption} showMobileTranslations={showMobileTranslations} />
      ) : (
        <p>{panel.beat}</p>
      )}
      {readFirst ? (
        <PanelInlineTaskDisclosure
          stop={stop}
          tasks={mobileTasks}
          answers={answers}
          setAnswer={setAnswer}
          onSubmit={onSubmit}
          submittingTask={submittingTask}
          attemptsByTask={attemptsByTask}
          targetVocabulary={targetVocabulary}
        />
      ) : (
        <>
          <MobileStoryTaskLauncher stop={stop} attemptsByTask={attemptsByTask} onOpenMobileTask={onOpenMobileTask} revealed={revealed} />
          {mobileTasks.map((task) => (
            <TaskControls
              key={task.id}
              task={task}
              value={answers[task.id] || ''}
              setValue={(value) => setAnswer(task.id, value)}
              onSubmit={() => onSubmit(task)}
              submitting={submittingTask === task.id}
              attempt={attemptsByTask[task.id]}
              targetVocabulary={targetVocabulary}
            />
          ))}
        </>
      )}
    </motion.article>
  );
}

function PanelCard({
  panel,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  onOpenMobileTask,
  revealed,
  showMobileTranslations,
  targetVocabulary,
  readFirst = false,
}: {
  panel: GraphicNovelPanel;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
  revealed: boolean;
  showMobileTranslations: boolean;
  targetVocabulary: FeuilletonVocabularyItem[];
  readFirst?: boolean;
}) {
  const overlay = panel.overlay_payload || {};
  const tasks = (overlay.tasks || []) as OverlayTask[];
  const mobileTasks: OverlayTask[] = tasks.map((task) => ({ ...task, panel }));
  const stop = panelTaskStop(panel, mobileTasks);
  const fallbackPanel = isFallbackPanel(panel);
  const caption = overlay.caption || {};
  const bubbles = (overlay.bubbles || []) as PanelBubble[];
  const panelVocabulary = panelVocabularyMatches(panel, mobileTasks, targetVocabulary);
  const imageUrl = panelImageUrl(panel);
  const isQueuedArt = !imageUrl && panel.generation_metadata?.image_status === 'queued';
  const shouldUseFallback = fallbackPanel || !imageUrl;
  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: (panel.panel_index || 1) * 0.08 }}
      className="panel-card"
      id={readFirst ? `reading-${stop.elementId}` : stop.elementId}
      data-mobile-task-stop={readFirst ? undefined : stop.id}
    >
      <div className={`panel-image ${shouldUseFallback ? 'fallback-panel' : 'generated-panel'}`}>
        {shouldUseFallback ? (
          <ComicFallbackPanel panel={panel} queued={isQueuedArt} />
        ) : (
          <Image
            src={imageUrl}
            alt=""
            fill
            sizes="(max-width: 760px) calc(100vw - 28px), 50vw"
            unoptimized
          />
        )}
        <BubbleOverlay bubbles={bubbles} showMobileTranslations={showMobileTranslations} />
      </div>
      <div className="panel-body">
        <div className="panel-head">
          <span className="t-mono">PANEL {panel.panel_index}</span>
          <strong>{panel.title}</strong>
          <PanelAudioButton panel={panel} />
        </div>
        <PanelVocabularyMarker items={panelVocabulary} />
        {bubbles.some((bubble) => bubble?.fr) && (
          <details className="mobile-panel-dialogue">
            <summary>Dialogue transcript</summary>
            <BubbleTranscript bubbles={bubbles} showMobileTranslations={showMobileTranslations} />
          </details>
        )}
      {caption.fr ? (
        <CaptionBlock caption={caption} showMobileTranslations={showMobileTranslations} />
      ) : (
        <p>{panel.beat}</p>
      )}
        {readFirst ? (
          <PanelInlineTaskDisclosure
            stop={stop}
            tasks={mobileTasks}
            answers={answers}
            setAnswer={setAnswer}
            onSubmit={onSubmit}
            submittingTask={submittingTask}
            attemptsByTask={attemptsByTask}
            targetVocabulary={targetVocabulary}
          />
        ) : (
          <>
            <MobileStoryTaskLauncher stop={stop} attemptsByTask={attemptsByTask} onOpenMobileTask={onOpenMobileTask} revealed={revealed} />
            {mobileTasks.map((task) => (
              <TaskControls
                key={task.id}
                task={task}
                value={answers[task.id] || ''}
                setValue={(value) => setAnswer(task.id, value)}
                onSubmit={() => onSubmit(task)}
                submitting={submittingTask === task.id}
                attempt={attemptsByTask[task.id]}
                targetVocabulary={targetVocabulary}
              />
            ))}
          </>
        )}
      </div>
    </motion.article>
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
      toast.error('Could not play this panel.');
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
      toast.error('Could not play the episode audio.');
    };
    setPlaying(true);
    await player.play();
  };

  return (
    <section className="paper episode-audio" aria-label="Episode audio">
      <div>
        <span className="t-mono">Audio edition</span>
        <strong>{audioPanels.length} panel{audioPanels.length === 1 ? '' : 's'} ready</strong>
      </div>
      <button type="button" onClick={() => playing ? stop() : void playFrom(0)}>
        {playing ? <Pause size={16} /> : <PlayCircle size={17} />}
        {playing ? 'Pause' : 'Lire l’épisode'}
      </button>
    </section>
  );
}

function ReadFirstTaskSection({
  scene,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  targetVocabulary,
}: {
  scene: GraphicNovelScene;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  targetVocabulary: FeuilletonVocabularyItem[];
}) {
  if (scene.script_payload?.experience_mode === 'reward') return null;
  const groups = (scene.panels || [])
    .map((panel) => {
      const tasks: OverlayTask[] = ((panel.overlay_payload?.tasks || []) as OverlayTask[])
        .map((task): OverlayTask => ({ ...task, panel }))
        .filter((task) => task.id && !attemptsByTask[task.id]);
      return { panel, tasks, stop: panelTaskStop(panel, tasks) };
    })
    .filter((group) => group.tasks.some((task) => task.id));
  if (!groups.length) return null;
  return (
    <section className="paper read-first-task-section" aria-label="Unfinished episode tasks">
      <div className="read-first-head">
        <span className="t-mono red">Encore à toi</span>
        <h3>Unfinished panel tasks.</h3>
        <p>Everything here is still anchored to its panel above; this is only the end-of-read catch-up list.</p>
      </div>
      <div className="read-first-groups">
        {groups.map(({ panel, tasks, stop }) => (
          <article key={stop.id} id={stop.elementId} data-mobile-task-stop={stop.id} className="read-first-group">
            <div className="panel-head">
              <span className="t-mono">PANEL {panel.panel_index}</span>
              <strong>{panel.title}</strong>
            </div>
            {tasks.map((task) => (
              <TaskControls
                key={task.id}
                task={task}
                value={answers[task.id] || ''}
                setValue={(value) => setAnswer(task.id, value)}
                onSubmit={() => onSubmit(task)}
                submitting={submittingTask === task.id}
                attempt={attemptsByTask[task.id]}
                targetVocabulary={targetVocabulary}
              />
            ))}
          </article>
        ))}
      </div>
    </section>
  );
}

function PanelInlineTaskDisclosure({
  stop,
  tasks,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  targetVocabulary,
}: {
  stop: MobileTaskStop;
  tasks: OverlayTask[];
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  targetVocabulary: FeuilletonVocabularyItem[];
}) {
  const validTasks = tasks.filter((task) => task.id);
  const [open, setOpen] = useState(false);
  const drawerId = `drawer-${stop.id}`;
  const pending = validTasks.filter((task) => !attemptsByTask[task.id]).length;
  const reviewed = validTasks.length - pending;
  useEffect(() => {
    const element = document.getElementById(drawerId);
    const listener = () => setOpen(true);
    element?.addEventListener('feuilleton-open-task-drawer', listener);
    return () => element?.removeEventListener('feuilleton-open-task-drawer', listener);
  }, [drawerId]);
  if (!validTasks.length) return null;
  const submit = (task: OverlayTask) => {
    setOpen(true);
    onSubmit(task);
    window.setTimeout(() => openNextPanelTaskDrawer(drawerId), 200);
  };
  return (
    <details
      id={drawerId}
      className="panel-task-drawer"
      data-panel-task-drawer="true"
      data-has-pending={pending > 0 ? 'true' : 'false'}
      open={open}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>
        <span>À toi — {pending > 0 ? `${pending} à faire` : 'fait'}</span>
        <small>{reviewed}/{validTasks.length}</small>
      </summary>
      <div className="panel-task-drawer-body">
        {validTasks.map((task) => (
          <TaskControls
            key={task.id}
            task={task}
            value={answers[task.id] || ''}
            setValue={(value) => setAnswer(task.id, value)}
            onSubmit={() => submit(task)}
            submitting={submittingTask === task.id}
            attempt={attemptsByTask[task.id]}
            targetVocabulary={targetVocabulary}
          />
        ))}
      </div>
    </details>
  );
}

function openNextPanelTaskDrawer(currentDrawerId: string) {
  if (typeof document === 'undefined') return;
  const drawers = Array.from(document.querySelectorAll<HTMLElement>('[data-panel-task-drawer="true"][data-has-pending="true"]'));
  const index = drawers.findIndex((drawer) => drawer.id === currentDrawerId);
  const next = drawers[index + 1];
  if (!next) return;
  next.dispatchEvent(new CustomEvent('feuilleton-open-task-drawer'));
}

function BubbleOverlay({ bubbles, showMobileTranslations }: { bubbles: PanelBubble[]; showMobileTranslations: boolean }) {
  const visible = bubbles.filter((bubble) => bubble?.fr);
  const [translated, setTranslated] = useState<Record<number, boolean>>({});
  if (!visible.length) return null;
  return (
    <div className="bubble-layer" aria-label="Panel dialogue">
      {visible.slice(0, 2).map((bubble, index) => {
        const who = panelBubbleCharacter(bubble);
        return (
        <button
          type="button"
          className={`speech-bubble bubble-${index + 1} tone-${bubble.tone || 'deadpan'}`}
          data-char={who}
          key={`${bubble.speaker || 'bubble'}-${index}`}
          aria-label={bubble.en ? `Toggle ${bubble.speaker || 'dialogue'} translation` : `${bubble.speaker || 'Dialogue'} bubble`}
          onClick={() => bubble.en && setTranslated((current) => ({ ...current, [index]: !current[index] }))}
          style={{
            left: `${clampPercent(bubble.x, index === 0 ? 12 : 54)}%`,
            top: `${clampPercent(bubble.y, index === 0 ? 12 : 28)}%`,
            borderColor: bubble.accent_color || bubble.accent_colour || undefined,
          }}
        >
          {bubble.speaker && <span>{bubble.speaker}</span>}
          <p>{(showMobileTranslations || translated[index]) && bubble.en ? bubble.en : bubble.fr}</p>
          {bubble.en && <small>{(showMobileTranslations || translated[index]) ? 'FR' : 'EN'}</small>}
        </button>
        );
      })}
    </div>
  );
}

function BubbleTranscript({ bubbles, showMobileTranslations }: { bubbles: PanelBubble[]; showMobileTranslations: boolean }) {
  const visible = bubbles.filter((bubble) => bubble?.fr);
  if (!visible.length) return null;
  return (
    <div className="bubble-transcript">
      {visible.map((bubble, index) => (
        <blockquote key={`${bubble.speaker || 'bubble'}-${index}`} data-char={panelBubbleCharacter(bubble)}>
          {bubble.speaker && <span>{bubble.speaker}</span>}
          <p>{bubble.fr}</p>
          {bubble.en && <small className={showMobileTranslations ? 'mobile-en-visible' : ''}>{bubble.en}</small>}
        </blockquote>
      ))}
    </div>
  );
}

function clampPercent(value: number | undefined, fallback: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return fallback;
  return Math.max(4, Math.min(64, value));
}

function CaptionBlock({ caption, showMobileTranslations }: { caption: any; showMobileTranslations: boolean }) {
  return (
    <div className="panel-caption">
      <p className="caption-fr">{caption.fr}</p>
      {caption.en && (
        <details className={`caption-translation ${showMobileTranslations ? 'mobile-en-visible' : ''}`} open={showMobileTranslations || undefined}>
          <summary>Translation</summary>
          <p className="caption-en">{caption.en}</p>
        </details>
      )}
    </div>
  );
}

function isFallbackPanel(panel: GraphicNovelPanel) {
  return Boolean(panel.generation_metadata?.fallback_used || panel.image_payload?.fallback_used || panel.image_payload?.model === 'atelier-svg-fallback');
}

function sceneImageStatus(scene: GraphicNovelScene) {
  if (scene.script_payload?.render_mode === 'page') {
    const pageImage = scene.script_payload?.page_image || {};
    const fallback = Boolean(pageImage.fallback_used);
    return { isFallback: fallback, label: `${scene.image_model} · ${scene.image_quality} · page${fallback ? ' fallback' : ''}` };
  }
  const panels = scene.panels || [];
  const fallbackCount = panels.filter(isFallbackPanel).length;
  if (fallbackCount > 0) {
    const suffix = panels.length ? `${fallbackCount}/${panels.length}` : 'local';
    return { isFallback: true, label: `LOCAL STORYBOARD FALLBACK · ${suffix}` };
  }
  return { isFallback: false, label: `${scene.image_model} · ${scene.image_quality}` };
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

function sourceTextLooksFrench(text: string) {
  return /[àâçéèêëîïôùûüÿœ]|(\b(le|la|les|des|une|un|et|dans|avec|pour|selon|annonce|présidentielle)\b)/i.test(text);
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

function visibleOpenTaskFeatures(task: Record<string, any>) {
  if (task.task_type !== 'short_sentence') return [];
  if (!Array.isArray(task.expected_features)) return [];
  return task.expected_features
    .map((item: unknown) => String(item || '').trim())
    .filter(Boolean)
    .filter((item: string) => !/(phrase compl[eè]te|complete sentence|prolongement humoristique|humou?r|ironie|irony|scene|sc[eè]ne|short sentence)/i.test(item))
    .slice(0, 3);
}

function displayTaskInstruction(task: Record<string, any>) {
  let instruction = String(task.instruction || '').trim();
  if (mentionsParentheses(instruction) && !hasParentheticalCue(task.prompt)) {
    instruction = 'Complétez la phrase avec la forme correcte.';
  }
  const openFeatures = visibleOpenTaskFeatures(task);
  if (openFeatures.length > 0 && !openFeatures.some((feature) => instruction.toLowerCase().includes(feature.toLowerCase()))) {
    instruction = `${instruction || 'Rédigez une phrase courte.'} Utilisez clairement : ${openFeatures.join(' · ')}.`;
  }
  return instruction || 'Complétez la tâche.';
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
  return correction?.verdict === 'correct' || correction?.verdict === 'accepted';
}

function taskSheetFeedbackTitle(correction: Record<string, any> | null | undefined) {
  if (!correction) return 'Answer saved';
  if (correctionIsPositive(correction)) return 'Accepted';
  return String(correction.verdict || 'Repair saved').replace(/_/g, ' ');
}

function mobileTaskLauncherCopy(tasks: OverlayTask[], attemptsByTask: Record<string, Record<string, any>>) {
  const pending = tasks.filter((task) => task.id && !attemptsByTask[task.id]).length;
  if (pending > 0) {
    return {
      title: `${pending} task${pending === 1 ? '' : 's'} here`,
      detail: 'Open task sheet',
    };
  }
  const needsRepair = tasks.some((task) => {
    const correction = attemptsByTask[task.id]?.correction;
    return correction && !correctionIsPositive(correction);
  });
  return {
    title: needsRepair ? 'Repair saved' : 'Task reviewed',
    detail: needsRepair ? 'Review correction' : 'Read feedback',
  };
}

function completionTakeaway(scene: GraphicNovelScene) {
  const grammarTarget = (scene.script_payload?.targets || []).find((target: any) => target.kind === 'grammar' && target.label);
  if (grammarTarget?.label) return `Watch for ${grammarTarget.label} when the scene pressure changes.`;
  const firstPanelTask = extractTasks(scene).find((task) => task.label || task.instruction);
  if (firstPanelTask?.label) return `Today's repair centered on ${firstPanelTask.label}.`;
  return 'Keep the French sentence anchored to the panel before adding the joke.';
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

function serialNewsLine(scene: GraphicNovelScene) {
  const source = scene.source_snapshot || {};
  const serialContext = scene.script_payload?.serial_context || {};
  const sourceUsage = scene.script_payload?.source_usage || {};
  const sourceCopy = feuilletonSourceCopy(source, scene.script_payload || {});
  return trimFeuilletonText(firstString(
    sourceUsage.romy_line,
    serialContext.news_line,
    source.news_line,
    sourceCopy.titleFr,
  ), 150);
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

function serialPanelFrame(panel: GraphicNovelPanel) {
  const overlay = panel.overlay_payload || {};
  const frame = firstString(overlay.frame, overlay.shot, panel.image_payload?.frame, panel.generation_metadata?.frame);
  if (frame) return frame;
  const prefix = `PANEL ${String(panel.panel_index || 1).padStart(2, '0')}`;
  return panel.title ? `${prefix} · ${panel.title}` : prefix;
}

function serialTaskPrompt(task: Record<string, any>) {
  return trimFeuilletonText(firstString(
    task.serial_prompt,
    task.scene_prompt,
    task.prompt_body,
    task.prompt,
    task.instruction,
    'Choose the line Toi says next.',
  ), 120);
}

function feuilletonSourceCopy(source: Record<string, any>, script: Record<string, any>) {
  const item = (source.items || [])[0] || {};
  const rawTitle = stripInternalSourceLanguage(source.title || item.title);
  const rawSummary = stripInternalSourceLanguage(source.summary || item.summary);
  const sourceUsage = script.source_usage || {};
  const titleFrSeed = stripInternalSourceLanguage(source.title_fr || item.title_fr || sourceUsage.title_fr);
  const summaryFrSeed = stripInternalSourceLanguage(source.summary_fr || item.summary_fr || sourceUsage.summary_fr);

  const titleFr = titleFrSeed || (sourceTextLooksFrench(rawTitle) ? rawTitle : rawTitle || 'L’actualité française du jour');
  const summaryFr = summaryFrSeed || (sourceTextLooksFrench(rawSummary)
    ? rawSummary
    : rawSummary || 'Cette édition part d’un sujet français récent et le transforme en scène satirique.');

  return {
    titleFr,
    summaryFr,
    titleEn: sourceTextLooksFrench(rawTitle) ? '' : rawTitle,
    summaryEn: sourceTextLooksFrench(rawSummary) ? '' : rawSummary,
  };
}

function ComicFallbackPanel({ panel, queued = false }: { panel: GraphicNovelPanel; queued?: boolean }) {
  const variant = ((panel.panel_index - 1) % 4) + 1;
  return (
    <div className={`comic-fallback comic-${variant} ${queued ? 'queued' : ''}`} aria-hidden={!queued}>
      <div className="comic-sun" />
      <div className="comic-window window-a" />
      <div className="comic-window window-b" />
      <div className="comic-awning" />
      <div className="comic-ground" />
      <div className="comic-table" />
      <div className="comic-phone" />
      <div className="comic-figure figure-a">
        <span className="head" />
        <span className="body" />
        <span className="arm arm-a" />
        <span className="arm arm-b" />
      </div>
      <div className="comic-figure figure-b">
        <span className="head" />
        <span className="body" />
        <span className="arm arm-a" />
        <span className="arm arm-b" />
      </div>
      <div className="comic-rain rain-a" />
      <div className="comic-rain rain-b" />
      <div className="comic-rain rain-c" />
      {queued && (
        <div className="queued-panel-copy">
          <span>At the printer</span>
          <p>{panel.beat}</p>
        </div>
      )}
    </div>
  );
}

function FinalTask({
  scene,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  targetVocabulary,
}: {
  scene: GraphicNovelScene;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  targetVocabulary: FeuilletonVocabularyItem[];
}) {
  const task = (scene.script_payload || {}).final_prompt;
  if (scene.script_payload?.experience_mode === 'reward') return null;
  if (!task?.id) return null;
  const instruction = displayTaskInstruction(task);
  return (
    <section className="paper final-task">
      <div>
        <div className="t-mono">FINAL LINE</div>
        <h3>Continue the scene</h3>
        <p>{instruction}</p>
      </div>
      <TaskControls
        task={task}
        value={answers[task.id] || ''}
        setValue={(value) => setAnswer(task.id, value)}
        onSubmit={() => onSubmit(task)}
        submitting={submittingTask === task.id}
        attempt={attemptsByTask[task.id]}
        targetVocabulary={targetVocabulary}
      />
    </section>
  );
}

function MobileFinalTaskCard({
  scene,
  attemptsByTask,
  onOpenMobileTask,
}: {
  scene: GraphicNovelScene;
  attemptsByTask: Record<string, Record<string, any>>;
  onOpenMobileTask: (taskId?: string | null, options?: { scroll?: boolean }) => void;
}) {
  const task = finalSceneTask(scene);
  if (!task?.id) return null;
  const stop = finalTaskStop(scene, task);
  const instruction = displayTaskInstruction(task);
  return (
    <section className="paper mobile-final-task-card" id={stop.elementId} data-mobile-task-stop={stop.id} aria-label="Final Feuilleton task">
      <div>
        <span className="t-mono">Final line</span>
        <h3>Finish the scene</h3>
        <p>{instruction}</p>
      </div>
      <MobileStoryTaskLauncher
        stop={stop}
        attemptsByTask={attemptsByTask}
        onOpenMobileTask={onOpenMobileTask}
        revealed
      />
    </section>
  );
}

function TaskControls({
  task,
  value,
  setValue,
  onSubmit,
  submitting,
  attempt,
  targetVocabulary = [],
}: {
  task: OverlayTask;
  value: string;
  setValue: (value: string) => void;
  onSubmit: () => void;
  submitting: boolean;
  attempt?: Record<string, any>;
  targetVocabulary?: FeuilletonVocabularyItem[];
}) {
  const correction = attempt?.correction;
  const isChoice = task.task_type === 'choice';
  const isClosed = task.task_type === 'cloze' || isChoice;
  const choiceOptions = Array.isArray(task.options) ? task.options.map(choiceOptionView).filter(Boolean) as ChoiceOptionView[] : [];
  const hasOptions = choiceOptions.length > 0;
  const isCorrect = correctionIsPositive(correction);
  const errataCount = Array.isArray(correction?.errata) ? correction.errata.length : 0;
  const verdictLabel = correction?.verdict
    ? String(correction.verdict).replace(/_/g, ' ')
    : '';
  const promptTranslation = task.prompt_translation || task.translation || task.prompt_en;
  const instruction = displayTaskInstruction(task);
  const taskVocabulary = taskVocabularyItems(task, targetVocabulary);
  const submittedLabel = correction ? (isCorrect ? 'ACCEPTED' : 'REPAIR SAVED') : 'SUBMITTED';
  return (
    <div className={`task-box ${correction ? correction.verdict : ''}`}>
      <div className="task-title">
        <span>{task.label || task.task_type}</span>
        <small>{instruction}</small>
      </div>
      <TaskVocabularyMarker items={taskVocabulary} />
      {task.prompt && (
        <div className="task-prompt-wrap">
          <p className="task-prompt">{task.prompt}</p>
          {promptTranslation && (
            <details className="task-translation">
              <summary>Translate</summary>
              <p>{promptTranslation}</p>
            </details>
          )}
        </div>
      )}
      {hasOptions && (
        <div className="option-row">
          {choiceOptions.map((option) => (
            <button key={option.value} className={value === option.value ? 'selected' : ''} onClick={() => setValue(option.value)} type="button">
              <span>{option.label}</span>
              <strong>{option.text}</strong>
              {option.en && <small>{option.en}</small>}
            </button>
          ))}
        </div>
      )}
      {isChoice && hasOptions ? null : isClosed ? (
        <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="Your answer" />
      ) : (
        <textarea value={value} onChange={(event) => setValue(event.target.value)} placeholder={task.placeholder || 'Write one short sentence.'} />
      )}
      {correction && (
        <div className={`inline-feedback ${isCorrect ? 'positive' : 'negative'}`}>
          <strong>{isCorrect ? <Check size={14} /> : <X size={14} />}{isCorrect ? 'Accepted' : verdictLabel}</strong>
          {!isCorrect && correction.corrected_answer && <p><b>Better line.</b> {correction.corrected_answer}</p>}
          {correction.why && <p><b>Why.</b> {correction.why}</p>}
          {correction.repair && <p><b>Repair.</b> {correction.repair}</p>}
          <VocabularyCreditBadge correction={correction} labelMode="word" labelPrefix="Vocabulary · " />
          {!isCorrect && <em>+{errataCount || 1} erratum</em>}
        </div>
      )}
      <button className="btn solid" disabled={submitting || Boolean(attempt)} onClick={onSubmit} type="button">
        {attempt ? submittedLabel : submitting ? 'CHECKING' : 'SUBMIT'} <Send size={13} />
      </button>
    </div>
  );
}

function FeuilletonCliffhangerHero({ scene }: { scene: GraphicNovelScene }) {
  const hook = scene.hook || scene.script_payload?.hook || scene.recap?.hook || {};
  const question = String(hook?.unresolved_question || hook?.teaser || '').trim();
  const beat = String(hook?.text || '').trim();
  if (!question && !beat) return null;
  const finalPanel = [...(scene.panels || [])].sort((left, right) => (right.panel_index || 0) - (left.panel_index || 0))[0];
  const who = feuilletonCliffhangerCharacter(scene, hook);
  return (
    <section className="s-cliff feuilleton-cliffhanger" data-char={who} aria-label="Feuilleton cliffhanger">
      <div className="ctop">
        <span className="ser">Le Feuilleton</span>
        <span className="end">À suivre</span>
      </div>
      <div className="cart">
        <span className="frame-note">{finalPanel?.title ? `FINAL · ${finalPanel.title}` : 'FINAL · the question lands'}</span>
        <div className="float">
          <span className="s-ava sm" data-char={who}>{feuilletonCharacterInitial(who)}</span>
        </div>
      </div>
      <div className="cbody">
        <div className="who">{feuilletonCharacterName(who)}</div>
        <div className="q">{question || beat}</div>
        {beat && question !== beat && <div className="beat">{beat}</div>}
        <Link className="ccta" href={feuilletonNextMissionHref(scene)}>
          Answer in the next episode <ArrowRight size={18} aria-hidden="true" />
        </Link>
        <div className="next">Next · Act · Episode {typeof scene.episode_index === 'number' ? scene.episode_index + 2 : ''}</div>
      </div>
    </section>
  );
}

function feuilletonNextMissionHref(scene: GraphicNovelScene) {
  const vocabularyIds = sceneTargetVocabulary(scene)
    .map((item) => Number(item.word_id))
    .filter((item) => Number.isFinite(item));
  const pairs: Array<[string, string | number | null | undefined]> = [
    ['mission_id', scene.mission_id || undefined],
    ['atelier_session_id', scene.atelier_session_id || undefined],
    ['serial_thread_id', scene.serial_thread_id || undefined],
    ['episode_index', typeof scene.episode_index === 'number' ? scene.episode_index + 1 : undefined],
    ...(scene.selected_concept_ids || []).slice(0, 4).map((id): [string, number] => ['concept_id', id]),
    ...vocabularyIds.slice(0, 4).map((id): [string, number] => ['vocabulary_id', id]),
    ...(scene.target_errata_ids || []).slice(0, 2).map((id): [string, string] => ['erratum_id', String(id)]),
  ];
  return routeWithQuery('/missions', pairs);
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

function feuilletonCharacterInitial(who: string) {
  return ({ marin: 'M', lila: 'L', gus: 'G', romy: 'R', margaux: 'Mx', marchand: 'M·' } as Record<string, string>)[who] || 'R';
}

function feuilletonCharacterName(who: string) {
  return ({
    marin: 'Marin Lévêque',
    lila: 'Lila Bonnet',
    gus: 'Augustin “Gus”',
    romy: 'Romy Tremblay',
    margaux: 'Margaux',
    marchand: 'M. Marchand',
  } as Record<string, string>)[who] || 'Romy Tremblay';
}

function PostSceneVocabularySummary({
  scene,
  vocabulary,
}: {
  scene: GraphicNovelScene;
  vocabulary: FeuilletonVocabularyItem[];
}) {
  const items = sceneVocabularyRecapItems(scene, vocabulary).slice(0, 6);
  const credit = vocabularyCreditRows(scene.recap?.vocabulary_credit);
  if (!items.length && !credit.length) return null;
  return (
    <section className="paper vocabulary-recap" aria-label="Post-scene vocabulary recap">
      <header>
        <div>
          <span className="t-mono">Vocabulary recap</span>
          <h3>{scene.status === 'completed' ? 'Saved from this edition' : 'After the final panel'}</h3>
        </div>
        <Link href="/vocabulary/review">Review due words <ArrowRight size={13} /></Link>
      </header>
      {credit.length > 0 ? (
        <div className="vocabulary-credit-row" aria-label="Vocabulary credit">
          {credit.map((item) => (
            <span key={item.key}><strong>{item.value}</strong>{item.label}</span>
          ))}
        </div>
      ) : (
        <p>{scene.status === 'completed' ? 'No vocabulary credit was recorded in this edition; the target cards stay linked here for review.' : 'Complete the edition to save context credit; the target cards stay linked here for review.'}</p>
      )}
      {items.length > 0 && (
        <div className="vocabulary-recap-list">
          {items.map((item) => (
            <Link key={vocabularyItemKey(item)} href={vocabularyDetailHref(item)}>
              <span>{vocabularySourceLabel(item)}</span>
              <strong>{item.word}</strong>
              {item.translation && <em>{item.translation}</em>}
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function FeuilletonContinuationCard({
  scene,
  vocabulary,
}: {
  scene: GraphicNovelScene;
  vocabulary: FeuilletonVocabularyItem[];
}) {
  const items = sceneVocabularyRecapItems(scene, vocabulary).slice(0, 3);
  const vocabularyIds = items
    .map((item) => Number(item.word_id))
    .filter((item) => Number.isFinite(item));
  const conceptIds = (scene.selected_concept_ids || []).slice(0, 4);
  const errataIds = (scene.target_errata_ids || []).slice(0, 2);
  const hook = scene.hook || scene.script_payload?.hook || scene.recap?.hook || {};
  const missionPairs: Array<[string, string | number | null | undefined]> = [
    ['mission_id', scene.mission_id || undefined],
    ['atelier_session_id', scene.atelier_session_id || undefined],
    ['serial_thread_id', scene.serial_thread_id || undefined],
    ['episode_index', typeof scene.episode_index === 'number' ? scene.episode_index + 1 : undefined],
    ...conceptIds.map((id): [string, number] => ['concept_id', id]),
    ...vocabularyIds.slice(0, 4).map((id): [string, number] => ['vocabulary_id', id]),
    ...errataIds.map((id): [string, string] => ['erratum_id', String(id)]),
  ];
  const atelierPairs: Array<[string, string | number | null | undefined]> = [
    ['atelier_session_id', scene.atelier_session_id || undefined],
    ['serial_thread_id', scene.serial_thread_id || undefined],
    ...conceptIds.map((id): [string, number] => ['concept_id', id]),
    ...vocabularyIds.slice(0, 4).map((id): [string, number] => ['vocabulary_id', id]),
  ];
  const focus = [
    ...items.map((item) => ({ label: `Word · ${item.word}`, tone: 'vocabulary' as const })),
    ...conceptIds.slice(0, 2).map((id) => ({ label: `Rule · ${id}`, tone: 'grammar' as const })),
  ].slice(0, 4);

  return (
    <ContinuationCard
      className="feuilleton-continuation"
      tone="feuilleton"
      eyebrow={hook?.text ? 'Cliffhanger' : scene.status === 'completed' ? 'Edition filed' : 'After the final panel'}
      title={hook?.teaser || (scene.status === 'completed' ? 'Turn this scene into practice' : 'Finish the scene, then carry it forward')}
      description={scene.status === 'completed'
        ? hook?.text || 'The reading context is saved. Use the same words in a mission, or review the deck while the scene is fresh.'
        : 'The story is carrying today’s vocabulary; completing it saves contextual credit.'}
      focus={hook?.unresolved_question ? [{ label: hook.unresolved_question, tone: 'mission' as const }, ...focus].slice(0, 4) : focus}
      actions={[
        { label: hook?.next_beat_kind === 'mission' ? 'Next episode' : 'Use in mission', href: routeWithQuery('/missions', missionPairs), tone: 'primary' },
        { label: 'Review words', href: '/vocabulary/review' },
        { label: 'Back to Atelier', href: routeWithQuery('/atelier', atelierPairs), tone: 'quiet' },
      ]}
      footer="Reading becomes memory when the thread keeps moving."
    />
  );
}

function QueueCard({
  today,
  scene,
  onSelect,
}: {
  today: GraphicNovelToday | null;
  scene: GraphicNovelScene | null;
  onSelect: (scene: GraphicNovelScene) => void;
}) {
  const scenes = [
    today?.active_scene && { label: 'Active', scene: today.active_scene },
    today?.available_scene && { label: 'Available', scene: today.available_scene },
  ].filter(Boolean) as Array<{ label: string; scene: GraphicNovelScene }>;
  return (
    <section className="paper side-card">
      <header>
        <span className="t-mono">FEUILLETON QUEUE</span>
        <Sparkles size={15} />
      </header>
      {scenes.length ? scenes.map((item) => (
        <button key={`${item.label}-${item.scene.id}`} className={scene?.id === item.scene.id ? 'active' : ''} onClick={() => onSelect(item.scene)}>
          <span className="t-mono-low">{item.label}</span>
          <strong>{item.scene.title}</strong>
          <small>{item.scene.status}</small>
        </button>
      )) : (
        <p className="side-empty">{today?.recommendation?.reason || 'Create an errata-led visual scene.'}</p>
      )}
    </section>
  );
}

function TargetCard({
  scene,
  tasks,
  attemptsByTask,
}: {
  scene: GraphicNovelScene | null;
  tasks: OverlayTask[];
  attemptsByTask: Record<string, Record<string, any>>;
}) {
  const targets = (scene?.script_payload || {}).targets || [];
  const countableTasks = tasks.filter((task) => task.id);
  const submittedCount = countableTasks.filter((task) => attemptsByTask[task.id]).length;
  return (
    <section className="paper side-card">
      <header>
        <span className="t-mono">TASKS</span>
        <span className="t-mono-low">{submittedCount}/{countableTasks.length} submitted</span>
      </header>
      {targets.length > 0 && <div className="side-subhead">Learning targets</div>}
      {targets.map((target: any, index: number) => (
        <div className="target-row" key={`${target.kind}-${target.label}-${index}`}>
          <span className={target.kind === 'grammar' ? 'dot blue' : 'dot red'} />
          <p>{target.label}</p>
        </div>
      ))}
      {!targets.length && <p className="side-empty">Targets will appear after a scene is created.</p>}
    </section>
  );
}

function CorrectionStack({ scene, correction }: { scene: GraphicNovelScene | null; correction: Record<string, any> | null }) {
  if (scene?.script_payload?.experience_mode === 'reward') {
    const glosses = scene.script_payload?.glosses || [];
    return (
      <section className="paper reward-stack">
        <div className="between">
          <span className="t-mono">REWARD READING</span>
          <span className="t-mono-low">{glosses.length} glosses</span>
        </div>
        <p>No required exercises here. Save phrases, skim the glosses, or open the linked rules when something catches.</p>
        <div className="gloss-list">
          {glosses.map((item: any, index: number) => (
            <div key={`${item.term}-${index}`} className="gloss-chip">
              <strong>{item.term}</strong>
              <span>{item.meaning}</span>
            </div>
          ))}
        </div>
        <Link className="btn solid" href="/grammar">OPEN NOTEBOOK <ArrowRight size={13} /></Link>
      </section>
    );
  }
  const attempts = scene?.attempts || [];
  const errata = attempts.flatMap((attempt) => attempt.correction?.errata || []);
  return (
    <section className="correction-stack">
      <div className="between">
        <span className="t-mono">LIVE CORRECTION</span>
        <span className="t-mono-low">{errata.length}</span>
      </div>
      {!correction && <div className="empty-slip">Submit an overlay task to see Feuilleton feedback.</div>}
      {correction && <VocabularyCreditBadge correction={correction} labelMode="word" labelPrefix="Vocabulary · " />}
      {errata.slice(0, 5).map((item: any, index: number) => (
        <RedInkRepairSlip
          key={`${item.display_label}-${index}`}
          label={item.display_label}
          slipNumber={`No. ${String(index + 1).padStart(2, '0')}`}
          learnerText={item.learner_text}
          correctedText={item.corrected_target}
          why={item.why_wrong}
          repair={item.repair_hint}
          source="Feuilleton · story repair"
          action={item.concept_id && <Link className="notebook-link" href={`/grammar?concept=${item.concept_id}`}>Review rule</Link>}
        />
      ))}
    </section>
  );
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
    label: `Panel ${panel.panel_index}`,
    title: panel.title || `Panel ${panel.panel_index}`,
    subtitle: panel.beat || 'A story beat with its own repair.',
    tasks,
    panel,
  };
}

function finalTaskStop(scene: GraphicNovelScene, task: OverlayTask): MobileTaskStop {
  const id = `scene-final-${taskStopSafeId(String(scene.id || task.id))}`;
  return {
    id,
    elementId: mobileTaskStopDomId(id),
    label: 'Final line',
    title: 'Finish the scene',
    subtitle: String(task.prompt_body || task.prompt || 'Write one final French line that turns the scene.'),
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
    || translations.de
    || translations.en
    || translations.fr
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

function resolveVocabularyItem(item: FeuilletonVocabularyItem, vocabulary: FeuilletonVocabularyItem[]) {
  const match = vocabulary.find((candidate) => (
    (item.word_id && candidate.word_id === item.word_id)
    || normalizeVocabularyLookupText(candidate.word) === normalizeVocabularyLookupText(item.word)
  ));
  return match ? {
    ...item,
    ...match,
    word: match.word || item.word,
    translation: item.translation || match.translation,
    example_sentence: item.example_sentence || match.example_sentence,
    example_translation: item.example_translation || match.example_translation,
  } : item;
}

function taskVocabularyItems(task: Record<string, any>, vocabulary: FeuilletonVocabularyItem[]) {
  const direct = vocabularyItemFromTask(task);
  if (!direct) return [];
  return mergeVocabularyItems([resolveVocabularyItem(direct, vocabulary)]).slice(0, 1);
}

function panelVocabularyMatches(panel: GraphicNovelPanel, tasks: OverlayTask[], vocabulary: FeuilletonVocabularyItem[]) {
  if (!vocabulary.length) return [];
  const direct = tasks
    .map(vocabularyItemFromTask)
    .filter(Boolean)
    .map((item) => resolveVocabularyItem(item as FeuilletonVocabularyItem, vocabulary));
  const panelText = panelVocabularyText(panel, tasks);
  const contextual = vocabulary.filter((item) => textContainsVocabularyItem(panelText, item));
  return mergeVocabularyItems([...direct, ...contextual]).slice(0, 2);
}

function panelVocabularyText(panel: GraphicNovelPanel, tasks: OverlayTask[]) {
  const overlay = panel.overlay_payload || {};
  const caption = overlay.caption || {};
  const bubbles = Array.isArray(overlay.bubbles) ? overlay.bubbles : [];
  return [
    panel.title,
    panel.beat,
    caption.fr,
    caption.en,
    ...bubbles.flatMap((bubble: PanelBubble) => [bubble.fr, bubble.en]),
    ...tasks.map(taskVocabularyText),
  ].filter(Boolean).join(' ');
}

function taskVocabularyText(task: Record<string, any>) {
  return [
    task.label,
    task.instruction,
    task.prompt,
    task.prompt_translation,
    task.target_word,
    task.expected_answer,
    ...(Array.isArray(task.expected_features) ? task.expected_features : []),
    ...(Array.isArray(task.options) ? task.options : []),
  ].filter(Boolean).join(' ');
}

function textContainsVocabularyItem(text: string, item: FeuilletonVocabularyItem) {
  const normalizedText = ` ${normalizeVocabularyLookupText(text)} `;
  const normalizedWord = normalizeVocabularyLookupText(item.word);
  if (!normalizedWord || (normalizedWord.length < 3 && !/[' -]/.test(normalizedWord))) return false;
  if (normalizedWord.includes(' ') || normalizedWord.includes("'") || normalizedWord.includes('-')) {
    return normalizedText.includes(` ${normalizedWord} `) || normalizedText.includes(normalizedWord);
  }
  return normalizedText.includes(` ${normalizedWord} `);
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

function vocabularySourceLabel(item: FeuilletonVocabularyItem) {
  const bucket = String(item.bucket || '').toLowerCase();
  const scheduler = String(item.scheduler || '').toLowerCase();
  if (['due', 'fragile', 'linked', 'erratum', 'topic', 'topic_compatible', 'review'].includes(bucket)) {
    return 'your queue';
  }
  if (scheduler.includes('fsrs') || scheduler.includes('linked') || scheduler.includes('queue') || scheduler.includes('mission')) {
    return 'your queue';
  }
  if (bucket === 'target' && scheduler && scheduler !== 'explicit') return 'your queue';
  return 'French 5000';
}

function vocabularyItemKey(item: FeuilletonVocabularyItem) {
  return `${item.word_id || normalizeVocabularyLookupText(item.word)}-${item.word}`;
}

function vocabularyDetailHref(item: FeuilletonVocabularyItem) {
  return item.word_id ? `/vocabulary?word=${item.word_id}` : '/vocabulary';
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

function vocabularyCreditRows(credit: Record<string, any> | undefined) {
  const labels = [
    ['seen_context', 'seen'],
    ['recognized', 'recognized'],
    ['produced_correct', 'produced'],
    ['produced_incorrect', 'repaired'],
    ['missed_target', 'missed'],
  ];
  return labels
    .map(([key, label]) => ({ key, label, value: Number(credit?.[key] || 0) }))
    .filter((item) => item.value > 0);
}

function feuilletonIssueNumber(scene: GraphicNovelScene) {
  const source = scene.source_snapshot || {};
  const rawDate = String(source.date || scene.created_at || '').slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(rawDate)) return `No. ${rawDate.replace(/-/g, '')}`;
  return `No. ${String(scene.id || '').replace(/-/g, '').slice(0, 6).toUpperCase() || 'daily'}`;
}

function feuilletonEditionDate(scene: GraphicNovelScene) {
  const source = scene.source_snapshot || {};
  const item = (source.items || [])[0] || {};
  return formatFeuilletonDate(source.date || item.published_at || source.fetched_at || scene.created_at);
}

function feuilletonSynopsis(scene: GraphicNovelScene, sourceCopy: ReturnType<typeof feuilletonSourceCopy>) {
  const storyBible = scene.script_payload?.story_bible || {};
  return trimFeuilletonText(
    stripInternalSourceLanguage(sourceCopy.summaryFr || storyBible.premise || scene.brief),
    190,
  );
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

function trimFeuilletonText(value: unknown, max = 160) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max - 3).trim()}...` : text;
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
  const missionId = typeof query.mission_id === 'string' ? query.mission_id : '';
  const atelierSessionId = typeof query.atelier_session_id === 'string' ? query.atelier_session_id : '';
  const serialThreadId = typeof query.serial_thread_id === 'string' ? query.serial_thread_id : '';
  const chips: NonNullable<FeuilletonThreadContext>['chips'] = [];

  if (grammarCount) chips.push({ key: 'grammar', label: 'Grammar', value: formatContextCount(grammarCount, 'focus'), tone: 'blue' });
  if (vocabularyCount) chips.push({ key: 'vocabulary', label: 'Vocabulary', value: formatContextCount(vocabularyCount, 'word'), tone: 'yellow' });
  if (errataCount) chips.push({ key: 'errata', label: 'Errata', value: formatContextCount(errataCount, 'repair'), tone: 'red' });
  if (missionId) chips.push({ key: 'mission', label: 'Mission', value: shortContextId(missionId), tone: 'blue' });
  if (serialThreadId) chips.push({ key: 'serial', label: 'Story thread', value: shortContextId(serialThreadId), tone: 'yellow' });
  if (atelierSessionId) chips.push({ key: 'atelier-session', label: 'Atelier Session', value: shortContextId(atelierSessionId), tone: 'red' });
  if (!chips.length) return null;

  const sources = [
    atelierSessionId ? 'Atelier session' : '',
    serialThreadId ? 'serial thread' : '',
    missionId ? 'mission' : '',
    grammarCount ? `${grammarCount} grammar ${grammarCount === 1 ? 'focus' : 'focuses'}` : '',
    vocabularyCount ? `${vocabularyCount} vocabulary ${vocabularyCount === 1 ? 'word' : 'words'}` : '',
    errataCount ? `${errataCount} ${errataCount === 1 ? 'erratum' : 'errata'}` : '',
  ].filter(Boolean);

  return {
    summary: `This edition was seeded from ${joinContextSources(sources)} in today's learning thread.`,
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
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(', ')}, and ${items[items.length - 1]}`;
}

function graphicNovelContextKey(query: RouterQueryLike) {
  const keys = ['atelier_session_id', 'mission_id', 'concept_id', 'erratum_id', 'vocabulary_id'];
  const serialKeys = ['serial_thread_id', 'episode_index'];
  const parts = [...keys, ...serialKeys].flatMap((key) => queryList(query[key]).map((value) => `${key}:${value}`));
  return parts.length ? parts.join('|') : '';
}

function FeuilletonStyles() {
  return (
    <style jsx global>{`
      .feuilleton-page {
        --paper: #f1ece1;
        --paper-2: #e8e0cf;
        --paper-3: #d8cdb6;
        --sheet: #f8f3e8;
        --ink: #14110d;
        --ink-2: #4a4538;
        --ink-3: #8a826f;
        --red: #d8321a;
        --blue: #1d3a8a;
        --yellow: #f3c318;
        --green: #3f7a4b;
        --serif: "EB Garamond", Garamond, "Times New Roman", serif;
        --grotesk: "Inter", "Helvetica Neue", Arial, sans-serif;

        /* Override global app theme custom properties locally to force light/paper styling inside this scope */
        --app-paper: var(--paper);
        --app-paper-2: var(--paper-2);
        --app-paper-3: var(--paper-3);
        --app-sheet: var(--sheet);
        --app-ink: var(--ink);
        --app-ink-2: var(--ink-2);
        --app-ink-3: var(--ink-3);
        --app-blue: var(--blue);
        --app-red: var(--red);
        --app-yellow: var(--yellow);
        --app-green: var(--green);

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
      .fn-masthead { border-bottom: 1px solid var(--ink); }
      .masthead-inner { min-height: 58px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
      .brand { display: inline-flex; align-items: center; gap: 12px; color: var(--ink); text-decoration: none; font-size: 22px; font-weight: 900; letter-spacing: -.03em; }
      .fn-masthead nav { display: flex; gap: 20px; align-items: center; }
      .fn-masthead nav a, .t-mono, .btn { font-size: 10px; letter-spacing: .13em; text-transform: uppercase; font-weight: 900; text-decoration: none; }
      .fn-masthead nav a { color: var(--ink-3); border-bottom: 2px solid transparent; padding-bottom: 3px; }
      .fn-masthead nav a.active, .fn-masthead nav a:hover { color: var(--ink); border-color: var(--ink); }
      .t-mono-low { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-2); font-weight: 800; }
      .red { color: var(--red); }
      .between { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
      .fn-grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 28px; padding-top: 34px; padding-bottom: 80px; align-items: start; }
      .fn-main { min-width: 0; display: grid; gap: 24px; }
      .fn-side { display: grid; gap: 20px; align-content: start; }
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
      .seg-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--ink); background: var(--paper); width: 100%; }
      .seg-row.compact { grid-template-columns: repeat(2, minmax(0, 1fr)); width: min(340px, 100%); }
      .seg-row.compact:last-of-type { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .seg-row button { min-height: 36px; border-right: 1px solid var(--ink); padding: 6px 10px; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; }
      .seg-row button:last-child { border-right: 0; }
      .seg-row button span { display: block; margin-top: 2px; color: var(--ink-3); font-size: 9px; letter-spacing: .08em; }
      .seg-row button.active { background: var(--ink); color: var(--paper); }
      .seg-row button.active span { color: var(--paper); opacity: .7; }
      .preset-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; width: 100%; }
      .preset-row button {
        min-height: 50px;
        border: 1px solid var(--ink);
        padding: 8px 10px;
        text-align: left;
        font-size: 12px;
        font-weight: 900;
        background: var(--paper);
      }
      .preset-row button span {
        display: block;
        margin-top: 3px;
        color: var(--ink-3);
        font-size: 9px;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .preset-row button.active { background: var(--ink); color: var(--paper); }
      .preset-row button.active span { color: var(--paper); opacity: .72; }
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
      .btn { display: inline-flex; align-items: center; justify-content: center; gap: 9px; min-height: 42px; padding: 0 18px; border: 1px solid var(--ink); background: var(--paper); transition: .12s ease; }
      .btn:hover:not(:disabled) { background: var(--ink); color: var(--paper); }
      .btn:disabled { opacity: .45; cursor: not-allowed; }
      .btn.red { background: var(--red); border-color: var(--red); color: var(--paper); }
      .btn.solid { background: var(--ink); color: var(--paper); }
      .btn.lg { min-height: 56px; padding-inline: 28px; }
      .scene-brief { padding: 28px 32px; background: var(--paper); }
      .kicker { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
      .kicker span { border: 1px solid var(--ink); padding: 5px 8px; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; }
      .kicker span.fallback { background: var(--yellow); color: var(--ink); }
      .scene-brief h2 {
        margin: 0;
        font-family: var(--serif);
        font-size: clamp(28px, 3.4vw, 38px);
        line-height: 1.04;
        letter-spacing: 0;
        font-style: italic;
        font-weight: 700;
      }
      .scene-brief > p { max-width: 760px; color: var(--ink-2); line-height: 1.5; font-size: 17px; }
      .edition-meta {
        display: grid;
        gap: 8px;
        max-width: 780px;
        margin-top: 12px;
        color: var(--ink-2);
      }
      .edition-meta > div {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
      }
      .edition-meta span,
      .edition-meta a {
        border: 1px solid var(--paper-3);
        background: var(--sheet);
        color: inherit;
        padding: 4px 7px;
        font-size: 10px;
        letter-spacing: .1em;
        text-transform: uppercase;
        font-weight: 900;
        text-decoration: none;
      }
      .edition-meta p {
        margin: 0;
        line-height: 1.45;
        font-size: 14px;
      }
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
        box-shadow: 4px 4px 0 var(--yellow);
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
      .feuilleton-vocabulary-strip {
        display: grid;
        gap: 10px;
        max-width: 780px;
        margin-top: 16px;
        border-top: 1px solid var(--ink);
        border-bottom: 1px solid var(--ink);
        padding: 11px 0;
      }
      .feuilleton-vocabulary-strip summary {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 14px;
        cursor: pointer;
        list-style: none;
      }
      .feuilleton-vocabulary-strip summary::-webkit-details-marker {
        display: none;
      }
      .feuilleton-vocabulary-strip summary strong {
        color: var(--ink-2);
        font-size: 13px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .feuilleton-vocabulary-strip > div {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding-top: 9px;
      }
      .feuilleton-vocabulary-strip > div > a {
        display: inline-flex;
        align-items: baseline;
        gap: 8px;
        border: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 6px 9px;
        color: inherit;
        text-decoration: none;
      }
      .feuilleton-vocabulary-strip > div > a > span {
        color: var(--blue);
        font-size: 9px;
        letter-spacing: .1em;
        text-transform: uppercase;
        font-weight: 900;
      }
      .feuilleton-vocabulary-strip strong {
        font-size: 14px;
        line-height: 1.1;
      }
      .feuilleton-vocabulary-strip em {
        color: var(--ink-3);
        font-size: 12px;
        font-style: normal;
        font-weight: 800;
      }
      .context-vocabulary-marker {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 7px;
        margin-top: -3px;
      }
      .context-vocabulary-marker > span,
      .task-vocabulary-marker span {
        color: var(--ink-3);
        font-size: 9px;
        letter-spacing: .12em;
        text-transform: uppercase;
        font-weight: 900;
      }
      .context-vocabulary-marker a,
      .task-vocabulary-marker a {
        display: inline-flex;
        align-items: baseline;
        gap: 6px;
        color: inherit;
        text-decoration: none;
      }
      .context-vocabulary-marker a {
        border-bottom: 1px solid var(--paper-3);
        padding-bottom: 2px;
      }
      .context-vocabulary-marker strong,
      .task-vocabulary-marker strong {
        font-family: var(--serif);
        font-size: 17px;
        font-style: italic;
        line-height: 1;
      }
      .context-vocabulary-marker em,
      .task-vocabulary-marker em {
        color: var(--blue);
        font-size: 9px;
        font-style: normal;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
      }
      .task-vocabulary-marker {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        border: 1px solid rgba(20,17,13,.18);
        background: rgba(248,243,232,.6);
        padding: 7px 9px;
      }
      .vocabulary-recap {
        display: grid;
        gap: 14px;
        padding: 22px 26px;
        background: var(--paper);
      }
      .vocabulary-recap header {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 18px;
        border-bottom: 1px solid var(--ink);
        padding-bottom: 12px;
      }
      .vocabulary-recap h3 {
        margin: 5px 0 0;
        font-family: var(--serif);
        font-size: 30px;
        font-style: italic;
        line-height: 1;
        letter-spacing: 0;
      }
      .vocabulary-recap header a {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        color: var(--blue);
        text-decoration: none;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
        white-space: nowrap;
      }
      .vocabulary-recap > p {
        margin: 0;
        color: var(--ink-2);
        line-height: 1.4;
      }
      .vocabulary-credit-row {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        border: 1px solid var(--ink);
        background: var(--paper-2);
      }
      .vocabulary-credit-row span {
        min-width: 0;
        padding: 10px;
        border-right: 1px solid var(--ink);
        color: var(--ink-2);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .vocabulary-credit-row span:last-child { border-right: 0; }
      .vocabulary-credit-row strong {
        display: block;
        color: var(--ink);
        font-size: 24px;
        line-height: 1;
      }
      .vocabulary-recap-list {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 9px;
      }
      .vocabulary-recap-list a {
        display: grid;
        gap: 4px;
        min-width: 0;
        border: 1px solid var(--ink);
        background: var(--sheet);
        color: inherit;
        padding: 10px 12px;
        text-decoration: none;
      }
      .vocabulary-recap-list span {
        color: var(--blue);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
      }
      .vocabulary-recap-list strong {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-family: var(--serif);
        font-size: 21px;
        font-style: italic;
        line-height: 1;
      }
      .vocabulary-recap-list em {
        overflow: hidden;
        color: var(--ink-2);
        font-size: 12px;
        font-style: normal;
        font-weight: 800;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .mobile-completion-card,
      .mobile-reading-bar,
      .mobile-final-task-card,
      .mobile-generation-steps,
      .mobile-generation-note,
      .mobile-loading-copy,
      .mobile-loading-stack,
      .mobile-empty-note,
      .mobile-empty-task-note {
        display: none;
      }
      .feuilleton-mobile-actions,
      .feuilleton-mobile-en-toggle {
        display: none;
      }
      .mobile-panel-dialogue {
        display: none;
      }
      .story-card { margin-top: 18px; border-left: 4px solid var(--blue); background: var(--paper-2); padding: 14px 18px; max-width: 780px; }
      .story-card p { margin: 8px 0 0; color: var(--ink-2); line-height: 1.45; }
      .source-card { margin-top: 18px; border-left: 4px solid var(--yellow); background: var(--paper-2); padding: 14px 18px; max-width: 780px; }
      .source-card strong { display: block; margin: 8px 0; font-size: 18px; line-height: 1.15; }
      .source-card p { margin: 0; color: var(--ink-2); line-height: 1.45; }
      .compact-source {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        border-left-width: 3px;
      }
      .compact-source strong {
        margin: 0;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .compact-source .source-meta {
        margin-left: auto;
        white-space: nowrap;
      }
      .feuilleton-page.is-serial .fn-grid {
        width: min(760px, 100%);
        grid-template-columns: minmax(0, 1fr);
        gap: 0;
        padding-top: 22px;
      }
      .feuilleton-page.is-serial .fn-side {
        display: none;
      }
      .feuilleton-page.is-serial .fn-main {
        gap: 18px;
      }
      .serial-reader {
        border: 1.5px solid var(--ink);
        background: var(--paper);
        overflow: hidden;
      }
      .s-mast {
        border-bottom: 2px solid var(--ink);
        padding: 18px 20px 16px;
        text-align: center;
      }
      .s-mast .kicker {
        display: block;
        margin: 0;
        color: var(--ink-3);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .26em;
        text-transform: uppercase;
      }
      .s-mast .title {
        margin: 6px 0 0;
        font-family: var(--serif);
        font-size: clamp(32px, 7vw, 50px);
        font-style: italic;
        font-weight: 700;
        line-height: .96;
        letter-spacing: 0;
      }
      .s-mast .dateline {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 10px;
        color: var(--ink-2);
        font-size: 8.5px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .s-mast .dateline i {
        display: inline-block;
        width: 3px;
        height: 3px;
        background: var(--ink-3);
      }
      .s-news {
        display: flex;
        gap: 9px;
        align-items: baseline;
        padding: 10px 18px;
        border-bottom: 1px solid var(--ink);
        background: var(--sheet);
      }
      .s-news .lbl {
        flex: 0 0 auto;
        border: 1px solid var(--accent, var(--blue));
        color: var(--accent, var(--blue));
        padding: 2px 5px;
        font-size: 8px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .s-news .txt {
        color: var(--ink-2);
        font-family: var(--serif);
        font-size: 13px;
        font-style: italic;
        line-height: 1.25;
      }
      .s-prev {
        margin: 16px 18px 4px;
        border: 1px solid var(--ink);
        background: var(--paper);
      }
      .s-prev .ph {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 7px 12px;
        border-bottom: 1px dashed var(--ink-3);
      }
      .s-prev .tag {
        color: var(--red);
        font-size: 8.5px;
        font-weight: 900;
        letter-spacing: .16em;
        text-transform: uppercase;
      }
      .s-prev .tag.stamp2 {
        margin-left: auto;
        border: 1px solid var(--ink-3);
        color: var(--ink-3);
        padding: 2px 6px;
        transform: rotate(-2deg);
      }
      .s-prev .pb {
        padding: 10px 13px 12px;
        color: var(--ink-2);
        font-family: var(--serif);
        font-size: 14.5px;
        font-style: italic;
        line-height: 1.32;
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
        padding: 0 0 10px;
      }
      .s-panel {
        margin: 18px;
      }
      .serial-panel {
        --accent: var(--char-romy);
      }
      .s-art {
        position: relative;
        min-height: 260px;
        aspect-ratio: 4 / 3;
        border: 1.5px solid var(--ink);
        background: var(--paper-2);
        background-image: repeating-linear-gradient(135deg, rgba(20,17,13,.06) 0 2px, transparent 2px 12px);
        overflow: hidden;
      }
      .s-art img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
      .s-art .frame-note {
        position: absolute;
        top: 9px;
        left: 9px;
        z-index: 4;
        max-width: 72%;
        border: 1px solid var(--ink-3);
        background: color-mix(in srgb, var(--paper) 92%, transparent);
        color: var(--ink-3);
        padding: 3px 6px;
        font-family: var(--mono);
        font-size: 9px;
        font-weight: 600;
        letter-spacing: .02em;
      }
      .s-cap {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 11px;
        align-items: baseline;
        padding: 10px 2px 2px;
      }
      .s-cap .n {
        color: var(--ink-3);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .04em;
      }
      .s-cap .c {
        color: var(--ink);
        font-family: var(--serif);
        font-size: 17px;
        font-style: italic;
        line-height: 1.3;
        text-wrap: pretty;
      }
      .serial-panel .context-vocabulary-marker {
        margin: 9px 0 0;
      }
      .serial-dialogue {
        margin-top: 10px;
      }
      .serial-caption-translation {
        margin-top: 8px;
      }
      .s-fork {
        margin: 16px 18px;
        border: 1.5px solid var(--ink);
        background: var(--sheet);
      }
      .serial-panel .s-fork {
        margin: 14px 0 0;
      }
      .s-fork .fh {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 9px 13px;
        border-bottom: 1px solid var(--ink);
      }
      .s-fork .fh .q {
        color: var(--ink-3);
        font-size: 8.5px;
        font-weight: 900;
        letter-spacing: .14em;
        line-height: 1.35;
        text-transform: uppercase;
      }
      .s-fork .fh .q b {
        color: var(--ink);
      }
      .serial-act-body {
        display: grid;
        gap: 12px;
        padding: 12px;
      }
      .serial-act .task-box,
      .serial-final-act .task-box {
        border-left-color: var(--char-toi);
        background: var(--paper);
      }
      .serial-final-act {
        margin: 0;
      }
      .serial-reader .page-scene {
        padding: 18px;
      }
      .speech-bubble[data-char] {
        border-color: var(--accent);
      }
      .speech-bubble[data-char] span,
      .bubble-transcript blockquote[data-char] span {
        color: var(--accent);
      }
      .bubble-transcript blockquote[data-char] {
        border-left-color: var(--accent);
      }
      .feuilleton-cliffhanger {
        margin: 0;
        border: 0;
      }
      .feuilleton-cliffhanger .s-ava {
        --accent: inherit;
      }
      .source-translation {
        margin-top: 10px;
        border-top: 1px solid rgba(20,17,13,.18);
        padding-top: 8px;
      }
      .source-translation summary {
        cursor: pointer;
        color: var(--blue);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .source-translation strong { margin-top: 8px; }
      .source-meta { display: flex; justify-content: space-between; gap: 12px; margin-top: 10px; border-top: 1px solid rgba(20,17,13,.22); padding-top: 10px; font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
      .source-meta a, .notebook-link { color: var(--blue); text-decoration: none; }
      .edition-printing {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 12px;
        border: 1px solid rgba(29,58,138,.28);
        background: rgba(29,58,138,.08);
        color: var(--blue);
        padding: 9px 11px;
        font-size: 12px;
        font-weight: 900;
      }
      .brief-glosses { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
      .brief-glosses span {
        border: 1px solid var(--ink);
        background: var(--paper-2);
        padding: 6px 9px;
        font-size: 12px;
        line-height: 1.2;
      }
      .page-scene { display: grid; gap: 20px; }
      .comic-page-card { background: var(--paper); padding: 12px; }
      .comic-page-image {
        position: relative;
        background: var(--paper-2);
        border: 2px solid var(--ink);
        overflow: hidden;
      }
      .comic-page-image img { display: block; width: 100%; height: auto; }
      .comic-page-caption {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        border-top: 1px solid var(--paper-3);
        padding: 12px 4px 2px;
      }
      .comic-page-caption p { margin: 0; max-width: 620px; color: var(--ink-2); line-height: 1.35; }
      .annotation-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
      .panel-annotation {
        padding: 18px;
        display: grid;
        gap: 12px;
        background: var(--paper);
        border: 2px solid var(--ink);
        box-shadow: 4px 4px 0px 0px var(--ink);
        transition: transform 0.25s cubic-bezier(0.165, 0.84, 0.44, 1), box-shadow 0.25s cubic-bezier(0.165, 0.84, 0.44, 1);
      }
      .panel-annotation:hover {
        transform: translateY(-4px) scale(1.01);
        box-shadow: 8px 8px 0px 0px var(--ink);
      }
      .panel-annotation > p { margin: 0; color: var(--ink-2); line-height: 1.4; }
      .panel-annotation blockquote {
        margin: 0;
        background: var(--paper-2);
        border-left: 4px solid var(--blue);
        padding: 10px 12px;
      }
      .panel-annotation blockquote span {
        display: block;
        margin-bottom: 4px;
        color: var(--blue);
        font-size: 10px;
        letter-spacing: .12em;
        text-transform: uppercase;
        font-weight: 900;
      }
      .panel-annotation blockquote p { margin: 0; font-family: var(--serif); font-size: 22px; font-style: italic; line-height: 1.18; }
      .panel-grid { display: grid; gap: 24px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .panel-card {
        border: 2px solid var(--ink);
        background: var(--paper);
        overflow: hidden;
        box-shadow: 4px 4px 0px 0px var(--ink);
        transition: transform 0.25s cubic-bezier(0.165, 0.84, 0.44, 1), box-shadow 0.25s cubic-bezier(0.165, 0.84, 0.44, 1);
      }
      .panel-card:hover {
        transform: translateY(-4px) scale(1.01);
        box-shadow: 8px 8px 0px 0px var(--ink);
      }
      .panel-card .panel-image img {
        transition: transform 0.3s cubic-bezier(0.165, 0.84, 0.44, 1);
      }
      .panel-card:hover .panel-image img {
        transform: scale(1.04);
      }
      .panel-image {
        aspect-ratio: 1 / 1;
        min-height: 0;
        position: relative;
        overflow: hidden;
        background: var(--paper-2);
        border-bottom: 2px solid var(--ink);
      }
      .panel-image img {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        min-height: 0;
        object-fit: cover;
        display: block;
      }
      .comic-fallback {
        position: absolute;
        inset: 0;
        overflow: hidden;
        background:
          radial-gradient(circle at 18px 18px, rgba(20,17,13,.13) 0 2px, transparent 2px 100%) 0 0 / 30px 30px,
          linear-gradient(180deg, #f4efe3 0%, #e3d8c2 100%);
      }
      .comic-fallback.queued {
        background:
          radial-gradient(circle at 18px 18px, rgba(20,17,13,.09) 0 2px, transparent 2px 100%) 0 0 / 30px 30px,
          linear-gradient(180deg, #f8f3e8 0%, #e9dfcc 100%);
      }
      .queued-panel-copy {
        position: absolute;
        inset: auto 18px 18px 18px;
        z-index: 4;
        border: 2px solid var(--ink);
        background: rgba(244,239,227,.94);
        box-shadow: 4px 4px 0 var(--ink);
        padding: 12px;
      }
      .queued-panel-copy span {
        display: block;
        margin-bottom: 6px;
        color: var(--blue);
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .queued-panel-copy p {
        margin: 0;
        color: var(--ink);
        font-size: 13px;
        line-height: 1.35;
      }
      .comic-fallback::before {
        content: "";
        position: absolute;
        inset: 22px;
        border: 3px solid var(--ink);
        background:
          linear-gradient(90deg, transparent 0 49%, rgba(20,17,13,.22) 49% 50%, transparent 50% 100%),
          linear-gradient(180deg, transparent 0 58%, rgba(20,17,13,.2) 58% 59%, transparent 59% 100%);
        pointer-events: none;
      }
      .comic-sun {
        position: absolute;
        right: 54px;
        top: 42px;
        width: 58px;
        height: 58px;
        border-radius: 50%;
        background: var(--yellow);
        border: 3px solid var(--ink);
      }
      .comic-window {
        position: absolute;
        top: 58px;
        width: 96px;
        height: 92px;
        border: 3px solid var(--ink);
        background: rgba(29,58,138,.18);
      }
      .comic-window::before,
      .comic-window::after {
        content: "";
        position: absolute;
        background: var(--ink);
      }
      .comic-window::before { left: 50%; top: 0; width: 3px; height: 100%; }
      .comic-window::after { left: 0; top: 50%; width: 100%; height: 3px; }
      .window-a { left: 64px; }
      .window-b { left: 188px; transform: skewY(-2deg); }
      .comic-awning {
        position: absolute;
        left: 48px;
        right: 48px;
        top: 165px;
        height: 52px;
        border: 3px solid var(--ink);
        background: repeating-linear-gradient(90deg, var(--red) 0 42px, var(--paper) 42px 84px);
        transform: rotate(-1deg);
      }
      .comic-ground {
        position: absolute;
        left: 36px;
        right: 36px;
        bottom: 42px;
        height: 76px;
        border-top: 5px solid var(--ink);
        background: linear-gradient(135deg, rgba(20,17,13,.08) 0 25%, transparent 25% 50%, rgba(20,17,13,.08) 50% 75%, transparent 75%) 0 0 / 42px 42px;
      }
      .comic-table {
        position: absolute;
        right: 84px;
        bottom: 88px;
        width: 112px;
        height: 18px;
        background: var(--blue);
        border: 3px solid var(--ink);
      }
      .comic-table::before,
      .comic-table::after {
        content: "";
        position: absolute;
        top: 16px;
        width: 4px;
        height: 56px;
        background: var(--ink);
      }
      .comic-table::before { left: 18px; }
      .comic-table::after { right: 18px; }
      .comic-phone {
        position: absolute;
        right: 126px;
        bottom: 124px;
        width: 30px;
        height: 48px;
        border: 3px solid var(--ink);
        border-radius: 5px;
        background: var(--paper);
        transform: rotate(-8deg);
      }
      .comic-phone::after {
        content: "";
        position: absolute;
        left: 9px;
        bottom: 4px;
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--ink);
      }
      .comic-figure {
        position: absolute;
        bottom: 92px;
        width: 86px;
        height: 146px;
      }
      .figure-a { left: 112px; }
      .figure-b { left: 248px; transform: scale(.9) rotate(2deg); }
      .comic-figure .head {
        position: absolute;
        left: 22px;
        top: 0;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: var(--paper);
        border: 4px solid var(--ink);
      }
      .comic-figure .body {
        position: absolute;
        left: 26px;
        top: 48px;
        width: 36px;
        height: 76px;
        background: var(--red);
        border: 4px solid var(--ink);
        border-radius: 18px 18px 8px 8px;
      }
      .figure-b .body { background: var(--blue); }
      .comic-figure .arm {
        position: absolute;
        top: 68px;
        width: 52px;
        height: 5px;
        background: var(--ink);
        transform-origin: left center;
      }
      .comic-figure .arm-a { left: 4px; transform: rotate(-24deg); }
      .comic-figure .arm-b { left: 42px; transform: rotate(32deg); }
      .comic-rain {
        position: absolute;
        width: 4px;
        height: 54px;
        background: var(--blue);
        opacity: .65;
        transform: rotate(16deg);
      }
      .rain-a { left: 58%; top: 64px; }
      .rain-b { left: 66%; top: 116px; height: 42px; }
      .rain-c { left: 74%; top: 78px; height: 62px; }
      .comic-1 .figure-b { display: none; }
      .comic-1 .comic-phone { opacity: .45; }
      .comic-2 .comic-sun { background: var(--blue); }
      .comic-2 .comic-phone { transform: rotate(8deg) scale(1.18); background: var(--yellow); }
      .comic-3 .comic-rain { opacity: .9; }
      .comic-3 .comic-awning { background: repeating-linear-gradient(90deg, var(--blue) 0 42px, var(--paper) 42px 84px); }
      .comic-4 .comic-table { background: var(--yellow); }
      .comic-4 .figure-a .body { background: var(--blue); }
      .bubble-layer {
        position: absolute;
        inset: 0;
        z-index: 3;
        pointer-events: none;
      }
      .speech-bubble {
        position: absolute;
        max-width: min(42%, 320px);
        background: rgba(245, 239, 226, .96);
        border: 2px solid var(--ink);
        padding: 10px 12px;
        box-shadow: 5px 5px 0 var(--ink);
        transform: rotate(-.5deg);
        color: var(--ink);
        font: inherit;
        text-align: left;
        pointer-events: auto;
        transition: transform 0.2s ease-out, box-shadow 0.2s ease-out, border-color 0.2s ease-out;
      }
      .speech-bubble:hover {
        transform: scale(1.03) rotate(0deg);
        box-shadow: 7px 7px 0 var(--blue);
        border-color: var(--blue);
        background: #fff;
        z-index: 10;
      }
      .speech-bubble p {
        transition: color 0.2s ease-out;
      }
      .speech-bubble:hover p {
        color: var(--blue);
      }
      .speech-bubble::after {
        content: "";
        position: absolute;
        left: 20px;
        bottom: -12px;
        width: 18px;
        height: 18px;
        background: inherit;
        border-right: 2px solid var(--ink);
        border-bottom: 2px solid var(--ink);
        transform: rotate(45deg);
      }
      .speech-bubble:nth-child(even) {
        transform: rotate(.5deg);
      }
      .speech-bubble:nth-child(even)::after {
        left: auto;
        right: 28px;
      }
      .speech-bubble span,
      .bubble-transcript span {
        display: block;
        margin-bottom: 4px;
        font-size: 9px;
        letter-spacing: .12em;
        text-transform: uppercase;
        font-weight: 900;
        color: var(--blue);
      }
      .speech-bubble p { margin: 0; font-family: var(--serif); font-size: clamp(15px, 1.8vw, 21px); font-style: italic; line-height: 1.12; }
      .speech-bubble small {
        display: inline-block;
        margin-top: 6px;
        color: var(--blue);
        font-family: var(--mono);
        font-size: 9px;
        font-weight: 900;
        letter-spacing: .12em;
      }
      .bubble-transcript {
        display: grid;
        gap: 8px;
      }
      .bubble-transcript blockquote {
        margin: 0;
        border-left: 4px solid var(--blue);
        background: var(--paper-2);
        padding: 10px 12px;
        transition: transform 0.2s ease-out, border-left-color 0.2s ease-out, background-color 0.2s ease-out, box-shadow 0.2s ease-out;
      }
      .bubble-transcript blockquote:hover {
        transform: translateX(4px);
        border-left-color: var(--yellow);
        background: var(--paper);
        box-shadow: 2px 2px 0px 0px var(--ink);
      }
      .bubble-transcript blockquote p {
        transition: color 0.2s ease-out;
      }
      .bubble-transcript blockquote:hover p {
        color: var(--blue);
      }
      .bubble-transcript small {
        display: block;
        margin-top: 5px;
        color: var(--ink-2);
        line-height: 1.3;
      }
      .panel-body { padding: 18px; display: grid; gap: 14px; }
      .panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--paper-3); padding-bottom: 9px; }
      .panel-audio-button {
        display: inline-grid;
        place-items: center;
        flex: 0 0 auto;
        width: 30px;
        height: 30px;
        border: 1.5px solid var(--ink);
        background: var(--paper);
        color: var(--blue);
        box-shadow: 2px 2px 0 var(--ink);
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
      .read-first-task-section {
        display: grid;
        gap: 18px;
        padding: 20px;
        background: var(--paper);
      }
      .read-first-head h3 {
        margin: 6px 0 7px;
        font-family: var(--serif);
        font-size: 31px;
        font-style: italic;
        line-height: 1;
      }
      .read-first-head p {
        margin: 0;
        color: var(--ink-2);
        line-height: 1.4;
      }
      .read-first-groups {
        display: grid;
        gap: 14px;
      }
      .read-first-group {
        display: grid;
        gap: 12px;
        border: 1.5px solid var(--ink);
        background: var(--paper-2);
        padding: 14px;
      }
      .panel-task-drawer {
        border: 1.5px solid var(--ink);
        background: var(--paper);
        box-shadow: 4px 4px 0 var(--ink);
      }
      .panel-task-drawer summary {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 12px;
        min-height: 46px;
        padding: 0 13px;
        cursor: pointer;
        list-style: none;
      }
      .panel-task-drawer summary::-webkit-details-marker {
        display: none;
      }
      .panel-task-drawer summary span {
        color: var(--red);
        font-size: 12px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .panel-task-drawer summary small {
        color: var(--ink-2);
        font-family: var(--mono);
        font-size: 10px;
        font-weight: 900;
      }
      .panel-task-drawer-body {
        display: grid;
        gap: 12px;
        border-top: 1.5px solid var(--ink);
        padding: 12px;
      }
      .panel-body > p { margin: 0; color: var(--ink-2); line-height: 1.4; }
      .panel-caption {
        display: grid;
        gap: 7px;
        border-left: 4px solid var(--blue);
        background: var(--paper-2);
        padding: 12px 14px;
        transition: transform 0.2s ease-out, border-left-color 0.2s ease-out, background-color 0.2s ease-out, box-shadow 0.2s ease-out;
      }
      .panel-caption:hover {
        transform: translateX(4px);
        border-left-color: var(--yellow);
        background: var(--paper);
        box-shadow: 2px 2px 0px 0px var(--ink);
      }
      .panel-caption p { margin: 0; }
      .caption-fr {
        font-family: var(--serif);
        font-size: 24px;
        line-height: 1.12;
        font-style: italic;
        transition: color 0.2s ease-out;
      }
      .panel-caption:hover .caption-fr {
        color: var(--blue);
      }
      .caption-en {
        color: var(--ink-2);
        line-height: 1.35;
      }
      .caption-translation summary {
        cursor: pointer;
        width: fit-content;
        font-size: 10px;
        letter-spacing: .12em;
        text-transform: uppercase;
        font-weight: 900;
        color: var(--blue);
      }
      .caption-translation[open] {
        border-top: 1px solid var(--paper-3);
        padding-top: 7px;
      }
      .task-box { display: grid; gap: 12px; border-left: 4px solid var(--blue); background: var(--paper-2); padding: 14px; }
      .task-title { display: grid; gap: 4px; }
      .task-title span { font-size: 11px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; }
      .task-title small { color: var(--ink-2); line-height: 1.35; }
      .task-prompt-wrap { display: grid; gap: 6px; }
      .task-prompt { margin: 0; font-family: var(--serif); font-size: 21px; font-style: italic; }
      .task-translation summary {
        cursor: pointer;
        color: var(--blue);
        font-size: 10px;
        font-family: var(--mono);
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .task-translation p {
        margin: 6px 0 0;
        color: var(--ink-2);
        font-family: var(--sans);
        font-size: 14px;
        font-style: normal;
        line-height: 1.35;
      }
      .option-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
      .option-row button { display: grid; gap: 3px; min-height: 64px; border: 1px solid var(--ink); background: var(--paper); padding: 8px 10px; text-align: left; }
      .option-row button span { color: var(--blue); font-family: var(--mono); font-size: 10px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
      .option-row button strong { font-family: var(--serif); font-size: 18px; font-style: italic; line-height: 1.12; }
      .option-row button small { color: var(--ink-2); font-size: 12px; line-height: 1.2; }
      .option-row button.selected { background: var(--ink); color: var(--paper); }
      .task-box input, .task-box textarea { width: 100%; border: 1px solid var(--ink); background: var(--paper); padding: 11px 12px; outline: none; box-shadow: 4px 4px 0 var(--ink); font-family: var(--serif); font-size: 20px; font-style: italic; }
      .task-box textarea { min-height: 100px; resize: vertical; }
      .inline-feedback { border: 1px solid var(--ink); border-left: 4px solid var(--blue); background: rgba(255,255,255,.35); padding: 10px 12px; }
      .inline-feedback strong { display: inline-flex; align-items: center; gap: 6px; }
      .inline-feedback.positive { border-left-color: var(--green); background: rgba(63,122,75,.12); }
      .inline-feedback.negative { border-left-color: var(--red); background: rgba(216,50,26,.1); }
      .inline-feedback p { margin: 4px 0 0; line-height: 1.35; }
      .inline-feedback em { display: inline-block; margin-top: 8px; border: 1px solid var(--red); color: var(--red); background: var(--sheet); padding: 3px 7px; font-style: normal; font-size: 10px; font-weight: 900; }
      .final-task { padding: 24px 28px; background: var(--paper); display: grid; gap: 16px; }
      .final-task h3 { margin: 6px 0 0; font-size: 30px; line-height: 1; letter-spacing: -.035em; }
      .final-task p { margin: 8px 0 0; color: var(--ink-2); line-height: 1.45; }
      .mobile-story-task-launcher,
      .mobile-task-flyin,
      .mobile-bottom-sheet-layer {
        display: none;
      }
      .complete-row { display: flex; justify-content: flex-end; gap: 12px; flex-wrap: wrap; }
      .side-card header { min-height: 44px; padding: 0 14px; border-bottom: 1px solid var(--ink); display: flex; align-items: center; justify-content: space-between; }
      .side-card button { width: 100%; text-align: left; padding: 14px; border-top: 1px solid var(--paper-3); display: grid; gap: 5px; }
      .side-card button.active { background: var(--ink); color: var(--paper); }
      .side-empty { margin: 0; padding: 14px; color: var(--ink-2); line-height: 1.4; }
      .side-subhead { padding: 12px 14px 0; color: var(--ink-3); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; font-weight: 900; }
      .target-row { display: grid; grid-template-columns: 12px 1fr; gap: 9px; padding: 12px 14px; border-top: 1px solid var(--paper-3); align-items: start; }
      .target-row p { margin: 0; line-height: 1.35; font-size: 13px; }
      .dot { width: 8px; height: 8px; margin-top: 5px; border-radius: 50%; display: inline-block; background: var(--ink); }
      .dot.blue { background: var(--blue); }
      .dot.red { background: var(--red); }
      .correction-stack { display: grid; gap: 14px; }
      .reward-stack { display: grid; gap: 14px; padding: 16px; }
      .reward-stack p { margin: 0; color: var(--ink-2); line-height: 1.4; }
      .gloss-list { display: grid; gap: 8px; }
      .gloss-chip { border: 1px solid var(--ink); padding: 10px; background: var(--paper); display: grid; gap: 4px; }
      .gloss-chip strong { font-family: var(--serif); font-size: 18px; font-style: italic; }
      .gloss-chip span { color: var(--ink-2); font-size: 13px; }
      .empty-slip { border: 1px dashed var(--ink-3); padding: 16px; color: var(--ink-2); }
      .errata-slip { position: relative; background: var(--paper); border: 2px solid var(--ink); padding: 24px 16px 16px; box-shadow: 5px 5px 0 var(--ink); transform: rotate(-1deg); }
      .errata-slip:nth-child(even) { transform: rotate(1deg); }
      .slip-label { position: absolute; left: 14px; top: -12px; background: var(--red); color: var(--paper); padding: 5px 10px; font-size: 10px; letter-spacing: .08em; text-transform: uppercase; font-weight: 900; }
      .slip-num { position: absolute; right: 0; top: 0; background: var(--ink); color: var(--paper); padding: 5px 8px; font-size: 10px; }
      .wrong { color: var(--red); text-decoration: line-through; font-family: var(--serif); font-size: 20px; font-style: italic; }
      .right { background: rgba(243,195,24,.25); display: inline; font-family: var(--serif); font-size: 20px; font-style: italic; }
      .why { margin-top: 12px; border-left: 4px solid var(--blue); padding-left: 10px; color: var(--ink-2); line-height: 1.35; }
      .why p { margin: 4px 0; }
      .spin { animation: spin 1s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @media (max-width: 980px) {
        .fn-grid, .panel-grid, .annotation-grid { grid-template-columns: 1fr; }
        .fn-title, .masthead-inner { align-items: flex-start; flex-direction: column; }
        .create-console { width: 100%; justify-items: stretch; }
        .seg-row.compact { width: 100%; }
        .preset-row { grid-template-columns: 1fr; }
        .fn-masthead nav { flex-wrap: wrap; }
        .fn-side { order: -1; }
      }
      @media (max-width: 760px) {
        .feuilleton-page {
          padding-bottom: calc(var(--phone-bottom-nav-space) + 18px);
        }
        .feuilleton-page .feuilleton-mobile-actions {
          display: inline-grid;
          grid-template-columns: auto auto auto;
          align-items: center;
          gap: 8px;
        }
        .feuilleton-page .feuilleton-mobile-today {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 64px;
          min-height: 44px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
          padding: 8px 10px;
          text-decoration: none;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .feuilleton-page .feuilleton-mobile-en-toggle {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 56px;
          min-height: 44px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
          padding: 8px 12px;
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .13em;
          text-transform: uppercase;
        }
        .feuilleton-page .feuilleton-mobile-en-toggle.active {
          background: var(--ink);
          color: var(--paper);
        }
        .feuilleton-page .feuilleton-mobile-new-scene {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          min-height: 44px;
          border: 1px solid var(--ink);
          background: var(--red);
          color: var(--paper);
          padding: 8px 12px;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
          white-space: nowrap;
        }
        .feuilleton-page .feuilleton-mobile-new-scene:disabled {
          opacity: .55;
          cursor: not-allowed;
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
        .feuilleton-page.has-scene .app-mobile-nav {
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
        .preset-row {
          gap: 0;
          grid-template-columns: 1fr;
        }
        .preset-row button {
          min-height: 52px;
          border-bottom: 0;
          background: var(--ink);
          color: var(--paper);
          padding: 10px 13px;
        }
        .preset-row button span {
          color: rgba(241,236,225,.72);
        }
        .seg-row {
          border-top-width: 1px;
          background: #f8f3e8;
        }
        .seg-row button,
        .preset-row button {
          min-width: 0;
        }
        .seg-row button {
          min-height: 44px;
          padding: 7px 8px;
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
          background: #f8f3e8;
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
        .feuilleton-page .mobile-empty-note {
          display: block;
          color: var(--ink-2);
          font-size: 13px;
          letter-spacing: 0;
          text-transform: none;
          font-weight: 700;
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
          padding: 20px;
        }
        .feuilleton-page .edition-actions {
          min-width: 0;
        }
        .feuilleton-page .scene-brief {
          width: 100%;
          max-width: 100%;
          padding: 18px;
          overflow: hidden;
          border-width: 1px;
          background: var(--sheet);
        }
        .feuilleton-page .kicker {
          display: none;
        }
        .feuilleton-page .kicker span {
          flex: 0 0 auto;
          white-space: nowrap;
        }
        .feuilleton-page .scene-brief h2 {
          font-size: 29px;
        }
        .feuilleton-page .scene-brief > p {
          font-size: 15px;
          line-height: 1.45;
        }
        .feuilleton-page .edition-meta {
          margin-top: 10px;
        }
        .feuilleton-page .edition-meta > div {
          gap: 6px;
        }
        .feuilleton-page .edition-meta span,
        .feuilleton-page .edition-meta a {
          max-width: 100%;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .feuilleton-page .edition-meta p {
          font-size: 13px;
          overflow-wrap: anywhere;
        }
        .feuilleton-page .today-thread-banner {
          grid-template-columns: 1fr;
          gap: 12px;
          margin-top: 12px;
          padding: 13px;
          border-left-width: 5px;
          box-shadow: 3px 3px 0 var(--yellow);
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
        .feuilleton-page .feuilleton-vocabulary-strip {
          margin-top: 12px;
        }
        .feuilleton-page .feuilleton-vocabulary-strip summary {
          align-items: center;
        }
        .feuilleton-page .feuilleton-vocabulary-strip summary strong {
          max-width: 58%;
        }
        .feuilleton-page .feuilleton-vocabulary-strip > div {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 7px;
        }
        .feuilleton-page .feuilleton-vocabulary-strip > div > a {
          display: grid;
          gap: 2px;
          min-width: 0;
          padding: 7px 8px;
        }
        .feuilleton-page .feuilleton-vocabulary-strip strong,
        .feuilleton-page .feuilleton-vocabulary-strip em {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .feuilleton-page .context-vocabulary-marker {
          gap: 6px;
          margin-top: -2px;
        }
        .feuilleton-page .context-vocabulary-marker a {
          max-width: 100%;
        }
        .feuilleton-page .context-vocabulary-marker strong,
        .feuilleton-page .task-vocabulary-marker strong {
          font-size: 16px;
          overflow-wrap: anywhere;
        }
        .feuilleton-page .source-card {
          width: 100%;
          max-width: 100%;
          min-width: 0;
          padding: 12px;
          overflow: hidden;
        }
        .feuilleton-page .source-card strong {
          display: block;
          max-width: 100%;
          font-size: 16px;
          line-height: 1.2;
          overflow-wrap: anywhere;
        }
        .feuilleton-page .source-card p {
          overflow-wrap: anywhere;
        }
        .feuilleton-page .source-meta {
          display: grid;
          gap: 7px;
          overflow-wrap: anywhere;
        }
        .feuilleton-page .compact-source {
          display: grid;
          grid-template-columns: minmax(0, 1fr);
          gap: 5px;
        }
        .feuilleton-page .compact-source .source-meta {
          margin-left: 0;
          display: flex;
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
        .feuilleton-page .s-mast {
          padding: 16px 16px 14px;
        }
        .feuilleton-page .s-mast .kicker {
          display: block;
        }
        .feuilleton-page .s-mast .title {
          font-size: 34px;
        }
        .feuilleton-page .s-mast .dateline {
          gap: 7px;
        }
        .feuilleton-page .s-news {
          display: grid;
          gap: 7px;
          padding: 9px 14px;
        }
        .feuilleton-page .s-news .lbl {
          width: fit-content;
        }
        .feuilleton-page .s-prev,
        .feuilleton-page .serial-reader-toggle,
        .feuilleton-page .s-panel,
        .feuilleton-page .s-fork {
          margin-left: var(--phone-gutter);
          margin-right: var(--phone-gutter);
        }
        .feuilleton-page .serial-panel .s-fork {
          margin-left: 0;
          margin-right: 0;
        }
        .feuilleton-page .s-art {
          min-height: var(--phone-art-min-height);
          aspect-ratio: 3 / 4;
        }
        .feuilleton-page .s-cap {
          gap: 9px;
        }
        .feuilleton-page .s-cap .c {
          font-size: 16px;
        }
        .feuilleton-page .serial-act-body {
          padding: 11px;
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
        .feuilleton-page .comic-page-card {
          padding: 8px;
        }
        .feuilleton-page .comic-page-caption {
          display: grid;
          gap: 8px;
        }
        .feuilleton-page .annotation-grid {
          gap: 12px;
        }
        .feuilleton-page .panel-card,
        .feuilleton-page .comic-page-card,
        .feuilleton-page .panel-annotation,
        .feuilleton-page .final-task,
        .feuilleton-page .side-card,
        .feuilleton-page .vocabulary-recap {
          max-width: 100%;
          min-width: 0;
          border-width: 1px;
        }
        .feuilleton-page .panel-image {
          aspect-ratio: 4 / 3;
          border-bottom-width: 1px;
        }
        .feuilleton-page .speech-bubble {
          max-width: 54%;
          min-width: 112px;
          padding: 8px 9px;
          box-shadow: 3px 3px 0 var(--ink);
        }
        .feuilleton-page .bubble-1 {
          left: 5% !important;
        }
        .feuilleton-page .bubble-2 {
          left: auto !important;
          right: 5%;
        }
        .feuilleton-page .speech-bubble p {
          font-size: 15px;
          line-height: 1.08;
          overflow-wrap: anywhere;
        }
        .feuilleton-page .bubble-layer {
          display: block;
        }
        .feuilleton-page .mobile-panel-dialogue {
          display: grid;
          gap: 7px;
          border: 1px solid var(--ink);
          background: var(--paper);
          padding: 9px 10px;
        }
        .feuilleton-page .mobile-panel-dialogue summary {
          cursor: pointer;
          color: var(--blue);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .feuilleton-page .mobile-panel-dialogue .bubble-transcript {
          gap: 6px;
        }
        .feuilleton-page .mobile-panel-dialogue .bubble-transcript blockquote {
          padding: 9px 11px;
          background: var(--sheet);
        }
        .feuilleton-page .mobile-panel-dialogue .bubble-transcript p {
          font-size: 19px;
          line-height: 1.18;
        }
        .feuilleton-page .bubble-transcript small,
        .feuilleton-page .caption-translation {
          display: none;
        }
        .feuilleton-page .bubble-transcript small.mobile-en-visible,
        .feuilleton-page .caption-translation.mobile-en-visible {
          display: block;
        }
        .feuilleton-page .panel-body {
          padding: 14px;
          gap: 11px;
        }
        .feuilleton-page .panel-head {
          display: grid;
          gap: 4px;
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
        .feuilleton-page .read-first-task-section {
          padding: 15px;
          gap: 14px;
        }
        .feuilleton-page .read-first-head h3 {
          font-size: 27px;
        }
        .feuilleton-page .read-first-group {
          padding: 12px;
          gap: 11px;
        }
        .feuilleton-page .panel-task-drawer summary {
          min-height: 44px;
        }
        .feuilleton-page .caption-fr {
          font-size: 21px;
        }
        .feuilleton-page .mobile-story-task-launcher {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 3px 12px;
          width: 100%;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 11px 12px;
          text-align: left;
          box-shadow: inset 4px 0 0 var(--red);
          opacity: 0;
          pointer-events: none;
          transition: opacity 150ms ease-out;
        }
        .feuilleton-page .mobile-story-task-launcher.revealed {
          opacity: 1;
          pointer-events: auto;
        }
        .feuilleton-page .mobile-story-task-launcher.complete {
          box-shadow: inset 4px 0 0 var(--green);
        }
        .feuilleton-page .mobile-story-task-launcher span {
          grid-column: 1 / -1;
          color: var(--ink-2);
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 0;
          text-transform: none;
        }
        .feuilleton-page .mobile-story-task-launcher strong {
          min-width: 0;
          font-family: var(--serif);
          font-size: 22px;
          font-style: italic;
          line-height: 1;
        }
        .feuilleton-page .mobile-story-task-launcher small {
          align-self: end;
          color: var(--blue);
          font-size: 12px;
          font-weight: 900;
          letter-spacing: 0;
          line-height: 1.1;
          text-align: right;
          text-transform: none;
        }
        .feuilleton-page .panel-body > .task-box,
        .feuilleton-page .panel-annotation > .task-box,
        .feuilleton-page .final-task {
          display: none;
        }
        .feuilleton-page .mobile-final-task-card {
          display: grid;
          gap: 13px;
          padding: 16px;
          background: var(--sheet);
          border-width: 1px;
        }
        .feuilleton-page .mobile-final-task-card h3 {
          margin: 5px 0 0;
          font-family: var(--serif);
          font-size: 29px;
          font-style: italic;
          line-height: 1;
          letter-spacing: 0;
        }
        .feuilleton-page .mobile-final-task-card p {
          margin: 7px 0 0;
          color: var(--ink-2);
          font-size: 14px;
          line-height: 1.35;
        }
        .feuilleton-page .vocabulary-recap {
          gap: 12px;
          padding: 16px;
          background: var(--sheet);
        }
        .feuilleton-page .vocabulary-recap header {
          display: grid;
          gap: 10px;
          align-items: start;
        }
        .feuilleton-page .vocabulary-recap h3 {
          font-size: 27px;
        }
        .feuilleton-page .vocabulary-recap header a {
          width: fit-content;
          white-space: normal;
        }
        .feuilleton-page .vocabulary-credit-row,
        .feuilleton-page .vocabulary-recap-list {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .feuilleton-page .vocabulary-credit-row span {
          border-bottom: 1px solid var(--ink);
        }
        .feuilleton-page .vocabulary-credit-row span:nth-child(2n) {
          border-right: 0;
        }
        .feuilleton-page .vocabulary-recap-list a {
          padding: 9px 10px;
        }
        .feuilleton-page .mobile-task-sheet-status {
          display: grid;
          gap: 3px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          box-shadow: inset 5px 0 0 var(--blue);
          padding: 10px 12px;
        }
        .feuilleton-page .mobile-task-sheet-status span {
          color: var(--ink-3);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .feuilleton-page .mobile-task-sheet-status strong {
          font-family: var(--serif);
          font-size: 22px;
          font-style: italic;
          line-height: 1;
        }
        .feuilleton-page .mobile-correction-note,
        .feuilleton-page .mobile-submit-error {
          display: grid;
          gap: 5px;
          border: 1px solid var(--ink);
          background: rgba(216,50,26,.1);
          border-left: 5px solid var(--red);
          padding: 10px 12px;
          line-height: 1.35;
          animation: feuilleton-feedback-slip 180ms ease-out both;
        }
        .feuilleton-page .mobile-correction-note strong,
        .feuilleton-page .mobile-submit-error button {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 10px;
          letter-spacing: .12em;
          text-transform: uppercase;
          font-weight: 900;
        }
        .feuilleton-page .mobile-correction-note span,
        .feuilleton-page .mobile-submit-error span {
          color: var(--ink-2);
          overflow-wrap: anywhere;
        }
        .feuilleton-page .mobile-correction-note em {
          width: fit-content;
          border: 1px solid var(--red);
          color: var(--red);
          background: var(--sheet);
          padding: 3px 7px;
          font-style: normal;
          font-size: 10px;
          font-weight: 900;
        }
        .feuilleton-page .mobile-correction-note.positive {
          background: rgba(63,122,75,.12);
          border-left-color: var(--green);
        }
        .feuilleton-page .mobile-submit-error {
          background: rgba(216,50,26,.12);
          border-left: 5px solid var(--red);
        }
        .feuilleton-page .mobile-submit-error button {
          width: fit-content;
          min-height: 32px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 0 12px;
        }
        .feuilleton-page .task-box {
          min-width: 0;
          padding: 12px;
          gap: 10px;
        }
        .feuilleton-page .task-prompt,
        .feuilleton-page .task-box input,
        .feuilleton-page .task-box textarea {
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
        .feuilleton-page .task-box input,
        .feuilleton-page .task-box textarea {
          box-shadow: 3px 3px 0 var(--ink);
        }
        .feuilleton-page .mobile-bottom-sheet-layer {
          position: fixed;
          inset: 0;
          z-index: 92;
          display: block;
        }
        .feuilleton-page .mobile-bottom-sheet-backdrop {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          background: rgba(20,17,13,.4);
          animation: feuilleton-task-scrim 280ms ease-out both;
        }
        .feuilleton-page .mobile-task-flyin {
          position: absolute;
          left: 0;
          right: 0;
          bottom: 0;
          display: grid;
          gap: 12px;
          width: 100%;
          max-height: min(78svh, 620px);
          overflow: auto;
          border: 1px solid var(--ink);
          border-left: 0;
          border-right: 0;
          border-bottom: 0;
          background: var(--paper);
          padding: 10px 14px calc(18px + env(safe-area-inset-bottom));
          box-shadow: 0 -20px 40px rgba(20,17,13,.18);
          animation: feuilleton-task-sheet 280ms ease-out both;
        }
        .feuilleton-page .mobile-task-flyin .mobile-bottom-sheet-body {
          display: grid;
          gap: 12px;
          padding-top: 12px;
        }
        .feuilleton-page .mobile-sheet-grabber {
          justify-self: center;
          width: 36px;
          height: 4px;
          border-radius: 999px;
          background: var(--ink-3);
        }
        .feuilleton-page .mobile-task-flyin header {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 12px;
          align-items: start;
          padding-bottom: 10px;
          border-bottom: 1px solid var(--ink);
        }
        .feuilleton-page .mobile-task-flyin header strong {
          display: block;
          overflow: hidden;
          margin-top: 3px;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-family: var(--serif);
          font-size: 24px;
          font-style: italic;
          line-height: 1;
        }
        .feuilleton-page .mobile-task-flyin .mobile-bottom-sheet-title {
          margin-top: 4px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-family: var(--serif);
          font-size: 24px;
          font-style: italic;
          line-height: 1;
        }
        .feuilleton-page .mobile-task-flyin header small {
          display: block;
          margin-top: 4px;
          color: var(--ink-2);
          font-size: 12px;
          font-weight: 800;
          line-height: 1.25;
        }
        .feuilleton-page .mobile-task-flyin .mobile-bottom-sheet-description {
          display: block;
          margin-top: 4px;
          color: var(--ink-2);
          font-size: 12px;
          font-weight: 800;
          line-height: 1.25;
        }
        .feuilleton-page .mobile-task-flyin header button,
        .feuilleton-page .mobile-task-flyin footer button {
          min-height: 44px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          padding: 0 10px;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }
        .feuilleton-page .mobile-task-flyin .task-box {
          max-height: none;
        }
        .feuilleton-page .mobile-task-flyin footer {
          position: sticky;
          bottom: calc(-18px - env(safe-area-inset-bottom));
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 8px;
          margin: 0 -14px calc(-18px - env(safe-area-inset-bottom));
          padding: 10px 14px calc(18px + env(safe-area-inset-bottom));
          border-top: 1px solid var(--ink);
          background: var(--paper);
        }
        .feuilleton-page .mobile-task-flyin footer button:last-child {
          background: var(--ink);
          color: var(--paper);
        }
        .feuilleton-page .mobile-task-flyin footer button:disabled {
          opacity: .45;
          cursor: not-allowed;
        }
        .feuilleton-page .complete-row {
          display: none;
        }
        .feuilleton-page .mobile-completion-card {
          display: grid;
          gap: 14px;
          padding: 18px;
          background: var(--sheet);
          border-width: 1px;
        }
        .feuilleton-page .mobile-completion-card h3 {
          margin: 0;
          font-family: var(--serif);
          font-size: 30px;
          font-style: italic;
          line-height: 1;
          letter-spacing: 0;
        }
        .feuilleton-page .mobile-completion-card p {
          margin: 0;
          color: var(--ink-2);
          line-height: 1.4;
        }
        .feuilleton-page .mobile-completion-stats {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          border: 1px solid var(--ink);
          background: var(--paper-2);
        }
        .feuilleton-page .mobile-completion-stats div {
          padding: 12px;
        }
        .feuilleton-page .mobile-completion-stats div + div {
          border-left: 1px solid var(--ink);
        }
        .feuilleton-page .mobile-completion-stats strong {
          display: block;
          font-size: 26px;
          line-height: 1;
        }
        .feuilleton-page .mobile-completion-stats span {
          display: block;
          margin-top: 5px;
          color: var(--ink-2);
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
        }
        .feuilleton-page .fn-side {
          display: none;
        }
        .feuilleton-page .mobile-reading-bar {
          position: fixed;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 91;
          display: grid;
          grid-template-columns: auto minmax(0, 1fr) auto;
          align-items: center;
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
        .feuilleton-page .mobile-reading-bar button:disabled {
          opacity: .42;
          cursor: not-allowed;
        }
        .feuilleton-page .mobile-reading-bar div {
          min-width: 0;
          text-align: right;
          line-height: 1;
        }
        .feuilleton-page .mobile-reading-bar strong {
          display: block;
          margin-top: 3px;
          font-size: 15px;
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
