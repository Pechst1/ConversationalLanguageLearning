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
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { frenchSpacing } from '@/lib/french-typography';
import { enterImmersiveSurface } from '@/lib/immersive-surface';
import { resolveMediaUrl } from '@/lib/media-url';
import apiService from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { fillReaderCopy, readerCopy, type ReaderCopy } from './reader-copy';
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
  type ReaderLine,
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
  /** An illustrated-page edition composes ONE printed page for the whole scene
      (`script_payload.page_image`). When given, a panel that has no art of its
      own shows that page as its plate instead of a "sans illustration" note. */
  pageArt?: string | null;
  /** Extra per-panel tools (e.g. a panel's narration) rendered in the tools row. */
  renderStageTools?: (stage: ReaderStage) => React.ReactNode;
  /** One small note under a task's prompt — the server's "because" line. */
  taskNote?: (task: ReaderTask) => string;
  /** WP-44. How each panel is drawn: `bubble` = the reply over the art
      (artboard A), `line` = the reply in a card under it (artboard B). Absent
      leaves the legacy layout — art, replies, caption — exactly as it was. */
  panelVariant?: ((stage: ReaderStage) => 'bubble' | 'line') | null;
  /** WP-44. One quiet link under the nav, e.g. «Écouter d'abord». */
  footLink?: React.ReactNode;
  /** WP-44. Where this episode's art came from, e.g. `setting_reference`.
      Written to the DOM for telemetry and never shown to the learner: the
      provenance is the product's business, and the banner that used to state
      it interrupted every scene with a disclaimer about a picture. */
  artProvenance?: string | null;
  /** WP-82. The chrome's language (`lib/language-rule.ts`): the learner's up
      to A2, French from B1. Absent keeps the French chrome. The story is
      content and stays French either way. */
  language?: ControlLanguage | null;
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
  completeLabel,
  filed = false,
  nextHref,
  nextLabel,
  banner,
  pageArt,
  renderStageTools,
  taskNote,
  panelVariant = null,
  footLink = null,
  artProvenance = null,
  language = null,
}: FeuilletonReaderProps) {
  const t = readerCopy(language);
  const [help, setHelp] = useState<WordHelpRequest | null>(null);
  const [translated, setTranslated] = useState<Record<string, boolean>>({});

  /* This reader owns the whole screen while it is up: its own exit, its own
     progress rail, its own action bar. Anything else that draws one of those
     stands down (WP-20 D-4, D-9). */
  useEffect(() => enterImmersiveSurface(), []);
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

  const stageTools = renderStageTools ? renderStageTools(stage) : null;
  const railPct = count > 1 ? Math.round(((safeIndex + 1) / count) * 100) : 100;
  const positionLabel =
    stage.kind === 'resolution'
      ? fillReaderCopy(t.position_end, { n: safeIndex + 1, count })
      : fillReaderCopy(t.position_panel, { n: safeIndex + 1, count });

  return (
    /* The av2 root supplies the tokens and the `.av2` ancestor every reader
       rule is written against; the reader itself stays the section. */
    <AtelierV2Root as="div" className="fr-scope">
    <section
      className="fr-reader"
      aria-label={t.reader_label}
      data-story={panelVariant ? '1' : undefined}
      data-art={artProvenance || undefined}
      ref={rootRef}
    >
      <div className="fr-bar">
        <button type="button" className="fr-icon-btn" onClick={onExit} aria-label={t.exit}>
          <CrossIcon size={16} />
        </button>
        <div
          className="fr-rail"
          role="progressbar"
          aria-valuemin={1}
          aria-valuemax={count}
          aria-valuenow={safeIndex + 1}
          aria-label={t.progress}
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
        <h1 className="fr-title">{frenchSpacing(title)}</h1>
        {previously && safeIndex === 0 && <p className="fr-previously">{t.previously} — {frenchSpacing(previously)}</p>}
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
        aria-roledescription={t.roledescription}
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
            {t.already_read}
          </p>
        )}
        {readState !== 'read' && stageLiveTask && (
          <p className="fr-state is-live">
            <span className="tok" aria-hidden="true" />
            {t.your_turn}
          </p>
        )}

        {stage.kind === 'panel' ? (
          <PanelBody
            stage={stage}
            showTranslation={showTranslation}
            onWord={openHelp}
            pageArt={pageArt}
            variant={panelVariant ? panelVariant(stage) : null}
            t={t}
          />
        ) : (
          <ResolutionBody stage={stage} t={t} />
        )}

        {stage.kind === 'panel' && (hasEnglish || stageTools) && (
          <div className="fr-tools">
            {hasEnglish && (
              <button
                type="button"
                className="fr-chip"
                aria-pressed={showTranslation}
                onClick={() => setTranslated((current) => ({ ...current, [stageKey]: !current[stageKey] }))}
              >
                <span className="sq" aria-hidden="true" />
                {showTranslation ? t.hide_translation : t.translate_panel}
              </button>
            )}
            {stageTools}
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
                  {t.task_locked}
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
              note={taskNote ? taskNote(task) : ''}
              t={t}
            />
          );
        })}

        {stage.kind === 'resolution' && filed && (
          <p className="fr-state">
            <span className="tok" aria-hidden="true">
              <CheckIcon size={11} />
            </span>
            {t.filed}
          </p>
        )}
      </div>

      <nav className="fr-nav" aria-label={t.nav_label}>
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
                      ? t.go_end
                      : fillReaderCopy(t.go_panel, { n: entryIndex + 1 })
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
            aria-label={t.prev_label}
          >
            <ArrowLeftIcon size={18} />
            <span className="fr-sr">{t.prev}</span>
          </button>

          {isLast ? (
          filed && nextHref ? (
            <Link className="fr-btn fr-next is-action" data-press="3d" href={nextHref}>
              {nextLabel || t.read_on} <ArrowRightIcon size={18} />
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
              {completing ? t.completing : completeLabel || t.complete}
            </button>
          ) : (
            <button type="button" className="fr-btn fr-next" disabled>
              {t.episode_end}
            </button>
          )
        ) : (
          <button
            type="button"
            className="fr-btn fr-next"
            data-press={primary === 'next' ? '3d' : undefined}
            onClick={() => go(safeIndex + 1)}
          >
            {t.next} <ArrowRightIcon size={18} />
          </button>
          )}
        </div>

        {footLink && <div className="fr-foot-link">{footLink}</div>}
      </nav>

      <WordHelpSheet request={help} onClose={() => setHelp(null)} language={language} />
    </section>
    </AtelierV2Root>
  );
}

