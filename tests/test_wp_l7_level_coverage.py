"""WP-L7 — the level as syllabus coverage plus a checkpoint.

Pins:
1. the coverage model: which units and words belong to a sub-band (v1 halves,
   v2 tags), what «held» and «known» mean, the percent beside the band;
2. promotion: coverage makes the épreuve ready, only a passed épreuve raises
   the level, and nothing lowers it again;
3. the checkpoint state machine (ready → failed → a week later ready → passed);
4. release day: nobody's shown level drops;
5. the prior (placement / declaration) as a floor until 40 attempts, then kept
   as far as the evidence confirms it;
6. the API the story engine uses.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.cefr import UserLevelCheckpoint
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import level_checkpoint as checkpoints
from app.services import level_coverage
from app.services.cefr_progress import (
    CEFR_LEVELS,
    DECLARED_LEVEL_EVIDENCE_ATTEMPTS,
    CEFRProgressService,
)
from app.services.grammar_catalog import FRENCH_CORE_CATALOG_V2_VERSION

NOW = datetime.now(UTC)
#: A tiny band vocabulary, so a scenario can know 80 % of it with five cards.
BAND_WORDS = frozenset({"bonjour", "merci", "café", "pain", "eau"})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_catalog(db_session):
    """Other suites leave active concepts behind; park them for this test."""

    parked = [c.id for c in db_session.query(GrammarConcept).filter(GrammarConcept.active.is_(True)).all()]
    if parked:
        db_session.query(GrammarConcept).filter(GrammarConcept.id.in_(parked)).update(
            {GrammarConcept.active: False}, synchronize_session=False
        )
        db_session.commit()
    created: list[int] = []

    def make(level: str, order: int, *, sub_band: str | None = None) -> GrammarConcept:
        concept = GrammarConcept(
            external_id=f"WPL7_{uuid.uuid4().hex[:10]}",
            language="fr",
            name=f"Unit {level} {order}",
            level=level,
            difficulty_order=order,
            active=True,
            source_refs={"syllabus": {"sub_band": sub_band}} if sub_band else {},
        )
        db_session.add(concept)
        db_session.commit()
        created.append(concept.id)
        return concept

    try:
        yield make
    finally:
        db_session.rollback()
        if created:
            db_session.query(UserGrammarProgress).filter(UserGrammarProgress.concept_id.in_(created)).delete(
                synchronize_session=False
            )
            db_session.query(GrammarConcept).filter(GrammarConcept.id.in_(created)).delete(synchronize_session=False)
        if parked:
            db_session.query(GrammarConcept).filter(GrammarConcept.id.in_(parked)).update(
                {GrammarConcept.active: True}, synchronize_session=False
            )
        db_session.commit()


@pytest.fixture()
def small_band(monkeypatch):
    monkeypatch.setattr(level_coverage, "band_words", lambda band: BAND_WORDS if band == "A1.1" else frozenset())


def _user(db_session, *, estimate: str = "A1.1", declared: str = "A1", payload: dict | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wpl7-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level=declared,
        cefr_estimate=estimate,
        cefr_estimate_payload=payload if payload is not None else {},
        daily_goal_minutes=10,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _hold(
    db_session, user: User, concept: GrammarConcept, *, stability: float = 30.0, held: bool = True
) -> None:
    """A practised unit; ``held`` writes WP-L4's «Tenue» (``held_at``)."""

    db_session.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=concept.id,
            score=8.0,
            reps=6,
            state="gefestigt",
            stability=stability,
            difficulty=4.0,
            lapses=0,
            last_review=NOW - timedelta(days=1),
            next_review=NOW - timedelta(days=1) + timedelta(days=stability),
            introduced_at=NOW - timedelta(days=40),
            held_at=NOW - timedelta(days=2) if held else None,
        )
    )
    db_session.commit()


