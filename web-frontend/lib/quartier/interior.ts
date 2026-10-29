/**
 * Le Quartier · a room of the season, played (`room.ts` builds it).
 *
 * A street the forge built has its people and their trade (`visit.ts`); a room has what the canon
 * gives the place. The stairwell of Le Mistral's building has its push-button light, which lights
 * the stairs for a while and clicks off, the flight up to the first floor, and the door with its
 * brass «1», which the story opens once (T1 R2) and shuts again (R3): nobody goes in before T2.
 * The interior plays that. You come in from the street into the dark, press the orange button,
 * climb, and the door opens onto Odile's kitchen in the street light through the slats; it shuts
 * again, and the light goes out on it. What it remembers is keyed to the room: a door the story
 * opens once stays shut on your next visit.
 *
 * The season's scenes will be played in a room by the stage; until then this is what a room
 * offers. It publishes the `StageUi` a visit does, so the screen lays it out the same way.
 */
import { Vector3 } from 'three';

import type { Hit, Quartier } from './engine';
import { Memory } from './memory';
import type { Words } from './memory';
import { STRIDE } from './pace';
import type { RoomBuilt } from './room';
import { BLANK } from './stage';
import type { Cue, Din, Director, Level, Native, StageUi, Street } from './stage';

const w = (fr: string, en: string, de: string): Words => ({ fr, en, de });

const LINES = {
  arrive: w('Après la fermeture. L’escalier, à côté du café.', 'After closing. The stairwell, next to the café.', 'Nach Feierabend. Das Treppenhaus neben dem Café.'),
  light: w('Allume la lumière', 'Turn on the light', 'Mach das Licht an'),
  relight: w('Rallume la lumière', 'Turn the light back on', 'Mach das Licht wieder an'),
  climb: w('Monte au premier', 'Go up to the first floor', 'Geh in den ersten Stock'),
  door: w('Ouvre la porte', 'Open the door', 'Öffne die Tür'),
  dark: w('Il fait noir : rallume d’abord.', 'It is dark: turn the light back on first.', 'Es ist dunkel: mach erst das Licht wieder an.'),
  after: w('Personne n’entre. Pas encore.', 'Nobody goes in. Not yet.', 'Niemand geht hinein. Noch nicht.'),
  shut: w('La porte reste fermée. Pas avant mercredi.', 'The door stays shut. Not before Wednesday.', 'Die Tür bleibt zu. Nicht vor Mittwoch.'),
  lit: w('Tu as allumé la minuterie.', 'You turned on the stair light.', 'Du hast das Treppenlicht angemacht.'),
  climbed: w('Tu as monté l’escalier jusqu’au premier.', 'You climbed the stairs to the first floor.', 'Du bist die Treppe in den ersten Stock hinaufgestiegen.'),
  opened: w('Tu as ouvert la porte du «1», puis tu l’as refermée.', 'You opened the door with the «1», then shut it again.', 'Du hast die Tür mit der «1» geöffnet und wieder geschlossen.'),
  waited: w('Tu as attendu en bas de l’escalier, dans le noir.', 'You waited at the foot of the stairs, in the dark.', 'Du hast unten an der Treppe im Dunkeln gewartet.'),
  until: w('La porte restera fermée jusqu’à mercredi.', 'The door will stay shut until Wednesday.', 'Die Tür bleibt bis Mittwoch zu.'),
};

/** What you are on your way to do: the light, the flight, the door, nothing more. */
type Step = 'light' | 'climb' | 'door' | 'done';

export interface InteriorOptions {
  level?: Level;
  native?: Native;
  /** what the quarter remembers (shared with the quai) */
  memory?: Memory;
  onCue?: (cue: Cue) => void;
}

export class Interior implements Director {
  ui: StageUi = { ...BLANK };
  readonly memory: Memory;
  readonly room: RoomBuilt;
  readonly day: string;
  private listeners = new Set<(ui: StageUi) => void>();
  private native: Native;
  private onCue?: (cue: Cue) => void;
  private step: Step = 'light';
  /** when the circuit goes out (performance.now()); 0 while it is out */
  private litUntil = 0;
  private tickAt = 0;
  private goal: { to: Vector3; switchKey: string | null } | null = null;
  private wayAt = 0;
  /** the door's moment is playing: the room waits */
  private busy = false;
  private did = new Set<'lit' | 'climbed' | 'opened'>();
  private tapWait: (() => void) | null = null;
  /** the latest turn of your head (`face`): an earlier one does not let go of it */
  private faced = 0;
  /** the lens is open for the door (`faceDoor`) */
  private wide = false;
  private timers = new Set<number>();
  private stopTick: () => void;
  private stopHit: () => void;
  private disposed = false;

