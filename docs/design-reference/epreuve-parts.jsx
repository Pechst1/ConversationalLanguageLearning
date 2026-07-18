/* ============================================================
   L'ÉPREUVE — the typesetter's grammar session · primitives.
   Every prop maps to a named field on the engineer's payload;
   the component-spec board carries the full contract.
   Round types: recognize · fill · transform · word-bank ·
   classify · produce · speak. One exercise at a time; one
   primary action; ExerciseShell / FeedbackSheet / ProgressBar
   contracts extended, never broken.
   ============================================================ */

/* ---- press chrome icons (grotesk only) --------------------- */
const EpIco = {
  close: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="square"><path d="M5 5l14 14M19 5L5 19"/></svg>,
  ask:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 9a3 3 0 1 1 4 2.8c-1 .5-1.5 1-1.5 2.2"/><circle cx="11.5" cy="18" r="1.1" fill="currentColor" stroke="none"/></svg>,
  arrow: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M4 12h15M13 6l6 6-6 6"/></svg>,
  check: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="square"><path d="M4 12.5l5 5 11-12"/></svg>,
  play:  <svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M7 4l13 8-13 8z"/></svg>,
  mic:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>,
  home:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 11l8-6 8 6v8H4z"/></svg>,
  book:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 5h7v14H4zM13 5h7v14h-7z"/></svg>,
  pencil:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 20l1-4L16 5l3 3L8 19z"/><path d="M14 7l3 3"/></svg>,
  retry: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M4 11a8 8 0 0 1 14-5l2 2M20 5v4h-4"/></svg>,
};

/* ============================================================
   SHELL
   ============================================================ */
function EpShell({ theme = 'light', children, style }) {
  return <div className="ep" data-theme={theme} style={style}>{children}</div>;
}

/* ============================================================
   THE COMPOSING STICK (progress) — replaces ProgressBar.
   groups[]: { total, set, current } — one per concept; concept
   boundaries read as line breaks. fields: completedDrills,
   totalDrills, concept boundaries.
   ============================================================ */
