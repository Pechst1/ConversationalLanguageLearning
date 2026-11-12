"""Owner decision, 12 Nov 2026: a sentence the learner builds or writes is said to nobody.

«Wir können bei Lila bleiben, Marin.» made the learner decide where «Marin» goes in the
French — needless difficulty, not the rule. So no build or write item (tiles, a word bank,
«Sag auf Französisch: …», a repair, «Write what you said», a free sentence with a model
answer) carries a name or form of address set off by a comma, in its prompt, its tiles,
its model answer or its accepted answers. A name inside the sentence («chez Lila») stays;
the story's dialogue and the recognise / choose items keep theirs.

This supersedes #384 for build/write items: the German prompt no longer moves the name
first, because there is no name; a plural «Sie» opens as «Sie (alle)» again (#126).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services import item_bank as ib
from app.services.answer_acceptance import addressed_names, strip_vocative, widened_answers
from app.services.cast_registry import vocative_names
from app.services.journey_contracts import RecallTask, TargetKind, TargetRef
from app.services.no_address import unaddressed_item, unaddressed_payload, unaddressed_task

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
LANGUAGES = ("en", "de", "fr")
#: Independent of the strip: a cast name said to someone, at either end, in any language.
_NAMES = "|".join(re.escape(name) for name in sorted(vocative_names(), key=len, reverse=True))
_SAID_TO = re.compile(
    rf",\s*(?:{_NAMES}|madame|monsieur|madam|sir)\s*[.?!…»“”\"]|(?:^|[.?!…:]\s+|[«„“\"]\s?)(?:{_NAMES}),\s",
    re.IGNORECASE,
)


def _addressed(text: object) -> bool:
    return bool(_SAID_TO.search(str(text or ""))) or bool(addressed_names(text))


# --------------------------------------------------------------------------- #
# The strip
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("sentence", "bare"),
    [
        ("On peut rester chez Lila, Marin.", "On peut rester chez Lila."),
        ("Margaux, je voudrais un café, s'il te plaît.", "Je voudrais un café, s'il te plaît."),
        ("Tu veux des poires, Lila ? Oui, j'en veux deux.", "Tu veux des poires ? Oui, j'en veux deux."),
        ("Je suis au Mistral, Monsieur Marchand.", "Je suis au Mistral."),
        ("Un café, s'il vous plaît, madame.", "Un café, s'il vous plaît."),
        ("Monsieur, vous avez l'heure ?", "Vous avez l'heure ?"),
        ("« Lila, tu viens ? »", "« Tu viens ? »"),
    ],
)
def test_the_address_goes_and_the_sentence_stays(sentence: str, bare: str) -> None:
    assert addressed_names(sentence)
    assert strip_vocative(sentence) == bare


@pytest.mark.parametrize(
    "sentence",
    [
        "Alors, il est là.",
        "Hier, nous avons bien dormi.",
        "Nous sommes avec Marin à la banque.",
        "On peut rester chez Lila.",
        "Oui. Odile, c'est ma grand-mère.",
        "Le Mistral, c'est mon café.",
        "Avant-hier, tu as bu un verre avec Gus.",
        "Désolée, je viens de voir ton message.",
        "L'addition, s'il vous plaît !",
    ],
)
def test_a_comma_that_sets_off_no_address_stays(sentence: str) -> None:
    assert addressed_names(sentence) == []
    assert strip_vocative(sentence) == sentence


def test_the_prompt_loses_the_same_address_in_every_language() -> None:
    names = addressed_names("Elles sont heureuses, Margaux.")
    assert strip_vocative('Say in French: "They are happy, Margaux."', names) == 'Say in French: "They are happy."'
    # #384 moved the name first so «sie» reads «they»; with no name, «Sie (alle)» (#126).
    assert strip_vocative("Sag auf Französisch: „Margaux, sie sind glücklich.“", names) == (
        "Sag auf Französisch: „Sie (alle) sind glücklich.“"
    )
    assert strip_vocative("Margaux, sie ist glücklich.", names) == "Sie ist glücklich."
    marchand = addressed_names("Je suis là, Monsieur Marchand.")
    assert strip_vocative("I am here, Mr Marchand.", marchand) == "I am here."
    assert strip_vocative("Ich bin hier, Herr Marchand.", marchand) == "Ich bin hier."
    # Only the names asked for: another comma in the prompt stays.
    assert strip_vocative("Ja, Marin ist hier, Lila.", ["Lila"]) == "Ja, Marin ist hier."


def test_a_stored_answer_without_its_name_is_right() -> None:
    """#735 stays the safety net (name at either end) and the bare sentence counts too."""

    widened = widened_answers(["On peut rester chez Lila, Marin."])
    assert "On peut rester chez Lila." in widened
    assert "Marin, on peut rester chez Lila." in widened


