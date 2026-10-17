/**
 * WP-103 T8 — La Forge's «Correct / À corriger» leads somewhere.
 *
 * The owner's test: sorting a sentence as wrong ended at the sort. The fix: after
 * «À corriger», the learner corrects the sentence — a short field, or tiles at
 * A1 when the item carries options — and «Passer» shows the corrected sentence.
 * Either way the right form is seen.
 *
 * The server sends, on the classify result:
 *   `corrected_fr`                the right sentence;
 *   `follow_up`                   `{ kind: "correct_it", source_fr, goal_native }`
 *                                 (plus `options` for tiles, and any extra
 *                                 `accepted_fr`), graded like a transform.
 *
 * Everything is read defensively. Without `follow_up` the corrected sentence is
 * still shown («La bonne phrase»); without either, nothing is added.
 *
 * Pure: the component draws it, the node suite pins it.
 */

export type ForgeFollowUp = {
  kind: 'correct_it';
  /** The wrong sentence, quoted (French). */
  sourceFr: string;
  /** «Correct the sentence.» — in the learner's language, when the server said it. */
  goalNative: string | null;
  /** The right sentence: revealed by «Passer» and by a wrong try. */
  correctedFr: string | null;
  /** Tiles (a shuffled bank, spares included) — a field otherwise. */
  options: string[] | null;
  /** Every sentence that counts as right (the corrected one first). */
  accepted: string[];
};

export type ClassifyRepair = {
  followUp: ForgeFollowUp | null;
  /** The right sentence, for the plain «La bonne phrase» line when there is no follow-up. */
  correctedFr: string | null;
};

function text(value: unknown): string {
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
}

/** The bank appends the sentence's meaning: «Elle a mangé (She ate)». */
function bareSentence(prompt: unknown): string {
  return text(prompt).replace(/\s*\([^()]*\)\s*$/, '').trim();
}

/** A judgement classify: «Correct» / «À corriger» on a French sentence. */
export function isJudgementItem(item: Record<string, any> | null | undefined): boolean {
  if (!item) return false;
  if (item.classify_kind) return item.classify_kind === 'judgement';
  const labels: string[] = Array.isArray(item.labels) ? item.labels.map((label: unknown) => text(label).toLowerCase()) : [];
  return labels.includes('correct') && labels.includes('à corriger');
}

function sentenceIsWrong(item: Record<string, any> | null | undefined): boolean {
  return text(item?.correct_label ?? item?.correct_answer).toLowerCase() === 'à corriger';
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(text).filter(Boolean) : [];
}

export function classifyRepair(
  item: Record<string, any> | null | undefined,
  correction: Record<string, any> | null | undefined,
): ClassifyRepair {
  const raw =
    correction?.follow_up ?? correction?.forge?.follow_up ?? item?.follow_up ?? null;
  const spec = raw && typeof raw === 'object' ? (raw as Record<string, any>) : null;
  const correctedFr =
    text(spec?.corrected_fr) || text(correction?.corrected_fr) || text(item?.corrected_fr) || null;
  // Only a wrong sentence has anything to correct.
  if (!spec && !(isJudgementItem(item) && sentenceIsWrong(item))) return { followUp: null, correctedFr: null };
  if (!spec) return { followUp: null, correctedFr };
  if (spec.kind && spec.kind !== 'correct_it') return { followUp: null, correctedFr };
  const sourceFr = text(spec.source_fr) || text(item?.source_fr) || bareSentence(item?.prompt);
  if (!sourceFr) return { followUp: null, correctedFr };
  const options = strings(spec.options);
  const accepted = [correctedFr, ...strings(spec.accepted_fr), ...strings(spec.accepted_answers)].filter(
    (value, index, all): value is string => Boolean(value) && all.indexOf(value) === index,
  );
  return {
    followUp: {
      kind: 'correct_it',
      sourceFr,
      goalNative: text(spec.goal_native) || null,
      correctedFr,
      options: options.length >= 2 ? options : null,
      accepted,
    },
    correctedFr,
  };
}

/** Case, quotes, the space after an elision and the final stop do not matter; accents do. */
export function foldSentence(value: string | string[] | null | undefined): string {
  const raw = Array.isArray(value) ? value.join(' ') : String(value ?? '');
  return raw
    .normalize('NFC')
    .replace(/[‘’ʼ`]/g, "'")
    .replace(/'\s+/g, "'")
    .replace(/[“”«»„"]/g, '')
    .replace(/\s+/g, ' ')
    .replace(/[.!?…;:,\s]+$/g, '')
    .trim()
    .toLowerCase();
}

/** The sentence without its punctuation marks: what a tile build can say. */
function foldWords(value: string | string[]): string {
  return foldSentence(value).replace(/[.!?…;:,]/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * Owner request 2026-10-17, as `answer_acceptance.repair_readings` on the server:
 * a typed correction may be only the part that changed («vertes» for «des chaises
 * vert»), with any of the unchanged words around it. Each reading puts the answer
 * in place of the stretch of the source that differs from the target; it is right
 * only when the whole sentence it makes is the target.
 */
export function repairReadings(answer: string, source: string, target: string): string[] {
  const learner = foldWords(answer).split(' ').filter(Boolean);
  const wrong = foldWords(source).split(' ').filter(Boolean);
  const right = foldWords(target).split(' ').filter(Boolean);
  if (!learner.length || !wrong.length || !right.length) return [];
  const limit = Math.min(wrong.length, right.length);
  let head = 0;
  while (head < limit && wrong[head] === right[head]) head += 1;
  let tail = 0;
  while (tail < limit - head && wrong[wrong.length - 1 - tail] === right[right.length - 1 - tail]) tail += 1;
  const readings: string[] = [];
  for (let before = 0; before <= head; before += 1) {
    for (let after = 0; after <= tail; after += 1) {
      readings.push([...wrong.slice(0, head - before), ...learner, ...wrong.slice(wrong.length - tail + after)].join(' '));
    }
  }
  return readings;
}

/**
 * True when the answer (typed, or tiles in order) is one of the accepted sentences.
 * Tiles carry words only (live walk #115: no «,» or «?» tile), so a tile build is
 * compared without punctuation; a typed answer still keeps its inner commas, and
 * may be only the corrected part (:func:`repairReadings`).
 */
export function followUpMatches(answer: string | string[], followUp: ForgeFollowUp): boolean {
  const said = foldSentence(answer);
  if (!said) return false;
  if (Array.isArray(answer)) {
    const words = foldWords(answer);
    return followUp.accepted.some((sentence) => foldWords(sentence) === words);
  }
  if (followUp.accepted.some((sentence) => foldSentence(sentence) === said)) return true;
  return followUp.accepted.some((sentence) =>
    repairReadings(answer, followUp.sourceFr, sentence).includes(foldWords(sentence)),
  );
}

export type FollowUpOutcome = 'right' | 'revealed';

/**
 * A check is one shot, like a transform: right, or the right sentence is shown.
 * «Passer» is `revealed` without a try.
 */
export function followUpOutcome(answer: string | string[], followUp: ForgeFollowUp): FollowUpOutcome {
  return followUpMatches(answer, followUp) ? 'right' : 'revealed';
}

/** What the learner may do next: nothing is gated once the follow-up is settled. */
export function followUpSettled(outcome: FollowUpOutcome | null | undefined): boolean {
  return outcome === 'right' || outcome === 'revealed';
}