def _know(db_session, user: User, lemma: str, **overrides) -> None:
    word = VocabularyWord(language="fr", word=lemma, normalized_word=lemma, difficulty_level=1)
    db_session.add(word)
    db_session.flush()
    fields = {
        "user_id": user.id,
        "word_id": word.id,
        "stability": 20.0,
        "difficulty": 5.0,
        "reps": 3,
        "state": "reviewing",
        "phase": "review",
        "last_review_date": NOW - timedelta(days=1),
    }
    fields.update(overrides)
    db_session.add(UserVocabularyProgress(**fields))
    db_session.commit()


def _cover_a11(db_session, user, make) -> list[GrammarConcept]:
    """Two A1 concepts (A1.1 = the first) held, four of five band words known."""

    units = [make("A1", 1), make("A1", 2)]
    _hold(db_session, user, units[0])
    for lemma in ("bonjour", "merci", "café", "pain"):
        _know(db_session, user, lemma)
    return units


# ---------------------------------------------------------------------------
# 1. The coverage model
# ---------------------------------------------------------------------------


def test_v1_splits_each_level_into_halves_by_teaching_order(db_session, isolated_catalog):
    a = [isolated_catalog("A1", order) for order in (3, 1, 2, 4, 5)]
    b = isolated_catalog("A2", 1)
    by_order = sorted(a, key=lambda c: c.difficulty_order)
    assert level_coverage.band_unit_ids(db_session, "A1.1") == [c.id for c in by_order[:3]]
    assert level_coverage.band_unit_ids(db_session, "A1.2") == [c.id for c in by_order[3:]]
    assert level_coverage.band_unit_ids(db_session, "A2.1") == [b.id]
    assert level_coverage.band_unit_ids(db_session, "A2.2") == []


def test_v2_uses_each_units_sub_band_tag(db_session, isolated_catalog, monkeypatch):
    monkeypatch.setattr(
        "app.services.grammar_catalog.active_catalog_version", lambda: FRENCH_CORE_CATALOG_V2_VERSION
    )
    first = isolated_catalog("A1", 1, sub_band="A1.2")
    second = isolated_catalog("A1", 2, sub_band="A1.1")
    assert level_coverage.band_unit_ids(db_session, "A1.1") == [second.id]
    assert level_coverage.band_unit_ids(db_session, "A1.2") == [first.id]


def test_band_words_are_the_sub_bands_lemmas_without_closed_class_words():
    words = level_coverage.band_words("A1.1")
    assert "bonjour" in words
    assert "le" not in words and "je" not in words and "dans" not in words
    assert 250 < len(words) < 384  # the lexicon's A1.1 minus its closed-class words
    assert level_coverage.band_words("B2.1") == frozenset()  # the lexicon stops at B1


def test_held_is_wp_l4_tenue_whatever_the_stability(db_session, isolated_catalog):
    user = _user(db_session)
    held, strong_not_held = (isolated_catalog("A1", n) for n in (1, 2))
    _hold(db_session, user, held, stability=3)
    _hold(db_session, user, strong_not_held, stability=60, held=False)
    assert level_coverage.held_unit_ids(db_session, user) == {held.id}


def test_a_word_is_known_at_retrievability_085_on_a_settled_card(db_session):
    user = _user(db_session)
    fresh = UserVocabularyProgress(stability=10.0, reps=3, state="reviewing", last_review_date=NOW - timedelta(days=2))
    faded = UserVocabularyProgress(stability=2.0, reps=3, state="reviewing", last_review_date=NOW - timedelta(days=30))
    once = UserVocabularyProgress(stability=10.0, reps=1, state="reviewing", last_review_date=NOW)
    relearning = UserVocabularyProgress(stability=10.0, reps=4, state="relearning", last_review_date=NOW)
    legacy = UserVocabularyProgress(stability=0.0, reps=0, state="mastered", mastered_date=NOW, last_review_date=None)
    assert level_coverage.is_word_known(fresh, now=NOW)
    assert not level_coverage.is_word_known(faded, now=NOW)
    assert not level_coverage.is_word_known(once, now=NOW)
    assert not level_coverage.is_word_known(relearning, now=NOW)
    assert level_coverage.is_word_known(legacy, now=NOW)
    _know(db_session, user, "le chien")
    assert {"chien"} <= level_coverage.known_lemmas(db_session, user)


