"""P10 — the strings that were in the wrong language (experience review, finding 9).

Observed in real play (logs ``b1-part1.md``, ``b1-part2.md``, ``a1-part1.md``):

* La Forge's build card printed the generator's own ask as the sentence to build:
  «Construis la phrase : « Express a complete sentence in French using pronoun choice;
  use every target chip once. »».
* A German learner's lexical gap was glossed in English («bague — ring»): the grader
  asked every model for «a short English gloss».
* The authored end-card caption read «Lila heard what you said. The rest stays open.»
  on a French (B1) card: it followed the mother tongue, not the interface language.

The rule: everything that is not fiction is in the interface language
(``user_chrome_language``); glosses in the mother tongue (``user_mother_tongue``).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import atelier, item_bank
from app.services import living_story as engine

PLACEHOLDER = "Express a complete sentence in French using pronoun choice; use every target chip once."


def _stored_build(cue: str) -> dict:
    """A word-bank item as an exercise set stored before P10 carries it."""

    return {
        "id": "c1-fallback-bank-1",
        "prompt": "Build the full French sentence.",
        "meaning_cue": cue,
        "tokens": ["demain", "me", "Tu", "peux", "en", "?", "y", "prêter", "le"],
        "answer_tokens": ["Tu", "peux", "me", "le", "prêter", "demain", "?"],
        "correct_answer": "Tu peux me le prêter demain ?",
    }


def _served_text(item: dict) -> str:
    return " ".join(str(item.get(key) or "") for key in ("meaning_cue", "goal_native", "prompt", "instruction"))


def test_the_fallback_cue_is_a_meaning_or_nothing():
    assert atelier._word_bank_meaning_cue(None, "Tu peux me le prêter demain ?") == ""
    assert atelier._word_bank_meaning_cue(None, "Je ne bois pas de café") == "I do not drink coffee."
    for cue in atelier._FALLBACK_MEANING_CUES.values():
        assert not cue.lower().startswith("express"), cue


@pytest.mark.parametrize(
    ("language", "native"),
    [("en", "en"), ("de", "de"), ("fr", "en"), ("fr", "de"), ("fr", "es")],
)
def test_a_stored_placeholder_cue_never_reaches_a_learner(language, native):
    for cue in (PLACEHOLDER, f"Express: {PLACEHOLDER}"):
        served = item_bank.public_item(_stored_build(cue), language, native)
        assert not str(served.get("meaning_cue") or "").lower().startswith("express")
        assert "complete sentence in French" not in _served_text(served), served
        assert "target chip" not in _served_text(served), served


def test_a_real_meaning_keeps_its_words_without_the_prefix():
    served = item_bank.public_item(_stored_build("Express: You can lend it to me tomorrow?"), "en", "en")
    assert served["meaning_cue"] == "You can lend it to me tomorrow?"
    assert item_bank.meaning_cue_text("Build the full French sentence.") == ""
    assert item_bank.meaning_cue_text("") == ""


def _correction_service(chrome: str, native: str) -> atelier.AtelierCorrectionService:
    service = atelier.AtelierCorrectionService.__new__(atelier.AtelierCorrectionService)
    service.explanation_language = chrome
    service._learner_native = native
    return service


@pytest.mark.parametrize(("chrome", "native", "name"), [("de", "de", "German"), ("fr", "de", "German"), ("fr", "en", "English")])
def test_the_grader_asks_for_the_gloss_in_the_mother_tongue(chrome, native, name):
    prompt = _correction_service(chrome, native)._correction_system_prompt()
    assert "short English gloss" not in prompt
    assert f"a short gloss in {name} (the learner's own language)" in prompt


@pytest.mark.parametrize(
    ("native", "level", "expected"),
    [
        ("en", "B1.1", "a écouté ce que tu as dit"),
        ("de", "A1.1", "hat gehört, was du gesagt hast"),
        ("en", "A1.1", "heard what you said"),
    ],
)
def test_the_fallback_end_caption_is_in_the_interface_language(monkeypatch, native, level, expected):
    from app.services import pilot_events, scene_record, story_lanes

    monkeypatch.setattr(scene_record, "enabled", lambda: True)
    # The story context of a non-season day: its control language is the mother tongue.
    monkeypatch.setattr(engine, "story_context", lambda db, user: {"control_language": native, "revision": "r"})
    monkeypatch.setattr(story_lanes, "exit_register", lambda db, user, scenario: "tu")

    class _Events:
        def __init__(self, db):
            pass

        def record(self, *args, **kwargs):
            return None

    monkeypatch.setattr(pilot_events, "PilotEventService", _Events)
    user = SimpleNamespace(id=1, native_language=native, cefr_estimate=level, proficiency_level=None)
    scenario = SimpleNamespace(character_name="Lila Moreau", character_id="lila")
    evaluation = engine._fallback_evaluation(
        None,
        user=user,
        scenario=scenario,
        answer=SimpleNamespace(text="Je vais bien."),
        assistance=engine.AssistanceLevel.NONE,
        reason="model_error",
    )
    summary = evaluation.consequence.details["summary_native"]
    assert expected in summary, summary
