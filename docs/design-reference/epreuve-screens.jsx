/* ============================================================
   L'ÉPREUVE — the session, every state.
   One thread of content (le passé composé · la lettre de Romy)
   runs through the loop so the surface reads as one séance,
   continuous with La Une and Le Feuilleton.
   ============================================================ */

/* the assembling motif for "le passé composé":
   auxiliaire (block) + participe (triangle) + accord (circle) */
function pcMotif(set, printing, done) {
  const M = [
    { shape: 'block', cx: 14, cy: 31, s: 15, role: 'auxiliaire' },
    { shape: 'triangle', cx: 30, cy: 18, s: 19, role: 'participe' },
    { shape: 'circle', cx: 33, cy: 35, s: 13, role: 'accord' },
  ];
  return <EpMotif done={done} prims={M.map((p, i) => ({ ...p, printed: i < set, printing: i === printing }))} />;
}

/* standard mid-session composing stick */
const G_MID = [{ total: 4, set: 4 }, { total: 5, set: 2, current: true }, { total: 4, set: 0 }];
const CAP_MID = ['La séance', 'Ligne 7 / 13'];

/* ============================================================
   STATE 1 — RECOGNIZE / FILL, mid-exercise
   variants: rule closed · rule open · with provenance (resurfaced)
   ============================================================ */
function EpRecognize({ theme = 'light', rule = false, provenance = false }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={G_MID} cap={CAP_MID} />
      <div className="ep-body">
        <div className="ep-sheet">
          <EpEyebrow round="Manche 2" mode="Reconnaître" i={7} n={13} retour={provenance} />
          {provenance && (
            <EpProvenance>Manqué mercredi — <b>lettre à M. Marchand</b>. On le reprend proprement.</EpProvenance>
          )}
          <EpConcept title="Le passé composé" motif={pcMotif(1, null)} askOn={rule} />
          {rule && (
            <EpRule
              lede={<React.Fragment>On forme le passé composé avec l’auxiliaire <b>avoir</b> ou <b>être</b>, suivi du participe passé. Il pose un fait <i>accompli</i>, ponctuel.</React.Fragment>}
              examples={[
                <React.Fragment key="a">Tu <b>as vu</b> l’heure. — <span style={{ color: 'var(--app-ink-3)' }}>fait ponctuel</span></React.Fragment>,
                <React.Fragment key="b">Elle <b>est venue</b> tôt. — <span style={{ color: 'var(--app-ink-3)' }}>auxiliaire être</span></React.Fragment>,
              ]}
            />
          )}
          <EpPrompt label="Complétez la réplique de Romy" cue={<React.Fragment><b>You saw</b> the time on the postmark?</React.Fragment>}>
            « Tu <Blank set>as vu</Blank> l’heure du cachet ? »
          </EpPrompt>
          <EpOpts>
            <EpOpt>as voyais</EpOpt>
            <EpOpt chosen>as vu</EpOpt>
            <EpOpt>avais vu</EpOpt>
          </EpOpts>
        </div>
        <EpFoot>
          <EpBar>Vérifier</EpBar>
        </EpFoot>
      </div>
    </EpShell>
  );
}

/* ============================================================
   STATE 2 — MOVABLE TYPE (word-bank), mid-build
   ============================================================ */
function EpWordBank({ theme = 'light' }) {
  const placed = ['Si', 'tu', 'viens,', 'je'];
  const bank = ['dîner.', 'préparerai', 'le', 'demain'];
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={G_MID} cap={['La séance', 'Ligne 8 / 13']} />
      <div className="ep-body">
        <div className="ep-sheet">
          <EpEyebrow round="Manche 2" mode="Composer" i={8} n={13} />
          <EpConcept title="La condition · si + présent" motif={pcMotif(2, null)} />
          <div className="ep-cue" style={{ marginTop: 13 }}><b>Réglez :</b> “If you come, I’ll make dinner.”</div>
          <EpSetLine>
            {placed.map((w, i) => <EpSlug key={i} set>{w}</EpSlug>)}
          </EpSetLine>
          <EpCase label="La casse · les sortes" count={bank.length}>
            {bank.map((w, i) => <EpSlug key={i}>{w}</EpSlug>)}
          </EpCase>
        </div>
        <EpFoot>
          <EpBar disabled>Vérifier</EpBar>
        </EpFoot>
      </div>
    </EpShell>
  );
}

