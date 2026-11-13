"""WP-L10 — the rule card v2 content is complete, well-formed and served."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from app.services.rule_cards import _cards, rule_card_for

ROOT = Path(__file__).resolve().parents[1]
SHAPES = {"square", "circle", "circles", "triangle", "none"}
MARK = re.compile(r"\[[^\]]+\]")


def _catalogue_ids(levels: set[str]) -> set[str]:
    with (ROOT / "app" / "data" / "grammar_catalog" / "french_core_grammar_v1.tsv").open(encoding="utf-8") as handle:
        return {row["external_id"] for row in csv.DictReader(handle, delimiter="\t") if row["cefr_level"] in levels}


def _balanced(text: str) -> bool:
    depth = {"[": 0, "{": 0}
    for char in text:
        if char in "[{":
            if any(depth.values()):
                return False
            depth[char] += 1
        elif char == "]":
            depth["["] -= 1
        elif char == "}":
            depth["{"] -= 1
        if min(depth.values()) < 0:
            return False
    return not any(depth.values())


def test_every_a1_and_a2_concept_has_a_card():
    assert _catalogue_ids({"A1", "A2"}) <= set(_cards())


def test_every_card_is_complete_in_english_and_german():
    for external_id, card in _cards().items():
        assert MARK.search(card["example"]["fr"]), external_id
        for field in ("rule", "more"):
            for language in ("en", "de"):
                assert card[field][language].strip(), (external_id, field, language)
        for language in ("en", "de"):
            assert card["example"]["tr"][language].strip(), (external_id, language)
        # One sentence, short: the owner's rule card has no text wall.
        assert len(card["rule"]["en"].split()) <= 20, external_id
        assert card["contrast"]["wrong"] and MARK.search(card["contrast"]["right"]), external_id


def test_markup_is_balanced_and_patterns_are_drawable():
    for external_id, card in _cards().items():
        pattern = card["pattern"]
        strings = [card["example"]["fr"], card["contrast"]["wrong"], card["contrast"]["right"]]
        if pattern["kind"] == "rows":
            assert pattern["rows"], external_id
            for row in pattern["rows"]:
                assert row["shape"] in SHAPES, (external_id, row)
                strings.append(row["fr"])
        else:
            # Six persons, or eight where il/elle and ils/elles differ (agreement),
            # or four for a paradigm that is not a person table (passive, gérondif).
            assert pattern["kind"] == "table" and 4 <= len(pattern["rows"]) <= 8, external_id
            strings.extend(row["fr"] for row in pattern["rows"])
            assert pattern["note"]["en"] and pattern["note"]["de"], external_id
        for text in strings:
            assert _balanced(text), (external_id, text)


def test_a_concept_without_a_card_keeps_the_legacy_panel():
    assert rule_card_for(None) is None
    assert rule_card_for("FR_C1_SYN_001") is None
    assert rule_card_for("FR_A1_NOUN_001")["speaker"] == "margaux_barman"


def test_the_card_travels_with_the_serialized_concept():
    from types import SimpleNamespace

    from app.services.atelier import serialize_concept

    concept = SimpleNamespace(
        id=1, external_id="FR_A1_VERB_001", name="Present tense core verbs", level="A1",
        category="Verbs", subskill="present", core_rule="", main_traps="", anchor_examples="",
        exercise_tags=[], is_foundation=True,
    )
    data = serialize_concept(concept)
    assert data["rule_card"]["pattern"]["kind"] == "table"
    assert data["rule_card"]["pattern"]["verb"] == "habiter"


# --------------------------------------------------------------------------
# #753: the French text of a rule card speaks to the learner with «tu».
#
# The cards are stored text, served as written; two authoring batches wrote two
# registers (A2/B2 «Mets avoir au présent», A1/B1/C1 «Mettez…») and nothing
# checked which one a card was in. This is the register contract for that text.
# A *mention* of vous (a form being taught: «nous, vous, ils», «: vous êtes»,
# «(pourriez-vous…)», «« Avez-vous… ? »») is not an address and is left alone.
# --------------------------------------------------------------------------

RULE_CARD_FILES = sorted((ROOT / "app" / "data" / "rule_cards").glob("fr2_*.json"))
#: Quoted or bracketed text is an example or a form, never the card talking.
_MENTIONED = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"]*\"|\([^)]*\)")
_STEP = r"^[ \t]*(?:\d+[.)][ \t]*)?"
#: A vous imperative that opens a step: «Remplacez…», «Dites…», «Ne déplacez pas…».
_VOUS_VERB = (
    r"(?:ne[ \t]+|n['’][ \t]*)?(?:(?:le|la|les|en|y|lui|leur)[ \t]+|l['’])?"
    r"([A-Za-zÀ-ÿ]{2,}ez|dites|faites)\b(?!-(?:vous|nous)\b)"
)
_VOUS_IMPERATIVE = re.compile(rf"{_STEP}{_VOUS_VERB}", re.MULTILINE | re.IGNORECASE)
#: …or a later sentence or clause («…, regardez la terminaison», «Prends l'infinitif
#: et enlevez -er»), unless it stands alone in a list of forms («aie, ayons, ayez.»,
#: «Prends ! Tournez !»).
_VOUS_IMPERATIVE_INSIDE = re.compile(
    rf"(?:[.!?;:,]|\b(?:et|ou|puis|mais|alors))[ \t]+{_VOUS_VERB}(?![ \t]*(?:[,.;!?/]|$))",
    re.MULTILINE | re.IGNORECASE,
)
#: «Demandez-vous», «Rappelez-vous» opening a sentence (not an inversion being taught).
_VOUS_REFLEXIVE = re.compile(
    rf"(?:{_STEP}|[.!?;][ \t]+)([A-Za-zÀ-ÿ]+ez-vous)\b(?![ \t]*(?:…|\?))", re.MULTILINE
)
#: «votre choix», «vos raisons» (not «notre/votre/leur», a series being taught).
_VOUS_POSSESSIVE = re.compile(r"(?<![/\w])(votre|vos)\b(?![ \t]*/)", re.IGNORECASE)
#: «vous voulez savoir»: vous as the subject of the card's own sentence, before any
#: colon (after a colon come the forms: «: nous avons, vous avez»).
_VOUS_SUBJECT = re.compile(r"\b(vous[ \t]+[a-zà-ÿ]+(?<!i)ez)\b(?![ \t]*(?:…|\?))", re.IGNORECASE)
_NOT_VERBS = {"chez", "assez", "nez", "rez"}


def _french_lines() -> list[tuple[str, str, str, str]]:
    """``(file, card, field, text)`` for every French learner-facing string of every card."""

    found: list[tuple[str, str, str, str]] = []

    def walk(node, card_id: str, where: str, path: Path) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("fr"), str) and ("en" in node or "de" in node):
                found.append((path.name, card_id, where, node["fr"]))
            for key, value in node.items():
                walk(value, card_id, f"{where}.{key}" if where else key, path)
        elif isinstance(node, list):
            for value in node:
                walk(value, card_id, f"{where}[]", path)

    for path in RULE_CARD_FILES:
        for card_id, card in json.loads(path.read_text(encoding="utf-8"))["cards"].items():
            walk(card, card_id, "", path)
    return found


def vous_address(text: str) -> list[str]:
    """The places where ``text`` addresses its reader with vous, mentions aside."""

    plain = _MENTIONED.sub(" ", text)
    # «1. Remplacez» opens a step and also follows «.»: one hit per place, not per pattern.
    imperatives = {
        m.start(1): m.group(1)
        for pattern in (_VOUS_IMPERATIVE, _VOUS_IMPERATIVE_INSIDE)
        for m in pattern.finditer(plain)
        if m.group(1).lower() not in _NOT_VERBS
    }
    hits = [imperatives[start] for start in sorted(imperatives)]
    hits +=[m.group(1) for m in _VOUS_REFLEXIVE.finditer(plain)]
    hits += [m.group(1) for m in _VOUS_POSSESSIVE.finditer(plain)]
    for sentence in re.split(r"[.!?;\n]", plain):
        hits += [m.group(1) for m in _VOUS_SUBJECT.finditer(sentence.split(":")[0])]
    return hits


def test_register_guard_tells_address_from_mention():
    for addressed in (
        "1. Remplacez chaque complément par son pronom.",
        "2. Rangez-les : me/te/nous/vous · le/la/les.",
        "Je ferai et je ferais se prononcent pareil : à l'écrit, regardez la terminaison.",
        "1. Demandez-vous : avant ou après ?",
        "Choisissez le mot selon ce que vous voulez savoir.",
        "Ajoute l'infinitif, dans l'ordre de votre choix.",
        "1. Dites la phrase : tu viens ce soir.",
        "3. Ne déplacez pas le verbe.",
        "1. Prends l'infinitif et enlevez -er : parler → parl-.",
        "Concède d'abord, puis réfutez : ta position vient en second.",
    ):
        assert vous_address(addressed), addressed
    for mentioned in (
        "1. Mets avoir au présent : j'ai, tu as, il a, nous avons, vous avez, ils ont.",
        "Je voudrais pour demander poliment ; vous voulez… ? pour proposer.",
        "Choisis la série : mon/ton/son, notre/votre/leur.",
        "« Avez-vous… ? » inverse le verbe et le sujet.",
        "D'autres formes polies : j'aimerais, pourriez-vous…",
        "Que nous parlions, que vous preniez : les mêmes formes qu'à l'imparfait.",
        "Quand on dit Madame ou Monsieur, on dit vous.",
        "Certaines formes servent aussi d'impératif (sois sage, ayez confiance).",
        "Après chez : moi, toi, lui, elle, nous, vous, eux, elles.",
        "Avoir a son propre impératif : aie, ayons, ayez.",
        "2. Enlève le pronom : Prends ! Tournez !",
        "3. Mets le verbe au subjonctif : viennes, finisse, preniez.",
    ):
        assert not vous_address(mentioned), mentioned


def test_rule_cards_say_tu():
    """Every French learner-facing line of every fr2 card addresses the learner with tu."""
    assert len(RULE_CARD_FILES) == 5
    slips = [
        f"{name} {card_id} {where}: {hits} in «{text}»"
        for name, card_id, where, text in _french_lines()
        for hits in [vous_address(text)]
        if hits
    ]
    per_file = {path.name: sum(s.startswith(path.name) for s in slips) for path in RULE_CARD_FILES}
    assert not slips, f"French rule-card text says vous to the learner {per_file}:\n" + "\n".join(slips)
