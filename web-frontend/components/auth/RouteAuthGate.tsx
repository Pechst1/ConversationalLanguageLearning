import React from 'react';
import { useRouter } from 'next/router';

import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { sanitizeAuthCallbackUrl, useAppSession } from '@/lib/app-auth';
import { atelierChrome } from '@/lib/atelier-v2-copy';
import { readLearnerLanguage } from '@/lib/learner-language';

const PUBLIC_PATHNAMES = new Set([
  '/',
  '/auth/signin',
  '/auth/signup',
  '/auth/forgot-password',
  // WP-72: the privacy policy and the terms must be readable before an account
  // exists — sign-up links to them and App Review opens them signed out.
  '/privacy',
  '/terms',
  // Dev/QA only, and pruned from the native export (scripts/native-export-prune.mjs).
  '/mobile-visual-qa',
  // Both of these are development-only: their `getStaticProps` returns
  // `notFound` when NODE_ENV is production, so the route does not exist in a
  // production build and listing it here widens nothing.
  '/atelier-v2-gallery',
]);

const GUEST_ONLY_PATHNAMES = new Set([
  '/auth/signin',
  '/auth/signup',
]);

/* WP-83 — one loader. While the session resolves the screen shows the same
   av2 skeleton the pages themselves use, labelled for screen readers, instead
   of an unlabelled spinner that a page skeleton then replaced. */
function LoadingFrame() {
  const [language, setLanguage] = React.useState<string>('en');
  React.useEffect(() => setLanguage(readLearnerLanguage()), []);
  const label = atelierChrome(language).loading;
  return (
    <AtelierV2Root language={language} className="app-loading-frame" role="status" aria-busy="true" aria-label={label}>
      <span className="av2-sr">{label}</span>
      <div className="av2-skeleton" style={{ width: '40%', height: '1rem' }} aria-hidden="true" />
      <div className="av2-skeleton" style={{ width: '70%', height: '2rem' }} aria-hidden="true" />
      <div className="av2-skeleton" style={{ height: '12rem' }} aria-hidden="true" />
      <div className="av2-skeleton" style={{ height: '3.5rem' }} aria-hidden="true" />
    </AtelierV2Root>
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
