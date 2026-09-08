/* Atelier V2 — LE COURRIER · Missions on the Claude design system.
   Source of truth: the MISSIONS artboard in
   docs/design-reference/claude/Atelier App.dc.html — a 40px round portrait,
   the character's name as the one Garamond-italic headline, a 12px muted
   mission line, a yellow reward chip, a column of chat bubbles (character:
   card colour, 20/20/20/6; learner: blue, 20/20/6/20), a green feedback line,
   a Garamond-italic blue hint pill with a yellow square, and a footer composer
   (50px pill well + one round red 3D-press button).

   Everything the artboard does not draw (the brief, the word ribbon, the
   repair note, the voicemail memo, the recap, the archive, empty / error /
   loading) is extended from the same primitives in styles/atelier-v2.css —
   rounded 16–24px surfaces, the four Bauhaus tokens, sentence case, two fonts.
   Every component still maps onto a real API field. All rules here are written
   `.av2 .cr-…` so they outrank the legacy element resets. */

import React, { useState } from 'react';
import Link from 'next/link';

import {
  Action,
  ArrowLeftIcon,
  ArrowRightIcon,
  Chip,
  IconAction,
  Portrait,
  SendIcon,
  ShapeToken,
} from '@/components/atelier-v2/ui';

/* ---------- lazy translate (frame + character voice) ----------
   Wraps apiService.translateToEnglish; English is out-of-fiction chrome, so
   the reveal is plain muted text, never set as the character's line. */
export function CrTranslate({
  translate,
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

  return (
    <div className="cr-trad">
      <button
        type="button"
        className="cr-trad-btn"
        onClick={reveal}
        aria-expanded={open}
        aria-label={open ? 'Masquer la traduction' : 'Voir la traduction'}
      >
        {open ? 'Masquer' : label}
      </button>
      {open && (
        <p className="cr-trad-reveal" lang="en">
          {loading ? 'Traduction…' : text || 'Traduction indisponible.'}
        </p>
      )}
    </div>
  );
}

/* ---------- header row (the design's Missions header) ----------
   name    ← messenger.contact_name (portrait initial + the one headline)
   line    ← cadence / act kicker · mission title (12px muted)
   chip    ← reward chip "■ used/total" from target_vocabulary, or "done" */
export function CrDesk({
  name,
  line,
  chip,
  onBack,
  backHref = '/atelier',
  backLabel = 'Retour à la Une',
}: {
  name: string;
  line: string;
  chip?: React.ReactNode;
  onBack?: (event: React.MouseEvent<HTMLAnchorElement>) => void;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <header className="cr-desk">
      <Link className="av2-icon-btn cr-back" href={backHref} onClick={onBack} aria-label={backLabel} title={backLabel}>
        <ArrowLeftIcon size={20} />
      </Link>
      <Portrait name={name} />
      <div className="cr-desk-main">
        <h1 className="cr-name" lang="fr">{name}</h1>
        <p className="cr-line">{line}</p>
      </div>
      {chip}
    </header>
  );
}

/* ---------- the situation (no artboard: extended as a card surface) ----------
   frame ← slim_payload.frame · ask ← slim_payload.ask (red triangle = action) */
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
    <section className="cr-sit" aria-label="La situation">
      <p className="cr-sit-frame" lang="fr">{frame}</p>
      {ask && (
        <p className="cr-sit-ask">
          <ShapeToken kind="action" size="sm" />
          <span><b>À faire ·</b> <span lang="fr">{ask}</span></span>
        </p>
      )}
      {translate && <CrTranslate translate={translate} />}
    </section>
  );
}

/* ---------- P.S. ← slim_payload.twist → the design's hint pill ---------- */
export function CrPS({ text }: { text?: string | null }) {
  if (!text) return null;
  return (
    <p className="cr-hint" lang="fr">
      <ShapeToken kind="reward" size="sm" />
      <span>P.S. — {text}</span>
    </p>
  );
}

/* ---------- word ribbon ← target_vocabulary (≤3) as reward chips ----------
   A word already placed flips to the ink square (= done), with the word said
   out loud so the state is never colour alone. */
