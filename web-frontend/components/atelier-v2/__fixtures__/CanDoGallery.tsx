/**
 * WP-94 / WP-95 gallery specimens (dev only, `/atelier-v2-gallery`):
 *
 *   · Home on a «Numéro spécial» day — the double-ruled masthead, the card's
 *     kicker and the can-dos, and the next-step line;
 *   · the recap on `epreuve_result: passed` (the oversized seal, the whole
 *     cast) and on `failed` (the kind line and the next date);
 *   · the Carnet with mixed stamps, and a locked future band.
 *
 * Fixed sample data; nothing here is a learner's. The can-do titles are the
 * shape `GET /can-dos` sends.
 */

import React, { useState } from 'react';

import { HomeScreen } from '@/components/atelier-v2/home/HomeScreen';
import { JourneyRecap } from '@/components/atelier-v2/journey/JourneyRecap';
import { JourneyTodayCard } from '@/components/atelier-v2/journey/JourneyTodayCard';
import { dayMarkState } from '@/components/atelier-v2/journey/day-mark';
import { journeyProgress, phaseFromEnvelope } from '@/components/atelier-v2/journey/journey-state';
import type { DailyJourneyController } from '@/components/atelier-v2/journey/useDailyJourney';
import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { CarnetView } from '@/components/cahiers/CarnetTab';
import { carnetModel, nextStepView, readCanDos } from '@/lib/can-dos';
import type { ControlLanguage, JourneyRecap as Recap, JourneySnapshot, TodayEnvelope } from '@/types/daily-journey';

const CAN_DOS = [
  { id: 'a11_order_cafe', title_fr: 'commander au café', title_native: 'order at a café' },
  { id: 'a11_price_pay', title_fr: 'demander un prix et payer', title_native: 'ask a price and pay' },
  { id: 'a11_introduce', title_fr: 'se présenter', title_native: 'introduce yourself' },
];

const SCENARIO = {
  scenario_key: 'gallery_epreuve',
  content_version: '1',
  title_fr: 'La soirée du Mistral',
  objective_key: 'epreuve',
  objective_native: 'Show what you can do at the Mistral’s evening.',
  level_band: 'A1' as const,
  character_id: 'margaux_barman',
  character_name: 'Margaux',
  location_id: 'le_mistral',
  location_name: 'Le Mistral',
  image_url: null,
  serial_thread_id: null,
  serial_episode_id: null,
  estimated_seconds: 540,
  special: 'epreuve',
  epreuve: { band: 'A1.1', can_dos: CAN_DOS },
};

function offerController(language: ControlLanguage): DailyJourneyController {
  const envelope = {
    contract_version: 1,
    enabled: true,
    control_language: language,
    local_date: '2026-09-28',
    timezone: 'Europe/Paris',
    journey: null,
    available: SCENARIO,
    legacy_resume: null,
    practice_href: '/atelier?mode=practice',
    because: null,
    is_warm: false,
  } as unknown as TodayEnvelope;
  return {
    phase: phaseFromEnvelope(envelope),
    feedback: { kind: 'idle' },
    envelope,
    journey: null,
    step: null,
    respondPrompt: null,
    controlLanguage: language,
    legacyResume: null,
    progress: journeyProgress(null),
    busy: false,
    waiting: false,
    warm: false,
    help: null,
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  } as unknown as DailyJourneyController;
}

const JOURNEY = {
  id: 'gallery-epreuve',
  contract_version: 1,
  revision: 9,
  status: 'completed',
  local_date: '2026-09-28',
  timezone: 'Europe/Paris',
  budget_seconds: 600,
  estimated_active_seconds: 540,
  current_step_id: null,
  scenario: SCENARIO,
  steps: [],
  recap: null,
  retry: null,
  edition_no: 12,
  streak: { days: 12, today_done: true, freeze_available: false, freeze_used_on: null },
  special: 'epreuve',
  epreuve: { band: 'A1.1', can_dos: CAN_DOS },
} as unknown as JourneySnapshot;

function recapFor(result: 'passed' | 'failed'): Recap {
  return {
    completion_kind: 'complete',
    objective_outcome: result === 'passed' ? 'met' : 'partially_met',
    practiced_targets: [],
    capability_evidence: [],
    next_focus: null,
    collectible_ids: [],
    story_outcome: null,
    active_seconds: 560,
    steps_done: 5,
    level: result === 'passed' ? 'A1.2' : 'A1.1',
    level_up:
      result === 'passed'
        ? { from_level: 'A1.1', to_level: 'A1.2', mastered_vocabulary: 212, mastered_grammar: 14 }
        : null,
    epreuve_result: result,
    epreuve_line_fr:
      result === 'passed'
        ? 'Toute la troupe lève son verre : vous avez tenu la soirée en français.'
        : 'On remet ça bientôt — la soirée vous attend.',
  };
}

const CARNET = readCanDos({
  current_band: 'A1.1',
  bands: [
    {
      band: 'A1.1',
      title_native: 'A1.1',
      can_dos: [
        {
          ...CAN_DOS[0],
          stamped_at: '2026-09-22T09:14:00+02:00',
          source: 'scene',
          scene_id: 's1',
          scene_title_fr: 'Vous avez commandé au comptoir',
          character_id: 'margaux_barman',
          quote_fr: 'Un café noir, s’il vous plaît.',
        },
        { ...CAN_DOS[1], stamped_at: null, source: null },
        {
          ...CAN_DOS[2],
          stamped_at: '2026-09-20',
          source: 'authored',
          scene_title_fr: 'Premier jour au Mistral',
          character_id: 'marin_leveque',
          quote_fr: 'Je m’appelle Vincent.',
        },
      ],
    },
    {
      band: 'A1.2',
      title_native: 'A1.2',
      can_dos: [{ id: 'a12_directions', title_fr: 'demander son chemin', title_native: 'ask the way' }],
    },
  ],
});

export function CanDoGallerySections({
  language,
  Section,
}: {
  language: ControlLanguage;
  Section: React.ComponentType<{ title: string; children: React.ReactNode }>;
}) {
  const [band, setBand] = useState<string | null>(null);
  const next = nextStepView({ band: 'A1.1', next: { ...CAN_DOS[1], band: 'A1.1' } }, language);
  return (
    <>
      <Section title="WP-94 · Home — «Numéro spécial»">
        <HomeScreen
          dateLabel="dimanche 28 septembre"
          editionLabel="Édition Nº 12 · A1.1"
          streak={12}
          language={language}
          nextStep={next}
          special
          day={dayMarkState(null, language)}
          hero={<JourneyTodayCard controller={offerController(language)} onOpen={() => {}} />}
          episode={null}
          action={null}
          tiles={[]}
          colophon={null}
        />
      </Section>
      <Section title="WP-94 · Recap — épreuve passed">
        <AtelierV2Root language={language}>
          <JourneyRecap journey={JOURNEY} recap={recapFor('passed')} language={language} onExit={() => {}} />
        </AtelierV2Root>
      </Section>
      <Section title="WP-94 · Recap — épreuve failed">
        <AtelierV2Root language={language}>
          <JourneyRecap journey={JOURNEY} recap={recapFor('failed')} language={language} onExit={() => {}} />
        </AtelierV2Root>
      </Section>
      <Section title="WP-95 · Le Carnet — mixed stamps (tap A1.2: locked)">
        <AtelierV2Root language={language}>
          <CarnetView model={carnetModel(CARNET, band, language)} language={language} onSelectBand={setBand} />
        </AtelierV2Root>
      </Section>
    </>
  );
}

export default CanDoGallerySections;
