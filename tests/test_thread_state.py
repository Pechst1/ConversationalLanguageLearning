"""Courrier thread state (#538, #557, #520): the reply follows the learner's choice,
the suggestions follow the thread, and a letter keeps one tu/vous register.

Root cause shared by the three: the Courrier kept the thread in three unconnected
places (the letter in the payload, the turns in their table, the chips fixed at
creation) and none of them was an input to the next line. The reply writer saw the
turns but not the letter it was answering, the chips were never recomputed, and
authored letter text was never held to the one-register rule the generated text is.

No model calls: scripted writers and the exact lines quoted in the issues.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.db.models.user import User
from app.services import missions
from app.services.llm_service import LLMProviderError
from app.services.pragmatics import address_markers

# --- #538 -------------------------------------------------------------------

LETTER_2 = "Ta taille est là. Tu préfères la poste ou la boutique ? Il en reste une jusqu'à ce soir."
LEARNER_CHOICE = "Non, pas la poste. Je viens à la boutique à midi, avec ma assiette. Ce mois, je suis très occupé."
ANAIS_WALK_REPLY = (
    "D'accord, je comprends que tu es occupé. Mais pourrais-tu me dire quel est le problème avec ta commande ? "
    "Est-ce que tu souhaites un échange ou un remboursement ?"
)
ANAIS_FOLLOWING_THE_CHOICE = "D'accord, on t'attend à la boutique à midi. Ta taille reste pour toi."


class _CapturingLlm:
    def __init__(self, drafts: list[str]) -> None:
        self.drafts, self.systems, self.messages = list(drafts), [], []

    def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
        self.systems.append(kwargs["system_prompt"])
        self.messages.append(kwargs["messages"])
        if not self.drafts:
            raise LLMProviderError("the provider is down")
        return SimpleNamespace(content=self.drafts.pop(0))


def _letter_two(monkeypatch, drafts: list[str]):
    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    monkeypatch.setattr(missions, "_learner_level_code", lambda db, user: "A1")
    mission = SimpleNamespace(
        id=None,
        title="Ta taille est arrivée",
        brief="La boutique a ta taille. Choisis : par la poste ou à la boutique.",
        prompt_payload={
            "messenger": {
                "contact_name": "Boutique Anaïs",
                "register": "tu / warm informal",
                "target_register": "tu / registre familier",
                "opening_message": LETTER_2,
            },
            "conversation_opening": LETTER_2,
        },
        source_snapshot={},
        turns=[],  # the letter is not a turn: it lives in the payload
        attempts=[],
        stakes_level=1,
        mission_type="message",
    )
    llm = _CapturingLlm(drafts)
    return missions.MissionConversationService(db=None, llm_service=llm), llm, mission


def _context_of(llm) -> dict:
    return json.loads(llm.messages[0][0]["content"].removeprefix("Scene context: "))


def test_the_writer_is_told_what_the_reply_did_to_the_letters_question(monkeypatch) -> None:
    """#538: «Tu préfères la poste ou la boutique ?» / «Non, pas la poste. Je viens à la
    boutique à midi» was answered with a question about a problem and an exchange. The writer
    had no record of the question or that it was answered."""

    service, llm, mission = _letter_two(monkeypatch, [ANAIS_FOLLOWING_THE_CHOICE])
    service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE)

    ledger = _context_of(llm)["ledger"]
    assert ledger["last_turn"]["intent"] == "no"
    assert [(row["text_fr"], row["answered_at"]) for row in ledger["asked"]] == [("Tu préfères la poste ou la boutique ?", 0)]
    assert "THE THREAD IS YOUR MEMORY" in llm.systems[0] and "a no stays a no" in llm.systems[0]


def test_a_natural_reply_costs_no_retry(monkeypatch) -> None:
    """The draft of this fix demanded a word from the learner's clause, and a natural reply
    with none of them paid for a retry. State goes in; nothing here judges meaning, so the
    walk's reply is held back only by what the writer now knows. **No real model has answered
    this prompt**: that needs a recording or a live walk."""

    for reply in (ANAIS_FOLLOWING_THE_CHOICE, "Parfait, je te garde tout ça jusqu'à ce soir.", ANAIS_WALK_REPLY):
        service, llm, mission = _letter_two(monkeypatch, [reply])
        assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE) == reply
        assert len(llm.systems) == 1


def test_the_reply_writer_is_shown_the_letter_it_answers(monkeypatch) -> None:
    """The writer got the turns and the learner's line, never the letter that asked the
    question, so there was no question for it to hold the answer against."""

    service, llm, mission = _letter_two(monkeypatch, [ANAIS_FOLLOWING_THE_CHOICE])
    service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE)

    sent = json.dumps(llm.messages[0], ensure_ascii=False)
    assert "Tu préfères la poste ou la boutique" in sent


def test_a_reply_that_asks_the_settled_choice_again_is_held_back(monkeypatch) -> None:
    again = "D'accord ! Alors, la poste ou la boutique ?"
    service, llm, mission = _letter_two(monkeypatch, [again, ANAIS_FOLLOWING_THE_CHOICE])
    answer = service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE)
    assert answer == ANAIS_FOLLOWING_THE_CHOICE
    assert len(llm.systems) == 2


def test_a_reask_never_costs_the_reply(monkeypatch) -> None:
    """Soft, as on a scene: what the retry says again is served without the question, and if
    the retry fails outright the first draft is served the same way."""

    again = "D'accord ! Alors, la poste ou la boutique ?"
    service, llm, mission = _letter_two(monkeypatch, [again, again])
    assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE) == "D'accord !"
    assert len(llm.systems) == 2

    service, llm, mission = _letter_two(monkeypatch, [again])
    assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE) == "D'accord !"


def test_a_reply_quoting_what_they_never_wrote_is_asked_for_again(monkeypatch) -> None:
    quoted = "Tu as écrit « je préfère la poste », c'est noté."
    service, llm, mission = _letter_two(monkeypatch, [quoted, ANAIS_FOLLOWING_THE_CHOICE])
    assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE) == ANAIS_FOLLOWING_THE_CHOICE
    assert "never wrote" in llm.systems[1]


def test_an_extra_is_told_they_have_never_met_the_learner(monkeypatch) -> None:
    service, llm, mission = _letter_two(monkeypatch, [ANAIS_FOLLOWING_THE_CHOICE])
    service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE)
    assert _context_of(llm)["you_have_never_met_them"] is True
    assert "who_they_are_to_you" not in _context_of(llm)


def test_a_cast_member_is_told_what_they_are_to_the_learner(monkeypatch) -> None:
    service, llm, mission = _letter_two(monkeypatch, [ANAIS_FOLLOWING_THE_CHOICE])
    mission.prompt_payload["messenger"]["contact_name"] = "Camille"
    service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_CHOICE)
    context = _context_of(llm)
    assert "you_have_never_met_them" not in context
    assert context["who_they_are_to_you"]
    assert "friend" not in context["who_they_are_to_you"].casefold().replace("not a friend", "")


def test_an_extra_may_write_but_not_as_someone_who_knows_the_learner() -> None:
    """#626's family: «on s'est vus au Mistral» from someone day 1 never showed."""

    stranger = {"contact_name": "Mme Vidal", "opening_message": "Bonsoir, on s'est vus au marché, vous vous souvenez ?"}
    assert missions.canned_letter_problem(stranger, {"band": "A1"}) == "claims_to_know"
    assert missions.canned_letter_problem(stranger, {"band": "A1"}, follow_up=True) != "claims_to_know"
    # A stranger's plain facts are not a claim, and neither is a cast member's letter.
    assert not missions.extra_claims_to_know("Mme Vidal", ["Bonsoir, il y a eu beaucoup de bruit hier soir."])
    assert not missions.extra_claims_to_know("Margaux", ["La dernière fois, tu as oublié ton écharpe."])


