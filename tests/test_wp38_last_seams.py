"""WP-38 — the last seams the 2026-09-10 cohort and WP-36/37 left open.

WP-37 applied the hooks eight packages owed each other and wrote down, honestly,
the four it could not apply from inside its own lease. This file pins those, and
WP-36's three:

1. **WP-34 has a surface.** ``CrIntakeEntry`` / ``CrArtefactCard`` /
   ``CrArtefactTaskCard`` were built, exported, covered by 17 frontend
   assertions — and imported by no page. A backend with 82 passing tests and no
   way in is a backend nobody uses.
2. **The radio transport goes through the journey facade** (WP-32 §9.1, WP-37
   §4), not through ``apiService``.
3. **The day-before rehearsal push is sent** (WP-31 §7.2, WP-37 §6), once, on
   its own key, and independently of the morning edition.
4. **``scenario_key`` is the authored-scenario catalogue**, not every member of
   ``CapabilityKey`` — the "still lax, deliberately not fixed here" line at the
   end of WP-37 §1.
5. **WP-36's hooks**: the node suite is in ``package.json`` and in CI; a
   rehearsal stores the character's reply so a prompted repair can be
   recognised; and the policy's decision is recorded so uptake is countable.

No model call is made anywhere in this file.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.pilot_event import PilotEvent
from app.db.models.push_subscription import PushSubscription
from app.db.models.rehearsal import Rehearsal
from app.db.models.user import User
from app.services import journey_content as jc_content
from app.services import journey_conversation as jc
from app.services import journey_events
from app.services.daily_journey import SELF_REPAIR_EVENT_TYPE, DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from app.services.error_memory import ERROR_STATE_OPEN, ErrorMemoryService
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    InputMode,
    TaskOutcome,
)
from app.services.rehearsal import RehearsalService

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"
sys.path.insert(0, str(ROOT / "scripts"))

DAY = date(2026, 9, 11)
NOW = datetime(2026, 9, 11, 9, 0, tzinfo=UTC)


def _read(path: Path) -> str:
    assert path.exists(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def _user(db_session: Session, *, native: str = "en") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp38-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ==========================================================================
# 1. WP-34 has a surface (WP-37 §2.1)
# ==========================================================================

MISSIONS_PAGE = WEB / "pages" / "missions.tsx"
COURRIER = WEB / "components" / "courrier" / "Courrier.tsx"
ATELIER_PAGE = WEB / "pages" / "atelier.tsx"

INTAKE_COMPONENTS = ("CrIntakeEntry", "CrArtefactCard", "CrArtefactTaskCard")


def test_the_intake_components_are_imported_by_a_page_and_rendered() -> None:
    """The failure WP-37 named: exported, tested, and mounted nowhere.

    Both halves are asserted, because an import alone proves nothing — an
    imported component that is never placed in the tree is the same dead screen
    with a passing type-check.
    """

    page = _read(MISSIONS_PAGE)
    pages = "\n".join(_read(path) for path in sorted(WEB.glob("pages/*.tsx")))
    for name in INTAKE_COMPONENTS:
        assert name in pages, f"{name} is exported and imported by no page"
        assert f"<{name}" in page, f"{name} is imported but never rendered"
    # The honest «non lu» state is on the surface too, or a document that could
    # not be read would simply vanish from the list.
    assert "<CrArtefactUnread" in page


def test_the_intake_view_reaches_every_route_wp34_shipped() -> None:
    page = _read(MISSIONS_PAGE)
    for call in (
        "apiService.getIntakeArtefacts()",
        "apiService.readIntakeText(",
        "apiService.readIntakePhoto(",
        "apiService.deleteIntakeArtefact(",
    ):
        assert call in page, f"{call} is not wired to the surface"


def test_the_intake_view_creates_no_mission(db_session: Session) -> None:
    """The expensive mistake this route makes if the guard is missing.

    ``/missions`` with no mission *creates* one — a paid generation — and then
    rewrites the URL to it. A learner who came to paste a letter would pay for a
    mission they never asked for and never see the intake.
    """

    page = _read(MISSIONS_PAGE)
    guard = page.split("const loadMission = useCallback", 1)[1].split("const requestId", 1)[0]
    assert "if (intakeMode)" in guard
    assert "return;" in guard
    assert "intakeMode" in page.split("}, [createSeededMission", 1)[1][:80], (
        "the guard must be in the callback's dependencies or it reads a stale flag"
    )


def test_the_intake_screen_keeps_exactly_one_press() -> None:
    """Design principle 1, on a screen that renders two components that each own one.

    ``CrIntakeEntry`` has the 3D press («Faire lire»); ``CrArtefactTaskCard``
    has one too when it is given ``onStart``. It is not given one here — the
    reply is written in the Courrier, where the composer and the corrector
    already live — so the task card renders no button at all.
    """

    page = _read(MISSIONS_PAGE)
    branch = page.split("{intakeMode ? (", 1)[1].split(") : loading && !mission ? (", 1)[0]
    assert "<CrArtefactTaskCard task={artefact.task} />" in branch
    assert "onStart=" not in branch
    assert "tone=\"primary\"" not in branch
    assert "tone='primary'" not in branch


def test_the_courrier_offers_a_row_into_the_intake_never_a_second_press() -> None:
    source = _read(COURRIER)
    assert "export const CR_INTAKE_HREF = '/missions?intake=1';" in source
    block = source.split("export function CrIntakeLink(", 1)[1].split("export function CrIntakeEntry", 1)[0]
    assert 'className="av2-row"' in block, "the quiet row shape Home already uses"
    assert "Action" not in block and "tone=" not in block
    assert "Apportez votre français" in block
    # …and the Courrier actually renders it.
    assert "<CrIntakeLink />" in _read(MISSIONS_PAGE)


def test_the_home_entry_exists_now_that_the_screen_does() -> None:
    """WP-37 withheld this row because it would have opened an empty screen.

    It is still gated: a learner whose weekly allowance is spent is not sent to
    a screen that can only tell them to come back next week.
    """

    source = _read(ATELIER_PAGE)
    assert "apiService.getIntakeArtefacts()" in source
    assert "envelope?.cap?.enabled" in source
    entries = source.split("const homeEntries: HomeEntry[]", 1)[1].split("const homeTiles", 1)[0]
    assert "intakeOpen" in entries
    assert "Vos documents" in entries
    # One constant for the destination, shared with the Courrier's own row.
    assert "CR_INTAKE_HREF" in entries
    assert "from '@/components/courrier/Courrier'" in source


def test_home_still_draws_exactly_one_primary_action() -> None:
    """A third quiet row must not have become a third press bar."""

    home = _read(WEB / "components" / "atelier-v2" / "home" / "HomeScreen.tsx")
    assert home.count('tone="primary"') == 1


# ==========================================================================
# 2. The radio transport goes through the facade (WP-32 §9.1 / WP-37 §4)
# ==========================================================================

def test_the_radio_components_no_longer_reach_for_apiservice() -> None:
    hook = _read(WEB / "components" / "atelier-v2" / "journey" / "useEpisodeAudio.ts")
    step = _read(WEB / "components" / "atelier-v2" / "journey" / "StoryEpisodeStep.tsx")
    assert "apiService" not in hook
    assert "apiService" not in step
    for name in ("getEpisodeAudio", "synthesizeEpisodeAudio", "getEpisodeAudioClip"):
        assert name in hook
    assert "recordEpisodePrediction" in step
    assert "from '@/services/daily-journey'" in hook
    assert "from '@/services/daily-journey'" in step
    # The facade still exports them — switching the callers is only half of it.
    facade = _read(WEB / "services" / "daily-journey.ts")
    for name in (
        "export const getEpisodeAudio",
        "export const synthesizeEpisodeAudio",
        "export const getEpisodeAudioClip",
        "export const recordEpisodePrediction",
    ):
        assert name in facade


def test_the_prediction_call_stays_outside_the_mutation_service() -> None:
    """WP-32 §3: the prediction check is measurement, never marking."""

    facade = _read(WEB / "services" / "daily-journey.ts")
    body = facade.split("export const recordEpisodePrediction", 1)[0]
    assert "dailyJourneyService" in body, "the reward authority is declared above the transport"


# ==========================================================================
# 3. The day-before rehearsal push is sent, once (WP-31 §7.2 / WP-37 §6)
# ==========================================================================

class _FakeNotifications:
    """Counts deliveries the way the real service does: one per subscribed device."""

    sent: list[tuple[str, str, dict]] = []
    deliveries = 1

    def __init__(self, db) -> None:
        self.db = db

    def send_notification(self, user_id, message, title="", *, data=None) -> int:
        type(self).sent.append((str(title), str(message), dict(data or {})))
        return type(self).deliveries


@pytest.fixture()
def fake_push(monkeypatch: pytest.MonkeyPatch):
    import app.services.notification_service as notification_service

    _FakeNotifications.sent = []
    _FakeNotifications.deliveries = 1
    monkeypatch.setattr(notification_service, "NotificationService", _FakeNotifications)
    return _FakeNotifications


def _rehearsal(
    db_session: Session,
    user: User,
    *,
    status: str = "ready",
    event_date: date | None = None,
    goal: str = "Demander une réparation du chauffage",
) -> Rehearsal:
    row = Rehearsal(
        id=uuid.uuid4(),
        user_id=user.id,
        status=status,
        declaration="call the landlord about the heating",
        brief={"goal_fr": goal, "counterpart": "le propriétaire", "register": "vous"},
        scene={},
        turns=[],
        debrief={},
        event_date=event_date if event_date is not None else DAY + timedelta(days=1),
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_the_reminder_is_sent_once_however_often_the_beat_runs(
    db_session: Session, fake_push
) -> None:
    """The morning beat runs every few minutes. Twice is a learner unsubscribing."""

    from app.tasks.notifications import REHEARSAL_REMINDER_EVENT, _send_rehearsal_reminder

    user = _user(db_session)
    _rehearsal(db_session, user)
    now = datetime(2026, 9, 11, 9, 0)

    assert _send_rehearsal_reminder(db_session, user, now) == 1
    assert _send_rehearsal_reminder(db_session, user, now) == 0
    assert _send_rehearsal_reminder(db_session, user, now) == 0
    assert len(fake_push.sent) == 1

    rows = (
        db_session.query(PilotEvent)
        .filter(
            PilotEvent.user_id == user.id,
            PilotEvent.event_type == REHEARSAL_REMINDER_EVENT,
        )
        .all()
    )
    assert len(rows) == 1
    # WP-37 §6's key: its own, and per learner per day.
    assert rows[0].entity_id == f"rehearsal-ready:{user.id}:2026-09-11"


def test_the_reminder_opens_the_rehearsal_and_names_the_learners_own_goal(
    db_session: Session, fake_push
) -> None:
    from app.tasks.notifications import _send_rehearsal_reminder

    user = _user(db_session)
    _rehearsal(db_session, user, goal="Appeler le propriétaire pour le chauffage")
    _send_rehearsal_reminder(db_session, user, datetime(2026, 9, 11, 9, 0))

    title, message, data = fake_push.sent[0]
    assert "Appeler le propriétaire pour le chauffage" in message
    assert data["route"] == "/repetition"
    assert data["kind"] == "rehearsal_reminder"
    assert title


def test_a_learner_with_nothing_tomorrow_is_not_pushed(db_session: Session, fake_push) -> None:
    from app.tasks.notifications import _send_rehearsal_reminder

    user = _user(db_session)
    _rehearsal(db_session, user, event_date=DAY + timedelta(days=4))

    assert _send_rehearsal_reminder(db_session, user, datetime(2026, 9, 11, 9, 0)) == 0
    assert fake_push.sent == []
    assert db_session.query(PilotEvent).filter(PilotEvent.user_id == user.id).count() == 0


def test_an_undelivered_reminder_is_never_marked_as_sent(
    db_session: Session, fake_push
) -> None:
    """No device took it. Recording it would burn the only day it can be sent."""

    from app.tasks.notifications import REHEARSAL_REMINDER_EVENT, _send_rehearsal_reminder

    fake_push.deliveries = 0
    user = _user(db_session)
    _rehearsal(db_session, user)

    assert _send_rehearsal_reminder(db_session, user, datetime(2026, 9, 11, 9, 0)) == 0
    assert (
        db_session.query(PilotEvent)
        .filter(
            PilotEvent.user_id == user.id,
            PilotEvent.event_type == REHEARSAL_REMINDER_EVENT,
        )
        .count()
        == 0
    )


def test_the_edition_and_the_reminder_do_not_block_each_other(
    db_session: Session, fake_push, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The trap in the call site: the edition's dedupe used to ``continue``.

    A learner whose edition already went out today would then never hear that
    the real thing is tomorrow — the push would be dead for exactly the learners
    who use the app.
    """

    import app.tasks.notifications as tasks

    user = _user(db_session)
    _rehearsal(db_session, user)
    now = datetime.now(tasks.PARIS_TZ)
    user.reminder_time = f"{now.hour:02d}:{now.minute:02d}"
    user.is_active = True
    user.notifications_enabled = True
    user.practice_reminders = True
    db_session.add(
        PushSubscription(
            id=uuid.uuid4(),
            user_id=user.id,
            endpoint=f"https://example.test/{uuid.uuid4().hex}",
            keys={"p256dh": "x", "auth": "y"},
        )
    )
    # Today's edition has already gone out.
    db_session.add(
        PilotEvent(
            id=uuid.uuid4(),
            user_id=user.id,
            event_type="morning_edition_sent",
            entity_type="notification",
            entity_id=now.date().isoformat(),
            payload={},
        )
    )
    db_session.commit()

    class _Session:
        def __enter__(self):
            return db_session

        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            return None

    monkeypatch.setattr(tasks, "SessionLocal", lambda: _Session())
    # The rehearsal is dated relative to the real clock for this one test.
    row = db_session.query(Rehearsal).filter(Rehearsal.user_id == user.id).one()
    row.event_date = now.date() + timedelta(days=1)
    db_session.commit()

    result = tasks.send_morning_editions()

    assert result["rehearsal_reminders_sent"] == 1
    assert len(fake_push.sent) == 1, "the edition was deduped; the reminder still went"
    assert fake_push.sent[0][2]["route"] == "/repetition"


