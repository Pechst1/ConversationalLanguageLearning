/**
 * WP-98 / WP-99 gallery specimens: «Pendant votre absence», the season's
 * front page (the day's first screen and Home's card), and Home between two
 * seasons. Every value is a fixture shaped like the server's contract.
 */

import React from 'react';

import { HomeScreen } from '@/components/atelier-v2/home/HomeScreen';
import { JourneyTodayCard } from '@/components/atelier-v2/journey/JourneyTodayCard';
import { EntreTemps, SeasonPremiere } from '@/components/atelier-v2/journey/SeasonPages';
import { dayMarkState } from '@/components/atelier-v2/journey/day-mark';
import { journeyProgress, phaseFromEnvelope } from '@/components/atelier-v2/journey/journey-state';
import { absenceOf, seasonPremiereOf } from '@/components/atelier-v2/journey/season-return-model';
import type { DailyJourneyController } from '@/components/atelier-v2/journey/useDailyJourney';
import { AtelierV2Root } from '@/components/atelier-v2/ui';
import type { ControlLanguage, TodayEnvelope } from '@/types/daily-journey';

const POSTER = '/assets/serial/locations/le_mistral-counter.webp';

const SCENARIO = {
  scenario_key: 'gallery_premiere',
  content_version: '1',
  title_fr: 'Une lettre sans timbre',
  objective_key: 'premiere',
  objective_native: 'Ask Romy who left the letter.',
  level_band: 'A1' as const,
  character_id: 'romy_tremblay',
  character_name: 'Romy',
  location_id: 'le_mistral',
  location_name: 'Le Mistral',
  image_url: POSTER,
  serial_thread_id: null,
  serial_episode_id: null,
  estimated_seconds: 480,
};

const ABSENCE = absenceOf({
  absence: {
    days: 6,
    greeting_fr: 'Te voilà enfin ! Six jours, tu sais, c’est long au Mistral.',
    character_id: 'romy_tremblay',
    character_name: 'Romy',
    entre_temps: [
      { text_fr: 'Marin a repeint la porte de l’immeuble en bleu.', date: '2026-09-23', character_id: 'marin_leveque' },
      { text_fr: 'Lila a trouvé un chat dans l’escalier.', date: '2026-09-24', character_id: 'lila_bonnet' },
      { text_fr: 'Margaux a changé le menu du midi.', date: '2026-09-25', character_id: 'margaux_barman' },
      { text_fr: 'Gus cherche encore sa clé.', date: '2026-09-26', character_id: 'augustin_de_roncourt' },
      { text_fr: 'Romy a gardé votre place au comptoir.', date: '2026-09-27', character_id: 'romy_tremblay' },
    ],
    lapsed_letters: [{ mission_id: 'g-m7', correspondent_name: 'Lila' }],
  },
})!;

const PREMIERE = seasonPremiereOf({
  season_premiere: {
    number: 2,
    title_fr: 'Les voisins',
    logline_fr: 'Une lettre arrive sans timbre, et tout l’immeuble veut savoir qui l’a écrite.',
  },
})!;

function controllerFor(language: ControlLanguage, extra: Record<string, unknown>, available: unknown): DailyJourneyController {
  const envelope = {
    contract_version: 1,
    enabled: true,
    control_language: language,
    local_date: '2026-09-29',
    timezone: 'Europe/Paris',
    journey: null,
    available,
    legacy_resume: null,
    practice_href: '/atelier?mode=practice',
    because: null,
    is_warm: false,
    forge: { href: '/atelier?mode=forge', concept_id: 12, budget_seconds: 300, folded: false },
    ...extra,
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

export function SeasonReturnGallerySections({
  language,
  Section,
}: {
  language: ControlLanguage;
  Section: React.ComponentType<{ title: string; children: React.ReactNode }>;
}) {
  return (
    <>
      <Section title="WP-99 · «Pendant votre absence» — Entre-temps">
        <AtelierV2Root language={language}>
          <EntreTemps absence={ABSENCE} language={language} onContinue={() => {}} />
        </AtelierV2Root>
      </Section>
      <Section title="WP-98 · «Nouvelle saison» — the day’s first screen">
        <AtelierV2Root language={language}>
          <SeasonPremiere premiere={PREMIERE} posterUrl={POSTER} language={language} onContinue={() => {}} />
        </AtelierV2Root>
      </Section>
      <Section title="WP-98 · Home — a season premiere">
        <HomeScreen
          dateLabel="mardi 29 septembre"
          editionLabel="Édition Nº 22 · A1.2"
          streak={9}
          language={language}
          day={dayMarkState(null, language)}
          hero={
            <JourneyTodayCard
              controller={controllerFor(
                language,
                { season_premiere: { number: 2, title_fr: PREMIERE.titleFr, logline_fr: PREMIERE.loglineFr } },
                SCENARIO,
              )}
              onOpen={() => {}}
            />
          }
          episode={null}
          action={null}
          tiles={[]}
          colophon={null}
        />
      </Section>
      <Section title="WP-98 · Home — between two seasons">
        <HomeScreen
          dateLabel="mardi 29 septembre"
          editionLabel="Édition Nº 22 · A1.2"
          streak={9}
          language={language}
          day={dayMarkState(null, language)}
          planHidden
          hero={
            <JourneyTodayCard
              controller={controllerFor(
                language,
                {
                  interlude: {
                    returns_on: '2026-10-05',
                    reason_fr: 'Le Mistral ferme une semaine : Margaux part voir sa sœur à Lyon.',
                  },
                },
                null,
              )}
              onOpen={() => {}}
            />
          }
          episode={null}
          action={null}
          tiles={[]}
          colophon={null}
        />
      </Section>
    </>
  );
}

export default SeasonReturnGallerySections;
