/* The Feuilleton, read as a graphic novel: one panel at a time, with an obvious
   way forward and back.
 *
 * Contract this component keeps:
 *   · Navigation is *only* navigation. Moving between panels sends nothing to
 *     the server — no attempt, no advance, no completion. Revisiting a panel
 *     therefore cannot replay a choice or file an episode twice.
 *   · A revisited panel says so; the one place the learner is being asked to act
 *     says so differently, in the action colour.
 *   · A learner is never blocked by an exercise: Suivant stays live whether or
 *     not the panel's task has been answered.
 *   · Word help never moves the learner's place.
 *   · Missing art, art still printing and an unavailable episode are stated, not
 *     papered over.
 *
 * The visual system is the Claude overhaul: rounded surfaces, sentence case, one
 * Garamond italic headline per screen, one 3D-press primary, blue = story,
 * red = action, ink = done, plus the world-bible character accents. */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  AtelierV2Root,
  CheckIcon,
  CrossIcon,
  SpinnerToken,
} from '@/components/atelier-v2/ui';
import { resolveMediaUrl } from '@/lib/media-url';

import { TappableFrench } from './TappableFrench';
import { WordHelpSheet, type WordHelpRequest } from './WordHelpSheet';
import {
  choiceOptions,
  correctionIsBranch,
  correctionIsPositive,
  correctionLine,
  stageReadState,
  stageTaskIds,
  taskIsChoice,
  taskIsClosed,
  taskPromptLine,
  taskPromptTranslation,
  type ReaderStage,
  type ReaderTask,
} from './panel-model';

export type ReaderSubmitError = { taskId: string; message: string } | null;

export type FeuilletonReaderProps = {
  /** the running head: eyebrow + the one Garamond italic headline */
  episodeLabel: string;
  title: string;
  location?: string;
  previously?: string;

  stages: ReaderStage[];
  index: number;
  furthest: number;
  onIndexChange: (next: number) => void;

  answers: Record<string, string>;
  setAnswer: (taskId: string, value: string) => void;
  onSubmit: (task: ReaderTask) => void;
  submittingTask: string | null;
  attemptsByTask: Record<string, Record<string, any>>;
  submitError: ReaderSubmitError;
  /** the one task that currently accepts a submission, chosen in reading order */
  liveTaskId: string | null;

  onExit: () => void;
  /** absent while the episode is still being generated, or when already filed */
  onComplete?: (() => void) | null;
  completing?: boolean;
  /** Label of the closing primary. The daily journey says "Continuer". */
  completeLabel?: string;
  filed?: boolean;
  nextHref?: string | null;
  nextLabel?: string;
  /** shown above the stage when the server says art is still being produced */
  banner?: React.ReactNode;
};

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

const SWIPE_DISTANCE = 48;