# ==========================================================================
# 4. `scenario_key` is the authored catalogue (WP-37 §1, last paragraph)
# ==========================================================================

def test_the_event_vocabulary_is_the_authored_scenarios_not_the_enum() -> None:
    """`register` is a dimension of a respond turn. Nothing writes it as a scenario."""

    from app.services.journey_content import SCENARIO_PRIORITY

    for key in SCENARIO_PRIORITY:
        clean, dropped = journey_events.sanitize_metadata({"scenario_key": str(key)})
        assert clean["scenario_key"] == str(key)
        assert dropped == []

    clean, dropped = journey_events.sanitize_metadata({"scenario_key": "register"})
    assert clean == {}
    assert dropped == ["scenario_key"]
    # …and the enum really does still carry it, so this is a narrowing and not a
    # test of an absent member.
    assert str(CapabilityKey.REGISTER) == "register"


def test_a_rejected_scenario_key_is_reported_by_name_and_never_echoed() -> None:
    clean, dropped = journey_events.sanitize_metadata({"scenario_key": "j'ai dit une café"})
    assert clean == {}
    assert dropped == ["scenario_key"]


def test_the_contract_freeze_records_the_register_row() -> None:
    """WP-37 drafted row 16 and left it unapplied; revision 2 carries it now."""

    text = _read(ROOT / "docs" / "implementation" / "atelier-v2" / "CONTRACT-FREEZE.md")
    row = [line for line in text.splitlines() if line.startswith("| 16 |")]
    assert len(row) == 1, "row 16 is missing or duplicated"
    assert "`CapabilityKey` gains `register`" in row[0]
    assert "SCENARIO_PRIORITY" in row[0]


