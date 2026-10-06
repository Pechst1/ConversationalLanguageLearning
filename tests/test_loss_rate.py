"""LOSS-RATE 2026-10-06: fewer lost generated days, with every guard as it was.

The WP-133a/b live reads lost 31 of 77 generated-day attempts. 23 of 36 first gap
days after a tentpole were lost against 8 of 41 days inside a gap: the director was
told the season brief «outranks» chapter shapes, was never told the tentpole had
closed the chapter, and continued it (``wrong_beat``) or reused its question
(``chapter_not_advanced``). These tests pin the fixes (docs/implementation/atelier-v2/
LOSS-RATE-2026-10-06.md): the brief states what each guard checks, the retry hints say
what to change, no-story shape slips are read tolerantly, a truncated page is retried
with room, ``jump_to_day`` seeds a real learner's state, and every refusal can be
recorded by the next paid read. Each guard still refuses what it refused.
"""

from __future__ import annotations

import json
import time
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.services import living_story as engine
from app.services.season.director import SeasonChecklist
from app.services.season.format import load_season
from tests import test_journey_end_to_end as support
from tests import test_season_one as season_suite
from tests.test_living_story import _scene_context, draft

assembled_client = season_suite.assembled_client
clock = season_suite.clock
journey_enabled = season_suite.journey_enabled
season_on = season_suite.season_on


# ---------------------------------------------------------------------------
# brief.page_rules: the brief states what the guards check
# ---------------------------------------------------------------------------


def _today(flags: dict | None = None):
    return SimpleNamespace(season=load_season("s1"), flags=dict(flags or {}), band="B1")


SEASON_CAST = [
    {"id": member_id}
    for member_id in (
        "lila_bonnet", "marin_leveque", "augustin_de_roncourt", "margaux_barman", "romy_tremblay",
        "landlord_marchand", "camille_marchand", "mme_diallo", "maitre_vasseur", "bastien_roux",
    )
]


def _rules(chapter, *, shape="standard", level="B1", flags=None, recent=None, resolved=None):
    return engine.season_page_rules(
        _today(flags),
        chapter=chapter,
        shape=shape,
        level=level,
        cast=SEASON_CAST,
        resolved_questions=list(resolved or []),
        recent=list(recent or []),
    )["page_rules"]


def test_after_a_tentpole_the_brief_says_a_new_chapter_opens_and_names_the_retired_question():
    season_question = load_season("s1").question.text("B1")
    closed = {"title_fr": "La photographie", "dramatic_question": season_question, "resolved": True, "scene_count": 2}
    rules = _rules(closed)
    assert rules["chapter"]["open_new"] is True and rules["chapter"]["beat"] == "setup"
    assert season_question[:140] in rules["chapter"]["retired_questions"]
    assert "never the season's question" in rules["chapter"]["rule"]
    assert "refused" in rules["checked"]


def test_inside_a_gap_the_brief_says_which_beat_and_to_keep_the_question():
    chapter = {"title_fr": "La clé", "dramatic_question": "Qui garde la clé ?", "scene_count": 1, "shape": "standard"}
    rules = _rules(chapter)
    assert rules["chapter"]["open_new"] is False and rules["chapter"]["beat"] == "complication"
    assert "verbatim" in rules["chapter"]["rule"] and "«La clé»" in rules["chapter"]["rule"]
    last = {**chapter, "scene_count": 3}
    recent = [{"chapter_title_fr": "La clé", "objective_native": "Dis à Romy si tu acceptes, et pourquoi."}]
    rules = _rules(last, recent=recent)
    assert rules["chapter"]["beat"] == "resolution"
    assert rules["chapter"]["already_asked"] == ["Dis à Romy si tu acceptes, et pourquoi."]
    assert f"{int(engine.RESOLUTION_OVERLAP * 100)} %" in rules["chapter"]["resolution"]


