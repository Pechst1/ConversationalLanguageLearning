"""Story plan, Phase 1 «Entschlacken» (15 Oct 2026): the page is written for the reader.

Vincent: «Warum sind die Stories so belanglos und komisch? Auch sehr umständlich oft
geworded?» The paid runs of 7 and 8 Oct showed why: the director wrote for the guards
(three of five frequency-picked words in the dialogue, the day's grammar form twice and a
question built around it, task lines of up to 37 words, an answer floor of 10 to 14
words). What this file pins:

* the director never sees the band's unmet words; ``placed`` is read from the page;
* the grammar form is said once and never asked for; the task line is at most twelve
  words at every band, with no answer floor;
* the frame of a task line («Romy möchte wissen, ob…») is left out of the repeat test;
* the cast's speech samples come at the learner's band only;
* the character closes today's question, and asks for depth from B1;
* on a season day a repeated mistake is corrected in the margin, never in the
  character's line;
* a line the prose detector hears as a machine costs the page one retry, never the day,
  and the reply side is counted only.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.models.user import User
from app.services import journey_content as jc_content
from app.services import journey_conversation as jc
from app.services import living_story as engine
from app.services import story_lanes
from app.services.journey_contracts import CapabilityKey
from app.services.learner_copy import LEARNER_COPY, SUPPORTED_COPY_LANGUAGES
from tests.test_wp36_self_repair import WRONG, record

# ---------------------------------------------------------------------------
# The director's brief
# ---------------------------------------------------------------------------


def test_the_director_asks_for_no_word_list_and_the_form_once():
    assert "mots_a_placer" not in engine.DIRECTOR
    assert "at least twice" not in engine.DIRECTOR
    assert "SAYS it once" in engine.DIRECTOR
    assert "never built so that the answer must use the form" in engine.DIRECTOR
    assert engine.GRAMMAR_MIN_USES == 1


def test_the_director_keeps_captions_out_of_the_learners_turn():
    assert "A caption never" in engine.DIRECTOR and "attend ta réponse" in engine.DIRECTOR
    assert "never a\ncaption about it" in engine.DIRECTOR
    assert "they talk to EACH OTHER" not in engine.DIRECTOR
    assert "Never fill a panel with small talk" in engine.DIRECTOR


def test_the_director_asks_for_a_task_of_twelve_words_and_an_answer_a_person_would_give():
    assert "at most 12 words" in engine.DIRECTOR
    assert "22 words" not in engine.DIRECTOR
    assert "as long as a person would say it" in engine.DIRECTOR
    assert all(words == 12 for _separators, words in engine._OBJECTIVE_LIMITS.values())
    assert not hasattr(engine, "_ANSWER_MINIMUM_WORDS")


def test_a_short_answer_never_costs_a_draft():
    """The season bible's own C1 answers have a median of nine words («Ce soir. Autant ne
    pas attendre.»)."""

    for level in ("B1", "B2", "C1"):
        engine._check_objective_scope("Tell Romy when you will call your mother.", level)


def test_the_payload_and_the_stored_context_never_carry_the_unmet_words():
    context = {"level": "A1", engine.MOTS_KEY: ["clé", "poche"]}
    assert engine.MOTS_KEY not in engine._prompt_payload(context)
    assert engine.MOTS_KEY not in engine._storable_context(context)


def test_placed_is_read_from_the_finished_page():
    from tests import test_living_story as story

    draft = engine.SceneDraft.model_validate(story.draft(story._scene_context(), 0))
    draft.panels[1].dialogue[0].text_fr = "Tu as vu la clé ? Elle était dans ta poche."
    outcome = engine.word_outcome(draft, {engine.MOTS_KEY: ["sac", "clé", "poche", "chaise"]})
    assert outcome["placed"] == ["clé", "poche"]
    assert "offered" not in outcome, "nothing is offered to the director any more"


# ---------------------------------------------------------------------------
# Repeats: what is asked, not who asks it
# ---------------------------------------------------------------------------


def test_the_frame_of_a_task_line_is_not_a_repeat():
    names = {"Romy", "Lila"}
    assert engine._premise_overlap("Romy möchte wissen, ob du bleibst.", "Romy möchte wissen, was du denkst.") >= 0.6
    assert engine._task_overlap("Romy möchte wissen, ob du bleibst.", "Romy möchte wissen, was du denkst.", names) < 0.6
    assert engine._task_overlap(
        "Explique à Romy pourquoi tu restes.", "Explique à Lila pourquoi tu restes.", names
    ) == 1.0, "the same question to someone else is still the same question"


# ---------------------------------------------------------------------------
# The cast speaks at the learner's band
# ---------------------------------------------------------------------------


def _season_cast() -> dict[str, str]:
    world = json.loads(Path("app/data/season/s1/world.json").read_text(encoding="utf-8"))
    return {member["id"]: member["speech_pattern"] for member in world["cast"]}


@pytest.mark.parametrize(
    ("level", "kept", "dropped"),
    [
        ("A1", "«Mais arrête. C'est évident.»", "«Je déteste avoir raison la nuit.»"),
        ("A2", "«Mais arrête. C'est évident.»", "«Je déteste avoir raison la nuit.»"),
        ("B1", "«Je déteste avoir raison la nuit.»", "«Mais arrête. C'est évident.»"),
        ("C1", "«Je déteste avoir raison la nuit.»", "«Mais arrête. C'est évident.»"),
    ],
)
def test_the_speech_samples_are_the_learners_band_only(level, kept, dropped):
    lila = engine.speech_at_level(_season_cast()["lila_bonnet"], level)
    assert kept in lila and dropped not in lila
    assert "A2:" not in lila and "B1:" not in lila
    assert "Says «la lumière est fausse»" in lila, "a note outside the samples is kept"


def test_the_director_context_carries_the_banded_cast():
    cast = [{"id": "lila_bonnet", "speech_pattern": _season_cast()["lila_bonnet"]}]
    assert "«Mais arrête" not in engine._cast_for_level(cast, "B2")[0]["speech_pattern"]
    assert "«Mais arrête" in engine._cast_for_level(cast, "A1")[0]["speech_pattern"]
    plain = [{"id": "x", "speech_pattern": "Short exact sentences, formal vous."}]
    assert engine._cast_for_level(plain, "B1") == plain


# ---------------------------------------------------------------------------
# The answer lanes: today's question closes today
# ---------------------------------------------------------------------------


def test_the_character_draws_their_own_conclusion_and_never_defers_the_question():
    assert "draw your own conclusion" in story_lanes.VOICE
    assert "Pas de nom, alors." in story_lanes.VOICE and "Pas de nom, alors." in story_lanes.STORY
    assert "on verra demain" in story_lanes.STORY and "story.carries_over" in story_lanes.STORY


def test_from_b1_a_short_answer_gets_a_real_follow_up():
    assert "From B1, when the learner answered in a few" in story_lanes.VOICE
    assert "«Pourquoi ?»" in story_lanes.VOICE


def test_the_story_lane_is_told_nothing_carries_over():
    payload = {"story": {"level": "B1"}, "learner_text": "Non."}
    lane = story_lanes.story_payload(payload, {"reply_fr": "Pas de nom, alors."})
    assert lane["story"]["carries_over"] is False
    assert lane["story"]["level"] == "B1" and lane["released"] == {"reply_fr": "Pas de nom, alors."}
    assert "carries_over" not in payload["story"], "the caller's payload is not changed"


# ---------------------------------------------------------------------------
# A season day corrects in the margin
# ---------------------------------------------------------------------------


def _learner(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@phase1.test",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _decision(db_session, user, brief, *, turn_index=0):
    return jc.feedback_decision(
        db_session,
        user=user,
        scenario=brief,
        task=brief.response_task,
        text="Je voudrais une café.",
        turn_index=turn_index,
        history=None,
    )


def test_a_season_day_corrects_a_repeated_mistake_in_the_margin(db_session):
    user = _learner(db_session)
    record(db_session, user)
    plain = jc_content.resolve_scenario_brief(db_session, user=user, scenario_key=CapabilityKey.ORDER_AT_CAFE)
    assert _decision(db_session, user, plain).prompt is not None, "elsewhere the character asks"

    season = replace(plain, story_context={**(plain.story_context or {}), "season": {"kind": "gap"}})
    decision = _decision(db_session, user, season)
    assert decision.prompt is None and decision.elicitation_fr is None, "nothing in the line"
    assert decision.reason == "recurrence_in_margin"
    assert decision.explicit is not None and decision.explicit.span_fr == WRONG
    assert decision.explicit.corrected_fr == "un café"
    assert decision.explicit.note_native.startswith("It is “un café”, not “une café”.")
    assert "asked" not in decision.explicit.note_native
    # A margin note asks nothing, so it is not bounded by the turns left.
    last = _decision(db_session, user, season, turn_index=season.response_task.max_turns)
    assert last.explicit is not None and last.prompt is None


def test_the_margin_note_is_written_in_three_languages():
    row = LEARNER_COPY["self_repair.margin_note"]
    assert set(row) == set(SUPPORTED_COPY_LANGUAGES)
    for language, template in row.items():
        assert "{correct}" in template and "{wrong}" in template, language


# ---------------------------------------------------------------------------
# «Maßstab»: the detector on every generated page
# ---------------------------------------------------------------------------


def test_a_machine_line_costs_the_page_one_retry_never_the_day():
    from tests import test_living_story as story

    context = story._scene_context()
    draft = engine.SceneDraft.model_validate(story.draft(context, 0))
    assert engine.prose_gap(draft, context) is None, "the fixture's page reads like people"
    draft.panels[-1].narration_fr = "Tout le monde attend ta réponse."
    with pytest.raises(engine.SoftRejection) as caught:
        engine._check_reading_aids(draft, context)
    assert str(caught.value) == "machine_prose"
    assert "'Tout le monde attend ta réponse.'" in caught.value.hint
    assert caught.value.proposal is draft, "the page is servable as it stands"


def test_a_broken_detector_never_refuses_a_page(monkeypatch):
    from app.services.season import prose_detector
    from tests import test_living_story as story

    def broken(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(prose_detector, "page_hits", broken)
    context = story._scene_context()
    draft = engine.SceneDraft.model_validate(story.draft(context, 0))
    draft.panels[-1].narration_fr = "Tout le monde attend ta réponse."
    assert engine.prose_gap(draft, context) is None


def test_the_cast_s_refrains_may_come_back_on_one_page():
    season_day = {engine.SEASON_TODAY_KEY: SimpleNamespace(season=SimpleNamespace(id="s1"))}
    assert "J'ai rien entendu." in engine._signature_phrases(season_day)
    assert engine._signature_phrases({}), "a life without a season reads the serial bible's"


def test_the_reply_side_is_counted_never_refused():
    turn = SimpleNamespace(reply_fr="D'accord.", resolution_fr="Elle sourit. On verra demain.")
    assert story_lanes.reply_prose_counts(turn) == {"prose_hits": {"deferred_ending": 1}}
    plain = SimpleNamespace(reply_fr="D'accord.", resolution_fr="Elle range la clé dans sa poche.")
    assert story_lanes.reply_prose_counts(plain) == {}
    assert story_lanes.reply_prose_counts(None) == {}
