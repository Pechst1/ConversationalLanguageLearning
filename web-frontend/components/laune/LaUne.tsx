/* Atelier — LA UNE · the home screen as the front page of today's edition.
   1:1 port of the design package (laune-parts.jsx / laune.css, "Atelier La
   Une" canvas). Every component maps onto real API fields; the migration
   note ("TodayView → La Une") lists what each piece replaces in
   pages/atelier.tsx. Session view, routes and the bottom tab bar are
   untouched. */

import Link from 'next/link';
import React from 'react';

import { pulseAppHaptic } from '@/lib/haptics';

function LuPortraitChip({
  name,
  url,
  accentColour,
  className,
}: {
  name: string;
  url?: string | null;
  accentColour?: string | null;
  className: string;
}) {
  const [failed, setFailed] = React.useState(false);
  return (
    <span
      className={className}
      style={accentColour ? { '--cast-accent': accentColour } as React.CSSProperties : undefined}
    >
      {url && !failed ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt="" onError={() => setFailed(true)} />
        </>
      ) : (
        (name.trim()[0] || 'M').toUpperCase()
      )}
    </span>
  );
}

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
  React.useEffect(() => {
    pulseAppHaptic('complete');
  }, []);

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
  niveau = '',
  boucle = false,
  boucleDate = '',
}: {
  name?: string;
  date: string;
  edition: string;
  streak?: number;
  niveau?: string;
  boucle?: boolean;
  boucleDate?: string;
}) {
  /* The app masthead already carries the brand, the mark and the gear. Repeating
     them here cost three rows of chrome before any content, so the front page
     keeps only what the app header cannot say: which day this edition is, and
     whether it is filed. Edition number and level moved to Le Cours, which is
     where a level belongs. */
  return (
    <header className="lu-mast-wrap">
      <div className="folio">
        <b>{date}</b>
        {/* Idiomatic French: the ordinal stands alone; runs use the cardinal. */}
        {streak > 0 && <span>{streak === 1 ? '1ᵉʳ jour' : `${streak} jours de suite`}</span>}
        {boucle && <span className="filed">Bouclé{boucleDate ? ` · ${boucleDate}` : ''}</span>}
      </div>
    </header>
  );
}

/* ---------- lead story · Le Feuilleton / La Mission ---------- */
/* artMode: 'art' | 'press' (generating) | 'late' (delayed) | 'none' (no
   illustration for this beat — e.g. a letter mission; text leads).
   headline: hook.teaser / previously; ep 1 → honest first-scene copy. */




/* Errata — the repair queue, printed exactly like a newspaper's errata box. */

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
        <div className="lu-kicker mut">La Bibliothèque</div>
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
      <div className="head"><span>La phrase d’hier</span></div>
      <blockquote>« {text} »</blockquote>
      <p>par <em>{byline}</em></p>
    </aside>
  );
}

/* ---------- le cours du français (CEFR ticker) ---------- */


/* ---------- la manchette : the day is one story ---------- */
/* The lead episode and the day's ask were two stacked articles with two
   CTAs; the front page now carries ONE story and ONE action. Every prop maps
   to a /atelier/today field; `ask` follows the recommendation kind. */
