export const colors = {
  background: '#FFFFFF',
  surface: '#F5F5F5',
  primary: '#0066FF',
  primaryDark: '#0044AA',
  accent: '#FFB400',
  text: '#1A1A1A',
  textSecondary: '#4F4F4F',
  border: '#E0E0E0',
  success: '#2E7D32',
  error: '#C62828'
} as const;

export type ColorName = keyof typeof colors;
