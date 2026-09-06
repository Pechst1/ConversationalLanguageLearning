/* Feuilleton panel images persisted with GRAPHIC_NOVEL_IMAGE_STORAGE=local are
   served by the API at /media/…. On the web the Next proxy rewrites that path to
   the API host; the native build talks to the API directly, so a bare "/media/…"
   would resolve against the app bundle and 404. Resolve it against the API origin. */
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || '').trim();

function apiOrigin(): string {
  if (!API_BASE) return '';
  try {
    return new URL(API_BASE).origin;
  } catch {
    return '';
  }
}

export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const value = String(url).trim();
  if (!value) return null;
  if (/^(https?:|data:|blob:)/i.test(value)) return value;
  if (value.startsWith('/media/')) {
    const origin = apiOrigin();
    return origin ? `${origin}${value}` : value;
  }
  return value;
}