  constructor(private q: Quartier, opts: InteriorOptions = {}) {
    if (!q.room) throw new Error('An interior is a room of the season');
    this.room = q.room;
    this.day = `room.${q.room.spec.id}`;
    this.native = opts.native ?? 'en';
    this.onCue = opts.onCue;
    this.memory = opts.memory ?? new Memory(false);
    this.stopTick = q.onTick(() => this.tick());
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
    void street;
  }

  private show(patch: Partial<StageUi>) {
    this.ui = { ...this.ui, ...patch };
    this.listeners.forEach((fn) => fn(this.ui));
  }

  private say(words: Words) {
    return { text: words.fr, native: words[this.native] };
  }

  /** The door the story opens once, its spot and where you stand before it and in it. */
  private get door() {
    return this.room.openings.find((o) => o.opens === 'once') ?? null;
  }

  private doorKey(key: string) {
    return `${this.room.spec.id}.${key}`;
  }

  /** Has the door been opened already (this visit or an earlier one)? */
  private opened() {
    const d = this.door;
    return Boolean(d && this.memory.state()[this.doorKey(d.key)] === 'opened');
  }

  private mark(key: string, fallback: Vector3) {
    return this.room.marks[key]?.clone() ?? fallback.clone();
  }

  /** The room is dark when you come in; its buttons glow, and a tap on one is a press. */
  async prepare() {
    this.room.switches.forEach((s) => this.q.addSpot({ id: `switch:${s.key}`, pos: s.at.clone(), radius: 0.3, enabled: true }));
    this.room.openings.filter((o) => o.opens === 'once').forEach((o) => this.q.addSpot({ id: `door:${o.key}`, pos: o.centre.clone(), radius: 0.55, enabled: true }));
    this.q.setRoomLight(0);
  }

  begin() {
    if (this.memory.places()[this.room.spec.id] !== 'visited') this.memory.apply(this.day, { kind: 'place', id: this.room.spec.id, status: 'visited' });
    this.step = this.opened() ? 'done' : 'light';
    this.show({ ...BLANK, phase: 'roam', canLeave: true, caption: this.say(LINES.arrive) });
    this.nextGoal();
  }

  tap() {
    if (this.tapWait) {
      const go = this.tapWait;
      this.tapWait = null;
      go();
      return;
    }
    if (this.ui.caption) this.show({ caption: null });
    else if (this.ui.aside) this.show({ aside: null });
  }

  answer(text: string) {
    void text;
  }

  /** «Y aller»: walk me there, and turn me to what I came for (the button, the door). */
  go() {
    const g = this.goal;
    if (!g) return;
    void this.reach(g.to).then((there) => {
      if (!there || this.goal !== g || this.busy) return;
      const s = g.switchKey ? this.room.switches.find((x) => x.key === g.switchKey) : null;
      if (s) this.face(s.at);
      else if (this.step === 'door') this.faceDoor();
    });
  }

  /** «Directement»: put me there, and do it (press the button, open the door). */
  skipWalk() {
    const g = this.goal;
    if (!g || this.busy) return;
    if (g.switchKey) {
      const s = this.room.switches.find((x) => x.key === g.switchKey);
      this.q.place(g.to, s ? s.at.clone() : undefined);
      this.press();
    } else if (this.step === 'door') {
      void this.openDoor();
    } else {
      const d = this.door;
      this.q.place(g.to, d ? d.centre.clone() : undefined);
    }
  }

  goOn() {
    // nothing waits in a room
  }

  /** Back to the street door, in the dark. */
  replay() {
    if (this.busy) return;
    this.q.place(this.room.start.pos, this.room.start.look);
    this.litUntil = 0;
    this.q.setRoomLight(0);
    this.begin();
  }

  /** From the end card: stay a little longer. */
  roam() {
    this.show({ phase: 'roam', recap: null, canLeave: true });
    this.nextGoal();
  }

