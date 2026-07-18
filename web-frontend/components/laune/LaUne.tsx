/* Atelier — LA UNE · the home screen as the front page of today's edition.
   1:1 port of the design package (laune-parts.jsx / laune.css, "Atelier La
   Une" canvas). Every component maps onto real API fields; the migration
   note ("TodayView → La Une") lists what each piece replaces in
   pages/atelier.tsx. Session view, routes and the bottom tab bar are
   untouched. */

import Link from 'next/link';
import React from 'react';

/* ---------- tiny icons ---------- */
export function IcoGear() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1" />
    </svg>
  );
}
export function IcoArrow() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  );
}
export function IcoCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
      <path d="M4.5 12.5l5 5 10-11" />
    </svg>
  );
}

/* ---------- rubber stamp ---------- */
export function LuStamp({
  word = 'FAIT',
  tone = 'red',
  tilt = -7,
  sm = false,
  date = null,
  style,
}: {
  word?: string;
  tone?: 'red' | 'ink' | 'blue';
  tilt?: number;
  sm?: boolean;
  date?: string | null;
  style?: React.CSSProperties;
}) {
  return (
    <span
      className={'lu-stamp ' + tone + (sm ? ' sm' : '')}
      style={{ '--tilt': tilt + 'deg', ...style } as React.CSSProperties}
      aria-hidden="true"
    >
      {word}
      {date && <span className="d">{date}</span>}
    </span>
  );
}

/* ---------- masthead + ears ---------- */
/* streakLine honesty: streak 0 → "Première édition" (red), never a fake count. */
export function LuMasthead({
  name = 'L’Atelier',
  date,
  edition,
  streak = 0,
  boucle = false,
  boucleDate = '',
}: {
  name?: string;
  date: string;
  edition: string;
  streak?: number;
  boucle?: boolean;
  boucleDate?: string;
}) {
  const long = name.length > 12;
  return (
    <header className="lu-mast-wrap">
      <div className="lu-ears">
        <span className="ear-badge">{edition}</span>
        <Link className="ear-gear" href="/settings" aria-label="Settings"><IcoGear /></Link>
      </div>
      <div className="lu-masthead">
        {boucle && (
          <div className="lu-boucle">
            <span className="box"><b>Bouclé</b><span>{boucleDate}</span></span>
          </div>
        )}
        <h1 className={'name' + (long ? ' long' : '')}>{name}</h1>
        <div className="folio">
          <b>{date}</b>
          <span className="dot" />
          {streak > 0
            ? <span>{streak}<sup>e</sup> jour de suite</span>
            : <span className="first">Première édition</span>}
        </div>
      </div>
    </header>
  );
}

/* ---------- lead story · Le Feuilleton / La Mission ---------- */
/* artMode: 'art' | 'press' (generating) | 'late' (delayed) | 'none' (no
   illustration for this beat — e.g. a letter mission; text leads).
   headline: hook.teaser / previously; ep 1 → honest first-scene copy. */
export function LuLead({
  ep = 1,
  mission = false,
  artMode = 'none',
  artUrl = null,
  headline,
  byline = 'Monsieur Marchand',
  done = false,
  onOpen,
}: {
  ep?: number;
  mission?: boolean;
  artMode?: 'art' | 'press' | 'late' | 'none';
  artUrl?: string | null;
  headline: string;
  byline?: string;
  done?: boolean;
  onOpen?: (() => void) | null;
}) {
  const kicker = mission ? `Courrier attendu · Épisode ${ep}` : `Le Feuilleton · Épisode ${ep}`;
  const showFrame = artMode === 'art' || artMode === 'press';
  const body = (
    <React.Fragment>
      <div className={'lu-kicker' + (mission ? ' blue' : '')}>{kicker}<span className="tail" /></div>
      {showFrame && (
        <div className="lu-art-frame colorable">
          <div className="ratio">
            {artMode === 'art' && artUrl && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img className="lu-art-img" src={artUrl} alt={'Illustration — épisode ' + ep} />
            )}
            {artMode === 'press' && (
              <div className="lu-art-press">
                <div className="plate">
                  <b>Sous presses</b>
                  <span>L’illustration de l’épisode {ep} est en cours d’impression.</span>
                  <div className="rollers"><i /><i /><i /></div>
                </div>
              </div>
            )}
          </div>
          <div className="credit">
            <span>Illustration · Le Feuilleton</span>
            <span>Éd. Nº {ep}</span>
          </div>
        </div>
      )}
      <h2 className="lu-head lg">{headline}</h2>
      {artMode === 'late' && (
        <div className="lu-art-late">
          <b>Illustration retardée</b>
          L’image de cet épisode paraîtra dans une édition ultérieure. Le texte, lui, n’attend pas.
        </div>
      )}
      <div className="lu-byline">
        <span className="chip">{(byline.trim()[0] || 'M').toUpperCase()}</span>
        par <em>{byline}</em>
      </div>
    </React.Fragment>
  );
  return (
    <article className={'lu-art-sec lu-lead' + (done ? ' done' : ' undone')}>
      {done && <LuStamp word={mission ? 'Envoyé' : 'Lu'} tilt={-8} />}
      {onOpen ? (
        <button
          type="button"
          className="lu-tap"
          onClick={onOpen}
          aria-label={(mission ? 'Répondre à la mission — ' : 'Lire l’épisode — ') + headline}
        >
          {body}
        </button>
      ) : (
        <div className="lu-tap static">{body}</div>
      )}
    </article>
  );
}

