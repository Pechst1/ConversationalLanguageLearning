/**
 * Le Quartier · a visit: a place the forge built, played without a script.
 *
 * The quai has the season's scene; a forged place has its people and its trade. The visit stands
 * the people the brief names behind their stalls (`SiteSpec.people`), a stallholder behind some of
 * the other stalls, and gives you an errand or two to start from (the primeur, the fromagère under
 * the hall, the brocante). Everything after that is yours: what you say to a stallholder is read
 * by `market-talk.ts`, and lands in the same memory as the quai's choices: what you bought and
 * for how much, the bonjour you forgot, the lamp you haggled down. The stallholders greet you by
 * it the next time; the people in the street talk about it; the stalls call out as you pass.
 *
 * It publishes the `StageUi` the screen already lays out (a talk sheet, a bark, a goal with its
 * dotted way, an end card with what you did), so the screen draws a visit like a scene.
 */
import { Vector3 } from 'three';

import { passerbyArt, personArt } from './cast-art';
import { Troupe } from './cast';
import type { PaperFigure } from './cast';
import type { Hit, Quartier } from './engine';
import { seeded } from './geo';
import { GOODS } from './market';
import type { GoodsKind, StallInfo } from './market';
import { MARKET_BARKS, chipsOf, cryOf, helloOf, memoryKey, newSale, sell, tradeOf } from './market-talk';
import type { Said, Sale, Trade } from './market-talk';
import { Memory, eligible } from './memory';
import type { Effect, Value, Words } from './memory';
import { AMBIANCES } from './palette';
import { STRIDE } from './pace';
import type { SiteBuilt, SitePerson } from './site';
import { BLANK } from './stage';
import type { Cue, Director, Level, Native, SpeechUi, StageUi, Street } from './stage';
import { worldState } from './world';

const w = (fr: string, en: string, de: string): Words => ({ fr, en, de });

/** A stallholder's mood as the avatar kit's faces. */
const FACES: Record<string, string> = { joie: 'joie', malice: 'malice', fache: 'fache', surprise: 'surprise', cold: 'neutre', neutral: 'neutre' };

/** Who calls out from a stall nobody named: the stall, by what it sells. */
const STALLS: Record<GoodsKind, string> = {
  fruits: 'Les fruits',
  legumes: 'Les légumes',
  fleurs: 'Les fleurs',
  olives: 'Les olives',
  fromages: 'Les fromages',
  brocante: 'La brocante',
  livres: 'Les livres',
  vaisselle: 'La vaisselle',
  disques: 'Les disques',
};

interface Keeper {
  /** the troupe's key: `vendeur:<person>` for the people the brief names, `etal:<n>` for the others */
  key: string;
  name: string;
  trade: Trade;
  stall: StallInfo;
  /** where they stand: behind the stall, facing its front */
  stand: Vector3;
  seed: number;
  height: number;
  /** the brief's person, for those it names */
  person?: SitePerson;
  f: PaperFigure | null;
}

export interface VisitOptions {
  level?: Level;
  native?: Native;
  /** what the quarter remembers (shared with the quai) */
  memory?: Memory;
  street?: Street;
  onCue?: (cue: Cue) => void;
}

export class Visit implements Director {
  ui: StageUi = { ...BLANK };
  readonly memory: Memory;
  readonly site: SiteBuilt;
  private listeners = new Set<(ui: StageUi) => void>();
  private native: Native;
  private onCue?: (cue: Cue) => void;
  private street?: Street;
  private troupe: Troupe;
  private sellers: Keeper[] = [];
  private hands: Keeper[] = [];
  private talking: { keeper: Keeper; sale: Sale } | null = null;
  private goal: { keeper: Keeper; to: Vector3 } | null = null;
  private wayAt = 0;
  /** the people you have talked to on this visit */
  private met = new Set<string>();
  private barkAt = 0;
  private barkedBy = new Map<string, number>();
  private lastBark = '';
  private cryAt = 0;
  private stopTick: () => void;
  private stopHit: () => void;
  /** this visit's entries in the memory start here */
  private since = 0;
  private disposed = false;
  readonly day: string;

