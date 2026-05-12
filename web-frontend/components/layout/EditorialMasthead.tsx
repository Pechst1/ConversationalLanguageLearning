import React from 'react';
import Link from 'next/link';

type MastheadSection =
  | 'home'
  | 'conversation'
  | 'studio'
  | 'notebook'
  | 'missions'
  | 'feuilleton'
  | 'review'
  | 'progress';

interface EditorialMastheadProps {
  active?: MastheadSection;
  brandHref?: string;
  brandLabel?: string;
  atelierHref?: string;
  studioControl?: React.ReactNode;
  sessionControl?: React.ReactNode;
  trailing?: React.ReactNode;
}

export default function EditorialMasthead({
  active,
  brandHref = '/atelier',
  brandLabel = 'Atelier',
  atelierHref = '/atelier',
  studioControl,
  sessionControl,
  trailing,
}: EditorialMastheadProps) {
  return (
    <header className="app-masthead">
      <div className="app-spread app-masthead-inner">
        <Link className="app-brand" href={brandHref} aria-label={`Open ${brandLabel} home`}>
          <AtelierMark />
          <span>{brandLabel}</span>
        </Link>
        <nav className="app-nav" aria-label="Primary">
          {studioControl || (
            <Link className={active === 'home' || active === 'studio' ? 'active' : ''} href={atelierHref}>
              Atelier
            </Link>
          )}
          {sessionControl}
          <Link className={active === 'notebook' ? 'active' : ''} href="/grammar">Notebook</Link>
          <Link className={active === 'missions' ? 'active' : ''} href="/missions">Missions</Link>
          <Link className={active === 'feuilleton' ? 'active' : ''} href="/graphic-novel">Feuilleton</Link>
          {trailing && <span className="app-nav-trailing">{trailing}</span>}
        </nav>
      </div>
      <style jsx global>{`
        .app-masthead {
          --app-paper: #f1ece1;
          --app-ink: #14110d;
          --app-ink-3: #8a826f;
          position: sticky;
          top: 0;
          z-index: 40;
          border-bottom: 1px solid var(--app-ink);
          background: rgba(241, 236, 225, .94);
          backdrop-filter: blur(10px);
        }
        .app-spread {
          width: min(1320px, 100%);
          margin: 0 auto;
          padding-left: clamp(22px, 4vw, 48px);
          padding-right: clamp(22px, 4vw, 48px);
        }
        .app-masthead-inner {
          min-height: 58px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 24px;
        }
        .app-brand {
          display: inline-flex;
          align-items: center;
          gap: 12px;
          color: var(--app-ink);
          text-decoration: none;
          font-size: 22px;
          font-weight: 900;
          letter-spacing: 0;
          white-space: nowrap;
        }
        .app-nav {
          display: flex;
          align-items: center;
          gap: 20px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }
        .app-nav a,
        .app-nav .app-nav-button,
        .app-nav-trailing {
          color: var(--app-ink-3);
          border: 0;
          border-bottom: 2px solid transparent;
          background: transparent;
          padding: 0 0 3px;
          font: inherit;
          font-size: 10px;
          letter-spacing: .13em;
          text-transform: uppercase;
          font-weight: 900;
          text-decoration: none;
          cursor: pointer;
        }
        .app-nav a.active,
        .app-nav a:hover,
        .app-nav .app-nav-button.active,
        .app-nav .app-nav-button:hover {
          color: var(--app-ink);
          border-bottom-color: var(--app-ink);
        }
        .app-nav .app-nav-button:disabled {
          opacity: .35;
          cursor: not-allowed;
        }
        .app-nav-trailing {
          border-bottom: 0;
          cursor: default;
          color: #4a4538;
          display: inline-flex;
          align-items: center;
          gap: 10px;
        }
        @media (max-width: 760px) {
          .app-masthead-inner {
            align-items: flex-start;
            flex-direction: column;
            padding-top: 12px;
            padding-bottom: 12px;
          }
          .app-nav {
            gap: 14px;
            justify-content: flex-start;
          }
        }
      `}</style>
    </header>
  );
}

function AtelierMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <rect x="0" y="0" width="11" height="11" fill="var(--app-ink, #14110d)" />
      <circle cx="22" cy="6" r="6" fill="var(--app-blue, #1d3a8a)" />
      <rect x="0" y="17" width="11" height="11" fill="var(--app-yellow, #f3c318)" />
      <path d="M17 28L23 16L28 28H17Z" fill="var(--app-red, #d8321a)" />
    </svg>
  );
}
