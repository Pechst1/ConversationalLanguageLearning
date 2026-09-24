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
import { crLetterHeadline } from '@/components/courrier/courrier-copy';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { RuleCard } from '@/components/atelier-v2/rule/RuleCard';
import {
  checkAnswerLocally,
  correctOptionLocally,
  promptHasAnswerKey,
  shownVerdict,
  type LocalVerdict,
} from '@/lib/answer-key';
import { atelierCopy, type AtelierCopy } from '@/lib/atelier-v2-copy';
import { castIdFor, expressionForVerdict } from '@/lib/cast-faces';
import { feel, markVerdictFelt } from '@/lib/feel';
import { frenchSpacing } from '@/lib/french-typography';
import { usableCard } from '@/lib/rule-card';
import type { PortraitMood } from '@/lib/onboarding-portraits';
import type {
  AttemptInput,
  ControlLanguage,
  HelpKind,
  HelpResult,
  RecallStep,
  RespondStep,
  ResolutionStep,
  RuleStep,
  SceneStep,
} from '@/types/daily-journey';

import type { JourneyCopy } from './journey-copy';
import { journeyCopy } from './journey-copy';
import type { JourneySpeaker } from './journey-faces';
import {
  answerIsBlank,
  chapterRecapOf,
  letterOf,
  recallAttempt,
  recallIsPicked,
  registerNoteOf,
  resolutionAwaitsStory,
  sceneOpensOnAudio,
  textOffered,
  voiceOffered,
  wordBankHasSpareChips,
  type JourneyFeedback,
} from './journey-state';
import {
  FAILURE_COPY_KEY,
  micRefusalExplained,
  readAnswerMode,
  rememberMicRefusalExplained,
  submittedMode,
  voiceIsBusy,
  writeAnswerMode,
  type AnswerMode,
} from './voice-answer';
import { useVoiceAnswer } from './useVoiceAnswer';
import { MatchPairs } from './MatchPairs';
import { WhoSaid } from './WhoSaid';
import { listenTapHasAudio, optionLang } from './practice-formats';
import {
  CharacterSmiles,
  CharacterTyping,
  StoryWriting,
  TypedReply,
  respondSpeaker,
  useTypedText,
} from './ReplyStage';

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

/**
 * The answer the learner sent, once the step is graded.
 *
 * A graded step's input surface stops offering to be used — the textarea, the
 * send button and the help row all go, because none of them can do anything
 * for a step that is closed (WP-20 D-6). What the learner wrote stays on
 * screen, read-only, in the block the field occupied.
 */
