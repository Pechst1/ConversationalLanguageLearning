/**
 * WP-94 «Numéro spécial» + WP-95 «Le Carnet» — the pure model.
 *
 * Everything the special edition, the épreuve recap, Home's next-step line and
 * the Carnet decide lives here, so the node suite (`lib/can-dos.test.js`) can
 * prove it without a DOM. Every reader is defensive: an older server sends none
 * of these fields, and a missing field is a missing line — never a placeholder.
 *
 * Contracts (read, never invented):
 *   journey snapshot  `special: "epreuve" | null`,
 *                     `epreuve: { band, can_dos: [{ id, title_fr, title_native }] } | null`
 *   recap             `epreuve_result: "passed" | "failed" | null`, `epreuve_line_fr`
 *   level payload     `next_can_do: { id, title_fr, title_native, band } | null`,
 *                     `can_dos_stamped`, `can_dos_total`
 *   GET /can-dos      `{ current_band, bands: [{ band, title_native, can_dos: [...] }] }`
 */

import { castIdFor } from '@/lib/cast-faces';
import type { ControlLanguage } from '@/types/daily-journey';

import { canDoCopy, fill } from './can-do-copy';

export type CanDoTitle = { id: string; title_fr: string; title_native?: string | null };

export type NextCanDo = CanDoTitle & { band: string | null };

export type CanDoSource = 'scene' | 'epreuve' | 'authored';

export type CanDoEntry = CanDoTitle & {
  stamped_at?: string | null;
  source?: CanDoSource | null;
  scene_id?: string | null;
  scene_title_fr?: string | null;
  character_id?: string | null;
  quote_fr?: string | null;
};

export type CanDoBand = { band: string; title_native?: string | null; can_dos: CanDoEntry[] };

export type CanDosPayload = { current_band: string | null; bands: CanDoBand[] };

export type EpreuveInfo = { band: string | null; canDos: CanDoTitle[] };

const isRecord = (value: unknown): value is Record<string, any> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const str = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

function canDoTitleOf(raw: unknown): CanDoTitle | null {
  if (!isRecord(raw)) return null;
  const id = str(raw.id) || str(raw.can_do_id);
  const titleFr = str(raw.title_fr);
  const titleNative = str(raw.title_native);
  if (!id || (!titleFr && !titleNative)) return null;
  return { id, title_fr: titleFr || titleNative, title_native: titleNative || null };
}

/** The can-do's title in the chrome language: French chrome reads `title_fr`. */
export function canDoTitle(canDo: CanDoTitle, language: ControlLanguage): string {
  if (language === 'fr') return canDo.title_fr || canDo.title_native || '';
  return canDo.title_native || canDo.title_fr || '';
}

/* ------------------------------------------------------------------ */
/* Band order                                                          */
/* ------------------------------------------------------------------ */

/** «A1.2» → a sortable rank; unknown shapes sort last (and stay in payload order). */
export function bandRank(band: unknown): number {
  const match = /^([ABC])([12])(?:\.(\d+))?$/i.exec(str(band));
  if (!match) return Number.POSITIVE_INFINITY;
  const letter = 'ABC'.indexOf(match[1].toUpperCase());
  return letter * 1000 + Number(match[2]) * 100 + Number(match[3] ?? 0);
}

/* ------------------------------------------------------------------ */
/* Dates                                                               */
/* ------------------------------------------------------------------ */

const LOCALE: Record<ControlLanguage, string> = { en: 'en-GB', de: 'de-DE', fr: 'fr-FR' };

