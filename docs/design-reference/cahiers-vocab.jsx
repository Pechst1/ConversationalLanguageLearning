/* Atelier — LES CAHIERS · vocabulary screens (registre, fiche de mot, atlas, bibliothèque, routes directes). */

const NC_QUEUE = [
  { rank: null, word: 'abaisser', tr: 'herabsetzen, senken', pos: 'verbe', bucket: { id: 'due', label: 'À revoir' } },
  { rank: null, word: 'l’épreuve', tr: 'die Druckfahne, die Prüfung', pos: 'nom', bucket: { id: 'fragile', label: 'Fragile' }, sel: true },
  { rank: null, word: 'abattre', tr: 'niederreißen, fällen', pos: 'verbe', bucket: { id: 'due', label: 'À revoir' } },
  { rank: null, word: 'la manchette', tr: 'die Schlagzeile', pos: 'nom', bucket: { id: 'new', label: 'Nouveau' } },
];
const NC_DECK = [
  { rank: 208, word: 'l’encre', tr: 'die Tinte', pos: 'nom', state: 'mastered', stateLabel: 'Acquis' },
  { rank: 209, word: 'encrer', tr: 'einfärben', pos: 'verbe', state: 'solid', stateLabel: 'Solide' },
  { rank: 212, word: 'l’épreuve', tr: 'die Druckfahne, die Prüfung', pos: 'nom', state: 'fragile', stateLabel: 'Fragile' },
  { rank: 214, word: 'épuiser', tr: 'erschöpfen, vergreifen', pos: 'verbe', state: 'building', stateLabel: 'En cours' },
  { rank: 217, word: 'l’équipe', tr: 'die Mannschaft', pos: 'nom', state: 'new', stateLabel: 'Nouveau' },
];

/* ---------- View 3 · Vocabulary landing ---------- */
function PageVocabLanding({ dark = false, motion = true, wide = false }) {
  return (
    <NcShell dark={dark} motion={motion} wide={wide} screenLabel={'Carnet · vocabulaire' + (dark ? ' · sombre' : '')}>
      <NcMasthead cefr="A2.1 en cours" />
      <NcModeTabs active="vocabulaire" metas={{ grammaire: '54 fiches', vocabulaire: '12 à revoir', bibliotheque: '2 volumes' }} />
      <NcFilingSummary lead="Registre" items={[{ n: 12, label: 'à revoir', tone: 'due' }, { n: 4, label: 'fragiles', tone: 'due' }, { n: 6, label: 'nouveaux' }]} />
      <div className="nc-next">
        <div className="k"><span>À prendre ensuite</span><span className="why">complète la piste A2 · cuisine</span></div>
        <div className="words">
          {[['la casserole', 'der Kochtopf'], ['mijoter', 'schmoren'], ['la recette', 'das Rezept'], ['épais', 'dick(flüssig)']].map(([w, t]) => (
            <button className="w" key={w}><b>{w}</b><span>{t}</span></button>
          ))}
        </div>
      </div>
      <NcSearch placeholder="Chercher un mot…" />
      <NcChips active={0} chips={[{ l: 'Tous' }, { l: 'À revoir', n: 12 }, { l: 'Fragiles', n: 4 }, { l: 'Nouveaux', n: 6 }, { l: 'Acquis' }]} />
      <NcLiveSum text="4 cartes en file · 5 entrées du registre" />
      <NcLedgerHead t="File du jour — à revoir" n="4 cartes" />
      <div className="nc-index">{NC_QUEUE.map((w) => <NcWordRow key={w.word} {...w} sel={false} />)}</div>
      <NcLedgerHead t="Registre des mots — Français 5000" tone="blue" n="Nº 208 – 217" />
      <div className="nc-index">{NC_DECK.map((w) => <NcWordRow key={w.rank} {...w} />)}</div>
      <button className="nc-fold">
        <span><span className="t">Atlas des acquis</span><span className="s" style={{ display: 'block' }}>612 mots tenus sur 5 000 · carte pliée</span></span>
        <span className="chev">Déplier <NcIcoFold /></span>
      </button>
      <div className="nc-dossier">
        <div className="k">Dossier de la semaine</div>
        <h3>Semaine 29 — le registre s’épaissit.</h3>
        <dl>
          <div><dt>Réparations</dt><dd>7</dd></div>
          <div><dt>Révisions</dt><dd>41</dd></div>
          <div><dt>Vus</dt><dd>63</dd></div>
          <div><dt>Employés</dt><dd>19</dd></div>
        </dl>
        <div className="thread"><b>l’épreuve · fil fragile</b><em>Deux ratés de suite en production — resémer en mission.</em></div>
      </div>
      <NcColophon />
    </NcShell>
  );
}

