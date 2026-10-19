/**
 * Ton personnage — the editor.
 *
 * The character stands on a stage at the top and reacts to every change: a new hat is greeted
 * with a wave, glasses make it think, an accessory is shown off, a roll of the dice gets a shrug,
 * and «C’est moi !» ends on the troupe's signature jump. Below it, one tab per part of the body;
 * each choice is drawn as the learner's own character already wearing it, so a square is a
 * preview, never an icon to imagine.
 *
 * Earned pieces (`REWARDS`) are shown too, with a padlock and how far the learner is from them
 * («23 sur 50»): tapping one says how to win it instead of putting it on.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';

import { Action, CrossIcon, LockIcon } from '@/components/atelier-v2/ui';
import type { RigCrop } from '@/components/cast/rig-kit';
import type { ExpressionId, GestureId } from '@/components/cast/vivant/kit';
import type { AvatarConfig, AvatarSlot, AvatarToggle } from '@/lib/avatar';
import {
  EYE_COLOURS,
  FABRICS,
  HAIR_COLOURS,
  REWARDS,
  SKINS,
  SLOT_OPTIONS,
  isLocked,
  normalizeAvatar,
  randomAvatar,
} from '@/lib/avatar';
import type { AvatarRewardState } from '@/services/api';

import { Avatar } from './Avatar';
import { fill, type AvatarCopy } from './avatar-copy';

/** A square of the figure's 200×420 frame to zoom on — `[x, y, side]` — or one of its crops. */
export type AvatarView = RigCrop | [number, number, number];

const EYES_VIEW: AvatarView = [56, 98, 88];
const TOP_VIEW: AvatarView = [10, 196, 180];
const NECK_VIEW: AvatarView = [36, 176, 128];
const WRIST_VIEW: AvatarView = [20, 230, 160];
const CHEST_VIEW: AvatarView = [36, 196, 128];

/** The view that shows a slot best, for the editor's squares and the wardrobe's cards. */
export const SLOT_VIEW: Record<AvatarSlot, AvatarView> = {
  skin: 'head',
  face: 'head',
  hair: 'head',
  hairColor: 'head',
  eyes: EYES_VIEW,
  eyeColor: EYES_VIEW,
  brows: EYES_VIEW,
  beard: 'head',
  glasses: 'head',
  hat: 'head',
  hatColor: 'head',
  top: TOP_VIEW,
  topColor: TOP_VIEW,
  neck: NECK_VIEW,
  wrist: WRIST_VIEW,
  ears: 'head',
  pin: CHEST_VIEW,
};

/** The character, still, framed on one view, `size` pixels square (or wide, for a crop). */
export function AvatarPortrait({ config, view, size }: { config: AvatarConfig; view: AvatarView; size: number }) {
  if (typeof view === 'string') return <Avatar config={config} crop={view} size={size} still />;
  const [x, y, side] = view;
  const s = size / side;
  const style: CSSProperties = { position: 'absolute', left: -x * s, top: -y * s };
  return (
    <span className="pe-zoom" style={{ width: size, height: size }}>
      <Avatar config={config} crop="full" size={200 * s} still style={style} />
    </span>
  );
}

export type EditorTab = 'face' | 'hair' | 'eyes' | 'beard' | 'glasses' | 'hat' | 'top' | 'extras';

type Section =
  | { kind: 'parts'; slot: AvatarSlot }
  | { kind: 'colours'; slot: AvatarSlot; when?: (config: AvatarConfig) => boolean }
  | { kind: 'toggles'; keys: AvatarToggle[] }
  | { kind: 'note'; key: keyof AvatarCopy };