def test_the_percent_beside_the_band_reads_90_at_coverage_and_100_after_the_epreuve():
    empty = level_coverage.BandCoverage("A1.1", units_held=0, units_total=18, words_known=0, words_total=316)
    half = level_coverage.BandCoverage("A1.1", units_held=8, units_total=18, words_known=126, words_total=316)
    full = level_coverage.BandCoverage("A1.1", units_held=16, units_total=18, words_known=253, words_total=316)
    passed = level_coverage.BandCoverage(
        "A1.1", units_held=16, units_total=18, words_known=253, words_total=316, checkpoint_passed=True
    )
    assert empty.percent == 0
    assert 40 <= half.percent <= 50
    assert full.coverage_met and full.percent == 90
    assert passed.percent == 100
    assert full.as_dict()["label"] == "A1.1 · 90 %"
    # A band without units (no catalogue) is never covered.
    assert not level_coverage.BandCoverage("A1.1", 0, 0, 5, 5).coverage_met


# ---------------------------------------------------------------------------
# 2–3. Promotion and the checkpoint
# ---------------------------------------------------------------------------


def test_coverage_makes_the_epreuve_ready_but_only_a_pass_raises_the_level(
    db_session, isolated_catalog, small_band
):
    user = _user(db_session)
    _cover_a11(db_session, user, isolated_catalog)

    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate"] == "A1.1"
    assert payload["coverage"]["coverage_met"] is True
    assert payload["level_label"] == "A1.1 · 90 %"
    assert payload["checkpoint"]["state"] == "ready"
    assert payload["checkpoint"]["checkpoint_ready"] is True
    assert payload["checkpoint"]["can_dos"], "the épreuve knows the band's can-dos"
    row = db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id, band="A1.1").one()
    assert row.status == "ready" and row.ready_at is not None

    checkpoints.record_checkpoint_result(db_session, user, band="A1.1", passed=True, now=NOW)
    db_session.commit()
    after = CEFRProgressService(db_session).recompute(user, source="test")
    assert after["estimate"] == "A1.2"
    assert after["estimate_source"] == "measured"
    assert after["coverage"]["band"] == "A1.2"
    assert after["checkpoint"]["state"] == "locked"