/* WP-77: a drawn cast member's face, small, beside the name. */
function SpeakerFace({ line }: { line: ReaderLine }) {
  if (!line.faceId) return null;
  return <CastPortrait characterId={line.faceId} name={line.who} mood={line.faceMood ?? 'neutral'} size="xs" />;
}

/* One reply, as a card. The legacy layout keeps its accent dot; the WP-44
   artboards print the name alone in the story blue. */
function SpeechBody({
  line,
  stage,
  showTranslation,
  onWord,
  glyph = false,
}: {
  line: ReaderLine;
  stage: Extract<ReaderStage, { kind: 'panel' }>;
  showTranslation: boolean;
  onWord: (
    word: { surface: string; term: string },
    context: { sentence: string; sentenceEn?: string; character?: string; speaker?: string },
  ) => void;
  glyph?: boolean;
}) {
  return (
    <div className="fr-speech" data-char={line.character || stage.character || undefined}>
      {line.who && (
        <p className="fr-speaker" data-face={line.faceId ? 'true' : undefined}>
          {/* WP-77: the speaker's face beside their line; the narrator has none. */}
          {line.faceId ? (
            <SpeakerFace line={line} />
          ) : (
            glyph && <span className="glyph" aria-hidden="true" />
          )}
          {line.who}
        </p>
      )}
      <p className="fr-line" lang="fr">
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
  );
}

