import { Capacitor } from '@capacitor/core';

export function isNativePlatform() {
  return typeof window !== 'undefined' && Capacitor.isNativePlatform();
}
