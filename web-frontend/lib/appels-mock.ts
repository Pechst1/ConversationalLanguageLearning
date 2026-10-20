/**
 * Les appels — an in-memory client for `/appel?mock=1` (dev only, never in a
 * production build): Romy rings, three lines, then goodbye. Mirrors the server's
 * shapes (`app/services/appels.py` `public_view`).
 */

import type { AppelsClient, Call } from './appels-api';

const REPLIES = [
  'Ah, super ! Dis, tu as vu Gus aujourd’hui ? Il était bizarre au Mistral.',
  'Hmm. Je crois qu’il cache quelque chose. Tu peux lui parler demain ?',
  'Merci, t’es génial. Bon, je te laisse. Bonne soirée !',
];

export function createMockAppelsClient({ start = 'ringing', latency = 400 }: { start?: string; latency?: number } = {}): AppelsClient {
  let call: Call = {
    id: 'mock-call',
    status: start === 'missed' ? 'missed' : 'ringing',
    caller: { id: 'romy_tremblay', name: 'Romy', face: 'romy_tremblay' },
    turns: [],
    voicemail:
      start === 'missed'
        ? { text_fr: 'Allô, c’est Romy. Je voulais te parler de Gus. Rappelle-moi quand tu peux !', clip_id: null }
        : null,
    turns_left: 3,
    reason_en: start === 'missed' ? 'Romy wanted to talk about Gus.' : null,
  };
  const wait = <T,>(value: T) => new Promise<T>((done) => setTimeout(() => done(value), latency));
  const update = (next: Partial<Call>) => {
    call = { ...call, ...next };
    return wait(call);
  };
  return {
    today: () => wait(call),
    answer: () =>
      update({
        status: 'live',
        turns: [{ who: 'caller', text_fr: 'Allô ? C’est Romy. Tu as une minute ? Ta journée s’est bien passée ?', clip_id: null }],
      }),
    decline: () =>
      update({
        status: 'missed',
        voicemail: { text_fr: 'Allô, c’est Romy. Rappelle-moi quand tu peux !', clip_id: null },
        reason_en: 'Romy wanted to talk about Gus.',
      }),
    say: (_id, text, mode) => {
      const used = call.turns.filter((turn) => turn.who === 'learner').length + 1;
      const left = Math.max(0, 3 - used);
      return update({
        turns: [
          ...call.turns,
          { who: 'learner', text_fr: text, mode },
          { who: 'caller', text_fr: REPLIES[Math.min(used, REPLIES.length) - 1], clip_id: null },
        ],
        turns_left: left,
        status: left === 0 ? 'ended' : 'live',
        reason_en: left === 0 ? 'Romy wanted to know whether Gus said anything to you.' : null,
      });
    },
    hangUp: () => update({ status: 'ended', reason_en: 'Romy wanted to know whether Gus said anything to you.' }),
  };
}