function SentAnswer({ label, text }: { label: string; text: string }) {
  if (answerIsBlank(text)) return null;
  return (
    <div className="av2-field">
      <span className="av2-field__label">{label}</span>
      <p className="av2-field__sent" lang="fr">
        {text}
      </p>
    </div>
  );
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
  speaker = null,
  speakerMood = 'neutral',
  children,
}: {
  label: React.ReactNode;
  headline: React.ReactNode;
  headlineLang?: string;
  /** WP-D2: the headline is this character's line, said in a bubble beside their face. */
  speaker?: JourneySpeaker | null;
  speakerMood?: PortraitMood;
  children: React.ReactNode;
}) {
  // WP-82: a French headline (or bubble) keeps « ? ! » on its word's line.
  const shown = headlineLang === 'fr' && typeof headline === 'string' ? frenchSpacing(headline) : headline;
  const title = (
    <h2 className="av2-headline" lang={headlineLang}>
      {shown}
    </h2>
  );
  return (
    <section className="av2-stack av2-step">
      <p className="av2-label av2-label--story">{label}</p>
      {speaker ? (
        <div className="av2-speech" data-mood={speakerMood}>
          {/* Keyed on the mood, so the verdict's face pops in (at-pop). */}
          <span key={speakerMood} className="av2-speech__face">
            <CastPortrait
              characterId={speaker.id || ''}
              name={speaker.name}
              mood={speakerMood}
              size="md"
              ring
            />
          </span>
          <div
            className="av2-speech__bubble"
            data-long={typeof headline === 'string' && headline.length > 48 ? 'true' : undefined}
          >
            {title}
          </div>
        </div>
      ) : (
        title
      )}
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
          {copy.assistance_used}:{' '}
          {used.map((level) => copy[HELP_LABEL[level as HelpKind]] ?? level).join(', ')}
        </p>
      )}

      {help && (
        <Surface role="status" aria-label={wide.rule_card}>
          <p className="av2-label">{copy[HELP_LABEL[help.help_kind]]}</p>
          {help.content_fr && (
            <p className="av2-fr av2-headline av2-headline--rule" lang="fr">
              {frenchSpacing(help.content_fr)}
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

/**
 * WP-77: a line a character says, with their face. Anyone outside the drawn
 * cast keeps the round initial; the words are the same either way.
 */
export function SpokenLine({
  speaker,
  mood = 'neutral',
  children,
}: {
  speaker: JourneySpeaker | null | undefined;
  mood?: PortraitMood;
  children: React.ReactNode;
}) {
  if (!speaker) return <>{children}</>;
  return (
    <div className="av2-said" data-face={castIdFor(speaker.id, speaker.name) ? 'true' : undefined}>
      <CastPortrait characterId={speaker.id || ''} name={speaker.name} mood={mood} size="sm" />
      <div className="av2-said__body">
        <p className="av2-label">{speaker.name}</p>
        {children}
      </div>
    </div>
  );
}

export function SceneStepView({
  step,
  copy,
  busy,
  onContinue,
  speaker = null,
}: { step: SceneStep; speaker?: JourneySpeaker | null } & Pick<
  StepViewCommonProps,
  'copy' | 'busy' | 'onContinue'
>) {
  const wide = widenCopy(copy);
  return (
    <StepFrame label={copy.today_eyebrow} headline={step.prompt.setup_fr} headlineLang="fr">
      {/* WP-66 «jour d'écoute». The planner dealt a listening day, so the
          learner is told the order before they start reading past it. The
          server withdraws the flag when the deployment cannot speak, so this
          never promises audio that will not arrive. */}
      {sceneOpensOnAudio(step.prompt) && (
        <p className="av2-label" data-state="listen-first-day">
          {wide.listen_first_day}
        </p>
      )}

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
          <SpokenLine speaker={speaker}>
            <p className="av2-fr av2-headline av2-headline--rule" lang="fr">
              {frenchSpacing(step.prompt.character_line_fr)}
            </p>
          </SpokenLine>
        </Surface>
      )}

      {/* WP-82 (appendix A): the objective is printed once, on the reply
          step where it is asked for — not here as «What you need to do: …». */}

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
  // WP-76: the verdict the hashed key gave on the device, before the server's.
  const [local, setLocal] = useState<{
    stepId: string;
    verdict: LocalVerdict;
    correctOptionId: string | null;
  } | null>(null);
  const currentStep = useRef(step.id);
  currentStep.current = step.id;
  const graded = feedback.kind === 'graded';
  const localHere = local && local.stepId === step.id ? local : null;
  // A pick graded on the device is committed: it is the answer being sent.
  const locked = busy || graded || feedback.kind === 'submitting' || Boolean(localHere);

  useEffect(() => {
    // A new step is a new answer; the same step keeps what the learner picked,
    // and a cold start gets back whatever was typed before the interruption.
    setChoice(null);
    setTiles([]);
    setLocal(null);
    setText(draft?.get(draftKey) ?? '');
  }, [draft, draftKey, step.id]);

  // The server's verdict is final. When it disagrees with the device, the
  // colours simply follow it — no second sound, no second buzz (`lib/feel`).
  const serverVerdict = graded ? feedback.verdict : null;
  const shown = shownVerdict(localHere?.verdict ?? null, serverVerdict);
  const serverSaysRight = serverVerdict === 'correct' || serverVerdict === 'supported';

  const options = useMemo<ChoiceOption[]>(
    () =>
      step.prompt.options.map((option) => {
        let state: ChoiceOption['state'];
        if (shown && option.id === choice) state = shown;
        else if (
          shown === 'wrong' &&
          !serverSaysRight &&
          localHere?.correctOptionId === option.id
        ) {
          // The learner has committed; showing the right card is feedback.
          state = 'correct';
        }
        // WP-78: a meaning card is in the learner's language, not French.
        return { id: option.id, textFr: option.text_fr, state, lang: optionLang(option) ?? null };
      }),
    [step.prompt.options, shown, choice, serverSaysRight, localHere?.correctOptionId],
  );

  // WP-66: six formats, three input surfaces. `recallAttempt` owns the mapping
  // in `journey-state.ts`, so "what the learner sees" and "what gets posted"
  // cannot drift apart — and a format this build has never heard of falls back
  // to a written answer rather than to a dead Check button.
  const attempt = recallAttempt(step.prompt, { choice, tiles, text });
  const ready = attempt !== null;
  const picks = recallIsPicked(step.prompt.task_type);
  const submit = () => {
    if (!attempt) return;
    const stepId = step.id;
    const prompt = step.prompt;
    if (promptHasAnswerKey(prompt) && (attempt.mode === 'choice' || attempt.mode === 'tiles')) {
      const answer =
        attempt.mode === 'choice' ? { optionId: attempt.option_id } : { tileIds: attempt.tile_ids };
      // One SHA-256 of a short string: well inside the 100 ms budget. The
      // attempt below is posted either way; this only colours the pick.
      void checkAnswerLocally(prompt, answer).then(async (verdict) => {
        if (!verdict || currentStep.current !== stepId) return;
        setLocal({ stepId, verdict, correctOptionId: null });
        markVerdictFelt(stepId, verdict);
        feel(verdict);
        if (verdict === 'wrong' && attempt.mode === 'choice') {
          const right = await correctOptionLocally(prompt);
          if (right && currentStep.current === stepId) {
            setLocal((current) =>
              current && current.stepId === stepId ? { ...current, correctOptionId: right } : current,
            );
          }
        }
      });
    }
    onSubmit(attempt);
  };

  // WP-78. A matching grid posts itself when its last pair lands: the pairs
  // were graded one by one on the device already, so a Check would be a
  // second tap for nothing. A clean grid is coloured correct at once; one with
  // a slip waits for the server, which grades the target's first pairing.
  const isMatch = step.prompt.task_type === 'match_pairs';
  const completeMatch = React.useCallback(
    (pairs: string[], clean: boolean) => {
      const stepId = step.id;
      setTiles(pairs);
      if (clean) {
        setLocal({ stepId, verdict: 'correct', correctOptionId: null });
        markVerdictFelt(stepId, 'correct');
        feel('correct');
      }
      onSubmit({ mode: 'tiles', tile_ids: pairs });
    },
    [onSubmit, step.id],
  );
  // WP-78. Read-and-tap until a clip exists: the phrase is the headline. With
  // a clip, the phrase stays unprinted until the answer is graded.
  const heard = listenTapHasAudio(step.prompt);
  const headline =
    heard && !graded
      ? step.prompt.instruction_native
      : step.prompt.prompt_fr || step.prompt.instruction_native;

  return (
    <StepFrame
      label={copy.today_eyebrow}
      headline={headline}
      headlineLang={headline === step.prompt.prompt_fr && step.prompt.prompt_fr ? 'fr' : undefined}
    >
      {step.prompt.prompt_fr && headline !== step.prompt.instruction_native && (
        <p className="av2-body av2-body--lg">{step.prompt.instruction_native}</p>
      )}
      {!step.prompt.prompt_fr && isMatch && (
        <p className="av2-body av2-body--lg">{step.prompt.instruction_native}</p>
      )}
      {heard && step.prompt.audio_url && (
        <audio className="av2-listen" controls preload="auto" src={step.prompt.audio_url} />
      )}

      {/* A transform prints the sentence being rewritten, so the learner knows
          the headline above is the source and not their answer. */}
      {step.prompt.task_type === 'transform' && step.prompt.prompt_fr && (
        <p className="av2-label" data-state="transform-source">
          {wide.transform_source_label}
        </p>
      )}

      {isMatch && (
        <MatchPairs
          key={step.id}
          prompt={step.prompt}
          disabled={locked}
          onComplete={completeMatch}
        />
      )}

      {/* WP-86: «Qui a dit ça ?» — the line is the headline, the faces the cards. */}
      {step.prompt.task_type === 'who_said' && (
        <WhoSaid
          options={step.prompt.options}
          states={options}
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

      {(step.prompt.task_type === 'choice' ||
        step.prompt.task_type === 'classify' ||
        step.prompt.task_type === 'listen_tap') && (
        <ChoiceList
          options={options}
          selectedId={choice}
          label={
            step.prompt.task_type === 'classify'
              ? wide.classify_label
              : step.prompt.instruction_native
          }
          disabled={locked}
          onSelect={setChoice}
          statusLabels={{
            selected: wide.status_selected,
            correct: wide.status_correct,
            wrong: wide.status_wrong,
          }}
        />
      )}

      {/* A word bank is tiles whose chip row is *not* the answer in the wrong
          order. Saying so is the difference between a puzzle and a count. */}
      {wordBankHasSpareChips(step.prompt) && (
        <p className="av2-label" data-state="word-bank-spare">
          {wide.word_bank_spare_chips}
        </p>
      )}

      {/* One bank for both formats (WP-76: a second copy used to render for
          plain tiles). */}
      {(step.prompt.task_type === 'tiles' ||
        step.prompt.task_type === 'word_bank' ||
        step.prompt.task_type === 'unscramble') && (
        <WordTiles
          options={options}
          placed={tiles}
          label={step.prompt.instruction_native}
          emptyHint={wide.tiles_empty}
          removeLabel={wide.remove_last}
          disabled={locked}
          onPlace={(id) => setTiles((current) => [...current, id])}
          onRemoveLast={() => setTiles((current) => current.slice(0, -1))}
          verdict={tiles.length ? shown : null}
          verdictLabel={shown === 'correct' ? wide.status_correct : wide.status_wrong}
        />
      )}

      {/* Anything that is not picked is written: short answer, transform, and
          whatever a newer server deals that this build has not met yet. */}
      {!picks &&
        (graded ? (
          <SentAnswer label={copy.answer_label} text={text} />
        ) : (
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
        ))}

      {/* The verdict carries the step's only remaining action once it is
          graded; checking again and asking for a hint are both spent. */}
      {!graded && (
        <>
          {!isMatch && (
            <Action
              tone="primary"
              disabled={locked || !ready}
              pending={feedback.kind === 'submitting'}
              pendingLabel={copy.sending}
              onClick={submit}
            >
              {copy.check}
            </Action>
          )}

          <HelpRow
            available={step.prompt.help_available}
            used={step.assistance_used.filter((level) => level !== 'none')}
            copy={copy}
            busy={busy}
            help={help}
            onHelp={onHelp}
          />
        </>
      )}
    </StepFrame>
  );
}

// ---------------------------------------------------------------------------
// Respond
// ---------------------------------------------------------------------------

/** Which chrome language a journey copy table is (no hook: the step views
 *  also render outside a React tree in tests). French when it is none of them. */
function copyLanguage(copy: JourneyCopy): 'en' | 'de' | 'fr' {
  return (['en', 'de', 'fr'] as const).find((language) => journeyCopy(language) === copy) ?? 'fr';
}

export function RespondStepView({
  step,
  copy,
  busy,
  feedback,
  help,
  onHelp,
  onSubmit,
  draft,
}: { step: RespondStep } & StepViewCommonProps) {
  // A respond step can hold more than one turn, and each turn is its own
  // answer, so the turn is part of the key: a new turn starts clean rather
  // than reopening with the sentence the learner already sent.
  const draftKey = `${step.id}:${step.prompt.turn_index}`;
  const [text, setText] = useState(() => draft?.get(draftKey) ?? '');
  const canSpeak = voiceOffered(step.prompt);
  const canType = textOffered(step.prompt);
  // WP-27: speaking is the default output. The first render agrees with the
  // server (voice whenever the step offers it) and the remembered preference
  // is applied in an effect, so a learner who chose "Écrire" keeps it without
  // a hydration mismatch.
  const [mode, setMode] = useState<AnswerMode>(canSpeak ? 'voice' : 'text');
  const [explainRefusal, setExplainRefusal] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const voice = useVoiceAnswer();
  const voiceState = voice.state;
  // A graded turn is closed until the learner continues: re-submitting into a
  // completed step would only earn a 409 `step_not_active`. WP-76: a turn whose
  // reply is still typing in (`replying`) is already graded.
  const graded = feedback.kind === 'graded' || feedback.kind === 'replying';
  const busyVoice = voiceIsBusy(voiceState);
  const locked = busy || feedback.kind === 'submitting' || graded || busyVoice;
  // WP-76: the one who answers — typing while the answer is read, then speaking.
  const replier = respondSpeaker(step.prompt);
  const waitingForReply = feedback.kind === 'submitting' || feedback.kind === 'retrying';
  const reply =
    graded && feedback.result.character_reply_fr ? feedback.result.character_reply_fr : null;

  useEffect(() => {
    // A new turn starts empty but keeps the same mounted field, so focus and
    // the software keyboard survive the round trip. A resumed turn comes back
    // with exactly what the learner had typed.
    setText(draft?.get(draftKey) ?? '');
  }, [draft, draftKey]);

  useEffect(() => {
    if (!canSpeak) {
      setMode('text');
      return;
    }
    if (!canType) {
      setMode('voice');
      return;
    }
    setMode(readAnswerMode('voice'));
  }, [canSpeak, canType]);

  const chooseMode = (next: AnswerMode) => {
    setMode(next);
    writeAnswerMode(next);
    if (next === 'text') voice.reset();
  };

  useEffect(() => {
    // A device that refuses the microphone is a fact about the device, not a
    // thing to ask about every turn: the learner is put on the text path, told
    // once why, and the preference remembers it.
    if (voiceState.kind !== 'failed') return;
    if (voiceState.reason !== 'permission' && voiceState.reason !== 'unsupported') return;
    setMode('text');
    writeAnswerMode('text');
    if (!micRefusalExplained()) {
      setExplainRefusal(true);
      rememberMicRefusalExplained();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceState.kind, (voiceState as { reason?: string }).reason]);

  const setAnswer = (next: string) => {
    setText(next);
    draft?.set(draftKey, next);
  };

  useEffect(() => {
    // The transcript is a draft, never a submission: it lands in the field so
    // the learner can fix a misheard word before anything is graded.
    if (voiceState.kind === 'transcript') setAnswer(voiceState.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceState.kind, voiceState.kind === 'transcript' ? voiceState.text : null]);

  const failureNotice =
    voiceState.kind === 'failed'
      ? (copy as Record<string, string>)[FAILURE_COPY_KEY[voiceState.reason]] || copy.voice_failed
      : null;

  const submit = () => onSubmit({ mode: submittedMode(voiceState, text), text });

  const sendAction = (
    <Action
      tone="primary"
      disabled={locked || answerIsBlank(text)}
      pending={feedback.kind === 'submitting'}
      pendingLabel={copy.sending}
      onClick={submit}
    >
      {copy.send}
    </Action>
  );

  // WP-66 «jour de lettre»: the turn is a reply to a Courrier letter rather
  // than to a spoken line. Absent on every other shape, so the ordinary
  // respond step is untouched — and `letterOf` refuses half a letter, so a
  // letter block can never replace the character's line with a blank one.
  const letter = letterOf(step.prompt);
  // A letter's subject is its French headline; the server's fallback
  // («Une lettre du Courrier.») is chrome and is said in the chrome language —
  // the language of the copy table this step was handed.
  const letterHeadline = letter
    ? crLetterHeadline({ summary_fr: letter.subject_fr }, copyLanguage(copy))
    : null;
  const wide = widenCopy(copy);
  // WP-D2: the character's line is said beside their face, which reacts to
  // the verdict. A letter day keeps its subject headline and byline.
  const saying = !letter && replier ? replier : null;
  const sayingMood: PortraitMood =
    feedback.kind === 'graded' ? expressionForVerdict(feedback.verdict) : 'neutral';
  // Beside a face, the reply is said in the bubble (typing in), never a second
  // time in a row below it; without a face it keeps its own row.
  const spoken = useTypedText(saying && reply ? reply : '', feedback.kind === 'replying');

  return (
    <StepFrame
      label={
        saying ? saying.name : <Byline name={letter?.correspondent_name || step.prompt.character_name} />
      }
      headline={letterHeadline ? letterHeadline.text : spoken || step.prompt.character_line_fr}
      headlineLang={letterHeadline ? letterHeadline.lang : 'fr'}
      speaker={saying}
      speakerMood={sayingMood}
    >
      {letter && (
        <Surface shape="episode">
          <p className="av2-label">
            {wide.letter_from.replace('{name}', letter.correspondent_name)}
          </p>
          <p className="av2-fr av2-body av2-body--lg" lang="fr">
            {frenchSpacing(letter.body_fr)}
          </p>
        </Surface>
      )}

      <p className="av2-body av2-body--lg">
        {letter ? letter.objective_native : step.prompt.objective_native}
      </p>

      {step.prompt.targets.length > 0 && (
        <div className="av2-help__actions">
          {step.prompt.targets.map((target) => (
            <Chip key={`${target.kind}:${target.id}`} icon={<ShapeToken kind="reward" size="sm" />}>
              <span lang="fr">{target.label_fr}</span>
            </Chip>
          ))}
        </div>
      )}

      {/* Until the turn is graded, when the field, the send button, the
          microphone and the help row all stop offering themselves and the
          verdict's Continue is the only action left (WP-20 D-6). */}
      {graded ? (
        <SentAnswer label={copy.answer_label} text={text} />
      ) : mode === 'voice' && canSpeak ? (
        <>
          {voiceState.kind === 'transcript' ? (
            <>
              {textAnswerField({
                label: copy.voice_transcript_label,
                value: text,
                rows: 3,
                disabled: locked,
                placeholder: copy.answer_placeholder,
                invalid: feedback.kind === 'empty',
                inputRef,
                onChange: setAnswer,
              })}
              <p className="av2-body">{copy.voice_transcript_hint}</p>
              <div className="av2-respond__actions">
                {sendAction}
                <Action tone="quiet" disabled={locked} onClick={() => void voice.start()}>
                  {copy.voice_retry}
                </Action>
              </div>
            </>
          ) : (
            <>
              {/* WP-82 (appendix A): no «say it out loud…» line — the mic says it. */}
              <div className="av2-respond__actions">
                <Action
                  tone="primary"
                  disabled={busy || feedback.kind === 'submitting'}
                  pending={voiceState.kind === 'transcribing'}
                  pendingLabel={copy.transcribing}
                  icon={voiceState.kind === 'recording' ? <StopIcon size={18} /> : <MicIcon size={18} />}
                  onClick={() => (voiceState.kind === 'recording' ? voice.stop() : void voice.start())}
                >
                  {voiceState.kind === 'recording' ? copy.stop_recording : copy.speak}
                </Action>
                {canType && (
                  <Action tone="quiet" disabled={busyVoice} onClick={() => chooseMode('text')}>
                    {copy.use_text}
                  </Action>
                )}
              </div>
            </>
          )}
        </>
      ) : (
        <>
          {textAnswerField({
            label: copy.answer_label,
            value: text,
            rows: 3,
            disabled: locked,
            placeholder: copy.answer_placeholder,
            invalid: feedback.kind === 'empty',
            inputRef,
            onChange: setAnswer,
          })}

          <div className="av2-respond__actions">
            {sendAction}
            {canSpeak && (
              <Action tone="quiet" disabled={locked} onClick={() => chooseMode('voice')}>
                {copy.use_voice}
              </Action>
            )}
          </div>
        </>
      )}

      {/* WP-76: the wait has a face, and the reply is read before it is judged. */}
      {waitingForReply && <CharacterTyping speaker={replier} />}
      {reply && !saying && (
        <TypedReply speaker={replier} reply={reply} animate={feedback.kind === 'replying'} />
      )}

      {!graded && voiceState.kind === 'recording' && (
        <Notice shape="action">
          <p>{copy.record}</p>
        </Notice>
      )}

      {!graded && voiceState.kind === 'transcribing' && (
        <Notice shape="story">
          <p>{copy.transcribing}</p>
        </Notice>
      )}

      {!graded && failureNotice && (
        <Notice shape="action">
          <p>{failureNotice}</p>
        </Notice>
      )}

      {!graded && explainRefusal && (
        <Notice shape="story">
          <p>{copy.voice_permission}</p>
        </Notice>
      )}

      {!graded && (
        <HelpRow
          available={step.prompt.help_available}
          used={step.assistance_used.filter((level) => level !== 'none')}
          copy={copy}
          busy={busy}
          help={help}
          onHelp={onHelp}
        />
      )}
    </StepFrame>
  );
}

// ---------------------------------------------------------------------------
// Resolution
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Rule — WP-L4 «Règle»
// ---------------------------------------------------------------------------

/**
 * The day's new grammar unit, as its WP-L10 rule card in the `intro` variant:
 * the French example is the screen's one Garamond line, the rule is one
 * sentence in the learner's language, and «Essayer» is the one primary — it
 * advances to the unit's guided items. The step is read, never answered.
 *
 * `language` is the chrome language (the learner's up to A2, French from B1),
 * which is also the language the card's rule is picked in.
 */
export function RuleStepView({
  step,
  copy,
  busy,
  language,
  onContinue,
}: { step: RuleStep; language: ControlLanguage } & Pick<
  StepViewCommonProps,
  'copy' | 'busy' | 'onContinue'
>) {
  const card = step.prompt.rule_card;
  const proceed = () => {
    if (!busy) onContinue();
  };
  if (!usableCard(card)) {
    // A card the client cannot draw still lets the learner through.
    return (
      <StepFrame
        label={copy.today_eyebrow}
        headline={step.prompt.title_fr || step.prompt.title_native}
        headlineLang={step.prompt.title_fr ? 'fr' : undefined}
      >
        <p className="av2-body av2-body--lg">{step.prompt.title_native}</p>
        <Action tone="primary" pending={busy} pendingLabel={copy.sending} onClick={proceed}>
          {copy.scene_continue}
        </Action>
      </StepFrame>
    );
  }
  return (
    <section className="av2-stack av2-step" data-step="rule">
      <RuleCard
        card={card}
        language={language}
        variant="intro"
        conceptId={step.prompt.concept_id}
        onDone={proceed}
      />
    </section>
  );
}

export function ResolutionStepView({
  step,
  copy,
  busy,
  onContinue,
}: { step: ResolutionStep } & Pick<StepViewCommonProps, 'copy' | 'busy' | 'onContinue'>) {
  const wide = widenCopy(copy);
  const register = registerNoteOf(step.prompt);
  const chapterRecap = chapterRecapOf(step.prompt);
  if (resolutionAwaitsStory(step)) {
    // WP-87: the story lane is still writing the ending; the hook polls meanwhile.
    return (
      <StepFrame label={copy.today_eyebrow} headline={null}>
        <StoryWriting speaker={null} />
        <Action tone="primary" disabled onClick={onContinue}>
          {copy.continue}
        </Action>
      </StepFrame>
    );
  }
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

      {/* WP-66 «jour de reprise»: the chapter that just closed. French, because
          it is story, and absent rather than empty when there is none. */}
      {chapterRecap && (
        <Surface shape="episode">
          <p className="av2-label">{wide.chapter_recap_label}</p>
          <p className="av2-fr av2-body" lang="fr">
            {frenchSpacing(chapterRecap)}
          </p>
        </Surface>
      )}

      {/* WP-33 / WP-66: the register the learner has been graded on since
          WP-33 and shown since never. One French line, and why it matters in
          their own language. Nothing at all when it was not evaluated — which
          is neither a pass nor a failure, and so is not a line. */}
      {register && (
        <Notice shape="story">
          <p className="av2-label" data-state="register">
            {wide.register_label}
          </p>
          <p className="av2-fr av2-body" lang="fr">
            {frenchSpacing(register.lineFr)}
          </p>
          {register.reasonNative && (
            <p className="av2-body">{register.reasonNative}</p>
          )}
        </Notice>
      )}

      <Action tone="primary" pending={busy} pendingLabel={copy.sending} onClick={onContinue}>
        {copy.continue}
      </Action>
    </StepFrame>
  );
}

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------

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
  speaker = null,
}: {
  feedback: JourneyFeedback;
  copy: JourneyCopy;
  onContinue: () => void;
  onRetry: () => void;
  onDismiss: () => void;
  /** WP-77: whose face reacts to the verdict. */
  speaker?: JourneySpeaker | null;
}) {
  const wide = widenCopy(copy);
  // WP-76: the verdict is a sheet pinned to the bottom of the screen. When it
  // lands it is brought into view and focused, so a screen reader starts on it
  // rather than on whatever the learner last touched.
  const gradedRef = useRef<HTMLDivElement | null>(null);
  const gradedResult = feedback.kind === 'graded' ? feedback.result : null;
  useEffect(() => {
    const node = gradedRef.current;
    if (!gradedResult || !node) return;
    const still =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    try {
      node.scrollIntoView?.({ block: 'nearest', behavior: still ? 'auto' : 'smooth' });
      node.focus({ preventScroll: true });
    } catch {
      /* an old engine without the options bag still shows the band */
    }
  }, [gradedResult]);

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
      // WP-82 (text diet): the reply's provenance is no longer printed under
      // the verdict — «Written reply from the script» told the learner nothing
      // they could act on. The payload still carries `reply_source`.
      const { result, verdict } = feedback;
      const title =
        verdict === 'correct' ? copy.correct : verdict === 'supported' ? copy.supported : copy.wrong;
      // WP-77: the character reacts to *your* answer — pleased or cross, small.
      const face =
        speaker && castIdFor(speaker.id, speaker.name) ? (
          <CastPortrait
            characterId={speaker.id || ''}
            name={speaker.name}
            mood={expressionForVerdict(verdict)}
            size="sm"
          />
        ) : undefined;

      return (
        <div className="av2-graded" data-state={verdict} ref={gradedRef} tabIndex={-1}>
          <FeedbackBand
            tone={verdict}
            title={title}
            // The reply is the character's own speech now (RespondStepView types
            // it in, WP-76); the verdict card no longer repeats it.
            face={face}
          >
            {result.correction && (
              <Correction
                label={copy.correction}
                spanFr={result.correction.span_fr}
                correctedFr={result.correction.corrected_fr}
                noteNative={result.correction.note_native}
              />
            )}
          </FeedbackBand>
          {/* WP-D2: «Marin vous sourit ↑» — the relationship moved, said once. */}
          {verdict === 'correct' && speaker && <CharacterSmiles speaker={speaker} />}

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
