/**
 * Les appels — the typed client for `/appels/*` and the call's pure model.
 *
 * Same shape as `lib/correcteur-api.ts`: the transport is the only thing that knows
 * the network; `today()` answering a bare 404 (the flag is off) resolves to `null`,
 * like a day with no call. The copy is here too, in the learner's chrome language:
 * the call itself is French only.
 */

export const APPELS_BASE = '/appels';
/** The transcription surface of a spoken line on a call (`app/services/appels.py`). */
export const APPEL_SURFACE = 'appel';

export type CallStatus = 'ringing' | 'live' | 'ended' | 'missed';

export type CallTurn = {
  who: 'caller' | 'learner';
  text_fr: string;
  clip_id?: string | null;
  mode?: 'text' | 'voice';
};

export type Call = {
  id: string;
  status: CallStatus;
  caller: { id: string; name: string; face?: string | null };
  turns: CallTurn[];
  voicemail: { text_fr: string; clip_id?: string | null } | null;
  turns_left: number;
  reason_en: string | null;
};

export type AppelsTransport = {
  get: (url: string) => Promise<unknown>;
  post: (url: string, body?: unknown) => Promise<unknown>;
};

export type AppelsClient = {
  today: () => Promise<Call | null>;
  answer: (id: string) => Promise<Call>;
  decline: (id: string) => Promise<Call>;
  say: (id: string, text: string, mode: 'text' | 'voice') => Promise<Call>;
  hangUp: (id: string) => Promise<Call>;
};

export class AppelError extends Error {
  constructor(public status: number, public code: string) {
    super(code);
  }
}

const STATUSES: CallStatus[] = ['ringing', 'live', 'ended', 'missed'];

const asObject = (value: unknown): Record<string, any> =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, any>) : {};

export function parseCall(raw: unknown): Call | null {
  const row = asObject(raw);
  if (!row.id || !STATUSES.includes(row.status)) return null;
  const caller = asObject(row.caller);
  const turns: CallTurn[] = (Array.isArray(row.turns) ? row.turns : [])
    .map(asObject)
    .filter((turn) => (turn.who === 'caller' || turn.who === 'learner') && typeof turn.text_fr === 'string')
    .map((turn) => ({
      who: turn.who,
      text_fr: turn.text_fr,
      clip_id: turn.clip_id ?? null,
      ...(turn.mode ? { mode: turn.mode } : {}),
    }));
  const voicemail = asObject(row.voicemail);
  return {
    id: String(row.id),
    status: row.status,
    caller: { id: String(caller.id || ''), name: String(caller.name || ''), face: caller.face ?? null },
    turns,
    voicemail: typeof voicemail.text_fr === 'string' ? { text_fr: voicemail.text_fr, clip_id: voicemail.clip_id ?? null } : null,
    turns_left: Math.max(0, Number(row.turns_left) || 0),
    reason_en: typeof row.reason_en === 'string' ? row.reason_en : null,
  };
}

function toError(error: unknown): AppelError {
  if (error instanceof AppelError) return error;
  const response = (error as { response?: { status?: number; data?: unknown } } | null)?.response;
  if (!response) return new AppelError(0, 'network');
  const detail = asObject(asObject(response.data).detail);
  return new AppelError(Number(response.status) || 0, String(detail.code || 'error'));
}

export function createAppelsClient(transport: AppelsTransport): AppelsClient {
  async function call(run: () => Promise<unknown>): Promise<Call> {
    let raw: unknown;
    try {
      raw = await run();
    } catch (error) {
      throw toError(error);
    }
    const parsed = parseCall(asObject(raw).call);
    if (!parsed) throw new AppelError(0, 'malformed');
    return parsed;
  }
  const at = (id: string, action: string) => `${APPELS_BASE}/${encodeURIComponent(id)}/${action}`;
  return {
    async today() {
      try {
        return parseCall(asObject(await transport.get(`${APPELS_BASE}/today`)).call);
      } catch (error) {
        const failure = toError(error);
        if (failure.status === 404) return null; // the feature is off
        throw failure;
      }
    },
    answer: (id) => call(() => transport.post(at(id, 'answer'))),
    decline: (id) => call(() => transport.post(at(id, 'decline'))),
    say: (id, text, mode) => call(() => transport.post(at(id, 'say'), { text, mode })),
    hangUp: (id) => call(() => transport.post(at(id, 'hang-up'))),
  };
}

export function httpAppelsTransport(): AppelsTransport {
  // Required lazily so the pure client (and its node tests) never load axios.
  const { apiService } = require('@/services/api') as typeof import('@/services/api');
  const quiet = { suppressGlobalError: true } as Record<string, unknown>;
  return {
    get: (url) => apiService.get(url, quiet),
    post: (url, body) => apiService.post(url, body ?? {}, quiet),
  };
}

let http: AppelsClient | null = null;

export function appelsClient(): AppelsClient {
  if (!http) http = createAppelsClient(httpAppelsTransport());
  return http;
}

// ---------------------------------------------------------------------------
// What the screen shows
// ---------------------------------------------------------------------------

