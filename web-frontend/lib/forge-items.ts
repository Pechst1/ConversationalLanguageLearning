/**
 * La Forge (WP-S2 × WP-S3): the item the forge serves next may be a bank
 * top-up — generated on the server after the séance started, appended to this
 * session's exercise set, and absent from the set the page loaded. The forge's
 * `next` carries the item itself; these helpers seat it in the page's copy of
 * the set and point the drill at it, so the one Épreuve renders it like any
 * other item (and the submit posts its id, which the server grades by key).
 */

export type ForgeNextLike = {
  concept_id: number;
  round: string;
  mode: string;
  item_id: string;
  item_index?: number;
  item?: Record<string, any> | null;
};

type ExerciseSetLike = { concept_id: number; payload: Record<string, any> };

export const FORGE_OUTPUT_ROUNDS = ['sentence', 'speak', 'conversation'] as const;

export function isForgeOutputRound(round: string): boolean {
  return (FORGE_OUTPUT_ROUNDS as readonly string[]).includes(round);
}

function containerItems(payload: Record<string, any>, round: string, mode: string): any[] | null {
  if (round === 'recognize') return payload?.recognize?.[mode]?.items ?? null;
  if (round === 'transform') return payload?.transform?.items ?? null;
  if (isForgeOutputRound(round)) return payload?.output_ladder?.[round]?.items ?? null;
  return null;
}

function withItem(payload: Record<string, any>, round: string, mode: string, item: Record<string, any>) {
  const next = { ...payload };
  if (round === 'recognize') {
    const recognize = { ...(next.recognize || {}) };
    const container = { ...(recognize[mode] || {}) };
    container.items = [...(container.items || []), item];
    recognize[mode] = container;
    next.recognize = recognize;
  } else if (round === 'transform') {
    next.transform = { ...(next.transform || {}), items: [...(next.transform?.items || []), item] };
  } else {
    const ladder = { ...(next.output_ladder || {}) };
    ladder[round] = { ...(ladder[round] || {}), items: [...(ladder[round]?.items || []), item] };
    next.output_ladder = ladder;
  }
  return next;
}

/**
 * The exercise sets with the forge's next item seated, and that item's index in
 * its container. Unchanged sets (the same array) when the item is already there
 * or the forge sent none; `index` then falls back to the server's `item_index`.
 */
export function seatForgeItem<T extends ExerciseSetLike>(
  sets: T[],
  next: ForgeNextLike | null | undefined,
): { sets: T[]; index: number } {
  if (!next) return { sets, index: 0 };
  const fallback = Math.max(0, Number(next.item_index || 0));
  const setIndex = sets.findIndex((set) => set.concept_id === next.concept_id);
  if (setIndex < 0) return { sets, index: fallback };
  const payload = sets[setIndex].payload || {};
  const items = containerItems(payload, next.round, next.mode) || [];
  const found = items.findIndex((item: any) => String(item?.id ?? '') === String(next.item_id));
  if (found >= 0) return { sets, index: found };
  const item = next.item && typeof next.item === 'object' ? next.item : null;
  if (!item || String(item.id ?? '') !== String(next.item_id)) return { sets, index: fallback };
  const seated = sets.slice();
  seated[setIndex] = { ...sets[setIndex], payload: withItem(payload, next.round, next.mode, item) };
  return { sets: seated, index: items.length };
}

/**
 * The output rungs render their container's first item. When the forge poses
 * another one (a top-up, a reprise), the page shows a set scoped to that item.
 */
export function scopeOutputItem(
  payload: Record<string, any> | null,
  round: string,
  index: number,
): Record<string, any> | null {
  if (!payload || !isForgeOutputRound(round) || index <= 0) return payload;
  const items = payload.output_ladder?.[round]?.items || [];
  const item = items[index];
  if (!item) return payload;
  return {
    ...payload,
    output_ladder: { ...(payload.output_ladder || {}), [round]: { ...(payload.output_ladder?.[round] || {}), items: [item] } },
  };
}
