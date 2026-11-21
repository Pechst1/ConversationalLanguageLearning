/**
 * The word ribbon («à placer :»): the letter's target words, each marked «used»
 * once the server's check of a reply recorded it (#928).
 *
 * «Used» is read from `used_target_word_ids` (serialize_mission, app/services/
 * missions.py), the one record of which targets the learner's checked replies
 * used: an inflected verb («vendu» for vendre) and a word without its accent
 * («cle» for clé) count there. The screen never matches the raw text itself.
 */

import type { RealWorldMission } from '@/services/api';

export type RibbonWord = { t: string; used?: boolean; recall?: string };

export function ribbonWords(mission: RealWorldMission | null): RibbonWord[] {
  const direct = Array.isArray(mission?.target_vocabulary) ? mission?.target_vocabulary || [] : [];
  const prompt = Array.isArray(mission?.prompt_payload?.target_vocabulary)
    ? mission?.prompt_payload?.target_vocabulary || []
    : [];
  const usedIds = new Set(
    (Array.isArray(mission?.used_target_word_ids) ? mission?.used_target_word_ids || [] : []).map(Number),
  );
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
    const used = usedIds.has(Number(item.word_id));
    const meaning = String(item.translation || '').trim();
    result.push({ t: word, used, ...(recall && meaning ? { recall: meaning } : {}) });
  });
  return result;
}
