/* Atelier — Serial World screens.
   Composes the act → see loop onto the design canvas, plus the
   system spec boards. Tweak-driven where it earns it. */

const { useState, useEffect } = React;

/* ============================================================
   EPISODE 04 — "L'inspection"  (content)
   ============================================================ */
const REPLY_MOODS = {
  warm: {
    mood: 'warm', moodLabel: 'Radouci · warm', score: 4,
    speech: '« Ah — je comprends mieux. Si le radiateur fuit, j’enverrai quelqu’un jeudi. Merci de m’avoir prévenu. »',
    gloss: 'You explained that the radiator broke (not that you broke it) and proposed a time — in vous. He softens and the scene resolves.',
    needs: [
      { t: <span>Say <em>what happened</em> — radiator, passé composé</span>, met: true },
      { t: <span>Propose a fix — <em>si</em> + future</span>, met: true },
      { t: <span>Stay in <em>vous</em> with the landlord</span>, met: true },
    ],
    resolved: true,
  },
  cool: {
    mood: 'cool', moodLabel: 'Réservé · guarded', score: 3,
    speech: '« Bien. Jeudi, alors. Soyez là à neuf heures — et ne touchez à rien d’ici là. »',
    gloss: 'Clipped, but he got what he needed. He’ll act. He is not your friend yet — and that distance is a thread for later.',
    needs: [
      { t: <span>Say <em>what happened</em> — radiator, passé composé</span>, met: true },
      { t: <span>Propose a fix — <em>si</em> + future</span>, met: true },
      { t: <span>Stay in <em>vous</em> with the landlord</span>, met: true },
    ],
    resolved: true,
  },
  confused: {
    mood: 'confused', moodLabel: 'Perdu · confused', score: 1,
    speech: '« Pardon ? Vous… vous avez cassé le radiateur ? Je ne comprends pas ce que vous me demandez. »',
    gloss: 'A tense slip turned “it broke” into “I broke it.” He can’t act on this — he thinks you’re confessing, not asking.',
    needs: [
      { t: <span>Say <em>what happened</em> — radiator, passé composé</span>, met: false },
      { t: <span>Propose a fix — <em>si</em> + future</span>, met: false },
      { t: <span>Stay in <em>vous</em> with the landlord</span>, met: true },
    ],
    resolved: false,
  },
};

const CLIFF_TONES = {
  intimate: {
    question: '« Tu savais que l’appartement du dessus n’a jamais été déclaré ? »',
    beat: 'She lowers the microphone. For once she isn’t performing — she’s asking you, neighbour to neighbour, in tu.',
  },
  suspense: {
    question: '« L’appartement du dessus n’existe pas sur le papier. Et c’est toi qui y habites. »',
    beat: 'The red light on her recorder is already on. Whatever you say next, the whole quartier hears tomorrow.',
  },
};

const RECAP_WORDS = [
  { fr: 'le radiateur', en: 'radiator' },
  { fr: 'déclarer', en: 'to register / declare' },
  { fr: 'prévenir', en: 'to warn, notify' },
  { fr: 'le dessus', en: 'the floor above' },
  { fr: 'à suivre', en: 'to be continued' },
];

const MAP_EPISODES = [
  { n: 'I',  date: '12 mai', loc: 'Le Mistral', who: 'margaux', hook: 'L’arrivée — a key that wouldn’t turn.', choice: 'You asked Margaux for the spare.', plate: 'EST · café, night' },
  { n: 'II', date: '19 mai', loc: 'L’immeuble', who: 'marin', hook: 'Le voisin — a knock at the wrong hour.', choice: 'You let Marin in.', plate: 'INT · landing' },
  { n: 'III',date: '26 mai', loc: 'Oberkampf', who: 'romy', hook: 'Le micro — a reporter, a camera, your name.', choice: 'You stayed and spoke.', plate: 'EXT · street, rain' },
  { n: 'IV', date: '31 mai', loc: 'Le Mistral', who: 'marchand', hook: 'L’inspection — the landlord wants in.', choice: 'Wrote back in vous; proposed Thursday.', plate: 'INT · the booth' },
  { n: 'V',  date: 'à suivre', loc: '?', who: 'romy', hook: 'Le direct — what you say goes on air.', up: true },
];

/* ============================================================
   A1 — THE SERIAL ON-RAMP (Atelier home)
   ============================================================ */
