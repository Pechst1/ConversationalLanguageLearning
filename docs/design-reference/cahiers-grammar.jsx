/* Atelier — LES CAHIERS · grammar screens + system states.
   Data honesty: every count/date shown is derivable from the grammar list/detail
   contract (see Données → props board). */

const NC_CONCEPTS = [
  { no: 1, title: 'Le genre et le nombre', level: 'A1', cat: 'Accords', mastery: 8, state: 'solid', stateLabel: 'Solide' },
  { no: 2, title: 'Les articles définis : le, la, l’, les', level: 'A1', cat: 'Articles', mastery: 6, state: 'building', stateLabel: 'En cours', due: true, errata: 2, sel: true },
  { no: 3, title: 'Les articles indéfinis : un, une, des', level: 'A1', cat: 'Articles', mastery: 7, state: 'solid', stateLabel: 'Solide' },
  { no: 4, title: 'Le partitif : du, de la, de l’', level: 'A2', cat: 'Articles', mastery: 3, state: 'fragile', stateLabel: 'Fragile', errata: 1 },
  { no: 5, title: 'Les possessifs : mon, ma, mes', level: 'A1', cat: 'Déterminants', mastery: 9, state: 'mastered', stateLabel: 'Acquis' },
  { no: 6, title: 'Le passé composé avec avoir', level: 'A2', cat: 'Temps', mastery: 4, state: 'building', stateLabel: 'En cours' },
  { no: 7, title: 'La négation : ne … pas', level: 'A1', cat: 'Syntaxe', mastery: 0, state: 'new', stateLabel: 'Nouveau' },
];

function NcGrammarIndex({ skipSel = false, rows = NC_CONCEPTS }) {
  return (
    <div className="nc-index" role="list">
      {rows.map((c) => <NcIndexRow key={c.no} {...c} sel={!skipSel && c.sel} />)}
    </div>
  );
}

/* ---------- View 1 · Notebook landing, grammar active ---------- */
function PageNotebookGrammar({ dark = false, motion = true, feuilleton = true, library = true, wide = false, big = false }) {
  return (
    <NcShell dark={dark} motion={motion} wide={wide} big={big} screenLabel={'Carnet · grammaire' + (dark ? ' · sombre' : '')}>
      <NcMasthead cefr="A2.1 en cours" />
      {feuilleton && <NcFeuilleFile ep={14} title="La lettre de Lyon" />}
      <NcModeTabs active="grammaire" library={library} metas={{ grammaire: '54 fiches', vocabulaire: '12 à revoir', bibliotheque: '2 volumes' }} />
      <NcFilingSummary lead="Classement" items={[{ n: 54, label: 'fiches' }, { n: 3, label: 'à revoir', tone: 'due' }, { n: 5, label: 'errata récents', tone: 'era' }]} />
      <NcSearch placeholder="Chercher une règle…" />
      <NcChips active={0} chips={[{ l: 'Toutes', n: 54 }, { l: 'À revoir', n: 3 }, { l: 'A1' }, { l: 'A2' }, { l: 'B1' }]} />
      <NcLiveSum text="54 fiches dans ce classement" />
      <NcLedgerHead t="Index des règles" n="Nº 1 – 7 de 54" />
      <NcGrammarIndex />
      <NcColophon />
    </NcShell>
  );
}