export function CrRibbon({ words = [] }: { words?: { t: string; used?: boolean }[] }) {
  if (!words.length) return null;
  return (
    <div className="cr-ribbon" role="list" aria-label="Mots à placer">
      <span className="cr-ribbon-k">À placer</span>
      {words.map((w) => (
        <span role="listitem" key={w.t}>
          <Chip tone={w.used ? 'plain' : 'reward'} icon={<ShapeToken kind={w.used ? 'done' : 'reward'} size="sm" />}>
            <span lang="fr">{w.t}</span>
            {w.used && <span className="av2-sr"> · placé</span>}
          </Chip>
        </span>
      ))}
    </div>
  );
}

/* ---------- bubble ← a conversation turn ----------
   Character: card colour, 20/20/20/6. Learner: blue, 20/20/6/20. The speaker
   is announced to assistive tech; the time prints only when the turn has one. */
export function CrSlip({
  who,
  time,
  you = false,
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
    <div className={'cr-turn' + (you ? ' cr-turn--mine' : '')}>
      <div className={'av2-bubble' + (you ? ' av2-bubble--mine' : '')} lang="fr">
        <span className="av2-sr">{who} · </span>
        {children}
      </div>
      {time && <span className="cr-turn-time">{time}</span>}
      {translate && <CrTranslate translate={translate} />}
    </div>
  );
}

/* ---------- repair note ← turn.correction ----------
   The design's green "● Bien dit · une petite remarque" line, then the fix. */
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
  const count = Math.max(lines.length, correctedAnswer ? 1 : 0);
  return (
    <aside className="cr-repair" aria-label="Correction">
      <p className="cr-feedback">
        <span className="cr-feedback-dot" aria-hidden="true" />
        Bien dit · {count === 1 ? 'une petite remarque' : `${count} petites remarques`}
      </p>
      <div className="cr-repair-card">
        {correctedAnswer && (
          <p className="cr-repair-answer" lang="fr">{correctedAnswer}</p>
        )}
        {lines.map((line, index) => (
          <React.Fragment key={index}>
            {line.fixed && <p className="cr-repair-fix" lang="fr">{line.fixed}</p>}
            {line.why && <p className="cr-repair-why">{line.why}</p>}
          </React.Fragment>
        ))}
        {savedCount > 0 && (
          <p className="cr-repair-saved">
            <ShapeToken kind="done" size="sm" />
            <span>{savedCount} réparation{savedCount === 1 ? '' : 's'} enregistrée{savedCount === 1 ? '' : 's'}</span>
          </p>
        )}
      </div>
    </aside>
  );
}

/* ---------- phone memo ← voicemail / phone_call payload ----------
   No artboard: the transcript is the character's voice, so it is drawn as a
   character bubble under a small "pendant votre absence" card. */
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
      <div className="cr-memo-card">
        <p className="cr-memo-head">
          <ShapeToken kind="story" size="sm" />
          <span>Pendant votre absence · message téléphonique</span>
          {stamp && (
            <Chip icon={<ShapeToken kind="done" size="sm" />} className="cr-memo-stamp">{stamp}</Chip>
          )}
        </p>
        {rows.map((r) => (
          <p className="cr-memo-row" key={r[0]}><span>{r[0]}</span><b>{r[1]}</b></p>
        ))}
      </div>
      <div className="cr-turn">
        <div className="av2-bubble" lang="fr">
          <span className="av2-sr">Transcription automatique · </span>
          {transcript}
        </div>
        {translate && <CrTranslate translate={translate} />}
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
    <div className={'cr-call' + (live ? ' cr-call--live' : '')} role="status">
      <ShapeToken kind="action" size="sm" />
      <span className="cr-call-tx"><b>{who}</b><span>{sub}</span></span>
    </div>
  );
}

