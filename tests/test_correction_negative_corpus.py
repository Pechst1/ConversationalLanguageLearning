"""#250: correct French a careless rule would mark wrong. The guard is zero edits.

Three night attempts at the model-free pass (#259, #274, #310) were each rejected for the
same thing: a new rule told a learner that correct French was wrong, and the learner copies
the fix and is drilled on it. ``tests/test_correction_corpus.py`` measures the rules on the
French the app publishes, but the app never writes a sentence about vitamin C or a train
that is three hours late. This file holds the sentences that break a rule of that shape:
every correct sentence those reviews named, and for each rule its own lookalikes.

A sentence here is correct French, or a learner citing a word. Nothing in it may be touched.
No model call is made anywhere in this file.
"""

from __future__ import annotations

import pytest

from app.services import correction_contract as cc

#: The correct sentences the three rejected attempts got wrong, word for word.
REJECTED_259 = [
    "Elle a rentré tout le linge avant la pluie.",
    "Elle a sorti cette lettre de sa poche.",
    "Il a monté ce meuble hier.",
    "Elle a sorti de l'argent.",
    "Il a sorti du pain.",
    "Nous avons monté tout le matériel.",
    "Il a retourné ce fichier.",
    "Il fait le tour de la tour.",
]
REJECTED_274 = [
    "Marin le porte.",
    "Marin le porte dans la cuisine.",
    "Gus le visite.",
    "Lila la sort.",
    "Odile la change.",
    "Mon père la sort.",
    "Il a déménagé et il aime sa nouvelle ville.",
    "Elle a ouvert la porte et elle regarde la rue.",
    "Il a mangé et il habite ici.",
]
REJECTED_310 = [
    "Prends la ligne C et descends à Opéra.",
    "Vitamine D et fer.",
    "Je prends la ligne B ou la ligne D à midi.",
    "La gare est à 200 m à pied.",
    "Le cours dure 10 s et pas plus.",
    "Ça s'écrit J U L I E.",
    "Le rendez-vous a trois heures de retard.",
    "Mon rendez-vous a deux heures de retard.",
]
#: Correct sentences the live walks saw marked wrong (#93, #193, the gold set's right items).
SEEN_MARKED_WRONG = [
    "Vous êtes disponible jeudi matin ?",
    "Je suis froid avec elle.",
    "Je suis chaud pour ça.",
    "Je suis fatigué, mais je suis content.",
    "Les loyers sont aussi plus chers chez moi.",
    "Tu es disponible jeudi ?",
    "Je suis au Mistral avec Marin et nous buvons du café.",
    "Tu veux un café demain matin ?",
    "Non, je ne veux pas parler à Lila. Elle ne parle pas, tu te souviens ?",
]

#: A word that only looks wrong: a real «a», a date, a word with its apostrophe, a quoted word.
EVERY_RULE = [
    "Il a dix-huit ans.",
    "Elle a deux heures de retard.",
    "Il a 3 heures devant lui.",
    "Il y a une heure.",
    "Le 2 mai, je pars à Lyon.",
    "Je pars le deux mai.",
    "Quelqu'un est là.",
    "Aujourd'hui, je travaille.",
    "T'es où ?",
    "La presqu'île est belle.",
    "D'Artagnan est un héros.",
    "On ne dit pas « ce est », on dit « c'est ».",
    "On n'écrit jamais « ne y », on écrit « n'y ».",
    "On n'écrit jamais « Je ne ai ».",
    "En anglais, on écrit « the hotel ».",
    "Le mot allemand « Hotel » n'a pas d'accent.",
]

