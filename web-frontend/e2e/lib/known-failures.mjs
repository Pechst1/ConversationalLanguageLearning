// App failures the walk finds and an open issue (label walk-finding) tracks. Each entry
// covers one check in the one situation the issue describes, and nothing wider: the same
// check failing anywhere else still fails the walk. When the issue is fixed, delete its
// entry; `known-failures.test.mjs` keeps every entry narrow and numbered.
//
// { id: the check, issue: the GitHub issue, why: one line, when(detail, where): true
//   for the failures the issue describes }
import { englishWords } from './assertions.mjs';

/** #718: the reload served every expected card, in order, and more: freed slots refilled. */
function reloadRefilled(detail) {
  const m = detail.match(/expected (\{.*\}), the reload served (\{.*\})$/);
  if (!m) return false;
  let expected;
  let served;
  try {
    expected = JSON.parse(m[1]);
    served = JSON.parse(m[2]);
  } catch {
    return false;
  }
  let extra = 0;
  for (const [list, ids] of Object.entries(expected)) {
    const got = served[list] || [];
    if (JSON.stringify(got.slice(0, ids.length)) !== JSON.stringify(ids)) return false;
    extra += got.length - ids.length;
  }
  return extra > 0;
}

export const KNOWN_FAILURES = [
  {
    id: 'appeal-upheld-turns-the-verdict',
    issue: 715,
    why: 'a pairs drill offers the appeal, and the server refuses it (no answer text): «unread»',
    when: (detail, where) => where.drill === 'match' && /^appeal unread:/.test(detail),
  },
  {
    id: 'season-tentpole-on-its-day',
    issue: 717,
    why: "season 1's second tentpole (t2.a, t2.b) does not land on days 7-10 with production's flags and full days",
    when: (detail) => /^t2\.[ab]: /.test(detail),
  },
  {
    id: 'drill-reload-keeps-the-batch',
    issue: 718,
    why: "after the day's words step, a drill reload refills the answered slots",
    when: (detail) => reloadRefilled(detail),
  },
  {
    id: 'no-english-on-french-b1',
    issue: 196,
    why: 'a La Forge item under French chrome quotes its sentence in English («Complète la phrase : « Last night… »»)',
    // Only the quoted sentence of a «… la phrase : « … »» item, and only when that quote is English.
    when: (detail) => {
      const quote = detail.match(/la phrase\s*:\s*«\s*([^»]+)»/);
      return Boolean(quote) && englishWords(quote[1]).length >= 3;
    },
  },
];

export function knownFailure(id, detail, where = {}) {
  return KNOWN_FAILURES.find((entry) => entry.id === id && entry.when(detail, where)) || null;
}
