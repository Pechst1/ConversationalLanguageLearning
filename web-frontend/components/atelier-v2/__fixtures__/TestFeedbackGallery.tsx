/**
 * WP-103 «Retour d'essai» gallery specimens: every state the owner's first test
 * asked for, in one place, so it can be reviewed at 320/390/440 and in the
 * three chrome languages without driving a real day.
 *
 *   T3  a drill's goal line and its header
 *   T2  «Afficher le texte» at every stage of the listening cycle
 *   T6  the corrected form under the learner's line, and the closing verdict
 *   T7  «À vous — répondez à Marin · échange 2 sur 3»
 *   T9  «Je relis…» while the model reads
 *   T8  «Corrigez la phrase» after «À corriger»
 *
 * Every value is a fixture shaped like the server's contract; none is a
 * learner's data.
 */

import React, { useReducer, useState } from 'react';

import { atelierCopy } from '@/lib/atelier-v2-copy';
import { classifyRepair } from '@/lib/forge-followup';
import {
  EpisodeRadioView,
} from '@/components/atelier-v2/journey/StoryEpisodeReader';
import { JourneyFeedbackView, RecallStepView, RespondStepView } from '@/components/atelier-v2/journey/JourneySteps';
import { stepHeaderLine } from '@/components/atelier-v2/journey/drill-frame';
import { journeyCopy } from '@/components/atelier-v2/journey/journey-copy';
import {
  RADIO_INITIAL,
  RADIO_TEXT_INITIAL,
  radioTextReduce,
  verifyEpisodeGuess,
  type RadioStage,
} from '@/components/atelier-v2/journey/story-episode-model';
import type { UseEpisodeAudio } from '@/components/atelier-v2/journey/useEpisodeAudio';
import { EpShell } from '@/components/epreuve/Epreuve';
import {
  FOLLOW_UP_EMPTY,
  ForgeCorrectedLine,
  ForgeFollowUp,
  ForgeGoalLine,
  ForgeReading,
  type FollowUpDraft,
} from '@/components/epreuve/ForgeFollowUp';
import { drillGoalLine } from '@/components/atelier-v2/journey/drill-frame';
import type {
  AttemptResult,
  ControlLanguage,
  RecallStep,
  RespondPrompt,
  RespondStep,
  StoryEpisode,
} from '@/types/daily-journey';

type SectionComponent = React.ComponentType<{ title: string; children: React.ReactNode }>;

const noop = () => {};

// ---------------------------------------------------------------------------
// T3 — the goal line and the header
// ---------------------------------------------------------------------------

function recallStep(extra: Partial<RecallStep['prompt']>): RecallStep {
  return {
    id: 'gallery-recall',
    ordinal: 2,
    kind: 'recall',
    status: 'active',
    estimated_seconds: 40,
    assistance_used: [],
    prompt: {
      task_type: 'word_bank',
      instruction_native: 'Build the sentence. Some chips are not needed.',
      prompt_fr: null,
      options: [
        { id: 'a', text_fr: 'Une' },
        { id: 'b', text_fr: 'petite' },
        { id: 'c', text_fr: 'table' },
        { id: 'd', text_fr: 'blanche' },
        { id: 'e', text_fr: 'est' },
        { id: 'f', text_fr: 'grand' },
      ],
      target: { kind: 'grammar', id: 'g-12', label_fr: 'Genre et nombre', label_native: 'Gender and number' },
      optional: false,
      help_available: [],
      ...extra,
    },
  };
}

// ---------------------------------------------------------------------------
// T6 / T7 — the conversation
// ---------------------------------------------------------------------------

function respondPrompt(extra: Partial<RespondPrompt>): RespondPrompt {
  return {
    turn_index: 1,
    max_turns: 3,
    repair_allowed: true,
    character_id: 'marin_leveque',
    character_name: 'Marin',
    character_line_fr: 'Bien sûr. Vous prenez un café ?',
    character_line_audio_url: null,
    objective_native: 'Ask Romy if she wants to sit with you.',
    input_modes: ['text'],
    targets: [],
    help_available: [],
    ...extra,
  };
}

function respondStep(id: string, extra: Partial<RespondPrompt>): RespondStep {
  return {
    id,
    ordinal: 3,
    kind: 'respond',
    status: 'active',
    estimated_seconds: 120,
    assistance_used: [],
    prompt: respondPrompt(extra),
  };
}

const SLIP = {
  span_fr: 'ton place',
  corrected_fr: 'ta place',
  note_native: '«Place» is feminine, so it takes «ta».',
};

const TURN_SLIP = respondStep('gallery-103-slip', {
  thread: [{ learner_fr: 'Je peux prendre ton place ?', character_fr: 'Bien sûr. Vous prenez un café ?', correction: SLIP }],
});

const TURN_LAST = respondStep('gallery-103-last', {
  turn_index: 2,
  character_line_fr: 'Et avec ça ?',
  thread: [
    { learner_fr: 'Je peux prendre ton place ?', character_fr: 'Bien sûr. Vous prenez un café ?', correction: SLIP },
    { learner_fr: 'Oui, un café, merci.', character_fr: 'Et avec ça ?', correction: null },
  ],
});

