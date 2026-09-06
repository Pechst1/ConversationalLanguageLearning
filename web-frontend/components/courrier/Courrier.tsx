/* Atelier — LE COURRIER · Missions as the journal's correspondence desk.
   1:1 port of the design package (courrier-parts.jsx / courrier.css, the
   "Atelier Le Courrier" canvas) into the app's token system. Every component
   maps onto a real API field; the migration note lives in
   docs/overhaul-missions.md §5. The shared "press" primitives (LuStamp,
   LuNotice, the stamp/skeleton keyframes) are reused from LaUne so the two
   surfaces stay one publication; only the correspondence-desk parts (cr-*)
   are defined here. Bottom tab bar (PhoneProductNav) is untouched. */

import React, { useState } from 'react';
import Link from 'next/link';
import { IcoArrow, IcoCheck, LuStamp } from '@/components/laune/LaUne';

/* ---------- icons ---------- */
export function IcoBack() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
      <path d="M20 12H5M11 6l-6 6 6 6" />
    </svg>
  );
}
export function IcoMic() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3.2" />
    </svg>
  );
}
export function IcoTrad() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M4 9h9M8.5 5.5V9M6 9c0 3.4 3 6 6.5 6M11 9c-.6 2.6-2.8 5-6 6" />
      <path d="M14.5 19l3.2-8 3.3 8M15.6 16.6h4.3" />
    </svg>
  );
}
export function IcoStop() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <rect x="7.5" y="7.5" width="9" height="9" />
    </svg>
  );
}

/* ---------- lazy translate glyph (frame + character voice) ----------
   Wraps apiService.translateToEnglish; English is out-of-fiction chrome, so
   the reveal is plain graphite text, never set as the character's line. */
export function CrTranslate({
  translate,
  variant = 'glyph',
  label = 'Traduire',
}: {
  translate: () => Promise<string>;
  variant?: 'glyph' | 'text';
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [text, setText] = useState('');

  const reveal = async () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (text || loading) return;
    setLoading(true);
    try {
      setText(await translate());
    } catch (error) {
      console.error(error);
      setText('Traduction indisponible.');
    } finally {
      setLoading(false);
    }
  };

  if (variant === 'text') {
    return (
      <div className="cr-trad-text">
        <button type="button" onClick={reveal} aria-label={open ? 'Masquer la traduction' : 'Voir la traduction'}>
          {open ? 'Masquer' : label}
        </button>
        {open && <p>{loading ? 'Traduction…' : text || 'Traduction indisponible.'}</p>}
      </div>
    );
  }
  return (
    <>
      <button className="cr-trad" type="button" onClick={reveal} aria-label={open ? 'Masquer la traduction' : 'Voir la traduction'}>
        <IcoTrad />
      </button>
      {open && <p className="cr-trad-reveal">{loading ? 'Traduction…' : text || 'Traduction indisponible.'}</p>}
    </>
  );
}

/* ---------- desk header ----------
   kicker  ← mission_format / serial_thread_id ("Le Feuilleton · Acte N")
   title   ← mission title (serif italic headline)
   cadence ← cadence === 'weekly' → "Courrier de la semaine"
   status  ← mission status → printed marginalia, never a pill */
export function CrDesk({
  kicker = 'Le Courrier',
  blue = false,
  title,
  cadence = null,
  status = 'open',
  statusLine,
  onBack,
  backHref = '/atelier',
  backLabel = 'La Une',
}: {
  kicker?: string;
  blue?: boolean;
  title: string;
  cadence?: string | null;
  status?: 'open' | 'done';
  statusLine: string;
  onBack?: (event: React.MouseEvent<HTMLAnchorElement>) => void;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <header className="cr-desk">
      <div className="backrow">
        <a className="cr-back" href={backHref} onClick={onBack}><IcoBack /> {backLabel}</a>
        {cadence && <span className="cr-cadence">{cadence}</span>}
      </div>
      <div className={'kicker' + (blue ? ' blue' : '')}>{kicker}</div>
      <h1>{title}</h1>
      <div className="marge">
        <span className={'sq ' + (status === 'done' ? 'done' : 'open')} />
        <span>{statusLine}</span>
      </div>
    </header>
  );
}

/* ---------- the situation ----------
   frame ← slim_payload.frame · ask ← slim_payload.ask · translate = glyph */
export function CrSituation({
  frame,
  ask,
  translate,
}: {
  frame: string;
  ask: string;
  translate?: () => Promise<string>;
}) {
  return (
    <section className="cr-sit-wrap">
      <div className="cr-sit">
        <div>
          <p className="frame">{frame}</p>
          {ask && <p className="ask"><b>On attend de vous</b>{ask}</p>}
        </div>
        {translate && <CrTranslate translate={translate} />}
      </div>
    </section>
  );
}

