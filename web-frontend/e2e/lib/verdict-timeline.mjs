// One verdict per question (`one-verdict-never-reversed`): which question a verdict on screen
// belongs to.
//
// An item is named by the text it showed before it was answered. Main's walk of 10 Nov 2026
// (season-en day 2) caught the sheet of a miss on item 12/13 still sliding out while 13/13
// was already on screen; the walk answered 13/13 from that frame, never saw it unanswered,
// and filed 13/13's «Correct, with help» under 12/13's «Not yet» as one reversed verdict. The
// item counter («12/13») says when the screen has moved on: a verdict shown beside a new
// counter is the old item's leaving, so that frame names the new item and adds no state.
import { PENDING_VERDICT } from './assertions.mjs';

const STEP_RE = /(Step \d+ of \d+|Schritt \d+ von \d+|Étape \d+ sur \d+)/;
const COUNTER_RE = /\b(\d{1,3})\/(\d{1,3})\b/;

/** The «12/13» counter of a drill set, or null. */
export function itemCounter(text) {
  const match = String(text || '').match(COUNTER_RE);
  return match ? match[0] : null;
}

/**
 * Track the verdict states of the screen `s` on `walk` (its `questionSig`, `questionCounter`,
 * `stepCaptions`, `timelines` and `day`). Returns the item's timeline.
 */
export function trackVerdicts(walk, s, kind) {
  const hasVerdict = s.graded.length + s.epFeedback.length > 0;
  const counter = itemCounter(s.text);
  const leaving = hasVerdict && counter && walk.questionCounter && counter !== walk.questionCounter;
  if (!hasVerdict || leaving) {
    walk.questionSig = s.text.slice(0, 140);
    walk.questionCounter = counter;
  }
  const step = (s.text.match(STEP_RE) || ['none'])[0];
  if (step !== 'none' && walk.stepCaptions[walk.stepCaptions.length - 1] !== step) walk.stepCaptions.push(step);
  const key = kind === 'thread' ? `thread ${step}` : `${step} ${walk.questionSig || ''}`;
  const t = walk.timelines.get(`${walk.day}:${key}`) || { states: [], pending: false };
  if (!leaving) {
    for (const g of s.graded) if (t.states[t.states.length - 1] !== g.state) t.states.push(g.state);
    for (const f of s.epFeedback) if (t.states[t.states.length - 1] !== f.verdict) t.states.push(f.verdict);
  }
  if (PENDING_VERDICT.test(s.text)) t.pending = true;
  walk.timelines.set(`${walk.day}:${key}`, t);
  return t;
}

/** Whether a timeline's verdicts changed (`unscored` is no verdict). */
export function reversed(t) {
  const distinct = t.states.filter((x) => x && x !== 'unscored');
  return { flips: distinct.some((x, i) => i > 0 && x !== distinct[i - 1]), distinct };
}
