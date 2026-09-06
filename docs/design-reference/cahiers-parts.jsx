/* Atelier — LES CAHIERS · primitives (Nc*)
   Reference back matter: rules index + word ledger + bound library.
   Every prop maps onto real API fields — see the "Données → props" board.
   One Babel scope; published to window at the end. */

function NcIcoGear() { return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3.2"></circle><path d="M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1"></path></svg>); }
function NcIcoBack() { return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 12H5M11 6l-6 6 6 6"></path></svg>); }
function NcIcoArrow() { return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M4 12h15M13 6l6 6-6 6"></path></svg>); }
function NcIcoX() { return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M5 5l14 14M19 5L5 19"></path></svg>); }
function NcIcoSearch() { return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="6.5"></circle><path d="M16 16l5 5"></path></svg>); }
function NcIcoFold({ open }) { return (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d={open ? "M5 15l7-7 7 7" : "M5 9l7 7 7-7"}></path></svg>); }

/* ---------- shell ---------- */
/* NcShell: theme 'light'|'dark' · wide → 430px check · big → large-dynamic-text
   Bottom tabs = existing chrome, unchanged (Carnet active). */
function NcShell({ dark = false, wide = false, big = false, motion = true, hint = null, children, screenLabel }) {
  return (
    <div className={'nc' + (dark ? ' dark' : '') + (wide ? ' w430' : '') + (big ? ' bigtype' : '') + (motion ? ' motion' : '')} data-screen-label={screenLabel}>
      {hint && <span className="nc-hint">{hint}</span>}
      <div className="nc-page">{children}</div>
      <NcTabs />
    </div>
  );
}
function NcTabs() {
  const Item = ({ label, active, shape }) => (
    <a href="#" className={active ? 'active' : ''}>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        {shape === 'sq' && <rect x="5" y="5" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" />}
        {shape === 'ci' && <circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" strokeWidth="1.8" />}
        {shape === 'tri' && <polygon points="12,5 20,19 4,19" fill="none" stroke="currentColor" strokeWidth="1.8" />}
        {shape === 'bk' && <path d="M6 5h12v14H6zM6 9h12" fill={active ? 'none' : 'none'} stroke="currentColor" strokeWidth="1.8" />}
      </svg>
      {label}
    </a>
  );
  return (
    <nav className="nc-tabs" aria-label="App navigation (existing)">
      <Item label="Atelier" shape="sq" />
      <Item label="Missions" shape="tri" />
      <Item label="Feuilleton" shape="ci" />
      <Item label="Carnet" shape="bk" active />
    </nav>
  );
}

/* ---------- masthead ---------- */
/* cefr: shell CEFR progress (level string) · cefr=null → designed absent state.
   slim: direct routes /grammar /vocabulary — one rubric line, no second hero. */
function NcMasthead({ cahier = 'Grammaire', cefr = 'A2.1 en cours', slim = false, route = null, xlink = null }) {
  if (slim) {
    return (
      <header className="nc-mast slim">
        <span className="rub"><b>Les Cahiers</b> · {route}</span>
        {xlink && <a className="xlink" href="#">{xlink} →</a>}
      </header>
    );
  }
  return (
    <header>
      <div className="nc-ears">
        <span className="ear-badge">Les Cahiers</span>
        <button className="ear-gear" aria-label="Settings"><NcIcoGear /></button>
      </div>
      <div className="nc-mast">
        <h1 className="name">Les Cahiers</h1>
        <div className="folio">
          <b>Référence de l’édition</b>
          <span className="dot"></span>
          {cefr ? <span>Cours · {cefr}</span> : <span className="off">Progression indisponible</span>}
        </div>
      </div>
    </header>
  );
}

/* ---------- mode tabs ---------- */
/* tabs: [{ id, label, meta }] — Bibliothèque appears only when the launch flag is on. */
function NcModeTabs({ active = 'grammaire', library = true, metas = {} }) {
  const tabs = [
    { id: 'grammaire', label: 'Grammaire', meta: metas.grammaire || 'Index des règles' },
    { id: 'vocabulaire', label: 'Vocabulaire', meta: metas.vocabulaire || 'Registre des mots' },
  ];
  if (library) tabs.push({ id: 'bibliotheque', label: 'Bibliothèque', meta: metas.bibliotheque || 'Lecture reliée' });
  return (
    <div className="nc-modetabs" role="tablist" aria-label="Modes du carnet">
      {tabs.map((t) => (
        <a key={t.id} href="#" role="tab" className="nc-tab" aria-selected={t.id === active ? 'true' : 'false'}>
          <span className="m">{t.label}</span>
          <span className="s">{t.meta}</span>
        </a>
      ))}
    </div>
  );
}

/* ---------- filing summary ---------- */
/* items: [{ n, label, tone: 'due'|'era'|null }] — counts derived from the lists themselves. */
function NcFilingSummary({ lead = 'Classement', items = [] }) {
  return (
    <div className="nc-filing" role="status">
      <span className="k">{lead}</span>
      {items.map((it, i) => (
        <React.Fragment key={i}>
          <span className="sep"></span>
          <span className={it.tone || ''}>{it.n != null ? it.n + ' ' : ''}{it.label}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

/* ---------- optional feuilleton file ---------- */
/* payload: current Feuilleton (title, ep). No payload → module disappears entirely. */
function NcFeuilleFile({ ep = 14, title }) {
  return (
    <a className="nc-feuille" href="#">
      <span className="spine" aria-hidden="true"></span>
      <span><span className="k">Le Feuilleton · classé au dossier</span><span className="t" style={{ display: 'block' }}>Épisode {ep} — {title}</span></span>
      <span className="go">Reprendre →</span>
    </a>
  );
}

/* ---------- search / chips / live summary ---------- */
function NcSearch({ placeholder }) {
  return (
    <div className="nc-search"><NcIcoSearch /><input type="search" placeholder={placeholder} aria-label={placeholder} /></div>
  );
}
function NcChips({ chips, active = 0 }) {
  return (
    <div className="nc-chips" role="group" aria-label="Filtres">
      {chips.map((c, i) => (
        <button key={c.l} className="nc-chip" aria-pressed={i === active ? 'true' : 'false'}>
          {c.l}{c.n != null && <span className="n">{c.n}</span>}
        </button>
      ))}
    </div>
  );
}
function NcLiveSum({ text, clearable = false }) {
  return (
    <div className="nc-livesum" aria-live="polite">
      <em>{text}</em>
      {clearable && <button className="clear">Effacer les filtres</button>}
    </div>
  );
}

/* ---------- ledger heads ---------- */
function NcLedgerHead({ t, n, tone = '' }) {
  return (<div className="nc-ledghead"><span className={'t ' + tone}>{t}</span>{n && <span className="n">{n}</span>}</div>);
}

/* ---------- grammar index row ---------- */
/* Maps display_title, level, localized category, mastery, state_label,
   next_review (due mark), due_errata_count. sel = query-selected concept. */
function NcDueMark({ label = 'À revoir' }) { return <span className="nc-due">{label}</span>; }
function NcStateStamp({ state = 'new', label }) {
  const map = { new: '', building: 'building', fragile: 'fragile', solid: 'solid', mastered: 'mastered' };
  return <span className={'nc-stamp ' + (map[state] || '')}>{label}</span>;
}
function NcIndexRow({ no, title, level, cat, mastery = 0, state = 'new', stateLabel = 'Nouveau', due = false, errata = 0, sel = false }) {
  return (
    <button className={'nc-row' + (sel ? ' sel' : '')} aria-label={title + ', ' + level + ' ' + cat + (due ? ', à revoir' : '')}>
      <span className="no">{String(no).padStart(2, '0')}</span>
      <span className="t">{title}</span>
      <span className="marks">
        {due ? <NcDueMark /> : <NcStateStamp state={state} label={stateLabel} />}
        {errata > 0 && <span className="nc-errdot"><i></i>{errata} errata</span>}
      </span>
      <span className="meta">
        <span>{level} · {cat}</span>
        <span className="lead" aria-hidden="true"></span>
        <span className="nc-pips" aria-label={'Maîtrise ' + mastery + ' sur 10'}>
          {Array.from({ length: 10 }, (_, i) => <i key={i} className={i < mastery ? 'on' : ''}></i>)}
        </span>
      </span>
    </button>
  );
}

/* ---------- word ledger row ---------- */
/* deck row: word, translation, part_of_speech, frequency_rank + mastery-map cell state.
   queue row: rank slot shows bucket instead. */
function NcWordRow({ rank, word, tr, pos, bucket = null, state = null, stateLabel = null, sel = false }) {
  return (
    <button className={'nc-wordrow' + (sel ? ' sel' : '')} aria-label={word + (tr ? ', ' + tr : '')}>
      <span className="rank">{rank != null ? '#' + rank : '·'}</span>
      <span className="w">{word}</span>
      <span className="marks">
        {bucket && <span className={'nc-bucket ' + bucket.id}><i></i>{bucket.label}</span>}
        {state && <span className={'nc-bucket ' + state}><i></i>{stateLabel}</span>}
      </span>
      <span className="tr">{tr}{pos ? ' · ' + pos : ''}</span>
    </button>
  );
}

/* ---------- fiche sections ---------- */
function NcSec({ kick, tone = '', ct, children }) {
  return (
    <section className="nc-sec">
      <div className={'kick ' + tone}>{kick}<span className="tail"></span>{ct && <span className="ct">{ct}</span>}</div>
      {children}
    </section>
  );
}
function NcExample({ fr, de }) {
  return (<div className="nc-ex"><span className="fr" dangerouslySetInnerHTML={{ __html: fr }}></span><span className="de">{de}</span></div>);
}
function NcErrRow({ q, d, recent = false }) {
  return (
    <div className={'nc-errow' + (recent ? ' recent' : '')}>
      <i aria-hidden="true"></i>
      <span className="q" dangerouslySetInnerHTML={{ __html: q }}></span>
      <span className="d">{d}</span>
    </div>
  );
}

/* ---------- notes en marge ---------- */
/* mode: 'idle' (empty or filled) | 'editing' | 'saving' | 'error' — personal_notes. */
function NcMarginNotes({ mode = 'idle', text = '', dirty = false }) {
  if (mode === 'idle') {
    return (
      <div className="nc-notes">
        <p className={'txt' + (text ? '' : ' ph')}>{text || 'Aucune note pour l’instant — la marge vous attend.'}</p>
        <div className="bar"><button className="act">{text ? 'Modifier' : 'Annoter'}</button>{text && <span className="st">Enregistrée</span>}</div>
      </div>
    );
  }
  const saving = mode === 'saving', err = mode === 'error';
  return (
    <div className={'nc-notes editing' + (saving ? ' saving' : '') + (err ? ' err' : '')}>
      <textarea defaultValue={text} aria-label="Notes en marge" readOnly={saving}></textarea>
      <div className="bar">
        <div style={{ display: 'flex', gap: 7 }}>
          <button className="act primary" disabled={saving}>{saving ? 'Envoi…' : 'Enregistrer'}</button>
          <button className="act" disabled={saving}>Annuler</button>
        </div>
        {err ? <span className="st bad">Échec — note conservée ici</span>
          : saving ? <span className="st dirty">Classement en cours</span>
          : dirty ? <span className="st dirty">Non enregistrée</span> : <span className="st">Brouillon</span>}
      </div>
      {err && (
        <div className="nc-notice inline" role="alert" style={{ marginTop: 9 }}>
          <span className="sq"></span>
          <span className="body"><b>Avis du bureau des archives</b><p>La note n’a pas pu être classée. Elle reste dans la marge. <button className="retry" style={{ minHeight: 32, marginTop: 6 }}>Retry</button></p></span>
        </div>
      )}
    </div>
  );
}

/* ---------- coverage track + mastery map ---------- */
function NcCoverageTrack({ lab, val, max, tone = '' }) {
  return (
    <div className="nc-track" role="progressbar" aria-valuenow={val} aria-valuemax={max} aria-label={lab}>
      <span className="lab">{lab}</span>
      <span className="bar"><i className={tone} style={{ width: Math.min(100, 100 * val / max) + '%' }}></i></span>
      <span className="num">{val} / {max}</span>
    </div>
  );
}
/* deterministic pseudo-random cells so both themes render identical maps */
function ncMapCells(n = 280, seed = 7) {
  const states = ['', '', '', 'building', 'solid', 'solid', 'mastered', 'due', 'fragile', 'solid', 'mastered', '', 'building', 'mastered'];
  const out = []; let x = seed;
  for (let i = 0; i < n; i++) { x = (x * 48271) % 2147483647; out.push(states[(x + (i < n * 0.4 ? 5 : 0)) % states.length]); }
  return out;
}
function NcMasteryMap({ n = 280, totals, note }) {
  const cells = React.useMemo(() => ncMapCells(n), [n]);
  return (
    <React.Fragment>
      <div className="nc-map" aria-hidden="true">{cells.map((s, i) => <i key={i} className={s}></i>)}</div>
      <div className="nc-maplegend" aria-label="Répartition des états">
        {totals.map((t) => <span key={t.id}><i className={t.id}></i>{t.label} {t.n}</span>)}
      </div>
      {note && <p className="nc-mapnote">{note}</p>}
    </React.Fragment>
  );
}

/* ---------- system: notice / skeleton / empty ---------- */
function NcNotice({ tone = 'red', label = 'Avis du bureau des archives', message, retry = true }) {
  return (
    <div className="nc-notice" role="alert">
      <span className={'sq ' + tone}></span>
      <span className="body"><b>{label}</b><p>{message}</p></span>
      {retry && <button className="retry">Retry</button>}
    </div>
  );
}
/* press/file skeleton — index rows setting into the ledger, never a spinner */
function NcSkeleton({ rows = 5, file = true }) {
  return (
    <div className="nc-skel" aria-hidden="true">
      {file && <div className="filecard"></div>}
      <div className="ln k" style={{ marginTop: 16 }}></div>
      {Array.from({ length: rows }, (_, i) => (
        <div className="srow" key={i}>
          <span className="ln no"></span>
          <span><span className="ln t" style={{ width: (82 - (i * 13) % 34) + '%' }}></span><span className="ln" style={{ width: '44%', height: 8 }}></span></span>
          <span className="ln" style={{ width: 46, height: 14 }}></span>
        </div>
      ))}
    </div>
  );
}
function NcEmpty({ title = 'Aucune fiche dans ce classement', body, action = null }) {
  return (
    <div className="nc-empty">
      <span className="mark" aria-hidden="true"></span>
      <h4>{title}</h4>
      {body && <p>{body}</p>}
      {action && <button className="act">{action}</button>}
    </div>
  );
}
function NcColophon({ text = 'Les Cahiers · référence de l’édition' }) {
  return <div className="nc-colophon">{text}</div>;
}

Object.assign(window, {
  NcIcoGear, NcIcoBack, NcIcoArrow, NcIcoX, NcIcoSearch, NcIcoFold,
  NcShell, NcTabs, NcMasthead, NcModeTabs, NcFilingSummary, NcFeuilleFile,
  NcSearch, NcChips, NcLiveSum, NcLedgerHead,
  NcDueMark, NcStateStamp, NcIndexRow, NcWordRow,
  NcSec, NcExample, NcErrRow, NcMarginNotes,
  NcCoverageTrack, NcMasteryMap, ncMapCells,
  NcNotice, NcSkeleton, NcEmpty, NcColophon,
});
