import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';

import { PHONE_PRODUCT_TABS, resolveProductSection, type ProductSection } from '@/lib/product-shell';

type PhoneProductNavProps = {
  active?: ProductSection;
  placement?: 'fixed' | 'embedded';
};

export default function PhoneProductNav({ active, placement = 'fixed' }: PhoneProductNavProps) {
  const router = useRouter();
  const activeSection = active || resolveProductSection(router.pathname);

  return (
    <nav className={`phone-product-nav ${placement}`} aria-label="Primary">
      {PHONE_PRODUCT_TABS.map((item) => {
        const isActive = item.id === activeSection;
        return (
          <Link
            key={item.id}
            className={isActive ? 'active' : ''}
            href={item.href}
            aria-current={isActive ? 'page' : undefined}
          >
            <PhoneProductIcon kind={item.icon} />
            <span>{item.label}</span>
          </Link>
        );
      })}
      <style jsx global>{`
        .phone-product-nav {
          --nav-paper: var(--app-paper, #f1ece1);
          --nav-sheet: var(--app-sheet, #f8f3e8);
          --nav-ink: var(--app-ink, #14110d);
          --nav-muted: var(--app-ink-3, #8a826f);
          grid-template-columns: repeat(4, minmax(0, 1fr));
          min-height: var(--phone-bottom-nav-space);
          padding: 0 0 var(--phone-safe-bottom-space);
          border-top: 1px solid var(--nav-ink);
          background: var(--nav-paper);
        }
        .phone-product-nav.fixed {
          position: fixed;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 70;
          display: none;
        }
        .phone-product-nav.embedded {
          display: grid;
          flex: 0 0 auto;
        }
        .phone-product-nav a {
          min-width: 0;
          min-height: var(--phone-bottom-nav-height);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 5px;
          margin-top: -1px;
          border-top: 2px solid transparent;
          color: var(--nav-muted);
          text-decoration: none;
          font-family: var(--app-grotesk, Inter, ui-sans-serif, system-ui, sans-serif);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .12em;
          line-height: 1;
          text-transform: uppercase;
        }
        .phone-product-nav a.active {
          border-top-color: var(--nav-ink);
          background: var(--nav-sheet);
          color: var(--nav-ink);
        }
        .phone-product-nav svg {
          width: 22px;
          height: 22px;
          flex: 0 0 auto;
        }
        .phone-product-nav span {
          max-width: 100%;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        @media (max-width: 760px) {
          .phone-product-nav.fixed {
            display: grid;
          }
        }
        @media (max-width: 420px) {
          .phone-product-nav a {
            font-size: 9px;
            letter-spacing: .08em;
          }
        }
      `}</style>
    </nav>
  );
}

function PhoneProductIcon({ kind }: { kind: 'mark' | 'mission' | 'feuilleton' | 'book' }) {
  if (kind === 'mark') {
    return (
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <rect x="0" y="0" width="8" height="8" fill="currentColor" />
        <path d="M20 0 A 12 12 0 0 0 8 12 L 20 12 Z" fill="currentColor" />
        <rect x="0" y="12" width="8" height="8" fill="currentColor" />
      </svg>
    );
  }
  if (kind === 'mission') {
    return (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M10 2.5 18 17.5H2L10 2.5Z" stroke="currentColor" strokeWidth="1.8" />
      </svg>
    );
  }
  if (kind === 'feuilleton') {
    return (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <rect x="3" y="3" width="14" height="14" stroke="currentColor" strokeWidth="1.8" />
        <path d="M10 3V17M3 10H17" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" fill="none">
      <rect x="3" y="2" width="13" height="16" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 4h13M3 6h13" stroke="currentColor" strokeWidth="1" />
      <path d="M11 2v8l-2-2-2 2V2" fill="currentColor" />
    </svg>
  );
}