const TURN_CLOSED = respondStep('gallery-103-closed', {
  turn_index: 2,
  thread: [
    { learner_fr: 'Je peux prendre ton place ?', character_fr: 'Bien sûr. Vous prenez un café ?', correction: SLIP },
    { learner_fr: 'Oui, un café, merci.', character_fr: 'Et avec ça ?', correction: null },
  ],
});

const CLOSING_RESULT = {
  contract_version: 1,
  evidence_ref: 'gallery',
  task_outcome: 'partially_met',
  assistance_level: 'none',
  correction: {
    span_fr: 'un poster grand',
    corrected_fr: 'un grand poster',
    note_native: 'Adjective position.',
    notes_native: ['Some short adjectives go before the noun.', '«Poster» is masculine, so «grand» takes no -e.'],
  },
  character_reply_fr: 'Avec plaisir. Installez-vous.',
  reply_source: 'model',
  next_turn: null,
  pending: false,
  journey: null,
} as unknown as AttemptResult;

const CLOSING_FEEDBACK = {
  kind: 'graded' as const,
  verdict: 'supported' as const,
  result: CLOSING_RESULT,
  replySource: 'model' as const,
};

// ---------------------------------------------------------------------------
// T2 — the listening cycle
// ---------------------------------------------------------------------------

const EPISODE: StoryEpisode = {
  id: 'gallery-103-episode',
  scene_id: 'gallery-103-episode',
  serial_thread_id: 't',
  serial_episode_id: null,
  journey_id: 'j',
  title_fr: 'Une place au comptoir',
  status: 'available',
  chapter: { id: 'c1', title_fr: 'Chapitre 1' },
  panel_index: 0,
  panels: [
    {
      id: 'p1',
      index: 0,
      narration_fr: 'Le Mistral est presque vide.',
      dialogue: [
        { character_id: 'romy_tremblay', character_name: 'Romy', text_fr: 'Tu veux t’asseoir avec moi ?' },
        { character_id: 'marin_leveque', character_name: 'Marin', text_fr: 'Avec plaisir, merci.' },
      ],
      image_url: null,
      image_status: 'unavailable',
    },
  ],
  resolution: null,
};

const AUDIO: UseEpisodeAudio = {
  state: { kind: 'ready', clips: [] },
  clips: [],
  prepare: noop,
  play: noop,
  playFrom: noop,
  stop: noop,
  busy: false,
  heard: false,
};

function RadioSpecimen({ stage, copy, startShown = false }: { stage: RadioStage; copy: ReturnType<typeof journeyCopy>; startShown?: boolean }) {
  const [text, dispatchText] = useReducer(
    radioTextReduce,
    startShown ? radioTextReduce(RADIO_TEXT_INITIAL, { type: 'all' }) : RADIO_TEXT_INITIAL,
  );
  const state = { ...RADIO_INITIAL, stage, guess: 'accord' as const, heard: true };
  return (
    <EpisodeRadioView
      episode={EPISODE}
      copy={copy}
      audio={AUDIO}
      state={state}
      text={text}
      verification={verifyEpisodeGuess(EPISODE, state.guess)}
      onContinue={noop}
      onReadInstead={noop}
      dispatch={noop}
      dispatchText={dispatchText}
    />
  );
}

// ---------------------------------------------------------------------------
// T8 — the follow-up
// ---------------------------------------------------------------------------

const WRONG_ITEM = {
  id: 'c1',
  prompt: 'Lila cherche un poster grand (Lila is looking for a big poster)',
  labels: ['Correct', 'À corriger'],
  correct_label: 'À corriger',
  classify_kind: 'judgement',
};
const CORRECTED = 'Lila cherche un grand poster.';
const FOLLOW_UP = { kind: 'correct_it', source_fr: 'Lila cherche un poster grand.', goal_native: 'Correct the sentence.' };
const FIELD = classifyRepair(WRONG_ITEM, { corrected_fr: CORRECTED, follow_up: FOLLOW_UP }).followUp;
const TILES = classifyRepair(WRONG_ITEM, {
  corrected_fr: CORRECTED,
  follow_up: { ...FOLLOW_UP, options: ['Lila', 'cherche', 'un', 'grand', 'poster', 'petit'] },
}).followUp;

function FollowUpSpecimen({ spec, start }: { spec: NonNullable<typeof FIELD>; start?: Partial<FollowUpDraft> }) {
  const [draft, setDraft] = useState<FollowUpDraft>({ ...FOLLOW_UP_EMPTY, ...start });
  return <ForgeFollowUp followUp={spec} draft={draft} onDraft={setDraft} />;
}

// ---------------------------------------------------------------------------
// The sections
// ---------------------------------------------------------------------------

