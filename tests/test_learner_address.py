"""One register setting for how the app addresses the learner (#144, #106, #128).

German is «du», French is «tu» (owner decision, 14 Oct 2026). The app's own words —
server-written hints, mission goals, success signals, reasons, corrections, and the
prompts that ask a model to write for the learner — read that one setting
(:mod:`app.services.address`) instead of each choosing a pronoun in a string literal.

A character's own lines are a different thing: Gus says «vous» until the third
tentpole, Margaux says «tu» from the first night. ``character_register`` resolves that
once for every surface, so the scene and the Courrier cannot disagree about it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.address import (
    LEARNER_ADDRESS,
    address_instruction,
    character_register,
    learner_address,
)

APP = Path(__file__).resolve().parents[1] / "app"

#: Server modules whose French (``"fr"``) and German (``"de"``) strings are the app talking
#: to the learner. A character's line, an exercise sentence or a grammar example is not
#: in these tables (they live under ``opening_message``, ``quick_replies``, item banks).
SERVER_COPY_MODULES = (
    "services/learner_copy.py",
    "services/recommendation_reasons.py",
    "services/placement.py",
    "services/journey_contracts.py",
    "services/journey_planner.py",
    "services/journey_learning.py",
    "services/kept_words.py",
    "services/intake.py",
    "api/v1/endpoints/intake.py",
    "services/living_story.py",
    "services/missions.py",
)

#: Dict keys in ``missions.py`` that hold learner-facing prose (not a character's line).
MISSION_LEARNER_KEYS = frozenset(
    {
        "brief",
        "success_signal",
        "twist",
        "scene_anchor",
        "dispatch_note",
        "inbox_context",
        "channel_label",
        "contact_role",
        "title",
        "explain_plan",
        "news_summary",
        "travel_work",
        "conversation",
    }
)

_QUOTED = re.compile(r"«[^»]*»|“[^”]*”|„[^“”]*[“”]|`[^`]*`")
_FRENCH_ADDRESS = re.compile(
    r"\b(?:vous|votre|vos|dites|redites|faites|refaites)\b"
    r"|\b(?!chez\b|assez\b|nez\b|rez\b|rendez\b)[A-Za-zÀ-ÿ]{2,}ez\b",
    re.IGNORECASE,
)
_GERMAN_ADDRESS = re.compile(
    r"\b(?:Ihr|Ihre|Ihren|Ihrer|Ihrem|Ihres|Ihnen)\b"
    r"|\b[A-ZÄÖÜ][a-zäöüß]+(?:en|n) Sie\b"
    r"|\b(?:damit|dass|wenn|woher|wohin|ob|wo|was|wie|wann|warum|weil|sobald|falls|bevor|und|oder|aber"
    r"|haben|können|möchten|sind|werden|müssen|wollen|dürfen|sollen) Sie\b"
)


def _strings(node: ast.AST) -> list[tuple[int, str]]:
    """Every literal string below ``node`` (the constant parts of an f-string included)."""

    found: list[tuple[int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            found.append((child.lineno, child.value))
    return found


def _learner_strings(path: Path, *, keys: frozenset[str] | None = None) -> list[tuple[str, int, str, str]]:
    """``(file, line, language, text)`` for each ``"fr"``/``"de"`` (and ``keys``) dict value."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[str, int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=False):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            if key.value in {"fr", "de"}:
                language = key.value
            elif keys and key.value in keys and not isinstance(value, ast.Dict):
                language = "fr"
            else:
                continue
            for line, text in _strings(value):
                out.append((path.name, line, language, text))
    return out


#: Labels that *name* a form rather than address anyone («Conjugaison : vous avez»).
NAMED_FORMS = frozenset({"Conjugaison : vous avez"})


def _address_violations(language: str, text: str) -> list[str]:
    if text in NAMED_FORMS:
        return []
    stripped = _QUOTED.sub(" ", text)
    stripped = re.sub(r"s[’']il vous pla[iî]t|rendez-vous", " ", stripped, flags=re.IGNORECASE)
    pattern = _FRENCH_ADDRESS if language == "fr" else _GERMAN_ADDRESS
    return [match.group(0) for match in pattern.finditer(stripped)]


