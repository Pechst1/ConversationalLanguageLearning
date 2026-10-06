/**
 * The second way in (owner, 2026-10-01): tapping the Atelier mark on La Une opens
 * a short sheet with the settings people flip often, here the drawn or painted
 * cast, and a link to all settings. Everything else stays in Réglages.
 */
import React from 'react';
import Link from 'next/link';

import { BottomSheet } from '@/components/atelier-v2/ui';
import { setArtSet, useArtSet } from '@/lib/art-set';
import { useLearnerProfile } from '@/lib/learner-language';
import { resolveSettingsLanguage, settingsCopy } from '@/lib/settings-copy';

export function QuickSettings({ open, onClose }: { open: boolean; onClose: () => void }) {
  const profile = useLearnerProfile();
  const copy = settingsCopy(resolveSettingsLanguage(profile.language));
  const art = useArtSet();
  const options = [
    { value: 'drawn' as const, label: copy.cast_art_drawn },
    { value: 'painted' as const, label: copy.cast_art_painted },
  ];
  return (
    <BottomSheet open={open} onClose={onClose} title={copy.quick_title}>
      <div className="av2-stack quick-settings" data-quick-settings="">
        <div>
          <p className="av2-body quick-settings__label">{copy.row_cast_art}</p>
          <p className="av2-label">{copy.row_cast_art_hint}</p>
        </div>
        <div className="quick-settings__seg" role="radiogroup" aria-label={copy.row_cast_art}>
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={art === option.value}
              className="quick-settings__opt"
              data-on={art === option.value ? '' : undefined}
              onClick={() => setArtSet(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <Link className="av2-label quick-settings__all" href="/settings" onClick={onClose}>
          {copy.quick_all} →
        </Link>
      </div>
      <style jsx global>{`
        .av2 .quick-settings { gap: 14px; padding-bottom: 8px; }
        .av2 .quick-settings__label { margin: 0; font-weight: 600; }
        .av2 .quick-settings__seg { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .av2 .quick-settings__opt {
          min-height: var(--av2-tap);
          border: 0;
          border-radius: var(--av2-r-button);
          background: var(--av2-paper);
          color: var(--av2-ink);
          font: 600 var(--av2-t-body-lg) / 1 var(--av2-sans);
          box-shadow: 0 var(--av2-press-sm) 0 var(--av2-line-2);
          cursor: pointer;
        }
        .av2 .quick-settings__opt[data-on] {
          background: var(--av2-ink);
          color: var(--av2-on-ink);
          box-shadow: 0 var(--av2-press-sm) 0 var(--av2-ink-deep);
        }
        .av2 .quick-settings__all { color: var(--av2-ink); text-decoration: underline; text-underline-offset: 3px; }
      `}</style>
    </BottomSheet>
  );
}

export default QuickSettings;