/* ---------- la séance du jour ---------- */
/* concepts: [{ t, cefr, role: 'new'|'fragile'|'contrast' }]
   status: 'fresh' | 'resume' | 'done' — resume shows SOUS PRESSE + progress */
export type LuSeanceConcept = { t: string; cefr: string; role: 'new' | 'fragile' | 'contrast' };
const LU_ROLES: Record<LuSeanceConcept['role'], string> = {
  new: 'Nouveau',
  fragile: 'Fragile',
  contrast: 'Contraste',
};
export function LuSeance({
  concepts = [],
  mins = 8,
  drills = 22,
  status = 'fresh',
  progress = null,
  disabled = false,
  onCta,
}: {
  concepts?: LuSeanceConcept[];
  mins?: number;
  drills?: number;
  status?: 'fresh' | 'resume' | 'done';
  progress?: [number, number] | null;
  disabled?: boolean;
  onCta?: () => void;
}) {
  const done = status === 'done';
  return (
    <article className={'lu-art-sec lu-seance' + (done ? ' done' : ' undone')}>
      {done && <LuStamp word="Fait" tilt={6} />}
      <div className="lu-kicker">La Séance du jour<span className="tail" /></div>
      <h2 className="lu-head">{concepts.length === 1 ? 'Une règle, bien posée' : 'Trois règles, une page'}</h2>
      <div className="lu-concepts">
        {concepts.map((c) => (
          <div className="lu-concept" key={c.t}>
            <span className="t">{c.t}</span>
            <span className="colorable">
              <span className={'lu-tag ' + c.role}><i />{LU_ROLES[c.role]} <span className="lv">{c.cefr}</span></span>
            </span>
          </div>
        ))}
      </div>
      {done ? (
        <div className="lu-record"><IcoCheck /> Séance bouclée · {drills} exercices</div>
      ) : (
        <React.Fragment>
          <div className="meta-line">
            {status === 'resume' && <span className="sous">Sous presse</span>}
            <span>~{mins} min · {drills} exercices</span>
            {status === 'resume' && progress && <span>· {progress[0]}/{progress[1]}</span>}
          </div>
          {status === 'resume' && progress && (
            <div className="lu-progress"><i style={{ width: (100 * progress[0] / Math.max(1, progress[1])) + '%' }} /></div>
          )}
          <button className="lu-cta" type="button" onClick={onCta} disabled={disabled} aria-busy={disabled || undefined}>
            {status === 'resume' ? 'Reprendre la séance' : 'Commencer la séance'} <IcoArrow />
          </button>
        </React.Fragment>
      )}
    </article>
  );
}

/* ---------- secondary articles ---------- */
/* Le Lexique — due count is the story; due=0 renders the brief instead. */
export function LuLexique({
  due = 0,
  briefText = 'Rien à revoir — la mémoire tient.',
  href = '/vocabulary/review',
}: {
  due?: number;
  briefText?: string;
  href?: string;
}) {
  if (due === 0) {
    return (
      <div className="lu-brief">
        <span className="k">Le Lexique</span><span className="sep" />
        <em>{briefText}</em>
      </div>
    );
  }
  return (
    <article className="lu-art-sec undone">
      <Link className="lu-tap" href={href} aria-label={'Réviser ' + due + ' mots'}>
        <div className="lu-kicker blue">Le Lexique<span className="tail" /></div>
        <div className="count colorable" style={{ color: 'var(--blue)' }}>{due}</div>
        <h3 className="lu-head">mots à revoir</h3>
        <p className="lu-deck">La mémoire s’use si l’on ne s’en sert.</p>
      </Link>
    </article>
  );
}

/* Errata — the repair queue, printed exactly like a newspaper's errata box. */
export function LuErrata({
  due = 0,
  done = false,
  briefText = 'Aucun erratum — l’édition d’hier était impeccable.',
  onOpen,
}: {
  due?: number;
  done?: boolean;
  briefText?: string;
  onOpen?: () => void;
}) {
  if (due === 0) {
    return (
      <div className="lu-brief">
        <span className="k">Errata</span><span className="sep" />
        <em>{briefText}</em>
      </div>
    );
  }
  return (
    <article className={'lu-art-sec' + (done ? ' done' : ' undone')}>
      <button className="lu-tap" type="button" onClick={onOpen} aria-label={due + ' corrections à apporter'}>
        <div className="lu-kicker">Errata<span className="tail" /></div>
        <div className="count colorable" style={{ color: 'var(--red)' }}>{due}</div>
        <h3 className="lu-head">correction{due > 1 ? 's' : ''} à apporter</h3>
        <p className="lu-deck">La rédaction corrige ses fautes d’hier.</p>
      </button>
    </article>
  );
}

