/* La page d'accueil publique — the quietest sheet in the app.
   One nameplate, one dateline, one truthful serif sentence, two actions.
   No fake queue, no placeholder numbers, no time promises: the edition
   speaks for itself once the reader signs in. */

import Head from 'next/head';
import Link from 'next/link';
import { useEffect, useState } from 'react';
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

      <main className="landing" lang="fr">
        <header className="masthead">
          <AtelierMark />
          <div className="nameplate">L’Atelier</div>
          <p className="folio">Quotidien de français</p>
          <p className={`dateline${dateline ? ' shown' : ''}`}>
            {dateline && <time dateTime={dateline.iso}>{dateline.text}</time>}
          </p>
        </header>

        <section className="pitch" aria-label="Présentation">
          <h1>Chaque jour, une édition de français dont vous êtes un personnage.</h1>
          <p className="standfirst">
            Un épisode de feuilleton où vous tenez votre rôle, une courte séance
            d’exercices, des progrès consignés noir sur blanc.
          </p>

          <div className="actions">
            {authed ? (
              <Link className="action primary" href="/atelier">
                Ouvrir votre édition
              </Link>
            ) : (
              <>
                <Link className="action primary" href="/auth/signin">
                  Se connecter
                </Link>
                <Link className="action" href="/auth/signup">
                  Créer un compte
                </Link>
              </>
            )}
          </div>
        </section>
      </main>

      <style jsx>{`
        .landing {
          flex: 1 1 auto;
          display: flex;
          flex-direction: column;
          width: min(100%, var(--phone-shell-max, 430px));
          margin: 0 auto;
          padding: calc(max(26px, var(--phone-safe-top, 0px)) + 8px)
            var(--phone-gutter, 18px)
            calc(var(--phone-safe-bottom-space, 18px) + 12px);
          color: var(--app-ink);
        }

        /* ---- masthead: the nameplate of the paper ---- */
        .masthead {
          text-align: center;
          border-bottom: 1px solid var(--app-ink);
          padding-bottom: 18px;
        }
        .nameplate {
          margin-top: 12px;
          font-family: var(--app-serif);
          font-size: var(--t-display, 2.75rem);
          font-weight: 600;
          line-height: 1;
          letter-spacing: 0;
        }
        .folio {
          margin: 12px 0 0;
          font-size: var(--t-label, 0.6875rem);
          font-weight: 700;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--app-ink-3);
        }
        .dateline {
          margin: 5px 0 0;
          min-height: 1.5em;
          font-size: var(--t-label, 0.6875rem);
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--app-ink-3);
          opacity: 0;
        }
        .dateline.shown {
          opacity: 1;
        }

        /* ---- the one article ---- */
        .pitch {
          margin: auto 0;
          padding: 44px 0;
        }
        h1 {
          margin: 0;
          font-family: var(--app-serif);
          font-style: italic;
          font-weight: 600;
          font-size: var(--t-head, 1.75rem);
          line-height: 1.12;
          letter-spacing: 0;
          color: var(--app-ink);
          text-wrap: balance;
        }
        .standfirst {
          margin: 14px 0 0;
          font-size: var(--t-body, 1rem);
          line-height: 1.55;
          color: var(--app-ink-2);
        }

        /* ---- actions: soft pills, ≥44px tap targets ---- */
        .actions {
          display: grid;
          gap: 10px;
          margin-top: 32px;
        }
        .actions :global(.action) {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: max(44px, var(--phone-action-height, 54px));
          padding: 0 22px;
          border-radius: 999px;
          border: 1px solid var(--app-ink);
          background: transparent;
          color: var(--app-ink);
          font-size: var(--t-body, 1rem);
          font-weight: 600;
          letter-spacing: 0.01em;
          text-transform: none;
          text-decoration: none;
        }
        .actions :global(.action.primary) {
          background: var(--app-ink);
          color: var(--app-paper);
        }
        .actions :global(.action:hover) {
          background: var(--app-paper-2);
        }
        .actions :global(.action.primary:hover) {
          background: var(--app-ink-2);
          border-color: var(--app-ink-2);
          color: var(--app-paper);
        }
        .actions :global(.action:active) {
          background: var(--app-paper-2);
          color: var(--app-ink);
        }

        @media (prefers-reduced-motion: no-preference) {
          .dateline {
            transition: opacity 0.45s var(--ease-standard, ease);
          }
          .actions :global(.action) {
            transition: background 0.16s ease, color 0.16s ease,
              transform 0.12s ease;
          }
        }
      `}</style>
    </>
  );
}

/* The pressmark, set in the house inks (same mark as the auth pages). */
function AtelierMark() {
  return (
    <svg width="30" height="30" viewBox="0 0 28 28" aria-hidden="true">
      <rect x="0" y="0" width="11" height="11" fill="var(--app-ink)" />
      <circle cx="22" cy="6" r="6" fill="var(--app-blue)" />
      <rect x="0" y="17" width="11" height="11" fill="var(--app-yellow)" />
      <path d="M17 28L23 16L28 28H17Z" fill="var(--app-red)" />
    </svg>
  );
}