/* ---------- View 2 · Grammar entry detail ---------- */
function PageGrammarEntry({ dark = false, motion = true, notesMode = 'idle', notesText = 'Penser à « l’ » devant voyelle — comme « l’ami ».', big = false }) {
  return (
    <NcShell dark={dark} motion={motion} big={big} screenLabel={'Fiche de grammaire' + (dark ? ' · sombre' : '')}>
      <button className="nc-crumb"><NcIcoBack /> Index des règles · <b>Fiche Nº 02</b></button>
      <header className="nc-entryhead">
        <div className="tags">
          <span className="nc-tagchip lvl"><i></i>A1</span>
          <span className="nc-tagchip cat"><i></i>Articles</span>
          <NcDueMark />
        </div>
        <h2>Les articles définis : le, la, l’, les</h2>
        <div className="row2">
          <span className="bigpips" aria-label="Maîtrise 6 sur 10">{Array.from({ length: 10 }, (_, i) => <i key={i} className={i < 6 ? 'on' : ''}></i>)}</span>
          <span>En cours</span>
          <span className="nxt">Prochaine révision · demain</span>
        </div>
      </header>
      <NcSec kick="La règle" tone="">
        <p className="nc-rulebox">L’article défini s’accorde en genre et en nombre ; devant voyelle ou h muet, « le » et « la » deviennent « l’ ».</p>
      </NcSec>
      <NcSec kick="Exemples d’ancrage" tone="blue" ct="3 fiches">
        <NcExample fr="<b>Le</b> journal paraît chaque matin." de="Die Zeitung erscheint jeden Morgen." />
        <NcExample fr="<b>L’</b>encre sèche vite sur ce papier." de="Die Tinte trocknet schnell auf diesem Papier." />
        <NcExample fr="<b>Les</b> épreuves attendent au marbre." de="Die Druckfahnen warten auf dem Satztisch." />
      </NcSec>
      <NcSec kick="Pièges principaux" tone="" ct="2 relevés">
        <div className="nc-trap"><i></i><span>« Le » ne s’élide jamais devant h aspiré : <em>le héros</em>, pas <em>l’héros</em>.</span></div>
        <div className="nc-trap"><i></i><span>L’allemand ne contracte pas : <em>de + le → du</em> n’a pas d’équivalent direct.</span></div>
      </NcSec>
      <NcSec kick="Motif" tone="mut">
        <div className="nc-motif">
          le / la (+ voyelle → l’) + nom&nbsp;&nbsp;·&nbsp;&nbsp;les + pluriel
          <div className="bp"><span>Gabarit d’exercice</span><b>Vérifié · qualité 4/5</b></div>
        </div>
      </NcSec>
      <NcSec kick="Errata — à revoir" tone="" ct="2 dus">
        <NcErrRow q="« J’ai lu <s>le</s> annonce » → <b>l’annonce</b>" d="D’hier" />
        <NcErrRow q="« <s>La</s> hiver est long » → <b>l’hiver</b>" d="Il y a 3 j" />
      </NcSec>
      <NcSec kick="Errata récents" tone="mut" ct="1 réparé">
        <NcErrRow recent q="« <s>le</s> équipe » → <b>l’équipe</b> — réparé à l’Épreuve" d="Lundi" />
      </NcSec>
      <NcSec kick="Notes en marge" tone="blue">
        <NcMarginNotes mode={notesMode} text={notesText} />
      </NcSec>
      <a className="nc-cta" href="#">Composer à l’Atelier <NcIcoArrow /></a>
      <div className="nc-exercisetags"><span>élision</span><span>article + nom</span><span>dictée courte</span></div>
      <NcColophon />
    </NcShell>
  );
}

