/**
 * WP-90 «La planche» — the story reader's states, at phone size. DEVELOPMENT
 * ONLY: mounted from `pages/atelier-v2-gallery.tsx` (whose `getStaticProps`
 * returns `notFound` in a production build).
 *
 * The reader owns its whole screen (a pinned nav, a folding running head), so
 * each state is its own screen — `/atelier-v2-gallery?reader=plate` — and the
 * gallery lays them side by side in 375×812 frames, the phone the fit target
 * is measured on:
 *
 *   plate       a panel whose drawing is on the press: the blue-ink duotone
 *               plate and its folio ribbon
 *   arrive      the same panel; its drawing lands after two seconds and
 *               crossfades in (appears at once under Reduce Motion)
 *   drawn       the first panel, drawn, with the headline
 *   running     panel 3 of 4, three lines: the running head, compact captions,
 *               the pinned nav — the "fits without scrolling" specimen
 *   translated  «Translate the panel» open on a ≤A2 line
 *   finale      the ending as the last panel — the «case finale»
 *   finale-wait the ending still being written: the speaker's face, no primary
 *
 * `&lang=fr|en|de` switches the chrome; the story stays French.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { ResolutionStepView } from '@/components/atelier-v2/journey/JourneySteps';
import { StoryEpisodeReader } from '@/components/atelier-v2/journey/StoryEpisodeReader';
import { journeyCopy } from '@/components/atelier-v2/journey/journey-copy';
import { useLineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { atelierCopy } from '@/lib/atelier-v2-copy';
import type {
  ControlLanguage,
  JourneySnapshot,
  ResolutionStep,
  StoryEpisode,
  StoryPanel,
} from '@/types/daily-journey';

const ART = '/assets/serial/scenes/order_at_cafe';
const PLATE = '/assets/serial/locations/le_mistral-counter.webp';

type Line = StoryPanel['dialogue'][number] & { mood?: string; text_native?: string | null };
type Panel = Omit<StoryPanel, 'dialogue'> & { dialogue: Line[]; alt_native?: string };

/* The first day's café scene, as the engine sends it with WP-90's additions. */
const PANELS: Panel[] = [
  {
    id: 'g-p1',
    index: 0,
    narration_fr: 'Le Mistral, huit heures. Ça sent le pain chaud.',
    dialogue: [
      {
        character_id: 'margaux_barman',
        character_name: 'Margaux',
        text_fr: 'Bonjour ! Qu’est-ce que je vous sers ?',
        mood: 'happy',
        text_native: 'Hello! What can I get you?',
      },
    ],
    image_url: `${ART}/panel-1.webp`,
    image_status: 'panel_art',
    alt_native: 'Margaux smiles behind the counter of a small Paris café.',
  },
  {
    id: 'g-p2',
    index: 1,
    narration_fr: 'Vous regardez le tableau.',
    dialogue: [
      { character_id: 'toi', character_name: 'Vous', text_fr: 'Un café, s’il vous plaît.', text_native: 'A coffee, please.' },
      {
        character_id: 'margaux_barman',
        character_name: 'Margaux',
        text_fr: 'Un petit noir ? Bien sûr.',
        mood: 'neutral',
        text_native: 'An espresso? Of course.',
      },
    ],
    image_url: `${ART}/panel-2.webp`,
    image_status: 'panel_art',
    alt_native: 'The chalkboard menu above the coffee machine.',
  },
  {
    id: 'g-p3',
    index: 2,
    narration_fr: 'Un homme entre, pressé.',
    dialogue: [
      { character_id: 'marin_leveque', character_name: 'Marin', text_fr: 'Pardon, madame !', mood: 'cross', text_native: 'Sorry, madam!' },
      { character_id: 'margaux_barman', character_name: 'Margaux', text_fr: 'Ce n’est rien.', mood: 'neutral', text_native: 'It’s nothing.' },
      { character_id: 'toi', character_name: 'Vous', text_fr: 'Il est pressé !', text_native: 'He is in a hurry!' },
    ],
    image_url: `${ART}/panel-3.webp`,
    image_status: 'panel_art',
    alt_native: 'A man in a coat squeezes past the counter.',
  },
  {
    id: 'g-p4',
    index: 3,
    narration_fr: 'Margaux pose la tasse devant vous.',
    dialogue: [
      { character_id: 'margaux_barman', character_name: 'Margaux', text_fr: 'Et voilà. Bonne journée !', mood: 'moved', text_native: 'There you go. Have a good day!' },
    ],
    image_url: `${ART}/panel-4.webp`,
    image_status: 'panel_art',
    alt_native: 'A cup of coffee on the zinc counter.',
  },
];

function episodeAt(panelIndex: number, rendering: number | null = null): StoryEpisode {
  return {
    id: 'gallery-episode',
    scene_id: 'gallery-episode',
    serial_thread_id: '',
    serial_episode_id: null,
    journey_id: 'gallery-journey',
    title_fr: 'Le Mistral',
    status: 'available',
    chapter: { id: 'c1', title_fr: 'Chapitre 1 · Premier café' },
    panel_index: panelIndex,
    panels: PANELS.map((panel) =>
      panel.index === rendering
        ? { ...panel, image_url: PLATE, image_status: 'rendering' as const }
        : panel,
    ) as unknown as StoryPanel[],
    resolution: null,
  };
}

