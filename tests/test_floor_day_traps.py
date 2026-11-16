"""#807 / #824 / #825: the basic check (``correction_contract``, no model) names the day's trap.

#807 (walk 15 Nov, no model, a passé composé day): the basic check fixed the accents around
the verb and never the verb. «il a invite Lila», «ils ont expliquer la methode», «tu as
appele la banque», «je suis arrive», «Gus m a demande», «Margaux m a donne» were listed
with only their apostrophes, so the one slip that is the day's rule was never named. The
floor had no rule for an auxiliary followed by a verb form that is not a participle.

#824 (walk 16 Nov, no model, an avoir day): «Tu es faim ce soir ?», the avoir card's own
«Falsch», went by unnamed: the être-for-avoir slip was read for «je suis» only.

#825 (walk 16 Nov, no model, Courrier): «je ne pas oublie plus» was «corrected» into «je
n'oublie pas plus»: the negation reorder moved «pas» behind the verb without reading the
«plus» that already closed the negation there.

The three share one cause: the floor's rules read a few tokens around one word and never
the rest of the shape the card teaches (the auxiliary + its participle, the person of
être, the second half of the negation). The guards below run each card's own trap, and
the shapes built on it, through the basic check.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.services import correction_contract

# ---------------------------------------------------------------------------
# #807: the participle after an auxiliary
# ---------------------------------------------------------------------------

FORGE_INVITE = "L ete dernier, il a invite Lila au cinema."
FORGE_EXPLIQUER = "La semaine derniere, ils ont expliquer la methode de Gus. Mais c est quoi, cette methode ?"
FORGE_APPELE = "Avant-hier, tu as appele la banque."
JOURNAL_RETELL = (
    "Hier soir, je suis arrive au Mistral avec la cle de ma grand-mère. Gus m a demande qui j etais, "
    "et Margaux m a donne la cle."
)

WALK_PARTICIPLES = [
    (FORGE_INVITE, "a invité"),
    (FORGE_EXPLIQUER, "ont expliqué"),
    (FORGE_APPELE, "as appelé"),
    (JOURNAL_RETELL, "suis arrivé"),
    (JOURNAL_RETELL, "m'a demandé"),
    (JOURNAL_RETELL, "m'a donné"),
]
WALK_IDS = ["invite", "expliquer", "appele", "arrive", "demande", "donne"]


def _named(errata: list[dict], right: str) -> bool:
    participle = right.split()[-1]
    return any(participle in str(item.get("corrected_target") or "") for item in errata)


@pytest.mark.parametrize(("sentence", "right"), WALK_PARTICIPLES, ids=WALK_IDS)
def test_pc_floor(sentence, right):
    """The floor names the participle after an auxiliary, on the walk's exact sentences."""
    errata = correction_contract.deterministic_errata(sentence, language="en")
    assert _named(errata, right), (
        f"«{sentence}»: the basic check never names «{right}»; it listed "
        f"{[(e['learner_text'], e['corrected_target']) for e in errata]}"
    )
    assert right in correction_contract.repair_text(sentence)


@pytest.mark.parametrize(("sentence", "right"), WALK_PARTICIPLES, ids=WALK_IDS)
def test_pc_forge(sentence, right):
    """La Forge's free sentence with no model to read it (#724's fallback)."""
    from app.services.atelier import _with_rule_fixes

    correction = _with_rule_fixes({}, sentence, language="en")
    assert _named(correction["errata"], right), correction["errata"]


@pytest.mark.parametrize(
    "right",
    [
        "Il a une invite à répondre.",
        "Il invite Lila.",
        "Il a demandé.",
        "Gus m'a demandé qui j'étais.",
        "J'ai envie de partir.",
        "J'ai hâte de te voir.",
        "J'en ai marre.",
        "Elle est calme.",
        "C'est pratique.",
        "La salle est vide.",
        "Il a entre vingt et trente ans.",
        "C'est entre nous.",
        "Il y a place pour deux.",
        "Je suis prêt a manger.",
        "Il va arriver demain.",
        "Je n'ai rien à manger.",
        "Ils ont classe le lundi.",
        # review of #815: «il n'y a» is «there is» as much as «il y a»
        "Il n'y a pas foule.",
        "Il n'y a pas foule ce soir.",
        "Il n'y a jamais foule ici.",
        "Il n'y a plus place.",
        "Il n'y a pas place pour le doute.",
        "On a contrôle demain.",
    ],
)
def test_a_form_that_is_not_after_an_auxiliary_or_is_a_word_is_left_alone(right):
    rules = [edit.rule_id for edit in correction_contract.deterministic_edits(right)]
    assert "FR_PARTICIPLE" not in rules, f"«{right}» is French as written: {rules}"
    assert correction_contract.repair_text(right) == right