/* ============================================================
   STATE 3 — TRANSFORM wrong → proofreader's marks → micro-repair
   step: 'marks' | 'repair'
   ============================================================ */
function EpMarks({ theme = 'light', step = 'marks' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={G_MID} cap={['La séance', 'Ligne 9 / 13']} />
      <div className="ep-body">
        <div className="ep-sheet">
          <EpEyebrow round="Manche 2" mode="Transformer" i={9} n={13} />
          <EpConcept title="Le passé composé" motif={pcMotif(2, null)} />
          <EpPrompt label="Mettez au passé composé">
            « Elle <span style={{ color: 'var(--app-ink-3)', fontStyle: 'italic' }}>voit</span> la lettre. »
          </EpPrompt>

          {step === 'marks' && (
            <React.Fragment>
              <EpGalley
                anchor="votre ligne"
                why={<React.Fragment><b>Participe passé de « voir » : vu.</b> Avec l’auxiliaire <i>avoir</i>, on ne conjugue pas le verbe — on pose le participe.</React.Fragment>}
                relecture={<EpRelecture status="done"><b>Relu.</b> Le correcteur confirme la marque.</EpRelecture>}
              >
                Elle a <EpFix old="voyait" fix="vu" /> la lettre.
              </EpGalley>
              <EpFoot style={{ padding: 0 }} />
            </React.Fragment>
          )}

          {step === 'repair' && (
            <React.Fragment>
              <EpGalley anchor="corrigé" why={<React.Fragment><b>Participe passé : vu.</b> Recopiez pour fixer le geste.</React.Fragment>}>
                Elle a <EpFix old="voyait" fix="vu" /> la lettre.
              </EpGalley>
              <EpRepair target="Elle a vu la lettre." typed="Elle a vu la " status="typing" />
            </React.Fragment>
          )}
        </div>
        <EpFoot>
          {step === 'marks'
            ? <React.Fragment><EpVerdict tone="no">Pas encore — la ligne est marquée</EpVerdict><EpBar icon="arrow">Recomposer la ligne</EpBar></React.Fragment>
            : <EpBar icon="arrow" tone="ghost">Continuer</EpBar>}
        </EpFoot>
      </div>
    </EpShell>
  );
}

/* ============================================================
   STATE 4 — CONFIDENCE TAP before Check · CORRECT moment (no modal)
   phase: 'confidence' | 'correct'
   ============================================================ */
function EpCorrectMoment({ theme = 'light', phase = 'confidence' }) {
  const correct = phase === 'correct';
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={correct ? [{ total: 4, set: 4 }, { total: 5, set: 3, current: true }, { total: 4, set: 0 }] : G_MID} cap={CAP_MID} />
      <div className="ep-body">
        <div className="ep-sheet">
          <EpEyebrow round="Manche 2" mode="Reconnaître" i={7} n={13} />
          <EpConcept title="Le passé composé" motif={pcMotif(correct ? 3 : 2, correct ? 2 : null, correct)} />
          <EpPrompt label="Complétez la réplique de Romy" cue={<React.Fragment><b>You saw</b> the time on the postmark?</React.Fragment>}>
            « Tu <Blank set>as vu</Blank> l’heure du cachet ? »
          </EpPrompt>
          <EpOpts>
            <EpOpt>as voyais</EpOpt>
            <EpOpt chosen right={correct}>as vu</EpOpt>
            <EpOpt>avais vu</EpOpt>
          </EpOpts>
          {!correct && <EpConfidence value="sure" />}
          {correct && <EpCorrect struck said={<React.Fragment>Juste. <b>« Tu as vu »</b> — la ligne est posée.</React.Fragment>} />}
        </div>
        <EpFoot>
          {correct
            ? <React.Fragment><EpVerdict tone="go">Ligne réglée · sortie propre</EpVerdict><EpBar icon="arrow">Ligne suivante</EpBar></React.Fragment>
            : <EpBar>Vérifier</EpBar>}
        </EpFoot>
      </div>
    </EpShell>
  );
}