/** The caller's last line: what plays, and what «Voir le texte» shows. */
export function lastCallerTurn(call: Call | null): { turn: CallTurn; index: number } | null {
  if (!call) return null;
  for (let index = call.turns.length - 1; index >= 0; index -= 1) {
    if (call.turns[index].who === 'caller') return { turn: call.turns[index], index };
  }
  return null;
}

/** «2:05» from seconds. */
export function callClock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/** The portrait the call shows: the drawn cast's neutral portrait, or none. */
export function callerPortrait(call: Call | null): string | null {
  const face = call?.caller.face;
  return face ? `/assets/serial/drawn/${face}/portrait-neutre.png` : null;
}

export type AppelsLanguage = 'fr' | 'en' | 'de';

export type AppelsCopy = {
  page_title: string;
  calling: (name: string) => string;
  calling_hint: string;
  answer: string;
  decline: string;
  voicemail_title: (name: string) => string;
  play: string;
  stop: string;
  hang_up: string;
  show_text: string;
  hide_text: string;
  you: string;
  talk: string;
  talking: string;
  listening: string;
  thinking: string;
  write: string;
  send: string;
  placeholder: string;
  turns_left: (n: number) => string;
  ended_title: (name: string) => string;
  ended_body: string;
  why: string;
  back_home: string;
  error: string;
  retry: string;
  mic_refused: string;
  empty: string;
};

const COPY: Record<AppelsLanguage, AppelsCopy> = {
  fr: {
    page_title: 'Appel',
    calling: (name) => `${name} t’appelle`,
    calling_hint: 'Un appel de deux minutes, en français.',
    answer: 'Décrocher',
    decline: 'Plus tard',
    voicemail_title: (name) => `Message de ${name}`,
    play: 'Écouter',
    stop: 'Arrêter',
    hang_up: 'Raccrocher',
    show_text: 'Voir le texte',
    hide_text: 'Masquer le texte',
    you: 'Toi',
    talk: 'Maintenir pour parler',
    talking: 'Je t’écoute… relâche pour envoyer',
    listening: 'Écoute…',
    thinking: '…',
    write: 'Écrire plutôt',
    send: 'Envoyer',
    placeholder: 'Ta réponse',
    turns_left: (n) => (n === 1 ? 'Encore une réplique' : `Encore ${n} répliques`),
    ended_title: (name) => `Appel terminé avec ${name}`,
    ended_body: 'Ce que tu as dit compte pour la suite de l’histoire.',
    why: 'Pourquoi cet appel',
    back_home: 'Retour à l’Atelier',
    error: 'La ligne a coupé.',
    retry: 'Réessayer',
    mic_refused: 'Micro indisponible : écris ta réponse.',
    empty: 'Rien entendu. Réessaie ou écris.',
  },
  en: {
    page_title: 'Call',
    calling: (name) => `${name} is calling`,
    calling_hint: 'A two-minute call, in French.',
    answer: 'Answer',
    decline: 'Not now',
    voicemail_title: (name) => `Voicemail from ${name}`,
    play: 'Play',
    stop: 'Stop',
    hang_up: 'Hang up',
    show_text: 'Show the text',
    hide_text: 'Hide the text',
    you: 'You',
    talk: 'Hold to talk',
    talking: 'Listening… let go to send',
    listening: 'Listen…',
    thinking: '…',
    write: 'Type instead',
    send: 'Send',
    placeholder: 'Your answer, in French',
    turns_left: (n) => (n === 1 ? 'One more line' : `${n} more lines`),
    ended_title: (name) => `Call with ${name} ended`,
    ended_body: 'What you said carries into the story.',
    why: 'Why they called',
    back_home: 'Back to the Atelier',
    error: 'The line dropped.',
    retry: 'Try again',
    mic_refused: 'No microphone: type your answer.',
    empty: 'Nothing heard. Try again or type.',
  },
  de: {
    page_title: 'Anruf',
    calling: (name) => `${name} ruft an`,
    calling_hint: 'Ein Anruf von zwei Minuten, auf Französisch.',
    answer: 'Annehmen',
    decline: 'Später',
    voicemail_title: (name) => `Nachricht von ${name}`,
    play: 'Abspielen',
    stop: 'Stopp',
    hang_up: 'Auflegen',
    show_text: 'Text zeigen',
    hide_text: 'Text ausblenden',
    you: 'Du',
    talk: 'Gedrückt halten zum Sprechen',
    talking: 'Ich höre zu… loslassen zum Senden',
    listening: 'Hör zu…',
    thinking: '…',
    write: 'Lieber tippen',
    send: 'Senden',
    placeholder: 'Deine Antwort, auf Französisch',
    turns_left: (n) => (n === 1 ? 'Noch ein Satz' : `Noch ${n} Sätze`),
    ended_title: (name) => `Anruf mit ${name} beendet`,
    ended_body: 'Was du gesagt hast, zählt für die Geschichte.',
    why: 'Warum der Anruf',
    back_home: 'Zurück zum Atelier',
    error: 'Die Leitung ist abgebrochen.',
    retry: 'Nochmal',
    mic_refused: 'Kein Mikrofon: tippe deine Antwort.',
    empty: 'Nichts gehört. Nochmal oder tippen.',
  },
};

export function appelsCopy(language: string | null | undefined): AppelsCopy {
  return COPY[(language === 'en' || language === 'de' ? language : 'fr') as AppelsLanguage];
}