def test_no_authored_first_letter_from_an_extra_claims_to_know_the_learner() -> None:
    claims = [
        letter["domain"]
        for letter in missions.REAL_WORLD_MISSION_DOMAINS
        if missions.extra_claims_to_know(
            letter.get("contact_name"), [letter.get("scene_anchor"), letter.get("opening_message"), letter.get("twist")]
        )
    ]
    assert claims == []


def _zoe_mission(turn_texts: list[tuple[str, str]]) -> RealWorldMission:
    mission = RealWorldMission(
        id=uuid4(), user_id=uuid4(), cadence="ad_hoc", mission_type="message", title="La fête dans la salle",
        brief="Zoé t'invite.", selected_concept_ids=[], target_errata_ids=[], target_vocabulary_ids=[],
        source_snapshot={}, objectives=[], recap_payload={}, status="in_progress",
        prompt_payload={
            "messenger": {
                "contact_name": "Zoé",
                "opening_message": "Salut, c'est Zoé. Tu viens à ma fête samedi ?",
                "quick_replies": ["Oui, je viens à ta fête !", "Je n'ai pas la page du menu.", "Quelle est l'heure ?"],
            }
        },
    )
    mission.turns = [
        RealWorldMissionTurn(id=uuid4(), turn_index=index + 1, role=role, mode="chat", text=text)
        for index, (role, text) in enumerate(turn_texts)
    ]
    mission.attempts = []
    return mission


