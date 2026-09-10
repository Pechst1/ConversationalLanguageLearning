/* La page d'accueil publique — the quietest sheet in the app.
   One nameplate, one dateline, one truthful serif sentence, two actions.
   No fake queue, no placeholder numbers, no time promises: the edition
   speaks for itself once the reader signs in. */

import Head from 'next/head';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { AtelierMark, AuthScreen, AuthSpacer } from '@/components/auth/AuthShell';
import { useAppSession } from '@/lib/app-auth';

export default function HomePage() {
  const { status } = useAppSession();
  const authed = status === 'authenticated';

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

        <AuthSpacer />

        <section className="la-une__pitch" aria-label="Présentation" lang="fr">
          <h1 className="av2-headline av2-headline--screen">
            Chaque jour, une édition de français dont vous êtes un personnage.
          </h1>
          <p className="av2-body av2-body--lg">
            Un épisode de feuilleton où vous tenez votre rôle, une courte séance
            d’exercices, des progrès consignés noir sur blanc.
          </p>
        </section>

        <AuthSpacer />

        <div className="la-une__actions">
          {authed ? (
            <Link className="av2-btn av2-btn--primary" href="/atelier">
              Ouvrir votre édition
            </Link>
          ) : (
            <>
              <Link className="av2-btn av2-btn--primary" href="/auth/signin">
                Se connecter
              </Link>
              <Link className="av2-btn av2-btn--secondary" href="/auth/signup">
                Créer un compte
              </Link>
            </>
          )}
        </div>
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
      `}</style>
    </>
  );
}
