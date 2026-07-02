/* Atelier — Le Feuilleton · the reward surfaces.
   "Edition printed" (the peak moment — the seal struck onto the
   page, the ink-block shadow's one rightful home) and the seal
   collection (a dignified editorial almanac). Delight is
   concentrated HERE, at the end, and made variable + collectible
   — never a fixed "well done", never a panic over a broken streak. */

function RArrow() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M4 12h15M13 6l6 6-6 6" /></svg>;
}

/* ============================================================
   EDITION PRINTED — the session-complete peak
   ============================================================ */
function EditionPrinted({ no = 12, stamp = true, height = 928 }) {
  const s = SEALS[no] || SEALS[12];
  return (
    <div className="printed" style={{ height }}>
      <div className="printed-body">
        <div className="rubric">Edition printed</div>
        <div className="endmark" />
        <h2>Today&apos;s seal is struck.</h2>

        <div className="seal-stage">
          <Seal variant={s.variant} no={no} date={s.date} stamp={stamp} size="lg" />
        </div>

        <div className="printed-meta">
          <div className="row"><span>Edition</span><b>Nº {no} · imprimée</b></div>
          <div className="row"><span>Composition</span><b>« {s.name} »</b></div>
          <div className="row"><span>In your almanac</span><b>11 collected</b></div>
          <div className="row"><span>Earned today</span><b className="red">4 logo tokens</b></div>
        </div>

        <div className="week-strip">
          <div className="wh"><span className="t">This week</span><span className="n">4 / 7 · 3 to a complete week</span></div>
          <div className="cells">
            <div className="cell"><i className="circle" /></div>
            <div className="cell"><i /></div>
            <div className="cell"><i className="circle" /></div>
            <div className="cell today"><i /></div>
            <div className="cell empty"><i /></div>
            <div className="cell empty"><i /></div>
            <div className="cell empty"><i /></div>
          </div>
        </div>

        <a className="teaser" href="#">
          <span className="thumb"><b>scene</b></span>
          <span className="tx">
            <span className="k">Tomorrow · Épisode 5</span>
            <h4>Au comptoir du Mistral</h4>
            <p>Si type 1 walks into a real conversation.</p>
          </span>
          <span className="go"><RArrow /></span>
        </a>
      </div>
    </div>
  );
}

/* ============================================================
   THE SEAL COLLECTION — the editorial almanac
   ============================================================ */
function SealCollection({ height = 1004 }) {
  const archive = [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1];
  return (
    <div className="coll" style={{ height }}>
      <div className="coll-head">
        <div className="k">L&apos;almanach des sceaux</div>
        <h1>Seal collection</h1>
        <div className="meta">
          <b>12</b><span>collected</span><span className="dot" />
          <span>Nº 1 – 12</span><span className="dot" /><span>3 to a complete week</span>
        </div>
      </div>

      <div className="coll-body">
        {/* current week — endowed progress, no panic */}
        <div className="coll-week">
          <div className="wh"><span className="t">This week</span><span className="n">4 / 7 · 3 to go</span></div>
          <div className="row7">
            <SealMini no={9} variant={SEALS[9].variant} state="earned" />
            <SealMini no={10} variant={SEALS[10].variant} state="earned" />
            <SealMini no={11} variant={SEALS[11].variant} state="earned" />
            <SealMini no={12} variant={SEALS[12].variant} state="earned" />
            <SealMini state="future" />
            <SealMini state="future" />
            <SealMini state="future" />
          </div>
        </div>

        {/* the full run */}
        <div className="coll-section">
          <div className="sh"><span className="t">The run so far</span><span className="ln" /><span className="ct">Nº 1 – 12</span></div>
          <div className="coll-grid">
            {archive.map((n) => (
              <SealMini key={n} no={n} variant={SEALS[n].variant} state="earned" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   SPEC BOARD — the four daily seal variants (collectible set)
   ============================================================ */
function SealVariantsBoard() {
  const set = [
    { no: 12, label: 'En ligne · the row' },
    { no: 11, label: 'La colonne · stacked' },
    { no: 10, label: 'En abyme · nested' },
    { no: 9, label: 'Le quatuor · the house mark' },
  ];
  return (
    <div className="board" style={{ width: 560 }}>
      <div className="board-head">
        <div className="k">The reward · collectible seals</div>
        <h2>One run, four compositions</h2>
        <p>The peak reward is a pressmark, struck at the end of a session — the single place the house ink-block shadow is allowed. Each day&apos;s seal sets the same three forms in a different lockup, so the almanac is variable and worth collecting. No two days feel identical; none is a fixed "well done".</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '34px 24px', justifyItems: 'center', padding: '20px 0 6px' }}>
        {set.map((v) => {
          const s = SEALS[v.no];
          return (
            <div key={v.no} style={{ display: 'grid', justifyItems: 'center', gap: 16 }}>
              <Seal variant={s.variant} no={v.no} date={s.date} size="lg" />
              <div style={{ fontSize: 10, fontWeight: 900, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--ink-2)' }}>{v.label}</div>
            </div>
          );
        })}
      </div>
      <div className="kit-foot">
        <span className="pin">Why variable ·</span> a small, unpredictable reward at the finish (variable reinforcement) plus a visible, partly-filled set (endowed progress) is far stickier — and more dignified — than a fixed badge or a streak you can lose.
      </div>
    </div>
  );
}

Object.assign(window, { EditionPrinted, SealCollection, SealVariantsBoard });
