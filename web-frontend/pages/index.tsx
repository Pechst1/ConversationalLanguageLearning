/* La page d'accueil publique — the quietest sheet in the app.
   One nameplate, one dateline, the promise in the learner's own language, and
   one primary action: «Commencer», which plays the sixty-second taste right
   here, before any account (WP-75). «J'ai déjà un compte» is a quiet link.
   No fake queue, no placeholder numbers: the promise is the one the taste
   keeps. */

import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { AtelierMark, AuthScreen, AuthSpacer } from '@/components/auth/AuthShell';
import { Action } from '@/components/atelier-v2/ui';
import { LanguageSwitch, useOnboardingLanguage } from '@/components/onboarding/LanguageSwitch';
import { Taste } from '@/components/onboarding/Taste';
import { useAppSession } from '@/lib/app-auth';
import { TASTE_COPY, TASTE_NAV } from '@/lib/onboarding-taste';

export default function HomePage() {
  const router = useRouter();
  const { status } = useAppSession();
  const authed = status === 'authenticated';
  const [language, setLanguage] = useOnboardingLanguage();
  const [tasting, setTasting] = useState(false);
  const copy = TASTE_COPY[language];

  /* The dateline is set on the client so the statically generated HTML never
     carries a stale build-day date. The line's space is reserved; the text
     simply fades onto the paper (opacity only). */
  const [dateline, setDateline] = useState<{ text: string; iso: string } | null>(null);
  useEffect(() => {
    try {
      const now = new Date();
      const text = new Intl.DateTimeFormat('fr-FR', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      }).format(now);
      setDateline({
        text: text.charAt(0).toUpperCase() + text.slice(1),
        iso: now.toISOString().slice(0, 10),
      });
    } catch {
      setDateline(null);
    }
  }, []);

  return (
    <>
      <Head>
        <title>L’Atelier</title>
        <meta
          name="description"
          content="L’Atelier — un quotidien pour apprendre le français : un feuilleton dont vous êtes un personnage, une courte séance, des progrès consignés noir sur blanc."
        />
      </Head>

      <AuthScreen label="L’Atelier">
        {!tasting && (
          <header className="la-une" lang="fr">
            <AtelierMark size={26} />
            <p className="la-une__nameplate">L’Atelier</p>
            {/* The dateline's space is reserved so the line never reflows when the
                client fills it in; only its opacity changes. */}
            <p className={`la-une__folio${dateline ? ' is-shown' : ''}`}>
              Quotidien de français
              {dateline && (
                <>
                  {' · '}
                  <time dateTime={dateline.iso}>{dateline.text}</time>
                </>
              )}
            </p>
            <div className="la-une__rule" aria-hidden="true" />
          </header>
        )}

        {tasting ? (
          <Taste language={language} onKeep={() => void router.push('/auth/signup')} />
        ) : (
          <>
            <AuthSpacer />

            <section className="la-une__pitch" aria-label="L’Atelier">
              <h1 className="av2-headline av2-headline--screen" lang={language}>
                {copy.promise}
              </h1>
            </section>

            <AuthSpacer />

            <div className="la-une__actions">
              {authed ? (
                <Link className="av2-btn av2-btn--primary" href="/atelier">
                  Ouvrir votre édition
                </Link>
              ) : (
                <>
                  <Action tone="primary" onClick={() => setTasting(true)}>
                    {TASTE_NAV[language].start}
                  </Action>
                  <Link className="av2-btn av2-btn--quiet" href="/auth/signin">
                    {TASTE_NAV[language].have_account}
                  </Link>
                  <div className="la-une__lang">
                    <LanguageSwitch value={language} onChange={setLanguage} label={copy.language} />
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </AuthScreen>

      <style jsx global>{`
        .av2 .la-une {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          text-align: center;
        }
        .av2 .la-une__nameplate {
          margin: 0;
          font-family: var(--av2-serif);
          font-size: var(--av2-t-display);
          font-weight: 500;
          line-height: 1.05;
          color: var(--av2-ink);
        }
        .av2 .la-une__folio {
          margin: 0;
          min-height: 1.4em;
          font-size: var(--av2-t-meta);
          font-weight: 700;
          line-height: 1.4;
          color: var(--av2-muted);
          opacity: 0;
          transition: opacity 0.4s ease;
          overflow-wrap: anywhere;
        }
        .av2 .la-une__folio.is-shown {
          opacity: 1;
        }
        .av2 .la-une__rule {
          width: 100%;
          height: 1px;
          margin-top: 6px;
          background: var(--av2-line);
        }
        .av2 .la-une__pitch {
          display: flex;
          flex-direction: column;
          gap: 14px;
          min-width: 0;
        }
        .av2 .la-une__actions {
          display: flex;
          flex-direction: column;
          gap: 10px;
          min-width: 0;
        }
        .av2 .la-une__lang {
          display: flex;
          justify-content: center;
          margin-top: 6px;
        }
      `}</style>
    </>
  );
}