def test_the_brief_names_who_may_speak_and_a_two_hander_has_one_voice():
    rules = _rules(None)
    assert "odile" not in rules["voices"]["speakers"] and "clerk" not in rules["voices"]["speakers"]
    assert "never has a dialogue line" in rules["voices"]["rule"]
    two = _rules({"title_fr": "x", "dramatic_question": "y", "scene_count": 1, "shape": "two_hander"}, shape="two_hander")
    assert "ONLY character_id has dialogue lines" in two["voices"]["rule"]


def test_the_registers_in_the_brief_are_todays_not_the_seasons_first():
    assert _rules(None)["address"]["registers"]["augustin_de_roncourt"] == "vous"
    after_t3 = _rules(None, flags={"register.augustin_de_roncourt": "tu"})
    assert after_t3["address"]["registers"]["augustin_de_roncourt"] == "tu"
    assert "odile" not in after_t3["address"]["registers"]


@pytest.mark.parametrize("level", ["B1", "B2", "C1"])
def test_the_brief_states_the_objective_floor_the_guard_holds(level):
    floor = engine._OBJECTIVE_MINIMUM_WORDS[level]
    assert f"at least {floor} words" in _rules(None, level=level)["objective"]


def test_the_brief_states_the_one_act_limit_at_a1():
    assert "ONE act" in _rules(None, level="A1")["objective"]
    assert "at most 16 words" in _rules(None, level="A1")["objective"]


def test_the_director_is_told_the_chapter_bookkeeping_still_holds_on_a_season_day():
    assert "brief.page_rules" in engine.DIRECTOR
    assert "(chapter shapes, arcs, secrets, callbacks)" not in engine.DIRECTOR
    assert "after a tentpole it always does: beat setup" in engine.DIRECTOR