/* ---------- View 4 · Word entry sheet ---------- */
function PageWordSheet({ dark = false, motion = true }) {
  return (
    <NcShell dark={dark} motion={motion} screenLabel={'Fiche de mot · l’épreuve' + (dark ? ' · sombre' : '')}>
      <NcMasthead cefr="A2.1 en cours" />
      <NcModeTabs active="vocabulaire" metas={{ grammaire: '54 fiches', vocabulaire: '12 à revoir', bibliotheque: '2 volumes' }} />
      <NcLedgerHead t="File du jour — à revoir" n="4 cartes" />
      <div className="nc-index">{NC_QUEUE.map((w) => <NcWordRow key={w.word} {...w} />)}</div>
      <div style={{ height: 340 }}></div>
      <div className="nc-sheetstage">
        <div className="scrim" aria-hidden="true"></div>
        <div className="nc-sheet" role="dialog" aria-modal="true" aria-label="Fiche du mot l’épreuve">
          <div className="grab" aria-hidden="true"></div>
          <div className="shead">
            <div>
              <div className="k">Registre des mots · Nº 212</div>
              <h2>l’épreuve</h2>
              <div className="tr">die Druckfahne, die Prüfung</div>
            </div>
            <button className="x" aria-label="Fermer la fiche"><NcIcoX /></button>
          </div>
          <div className="nc-metagrid">
            <div><b>#212</b><span>Rang de fréquence</span></div>
            <div><b>nom, f.</b><span>Catégorie</span></div>
            <div><b>N2</b><span>Difficulté</span></div>
          </div>
          <div className="nc-fragnote">
            <span className="tag">Fil fragile</span>
            <p>Deux ratés de suite en production — la stabilité retombe. Revue avancée à aujourd’hui.</p>
          </div>
          <div className="nc-ratings" role="group" aria-label="Noter la révision">
            <button className="again"><b>Again</b><span>Reviendra vite</span></button>
            <button className="hard"><b>Hard</b><span>Garder proche</span></button>
            <button className="good"><b>Good</b><span>Revue normale</span></button>
            <button className="easy"><b>Easy</b><span>Éloigner</span></button>
          </div>
          <div className="nc-seedacts">
            <a href="#">Biographie du mot <em>4 traces</em></a>
            <a href="#">Semer en mission <em>Le Courrier</em></a>
            <a href="#">Lire au feuilleton <em>Épisode à la demande</em></a>
            <a href="#">Composer à l’Atelier <em>exercices ciblés</em></a>
          </div>
        </div>
      </div>
    </NcShell>
  );
}

/* ---------- View 4b · Biography ---------- */
function PageBiography({ dark = false }) {
  return (
    <NcShell dark={dark} screenLabel="Biographie du mot">
      <NcMasthead slim route="Biographie du mot" xlink="Registre" />
      <header className="nc-entryhead" style={{ marginTop: 12 }}>
        <div className="tags"><span className="nc-tagchip cat"><i></i>nom, f.</span><span className="nc-tagchip lvl"><i></i>#212</span></div>
        <h2>l’épreuve — sa vie dans votre édition</h2>
        <div className="row2"><span>Origine · Feuilleton, Épisode 9</span><span className="nxt">Progrès · fragile → en cours</span></div>
      </header>
      <NcSec kick="Chronique" tone="blue" ct="5 événements">
        <div className="nc-bio">
          <div className="ev first"><i></i><span className="b"><b>Première rencontre — Le Feuilleton, Épisode 9</b><em>« Les épreuves attendaient sur le marbre. »</em></span><span className="d">2 juil.</span></div>
          <div className="ev good"><i></i><span className="b"><b>Reconnu en lecture</b><em>Sans indice, en contexte.</em></span><span className="d">4 juil.</span></div>
          <div className="ev bad"><i></i><span className="b"><b>Raté en production — Mission « Au kiosque »</b><em>« la épreuve » → l’épreuve</em></span><span className="d">9 juil.</span></div>
          <div className="ev bad"><i></i><span className="b"><b>Raté en dictée — L’Épreuve</b><em>Genre confondu ; erratum classé.</em></span><span className="d">15 juil.</span></div>
          <div className="ev good"><i></i><span className="b"><b>Réparé — révision réussie</b><em>Stabilité en légère hausse.</em></span><span className="d">18 juil.</span></div>
        </div>
      </NcSec>
      <NcSec kick="Exemples au dossier" tone="mut" ct="2 sources">
        <NcExample fr="Les <b>épreuves</b> attendaient sur le marbre." de="Die Druckfahnen warteten auf dem Satztisch." />
        <NcExample fr="Corriger une <b>épreuve</b> avant le tirage." de="Eine Druckfahne vor dem Druck korrigieren." />
      </NcSec>
      <a className="nc-cta quiet" href="#">Retour à la fiche <NcIcoArrow /></a>
      <NcColophon />
    </NcShell>
  );
}

