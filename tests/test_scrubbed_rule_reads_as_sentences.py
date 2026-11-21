"""R5 (check walk of 19 Nov, B1.1, English): «You wrote «lui». Order. Je te le donne, je le lui donne.»

While a missed Forge item waits for its retry, every clause of its note that names the
answer is dropped (``solution_gate.scrub_hint``). The unit's short rule opened with a bare
label («Order: me/te/…, then en: je te le donne…»); with the list gone, the label was left
standing as a one-word sentence. The rule now opens with a sentence in en, de and fr.
"""

from __future__ import annotations

import re

import pytest

from app.services import solution_gate
from app.services.grammar_units import _v2_rows_by_external_id
from app.services.learner_copy import learner_text


def _short_rule(language: str) -> str:
    return _v2_rows_by_external_id()["FR2_B11_DOUBLE_PRONOUNS"]["syllabus"]["rule_short"][language]


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_a_withheld_pronoun_order_note_reads_as_sentences(language: str) -> None:
    what = learner_text("forge.diff.word", language, learner="lui", target="en")
    note = f"{what} {_short_rule(language)}"
    scrubbed = solution_gate.scrub_hint(note, ["en"], {"en"})
    assert scrubbed, note
    assert "«en»" not in scrubbed and "« en »" not in scrubbed, scrubbed
    for sentence in re.split(r"(?<=[.!?])\s+", scrubbed):
        words = re.findall(r"[\w’']+", sentence)
        assert len(words) >= 3, f"a label standing as a sentence: {sentence!r} in {scrubbed!r}"


def test_the_short_rule_keeps_its_three_languages() -> None:
    assert _short_rule("en").startswith("The order is fixed:")
    assert _short_rule("de").startswith("Die Reihenfolge ist fest:")
    assert _short_rule("fr").startswith("L'ordre est fixe :")