  constructor(private q: Quartier, opts: VisitOptions = {}) {
    if (!q.site) throw new Error('A visit is to a forged place');
    this.site = q.site;
    this.day = `visit.${q.site.spec.id}`;
    this.native = opts.native ?? 'en';
    this.onCue = opts.onCue;
    this.street = opts.street;
    this.memory = opts.memory ?? new Memory(false);
    this.troupe = new Troupe(q.world, { figure: (key, expression) => this.art(key, expression), item: () => null }, 400);
    q.addTroupe(this.troupe);
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

  private speech(who: string, name: string, words: Words, direction: string | null = null): SpeechUi {
    return { who, char: 'passant', name, text: words.fr, native: words[this.native], direction };
  }

  private remember(effects: Effect | Effect[] | undefined) {
    this.memory.apply(this.day, effects);
  }

  private state(): Record<string, Value> {
    const a = AMBIANCES[this.q.ambiance];
    return { ...this.memory.state(), ...worldState(), night: a.night > 0.5, rain: a.rain };
  }

  /* ---- the people of the place ------------------------------------------------------------ */

  private art(key: string, expression: string) {
    const k = this.keeperOf(key);
    if (k?.person) return personArt(k.seed, k.person.look ?? {}, (FACES[expression] ?? expression) as never, 300);
    return passerbyArt(k ? k.seed : 7, 256);
  }

  private keeperOf(key: string): Keeper | null {
    return this.sellers.find((x) => x.key === key) ?? this.hands.find((x) => x.key === key) ?? null;
  }

  /** Stand everyone behind a stall: the people the brief names at theirs, a keeper at some others. */
  private cast() {
    const site = this.site;
    const taken: StallInfo[] = [];
    const behind = (st: StallInfo) => st.front.clone().addScaledVector(st.facing, -2.45);
    site.spec.people.forEach((p, i) => {
      if (!p.goods) return;
      const hall = p.in ? site.landmarks.find((l) => l.name === p.in) : undefined;
      const pool = (hall ? hall.stalls : site.stalls).filter((x) => x.goods === p.goods && taken.indexOf(x) < 0);
      if (!pool.length) return;
      // the counter nearest the door (in a hall) or where the brief put them (in the street)
      const near = hall && hall.doors.length ? hall.doors[0] : new Vector3(p.pos[0], 0, p.pos[1]);
      pool.sort((a, b) => a.front.distanceTo(near) - b.front.distanceTo(near));
      const stall = pool[0];
      taken.push(stall);
      const R = seeded(p.seed ?? 4000 + i * 97);
      this.sellers.push({ key: `vendeur:${p.key}`, name: p.name.fr, trade: tradeOf(p.goods), stall, stand: behind(stall), seed: p.seed ?? 4000 + i * 97, height: R.range(1.62, 1.84), person: p, f: null });
    });
    // someone behind one stall in four in the street, and here and there under the hall
    const others: StallInfo[] = [];
    site.stalls.forEach((st, i) => {
      if (taken.indexOf(st) < 0 && i % 4 === 1) others.push(st);
    });
    site.landmarks.forEach((l) =>
      l.stalls.forEach((st, i) => {
        if (taken.indexOf(st) < 0 && i % 10 === 4) others.push(st);
      }),
    );
    others.forEach((st, i) => {
      const seed = 9100 + i * 131;
      const R = seeded(seed);
      this.hands.push({ key: `etal:${i}`, name: STALLS[st.goods], trade: tradeOf(st.goods), stall: st, stand: behind(st), seed, height: R.range(1.58, 1.86), f: null });
    });
  }

  /* ---- what the screen calls ------------------------------------------------------------- */

  /** Print the stallholders the brief names (the others come while you read the title card). */
  async prepare() {
    if (!this.sellers.length) this.cast();
    for (let i = 0; i < this.sellers.length && !this.disposed; i++) {
      const s = this.sellers[i];
      try {
        s.f = await this.troupe.add({ key: s.key, height: s.height }, s.stand);
      } catch {
        s.f = null;
      }
    }
    void this.printHands();
  }

  private async printHands() {
    for (let i = 0; i < this.hands.length && !this.disposed; i++) {
      const h = this.hands[i];
      try {
        h.f = await this.troupe.add({ key: h.key, height: h.height }, h.stand);
      } catch {
        h.f = null;
      }
      await new Promise((r) => setTimeout(r, 40));
    }
  }

  /** From the title card: you arrive, and there is an errand to start with. */
  begin() {
    this.since = this.memory.entries.length;
    if (this.memory.places()[this.site.spec.id] !== 'visited') this.remember({ kind: 'place', id: this.site.spec.id, status: 'visited' });
    this.show({ ...BLANK, phase: 'roam', progress: 0 });
    this.nextGoal();
  }

  tap() {
    if (this.ui.aside) this.show({ aside: null });
    else if (this.ui.bark) this.show({ bark: null });
  }

  /** There is no turn to answer on a visit. */
  answer(text: string) {
    void text;
  }

  /** «Y aller»: walk me to the stall. */
  go() {
    const g = this.goal;
    if (g) void this.q.walkTo(g.to, STRIDE);
  }

  /** «Directement»: put me in front of it. */
  skipWalk() {
    const g = this.goal;
    if (!g) return;
    this.q.place(g.to, g.keeper.stand.clone().setY(1.5));
    this.arrive();
  }

  goOn() {
    // nothing waits on a visit
  }

  replay() {
    this.roam();
  }

  /** From the end card: stay a little longer. */
  roam() {
    this.show({ phase: 'roam', recap: null, canLeave: true });
    this.nextGoal();
  }

  /** «Rentrer»: the end card, with what you did here and what it will change. */
  leave() {
    if (this.ui.talk) this.endTalk();
    this.goal = null;
    this.q.stop();
    this.q.showWay(null);
    this.show({ phase: 'end', recap: this.recap(), canLeave: false, goal: null, bark: null, aside: null });
  }

  /** Talk to a stallholder: they greet you by what they remember of you. */
  talkTo(key: string) {
    const k = this.sellers.find((x) => x.key === key);
    if (!k || !k.person) return;
    const state = this.state();
    const sale = newSale(k.person.key, this.site.spec.id, k.person.name, k.trade, k.stall.wares, GOODS[k.stall.goods]);
    const hello = helloOf(sale, state);
    const lines: Said[] = [{ say: hello.say, mood: hello.mood }];
    const taste = k.trade.taste;
    if (hello.taste && taste && k.stall.wares.some((x) => x.label === taste.of)) {
      sale.offered = true;
      if (taste.offer) lines.push({ say: taste.offer, direction: 'holding one out' });
    }
    this.talking = { keeper: k, sale };
    this.met.add(key);
    if (this.goal?.keeper === k) {
      this.goal = null;
      this.q.showWay(null);
    }
    this.q.stop();
    k.f?.hop();
    k.f?.talk(1.2);
    this.face(k, hello.mood);
    if (k.f) {
      const d = this.q.camera.position.distanceTo(k.f.face());
      this.q.look(k.f.face().add(new Vector3(0, -d * 0.26, 0)), 2.4);
    }
    this.onCue?.('paper');
    this.show({
      talk: { who: key, char: 'passant', name: k.name, lines: lines.map((l) => ({ ...this.say(l.say), direction: l.direction ?? null })), you: null, chips: chipsOf(sale, state) },
      bark: null,
      goal: null,
    });
  }

  /** What you say at the stall. */
  talkSay(text: string) {
    const t = this.talking;
    const talk = this.ui.talk;
    if (!t || !talk || !text.trim()) return;
    const r = sell(t.sale, text, this.state());
    this.remember(r.effects);
    const last = r.lines[r.lines.length - 1];
    this.face(t.keeper, r.mood ?? last?.mood);
    t.keeper.f?.talk(0.9 + r.lines.reduce((n, l) => n + l.say.fr.length, 0) * 0.045);
    if (r.effects.some((e) => e.kind === 'journal')) this.onCue?.('paper');
    this.show({
      talk: { ...talk, you: text.trim(), lines: r.lines.map((l) => ({ ...this.say(l.say), direction: l.direction ?? null })), chips: r.done ? [] : chipsOf(t.sale, this.state()) },
    });
    // a goodbye: the sheet stays long enough to read their answer
    if (r.done) {
      window.setTimeout(() => {
        if (this.talking === t && !this.disposed) this.endTalk();
      }, 2600);
    }
  }

  endTalk() {
    const t = this.talking;
    if (!t && !this.ui.talk) return;
    this.talking = null;
    this.q.look(null);
    let bark: StageUi['bark'] = null;
    if (t && (t.sale.bag.length || t.sale.owing !== null)) {
      // you walked off: the bag goes back on the stall, and they call after you
      t.sale.bag = [];
      t.sale.owing = null;
      bark = { ...this.speech(t.keeper.key, t.keeper.name, w('Eh ! Vous oubliez vos courses !', "Hey! You're forgetting your shopping!", 'He! Sie vergessen Ihre Einkäufe!')), at: performance.now() };
      this.remember({ kind: 'fact', key: memoryKey(t.sale, 'walked'), value: true });
    }
    if (t) this.face(t.keeper, 'neutral');
    this.show({ talk: null, bark });
    this.nextGoal();
  }

  /** Someone in the crowd you passed, or tapped. */
  passerby(key: string, tapped: boolean) {
    const now = performance.now();
    const ui = this.ui;
    if (ui.phase !== 'roam' || ui.talk) return;
    if (tapped) this.street?.hop(key);
    if (!tapped && (now - this.barkAt < 8000 || now - (this.barkedBy.get(key) ?? -1e9) < 60000)) return;
    if (tapped && now - (this.barkedBy.get(key) ?? -1e9) < 1500) return;
    const place = this.site.spec.id;
    const list = eligible(
      MARKET_BARKS.filter((b) => !b.place || b.place === place),
      this.state(),
    );
    const pool = list.filter((b) => b.id !== this.lastBark);
    if (!pool.length) return;
    const total = pool.reduce((s, b) => s + 1 + (b.salience ?? 0), 0);
    let roll = Math.random() * total;
    const b = pool.find((x) => (roll -= 1 + (x.salience ?? 0)) < 0) ?? pool[0];
    this.lastBark = b.id;
    this.barkAt = now;
    this.barkedBy.set(key, now);
    this.show({ bark: { ...this.speech(key, 'Quelqu’un', b.say), at: now } });
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
    this.q.removeTroupe(this.troupe);
    this.troupe.dispose();
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
      if (this.sellers.some((x) => x.key === hit.key)) {
        if (this.talking?.keeper.key !== hit.key) {
          if (this.ui.talk) this.endTalk();
          this.talkTo(hit.key);
        }
        return;
      }
      const h = this.hands.find((x) => x.key === hit.key);
      if (h) {
        h.f?.hop();
        this.cry(h, true);
      }
      return;
    }
    if (hit.kind === 'ground') {
      if (this.ui.talk) this.endTalk();
      void this.q.walkTo(hit.point, STRIDE);
    }
  }

