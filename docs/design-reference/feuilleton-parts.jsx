/* ============================================================
   LE FEUILLETON — shared "supplement" primitives + world data
   Every prop maps to a named field on the engineer's payload;
   see the component-spec board for the full contract.
   ============================================================ */

/* ---- tiny press icons (grotesk chrome only) ---------------- */
const FeIco = {
  back: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M14 6l-6 6 6 6"/></svg>,
  play: <svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M7 4l13 8-13 8z"/></svg>,
  pause: <svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>,
  arrow: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M5 12h13M13 6l6 6-6 6"/></svg>,
  sound: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9a4 4 0 0 1 0 6"/></svg>,
  home: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 11l8-6 8 6v8H4z"/></svg>,
  courrier: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="6" width="18" height="12"/><path d="M3 7l9 6 9-6"/></svg>,
  book: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 5h7v14H4zM13 5h7v14h-7z"/></svg>,
  cast: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="9" cy="9" r="3"/><path d="M4 20a5 5 0 0 1 10 0M15 8a3 3 0 0 1 0 6"/></svg>,
};

/* ---- the season cast (world bible ids) --------------------- */
const FE_CAST = {
  romy:     { id: 'romy', ini: 'R', name: 'Romy Tremblay',   role: 'Reporter · Le Fil',       loc: 'Le Mistral' },
  marin:    { id: 'marin', ini: 'M', name: 'Marin Lévêque',   role: 'Skipper',                 loc: 'Le Vieux-Port' },
  lila:     { id: 'lila', ini: 'L', name: 'Lila Bonnet',      role: 'Libraire',                loc: 'La Marge' },
  gus:      { id: 'gus', ini: 'G', name: 'Augustin “Gus”',   role: 'Barman · Le Mistral',     loc: 'Le Mistral' },
  margaux:  { id: 'margaux', ini: 'Mx', name: 'Margaux Roy',   role: 'Chef de cuisine',         loc: 'Chez Margaux' },
  marchand: { id: 'marchand', ini: 'Mr', name: 'M. Marchand',  role: 'Rédacteur en chef',       loc: 'La Rédaction' },
};

/* ============================================================
   SHELL + CHROME
   ============================================================ */
function FeShell({ theme = 'light', char, children, style }) {
  return (
    <div className="fe" data-theme={theme} data-char={char} style={style}>
      {children}
    </div>
  );
}

function FeChrome({ en = false, dest = 'La Une' }) {
  return (
    <div className="fe-chrome">
      <a className="back" href="#">{FeIco.back}<span>{dest}</span></a>
      <button className={'en' + (en ? ' on' : '')}>EN</button>
    </div>
  );
}

/* ============================================================
   A. DATELINE MASTHEAD  +  reading-progress rule
   fields: episode_index, title, dateline, season
   ============================================================ */
function FeMasthead({ season = 1, index, title, dateline, progress = 0, progressRed }) {
  return (
    <React.Fragment>
      <div className="fe-mast">
        <div className="folio">
          <span>Le Feuilleton</span><i></i>
          <span>Saison {season}</span><i></i>
          <span>Épisode {index}</span>
        </div>
        <div className="kicker">Le supplément illustré de l’édition</div>
        <h1>{title}</h1>
        <div className="dateline">
          {dateline.map((d, i) => (
            <React.Fragment key={i}>{i > 0 && <i></i>}<span>{d}</span></React.Fragment>
          ))}
        </div>
      </div>
      <div className={'fe-progress' + (progressRed ? ' red' : '')}>
        <i style={{ width: progress + '%' }}></i>
      </div>
    </React.Fragment>
  );
}

/* ============================================================
   PREVIOUSLY — one line: what your last reply changed
   fields: previously.text (with <u> for the consequence), episode_ref
   ============================================================ */
function FePreviously({ epRef, children }) {
  return (
    <div className="fe-previously">
      <div className="ph"><span className="tag">Précédemment</span><span className="ep">{epRef}</span></div>
      <div className="pb">{children}</div>
    </div>
  );
}

