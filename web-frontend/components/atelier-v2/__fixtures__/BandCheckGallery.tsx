/**
 * SPEED-1 gallery specimens: «Vérification du lexique».
 *
 *   1. the two entry points (placement result, Le lexique)
 *   2. the intro, with the sub-bands left to check
 *   3. a question mid-run (the 7th of 24), then the send in flight and a failed send
 *   4. the result card: passed (words credited), passed with nothing new to
 *      card, and not passed with the next band offered anyway
 *
 * The items are shaped like `GET /vocabulary/band-check/A1.2` answers; the
 * glosses follow the gallery's language like the server's would.
 */

import React from 'react';

import { BandCheckEntryView } from '@/components/atelier-v2/band-check/BandCheckEntry';
import { BandCheckView, type BandCheckViewState } from '@/components/atelier-v2/band-check/BandCheck';
import { answer, startRun, summarize } from '@/components/atelier-v2/band-check/band-check-state';
import type { BandCheckItem, BandCheckSubBand } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

type SectionComponent = React.ComponentType<{ title: string; children: React.ReactNode }>;

const BANDS: BandCheckSubBand[] = [
  { sub_band: 'A1.1', words: 180, credited: true },
  { sub_band: 'A1.2', words: 210, credited: false },
  { sub_band: 'A2.1', words: 240, credited: false },
];

const GLOSSES: Record<'en' | 'de', Array<[string, string[]]>> = {
  en: [
    ['la fenêtre', ['the window', 'the door', 'the wall', 'the floor']],
    ['oublier', ['to forget', 'to borrow', 'to follow', 'to offer']],
    ['le voisin', ['the neighbour', 'the cousin', 'the waiter', 'the guest']],
    ['lent', ['slow', 'light', 'long', 'late']],
    ['l’épicerie', ['the grocer’s', 'the bakery', 'the pharmacy', 'the station']],
    ['rarement', ['rarely', 'quickly', 'early', 'together']],
    ['le quartier', ['the neighbourhood', 'the quarter hour', 'the square', 'the market']],
  ],
  de: [
    ['la fenêtre', ['das Fenster', 'die Tür', 'die Wand', 'der Boden']],
    ['oublier', ['vergessen', 'leihen', 'folgen', 'anbieten']],
    ['le voisin', ['der Nachbar', 'der Cousin', 'der Kellner', 'der Gast']],
    ['lent', ['langsam', 'leicht', 'lang', 'spät']],
    ['l’épicerie', ['der Lebensmittelladen', 'die Bäckerei', 'die Apotheke', 'der Bahnhof']],
    ['rarement', ['selten', 'schnell', 'früh', 'zusammen']],
    ['le quartier', ['das Viertel', 'die Viertelstunde', 'der Platz', 'der Markt']],
  ],
};

function items(language: ControlLanguage): BandCheckItem[] {
  const rows = GLOSSES[language === 'de' ? 'de' : 'en'];
  // 24 items, as the server deals them; the first seven are drawn above.
  return Array.from({ length: 24 }, (_, index) => {
    const [fr, options] = rows[index % rows.length];
    const shift = index % 4;
    return { id: `w${index}`, fr, options: [...options.slice(shift), ...options.slice(0, shift)] };
  });
}

const noop = () => {};

export function BandCheckGallerySections({
  language,
  Section,
}: {
  language: ControlLanguage;
  Section: SectionComponent;
}) {
  const run = startRun('A1.2', items(language), 0.9);
  let midRun = run;
  for (let step = 0; step < 6; step += 1) midRun = answer(midRun, step === 3 ? null : 0);
  let fullRun = midRun;
  while (fullRun.index < fullRun.items.length) fullRun = answer(fullRun, 0);

  const states: Array<[string, BandCheckViewState]> = [
    ['Intro', { phase: 'intro', run, bands: BANDS }],
    ['Question 7 / 24', { phase: 'question', run: midRun }],
    ['Sending', { phase: 'question', run: fullRun, sending: true }],
    ['Send failed', { phase: 'question', run: fullRun, failed: true }],
    [
      'Passed — 196 words credited',
      {
        phase: 'result',
        summary: summarize(
          { sub_band: 'A1.2', correct: 23, total: 24, passed: true, credited_words: 196, missed: ['w5'] },
          BANDS,
          0.9,
        ),
      },
    ],
    [
      'Passed — nothing new to card',
      {
        phase: 'result',
        summary: summarize(
          { sub_band: 'A1.2', correct: 24, total: 24, passed: true, credited_words: 0, missed: [] },
          BANDS,
          0.9,
        ),
      },
    ],
    [
      'Not passed — next band offered anyway',
      {
        phase: 'result',
        summary: summarize(
          {
            sub_band: 'A1.2',
            correct: 17,
            total: 24,
            passed: false,
            credited_words: 0,
            missed: ['w1', 'w2', 'w3', 'w4', 'w5', 'w6', 'w7'],
          },
          BANDS,
          0.9,
        ),
      },
    ],
  ];

  return (
    <>
      <Section title="Vérification du lexique — entry points">
        <BandCheckEntryView origin="placement" language={language} bands={BANDS} />
        <BandCheckEntryView origin="lexique" language={language} bands={BANDS} />
      </Section>
      {states.map(([title, state]) => (
        <Section key={title} title={`Vérification du lexique — ${title}`}>
          <BandCheckView
            state={state}
            language={language}
            origin="placement"
            keyboard={false}
            onBegin={noop}
            onChoose={noop}
            onUndo={noop}
            onResend={noop}
            onRetryOpen={noop}
            onCheckBand={noop}
            onLeave={noop}
          />
        </Section>
      ))}
    </>
  );
}