/* La Bibliothèque — feature-flagged book episode. Marked optional. */
export function LuBiblio({
  title = 'Le Petit Nicolas',
  chapter = 1,
  href = '/notebook?mode=library',
}: {
  title?: string;
  chapter?: number;
  href?: string;
}) {
  return (
    <article className="lu-art-sec undone">
      <Link className="lu-tap" href={href} aria-label={'Lire ' + title + ', chapitre ' + chapter}>
        <div className="lu-kicker mut">La Bibliothèque<span className="tail" /></div>
        <h3 className="lu-head" style={{ fontSize: 20 }}>{title}</h3>
        <p className="lu-deck">Chapitre {chapter} · lecture du soir, sans exercice.</p>
      </Link>
    </article>
  );
}

/* Citation du jour — pure ornament, no tap. */
export function LuCitation({ text, source, detail }: { text: string; source: string; detail?: string }) {
  return (
    <aside className="lu-citation">
      <p className="q">« {text} »</p>
      <p className="src">{source}{detail ? ' · ' + detail : ''}</p>
    </aside>
  );
}

/* La phrase d'hier — printed only when the preceding edition filed one. */
export function LuPhraseDuJour({
  text,
  byline,
  paru = true,
}: {
  text: string;
  byline: string;
  paru?: boolean;
}) {
  return (
    <aside className="lu-phrase-du-jour" aria-label="La phrase d’hier">
      <div className="head">
        <span>La phrase d’hier</span>
        {paru && <span className="paru">Paru</span>}
      </div>
      <blockquote>« {text} »</blockquote>
      <p>par <em>{byline}</em></p>
    </aside>
  );
}

/* ---------- le cours du français (CEFR ticker) ---------- */
export function LuCours({
  from = 'A1.1',
  to = 'A1.2',
  days = null,
  words = [0, 300],
  grammar = [0, 20],
  delta = null,
  forecast = true,
}: {
  from?: string;
  to?: string;
  days?: number | null;
  words?: [number, number];
  grammar?: [number, number];
  delta?: string | null;
  forecast?: boolean;
}) {
  return (
    <section className="lu-cours">
      <div className="row1"><span>Le cours du français</span><span>CECR</span></div>
      {forecast ? (
        <div className="quote">
          <b>{from} → {to}</b>
          <span>~{days} jours à ce rythme</span>
        </div>
      ) : (
        <div className="quote">
          <b>{from}</b>
          <span>Prévisions après 7 jours actifs.</span>
        </div>
      )}
      <div className="gauges">
        <div className="g">
          <span className="lab">Mots</span>
          <span className="bar"><i style={{ width: Math.min(100, 100 * words[0] / Math.max(1, words[1])) + '%' }} /></span>
          <span className="num">{words[0]} / {words[1]}</span>
        </div>
        <div className="g">
          <span className="lab">Structures</span>
          <span className="bar"><i style={{ width: Math.min(100, 100 * grammar[0] / Math.max(1, grammar[1])) + '%' }} /></span>
          <span className="num">{grammar[0]} / {grammar[1]}</span>
        </div>
      </div>
      {delta && <div className="delta">Aujourd’hui : {delta}</div>}
    </section>
  );
}

/* ---------- demain dans votre édition ---------- */
export function LuDemain({
  focus,
  focusHref = '/notebook',
  ep = null,
  epTease = null,
  words = null,
  grand = false,
}: {
  focus: string;
  focusHref?: string;
  ep?: number | null;
  epTease?: string | null;
  words?: number | null;
  grand?: boolean;
}) {
  return (
    <section className={'lu-demain' + (grand ? ' grand' : '')}>
      <div className="k">Demain dans votre édition</div>
      {grand && epTease && <p className="tease">Épisode {ep} : {epTease}</p>}
      <ul>
        <li><span className="h">Grammaire</span><span><Link href={focusHref}><em>{focus}</em></Link></span></li>
        {!grand && ep && <li><span className="h">Feuilleton</span><span>Épisode {ep}{epTease ? ' : ' + epTease : ''}</span></li>}
        {words != null && <li><span className="h">Lexique</span><span>{words} mots nouveaux au marbre</span></li>}
      </ul>
    </section>
  );
}

/* ---------- press notice (load errors) ---------- */
export function LuNotice({
  tone = 'red',
  label,
  message,
  retry = true,
  onRetry,
}: {
  tone?: 'red' | 'yellow' | 'blue';
  label: string;
  message: string;
  retry?: boolean;
  onRetry?: () => void;
}) {
  return (
    <div className="lu-notice" role="alert">
      <span className={'sq ' + tone} />
      <span className="body"><b>{label}</b><p>{message}</p></span>
      {retry && <button className="retry" type="button" onClick={onRetry}>Retry</button>}
    </div>
  );
}