def test_an_adverb_between_the_auxiliary_and_the_participle():
    assert correction_contract.repair_text("Il a juste regarde.") == "Il a juste regardé."


def _er_verbs() -> list[str]:
    from app.services.lexical_coverage import load_lexicon

    lemmas = load_lexicon().lemmas
    return sorted(
        word
        for word, entry in lemmas.items()
        if entry.get("pos") == "verb" and word.endswith("er") and entry.get("band") in {"A1", "A2"}
    )


def _third_person(verb: str) -> str:
    """The plain written «il …» form a learner types for the participle: «invite», «appele»."""
    return verb[:-2] + "e"


#: avoir forms with the subject each one takes.
_AVOIR = [("j'", "ai"), ("tu", "as"), ("il", "a"), ("nous", "avons"), ("vous", "avez"), ("ils", "ont")]
#: être forms: the -er verbs that make their passé composé with être.
_ETRE = [("je", "suis"), ("tu", "es"), ("il", "est"), ("nous", "sommes"), ("vous", "êtes"), ("ils", "sont")]
_ETRE_ER_VERBS = ("aller", "arriver", "entrer", "rester", "tomber", "rentrer", "monter", "retourner")


def test_pc_every_er_verb():
    """The guard of #807's done-when: an -er verb of the A1–A2 lexicon, written as its
    infinitive or as its bare «il» form, after each auxiliary form, is named."""
    verbs = _er_verbs()
    assert len(verbs) > 150, verbs
    missed: list[str] = []
    for verb in verbs:
        participle = verb[:-2] + "é"
        cases = list(_AVOIR)
        if verb in _ETRE_ER_VERBS:
            cases += _ETRE
        for subject, aux in cases:
            for written in (verb, _third_person(verb)):
                if written == "entre":
                    continue  # «entre» is the preposition: «il est entre deux chaises»
                glue = "" if subject.endswith("'") else " "
                sentence = f"Hier, {subject}{glue}{aux} {written} avec Lila."
                fixed = correction_contract.repair_text(sentence)
                if not re.search(rf"(?<!\w){participle}e?s?(?!\w)", fixed):
                    missed.append(f"{sentence} -> {fixed}")
    assert not missed, f"{len(missed)} missed: {missed}"


@pytest.fixture
def journal(db_engine, db_session):
    """The Journal's table, as ``tests/test_journal.py`` sets it up for its own tests."""
    from app.db.models.journal import JournalEntry

    JournalEntry.__table__.create(bind=db_engine, checkfirst=True)
    yield


def test_pc_journal(journal, db_session, monkeypatch):
    """#807 done-when: the Journal's basic check (no model) on the walk's retell."""
    from app.config import settings
    from tests.test_journal import TODAY, _concept, _journey, _user, _write

    monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_ENABLED", False)
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    entry = _write(db_session, user, None, JOURNAL_RETELL)

    rights = " | ".join(str(item.get("corrected_fr")) for item in entry.correction["errata"])
    for participle in ("arrivé", "demandé", "donné"):
        assert participle in rights, f"the Journal's basic check never names «{participle}»: {rights}"


