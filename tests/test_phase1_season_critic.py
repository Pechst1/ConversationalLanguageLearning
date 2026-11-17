"""Phase 1 «Entschlacken»: the season's story critic reads the page like a reader.

Three rubric items join WP-114's. ``reads_like_people`` and ``one_plain_question``
refuse a page, and a refusal for them alone is storytelling: the retry is bought and a
second refusal is still served and logged. ``moves_on`` compares the day with the
learner's last three (``recent_days``) and is scored and stored, not yet refused for.
Pure functions and a stubbed critic call: no model, no database.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services import living_story as engine
from app.services.season.canon_guards import CORRECTNESS, STORYTELLING, issue_class, review_class
from app.services.season.director import (
    RECENT_DAY_KEYS,
    STORY_CRITIC,
    StoryReview,
    critic_payload,
    review_verdict,
)

#: A page WP-114's rubric accepts.
GOOD = StoryReview(meaningful_change=True)

#: Five days the learner read, as ``context["recent_situations"]`` holds them.
RECENT = [
    {
        "novelty_key": f"season-{n}",
        "premise_fr": f"Margaux essuie un verre déjà sec ({n}).",
        "objective_native": f"Tell Margaux what you want ({n}).",
        "character_id": "margaux_barman",
        "location_id": "le_mistral",
        "causal_reason": "Follows the gap's thread.",
        "beat": "setup",
        "problem_key": f"order-{n}",
        "chapter_title_fr": "La première semaine",
    }
    for n in range(1, 6)
]

CONTRADICTS = "The task contradicts the lead's question: make both ask the same plain thing."


def _plain(text: str) -> str:
    return " ".join(text.split())


def _seen(rows: list[dict]) -> list[dict]:
    return [
        {key: row[key] for key in ("location_id", "character_id", "premise_fr", "objective_native")}
        for row in rows
    ]


def test_a_reply_without_the_new_items_never_refuses_a_page():
    review = StoryReview.model_validate({"meaningful_change": True, "in_character": True})
    assert review.reads_like_people and review.one_plain_question and review.moves_on
    assert review_verdict(review)


def test_the_verdict_refuses_lines_that_are_not_people_and_a_question_that_is_not_plain():
    assert review_verdict(GOOD)
    assert not review_verdict(GOOD.model_copy(update={"reads_like_people": False}))
    assert not review_verdict(GOOD.model_copy(update={"one_plain_question": False}))
    # Scored and stored, never refused for in this phase.
    assert review_verdict(GOOD.model_copy(update={"moves_on": False}))


def test_the_critic_is_told_the_rule_the_verdict_applies():
    prompt = _plain(STORY_CRITIC)
    assert (
        "accepted is true only when meaningful_change, in_character, honours_choices, obstacle_faced, "
        "reads_like_people, one_plain_question and remembers are true and spoils_next_tentpole is false."
    ) in prompt
    for item in ("reads_like_people", "one_plain_question", "moves_on", "remembers"):
        assert f"- {item}:" in prompt, item
    assert "at most 12 words" in prompt.split("- one_plain_question:")[1].split("- moves_on:")[0]
    assert "recent_days" in prompt.split("- moves_on:")[1].split("The page is not the whole day")[0]
    # WP-149 stays: the learner's reply never appears on the page, and the change is
    # judged on the page plus the planned exchange.
    assert "Never ask for the learner's reply, words or decision to appear on the page" in prompt
    assert "Judge meaningful_change and value_turn on the page PLUS that planned exchange" in prompt


def test_the_critic_reads_the_last_three_days_as_a_reader_knows_them():
    payload = critic_payload(
        {"today": {}}, {"title_fr": "La même chose ?"}, recent_days=[*RECENT, "not a day"]
    )
    assert payload["recent_days"] == _seen(RECENT[-3:])
    assert RECENT_DAY_KEYS == ("location_id", "character_id", "premise_fr", "objective_native")
    assert critic_payload({"today": {}}, {"title_fr": "La même chose ?"})["recent_days"] == []


def test_a_refusal_for_the_reader_items_alone_is_storytelling():
    assert issue_class(CONTRADICTS) == CORRECTNESS, "the word alone reads as a canon defect"
    unplain = GOOD.model_copy(update={"one_plain_question": False, "issues": [CONTRADICTS]})
    assert not review_verdict(unplain) and review_class(unplain) == STORYTELLING
    waiting = GOOD.model_copy(
        update={
            "reads_like_people": False,
            "issues": ["Cut the caption «Tout le monde attend ta réponse»."],
        }
    )
    assert not review_verdict(waiting) and review_class(waiting) == STORYTELLING
    # moves_on refuses nothing yet; read as a refusal, it would be storytelling too.
    rerun = GOOD.model_copy(update={"moves_on": False, "issues": [CONTRADICTS]})
    assert review_verdict(rerun) and review_class(rerun) == STORYTELLING
    # With any other failed item, WP-149's classification holds.
    assert review_class(unplain.model_copy(update={"honours_choices": False})) == CORRECTNESS
    assert review_class(unplain.model_copy(update={"spoils_next_tentpole": True})) == CORRECTNESS
    gus = unplain.model_copy(
        update={
            "in_character": False,
            "issues": ["Make Gus use 'vous' (he still uses 'vous' until T3)."],
        }
    )
    assert review_class(gus) == CORRECTNESS
    flat = waiting.model_copy(
        update={"meaningful_change": False, "issues": ["Nothing changes by the end of the day."]}
    )
    assert review_class(flat) == STORYTELLING


def test_the_season_critic_reads_the_last_three_days_and_serves_a_second_reader_refusal(
    monkeypatch,
):
    sent: list[dict] = []
    answer = {
        "review": GOOD.model_copy(
            update={"one_plain_question": False, "moves_on": False, "issues": [CONTRADICTS]}
        )
    }

    def critic(system, payload, schema, record, **kwargs):
        sent.append(payload)
        return answer["review"], None

    monkeypatch.setattr(engine, "STORY_CRITIC_ENABLED", True)
    monkeypatch.setattr(engine, "_json_call", critic)
    reviews: list[dict] = []
    review = engine._season_story_review(
        {"season_script": {"brief": {"today": {}}}, "recent_situations": RECENT}, reviews
    )
    page = SimpleNamespace(
        title_fr="La même chose ?", model_dump=lambda **_: {"title_fr": "La même chose ?"}
    )

    assert review(page, deadline=0.0, record=lambda entry: None) == {
        "accepted": False,
        "issues": [CONTRADICTS],
        "class": STORYTELLING,
    }
    assert review(page, deadline=0.0, record=lambda entry: None, final=True)["accepted"] is True, (
        "a second storytelling refusal is served"
    )
    assert [row["class"] for row in reviews] == [STORYTELLING, STORYTELLING]
    assert reviews[-1]["override"] is True and reviews[-1]["accepted"] is False
    assert reviews[-1]["one_plain_question"] is False and reviews[-1]["moves_on"] is False, (
        "scored and stored"
    )
    assert sent[0]["recent_days"] == _seen(RECENT[-3:])

    # A day that only stages a recent day again is still accepted.
    answer["review"] = GOOD.model_copy(update={"moves_on": False})
    assert review(page, deadline=0.0, record=lambda entry: None) == {
        "accepted": True,
        "issues": [],
        "class": None,
    }
    assert reviews[-1]["moves_on"] is False
