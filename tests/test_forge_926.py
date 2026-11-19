"""#926: «You arrived at the station» refused «Tu es arrivé» (walk 19 Nov 2026).

Item ``FR2_A21_PC_ETRE`` / ``pc-etre-end`` rendered «tu» as a woman: «Tu es arrivée
à la gare samedi dernier.» Its agreement trap is the masculine «Tu es arrivé», so the
key could not list the masculine (a key never accepts what the screen shows as
wrong), and the English said only «You arrived». English «I», «you», «we» name no
gender (and «you» no number): the trap was a right answer.

Root cause #174: an agreement trap is chosen by form alone. Now, when a person the
English allows would make one of the item's ✗ sentences, the English (and German)
names the item's own subject («You (a woman) arrived …»), so the trap is wrong for
what the learner is asked, and the key lists only the persons that name allows.
"""

from __future__ import annotations

import random
import re

from app.services import item_bank as ib

UNIT = "FR2_A21_PC_ETRE"

#: English pronouns that name no gender (and «you» no number).
_OPEN = {"I", "you", "we"}


def _named(english: str, pronoun: str) -> bool:
    """``english`` says which ``pronoun`` it means: «you (a woman)», «I (a man)», «you (plural)»."""

    flags = 0 if pronoun == "I" else re.IGNORECASE
    return re.search(rf"\b{pronoun}\b\s*\(", english, flags) is not None


def _walk_item() -> ib.BankItem:
    """The walk's exact item, served through the bank's own sampling path."""

    bank = ib.ItemBank()
    frame = next(f for f in bank.frames(UNIT) if f.frame_id == "pc-etre-end")
    lex = bank.lex
    arriver = lex.verbs["arriver"]
    station = next(comp for comp in arriver.get("comps") or [] if comp.get("fr") == "à la gare")
    bindings = {
        "S": next(entry for entry in lex.pool("pron") if entry.get("id") == "tu_f"),
        "V": arriver,
        "O": station,
        "T": next(entry for entry in lex.pool("time_past_end") if entry.get("fr") == "samedi dernier"),
    }
    bank.frames = lambda unit: [frame]  # type: ignore[method-assign]
    bank._bind = lambda *args, **kwargs: dict(bindings)  # type: ignore[method-assign]
    return next(bank.sample(UNIT, random.Random(926)))


def test_walk_item_tu_es_arrive():
    item = _walk_item()
    assert item.sentence == "Tu es arrivée à la gare samedi dernier."
    masculine = "Tu es arrivé à la gare samedi dernier."
    accepted = {ib.normalize(sentence) for sentence in item.accepted}
    shown_wrong = {ib.normalize(sentence) for sentence in item.wrong_sentences}
    if ib.normalize(masculine) in shown_wrong:
        # The trap stays only when the prompt rules the masculine out.
        assert re.match(r"You \(a woman\) arrived at the station", item.en), (
            f"«{masculine}» is shown as wrong, but the English «{item.en}» names no gender"
        )
        assert ib.normalize(masculine) not in accepted
    else:
        assert ib.normalize(masculine) in accepted, item.accepted
    # The repair card says the same meaning to the learner.
    repair = ib.transform_item(item)
    assert repair is not None
    assert repair["meaning"] == item.en


def test_named_woman_key():
    """Once the English says «you (a woman)», the key lists only what that allows:
    no masculine, no plural «Vous êtes arrivés»."""

    item = _walk_item()
    if not _named(item.en, "you"):
        # Unnamed, «you» is a man too: the masculine must then be right.
        assert ib.normalize("Tu es arrivé à la gare samedi dernier.") in {ib.normalize(s) for s in item.accepted}, item
        return
    for sentence in item.accepted:
        assert not re.search(r"\barrivés?\b(?!e)", sentence) or "arrivée" in sentence, item.accepted
        assert "arrivés" not in sentence and "arrivées" not in sentence, item.accepted


def _gender_and_number_twins(entry: dict) -> list[dict]:
    """The same French pronoun as another person the English allows: the other
    gender (je, tu, nous, vous), a polite «vous» to one person, «on» agreeing in
    the plural."""

    lex = ib.lexicon()
    twins = [other for other in lex.pool("pron") if other.get("fr") == entry.get("fr") and other.get("en") == entry.get("en")]
    if entry.get("fr") == "vous":
        twins += [{**other, "n": "s"} for other in twins]
    if entry.get("fr") == "on":
        twins += [{**other, "n": "p"} for other in twins]
    return [t for t in twins if (t.get("g"), t.get("n")) != (entry.get("g"), entry.get("n"))]


def test_open_subject_guard():
    """The done-when, on every unit: an item whose subject is je / tu / nous / on /
    vous never shows as ✗ a sentence that is right for another person the English
    allows, unless the English names its own («I (a woman)», «you (plural)»)."""

    bank = ib.default_bank()
    checked, offenders = 0, []
    for unit in ib.template_units():
        frames = {frame.frame_id: frame for frame in bank.frames(unit)}
        for item in bank.generate(unit, 40, seed="guard-926"):
            frame = frames[item.frame_id]
            bindings = dict(item.bindings)
            said = set(re.findall(r"[\wÀ-ÿ]+", item.sentence.casefold()))
            shown_wrong = {ib.normalize(sentence) for sentence in item.wrong_sentences}
            for slot, entry in bindings.items():
                english = entry.get("en")
                if "pron" not in (entry.get("tags") or []) or not isinstance(english, str) or english not in _OPEN:
                    continue
                if entry.get("fr") not in said:
                    continue
                checked += 1
                for twin in _gender_and_number_twins(entry):
                    try:
                        other = bank.render(frame, {**bindings, slot: twin}, alternatives=False)
                    except (ib.RenderError, KeyError, IndexError):
                        continue
                    if ib.normalize(other.sentence) in shown_wrong and not _named(item.en, entry["en"]):
                        offenders.append((unit, item.frame_id, item.en, item.sentence, other.sentence))
    assert checked > 200
    assert not offenders, f"{len(offenders)} items show a right answer as wrong, e.g. {offenders}"
