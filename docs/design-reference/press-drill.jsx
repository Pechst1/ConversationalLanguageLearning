/* Atelier — Le Feuilleton · the drill "do" screen.
   A single focused word-bank exercise: build the sentence from
   scrambled sorts. Slim PRESS RUN bar, the companions reacting
   in the margin, one red Check. The correct micro-reward is
   small and fast — chips ink in, forms hop — because the big
   reward is saved for the printed seal at the end. */

/* ---------- local icons ---------- */
function IcClose() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square"><path d="M5 5l14 14M19 5L5 19" /></svg>;
}
function IcQ() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 9a3 3 0 1 1 4 2.8c-1 .5-1.5 1-1.5 2.2" /><circle cx="11.5" cy="18" r="1.1" fill="currentColor" stroke="none" /></svg>;
}
function IcArrow() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M4 12h15M13 6l6 6-6 6" /></svg>;
}
function IcCheck() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="square"><path d="M4 12.5l5 5 11-12" /></svg>;
}

const D_ANSWER = ['Si', 'tu', 'viens,', 'je', 'préparerai', 'le', 'dîner.'];
const D_SCRAMBLE = [4, 1, 6, 0, 3, 5, 2]; // bank display order (ids into D_ANSWER)

function DrillScreen({ initialPlaced = [], initialStatus = 'composing', height = 728, motionPref = true }) {
  const [placed, setPlaced] = React.useState(initialPlaced);
  const [status, setStatus] = React.useState(initialStatus); // composing | correct | wrong
  const [nonce, setNonce] = React.useState(0);
  const bump = () => setNonce((n) => n + 1);

  const inBank = D_SCRAMBLE.filter((id) => !placed.includes(id));
  const full = placed.length === D_ANSWER.length;
  const react = status === 'correct' ? 'correct' : status === 'wrong' ? 'wrong' : 'neutral';

  const addWord = (id) => { if (status === 'correct') return; setStatus('composing'); setPlaced((p) => [...p, id]); };
  const removeWord = (id) => { if (status !== 'composing') return; setPlaced((p) => p.filter((x) => x !== id)); };

  const check = () => {
    const ok = placed.length === D_ANSWER.length && placed.every((id, i) => id === i);
    setStatus(ok ? 'correct' : 'wrong');
    bump();
  };
  const retry = () => { setStatus('composing'); bump(); };
  const replay = () => { setPlaced([]); setStatus('composing'); bump(); };

  return (
    <div className="drill" style={{ height }}>
      {/* slim top bar */}
      <div className="drill-bar">
        <button className="icbtn" title="Close" onClick={replay}><IcClose /></button>
        <div className="prog">
          <div className="lab"><span className="l">Press run</span><span className="r">Sheet 5 / 6</span></div>
          <div className="prog-track near">
            <span className="seg done" /><span className="seg done" /><span className="seg done" />
            <span className="seg done" /><span className="seg cur" /><span className="seg" />
          </div>
        </div>
        <button className="icbtn" title="Show the rule"><IcQ /></button>
      </div>

      {/* body: companion margin + exercise */}
      <div className="drill-body">
        <div className="drill-margin">
          <AtelierForms react={react} reactKey={nonce} motion={motionPref} />
        </div>
        <div className="drill-main">
          <div className="drill-q">
            <div className="kicker">Compose · Si type 1</div>
            <div className="cue">If you come, <span className="src">I&apos;ll make dinner.</span></div>
          </div>

          <div className={'tray' + (placed.length === 0 ? ' empty' : '') + (status === 'wrong' ? ' nudge' : '')}>
            {placed.map((id, i) => (
              <span key={id} className={'chip placed' + (status === 'correct' ? ' inked' : '')}
                style={status === 'correct' ? { transitionDelay: i * 0.05 + 's' } : null}
                onClick={() => removeWord(id)}>
                {D_ANSWER[id]}
              </span>
            ))}
          </div>

          <div className="bank">
            <div className="bank-cap">The sorts · {inBank.length} left</div>
            {D_SCRAMBLE.map((id) => (
              <span key={id} className={'chip' + (placed.includes(id) ? ' spent' : '')}
                onClick={() => addWord(id)}>
                {D_ANSWER[id]}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* one dominant action */}
      <div className="drill-foot">
        {status === 'correct' && (
          <React.Fragment>
            <div className="drill-verdict go"><span>— Juste · the line is set —</span><span className="ln" /></div>
            <button className="btn-continue">Continue · Sheet 6 <IcArrow /></button>
          </React.Fragment>
        )}
        {status === 'wrong' && (
          <React.Fragment>
            <div className="drill-verdict no"><span>— Not yet · re-set a sort —</span><span className="ln" /></div>
            <button className="btn-check again" onClick={retry}>Try again</button>
          </React.Fragment>
        )}
        {status === 'composing' && (
          <button className="btn-check" disabled={!full} onClick={check}>Check <IcCheck /></button>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { DrillScreen });