function PanelBody({
  stage,
  showTranslation,
  onWord,
  pageArt,
  variant = null,
  t,
}: {
  t: ReaderCopy;
  stage: Extract<ReaderStage, { kind: 'panel' }>;
  showTranslation: boolean;
  onWord: (
    word: { surface: string; term: string },
    context: { sentence: string; sentenceEn?: string; character?: string; speaker?: string },
  ) => void;
  pageArt?: string | null;
  variant?: 'bubble' | 'line' | null;
}) {
  const src = resolveMediaUrl(stage.imageUrl);
  const page = pageArt ? resolveMediaUrl(pageArt) : null;

  /* WP-44, artboards A and B. The story reader reads in the order a reader
     reads: the picture, then what happened, then who said what. The bubble
     variant moves the single reply onto the picture it belongs to; nothing
     else about the panel changes, and the words are the same words. */
  if (variant) {
    const speech = stage.lines.map((line) => (
      <SpeechBody
        key={line.key}
        line={line}
        stage={stage}
        showTranslation={showTranslation}
        onWord={onWord}
      />
    ));
    const bubbleLine = variant === 'bubble' ? stage.lines[0] : null;
    return (
      <>
        {stage.artStatus === 'ready' && src ? (
          <figure className="fr-plate" data-variant={variant}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={src} alt={stage.title ? fillReaderCopy(t.plate_alt, { title: stage.title }) : ''} />
            {bubbleLine && (
              <div
                className="fr-bubble"
                data-char={bubbleLine.character || stage.character || undefined}
              >
                <p className="fr-speaker" data-face={bubbleLine.faceId ? 'true' : undefined}>
                  {bubbleLine.faceId && <SpeakerFace line={bubbleLine} />}
                  {bubbleLine.who}
                </p>
                <p className="fr-line" lang="fr">
                  <TappableFrench
                    text={bubbleLine.fr}
                    idPrefix={bubbleLine.key}
                    onWord={(word) =>
                      onWord(word, {
                        sentence: bubbleLine.fr,
                        sentenceEn: bubbleLine.en,
                        character: bubbleLine.character || stage.character,
                        speaker: bubbleLine.who,
                      })
                    }
                  />
                </p>
              </div>
            )}
          </figure>
        ) : null}

        {stage.caption && (
          <p className="fr-caption">
            <TappableFrench
              text={stage.caption}
              idPrefix={`${stage.key}-cap`}
              onWord={(word) => onWord(word, { sentence: stage.caption, character: stage.character })}
            />
          </p>
        )}

        {variant === 'bubble'
          ? stage.lines.slice(1).map((line) => (
              <SpeechBody
                key={line.key}
                line={line}
                stage={stage}
                showTranslation={showTranslation}
                onWord={onWord}
              />
            ))
          : speech}
      </>
    );
  }

  return (
    <>
      {stage.artStatus === 'ready' && src ? (
        <figure className="fr-plate">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={stage.title ? fillReaderCopy(t.plate_alt, { title: stage.title }) : ''} />
        </figure>
      ) : page ? (
        /* the illustrated-page edition: one composed page is the plate */
        <figure className="fr-plate is-page">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={page} alt={t.page_alt} />
        </figure>
      ) : stage.artStatus === 'printing' ? (
        <figure className="fr-plate is-printing" aria-live="polite">
          <figcaption className="fr-plate-note">{t.art_printing}</figcaption>
        </figure>
      ) : (
        <figure className="fr-plate is-missing">
          <figcaption className="fr-plate-note">{t.art_missing}</figcaption>
        </figure>
      )}

      {stage.lines.map((line) => (
        <SpeechBody
          key={line.key}
          line={line}
          stage={stage}
          showTranslation={showTranslation}
          onWord={onWord}
          glyph
        />
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

function ResolutionBody({ stage, t }: { stage: Extract<ReaderStage, { kind: 'resolution' }>; t: ReaderCopy }) {
  if (!stage.hookQuestion && !stage.hookBeat) return null;
  return (
    <div className="fr-notice" data-char={stage.character || undefined}>
      <p className="fr-eyebrow">{t.to_follow}</p>
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
  note = '',
  t,
}: {
  t: ReaderCopy;
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
  note?: string;
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
      <TaskTranslate french={prompt} supplied={promptEn} t={t} />
      {note && <p className="fr-prompt-note">{note}</p>}

      {answered ? (
        <>
          {recorded && (
            <blockquote className="fr-quote">
              <p className="fr-quote-k">{t.answer_sent}</p>
              <p className="fr-quote-fr">{recorded}</p>
            </blockquote>
          )}
          {correction && (
            <p className={`fr-feedback ${branch ? 'is-branch' : positive ? '' : 'is-wrong'}`} role="status">
              <span className="tok" aria-hidden="true">
                {positive ? <CheckIcon size={15} /> : <CrossIcon size={15} />}
              </span>
              <span>
                <b>{branch ? t.verdict_branch : positive ? t.verdict_ok : t.verdict_retry}</b>
                {feedback}
              </span>
            </p>
          )}
        </>
      ) : (
        <>
          {options.length > 0 && (
            <div className="fr-options" role="group" aria-label={t.options_label}>
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
                lang="fr"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder={t.answer_label}
                aria-label={t.answer_label}
              />
            ) : (
              <textarea
                className="fr-field"
                lang="fr"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                rows={3}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder={task.placeholder || t.answer_placeholder}
                aria-label={t.answer_label}
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
            {submitting ? t.checking : t.send}
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

/* Translation is one explicit affordance: the English never prints beside the
   French uncalled. A supplied translation is shown on request; otherwise the
   line is translated on demand, and the request is never a graded attempt. */
function TaskTranslate({ french, supplied, t }: { french: string; supplied?: string; t: ReaderCopy }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(supplied || '');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setText(supplied || '');
    setOpen(false);
  }, [french, supplied]);

  if (!french.trim()) return null;

  const toggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (text || loading) return;
    setLoading(true);
    try {
      const translated = await apiService.translateToEnglish(french);
      setText(translated || '');
    } catch {
      setText('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="fr-tools">
        <button type="button" className="fr-chip" aria-expanded={open} onClick={() => void toggle()}>
          <span className="sq" aria-hidden="true" />
          {open ? t.hide_translation : t.translate}
        </button>
      </div>
      {open && (
        <p className="fr-prompt-en" aria-live="polite">
          {loading ? t.translating : text || t.no_translation}
        </p>
      )}
    </>
  );
}

export default FeuilletonReader;
