import React from 'react';
import { useRouter } from 'next/router';

import { sanitizeAuthCallbackUrl, useAppSession } from '@/lib/app-auth';

const PUBLIC_PATHNAMES = new Set([
  '/',
  '/auth/signin',
  '/auth/signup',
  '/auth/forgot-password',
  '/mobile-visual-qa',
]);

const GUEST_ONLY_PATHNAMES = new Set([
  '/auth/signin',
  '/auth/signup',
]);

function LoadingFrame() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-2 border-[var(--app-ink)] border-t-transparent" />
    </div>
  );
}

export default function RouteAuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { status } = useAppSession();
  const isGuestOnly = GUEST_ONLY_PATHNAMES.has(router.pathname);
  const isProtected = !PUBLIC_PATHNAMES.has(router.pathname);
  const pendingRedirectRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (!router.isReady) return;

    if (isProtected && status === 'unauthenticated') {
      const callbackUrl = sanitizeAuthCallbackUrl(router.asPath);
      const redirectKey = `/auth/signin?callbackUrl=${encodeURIComponent(callbackUrl)}`;
      if (pendingRedirectRef.current === redirectKey) return;
      pendingRedirectRef.current = redirectKey;
      void router.replace({
        pathname: '/auth/signin',
        query: { callbackUrl },
      }, undefined, { scroll: false }).finally(() => {
        pendingRedirectRef.current = null;
      });
      return;
    }

    if (isGuestOnly && status === 'authenticated') {
      const destination = sanitizeAuthCallbackUrl(router.query.callbackUrl);
      if (router.asPath === destination || pendingRedirectRef.current === destination) return;
      pendingRedirectRef.current = destination;
      void router.replace(destination, undefined, { scroll: false }).finally(() => {
        pendingRedirectRef.current = null;
      });
    }
  }, [isGuestOnly, isProtected, router, router.asPath, router.isReady, router.query.callbackUrl, status]);

  if (!router.isReady && isProtected && status !== 'authenticated') return <LoadingFrame />;
  if (isProtected && status !== 'authenticated') return <LoadingFrame />;
  if (isGuestOnly && status === 'authenticated') return <LoadingFrame />;

  return <>{children}</>;
}
