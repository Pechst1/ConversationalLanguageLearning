/**
 * The word ribbon («à placer :») and its «2/3» chip (#928, root cause #143).
 *
 * A target word is «used» when the server's record says so: every learner
 * message is checked against the ribbon's words when it is stored, in any accent
 * and any real inflection («vendu» is vendre, «cle» is clé), and the mission
 * carries the result as `used_target_word_ids`. The page never tests the raw
 * text against the word itself: a second, simpler test on the client is how
 * «vendu» and «cle» once read as unused. Kept outside the page so a node test
 * can hold it.
 */

import type { RealWorldMission } from '@/services/api';

export type RibbonWord = { t: string; used?: boolean; recall?: string };

export function ribbonWords(mission: RealWorldMission | null | undefined): RibbonWord[] {
  const direct = Array.isArray(mission?.target_vocabulary) ? mission?.target_vocabulary || [] : [];
  const prompt = Array.isArray(mission?.prompt_payload?.target_vocabulary)
    ? mission?.prompt_payload?.target_vocabulary || []
    : [];
  const usedIds = new Set((mission?.used_target_word_ids || []).map((id) => Number(id)));
  // WP-115d: the week's letter asks for due words by their meaning — the reply is
  // where the learner recalls the French, which the ribbon shows once it is used.
  const recall = Boolean(mission?.prompt_payload?.recall_ribbon);
  const seen = new Set<string>();
  const result: RibbonWord[] = [];
  (direct.length ? direct : prompt).forEach((item: Record<string, any>) => {
    const word = String(item.word || '').trim();
    const key = word.toLowerCase();
    if (!word || seen.has(key) || result.length >= 3) return;
    seen.add(key);
    const used = item.word_id != null && usedIds.has(Number(item.word_id));
    const meaning = String(item.translation || '').trim();
    result.push({ t: word, used, ...(recall && meaning ? { recall: meaning } : {}) });
  });
  return result;
}