/* ============================================================
   STATE 5 — SPEAK round: écouter / recording / transcribing / marked
   phase: 'listen' | 'recording' | 'transcribing' | 'marked'
   ============================================================ */
function EpSpeak({ theme = 'light', phase = 'listen' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={G_MID} cap={['La séance', 'Ligne 10 / 13']} />
      <div className="ep-body">
        <div className="ep-sheet">
          <EpEyebrow round="Manche 3" mode="Parler" i={10} n={13} />
          <EpConcept title="La liaison · « les_amis »" motif={pcMotif(1, null)} />
          <EpPrompt label="Écoutez, puis répétez" cue={<React.Fragment><b>She kept the letter three years.</b></React.Fragment>}>
            « Elle a gardé la lettre trois ans. »
          </EpPrompt>
          <EpListen fr="Elle a gardé la lettre trois ans." playing={phase === 'listen'} />
          {phase === 'marked' ? (
            <EpGalley
              label="Votre transcription · marquée"
              anchor="au micro"
              why={<React.Fragment><b>La liaison « trois_ans » manque.</b> Le « s » se prononce ici : /trwɑ.zɑ̃/.</React.Fragment>}
            >
              Elle a gardé la lettre <EpFix old="trois ans" fix="trois‿ans" />.
            </EpGalley>
          ) : (
            <EpRecord status={phase === 'listen' ? 'idle' : phase} />
          )}
        </div>
        <EpFoot>
          {phase === 'marked'
            ? <React.Fragment><EpVerdict tone="no">Presque — la liaison est marquée</EpVerdict><EpBar icon="arrow">Réécouter · reprendre</EpBar></React.Fragment>
            : <EpBar disabled={phase !== 'idle'} icon={phase === 'listen' ? null : 'check'}>{phase === 'transcribing' ? 'Transcription…' : phase === 'recording' ? 'Enregistrement…' : 'Vérifier au micro'}</EpBar>}
        </EpFoot>
      </div>
    </EpShell>
  );
}

/* ============================================================
   STATE 6 — AI SECOND LOOK: pending → resolved (in place)
   ============================================================ */
function EpSecondLook({ theme = 'light', status = 'pending' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={G_MID} cap={['La séance', 'Ligne 11 / 13']} />
      <div className="ep-body">
        <div className="ep-sheet">
          <EpEyebrow round="Manche 3" mode="Produire" i={11} n={13} />
          <EpConcept title="Produire · une phrase libre" motif={pcMotif(2, null)} />
          <EpPrompt label="Vous avez écrit">
            « J’ai gardé ta lettre, moi aussi. »
          </EpPrompt>
          <EpGalley
            label={status === 'pending' ? 'Première lecture · juste' : 'Relu · une nuance'}
            anchor="votre ligne"
            why={status === 'done'
              ? <React.Fragment><b>Juste, et bien tourné.</b> « moi aussi » en fin de phrase renforce l’aveu — le correcteur l’a retenu pour l’épreuve.</React.Fragment>
              : null}
            relecture={<EpRelecture status={status}>{status === 'done' ? <React.Fragment><b>Relecture terminée.</b> Aucune faute — une tournure notée.</React.Fragment> : null}</EpRelecture>}
          >
            {status === 'pending'
              ? <React.Fragment>J’ai gardé ta lettre, moi aussi.</React.Fragment>
              : <React.Fragment>J’ai gardé ta lettre, <span style={{ borderBottom: '2px solid var(--ep-bon)' }}>moi aussi</span>.</React.Fragment>}
          </EpGalley>
        </div>
        <EpFoot>
          {status === 'pending'
            ? <React.Fragment><EpVerdict tone="go">Juste · relecture en appui</EpVerdict><EpBar icon="arrow">Ligne suivante</EpBar></React.Fragment>
            : <React.Fragment><EpVerdict tone="go">Retenu pour la phrase du jour</EpVerdict><EpBar icon="arrow">Ligne suivante</EpBar></React.Fragment>}
        </EpFoot>
      </div>
    </EpShell>
  );
}

