"""#780 (walk 14 Nov 2026): La Forge put plain «Sag auf Französisch» items under the beat's
character («Gus · vous»), even «Du bist 39 Jahre alt.», and asked a review item to
«Antworte … mit der Regel von heute».

* A «Say in French: "…"» task is a sentence the learner says to nobody (owner, 12 Nov):
  no one says a line to answer, so no character and no serial context go on it.
* An item that does carry a character agrees with its register on every line the learner
  reads or says (the cue's quoted line in their language, the model answer), not only on
  a French prompt.
* An item's cue is shared by every role the rule is posed in (new, due, contrast), so it
  never says «today's» rule.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.item_bank import BankItem, output_item, public_item

GUS_VOUS = {"id": "augustin_de_roncourt", "name": "Gus", "role": None, "register": "vous", "closeness": 1}
LILA_TU = {"id": "lila_bonnet", "name": "Lila", "role": None, "register": "tu", "closeness": 3}
REQUIREMENT = {"id": "rule", "label": "être"}
#: A French line that addresses nobody: it agrees with any badge.
NEUTRAL_LINE = "« Ce soir, il y a une fête au Mistral. »"


def _context(character: dict = GUS_VOUS) -> dict:
    return {
        "thread_id": "t",
        "episode_index": 1,
        "scene_context": "Au Mistral.",
        "opener": "…",
        "character": dict(character),
        "met": {character["id"]: {"id": character["id"], "name": character["name"], "relationship": {"register": character["register"]}}},
        "state": {},
    }


def _bank(unit: str, sentence: str, en: str, de: str, accepted: tuple[str, ...] = ()) -> BankItem:
    return BankItem(
        unit=unit,
        frame_id=f"{unit.lower()}-1",
        sentence=sentence,
        target=sentence.split()[1],
        traps=(),
        wrong_sentences=(),
        prefix="",
        suffix="",
        en=en,
        scene="",
        accepted=accepted or (sentence,),
        de=de,
    )


#: The walk's three items, as the bank serves them on the conversation rung.
WALK_ITEMS = [
    _bank("FR2_A11_ETRE", "Il est à la poste.", "He is at the post office.", "Er ist auf der Post."),
    _bank("FR2_A11_AVOIR", "Tu as trente-neuf ans.", "You are 39 years old.", "Du bist 39 Jahre alt."),
    _bank(
        "FR2_A11_ETRE",
        "Ils sont grands.",
        "They (all) are tall.",
        "Sie (alle) sind groß.",
        ("Ils sont grands.", "Elles sont grandes."),
    ),
]


def _served(payload: dict) -> dict:
    return payload["output_ladder"]["conversation"]["items"][0]


def _decorate(item: dict, character: dict = GUS_VOUS) -> dict:
    from app.api.v1.endpoints.atelier import _with_serial_conversation

    payload = {"output_ladder": {"conversation": {"items": [item]}}}
    return _served(_with_serial_conversation(payload, context=_context(character), concept=SimpleNamespace(id=1, name="être")))


@pytest.mark.parametrize("bank", WALK_ITEMS, ids=["etre", "avoir", "sie"])
def test_say_no_badge(bank: BankItem) -> None:
    item = output_item(bank, round_name="conversation", requirement=REQUIREMENT)
    assert item is not None and item["prompt"].startswith("Say in French:")
    served = _decorate(item)
    assert "character" not in served, f"«{bank.de}» is said to nobody, yet went out under {served.get('character')}"
    assert "serial_context" not in served


def test_line_keeps_badge() -> None:
    item = {
        "id": "turn-1",
        "prompt": '« Vous êtes à la poste ? » Reply in French: "Yes, I am at the post office."',
        "prompt_l10n": {"de": "« Vous êtes à la poste ? » Antworte auf Französisch: „Ja, ich bin auf der Post.“"},
        "example_answer": "Oui, je suis à la poste.",
    }
    served = _decorate(item)
    assert served["character"]["name"] == "Gus"
    assert served["character"]["register"] == "vous"
    assert served["serial_context"]["register"] == "vous"


@pytest.mark.parametrize(
    "item",
    [
        # The French line says vous, the learner's line says du: two different people.
        {
            "id": "turn-1",
            "prompt": '« Vous venez ce soir ? » Reply in French: "Are you coming too?"',
            "prompt_l10n": {"de": "« Vous venez ce soir ? » Antworte auf Französisch: „Kommst du auch?“"},
            "example_answer": "Tu viens aussi ?",
        },
        # The French line addresses nobody; the line the learner says (its German meaning
        # and its model answer) says du.
        {
            "id": "turn-2",
            "prompt": f'{NEUTRAL_LINE} Reply in French: "Are you coming too?"',
            "prompt_l10n": {"de": f"{NEUTRAL_LINE} Antworte auf Französisch: „Kommst du auch?“"},
            "meaning_l10n": {"en": "Are you coming too?", "de": "Kommst du auch?"},
            "example_answer": "Tu viens aussi ?",
        },
    ],
    ids=["vous-du", "none-du"],
)
def test_cue_register(item: dict) -> None:
    served = _decorate(item)
    assert "character" not in served, f"a tu line went out under {served.get('character')}"
    assert "serial_context" not in served


def test_reverse_register() -> None:
    item = {
        "id": "turn-3",
        "prompt": f'{NEUTRAL_LINE} Reply in French: "Are you coming too?"',
        "prompt_l10n": {"de": f"{NEUTRAL_LINE} Antworte auf Französisch: „Kommen Sie auch?“"},
        "example_answer": "Vous venez aussi ?",
    }
    assert "character" not in _decorate(item, LILA_TU)


def test_app_du() -> None:
    """«Antworte auf Französisch» is the app speaking to the learner, not the line."""

    item = {
        "id": "turn-4",
        "prompt": f'{NEUTRAL_LINE} Reply in French: "I am coming too."',
        "prompt_l10n": {"de": f"{NEUTRAL_LINE} Antworte auf Französisch, sag ihr, dass du auch kommst: „Ich komme auch.“"},
        "example_answer": "Je viens aussi.",
    }
    assert _decorate(item, GUS_VOUS)["character"]["name"] == "Gus"


@pytest.mark.parametrize("language", ["de", "en", "fr"])
@pytest.mark.parametrize("round_name", ["conversation", "sentence", "speak"])
def test_no_today(language: str, round_name: str) -> None:
    """The same stored item is posed on a review unit («Wiederholung · heute fällig»)."""

    item = output_item(WALK_ITEMS[0], round_name=round_name, requirement=REQUIREMENT)
    served = public_item(item, language, "de")
    texts = [served.get("instruction"), served.get("goal_native"), served.get("prompt")]
    texts += list((served.get("instruction_l10n") or {}).values())
    for text in filter(None, texts):
        assert not any(word in text for word in ("von heute", "today's", "rule of the day", "du jour")), text


def test_cached_cue() -> None:
    """A set stored before #780 still carries the old English instruction."""

    item = output_item(WALK_ITEMS[0], round_name="conversation", requirement=REQUIREMENT)
    item["instruction"] = "Reply in French, with today's rule."
    for language in ("en", "de", "fr"):
        served = public_item(item, language, "de")
        assert "today" not in served["instruction"] and "heute" not in served["instruction"], served["instruction"]
