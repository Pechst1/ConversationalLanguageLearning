export const fontFamilies = {
  regular: 'System',
  medium: 'System',
  bold: 'System'
} as const;

export const fontSizes = {
  caption: 12,
  body: 16,
  subtitle: 18,
  title: 24,
  headline: 32
} as const;

export const lineHeights = {
  tight: 1.2,
  normal: 1.4,
  relaxed: 1.6
} as const;

export type FontFamily = keyof typeof fontFamilies;
export type FontSize = keyof typeof fontSizes;
export type LineHeight = keyof typeof lineHeights;
