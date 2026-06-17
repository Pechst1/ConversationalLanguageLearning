import React from 'react';
import { useRouter } from 'next/router';

import { useAppSession } from '@/lib/app-auth';

const PUBLIC_PATHNAMES = new Set([
  '/',
  '/auth/signin',
  '/auth/signup',
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

function safeCallbackUrl(value: string | string[] | undefined) {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate && candidate.startsWith('/') ? candidate : '/atelier';
}

export default function RouteAuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { status } = useAppSession();
  const isGuestOnly = GUEST_ONLY_PATHNAMES.has(router.pathname);
  const isProtected = !PUBLIC_PATHNAMES.has(router.pathname);

  React.useEffect(() => {
    if (!router.isReady) return;

    if (isProtected && status === 'unauthenticated') {
      const callbackUrl = router.asPath.startsWith('/') ? router.asPath : '/atelier';
      router.replace({
        pathname: '/auth/signin',
        query: { callbackUrl },
      });
      return;
    }

    if (isGuestOnly && status === 'authenticated') {
      router.replace(safeCallbackUrl(router.query.callbackUrl));
    }
  }, [isGuestOnly, isProtected, router, status]);

  if (!router.isReady) return <LoadingFrame />;
  if (isProtected && status !== 'authenticated') return <LoadingFrame />;
  if (isGuestOnly && status === 'authenticated') return <LoadingFrame />;

  return <>{children}</>;
}
