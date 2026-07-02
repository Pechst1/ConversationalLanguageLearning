import { Haptics, ImpactStyle, NotificationType } from '@capacitor/haptics';

import { isNativePlatform } from '@/lib/native-platform';

export type AppHapticKind = 'selection' | 'correct' | 'repair' | 'complete' | 'token';

function reducedMotionPreferred() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

function vibrateBrowser(kind: AppHapticKind) {
  const vibrate = (navigator as Navigator & { vibrate?: (pattern: number[]) => boolean }).vibrate;
  if (!vibrate) return;

  const pattern = kind === 'correct'
    ? [12]
    : kind === 'token'
      ? [12, 26, 12]
      : kind === 'complete'
        ? [18, 28, 18]
        : kind === 'repair'
          ? [10, 24, 10]
          : [8];
  try {
    navigator.vibrate(pattern);
  } catch {
    // Browser vibration support varies; never let it interrupt the user flow.
  }
}

export function pulseAppHaptic(kind: AppHapticKind = 'selection') {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return;
  if (reducedMotionPreferred()) return;

  if (isNativePlatform()) {
    void (async () => {
      try {
        if (kind === 'token' || kind === 'complete') {
          await Haptics.notification({ type: NotificationType.Success });
        } else if (kind === 'repair') {
          await Haptics.notification({ type: NotificationType.Warning });
        } else {
          await Haptics.impact({ style: kind === 'selection' ? ImpactStyle.Light : ImpactStyle.Medium });
        }
      } catch {
        vibrateBrowser(kind);
      }
    })();
    return;
  }

  vibrateBrowser(kind);
}
