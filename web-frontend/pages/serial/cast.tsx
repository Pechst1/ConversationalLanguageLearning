import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import apiService, { SerialCastMember } from '@/services/api';

const AVATAR_REFERENCE_ASSET = 'assets/serial/characters/user/model-sheet.png';

export default function SerialCastPage() {
  const [cast, setCast] = useState<SerialCastMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [avatarDescription, setAvatarDescription] = useState('');
  const [avatarMode, setAvatarMode] = useState<'avatar' | 'pov'>('pov');
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [avatarMessage, setAvatarMessage] = useState('');

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
      setAvatarMessage(payload.protagonist_mode === 'avatar' ? 'Avatar saved for future panels.' : 'POV mode saved.');
    } catch (error) {
      console.error(error);
      setAvatarMessage('Could not save the character setup.');
    } finally {
      setAvatarSaving(false);
    }
  }

  return (
    <>
      <CastStyles />
      <main className="cast-page">
        <EditorialMasthead active="studio" />
        <section className="cast-head">
          <Link href="/serial"><ArrowLeft size={15} /> Season 1</Link>
          <div>
            <span>Le Feuilleton</span>
            <h1>Cast</h1>
          </div>
        </section>
        {loading ? (
          <div className="cast-loading"><Loader2 className="spin" /> Loading cast</div>
        ) : (
          <>
            <section className="avatar-builder" aria-label="Your serial character">
              <div>
                <span>Your character</span>
                <strong>{avatarMode === 'avatar' ? 'Visible avatar' : 'POV mode'}</strong>
              </div>
              <label>
                <span>Descriptor</span>
                <input value={avatarDescription} onChange={(event) => setAvatarDescription(event.target.value)} placeholder="short visual cue" />
              </label>
              <div className="avatar-reference-summary" aria-label="Avatar visual reference">
                <span>Reference</span>
                <strong>Private model sheet</strong>
                <small>Used for visual consistency in generated panels.</small>
              </div>
              <div className="avatar-actions">
                <button type="button" disabled={avatarSaving} onClick={() => void saveAvatar('avatar')}>
                  {avatarSaving ? <Loader2 className="spin" size={14} /> : null} Save avatar
                </button>
                <button type="button" disabled={avatarSaving} onClick={() => void saveAvatar('pov')}>
                  Use POV
                </button>
              </div>
              {avatarMessage && <p>{avatarMessage}</p>}
            </section>
            <section className="cast-grid" aria-label="Serial cast">
              {cast.map((member) => (
                <article className="cast-card" key={member.id} style={{ '--accent': member.accent_colour || '#1d3a8a' } as CSSProperties}>
                  <div className="cast-image">
                    {member.model_sheet_url && <Image src={member.model_sheet_url} alt="" fill sizes="(max-width: 720px) 100vw, 280px" />}
                  </div>
                  <div className="cast-copy">
                    <div className="cast-row">
                      <span>{member.relationship.register === 'tu' ? 'tu earned' : 'vous'}</span>
                      <strong>{member.name}</strong>
                    </div>
                    <p>{member.role}</p>
                    <div className="closeness" aria-label={`Closeness ${member.relationship.closeness} of 5`}>
                      {Array.from({ length: 5 }).map((_, index) => (
                        <i key={index} className={index < member.relationship.closeness ? 'on' : ''} />
                      ))}
                    </div>
                    {member.relationship.register_switch_episode != null && (
                      <div className="cast-event">
                        Tu switch filed in Episode {Number(member.relationship.register_switch_episode) + 1}
                      </div>
                    )}
                    {(member.relationship.callbacks || []).length > 0 && (
                      <div className="callback-row" aria-label={`${member.name} callbacks`}>
                        {(member.relationship.callbacks || []).slice(0, 4).map((callback) => (
                          <span key={callback}>{callback}</span>
                        ))}
                      </div>
                    )}
                    {member.relationship.last_summary && <em>{member.relationship.last_summary}</em>}
                    {(member.episodes || []).length > 0 && (
                      <div className="episode-links" aria-label={`${member.name} episode appearances`}>
                        {(member.episodes || []).slice(0, 4).map((episode) => (
                          <Link key={`${member.id}-${episode.episode_index}`} href={episode.href}>
                            <span>{episode.episode_label}</span>
                            <strong>{episode.title}</strong>
                            <ArrowRight size={13} />
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </section>
          </>
        )}
      </main>
    </>
  );
}

function CastStyles() {
  return (
    <style jsx global>{`
      .cast-page {
        min-height: 100vh;
        background: #f4efe3;
        color: #14110d;
        padding: 0 18px 48px;
      }
      .cast-head {
        display: flex;
        justify-content: space-between;
        align-items: end;
        max-width: 1040px;
        margin: 28px auto 22px;
        border-bottom: 3px solid #14110d;
        padding-bottom: 18px;
      }
      .cast-head a {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: 2px solid #14110d;
        background: #fff9ec;
        color: #14110d;
        padding: 10px 12px;
        font-weight: 900;
        text-decoration: none;
      }
      .cast-head span {
        display: block;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
        text-align: right;
      }
      .cast-head h1 {
        margin: 6px 0 0;
        font-family: Georgia, serif;
        font-size: 46px;
        line-height: .95;
      }
      .avatar-builder {
        display: grid;
        grid-template-columns: minmax(160px, .7fr) minmax(180px, 1fr) minmax(180px, 1fr) auto;
        gap: 12px;
        align-items: end;
        max-width: 1040px;
        margin: 0 auto 18px;
        border: 2px solid #14110d;
        background: #fff9ec;
        box-shadow: 4px 4px 0 #14110d;
        padding: 13px;
      }
      .avatar-builder > div:first-child,
      .avatar-builder label,
      .avatar-reference-summary {
        display: grid;
        gap: 5px;
        min-width: 0;
      }
      .avatar-builder span {
        color: #1d3a8a;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .avatar-builder strong {
        font-family: Georgia, serif;
        font-size: 22px;
        line-height: 1;
      }
      .avatar-builder input {
        width: 100%;
        min-height: 40px;
        border: 1.5px solid #14110d;
        background: #f4efe3;
        padding: 0 10px;
        font: inherit;
      }
      .avatar-reference-summary small {
        color: #8b8578;
        font-size: 12px;
        font-weight: 800;
        line-height: 1.25;
      }
      .avatar-actions {
        display: flex;
        gap: 8px;
      }
      .avatar-actions button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        min-height: 40px;
        border: 1.5px solid #14110d;
        background: #14110d;
        color: #fff9ec;
        padding: 0 12px;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .08em;
        text-transform: uppercase;
        white-space: nowrap;
      }
      .avatar-actions button + button {
        background: #f4efe3;
        color: #14110d;
      }
      .avatar-builder > p {
        grid-column: 1 / -1;
        margin: 0;
        color: #554d43;
        font-weight: 800;
      }
      .cast-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 18px;
        max-width: 1040px;
        margin: 0 auto;
      }
      .cast-card {
        border: 2px solid #14110d;
        background: #fff9ec;
        box-shadow: 4px 4px 0 #14110d;
        overflow: hidden;
      }
      .cast-image {
        position: relative;
        aspect-ratio: 4 / 3;
        border-bottom: 6px solid var(--accent);
        background: #e8ddc8;
      }
      .cast-image img {
        object-fit: cover;
      }
      .cast-copy {
        display: grid;
        gap: 10px;
        padding: 14px;
      }
      .cast-row {
        display: flex;
        align-items: start;
        justify-content: space-between;
        gap: 12px;
      }
      .cast-row span {
        border: 1px solid var(--accent);
        color: var(--accent);
        padding: 4px 6px;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
        white-space: nowrap;
      }
      .cast-row strong {
        font-family: Georgia, serif;
        font-size: 24px;
        line-height: 1;
      }
      .cast-copy p,
      .cast-copy em {
        margin: 0;
        color: #554d43;
        line-height: 1.4;
      }
      .cast-copy em {
        border-left: 4px solid var(--accent);
        padding-left: 10px;
        font-style: normal;
      }
      .cast-event {
        border: 1px solid var(--accent);
        color: var(--accent);
        padding: 7px 8px;
        font-size: 11px;
        font-weight: 900;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .callback-row {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .callback-row span {
        background: #f7c516;
        border: 1px solid #14110d;
        padding: 4px 6px;
        font-size: 11px;
        font-weight: 900;
      }
      .episode-links {
        display: grid;
        gap: 6px;
        border-top: 1px solid #cfc3ad;
        padding-top: 10px;
      }
      .episode-links a {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 2px 8px;
        align-items: center;
        color: #14110d;
        text-decoration: none;
      }
      .episode-links a span {
        color: #807767;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: .1em;
        text-transform: uppercase;
      }
      .episode-links a strong {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .episode-links a svg {
        grid-row: 1 / span 2;
        grid-column: 2;
      }
      .closeness {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 5px;
      }
      .closeness i {
        height: 7px;
        border: 1px solid #14110d;
        background: #e8ddc8;
      }
      .closeness i.on {
        background: var(--accent);
      }
      .cast-loading {
        max-width: 1040px;
        margin: 0 auto;
        border: 2px solid #14110d;
        background: #fff9ec;
        padding: 18px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 900;
      }
      .spin { animation: spin 1s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      @media (max-width: 900px) {
        .avatar-builder { grid-template-columns: 1fr 1fr; }
        .avatar-actions { align-self: stretch; }
        .avatar-actions button { flex: 1; }
        .cast-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 640px) {
        .cast-head {
          align-items: start;
          flex-direction: column;
        }
        .cast-head span {
          text-align: left;
        }
        .avatar-builder { grid-template-columns: 1fr; }
        .avatar-actions { display: grid; grid-template-columns: 1fr 1fr; }
        .cast-grid { grid-template-columns: 1fr; }
      }
    `}</style>
  );
}
