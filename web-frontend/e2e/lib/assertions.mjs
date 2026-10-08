// Learner-clarity assertions. Every one answers a piece of the same question for the
// screen it looks at: does the learner know what to do, whether they were right, and
// how to go on? A failed assertion is a finding: it is recorded (with the screenshot),
// never swallowed.

export class Findings {
  constructor() {
    this.results = []; // { id, ok, detail, where, shot }
    this.counts = new Map();
  }
  check(id, ok, detail, where = {}) {
    if (!ok) {
      // The same finding on the same screen is one finding, not one per poll.
      const key = `${id}|${where.lang}|${where.level}|${where.kind}|${id.startsWith('no-english') ? '' : String(detail).slice(0, 80)}`;
      this.seen = this.seen || new Set();
      if (this.seen.has(key)) return false;
      this.seen.add(key);
    }
    this.results.push({ id, ok: !!ok, detail: ok ? '' : String(detail || ''), where });
    const c = this.counts.get(id) || { pass: 0, fail: 0 };
    c[ok ? 'pass' : 'fail'] += 1;
    this.counts.set(id, c);
    if (!ok) console.log(`  [FAIL] ${id} — ${detail} (${JSON.stringify(where)})`);
    return !!ok;
  }
  get failures() {
    return this.results.filter((r) => !r.ok);
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
  /Accept or decline, and say when you are free\.?/g,
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

export const SERVER_BANNER = /(reach(ed)? the server|Server (an|erreicht)|serveur|Sending to the server|gesendet)/i;
export const PENDING_VERDICT = /(Je relis|Checking|Prüfe|Wird geprüft|Reading it over)/i;
