/* Atelier — LES CAHIERS · spec boards (reuse .board classes from atelier.css). */

function NcBoard({ k, h, p, children, w = 500 }) {
  return (
    <div className="board" style={{ width: w }}>
      <div className="board-head"><span className="k">{k}</span><h2>{h}</h2>{p && <p>{p}</p>}</div>
      {children}
    </div>
  );
}
function NcSpecRow({ t, children, tokens = [] }) {
  return (
    <div className="kit-row" style={{ gridTemplateColumns: '132px 1fr' }}>
      <div className="kdesc"><div className="kt">{t}</div></div>
      <div className="kdesc">{children}{tokens.length > 0 && <div className="tokens">{tokens.map((x) => <span key={x}>{x}</span>)}</div>}</div>
    </div>
  );
}
const ncP = (txt) => <p style={{ margin: '6px 0 0' }}>{txt}</p>;

/* ---------- 1 · Composants & réemploi ---------- */
function BoardComponents() {
  return (
    <NcBoard k="Spécification" h="Composants — contrats & réemploi" p="Chaque Nc* est un composant React token-only. « Réemploi » nomme la primitive La Une existante à réutiliser telle quelle plutôt qu’à dupliquer.">
      <NcSpecRow t="NcShell" tokens={['.nc', '.nc.dark → jetons', '.nc-page', 'safe-area padding']}>
        {ncP('Cadre du carnet : page + tabs existants (inchangés). Props: mode, theme (hérite data-theme), motion. La barre d’onglets du bas est le chrome courant — aucun redesign.')}
      </NcSpecRow>
      <NcSpecRow t="NcMasthead" tokens={['.nc-mast', '.nc-mast.slim', '.folio .off = absent']}>
        {ncP('Lockup compact « Les Cahiers » + folio CEFR (module coquille). cefr=null → « Progression indisponible » (état absent conçu). slim pour /grammar et /vocabulary : une ligne de rubrique, jamais un second héros.')}
      </NcSpecRow>
      <NcSpecRow t="NcModeTabs" tokens={['role=tablist', 'aria-selected', '.nc-tab min 44px', 'flag → 2 ou 3 onglets']}>
        {ncP('Intercalaires de dossier. Bibliothèque n’existe que si le drapeau de lancement est levé. Meta par onglet = compte honnête dérivé des listes.')}
      </NcSpecRow>
      <NcSpecRow t="NcFilingSummary" tokens={['.nc-filing', 'role=status', '.due .era']}>
        {ncP('Ligne de classement : comptes dérivés (fiches, à revoir, errata récents). Sert aussi l’état partiel (« La progression du cours est indisponible »).')}
      </NcSpecRow>
      <NcSpecRow t="NcIndex / NcIndexRow" tokens={['.nc-row', '.nc-row.sel', '.no .t .meta .marks', 'points de conduite = radial-gradient']}>
        {ncP('Index des règles : numéro, titre serif, niveau · catégorie, pips de maîtrise (mastery/10), marques à droite. sel = concept de la query (?concept=).')}
      </NcSpecRow>
      <NcSpecRow t="NcDueMark / NcStateStamp" tokens={['.nc-due', '.nc-stamp.{building,fragile,solid,mastered}']}>
        {ncP('À revoir prime sur l’état ; une seule marque forte par ligne. Libellés = state_label localisé, jamais recalculés côté client.')}
        {ncP('Réemploi : même langage que lu-stamp / lu-tag, réduit au corps 8 px du registre.')}
      </NcSpecRow>
      <NcSpecRow t="NcEntry (fiche)" tokens={['.nc-entryhead', '.nc-sec', '.nc-rulebox', '.nc-motif', '.nc-errow']}>
        {ncP('Sections dans l’ordre du contrat : règle, exemples d’ancrage (FR serif + DE), pièges, motif (mono + statut du gabarit), errata dus puis récents, notes, CTA Atelier avec exercise_tags.')}
      </NcSpecRow>
      <NcSpecRow t="NcMarginNotes" tokens={['.nc-notes', '.editing .saving .err', 'textarea ≥84px', 'états: repos·édition·envoi·échec']}>
        {ncP('personal_notes éditables, persistées. L’échec garde le texte local et affiche l’avis avec Retry — la note ne se perd jamais.')}
      </NcSpecRow>
      <NcSpecRow t="NcWordRow / NcWordEntry" tokens={['.nc-wordrow', '.nc-sheet', '.nc-metagrid', '.nc-fragnote', '.nc-ratings']}>
        {ncP('Registre : rang #, mot serif, traduction · catégorie, état de la carte de maîtrise. Fiche de mot = feuille basse accessible (role=dialog, focus piégé) : héros, méta, raison de fragilité, notation, actions semées.')}
        {ncP('Réemploi : MobileBottomSheet existant porte la feuille ; FragilityBadge fournit la raison — ne pas dupliquer.')}
      </NcSpecRow>
      <NcSpecRow t="NcBiography" tokens={['.nc-bio .ev', '.first .good .bad']}>
        {ncP('Chronique du mot : origine, progrès, événements datés (API biography). Remplace le contenu de WordBiographySheet, même coquille.')}
      </NcSpecRow>
      <NcSpecRow t="NcAtlasFoldout" tokens={['.nc-fold', '.nc-track', '.nc-map (280 cases)', 'divulgation progressive']}>
        {ncP('Bande pliée dans le flux ; dépliée = couverture CECR / domaines / verbes / structures + carte. Jamais 5 000 cases dans le chemin de lecture par défaut.')}
      </NcSpecRow>
      <NcSpecRow t="NcSkeleton / NcNotice / NcEmpty" tokens={['.nc-skel (fichier + lignes)', '.nc-notice', '.nc-empty']}>
        {ncP('Réemploi direct : NcNotice EST LuNotice (mêmes classes de rôle, libellé « Avis du bureau des archives ») ; NcSkeleton suit lu-skel, en rangées d’index. Un seul composant d’avis pour toute la grappe.')}
      </NcSpecRow>
    </NcBoard>
  );
}

