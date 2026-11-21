"""#747: a Courrier character keeps one register and writes correct French.

Live walk 13 Nov 2026, Courrier «Le déjeuner au bureau»: Nina («ta collègue») opens
with «Tu as la commande ?», then replies «mais que allons-nous prendre ? Avez-vous
une idée ?» and «Que diriez-vous d'une sandwich au poulet ou d'une salade ?». The
hint under her letter says «la serviette est restée chez Nina» while her own line
says «ma serviette est au travail».

No model calls: every test feeds the exact lines from the issue to the deterministic
guards, or drives the existing Courrier code with a scripted writer.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

NINA_LETTER = "Salut ! Tu as la commande ? J'ai faim, et ma serviette est au travail 😅"
NINA_HINT = "La commande est au travail, mais la serviette est restée chez Nina."
#: What a variety letter stores when its domain has no «tu»/«vous» (missions.py).
VARIETY_REGISTER = "natural French; formal only when the scenario requires it"
NINA_REPLY_1 = (
    "D'accord, pas de problème. On peut manger ensemble, mais que allons-nous prendre ? "
    "Avez-vous une idée ?"
)
NINA_REPLY_2 = (
    "Un dinosaure dans le métro ? C'est incroyable ! Mais revenons à notre déjeuner. "
    "Que diriez-vous d'une sandwich au poulet ou d'une salade ?"
)
GOOD_REPLY = "D'accord ! Tu prends un sandwich ou une salade ?"


class _ReplyLlm:
    def __init__(self, drafts: list[str]) -> None:
        self.drafts, self.systems, self.contexts = drafts, [], []

    def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
        self.systems.append(kwargs["system_prompt"])
        self.contexts.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(content=self.drafts.pop(0))


def _nina(monkeypatch, drafts: list[str]):
    from app.services import missions

    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    monkeypatch.setattr(missions, "_learner_level_code", lambda db, user: "A1")
    mission = SimpleNamespace(
        id=None,
        title="Le déjeuner au bureau",
        brief="Nina a faim.",
        prompt_payload={
            "messenger": {
                "contact_name": "Nina",
                "contact_role": "ta collègue",
                "opening_message": NINA_LETTER,
                "twist": NINA_HINT,
            },
            "target_register": VARIETY_REGISTER,
        },
        source_snapshot={},
        turns=[],
        attempts=[],
        stakes_level=1,
        mission_type="message",
    )
    llm = _ReplyLlm(drafts)
    return missions.MissionConversationService(db=None, llm_service=llm), llm, mission


# ---------------------------------------------------------------------------
# Register: fixed per character, by the character's own first words
# ---------------------------------------------------------------------------


def test_ninas_vous_reply_to_a_tu_letter_is_rewritten(monkeypatch) -> None:
    service, llm, mission = _nina(monkeypatch, [NINA_REPLY_1, GOOD_REPLY])
    answer = service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="On mange ensemble ?")
    assert answer == GOOD_REPLY, "Nina's «Avez-vous une idée ?» to a tu colleague was shown"
    assert len(llm.systems) == 2
    assert "«tu»" in llm.systems[1]


def test_the_actor_is_told_the_register_of_its_own_letter(monkeypatch) -> None:
    """The actor was handed «formal only when the scenario requires it», and chose vous."""

    service, llm, mission = _nina(monkeypatch, [GOOD_REPLY])
    service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="On mange ensemble ?")
    assert "tu / registre familier" in llm.contexts[0]
    assert VARIETY_REGISTER not in llm.contexts[0]


def test_ninas_second_reply_is_rewritten_too(monkeypatch) -> None:
    service, llm, mission = _nina(monkeypatch, [NINA_REPLY_2, GOOD_REPLY])
    answer = service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Un dinosaure !")
    assert answer == GOOD_REPLY
    hint = llm.systems[1]
    assert "«tu»" in hint and "sandwich" in hint


def test_the_plain_acknowledgement_keeps_the_letters_tu(monkeypatch) -> None:
    service, _llm, mission = _nina(monkeypatch, [NINA_REPLY_1, NINA_REPLY_1])
    answer = service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Oui")
    assert "ton message" in answer


# ---------------------------------------------------------------------------
# The French itself: elision and the gender of a known noun
# ---------------------------------------------------------------------------


def test_que_before_a_vowel_is_caught() -> None:
    from app.services.letter_voice import voice_problems

    problems = voice_problems(
        ["On peut manger ensemble, mais que allons-nous prendre ? Tu as une idée ?"], register="tu", level="A1"
    )
    assert any("qu'allons" in problem for problem in problems), problems


@pytest.mark.parametrize(
    ("line", "fix"),
    [
        ("Je ai faim.", "J'ai"),
        ("Il ne est pas là.", "n'est"),
        ("Elle se appelle Nina.", "s'appelle"),
        ("Je le ai vu.", "l'ai"),
        ("C'est la amie de Paul.", "l'amie"),
        ("Un verre de eau, merci.", "d'eau"),
        ("Je viens si il pleut.", "s'il"),
    ],
)
def test_other_missing_elisions_are_caught(line: str, fix: str) -> None:
    from app.services.letter_voice import voice_problems

    problems = voice_problems([line], register="tu", level="A1")
    assert any(fix in problem for problem in problems), problems


def test_une_sandwich_is_caught() -> None:
    from app.services.letter_voice import voice_problems

    problems = voice_problems(
        ["Que dirais-tu d'une sandwich au poulet ou d'une salade ?"], register="tu", level="A1"
    )
    assert any("un sandwich" in problem for problem in problems), problems


def test_un_salade_is_caught() -> None:
    from app.services.letter_voice import voice_problems

    assert any("une salade" in p for p in voice_problems(["Je prends un salade."], register="tu", level="A1"))


@pytest.mark.parametrize(
    "line",
    [
        GOOD_REPLY,
        NINA_LETTER,
        "Je crois que oui.",
        "Donne-le à Marie, et dis-le-moi.",
        "Tu as vu la une du journal ?",
        "Le onze, je suis libre.",
        "Elle est médecin : une médecin très calme.",
        "C'est une enfant très sage, et une élève sérieuse.",
        "On se voit un après-midi, ou une après-midi, comme tu veux.",
        "Il était une fois un chat.",
        "J'en ai un aussi. Un à un, ils arrivent.",
        "Tu veux un livre ou une livre de pommes ?",
        "Un tour en ville ? La tour est belle.",
        "Je prends un crème au café.",
        "Quelqu'un a un plan ?",
        "Le yaourt est dans le frigo.",
        "Elle était là. Je pense qu'il est là, et lorsque il pleut on reste.",
    ],
)
def test_correct_french_is_never_flagged(line: str) -> None:
    from app.services.letter_voice import voice_problems

    assert voice_problems([line], register="tu", level="A1") == []


# ---------------------------------------------------------------------------
# The hint under the letter never contradicts the letter
# ---------------------------------------------------------------------------


def _stored_nina():
    from app.db.models.mission import RealWorldMission

    mission = RealWorldMission(
        id=uuid4(),
        user_id=uuid4(),
        cadence="ad_hoc",
        mission_type="message",
        title="Le déjeuner au bureau",
        brief="Nina a faim.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[],
        prompt_payload={
            "messenger": {"contact_name": "Nina", "opening_message": NINA_LETTER, "twist": NINA_HINT},
            "variety": {"twist": NINA_HINT},
            "slim_payload": {"twist": NINA_HINT},
        },
        recap_payload={},
        status="in_progress",
    )
    mission.created_at = datetime(2026, 11, 13, 4, 0, 0)
    mission.turns = []
    mission.attempts = []
    return mission


def test_the_stored_hint_that_contradicts_ninas_line_is_not_served() -> None:
    from app.services.missions import serialize_mission

    mission = _stored_nina()
    payload = serialize_mission(mission)["prompt_payload"]
    assert not payload["messenger"].get("twist"), payload["messenger"].get("twist")
    assert not payload["variety"].get("twist")
    assert not payload["slim_payload"].get("twist")
    # The stored letter is untouched: the filter runs on every read.
    assert mission.prompt_payload["messenger"]["twist"] == NINA_HINT


def test_a_hint_that_agrees_with_the_letter_is_served() -> None:
    from app.services.missions import serialize_mission

    mission = _stored_nina()
    agreeing = "La commande est au travail, et la serviette aussi."
    mission.prompt_payload = {
        **mission.prompt_payload,
        "messenger": {"contact_name": "Nina", "opening_message": NINA_LETTER, "twist": agreeing},
        "variety": {"twist": agreeing},
    }
    payload = serialize_mission(mission)["prompt_payload"]
    assert payload["messenger"]["twist"] == agreeing
    assert payload["variety"]["twist"] == agreeing


def test_the_letter_writer_is_told_when_its_hint_moves_a_thing(monkeypatch) -> None:
    import json

    from app.db.models.user import User
    from app.services import missions

    payloads: list[dict] = []

    def draft(twist: str) -> str:
        return json.dumps(
            {
                "title": "Le déjeuner au bureau",
                "brief": "Réponds à Nina.",
                "contact_name": "Nina",
                "opening_message": NINA_LETTER,
                "twist": twist,
                "success_signal": "Nina sait quoi manger.",
                "success_signal_en": "Nina knows what to eat.",
                "success_signal_de": "Nina weiß, was sie isst.",
            }
        )

    drafts = [draft(NINA_HINT), draft("La commande est au travail, mais Nina a oublié son ticket.")]

    class _Llm:
        def generate_chat_completion(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            payloads.append(json.loads(messages[0]["content"]))
            return SimpleNamespace(content=drafts.pop(0))

    monkeypatch.setattr(missions, "_safe_llm", lambda: _Llm())
    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    generator = missions.MissionGenerator.__new__(missions.MissionGenerator)
    generator.llm = None
    generator.db = None
    monkeypatch.setattr(generator, "_letter_known_words", lambda user: None)
    user = User(email="a@example.com", hashed_password="x", proficiency_level="A1", native_language="en")
    scenario = generator._llm_scenario(
        user=user, mission_type="message", concepts=[], vocabulary=[], variety={}, recent_variety=[]
    )
    assert len(payloads) == 2, "the hint that moves Nina's napkin was accepted"
    assert "serviette" in payloads[1]["rewrite_because"]
    assert scenario is not None and "ticket" in scenario["messenger"]["twist"]


def test_the_authored_letters_pass_the_same_checks() -> None:
    """Every letter the Courrier ships with passes the checks its writers are held to."""

    from app.services import missions
    from app.services.letter_voice import contradicted_things, voice_problems

    for variety in missions.REAL_WORLD_MISSION_DOMAINS:
        lines = [variety.get("scene_anchor"), variety.get("opening_message"), variety.get("twist")]
        assert voice_problems(lines, register=None, level=None) == [], variety["domain"]
        assert contradicted_things(variety.get("opening_message"), variety.get("twist")) == [], variety["domain"]
