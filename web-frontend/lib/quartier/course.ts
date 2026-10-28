/**
 * Le Quartier · race day: a place where the news happens, played as it happens.
 *
 * The forge drafted the set from the survey and the kit drew it (`hippodrome.ts`); this runs the
 * day on it. The clerk at the betting window takes your bet, the regular at the rail tells you
 * what the Papier says about the race, the crowd talks about it as you pass (`course-talk.ts`).
 * Once you have your ticket and stand at the rail (or after a while, ticket or not), the horses
 * go into the stalls; the voice over the course calls the race while it is out of sight, then the
 * field comes up the straight and past the post in an order nobody wrote: it is drawn when the
 * gates open, each runner's chance by its odds. The board shows the result, and the window
 * pays, or doesn't. What you did lands in the same memory as the quai's choices.
 */
import { CanvasTexture, Mesh, MeshBasicMaterial, PlaneGeometry, SRGBColorSpace, Vector3 } from 'three';

import { personAvatar } from './avatars';
import { personArt } from './cast-art';
import { Troupe } from './cast';
import type { Figure, FigureSpec, PaperFigure } from './cast';
import { avatarRound } from './cast3d';
import { CHEERS, RACE_BARKS, atRail, atWindow, callRace, newRegular, newWindow, regularChips, regularHello, windowChips, windowHello } from './course-talk';
import type { Call, Race, Regular, Reply, Said, Window } from './course-talk';
import type { Hit, Quartier } from './engine';
import { KERB } from './kit';
import { horseArt } from './horse-art';
import type { Runner, VenueBuilt } from './hippodrome';
import { Memory } from './memory';
import type { Effect, Words } from './memory';
import { STRIDE } from './pace';
import { INKS, css, mix } from './palette';
import type { SiteBuilt, SitePerson } from './site';
import { BLANK } from './stage';
import type { Cue, Din, Director, Level, Native, SpeechUi, StageUi, Street } from './stage';

const w = (fr: string, en: string, de: string): Words => ({ fr, en, de });

const FACES: Record<string, string> = { joie: 'joie', malice: 'malice', fache: 'fache', surprise: 'surprise', cold: 'neutre', neutral: 'neutre' };

/** seconds from the off: into the straight, past the post */
const STRAIGHT = 23;
const SPEED = 16.6;
const RUN_IN = 300;
const POST = STRAIGHT + RUN_IN / SPEED;
/** how long the horses take to go into the stalls */
const LOADING = 5;

interface Horse {
  r: Runner;
  f: PaperFigure | null;
  /** metres behind the leader: after the off, into the straight, at the post */
  gapOff: number;
  gapIn: number;
  gapPost: number;
  /** metres from the stand-side rail: into the straight, at the post */
  laneIn: number;
  lanePost: number;
  phase: number;
  facing: 'neutre' | 'droite';
}

interface Goal {
  to: Vector3;
  look: Vector3;
  label: Words;
  /** someone to talk to when you get there */
  talk?: string;
}

interface Person {
  key: string;
  spec: SitePerson;
  f: Figure | null;
}

export interface CourseOptions {
  level?: Level;
  native?: Native;
  memory?: Memory;
  street?: Street;
  onCue?: (cue: Cue) => void;
  /** the voice over the course: the stalls, the race called, the result (`heat`: how worked up, 0 to 1) */
  onSay?: (fr: string, heat: number) => void;
}

const CLOSED: Said = { say: w('Trop tard, les paris sont fermés ! Regardez la course !', 'Too late, betting is closed! Watch the race!', 'Zu spät, die Wetten sind geschlossen! Schauen Sie das Rennen!'), mood: 'malice' };
const HUSH: Said = { say: w('Chut… Regardez ! Ils arrivent !', 'Shh… Look! Here they come!', 'Psst… Schauen Sie! Da kommen sie!'), mood: 'surprise' };

