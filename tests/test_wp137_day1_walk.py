"""WP-137 — the day-1 walk fixes (backend half).

The 2026-10-06 walk, as a German-speaking A1 learner at phone size:

  C-2  «Sanfter Wiedereinstieg» on the card of a learner still on N° 1. The only
       "practice" was a day opened and stopped ten seconds later, three days
       before. A day stopped before a single step was done is not practice, so
       a learner with no practice history is never returning.
  C-3  «die Wohnung» beside a bare «Schlüssel», and only the day's three words
       on the table, so every item fell to elimination. One article policy per
       item, and at A1 the wrong cards are core words of the band with the
       answer's part of speech.
  C-4  «Le mauvais accueil»: every face grinned, Lila said «Non.» laughing. A
       line can be ``cold`` (the script's and the director's word), which the
       drawn cast plays without a smile; day 1's cold lines say so.
  C-5  Panel 3 of 6 was the bare plate: an authored silence (``silence: true``)
       projects to a panel with no line and no narration. The reader gives it a
       caption and a slow pan (web-frontend); here, the shape it keys on.
"""
from __future__ import annotations

import re
import uuid
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.schemas.daily_journey import JourneyFinishRequest
from app.services import journey_planner as planner
from app.services import living_story as engine
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from app.services.journey_contracts import TargetKind, TargetRef
from app.services.practice_level import core_entry
from app.services.season import runtime as season_runtime
from app.services.season.flags import effective_flags
from app.services.season.format import MOODS, load_season
from app.services.season.page import project, resolve_day
from app.services.streak import local_today, snapshot_fields
from tests.test_daily_journey_state import (  # noqa: F401 - fixture
    create_request,
    drive_to_finish,
    enabled,
    make_user,
)
from tests.test_journey_planner import _brief


def _service(db: Session) -> DailyJourneyService:
    return DailyJourneyService(db, build_default_adapters())


# ---------------------------------------------------------------------------
# C-2 · a learner with no practice history is never «returning»
# ---------------------------------------------------------------------------


def test_c2_a_new_learner_has_no_missed_days(db_session: Session, enabled: None) -> None:  # noqa: F811
    user = make_user(db_session, "wp137-new@example.com", native_language="de")
    today = local_today(user)
    for later in (0, 1, 3, 30):
        assert snapshot_fields(db_session, user.id, today + timedelta(days=later))["missed_days"] == 0


def test_c2_a_day_stopped_before_any_step_is_not_practice(db_session: Session, enabled: None) -> None:  # noqa: F811
    user = make_user(db_session, "wp137-empty-stop@example.com", native_language="de")
    service = _service(db_session)
    created, _ = service.create_journey(user, create_request())
    service.finish(
        user,
        uuid.UUID(created.id),
        JourneyFinishRequest(
            mutation_id=uuid.uuid4().hex,
            expected_revision=created.revision,
            finish_kind="early",
        ),
    )
    db_session.refresh(user)
    assert user.grammar_last_review_date is None, "ten seconds on day 1 is not a practised day"
    assert int(user.grammar_streak_days or 0) == 0
    three_days_on = local_today(user) + timedelta(days=3)
    assert snapshot_fields(db_session, user.id, three_days_on)["missed_days"] == 0


def test_c2_a_finished_day_is_practice_and_an_absence_after_it_counts(
    db_session: Session, enabled: None  # noqa: F811
) -> None:
    user = make_user(db_session, "wp137-real-day@example.com", native_language="de")
    service = _service(db_session)
    created, _ = service.create_journey(user, create_request())
    drive_to_finish(service, user, created, finish_kind="complete")
    db_session.refresh(user)
    practised = user.grammar_last_review_date
    assert practised is not None
    assert snapshot_fields(db_session, user.id, practised + timedelta(days=3))["missed_days"] == 2


# ---------------------------------------------------------------------------
# C-3 · one article policy per item; no closed set at A1
# ---------------------------------------------------------------------------

#: The day-1 words of the walk, glossed as the walk showed them.
DAY_ONE = [
    TargetRef(kind=TargetKind.VOCABULARY, id="11", label_fr="appartement", label_native="die Wohnung"),
    TargetRef(kind=TargetKind.VOCABULARY, id="12", label_fr="clé", label_native="Schlüssel"),
    TargetRef(kind=TargetKind.VOCABULARY, id="13", label_fr="vendre", label_native="verkaufen"),
]
_ARTICLE = re.compile(r"^(le|la|les|un|une|l'|der|die|das|ein|eine|the|a|an)\b", re.IGNORECASE)


def _one_policy(texts: list[str]) -> bool:
    carries = [bool(_ARTICLE.match(text)) for text in texts]
    return all(carries) or not any(carries)


def _pos(text: str) -> str | None:
    return (core_entry(planner.split_article(text)[1]) or {}).get("pos")


