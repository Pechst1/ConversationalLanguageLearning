/**
 * Step renderers for the daily journey (WP-07 functional milestone).
 *
 * Presentation only: every one of these takes state and callbacks as props and
 * performs no request of its own, so the Claude-Design renderer can replace
 * them without touching `useDailyJourney`.
 *
 * Existing app primitives only — `ExerciseShell`, `Button`, `FeedbackSheet` —
 * plus component-scoped `styled-jsx`. No global CSS reset, no new fonts, no
 * second design system.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Mic, Square } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { ExerciseShell } from '@/components/ui/ExerciseShell';
import { FeedbackSheet } from '@/components/ui/FeedbackSheet';
import { resolveMediaUrl } from '@/lib/media-url';
import type {
  AttemptInput,
  HelpKind,
  HelpResult,
  RecallStep,
  RespondStep,
  ResolutionStep,
  SceneStep,
} from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import {
  answerIsBlank,
  textOffered,
  voiceOffered,
  type JourneyFeedback,
  type ReplyProvenance,
} from './journey-state';
import type { VoiceState } from './useDailyJourney';

export type StepViewCommonProps = {
  copy: JourneyCopy;
  busy: boolean;
  feedback: JourneyFeedback;
  help: HelpResult | null;
  onHelp: (kind: HelpKind) => void;
  onSubmit: (input: AttemptInput) => void;
  onContinue: () => void;
  /**
   * Draft persistence for the two free-text fields (WP-10). Optional so a
   * renderer can be exercised without a store; when it is supplied the text the
   * learner typed survives a kill, a background, and a cold start.
   *
   * A draft is only ever a draft. It is never shown as an answer that was sent,
   * and it never carries a grade.
   */
  draft?: { get: (key: string) => string; set: (key: string, text: string) => void };
};

const HELP_LABEL: Record<HelpKind, keyof JourneyCopy> = {
  hint: 'help_hint',
  translation: 'help_translation',
  solution: 'help_solution',
  suggested_response: 'help_suggested_response',
};

/** Help is on demand and never in front of the prompt. */
export function HelpRow({
  available,
  used,
  copy,
  busy,
  help,
  onHelp,
}: {
  available: HelpKind[];
  used: string[];
  copy: JourneyCopy;
  busy: boolean;
  help: HelpResult | null;
  onHelp: (kind: HelpKind) => void;
}) {
  if (!available.length) return null;
  return (
    <div className="journey-help">
      <div className="journey-help-actions">
        {available.map((kind) => (
          <Button
            key={kind}
            type="button"
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={() => onHelp(kind)}
          >
            {copy[HELP_LABEL[kind]]}
          </Button>
        ))}
      </div>
      {used.length > 0 && (
        <p className="journey-help-used">
          {copy.assistance_used}: {used.join(', ')}
        </p>
      )}
      {help && (
        <div className="journey-help-content" role="status">
          <b>{copy[HELP_LABEL[help.help_kind]]}</b>
          {help.content_fr && <p lang="fr">{help.content_fr}</p>}
          {help.content_native && <p>{help.content_native}</p>}
        </div>
      )}
      <style jsx>{`
        .journey-help {
          display: grid;
          gap: 8px;
        }
        .journey-help-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .journey-help-used,
        .journey-help-content p {
          margin: 0;
          font-size: 13px;
          line-height: 1.4;
          color: var(--app-ink-2);
        }
        .journey-help-content {
          border: 1px dashed var(--app-ink);
          padding: 10px 12px;
          display: grid;
          gap: 4px;
          background: var(--app-paper-2);
        }
        .journey-help-content b {
          font-size: 11px;
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }
      `}</style>
    </div>
  );
}

/** Artwork is decoration: a missing image never blocks reading or answering. */
function StepArt({ url, alt }: { url: string | null; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className="journey-art"
      src={resolveMediaUrl(url) || url}
      alt={alt}
      onError={() => setFailed(true)}
      style={{ width: '100%', height: 'auto', border: '1px solid var(--app-ink)' }}
    />
  );
}

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------

