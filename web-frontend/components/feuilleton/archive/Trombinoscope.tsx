/**
 * WP-96/97 «Le trombinoscope» — the cast, inside the Feuilleton's one surface.
 *
 * Replaces /serial/cast. One card per character: the face in the mood the
 * story left them in, the register («tu depuis le 12 sept.» / «vous»), ONE
 * relationship meter — the engine's trust, which can fall — and «Ce que
 * {name} sait de vous» (what they witnessed, at most five, dated). The
 * closeness pips, a count that only went up, are gone.
 *
 * The learner's own card (POV or avatar) comes with it unchanged: the same
 * endpoint, the same choice.
 */

import React, { useState } from 'react';

import { Action, Chip, Surface, textAnswerField } from '@/components/atelier-v2/ui';
import { fbFill, feuilletonCopy, type FeuilletonCopy } from '@/components/feuilleton/feuilleton-copy';
import { expressionForMood, faceSrcFor } from '@/lib/cast-faces';
import { frenchSpacing } from '@/lib/french-typography';
import apiService, { type SerialCastMember } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { archiveCopy, archiveDate, faFill } from './archive-copy';
import { TrustMeter } from './ArchiveMarks';
import { castRegister, castTrust, knownAboutYou, registerLine } from './trombinoscope-model';

const AVATAR_REFERENCE_ASSET = 'assets/serial/characters/user/model-sheet.webp';

/* WP-61: the living story's mood per character (-2..2), in a sentence that
   needs no gender agreement. A neutral mood says nothing. */
const MOOD_LINES: Record<number, keyof FeuilletonCopy> = {
  [-2]: 'mood_m2',
  [-1]: 'mood_m1',
  1: 'mood_p1',
  2: 'mood_p2',
};

function initial(name?: string | null): string {
  return (name || '').trim().charAt(0).toUpperCase() || '?';
}

export function Trombinoscope({
  cast,
  language = null,
  withAvatar = true,
}: {
  cast: SerialCastMember[];
  language?: ControlLanguage | null;
  /** The learner's own card (saves through the API); off in the gallery. */
  withAvatar?: boolean;
}) {
  return (
    <div className="fa-cast" data-trombinoscope="">
      {withAvatar && <LearnerCard language={language} />}
      {cast.map((member) => (
        <CastCard key={member.id} member={member} language={language} />
      ))}
    </div>
  );
}

function LearnerCard({ language }: { language: ControlLanguage | null }) {
  const t = feuilletonCopy(language);
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState<'avatar' | 'pov'>('pov');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [open, setOpen] = useState(false);

  async function save(next: 'avatar' | 'pov') {
    setSaving(true);
    setMessage('');
    try {
      const references = [AVATAR_REFERENCE_ASSET];
      const payload = await apiService.setSerialAvatar({
        mode: next,
        description,
        reference_images: next === 'avatar' ? references : [],
        avatar_builder: next === 'avatar' ? { description, reference: references[0] } : {},
      });
      setMode(payload.protagonist_mode === 'avatar' ? 'avatar' : 'pov');
      setMessage(payload.protagonist_mode === 'avatar' ? t.avatar_saved : t.pov_saved);
    } catch (error) {
      console.error(error);
      setMessage(t.avatar_failed);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Surface as="section" tone="ink" className="fa-card cast-me" aria-label={t.your_character}>
      <div className="fa-card__top">
        <span className="fa-portrait fa-portrait--me" aria-hidden="true">T</span>
        <div className="fa-card__id">
          <p className="av2-label">{t.your_character}</p>
          <p className="av2-headline av2-headline--rule">{mode === 'avatar' ? t.avatar_visible : t.pov_mode}</p>
          {!open && <p className="av2-body">{mode === 'avatar' ? t.sheet_avatar : t.sheet_pov}</p>}
        </div>
        <Chip tone="plain" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
          {open ? t.close : t.customise}
        </Chip>
      </div>
      {open && (
        <div className="cast-me__body">
          {textAnswerField({
            label: t.descriptor,
            value: description,
            rows: 1,
            placeholder: t.descriptor_placeholder,
            disabled: saving,
            onChange: setDescription,
          })}
          <div className="cast-me__actions">
            <Action tone="reward" pending={saving} pendingLabel={t.saving} onClick={() => void save('avatar')}>
              {t.use_avatar}
            </Action>
            <Action tone="secondary" disabled={saving} onClick={() => void save('pov')}>
              {t.stay_pov}
            </Action>
          </div>
          {message && (
            <p className="av2-label" role="status">
              {message}
            </p>
          )}
        </div>
      )}
    </Surface>
  );
}

export function CastCard({ member, language = null }: { member: SerialCastMember; language?: ControlLanguage | null }) {
  const fb = feuilletonCopy(language);
  const t = archiveCopy(language);
  const mood = Number(member.relationship?.mood ?? 0);
  const moodKey = MOOD_LINES[Math.round(mood)];
  const moodLine = moodKey ? fbFill(fb[moodKey], { name: member.name }) : '';
  const face = faceSrcFor([member.id, member.name], expressionForMood(mood));
  const { register } = castRegister(member as any);
  const trust = castTrust(member as any);
  const known = knownAboutYou(member as any);

  return (
    <Surface
      as="article"
      className="fa-card"
      aria-label={member.name}
      data-cast={member.id}
      style={member.accent_colour ? ({ ['--cast-accent' as string]: member.accent_colour } as React.CSSProperties) : undefined}
    >
      <div className="fa-card__top">
        <span className="fa-portrait" aria-hidden="true">
          {face ? (
            // WP-77: the face that matches how they feel about you right now.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={face} alt="" data-mood={expressionForMood(mood)} />
          ) : member.model_sheet_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={member.model_sheet_url} alt="" />
          ) : (
            initial(member.name)
          )}
        </span>
        <div className="fa-card__id">
          <p className="av2-headline av2-headline--rule">{member.name}</p>
          {member.role && (
            <p className="av2-label" lang="fr">
              {member.role}
            </p>
          )}
          <p className="fa-register" data-register={register}>
            {registerLine(member as any, language)}
          </p>
        </div>
      </div>

      <div className="fa-trust-row">
        <span className="av2-label">{t.trust_label}</span>
        <TrustMeter trust={trust} language={language} />
      </div>

      {moodLine ? <p className="av2-body">{moodLine}</p> : null}

      <div className="fa-known-block">
        <p className="av2-label">{faFill(t.known_label, { name: member.name })}</p>
        {known.length ? (
          <ul className="fa-known">
            {known.map((fact, index) => (
              <li key={`${fact.scene_id || fact.date || 'k'}-${index}`}>
                <span className="fa-known__date">{archiveDate(fact.date, language)}</span>
                <span className="fa-known__text" lang="fr">
                  {frenchSpacing(fact.text_fr)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="av2-body">{faFill(t.known_none, { name: member.name })}</p>
        )}
      </div>
    </Surface>
  );
}

export default Trombinoscope;