# ==========================================================================
# 5. WP-36's hooks
# ==========================================================================

def test_the_self_repair_suite_runs_in_package_json_and_in_ci() -> None:
    package = json.loads(_read(WEB / "package.json"))["scripts"]
    workflow = _read(ROOT / ".github" / "workflows" / "ci.yml")
    assert package["test:self-repair"] == (
        "node components/atelier-v2/journey/journey-self-repair.test.js"
    )
    # CI runs every node suite through `npm test` (WP-85; see test_wp85_ci.py).
    assert "npm test" in workflow
    assert (
        WEB / "components" / "atelier-v2" / "journey" / "journey-self-repair.test.js"
    ).exists()


def test_a_rehearsal_hands_the_policy_the_characters_own_lines(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP-36 §8.3. Without this the loop cannot close in a rehearsal.

    The policy recomputes *have I already asked?* and *is this turn the answer?*
    from the counterpart's previous lines. A history of learner turns only means
    a rehearsal could be prompted once — on its first turn, where there is
    nothing to recognise — and the repair could never be recognised, credited or
    corrected.
    """

    import app.services.rehearsal as rehearsal_module

    captured: dict[str, object] = {}

    class _Stop(RuntimeError):
        pass

    def _capture(db, **kwargs):
        captured.update(kwargs)
        raise _Stop

    monkeypatch.setattr(rehearsal_module, "evaluate_response", _capture)

    user = _user(db_session)
    row = _rehearsal(db_session, user, status="rehearsing")
    row.scene = {"turns": 4, "register": "vous", "counterpart_name": "Le propriétaire"}
    row.turns = [
        {
            "index": 0,
            "scored": True,
            "learner_text": "Bonjour, j'ai une problème avec le chauffage.",
            "reply_fr": "Pardon, un ou une problème ?",
        }
    ]
    db_session.commit()

    with pytest.raises(_Stop):
        RehearsalService(db_session).respond(
            user, row, text="Un problème, pardon.", turn_index=1
        )

    history = captured["history"]
    assert history == [
        {
            "role": "learner",
            "text": "Bonjour, j'ai une problème avec le chauffage.",
            "character": "Pardon, un ou une problème ?",
        }
    ]
    # The shape the policy actually reads.
    assert jc._character_history_texts(history) == ["Pardon, un ou une problème ?"]


def _erratum(db_session: Session, user: User) -> UserError:
    ErrorMemoryService(db_session).record_erratum(
        user=user,
        erratum={
            "display_label": "Le genre des noms",
            "learner_text": "une café",
            "corrected_target": "un café",
            "why_wrong": "café is masculine",
            "repair_hint": "un café",
            "task_error_type": "Le genre des noms",
            "severity": 2,
        },
        source_type="daily_journey",
        source_payload={"foreground": True},
    )
    db_session.commit()
    error = (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id)
        .order_by(UserError.created_at.desc())
        .first()
    )
    assert error is not None
    error.state = ERROR_STATE_OPEN
    error.next_review_date = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()
    db_session.refresh(error)
    return error


def _evaluate(db_session: Session, user: User, text: str):
    jc_content.reset_content_cache()
    brief = jc_content.resolve_scenario_brief(
        db_session, user=user, scenario_key=CapabilityKey.ORDER_AT_CAFE
    )
    return jc.evaluate_response(
        db_session,
        user=user,
        scenario=brief,
        task=brief.response_task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        turn_index=0,
        assistance=AssistanceLevel.NONE,
        history=None,
    )


def test_the_grading_carries_out_why_the_policy_stayed_quiet_or_spoke(
    db_session: Session,
) -> None:
    """WP-36 §8.4's precondition: the decision was taken and then discarded."""

    user = _user(db_session)
    quiet = _evaluate(db_session, user, "Bonjour, je voudrais un café, s'il vous plaît.")
    assert quiet.feedback_reason == "no_open_errata"

    _erratum(db_session, user)
    prompted = _evaluate(db_session, user, "Bonjour, je voudrais une café, s'il vous plaît.")
    assert prompted.feedback_reason == "recurrence"
    assert prompted.character_reply_fr.endswith("Pardon, un ou une café ?")


def test_the_reason_never_changes_what_the_turn_was_worth(db_session: Session) -> None:
    """A telemetry field that moved a grade would be worse than no telemetry.

    Two learners, the same sentence; one has the mistake on record and one does
    not. The prompted learner is asked a question and the other is not — and the
    turn is worth exactly the same to both.
    """

    text = "Bonjour, je voudrais une café, s'il vous plaît."
    untouched = _user(db_session)
    plain = _evaluate(db_session, untouched, text)

    prompted_user = _user(db_session)
    _erratum(db_session, prompted_user)
    graded = _evaluate(db_session, prompted_user, text)

    assert graded.feedback_reason == "recurrence"
    assert plain.feedback_reason == "no_open_errata"
    assert graded.outcome is plain.outcome
    assert graded.turn_consumed is plain.turn_consumed
    assert graded.correction is None, "a prompt and its answer in one breath is a recast"


def _telemetry(db_session: Session, user: User, *, reason: str, needs_repair: bool = True):
    service = DailyJourneyService(db_session, build_default_adapters())
    journey = SimpleNamespace(id=uuid.uuid4())
    step = SimpleNamespace(id=uuid.uuid4(), turn_index=1)
    evaluation = SimpleNamespace(
        feedback_reason=reason,
        outcome=TaskOutcome.MET,
        needs_repair=needs_repair,
    )
    service._record_feedback_decision(user, journey, step, evaluation)
    db_session.flush()
    return (
        db_session.query(PilotEvent)
        .filter(
            PilotEvent.user_id == user.id,
            PilotEvent.event_type == SELF_REPAIR_EVENT_TYPE,
        )
        .all()
    )


def test_a_prompted_repair_and_its_outcome_are_countable(db_session: Session) -> None:
    user = _user(db_session)
    rows = _telemetry(db_session, user, reason="repair_not_attempted", needs_repair=False)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["reason"] == "repair_not_attempted"
    assert payload["elicited"] is False
    assert payload["turn_index"] == 1
    # Telemetry, not a transcript: nothing the learner wrote is in the row.
    assert set(payload) == {"reason", "journey_id", "turn_index", "outcome", "elicited"}


def test_the_ordinary_turn_writes_no_row(db_session: Session) -> None:
    """Every turn in the app is `no_open_errata`; a row each would bury the six."""

    user = _user(db_session)
    assert _telemetry(db_session, user, reason="no_open_errata") == []
    assert _telemetry(db_session, user, reason="") == []


def test_telemetry_can_never_break_a_turn(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.pilot_events as pilot_events

    class _Broken:
        def __init__(self, db) -> None:
            raise RuntimeError("ledger down")

    monkeypatch.setattr(pilot_events, "PilotEventService", _Broken)
    user = _user(db_session)
    # No exception escapes: the learner keeps their turn.
    assert _telemetry(db_session, user, reason="repair_succeeded") == []


# ==========================================================================
# 6. …and the digest can read it
# ==========================================================================

def _self_repair_event(db_session: Session, user: User, reason: str) -> None:
    db_session.add(
        PilotEvent(
            id=uuid.uuid4(),
            user_id=user.id,
            event_type=SELF_REPAIR_EVENT_TYPE,
            entity_type="daily_journey_step",
            entity_id=str(uuid.uuid4()),
            payload={"reason": reason},
            occurred_at=NOW,
        )
    )
    db_session.flush()


def test_the_digest_line_says_none_rather_than_nought_per_cent(db_session: Session) -> None:
    """A rate with no denominator is not a measurement.

    Read for one learner: unlike the rehearsal and intake lines, this one *is*
    filterable, because every row carries the learner it belongs to.
    """

    from pilot_digest import format_self_repair_line

    user = _user(db_session)
    line = format_self_repair_line(db_session, DAY, str(user.id))
    assert "none" in line
    assert "%" not in line


def test_a_window_with_prompts_but_no_answers_prints_no_rate(db_session: Session) -> None:
    """The prompt and its answer fall in different windows. A rate here would lie."""

    from pilot_digest import format_self_repair_line

    user = _user(db_session)
    _self_repair_event(db_session, user, "recurrence")
    line = format_self_repair_line(db_session, DAY, str(user.id))
    assert "1 prompt(s) asked, 0 answered" in line
    assert "%" not in line


def test_the_uptake_rate_carries_its_denominator_and_names_the_ignored(
    db_session: Session,
) -> None:
    from pilot_digest import format_self_repair_line

    user = _user(db_session)
    for reason in ("recurrence", "recurrence", "repair_succeeded", "repair_failed"):
        _self_repair_event(db_session, user, reason)
    _self_repair_event(db_session, user, "repair_not_attempted")
    _self_repair_event(db_session, user, "last_turn")

    line = format_self_repair_line(db_session, DAY, str(user.id))
    assert "2 prompt(s) asked, 3 answered" in line
    assert "repaired 1/3 (33 %)" in line
    assert "ignored 1" in line
    assert "1 prompt(s) withheld by the bounds" in line


def test_the_digest_script_still_calls_every_line_it_defines() -> None:
    """WP-37's own rule, extended to this package's line."""

    source = _read(ROOT / "scripts" / "pilot_digest.py")
    body = source.split("def main() -> None:", 1)[1]
    defined = [
        line.split("(", 1)[0].removeprefix("def ")
        for line in source.splitlines()
        if line.startswith("def format_")
    ]
    assert "format_self_repair_line" in defined
    for name in defined:
        assert f"{name}(" in body, f"{name} is defined but never printed"