  /** «Rentrer»: the end card, with what you did here. */
  leave() {
    if (this.busy) return;
    this.goal = null;
    this.q.stop();
    this.q.showWay(null);
    const did = (['lit', 'climbed', 'opened'] as const).filter((k) => this.did.has(k)).map((k) => this.say(LINES[k]));
    this.show({
      phase: 'end',
      canLeave: false,
      goal: null,
      caption: null,
      aside: null,
      recap: { did: did.length ? did : [this.say(LINES.waited)], tomorrow: this.did.has('opened') ? [this.say(LINES.until)] : [] },
    });
  }

  talkTo(key: string) {
    void key;
  }

  talkSay(text: string) {
    void text;
  }

  endTalk() {
    // nobody to talk to in a stairwell after closing
  }

  passerby(key: string, tapped: boolean) {
    void key;
    void tapped;
  }

  phoneReply(text: string) {
    void text;
  }

  closePhone() {
    this.show({ phone: null });
  }

  /** A stairwell after closing: no murmur, nobody about. */
  din(): Din {
    return { crowd: 0, hooves: 0 };
  }

  dispose() {
    this.disposed = true;
    this.timers.forEach((t) => window.clearTimeout(t));
    this.timers.clear();
    this.tapWait = null;
    this.stopTick();
    this.stopHit();
    this.listeners.clear();
  }

  /* ---- the light ------------------------------------------------------------------------------ */

  /** A press on a button of the circuit: the clunk, the light, the clockwork ticking down. */
  private press() {
    const seconds = Object.values(this.room.spec.timers)[0] ?? 50;
    const now = performance.now();
    if (!this.litUntil) this.q.setRoomLight(1);
    this.onCue?.('switch');
    this.litUntil = now + seconds * 1000;
    this.tickAt = now;
    this.did.add('lit');
    if (this.step === 'light') this.step = 'climb';
    this.nextGoal();
  }

  /** The minuterie runs out: the relay clacks, and the stairwell is dark. */
  private out() {
    this.litUntil = 0;
    this.q.setRoomLight(0);
    this.onCue?.('switch');
    this.nextGoal();
  }

  /* ---- the door ------------------------------------------------------------------------------- */

  /**
   * The door opens once (T1 R2): the key turns, it swings onto the dark kitchen and the street
   * light through the slats, you look in from the threshold; it shuts again (R3), and soon after
   * the light goes out. Nobody goes in.
   */
  private async openDoor() {
    const d = this.door;
    if (!d || this.busy) return;
    if (this.opened()) {
      this.show({ caption: this.say(LINES.shut) });
      return;
    }
    if (!this.litUntil) {
      this.show({ caption: this.say(LINES.dark) });
      return;
    }
    this.busy = true;
    this.goal = null;
    this.q.stop();
    this.q.showWay(null);
    const before = this.mark('door', d.front);
    const sill = this.mark('threshold', d.front);
    const inside = this.mark('inside', d.centre);
    // the light holds while the door is open
    this.litUntil = Math.max(this.litUntil, performance.now() + 14000);
    this.show({ phase: 'scene', silent: true, caption: null, aside: null, goal: null, canLeave: false, beat: 'door.before', progress: 0.2 });
    this.q.frozen = true;
    this.q.place(before, d.centre.clone());
    this.q.look(d.centre.clone(), 5);
    if (!(await this.wait(800))) return;
    this.onCue?.('key');
    this.show({ beat: 'door.key', progress: 0.35 });
    if (!(await this.wait(1100))) return;
    this.onCue?.('door');
    this.q.openDoor(true, d.key);
    this.show({ beat: 'door.open', progress: 0.5 });
    if (!(await this.wait(1500))) return;
    // R2: from the threshold, the room and your hand on the frame
    this.q.place(sill, inside);
    this.q.look(inside, 4);
    this.lensAcross(46);
    this.show({ beat: 'door.look', waitingTap: true, progress: 0.65 });
    if (!(await this.wait(5200, true))) return;
    // R3: the door closing again, from where you stood before it, looking in: you have not gone
    // in (the threshold is where the leaf shuts, so you are back on the landing first)
    this.show({ beat: 'door.close', waitingTap: false, progress: 0.8 });
    const away = d.front.clone().sub(d.centre).setY(0).normalize();
    const through = d.centre.clone().addScaledVector(away, -3).setY(d.centre.y - 0.35);
    this.q.place(before, through);
    this.q.look(through, 4);
    this.q.lens(60);
    this.wide = false;
    this.q.openDoor(false, d.key);
    if (!(await this.wait(1500))) return;
    this.onCue?.('door');
    if (!(await this.wait(600))) return;
    this.memory.apply(this.day, [
      { kind: 'fact', key: this.doorKey(d.key), value: 'opened' },
      { kind: 'journal', words: LINES.opened },
    ]);
    this.did.add('opened');
    this.step = 'done';
    this.q.look(d.centre.clone(), 3);
    // and the light goes out on it
    this.litUntil = Math.min(this.litUntil, performance.now() + 1700);
    this.show({ beat: 'door.shut', progress: 0.95 });
    if (!(await this.wait(2600))) return;
    this.q.look(null);
    this.q.frozen = false;
    this.busy = false;
    this.show({ phase: 'roam', silent: false, beat: null, progress: 1, canLeave: true, caption: this.say(LINES.after) });
    this.nextGoal();
  }