/* ---------- View 5 · Atlas des acquis (fold-out) ---------- */
function PageAtlas({ dark = false, motion = true }) {
  return (
    <NcShell dark={dark} motion={motion} screenLabel={'Atlas des acquis' + (dark ? ' · sombre' : '')}>
      <NcMasthead cefr="A2.1 en cours" />
      <NcModeTabs active="vocabulaire" metas={{ grammaire: '54 fiches', vocabulaire: '12 à revoir', bibliotheque: '2 volumes' }} />
      <button className="nc-fold" style={{ background: 'var(--app-sheet)' }}>
        <span><span className="t">Atlas des acquis</span><span className="s" style={{ display: 'block' }}>612 mots tenus sur 5 000 · carte dépliée</span></span>
        <span className="chev">Replier <NcIcoFold open /></span>
      </button>
      <NcLedgerHead t="Couverture CECR" n="mots tenus / bande" />
      <NcCoverageTrack lab="A1" val={498} max={700} tone="ink" />
      <NcCoverageTrack lab="A2" val={102} max={900} />
      <NcCoverageTrack lab="B1" val={12} max={1400} />
      <NcCoverageTrack lab="B2" val={0} max={2000} />
      <NcLedgerHead t="Pistes par domaine" tone="blue" n="4 en cours" />
      <NcCoverageTrack lab="Cuisine" val={31} max={60} />
      <NcCoverageTrack lab="Presse" val={44} max={50} tone="ink" />
      <NcCoverageTrack lab="Voyage" val={12} max={80} />
      <NcCoverageTrack lab="Bureau" val={8} max={40} tone="red" />
      <NcLedgerHead t="Verbes & structures" tone="blue" n="2 pistes" />
      <NcCoverageTrack lab="Verbes" val={86} max={300} />
      <NcCoverageTrack lab="Structures" val={9} max={20} tone="ink" />
      <NcLedgerHead t="Carte de maîtrise — Français 5000" n="1 case = 1 mot" />
      <NcMasteryMap n={280} totals={[
        { id: 'due', label: 'À revoir', n: 12 }, { id: 'fragile', label: 'Fragiles', n: 4 },
        { id: 'building', label: 'En cours', n: 57 }, { id: 'solid', label: 'Solides', n: 419 },
        { id: 'mastered', label: 'Acquis', n: 120 }, { id: '', label: 'Nouveaux', n: 4388 },
      ]} note="Les 280 premières cases par rang de fréquence — la carte entière (5 000) se parcourt par bandes, jamais imposée à la lecture." />
      <div className="nc-next" style={{ marginTop: 16 }}>
        <div className="k"><span>À prendre ensuite</span><span className="why">meilleur gain de couverture</span></div>
        <div className="words">
          {[['la casserole', 'der Kochtopf'], ['mijoter', 'schmoren'], ['la recette', 'das Rezept']].map(([w, t]) => (
            <button className="w" key={w}><b>{w}</b><span>{t}</span></button>
          ))}
        </div>
      </div>
      <NcColophon />
    </NcShell>
  );
}

