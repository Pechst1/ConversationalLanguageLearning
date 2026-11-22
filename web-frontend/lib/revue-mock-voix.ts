/**
 * DEV ONLY · «Papier · la voix» in the scripted mock (`/revue?mock=1&voix=1`): wraps the mock
 * transport and answers the voice's routes the server's way; everything else passes through.
 *
 *  * the manifest from the mock session's own text (the lead, the takes, the reply and the last
 *    word once said; the dictée: the lead's shortest whole sentence of 4–14 words);
 *  * a line answers a clip id, and the clip is SILENCE as long as the line would take to say
 *    (no network, no voice: the screens behave as with a real clip — the words come after it);
 *    `audio: false` (`&voixaudio=0`) answers `disabled`, as a deployment without speech; `fail`
 *    (`&voixfail=1`) fails every clip, as a provider that is down;
 *  * the dictée: the grader's three verdicts and word marks, the sentence only after two tries.
 */

import type { VoixTransport } from './revue-voix';

type Json = Record<string, any>;

const SENTENCE = /[^.!?…]+[.!?…]*/g;
const LETTERS = "A-Za-z0-9À-ÖØ-öø-ÿŒœ";
const WORD = new RegExp(`[${LETTERS}'’-]+`, 'g');
const words = (text: string) => (text.match(new RegExp(`[${LETTERS}]+(?:['’][${LETTERS}]+)*`, 'g')) ?? []).length;

function fold(text: string, accents = true): string {
  let value = text.toLowerCase().replace(/[’‘]/g, "'");
  if (!accents) value = value.normalize('NFD').replace(/[̀-ͯ]/g, '');
  return value.replace(new RegExp(`[^${LETTERS}']+`, 'g'), ' ').trim();
}

function leadOf(session: Json): string {
  for (const mode of ['comptoir', 'titre', 'intox', 'photo', 'micro', 'fil']) {
    const lead = session?.[mode]?.read?.lead?.fr;
    if (typeof lead === 'string' && lead) return lead;
  }
  return '';
}

function dicteeOf(lead: string): string | null {
  const fits = (lead.match(SENTENCE) ?? []).map((s) => s.trim()).filter((s) => words(s) >= 4 && words(s) <= 14 && /[.!?…]$/.test(s));
  return fits.length ? fits.reduce((best, s) => (words(s) < words(best) ? s : best)) : null;
}

function manifestOf(session: Json, audio: boolean): Json {
  const lead = leadOf(session);
  const lines: Json[] = lead ? [{ kind: 'lead', speaker_id: 'narrator', text_fr: lead }] : [];
  const comptoir = session?.comptoir;
  if (comptoir) {
    for (const member of comptoir.cast ?? []) lines.push({ kind: 'take', speaker_id: member.id, text_fr: member.take?.fr ?? '' });
    const opinion = comptoir.opinion;
    if (opinion?.reply?.line?.fr && opinion.proof !== 'marked') {
      lines.push({ kind: 'reply', speaker_id: opinion.reply.by, text_fr: opinion.reply.line.fr });
      if (opinion.comeback?.last_word?.fr) lines.push({ kind: 'last_word', speaker_id: opinion.reply.by, text_fr: opinion.comeback.last_word.fr });
    }
  }
  const dictee = dicteeOf(lead);
  return {
    audio: audio ? 'ready' : 'device',
    newsreader_id: 'narrator',
    lines: lines.filter((line) => line.text_fr),
    dictee: dictee && audio ? { text_fr: dictee, words: words(dictee), max_tries: 2 } : null,
  };
}

/** A silent mono WAV, `seconds` long: a clip that plays and ends, and says nothing. */
export function silentWav(seconds: number): Blob {
  const rate = 8000;
  const samples = Math.max(1, Math.round(rate * seconds));
  const buffer = new ArrayBuffer(44 + samples);
  const view = new DataView(buffer);
  const ascii = (at: number, text: string) => text.split('').forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
  ascii(0, 'RIFF');
  view.setUint32(4, 36 + samples, true);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate, true);
  view.setUint16(32, 1, true);
  view.setUint16(34, 8, true);
  ascii(36, 'data');
  view.setUint32(40, samples, true);
  for (let i = 0; i < samples; i += 1) view.setUint8(44 + i, 128);
  return new Blob([buffer], { type: 'audio/wav' });
}