def test_the_director_reads_page_rules_on_the_first_gap_day(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    email = f"loss-rate-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=1)
    db_session.commit()
    for _ in range(2):  # T1 A and B
        d.create()
        d.play(answer="Je reste encore un peu.")
        assert d.finish("complete").status_code == 200
        clock.advance(days=1)
    d.create()
    drafts = [source for schema, source in season_on.calls if schema == "SceneDraft"]
    assert drafts, "g1.1 is a generated day"
    rules = drafts[-1]["season_script"]["brief"]["page_rules"]
    assert rules["chapter"]["open_new"] is True and rules["chapter"]["beat"] == "setup"
    # The tentpole's chapter asked the season's question; it is retired.
    assert any("grand-mère" in question for question in rules["chapter"]["retired_questions"])


# ---------------------------------------------------------------------------
# The chapter shape a closed chapter no longer imposes
# ---------------------------------------------------------------------------


def _two_voice_draft(context, n=0):
    value = draft(context, n)
    value["panels"][0]["dialogue"] = [{"character_id": "lila_bonnet", "text_fr": "Il pleut encore."}]
    return engine.SceneDraft.model_validate(value)


def test_a_closed_two_hander_does_not_bind_the_next_chapters_setup():
    closed = {"title_fr": "Deux", "dramatic_question": "Qui parle ?", "resolved": True, "shape": "two_hander"}
    context = _scene_context(chapter=closed, chapter_shape={"shape": "standard"})
    engine._validate_scene(_two_voice_draft(context), context)


def test_an_open_two_hander_still_refuses_a_third_voice():
    open_chapter = {
        "title_fr": "Deux", "dramatic_question": "Qui parle ?", "scene_count": 1, "shape": "two_hander",
        "possible_developments": ["a", "b"],
    }
    context = _scene_context(chapter=open_chapter, chapter_shape={"shape": "two_hander"})
    proposal = _two_voice_draft(context)
    proposal.beat = "turn"
    with pytest.raises(engine.StoryUnavailable, match="two_hander_crowded"):
        engine._validate_scene(proposal, context)


# ---------------------------------------------------------------------------
# The retry hints say what to change
# ---------------------------------------------------------------------------


def test_wrong_beat_after_a_closed_chapter_says_a_new_chapter_opens():
    closed = {"title_fr": "La photographie", "dramatic_question": "Q ?", "resolved": True, "scene_count": 2}
    context = _scene_context(chapter=closed)
    proposal = engine.SceneDraft.model_validate({**draft(context, 0), "beat": "complication"})
    with pytest.raises(engine.StoryUnavailable, match="wrong_beat") as caught:
        engine._validate_scene(proposal, context)
    assert "OPENS a new chapter" in caught.value.hint and "«La photographie»" in caught.value.hint
    assert "scene 3" not in caught.value.hint


def test_wrong_beat_inside_a_chapter_names_its_own_beat_count():
    chapter = {
        "title_fr": "Ensemble", "dramatic_question": "Q ?", "scene_count": 1, "shape": "ensemble",
        "possible_developments": ["a", "b"],
    }
    context = _scene_context(chapter=chapter, chapter_shape={"shape": "ensemble"})
    value = draft(context, 0)
    proposal = engine.SceneDraft.model_validate({**value, "beat": "turn"})
    with pytest.raises(engine.StoryUnavailable, match="wrong_beat") as caught:
        engine._validate_scene(proposal, context)
    assert "5-beat chapter" in caught.value.hint and "complication" in caught.value.hint


def test_chapter_not_advanced_names_the_question_it_repeats():
    question = "Ta grand-mère t'a laissé ce qu'il y a au-dessus du Mistral : tu le gardes ?"
    closed = {"title_fr": "T", "dramatic_question": question, "resolved": True}
    context = _scene_context(chapter=closed)
    value = draft(context, 0)
    value["chapter"] = {**value["chapter"], "dramatic_question": question}
    with pytest.raises(engine.StoryUnavailable, match="chapter_not_advanced") as caught:
        engine._validate_scene(engine.SceneDraft.model_validate(value), context)
    assert "Set beat to setup" in caught.value.hint and "repeats «" in caught.value.hint


def test_resolution_repeats_turn_lists_the_shared_words():
    chapter = {
        "title_fr": "Une exposition 0", "dramatic_question": "Q ?", "scene_count": 3, "shape": "standard",
        "possible_developments": ["a", "b"],
    }
    value = draft(_scene_context(), 0)
    recent = [{"chapter_title_fr": "Une exposition 0", "objective_native": value["objective_native"], "novelty_key": "x"}]
    context = _scene_context(chapter=chapter, recent_situations=recent)
    value["chapter"] = {"title_fr": "Une exposition 0", "dramatic_question": "Q ?", "possible_developments": ["a", "b"]}
    proposal = engine.SceneDraft.model_validate({**value, "beat": "resolution"})
    with pytest.raises(engine.StoryUnavailable, match="resolution_repeats_turn") as caught:
        engine._validate_scene(proposal, context)
    assert "shares these words with it: [" in caught.value.hint


def test_unknown_panel_character_says_the_learner_never_has_a_line():
    context = _scene_context()
    value = draft(context, 0)
    value["panels"][1]["dialogue"].append({"character_id": "learner", "text_fr": "Oui."})
    with pytest.raises(engine.StoryUnavailable, match="unknown_panel_character") as caught:
        engine._validate_scene(engine.SceneDraft.model_validate(value), context)
    assert "learner never has a dialogue line" in caught.value.hint


# ---------------------------------------------------------------------------
# Tolerant shape, strict story
# ---------------------------------------------------------------------------


def _raw(**over):
    value = draft(_scene_context(), 0)
    value.update(over)
    return value


def test_no_story_slips_are_repaired_and_noted():
    value = _raw(
        beat=" Setup ",
        secret_shift="none",
        thread_shift="open",
        capability_key="make_a_wish",
        learner_turn="Je reste.",
        lexicon=[{"surface_fr": "affiche", "lemma": "affiche", "gloss_native": "poster " * 40}] * 12,
        source_event_ids=[f"e{i}" for i in range(10)],
    )
    value["panels"][0]["visual_direction"] = "A long shot. " * 60
    value["panels"][0]["shot"] = "wide"
    value["panels"][1]["dialogue"][0]["to"] = "learner"
    value["chapter"]["possible_developments"] = ["a", "b", "c", "d", "e", "f", "g"]
    repaired, notes = engine.tolerant_scene_json(value)
    scene = engine.SceneDraft.model_validate(repaired)
    assert scene.beat == "setup" and scene.secret_shift is None and scene.thread_shift is None
    assert scene.capability_key is None and len(scene.lexicon) == 10 and len(scene.source_event_ids) == 8
    assert len(scene.panels[0].visual_direction) <= engine.VISUAL_DIRECTION_CHARS
    assert len(scene.chapter.possible_developments) == 5
    assert any("learner_turn" in note for note in notes) and any("shot" in note for note in notes)


def test_learner_facing_overflow_and_a_made_up_beat_still_fail():
    for value in (_raw(premise_fr="x " * 400), _raw(beat="aftermath")):
        repaired, _ = engine.tolerant_scene_json(value)
        with pytest.raises(ValidationError):
            engine.SceneDraft.model_validate(repaired)


def test_the_directors_checklist_is_cut_not_refused():
    checklist = SeasonChecklist.model_validate(
        {"premise_id": "none", "threads": [f"t{i}" for i in range(7)], "change_after": "mot " * 100, "hook_fr": None}
    )
    assert checklist.premise_id is None and len(checklist.threads) == 4
    assert len(checklist.change_after) <= 240 and checklist.hook_fr == ""


class _NoEvents:
    def __init__(self, *args, **kwargs):
        pass

    def record(self, *args, **kwargs):
        return None


def _no_events(monkeypatch):
    monkeypatch.setattr("app.services.pilot_events.PilotEventService", _NoEvents)


class _Provider:
    def __init__(self, contents, finish="stop"):
        self.contents = list(contents)
        self.finish = finish
        self.kwargs: list[dict] = []

    def generate_chat_completion(self, messages, **kwargs):
        self.kwargs.append(kwargs)
        content = self.contents.pop(0)
        return SimpleNamespace(
            content=content, model="fake", provider="test", total_tokens=10, cost=0.0,
            raw_response={
                "choices": [{"finish_reason": self.finish if self.contents else "stop"}],
                "usage": {"completion_tokens": 5000, "completion_tokens_details": {"reasoning_tokens": 3100}},
            },
        )


def test_a_cut_off_page_is_named_truncated_with_an_excerpt(monkeypatch):
    whole = json.dumps(draft(_scene_context(), 0))
    fake = _Provider([whole[: len(whole) // 2], whole], finish="length")
    monkeypatch.setattr(engine, "_client", lambda: fake)
    with pytest.raises(engine.ParsedOutputError, match="invalid_story_output") as caught:
        engine._json_call(engine.DIRECTOR, {"data": 1}, engine.SceneDraft, deadline=time.monotonic() + 60)
    details = caught.value.details
    assert details["truncated"] is True and details["finish_reason"] == "length"
    assert details["reasoning_tokens"] == 3100 and details["excerpt"]
    assert "cut off" in caught.value.hint


def test_the_retry_after_a_cut_off_page_gets_room_to_finish(monkeypatch):
    whole = json.dumps(draft(_scene_context(), 0))
    fake = _Provider([whole[:900], whole], finish="length")
    monkeypatch.setattr(engine, "_client", lambda: fake)
    monkeypatch.setattr(engine, "CRITIC_ENABLED", False)
    monkeypatch.setattr(engine, "_record_cost", lambda *a, **k: None)
    _no_events(monkeypatch)
    proposal, _ = engine._approved(
        engine.DIRECTOR, {}, engine.SceneDraft, lambda p: None, db=None, user=SimpleNamespace(id=uuid.uuid4())
    )
    assert proposal.title_fr
    assert "max_tokens" in fake.kwargs[0] and fake.kwargs[0]["max_tokens"] == 5000
    assert fake.kwargs[1]["max_tokens"] == engine.TRUNCATED_RETRY_TOKENS


def test_a_shape_error_that_is_not_truncation_keeps_the_default_budget():
    error = engine.ParsedOutputError("invalid_story_output", details={"truncated": False})
    assert engine._next_budget(error, None) is None
    assert engine._next_budget(engine.StoryUnavailable("wrong_beat"), None) is None


# ---------------------------------------------------------------------------
# Every refusal can be recorded
# ---------------------------------------------------------------------------


def test_every_refused_draft_reaches_the_observers_with_its_claims(monkeypatch):
    records: list[dict] = []
    monkeypatch.setattr(engine, "REFUSAL_OBSERVERS", [records.append])
    monkeypatch.setattr(engine, "CRITIC_ENABLED", False)
    monkeypatch.setattr(engine, "_record_cost", lambda *a, **k: None)
    _no_events(monkeypatch)
    closed = {"title_fr": "T1", "dramatic_question": "Q ?", "resolved": True}
    context = _scene_context(chapter=closed)
    drafts = [engine.SceneDraft.model_validate({**draft(context, 0), "beat": "turn"}), engine.SceneDraft.model_validate(draft(context, 1))]
    monkeypatch.setattr(engine, "_json_call", lambda *a, **k: (drafts.pop(0), {}))
    engine._approved(
        engine.DIRECTOR, {}, engine.SceneDraft, lambda p: engine._validate_scene(p, context),
        db=None, user=SimpleNamespace(id=uuid.uuid4()), digest=lambda p: engine.scene_digest(p, context),
    )
    assert len(records) == 1
    record = records[0]
    assert record["reason"] == "wrong_beat" and "OPENS a new chapter" in record["hint"]
    assert record["draft"]["beat"] == "turn" and record["draft"]["required_beat"] == ["setup"]
    assert record["draft"]["chapter_closed"] is True and record["draft"]["open_question"] == "Q ?"


# ---------------------------------------------------------------------------
# jump_to_day: the state a real learner has on that day
# ---------------------------------------------------------------------------


def _jumped(assembled_client, db_session, day: int, cefr: str = "B2.1"):
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    email = f"loss-jump-{uuid.uuid4()}@example.com"
    support.register(assembled_client, email, cefr=cefr)
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=day)
    db_session.commit()
    thread = season_suite._thread(db_session, user.id)
    return user, dict(thread.state or {})


def test_a_jump_past_t6_carries_the_flags_the_tentpoles_set(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    _, state = _jumped(assembled_client, db_session, 51)
    flags = state[engine.STATE_KEY]["season_script"]["flags"]
    assert flags.get("s1.plan") == "lease" and flags.get("s1.went_with_lila_to_marin") is True


def test_a_jump_stages_the_moments_of_every_gap_it_passes(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    _, state = _jumped(assembled_client, db_session, 25)
    staged = {(row["gap"], row["premise"]) for row in state[engine.STATE_KEY]["season_script"]["premises"]}
    season = load_season("s1")
    for gap_id in ("g1", "g2", "g3"):
        for need in season.gaps[gap_id].required:
            assert (gap_id, need.premise) in staged
    # Gus says «tu» after T3, in the relationships the director reads.
    assert state["relationships"]["augustin_de_roncourt"]["register"] == "tu"


def test_a_jump_into_a_gap_leaves_that_gaps_moments_owed(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    _, state = _jumped(assembled_client, db_session, 14)
    staged = {row["gap"] for row in state[engine.STATE_KEY]["season_script"].get("premises") or []}
    assert "g2" not in staged and "g1" in staged
