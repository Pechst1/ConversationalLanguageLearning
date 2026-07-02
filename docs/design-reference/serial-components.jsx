/* Atelier — Serial World components.
   One Babel scope; published to window at the end. Reuses the
   editorial chrome (Head / Nav / Edition / Mark) from roadmap.jsx. */

/* ---------- small icons (local, self-contained) ---------- */
function SArrow() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square">
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  );
}
function STick() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="var(--paper)" strokeWidth="3" strokeLinecap="square">
      <path d="M4 12.5l5 5 11-12" />
    </svg>
  );
}
function SEye() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="2.6" />
    </svg>
  );
}
function SQuill() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" strokeLinejoin="round">
      <path d="M5 19l3-9 9-5-5 9-7 5z" /><path d="M8 16l4-4" />
    </svg>
  );
}

/* ---------- the cast ---------- */
const CAST = {
  marin:    { id: 'marin',    name: 'Marin Lévêque',  ini: 'M',  role: 'Le voisin' },
  lila:     { id: 'lila',     name: 'Lila Bonnet',    ini: 'L',  role: 'Sa sœur' },
  gus:      { id: 'gus',      name: 'Augustin “Gus”', ini: 'G',  role: 'Habitué du Mistral' },
  romy:     { id: 'romy',     name: 'Romy Tremblay',  ini: 'R',  role: 'Reporter radio' },
  margaux:  { id: 'margaux',  name: 'Margaux',        ini: 'Mx', role: 'Au comptoir' },
  marchand: { id: 'marchand', name: 'M. Marchand',    ini: 'M·', role: 'Le propriétaire' },
  toi:      { id: 'toi',      name: 'Toi',            ini: 'T',  role: 'You' },
};

/* ---------- character marks ---------- */
function Avatar({ who, size = '', mood }) {
  const c = CAST[who] || CAST.toi;
  return (
    <span className={'s-ava ' + size} data-char={who} style={c.ini.length > 1 ? { fontSize: size === 'lg' ? 19 : 15 } : null}>
      {c.ini}
      {mood && <span className={'mood-pip ' + mood}><i /></span>}
    </span>
  );
}
function CharChip({ who, withRole }) {
  const c = CAST[who] || CAST.toi;
  return (
    <span className="s-chip" data-char={who}>
      <span className="sw" />{c.name}{withRole && <span className="role">· {c.role}</span>}
    </span>
  );
}

/* ---------- speech bubble ---------- */
function Said({ who, line, gloss, you }) {
  const c = CAST[who] || CAST.toi;
  return (
    <div className={'s-said' + (you ? ' you' : '')} data-char={who}>
      <Avatar who={who} size="sm" />
      <div className="s-bubble">
        <div className="who">{c.name}</div>
        <div className="line">{line}</div>
        {gloss && <div className="gloss">{gloss}</div>}
      </div>
    </div>
  );
}

/* ============================================================
   A1 — THE SERIAL ON-RAMP CARD
   ============================================================ */
function ThreadCard({ variant = 'act', who = 'marchand', ep, prev, beat, title, sub, cta, ctaInk }) {
  const inner = (
    <React.Fragment>
      <div className="ttop">
        <Mark size={18} />
        <span className="ser">The serial</span>
        <span className="ep">{ep}</span>
      </div>
      {prev && <div className="prev"><b>Previously —</b> {prev}</div>}
      <div className="tmain" data-char={who}>
        <Avatar who={who} size="lg" mood={variant === 'act' ? 'confused' : 'warm'} />
        <div>
          <div className="beat">{beat}</div>
          <h2>{title}</h2>
          <div className="sub">{sub}</div>
        </div>
      </div>
      {cta && <div className={'tcta' + (ctaInk ? ' ink' : '')}>{cta} <SArrow /></div>}
    </React.Fragment>
  );
  const cls = 's-thread' + (variant === 'invite' ? ' invite' : '') + (variant === 'rest' ? ' rest' : '');
  return <a className={cls} href="#" data-char={who}>{inner}</a>;
}

/* ============================================================
   A2 — THE ACT SCREEN PARTS
   ============================================================ */