# --------------------------------------------------------------------------- #
# Authored data: the template frames, the rule cards, the unit reviews
# --------------------------------------------------------------------------- #

_SLOT = re.compile(r"\{[^{}]*\}|\[\[|\]\]|//[^\]]*?(?=\]\])")


def test_no_template_frame_is_said_to_someone() -> None:
    """A frame's own words never address anyone: the bank adds a name only through its
    vocative twin (``~voc``), which the build and write rungs take out again."""

    found = []
    for path in sorted((DATA / "grammar_templates").glob("units_*.json")):
        for unit, spec in json.loads(path.read_text()).items():
            for frame in (spec.get("frames") or []) if isinstance(spec, dict) else []:
                for text in (frame.get("fr"), frame.get("en"), frame.get("de"), *(frame.get("accepted") or [])):
                    if text and _addressed(_SLOT.sub("x", text)):
                        found.append((unit, frame.get("id"), text))
    assert found == []


def _pairs_and_examples() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted((DATA / "rule_cards").glob("*.json")):
        for unit, card in json.loads(path.read_text())["cards"].items():
            contrast = card.get("contrast") or {}
            out.extend((unit, str(contrast.get(key) or "")) for key in ("wrong", "right"))
            for trap in card.get("traps") or []:
                out.extend((unit, str(trap.get(key) or "")) for key in ("wrong", "right"))
            out.extend((unit, str(example.get("fr") or "")) for example in card.get("examples") or [])
    for path in sorted((DATA / "grammar_review").glob("units_*.json")):
        for unit in json.loads(path.read_text())["units"]:
            for field in ("main_traps", "anchor_examples"):
                for part in str(unit.get(field) or "").split(" | "):
                    out.extend((str(unit.get("id")), side) for side in re.split(r"\s*(?:→|->)\s*", part))
    return [(unit, text.replace("✗", "").replace("✓", "").strip()) for unit, text in out if text.strip()]


def test_no_authored_pair_or_anchor_is_said_to_someone() -> None:
    """The ✗/✓ pairs become repairs and the anchors become builds: none addresses anyone."""

    assert [(unit, text) for unit, text in _pairs_and_examples() if _addressed(text)] == []


# --------------------------------------------------------------------------- #
# La Forge: every build and write rung of every unit, served in every language
# --------------------------------------------------------------------------- #


def _served_texts(payload: dict) -> list[str]:
    """Every string the learner reads or that is the key, except a character's own line."""

    keep_out = {"scene", "coach", "character", "id", "bank_frame", "bank_fingerprint", "rule_panel"}
    texts: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key not in keep_out:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            texts.append(node)

    walk(payload)
    return texts


@pytest.fixture(scope="module")
def bank_items() -> list[ib.BankItem]:
    bank = ib.default_bank()
    items = []
    for unit in sorted(bank.templates):
        for seed in range(3):
            items.extend(bank.generate(unit, 6, seed=f"no-address:{unit}:{seed}"))
    return items


def test_the_bank_still_addresses_people_where_the_learner_only_recognises(bank_items) -> None:
    """The twins are kept: a fill or a sort may name who it is said to."""

    assert any(addressed_names(item.sentence) for item in bank_items)


def test_no_forge_build_or_write_item_is_said_to_someone(bank_items) -> None:
    from app.services.forge_coaches import coach_for_concept

    checked = stripped = 0
    for item in bank_items:
        coach = coach_for_concept(item.unit)
        built = [
            ib.word_bank_item(item),
            ib.transform_item(item),
            ib.output_item(item, round_name="sentence", requirement={"label": item.unit}),
            ib.output_item(item, round_name="conversation", requirement={"label": item.unit}, coach=coach),
            # ``build_bank_set`` seats only items that keep a sentence in the paragraph.
            ib.produce_block(item, item, requirement={"label": item.unit}) if ib.without_vocative(item) else None,
        ]
        stripped += bool(addressed_names(item.sentence))
        for payload in built:
            if payload is None:
                continue
            checked += 1
            if payload.get("answer_tokens"):
                # The tray builds the key, nothing more and nothing less.
                assert ib.normalize(ib._join(payload["answer_tokens"])) == ib.normalize(payload["correct_answer"])
            for language in LANGUAGES:
                for text in _served_texts(ib.public_item(payload, language)):
                    assert not _addressed(text), (item.frame_id, language, text)
    assert checked and stripped


