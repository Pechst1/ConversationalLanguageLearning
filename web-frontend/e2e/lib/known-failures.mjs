// App failures the walk finds and an open issue (label walk-finding) tracks. Each entry
// covers one check in the one situation the issue describes, and nothing wider: the same
// check failing anywhere else still fails the walk. When the issue is fixed, delete its
// entry; `known-failures.test.mjs` keeps every entry narrow and numbered.
//
// { id: the check, issue: the GitHub issue, why: one line, when(detail, where): true
//   for the failures the issue describes }
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
];

export function knownFailure(id, detail, where = {}) {
  return KNOWN_FAILURES.find((entry) => entry.id === id && entry.when(detail, where)) || null;
}