function ReplyCard({ who, mood, moodLabel, loc, speech, gloss, ink, needs, score }) {
  const c = CAST[who];
  return (
    <div className="s-reply" data-char={who}>
      <div className="rhead">
        <Avatar who={who} mood={mood} />
        <div>
          <div className="nm">{c.name}</div>
          <div className="mood">{moodLabel}</div>
        </div>
        <div className="loc">{loc}</div>
      </div>
      <div className="rbody">
        <div className={'speech' + (ink ? ' ink' : '')}>{speech}</div>
        {gloss && <div className="gloss">{gloss}</div>}
        {needs && (
          <div className="s-needs">
            <div className="cap">What the scene still needs</div>
            {needs.map((n, i) => (
              <div className={'n ' + (n.met ? 'met' : 'miss')} key={i}>
                <span className="box">{n.met && <STick />}</span>
                <span className="t">{n.t}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {score != null && (
        <div className="s-score">
          <span className="cap">Accuracy · optional</span>
          <span className="pips">{[0,1,2,3].map(i => <i key={i} className={i < score ? 'on' : ''} />)}</span>
        </div>
      )}
    </div>
  );
}

function RepairSlip({ why, children }) {
  return (
    <div className="s-repair">
      <div className="rh"><span className="tri" /><span className="t">He didn’t follow you</span></div>
      <div className="rb">
        <div className="why">{why}</div>
        <div className="fix">{children}</div>
      </div>
    </div>
  );
}

function OutcomeHook({ what, hook, cta }) {
  return (
    <div className="s-outcome">
      <div className="cap">— The scene resolves —</div>
      <div className="what">{what}</div>
      <div className="hook">{hook}</div>
      <a className="s-cta-see" href="#">{cta} <SEye /></a>
    </div>
  );
}

/* a quiet context anchor strip used atop the Act screen */
function ContextAnchor({ loc, partner }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 0 13px', borderBottom: '1px solid var(--ink)', marginBottom: 14 }}>
      <span style={{ fontSize: 8.5, fontWeight: 900, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>Scène</span>
      <span style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 15, color: 'var(--ink)' }}>{loc}</span>
      <span style={{ marginLeft: 'auto' }}><CharChip who={partner} /></span>
    </div>
  );
}

/* ============================================================
   A3 — THE SERIAL READER PARTS
   ============================================================ */
function ReaderMast({ kicker, title, ep, loc, news }) {
  return (
    <React.Fragment>
      <div className="s-mast">
        <div className="kicker">{kicker}</div>
        <div className="title">{title}</div>
        <div className="dateline"><span>Épisode {ep}</span><i /><span>{loc}</span><i /><span>Samedi 31 mai</span></div>
      </div>
      {news && (
        <div className="s-news">
          <span className="lbl">Cette semaine</span>
          <span className="txt">{news}</span>
        </div>
      )}
    </React.Fragment>
  );
}

function PreviouslyOn({ children }) {
  return (
    <div className="s-prev">
      <div className="ph"><span className="tag">▸ Previously on</span><span className="tag stamp2">Ép. 3</span></div>
      <div className="pb">{children}</div>
    </div>
  );
}

/* a single vertical-scroll panel: striped art + framed caption + optional float bubble */
function Panel({ n, h = 200, frame, dir, caption, float, full }) {
  return (
    <div className={'s-panel' + (full ? ' full' : '')}>
      <div className="s-art" style={{ height: h }}>
        <span className="frame-note">{frame}</span>
        {dir && <span className="stage-dir">{dir}</span>}
        {float && (
          <div className="float" style={float.pos}>
            <Said who={float.who} line={float.line} you={float.you} />
          </div>
        )}
      </div>
      {caption && <div className="s-cap"><span className="n">{n}</span><span className="c">{caption}</span></div>}
    </div>
  );
}

/* the choice fork — authoring the protagonist's line */
function ChoiceFork({ prompt, options }) {
  return (
    <div className="s-fork">
      <div className="fh"><Avatar who="toi" size="sm" /><span className="q"><b>You write the next line.</b> {prompt}</span></div>
      <div className="opts">
        {options.map((o, i) => (
          <a className={'opt' + (o.chosen ? ' chosen' : '')} href="#" key={i} data-char="toi">
            <span className="pick">{o.chosen ? 'Your line' : 'Option ' + String.fromCharCode(65 + i)}</span>
            <span className="line">{o.line}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   A4 — THE CLIFFHANGER CARD
   ============================================================ */
function Cliffhanger({ who, frame, float, line, question, beat, cta, next, tone }) {
  return (
    <div className="s-cliff" data-char={who}>
      <div className="ctop"><span className="ser">The cliffhanger</span><span className="end">— à suivre —</span></div>
      <div className="cart">
        <span className="frame-note">{frame}</span>
        {float && (
          <div className="float" style={float.pos}>
            <Said who={who} line={float.line} />
          </div>
        )}
      </div>
      <div className="cbody">
        <div className="who">{CAST[who].name} · {CAST[who].role}</div>
        <div className="q">{question}</div>
        <div className="beat">{beat}</div>
        <a className="ccta" href="#">{cta} <SQuill /></a>
        <div className="next">{next}</div>
      </div>
    </div>
  );
}

function VocabRecap({ words }) {
  return (
    <div className="s-recap">
      <div className="rh"><span className="t">Picked up this episode</span><span className="meta">{words.length} words · filed to Notebook</span></div>
      <div className="words">
        {words.map((w, i) => (
          <div className="w" key={i}>
            <span className="dot" /><span className="fr">{w.fr}</span><span className="en">{w.en}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   A5 — THREAD MAP
   ============================================================ */
function ThreadMap({ episodes }) {
  return (
    <div className="s-map">
      {episodes.map((e, i) => (
        <div className={'s-ep ' + (e.up ? 'up ' : '') + (i === 0 ? 'first ' : '') + (i === episodes.length - 1 ? 'last' : '')} key={i} data-char={e.who}>
          <span className="dot2">{e.up ? e.n : e.n}</span>
          <div className="ebody">
            <div className="edate">Ép. {e.n} · {e.date} · {e.loc}</div>
            <div className="ehook">{e.hook}</div>
            {!e.up && (
              <div className="eplate">
                <div className="thumb"><span>{e.plate}</span></div>
                <div className="choice"><b>You chose</b><em>{e.choice}</em></div>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

Object.assign(window, {
  CAST, Avatar, CharChip, Said,
  ThreadCard,
  ReplyCard, RepairSlip, OutcomeHook, ContextAnchor,
  ReaderMast, PreviouslyOn, Panel, ChoiceFork,
  Cliffhanger, VocabRecap, ThreadMap,
  SArrow, STick, SEye, SQuill,
});
