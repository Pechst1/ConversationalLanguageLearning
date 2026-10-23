/**
 * Le Quartier · what the quarter remembers.
 *
 * Everything you do is written down as an effect: a fact, a person's regard moved, a line for your
 * carnet, something you learned, an object changing hands, a place opened. What the screen shows
 * (the carnet, who greets you how, which storylet plays next, the note waiting when you come
 * back) is read from that log, so replaying a day only drops that day's effects.
 *
 * The words are the N1 agency pilot's (`app/data/season/s1/agency.json`): a storylet has a `when`
 * over the state, a `salience`, and plays once if it says so. In the app the log lives on the
 * server with Le Monde; the prototype keeps it on the phone, and works the same without storage.
 */

export type CastId = 'augustin_de_roncourt' | 'marin_leveque' | 'lila_bonnet' | 'margaux_barman' | 'camille_marchand';

export type Value = string | number | boolean;

/** A line in French with its two translations. */
export interface Words {
  fr: string;
  en: string;
  de: string;
}

export type Effect =
  | { kind: 'fact'; key: string; value: Value }
  | { kind: 'regard'; who: CastId; delta: number }
  | { kind: 'journal'; words: Words; who?: CastId }
  /** something you now know, and who told you */
  | { kind: 'learn'; key: string; words: Words; who?: CastId }
  /** who holds an object now: `toi`, a cast id, or a place (`zinc`) */
  | { kind: 'item'; id: string; holder: string }
  | { kind: 'meet'; who: CastId }
  | { kind: 'place'; id: string; status: PlaceStatus };

/** You have been there, or someone told you about it. (Whether a place exists yet is the world's, under `world.<id>`.) */
export type PlaceStatus = 'visited' | 'noticed';

export interface Logged {
  /** the day (or `roam`, `phone`) the effect belongs to */
  day: string;
  at: number;
  effect: Effect;
}

/** A condition over the state, as in agency.json: a value, one of several, set or not, at least or at most. */
export type Want = Value | Value[] | { set: boolean } | { min: number } | { max: number };
export type When = Record<string, Want>;

export interface Storylet {
  id: string;
  when?: When;
  salience?: number;
  /** plays only once (its id goes into the state as `seen.<id>`) */
  once?: boolean;
}

const KEY = 'qz.memory.v1';
const REGARD_MIN = -3;
const REGARD_MAX = 3;

interface Saved {
  v: 1;
  log: Logged[];
  lastSeen: number;
  visits: number;
}

function storage(): Storage | null {
  try {
    return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null;
  } catch {
    return null;
  }
}

export class Memory {
  private log: Logged[] = [];
  private listeners = new Set<() => void>();
  /** when you were last in the quarter (0 the first time) */
  lastSeen = 0;
  /** how many times you have opened the quarter */
  visits = 0;

  constructor(private persist = true) {
    if (!persist) return;
    const s = storage();
    try {
      const raw = s?.getItem(KEY);
      if (!raw) return;
      const saved = JSON.parse(raw) as Saved;
      if (saved && saved.v === 1 && Array.isArray(saved.log)) {
        this.log = saved.log.filter((l) => l && l.effect && typeof l.day === 'string');
        this.lastSeen = Number(saved.lastSeen) || 0;
        this.visits = Number(saved.visits) || 0;
      }
    } catch {
      // a broken record starts the quarter over
    }
  }

  subscribe(fn: () => void) {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  }

  private changed() {
    this.save();
    this.listeners.forEach((fn) => fn());
  }

  private save() {
    if (!this.persist) return;
    const s = storage();
    try {
      const saved: Saved = { v: 1, log: this.log, lastSeen: this.lastSeen, visits: this.visits };
      s?.setItem(KEY, JSON.stringify(saved));
    } catch {
      // full or blocked: the quarter still remembers until the page closes
    }
  }

  /** You arrive: count the visit and return how long you were away (ms; Infinity the first time). */
  arrive(now = Date.now()) {
    const away = this.lastSeen ? now - this.lastSeen : Infinity;
    this.visits++;
    this.lastSeen = now;
    this.save();
    return away;
  }

  /** You are still here (call now and then, so the next visit knows when you left). */
  touch(now = Date.now()) {
    this.lastSeen = now;
    this.save();
  }

  /** A day starts (or starts over): what you did in it before is forgotten. */
  beginDay(day: string) {
    const before = this.log.length;
    this.log = this.log.filter((l) => l.day !== day);
    if (this.log.length !== before) this.changed();
  }

  apply(day: string, effects: Effect | Effect[] | undefined) {
    const list = Array.isArray(effects) ? effects : effects ? [effects] : [];
    if (!list.length) return;
    const at = Date.now();
    list.forEach((effect) => this.log.push({ day, at, effect }));
    this.changed();
  }

