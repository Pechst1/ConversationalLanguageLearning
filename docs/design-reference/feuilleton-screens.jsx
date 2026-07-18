/* ============================================================
   LE FEUILLETON — the four views, all states.
   One episode of narrative content threads every reader state
   so the surfaces read as the same publication.
   ============================================================ */

/* --- Episode 4 content (honest fields the engineer will fill) --- */
const EP4 = {
  index: 4, season: 1,
  title: 'La lettre au fond du tiroir',
  dateline: ['Dimanche 8 juin', 'Le Mistral', 'Marseille'],
  lead: 'romy',
};

/* word-level gloss helper: tap-to-gloss underline */
function G({ children, gloss }) {
  return <span className="gloss-word" title={gloss}>{children}</span>;
}

/* ============================================================
   A / D — THE READER  (variation A: classic centrefold)
   state: 'mid' | 'audio' | 'done' | 'generating' | 'delayed' | 'permalink'
   ============================================================ */
function FeReaderA({ theme = 'light', state = 'mid' }) {
  const filed = state === 'done';
  const permalink = state === 'permalink';
  return (
    <FeShell theme={theme} char="romy">
      {!permalink && <FeChrome dest="La Une" en={false} />}
      {permalink && <FeChrome dest="La saison reliée" en={false} />}
      <div className={'fe-body fe-scroll' + (filed ? ' fe-filed' : '')}>
        <FeMasthead season={EP4.season} index={EP4.index} title={EP4.title}
          dateline={EP4.dateline} progress={permalink ? 100 : state === 'done' ? 100 : 46} progressRed={state === 'done'} />

        {/* relationship cue — present while reading */}
        {!permalink && (
          <div style={{ display: 'flex', justifyContent: 'center', margin: '13px 0 0' }}>
            <FeRelChip char="romy" register="tu" closeness={3} />
          </div>
        )}
        {permalink && (
          <div style={{ display: 'flex', justifyContent: 'center', margin: '13px 0 0' }}>
            <div style={{ fontFamily: 'var(--fe-mono)', fontSize: 9, color: 'var(--app-ink-3)', letterSpacing: '.06em' }}>
              permalink · /serial/episode/4 · lecture seule
            </div>
          </div>
        )}

        {/* Previously — the consequence of the learner's French */}
        {!permalink && (
          <FePreviously epRef="Épisode 3">
            Hier, vous avez proposé le <u>tutoiement</u> à Romy — elle a accepté. Ce matin, elle vous attend au comptoir.
          </FePreviously>
        )}

        {/* pinned audio bar (variation A places audio right under the fold) */}
        {!permalink && (
          <FeAudioBar
            playing={state === 'audio'}
            at={state === 'audio' ? 34 : 0}
            ticks={[0, 22, 44, 62, 80]}
            time={state === 'audio' ? '1:26 / 4:12' : '4:12'}
            now={state === 'audio' ? <React.Fragment><b>Planche 2</b> — « Tu as vu l’heure du cachet ? Minuit passé. »</React.Fragment> : null}
          />
        )}

        {/* Panel 1 — establishing, narration box */}
        <FePanel
          slug="art: romy_leveque + le_mistral · rain-on-glass, zinc counter, morning"
          direction="INT. LE MISTRAL — MATIN. Romy pousse une enveloppe jaunie sur le zinc."
          ratio="wide"
          capNum="I."
          credit="Planche · atelier du Feuilleton"
          play={state === 'audio' ? 'playing' : 'idle'}
          colorable={filed || permalink}
          narration={[{ at: { left: 12, top: 12 }, t: <React.Fragment>Le café n’était pas encore ouvert. La pluie, si.</React.Fragment> }]}
          caption={<React.Fragment>Romy avait gardé la lettre trois ans. Elle la posa comme on rend une dette.</React.Fragment>}
        />

        {/* Panel 2 — speech bubbles over art */}
        <FePanel
          slug="art: romy close · guarded→warm, the envelope between you"
          direction="Elle glisse l’enveloppe vers vous, sans lâcher le coin."
          ratio="tall"
          capNum="II."
          credit="Planche · atelier du Feuilleton"
          play={state === 'audio' ? 'playing' : 'idle'}
          colorable={filed || permalink}
          bubbles={[
            { char: 'romy', who: 'Romy', fr: <React.Fragment>Tu as vu l’heure du <G gloss="postmark">cachet</G> ? Minuit passé.</React.Fragment>, at: { left: 14, top: 16 }, tail: 'bl' },
            { char: 'toi', who: 'Toi', fr: <React.Fragment>Quelqu’un a écrit ça en cachette.</React.Fragment>, at: { right: 12, bottom: 30 }, tail: 'br' },
          ]}
          caption={<React.Fragment>Le tampon disait minuit ; l’écriture, l’urgence.</React.Fragment>}
        />

        {/* read-first study task — folded on mid, revealed after the read */}
        {!permalink && (
          <FeTask
            anchor="↳ ancré à la planche II"
            folded={state === 'mid' || state === 'audio'}
            revealPrompt="Un exercice vous attend — quand vous aurez lu."
            title={<React.Fragment>Complétez la réplique de Romy : « Tu <span className="cloze">as vu</span> l’heure du cachet&nbsp;? »</React.Fragment>}
          >
            <div className="fe-task-opts opts">
              <button className="opt">as voyais</button>
              <button className="opt chosen">as vu</button>
              <button className="opt">avais vu</button>
            </div>
            <div className="fe-correction">
              <div className="cap">Correction — en douceur</div>
              <div className="body">Passé composé : <ins>as vu</ins>, pas <del>as voyais</del>. Un fait ponctuel, déjà accompli.</div>
            </div>
          </FeTask>
        )}

        {/* transcript fallback always available */}
        {!permalink && (
          <div style={{ margin: '4px 18px 0' }}>
            <div style={{ fontSize: 8.5, fontWeight: 900, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--app-ink-3)' }}>Transcription</div>
            <FeTranscript char="romy" lines={[
              { who: 'Romy', fr: 'Tu as vu l’heure du cachet ? Minuit passé.' },
              { who: 'Toi', fr: 'Quelqu’un a écrit ça en cachette.' },
            ]} />
          </div>
        )}

        {/* completion / cliffhanger / filed */}
        {(filed || permalink) && (
          <React.Fragment>
            <FeCliff
              hook="Et si la lettre lui était adressée, à elle ?"
              demain={permalink ? null : 'Romy ouvre le tiroir'}
            />
            {!permalink && (
              <React.Fragment>
                <div style={{ display: 'flex', justifyContent: 'center', margin: '16px 0 0' }}>
                  <FeFiled label="Classé · Épisode 4 déposé" />
                </div>
                <FeContinuation readNext="Lire l’épisode 5" actIn="Aller agir dans Le Courrier" />
              </React.Fragment>
            )}
          </React.Fragment>
        )}

        {!filed && !permalink && (
          <div style={{ margin: '18px 18px 6px', textAlign: 'center', fontFamily: 'var(--app-serif)', fontStyle: 'italic', fontSize: 14, color: 'var(--app-ink-3)' }}>
            … la suite plus bas.
          </div>
        )}
      </div>
      <FeTabs active={permalink ? 'feuilleton' : 'feuilleton'} />
    </FeShell>
  );
}

/* ============================================================
   THE READER — art status states (generating / delayed)
   ============================================================ */
function FeReaderStatus({ theme = 'light', status = 'generating' }) {
  return (
    <FeShell theme={theme} char="romy">
      <FeChrome dest="La Une" />
      <div className="fe-body fe-scroll">
        <FeMasthead season={1} index={4} title={EP4.title} dateline={EP4.dateline} progress={20} />
        <FePreviously epRef="Épisode 3">
          Hier, vous avez proposé le <u>tutoiement</u> à Romy — elle a accepté.
        </FePreviously>
        <FePanel
          ratio="wide"
          status={status}
          statusNote={status === 'generating'
            ? 'On tire la planche I…'
            : 'La presse a du retard sur cette planche. Le texte mène ; l’image suit sous peu.'}
          capNum="I."
          caption={status === 'delayed'
            ? <React.Fragment>Romy posa la lettre sur le zinc, comme on rend une dette. <em style={{ color: 'var(--app-ink-3)' }}>(image à suivre)</em></React.Fragment>
            : <React.Fragment>Romy posa la lettre sur le zinc, comme on rend une dette.</React.Fragment>}
        />
        {status === 'delayed' && (
          <div style={{ margin: '4px 18px 0' }}>
            <FeTranscript char="romy" lines={[
              { who: 'Romy', fr: 'Tu as vu l’heure du cachet ? Minuit passé.' },
              { who: 'Toi', fr: 'Quelqu’un a écrit ça en cachette.' },
            ]} />
          </div>
        )}
        <div style={{ margin: '14px 18px 0', fontFamily: 'var(--fe-mono)', fontSize: 9, color: 'var(--app-ink-3)', lineHeight: 1.5 }}>
          scene.status = "{status}" · le récit ne s’interrompt jamais pour l’image
        </div>
      </div>
      <FeTabs active="feuilleton" />
    </FeShell>
  );
}

/* ============================================================
   THE READER — variation B: "L'édition sonore" (audio-first)
   ============================================================ */
function FeReaderB({ theme = 'light' }) {
  return (
    <FeShell theme={theme} char="romy">
      <FeChrome dest="La Une" />
      <div className="fe-body fe-scroll">
        <FeMasthead season={1} index={4} title={EP4.title} dateline={EP4.dateline} progress={0} />
        <div style={{ textAlign: 'center', margin: '11px 18px 0', fontFamily: 'var(--app-serif)', fontStyle: 'italic', fontSize: 13, color: 'var(--app-ink-3)' }}>
          Une édition à écouter d’abord — les planches suivent la voix.
        </div>
        <FeAudioCTA label="Écouter l’épisode · 4:12" />
        <div style={{ display: 'flex', justifyContent: 'center', margin: '2px 0 0' }}>
          <FeRelChip char="romy" register="tu" closeness={3} />
        </div>
        <FePreviously epRef="Épisode 3">
          Hier, vous avez proposé le <u>tutoiement</u> — Romy a accepté.
        </FePreviously>
        {/* transcript leads; art is a quiet companion */}
        <div style={{ margin: '14px 18px 0' }}>
          <div style={{ fontSize: 8.5, fontWeight: 900, letterSpacing: '.14em', textTransform: 'uppercase', color: 'var(--app-ink-3)', marginBottom: 6 }}>Planche I · transcription</div>
          <FeTranscript char="romy" lines={[
            { who: 'Décor', fr: 'Le café n’était pas encore ouvert. La pluie, si.' },
            { who: 'Romy', fr: 'Tu as vu l’heure du cachet ? Minuit passé.' },
            { who: 'Toi', fr: 'Quelqu’un a écrit ça en cachette.' },
          ]} />
        </div>
        <FePanel
          slug="art: romy + le_mistral · companion plate, muted"
          ratio="wide"
          capNum="I."
          credit="Planche · atelier du Feuilleton"
          play="idle"
          caption={<React.Fragment>Romy posa la lettre comme on rend une dette.</React.Fragment>}
        />
        <div style={{ margin: '10px 18px 0', fontFamily: 'var(--fe-mono)', fontSize: 9, color: 'var(--app-ink-3)', lineHeight: 1.5 }}>
          AUDIO_ONLY_MODE — voix mène, image en appui, exercice après l’écoute
        </div>
      </div>
      <FeTabs active="feuilleton" />
    </FeShell>
  );
}

/* ============================================================
   THE READER — empty / first-run (no thread yet)
   ============================================================ */
function FeReaderEmpty({ theme = 'light' }) {
  return (
    <FeShell theme={theme} char="romy">
      <FeChrome dest="La Une" />
      <div className="fe-body">
        <div className="fe-firstrun">
          <div className="k">Le Feuilleton · Saison 1</div>
          <h2>Le premier numéro n’est pas encore paru.</h2>
          <p>Chaque jour, une planche illustrée. Votre français fait avancer l’histoire — et les gens que vous y rencontrez s’en souviennent.</p>
          <a className="cta" href="#">{FeIco.arrow}<span>Ouvrir l’épisode 1</span></a>
          <div style={{ marginTop: 26, fontFamily: 'var(--fe-mono)', fontSize: 9, color: 'var(--app-ink-3)', lineHeight: 1.6 }}>
            episodes = [] · scene = null<br />premier épisode généré à l’ouverture
          </div>
        </div>
      </div>
      <FeTabs active="feuilleton" />
    </FeShell>
  );
}

/* ============================================================
   THE READER — loading skeleton + error notice
   ============================================================ */
function FeReaderLoading({ theme = 'light' }) {
  return (
    <FeShell theme={theme} char="romy">
      <FeChrome dest="La Une" />
      <div className="fe-body"><FeSkeleton /></div>
      <FeTabs active="feuilleton" />
    </FeShell>
  );
}
function FeReaderError({ theme = 'light' }) {
  return (
    <FeShell theme={theme} char="romy">
      <FeChrome dest="La Une" />
      <div className="fe-body">
        <FeMasthead season={1} index={4} title={EP4.title} dateline={EP4.dateline} progress={0} />
        <FeNotice msg="La planche n’a pas pu être imprimée. Le récit reste lisible ; la rédaction réessaie l’image." />
      </div>
      <FeTabs active="feuilleton" />
    </FeShell>
  );
}

/* ============================================================
   C. THE ARCHIVE — "La saison reliée"
   ============================================================ */
const ARCHIVE = [
  { roman: 'IV', title: 'La lettre au fond du tiroir', date: '8 juin', location: 'Le Mistral', char: 'romy', slug: 'romy+mistral', state: 'current',
    choice: 'On se tutoie, alors ?', outcome: 'Romy a accepté — le vouvoiement est tombé.' },
  { roman: 'III', title: 'Le quai à marée basse', date: '7 juin', location: 'Le Vieux-Port', char: 'marin', slug: 'marin+port',
    choice: 'Je peux monter à bord ?', outcome: 'Marin vous a laissé barrer — il vous fait confiance.' },
  { roman: 'II', title: 'La marge et le crayon', date: '6 juin', location: 'La Marge', char: 'lila', slug: 'lila+libr',
    choice: 'Vous auriez ce titre d’occasion ?', outcome: 'Lila a mis un livre de côté à votre nom.' },
  { roman: 'I', title: 'Un café qu’on n’a pas commandé', date: '5 juin', location: 'Le Mistral', char: 'gus', slug: 'gus+bar',
    choice: 'Bonjour — un serré, s’il vous plaît.', outcome: 'Gus a retenu votre commande. Vous êtes un habitué.' },
];
function FeArchive({ theme = 'light', variant = 'full' }) {
  return (
    <FeShell theme={theme}>
      <FeChrome dest="La Une" />
      <div className="fe-body fe-scroll">
        <div className="fe-arc-head">
          <div className="kicker">Le Feuilleton · Saison 1</div>
          <h2>La saison reliée</h2>
          <div className="sub">{variant === 'full' ? 'Quatre planches déposées · votre exemplaire' : 'Le premier cahier · à peine relié'}</div>
        </div>

        <div className="fe-season-line">
          <div className="cap"><span>Progression de la saison</span><span>{variant === 'full' ? '4 / 12' : '1 / 12'}</span></div>
          <div className="bar"><i style={{ width: variant === 'full' ? '33%' : '8%' }}></i></div>
        </div>

        <div className="fe-season" data-char="">
          {(variant === 'full' ? ARCHIVE : ARCHIVE.slice(3)).map((e, i) => (
            <FeArchivePlate key={i} {...e} />
          ))}
          {variant === 'full'
            ? <FeArchivePlate roman="V" title="Le tiroir de Romy" date="demain" location="Le Mistral" char="romy" state="up" />
            : (
              <div className="fe-arc-empty">
                <div className="mark"></div>
                <h3>La reliure commence.</h3>
                <p>Un épisode par jour vient s’ajouter au cahier. Revenez demain pour la planche II.</p>
              </div>
            )}
        </div>

        <a className="fe-cast-entry" href="#">
          <div className="l"><div className="k">Les personnages</div><div className="t">Voir qui vous connaissez</div></div>
          <div className="faces">
            <i data-char="romy" style={{ background: 'var(--char-romy)' }}>R</i>
            <i data-char="marin" style={{ background: 'var(--char-marin)' }}>M</i>
            <i data-char="lila" style={{ background: 'var(--char-lila)' }}>L</i>
            <i data-char="gus" style={{ background: 'var(--char-gus)' }}>G</i>
          </div>
        </a>
      </div>
      <FeTabs active="feuilleton" />
    </FeShell>
  );
}

/* ============================================================
   D. THE CAST — "Les personnages"
   ============================================================ */
function FeCast({ theme = 'light', variant = 'populated' }) {
  const pop = variant === 'populated';
  return (
    <FeShell theme={theme}>
      <FeChrome dest="La saison reliée" />
      <div className="fe-body fe-scroll">
        <div className="fe-cast-head">
          <div className="kicker">Le Feuilleton</div>
          <h2>Les personnages</h2>
          <div className="sub">Le registre du théâtre — qui vous tutoie, qui se souvient.</div>
        </div>

        <FeMeCard name="Toi" ini="T" />

        {pop ? (
          <React.Fragment>
            <FeCastCard char="romy" register="tu" closeness={3} switchEp={4}
              slug="romy_ref"
              callbacks={['la lettre de minuit', 'le tutoiement', 'son frère au journal']}
              last="« Passe demain — je te montrerai le tiroir. » (planche II)" />
            <FeCastCard char="marin" register="tu" closeness={2} switchEp={3}
              callbacks={['barrer le voilier', 'la marée de 6 h']}
              last="« Tu tiens la barre mieux qu’hier. » (épisode 3)" />
            <FeCastCard char="lila" register="vous" closeness={2}
              callbacks={['le livre mis de côté']}
              last="« Je vous l’ai gardé sous le comptoir. » (épisode 2)" />
            <FeCastCard char="gus" register="vous" closeness={1}
              callbacks={['le café serré']}
              last="« Comme d’habitude ? » (épisode 1)" />
          </React.Fragment>
        ) : (
          <React.Fragment>
            <FeCastCard char="gus" register="vous" closeness={1}
              callbacks={['le café serré']}
              last="« Bienvenue au Mistral. » (épisode 1)" />
            <FeCastCard char="romy" register="vous" closeness={0}
              callbacks={[]} last={null} />
            <div style={{ margin: '14px 18px', padding: '18px 16px', border: '1px dashed var(--app-ink-3)', textAlign: 'center' }}>
              <div style={{ fontFamily: 'var(--app-serif)', fontStyle: 'italic', fontSize: 15, color: 'var(--app-ink-2)', lineHeight: 1.4 }}>
                Tout le monde vous vouvoie encore.
              </div>
              <div style={{ marginTop: 7, fontSize: 11, color: 'var(--app-ink-3)', lineHeight: 1.45 }}>
                Le tutoiement s’accorde — il ne se prend pas. Continuez la saison pour l’obtenir.
              </div>
            </div>
          </React.Fragment>
        )}
      </div>
      <FeTabs active="cast" />
    </FeShell>
  );
}

Object.assign(window, {
  EP4, G,
  FeReaderA, FeReaderStatus, FeReaderB, FeReaderEmpty, FeReaderLoading, FeReaderError,
  FeArchive, FeCast,
});
