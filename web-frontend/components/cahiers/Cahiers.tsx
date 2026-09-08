/* Atelier — "LES CAHIERS" · the notebook cluster's shared primitives.
 *
 * Ported from the Claude Design package (cahiers-parts.jsx / cahiers.css) into
 * the app's `--app-*` token system — theme-aware light/dark for free. The
 * design doc's `.nc { --app-paper: … }` / `.nc.dark { … }` palette mirror is
 * dropped here; `.nc` inherits the global tokens from styles/globals.css and
 * only defines the derived `--nc-*` values. Every prop maps to a real API
 * field (see docs/overhaul-notebook.md §"Données → props").
 *
 * The pages provide the app chrome (PhoneProductNav) exactly like La Une; the
 * design's own NcTabs/NcShell harness is not ported.
 */
import React from 'react';
import Link from 'next/link';

/* ---------- icons ---------- */
export function NcIcoGear() {
  return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}><circle cx="12" cy="12" r="3.2" /><path d="M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1" /></svg>);
}
export function NcIcoBack() {
  return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4}><path d="M20 12H5M11 6l-6 6 6 6" /></svg>);
}
export function NcIcoArrow() {
  return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4}><path d="M4 12h15M13 6l6 6-6 6" /></svg>);
}
export function NcIcoX() {
  return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4}><path d="M5 5l14 14M19 5L5 19" /></svg>);
}
export function NcIcoSearch() {
  return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><circle cx="11" cy="11" r="6.5" /><path d="M16 16l5 5" /></svg>);
}
export function NcIcoFold({ open = false }: { open?: boolean }) {
  return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4}><path d={open ? 'M5 15l7-7 7 7' : 'M5 9l7 7 7-7'} /></svg>);
}

/* ---------- masthead ---------- */
export function NcMasthead({
  cefr = null,
  slim = false,
  route = null,
  xlink = null,
  xlinkHref = '#',
  settingsHref = '/settings',
}: {
  cefr?: string | null;
  slim?: boolean;
  route?: string | null;
  xlink?: string | null;
  xlinkHref?: string;
  settingsHref?: string;
}) {
  if (slim) {
    return (
      <header className="nc-mast slim">
        <span className="rub"><b>Les Cahiers</b>{route ? ' · ' + route : ''}</span>
        {xlink && <Link className="xlink" href={xlinkHref}>{xlink} →</Link>}
      </header>
    );
  }
  return (
    <header>
      <div className="nc-mast">
        <div className="folio">
          {cefr ? <b>Cours · {cefr}</b> : <span className="off">Progression indisponible</span>}
          {/* /notebook renders its own shell, so this gear is the only way to
              reach settings from here — the duplicated brand badge went, the
              control stays. */}
          <Link className="folio-gear" href={settingsHref} aria-label="Réglages"><NcIcoGear /></Link>
        </div>
      </div>
    </header>
  );
}

/* ---------- mode tabs ---------- */
export type NcMode = 'grammaire' | 'vocabulaire' | 'releve' | 'bibliotheque';
export function NcModeTabs({
  active = 'grammaire',
  library = true,
  metas = {},
  onSelect,
}: {
  active?: NcMode;
  library?: boolean;
  metas?: Partial<Record<NcMode, string>>;
  onSelect?: (mode: NcMode) => void;
}) {
  // The old Progrès tab embedded the pre-journal English Anki dashboard (raw
  // stage table, global word dump) inside the French Cahier. Le Relevé replaces
  // it: same slot, learner-scoped data only, French throughout.
  const tabs: Array<{ id: NcMode; label: string; meta: string }> = [
    { id: 'grammaire', label: 'Grammaire', meta: metas.grammaire || '' },
    { id: 'vocabulaire', label: 'Vocabulaire', meta: metas.vocabulaire || '' },
    { id: 'releve', label: 'Relevé', meta: metas.releve || '' },
  ];
  if (library) tabs.push({ id: 'bibliotheque', label: 'Bibliothèque', meta: metas.bibliotheque || '' });
  return (
    <div className="nc-modetabs" role="tablist" aria-label="Modes du carnet">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          className="nc-tab"
          aria-selected={t.id === active}
          onClick={() => onSelect?.(t.id)}
        >
          <span className="m">{t.label}</span>
          {t.meta && <span className="s">{t.meta}</span>}
        </button>
      ))}
    </div>
  );
}

