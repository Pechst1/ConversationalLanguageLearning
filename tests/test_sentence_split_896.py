"""#896: one sentence splitter, on the server and on the device, pinned by one fixture.

Three walk findings in a week were the same flaw: each surface cut a text into sentences
with its own pattern, and none knew that a «?» inside a quotation, before a hesitation
that runs on, or inside a chain of alternatives ends no sentence.

* #893 (18 Nov): La Forge's judge miss printed «„Tu est française, Margaux ? “ stimmt
  nicht; richtig ist „Tu es française, Margaux ?»: the device's note splitter cut at every
  «?», and the closing «“.» folded to nothing and was dropped.
* #827 (16 Nov): «Fin du chapitre» printed «Ou tu dis au revoir à tout ça ?», the last of
  the A1 season question's alternatives: ``question_line`` kept the last «?» piece.
* #849: the rule drill keyed «le groupe qui tient le café ensemble ?», the tail after
  «déjà…», fixed then in one splitter only.

``app.services.sentence_line.sentences`` is the one splitter; ``web-frontend/lib/
sentence-split.ts`` mirrors it and reads the same fixture (``lib/sentence-split.test.js``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services import living_story as engine
from app.services import story_archive
from app.services.season.levels import VARIANT_FIELDS, level_key, read_levels
from app.services.sentence_line import drop_cut_tail, question_line, sentences

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/sentence_split_cases.json"


def _cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


#: Read at collection for the parametrised test; the walk-lines test below reads it again
#: and fails loudly if the fixture is gone.
CASES = _cases() if FIXTURE.exists() else []
SEASON = ROOT / "app/data/season/s1"
#: A line opening on one of these is the tail of a chain of alternatives (#827 done-when).
FRAGMENT_OPENING = re.compile(r"^[«\"“(]?\s*(?:ou|et|mais|pour)\b", re.IGNORECASE)


@pytest.mark.parametrize("case", CASES, ids=[case["why"][:60] for case in CASES])
def test_the_server_splitter_reads_every_fixture_line(case: dict) -> None:
    assert sentences(case["text"]) == case["sentences"], case["why"]


def test_the_fixture_holds_the_walk_lines() -> None:
    texts = [case["text"] for case in _cases()]
    assert "„Tu est française, Margaux ?“ stimmt nicht; richtig ist „Tu es française, Margaux ?“." in texts
    assert "Comment on dit, déjà… le groupe qui tient le café ensemble ?" in texts
    assert _season_questions()["a1"] in texts


# --- #827: a chapter's question is a whole question ------------------------------------


def _season_questions() -> dict[str, str]:
    question = json.loads((SEASON / "season.json").read_text(encoding="utf-8"))["question"]
    by_level = {"a2": question["a2"]}
    if question.get("b1"):
        by_level["b1"] = question["b1"]
    variants = read_levels(SEASON)["lines"].get(level_key(question["a2"], question.get("b1"))) or {}
    for field in VARIANT_FIELDS:
        if isinstance(variants.get(field), str) and variants[field].strip():
            by_level[field] = variants[field]
    return by_level


def test_every_level_of_the_season_question_has_a_variant() -> None:
    # The A1 one is the walk's: if it went missing, the next test would pass on nothing.
    assert {"a1", "a2", "b2", "c1"} <= set(_season_questions())


@pytest.mark.parametrize("level", sorted(_season_questions()))
def test_each_level_of_the_season_question_files_a_whole_question(level: str) -> None:
    text = _season_questions()[level]
    line = question_line(text, engine.DIGEST_PART_CHARS)

    assert line, f"{level}: no question at all"
    assert line.endswith("?"), f"{level}: {line!r} is not a question"
    assert not FRAGMENT_OPENING.match(line), f"{level}: {line!r} opens on the tail of a chain of alternatives"
    assert line in " ".join(sentences(text)), f"{level}: {line!r} is not cut from the text"


def test_the_a1_chain_is_filed_from_its_first_question() -> None:
    line = question_line(_season_questions()["a1"], engine.DIGEST_PART_CHARS)

    assert line == (
        "Alors, qu'est-ce que tu fais ? Tu prends l'appartement pour toi ? "
        "Pour toi et les autres ? Ou tu dis au revoir à tout ça ?"
    )


def test_the_archive_line_of_a_chapter_with_no_resolution_is_the_whole_question() -> None:
    digest = engine.chapter_digest_line({"question": _season_questions()["a1"], "resolved_fr": "", "development": ""})

    assert digest and digest.startswith("Alors, qu'est-ce que tu fais ?"), digest
    assert digest.endswith("Ou tu dis au revoir à tout ça ?"), digest


def test_a_chain_too_long_to_lead_in_is_kept_whole_from_its_first_alternative() -> None:
    text = (
        "Le café brûle encore dans les mémoires du quartier, et personne ne veut en parler franchement. "
        "Qu'est-ce que tu fais de l'appartement que ta grand-mère t'a laissé au-dessus du Mistral ? "
        "Tu le gardes pour toi seul ? Pour toi et pour tous ceux qui vivent ici depuis des années ? "
        "Ou tu rends la clé au notaire ?"
    )
    line = question_line(text, 160)

    assert line == (
        "Tu le gardes pour toi seul ? Pour toi et pour tous ceux qui vivent ici depuis des années ? "
        "Ou tu rends la clé au notaire ?"
    )


def test_an_alternative_after_a_statement_brings_the_statement_or_nothing() -> None:
    text = (
        "Ta grand-mère t'a laissé l'étage au-dessus du Mistral, et avec lui le feu qui a pris en dessous, "
        "il y a quarante ans. Ou tu préfères ne rien savoir de tout ça, et partir demain ?"
    )

    assert question_line(text, 100) == ""
    assert question_line(text, 200) == text


# --- #827 review (night 2026-11-17): whole questions that open on Et/Mais/Pour stay -----


def test_a_whole_closing_question_that_opens_on_mais_is_still_the_question() -> None:
    text = (
        "Odile ferme le café à minuit, comme chaque soir depuis l'incendie de 1984, et Marin range les "
        "chaises sans un mot pour personne. Mais qui a gardé la deuxième clé ?"
    )

    assert question_line(text, 100) == "Mais qui a gardé la deuxième clé ?"


@pytest.mark.parametrize(
    "question",
    [
        "Mais qui a gardé la deuxième clé ?",
        "Et si Odile avait menti sur l'incendie ?",
        "Pour qui Odile travaille-t-elle vraiment ?",
    ],
)
def test_a_whole_question_opening_on_et_mais_pour_is_read_back_unchanged(question: str) -> None:
    assert drop_cut_tail(question) == question
    assert engine.chapter_digest_line({"question": question, "resolved_fr": ""}) == question
    assert (
        engine.chapter_digest_line({"question": question, "resolved_fr": "Marin garde la clé."})
        == f"{question} → Marin garde la clé."
    )
    assert story_archive.clean_digest(f"{question} → Marin garde la clé.") == f"{question} → Marin garde la clé."


def test_a_row_filed_under_the_tail_alone_is_read_back_without_it() -> None:
    # Rows written before the fix carry «Ou tu dis au revoir à tout ça ?» as their question.
    tail = "Ou tu dis au revoir à tout ça ?"
    assert engine.chapter_digest_line({"question": tail, "resolved_fr": ""}) is None
    assert engine.chapter_digest_line({"question": tail, "resolved_fr": "Marin garde la clé."}) == "Marin garde la clé."
    assert story_archive.clean_digest(f"{tail} → Marin garde la clé.") == "Marin garde la clé."
    assert story_archive.clean_digest(tail) is None
    # A resolution that opens on «Et» is no question, and stays.
    assert story_archive.clean_digest("Et Marin garde la clé.") == "Et Marin garde la clé."


# --- the guard: no new surface cuts sentences with a pattern of its own ------------------

#: A pattern that cuts a text at, or runs a match up to, a sentence's end: a lookbehind
#: on . ! ? («(?<=[.!?…])»), a run of anything but them («[^.!?…]+»), or a split on them.
_STOP_CLASS = re.compile(r"\[(\^?)((?:\\.|[^\]\[\\\n])*)\]")


def _sentence_cuts(source: str) -> int:
    count = 0
    for line in source.splitlines():
        for match in _STOP_CLASS.finditer(line):
            negated, body = match.group(1), match.group(2)
            if not all(mark in body for mark in ".!?"):
                continue
            before = line[: match.start()]
            if negated or before.endswith("(?<=") or re.search(r"\bsplit\s*\(", before):
                count += 1
    return count


#: Surfaces that still cut sentences with a pattern of their own, and how many such
#: patterns each holds: the remaining stages of #896. The list may only shrink: move a
#: surface onto ``sentence_line.sentences`` (or ``splitSentences`` on the device), then
#: drop its line here. A new surface that cuts sentences calls the shared splitter.
KNOWN_OWN_SPLITTERS = {
    "app/services/achievement_recap.py": 1,
    "app/services/anki_import.py": 1,
    "app/services/answer_acceptance.py": 2,
    "app/services/book_library.py": 3,
    "app/services/forge.py": 1,
    "app/services/forge_grading.py": 5,
    "app/services/forge_item_validator.py": 2,
    "app/services/grammar_feedback.py": 3,
    "app/services/item_bank.py": 1,
    "app/services/item_bank_de.py": 2,
    "app/services/journal.py": 1,
    "app/services/journey_conversation.py": 1,
    "app/services/lane_guards.py": 7,
    "app/services/learner_facts.py": 1,
    "app/services/living_story.py": 2,
    "app/services/no_address.py": 1,
    "app/services/revue/builder.py": 1,
    "app/services/revue/comptoir.py": 1,
    "app/services/revue/correcteur.py": 1,
    "app/services/revue/encounter.py": 1,
    "app/services/revue/radio.py": 1,
    "app/services/revue/voice.py": 1,
    "app/services/scene_ledger.py": 1,
    "app/services/season/canon_guards.py": 5,
    "app/services/season/epilogue.py": 1,
    "app/services/season/prose_detector.py": 2,
    "app/services/solution_gate.py": 1,
    "app/services/story_correspondence.py": 1,
    "app/services/story_memory.py": 1,
    "app/services/story_split.py": 1,
    "app/services/story_teaser.py": 1,
    "web-frontend/lib/revue-mock-comptoir.ts": 2,
    "web-frontend/lib/revue-mock.ts": 1,
}
#: The shared splitter itself, and its mirror.
SHARED_SPLITTERS = {"app/services/sentence_line.py", "web-frontend/lib/sentence-split.ts"}


def _surfaces() -> dict[str, int]:
    found: dict[str, int] = {}
    paths = [*(ROOT / "app/services").rglob("*.py"), *(ROOT / "web-frontend/lib").rglob("*.ts")]
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if relative in SHARED_SPLITTERS or ".test." in relative:
            continue
        count = _sentence_cuts(path.read_text(encoding="utf-8"))
        if count:
            found[relative] = count
    return found


def test_the_guard_sees_the_patterns_it_is_for() -> None:
    assert _sentence_cuts(r"""return (note.match(/[^.!?…]+(?:[.!?…]+|$)/g) ?? [note])""") == 1
    assert _sentence_cuts(r'''_SPLIT = re.compile(r"(?<=[.!?…])\s+")''') == 1
    assert _sentence_cuts(r'''parts = re.split(r"[.!?…]+", text)''') == 1
    # Stripping a final stop, or checking that a line ends on one, cuts nothing.
    assert _sentence_cuts(r""".replace(/[.!?…:;,\s]+$/g, '')""") == 0
    assert _sentence_cuts(r'''if re.search(r"[.!?…]$", text):''') == 0


def test_no_surface_cuts_sentences_without_the_shared_splitter() -> None:
    found = _surfaces()
    new = {path: count for path, count in found.items() if count > KNOWN_OWN_SPLITTERS.get(path, 0)}
    assert not new, (
        "these surfaces cut text into sentences with a pattern of their own; call "
        "app.services.sentence_line.sentences (or splitSentences from web-frontend/lib/sentence-split.ts) "
        f"instead (#896): {new}"
    )


def test_the_list_of_own_splitters_only_shrinks() -> None:
    found = _surfaces()
    gone = {path: count for path, count in KNOWN_OWN_SPLITTERS.items() if found.get(path, 0) < count}
    assert not gone, f"these surfaces now use the shared splitter: lower or drop their line in KNOWN_OWN_SPLITTERS: {gone}"
