"""Walk 14 (two-week real-model walk, 21 Nov 2026): wrong French taught, wrong answers
credited, a right answer refused, an item back against its own schedule.

Each case uses the walk's exact strings; the rows are those stored in the walk databases.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.fault_quality import drillable_errors, learner_own_fault

# ---------------------------------------------------------------------------
# A. «je vends» «corrected» to «je vende» (B, days 3–13)
# ---------------------------------------------------------------------------


def _row(original: str, correction: str, *, source_type: str = "mission") -> SimpleNamespace:
    return SimpleNamespace(
        original_text=original,
        correction=correction,
        source_type=source_type,
        source_attempt_id=None,
        error_metadata={},
    )


def test_a_letter_s_subjunctive_fix_without_its_clause_is_not_a_review_item() -> None:
    # The Courrier's correction was right in «il faut que je vends …»; stored bare,
    # it «corrects» right French into wrong French.
    assert not learner_own_fault(wrong="je vends", correct="je vende")
    # The learner's answer to that card became a second fault: same verdict.
    assert not learner_own_fault(wrong="je avais vendu", correct="je vende")
    rows = [_row("je vends", "je vende"), _row("je avais vendu", "je vende", source_type="atelier")]
    assert drillable_errors(None, rows) == []


def test_the_same_fix_inside_its_clause_stays() -> None:
    assert learner_own_fault(wrong="il faut que je vends", correct="il faut que je vende")
    assert learner_own_fault(
        wrong="je vends",
        correct="je vende",
        submitted="Il faut que je vends son appartement.",
        item=None,
    )
    # A fix that changes no tense is untouched by the check.
    assert learner_own_fault(wrong="un valise", correct="une valise")


def test_due_error_records_never_hands_out_the_bare_subjunctive(db_session) -> None:
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from app.db.models.error import UserError
    from app.db.models.user import User
    from app.services.error_memory import ErrorMemoryService

    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="x", target_language="fr", native_language="en")
    db_session.add(user)
    db_session.flush()
    past = datetime.now(UTC) - timedelta(days=1)
    bad = UserError(
        id=uuid4(), user_id=user.id, error_category="grammar", original_text="je vends", correction="je vende",
        occurrences=1, state="repairing", next_review_date=past, source_type="mission",
    )
    good = UserError(
        id=uuid4(), user_id=user.id, error_category="grammar", original_text="un valise", correction="une valise",
        occurrences=1, state="repairing", next_review_date=past, source_type="atelier",
    )
    db_session.add_all([bad, good])
    db_session.flush()
    ids = {row.id for row in ErrorMemoryService(db_session).due_error_records(user)}
    assert good.id in ids
    assert bad.id not in ids


# ---------------------------------------------------------------------------
# B. Wrong answers credited
# ---------------------------------------------------------------------------


def test_le_image_fails_the_article_rule_check() -> None:
    """A1 day 7, «Kurz prüfen» (a test-out): the detector hit «le image» and the unit's
    trap («le école») is a window, so nothing refused the missing elision."""

    from app.services.forge_grading import free_use_acceptable

    concept = SimpleNamespace(id=5, external_id="FR2_A11_LE_LA", name="Le, la, l', les")
    verdict = free_use_acceptable(concept, "Où est le image ?", ["Où est le tableau ?"])
    assert verdict["acceptable"] is False
    assert verdict["wrong"] == "le image"
    assert free_use_acceptable(concept, "Où est l'image ?", ["Où est le tableau ?"])["acceptable"] is True


def test_nous_sommes_drole_is_not_right_even_when_the_model_says_so() -> None:
    """A1 day 13: the model said right (with a note «drôles»), and the rules had no
    predicate-adjective agreement to hold it to."""

    from app.services.correction_contract import deterministic_edits
    from app.services.forge_grading import held_to_the_rules

    held = held_to_the_rules({"verdict": "correct", "score_0_4": 4.0, "errata": []}, "Nous sommes drôle.", "de")
    assert held["verdict"] == "partial"
    assert held["corrected_answer"] == "Nous sommes drôles."
    hint = held["errata"][0]["hint"]
    assert "drôles" not in hint  # no solution before a retry
    for right in ("Nous sommes drôles.", "On est drôle.", "Vous êtes drôle.", "Nous sommes à Lyon.", "Ils sont médecins."):
        assert deterministic_edits(right) == [], right
    # The learner's gender is never read: «fatigués» or «fatiguées» is the learner's
    # call, so after «nous» only an adjective the same in both genders is changed.
    assert deterministic_edits("Nous sommes fatigué.") == []
    assert [e.replacement for e in deterministic_edits("Ils sont très calme.")] == ["calmes"]


def test_quatre_vingts_dix_does_not_meet_the_numbers_unit() -> None:
    """B1 day 14, Rappel «Écris une phrase à toi»: the unit's detector saw a number ≥ 70."""

    from app.services.correction_contract import deterministic_edits
    from app.services.journey_learning import _rules_find_a_slip

    line = "Marin a quatre-vingts-dix ans et Margaux a soixante-dix-sept ans."
    assert _rules_find_a_slip(line)
    assert [(e.span, e.replacement) for e in deterministic_edits(line)] == [("quatre-vingts", "quatre-vingt")]
    assert not _rules_find_a_slip("Marin a quatre-vingt-dix ans et Margaux a soixante-dix-sept ans.")
    assert not _rules_find_a_slip("Il a quatre-vingts ans.")
    assert not _rules_find_a_slip("Ça coûte deux cents euros.")


