/**
 * WP-43 — the screen foot, as the nouvelles-pages artboards draw it.
 *
 * A page's primary action (and its one quiet alternative) sit in a foot at the
 * end of the page: hairline above, paper behind, 14px of air and the safe
 * area below. It is placed **in the flow**, after the page body, never fixed
 * over it — the app shell reserves the tab bar's height at the bottom of every
 * phone page (`.app-route-shell`, WP-43), so a foot in the flow always ends
 * above the tab bar and nothing a learner must press is ever behind it
 * (WP-39, the placement finding).
 *
 * `tone` is the same tint the session's foot carries after a verdict.
 */

import React from 'react';

export type ScreenFootProps = {
  children: React.ReactNode;
  /** Verdict tint under the actions, as on the session foot. */
  tone?: 'neutral' | 'correct' | 'wrong';
  className?: string;
};

export function ScreenFoot({ children, tone = 'neutral', className }: ScreenFootProps) {
  return (
    <div
      className={['av2-screen__foot', 'av2-screen__foot--flow', className].filter(Boolean).join(' ')}
      data-tone={tone}
    >
      {children}
    </div>
  );
}

export default ScreenFoot;