/* ---------- P.S. ← slim_payload.twist (optional — omit when absent) ---------- */
export function CrPS({ text }: { text?: string | null }) {
  if (!text) return null;
  return <p className="cr-ps">P.S. — {text}</p>;
}

/* ---------- word ribbon ← target_vocabulary (≤3) ---------- */
export function CrRibbon({ words = [] }: { words?: { t: string; used?: boolean }[] }) {
  if (!words.length) return null;
  return (
    <div className="cr-ribbon">
      <span className="k">À placer :</span>
      {words.map((w) => (
        <span key={w.t} className={'w' + (w.used ? ' used' : '')}>{w.t}</span>
      ))}
    </div>
  );
}

/* ---------- dépêche slip ← a conversation turn (name, time, text) ---------- */
export function CrSlip({
  who,
  time,
  you = false,
  sent = false,
  translate,
  children,
}: {
  who: string;
  time?: string;
  you?: boolean;
  sent?: boolean;
  translate?: () => Promise<string>;
  children: React.ReactNode;
}) {
  return (
    <div className={'cr-slip' + (you ? ' you' : '')}>
      {you && sent && <span className="cr-post" aria-hidden="true">P</span>}
      <div className="head"><b>{who}</b>{time && <span className="t">{time}</span>}</div>
      <div className="txt">{children}</div>
      {translate && <CrTranslate translate={translate} variant="text" />}
    </div>
  );
}

/* ---------- repair note ← turn.correction (full rewrite, edits, persistence) ---------- */
export function CrRepair({
  correctedAnswer,
  lines,
  savedCount = 0,
}: {
  correctedAnswer?: string;
  lines: { fixed?: string; why?: string }[];
  savedCount?: number;
}) {
  if (!correctedAnswer && !lines.length) return null;
  return (
    <aside className="cr-repair">
      <div className="k">Correction</div>
      {correctedAnswer && <div className="answer">{correctedAnswer}</div>}
      {lines.length > 0 && <div className="edits">À retenir</div>}
      {lines.map((line, index) => (
        <React.Fragment key={index}>
          {line.fixed && <div className="fix">{line.fixed}</div>}
          {line.why && <div className="why">{line.why}</div>}
        </React.Fragment>
      ))}
      {savedCount > 0 && (
        <div className="saved">
          {savedCount} réparation{savedCount === 1 ? '' : 's'} enregistrée{savedCount === 1 ? '' : 's'}
        </div>
      )}
    </aside>
  );
}

/* ---------- phone memo ← voicemail / phone_call payload ----------
   "pendant votre absence" slip carrying the transcribed voicemail. */
export function CrMemo({
  rows = [],
  transcript,
  stamp = null,
  translate,
}: {
  rows?: [string, string][];
  transcript: string;
  stamp?: string | null;
  translate?: () => Promise<string>;
}) {
  return (
    <div className="cr-memo">
      {stamp && <LuStamp word={stamp} tone="red" sm tilt={5} style={{ top: 8, right: 8 }} />}
      <div className="mh"><b>Pendant votre absence</b><span>Message téléphonique</span></div>
      {rows.map((r) => (
        <div className="cr-mrow" key={r[0]}><span className="l">{r[0]}</span><span className="v">{r[1]}</span></div>
      ))}
      <div className="cr-mmsg">
        <div className="l">Transcription automatique<span className="ln" /></div>
        <p>« {transcript} »</p>
        {translate && <CrTranslate translate={translate} variant="text" />}
      </div>
    </div>
  );
}

/* ---------- live call strip ← mission_format 'phone_call' ---------- */
export function CrCallStrip({
  live = false,
  who,
  sub,
}: {
  live?: boolean;
  who: string;
  sub: string;
}) {
  return (
    <div className={'cr-call' + (live ? ' live' : '')}>
      <span className="dot" aria-hidden="true" />
      <span className="tx"><b>{who}</b><span>{sub}</span></span>
    </div>
  );
}

/* ---------- composer bar (per-format) ----------
   quick ← quick_replies · cta ← "Envoyer" / "Déposer" / "Parler"
   finish gate: "Envoie d'abord." until ≥1 learner turn sent */