def _chips(mission: RealWorldMission) -> list[str]:
    return list(serialize_chips(mission))


def serialize_chips(mission: RealWorldMission) -> list[str]:
    payload = missions.serialize_mission(mission)
    return payload["prompt_payload"]["messenger"]["quick_replies"]


def test_suggestions_do_not_offer_the_opposite_of_what_the_learner_said() -> None:
    """#557: after «Non, je ne peux pas venir à ta fête», «Oui, je viens à ta fête !» stayed."""

    mission = _zoe_mission(
        [
            ("user", "Non, je ne peux pas venir à ta fête, je suis fatigué."),
            ("assistant", "C'est dommage que tu ne puisses pas venir."),
        ]
    )
    chips = _chips(mission)
    assert "Oui, je viens à ta fête !" not in chips, chips
    assert "Quelle est l'heure ?" in chips  # a question still fits


def test_suggestions_do_not_repeat_what_the_learner_already_said() -> None:
    mission = _zoe_mission(
        [
            ("user", "Je n'ai pas la page du menu."),
            ("assistant", "Je te l'envoie. Tu viens samedi ?"),
        ]
    )
    chips = _chips(mission)
    assert "Je n'ai pas la page du menu." not in chips, chips
    assert "Oui, je viens à ta fête !" in chips  # nothing contradicts it


def test_the_opening_suggestions_are_untouched_before_the_first_reply() -> None:
    chips = _chips(_zoe_mission([]))
    assert chips == ["Oui, je viens à ta fête !", "Je n'ai pas la page du menu.", "Quelle est l'heure ?"]


def test_the_stored_letter_keeps_its_original_suggestions() -> None:
    mission = _zoe_mission([("user", "Non, je ne peux pas venir à ta fête.")])
    _chips(mission)
    assert "Oui, je viens à ta fête !" in mission.prompt_payload["messenger"]["quick_replies"]


# --- #520 -------------------------------------------------------------------


def _lines(letter: dict) -> dict[str, str]:
    lines = {
        "scene_anchor": letter.get("scene_anchor"),
        "opening_message": letter.get("opening_message"),
        "twist": letter.get("twist"),
    }
    for index, follow_up in enumerate(missions.follow_ups_of(letter)):
        lines[f"follow_up_{index + 1}"] = follow_up["opening_message"]
    return {key: value for key, value in lines.items() if value}


def _registers(lines: dict[str, str]) -> dict[str, str]:
    seen = {}
    for key, text in lines.items():
        tu, vous = address_markers(text)
        if tu or vous:
            seen[key] = "both" if tu and vous else ("tu" if tu else "vous")
    return seen


