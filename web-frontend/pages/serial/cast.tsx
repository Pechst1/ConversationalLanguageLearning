import { useEffect, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import {
  FeuilletonStyles,
  FeMastheadBar,
  FeSectionNav,
  FeCastCard,
  FeMeCard,
  FeIco,
} from '@/components/feuilleton/Feuilleton';
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
      <main className="fe-stage">
        <div className="fe" aria-label="Le Feuilleton · les personnages">
          <FeMastheadBar />
          <FeSectionNav active="cast" />
          <div className="fe-body fe-scroll">
            <div className="fe-cast-head">
              <div className="kicker">Le Feuilleton · Les personnages</div>
              <h2>Les personnages</h2>
              <div className="sub">
                {loading
                  ? 'le registre du théâtre'
                  : anyTu
                    ? 'le registre du théâtre — un tutoiement accordé'
                    : 'le registre du théâtre — tout le monde vous vouvoie encore'}
              </div>
            </div>

            {loading ? (
              <div className="fe-skel" aria-hidden="true">
                <div className="l" style={{ width: '70%', height: 54, marginBottom: 12 }} />
                <div className="l" style={{ width: '70%', height: 54, marginBottom: 12 }} />
                <div className="l" style={{ width: '70%', height: 54 }} />
                <div className="press">— on appelle les rôles —</div>
              </div>
            ) : (
              <>
                <FeMeCard
                  name={avatarMode === 'avatar' ? 'Avatar visible' : 'Mode POV'}
                  ini="T"
                  kicker="Votre personnage"
                  onCustomise={() => setCustomising((value) => !value)}
                  customiseLabel={customising ? 'Fermer' : 'Personnaliser'}
                  slug={
                    customising
                      ? undefined
                      : `Private model sheet · ${avatarMode === 'avatar' ? 'style verrouillé' : 'POV — jamais dessiné'}`
                  }
                >
                  {customising && (
                    <div className="body">
                      <label className="fe-me-field">
                        <span>Descripteur visuel</span>
                        <input
                          value={avatarDescription}
                          onChange={(event) => setAvatarDescription(event.target.value)}
                          placeholder="ex. écharpe rouge, carnet"
                        />
                      </label>
                      <div className="fe-me-actions">
                        <button type="button" disabled={avatarSaving} onClick={() => void saveAvatar('avatar')}>
                          {avatarSaving ? '…' : 'Utiliser l’avatar'}
                        </button>
                        <button type="button" className="ghost" disabled={avatarSaving} onClick={() => void saveAvatar('pov')}>
                          Rester en POV
                        </button>
                      </div>
                      {avatarMessage && <p className="fe-me-msg">{avatarMessage}</p>}
                    </div>
                  )}
                </FeMeCard>

                {cast.map((member) => (
                  <FeCastCard
                    key={member.id}
                    char={member.id}
                    accent={member.accent_colour}
                    name={member.name}
                    ini={initial(member.name)}
                    role={member.role || undefined}
                    imageUrl={member.model_sheet_url}
                    register={member.relationship.register}
                    closeness={member.relationship.closeness}
                    switchEp={
                      member.relationship.register_switch_episode != null
                        ? Number(member.relationship.register_switch_episode) + 1
                        : undefined
                    }
                    callbacks={(member.relationship.callbacks || []).slice(0, 4)}
                    last={member.relationship.last_summary || undefined}
                  >
                    {(member.episodes || []).length > 0 && (
                      <div className="fe-eplinks">
                        {(member.episodes || []).slice(0, 4).map((episode) => (
                          <Link key={`${member.id}-${episode.episode_index}`} href={episode.href}>
                            <span>{episode.episode_label}</span>
                            <strong>{episode.title}</strong>
                            {FeIco.arrow}
                          </Link>
                        ))}
                      </div>
                    )}
                  </FeCastCard>
                ))}
              </>
            )}
          </div>
        </div>
      </main>
      <PhoneProductNav active="feuilleton" />
      <FeuilletonStyles />
      <style jsx global>{`
        .fe-stage { min-height: 100vh; background: var(--app-paper); color: var(--app-ink); }
        .fe-me .fe-me-field { display: grid; gap: 5px; }
        .fe-me .fe-me-field span { font-size: 8.5px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-yellow); }
        .fe-me .fe-me-field input {
          width: 100%; min-height: 40px; border: 1.5px solid var(--app-paper); background: transparent;
          color: var(--app-paper); padding: 0 10px; font: inherit;
        }
        .fe-me .fe-me-field input::placeholder { color: var(--app-paper-3); }
        .fe-me .fe-me-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .fe-me .fe-me-actions button {
          min-height: 42px; border: 1.5px solid var(--app-paper); background: var(--app-paper); color: var(--app-ink);
          font-size: 10px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; cursor: pointer;
        }
        .fe-me .fe-me-actions button.ghost { background: transparent; color: var(--app-paper); }
        .fe-me .fe-me-actions button:disabled { opacity: .6; cursor: default; }
        .fe-me .fe-me-msg { margin: 0; font-size: 11px; line-height: 1.4; color: var(--app-paper-2); }
        .fe-cast-card .fe-eplinks { border-top: 1px solid var(--app-paper-3); padding: 11px 14px 12px; display: grid; gap: 7px; }
        .fe-cast-card .fe-eplinks a {
          display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 1px 8px; align-items: center;
          color: var(--app-ink); text-decoration: none;
        }
        .fe-cast-card .fe-eplinks a span { grid-column: 1; font-size: 8px; font-weight: 900; letter-spacing: .11em; text-transform: uppercase; color: var(--app-ink-3); }
        .fe-cast-card .fe-eplinks a strong { grid-column: 1; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .fe-cast-card .fe-eplinks a svg { grid-column: 2; grid-row: 1 / span 2; width: 14px; height: 14px; color: var(--app-ink-3); }
      `}</style>
    </>
  );
}