/* ---------- composer (the design's footer) ----------
   quick ← quick_replies (paper chips) · the well ← the learner's draft ·
   `send` ← the ONE 3D press on the screen: a round red icon action, unless the
   page hands in a voice control to stand in its place while the draft is
   empty. Finish stays a quiet action gated on ≥1 learner turn. */
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
  voice,
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
  /** A control that replaces the send press (the mic) while there is no draft. */
  voice?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <form className="cr-composer" onSubmit={onSubmit}>
      {quick.length > 0 && (
        <div className="cr-quick" role="group" aria-label="Réponses rapides">
          {quick.map((q) => (
            <Chip key={q} onClick={() => onQuick?.(q)} className="cr-quick-chip">
              <span lang="fr">{q}</span>
            </Chip>
          ))}
        </div>
      )}
      <div className="av2-composer cr-well">
        {children}
        {voice ?? (
          <IconAction
            label={cta}
            tone="action"
            pressable
            type="submit"
            className="cr-send"
            disabled={!canSubmit}
            pending={sending}
          >
            <SendIcon size={20} />
          </IconAction>
        )}
      </div>
      {!hideFinish && (
        <div className="cr-finish-row">
          <Action
            tone="quiet"
            inline
            disabled={!canFinish}
            pending={finishing}
            pendingLabel="Clôture…"
            onClick={onFinish}
            className="cr-finish"
          >
            {finishLabel}
          </Action>
          {!canFinish && <span className="cr-gate">Envoyez d’abord une réponse.</span>}
        </div>
      )}
    </form>
  );
}

/* ---------- resolution link/button ----------
   `primary` is the one 3D press of the resolved screen; the rest are quiet. */
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
  if (href) {
    return (
      <Link
        className={'av2-btn ' + (primary ? 'av2-btn--primary' : 'av2-btn--quiet') + (quiet ? ' cr-ghost--quiet' : '')}
        href={href}
        onClick={onClick}
      >
        <span>{children}</span>
        {primary && <ArrowRightIcon size={18} />}
      </Link>
    );
  }
  return (
    <Action
      tone={primary ? 'primary' : 'quiet'}
      className={quiet ? 'cr-ghost--quiet' : undefined}
      onClick={onClick}
      disabled={disabled}
      iconAfter={primary ? <ArrowRightIcon size={18} /> : undefined}
    >
      {children}
    </Action>
  );
}

/* ============================================================
   Styles — written `.av2 .cr-…` (0,2,0) on purpose: legacy page resets such
   as `.x-page button { background: transparent }` are (0,1,1). Only --av2-*
   tokens; sizes in rem; two faces (AtelierSerif / AtelierSans) behind the
   tokens. The journal's old `font-size: var(--t-…)` scale is retired here.
   ============================================================ */