const ease = (p: number) => p * p * (3 - 2 * p);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export class Course implements Director {
  ui: StageUi = { ...BLANK };
  readonly memory: Memory;
  readonly site: SiteBuilt;
  readonly venue: VenueBuilt;
  readonly race: Race;
  private listeners = new Set<(ui: StageUi) => void>();
  private native: Native;
  private onCue?: (cue: Cue) => void;
  private onSay?: (fr: string, heat: number) => void;
  private street?: Street;
  private people: Troupe<Figure>;
  private field: Troupe;
  private cast: Person[] = [];
  private horses: Horse[] = [];
  private window: Window;
  private regular: Regular;
  private talking: Person | null = null;
  private goal: Goal | null = null;
  private wayAt = 0;
  private beganAt = 0;
  private ticketAt = 0;
  /** the stalls are loading (the off is at `offAt`), the race is on, or it is over */
  private offAt = 0;
  /** since when you have stood at the rail */
  private railAt = 0;
  /** your head is following the field */
  private following = false;
  /** how loud the field's hooves are where you stand */
  private hooves = 0;
  private calls: Call[] = [];
  private called = 0;
  private finish: number[] = [];
  private over = false;
  private board: { mesh: Mesh; ctx: CanvasRenderingContext2D; tex: CanvasTexture } | null = null;
  private barkAt = 0;
  private barkedBy = new Map<string, number>();
  private lastBark = -1;
  private stopTick: () => void;
  private stopHit: () => void;
  private since = 0;
  private disposed = false;
  readonly day: string;

  constructor(private q: Quartier, opts: CourseOptions = {}) {
    if (!q.site || !q.site.venue) throw new Error('Race day is at a racecourse');
    this.site = q.site;
    this.venue = q.site.venue;
    this.day = `visit.${q.site.spec.id}`;
    this.native = opts.native ?? 'en';
    this.onCue = opts.onCue;
    this.onSay = opts.onSay;
    this.street = opts.street;
    this.memory = opts.memory ?? new Memory(false);
    // the clerk remembers a bonjour you owed her, as the end card said she would
    this.window = newWindow(this.memory.fact('hippodrome_longchamp.guichetiere.bonjour') === 'forgot');
    this.race = { spec: this.venue.spec.race, runners: this.venue.runners, holder: this.venue.holder, result: null };
    // the regular knows you again from your last race day: who won, and how your ticket went
    const winner = this.memory.fact('hippodrome_longchamp.winner');
    const ticket = this.memory.fact('hippodrome_longchamp.ticket');
    this.regular = newRegular(this.race, Math.random(), typeof winner === 'number' ? { winner, ticket: typeof ticket === 'string' ? ticket : null } : null);
    // the clerk and the regular stand in the round; the horses stay printed cards
    this.people = new Troupe<Figure>(q.world, { figure: (key, expression) => this.personArt(key, expression), item: () => null }, 400, q.cast === 'round' ? (spec) => this.round(spec) : undefined);
    this.field = new Troupe(q.world, { figure: (key, expression) => this.horseArt(key, expression), item: () => null }, 360);
    q.addTroupe(this.people);
    q.addTroupe(this.field);
    this.stopTick = q.onTick((dt) => this.tick(dt));
    this.stopHit = q.on((hit) => this.hit(hit));
  }

  subscribe(fn: (ui: StageUi) => void) {
    this.listeners.add(fn);
    fn(this.ui);
    return () => {
      this.listeners.delete(fn);
    };
  }

  setLevel(level: Level) {
    void level;
  }

  setNative(native: Native) {
    this.native = native;
  }

  setStreet(street: Street | undefined) {
    this.street = street;
  }

  private show(patch: Partial<StageUi>) {
    if (!Object.keys(patch).length) return;
    this.ui = { ...this.ui, ...patch };
    this.listeners.forEach((fn) => fn(this.ui));
  }

  private say(words: Words) {
    return { text: words.fr, native: words[this.native] };
  }

  private speech(who: string, name: string, words: Words): SpeechUi {
    return { who, char: 'passant', name, text: words.fr, native: words[this.native], direction: null };
  }

  private remember(effects: Effect[]) {
    this.memory.apply(this.day, effects);
  }

  /* ---- the drawings ----------------------------------------------------------------------- */

  private personArt(key: string, expression: string) {
    const p = this.cast.find((x) => x.key === key);
    return personArt(p?.spec.seed ?? 11, p?.spec.look ?? {}, (FACES[expression] ?? expression) as never, 300);
  }

  /** Someone the brief names, in the round: the record their card is drawn from, stood up. */
  private round(spec: FigureSpec) {
    const p = this.cast.find((x) => x.key === spec.key);
    const seed = p?.spec.seed ?? 11;
    return avatarRound(this.q.world, personAvatar(seed, p?.spec.look ?? {}), spec, seed);
  }

  /** A runner, facing the way it runs as you see it: «neutre» is the usual view from the stand side. */
  private horseArt(key: string, expression: string) {
    const n = parseInt(key.split(':')[1], 10);
    const r = this.venue.runners.find((x) => x.n === n);
    if (!r) return null;
    return horseArt(r.n, r.silks, r.coat, expression !== 'droite');
  }

  /* ---- what the screen calls -------------------------------------------------------------- */

  async prepare() {
    const v = this.venue;
    this.site.spec.people.forEach((spec) => {
      this.cast.push({ key: spec.key, spec, f: null });
    });
    for (const p of this.cast) {
      if (this.disposed) return;
      const at = p.key === 'guichetiere' ? v.clerk.clone().setY(KERB) : v.rail.clone().setY(KERB);
      try {
        p.f = await this.people.add({ key: p.key, height: p.key === 'guichetiere' ? 1.66 : 1.74 }, at);
      } catch {
        p.f = null;
      }
    }
    this.makeBoard();
    void this.printField();
  }

  private async printField() {
    const v = this.venue;
    for (const r of v.runners) {
      if (this.disposed) return;
      const h: Horse = { r, f: null, gapOff: 0, gapIn: 0, gapPost: 0, laneIn: 0, lanePost: 0, phase: Math.random() * 6, facing: 'neutre' };
      try {
        h.f = await this.field.add({ key: `cheval:${r.n}`, height: 2.55 }, v.at(-RUN_IN - 40, v.spec.track / 2, KERB));
        if (h.f) h.f.visible = false;
      } catch {
        h.f = null;
      }
      this.horses.push(h);
      await new Promise((res) => setTimeout(res, 20));
    }
  }

  begin() {
    this.since = this.memory.entries.length;
    this.beganAt = performance.now();
    if (this.memory.places()[this.site.spec.id] !== 'visited') this.memory.apply(this.day, { kind: 'place', id: this.site.spec.id, status: 'visited' });
    this.show({ ...BLANK, phase: 'roam', progress: 0 });
    this.nextGoal();
  }

  tap() {
    if (this.ui.aside) this.show({ aside: null });
    else if (this.ui.bark) this.show({ bark: null });
  }

  answer(text: string) {
    void text;
  }

  go() {
    const g = this.goal;
    if (g) void this.q.walkTo(g.to, STRIDE);
  }

  skipWalk() {
    const g = this.goal;
    if (!g) return;
    this.q.place(g.to, g.look);
    this.arrive();
  }

  goOn() {
    // the race waits for nobody, and nothing waits for you
  }

  replay() {
    this.roam();
  }

  roam() {
    this.show({ phase: 'roam', recap: null, canLeave: true });
    this.nextGoal();
  }

  leave() {
    if (this.ui.talk) this.endTalk();
    this.goal = null;
    this.q.stop();
    this.q.look(null);
    this.q.showWay(null);
    this.show({ phase: 'end', recap: this.recap(), canLeave: false, goal: null, bark: null, aside: null, caption: null });
  }

  talkTo(key: string) {
    const p = this.cast.find((x) => x.key === key);
    if (!p) return;
    const closed = this.offAt > 0 && !this.over;
    const coming = closed && this.raceTime() > STRAIGHT - 2;
    let first: Said;
    let chips: string[];
    if (key === 'guichetiere') {
      first = closed ? CLOSED : windowHello(this.window, this.race);
      chips = closed ? [] : windowChips(this.window, this.race);
    } else {
      first = coming ? HUSH : regularHello(this.regular, this.race);
      chips = coming ? [] : this.regular.greeted || this.race.result ? regularChips(this.regular, this.race) : ['Bonjour !'].concat(regularChips(this.regular, this.race).slice(0, 2));
    }
    this.talking = p;
    if (this.goal?.talk === key) {
      this.goal = null;
      this.q.showWay(null);
    }
    this.q.stop();
    p.f?.hop();
    p.f?.talk(1.2);
    this.face(p, first.mood);
    if (p.f) {
      const d = this.q.camera.position.distanceTo(p.f.face());
      this.q.look(p.f.face().add(new Vector3(0, -d * 0.26, 0)), 2.4);
    }
    this.onCue?.('paper');
    this.show({ talk: { who: key, char: 'passant', name: p.spec.name.fr, lines: [{ ...this.say(first.say), direction: null }], you: null, chips }, bark: null, goal: null });
  }

  talkSay(text: string) {
    const p = this.talking;
    const talk = this.ui.talk;
    if (!p || !talk || !text.trim()) return;
    const closed = this.offAt > 0 && !this.over;
    let r: Reply;
    if (closed && (p.key === 'guichetiere' || this.raceTime() > STRAIGHT - 2)) r = { lines: [p.key === 'guichetiere' ? CLOSED : HUSH], effects: [], chips: [] };
    else r = p.key === 'guichetiere' ? atWindow(this.window, text, this.race) : atRail(this.regular, text, this.race);
    this.remember(r.effects);
    if (p.key === 'guichetiere' && this.window.ticket && !this.ticketAt) this.ticketAt = performance.now();
    const last = r.lines[r.lines.length - 1];
    this.face(p, last?.mood);
    p.f?.talk(0.9 + r.lines.reduce((n, l) => n + l.say.fr.length, 0) * 0.045);
    if (r.effects.some((e) => e.kind === 'journal')) this.onCue?.('paper');
    this.show({ talk: { ...talk, you: text.trim(), lines: r.lines.map((l) => ({ ...this.say(l.say), direction: null })), chips: r.chips } });
    if (r.done) {
      window.setTimeout(() => {
        if (this.talking === p && !this.disposed) this.endTalk();
      }, 2600);
    }
  }

  endTalk() {
    const p = this.talking;
    if (!p && !this.ui.talk) return;
    this.talking = null;
    this.q.look(null);
    let bark: StageUi['bark'] = null;
    // you walked off with the clerk waiting for your money
    if (p?.key === 'guichetiere' && this.window.owing !== null) {
      this.window.owing = null;
      this.window.ask = { horse: null, kind: null, stake: null };
      bark = { ...this.speech(p.key, p.spec.name.fr, w('Eh ! Et votre pari ?', 'Hey! What about your bet?', 'He! Und Ihre Wette?')), at: performance.now() };
    }
    if (p) this.face(p, 'neutral');
    this.show({ talk: null, bark });
    this.nextGoal();
  }

  passerby(key: string, tapped: boolean) {
    const now = performance.now();
    const ui = this.ui;
    if (ui.phase !== 'roam' || ui.talk) return;
    if (tapped) this.street?.hop(key);
    if (!tapped && (now - this.barkAt < 8000 || now - (this.barkedBy.get(key) ?? -1e9) < 60000)) return;
    if (tapped && now - (this.barkedBy.get(key) ?? -1e9) < 1500) return;
    let words: Words;
    if (this.offAt > 0 && !this.over && now > this.offAt) {
      const pick = this.race.runners[Math.floor(Math.random() * this.race.runners.length)].n;
      const c = CHEERS[Math.floor(Math.random() * CHEERS.length)];
      words = w(c.fr.replace('{n}', String(pick)), c.en.replace('{n}', String(pick)), c.de.replace('{n}', String(pick)));
    } else {
      let i = Math.floor(Math.random() * RACE_BARKS.length);
      if (i === this.lastBark) i = (i + 1) % RACE_BARKS.length;
      this.lastBark = i;
      words = RACE_BARKS[i];
    }
    this.barkAt = now;
    this.barkedBy.set(key, now);
    this.show({ bark: { ...this.speech(key, 'Quelqu’un', words), at: now } });
  }

  phoneReply(text: string) {
    void text;
  }

  closePhone() {
    this.show({ phone: null });
  }

  dispose() {
    this.disposed = true;
    this.stopTick();
    this.stopHit();
    this.q.removeTroupe(this.people);
    this.q.removeTroupe(this.field);
    this.people.dispose();
    this.field.dispose();
    if (this.board) {
      this.q.scene.remove(this.board.mesh);
      this.board.mesh.geometry.dispose();
      (this.board.mesh.material as MeshBasicMaterial).dispose();
      this.board.tex.dispose();
    }
    this.listeners.clear();
  }

  /* ---- the frame -------------------------------------------------------------------------- */

  private hit(hit: Hit) {
    if (this.ui.phase !== 'roam') return;
    if (hit.kind === 'person') {
      if (hit.key.indexOf('passant:') === 0) {
        this.passerby(hit.key, true);
        return;
      }
      if (this.cast.some((x) => x.key === hit.key) && this.talking?.key !== hit.key) {
        if (this.ui.talk) this.endTalk();
        this.talkTo(hit.key);
      }
      return;
    }
    if (hit.kind === 'ground') {
      if (this.ui.talk) this.endTalk();
      void this.q.walkTo(hit.point, STRIDE);
    }
  }

  /** Seconds since the off (negative while the horses go into the stalls). */
  private raceTime() {
    return this.offAt ? (performance.now() - this.offAt) / 1000 : -1;
  }

  /** Where you are across the course: metres from the rail (negative: on your side of it). */
  private acrossOf(p: Vector3) {
    const v = this.venue.spec;
    return (p.x - v.post[0]) * v.n[0] + (p.z - v.post[1]) * v.n[1];
  }

  private tick(dt: number) {
    const now = performance.now();
    const roaming = this.ui.phase === 'roam' && !this.ui.talk;
    const g = this.goal;
    if (g && roaming) {
      if (now - this.wayAt > 900 && !this.q.walking) {
        this.wayAt = now;
        this.q.showWay(g.to);
      }
      if (Math.hypot(this.q.feet.x - g.to.x, this.q.feet.z - g.to.z) < 1.6) this.arrive();
    }
    if (this.ui.bark && now - this.ui.bark.at > 6500) this.show({ bark: null });
    if (roaming !== this.ui.canLeave) this.show({ canLeave: roaming });
    if (this.ui.phase === 'roam') {
      this.maybeCall(now);
      this.run(now, dt);
    }
  }

  /** The horses go into the stalls once you are ready to watch, or once the course is. */
  private maybeCall(now: number) {
    if (this.offAt || !this.beganAt || !this.horses.length || this.horses.length < this.venue.runners.length) return;
    if (this.acrossOf(this.q.feet) > -5) this.railAt = this.railAt || now;
    else this.railAt = 0;
    const atRail = this.railAt > 0 && now - this.railAt > 6000;
    const since = (now - this.beganAt) / 1000;
    const ticket = this.window.ticket !== null;
    const ready = (ticket && (atRail || (now - this.ticketAt) / 1000 > 40)) || (!ticket && atRail && since > 40) || since > 150;
    if (!ready || this.ui.talk) return;
    this.offAt = now + LOADING * 1000;
    this.draw();
    const stalls = w('Les chevaux entrent dans les stalles… Les paris sont fermés !', 'The horses are going into the stalls… Betting is closed!', 'Die Pferde gehen in die Startboxen… Die Wetten sind geschlossen!');
    this.show({ caption: this.say(stalls) });
    this.onSay?.(stalls.fr, 0);
    if (this.goal) {
      this.goal = null;
      this.q.showWay(null);
      this.show({ goal: null });
    }
  }

  /**
   * The draw at the off: the finish by each runner's chance (its odds), the field's order at the
   * off and into the straight, the lanes, and the race called from it.
   */
  private draw() {
    const T = this.venue.spec.track;
    const left = this.horses.slice();
    const finish: Horse[] = [];
    while (left.length) {
      const weights = left.map((h) => 1 / (h.r.odds + 1));
      let roll = Math.random() * weights.reduce((a, b) => a + b, 0);
      let k = 0;
      while (k < left.length - 1 && (roll -= weights[k]) > 0) k++;
      finish.push(left.splice(k, 1)[0]);
    }
    let gap = 0;
    finish.forEach((h, i) => {
      if (i) gap += i < 4 ? 0.4 + Math.random() * 1.6 : 0.8 + Math.random() * 2.2;
      h.gapPost = gap;
    });
    // into the straight: the finish order shuffled about, the winner somewhere in the pack
    const into = finish.map((h, i) => ({ h, k: i + (Math.random() - 0.5) * 9 + (i === 0 ? 3 + Math.random() * 3 : 0) })).sort((a, b) => a.k - b.k);
    gap = 0;
    into.forEach(({ h }, i) => {
      if (i) gap += 1 + Math.random() * 1.6;
      h.gapIn = gap;
      // bunched toward the inner rail, four and five wide
      h.laneIn = T - 2 - (i % 5) * 1.7 - Math.random() * 0.4;
    });
    const off = finish.map((h) => ({ h, k: Math.random() })).sort((a, b) => a.k - b.k);
    gap = 0;
    off.forEach(({ h }, i) => {
      if (i) gap += 1.2 + Math.random() * 1.8;
      h.gapOff = gap;
    });
    // at the post, fanned across the track; the winner came wide, toward the stand
    finish.forEach((h, i) => {
      h.lanePost = i === 0 ? 4 + Math.random() * 3 : Math.max(2.5, Math.min(T - 2, h.laneIn + (Math.random() - 0.6) * 9));
    });
    this.finish = finish.map((h) => h.r.n);
    this.calls = callRace(this.race, (t) => this.orderAt(t), STRAIGHT, POST, this.finish);
    this.called = 0;
  }

  /** Who leads at `t` seconds from the off, first to last. */
  private orderAt(t: number): number[] {
    const gapAt = (h: Horse) => (t < STRAIGHT ? lerp(h.gapOff, h.gapIn, t / STRAIGHT) : lerp(h.gapIn, h.gapPost, ease(Math.min(1, (t - STRAIGHT) / (POST - STRAIGHT)))));
    return this.horses
      .slice()
      .sort((a, b) => gapAt(a) - gapAt(b))
      .map((h) => h.r.n);
  }

  /** The crowd from a murmur to the roar at the post, and the hooves as the field goes past. */
  din(): Din {
    const t = this.raceTime();
    let crowd = 0.2;
    if (this.offAt && t >= 0) {
      if (t < STRAIGHT) crowd = 0.3 + 0.12 * (t / STRAIGHT);
      else if (t < POST) crowd = 0.42 + 0.58 * Math.pow((t - STRAIGHT) / (POST - STRAIGHT), 1.5);
      else crowd = Math.max(0.24, 1 - (t - POST) / 9);
    }
    return { crowd, hooves: this.ui.phase === 'roam' ? this.hooves : 0 };
  }

  /** The race, frame by frame: the calls, the field up the straight, the finish. */
  private run(now: number, dt: number) {
    if (!this.offAt) return;
    const t = (now - this.offAt) / 1000;
    if (t < 0 || t > POST + 16) {
      this.hooves = 0;
      return;
    }
    if (this.called === 0) this.onCue?.('bell');
    if (t > STRAIGHT - 1.5 && t < POST + 3 && this.ui.talk) this.endTalk();
    while (this.called < this.calls.length && this.calls[this.called].at <= t) {
      const call = this.calls[this.called];
      this.show({ caption: this.say(call.say) });
      // calm on the far side, worked up into the straight, hoarse at the post
      this.onSay?.(call.say.fr, call.at < STRAIGHT ? 0.2 : call.at <= POST ? 0.5 + (0.5 * (call.at - STRAIGHT)) / (POST - STRAIGHT) : 0.3);
      this.called++;
    }
    const v = this.venue;
    const p = Math.max(0, Math.min(1, (t - STRAIGHT) / (POST - STRAIGHT)));
    // past the post they ease off and pull up, out by the far turn
    const after = Math.min(t - POST, 14);
    const lead = t < POST ? -RUN_IN + SPEED * (t - STRAIGHT) : SPEED * after - 0.55 * after * after;
    const cam = this.q.camera.position;
    let cx = 0;
    let cz = 0;
    let seen = 0;
    let near = Infinity;
    this.horses.forEach((h) => {
      const f = h.f;
      if (!f) return;
      const gap = t < POST ? lerp(h.gapIn, h.gapPost, ease(p)) : h.gapPost;
      const u = lead - gap;
      const lane = lerp(h.laneIn, h.lanePost, ease(p));
      f.visible = t >= STRAIGHT - 0.3 && t < POST + 15;
      if (!f.visible) return;
      const pos = v.at(u, lane, KERB);
      f.place(pos);
      const pace = t < POST ? 1 : Math.max(0.2, 1 - after * 0.066);
      h.phase += dt * Math.PI * 2 * 2.3 * pace;
      f.lift = Math.abs(Math.cos(h.phase)) * 0.16 * pace;
      f.rock = Math.sin(h.phase) * 0.05 * pace;
      // the drawing faces the way it runs, as you see it
      const dx = cam.x - pos.x;
      const dz = cam.z - pos.z;
      const facing = v.spec.u[0] * dz - v.spec.u[1] * dx > 0 ? 'droite' : 'neutre';
      if (facing !== h.facing) {
        h.facing = facing;
        void this.field.face(`cheval:${h.r.n}`, facing);
      }
      if (u > -RUN_IN && u < 60) {
        cx += pos.x;
        cz += pos.z;
        seen++;
      }
      near = Math.min(near, Math.hypot(dx, dz));
    });
    // the hooves carry 200 m over the turf, and fade as the field pulls up
    this.hooves = near < 200 ? Math.pow(1 - near / 200, 2) * (t < POST ? 1 : Math.max(0.2, 1 - after * 0.066)) : 0;
    // your head follows the field up the straight, unless you are talking
    if (!this.ui.talk && t > STRAIGHT + 0.5 && t < POST + 2.5 && seen) {
      this.q.look(new Vector3(cx / seen, 1.5, cz / seen), 2.2);
      this.following = true;
    } else if (this.following && t >= POST + 2.5) {
      this.following = false;
      this.q.look(null);
    }
    if (t > POST + 7 && !this.over) this.finished();
  }

  /** The result: on the board, in your memory, and what your ticket says. */
  private finished() {
    this.over = true;
    this.race.result = this.finish.slice();
    this.paintBoard();
    // the board across the track has the result: your head turns to it, then lets go
    if (!this.ui.talk) {
      this.q.look(this.venue.board.center, 2.0);
      window.setTimeout(() => !this.disposed && !this.ui.talk && this.q.look(null), 3500);
    }
    const r = this.race.result;
    const name = this.race.spec.name;
    this.remember([
      { kind: 'journal', words: w(`Tu as vu le ${r[0]} gagner le ${name.fr}.`, `You saw number ${r[0]} win the ${name.en}.`, `Du hast die ${r[0]} den ${name.de} gewinnen sehen.`) },
      { kind: 'fact', key: 'hippodrome_longchamp.winner', value: r[0] },
      // and how your ticket went, for the regular the next time
      { kind: 'fact', key: 'hippodrome_longchamp.ticket', value: this.window.ticket ? (this.won() ? 'won' : 'lost') : 'none' },
      // the words of a race, heard as it was called
      {
        kind: 'learn',
        key: 'hippodrome_longchamp.mots',
        from: 'Le speaker',
        words: w(
          'La corde (le bord intérieur de la piste), la ligne droite (la fin, jusqu’au poteau) et côte à côte.',
          'La corde (the inside rail), la ligne droite (the home straight, up to the post) and côte à côte (neck and neck).',
          'La corde (die Innenbande), la ligne droite (die Zielgerade bis zum Pfosten) und côte à côte (Kopf an Kopf).',
        ),
      },
    ]);
    const tk = this.window.ticket;
    let line: Words;
    if (!tk) line = w(`Le ${r[0]} gagne. Sans ticket, tu as juste crié.`, `Number ${r[0]} wins. No ticket: you just shouted.`, `Die ${r[0]} gewinnt. Ohne Ticket hast du nur mitgefiebert.`);
    else if ((tk.kind === 'gagnant' && r[0] === tk.horse) || (tk.kind === 'place' && r.slice(0, 3).indexOf(tk.horse) >= 0)) line = w(`Ton ticket, le ${tk.horse} : gagné ! Passe au guichet.`, `Your ticket, number ${tk.horse}: a winner! Go to the window.`, `Dein Ticket, die ${tk.horse}: gewonnen! Geh zum Schalter.`);
    else line = w(`Ton ticket, le ${tk.horse}… arrivé ${r.indexOf(tk.horse) + 1}e. Perdu.`, `Your ticket, number ${tk.horse}… came ${ordinal(r.indexOf(tk.horse) + 1)}. Lost.`, `Dein Ticket, die ${tk.horse}… ${r.indexOf(tk.horse) + 1}. geworden. Verloren.`);
    this.show({ caption: this.say(line) });
    const reg = this.cast.find((x) => x.key === 'habitue');
    if (reg) {
      const said = regularHello(this.regular, this.race);
      reg.f?.talk(2);
      this.face(reg, said.mood);
      this.show({ bark: { ...this.speech(reg.key, reg.spec.name.fr, said.say), at: performance.now() } });
    }
    window.setTimeout(() => {
      if (!this.disposed && this.ui.caption) this.show({ caption: null });
    }, 9000);
    this.nextGoal();
  }

  private arrive() {
    const g = this.goal;
    if (!g) return;
    this.goal = null;
    this.q.showWay(null);
    this.q.stop();
    if (g.talk) this.talkTo(g.talk);
    else {
      this.q.look(g.look, 2.4);
      window.setTimeout(() => !this.ui.talk && this.q.look(null), 1600);
      this.show({ goal: null });
    }
  }

  /** The errand of the moment: a bet, then the rail, then (if the ticket won) the window again. */
  private nextGoal() {
    const v = this.venue;
    const c = this.window;
    let goal: Goal | null = null;
    if (!this.offAt && !c.ticket) goal = { to: v.window.clone(), look: v.clerk.clone().setY(1.5), label: w('Parier deux euros au guichet', 'Bet two euros at the window', 'Am Schalter zwei Euro setzen'), talk: 'guichetiere' };
    else if (!this.offAt && c.ticket) goal = { to: v.at(-5, -2.2, 0), look: v.at(-150, v.spec.track * 0.6, 1.5), label: w('Aller voir la course au bord de la piste', 'Go and watch the race at the rail', 'Das Rennen an der Bande anschauen') };
    else if (this.over && c.ticket && !c.paid && this.won()) goal = { to: v.window.clone(), look: v.clerk.clone().setY(1.5), label: w('Toucher les gains au guichet', 'Collect the winnings at the window', 'Den Gewinn am Schalter abholen'), talk: 'guichetiere' };
    this.goal = goal;
    this.wayAt = 0;
    if (!goal) this.q.showWay(null);
    this.show({ goal: goal ? { label: goal.label.fr, native: goal.label[this.native] } : null });
  }

  private won() {
    const tk = this.window.ticket;
    const r = this.race.result;
    if (!tk || !r) return false;
    return tk.kind === 'gagnant' ? r[0] === tk.horse : r.slice(0, 3).indexOf(tk.horse) >= 0;
  }

  private face(p: Person, mood: string | undefined) {
    if (!p.f) return;
    const expression = FACES[mood ?? 'neutral'] ?? 'neutre';
    if (expression !== p.f.expression) void this.people.face(p.key, expression);
  }

  /* ---- the board -------------------------------------------------------------------------- */

  private makeBoard() {
    const b = this.venue.board;
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = Math.round((1024 * b.height) / b.width);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const tex = new CanvasTexture(canvas);
    tex.colorSpace = SRGBColorSpace;
    const mesh = new Mesh(new PlaneGeometry(b.width, b.height), new MeshBasicMaterial({ map: tex, toneMapped: false }));
    mesh.position.copy(b.center);
    mesh.lookAt(b.center.clone().add(b.normal));
    this.q.scene.add(mesh);
    this.board = { mesh, ctx, tex };
    this.paintBoard();
  }

  private paintBoard() {
    const B = this.board;
    if (!B) return;
    const { ctx } = B;
    const W = ctx.canvas.width;
    const H = ctx.canvas.height;
    const race = this.race;
    ctx.fillStyle = css(mix(INKS.ink, INKS.cobalt, 0.22));
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = css(INKS.sunflower);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = '700 46px "Helvetica Neue", Arial, sans-serif';
    ctx.fillText(race.spec.name.fr.toUpperCase(), W / 2, 44);
    ctx.fillStyle = css(INKS.card);
    ctx.font = '500 28px "Helvetica Neue", Arial, sans-serif';
    ctx.fillText(`${race.spec.metres.toLocaleString('fr-FR')} m · ${race.spec.hour} · ${race.runners.length} partants`, W / 2, 92);
    if (race.result) {
      ctx.fillStyle = css(INKS.card);
      ctx.font = '700 40px "Helvetica Neue", Arial, sans-serif';
      ctx.fillText('ARRIVÉE', W / 2, 170);
      race.result.slice(0, 3).forEach((n, i) => {
        const x = W / 2 + (i - 1) * 250;
        const r = race.runners.find((x2) => x2.n === n);
        ctx.fillStyle = r ? css(r.silks.body) : css(INKS.card);
        ctx.fillRect(x - 90, 220, 180, 180);
        ctx.fillStyle = css(INKS.card);
        ctx.fillRect(x - 70, 240, 140, 140);
        ctx.fillStyle = css(INKS.ink);
        ctx.font = '700 104px Georgia, "Times New Roman", serif';
        ctx.fillText(String(n), x, 316);
        ctx.fillStyle = css(INKS.sunflower);
        ctx.font = '700 30px "Helvetica Neue", Arial, sans-serif';
        ctx.fillText(['1er', '2e', '3e'][i], x, 434);
      });
    } else {
      ctx.font = '700 30px "Helvetica Neue", Arial, sans-serif';
      const rows = Math.ceil(race.runners.length / 2);
      race.runners.forEach((r, i) => {
        const col = i < rows ? 0 : 1;
        const row = i % rows;
        const x = col ? W * 0.56 : W * 0.08;
        const y = 150 + row * 44;
        ctx.fillStyle = css(r.silks.body);
        ctx.fillRect(x, y - 17, 34, 34);
        ctx.fillStyle = css(r.silks.second);
        ctx.fillRect(x + 8, y - 9, 18, 18);
        ctx.textAlign = 'left';
        ctx.fillStyle = css(INKS.card);
        ctx.fillText(String(r.n), x + 50, y + 1);
        ctx.fillStyle = r.n === race.holder ? css(INKS.sunflower) : css(INKS.card);
        ctx.textAlign = 'right';
        ctx.fillText(`${r.odds}/1`, x + 330, y + 1);
      });
      ctx.textAlign = 'center';
    }
    B.tex.needsUpdate = true;
  }

  /* ---- the end card ----------------------------------------------------------------------- */

  private recap(): StageUi['recap'] {
    const mine = this.memory.entries.slice(this.since).filter((l) => l.day === this.day);
    const did: Array<{ text: string; native: string }> = [];
    let forgot = false;
    mine.forEach((l) => {
      const e = l.effect;
      if (e.kind === 'journal') did.push(this.say(e.words));
      else if (e.kind === 'learn') did.push(this.say(w(`Tu as appris : ${lower(e.words.fr)}`, `You learned: ${lower(e.words.en)}`, `Du hast erfahren: ${e.words.de}`)));
      else if (e.kind === 'fact' && e.key === 'hippodrome_longchamp.guichetiere.bonjour' && e.value === 'forgot') forgot = true;
    });
    if (!did.length) did.push(this.say(w('Tu as fait un tour sur la pelouse, sans parier.', 'You had a wander on the lawn, without a bet.', 'Du bist über den Rasen geschlendert, ohne zu wetten.')));
    const next: Words[] = [];
    if (forgot) next.push(w('La prochaine fois, la guichetière se souviendra du bonjour.', 'Next time, the clerk will remember the bonjour.', 'Beim nächsten Mal erinnert sich die Schalterfrau an das Bonjour.'));
    if (this.window.paid && this.won()) next.push(w('Le Papier racontera l’Arc. Tu sauras qui a vraiment gagné.', "The Papier will tell the Arc. You'll find out who really won.", 'Das Papier erzählt vom Arc. Du erfährst, wer wirklich gewonnen hat.'));
    return { did: did.slice(0, 6), tomorrow: next.slice(0, 3).map((x) => this.say(x)) };
  }
}

const lower = (s: string) => (s ? s[0].toLowerCase() + s.slice(1) : s);
const ordinal = (n: number) => `${n}${n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'}`;
