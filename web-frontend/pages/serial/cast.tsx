/* "Les personnages" — the register of the theatre.
 *
 * No artboard in the Claude design covers a cast list, so this screen is
 * extended from its primitives: the Feuilleton index head (kicker + one
 * Garamond-italic headline), the Cahier's rows (card colour, radius 16, a
 * round portrait in the character's world-bible accent), a segmented pill for
 * the learner's own character, and the design's shape tokens for closeness.
 * Behaviour is unchanged: the cast comes from the serial thread, the avatar
 * choice is saved through the same endpoint, and every episode link is the
 * server's own href. */

import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import {
  Action,
  ArrowRightIcon,
  AtelierV2Root,
  Chip,
  ShapeToken,
  Skeleton,
  Surface,
  textAnswerField,
} from '@/components/atelier-v2/ui';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader';
import apiService, { SerialCastMember } from '@/services/api';

const AVATAR_REFERENCE_ASSET = 'assets/serial/characters/user/model-sheet.webp';

function initial(name?: string | null): string {
  if (!name) return '?';
  return name.trim().charAt(0).toUpperCase() || '?';
}

export default function SerialCastPage() {
  const [cast, setCast] = useState<SerialCastMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [avatarDescription, setAvatarDescription] = useState('');
  const [avatarMode, setAvatarMode] = useState<'avatar' | 'pov'>('pov');
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [avatarMessage, setAvatarMessage] = useState('');
  const [customising, setCustomising] = useState(false);

  useEffect(() => {
    let alive = true;
    apiService.getSerialCast()
      .then((payload) => {
        if (alive) setCast(payload.cast || []);
      })
      .catch((error) => {
        console.error(error);
        if (alive) setCast([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  async function saveAvatar(mode: 'avatar' | 'pov') {
    setAvatarSaving(true);
    setAvatarMessage('');
    try {
      const references = AVATAR_REFERENCE_ASSET
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
      const payload = await apiService.setSerialAvatar({
        mode,
        description: avatarDescription,
        reference_images: mode === 'avatar' ? references : [],
        avatar_builder: mode === 'avatar' ? { description: avatarDescription, reference: references[0] || '' } : {},
      });
      setAvatarMode(payload.protagonist_mode === 'avatar' ? 'avatar' : 'pov');
      setAvatarMessage(payload.protagonist_mode === 'avatar' ? 'Avatar retenu pour les prochaines planches.' : 'Mode POV enregistré.');
    } catch (error) {
      console.error(error);
      setAvatarMessage('Impossible d’enregistrer votre personnage.');
    } finally {
      setAvatarSaving(false);
    }
  }

  const anyTu = cast.some((member) => member.relationship.register === 'tu');

  return (
    <>
      <Head>
        <title>Les personnages · Le Feuilleton · L’Atelier</title>
      </Head>
      <FeuilletonReaderStyles />
      <AtelierV2Root as="main" className="fr-page cast-page" aria-label="Le Feuilleton · les personnages">
        <header className="fr-page-head">
          <div className="k">
            {loading
              ? 'Le registre du théâtre'
              : anyTu
                ? 'Le registre du théâtre · un tutoiement accordé'
                : 'Le registre du théâtre · tout le monde vous vouvoie encore'}
          </div>
          {/* the one Garamond italic headline on this screen */}
          <h1>Les personnages</h1>
        </header>

        <div className="fr-rows">
          <Link className="fr-row" href="/serial">
            <span className="thumb" aria-hidden="true" />
            <span className="meta">
              <span className="k">Le feuilleton</span>
              <span className="t">La saison</span>
            </span>
            <span className="go" aria-hidden="true"><ArrowRightIcon size={18} /></span>
          </Link>
        </div>

        {loading ? (
          <div className="fr-skeleton" aria-live="polite" aria-busy="true">
            <span className="fr-sr">On appelle les rôles</span>
            <i />
            <i />
            <i />
          </div>
        ) : (
          <div className="cast-list">
            {/* The learner's own character: POV or avatar, saved on the thread. */}
            <Surface as="section" tone="ink" className="cast-me" aria-label="Votre personnage">
              <div className="cast-me__top">
                <span className="cast-portrait cast-portrait--me" aria-hidden="true">T</span>
                <div className="cast-me__id">
                  <p className="av2-label">Votre personnage</p>
                  <p className="av2-headline av2-headline--rule">
                    {avatarMode === 'avatar' ? 'Avatar visible' : 'Mode POV'}
                  </p>
                  {!customising && (
                    <p className="av2-body">
                      {`Private model sheet · ${avatarMode === 'avatar' ? 'style verrouillé' : 'POV — jamais dessiné'}`}
                    </p>
                  )}
                </div>
                <Chip tone="plain" onClick={() => setCustomising((value) => !value)} aria-expanded={customising}>
                  {customising ? 'Fermer' : 'Personnaliser'}
                </Chip>
              </div>
              {customising && (
                <div className="cast-me__body">
                  {textAnswerField({
                    label: 'Descripteur visuel',
                    value: avatarDescription,
                    rows: 1,
                    placeholder: 'ex. écharpe rouge, carnet',
                    disabled: avatarSaving,
                    onChange: setAvatarDescription,
                  })}
                  <div className="cast-me__actions">
                    <Action tone="reward" pending={avatarSaving} pendingLabel="Enregistrement…" onClick={() => void saveAvatar('avatar')}>
                      Utiliser l’avatar
                    </Action>
                    <Action tone="secondary" disabled={avatarSaving} onClick={() => void saveAvatar('pov')}>
                      Rester en POV
                    </Action>
                  </div>
                  {avatarMessage && (
                    <p className="av2-label" role="status">
                      {avatarMessage}
                    </p>
                  )}
                </div>
              )}
            </Surface>

            {cast.map((member) => (
              <CastCard key={member.id} member={member} />
            ))}
          </div>
        )}
      </AtelierV2Root>
      <PhoneProductNav active="feuilleton" />
      <style jsx global>{`
        body { background: var(--app-paper); }
        .av2.cast-page { min-height: 100vh; padding-bottom: calc(var(--phone-bottom-nav-space, 88px)); }
        .av2 .cast-list { display: flex; flex-direction: column; gap: 10px; padding: 18px 0 0; }

        .av2 .cast-portrait {
          flex: none;
          display: grid;
          place-items: center;
          width: 56px;
          height: 56px;
          border-radius: 999px;
          overflow: hidden;
          background: var(--cast-accent, var(--av2-char-default));
          color: var(--av2-on-dark);
          font-family: var(--av2-serif);
          font-style: italic;
          font-weight: 600;
          font-size: var(--av2-t-title);
          line-height: 1;
        }
        .av2 .cast-portrait img { width: 100%; height: 100%; object-fit: cover; display: block; }
        .av2 .cast-portrait--me { background: var(--av2-card); color: var(--av2-ink); }

        /* the learner's card: the design's ink surface */
        .av2 .cast-me { display: flex; flex-direction: column; gap: 12px; }
        .av2 .cast-me__top { display: flex; align-items: center; gap: 14px; min-width: 0; }
        .av2 .cast-me__id { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
        .av2 .cast-me .av2-label, .av2 .cast-me .av2-body, .av2 .cast-me .av2-headline { color: inherit; }
        .av2 .cast-me .av2-chip { background: var(--av2-card); color: var(--av2-ink); }
        .av2 .cast-me__body { display: flex; flex-direction: column; gap: 10px; }
        .av2 .cast-me__body .av2-field__label { color: inherit; }
        .av2 .cast-me__actions { display: flex; flex-wrap: wrap; gap: 10px; }
        .av2 .cast-me__actions > .av2-btn { flex: 1 1 10rem; width: auto; }

        /* a character: portrait, name, role, register chip; then closeness and recalls */
        .av2 .cast-card { display: flex; flex-direction: column; gap: 12px; }
        .av2 .cast-card__top { display: flex; align-items: center; gap: 14px; min-width: 0; }
        .av2 .cast-card__id { flex: 1 1 auto; min-width: 0; }
        .av2 .cast-card__role { margin: 3px 0 0; }
        .av2 .cast-card__register { flex: none; }
        .av2 .cast-closeness { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .av2 .cast-closeness__pips { display: inline-flex; gap: 4px; }
        .av2 .cast-closeness__pips i { width: 12px; height: 12px; border-radius: 999px; background: var(--av2-line); }
        .av2 .cast-closeness__pips i[data-on='true'] { background: var(--av2-blue); }
        .av2 .cast-ledger { display: flex; flex-direction: column; gap: 6px; }
        .av2 .cast-ledger__callbacks { display: flex; flex-wrap: wrap; gap: 6px; }
        .av2 .cast-ledger__last { margin: 0; }
        .av2 .cast-episodes { display: flex; flex-direction: column; gap: 6px; padding-top: 10px; border-top: 1px solid var(--av2-line); }
        .av2 .cast-episodes a {
          display: flex; align-items: center; gap: 10px; min-height: 44px; min-width: 0;
          color: var(--av2-ink); text-decoration: none;
        }
        .av2 .cast-episodes a .meta { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; }
        .av2 .cast-episodes a .t {
          font-family: var(--av2-serif); font-style: italic; font-weight: 600; font-size: var(--av2-t-body);
          line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .av2 .cast-episodes a svg { flex: none; color: var(--av2-muted); }
        @media (max-width: 360px) {
          .av2 .cast-me__actions > .av2-btn { flex-basis: 100%; }
        }
      `}</style>
    </>
  );
}

/* One cast member. `model_sheet_url` is the character's portrait; the accent
   colour is the world bible's, and closeness is the server's 0–5 count. */
function CastCard({ member }: { member: SerialCastMember }) {
  const closeness = Math.max(0, Math.min(5, Number(member.relationship.closeness || 0)));
  const register = member.relationship.register === 'tu' ? 'tu' : 'vous';
  const switchEp = member.relationship.register_switch_episode != null
    ? Number(member.relationship.register_switch_episode) + 1
    : null;
  const callbacks = (member.relationship.callbacks || []).slice(0, 4);
  const episodes = (member.episodes || []).slice(0, 4);

  return (
    <Surface
      as="article"
      className="cast-card"
      aria-label={member.name}
      style={member.accent_colour ? ({ ['--cast-accent' as string]: member.accent_colour } as React.CSSProperties) : undefined}
    >
      <div className="cast-card__top">
        <span className="cast-portrait" aria-hidden="true">
          {member.model_sheet_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={member.model_sheet_url} alt="" />
          ) : (
            initial(member.name)
          )}
        </span>
        <div className="cast-card__id">
          <p className="av2-headline av2-headline--rule">{member.name}</p>
          {member.role && <p className="av2-label cast-card__role">{member.role}</p>}
        </div>
        <Chip tone={register === 'tu' ? 'reward' : 'quiet'} className="cast-card__register">
          <span lang="fr">{register}</span> · {register === 'tu' ? 'accordé' : 'de rigueur'}
        </Chip>
      </div>

      <div className="cast-closeness">
        <span className="av2-label">Proximité</span>
        <span className="cast-closeness__pips" role="img" aria-label={`Proximité ${closeness} sur 5`}>
          {[0, 1, 2, 3, 4].map((index) => (
            <i key={index} data-on={index < closeness ? 'true' : undefined} />
          ))}
        </span>
        <span className="av2-label" style={{ fontWeight: 400 }}>
          {switchEp != null ? `Tutoiement — ép. ${switchEp}` : 'Pas encore de tutoiement'}
        </span>
      </div>

      <div className="cast-ledger">
        <span className="av2-label">Rappels</span>
        {callbacks.length ? (
          <div className="cast-ledger__callbacks">
            {callbacks.map((callback, index) => (
              <Chip key={index} icon={<ShapeToken kind="story" size="sm" />}>
                <span lang="fr">{callback}</span>
              </Chip>
            ))}
          </div>
        ) : (
          <p className="av2-body">Aucun rappel encore — l’histoire commence.</p>
        )}
        {member.relationship.last_summary ? (
          <p className="av2-body cast-ledger__last">
            <strong>Dernier échange —</strong> {member.relationship.last_summary}
          </p>
        ) : (
          <p className="av2-body cast-ledger__last">Vous ne vous êtes pas encore parlé.</p>
        )}
      </div>

      {episodes.length > 0 && (
        <div className="cast-episodes">
          {episodes.map((episode) => (
            <Link key={`${member.id}-${episode.episode_index}`} href={episode.href}>
              <span className="meta">
                <span className="av2-label">{episode.episode_label}</span>
                <span className="t">{episode.title}</span>
              </span>
              <ArrowRightIcon size={16} />
            </Link>
          ))}
        </div>
      )}
    </Surface>
  );
}
