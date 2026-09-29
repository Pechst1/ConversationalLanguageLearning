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

/** A note as its sentences: the corrector's explanation is one or two. */
function noteSentences(note: string): string[] {
  // No lookbehind: older iOS web views refuse it.
  return (note.match(/[^.!?…]+(?:[.!?…]+|$)/g) ?? [note])
    .map((sentence) => sentence.trim())
    .filter(Boolean);
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