export type LuAskKind = 'mission' | 'session' | 'review' | 'read' | 'rest';
export function LuManchette({
  ep = 1,
  mission = false,
  artMode = 'none',
  artUrl = null,
  headline,
  byline = 'Monsieur Marchand',
  portraitUrl = null,
  accentColour = null,
  minutes = 8,
  budgetMinutes = null,
  replyMode = 'write',
  ask = 'mission',
  concept = 'une règle à consolider',
  because = null,
  recap = null,
  read = false,
  done = false,
  disabled = false,
  onOpen,
  onCta,
}: {
  ep?: number;
  mission?: boolean;
  artMode?: 'art' | 'press' | 'late' | 'none';
  artUrl?: string | null;
  headline: string;
  byline?: string;
  portraitUrl?: string | null;
  accentColour?: string | null;
  minutes?: number;
  /** The learner's stated budget, passed ONLY when the honest estimate overruns it. */
  budgetMinutes?: number | null;
  /** Whether the reply to the character is written or spoken. */
  replyMode?: 'write' | 'speak';
  ask?: LuAskKind;
  concept?: string;
  /** One quiet explaining clause; null hides the line entirely. */
  because?: string | null;
  recap?: string | null;
  /** The episode itself has been read/answered (stamp on the lead). */
  read?: boolean;
  /** The whole edition is filed — no ask, no CTA. */
  done?: boolean;
  disabled?: boolean;
  onOpen?: (() => void) | null;
  onCta?: () => void;
}) {
  const kicker = mission ? `Courrier attendu · Épisode ${ep}` : `Le Feuilleton · Épisode ${ep}`;
  const showFrame = artMode === 'art' || artMode === 'press';
  const askLine = ask === 'rest' || done
    ? null
    : ask === 'mission'
      ? (replyMode === 'speak' ? `À vous de parler : cinq minutes de voix avec ${byline}.` : `À vous d’écrire : une réponse à ${byline}.`)
      : ask === 'session'
        ? 'À vous de jouer : la séance du jour.'
        : ask === 'review'
          ? 'À vous de réviser : le lexique du jour.'
          : 'À vous de lire : l’épisode du jour.';
  const lead = (
    <React.Fragment>
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
        <LuPortraitChip className="chip" name={byline} url={portraitUrl} accentColour={accentColour} />
        par <em>{byline}</em>
      </div>
    </React.Fragment>
  );
  return (
    <article className={'lu-art-sec lu-manchette' + (read ? ' done' : ' undone')}>
      {done ? <LuStamp word="Bouclé" tone="blue" tilt={-5} /> : read ? <LuStamp word={mission ? 'Envoyé' : 'Lu'} tilt={-8} /> : null}
      <div className={'lu-kicker' + (mission ? ' blue' : '')}>{kicker}</div>
      {onOpen ? (
        <button
          type="button"
          className="lu-tap"
          onClick={onOpen}
          aria-label={(mission ? 'Répondre à la mission — ' : 'Lire l’épisode — ') + headline}
        >
          {lead}
        </button>
      ) : (
        <div className="lu-tap static">{lead}</div>
      )}
      {(askLine || recap) && <div className="lu-manchette-rule" />}
      {askLine && (
        <div className="lu-ask">
          <p className="lu-ask-line">{askLine}</p>
          <p className="lu-ask-meta">{concept} · ~{minutes} min</p>
          {because && <p className="lu-prescription-because">{because}</p>}
          {budgetMinutes != null && (
            <p className="lu-prescription-overrun">
              Plus long que les {budgetMinutes} minutes demandées — vous pouvez vous arrêter
              quand vous voulez.
            </p>
          )}
        </div>
      )}
      {recap && (
        <p className="lu-cast-recap">
          <LuPortraitChip className="lu-character-chip" name={byline} url={portraitUrl} accentColour={accentColour} />
          {recap}
        </p>
      )}
      {!done && (
        <button className="lu-cta" type="button" onClick={onCta} disabled={disabled} aria-busy={disabled || undefined}>
          Continuer <IcoArrow />
        </button>
      )}
      {!done && (
        <Link className="lu-prescription-adjust" href="/settings?section=practice">Ajuster le temps de l’édition</Link>
      )}
    </article>
  );
}

/* ---------- en bref : three hairline rows ---------- */
/* Séance, lexique and cours used to be three articles with their own
   headlines, counters and buttons. On a front page they are briefs. */
export type LuBrefRow = {
  id: string;
  label: string;
  value: string;
  href?: string;
  onClick?: () => void;
  done?: boolean;
  disabled?: boolean;
};
export function LuEnBref({ rows }: { rows: LuBrefRow[] }) {
  return (
    <section className="lu-enbref" aria-label="En bref">
      <div className="lu-kicker">En bref</div>
      <div className="lu-enbref-rule" />
      {rows.map((row) => {
        const inner = (
          <React.Fragment>
            <span className="l">{row.label}</span>
            <span className="v">
              {row.done && <IcoCheck />}
              {row.value}
              {!row.done && <span className="go">→</span>}
            </span>
          </React.Fragment>
        );
        if (row.href && !row.onClick) {
          return <Link key={row.id} className={'lu-bref' + (row.done ? ' done' : '')} href={row.href}>{inner}</Link>;
        }
        return (
          <button
            key={row.id}
            type="button"
            className={'lu-bref' + (row.done ? ' done' : '')}
            onClick={row.onClick}
            disabled={row.disabled}
          >
            {inner}
          </button>
        );
      })}
    </section>
  );
}