# ---------------------------------------------------------------------------
# #824: être for avoir in every person, and every A1 card's own trap
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "right"),
    [
        ("Tu es faim ce soir ?", "Tu as faim ce soir ?"),
        ("Je suis vingt ans.", "J'ai vingt ans."),
        ("Je suis froid.", "J'ai froid."),
        ("Tu es froid ?", "Tu as froid ?"),
        ("Il est soif après le match.", "Il a soif après le match."),
        ("Elle est peur du noir.", "Elle a peur du noir."),
        ("On est faim !", "On a faim !"),
        ("Nous sommes faim.", "Nous avons faim."),
        ("Vous êtes soif ?", "Vous avez soif ?"),
        ("Ils sont sommeil.", "Ils ont sommeil."),
    ],
)
def test_etre_for_avoir_in_every_person(sentence, right):
    """#824: the basic check names «avoir faim» whoever is hungry, with the card's form."""
    errata = correction_contract.deterministic_errata(sentence, language="de")
    assert correction_contract.repair_text(sentence) == right, (
        f"«{sentence}»: the basic check printed «{correction_contract.repair_text(sentence)}»; it listed "
        f"{[(e['learner_text'], e['corrected_target']) for e in errata]}"
    )
    assert errata and all(e["why_wrong"] for e in errata)


def test_tu_es_faim_in_la_forge_without_a_model():
    """#824: La Forge's free item with no model names «Tu as faim» as a basic check."""
    from app.services.atelier import _with_rule_fixes

    correction = _with_rule_fixes({}, "Tu es faim ce soir ?", language="de")
    assert [(e["learner_text"], e["corrected_target"]) for e in correction["errata"]] == [("Tu es faim", "Tu as faim")]
    assert "tu as faim" in correction["errata"][0]["why_wrong"]


@pytest.mark.parametrize(
    "right",
    [
        "Il est froid.",  # the soup, the room, the man
        "La soupe est froide.",
        "Elle est froide avec moi.",
        "Je suis froid avec elle.",
        "Ils sont froids.",
        "Il est chaud.",
        "J'ai faim.",
        "Tu as soif ?",
        "C'est la faim.",
    ],
)
def test_etre_for_avoir_leaves_french_alone(right):
    rules = [edit.rule_id for edit in correction_contract.deterministic_edits(right)]
    assert "FR_AVOIR_STATE" not in rules, f"«{right}» is French as written: {rules}"


def _card_traps(level: str) -> list[tuple[str, str, str]]:
    path = Path(__file__).resolve().parents[1] / "app" / "data" / "rule_cards" / f"fr2_{level}.json"
    cards = json.loads(path.read_text(encoding="utf-8"))["cards"]
    out = []
    for card_id, card in sorted(cards.items()):
        contrast = card.get("contrast") or {}
        if contrast.get("wrong") and contrast.get("right"):
            out.append((card_id, contrast["wrong"], re.sub(r"[\[\]{}]", "", contrast["right"])))
    return out


#: The A1 cards whose «Falsch» line the floor cannot read yet: each needs a rule of its
#: own (an article, a conjugation table, a word order), and each is a model's job until
#: then. ``strict``: a card that starts passing must leave this list, so the guard keeps
#: what it gains.
_NOT_READ_YET = {
    "FR2_A11_ADJ_AGREEMENT", "FR2_A11_ALLER_VENIR", "FR2_A11_ER_VERBS", "FR2_A11_FAIRE_PRENDRE",
    "FR2_A11_IL_Y_A", "FR2_A11_JE_VOUDRAIS", "FR2_A11_LE_LA", "FR2_A11_NEGATION", "FR2_A11_NUMBERS",
    "FR2_A11_PLACES", "FR2_A11_UN_UNE", "FR2_A12_CEST_IL_EST", "FR2_A12_DAYS_DATES", "FR2_A12_ER_SPELLING",
    "FR2_A12_FREQUENCY", "FR2_A12_FUTUR_PROCHE", "FR2_A12_IMPERATIVE", "FR2_A12_IR_RE_VERBS",
    "FR2_A12_MODALS", "FR2_A12_NUMBERS_BIG", "FR2_A12_PRONOMINAL", "FR2_A12_QUANTITIES",
    "FR2_A12_QUEL_EXCLAMATIF", "FR2_A12_TIME",
}


