/* Atelier — LE FEUILLETON · the edition's illustrated serial supplement.
   1:1 port of the design package (feuilleton-parts.jsx / feuilleton.css, the
   "Atelier Le Feuilleton" canvas) into the app's token system. One section,
   four views (reader · archive · cast · permalink), one type language shared
   with "La Une" and "Le Courrier".

   TOKEN DISCIPLINE — the whole point of this pass:
   · Uses --app-* tokens ONLY. The design doc hardcoded a light palette and
     re-aliased the app tokens; both are removed here. The `.fe` shell maps its
     locals straight onto --app-*, so light/dark are free (globals.css owns the
     theme via :root[data-theme]).
   · DERIVED VALUES (documented, theme-aware):
       --fe-halftone : the 135° tint field on a set-but-unread plate — ink @ 6%
                       (light) / paper @ 5% (dark).
       --char-*      : one spot ink per cast member (serial world bible). Lifts a
                       step in dark. Real cast members carry `accent_colour` from
                       the API — pass it via the `accent` prop to override.
   The migration note lives in docs/overhaul-feuilleton.md §5. Bottom tab bar
   (PhoneProductNav) is untouched — the `.fe-tabs` here is design-only and unused
   in the app. */

import React from 'react';
import Link from 'next/link';
import type { CSSProperties, ReactNode } from 'react';

/* ---------- tiny press icons (grotesk chrome only) ---------- */
export const FeIco = {
  back: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" aria-hidden="true">
      <path d="M14 6l-6 6 6 6" />
    </svg>
  ),
  play: (
    <svg viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden="true">
      <path d="M7 4l13 8-13 8z" />
    </svg>
  ),
  pause: (
    <svg viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden="true">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  ),
  arrow: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" aria-hidden="true">
      <path d="M5 12h13M13 6l6 6-6 6" />
    </svg>
  ),
  sound: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" aria-hidden="true">
      <path d="M4 9v6h4l5 4V5L8 9z" />
      <path d="M17 9a4 4 0 0 1 0 6" />
    </svg>
  ),
};

/* accent bridge — real cast members carry `accent_colour`; the design keys a
   `data-char` slug onto the world-bible palette. Either sets --accent. */
function accentStyle(accent?: string | null, extra?: CSSProperties): CSSProperties | undefined {
  if (accent) return { ['--accent' as any]: accent, ...(extra || {}) };
  return extra;
}

/* ============================================================
   MASTHEAD BAR — the section's ear-badge + settings lockup, matching
   La Une (LuMasthead) and Les Cahiers (NcMasthead) so every surface
   opens the same way. Sits above the section nav on all Feuilleton views.
   ============================================================ */
export function FeMastheadBar({ settingsHref = '/settings' }: { settingsHref?: string }) {
  return (
    <div className="fe-ears">
      <Link className="ear-gear" href={settingsHref} aria-label="Réglages">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
          <circle cx="12" cy="12" r="3.2" />
          <path d="M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1" />
        </svg>
      </Link>
    </div>
  );
}

/* ============================================================
   SECTION NAV — the cross-route IA (reader · archive · cast).
   One "Feuilleton section of the paper" across the four routes.
   ============================================================ */
export function FeSectionNav({ active }: { active: 'episode' | 'season' | 'cast' }) {
  return (
    <nav className="fe-secnav" aria-label="Le Feuilleton">
      <Link href="/graphic-novel" className={active === 'episode' ? 'active' : undefined}>
        L’épisode
      </Link>
      <Link href="/serial" className={active === 'season' ? 'active' : undefined}>
        La saison
      </Link>
      <Link href="/serial/cast" className={active === 'cast' ? 'active' : undefined}>
        Les personnages
      </Link>
    </nav>
  );
}

/* ============================================================
   A. DATELINE MASTHEAD  +  reading-progress rule
   fields: episode_index, title, dateline, season
   ============================================================ */
/* ONE compact header. The folio is a single kicker line — section · season ·
   episode — so the season is named exactly once on the page; the dateline is one
   line (place · date). Anything else that used to stack above the title (a news
   kicker with no news, a repeated "Saison 1", a per-panel credit) is gone. */
