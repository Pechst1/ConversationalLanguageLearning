/**
 * Le Quartier · the details: the small things the story leaves in the places the learner walks.
 *
 * A place opens when the story first goes there (`world.json`, a room in `world/rooms`); a detail
 * is smaller: a thing in a built place that appears once the story put it there. Two kinds:
 *
 * - a season moment (the plan's ladder): the learner's usual cup on the zinc after «La même
 *   chose ?», the party's garlands. It waits on the season flag the moment sets (`flag`), and a
 *   thing's `text` may name the flag's value (`{value}`): the cup is the learner's own order.
 * - a story order: something a page of the learner's own story left there (`living_story.WorldMark`,
 *   Gus's petition on Le Mistral's window). It waits on that mark (`mark`: its French name and
 *   the season place the page set it in).
 *
 * The forge writes each one as a detail file (`world/details/<id>.json`), in the coordinates of the
 * place it stands in (`in`: the quai de Valmy for Le Mistral's room, or a room of `world/rooms`),
 * with the things the room kit draws (`room.ts`). The quarter lays the details the learner's own
 * story set: the server sends the flags it set and the marks it left
 * (`GET /story-engine/world-state`), and `setBy` picks them. The standalone page lays one with
 * `?detail=<id>&value=<the flag's value>` to look at it.
 */
import { buildThing } from './room';
import type { RoomThing } from './room';
import type { Build } from './kit';
import type { Words } from './memory';

export interface DetailSpec {
  id: string;
  version: number;
  kind: 'detail';
  /** the built place it stands in (`world.json`: the quai de Valmy for Le Mistral's room, or a room) */
  in: string;
  title: Words;
  /** the line of the plan's ladder it is, or the page that left it, and what sets it */
  moment: string;
  /** a season moment: the flag it waits on (`app/data/season/s1/season.json`), and the value shown when none is given */
  flag?: { key: string; example: string };
  /** a story order: the mark it waits on, as a page left it (its French name, the season place) */
  mark?: { name_fr: string; location_id: string };
  things: RoomThing[];
  provenance: { canon: string; scenes: string[] };
}

/** What the learner's story set and left, as the server sends it (`/story-engine/world-state`). */
export interface LearnerWorld {
  flags?: Record<string, unknown> | null;
  marks?: Array<{ kind: string; name_fr: string; location_id?: string | null }> | null;
}

/** A name as a mark is matched: case and spacing aside. */
export function foldName(name: string): string {
  return name.toLocaleLowerCase('fr').split(/\s+/).filter(Boolean).join(' ');
}

/** The detail's things with the flag's value written in, as the kit draws them. */
export function detailThings(spec: DetailSpec, value?: string): RoomThing[] {
  const v = value && value.trim() ? value.trim() : (spec.flag?.example ?? '');
  return spec.things.map((t) => (t.text ? { ...t, text: t.text.map((s) => s.split('{value}').join(v)) } : t));
}

/**
 * The value a season flag holds for a detail, or null when the story has not set it: a word (the
 * learner's order) is shown, a flag that is only true is laid with its example, and an empty
 * word, false or nothing waits.
 */
export function flagValue(flags: Record<string, unknown> | null | undefined, key: string): string | null {
  const v = flags ? flags[key] : undefined;
  if (typeof v === 'string') return v.trim() ? v.trim() : null;
  if (typeof v === 'number' && Number.isFinite(v)) return String(v);
  return v === true ? '' : null;
}

/** The details the learner's story set: a flag it set (with its value; `undefined`: the example) or a mark it left. */
export function setBy(specs: DetailSpec[], world: LearnerWorld | null | undefined): Array<{ spec: DetailSpec; value?: string }> {
  const left = new Set(
    (world?.marks ?? [])
      .filter((m) => m && m.kind === 'thing' && typeof m.name_fr === 'string')
      .map((m) => `${foldName(m.name_fr)}@${m.location_id ?? ''}`),
  );
  const out: Array<{ spec: DetailSpec; value?: string }> = [];
  specs.forEach((spec) => {
    if (spec.flag) {
      const v = flagValue(world?.flags, spec.flag.key);
      if (v !== null) out.push({ spec, value: v || undefined });
    } else if (spec.mark && left.has(`${foldName(spec.mark.name_fr)}@${spec.mark.location_id}`)) {
      out.push({ spec });
    }
  });
  return out;
}

/** Lay a detail into its place's build. */
export function buildDetail(B: Build, spec: DetailSpec, value?: string) {
  detailThings(spec, value).forEach((t, i) => buildThing(B, t, 900 + i));
}