def test_a_stored_item_is_served_and_graded_without_its_name() -> None:
    """An item written before the decision: served (``public_item``) and graded
    (``unaddressed_payload`` on the prompt payload) alike, tiles and key one sentence."""

    stored = {
        "id": "fr2-a11-on-build-1",
        "prompt": "Build it. One word is extra.",
        "meaning_cue": "We can stay at Lila's place, Marin.",
        "meaning_l10n": {"en": "We can stay at Lila's place, Marin.", "de": "Wir können bei Lila bleiben, Marin."},
        "answer_tokens": ["On", "peut", "rester", "chez", "Lila", ",", "Marin", "."],
        "tokens": ["Marin", "rester", ",", "On", "chez", "peut", "Lila", "peux", "."],
        "correct_answer": "On peut rester chez Lila, Marin.",
        "accepted_answers": ["On peut rester chez Lila, Marin.", "Nous pouvons rester chez Lila, Marin."],
    }
    served = ib.public_item(dict(stored), "de")
    graded = unaddressed_payload({"round": "recognize", "mode": "word_bank", "items": [dict(stored)]})["items"][0]
    for item in (served, graded):
        assert item["correct_answer"] == "On peut rester chez Lila."
        assert item["answer_tokens"] == ["On", "peut", "rester", "chez", "Lila", "."]
        assert sorted(item["tokens"]) == sorted(["rester", "On", "chez", "peut", "Lila", "peux", "."])
        assert item["accepted_answers"] == ["On peut rester chez Lila.", "Nous pouvons rester chez Lila."]
        assert item["meaning_l10n"]["de"] == "Wir können bei Lila bleiben."
    # Stripping twice changes nothing: a stripped item is served and graded as it is.
    assert unaddressed_item(graded) == graded


def test_a_name_first_build_opens_on_a_capital() -> None:
    item = unaddressed_item(
        {
            "id": "x",
            "answer_tokens": ["Margaux", ",", "tu", "as", "des", "tasses", "?"],
            "tokens": ["tasses", "tu", "Margaux", "as", "?", ",", "des", "les"],
            "correct_answer": "Margaux, tu as des tasses ?",
            "meaning_l10n": {"de": "Margaux, hast du Tassen?"},
        }
    )
    assert item["correct_answer"] == "Tu as des tasses ?"
    assert item["answer_tokens"] == ["Tu", "as", "des", "tasses", "?"]
    assert "Tu" in item["tokens"] and "Margaux" not in item["tokens"] and "," not in item["tokens"]
    assert item["meaning_l10n"]["de"] == "Hast du Tassen?"


def test_a_build_with_no_sentence_left_is_not_posed() -> None:
    assert unaddressed_item({"id": "x", "example_answer": "Merci, madame.", "prompt": 'Say in French: "Thank you, madam."'}) is None
    # Served and graded alike, it stays as it was (and «Merci.» is accepted all the same).
    assert unaddressed_payload({"items": [{"id": "x", "example_answer": "Merci, madame."}]})["items"][0]["example_answer"] == "Merci, madame."


def test_recognise_items_keep_their_name() -> None:
    fill = {"id": "x", "prompt": "On ___ rester chez Lila, Marin.", "choices": ["peut", "peux"], "correct_answer": "peut"}
    assert unaddressed_item(fill) == fill
    assert ib.public_item(dict(fill), "en")["prompt"] == fill["prompt"]


# --------------------------------------------------------------------------- #
# The journey's recall drills
# --------------------------------------------------------------------------- #

_TARGET = TargetRef(kind=TargetKind.GRAMMAR, id="g:1", label_fr="pouvoir")


def _tiles_task(words: list[str], *, goal: str) -> RecallTask:
    tiles = [{"id": f"tile_{index}", "text_fr": word} for index, word in enumerate(words)]
    sentence = " ".join(words)
    return RecallTask(
        task_type="tiles",
        instruction_native="Bau den Satz.",
        prompt_fr=None,
        options=[*reversed(tiles), {"id": "chip_x", "text_fr": "peux"}],
        target=_TARGET,
        optional=False,
        correct_tile_order=[tile["id"] for tile in tiles],
        accepted_answers=[sentence],
        solution_fr=sentence,
        hint_native=f"Der Satz beginnt mit «{words[0]}».",
        goal_native=goal,
    )