export function TestFeedbackGallerySections({
  language,
  Section,
}: {
  language: ControlLanguage;
  Section: SectionComponent;
}) {
  const copy = { ...atelierCopy(language), ...journeyCopy(language) };
  const journey = journeyCopy(language);
  const goal = 'Build: "A small white table is in the kitchen."';
  const props = <S extends RecallStep | RespondStep>(
    step: S,
    feedback: React.ComponentProps<typeof RespondStepView>['feedback'] = { kind: 'idle' },
  ) => ({
    step,
    copy,
    busy: false,
    feedback,
    help: null,
    onHelp: noop,
    onSubmit: noop,
    onContinue: noop,
  });
  const header = (step: RecallStep | RespondStep) =>
    stepHeaderLine({
      step,
      language,
      copy: journey,
      location: 'Le Mistral',
      objective: 'Ask Romy if she wants to sit with you.',
    });

  return (
    <>
      <Section title="WP-103 T3 — a drill says what it asks for">
        <p className="av2-label">The header of a drill names the drill; the reply keeps the day’s objective</p>
        <p className="av2-label">{header(recallStep({}))}</p>
        <p className="av2-label">{header(TURN_SLIP)}</p>
        <p className="av2-label">With its goal — «Build the sentence» is no longer a riddle</p>
        <RecallStepView {...props(recallStep({ goal_native: goal }))} />
        <p className="av2-label">Without a goal — the scene line it is cut from</p>
        <RecallStepView {...props(recallStep({ source_fr: 'Une petite table blanche est dans la cuisine.' }))} />
        <p className="av2-label">La Forge — the same goal line under an item</p>
        <EpShell as="div" language={language}>
          <div className="ep-exercise">
            <ForgeGoalLine goal={drillGoalLine({ goal_native: goal, instruction_native: '', prompt_fr: '' })} />
          </div>
        </EpShell>
      </Section>

      <Section title="WP-103 T2 — «Afficher le texte» at every stage">
        <p className="av2-label">Prédire — the page toggle is there, even before a guess</p>
        <RadioSpecimen stage="predire" copy={journey} />
        <p className="av2-label">Écouter — hidden by default, a toggle per line</p>
        <RadioSpecimen stage="ecouter" copy={journey} />
        <p className="av2-label">Écouter — the page’s text shown</p>
        <RadioSpecimen stage="ecouter" copy={journey} startShown />
        <p className="av2-label">Vérifier — the question again, with its answer</p>
        <RadioSpecimen stage="verifier" copy={journey} />
        <p className="av2-label">Retenir — the toggle is still there</p>
        <RadioSpecimen stage="retenir" copy={journey} startShown />
      </Section>

      <Section title="WP-103 T6 / T7 — the conversation says what was corrected and what comes next">
        <p className="av2-label">Exchange 2 of 3 — the corrected form is printed; tap it for the note; the cue under the line</p>
        <RespondStepView {...props(TURN_SLIP)} />
        <p className="av2-label">The last exchange</p>
        <RespondStepView {...props(TURN_LAST)} />
        <p className="av2-label">The close — «Continue» is the only action; the verdict lists the turn’s corrections</p>
        <RespondStepView {...props(TURN_CLOSED, CLOSING_FEEDBACK)} />
        <JourneyFeedbackView
          feedback={CLOSING_FEEDBACK}
          copy={copy}
          onContinue={noop}
          onRetry={noop}
          onDismiss={noop}
          speaker={{ id: 'marin_leveque', name: 'Marin' }}
        />
      </Section>

      <Section title="WP-103 T9 — «Je relis…» while the model reads">
        <EpShell as="div" language={language}>
          <ForgeReading coach={{ id: 'romy_tremblay', name: 'Romy' }} onSkip={noop} patienceMs={1000 * 60 * 60} />
        </EpShell>
      </Section>

      <Section title="WP-103 T8 — «Corrigez la phrase» after «À corriger»">
        <p className="av2-label">A field — nothing shown before a try or a skip</p>
        <EpShell as="div" language={language}>
          {FIELD && <FollowUpSpecimen spec={FIELD} />}
        </EpShell>
        <p className="av2-label">Tiles at A1</p>
        <EpShell as="div" language={language}>
          {TILES && <FollowUpSpecimen spec={TILES} start={{ placed: [0, 1] }} />}
        </EpShell>
        <p className="av2-label">«Passer» — the right sentence is shown</p>
        <EpShell as="div" language={language}>
          {FIELD && <FollowUpSpecimen spec={FIELD} start={{ outcome: 'revealed', skipped: true }} />}
        </EpShell>
        <p className="av2-label">A right try</p>
        <EpShell as="div" language={language}>
          {FIELD && <FollowUpSpecimen spec={FIELD} start={{ text: 'Lila cherche un grand poster', outcome: 'right' }} />}
        </EpShell>
        <p className="av2-label">No follow-up from the server — «La bonne phrase»</p>
        <EpShell as="div" language={language}>
          <ForgeCorrectedLine fr={CORRECTED} />
        </EpShell>
      </Section>
    </>
  );
}