  /** Wait, or until a tap if `tappable`; false if the room was closed meanwhile. */
  private wait(ms: number, tappable = false): Promise<boolean> {
    return new Promise((resolve) => {
      const t = window.setTimeout(() => {
        this.timers.delete(t);
        if (tappable) this.tapWait = null;
        resolve(!this.disposed);
      }, ms);
      this.timers.add(t);
      if (tappable) {
        this.tapWait = () => {
          window.clearTimeout(t);
          this.timers.delete(t);
          resolve(!this.disposed);
        };
      }
    });
  }

  /* ---- the frame ------------------------------------------------------------------------------ */

  private hit(hit: Hit) {
    if (this.ui.phase !== 'roam' || this.busy) return;
    if (hit.kind === 'spot') {
      if (hit.id.indexOf('switch:') === 0) {
        const s = this.room.switches.find((x) => `switch:${x.key}` === hit.id);
        if (!s) return;
        // a button out of reach: walk to it, then press
        const stand = this.standBy(s.at, s.key);
        if (Math.hypot(this.q.feet.x - stand.x, this.q.feet.z - stand.z) > 1.6) {
          void this.reach(stand).then((there) => there && !this.busy && this.press());
        } else this.press();
        return;
      }
      if (hit.id.indexOf('door:') === 0) {
        const d = this.door;
        if (!d) return;
        const before = this.mark('door', d.front);
        if (Math.hypot(this.q.feet.x - before.x, this.q.feet.z - before.z) > 1.8) {
          void this.reach(before).then((there) => there && void this.openDoor());
        } else void this.openDoor();
      }
      return;
    }
    if (hit.kind === 'ground') void this.q.walkTo(hit.point, STRIDE);
  }

  private tick() {
    const now = performance.now();
    if (this.litUntil) {
      if (now > this.litUntil) this.out();
      else if (now - this.tickAt > 1000) {
        this.tickAt = now;
        this.onCue?.('tick');
      }
    }
    const roaming = this.ui.phase === 'roam' && !this.busy;
    const g = this.goal;
    if (g && roaming) {
      if (now - this.wayAt > 900 && !this.q.walking) {
        this.wayAt = now;
        this.q.showWay(g.to);
      }
      // up on the landing: the door is next, and you turn to it (R1: a door with a brass «1»)
      if (this.step === 'climb' && !g.switchKey && Math.hypot(this.q.feet.x - g.to.x, this.q.feet.z - g.to.z) < 1.4 && Math.abs(this.q.feet.y - g.to.y) < 0.4) {
        this.did.add('climbed');
        this.step = 'door';
        this.nextGoal();
        this.faceDoor();
      }
    }
    // the lens opened for the door closes again once you walk off the landing
    if (this.wide && !this.busy) {
      const landing = this.mark('landing', this.room.start.pos);
      if (Math.hypot(this.q.feet.x - landing.x, this.q.feet.z - landing.z) > 1.4 || Math.abs(this.q.feet.y - landing.y) > 0.4) {
        this.wide = false;
        this.q.lens(60);
      }
    }
    if (roaming !== this.ui.canLeave && this.ui.phase === 'roam') this.show({ canLeave: roaming });
  }