/* ============================================================
   B. PANEL — frame · on-art bubbles · caption · credit · play
   fields: panel.{image_url, slug, direction, bubbles[], caption,
           credit, audio_payload}
   ============================================================ */
function FePanel({ slug, direction, ratio, bubbles = [], narration = [], caption, capNum, credit,
                  play, onPlay, status, statusNote, full, colorable }) {
  const cls = 'fe-art'
    + (ratio ? ' ' + ratio : '')
    + (status ? ' ' + status : '')
    + (colorable ? ' fe-colorable' : '');
  return (
    <div className={'fe-panel' + (full ? ' full' : '')}>
      <div className={cls}>
        {status === 'generating' ? (
          <React.Fragment>
            <div className="rollers"><i></i><i></i><i></i></div>
            <div className="press-note">{statusNote || 'On tire la planche…'}</div>
          </React.Fragment>
        ) : status === 'delayed' ? (
          <div className="apology">
            <div className="k">Planche retardée</div>
            <div className="m">{statusNote || 'La presse a pris du retard. Le texte mène ; l’image suit sous peu.'}</div>
          </div>
        ) : (
          <React.Fragment>
            {slug && <div className="slug">{slug}</div>}
            {direction && <div className="dir">{direction}</div>}
            {play !== undefined && (
              <button className={'fe-panel-play' + (play === 'playing' ? ' playing' : '')} onClick={onPlay}>
                {play === 'playing' ? FeIco.pause : FeIco.play}
              </button>
            )}
            {narration.map((n, i) => (
              <div className="fe-narr" key={'n' + i} style={n.at}><div className="t">{n.t}</div></div>
            ))}
            {bubbles.map((b, i) => <FeBubble key={i} {...b} />)}
          </React.Fragment>
        )}
      </div>
      {credit && (
        <div className="fe-credit"><span>{credit}</span><span className="rule"></span><span>Le Feuilleton</span></div>
      )}
      {caption && (
        <div className="fe-cap">
          <div className="n">{capNum}</div>
          <div className="c">{caption}</div>
        </div>
      )}
    </div>
  );
}

/* on-art SPEECH bubble (tail) — pos {left/right/top/bottom}, tail bl|br|tl */
function FeBubble({ who, char, fr, en, at, tail = 'bl' }) {
  return (
    <div className="fe-bubble" data-tail={tail} data-char={char} style={at}>
      {who && <div className="who">{who}</div>}
      <div className="fr">{fr}</div>
      {en && <div className="en">{en}</div>}
    </div>
  );
}

/* transcript fallback for a panel (audio-only / a11y) */
function FeTranscript({ char, lines }) {
  return (
    <div className="fe-transcript" data-char={char}>
      {lines.map((l, i) => <div className="line" key={i}><b>{l.who} —</b> {l.fr}</div>)}
    </div>
  );
}

/* ============================================================
   RELATIONSHIP CUE — register + closeness, in-scene
   fields: cast.relationship.{register, closeness}
   ============================================================ */
