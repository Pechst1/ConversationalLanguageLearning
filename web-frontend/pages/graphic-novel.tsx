import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';
import { ArrowRight, Check, Loader2, Send, Sparkles } from 'lucide-react';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import apiService, {
  GraphicNovelAttemptResult,
  GraphicNovelPanel,
  GraphicNovelScene,
  GraphicNovelToday,
} from '@/services/api';

type OverlayTask = Record<string, any> & { panel?: GraphicNovelPanel | null };
type PanelBubble = {
  speaker?: string;
  fr?: string;
  en?: string;
  x?: number;
  y?: number;
  tone?: string;
};
type PanelCount = 4 | 6 | 8;
type StoryQuality = 'standard' | 'premium';
type HumorStyle = 'dry' | 'satirical' | 'absurd';
type ExperienceMode = 'study' | 'reward';
type RenderMode = 'page' | 'panels';
type ImageQuality = 'low' | 'medium' | 'high';

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
  const [generationFailure, setGenerationFailure] = useState<Record<string, any> | null>(null);
  const [panelCount, setPanelCount] = useState<PanelCount>(6);
  const [storyQuality, setStoryQuality] = useState<StoryQuality>('standard');
  const [humorStyle, setHumorStyle] = useState<HumorStyle>('satirical');
  const experienceMode: ExperienceMode = 'study';
  const [renderMode, setRenderMode] = useState<RenderMode>('panels');
  const [imageQuality, setImageQuality] = useState<ImageQuality>('medium');

  const tasks = useMemo(() => extractTasks(scene), [scene]);
  const attemptsByTask = useMemo(() => {
    const map: Record<string, Record<string, any>> = {};
    (scene?.attempts || []).forEach((attempt) => {
      if (attempt.task_id) map[attempt.task_id] = attempt;
    });
    return map;
  }, [scene?.attempts]);

  useEffect(() => {
    if (!router.isReady) return;
    void loadInitial();
  }, [router.isReady, router.query.scene]);

  async function loadInitial() {
    setLoading(true);
    try {
      const sceneId = typeof router.query.scene === 'string' ? router.query.scene : null;
      if (sceneId) {
        const loaded = await apiService.getGraphicNovelScene(sceneId);
        setScene(loaded);
        setGenerationFailure(null);
        return;
      }
      const next = await apiService.getGraphicNovelToday();
      setToday(next);
      setScene(next.active_scene || next.available_scene || null);
      setGenerationFailure(null);
    } catch {
      toast.error('Could not load Feuilleton.');
    } finally {
      setLoading(false);
    }
  }

  async function createScene(extra?: Record<string, any>) {
    setCreating(true);
    if (!scene) setGenerationFailure(null);
    const toastId = toast.loading('Writing the gag and generating medium image panels. This can take a few minutes.');
    try {
      const conceptIds = queryList(router.query.concept_id).map(Number).filter(Boolean);
      const errataIds = queryList(router.query.erratum_id);
      const atelierSessionId = typeof router.query.atelier_session_id === 'string' ? router.query.atelier_session_id : undefined;
      const missionId = typeof router.query.mission_id === 'string' ? router.query.mission_id : undefined;
      const next = await apiService.createGraphicNovelScene({
        cadence: atelierSessionId ? 'post_session' : 'ad_hoc',
        atelier_session_id: atelierSessionId,
        mission_id: missionId,
        preferred_concept_ids: conceptIds.length ? conceptIds : undefined,
        preferred_errata_ids: errataIds.length ? errataIds : undefined,
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
      setScene(next);
      setGenerationFailure(null);
      setLastCorrection(null);
      router.replace({ pathname: '/graphic-novel', query: { scene: next.id } }, undefined, { shallow: true });
      toast.success('Feuilleton ready.', { id: toastId });
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

  async function submitTask(task: OverlayTask) {
    if (!scene) return;
    const answer = (answers[task.id] || '').trim();
    if (!answer) {
      toast.error('Write or choose an answer first.');
      return;
    }
    setSubmittingTask(task.id);
    try {
      const result: GraphicNovelAttemptResult = await apiService.submitGraphicNovelAttempt(scene.id, {
        task_id: task.id,
        answer_payload: { answer },
      });
      setScene(result.scene);
      setLastCorrection(result.correction);
    } catch {
      toast.error('The Feuilleton correction could not be submitted.');
    } finally {
      setSubmittingTask(null);
    }
  }

  async function completeScene() {
    if (!scene) return;
    setCompleting(true);
    try {
      const result = await apiService.completeGraphicNovelScene(scene.id);
      setScene(result.scene);
      toast.success('Feuilleton complete.');
    } catch {
      toast.error('Could not complete Feuilleton.');
    } finally {
      setCompleting(false);
    }
  }

  return (
    <>
      <FeuilletonStyles />
      <main className="feuilleton-page">
        <EditorialMasthead active="feuilleton" />

        <div className="fn-spread fn-grid">
          <section className="fn-main">
            <div className="fn-title">
              <div>
                <div className="t-mono">PERSONAL INPUT FEED</div>
                <h1>Feuilleton</h1>
              </div>
              <div className="create-console">
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
              </div>
            </div>

            {creating && (
              <section className="paper generation-progress">
                <Loader2 className="spin" size={18} />
                <div>
                  <strong>Writing the visual gag, then generating six medium image panels</strong>
                  <p>The image model is the slow part. Medium quality stays on because low quality was not strong enough.</p>
                </div>
              </section>
            )}

            {loading ? (
              <div className="paper loading"><Loader2 className="spin" /> LOADING FEUILLETON</div>
            ) : generationFailure ? (
              <EditionPreparing onRetry={() => createScene()} creating={creating} />
            ) : scene ? (
              <>
                <SceneBrief scene={scene} />
                {scene.script_payload?.render_mode === 'page' ? (
                  <PageScene
                    scene={scene}
                    answers={answers}
                    setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                    onSubmit={submitTask}
                    submittingTask={submittingTask}
                    attemptsByTask={attemptsByTask}
                  />
                ) : (
                  <section className="panel-grid">
                    {(scene.panels || []).map((panel) => (
                      <PanelCard
                        key={panel.id}
                        panel={panel}
                        answers={answers}
                        setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                        onSubmit={submitTask}
                        submittingTask={submittingTask}
                        attemptsByTask={attemptsByTask}
                      />
                    ))}
                  </section>
                )}
                <FinalTask
                  scene={scene}
                  answers={answers}
                  setAnswer={(taskId, value) => setAnswers((current) => ({ ...current, [taskId]: value }))}
                  onSubmit={submitTask}
                  submittingTask={submittingTask}
                  attemptsByTask={attemptsByTask}
                />
                <div className="complete-row">
                  <button className="btn solid lg" disabled={completing || scene.status === 'completed'} onClick={completeScene}>
                    {scene.status === 'completed' ? 'FEUILLETON COMPLETE' : 'COMPLETE FEUILLETON'} <Check size={15} />
                  </button>
                </div>
              </>
            ) : (
              <div className="paper empty-state">
                <p>No Feuilleton scene yet.</p>
                <button className="btn red" disabled={creating} onClick={() => createScene()}>
                  CREATE FIRST SCENE <ArrowRight size={14} />
                </button>
              </div>
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

function SceneBrief({ scene }: { scene: GraphicNovelScene }) {
  const source = scene.source_snapshot || {};
  const sourceItem = (source.items || [])[0] || {};
  const showSource = Boolean(source.mode && source.mode !== 'atelier_curated' && (source.title || sourceItem.title));
  const imageStatus = sceneImageStatus(scene);
  const script = scene.script_payload || {};
  const cost = script.estimated_cost || {};
  const sourceCopy = feuilletonSourceCopy(source, script);
  const publicBrief = feuilletonPublicBrief(scene.brief);
  return (
    <section className="paper scene-brief">
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
      <h2>{scene.title}</h2>
      {publicBrief && <p>{publicBrief}</p>}
      {showSource && (
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
      )}
    </section>
  );
}

function EditionPreparing({ onRetry, creating }: { onRetry: () => void; creating: boolean }) {
  return (
    <section className="paper edition-preparing">
      <div>
        <div className="t-mono">TODAY&apos;S EDITION</div>
        <h2>No complete edition returned.</h2>
        <p>This state is reserved for hard service failures, not a quality judgment. Try again, or continue in Atelier while the image service catches up.</p>
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
}: {
  scene: GraphicNovelScene;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
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
          {pageImage?.url ? <img src={pageImage.url} alt="" /> : <ComicFallbackPanel panel={fallbackPanel as GraphicNovelPanel} />}
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
}: {
  panel: GraphicNovelPanel;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
}) {
  const overlay = panel.overlay_payload || {};
  const tasks = (overlay.tasks || []) as OverlayTask[];
  const caption = overlay.caption || {};
  const bubbles = (overlay.bubbles || []) as PanelBubble[];
  return (
    <article className="paper panel-annotation">
      <div className="panel-head">
        <span className="t-mono">PANEL {panel.panel_index}</span>
        <strong>{panel.title}</strong>
      </div>
      <BubbleTranscript bubbles={bubbles} />
      {caption.fr ? (
        <CaptionBlock caption={caption} />
      ) : (
        <p>{panel.beat}</p>
      )}
      {tasks.map((task) => (
        <TaskControls
          key={task.id}
          task={{ ...task, panel }}
          value={answers[task.id] || ''}
          setValue={(value) => setAnswer(task.id, value)}
          onSubmit={() => onSubmit({ ...task, panel })}
          submitting={submittingTask === task.id}
          attempt={attemptsByTask[task.id]}
        />
      ))}
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
}: {
  panel: GraphicNovelPanel;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
}) {
  const overlay = panel.overlay_payload || {};
  const tasks = (overlay.tasks || []) as OverlayTask[];
  const fallbackPanel = isFallbackPanel(panel);
  const caption = overlay.caption || {};
  const bubbles = (overlay.bubbles || []) as PanelBubble[];
  return (
    <article className="panel-card">
      <div className={`panel-image ${fallbackPanel ? 'fallback-panel' : 'generated-panel'}`}>
        {fallbackPanel ? (
          <ComicFallbackPanel panel={panel} />
        ) : (
          panel.image_url && <img src={panel.image_url} alt="" />
        )}
        <BubbleOverlay bubbles={bubbles} />
      </div>
      <div className="panel-body">
        <div className="panel-head">
          <span className="t-mono">PANEL {panel.panel_index}</span>
          <strong>{panel.title}</strong>
        </div>
        {caption.fr ? (
          <CaptionBlock caption={caption} />
        ) : (
          <p>{panel.beat}</p>
        )}
        {tasks.map((task) => (
          <TaskControls
            key={task.id}
            task={{ ...task, panel }}
            value={answers[task.id] || ''}
            setValue={(value) => setAnswer(task.id, value)}
            onSubmit={() => onSubmit({ ...task, panel })}
            submitting={submittingTask === task.id}
            attempt={attemptsByTask[task.id]}
          />
        ))}
      </div>
    </article>
  );
}

function BubbleOverlay({ bubbles }: { bubbles: PanelBubble[] }) {
  const visible = bubbles.filter((bubble) => bubble?.fr);
  if (!visible.length) return null;
  return (
    <div className="bubble-layer" aria-label="Panel dialogue">
      {visible.slice(0, 2).map((bubble, index) => (
        <div
          className={`speech-bubble bubble-${index + 1} tone-${bubble.tone || 'deadpan'}`}
          key={`${bubble.speaker || 'bubble'}-${index}`}
          style={{
            left: `${clampPercent(bubble.x, index === 0 ? 12 : 54)}%`,
            top: `${clampPercent(bubble.y, index === 0 ? 12 : 28)}%`,
          }}
        >
          {bubble.speaker && <span>{bubble.speaker}</span>}
          <p>{bubble.fr}</p>
          {bubble.en && (
            <details className="bubble-translation">
              <summary>EN</summary>
              <p>{bubble.en}</p>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

function BubbleTranscript({ bubbles }: { bubbles: PanelBubble[] }) {
  const visible = bubbles.filter((bubble) => bubble?.fr);
  if (!visible.length) return null;
  return (
    <div className="bubble-transcript">
      {visible.slice(0, 2).map((bubble, index) => (
        <blockquote key={`${bubble.speaker || 'bubble'}-${index}`}>
          {bubble.speaker && <span>{bubble.speaker}</span>}
          <p>{bubble.fr}</p>
          {bubble.en && <small>{bubble.en}</small>}
        </blockquote>
      ))}
    </div>
  );
}

function clampPercent(value: number | undefined, fallback: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return fallback;
  return Math.max(4, Math.min(64, value));
}

function CaptionBlock({ caption }: { caption: any }) {
  return (
    <div className="panel-caption">
      <p className="caption-fr">{caption.fr}</p>
      {caption.en && (
        <details className="caption-translation">
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
    .replace(/\s*The scene should fictionalize[^.]*\./gi, '')
    .replace(/\s*avoid depicting real politicians[^.]*\./gi, '')
    .replace(/\s*keep the humour dry rather than cruel\.?/gi, '')
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

function ComicFallbackPanel({ panel }: { panel: GraphicNovelPanel }) {
  const variant = ((panel.panel_index - 1) % 4) + 1;
  return (
    <div className={`comic-fallback comic-${variant}`} aria-hidden="true">
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
}: {
  scene: GraphicNovelScene;
  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: OverlayTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
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
}: {
  task: OverlayTask;
  value: string;
  setValue: (value: string) => void;
  onSubmit: () => void;
  submitting: boolean;
  attempt?: Record<string, any>;
}) {
  const correction = attempt?.correction;
  const isClosed = task.task_type === 'cloze' || task.task_type === 'choice';
  const isCorrect = correction?.verdict === 'correct' || correction?.verdict === 'accepted';
  const verdictLabel = correction?.verdict
    ? String(correction.verdict).replace(/_/g, ' ')
    : '';
  const promptTranslation = task.prompt_translation || task.translation || task.prompt_en;
  const instruction = displayTaskInstruction(task);
  return (
    <div className={`task-box ${correction ? correction.verdict : ''}`}>
      <div className="task-title">
        <span>{task.label || task.task_type}</span>
        <small>{instruction}</small>
      </div>
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
      {Array.isArray(task.options) && (
        <div className="option-row">
          {task.options.map((option: string) => (
            <button key={option} className={value === option ? 'selected' : ''} onClick={() => setValue(option)}>
              {option}
            </button>
          ))}
        </div>
      )}
      {isClosed ? (
        <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="Your answer" />
      ) : (
        <textarea value={value} onChange={(event) => setValue(event.target.value)} placeholder={task.placeholder || 'Write one short sentence.'} />
      )}
      {correction && (
        <div className="inline-feedback">
          <strong>{verdictLabel}</strong>
          {!isCorrect && correction.corrected_answer && <p><b>Better line.</b> {correction.corrected_answer}</p>}
          {correction.why && <p><b>Why.</b> {correction.why}</p>}
          {correction.repair && <p><b>Repair.</b> {correction.repair}</p>}
        </div>
      )}
      <button className="btn solid" disabled={submitting || Boolean(attempt)} onClick={onSubmit}>
        {attempt ? 'SUBMITTED' : submitting ? 'CHECKING' : 'SUBMIT'} <Send size={13} />
      </button>
    </div>
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
      {errata.slice(0, 5).map((item: any, index: number) => (
        <article key={`${item.display_label}-${index}`} className="errata-slip">
          <span className="slip-label">{item.display_label}</span>
          <span className="slip-num">Nº {String(index + 1).padStart(2, '0')}</span>
          <div className="t-mono-low">YOU WROTE</div>
          <p className="wrong">{item.learner_text}</p>
          <div className="t-mono-low red">CORRECTED</div>
          <p className="right">{item.corrected_target}</p>
          <div className="why">
            <p><strong>Why.</strong> {item.why_wrong}</p>
            <p><strong>Repair.</strong> {item.repair_hint}</p>
          </div>
          {item.concept_id && <Link className="notebook-link" href={`/grammar?concept=${item.concept_id}`}>Review rule ↗</Link>}
        </article>
      ))}
    </section>
  );
}

function extractTasks(scene: GraphicNovelScene | null): OverlayTask[] {
  if (!scene) return [];
  if (scene.script_payload?.experience_mode === 'reward') return [];
  const panelTasks = (scene.panels || []).flatMap((panel) => ((panel.overlay_payload?.tasks || []) as OverlayTask[]).map((task) => ({ ...task, panel })));
  const finalPrompt = scene.script_payload?.final_prompt?.id ? [{ ...scene.script_payload.final_prompt, panel: null }] : [];
  return [...panelTasks, ...finalPrompt];
}

function queryList(value: string | string[] | undefined): string[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function FeuilletonStyles() {
  return (
    <style jsx global>{`
      .feuilleton-page {
        --paper: #f1ece1;
        --paper-2: #e8e0cf;
        --paper-3: #d8cdb6;
        --ink: #14110d;
        --ink-2: #4a4538;
        --ink-3: #8a826f;
        --red: #d8321a;
        --blue: #1d3a8a;
        --yellow: #f3c318;
        --serif: "EB Garamond", Garamond, "Times New Roman", serif;
        --grotesk: "Inter", "Helvetica Neue", Arial, sans-serif;
        min-height: 100vh;
        background: var(--paper);
        color: var(--ink);
        font-family: var(--grotesk);
      }
      .feuilleton-page * { box-sizing: border-box; }
      .feuilleton-page button, .feuilleton-page input, .feuilleton-page textarea { font: inherit; color: inherit; }
      .feuilleton-page button { border: 0; background: transparent; cursor: pointer; }
      .fn-spread { width: min(1320px, 100%); margin: 0 auto; padding: 0 clamp(22px, 4vw, 48px); }
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
      .story-card { margin-top: 18px; border-left: 4px solid var(--blue); background: var(--paper-2); padding: 14px 18px; max-width: 780px; }
      .story-card p { margin: 8px 0 0; color: var(--ink-2); line-height: 1.45; }
      .source-card { margin-top: 18px; border-left: 4px solid var(--yellow); background: var(--paper-2); padding: 14px 18px; max-width: 780px; }
      .source-card strong { display: block; margin: 8px 0; font-size: 18px; line-height: 1.15; }
      .source-card p { margin: 0; color: var(--ink-2); line-height: 1.45; }
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
      .panel-annotation { padding: 18px; display: grid; gap: 12px; background: var(--paper); }
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
      .panel-card { border: 2px solid var(--ink); background: var(--paper); overflow: hidden; }
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
        pointer-events: auto;
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
      .bubble-translation {
        margin-top: 6px;
        border-top: 1px solid var(--paper-3);
        padding-top: 4px;
        font-size: 11px;
        color: var(--ink-2);
      }
      .bubble-translation summary {
        cursor: pointer;
        font-family: var(--mono);
        letter-spacing: .12em;
        font-size: 9px;
        color: var(--blue);
      }
      .bubble-translation p {
        margin-top: 3px;
        font-family: var(--sans);
        font-size: 12px;
        font-style: normal;
        line-height: 1.25;
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
      }
      .bubble-transcript p {
        margin: 0;
        font-family: var(--serif);
        font-size: 21px;
        font-style: italic;
        line-height: 1.15;
      }
      .bubble-transcript small {
        display: block;
        margin-top: 5px;
        color: var(--ink-2);
        line-height: 1.3;
      }
      .panel-body { padding: 18px; display: grid; gap: 14px; }
      .panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--paper-3); padding-bottom: 9px; }
      .panel-body > p { margin: 0; color: var(--ink-2); line-height: 1.4; }
      .panel-caption {
        display: grid;
        gap: 7px;
        border-left: 4px solid var(--blue);
        background: var(--paper-2);
        padding: 12px 14px;
      }
      .panel-caption p { margin: 0; }
      .caption-fr {
        font-family: var(--serif);
        font-size: 24px;
        line-height: 1.12;
        font-style: italic;
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
      .option-row { display: flex; flex-wrap: wrap; gap: 8px; }
      .option-row button { border: 1px solid var(--ink); background: var(--paper); padding: 8px 10px; font-family: var(--serif); font-size: 18px; font-style: italic; }
      .option-row button.selected { background: var(--ink); color: var(--paper); }
      .task-box input, .task-box textarea { width: 100%; border: 1px solid var(--ink); background: var(--paper); padding: 11px 12px; outline: none; box-shadow: 4px 4px 0 var(--ink); font-family: var(--serif); font-size: 20px; font-style: italic; }
      .task-box textarea { min-height: 100px; resize: vertical; }
      .inline-feedback { border-left: 4px solid var(--blue); background: rgba(255,255,255,.35); padding: 10px 12px; }
      .inline-feedback p { margin: 4px 0 0; line-height: 1.35; }
      .final-task { padding: 24px 28px; background: var(--paper); display: grid; gap: 16px; }
      .final-task h3 { margin: 6px 0 0; font-size: 30px; line-height: 1; letter-spacing: -.035em; }
      .final-task p { margin: 8px 0 0; color: var(--ink-2); line-height: 1.45; }
      .complete-row { display: flex; justify-content: flex-end; }
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
    `}</style>
  );
}
