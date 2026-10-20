/**
 * Le Cahier · Moi — the learner's own page: their character, a few facts about them, and the
 * wardrobe of pieces their achievements win.
 *
 * The character is the door to the editor (a tap opens `/personnage`); without one there is a
 * big «+». The wardrobe is the achievement list told as rewards: every achievement brings a piece
 * to wear, shown on the learner's own character, with how far they are from it. An earned piece
 * is put on (or taken off) right here.
 */
import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import { Action, LockIcon, StateBlock, useControlLanguage } from '@/components/atelier-v2/ui';
import type { ExpressionId, GestureId } from '@/components/cast/vivant/kit';
import type { AvatarConfig, AvatarSlot } from '@/lib/avatar';
import { DEFAULT_AVATAR, SLOT_OPTIONS } from '@/lib/avatar';
import { saveLearnerAvatar, useLearnerAvatar } from '@/lib/learner-avatar';
import { oncePerLoad } from '@/lib/once-per-load';
import api from '@/services/api';

import { Avatar } from './Avatar';
import { AvatarPortrait, SLOT_VIEW, partName } from './AvatarEditor';
import { avatarCopy, fill, type AvatarCopy } from './avatar-copy';

/** The editor, coming back to this page when it closes. */
export const EDIT_HREF = `/personnage?next=${encodeURIComponent('/notebook?mode=moi')}`;

type Me = {
  full_name?: string | null;
  native_language?: string | null;
  cefr_estimate?: string | null;
  current_streak?: number | null;
  longest_streak?: number | null;
  daily_goal_minutes?: number | null;
};

function languageName(copy: AvatarCopy, code: string | null | undefined): string | null {
  const base = String(code || '').toLowerCase().split(/[-_]/)[0];
  if (base === 'fr') return copy.language_fr;
  if (base === 'en') return copy.language_en;
  if (base === 'de') return copy.language_de;
  return base || null;
}

function days(copy: AvatarCopy, n: number): string {
  return fill(n === 1 ? copy.streak_value_one : copy.streak_value_many, { n });
}

/** What the slot holds when the piece is taken off: the slot's first, plain choice. */
function bare(slot: AvatarSlot): string {
  return slot === 'top' ? 'pull' : SLOT_OPTIONS[slot][0];
}

