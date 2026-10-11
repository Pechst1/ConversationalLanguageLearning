/**
 * WP-72 — the public `/privacy` and `/terms` screens.
 *
 * Public (RouteAuthGate lists both), shipped in the native export, and readable
 * offline: the text is bundled, not fetched. Language: `?lang=` (sign-up and
 * Réglages pass the learner's), else the device language, else English.
 */
import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowLeft } from 'lucide-react';

import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { LegalDocumentView } from '@/components/legal/LegalDocumentView';
import {
  LEGAL_LANGUAGES,
  legalDocument,
  legalHref,
  legalLabels,
  resolveLegalLanguage,
  type LegalDocumentKind,
  type LegalLanguage,
} from '@/lib/legal';

const BACK: Record<LegalLanguage, string> = { en: 'Back', de: 'Zurück', fr: 'Retour' };

export function LegalPage({ kind }: { kind: LegalDocumentKind }) {
  const router = useRouter();
  const [language, setLanguage] = React.useState<LegalLanguage | null>(null);

  React.useEffect(() => {
    if (!router.isReady) return;
    const device = typeof navigator === 'undefined' ? undefined : navigator.language;
    setLanguage(resolveLegalLanguage(router.query.lang, device));
  }, [router.isReady, router.query.lang]);

  const shown = language ?? 'en';
  const other: LegalDocumentKind = kind === 'privacy' ? 'terms' : 'privacy';
  const labels = legalLabels(shown);

  const goBack = () => {
    if (typeof window !== 'undefined' && window.history.length > 1) router.back();
    else void router.push('/');
  };

  return (
    <>
      <Head>
        <title>{`${legalDocument(kind, shown).title} · L’Atelier`}</title>
      </Head>
      <AtelierV2Root as="main" className="lg-page" language={shown} aria-busy={language === null}>
        <div className="lg-page__column">
          <nav className="lg-page__bar">
            <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline" onClick={goBack}>
              <ArrowLeft size={18} aria-hidden="true" /> {BACK[shown]}
            </button>
            <span className="lg-page__langs">
              {LEGAL_LANGUAGES.map((code) => (
                <Link
                  key={code}
                  href={legalHref(kind, code)}
                  replace
                  hrefLang={code}
                  aria-current={code === shown ? 'true' : undefined}
                  className="lg-page__lang"
                >
                  {code.toUpperCase()}
                </Link>
              ))}
            </span>
          </nav>
          {language !== null && <LegalDocumentView kind={kind} language={language} />}
          <p className="lg-page__other">
            <Link href={legalHref(other, shown)}>{labels[other]}</Link>
          </p>
        </div>
      </AtelierV2Root>
      <style jsx global>{`
        .av2.lg-page {
          min-height: 100vh;
          background: var(--av2-paper);
          padding: calc(env(safe-area-inset-top, 0px) + 12px) 16px
            calc(env(safe-area-inset-bottom, 0px) + 32px);
        }
        .av2 .lg-page__column {
          max-width: 40rem;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .av2 .lg-page__bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .av2 .lg-page__langs {
          display: flex;
          gap: 4px;
        }
        .av2 .lg-page__lang {
          min-width: 44px;
          min-height: 44px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 999px;
          color: var(--av2-muted);
          font-size: 0.875rem;
          text-decoration: none;
        }
        .av2 .lg-page__lang[aria-current='true'] {
          color: var(--av2-ink);
          font-weight: 700;
          background: var(--av2-line);
        }
        .av2 .lg-page__other {
          padding-top: 20px;
        }
        .av2 .lg-page__other a {
          color: var(--av2-blue);
        }
      `}</style>
    </>
  );
}
