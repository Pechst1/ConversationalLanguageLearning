/**
 * Step renderers for the daily journey — WP-07 **visual** milestone.
 *
 * Presentation only. Every one of these takes state and callbacks as props and
 * performs no request of its own, so `useDailyJourney`, `journey-state.ts` and
 * `journey-requests.ts` are reused byte-for-byte from the functional milestone.
 * The functional pass rendered these through the legacy `ExerciseShell`; this
 * pass swaps that for the Atelier V2 design system and changes nothing else.
 *
 * ---------------------------------------------------------------------------
 * Design mapping — `docs/design-reference/claude/Atelier App.dc.html`, Séance
 * ---------------------------------------------------------------------------
 * Taken verbatim: the blue step label, the "La règle" pill that discloses a
 * rounded rule card, the Garamond-italic prompt, the 2px-edge option cards with
 * their `0 3px 0` press and their selected/correct/wrong colouring, the footer
 * feedback band with its round icon badge and tinted ground, and the single
 * 3D-press primary whose label cycles check → continue.
 *
 * Deliberately NOT taken: the design's Séance is a three-exercise grammar drill
 * with a "12 jours de suite" streak counter. Our product is the 3–5 step
 * journey, and CONTRACTS forbids a fabricated streak. The chrome is reused; the
 * numbers come from the real plan, and the streak is simply absent. Recorded in
 * FRONTEND-ENGINE-HANDOFF §4.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';

import {
  Action,
  Artwork,
  Byline,
  ChoiceList,
  Chip,
  Correction,
  FeedbackBand,
  IconAction,
  MicIcon,
  Notice,
  ShapeToken,
  StopIcon,
  Surface,
  WordTiles,
  textAnswerField,
  type ChoiceOption,
} from '@/components/atelier-v2/ui';
import { atelierCopy, type AtelierCopy } from '@/lib/atelier-v2-copy';
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

/**
 * The renderers take the copy table as a prop, exactly as they did in the
 * functional milestone, so they stay drop-in replacements: `pages/atelier.tsx`
 * and `journey.test.js` call them unchanged.
 *
 * `JourneySession` and `JourneyTodayCard` merge the V2 chrome keys (action
 * names, status words) into that table in the learner's own language before
 * passing it down, so the common path is a plain object read. A caller that
 * passes a bare `journeyCopy(...)` table — which is what the node test harness
 * does — gets the English chrome filled in rather than raw keys on screen.
 *
 * Deliberately a plain function rather than a context hook: these renderers are
 * exercised outside a React tree by the test harness, and presentation should
 * not require a provider to produce correct output.
 */
function widenCopy(copy: JourneyCopy): AtelierCopy {
  return (copy as Partial<AtelierCopy>).action_check
    ? (copy as AtelierCopy)
    : { ...atelierCopy('en'), ...copy };
}

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

// ---------------------------------------------------------------------------
// Shared frame
// ---------------------------------------------------------------------------

/**
 * The Séance chrome every step shares: a blue step label, one Garamond-italic
 * headline, the body, and one primary action.
 *
 * `label` is the design's blue "Reconnaître · 1/3" line. Ours never carries an
 * exercise count, because the plan has steps, not drills.
 */
function StepFrame({
  label,
  headline,
  headlineLang,
  children,
}: {
  label: React.ReactNode;
  headline: React.ReactNode;
  headlineLang?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="av2-stack av2-step">
      <p className="av2-label av2-label--story">{label}</p>
      <h2 className="av2-headline" lang={headlineLang}>
        {headline}
      </h2>
      {children}
    </section>
  );
}

