/* Atelier — Le Feuilleton · stats, collectibles & the workshop.
   The session summary frames momentum kindly (no panic, no
   comparison shaming). Collectibles are bound to EARNED behaviour;
   tokens accumulate and are spent in the workshop to construct new
   collectibles. Reinforcement is variable but never a slot machine. */

function SArrowR() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M4 12h15M13 6l6 6-6 6" /></svg>;
}

/* ============================================================
   SESSION SUMMARY — the day's tally + forward-looking projections
   ============================================================ */
function SessionSummary({ height = 648 }) {
  return (
    <div className="summary" style={{ height }}>
      <div className="summary-body">
        <div className="rubric">Session summary</div>
        <h2>A strong run.</h2>
        <div className="sub">Six screens set, eighteen lines composed. Here&apos;s what today earned — and where it points.</div>

        <div className="tally">
          <div className="t"><div className="n">4</div><div className="l">Logo tokens<br />minted</div></div>
          <div className="t"><div className="n">4/6</div><div className="l">Perfect<br />screens</div></div>
          <div className="t"><div className="n">94%</div><div className="l">Accuracy<br />today</div></div>
        </div>

        <div className="tok-earned">
          <div className="chips">
            <LogoToken size="sm" /><LogoToken size="sm" /><LogoToken size="sm" /><LogoToken size="sm" />
          </div>
          <div className="tx"><b>4 logo tokens</b><span>From your four perfect screens</span></div>
          <div className="to">→ workshop</div>
        </div>

        <div className="proj">
          <div className="ph">Where this is heading</div>
          <div className="p">
            <div className="pt"><b>Si + conditional</b> — on track to master <span className="hi">faster than 80%</span> of readers.</div>
            <div className="bar"><i style={{ width: '72%' }} /><span className="you" style={{ left: '72%' }} /></div>
            <div className="pm">72% set · the marker is you, the bar is the cohort median pace</div>
          </div>
          <div className="p">
            <div className="pt">At this pace, <b>A1.2</b> is achievable in <span className="hi">≈ 20 days</span>.</div>
            <div className="pm">Projected from your last 14 sessions · adjusts as you go</div>
          </div>
          <div className="p">
            <div className="pt">You set today&apos;s lines <span className="hi">faster than 90%</span> of readers.</div>
            <div className="pm">Median time-to-set across the six screens</div>
          </div>
        </div>

        <button className="seal-cta">Strike today&apos;s seal <SArrowR /></button>
        <div className="foot-note">Projections are momentum, not promises. Nothing here expires, and a missed day costs you nothing.</div>
      </div>
    </div>
  );
}

/* ============================================================
   COLLECTIBLES — what each is bound to (earned, never bought)
   ============================================================ */
function CollectiblesBoard() {
  return (
    <div className="board" style={{ width: 540 }}>
      <div className="board-head">
        <div className="k">The token economy · bindings</div>
        <h2>Bound to behaviour</h2>
        <p>Every collectible is minted by something you <i>did</i> — a flawless screen, a perfect session, a fast run, a story beat. None can be bought, none expires, and missing a day takes nothing away. Variable reinforcement, kept dignified.</p>
      </div>

      <div className="bind-row">
        <div className="art"><LogoToken /></div>
        <div>
          <div className="bt">Logo token <span className="req">· perfect screen (3/3 flawless)</span></div>
          <p>The three forms grin and fuse into the house mark. Confetti + a haptic tick at the moment of the lock. The day&apos;s most repeatable token — good days mint several.</p>
        </div>
      </div>

      <div className="bind-row">
        <div className="art"><div className="gilt"><SealMini no={12} variant="quad" state="earned" /></div></div>
        <div>
          <div className="bt">Gilt seal <span className="req">· a flawless round (whole session, no slip)</span></div>
          <p>The day&apos;s seal struck in gold instead of ink. Rare by design — it marks a session you got end-to-end clean, not just a streak you kept alive.</p>
        </div>
      </div>

      <div className="bind-row">
        <div className="art"><div className="scene-thumb"><b>épisode 4 · panel</b></div></div>
        <div>
          <div className="bt">Story seal <span className="req">· a Feuilleton beat</span></div>
          <p>Earned by reaching a turn in the serial. Its face is a <b>cropped panel from that episode&apos;s illustration</b> — so the almanac doubles as a memory of the story, not just a scorecard.</p>
          <div className="eng">ENG NOTE — story-seal art = a designated crop region per episode illustration; ship a 1:1 mask + focal point with each scene asset. Mint on beat-complete, not on exercise-complete.</div>
        </div>
      </div>

      <div className="kit-foot">
        <span className="pin">Deliberately absent ·</span> no lives, no gems, no purchasable tokens, no streak you can lose, no countdown. The only currency is skill, and the only pressure is curiosity.
      </div>
    </div>
  );
}

/* ============================================================
   THE WORKSHOP — tokens are spent to construct new collectibles
   ============================================================ */
function WorkshopBoard() {
  return (
    <div className="board" style={{ width: 520 }}>
      <div className="board-head">
        <div className="k">The workshop · l&apos;atelier</div>
        <h2>Tokens become collectibles</h2>
        <p>What you mint by playing can be set into something larger. The workshop is where a week of tokens is composed into a bound plate — endowed progress you can see filling.</p>
      </div>

      <div className="workshop-inv">
        <span className="n">11</span>
        <div className="l">logo tokens<br /><b>in the case</b></div>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <LogoToken size="sm" /><LogoToken size="sm" /><LogoToken size="sm" /><LogoToken size="sm" />
        </span>
      </div>

      <div className="recipe">
        <div className="in"><span className="cost"><LogoToken size="sm" /><span className="x">× 7</span></span><span className="lbl">logo tokens</span></div>
        <div className="arrow-mid"><SArrowR /></div>
        <div className="out"><span className="reward-name">« Semaine » gilt plate</span></div>
      </div>
      <div className="recipe">
        <div className="in"><span className="cost"><div className="scene-thumb" style={{ width: 30, height: 24 }} /><span className="x">× 3</span></span><span className="lbl">story seals</span></div>
        <div className="arrow-mid"><SArrowR /></div>
        <div className="out"><span className="reward-name">A bound chapter plate</span></div>
      </div>
      <div className="recipe">
        <div className="in"><span className="cost"><div className="gilt-disc" style={{ width: 26, height: 26, border: '1.5px solid var(--ink)', borderRadius: '50%' }} /><span className="x">× 4</span></span><span className="lbl">gilt seals</span></div>
        <div className="arrow-mid"><SArrowR /></div>
        <div className="out"><span className="reward-name">The annual colophon</span></div>
      </div>

      <div className="kit-foot">
        <span className="pin">Why a workshop ·</span> spending is optional and additive — you never <b>lose</b> a token, you <b>compose</b> with it. The construction step is the second, slower reward loop beneath the daily seal.
      </div>
    </div>
  );
}

Object.assign(window, { SessionSummary, CollectiblesBoard, WorkshopBoard });