/* ============================================================
   STATE 7 — EARLY MASTERY LOCK (skip = earned promotion)
   ============================================================ */
function EpEarlyLock({ theme = 'light' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={[{ total: 4, set: 4 }, { total: 5, set: 5 }, { total: 4, set: 0, current: true }]} cap={['La séance', 'Concept 2 · verrouillé']} />
      <div className="ep-body">
        <EpLock motif={pcMotif(3, null, true)} title="Le passé composé — réglé sans une faute." />
      </div>
    </EpShell>
  );
}

/* ============================================================
   STATE 8 — SESSION COMPLETE: BON À TIRER + l'épreuve recap
   phase: 'bat' | 'recap'; gilt, phrase optional
   ============================================================ */
function EpComplete({ theme = 'light', phase = 'recap', gilt = true, phrase = true }) {
  if (phase === 'bat') {
    return (
      <EpShell theme={theme}>
        <div className="ep-body">
          <EpBatStage sub={<React.Fragment>La séance est composée. On tire l’épreuve.</React.Fragment>} />
        </div>
      </EpShell>
    );
  }
  return (
    <EpShell theme={theme}>
      <div className="ep-body ep-recap">
        <EpRecapHead date="Dimanche 8 juin · édition du soir" />
        <div className="ep-recap-body">
          <EpStick
            full
            groups={[{ total: 4, set: 4 }, { total: 5, set: 5 }, { total: 4, set: 4 }]}
            labels={[
              { name: 'Passé composé', state: 'done' },
              { name: 'La condition', state: 'done' },
              { name: 'La liaison', state: 'done' },
            ]}
          />

          <div className="ep-sec-cap">Le compte du jour</div>
          <EpTally items={[
            { n: 13, l: 'Lignes réglées' },
            { n: 3, l: 'Concepts affermis' },
            { n: gilt ? 0 : 2, l: 'Errata classés' },
          ]} />

          {gilt && (
            <React.Fragment>
              <div className="ep-sec-cap">Course sans faute</div>
              <div style={{ display: 'flex', justifyContent: 'center', padding: '6px 0 4px' }}>
                <EpSeal gilt stamp />
              </div>
              <div style={{ textAlign: 'center', fontSize: 10, fontWeight: 900, letterSpacing: '.13em', textTransform: 'uppercase', color: '#8a6d1a', marginTop: 6 }}>
                Sceau doré · édition impeccable
              </div>
            </React.Fragment>
          )}

          <div className="ep-sec-cap">Les lignes déposées</div>
          <EpProof lines={[
            { fr: <React.Fragment>Tu as vu l’heure du cachet ?</React.Fragment>, tag: 'Passé comp.' },
            { fr: <React.Fragment>Si tu viens, je préparerai le dîner.</React.Fragment>, tag: 'Condition' },
            { re: true, fr: <React.Fragment>Elle a <del>voyait</del> <ins>vu</ins> la lettre.</React.Fragment>, tag: 'Corrigé' },
            { fr: <React.Fragment>J’ai gardé ta lettre, moi aussi.</React.Fragment>, tag: 'Produit' },
          ]} />

          {phrase && (
            <React.Fragment>
              <div className="ep-sec-cap">La phrase du jour</div>
              <EpPhrase quote="J’ai gardé ta lettre, moi aussi." by="Composé par vous · manche 3" />
            </React.Fragment>
          )}

          <div className="ep-sec-cap">Frappé aujourd’hui</div>
          <EpMint note={gilt ? 'Trois concepts scellés · sceau doré' : 'Deux concepts scellés au propre'} tokens={gilt ? 3 : 2} />

          <div className="ep-sec-cap">La série</div>
          <EpStreak was={6} now={7} rules={7} on={7} />

          <EpHandoff next="Le Feuilleton · ép. 4" />
          <div style={{ marginTop: 16, textAlign: 'center', fontFamily: 'var(--ep-mono)', fontSize: 8.5, color: 'var(--app-ink-3)', letterSpacing: '.04em' }}>
            recap.attempts · strengthened · errata_logged · minted_collectibles · streak
          </div>
        </div>
      </div>
    </EpShell>
  );
}

