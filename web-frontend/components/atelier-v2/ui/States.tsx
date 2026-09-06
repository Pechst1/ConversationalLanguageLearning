/**
 * Empty, loading and error states, and the four-tab navigation (WP-01).
 *
 * The design has no artboard for "nothing here", "still loading" or "that
 * failed" — a static canvas never fails. These are extended from its own
 * primitives rather than invented: the outlined dashed surface it uses for a
 * locked episode becomes `empty`; the blush feedback tint becomes `error`; the
 * shape vocabulary carries the state non-verbally alongside a real sentence.
 */

import React from 'react';

import { Action, type ActionTone } from './Action';
import { ShapeToken } from './Shapes';

export type StateBlockProps = {
  tone: 'empty' | 'loading' | 'error';
  title: string;
  body?: React.ReactNode;
  action?: { label: string; onSelect: () => void; tone?: ActionTone };
};

export function StateBlock({ tone, title, body, action }: StateBlockProps) {
  return (
    <div
      className="av2-state"
      data-tone={tone}
      role={tone === 'error' ? 'alert' : 'status'}
      aria-busy={tone === 'loading' || undefined}
    >
      <span className="av2-state__shapes" aria-hidden="true">
        {tone === 'error' ? (
          <ShapeToken kind="action" />
        ) : tone === 'loading' ? (
          <ShapeToken kind="story" />
        ) : (
          <ShapeToken kind="done" />
        )}
      </span>
      <h2 className="av2-headline av2-headline--rule">{title}</h2>
      {body && <p className="av2-body av2-body--lg">{body}</p>}
      {action && (
        <Action tone={action.tone ?? 'secondary'} inline onClick={action.onSelect}>
          {action.label}
        </Action>
      )}
    </div>
  );
}

/**
 * A placeholder with the shape of the content that is coming.
 *
 * `aria-hidden`, with the real "loading" message carried by a sibling
 * `StateBlock` or an `aria-busy` region — a screen reader must hear a sentence,
 * not a description of grey rectangles.
 */
export function Skeleton({ height = 56, radius }: { height?: number; radius?: number }) {
  return (
    <div
      className="av2-skeleton"
      aria-hidden="true"
      style={{ height, borderRadius: radius }}
    />
  );
}

// ---------------------------------------------------------------------------
// Tab bar
// ---------------------------------------------------------------------------

export type TabKey = 'atelier' | 'missions' | 'serial' | 'notebook';

export type TabDefinition = {
  key: TabKey;
  label: string;
  onSelect: () => void;
};

/**
 * The design's four French tabs — Atelier · Missions · Feuilleton · Cahier —
 * with the icons drawn from the Bauhaus mark's own shapes. The active tab is
 * an icon inside a 44×28 `#e8e0cf` pill with a 700 label; inactive is muted
 * 600. Labels are localized rather than hard-coded French, because the product
 * decision is that a learner must not have to learn the chrome vocabulary.
 *
 * `aria-current="page"` carries the active state, so it is not colour alone.
 *
 * The design hides the tabs on Séance and Lexique, which are immersive. That
 * is the caller's decision — this component simply is not rendered there.
 *
 * Ownership note: `components/layout/**` belongs to the frontend lead, so this
 * is the primitive only. It is not wired into the app shell here.
 */
export function TabBar({
  tabs,
  active,
  label,
}: {
  tabs: TabDefinition[];
  active: TabKey;
  label: string;
}) {
  return (
    <nav className="av2-tabs" aria-label={label}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className="av2-tab"
          aria-current={tab.key === active ? 'page' : undefined}
          onClick={tab.onSelect}
        >
          <span className="av2-tab__pill" aria-hidden="true">
            <TabGlyph tab={tab.key} />
          </span>
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}

function TabGlyph({ tab }: { tab: TabKey }) {
  if (tab === 'atelier') {
    // The mark itself: all four shapes.
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
  if (tab === 'missions') {
    return (
      <svg {...common}>
        <path d="M10 2.5 18 17.5H2L10 2.5Z" strokeWidth={2} strokeLinejoin="round" />
      </svg>
    );
  }
  if (tab === 'serial') {
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
