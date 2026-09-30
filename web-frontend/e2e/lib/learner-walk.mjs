// One learner, one day at a time, on a phone-sized page. The class reads the screen,
// does what a learner would do, takes screenshots (light + dark) on every new screen
// and runs the learner-clarity assertions as it goes.
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { snapshot, sleep } from './driver.mjs';
import { englishWords, PENDING_VERDICT, SERVER_BANNER } from './assertions.mjs';

const STEP_RE = /(Step \d+ of \d+|Schritt \d+ von \d+|Étape \d+ sur \d+)/;
const REPLIES = ['Oui, je peux vous aider samedi.', 'Merci, à samedi !', 'Avec plaisir, à bientôt.', 'D’accord, je viens.'];
const FREE = 'Je voudrais un café, s’il vous plaît.';

export class LearnerWalk {
  constructor({ page, findings, outDir, lang, level, stack, shots, scale }) {
    Object.assign(this, { page, findings, outDir, lang, level, stack, shots, scale });
    this.day = 0;
    this.seq = 0;
    this.kindsSeen = new Set();
    this.replies = 0;
    mkdirSync(outDir, { recursive: true });
    this.timelines = new Map();
  }

  where(extra = {}) {
    return { lang: this.lang, level: this.level, day: this.day, ...extra };
  }

  async shoot(kind, note = '') {
    this.seq += 1;
    const base = `d${this.day}-${String(this.seq).padStart(2, '0')}-${kind}`;
    const files = {};
    for (const scheme of ['light', 'dark']) {
      await this.page.emulateMedia({ colorScheme: scheme });
      await sleep(120);
      const file = path.join(this.outDir, `${base}-${scheme}.png`);
      await this.page.screenshot({ path: file, animations: 'disabled' });
      files[scheme] = path.relative(this.shots.root, file);
    }
    await this.page.emulateMedia({ colorScheme: 'light' });
    this.shots.list.push({ lang: this.lang, level: this.level, day: this.day, kind, note, ...files });
    return files.light;
  }

  classify(s) {
    if (s.recap) return 'recap';
    if (s.homeDone) return 'home-done';
    if (s.reader.length) return 'reader';
    if (s.thread) return 'thread';
    if (s.dictation) return 'dictation';
    if (s.dataStep.includes('read')) return 'read';
    if (s.match) return 'match';
    if (s.tilesBox) return 'tiles';
    if (s.choices || s.whoSaid) return 'choice';
    if (s.dataStep.includes('rule')) return 'rule';
    if (s.forgeStep) return 'forge-offer';
    if (s.textarea) return 'field';
    // The cast intro, by its own element: a «guillemet» in a name or a teaser is not it.
    if (s.castIntro || /^(Cast|Characters|Personnages|Figuren|Die Figuren)\b/i.test(s.text.slice(0, 60))) return 'cast';
    return 'screen';
  }

  async newSession(context) {
    // A fresh page per learner; runtime errors and server errors are findings.
    const page = await context.newPage();
    this.page = page;
    page.on('pageerror', (e) => this.findings.check('no-uncaught-error', false, String(e.message).slice(0, 200), this.where()));
    page.on('response', (r) => {
      const st = r.status();
      if (st >= 500 && r.url().includes('/api/')) {
        this.findings.check('no-server-error', false, `${st} ${r.request().method()} ${new URL(r.url()).pathname}`, this.where());
      }
    });
    return page;
  }

  /** Read-only page checks that hold on every screen. */
  pageChecks(s, kind) {
    const w = this.where({ kind });
    this.findings.check('no-horizontal-scroll', s.scrollW <= s.innerW + 1, `scrollWidth ${s.scrollW} > ${s.innerW}`, w);
    if (this.level.startsWith('B') || this.level.startsWith('C')) {
      const eng = englishWords(s.nonFrText);
      this.findings.check('no-english-on-french-b1', eng.length < 3, `English chrome on a French screen: ${eng.slice(0, 8).join(', ')} — «${s.nonFrText.slice(0, 120)}»`, w);
      const englishLabels = /present condition|future result|imperative result|background\/habit|bounded event|article changes/i;
      this.findings.check('b1-classification-labels-are-french', !englishLabels.test(s.text), 'Classification labels and corrections must be French, including inside lang="fr".', w);
    }
  }

