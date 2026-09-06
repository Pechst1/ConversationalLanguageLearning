/* DEVELOPMENT-ONLY reader harness.
 *
 * Mounted only from `pages/mobile-visual-qa.tsx`, which is itself dev-only
 * (`getStaticProps` returns notFound in a production build). It exists so the
 * reader's states can be driven without a signed-in session: generation still
 * printing, missing art, a superseded (409) episode, a filed episode, and a
 * revisit versus a live choice.
 *
 * The scene body is a captured REAL response from
 * `GET /api/v1/graphic-novel/scenes/{id}` — the same shapes the reader meets in
 * production, not an idealised hand-written payload. Word help still calls the
 * real `/vocabulary/lookup` and `/atelier/translate` endpoints from here.
 *
 * States: ?reader=ready | printing | missing | stale | filed | answered
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  FeuilletonReader,
  FeuilletonReaderStyles,
  attemptsByTaskId,
  buildReaderStages,
  clampStageIndex,
  liveTaskId as resolveLiveTaskId,
  normalizeReaderPosition,
  readerEpisodeLabel,
  readerLocation,
  readerStorageKey,
  resolveFurthest,
  resolveStartIndex,
} from '@/components/feuilleton/reader';
import { readLocalJson, writeLocalJson } from '@/lib/pilot-resilience';

import generatedScene from './generated-scene.json';

type PreviewState = 'ready' | 'printing' | 'missing' | 'stale' | 'filed' | 'answered';

function sceneForState(state: PreviewState): Record<string, any> {
  const base = JSON.parse(JSON.stringify(generatedScene)) as Record<string, any>;
  if (state === 'printing') {
    base.status = 'generating';
    base.panels[2].image_url = null;
    base.panels[2].image_payload = { url: null };
    base.panels[2].generation_metadata = { image_status: 'queued' };
    base.panels[3].image_url = null;
    base.panels[3].image_payload = { url: null };
    base.panels[3].generation_metadata = { image_status: 'queued' };
  }
  if (state === 'missing') {
    base.panels[1].image_url = null;
    base.panels[1].image_payload = { url: null };
    base.panels[1].generation_metadata = {};
  }
  if (state === 'filed' || state === 'answered') {
    const ids: string[] = [];
    base.panels.forEach((panel: any) => {
      (panel.overlay_payload?.tasks || []).forEach((task: any) => ids.push(String(task.id)));
    });
    if (base.script_payload?.final_prompt?.id) ids.push(String(base.script_payload.final_prompt.id));
    base.attempts = ids.map((id, index) => ({
      task_id: id,
      answer_payload: { answer: index === 0 ? 'Option A' : 'Le reçu devient un exemplaire officiel.' },
      correction: index === 0
        ? { verdict: 'branch', why: 'L’employé range le reçu : l’histoire suit ce choix.' }
        : { verdict: 'correct', why: 'Phrase claire et bien accordée.' },
    }));
    if (state === 'filed') base.status = 'completed';
  }
  return base;
}

const PREVIEW_STATES: PreviewState[] = ['ready', 'printing', 'missing', 'stale', 'filed', 'answered'];

/* Read from the URL directly rather than from the router: this QA page is
   statically generated, so router.query can lag or stay empty. */
function stateFromLocation(): PreviewState | null {
  if (typeof window === 'undefined') return null;
  const value = new URLSearchParams(window.location.search).get('reader');
  if (!value) return null;
  return (PREVIEW_STATES as string[]).includes(value) ? (value as PreviewState) : 'ready';
}

