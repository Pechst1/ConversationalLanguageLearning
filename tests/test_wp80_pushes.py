"""WP-80: a reason to come back tomorrow — the scheduled pushes.

Every push here goes through a patched sender: nothing leaves the building.

* the morning push fires at the learner's reminder time **in their zone**, is a
  character speaking (title = name, a line in their voice, their portrait) and
  deep-links into the scene; silent once today's scene is done;
* the story's own teaser wins over the authored line when the engine wrote one;
* the evening streak-at-risk push fires at local 19:00, only for a live streak
  of at least two days that today has not extended, once;
* the Lexique review reminder is scheduled, «vous», no emoji, and waits for
  the day's scene.
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.push_subscription import PushSubscription
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import serial_notifications as copy
from app.tasks import notifications as tasks


class _FakeNotifications:
    sent: list[dict] = []

    def __init__(self, db) -> None:
        self.db = db

    def send_notification(self, user_id, message, title="L’Atelier", *, data=None) -> int:
        _FakeNotifications.sent.append(
            {"user_id": user_id, "title": title, "message": message, "data": dict(data or {})}
        )
        return 1


@pytest.fixture()
def sent(db_session, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    import app.services.notification_service as notification_service

    _FakeNotifications.sent = []
    monkeypatch.setattr(notification_service, "NotificationService", _FakeNotifications)

    class _Session:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            return None

    monkeypatch.setattr(tasks, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")
    return _FakeNotifications.sent


def _learner(db_session, *, tz: str, reminder: str = "08:30", band: str = "A1") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp80-push-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        timezone=tz,
        reminder_time=reminder,
        cefr_estimate=band,
        is_active=True,
        notifications_enabled=True,
        practice_reminders=True,
        streak_notifications=True,
    )
    db_session.add(user)
    db_session.add(
        PushSubscription(
            id=uuid.uuid4(),
            user_id=user.id,
            endpoint=f"https://push.test/{uuid.uuid4().hex}",
            keys={"p256dh": "x", "auth": "y"},
        )
    )
    db_session.commit()
    return user


def _journey(db_session, user: User, day: date, *, status: str, character=("romy_tremblay", "Romy")) -> DailyJourney:
    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=day,
        timezone=user.timezone,
        status=status,
        budget_seconds=300,
        scenario_snapshot={"character_id": character[0], "character_name": character[1]},
        created_at=datetime.now(UTC),
    )
    db_session.add(journey)
    db_session.commit()
    return journey


def _mine(sent: list[dict], user: User) -> list[dict]:
    return [row for row in sent if row["user_id"] == user.id]


# ---------------------------------------------------------------------------
# Morning
# ---------------------------------------------------------------------------

# 20:30 UTC on 21 Sept is 08:30 NZST on 22 Sept and 13:30 PDT on 21 Sept.
AUCKLAND_0830 = datetime(2026, 9, 21, 20, 30, tzinfo=UTC)


def test_the_morning_push_fires_at_the_local_reminder_time(db_session, sent) -> None:
    auckland = _learner(db_session, tz="Pacific/Auckland")
    los_angeles = _learner(db_session, tz="America/Los_Angeles")
    paris = _learner(db_session, tz="Europe/Paris")

    tasks.send_morning_editions(now=AUCKLAND_0830.isoformat())

    assert len(_mine(sent, auckland)) == 1
    assert _mine(sent, los_angeles) == []
    assert _mine(sent, paris) == []

    push = _mine(sent, auckland)[0]
    # A character speaks: the default voice before any scene is Marin's.
    assert push["title"] == "Marin"
    assert push["message"] in {line["A"] for line in copy.MORNING_LINES.values()}
    assert push["data"]["route"] == "/atelier?start=today"
    assert push["data"]["image"] == "/assets/serial/characters/marin_leveque/portrait-neutral.webp"
    assert push["data"]["kind"] == "morning_teaser"
    assert push["data"]["notification_id"] == "2026-09-22"  # Auckland's day
    assert push["title"] != copy.DAILY_JOURNEY_MORNING_TITLE

    # Deduped per local day.
    tasks.send_morning_editions(now=(AUCKLAND_0830 + timedelta(minutes=5)).isoformat())
    assert len(_mine(sent, auckland)) == 1

    # Los Angeles gets theirs at their own 08:30 (15:30 UTC).
    tasks.send_morning_editions(now=datetime(2026, 9, 22, 15, 30, tzinfo=UTC).isoformat())
    assert len(_mine(sent, los_angeles)) == 1


def test_the_voice_is_the_latest_scene_s_character(db_session, sent) -> None:
    user = _learner(db_session, tz="Pacific/Auckland", band="B1")
    _journey(db_session, user, date(2026, 9, 21), status="completed")

    tasks.send_morning_editions(now=AUCKLAND_0830.isoformat())

    push = _mine(sent, user)[0]
    assert push["title"] == "Romy"
    assert push["message"] == copy.MORNING_LINES["romy_tremblay"]["B"]
    assert push["data"]["image"].endswith("/romy_tremblay/portrait-neutral.webp")
    assert push["data"]["teaser_source"] == "authored"


def test_silent_once_today_s_scene_is_done(db_session, sent) -> None:
    user = _learner(db_session, tz="Pacific/Auckland")
    _journey(db_session, user, date(2026, 9, 22), status="completed")

    tasks.send_morning_editions(now=AUCKLAND_0830.isoformat())

    assert _mine(sent, user) == []


def test_the_engine_s_teaser_wins_when_the_story_wrote_one(db_session, sent) -> None:
    user = _learner(db_session, tz="Pacific/Auckland")
    db_session.add(
        SerialThread(
            id=uuid.uuid4(),
            user_id=user.id,
            status="active",
            state={
                "living_story": {
                    "next_teaser": {
                        "text_fr": "Demain, je vous montre la lettre.",
                        "character_id": "lila_bonnet",
                    }
                }
            },
        )
    )
    db_session.commit()

    push = copy.daily_journey_morning_push(db_session, user, today=date(2026, 9, 22))

    assert push is not None
    assert (push.title, push.message, push.source) == ("Lila", "Demain, je vous montre la lettre.", "engine")
    assert push.image.endswith("/lila_bonnet/portrait-neutral.webp")


def test_a_resumable_scene_is_picked_up_where_it_stopped(db_session, sent) -> None:
    user = _learner(db_session, tz="Pacific/Auckland")
    _journey(db_session, user, date(2026, 9, 22), status="paused")

    push = copy.daily_journey_morning_push(db_session, user, today=date(2026, 9, 22))

    assert push.message == copy.RESUME_LINES["A"]
    assert push.title == "Romy"


# ---------------------------------------------------------------------------
# Evening: streak at risk
# ---------------------------------------------------------------------------

PARIS_1900 = datetime(2026, 9, 22, 17, 0, tzinfo=UTC)


def _with_streak(user: User, days: int, last: date) -> None:
    user.grammar_streak_days = days
    user.grammar_last_review_date = last
    user.current_streak = days


def test_streak_at_risk_fires_at_local_19h_for_a_live_streak_not_done_today(db_session, sent) -> None:
    at_risk = _learner(db_session, tz="Europe/Paris")
    _with_streak(at_risk, 3, date(2026, 9, 21))
    one_day = _learner(db_session, tz="Europe/Paris")
    _with_streak(one_day, 1, date(2026, 9, 21))
    done = _learner(db_session, tz="Europe/Paris")
    _with_streak(done, 5, date(2026, 9, 22))
    broken = _learner(db_session, tz="Europe/Paris")
    _with_streak(broken, 9, date(2026, 9, 19))
    db_session.commit()

    ours = (at_risk, one_day, done, broken)

    def mine() -> list[dict]:
        return [row for row in sent if row["user_id"] in {user.id for user in ours}]

    tasks.send_streak_reminders(now=(PARIS_1900 - timedelta(hours=1)).isoformat())
    assert mine() == [], "18:00 local is not the evening push"

    tasks.send_streak_reminders(now=PARIS_1900.isoformat())

    assert [row["user_id"] for row in mine()] == [at_risk.id]
    push = mine()[0]
    assert push["title"] == "Marin"
    assert "3 jours de suite" in push["message"]
    assert push["data"]["route"] == "/atelier?start=today"
    assert push["data"]["kind"] == "streak_reminder"

    # A broken chain was settled to zero on the way, never announced.
    db_session.refresh(broken)
    assert broken.current_streak == 0

    # Once per local day.
    tasks.send_streak_reminders(now=(PARIS_1900 + timedelta(minutes=10)).isoformat())
    assert len(mine()) == 1


def test_streak_at_risk_uses_the_learner_s_evening_not_the_server_s(db_session, sent) -> None:
    user = _learner(db_session, tz="America/Los_Angeles")
    _with_streak(user, 4, date(2026, 9, 21))
    db_session.commit()

    tasks.send_streak_reminders(now=PARIS_1900.isoformat())  # 10:00 in LA
    assert _mine(sent, user) == []
    tasks.send_streak_reminders(now=datetime(2026, 9, 23, 2, 0, tzinfo=UTC).isoformat())  # 19:00 PDT 22 Sept
    assert len(_mine(sent, user)) == 1


def test_streak_at_risk_respects_the_setting(db_session, sent) -> None:
    user = _learner(db_session, tz="Europe/Paris")
    _with_streak(user, 4, date(2026, 9, 21))
    user.streak_notifications = False
    db_session.commit()

    tasks.send_streak_reminders(now=PARIS_1900.isoformat())
    assert _mine(sent, user) == []


# ---------------------------------------------------------------------------
# Review reminder
# ---------------------------------------------------------------------------


def test_the_review_reminder_is_scheduled_and_waits_for_the_scene(db_session, sent, monkeypatch) -> None:
    from app.celery_app import celery_app
    from app.services.unified_srs import UnifiedSRSService

    assert any(
        entry["task"] == "app.tasks.notifications.send_daily_srs_reminders"
        for entry in celery_app.conf.beat_schedule.values()
    )
    monkeypatch.setattr(UnifiedSRSService, "get_due_summary", lambda self, user_id: SimpleNamespace(total_due=3))
    paris_1800 = PARIS_1900 - timedelta(hours=1)

    waiting = _learner(db_session, tz="Europe/Paris")
    finished = _learner(db_session, tz="Europe/Paris")
    _journey(db_session, finished, date(2026, 9, 22), status="completed")

    tasks.send_daily_srs_reminders(now=paris_1800.isoformat())

    assert len(_mine(sent, finished)) == 1
    push = _mine(sent, finished)[0]
    assert push["message"] == "3 mots vous attendent pour une révision rapide."
    assert push["data"]["route"] == "/vocabulary/review"
    assert _mine(sent, waiting) == []


# ---------------------------------------------------------------------------
# Copy rules
# ---------------------------------------------------------------------------

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
TU = re.compile(r"\b(tu|toi|ton|ta|tes|te)\b", re.IGNORECASE)


def _all_lines() -> list[str]:
    lines: list[str] = []
    for table in (copy.MORNING_LINES, copy.STREAK_LINES):
        for row in table.values():
            lines.extend(row.values())
    lines.extend(copy.DEFAULT_MORNING_LINE.values())
    lines.extend(copy.DEFAULT_STREAK_LINE.values())
    lines.extend(copy.RESUME_LINES.values())
    lines.extend(tasks.review_reminder_copy(n)[1] for n in (1, 4))
    return lines


def test_every_line_says_vous_and_carries_no_emoji() -> None:
    for line in _all_lines():
        assert not EMOJI.search(line), line
        assert not TU.search(line), line


def test_every_portrait_character_has_its_own_lines() -> None:
    for character_id in copy.CHARACTER_NAMES:
        assert set(copy.MORNING_LINES[character_id]) == {"A", "B"}
        assert set(copy.STREAK_LINES[character_id]) == {"A", "B"}
        assert copy.portrait_path(character_id).endswith(f"/{character_id}/portrait-neutral.webp")
    assert copy.portrait_path("marin") == copy.portrait_path("marin_leveque")
    assert copy.portrait_path("nobody") is None