def test_an_uncovered_band_cannot_take_its_epreuve(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    isolated_catalog("A1", 1)
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["checkpoint"]["state"] == "locked"
    assert payload["checkpoint"]["checkpoint_ready"] is False
    with pytest.raises(checkpoints.CheckpointError) as refused:
        checkpoints.record_checkpoint_result(db_session, user, band="A1.1", passed=True, now=NOW)
    assert refused.value.code == "not_ready"


def test_a_failed_epreuve_returns_after_a_week_of_consolidation(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    _cover_a11(db_session, user, isolated_catalog)
    CEFRProgressService(db_session).recompute(user, source="test")

    row = checkpoints.record_checkpoint_result(db_session, user, band="A1.1", passed=False, now=NOW)
    db_session.commit()
    assert row.status == "failed"
    assert checkpoints._aware(row.retry_after) == NOW + timedelta(days=7)
    assert checkpoints.state_of(row, coverage_met=True, now=NOW + timedelta(days=3)) == "failed"
    with pytest.raises(checkpoints.CheckpointError) as early:
        checkpoints.record_checkpoint_result(db_session, user, band="A1.1", passed=True, now=NOW + timedelta(days=3))
    assert early.value.code == "retry_later"

    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["checkpoint"]["state"] == "failed"
    assert payload["checkpoint"]["retry_after"]
    assert payload["estimate"] == "A1.1"
    # The forecast is bounded below by the week of consolidation.
    assert payload["forecast"]["range_days"][1] >= 7

    later = NOW + timedelta(days=7, minutes=1)
    assert checkpoints.state_of(row, coverage_met=True, now=later) == "ready"
    checkpoints.record_checkpoint_result(db_session, user, band="A1.1", passed=True, now=later)
    db_session.commit()
    assert row.status == "passed" and row.attempts == 2
    with pytest.raises(checkpoints.CheckpointError) as closed:
        checkpoints.record_checkpoint_result(db_session, user, band="A1.1", passed=True, now=later)
    assert closed.value.code == "already_closed"


def test_demotion_is_invisible_fragile_items_simply_come_back(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    units = _cover_a11(db_session, user, isolated_catalog)
    CEFRProgressService(db_session).recompute(user, source="test")
    checkpoints.record_checkpoint_result(db_session, user, band="A1.1", passed=True, now=NOW)
    db_session.commit()
    assert CEFRProgressService(db_session).recompute(user, source="test")["estimate"] == "A1.2"

    # Everything lapses: the unit's memory collapses and every word fades.
    progress = db_session.query(UserGrammarProgress).filter_by(user_id=user.id, concept_id=units[0].id).one()
    progress.stability, progress.next_review = 2.0, progress.last_review + timedelta(days=1)
    db_session.query(UserVocabularyProgress).filter_by(user_id=user.id).update({"state": "relearning"})
    db_session.commit()
    for _ in range(4):
        payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate"] == "A1.2"


def test_a_unit_once_held_stays_counted_in_its_bands_coverage(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    units = [isolated_catalog("A1", 1), isolated_catalog("A1", 2)]
    _hold(db_session, user, units[0])
    first = CEFRProgressService(db_session).recompute(user, source="test")
    assert first["coverage"]["units"]["held"] == 1
    progress = db_session.query(UserGrammarProgress).filter_by(user_id=user.id, concept_id=units[0].id).one()
    progress.stability, progress.next_review = 1.0, progress.last_review + timedelta(days=1)  # a lapse
    db_session.commit()
    again = CEFRProgressService(db_session).recompute(user, source="test")
    assert again["coverage"]["units"]["held"] == 1


# ---------------------------------------------------------------------------
# 4. Release day
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", CEFR_LEVELS)
def test_no_measured_level_drops_on_release_day(db_session, level):
    legacy = {"version": "cefr-progress-v1", "estimate": level, "estimate_source": "measured"}
    user = _user(db_session, estimate=level, declared="A1", payload=legacy)

    # The Dossier's read path (no write) and the first persisted recompute agree.
    read_only = CEFRProgressService(db_session).recompute(user, source="test", persist=False)
    assert read_only["estimate"] == level
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate"] == level
    assert payload["release_floor"] == (level if level != "A1.1" else None)
    # …and on every recompute after it, now that the payload is v2.
    for _ in range(4):
        payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate"] == level
    if level != "A1.1":
        below = CEFR_LEVELS[CEFR_LEVELS.index(level) - 1]
        row = db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id, band=below).one()
        assert (row.status, row.source) == ("credited", "release_grandfather")


def test_a_level_above_the_declaration_without_a_payload_holds(db_session):
    user = _user(db_session, estimate="A2.2", declared="A1")
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate"] == "A2.2"
    assert payload["estimate_source"] == "measured"


def test_a_declared_level_keeps_its_own_rule_on_release_day(db_session):
    legacy = {"version": "cefr-progress-v1", "estimate": "B1.1", "estimate_source": "declared"}
    user = _user(db_session, estimate="B1.1", declared="B1", payload=legacy)
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate"] == "B1.1"
    assert payload["estimate_source"] == "declared"
    assert payload["release_floor"] is None
    assert db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id).count() == 0


def test_the_daily_journey_finish_credits_the_release_floor_before_anything_else(db_session):
    """The journey finish (`_measure_up`, no commit of its own) may be the first
    recompute a learner sees after release: it writes the credit row, so the
    floor survives whichever recompute comes next."""

    from app.services.achievement_recap import _measure_up

    legacy = {"version": "cefr-progress-v1", "estimate": "A2.1", "estimate_source": "measured"}
    user = _user(db_session, estimate="A2.1", payload=legacy)
    _measure_up(db_session, user)
    db_session.commit()
    row = db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id, band="A1.2").one()
    assert (row.status, row.source) == ("credited", "release_grandfather")
    user.cefr_estimate_payload = {"version": "cefr-progress-v2", "release_floor": None}
    db_session.commit()
    assert CEFRProgressService(db_session).recompute(user, source="test")["estimate"] == "A2.1"

    # Once on v2, the journey finish refreshes the payload (coverage, épreuve, forecast).
    _measure_up(db_session, user)
    db_session.commit()
    assert user.cefr_estimate_payload["version"] == "cefr-progress-v2"
    assert user.cefr_estimate_payload["coverage"]["band"] == "A2.1"


# ---------------------------------------------------------------------------
# 5. The prior
# ---------------------------------------------------------------------------


def _attempts(db_session, user, *, score: float, count: int = DECLARED_LEVEL_EVIDENCE_ATTEMPTS + 2) -> None:
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="completed")
    db_session.add(session)
    db_session.flush()
    for index in range(count):
        db_session.add(
            AtelierAttempt(
                atelier_session_id=session.id,
                user_id=user.id,
                concept_id=None,
                round="recognize",
                mode="fill",
                exercise_id=f"wpl7-{index}",
                verdict="correct" if score >= 3 else "incorrect",
                score_0_4=score,
                created_at=NOW - timedelta(days=1),
            )
        )
    db_session.commit()