  private tick() {
    const now = performance.now();
    const roaming = this.ui.phase === 'roam' && !this.ui.talk;
    const g = this.goal;
    if (g && roaming) {
      if (now - this.wayAt > 900 && !this.q.walking) {
        this.wayAt = now;
        this.q.showWay(g.to);
      }
      if (Math.hypot(this.q.feet.x - g.to.x, this.q.feet.z - g.to.z) < 1.5) this.arrive();
    }
    if (this.ui.bark && now - this.ui.bark.at > 6500) this.show({ bark: null });
    if (roaming !== this.ui.canLeave) this.show({ canLeave: roaming });
    // the market calls out: the nearest stall, now and then
    if (roaming && !this.ui.bark && now - this.cryAt > 11000) {
      const feet = this.q.feet;
      let best: Keeper | null = null;
      let bestD = 9;
      this.sellers.concat(this.hands).forEach((k) => {
        if (!k.f || this.met.has(k.key)) return;
        const d = Math.hypot(k.stand.x - feet.x, k.stand.z - feet.z);
        if (d < bestD) {
          best = k;
          bestD = d;
        }
      });
      if (best) {
        this.cryAt = now;
        this.cry(best, false);
      }
    }
  }

  /** At the stall the errand led to: they speak first. */
  private arrive() {
    const g = this.goal;
    if (!g) return;
    this.goal = null;
    this.q.showWay(null);
    this.q.stop();
    this.talkTo(g.keeper.key);
  }