@pytest.mark.parametrize("target", DAY_ONE, ids=lambda t: t.label_fr)
def test_c3_listen_and_tap_at_a1_is_not_a_closed_set(target: TargetRef) -> None:
    task = planner.build_listen_tap_task(
        target=target, pool=DAY_ONE, optional=False, control_language="de", band="A1"
    )
    assert task is not None
    texts = [option["text_fr"] for option in task.options]
    assert _one_policy(texts), texts
    others = {planner._bare(word.label_native) for word in DAY_ONE if word is not target}
    assert not {planner._bare(text) for text in texts} & others, f"today's other answers: {texts}"
    correct = next(o["text_fr"] for o in task.options if o["id"] == task.correct_option_id)
    assert planner._bare(correct) == planner._bare(target.label_native)


@pytest.mark.parametrize("label", ["clé", "la clé", "vendre", "appartement"])
def test_c3_a_choice_at_a1_keeps_one_shape_and_one_part_of_speech(label: str) -> None:
    target = TargetRef(kind=TargetKind.VOCABULARY, id="w-" + label, label_fr=label, label_native="x-gloss")
    task = planner.build_recall_task(
        target=target,
        scenario=_brief(control_language="de"),
        affordances=["appartement", "clé", "vendre", "la porte", "le café", "porte", "café"],
        optional=False,
    )
    assert task is not None and task.task_type == "choice"
    texts = [option["text_fr"] for option in task.options]
    assert _one_policy(texts), texts
    assert {_pos(text) for text in texts} == {_pos(label)}, texts
    today = {planner._bare(word.label_fr) for word in DAY_ONE} - {planner._bare(label)}
    assert not {planner._bare(text) for text in texts} & today, texts


def test_c3_the_format_is_still_the_scenes_decision() -> None:
    """A word the scene could not pose as a choice is still typed at A1."""

    target = TargetRef(kind=TargetKind.VOCABULARY, id="v-x", label_fr="parapluie", label_native="Regenschirm")
    task = planner.build_recall_task(
        target=target, scenario=_brief(control_language="de"), affordances=[], optional=False
    )
    assert task is not None and task.task_type == "short_answer"


def test_c3_a_matching_grid_keeps_one_article_policy_per_column() -> None:
    pool = [
        *DAY_ONE,
        TargetRef(kind=TargetKind.VOCABULARY, id="14", label_fr="la porte", label_native="die Tür"),
    ]
    task = planner.build_match_pairs_task(
        target=pool[0], pool=pool, optional=False, control_language="de"
    )
    assert task is not None
    for side in ("fr", "native"):
        texts = [o["text_fr"] for o in task.options if o["side"] == side]
        assert _one_policy(texts), texts


def test_c3_above_a2_the_cards_are_unchanged() -> None:
    task = planner.build_listen_tap_task(
        target=DAY_ONE[2], pool=DAY_ONE, optional=False, control_language="de", band="B1"
    )
    assert task is not None
    texts = {o["text_fr"] for o in task.options}
    assert texts == {"Wohnung", "Schlüssel", "verkaufen"}, "one policy, today's words, as before"


# ---------------------------------------------------------------------------
# C-4 · a cold line is a mood, and day 1's cold lines carry it
# C-5 · an authored silence reaches the reader as a panel with nothing in it
# ---------------------------------------------------------------------------


def _day_one_panels(band: str = "A1", language: str = "de") -> list[dict]:
    season = load_season("s1")
    flags = effective_flags(season, {}, seed="wp137")
    page = resolve_day(season, "t1", "a", flags=flags, band=band, language=language)
    return [
        season_runtime._engine_panel(panel, language=language)
        for panel in project(page)["scene_panels"]
    ]


def test_c4_cold_is_a_mood_the_script_and_the_director_may_write() -> None:
    assert "cold" in MOODS and "cold" in engine.LINE_MOODS
    line = engine.Dialogue.model_validate({"character_id": "lila_bonnet", "text_fr": "Non.", "mood": "cold"})
    assert line.mood == "cold", "the engine keeps the word, it does not fold it to neutral"
    assert "moved or cold" in engine.DIRECTOR, "the director is told it may"


@pytest.mark.parametrize("band", ["A1", "A2", "B1"])
def test_c4_day_one_plays_its_cold_beats_cold(band: str) -> None:
    panels = _day_one_panels(band)
    lines = [(line["character_id"], line["text_fr"], line["mood"]) for panel in panels for line in panel["dialogue"]]
    lila_non = [mood for who, text, mood in lines if who == "lila_bonnet" and text.strip() == "Non."]
    assert lila_non == ["cold"], "«Non.» is dry, not laughing"
    welcome = [line["mood"] for line in panels[3]["dialogue"] if line["character_id"] == "augustin_de_roncourt"]
    assert welcome == ["cold"], "the bow is too deep; the welcome is frosty"
    question = [line["mood"] for line in panels[-1]["dialogue"] if line["character_id"] == "augustin_de_roncourt"]
    assert question == ["cold"], "all charm and no warmth"


def test_c5_the_silent_panel_reaches_the_reader_with_nothing_said() -> None:
    panels = _day_one_panels()
    silent = [panel for panel in panels if not panel["dialogue"] and not panel["narration_fr"].strip()]
    assert len(silent) == 1, "panel 3, the cicada on the zinc, is the day's one authored silence"
    assert panels.index(silent[0]) == 2
