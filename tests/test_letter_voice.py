"""#117: Courrier notes keep one address form per character and the learner's band.

No model calls: every test feeds the exact lines from the issue (or a plain-French
negative) to the deterministic guard, or drives the existing Courrier code with a
scripted writer.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

MARIN_LETTER = (
    "Salut, c'est Marin Lévêque. Je pense encore à notre dernière rencontre. "
    "Et toi, tu en penses quoi ?"
)
MARIN_PS = "Sur la photo, la porte est bleue. Votre porte est verte."
MARIN_REPLY = (
    "Ah, je comprends mieux maintenant ! La commande concerne le poisson que j'avais prévu pour Bruno, "
    "mais il semble qu'il y ait eu un malentendu. Donc, tu es bien au-dessus du café d'Odile. "
    "Peux-tu vérifier si tu as reçu un avis de livraison par erreur ?"
)
WALK_14_OCT = [
    "j'espère que Bruno ne sera pas trop agité",
    "ça ne prendra pas trop de temps à réparer",
]
#: Ordinary A1 French the guard must never touch (reviewer's notes on attempt 1).
PLAIN_A1 = [
    "Je pense qu'ils viennent demain.",
    "Je crois qu'ils prennent le bus.",
    "Marie dit qu'ils partent à huit heures.",
    "Elle dit qu'elles viennent.",
    "Ils doivent travailler.",
    "Il était fatigué.",
    "C'était fermé.",
    "J'étais occupé hier.",
    "Il était pressé.",
    "Il était né à Paris.",
    "Elle était contente.",
    "J'avais faim. Il avait chaud.",
    "Salut ! Il est ici. Tu viens demain ? Elle a mangé. Je pense à toi.",
    "Ils sont allés au café. Nous avons pris le train.",
]


# ---------------------------------------------------------------------------
# The guard itself
# ---------------------------------------------------------------------------


def test_letter_mixing_tu_and_vous_is_caught() -> None:
    from app.services.letter_voice import voice_problems

    problems = voice_problems([MARIN_LETTER, MARIN_PS], register="tu", level="A1")
    assert any("both" in problem for problem in problems)


def test_letter_mixing_is_caught_even_when_register_is_unknown() -> None:
    from app.services.letter_voice import voice_problems

    assert voice_problems([MARIN_LETTER, MARIN_PS], register=None, level=None)


def test_wrong_register_for_the_character_is_caught() -> None:
    from app.services.letter_voice import voice_problems

    assert voice_problems(["Vous avez oublié votre écharpe."], register="tu", level="A1")
    assert voice_problems(["Tu as oublié ton écharpe."], register="vous", level="A1")
    assert not voice_problems(["Tu as oublié ton écharpe."], register="tu", level="A1")


def test_the_issue_reply_is_above_a1() -> None:
    from app.services.letter_voice import above_band_tenses

    assert above_band_tenses(MARIN_REPLY, "A1") == ["plus-que-parfait", "subjonctif"]
    assert above_band_tenses(MARIN_REPLY, "A2") == ["plus-que-parfait", "subjonctif"]
    assert above_band_tenses(MARIN_REPLY, "B1") == []


def test_the_future_is_above_a1_only() -> None:
    from app.services.letter_voice import above_band_tenses

    for line in WALK_14_OCT:
        assert above_band_tenses(line, "A1") == ["futur simple"]
        assert above_band_tenses(line, "A2") == []


@pytest.mark.parametrize("line", PLAIN_A1)
def test_plain_a1_french_is_never_flagged(line: str) -> None:
    """The indicative present of «venir/prendre/partir/devoir» in the 3rd person plural
    is spelt like the subjunctive, and «était fatigué» is an adjective, not a pluperfect."""

    from app.services.letter_voice import voice_problems

    assert voice_problems([line], register="tu", level="A1") == []


@pytest.mark.parametrize(
    "line",
    [
        "Elle était partie.",
        "Il était déjà arrivé.",
        "Ils n'étaient pas rentrés.",
        "Elle s'était trompée.",
        "Je m'étais levé tôt.",
        "Nous nous étions perdus.",
        "J'avais oublié ton nom.",
        "Il n'avait pas prévu ça.",
    ],
)
def test_real_plus_que_parfait_is_flagged(line: str) -> None:
    from app.services.letter_voice import above_band_tenses

    assert above_band_tenses(line, "A1") == ["plus-que-parfait"]


@pytest.mark.parametrize(
    "line",
    [
        "Il faut qu'il y ait de la place.",
        "Je veux que tu viennes.",
        "Je veux qu'il vienne.",
        "J'espère qu'ils soient là.",
        "Il faut qu'ils fassent attention.",
        "Je veux qu'elles puissent venir.",
        "Pour que vous sachiez.",
    ],
)
def test_unambiguous_subjunctive_is_flagged(line: str) -> None:
    from app.services.letter_voice import above_band_tenses

    assert "subjonctif" in above_band_tenses(line, "A1")


def test_register_word() -> None:
    from app.services.letter_voice import register_word

    assert register_word("tu / warm informal") == "tu"
    assert register_word("vous / polite formal") == "vous"
    assert register_word("polite neutral") is None


# ---------------------------------------------------------------------------
# The wiring: the letter writer, the story-born letter, the reply
# ---------------------------------------------------------------------------


def _generator():
    from app.services import missions

    generator = missions.MissionGenerator.__new__(missions.MissionGenerator)
    generator.llm = None
    generator.db = None
    return generator


def test_a_story_born_letter_drops_a_ps_that_contradicts_its_opening() -> None:
    """Marin writes «tu» in the opening and «Votre porte est verte» in the P.S."""

    generator = _generator()
    context = {
        "relationship": "marin",
        "character_name": "Marin Lévêque",
        "register": "tu",
        "scenario": "La porte bleue.",
        "summary_fr": "La porte.",
    }
    messenger = {
        "contact_name": "Marin Lévêque",
        "opening_message": MARIN_LETTER,
        "twist": MARIN_PS,
        "success_signal_i18n": {"fr": "Marin sait ce que tu en penses."},
    }
    _title, _brief, story_messenger, _objectives = generator._story_born_mission(
        title="Un mot de Marin", brief="", messenger=messenger, custom_context=context
    )
    assert not story_messenger.get("twist"), story_messenger.get("twist")
    # A consistent P.S. is kept.
    messenger["twist"] = "Sur la photo, la porte est bleue. Ta porte est verte."
    _title, _brief, story_messenger, _objectives = generator._story_born_mission(
        title="Un mot de Marin", brief="", messenger=messenger, custom_context=context
    )
    assert story_messenger["twist"] == messenger["twist"]


def test_the_letter_writer_is_told_why_a_mixed_draft_was_refused(monkeypatch) -> None:
    from app.db.models.user import User
    from app.services import missions

    payloads: list[dict] = []

    def draft(opening: str, twist: str) -> str:
        return json.dumps(
            {
                "title": "Un mot de Marin",
                "brief": "Réponds à Marin.",
                "contact_name": "Marin Lévêque",
                "opening_message": opening,
                "twist": twist,
                "success_signal": "Marin sait ce que tu en penses.",
                "success_signal_en": "Marin knows what you think.",
                "success_signal_de": "Marin weiß, was du denkst.",
            }
        )

    drafts = [draft(MARIN_LETTER, MARIN_PS), draft(MARIN_LETTER, "La porte est bleue. Ta porte est verte.")]

    class _Llm:
        def generate_chat_completion(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            payloads.append(json.loads(messages[0]["content"]))
            return SimpleNamespace(content=drafts.pop(0))

    monkeypatch.setattr(missions, "_safe_llm", lambda: _Llm())
    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    generator = _generator()
    monkeypatch.setattr(generator, "_letter_known_words", lambda user: None)
    user = User(email="a@example.com", hashed_password="x", proficiency_level="A1", native_language="en")
    scenario = generator._llm_scenario(
        user=user,
        mission_type="message",
        concepts=[],
        vocabulary=[],
        variety={},
        recent_variety=[],
        story_context={"character_name": "Marin Lévêque", "register": "tu", "scenario": "La porte."},
    )
    assert len(payloads) == 2, "the mixed draft was accepted at the first attempt"
    assert "«tu» and «vous»" in payloads[1]["rewrite_because"]
    assert scenario is not None and "Ta porte" in scenario["messenger"]["twist"]


class _ReplyLlm:
    def __init__(self, drafts: list[str]) -> None:
        self.drafts, self.systems = drafts, []

    def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
        self.systems.append(kwargs["system_prompt"])
        return SimpleNamespace(content=self.drafts.pop(0))


def _reply_service(monkeypatch, drafts: list[str], level: str = "A1"):
    from app.services import missions

    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    monkeypatch.setattr(missions, "_learner_level_code", lambda db, user: level)
    mission = SimpleNamespace(
        id=None,
        title="t",
        brief="b",
        prompt_payload={
            "messenger": {"contact_name": "Marin", "register": "tu / warm informal", "opening_message": "Salut !"}
        },
        source_snapshot={},
        turns=[],
        attempts=[],
        stakes_level=1,
        mission_type="conversation",
    )
    llm = _ReplyLlm(drafts)
    service = missions.MissionConversationService(db=None, llm_service=llm)
    return service, llm, mission


def test_a_reply_above_the_band_is_rewritten_with_the_guards_hint(monkeypatch) -> None:
    good = "Ah, merci ! Tu viens au café ?"
    service, llm, mission = _reply_service(monkeypatch, [MARIN_REPLY, good])
    assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Oui") == good
    assert len(llm.systems) == 2, "the A1.1 reply was never checked"
    assert "plus-que-parfait" in llm.systems[1]


def test_a_reply_that_stays_above_the_band_gets_the_plain_acknowledgement(monkeypatch) -> None:
    service, _llm, mission = _reply_service(monkeypatch, [MARIN_REPLY, MARIN_REPLY])
    answer = service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Oui")
    assert "je l'ai bien lu" in answer


def test_plain_a1_reply_is_kept_as_written(monkeypatch) -> None:
    plain = "Je pense qu'ils viennent demain. Il était fatigué, mais tu peux venir."
    service, llm, mission = _reply_service(monkeypatch, [plain])
    assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Oui") == plain
    assert len(llm.systems) == 1


def test_the_actor_prompt_describes_the_language_without_naming_the_level(monkeypatch) -> None:
    """The actor is told what French to write, never that its reader is a beginner."""

    good = "Ah, merci ! Tu viens au café ?"
    service, llm, mission = _reply_service(monkeypatch, [good])
    service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Oui")
    prompt = llm.systems[0]
    assert "present tense" in prompt and "passé composé" in prompt
    assert "A1" not in prompt
    assert "beginner" not in prompt.lower()
