// Learner-clarity assertions. Every one answers a piece of the same question for the
// screen it looks at: does the learner know what to do, whether they were right, and
// how to go on? A failed assertion is a finding: it is recorded (with the screenshot),
// never swallowed.

import { knownFailure } from './known-failures.mjs';

export class Findings {
  constructor({ known = knownFailure } = {}) {
    this.results = []; // { id, ok, detail, where, shot, known }
    this.counts = new Map();
    this.knownFailure = known;
  }
  check(id, ok, detail, where = {}) {
    if (!ok) {
      // The same finding on the same screen is one finding, not one per poll.
      const key = `${id}|${where.lang}|${where.level}|${where.kind}|${id.startsWith('no-english') ? '' : String(detail).slice(0, 80)}`;
      this.seen = this.seen || new Set();
      if (this.seen.has(key)) return false;
      this.seen.add(key);
    }
    // An app failure with an open issue (known-failures.mjs) is still recorded and printed
    // with its issue number, but does not fail the walk; anything else it does not match
    // fails as before.
    const known = ok ? null : this.knownFailure(id, String(detail || ''), where);
    this.results.push({ id, ok: !!ok, detail: ok ? '' : String(detail || ''), where, ...(known ? { known: known.issue } : {}) });
    const c = this.counts.get(id) || { pass: 0, fail: 0, known: 0 };
    c[ok ? 'pass' : known ? 'known' : 'fail'] += 1;
    this.counts.set(id, c);
    if (!ok) console.log(`  [${known ? `KNOWN #${known.issue}` : 'FAIL'}] ${id} — ${detail} (${JSON.stringify(where)})`);
    return !!ok;
  }
  /** Failures that fail the walk: every failed check no known issue covers. */
  get failures() {
    return this.results.filter((r) => !r.ok && !r.known);
  }
  /** Failures an open issue covers (known-failures.mjs). */
  get known() {
    return this.results.filter((r) => !r.ok && r.known);
  }
  summary() {
    return [...this.counts.entries()].map(([id, c]) => ({ id, ...c }));
  }
}

// Words that give English away; a French B1+ screen may quote one only inside lang="fr".
const ENGLISH = new Set(
  ['the', 'and', 'your', 'you', 'with', 'this', 'that', 'is', 'are', 'for', 'from', 'of', 'to', 'in', 'on', 'it', 'not', 'yet', 'next', 'today', 'continue', 'done', 'answer', 'check', 'hint', 'translation', 'step', 'say', 'ask', 'what', 'how', 'can', 'will', 'have', 'was', 'were', 'has', 'be', 'or', 'but', 'an', 'at', 'as', 'by', 'her', 'his', 'she', 'he', 'we', 'they'],
);
// Text the fake story provider writes in English on purpose (scripts/dev_story_engine_server.py):
// scene setup, objective, hint and translation are `*_native` fields, and the fake has one native.
const FAKE_PROVIDER_ENGLISH = [
  /\[dev fake\][^.]*\./gi,
  /Suggest how you can help, or explain that you cannot\.?/g,
  /Propose an alternative for the market morning, or decline\.?/g,
  /Negotiate a price or say the bike does not interest you\.?/g,
  /Explain what happened to the parcel\.?/g,
  /Say whether you come on Friday and what you bring\.?/g,
  /Ask a neighbour for help, or offer yours\.?/g,
  /Say if you can keep the cat this weekend\.?/g,
  /Say yes or no, and when\.?/g,
  /Can you help me\?/g,
  /You (declined|offered to help)\.?/g,
];

export function englishWords(text) {
  let t = text;
  for (const re of FAKE_PROVIDER_ENGLISH) t = t.replace(re, ' ');
  const words = t.toLowerCase().match(/[a-z']+/g) || [];
  return [...new Set(words.filter((w) => ENGLISH.has(w)))];
}

/**
 * A screen's non-French text less what is marked as the learner's own language.
 *
 * Owner, 18–19 Nov 2026: from B1 the chrome is French, but an explanation (a rule, a hint,
 * why an answer was wrong, a correction's tag, a word's gloss) is in the learner's mother
 * tongue and carries `lang` with it. `marked` is the snapshot's list of outermost marked
 * non-French elements (`driver.mjs`); only those in `native` are set aside, so unmarked
 * English, or English marked for another learner, still counts.
 */
export function unmarkedText(text, marked, native) {
  let out = ` ${String(text || '')} `;
  const own = String(native || '').toLowerCase().split('-')[0];
  for (const item of marked || []) {
    if (!own || item?.lang !== own || !item.text) continue;
    out = out.replace(item.text, ' ');
  }
  return out.replace(/\s+/g, ' ').trim();
}

/**
 * The B1 French-screen language check: `{ ok, words, around }` for screen `s` of a walker
 * whose mother tongue is `native`. Three English marker words outside French and outside the
 * walker's own marked explanations fail it.
 */
export function englishOnFrenchScreen(s, native) {
  const text = unmarkedText(s?.nonFrText, s?.marked, native);
  const words = englishWords(text);
  // The text around the first English word, not the page's opening chrome: the
  // detail has to name the string to fix.
  const at = words.length >= 3 ? text.toLowerCase().search(new RegExp(`\\b(${words.join('|')})\\b`)) : 0;
  const around = text.slice(Math.max(0, at - 60), Math.max(0, at - 60) + 240);
  return { ok: words.length < 3, words, around };
}

/**
 * Whether screen `s` shows a connection banner (an answer did not reach the server, is on its
 * way, or is kept on this device): an element the app marks `data-connection-banner`
 * (lib/connection-banner.ts) or the session's `.journey-connection` notice. Never a word in the
 * screen's text: that text holds the scene, and a scene says «serveur» (a waiter) or
 * «gesendet» as freely as any other word (#794).
 */
export function serverBanner(s) {
  return (s.connection || []).length > 0 || (s.connectionBanners || []).length > 0;
}

/** The banners on screen `s`, for a finding's detail. */
export function bannersOn(s) {
  return [...new Set([...(s.connectionBanners || []), ...(s.connection || [])])].join(', ');
}
export const PENDING_VERDICT = /(Je relis|Checking|Prüfe|Wird geprüft|Reading it over)/i;
