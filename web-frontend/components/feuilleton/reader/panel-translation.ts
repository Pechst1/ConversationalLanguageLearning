/* «Traduire la case» for every panel, not only the ones the director translated.
 *
 * WP-90 brought the chip back for ≤A2 learners: the director sends each line's
 * `text_native`. From B1 it sends none, and narration never had one, so a
 * learner stuck on a long passage had nothing to press. Here a panel's French
 * that arrived without a translation is translated on demand, into the
 * learner's own language (`/atelier/translate` reads `native_language`), when
 * the learner asks and never before: the French is always read first.
 *
 * Pure functions over a table keyed by the French text, so the reader holds no
 * per-panel bookkeeping and the same sentence is never asked for twice. */

import type { ReaderPanelStage } from './panel-model';

export type PanelTranslation =
  | { state: 'loading' }
  | { state: 'ready'; text: string }
  | { state: 'failed' };

export type PanelTranslationTable = Readonly<Record<string, PanelTranslation>>;

/** Everything on the panel a learner could ask to have translated. */
export function panelHasText(stage: ReaderPanelStage): boolean {
  return Boolean(stage.caption.trim()) || stage.lines.some((line) => !line.you && Boolean(line.fr.trim()));
}

/**
 * The French on this panel that has no translation yet: the narration, then
 * each line the director sent without one. The learner's own line is theirs
 * already and is never sent.
 */
export function panelTextsToTranslate(stage: ReaderPanelStage): string[] {
  const texts: string[] = [];
  const add = (text: string) => {
    const french = text.trim();
    if (french && !texts.includes(french)) texts.push(french);
  };
  if (!stage.captionEn) add(stage.caption);
  stage.lines.forEach((line) => {
    if (!line.you && !line.en) add(line.fr);
  });
  return texts;
}

/** The texts still to request: never asked, or asked and failed (a retry). */
export function textsToRequest(stage: ReaderPanelStage, table: PanelTranslationTable): string[] {
  return panelTextsToTranslate(stage).filter((text) => !table[text] || table[text].state === 'failed');
}

/** The panel with what has arrived filled in; a supplied translation always wins. */
export function translatedStage(stage: ReaderPanelStage, table: PanelTranslationTable): ReaderPanelStage {
  const ready = (text: string) => {
    const entry = table[text.trim()];
    return entry && entry.state === 'ready' ? entry.text : '';
  };
  let changed = false;
  const lines = stage.lines.map((line) => {
    if (line.you || line.en) return line;
    const en = ready(line.fr);
    if (!en) return line;
    changed = true;
    return { ...line, en };
  });
  const captionEn = stage.captionEn || (stage.caption ? ready(stage.caption) : '');
  if (captionEn !== (stage.captionEn || '')) changed = true;
  return changed ? { ...stage, lines, ...(captionEn ? { captionEn } : {}) } : stage;
}

/**
 * Where the panel's translation stands once asked for: `loading` while any
 * part is on its way, `failed` when the panel ends with no translation at all
 * for something on it, else `ready`.
 */
export function panelTranslationState(
  stage: ReaderPanelStage,
  table: PanelTranslationTable,
): 'ready' | 'loading' | 'failed' {
  const pending = panelTextsToTranslate(stage).map((text) => table[text]);
  if (pending.some((entry) => !entry || entry.state === 'loading')) return 'loading';
  if (pending.some((entry) => entry.state === 'failed')) return 'failed';
  return 'ready';
}