  async stepPass(s, kind, state) {
    const w = this.where({ kind });
    // Drill goal line (WP-103 T3): a learner must be told what to produce.
    if (['tiles', 'choice', 'match', 'dictation', 'field', 'read'].includes(kind) && !s.thread) {
      const goalText = [...s.goal, ...s.bodyLg, ...s.headline].join(' ').trim();
      this.findings.check('drill-shows-a-goal', goalText.length >= 8, `no goal/instruction on a ${kind} drill: «${s.text.slice(0, 100)}»`, w);
      if (kind === 'tiles') this.findings.check('tiles-drill-goal-line', s.goal.length > 0, `word bank without a [data-goal] line: «${s.text.slice(0, 100)}»`, w);
    }
    // A way forward on every screen.
    const forward = s.buttons.some((b) => !b.disabled && b.text && !/^(Pause|Stop|Hint|Translation|Show the answer|Tipp|Übersetzung|Indice|Traduction|Leave|Previous)/i.test(b.text));
    const inputs = s.choices || s.tiles || s.textarea || s.match || s.dictation;
    if (!forward && !inputs && !s.buttons.some((b) => b.disabled)) {
      this.findings.check('a-way-forward', false, `nothing to do on «${s.text.slice(0, 100)}»`, w);
    }
    // Connection banner while typing.
    if (state.typing) {
      const banner = s.connection.length > 0 || SERVER_BANNER.test(s.text);
      this.findings.check('no-server-banner-while-typing', !banner, `banner while typing: «${s.text.slice(0, 160)}»`, w);
    }
  }

  trackVerdicts(s, kind) {
    // One verdict per question: a conversation is one question for its whole length;
    // any other item is identified by the text it showed before it was answered.
    const hasVerdict = s.graded.length + s.epFeedback.length > 0;
    if (!hasVerdict) this.questionSig = s.text.slice(0, 140);
    const step = (s.text.match(STEP_RE) || ['none'])[0];
    const key = kind === 'thread' ? `thread ${step}` : `${step} ${this.questionSig || ''}`;
    const t = this.timelines.get(`${this.day}:${key}`) || { states: [], pending: false };
    for (const g of s.graded) if (t.states[t.states.length - 1] !== g.state) t.states.push(g.state);
    for (const f of s.epFeedback) if (t.states[t.states.length - 1] !== f.verdict) t.states.push(f.verdict);
    if (PENDING_VERDICT.test(s.text)) t.pending = true;
    this.timelines.set(`${this.day}:${key}`, t);
    return t;
  }

  finishTimelines() {
    for (const [k, t] of this.timelines) {
      const distinct = t.states.filter((x) => x && x !== 'unscored');
      const flips = distinct.some((x, i) => i > 0 && x !== distinct[i - 1]);
      this.findings.check('one-verdict-never-reversed', !flips, `verdict changed on ${k}: ${distinct.join(' → ')}`, this.where());
    }
    this.timelines.clear();
  }

  async typeInto(locator, text, state) {
    await locator.click();
    await locator.fill('');
    const half = Math.floor(text.length / 2);
    state.typing = true;
    await locator.pressSequentially(text.slice(0, half), { delay: 25 });
    let s = await snapshot(this.page);
    this.findings.check('no-server-banner-while-typing', !(s.connection.length || SERVER_BANNER.test(s.text)), `banner mid-typing: «${s.text.slice(0, 160)}»`, this.where({ kind: 'typing' }));
    await locator.pressSequentially(text.slice(half), { delay: 25 });
    s = await snapshot(this.page);
    this.findings.check('no-server-banner-while-typing', !(s.connection.length || SERVER_BANNER.test(s.text)), `banner after typing: «${s.text.slice(0, 160)}»`, this.where({ kind: 'typing' }));
    state.typing = false;
  }

  /** Reader: the Next button must never move between panels. */
  readerChecks(s, state) {
    const btn = s.reader.find((r) => !r.disabled && !/^(Prev|Zur|Préc)/i.test(r.text) && r.w > 0) || s.reader[s.reader.length - 1];
    if (!btn) return;
    if (!state.readerBox) state.readerBox = btn;
    const b0 = state.readerBox;
    const moved = ['x', 'y', 'w', 'h'].some((k) => Math.abs(b0[k] - btn[k]) > 1);
    this.findings.check('reader-next-never-moves', !moved, `Next moved from ${JSON.stringify(b0)} to ${JSON.stringify(btn)} («${btn.text}»)`, this.where({ kind: 'reader' }));
  }

