"""WP-35 — «Votre dossier»: the learner model as a service.

What these hold down, one property per test:

1. **The page states a belief and names its source.** A learner who only ever
   declared a level is told so, with no confidence number attached; a placed
   learner gets the placement's own confidence, date and dimensions.
2. **Nothing is re-scored.** The capability states come out of
   ``build_capability_summary`` byte for byte (CONTRACTS §8: two rubrics is how
   the recap and the progress endpoint came to disagree), and every capability
   evidence row carries the journey it happened in.
3. **Today's «because» is read from the plan.** A mistake recorded *after* the
   plan was built never appears in it — the WP-28 rule, on a second surface.
4. **Reading the dossier changes nothing.** Not a due date, not a state, not a
   CEFR history row.
5. **A claim is never trusted.** «Je connais déjà» is two items from the
   learner's own records; both right advances the schedule through the SRS
   services, anything else leaves it exactly as it was — and the claim is on the
   ledger either way. A source scan pins that the advance is unreachable except
   from the passing branch.
"""
from __future__ import annotations

import ast
import pathlib
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models.daily_journey import DailyJourney
from app.db.models.error import UserError
from app.db.models.pilot_event import PilotEvent
from app.db.models.placement import PlacementSession
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.error_memory import (
    ERROR_STATE_MASTERED,
    ERROR_STATE_OPEN,
    ERROR_STATE_REPAIRING,
    ErrorMemoryService,
)
from app.services.learner_model import (
    CLAIM_EVENT_TYPE,
    CLAIM_ITEMS_REQUIRED,
    CLAIM_KIND_ERRATUM,
    CLAIM_KIND_WORD,
    CLAIM_STAGE_CHECKED,
    CLAIM_STAGE_OPENED,
    DOSSIER_VERSION,
    VERDICT_NOT_YET,
    VERDICT_UNVERIFIABLE,
    VERDICT_VERIFIED,
    ClaimRefused,
    build_claim_check,
    build_dossier,
    record_claim_opened,
    verify_claim,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE = REPO_ROOT / "app/services/learner_model.py"

NOW = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _user(db_session, *, level: str = "A2", native: str = "en") -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
        native_language=native,
        proficiency_level=level,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _erratum(
    db_session,
    user: User,
    *,
    label: str = "Accord en genre",
    learner_text: str = "une homme",
    corrected: str = "un homme",
) -> UserError:
    ErrorMemoryService(db_session).record_erratum(
        user=user,
        erratum={
            "display_label": label,
            "learner_text": learner_text,
            "corrected_target": corrected,
            "why_wrong": "homme est masculin",
            "repair_hint": corrected,
            "task_error_type": label,
            "severity": 2,
        },
        source_type="daily_journey",
    )
    db_session.commit()
    return (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id, UserError.display_label == label)
        .order_by(UserError.created_at.desc())
        .first()
    )


def _add(db_session, instance):
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    return instance


def _vocabulary_word(db_session, **overrides) -> VocabularyWord:
    word = VocabularyWord(
        language=overrides.pop("language", "fr"),
        word=overrides.pop("word", "facture"),
        normalized_word=overrides.pop("normalized_word", "facture"),
        english_translation=overrides.pop("english_translation", "invoice"),
        german_translation=overrides.pop("german_translation", "die Rechnung"),
        example_sentence=overrides.pop("example_sentence", "Je paie la facture demain."),
        is_anki_card=True,
        direction="fr_to_de",
        **overrides,
    )
    return _add(db_session, word)


def _journey(db_session, user: User, *, because: dict | None, day: date | None = None) -> DailyJourney:
    journey = DailyJourney(
        user_id=user.id,
        local_date=day or datetime.now(UTC).date(),
        timezone="UTC",
        status="active",
        plan_selection={"because": because} if because is not None else {},
    )
    return _add(db_session, journey)


