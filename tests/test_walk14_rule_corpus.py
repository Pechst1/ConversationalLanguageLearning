"""Walk 14: the two new model-free rules (``FR_ADJ_PLURAL``, ``FR_NUMBER_S``) on correct
French that looks like their mistakes. A correct sentence here must get no edit at all: a
wrong correction is the bug PR #987 exists to remove, a missed slip costs little.
No model call is made anywhere in this file.
"""

from __future__ import annotations

import pytest

from app.services import correction_contract as cc

ADJ_RIGHT = [
    # Invariable colours named after a thing, and compound colours.
    "Ils sont marron.",
    "Elles sont orange.",
    "Ils sont crème.",
    "Elles sont turquoise.",
    "Ils sont kaki.",
    "Elles sont bordeaux.",
    "Ils sont noisette.",
    "Elles sont cerise.",
    "Ils sont chocolat.",
    "Ils sont bleu marine.",
    "Elles sont vert clair.",
    "Ils sont gris foncé.",
    "Elles sont bleu ciel.",
    "Ils sont rose bonbon.",
    # Degree words and frozen phrases.
    "Ils sont super contents.",
    "Ils sont super content de te voir, mais super fatigués.",
    "Ils sont bon marché.",
    "Elles sont bon marché.",
    "Ils sont debout.",
    "Ils sont bien.",
    "Nous sommes mal.",
    "Nous sommes ensemble.",
    "Ils sont pas mal.",
    "Nous sommes d'accord.",
    "Elles sont d'accord avec nous.",
    # Loans and invariable words.
    "Ils sont cool.",
    "Elles sont sympa.",
    "Ils sont sympas.",
    "Ils sont chic.",
    "Ils sont standard.",
    # -al, -eu, -eau and words already in s/x/z.
    "Ils sont banals.",
    "Ils sont finals.",
    "Ils sont fatals.",
    "Ils sont navals.",
    "Ils sont normaux.",
    "Ils sont bleus.",
    "Ils sont beaux.",
    "Ils sont heureux.",
    "Ils sont gris.",
    "Ils sont français.",
    "Nous sommes sérieux.",
    # Already plural, or not a predicate adjective at all.
    "Nous sommes drôles.",
    "Elles sont libres ce soir.",
    "Ils sont très calmes.",
    "Ils sont contents de te voir.",
    "Nous sommes à Lyon.",
    "Nous sommes chez Lila.",
    "Ils sont médecins.",
    "Ils sont là.",
    "Nous sommes ici depuis lundi.",
    "Vous êtes drôle.",
    "On est drôle.",
    "Elles sont contentes.",
    "Elles sont fatiguées.",
    # The learner's gender is never read: «fatigués» or «fatiguées» is the learner's call.
    "Nous sommes fatigué.",
    "Elles sont content.",
]

ADJ_WRONG = [
    ("Nous sommes drôle.", "drôles"),
    ("Ils sont drôle.", "drôles"),
    ("Elles sont drôle.", "drôles"),
    ("Ils sont très calme.", "calmes"),
    ("Elles sont libre ce soir.", "libres"),
    ("Nous sommes triste.", "tristes"),
    ("Ils sont rouge.", "rouges"),
    ("Elles sont rapide.", "rapides"),
    ("Ils sont content.", "contents"),
    ("Ils sont content de te voir.", "contents"),
    ("Ils sont grand.", "grands"),
    ("Ils sont petit.", "petits"),
    ("Ils sont fatigué.", "fatigués"),
    ("Ils sont joli.", "jolis"),
    ("Ils sont têtu.", "têtus"),
    ("Ils sont vraiment intelligent.", "intelligents"),
    ("Nous sommes jeune et libre.", "jeunes"),
]

NUMBER_RIGHT = [
    "Il a quatre-vingts ans.",
    "Ça coûte deux cents euros.",
    "Marin a quatre-vingt-dix ans.",
    "Le billet coûte deux cent dix euros.",
    "La ville a quatre-vingts millions d'habitants.",
    "Il y a deux cents millions de lecteurs.",
    "Ça coûte trois cents milliards.",
    "Ils ont gagné quatre-vingt mille euros.",
    "Quatre-vingt-un, quatre-vingt-deux, quatre-vingt-trois.",
    "J'ai lu les deux cents pages.",
    "Il y a deux cents, trois sont cassés.",
    "Deux cents personnes sont venues.",
    "Nous avons quatre-vingts invités.",
]

NUMBER_WRONG = [
    ("Marin a quatre-vingts-dix ans.", "quatre-vingt"),
    ("Le livre a quatre-vingts-deux pages.", "quatre-vingt"),
    ("Quatre-vingts-un.", "Quatre-vingt"),
    ("Ils ont gagné quatre-vingts mille euros.", "quatre-vingt"),
    ("Le billet coûte deux cents dix euros.", "deux cent"),
    ("Il y a trois cents cinquante places.", "trois cent"),
]


@pytest.mark.parametrize("sentence", ADJ_RIGHT)
def test_correct_predicate_adjectives_get_no_edit(sentence: str) -> None:
    assert cc.deterministic_edits(sentence) == [], sentence


@pytest.mark.parametrize(("sentence", "right"), ADJ_WRONG)
def test_a_singular_predicate_adjective_after_a_plural_subject_is_named(sentence: str, right: str) -> None:
    edits = [edit for edit in cc.deterministic_edits(sentence) if edit.rule_id == "FR_ADJ_PLURAL"]
    assert [edit.replacement for edit in edits][:1] == [right], sentence
    fixed = cc.apply_edits(sentence, cc.deterministic_edits(sentence))
    assert cc.deterministic_edits(fixed) == [], fixed


@pytest.mark.parametrize("sentence", NUMBER_RIGHT)
def test_correct_numbers_get_no_edit(sentence: str) -> None:
    assert cc.deterministic_edits(sentence) == [], sentence


@pytest.mark.parametrize(("sentence", "right"), NUMBER_WRONG)
def test_a_plural_s_inside_a_number_is_named(sentence: str, right: str) -> None:
    edits = [edit for edit in cc.deterministic_edits(sentence) if edit.rule_id == "FR_NUMBER_S"]
    assert [edit.replacement for edit in edits] == [right], sentence


def test_the_corpora_are_the_size_asked_for() -> None:
    assert len(ADJ_RIGHT) >= 40 and len(ADJ_WRONG) >= 15