  private nextGoal() {
    const next = this.sellers.find((k) => k.person?.goal && !this.met.has(k.key));
    if (!next || !next.person?.goal) {
      this.goal = null;
      this.q.showWay(null);
      this.show({ goal: null });
      return;
    }
    this.goal = { keeper: next, to: next.stall.front.clone() };
    this.wayAt = 0;
    this.show({ goal: { label: next.person.goal.fr, native: next.person.goal[this.native] } });
  }

  private cry(k: Keeper, tapped: boolean) {
    const now = performance.now();
    if (!tapped && now - this.barkAt < 4000) return;
    k.f?.talk(1.5);
    this.barkAt = now;
    this.show({ bark: { ...this.speech(k.key, k.name, cryOf(k.trade, k.stall.wares, Math.random())), at: now } });
  }

  private face(k: Keeper, mood: string | undefined) {
    if (!k.f || !k.person) return;
    const expression = FACES[mood ?? 'neutral'] ?? 'neutre';
    if (expression !== k.f.expression) void this.troupe.face(k.key, expression);
  }

  /** The end card: what you did on this visit, and what the place will remember. */
  private recap(): StageUi['recap'] {
    const mine = this.memory.entries.slice(this.since).filter((l) => l.day === this.day);
    const did: Array<{ text: string; native: string }> = [];
    const facts: Record<string, Value> = {};
    mine.forEach((l) => {
      const e = l.effect;
      if (e.kind === 'journal') did.push(this.say(e.words));
      else if (e.kind === 'learn') did.push(this.say(w(`Tu as appris : ${lower(e.words.fr)}`, `You learned: ${lower(e.words.en)}`, `Du hast erfahren: ${e.words.de}`)));
      else if (e.kind === 'fact') facts[e.key] = e.value;
    });
    if (!did.length) did.push(this.say(w('Tu as fait un tour, sans rien acheter.', 'You had a look round, without buying anything.', 'Du hast dich umgesehen, ohne etwas zu kaufen.')));
    const next: Words[] = [];
    this.sellers.forEach((k) => {
      if (!k.person) return;
      const key = (what: string) => memoryKey({ place: this.site.spec.id, who: k.person!.key }, what);
      const n = k.person.name;
      const fr = lower(n.fr);
      const de = n.de.replace(/^(Der|Die|Das) /, (m) => m.toLowerCase());
      if (facts[key('bonjour')] === 'forgot') next.push(w(`La prochaine fois, ${fr} se souviendra du bonjour.`, `Next time, ${lower(n.en)} will remember the bonjour.`, `Beim nächsten Mal erinnert sich ${de} an das Bonjour.`));
      else if (facts[key('haggled')]) next.push(w(`${n.fr} se souviendra de ton marchandage.`, `${n.en} will remember your haggling.`, `${n.de} wird sich an dein Feilschen erinnern.`));
      else if (facts[key('bought')]) next.push(w(`La prochaine fois, ${fr} te reconnaîtra.`, `Next time, ${lower(n.en)} will recognise you.`, `Beim nächsten Mal erkennt ${de} dich wieder.`));
      if (facts[key('tu')]) next.push(w(`Tu as tutoyé ${fr}. On s'en souviendra.`, `You said tu to ${lower(n.en)}. That will be remembered.`, `Du hast ${de.replace(/^der /, 'den ')} geduzt. Das bleibt hängen.`));
    });
    return { did: did.slice(0, 6), tomorrow: next.slice(0, 3).map((x) => this.say(x)) };
  }
}

const lower = (s: string) => (s ? s[0].toLowerCase() + s.slice(1) : s);
