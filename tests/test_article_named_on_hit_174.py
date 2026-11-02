"""#174, owner call of 2 Nov 2026: a noun asked for without its article.

«Wie sagt man „Wohnung“?» asks for the noun, so the noun alone or with any article is
the word (QA-PRACTICE, 3 Oct: `test_a_noun_asked_without_an_article_is_right_with_any_
article_or_none`). That stays. What changes: a wrong article («une appartement», «le
appartement») was passed in silence, and the learner never read the right one. It is
now named on the hit, in one line, the way a forgiven accent is («Richtig — achte auf
den Artikel: «un appartement».»). The answer stays a hit, and nothing is filed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import journey_learning
from app.services.answer_acceptance import article_slip_fix, article_slip_note
from app.services.journey_contracts import AssistanceLevel, AttemptAnswer, InputMode, TaskOutcome
from tests.test_qa_practice_items import GERMAN_A1, _short_answer

ENGLISH_A1 = SimpleNamespace(native_language="en", cefr_estimate="A1.1", proficiency_level="A1")


def _evaluate(task, text: str, user=GERMAN_A1):  # type: ignore[no-untyped-def]
    return journey_learning.evaluate_recall(
        None, user=user, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text), assistance=AssistanceLevel.NONE,
    )


@pytest.mark.parametrize(
    ("typed", "note"),
    [
        ("une appartement", "Richtig — achte auf den Artikel: «un appartement»."),
        ("Une appartement.", "Richtig — achte auf den Artikel: «un appartement»."),
        ("le appartement", "Richtig — vor einem Vokal: «l'appartement»."),
        ("la appartement", "Richtig — vor einem Vokal: «l'appartement»."),
        ("une appart", "Richtig — achte auf den Artikel: «un appart»."),
    ],
)
def test_a_wrong_article_stays_a_hit_and_is_named(typed: str, note: str) -> None:
    evaluation = _evaluate(_short_answer("un appartement", "Wohnung"), typed)

    assert evaluation.outcome is TaskOutcome.MET
    assert evaluation.slip_note_native == note
    assert evaluation.slip_kind == "article"
    assert evaluation.correction is None  # named, never filed as a mistake


def test_the_line_is_in_the_learner_s_language() -> None:
    evaluation = _evaluate(_short_answer("un appartement", "flat"), "une appartement", user=ENGLISH_A1)

    assert evaluation.outcome is TaskOutcome.MET
    assert evaluation.slip_note_native == "Right — watch the article: «un appartement»."


@pytest.mark.parametrize("typed", ["un appartement", "l'appartement", "appartement", "un appart", "  APPARTEMENT "])
def test_a_right_article_or_none_is_named_nothing(typed: str) -> None:
    evaluation = _evaluate(_short_answer("un appartement", "Wohnung"), typed)

    assert evaluation.outcome is TaskOutcome.MET
    assert evaluation.slip_note_native is None
    assert evaluation.slip_kind is None


def test_a_gloss_that_names_its_article_still_refuses_the_wrong_one() -> None:
    evaluation = _evaluate(_short_answer("un appartement", "eine Wohnung"), "une appartement")

    assert evaluation.outcome is TaskOutcome.NOT_YET
    assert evaluation.correction is not None
    assert evaluation.correction.corrected_fr == "un appartement"


@pytest.mark.parametrize(
    ("key", "typed", "fixed"),
    [
        ("un appartement", "une appartement", "un appartement"),
        ("un appartement", "le appartement", "l'appartement"),
        ("appartement", "une appartement", "un appartement"),
        ("un appart", "une appart", "un appart"),
        # The key's article decides the gender, not another word spelt the same.
        ("la poste", "le poste", "la poste"),
        ("la poste", "un poste", "une poste"),
        ("l'école", "la école", "l'école"),
        ("les toilettes", "la toilettes", "les toilettes"),
        # Nothing is named when it cannot be told.
        ("un appartement", "appartement", None),
        ("un hôtel", "le hôtel", None),
        ("un yaourt", "la yaourt", None),
        ("", "une appartement", None),
    ],
)
def test_the_named_form(key: str, typed: str, fixed: str | None) -> None:
    assert article_slip_fix(key, typed) == fixed


def test_the_note_names_only_an_article_slip() -> None:
    assert article_slip_note("gender", "un appartement", "fr") == "Juste — attention à l'article : « un appartement »."
    assert article_slip_note("elision", "l'appartement", "en") == "Right — before a vowel: «l'appartement»."
    assert article_slip_note("accent", "très", "en") is None
    assert article_slip_note("gender", "", "en") is None