  async act(s, kind, state) {
    const page = this.page;
    if (kind === 'reader') {
      const next = page.locator('.fr-next:not([disabled])').last();
      if (await next.count()) { await next.click({ timeout: 3000 }).catch(() => {}); return true; }
      return false;
    }
    if (s.graded.length || s.epFeedback.length) {
      const prim = page.locator('.av2-graded .av2-btn, .av2-btn--primary:not([disabled])').last();
      if (await prim.count()) { await prim.click({ timeout: 3000 }).catch(() => {}); return true; }
    }
    const enabledChoice = page.locator('.av2-choice:not([disabled])');
    if (await enabledChoice.count()) {
      const n = await enabledChoice.count();
      await enabledChoice.nth((this.day + state.itemIndex) % n).click({ timeout: 3000 }).catch(() => {});
      state.itemIndex += 1;
      await sleep(150);
      const check = page.locator('.av2-btn--primary:not([disabled])').first();
      if (await check.count()) await check.click({ timeout: 3000 }).catch(() => {});
      return true;
    }
    // «Qui a dit ça ?»: the faces are cards, not .av2-choice buttons.
    const faces = page.locator('.av2-who-said__card:not([disabled])');
    if (await faces.count()) {
      const n = await faces.count();
      await faces.nth((this.day + state.itemIndex) % n).click({ timeout: 3000 }).catch(() => {});
      state.itemIndex += 1;
      await sleep(150);
      const check = page.locator('.av2-btn--primary:not([disabled])').first();
      if (await check.count()) await check.click({ timeout: 3000 }).catch(() => {});
      return true;
    }
    const bank = page.locator('.av2-tiles__bank button.av2-tile:not([disabled])');
    if (await bank.count()) {
      for (let i = 0; i < 14 && (await bank.count()); i += 1) {
        await bank.first().click({ timeout: 2000 }).catch(() => {});
        await sleep(80);
      }
      const check = page.locator('.av2-btn--primary:not([disabled])').first();
      if (await check.count()) await check.click({ timeout: 3000 }).catch(() => {});
      return true;
    }
    const cards = page.locator('.av2-match__card:not([disabled])');
    if (await cards.count()) {
      // Pairs: the first idle French card, tried against each idle meaning until it
      // is matched (keyed: a wrong pair flashes and returns to idle).
      const french = page.locator('.av2-match__col').nth(0).locator('.av2-match__card[data-state="idle"]');
      const meanings = page.locator('.av2-match__col').nth(1).locator('.av2-match__card[data-state="idle"]');
      for (let round = 0; round < 12 && (await french.count()); round += 1) {
        const before = await french.count();
        const n = await meanings.count();
        let paired = false;
        for (let j = 0; j < n && !paired; j += 1) {
          await french.first().click({ timeout: 1500 }).catch(() => {});
          await meanings.nth(j).click({ timeout: 1500 }).catch(() => {});
          await sleep(600);
          paired = (await french.count()) < before;
        }
        if (!paired) break;
      }
      return true;
    }
    if (s.fieldEnabled) {
      const field = page.locator('textarea:not([disabled]), input[type=text]:not([disabled])').first();
      const text = kind === 'thread' ? REPLIES[this.replies++ % REPLIES.length] : FREE;
      await this.typeInto(field, text, state);
      const send = page.locator('.av2-btn--primary:not([disabled])').first();
      if (await send.count()) await send.click({ timeout: 3000 }).catch(() => {});
      return true;
    }
    const prim = page.locator('.av2-btn--primary:not([disabled])').first();
    if (await prim.count()) { await prim.click({ timeout: 3000 }).catch(() => {}); return true; }
    return false;
  }

