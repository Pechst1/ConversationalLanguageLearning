"""#730: the Cahier's x-ray box («Der Satz unter der Lupe») speaks the learner's language.

The marks of a unit's x-ray sentence come from the catalogue column ``xray_marks``
(``token=>role=>note``), which was authored once, in English. Every other learner-facing
field of a unit has a German and a French twin (``name_de`` / ``name_fr``,
``rule_short_de`` / ``rule_short_fr``); the marks had none, so a German A1 learner read
«Subject verb · je takes suis» under German chrome. Root cause #522: stored learner-facing
text with no locale contract.

The contract now: the catalogue carries ``xray_marks_de`` / ``xray_marks_fr`` (same tokens,
a role label in words and a note), ``unit_xray`` serves each mark's ``label`` and ``note``
as ``{en, de, fr}`` blocks, and the client draws the box only in a language every mark has
text in (``web-frontend/lib/rule-card.test.js``).
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.grammar_catalog import FRENCH_CORE_CATALOG_V2_VERSION, catalog_rows
from app.services.grammar_map import unit_xray

LEVELS = ("A1", "A2", "B1", "B2", "C1")


def _units() -> list[tuple[str, SimpleNamespace]]:
    return [
        (row["external_id"], SimpleNamespace(external_id=row["external_id"], source_refs=row["source_refs"]))
        for row in catalog_rows(FRENCH_CORE_CATALOG_V2_VERSION)
        if row["level"] in LEVELS
    ]


def _problems(unit_id: str, xray: dict) -> list[str]:
    problems: list[str] = []
    for mark in xray["marks"]:
        label = mark.get("label") if isinstance(mark.get("label"), dict) else {}
        note = mark.get("note") if isinstance(mark.get("note"), dict) else {}
        english_note = str(note.get("en") or mark.get("explanation") or "").strip()
        for language in ("de", "fr"):
            role_text = str(label.get(language) or "").strip()
            note_text = str(note.get(language) or "").strip()
            where = f"{unit_id} «{mark['token']}» ({language})"
            if not role_text:
                problems.append(f"{where}: no role label, the client shows the key «{mark.get('role')}»")
            elif "_" in role_text:
                problems.append(f"{where}: the role label is a key «{role_text}»")
            if not note_text:
                problems.append(f"{where}: no note, the English one is «{english_note}»")
            elif note_text == english_note:
                problems.append(f"{where}: the note is the English one «{note_text}»")
    return problems


def test_every_mark_served_for_de_and_fr_has_localized_text() -> None:
    units = _units()
    assert len(units) > 150, "the v2 catalogue walks A1 to C1"
    problems: list[str] = []
    served = 0
    for unit_id, concept in units:
        xray = unit_xray(concept)
        if xray is None:
            continue
        served += 1
        problems.extend(_problems(unit_id, xray))
    assert served == len(units), "every v2 unit has an x-ray sentence"
    assert not problems, f"{len(problems)} marks without German/French text, e.g.\n" + "\n".join(problems[:6])


def test_the_walk_units_say_it_in_german_and_french() -> None:
    by_id = dict(_units())
    for unit_id, english in (("FR2_A11_ETRE", "je takes suis"), ("FR2_A11_AVOIR", "age takes avoir, not être")):
        xray = unit_xray(by_id[unit_id])
        assert xray is not None
        mark = xray["marks"][0]
        note = mark.get("note") or {}
        for language in ("de", "fr"):
            assert note.get(language) and note[language] != english, f"{unit_id} ({language}) reads «{english}»: {mark}"
            assert (mark.get("label") or {}).get(language), f"{unit_id} ({language}) shows the key «{mark['role']}»"
        assert note.get("en") == english, mark
