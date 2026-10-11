/**
 * WP-96 / WP-97 gallery specimens (dev only, `/atelier-v2-gallery`):
 *
 *   · «Archives du journal» — a running season with one chapter open and one
 *     closed on its digest line, and a finished season bound as «Tome 1»;
 *   · one planche reread without its page: «la réplique de l'abonné·e», the
 *     ending, a margin note;
 *   · «Le trombinoscope» — trust that has fallen, a «tu» with its date, a
 *     character the learner has not met yet;
 *   · «Précédemment» before a scene; a margin note; the colophon and the tome.
 *
 * Fixed sample data; nothing here is a learner's.
 */

import React, { useState } from 'react';

import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader';
import type { SerialCastMember } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { normalizeArchive } from '../archive-model';
import { ChapterColophon, MarginNotes, Precedemment, TomeSeal } from '../ArchiveMarks';
import { ArchiveStyles } from '../ArchiveStyles';
import { ArchiveDayPage, ArchiveNav, ArchiveVolume } from '../FeuilletonArchive';
import { Trombinoscope } from '../Trombinoscope';

const NOTE = {
  text_fr: 'Parce que vous avez dit à Marin « vas-y »',
  cause_scene_id: 'g-s2',
  cause_date: '2026-09-13',
  character_id: 'marin',
  cause_edition_no: 2,
};

const day = (date: string, n: number, title: string, extra: Record<string, unknown> = {}) => ({
  date,
  journey_id: `g-j${n}`,
  scene_id: `g-s${n}`,
  title_fr: title,
  edition_no: n,
  image_url: '/assets/serial/locations/le_mistral-counter.webp',
  learner_lines: [],
  ending_fr: null,
  margin_notes: [],
  can_do_id: null,
  special: null,
  ...extra,
});

const ARCHIVE = normalizeArchive({
  seasons: [
    { number: 1, title_fr: 'S’installer', finished: true, loaded: false, day_count: 21, chapters: [] },
    {
      number: 2,
      title_fr: 'Les voisins',
      finished: false,
      loaded: true,
      chapters: [
        {
          index: 1,
          title_fr: 'La clé perdue',
          digest_fr: 'Qui a pris la clé de Lila ? → Marin, qui voulait la lui rendre.',
          closed: true,
          days: [
            day('2026-09-12', 1, 'Une clé sous le paillasson'),
            day('2026-09-13', 2, 'Marin se décide', { learner_lines: ['Vas-y, Marin !'] }),
          ],
        },
        {
          index: 2,
          title_fr: 'Le plombier',
          closed: false,
          days: [
            day('2026-09-14', 3, 'Soirée au Mistral', { special: 'epreuve' }),
            day('2026-09-15', 4, 'Une fuite chez Romy', {
              learner_lines: ['Je peux vous aider ?', 'J’ai un numéro de plombier.'],
              ending_fr: 'Romy note le numéro et vous remercie deux fois.',
              margin_notes: [NOTE],
            }),
          ],
        },
      ],
    },
  ],
  current: { season: 2, chapter: 2 },
});

const CAST = [
  {
    id: 'marin',
    name: 'Marin',
    role: 'le voisin du dessous',
    trust: 2,
    register: 'vous',
    known_about_you: [
      { text_fr: 'Vous lui avez dit « vas-y » devant Lila.', date: '2026-09-13', scene_id: 'g-s2' },
      { text_fr: 'Vous n’avez pas répondu à sa lettre.', date: '2026-09-18', scene_id: null },
    ],
    relationship: { register: 'vous', mood: -1 },
  },
  {
    id: 'romy',
    name: 'Romy',
    role: 'la colocataire',
    trust: 4,
    register: 'tu',
    tu_since: { date: '2026-09-12', scene_id: 'g-s1' },
    known_about_you: [{ text_fr: 'Vous avez un numéro de plombier.', date: '2026-09-15', scene_id: 'g-s4' }],
    relationship: { register: 'tu', mood: 2 },
  },
  { id: 'lila', name: 'Lila', role: 'la voisine du troisième', relationship: { register: 'vous' } },
] as unknown as SerialCastMember[];

export function ArchiveGallerySections({
  language,
  Section,
}: {
  language: ControlLanguage;
  Section: React.ComponentType<{ title: string; children: React.ReactNode }>;
}) {
  const [open, setOpen] = useState<string[]>(['s2c2']);
  const [tomes, setTomes] = useState<number[]>([]);
  const toggle = (key: string) => setOpen((current) => (current.includes(key) ? current.filter((k) => k !== key) : [...current, key]));
  const planche = ARCHIVE.seasons[0].chapters[0].days[1];
  return (
    <>
      <Section title="WP-96 · Archives du journal — chapters, colophon, tome">
        <AtelierV2Root language={language} className="fr-page">
          <FeuilletonReaderStyles />
          <ArchiveStyles />
          <ArchiveNav view="archive" language={language} />
          <ArchiveVolume
            archive={ARCHIVE}
            language={language}
            openKeys={open}
            onToggleChapter={toggle}
            openTomes={tomes}
            onToggleTome={(n) => setTomes((current) => (current.includes(n) ? current.filter((x) => x !== n) : [...current, n]))}
          />
        </AtelierV2Root>
      </Section>
      <Section title="WP-96 · A planche reread — la réplique de l’abonné·e">
        <AtelierV2Root language={language} className="fr-page">
          <ArchiveStyles />
          <ArchiveDayPage day={planche} archive={ARCHIVE} language={language} episode={null} />
        </AtelierV2Root>
      </Section>
      <Section title="WP-97 · Le trombinoscope — trust that fell, a «tu», a stranger">
        <AtelierV2Root language={language} className="fr-page">
          <ArchiveStyles />
          <ArchiveNav view="cast" language={language} />
          <Trombinoscope cast={CAST} language={language} withAvatar={false} />
        </AtelierV2Root>
      </Section>
      <Section title="WP-96 · «Précédemment» — before a new scene">
        <AtelierV2Root language={language}>
          <ArchiveStyles />
          <Precedemment
            lines={[
              'Marin a rendu la clé à Lila.',
              'Romy cherche un plombier depuis lundi.',
              'Au Mistral, Margaux vous a gardé une table.',
            ]}
            language={language}
            onRead={() => {}}
          />
        </AtelierV2Root>
      </Section>
      <Section title="WP-97 · Margin note, colophon, tome">
        <AtelierV2Root language={language}>
          <ArchiveStyles />
          <MarginNotes notes={[NOTE]} language={language} />
          <ChapterColophon digest="Qui a pris la clé de Lila ? → Marin, qui voulait la lui rendre." />
          <div className="fa-tome">
            <TomeSeal number={1} title="S’installer" language={language} stamp />
          </div>
        </AtelierV2Root>
      </Section>
    </>
  );
}

export default ArchiveGallerySections;
