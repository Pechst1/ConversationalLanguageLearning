// What a miss screen must look like at phone size (#282), read from the walk's snapshot
// (`layout` in driver.mjs). Pure, so the node suite and the walk share one definition.
//
//   miss-prompt-not-covered         no cameo bubble stands on the item's prompt or answer box
//   miss-action-above-the-sheet     «Compare» is fully above the verdict sheet, never behind it
//   repair-field-matches-the-instruction
//                                   the words the instruction names («Replace «à le» with «au»»)
//                                   are the words the field holds

const overlaps = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;

/** The words an instruction like «Replace «à le» with «au» here.» says are wrong, or null. */
export function namedWrongWords(hint) {
  const match = /(?:replace|ersetze|remplace)\s+[«“"„]\s*([^»”"“]+?)\s*[»”"“]/i.exec(String(hint || ''));
  return match ? match[1].replace(/\s+/g, ' ').trim() : null;
}

/** `[{ name, ok, detail }]` for every check the screen has the parts for; empty off a miss. */
export function missLayoutChecks(layout) {
  if (!layout) return [];
  const checks = [];
  const exercise = layout.exercise || [];
  const bubbles = layout.bubbles || [];
  if (exercise.length && bubbles.length) {
    const covered = bubbles.filter((bubble) => exercise.some((zone) => overlaps(bubble, zone)));
    checks.push({
      name: 'miss-prompt-not-covered',
      ok: covered.length === 0,
      detail: `a cameo bubble ${JSON.stringify(covered[0])} stands on the prompt and answer ${JSON.stringify(exercise)}`,
    });
  }
  const sheet = (layout.sheet || [])[0];
  const compare = layout.compare || [];
  if (sheet && compare.length) {
    const behind = compare.filter((box) => box.bottom > sheet.top);
    checks.push({
      name: 'miss-action-above-the-sheet',
      ok: behind.length === 0,
      detail: `«Compare» ${JSON.stringify(behind[0])} is behind or below the verdict sheet that starts at ${sheet.top} (screen ${layout.height})`,
    });
  }
  const named = namedWrongWords((layout.hints || []).join(' '));
  const gaps = layout.gaps || [];
  if (named && gaps.length) {
    const fold = (text) => String(text).replace(/\s+/g, ' ').trim().toLowerCase();
    checks.push({
      name: 'repair-field-matches-the-instruction',
      ok: gaps.some((value) => fold(value) === fold(named)),
      detail: `the instruction names «${named}» but the field holds ${gaps.map((value) => `«${value}»`).join(' · ')}`,
    });
  }
  return checks;
}