def test_every_authored_letter_keeps_one_register_in_every_line() -> None:
    """#520: «avez-vous» in the opening, «à ta taille» in the P.S., «À ton bureau» in the
    setting line. The generated letter was held to one register; the authored table was not."""

    mixed = {
        letter["domain"]: _registers(_lines(letter))
        for letter in missions.REAL_WORLD_MISSION_DOMAINS
        if len(set(_registers(_lines(letter)).values())) > 1
    }
    assert mixed == {}, mixed


def test_the_first_letters_keep_one_register_in_both_registers() -> None:
    for key in missions.FIRST_LETTERS:
        for register in ("tu", "vous"):
            printed = missions.first_letter_for(SimpleNamespace(cefr_estimate="B1" if key == "B" else "A1"), register=register)
            seen = set(_registers(_lines(printed)).values())
            assert seen <= {register}, (key, register, _registers(_lines(printed)))


def test_the_shop_letter_of_the_walk_speaks_vous_in_every_line() -> None:
    shop = next(item for item in missions.REAL_WORLD_MISSION_DOMAINS if item["domain"] == "shopping")
    seen = _registers(_lines(shop))
    assert set(seen.values()) == {"vous"}, seen
    assert "À ton bureau" not in shop["scene_anchor"]


def test_a_canned_letter_that_mixes_registers_is_not_printed() -> None:
    letter = {
        "domain": "shopping", "level": "A1", "scene_anchor": "À ton bureau, avec le paquet à renvoyer",
        "opening_message": "Bonjour, quelle taille avez-vous et quelle taille voulez-vous ?",
        "twist": "Il reste un seul article à ta taille, jusqu'à ce soir.",
    }
    rotation = {"band": "A1"}
    assert missions.canned_letter_problem(letter, rotation) == "mixed_register"
    assert missions.canned_letter_problem({**letter, "scene_anchor": "Au bureau", "twist": "Il reste un article à votre taille."}, rotation) is None


def test_the_letter_writer_is_held_to_one_register_in_the_setting_line_too(monkeypatch) -> None:
    """The setting line is printed with the letter: «À ton bureau» over a «vous» opening
    sends the draft back with the reason, as a mixed P.S. already did (#117)."""

    payloads: list[dict] = []

    def draft(scene_anchor: str) -> str:
        return json.dumps(
            {
                "title": "Pas la bonne taille",
                "brief": "Demande un échange.",
                "contact_name": "Boutique Anaïs",
                "scene_anchor": scene_anchor,
                "opening_message": "Bonjour, quelle taille avez-vous et quelle taille voulez-vous ?",
                "twist": "Il reste un seul article à votre taille.",
                "success_signal": "La boutique envoie la bonne taille.",
                "success_signal_en": "The shop sends the right size.",
                "success_signal_de": "Der Laden schickt die richtige Größe.",
            }
        )

    drafts = [draft("À ton bureau, avec le paquet à renvoyer"), draft("Au bureau, avec le paquet à renvoyer")]

    class _Llm:
        def generate_chat_completion(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            payloads.append(json.loads(messages[0]["content"]))
            return SimpleNamespace(content=drafts.pop(0))

    monkeypatch.setattr(missions, "_safe_llm", lambda: _Llm())
    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    generator = missions.MissionGenerator.__new__(missions.MissionGenerator)
    generator.llm, generator.db = None, None
    monkeypatch.setattr(generator, "_letter_known_words", lambda user: None)
    user = User(email="shop@example.com", hashed_password="x", proficiency_level="A1", native_language="en")
    scenario = generator._llm_scenario(
        user=user, mission_type="message", concepts=[], vocabulary=[], variety={}, recent_variety=[]
    )
    assert len(payloads) == 2, "the mixed setting line was accepted at the first attempt"
    assert "«tu» and «vous»" in payloads[1]["rewrite_because"]
    assert scenario is not None and scenario["messenger"]["scene_anchor"].startswith("Au bureau")