function AlsoToday({ label, title, meta }) {
  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontSize: 9, fontWeight: 900, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--ink-3)', marginBottom: 9 }}>{label}</div>
      <a href="#" style={{ display: 'flex', alignItems: 'center', gap: 12, textDecoration: 'none', color: 'var(--ink)', border: '1px solid var(--ink)', background: 'var(--sheet)', padding: '12px 14px' }}>
        <span className="s-ava sm" data-char="toi" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>VI</span>
        <span style={{ minWidth: 0 }}>
          <span style={{ display: 'block', fontFamily: 'var(--serif)', fontStyle: 'italic', fontWeight: 600, fontSize: 18, lineHeight: 1 }}>{title}</span>
          <span style={{ display: 'block', fontSize: 9, fontWeight: 900, letterSpacing: '.13em', textTransform: 'uppercase', color: 'var(--ink-3)', marginTop: 4 }}>{meta}</span>
        </span>
        <span style={{ marginLeft: 'auto', width: 16, height: 16, color: 'var(--ink)' }}><SArrow /></span>
      </a>
    </div>
  );
}

function AtelierHome({ state }) {
  const cfg = {
    act:  { rubric: 'The serial · your turn', sub: 'Episode 4 · Marchand is waiting', height: 736 },
    see:  { rubric: 'The serial · new episode', sub: 'Episode 4 · ready to read', height: 712 },
    invite:{ rubric: 'The serial · begins today', sub: 'Episode 1 · an invitation', height: 688 },
    rest: { rubric: 'The serial · all caught up', sub: 'You’re even with the story', height: 700 },
  }[state];
  return (
    <div className="ph" style={{ height: cfg.height }}>
      <Head title="Atelier" />
      <div className="ph-body">
        <Edition rubric={cfg.rubric} date="Samedi 31 mai" sub={cfg.sub} streak="12" />
        <div style={{ marginTop: 18 }}>
          {state === 'act' && (
            <ThreadCard variant="act" who="marchand" ep="Episode 4 · Act"
              prev="you survived Romy’s camera on Oberkampf."
              beat="Le propriétaire a répondu" title="“Je passe lundi. Soyez là.”"
              sub="Marchand wants to inspect the flat. Toi needs to reply — in his language."
              cta="Reply to Marchand" />
          )}
          {state === 'see' && (
            <ThreadCard variant="see" who="marin" ep="Episode 4 · See"
              prev="you wrote back to Marchand, in vous."
              beat="New episode ready" title="“L’inspection”"
              sub="The reply you wrote becomes the scene. See what it set in motion at Le Mistral."
              cta="Read episode 4" ctaInk />
          )}
          {state === 'invite' && (
            <ThreadCard variant="invite" who="margaux" ep="Episode 1 · begins"
              beat="A new serial" title="“L’arrivée”"
              sub="A café in the 11th, a key that won’t turn, and people who’ll remember you. Your French moves the story."
              cta="Begin episode 1" ctaInk />
          )}
          {state === 'rest' && (
            <ThreadCard variant="rest" who="romy" ep="Episode 4 · settled"
              prev="you sent the story on air with Romy."
              beat="— Fin de l’épisode —" title="You’re caught up."
              sub="Episode 5 is still being typeset. Let the cliffhanger sit overnight — it’s working on you." />
          )}
        </div>
        {state !== 'rest' && <AlsoToday label="Also in today’s edition" title="Grammar session" meta={state === 'invite' ? 'I–VI · not started' : '2 of 6 signatures set'} />}
        {state === 'rest' && (
          <div style={{ marginTop: 22, textAlign: 'center' }}>
            <div className="datestamp" style={{ display: 'inline-block', border: '1px solid var(--ink-3)', color: 'var(--ink-3)', fontSize: 9, fontWeight: 900, letterSpacing: '.16em', textTransform: 'uppercase', padding: '5px 10px', transform: 'rotate(-3deg)' }}>À suivre · 02 · 06</div>
          </div>
        )}
      </div>
      <Nav active="atelier" />
    </div>
  );
}

/* ============================================================
   A2 — THE ACT SCREEN
   ============================================================ */
