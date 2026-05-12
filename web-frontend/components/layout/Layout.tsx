import React from 'react';
import { useRouter } from 'next/router';
import { Toaster } from 'react-hot-toast';
import EditorialMasthead from './EditorialMasthead';
import { cn } from '@/lib/utils';

interface LayoutProps {
  children: React.ReactNode;
  showSidebar?: boolean;
  className?: string;
}

export default function Layout({ children, showSidebar = true, className }: LayoutProps) {
  const router = useRouter();

  const isPublicRoute = router.pathname === '/' || router.pathname.startsWith('/auth');
  const usesOwnShell = [
    '/atelier',
    '/missions',
    '/graphic-novel',
    '/grammar',
    '/learn',
    '/learn/new',
    '/learn/session/[id]',
    '/audio-session',
  ].includes(router.pathname);
  const showsNavigation = showSidebar && !isPublicRoute && !usesOwnShell;
  const activeSection = getMastheadSection(router.pathname);

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

      <main className={cn('min-h-screen', className)}>
        {usesOwnShell || !showsNavigation ? children : <div className="app-page-frame">{children}</div>}
      </main>
    </div>
  );
}

function getMastheadSection(pathname: string) {
  if (pathname === '/dashboard') return 'studio';
  if (pathname.startsWith('/learn')) return 'conversation';
  if (pathname === '/atelier' || pathname === '/daily-practice') return 'studio';
  if (pathname === '/grammar') return 'notebook';
  if (pathname === '/missions') return 'missions';
  if (pathname === '/graphic-novel') return 'feuilleton';
  if (pathname === '/practice' || pathname === '/sessions') return 'review';
  if (pathname === '/progress' || pathname === '/achievements') return 'progress';
  return undefined;
}