function EpStick({ groups, cap, full, labels }) {
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

/* ============================================================
   TOPBAR — close · composing stick · Finish
   ============================================================ */
function EpTopbar({ groups, cap, onClose }) {
  return (
    <div className="ep-top">
      <button className="ic" title="Fermer" onClick={onClose}>{EpIco.close}</button>
      <EpStick groups={groups} cap={cap} />
      <button className="finish">Terminer</button>
    </div>
  );
}

/* ============================================================
   THE EXERCISE SHEET header — eyebrow · provenance · concept
   title + motif · rule toggle
   fields: round_label, mode, index/total, provenance(errata),
   concept.title, atelier_blueprint.visual_motif, payload.rule_panel
   ============================================================ */
function EpEyebrow({ round, mode, i, n, retour }) {
  return (
    <div className="ep-eyebrow">
      <span>{round}</span><i></i><span className="mode">{mode}</span>
      {retour && <span className="ep-retour"><span className="d"></span>Retour · déjà corrigé</span>}
      <span className="idx">{i} / {n}</span>
    </div>
  );
}

/* provenance — a resurfaced past error (source data on errata) */
function EpProvenance({ children }) {
  return <div className="ep-prov">{children}</div>;
}

function EpConcept({ title, motif, askOn, onAsk }) {
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

/* ---- ASSEMBLING MOTIF -------------------------------------
   prims[]: { shape:'circle'|'square'|'triangle'|'block', cx, cy, s,
              printed, printing, role }. One prints per round done.
   ============================================================ */
function epShape(p, key) {
  const cls = 'shp ' + ({ circle: 'c-circle', square: 'c-square', triangle: 'c-tri', block: 'c-block' }[p.shape]);
  if (p.shape === 'circle') return <circle key={key} className={cls} cx={p.cx} cy={p.cy} r={p.s / 2} />;
  if (p.shape === 'triangle') {
    const h = p.s, half = p.s / 2;
    const pts = `${p.cx},${p.cy - half} ${p.cx + half},${p.cy + half} ${p.cx - half},${p.cy + half}`;
    return <polygon key={key} className={cls} points={pts} />;
  }
  // square + block
  return <rect key={key} className={cls} x={p.cx - p.s / 2} y={p.cy - p.s / 2} width={p.s} height={p.s} />;
}
function EpMotif({ prims = [], done, canvas = 46 }) {
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

/* ---- THE RULE SHEET ---------------------------------------- */
function EpRule({ kicker = 'La règle', lede, examples = [], onClose }) {
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

/* ============================================================
   PROMPT LINE + meaning cue
   ============================================================ */
function EpPrompt({ label = 'Réglez la ligne', children, cue }) {
  return (
    <div className="ep-prompt">
      <div className="lab">{label}</div>
      <div className="ep-line">{children}</div>
      {cue && <div className="ep-cue">{cue}</div>}
    </div>
  );
}
function Blank({ children, set }) {
  return <span className={'blank' + (set ? ' set' : '')}>{children || '\u00a0\u00a0\u00a0\u00a0'}</span>;
}

/* ============================================================
   RECOGNIZE / FILL — option sorts
   fields: options[] / fill.items[].choices[]
   ============================================================ */
function EpOpts({ children }) { return <div className="ep-opts">{children}</div>; }
function EpOpt({ chosen, right, wrong, children, onClick }) {
  return <button className={'ep-opt' + (chosen ? ' chosen' : '') + (right ? ' right' : '') + (wrong ? ' wrong' : '')} onClick={onClick}>{children}</button>;
}
function EpChoices({ children }) { return <div className="ep-choices">{children}</div>; }

/* ============================================================
   MOVABLE TYPE (word-bank) — tokens[] → answer_tokens[]
   fields: tokens[], answer_tokens[], meaning_cue
   ============================================================ */
function EpSlug({ children, spent, set, onClick }) {
  return <button className={'ep-slug' + (spent ? ' spent' : '') + (set ? ' set' : '')} onClick={onClick}>{children}</button>;
}
function EpSetLine({ empty, children }) {
  return <div className={'ep-setline' + (empty ? ' empty' : '')}>{children}</div>;
}
function EpCase({ label, count, children }) {
  return (
    <div className="ep-case">
      <div className="cap"><span>{label}</span>{count != null && <span>{count} sortes</span>}</div>
      <div className="sorts">{children}</div>
    </div>
  );
}

/* CLASSIFY — labelled cases */
function EpCases({ boxes }) {
  return (
    <div className="ep-cases">
      {boxes.map((b, i) => (
        <div className="ep-casebox" key={i}>
          <div className="ch">{b.label}</div>
          <div className="cbody">{b.slugs.map((s, j) => <EpSlug key={j} set>{s}</EpSlug>)}</div>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
   PRODUCE — free composition field
   ============================================================ */
function EpProduce({ typed, placeholder, caret = true }) {
  return (
    <div className="ep-produce">
      <div className="ep-field">
        {typed ? <span>{typed}</span> : <span className="ph">{placeholder}</span>}
        {caret && <span className="caret"></span>}
      </div>
    </div>
  );
}

/* ============================================================
   CONFIDENCE TAP — sûr / pas sûr, skippable
   fields: confidence_tap ('sure'|'unsure'|null)
   ============================================================ */
function EpConfidence({ value, onPick }) {
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

/* ============================================================
   PRIMARY ACTION — ink press-bar + verdict line
   ============================================================ */
function EpVerdict({ tone = 'go', children }) {
  return <div className={'ep-verdict ' + tone}><span>{children}</span><span className="ln"></span></div>;
}
function EpBar({ children, tone, disabled, icon = 'check', onClick }) {
  return (
    <button className={'ep-bar' + (tone ? ' ' + tone : '')} disabled={disabled} onClick={onClick}>
      <span>{children}</span>{icon && EpIco[icon]}
    </button>
  );
}
function EpFoot({ children }) { return <div className="ep-foot">{children}</div>; }

/* ============================================================
   PROOFREADER'S MARKS — the feedback language (the heart)
   fields: correction.errata[]{learner_text, corrected_target,
   why_wrong/reason, display_label}, payload.xray{sentence, marks[]}
   ============================================================ */
/* a replace mark: struck learner span + red fix above with caret */
function EpFix({ old, fix }) {
  return (
    <span className="ep-fix">
      <span className="new">{fix}</span>
      <span className="car">‸</span>
      <span className="old">{old}</span>
    </span>
  );
}
/* an insertion mark: a caret between words, the missing word above */
function EpIns({ fix }) {
  return (
    <span className="ep-ins">
      <span className="new">{fix}</span>
      <span className="car">‸</span>
    </span>
  );
}
function EpGalley({ label = 'Marques du correcteur', anchor, children, why, relecture }) {
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
/* async AI second look — resolves in place */
function EpRelecture({ status = 'pending', children }) {
  if (status === 'pending') {
    return <div className="ep-relecture pending"><span>Relecture en cours</span><span className="dots"><i></i><i></i><i></i></span></div>;
  }
  return <div className="ep-relecture done">{children}</div>;
}

/* ---- BON stamp + correct moment (no modal) ----------------- */
function EpBonStamp({ struck }) {
  return (
    <div className={'ep-bon-stamp' + (struck ? ' ep-struck' : '')}>
      <span>Bon</span><span className="d">à tirer</span>
    </div>
  );
}
function EpCorrect({ said, struck }) {
  return (
    <div className="ep-correct">
      <EpBonStamp struck={struck} />
      <div className="said">{said}</div>
    </div>
  );
}

/* ============================================================
   TYPED MICRO-REPAIR — "Recopie la correction :"
   fields: repair.target, repair.typed, repair.status
   ============================================================ */
function EpRepair({ target, typed = '', status, errFrom }) {
  const ghost = target.slice(typed.length);
  const okChars = errFrom == null ? typed.length : errFrom;
  const good = typed.slice(0, okChars);
  const bad = errFrom == null ? '' : typed.slice(errFrom);
  return (
    <div className="ep-repair">
      <div className="rh">Recopie la correction</div>
      <div className="rf">
        <div className={'ep-typefield' + (status === 'ok' ? ' ok' : status === 'no' ? ' no' : '')}>
          <span className="typed">{good}</span>
          {bad && <span className="typed err">{bad}</span>}
          {status !== 'ok' && <span className="caret"></span>}
          <span className="ghost">{ghost}</span>
        </div>
        {status === 'ok' && <div className="rmeta ok">— Ligne recomposée · juste —</div>}
        {status === 'no' && <div className="rmeta no">— La lettre diffère · reprenez le sort —</div>}
      </div>
    </div>
  );
}

/* ============================================================
   ÉCOUTER + SHADOWING (speak round)
   fields: tts_url (écouter), record.status (idle/recording/transcribing),
   transcript (→ marked like any answer)
   ============================================================ */
function EpListen({ fr, disabled, playing }) {
  return (
    <div className={'ep-listen' + (disabled ? ' disabled' : '')}>
      <button className="play">{EpIco.play}</button>
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
function EpRecord({ status = 'idle' }) {
  const st = { idle: 'Appuyez pour répéter', recording: 'Enregistrement…', transcribing: 'Transcription…' }[status];
  return (
    <div className={'ep-record ' + status}>
      {status === 'transcribing'
        ? <div className="rollers"><i></i><i></i><i></i></div>
        : <button className="mic">{EpIco.mic}</button>}
      <div className="st">{st}</div>
    </div>
  );
}

/* ============================================================
   EARLY MASTERY LOCK — "PLOMB VERROUILLÉ"
   fields: early_lock (concept ended clean)
   ============================================================ */
function EpLock({ motif, title, promo }) {
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

/* ============================================================
   BON À TIRER — the session-completion stamp
   ============================================================ */
function EpBatStage({ sub }) {
  return (
    <div className="ep-bat-stage">
      <div className="ep-bat ep-struck"><span className="m">Bon à tirer</span><span className="d">Édition prête</span></div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

/* ============================================================
   RECAP — the proof sheet · l'épreuve
   ============================================================ */
function EpRecapHead({ date }) {
  return (
    <div className="ep-recap-head">
      <div className="folio"><span>Atelier</span><i></i><span>La séance</span><i></i><span>L’épreuve</span></div>
      <h1>L’épreuve</h1>
      <div className="date">{date}</div>
    </div>
  );
}
function EpTally({ items }) {
  return (
    <div className="ep-tally">
      {items.map((it, i) => <div className="t" key={i}><div className="n">{it.n}</div><div className="l">{it.l}</div></div>)}
    </div>
  );
}
function EpProof({ lines }) {
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
function EpPhrase({ quote, by }) {
  return (
    <div className="ep-phrase">
      <div className="flag">À paraître demain</div>
      <div className="q">« {quote} »</div>
      <div className="by"><span className="ln"></span><span>{by}</span></div>
    </div>
  );
}
/* the fused logo token — set from house forms */
function EpToken() {
  return (
    <div className="ep-token">
      <div className="lt">
        <svg viewBox="0 0 24 24"><circle className="shp c-circle" cx="8" cy="8" r="5"/></svg>
        <svg viewBox="0 0 24 24"><rect className="shp c-square" x="12" y="3" width="9" height="9"/></svg>
        <svg viewBox="0 0 24 24"><polygon className="shp c-tri" points="12,13 20,21 4,21"/></svg>
      </div>
    </div>
  );
}
function EpMint({ note, tokens = 2 }) {
  return (
    <div className="ep-mint">
      <div className="tx"><b>Jetons frappés</b><span>{note}</span></div>
      <div className="tokens">{Array.from({ length: tokens }).map((_, i) => <EpToken key={i} />)}</div>
    </div>
  );
}
/* the seal — printer's colophon; gilt for a flawless run */
function EpSeal({ gilt, label = 'ATELIER · BON À TIRER', stamp }) {
  return (
    <div className={'ep-seal' + (gilt ? ' gilt' : '') + (stamp ? ' stamp' : '')}>
      <div className="med">
        <svg className="ring" viewBox="0 0 116 116">
          <defs><path id="ep-ring-p" d="M58,58 m-44,0 a44,44 0 1,1 88,0 a44,44 0 1,1 -88,0" /></defs>
          <text><textPath href="#ep-ring-p" startOffset="0">{label} · {label}</textPath></text>
        </svg>
        <div className="core">
          <svg viewBox="0 0 58 58"><circle className="shp c-circle" cx="20" cy="20" r="12"/></svg>
          <svg viewBox="0 0 58 58"><rect className="shp c-square" x="30" y="8" width="20" height="20"/></svg>
          <svg viewBox="0 0 58 58"><polygon className="shp c-tri" points="29,30 50,52 8,52"/></svg>
        </div>
      </div>
    </div>
  );
}
function EpStreak({ was, now, rules = 5, on = 4 }) {
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
function EpHandoff({ next = 'Le Feuilleton' }) {
  return (
    <div className="ep-handoff">
      <a className="on" href="#"><span>Lire {next}</span>{EpIco.book}</a>
      <a className="back" href="#"><span>Revenir à La Une</span>{EpIco.home}</a>
    </div>
  );
}

/* ============================================================
   SYSTEM STATES — resume · loading · error
   ============================================================ */
function EpResume({ groups, cap }) {
  return (
    <div className="ep-resume">
      <div className="k">Séance en cours</div>
      <h2>La ligne était à moitié réglée.</h2>
      <p>Vous avez composé quatre sortes. Reprenez là où le plomb attend.</p>
      <div className="stickwrap"><EpStick groups={groups} cap={cap} /></div>
      <button className="cta">{EpIco.arrow}<span>Reprendre la composition</span></button>
    </div>
  );
}
function EpSkeleton() {
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
function EpNotice({ msg = 'La séance n’a pas pu être composée. Le texte est sauvegardé ; la rédaction réessaie.' }) {
  return (
    <div className="ep-notice">
      <div className="nh"><span className="tri"></span><span className="t">Avis de la rédaction</span></div>
      <div className="nb">
        <div className="m">{msg}</div>
        <button className="retry">{EpIco.retry}<span>Réessayer</span></button>
      </div>
    </div>
  );
}

Object.assign(window, {
  EpIco, EpShell, EpStick, EpTopbar,
  EpEyebrow, EpProvenance, EpConcept, EpMotif, EpRule,
  EpPrompt, Blank, EpOpts, EpOpt, EpChoices,
  EpSlug, EpSetLine, EpCase, EpCases, EpProduce,
  EpConfidence, EpVerdict, EpBar, EpFoot,
  EpFix, EpIns, EpGalley, EpRelecture, EpBonStamp, EpCorrect, EpRepair,
  EpListen, EpRecord, EpLock, EpBatStage,
  EpRecapHead, EpTally, EpProof, EpPhrase, EpToken, EpMint, EpSeal, EpStreak, EpHandoff,
  EpResume, EpSkeleton, EpNotice,
});
