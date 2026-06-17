/* Atelier — Le Feuilleton · the press-run components.
   AtelierForms (margin companions), the Seal (printer's colophon)
   and the form primitives. One Babel scope; published to window.
   Reuses the editorial chrome + spot-colour discipline from the
   house system — the forms ARE the logo motif, set not drawn. */

/* ---------- the four house forms, as small set shapes ---------- */
function Circle()   { return <svg className="shape" viewBox="0 0 38 38"><circle cx="19" cy="19" r="15" /></svg>; }
function Square()   { return <svg className="shape" viewBox="0 0 38 38"><rect x="6" y="6" width="26" height="26" /></svg>; }
function Triangle() { return <svg className="shape" viewBox="0 0 38 38"><polygon points="19,5 34,32 4,32" /></svg>; }
function Block()    { return <svg className="shape" viewBox="0 0 22 22"><rect x="2" y="2" width="18" height="18" /></svg>; }

/* ============================================================
   ATELIERFORMS — the quiet margin companions
   A column of type-sorts beside the exercise. Reaction is carried
   by motion; a minimal mark (dot-pair eyes + a 1px mouth) appears
   ONLY while reacting, and only on the circle. No persistent face.
   ============================================================ */
function AtelierForms({ react = 'neutral', motion = true, reactKey }) {
  return (
    <div className={'af-rail' + (motion ? ' motion' : '')} data-react={react} key={reactKey}>
      <div className="af circle">
        <Circle />
        <div className="mark" aria-hidden="true">
          <span className="eye l" /><span className="eye r" />
          <svg className="smile" viewBox="-8 -4 16 8"><path d="M-5 -1 Q0 3.4 5 -1" /></svg>
          <svg className="flat" viewBox="-8 -4 16 8"><path d="M-5 1 L5 1" /></svg>
        </div>
      </div>
      <div className="af square"><Square /></div>
      <div className="af triangle"><Triangle /></div>
      <div className="af block"><Block /></div>
    </div>
  );
}

/* static three-state spec board */
function AtelierFormsStates() {
  return (
    <div className="board">
      <div className="board-head">
        <div className="k">AtelierForms · 01</div>
        <h2>The margin companions</h2>
        <p>The three house forms sit in the exercise margin as a column of type-sorts. They react with motion, not character. A minimal mark — a dot-pair and a single-stroke mouth — surfaces on the circle only while it reacts, then withdraws. No names, no faces at rest.</p>
      </div>
      <div className="af-states">
        <div className="col">
          <div className="rail-wrap"><AtelierForms react="neutral" motion={false} /></div>
          <div className="st">Neutral</div>
          <div className="d">Calm. Set, unmarked, at rest in the margin.</div>
        </div>
        <div className="col">
          <div className="rail-wrap"><AtelierForms react="correct" motion={false} /></div>
          <div className="st go">Correct</div>
          <div className="d">A small settle/hop. Eyes + a 1px up-curve mouth appear, then fade.</div>
        </div>
        <div className="col">
          <div className="rail-wrap"><AtelierForms react="wrong" motion={false} /></div>
          <div className="st no">Wrong</div>
          <div className="d">A slight wince-tilt (−7°), faintly faded. The mouth goes flat.</div>
        </div>
      </div>
      <div className="kit-foot">
        <span className="pin">Reduced motion ·</span> the hop and wince are gated behind <b>prefers-reduced-motion</b>. With motion off, the state still changes — the mark appears and the tilt holds — but lands instantly, no animation.
      </div>
    </div>
  );
}