function marksOf(answer: string, expected: string): Json[] {
  const mine: RegExpExecArray[] = [];
  const re = new RegExp(WORD.source, 'g');
  for (let m = re.exec(answer); m; m = re.exec(answer)) mine.push(m);
  const theirs = (expected.match(WORD) ?? []).map((w) => fold(w));
  const marks: Json[] = [];
  mine.forEach((match, index) => {
    const word = fold(match[0]);
    const right = theirs[index];
    if (right === undefined || word === right || marks.length >= 3) return;
    marks.push({ span_fr: match[0], start: match.index ?? 0, kind: fold(match[0], false) === fold(right, false) || word.slice(0, 3) === right.slice(0, 3) ? 'orthographe' : 'mot' });
  });
  if (!marks.length && mine.length < theirs.length && mine.length) {
    const lastWord = mine[mine.length - 1];
    marks.push({ span_fr: lastWord[0], start: lastWord.index ?? 0, kind: 'manque' });
  }
  return marks;
}

/** The mock transport with the voice's routes; `enabled: false` answers them 404 as the switch off does. */
export function withVoixMock<T extends VoixTransport>(
  inner: T,
  { enabled = true, audio = true, fail = false }: { enabled?: boolean; audio?: boolean; fail?: boolean } = {},
): T {
  const clips = new Map<string, number>();
  const route = (url: string) => /^\/revue\/sessions\/([^/]+)\/voix(?:\/(line|dictee))?$/.exec(url);
  const notFound = (): never => {
    throw Object.assign(new Error('Not Found'), { response: { status: 404, data: { detail: 'Not Found' } } });
  };
  const session = async (id: string): Promise<Json> => (await inner.get(`/revue/sessions/${encodeURIComponent(id)}`)) as Json;
  return {
    ...inner,
    async get(url: string) {
      const m = route(url);
      if (!m || m[2]) return inner.get(url);
      if (!enabled) notFound();
      return manifestOf(await session(decodeURIComponent(m[1])), audio);
    },
    async post(url: string, body: unknown) {
      const m = route(url);
      if (!m || !m[2]) return inner.post(url, body);
      if (!enabled) notFound();
      const b = (body ?? {}) as Json;
      const manifest = manifestOf(await session(decodeURIComponent(m[1])), audio);
      if (m[2] === 'line') {
        const text = String(b.text_fr ?? '');
        const known = [...manifest.lines.map((l: Json) => l.text_fr), manifest.dictee?.text_fr].some((t) => t && fold(t) === fold(text));
        if (!known) notFound();
        if (!audio) return { status: 'disabled' };
        // `&voixfail=1`: a clip that cannot be had (the screens then show every text at once).
        if (fail) throw Object.assign(new Error('clip failed'), { response: { status: 502, data: { detail: 'clip failed' } } });
        const id = `mock-voix-${clips.size + 1}`;
        clips.set(id, Math.max(1.2, text.length * 0.055));
        return { status: 'ready', clip_id: id, content_type: 'audio/wav', voice: 'mock', cached: false };
      }
      const expected = manifest.dictee?.text_fr;
      if (!expected) notFound();
      const answer = String(b.text ?? '');
      const attempt = Math.max(1, Math.min(2, Number(b.attempt) || 1));
      const outcome = fold(answer) === fold(expected) ? 'met' : fold(answer, false) === fold(expected, false) ? 'partially_met' : 'not_yet';
      const resolved = outcome === 'met' || attempt >= 2;
      return {
        outcome,
        attempt,
        max_tries: 2,
        resolved,
        answer_fr: answer,
        marks: outcome === 'met' ? [] : marksOf(answer, expected),
        expected_fr: resolved ? expected : null,
        note: null, // the server's note is the grader's, in the mother tongue
      };
    },
    clip: async (clipId: string) => silentWav(clips.get(clipId) ?? 1.5),
  } as T;
}
