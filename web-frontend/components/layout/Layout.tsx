import React, { useEffect } from 'react';
import { useRouter } from 'next/router';
import { useSession } from 'next-auth/react';
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
import { cn } from '@/lib/utils';
import { resolveProductSection, routeUsesOwnProductShell } from '@/lib/product-shell';

interface LayoutProps {
  children: React.ReactNode;
  showSidebar?: boolean;
  className?: string;
}

export default function Layout({ children, showSidebar = true, className }: LayoutProps) {
  const router = useRouter();
  const { data: session, status } = useSession();

  const isPublicRoute = router.pathname === '/' || router.pathname.startsWith('/auth');
  const usesOwnShell = routeUsesOwnProductShell(router.pathname);
  const showsNavigation = showSidebar && !isPublicRoute && !usesOwnShell;
  const activeSection = getMastheadSection(router.pathname);

  useEffect(() => {
    const stored = readStoredVisualSettings();
    applyVisualSettings(stored.theme, stored.fontSize);
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
    <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)]">
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            style: {
              background: '#10b981',
            },
          },
          error: {
            style: {
              background: '#ef4444',
            },
          },
        }}
      />

      {showsNavigation && <EditorialMasthead active={activeSection} />}

      <main className={cn('min-h-screen flex flex-col', className)}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={router.asPath}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="w-full flex-1 flex flex-col"
          >
            {usesOwnShell || !showsNavigation ? children : <div className="app-page-frame w-full flex-1 flex flex-col">{children}</div>}
          </motion.div>
        </AnimatePresence>
      </main>
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
  if (pathname === '/dashboard') return 'studio';
  if (pathname.startsWith('/learn')) return 'conversation';
  if (pathname === '/atelier' || pathname === '/daily-practice') return 'studio';
  if (pathname === '/grammar' || pathname === '/vocabulary') return 'notebook';
  if (pathname === '/missions') return 'missions';
  if (pathname === '/graphic-novel') return 'feuilleton';
  if (pathname === '/practice' || pathname === '/sessions') return 'review';
  if (pathname === '/progress' || pathname === '/achievements') return 'progress';
  if (pathname === '/settings') return 'settings';
  return undefined;
}
