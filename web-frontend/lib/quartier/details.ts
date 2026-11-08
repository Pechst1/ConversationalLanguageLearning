/**
 * Le Quartier · Le Mistral's details: the small things the season leaves in the café.
 *
 * A place opens when the story first goes there (`world.json`, a room in `world/rooms`); a detail
 * is smaller: a thing in Le Mistral's room that appears when the moment that put it there has
 * been played (the plan's ladder: the learner's usual cup on the zinc after «La même chose», Gus's
 * petition, the party's garlands). The forge writes each one from the canon as a detail file
 * (`world/details/<id>.json`): the season flag it waits on, the moment of the ladder, and the
 * things the room kit draws (`room.ts`), in the quarter's coordinates. A thing's `text` may name
 * the flag's value (`{value}`): the cup is the learner's own order.
 *
 * Until the learner's details come from the server with their season state, nothing shows one:
 * the standalone page lays it with `?detail=<id>&value=<the flag's value>` to look at it.
 */
import { buildThing } from './room';
import type { RoomThing } from './room';
import type { Build } from './kit';
import type { Words } from './memory';

export interface DetailSpec {
  id: string;
  version: number;
  kind: 'detail';
  /** the place it is in (Le Mistral's room, on the quai de Valmy) */
  in: string;
  title: Words;
  /** the line of the plan's ladder it is, and the season's moment that sets it */
  moment: string;
  /** the season flag it waits on (`app/data/season/s1/season.json`), and the value shown when none is given */
  flag: { key: string; example: string };
  things: RoomThing[];
  provenance: { canon: string; scenes: string[] };
}

/** The detail's things with the flag's value written in, as the kit draws them. */
export function detailThings(spec: DetailSpec, value?: string): RoomThing[] {
  const v = value && value.trim() ? value.trim() : spec.flag.example;
  return spec.things.map((t) => (t.text ? { ...t, text: t.text.map((s) => s.split('{value}').join(v)) } : t));
}

/** Lay a detail into Le Mistral's build. */
export function buildDetail(B: Build, spec: DetailSpec, value?: string) {
  detailThings(spec, value).forEach((t, i) => buildThing(B, t, 900 + i));
}