export const EDITOR_TABS: Array<{ id: EditorTab; label: keyof AvatarCopy; sections: Section[] }> = [
  {
    id: 'face',
    label: 'tab_face',
    sections: [
      { kind: 'colours', slot: 'skin' },
      { kind: 'parts', slot: 'face' },
      { kind: 'toggles', keys: ['freckles', 'blush'] },
    ],
  },
  {
    id: 'hair',
    label: 'tab_hair',
    sections: [
      { kind: 'parts', slot: 'hair' },
      { kind: 'colours', slot: 'hairColor', when: (config) => config.hair !== 'chauve' },
    ],
  },
  {
    id: 'eyes',
    label: 'tab_eyes',
    sections: [
      { kind: 'colours', slot: 'eyeColor' },
      { kind: 'parts', slot: 'eyes' },
      { kind: 'parts', slot: 'brows' },
      { kind: 'toggles', keys: ['lashes'] },
    ],
  },
  { id: 'beard', label: 'tab_beard', sections: [{ kind: 'parts', slot: 'beard' }, { kind: 'note', key: 'beard_colour_note' }] },
  { id: 'glasses', label: 'tab_glasses', sections: [{ kind: 'parts', slot: 'glasses' }] },
  {
    id: 'hat',
    label: 'tab_hat',
    sections: [
      { kind: 'parts', slot: 'hat' },
      { kind: 'colours', slot: 'hatColor', when: (config) => config.hat !== 'aucun' },
    ],
  },
  { id: 'top', label: 'tab_top', sections: [{ kind: 'parts', slot: 'top' }, { kind: 'colours', slot: 'topColor' }] },
  {
    id: 'extras',
    label: 'tab_extras',
    sections: [
      { kind: 'parts', slot: 'neck' },
      { kind: 'parts', slot: 'wrist' },
      { kind: 'parts', slot: 'ears' },
      { kind: 'parts', slot: 'pin' },
    ],
  },
];

/** The tab that holds a slot (the wardrobe opens the editor on it). */
export function tabForSlot(slot: AvatarSlot): EditorTab {
  const found = EDITOR_TABS.find((tab) => tab.sections.some((section) => 'slot' in section && section.slot === slot));
  return found ? found.id : 'face';
}

/** The colour a swatch shows. */
function swatchColour(slot: AvatarSlot, id: string): string {
  if (slot === 'skin') return SKINS[id]?.skin ?? SKINS.s3.skin;
  if (slot === 'hairColor') return HAIR_COLOURS[id]?.hair ?? HAIR_COLOURS.chatain.hair;
  if (slot === 'eyeColor') return EYE_COLOURS[id] ?? EYE_COLOURS.bruns;
  return FABRICS[id] ?? FABRICS.marine;
}

/** A part's name in the copy table, or its id when the table has none. */
export function partName(copy: AvatarCopy, slot: AvatarSlot, value: string): string {
  return copy.parts[`${slot}.${value}`] ?? value;
}

function swatchName(copy: AvatarCopy, slot: AvatarSlot, id: string): string {
  if (slot === 'skin') return fill(copy.skin_tone, { n: SLOT_OPTIONS.skin.indexOf(id) + 1 });
  return copy.colours[id] ?? id;
}

/** How the character greets a change of each slot. */
export function reactionFor(slot: AvatarSlot | AvatarToggle): { expression: ExpressionId; gesture: GestureId | null } {
  switch (slot) {
    case 'hat':
    case 'hatColor':
      return { expression: 'joie', gesture: 'salut' };
    case 'glasses':
      return { expression: 'malice', gesture: 'reflechit' };
    case 'top':
    case 'topColor':
      return { expression: 'joie', gesture: 'bravo' };
    case 'neck':
    case 'wrist':
    case 'ears':
    case 'pin':
      return { expression: 'fier', gesture: 'montre' };
    case 'eyes':
    case 'eyeColor':
    case 'brows':
    case 'lashes':
      return { expression: 'surprise', gesture: null };
    case 'hair':
    case 'hairColor':
    case 'beard':
      return { expression: 'malice', gesture: null };
    default:
      return { expression: 'joie', gesture: null };
  }
}

export interface AvatarEditorProps {
  copy: AvatarCopy;
  /** where the editor starts; null while the learner's record is loading */
  initial: AvatarConfig | null;
  unlocked: string[];
  rewards: AvatarRewardState[];
  /** onboarding: a title that asks, and no way out but making one */
  first?: boolean;
  initialTab?: EditorTab;
  /** save the record; resolves to an error message, or null when saved */
  onSave: (config: AvatarConfig) => Promise<{ error: string | null; config?: AvatarConfig }>;
  onClose?: () => void;
  /** called once the signature jump has played after a save */
  onDone: () => void;
}

type Beat = { n: number; expression: ExpressionId; gesture: GestureId | null };

function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
}

