// #954 `rule-check-tally-matches-its-items`: a Regelprüfung's result counts the verdicts its
// items showed. Walk of 20 Nov 2026 (a1-de-fresh, day 2): the own sentence said «Noch nicht»,
// then the result said «3 von 3 richtig, der eigene Satz inklusive».
//
// A rule check's item carries the épreuve eyebrow in its head (`.forge-head__eyebrow`, the
// séance's items do not); its result is `.forge-result__sub` («{correct} von {total} …»).

/** A fresh tally: the first verdict each item of the rule check showed, by item. */
export function newTestOutTally() {
  return { items: new Map(), checked: false };
}

/** «2 von 3 richtig» / «2 of 3 right» / «2 sur 3» → [2, 3]. */
export function resultCount(text) {
  const match = String(text || '').match(/(\d+)\D{1,8}?(\d+)/);
  return match ? [Number(match[1]), Number(match[2])] : null;
}

/**
 * Read one frame `s` (the walk's snapshot: `testOut`, `forgeHead`, `forgeResult`,
 * `epFeedback`) of the item `key`. Returns the check to file once a result shows
 * ({ ok, detail }), else null.
 */
export function readTestOut(tally, s, key) {
  if (s.forgeResult) {
    if (tally.checked) return null;
    tally.checked = true;
    const count = resultCount(s.forgeResult);
    if (!count) return null;
    const [correct, total] = count;
    const missed = [...tally.items.entries()].filter(([, verdict]) => verdict === 'wrong').map(([item]) => item);
    return {
      ok: correct + missed.length <= total,
      detail: `«${s.forgeResult.slice(0, 90)}» after ${missed.length} item(s) shown «not yet»: ${missed.map((item) => `«${String(item).slice(0, 60)}»`).join(', ')}`,
    };
  }
  if (s.forgeHead && !s.testOut) {
    // A séance item: whatever rule check comes next starts its own count.
    tally.items.clear();
    tally.checked = false;
    return null;
  }
  if (!s.testOut) return null;
  if (tally.checked) {
    // A new rule check after a finished one.
    tally.items.clear();
    tally.checked = false;
  }
  const verdict = (s.epFeedback || []).map((f) => f.verdict).find((v) => v === 'correct' || v === 'wrong');
  if (verdict && !tally.items.has(key)) tally.items.set(key, verdict);
  return null;
}