/* ---------- skeleton: the page coming off the press ---------- */
export function LuSkeleton() {
  return (
    <div className="lu-skel" aria-hidden="true">
      <div className="lu-art-sec">
        <div className="ln k" />
        <div className="blockart" />
        <div className="ln t" />
        <div className="ln t" style={{ width: '72%' }} />
        <div className="ln" style={{ width: '38%' }} />
      </div>
      <div className="lu-art-sec">
        <div className="ln k" />
        <div className="ln t" style={{ width: '84%' }} />
        <div className="ln" />
        <div className="ln" />
        <div className="ln" style={{ width: '52%' }} />
        <div className="ln t" style={{ height: 44, marginTop: 14, background: 'var(--news-wash)', border: '1px solid var(--paper-3)' }} />
      </div>
      <div className="lu-duo" style={{ borderBottom: 0 }}>
        <div className="lu-art-sec"><div className="ln k" style={{ width: '60%' }} /><div className="ln t" style={{ width: '46%' }} /><div className="ln" /></div>
        <div className="lu-art-sec"><div className="ln k" style={{ width: '60%' }} /><div className="ln t" style={{ width: '46%' }} /><div className="ln" /></div>
      </div>
    </div>
  );
}

/* ============================================================
   Styles — laune.css ported verbatim; only the fixed 390px
   artboard width becomes the app's phone-shell sizing, and the
   ".desk" board variant becomes a ≥1100px media query.
   ============================================================ */
