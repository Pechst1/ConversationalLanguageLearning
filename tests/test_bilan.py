"""«Le bilan» — the learner's week (``app/services/bilan.py``, ``/bilan``).

* The routes are a 404 while ``BILAN_ENABLED`` is off (before auth), 401 without a
  session and 200 with one.
* An empty week, a one-day week and a week whose lines were never checked: the page is
  honest — no line that has no settled, checked correction (#949, #971).
* Owner scoping: another learner's days, verdicts, words and rules never show.
* The week is Monday–Sunday in the learner's zone, DST included.
* The Monday push: once, under the cap, never against the opt-out, never while off.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.push_subscription import PushSubscription
from app.db.models.user import User
from app.db.models.verdict_record import VerdictRecord
from app.db.models.vocabulary import VocabularyWord
from app.main import create_app
from app.services import bilan
from app.tasks import notifications as tasks

# Wednesday 18 Nov 2026, 12:00 in Paris (CET, UTC+1).
NOW = datetime(2026, 11, 18, 11, 0, tzinfo=UTC)
MONDAY = date(2026, 11, 16)


def _learner(
    db: Session, *, tz: str = "Europe/Paris", native: str = "en", band: str = "A2"
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"bilan-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        timezone=tz,
        cefr_estimate=band,
        proficiency_level=band,
        is_active=True,
        notifications_enabled=True,
        practice_reminders=True,
    )
    db.add(user)
    db.commit()
    return user


def _day(
    db: Session,
    user: User,
    day: date,
    *,
    turns: list[dict] | None = None,
    status: str = "completed",
) -> DailyJourney:
    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=day,
        timezone=user.timezone,
        status=status,
        budget_seconds=300,
        scenario_snapshot={},
        created_at=datetime.now(UTC),
    )
    db.add(journey)
    db.flush()
    db.add(
        DailyJourneyStep(
            id=uuid.uuid4(),
            journey_id=journey.id,
            ordinal=1,
            kind="respond",
            status="completed",
            public_prompt={},
            private_task={"turns": turns or []},
        )
    )
    db.commit()
    return journey


def _turn(learner: str, *, span: str | None = None, fixed: str | None = None, **extra) -> dict:
    correction = (
        {"span_fr": span, "corrected_fr": fixed, "note_native": "", "kind": "edit"}
        if span and fixed
        else None
    )
    return {
        "learner": learner,
        "character": "D'accord.",
        "correction": correction,
        "free": False,
        **extra,
    }


def _verdict(
    db: Session,
    user: User,
    answer: str,
    *,
    corrected: str | None,
    outcome: str = "partly",
    counts: bool = True,
    at: datetime = NOW,
    superseded: bool = False,
    replacement: str | None = None,
    subject_type: str = "journal_entry",
    subject_id: str | None = None,
) -> None:
    edits = (
        [
            {
                "span": "x",
                "start": 0,
                "end": 1,
                "replacement": replacement,
                "note": "",
                "by": "model",
                "rule_id": None,
            }
        ]
        if replacement
        else []
    )
    db.add(
        VerdictRecord(
            id=uuid.uuid4(),
            user_id=user.id,
            surface="forge" if subject_type == "forge_attempt" else "journal",
            subject_type=subject_type,
            subject_id=subject_id or uuid.uuid4().hex,
            answer_text=answer,
            verdict={
                "shown": {
                    "outcome": outcome,
                    "checked_by": "model",
                    "call": "ok",
                    "edits": edits,
                    "corrected": corrected,
                    "counts": counts,
                }
            },
            counts=counts,
            judge_version="test",
            superseded_by_id=uuid.uuid4() if superseded else None,
            settled_at=at if counts else None,
            created_at=at,
        )
    )
    db.commit()


def _payload(db: Session, user: User, **kwargs) -> dict:
    return bilan.build_bilan(db, user, now=NOW, **kwargs)


# ---------------------------------------------------------------------------
# The week
# ---------------------------------------------------------------------------


def test_the_week_is_monday_to_sunday_in_the_learner_s_zone(db_session: Session) -> None:
    user = _learner(db_session, tz="Pacific/Auckland")
    # 23:30 UTC on Sunday 22 Nov is already Monday 23 Nov in Auckland.
    week = bilan.current_week(user, datetime(2026, 11, 22, 23, 30, tzinfo=UTC))
    assert week.start == date(2026, 11, 23)


def test_a_week_across_the_dst_change_is_seven_local_days() -> None:
    # Paris leaves summer time on Sunday 25 Oct 2026: that week lasts 169 hours.
    start, end = bilan.Week(start=date(2026, 10, 19), zone="Europe/Paris").utc_bounds()
    assert end - start == timedelta(hours=169)
    assert start == datetime(2026, 10, 18, 22, 0, tzinfo=UTC)
    assert end == datetime(2026, 10, 25, 23, 0, tzinfo=UTC)


def test_a_week_after_today_is_never_read(db_session: Session) -> None:
    user = _learner(db_session)
    assert bilan.week_for(user, date(2027, 1, 4), NOW).start == MONDAY


# ---------------------------------------------------------------------------
# The page model
# ---------------------------------------------------------------------------


def test_an_empty_week_is_empty_and_honest(db_session: Session) -> None:
    user = _learner(db_session)
    page = _payload(db_session, user)
    assert page["week_start"] == "2026-11-16" and page["week_end"] == "2026-11-22"
    assert page["days_played"] == 0 and not any(day["played"] for day in page["days"])
    assert [day["future"] for day in page["days"]] == [False, False, False, True, True, True, True]
    assert page["lines"] == [] and page["rules"] == []
    assert page["words"] == {"new_count": 0, "reviewed_count": 0, "held_count": 0, "shown": []}
    assert page["story"] == {"episodes": [], "decisions": [], "next_fr": None}
    assert page["is_current"] is True and page["closed"] is False


def test_a_one_day_week_shows_the_corrected_line_never_the_raw_one(db_session: Session) -> None:
    user = _learner(db_session)
    _day(
        db_session,
        user,
        MONDAY + timedelta(days=1),
        turns=[
            _turn("Je veux aller au marché avec toi demain.", span="Je veux", fixed="Je voudrais"),
        ],
    )
    page = _payload(db_session, user)
    assert page["days_played"] == 1
    assert [day["played"] for day in page["days"]][:3] == [False, True, False]
    assert [line["text_fr"] for line in page["lines"]] == [
        "Je voudrais aller au marché avec toi demain."
    ]
    assert "Je veux aller" not in str(page)


def test_a_week_of_unchecked_lines_shows_no_line(db_session: Session) -> None:
    user = _learner(db_session)
    _day(
        db_session,
        user,
        MONDAY,
        turns=[
            # nobody read it (#333)
            _turn(
                "Je prends le bus pour aller au travail.",
                span="prends",
                fixed="prenais",
                check_failure="timeout",
            ),
            # no correction: «nothing flagged» is not a check of the sentence
            _turn("Il ne veut plus boire son café le matin."),
            # a free retry, and a stock exit
            _turn(
                "Elle a chaude dans la cuisine ce soir.", span="chaude", fixed="chaud", free=True
            ),
            _turn(
                "Nous allons au cinéma ce soir ensemble.",
                span="allons",
                fixed="irons",
                stock_exit=True,
            ),
        ],
    )
    # ledger rows that do not count, or no longer stand
    _verdict(
        db_session,
        user,
        "Je mange une pomme rouge chaque matin.",
        corrected=None,
        outcome="right",
        counts=False,
    )
    _verdict(
        db_session,
        user,
        "Tu habites dans une grande maison.",
        corrected=None,
        outcome="right",
        superseded=True,
    )
    _verdict(
        db_session, user, "Il fait beau aujourd'hui à Paris.", corrected=None, outcome="not_yet"
    )
    page = _payload(db_session, user)
    assert page["days_played"] == 1
    assert page["lines"] == []


def test_settled_ledger_lines_count_corrected_or_right(db_session: Session) -> None:
    user = _learner(db_session)
    _verdict(
        db_session,
        user,
        "Hier je suis allé à la boulangerie du coin.",
        corrected=None,
        outcome="right",
    )
    _verdict(
        db_session,
        user,
        "Elle a chaude dans la cuisine.",
        corrected="Elle a chaud dans la cuisine.",
        replacement="chaud",
    )
    texts = [line["text_fr"] for line in _payload(db_session, user)["lines"]]
    assert "Elle a chaud dans la cuisine." in texts
    assert "Hier je suis allé à la boulangerie du coin." in texts
    assert "Elle a chaude dans la cuisine." not in texts


def test_only_free_forge_production_is_a_line(db_session: Session) -> None:
    from app.db.models.atelier import AtelierAttempt, AtelierSession

    user = _learner(db_session)
    session = AtelierSession(
        id=uuid.uuid4(),
        user_id=user.id,
        selected_concept_ids=[],
        quote_payload={},
        recap_payload={},
    )
    db_session.add(session)
    db_session.flush()
    for round_, answer in (
        ("sentence", "Je prends le métro tous les matins."),
        ("transform", "Tu es à l'hôtel ce soir."),
    ):
        attempt = AtelierAttempt(
            id=uuid.uuid4(),
            atelier_session_id=session.id,
            user_id=user.id,
            round=round_,
            mode="x",
            exercise_id="x",
            prompt_payload={},
            answer_payload={},
            correction_payload={},
        )
        db_session.add(attempt)
        db_session.flush()
        _verdict(
            db_session,
            user,
            answer,
            corrected=None,
            outcome="right",
            subject_type="forge_attempt",
            subject_id=str(attempt.id),
        )
    texts = [line["text_fr"] for line in _payload(db_session, user)["lines"]]
    assert texts == ["Je prends le métro tous les matins."]


def test_lines_are_short_whole_sentences_said_to_nobody(db_session: Session) -> None:
    assert bilan._one_sentence("Maintenant, Lila, je pense que je garde la carte.") is None
    assert bilan._one_sentence("Je garde la carte, Lila.") is None
    long = "Oui il ne veut plus boire et il prend son bain avec moi tous les soirs de la semaine."
    assert bilan._one_sentence(long) is None
    assert bilan._one_sentence("je garde la carte") == "Je garde la carte."
    assert bilan._one_sentence("Bonjour. Je garde la carte de ma grand-mère.", "carte") == (
        "Je garde la carte de ma grand-mère."
    )


def test_a_scene_line_keeps_only_french_around_the_fix(db_session: Session) -> None:
    # Real walk of 21–27 Nov: one correction per reply, the rest of the sentence unread.
    user = _learner(db_session)
    _day(
        db_session,
        user,
        MONDAY,
        turns=[
            _turn("J ai froid. Je suis müde ce soir.", span="müde", fixed="fatigué"),
            _turn(
                "Parce que j ai peur. Je suis vingt ans.",
                span="Je suis vingt ans",
                fixed="J'ai vingt ans",
            ),
            _turn(
                "Il y a une clé et un lettre secret.",
                span="un lettre secret",
                fixed="une lettre secrète",
            ),
            _turn(
                "Ich weiß nicht. Je pas vendre maintenant.",
                span="Je pas vendre",
                fixed="Je ne vends pas",
            ),
            _turn("Pourquoi non ? Oui, je monter avec toi.", span="je monter", fixed="Je monte"),
        ],
    )
    texts = [line["text_fr"] for line in _payload(db_session, user)["lines"]]
    assert "Je suis fatigué ce soir." in texts
    assert "J'ai vingt ans." in texts
    assert "Il y a une clé et une lettre secrète." in texts
    assert "Je ne vends pas maintenant." in texts
    assert "Oui, je monte avec toi." in texts
    assert bilan._reads_french("Je suis müde und fatigué.") is False
    assert bilan._reads_french("J ai vingt ans.") is False
    assert bilan._reads_french("Odile est ma grand-mère.") is True


def test_at_most_five_lines_spread_over_the_days(db_session: Session) -> None:
    user = _learner(db_session)
    for offset in range(3):
        _day(
            db_session,
            user,
            MONDAY + timedelta(days=offset),
            turns=[
                _turn(
                    f"Je veux voir le film numéro {n} avec toi.",
                    span="Je veux",
                    fixed="Je voudrais",
                )
                for n in range(offset * 3, offset * 3 + 3)
            ],
        )
    lines = _payload(db_session, user)["lines"]
    assert len(lines) == bilan.MAX_LINES
    assert {line["date"] for line in lines} == {"2026-11-16", "2026-11-17", "2026-11-18"}
    assert [line["date"] for line in lines] == sorted(line["date"] for line in lines)


def test_words_and_rules_of_the_week(db_session: Session) -> None:
    user = _learner(db_session, native="de")
    met = VocabularyWord(
        language="fr", word="la clé", normalized_word="la cle", german_translation="der Schlüssel"
    )
    old = VocabularyWord(
        language="fr", word="le pain", normalized_word="le pain", german_translation="das Brot"
    )
    anki = VocabularyWord(
        language="fr", word="la voile", normalized_word="la voile", is_anki_card=True
    )
    db_session.add_all([met, old, anki])
    db_session.flush()
    in_week = NOW - timedelta(days=1)
    new_row = UserVocabularyProgress(user_id=user.id, word_id=met.id, created_at=in_week)
    old_row = UserVocabularyProgress(
        user_id=user.id, word_id=old.id, created_at=NOW - timedelta(days=30)
    )
    db_session.add_all(
        [
            new_row,
            old_row,
            UserVocabularyProgress(user_id=user.id, word_id=anki.id, created_at=in_week),
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            ReviewLog(progress_id=old_row.id, review_date=in_week - timedelta(hours=2), rating=0),
            ReviewLog(progress_id=old_row.id, review_date=in_week, rating=2),
            ReviewLog(progress_id=new_row.id, review_date=in_week, rating=0),
            # retried right the same minute it was met: not held (a lesson's retry)
            ReviewLog(progress_id=new_row.id, review_date=in_week + timedelta(minutes=1), rating=2),
        ]
    )
    rule = GrammarConcept(name="passe_compose", level="A2", language="fr")
    held = GrammarConcept(name="articles", level="A1", language="fr")
    db_session.add_all([rule, held])
    db_session.flush()
    db_session.add_all(
        [
            UserGrammarProgress(user_id=user.id, concept_id=rule.id, introduced_at=in_week, reps=2),
            UserGrammarProgress(
                user_id=user.id,
                concept_id=held.id,
                introduced_at=NOW - timedelta(days=30),
                held_at=in_week,
                reps=6,
            ),
        ]
    )
    db_session.commit()

    page = _payload(db_session, user)
    words = page["words"]
    assert words["new_count"] == 1 and words["shown"] == [
        {"word": "la clé", "gloss": "der Schlüssel"}
    ]
    assert words["reviewed_count"] == 2 and words["held_count"] == 1
    moves = {row["concept_id"]: (row["from_stage"], row["stage"]) for row in page["rules"]}
    assert moves == {rule.id: ("new", "practising"), held.id: ("practising", "held")}
    # The Cahier's own words (WP-130), in the learner's interface language (A2 + de).
    assert {row["stage_label"] for row in page["rules"]} == {"in Übung", "gefestigt"}
    assert {row["title_fr"] for row in page["rules"]} == {"passe_compose", "articles"}


def test_the_story_describes_decisions_and_never_quotes_the_learner(db_session: Session) -> None:
    from app.db.models.serial import SerialThread
    from app.services.living_story import STATE_KEY

    user = _learner(db_session)
    _day(db_session, user, MONDAY + timedelta(days=1))
    live = {
        "events": [
            {
                "id": "e1",
                "date": "2026-11-17",
                "scene_id": "s",
                "summary_fr": "x",
                "did_fr": "Tu vas aider Margaux.",
            },
            {
                "id": "e0",
                "date": "2026-11-09",
                "scene_id": "s",
                "summary_fr": "x",
                "did_fr": "Tu pars lundi.",
            },
        ],
        "chronicle": [
            {
                "date": "2026-11-17",
                "quote": "Je pas sais.",
                "question": "Vas-tu rester ?",
                "resolved_fr": "Tu ne sais pas encore quelle porte la clé ouvre.",
            },
        ],
        "next_teaser": {"text_fr": "Qui a laissé la lettre sous la porte de Lila ?"},
    }
    db_session.add(
        SerialThread(
            id=uuid.uuid4(),
            user_id=user.id,
            status="active",
            world_bible={},
            state={STATE_KEY: live},
            news_seed={},
            current_episode_index=0,
        )
    )
    db_session.commit()
    story = _payload(db_session, user)["story"]
    assert [(row["kind"], row["label_fr"]) for row in story["decisions"]] == [
        ("promise", "Tu vas aider Margaux."),
        ("resolved", "Tu ne sais pas encore quelle porte la clé ouvre."),
    ]
    assert story["next_fr"] == "Qui a laissé la lettre sous la porte de Lila ?"
    assert "Je pas sais" not in str(story) and "Vas-tu rester" not in str(story)
    # An older week's hook was answered by the days after it.
    assert _payload(db_session, user, week_start=date(2026, 11, 9))["story"]["next_fr"] is None


def test_another_learner_s_week_never_shows(db_session: Session) -> None:
    me = _learner(db_session)
    other = _learner(db_session)
    _day(
        db_session,
        other,
        MONDAY,
        turns=[_turn("Je veux partir avec elle demain.", span="Je veux", fixed="Je voudrais")],
    )
    _verdict(db_session, other, "Il a chaud dans la cuisine.", corrected=None, outcome="right")
    word = VocabularyWord(
        language="fr", word="la porte", normalized_word="la porte", english_translation="door"
    )
    concept = GrammarConcept(name="futur", level="A2", language="fr")
    db_session.add_all([word, concept])
    db_session.flush()
    db_session.add_all(
        [
            UserVocabularyProgress(
                user_id=other.id, word_id=word.id, created_at=NOW - timedelta(hours=3)
            ),
            UserGrammarProgress(
                user_id=other.id, concept_id=concept.id, introduced_at=NOW - timedelta(hours=3)
            ),
        ]
    )
    db_session.commit()
    page = _payload(db_session, me)
    assert page["days_played"] == 0 and page["lines"] == [] and page["rules"] == []
    assert page["words"]["new_count"] == 0
    assert bilan.home_card(db_session, me, now=NOW + timedelta(days=7)) == {
        "week_start": None,
        "days_played": 0,
    }
    assert bilan.home_card(db_session, other, now=NOW + timedelta(days=7)) == {
        "week_start": "2026-11-16",
        "days_played": 1,
    }


def test_past_weeks_and_navigation(db_session: Session) -> None:
    user = _learner(db_session)
    _day(db_session, user, MONDAY - timedelta(days=12))
    _day(db_session, user, MONDAY + timedelta(days=1))
    page = _payload(db_session, user)
    assert page["previous_week_start"] == "2026-11-02" and page["next_week_start"] is None
    past = _payload(db_session, user, week_start=date(2026, 11, 4))
    assert (
        past["week_start"] == "2026-11-02"
        and past["closed"] is True
        and past["is_current"] is False
    )
    assert past["next_week_start"] == "2026-11-16" and past["days_played"] == 1


# ---------------------------------------------------------------------------
# The routes
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session) -> Iterator[tuple[TestClient, dict]]:
    app = create_app()
    who: dict = {}

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: who["user"]
    with TestClient(app) as client:
        yield client, who


def test_routes_are_404_while_the_flag_is_off(api, db_session: Session, monkeypatch) -> None:
    client, who = api
    monkeypatch.setattr(settings, "BILAN_ENABLED", False)
    who["user"] = _learner(db_session)
    assert client.get("/api/v1/bilan").status_code == 404
    assert client.get("/api/v1/bilan/card").status_code == 404


def test_routes_answer_when_on(api, db_session: Session, monkeypatch) -> None:
    client, who = api
    monkeypatch.setattr(settings, "BILAN_ENABLED", True)
    who["user"] = user = _learner(db_session)
    this_monday = bilan.current_week(user).start
    _day(
        db_session,
        user,
        this_monday,
        turns=[
            _turn("Je veux un café au lait s'il vous plaît.", span="Je veux", fixed="Je voudrais")
        ],
    )
    response = client.get("/api/v1/bilan")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["week_start"] == this_monday.isoformat() and body["days_played"] == 1
    assert body["lines"][0]["text_fr"] == "Je voudrais un café au lait s'il vous plaît."
    card = client.get("/api/v1/bilan/card")
    assert card.status_code == 200 and card.json() == {"week_start": None, "days_played": 0}
    assert client.get("/api/v1/bilan", params={"week": "not-a-date"}).status_code == 422


def test_routes_need_a_session(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "BILAN_ENABLED", True)
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        assert client.get("/api/v1/bilan").status_code == 401


# ---------------------------------------------------------------------------
# The Monday push
# ---------------------------------------------------------------------------


class _Fake:
    sent: list[dict] = []

    def __init__(self, db) -> None:
        self.db = db

    def send_notification(self, user_id, message, title="L’Atelier", *, data=None) -> int:
        _Fake.sent.append(
            {"user_id": user_id, "title": title, "message": message, "data": dict(data or {})}
        )
        return 1


@pytest.fixture()
def sent(db_session: Session, monkeypatch) -> list[dict]:
    import app.services.notification_service as notification_service

    _Fake.sent = []
    monkeypatch.setattr(notification_service, "NotificationService", _Fake)

    class _Session:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            return None

    monkeypatch.setattr(tasks, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(settings, "BILAN_ENABLED", True)
    return _Fake.sent


def _subscribed(db: Session, user: User) -> User:
    db.add(
        PushSubscription(
            id=uuid.uuid4(),
            user_id=user.id,
            endpoint=f"https://push.test/{uuid.uuid4().hex}",
            keys={"p256dh": "x", "auth": "y"},
        )
    )
    db.commit()
    return user


# Monday 23 Nov 2026, 11:00 in Paris = 10:00 UTC.
PARIS_MONDAY_1100 = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)


def _mine(sent: list[dict], user: User) -> list[dict]:
    return [row for row in sent if row["user_id"] == user.id]


def test_the_monday_push_goes_once_about_a_played_week(db_session: Session, sent) -> None:
    from app.celery_app import celery_app

    assert "app.tasks.notifications.send_bilan_pushes" in {
        entry["task"] for entry in celery_app.conf.beat_schedule.values()
    }
    player = _subscribed(db_session, _learner(db_session))
    idle = _subscribed(db_session, _learner(db_session))
    _day(db_session, player, MONDAY + timedelta(days=2))
    tasks.send_bilan_pushes(now=PARIS_MONDAY_1100.isoformat())
    tasks.send_bilan_pushes(now=(PARIS_MONDAY_1100 + timedelta(minutes=5)).isoformat())
    pushes = _mine(sent, player)
    assert len(pushes) == 1 and _mine(sent, idle) == []
    assert pushes[0]["message"] == "Un jour joué la semaine dernière. Ton bilan t’attend."
    assert pushes[0]["data"]["route"] == "/bilan?week=2026-11-16"
    # Not on a Tuesday, not at another hour.
    _Fake.sent.clear()
    tasks.send_bilan_pushes(now=(PARIS_MONDAY_1100 + timedelta(days=1)).isoformat())
    tasks.send_bilan_pushes(now=(PARIS_MONDAY_1100 + timedelta(hours=3)).isoformat())
    assert _Fake.sent == []


def test_the_monday_push_respects_opt_out_cap_and_flag(
    db_session: Session, sent, monkeypatch
) -> None:
    opted_out = _subscribed(db_session, _learner(db_session))
    opted_out.practice_reminders = False
    capped = _subscribed(db_session, _learner(db_session))
    for user in (opted_out, capped):
        _day(db_session, user, MONDAY)
        _day(db_session, user, MONDAY + timedelta(days=1))
    for event in (tasks.MORNING_EVENT, tasks.STREAK_REMINDER_EVENT, tasks.REVIEW_REMINDER_EVENT):
        db_session.add(
            PilotEvent(
                user_id=capped.id,
                event_type=event,
                entity_type="notification",
                entity_id="2026-11-23",
                payload={},
            )
        )
    db_session.commit()
    tasks.send_bilan_pushes(now=PARIS_MONDAY_1100.isoformat())
    assert sent == []

    monkeypatch.setattr(settings, "BILAN_ENABLED", False)
    fresh = _subscribed(db_session, _learner(db_session))
    _day(db_session, fresh, MONDAY)
    assert tasks.send_bilan_pushes(now=PARIS_MONDAY_1100.isoformat()) == {
        "eligible_users": 0,
        "notifications_sent": 0,
    }
    assert sent == []


def test_push_copy_is_french_and_true() -> None:
    assert tasks.bilan_push_copy(1)[1].startswith("Un jour joué")
    assert tasks.bilan_push_copy(4)[1] == "4 jours joués la semaine dernière. Ton bilan est prêt."
