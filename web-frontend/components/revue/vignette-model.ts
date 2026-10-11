/**
 * WP-120 §4 · the vignette, as pure functions: sizes, the week number, the label,
 * and the client-side pictogram sanitiser.
 *
 * The server already validated the pictogram in the house grammar
 * (`app/services/revue/pictogram.py`); the client does not trust that. It rebuilds
 * the markup from the same whitelist — only `path`, `circle`, `rect`, `ellipse`,
 * only geometry and paint attributes, only numbers, `#hex` colours and path data
 * made of `M L C Q Z` and numbers — and drops everything else (elements, text,
 * attributes, entities). Nothing from the input is echoed except values that
 * match those patterns, so the result is safe to inline.
 */

export type VignetteRing = 'headline' | 'question' | 'report';
export type VignetteSize = 'pin' | 'seal' | 'large';

export const VIGNETTE_RINGS: readonly VignetteRing[] = ['headline', 'question', 'report'];
/** Rendered diameter in CSS px. */
export const VIGNETTE_SIZE_PX: Record<VignetteSize, number> = { pin: 28, seal: 64, large: 160 };

/** The pictogram's own viewBox (house grammar). */
export const PICTOGRAM_VIEWBOX = '0 0 100 100';

const SHAPES: Record<string, readonly string[]> = {
  path: ['d'],
  circle: ['cx', 'cy', 'r'],
  rect: ['x', 'y', 'width', 'height', 'rx', 'ry'],
  ellipse: ['cx', 'cy', 'rx', 'ry'],
};
const PAINT = ['fill', 'stroke', 'stroke-width', 'stroke-linejoin', 'stroke-linecap', 'fill-rule'] as const;
const ENUMS: Record<string, readonly string[]> = {
  'stroke-linejoin': ['round', 'miter', 'bevel'],
  'stroke-linecap': ['round', 'butt', 'square'],
  'fill-rule': ['nonzero', 'evenodd'],
};
const NUMBER = /^-?(?:\d+\.?\d*|\.\d+)$/;
const COLOUR = /^(?:#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}|none)$/;
const PATH_DATA = /^[MLCQZ0-9.,\s-]+$/;
const TAG = /<\s*([a-zA-Z][\w:.-]*)((?:\s+[^\s=/>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*\/?\s*>/g;
const ATTR = /([^\s=/>]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g;
const SKIP_CONTENT = /<\s*(script|style|text|title|desc|foreignObject|metadata)\b[\s\S]*?<\s*\/\s*\1\s*>/gi;

function safeValue(name: string, value: string): string | null {
  const v = value.trim();
  if (name === 'd') return PATH_DATA.test(v) && /^M/.test(v) ? v.replace(/\s+/g, ' ') : null;
  if (name === 'fill' || name === 'stroke') return COLOUR.test(v) ? v : null;
  if (name in ENUMS) return ENUMS[name].includes(v) ? v : null;
  return NUMBER.test(v) ? v : null;
}

/**
 * The pictogram's shapes, rebuilt from the whitelist (no `<svg>` wrapper): ready to
 * inline inside the stamp's nested `<svg viewBox="0 0 100 100">`.
 */
export function sanitisePictogram(svg: string | null | undefined): string {
  if (!svg || typeof svg !== 'string') return '';
  // Comments, CDATA and whole forbidden elements (with their content) go first.
  const text = svg
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<!\[CDATA\[[\s\S]*?\]\]>/g, '')
    .replace(/<!DOCTYPE[\s\S]*?>/gi, '')
    .replace(SKIP_CONTENT, '');
  const out: string[] = [];
  const tags = new RegExp(TAG.source, 'g');
  for (let match = tags.exec(text); match; match = tags.exec(text)) {
    const tag = match[1].toLowerCase();
    const allowed = SHAPES[tag];
    if (!allowed) continue;
    const attrs: string[] = [];
    const seen = new Set<string>();
    let poisoned = false;
    const source = match[2] || '';
    const attrRe = new RegExp(ATTR.source, 'g');
    for (let attr = attrRe.exec(source); attr; attr = attrRe.exec(source)) {
      const name = attr[1].toLowerCase();
      if (seen.has(name)) continue;
      if (!allowed.includes(name) && !(PAINT as readonly string[]).includes(name)) continue;
      const value = safeValue(name, attr[2] ?? attr[3] ?? attr[4] ?? '');
      if (value == null) {
        // A fill or path the grammar cannot read drops the whole shape (never a default black).
        if (name === 'fill' || name === 'd') poisoned = true;
        continue;
      }
      seen.add(name);
      attrs.push(`${name}="${value}"`);
    }
    if (poisoned || (tag === 'path' && !seen.has('d'))) continue;
    out.push(`<${tag} ${attrs.join(' ')}/>`);
    if (out.length >= 12) break;
  }
  return out.join('');
}

/** `"2026-W40"` → `40`; anything else → `null`. */
export function weekNumber(week: string | null | undefined): number | null {
  const match = /^\d{4}-W(\d{2})$/.exec(String(week ?? ''));
  return match ? Number(match[1]) : null;
}

export function isVignetteRing(value: unknown): value is VignetteRing {
  return (VIGNETTE_RINGS as readonly unknown[]).includes(value);
}

const RING_FR: Record<VignetteRing, string> = {
  headline: 'un titre',
  question: 'une question de lecteur',
  report: 'un compte rendu',
};

/** The stamp's accessible name, in French like the stamp itself. */
export function vignetteLabel({
  week,
  placeLabelFr,
  ring,
  keptContribution,
}: {
  week: string;
  placeLabelFr: string;
  ring: VignetteRing;
  keptContribution: boolean;
}): string {
  const no = weekNumber(week);
  const parts = [no != null ? `Vignette, semaine ${no}` : 'Vignette'];
  if (placeLabelFr) parts.push(placeLabelFr);
  parts.push(`tu as fait ${RING_FR[ring]}`);
  if (keptContribution) parts.push('ta part est dans la dépêche');
  return parts.join(' · ');
}