  /** Play one journey from Home to the recap. Returns the kinds seen. */
  async playJourney({ maxSeconds = 240, entry = null, label = '' } = {}) {
    const page = this.page;
    const state = { itemIndex: 0, typing: false, readerBox: null };
    if (!entry) this.timelines.clear();
    if (entry) {
      await page.goto(`${this.stack.web}${entry}`, { waitUntil: 'domcontentloaded' });
      await sleep(2500);
    } else {
      await page.goto(`${this.stack.web}/atelier`, { waitUntil: 'domcontentloaded' });
      // The first cold compile of a page can take a while on a dev server; one reload is allowed.
      const ready = await page.locator('.av2-btn--primary').first().waitFor({ timeout: 45000 }).then(() => true, () => false);
      if (!ready) {
        await page.reload({ waitUntil: 'domcontentloaded' });
        await page.locator('.av2-btn--primary').first().waitFor({ timeout: 60000 });
      }
      const home = await snapshot(page);
      this.pageChecks(home, 'home');
      await this.shoot('home-before');
      await page.locator('.av2-btn--primary').first().click();
    }

    const t0 = Date.now();
    // WP-111: every line the story put on screen today (reader and thread), so the
    // walk can tell which season page a day served.
    if (!entry) this.dayText = '';
    let lastSig = '';
    let sameFor = 0;
    let shotSig = '';
    const kinds = [];
    while (Date.now() - t0 < maxSeconds * 1000) {
      await sleep(250);
      const s = await snapshot(page);
      const kind = this.classify(s);
      const sig = `${kind}|${s.text.slice(0, 160)}|${s.graded.map((g) => g.state).join()}|${s.reader.map((r) => r.text).join()}`;
      this.trackVerdicts(s, kind);
      if (kind === 'reader') this.readerChecks(s, state);
      if (!entry && (kind === 'reader' || kind === 'thread') && !this.dayText.includes(s.text.slice(0, 200))) {
        this.dayText += `\n${s.text}`;
      }
      if (sig !== lastSig) {
        lastSig = sig;
        sameFor = 0;
        this.kindsSeen.add(kind);
        kinds.push(kind);
        this.pageChecks(s, kind);
        await this.stepPass(s, kind, state);
        const verdict = s.graded[0]?.state || s.epFeedback[0]?.verdict;
        if (verdict) {
          this.findings.check('one-verdict-on-screen', s.graded.length + s.epFeedback.length === 1, `${s.graded.length + s.epFeedback.length} verdicts at once`, this.where({ kind }));
          if (verdict === 'wrong') {
            const gt = (s.graded[0]?.text || '').replace(/Continue|Weiter|Continuer|Not yet|Noch nicht|Pas encore/gi, '').trim();
            this.findings.check('wrong-verdict-shows-the-right-form', gt.length >= 8 || s.frTexts.length > 0, `«Not yet» with no correct form on screen: «${s.text.slice(0, 140)}»`, this.where({ kind }));
          }
        }
        const shotKey = `${kind}|${verdict || ''}|${kind === 'reader' ? s.reader.map((r) => r.text).join() : s.text.slice(0, 60)}`;
        const isReaderMid = kind === 'reader' && s.text.match(/Panel (\d+) of (\d+)/) && !/Panel 1 of|Panel (\d+) of \1/.test(s.text) && (() => { const m = s.text.match(/Panel (\d+) of (\d+)/); return m[1] !== '1' && m[1] !== m[2]; })();
        if (shotKey !== shotSig && !isReaderMid) {
          shotSig = shotKey;
          await this.shoot(label + kind + (verdict ? `-${verdict}` : ''));
        }
      } else sameFor += 1;
      if (kind === 'recap' || kind === 'home-done') break;
      const acted = await this.act(s, kind, state);
      if (!acted && sameFor > 40 && !entry) {
        this.findings.check('a-way-forward', false, `stuck for ${(sameFor * 0.25).toFixed(0)}s on «${s.text.slice(0, 140)}»`, this.where({ kind }));
        await this.shoot('stuck');
        break;
      }
      if (entry && !s.url.startsWith('/atelier')) break; // the loop led out of the page (e.g. to Courrier)
      if (entry && sameFor > 40) break; // the loop ended by itself (no recap to reach)
      if (sameFor > 120) {
        this.findings.check('a-way-forward', false, `no change for 30s on «${s.text.slice(0, 140)}»`, this.where({ kind }));
        await this.shoot('stuck');
        break;
      }
    }
    this.finishTimelines();
    return kinds;
  }

  async visit(routePath, label) {
    const page = this.page;
    await page.goto(`${this.stack.web}${routePath}`, { waitUntil: 'domcontentloaded' });
    await sleep(1800);
    const s = await snapshot(page);
    this.pageChecks(s, label);
    this.findings.check('page-has-content', s.text.length > 40, `«${s.text.slice(0, 80)}»`, this.where({ kind: label }));
    await this.shoot(label);
    return s;
  }
}
