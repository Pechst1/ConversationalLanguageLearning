# ruff: noqa: F811 - the v2 fixture is imported by name and requested as an argument
"""#169 — «Forge today's rule» keeps to today's rule.

Six nights in a row a walk saw the day's Forge alternate today's rule with a
rule the learner was never taught («Un, une, des» beside the passé composé on
day 1; articles after a false correction for A1 personas, #318): half the
items, starting at Level 1.

Two mechanisms let it in. The picker took any row the review queue called due
(a scene's exposure, an erratum's concept, a row touched today) as a «due
rule», and ``introduced_at`` — stamped by the first evidence on *any* surface —
passed for «met». And the core never served one rule twice in a row, so any
second rule took every other item, whatever its share.

The contract now lives in one place (``forge_picker``: ``DAY_ORIGINS``,
``DAY_REVIEW_RULES``, ``DAY_REVIEW_SHARE``, ``day_review_eligible``): the day's
step is today's rule, plus at most one rule the learner was taught and that is
due, for at most a quarter of the items, never before item 4, each labelled.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.forge import ForgeState, ForgeUnit, Role
from app.core.srs.memory import Evidence, EvidenceFormat
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.services import concept_life, forge_picker
from app.services.grammar import GrammarService, apply_grammar_evidence
from tests.test_wp_s4_one_picker import v2  # noqa: F401 - fixture

PASSWORD = "forge-secure-169"


def _learner(client: TestClient, db: Session, *, cefr: str) -> tuple[User, dict[str, str]]:
    email = f"forge-169-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "target_language": "fr",
            "native_language": "en",
            "cefr_estimate": cefr,
        },
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    user = db.query(User).filter(User.email == email).one()
    return user, {"Authorization": f"Bearer {token}"}


def _articles(db: Session) -> GrammarConcept:
    concept = (
        db.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True), GrammarConcept.language == "fr", GrammarConcept.name.ilike("%indefinite article%"))
        .order_by(GrammarConcept.difficulty_order, GrammarConcept.id)
        .first()
    ) or (
        db.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True), GrammarConcept.language == "fr", GrammarConcept.external_id.isnot(None))
        .order_by(GrammarConcept.difficulty_order, GrammarConcept.id)
        .first()
    )
    assert concept is not None
    return concept


def _touch_untaught_rule(db: Session, user: User, concept: GrammarConcept, *, now: datetime) -> None:
    """What the walks saw before the Forge: the day's scene shows the rule
    (exposure: first evidence, so ``introduced_at`` and a schedule) and a
    correction names it (an erratum, due now). Nobody taught it."""

    GrammarService(db).mark_concepts_practiced_in_context(user=user, concept_ids=[concept.id])
    db.add(
        UserError(
            user_id=user.id,
            concept_id=concept.id,
            error_category="grammar",
            error_pattern="article",
            original_text="un appart",
            correction="un appartement",
            next_review_date=now - timedelta(hours=1),
            occurrences=2,
        )
    )
    db.commit()


def _start_day_forge(client: TestClient, headers: dict[str, str], today_id: int | None) -> dict:
    """The day's grammar step: ``/atelier?mode=forge&concept=<id>&budget=300&from=day``."""

    body: dict = {"origin": "after_day", "budget_seconds": 300}
    if today_id is not None:
        body["preferred_concept_id"] = today_id
    response = client.post("/api/v1/atelier/sessions", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _serve_all(forge: dict) -> list[tuple[int, str]]:
    """Every slot the séance would serve, all answered right (one rule per item)."""

    state = ForgeState.from_dict(forge)
    served: list[tuple[int, str]] = []
    while (slot := state.next_slot()) is not None:
        served.append((slot.concept_id, slot.role))
        state.history.append({"concept_id": slot.concept_id, "role": slot.role, "rung": slot.rung})
        track = state.track(slot.concept_id)
        track.served += 1
    return served


def _assert_only_today_or_taught_and_due(db: Session, user: User, served: list[tuple[int, str]], today_id: int) -> None:
    now = datetime.now(UTC)
    rows = {
        row.concept_id: row
        for row in db.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user.id).all()
    }
    for position, (concept_id, role) in enumerate(served, start=1):
        if concept_id == today_id:
            assert role == Role.TODAY.value
            continue
        assert forge_picker.day_review_eligible(rows.get(concept_id), now=now), (
            f"item {position}: rule {concept_id} was never taught or is not due"
        )
        assert role == Role.DUE.value, "a mixed-in item carries its role, so the page labels it «Review»"