def test_the_setting_is_tu_and_du() -> None:
    assert dict(LEARNER_ADDRESS) == {"fr": "tu", "de": "du"}
    assert learner_address("fr") == "tu"
    assert learner_address("de") == "du"
    assert learner_address("de-DE") == "du"
    assert learner_address("en") is None


@pytest.mark.parametrize("module", SERVER_COPY_MODULES)
def test_server_text_addresses_the_learner_with_the_one_setting(module: str) -> None:
    """No «vous»/«votre»/imperative in -ez and no «Sie»/«Ihr» addressed to the learner.

    Quoted material («…», `…`, „…“) is exempt: it names a form (a grammar point, the
    politeness formula «s’il vous plaît»), it does not address anyone.
    """

    path = APP / module
    keys = MISSION_LEARNER_KEYS if path.name == "missions.py" else None
    offenders = [
        f"{name}:{line} [{language}] {text[:90]!r} -> {hits}"
        for name, line, language, text in _learner_strings(path, keys=keys)
        if (hits := _address_violations(language, text))
    ]
    assert not offenders, "learner-facing text uses the wrong register:\n" + "\n".join(offenders)


def test_the_scan_catches_what_it_is_meant_to() -> None:
    assert _address_violations("fr", "Dites qui vous êtes.") == ["Dites", "vous"]
    assert _address_violations("fr", "Ton niveau : réessaie.") == []
    assert _address_violations("fr", "Dis « vous » ou « tu », et « s’il vous plaît ».") == []
    assert _address_violations("de", "Beginnen Sie mit einer Begrüßung.") == ["Beginnen Sie"]
    assert _address_violations("de", "Ausgewählt, damit Sie die Wörter Ihrer Ausgabe anwenden.") == ["damit Sie", "Ihrer"]
    # «sie» as «she/they» and a sentence-initial «Sie» are not an address.
    assert _address_violations("de", "Samira weiß, ob sie etwas zurücklegen soll. Sie bleibt am Rand.") == []


def test_the_prompt_sentence_names_the_register() -> None:
    fr = address_instruction("fr")
    de = address_instruction("de")
    assert "«tu»" in fr and "vous" in fr  # names the form to use and the one to avoid
    assert "«du»" in de and "Sie" in de
    assert address_instruction("en") == ""


# ---------------------------------------------------------------------------
# Prompts read the setting (story, Courrier, corrections)
# ---------------------------------------------------------------------------


def test_the_story_brief_carries_the_register_note() -> None:
    from app.services import living_story

    note = living_story.learner_address(SimpleNamespace(address_preference="neutral"))["register_note"]
    assert note == address_instruction("fr")
    assert "«tu»" in note


