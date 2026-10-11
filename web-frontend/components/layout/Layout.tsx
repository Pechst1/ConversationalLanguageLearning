import React, { useEffect } from 'react';
import { useRouter } from 'next/router';
import { Toaster } from 'react-hot-toast';
import { motion, AnimatePresence } from 'framer-motion';
import EditorialMasthead from './EditorialMasthead';
import {
  applyVisualSettings,
  persistVisualSettings,
  readStoredVisualSettings,
  type AppFontSize,
  type AppTheme,
} from '@/lib/app-preferences';
import { resolveBrowserApiBaseUrl } from '@/services/api';
import { chromeLanguage } from '@/lib/language-rule';
import {
  readLearnerLanguage,
  readLearnerLevel,
  rememberLearnerLanguage,
  rememberLearnerLevel,
} from '@/lib/learner-language';
import { cn } from '@/lib/utils';
import { useAppSession } from '@/lib/app-auth';
import { isNativePlatform } from '@/lib/native-platform';
import { resolveProductSection, routeUsesOwnProductShell } from '@/lib/product-shell';
import { installViewportMetrics } from '@/lib/viewport-metrics';
import FeedbackWidget from '@/components/feedback/FeedbackWidget';

interface LayoutProps {
  children: React.ReactNode;
  showSidebar?: boolean;
  className?: string;
}

export default function Layout({ children, showSidebar = true, className }: LayoutProps) {
  const router = useRouter();
  const { data: session, status } = useAppSession();

  const isPublicRoute = router.pathname === '/' || router.pathname.startsWith('/auth');
  const usesOwnShell = routeUsesOwnProductShell(router.pathname);
  const showsNavigation = showSidebar && !isPublicRoute && !usesOwnShell;
  const showsFeedback = status === 'authenticated' && !isPublicRoute;
  const activeSection = getMastheadSection(router.pathname);

  useEffect(() => {
    const stored = readStoredVisualSettings();
    applyVisualSettings(stored.theme, stored.fontSize);
    // WP-83: the cached chrome language until the profile answers. Signed
    // out, the document stays French (_document), like the pages it serves.
    if (status === 'loading') return;
    document.documentElement.lang = status === 'authenticated'
      ? chromeLanguage(readLearnerLanguage(), readLearnerLevel())
      : 'fr';
  }, [status]);

  useEffect(() => installViewportMetrics(), []);

  useEffect(() => {
    if (!isNativePlatform()) return;
    // Mark the document so native-only polish (no zoom, hidden scrollbars,
    // no overscroll bounce/tap-highlight) applies without degrading the web build.
    document.documentElement.classList.add('is-native');
    const viewport = document.querySelector('meta[name="viewport"]');
    viewport?.setAttribute(
      'content',
      'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover',
    );
  }, []);

  useEffect(() => {
    if (status !== 'authenticated' || !session?.accessToken) return;

    const controller = new AbortController();
    const loadPreferences = async () => {
      try {
        const response = await fetch(`${resolveBrowserApiBaseUrl()}/users/me/settings`, {
          headers: {
            Authorization: `Bearer ${session.accessToken}`,
          },
          signal: controller.signal,
        });
        if (!response.ok) return;
        const settings = await response.json();
        // WP-83: <html lang> follows the chrome language (WP-82's rule).
        const language = rememberLearnerLanguage(settings.native_language);
        const level = rememberLearnerLevel(settings.cefr_estimate);
        document.documentElement.lang = chromeLanguage(language, level);
        persistVisualSettings(
          (settings.theme || 'system') as AppTheme,
          (settings.font_size || 'medium') as AppFontSize
        );
      } catch {
        // Visual preferences are a convenience layer; failed loading should not block navigation.
      }
    };

    loadPreferences();
    return () => controller.abort();
  }, [session?.accessToken, status]);

  return (
    <div className="app-root min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)]">
      {/* WP-83: the few notices still raised as toasts sit on the app's own
          tokens (both themes), centred and clear of the Dynamic Island. */}
      <Toaster
        position="top-center"
        containerStyle={{ top: 'calc(env(safe-area-inset-top, 0px) + 12px)', left: 16, right: 16 }}
        toastOptions={{
          duration: 4000,
          style: {
            background: 'var(--app-sheet)',
            color: 'var(--app-ink)',
            borderRadius: 16,
            boxShadow: '0 8px 24px rgb(0 0 0 / 0.18)',
            fontFamily: 'var(--app-grotesk)',
            fontSize: '0.9375rem',
            maxWidth: 480,
          },
        }}
      />

      {showsNavigation && <EditorialMasthead active={activeSection} />}

      <main className={cn('app-main-shell min-h-screen flex flex-col', className)}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            // The route, not the query: a shallow `router.replace` that only
            // changes `?…` (Missions, Cahier sections, `?start=today`) must not
            // unmount the page and drop its state (WP-75 / WP-83).
            key={router.asPath.split(/[?#]/)[0]}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="app-route-shell w-full flex-1 flex flex-col"
          >
            {usesOwnShell || !showsNavigation ? children : <div className="app-page-frame w-full flex-1 flex flex-col">{children}</div>}
          </motion.div>
        </AnimatePresence>
      </main>
      {showsFeedback && <FeedbackWidget />}
    </div>
  );
}

function getMastheadSection(pathname: string) {
  const productSection = resolveProductSection(pathname);
  if (productSection === 'atelier') return 'studio';
  if (productSection === 'notebook') return 'notebook';
  if (productSection === 'missions') return 'missions';
  if (productSection === 'feuilleton') return 'feuilleton';
  if (productSection === 'settings') return 'settings';
  if (pathname === '/atelier') return 'studio';
  if (pathname === '/grammar' || pathname === '/vocabulary') return 'notebook';
  if (pathname === '/missions') return 'missions';
  if (pathname === '/graphic-novel') return 'feuilleton';
  if (pathname === '/settings') return 'settings';
  return undefined;
}