/**
 * Help — on demand, never in front of the prompt.
 *
 * The design's "La règle" pill and the rounded card it discloses. Each help
 * kind gets its own pill; whatever the server returns renders in the card. The
 * assistance already spent is stated plainly, because it is what turns a
 * correct answer into a supported one.
 */
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
  const wide = widenCopy(copy);

  return (
    <div className="av2-stack av2-help">
      <div className="av2-help__actions">
        {available.map((kind) => (
          <Chip
            key={kind}
            icon={<ShapeToken kind="reward" size="sm" />}
            disabled={busy}
            onClick={() => onHelp(kind)}
          >
            {copy[HELP_LABEL[kind]]}
          </Chip>
        ))}
      </div>

      {used.length > 0 && (
        <p className="av2-label">
          {copy.assistance_used}: {used.join(', ')}
        </p>
      )}

      {help && (
        <Surface role="status" aria-label={wide.rule_card}>
          <p className="av2-label">{copy[HELP_LABEL[help.help_kind]]}</p>
          {help.content_fr && (
            <p className="av2-fr av2-headline av2-headline--rule" lang="fr">
              {help.content_fr}
            </p>
          )}
          {help.content_native && <p className="av2-body av2-body--lg">{help.content_native}</p>}
        </Surface>
      )}
    </div>
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
  const wide = widenCopy(copy);
  return (
    <StepFrame label={copy.today_eyebrow} headline={step.prompt.setup_fr} headlineLang="fr">
      {step.prompt.image_url && (
        <Surface shape="hero" aria-hidden={false}>
          <Artwork
            url={step.prompt.image_url}
            // The scene's own gloss is the honest description of its art.
            alt={step.prompt.setup_native}
            fallbackLabel={wide.artwork_unavailable}
          />
        </Surface>
      )}

      <p className="av2-body av2-body--lg">{step.prompt.setup_native}</p>

      {step.prompt.character_line_fr && (
        <Surface>
          <p className="av2-fr av2-headline av2-headline--rule" lang="fr">
            {step.prompt.character_line_fr}
          </p>
        </Surface>
      )}

      <p className="av2-label">
        {copy.objective}: {step.prompt.objective_native}
      </p>

      <Action
        tone="primary"
        pending={busy}
        pendingLabel={copy.sending}
        onClick={onContinue}
      >
        {copy.scene_continue}
      </Action>
    </StepFrame>
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
  const wide = widenCopy(copy);
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

  const options = useMemo<ChoiceOption[]>(
    () =>
      step.prompt.options.map((option) => ({
        id: option.id,
        textFr: option.text_fr,
      })),
    [step.prompt.options],
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
    <StepFrame
      label={copy.today_eyebrow}
      headline={step.prompt.prompt_fr || step.prompt.instruction_native}
      headlineLang={step.prompt.prompt_fr ? 'fr' : undefined}
    >
      {step.prompt.prompt_fr && (
        <p className="av2-body av2-body--lg">{step.prompt.instruction_native}</p>
      )}

      {step.prompt.task_type === 'choice' && (
        <ChoiceList
          options={options}
          selectedId={choice}
          label={step.prompt.instruction_native}
          disabled={locked}
          onSelect={setChoice}
          statusLabels={{
            selected: wide.status_selected,
            correct: wide.status_correct,
            wrong: wide.status_wrong,
          }}
        />
      )}

      {step.prompt.task_type === 'tiles' && (
        <WordTiles
          options={options}
          placed={tiles}
          label={step.prompt.instruction_native}
          emptyHint={wide.tiles_empty}
          removeLabel={wide.remove_last}
          disabled={locked}
          onPlace={(id) => setTiles((current) => [...current, id])}
          onRemoveLast={() => setTiles((current) => current.slice(0, -1))}
        />
      )}

      {step.prompt.task_type === 'short_answer' && (
        // Called as a factory, not rendered as a child component, so the
        // field lives in this step's own element tree — that is the surface
        // the WP-10 draft-recovery tests drive.
        textAnswerField({
          label: copy.answer_label,
          value: text,
          rows: 2,
          disabled: locked,
          placeholder: copy.answer_placeholder,
          invalid: feedback.kind === 'empty',
          onChange: (next) => {
            setText(next);
            draft?.set(draftKey, next);
          },
        })
      )}

      <Action
        tone="primary"
        disabled={locked || !ready}
        pending={feedback.kind === 'submitting'}
        pendingLabel={copy.sending}
        onClick={submit}
      >
        {copy.check}
      </Action>

      <HelpRow
        available={step.prompt.help_available}
        used={step.assistance_used.filter((level) => level !== 'none')}
        copy={copy}
        busy={busy}
        help={help}
        onHelp={onHelp}
      />
    </StepFrame>
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
  const wide = widenCopy(copy);
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
    <StepFrame
      label={<Byline name={step.prompt.character_name} />}
      headline={step.prompt.character_line_fr}
      headlineLang="fr"
    >
      <p className="av2-body av2-body--lg">{step.prompt.objective_native}</p>

      {step.prompt.targets.length > 0 && (
        <div className="av2-help__actions">
          {step.prompt.targets.map((target) => (
            <Chip key={`${target.kind}:${target.id}`} icon={<ShapeToken kind="reward" size="sm" />}>
              <span lang="fr">{target.label_fr}</span>
            </Chip>
          ))}
        </div>
      )}

      {canSpeak && canType && (
        <div className="av2-help__actions" role="group" aria-label={copy.answer_label}>
          <Chip
            tone={mode === 'text' ? 'story' : 'plain'}
            aria-pressed={mode === 'text'}
            onClick={() => {
              setMode('text');
              onResetVoice();
            }}
          >
            {copy.use_text}
          </Chip>
          <Chip
            tone={mode === 'voice' ? 'story' : 'plain'}
            aria-pressed={mode === 'voice'}
            onClick={() => setMode('voice')}
          >
            {copy.use_voice}
          </Chip>
        </div>
      )}

      {/* Text is always a full path, whatever the microphone is doing. */}
      {textAnswerField({
        label: copy.answer_label,
        value: text,
        rows: 3,
        disabled: locked,
        placeholder: copy.answer_placeholder,
        invalid: feedback.kind === 'empty',
        inputRef,
        onChange: (next) => {
          setText(next);
          draft?.set(draftKey, next);
        },
      })}

      <div className="av2-respond__actions">
        <Action
          tone="primary"
          disabled={locked || answerIsBlank(text)}
          pending={feedback.kind === 'submitting'}
          pendingLabel={copy.sending}
          onClick={() => onSubmit({ mode: 'text', text })}
        >
          {copy.send}
        </Action>

        {canSpeak && mode === 'voice' && (
          <IconAction
            label={voice.kind === 'recording' ? copy.stop_recording : copy.record}
            tone={voice.kind === 'recording' ? 'recording' : 'action'}
            pressable
            pending={voice.kind === 'transcribing'}
            onClick={() => (voice.kind === 'recording' ? onStopRecording() : onStartRecording())}
          >
            {voice.kind === 'recording' ? <StopIcon size={18} /> : <MicIcon size={18} />}
          </IconAction>
        )}
      </div>

      {voice.kind === 'recording' && (
        <Notice shape="action">
          <p>{copy.record}</p>
        </Notice>
      )}

      {voice.kind === 'transcribing' && (
        <Notice shape="story">
          <p>{copy.transcribing}</p>
        </Notice>
      )}

      {(voice.kind === 'failed' || voice.kind === 'unsupported') && (
        <Notice shape="action">
          <p>{copy.voice_failed}</p>
        </Notice>
      )}

      <HelpRow
        available={step.prompt.help_available}
        used={step.assistance_used.filter((level) => level !== 'none')}
        copy={copy}
        busy={busy}
        help={help}
        onHelp={onHelp}
      />
    </StepFrame>
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
  const wide = widenCopy(copy);
  return (
    <StepFrame
      label={copy.today_eyebrow}
      headline={step.prompt.character_line_fr}
      headlineLang="fr"
    >
      {step.prompt.image_url && (
        <Surface shape="hero">
          <Artwork
            url={step.prompt.image_url}
            alt={step.prompt.summary_native}
            fallbackLabel={wide.artwork_unavailable}
          />
        </Surface>
      )}

      <p className="av2-body av2-body--lg">{step.prompt.summary_native}</p>

      <Action tone="primary" pending={busy} pendingLabel={copy.sending} onClick={onContinue}>
        {copy.continue}
      </Action>
    </StepFrame>
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

/**
 * Every non-idle feedback state, each visually distinct.
 *
 * The design has exactly one of these — the graded band. The other six are
 * extended from its own primitives, and the extension is deliberate rather
 * than decorative: **only a graded verdict gets the feedback band and its
 * tint.** Retrying, empty, unscored, reconciled and transport failure all
 * render as a `Notice` — no tint, no tick, no celebration — because none of
 * them is something the learner got wrong. `journey-state.ts` guarantees that
 * separation in the data; this keeps it true in the pixels.
 */
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
  const wide = widenCopy(copy);

  switch (feedback.kind) {
    case 'idle':
    case 'submitting':
      // In-flight is shown on the button, not as a verdict.
      return null;

    case 'retrying':
      return (
        <div data-state="retrying">
          <Notice shape="story">
            <p>{copy.retrying}</p>
          </Notice>
        </div>
      );

    case 'empty':
      return (
        <div data-state="empty">
          <Notice tone="alert" live="alert" shape="action">
            <p>{copy.empty_answer}</p>
          </Notice>
        </div>
      );

    case 'unscored':
      return (
        <div data-state="unscored">
          <Notice shape="story">
            <p>{copy.still_grading}</p>
            <Action tone="secondary" inline onClick={onRetry}>
              {copy.try_grading_again}
            </Action>
          </Notice>
        </div>
      );

    case 'reconciled':
      return (
        <div data-state="reconciled">
          <Notice shape="story">
            <p>{copy.reconciled}</p>
            <Action tone="secondary" inline onClick={onDismiss}>
              {copy.continue}
            </Action>
          </Notice>
        </div>
      );

    case 'error':
      return (
        <div data-state="error">
          <Notice tone="alert" live="alert" shape="action">
            <p>{copy.transport_error}</p>
            {feedback.retryable && (
              <Action tone="secondary" inline onClick={onRetry}>
                {copy.retry}
              </Action>
            )}
          </Notice>
        </div>
      );

    case 'graded': {
      const { result, verdict, replySource } = feedback;
      const title =
        verdict === 'correct' ? copy.correct : verdict === 'supported' ? copy.supported : copy.wrong;
      const note = replyNote(replySource, copy);

      return (
        <div className="av2-graded" data-state={verdict}>
          <FeedbackBand tone={verdict} title={title} detail={result.character_reply_fr || undefined}>
            {note && <p className="av2-label">{note}</p>}
            {result.correction && (
              <Correction
                label={copy.correction}
                spanFr={result.correction.span_fr}
                correctedFr={result.correction.corrected_fr}
                noteNative={result.correction.note_native}
              />
            )}
          </FeedbackBand>

          <Action tone="primary" onClick={onContinue}>
            {wide.action_continue}
          </Action>
        </div>
      );
    }

    default:
      return null;
  }
}
