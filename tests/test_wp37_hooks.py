"""WP-37 — the hooks the 2026-09-10 packages left owed outside their leases.

Eight packages landed on 2026-09-10 and each one stopped at the edge of its
lease, writing the missing diff into its handover instead of applying it. The
cost of that discipline is that several of them shipped dark: a helper nobody
calls prints nothing, a summary the enum cannot carry never reaches the wire,
and a screen with no entry point is a screen nobody opens.

This file pins what WP-37 wired, in the order the deliverable lists it:

1. **`CapabilityKey.REGISTER`** (WP-33) is on the wire, exactly once, and the
   finish recap and the progress endpoint both still answer 200. The dimension
   is *not* a scenario, and nothing groups evidence under it.
2. **The digest lines** (WP-30 §7, WP-31 §7.3, WP-32 §9.3, WP-33, WP-34) — each
   one honest on an empty window: "none" and "nothing to report" are results; a
   zero that reads like a measurement is not.
3. **The day-before rehearsal push** (WP-31 §7.2) — only for a rehearsal still
   unplayed, and it names the learner's own goal, never a story character.
4. **The frontend seams** (WP-31 §7.1, WP-32 §9.1–9.2, WP-35) — source scans in
   the style of the other `test_frontend_*` pins: the Home entries, the Réglages
   listen-first row, the journey facade's radio exports, and the three node
   suites in `package.json` and CI.

No model call is made anywhere in this file.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models.pilot_event import PilotEvent
from app.db.models.rehearsal import Rehearsal
from app.db.models.user import User
from app.services import journey_capabilities
from app.services.journey_capabilities import build_capability_summary
from app.services.journey_contracts import CapabilityKey
from app.services.serial_notifications import (
    REHEARSAL_READY_TITLE,
    rehearsal_reminder_copy,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"
sys.path.insert(0, str(ROOT / "scripts"))

DAY = date(2026, 9, 11)
NOW = datetime(2026, 9, 11, 9, 0, tzinfo=UTC)


def _read(path: Path) -> str:
    assert path.exists(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def _user(db_session: Session) -> User:
    user = User(
        id=uuid4(),
        email=f"wp37-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
        cefr_estimate="A2.1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _event(
    db_session: Session,
    *,
    event_type: str,
    user: User | None = None,
    payload: dict | None = None,
    cost: float = 0.0,
    when: datetime = NOW,
) -> PilotEvent:
    row = PilotEvent(
        id=uuid4(),
        event_type=event_type,
        user_id=user.id if user else None,
        payload=payload or {},
        cost_usd=cost,
        occurred_at=when,
    )
    db_session.add(row)
    db_session.flush()
    return row


# ==========================================================================
# 1. The register dimension reaches the wire — once
# ==========================================================================

def test_the_enum_carries_register_last_and_the_summary_prints_it_once(
    db_session: Session,
) -> None:
    user = _user(db_session)
    keys = [
        str(item.capability_key)
        for item in build_capability_summary(db_session, user=user).capabilities
    ]
    assert keys == ["order_at_cafe", "arrange_meeting", "explain_delay", "register"]
    assert len(keys) == len(set(keys)), "the dimension must not be summarised twice"


def test_register_is_a_dimension_and_never_a_scenario(db_session: Session) -> None:
    """Nothing groups, reads or plans evidence under it.

    `_CAPABILITY_ORDER` used to be `tuple(CapabilityKey)`. Had it stayed that,
    the enum line would have asked the evidence reader for a scenario nothing
    writes, and `_TITLES[language][REGISTER]` would have raised on every call.
    """

    from app.services.journey_content import SCENARIO_PRIORITY

    assert CapabilityKey.REGISTER not in SCENARIO_PRIORITY
    assert CapabilityKey.REGISTER not in journey_capabilities._SCENARIO_KEYS
    assert journey_capabilities._CAPABILITY_ORDER == journey_capabilities._SCENARIO_KEYS
    for language in ("en", "de", "fr"):
        assert CapabilityKey.REGISTER not in journey_capabilities._TITLES[language]


def test_the_pydantic_contract_accepts_the_new_key(db_session: Session) -> None:
    """A key the schema has never heard of is what would 500 the finish recap."""

    from app.schemas.daily_journey import CapabilitySummary

    summary = CapabilitySummary(
        capability_key="register",
        title_native="Speak to the right person the right way",
        state="not_tried",
        modalities=[],
        latest_qualifying_on=None,
        evidence=[],
    )
    assert summary.capability_key is CapabilityKey.REGISTER
    assert json.loads(summary.model_dump_json())["capability_key"] == "register"


def test_the_frozen_progress_fixture_gained_the_dimension_and_nothing_else() -> None:
    """The contract change is additive: three unchanged entries, one appended."""

    fixture = json.loads(
        _read(
            ROOT
            / "tests"
            / "fixtures"
            / "daily_journey_v1"
            / "public"
            / "unknown_legacy_assistance.json"
        )
    )["response"]
    keys = [item["capability_key"] for item in fixture["capabilities"]]
    assert keys == ["order_at_cafe", "arrange_meeting", "explain_delay", "register"]
    assert fixture["contract_version"] == 1, "no existing field changed meaning"
    assert fixture["capabilities"][-1]["state"] == "not_tried"


# ==========================================================================
# 2. The digest lines
# ==========================================================================

def test_every_new_digest_line_is_honest_about_an_empty_day(db_session: Session) -> None:
    """The shared property: no data prints "none", never a manufactured zero."""

    from pilot_digest import (
        format_episode_audio_line,
        format_episode_prediction_line,
        format_intake_line,
        format_journal_lines,
        format_register_line,
        format_rehearsal_line,
    )

    empty = date(2019, 1, 1)
    assert "nothing to report" in format_rehearsal_line(db_session, empty)
    assert "nothing to report" in format_intake_line(db_session, empty)
    assert format_episode_audio_line(db_session, empty) == "Radio episodes (synthesis): none"
    assert (
        format_episode_prediction_line(db_session, empty)
        == "Radio episodes (prediction): none"
    )
    assert format_journal_lines(db_session, empty) == [
        "Journal corrections: none",
        "Journal follow-ups (+7d): none answered — nothing to report",
    ]
    assert "nothing to report" in format_register_line({"journey": {"capabilities": {}}})
    # And none of them prints a percentage of nothing.
    for line in (
        format_rehearsal_line(db_session, empty),
        format_intake_line(db_session, empty),
        format_episode_audio_line(db_session, empty),
        format_episode_prediction_line(db_session, empty),
        *format_journal_lines(db_session, empty),
    ):
        assert "0%" not in line and "0 %" not in line


def test_the_synthesis_line_prints_the_cache_hit_rate_and_says_the_money_is_modelled(
    db_session: Session,
) -> None:
    from pilot_digest import format_episode_audio_line

    from app.services.episode_audio import EPISODE_AUDIO_EVENT_TYPE

    user = _user(db_session)
    _event(
        db_session,
        event_type=EPISODE_AUDIO_EVENT_TYPE,
        user=user,
        payload={"lines": 6, "cached_lines": 2, "model": "tts-1-hd", "status": "ok"},
        cost=0.012,
    )
    _event(
        db_session,
        event_type=EPISODE_AUDIO_EVENT_TYPE,
        user=user,
        payload={"lines": 1, "cached_lines": 1, "model": "tts-1-hd", "status": "failed"},
        cost=0.002,
    )
    line = format_episode_audio_line(db_session, DAY, str(user.id))

    assert "2 paying run(s)" in line
    assert "1 learner(s)" in line
    assert "7 lines synthesized, 3 from cache (30% of the lines these runs served)" in line
    assert "estimated from characters, not a provider bill" in line
    assert "$0.0140/listening learner" in line
    assert "1 run(s) failed and served no clips" in line


def test_the_prediction_line_counts_and_refuses_to_call_it_an_accuracy_rate(
    db_session: Session,
) -> None:
    from pilot_digest import format_episode_prediction_line

    from app.services.episode_audio import PREDICTION_EVENT_TYPE

    user = _user(db_session)
    for verdict in ("confirmed", "confirmed", "other", "unresolved"):
        _event(
            db_session,
            event_type=PREDICTION_EVENT_TYPE,
            user=user,
            payload={"verdict": verdict, "guess": "oui"},
        )
    line = format_episode_prediction_line(db_session, DAY, str(user.id))

    assert "n=4" in line
    assert "confirmed:2, other:1, unresolved:1" in line
    assert "not an accuracy rate" in line
    assert "%" not in line, "a two-way guess must never be printed as a percentage"


def test_the_journal_prints_its_cost_and_its_retention_signal_apart(
    db_session: Session,
) -> None:
    from pilot_digest import format_journal_lines

    from app.services.journal import JOURNAL_EVENT_TYPE, JOURNAL_FOLLOWUP_EVENT_TYPE

    user = _user(db_session)
    _event(
        db_session,
        event_type=JOURNAL_EVENT_TYPE,
        user=user,
        payload={"total_tokens": 900, "model": "gpt-5-mini"},
        cost=0.0021,
    )
    _event(
        db_session,
        event_type=JOURNAL_FOLLOWUP_EVENT_TYPE,
        user=user,
        payload={"signal": "used_again_later"},
    )
    _event(
        db_session,
        event_type=JOURNAL_FOLLOWUP_EVENT_TYPE,
        user=user,
        payload={"signal": "not_recalled"},
    )
    cost_line, retention_line = format_journal_lines(db_session, DAY, str(user.id))

    assert cost_line == "Journal corrections: 1 calls · 900 tokens · $0.0021 · gpt-5-mini"
    assert "1/2 still recalled a stored fact" in retention_line
    # CONTRACTS §8: the journal's signal is named apart from journey evidence.
    assert "not journey evidence" in retention_line


def test_the_register_line_is_read_off_the_rollup_rather_than_rescored() -> None:
    from pilot_digest import format_register_line

    report = {
        "journey": {
            "capabilities": {
                "learners_measured": 3,
                "by_capability": {
                    "order_at_cafe": {"independent_once": 3},
                    "register": {"independent_once": 2, "unknown": 1},
                },
            }
        }
    }
    line = format_register_line(report)
    assert "n=3 learners" in line
    assert "independent_once:2, unknown:1" in line
    assert "never as a pass" in line


def test_the_digest_says_when_a_cohort_wide_line_ignores_the_user_filter(
    db_session: Session,
) -> None:
    """`rehearsal_digest_line` and `intake_digest_line` take no learner filter.

    Printing them under a `--user-id` run without saying so would read as one
    learner's numbers.
    """

    from pilot_digest import format_intake_line, format_rehearsal_line

    who = str(uuid4())
    assert "not filtered by --user-id" in format_rehearsal_line(db_session, DAY, who)
    assert "not filtered by --user-id" in format_intake_line(db_session, DAY, who)
    assert "not filtered by --user-id" not in format_rehearsal_line(db_session, DAY)


def test_the_digest_script_calls_every_line_it_defines() -> None:
    """A formatter nobody calls is exactly the failure this package exists to fix."""

    source = _read(ROOT / "scripts" / "pilot_digest.py")
    body = source.split("def main() -> None:", 1)[1]
    for name in (
        "format_rehearsal_line",
        "format_intake_line",
        "format_episode_audio_line",
        "format_episode_prediction_line",
        "format_journal_lines",
        "format_register_line",
    ):
        assert f"{name}(" in body, f"{name} is defined but never printed"


# ==========================================================================
# 3. The day-before rehearsal push (WP-31 §7.2)
# ==========================================================================

def _rehearsal(
    db_session: Session,
    user: User,
    *,
    status: str,
    event_date: date | None,
    goal: str = "Demander une réparation du chauffage",
) -> Rehearsal:
    row = Rehearsal(
        id=uuid4(),
        user_id=user.id,
        status=status,
        declaration="call the landlord about the heating",
        brief={"goal_fr": goal, "counterpart": "le propriétaire", "register": "vous"},
        scene={},
        turns=[],
        debrief={},
        event_date=event_date,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_the_push_fires_the_day_before_and_names_the_learners_own_goal(
    db_session: Session,
) -> None:
    user = _user(db_session)
    _rehearsal(db_session, user, status="ready", event_date=DAY + timedelta(days=1))

    copy = rehearsal_reminder_copy(db_session, user, today=DAY)

    assert copy is not None
    title, message = copy
    assert title == REHEARSAL_READY_TITLE
    assert message == "Demander une réparation du chauffage"


@pytest.mark.parametrize("status", ["rehearsed", "debriefed", "declared", "not_prepared", "abandoned"])
def test_the_push_never_fires_for_a_rehearsal_that_is_not_waiting_to_be_played(
    db_session: Session, status: str
) -> None:
    user = _user(db_session)
    _rehearsal(db_session, user, status=status, event_date=DAY + timedelta(days=1))

    assert rehearsal_reminder_copy(db_session, user, today=DAY) is None


@pytest.mark.parametrize("offset", [0, 2, -1])
def test_the_push_only_speaks_about_tomorrow(db_session: Session, offset: int) -> None:
    user = _user(db_session)
    _rehearsal(db_session, user, status="ready", event_date=DAY + timedelta(days=offset))

    assert rehearsal_reminder_copy(db_session, user, today=DAY) is None


def test_a_rehearsal_without_a_resolved_date_is_never_reminded_about(
    db_session: Session,
) -> None:
    user = _user(db_session)
    _rehearsal(db_session, user, status="ready", event_date=None)

    assert rehearsal_reminder_copy(db_session, user, today=DAY) is None


def test_a_goalless_brief_falls_back_to_a_line_that_claims_nothing(
    db_session: Session,
) -> None:
    user = _user(db_session)
    _rehearsal(db_session, user, status="rehearsing", event_date=DAY + timedelta(days=1), goal="")

    copy = rehearsal_reminder_copy(db_session, user, today=DAY)
    assert copy == (REHEARSAL_READY_TITLE, "C’est demain. Répétez-la une fois.")


def test_the_push_is_another_learners_business_only(db_session: Session) -> None:
    owner = _user(db_session)
    stranger = _user(db_session)
    _rehearsal(db_session, owner, status="ready", event_date=DAY + timedelta(days=1))

    assert rehearsal_reminder_copy(db_session, stranger, today=DAY) is None


def test_the_push_copy_names_no_story_character(db_session: Session) -> None:
    """WP-31 §2: a rehearsal is biography, not canon."""

    source = _read(ROOT / "app" / "services" / "serial_notifications.py")
    body = source.split("def rehearsal_reminder_copy(", 1)[1].split("\n__all__", 1)[0]
    for name in ("Romy", "Margaux", "Lila"):
        assert name not in body


# ==========================================================================
# 4. The frontend seams
# ==========================================================================

HOME_SCREEN = WEB / "components" / "atelier-v2" / "home" / "HomeScreen.tsx"
ATELIER_PAGE = WEB / "pages" / "atelier.tsx"
SETTINGS_PAGE = WEB / "pages" / "settings.tsx"
JOURNEY_FACADE = WEB / "services" / "daily-journey.ts"
EPISODE_MODEL = WEB / "components" / "atelier-v2" / "journey" / "story-episode-model.ts"


def test_home_can_carry_quiet_entries_and_they_are_rows_not_press_bars() -> None:
    source = _read(HOME_SCREEN)
    assert "export type HomeEntry" in source
    assert "entries?: HomeEntry[] | null;" in source
    block = source.split("{entries && entries.length > 0 && (", 1)[1].split(")}", 1)[0]
    assert 'className="av2-row"' in block
    assert "Action" not in block, "design principle 1: one primary action per screen"
    assert "tone=" not in block


def test_the_rehearsal_entry_is_gated_on_the_servers_own_answer() -> None:
    """`debrief_due` is non-null only on a day the rehearsal has something to ask."""

    source = _read(ATELIER_PAGE)
    assert "apiService.getRehearsalState()" in source
    assert "Boolean(envelope?.debrief_due)" in source
    entries = source.split("const homeEntries: HomeEntry[]", 1)[1].split("const homeTiles", 1)[0]
    assert "rehearsalDue" in entries
    assert "'/repetition'" in entries
    assert "Comment ça s’est passé ?" in entries


def test_the_dossier_entry_is_on_home_in_french_sentence_case() -> None:
    source = _read(ATELIER_PAGE)
    entries = source.split("const homeEntries: HomeEntry[]", 1)[1].split("const homeTiles", 1)[0]
    assert "Votre dossier" in entries
    assert "'/dossier'" in entries
    # An edition that failed to load offers no side doors.
    assert "errorOnlyPage" in entries
    assert "entries={homeEntries}" in source


def test_home_still_draws_exactly_one_primary_action() -> None:
    source = _read(HOME_SCREEN)
    assert source.count('tone="primary"') == 1


def test_reglages_offers_listen_first_through_the_readers_own_key() -> None:
    """WP-32 §9.2 — one key, so the two controls cannot disagree."""

    settings = _read(SETTINGS_PAGE)
    assert "readListenFirst" in settings and "writeListenFirst" in settings
    # WP-46: the row's words read in the learner's own language.
    assert "copy.row_listen_first" in settings
    listen_copy = _read(WEB / "lib" / "settings-copy.ts")
    for label in ("Listen first", "Zuerst hören", "Écouter d’abord"):
        assert label in listen_copy, label
    assert "st-listen-first-label" in settings
    # Read after mount: localStorage during render is a hydration mismatch.
    assert "useEffect(() => { setListenFirst(readListenFirst()); }, []);" in settings
    # …and it is still the reader's key, and still off by default.
    model = _read(EPISODE_MODEL)
    assert "LISTEN_FIRST_KEY = 'atelier.journey.listen-first'" in model
    assert "export function readListenFirst(fallback = false)" in model


def test_the_journey_facade_exports_the_radio_transport() -> None:
    source = _read(JOURNEY_FACADE)
    for name in (
        "export const getEpisodeAudio",
        "export const synthesizeEpisodeAudio",
        "export const getEpisodeAudioClip",
        "export const recordEpisodePrediction",
    ):
        assert name in source


def test_the_three_new_node_suites_are_in_package_json_and_in_ci() -> None:
    package = json.loads(_read(WEB / "package.json"))["scripts"]
    workflow = _read(ROOT / ".github" / "workflows" / "ci.yml")
    for script in ("test:rehearsal", "test:dossier", "test:courrier-intake"):
        assert script in package, f"{script} missing from package.json"
        assert f"npm run {script}" in workflow, f"{script} is not run in CI"