@pytest.mark.parametrize(
    ("card", "wrong", "right"),
    [
        pytest.param(
            *trap,
            id=trap[0],
            marks=[pytest.mark.xfail(strict=True, reason="no floor rule reads this card yet")]
            if trap[0] in _NOT_READ_YET
            else [],
        )
        for trap in _card_traps("A1")
    ],
)
def test_every_a1_card_trap_is_named_by_the_basic_check(card, wrong, right):
    """#824's guard: each A1 card's own «Falsch» line comes out as the card's «Richtig»."""
    fixed = correction_contract.repair_text(wrong)
    assert fixed == right, f"{card}: «{wrong}» is printed as «{fixed}», the card says «{right}»"


def test_the_avoir_and_passe_compose_cards_are_read():
    """The two traps of #807 and #824 stay out of the not-yet list."""
    assert {"FR2_A11_AVOIR", "FR2_A12_PC_CHUNKS"} <= {card for card, _w, _r in _card_traps("A1")}
    assert not {"FR2_A11_AVOIR", "FR2_A12_PC_CHUNKS"} & _NOT_READ_YET


# ---------------------------------------------------------------------------
# #825: the negation reorder never prints «pas plus»
# ---------------------------------------------------------------------------

COURRIER_REPLY = "Merci Margaux ! Oui, je passe demain. Je suis tres fatigue, je ne pas oublie plus."


def test_ne_pas_oublie_plus():
    """#825 done-when: «je ne pas oublie plus» gives «je n'oublie plus»."""
    assert correction_contract.repair_text("je ne pas oublie plus") == "je n'oublie plus"
    fixed = correction_contract.repair_text(COURRIER_REPLY)
    assert "pas plus" not in fixed, fixed
    assert fixed.endswith("je n'oublie plus."), fixed


def test_the_courrier_basic_check_prints_no_pas_plus():
    """The Courrier's model-free pass (``_deterministic_errata``) on the walk's reply."""
    from app.services.missions import MissionCorrectionService

    service = MissionCorrectionService.__new__(MissionCorrectionService)
    errata, corrected = service._deterministic_errata(COURRIER_REPLY, language="de")
    assert "pas plus" not in corrected, corrected
    assert all("pas plus" not in str(item.get("corrected_target")) for item in errata), errata
    assert any(item.get("corrected_target") == "n'oublie plus" for item in errata), errata


_SUBJECTS = ["je", "tu", "il", "nous", "vous", "ils"]
_VERBS = {"je": "oublie", "tu": "manges", "il": "parle", "nous": "regardons", "vous": "aimez", "ils": "écoutent"}
_CLOSERS = ["plus", "jamais", "rien", "personne"]
_DOUBLED = re.compile(r"\bpas (plus|jamais|rien|personne|aucun|aucune|guère)\b")


def test_the_negation_reorder_never_doubles_the_negation():
    """#825's guard: every misplaced «pas» with a second negation word after the verb is
    repaired into one negation, and the printed line triggers no further negation fix."""
    printed: list[str] = []
    for subject in _SUBJECTS:
        verb = _VERBS[subject]
        for closer in _CLOSERS:
            for sentence in (
                f"Hier soir, {subject} ne pas {verb} {closer}.",
                f"Hier soir, {subject} pas {verb} {closer}.",
                f"Hier soir, {subject} ne {closer} {verb} pas.",
            ):
                fixed = correction_contract.repair_text(sentence)
                again = [
                    (e.rule_id, e.span)
                    for e in correction_contract.deterministic_edits(fixed)
                    if e.rule_id.startswith(("FR_NEGATION", "FR_DOUBLE_NEGATION"))
                ]
                if _DOUBLED.search(fixed) or again or f" {closer}" not in fixed:
                    printed.append(f"{sentence} -> {fixed} {again}")
    assert not printed, f"{len(printed)} wrong lines: {printed}"


@pytest.mark.parametrize(
    ("sentence", "right"),
    [
        ("Je ne pas parle.", "Je ne parle pas."),
        ("Je pas ai beaucoup de bagages.", "Je n'ai pas beaucoup de bagages."),
        ("Je ne jamais vois rien.", "Je ne vois jamais rien."),
    ],
)
def test_the_plain_reorders_are_kept(sentence, right):
    assert correction_contract.repair_text(sentence) == right