export function FeuilletonReader({
  episodeLabel,
  title,
  location,
  previously,
  stages,
  index,
  furthest,
  onIndexChange,
  answers,
  setAnswer,
  onSubmit,
  submittingTask,
  attemptsByTask,
  submitError,
  liveTaskId,
  onExit,
  onComplete,
  completing = false,
  completeLabel = 'Terminer l’épisode',
  filed = false,
  nextHref,
  nextLabel,
  banner,
}: FeuilletonReaderProps) {
  const [help, setHelp] = useState<WordHelpRequest | null>(null);
  const [translated, setTranslated] = useState<Record<string, boolean>>({});
  const rootRef = useRef<HTMLElement | null>(null);
  const swipeRef = useRef<{ x: number; y: number } | null>(null);
  const firstRenderRef = useRef(true);

  const count = stages.length;
  const safeIndex = count ? Math.min(Math.max(index, 0), count - 1) : 0;
  const stage = count ? stages[safeIndex] : null;
  const isFirst = safeIndex <= 0;
  const isLast = safeIndex >= count - 1;

  const go = useCallback(
    (next: number) => {
      if (!count) return;
      const clamped = Math.min(Math.max(next, 0), count - 1);
      if (clamped === safeIndex) return;
      onIndexChange(clamped);
    },
    [count, onIndexChange, safeIndex],
  );

  /* Keyboard: arrows page, Home/End jump. Never while typing an answer, and
     never while the help sheet owns the keyboard. */
  useEffect(() => {
    if (help) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || target?.isContentEditable) return;
      if (event.key === 'ArrowRight') {
        event.preventDefault();
        go(safeIndex + 1);
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        go(safeIndex - 1);
      } else if (event.key === 'Home') {
        event.preventDefault();
        go(0);
      } else if (event.key === 'End') {
        event.preventDefault();
        go(count - 1);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [count, go, help, safeIndex]);

  /* Bring the new panel into view without stealing focus from Suivant. */
  useEffect(() => {
    if (firstRenderRef.current) {
      firstRenderRef.current = false;
      return;
    }
    const node = rootRef.current;
    if (!node) return;
    node.scrollIntoView({ block: 'start', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }, [safeIndex]);

  const onPointerDown = useCallback((event: React.PointerEvent) => {
    if (event.pointerType === 'mouse') return;
    const target = event.target as HTMLElement | null;
    if (target?.closest('button, a, input, textarea, select')) {
      swipeRef.current = null;
      return;
    }
    swipeRef.current = { x: event.clientX, y: event.clientY };
  }, []);

  const onPointerUp = useCallback(
    (event: React.PointerEvent) => {
      const start = swipeRef.current;
      swipeRef.current = null;
      if (!start) return;
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      if (Math.abs(dx) < SWIPE_DISTANCE || Math.abs(dx) < Math.abs(dy) * 1.4) return;
      go(dx < 0 ? safeIndex + 1 : safeIndex - 1);
    },
    [go, safeIndex],
  );

  const readState = useMemo(
    () => (stage ? stageReadState(stage, { furthestOrdinal: furthest + 1, liveTaskId }) : 'ahead'),
    [furthest, liveTaskId, stage],
  );

  const stageLiveTask = useMemo(() => {
    if (!stage || !liveTaskId) return null;
    return stage.tasks.find((task) => String(task.id) === liveTaskId) || null;
  }, [liveTaskId, stage]);

  /* Exactly one tactile 3D press on screen. It belongs to whatever the learner
     is actually being asked to do here. */
  const primary: 'task' | 'complete' | 'next' | 'link' =
    stageLiveTask && !attemptsByTask[String(stageLiveTask.id)]
      ? 'task'
      : isLast && filed && nextHref
        ? 'link'
        : isLast && onComplete
          ? 'complete'
          : 'next';

  const openHelp = useCallback(
    (word: { surface: string; term: string }, context: { sentence: string; sentenceEn?: string; character?: string; speaker?: string }) => {
      setHelp({
        surface: word.surface,
        term: word.term,
        sentence: context.sentence,
        sentenceEn: context.sentenceEn,
        character: context.character,
        speaker: context.speaker,
      });
    },
    [],
  );

  if (!stage) return null;

  const stageKey = stage.key;
  const showTranslation = Boolean(translated[stageKey]);
  const hasEnglish =
    stage.kind === 'panel' && stage.lines.some((line) => Boolean(line.en));

  const railPct = count > 1 ? Math.round(((safeIndex + 1) / count) * 100) : 100;
  const positionLabel =
    stage.kind === 'resolution'
      ? `Fin de l’épisode, ${safeIndex + 1} sur ${count}`
      : `Planche ${safeIndex + 1} sur ${count}`;

  return (
    /* The av2 root supplies the tokens and the `.av2` ancestor every reader
       rule is written against; the reader itself stays the section. */
    <AtelierV2Root as="div" className="fr-scope">
    <section className="fr-reader" aria-label="Lecteur du feuilleton" ref={rootRef}>
      <div className="fr-bar">
        <button type="button" className="fr-icon-btn" onClick={onExit} aria-label="Quitter la lecture">
          <CrossIcon size={16} />
        </button>
        <div
          className="fr-rail"
          role="progressbar"
          aria-valuemin={1}
          aria-valuemax={count}
          aria-valuenow={safeIndex + 1}
          aria-label="Avancement dans l’épisode"
        >
          <i style={{ width: `${railPct}%` }} />
        </div>
        <span className="fr-count" aria-hidden="true">
          {safeIndex + 1} / {count}
        </span>
      </div>

      <div className="fr-head">
        <p className="fr-eyebrow">
          {[episodeLabel, location].filter(Boolean).join(' · ')}
        </p>
        {/* the one Garamond italic headline on this screen */}
        <h1 className="fr-title">{title}</h1>
        {previously && safeIndex === 0 && <p className="fr-previously">Précédemment — {previously}</p>}
      </div>

      {banner}

      <p className="fr-sr" role="status" aria-live="polite">
        {positionLabel}
      </p>

      <div
        className="fr-stage"
        data-char={stage.character || undefined}
        data-kind={stage.kind}
        role="group"
        aria-roledescription="planche"
        aria-label={positionLabel}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={() => {
          swipeRef.current = null;
        }}
      >
        {readState === 'read' && (
          <p className="fr-state">
            <span className="tok" aria-hidden="true">
              <CheckIcon size={11} />
            </span>
            Déjà lu · vous relisez cette planche
          </p>
        )}
        {readState !== 'read' && stageLiveTask && (
          <p className="fr-state is-live">
            <span className="tok" aria-hidden="true" />
            À vous de répondre sur cette planche
          </p>
        )}

        {stage.kind === 'panel' ? (
          <PanelBody
            stage={stage}
            showTranslation={showTranslation}
            onWord={openHelp}
          />
        ) : (
          <ResolutionBody stage={stage} />
        )}

        {stage.kind === 'panel' && hasEnglish && (
          <div className="fr-tools">
            <button
              type="button"
              className="fr-chip"
              aria-pressed={showTranslation}
              onClick={() => setTranslated((current) => ({ ...current, [stageKey]: !current[stageKey] }))}
            >
              <span className="sq" aria-hidden="true" />
              {showTranslation ? 'Masquer la traduction' : 'Traduire la planche'}
            </button>
          </div>
        )}

        {stage.tasks.map((task) => {
          const taskId = String(task.id || '');
          const attempt = attemptsByTask[taskId];
          const live = taskId === liveTaskId;
          if (!attempt && !live) {
            return (
              <p className="fr-notice is-stale" key={taskId}>
                <span className="fr-sheet-note">
                  Cette réplique s’ouvre après celle qui la précède dans l’épisode.
                </span>
              </p>
            );
          }
          return (
            <TaskCard
              key={taskId}
              task={task}
              value={answers[taskId] || ''}
              setValue={(value) => setAnswer(taskId, value)}
              onSubmit={() => onSubmit(task)}
              submitting={submittingTask === taskId}
              attempt={attempt}
              submitError={submitError}
              press={primary === 'task' && live}
              onWord={openHelp}
              character={stage.character}
            />
          );
        })}

        {stage.kind === 'resolution' && filed && (
          <p className="fr-state">
            <span className="tok" aria-hidden="true">
              <CheckIcon size={11} />
            </span>
            Épisode classé
          </p>
        )}
      </div>

      <nav className="fr-nav" aria-label="Navigation dans l’épisode">
        <ol className="fr-dots">
          {stages.map((entry, entryIndex) => {
            const state =
              entryIndex === safeIndex ? 'current' : entryIndex <= furthest ? 'read' : 'ahead';
            return (
              <li key={entry.key}>
                <button
                  type="button"
                  className="fr-dot"
                  data-state={state}
                  data-kind={entry.kind}
                  aria-current={entryIndex === safeIndex ? 'step' : undefined}
                  aria-label={
                    entry.kind === 'resolution'
                      ? 'Aller à la fin de l’épisode'
                      : `Aller à la planche ${entryIndex + 1}`
                  }
                  onClick={() => go(entryIndex)}
                >
                  <span className="glyph" aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ol>

        <div className="fr-nav-row">
          <button
            type="button"
            className="fr-btn fr-prev"
            onClick={() => go(safeIndex - 1)}
            disabled={isFirst}
            aria-label="Planche précédente"
          >
            <ArrowLeftIcon size={18} />
            <span className="fr-sr">Précédent</span>
          </button>

          {isLast ? (
          filed && nextHref ? (
            <Link className="fr-btn fr-next is-action" data-press="3d" href={nextHref}>
              {nextLabel || 'Lire la suite'} <ArrowRightIcon size={18} />
            </Link>
          ) : onComplete ? (
            <button
              type="button"
              className="fr-btn fr-next is-action"
              data-press={primary === 'complete' ? '3d' : undefined}
              disabled={completing}
              onClick={onComplete}
            >
              {completing ? <SpinnerToken /> : <CheckIcon size={16} />}
              {completing ? 'Classement…' : completeLabel}
            </button>
          ) : (
            <button type="button" className="fr-btn fr-next" disabled>
              Fin de l’épisode
            </button>
          )
        ) : (
          <button
            type="button"
            className="fr-btn fr-next"
            data-press={primary === 'next' ? '3d' : undefined}
            onClick={() => go(safeIndex + 1)}
          >
            Suivant <ArrowRightIcon size={18} />
          </button>
          )}
        </div>
      </nav>

      <WordHelpSheet request={help} onClose={() => setHelp(null)} />
    </section>
    </AtelierV2Root>
  );
}

function PanelBody({
  stage,
  showTranslation,
  onWord,
}: {
  stage: Extract<ReaderStage, { kind: 'panel' }>;
  showTranslation: boolean;
  onWord: (
    word: { surface: string; term: string },
    context: { sentence: string; sentenceEn?: string; character?: string; speaker?: string },
  ) => void;
}) {
  const src = resolveMediaUrl(stage.imageUrl);
  return (
    <>
      {stage.artStatus === 'ready' && src ? (
        <figure className="fr-plate">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={stage.title ? `Planche : ${stage.title}` : ''} />
        </figure>
      ) : stage.artStatus === 'printing' ? (
        <figure className="fr-plate is-printing" aria-live="polite">
          <figcaption className="fr-plate-note">L’illustration de cette planche est encore sous presse. Le texte est complet.</figcaption>
        </figure>
      ) : (
        <figure className="fr-plate is-missing">
          <figcaption className="fr-plate-note">Cette planche est parue sans illustration.</figcaption>
        </figure>
      )}

      {stage.lines.map((line) => (
        <div className="fr-speech" data-char={line.character || stage.character || undefined} key={line.key}>
          {line.who && (
            <p className="fr-speaker">
              <span className="glyph" aria-hidden="true" />
              {line.who}
            </p>
          )}
          <p className="fr-line">
            <TappableFrench
              text={line.fr}
              idPrefix={line.key}
              onWord={(word) =>
                onWord(word, {
                  sentence: line.fr,
                  sentenceEn: line.en,
                  character: line.character || stage.character,
                  speaker: line.who,
                })
              }
            />
          </p>
          {showTranslation && line.en && <p className="fr-line-en">{line.en}</p>}
        </div>
      ))}

      {stage.caption && (
        <p className="fr-caption">
          <TappableFrench
            text={stage.caption}
            idPrefix={`${stage.key}-cap`}
            onWord={(word) => onWord(word, { sentence: stage.caption, character: stage.character })}
          />
        </p>
      )}
    </>
  );
}

function ResolutionBody({ stage }: { stage: Extract<ReaderStage, { kind: 'resolution' }> }) {
  if (!stage.hookQuestion && !stage.hookBeat) return null;
  return (
    <div className="fr-notice" data-char={stage.character || undefined}>
      <p className="fr-eyebrow">À suivre</p>
      {stage.hookQuestion && <h2>{stage.hookQuestion}</h2>}
      {stage.hookBeat && <p>{stage.hookBeat}</p>}
    </div>
  );
}

function TaskCard({
  task,
  value,
  setValue,
  onSubmit,
  submitting,
  attempt,
  submitError,
  press,
  onWord,
  character,
}: {
  task: ReaderTask;
  value: string;
  setValue: (value: string) => void;
  onSubmit: () => void;
  submitting: boolean;
  attempt?: Record<string, any>;
  submitError: ReaderSubmitError;
  press: boolean;
  onWord: (
    word: { surface: string; term: string },
    context: { sentence: string; sentenceEn?: string; character?: string; speaker?: string },
  ) => void;
  character?: string;
}) {
  const taskId = String(task.id || '');
  const correction = attempt?.correction as Record<string, any> | undefined;
  const answered = Boolean(attempt);
  const options = choiceOptions(task);
  const isChoice = taskIsChoice(task);
  const prompt = taskPromptLine(task);
  const promptEn = taskPromptTranslation(task);
  const branch = correctionIsBranch(correction);
  const positive = correctionIsPositive(correction);
  const feedback = correctionLine(correction);
  const errored = submitError?.taskId === taskId;
  const recorded = String(attempt?.answer_payload?.answer ?? attempt?.answer ?? '').trim();

  return (
    <div className={`fr-act ${answered ? 'is-read' : ''}`} data-char={character || undefined}>
      <p className="fr-prompt">
        <TappableFrench
          text={prompt}
          idPrefix={`${taskId}-p`}
          onWord={(word) => onWord(word, { sentence: prompt, sentenceEn: promptEn, character })}
        />
      </p>
      {promptEn && <p className="fr-prompt-en">{promptEn}</p>}

      {answered ? (
        <>
          {recorded && (
            <blockquote className="fr-quote">
              <p className="fr-quote-k">Votre réponse, déjà envoyée</p>
              <p className="fr-quote-fr">{recorded}</p>
            </blockquote>
          )}
          {correction && (
            <p className={`fr-feedback ${branch ? 'is-branch' : positive ? '' : 'is-wrong'}`} role="status">
              <span className="tok" aria-hidden="true">
                {positive ? <CheckIcon size={15} /> : <CrossIcon size={15} />}
              </span>
              <span>
                <b>{branch ? 'Choix pris en compte' : positive ? 'Acceptée' : 'Reprise classée'}</b>
                {feedback}
              </span>
            </p>
          )}
        </>
      ) : (
        <>
          {options.length > 0 && (
            <div className="fr-options" role="group" aria-label="Répliques possibles">
              {options.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className="fr-option"
                  aria-pressed={value === option.value}
                  onClick={() => setValue(option.value)}
                >
                  <span>{option.text}</span>
                  <span className="dot" aria-hidden="true" />
                </button>
              ))}
            </div>
          )}
          {!(isChoice && options.length > 0) &&
            (taskIsClosed(task) ? (
              <input
                className="fr-field"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder="Votre réponse"
                aria-label="Votre réponse"
              />
            ) : (
              <textarea
                className="fr-field"
                rows={3}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder={task.placeholder || 'Écrivez une phrase courte.'}
                aria-label="Votre réponse"
              />
            ))}
          <button
            type="button"
            className="fr-btn is-action"
            data-press={press ? '3d' : undefined}
            disabled={submitting}
            onClick={onSubmit}
          >
            {submitting ? <SpinnerToken /> : null}
            {submitting ? 'Relecture…' : 'Envoyer'}
          </button>
          {errored && (
            <p className="fr-feedback is-wrong" role="status">
              <span className="tok" aria-hidden="true">
                <CrossIcon size={15} />
              </span>
              <span>{submitError?.message}</span>
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default FeuilletonReader;