/* ---------- filing summary ---------- */
export type NcFilingItem = { n?: number | null; label: string; tone?: 'due' | 'era' | '' };
export function NcFilingSummary({ lead = '', items = [] }: { lead?: string; items?: NcFilingItem[] }) {
  return (
    <div className="nc-filing" role="status">
      {lead ? <span className="k">{lead}</span> : null}
      {items.map((it, i) => (
        <React.Fragment key={i}>
          <span className="sep" />
          <span className={it.tone || ''}>{it.n != null ? it.n + ' ' : ''}{it.label}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

/* ---------- optional feuilleton file ---------- */
export function NcFeuilleFile({ ep, title, href = '/graphic-novel' }: { ep?: number | string; title: string; href?: string }) {
  return (
    <Link className="nc-feuille" href={href}>
      <span className="spine" aria-hidden="true" />
      <span>
        <span className="k">Le Feuilleton · classé au dossier</span>
        <span className="t" style={{ display: 'block' }}>{ep != null ? `Épisode ${ep} — ` : ''}{title}</span>
      </span>
      <span className="go">Reprendre →</span>
    </Link>
  );
}

/* ---------- search / chips / live summary ---------- */
export function NcSearch({
  placeholder,
  value,
  onChange,
}: {
  placeholder: string;
  value?: string;
  onChange?: (value: string) => void;
}) {
  return (
    <div className="nc-search">
      <NcIcoSearch />
      <input
        type="search"
        placeholder={placeholder}
        aria-label={placeholder}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </div>
  );
}
export type NcChip = { l: string; n?: number | null };
export function NcChips({ chips, active = 0, onSelect }: { chips: NcChip[]; active?: number; onSelect?: (index: number) => void }) {
  return (
    <div className="nc-chips" role="group" aria-label="Filtres">
      {chips.map((c, i) => (
        <button key={c.l} type="button" className="nc-chip" aria-pressed={i === active} onClick={() => onSelect?.(i)}>
          {c.l}{c.n != null && <span className="n">{c.n}</span>}
        </button>
      ))}
    </div>
  );
}
export function NcLiveSum({ text, clearable = false, onClear }: { text: string; clearable?: boolean; onClear?: () => void }) {
  return (
    <div className="nc-livesum" aria-live="polite">
      <em>{text}</em>
      {clearable && <button type="button" className="clear" onClick={onClear}>Effacer les filtres</button>}
    </div>
  );
}

/* ---------- ledger heads ---------- */
export function NcLedgerHead({ t, n, tone = '' }: { t: string; n?: string | null; tone?: 'blue' | 'mut' | '' }) {
  return (<div className="nc-ledghead"><span className={'t ' + tone}>{t}</span>{n && <span className="n">{n}</span>}</div>);
}

/* ---------- grammar index row ---------- */
export type NcState = 'new' | 'building' | 'fragile' | 'solid' | 'mastered';
export function NcDueMark({ label = 'À revoir' }: { label?: string }) { return <span className="nc-due">{label}</span>; }
export function NcStateStamp({ state = 'new', label }: { state?: NcState; label: string }) {
  const map: Record<NcState, string> = { new: '', building: 'building', fragile: 'fragile', solid: 'solid', mastered: 'mastered' };
  return <span className={'nc-stamp ' + (map[state] || '')}>{label}</span>;
}
export function NcIndexRow({
  no, title, level, cat, mastery = 0, state = 'new', stateLabel = 'Nouveau', due = false, errata = 0, sel = false, onClick,
}: {
  no: number | string;
  title: string;
  level: string;
  cat: string;
  mastery?: number;
  state?: NcState;
  stateLabel?: string;
  due?: boolean;
  errata?: number;
  sel?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={'nc-row' + (sel ? ' sel' : '')}
      aria-label={title + ', ' + level + ' ' + cat + (due ? ', à revoir' : '')}
      onClick={onClick}
    >
      <span className="no">{String(no).padStart(2, '0')}</span>
      <span className="t">{title}</span>
      <span className="marks">
        {due ? <NcDueMark /> : <NcStateStamp state={state} label={stateLabel} />}
        {errata > 0 && <span className="nc-errdot"><i />{errata} errata</span>}
      </span>
      <span className="meta">
        <span>{level} · {cat}</span>
        <span className="lead" aria-hidden="true" />
        <span className="nc-pips" aria-label={'Maîtrise ' + mastery + ' sur 10'}>
          {Array.from({ length: 10 }, (_, i) => <i key={i} className={i < mastery ? 'on' : ''} />)}
        </span>
      </span>
    </button>
  );
}

/* ---------- word ledger row ---------- */
export type NcBucket = { id: 'due' | 'fragile' | 'new'; label: string };
export function NcWordRow({
  rank, word, tr, pos, bucket = null, state = null, stateLabel = null, sel = false, onClick,
}: {
  rank?: number | null;
  word: string;
  tr?: string | null;
  pos?: string | null;
  bucket?: NcBucket | null;
  state?: NcState | null;
  stateLabel?: string | null;
  sel?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={'nc-wordrow' + (sel ? ' sel' : '')}
      aria-label={word + (tr ? ', ' + tr : '')}
      onClick={onClick}
    >
      <span className="rank">{rank != null ? '#' + rank : '·'}</span>
      <span className="w">{word}</span>
      <span className="marks">
        {bucket && <span className={'nc-bucket ' + bucket.id}><i />{bucket.label}</span>}
        {state && <span className={'nc-bucket ' + state}><i />{stateLabel}</span>}
      </span>
      <span className="tr">{tr}{pos ? ' · ' + pos : ''}</span>
    </button>
  );
}

/* ---------- fiche sections ---------- */
export function NcSec({ kick, tone = '', ct, children }: { kick: string; tone?: 'blue' | 'mut' | ''; ct?: string | null; children: React.ReactNode }) {
  return (
    <section className="nc-sec">
      <div className={'kick ' + tone}>{kick}{ct && <span className="ct">{ct}</span>}</div>
      {children}
    </section>
  );
}
export function NcExample({ fr, de }: { fr: string; de?: string | null }) {
  return (<div className="nc-ex"><span className="fr" dangerouslySetInnerHTML={{ __html: fr }} />{de && <span className="de">{de}</span>}</div>);
}
export function NcErrRow({ q, d, recent = false }: { q: string; d?: string | null; recent?: boolean }) {
  return (
    <div className={'nc-errow' + (recent ? ' recent' : '')}>
      <i aria-hidden="true" />
      <span className="q" dangerouslySetInnerHTML={{ __html: q }} />
      {d && <span className="d">{d}</span>}
    </div>
  );
}

/* ---------- notes en marge ---------- */
export function NcMarginNotes({
  editing = false,
  value = '',
  onValueChange,
  saving = false,
  error = false,
  dirty = false,
  onEdit,
  onSave,
  onCancel,
  onRetry,
}: {
  editing?: boolean;
  value?: string;
  onValueChange?: (value: string) => void;
  saving?: boolean;
  error?: boolean;
  dirty?: boolean;
  onEdit?: () => void;
  onSave?: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
}) {
  if (!editing) {
    return (
      <div className="nc-notes">
        <p className={'txt' + (value ? '' : ' ph')}>{value || 'Aucune note pour l’instant — la marge vous attend.'}</p>
        <div className="bar">
          <button type="button" className="act" onClick={onEdit}>{value ? 'Modifier' : 'Annoter'}</button>
          {value && <span className="st">Enregistrée</span>}
        </div>
      </div>
    );
  }
  return (
    <div className={'nc-notes editing' + (saving ? ' saving' : '') + (error ? ' err' : '')}>
      <textarea
        value={value}
        onChange={(e) => onValueChange?.(e.target.value)}
        aria-label="Notes en marge"
        readOnly={saving}
      />
      <div className="bar">
        <div style={{ display: 'flex', gap: 7 }}>
          <button type="button" className="act primary" disabled={saving} onClick={onSave}>{saving ? 'Envoi…' : 'Enregistrer'}</button>
          <button type="button" className="act" disabled={saving} onClick={onCancel}>Annuler</button>
        </div>
        {error ? <span className="st bad">Échec — note conservée ici</span>
          : saving ? <span className="st dirty">Classement en cours</span>
          : dirty ? <span className="st dirty">Non enregistrée</span> : <span className="st">Brouillon</span>}
      </div>
      {error && (
        <div className="nc-notice inline" role="alert" style={{ marginTop: 9 }}>
          <span className="sq" />
          <span className="body"><b>Avis du bureau des archives</b><p>La note n’a pas pu être classée. Elle reste dans la marge. <button type="button" className="retry" style={{ minHeight: 32, marginTop: 6 }} onClick={onRetry}>Réessayer</button></p></span>
        </div>
      )}
    </div>
  );
}

/* ---------- coverage track + mastery map ---------- */
export function NcCoverageTrack({ lab, val, max, tone = '' }: { lab: string; val: number; max: number; tone?: 'ink' | 'red' | '' }) {
  return (
    <div className="nc-track" role="progressbar" aria-valuenow={val} aria-valuemax={max} aria-label={lab}>
      <span className="lab">{lab}</span>
      <span className="bar"><i className={tone} style={{ width: Math.min(100, max ? 100 * val / max : 0) + '%' }} /></span>
      <span className="num">{val} / {max}</span>
    </div>
  );
}
/* deterministic pseudo-random cells so both themes render identical maps */
export function ncMapCells(n = 280, seed = 7): string[] {
  const states = ['', '', '', 'building', 'solid', 'solid', 'mastered', 'due', 'fragile', 'solid', 'mastered', '', 'building', 'mastered'];
  const out: string[] = []; let x = seed;
  for (let i = 0; i < n; i++) { x = (x * 48271) % 2147483647; out.push(states[(x + (i < n * 0.4 ? 5 : 0)) % states.length]); }
  return out;
}
export type NcMapTotal = { id: string; label: string; n: number };
export function NcMasteryMap({ cells, totals, note }: { cells: string[]; totals: NcMapTotal[]; note?: string | null }) {
  return (
    <>
      <div className="nc-map" aria-hidden="true">{cells.map((s, i) => <i key={i} className={s} />)}</div>
      <div className="nc-maplegend" aria-label="Répartition des états">
        {totals.map((t) => <span key={t.id || t.label}><i className={t.id} />{t.label} {t.n}</span>)}
      </div>
      {note && <p className="nc-mapnote">{note}</p>}
    </>
  );
}

/* ---------- system: notice / skeleton / empty ---------- */
export function NcNotice({ tone = 'red', label = 'Avis du bureau des archives', message, retry = true, onRetry }: { tone?: 'red' | 'blue' | 'yellow'; label?: string; message: string; retry?: boolean; onRetry?: () => void }) {
  return (
    <div className="nc-notice" role="alert">
      <span className={'sq ' + tone} />
      <span className="body"><b>{label}</b><p>{message}</p></span>
      {retry && <button type="button" className="retry" onClick={onRetry}>Réessayer</button>}
    </div>
  );
}
/* press/file skeleton — index rows setting into the ledger, never a spinner */
export function NcSkeleton({ rows = 5, file = true }: { rows?: number; file?: boolean }) {
  return (
    <div className="nc-skel" aria-hidden="true">
      {file && <div className="filecard" />}
      <div className="ln k" style={{ marginTop: 16 }} />
      {Array.from({ length: rows }, (_, i) => (
        <div className="srow" key={i}>
          <span className="ln no" />
          <span><span className="ln t" style={{ width: (82 - (i * 13) % 34) + '%' }} /><span className="ln" style={{ width: '44%', height: 8 }} /></span>
          <span className="ln" style={{ width: 46, height: 14 }} />
        </div>
      ))}
    </div>
  );
}
export function NcEmpty({ title = 'Aucune fiche dans ce classement', body, action, onAction }: { title?: string; body?: string | null; action?: string | null; onAction?: () => void }) {
  return (
    <div className="nc-empty">
      <span className="mark" aria-hidden="true" />
      <h4>{title}</h4>
      {body && <p>{body}</p>}
      {action && <button type="button" className="act" onClick={onAction}>{action}</button>}
    </div>
  );
}
export function NcColophon({ text = 'Les Cahiers · référence de l’édition' }: { text?: string }) {
  return <div className="nc-colophon">{text}</div>;
}

/* ---------- crumb / entry head / CTA (fiche detail scaffolding) ---------- */
export function NcCrumb({ label, index, onBack }: { label: string; index?: string | null; onBack?: () => void }) {
  return (
    <button type="button" className="nc-crumb" onClick={onBack}>
      <NcIcoBack /> {label}{index ? <> · <b>{index}</b></> : null}
    </button>
  );
}
export function NcCta({ children, href = '#', quiet = false, onClick }: { children: React.ReactNode; href?: string; quiet?: boolean; onClick?: () => void }) {
  return (
    <Link className={'nc-cta' + (quiet ? ' quiet' : '')} href={href} onClick={onClick}>
      {children} <NcIcoArrow />
    </Link>
  );
}

/* ============================================================
   Styles — ported from cahiers.css; `.nc` inherits global --app-*
   tokens (no palette mirror); derived --nc-* values kept.
   ============================================================ */
export function CahiersStyles() {
  return (
    <style jsx global>{`
      .nc {
        --nc-hair: color-mix(in oklab, var(--app-ink) 24%, var(--app-paper));
        --nc-wash: color-mix(in oklab, var(--app-paper-2) 70%, var(--app-sheet));
        --nc-half: color-mix(in oklab, var(--app-ink) 55%, var(--app-paper));
        --nc-fragile: color-mix(in oklab, var(--app-red) 45%, var(--app-paper));
        --nc-scrim: color-mix(in oklab, var(--app-ink) 45%, transparent);
        --nc-halo: color-mix(in oklab, var(--app-yellow) 45%, transparent);
        position: relative;
        width: min(var(--app-viewport-width, 100vw), var(--phone-shell-max, 430px));
        margin: 0 auto;
        min-height: var(--app-viewport-height, 100vh);
        background: var(--app-paper); color: var(--app-ink);
        font-family: var(--app-grotesk); -webkit-font-smoothing: antialiased;
        padding-top: var(--phone-safe-top, 0px);
      }
      /* Flow variant: drop the phone-shell width/background so the primitives
         can nest inside an existing scoped container (e.g. the vocabulary
         page's .vocab-page, which keeps its own detail-sheet styles). */
      .nc.nc-flow { width: 100%; max-width: 430px; margin: 0; min-height: 0; background: transparent; padding-top: 0; }
      .nc.nc-flow > .nc-page { padding: 0; }
      .nc * { box-sizing: border-box; }
      /* Element-scoped resets (.nc button = class + type) outrank every
         component class (.nc-chip = one class), so chips and rows lost their
         border, padding and type. Wrapping the reset in :where() keeps it at
         zero specificity, which is what a reset should have been all along. */
      .nc :where(a, button, input, textarea) { font: inherit; color: inherit; text-align: inherit; }
      .nc :where(button) { border: 0; background: transparent; padding: 0; cursor: pointer; }
      .nc :where(a) { text-decoration: none; }
      .nc :is(a,button,input,textarea):focus-visible { outline: 2px solid var(--app-ink); outline-offset: 2px; box-shadow: 0 0 0 5px var(--nc-halo); }
      .nc-page { padding: 0 18px calc(var(--phone-bottom-nav-space, 84px) + 8px); min-width: 0; }

      /* ---- ears + masthead ---- */

      .nc-mast { text-align: center; padding-top: 2px; }
      /* One quiet line, like La Une's folio: the app masthead already carries
         the brand and the gear, so the notebook only states what it tracks. */
      .nc-mast .folio { padding: 14px 0 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: var(--t-small); color: var(--app-ink-3); }
      .nc-mast .folio .folio-gear { width: 44px; height: 44px; margin-left: auto; margin-right: -10px; display: grid; place-items: center; color: var(--app-ink-3); }
      .nc-mast .folio .folio-gear svg { width: 18px; height: 18px; }
      .nc-mast .folio b { color: var(--app-ink-2); font-weight: 600; white-space: nowrap; }
      .nc-mast .folio .off { color: var(--app-ink-3); font-style: italic; text-transform: none; letter-spacing: .02em; font-weight: 700; font-family: var(--app-serif); font-size: var(--t-small); }
      .nc-mast.slim { text-align: left; padding-top: 10px; border-bottom: 3px double var(--app-ink); padding-bottom: 8px; display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
      .nc-mast.slim .rub { font-size: var(--t-label); font-weight: 900; letter-spacing: .18em; text-transform: uppercase; color: var(--app-red); }
      .nc-mast.slim .rub b { color: var(--app-ink); }
      .nc-mast.slim .xlink { font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); border-bottom: 1px solid var(--nc-hair); padding-bottom: 2px; white-space: nowrap; }

      /* ---- mode tabs — file dividers ---- */
      .nc-modetabs { margin-top: 14px; display: flex; align-items: flex-end; gap: 4px; border-bottom: 1.5px solid var(--app-ink); }
      .nc-modetabs .nc-tab { flex: 1 1 0; min-height: 46px; border: 1.5px solid var(--app-ink); border-bottom: 0; background: var(--app-paper-2); color: var(--app-ink-2); padding: 7px 6px 6px; display: grid; gap: 2px; align-content: center; text-align: center; }
      .nc-modetabs .nc-tab .m { font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
      .nc-modetabs .nc-tab .s { font-size: var(--t-label); font-weight: 700; letter-spacing: .04em; color: var(--app-ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .nc-modetabs .nc-tab[aria-selected="true"] { background: var(--app-sheet); color: var(--app-ink); min-height: 52px; box-shadow: inset 0 3px 0 var(--app-red); }
      .nc-modetabs .nc-tab[aria-selected="true"] .s { color: var(--app-ink-2); }

      /* ---- filing summary strip ---- */
      .nc-filing { display: flex; align-items: center; gap: 8px; padding: 9px 0; border-bottom: 1px solid var(--nc-hair); font-size: var(--t-label); font-weight: 800; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-2); flex-wrap: wrap; }
      .nc-filing .k { color: var(--app-ink-3); }
      .nc-filing .sep { width: 3px; height: 3px; background: var(--app-ink-3); border-radius: 50%; flex: 0 0 auto; }
      .nc-filing .due { color: var(--app-ink-2); font-weight: 700; }
      .nc-filing .era { color: var(--app-blue); }

      /* ---- optional feuilleton file ---- */
      .nc-feuille { margin-top: 12px; display: grid; grid-template-columns: 10px minmax(0,1fr) auto; gap: 12px; align-items: center; border: 1px solid var(--app-ink); background: var(--app-sheet); padding: 10px 12px 10px 0; color: var(--app-ink); }
      .nc-feuille .spine { align-self: stretch; background: var(--app-blue); border-right: 1px solid var(--app-ink); }
      .nc-feuille .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-blue); }
      .nc-feuille .t { margin-top: 2px; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-body); line-height: 1.08; }
      .nc-feuille .go { font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-2); white-space: nowrap; }

      /* ---- search + filter chips + live summary ---- */
      .nc-search { margin-top: 14px; display: grid; grid-template-columns: auto minmax(0,1fr); align-items: center; gap: 9px; border: 1px solid var(--app-ink); background: var(--app-sheet); padding: 0 12px; min-height: 46px; }
      .nc-search svg { width: 16px; height: 16px; color: var(--app-ink-3); }
      .nc-search input { border: 0 !important; background: transparent; box-shadow: none !important; padding: 10px 0; font-size: var(--t-body); min-width: 0; outline: 0; }
      .nc-search input::placeholder { color: var(--app-ink-3); font-style: italic; font-family: var(--app-serif); font-size: var(--t-body); }
      .nc-chips { margin-top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
      .nc-chip { min-height: 44px; padding: 0 13px; border: 1px solid var(--app-ink); background: var(--app-paper); font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-2); display: inline-flex; align-items: center; gap: 6px; }
      .nc-chip[aria-pressed="true"] { background: var(--app-ink); color: var(--app-paper); }
      .nc-chip .n { font-weight: 800; color: var(--app-ink-3); letter-spacing: 0; }
      .nc-chip[aria-pressed="true"] .n { color: var(--app-paper-3); }
      .nc-livesum { margin-top: 9px; min-height: 30px; display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: var(--t-label); font-weight: 700; color: var(--app-ink-2); }
      .nc-livesum em { font-family: var(--app-serif); font-style: italic; font-size: var(--t-small); }
      .nc-livesum .clear { min-height: 30px; padding: 0 9px; border: 1px solid var(--app-ink); font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }

      /* ---- ledger section head ---- */
      .nc-ledghead { margin-top: 18px; padding-bottom: 6px; border-bottom: 2px solid var(--app-ink); display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
      .nc-ledghead .t { font-size: var(--t-label); font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-ledghead .t.blue { color: var(--app-blue); }
      .nc-ledghead .t.mut { color: var(--app-ink-3); }
      .nc-ledghead .n { font-size: var(--t-label); font-weight: 800; letter-spacing: .06em; color: var(--app-ink-3); font-variant-numeric: tabular-nums; }

      /* ---- grammar index rows ---- */
      .nc-index { display: grid; }
      .nc-row { position: relative; display: grid; grid-template-columns: 34px minmax(0,1fr) auto; gap: 0 10px; align-items: center; width: 100%; min-height: 60px; padding: 11px 0; border-bottom: 1px solid var(--nc-hair); text-align: left; }
      .nc-row .no { align-self: start; padding-top: 2px; font-size: var(--t-label); font-weight: 800; letter-spacing: .04em; color: var(--app-ink-3); font-variant-numeric: tabular-nums; }
      .nc-row .t { font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-lead); line-height: 1.1; color: var(--app-ink); overflow-wrap: anywhere; }
      .nc-row .meta { grid-column: 2; margin-top: 4px; font-size: var(--t-label); font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
      .nc-row .marks { grid-column: 3; grid-row: 1 / span 2; display: grid; gap: 5px; justify-items: end; align-self: center; }
      .nc-row:active { background: var(--app-paper-2); }
      .nc-row.sel { background: var(--app-sheet); box-shadow: inset 3px 0 0 var(--app-red); padding-left: 10px; margin-left: -10px; border-bottom-color: var(--app-ink); }
      .nc-row .lead { flex: 1 1 8px; min-width: 8px; height: 1px; background-image: radial-gradient(circle, var(--app-ink-3) 34%, transparent 40%); background-size: 5px 2px; background-repeat: repeat-x; background-position: 0 50%; align-self: center; }
      .nc-pips { display: inline-flex; gap: 2px; }
      .nc-pips i { width: 4px; height: 9px; background: var(--app-paper-3); }
      .nc-pips i.on { background: var(--app-ink); }
      .nc-due { display: inline-block; border: 1.5px solid var(--app-red); color: var(--app-ink); padding: 2px 6px 1px; font-size: var(--t-label); font-weight: 700; letter-spacing: .12em; text-transform: uppercase; transform: rotate(-2deg); white-space: nowrap; }
      .nc-stamp { display: inline-block; border: 1px solid currentColor; padding: 2px 6px 1px; font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--app-ink-3); white-space: nowrap; }
      .nc-stamp.solid { color: var(--app-ink); background: var(--app-sheet); }
      .nc-stamp.mastered { color: var(--app-paper); background: var(--app-ink); border-color: var(--app-ink); }
      .nc-stamp.fragile { color: var(--app-red); }
      .nc-stamp.building { color: var(--app-blue); }
      .nc-errdot { display: inline-flex; align-items: center; gap: 4px; font-size: var(--t-label); font-weight: 900; letter-spacing: .08em; color: var(--app-blue); }
      .nc-errdot i { width: 0; height: 0; border-style: solid; border-width: 0 4.5px 8px; border-color: transparent transparent var(--app-blue); }

      /* ---- entry detail (la fiche) ---- */
      .nc-crumb { margin-top: 12px; display: flex; align-items: center; gap: 8px; min-height: 44px; font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-crumb svg { width: 14px; height: 14px; }
      .nc-crumb b { color: var(--app-ink); }
      .nc-entryhead { position: relative; border-bottom: 2px solid var(--app-ink); padding-bottom: 12px; }
      .nc-entryhead .tags { display: flex; gap: 6px; flex-wrap: wrap; }
      .nc-tagchip { border: 1px solid var(--app-ink); background: var(--app-sheet); padding: 3px 7px 2px; font-size: var(--t-label); font-weight: 900; letter-spacing: .13em; text-transform: uppercase; display: inline-flex; align-items: center; gap: 5px; }
      .nc-tagchip i { width: 7px; height: 7px; }
      .nc-tagchip.lvl i { background: var(--app-yellow); }
      .nc-tagchip.cat i { background: var(--app-blue); }
      .nc-entryhead h2 { margin: 9px 0 0; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-head); line-height: 1.02; text-wrap: pretty; }
      .nc-entryhead .row2 { margin-top: 10px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: var(--t-label); font-weight: 800; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-2); }
      .nc-entryhead .row2 .nxt { color: var(--app-ink-3); }
      .nc-entryhead .bigpips { display: inline-flex; gap: 3px; }
      .nc-entryhead .bigpips i { width: 6px; height: 13px; background: var(--app-paper-3); }
      .nc-entryhead .bigpips i.on { background: var(--app-ink); }
      .nc-sec { padding: 14px 0 15px; border-bottom: 1px solid var(--nc-hair); }
      .nc-sec .kick { display: flex; align-items: center; gap: 8px; font-size: var(--t-label); font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-sec .kick.blue { color: var(--app-blue); }
      .nc-sec .kick.mut { color: var(--app-ink-3); }
      .nc-sec .kick .tail { flex: 1; height: 1px; background: var(--nc-hair); }
      .nc-sec .kick .ct { font-size: var(--t-label); color: var(--app-ink-3); letter-spacing: .06em; }
      .nc-sec .body { margin-top: 8px; font-size: var(--t-small); line-height: 1.45; color: var(--app-ink); }
      .nc-rulebox { margin-top: 9px; border-left: 3px solid var(--app-ink); padding: 2px 0 2px 12px; font-family: var(--app-serif); font-size: var(--t-body); line-height: 1.3; font-style: italic; }
      .nc-ex { margin-top: 10px; display: grid; gap: 2px; }
      .nc-ex .fr { font-family: var(--app-serif); font-style: italic; font-size: var(--t-body); line-height: 1.25; }
      .nc-ex .fr b { color: var(--app-blue); font-weight: 700; }
      .nc-ex .de { font-size: var(--t-small); color: var(--app-ink-3); line-height: 1.35; }
      .nc-trap { margin-top: 9px; display: grid; grid-template-columns: 14px minmax(0,1fr); gap: 8px; font-size: var(--t-small); line-height: 1.4; color: var(--app-ink-2); }
      .nc-trap i { width: 0; height: 0; margin-top: 3px; border-style: solid; border-width: 0 6px 11px; border-color: transparent transparent var(--app-red); }
      .nc-motif { margin-top: 9px; border: 1px solid var(--app-ink); background: var(--app-sheet); padding: 10px 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: var(--t-small); line-height: 1.5; color: var(--app-ink); overflow-wrap: anywhere; }
      .nc-motif .bp { display: flex; justify-content: space-between; gap: 10px; margin-top: 8px; padding-top: 7px; border-top: 1px solid var(--nc-hair); font-family: var(--app-grotesk); font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-motif .bp b { color: var(--app-blue); }
      .nc-errow { display: grid; grid-template-columns: 14px minmax(0,1fr) auto; gap: 9px; align-items: baseline; padding: 9px 0; border-bottom: 1px solid var(--nc-hair); }
      .nc-errow:last-child { border-bottom: 0; }
      .nc-errow i { width: 0; height: 0; align-self: center; border-style: solid; border-width: 0 5px 9px; border-color: transparent transparent var(--app-red); }
      .nc-errow.recent i { border-bottom-color: var(--app-ink-3); }
      .nc-errow .q { font-family: var(--app-serif); font-style: italic; font-size: var(--t-body); line-height: 1.25; }
      .nc-errow .q s { text-decoration-color: var(--app-red); }
      .nc-errow .q b { font-style: normal; font-weight: 700; color: var(--app-ink-2); }
      .nc-errow .d { font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-3); white-space: nowrap; }

      /* ---- notes en marge ---- */
      .nc-notes { margin-top: 9px; border: 1px dashed var(--app-ink-3); background: var(--app-sheet); padding: 11px 12px; }
      .nc-notes .txt { font-family: var(--app-serif); font-style: italic; font-size: var(--t-body); line-height: 1.4; color: var(--app-ink-2); }
      .nc-notes .txt.ph { color: var(--app-ink-3); }
      .nc-notes .bar { margin-top: 9px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
      .nc-notes .act { min-height: 44px; padding: 0 18px; border-radius: 999px; border: 1px solid var(--app-ink); background: transparent; color: var(--app-ink); font-size: var(--t-small); font-weight: 600; letter-spacing: .01em; text-transform: none; transition: background .16s ease, color .16s ease; }
      .nc-notes .act:active { background: var(--app-paper-2); color: var(--app-ink); }
      .nc-notes .act:disabled { opacity: .5; }
      .nc-notes .st { font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-notes.editing { border-style: solid; border-color: var(--app-ink); background: var(--app-paper); }
      .nc-notes textarea { display: block; width: 100%; min-height: 84px; resize: vertical; border: 1px solid var(--app-ink) !important; background: var(--app-sheet); padding: 9px 10px; font-family: var(--app-serif); font-style: italic; font-size: var(--t-body); line-height: 1.4; box-shadow: none !important; }
      .nc-notes .act.primary { background: var(--app-ink); color: var(--app-paper); }
      .nc-notes .act.primary:active { background: var(--app-paper-2); color: var(--app-ink); }
      .nc-notes.saving .st, .nc-notes .st.dirty { color: var(--app-blue); }
      .nc-notes.err { border-color: var(--app-red); border-style: solid; }
      .nc-notes .st.bad { color: var(--app-red); }

      /* ---- dominant CTA into the Atelier ---- */
      /* Primary action, soft: pill geometry, solid ink on paper, sentence case. */
      .nc-cta { margin-top: 16px; display: flex; align-items: center; justify-content: center; gap: 11px; width: 100%; min-height: 54px; padding: 0 22px; border-radius: 999px; background: var(--app-ink); color: var(--app-paper); border: 1px solid var(--app-ink); font-size: var(--t-body); font-weight: 600; letter-spacing: .01em; text-transform: none; transition: background .16s ease, color .16s ease; }
      .nc-cta:active { background: var(--app-paper-2); color: var(--app-ink); }
      .nc-cta svg { width: 16px; height: 16px; }
      /* Outlined sibling: same pill, transparent fill, ink keyline. */
      .nc-cta.quiet { background: transparent; color: var(--app-ink); border-color: var(--app-ink); }
      .nc-cta.quiet:active { background: var(--app-paper-2); color: var(--app-ink); }
      .nc-exercisetags { margin-top: 9px; display: flex; gap: 6px; flex-wrap: wrap; }
      .nc-exercisetags span { border: 1px solid var(--nc-hair); background: var(--app-paper); padding: 3px 8px 2px; font-size: var(--t-label); font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--app-ink-2); }

      /* ---- vocabulary: next set, queue + ledger ---- */
      .nc-next { margin-top: 14px; border: 1.5px solid var(--app-ink); background: var(--app-sheet); padding: 12px 14px 14px; }
      .nc-next .k { display: flex; justify-content: space-between; gap: 10px; font-size: var(--t-label); font-weight: 900; letter-spacing: .16em; text-transform: uppercase; color: var(--app-red); }
      .nc-next .k .why { color: var(--app-ink-3); letter-spacing: .06em; }
      .nc-next .words { margin-top: 9px; display: flex; gap: 7px; flex-wrap: wrap; }
      .nc-next .w { border: 1px solid var(--app-ink); background: var(--app-paper); padding: 6px 10px 5px; min-height: 44px; display: inline-flex; flex-direction: column; justify-content: center; }
      .nc-next .w b { font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-body); line-height: 1; }
      .nc-next .w span { margin-top: 2px; font-size: var(--t-label); font-weight: 800; letter-spacing: .04em; color: var(--app-ink-3); }
      .nc-wordrow { display: grid; grid-template-columns: 40px minmax(0,1fr) auto; gap: 0 10px; align-items: center; width: 100%; min-height: 58px; padding: 9px 0; border-bottom: 1px solid var(--nc-hair); text-align: left; }
      .nc-wordrow .rank { align-self: start; margin-top: 1px; display: inline-grid; place-items: center; min-width: 32px; min-height: 20px; border: 1px solid var(--nc-hair); font-size: var(--t-label); font-weight: 800; color: var(--app-ink-3); font-variant-numeric: tabular-nums; }
      .nc-wordrow .w { font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-body); line-height: 1.05; overflow-wrap: anywhere; }
      .nc-wordrow .tr { grid-column: 2; margin-top: 3px; font-size: var(--t-small); font-weight: 600; color: var(--app-ink-3); line-height: 1.3; overflow-wrap: anywhere; }
      .nc-wordrow .marks { grid-column: 3; grid-row: 1 / span 2; display: grid; gap: 4px; justify-items: end; }
      .nc-wordrow:active { background: var(--app-paper-2); }
      .nc-wordrow.sel { background: var(--app-sheet); box-shadow: inset 3px 0 0 var(--app-blue); padding-left: 10px; margin-left: -10px; }
      .nc-bucket { display: inline-flex; align-items: center; gap: 5px; font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-bucket i { width: 8px; height: 8px; border: 1px solid var(--app-ink); background: var(--app-paper-2); flex: 0 0 auto; }
      .nc-bucket.due i { background: var(--app-red); }
      .nc-bucket.fragile i { background: var(--nc-fragile); }
      .nc-bucket.new i { background: var(--app-yellow); }
      .nc-bucket.building i { background: var(--app-yellow); }
      .nc-bucket.solid i { background: var(--app-blue); }
      .nc-bucket.mastered i { background: var(--app-ink); }

      /* ---- atlas fold (progressive disclosure band) ---- */
      .nc-fold { margin-top: 16px; width: 100%; border: 1.5px solid var(--app-ink); background: var(--app-paper-2); display: grid; grid-template-columns: minmax(0,1fr) auto; align-items: center; gap: 10px; padding: 11px 14px; min-height: 54px; text-align: left; }
      .nc-fold .t { font-size: var(--t-label); font-weight: 900; letter-spacing: .15em; text-transform: uppercase; color: var(--app-ink); }
      .nc-fold .s { margin-top: 3px; font-size: var(--t-label); font-weight: 700; color: var(--app-ink-2); }
      .nc-fold .chev { font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-2); display: inline-flex; align-items: center; gap: 6px; }
      .nc-fold .chev svg { width: 13px; height: 13px; }
      .nc-track { display: grid; grid-template-columns: 52px minmax(0,1fr) 64px; align-items: center; gap: 9px; padding: 6px 0; }
      .nc-track .lab { font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-track .bar { height: 5px; background: var(--app-paper-3); position: relative; }
      .nc-track .bar i { position: absolute; inset: 0 auto 0 0; background: var(--app-blue); }
      .nc-track .bar i.red { background: var(--app-red); }
      .nc-track .bar i.ink { background: var(--app-ink); }
      .nc-track .num { font-size: var(--t-label); font-weight: 800; color: var(--app-ink-2); text-align: right; font-variant-numeric: tabular-nums; }
      .nc-map { margin-top: 10px; border: 1px solid var(--app-ink); background: var(--app-paper); padding: 8px; display: grid; grid-template-columns: repeat(40, 1fr); gap: 2px; }
      .nc-map i { display: block; aspect-ratio: 1; background: var(--app-paper-2); }
      .nc-map i.due { background: var(--app-red); }
      .nc-map i.fragile { background: var(--nc-fragile); }
      .nc-map i.building { background: var(--app-yellow); }
      .nc-map i.solid { background: var(--app-blue); }
      .nc-map i.mastered { background: var(--app-ink); }
      .nc-maplegend { margin-top: 9px; display: flex; flex-wrap: wrap; gap: 6px 12px; font-size: var(--t-label); font-weight: 800; letter-spacing: .06em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-maplegend span { display: inline-flex; align-items: center; gap: 5px; font-variant-numeric: tabular-nums; }
      .nc-maplegend i { width: 9px; height: 9px; border: 1px solid var(--app-ink); background: var(--app-paper-2); }
      .nc-maplegend i.due { background: var(--app-red); } .nc-maplegend i.fragile { background: var(--nc-fragile); } .nc-maplegend i.building { background: var(--app-yellow); } .nc-maplegend i.solid { background: var(--app-blue); } .nc-maplegend i.mastered { background: var(--app-ink); }
      .nc-mapnote { margin-top: 8px; font-size: var(--t-label); line-height: 1.4; color: var(--app-ink-3); font-style: italic; font-family: var(--app-serif); }

      /* ---- dossier de la semaine ---- */
      .nc-dossier { margin-top: 16px; border: 1px solid var(--app-ink); background: var(--app-sheet); padding: 12px 14px 14px; }
      .nc-dossier .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .16em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-dossier h3 { margin: 6px 0 0; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-lead); line-height: 1.1; }
      .nc-dossier dl { display: grid; grid-template-columns: repeat(4, 1fr); margin: 11px 0 0; border: 1px solid var(--app-ink); background: var(--app-paper); }
      .nc-dossier dl > div { min-width: 0; padding: 8px 9px; border-right: 1px solid var(--app-ink); }
      .nc-dossier dl > div:last-child { border-right: 0; }
      .nc-dossier dt { font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-dossier dd { margin: 3px 0 0; font-family: var(--app-serif); font-style: italic; font-weight: 700; font-size: var(--t-lead); line-height: 1; }
      .nc-dossier .thread { margin-top: 9px; border-left: 3px solid var(--app-red); background: var(--app-paper); padding: 8px 10px; }
      .nc-dossier .thread b { display: block; font-size: var(--t-small); font-weight: 800; }
      .nc-dossier .thread em { display: block; margin-top: 2px; font-style: normal; font-size: var(--t-label); color: var(--app-ink-3); font-weight: 700; line-height: 1.3; }

      /* ---- word entry sheet (bottom sheet) ---- */
      .nc-sheetstage { position: fixed; inset: 0; z-index: 60; display: flex; flex-direction: column; justify-content: flex-end; }
      .nc-sheetstage .scrim { position: absolute; inset: 0; background: var(--nc-scrim); border: 0; }
      .nc-sheet { position: relative; width: min(var(--app-viewport-width, 100vw), var(--phone-shell-max, 430px)); margin: 0 auto; border-top: 1.5px solid var(--app-ink); background: var(--app-paper); padding: 10px 18px calc(16px + var(--phone-safe-bottom, 12px)); box-shadow: 0 -18px 40px var(--nc-scrim); max-height: 88vh; overflow-y: auto; }
      .nc-sheet .grab { width: 44px; height: 4px; margin: 0 auto 12px; background: var(--app-ink-3); border-radius: 999px; }
      .nc-sheet .shead { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; border-bottom: 2px solid var(--app-ink); padding-bottom: 12px; }
      .nc-sheet .shead .k { font-size: var(--t-label); font-weight: 900; letter-spacing: .16em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-sheet .shead h2 { margin: 4px 0 0; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-display); line-height: .95; overflow-wrap: anywhere; }
      .nc-sheet .shead .tr { margin-top: 6px; font-size: var(--t-small); font-weight: 700; color: var(--app-ink-2); }
      .nc-sheet .shead .x { flex: 0 0 auto; width: 44px; height: 44px; border: 1px solid var(--app-ink); background: var(--app-sheet); display: grid; place-items: center; }
      .nc-sheet .shead .x svg { width: 16px; height: 16px; }
      .nc-metagrid { margin-top: 12px; display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid var(--app-ink); background: var(--app-sheet); }
      .nc-metagrid > div { min-width: 0; padding: 8px 10px; border-right: 1px solid var(--nc-hair); }
      .nc-metagrid > div:last-child { border-right: 0; }
      .nc-metagrid b { display: block; font-family: var(--app-serif); font-style: italic; font-weight: 700; font-size: var(--t-body); line-height: 1; overflow-wrap: anywhere; }
      .nc-metagrid span { display: block; margin-top: 3px; font-size: var(--t-label); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-fragnote { margin-top: 10px; border: 1.5px solid var(--app-red); background: var(--app-paper); padding: 9px 11px; display: grid; grid-template-columns: auto minmax(0,1fr); gap: 9px; align-items: baseline; }
      .nc-fragnote .tag { font-size: var(--t-label); font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-red); border: 1px solid var(--app-red); padding: 2px 5px 1px; transform: rotate(-2deg); white-space: nowrap; }
      .nc-fragnote p { margin: 0; font-size: var(--t-small); line-height: 1.4; color: var(--app-ink-2); }
      .nc-ratings { margin-top: 12px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; }
      .nc-ratings button { min-height: 52px; border: 1.5px solid var(--app-ink); background: var(--app-sheet); display: grid; gap: 1px; align-content: center; justify-items: center; padding: 6px 4px; }
      .nc-ratings button b { font-size: var(--t-label); font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
      .nc-ratings button span { font-size: var(--t-label); font-weight: 800; letter-spacing: .04em; color: var(--app-ink-3); text-align: center; }
      .nc-ratings button.again { box-shadow: inset 0 -3px 0 var(--app-red); }
      .nc-ratings button.hard { box-shadow: inset 0 -3px 0 var(--app-yellow); }
      .nc-ratings button.good { box-shadow: inset 0 -3px 0 var(--app-blue); }
      .nc-ratings button.easy { box-shadow: inset 0 -3px 0 var(--app-ink); }
      .nc-ratings button[disabled] { opacity: .45; }
      .nc-seedacts { margin-top: 12px; display: grid; gap: 7px; }
      .nc-seedacts a { display: grid; grid-template-columns: minmax(0,1fr) auto; align-items: center; gap: 10px; min-height: 46px; border: 1px solid var(--app-ink); background: var(--app-paper); padding: 0 12px; font-size: var(--t-label); font-weight: 900; letter-spacing: .12em; text-transform: uppercase; }
      .nc-seedacts a em { font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-small); text-transform: none; letter-spacing: 0; color: var(--app-ink-3); justify-self: end; }
      /* biography timeline */
      .nc-bio { margin-top: 10px; }
      .nc-bio .ev { position: relative; display: grid; grid-template-columns: 20px minmax(0,1fr) auto; gap: 9px; padding: 9px 0; }
      .nc-bio .ev::before { content: ""; position: absolute; left: 5px; top: 0; bottom: 0; border-left: 1.5px solid var(--nc-hair); }
      .nc-bio .ev:first-child::before { top: 14px; }
      .nc-bio .ev:last-child::before { bottom: calc(100% - 20px); }
      .nc-bio .ev i { position: relative; z-index: 1; width: 11px; height: 11px; margin-top: 4px; background: var(--app-paper); border: 1.5px solid var(--app-ink); }
      .nc-bio .ev.good i { background: var(--app-blue); }
      .nc-bio .ev.bad i { background: var(--app-red); }
      .nc-bio .ev.first i { background: var(--app-yellow); }
      .nc-bio .ev .b b { display: block; font-size: var(--t-small); font-weight: 800; line-height: 1.25; }
      .nc-bio .ev .b em { display: block; margin-top: 1px; font-family: var(--app-serif); font-style: italic; font-size: var(--t-small); color: var(--app-ink-2); line-height: 1.3; }
      .nc-bio .ev .d { font-size: var(--t-label); font-weight: 900; letter-spacing: .08em; text-transform: uppercase; color: var(--app-ink-3); white-space: nowrap; }

      /* ---- bibliothèque ---- */
      .nc-book { display: grid; grid-template-columns: 14px minmax(0,1fr) auto; gap: 12px; align-items: center; width: 100%; min-height: 66px; padding: 12px 12px 12px 0; border: 1px solid var(--app-ink); background: var(--app-sheet); margin-top: 10px; text-align: left; }
      .nc-book .spine { align-self: stretch; border-right: 1px solid var(--app-ink); background: var(--app-blue); }
      .nc-book.b2 .spine { background: var(--app-red); }
      .nc-book.b3 .spine { background: var(--app-yellow); }
      .nc-book .t { font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-lead); line-height: 1.05; }
      .nc-book .m { margin-top: 3px; font-size: var(--t-label); font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
      .nc-book .pr { display: grid; gap: 4px; justify-items: end; }
      .nc-book .pr .pct { font-family: var(--app-serif); font-style: italic; font-weight: 700; font-size: var(--t-body); }
      .nc-book .pr .bar { width: 54px; height: 4px; background: var(--app-paper-3); position: relative; }
      .nc-book .pr .bar i { position: absolute; inset: 0 auto 0 0; background: var(--app-ink); }

      /* ---- system: notice, skeleton, empty ---- */
      .nc-notice { margin-top: 14px; border: 1.5px solid var(--app-ink); background: var(--app-paper-2); display: grid; grid-template-columns: auto minmax(0,1fr) auto; gap: 12px; align-items: center; padding: 11px 12px; }
      .nc-notice .sq { width: 12px; height: 12px; background: var(--app-red); border: 1px solid var(--app-ink); }
      .nc-notice .sq.blue { background: var(--app-blue); }
      .nc-notice .sq.yellow { background: var(--app-yellow); }
      .nc-notice .body b { display: block; font-size: var(--t-label); font-weight: 900; letter-spacing: .15em; text-transform: uppercase; }
      .nc-notice .body p { margin: 3px 0 0; font-size: var(--t-small); line-height: 1.4; color: var(--app-ink-2); }
      .nc-notice .retry { min-height: 44px; padding: 0 18px; border-radius: 999px; border: 1px solid var(--app-ink); background: var(--app-ink); color: var(--app-paper); font-size: var(--t-small); font-weight: 600; letter-spacing: .01em; text-transform: none; transition: background .16s ease, color .16s ease; }
      .nc-notice .retry:active { background: var(--app-paper-2); color: var(--app-ink); }
      .nc-notice.inline { grid-template-columns: auto minmax(0,1fr); }
      .nc-skel { pointer-events: none; }
      .nc-skel .ln { background: var(--app-paper-3); height: 11px; margin-top: 8px; }
      .nc-skel .ln.t { height: 17px; }
      .nc-skel .ln.k { height: 8px; width: 34%; background: var(--nc-wash); border: 1px solid var(--app-paper-3); }
      .nc-skel .ln.no { width: 26px; height: 9px; }
      .nc-skel .filecard { margin-top: 10px; border: 1px solid var(--app-paper-3); background: var(--nc-wash); height: 52px; }
      .nc-skel .srow { display: grid; grid-template-columns: 34px minmax(0,1fr) auto; gap: 10px; align-items: center; padding: 13px 0; border-bottom: 1px solid var(--nc-hair); }
      .nc-skel .srow .ln { margin-top: 0; }
      @media (prefers-reduced-motion: no-preference) {
        .nc-skel .ln, .nc-skel .filecard { animation: nc-set 1.4s ease-in-out infinite; }
      }
      @keyframes nc-set { 0%,100% { opacity: 1; } 50% { opacity: .55; } }
      .nc-empty { margin-top: 14px; border: 1px dashed var(--app-ink-3); background: var(--app-sheet); padding: 22px 18px; text-align: center; }
      .nc-empty .mark { width: 12px; height: 12px; background: var(--app-ink); margin: 0 auto; }
      .nc-empty h4 { margin: 12px 0 0; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-lead); line-height: 1.15; }
      .nc-empty p { margin: 7px auto 0; max-width: 250px; font-size: var(--t-small); line-height: 1.45; color: var(--app-ink-2); }
      .nc-empty .act { margin-top: 13px; min-height: 44px; padding: 0 18px; border-radius: 999px; border: 1px solid var(--app-ink); background: transparent; color: var(--app-ink); font-size: var(--t-small); font-weight: 600; letter-spacing: .01em; text-transform: none; transition: background .16s ease, color .16s ease; }
      .nc-empty .act:active { background: var(--app-paper-2); color: var(--app-ink); }

      /* ---- colophon ---- */
      .nc-colophon { margin-top: 18px; text-align: center; font-size: var(--t-label); font-weight: 800; letter-spacing: .2em; text-transform: uppercase; color: var(--app-ink-3); display: flex; align-items: center; gap: 10px; justify-content: center; }
      .nc-colophon::before, .nc-colophon::after { content: ""; flex: 1; height: 1px; background: var(--nc-hair); }
    `}</style>
  );
}