function ActScreen({ mood }) {
  const m = REPLY_MOODS[mood] || REPLY_MOODS.warm;
  return (
    <div className="ph" style={{ height: 1218 }}>
      <Head title="Atelier" />
      <div className="ph-body">
        <Edition rubric="Act · Episode 4" rubricMuted={false} date="L’inspection" sub="Reply to the landlord — keep the flat" />
        <ContextAnchor loc="Le Mistral · your booth" partner="marchand" />

        <div style={{ display: 'grid', gap: 12 }}>
          <Said who="marchand" line="« Je passe lundi pour l’état des lieux. J’ai eu une plainte pour le bruit. »" gloss="A complaint about the noise — he’s coming Monday to inspect." />
          <Said who="toi" you line="« Bonjour Monsieur. En fait, le radiateur a cessé de marcher — c’est l’eau, pas le bruit. Si vous envoyez un plombier, je serai là toute la semaine. »" />
        </div>

        <div style={{ margin: '15px 0 9px', fontSize: 9, fontWeight: 900, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>His reply — the payoff</div>

        <ReplyCard who="marchand" mood={m.mood} moodLabel={m.moodLabel} loc="Le Mistral"
          speech={m.speech} gloss={m.gloss} needs={m.needs} score={m.score} />

        {m.resolved ? (
          <OutcomeHook
            what="Marchand will send a plumber Thursday — and he let something slip."
            hook="“The flat upstairs is empty now,” he said. “Strange — it was never on my books.” Romy has been asking about that same flat all week."
            cta="See what happens" />
        ) : (
          <React.Fragment>
            <RepairSlip why="“J’ai cassé le radiateur” tells him you broke it. One tense turns a request into a confession.">
              <span><b>What he heard:</b> <del>j’ai cassé le radiateur</del> → <ins>le radiateur est tombé en panne</ins>. The thing broke; you didn’t break it.</span>
            </RepairSlip>
            <a className="cta" href="#" style={{ marginTop: 14 }}>Try the line again <SArrow /></a>
          </React.Fragment>
        )}
      </div>
      <Nav active="atelier" />
    </div>
  );
}

/* ============================================================
   A3 — THE SERIAL READER (vertical scroll)
   ============================================================ */
function ReaderVertical() {
  return (
    <div className="ph" style={{ height: 2024 }}>
      <Head title="Atelier" />
      <div className="s-feuil">
        <ReaderMast kicker="Le Feuilleton" title="L’inspection" ep="4" loc="Le Mistral, XIᵉ"
          news="« Un immeuble du XIᵉ logerait des locataires non déclarés » — Romy Tremblay, Radio Canal." />

        <PreviouslyOn>
          You survived Romy’s camera on Oberkampf — and let slip that you live on the fourth floor. Marchand went quiet. Until this morning, when the phone lit up in your hand.
        </PreviouslyOn>

        <Panel n="01" h={208}
          frame="EST · LE MISTRAL — INT, day, rain on glass"
          dir="wide · zinc counter, Margaux drying a cup, your booth by the window"
          caption="Le Mistral, neuf heures. La pluie écrit sur la vitre." />

        <Panel n="02" h={216}
          frame="MED · MARIN slides into the booth"
          float={{ who: 'marin', line: '« Il t’a écrit, le proprio ? Montre. »', pos: { left: 14, bottom: 12 } }}
          caption="Marin se glisse en face de toi, déjà inquiet pour toi." />

        <Panel n="03" h={200}
          frame="CU · the phone, screen lit — “M. MARCHAND”"
          dir="prop continuity · the glowing phone (landlord thread)"
          caption={<span>Sur l’écran, un seul mot : « inspection ». Il veut <span className="s-cloze done">visiter</span> l’appartement.</span>} />

        <ChoiceFork prompt="Marin asks what you’ll tell him."
          options={[
            { line: '« Qu’il vienne. Je n’ai rien à cacher. »', chosen: true },
            { line: '« Pas avant que j’aie parlé à Romy. »' },
          ]} />

        <Panel n="04" h={206}
          frame="MED · MARIN reacts to your line"
          float={{ who: 'marin', line: '« D’accord. Mais je reste, alors. »', pos: { right: 14, bottom: 12 } }}
          caption="Il hoche la tête, lentement. Ta phrase devient la sienne." />

        <Panel n="05" h={196}
          frame="WIDE · the café door opens — a silhouette, a microphone"
          dir="Romy enters · cold air first. Hold on the door."
          caption="La porte s’ouvre. Le froid entre avant elle." />

        <div style={{ textAlign: 'center', padding: '6px 18px 22px' }}>
          <div style={{ fontSize: 9, fontWeight: 900, letterSpacing: '.18em', textTransform: 'uppercase', color: 'var(--ink-3)', display: 'inline-flex', alignItems: 'center', gap: 9 }}>
            <span style={{ width: 22, height: 1, background: 'var(--ink-3)' }} />à suivre<span style={{ width: 22, height: 1, background: 'var(--ink-3)' }} />
          </div>
        </div>
      </div>
      <Nav active="atelier" />
    </div>
  );
}

/* compact vertical slice for the render-mode comparison */
function ReaderVerticalMini() {
  return (
    <div className="ph" style={{ height: 980 }}>
      <Head title="Atelier" />
      <div className="s-feuil">
        <ReaderMast kicker="Le Feuilleton" title="L’inspection" ep="4" loc="Le Mistral, XIᵉ" />
        <Panel n="01" h={150} frame="EST · LE MISTRAL — rain on glass"
          caption="Neuf heures. La pluie écrit sur la vitre." />
        <Panel n="02" h={158}
          frame="MED · MARIN at the booth"
          float={{ who: 'marin', line: '« Il t’a écrit, le proprio ? »', pos: { left: 12, bottom: 10 } }}
          caption="Marin se glisse en face de toi." />
        <ChoiceFork prompt="You write the next line."
          options={[{ line: '« Qu’il vienne. »', chosen: true }, { line: '« Pas encore. »' }]} />
      </div>
      <Nav active="atelier" />
    </div>
  );
}

/* comic-page render mode — fixed grid */
function ReaderComic() {
  return (
    <div className="ph" style={{ height: 980 }}>
      <Head title="Atelier" />
      <div className="s-page">
        <div className="s-mast" style={{ border: 0, borderBottom: '2px solid var(--ink)', padding: '4px 0 12px', marginBottom: 12 }}>
          <div className="kicker">Le Feuilleton · render mode “page”</div>
          <div className="title" style={{ fontSize: 26 }}>L’inspection</div>
        </div>
        <div className="s-grid">
          <div className="s-art wide">
            <span className="frame-note">EST · LE MISTRAL</span>
            <div className="gcap">Neuf heures. La pluie écrit sur la vitre.</div>
          </div>
          <div className="s-art">
            <span className="frame-note">MED · MARIN</span>
            <div className="float" data-char="marin" style={{ left: 8, top: 30, maxWidth: '88%' }}>
              <Said who="marin" line="« Montre. »" />
            </div>
          </div>
          <div className="s-art">
            <span className="frame-note">CU · le phone</span>
            <div className="gcap">« inspection »</div>
          </div>
          <div className="s-art">
            <span className="frame-note">MED · toi</span>
            <div className="float" data-char="toi" style={{ right: 8, top: 30, maxWidth: '88%' }}>
              <Said who="toi" you line="« Qu’il vienne. »" />
            </div>
          </div>
          <div className="s-art">
            <span className="frame-note">REACT · MARIN</span>
            <div className="gcap">Ta phrase devient la sienne.</div>
          </div>
          <div className="s-art wide">
            <span className="frame-note">WIDE · la porte s’ouvre</span>
            <div className="gcap">Le froid entre avant elle. — à suivre</div>
          </div>
        </div>
      </div>
      <Nav active="atelier" />
    </div>
  );
}

/* ============================================================
   A4 — THE CLIFFHANGER
   ============================================================ */
function CliffScreen({ tone, withRecap }) {
  const t = CLIFF_TONES[tone] || CLIFF_TONES.intimate;
  return (
    <div className="ph" style={{ height: withRecap ? 1024 : 760 }}>
      <Head title="Atelier" />
      <div style={{ flex: '0 0 auto' }}>
        <Cliffhanger who="romy"
          frame="CU · ROMY in the doorway, recorder raised — rain behind her"
          float={{ line: '…', pos: { right: 12, top: 14 } }}
          question={t.question}
          beat={t.beat}
          cta="Answer Romy"
          next="Next · Act · Episode 5 — “Le direct”" />
        {withRecap && <VocabRecap words={RECAP_WORDS} />}
      </div>
      {!withRecap && <div style={{ flex: 1, background: 'var(--ink)' }} />}
      <Nav active="atelier" />
    </div>
  );
}

/* ============================================================
   A5 — THE STORY SO FAR
   ============================================================ */
function StorySoFar() {
  return (
    <div className="ph" style={{ height: 1004 }}>
      <Head title="Atelier" />
      <div className="ph-body">
        <Edition rubric="The serial · index" date="The story so far" sub="Four installments with these people" />
        <div style={{ marginTop: 16 }}>
          <ThreadMap episodes={MAP_EPISODES} />
        </div>
      </div>
      <Nav active="atelier" />
    </div>
  );
}

Object.assign(window, {
  AtelierHome, ActScreen,
  ReaderVertical, ReaderVerticalMini, ReaderComic,
  CliffScreen, StorySoFar,
  REPLY_MOODS, CLIFF_TONES,
});