function FeRelChip({ char, name, register = 'vous', closeness = 0 }) {
  const c = FE_CAST[char];
  return (
    <div className="fe-rel" data-char={char}>
      <div className="ava">{c ? c.ini : '?'}</div>
      <div className="meta">
        <div className="nm">{name || (c && c.name)}</div>
        <div className="rr">
          <span className={'reg' + (register === 'tu' ? ' tu' : '')}>{register}</span>
          <span className="pips">
            {[0,1,2,3,4].map(i => <i key={i} className={i < closeness ? 'on' : ''}></i>)}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   AUDIO — "Écouter l'épisode": pinned bar + inline CTA
   fields: scene.audio.{duration, position, panel_ticks[]}
   ============================================================ */
function FeAudioBar({ playing, title = 'Écouter l’épisode', now, at = 0, ticks = [], time = '0:00 / 4:12' }) {
  return (
    <div className={'fe-audio' + (playing ? ' playing' : '')}>
      <div className="row">
        <button className="play">{playing ? FeIco.pause : FeIco.play}</button>
        <div className="lab">
          <div className="k">{playing ? 'Lecture en cours' : 'Version sonore'}</div>
          <div className="t">{title}</div>
        </div>
        <div className="time">{time}</div>
      </div>
      <div className="scrub">
        <i style={{ width: at + '%' }}></i>
        {ticks.map((t, i) => <span className="tick" key={i} style={{ left: t + '%' }}></span>)}
      </div>
      {now && <div className="now">{now}</div>}
    </div>
  );
}

function FeAudioCTA({ label = 'Écouter l’épisode' }) {
  return <button className="fe-audio-cta">{FeIco.sound}<span>{label}</span></button>;
}

/* ============================================================
   READ-FIRST STUDY TASK — folded → revealed after the read
   fields: task.{anchor_panel, prompt, options[], answer, correction}
   ============================================================ */
function FeTask({ anchor, folded, revealPrompt, kicker = 'Exercice', title, children }) {
  return (
    <div className={'fe-task' + (folded ? ' folded' : '')}>
      <div className="th"><span className="k">{kicker}</span><span className="anchor">{anchor}</span></div>
      <div className="reveal">
        <span className="t">{revealPrompt || 'Un exercice vous attend — après la lecture.'}</span>
        <span className="go">Réviser {FeIco.arrow}</span>
      </div>
      <div className="tb">
        {title && <div className="q">{title}</div>}
        {children}
      </div>
    </div>
  );
}

/* ============================================================
   CLIFFHANGER + CONTINUATION + FILED
   fields: cliffhanger.{hook, demain}, continuation.{read_next, act_in}
   ============================================================ */
function FeCliff({ kicker = 'À suivre', hook, demain }) {
  return (
    <div className="fe-cliff">
      <div className="k">{kicker}</div>
      <div className="q">{hook}</div>
      {demain && <div className="demain">Demain — <b>{demain}</b></div>}
    </div>
  );
}
function FeContinuation({ readNext = 'Lire le prochain épisode', actIn = 'Agir dans Le Courrier' }) {
  return (
    <div className="fe-cont">
      <a className="beat read" href="#"><span>{readNext}</span>{FeIco.arrow}</a>
      <a className="beat act" href="#"><span>{actIn}</span>{FeIco.arrow}</a>
    </div>
  );
}
function FeFiled({ label = 'Classé · Épisode déposé' }) {
  return <div className="fe-stamp-filed">{label}</div>;
}

/* ============================================================
   C. ARCHIVE — filed plate row
   fields: episodes[].{index_roman, title, date, location, lead_char,
           choice, outcome, thumbnail_url, completed_at, status}
   ============================================================ */
function FeArchivePlate({ roman, title, date, location, char, slug, choice, outcome, state = 'filed' }) {
  const c = FE_CAST[char];
  return (
    <a className={'fe-plate ' + (state === 'current' ? 'current' : state === 'up' ? 'up' : '')} data-char={char} href="#">
      <div className="roman">{roman}</div>
      <div className="thumb">
        {slug && <span className="slug">{slug}</span>}
        <span className="port">{c ? c.ini : '·'}</span>
      </div>
      <div className="info">
        <div className="meta"><span>{date}</span><i></i><span>{location}</span></div>
        <h3>{title}</h3>
        {choice && <div className="choice"><b>Votre réplique</b><em>« {choice} »</em></div>}
        {outcome && <div className="outcome">{outcome}</div>}
      </div>
      <span className="filed">{state === 'current' ? 'En cours' : state === 'up' ? 'À venir' : 'Classé'}</span>
    </a>
  );
}

/* ============================================================
   D. CAST — card · register stamp · closeness · ledger
   fields: member.{name, role, char, relationship:{register, closeness,
           register_switch_episode, callbacks[], last_summary}}
   ============================================================ */
function FeCastCard({ char, name, role, register = 'vous', closeness = 0,
                     switchEp, callbacks = [], last, slug }) {
  const c = FE_CAST[char] || {};
  return (
    <div className="fe-cast-card" data-char={char}>
      <div className="top">
        <div className="port">{c.ini}{slug && <span className="slug">{slug}</span>}</div>
        <div className="id">
          <div className="nm">{name || c.name}</div>
          <div className="role">{role || c.role} · <b>{c.loc}</b></div>
        </div>
        <div className={'fe-reg' + (register === 'vous' ? ' vous' : '')}>
          <span className="r">{register}</span>
          <span className="l">{register === 'tu' ? 'accordé' : 'de rigueur'}</span>
        </div>
      </div>
      <div className="fe-close">
        <span className="cap">Proximité</span>
        <span className="switch">
          {switchEp ? <React.Fragment>Tutoiement — <b>ép. {switchEp}</b></React.Fragment> : 'Pas encore de tutoiement'}
        </span>
        <span className="pips">
          {[0,1,2,3,4].map(i => <i key={i} className={i < closeness ? 'on' : ''}></i>)}
        </span>
      </div>
      <div className="fe-ledger">
        <div className="cap">Rappels</div>
        {callbacks.length ? (
          <div className="cb">{callbacks.map((cb, i) => <span key={i}>{cb}</span>)}</div>
        ) : (
          <div className="none">Aucun rappel encore — l’histoire commence.</div>
        )}
        {last ? <div className="last"><b>Dernier échange —</b> {last}</div>
              : <div className="none">Vous ne vous êtes pas encore parlé.</div>}
      </div>
    </div>
  );
}

/* learner's own serial character */
function FeMeCard({ name = 'Toi', ini = 'T', slug = 'ref: assets/serial/characters/toi/turnaround.png · style_ref locked' }) {
  return (
    <div className="fe-me" data-char="toi">
      <div className="top">
        <div className="port">{ini}</div>
        <div className="id">
          <div className="k">Votre personnage</div>
          <div className="nm">{name}</div>
        </div>
        <button className="customise">Personnaliser</button>
      </div>
      <div className="ref"><div className="slug">{slug}</div></div>
    </div>
  );
}
function FeRegStamp({ register = 'vous' }) {
  return (
    <div className={'fe-reg' + (register === 'vous' ? ' vous' : '')}>
      <span className="r">{register}</span>
      <span className="l">{register === 'tu' ? 'accordé' : 'de rigueur'}</span>
    </div>
  );
}

/* ============================================================
   SKELETON + NOTICE + TABS
   ============================================================ */
function FeSkeleton() {
  return (
    <div className="fe-skel">
      <div className="l" style={{ width: '40%', margin: '0 auto 10px' }}></div>
      <div className="l" style={{ width: '70%', height: 20, margin: '0 auto 12px' }}></div>
      <div className="art"></div>
      <div className="l" style={{ width: '90%' }}></div>
      <div className="l" style={{ width: '80%' }}></div>
      <div className="l" style={{ width: '55%' }}></div>
      <div className="press">— on tire l’édition —</div>
    </div>
  );
}
function FeNotice({ msg = 'La planche n’a pas pu être imprimée. La rédaction a été prévenue.' }) {
  return (
    <div className="fe-notice">
      <div className="nh"><span className="tri"></span><span className="t">Avis de la rédaction</span></div>
      <div className="nb">
        <div className="m">{msg}</div>
        <button className="retry">{FeIco.arrow}<span>Réessayer</span></button>
      </div>
    </div>
  );
}
function FeTabs({ active = 'feuilleton' }) {
  const items = [
    ['home', 'La Une', FeIco.home],
    ['courrier', 'Le Courrier', FeIco.courrier],
    ['feuilleton', 'Feuilleton', FeIco.book],
    ['cast', 'Personnages', FeIco.cast],
  ];
  return (
    <div className="fe-tabs">
      {items.map(([k, l, ic]) => (
        <a key={k} href="#" className={active === k ? 'active' : ''}>{ic}<span>{l}</span></a>
      ))}
    </div>
  );
}

Object.assign(window, {
  FeIco, FE_CAST,
  FeShell, FeChrome, FeMasthead, FePreviously,
  FePanel, FeBubble, FeTranscript, FeRelChip,
  FeAudioBar, FeAudioCTA, FeTask, FeCliff, FeContinuation, FeFiled,
  FeArchivePlate, FeCastCard, FeMeCard, FeRegStamp,
  FeSkeleton, FeNotice, FeTabs,
});
