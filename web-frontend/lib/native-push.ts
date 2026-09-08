import { Capacitor, type PluginListenerHandle } from '@capacitor/core';
import { PushNotifications } from '@capacitor/push-notifications';

export function nativePushIsAvailable(): boolean {
  return process.env.NEXT_PUBLIC_NATIVE_PUSH_ENABLED === 'true'
    && Capacitor.isNativePlatform()
    && Capacitor.isPluginAvailable('PushNotifications');
}

export async function registerNativePushToken(): Promise<string> {
  if (!nativePushIsAvailable()) {
    throw new Error('Native push is not available in this build.');
  }

  const current = await PushNotifications.checkPermissions();
  const permission = current.receive === 'prompt' || current.receive === 'prompt-with-rationale'
    ? await PushNotifications.requestPermissions()
    : current;
  if (permission.receive !== 'granted') {
    throw new Error('Notification permission was not granted.');
  }

  return new Promise<string>(async (resolve, reject) => {
    let settled = false;
    const handles: PluginListenerHandle[] = [];
    const finish = async (result: { token?: string; error?: Error }) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      await Promise.all(handles.map((handle) => handle.remove()));
      if (result.error) reject(result.error);
      else resolve(result.token || '');
    };
    const timeout = window.setTimeout(
      () => void finish({ error: new Error('Apple did not return a device token in time.') }),
      15_000,
    );

    try {
      handles.push(
        await PushNotifications.addListener('registration', ({ value }) => {
          void finish({ token: value });
        }),
      );
      handles.push(
        await PushNotifications.addListener('registrationError', ({ error }) => {
          void finish({ error: new Error(error || 'Apple push registration failed.') });
        }),
      );
      await PushNotifications.register();
    } catch (error) {
      await finish({ error: error instanceof Error ? error : new Error(String(error)) });
    }
  });
}

export async function listenForNativePushActions(
  navigate: (route: string, data: Record<string, unknown>) => void,
): Promise<(() => Promise<void>) | null> {
  if (!nativePushIsAvailable()) return null;
  const handle = await PushNotifications.addListener(
    'pushNotificationActionPerformed',
    ({ notification }) => {
      const route = notification?.data?.route;
      if (typeof route === 'string' && route.startsWith('/')) {
        navigate(route, notification?.data || {});
      }
    },
  );
  return () => handle.remove();
}