export function SceneStepView({
  step,
  copy,
  busy,
  onContinue,
}: { step: SceneStep } & Pick<StepViewCommonProps, 'copy' | 'busy' | 'onContinue'>) {
  return (
    <ExerciseShell eyebrow={copy.today_eyebrow} title={step.prompt.objective_native}>
      <div className="journey-step">
        <StepArt url={step.prompt.image_url} alt={step.prompt.setup_native} />
        <p lang="fr" className="journey-lead">
          {step.prompt.setup_fr}
        </p>
        <p className="journey-native">{step.prompt.setup_native}</p>
        {step.prompt.character_line_fr && (
          <blockquote lang="fr" className="journey-line">
            {step.prompt.character_line_fr}
          </blockquote>
        )}
        <Button type="button" onClick={onContinue} disabled={busy} className="journey-primary">
          {busy ? copy.sending : copy.scene_continue}
        </Button>
      </div>
      <StepStyles />
    </ExerciseShell>
  );
}

// ---------------------------------------------------------------------------
// Recall
// ---------------------------------------------------------------------------

export function RecallStepView({
  step,
  copy,
  busy,
  feedback,
  help,
  onHelp,
  onSubmit,
  draft,
}: { step: RecallStep } & StepViewCommonProps) {
  const [choice, setChoice] = useState<string | null>(null);
  const [tiles, setTiles] = useState<string[]>([]);
  // A recall draft is keyed by the step: one step, one written answer.
  const draftKey = step.id;
  const [text, setText] = useState(() => draft?.get(draftKey) ?? '');
  const locked = busy || feedback.kind === 'graded' || feedback.kind === 'submitting';

  useEffect(() => {
    // A new step is a new answer; the same step keeps what the learner picked,
    // and a cold start gets back whatever was typed before the interruption.
    setChoice(null);
    setTiles([]);
    setText(draft?.get(draftKey) ?? '');
  }, [draft, draftKey, step.id]);

  const remainingTiles = useMemo(
    () => step.prompt.options.filter((option) => !tiles.includes(option.id)),
    [step.prompt.options, tiles],
  );

  const ready =
    step.prompt.task_type === 'choice'
      ? Boolean(choice)
      : step.prompt.task_type === 'tiles'
        ? tiles.length > 0
        : !answerIsBlank(text);

  const submit = () => {
    if (step.prompt.task_type === 'choice' && choice) {
      onSubmit({ mode: 'choice', option_id: choice });
      return;
    }
    if (step.prompt.task_type === 'tiles' && tiles.length) {
      onSubmit({ mode: 'tiles', tile_ids: tiles });
      return;
    }
    onSubmit({ mode: 'text', text });
  };

  return (
    <ExerciseShell eyebrow={copy.today_eyebrow} title={step.prompt.instruction_native}>
      <div className="journey-step">
        {step.prompt.prompt_fr && (
          <p lang="fr" className="journey-lead">
            {step.prompt.prompt_fr}
          </p>
        )}

        {step.prompt.task_type === 'choice' && (
          <ul className="journey-options" role="radiogroup" aria-label={step.prompt.instruction_native}>
            {step.prompt.options.map((option) => {
              const selected = choice === option.id;
              return (
                <li key={option.id}>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    className={selected ? 'journey-option selected' : 'journey-option'}
                    disabled={locked}
                    onClick={() => setChoice(option.id)}
                  >
                    <span lang="fr">{option.text_fr}</span>
                    {selected && <b aria-hidden="true">✓</b>}
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {step.prompt.task_type === 'tiles' && (
          <div className="journey-tiles">
            <p className="journey-tile-line" lang="fr" aria-live="polite">
              {tiles
                .map((id) => step.prompt.options.find((option) => option.id === id)?.text_fr || '')
                .join(' ') || '—'}
            </p>
            <div className="journey-tile-bank">
              {remainingTiles.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className="journey-option"
                  disabled={locked}
                  onClick={() => setTiles((current) => [...current, option.id])}
                >
                  <span lang="fr">{option.text_fr}</span>
                </button>
              ))}
            </div>
            {tiles.length > 0 && !locked && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setTiles((current) => current.slice(0, -1))}
              >
                ←
              </Button>
            )}
          </div>
        )}

        {step.prompt.task_type === 'short_answer' && (
          <label className="journey-field">
            <span>{copy.answer_label}</span>
            <textarea
              lang="fr"
              rows={2}
              value={text}
              disabled={locked}
              placeholder={copy.answer_placeholder}
              onChange={(event) => {
                setText(event.target.value);
                draft?.set(draftKey, event.target.value);
              }}
            />
          </label>
        )}

        <Button
          type="button"
          onClick={submit}
          disabled={locked || !ready}
          className="journey-primary"
        >
          {feedback.kind === 'submitting' ? copy.sending : copy.check}
        </Button>

        <HelpRow
          available={step.prompt.help_available}
          used={step.assistance_used.filter((level) => level !== 'none')}
          copy={copy}
          busy={busy}
          help={help}
          onHelp={onHelp}
        />
      </div>
      <StepStyles />
    </ExerciseShell>
  );
}

// ---------------------------------------------------------------------------
// Respond
// ---------------------------------------------------------------------------

export function RespondStepView({
  step,
  copy,
  busy,
  feedback,
  help,
  voice,
  onHelp,
  onSubmit,
  onStartRecording,
  onStopRecording,
  onResetVoice,
  draft,
}: { step: RespondStep; voice: VoiceState } & StepViewCommonProps & {
    onStartRecording: () => void;
    onStopRecording: () => void;
    onResetVoice: () => void;
  }) {
  // A respond step can hold more than one turn, and each turn is its own
  // answer, so the turn is part of the key: a new turn starts clean rather
  // than reopening with the sentence the learner already sent.
  const draftKey = `${step.id}:${step.prompt.turn_index}`;
  const [text, setText] = useState(() => draft?.get(draftKey) ?? '');
  const [mode, setMode] = useState<'text' | 'voice'>('text');
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const canSpeak = voiceOffered(step.prompt);
  const canType = textOffered(step.prompt);
  // A graded turn is closed until the learner continues: re-submitting into a
  // completed step would only earn a 409 `step_not_active`.
  const locked =
    busy ||
    feedback.kind === 'submitting' ||
    feedback.kind === 'graded' ||
    voice.kind === 'recording' ||
    voice.kind === 'transcribing';

  useEffect(() => {
    // A new turn starts empty but keeps the same mounted field, so focus and
    // the software keyboard survive the round trip. A resumed turn comes back
    // with exactly what the learner had typed.
    setText(draft?.get(draftKey) ?? '');
  }, [draft, draftKey]);

  useEffect(() => {
    if (!canSpeak && mode === 'voice') setMode('text');
  }, [canSpeak, mode]);

  return (
    <ExerciseShell eyebrow={step.prompt.character_name} title={step.prompt.objective_native}>
      <div className="journey-step">
        <blockquote lang="fr" className="journey-line">
          {step.prompt.character_line_fr}
        </blockquote>

        {step.prompt.targets.length > 0 && (
          <div className="journey-targets">
            {step.prompt.targets.map((target) => (
              <span className="journey-target" key={`${target.kind}:${target.id}`} lang="fr">
                {target.label_fr}
              </span>
            ))}
          </div>
        )}

        {canSpeak && canType && (
          <div className="journey-modes" role="group">
            <Button
              type="button"
              size="sm"
              variant={mode === 'text' ? 'default' : 'outline'}
              aria-pressed={mode === 'text'}
              onClick={() => {
                setMode('text');
                onResetVoice();
              }}
            >
              {copy.use_text}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={mode === 'voice' ? 'default' : 'outline'}
              aria-pressed={mode === 'voice'}
              onClick={() => setMode('voice')}
            >
              {copy.use_voice}
            </Button>
          </div>
        )}

        {/* Text is always a full path, whatever the microphone is doing. */}
        <label className="journey-field">
          <span>{copy.answer_label}</span>
          <textarea
            ref={inputRef}
            lang="fr"
            rows={3}
            value={text}
            disabled={locked}
            placeholder={copy.answer_placeholder}
            onChange={(event) => {
              setText(event.target.value);
              draft?.set(draftKey, event.target.value);
            }}
          />
        </label>

        <div className="journey-actions">
          <Button
            type="button"
            className="journey-primary"
            disabled={locked || answerIsBlank(text)}
            onClick={() => onSubmit({ mode: 'text', text })}
          >
            {feedback.kind === 'submitting' ? copy.sending : copy.send}
          </Button>

          {canSpeak && mode === 'voice' && (
            <Button
              type="button"
              variant="outline"
              disabled={busy || voice.kind === 'transcribing'}
              leftIcon={
                voice.kind === 'recording' ? (
                  <Square size={16} />
                ) : voice.kind === 'transcribing' ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Mic size={16} />
                )
              }
              onClick={() => (voice.kind === 'recording' ? onStopRecording() : onStartRecording())}
            >
              {voice.kind === 'recording'
                ? copy.stop_recording
                : voice.kind === 'transcribing'
                  ? copy.transcribing
                  : copy.record}
            </Button>
          )}
        </div>

        {(voice.kind === 'failed' || voice.kind === 'unsupported') && (
          <p className="journey-notice" role="status">
            {copy.voice_failed}
          </p>
        )}

        <HelpRow
          available={step.prompt.help_available}
          used={step.assistance_used.filter((level) => level !== 'none')}
          copy={copy}
          busy={busy}
          help={help}
          onHelp={onHelp}
        />
      </div>
      <StepStyles />
    </ExerciseShell>
  );
}

// ---------------------------------------------------------------------------
// Resolution
// ---------------------------------------------------------------------------

export function ResolutionStepView({
  step,
  copy,
  busy,
  onContinue,
}: { step: ResolutionStep } & Pick<StepViewCommonProps, 'copy' | 'busy' | 'onContinue'>) {
  return (
    <ExerciseShell eyebrow={copy.today_eyebrow} title={step.prompt.summary_native}>
      <div className="journey-step">
        <StepArt url={step.prompt.image_url} alt={step.prompt.summary_native} />
        <blockquote lang="fr" className="journey-line">
          {step.prompt.character_line_fr}
        </blockquote>
        <Button type="button" onClick={onContinue} disabled={busy} className="journey-primary">
          {busy ? copy.sending : copy.continue}
        </Button>
      </div>
      <StepStyles />
    </ExerciseShell>
  );
}

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------

function replyNote(source: ReplyProvenance, copy: JourneyCopy): string | undefined {
  // Only an explicitly authored line is labelled. `unknown` says nothing rather
  // than claiming the reply was generated live.
  return source === 'authored' ? copy.reply_authored_note : undefined;
}

export function JourneyFeedbackView({
  feedback,
  copy,
  onContinue,
  onRetry,
  onDismiss,
}: {
  feedback: JourneyFeedback;
  copy: JourneyCopy;
  onContinue: () => void;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  switch (feedback.kind) {
    case 'idle':
    case 'submitting':
      return null;

    case 'retrying':
      return (
        <p className="journey-notice" role="status" data-state="retrying">
          {copy.retrying}
          <StepStyles />
        </p>
      );

    case 'empty':
      return (
        <p className="journey-notice" role="alert" data-state="empty">
          {copy.empty_answer}
          <StepStyles />
        </p>
      );

    case 'unscored':
      return (
        <div className="journey-notice" role="status" data-state="unscored">
          <p>{copy.still_grading}</p>
          <Button type="button" size="sm" variant="outline" onClick={onRetry}>
            {copy.try_grading_again}
          </Button>
          <StepStyles />
        </div>
      );

    case 'reconciled':
      return (
        <div className="journey-notice" role="status" data-state="reconciled">
          <p>{copy.reconciled}</p>
          <Button type="button" size="sm" variant="outline" onClick={onDismiss}>
            {copy.continue}
          </Button>
          <StepStyles />
        </div>
      );

    case 'error':
      return (
        <div className="journey-notice" role="alert" data-state="error">
          <p>{copy.transport_error}</p>
          {feedback.retryable && (
            <Button type="button" size="sm" variant="outline" onClick={onRetry}>
              {copy.retry}
            </Button>
          )}
          <StepStyles />
        </div>
      );

    case 'graded': {
      const { result, verdict, replySource } = feedback;
      const title =
        verdict === 'correct' ? copy.correct : verdict === 'supported' ? copy.supported : copy.wrong;
      const note = replyNote(replySource, copy);
      return (
        // `.atelier-feedback-sheet` is a fixed bottom-right slip in the legacy
        // flow. Inside the journey it belongs in normal flow, directly under the
        // answer, so it cannot cover the input or sit behind the bottom nav.
        <div className="journey-feedback" data-state={verdict}>
          <FeedbackSheet
            status={verdict === 'wrong' ? 'wrong' : 'correct'}
            title={title}
            explanation={result.character_reply_fr || undefined}
            rule={note}
            correctionItems={
              result.correction
                ? [
                    {
                      title: copy.correction,
                      explanation: `${result.correction.span_fr} → ${result.correction.corrected_fr}`,
                      repair: result.correction.note_native,
                    },
                  ]
                : undefined
            }
            onNext={onContinue}
            nextLabel={copy.continue}
          />
        </div>
      );
    }

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Scoped styles — component-local, no global selectors
// ---------------------------------------------------------------------------

export function StepStyles() {
  return (
    <style jsx global>{`
      .journey-step {
        display: grid;
        gap: 14px;
        min-width: 0;
      }
      .journey-step .journey-lead {
        margin: 0;
        font-size: 17px;
        line-height: 1.45;
      }
      .journey-step .journey-native {
        margin: 0;
        font-size: 14px;
        line-height: 1.45;
        color: var(--app-ink-2);
      }
      .journey-step .journey-line {
        margin: 0;
        border-left: 3px solid var(--app-ink);
        padding: 6px 0 6px 12px;
        font-size: 17px;
        line-height: 1.45;
      }
      .journey-step .journey-options {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        gap: 8px;
      }
      .journey-step .journey-option {
        width: 100%;
        min-height: 44px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        border: 1px solid var(--app-ink);
        background: var(--app-sheet);
        color: var(--app-ink);
        padding: 10px 12px;
        text-align: left;
        font-size: 16px;
        line-height: 1.35;
        overflow-wrap: anywhere;
      }
      .journey-step .journey-option.selected {
        background: var(--app-yellow, var(--app-paper-2));
        border-width: 2px;
        font-weight: 600;
      }
      /* A disabled option must stay readable: dim the border, never the text. */
      .journey-step .journey-option:disabled {
        opacity: 1;
        cursor: default;
        border-color: var(--app-ink-3);
        color: var(--app-ink);
      }
      .journey-step .journey-option.selected:disabled {
        border-color: var(--app-ink);
      }
      .journey-step .journey-option:focus-visible {
        outline: 2px solid var(--app-ink);
        outline-offset: 2px;
      }
      .journey-step .journey-tiles {
        display: grid;
        gap: 8px;
      }
      .journey-step .journey-tile-line {
        margin: 0;
        min-height: 44px;
        border-bottom: 1px solid var(--app-ink);
        font-size: 17px;
        line-height: 1.4;
        overflow-wrap: anywhere;
      }
      .journey-step .journey-tile-bank {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .journey-step .journey-tile-bank .journey-option {
        width: auto;
      }
      .journey-step .journey-field {
        display: grid;
        gap: 6px;
      }
      .journey-step .journey-field > span {
        font-size: 11px;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--app-ink-3);
      }
      .journey-step .journey-field textarea {
        width: 100%;
        min-height: 88px;
        border: 1px solid var(--app-ink);
        background: var(--app-sheet);
        color: var(--app-ink);
        padding: 10px 12px;
        font: inherit;
        font-size: 16px; /* keeps iOS from zooming the viewport on focus */
        line-height: 1.4;
        resize: vertical;
      }
      .journey-step .journey-field textarea:disabled {
        opacity: 1;
        color: var(--app-ink-2);
      }
      .journey-step .journey-actions,
      .journey-step .journey-modes {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .journey-step .journey-actions .journey-primary {
        flex: 1 1 12rem;
      }
      .journey-step .journey-targets {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .journey-step .journey-target {
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        border: 1px solid var(--app-ink-3);
        background: var(--app-paper-2);
        padding: 2px 8px;
        font-size: 13px;
        line-height: 1.3;
      }
      .journey-feedback {
        min-width: 0;
      }
      .journey-feedback .atelier-feedback-sheet {
        position: static;
        width: 100%;
        max-width: none;
        right: auto;
        bottom: auto;
        z-index: auto;
        animation: none;
      }
      .journey-feedback .atelier-feedback-sheet .feedback-actions {
        flex-wrap: wrap;
      }
      .journey-notice {
        margin: 12px 0 0;
        display: grid;
        gap: 8px;
        justify-items: start;
        border: 1px solid var(--app-ink);
        background: var(--app-paper-2);
        padding: 10px 12px;
        font-size: 14px;
        line-height: 1.4;
      }
      .journey-notice[data-state='empty'],
      .journey-notice[data-state='error'] {
        border-left-width: 4px;
      }
      .journey-notice p {
        margin: 0;
      }
      @media (max-width: 360px) {
        .journey-step .journey-actions .journey-primary {
          flex-basis: 100%;
        }
      }

      /* -------------------------------------------------------------------
         Reachability at 320 CSS px with 200% text.

         Every size in this screen is rem-based, so at 200% text a single
         uppercase word ("TRANSLATION") is wider than the whole column. Left
         alone the shared exercise shell grows past the viewport; the document
         does not scroll horizontally, so the answer field and the primary
         action are clipped out of reach rather than merely off-screen.

         Three rules, every selector scoped under .journey-shell so nothing
         here can reach a legacy page:
           1. the shell and its body may not impose a minimum width wider than
              the grid track they sit in;
           2. long words break instead of pushing the layout outwards;
           3. a control label wraps rather than setting the row's width.
         ------------------------------------------------------------------- */
      .journey-shell .atelier-exercise-shell,
      .journey-shell .atelier-exercise-shell > header,
      .journey-shell .atelier-exercise-shell > header > div,
      .journey-shell .atelier-exercise-shell-body {
        min-width: 0;
        max-width: 100%;
      }
      .journey-shell .atelier-exercise-shell > header h2,
      .journey-shell .atelier-exercise-shell > header span {
        overflow-wrap: anywhere;
      }

      /* -------------------------------------------------------------------
         Touch targets. The shared Button 'sm' size is 40px tall, which is
         under the 44px minimum on every one of these secondary controls
         (hint / translation / show the answer / suggest a reply / stop here /
         pause). Raising the minimum height rather than the font size keeps
         the visual weight and makes the target reachable; height:auto is
         required alongside it so a label that now wraps is not clipped.
         ------------------------------------------------------------------- */
      .journey-shell button {
        height: auto;
        min-height: 44px;
        min-width: 0;
        max-width: 100%;
        white-space: normal;
        overflow-wrap: anywhere;
      }
    `}</style>
  );
}