export function FeMasthead({
  section = 'Le Feuilleton',
  season = 1,
  index,
  title,
  dateline = [],
  progress = 0,
  progressRed = false,
}: {
  section?: ReactNode;
  season?: number | null;
  index?: number | string | null;
  title: ReactNode;
  dateline?: string[];
  progress?: number;
  progressRed?: boolean;
}) {
  const folio: ReactNode[] = [section];
  if (season != null) folio.push(`Saison ${season}`);
  if (index != null) folio.push(`Épisode ${index}`);
  return (
    <>
      <div className="fe-mast">
        <div className="folio">
          {folio.map((part, i) => (
            <React.Fragment key={i}>
              {i > 0 && <i />}
              <span>{part}</span>
            </React.Fragment>
          ))}
        </div>
        <h1>{title}</h1>
        {dateline.length > 0 && (
          <div className="dateline">
            {dateline.map((d, i) => (
              <React.Fragment key={i}>
                {i > 0 && <i />}
                <span>{d}</span>
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
      <div className={'fe-progress' + (progressRed ? ' red' : '')}>
        <i style={{ width: Math.max(0, Math.min(100, progress)) + '%' }} />
      </div>
    </>
  );
}

/* ============================================================
   PREVIOUSLY — one line: what your last reply changed
   ============================================================ */
export function FePreviously({ children }: { children: ReactNode }) {
  return (
    <p className="fe-previously">
      <span className="tag">Précédemment</span> {children}
    </p>
  );
}

/* ============================================================
   B. PANEL — one frame · one numeral · an additive caption
   The panel prints the art and nothing else on top of it: the old on-art bubble
   layer, the "direction" slug, the repeated "LE FEUILLETON" credit line and the
   uppercase title slug are gone (they duplicated the dialogue and stacked six
   kickers down the page). Dialogue is one block of lines under the art
   (FeDialogue). One ratio for every plate.
   ============================================================ */
export type FeRatio = 'square' | 'tall' | 'wide' | '';

export function FePanel({
  ratio = 'square',
  caption,
  capNum,
  imageUrl,
  imageAlt = '',
  status,
  statusNote,
  full = false,
  colorable = false,
  children,
}: {
  ratio?: FeRatio;
  caption?: ReactNode;
  capNum?: ReactNode;
  imageUrl?: string | null;
  imageAlt?: string;
  status?: 'generating' | 'delayed';
  statusNote?: ReactNode;
  full?: boolean;
  colorable?: boolean;
  children?: ReactNode;
}) {
  const cls =
    'fe-art' + (ratio ? ' ' + ratio : '') + (status ? ' ' + status : '') + (colorable ? ' fe-colorable' : '');
  // A plate with no art and nothing being printed draws no empty frame: the
  // dialogue leads and the page stays quiet rather than promising an image.
  const hasPlate = Boolean(imageUrl || status || children);
  return (
    <div className={'fe-panel' + (full ? ' full' : '')}>
      {hasPlate && (
      <div className={cls}>
        {status === 'generating' ? (
          /* One quiet plate-ruled frame with a small press mark — no sentence
             repeated once per panel while the art prints. */
          <span className="press-mark">{statusNote || 'Sous presse'}</span>
        ) : status === 'delayed' ? (
          <div className="apology">
            <div className="k">Planche retardée</div>
            <div className="m">
              {statusNote || 'La presse a pris du retard. Le texte mène ; l’image suit sous peu.'}
            </div>
          </div>
        ) : (
          <>
            {imageUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img className="fe-art-img" src={imageUrl} alt={imageAlt} />
            )}
            {children}
          </>
        )}
      </div>
      )}
      {caption && (
        <div className="fe-cap">
          {capNum != null && <div className="n">{capNum}</div>}
          <div className="c">{caption}</div>
        </div>
      )}
    </div>
  );
}

/* The panel's dialogue: canonical short speaker names, one line each, with a
   single "Traduire" affordance that stays closed until the reader asks. */
export type FeDialogueLine = { who?: ReactNode; fr: ReactNode; en?: ReactNode };

export function FeDialogue({
  char,
  accent,
  lines,
  translated = false,
  onTranslate,
  translateLabel = 'Traduire',
  hideLabel = 'Masquer la traduction',
}: {
  char?: string;
  accent?: string | null;
  lines: FeDialogueLine[];
  translated?: boolean;
  onTranslate?: () => void;
  translateLabel?: ReactNode;
  hideLabel?: ReactNode;
}) {
  if (!lines.length) return null;
  const hasEnglish = lines.some((line) => line.en);
  return (
    <div className="fe-dialogue" data-char={char} style={accentStyle(accent)}>
      {lines.map((line, i) => (
        <p className="line" key={i}>
          {line.who && <b>{line.who} —</b>} {line.fr}
          {translated && line.en && <em>{line.en}</em>}
        </p>
      ))}
      {hasEnglish && onTranslate && (
        <button type="button" className="fe-translate" onClick={onTranslate}>
          {translated ? hideLabel : translateLabel}
        </button>
      )}
    </div>
  );
}

/* ============================================================
   RELATIONSHIP CUE — register + closeness, in-scene
   ============================================================ */
export function FeRelChip({
  char,
  accent,
  name,
  ini,
  register = 'vous',
  closeness = 0,
}: {
  char?: string;
  accent?: string | null;
  name?: ReactNode;
  ini?: string;
  register?: string;
  closeness?: number;
}) {
  return (
    <div className="fe-rel" data-char={char} style={accentStyle(accent)}>
      <div className="ava">{ini || '?'}</div>
      <div className="meta">
        <div className="nm">{name}</div>
        <div className="rr">
          <span className={'reg' + (register === 'tu' ? ' tu' : '')}>{register}</span>
          <span className="pips">
            {[0, 1, 2, 3, 4].map((i) => (
              <i key={i} className={i < closeness ? 'on' : ''} />
            ))}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   AUDIO — "Écouter l'épisode": pinned bar + inline CTA
   ============================================================ */
export function FeAudioBar({
  playing = false,
  title = 'Écouter l’épisode',
  now,
  at = 0,
  ticks = [],
  time = '0:00 / 4:12',
  onToggle,
}: {
  playing?: boolean;
  title?: ReactNode;
  now?: ReactNode;
  at?: number;
  ticks?: number[];
  time?: ReactNode;
  onToggle?: () => void;
}) {
  return (
    <div className={'fe-audio' + (playing ? ' playing' : '')}>
      <div className="row">
        <button type="button" className="play" onClick={onToggle} aria-label={playing ? 'Pause' : 'Écouter'}>
          {playing ? FeIco.pause : FeIco.play}
        </button>
        <div className="lab">
          <div className="k">{playing ? 'Lecture en cours' : 'Version sonore'}</div>
          <div className="t">{title}</div>
        </div>
        <div className="time">{time}</div>
      </div>
      <div className="scrub">
        <i style={{ width: Math.max(0, Math.min(100, at)) + '%' }} />
        {ticks.map((t, i) => (
          <span className="tick" key={i} style={{ left: t + '%' }} />
        ))}
      </div>
      {now && <div className="now">{now}</div>}
    </div>
  );
}

export function FeAudioCTA({ label = 'Écouter l’épisode', onClick }: { label?: ReactNode; onClick?: () => void }) {
  return (
    <button type="button" className="fe-audio-cta" onClick={onClick}>
      {FeIco.sound}
      <span>{label}</span>
    </button>
  );
}

/* ============================================================
   READ-FIRST STUDY TASK — folded → revealed after the read
   ============================================================ */
/* ONE quiet inline action: a kicker, then the body. The prompt is said once,
   by the body itself — the old reveal button, the anchor counter and the
   duplicated title line are gone. */
export function FeTask({ kicker = 'Votre réplique', children }: { kicker?: ReactNode; children?: ReactNode }) {
  return (
    <div className="fe-task">
      <div className="th">
        <span className="k">{kicker}</span>
      </div>
      <div className="tb">{children}</div>
    </div>
  );
}

/* ============================================================
   CLIFFHANGER + CONTINUATION + FILED
   ============================================================ */
export function FeCliff({ kicker = 'À suivre', hook, demain }: { kicker?: ReactNode; hook: ReactNode; demain?: ReactNode }) {
  return (
    <div className="fe-cliff">
      <div className="k">{kicker}</div>
      <div className="q">{hook}</div>
      {demain && <div className="demain">Demain — {demain}</div>}
    </div>
  );
}

export function FeContinuation({
  readNext = 'Lire le prochain épisode',
  actIn = 'Agir dans Le Courrier',
  onReadNext,
  onActIn,
  readNextHref,
  actInHref,
}: {
  readNext?: ReactNode;
  actIn?: ReactNode;
  onReadNext?: () => void;
  onActIn?: () => void;
  readNextHref?: string;
  actInHref?: string;
}) {
  const Read: any = readNextHref ? 'a' : 'button';
  const Act: any = actInHref ? 'a' : 'button';
  return (
    <div className="fe-cont">
      <Read className="beat read" href={readNextHref} type={readNextHref ? undefined : 'button'} onClick={onReadNext}>
        <span>{readNext}</span>
        {FeIco.arrow}
      </Read>
      <Act className="beat act" href={actInHref} type={actInHref ? undefined : 'button'} onClick={onActIn}>
        <span>{actIn}</span>
        {FeIco.arrow}
      </Act>
    </div>
  );
}

export function FeFiled({ label = 'Classé · Épisode déposé' }: { label?: ReactNode }) {
  return <div className="fe-stamp-filed">{label}</div>;
}

/* ============================================================
   C. ARCHIVE — filed plate row
   ============================================================ */
export function FeArchivePlate({
  roman,
  title,
  date,
  location,
  char,
  accent,
  ini,
  slug,
  choice,
  outcome,
  thumbnailUrl,
  state = 'filed',
  href,
  currentLabel = 'En cours',
  upLabel = 'À venir',
  filedLabel = 'Classé',
}: {
  roman: ReactNode;
  title: ReactNode;
  date?: ReactNode;
  location?: ReactNode;
  char?: string;
  accent?: string | null;
  ini?: string;
  slug?: string;
  choice?: ReactNode;
  outcome?: ReactNode;
  thumbnailUrl?: string | null;
  state?: 'filed' | 'current' | 'up';
  href?: string;
  currentLabel?: ReactNode;
  upLabel?: ReactNode;
  filedLabel?: ReactNode;
}) {
  const Tag: any = href ? 'a' : 'div';
  return (
    <Tag
      className={'fe-plate ' + (state === 'current' ? 'current' : state === 'up' ? 'up' : '')}
      data-char={char}
      href={href}
      style={accentStyle(accent)}
    >
      <div className="roman">{roman}</div>
      <div className="thumb">
        {thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumbnailUrl} alt="" />
        ) : (
          slug && <span className="slug">{slug}</span>
        )}
        <span className="port">{ini || '·'}</span>
      </div>
      <div className="info">
        {(date || location) && (
          <div className="meta">
            {date && <span>{date}</span>}
            {date && location && <i />}
            {location && <span>{location}</span>}
          </div>
        )}
        <h3>{title}</h3>
        {choice && (
          <div className="choice">
            <b>Votre réplique</b>
            <em>« {choice} »</em>
          </div>
        )}
        {outcome && <div className="outcome">{outcome}</div>}
      </div>
      <span className="filed">{state === 'current' ? currentLabel : state === 'up' ? upLabel : filedLabel}</span>
    </Tag>
  );
}

/* ============================================================
   D. CAST — card · register stamp · closeness · ledger
   ============================================================ */
export function FeCastCard({
  char,
  accent,
  name,
  ini,
  role,
  loc,
  register = 'vous',
  closeness = 0,
  switchEp,
  callbacks = [],
  last,
  slug,
  imageUrl,
  children,
}: {
  char?: string;
  accent?: string | null;
  name?: ReactNode;
  ini?: string;
  role?: ReactNode;
  loc?: ReactNode;
  register?: string;
  closeness?: number;
  switchEp?: ReactNode;
  callbacks?: ReactNode[];
  last?: ReactNode;
  slug?: string;
  imageUrl?: string | null;
  children?: ReactNode;
}) {
  return (
    <div className="fe-cast-card" data-char={char} style={accentStyle(accent)}>
      <div className="top">
        <div className="port">
          {imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={imageUrl} alt="" />
          ) : (
            ini
          )}
          {slug && <span className="slug">{slug}</span>}
        </div>
        <div className="id">
          <div className="nm">{name}</div>
          {(role || loc) && (
            <div className="role">
              {role}
              {loc ? (
                <>
                  {' · '}
                  <b>{loc}</b>
                </>
              ) : null}
            </div>
          )}
        </div>
        <FeRegStamp register={register} />
      </div>
      <div className="fe-close">
        <span className="cap">Proximité</span>
        <span className="switch">
          {switchEp != null ? (
            <>
              Tutoiement — <b>ép. {switchEp}</b>
            </>
          ) : (
            'Pas encore de tutoiement'
          )}
        </span>
        <span className="pips">
          {[0, 1, 2, 3, 4].map((i) => (
            <i key={i} className={i < closeness ? 'on' : ''} />
          ))}
        </span>
      </div>
      <div className="fe-ledger">
        <div className="cap">Rappels</div>
        {callbacks.length ? (
          <div className="cb">
            {callbacks.map((cb, i) => (
              <span key={i}>{cb}</span>
            ))}
          </div>
        ) : (
          <div className="none">Aucun rappel encore — l’histoire commence.</div>
        )}
        {last ? (
          <div className="last">
            <b>Dernier échange —</b> {last}
          </div>
        ) : (
          <div className="none">Vous ne vous êtes pas encore parlé.</div>
        )}
      </div>
      {children}
    </div>
  );
}

/* learner's own serial character */
export function FeMeCard({
  name = 'Toi',
  ini = 'T',
  kicker = 'Votre personnage',
  slug,
  onCustomise,
  customiseLabel = 'Personnaliser',
  imageUrl,
  children,
}: {
  name?: ReactNode;
  ini?: string;
  kicker?: ReactNode;
  slug?: ReactNode;
  onCustomise?: () => void;
  customiseLabel?: ReactNode;
  imageUrl?: string | null;
  children?: ReactNode;
}) {
  return (
    <div className="fe-me" data-char="toi">
      <div className="top">
        <div className="port">
          {imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={imageUrl} alt="" />
          ) : (
            ini
          )}
        </div>
        <div className="id">
          <div className="k">{kicker}</div>
          <div className="nm">{name}</div>
        </div>
        {onCustomise && (
          <button type="button" className="customise" onClick={onCustomise}>
            {customiseLabel}
          </button>
        )}
      </div>
      {slug && (
        <div className="ref">
          <div className="slug">{slug}</div>
        </div>
      )}
      {children}
    </div>
  );
}

export function FeRegStamp({ register = 'vous' }: { register?: string }) {
  return (
    <div className={'fe-reg' + (register === 'vous' ? ' vous' : '')}>
      <span className="r">{register}</span>
      <span className="l">{register === 'tu' ? 'accordé' : 'de rigueur'}</span>
    </div>
  );
}

/* ============================================================
   SKELETON + NOTICE
   ============================================================ */
export function FeSkeleton({ press = '— on tire l’édition —' }: { press?: ReactNode }) {
  return (
    <div className="fe-skel" aria-hidden="true">
      <div className="l" style={{ width: '40%', margin: '0 auto 10px' }} />
      <div className="l" style={{ width: '70%', height: 20, margin: '0 auto 12px' }} />
      <div className="art" />
      <div className="l" style={{ width: '90%' }} />
      <div className="l" style={{ width: '80%' }} />
      <div className="l" style={{ width: '55%' }} />
      <div className="press">{press}</div>
    </div>
  );
}

export function FeNotice({
  label = 'Avis de la rédaction',
  msg = 'La planche n’a pas pu être imprimée. La rédaction a été prévenue.',
  onRetry,
  retryLabel = 'Réessayer',
}: {
  label?: ReactNode;
  msg?: ReactNode;
  onRetry?: () => void;
  retryLabel?: ReactNode;
}) {
  return (
    <div className="fe-notice">
      <div className="nh">
        <span className="tri" />
        <span className="t">{label}</span>
      </div>
      <div className="nb">
        <div className="m">{msg}</div>
        {onRetry && (
          <button type="button" className="retry" onClick={onRetry}>
            {FeIco.arrow}
            <span>{retryLabel}</span>
          </button>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   THE STYLES — ported from feuilleton.css, --app-* only.
   `.fe` maps its locals onto the theme-aware app tokens; derived
   halftone / scrim / char accents are defined here and lifted in
   dark via :root[data-theme="dark"] .fe.
   ============================================================ */
export function FeuilletonStyles() {
  return (
    <style jsx global>{`
      /* .fe = the standalone phone-shell supplement page (archive / cast).
         .fe-embed = the same token + accent scope with NO layout, so the shared
         primitives can be dropped into another surface (e.g. the reader's own
         two-column layout) without imposing the phone shell. */
      .fe, .fe-embed {
        --serif: var(--app-serif);
        --grotesk: 'Inter', 'Helvetica Neue', Arial, sans-serif;
        --fe-mono: 'iA Writer Mono', ui-monospace, 'SF Mono', Menlo, monospace;
        --fe-halftone: rgba(20, 17, 13, 0.06);
        /* character accent palette — from the serial world bible */
        --char-romy: #1d3a8a;
        --char-marin: #2c6a5d;
        --char-lila: #c2890f;
        --char-gus: #8a2f2a;
        --char-margaux: #a85d24;
        --char-marchand: #5b5346;
        --char-toi: var(--app-ink);
        --accent: var(--app-ink);
        color: var(--app-ink);
        -webkit-font-smoothing: antialiased;
      }
      .fe {
        position: relative;
        width: min(var(--app-viewport-width), var(--phone-shell-max));
        min-height: var(--app-viewport-height);
        margin: 0 auto;
        background: var(--app-paper);
        font-family: var(--grotesk);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        padding-top: var(--phone-safe-top);
      }
      :root[data-theme='dark'] .fe,
      :root[data-theme='dark'] .fe-embed {
        --fe-halftone: rgba(245, 239, 225, 0.05);
        --char-romy: #7c9bff;
        --char-marin: #5fb3a1;
        --char-lila: #e0ad3e;
        --char-gus: #d97a72;
        --char-margaux: #d68f52;
        --char-marchand: #a89b86;
      }
      .fe *, .fe-embed * { box-sizing: border-box; }
      /* Wrapped in :where() so the reset carries zero specificity: as plain
         element selectors these outranked every component class and silently
         removed their border, padding and type. */
      .fe :where(a, button), .fe-embed :where(a, button) { font: inherit; color: inherit; text-align: inherit; }
      .fe :where(button), .fe-embed :where(button) { border: 0; background: transparent; padding: 0; cursor: pointer; }
      .fe-body { flex: 1 1 auto; }
      .fe-scroll { padding-bottom: calc(var(--phone-bottom-nav-space, 20px)); }

      /* MASTHEAD EAR ROW — matches La Une / Les Cahiers ears */
      .fe-ears, .fe-embed .fe-ears {
        display: flex; align-items: center; justify-content: space-between;
        padding: 12px 18px 0; min-height: 44px;
      }
      .fe-ears .ear-badge {
        border: 1px solid var(--app-ink); background: var(--app-sheet);
        padding: 5px 8px 4px; font-size: var(--t-label); font-weight: 900;
        letter-spacing: .14em; text-transform: uppercase; white-space: nowrap;
        color: var(--app-ink);
      }
      .fe-ears .ear-gear {
        width: 44px; height: 44px; margin: -6px -8px 0 0;
        display: grid; place-items: center; color: var(--app-ink-2);
      }
      .fe-ears .ear-gear svg { width: 18px; height: 18px; }

      /* SECTION NAV — cross-route IA */
      .fe-secnav {
        display: flex; gap: 18px; padding: 11px 18px; border-bottom: 1px solid var(--app-ink);
        background: var(--app-sheet);
        font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase;
      }
      .fe-secnav a { color: var(--app-ink-3); text-decoration: none; padding-bottom: 2px; border-bottom: 2px solid transparent; }
      .fe-secnav a:hover { color: var(--app-ink-2); }
      .fe-secnav a.active { color: var(--app-ink); border-bottom-color: var(--app-red); }

      /* accent scope */
      .fe [data-char='romy'], .fe-embed [data-char='romy'] { --accent: var(--char-romy); }
      .fe [data-char='marin'], .fe-embed [data-char='marin'] { --accent: var(--char-marin); }
      .fe [data-char='lila'], .fe-embed [data-char='lila'] { --accent: var(--char-lila); }
      .fe [data-char='gus'], .fe-embed [data-char='gus'] { --accent: var(--char-gus); }
      .fe [data-char='margaux'], .fe-embed [data-char='margaux'] { --accent: var(--char-margaux); }
      .fe [data-char='marchand'], .fe-embed [data-char='marchand'] { --accent: var(--char-marchand); }
      .fe [data-char='toi'], .fe-embed [data-char='toi'] { --accent: var(--char-toi); }

      /* discreet chrome bar */
      .fe-chrome {
        display: flex; align-items: center; gap: 8px;
        padding: 8px 16px; border-bottom: 1px solid var(--app-ink);
        background: var(--app-sheet);
      }
      .fe-chrome .back {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase;
        color: var(--app-ink); text-decoration: none;
      }
      .fe-chrome .back svg { width: 13px; height: 13px; }
      .fe-chrome .en {
        margin-left: auto;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase;
        border: 1px solid var(--app-ink); background: var(--app-paper);
        padding: 4px 8px; color: var(--app-ink-2); cursor: pointer;
      }
      .fe-chrome .en.on { background: var(--app-ink); color: var(--app-paper); }

      /* A. DATELINE MASTHEAD */
      .fe-mast { padding: 15px 20px 0; text-align: center; }
      .fe-mast .folio {
        display: flex; align-items: center; justify-content: center; gap: 7px;
        padding: 5px 0; border-top: 1px solid var(--app-ink);
        border-bottom: 3px double var(--app-ink);
        font-size: var(--t-label); font-weight: 800; letter-spacing: .18em; text-transform: uppercase;
        color: var(--app-ink);
      }
      .fe-mast .folio i { width: 3px; height: 3px; background: var(--app-red); display: inline-block; }
      .fe-mast .kicker {
        margin-top: 11px;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .22em; text-transform: uppercase;
        color: var(--app-red);
      }
      .fe-mast h1 {
        margin: 6px 0 0;
        font-family: var(--serif); font-style: italic; font-weight: 700;
        font-size: var(--t-head); line-height: .98; letter-spacing: 0; color: var(--app-ink);
        text-wrap: balance;
      }
      .fe-mast .dateline {
        margin: 9px 0 13px;
        display: flex; align-items: center; justify-content: center; gap: 8px;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase;
        color: var(--app-ink-3);
      }
      .fe-mast .dateline i { width: 3px; height: 3px; background: var(--app-ink-3); display: inline-block; }

      .fe-progress { height: 3px; background: var(--app-paper-3); position: relative; overflow: hidden; }
      .fe-progress > i { position: absolute; inset: 0 auto 0 0; background: var(--app-ink); transition: width .3s ease; }
      .fe-progress.red > i { background: var(--app-red); }

      /* PREVIOUSLY */
      /* One quiet italic line — not a boxed strip with its own kicker row. */
      .fe-previously {
        margin: 10px 18px 0; text-align: center;
        font-family: var(--serif); font-style: italic; font-size: var(--t-small); line-height: 1.4; color: var(--app-ink-3);
      }
      .fe-previously .tag {
        font-family: var(--grotesk); font-style: normal; font-weight: 800;
        letter-spacing: .01em; color: var(--app-ink-2);
      }
      /* B. THE PANEL */
      .fe-panel { margin: 16px 18px; }
      .fe-panel.full { margin: 16px 0; }
      /* ONE ratio and one focal treatment for every plate: the generated art is
         square, so a square frame crops nothing and the page keeps a rhythm. */
      .fe-art {
        position: relative; border: 1.5px solid var(--app-ink);
        aspect-ratio: 1 / 1; overflow: hidden; background: var(--app-paper-2);
        background-image: repeating-linear-gradient(135deg, var(--fe-halftone) 0 2px, transparent 2px 13px);
      }
      .fe-art .fe-art-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center; }
      .fe-cap {
        display: grid; grid-template-columns: auto 1fr; gap: 11px; align-items: baseline; padding: 9px 2px 0;
      }
      .fe-cap .n {
        font-family: var(--grotesk); font-weight: 900; font-size: var(--t-label); letter-spacing: .05em; color: var(--app-ink-3); padding-top: 3px;
      }
      .fe-cap .c {
        font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1.32; color: var(--app-ink); text-wrap: pretty;
      }

      /* DIALOGUE — the single place a line of dialogue is printed. */
      .fe-dialogue { margin: 10px 2px 0; border-left: 2px solid var(--app-paper-3); padding: 2px 0 2px 12px; }
      .fe-dialogue .line { margin: 0 0 5px; font-size: var(--t-small); line-height: 1.5; color: var(--app-ink-2); }
      .fe-dialogue .line:last-of-type { margin-bottom: 0; }
      .fe-dialogue .line b { color: var(--accent); font-weight: 800; }
      .fe-dialogue .line em { display: block; margin-top: 2px; font-style: normal; color: var(--app-ink-3); }
      .fe-translate {
        margin-top: 8px; font-size: var(--t-label); font-weight: 700; letter-spacing: .01em;
        color: var(--app-ink-3); border-bottom: 1px solid var(--app-paper-3); padding-bottom: 1px;
      }

      /* PANEL STATUS — a plate-ruled frame with a small press mark, said once. */
      .fe-art.generating { display: grid; place-items: center; }
      .fe-art.generating .press-mark {
        font-size: var(--t-label); font-weight: 900; letter-spacing: .18em; text-transform: uppercase;
        color: var(--app-ink-3); border: 1px solid var(--app-ink-3); padding: 4px 9px;
      }
      .fe-art.delayed { background: var(--app-sheet); display: grid; place-items: center; padding: 18px; }
      .fe-art.delayed .apology { border: 1px dashed var(--app-ink-3); padding: 14px 16px; text-align: center; max-width: 80%; }
      .fe-art.delayed .apology .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .16em; text-transform: uppercase; color: var(--app-red); }
      .fe-art.delayed .apology .m { margin-top: 6px; font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1.3; color: var(--app-ink-2); }

      /* RELATIONSHIP CUE */
      .fe-rel { display: inline-flex; align-items: stretch; gap: 0; border: 1px solid var(--app-ink); background: var(--app-paper); }
      .fe-rel .ava {
        width: 30px; display: grid; place-items: center; background: var(--accent); color: var(--app-paper);
        font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-body); border-right: 1px solid var(--app-ink);
      }
      .fe-rel .meta { padding: 4px 9px 4px 8px; display: flex; flex-direction: column; justify-content: center; }
      .fe-rel .meta .nm { font-size: var(--t-label); font-weight: 800; letter-spacing: .01em; line-height: 1; }
      .fe-rel .meta .rr { display: flex; align-items: center; gap: 6px; margin-top: 3px; }
      .fe-rel .reg { font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; border: 1px solid var(--accent); color: var(--accent); padding: 1px 4px; }
      .fe-rel .reg.tu { background: var(--accent); color: var(--app-paper); }
      .fe-rel .pips { display: flex; gap: 2px; }
      .fe-rel .pips i { width: 4px; height: 9px; background: var(--app-paper-3); }
      .fe-rel .pips i.on { background: var(--accent); }

      /* AUDIO */
      .fe-audio { margin: 14px 18px; border: 1.5px solid var(--app-ink); background: var(--app-ink); color: var(--app-paper); }
      .fe-audio .row { display: flex; align-items: center; gap: 12px; padding: 12px 14px; }
      .fe-audio .play {
        flex: 0 0 auto; width: 42px; height: 42px; border: 1.5px solid var(--app-paper);
        background: var(--app-red); color: var(--app-sheet); display: grid; place-items: center; cursor: pointer; padding: 0;
      }
      .fe-audio .play svg { width: 17px; height: 17px; }
      .fe-audio .lab { min-width: 0; }
      .fe-audio .lab .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .16em; text-transform: uppercase; color: var(--app-yellow); }
      .fe-audio .lab .t { margin-top: 2px; font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1; color: var(--app-paper); }
      .fe-audio .time { margin-left: auto; font-family: var(--fe-mono); font-size: var(--t-label); color: var(--app-paper-3); }
      .fe-audio .scrub { height: 4px; background: rgba(128, 128, 128, .22); position: relative; }
      .fe-audio .scrub > i { position: absolute; inset: 0 auto 0 0; background: var(--app-yellow); }
      .fe-audio .scrub .tick { position: absolute; top: -2px; width: 1px; height: 8px; background: rgba(128, 128, 128, .4); }
      .fe-audio.playing .play { background: var(--app-paper); color: var(--app-ink); }
      .fe-audio .now { padding: 8px 14px 10px; border-top: 1px solid rgba(128, 128, 128, .2); font-size: var(--t-label); line-height: 1.4; color: var(--app-paper-2); }
      .fe-audio .now b { color: var(--app-yellow); font-weight: 800; }

      /* Primary action, soft: pill geometry, solid ink on paper, sentence case. */
      .fe-audio-cta {
        display: flex; align-items: center; justify-content: center; gap: 11px;
        margin: 14px 18px; min-height: 54px; padding: 0 22px; width: calc(100% - 36px);
        border-radius: 999px;
        background: var(--app-ink); color: var(--app-paper); border: 1px solid var(--app-ink);
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em; text-transform: none; text-decoration: none; cursor: pointer;
        transition: background .16s ease, color .16s ease;
      }
      .fe-audio-cta:active { background: var(--app-paper-2); color: var(--app-ink); }
      .fe-audio-cta:disabled { opacity: .5; }
      .fe-audio-cta svg { width: 18px; height: 18px; }

      /* READ-FIRST STUDY TASK */
      /* E. READ-FIRST TASK — one quiet inline action */
      .fe-task { margin: 14px 18px; border: 1.5px solid var(--app-ink); background: var(--app-sheet); }
      .fe-task .th { display: flex; align-items: center; gap: 8px; padding: 9px 13px; border-bottom: 1px solid var(--app-ink); }
      .fe-task .th .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-ink-3); }
      .fe-task .tb { padding: 13px 14px 15px; }
      .fe-task .q { font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1.25; color: var(--app-ink); }

      .fe-correction { margin-top: 12px; border-top: 1px solid var(--app-paper-3); padding-top: 11px; }
      .fe-correction .cap { font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-ink-3); }
      .fe-correction .body { margin-top: 5px; font-size: var(--t-small); line-height: 1.42; color: var(--app-ink-2); }
      .fe-correction del { color: var(--app-red); text-decoration-thickness: 1.5px; }
      .fe-correction ins { text-decoration: none; border-bottom: 2px solid var(--app-red); color: var(--app-ink); }

      /* CLIFFHANGER + CONTINUATION */
      .fe-cliff { margin-top: 18px; background: var(--app-ink); color: var(--app-paper); padding: 20px 18px 18px; text-align: center; }
      .fe-cliff .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .18em; text-transform: uppercase; color: var(--app-yellow); }
      .fe-cliff .q { margin: 11px auto 0; max-width: 300px; font-family: var(--serif); font-style: italic; font-weight: 600; font-size: var(--t-head); line-height: 1.1; color: var(--app-paper); text-wrap: balance; }
      .fe-cliff .demain {
        margin: 15px auto 0; display: inline-flex; align-items: center; gap: 9px;
        border-top: 1px solid rgba(128, 128, 128, .25); border-bottom: 1px solid rgba(128, 128, 128, .25);
        padding: 8px 14px; font-family: var(--serif); font-style: italic; font-size: var(--t-small); line-height: 1.35; color: var(--app-paper-2);
      }
      .fe-cont { margin: 16px 18px; display: grid; gap: 10px; }
      .fe-cont .beat {
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        min-height: 54px; padding: 0 18px; text-decoration: none; border: 1.5px solid var(--app-ink);
        font-size: var(--t-small); font-weight: 900; letter-spacing: .12em; text-transform: uppercase;
      }
      .fe-cont .beat.read { background: var(--app-red); color: var(--app-paper); box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--app-ink) 28%, transparent); }
      .fe-cont .beat.act { background: var(--app-paper); color: var(--app-ink); }
      .fe-cont .beat svg { width: 17px; height: 17px; flex: 0 0 auto; }

      .fe-stamp-filed {
        display: inline-flex; align-items: center; gap: 7px; border: 2px solid var(--app-red); color: var(--app-red);
        font-size: var(--t-label); font-weight: 900; letter-spacing: .2em; text-transform: uppercase; padding: 5px 11px;
        transform: rotate(-4deg); box-shadow: inset 0 0 0 1px var(--app-red);
      }

      .fe-colorable { filter: grayscale(1) contrast(.92); opacity: .82; }
      .fe-filed .fe-colorable { filter: none; opacity: 1; }
      @media (prefers-reduced-motion: no-preference) {
        .fe-filed .fe-colorable { animation: fe-printin var(--fe-printin-dur, .7s) ease forwards; }
      }
      @keyframes fe-printin { from { filter: grayscale(1) contrast(.92); opacity: .82; } to { filter: none; opacity: 1; } }

      /* C. THE ARCHIVE */
      .fe-season { padding: 4px 0 8px; }
      .fe-season-line { margin: 4px 18px 14px; }
      .fe-season-line .cap { display: flex; align-items: baseline; justify-content: space-between; font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--app-ink-3); }
      .fe-season-line .bar { margin-top: 6px; height: 4px; background: var(--app-paper-3); position: relative; }
      .fe-season-line .bar > i { position: absolute; inset: 0 auto 0 0; background: var(--app-ink); }

      .fe-plate {
        position: relative; display: grid; grid-template-columns: 34px 60px 1fr; gap: 12px;
        padding: 14px 18px; border-bottom: 1px solid var(--app-paper-3); align-items: start;
        text-decoration: none; color: var(--app-ink);
      }
      .fe-plate .roman { font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-head); color: var(--app-ink-3); line-height: 1; padding-top: 2px; text-align: center; }
      .fe-plate .thumb {
        position: relative; height: 62px; border: 1px solid var(--app-ink); overflow: hidden; background: var(--app-paper-2);
        background-image: repeating-linear-gradient(135deg, var(--fe-halftone) 0 2px, transparent 2px 9px);
      }
      .fe-plate .thumb img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
      .fe-plate .thumb .port {
        position: absolute; left: 4px; bottom: 4px; width: 20px; height: 20px; border: 1px solid var(--app-ink);
        background: var(--accent); color: var(--app-paper); display: grid; place-items: center;
        font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-small);
      }
      .fe-plate .thumb .slug { position: absolute; top: 3px; right: 3px; font-family: var(--fe-mono); font-size: var(--t-label); color: var(--app-ink-3); }
      .fe-plate .info { min-width: 0; }
      .fe-plate .info .meta { font-size: var(--t-label); font-weight: 900; letter-spacing: .11em; text-transform: uppercase; color: var(--app-ink-3); display: flex; gap: 6px; align-items: center; }
      .fe-plate .info .meta i { width: 2px; height: 2px; background: var(--app-ink-3); }
      .fe-plate .info h3 { margin: 4px 0 0; font-family: var(--serif); font-style: italic; font-weight: 600; font-size: var(--t-lead); line-height: 1.06; }
      .fe-plate .info .choice { margin-top: 6px; font-size: var(--t-label); line-height: 1.35; color: var(--app-ink-2); }
      .fe-plate .info .choice b { display: block; font-size: var(--t-label); font-weight: 900; letter-spacing: .11em; text-transform: uppercase; color: var(--app-ink-3); margin-bottom: 1px; }
      .fe-plate .info .choice em { font-style: italic; font-family: var(--serif); font-size: var(--t-small); color: var(--app-ink); }
      .fe-plate .info .outcome { margin-top: 6px; padding-left: 9px; border-left: 2px solid var(--accent); font-size: var(--t-small); line-height: 1.32; color: var(--app-ink-2); }
      .fe-plate .filed { position: absolute; top: 12px; right: 16px; font-size: var(--t-label); font-weight: 900; letter-spacing: .16em; text-transform: uppercase; color: var(--app-ink-3); border: 1px solid var(--app-ink-3); padding: 2px 5px; transform: rotate(-3deg); }
      .fe-plate.current { background: var(--app-sheet); }
      .fe-plate.current::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--app-red); }
      .fe-plate.current .filed { color: var(--app-red); border-color: var(--app-red); }
      .fe-plate.up { opacity: .62; }
      .fe-plate.up .roman, .fe-plate.up .thumb .port { color: var(--app-ink-3); }

      .fe-arc-head { padding: 15px 18px 12px; border-bottom: 1px solid var(--app-ink); }
      .fe-arc-head .kicker { font-size: var(--t-label); font-weight: 900; letter-spacing: .2em; text-transform: uppercase; color: var(--app-red); }
      .fe-arc-head h2 { margin: 5px 0 0; font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-head); line-height: 1; }
      .fe-arc-head .sub { margin-top: 6px; font-size: var(--t-small); color: var(--app-ink-3); }
      .fe-cast-entry {
        display: flex; align-items: center; justify-content: space-between; gap: 10px;
        margin: 14px 18px; padding: 12px 15px; border: 1.5px solid var(--app-ink); background: var(--app-paper);
        box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--app-ink) 18%, transparent); text-decoration: none; color: var(--app-ink);
      }
      .fe-cast-entry .l .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-ink-3); }
      .fe-cast-entry .l .t { margin-top: 3px; font-family: var(--serif); font-style: italic; font-size: var(--t-lead); }
      .fe-cast-entry .faces { display: flex; }
      .fe-cast-entry .faces i { width: 26px; height: 26px; border: 1px solid var(--app-ink); display: grid; place-items: center; color: var(--app-paper); font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-small); margin-left: -7px; overflow: hidden; }
      .fe-cast-entry .faces i img { width: 100%; height: 100%; object-fit: cover; }

      .fe-arc-empty { padding: 40px 24px; text-align: center; }
      .fe-arc-empty .mark { width: 14px; height: 14px; background: var(--app-ink); margin: 0 auto 16px; }
      .fe-arc-empty h3 { font-family: var(--serif); font-style: italic; font-weight: 600; font-size: var(--t-head); line-height: 1.1; margin: 0 auto; max-width: 250px; }
      .fe-arc-empty p { margin: 12px auto 0; max-width: 240px; font-size: var(--t-small); line-height: 1.5; color: var(--app-ink-2); }
      .fe-arc-empty .cta {
        display: inline-flex; align-items: center; gap: 10px; margin-top: 20px; min-height: 50px; padding: 0 20px;
        background: var(--app-red); color: var(--app-paper); border: 1.5px solid var(--app-ink); box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--app-ink) 28%, transparent);
        font-size: var(--t-small); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; text-decoration: none;
      }
      .fe-arc-empty .cta svg { width: 16px; height: 16px; }

      /* D. THE CAST */
      .fe-cast-head { padding: 15px 18px 12px; text-align: center; border-bottom: 3px double var(--app-ink); }
      .fe-cast-head .kicker { font-size: var(--t-label); font-weight: 900; letter-spacing: .22em; text-transform: uppercase; color: var(--app-red); }
      .fe-cast-head h2 { margin: 5px 0 0; font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-head); line-height: 1; }
      .fe-cast-head .sub { margin-top: 6px; font-size: var(--t-label); color: var(--app-ink-3); font-style: italic; font-family: var(--serif); }

      .fe-cast-card { margin: 14px 18px; border: 1.5px solid var(--app-ink); background: var(--app-paper); }
      .fe-cast-card .top { display: grid; grid-template-columns: 54px 1fr auto; gap: 12px; padding: 13px 14px; align-items: center; }
      .fe-cast-card .port {
        position: relative; width: 54px; height: 54px; border: 1.5px solid var(--app-ink); background: var(--accent); color: var(--app-paper);
        display: grid; place-items: center; font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-head); overflow: hidden;
      }
      .fe-cast-card .port img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
      .fe-cast-card .port .slug { position: absolute; bottom: 2px; right: 3px; font-family: var(--fe-mono); font-size: var(--t-label); color: rgba(255,255,255,.7); }
      .fe-cast-card .id { min-width: 0; }
      .fe-cast-card .id .nm { font-family: var(--serif); font-style: italic; font-weight: 600; font-size: var(--t-lead); line-height: 1; }
      .fe-cast-card .id .role { margin-top: 3px; font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-3); }
      .fe-cast-card .id .role b { color: var(--accent); }

      .fe-reg { display: inline-flex; flex-direction: column; align-items: center; gap: 3px; border: 2px solid var(--accent); padding: 5px 9px 4px; transform: rotate(2deg); }
      .fe-reg .r { font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-lead); color: var(--accent); line-height: .9; }
      .fe-reg .l { font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); }
      .fe-reg.vous { border-color: var(--app-ink-3); transform: rotate(-1deg); }
      .fe-reg.vous .r, .fe-reg.vous .l { color: var(--app-ink-3); }

      .fe-close { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-top: 1px solid var(--app-paper-3); }
      .fe-close .cap { font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--app-ink-3); }
      .fe-close .pips { display: flex; gap: 3px; margin-left: auto; }
      .fe-close .pips i { width: 8px; height: 13px; background: var(--app-paper-3); border: 1px solid transparent; }
      .fe-close .pips i.on { background: var(--accent); }
      .fe-close .switch { font-size: var(--t-label); font-weight: 800; letter-spacing: .04em; color: var(--app-ink-3); }
      .fe-close .switch b { color: var(--accent); }

      .fe-ledger { border-top: 1px solid var(--app-paper-3); padding: 11px 14px 12px; }
      .fe-ledger .cap { font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-ink-3); }
      .fe-ledger .cb { margin-top: 7px; display: flex; flex-wrap: wrap; gap: 5px; }
      .fe-ledger .cb span { font-size: var(--t-label); font-weight: 700; border: 1px solid var(--app-ink-3); padding: 2px 6px; color: var(--app-ink-2); background: var(--app-sheet); }
      .fe-ledger .last { margin-top: 9px; font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1.34; color: var(--app-ink-2); }
      .fe-ledger .last b { color: var(--app-ink); font-style: normal; font-weight: 700; }
      .fe-ledger .none { margin-top: 7px; font-size: var(--t-small); font-style: italic; font-family: var(--serif); color: var(--app-ink-3); }

      .fe-me { margin: 14px 18px; border: 1.5px solid var(--app-ink); background: var(--app-ink); color: var(--app-paper); }
      .fe-me .top { display: grid; grid-template-columns: 54px 1fr auto; gap: 12px; padding: 13px 14px; align-items: center; }
      .fe-me .port { position: relative; width: 54px; height: 54px; border: 1.5px solid var(--app-paper); background: var(--app-paper); color: var(--app-ink); display: grid; place-items: center; font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-head); overflow: hidden; }
      .fe-me .port img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
      .fe-me .id .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-yellow); }
      .fe-me .id .nm { margin-top: 3px; font-family: var(--serif); font-style: italic; font-size: var(--t-lead); line-height: 1; }
      .fe-me .customise { min-height: 44px; padding: 0 18px; border-radius: 999px; border: 1px solid var(--app-paper); background: transparent; color: var(--app-paper); font-size: var(--t-small); font-weight: 600; letter-spacing: .01em; text-transform: none; cursor: pointer; transition: background .16s ease, color .16s ease; }
      .fe-me .customise:active { background: var(--app-paper-2); color: var(--app-ink); }
      .fe-me .ref { padding: 0 14px 13px; }
      .fe-me .ref .slug { font-family: var(--fe-mono); font-size: var(--t-label); color: var(--app-paper-3); border: 1px solid rgba(128,128,128,.3); padding: 8px 10px; line-height: 1.5; }
      .fe-me .body { padding: 0 14px 14px; display: grid; gap: 8px; }

      /* EMPTY / FIRST-RUN */
      .fe-firstrun { padding: 44px 26px 34px; text-align: center; }
      .fe-firstrun .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .2em; text-transform: uppercase; color: var(--app-red); }
      .fe-firstrun h2 { margin: 14px auto 0; max-width: 280px; font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-head); line-height: 1.04; }
      .fe-firstrun p { margin: 14px auto 0; max-width: 250px; font-size: var(--t-small); line-height: 1.5; color: var(--app-ink-2); }
      .fe-firstrun .cta {
        display: inline-flex; align-items: center; gap: 10px; margin-top: 22px; min-height: 52px; padding: 0 22px;
        background: var(--app-red); color: var(--app-paper); border: 1.5px solid var(--app-ink); box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--app-ink) 28%, transparent);
        font-size: var(--t-small); font-weight: 900; letter-spacing: .13em; text-transform: uppercase; text-decoration: none;
      }
      .fe-firstrun .cta svg { width: 17px; height: 17px; }

      /* LOADING SKELETON + ERROR */
      .fe-skel { padding: 16px 18px; }
      .fe-skel .l { background: var(--app-paper-3); height: 12px; margin-bottom: 9px; position: relative; overflow: hidden; }
      .fe-skel .art { height: 150px; border: 1.5px solid var(--app-paper-3); background: var(--app-paper-2); margin: 12px 0; position: relative; overflow: hidden; }
      @media (prefers-reduced-motion: no-preference) {
        .fe-skel .art::after, .fe-skel .l::after {
          content: ""; position: absolute; inset: 0;
          background: linear-gradient(100deg, transparent 20%, rgba(255,255,255,.35) 50%, transparent 80%);
          animation: fe-shimmer 1.4s linear infinite;
        }
      }
      @keyframes fe-shimmer { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
      .fe-skel .press { text-align: center; font-family: var(--fe-mono); font-size: var(--t-label); letter-spacing: .1em; color: var(--app-ink-3); margin-top: 6px; }

      .fe-notice { margin: 16px 18px; border: 1.5px solid var(--app-red); background: var(--app-sheet); }
      .fe-notice .nh { display: flex; align-items: center; gap: 8px; padding: 9px 13px; border-bottom: 1px solid var(--app-red); }
      .fe-notice .nh .tri { width: 0; height: 0; border-style: solid; border-width: 0 6px 11px 6px; border-color: transparent transparent var(--app-red) transparent; }
      .fe-notice .nh .t { font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-red); }
      .fe-notice .nb { padding: 12px 14px 14px; }
      .fe-notice .nb .m { font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1.3; color: var(--app-ink); }
      /* Outlined action: same pill, transparent fill, ink keyline. */
      .fe-notice .retry { margin-top: 11px; display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 44px; border-radius: 999px; border: 1px solid var(--app-ink); background: transparent; padding: 0 18px; font-size: var(--t-small); font-weight: 600; letter-spacing: .01em; text-transform: none; color: var(--app-ink); cursor: pointer; transition: background .16s ease, color .16s ease; }
      .fe-notice .retry:active { background: var(--app-paper-2); color: var(--app-ink); }
      .fe-notice .retry svg { width: 13px; height: 13px; }
    `}</style>
  );
}
