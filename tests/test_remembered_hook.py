"""STORY_REMEMBERED_HOOK: tomorrow's hook remembers what the learner decided (#466, #455, #620).

* the decision is read from the scene's record: a clear yes or no to something a
  character put to the learner; a fact question, an off-script reply, a question back
  and a mixed «non … oui» day hold none;
* the line says the decision and leaves its consequence open, at the learner's level,
  never quoting the learner and never longer than the one line every surface prints;
* it is the day's one hook (end card, Done, Home, Quartier, tomorrow's page), «Précédemment»
  opens on it, a «Demain» pick keeps it, and the evening push carries it once, from the
  character, in place of the streak line;
* flag off, or no decision: the authored hook unchanged.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.db.models.push_subscription import PushSubscription
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import living_story as engine
from app.services import remembered_hook
from app.services import serial_notifications as copy
from app.services.story_tomorrow import _remembered_today
from app.tasks import notifications as tasks

LILA_WORLD = {"cast": [{"id": "lila_bonnet", "name": "Lila Bonnet"}]}

#: #620's walk, played back: a «non» with mistakes, then an off-script cat story.
PIZZA_NON = {
    "opening": "Tiens, une pizza ! On partage ?",
    "exchanges": [
        (
            "Non, je ne partage pas la pizza… tu a menti à Margaux",
            "Bon. Alors je la mange seule ! Et ce chat, il est à toi ?",
        ),
        ("Le chat s appelle Napoleon, il aime le poisson.", "Napoléon ! Quel nom."),
    ],
}
PIZZA_OUI = {
    "opening": "Tiens, une pizza ! On partage, d'accord ?",
    "exchanges": [("Oui, avec plaisir !", "Super, je coupe.")],
}
OFF_SCRIPT = {
    "opening": "Tiens, une pizza ! On partage ?",
    "exchanges": [
        ("Mon chat aime le poisson et il dort beaucoup.", "Ah, ton chat ! Il s'appelle comment ?")
    ],
}
FACT_QUESTION = {
    "opening": "Tu as faim ?",
    "exchanges": [("Non, merci.", "D'accord.")],
}
MIXED = {
    "opening": "Tiens, une pizza ! On partage ?",
    "exchanges": [
        ("Non, je ne partage pas.", "Bon. Tu lis la lettre avec moi ?"),
        ("Oui, je lis la lettre avec toi.", "Merci."),
    ],
}


def _exchanges(case: dict) -> list[dict]:
    return [
        {"learner": learner, "character": character} for learner, character in case["exchanges"]
    ]


@pytest.fixture()
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STORY_REMEMBERED_HOOK", True)


# -- 1. the decision ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "kind"),
    [
        (PIZZA_NON, "refused"),
        (PIZZA_OUI, "agreed"),
        (OFF_SCRIPT, None),
        (FACT_QUESTION, None),
        (MIXED, None),
    ],
    ids=["non", "oui", "off-script", "fact-question", "non-then-oui"],
)
def test_the_decision_is_a_clear_yes_or_no_to_a_choice_put_to_the_learner(case, kind) -> None:
    found = remembered_hook.decision(case["opening"], _exchanges(case))
    assert (found or {}).get("kind") == kind


def test_the_record_s_reading_of_a_turn_wins_over_the_words() -> None:
    exchanges = [{"learner": "Hmm, la pizza… bof.", "character": "Tant pis."}]
    assert remembered_hook.decision("On partage ?", exchanges) is None
    ledger = {"turns": [{"at": 0, "intent": "no"}]}
    assert remembered_hook.decision("On partage ?", exchanges, ledger) == {
        "kind": "refused",
        "at": 0,
    }


def test_a_question_back_is_no_decision() -> None:
    exchanges = [
        {"learner": "Pourquoi tu veux partager ?", "character": "Parce que j'ai trop faim."}
    ]
    assert remembered_hook.decision("On partage ?", exchanges) is None


# -- 2. the line ----------------------------------------------------------------------


@pytest.mark.parametrize("band", ["A1", "A2", "B1", "B2", "C1"])
@pytest.mark.parametrize("kind", ["refused", "agreed"])
@pytest.mark.parametrize("seed", ["a", "b", "c", "d"])
def test_every_line_is_short_unquoted_and_says_the_decision(band, kind, seed) -> None:
    row = remembered_hook.compose(
        {"kind": kind, "at": 0},
        character_id="lila_bonnet",
        name="Lila",
        band=band,
        seed=seed,
        date="2026-11-21",
    )
    assert row is not None
    line = row["text_fr"]
    assert line == row["open_fr"]
    assert remembered_hook.problem(line) is None
    assert len(line.split()) <= remembered_hook.MAX_WORDS
    assert not re.search(r"[«»\"“”]", line)
    assert line.startswith(
        "Tu as dit non à Lila." if kind == "refused" else "Tu as dit oui à Lila."
    )
    assert "{" not in line and "  " not in line
    assert "que elle" not in line and "que il" not in line
    if band.startswith("A"):
        # Below B1: no inversion, no subjunctive, nothing past the passé composé of «dire».
        assert "-t-" not in line and "reste à" not in line.casefold()
    assert row["remembered"]["recalled_fr"] in line
    assert set(row["remembered"]["native"]) == {"en", "de"}
    assert row["source"] == "remembered"


def test_a_person_whose_gender_the_learner_picks_is_named_not_given_a_pronoun() -> None:
    for seed in "abcdef":
        row = remembered_hook.compose(
            {"kind": "refused", "at": 0},
            character_id="camille_marchand",
            name="Camille",
            band="A1",
            seed=seed,
            date="d",
        )
        assert " elle " not in f" {row['text_fr']} " and " il " not in f" {row['text_fr']} ", row[
            "text_fr"
        ]


def test_a_second_non_in_the_week_is_a_different_line() -> None:
    first = remembered_hook.compose(
        {"kind": "refused"}, character_id="lila_bonnet", name="Lila", band="B1", seed="s", date="d"
    )
    second = remembered_hook.compose(
        {"kind": "refused"},
        character_id="lila_bonnet",
        name="Lila",
        band="B1",
        seed="s",
        date="d",
        used=[first["text_fr"]],
    )
    assert second["text_fr"] != first["text_fr"] and second["text_fr"].startswith(
        "Tu as dit non à Lila."
    )


def test_a_line_that_would_repeat_the_learner_s_words_is_not_shown() -> None:
    line = "Tu as dit non à Lila. Est-ce qu'elle va accepter ça ?"
    assert remembered_hook.problem(line, said=["Je ne partage pas la pizza, tu a menti"]) is None
    assert remembered_hook.problem(line, said=["Bon, tu as dit non à Lila hier"]) == "learner_quote"
    assert remembered_hook.problem("« Je pense que je vais vendre la bouillotte »") == "quote"
    assert remembered_hook.problem("Tu as dit non à {name}.") == "slot"


# -- 3. the day's one hook ------------------------------------------------------------

AUTHORED = {
    "text_fr": "On va aider Lila à l'école.",
    "ref": "tomorrow:g1.2:ecole",
    "source": "pick",
    "kind": "season",
}


def _settle(monkeypatch, case: dict, *, band: str = "A1", authored: dict | None = AUTHORED):
    monkeypatch.setattr(
        engine, "_contract_hook", lambda *a, **k: dict(authored) if authored else None
    )
    monkeypatch.setattr(engine, "_tomorrow_beat", lambda *a, **k: None)
    turn = SimpleNamespace(
        tomorrow_question_fr="",
        resolution_fr="Bon, à demain.",
        reply_fr="D'accord.",
        commitments=[],
        authored_ending=True,
    )
    step = SimpleNamespace(kind="respond", private_task={"turns": _exchanges(case)})
    brief = SimpleNamespace(
        character_id="lila_bonnet",
        story_context={"draft": {"opening_line_fr": case["opening"], "panels": []}},
    )
    journey = SimpleNamespace(local_date=date(2026, 11, 20), steps=[step])
    user = SimpleNamespace(id=1, cefr_estimate=band)
    return engine._hook_after_day(
        None,
        user,
        live={},
        world_after=LILA_WORLD,
        brief=brief,
        turn=turn,
        journey=journey,
        act=None,
        relationships={"lila_bonnet": {"register": "tu"}},
        seed="remember",
    )


def test_flag_off_is_main_s_hook(monkeypatch) -> None:
    teaser, rows = _settle(monkeypatch, PIZZA_NON)
    assert teaser["text_fr"] == AUTHORED["text_fr"]
    assert "remembered" not in teaser and rows[-1]["source"] == "pick"


def test_a_no_decision_day_keeps_the_authored_hook(monkeypatch, on) -> None:
    for case in (OFF_SCRIPT, FACT_QUESTION, MIXED):
        teaser, _rows = _settle(monkeypatch, case)
        assert teaser["text_fr"] == AUTHORED["text_fr"], case
        assert "remembered" not in teaser


def test_a_non_is_remembered_as_the_day_s_one_hook(monkeypatch, on) -> None:
    teaser, rows = _settle(monkeypatch, PIZZA_NON)
    assert teaser["text_fr"].startswith("Tu as dit non à Lila.")
    assert teaser["text_fr"] == teaser["open_fr"] == rows[-1]["text_fr"]
    assert rows[-1]["source"] == "remembered"
    assert teaser["character_id"] == "lila_bonnet"
    assert teaser["remembered"]["authored"]["text_fr"] == AUTHORED["text_fr"]
    # #620: nothing the learner wrote, nothing they did not say.
    for learner, _character in PIZZA_NON["exchanges"]:
        assert learner not in teaser["text_fr"]
    assert "oui" not in teaser["text_fr"] and "promis" not in teaser["text_fr"]


def test_a_tentpole_s_own_a_suivre_stands(on) -> None:
    tentpole = {"text_fr": "À suivre…", "ref": "season:t3", "kind": "season", "source": "tentpole"}
    kept = remembered_hook.remember(
        tentpole,
        opening_line_fr=PIZZA_NON["opening"],
        exchanges=_exchanges(PIZZA_NON),
        ledger=None,
        character_id="lila_bonnet",
        name="Lila",
        band="A1",
        seed="s",
        date="2026-11-20",
    )
    assert kept is tentpole


def test_any_failure_keeps_the_authored_hook(monkeypatch, on) -> None:
    monkeypatch.setattr(remembered_hook, "decision", lambda *a, **k: 1 / 0)
    teaser, _rows = _settle(monkeypatch, PIZZA_NON)
    assert teaser["text_fr"] == AUTHORED["text_fr"]


# -- 4. tomorrow agrees ---------------------------------------------------------------


def test_tomorrow_s_page_and_precedemment_open_on_the_decision(monkeypatch, on) -> None:
    teaser, _rows = _settle(monkeypatch, PIZZA_NON)
    live = {
        "next_teaser": teaser,
        "events": [{"scene_id": "s", "date": "2026-11-20", "summary_fr": "x"}],
    }
    hook = engine.yesterday_hook(live)
    assert hook["text_fr"] == teaser["text_fr"]
    assert hook["learner_decided_fr"] == "Tu as dit non à Lila."
    lines = engine._remembered_previously(
        live, ["La pizza de Lila : elle mange seule.", "Une autre ligne.", "Trois."]
    )
    assert lines[0] == "Tu as dit non à Lila." and len(lines) == engine.PREVIOUSLY_LINES
    monkeypatch.setattr(settings, "STORY_REMEMBERED_HOOK", False)
    assert "learner_decided_fr" not in engine.yesterday_hook(live)
    assert engine._remembered_previously(live, ["a"]) == ["a"]


def test_a_demain_pick_keeps_the_remembered_line(monkeypatch, on) -> None:
    teaser, _rows = _settle(monkeypatch, PIZZA_NON)
    journey = SimpleNamespace(local_date=date(2026, 11, 20))
    assert _remembered_today(teaser, journey)["text_fr"] == teaser["text_fr"]
    assert _remembered_today(teaser, SimpleNamespace(local_date=date(2026, 11, 21))) is None
    assert _remembered_today({"text_fr": "On va cuisiner.", "date": "2026-11-20"}, journey) is None


# -- 5. the evening push --------------------------------------------------------------


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


PARIS_1900 = datetime(2026, 11, 21, 18, 0, tzinfo=UTC)


def _learner(db_session, *, band: str = "A1", practice: bool = True) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"remembered-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        timezone="Europe/Paris",
        reminder_time="08:30",
        cefr_estimate=band,
        is_active=True,
        notifications_enabled=True,
        practice_reminders=practice,
        streak_notifications=True,
    )
    user.grammar_streak_days = 3
    user.grammar_last_review_date = date(2026, 11, 20)
    user.current_streak = 3
    db_session.add(user)
    db_session.add(
        PushSubscription(
            id=uuid.uuid4(),
            user_id=user.id,
            endpoint=f"https://push.test/{uuid.uuid4().hex}",
            keys={"p256dh": "x", "auth": "y"},
        )
    )
    row = remembered_hook.compose(
        {"kind": "refused", "at": 0},
        character_id="lila_bonnet",
        name="Lila",
        band=band,
        seed="push",
        date="2026-11-20",
        authored=AUTHORED,
    )
    db_session.add(
        SerialThread(
            id=uuid.uuid4(),
            user_id=user.id,
            status="active",
            state={"living_story": {"next_teaser": row}},
        )
    )
    db_session.commit()
    return user


def _mine(sent: list[dict], user: User) -> list[dict]:
    return [row for row in sent if row["user_id"] == user.id]


def test_the_evening_push_carries_the_hook_once_in_place_of_the_streak_line(
    db_session, sent, on
) -> None:
    user = _learner(db_session)
    tasks.send_streak_reminders(now=PARIS_1900.isoformat())
    [push] = _mine(sent, user)
    assert push["title"] == "Lila"
    assert (
        push["data"]["kind"] == "remembered_hook" and push["data"]["teaser_source"] == "remembered"
    )
    french, gloss = push["message"].split("\n")
    # Lila and this learner have not moved to «tu» yet: her own line says «vous».
    assert french.startswith("Vous m'avez dit non.") and "jours de suite" not in push["message"]
    assert gloss.startswith("You said no to me.")
    # Once per hook: the next evening (not played) is the streak line again.
    tasks.send_streak_reminders(now=(PARIS_1900 + timedelta(days=1)).isoformat())
    later = _mine(sent, user)
    assert len(later) <= 2 and all(row["data"]["kind"] != "remembered_hook" for row in later[1:])


def test_the_morning_holds_the_remembered_hook_for_the_evening(db_session, sent, on) -> None:
    user = _learner(db_session, band="B1")
    push = copy.daily_journey_morning_push(db_session, user, today=date(2026, 11, 21))
    assert push is not None and push.source == "authored" and "Lila" not in push.message


@pytest.mark.parametrize("flag", [False, True], ids=["flag-off", "practice-reminders-off"])
def test_without_the_flag_or_with_reminders_off_the_streak_line_stands(
    db_session, sent, monkeypatch, flag
) -> None:
    monkeypatch.setattr(settings, "STORY_REMEMBERED_HOOK", flag)
    user = _learner(db_session, practice=not flag)
    tasks.send_streak_reminders(now=PARIS_1900.isoformat())
    [push] = _mine(sent, user)
    assert push["data"]["kind"] == "streak_reminder" and "3 jours de suite" in push["message"]
