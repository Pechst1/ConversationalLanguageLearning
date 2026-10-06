/**
 * WP-S8 — «La Forge» on the pilot dashboard: the wire shape of
 * `GET /analytics/pilot-forge` and the pure helpers the section renders with.
 *
 * Every number is the server's; nothing here computes a metric. A value the
 * server could not measure (`null`) reads «n/a», never 0.
 */

export type Distribution = { n: number; median: number | null; p90: number | null };

export type ForgeRuleMetrics = {
  items_to_proficient: Distribution;
  items_to_held: Distribution;
  days_to_held: Distribution;
  lapse_after_held: { returned: number; lapsed: number; rate: number | null };
  test_out: { finished: number; passed: number; pass_rate: number | null };
};

export type ForgeSeanceMetrics = {
  started: number;
  completed: number;
  abandoned: number;
  still_open: number;
  completion_rate: number | null;
  abandon_rate: number | null;
  active_minutes: Distribution;
  items: { median: number | null };
  abandon_reasons: Record<string, number>;
};

export type ForgeLatencyRow = {
  rung: string;
  n: number;
  local_p50_ms: number | null;
  local_p95_ms: number | null;
  async_n: number;
  async_p50_ms: number | null;
  async_p95_ms: number | null;
  verdict_changed: number;
};

export type ForgeSection = {
  learners: number;
  rules: ForgeRuleMetrics;
  seances: ForgeSeanceMetrics;
  latency: { by_rung: ForgeLatencyRow[]; local_p95_ms: number | null };
};

export type ForgeWindow = {
  days: number;
  since: string;
  overall: ForgeSection;
  by_band: Array<ForgeSection & { band: string }>;
};

export type PilotForge = { generated_at: string; windows: ForgeWindow[] };

export const ALL_BANDS = 'all';

/** The section for a window and a band («all» = every learner). */
export function forgeSectionFor(
  report: PilotForge | null | undefined,
  days: number,
  band: string = ALL_BANDS,
): ForgeSection | null {
  const window = report?.windows?.find((item) => item.days === days);
  if (!window) return null;
  if (band === ALL_BANDS) return window.overall;
  return window.by_band.find((item) => item.band === band) ?? null;
}

/** The bands with data in a window, in report order. */
export function forgeBands(report: PilotForge | null | undefined, days: number): string[] {
  const window = report?.windows?.find((item) => item.days === days);
  return window ? window.by_band.map((item) => item.band) : [];
}

export function rateLabel(value: number | null | undefined): string {
  return value === null || value === undefined ? 'n/a' : `${Math.round(value * 100)} %`;
}

export function numberLabel(value: number | null | undefined, unit = ''): string {
  if (value === null || value === undefined) return 'n/a';
  const rounded = Math.round(value * 10) / 10;
  return `${rounded}${unit}`;
}

/** «23 · p90 41 (n = 12)», or «n/a (n = 0)» when nothing was measured. */
export function distributionLabel(value: Distribution | null | undefined, unit = ''): string {
  if (!value || !value.n) return 'n/a (n = 0)';
  const p90 = value.p90 === null || value.p90 === undefined ? '' : ` · p90 ${numberLabel(value.p90, unit)}`;
  return `${numberLabel(value.median, unit)}${p90} (n = ${value.n})`;
}

/** The rung names, as the séance's header names them. */
const RUNG_LABELS: Record<string, string> = {
  recognise: 'Recognise',
  discriminate: 'Discriminate',
  build: 'Build',
  transform: 'Transform',
  produce: 'Produce',
  free_use: 'Free use',
};

export function rungLabel(rung: string): string {
  return RUNG_LABELS[rung] ?? rung;
}

/** WP-S1's bars: p95 under 300 ms for every key-graded rung; free production
 *  (produce, free use) shows its local verdict in under 500 ms. */
export function localTargetMs(rung: string): number {
  return rung === 'produce' || rung === 'free_use' ? 500 : 300;
}

export function latencyOverTarget(row: ForgeLatencyRow): boolean {
  return row.local_p95_ms !== null && row.local_p95_ms > localTargetMs(row.rung);
}