  /**
   * A lens that takes in `deg` of the room across, on any screen: a phone held upright sees less
   * across than a square, so R2's coat, clock and calendar need a wider one there.
   */
  private lensAcross(deg: number) {
    const aspect = Math.max(0.3, this.q.camera.aspect);
    const fov = (2 * Math.atan(Math.tan((deg * Math.PI) / 360) / aspect) * 180) / Math.PI;
    this.q.lens(Math.min(84, Math.max(52, fov)));
  }

  /**
   * Turn your head to something for a moment, then let your eyes go where you like. Not while the
   * last steps are still walking you there (let go, the head would turn back to the way), nor
   * before it has come round on a slow phone (a few seconds at most).
   */
  private face(at: Vector3 | undefined) {
    if (!at) return;
    const mine = ++this.faced;
    const target = at.clone();
    this.q.look(target, 3);
    const letGo = (ms: number, tries: number) => {
      const t = window.setTimeout(() => {
        this.timers.delete(t);
        if (mine !== this.faced) return;
        if ((this.q.walking || !this.facing(target)) && tries > 0) letGo(400, tries - 1);
        else if (!this.busy) this.q.look(null);
      }, ms);
      this.timers.add(t);
    };
    letGo(1600, 10);
  }

  /**
   * Turn to the door with its «1», the whole of it: the landing is too shallow to step back from
   * it, so the lens opens as for R2 (an upright phone sees little across) until you walk off.
   */
  private faceDoor() {
    this.face(this.door?.centre);
    this.lensAcross(46);
    this.wide = true;
  }

  /** Is your head turned to `at`, within a few degrees? */
  private facing(at: Vector3) {
    const cam = this.q.camera;
    const want = at.clone().sub(cam.position).normalize();
    return cam.getWorldDirection(new Vector3()).dot(want) > Math.cos(0.05);
  }

  /**
   * Walk there; true only once you stand there, in the room as you left it. A tap elsewhere or
   * the thumb on the way ends the walk too, and the engine says true then as well: that is not
   * arriving, and nothing is pressed or opened from afar.
   */
  private async reach(to: Vector3) {
    const end = this.q.nav.nearest(to.x, to.z, 4);
    const ok = await this.q.walkTo(to, STRIDE);
    return ok && !this.disposed && this.ui.phase === 'roam' && end !== null && Math.hypot(this.q.feet.x - end[0], this.q.feet.z - end[1]) < 0.1;
  }

  /** Where you stand to press a button: a little out from the wall, on the floor. */
  private standBy(at: Vector3, key: string) {
    const s = this.room.switches.find((x) => x.key === key);
    const f = s ? s.facing : new Vector3(0, 0, 1);
    const p = new Vector3(at.x + f.x * 0.55, 0, at.z + f.z * 0.55);
    p.y = this.q.nav.heightAt(p.x, p.z);
    return p;
  }

  /** The nearest button, by the way you would walk (near enough: as the crow flies, and on your floor first). */
  private nearestSwitch() {
    const feet = this.q.feet;
    let best: { key: string; at: Vector3; d: number } | null = null;
    for (const s of this.room.switches) {
      const stand = this.standBy(s.at, s.key);
      const d = Math.hypot(stand.x - feet.x, stand.z - feet.z) + Math.abs(stand.y - feet.y) * 4;
      if (!best || d < best.d) best = { key: s.key, at: stand, d };
    }
    return best;
  }

  private nextGoal() {
    if (this.busy) return;
    let label: Words | null = null;
    let goal: Interior['goal'] = null;
    const sw = this.nearestSwitch();
    if (this.step !== 'done' && !this.litUntil && sw) {
      label = this.did.has('lit') ? LINES.relight : LINES.light;
      goal = { to: sw.at, switchKey: sw.key };
    } else if (this.step === 'climb') {
      label = LINES.climb;
      goal = { to: this.mark('landing', this.room.start.pos), switchKey: null };
    } else if (this.step === 'door') {
      const d = this.door;
      if (d) {
        label = LINES.door;
        goal = { to: this.mark('door', d.front), switchKey: null };
      }
    }
    this.goal = goal;
    this.wayAt = 0;
    if (!goal) this.q.showWay(null);
    this.show({ goal: label ? { label: label.fr, native: label[this.native] } : null });
  }
}