/* ---------- 2 · Jetons & CSS ---------- */
function BoardTokens() {
  const rows = [
    ['--nc-hair', 'color-mix(in oklab, var(--app-ink) 24%, var(--app-paper))', 'filets fins d’index, bordures de rangée'],
    ['--nc-wash', 'color-mix(in oklab, var(--app-paper-2) 70%, var(--app-sheet))', 'lavis du squelette'],
    ['--nc-half', 'color-mix(in oklab, var(--app-ink) 55%, var(--app-paper))', 'encre retirée (états sourds)'],
    ['--nc-fragile', 'color-mix(in oklab, var(--app-red) 45%, var(--app-paper))', 'case fragile de la carte'],
    ['--nc-scrim', 'color-mix(in oklab, var(--app-ink) 45%, transparent)', 'voile de la feuille basse'],
    ['--nc-halo', 'color-mix(in oklab, var(--app-yellow) 45%, transparent)', 'halo de focus (= globals.css)'],
  ];
  return (
    <NcBoard k="Spécification" h="Jetons — --app-* seulement" p="Aucune palette :root, aucun hex, aucun thème épinglé. Les six valeurs dérivées ci-dessous sont les seules ajoutées ; elles suivent le thème automatiquement puisque chaque mélange part d’un jeton.">
      {rows.map(([t, f, u]) => (
        <NcSpecRow key={t} t={t} tokens={[f]}>{ncP(u)}</NcSpecRow>
      ))}
      <NcSpecRow t="Thèmes" tokens={[':root[data-theme=dark]', ':root[data-theme=system] + media', 'color-scheme']}>
        {ncP('Le carnet n’ajoute rien : il hérite les redéfinitions de globals.css. Les blocs .nc/.nc.dark du prototype existent uniquement pour poser clair et sombre côte à côte — ils ne se livrent pas.')}
      </NcSpecRow>
      <NcSpecRow t="Typo" tokens={['var(--app-serif) italique = titres, mots, notes', 'var(--app-grotesk) 800–900 caps .10–.16em = étiquettes', 'mono UI = motif seulement']}>
        {ncP('Deux voix, comme La Une ; la fiche parle serif, l’index étiquette en grotesk.')}
      </NcSpecRow>
      <NcSpecRow t="Mouvement" tokens={['transform / opacity uniquement', 'prefers-reduced-motion → statique', 'squelette: opacity 1.4s']}>
        {ncP('Une seule animation dans la grappe (battement du squelette). Rien ne défile, rien ne rebondit.')}
      </NcSpecRow>
    </NcBoard>
  );
}

