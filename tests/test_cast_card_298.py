"""#298: the Trombinoscope card is written for the learner, never copied from the
author's story bible.

Root cause: ``world.json`` ``cast[].role`` / ``dynamic_with_user`` are briefs for the
writers («from T2 on», «they are NOT a couple») and ``cast_payload`` sent them to the
cast page, the studio header and the atelier character as the card's own text. One
field served the author and the learner. The card line now comes from the cast
registry (``cast_cards.json``, per interface language); the bible's text stays server
side (``cast_author_notes``) for the prompts that need it.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from app.services import cast_registry as reg
from app.services.serial import SerialThreadService

WORLD = json.loads(reg.WORLD_PATH.read_text(encoding="utf-8"))
LANGUAGES = ("en", "de", "fr")
#: Author notation and planning words that may never reach a learner.
PLANNING = re.compile(r"\bT\d\b|\bNOT\b|(?i:\bgap\s*\d|\bseason\s*\d|\bsaison\s*\d|minor character|\bplot\b)")


def _service() -> SerialThreadService:
    service = SerialThreadService.__new__(SerialThreadService)
    service._cast_episode_index = lambda thread: {}
    return service


def _thread() -> SimpleNamespace:
    return SimpleNamespace(world_bible=WORLD, state={})


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def test_no_cast_card_text_is_the_authors_planning_note():
    rows = _service().cast_payload(_thread())
    assert rows
    for row in rows:
        text = " ".join(_strings(row))
        assert not PLANNING.search(text), f"{row['id']}: planning text reaches the card: {text[:160]!r}"
        assert "NOT a couple" not in text and "T2" not in text


def test_the_card_never_carries_the_bible_fields_the_author_wrote():
    bible = {str(m["id"]): m for m in WORLD["cast"]}
    for row in _service().cast_payload(_thread()):
        sent = " ".join(_strings(row))
        for field in ("role", "dynamic_with_user", "personality", "wants", "contradiction"):
            note = str(bible[row["id"]].get(field) or "").strip()
            assert not note or note not in sent, f"{row['id']}: the bible's {field} is on the card"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_card_is_a_learner_line_in_the_interface_language(language):
    rows = _service().cast_payload(_thread(), language=language)
    for row in rows:
        assert row["role"] == reg.card_line(row["id"], language)
        assert row["role"], f"{row['id']} has no learner-facing card line in {language}"
        assert not PLANNING.search(row["role"])


def test_every_cast_member_has_a_line_in_each_language_and_it_is_translated():
    for cast_id in reg.all_members():
        lines = {lang: reg.card_line(cast_id, lang) for lang in LANGUAGES}
        assert all(lines.values()), f"{cast_id}: missing a card line: {lines}"
        assert lines["en"] != lines["de"], f"{cast_id}: the German line is the English one"
        assert lines["en"] != lines["fr"], f"{cast_id}: the French line is the English one"


def test_a_card_names_nobody_the_learner_meets_after_that_person():
    """No plot ahead of the page: a card may not name someone introduced later."""
    members = reg.all_members()
    for cast_id, found in members.items():
        for language in LANGUAGES:
            line = reg.card_line(cast_id, language).lower()
            for other in members.values():
                if other.first_day <= found.first_day:
                    continue
                titles = {"mme", "m.", "maître", "mr", "mrs"}
                labels = {other.short_name} | {w for w in other.name.split() if w.lower() not in titles}
                for label in labels:
                    assert not re.search(rf"\b{re.escape(label.lower())}\b", line), (
                        f"{cast_id} ({language}) names {other.id}, who comes later: {line!r}"
                    )


def test_the_authors_notes_stay_server_side_for_the_prompts():
    notes = _service().cast_author_notes(_thread())
    assert "NOT a couple" in notes["lila_bonnet"]["role"]
    assert notes["mme_diallo"]["dynamic_with_user"]