def test_a_recall_build_loses_the_address_and_its_tiles() -> None:
    task = _tiles_task(["On", "peut", "rester", "chez", "Lila,", "Marin."], goal="Bau den Satz: „Wir können bei Lila bleiben, Marin.“")
    bare = unaddressed_task(task)
    by_id = {option["id"]: option["text_fr"] for option in bare.options}
    assert [by_id[tile] for tile in bare.correct_tile_order] == ["On", "peut", "rester", "chez", "Lila."]
    assert "Marin." not in by_id.values() and "Lila," not in by_id.values() and "peux" in by_id.values()
    assert bare.solution_fr == "On peut rester chez Lila." and bare.accepted_answers == ["On peut rester chez Lila."]
    assert bare.goal_native == "Bau den Satz: „Wir können bei Lila bleiben.“"


def test_a_recall_build_opening_on_a_name_loses_it_and_its_hint() -> None:
    task = _tiles_task(["Lila,", "tu", "viens", "au", "Mistral", "?"], goal="Bau den Satz: „Lila, kommst du ins Mistral?“")
    bare = unaddressed_task(task)
    by_id = {option["id"]: option["text_fr"] for option in bare.options}
    assert " ".join(by_id[tile] for tile in bare.correct_tile_order) == "Tu viens au Mistral ?"
    assert bare.hint_native is None
    assert bare.goal_native == "Bau den Satz: „Kommst du ins Mistral?“"


def test_a_register_repair_whose_cue_is_the_address_is_not_posed() -> None:
    task = RecallTask(
        task_type="transform", instruction_native="Korrigiere.", prompt_fr="Monsieur, un café, s'il te plaît.",
        options=[], target=_TARGET, optional=False, accepted_answers=["Monsieur, un café, s'il vous plaît."],
        solution_fr="Monsieur, un café, s'il vous plaît.", source_fr="Monsieur, un café, s'il te plaît.",
    )
    assert unaddressed_task(task) is None


def test_a_choice_keeps_its_name() -> None:
    task = RecallTask(
        task_type="choice", instruction_native="Wähle.", prompt_fr="On ___ rester chez Lila, Marin.",
        options=[{"id": "a", "text_fr": "peut"}], target=_TARGET, optional=False, correct_option_id="a",
    )
    assert unaddressed_task(task) is task


def _scene_lines() -> list[str]:
    """Every French line a checked-in scene or season says (the lines a rebuild is cut from)."""

    lines: list[str] = []

    def walk(node: object, key: str = "") -> None:
        if isinstance(node, dict):
            for child_key, value in node.items():
                walk(value, child_key)
        elif isinstance(node, list):
            for value in node:
                walk(value, key)
        elif isinstance(node, str) and key in {"text_fr", "line_fr", "opening_line_fr", "a1", "a2", "b1", "b2", "c1"}:
            lines.append(node)

    for folder in ("journey_scenarios", "season"):
        for path in sorted((DATA / folder).rglob("*.json")):
            walk(json.loads(path.read_text()))
    return lines


def test_no_scene_line_is_rebuilt_said_to_someone() -> None:
    """The story's lines keep their names; a line cut into tiles to rebuild loses it."""

    from app.services.scene_items import SceneLine, build_line_unscramble_task

    rebuilt = addressed = 0
    for index, text in enumerate(_scene_lines()):
        for language in LANGUAGES:
            task = build_line_unscramble_task(
                target=_TARGET, line=SceneLine("lila", text, f"line-{index}"), speaker_name="Lila",
                optional=False, control_language=language, meaning=None,
            )
            if task is None:
                continue
            rebuilt += 1
            addressed += bool(addressed_names(text))
            bare = unaddressed_task(task)
            if bare is None:
                continue
            by_id = {option["id"]: option["text_fr"] for option in bare.options}
            built = " ".join(by_id[tile] for tile in bare.correct_tile_order)
            for field in (built, bare.solution_fr, *bare.accepted_answers, bare.goal_native, bare.instruction_native):
                assert not _addressed(field), (language, text, field)
    assert rebuilt and addressed