/* ---------- View 6 · Bibliothèque ---------- */
function PageLibrary({ dark = false }) {
  return (
    <NcShell dark={dark} screenLabel="Carnet · bibliothèque">
      <NcMasthead cefr="A2.1 en cours" />
      <NcModeTabs active="bibliotheque" metas={{ grammaire: '54 fiches', vocabulaire: '12 à revoir', bibliotheque: '2 volumes' }} />
      <NcFilingSummary lead="Reliure" items={[{ n: 2, label: 'volumes' }, { n: 1, label: 'lecture en cours' }]} />
      <NcLedgerHead t="Volumes reliés" n="2 au dossier" />
      <button className="nc-book">
        <span className="spine" aria-hidden="true"></span>
        <span><span className="t">Le Petit Nicolas</span><span className="m" style={{ display: 'block' }}>Chapitre 3 de 19 · lecture du soir</span></span>
        <span className="pr"><span className="pct">16 %</span><span className="bar"><i style={{ width: '16%' }}></i></span></span>
      </button>
      <button className="nc-book b2">
        <span className="spine" aria-hidden="true"></span>
        <span><span className="t">Contes du lundi</span><span className="m" style={{ display: 'block' }}>Non commencé · 24 chapitres</span></span>
        <span className="pr"><span className="pct">—</span><span className="bar"><i style={{ width: 0 }}></i></span></span>
      </button>
      <NcLedgerHead t="Exercice du chapitre" tone="blue" n="l’existant, refilé" />
      <div className="nc-runner">
        <div className="k"><span>Le Petit Nicolas · ch. 3</span><span className="pg">Question 2 / 6</span></div>
        <p className="q">Nicolas range <span className="gap"></span> cartable avant de sortir.</p>
        <div className="nc-chips" style={{ marginTop: 12 }}>
          <button className="nc-chip">son</button>
          <button className="nc-chip">sa</button>
          <button className="nc-chip">ses</button>
        </div>
      </div>
      <NcNotice tone="yellow" label="Mode optionnel" message="La Bibliothèque paraît seulement si son drapeau de lancement est levé ; sans lui, le carnet garde deux onglets." retry={false} />
      <NcColophon />
    </NcShell>
  );
}

/* ---------- View 7 · Direct routes ---------- */
function PageDirectGrammar({ dark = false }) {
  return (
    <NcShell dark={dark} screenLabel="/grammar · route directe">
      <NcMasthead slim route="Grammaire" xlink="Vocabulaire" />
      <NcFilingSummary lead="Classement" items={[{ n: 54, label: 'fiches' }, { n: 3, label: 'à revoir', tone: 'due' }]} />
      <NcSearch placeholder="Chercher une règle…" />
      <NcChips active={1} chips={[{ l: 'Toutes', n: 54 }, { l: 'À revoir', n: 3 }, { l: 'A1' }, { l: 'A2' }]} />
      <NcLiveSum text="3 fiches à revoir" clearable />
      <NcLedgerHead t="Index des règles" n="3 fiches" />
      <NcGrammarIndex skipSel rows={NC_CONCEPTS.filter((c) => c.due || c.state === 'fragile').concat(NC_CONCEPTS[5]).slice(0, 3)} />
      <NcColophon text="/grammar — mêmes primitives, sans second héros" />
    </NcShell>
  );
}
function PageDirectVocab({ dark = false }) {
  return (
    <NcShell dark={dark} screenLabel="/vocabulary · route directe">
      <NcMasthead slim route="Vocabulaire" xlink="Grammaire" />
      <NcFilingSummary lead="Registre" items={[{ n: 12, label: 'à revoir', tone: 'due' }, { n: 4, label: 'fragiles', tone: 'due' }]} />
      <NcSearch placeholder="Chercher un mot…" />
      <NcChips active={0} chips={[{ l: 'Tous' }, { l: 'À revoir', n: 12 }, { l: 'Fragiles', n: 4 }]} />
      <NcLiveSum text="4 cartes en file · 5 entrées du registre" />
      <NcLedgerHead t="File du jour — à revoir" n="4 cartes" />
      <div className="nc-index">{NC_QUEUE.slice(0, 3).map((w) => <NcWordRow key={w.word} {...w} sel={false} />)}</div>
      <NcColophon text="/vocabulary — mêmes primitives, sans second héros" />
    </NcShell>
  );
}

Object.assign(window, {
  NC_QUEUE, NC_DECK,
  PageVocabLanding, PageWordSheet, PageBiography, PageAtlas, PageLibrary,
  PageDirectGrammar, PageDirectVocab,
});
