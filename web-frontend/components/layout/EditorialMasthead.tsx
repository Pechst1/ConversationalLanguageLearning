import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Settings } from 'lucide-react';

import {
  resolveProductSection,
  resolveProductTitle,
  type ProductSection,
} from '@/lib/product-shell';
import PhoneProductNav from './PhoneProductNav';

type MastheadSection =
  | 'home'
  | 'conversation'
  | 'studio'
  | 'notebook'
  | 'missions'
  | 'feuilleton'
  | 'review'
  | 'progress'
  | 'settings';

interface EditorialMastheadProps {
  active?: MastheadSection;
  brandHref?: string;
  brandLabel?: string;
  atelierHref?: string;
  studioControl?: React.ReactNode;
  sessionControl?: React.ReactNode;
  trailing?: React.ReactNode;
  hideMobileNav?: boolean;
  hideMobileHeader?: boolean;
  hideMobileTitle?: boolean;
  mobileAction?: React.ReactNode;
}

export default function EditorialMasthead({
  active,
  brandHref = '/atelier',
  brandLabel = 'Atelier',
  atelierHref = '/atelier',
  studioControl,
  sessionControl,
  trailing,
  hideMobileNav = false,
  hideMobileHeader = false,
  hideMobileTitle = false,
  mobileAction,
}: EditorialMastheadProps) {
  const router = useRouter();
  const mobileSection = resolveProductSection(router.pathname) || productSectionFromMasthead(active);
  const mobileTitle = resolveProductTitle(mobileSection, router.pathname);
  const isSettingsActive = active === 'settings' || router.pathname === '/settings';

  return (
    <header className={`app-masthead ${hideMobileHeader ? 'app-mobile-header-hidden' : ''} ${hideMobileTitle ? 'app-mobile-title-hidden' : ''} ${mobileAction ? 'app-has-mobile-action' : ''}`}>
      <div className="app-spread app-masthead-inner">
        <Link className="app-brand" href={brandHref} aria-label={`Open ${brandLabel} home`}>
          <AtelierMark />
          <span>{brandLabel}</span>
        </Link>
        <div className="app-mobile-title" aria-hidden="true">{mobileTitle}</div>
        <div className="app-mobile-action">
          {mobileAction}
          <SettingsAffordance active={isSettingsActive} mobile />
        </div>
        <div className="app-header-tools">
          <nav className="app-nav" aria-label="Primary">
            {studioControl || (
              <Link className={mobileSection === 'atelier' ? 'active' : ''} href={atelierHref}>
                Atelier
              </Link>
            )}
            {sessionControl}
            <Link className={mobileSection === 'notebook' ? 'active' : ''} href="/notebook">Notebook</Link>
            {trailing && <span className="app-nav-trailing">{trailing}</span>}
          </nav>
          <SettingsAffordance active={isSettingsActive} />
        </div>
      </div>
      {!hideMobileNav && (
        <PhoneProductNav active={mobileSection} />
      )}
      <style jsx global>{`
        .app-masthead {
          --app-paper: #f1ece1;
          --app-ink: #14110d;
          --app-ink-3: #8a826f;
          --app-sheet: #f8f3e8;
          position: sticky;
          top: 0;
          z-index: 40;
          border-bottom: 1px solid var(--app-ink);
          background: rgba(241, 236, 225, .94);
          backdrop-filter: blur(10px);
          /* Clear the status bar / Dynamic Island on native devices. */
          padding-top: env(safe-area-inset-top);
        }
        .app-spread {
          box-sizing: border-box;
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
        .app-header-tools {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .app-settings-affordance {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          color: var(--app-ink-3);
          text-decoration: none;
          font-size: 10px;
          letter-spacing: .13em;
          text-transform: uppercase;
          font-weight: 900;
          line-height: 1;
        }
        .app-settings-affordance:hover,
        .app-settings-affordance.active {
          color: var(--app-ink);
        }
        .app-settings-affordance svg {
          width: 16px;
          height: 16px;
          flex: 0 0 auto;
        }
        .app-mobile-title {
          display: none;
        }
        .app-mobile-action {
          display: none;
        }
        @media (max-width: 760px) {
          .app-masthead {
            background: var(--app-paper);
            backdrop-filter: none;
          }
          .app-masthead.app-mobile-header-hidden {
            display: none;
          }
          .app-spread {
            padding-left: 16px;
            padding-right: 16px;
          }
          .app-masthead-inner {
            position: relative;
            min-height: 52px;
            justify-content: center;
            padding-top: 8px;
            padding-bottom: 12px;
          }
          .app-header-tools {
            display: none;
          }
          .app-brand {
            position: absolute;
            left: 16px;
            width: 56px;
            gap: 0;
            font-size: 0;
          }
          .app-brand svg {
            width: 22px;
            height: 22px;
          }
          .app-brand span {
            display: none;
          }
          .app-mobile-title {
            position: absolute;
            left: 74px;
            right: 74px;
            display: block;
            overflow: hidden;
            color: var(--app-ink);
            text-align: center;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-family: var(--app-serif, "EB Garamond", Garamond, "Times New Roman", serif);
            font-size: 22px;
            font-style: italic;
            font-weight: 500;
            line-height: 1;
            letter-spacing: 0;
          }
          .app-mobile-action {
            position: absolute;
            right: 16px;
            width: 56px;
            display: flex;
            align-items: center;
            gap: 8px;
            justify-content: flex-end;
          }
          .app-masthead.app-has-mobile-action .app-mobile-action {
            width: auto;
            max-width: calc(var(--app-viewport-width) - 96px);
          }
          .app-masthead.app-mobile-title-hidden .app-mobile-title {
            display: none;
          }
          .app-masthead.app-has-mobile-action .app-mobile-title {
            display: none;
          }
          .app-mobile-action .app-settings-affordance {
            width: 36px;
            height: 36px;
            border: 1px solid var(--app-ink);
            background: var(--app-sheet);
            color: var(--app-ink);
          }
          .app-mobile-action .app-settings-affordance span {
            display: none;
          }
        }
      `}</style>
    </header>
  );
}

function productSectionFromMasthead(active?: MastheadSection): ProductSection | undefined {
  if (active === 'notebook' || active === 'progress') return 'notebook';
  if (active === 'missions') return 'missions';
  if (active === 'feuilleton') return 'feuilleton';
  if (active === 'settings') return undefined;
  return 'atelier';
}

function SettingsAffordance({ active, mobile = false }: { active: boolean; mobile?: boolean }) {
  return (
    <Link
      className={`app-settings-affordance ${active ? 'active' : ''}`}
      href="/settings"
      aria-label="Settings"
      aria-current={active ? 'page' : undefined}
      title="Settings"
    >
      <Settings aria-hidden="true" strokeWidth={2.4} />
      {!mobile && <span>Settings</span>}
    </Link>
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
