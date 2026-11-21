import React from 'react';
import { useRouter } from 'next/router';

import { AtelierV2Root, StateBlock } from '@/components/atelier-v2/ui';
import { sanitizeAuthCallbackUrl, useAppSession } from '@/lib/app-auth';
import { atelierChrome } from '@/lib/atelier-v2-copy';
import { readLearnerLanguage, readLearnerLevel } from '@/lib/learner-language';
import { chromeLanguage } from '@/lib/language-rule';
import { guestOnlyRoutes, publicRoutes } from '@/lib/places';
import { reconnectWebSession, SESSION_EXPIRED_EVENT, sessionExpiredCopy } from '@/lib/session-recovery';

// S4 stage 1: who may open a route signed out is the register's `access`
// (lib/places.ts). Public there: the front door, sign-in and sign-up, the
// legal pages (App Review opens them signed out) and the dev sheets, which do
// not exist in a production build (their `getStaticProps` returns `notFound`)
// and are pruned from the native export.
const PUBLIC_PATHNAMES = new Set(publicRoutes());

const GUEST_ONLY_PATHNAMES = new Set(guestOnlyRoutes());

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
  const [expired, setExpired] = React.useState(false);
  React.useEffect(() => {
    const expire = () => setExpired(true);
    window.addEventListener(SESSION_EXPIRED_EVENT, expire);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expire);
  }, []);

  React.useEffect(() => {
    if (!router.isReady) return;

    if (isProtected && status === 'unauthenticated' && !expired) {
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
  }, [expired, isGuestOnly, isProtected, router, router.asPath, router.isReady, router.query.callbackUrl, status]);

  if (isProtected && expired) {
    const language = chromeLanguage(readLearnerLanguage(), readLearnerLevel());
    const copy = sessionExpiredCopy[language];
    return (
      <AtelierV2Root language={language}>
        <StateBlock tone="error" title={copy.message} action={{
          label: copy.action,
          onSelect: () => { void reconnectWebSession(sanitizeAuthCallbackUrl(router.asPath)); },
        }} />
      </AtelierV2Root>
    );
  }

  if (!router.isReady && isProtected && status !== 'authenticated') return <LoadingFrame />;
  if (isProtected && status !== 'authenticated') return <LoadingFrame />;
  if (isGuestOnly && status === 'authenticated') return <LoadingFrame />;

  return <>{children}</>;
}
