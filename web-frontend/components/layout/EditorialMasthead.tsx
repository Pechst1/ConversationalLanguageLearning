import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { GearIcon } from '@/components/atelier-v2/ui';

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
  brandLabel = 'L’Atelier',
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
            <Link className={mobileSection === 'notebook' ? 'active' : ''} href="/notebook">Cahier</Link>
            {trailing && <span className="app-nav-trailing">{trailing}</span>}
          </nav>
          <SettingsAffordance active={isSettingsActive} />
        </div>
      </div>
      {!hideMobileNav && (
        <PhoneProductNav active={mobileSection} />
      )}
      <style jsx global>{`
        /* The app masthead in the Claude design's language: two fonts, sentence
           case, no tracked caps, no ruled boxes — a round paper affordance for
           settings, exactly the gear drawn on the HOME artboard. */
        .app-masthead {
          position: sticky;
          top: 0;
          z-index: 40;
          border-bottom: 1px solid var(--app-paper-2);
          background: color-mix(in srgb, var(--app-paper) 92%, transparent);
          backdrop-filter: blur(10px);
          /* Clear the status bar / Dynamic Island on native devices. */
          padding-top: env(safe-area-inset-top);
          font-family: 'AtelierSans', 'Instrument Sans', system-ui, sans-serif;
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
          font-family: 'AtelierSerif', 'EB Garamond', Georgia, serif;
          font-style: italic;
          font-size: 22px;
          font-weight: 500;
          letter-spacing: 0;
          white-space: nowrap;
        }
        .app-nav {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }
        .app-nav a,
        .app-nav .app-nav-button,
        .app-nav-trailing {
          display: inline-flex;
          align-items: center;
          min-height: 32px;
          padding: 0 13px;
          border: 0;
          border-radius: 999px;
          background: transparent;
          color: var(--app-ink-3);
          font: inherit;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: normal;
          text-transform: none;
          text-decoration: none;
          cursor: pointer;
        }
        .app-nav a.active,
        .app-nav a:hover,
        .app-nav .app-nav-button.active,
        .app-nav .app-nav-button:hover {
          color: var(--app-ink);
          background: var(--app-paper-2);
        }
        .app-nav .app-nav-button:disabled {
          opacity: .35;
          cursor: not-allowed;
        }
        .app-nav-trailing {
          cursor: default;
          color: var(--app-ink-2);
          gap: 10px;
        }
        .app-header-tools {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .app-settings-affordance {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          min-height: 32px;
          padding: 0 13px;
          border-radius: 999px;
          color: var(--app-ink-3);
          text-decoration: none;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: normal;
          text-transform: none;
          line-height: 1;
        }
        .app-settings-affordance:hover,
        .app-settings-affordance.active {
          color: var(--app-ink);
          background: var(--app-paper-2);
        }
        .app-settings-affordance svg {
          width: 18px;
          height: 18px;
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
            border-bottom: 0;
          }
          .app-masthead.app-mobile-header-hidden {
            display: none;
          }
          .app-spread {
            padding-left: 20px;
            padding-right: 20px;
          }
          .app-masthead-inner {
            position: relative;
            min-height: 52px;
            justify-content: center;
            padding-top: 8px;
            padding-bottom: 8px;
          }
          .app-header-tools {
            display: none;
          }
          .app-brand {
            position: absolute;
            left: 20px;
            width: 56px;
            gap: 0;
            font-size: 0;
          }
          .app-brand svg {
            width: 26px;
            height: 26px;
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
            font-family: 'AtelierSerif', 'EB Garamond', Georgia, serif;
            font-size: 22px;
            font-style: italic;
            font-weight: 500;
            line-height: 1;
            letter-spacing: 0;
          }
          .app-mobile-action {
            position: absolute;
            right: 20px;
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
          /* the design's settings gear: a 32px round paper disc, no rule */
          .app-mobile-action .app-settings-affordance {
            width: 36px;
            height: 36px;
            min-height: 36px;
            padding: 0;
            border: 0;
            border-radius: 999px;
            background: var(--app-sheet);
            color: var(--app-ink-2);
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
      <GearIcon size={18} />
      {!mobile && <span>Settings</span>}
    </Link>
  );
}

function AtelierMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 28 28" aria-hidden="true">
      <rect x="0" y="0" width="11" height="11" rx="2" fill="var(--app-ink, #14110d)" />
      <circle cx="22" cy="6" r="6" fill="var(--app-blue, #1d3a8a)" />
      <rect x="0" y="17" width="11" height="11" rx="2" fill="var(--app-yellow, #f3c318)" />
      <path d="M17 28L23 16L28 28H17Z" fill="var(--app-red, #d8321a)" />
    </svg>
  );
}