  /** Forget everything (the carnet's «Tout oublier»). */
  clear() {
    this.log = [];
    this.changed();
  }

  get entries(): readonly Logged[] {
    return this.log;
  }

  /* ---- what the log says ----------------------------------------------------------------- */

  fact(key: string): Value | undefined {
    for (let i = this.log.length - 1; i >= 0; i--) {
      const e = this.log[i].effect;
      if (e.kind === 'fact' && e.key === key) return e.value;
    }
    return undefined;
  }

  regard(who: CastId): number {
    let r = 0;
    this.log.forEach((l) => {
      if (l.effect.kind === 'regard' && l.effect.who === who) r += l.effect.delta;
    });
    return Math.max(REGARD_MIN, Math.min(REGARD_MAX, r));
  }

  holder(item: string): string | undefined {
    for (let i = this.log.length - 1; i >= 0; i--) {
      const e = this.log[i].effect;
      if (e.kind === 'item' && e.id === item) return e.holder;
    }
    return undefined;
  }

  met(): CastId[] {
    const out: CastId[] = [];
    this.log.forEach((l) => {
      if (l.effect.kind === 'meet' && !out.includes(l.effect.who)) out.push(l.effect.who);
    });
    return out;
  }

  places(): Record<string, PlaceStatus> {
    const out: Record<string, PlaceStatus> = {};
    this.log.forEach((l) => {
      if (l.effect.kind === 'place') out[l.effect.id] = l.effect.status;
    });
    return out;
  }

  /** The carnet's lines, newest first. */
  journal(): Array<{ words: Words; who?: CastId; day: string }> {
    const out: Array<{ words: Words; who?: CastId; day: string }> = [];
    this.log.forEach((l) => {
      if (l.effect.kind === 'journal') out.unshift({ words: l.effect.words, who: l.effect.who, day: l.day });
    });
    return out;
  }

  /** What you know, once each, in the order you learned it. */
  known(): Array<{ key: string; words: Words; who?: CastId }> {
    const out: Array<{ key: string; words: Words; who?: CastId }> = [];
    this.log.forEach((l) => {
      const e = l.effect;
      if (e.kind === 'learn' && !out.some((k) => k.key === e.key)) out.push({ key: e.key, words: e.words, who: e.who });
    });
    return out;
  }

  /**
   * The state as flat keys, for storylets: `t1.told`, `regard.lila_bonnet`, `item.cle_cigale`,
   * `knows.margaux.odile`, `met.gus`, `place.marche_aligre`, `seen.<storylet>`, `visits`.
   */
  state(): Record<string, Value> {
    const s: Record<string, Value> = { visits: this.visits };
    const regard: Record<string, number> = {};
    this.log.forEach((l) => {
      const e = l.effect;
      if (e.kind === 'fact') s[e.key] = e.value;
      else if (e.kind === 'regard') regard[e.who] = (regard[e.who] ?? 0) + e.delta;
      else if (e.kind === 'learn') s[`knows.${e.key}`] = true;
      else if (e.kind === 'item') s[`item.${e.id}`] = e.holder;
      else if (e.kind === 'meet') s[`met.${e.who}`] = true;
      else if (e.kind === 'place') s[`place.${e.id}`] = e.status;
    });
    Object.keys(regard).forEach((who) => {
      s[`regard.${who}`] = Math.max(REGARD_MIN, Math.min(REGARD_MAX, regard[who]));
    });
    return s;
  }
}

/** Does the state meet a `when`? A regard nobody moved counts as 0. */
export function matches(when: When | undefined, state: Record<string, Value>): boolean {
  if (!when) return true;
  return Object.keys(when).every((key) => {
    const want = when[key];
    const has = state[key] ?? (key.startsWith('regard.') ? 0 : undefined);
    if (Array.isArray(want)) return has !== undefined && want.includes(has);
    if (want && typeof want === 'object') {
      if ('set' in want) return (has !== undefined && has !== false) === want.set;
      if ('min' in want) return typeof has === 'number' && has >= want.min;
      if ('max' in want) return typeof has === 'number' && has <= want.max;
      return false;
    }
    return has === want;
  });
}

/** The storylets whose `when` holds and that have not played (if once), most salient first. */
export function eligible<S extends Storylet>(list: readonly S[], state: Record<string, Value>): S[] {
  return list
    .filter((s) => matches(s.when, state) && !(s.once && state[`seen.${s.id}`]))
    .sort((a, b) => (b.salience ?? 0) - (a.salience ?? 0));
}

/** The one storylet to play now, or null. */
export function pick<S extends Storylet>(list: readonly S[], state: Record<string, Value>): S | null {
  return eligible(list, state)[0] ?? null;
}
