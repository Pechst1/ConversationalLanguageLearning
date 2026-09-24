"""WP-84 — part of speech and noun gender for the core lexicon.

Writes ``app/data/lexical/fr_core_pos.json``: one ``{pos, gender?}`` entry per
lemma of ``fr_core_lexicon.json`` that the lexicon itself does not annotate
(WP-S2 annotated 139 nouns). Hand-classified lists below; a lemma in none of
them is a verb when it has an infinitive ending, and the script refuses to
write while anything is left unclassified.

Run: ``venv/bin/python scripts/build_lexicon_pos.py``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEXICON = ROOT / "app" / "data" / "lexical" / "fr_core_lexicon.json"
OUT = ROOT / "app" / "data" / "lexical" / "fr_core_pos.json"

NOUNS_M = """
jour mois an matin midi soir temps moment homme garçon père monsieur nom âge train bus métro argent euro prix
légume fruit repas déjeuner dîner mot français anglais vêtement pantalon soleil médecin cadeau monde pays ticket
menu client boulanger caissier accord après-midi rendez-vous numéro bruit goût pied œil cheveu bras cœur dos ventre
nez couteau bagage lundi mardi mercredi jeudi vendredi samedi dimanche janvier février mars avril mai juin juillet
août septembre octobre novembre décembre quart parent papa mari fils bébé copain grand-père grand-parent oncle
prénom cours exercice cahier crayon petit-déjeuner jus poulet côté printemps été automne hiver nuage vent ciel bain
centre village animal visage corps pull sport football jeu internet exemple besoin début entretien contrat papier
document formulaire ascenseur escalier étage grenier balcon chauffage loyer impôt salaire congé stage patron métier
rhume médicament infirmier accident transport retard quai arrêt trajet avion séjour hébergement ingrédient sel poivre
plat dessert pourboire sentiment espoir souvenir caractère amour conflit avantage inconvénient réfrigérateur fauteuil
couloir meuble mur pont coin chemin lac nord sud ouest cou genou doigt gant loisir dessin magazine ballon yaourt
jambon degré orage passeport visa voyageur passager tourisme vol départ tram camion embouteillage carrefour feu
permis garage port paysage camping courrier courriel logement studio mètre rez-de-chaussée sol four ménage
déménagement habitant vendeur solde chèque centime produit paquet kilo gramme litre morceau panier coiffeur raisin
bœuf cuisinier chef sang fond bout tour coup silence lieu minuit étranger portable frigo taxi bateau oiseau cheval
foot ski piano dictionnaire air plan tennis emploi chômage chômeur candidat employé employeur directeur ingénieur
avocat policier agriculteur ouvrier commerçant musicien acteur chanteur écrivain facteur informaticien technicien
retraité atelier écran clavier fichier site réseau lien collège lycée vocabulaire sujet bonheur ennui plaisir cri
rêve courage hasard souci mensonge secret couple mariage divorce adolescent roi programme poème auteur titre
spectateur art festival événement effet genre type reste nombre chiffre ordre choix effort succès échec progrès
niveau cas service intérêt sens point compte passé avenir futur présent siècle retour milieu lendemain conseil
danger château petit-fils beau-père neveu docteur pharmacien comprimé vaccin stress poids sommeil repos pompier
justificatif recours litige délai engagement enjeu obstacle défi développement citoyen droit règlement environnement
déchet climat diplôme apprentissage résultat argument débat point-de-vue avis reproche compliment malentendu
reportage témoignage témoin scandale sondage abonnement dialogue échange compromis désaccord aspect thème fait
doute principe respect risque bénéfice profit coût budget crédit emprunt revenu consommateur commerce secteur
fournisseur cadre salarié syndicat recrutement licenciement outil défaut talent expert professionnel certificat
original virement tarif taux montant remboursement tribunal juge procès crime individu bénévolat racisme état
gouvernement ministre président maire député parti vote soldat quotidien enseignement système établissement contact
instant gardien cabinet artisan rapport objectif logiciel tort hôte époux lecteur total but guichet siège autocar
trottoir piéton colis rayon distributeur horaire timbre toit tapis code haricot champignon porc bonbon bol lapin
mouton cochon réchauffement incendie recyclage tri emballage plastique carton gaspillage pétrole gaz charbon panneau
carburant carbone océan territoire désert chercheur laboratoire robot appareil virus traitement symptôme handicap
tabac alcool décès chirurgien soin pourcentage investissement capital patrimoine héritage esprit honneur isolement
désespoir enthousiasme attachement destin sort comportement style impact processus mécanisme fonctionnement contenu
élément critère concept désordre équilibre contraste volume espace univers geste poète personnage héros récit
narrateur drame réalisateur peintre monument accès abus manque domaine contexte commentaire malaise rythme
divertissement accent langage voisinage centre-ville chantier bâtiment os front insecte volet wagon brouillard
plafond rideau placard tiroir ail saumon miel sirop estomac souhait malheur choc désir chapitre regard raisonnement
auditeur téléspectateur animateur présentateur média immigré réfugié
"""

NOUNS_F = """
semaine année heure minute nuit fois femme fille famille mère madame maison salle addition bière chose réponse
langue chaussure pluie place vie soif faim odeur couleur taille main tête jambe bouche oreille bouteille cuillère
fourchette serviette nappe monnaie caisse queue file maman grand-mère tante nationalité profession classe leçon page
phrase journée toilette saison météo neige douche télévision pièce mer montagne campagne fleur dent jupe chemise
lunette course frite pâte terre université chance raison fin moitié suite facture adresse cave terrasse électricité
agence assurance équipe entreprise société carrière expérience santé douleur fièvre grippe ordonnance urgence
correspondance grève voie douane frontière auberge recette huile entrée boisson commande humeur colère peur joie
surprise honte fierté habitude personnalité relation amitié dispute solution différence ressemblance armoire
rivière forêt épaule chaussette danse invitation vidéo température chaleur mademoiselle dame location réservation
arrivée visite moto autoroute essence panne île vue tente enveloppe boîte vaisselle poubelle pointure promotion
réduction boutique marque qualité douzaine liste épicerie boucherie pâtisserie pêche cerise sauce crème omelette
nourriture peau gorge vache souris matinée soirée lumière date station route nature sortie erreur télé candidature
annonce offre motivation retraite usine imprimante application matière mathématique géographie science physique
grammaire note tristesse envie confiance passion vérité faute nouvelle naissance enfance jeunesse rencontre bise
mort reine information chaîne publicité bande peinture culture tradition occasion façon manière sorte partie part
règle décision situation possibilité aide attention affaire force voix époque veille identité image petite-fille
belle-mère nièce maladie blessure toux allergie fatigue forme ambulance opération démarche procédure administration
attestation demande réclamation plainte échéance contrainte opportunité perspective tendance évolution croissance
crise réforme mesure politique liberté égalité justice loi pollution énergie ressource formation compétence
connaissance recherche étude enquête conclusion hypothèse opinion critique émotion actualité presse source rumeur
polémique statistique donnée publication discussion négociation position pensée réflexion logique preuve réalité
impression certitude valeur morale tolérance solidarité responsabilité obligation interdiction autorisation
permission norme limite menace sécurité protection prévention précaution recommandation suggestion proposition
attente exigence priorité importance dépense économie finance dette épargne consommation concurrence industrie
production clientèle gestion direction manifestation revendication démission réussite ambition stratégie méthode
capacité formalité préfecture déclaration inscription signature copie case somme taxe amende allocation victime
prison sanction population communauté association inégalité pauvreté richesse intégration immigration
discrimination démocratie république élection nation union guerre paix armée violence coutume religion origine
éducation structure organisation institution communication excursion étape mission tâche peine quantité condition
circulation vitesse destination réception machine tranche saucisse carafe poule planète sécheresse inondation
tempête catastrophe canicule atmosphère biodiversité agriculture écologie transition survie disparition plante
découverte invention technologie innovation intelligence connexion médecine guérison épidémie infection dépression
drogue hygiène espérance clinique inflation hausse baisse augmentation diminution moyenne majorité minorité
mondialisation exportation importation bourse fortune propriété conscience mémoire imagination créativité
curiosité sagesse patience méfiance culpabilité dignité générosité gentillesse politesse injustice nostalgie
solitude angoisse anxiété admiration gratitude reconnaissance empathie sympathie affection tendresse rupture
séparation réconciliation illusion existence attitude réaction volonté célébrité réputation apparence beauté
influence conséquence base caractéristique signification définition notion théorie exception harmonie comparaison
proportion durée période phase civilisation humanité ombre littérature œuvre héroïne intrigue scène comédie
tragédie galerie architecture cathédrale création inspiration absence présence vision initiative remarque nuance
hésitation confusion tension pression charge routine détente distraction lecture écriture traduction
interprétation expression prononciation orthographe banlieue colocation construction poitrine joue espèce côte
étagère lessive prise casserole poêle inquiétude larme poésie rédaction rubrique conviction croyance lèvre
"""

#: Epicene nouns: one form, both genders (un/une élève). No single article.
NOUNS_MF = """
gens élève locataire dentiste touriste secrétaire architecte journaliste artiste adulte spécialiste bénévole
fonctionnaire comptable fleuriste colocataire
"""

#: Plural-only / always plural in use, with their gender.
PLURAL_F = "vacances"

ADJECTIVES = """
premier deuxième dernier prochain bonne petit grand bon mauvais beau joli nouveau vieux jeune gros long court chaud
froid cher gratuit facile difficile content heureux triste fatigué malade prêt libre occupé ouvert fermé plein vide
propre sale blanc noir rouge bleu vert jaune gentil sympa désolé possible important demi rose gris marron violet
brun allemand espagnol italien américain canadien belge suisse chinois japonais portugais russe marocain gauche
droite super vrai enchanté blond fort simple sympathique intelligent intéressant seul marié célibataire haut bas
différent clair foncé inquiet nerveux calme timide bavard sérieux drôle poli impoli aimable généreux égoïste
patient rapide lent bruyant silencieux confortable pratique utile inutile bizarre étrange typique habituel rare
fréquent récent ancien moderne nuageux ensoleillé mince génial faux européen postal végétarien large étroit lourd
léger sec mouillé salé sucré disponible complet direct proche touristique international national local privé
public moyen rond tranquille dangereux sûr prudent pressé impossible compliqué juste parfait sportif doux agréable
excellent frais délicieux fâché jaloux amoureux fier curieux courageux paresseux travailleur gourmand honnête
sincère sensible méchant mignon charmant ennuyeux passionnant incroyable extraordinaire formidable magnifique
terrible horrible merveilleux fantastique énervé stressé bête idiot impatient joyeux malheureux fou riche pauvre
certain enrhumé enceinte vivant grave émouvant bouleversé stupéfait déçu satisfait soulagé agacé méfiant confiant
conscient responsable capable incapable efficace pertinent cohérent contradictoire nuancé approfondi essentiel
principal nécessaire indispensable évident probable exact correct injuste absurde ridicule choquant scandaleux
inacceptable acceptable positif négatif personnel individuel collectif général particulier précis concret abstrait
complexe convaincant étonnant surprenant remarquable exceptionnel considérable énorme immense majeur mineur actuel
contemporain traditionnel classique unique commun courant social économique culturel financier familial médical
scientifique technique technologique numérique virtuel officiel légal illégal obligatoire facultatif coupable
innocent fiable crédible fidèle tolérant indépendant autonome ambitieux compétent central naturel doué ravi
optimiste pessimiste raisonnable tel bancaire double férié nucléaire renouvelable solaire éolien biologique
écologique durable artificiel handicapé mondial régional urbain rural global commercial industriel agricole mental
moral psychologique fragile solide stable progressif brutal profond superficiel vaste suffisant insuffisant excessif
modéré extrême radical absolu relatif réel potentiel éventuel précédent final initial secondaire fondamental
décisif urgent sévère strict exigeant attentif digne honteux humble modeste arrogant solitaire sociable discret
violent pacifique agressif tendre cruel équitable égal inégal divers varié multiple semblable similaire identique
pareil distinct opposé inverse ambigu confus net mystérieux inquiétant rassurant effrayant touchant fascinant
banal ordinaire régulier permanent temporaire provisoire définitif chimique toxique anxieux reconnaissant bilingue
interne externe mutuel artistique littéraire historique géographique religieux démocratique tiède mûr carré
sombre lumineux pluvieux meublé élégant affreux têtu sage subjectif neutre
"""

ADVERBS = """
très bien mal aussi alors encore déjà toujours souvent parfois peu trop assez beaucoup moins autant presque plutôt
vraiment surtout comme puis ensuite enfin d'abord aujourd'hui hier demain maintenant bientôt tard tôt vite
doucement ensemble seulement environ ne pas plus jamais rien y en là ici loin près là-bas longtemps dehors
ailleurs partout franchement heureusement malheureusement peut-être sûrement certainement évidemment d'accord bref
auparavant au-dessus dessus dedans autour debout lentement rapidement finalement récemment quelquefois rarement
normalement tellement exactement simplement facilement complètement volontiers ainsi également néanmoins toutefois
d'ailleurs en-effet par-conséquent notamment désormais aussitôt dorénavant éventuellement certes voire au-delà
apparemment effectivement forcément probablement totalement entièrement parfaitement largement globalement
essentiellement principalement particulièrement précisément justement réellement sincèrement honnêtement
personnellement concrètement actuellement autrement davantage dessous soudain autrefois immédiatement généralement
tant absolument premièrement dernièrement prochainement progressivement brusquement constamment régulièrement
fréquemment clairement nettement fortement légèrement relativement extrêmement énormément suffisamment directement
difficilement c'est-à-dire
"""

#: Articles, pronouns, determiners, prepositions, conjunctions — the grammar's words.
FUNCTION = """
le la les un une des de du à au aux et ou mais donc car ni or non si je tu il elle on nous vous ils elles me te se
moi toi lui eux soi mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs ce cet cette ces ça cela ceci
celui celle ceux celles que qui quoi dont où quand comment pourquoi combien quel quelle quels quelles dans sur
sous avec sans pour par chez entre vers contre depuis pendant avant après jusque dès selon malgré parmi devant
derrière voilà voici tout tous toute toutes autre autres même chaque quelque quelques plusieurs personne aucun
quelqu'un s'il parce pourtant cependant tandis lorsque puisque afin quoique nulle sauf grâce cause celui-là
chacun mien tien sien nôtre vôtre revanche contraire outre quant lors auprès envers hors durant travers
vis-à-vis sinon
"""

INTERJECTIONS = """
oui bonjour bonsoir salut merci pardon excusez excusez-moi revoir bienvenue hélas
"""

NUMBERS = """
deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt trente quarante cinquante
soixante cent mille zéro troisième quatrième cinquième sixième septième huitième neuvième dixième million centaine
milliard dizaine
"""

#: Verb forms the infinitive-ending rule cannot see.
VERBS_EXTRA = "rendre-visite"

_INFINITIVE = re.compile(r"(er|ir|re|oir|ïr)$")


def _words(block: str) -> list[str]:
    return [word for word in block.split() if word]


def build() -> dict[str, dict[str, str]]:
    lexicon = json.loads(LEXICON.read_text(encoding="utf-8"))["lemmas"]
    table: dict[str, dict[str, str]] = {}
    for word in _words(NOUNS_M):
        table[word] = {"pos": "noun", "gender": "m"}
    for word in _words(NOUNS_F) + _words(PLURAL_F):
        table[word] = {"pos": "noun", "gender": "f"}
    for word in _words(NOUNS_MF):
        table[word] = {"pos": "noun", "gender": "mf"}
    for block, pos in (
        (ADJECTIVES, "adjective"),
        (ADVERBS, "adverb"),
        (FUNCTION, "function"),
        (INTERJECTIONS, "interjection"),
        (NUMBERS, "number"),
        (VERBS_EXTRA, "verb"),
    ):
        for word in _words(block):
            table.setdefault(word, {"pos": pos})
    out: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for lemma, entry in lexicon.items():
        if entry.get("pos"):
            continue
        if lemma in table:
            out[lemma] = table[lemma]
        elif "-" in lemma and all((part in table and table[part]["pos"] == "number") or part in {"et", "un", "cents", "vingts"} for part in lemma.split("-")):
            out[lemma] = {"pos": "number"}
        elif _INFINITIVE.search(lemma):
            out[lemma] = {"pos": "verb"}
        else:
            missing.append(lemma)
    unknown = sorted(set(table) - set(lexicon))
    if missing:
        raise SystemExit(f"unclassified: {missing}")
    if unknown:
        print(f"note: {len(unknown)} listed words are not in the lexicon: {unknown[:20]}")
    return out


def main() -> None:
    out = build()
    payload = {
        "version": "fr-core-pos-v1",
        "provenance": (
            "WP-84 (2026-09-24): part of speech and noun gender for every core-lexicon lemma the lexicon "
            "does not annotate itself, hand-classified in scripts/build_lexicon_pos.py (verbs by their "
            "infinitive ending once every noun, adjective, adverb and function word is listed). "
            "gender: m / f / mf (epicene: one form for both)."
        ),
        "lemmas": dict(sorted(out.items())),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for entry in out.values():
        counts[entry["pos"]] = counts.get(entry["pos"], 0) + 1
    print(f"wrote {len(out)} lemmas: {counts}")


if __name__ == "__main__":
    main()