export default function ReaderHarness() {
  // Client-only: the server has no location and no storage, so it renders
  // nothing here and the first client pass renders the requested state. That
  // removes any hydration mismatch from the harness itself.
  // Opt-in only: without ?reader=… this renders nothing and the QA page it is
  // mounted in behaves exactly as before.
  const [state, setState] = useState<PreviewState | null>(null);
  useEffect(() => setState(stateFromLocation()), []);
  const active: PreviewState = state || 'ready';
  const scene = useMemo(() => sceneForState(active), [active]);

  const stages = useMemo(() => buildReaderStages(scene as any), [scene]);
  const stageKeys = useMemo(() => stages.map((entry) => entry.key), [stages]);

  const storageKey = readerStorageKey(`preview-${active}`);
  const [index, setIndex] = useState(0);
  const [furthest, setFurthest] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [restoredFor, setRestoredFor] = useState<string | null>(null);

  useEffect(() => {
    if (restoredFor === storageKey || !stageKeys.length) return;
    const saved = normalizeReaderPosition(readLocalJson(storageKey, {}));
    const start = resolveStartIndex(saved, stageKeys);
    setIndex(start);
    setFurthest(resolveFurthest(saved, stageKeys, start));
    setAnswers(saved.answers);
    setRestoredFor(storageKey);
  }, [restoredFor, stageKeys, storageKey]);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [localAttempts, setLocalAttempts] = useState<Record<string, Record<string, any>>>({});
  const [submitError, setSubmitError] = useState<{ taskId: string; message: string } | null>(null);

  const attempts = useMemo(
    () => ({ ...attemptsByTaskId(scene as any), ...localAttempts }),
    [localAttempts, scene],
  );
  const live = useMemo(() => resolveLiveTaskId(stages, attempts), [attempts, stages]);
  const safeIndex = clampStageIndex(index, stages.length);

  const persist = useCallback(
    (nextIndex: number, nextFurthest: number, nextAnswers: Record<string, string>) => {
      writeLocalJson(storageKey, {
        answers: nextAnswers,
        scrollY: 0,
        stageIndex: nextIndex,
        stageKey: stageKeys[nextIndex] ?? null,
        furthest: nextFurthest,
      });
    },
    [stageKeys, storageKey],
  );

  const onIndexChange = useCallback(
    (next: number) => {
      const raised = Math.max(furthest, next);
      setIndex(next);
      setFurthest(raised);
      persist(next, raised, answers);
    },
    [answers, furthest, persist],
  );

  const setAnswer = useCallback(
    (taskId: string, value: string) => {
      setAnswers((current) => {
        const next = { ...current, [taskId]: value };
        persist(safeIndex, furthest, next);
        return next;
      });
    },
    [furthest, persist, safeIndex],
  );

  /* Stands in for POST /attempts. In `stale` it answers the way a superseded
     episode does (409), so the error path can be seen without a server. */
  const onSubmit = useCallback(
    (task: Record<string, any>) => {
      const taskId = String(task.id || '');
      const answer = (answers[taskId] || '').trim();
      if (!answer) {
        setSubmitError({ taskId, message: 'Écrivez ou choisissez d’abord une réponse.' });
        return;
      }
      setSubmitError(null);
      setSubmitting(taskId);
      window.setTimeout(() => {
        setSubmitting(null);
        if (active === 'stale') {
          setSubmitError({
            taskId,
            message: 'Cet épisode a été remplacé ou déjà classé. Votre texte est conservé ; rouvrez l’épisode courant.',
          });
          return;
        }
        setLocalAttempts((current) => ({
          ...current,
          [taskId]: {
            task_id: taskId,
            answer_payload: { answer },
            correction: task.task_type === 'choice'
              ? { verdict: 'branch', why: 'L’histoire suit ce choix.' }
              : { verdict: 'correct', why: 'Phrase claire.' },
          },
        }));
      }, 400);
    },
    [answers, active],
  );

  if (!state) return null;

  return (
    <>
      <FeuilletonReaderStyles />
      {/* the QA reference layer would otherwise sit on top of the reader */}
      <style jsx global>{`
        [data-mobile-visual-qa],
        .mobile-bottom-sheet-layer { display: none !important; }
      `}</style>
      <section style={{ background: 'var(--app-paper)', paddingBottom: 24 }}>
        <div className="fr-page" style={{ paddingTop: 12, paddingBottom: 0 }}>
          <div className="fr-tools" role="group" aria-label="État du lecteur">
            {PREVIEW_STATES.map((entry) => (
              <a
                key={entry}
                className="fr-chip"
                aria-current={entry === active ? 'page' : undefined}
                data-active={entry === active ? 'true' : undefined}
                href={`?reader=${entry}`}
              >
                {entry}
              </a>
            ))}
          </div>
        </div>
        <FeuilletonReader
          episodeLabel={readerEpisodeLabel(scene as any)}
          title={String(scene.title || 'Le feuilleton')}
          location={readerLocation(scene as any)}
          previously=""
          stages={stages}
          index={safeIndex}
          furthest={furthest}
          onIndexChange={onIndexChange}
          answers={answers}
          setAnswer={setAnswer}
          onSubmit={onSubmit}
          submittingTask={submitting}
          attemptsByTask={attempts}
          submitError={submitError}
          liveTaskId={live}
          onExit={() => { window.location.href = '?reader=ready'; }}
          key={active}
          onComplete={active === 'filed' ? null : () => undefined}
          completing={false}
          filed={active === 'filed'}
          nextHref={active === 'filed' ? '/serial' : null}
          nextLabel="Lire le prochain épisode"
          banner={active === 'stale' ? (
            <div className="fr-notice is-stale" role="status">
              <h2>Cette édition a été remplacée.</h2>
              <p>Votre lecture et vos réponses restent ici. L’épisode courant peut être rouvert quand vous voulez.</p>
              <button type="button" className="fr-btn is-action">Rouvrir l’épisode courant</button>
            </div>
          ) : null}
        />
      </section>
    </>
  );
}