export function LaUneStyles() {
  return (
    <style jsx global>{`
      .lu {
        --paper: var(--app-paper);
        --paper-2: var(--app-paper-2);
        --paper-3: var(--app-paper-3);
        --sheet: var(--app-sheet);
        --ink: var(--app-ink);
        --ink-2: var(--app-ink-2);
        --ink-3: var(--app-ink-3);
        --blue: var(--app-blue);
        --red: var(--app-red);
        --yellow: var(--app-yellow);
        --serif: var(--app-serif);
        --grotesk: 'Inter', 'Helvetica Neue', Arial, sans-serif;
        --news-ink: #5d574a;
        --news-wash: #ece5d5;
        position: relative;
        width: min(var(--app-viewport-width), var(--phone-shell-max));
        min-height: var(--app-viewport-height);
        background: var(--sheet);
        color: var(--ink);
        font-family: var(--grotesk);
        -webkit-font-smoothing: antialiased;
        display: flex;
        flex-direction: column;
        padding-top: var(--phone-safe-top);
        background-image:
          radial-gradient(circle at 18% 22%, rgba(20, 17, 13, 0.03) 0, transparent 0.7px),
          radial-gradient(circle at 71% 56%, rgba(20, 17, 13, 0.03) 0, transparent 0.7px);
        background-size: 7px 7px, 11px 11px;
      }
      .lu * { box-sizing: border-box; }
      .lu a, .lu button { font: inherit; color: inherit; text-align: inherit; }
      .lu button { border: 0; background: transparent; padding: 0; cursor: pointer; }

      .lu-page { flex: 1 1 auto; padding: 0 18px calc(18px + 12px); }

      /* ---- ears + masthead ---- */
      .lu-ears {
        display: flex; align-items: center; justify-content: space-between;
        padding: 12px 0 0; min-height: 44px;
      }
      .lu-ears .ear-badge {
        border: 1px solid var(--ink); background: var(--paper);
        padding: 5px 8px 4px; font-size: 9px; font-weight: 900;
        letter-spacing: .14em; text-transform: uppercase; white-space: nowrap;
      }
      .lu-ears .ear-gear {
        width: 44px; height: 44px; margin: -6px -8px 0 0;
        display: grid; place-items: center; color: var(--ink-2);
        text-decoration: none;
      }
      .lu-ears .ear-gear svg { width: 18px; height: 18px; }

      .lu-masthead { position: relative; text-align: center; padding: 2px 0 0; }
      .lu-masthead .name {
        font-family: var(--serif); font-style: italic; font-weight: 600;
        font-size: 44px; line-height: .95; letter-spacing: -.01em; margin: 0;
      }
      .lu-masthead .name.long { font-size: 31px; }
      .lu-masthead .folio {
        margin-top: 9px; padding: 6px 0;
        border-top: 1px solid var(--ink); border-bottom: 3px double var(--ink);
        display: flex; align-items: center; justify-content: center; gap: 4px 8px;
        font-size: 9px; font-weight: 800; letter-spacing: .08em;
        text-transform: uppercase; color: var(--ink-2); flex-wrap: wrap;
      }
      .lu-masthead .folio b, .lu-masthead .folio span { white-space: nowrap; }
      .lu-masthead .folio b { color: var(--ink); font-weight: 900; }
      .lu-masthead .folio .dot { width: 3px; height: 3px; background: var(--ink-3); border-radius: 50%; }
      .lu-masthead .folio .first { color: var(--red); font-weight: 900; }

      /* BOUCLÉ — the put-to-bed stamp across the masthead */
      .lu-boucle {
        position: absolute; inset: -6px -10px auto; top: 50%;
        transform: translateY(-58%) rotate(-6deg);
        display: grid; place-items: center; pointer-events: none; z-index: 3;
        mix-blend-mode: multiply;
      }
      .lu-boucle .box {
        border: 3px solid var(--red); color: var(--red);
        padding: 7px 18px 6px; background: transparent;
        box-shadow: inset 0 0 0 1.5px var(--sheet), inset 0 0 0 3px var(--red);
        text-align: center; opacity: .88;
      }
      .lu-boucle .box b { display: block; font-size: 26px; font-weight: 900; letter-spacing: .3em; text-indent: .3em; text-transform: uppercase; }
      .lu-boucle .box span { display: block; margin-top: 2px; font-size: 8.5px; font-weight: 900; letter-spacing: .2em; text-transform: uppercase; }

      /* ---- generic article ---- */
      .lu-art-sec { position: relative; padding: 16px 0 18px; border-bottom: 1px solid var(--ink); }
      .lu-art-sec.no-rule { border-bottom: 0; }
      .lu-kicker {
        display: flex; align-items: center; gap: 8px; white-space: nowrap;
        font-size: 9.5px; font-weight: 900; letter-spacing: .16em;
        text-transform: uppercase; color: var(--red);
      }
      .lu-kicker.blue { color: var(--blue); }
      .lu-kicker.mut { color: var(--ink-3); }
      .lu-kicker .tail { flex: 1 1 auto; min-width: 10px; height: 1px; background: var(--paper-3); }
      .lu-head {
        margin: 7px 0 0; font-family: var(--serif); font-style: italic;
        font-weight: 600; font-size: 25px; line-height: 1.04; color: var(--ink);
        text-wrap: pretty;
      }
      .lu-head.lg { font-size: 28px; }
      .lu-deck { margin: 7px 0 0; font-size: 12.5px; line-height: 1.42; color: var(--ink-2); }
      .lu-byline {
        margin-top: 9px; display: flex; align-items: center; gap: 7px;
        font-size: 10.5px; font-weight: 700; color: var(--ink-2);
      }
      .lu-byline .chip {
        width: 22px; height: 22px; border: 1px solid var(--ink); border-radius: 50%;
        background: var(--paper-2); display: grid; place-items: center;
        font-family: var(--serif); font-style: italic; font-weight: 700; font-size: 11px;
        flex: 0 0 auto;
      }
      .lu-byline em { font-style: italic; font-family: var(--serif); font-size: 12.5px; }

      /* whole-article tap target */
      .lu-tap { display: block; width: 100%; text-decoration: none; }
      .lu-tap:active { background: var(--paper-2); }
      .lu-tap.static:active { background: transparent; }

      /* ---- the print-in mechanic ---- */
      /* Not done = newsprint: art desaturated, accents withdrawn to gray ink. */
      .lu-art-sec .colorable { transition: filter .6s cubic-bezier(.25, .6, .2, 1); }
      .lu-art-sec.undone .colorable { filter: grayscale(1) contrast(.94) opacity(.92); }
      .lu-art-sec.undone .lu-kicker { color: var(--news-ink); }
      .lu-art-sec.undone .lu-head { color: var(--ink); }

      /* the struck stamp */
      .lu-stamp {
        position: absolute; z-index: 2; pointer-events: none;
        transform: rotate(var(--tilt, -7deg));
        mix-blend-mode: multiply; color: var(--red);
        border: 2.5px solid currentColor; padding: 4px 10px 3px;
        box-shadow: inset 0 0 0 1.5px var(--sheet), inset 0 0 0 2.5px currentColor;
        font-size: 15px; font-weight: 900; letter-spacing: .24em; text-indent: .24em;
        text-transform: uppercase; opacity: .9; background: transparent;
      }
      .lu-stamp.ink { color: var(--ink); }
      .lu-stamp.blue { color: var(--blue); }
      .lu-stamp.sm { font-size: 11px; border-width: 2px; padding: 3px 8px 2px; box-shadow: inset 0 0 0 1px var(--sheet), inset 0 0 0 2px currentColor; }
      .lu-stamp .d { display: block; font-size: 7.5px; letter-spacing: .16em; text-indent: .16em; margin-top: 1px; }
      @media (prefers-reduced-motion: no-preference) {
        .lu.motion .lu-art-sec.done .lu-stamp { animation: lu-strike .32s cubic-bezier(.18, 1.35, .3, 1) .18s both; }
        .lu.motion .lu-boucle .box { animation: lu-strike .38s cubic-bezier(.18, 1.35, .3, 1) .25s both; }
      }
      @keyframes lu-strike {
        from { opacity: 0; transform: scale(1.55) rotate(var(--tilt, -7deg)); }
        60% { opacity: .95; }
        to { opacity: .9; transform: scale(1) rotate(var(--tilt, -7deg)); }
      }
      .lu-boucle .box { --tilt: 0deg; }

      /* ---- lead story (Le Feuilleton) ---- */
      .lu-lead { padding-top: 14px; }
      .lu-lead .lu-stamp { top: 26px; right: 4px; }
      .lu-art-frame { position: relative; margin-top: 10px; border: 1px solid var(--ink); background: var(--paper-2); }
      .lu-art-frame .ratio { position: relative; width: 100%; aspect-ratio: 16 / 10; overflow: hidden; }
      .lu-art-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }
      .lu-art-frame .credit {
        display: flex; justify-content: space-between; gap: 10px;
        padding: 5px 8px; border-top: 1px solid var(--ink);
        font-size: 8px; font-weight: 800; letter-spacing: .06em;
        text-transform: uppercase; color: var(--ink-3); background: var(--sheet);
      }
      .lu-art-frame .credit span { white-space: nowrap; }

      /* presses-running (art generating) — same composition, setting plates */
      .lu-art-press {
        position: absolute; inset: 0; display: grid; place-items: center;
        background:
          repeating-linear-gradient(0deg, var(--news-wash) 0 6px, var(--paper-2) 6px 12px);
      }
      .lu-art-press .plate {
        text-align: center; background: var(--sheet); border: 1px solid var(--ink);
        padding: 10px 14px; max-width: 84%;
      }
      .lu-art-press .plate b { display: block; font-size: 9.5px; font-weight: 900; letter-spacing: .18em; text-transform: uppercase; }
      .lu-art-press .plate span { display: block; margin-top: 3px; font-size: 9px; color: var(--ink-2); letter-spacing: .04em; }
      .lu-art-press .rollers { display: flex; gap: 4px; justify-content: center; margin-top: 7px; }
      .lu-art-press .rollers i { width: 5px; height: 5px; background: var(--ink); }
      @media (prefers-reduced-motion: no-preference) {
        .lu.motion .lu-art-press .rollers i { animation: lu-roll 1.1s ease-in-out infinite; }
        .lu.motion .lu-art-press .rollers i:nth-child(2) { animation-delay: .18s; }
        .lu.motion .lu-art-press .rollers i:nth-child(3) { animation-delay: .36s; }
      }
      @keyframes lu-roll { 0%, 100% { opacity: .25; } 50% { opacity: 1; } }

      /* delayed notice — a printed apology, text leads */
      .lu-art-late {
        margin-top: 10px; border: 1px dashed var(--ink-3); background: var(--paper);
        padding: 9px 12px; font-size: 10.5px; line-height: 1.45; color: var(--ink-2);
      }
      .lu-art-late b { font-weight: 900; letter-spacing: .12em; text-transform: uppercase; font-size: 8.5px; color: var(--ink); display: block; margin-bottom: 2px; }

      /* ---- la séance (primary article) ---- */
      .lu-seance { position: relative; }
      .lu-seance .lu-stamp { top: 20px; right: 2px; }
      .lu-concepts { margin-top: 12px; display: grid; }
      .lu-concept {
        display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px;
        align-items: center; padding: 9px 0; border-top: 1px solid var(--paper-3);
      }
      .lu-concept:last-child { border-bottom: 1px solid var(--paper-3); }
      .lu-concept .t { font-family: var(--serif); font-style: italic; font-size: 17.5px; line-height: 1.1; }
      .lu-concept .colorable { display: inline-flex; }
      .lu-tag {
        display: inline-flex; align-items: center; gap: 6px;
        border: 1px solid var(--ink); background: var(--sheet);
        padding: 3px 7px 2px; font-size: 8px; font-weight: 900;
        letter-spacing: .13em; text-transform: uppercase; white-space: nowrap;
      }
      .lu-tag i { width: 8px; height: 8px; flex: 0 0 auto; }
      .lu-tag.new i { background: var(--yellow); }
      .lu-tag.fragile i { background: var(--red); }
      .lu-tag.contrast i { background: var(--blue); }
      .lu-tag .lv { color: var(--ink-3); font-weight: 800; }

      .lu-seance .meta-line {
        margin-top: 10px; font-size: 10px; font-weight: 800; letter-spacing: .12em;
        text-transform: uppercase; color: var(--ink-3);
        display: flex; align-items: center; gap: 8px;
      }
      .lu-seance .meta-line .sous {
        color: var(--red); border: 1.5px solid var(--red); padding: 2px 6px 1px;
        transform: rotate(-2deg); letter-spacing: .16em;
      }
      .lu-progress { margin-top: 8px; height: 4px; background: var(--paper-3); position: relative; }
      .lu-progress i { position: absolute; inset: 0 auto 0 0; background: var(--red); }

      /* Primary action, set as a printed press bar: solid ink on paper,
         framed by hairline keylines above and below (no toy drop-shadow),
         inverts on press. Reads as newspaper furniture, not an app button. */
      .lu .lu-cta {
        margin-top: 15px;
        display: flex; align-items: center; justify-content: center; gap: 12px;
        width: 100%; min-height: 52px; padding: 0 18px;
        background: var(--ink); color: var(--paper);
        border: 1px solid var(--ink);
        box-shadow: inset 0 0 0 3px var(--sheet), inset 0 0 0 4px var(--ink);
        font-size: 12.5px; font-weight: 700; letter-spacing: .16em; text-indent: .16em;
        text-transform: uppercase; text-decoration: none; cursor: pointer;
        transition: background .16s ease, color .16s ease;
      }
      .lu-cta:hover { background: var(--paper); color: var(--ink); }
      .lu-cta:active { background: var(--paper-2); color: var(--ink); }
      .lu-cta:disabled { opacity: .5; cursor: progress; }
      .lu-cta:disabled:hover { background: var(--ink); color: var(--paper); }
      .lu-cta svg { width: 16px; height: 16px; }
      .lu-art-sec.done .lu-cta { display: none; }

      /* the done séance folds to a settled record line */
      .lu-record {
        margin-top: 12px; display: flex; align-items: center; gap: 9px;
        font-size: 10.5px; font-weight: 800; letter-spacing: .1em;
        text-transform: uppercase; color: var(--ink-2); white-space: nowrap;
      }
      .lu-record svg { width: 14px; height: 14px; flex: 0 0 auto; }

      /* ---- secondary column grid ---- */
      .lu-duo { display: grid; grid-template-columns: 1fr 1fr; border-bottom: 1px solid var(--ink); }
      .lu-duo .lu-art-sec { border-bottom: 0; }
      .lu-duo .lu-art-sec:first-child { border-right: 1px solid var(--ink); padding-right: 14px; }
      .lu-duo .lu-art-sec:last-child { padding-left: 14px; }
      .lu-duo .lu-brief { border-bottom: 0; }
      .lu-duo .lu-head { font-size: 20px; }
      .lu-duo .count {
        font-family: var(--serif); font-style: italic; font-weight: 700;
        font-size: 34px; line-height: .9; margin: 8px 0 0;
      }
      .lu-duo .lu-stamp { top: 14px; right: 8px; }

      /* one-line brief (empty / done reductions) */
      .lu-brief {
        display: flex; align-items: center; gap: 9px; padding: 10px 0;
        border-bottom: 1px solid var(--ink);
        font-size: 11px; color: var(--ink-2);
      }
      .lu-brief .k { font-size: 8.5px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-3); flex: 0 0 auto; }
      .lu-brief .sep { width: 12px; height: 1px; background: var(--ink-3); flex: 0 0 auto; }
      .lu-brief em { font-family: var(--serif); font-style: italic; font-size: 12.5px; }

      /* ---- citation du jour ---- */
      .lu-citation { text-align: center; padding: 18px 20px; border-bottom: 1px solid var(--ink); }
      .lu-citation .q { margin: 0; font-family: var(--serif); font-style: italic; font-size: 17px; line-height: 1.3; }
      .lu-citation .src { margin: 6px 0 0; font-size: 8.5px; font-weight: 900; letter-spacing: .18em; text-transform: uppercase; color: var(--ink-3); }

      /* ---- la phrase d'hier ---- */
      .lu-phrase-du-jour {
        margin: 16px 0; padding: 14px 16px 15px;
        border: 1.5px solid var(--ink); background: var(--paper);
        box-shadow: inset 0 0 0 3px var(--sheet), inset 0 0 0 4px var(--paper-3);
      }
      .lu-phrase-du-jour .head {
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        font-size: 8.5px; font-weight: 900; letter-spacing: .17em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .lu-phrase-du-jour .paru {
        border: 1px solid var(--red); color: var(--red); padding: 2px 6px 1px;
        letter-spacing: .14em; transform: rotate(-2deg);
      }
      .lu-phrase-du-jour blockquote {
        margin: 12px 0 0; font-family: var(--serif); font-style: italic;
        font-size: 21px; line-height: 1.3; color: var(--ink);
      }
      .lu-phrase-du-jour p {
        margin: 8px 0 0; font-size: 9px; font-weight: 800; letter-spacing: .1em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .lu-phrase-du-jour p em { font-family: var(--serif); font-size: 11px; text-transform: none; color: var(--ink); }

      /* ---- le cours du français (ticker) ---- */
      .lu-cours {
        margin-top: 16px; border: 1px solid var(--ink); background: var(--paper);
        padding: 10px 12px 12px;
      }
      .lu-cours .row1 {
        display: flex; align-items: baseline; justify-content: space-between; gap: 10px;
        font-size: 9px; font-weight: 900; letter-spacing: .15em; text-transform: uppercase; color: var(--ink-3);
      }
      .lu-cours .row1 span { white-space: nowrap; }
      .lu-cours .quote { margin-top: 5px; display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; }
      .lu-cours .quote b { font-family: var(--serif); font-style: italic; font-weight: 700; font-size: 19px; white-space: nowrap; }
      .lu-cours .quote span { font-size: 10px; font-weight: 800; letter-spacing: .06em; color: var(--ink-2); }
      .lu-cours .gauges { margin-top: 9px; display: grid; gap: 6px; }
      .lu-cours .g { display: grid; grid-template-columns: 62px 1fr 52px; align-items: center; gap: 8px; }
      .lu-cours .g .lab { font-size: 8px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--ink-3); }
      .lu-cours .g .bar { height: 3px; background: var(--paper-3); position: relative; }
      .lu-cours .g .bar i { position: absolute; inset: 0 auto 0 0; background: var(--blue); }
      .lu-cours .g .num { font-size: 9px; font-weight: 800; color: var(--ink-2); text-align: right; font-variant-numeric: tabular-nums; }
      .lu-cours .delta { margin-top: 8px; padding-top: 7px; border-top: 1px solid var(--paper-3); font-size: 9.5px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--blue); }

      /* ---- demain dans votre édition ---- */
      .lu-demain { margin-top: 16px; border-top: 3px double var(--ink); padding-top: 10px; }
      .lu-demain .k { font-size: 9px; font-weight: 900; letter-spacing: .18em; text-transform: uppercase; color: var(--ink-3); text-align: center; }
      .lu-demain ul { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 5px; }
      .lu-demain li {
        display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: baseline;
        font-size: 10.5px; line-height: 1.4; color: var(--ink-2);
      }
      .lu-demain li .h { font-size: 8px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--ink); white-space: nowrap; }
      .lu-demain li em { font-family: var(--serif); font-style: italic; font-size: 12px; color: var(--ink); }
      .lu-demain a { text-decoration: none; border-bottom: 1px solid var(--paper-3); }

      /* grown closing variant (édition complète) */
      .lu-demain.grand { border: 1.5px solid var(--ink); border-top: 1.5px solid var(--ink); background: var(--paper); padding: 16px 16px 18px; margin-top: 20px; }
      .lu-demain.grand .k { color: var(--red); }
      .lu-demain.grand .tease {
        margin: 10px 0 0; text-align: center; font-family: var(--serif); font-style: italic;
        font-weight: 600; font-size: 21px; line-height: 1.12;
      }
      .lu-demain.grand ul { margin-top: 12px; border-top: 1px solid var(--paper-3); padding-top: 10px; }

      /* end-of-page colophon */
      .lu-colophon {
        margin-top: 18px; text-align: center;
        font-size: 8px; font-weight: 800; letter-spacing: .2em; text-transform: uppercase; color: var(--ink-3);
        display: flex; align-items: center; gap: 10px; justify-content: center;
      }
      .lu-colophon::before, .lu-colophon::after { content: ''; flex: 1; height: 1px; background: var(--paper-3); }

      /* ---- press notice (load errors) ---- */
      .lu-notice {
        margin: 14px 0 0; border: 1.5px solid var(--ink); background: var(--paper-2);
        display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: center;
        padding: 11px 12px;
      }
      .lu-notice .sq { width: 12px; height: 12px; background: var(--red); border: 1px solid var(--ink); }
      .lu-notice .sq.blue { background: var(--blue); }
      .lu-notice .sq.yellow { background: var(--yellow); }
      .lu-notice .body b { display: block; font-size: 9px; font-weight: 900; letter-spacing: .15em; text-transform: uppercase; }
      .lu-notice .body p { margin: 3px 0 0; font-size: 11px; line-height: 1.4; color: var(--ink-2); }
      .lu-notice .retry {
        min-height: 44px; padding: 0 14px; border: 1.5px solid var(--ink);
        background: var(--ink); color: var(--paper);
        font-size: 10px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase;
        text-align: center;
      }

      /* ---- skeleton: the page coming off the press ---- */
      .lu-skel { pointer-events: none; }
      .lu-skel .ln { background: var(--paper-3); height: 11px; margin-top: 7px; }
      .lu-skel .ln.t { height: 22px; }
      .lu-skel .ln.k { height: 8px; width: 34%; background: var(--news-wash); border: 1px solid var(--paper-3); }
      .lu-skel .blockart {
        margin-top: 10px; aspect-ratio: 16/10; border: 1px solid var(--paper-3);
        background: repeating-linear-gradient(0deg, var(--news-wash) 0 6px, var(--paper-2) 6px 12px);
      }
      @media (prefers-reduced-motion: no-preference) {
        .lu.motion .lu-skel .ln, .lu.motion .lu-skel .blockart { animation: lu-set 1.4s ease-in-out infinite; }
      }
      @keyframes lu-set { 0%, 100% { opacity: 1; } 50% { opacity: .55; } }

      /* ---- desktop variant: state 2 widened to a true front page ---- */
      .lu-grid, .lu-grid .lu-col { display: contents; }
      .lu-grid .vrule { display: none; }
      @media (min-width: 1100px) {
        .lu { width: 1024px; }
        .lu-page { padding: 0 44px 44px; }
        .lu-masthead .name { font-size: 62px; }
        .lu-grid { display: grid; grid-template-columns: 1.35fr 1px 1fr; gap: 0 26px; }
        .lu-grid .lu-col { display: block; }
        .lu-grid .vrule { display: block; background: var(--ink); }
        .lu-head.lg { font-size: 34px; }
        .lu-duo { border-bottom: 0; }
      }
    `}</style>
  );
}