export function AvatarEditor({
  copy,
  initial,
  unlocked,
  rewards,
  first = false,
  initialTab = 'face',
  onSave,
  onClose,
  onDone,
}: AvatarEditorProps) {
  const [config, setConfig] = useState<AvatarConfig | null>(initial);
  const [tab, setTab] = useState<EditorTab>(initialTab);
  const [beat, setBeat] = useState<Beat>({ n: 0, expression: first ? 'joie' : 'neutre', gesture: first ? 'salut' : null });
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const calm = useRef<ReturnType<typeof setTimeout> | null>(null);
  const panel = useRef<HTMLDivElement | null>(null);

  // The record arrives after the first render (cache, then server): start from it once.
  useEffect(() => {
    if (!config && initial) setConfig(initial);
  }, [config, initial]);

  useEffect(() => () => {
    if (calm.current) clearTimeout(calm.current);
  }, []);

  const react = useCallback((expression: ExpressionId, gesture: GestureId | null, settle = 2600) => {
    setBeat((current) => ({ n: current.n + 1, expression, gesture }));
    if (calm.current) clearTimeout(calm.current);
    if (settle > 0) {
      calm.current = setTimeout(() => setBeat((current) => ({ ...current, expression: 'neutre', gesture: null })), settle);
    }
  }, []);

  const countFor = useCallback(
    (item: string): { current: number; target: number } | null => {
      const reward = rewards.find((entry) => entry.item === item);
      return reward ? { current: Math.min(reward.current, reward.target), target: reward.target } : null;
    },
    [rewards],
  );
  const progressFor = (item: string): string | null => {
    const count = countFor(item);
    return count ? fill(copy.progress, count) : null;
  };

  const choose = (slot: AvatarSlot, value: string) => {
    if (!config) return;
    if (isLocked(slot, value, unlocked)) {
      const achievement = REWARDS[value]?.achievement;
      const progress = progressFor(value);
      setHint(
        fill(copy.locked_hint, {
          item: partName(copy, slot, value),
          how: (achievement && copy.earn[achievement]) || copy.locked,
          progress: progress ?? copy.locked,
        }),
      );
      react('emu', 'oups');
      return;
    }
    setHint(null);
    setError(null);
    if (config[slot] === value) return;
    setConfig({ ...config, [slot]: value });
    const { expression, gesture } = reactionFor(slot);
    react(expression, gesture);
  };

  const toggle = (key: AvatarToggle) => {
    if (!config) return;
    setHint(null);
    setError(null);
    setConfig({ ...config, [key]: !config[key] });
    const { expression, gesture } = reactionFor(key);
    react(expression, gesture);
  };

  const roll = () => {
    setHint(null);
    setError(null);
    setConfig(randomAvatar(Math.random, unlocked));
    react('surprise', 'oups');
  };

  const save = async () => {
    if (!config || saving) return;
    setSaving(true);
    setError(null);
    setHint(null);
    const result = await onSave(normalizeAvatar(config));
    if (result.error) {
      setSaving(false);
      setError(result.error);
      if (result.config) setConfig(result.config);
      react('emu', null);
      return;
    }
    setSaved(true);
    react('joie', 'signature', 0);
    setTimeout(onDone, prefersReducedMotion() ? 500 : 1900);
  };

  const pickTab = (next: EditorTab) => {
    setTab(next);
    setHint(null);
    if (panel.current) panel.current.scrollTop = 0;
  };

  const current = EDITOR_TABS.find((entry) => entry.id === tab) ?? EDITOR_TABS[0];

  const tiles = useMemo(() => {
    if (!config) return null;
    return current.sections.map((section, index) => {
      if (section.kind === 'note') {
        return (
          <p key={`note-${index}`} className="pe-note">
            {copy[section.key] as string}
          </p>
        );
      }
      if (section.kind === 'toggles') {
        return (
          <div key={`toggles-${index}`} className="pe-toggles">
            {section.keys.map((key) => (
              <button
                key={key}
                type="button"
                className="pe-toggle"
                aria-pressed={Boolean(config[key])}
                onClick={() => toggle(key)}
              >
                <span className="pe-toggle__box" aria-hidden="true">
                  {config[key] ? '✓' : ''}
                </span>
                {copy[`toggle_${key}` as keyof AvatarCopy] as string}
              </button>
            ))}
          </div>
        );
      }
      const { slot } = section;
      if (section.kind === 'colours') {
        if (section.when && !section.when(config)) return null;
        return (
          <section key={slot} className="pe-section" aria-labelledby={`pe-h-${slot}`}>
            <h3 className="pe-section__h" id={`pe-h-${slot}`}>
              {copy[`sec_${slot}` as keyof AvatarCopy] as string}
            </h3>
            <div className="pe-swatches" role="group" aria-labelledby={`pe-h-${slot}`}>
              {SLOT_OPTIONS[slot].map((id) => (
                <button
                  key={id}
                  type="button"
                  className="pe-swatch"
                  aria-pressed={config[slot] === id}
                  aria-label={swatchName(copy, slot, id)}
                  title={swatchName(copy, slot, id)}
                  data-value={id}
                  onClick={() => choose(slot, id)}
                >
                  <span className="pe-swatch__dot" style={{ background: swatchColour(slot, id) }} />
                </button>
              ))}
            </div>
          </section>
        );
      }
      return (
        <section key={slot} className="pe-section" aria-labelledby={`pe-h-${slot}`}>
          <h3 className="pe-section__h" id={`pe-h-${slot}`}>
            {copy[`sec_${slot}` as keyof AvatarCopy] as string}
          </h3>
          <div className="pe-grid" role="group" aria-labelledby={`pe-h-${slot}`}>
            {SLOT_OPTIONS[slot].map((value) => {
              const locked = isLocked(slot, value, unlocked);
              const count = locked ? countFor(value) : null;
              const progress = count ? fill(copy.progress, count) : null;
              const name = partName(copy, slot, value);
              return (
                <button
                  key={value}
                  type="button"
                  className={['pe-tile', locked ? 'pe-tile--locked' : ''].filter(Boolean).join(' ')}
                  aria-pressed={config[slot] === value}
                  aria-label={locked ? `${name} · ${copy.locked}${progress ? ` · ${progress}` : ''}` : name}
                  data-value={value}
                  onClick={() => choose(slot, value)}
                >
                  <span className="pe-tile__art">
                    <AvatarPortrait config={{ ...config, [slot]: value }} view={SLOT_VIEW[slot]} size={72} />
                  </span>
                  {locked ? (
                    <span className="pe-tile__lock" aria-hidden="true">
                      <LockIcon size={12} />
                      {count ? <span>{`${count.current}/${count.target}`}</span> : null}
                    </span>
                  ) : null}
                  <span className="pe-tile__name" aria-hidden="true">
                    {name}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      );
    });
    // choose/toggle only close over config, copy, unlocked and rewards
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, current, copy, unlocked, rewards]);

  return (
    <div className="pe" data-first={first ? 'true' : undefined}>
      <header className="pe-top">
        <div className="pe-top__titles">
          <h1 className="av2-headline pe-title">{first ? copy.first_title : copy.page_title}</h1>
          <p className="pe-lede">{first ? copy.first_lede : copy.edit_lede}</p>
        </div>
        {!first && onClose ? (
          <button type="button" className="av2-icon-btn pe-close" aria-label={copy.close} title={copy.close} onClick={onClose}>
            <CrossIcon size={20} />
          </button>
        ) : null}
      </header>

      <div className="pe-stage" role="img" aria-label={copy.stage_label}>
        <span className="pe-stage__floor" aria-hidden="true" />
        {config ? (
          <Avatar
            key={beat.n}
            config={config}
            expression={beat.expression}
            gesture={beat.gesture}
            crop="full"
            size={200}
            className="pe-stage__figure"
          />
        ) : (
          <span className="pe-stage__wait" aria-hidden="true" />
        )}
      </div>

      <div className="pe-tabs" role="tablist" aria-label={copy.tabs_label}>
        {EDITOR_TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            id={`pe-tab-${entry.id}`}
            aria-selected={entry.id === tab}
            aria-controls="pe-panel"
            className="pe-tab"
            onClick={() => pickTab(entry.id)}
          >
            {copy[entry.label] as string}
          </button>
        ))}
      </div>

      <div className="pe-panel" id="pe-panel" role="tabpanel" aria-labelledby={`pe-tab-${tab}`} ref={panel}>
        {tiles}
      </div>

      <footer className="pe-foot">
        <p className="pe-foot__msg" role="status" aria-live="polite">
          {error ? <span className="pe-foot__err">{error}</span> : hint ? hint : saved ? copy.saved : ''}
        </p>
        <div className="pe-foot__row">
          <Action tone="secondary" inline onClick={roll} disabled={!config || saving || saved} icon={<DiceIcon />}>
            {copy.random}
          </Action>
          <Action
            tone="primary"
            onClick={save}
            pending={saving && !saved}
            pendingLabel={copy.saving}
            disabled={!config || saved}
            data-avatar-save=""
          >
            {copy.save}
          </Action>
        </div>
      </footer>
    </div>
  );
}

function DiceIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="3.5" y="3.5" width="17" height="17" rx="4" fill="none" stroke="currentColor" strokeWidth={2.2} />
      <circle cx="8.5" cy="8.5" r="1.6" fill="currentColor" />
      <circle cx="15.5" cy="15.5" r="1.6" fill="currentColor" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" />
      <circle cx="15.5" cy="8.5" r="1.6" fill="currentColor" />
      <circle cx="8.5" cy="15.5" r="1.6" fill="currentColor" />
    </svg>
  );
}

export default AvatarEditor;