export default function ProfileTab() {
  const copy = avatarCopy(useControlLanguage());
  const { avatar, rewards, load, reload } = useLearnerAvatar();
  const [me, setMe] = useState<Me | null>(null);
  const [beat, setBeat] = useState<{ n: number; expression: ExpressionId; gesture: GestureId | null }>({
    n: 0,
    expression: 'joie',
    gesture: 'salut',
  });
  const [busyItem, setBusyItem] = useState<string | null>(null);
  const [wearError, setWearError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    oncePerLoad('users/me', () => api.getCurrentUser())
      .then((payload) => {
        if (alive) setMe((payload ?? null) as Me | null);
      })
      .catch(() => {
        if (alive) setMe(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  const wear = async (slot: AvatarSlot, item: string) => {
    if (!avatar || busyItem) return;
    const worn = avatar[slot] === item;
    const next: AvatarConfig = { ...avatar, [slot]: worn ? bare(slot) : item };
    setBusyItem(item);
    setWearError(null);
    const result = await saveLearnerAvatar(next);
    setBusyItem(null);
    if (!result.ok) {
      setWearError(result.reason === 'locked' ? copy.save_locked : copy.save_failed);
      return;
    }
    setBeat((current) => ({ n: current.n + 1, expression: worn ? 'neutre' : 'fier', gesture: worn ? null : 'montre' }));
  };

  const earned = rewards.filter((reward) => reward.unlocked).length;

  return (
    <div className="mo" data-profile="">
      {avatar ? (
        <section className="mo-hero" aria-label={copy.disc_label}>
          <Link href={EDIT_HREF} className="mo-hero__stage" aria-label={copy.edit_action}>
            <span className="mo-hero__floor" aria-hidden="true" />
            <Avatar
              key={beat.n}
              config={avatar}
              expression={beat.expression}
              gesture={beat.gesture}
              crop="full"
              size={200}
              className="mo-hero__figure"
            />
          </Link>
          <div className="mo-hero__side">
            <p className="av2-headline av2-headline--title mo-hero__name">{me?.full_name?.trim() || copy.disc_label}</p>
            {me?.cefr_estimate ? <p className="mo-hero__meta">{me.cefr_estimate}</p> : null}
            <Link href={EDIT_HREF} className="av2-btn av2-btn--secondary av2-btn--inline mo-hero__edit">
              {copy.edit_action}
            </Link>
          </div>
        </section>
      ) : load === 'loading' ? (
        <section className="mo-hero mo-hero--wait" aria-busy="true" />
      ) : (
        <section className="mo-make">
          <Link href={EDIT_HREF} className="mo-make__plus" aria-label={copy.make_action}>
            <svg viewBox="0 0 24 24" width="44" height="44" aria-hidden="true" focusable="false">
              <path d="M12 4v16M4 12h16" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" />
            </svg>
          </Link>
          <div className="mo-make__text">
            <h2 className="av2-headline av2-headline--title">{copy.make_title}</h2>
            <p className="mo-make__body">{copy.make_body}</p>
            <Link href={EDIT_HREF} className="av2-btn av2-btn--primary av2-btn--inline">
              {copy.make_action}
            </Link>
          </div>
        </section>
      )}

      <section className="mo-block" aria-labelledby="mo-about">
        <h2 className="mo-block__h" id="mo-about">
          {copy.about_title}
        </h2>
        <NameLine copy={copy} name={me?.full_name ?? null} onSaved={(full_name) => setMe((current) => ({ ...(current ?? {}), full_name }))} />
        <dl className="mo-lines">
          {languageName(copy, me?.native_language) ? (
            <div className="mo-line">
              <dt>{copy.speaks}</dt>
              <dd>{languageName(copy, me?.native_language)}</dd>
            </div>
          ) : null}
          {me?.cefr_estimate ? (
            <div className="mo-line">
              <dt>{copy.level}</dt>
              <dd>{me.cefr_estimate}</dd>
            </div>
          ) : null}
          {me ? (
            <div className="mo-line">
              <dt>{copy.streak}</dt>
              <dd>
                {days(copy, Number(me.current_streak || 0))}
                {Number(me.longest_streak || 0) > Number(me.current_streak || 0)
                  ? ` · ${copy.record} ${days(copy, Number(me.longest_streak))}`
                  : ''}
              </dd>
            </div>
          ) : null}
          {me?.daily_goal_minutes ? (
            <div className="mo-line">
              <dt>{copy.goal}</dt>
              <dd>{fill(copy.goal_value, { n: me.daily_goal_minutes })}</dd>
            </div>
          ) : null}
        </dl>
        <Link href="/settings" className="mo-settings">
          {copy.settings_link}
        </Link>
      </section>

      <section className="mo-block" aria-labelledby="mo-wardrobe">
        <div className="mo-block__head">
          <h2 className="mo-block__h" id="mo-wardrobe">
            {copy.wardrobe_title}
          </h2>
          {rewards.length > 0 ? (
            <span className="mo-count">{fill(copy.wardrobe_count, { n: earned, total: rewards.length })}</span>
          ) : null}
        </div>
        <p className="mo-lede">{copy.wardrobe_lede}</p>
        {load === 'failed' && rewards.length === 0 ? (
          <StateBlock tone="error" title={copy.wardrobe_failed} action={{ label: copy.retry, onSelect: reload }} />
        ) : null}
        {wearError ? (
          <p className="mo-err" role="alert">
            {wearError}
          </p>
        ) : null}
        <ul className="mo-wardrobe">
          {rewards.map((reward) => {
            const slot = reward.slot as AvatarSlot;
            const base = avatar ?? DEFAULT_AVATAR;
            const worn = Boolean(avatar && avatar[slot] === reward.item);
            const current = Math.min(reward.current, reward.target);
            const name = partName(copy, slot, reward.item);
            return (
              <li key={reward.item} className={['mo-piece', reward.unlocked ? 'mo-piece--won' : ''].filter(Boolean).join(' ')} data-item={reward.item}>
                <span className="mo-piece__art" aria-hidden="true">
                  <AvatarPortrait config={{ ...base, [slot]: reward.item }} view={SLOT_VIEW[slot] ?? 'head'} size={84} />
                  {!reward.unlocked ? (
                    <span className="mo-piece__lock">
                      <LockIcon size={14} />
                    </span>
                  ) : null}
                </span>
                <span className="mo-piece__main">
                  <span className="mo-piece__name">{name}</span>
                  <span className="mo-piece__how">{copy.earn[reward.achievement_key] ?? reward.description ?? ''}</span>
                  {reward.unlocked ? (
                    avatar ? (
                      <button
                        type="button"
                        className="mo-piece__wear"
                        aria-pressed={worn}
                        disabled={busyItem !== null}
                        onClick={() => void wear(slot, reward.item)}
                      >
                        {worn ? `✓ ${copy.item_worn}` : copy.item_wear}
                      </button>
                    ) : (
                      <span className="mo-piece__yours">{copy.item_yours}</span>
                    )
                  ) : (
                    <span className="mo-piece__progress">
                      <span
                        className="mo-bar"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={reward.target}
                        aria-valuenow={current}
                        aria-label={`${name} · ${fill(copy.progress, { current, target: reward.target })}`}
                      >
                        <span className="mo-bar__fill" style={{ width: `${Math.round((current / Math.max(1, reward.target)) * 100)}%` }} />
                      </span>
                      <span className="mo-piece__count">{fill(copy.progress, { current, target: reward.target })}</span>
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

/** The first name, changed in place. */
function NameLine({ copy, name, onSaved }: { copy: AvatarCopy; name: string | null; onSaved: (name: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  const start = () => {
    setDraft(name ?? '');
    setFailed(false);
    setEditing(true);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const value = draft.trim().slice(0, 80);
    if (!value) return;
    setPending(true);
    setFailed(false);
    try {
      await api.updateProfile({ full_name: value });
      onSaved(value);
      setEditing(false);
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  };

  if (!editing) {
    return (
      <div className="mo-name">
        <span className="mo-name__l">{copy.name}</span>
        <span className="mo-name__v">{name?.trim() || <span className="mo-name__none">{copy.name_none}</span>}</span>
        <button type="button" className="mo-name__edit" onClick={start}>
          {copy.name_edit}
        </button>
      </div>
    );
  }
  return (
    <form className="mo-name mo-name--edit" onSubmit={submit}>
      <label className="mo-name__l" htmlFor="mo-name-input">
        {copy.name}
      </label>
      <input
        id="mo-name-input"
        className="mo-name__input"
        value={draft}
        maxLength={80}
        autoComplete="given-name"
        autoFocus
        onChange={(event) => setDraft(event.target.value)}
      />
      <div className="mo-name__actions">
        <Action tone="quiet" inline onClick={() => setEditing(false)} disabled={pending}>
          {copy.name_cancel}
        </Action>
        <Action tone="story" inline type="submit" pending={pending} pendingLabel={copy.saving} disabled={!draft.trim()}>
          {copy.name_save}
        </Action>
      </div>
      {failed ? (
        <p className="mo-err" role="alert">
          {copy.name_failed}
        </p>
      ) : null}
    </form>
  );
}