/* ---------- Notes en marge · the four states ---------- */
function PageNotesStates({ dark = false }) {
  const Cap = ({ t }) => <div style={{ margin: '16px 0 6px', fontSize: 9, fontWeight: 900, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--app-ink-3)' }}>{t}</div>;
  return (
    <NcShell dark={dark} screenLabel="Notes en marge · états">
      <NcMasthead slim route="Notes en marge" />
      <Cap t="1 · Repos — vide" />
      <NcMarginNotes mode="idle" text="" />
      <Cap t="2 · Édition — non enregistrée" />
      <NcMarginNotes mode="editing" text="Penser à « l’ » devant voyelle — comme « l’ami »." dirty />
      <Cap t="3 · Classement en cours" />
      <NcMarginNotes mode="saving" text="Penser à « l’ » devant voyelle — comme « l’ami »." />
      <Cap t="4 · Échec — la note reste dans la marge" />
      <NcMarginNotes mode="error" text="Penser à « l’ » devant voyelle — comme « l’ami »." />
    </NcShell>
  );
}

/* ---------- System states ---------- */
function PageLoading({ dark = false, motion = true }) {
  return (
    <NcShell dark={dark} motion={motion} screenLabel="Chargement · classement en cours">
      <NcMasthead cefr="A2.1 en cours" />
      <NcModeTabs active="grammaire" metas={{ grammaire: 'Classement…', vocabulaire: 'Registre des mots' }} />
      <div className="nc-filing"><span className="k">Classement en cours</span><span className="sep"></span><span>Le bureau des archives ouvre vos fiches</span></div>
      <NcSkeleton rows={6} />
    </NcShell>
  );
}

function PageEmptyStates({ dark = false }) {
  return (
    <NcShell dark={dark} screenLabel="États vides">
      <NcMasthead cefr="A2.1 en cours" />
      <NcModeTabs active="grammaire" library={false} metas={{ grammaire: '54 fiches', vocabulaire: '12 à revoir' }} />
      <NcSearch placeholder="Chercher une règle…" />
      <NcChips active={4} chips={[{ l: 'Toutes', n: 54 }, { l: 'À revoir', n: 3 }, { l: 'A1' }, { l: 'A2' }, { l: 'B1', n: 0 }]} />
      <NcLiveSum text="0 fiche en B1" clearable />
      <NcEmpty body="Aucune règle B1 n’est encore classée. Le classement s’ouvre à mesure que le cours avance." action="Effacer les filtres" />
      <NcLedgerHead t="Premier passage" tone="mut" />
      <NcEmpty title="Le cahier s’ouvre à la première séance" body="Vos fiches de grammaire se classent ici dès que l’Atelier compose votre première page." action="Ouvrir l’Atelier" />
      <NcColophon text="Sans Feuilleton en cours, le dossier du haut disparaît — rien ne le remplace" />
    </NcShell>
  );
}

function PageErrorPartial({ dark = false }) {
  return (
    <NcShell dark={dark} screenLabel="Erreur & données partielles">
      <NcMasthead cefr={null} />
      <NcModeTabs active="grammaire" metas={{ grammaire: '54 fiches', vocabulaire: 'Registre des mots' }} />
      <div className="nc-filing"><span className="k">Donnée partielle</span><span className="sep"></span><span>La progression du cours est indisponible — l’index, lui, fonctionne</span></div>
      <NcLedgerHead t="Index des règles" n="Nº 1 – 3 de 54" />
      <NcGrammarIndex skipSel rows={NC_CONCEPTS.slice(0, 3)} />
      <NcLedgerHead t="Échec de chargement" tone="mut" />
      <NcNotice message="L’index des règles n’a pas pu être ouvert. Vos fiches sont en sûreté au bureau des archives." />
      <NcNotice tone="blue" label="Avis du bureau des archives" message="Le registre des mots ne répond pas. La grammaire reste consultable." />
    </NcShell>
  );
}

/* ---------- a11y · focus, reduced motion, long strings ---------- */
function PageA11y({ dark = false }) {
  const Cap = ({ t }) => <div style={{ margin: '16px 0 6px', fontSize: 9, fontWeight: 900, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--app-ink-3)' }}>{t}</div>;
  return (
    <NcShell dark={dark} motion={false} screenLabel="Accessibilité">
      <NcMasthead slim route="Accessibilité" />
      <Cap t="Focus visible — anneau encre + halo jaune (globals.css)" />
      <button className="nc-chip demo-focus" aria-pressed="true">À revoir<span className="n">3</span></button>
      <Cap t="Chaînes longues — FR/DE, jamais tronquées, retour à la ligne" />
      <NcIndexRow no={41} title="L’accord du participe passé avec l’auxiliaire être et les verbes pronominaux" level="B1" cat="Accords du participe" mastery={2} state="fragile" stateLabel="Fragile" errata={1} />
      <NcWordRow rank={3971} word="l’Auseinandersetzung → la confrontation interminable" tr="die Auseinandersetzung, die Aufeinanderfolge von Ereignissen · nom" state="building" stateLabel="En cours" />
      <Cap t="Mouvement réduit — le squelette cesse de battre, rien ne bouge" />
      <NcSkeleton rows={2} file={false} />
      <Cap t="Cibles 44px — chips, lignes, onglets, actions de notes" />
      <p style={{ margin: 0, fontSize: 11, lineHeight: 1.5, color: 'var(--app-ink-2)' }}>Toutes les commandes tiennent la cible de 44 px ; les stamps et marques sont décoratifs (aria-hidden), l’état est porté par le libellé de la ligne.</p>
    </NcShell>
  );
}

Object.assign(window, {
  NC_CONCEPTS, NcGrammarIndex,
  PageNotebookGrammar, PageGrammarEntry, PageNotesStates,
  PageLoading, PageEmptyStates, PageErrorPartial, PageA11y,
});
