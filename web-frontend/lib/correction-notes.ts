/**
 * WP-103 T6 / T9 / T10 — one explanation per issue, never the same one twice.
 *
 * The owner's test: La Forge printed «3 corrections» with one explanation
 * repeated three times (the rule's note, the model's note, a second-check
 * line), and the conversation's slip carried a note the corrector had said
 * twice. The server now sends `notes_native` (one per issue, deduplicated);
 * these helpers hold the same line on the device, for payloads that predate it
 * and for a note that repeats *itself*.
 *
 * Pure: shared by the journey's thread and La Forge, and pinned by the node
 * suite.
 */

function foldNote(value: string): string {
  return value
    .replace(/[‘’ʼ]/g, "'")
    .replace(/[“”«»„"`]/g, '')
    .replace(/\s+/g, ' ')
    .replace(/[.!?…:;,\s]+$/g, '')
    .trim()
    .toLowerCase();
}

const OPENERS: Record<string, string> = { '«': '»', '„': '“', '“': '”' };
const ENDS = '.!?…';

/**
 * A note as its sentences: the corrector's explanation is one or two.
 *
 * R5 (check walk of 19 Nov, A1, German): a sentence ends at a stop outside every quote,
 * followed by a space or the end. «„Tu est bavard ?“ stimmt nicht; richtig ist „Tu es
 * bavard ?“.» used to be cut after each «?», inside the quotes; the pieces were joined
 * with spaces («„Tu est bavard ? “») and the lone «“.» was dropped as empty, so the
 * right form lost its closing quote.
 */
function noteSentences(note: string): string[] {
  const out: string[] = [];
  const open: string[] = [];
  let start = 0;
  for (let index = 0; index < note.length; index += 1) {
    const char = note[index];
    const top = open[open.length - 1];
    if (top && char === OPENERS[top]) open.pop();
    else if (char === '"') {
      if (top === '"') open.pop();
      else open.push('"');
    } else if (OPENERS[char]) open.push(char);
    else if (char === '»' || char === '”') open.pop();
    if (open.length || !ENDS.includes(char)) continue;
    let end = index + 1;
    while (end < note.length && ENDS.includes(note[end])) end += 1;
    if (end < note.length && !/\s/.test(note[end])) continue;
    out.push(note.slice(start, end));
    start = end;
    index = end - 1;
  }
  out.push(note.slice(start));
  return out.map((sentence) => sentence.trim()).filter(Boolean);
}

/**
 * Notes are compared sentence by sentence, whatever the case, the quotes or the
 * final stop; a sentence already said — or contained in a longer one already
 * said — is not said again, and a note left with nothing is dropped. Order is
 * kept.
 */
export function dedupeNotes(notes: ReadonlyArray<unknown> | null | undefined): string[] {
  const sentences: Array<{ note: number; text: string; folded: string }> = [];
  (notes ?? []).forEach((value, note) => {
    const text = typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
    if (!text) return;
    noteSentences(text).forEach((sentence) => {
      const folded = foldNote(sentence);
      if (folded) sentences.push({ note, text: sentence, folded });
    });
  });
  const kept = sentences.filter(
    (item, index) =>
      !sentences.some((other, otherIndex) => {
        if (otherIndex === index) return false;
        if (other.folded === item.folded) return otherIndex < index; // the first of equals stays
        // The longer one stays — but only a real sentence counts as said again, on whole words.
        return item.folded.length >= 12 && ` ${other.folded} `.includes(` ${item.folded} `);
      }),
  );
  const byNote = new Map<number, string[]>();
  kept.forEach((item) => byNote.set(item.note, [...(byNote.get(item.note) ?? []), item.text]));
  return Array.from(byNote.keys())
    .sort((a, b) => a - b)
    .map((note) => (byNote.get(note) as string[]).join(' '));
}

/**
 * What a correction explains: `notes_native` (one per issue) when the server
 * sent it, else the single `note_native`; deduplicated either way.
 */
export function correctionNotes(
  correction: { note_native?: unknown; notes_native?: unknown } | null | undefined,
): string[] {
  if (!correction) return [];
  const many = Array.isArray(correction.notes_native) ? dedupeNotes(correction.notes_native) : [];
  if (many.length) return many;
  return dedupeNotes([correction.note_native]);
}

/**
 * The label over a journey correction, by how its two texts relate: an `edit`
 * is «one thing to fix», a `pick` (#240) names the sentence that carries the
 * rule, a `meaning` (#167) names the French word whose meaning was missed, an
 * `example` (#624) offers a model sentence for a free sentence that missed the rule.
 */
export function correctionLabelKey(
  kind: unknown,
): 'correction' | 'correction_pick' | 'correction_meaning' | 'correction_example' {
  if (kind === 'pick') return 'correction_pick';
  if (kind === 'meaning') return 'correction_meaning';
  if (kind === 'example') return 'correction_example';
  return 'correction';
}

/**
 * La Forge's one correction block: the server's `notes_native` when it sent
 * them, else each erratum's `why_wrong` — the rule's note, the model's note and
 * a second-check line are the same explanation more often than not. One line
 * per distinct issue.
 */
export function forgeCorrectionNotes(correction: Record<string, any> | null | undefined): string[] {
  if (!correction) return [];
  const sent = Array.isArray(correction.notes_native) ? dedupeNotes(correction.notes_native) : [];
  if (sent.length) return sent;
  const errata: any[] = Array.isArray(correction.errata) ? correction.errata : [];
  return dedupeNotes(errata.map((erratum) => erratum?.why_wrong));
}