export function CrComposer({
  quick = [],
  onQuick,
  cta = 'Envoyer',
  onSubmit,
  sending = false,
  canSubmit = true,
  canFinish = false,
  onFinish,
  finishing = false,
  hideFinish = false,
  finishLabel = 'Terminer',
  children,
}: {
  quick?: string[];
  onQuick?: (value: string) => void;
  cta?: string;
  onSubmit?: (event: React.FormEvent) => void;
  sending?: boolean;
  canSubmit?: boolean;
  canFinish?: boolean;
  onFinish?: () => void;
  finishing?: boolean;
  hideFinish?: boolean;
  finishLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <form className="cr-composer" onSubmit={onSubmit}>
      {quick.length > 0 && (
        <div className="cr-quick">
          {quick.map((q) => (
            <button type="button" key={q} onClick={() => onQuick?.(q)}>{q}</button>
          ))}
        </div>
      )}
      {children}
      <div className={'cr-actions' + (hideFinish ? ' solo' : '')}>
        <button type="submit" className="cr-cta" disabled={!canSubmit || sending} aria-busy={sending || undefined}>
          {cta} <IcoArrow />
        </button>
        {!hideFinish && (
          <button type="button" className="cr-finish" disabled={!canFinish || finishing} onClick={onFinish} aria-busy={finishing || undefined}>
            {finishLabel}
          </button>
        )}
      </div>
      {!hideFinish && !canFinish && <div className="cr-gate">Envoyez d’abord une réponse.</div>}
    </form>
  );
}

/* ---------- resolution ghost link/button ---------- */
export function CrGhost({
  children,
  href,
  onClick,
  quiet = false,
  primary = false,
  disabled = false,
}: {
  children: React.ReactNode;
  href?: string;
  onClick?: (event: React.MouseEvent) => void;
  quiet?: boolean;
  primary?: boolean;
  disabled?: boolean;
}) {
  const cls = primary ? 'cr-cta' : 'cr-ghost' + (quiet ? ' quiet' : '');
  if (href) {
    return <Link className={cls} href={href} onClick={onClick}>{children}{primary && <IcoArrow />}</Link>;
  }
  return (
    <button type="button" className={cls} onClick={onClick} disabled={disabled}>
      {children}{primary && <IcoArrow />}
    </button>
  );
}

export { IcoArrow, IcoCheck };

/* ============================================================
   Styles — courrier.css ported into the app token system.
   The fixed 390px artboard becomes the phone-shell sizing; the
   design's `.cr.dark` remap is dropped because the `--app-*`
   tokens are already theme-aware (globals.css data-theme). The
   shared stamp/skeleton primitives + keyframes come from
   <LaUneStyles/>, mounted alongside this on the page.
   ============================================================ */
