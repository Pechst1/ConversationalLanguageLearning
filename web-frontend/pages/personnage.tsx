/**
 * Ton personnage — the editor, full screen.
 *
 *   /personnage                      change your character, then back to the Cahier's «Moi»
 *   /personnage?next=/somewhere      …then back there
 *   /personnage?tab=extras           open on one tab (the wardrobe's way in)
 *   /personnage?first=1&next=…       onboarding: right after sign-up, before the first scene;
 *                                    no way out but making one
 *
 * A learner without a character starts from a roll of the dice, so the first thing they see
 * is someone, not a blank.
 */
import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { AvatarEditor, EDITOR_TABS, type EditorTab } from '@/components/avatar/AvatarEditor';
import { AvatarStyles } from '@/components/avatar/AvatarStyles';
import { avatarCopy } from '@/components/avatar/avatar-copy';
import type { AvatarConfig } from '@/lib/avatar';
import { normalizeAvatar, randomAvatar } from '@/lib/avatar';
import { sanitizeAuthCallbackUrl } from '@/lib/app-auth';
import { saveLearnerAvatar, useLearnerAvatar } from '@/lib/learner-avatar';
import { useChromeLanguage } from '@/lib/learner-language';

/** Where the editor goes when it closes, unless `next` says otherwise. */
const AFTER_EDIT = '/notebook?mode=moi';
/** Where a new account goes once its character is made (WP-75's landing). */
const AFTER_FIRST = '/atelier?start=today';

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default function PersonnagePage() {
  const router = useRouter();
  const language = useChromeLanguage();
  const copy = avatarCopy(language);
  const { avatar, unlocked, rewards, load } = useLearnerAvatar();
  const [initial, setInitial] = useState<AvatarConfig | null>(null);

  const first = firstValue(router.query.first) === '1';
  const next = sanitizeAuthCallbackUrl(router.query.next, first ? AFTER_FIRST : AFTER_EDIT);
  const tabQuery = firstValue(router.query.tab);
  const initialTab: EditorTab = EDITOR_TABS.some((tab) => tab.id === tabQuery) ? (tabQuery as EditorTab) : 'face';

  // Start from the character the server holds, not the cached copy: the editor saves what it
  // starts from, so it must be this learner's. Offline, the cached one; without any, a roll.
  useEffect(() => {
    if (initial || load === 'loading') return;
    setInitial(avatar ? normalizeAvatar(avatar, unlocked) : randomAvatar(Math.random, unlocked));
  }, [avatar, initial, load, unlocked]);

  const onSave = useCallback(
    async (config: AvatarConfig) => {
      const result = await saveLearnerAvatar(config);
      if (result.ok) return { error: null };
      if (result.reason === 'locked') return { error: copy.save_locked, config: normalizeAvatar(config, unlocked) };
      return { error: copy.save_failed };
    },
    [copy, unlocked],
  );

  const leave = useCallback(() => {
    void router.replace(next);
  }, [next, router]);

  return (
    <>
      <Head>
        <title>{`${first ? copy.first_title : copy.page_title} · L’Atelier`}</title>
      </Head>
      <AvatarStyles />
      <AtelierV2Root as="main" language={language} className="pe-page" aria-label={copy.page_title}>
        {router.isReady ? (
          <AvatarEditor
            copy={copy}
            initial={initial}
            unlocked={unlocked}
            rewards={rewards}
            first={first}
            initialTab={initialTab}
            onSave={onSave}
            onClose={leave}
            onDone={leave}
          />
        ) : null}
      </AtelierV2Root>
    </>
  );
}
