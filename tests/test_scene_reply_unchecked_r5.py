"""Check walk 19 Nov (B1, day 2): a scene reply that was never corrected.

«Je ne sais pas encore. Hier j'ai allé chez le notaire …» stayed «Réponse enregistrée,
pas encore vérifiée. Elle ne compte pas encore.» for good. The walk's database stored the
turn with ``correction: null`` and ``check_failure: "StoryUnavailable:
story_provider_failed"``; the server log shows the season page's tutor lane
(``margin_correction``) getting one OpenAI 500 on its only attempt
(``story_lanes: no margin correction on the season page``, then
``verdict_check_failed surface=scene failure=provider_error``). Nothing reads a scene
reply later (``verdict_settle.SETTLERS`` has no scene surface), so «not yet» was final.

The fake provider here is ``living_story._json_call``: the tutor lane's only model call.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.services.living_story as engine
import app.services.story_lanes as lanes
from app.services.daily_journey import _public_thread

LEARNER = "Je ne sais pas encore. Hier j'ai allé chez le notaire et je pense que ce n'est pas plus simple pour tout le monde."

ALLER = lanes.TutorCorrection(
    span_fr="j'ai allé",
    corrected_fr="je suis allé",
    note_native="Aller forms its passé composé with être, not avoir.",
)


def _verdict(**overrides) -> lanes.TutorVerdict:
    fields = {"outcome": "partially_met", "evidence_quotes": ["Je ne sais pas encore."], "corrections": [ALLER]}
    return lanes.TutorVerdict(**{**fields, **overrides})


@pytest.fixture
def tutor(monkeypatch):
    """A scripted tutor: each entry of ``tutor.answers`` is one call — an exception to
    raise or a verdict to return."""

    state = SimpleNamespace(answers=[], calls=0)

    def payload(db, user, scenario, task, answer, history, turn_index):
        return {
            "learner_text": answer.text,
            "history": [],
            "targets": [],
            "story": {"level": "B1", "control_language": "en"},
            "scene": {},
        }

    def fake_call(system, request, schema, on_usage=None, **kwargs):
        state.calls += 1
        answer = state.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer, {}

    monkeypatch.setattr(engine, "_turn_payload", payload)
    monkeypatch.setattr(engine, "_json_call", fake_call)
    monkeypatch.setattr(lanes, "book_lane", lambda *a, **k: None)
    monkeypatch.setattr(lanes, "_scene_of", lambda *a, **k: None)
    return state


def _margin():
    return lanes.split_margin(
        lanes.margin_correction(
            None,
            user=None,
            scenario=SimpleNamespace(story_context={}),
            task=SimpleNamespace(),
            answer=SimpleNamespace(text=LEARNER, is_blank=False),
            turn_index=0,
        )
    )


@pytest.mark.parametrize(
    "first",
    [
        engine.StoryUnavailable("story_provider_failed"),  # the walk's OpenAI 500
        engine.StoryUnavailable("story_provider_timeout"),
    ],
    ids=["provider_500", "timeout"],
)
def test_a_tutor_that_fails_once_then_answers_ends_corrected(tutor, first):
    tutor.answers = [first, _verdict()]
    correction, failure = _margin()
    assert failure is None, "the second attempt read the reply"
    assert correction is not None and correction.corrected_fr == "je suis allé"
    assert tutor.calls == 2


def test_a_tutor_answer_rejected_once_is_asked_again(tutor):
    # A quote the learner never wrote: validate_tutor rejects it and the lane asks again.
    tutor.answers = [_verdict(evidence_quotes=["Je suis allée au marché."]), _verdict()]
    correction, failure = _margin()
    assert failure is None
    assert correction is not None and correction.span_fr == "j'ai allé"


def test_a_tutor_that_never_answers_is_a_final_failure_after_a_bounded_retry(tutor):
    tutor.answers = [engine.StoryUnavailable("story_provider_failed")] * 5
    correction, failure = _margin()
    assert correction is None
    assert failure and "story_provider_failed" in failure, "a failed check is never «found nothing»"
    assert tutor.calls == lanes.MARGIN_ATTEMPTS == 2, "bounded: two calls, never more"


def test_the_stored_turn_carries_the_late_correction_to_the_replay():
    """What the turn stores is what the replay thread draws: a reply read on the second
    attempt is stored corrected and not marked unchecked; one never read stays marked."""

    correction = lanes.turn_correction(_verdict(), LEARNER)
    read = {"learner": LEARNER, "character": "…", "correction": {
        "span_fr": correction.span_fr, "corrected_fr": correction.corrected_fr,
        "note_native": correction.note_native,
    }}
    unread = {"learner": LEARNER, "character": "…", "correction": None,
              "check_failure": "StoryUnavailable: story_provider_failed"}
    shown, missed = _public_thread([read, unread])
    assert shown["correction"]["corrected_fr"] == "je suis allé" and "unchecked" not in shown
    assert missed["correction"] is None and missed["unchecked"] is True