def _claims(db_session, user: User) -> list[PilotEvent]:
    return (
        db_session.query(PilotEvent)
        .filter(PilotEvent.user_id == user.id, PilotEvent.event_type == CLAIM_EVENT_TYPE)
        .order_by(PilotEvent.occurred_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# 1. What the app believes, and on whose authority
# ---------------------------------------------------------------------------


def test_a_declared_level_is_reported_as_declared_and_carries_no_confidence(db_session) -> None:
    """A signup dropdown is not a measurement, and must not wear a number."""

    user = _user(db_session, level="A2")
    level = build_dossier(db_session, user=user).level

    assert level["available"] is True
    assert level["estimate_source"] == "declared"
    assert level["confidence"] is None
    assert level["verified"] is False
    assert level["evidence"]["kind"] == "declaration"


def test_a_placement_is_reported_with_its_confidence_date_and_dimensions(db_session) -> None:
    user = _user(db_session, level="A2")
    session = PlacementSession(
        user_id=user.id,
        status="complete",
        current_band="B1.1",
        turns=[],
        estimate={
            "graded_turns": 5,
            "dimensions": {"range": 2.4, "accuracy": 2.0},
            "dimension_labels": {"range": "Étendue", "accuracy": "Correction"},
        },
        estimate_level="B1.1",
        confidence=0.72,
        completed_at=NOW,
    )
    _add(db_session, session)

    level = build_dossier(db_session, user=user).level

    assert level["estimate_source"] == "placement"
    assert level["estimate"] == "B1.1"
    assert level["confidence"] == pytest.approx(0.72)
    assert level["placement"]["dimensions"]["range"] == pytest.approx(2.4)
    assert level["placement"]["dimension_labels"]["range"] == "Étendue"
    assert level["evidence"]["kind"] == "placement"
    assert level["evidence"]["on"] == NOW.date().isoformat()
    # WP-25 §4.5: a placement measured the learner's French; their in-app
    # counters are still zero, so the page must not draw a verified level.
    assert level["verified"] is False
    assert level["status"] == "unverified"


def test_the_breakdown_is_the_cefr_services_own_and_is_not_recomputed(db_session) -> None:
    from app.services.cefr_progress import CEFRProgressService

    user = _user(db_session, level="B1")
    expected = CEFRProgressService(db_session).recompute(user, persist=False)

    level = build_dossier(db_session, user=user).level

    assert level["breakdown"] == expected["breakdown"]
    assert level["estimate"] == expected["estimate"]


def test_opening_the_dossier_writes_no_cefr_history_row(db_session) -> None:
    """The page is a read: it must not persist an estimate to be read."""

    from app.db.models.cefr import UserCEFRProgressHistory

    user = _user(db_session)
    before = db_session.query(UserCEFRProgressHistory).count()
    build_dossier(db_session, user=user)
    assert db_session.query(UserCEFRProgressHistory).count() == before


# ---------------------------------------------------------------------------
# 2. Capabilities — one rubric, with the journey behind each row
# ---------------------------------------------------------------------------


def test_capability_states_come_from_the_one_rubric_verbatim(db_session) -> None:
    from app.services.journey_capabilities import build_capability_summary

    user = _user(db_session)
    view = build_capability_summary(db_session, user=user, control_language="en")
    dossier = build_dossier(db_session, user=user)

    assert [item["key"] for item in dossier.capabilities] == [
        str(summary.capability_key) for summary in view.capabilities
    ]
    assert [item["state"] for item in dossier.capabilities] == [
        str(summary.state) for summary in view.capabilities
    ]
    assert {item["rubric_version"] for item in dossier.capabilities} == {view.rubric_version}


def test_every_capability_evidence_row_names_the_journey_it_happened_in(db_session) -> None:
    """«Every number links to its evidence»: the rubric gives the date, this gives the journey."""

    from tests.test_journey_capabilities import _independent_journey
    from tests.test_journey_capabilities import _user as _capability_user

    user = _capability_user(db_session)
    journey = _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    db_session.commit()

    dossier = build_dossier(db_session, user=user)
    cafe = next(item for item in dossier.capabilities if item["key"] == "order_at_cafe")

    assert cafe["state"] in {"with_support", "independent_once", "used_again_later"}
    assert cafe["evidence"], "a state above not_tried must show its evidence"
    row = cafe["evidence"][0]
    assert row["journey_id"] == str(journey.id)
    assert row["on"] == "2026-09-05"


def test_the_service_never_defines_a_second_rubric(db_session) -> None:
    """CONTRACTS §8: the rubric's four states may not be spelled out here."""

    source = SERVICE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigned = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    # No local ladder, and no local list of the rubric's states.
    assert "not_tried" not in source
    assert "with_support" not in source
    assert "used_again_later" not in source
    assert "CAPABILITY_STATES" not in assigned


# ---------------------------------------------------------------------------
# 3. Today's «because», read from the plan
# ---------------------------------------------------------------------------


def test_the_because_line_is_read_from_todays_plan(db_session) -> None:
    user = _user(db_session)
    payload = {
        "kind": "erratum",
        "reason": "erratum:2f9c",
        "label": "l’accord en genre",
        "example": "une homme → un homme",
    }
    journey = _journey(db_session, user, because=payload)

    today = build_dossier(db_session, user=user).today

    assert today["has_journey"] is True
    assert today["journey_id"] == str(journey.id)
    assert today["because"]["label"] == "l’accord en genre"
    assert today["evidence"]["journey_id"] == str(journey.id)


def test_a_mistake_recorded_after_the_plan_never_enters_the_because(db_session) -> None:
    """WP-28: the payload belongs to the scene the learner has, not to the queue."""

    user = _user(db_session)
    _journey(db_session, user, because=None)
    _erratum(db_session, user, label="Article partitif")

    today = build_dossier(db_session, user=user).today

    assert today["has_journey"] is True
    assert today["because"] is None


def test_without_a_journey_today_owes_no_line_at_all(db_session) -> None:
    user = _user(db_session)
    _journey(
        db_session,
        user,
        because={"kind": "erratum", "label": "hier"},
        day=datetime.now(UTC).date() - timedelta(days=1),
    )

    today = build_dossier(db_session, user=user).today

    assert today["has_journey"] is False
    assert today["because"] is None


# ---------------------------------------------------------------------------
# 4. Errata and vocabulary stock
# ---------------------------------------------------------------------------


def test_errata_are_grouped_by_state_with_their_next_due_date(db_session) -> None:
    user = _user(db_session)
    open_row = _erratum(db_session, user, label="Accord en genre")
    repairing = _erratum(db_session, user, label="Passé composé", learner_text="j’ai allé", corrected="je suis allé")
    repairing.state = ERROR_STATE_REPAIRING
    mastered = _erratum(db_session, user, label="Subjonctif", learner_text="il faut que je vais", corrected="il faut que j’aille")
    mastered.state = ERROR_STATE_MASTERED
    db_session.commit()

    errata = build_dossier(db_session, user=user).errata

    assert errata["available"] is True
    assert [item["id"] for item in errata["by_state"][ERROR_STATE_OPEN]] == [str(open_row.id)]
    assert [item["id"] for item in errata["by_state"][ERROR_STATE_REPAIRING]] == [str(repairing.id)]
    assert [item["id"] for item in errata["by_state"][ERROR_STATE_MASTERED]] == [str(mastered.id)]
    assert errata["by_state"][ERROR_STATE_OPEN][0]["next_review_date"] is not None
    # A finished erratum is not claimable: there is nothing left to declare.
    assert errata["by_state"][ERROR_STATE_MASTERED][0]["claimable"] is False
    assert errata["by_state"][ERROR_STATE_OPEN][0]["evidence"]["reference"] == str(open_row.id)


def test_reading_the_dossier_reschedules_nothing(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    before = (error.next_review_date, error.reps, error.state, error.ease_factor)

    build_dossier(db_session, user=user)
    db_session.refresh(error)

    assert (error.next_review_date, error.reps, error.state, error.ease_factor) == before


def test_the_vocabulary_stock_labels_what_is_evidence_and_what_is_assumed(db_session) -> None:
    user = _user(db_session)
    _vocabulary_word(db_session)

    stock = build_dossier(db_session, user=user).vocabulary

    assert stock["nailed_rule"]["retrievability"] == pytest.approx(0.9)
    if stock["known"] is not None:
        # WP-29 keeps the two halves apart on purpose: nailed words are
        # evidence, the core list is an assumption from the estimate.
        assert "nailed_words" in stock["known"]
        assert "core_words" in stock["known"]
        assert stock["known"]["estimate_source"] in {"declared", "placement", "measured"}


# ---------------------------------------------------------------------------
# 5. «Je connais déjà» — the claim, and the check in front of it
# ---------------------------------------------------------------------------


def test_an_erratum_claim_asks_two_items_and_ships_no_answers(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)

    check = build_claim_check(
        db_session, user=user, kind=CLAIM_KIND_ERRATUM, target_id=str(error.id)
    )

    assert check.verifiable is True
    assert len(check.items) == CLAIM_ITEMS_REQUIRED
    assert [item.kind for item in check.items] == ["repair", "cloze"]
    public = check.as_public()
    assert "accepted" not in str(public)
    # The cloze asks for the token that was actually wrong, not for the sentence.
    assert check.items[1].accepted == ("un",)
    assert "un" not in check.items[1].prompt_fr.split()


def test_two_right_answers_advance_the_schedule_through_the_srs_service(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    before_reps = int(error.reps or 0)

    verdict = verify_claim(
        db_session,
        user=user,
        kind=CLAIM_KIND_ERRATUM,
        target_id=str(error.id),
        answers=["un homme", "un"],
    )
    db_session.commit()
    db_session.refresh(error)

    assert verdict.verdict == VERDICT_VERIFIED
    assert verdict.advanced is True
    assert verdict.items_correct == CLAIM_ITEMS_REQUIRED
    # The lifecycle is WP-24's, not this package's: one spaced repair moves an
    # open erratum to `repairing`, never straight to `mastered`.
    assert error.state == ERROR_STATE_REPAIRING
    assert int(error.reps or 0) == before_reps + 1
    assert error.mastery_streak == 1


def test_a_failed_claim_costs_the_learner_nothing(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    before = (
        error.next_review_date,
        error.reps,
        error.lapses,
        error.state,
        error.ease_factor,
        error.mastery_streak,
    )

    verdict = verify_claim(
        db_session,
        user=user,
        kind=CLAIM_KIND_ERRATUM,
        target_id=str(error.id),
        answers=["une homme", "une"],
    )
    db_session.commit()
    db_session.refresh(error)

    assert verdict.verdict == VERDICT_NOT_YET
    assert verdict.advanced is False
    assert (
        error.next_review_date,
        error.reps,
        error.lapses,
        error.state,
        error.ease_factor,
        error.mastery_streak,
    ) == before


def test_one_right_answer_out_of_two_is_not_a_pass(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)

    verdict = verify_claim(
        db_session,
        user=user,
        kind=CLAIM_KIND_ERRATUM,
        target_id=str(error.id),
        answers=["un homme", "une"],
    )

    assert verdict.items_correct == 1
    assert verdict.verdict == VERDICT_NOT_YET
    assert verdict.advanced is False


def test_the_claim_is_recorded_whether_it_is_verified_or_not(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)

    check = build_claim_check(
        db_session, user=user, kind=CLAIM_KIND_ERRATUM, target_id=str(error.id)
    )
    record_claim_opened(db_session, user=user, check=check)
    verify_claim(
        db_session,
        user=user,
        kind=CLAIM_KIND_ERRATUM,
        target_id=str(error.id),
        answers=["", ""],
    )
    db_session.commit()

    stages = [dict(row.payload or {}).get("stage") for row in _claims(db_session, user)]
    assert stages == [CLAIM_STAGE_OPENED, CLAIM_STAGE_CHECKED]
    verdicts = [dict(row.payload or {}).get("verdict") for row in _claims(db_session, user)]
    assert verdicts[-1] == VERDICT_NOT_YET


def test_an_abandoned_claim_still_leaves_a_trace(db_session) -> None:
    """Saying «je connais déjà» and walking away is still something the learner said."""

    user = _user(db_session)
    error = _erratum(db_session, user)
    check = build_claim_check(
        db_session, user=user, kind=CLAIM_KIND_ERRATUM, target_id=str(error.id)
    )
    record_claim_opened(db_session, user=user, check=check)
    db_session.commit()

    rows = _claims(db_session, user)
    assert len(rows) == 1
    assert dict(rows[0].payload or {})["stage"] == CLAIM_STAGE_OPENED
    assert rows[0].entity_id == str(error.id)


def test_a_mastered_erratum_has_nothing_left_to_verify(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    error.state = ERROR_STATE_MASTERED
    db_session.commit()

    verdict = verify_claim(
        db_session,
        user=user,
        kind=CLAIM_KIND_ERRATUM,
        target_id=str(error.id),
        answers=["un homme", "un"],
    )

    assert verdict.verdict == VERDICT_UNVERIFIABLE
    assert verdict.advanced is False
    assert "acquis" in verdict.message_fr


def test_an_erratum_with_no_second_honest_question_is_unverifiable(db_session) -> None:
    """No cloze, no sibling: the claim is refused rather than passed on one item."""

    user = _user(db_session)
    error = _erratum(db_session, user, label="Mot isolé", learner_text="", corrected="bonjour")

    check = build_claim_check(
        db_session, user=user, kind=CLAIM_KIND_ERRATUM, target_id=str(error.id)
    )

    assert check.verifiable is False
    assert check.reason == "no_two_items"
    assert check.message_fr and "vérifier" in check.message_fr


def test_a_sibling_erratum_stands_in_when_no_cloze_can_be_derived(db_session) -> None:
    user = _user(db_session)
    first = _erratum(db_session, user, label="Mot isolé", learner_text="", corrected="bonjour")
    sibling = _erratum(db_session, user, label="Autre", learner_text="", corrected="bonsoir")
    sibling.memory_key = first.memory_key
    db_session.commit()

    check = build_claim_check(
        db_session, user=user, kind=CLAIM_KIND_ERRATUM, target_id=str(first.id)
    )

    assert check.verifiable is True
    assert [item.kind for item in check.items] == ["repair", "repair"]


def test_a_word_claim_asks_for_production_then_the_word_in_its_sentence(db_session) -> None:
    user = _user(db_session, native="de")
    word = _vocabulary_word(db_session)

    check = build_claim_check(
        db_session, user=user, kind=CLAIM_KIND_WORD, target_id=str(word.id)
    )

    assert check.verifiable is True
    assert [item.kind for item in check.items] == ["production", "cloze"]
    assert "Rechnung" in check.items[0].prompt_fr
    assert "facture" not in check.items[1].prompt_fr


def test_a_verified_word_claim_advances_the_vocabulary_schedule(db_session) -> None:
    from app.db.models.progress import UserVocabularyProgress

    user = _user(db_session, native="de")
    word = _vocabulary_word(db_session)

    verdict = verify_claim(
        db_session,
        user=user,
        kind=CLAIM_KIND_WORD,
        target_id=str(word.id),
        answers=["facture", "facture"],
    )
    db_session.commit()

    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == word.id,
        )
        .first()
    )
    assert verdict.verdict == VERDICT_VERIFIED
    assert verdict.advanced is True
    assert progress is not None
    assert progress.next_review_date is not None


def test_a_failed_word_claim_creates_no_progress_and_no_erratum(db_session) -> None:
    from app.db.models.progress import UserVocabularyProgress

    user = _user(db_session, native="de")
    word = _vocabulary_word(db_session)

    verdict = verify_claim(
        db_session,
        user=user,
        kind=CLAIM_KIND_WORD,
        target_id=str(word.id),
        answers=["facteur", "facteur"],
    )
    db_session.commit()

    assert verdict.verdict == VERDICT_NOT_YET
    assert (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id)
        .count()
        == 0
    )
    # A wrong answer to a claim the learner volunteered is not a new mistake.
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 0


def test_a_claim_about_someone_elses_record_finds_nothing(db_session) -> None:
    owner = _user(db_session)
    stranger = _user(db_session)
    error = _erratum(db_session, owner)

    check = build_claim_check(
        db_session, user=stranger, kind=CLAIM_KIND_ERRATUM, target_id=str(error.id)
    )

    assert check.verifiable is False
    assert check.reason == "not_found"


def test_an_unknown_claim_kind_is_refused(db_session) -> None:
    user = _user(db_session)
    with pytest.raises(ClaimRefused):
        build_claim_check(db_session, user=user, kind="mood", target_id="1")


# ---------------------------------------------------------------------------
# 6. The rule itself, read out of the source
# ---------------------------------------------------------------------------


def test_no_path_advances_a_schedule_without_a_passing_check() -> None:
    """The advance is called from one place, inside ``if passed``.

    A source scan rather than a behavioural test, because the property is
    *absence*: a future branch that advanced on a claim alone would pass every
    behavioural test above and still be the defect this package exists to avoid.
    """

    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    call_sites: list[ast.Call] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_advance_after_pass"
    ]
    assert len(call_sites) == 1, "the advance must have exactly one caller"

    guarded = False
    node: ast.AST | None = call_sites[0]
    while node is not None:
        parent = parents.get(node)
        if isinstance(parent, ast.If) and parent.body and node in ast.walk(parent.body[0]):
            if isinstance(parent.test, ast.Name) and parent.test.id == "passed":
                guarded = True
                break
        node = parent
    assert guarded, "the advance must sit inside `if passed:`"

    # And the writers themselves live only in that one function.
    writers = {"review_error", "apply"}
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        used = {
            child.func.attr
            for child in ast.walk(function)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
        }
        if used & writers:
            assert function.name == "_advance_after_pass", (
                f"{function.name} writes to a scheduler; only _advance_after_pass may"
            )


def test_the_schedule_is_never_written_by_column() -> None:
    """No `error.next_review_date = …`, no `progress.state = …` in this module."""

    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    forbidden = {
        "next_review_date",
        "scheduled_days",
        "ease_factor",
        "mastery_streak",
        "state",
        "stability",
        "difficulty",
        "reps",
        "lapses",
        "proficiency_score",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                assert target.attr not in forbidden, f"direct column write: {target.attr}"


def test_the_learner_facing_copy_in_the_service_is_french() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    start = source.index("_ITEM_COPY")
    end = source.index("# ------", start)
    copy = source[start:end]
    for english in ("Rewrite", "Complete the", "Write the word", "The meaning", "already known"):
        assert english not in copy
    assert "Réécrivez" in copy
    assert "Complétez" in copy


def test_the_version_is_declared_once() -> None:
    assert DOSSIER_VERSION == "learner-model-v1"