def test_a_prior_the_evidence_confirms_stands_and_is_credited(db_session):
    user = _user(db_session, declared="B1")
    assert CEFRProgressService(db_session).recompute(user, source="test")["estimate_source"] == "declared"
    _attempts(db_session, user, score=3.6)
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate"] == "B1.1"
    assert payload["estimate_source"] == "measured"
    row = db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id, band="A2.2").one()
    assert (row.status, row.source) == ("credited", "prior_confirmed")


def test_a_prior_the_evidence_contradicts_falls_as_before(db_session):
    user = _user(db_session, declared="B1")
    _attempts(db_session, user, score=1.0)
    payload = CEFRProgressService(db_session).recompute(user, source="test")
    assert payload["estimate"] == "A1.1"
    assert payload["estimate_source"] == "measured"


# ---------------------------------------------------------------------------
# 6. The API
# ---------------------------------------------------------------------------


def _login(client) -> tuple[dict[str, str], str]:
    email = f"wpl7-api-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "target_language": "fr",
            "native_language": "en",
            "proficiency_level": "A1",
        },
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}, email


def test_the_engine_reads_readiness_and_reports_the_epreuve(client, db_session, isolated_catalog, small_band):
    headers, email = _login(client)
    user = db_session.query(User).filter(User.email == email).one()
    _cover_a11(db_session, user, isolated_catalog)

    view = client.get("/api/v1/progress/cefr/checkpoint", headers=headers).json()
    assert view["band"] == "A1.1"
    assert view["checkpoint_ready"] is True
    assert view["level_label"] == "A1.1 · 90 %"

    wrong = client.post("/api/v1/progress/cefr/checkpoint", headers=headers, json={"band": "A2.1", "passed": True})
    assert wrong.status_code == 409

    failed = client.post(
        "/api/v1/progress/cefr/checkpoint",
        headers=headers,
        json={"band": "A1.1", "passed": False, "episode_id": "ep-1", "evidence": {"can_dos_met": 3}},
    )
    assert failed.status_code == 200
    assert failed.json()["checkpoint"]["state"] == "failed"
    retry = client.post("/api/v1/progress/cefr/checkpoint", headers=headers, json={"band": "A1.1", "passed": True})
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "retry_later"

    cefr = client.get("/api/v1/progress/cefr", headers=headers).json()
    assert cefr["level_label"].startswith("A1.1 · ")
    assert cefr["coverage"]["units"]["required"] == 1
    assert set(cefr["rhythm_priors"]) == {"leger", "regulier", "soutenu", "intensif"}