/* interactive "tap to react" demo */
function AtelierFormsDemo() {
  const [react, setReact] = React.useState('neutral');
  const [nonce, setNonce] = React.useState(0);
  const set = (s) => { setReact(s); setNonce((n) => n + 1); };
  return (
    <div className="board">
      <div className="board-head">
        <div className="k">AtelierForms · 02</div>
        <h2>Reactions, live</h2>
        <p>Trigger the states. Each settles back to calm on its own — the companions never hold an expression.</p>
      </div>
      <div className="af-demo">
        <div className="controls">
          <button className={react === 'neutral' ? 'on' : ''} onClick={() => set('neutral')}>Neutral</button>
          <button className={react === 'correct' ? 'on' : ''} onClick={() => set('correct')}>Correct</button>
          <button className={react === 'wrong' ? 'on' : ''} onClick={() => set('wrong')}>Wrong</button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <AtelierForms react={react} reactKey={nonce} />
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   THE FORM CORE — the three (or four) forms locked into an
   emblem. Reused by the Seal and by archive minis. Variants
   rearrange / recolour the lockup so each day's seal differs.
   ============================================================ */
function CoreForms({ variant = 'row' }) {
  const shapes = {
    row: (
      <React.Fragment>
        <circle className="shp c-circle" cx="40" cy="62" r="18" />
        <rect className="shp c-square" x="48" y="44" width="34" height="34" />
        <polygon className="shp c-tri" points="80,44 100,78 60,78" />
      </React.Fragment>
    ),
    stack: (
      <React.Fragment>
        <polygon className="shp c-tri" points="58,14 78,50 38,50" />
        <rect className="shp c-square" x="40" y="46" width="36" height="36" />
        <circle className="shp c-circle" cx="58" cy="88" r="17" />
      </React.Fragment>
    ),
    nested: (
      <React.Fragment>
        <circle className="shp c-circle" cx="58" cy="58" r="36" />
        <polygon className="shp c-tri" points="58,32 82,80 34,80" />
        <rect className="shp c-square" x="49" y="52" width="18" height="18" />
      </React.Fragment>
    ),
    quad: (
      <React.Fragment>
        <rect className="shp c-block" x="30" y="30" width="24" height="24" />
        <circle className="shp c-circle" cx="74" cy="42" r="13" />
        <rect className="shp c-square" x="30" y="62" width="24" height="24" />
        <polygon className="shp c-tri" points="74,62 88,86 60,86" />
      </React.Fragment>
    ),
  };
  return <svg viewBox="0 0 116 116">{shapes[variant] || shapes.row}</svg>;
}

/* the catalogue of daily seals — name + composition + ring lines */
const SEALS = {
  12: { variant: 'row',    date: 'Vendredi 30 mai', name: 'En ligne' },
  11: { variant: 'stack',  date: 'Jeudi 29 mai',    name: 'La colonne' },
  10: { variant: 'nested', date: 'Mercredi 28 mai', name: 'En abyme' },
  9:  { variant: 'quad',   date: 'Mardi 27 mai',    name: 'Le quatuor' },
  8:  { variant: 'row',    date: 'Lundi 26 mai',    name: 'En ligne' },
  7:  { variant: 'nested', date: 'Dimanche 25 mai', name: 'En abyme' },
  6:  { variant: 'stack',  date: 'Samedi 24 mai',   name: 'La colonne' },
  5:  { variant: 'quad',   date: 'Vendredi 23 mai', name: 'Le quatuor' },
  4:  { variant: 'row',    date: 'Jeudi 22 mai',    name: 'En ligne' },
  3:  { variant: 'nested', date: 'Mercredi 21 mai', name: 'En abyme' },
  2:  { variant: 'stack',  date: 'Mardi 20 mai',    name: 'La colonne' },
  1:  { variant: 'quad',   date: 'Lundi 19 mai',    name: 'Le quatuor' },
};

/* ============================================================
   THE SEAL — the printer's-colophon pressmark. The ONE place the
   ink-block shadow belongs. Ring text follows the curve; the
   forms lock into the centre. Variable + collectible by day.
   ============================================================ */
function Seal({ variant = 'row', no = 12, date = 'Vendredi 30 mai', stamp = false, size = 'lg' }) {
  const uid = React.useId().replace(/:/g, '');
  return (
    <div className={'seal ' + size + (stamp ? ' stamp' : '')}>
      <div className="seal-medallion">
        <svg className="ring" viewBox="0 0 200 200" aria-hidden="true">
          <defs>
            <path id={'rt' + uid} d="M 20,100 A 80,80 0 0 1 180,100" />
            <path id={'rb' + uid} d="M 23,100 A 77,77 0 0 0 177,100" />
          </defs>
          <circle cx="100" cy="100" r="66" fill="none" stroke="var(--ink)" strokeWidth="1.5" />
          {/* registration dots where the two text bands meet */}
          <circle cx="13.5" cy="100" r="2.6" fill="var(--ink)" />
          <circle cx="186.5" cy="100" r="2.6" fill="var(--ink)" />
          <text fontSize="11.5" textAnchor="middle">
            <textPath href={'#rt' + uid} startOffset="50%">ATELIER — LE FEUILLETON</textPath>
          </text>
          <text className="fine" textAnchor="middle">
            <textPath href={'#rb' + uid} startOffset="50%">{'Nº ' + no + '  ·  ' + date.toUpperCase()}</textPath>
          </text>
        </svg>
        <div className="core"><CoreForms variant={variant} /></div>
      </div>
    </div>
  );
}

/* compact archive seal — forms in a ring, Nº beneath */
function SealMini({ no, variant = 'row', state = 'earned' }) {
  return (
    <div className={'seal-mini ' + state}>
      <div className="disc">
        {state === 'earned' && <div className="core"><CoreForms variant={variant} /></div>}
      </div>
      <div className="no">{state === 'earned' ? 'Nº ' + no : (state === 'future' ? '—' : '')}</div>
    </div>
  );
}

/* ============================================================
   PER-EXERCISE REACTIVE FORM — neutral / grin / sad
   Each exercise on a screen is bound to ONE form; the form grins
   (flawless) or saddens (a slip). Marks sit per-shape and appear
   only on a verdict (transition-driven, snap-safe).
   ============================================================ */
function ReactForm({ shape = 'circle', state = 'neutral' }) {
  const Shape = shape === 'square' ? Square : shape === 'triangle' ? Triangle : Circle;
  return (
    <div className={'rf ' + shape} data-state={state}>
      <Shape />
      <div className="mk" aria-hidden="true">
        <span className="eye l" /><span className="eye r" />
        <svg className="grin" viewBox="-8 -4 16 8"><path d="M-5 -1 Q0 3.4 5 -1" /></svg>
        <svg className="sad" viewBox="-8 -4 16 8"><path d="M-5 2 Q0 -2.6 5 2" /></svg>
      </div>
    </div>
  );
}

/* ============================================================
   THE LOGO TOKEN — the three forms + the ink block fused into
   the house mark. Minted by a perfect screen; spendable in the
   workshop. CoreLogo is the 2×2 lockup (ink · blue · yellow · red).
   ============================================================ */
function CoreLogo() {
  return (
    <svg viewBox="0 0 62 62" aria-hidden="true">
      <rect className="shp c-block" x="8" y="8" width="18" height="18" />
      <circle className="shp c-circle" cx="45" cy="17" r="9" />
      <rect className="shp c-square" x="8" y="36" width="18" height="18" />
      <polygon className="shp c-tri" points="45,36 56,54 34,54" />
    </svg>
  );
}
function LogoToken({ pop = false, size = '' }) {
  return (
    <div className={'logo-token ' + size + (pop ? ' pop' : '')}>
      <div className="lt"><CoreLogo /></div>
    </div>
  );
}

/* ============================================================
   CONFETTI — restrained press-marks in the house inks. Quick
   scatter; off entirely under reduced motion.
   ============================================================ */
function Confetti({ count = 22 }) {
  const inks = ['var(--blue)', 'var(--yellow)', 'var(--red)', 'var(--ink)'];
  const kinds = ['sq', 'ci', 'tri'];
  const pieces = React.useMemo(() => Array.from({ length: count }, (_, i) => {
    const k = kinds[i % 3];
    const c = inks[i % 4];
    return {
      k, c,
      left: Math.round(6 + Math.random() * 88),
      dur: (0.9 + Math.random() * 0.7).toFixed(2),
      del: (Math.random() * 0.25).toFixed(2),
      r: Math.round(140 + Math.random() * 260) * (i % 2 ? 1 : -1),
    };
  }), [count]);
  return (
    <div className="confetti" aria-hidden="true">
      {pieces.map((p, i) => (
        <i key={i} className={p.k}
          style={{
            left: p.left + '%',
            color: p.c,
            background: p.k === 'tri' ? undefined : p.c,
            '--dur': p.dur + 's', '--del': p.del + 's', '--r': p.r + 'deg',
          }} />
      ))}
    </div>
  );
}

Object.assign(window, {
  Circle, Square, Triangle, Block,
  AtelierForms, AtelierFormsStates, AtelierFormsDemo,
  CoreForms, Seal, SealMini, SEALS,
  ReactForm, CoreLogo, LogoToken, Confetti,
});
