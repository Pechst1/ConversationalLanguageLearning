import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowLeft, Loader2 } from 'lucide-react';

import EditorialMasthead from '@/components/layout/EditorialMasthead';
import apiService, { SerialCastMember } from '@/services/api';

export default function SerialCastPage() {
  const [cast, setCast] = useState<SerialCastMember[]>([]);
  const [loading, setLoading] = useState(true);

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
                  {member.relationship.last_summary && <em>{member.relationship.last_summary}</em>}
                </div>
              </article>
            ))}
          </section>
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
        .cast-grid { grid-template-columns: 1fr; }
      }
    `}</style>
  );
}
