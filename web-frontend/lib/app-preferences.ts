export type AppTheme = 'light' | 'dark' | 'system';
export type AppFontSize = 'small' | 'medium' | 'large';

export const VISUAL_SETTINGS_STORAGE_KEY = 'atelier.visualSettings';

export interface VisualSettings {
  theme: AppTheme;
  fontSize: AppFontSize;
}

const fallbackSettings: VisualSettings = {
  theme: 'system',
  fontSize: 'medium',
};

function isTheme(value: unknown): value is AppTheme {
  return value === 'light' || value === 'dark' || value === 'system';
}

function isFontSize(value: unknown): value is AppFontSize {
  return value === 'small' || value === 'medium' || value === 'large';
}

/** WP-83: the browser bar's colour per theme — the paper of each (`--app-paper`). */
export const THEME_COLORS = { light: '#f1ece1', dark: '#171510' } as const;

export function applyVisualSettings(theme: AppTheme = 'system', fontSize: AppFontSize = 'medium') {
  if (typeof document === 'undefined') return;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.fontSize = fontSize;
  syncThemeColor(theme);
}

/**
 * `_document` ships one `theme-color` per colour scheme. A theme chosen in
 * Réglages pins both to that theme's paper; `system` gives each its own back.
 */
export function syncThemeColor(theme: AppTheme) {
  if (typeof document === 'undefined') return;
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach((meta) => {
    const scheme = (meta.getAttribute('media') || '').includes('dark') ? 'dark' : 'light';
    meta.setAttribute('content', THEME_COLORS[theme === 'system' ? scheme : theme]);
  });
}

export function readStoredVisualSettings(): VisualSettings {
  if (typeof window === 'undefined') return fallbackSettings;

  try {
    const parsed = JSON.parse(window.localStorage.getItem(VISUAL_SETTINGS_STORAGE_KEY) || '{}');
    if (!parsed || typeof parsed !== 'object') return fallbackSettings;
    return {
      theme: isTheme(parsed.theme) ? parsed.theme : fallbackSettings.theme,
      fontSize: isFontSize(parsed.fontSize) ? parsed.fontSize : fallbackSettings.fontSize,
    };
  } catch {
    return fallbackSettings;
  }
}

export function persistVisualSettings(theme: AppTheme, fontSize: AppFontSize) {
  applyVisualSettings(theme, fontSize);
  if (typeof window === 'undefined') return;

  window.localStorage.setItem(
    VISUAL_SETTINGS_STORAGE_KEY,
    JSON.stringify({ theme, fontSize })
  );
}
