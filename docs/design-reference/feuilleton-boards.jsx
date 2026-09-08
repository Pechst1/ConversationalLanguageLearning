/* ============================================================
   LE FEUILLETON — handoff boards
   Component spec · French copy deck · migration note · tokens
   ============================================================ */

/* ---- 1. COMPONENT SPEC — the shared "supplement" primitives --- */
function FeSpecBoard() {
  const rows = [
    {
      demo: <FeMasthead season={1} index={4} title="La lettre au fond du tiroir" dateline={['Dim. 8 juin', 'Le Mistral']} progress={46} />,
      t: 'Dateline masthead',
      p: 'Folio (section · saison · épisode), serif-italic title, dateline, and the thin reading-progress rule. La Une’s double-rule folio, reused.',
      props: ['season', 'index', 'title', 'dateline[]', 'progress 0–100', 'progressRed'],
    },
    {
      demo: <div style={{ width: 200 }}><FePanel slug="art: romy + le_mistral" ratio="wide" capNum="I." credit="atelier" caption="Romy posa la lettre comme on rend une dette." bubbles={[{ char: 'romy', who: 'Romy', fr: 'Minuit passé.', at: { left: 10, top: 14 }, tail: 'bl' }]} /></div>,
      t: 'Panel frame + on-art bubble + caption + credit',
      p: 'Frame sits on arbitrary raster art. Speech = bubble w/ ink outline, scrim shadow + tail; narration = hairline box, no tail. Caption is the editorial standfirst below; credit is a hairline strip.',
      props: ['image_url→slug', 'direction', 'bubbles[]{who,char,fr,en,at,tail}', 'narration[]', 'caption', 'credit', 'play'],
    },
    {
      demo: <FeRelChip char="romy" register="tu" closeness={3} />,
      t: 'Relationship chip',
      p: 'Register earned (tu/vous) + closeness 0–5, in the character’s accent. Present while reading & acting so the bond is felt.',
      props: ['char', 'register', 'closeness'],
    },
    {
      demo: <div style={{ width: 210 }}><FeAudioBar playing at={34} ticks={[0, 22, 44, 62]} time="1:26 / 4:12" now={<React.Fragment><b>Planche 2</b> — la réplique</React.Fragment>} /></div>,
      t: 'Audio control · “Écouter l’épisode”',
      p: 'First-class. Idle/playing bar; per-panel ticks on the scrubber; per-panel play chip on the plate. Yellow = the sound plate.',
      props: ['playing', 'at', 'ticks[]', 'now', 'time'],
    },
    {
      demo: <div style={{ width: 210 }}><FeArchivePlate roman="III" title="Le quai à marée basse" date="7 juin" location="Le Vieux-Port" char="marin" slug="marin" choice="Je peux monter ?" outcome="Marin vous a laissé barrer." /></div>,
      t: 'Filed plate / archive row',
      p: 'Roman numeral, lead-character portrait, date · location, your choice, its outcome, thumbnail, filed stamp. Current highlighted, à-venir dimmed.',
      props: ['roman', 'title', 'date', 'location', 'char', 'choice', 'outcome', 'state'],
    },
    {
      demo: <div style={{ width: 210 }}><FeCastCard char="romy" register="tu" closeness={3} switchEp={4} callbacks={['la lettre', 'le tutoiement']} last="« Passe demain. »" /></div>,
      t: 'Cast card + register stamp',
      p: 'Portrait, earned tu/vous stamp, closeness meter, the episode a tu-switch was filed in, callback chips, last-interaction line — a living ledger.',
      props: ['char', 'register', 'closeness', 'register_switch_episode', 'callbacks[]', 'last_summary'],
    },
    {
      demo: <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}><FeMeCard name="Toi" /></div>,
      t: 'Learner avatar',
      p: 'The learner’s own serial character with a real reference/customise affordance — inked, not drawn.',
      props: ['name', 'ini', 'ref slug', 'onCustomise'],
    },
    {
      demo: <div style={{ display: 'flex', gap: 14 }}><FeFiled label="Classé" /><div className="fe-colorable" style={{ width: 44, height: 30, border: '1.5px solid var(--app-ink)', background: 'var(--char-romy)' }}></div></div>,
      t: 'Filed stamp + print-in',
      p: 'On completion the plate resolves grayscale→colour (filter/opacity only, .7s, reduced-motion safe) and the red FILED stamp is struck.',
      props: ['.fe-filed .fe-colorable', 'fe-printin'],
    },
  ];
  return (
    <div className="fe-board">
      <div className="fe-board-head">
        <div className="k">Le Feuilleton · Système</div>
        <h2>Les primitives du supplément</h2>
        <p>Eight shared parts across the four views. EB Garamond (--app-serif) for story & headlines; Inter for chrome. Spacing scale 6 / 9 / 13 / 18px. Every prop maps to a named engineer field.</p>
      </div>
      {rows.map((r, i) => (
        <div className="fe-spec-row" key={i}>
          <div className="demo">{r.demo}</div>
          <div className="desc">
            <div className="t">{r.t}</div>
            <p>{r.p}</p>
            <div className="props">{r.props.map((p, j) => <span key={j}>{p}</span>)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---- 2. TOKEN BOARD — --app-* only, derived values documented --- */
function FeTokenBoard() {
  const toks = [
    ['--app-paper', 'page stock', 'var(--app-paper)', 'var(--app-ink)'],
    ['--app-sheet', 'card / inset', 'var(--app-sheet)', 'var(--app-ink)'],
    ['--app-ink', 'text & rules', 'var(--app-ink)', 'var(--app-paper)'],
    ['--app-ink-3', 'meta / muted', 'var(--app-ink-3)', 'var(--app-paper)'],
    ['--app-red', 'imprimatur / CTA', 'var(--app-red)', '#fff'],
    ['--app-yellow', 'the sound plate', 'var(--app-yellow)', 'var(--app-ink)'],
  ];
  return (
    <div className="fe-board">
      <div className="fe-board-head">
        <div className="k">Le Feuilleton · Contrainte dure</div>
        <h2>Jetons uniquement — light &amp; dark</h2>
        <p>The old reader hardcoded its palette and re-aliased tokens. Removed. The reader now reads <code style={{ fontFamily: 'var(--fe-mono)', fontSize: 11 }}>--app-*</code> straight, so dark is free.</p>
      </div>
      <div className="fe-tokens">
        {toks.map((t, i) => (
          <div className="sw" key={i}>
            <div className="chip" style={{ background: t[2] }}></div>
            <div className="meta"><div className="nm">{t[0]}</div><div className="role">{t[1]}</div></div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 22, borderTop: '1px solid var(--app-paper-3)', paddingTop: 16 }}>
        <div style={{ fontSize: 10, fontWeight: 900, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--app-ink)' }}>Valeurs dérivées — documentées</div>
        <div style={{ marginTop: 10, display: 'grid', gap: 8, fontFamily: 'var(--fe-mono)', fontSize: 10.5, lineHeight: 1.5, color: 'var(--app-ink-2)' }}>
          <div><b style={{ color: 'var(--app-red)' }}>--fe-newsprint</b> = paper-3 over paper — the undone/ungraded panel wash. Not a new hue.</div>
          <div><b style={{ color: 'var(--app-red)' }}>--fe-halftone</b> = ink @ 6% (dark: paper @ 5%) — the 135° tint field on a set-but-unread plate.</div>
          <div><b style={{ color: 'var(--app-red)' }}>--fe-scrim</b> = ink @ .18 — the bubble drop-shadow that keeps speech legible over arbitrary art.</div>
          <div><b style={{ color: 'var(--app-red)' }}>--char-*</b> = one spot ink per cast member (world bible). Lifts a step in dark; reads as border+fill over ink both ways.</div>
        </div>
      </div>
    </div>
  );
}

/* ---- 3. FRENCH COPY DECK — all states --------------------- */
function FeCopyBoard() {
  const rows = [
    ['Masthead', [['fr', 'Le Feuilleton · Saison 1 · Épisode 4'], ['fr', '« La lettre au fond du tiroir »'], ['note', 'Kicker : Le supplément illustré de l’édition']]],
    ['Précédemment', [['fr', 'Précédemment — Hier, vous avez proposé le tutoiement à Romy. Elle a accepté.']]],
    ['Relation', [['fr', 'tu · accordé — proximité ●●●○○'], ['note', 'Registre gagné, jamais pris.']]],
    ['Audio · repos', [['fr', 'Le Feuilleton · version sonore'], ['fr', 'Écouter l’épisode · 4:12']]],
    ['Audio · lecture', [['fr', 'Lecture en cours — Planche 2'], ['fr', '« Tu as vu l’heure du cachet ? Minuit passé. »']]],
    ['Exercice (plié)', [['fr', 'Un exercice vous attend — quand vous aurez lu.'], ['fr', 'Réviser →']]],
    ['Exercice (ouvert)', [['fr', 'Complétez : « Tu ___ l’heure du cachet ? »'], ['note', 'Correction : Passé composé — as vu, pas as voyais.']]],
    ['Planche en cours', [['fr', 'On tire la planche I…'], ['note', 'scene.status = generating']]],
    ['Planche retardée', [['fr', 'La presse a du retard. Le texte mène ; l’image suit sous peu.'], ['note', 'scene.status = delayed']]],
    ['À suivre', [['fr', 'À suivre — Et si la lettre lui était adressée, à elle ?'], ['fr', 'Demain — Romy ouvre le tiroir']]],
    ['Classé', [['fr', 'Classé · Épisode 4 déposé'], ['fr', 'Lire l’épisode 5 →'], ['fr', 'Aller agir dans Le Courrier →']]],
    ['Vide / 1er run', [['fr', 'Le premier numéro n’est pas encore paru.'], ['fr', 'Ouvrir l’épisode 1 →']]],
    ['Archive', [['fr', 'La saison reliée — 4 / 12'], ['fr', 'Votre réplique : « On se tutoie, alors ? »'], ['fr', 'Romy a accepté — le vouvoiement est tombé.']]],
    ['Archive · presque vide', [['fr', 'Le premier cahier · à peine relié'], ['fr', 'La reliure commence. Revenez demain pour la planche II.']]],
    ['Personnages', [['fr', 'Les personnages — le registre du théâtre'], ['fr', 'Rappels : la lettre de minuit · le tutoiement'], ['fr', 'Dernier échange — « Passe demain. »']]],
    ['Personnages · tôt', [['fr', 'Tout le monde vous vouvoie encore.'], ['fr', 'Le tutoiement s’accorde — il ne se prend pas.']]],
    ['Chargement', [['fr', '— on tire l’édition —']]],
    ['Erreur', [['fr', 'Avis de la rédaction — La planche n’a pas pu être imprimée. Le récit reste lisible.'], ['fr', 'Réessayer']]],
    ['Chrome (EN)', [['en-chrome', 'La Une · La saison reliée · EN · permalink · lecture seule'], ['note', 'Out-of-fiction only. Never mix languages in one line.']]],
  ];
  return (
    <div className="fe-board">
      <div className="fe-board-head">
        <div className="k">Le Feuilleton · Copy</div>
        <h2>Le cahier de copie</h2>
        <p>French for the publication and the story world; English only for out-of-fiction chrome. Never mixed in one line.</p>
      </div>
      <div className="fe-copy">
        {rows.map((r, i) => (
          <div className="fe-copy-row" key={i}>
            <div className="state">{r[0]}</div>
            <div className="lines">
              {r[1].map((l, j) => (
                l[0] === 'note'
                  ? <div className="note" key={j}>{l[1]}</div>
                  : <div className={l[0] === 'en-chrome' ? 'fr en-chrome' : 'fr'} key={j}>{l[1]}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---- 4. MIGRATION NOTE ------------------------------------ */
function FeMigrationBoard() {
  const rows = [
    ['Dateline masthead', 'graphic-novel.tsx', 'EditorialMasthead', 'new', 'Redrawn. Keeps Today link + EN toggle + New; adds folio, dateline, progress rule.'],
    ['Panel + on-art bubble', 'graphic-novel.tsx', 'FeuilletonPanel / SpeechBubble', 'new', 'Frame/bubble/caption redrawn; bubble position keeps scene.panels[].bubbles[].{x,y,tone}.'],
    ['Relationship chip', 'graphic-novel.tsx', '— (none)', 'new', 'New surface. Reads cast.relationship live during the read.'],
    ['Audio control', 'graphic-novel.tsx', 'audio_payload plumbing', 'keep', 'LOGIC stays; UI is redrawn to first-class bar + per-panel play.'],
    ['Study task', 'graphic-novel.tsx', 'mobileTaskStops + MobileBottomSheet', 'keep', 'Play loop unchanged — attemptsByTask, openMobileTask kept; only the sheet skin is redrawn read-first.'],
    ['EN toggle / gloss', 'graphic-novel.tsx', 'showMobileTranslations', 'keep', 'State kept; add word-level tap-to-gloss on top.'],
    ['Filed plate / archive', 'serial/index.tsx', 'SerialArchiveList', 'new', 'Rows → filed plates. Maps episodes[].{choice,outcome,thumbnail_url,completed_at,required_cast}.'],
    ['Cast card + stamp', 'serial/cast.tsx', 'CastGrid / CastMemberCard', 'new', 'Redrawn as ledger. Maps member.relationship.{register,closeness,register_switch_episode,callbacks,last_summary}.'],
    ['Permalink', 'serial/episode/[index].tsx', 'EpisodePermalink', 'keep', 'Reuses FeReaderA read-only (state="permalink"). No new logic.'],
    ['Palette / tokens', 'graphic-novel.tsx', 'FeuilletonStyles (hardcoded)', 'new', 'REMOVED. All --app-* now; no re-aliasing. This is the #1 change.'],
  ];
  return (
    <div className="fe-board">
      <div className="fe-board-head">
        <div className="k">Le Feuilleton · Handoff</div>
        <h2>Note de migration</h2>
        <p>What each new surface replaces across graphic-novel.tsx, serial/index.tsx, serial/cast.tsx — and which logic components stay. We redraw surfaces; we don’t touch the play loop.</p>
      </div>
      <div className="fe-mig">
        <div className="fe-mig-head"><span>New component</span><span>Replaces</span><span>Status</span></div>
        {rows.map((r, i) => (
          <div className="fe-mig-row" key={i}>
            <div className="comp">{r[0]}<span className="file">{r[1]}</span></div>
            <div className="repl">{r[2]}</div>
            <div className={'stat ' + r[3]}>{r[3] === 'keep' ? '✓ logic kept' : '◆ redrawn'}<div style={{ marginTop: 4, fontWeight: 400, color: 'var(--app-ink-2)', fontFamily: 'var(--app-grotesk)', fontSize: 10 }}>{r[4]}</div></div>
          </div>
        ))}
      </div>
      <div className="fe-note">
        <b>Kept intact:</b> the reading → task → audio → completion loop, attemptsByTask scoring, mobileTaskStops anchoring, audio_payload playback, generationFailure handling, and the bottom nav. This pass is surfaces only.
      </div>
    </div>
  );
}

Object.assign(window, {
  FeSpecBoard, FeTokenBoard, FeCopyBoard, FeMigrationBoard,
});