export function CourrierStyles() {
  return (
    <style jsx global>{`
      .cr {
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
        /* clear the fixed PhoneProductNav so the composer / resolution never
           hides behind it (matches the old page's bottom-nav reservation). */
        padding-bottom: var(--phone-bottom-nav-space);
        background-image:
          radial-gradient(circle at 18% 22%, rgba(20, 17, 13, 0.03) 0, transparent 0.7px),
          radial-gradient(circle at 71% 56%, rgba(20, 17, 13, 0.03) 0, transparent 0.7px);
        background-size: 7px 7px, 11px 11px;
      }
      .cr * { box-sizing: border-box; }
      /* :where() keeps the reset at zero specificity; as plain element
         selectors these outranked every component class. */
      .cr :where(a, button) { font: inherit; color: inherit; text-align: inherit; }
      .cr :where(button) { border: 0; background: transparent; padding: 0; cursor: pointer; }
      .cr-page { flex: 1 1 auto; padding: 0 18px 18px; }

      /* 1 · LE PUPITRE — desk header */
      .cr-desk { padding: 6px 0 14px; border-bottom: 3px double var(--ink); }
      .cr-desk .backrow {
        display: flex; align-items: center; justify-content: space-between;
        min-height: 44px; margin-bottom: 2px;
      }
      .cr-back {
        display: inline-flex; align-items: center; gap: 7px;
        min-height: 44px; padding-right: 12px;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase;
        color: var(--ink-2); text-decoration: none;
      }
      .cr-back svg { width: 14px; height: 14px; }
      .cr-cadence {
        flex: 0 0 auto;
        border: 1.5px solid var(--blue); color: var(--blue);
        font-size: var(--t-label); font-weight: 900; letter-spacing: .15em; text-transform: uppercase;
        padding: 4px 8px 3px; transform: rotate(2deg); white-space: nowrap;
      }
      .cr-desk .kicker {
        display: flex; align-items: center; gap: 8px; white-space: nowrap;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .18em;
        text-transform: uppercase; color: var(--red);
      }
      .cr-desk .kicker.blue { color: var(--blue); }
      .cr-desk .kicker .tail { flex: 1 1 auto; min-width: 10px; height: 1px; background: var(--paper-3); }
      .cr-desk h1 {
        margin: 7px 0 0; font-family: var(--serif); font-style: italic;
        font-weight: 600; font-size: var(--t-head); line-height: 1.04; color: var(--ink);
        text-wrap: pretty;
      }
      .cr-desk .marge {
        margin-top: 9px; display: flex; align-items: center; gap: 8px;
        font-size: var(--t-label); font-weight: 800; letter-spacing: .12em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .cr-desk .marge .sq { width: 7px; height: 7px; flex: 0 0 auto; border: 1px solid var(--ink); }
      .cr-desk .marge .sq.open { background: var(--yellow); }
      .cr-desk .marge .sq.done { background: var(--ink); }

      /* 2 · LA SITUATION */
      .cr-sit { display: grid; grid-template-columns: minmax(0, 1fr) 44px; gap: 8px; padding: 14px 0 0; }
      .cr-sit .frame {
        margin: 0; font-family: var(--serif); font-style: italic;
        font-size: var(--t-body); line-height: 1.32; color: var(--ink); text-wrap: pretty;
      }
      .cr-sit .ask { margin: 8px 0 0; font-size: var(--t-small); line-height: 1.45; color: var(--ink-2); }
      .cr-sit .ask b {
        display: block; margin-bottom: 2px;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .15em;
        text-transform: uppercase; color: var(--red);
      }
      .cr-trad {
        align-self: start; width: 44px; height: 44px;
        border: 1px solid var(--paper-3); background: var(--paper); color: var(--ink-2);
        display: grid; place-items: center;
      }
      .cr-trad svg { width: 16px; height: 16px; }
      .cr-trad-reveal {
        margin: 10px 0 0; font-size: var(--t-small); line-height: 1.4; color: var(--ink-2);
      }
      .cr-trad-text { margin-top: 8px; }
      .cr-trad-text button {
        font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase;
        color: var(--ink-3); border-bottom: 1px solid var(--paper-3); padding-bottom: 1px;
      }
      .cr-trad-text p { margin: 7px 0 0; font-size: var(--t-small); line-height: 1.4; color: var(--ink-2); }

      /* word ribbon */
      .cr-ribbon {
        margin-top: 12px; padding: 9px 0;
        border-top: 1px solid var(--paper-3); border-bottom: 1px solid var(--paper-3);
        display: flex; align-items: baseline; gap: 6px 12px; flex-wrap: wrap;
      }
      .cr-ribbon .k {
        font-size: var(--t-label); font-weight: 900; letter-spacing: .15em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .cr-ribbon .w {
        font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1;
        color: var(--ink); border-bottom: 1px dotted var(--ink-3); padding-bottom: 2px;
      }
      .cr-ribbon .w.used { border-bottom: 2px solid var(--ink); }
      .cr-ribbon .w.used::after { content: " ·"; color: var(--red); font-weight: 700; }

      /* 3 · LA DÉPÊCHE — message slips */
      .cr-thread { padding: 14px 0 4px; display: grid; gap: 12px; }
      .cr-slip {
        position: relative; width: 88%;
        border: 1px solid var(--ink); background: var(--paper);
        padding: 10px 12px 12px;
      }
      .cr-slip .head {
        display: flex; align-items: baseline; justify-content: space-between; gap: 10px;
        padding-bottom: 6px; margin-bottom: 8px;
        border-bottom: 1px solid var(--paper-3);
        font-size: var(--t-label); font-weight: 900; letter-spacing: .13em;
        text-transform: uppercase; color: var(--ink-2);
      }
      .cr-slip .head .t { font-weight: 800; letter-spacing: .06em; color: var(--ink-3); font-variant-numeric: tabular-nums; white-space: nowrap; }
      .cr-slip .txt { font-family: var(--serif); font-size: var(--t-body); line-height: 1.38; color: var(--ink); white-space: pre-wrap; }
      .cr-slip.you { margin-left: auto; background: var(--sheet); }
      .cr-post {
        position: absolute; top: -10px; right: -7px; z-index: 2;
        width: 26px; height: 30px; transform: rotate(4deg);
        border: 1.5px solid var(--red); color: var(--red); background: var(--sheet);
        box-shadow: inset 0 0 0 2.5px var(--sheet), inset 0 0 0 3.5px var(--red);
        display: grid; place-items: center;
        font-family: var(--serif); font-style: italic; font-weight: 700; font-size: var(--t-small);
        pointer-events: none;
      }
      .cr-ps {
        width: 88%; margin-top: 12px; padding-left: 11px; border-left: 2px solid var(--yellow);
        font-family: var(--serif); font-style: italic;
        font-size: var(--t-small); line-height: 1.42; color: var(--ink-2);
      }
      .cr-typing {
        width: fit-content; max-width: 88%;
        display: inline-flex; align-items: center; gap: 8px;
        border-left: 2px solid var(--blue); padding: 5px 9px;
        font-family: var(--serif); font-style: italic;
        font-size: var(--t-small); line-height: 1.3; color: var(--ink-2);
      }
      .cr-typing .rollers { display: inline-flex; gap: 3px; }
      .cr-typing .rollers i { width: 4px; height: 4px; background: currentColor; }
      @media (prefers-reduced-motion: no-preference) {
        .cr.motion .cr-typing .rollers i { animation: lu-roll 1.1s ease-in-out infinite; }
        .cr.motion .cr-typing .rollers i:nth-child(2) { animation-delay: .18s; }
        .cr.motion .cr-typing .rollers i:nth-child(3) { animation-delay: .36s; }
      }

      /* repair note — graphite pencil */
      .cr-repair {
        width: 88%; margin: -4px 0 0 auto;
        padding: 7px 11px 8px; border-left: 2px solid var(--ink-3);
      }
      .cr-repair .k {
        font-size: var(--t-label); font-weight: 900; letter-spacing: .17em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .cr-repair .answer {
        margin-top: 5px; font-family: var(--serif); font-style: italic;
        font-size: var(--t-body); line-height: 1.42; color: var(--ink);
      }
      .cr-repair .edits {
        margin-top: 8px; padding-top: 7px; border-top: 1px solid var(--paper-3);
        font-size: var(--t-label); font-weight: 900; letter-spacing: .15em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .cr-repair .fix { margin-top: 3px; font-family: var(--serif); font-style: italic; font-size: var(--t-body); color: var(--ink); }
      .cr-repair .why { margin-top: 3px; font-size: var(--t-label); line-height: 1.42; color: var(--ink-2); }
      .cr-repair .saved { margin-top: 5px; font-size: var(--t-label); font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-3); }
      .cr-reason {
        margin: 10px 0 2px; padding-left: 10px; border-left: 1px solid var(--ink-3);
        color: var(--ink-3); font-family: var(--serif); font-size: var(--t-small);
        font-style: italic; line-height: 1.42;
      }

      /* 6 · LE MESSAGE TÉLÉPHONIQUE — memo */
      .cr-memo { position: relative; margin-top: 14px; border: 1.5px solid var(--ink); background: var(--paper); }
      .cr-memo .mh { text-align: center; padding: 10px 10px 9px; border-bottom: 1.5px solid var(--ink); }
      .cr-memo .mh b { display: block; font-size: var(--t-small); font-weight: 900; letter-spacing: .22em; text-transform: uppercase; }
      .cr-memo .mh span { display: block; margin-top: 3px; font-size: var(--t-label); font-weight: 800; letter-spacing: .15em; text-transform: uppercase; color: var(--ink-3); }
      .cr-mrow { display: flex; align-items: baseline; gap: 10px; padding: 8px 12px 7px; border-bottom: 1px solid var(--paper-3); }
      .cr-mrow .l { flex: 0 0 96px; font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--ink-3); }
      .cr-mrow .v { font-family: var(--serif); font-style: italic; font-size: var(--t-body); color: var(--ink); }
      .cr-mmsg { padding: 10px 12px 13px; }
      .cr-mmsg .l { display: flex; align-items: center; gap: 8px; font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--ink-3); }
      .cr-mmsg .l .ln { flex: 1 1 auto; height: 1px; background: var(--paper-3); }
      .cr-mmsg p { margin: 8px 0 0; font-family: var(--serif); font-size: var(--t-body); line-height: 1.45; color: var(--ink); }

      /* live call strip */
      .cr-call {
        margin-top: 12px; display: flex; align-items: center; gap: 12px;
        border: 1.5px solid var(--ink); background: var(--paper); padding: 11px 13px;
      }
      .cr-call .dot { flex: 0 0 auto; width: 9px; height: 9px; border-radius: 50%; background: var(--red); }
      @media (prefers-reduced-motion: no-preference) {
        .cr.motion .cr-call.live .dot { animation: lu-roll 1.2s ease-in-out infinite; }
      }
      .cr-call .tx { min-width: 0; }
      .cr-call .tx b { display: block; font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; }
      .cr-call .tx span { display: block; margin-top: 2px; font-size: var(--t-label); color: var(--ink-2); font-variant-numeric: tabular-nums; }

      /* mic composer states */
      .cr-mic { margin-top: 12px; display: grid; gap: 10px; }
      .cr-mic .bar {
        display: flex; align-items: center; justify-content: center; gap: 12px;
        width: 100%; min-height: 54px; padding: 0 22px; border-radius: 999px;
        border: 1px solid var(--ink);
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em; text-transform: none;
        cursor: pointer;
        transition: background .16s ease, color .16s ease;
      }
      .cr-mic .bar:disabled { cursor: progress; opacity: .5; }
      .cr-mic .bar svg { width: 17px; height: 17px; flex: 0 0 auto; }
      .cr-mic .bar.idle { background: var(--ink); color: var(--paper); }
      .cr-mic .bar.idle:active { background: var(--paper-2); color: var(--ink); }
      /* Live recording keeps the ink fill (contrast) and takes a red keyline —
         the wave and timer inside carry the "we are rolling" signal. */
      .cr-mic .bar.rec { background: var(--ink); color: var(--paper); border-color: var(--red); box-shadow: 0 0 0 2px color-mix(in srgb, var(--red) 40%, transparent); }
      .cr-mic .timer { font-variant-numeric: tabular-nums; letter-spacing: .08em; }
      .cr-mic .wave { display: flex; align-items: center; gap: 3px; height: 16px; }
      .cr-mic .wave i { width: 3px; height: 14px; background: currentColor; transform: scaleY(.35); }
      @media (prefers-reduced-motion: no-preference) {
        .cr.motion .cr-mic .bar.rec .wave i { animation: cr-wave .9s ease-in-out infinite; }
        .cr.motion .cr-mic .bar.rec .wave i:nth-child(2) { animation-delay: .12s; }
        .cr.motion .cr-mic .bar.rec .wave i:nth-child(3) { animation-delay: .24s; }
        .cr.motion .cr-mic .bar.rec .wave i:nth-child(4) { animation-delay: .36s; }
        .cr.motion .cr-mic .bar.rec .wave i:nth-child(5) { animation-delay: .48s; }
      }
      @keyframes cr-wave { 0%, 100% { transform: scaleY(.3); } 50% { transform: scaleY(1); } }
      .cr-mic .fallback {
        justify-self: center; min-height: 44px; padding: 0 6px;
        display: inline-flex; align-items: center;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase;
        color: var(--ink-2); border-bottom: 1.5px solid var(--ink-3);
      }
      .cr-transcribe {
        display: flex; align-items: center; justify-content: center; gap: 12px;
        min-height: 56px; padding: 0 16px;
        border: 1.5px dashed var(--ink-3); background: var(--paper);
        font-size: var(--t-label); font-weight: 900; letter-spacing: .15em;
        text-transform: uppercase; color: var(--ink-2);
      }
      .cr-transcribe .rollers { display: flex; gap: 4px; }
      .cr-transcribe .rollers i { width: 5px; height: 5px; background: var(--ink); }
      @media (prefers-reduced-motion: no-preference) {
        .cr.motion .cr-transcribe .rollers i { animation: lu-roll 1.1s ease-in-out infinite; }
        .cr.motion .cr-transcribe .rollers i:nth-child(2) { animation-delay: .18s; }
        .cr.motion .cr-transcribe .rollers i:nth-child(3) { animation-delay: .36s; }
      }
      .cr-mic-problem { font-size: var(--t-small); line-height: 1.4; color: var(--red); }

      /* 7 · LE COMPOSTEUR */
      .cr-composer { flex: 0 0 auto; border-top: 1px solid var(--ink); background: var(--paper); padding: 11px 16px 13px; }
      .cr-quick { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
      .cr-quick button {
        min-height: 44px; padding: 8px 12px;
        border: 1px solid var(--ink); background: var(--sheet);
        font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1.15;
        color: var(--ink);
      }
      .cr-quick button:active { background: var(--paper-2); }
      .cr-label {
        display: block; margin-bottom: 6px;
        font-size: var(--t-label); font-weight: 900; letter-spacing: .15em; text-transform: uppercase; color: var(--ink-3);
      }
      .cr-instruction { margin: 0 0 8px; font-size: var(--t-small); line-height: 1.4; color: var(--ink-2); }
      .cr-draft {
        display: block; width: 100%; min-height: 54px; resize: none;
        border: 1px solid var(--ink); border-radius: 0; background: var(--sheet);
        outline: none; padding: 10px 12px;
        font-family: var(--serif); font-size: var(--t-body); line-height: 1.4; color: var(--ink);
      }
      .cr-draft.tall { min-height: 148px; resize: vertical; }
      .cr-draft::placeholder { color: var(--ink-3); font-style: italic; }
      .cr-draft:focus { border-color: var(--ink); box-shadow: inset 0 0 0 1px var(--ink); }
      .cr-actions { margin-top: 10px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: stretch; }
      .cr-actions.solo { grid-template-columns: 1fr; }
      /* Primary action, soft: pill geometry, solid ink on paper, sentence case. */
      .cr-cta {
        display: flex; align-items: center; justify-content: center; gap: 11px;
        min-height: 54px; padding: 0 22px; border-radius: 999px;
        background: var(--ink); color: var(--paper); border: 1px solid var(--ink);
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em; text-transform: none;
        text-decoration: none; cursor: pointer;
        transition: background .16s ease, color .16s ease;
      }
      .cr-cta:active { background: var(--paper-2); color: var(--ink); }
      .cr-cta:disabled { opacity: .5; cursor: progress; }
      .cr-cta svg { width: 17px; height: 17px; }
      /* Outlined sibling: same pill, transparent fill, ink keyline. */
      .cr-finish {
        min-height: 54px; padding: 0 22px; border-radius: 999px;
        border: 1px solid var(--ink); background: transparent; color: var(--ink);
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em; text-transform: none;
        white-space: nowrap;
        transition: background .16s ease, color .16s ease;
      }
      .cr-finish:active { background: var(--paper-2); color: var(--ink); }
      .cr-finish:disabled { border-color: var(--ink-3); color: var(--ink-3); opacity: .5; cursor: not-allowed; }
      .cr-gate {
        margin-top: 6px; text-align: right;
        font-size: var(--t-label); font-weight: 800; letter-spacing: .13em;
        text-transform: uppercase; color: var(--ink-3);
      }

      /* 8 · LA RÉSOLUTION */
      .cr-resolve { text-align: center; padding: 24px 0 6px; }
      .cr-resolve-kicker {
        margin-bottom: 14px; font-size: var(--t-label); font-weight: 900;
        letter-spacing: .18em; text-transform: uppercase; color: var(--ink-3);
      }
      .cr-resolve .lu-stamp.big {
        position: static; display: inline-block; transform: rotate(var(--tilt, -5deg));
        font-size: var(--t-head); padding: 8px 18px 7px; border-width: 3px;
        box-shadow: inset 0 0 0 1.5px var(--sheet), inset 0 0 0 3px currentColor;
      }
      .cr-resolve .lu-stamp.big .d { font-size: var(--t-label); }
      @media (prefers-reduced-motion: no-preference) {
        .cr.motion .cr-resolve .lu-stamp.big { animation: lu-strike .34s cubic-bezier(.18, 1.35, .3, 1) .15s both; }
        .cr.motion .cr-resolve .logo-token { animation: cr-token-pop .5s cubic-bezier(.2, 1.25, .3, 1) .55s both; }
      }
      @keyframes cr-token-pop { from { opacity: 0; transform: scale(.4); } to { opacity: 1; transform: scale(1); } }
      .cr-resolve .sub { margin: 14px auto 0; max-width: 280px; font-family: var(--serif); font-style: italic; font-size: var(--t-body); line-height: 1.3; color: var(--ink-2); }
      .cr-resolve .tok-stage { margin: 22px 0 0; display: grid; place-items: center; }
      .cr-resolve .earned { margin-top: 12px; font-size: var(--t-label); font-weight: 900; letter-spacing: .15em; text-transform: uppercase; color: var(--ink-3); }
      .cr-resolve .earned b { color: var(--ink); }
      .cr-credit { margin: 20px auto 0; max-width: 300px; border-top: 1px solid var(--ink); text-align: left; }
      .cr-credit .row { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 9px 2px; border-bottom: 1px solid var(--paper-3); }
      .cr-credit .row span { font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-3); white-space: nowrap; }
      .cr-credit .row b { font-family: var(--serif); font-style: italic; font-weight: 600; font-size: var(--t-body); color: var(--ink); text-align: right; }
      .cr-recap-grid {
        margin: 20px auto 0; max-width: 320px;
        display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
        border: 1px solid var(--ink); text-align: center;
      }
      .cr-recap-grid div { min-width: 0; padding: 11px 6px 10px; }
      .cr-recap-grid div + div { border-left: 1px solid var(--ink); }
      .cr-recap-grid strong {
        display: block; font-family: var(--serif); font-style: italic;
        font-size: var(--t-head); line-height: 1; color: var(--ink);
      }
      .cr-recap-grid span {
        display: block; margin-top: 5px; font-size: var(--t-label); font-weight: 900;
        line-height: 1.25; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-3);
      }
      .cr-readiness {
        margin: 12px auto 0; max-width: 320px; padding: 10px 2px;
        display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
        border-bottom: 3px double var(--ink); text-align: left;
      }
      .cr-readiness span {
        font-size: var(--t-label); font-weight: 900; letter-spacing: .13em;
        text-transform: uppercase; color: var(--ink-3);
      }
      .cr-readiness strong { font-family: var(--serif); font-style: italic; font-size: var(--t-lead); }
      .cr-objectives {
        margin: 14px auto 0; max-width: 320px; display: grid;
        border-bottom: 1px solid var(--ink); text-align: left;
      }
      .cr-objectives > .k {
        padding-bottom: 6px; font-size: var(--t-label); font-weight: 900;
        letter-spacing: .14em; text-transform: uppercase; color: var(--ink-3);
      }
      .cr-objectives > div {
        display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 6px;
        align-items: start; padding: 8px 2px; border-top: 1px solid var(--paper-3);
      }
      .cr-objectives > div > span { color: var(--red); font-size: var(--t-small); line-height: 1.2; }
      .cr-objectives > div.open > span { color: var(--ink-3); }
      .cr-objectives b { font-size: var(--t-label); line-height: 1.35; font-weight: 700; color: var(--ink-2); }
      .cr-nexts { margin: 22px auto 0; max-width: 320px; display: grid; gap: 10px; text-align: center; }
      .cr-ghost {
        display: flex; align-items: center; justify-content: center; gap: 10px;
        min-height: 54px; padding: 0 22px; border-radius: 999px;
        border: 1px solid var(--ink); background: transparent;
        font-size: var(--t-body); font-weight: 600; letter-spacing: .01em; text-transform: none;
        text-decoration: none; color: var(--ink); cursor: pointer;
        transition: background .16s ease, color .16s ease;
      }
      .cr-ghost:active { background: var(--paper-2); color: var(--ink); }
      .cr-ghost:disabled { opacity: .5; cursor: progress; }
      .cr-ghost.quiet { border-color: var(--ink-3); color: var(--ink-2); background: transparent; }

      /* 9 · SYSTEM — archive, skeleton, empty */
      .cr-archive { margin-top: 22px; border-top: 3px double var(--ink); padding-top: 12px; }
      .cr-archive .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .18em; text-transform: uppercase; color: var(--ink-3); }
      .cr-archive ul { list-style: none; margin: 8px 0 0; padding: 0; display: grid; }
      .cr-archive a {
        display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
        padding: 10px 0; border-bottom: 1px solid var(--paper-3);
        color: inherit; text-decoration: none;
      }
      .cr-archive a b { font-family: var(--serif); font-style: italic; font-size: var(--t-body); font-weight: 600; }
      .cr-archive a span { font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-3); white-space: nowrap; }

      .cr-skel { pointer-events: none; padding-top: 14px; display: grid; gap: 12px; }
      .cr-skel .slipph {
        width: 88%; height: 68px;
        border: 1px solid var(--paper-3);
        background: repeating-linear-gradient(0deg, var(--news-wash) 0 6px, var(--paper-2) 6px 12px);
      }
      .cr-skel .slipph.you { margin-left: auto; }
      .cr-skel .barph { height: 54px; border: 1.5px solid var(--paper-3); background: var(--news-wash); margin-top: 4px; }
      @media (prefers-reduced-motion: no-preference) {
        .cr.motion .cr-skel .slipph, .cr.motion .cr-skel .barph { animation: lu-set 1.4s ease-in-out infinite; }
      }

      .cr-empty { text-align: center; padding: 52px 24px 40px; }
      .cr-empty .rubric { font-size: var(--t-label); font-weight: 900; letter-spacing: .18em; text-transform: uppercase; color: var(--ink-3); }
      .cr-empty .endmark { width: 14px; height: 14px; background: var(--ink); margin: 18px auto 16px; }
      .cr-empty h2 { margin: 0 auto; max-width: 270px; font-family: var(--serif); font-style: italic; font-weight: 600; font-size: var(--t-head); line-height: 1.08; color: var(--ink); }
      .cr-empty p { margin: 14px auto 0; max-width: 250px; font-size: var(--t-small); line-height: 1.5; color: var(--ink-2); }
      .cr-empty .free {
        margin-top: 26px; display: inline-flex; align-items: center; gap: 9px;
        min-height: 44px; font-size: var(--t-small); font-weight: 900; letter-spacing: .14em;
        text-transform: uppercase; color: var(--ink); text-decoration: none;
        border-bottom: 1.5px solid var(--ink); padding-bottom: 2px;
      }
      .cr-empty .free svg { width: 14px; height: 14px; }
    `}</style>
  );
}
