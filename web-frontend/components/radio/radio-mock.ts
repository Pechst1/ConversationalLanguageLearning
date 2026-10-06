/**
 * WP-122 A · La Radio — DEV ONLY mock (`/radio?mock=1`), loaded on demand by the page
 * so it never reaches a production bundle's main chunk.
 *
 * The bulletin is the server's own script for the grève evergreen at A2, week 40
 * (`radio.bulletin_script`), and every clip is a tiny **silent** WAV data URI made
 * here (8 kHz, 8-bit mono), so the pane can play the whole listen → read → dictée →
 * «C'est entendu» path with no network and no audio file in the repo. The clips are
 * short (`MOCK_LINE_SECONDS`), not the estimate: the mock shows the flow, not the pace.
 */

import type { RadioClient } from '@/lib/radio-api';
import type { RadioBulletin, RadioDicteeResult, RadioWeek, RadioWeekResult } from '@/lib/radio-types';

export const MOCK_LINE_SECONDS = 1.2;
const RATE = 8000;

function base64(bytes: Uint8Array): string {
  if (typeof btoa === 'function') {
    let binary = '';
    for (let i = 0; i < bytes.length; i += 0x8000) {
      binary += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + 0x8000)));
    }
    return btoa(binary);
  }
  return Buffer.from(bytes).toString('base64');
}

/** A silent mono 8-bit PCM WAV of `seconds`, as a `data:audio/wav;base64,…` URI. */
export function silentWavDataUri(seconds: number): string {
  const samples = Math.max(1, Math.round(RATE * seconds));
  const bytes = new Uint8Array(44 + samples);
  const view = new DataView(bytes.buffer);
  const ascii = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) bytes[offset + i] = value.charCodeAt(i);
  };
  ascii(0, 'RIFF');
  view.setUint32(4, 36 + samples, true);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, RATE, true);
  view.setUint32(28, RATE, true); // byte rate
  view.setUint16(32, 1, true); // block align
  view.setUint16(34, 8, true); // bits per sample
  ascii(36, 'data');
  view.setUint32(40, samples, true);
  bytes.fill(128, 44); // 8-bit silence is the midpoint
  return `data:audio/wav;base64,${base64(bytes)}`;
}

const DOSSIER = 'evergreen-greve-transports';

const LINES: Array<[string, string, RadioBulletin['lines'][number]['role'], string, string | null]> = [
  ['romy_tremblay', 'Romy Tremblay', 'lede', 'En France, les grèves dans les métros et les trains reviennent souvent. Elles suivent des règles : un préavis, une déclaration des grévistes, un plan de transport. On parle souvent de « service minimum », mais ce n’est pas une vraie obligation.', null],
  ['romy_tremblay', 'Romy Tremblay', 'claim', 'Dans les transports publics, un préavis de grève doit être déposé au moins cinq jours avant le début de la grève.', 'c1'],
  ['romy_tremblay', 'Romy Tremblay', 'claim', 'Chaque salarié qui veut faire grève doit le dire 48 heures avant, pour que le service soit réorganisé sur les lignes les plus importantes.', 'c2'],
  ['romy_tremblay', 'Romy Tremblay', 'claim', 'D’après les syndicats de salariés et les partis de gauche, le service minimum remet en cause le droit de grève.', 'c4'],
  ['marin_leveque', 'Marin Lévêque', 'guest', 'À l’association, on aide les gens que ça touche. C’est concret, tu vois.', null],
  ['romy_tremblay', 'Romy Tremblay', 'signoff', 'C’était Le Papier, semaine 40.', null],
];

export function mockBulletin(): RadioBulletin {
  const clip = silentWavDataUri(MOCK_LINE_SECONDS);
  return {
    dossierId: DOSSIER,
    titleFr: 'Un jour de grève dans les transports',
    topic: 'work',
    band: 'A2',
    week: '2026-W40',
    seconds: 55.1,
    audio: 'ready',
    guestId: 'marin_leveque',
    lines: LINES.map(([speaker, speakerName, role, textFr, claimId], index) => ({
      index,
      speaker,
      speakerName,
      role,
      textFr,
      clipUrl: clip,
      claimId,
    })),
    dictee: { lineIndex: 1, words: 21 },
    stage: { plateUrl: '/assets/serial/locations/le_mistral-counter.webp', placeFr: 'Un quai de métro un matin de grève' },
  };
}

const ITEM = { dossierId: DOSSIER, titleFr: 'Un jour de grève dans les transports', topic: 'work', evergreen: true };

/** The dictée's ladder, as the server's `dictation_form` folds it (close enough for a mock). */
function form(text: string, keepAccents: boolean): string {
  let value = text.toLowerCase().replace(/[’‘`´]/g, "'");
  if (!keepAccents) value = value.normalize('NFKD').replace(/[̀-ͯ]/g, '');
  return value.replace(/[^0-9a-zà-ÿœæ']+/g, ' ').replace(/\s*'\s*/g, "' ").trim();
}

export function createMockRadioClient(): RadioClient {
  let heard = false;
  const week = (): RadioWeek => ({
    week: '2026-W40',
    current: heard ? null : ITEM,
    queue: heard ? [] : [ITEM],
    heard: heard ? [DOSSIER] : [],
    heardToday: heard,
    chip: !heard,
    seconds: 55,
  });
  const wait = <T,>(value: T) => new Promise<T>((resolve) => setTimeout(() => resolve(value), 250));
  return {
    week: () => wait<RadioWeekResult>({ enabled: true, week: week() }),
    bulletin: () => wait(mockBulletin()),
    dictee: (_id, text) => {
      const expected = LINES[1][3];
      const outcome: RadioDicteeResult['outcome'] =
        form(text, true) === form(expected, true) ? 'met' : form(text, false) === form(expected, false) ? 'partially_met' : 'not_yet';
      return wait({ outcome, expectedFr: expected, note: null });
    },
    heard: () => {
      heard = true;
      return wait(week());
    },
  };
}
