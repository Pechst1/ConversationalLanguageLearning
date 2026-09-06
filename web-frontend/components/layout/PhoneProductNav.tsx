import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';

import { PHONE_PRODUCT_TABS, resolveProductSection, type ProductSection } from '@/lib/product-shell';

type PhoneProductNavProps = {
  active?: ProductSection;
  placement?: 'fixed' | 'embedded';
};

/**
 * The four-tab bar, drawn as the Claude design draws it (Atelier App.dc.html,
 * TAB BAR): a paper surface over a 1px line, each tab an icon in a 44×28 pill
 * over an 11px sentence-case label; the active tab gets the line-coloured pill,
 * ink text and the bold weight. The icons are the Bauhaus mark's shapes with
 * the design's rounded corners.
 *
 * The nav carries the `av2` class itself, so the system's tokens (and its
 * light/dark handling) resolve on every page it sits under — the legacy pages
 * included. Routes, labels and the fixed/embedded placements are unchanged.
 */
export default function PhoneProductNav({ active, placement = 'fixed' }: PhoneProductNavProps) {
  const router = useRouter();
  const activeSection = active || resolveProductSection(router.pathname);

  return (
    <nav className={`av2 av2-tabbar phone-product-nav ${placement}`} aria-label="Primary">
      {PHONE_PRODUCT_TABS.map((item) => {
        const isActive = item.id === activeSection;
        return (
          <Link
            key={item.id}
            className="av2-tabbar__tab"
            href={item.href}
            aria-current={isActive ? 'page' : undefined}
          >
            <span className="av2-tab__pill" aria-hidden="true">
              <PhoneProductIcon kind={item.icon} active={isActive} />
            </span>
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function PhoneProductIcon({
  kind,
  active,
}: {
  kind: 'mark' | 'mission' | 'feuilleton' | 'book';
  active: boolean;
}) {
  if (kind === 'mark') {
    // The brand's four-shape mark in its own colours — the one full-colour
    // spot in the otherwise monochrome nav, in both themes.
    return (
      <svg width="16" height="16" viewBox="0 0 28 28" aria-hidden="true">
        <rect x="0" y="0" width="11" height="11" rx="2" fill="var(--av2-ink)" />
        <circle cx="22" cy="6" r="6" fill="var(--av2-blue)" />
        <rect x="0" y="17" width="11" height="11" rx="2" fill="var(--av2-yellow)" />
        <path d="M17 28L23 16L28 28H17Z" fill="var(--av2-red)" />
      </svg>
    );
  }
  const common = {
    width: 18,
    height: 18,
    viewBox: '0 0 20 20',
    fill: 'none',
    stroke: 'currentColor',
    'aria-hidden': true as const,
  };
  if (kind === 'mission') {
    return (
      <svg {...common}>
        <path
          d="M10 2.5 18 17.5H2L10 2.5Z"
          strokeWidth={2}
          strokeLinejoin="round"
          fill={active ? 'currentColor' : 'none'}
        />
      </svg>
    );
  }
  if (kind === 'feuilleton') {
    return (
      <svg {...common}>
        <rect x="3" y="3" width="14" height="14" rx="3" strokeWidth={2} />
        <path d="M10 3V17M3 10H17" strokeWidth={1.5} />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <rect x="3" y="2" width="13" height="16" rx="2" strokeWidth={1.8} />
      <path d="M11 2v8l-2-2-2 2V2" fill="currentColor" strokeWidth={1.5} />
    </svg>
  );
}