/* ============================================================
   STATE 9 — RESUME · LOADING · ERROR
   ============================================================ */
function EpResumeScreen({ theme = 'light' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={[{ total: 4, set: 4 }, { total: 5, set: 0, current: true }, { total: 4, set: 0 }]} cap={['La séance', 'Ligne 5 / 13']} />
      <div className="ep-body">
        <EpResume groups={[{ total: 4, set: 4 }, { total: 5, set: 0, current: true }, { total: 4, set: 0 }]} cap={['Reprise', 'Ligne 5 / 13']} />
      </div>
    </EpShell>
  );
}
function EpLoading({ theme = 'light' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={[{ total: 4, set: 0, current: true }, { total: 5, set: 0 }, { total: 4, set: 0 }]} cap={['La séance', 'On compose…']} />
      <div className="ep-body"><EpSkeleton /></div>
    </EpShell>
  );
}
function EpErrorScreen({ theme = 'light' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={G_MID} cap={CAP_MID} />
      <div className="ep-body">
        <div className="ep-sheet" style={{ paddingBottom: 0 }}>
          <EpEyebrow round="Manche 2" mode="Reconnaître" i={7} n={13} />
          <EpConcept title="Le passé composé" motif={pcMotif(1, null)} />
        </div>
        <EpNotice />
      </div>
    </EpShell>
  );
}

/* ============================================================
   TTS-UNAVAILABLE + CLASSIFY (honest empty / alternate round)
   ============================================================ */
function EpSpeakEmpty({ theme = 'light' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={G_MID} cap={['La séance', 'Ligne 10 / 13']} />
      <div className="ep-body">
        <div className="ep-sheet">
          <EpEyebrow round="Manche 3" mode="Parler" i={10} n={13} />
          <EpConcept title="La liaison · « les_amis »" motif={pcMotif(1, null)} />
          <EpPrompt label="Lisez à voix haute">« Elle a gardé la lettre trois ans. »</EpPrompt>
          <EpListen fr="Elle a gardé la lettre trois ans." disabled />
          <div style={{ marginTop: 10, fontFamily: 'var(--ep-mono)', fontSize: 10, color: 'var(--app-ink-3)', lineHeight: 1.5 }}>
            tts_url = null · le modèle sonore reviendra ; la ligne reste lisible
          </div>
        </div>
        <EpFoot><EpBar>Marquer comme lu</EpBar></EpFoot>
      </div>
    </EpShell>
  );
}
function EpClassify({ theme = 'light' }) {
  return (
    <EpShell theme={theme}>
      <EpTopbar groups={G_MID} cap={['La séance', 'Ligne 6 / 13']} />
      <div className="ep-body">
        <div className="ep-sheet">
          <EpEyebrow round="Manche 1" mode="Classer" i={6} n={13} />
          <EpConcept title="Auxiliaire · avoir ou être ?" motif={pcMotif(1, null)} />
          <div className="ep-cue" style={{ marginTop: 13 }}><b>Rangez</b> chaque participe dans sa casse.</div>
          <EpCases boxes={[
            { label: 'Avec avoir', slugs: ['vu', 'gardé'] },
            { label: 'Avec être', slugs: ['venue'] },
          ]} />
          <EpCase label="À ranger" count={1}>
            <EpSlug>tombée</EpSlug>
          </EpCase>
        </div>
        <EpFoot><EpBar disabled>Vérifier</EpBar></EpFoot>
      </div>
    </EpShell>
  );
}

Object.assign(window, {
  pcMotif, G_MID, CAP_MID,
  EpRecognize, EpWordBank, EpMarks, EpCorrectMoment, EpSpeak,
  EpSecondLook, EpEarlyLock, EpComplete,
  EpResumeScreen, EpLoading, EpErrorScreen, EpSpeakEmpty, EpClassify,
});
