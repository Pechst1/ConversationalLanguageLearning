"""#250 / #318: the model-free corrector, measured on the app's own French.

Each night attempt at #250 shipped a rule that marked one more correct sentence
wrong («le deux mai» -> «mais», «quelqu'un» -> «quelqu'une»), and each was found by
hand. This file runs every rule over all the French the app itself publishes (season
scenes, rule-card and grammar examples, journey scenarios, Le Petit Prince): a
correction there is a false correction, so the guard is zero. The rule cards' own
(wrong, right) pairs are the recall floor, and every fix the pass makes on them must
be part of the card's right answer and must settle (a fixed sentence gets no fix).

No model call is made anywhere in this file.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import pytest

from app.services import correction_contract as cc

DATA = Path(__file__).resolve().parents[1] / "app" / "data"

#: The keys that hold French in use (not a gloss, not a note *about* words).
_FR_KEYS = {"fr", "in_frame", "a2", "b1", "surface_fr", "title_fr", "line_fr", "story_date_fr", "fallback", "right"}
_FRENCH = re.compile(
    r"\b(le|la|les|un|une|des|je|tu|il|elle|on|nous|vous|ils|elles|est|et|de|du|à|au|pas|que|qui|ce|c'|j'|l'|d'|n')\b",
    re.IGNORECASE,
)
_ENGLISH = re.compile(r"\b(the|and|you|is|are|with|this|that|your|for|what|of)\b", re.IGNORECASE)

#: Recall on the rule cards' own mistakes: 18 before the rebuild, 62 after it.
RECALL_FLOOR = 60


def _unbracket(text: str) -> str:
    return text.replace("[", "").replace("]", "")


def _is_french_in_use(text: str) -> bool:
    if any(mark in text for mark in "{}<_"):
        return False  # a template slot or markup, not a sentence
    if len(text) < 8 or not _FRENCH.search(text):
        return False
    return len(_ENGLISH.findall(text)) <= 1


def _strings(node, key: str = "", path: str = ""):
    """``(key, path, text)`` for every string in a JSON tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, k, f"{path}.{k}")
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v, key, f"{path}[]")
    elif isinstance(node, str):
        yield key, path, node


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def correct_french() -> tuple[tuple[str, str], ...]:
    """``(source, text)`` for the correct French the app ships."""
    out: set[tuple[str, str]] = set()
    for path in sorted((DATA / "season").glob("*/*.json")):
        for key, _, text in _strings(_load(path)):
            if key in _FR_KEYS and _is_french_in_use(text):
                out.add(("season", text))
    for path in sorted((DATA / "rule_cards").glob("*.json")):
        for _, where, text in _strings(_load(path)):
            # example sentences only: the notes talk *about* words («si il / elle»,
            # «Afin que est suivi du subjonctif»), they are not French in use
            example = where.endswith((".example.fr", ".right")) or ".examples[]" in where or ".pattern.rows[]" in where
            if example and where.endswith((".fr", ".right")) and _is_french_in_use(_unbracket(text)):
                out.add(("rule_cards", _unbracket(text)))
    for key, _, text in _strings(_load(DATA / "grammar_rule_cards.json")):
        if key in {"fr", "right"} and _is_french_in_use(_unbracket(text)):
            out.add(("grammar_rule_cards", _unbracket(text)))
    for path in sorted((DATA / "grammar_review").glob("*.json")):
        for key, _, text in _strings(_load(path)):
            if key in {"anchor_examples", "xray_sentence"}:
                for sentence in text.split("|"):
                    if _is_french_in_use(sentence.strip()):
                        out.add(("grammar_review", sentence.strip()))
    for path in sorted((DATA / "journey_scenarios").glob("**/*.json")):
        for key, _, text in _strings(_load(path)):
            if key in _FR_KEYS and _is_french_in_use(text):
                out.add(("journey", text))
    for path in sorted((DATA / "stories" / "petit_prince" / "chapters").glob("*")):
        for paragraph in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            paragraph = " ".join(paragraph.split())
            if _is_french_in_use(paragraph) and len(paragraph) < 600:
                out.add(("petit_prince", paragraph))
    return tuple(sorted(out))


def _wrong_right(node):
    if isinstance(node, dict):
        if isinstance(node.get("wrong"), str) and isinstance(node.get("right"), str):
            yield node["wrong"], _unbracket(node["right"])
        for value in node.values():
            yield from _wrong_right(value)
    elif isinstance(node, list):
        for value in node:
            yield from _wrong_right(value)


@lru_cache(maxsize=1)
def rule_card_mistakes() -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for path in sorted((DATA / "rule_cards").glob("*.json")):
        pairs.extend(_wrong_right(_load(path)))
    return tuple(pairs)


def _norm(text: str) -> str:
    return " ".join(text.replace("’", "'").split()).casefold().rstrip(" .!?")


def test_the_corpus_is_large_enough_to_mean_something():
    sources = {source for source, _ in correct_french()}
    assert len(correct_french()) > 3500
    assert {"season", "rule_cards", "grammar_review", "petit_prince"} <= sources
    assert len(rule_card_mistakes()) > 600


def test_no_rule_corrects_the_french_the_app_itself_publishes():
    false_corrections = [
        f"[{source}] «{edit.span}» -> «{edit.replacement}» ({edit.rule_id}) in: {text[:120]}"
        for source, text in correct_french()
        for edit in cc.deterministic_edits(text)
    ]
    assert false_corrections == [], "\n".join(false_corrections[:40])


def test_the_pass_fixes_the_rule_cards_own_mistakes():
    fixed = [
        (wrong, right)
        for wrong, right in rule_card_mistakes()
        if (edits := cc.deterministic_edits(wrong)) and _norm(cc.apply_edits(wrong, edits)) == _norm(right)
    ]
    assert len(fixed) >= RECALL_FLOOR, f"only {len(fixed)} of {len(rule_card_mistakes())} rule-card mistakes fixed"


def test_every_fix_on_a_rule_card_mistake_is_part_of_its_right_answer():
    wrong_fixes = [
        f"{wrong} => {right}: «{edit.span}» -> «{edit.replacement}» ({edit.rule_id})"
        for wrong, right in rule_card_mistakes()
        for edit in cc.deterministic_edits(wrong)
        if _norm(edit.replacement) not in _norm(right)
    ]
    assert wrong_fixes == [], "\n".join(wrong_fixes)


@pytest.mark.parametrize("corpus", ["mistakes", "correct"])
def test_a_repaired_sentence_gets_no_further_fix(corpus):
    """The settling invariant (#318): a fix never teaches a new mistake."""
    texts = [wrong for wrong, _ in rule_card_mistakes()] if corpus == "mistakes" else [t for _, t in correct_french()]
    unsettled = []
    for text in texts:
        repaired = cc.repair_text(text)
        again = cc.deterministic_edits(repaired)
        if again:
            unsettled.append(f"{text} -> {repaired}: {[(e.span, e.replacement) for e in again]}")
    assert unsettled == [], "\n".join(unsettled[:20])


def test_every_edit_span_is_a_substring_at_its_offsets():
    for wrong, _ in rule_card_mistakes():
        for edit in cc.deterministic_edits(wrong):
            assert wrong[edit.start : edit.end] == edit.span
            assert edit.note_for("en") and edit.note_for("de") and edit.note_for("fr")
