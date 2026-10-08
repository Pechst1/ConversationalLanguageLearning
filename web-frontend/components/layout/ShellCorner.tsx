/**
 * One way to Settings, in the same place on every tab (owner, 2026-10-01): a cog
 * in the top-right corner of La Une, Feuilleton, Courrier and Cahier. It scrolls
 * with the page (absolute, not fixed) so it never sits over the reading.
 */
import React from 'react';
import Link from 'next/link';

import { GearIcon } from '@/components/atelier-v2/ui/Shapes';
import { useLearnerProfile } from '@/lib/learner-language';
import { resolveSettingsLanguage, settingsCopy } from '@/lib/settings-copy';

export function ShellCorner({ href = '/settings', label: given }: { href?: string; label?: string }) {
  const profile = useLearnerProfile();
  const label = given || settingsCopy(resolveSettingsLanguage(profile.language)).page_label;
  return (
    <Link className="av2 shell-corner av2-icon-btn" href={href} aria-label={label} title={label} data-shell-corner="">
      <GearIcon size={22} />
    </Link>
  );
}

export default ShellCorner;