/* ---------- 3 · Copy deck ---------- */
function BoardCopy() {
  const S = ({ g, rows }) => (
    <div className="kit-row" style={{ gridTemplateColumns: '110px 1fr' }}>
      <div className="kdesc"><div className="kt">{g}</div></div>
      <div className="kdesc">
        {rows.map(([a, b]) => (
          <p key={a} style={{ margin: '5px 0 0', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <b style={{ fontWeight: 800 }}>{a}</b><span style={{ color: 'var(--ink-2)' }}>{b}</span>
          </p>
        ))}
      </div>
    </div>
  );
  return (
    <NcBoard k="Copy deck" h="Toutes les chaînes visibles" p="Français dans la publication ; l’anglais ne subsiste que pour le chrome d’action existant (Retry, notation Anki). Jamais deux langues sur une même ligne.">
      <S g="Coquille" rows={[
        ['LES CAHIERS', 'badge d’oreille + nom de section'],
        ['Référence de l’édition', 'folio, gauche'],
        ['Cours · A2.1 en cours', 'folio, module CEFR présent'],
        ['Progression indisponible', 'folio, module CEFR absent'],
        ['Grammaire · Vocabulaire · Bibliothèque', 'onglets de mode'],
        ['Le Feuilleton · classé au dossier / Reprendre →', 'dossier optionnel'],
      ]} />
      <S g="Grammaire" rows={[
        ['Index des règles', 'tête du registre'],
        ['Chercher une règle…', 'placeholder recherche'],
        ['À revoir', 'marque d’échéance'],
        ['Nouveau · En cours · Fragile · Solide · Acquis', 'timbres d’état (= state_label)'],
        ['La règle / Exemples d’ancrage / Pièges principaux / Motif', 'sections de fiche'],
        ['Errata — à revoir / Errata récents', 'sections errata'],
        ['Notes en marge', 'notes personnelles'],
        ['Composer à l’Atelier', 'CTA de fiche'],
      ]} />
      <S g="Notes" rows={[
        ['Aucune note pour l’instant — la marge vous attend.', 'vide'],
        ['Annoter / Modifier / Enregistrer / Annuler', 'actions'],
        ['Non enregistrée / Classement en cours / Enregistrée', 'états'],
        ['Échec — note conservée ici', 'erreur (+ avis Retry)'],
      ]} />
      <S g="Vocabulaire" rows={[
        ['Registre des mots — Français 5000', 'tête du registre'],
        ['Chercher un mot…', 'placeholder recherche'],
        ['File du jour — à revoir', 'tête de file'],
        ['À prendre ensuite', 'prochain lot utile'],
        ['Fil fragile', 'raison de fragilité'],
        ['Atlas des acquis / Déplier / Replier', 'divulgation'],
        ['Dossier de la semaine', 'résumé hebdomadaire'],
        ['Biographie du mot / Semer en mission / Lire au feuilleton', 'actions semées'],
        ['Again · Hard · Good · Easy', 'notation — chrome anglais existant, conservé'],
      ]} />
      <S g="Système" rows={[
        ['Classement en cours', 'chargement'],
        ['Aucune fiche dans ce classement', 'vide (filtre)'],
        ['Le cahier s’ouvre à la première séance', 'premier usage'],
        ['Avis du bureau des archives', 'étiquette d’erreur'],
        ['Retry', 'action — chrome anglais existant'],
        ['Effacer les filtres', 'sortie du vide filtré'],
      ]} />
    </NcBoard>
  );
}

/* ---------- 4 · Données → props ---------- */
function BoardData() {
  return (
    <NcBoard k="Contrat de données" h="Données → props" p="Rien d’inventé : chaque texte visible remonte à un champ. L’optionnel disparaît ou reçoit son état « indisponible » dessiné.">
      <NcSpecRow t="Coquille" tokens={['CEFR progress → folio', 'feuilleton payload → NcFeuilleFile', 'launch flag → onglet Bibliothèque', 'route/query → mode + sel']}>
        {ncP('Sans payload Feuilleton : le module disparaît (aucun remplissage). Sans CEFR : « Progression indisponible ».')}
      </NcSpecRow>
      <NcSpecRow t="NcIndexRow" tokens={['display_title → t', 'level+localized category → meta', 'mastery → pips /10', 'state_label → NcStateStamp', 'next_review ≤ ajourd’hui → NcDueMark', 'due_errata_count → nc-errdot']}>
        {ncP('Le compte du classement (« 54 fiches · 3 à revoir ») est dérivé de la liste reçue, jamais d’un champ séparé.')}
      </NcSpecRow>
      <NcSpecRow t="NcEntry" tokens={['core_rule → rulebox', 'anchor_examples → NcExample[]', 'main_traps → nc-trap[]', 'motif + blueprint_status/quality → nc-motif', 'due_errata / recent_errata → NcErrRow[]', 'personal_notes → NcMarginNotes', 'exercise_tags → nc-exercisetags + CTA']}>
        {ncP('description/examples nourrissent la fiche longue ; les sections sans données se replient (pas de section vide).')}
      </NcSpecRow>
      <NcSpecRow t="File & registre" tokens={['due-context: word, translation, bucket, proficiency, due/fragility reason', 'deck: word, translation, part_of_speech, frequency_rank, difficulty', 'mastery-map cell → nc-bucket d’état']}>
        {ncP('File = cartes du jour (bucket) ; registre = Français 5000 par rang. Deux têtes distinctes, jamais mélangées.')}
      </NcSpecRow>
      <NcSpecRow t="NcWordEntry" tokens={['word/translation → héros', 'frequency_rank / pos / difficulty → metagrid', 'fragility reason → nc-fragnote', 'review → notation Anki', 'biography → NcBiography', 'actions semées → mission / feuilleton / atelier']}>
        {ncP('La note de fragilité n’apparaît que si la raison existe. Les ratings restent le chrome existant.')}
      </NcSpecRow>
      <NcSpecRow t="Atlas & dossier" tokens={['CEFR bands / category / verb / grammar tracks → NcCoverageTrack', 'next_best_set → À prendre ensuite', 'mastery map cells + state totals → NcMasteryMap', 'weekly dossier: headline, repairs/reviews/seen/used, fragile threads, next actions']}>
        {ncP('L’atlas est plié par défaut ; les totaux d’états viennent du résumé de la carte, pas d’un recomptage.')}
      </NcSpecRow>
    </NcBoard>
  );
}

/* ---------- 5 · Migration ---------- */
function BoardMigration() {
  return (
    <NcBoard k="Note de migration" h="pages/notebook · grammar · vocabulary" p="Toutes les capacités et contrats route/query existants sont préservés ; seul le markup de présentation change.">
      <NcSpecRow t="notebook.tsx" tokens={['?mode=grammar|vocabulary conservé', '?concept / ?review / ?word conservés', 'localStorage NOTEBOOK_MODE_STORAGE_KEY conservé']}>
        {ncP('notebook-shell-title + notebook-shell-eyebrow → NcMasthead (le style jsx local à --paper disparaît : jetons globaux). NotebookModeSwitch garde sa logique de capture de clic ; sa peau devient NcModeTabs (3ᵉ onglet derrière le drapeau).')}
      </NcSpecRow>
      <NcSpecRow t="grammar.tsx" tokens={['GrammarNotebookSurface embedded conservé', 'liste → NcIndex/NcIndexRow', 'détail → NcEntry + NcMarginNotes']}>
        {ncP('Les chips MASTERY/STATE/NEXT REVIEW empilés du détail actuel deviennent la ligne row2 de NcEntryHead ; RULE/WHEN/PATTERN/CONTRAST se rangent sous les têtes françaises du copy deck.')}
      </NcSpecRow>
      <NcSpecRow t="vocabulary.tsx" tokens={['vocab-hero → supprimé en embarqué (un seul héros)', 'vocab-row queue/deck → NcWordRow', 'vocab-map / legend → NcAtlasFoldout (plié)', 'vocab-weekly-dossier → NcDossier', 'MobileBottomSheet + FragilityBadge + WordBiographySheet réutilisés']}>
        {ncP('La carte de maîtrise sort du chemin de lecture : elle se replie dans l’Atlas. Les filtres et le résumé aria-live gardent leur logique ; libellés du copy deck.')}
      </NcSpecRow>
      <NcSpecRow t="À supprimer" tokens={['styles jsx locaux redéclarant --paper/--ink', 'vocab-flashcard (remplacé par la fiche + notation)', 'double héros notebook + vocab']}>
        {ncP('Aucune primitive nouvelle là où La Une en a déjà une : avis, squelette, timbres, chips — un seul jeu, importé.')}
      </NcSpecRow>
    </NcBoard>
  );
}

Object.assign(window, { BoardComponents, BoardTokens, BoardCopy, BoardData, BoardMigration });