export function CourrierStyles() {
  return (
    <style jsx global>{`
      .av2.cr {
        position: relative;
        width: min(var(--app-viewport-width, 100vw), var(--phone-shell-max, 430px));
        min-height: 100svh;
        display: flex;
        flex-direction: column;
        padding-top: var(--phone-safe-top, 0px);
        /* clears the fixed PhoneProductNav so the composer never hides behind it */
        padding-bottom: var(--phone-bottom-nav-space, 88px);
      }
      /* :where() keeps the reset at zero specificity so no component class is outranked. */
      .av2.cr :where(a, button) { font: inherit; color: inherit; text-align: inherit; }
      .av2 .cr-page { flex: 1 1 auto; display: flex; flex-direction: column; gap: 12px; padding: 0 var(--av2-gutter) 16px; }
      .av2 .cr-page--centre { justify-content: center; }

      /* header row */
      .av2 .cr-desk { display: flex; align-items: center; gap: 12px; padding: 14px 0 6px; }
      .av2 .cr-back { flex: none; margin-left: -6px; text-decoration: none; background: transparent; }
      .av2 .cr-desk-main { flex: 1 1 auto; min-width: 0; }
      .av2 .cr-name {
        margin: 0; font-family: var(--av2-serif); font-style: italic; font-weight: 400;
        font-size: 1.375rem; line-height: 1; color: var(--av2-ink);
        overflow-wrap: anywhere;
      }
      .av2 .cr-line { margin: 3px 0 0; font-size: var(--av2-t-meta); line-height: 1.3; color: var(--av2-muted); }
      .av2 .cr-desk .av2-chip { flex: none; min-height: 30px; padding: 0 10px; font-size: var(--av2-t-meta); }
      .av2 .cr-reason { margin: 0; font-size: var(--av2-t-label); line-height: 1.4; color: var(--av2-ink-2); }

      /* the situation */
      .av2 .cr-sit {
        display: flex; flex-direction: column; gap: 8px;
        padding: 14px 16px; border-radius: var(--av2-r-tile); background: var(--av2-card);
      }
      .av2 .cr-sit-frame { margin: 0; font-size: var(--av2-t-body); line-height: 1.45; color: var(--av2-ink); }
      .av2 .cr-sit-ask { margin: 0; display: flex; align-items: flex-start; gap: 8px; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2); }
      .av2 .cr-sit-ask .av2-shape { margin-top: 5px; }
      .av2 .cr-sit-ask b { font-weight: 700; color: var(--av2-red); }

      /* translate: a quiet text control, muted reveal */
      .av2 .cr-trad { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
      .av2 .cr-trad-btn {
        min-height: var(--av2-tap); padding: 0 4px; border: 0; background: transparent; cursor: pointer;
        font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted);
        text-decoration: underline; text-underline-offset: 3px;
      }
      .av2 .cr-trad-reveal { margin: 0 0 4px; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2); }
      .av2 .cr-turn .cr-trad { margin-top: -6px; }
      /* the turn's translate control is tighter than the standalone one, but
         never below the tap floor */
      .av2 .cr-turn .cr-trad-btn { min-height: var(--av2-tap); }

      /* hint pill — Garamond italic, blue, yellow square */
      .av2 .cr-hint {
        align-self: flex-start; margin: 0; display: flex; align-items: center; gap: 8px;
        padding: 10px 14px; border-radius: 14px; background: var(--av2-card);
        font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body); line-height: 1.3;
        color: var(--av2-blue);
      }
      .av2 .cr-hint .av2-shape { flex: none; }

      /* word ribbon */
      .av2 .cr-ribbon { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; }
      .av2 .cr-ribbon-k { font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); margin-right: 2px; }

      /* thread of bubbles */
      .av2 .cr-thread { display: flex; flex-direction: column; gap: 12px; padding: 10px 0 4px; }
      .av2 .cr-turn { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
      .av2 .cr-turn--mine { align-items: flex-end; }
      .av2 .cr-turn .av2-bubble { white-space: pre-wrap; }
      .av2 .cr-turn-time { font-size: var(--av2-t-meta); color: var(--av2-muted); font-variant-numeric: tabular-nums; padding: 0 6px; }
      .av2 .cr-typing {
        display: inline-flex; align-items: center; gap: 8px;
        font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-blue);
      }
      .av2 .cr-typing .rollers { display: inline-flex; gap: 3px; }
      .av2 .cr-typing .rollers i { width: 6px; height: 6px; border-radius: 999px; background: currentColor; }
      @media (prefers-reduced-motion: no-preference) {
        .av2.motion .cr-typing .rollers i { animation: cr-roll 1.1s ease-in-out infinite; }
        .av2.motion .cr-typing .rollers i:nth-child(2) { animation-delay: .18s; }
        .av2.motion .cr-typing .rollers i:nth-child(3) { animation-delay: .36s; }
      }
      @keyframes cr-roll { 0%, 100% { opacity: .25; } 50% { opacity: 1; } }

      /* feedback line + repair note */
      .av2 .cr-repair { align-self: flex-end; display: flex; flex-direction: column; align-items: flex-end; gap: 8px; max-width: 86%; margin-top: -4px; }
      .av2 .cr-feedback { margin: 0; display: flex; align-items: center; gap: 6px; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-green); }
      .av2 .cr-feedback-dot { width: 8px; height: 8px; border-radius: 999px; background: var(--av2-green); flex: none; }
      .av2 .cr-repair-card {
        display: flex; flex-direction: column; gap: 6px; width: 100%;
        padding: 12px 14px; border-radius: 20px 20px 6px 20px; background: var(--av2-card);
        font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2);
      }
      .av2 .cr-repair-card p { margin: 0; }
      .av2 .cr-repair-answer,
      .av2 .cr-repair-fix { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body); line-height: 1.35; color: var(--av2-green); }
      .av2 .cr-repair-saved { display: flex; align-items: center; gap: 6px; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }

      /* voicemail memo */
      .av2 .cr-memo { display: flex; flex-direction: column; gap: 10px; }
      .av2 .cr-memo-card { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; border-radius: var(--av2-r-tile); background: var(--av2-card); }
      .av2 .cr-memo-head { margin: 0; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
      .av2 .cr-memo-stamp { margin-left: auto; }
      .av2 .cr-memo-row { margin: 0; display: flex; gap: 10px; align-items: baseline; font-size: var(--av2-t-label); line-height: 1.4; }
      .av2 .cr-memo-row span { flex: 0 0 6.5rem; color: var(--av2-muted); }
      .av2 .cr-memo-row b { font-weight: 600; color: var(--av2-ink); }
      .av2 .cr-call { display: flex; align-items: center; gap: 10px; padding: 12px 14px; border-radius: var(--av2-r-tile); background: var(--av2-card); }
      @media (prefers-reduced-motion: no-preference) {
        .av2.motion .cr-call--live .av2-shape { animation: cr-roll 1.2s ease-in-out infinite; }
      }
      .av2 .cr-call-tx b { display: block; font-size: var(--av2-t-label); font-weight: 700; }
      .av2 .cr-call-tx span { display: block; font-size: var(--av2-t-meta); color: var(--av2-muted); font-variant-numeric: tabular-nums; }

      /* composer footer */
      .av2 .cr-composer {
        position: sticky; bottom: var(--phone-bottom-nav-space, 88px); z-index: 2;
        flex: none; display: flex; flex-direction: column; gap: 10px;
        padding: 12px var(--av2-gutter) 14px; background: var(--av2-paper);
      }
      .av2 .cr-quick { display: flex; flex-wrap: wrap; gap: 8px; }
      .av2 .cr-quick-chip { font-weight: 600; }
      .av2 .cr-well { align-items: flex-end; flex-wrap: wrap; }
      .av2 .cr-well .cr-mic-state, .av2 .cr-well .cr-mic-problem { flex: 1 1 100%; }
      .av2 .cr-well .av2-field { flex: 1 1 auto; gap: 4px; }
      .av2 .cr-well .av2-field__label { font-weight: 600; }
      .av2 .cr-instruction { margin: 0; font-size: var(--av2-t-label); line-height: 1.4; color: var(--av2-ink-2); }
      .av2 .cr-draft {
        min-height: 50px; padding: 0.8125rem 1.125rem; border-radius: 25px; resize: none;
        font-size: var(--av2-t-body-lg); line-height: 1.45;
      }
      .av2 .cr-draft--tall { min-height: 9.25rem; border-radius: 20px; resize: vertical; }
      .av2 .cr-send { width: 50px; height: 50px; margin-bottom: 0; }
      .av2 .cr-finish-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
      .av2 .cr-gate { font-size: var(--av2-t-meta); color: var(--av2-muted); }
      .av2 .cr-mic-state { display: flex; align-items: center; gap: 8px; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-ink-2); }
      .av2 .cr-mic-state .av2-shape { flex: none; }
      .av2 .cr-mic-problem { margin: 0; font-size: var(--av2-t-label); line-height: 1.4; color: var(--av2-red-deep); }
      @media (prefers-reduced-motion: no-preference) {
        .av2.motion .cr-mic-state--rec .av2-shape { animation: cr-roll .9s ease-in-out infinite; }
      }

      /* resolution — extended from the ink (done) and yellow (reward) surfaces */
      .av2 .cr-resolve { display: flex; flex-direction: column; gap: 12px; padding-top: 6px; }
      .av2 .cr-resolve-kicker { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
      .av2 .cr-seal { display: flex; flex-direction: column; gap: 6px; padding: 18px 20px; border-radius: var(--av2-r-hero); background: var(--av2-ink); color: var(--av2-on-ink); }
      .av2 .cr-seal-word { display: flex; align-items: center; gap: 10px; font-size: var(--av2-t-title); font-weight: 700; line-height: 1.1; }
      .av2 .cr-seal-word .av2-shape { color: var(--av2-yellow); }
      .av2 .cr-seal-date { font-size: var(--av2-t-meta); opacity: .8; }
      .av2 .cr-seal-sub { margin: 4px 0 0; font-size: var(--av2-t-body); line-height: 1.45; }
      .av2 .cr-token { display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-radius: var(--av2-r-episode); background: var(--av2-yellow); color: var(--av2-on-yellow); }
      /* the minted collectible keeps its artwork but drops the legacy ink box + offset shadow */
      .av2 .cr-token .logo-token { width: 64px; height: 64px; border: 0; border-radius: var(--av2-r-card); background: var(--av2-card); box-shadow: none; }
      .av2 .cr-token .logo-token .lt { width: 40px; height: 40px; }
      .av2 .cr-token-earned { font-size: var(--av2-t-body); font-weight: 700; }
      .av2 .cr-credit { display: flex; flex-direction: column; gap: 2px; padding: 6px 16px; border-radius: var(--av2-r-tile); background: var(--av2-card); }
      .av2 .cr-credit-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 40px; font-size: var(--av2-t-label); }
      .av2 .cr-credit-row span { display: flex; align-items: center; gap: 8px; color: var(--av2-muted); }
      .av2 .cr-credit-row b { font-weight: 700; color: var(--av2-ink); text-align: right; }
      .av2 .cr-recap-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
      .av2 .cr-recap-grid div { display: flex; flex-direction: column; gap: 4px; padding: 12px 10px; border-radius: var(--av2-r-tile); background: var(--av2-card); text-align: center; }
      .av2 .cr-recap-grid strong { font-family: var(--av2-serif); font-style: italic; font-weight: 400; font-size: var(--av2-t-head); line-height: 1; color: var(--av2-ink); }
      .av2 .cr-recap-grid span { font-size: var(--av2-t-meta); line-height: 1.25; color: var(--av2-muted); }
      .av2 .cr-readiness { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; border-radius: var(--av2-r-tile); background: var(--av2-card); font-size: var(--av2-t-label); color: var(--av2-muted); }
      .av2 .cr-readiness strong { font-size: var(--av2-t-action); color: var(--av2-ink); }
      .av2 .cr-objectives { display: flex; flex-direction: column; gap: 6px; padding: 12px 16px; border-radius: var(--av2-r-tile); background: var(--av2-card); }
      .av2 .cr-objectives-k { font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
      .av2 .cr-objective { display: flex; align-items: flex-start; gap: 8px; font-size: var(--av2-t-label); line-height: 1.4; color: var(--av2-ink-2); }
      .av2 .cr-objective .av2-shape { margin-top: 5px; }
      .av2 .cr-objective--met { color: var(--av2-ink); }
      .av2 .cr-next { margin: 0; font-size: var(--av2-t-body); line-height: 1.45; color: var(--av2-ink-2); }
      .av2 .cr-nexts { display: flex; flex-direction: column; gap: 8px; padding-top: 4px; }
      .av2 .cr-nexts .av2-btn { text-decoration: none; }
      .av2 .cr-ghost--quiet { color: var(--av2-muted); }

      /* archive */
      .av2 .cr-archive { display: flex; flex-direction: column; gap: 8px; padding-top: 10px; }
      .av2 .cr-archive-k { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
      .av2 .cr-archive ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
      .av2 .cr-archive-row {
        display: flex; align-items: center; gap: 12px; min-height: var(--av2-tap);
        padding: 12px 14px; border-radius: var(--av2-r-card); background: var(--av2-card);
        color: var(--av2-ink); text-decoration: none;
      }
      .av2 .cr-archive-row b { flex: 1 1 auto; font-size: var(--av2-t-body); font-weight: 600; line-height: 1.3; }
      .av2 .cr-archive-row span { display: flex; align-items: center; gap: 6px; font-size: var(--av2-t-meta); color: var(--av2-muted); white-space: nowrap; }

      /* loading */
      .av2 .cr-skel { display: flex; flex-direction: column; gap: 12px; padding-top: 14px; }
      .av2 .cr-skel .av2-skeleton { width: 78%; border-radius: 20px 20px 20px 6px; }
      .av2 .cr-skel .av2-skeleton.cr-skel--mine { align-self: flex-end; border-radius: 20px 20px 6px 20px; }
      .av2 .cr-skel .av2-skeleton.cr-skel--bar { width: 100%; border-radius: var(--av2-r-pill); margin-top: 8px; }
    `}</style>
  );
}