const RESOLUTION: ResolutionStep = {
  id: 'g-res',
  kind: 'resolution',
  ordinal: 6,
  status: 'active',
  estimated_seconds: 30,
  assistance_used: [],
  prompt: {
    outcome_key: 'served',
    character_line_fr: 'Votre café, et un croissant offert. À demain !',
    summary_native: 'You ordered politely, and Margaux remembered you.',
    image_url: `${ART}/panel-4.webp`,
    register_note_fr: '« vous » tenu avec Margaux.',
    register_reason_native: 'You kept vous with someone you had just met.',
  },
};

const JOURNEY = {
  id: 'gallery-journey',
  scenario: { title_fr: 'Le Mistral' },
  steps: [{ id: 'g-scene', kind: 'scene', prompt: { panels: PANELS } }, RESOLUTION],
} as unknown as Pick<JourneySnapshot, 'id' | 'steps' | 'scenario'>;

const MARGAUX = { id: 'margaux_barman', name: 'Margaux' };

export const READER_GALLERY_STATES = ['plate', 'arrive', 'drawn', 'running', 'translated', 'finale', 'finale-wait'] as const;
export type ReaderGalleryState = (typeof READER_GALLERY_STATES)[number];

function Specimen({ state, language }: { state: ReaderGalleryState; language: ControlLanguage }) {
  const voice = useLineVoice();
  const [arrived, setArrived] = useState(false);
  useEffect(() => {
    if (state !== 'arrive') return undefined;
    const timer = window.setTimeout(() => setArrived(true), 2000);
    return () => window.clearTimeout(timer);
  }, [state]);
  // «Translate the panel» is the learner's tap; the specimen taps it for them.
  useEffect(() => {
    if (state !== 'translated') return undefined;
    const timer = window.setTimeout(() => {
      document.querySelector<HTMLButtonElement>('.fr-bar .fr-chip')?.click();
    }, 50);
    return () => window.clearTimeout(timer);
  }, [state]);

  const episode = useMemo(() => {
    switch (state) {
      case 'plate':
        return episodeAt(2, 2);
      case 'arrive':
        return episodeAt(2, arrived ? null : 2);
      case 'drawn':
        return episodeAt(0);
      case 'translated':
        return episodeAt(1);
      default:
        return episodeAt(2);
    }
  }, [state, arrived]);

  const copy = { ...atelierCopy(language), ...journeyCopy(language) };

  if (state === 'finale' || state === 'finale-wait') {
    const step: ResolutionStep =
      state === 'finale-wait'
        ? {
            ...RESOLUTION,
            prompt: { ...RESOLUTION.prompt, character_line_fr: '', summary_native: '', story_pending: true },
          }
        : RESOLUTION;
    return (
      <ResolutionStepView
        step={step}
        copy={copy}
        busy={false}
        onContinue={() => {}}
        speaker={MARGAUX}
        journey={JOURNEY}
        onExit={() => {}}
      />
    );
  }

  return (
    <StoryEpisodeReader
      episode={episode}
      mode="continue"
      onExit={() => {}}
      onContinue={() => {}}
      continueLabel={copy.scene_continue}
      language={language}
      savePosition={false}
      footLink={null}
      lineVoice={voice}
    />
  );
}

/** One reader state, full-screen, inside the journey shell (`?reader=running`). */
export function ReaderGalleryScreen({
  state,
  language,
}: {
  state: ReaderGalleryState;
  language: ControlLanguage;
}) {
  return (
    <AtelierV2Root as="main" language={language} className="journey-shell">
      {/* The journey's session hides the app's own header and tab bar
          (pages/atelier.tsx, `Masthead view="session"`); so does the specimen. */}
      <style>{'.app-masthead, .phone-product-nav { display: none !important; }'}</style>
      <div className="av2-screen">
        <div className="av2-screen__body">
          <Specimen state={state} language={language} />
        </div>
      </div>
    </AtelierV2Root>
  );
}

/** The index: every state in a 375×812 frame, side by side. */
export function ReaderGalleryFrames({ language }: { language: ControlLanguage }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>
      {READER_GALLERY_STATES.map((name) => (
        <figure key={name} style={{ margin: 0 }}>
          <figcaption className="av2-label">{name}</figcaption>
          <iframe
            title={`reader-${name}`}
            src={`/atelier-v2-gallery?reader=${name}&lang=${language}`}
            width={375}
            height={812}
            loading="lazy"
            style={{ border: '1px solid var(--av2-line)', borderRadius: 12, background: 'var(--av2-paper)' }}
          />
        </figure>
      ))}
    </div>
  );
}

export function isReaderGalleryState(value: unknown): value is ReaderGalleryState {
  return typeof value === 'string' && (READER_GALLERY_STATES as readonly string[]).includes(value);
}
