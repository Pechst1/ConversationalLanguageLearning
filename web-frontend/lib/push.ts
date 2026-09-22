/**
 * WP-80 — the device side of push: what this build can do, what the OS has
 * been told, and the one call that asks it. The decision of *when* to ask
 * lives in `push-opt-in.ts`; this file only talks to Capacitor and the browser.
 *
 * Native push is on by default in the native build (`build-native.mjs`); web
 * push stays off unless the server has VAPID keys — without them a browser
 * subscription could never be delivered to, so it is not offered.
 */

import { Capacitor } from '@capacitor/core';
import { PushNotifications } from '@capacitor/push-notifications';

import apiService from '@/services/api';

import { nativePushIsAvailable, registerNativePushToken } from './native-push';
import { normalizePermission, type PushCapability, type PushPermission } from './push-opt-in';

export type PushAvailability = { capability: PushCapability; permission: PushPermission };

const NONE: PushAvailability = { capability: 'none', permission: 'unknown' };

async function vapidPublicKey(): Promise<string | null> {
  try {
    const response: any = await apiService.getVapidPublicKey();
    const key = (response?.publicKey ?? response?.data?.publicKey ?? '') as string;
    return key.trim() ? key.trim() : null;
  } catch {
    return null;
  }
}

/** What this device can do right now. Never throws; `none` when unsure. */
export async function pushAvailability(): Promise<PushAvailability> {
  if (typeof window === 'undefined') return NONE;
  try {
    if (Capacitor.isNativePlatform()) {
      if (!nativePushIsAvailable()) return NONE;
      const status = await PushNotifications.checkPermissions();
      return { capability: 'native', permission: normalizePermission(status.receive) };
    }
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      return NONE;
    }
    if (!(await vapidPublicKey())) return NONE;
    return { capability: 'web', permission: normalizePermission(Notification.permission) };
  } catch {
    return NONE;
  }
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  const output = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) output[index] = raw.charCodeAt(index);
  return output;
}

/**
 * Ask the OS (the one system dialog) and register the device with the server.
 * Resolves `true` when a subscription was stored. Never throws.
 */
export async function enablePush(capability: PushCapability): Promise<boolean> {
  try {
    if (capability === 'native') {
      const token = await registerNativePushToken();
      await apiService.subscribeToNativeNotifications(token);
      return true;
    }
    if (capability === 'web') {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') return false;
      const publicKey = await vapidPublicKey();
      if (!publicKey) return false;
      const registration = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
      });
      await apiService.subscribeToNotifications(subscription.toJSON());
      return true;
    }
  } catch (error) {
    console.info('Push was not enabled.', error);
  }
  return false;
}