/* ---------- demain : the colophon ---------- */
export function LuDemain({
  focus,
  focusHref = '/notebook',
  ep = null,
  epTease = null,
  grand = false,
}: {
  focus: string;
  focusHref?: string;
  ep?: number | null;
  epTease?: string | null;
  grand?: boolean;
}) {
  /* One centred italic line under a double rule — a colophon, not a section. */
  return (
    <section className={'lu-demain' + (grand ? ' grand' : '')}>
      {grand && epTease && <p className="tease">Épisode {ep} : {epTease}</p>}
      <p className="line">
        Demain — {ep ? <span>épisode {ep} · </span> : null}<Link href={focusHref}><em>{focus}</em></Link>
        {!grand && epTease ? <span> · {epTease}</span> : null}.
      </p>
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
      {retry && <button className="retry" type="button" onClick={onRetry}>Réessayer</button>}
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
        /* The "not yet printed" ink and wash. These were literal light-theme
           values, so in dark mode the withdrawn kickers landed at 2.34:1 —
           a dark grey on dark paper. Both now follow the theme tokens, which
           keeps the withdrawn feel while staying readable in either. */
        --news-ink: var(--app-ink-3);
        --news-wash: var(--app-paper-2);
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
      /* Zero-specificity reset: the old .lu a (class + type) outranked every
         component class, which is why styled links rendered at inherited size
         and full ink instead of their own quiet type. */
      .lu :where(a, button) { font: inherit; color: inherit; text-align: inherit; }
      .lu :where(button) { border: 0; background: transparent; padding: 0; cursor: pointer; }

      .lu-page { flex: 1 1 auto; padding: 0 18px calc(18px + 12px); }

      /* ---- folio: one quiet line, no second brand ---- */
      .lu-mast-wrap { padding: 14px 0 0; }
      .lu-mast-wrap .folio {
        display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
        font-size: var(--t-small); color: var(--ink-3);
      }
      .lu-mast-wrap .folio b { color: var(--ink-2); font-weight: 600; }
      .lu-mast-wrap .folio .filed { color: var(--red); font-weight: 800; }

      /* ---- generic article ----
         Sections are separated by space, not boxes. One hairline between them
         at most; a section that already reads as a unit gets none. */
      .lu-art-sec { position: relative; padding: 26px 0 0; }
      .lu-art-sec + .lu-art-sec { border-top: 1px solid var(--paper-3); }
      .lu-art-sec.no-rule { border-top: 0; }
      .lu-kicker {
        display: flex; align-items: center; gap: 8px; white-space: nowrap;
        font-size: var(--t-label); font-weight: 700; letter-spacing: .12em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .lu-kicker.blue { color: var(--blue); }
      .lu-kicker.mut { color: var(--ink-3); }
      .lu-head {
        margin: 8px 0 0; font-family: var(--serif); font-style: italic;
        font-weight: 600; font-size: var(--t-head); line-height: 1.06; color: var(--ink);
        text-wrap: pretty;
      }
      .lu-head.lg { font-size: var(--t-head); }
      .lu-deck { margin: 8px 0 0; font-size: var(--t-small); line-height: 1.45; color: var(--ink-2); }
      .lu-byline {
        margin-top: 10px; display: flex; align-items: center; gap: 7px;
        font-size: var(--t-label); font-weight: 600; color: var(--ink-3);
      }
      .lu-byline .chip {
        width: 22px; height: 22px; border: 1px solid var(--ink); border-radius: 50%;
        background: var(--cast-accent, var(--paper-2)); display: grid; place-items: center;
        font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-label);
        flex: 0 0 auto;
      }
      .lu-byline .chip img, .lu-character-chip img { width: 100%; height: 100%; display: block; object-fit: cover; object-position: top center; }
      .lu-character-target { display: inline-flex; align-items: center; gap: 5px; }
      .lu-character-chip { width: 22px; height: 22px; display: inline-grid; place-items: center; overflow: hidden; border: 1px solid var(--ink); background: var(--cast-accent, var(--news-wash)); font: 700 var(--t-label)/1 var(--mono); }
      .lu-byline em { font-style: italic; font-family: var(--serif); font-size: var(--t-small); }

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
        font-size: var(--t-body); font-weight: 800; letter-spacing: .24em; text-indent: .24em;
        text-transform: uppercase; opacity: .9; background: transparent;
      }
      .lu-stamp.ink { color: var(--ink); }
      .lu-stamp.blue { color: var(--blue); }
      .lu-stamp.sm { font-size: var(--t-label); border-width: 2px; padding: 3px 8px 2px; box-shadow: inset 0 0 0 1px var(--sheet), inset 0 0 0 2px currentColor; }
      .lu-stamp .d { display: block; font-size: var(--t-label); letter-spacing: .16em; text-indent: .16em; margin-top: 1px; }
      @media (prefers-reduced-motion: no-preference) {
        .lu.motion .lu-art-sec.done .lu-stamp { animation: lu-strike .32s cubic-bezier(.18, 1.35, .3, 1) .18s both; }
      }
      @keyframes lu-strike {
        from { opacity: 0; transform: scale(1.55) rotate(var(--tilt, -7deg)); }
        60% { opacity: .95; }
        to { opacity: .9; transform: scale(1) rotate(var(--tilt, -7deg)); }
      }

      /* ---- la manchette (the one story) ---- */
      .lu-manchette { padding-top: 14px; }
      .lu-manchette .lu-stamp { top: 26px; right: 4px; }
      .lu-art-frame { position: relative; margin-top: 10px; border: 1px solid var(--ink); background: var(--paper-2); }
      .lu-art-frame .ratio { position: relative; width: 100%; aspect-ratio: 16 / 10; overflow: hidden; }
      .lu-art-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; }

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
      .lu-art-press .plate b { display: block; font-size: var(--t-label); font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
      .lu-art-press .plate span { display: block; margin-top: 4px; font-size: var(--t-small); color: var(--ink-2); }
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
        margin-top: 10px; font-size: var(--t-small); line-height: 1.5; color: var(--ink-2);
      }
      .lu-art-late b { font-weight: 700; color: var(--ink); display: block; }

      .lu-manchette-rule { height: 1px; background: var(--paper-3); margin-top: 16px; }
      .lu-ask { margin-top: 14px; display: grid; gap: 4px; }
      .lu-ask-line { margin: 0; font-size: var(--t-small); line-height: 1.5; color: var(--ink-2); }
      .lu-ask-meta { margin: 0; font-size: var(--t-small); line-height: 1.5; color: var(--ink-3); }
      .lu-prescription-because,
      .lu-prescription-overrun {
        margin: 6px 0 0; font-size: var(--t-small); line-height: 1.5; color: var(--ink-3);
      }
      .lu-prescription-adjust {
        display: inline-flex; align-items: center; min-height: 44px; margin-top: 2px; color: var(--ink-3);
        font-size: var(--t-small); font-weight: 400; letter-spacing: 0;
        text-decoration-thickness: 1px; text-underline-offset: 3px;
      }
      .lu-cast-recap { display: flex; align-items: center; gap: 7px; margin: 12px 0 0; color: var(--ink-2); font: italic var(--t-small)/1.4 var(--serif); }

      /* Primary action, softened per the owner: a pill of solid ink, sentence
         case, no wide tracking. Still one action per page. */
      .lu .lu-cta {
        margin-top: 16px;
        display: flex; align-items: center; justify-content: center; gap: 10px;
        width: 100%; min-height: 54px; padding: 0 22px;
        background: var(--ink); color: var(--paper);
        border: 0; border-radius: 999px;
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em;
        text-decoration: none; cursor: pointer;
        transition: background .16s ease, color .16s ease, transform .12s ease;
      }
      .lu-cta:hover { background: var(--ink-2); color: var(--paper); }
      .lu-cta:active { background: var(--paper-2); color: var(--ink); transform: translateY(1px); }
      .lu-cta:disabled { opacity: .5; cursor: progress; }
      .lu-cta:disabled:hover { background: var(--ink); color: var(--paper); }
      .lu-cta svg { width: 16px; height: 16px; }
      .lu-art-sec.done .lu-cta { display: none; }

      /* ---- en bref ---- */
      .lu-enbref { padding: 26px 0 0; display: flex; flex-direction: column; }
      .lu-enbref .lu-kicker { margin-bottom: 10px; }
      .lu-enbref-rule { height: 1px; background: var(--ink); }
      .lu .lu-bref {
        display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
        width: 100%; min-height: 52px; padding: 15px 0;
        background: none; border: 0; border-bottom: 1px solid var(--paper-3);
        color: var(--ink); text-align: left; text-decoration: none; cursor: pointer;
      }
      .lu .lu-bref:last-child { border-bottom: 0; }
      .lu-bref .l { font-family: var(--serif); font-size: var(--t-lead); line-height: 1.2; }
      .lu-bref .v { display: inline-flex; align-items: baseline; gap: 6px; font-size: var(--t-small); color: var(--ink-2); text-align: right; }
      .lu-bref .v .go { color: var(--ink-3); }
      .lu-bref .v svg { width: 12px; height: 12px; align-self: center; }
      .lu-bref.done .l, .lu-bref.done .v { color: var(--ink-3); }
      .lu-bref:disabled { opacity: .5; cursor: progress; }
      .lu-bref:hover .v .go { color: var(--ink); }

      /* ---- citation du jour ---- */
      .lu-citation { text-align: center; padding: 26px 20px 0; }
      .lu-citation .q { margin: 0; font-family: var(--serif); font-style: italic; font-size: var(--t-lead); line-height: 1.35; }
      .lu-citation .src { margin: 8px 0 0; font-size: var(--t-label); font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-3); }

      /* ---- la phrase d'hier ---- */
      .lu-phrase-du-jour { padding: 26px 0 0; border-top: 1px solid var(--paper-3); }
      .lu-phrase-du-jour .head {
        font-size: var(--t-label); font-weight: 700; letter-spacing: .12em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .lu-phrase-du-jour blockquote {
        margin: 10px 0 0; font-family: var(--serif); font-style: italic;
        font-size: var(--t-head); line-height: 1.2; color: var(--ink);
      }
      .lu-phrase-du-jour p {
        margin: 8px 0 0; font-size: var(--t-label); font-weight: 600; letter-spacing: .08em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .lu-phrase-du-jour p em { font-family: var(--serif); font-size: var(--t-small); text-transform: none; color: var(--ink); }

      /* ---- demain : the colophon ---- */
      .lu-demain { margin-top: 10px; padding: 14px 0 6px; border-top: 3px double var(--ink); text-align: center; }
      .lu-demain .line {
        margin: 0; font-family: var(--serif); font-style: italic; font-size: var(--t-small); line-height: 1.5; color: var(--ink-3);
      }
      .lu-demain .line em { font-style: italic; color: var(--ink-2); }
      .lu-demain a { text-decoration: none; border-bottom: 1px solid var(--paper-3); }
      .lu-demain.grand .tease {
        margin: 0 0 8px; font-family: var(--serif); font-style: italic;
        font-weight: 600; font-size: var(--t-head); line-height: 1.15; color: var(--ink);
      }

      /* ---- press notice (load errors) ---- */
      .lu-notice {
        margin: 14px 0 0; border: 1.5px solid var(--ink); background: var(--paper-2);
        display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: center;
        padding: 11px 12px;
      }
      .lu-notice .sq { width: 12px; height: 12px; background: var(--red); border: 1px solid var(--ink); }
      .lu-notice .sq.blue { background: var(--blue); }
      .lu-notice .sq.yellow { background: var(--yellow); }
      .lu-notice .body b { display: block; font-size: var(--t-label); font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
      .lu-notice .body p { margin: 4px 0 0; font-size: var(--t-small); line-height: 1.45; color: var(--ink-2); }
      .lu-notice .retry {
        min-height: 44px; padding: 0 14px; border: 1.5px solid var(--ink);
        background: var(--ink); color: var(--paper);
        font-size: var(--t-label); font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
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
        .lu-grid { display: grid; grid-template-columns: 1.35fr 1px 1fr; gap: 0 26px; }
        .lu-grid .lu-col { display: block; }
        .lu-grid .vrule { display: block; background: var(--ink); }
        .lu-head.lg { font-size: var(--t-display); }
      }
    `}</style>
  );
}
