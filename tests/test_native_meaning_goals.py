"""NATIVE-MEANING (owner, 2026-10-16) — a production drill says what to produce,
in the learner's own language.

The owner's B1 day: a Rappel «…, ils veulent acheter tout l'immeuble. — Écrivez
les mots manquants.» (many words fit the gap) and a Forge word bank «Construisez
la phrase. Un mot est en trop.» with no meaning at all. From B1 the chrome is
French, so neither carried a meaning. Now the goal quotes the sentence's meaning
in ``native_language``.
"""
from __future__ import annotations

from app.services import item_bank as ib
from app.services import journey_planner as planner
from app.services import recall_meanings as rm
from app.services.daily_journey import _recall_task_to_json
from app.services.journey_contracts import TargetKind, TargetRef
from tests.test_journey_planner import _brief

SENTENCE = "Si Solvel gagne, ils veulent acheter tout l'immeuble."


def _cloze(control_language: str = "fr", label: str = "Si Solvel gagne"):
    target = TargetRef(kind=TargetKind.VOCABULARY, id="w1", label_fr=label, label_native=None)
    return planner.practice_task(
        "short_answer",
        target=target,
        scenario=_brief(level_band="B1", control_language=control_language),
        affordances=[],
        optional=False,
        learner_text=None,
        pool=[],
        sentences=[SENTENCE],
    )


def test_the_written_cloze_says_how_many_words_and_speaks_the_chrome_language() -> None:
    task = _cloze()
    assert task is not None and task.prompt_fr == "…, ils veulent acheter tout l'immeuble."
    assert task.goal_native == "Écris les 3 mots manquants."
    assert task.instruction_native == "Complétez la phrase de la scène."
    german = _cloze("de")
    assert german.goal_native == "Schreib die 3 fehlenden Wörter."
    assert german.instruction_native == "Ergänze den Satz aus der Szene."
    one = _cloze(label="immeuble")
    assert one.goal_native == "Écris le mot manquant."


def test_the_day_translates_the_cloze_sentence_into_the_learners_language() -> None:
    payload = _recall_task_to_json(_cloze())
    assert rm.full_sentence(payload) == SENTENCE
    asked: list[tuple[list[str], str]] = []

    def translate(sentences: list[str], language: str) -> list[str]:
        asked.append((sentences, language))
        return ["Wenn Solvel gewinnt, wollen sie das ganze Haus kaufen."]

    meanings = rm.native_meanings([payload], "de", translate=translate)
    assert asked == [([SENTENCE], "German")]
    assert rm.apply_meaning(payload, meanings, "fr") == (
        "Écris les 3 mots manquants : « Wenn Solvel gewinnt, wollen sie das ganze Haus kaufen. »"
    )
    # A French speaker, or no answer from the translator, leaves the goal alone.
    assert rm.native_meanings([payload], "fr", translate=translate) == {}
    assert rm.native_meanings([payload], "de", translate=lambda sentences, language: None) == {}
    # A goal that already quotes its meaning is not asked again.
    quoted = {**payload, "goal_native": "Bau den Satz: „Ich gehe.“"}
    assert rm.sentences_to_translate([quoted]) == []


def _word_bank() -> dict:
    meaning_en = "They can walk along the canal, Gus."
    meaning_de = "Sie können am Kanal entlang spazieren, Gus."
    return {
        "id": "wb1",
        "prompt": "Build it. One word is extra.",
        "instruction_key": "forge.word_bank",
        "tokens": ["Elles", "peuvent", "se", "promener", "le", "long", "du", "canal", "de"],
        "answer_tokens": ["Elles", "peuvent", "se", "promener", "le", "long", "du", "canal"],
        "meaning_cue": meaning_en,
        "meaning_l10n": {"en": meaning_en, "de": meaning_de},
        **ib._goal("build", meaning_en, meaning_de),
    }


def test_a_french_chrome_word_bank_quotes_the_learners_own_language() -> None:
    german = ib.with_goal(_word_bank(), "fr", "de")
    goal = "Construisez la phrase : « Sie können am Kanal entlang spazieren, Gus. » Un mot est en trop."
    assert german["goal_native"] == goal
    assert german["prompt"] == goal
    english = ib.with_goal(_word_bank(), "fr", "en")
    assert "« They can walk along the canal, Gus. »" in english["goal_native"]
    # A French speaker, or an unknown native language, keeps the French-only goal.
    assert ib.with_goal(_word_bank(), "fr", "fr")["goal_native"] == "Construisez la phrase. Un mot est en trop."
    assert ib.with_goal(_word_bank(), "fr")["goal_native"] == "Construisez la phrase. Un mot est en trop."
    # The German chrome is unchanged.
    assert ib.with_goal(_word_bank(), "de", "de")["goal_native"] == (
        "Bau den Satz: „Sie können am Kanal entlang spazieren, Gus.“"
    )
    assert ib.public_payload({"items": [_word_bank()]}, "fr", "de")["items"][0]["goal_native"] == goal
