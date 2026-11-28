"""#1087: La Forge's «Tu ___ chaud ce soir ?» had no German meaning.

Walk of 26 Nov 2026 (`a1-de-fresh`, La Forge on Avoir): the two-choice item
«___ chaud ce soir ?» («Tu es» / «Tu as») came with ``meaning_l10n`` = ``{"en": …}``
only. A German speaker is exactly the learner who falls into «Tu es chaud» («Bist du
…»), and he got no German line to read the meaning from.

The bank could not say it: «avoir chaud» is «mir ist heiß», a body feeling whose
experiencer stands in the dative and whose verb is an impersonal «ist». ``g_cl``
only built nominative-subject clauses, ``lexicon_de.json`` left «chaud» out of the
pool it authors, and ``render_german`` turned the missing German into ``None``,
which the quality gate tolerates (two items per unit).
"""
from __future__ import annotations

import pytest

from app.services import item_bank as ib

UNIT = "FR2_A11_AVOIR"


def _entry(pool: str, key: str) -> dict:
    return next(entry for entry in ib.lexicon().pools[pool] if entry.get("id") == key)


def _render(frame_id: str, subject: str, state: str = "chaud") -> str | None:
    bank = ib.default_bank()
    frame = next(frame for frame in bank.frames(UNIT) if frame.frame_id == frame_id)
    return bank.render_german(frame, {"S": _entry("pron", subject), "H": _entry("avoir_state", state)})


def test_walk_item():
    """The walk's item «Tu as chaud ce soir ?» means «Ist dir heute Abend heiß?»."""

    assert _render("avoir-state-q", "tu_m") == "Ist dir heute Abend heiß?"
    assert _render("avoir-state-q", "vous_f") == "Ist euch heute Abend heiß?"


@pytest.mark.parametrize(
    ("subject", "german"),
    [
        ("je_m", "Mir ist heute Abend heiß."),
        ("il", "Ihm ist heute Abend heiß."),
        ("elle", "Ihr ist heute Abend heiß."),
        ("on", "Uns ist heute Abend heiß."),
        ("nous_f", "Uns ist heute Abend heiß."),
        # A capital «Ihnen» reads as the polite «you»; the plural is named, as for «Sie (alle)».
        ("ils", "Ihnen (allen) ist heute Abend heiß."),
        ("elles", "Ihnen (allen) ist heute Abend heiß."),
    ],
    ids=lambda value: value.split("_")[0] if " " not in value else "",
)
def test_dative(subject, german):
    """Every person feels hot in the dative («avoir-state» frame)."""

    assert _render("avoir-state", subject) == german


def test_others():
    assert _render("avoir-state-q", "tu_m", "faim") == "Hast du heute Abend Hunger?"
    assert _render("avoir-state", "je_m", "froid") == "Ich friere heute Abend."


def test_bank():
    """The prompt the learner sees (``meaning_l10n``) carries German for every «chaud»
    item, the one said to someone as well («…, Marin ?» loses its address)."""

    bank = ib.default_bank()
    items = bank.generate(UNIT, 400, seed="forge-1087", detector=ib.unit_detector(UNIT))
    chaud = [item for item in items if dict(item.bindings).get("H", {}).get("id") == "chaud"]
    assert len(chaud) >= 4, "the sample has no «chaud» item to check"
    for item in chaud:
        posed = ib.without_vocative(item) or item
        meaning = ib._meaning_l10n(posed).get("meaning_l10n") or {}
        german = meaning.get("de")
        assert german, f"«{posed.sentence}» has no German meaning: {meaning}"
        assert "heiß" in german and german.split()[0].strip(",") not in {"Ich", "Du", "Bist", "Wir", "Seid", "Er", "Sie"}, german
        assert ib.german_problems(posed) == [], (posed.de, ib.german_problems(posed))


def test_calque():
    """«Bist du heute Abend heiß?» is «are you sexy tonight?»: the gate refuses it."""

    from app.services.item_bank_de import german_violations

    for wrong in ("Bist du heute Abend heiß?", "Ich bin heute Abend kalt.", "Wir sind heiß."):
        assert any("dative" in problem for problem in german_violations(wrong)), wrong
    for right in ("Ist dir heute Abend heiß?", "Mir ist kalt.", "Die Suppe ist heiß.", "Ich bin müde."):
        assert german_violations(right) == [], right
    # The dative «Ihr ist heiß» is right, the plural «Ihr ist müde» still wrong (review on #1116).
    from app.services.item_bank_de import AUX, _finite_forms

    finite = _finite_forms([AUX["sein"]])
    assert german_violations("Ihr ist heute Abend heiß.", finite=finite) == []
    assert any("does not agree" in problem for problem in german_violations("Ihr ist müde.", finite=finite))
    # Two sentences, one wrong: the gate names the wrong one (no own sentence split, #896).
    assert any("Bist du heiß" in problem for problem in german_violations("Mir ist kalt. Bist du heiß?"))


def test_pools():
    """The structural guard: a pool ``lexicon_de.json`` gives German to has German for
    each of its entries, so a word added to the French pool cannot lose its German
    meaning in silence (the 2 % the rendering gate tolerates hid «chaud»)."""

    import json

    overlay = json.loads((ib.TEMPLATE_DIR / "lexicon_de.json").read_text(encoding="utf-8"))
    lexicon = ib.lexicon()
    missing = [
        (pool, entry.get("fr"))
        for pool, table in (overlay.get("pools") or {}).items()
        for entry in lexicon.pools.get(pool) or []
        if entry.get("id") not in table and entry.get("fr") not in table
    ]
    assert missing == []


def test_voc():
    """«Ils ont chaud ce soir, Lila.» → «Lila, ihnen ist heute Abend heiß.» (the #384 rule
    for «Sie», in the dative)."""

    bank = ib.default_bank()
    frame = next(frame for frame in bank.frames(UNIT) if frame.frame_id == "avoir-state~voc")
    lila = next(entry for entry in ib.lexicon().pools["subj"] if entry.get("id") == "lila")
    german = bank.render_german(frame, {"S": _entry("pron", "ils"), "H": _entry("avoir_state", "chaud"), "VOC": lila})
    assert german == "Lila, ihnen ist heute Abend heiß."
