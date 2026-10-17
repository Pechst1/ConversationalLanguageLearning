"""#117: Courrier notes keep one address form per character and the learner's band."""

from __future__ import annotations

from app.services.letter_voice import above_band_tenses, register_word, voice_problems

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


def test_letter_mixing_tu_and_vous_is_caught() -> None:
    problems = voice_problems([MARIN_LETTER, MARIN_PS], register="tu", level="A1")
    assert any("both" in problem for problem in problems)


def test_letter_mixing_is_caught_even_when_register_is_unknown() -> None:
    assert voice_problems([MARIN_LETTER, MARIN_PS], register=None, level=None)


def test_wrong_register_for_the_character_is_caught() -> None:
    assert voice_problems(["Vous avez oublié votre écharpe."], register="tu", level="A1")
    assert voice_problems(["Tu as oublié ton écharpe."], register="vous", level="A1")
    assert not voice_problems(["Tu as oublié ton écharpe."], register="tu", level="A1")


def test_reply_above_a1_is_caught() -> None:
    assert above_band_tenses(MARIN_REPLY, "A1") == ["plus-que-parfait", "subjonctif"]
    assert above_band_tenses(MARIN_REPLY, "A2") == ["plus-que-parfait", "subjonctif"]
    assert above_band_tenses(MARIN_REPLY, "B1") == []


def test_future_is_above_a1_only() -> None:
    for line in WALK_14_OCT:
        assert above_band_tenses(line, "A1") == ["futur simple"]
        assert above_band_tenses(line, "A2") == []


def test_plain_a1_french_passes() -> None:
    plain = "Salut ! J'avais faim. Il est ici. Tu viens demain ? Elle a mangé. Je pense à toi."
    assert voice_problems([plain], register="tu", level="A1") == []


def test_register_word() -> None:
    assert register_word("tu / warm informal") == "tu"
    assert register_word("vous / polite formal") == "vous"
    assert register_word("polite neutral") is None


def test_reply_service_rewrites_then_falls_back(monkeypatch) -> None:
    """The reply path asks again with the guard's hint; two bad drafts give the plain acknowledgement."""

    from types import SimpleNamespace

    from app.services import missions

    class _Llm:
        def __init__(self, drafts: list[str]) -> None:
            self.drafts, self.systems = drafts, []

        def generate_chat_completion(self, **kwargs):
            self.systems.append(kwargs["system_prompt"])
            return SimpleNamespace(content=self.drafts.pop(0))

    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    monkeypatch.setattr(missions, "_learner_level_code", lambda db, user: "A1")
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
    good = "Ah, merci ! Tu viens au café ?"
    llm = _Llm([MARIN_REPLY, good])
    service = missions.MissionConversationService(db=None, llm_service=llm)
    assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Oui") == good
    assert "Rewrite your reply" in llm.systems[1]
    llm = _Llm([MARIN_REPLY, MARIN_REPLY])
    service = missions.MissionConversationService(db=None, llm_service=llm)
    assert "je l'ai bien lu" in service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Oui")