APOSTROPHE = [
    # a letter that names itself
    "La vitamine C est bonne pour la santé.",
    "La ligne C est fermée ce soir.",
    "Le plan B est prêt, le plan C est prêt aussi.",
    "Le bus C a du retard.",
    "La catégorie D est pour les camions.",
    "La porte D est ouverte.",
    "Le c est une consonne.",
    "Le d est muet dans ce mot.",
    "Le s est muet à la fin.",
    "Le n est une consonne.",
    "Le l est doublé dans ce mot.",
    "Il y a un s à la fin.",
    "Il y a un n et un l dans ce mot.",
    "J'écris un c et un d.",
    # a letter that stands for a number or a point
    "Si n est pair, on continue.",
    "Si n est pas pair, on recommence.",
    "Si c est pair, on continue.",
    "Si x est grand et n est petit, ça marche.",
    "Soit n un entier.",
    "Le point A est ici et le point C est là-bas.",
    "A est ici. C est là-bas.",
    # a unit
    "Il reste 2 l à la maison.",
    "Il boit 1 l et il mange.",
    "La piste fait 100 m et pas plus.",
    "Elle court 400 m en une minute.",
    "Il reste 10 s et c'est fini.",
    "Il fait 3 m en moyenne.",
    # an initial or a stage name
    "M. Martin est là.",
    "C. Dupont a appelé.",
    "J. Martin est mon ami.",
    "M Pokora chante ce soir.",
    "J Balvin est colombien.",
    # the apostrophe is there, in either typography
    "Qu'est-ce que c'est ?",
    "Qu’est-ce que c’est ?",
    "C'est bizarre.",
    "S'il te plaît, viens.",
    "J'ai une clé.",
    "Je n'y vais pas.",
    "Il n'est pas là.",
    "Je vais à l'hôtel.",
    "La clé d'Odile est là.",
    "Il m'a dit non.",
    "Je t'aime.",
    "Je l'ai vu hier.",
    "O'Brien est irlandais.",
    "Est-ce qu'il vient ?",
    "Quelqu'un m'a dit qu'elle est là.",
    # «a» is the verb, in front of an elided word
    "Il a l'hôtel de son père.",
    "Marin a l'air fatigué.",
    "Elle a la clé.",
    "Lundi a l'air calme.",
    "Lila a une clé et Marin a un chat.",
    "Le chat a l'air content.",
    # no French word glued together: a name, or a word of another language
    "Le mot anglais « nest » veut dire nid.",
    "En allemand, Nest veut dire nid.",
    "Son ami Jai est indien.",
    "Jai Paul est un musicien.",
    "Le Nest est un café à Lyon.",
    "Ils vont au Nest ce soir.",
]

ACCENT_FOLD = [
    # the bare form is itself French
    "Je suis sur la table.",
    "Il est sûr de lui et il dort sur le canapé.",
    "Elle va à la gare ou à la poste.",
    "Je mange du pain.",
    "Il a des amis.",
    "Le mur est blanc.",
    "La cote de ce tableau monte.",
    "La côte est belle et il est à côté de moi.",
    "Cette cure lui fait du bien.",
    "Le feutre est rouge.",
    "Il fonce vers la porte.",
    "Il marie sa fille.",
    "Elle pose la tasse.",
    "Un foret pour la perceuse.",
    "La pale de l'hélice est cassée.",
    "C'est une grande fosse.",
    "Il gravite autour d'elle.",
    "Les fuites d'eau sont réparées.",
    "J'ai une tache sur ma chemise.",
    "La sole est un poisson.",
    "Elle isole la pièce.",
    "Il contredit sa mère.",
    "Elle mouille ses cheveux.",
    "J'invite Lila.",
    "Il arrive demain.",
    "Elle marche vite.",
    "Je parle à Lila.",
    "Le marché est ouvert et il marche.",
    "Elle prie tous les jours.",
    "Il varie les plaisirs.",
    "Il applique la règle.",
    "On informe Lila.",
    "Il dore au soleil.",
    "La Tamise est longue.",
    "Il tamise la farine.",
    "Le sacre du roi.",
    "Elle fauche le pré.",
    # a name
    "Mon ami Andre arrive demain.",
    "Elle s'appelle Helene.",
    "Le Grand Hotel est fermé.",
    "Elle travaille au Regina Hotel.",
    # a word of another language, quoted or not
    "I like the hotel.",
    "The cafe is nice and the hotel is new.",
    "Das Hotel ist schön.",
    "Ich mag das Hotel und das Cafe.",
    "En anglais, hotel s'écrit sans accent.",
    "En allemand, Cafe prend une majuscule.",
    "Comment dit-on « hotel » en français ?",
    "Je ne comprends pas le mot « role ».",
    'Le mot "cle" n\'existe pas.',
    "On écrit 'hotel' sans accent en anglais.",
]

NE_BEFORE_A_VOWEL = [
    "On n'écrit jamais « ne était ».",
    "Le mot « ne » devient « n' » devant une voyelle.",
    "« ne ai » n'existe pas.",
    "Ne-Yo chante ce soir.",
    "Ne est le symbole du néon.",
    "Le mot ne est court.",
    "Je ne vais pas à Lyon.",
    "Je n'ai pas faim.",
    "Je n’ai pas faim.",
    "Il n'y a rien.",
    "Elle n'était pas là.",
    "Ne mange pas ça.",
    "Ne t'en va pas.",
]