def test_the_letter_writer_prompt_carries_the_register_note(monkeypatch) -> None:
    from app.db.models.user import User
    from app.services import missions

    captured: list[str] = []

    class _Llm:
        def generate_chat_completion(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            captured.append(str(kwargs.get("system_prompt") or ""))
            raise RuntimeError("stop after the prompt")

    monkeypatch.setattr(missions, "_safe_llm", lambda: _Llm())
    generator = missions.MissionGenerator.__new__(missions.MissionGenerator)
    generator.llm = None
    generator.db = None
    user = User(email="a@example.com", hashed_password="x", proficiency_level="A1", native_language="de")
    with pytest.raises(Exception):  # noqa: B017, PT011 - only the prompt matters here
        generator._llm_scenario(
            user=user,
            mission_type="message",
            concepts=[],
            vocabulary=[],
            variety={},
            recent_variety=[],
        )
    assert captured, "the letter writer was never given a system prompt"
    assert address_instruction("fr") in captured[0]


def test_the_correction_prompt_follows_the_explanation_language_register() -> None:
    from app.services.atelier import AtelierCorrectionService

    service = AtelierCorrectionService.__new__(AtelierCorrectionService)
    service.explanation_language = "de"
    assert address_instruction("de") in service._explanation_language_instruction()
    service.explanation_language = "fr"
    assert address_instruction("fr") in service._explanation_language_instruction()


# ---------------------------------------------------------------------------
# A character's register: one resolver for the scene and the Courrier
# ---------------------------------------------------------------------------


def test_a_recorded_relationship_wins() -> None:
    state = {"relationships": {"romy_tremblay": {"register": "tu"}, "margaux_barman": {"register": "vous"}}}
    assert character_register(state, "romy_tremblay") == "tu"
    assert character_register(state, "margaux_barman") == "vous"


def test_the_landlord_and_the_office_stay_vous() -> None:
    state = {"relationships": {"landlord_marchand": {"register": "tu"}, "office_clerk": {"register": "tu"}}}
    assert character_register(state, "landlord_marchand") == "vous"
    assert character_register(state, "office_clerk") == "vous"


def test_an_unrecorded_character_without_a_season_is_vous() -> None:
    assert character_register({}, "margaux_barman") == "vous"
    assert character_register(None, "") == "vous"


def test_an_unrecorded_character_speaks_as_the_season_opens_them(monkeypatch) -> None:
    """Margaux is «tu» in season 1 from the first night. The scene read that; the Courrier
    read only the relationship map, found no row yet, and wrote her «vous»."""

    from app.config import settings

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    assert character_register({}, "margaux_barman") == "tu"
    assert character_register({}, "romy_tremblay") == "tu"
    assert character_register({}, "augustin_de_roncourt") == "vous"  # «vous» until T3
    assert character_register({}, "landlord_marchand") == "vous"
    # What the story recorded still wins over the season's opening.
    state = {"relationships": {"margaux_barman": {"register": "vous"}}}
    assert character_register(state, "margaux_barman") == "vous"


def test_the_courrier_and_the_scene_agree_on_margaux(monkeypatch) -> None:
    from app.config import settings
    from app.services import story_correspondence as courrier
    from app.services.missions import MissionScheduler

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    thread = SimpleNamespace(state={}, world_bible={})
    assert courrier.learner_register(thread, "margaux_barman") == "tu"
    assert MissionScheduler._serial_register_for_character(thread=thread, character_id="margaux_barman").startswith("tu")
    letter = missions_first_letter(thread)
    assert "Tu as oublié ton écharpe" in letter["opening_message"]
    assert "Réponds" in letter["brief"]


def missions_first_letter(thread):  # noqa: ANN001
    from app.services import story_correspondence as courrier
    from app.services.missions import first_letter_for

    user = SimpleNamespace(cefr_estimate="A1", proficiency_level="A1")
    register = courrier.learner_register(thread, "margaux_barman")
    return first_letter_for(user, register=register, band="A1")


def test_the_courrier_tone_check_reads_the_resolved_register_not_the_rules_prose() -> None:
    """«Reformulez plus poliment» was answered to a «tu» reply because the check guessed the
    register from the words of ``realism_rules``; it now reads the register the
    correspondent actually has."""

    from app.services.missions import MissionConversationService

    service = MissionConversationService.__new__(MissionConversationService)
    text = "Salut ! Je passe demain vers 18 heures, tu es là ? Merci pour l'écharpe."
    informal = SimpleNamespace(
        prompt_payload={
            "target_register": "tu / warm informal",
            "messenger": {"realism_rules": ["Keep it polite and formal."]},
        },
        stakes_level=1,
    )
    assert service.branch_state(mission=informal, user_text=text, assistant_text="")["tone_ok"] is True

    formal = SimpleNamespace(
        prompt_payload={
            "target_register": "vous / polite formal",
            "messenger": {"realism_rules": ["Casual, warm."]},
        },
        stakes_level=1,
    )
    assert service.branch_state(mission=formal, user_text=text, assistant_text="")["tone_ok"] is False