def test_day_one_forge_for_a_fresh_learner_is_todays_rule_only(client: TestClient, db_session: Session, v2) -> None:
    user, headers = _learner(client, db_session, cefr="A2.1")
    now = datetime.now(UTC)
    today_id = forge_picker.forge_anchor_id(db_session, user, now)
    assert today_id is not None
    # The journey's Règle teaches today's rule.
    concept_life.mark_introduced(db_session, user=user, concept_id=today_id, now=now - timedelta(minutes=20))
    articles = _articles(db_session)
    assert articles.id != today_id
    _touch_untaught_rule(db_session, user, articles, now=now)

    started = _start_day_forge(client, headers, today_id)
    forge = started["quote"]["forge"]
    assert [unit["concept_id"] for unit in forge["units"]] == [today_id], forge["units"]
    served = _serve_all(forge)
    assert served and served[0] == (today_id, "today")
    _assert_only_today_or_taught_and_due(db_session, user, served, today_id)
    assert articles.id not in {concept_id for concept_id, _ in served}


def test_an_a1_learner_after_an_erratum_keeps_to_todays_rule(client: TestClient, db_session: Session, v2) -> None:
    """#318's path: a (false) correction points at the articles; the day's Forge
    must not pull them in beside today's rule."""

    user, headers = _learner(client, db_session, cefr="A1.1")
    now = datetime.now(UTC)
    today_id = forge_picker.forge_anchor_id(db_session, user, now)
    concept_life.mark_introduced(db_session, user=user, concept_id=today_id, now=now - timedelta(minutes=20))
    # The rule after it in teaching order, never taught: the erratum's concept.
    other = (
        db_session.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True), GrammarConcept.language == "fr", GrammarConcept.external_id.isnot(None), GrammarConcept.id != today_id)
        .order_by(GrammarConcept.difficulty_order, GrammarConcept.id)
        .first()
    )
    db_session.add(
        UserError(
            user_id=user.id,
            concept_id=other.id,
            error_category="grammar",
            original_text="Le tasse",
            correction="La tasse",
            next_review_date=now - timedelta(hours=2),
            occurrences=2,
        )
    )
    # The correction also counted as a miss on the rule: first evidence, so the
    # row says «introduced» and is due tomorrow — yet nothing taught it.
    progress = GrammarService(db_session).get_or_create_progress(user_id=user.id, concept_id=other.id)
    apply_grammar_evidence(progress, Evidence(EvidenceFormat.PRODUCE, correct=False), now=now - timedelta(minutes=10), score=2.0)
    db_session.add(progress)
    db_session.commit()

    forge = _start_day_forge(client, headers, today_id)["quote"]["forge"]
    served = _serve_all(forge)
    _assert_only_today_or_taught_and_due(db_session, user, served, today_id)
    assert other.id not in {concept_id for concept_id, _ in served}


def test_a_taught_due_rule_is_a_small_labelled_share_after_todays_first_items(
    client: TestClient, db_session: Session, v2
) -> None:
    user, headers = _learner(client, db_session, cefr="A2.1")
    now = datetime.now(UTC)
    today_id = forge_picker.forge_anchor_id(db_session, user, now)
    concept_life.mark_introduced(db_session, user=user, concept_id=today_id, now=now - timedelta(minutes=20))
    # Yesterday's rule: forged yesterday, due now.
    yesterday = (
        db_session.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True), GrammarConcept.language == "fr", GrammarConcept.external_id.isnot(None), GrammarConcept.id != today_id)
        .order_by(GrammarConcept.difficulty_order, GrammarConcept.id)
        .first()
    )
    db_session.add(
        UserGrammarProgress(
            user_id=user.id, concept_id=yesterday.id, score=6.0, reps=3, stability=1.0, forge_rung=3,
            introduced_at=now - timedelta(days=1), last_review=now - timedelta(days=1),
            next_review=now - timedelta(hours=1),
        )
    )
    db_session.commit()

    forge = _start_day_forge(client, headers, today_id)["quote"]["forge"]
    assert [(unit["concept_id"], unit["role"]) for unit in forge["units"]] == [(today_id, "today"), (yesterday.id, "due")]
    assert forge["review_share"] == forge_picker.DAY_REVIEW_SHARE
    served = _serve_all(forge)
    _assert_only_today_or_taught_and_due(db_session, user, served, today_id)
    review_positions = [index for index, (_cid, role) in enumerate(served, start=1) if role != "today"]
    assert review_positions, "a taught, due rule is reviewed"
    assert len(review_positions) <= forge_picker.DAY_REVIEW_SHARE * len(served)
    assert min(review_positions) >= 4, "today's rule has the first items"
    assert all(b - a > 1 for a, b in zip(review_positions, review_positions[1:], strict=False))


def test_the_core_never_alternates_on_the_days_step() -> None:
    """The mechanism under the walks' «every other item»: never back to back
    forced a second rule into every other slot. With the day's share it may not."""

    units = [ForgeUnit(1, Role.TODAY.value, 0, is_new=True), ForgeUnit(2, Role.DUE.value, 2)]
    state = ForgeState.seance(units, length=12, review_share=forge_picker.DAY_REVIEW_SHARE)
    served = _serve_all(state.to_dict())
    assert [cid for cid, _ in served] == [1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2]
    # Without a share (a practice séance), the ordinary mix is unchanged.
    plain = _serve_all(ForgeState.seance(units, length=12).to_dict())
    assert [cid for cid, _ in plain][:4] == [1, 2, 1, 2]