NEGATION_ORDER = [
    "Je fais un pas.",
    "Il avance pas à pas.",
    "Elle fait un pas en avant.",
    "Il a fait trois pas vers elle.",
    "Nous pas encore.",
    "Vous pas, nous oui.",
    "Eux oui, nous pas.",
    "Moi aussi, pas toi ?",
    "Il vient, elle pas.",
    "Elle, pas lui, a la clé.",
    "Tu viens ou pas ?",
    "Pas de chance, je pars.",
    "Je ne sais pas.",
    "Je n'ai pas de chat.",
    "Il ne parle pas.",
    "Je ne veux pas aller à Lyon.",
    "Je veux pas y aller.",
    "Je suis pas sûr.",
]

A_BEFORE_THE_CLOCK = [
    "Il a dix-huit heures de retard.",
    "Jeudi a dix-huit heures de cours.",
    "Le train de jeudi a dix-huit heures de retard.",
    "Le train du soir a trois heures de retard.",
    "Lundi a trois heures libres.",
    "Le vol de demain a deux heures de retard.",
    "Le matin a duré trois heures.",
    "Marin a dix-huit heures de route.",
    "Lila a 2 heures pour finir.",
    "Elle a 3 enfants.",
    "Il a 18 ans.",
    "Jeudi, il a 18 ans.",
    "Demain, elle a 20 ans.",
    "Hier, il a dormi dix heures.",
    "Demain a l'air beau.",
    "Camille a une clé et le train de lundi a une heure de retard.",
    "Jeudi à dix-huit heures, je pars.",
    "Il y a deux heures, j'ai vu Lila.",
    "Mardi, il y a une heure de cours.",
    "Mardi a 6 heures de cours.",
    "Cette semaine a 40 heures de travail.",
    "Lundi a 8h de cours.",
    "L'après-midi a trois heures de soleil.",
    "Le rendez-vous a 3 heures de retard.",
    "Le rendez-vous de jeudi a 2 h de retard.",
]

ADJECTIVE_AGREEMENT = [
    "Ma grand-mère est là.",
    "C'est une grand-mère très gentille.",
    "Elle a une grand-tante.",
    "La Grand-Place est belle.",
    "La grand-rue est fermée.",
    "Une voiture bon marché.",
    "Tu la trouves bon marché.",
    "La porte grand ouverte.",
    "Une fenêtre grand ouverte.",
    "Elle a une bonne offre.",
    "Une petite maison.",
    "Le long de la rue.",
    "Tout au long de la route.",
    "Il est de bonne humeur.",
    "Le Petit Prince est un beau livre.",
    "Une bonne idée et un bon ami.",
    "La nouvelle voiture et le nouveau vélo.",
    "La vieille ville et le vieux port.",
    "Une belle maison et un beau jardin.",
    "La première fois et le premier jour.",
    "La dernière fois et le dernier jour.",
    "La longue route et le long chemin.",
    "Une grosse voiture et un gros chat.",
    "Une mauvaise idée et un mauvais film.",
    "Une jolie robe et un joli chat.",
    "Elle a bon goût.",
    "Il fait bon ici.",
    "Ça sent bon la pizza.",
    "Ma petite amie est là.",
    "Sa grande sœur arrive.",
]

CORPUS = {
    "rejected-259": REJECTED_259,
    "rejected-274": REJECTED_274,
    "rejected-310": REJECTED_310,
    "seen-marked-wrong": SEEN_MARKED_WRONG,
    "every-rule": EVERY_RULE,
    "apostrophe": APOSTROPHE,
    "accent-fold": ACCENT_FOLD,
    "ne-before-a-vowel": NE_BEFORE_A_VOWEL,
    "negation-order": NEGATION_ORDER,
    "a-before-the-clock": A_BEFORE_THE_CLOCK,
    "adjective-agreement": ADJECTIVE_AGREEMENT,
}
SENTENCES = [
    pytest.param(sentence, id=f"{group}-{index}")
    for group, sentences in CORPUS.items()
    for index, sentence in enumerate(sentences)
]


def test_the_corpus_holds_every_sentence_the_rejected_attempts_got_wrong():
    assert len(REJECTED_259) + len(REJECTED_274) + len(REJECTED_310) == 25
    assert len(SENTENCES) > 200


@pytest.mark.parametrize("sentence", SENTENCES)
def test_no_rule_touches_it(sentence):
    edits = [(edit.span, edit.replacement, edit.rule_id) for edit in cc.deterministic_edits(sentence)]
    assert edits == []
    assert cc.repair_text(sentence) == sentence