function parseDay(value: unknown): Date | null {
  const raw = str(value);
  if (!raw) return null;
  // A bare local date is read at noon so no timezone moves it a day.
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(raw) ? new Date(`${raw}T12:00:00`) : new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** «28 sept.» / «28 Sept» / «28. Sept.» — `null` for an unreadable date. */
export function carnetDate(value: unknown, language: ControlLanguage): string | null {
  const parsed = parseDay(value);
  if (!parsed) return null;
  try {
    return new Intl.DateTimeFormat(LOCALE[language] ?? 'en-GB', { day: 'numeric', month: 'short' }).format(parsed);
  } catch {
    return null;
  }
}

/** The local day `days` after `localDate`, as «5 octobre» — `null` when unreadable. */
export function dayAfter(localDate: unknown, days: number, language: ControlLanguage): string | null {
  const parsed = parseDay(localDate);
  if (!parsed) return null;
  const next = new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate() + days, 12);
  try {
    return new Intl.DateTimeFormat(LOCALE[language] ?? 'en-GB', { day: 'numeric', month: 'long' }).format(next);
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------------ */
/* Cast names                                                          */
/* ------------------------------------------------------------------ */

const CAST_NAMES: Record<string, string> = {
  romy_tremblay: 'Romy',
  marin_leveque: 'Marin',
  lila_bonnet: 'Lila',
  margaux_barman: 'Margaux',
  augustin_de_roncourt: 'Gus',
  landlord_marchand: 'M. Marchand',
};

/** A character id → the name the story calls them, or `null` for someone unknown. */
export function castName(characterId: unknown): string | null {
  const id = castIdFor(str(characterId));
  return id ? CAST_NAMES[id] ?? null : null;
}

/* ------------------------------------------------------------------ */
/* WP-94 — the special edition                                         */
/* ------------------------------------------------------------------ */

function epreuveFrom(holder: unknown): EpreuveInfo | null {
  if (!isRecord(holder) || holder.special !== 'epreuve') return null;
  const raw = isRecord(holder.epreuve) ? holder.epreuve : {};
  const canDos = (Array.isArray(raw.can_dos) ? raw.can_dos : [])
    .map(canDoTitleOf)
    .filter((item: CanDoTitle | null): item is CanDoTitle => item !== null);
  return { band: str(raw.band) || null, canDos };
}

/**
 * Today is a special edition (`special: "epreuve"`). Reads the journey
 * snapshot, or — before a journey exists — the envelope's offered scenario or
 * the envelope itself. `null` on every ordinary day and on older servers.
 */
export function epreuveOf(source: unknown): EpreuveInfo | null {
  if (!isRecord(source)) return null;
  return (
    epreuveFrom(source) ??
    epreuveFrom(source.journey) ??
    epreuveFrom(source.available) ??
    epreuveFrom(isRecord(source.journey) ? source.journey.scenario : null) ??
    epreuveFrom(source.scenario) ??
    null
  );
}

/** «Aujourd’hui, montrez que vous savez : commander au café · demander un prix» — at most `max`, then «…». */
export function specialListLine(canDos: CanDoTitle[], language: ControlLanguage, max = 3): string | null {
  const titles = canDos.map((canDo) => canDoTitle(canDo, language)).filter(Boolean);
  if (!titles.length) return null;
  const shown = titles.slice(0, max).join(' · ');
  const list = titles.length > max ? `${shown} · …` : shown;
  return fill(canDoCopy(language).special_list, { list });
}

export type EpreuveRecapView =
  | {
      result: 'passed';
      band: string | null;
      title: string;
      sealTop: string;
      sealCaption: string;
      sealLabel: string;
      lineFr: string | null;
    }
  | {
      result: 'failed';
      title: string;
      body: string;
      lineFr: string | null;
      next: string;
    };

/**
 * The recap's épreuve moment. `passed`: an oversized seal stamped with the band
 * just closed and the host's line; `failed`: the kind line and the next special
 * edition's date. `null` on every other day.
 */
export function epreuveRecapView(
  journey: unknown,
  recap: unknown,
  language: ControlLanguage,
): EpreuveRecapView | null {
  if (!isRecord(recap)) return null;
  const result = recap.epreuve_result;
  if (result !== 'passed' && result !== 'failed') return null;
  const copy = canDoCopy(language);
  const lineFr = str(recap.epreuve_line_fr) || null;
  const localDate = isRecord(journey) ? journey.local_date : null;
  if (result === 'failed') {
    const date = dayAfter(localDate, 7, language);
    return {
      result,
      title: copy.epreuve_failed_title,
      body: copy.epreuve_failed_body,
      lineFr,
      next: date ? fill(copy.epreuve_next, { date }) : copy.epreuve_next.replace(/\s*\(\{date\}\)/, ''),
    };
  }
  const levelUp = isRecord(recap.level_up) ? recap.level_up : null;
  const band =
    epreuveOf(journey)?.band || str(levelUp?.from_level) || str(recap.level) || null;
  const date = carnetDate(localDate, 'fr');
  return {
    result,
    band,
    title: band ? fill(copy.epreuve_passed_title, { band }) : copy.special_kicker,
    sealTop: copy.epreuve_seal_top,
    sealCaption: [band, date].filter(Boolean).join(' · '),
    sealLabel: band ? fill(copy.epreuve_passed_aria, { band }) : copy.special_kicker,
    lineFr,
  };
}

/* ------------------------------------------------------------------ */
/* WP-95 — Home's next step                                            */
/* ------------------------------------------------------------------ */

export type NextStepView = {
  band: string | null;
  /** «Prochaine étape : demander un prix et payer» — or «Tout A1.1 est tamponné». */
  line: string;
  ariaLabel: string;
  href: string;
};

export const CARNET_HREF = '/notebook?mode=carnet';

/** Reads `next_can_do` from the level payload (or its `coverage`), wherever the server put it. */
export function nextCanDoOf(...sources: unknown[]): { next: NextCanDo | null; stamped: number | null; total: number | null } {
  for (const source of sources) {
    if (!isRecord(source)) continue;
    for (const holder of [source, source.coverage, source.cefr, source.level]) {
      if (!isRecord(holder) || !('next_can_do' in holder)) continue;
      const title = canDoTitleOf(holder.next_can_do);
      const stamped = Number.isFinite(Number(holder.can_dos_stamped)) && holder.can_dos_stamped != null
        ? Number(holder.can_dos_stamped)
        : null;
      const total = Number.isFinite(Number(holder.can_dos_total)) && holder.can_dos_total != null
        ? Number(holder.can_dos_total)
        : null;
      return {
        next: title ? { ...title, band: str((holder.next_can_do as Record<string, unknown>).band) || null } : null,
        stamped,
        total,
      };
    }
  }
  return { next: null, stamped: null, total: null };
}

/**
 * Home's level line (W12): the band code and the next can-do, never a
 * percentage. With no next can-do and every one stamped, it says so; with
 * nothing known, `null` (the band alone is drawn by the caller).
 */
export function nextStepView(
  args: { band?: string | null; next: NextCanDo | null; stamped?: number | null; total?: number | null },
  language: ControlLanguage,
): NextStepView | null {
  const copy = canDoCopy(language);
  const band = str(args.band) || args.next?.band || null;
  if (args.next) {
    const canDo = canDoTitle(args.next, language);
    return {
      band,
      line: fill(copy.next_step, { can_do: canDo }),
      ariaLabel: fill(copy.next_step_aria, { band: band ?? '', can_do: canDo }),
      href: CARNET_HREF,
    };
  }
  const total = Number(args.total ?? 0);
  if (band && total > 0 && Number(args.stamped ?? 0) >= total) {
    const line = fill(copy.band_all_stamped, { band });
    return { band, line, ariaLabel: line, href: CARNET_HREF };
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* WP-95 — the Carnet                                                  */
/* ------------------------------------------------------------------ */

export type CarnetBandState = 'past' | 'current' | 'future';

export type CarnetBandTab = { band: string; state: CarnetBandState; locked: boolean };

export type CarnetItem = {
  id: string;
  title: string;
  titleFr: string;
  stamped: boolean;
  /** «28 sept.» */
  date: string | null;
  /** «Un café au Mistral — Margaux, 28 sept.» */
  line: string | null;
  characterId: string | null;
  characterName: string | null;
  quoteFr: string | null;
  ariaState: string;
  rehearsalHref: string | null;
};

export type CarnetModel = {
  currentBand: string | null;
  bands: CarnetBandTab[];
  selected: {
    band: string;
    state: CarnetBandState;
    locked: boolean;
    lockedNote: string | null;
    count: string;
    stamped: number;
    total: number;
    items: CarnetItem[];
  } | null;
};

/** Répétition (WP-31) opened with the can-do as the situation to rehearse. */
export function rehearsalHref(canDo: CanDoTitle, language: ControlLanguage): string {
  const situation = canDoTitle(canDo, language);
  return situation ? `/repetition?situation=${encodeURIComponent(situation)}` : '/repetition';
}

/** Normalises `GET /can-dos`; anything unreadable is dropped, never guessed. */
export function readCanDos(payload: unknown): CanDosPayload | null {
  if (!isRecord(payload) || !Array.isArray(payload.bands)) return null;
  const bands: CanDoBand[] = [];
  for (const raw of payload.bands) {
    if (!isRecord(raw) || !str(raw.band)) continue;
    const canDos: CanDoEntry[] = [];
    for (const item of Array.isArray(raw.can_dos) ? raw.can_dos : []) {
      const title = canDoTitleOf(item);
      if (!title) continue;
      canDos.push({
        ...title,
        stamped_at: str(item.stamped_at) || null,
        source: item.source === 'scene' || item.source === 'epreuve' || item.source === 'authored' ? item.source : null,
        scene_id: str(item.scene_id) || null,
        scene_title_fr: str(item.scene_title_fr) || null,
        character_id: str(item.character_id) || null,
        quote_fr: str(item.quote_fr) || null,
      });
    }
    bands.push({ band: str(raw.band), title_native: str(raw.title_native) || null, can_dos: canDos });
  }
  return { current_band: str(payload.current_band) || null, bands };
}

function stampLine(item: CanDoEntry, date: string | null, language: ControlLanguage): string | null {
  const copy = canDoCopy(language);
  const what =
    item.scene_title_fr ||
    (item.source === 'epreuve' ? copy.carnet_source_epreuve : item.source === 'authored' ? copy.carnet_source_authored : '');
  const who = castName(item.character_id);
  const tail = [who, date].filter(Boolean).join(', ');
  if (what && tail) return `${what} — ${tail}`;
  return what || tail || null;
}

export function carnetModel(
  payload: CanDosPayload | null,
  selectedBand: string | null | undefined,
  language: ControlLanguage,
): CarnetModel {
  if (!payload || payload.bands.length === 0) return { currentBand: payload?.current_band ?? null, bands: [], selected: null };
  const copy = canDoCopy(language);
  const ordered = payload.bands
    .map((band, index) => ({ band, index }))
    .sort((a, b) => bandRank(a.band.band) - bandRank(b.band.band) || a.index - b.index)
    .map(({ band }) => band);
  const current = payload.current_band && ordered.some((b) => b.band === payload.current_band)
    ? payload.current_band
    : ordered[0].band;
  const currentRank = bandRank(current);
  const tabs: CarnetBandTab[] = ordered.map((b) => {
    const rank = bandRank(b.band);
    const state: CarnetBandState = b.band === current ? 'current' : rank < currentRank ? 'past' : 'future';
    return { band: b.band, state, locked: state === 'future' };
  });
  const chosen = ordered.find((b) => b.band === selectedBand) ?? ordered.find((b) => b.band === current)!;
  const tab = tabs.find((t) => t.band === chosen.band)!;
  const previous = ordered[ordered.indexOf(chosen) - 1]?.band ?? current;

  const items: CarnetItem[] = chosen.can_dos.map((item) => {
    const stamped = Boolean(item.stamped_at) && !tab.locked;
    const date = stamped ? carnetDate(item.stamped_at, language) : null;
    const title = canDoTitle(item, language);
    return {
      id: item.id,
      title,
      titleFr: item.title_fr,
      stamped,
      date,
      line: stamped ? stampLine(item, date, language) : null,
      characterId: stamped && castIdFor(item.character_id) ? String(item.character_id) : null,
      characterName: stamped ? castName(item.character_id) : null,
      quoteFr: stamped ? item.quote_fr ?? null : null,
      ariaState: stamped
        ? date
          ? fill(copy.carnet_stamped_aria, { date })
          : copy.carnet_stamped
        : copy.carnet_unstamped_aria,
      rehearsalHref: tab.locked ? null : rehearsalHref(item, language),
    };
  });
  const stampedCount = items.filter((item) => item.stamped).length;
  return {
    currentBand: current,
    bands: tabs,
    selected: {
      band: chosen.band,
      state: tab.state,
      locked: tab.locked,
      lockedNote: tab.locked ? fill(copy.carnet_band_locked_note, { band: chosen.band, previous }) : null,
      count: stampedCount > 0
        ? fill(copy.carnet_count, { stamped: stampedCount, total: items.length })
        : copy.carnet_count_none,
      stamped: stampedCount,
      total: items.length,
      items,
    },
  };
}