def test_secrete_is_not_secrete_with_its_agreement() -> None:
    """B1 day 14, «Ta phrase» «une porte secret»: the fix is the feminine «secrète»."""

    from app.services.answer_acceptance import judge

    verdict = judge("une porte secrete", ["une porte secrète"])
    assert not verdict.correct
    assert verdict.note == "accent"
    assert not judge("la premiere fois", ["la première fois"]).correct
    # A spelling accent elsewhere stays forgiven.
    assert judge("Il est tres grand.", ["Il est très grand."]).correct
    assert judge("ma mere", ["ma mère"]).correct


# ---------------------------------------------------------------------------
# C. A right answer refused: A1 day 2, the rule check of «être»
# ---------------------------------------------------------------------------


def test_je_suis_avec_lila_au_marche_is_right_on_the_rule_check_item(db_session, monkeypatch) -> None:
    """The walk's item: «Sag auf Französisch: „Ich bin mit Lila auf dem Markt.“». The local
    grade said right, the fallback's ``missing_targets`` stayed on the correction and the
    screen read it as «Die Aufgabe … erfüllt die Aufgabe noch nicht» (#954, fixed by #979,
    which the walk's build did not have)."""

    from app.config import settings
    from app.db.models.grammar import GrammarConcept
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService
    from app.services.grammar_catalog import FrenchCoreGrammarCatalog
    from tests.test_atelier import _user
    from tests.test_forge_integration import _right
    from tests.test_rule_check_one_verdict_954 import client_says_right

    learner = "Je suis avec Lila au marché."
    monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_ENABLED", False)
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    try:
        concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A11_ETRE").one()
        user = _user(db_session)
        user.native_language = "de"
        db_session.commit()
        forge = ForgeService(db_session)
        session = forge.start_test_out(user=user, concept_id=concept.id, short=True)
        service = AtelierCorrectionService(db_session)
        free_correction = None
        while (nxt := forge.next_item(user=user, session=session)) is not None:
            free = nxt["round"] not in {"recognize", "transform"}
            exercise_id = f"forge:{concept.id}:{nxt['round']}:{nxt['item_id']}"
            override = None
            if free:
                override = service._prompt_payload(concept, nxt["round"], nxt["mode"], exercise_id, user=user, session=session)
                override["items"][0] = {
                    **override["items"][0],
                    "prompt": 'Say in French: "I am at the market with Lila."',
                    "goal_l10n": {"de": "Sag auf Französisch: „Ich bin mit Lila auf dem Markt.“"},
                    "example_answer": "Je suis au marché avec Lila.",
                    "accepted_answers": ["Je suis au marché avec Lila.", "Je suis avec Lila au marché."],
                }
            attempt = service.submit_attempt(
                session=session,
                user=user,
                concept=concept,
                round_name=nxt["round"],
                mode="rewrite" if nxt["round"] == "transform" else nxt["mode"],
                exercise_id=exercise_id,
                answer_payload={"text": learner} if free else _right(nxt["item"], nxt["round"], nxt["mode"]),
                prompt_payload_override=override,
            )
            if free:
                free_correction = attempt.correction_payload
            forge.observe_attempt(user=user, session=session, attempt=attempt)
    finally:
        FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
    assert free_correction is not None
    assert client_says_right(free_correction), free_correction.get("missing_targets")
