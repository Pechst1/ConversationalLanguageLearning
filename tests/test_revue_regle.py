"""«Papier · La règle» (2026-11-22): Romy corrects like the scene's tutor and names the app's rules.

Always on, two wrong marks of the first real run (tirage 2026-11-22) are guarded: a correct
question rewritten to another form is accepted as written (an inversion at every level, a
spoken or «est-ce que» question below B2), and a mark that changes nothing is never shown.
With ``REVUE_TUTOR_MARKS_ENABLED`` every mark also passes the scene tutor's verification
(``story_lanes._accepted_correction``), falls back to the model-free edit as the scene does, and
names its grammar concept (``GrammarConcept.external_id``) — with the day's rule said so and
explained by the rule card's own line. Off, the marks are the Papier's own, as before.
"""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.services.revue import comptoir, comptoir_loop, voice
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider
from app.services.revue.evergreen import evergreens_for_week, load_evergreens
from tests.test_revue_comptoir_loop import (
    GUS,
    MARCHE,
    MARGAUX,
    ROMY,
    WEEK,
    Revue,
    act,
    make_user,
    revue_tables,  # noqa: F401 - the fixture
    state_of,
    wire,
)


class _Lazy:
    """A module imported when a test reads it (so each guard fails on its own line on the base)."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attr: str) -> Any:
        return getattr(importlib.import_module(self._name), attr)


regle = _Lazy("app.services.revue.regle")
rubrique_proof = _Lazy("app.services.revue.rubrique_proof")
A2_REASON = "le gens sont content au supermarché"


@pytest.fixture(autouse=True)
def switches(monkeypatch) -> None:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_POURQUOI_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "REVUE_TUTOR_MARKS_ENABLED", True, raising=False)
    comptoir.forget_cache()


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:  # noqa: F811 - the imported fixture
    return db_session


# ---------------------------------------------------------------------------
# Always on: a correct question stands, a mark that changes nothing is not a mark
# ---------------------------------------------------------------------------

STYLE = "Seize chevaux, vraiment ? Et la course, elle dure combien de temps ? Le vainqueur, il gagne quoi ?"
STYLE_INVERTED = "Seize chevaux, vraiment ? Et la course, combien de temps dure-t-elle ? Le vainqueur, que gagne-t-il ?"


@pytest.mark.parametrize(("sentence", "form"), [
    ("Tu viens quand ?", "intonation"),
    ("Et la course, elle dure combien de temps ?", "intonation"),
    ("Quand est-ce que tu viens ?", "est_ce_que"),
    ("Qu'est-ce que tu manges ?", "est_ce_que"),
    ("Quand viens-tu ?", "inversion"),
    ("De combien est la hausse des produits frais ?", "inversion"),
    ("Quand la course commence ?", "fronted"),
    ("Pourquoi elle est gratuite ?", "fronted"),
    ("Combien d'argent le gagnant reçoit ?", "fronted"),
])
def test_how_a_question_is_built(sentence: str, form: str) -> None:
    assert regle.learner_form(sentence) == form


def test_spoken_questions_stand_as_written_below_b2() -> None:
    """Tirage 2026-11-22: the three spoken-style questions were rewritten to inversion and marked
    «ordre» three times. Below B2 they are correct as written: no mark, printed as written."""

    for band in ("A2", "B1"):
        target = regle.accept_what_stands(STYLE, STYLE_INVERTED, band, voice.french_typography)
        assert target == STYLE
        assert comptoir_loop.proof_marks(STYLE, target) == []
    assert regle.accept_what_stands("Quand est-ce que tu viens ?", "Quand viens-tu ?", "A2",
                                    voice.french_typography) == "Quand est-ce que tu viens ?"
    assert regle.accept_what_stands("Tu viens ?", "Viens-tu ?", "B1", voice.french_typography) == "Tu viens ?"
    # From B2 the written form may be asked for (the policy before, unchanged there).
    assert regle.accept_what_stands("Tu viens quand ?", "Quand viens-tu ?", "B2", voice.french_typography) == "Quand viens-tu ?"


def test_a_correct_inversion_is_never_marked_at_any_level() -> None:
    """Tirage 2026-11-22: «De combien est la hausse des produits frais ?» was marked «est ·
    Wortstellung», «frais · Wortstellung» in round 1 and accepted unchanged in round 2."""

    learner = "De combien est la hausse des produits frais ?"
    for corrected in ("De combien la hausse des produits frais est-elle ?", "De combien la hausse des produits frais est ?"):
        for band in ("A2", "B1", "B2"):
            target = regle.accept_what_stands(learner, corrected, band, voice.french_typography)
            assert target == learner
            assert comptoir_loop.proof_marks(learner, target) == []


def test_a_real_slip_in_a_question_is_still_marked() -> None:
    learner = "Combien de chevaux est-ce que courent ? Quand la course commence ? Combien d'argent le gagner reçoit ?"
    corrected = ("Combien de chevaux est-ce qui courent ? Quand est-ce que la course commence ? "
                 "Combien d'argent est-ce que le gagnant reçoit ?")
    target = regle.accept_what_stands(learner, corrected, "A2", voice.french_typography)
    assert target == corrected, "a question word then its subject, neither inversion nor «est-ce que», is a slip"
    assert [m["span_fr"] for m in comptoir_loop.proof_marks(learner, target)] == ["que", "Quand", "d'argent"]


def test_a_mark_that_changes_nothing_is_dropped() -> None:
    learner = "De combien est la hausse des produits frais ?"
    marks = [{"span_fr": "est", "start": 11, "kind": "ordre"}, {"span_fr": "frais", "start": 38, "kind": "ordre"}]
    assert regle.drop_unchanged(marks, learner, learner) == []
    real = comptoir_loop.proof_marks("le gens sont content", "les gens sont contents")
    assert regle.drop_unchanged(real, "le gens sont content", "les gens sont contents") == real


def test_the_question_guard_holds_with_the_switch_off(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_TUTOR_MARKS_ENABLED", False, raising=False)
    checked = _proofread(db, STYLE, STYLE_INVERTED, level="A2.1")
    assert checked["proof"] == "clean" and checked["target"] == STYLE and checked["marks"] == []


def test_the_question_prompt_keeps_a_correct_question_and_its_version_moved() -> None:
    text = rubrique_proof.edit_instructions({"kind": "micro"})
    assert "never move it to another form" in text and "Tu viens quand ?" in text
    assert "inversion or «est-ce que» after a\n  question word in writing" not in text
    assert rubrique_proof.EDIT_PROMPT_VERSION == "rubrique-edit-v3"
    assert rubrique_proof.EDIT_PROMPT_VERSION_POURQUOI == "rubrique-edit-v4"
    with_why = rubrique_proof.edit_instructions({"kind": "micro", "explain_language": "de"})
    assert "why_hint" in with_why and "never move it to another form" in with_why


# ---------------------------------------------------------------------------
# The scene tutor's verification
# ---------------------------------------------------------------------------


def _vet(learner: str, target: str, rules: dict | None = None):
    marks = comptoir_loop.proof_marks(learner, target)
    return regle.vet(marks, learner_fr=learner, target_fr=target, language="de", rules=rules,
                     shape=voice.french_typography)


def test_a_mark_the_tutor_does_not_stand_by_is_dropped_and_its_change_taken_out() -> None:
    learner = "Je pense que tu as raison. Le gens sont content."
    target = "Je pense que vous avez raison. Les gens sont contents."
    fixed, marks = _vet(learner, target)
    assert [m["span_fr"] for m in marks] == ["Le", "content"], "«tu as» → «vous avez» changes the subject"
    assert fixed == "Je pense que tu as raison. Les gens sont contents."


def test_with_no_mark_left_the_model_free_edit_stands_in() -> None:
    learner = "Je suis froid, je pense que tu as raison."
    fixed, marks = _vet(learner, "Je suis froid, je pense que vous avez raison.")
    assert [(m["span_fr"], fixed) for m in marks] == [("Je suis froid", "J'ai froid, je pense que tu as raison.")]
    assert "j'ai froid" in marks[0]["why_full"].casefold(), "the scene's own note, in the learner's language"
    fixed, marks = _vet("Je pense que tu as raison.", "Je pense que vous avez raison.")
    assert (fixed, marks) == ("Je pense que tu as raison.", [])


def test_marks_the_tutor_stands_by_are_kept_as_they_are() -> None:
    learner = "À mon avis, parce que le gens sont content au supermarché."
    target = "À mon avis, parce que les gens sont contents au supermarché."
    fixed, marks = _vet(learner, target)
    assert fixed == target and [m["span_fr"] for m in marks] == ["le", "content"]
    assert all("_edit" not in m for m in marks)


# ---------------------------------------------------------------------------
# The app's rule
# ---------------------------------------------------------------------------


def test_a_mark_is_tied_to_the_catalogue_concept_with_its_name() -> None:
    concept = regle.concept_for("Les jurés ont devenu des juges.", "ont devenu", "sont devenus", kind="mot",
                                rule=None, rules=None, language="de")
    assert concept == {"concept_id": "FR2_A21_PC_ETRE", "concept_name": "Passé composé mit être und Angleichung",
                       "is_day_rule": False, "is_recent_rule": False}
    concept = regle.concept_for("Les gens sont content.", "content", "contents", kind="accord", rule="plural_s",
                                rules=None, language="fr")
    assert concept["concept_id"] in {"FR2_A11_ADJ_AGREEMENT", "FR2_A11_NOUN_PLURALS"} and concept["concept_name"]
    assert regle.concept_for("Je suis sicher.", "sicher", "sûr", kind="mot", rule=None, rules=None, language="de") is None


def test_every_concept_named_is_in_the_catalogue() -> None:
    from app.services.grammar_units import _v2_rows_by_external_id

    rows = _v2_rows_by_external_id()
    named = {c for table in (regle.RULE_CONCEPTS, regle.KIND_CONCEPTS) for ids in table.values() for c in ids}
    assert named <= set(rows), named - set(rows)
    from app.services.revue.correcteur import RULES

    assert set(regle.RULE_CONCEPTS) == set(RULES), "each of the Papier's six rules maps"


def test_the_days_rule_is_said_and_explains_itself_with_the_card() -> None:
    from app.services.grammar_units import regex_patterns, unit_detectors

    unit = SimpleNamespace(external_id="FR2_B12_SUBJ_IRREGULAR", id=1, level="B1", name="", description="", category="")
    rules = {"today": {"id": "FR2_B12_SUBJ_IRREGULAR", "name": "Subjonctif: unregelmäßige Verben",
                       "rule": "Nach «il faut que» steht der Subjonctif.", "detectors": regex_patterns(unit_detectors(unit))},
             "recent": [{"id": "FR2_A11_ADJ_AGREEMENT", "name": "Adjektive", "rule": "Das Adjektiv richtet sich nach dem Nomen.",
                         "detectors": []}]}
    learner = "Il faut que les gens peuvent nager et ils sont content."
    target = "Il faut que les gens puissent nager et ils sont contents."
    fixed, marks = _vet(learner, target, rules)
    named = regle.state_rules(regle.name_rules(marks, learner_fr=learner, target_fr=fixed, rules=rules, language="de"))
    day, recent = named
    assert (day["concept_id"], day["is_day_rule"], day["is_recent_rule"]) == ("FR2_B12_SUBJ_IRREGULAR", True, False)
    assert day["concept_name"] == "Subjonctif: unregelmäßige Verben", "the name the scene shows"
    assert day["why_full"] == day["why_hint"] == "Nach «il faut que» steht der Subjonctif."
    assert (recent["concept_id"], recent["is_day_rule"], recent["is_recent_rule"]) == ("FR2_A11_ADJ_AGREEMENT", False, True)
    assert recent["why_full"] == "Das Adjektiv richtet sich nach dem Nomen."


# ---------------------------------------------------------------------------
# In a session: the counter's opinion, the day's rule stamped
# ---------------------------------------------------------------------------


def _to_opinion(revue, row) -> None:
    act(revue, row, act="vote", value="contre")
    for guest in (ROMY, MARGAUX, GUS):
        act(revue, row, act="react", guest_id=guest, value="agree")
    act(revue, row, act="intox_who", guest_id=GUS)
    act(revue, row, act="intox_fix", value="six jours sur sept")


def _introduce(db: Session, user, external_id: str) -> None:
    concept = db.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one_or_none()
    if concept is None:
        concept = GrammarConcept(language="fr", level="A1", name=external_id, external_id=external_id,
                                 category="Agreement", description="", difficulty_order=10, active=True)
        db.add(concept)
        db.flush()
    db.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id, introduced_at=datetime.now(UTC) - timedelta(hours=1)))
    db.commit()


def test_in_a_session_the_mark_under_the_days_rule_is_stamped(db: Session) -> None:
    revue = Revue(db, FakeRevueProvider())
    user = make_user(db, level="A2.1", native="de")
    _introduce(db, user, "FR2_A11_ADJ_AGREEMENT")
    row = revue.start(user, week=WEEK, dossier_id=MARCHE)
    _to_opinion(revue, row)
    view = act(revue, row, act="opinion", value="contre", text=A2_REASON).session.comptoir
    marks = {m.span_fr: m for m in view.opinion.marks}
    assert set(marks) == {"le", "content"}
    content = marks["content"]
    assert (content.concept_id, content.is_day_rule) == ("FR2_A11_ADJ_AGREEMENT", True)
    assert content.concept_name
    assert content.why and "contents" not in content.why, "the card's line, never the answer"
    shown = json.loads(wire(view))["opinion"]["marks"]
    assert {"concept_id", "concept_name", "is_day_rule", "is_recent_rule"} <= set(shown[1])
    view = act(revue, row, act="opinion_fix", text="les gens sont contents au supermarché").session.comptoir
    note = next(n for n in view.opinion.notes if n.span_fr == "content")
    assert note.is_day_rule and note.concept_id == "FR2_A11_ADJ_AGREEMENT" and note.why == content.why


def test_off_the_marks_and_the_view_are_as_before(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_TUTOR_MARKS_ENABLED", False, raising=False)
    revue = Revue(db, FakeRevueProvider())
    user = make_user(db, level="A2.1", native="de")
    _introduce(db, user, "FR2_A11_ADJ_AGREEMENT")
    row = revue.start(user, week=WEEK, dossier_id=MARCHE)
    _to_opinion(revue, row)
    view = act(revue, row, act="opinion", value="contre", text=A2_REASON).session.comptoir
    shown = json.loads(wire(view))["opinion"]["marks"]
    assert all(sorted(m) == ["kind", "span_fr", "start", "why"] for m in shown), shown
    event = next(e for e in state_of(row).events if e.payload.get("act") == "opinion")
    assert not any("concept_id" in m for m in event.payload["marks"])


# ---------------------------------------------------------------------------
# The shared rubrique path (photo, micro)
# ---------------------------------------------------------------------------


class _Scripted(FakeRevueProvider):
    def __init__(self, edited: str) -> None:
        super().__init__()
        self.edited = edited

    def rubrique_edit(self, context):
        self.calls.append(("rubrique_edit", context))
        return {"edited_fr": self.edited, "marks": [{"span_fr": "elle dure", "kind": "ordre"}]}


def _proofread(db: Session, learner: str, edited: str, *, level: str) -> dict[str, Any]:
    user = make_user(db, level=level, native="de")
    dossier = next(d for d in load_evergreens() if d.id == MARCHE)
    encounter = SimpleNamespace(provider=_Scripted(edited), db=db)
    loaded = SimpleNamespace(dossier=dossier, row=SimpleNamespace(id="s", user_id=user.id), plan=None)
    return rubrique_proof.proofread(encounter, loaded, kind="micro", band=level[:2], learner_fr=learner)


def test_the_interview_questions_are_accepted_as_written(db: Session) -> None:
    checked = _proofread(db, STYLE, STYLE_INVERTED, level="A2.1")
    assert checked["proof"] == "clean" and checked["target"] == STYLE and checked["marks"] == []
    checked = _proofread(db, STYLE, STYLE_INVERTED, level="B2.1")
    assert checked["proof"] == "marked", "from B2 the written form may still be asked for"
