/* Atelier — L'ÉPREUVE · the grammar session as setting tomorrow's type.
   1:1 port of the design package (epreuve-parts.jsx / epreuve.css, the
   "Atelier L'Epreuve" canvas) into the app's --app-* token system. Every
   component maps onto a real session payload field; the migration note and
   component contract live in docs/overhaul-session.md §5. Interactive parts
   take behaviour handlers so pages/atelier.tsx (SessionView) can wire the
   real session logic — presentation only lives here. Theme-aware (the derived
   --ep-* values are color-mix over --app-ink; --ep-bon lifts in dark). */

import React from 'react';

type Node = React.ReactNode;

/* ---------- press chrome icons ---------- */
export const EpIco: Record<string, React.ReactElement> = {
  close: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="square"><path d="M5 5l14 14M19 5L5 19" /></svg>,
  ask: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 9a3 3 0 1 1 4 2.8c-1 .5-1.5 1-1.5 2.2" /><circle cx="11.5" cy="18" r="1.1" fill="currentColor" stroke="none" /></svg>,
  arrow: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M4 12h15M13 6l6 6-6 6" /></svg>,
  check: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="square"><path d="M4 12.5l5 5 11-12" /></svg>,
  play: <svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M7 4l13 8-13 8z" /></svg>,
  mic: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>,
  home: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 11l8-6 8 6v8H4z" /></svg>,
  book: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 5h7v14H4zM13 5h7v14h-7z" /></svg>,
  pencil: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 20l1-4L16 5l3 3L8 19z" /><path d="M14 7l3 3" /></svg>,
  retry: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M4 11a8 8 0 0 1 14-5l2 2M20 5v4h-4" /></svg>,
};

/* ---------- shell ---------- */
export function EpShell({ children, style, className = '' }: { children: Node; style?: React.CSSProperties; className?: string }) {
  return <div className={`ep ${className}`.trim()} style={style}>{children}</div>;
}

/* ---------- composing stick (progress) ---------- */
export type EpStickGroup = { total: number; set: number; current?: boolean };
export type EpStickLabel = { name: string; state?: string };
export function EpStick({ groups, cap, full, labels }: { groups: EpStickGroup[]; cap?: [string, string | number]; full?: boolean; labels?: EpStickLabel[] }) {
  return (
    <div className={'ep-stick' + (full ? ' full' : '')}>
      <div className="chan">
        {groups.map((g, gi) => (
          <div className="grp" key={gi}>
            {Array.from({ length: g.total }).map((_, i) => {
              const set = i < g.set;
              const cur = g.current && i === g.set;
              return <span key={i} className={'slug' + (set ? ' set' : '') + (cur ? ' cur' : '')} />;
            })}
          </div>
        ))}
      </div>
      {cap && <div className="cap"><span>{cap[0]}</span><span><b>{cap[1]}</b></span></div>}
      {full && labels && (
        <div className="concepts">
          {labels.map((l, i) => <div key={i} className={'c' + (l.state ? ' ' + l.state : '')}>{l.name}</div>)}
        </div>
      )}
    </div>
  );
}

/* ---------- topbar ---------- */
export function EpTopbar({ groups, cap, onClose, onFinish, finishDisabled }: { groups: EpStickGroup[]; cap?: [string, string | number]; onClose?: () => void; onFinish?: () => void; finishDisabled?: boolean }) {
  return (
    <div className="ep-top">
      <button className="ic" title="Fermer" onClick={onClose}>{EpIco.close}</button>
      <EpStick groups={groups} cap={cap} />
      <button className="finish" onClick={onFinish} disabled={finishDisabled}>Terminer</button>
    </div>
  );
}

/* ---------- sheet header ---------- */
export function EpEyebrow({ round, mode, i, n, retour }: { round: string; mode?: string; i: number | string; n: number | string; retour?: boolean }) {
  return (
    <div className="ep-eyebrow">
      <span>{round}</span>{mode && <><i></i><span className="mode">{mode}</span></>}
      {retour && <span className="ep-retour"><span className="d"></span>Retour · déjà corrigé</span>}
      <span className="idx">{i} / {n}</span>
    </div>
  );
}

export function EpProvenance({ children }: { children: Node }) {
  return <div className="ep-prov">{children}</div>;
}

export function EpConcept({ title, motif, askOn, onAsk }: { title: Node; motif?: Node; askOn?: boolean; onAsk?: () => void }) {
  return (
    <div className="ep-concept">
      <div className="ct">
        {motif}
        <h1>{title}</h1>
      </div>
      <button className={'ask' + (askOn ? ' on' : '')} title="Voir la règle" onClick={onAsk}>{EpIco.ask}</button>
    </div>
  );
}

/* ---------- assembling motif ---------- */
export type MotifPrim = { shape: 'circle' | 'square' | 'triangle' | 'block'; cx: number; cy: number; s: number; printed?: boolean; printing?: boolean; role?: string };
function epShape(p: MotifPrim, key: number) {
  const cls = 'shp ' + ({ circle: 'c-circle', square: 'c-square', triangle: 'c-tri', block: 'c-block' }[p.shape]);
  if (p.shape === 'circle') return <circle key={key} className={cls} cx={p.cx} cy={p.cy} r={p.s / 2} />;
  if (p.shape === 'triangle') {
    const half = p.s / 2;
    const pts = `${p.cx},${p.cy - half} ${p.cx + half},${p.cy + half} ${p.cx - half},${p.cy + half}`;
    return <polygon key={key} className={cls} points={pts} />;
  }
  return <rect key={key} className={cls} x={p.cx - p.s / 2} y={p.cy - p.s / 2} width={p.s} height={p.s} />;
}
export function EpMotif({ prims = [], done, canvas = 46 }: { prims?: MotifPrim[]; done?: boolean; canvas?: number }) {
  return (
    <div className={'ep-motif' + (done ? ' done' : '')}>
      <svg viewBox={`0 0 ${canvas} ${canvas}`}>
        {prims.map((p, i) => (
          <g key={i} className={'prim' + (p.printed ? '' : ' ghost') + (p.printing ? ' print-in' : '')}>
            {epShape(p, i)}
          </g>
        ))}
      </svg>
    </div>
  );
}

