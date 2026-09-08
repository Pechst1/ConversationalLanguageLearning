import Head from 'next/head';
import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import RouteAuthGate from '@/components/auth/RouteAuthGate';
import Layout from '@/components/layout/Layout';
import { AppAuthProvider, useAppSession } from '@/lib/app-auth';
import { listenForNativePushActions } from '@/lib/native-push';
import apiService from '@/services/api';
import {
  accountScopeKey,
  consumeResumeSuppression,
  suppressResumeRedirectOnce,
  syncAccountScope,
} from '@/lib/pilot-resilience';
import { resolveResumeHref } from '@/lib/journey-resume';
import { installKeyboardFocusGuard, installKeyboardInsets } from '@/lib/journey-lifecycle';
import { isNativePlatform } from '@/lib/native-platform';
import '@/styles/globals.css';
// Atelier V2 design system (WP-01). Next only permits a global stylesheet to be
// imported from _app, so it is loaded here rather than from the components that
// use it. Everything in the file is scoped under `.av2` or is an @font-face, so
// a page that never renders <AtelierV2Root> is unaffected by its presence.
import '@/styles/atelier-v2.css';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * Root lifecycle for interruption recovery (WP-10).
 *
 * Sits inside `AppAuthProvider` because it needs the signed-in identity, and
 * above every page because both of its jobs outlive a route:
 *
 *   * **Account scope.** Sign-out already sweeps the `pilot:` caches. This
 *     covers the cases where no sign-out ever runs — a cold start holding a
 *     restored token for a different learner, a native reinstall from backup, a
 *     session swapped underneath a suspended app. The first render after the
 *     identity changes clears the previous learner's caches, so a second
 *     account can never be shown the first one's scene, draft or progress.
 *   * **Software keyboard.** Publishes `--app-keyboard-inset` and keeps the
 *     focused field *and* its primary action above the keyboard. Generic:
 *     it keys off focus and document order, not off any renderer's markup.
 */
function AppLifecycle() {
  const session = useAppSession();
  const identity = session.data?.user?.id || session.data?.user?.email || '';

  useEffect(() => {
    if (session.status === 'loading') return;
    syncAccountScope(accountScopeKey(identity));
  }, [identity, session.status]);

  useEffect(() => installKeyboardInsets(), []);
  useEffect(() => installKeyboardFocusGuard(), []);

  return null;
}

export default function App({
  Component,
  pageProps: { session, ...pageProps },
}: AppProps) {
  const router = useRouter();

  useEffect(() => {
    document.querySelectorAll('[data-next-hide-fouc]').forEach((element) => element.remove());
  }, []);

  useEffect(() => {
    let removeListener: (() => Promise<void>) | null = null;
    let active = true;
    listenForNativePushActions((route, data) => {
      // A tapped notification is an explicit destination; the resume redirect
      // below is a guess. Claim the next navigation so the guess cannot win.
      // Nothing is discarded by going there: an unsent draft lives in the
      // account-scoped recovery cache, keyed by journey and step, so it is
      // still waiting when the learner comes back.
      suppressResumeRedirectOnce();
      void apiService.recordNotificationTap({
        route,
        kind: typeof data.kind === 'string' ? data.kind : undefined,
        notification_id: typeof data.notification_id === 'string' ? data.notification_id : undefined,
      }).catch(() => undefined).finally(() => {
        void router.push(route);
      });
    })
      .then((remove) => {
        if (!active && remove) void remove();
        else removeListener = remove;
      })
      .catch((error) => {
        console.warn('Native push action listener could not start.', error);
      });
    return () => {
      active = false;
      if (removeListener) void removeListener();
    };
  }, [router]);

  useEffect(() => {
    if (!router.isReady || !isNativePlatform()) return;
    if (!['/', '/atelier'].includes(router.pathname)) return;
    // A deep link that just claimed this navigation outranks the stored guess.
    if (consumeResumeSuppression()) return;
    // WP-20 (WP-19 defect D-1): an open V2 journey outranks the stored legacy
    // practice session, which is what used to win here and land a cold start in
    // the wrong Séance. `resolveResumeHref` falls back to the stored activity
    // unchanged whenever no journey is open.
    const href = resolveResumeHref();
    if (href && href !== router.asPath) void router.replace(href);
  }, [router]);

  useEffect(() => {
    let sent = false;
    const report = (message: string, stack?: string) => {
      if (sent) return;
      sent = true;
      void apiService.recordClientError({
        message: message.slice(0, 1000),
        stack: stack?.slice(0, 12000),
        route: window.location.pathname,
        source: isNativePlatform() ? 'capacitor' : 'web',
      }).catch(() => undefined);
      window.setTimeout(() => { sent = false; }, 5000);
    };
    const onError = (event: ErrorEvent) => report(event.message || 'Unhandled client error', event.error?.stack);
    const onRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      report(reason instanceof Error ? reason.message : String(reason), reason instanceof Error ? reason.stack : undefined);
    };
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onRejection);
    };
  }, []);

  return (
    <AppAuthProvider session={session}>
      <AppLifecycle />
      <QueryClientProvider client={queryClient}>
        <Head>
          <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
          <meta name="theme-color" content="#f1ece1" />
          <meta name="apple-mobile-web-app-capable" content="yes" />
          <meta name="apple-mobile-web-app-title" content="Atelier" />
          <meta name="apple-mobile-web-app-status-bar-style" content="default" />
          <link rel="manifest" href="/manifest.webmanifest" />
          <link rel="apple-touch-icon" href="/icons/atelier-mark.svg" />
        </Head>
        <Layout>
          <RouteAuthGate>
            <Component {...pageProps} />
          </RouteAuthGate>
        </Layout>
      </QueryClientProvider>
    </AppAuthProvider>
  );
}
