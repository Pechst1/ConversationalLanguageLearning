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

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  AtelierV2Root,
  CheckIcon,
  CrossIcon,
  ShapeToken,
  SpinnerToken,
} from '@/components/atelier-v2/ui';
import { SpeakingPortrait } from '@/components/atelier-v2/journey/SpeakingPortrait';
import type { LineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { frenchSpacing } from '@/lib/french-typography';
import { enterImmersiveSurface } from '@/lib/immersive-surface';
import { resolveMediaUrl } from '@/lib/media-url';
import apiService from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { fillReaderCopy, portraitAlt, readerCopy, type ReaderCopy } from './reader-copy';
import { FrenchLine, TappableFrench } from './TappableFrench';
import { markedForms, rayonsUnlocked, readRayons, writeRayons } from './grammar-marks';
import { WordHelpSheet, type WordHelpRequest } from './WordHelpSheet';
import {
  choiceOptions,
  correctionIsBranch,
  readerHeadParts,
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
import { useArtSet } from '@/lib/art-set';
import { PanelStage } from '@/components/cast/PanelStage';
import { useMouth } from '@/components/cast/useMouth';
import { VerticalPanel } from '@/components/atelier-v2/journey/vertical-page/VerticalPanel';
import { VerticalPageStyles } from '@/components/atelier-v2/journey/vertical-page/vertical-page-styles';

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

  /** The ✕. Absent draws none (the caller owns the way out). */
  onExit?: (() => void) | null;
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
  /** WP-97: what a stage prints in its margin — the notes paid back on this panel. */
  renderStageMargin?: (stage: ReaderStage) => React.ReactNode;
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
  /** WP-90/91: speaks a line when its speaker's face is tapped. Absent: plain faces. */
  lineVoice?: LineVoice | null;
  /** The face button's label («Écouter Margaux»); the reader's own copy when absent. */
  listenLabel?: ((name: string) => string) | null;
  /** WP-90: under the «case finale» — the register note, the chapter recap. */
  finaleExtra?: React.ReactNode;
  /** WP-90: shown in the finale while its ending is still being written. */
  finaleWait?: React.ReactNode;
  /**
   * WP-92 «Rayons X»: the day's rule, named in the chrome language. Given
   * (and some line carries marks), a toggle in the bar marks the rule's form
   * in the page — after the first full read, or at once on a replay.
   */
  rayonsTitle?: string | null;
  /** WP-93: the page is from another day, so the legend says «Ce jour-là». */
  rayonsPast?: boolean;
  /** WP-92: the page is being re-read (a replay, or the READ step): the toggle is there at once. */
  rayonsReplay?: boolean;
  /**
   * WP-144: `vertical` draws each story panel full-bleed with its lines as
   * balloons (`VerticalPanel`); `list` (the default) is the page as it was. Only
   * the story reader (`panelVariant` given) has a vertical page.
   */
  layout?: 'list' | 'vertical';
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
  renderStageMargin,
  taskNote,
  panelVariant = null,
  footLink = null,
  artProvenance = null,
  language = null,
  lineVoice = null,
  listenLabel = null,
  finaleExtra = null,
  finaleWait = null,
  rayonsTitle = null,
  rayonsPast = false,
  rayonsReplay = false,
  layout = 'list',
}: FeuilletonReaderProps) {
  const base = readerCopy(language);
  /* WP-91: the face's label comes from the journey's own table when it hands
     one over, so every «Écouter …» on the screen is the same words. */
  const t: ReaderCopy = listenLabel ? { ...base, listen_to: listenLabel('{name}') } : base;
  const [help, setHelp] = useState<WordHelpRequest | null>(null);
  const [translated, setTranslated] = useState<Record<string, boolean>>({});
  /* WP-92: «Rayons X» is off by default and remembered per device — read on
     the client only, so the server render and the first paint agree. */
  const [rayonsOn, setRayonsOn] = useState(false);
  useEffect(() => {
    setRayonsOn(readRayons());
  }, []);

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
      // WP-90: inside a French line the arrows walk its words, not the pages.
      if (target?.closest?.('[data-roving-line]')) return;
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
    (word: { surface: string; term: string }, context: WordContext) => {
      setHelp({
        surface: word.surface,
        term: word.term,
        sentence: context.sentence,
        sentenceEn: context.sentenceEn,
        character: context.character,
        speaker: context.speaker,
        speakerId: context.speakerId ?? null,
        panelId: context.panelId,
        lineKey: context.lineKey,
      });
    },
    [],
  );

  if (!stage) return null;

  const stageKey = stage.key;
  const vertical = layout === 'vertical' && Boolean(panelVariant);
  const verticalPanel = vertical && stage.kind === 'panel';
  const showTranslation = Boolean(translated[stageKey]);
  const hasEnglish =
    stage.kind === 'panel' && stage.lines.some((line) => Boolean(line.en));

  const stageTools = renderStageTools ? renderStageTools(stage) : null;
  const stageMargin = renderStageMargin ? renderStageMargin(stage) : null;
  const positionLabel =
    stage.kind === 'resolution'
      ? fillReaderCopy(t.position_end, { n: safeIndex + 1, count })
      : fillReaderCopy(t.position_panel, { n: safeIndex + 1, count });
  /* WP-90 (W4): one kicker, one title — never «Le feuilleton» twice — and
     after the first panel the headline folds into a running head in the bar,
     which is also the only place the position is printed. The dots are the
     one progress indicator. */
  const head = readerHeadParts({ episodeLabel, location, title });
  const folded = safeIndex > 0;
  const runningHead = fillReaderCopy(t.running_head, {
    title: frenchSpacing(head.title),
    n: safeIndex + 1,
    count,
  });
  const finale = stage.kind === 'resolution' ? stage.finale ?? null : null;
  /* WP-92 «Rayons X»: only when the page has marks, and only once the page
     has been read to its last panel (or is being re-read). */
  const lastPanelIndex = stages.reduce((last, entry, i) => (entry.kind === 'panel' ? i : last), -1);
  const rayonsAvailable =
    Boolean(rayonsTitle)
    && stages.some((entry) => entry.kind === 'panel' && entry.lines.some((line) => (line.marks?.length ?? 0) > 0))
    && rayonsUnlocked({ furthest, lastPanelIndex, replay: filed || rayonsReplay });
  const rayonsShown = rayonsAvailable && rayonsOn;
  const rayons: RayonsView | null = rayonsShown
    ? { formLabel: (form: string) => fillReaderCopy(t.rayons_form, { form }), lang: language ?? 'fr' }
    : null;
  const rayonsChip = rayonsAvailable ? (
    <button
      type="button"
      className="fr-chip fr-chip--rayons"
      aria-pressed={rayonsOn}
      aria-label={t.rayons_label}
      onClick={() => {
        const next = !rayonsOn;
        setRayonsOn(next);
        writeRayons(next);
      }}
    >
      <ShapeToken kind="action" size="sm" />
      {t.rayons}
    </button>
  ) : null;
  /* The story reader keeps the chip in the bar: a fixed place, so a panel with
     a translation and one without are the same height — and there it is the
     short word, pressed or not, with the whole phrase as its name. */
  const chipInBar = Boolean(panelVariant);
  const translateChip = stage.kind === 'panel' && hasEnglish ? (
    <button
      type="button"
      className="fr-chip"
      aria-pressed={showTranslation}
      aria-label={chipInBar ? t.translate_panel : undefined}
      onClick={() => setTranslated((current) => ({ ...current, [stageKey]: !current[stageKey] }))}
    >
      <span className="sq" aria-hidden="true" />
      {chipInBar ? t.translate : showTranslation ? t.hide_translation : t.translate_panel}
    </button>
  ) : null;

  return (
    /* The av2 root supplies the tokens and the `.av2` ancestor every reader
       rule is written against; the reader itself stays the section. */
    <AtelierV2Root as="div" className="fr-scope" language={language ?? undefined}>
    {vertical && <VerticalPageStyles />}
    <section
      className="fr-reader"
      aria-label={t.reader_label}
      data-story={panelVariant ? '1' : undefined}
      data-layout={vertical ? 'vertical' : undefined}
      data-art={artProvenance || undefined}
      ref={rootRef}
    >
      <div className="fr-bar" data-folded={folded ? 'true' : undefined}>
        {onExit && (
          <button type="button" className="fr-icon-btn" onClick={onExit} aria-label={t.exit}>
            <CrossIcon size={16} />
          </button>
        )}
        {folded ? (
          <p className="fr-running" lang="fr">
            {runningHead}
          </p>
        ) : (
          <span className="fr-running" aria-hidden="true" />
        )}
        {rayonsChip}
        {chipInBar && translateChip}
      </div>

      {rayonsShown && rayonsTitle && (
        /* one line, in the chrome language: which rule the marks are */
        <p className="fr-rayons-legend">
          <ShapeToken kind="action" size="sm" />
          <span>{fillReaderCopy(rayonsPast ? t.rayons_legend_past : t.rayons_legend, { title: rayonsTitle })}</span>
        </p>
      )}

      {/* WP-144: on the vertical page the first panel carries the headline as its establishing caption. */}
      {!folded && !verticalPanel && (
        <div className="fr-head">
          {head.eyebrow && <p className="fr-eyebrow">{head.eyebrow}</p>}
          {/* the one Garamond italic headline on this screen */}
          <h1 className="fr-title">{frenchSpacing(head.title)}</h1>
          {previously && <p className="fr-previously">{t.previously} — {frenchSpacing(previously)}</p>}
        </div>
      )}

      {banner}

      <p className="fr-sr" role="status" aria-live="polite">
        {positionLabel}
      </p>

      <div
        className="fr-stage"
        data-char={stage.character || undefined}
        data-kind={stage.kind}
        data-movement={stage.kind === 'panel' ? stage.movement : undefined}
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

        {stage.kind === 'panel' && verticalPanel ? (
          <VerticalPanel
            key={stage.key}
            stage={stage}
            showTranslation={showTranslation}
            onWord={openHelp}
            voice={lineVoice}
            marksFor={(line) => lineRayons(line, rayons)}
            head={folded ? null : { eyebrow: head.eyebrow, title: head.title }}
            topInset={readState === 'read' || stageLiveTask ? 36 : 0}
            t={t}
          />
        ) : stage.kind === 'panel' ? (
          <PanelBody
            /* a new panel is a new plate: no crossfade between panels, only
               between a panel's plate and its own drawing */
            key={stage.key}
            stage={stage}
            showTranslation={showTranslation}
            onWord={openHelp}
            pageArt={pageArt}
            variant={panelVariant ? panelVariant(stage) : null}
            voice={lineVoice}
            rayons={rayons}
            t={t}
          />
        ) : finale ? (
          <FinaleBody
            stage={stage}
            finale={finale}
            voice={lineVoice}
            wait={finaleWait}
            extra={finaleExtra}
            t={t}
          />
        ) : (
          <ResolutionBody stage={stage} t={t} />
        )}

        {stage.kind === 'panel' && ((!chipInBar && hasEnglish) || stageTools) && (
          <div className="fr-tools">
            {!chipInBar && translateChip}
            {stageTools}
          </div>
        )}

        {stageMargin}

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
        <ol className="fr-dots" aria-label={t.progress}>
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

          {isLast && finale?.waiting && !filed ? (
            /* WP-90: the ending is still being written — its face says so;
               there is no dead primary to stare at. */
            null
          ) : isLast ? (
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

/** WP-92: while «Rayons X» is on — how a marked line is announced, and in which language. */
type RayonsView = { formLabel: (form: string) => string; lang: string };

/** The marks for one line while «Rayons X» is on; nothing otherwise. */
function lineRayons(line: ReaderLine, rayons: RayonsView | null | undefined) {
  if (!rayons || !line.marks || line.marks.length === 0) return {};
  const forms = markedForms(line.fr, line.marks);
  return {
    marks: line.marks,
    marksLabel: forms.length ? rayons.formLabel(forms.join(' · ')) : '',
    marksLang: rayons.lang,
  };
}

/** Where a tapped word was: its line, and — for a spoken line — who said it, in
 *  which panel, under which audio key (WP-115a: a kept word remembers it). */
type WordContext = {
  sentence: string;
  sentenceEn?: string;
  character?: string;
  speaker?: string;
  speakerId?: string | null;
  panelId?: string;
  lineKey?: string;
};

type WordHandler = (
  word: { surface: string; term: string },
  context: WordContext,
) => void;

/* WP-77: a drawn cast member's face, small, beside the name. WP-90/91: the
   face acts (the line's mood) and is the play button when a voice is given;
   its alt says who and how — «Margaux, ravie». */
function SpeakerFace({ line, voice, t }: { line: ReaderLine; voice?: LineVoice | null; t: ReaderCopy }) {
  if (!line.faceId) return null;
  const mood = line.faceMood ?? 'neutral';
  return (
    <SpeakingPortrait
      characterId={line.faceId}
      name={line.who}
      mood={mood}
      size="xs"
      alt={portraitAlt(t, line.who, mood, line.faceId)}
      line={{ key: line.audioKey || line.key, text_fr: line.fr, character_id: line.speakerId ?? line.faceId }}
      voice={voice}
      label={fillReaderCopy(t.listen_to, { name: line.who || '' })}
    />
  );
}

/* One reply, as a card. The legacy layout keeps its accent dot; the WP-44
   artboards print the name alone in the story blue. WP-90: in the story
   reader it is a compact caption — the face, then the name over the line. */
function SpeechBody({
  line,
  stage,
  showTranslation,
  onWord,
  glyph = false,
  compact = false,
  voice = null,
  rayons = null,
  t,
}: {
  line: ReaderLine;
  stage: Extract<ReaderStage, { kind: 'panel' }>;
  showTranslation: boolean;
  onWord: WordHandler;
  glyph?: boolean;
  compact?: boolean;
  voice?: LineVoice | null;
  rayons?: RayonsView | null;
  t: ReaderCopy;
}) {
  const french = (
    <FrenchLine
      text={line.fr}
      idPrefix={line.key}
      wordLabel={t.word_help}
      {...lineRayons(line, rayons)}
      onWord={(word) =>
        onWord(word, {
          sentence: line.fr,
          sentenceEn: line.en,
          character: line.character || stage.character,
          speaker: line.who,
          speakerId: line.speakerId ?? null,
          panelId: stage.panelId,
          lineKey: line.audioKey,
        })
      }
    />
  );
  if (compact) {
    return (
      <div
        className="fr-speech"
        data-compact="true"
        data-char={line.character || stage.character || undefined}
      >
        {line.faceId ? (
          <SpeakerFace line={line} voice={voice} t={t} />
        ) : (
          <span className="fr-speech__bare" aria-hidden="true" />
        )}
        <div className="fr-speech__text">
          {line.who && <p className="fr-speaker">{line.who}</p>}
          {french}
          {showTranslation && line.en && <p className="fr-line-en">{line.en}</p>}
        </div>
      </div>
    );
  }
  return (
    <div className="fr-speech" data-char={line.character || stage.character || undefined}>
      {line.who && (
        <p className="fr-speaker" data-face={line.faceId ? 'true' : undefined}>
          {/* WP-77: the speaker's face beside their line; the narrator has none. */}
          {line.faceId ? (
            <SpeakerFace line={line} voice={voice} t={t} />
          ) : (
            glyph && <span className="glyph" aria-hidden="true" />
          )}
          {line.who}
        </p>
      )}
      {french}
      {showTranslation && line.en && <p className="fr-line-en">{line.en}</p>}
    </div>
  );
}

function reducedMotionNow(): boolean {
  return prefersReducedMotion();
}

/**
 * WP-90: the panel's picture, in a frame that never changes size.
 *
 * While the panel's own drawing is on the press the location plate stands in,
 * drawn as a blue-ink duotone with a folio ribbon («Planche 3 · sous presse»).
 * When the drawing lands it fades in over the plate in 300 ms — or simply
 * appears under Reduce Motion — and the frame's ratio holds, so nothing below
 * it moves.
 */
function PlateArt({
  src,
  alt,
  pending,
  ribbon,
  variant,
  pan = false,
  children,
}: {
  src: string;
  alt: string;
  pending: boolean;
  ribbon: string;
  variant?: 'bubble' | 'line' | null;
  /** WP-137 C-5: a silent panel's plate moves slowly (never under Reduce Motion). */
  pan?: boolean;
  children?: React.ReactNode;
}) {
  const [shown, setShown] = useState<{ src: string; pending: boolean }>({ src, pending });
  const [previous, setPrevious] = useState<{ src: string; pending: boolean } | null>(null);
  const [arrived, setArrived] = useState(true);

  useEffect(() => {
    setShown((current) => {
      if (current.src === src && current.pending === pending) return current;
      if (current.src !== src) {
        // The drawing replaces the plate: keep the plate underneath until the
        // drawing has loaded and faded in.
        setPrevious(current);
        setArrived(false);
      }
      return { src, pending };
    });
  }, [src, pending]);

  useEffect(() => {
    if (!arrived || !previous) return undefined;
    const timer = window.setTimeout(() => setPrevious(null), reducedMotionNow() ? 0 : 320);
    return () => window.clearTimeout(timer);
  }, [arrived, previous]);

  return (
    <figure
      className="fr-plate"
      data-variant={variant || undefined}
      data-pending={shown.pending ? 'true' : undefined}
      data-pan={pan ? 'slow' : undefined}
    >
      {previous && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          className="fr-art is-previous"
          src={previous.src}
          alt=""
          aria-hidden="true"
          data-pending={previous.pending ? 'true' : undefined}
        />
      )}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        key={shown.src}
        className="fr-art"
        src={shown.src}
        alt={alt}
        data-pending={shown.pending ? 'true' : undefined}
        data-arriving={!arrived ? 'true' : undefined}
        onLoad={() => setArrived(true)}
        onError={() => setArrived(true)}
      />
      {/* the blue ink over the plate; it lifts as the drawing arrives */}
      <span className="fr-ink" aria-hidden="true" data-on={shown.pending ? 'true' : undefined} />
      {shown.pending && <figcaption className="fr-folio">{ribbon}</figcaption>}
      {children}
    </figure>
  );
}

function PanelBody({
  stage,
  showTranslation,
  onWord,
  pageArt,
  variant = null,
  voice = null,
  rayons = null,
  t,
}: {
  t: ReaderCopy;
  stage: Extract<ReaderStage, { kind: 'panel' }>;
  showTranslation: boolean;
  onWord: WordHandler;
  pageArt?: string | null;
  variant?: 'bubble' | 'line' | null;
  voice?: LineVoice | null;
  rayons?: RayonsView | null;
}) {
  // WP-116: in the drawn art set the panel is its location plate with the cast
  // drawn on it; a painted drawing (people included) is not shown.
  const drawn = useArtSet() === 'drawn' && Boolean(stage.plateUrl);
  const src = drawn ? resolveMediaUrl(stage.plateUrl) : resolveMediaUrl(stage.imageUrl);
  const artReady = drawn || stage.artStatus === 'ready';
  // WP-116 phase 4: the line being heard, so its speaker's mouth follows the voice.
  const heard = voice ? stage.lines.find((line) => !line.you && (line.audioKey || line.key) === voice.speakingKey) ?? null : null;
  const heardMouth = useMouth(voice, heard ? heard.audioKey || heard.key : null, heard?.fr ?? null);
  const castOnPlate = drawn ? (
    // Toi stands in the corner only when no balloon already speaks for the learner.
    <PanelStage
      members={stage.cast ?? []}
      you={variant !== 'bubble' && stage.lines.some((line) => line.you)}
      talking={heard ? { id: heard.speakerId || heard.who, mouth: heardMouth } : null}
    />
  ) : null;
  const page = pageArt ? resolveMediaUrl(pageArt) : null;
  const alt = stage.imageAlt
    || (stage.title ? fillReaderCopy(t.plate_alt, { title: stage.title }) : '');

  /* WP-44, artboards A and B. The story reader reads in the order a reader
     reads: the picture, then what happened, then who said what. The bubble
     variant moves the single reply onto the picture it belongs to; nothing
     else about the panel changes, and the words are the same words. */
  if (variant) {
    // WP-110: when the learner spoke in this panel, their line is the balloon;
    // the characters keep their captions (S-2/F-2).
    const bubbleLine =
      variant === 'bubble' ? stage.lines.find((line) => line.you) ?? stage.lines[0] : null;
    const speech = stage.lines.filter((line) => line !== bubbleLine).map((line) => (
      <SpeechBody
        key={line.key}
        line={line}
        stage={stage}
        showTranslation={showTranslation}
        onWord={onWord}
        compact
        voice={voice}
        rayons={rayons}
        t={t}
      />
    ));
    return (
      <>
        {artReady && src ? (
          <PlateArt
            src={src}
            alt={alt}
            pending={!drawn && Boolean(stage.artPending)}
            ribbon={fillReaderCopy(t.art_on_press, { n: stage.ordinal })}
            variant={variant}
            pan={Boolean(stage.silent)}
          >
            {castOnPlate}
            {bubbleLine && (
              <div
                className="fr-bubble"
                data-char={bubbleLine.character || stage.character || undefined}
                data-you={bubbleLine.you ? 'true' : undefined}
              >
                <p className="fr-speaker" data-face={bubbleLine.faceId ? 'true' : undefined}>
                  {bubbleLine.faceId && <SpeakerFace line={bubbleLine} voice={voice} t={t} />}
                  {bubbleLine.who}
                </p>
                <FrenchLine
                  text={bubbleLine.fr}
                  idPrefix={bubbleLine.key}
                  wordLabel={t.word_help}
                  {...lineRayons(bubbleLine, rayons)}
                  onWord={(word) =>
                    onWord(word, {
                      sentence: bubbleLine.fr,
                      sentenceEn: bubbleLine.en,
                      character: bubbleLine.character || stage.character,
                      speaker: bubbleLine.who,
                      speakerId: bubbleLine.you ? null : bubbleLine.speakerId ?? null,
                      panelId: stage.panelId,
                      lineKey: bubbleLine.audioKey,
                    })
                  }
                />
              </div>
            )}
          </PlateArt>
        ) : null}

        {stage.caption && (
          <FrenchLine
            className="fr-caption"
            text={stage.caption}
            idPrefix={`${stage.key}-cap`}
            wordLabel={t.word_help}
            onWord={(word) => onWord(word, { sentence: stage.caption, character: stage.character })}
          />
        )}
        {stage.silent && <p className="fr-caption fr-caption--silent">{t.silent_beat}</p>}

        {speech.length > 0 && <div className="fr-captions">{speech}</div>}
      </>
    );
  }

  return (
    <>
      {artReady && src ? (
        <figure className="fr-plate" data-pan={stage.silent ? 'slow' : undefined}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={alt} />
          {castOnPlate}
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
          voice={voice}
          rayons={rayons}
          t={t}
        />
      ))}

      {stage.caption && (
        <FrenchLine
          className="fr-caption"
          text={stage.caption}
          idPrefix={`${stage.key}-cap`}
          wordLabel={t.word_help}
          onWord={(word) => onWord(word, { sentence: stage.caption, character: stage.character })}
        />
      )}
      {stage.silent && <p className="fr-caption fr-caption--silent">{t.silent_beat}</p>}
    </>
  );
}

/**
 * WP-90: the «case finale» — the day's ending as the reader's last panel.
 * Its picture, the character's line with their face, what happened in the
 * learner's language, then whatever the caller adds (the register note, the
 * chapter recap). While the ending is being written, the speaker's face waits
 * in its place.
 */
function FinaleBody({
  stage,
  finale,
  voice,
  wait,
  extra,
  t,
}: {
  stage: Extract<ReaderStage, { kind: 'resolution' }>;
  finale: NonNullable<Extract<ReaderStage, { kind: 'resolution' }>['finale']>;
  voice?: LineVoice | null;
  wait?: React.ReactNode;
  extra?: React.ReactNode;
  t: ReaderCopy;
}) {
  const src = finale.imageUrl ? resolveMediaUrl(finale.imageUrl) : '';
  const line = finale.line;
  return (
    <div className="fr-finale" data-char={stage.character || undefined}>
      <p className="fr-finale__label">
        <span className="tri" aria-hidden="true" />
        {t.finale_label}
      </p>
      {finale.waiting ? (
        wait
      ) : (
        <>
          {src && (
            <PlateArt src={src} alt={finale.imageAlt} pending={false} ribbon="" variant="line" />
          )}
          {line && (
            <div className="fr-speech" data-compact="true" data-char={line.character || undefined}>
              {line.faceId ? (
                <SpeakerFace line={line} voice={voice} t={t} />
              ) : (
                <span className="fr-speech__bare" aria-hidden="true" />
              )}
              <div className="fr-speech__text">
                {line.who && <p className="fr-speaker">{line.who}</p>}
                {/* the ending's line reads as one sentence, the day's last word */}
                <p className="fr-line" lang="fr">
                  {frenchSpacing(line.fr)}
                </p>
              </div>
            </div>
          )}
          {finale.summary && <p className="fr-finale__summary">{finale.summary}</p>}
          {/* WP-110: «À suivre…» — tomorrow's line closes the page. */}
          {stage.aSuivre && (
            <div className="fr-notice" data-a-suivre-box="true">
              <p className="fr-eyebrow">{t.to_follow}</p>
              <p className="fr-a-suivre" lang="fr" data-a-suivre="true">
                {frenchSpacing(stage.aSuivre)}
              </p>
            </div>
          )}
          {extra}
        </>
      )}
    </div>
  );
}

function ResolutionBody({ stage, t }: { stage: Extract<ReaderStage, { kind: 'resolution' }>; t: ReaderCopy }) {
  if (!stage.hookQuestion && !stage.hookBeat && !stage.aSuivre) return null;
  if (!stage.aSuivre) {
    return (
      <div className="fr-notice" data-char={stage.character || undefined}>
        <p className="fr-eyebrow">{t.to_follow}</p>
        {stage.hookQuestion && <h2>{stage.hookQuestion}</h2>}
        {stage.hookBeat && <p>{stage.hookBeat}</p>}
      </div>
    );
  }
  // WP-110: the ending, then «À suivre…» with tomorrow's line — the page's last words.
  return (
    <div className="fr-notice" data-char={stage.character || undefined}>
      {stage.hookQuestion && <h2>{stage.hookQuestion}</h2>}
      {stage.hookBeat && <p>{stage.hookBeat}</p>}
      <p className="fr-eyebrow fr-a-suivre__label">{t.to_follow}</p>
      <p className="fr-a-suivre" lang="fr" data-a-suivre="true">
        {frenchSpacing(stage.aSuivre)}
      </p>
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
    context: WordContext,
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