/* ---------- rule sheet ---------- */
export function EpRule({ kicker = 'La règle', lede, examples = [], onClose }: { kicker?: string; lede?: Node; examples?: Node[]; onClose?: () => void }) {
  return (
    <div className="ep-rule">
      <div className="rh">
        <span className="k">{kicker}</span>
        <button className="x" onClick={onClose}>✕</button>
      </div>
      <div className="rb">
        <div className="lede">{lede}</div>
        {examples.length > 0 && (
          <div className="anchor">
            <div className="c">Exemples d’ancrage</div>
            {examples.map((e, i) => <div className="ex" key={i}>{e}</div>)}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- prompt + cue ---------- */
export function EpPrompt({ label = 'Réglez la ligne', children, cue }: { label?: string; children: Node; cue?: Node }) {
  return (
    <div className="ep-prompt">
      <div className="lab">{label}</div>
      <div className="ep-line">{children}</div>
      {cue && <div className="ep-cue">{cue}</div>}
    </div>
  );
}
export function Blank({ children, set }: { children?: Node; set?: boolean }) {
  return <span className={'blank' + (set ? ' set' : '')}>{children || '    '}</span>;
}

/* ---------- recognize / fill ---------- */
export function EpOpts({ children }: { children: Node }) { return <div className="ep-opts">{children}</div>; }
export function EpOpt({ chosen, right, wrong, children, onClick, disabled }: { chosen?: boolean; right?: boolean; wrong?: boolean; children: Node; onClick?: () => void; disabled?: boolean }) {
  return <button className={'ep-opt' + (chosen ? ' chosen' : '') + (right ? ' right' : '') + (wrong ? ' wrong' : '')} onClick={onClick} disabled={disabled}>{children}</button>;
}
export function EpChoices({ children }: { children: Node }) { return <div className="ep-choices">{children}</div>; }

/* ---------- movable type (word-bank) ---------- */
export function EpSlug({ children, spent, set, onClick, disabled }: { children: Node; spent?: boolean; set?: boolean; onClick?: () => void; disabled?: boolean }) {
  return <button className={'ep-slug' + (spent ? ' spent' : '') + (set ? ' set' : '')} onClick={onClick} disabled={disabled}>{children}</button>;
}
export function EpSetLine({ empty, children }: { empty?: boolean; children?: Node }) {
  return <div className={'ep-setline' + (empty ? ' empty' : '')}>{children}</div>;
}
export function EpCase({ label, count, children }: { label: Node; count?: number | null; children?: Node }) {
  return (
    <div className="ep-case">
      <div className="cap"><span>{label}</span>{count != null && <span>{count} sortes</span>}</div>
      <div className="sorts">{children}</div>
    </div>
  );
}
export function EpCases({ boxes }: { boxes: { label: Node; slugs: Node[] }[] }) {
  return (
    <div className="ep-cases">
      {boxes.map((b, i) => (
        <div className="ep-casebox" key={i}>
          <div className="ch">{b.label}</div>
          <div className="cbody">{b.slugs.map((s, j) => <React.Fragment key={j}>{s}</React.Fragment>)}</div>
        </div>
      ))}
    </div>
  );
}

/* ---------- produce ---------- */
export function EpProduce({ typed, placeholder, caret = true }: { typed?: Node; placeholder?: Node; caret?: boolean }) {
  return (
    <div className="ep-produce">
      <div className="ep-field">
        {typed ? <span>{typed}</span> : <span className="ph">{placeholder}</span>}
        {caret && <span className="caret"></span>}
      </div>
    </div>
  );
}

/* ---------- confidence tap ---------- */
export function EpConfidence({ value, onPick }: { value?: 'sure' | 'unsure' | null; onPick?: (v: 'sure' | 'unsure') => void }) {
  return (
    <div className="ep-conf">
      <span className="lab">Avant de vérifier</span>
      <div className="chips">
        <button className={'chip sure' + (value === 'sure' ? ' on' : '')} onClick={() => onPick && onPick('sure')}>sûr·e</button>
        <button className={'chip unsure' + (value === 'unsure' ? ' on' : '')} onClick={() => onPick && onPick('unsure')}>pas sûr·e</button>
      </div>
    </div>
  );
}

/* ---------- primary action ---------- */
export function EpVerdict({ tone = 'go', children }: { tone?: string; children: Node }) {
  return <div className={'ep-verdict ' + tone}><span>{children}</span><span className="ln"></span></div>;
}
export function EpBar({ children, tone, disabled, icon = 'check', onClick }: { children: Node; tone?: string; disabled?: boolean; icon?: string | null; onClick?: () => void }) {
  return (
    <button className={'ep-bar' + (tone ? ' ' + tone : '')} disabled={disabled} onClick={onClick}>
      <span>{children}</span>{icon && EpIco[icon]}
    </button>
  );
}
export function EpFoot({ children }: { children: Node }) { return <div className="ep-foot">{children}</div>; }

/* ---------- proofreader's marks ---------- */
export function EpFix({ old, fix }: { old: Node; fix: Node }) {
  return (
    <span className="ep-fix">
      <span className="new">{fix}</span>
      <span className="car">‸</span>
      <span className="old">{old}</span>
    </span>
  );
}
export function EpIns({ fix }: { fix: Node }) {
  return (
    <span className="ep-ins">
      <span className="new">{fix}</span>
      <span className="car">‸</span>
    </span>
  );
}
/* label-vs-label correction (classify): two stacked lines, no floating caret —
   the chosen and correct category names run too long to anchor a bubble. */
export function EpLabelFix({ old, fix }: { old: Node; fix: Node }) {
  return (
    <div className="ep-labelfix">
      <div className="row"><span className="k">Classé</span><span className="v old">{old}</span></div>
      <div className="row"><span className="k">Correct</span><span className="v new">{fix}</span></div>
    </div>
  );
}
/* full-line rewrite (sentence / spoken / conversation / paragraph): the learner's
   own line struck through, the corrected line beneath — both WRAP within the
   column. The floating-caret EpFix is for a short word swap only; a whole
   sentence in a nowrap span overflows the frame. */
export function EpLineFix({ old, fix }: { old: Node; fix: Node }) {
  return (
    <div className="ep-linefix">
      {old ? <p className="old">{old}</p> : null}
      <p className="new">{fix}</p>
    </div>
  );
}
export function EpGalley({ label = 'Marques du correcteur', anchor, children, why, relecture }: { label?: string; anchor?: Node; children: Node; why?: Node; relecture?: Node }) {
  return (
    <div className="ep-galley">
      <div className="gh"><span>{label}</span>{anchor && <span className="n">{anchor}</span>}</div>
      <div className="ep-gline">{children}</div>
      {why && (
        <div className="ep-why">
          <span className="pin">{EpIco.pencil}</span>
          <div className="t">{why}</div>
        </div>
      )}
      {relecture}
    </div>
  );
}
export function EpRelecture({ status = 'pending', children }: { status?: 'pending' | 'done'; children?: Node }) {
  if (status === 'pending') {
    return <div className="ep-relecture pending"><span>Relecture en cours</span><span className="dots"><i></i><i></i><i></i></span></div>;
  }
  return <div className="ep-relecture done">{children}</div>;
}

/* ---------- BON stamp + correct moment ---------- */
export function EpBonStamp({ struck }: { struck?: boolean }) {
  return (
    <div className={'ep-bon-stamp' + (struck ? ' ep-struck' : '')}>
      <span>Bon</span><span className="d">à tirer</span>
    </div>
  );
}
export function EpCorrect({ said, struck }: { said: Node; struck?: boolean }) {
  return (
    <div className="ep-correct">
      <EpBonStamp struck={struck} />
      <div className="said">{said}</div>
    </div>
  );
}

/* ---------- typed micro-repair ---------- */
export function EpRepair({
  target,
  typed = '',
  status,
  errFrom,
  onChange,
  onSubmit,
  submitting,
  disabled,
}: {
  target: string;
  typed?: string;
  status?: 'ok' | 'no' | null;
  errFrom?: number | null;
  onChange?: (value: string) => void;
  onSubmit?: () => void;
  submitting?: boolean;
  disabled?: boolean;
}) {
  const ghost = target.slice(typed.length);
  const okChars = errFrom == null ? typed.length : errFrom;
  const good = typed.slice(0, okChars);
  const bad = errFrom == null ? '' : typed.slice(errFrom);
  return (
    <div className="ep-repair">
      <div className="rh">Recopie la correction</div>
      <div className="ep-rf">
        <div className={'ep-typefield' + (status === 'ok' ? ' ok' : status === 'no' ? ' no' : '')}>
          {onChange ? (
            <input
              aria-label="Recopie la correction"
              value={typed}
              onChange={(event) => onChange(event.target.value)}
              // The correction is already visible in the galley above; the
              // placeholder here is a generic prompt, not the answer itself,
              // so retyping stays a real recall exercise instead of copying.
              placeholder="Tapez la ligne corrigée…"
              disabled={disabled || status === 'ok'}
              autoCapitalize="sentences"
              autoCorrect="off"
              autoComplete="off"
              spellCheck={false}
            />
          ) : (
            <>
              <span className="typed">{good}</span>
              {bad && <span className="typed err">{bad}</span>}
              {status !== 'ok' && <span className="caret"></span>}
              <span className="ghost">{ghost}</span>
            </>
          )}
        </div>
        {onSubmit && status !== 'ok' && (
          <button type="button" className="ep-repair-submit" onClick={onSubmit} disabled={disabled || submitting || !typed.trim()}>
            {submitting ? 'Comparaison…' : 'Comparer la ligne'}
          </button>
        )}
        {status === 'ok' && <div className="rmeta ok">— Ligne recomposée · juste —</div>}
        {status === 'no' && <div className="rmeta no">— La lettre diffère · reprenez le sort —</div>}
      </div>
    </div>
  );
}

/* ---------- écouter + shadowing ---------- */
export function EpListen({ fr, disabled, playing, onPlay }: { fr: Node; disabled?: boolean; playing?: boolean; onPlay?: () => void }) {
  return (
    <div className={'ep-listen' + (disabled ? ' disabled' : '')}>
      <button className="play" onClick={onPlay} disabled={disabled}>{EpIco.play}</button>
      <div className="l">
        <div className="k">{disabled ? 'Voix indisponible' : playing ? 'Lecture' : 'Écouter le modèle'}</div>
        <div className="fr">{fr}</div>
      </div>
      {!disabled && (
        <div className="wave">
          {[10, 18, 8, 22, 14, 20, 9, 16, 12].map((h, i) => <i key={i} style={{ height: h }}></i>)}
        </div>
      )}
    </div>
  );
}
export function EpRecord({ status = 'idle', onToggle, disabled }: { status?: 'idle' | 'recording' | 'transcribing'; onToggle?: () => void; disabled?: boolean }) {
  const st = ({ idle: 'Appuyez pour répéter', recording: 'Enregistrement…', transcribing: 'Transcription…' } as Record<string, string>)[status];
  return (
    <div className={'ep-record ' + status}>
      {status === 'transcribing'
        ? <div className="rollers"><i></i><i></i><i></i></div>
        : <button className="mic" onClick={onToggle} disabled={disabled}>{EpIco.mic}</button>}
      <div className="st">{st}</div>
    </div>
  );
}

/* ---------- early mastery lock ---------- */
export function EpLock({ motif, title }: { motif?: Node; title: Node }) {
  return (
    <div className="ep-lock">
      <div className="k">Maîtrise anticipée</div>
      <div className="plate">
        {motif}
        <div className="band">Plomb verrouillé</div>
      </div>
      <h2>{title}</h2>
      <p>Tout était propre — le concept se ferme en avance. Vous passez au suivant.</p>
      <div className="promo">Concept classé <b>sans faute</b></div>
    </div>
  );
}

/* ---------- BON À TIRER completion stamp ---------- */
export function EpBatStage({ sub }: { sub?: Node }) {
  return (
    <div className="ep-bat-stage">
      <div className="ep-bat ep-struck"><span className="m">Bon à tirer</span><span className="d">Édition prête</span></div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

/* ---------- recap · l'épreuve ---------- */
export function EpRecapHead({ date }: { date: Node }) {
  return (
    <div className="ep-recap-head">
      <div className="folio"><span>Atelier</span><i></i><span>La séance</span><i></i><span>L’épreuve</span></div>
      <h1>L’épreuve</h1>
      <div className="date">{date}</div>
    </div>
  );
}
export function EpTally({ items }: { items: { n: Node; l: Node }[] }) {
  return (
    <div className="ep-tally">
      {items.map((it, i) => <div className="t" key={i}><div className="n">{it.n}</div><div className="l">{it.l}</div></div>)}
    </div>
  );
}
export function EpProof({ lines }: { lines: { fr: Node; tag: Node; re?: boolean }[] }) {
  return (
    <div className="ep-proof">
      {lines.map((l, i) => (
        <div className="pl" key={i}>
          <span className={'mk' + (l.re ? ' re' : '')}>{l.re ? '✎' : '✓'}</span>
          <span className="fr">{l.fr}</span>
          <span className="tag">{l.tag}</span>
        </div>
      ))}
    </div>
  );
}
export function EpPhrase({ quote, by }: { quote: Node; by: Node }) {
  return (
    <div className="ep-phrase">
      <div className="flag">À paraître demain</div>
      <div className="q">« {quote} »</div>
      <div className="by"><span className="ln"></span><span>{by}</span></div>
    </div>
  );
}
export function EpToken() {
  return (
    <div className="ep-token">
      <div className="lt">
        <svg viewBox="0 0 24 24"><circle className="shp c-circle" cx="8" cy="8" r="5" /></svg>
        <svg viewBox="0 0 24 24"><rect className="shp c-square" x="12" y="3" width="9" height="9" /></svg>
        <svg viewBox="0 0 24 24"><polygon className="shp c-tri" points="12,13 20,21 4,21" /></svg>
      </div>
    </div>
  );
}
export function EpMint({ note, tokens = 2 }: { note?: Node; tokens?: number }) {
  return (
    <div className="ep-mint">
      <div className="tx"><b>Jetons frappés</b><span>{note}</span></div>
      <div className="tokens">{Array.from({ length: tokens }).map((_, i) => <EpToken key={i} />)}</div>
    </div>
  );
}
export function EpSeal({ gilt, label = 'ATELIER · BON À TIRER', stamp }: { gilt?: boolean; label?: string; stamp?: boolean }) {
  return (
    <div className={'ep-seal' + (gilt ? ' gilt' : '') + (stamp ? ' stamp' : '')}>
      <div className="med">
        <svg className="ring" viewBox="0 0 116 116">
          <defs><path id="ep-ring-p" d="M58,58 m-44,0 a44,44 0 1,1 88,0 a44,44 0 1,1 -88,0" /></defs>
          <text><textPath href="#ep-ring-p" startOffset="0">{label} · {label}</textPath></text>
        </svg>
        <div className="core">
          <svg viewBox="0 0 58 58"><circle className="shp c-circle" cx="20" cy="20" r="12" /></svg>
          <svg viewBox="0 0 58 58"><rect className="shp c-square" x="30" y="8" width="20" height="20" /></svg>
          <svg viewBox="0 0 58 58"><polygon className="shp c-tri" points="29,30 50,52 8,52" /></svg>
        </div>
      </div>
    </div>
  );
}
export function EpStreak({ was, now, rules = 5, on = 4 }: { was: Node; now: Node; rules?: number; on?: number }) {
  return (
    <div className="ep-streak">
      <span className="n was">{was}</span>
      <span className="arw">{EpIco.arrow}</span>
      <span className="n now">{now}</span>
      <span className="l"><b>{now} jours</b> de suite — l’édition ne rate pas.</span>
      <span className="rules">{Array.from({ length: rules }).map((_, i) => <i key={i} className={i < on ? 'on' : ''}></i>)}</span>
    </div>
  );
}
export function EpHandoff({ next = 'Le Feuilleton', onRead, onHome }: { next?: string; onRead?: () => void; onHome?: () => void }) {
  return (
    <div className="ep-handoff">
      <button className="on" onClick={onRead}><span>Lire {next}</span>{EpIco.book}</button>
      <button className="back" onClick={onHome}><span>Revenir à La Une</span>{EpIco.home}</button>
    </div>
  );
}

/* ---------- system states ---------- */
export function EpResume({ groups, cap, onResume }: { groups: EpStickGroup[]; cap?: [string, string | number]; onResume?: () => void }) {
  return (
    <div className="ep-resume">
      <div className="k">Séance en cours</div>
      <h2>La ligne était à moitié réglée.</h2>
      <p>Reprenez là où le plomb attend.</p>
      <div className="stickwrap"><EpStick groups={groups} cap={cap} /></div>
      <button className="cta" onClick={onResume}>{EpIco.arrow}<span>Reprendre la composition</span></button>
    </div>
  );
}
export function EpSkeleton() {
  return (
    <div className="ep-skel">
      <div className="l" style={{ width: '38%' }}></div>
      <div className="l" style={{ width: '72%', height: 20 }}></div>
      <div className="box"></div>
      <div className="l" style={{ width: '90%' }}></div>
      <div className="l" style={{ width: '80%' }}></div>
      <div className="l" style={{ width: '55%' }}></div>
      <div className="press">— on compose la séance —</div>
    </div>
  );
}
export function EpNotice({ msg = 'La séance n’a pas pu être composée. Le texte est sauvegardé ; la rédaction réessaie.', onRetry }: { msg?: Node; onRetry?: () => void }) {
  return (
    <div className="ep-notice">
      <div className="nh"><span className="tri"></span><span className="t">Avis de la rédaction</span></div>
      <div className="nb">
        <div className="m">{msg}</div>
        <button className="retry" onClick={onRetry}>{EpIco.retry}<span>Réessayer</span></button>
      </div>
    </div>
  );
}

export function LEpreuveStyles() {
  return (
    <style jsx global>{`
.ep {
  --ep-bon: #2c6a5d;
  --ep-graphite: color-mix(in srgb, var(--app-ink) 62%, transparent);
  --ep-channel: color-mix(in srgb, var(--app-ink) 16%, transparent);
  --ep-slug-lo: color-mix(in srgb, var(--app-ink) 22%, transparent);
  --ep-printin-dur: .5s;
  --ep-mono: "iA Writer Mono", ui-monospace, "SF Mono", Menlo, monospace;
  position: relative;
  width: min(var(--app-viewport-width, 100vw), var(--phone-shell-max, 430px));
  max-width: 100%;
  background: var(--app-paper);
  color: var(--app-ink);
  font-family: var(--app-grotesk);
  -webkit-font-smoothing: antialiased;
  display: flex; flex-direction: column;
  overflow: hidden;
}
.ep * { box-sizing: border-box; }
.ep-body { flex: 1 1 auto; }

/* ============================================================
   TOPBAR — close · composing-stick progress · Finish. Slim, sticky.
   ============================================================ */
.ep-top {
  position: sticky; top: 0; z-index: 6;
  display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 13px;
  padding: 9px 14px 10px;
  background: var(--app-paper);
  border-bottom: 1px solid var(--app-ink);
}
.ep-top .ic {
  width: 30px; height: 30px; flex: 0 0 auto; padding: 0;
  border: 1px solid var(--app-ink); background: var(--app-sheet); color: var(--app-ink);
  display: grid; place-items: center; cursor: pointer;
}
.ep-top .ic svg { width: 15px; height: 15px; }
.ep-top .finish {
  border: 1px solid var(--app-ink); background: var(--app-paper); color: var(--app-ink);
  font-size: 9px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase;
  padding: 8px 11px; cursor: pointer;
}

/* ---- THE COMPOSING STICK (progress) ------------------------
   A typesetter's stick: each completed drill sets a lead slug
   into the current line. Concept boundaries read as breaks. */
.ep-stick { flex: 1 1 auto; min-width: 0; }
.ep-stick .chan {
  display: flex; gap: 4px; align-items: stretch;
  height: 18px; padding: 2px;
  background: var(--ep-channel);
  border: 1px solid var(--app-ink);
  box-shadow: inset 0 1px 2px rgba(0,0,0,.22);
}
.ep-stick .grp { display: flex; gap: 1.5px; flex: 1 1 auto; min-width: 0; }
.ep-stick .grp + .grp { margin-left: 3px; border-left: 1px solid var(--app-ink-3); padding-left: 4px; }
.ep-stick .slug { flex: 1 1 auto; min-width: 2px; background: var(--ep-slug-lo); }
.ep-stick .slug.set { background: var(--app-ink); }
.ep-stick .slug.cur { background: var(--app-yellow); box-shadow: 0 0 0 1px var(--app-ink); }
.ep-stick .cap {
  display: flex; justify-content: space-between; margin-top: 4px;
  font-size: 8px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-3);
}
.ep-stick .cap b { color: var(--app-ink); }

/* fuller stick — used in the recap proof sheet */
.ep-stick.full .chan { height: 26px; }
.ep-stick.full .concepts {
  margin-top: 7px; display: flex; gap: 4px;
}
.ep-stick.full .concepts .c {
  flex: 1 1 auto; text-align: center;
  font-size: 7.5px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase;
  color: var(--app-ink-3); padding-top: 5px; border-top: 1px solid var(--app-paper-3);
}
.ep-stick.full .concepts .c.done { color: var(--ep-bon); border-top-color: var(--ep-bon); }
.ep-stick.full .concepts .c.cur { color: var(--app-ink); border-top-color: var(--app-ink); }

/* ============================================================
   THE EXERCISE SHEET (ExerciseShell)
   eyebrow (round · mode · i/n) · provenance · concept title +
   assembling motif · rule toggle · body per round type.
   ============================================================ */
.ep-sheet { padding: 15px 20px 18px; }

.ep-eyebrow {
  display: flex; align-items: center; gap: 7px;
  font-size: 9px; font-weight: 900; letter-spacing: .16em; text-transform: uppercase;
  color: var(--app-ink-3);
}
.ep-eyebrow i { width: 3px; height: 3px; background: var(--app-ink-3); flex: 0 0 auto; }
.ep-eyebrow .mode { color: var(--app-red); }
.ep-eyebrow .idx { margin-left: auto; font-variant-numeric: tabular-nums; }

/* re-test flash tag — "Retour · déjà corrigé" (marginal) */
.ep-retour {
  display: inline-flex; align-items: center; gap: 5px; margin-left: 7px;
  font-size: 8px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase;
  color: var(--app-blue); border: 1px solid var(--app-blue); padding: 2px 5px;
}
.ep-retour .d { width: 0; height: 0; border-style: solid; border-width: 4px 0 4px 5px; border-color: transparent transparent transparent var(--app-blue); }

/* provenance note — graphite margin line for a resurfaced error */
.ep-prov {
  margin-top: 7px; padding-left: 10px; border-left: 2px solid var(--ep-graphite);
  font-family: var(--app-serif); font-style: italic; font-size: 12px; line-height: 1.35;
  color: var(--ep-graphite);
}
.ep-prov b { font-weight: 700; font-style: normal; }

/* concept title row + the assembling motif */
.ep-concept { margin-top: 11px; display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: start; }
.ep-concept .ct { min-width: 0; display: flex; gap: 12px; align-items: flex-start; }
.ep-concept h1 {
  margin: 0; font-family: var(--app-serif); font-style: italic; font-weight: 600;
  font-size: 25px; line-height: 1.04; letter-spacing: 0; color: var(--app-ink); text-wrap: balance;
}
.ep-concept .ask {
  flex: 0 0 auto; width: 30px; height: 30px; padding: 0;
  border: 1px solid var(--app-ink); background: var(--app-sheet); color: var(--app-ink);
  display: grid; place-items: center; cursor: pointer;
}
.ep-concept .ask svg { width: 16px; height: 16px; }
.ep-concept .ask.on { background: var(--app-ink); color: var(--app-paper); }

/* ---- ASSEMBLING MOTIF (per-concept progress) --------------
   A Bauhaus mark set from house primitives; one prints into
   place per round; whole when the concept is done. */
.ep-motif {
  position: relative; width: 46px; height: 46px; flex: 0 0 auto;
  border: 1px solid var(--app-ink); background: var(--app-sheet);
}
.ep-motif svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.ep-motif .prim { transition: opacity var(--ep-printin-dur) ease, filter var(--ep-printin-dur) ease; }
.ep-motif .prim .shp { stroke: var(--app-ink); stroke-width: 3; }
.ep-motif .prim .c-circle { fill: var(--app-blue); }
.ep-motif .prim .c-square { fill: var(--app-yellow); }
.ep-motif .prim .c-tri { fill: var(--app-red); }
.ep-motif .prim .c-block { fill: var(--app-ink); }
/* ghost = not yet printed: dashed outline, no fill */
.ep-motif .prim.ghost .shp { fill: none; stroke: var(--app-ink-3); stroke-width: 1.5; stroke-dasharray: 2.5 2.5; }
.ep-motif .prim.ghost { opacity: .75; }
.ep-motif.done { border-color: var(--app-ink); box-shadow: 2px 2px 0 var(--app-ink); }
@media (prefers-reduced-motion: no-preference) {
  .ep-motif .prim.print-in { animation: ep-print var(--ep-printin-dur) ease both; }
}
@keyframes ep-print { from { opacity: 0; filter: grayscale(1); } to { opacity: 1; filter: none; } }
/* motif caption (spec/legend use) */
.ep-motif-cap { font-family: var(--ep-mono); font-size: 8px; color: var(--app-ink-3); margin-top: 5px; line-height: 1.4; }

/* ---- THE RULE SHEET (payload.rule_panel + anchor examples) -- */
.ep-rule {
  margin-top: 13px; border: 1px solid var(--app-ink); background: var(--app-sheet);
  overflow: hidden;
}
.ep-rule .rh {
  display: flex; align-items: center; gap: 8px; padding: 9px 13px;
  border-bottom: 1px solid var(--app-ink); background: var(--app-paper);
}
.ep-rule .rh .k { font-size: 8.5px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-red); }
.ep-rule .rh .x { margin-left: auto; border: 0; background: none; color: var(--app-ink-3); cursor: pointer; font-size: 15px; line-height: 1; padding: 0; }
.ep-rule .rb { padding: 12px 14px 14px; }
.ep-rule .rb .lede { font-family: var(--app-serif); font-style: italic; font-size: 16px; line-height: 1.36; color: var(--app-ink); }
.ep-rule .rb .anchor { margin-top: 11px; padding-top: 10px; border-top: 1px dashed var(--app-ink-3); }
.ep-rule .rb .anchor .c { font-size: 8px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--app-ink-3); margin-bottom: 6px; }
.ep-rule .rb .ex { font-family: var(--app-serif); font-size: 15px; line-height: 1.5; color: var(--app-ink-2); }
.ep-rule .rb .ex b { color: var(--app-ink); border-bottom: 2px solid var(--app-red); font-weight: 600; }

/* ============================================================
   THE PROMPT LINE — French sentence is the hero type
   ============================================================ */
.ep-prompt { margin-top: 15px; }
.ep-prompt .lab { font-size: 8.5px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-ink-3); margin-bottom: 8px; }
.ep-line {
  font-family: var(--app-serif); font-size: 23px; line-height: 1.4; color: var(--app-ink); text-wrap: pretty;
}
.ep-line .blank {
  display: inline-block; min-width: 68px; text-align: center;
  border-bottom: 2px solid var(--app-red); color: var(--app-ink-3); font-style: italic;
}
.ep-line .blank.set { border-bottom-color: var(--app-ink); color: var(--app-ink); }
/* the English meaning cue — the compositor's instruction */
.ep-cue { margin-top: 9px; font-size: 12px; line-height: 1.4; color: var(--app-ink-3); }
.ep-cue b { font-weight: 800; color: var(--app-ink-2); }

/* ============================================================
   RECOGNIZE / FILL — option sorts
   ============================================================ */
.ep-opts { display: grid; gap: 8px; margin-top: 15px; }
.ep-opt {
  border: 1px solid var(--app-ink); background: var(--app-paper); color: var(--app-ink);
  padding: 12px 14px; text-align: left; cursor: pointer;
  font-family: var(--app-serif); font-size: 16px; line-height: 1.15;
}
.ep-opt.chosen { background: var(--app-ink); color: var(--app-paper); }
.ep-opt.right { border-color: var(--ep-bon); box-shadow: inset 0 0 0 1.5px var(--ep-bon); }
.ep-opt.wrong { border-color: var(--app-red); box-shadow: inset 0 0 0 1.5px var(--app-red); }
/* fill: choices as a row of small sorts */
.ep-choices { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }

/* ============================================================
   MOVABLE TYPE (word-bank) — tokens set into a line
   ============================================================ */
.ep-slug {
  font-family: var(--app-serif); font-size: 17px; line-height: 1;
  padding: 9px 11px; background: var(--app-paper); color: var(--app-ink);
  border: 1px solid var(--app-ink); cursor: pointer;
  box-shadow: inset 1px 1px 0 rgba(255,255,255,.35), 2px 2px 0 var(--app-ink);
}
.ep[data-theme="dark"] .ep-slug { box-shadow: inset 1px 1px 0 rgba(255,255,255,.08), 2px 2px 0 var(--app-ink); }
.ep-slug.spent { opacity: .3; pointer-events: none; box-shadow: none; }
.ep-slug.set { box-shadow: inset 1px 1px 0 rgba(255,255,255,.3), 1px 1px 0 var(--app-ink); }

/* the composing line — where set slugs sit on a baseline */
.ep-setline {
  position: relative; margin-top: 14px; min-height: 60px;
  display: flex; flex-wrap: wrap; gap: 7px; align-content: flex-start;
  padding: 12px 12px 16px;
  background: var(--ep-channel); border: 1px solid var(--app-ink);
  box-shadow: inset 0 1px 3px rgba(0,0,0,.15);
}
.ep-setline::after {
  content: ""; position: absolute; left: 12px; right: 12px; bottom: 9px;
  border-bottom: 1px solid var(--app-ink-3);
}
.ep-setline.empty::before {
  content: "réglez la ligne ici"; position: absolute; left: 14px; top: 14px;
  font-family: var(--ep-mono); font-size: 10px; color: var(--app-ink-3); letter-spacing: .04em;
}
/* the type case — available sorts */
.ep-case { margin-top: 13px; }
.ep-case .cap {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 8.5px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--app-ink-3);
  margin-bottom: 9px;
}
.ep-case .sorts {
  display: flex; flex-wrap: wrap; gap: 8px;
  padding: 11px; background: var(--app-sheet); border: 1px solid var(--app-paper-3);
}

/* CLASSIFY — sorting slugs into labelled cases */
.ep-cases { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }
.ep-casebox { border: 1px solid var(--app-ink); background: var(--app-sheet); }
.ep-casebox .ch {
  padding: 7px 10px; border-bottom: 1px solid var(--app-ink); background: var(--app-paper);
  font-size: 8.5px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-2);
}
.ep-casebox .cbody { padding: 10px; min-height: 58px; display: flex; flex-wrap: wrap; gap: 6px; align-content: flex-start; }

/* ============================================================
   PRODUCE — free composition (a set line + typed field)
   ============================================================ */
.ep-produce { margin-top: 14px; }
.ep-field {
  font-family: var(--app-serif); font-size: 19px; line-height: 1.4; color: var(--app-ink);
  padding: 13px 14px; min-height: 74px;
  background: var(--app-sheet); border: 1px solid var(--app-ink);
  box-shadow: inset 0 1px 3px rgba(0,0,0,.1);
}
.ep-field .ph { color: var(--app-ink-3); font-style: italic; }
.ep-field .caret { display: inline-block; width: 2px; height: 1.05em; background: var(--app-red); vertical-align: -2px; margin-left: 1px; }
@media (prefers-reduced-motion: no-preference) { .ep-field .caret { animation: ep-blink 1s step-end infinite; } }
@keyframes ep-blink { 50% { opacity: 0; } }

/* ============================================================
   CONFIDENCE TAP — optional two-chip: sûr / pas sûr, skippable
   ============================================================ */
.ep-conf { margin-top: 16px; display: flex; align-items: center; gap: 9px; }
.ep-conf .lab { font-size: 8.5px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
.ep-conf .chips { display: flex; gap: 7px; margin-left: auto; }
.ep-conf .chip {
  border: 1px solid var(--app-ink-3); background: var(--app-paper); color: var(--app-ink-2);
  font-size: 11px; font-weight: 800; letter-spacing: .02em; padding: 6px 12px; cursor: pointer;
}
.ep-conf .chip.sure.on { border-color: var(--ep-bon); background: var(--ep-bon); color: var(--app-paper); }
.ep-conf .chip.unsure.on { border-color: var(--app-ink); background: var(--app-ink); color: var(--app-paper); }

/* ============================================================
   THE PRIMARY ACTION — ink press-bar. Never two competing CTAs.
   ============================================================ */
.ep-foot { padding: 0 20px 20px; }
.ep-bar {
  display: flex; align-items: center; justify-content: center; gap: 11px;
  width: 100%; min-height: 56px; padding: 0 20px;
  background: var(--app-ink); color: var(--app-paper);
  border: 1px solid var(--app-ink); box-shadow: 4px 4px 0 var(--ep-channel);
  font-size: 12.5px; font-weight: 700; letter-spacing: .15em; text-transform: uppercase;
  cursor: pointer;
}
.ep-bar svg { width: 17px; height: 17px; }
.ep-bar[disabled] { opacity: .4; cursor: default; box-shadow: none; }
.ep-bar.red { background: var(--app-red); border-color: var(--app-red); color: #fff; box-shadow: 4px 4px 0 var(--ep-channel); }
.ep-bar.ghost { background: var(--app-paper); color: var(--app-ink); }

/* verdict line above the action (a ruled press notice) */
.ep-verdict {
  display: flex; align-items: center; gap: 10px; margin-bottom: 13px;
  font-size: 9px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase;
}
.ep-verdict .ln { flex: 1 1 auto; height: 1px; background: currentColor; opacity: .4; }
.ep-verdict.go { color: var(--ep-bon); }
.ep-verdict.no { color: var(--app-red); }

/* ============================================================
   PROOFREADER'S MARKS — the feedback language (the heart)
   The learner's OWN sentence, marked like an editor's galley:
   strike on the error, a red margin correction with caret, the
   "why" as a graphite pencil note beneath.
   ============================================================ */
.ep-galley {
  margin-top: 14px; position: relative;
  padding: 16px 16px 14px; background: var(--app-sheet); border: 1px solid var(--app-ink);
}
.ep-galley .gh {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
  font-size: 8.5px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-red);
}
.ep-galley .gh .n { margin-left: auto; font-family: var(--ep-mono); color: var(--app-ink-3); font-weight: 400; letter-spacing: .02em; }
/* the set line, with room above for margin corrections */
.ep-gline {
  font-family: var(--app-serif); font-size: 22px; line-height: 2.15; color: var(--app-ink);
}
/* a corrected span: struck original in line, red fix floating above with a caret.
   Only fits a short word-level swap inside a longer visible line — see
   EpLabelFix below for label-vs-label corrections (e.g. classify). */
.ep-fix { position: relative; white-space: nowrap; }
.ep-fix .old {
  color: var(--app-red); text-decoration: line-through; text-decoration-thickness: 2px;
  text-decoration-color: var(--app-red);
}
.ep-fix .new {
  position: absolute; left: 50%; top: -0.92em; transform: translateX(-50%);
  font-style: italic; font-size: 15px; color: var(--app-red); white-space: nowrap; line-height: 1;
}
/* the proofreader's caret ⁁ pointing up from the baseline to the fix */
.ep-fix .car {
  position: absolute; left: 50%; top: -0.08em; transform: translateX(-50%);
  color: var(--app-red); font-size: 13px; line-height: 1;
}
/* an insertion (missing word): a caret on the line, the word above */
.ep-ins { position: relative; display: inline-block; width: 0; }
.ep-ins .new { position: absolute; left: 50%; top: -0.92em; transform: translateX(-50%); font-style: italic; font-size: 15px; color: var(--app-red); white-space: nowrap; }
.ep-ins .car { position: absolute; left: 50%; top: -0.08em; transform: translateX(-50%); color: var(--app-red); font-size: 13px; }
.ep-labelfix { display: grid; gap: 7px; }
.ep-labelfix .row { display: flex; align-items: baseline; gap: 10px; }
.ep-labelfix .k { flex: 0 0 auto; width: 58px; font-family: var(--ep-mono); font-size: 8.5px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-3); }
.ep-labelfix .v { font-family: var(--app-serif); font-size: 17px; line-height: 1.3; }
.ep-labelfix .v.old { color: var(--app-red); text-decoration: line-through; text-decoration-thickness: 2px; text-decoration-color: var(--app-red); }
.ep-labelfix .v.new { color: var(--ep-bon); font-style: italic; }
.ep-linefix { display: grid; gap: 6px; }
.ep-linefix p { margin: 0; font-family: var(--app-serif); font-size: 18px; line-height: 1.4; overflow-wrap: anywhere; }
.ep-linefix .old { color: var(--app-red); text-decoration: line-through; text-decoration-thickness: 2px; text-decoration-color: color-mix(in srgb, var(--app-red) 55%, transparent); }
.ep-linefix .new { color: var(--ep-bon); font-style: italic; }
/* the graphite pencil "why" note */
.ep-why {
  margin-top: 13px; padding-top: 12px; border-top: 1px dashed var(--app-ink-3);
  display: grid; grid-template-columns: auto 1fr; gap: 9px; align-items: start;
}
.ep-why .pin {
  flex: 0 0 auto; width: 15px; height: 15px; color: var(--ep-graphite);
}
.ep-why .pin svg { width: 15px; height: 15px; }
.ep-why .t {
  font-family: var(--app-serif); font-style: italic; font-size: 13.5px; line-height: 1.42; color: var(--ep-graphite);
}
.ep-why .t b { font-style: normal; font-weight: 700; color: var(--app-ink-2); }

/* the async AI second-look — discreet marginal note, resolves in place */
.ep-relecture {
  margin-top: 12px; display: flex; align-items: center; gap: 8px;
  font-family: var(--app-serif); font-style: italic; font-size: 12.5px; color: var(--app-ink-3);
}
.ep-relecture .dots { display: inline-flex; gap: 3px; }
.ep-relecture .dots i { width: 4px; height: 4px; border-radius: 50%; background: var(--app-ink-3); }
@media (prefers-reduced-motion: no-preference) {
  .ep-relecture.pending .dots i { animation: ep-pulse 1s ease-in-out infinite; }
  .ep-relecture.pending .dots i:nth-child(2) { animation-delay: .2s; }
  .ep-relecture.pending .dots i:nth-child(3) { animation-delay: .4s; }
}
@keyframes ep-pulse { 0%,100% { opacity: .3; } 50% { opacity: 1; } }
.ep-relecture.done { color: var(--ep-bon); }
.ep-relecture.done b { font-style: normal; font-weight: 700; }

/* ---- BON stamp — correct answer, small, NOT a modal --------- */
.ep-bon-stamp {
  display: inline-flex; align-items: center; gap: 6px;
  border: 2px solid var(--ep-bon); color: var(--ep-bon);
  font-size: 12px; font-weight: 900; letter-spacing: .18em; text-transform: uppercase;
  padding: 5px 11px 4px; transform: rotate(-3.5deg);
  box-shadow: inset 0 0 0 1px var(--ep-bon);
}
.ep-bon-stamp .d { font-size: 7.5px; letter-spacing: .1em; color: var(--ep-bon); opacity: .8; }
@media (prefers-reduced-motion: no-preference) {
  .ep-struck { animation: ep-strike .3s cubic-bezier(.18,1.35,.3,1) both; }
}
@keyframes ep-strike { 0% { transform: scale(1.5) rotate(-14deg); opacity: 0; } 60% { transform: scale(.94) rotate(-2deg); opacity: 1; } 100% { transform: rotate(-3.5deg); } }

/* the correct-moment inline block (no modal) */
.ep-correct { margin-top: 14px; display: flex; align-items: center; gap: 13px; }
.ep-correct .said { font-family: var(--app-serif); font-style: italic; font-size: 16px; color: var(--app-ink-2); line-height: 1.3; }
.ep-correct .said b { color: var(--app-ink); font-style: normal; font-weight: 700; }

/* ============================================================
   TYPED MICRO-REPAIR — "Recopie la correction :"
   The corrected sentence as a ghost to type over.
   ============================================================ */
.ep-repair { margin-top: 14px; border: 1px solid var(--app-ink); background: var(--app-paper); }
.ep-repair .rh {
  padding: 8px 13px; border-bottom: 1px solid var(--app-ink); background: var(--app-sheet);
  font-size: 8.5px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--app-ink-2);
}
.ep-repair .ep-rf { padding: 13px 14px; }
.ep-typefield {
  position: relative; font-family: var(--app-serif); font-size: 19px; line-height: 1.4; color: var(--app-ink);
  padding: 11px 13px; background: var(--app-sheet); border: 1px solid var(--app-ink-3);
}
.ep-typefield input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--app-ink); font-family: var(--app-serif); font-size: 18px; line-height: 1.4; }
.ep-typefield input::placeholder { color: var(--app-ink-3); opacity: .52; }
.ep-repair-submit { margin-top: 10px; border: 1px solid var(--app-ink); background: var(--app-paper); color: var(--app-ink); padding: 8px 10px; font: 700 8.5px/1 var(--app-grotesk); letter-spacing: .12em; text-transform: uppercase; }
.ep-repair-submit:not(:disabled):hover { background: var(--app-ink); color: var(--app-paper); }
.ep-repair-submit:disabled { opacity: .45; cursor: not-allowed; }
.ep-typefield .typed { color: var(--app-ink); }
.ep-typefield .typed.err { color: var(--app-red); text-decoration: underline; text-decoration-style: wavy; text-decoration-color: var(--app-red); }
.ep-typefield .ghost { color: var(--app-ink-3); }
.ep-typefield .caret { display: inline-block; width: 2px; height: 1.05em; background: var(--app-red); vertical-align: -2px; }
@media (prefers-reduced-motion: no-preference) { .ep-typefield .caret { animation: ep-blink 1s step-end infinite; } }
.ep-typefield.ok { border-color: var(--ep-bon); box-shadow: inset 0 0 0 1px var(--ep-bon); }
.ep-typefield.no { border-color: var(--app-red); }
.ep-repair .rmeta { margin-top: 9px; font-size: 9px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.ep-repair .rmeta.ok { color: var(--ep-bon); }
.ep-repair .rmeta.no { color: var(--app-red); }

/* ============================================================
   ÉCOUTER + SHADOWING (speak round)
   écouter → parler (idle/recording/transcribing) → marked transcript
   ============================================================ */
.ep-listen {
  margin-top: 14px; display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; background: var(--app-ink); color: var(--app-paper); border: 1.5px solid var(--app-ink);
}
.ep-listen.disabled { background: var(--app-sheet); color: var(--app-ink-3); border-color: var(--app-ink-3); border-style: dashed; }
.ep-listen .play {
  flex: 0 0 auto; width: 40px; height: 40px; padding: 0;
  border: 1.5px solid var(--app-paper); background: var(--app-red); color: #fff;
  display: grid; place-items: center; cursor: pointer;
}
.ep-listen.disabled .play { border-color: var(--app-ink-3); background: transparent; color: var(--app-ink-3); }
.ep-listen .play svg { width: 16px; height: 16px; }
.ep-listen .l { min-width: 0; }
.ep-listen .l .k { font-size: 8.5px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-yellow); }
.ep-listen.disabled .l .k { color: var(--app-ink-3); }
.ep-listen .l .fr { margin-top: 2px; font-family: var(--app-serif); font-style: italic; font-size: 16px; line-height: 1.15; color: var(--app-paper); }
.ep-listen.disabled .l .fr { color: var(--app-ink-3); }
.ep-listen .wave { margin-left: auto; display: flex; gap: 2px; align-items: center; height: 22px; }
.ep-listen .wave i { width: 2px; background: var(--app-yellow); opacity: .55; }

/* the record affordance */
.ep-record { margin-top: 12px; display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 16px; border: 1px dashed var(--app-ink); background: var(--app-sheet); }
.ep-record .mic {
  width: 62px; height: 62px; border-radius: 50%; padding: 0;
  border: 1.5px solid var(--app-ink); background: var(--app-paper); color: var(--app-ink);
  display: grid; place-items: center; cursor: pointer;
}
.ep-record .mic svg { width: 24px; height: 24px; }
.ep-record.recording .mic { background: var(--app-red); color: #fff; border-color: var(--app-red); }
@media (prefers-reduced-motion: no-preference) {
  .ep-record.recording .mic { animation: ep-rec 1.3s ease-in-out infinite; }
}
@keyframes ep-rec { 0%,100% { box-shadow: 0 0 0 0 rgba(216,50,26,.5); } 50% { box-shadow: 0 0 0 8px rgba(216,50,26,0); } }
.ep-record .st { font-size: 9px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-ink-3); }
.ep-record.recording .st { color: var(--app-red); }
/* transcribing — the press rollers */
.ep-record .rollers { display: flex; gap: 7px; }
.ep-record .rollers i { width: 8px; height: 30px; background: var(--app-ink-3); }
@media (prefers-reduced-motion: no-preference) {
  .ep-record.transcribing .rollers i { animation: ep-roll 1s linear infinite; }
  .ep-record.transcribing .rollers i:nth-child(2) { animation-delay: .16s; }
  .ep-record.transcribing .rollers i:nth-child(3) { animation-delay: .32s; }
}
@keyframes ep-roll { 0% { transform: scaleY(.4); opacity: .5; } 50% { transform: scaleY(1); opacity: 1; } 100% { transform: scaleY(.4); opacity: .5; } }

/* ============================================================
   EARLY MASTERY LOCK — "PLOMB VERROUILLÉ"
   Skipping feels like an earned promotion, not missing content.
   ============================================================ */
.ep-lock { padding: 26px 22px 22px; text-align: center; }
.ep-lock .k { font-size: 9px; font-weight: 900; letter-spacing: .2em; text-transform: uppercase; color: var(--ep-bon); }
.ep-lock .plate {
  position: relative; margin: 18px auto 0; width: 132px; height: 132px;
  border: 2px solid var(--app-ink); background: var(--app-sheet); box-shadow: 5px 5px 0 var(--ep-channel);
  display: grid; place-items: center;
}
.ep-lock .plate .ep-motif { width: 76px; height: 76px; border: 0; background: transparent; }
.ep-lock .plate .band {
  position: absolute; left: -8px; right: -8px; top: 50%; transform: translateY(-50%) rotate(-6deg);
  background: var(--app-ink); color: var(--app-paper);
  font-size: 10px; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; text-align: center; padding: 5px 0;
}
.ep-lock h2 { margin: 20px auto 0; max-width: 270px; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: 27px; line-height: 1.05; }
.ep-lock p { margin: 11px auto 0; max-width: 250px; font-size: 12.5px; line-height: 1.5; color: var(--app-ink-2); }
.ep-lock .promo {
  margin: 16px auto 0; display: inline-flex; align-items: center; gap: 8px;
  border-top: 1px solid var(--app-ink); border-bottom: 1px solid var(--app-ink); padding: 8px 14px;
  font-size: 9px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--app-ink);
}
.ep-lock .promo b { color: var(--ep-bon); }

/* ============================================================
   BON À TIRER — the session-completion stamp across the page
   ============================================================ */
.ep-bat-stage { position: relative; padding: 54px 22px; text-align: center; background: var(--app-paper); }
.ep-bat {
  display: inline-flex; flex-direction: column; align-items: center; gap: 3px;
  border: 3px solid var(--app-red); color: var(--app-red);
  padding: 12px 22px 10px; transform: rotate(-5deg);
  box-shadow: inset 0 0 0 2px var(--app-red);
}
.ep-bat .m { font-family: var(--app-grotesk); font-weight: 900; font-size: 26px; letter-spacing: .08em; line-height: .9; }
.ep-bat .d { font-size: 8.5px; font-weight: 900; letter-spacing: .22em; text-transform: uppercase; }
.ep-bat-stage .sub { margin: 26px auto 0; max-width: 260px; font-family: var(--app-serif); font-style: italic; font-size: 16px; line-height: 1.35; color: var(--app-ink-2); }

/* ============================================================
   L'ÉPREUVE — the proof-sheet recap
   ============================================================ */
.ep-recap { background: var(--app-paper); }
.ep-recap-head { padding: 20px 22px 16px; border-bottom: 3px double var(--app-ink); text-align: center; }
.ep-recap-head .folio {
  display: flex; align-items: center; justify-content: center; gap: 7px;
  font-size: 8.5px; font-weight: 900; letter-spacing: .18em; text-transform: uppercase; color: var(--app-ink);
}
.ep-recap-head .folio i { width: 3px; height: 3px; background: var(--app-red); }
.ep-recap-head h1 { margin: 8px 0 0; font-family: var(--app-serif); font-style: italic; font-weight: 700; font-size: 34px; line-height: .95; }
.ep-recap-head .date { margin-top: 7px; font-size: 9px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; color: var(--app-ink-3); }

.ep-recap-body { padding: 16px 22px 22px; }
.ep-sec-cap { font-size: 9px; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; color: var(--app-ink-3); margin: 20px 0 10px; display: flex; align-items: center; gap: 8px; }
.ep-sec-cap::after { content: ""; flex: 1 1 auto; height: 1px; background: var(--app-paper-3); }

/* the day's tally (attempts · strengthened · errata) */
.ep-tally { display: grid; grid-template-columns: repeat(3, 1fr); border: 1.5px solid var(--app-ink); }
.ep-tally .t { padding: 13px 12px 12px; border-right: 1px solid var(--app-ink); }
.ep-tally .t:last-child { border-right: 0; }
.ep-tally .t .n { font-family: var(--app-serif); font-style: italic; font-weight: 700; font-size: 29px; line-height: .9; }
.ep-tally .t .l { margin-top: 6px; font-size: 8px; font-weight: 900; letter-spacing: .11em; text-transform: uppercase; color: var(--app-ink-3); line-height: 1.3; }

/* lines set — the proof lines of the session */
.ep-proof { display: grid; gap: 0; }
.ep-proof .pl { display: grid; grid-template-columns: 20px 1fr auto; gap: 10px; align-items: baseline; padding: 9px 2px; border-bottom: 1px solid var(--app-paper-3); }
.ep-proof .pl:last-child { border-bottom: 0; }
.ep-proof .pl .mk { font-family: var(--ep-mono); font-size: 11px; color: var(--ep-bon); padding-top: 2px; }
.ep-proof .pl .mk.re { color: var(--app-red); }
.ep-proof .pl .fr { font-family: var(--app-serif); font-size: 14.5px; line-height: 1.3; color: var(--app-ink); }
.ep-proof .pl .fr del { color: var(--app-red); text-decoration-thickness: 1.5px; }
.ep-proof .pl .fr ins { text-decoration: none; border-bottom: 1.5px solid var(--ep-bon); color: var(--app-ink); }
.ep-proof .pl .tag { font-size: 7.5px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; color: var(--app-ink-3); white-space: nowrap; padding-top: 3px; }

/* La phrase du jour — the learner's best sentence, typeset as a boxed quote */
.ep-phrase { margin-top: 12px; position: relative; border: 1.5px solid var(--app-ink); background: var(--app-sheet); padding: 18px 18px 15px; }
.ep-phrase .flag {
  position: absolute; top: -1px; right: 14px; transform: translateY(-50%);
  background: var(--app-red); color: #fff; font-size: 7.5px; font-weight: 900; letter-spacing: .11em; text-transform: uppercase; padding: 4px 8px;
}
.ep-phrase .q { font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: 22px; line-height: 1.28; color: var(--app-ink); text-wrap: balance; }
.ep-phrase .by { margin-top: 11px; display: flex; align-items: center; gap: 8px; font-size: 8.5px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink-3); }
.ep-phrase .by .ln { flex: 1 1 auto; height: 1px; background: var(--app-paper-3); }

/* minted collectibles — logo tokens + gilt seal */
.ep-mint { display: flex; align-items: center; gap: 14px; border: 1px solid var(--app-ink); background: var(--app-sheet); padding: 14px; }
.ep-mint .tx { min-width: 0; }
.ep-mint .tx b { font-size: 12px; font-weight: 800; }
.ep-mint .tx span { display: block; margin-top: 2px; font-size: 10px; line-height: 1.35; color: var(--app-ink-2); }
.ep-mint .tokens { display: flex; gap: 7px; margin-left: auto; flex: 0 0 auto; }

/* the logo token (house forms fused) — set, not drawn */
.ep-token { position: relative; width: 40px; height: 40px; border: 1.5px solid var(--app-ink); background: var(--app-paper); box-shadow: 2px 2px 0 var(--app-ink); display: grid; place-items: center; flex: 0 0 auto; }
.ep-token .lt { position: relative; width: 24px; height: 24px; }
.ep-token .lt svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.ep-token .shp { stroke: var(--app-ink); stroke-width: 3.5; }
.ep-token .c-circle { fill: var(--app-blue); } .ep-token .c-square { fill: var(--app-yellow); }
.ep-token .c-tri { fill: var(--app-red); } .ep-token .c-block { fill: var(--app-ink); }

/* the seal — the printer's colophon; gilt for a flawless run */
.ep-seal { position: relative; display: inline-grid; place-items: center; }
.ep-seal .med {
  position: relative; width: 116px; height: 116px; border-radius: 50%;
  background: var(--app-sheet); border: 1.5px solid var(--app-ink);
  box-shadow: 4px 4px 0 var(--ep-channel); display: grid; place-items: center;
}
.ep-seal .ring { position: absolute; inset: 0; width: 100%; height: 100%; }
.ep-seal .ring text { font-family: var(--app-grotesk); font-weight: 900; letter-spacing: .22em; fill: var(--app-ink); font-size: 8.5px; }
.ep-seal .core { position: relative; width: 58px; height: 58px; }
.ep-seal .core svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.ep-seal .core .shp { stroke: var(--app-ink); stroke-width: 3; }
.ep-seal .core .c-circle { fill: var(--app-blue); } .ep-seal .core .c-square { fill: var(--app-yellow); }
.ep-seal .core .c-tri { fill: var(--app-red); } .ep-seal .core .c-block { fill: var(--app-ink); }
.ep-seal.gilt .med { background: #f0e3b8; border-color: #8a6d1a; box-shadow: 4px 4px 0 #8a6d1a; }
.ep-seal.gilt .ring text { fill: #6f571a; }
.ep[data-theme="dark"] .ep-seal.gilt .med { background: #d8c37e; }
@media (prefers-reduced-motion: no-preference) {
  .ep-seal.stamp .med { animation: ep-seal-press .5s cubic-bezier(.2,1.2,.3,1) both; }
}
@keyframes ep-seal-press { 0% { transform: scale(1.18) rotate(-3.5deg); } 58% { transform: scale(.965) rotate(.6deg); } 100% { transform: scale(1) rotate(0); } }

/* streak line before → after */
.ep-streak { display: flex; align-items: center; gap: 12px; border: 1px solid var(--app-ink); background: var(--app-paper); padding: 12px 14px; }
.ep-streak .n { font-family: var(--app-serif); font-style: italic; font-weight: 700; font-size: 24px; line-height: 1; }
.ep-streak .n.was { color: var(--app-ink-3); }
.ep-streak .n.now { color: var(--app-ink); }
.ep-streak .arw { color: var(--app-red); }
.ep-streak .l { font-size: 10px; line-height: 1.35; color: var(--app-ink-2); }
.ep-streak .l b { font-weight: 800; color: var(--app-ink); }
.ep-streak .rules { margin-left: auto; display: flex; gap: 2px; align-items: flex-end; }
.ep-streak .rules i { width: 3px; height: 13px; background: var(--app-paper-3); }
.ep-streak .rules i.on { background: var(--app-ink); }

/* the handoff — back to La Une / on to Le Feuilleton */
.ep-handoff { margin-top: 14px; display: grid; gap: 10px; }
.ep-handoff a {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  min-height: 54px; padding: 0 18px; text-decoration: none; border: 1.5px solid var(--app-ink);
  font-size: 12px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase;
}
.ep-handoff a.on { background: var(--app-red); color: #fff; box-shadow: 4px 4px 0 var(--ep-channel); }
.ep-handoff a.back { background: var(--app-paper); color: var(--app-ink); }
.ep-handoff a svg { width: 16px; height: 16px; flex: 0 0 auto; }

/* ============================================================
   RESUME · LOADING · ERROR (press-house system states)
   ============================================================ */
.ep-resume { padding: 30px 24px; text-align: center; }
.ep-resume .k { font-size: 9px; font-weight: 900; letter-spacing: .2em; text-transform: uppercase; color: var(--app-red); }
.ep-resume h2 { margin: 13px auto 0; max-width: 270px; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: 27px; line-height: 1.05; }
.ep-resume p { margin: 11px auto 0; max-width: 250px; font-size: 12.5px; line-height: 1.5; color: var(--app-ink-2); }
.ep-resume .stickwrap { margin: 20px auto 0; max-width: 260px; }
.ep-resume .cta { margin: 22px auto 0; display: inline-flex; align-items: center; gap: 10px; min-height: 52px; padding: 0 22px; background: var(--app-ink); color: var(--app-paper); border: 1.5px solid var(--app-ink); box-shadow: 5px 5px 0 var(--ep-channel); font-size: 12px; font-weight: 900; letter-spacing: .13em; text-transform: uppercase; cursor: pointer; }
.ep-resume .cta svg { width: 16px; height: 16px; }

.ep-skel { padding: 16px 20px; }
.ep-skel .l { background: var(--app-paper-3); height: 12px; margin-bottom: 10px; position: relative; overflow: hidden; }
.ep-skel .box { height: 120px; border: 1px solid var(--app-paper-3); background: var(--app-paper-2); margin: 14px 0; position: relative; overflow: hidden; }
@media (prefers-reduced-motion: no-preference) {
  .ep-skel .l::after, .ep-skel .box::after {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(100deg, transparent 20%, rgba(255,255,255,.32) 50%, transparent 80%);
    animation: ep-shim 1.4s linear infinite;
  }
}
@keyframes ep-shim { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
.ep-skel .press { text-align: center; font-family: var(--ep-mono); font-size: 9px; letter-spacing: .1em; color: var(--app-ink-3); margin-top: 8px; }

.ep-notice { margin: 16px 20px; border: 1.5px solid var(--app-red); background: var(--app-sheet); }
.ep-notice .nh { display: flex; align-items: center; gap: 8px; padding: 9px 13px; border-bottom: 1px solid var(--app-red); }
.ep-notice .nh .tri { width: 0; height: 0; border-style: solid; border-width: 0 6px 11px 6px; border-color: transparent transparent var(--app-red) transparent; }
.ep-notice .nh .t { font-size: 9px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; color: var(--app-red); }
.ep-notice .nb { padding: 12px 14px 14px; }
.ep-notice .nb .m { font-family: var(--app-serif); font-style: italic; font-size: 15px; line-height: 1.3; color: var(--app-ink); }
.ep-notice .retry { margin-top: 11px; display: inline-flex; align-items: center; gap: 7px; border: 1.5px solid var(--app-ink); background: var(--app-paper); padding: 8px 13px; font-size: 9.5px; font-weight: 900; letter-spacing: .12em; text-transform: uppercase; color: var(--app-ink); cursor: pointer; }
.ep-notice .retry svg { width: 13px; height: 13px; }

/* --ep-bon lifts one step in dark; driven by the GLOBAL app theme (the app does not
   set data-theme on .ep). Mirrors globals.css dark handling. */
:root[data-theme="dark"] .ep { --ep-bon: #5fb3a1; }
@media (prefers-color-scheme: dark) { :root[data-theme="system"] .ep { --ep-bon: #5fb3a1; } }
      `}</style>
  );
}
