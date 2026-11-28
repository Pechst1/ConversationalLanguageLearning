/**
 * «Le bilan» — fixtures for the dev gallery (`/atelier-v2-gallery?bilan=full|thin|empty`)
 * and the node tests. Wire shape, snake_case, exactly as `GET /bilan` answers; the
 * sentences are written as corrected lines are filed (never a raw learner line).
 */

import type { BilanLanguage } from '@/lib/bilan-types';

const DAYS = ['2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22'];

const RULES: Record<BilanLanguage, { title: string; met: string; practising: string; held: string }> = {
  en: { title: 'The passé composé with avoir', met: 'practising', practising: 'practising', held: 'held' },
  de: { title: 'Das passé composé mit avoir', met: 'in Übung', practising: 'in Übung', held: 'gefestigt' },
  fr: { title: 'Le passé composé avec avoir', met: 'en route', practising: 'en route', held: 'tenue' },
};

const GLOSS: Record<BilanLanguage, string[]> = {
  en: ['key', 'stairs', 'to borrow', 'the market', 'a neighbour'],
  de: ['der Schlüssel', 'die Treppe', 'leihen', 'der Markt', 'die Nachbarin'],
  fr: ['la clé', 'l’escalier', 'emprunter', 'le marché', 'la voisine'],
};

export function bilanFixture(kind: 'full' | 'thin' | 'empty', language: BilanLanguage) {
  const played = kind === 'full' ? [0, 1, 3, 5] : kind === 'thin' ? [2] : [];
  const rules = RULES[language];
  const gloss = GLOSS[language];
  const full = kind === 'full';
  return {
    week_start: DAYS[0],
    week_end: DAYS[6],
    timezone: 'Europe/Paris',
    is_current: false,
    closed: true,
    language,
    level: 'A2',
    days: DAYS.map((date, index) => ({ date, played: played.includes(index), future: false })),
    days_played: played.length,
    lines:
      kind === 'empty'
        ? []
        : full
          ? [
              { text_fr: 'Je voudrais un café et un croissant.', date: DAYS[0], source: 'scene' },
              { text_fr: 'Hier, j’ai pris l’escalier avec Margaux.', date: DAYS[1], source: 'forge_attempt' },
              { text_fr: 'Tu peux me prêter ta clé ce soir ?', date: DAYS[3], source: 'scene' },
              { text_fr: 'Nous sommes allés au marché samedi matin.', date: DAYS[5], source: 'journal_entry' },
            ]
          : [{ text_fr: 'Je voudrais un café et un croissant.', date: DAYS[2], source: 'scene' }],
    words: {
      new_count: full ? 14 : kind === 'thin' ? 3 : 0,
      reviewed_count: full ? 31 : kind === 'thin' ? 4 : 0,
      held_count: full ? 26 : kind === 'thin' ? 4 : 0,
      shown:
        kind === 'empty'
          ? []
          : (full
              ? ['la clé', 'l’escalier', 'emprunter', 'le marché', 'la voisine']
              : ['la clé', 'l’escalier', 'emprunter']
            ).map((word, index) => ({ word, gloss: gloss[index] })),
    },
    rules: full
      ? [
          { concept_id: 1, title: rules.title, title_fr: 'Le passé composé avec avoir', from_stage: 'new',
            from_label: null, stage: 'practising', stage_label: rules.met },
          { concept_id: 2, title: language === 'en' ? 'Partitive articles' : language === 'de' ? 'Teilungsartikel' : 'Les articles partitifs',
            title_fr: 'Les articles partitifs', from_stage: 'practising', from_label: rules.practising, stage: 'held',
            stage_label: rules.held },
        ]
      : [],
    story: {
      episodes:
        kind === 'empty'
          ? []
          : full
            ? [
                { date: DAYS[0], title_fr: 'Le mauvais accueil' },
                { date: DAYS[1], title_fr: 'La clé de Lila' },
                { date: DAYS[3], title_fr: 'Un dimanche au marché' },
              ]
            : [{ date: DAYS[2], title_fr: 'La clé de Lila' }],
      decisions: full
        ? [
            { date: DAYS[1], label_fr: 'Je la prends.', kind: 'choice' },
            { date: DAYS[3], label_fr: 'Tu ne sais pas encore quelle porte la clé ouvre.', kind: 'resolved' },
          ]
        : [],
      next_fr: kind === 'empty' ? null : 'Qui a laissé la lettre sous la porte de Lila ?',
    },
    weeks: [
      { week_start: '2026-11-23', days_played: 0 },
      { week_start: DAYS[0], days_played: played.length },
    ],
    previous_week_start: full ? '2026-11-09' : null,
    next_week_start: '2026-11-23',
  };
}
