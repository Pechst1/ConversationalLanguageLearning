"""WP-84 — Courrier letters at the learner's level.

The A1.1 learner got «geste commercial». Every letter the Courrier prints is
now checked against the learner's band with the lexical-coverage guard's copy
rule (``lexical_coverage.check_copy_level``): a generated letter above the band
is rewritten once with the guard's hint, then replaced by the authored letter,
which is written at A1. A generated letter must also carry its objective in the
learner's own language (WP-68 §8).

The acceptance run: 50 letters for an A1.1 learner through a fake provider that
writes a third of them at A1, a third at B1 and then repairs them, and a third
at B1 every time — all 50 printed letters pass the lexical-level check.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest

import app.services.missions as missions_module
from app.db.models.user import User
from app.services import lexical_coverage as lc
from app.services.llm_service import LLMResult
from app.services.missions import (
    REAL_WORLD_MISSION_DOMAINS,
    MissionGenerator,
    letter_level_verdict,
    success_signal_i18n,
)

A1_LETTER = {
    "title": "Un paquet pour vous",
    "brief": "Le paquet est chez la voisine. Répondez et dites quand vous êtes là.",
    "contact_name": "Inès",
    "contact_role": "une amie",
    "contact_initials": "IN",
    "scene_anchor": "Le soir, dans la rue, devant la porte",
    "thread_title": "Inès · le paquet",
    "opening_message": "Bonsoir ! J'ai votre paquet chez moi. Vous êtes là ce soir ?",
    "ambient_cues": ["un petit paquet", "une porte bleue", "le soir"],
    "quick_replies": ["Oui, je suis là...", "Merci beaucoup !", "Je viens à..."],
    "success_signal": "Inès sait quand vous venez.",
    "success_signal_en": "Inès knows when you are coming.",
    "success_signal_de": "Inès weiß, wann Sie kommen.",
    "inbox_context": "Elle veut savoir quand vous venez.",
    "domain": "deliveries_admin",
    "channel": "sms",
    "tone": "light_warm",
    "twist": "Le paquet est très grand.",
    "mission_format": "chat_message",
}

B1_LETTER = {
    **A1_LETTER,
    "title": "Panne prolongée",
    "brief": "Ils minimisent la panne : exigez un geste commercial.",
    "opening_message": (
        "Bonjour, nous constatons une perturbation dans votre secteur. Nous vous proposons "
        "un geste commercial sous réserve de justificatif."
    ),
    "success_signal": "Le service client consigne la durée et propose un geste commercial.",
}


def _content(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


class FakeWriter:
    """One scenario per call; ``kind`` decides the letter's level."""

    def __init__(self) -> None:
        self.kind = "a1"
        self.calls: list[dict[str, Any]] = []

    def generate_chat_completion(self, messages, **_: Any) -> LLMResult:
        payload = json.loads(messages[-1]["content"])
        self.calls.append(payload)
        repair = bool(payload.get("rewrite_because"))
        if self.kind == "a1" or (self.kind == "repairable" and repair):
            letter = A1_LETTER
        else:
            letter = B1_LETTER
        return LLMResult(
            provider="fake",
            model="fake",
            content=_content(letter),
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=0.0,
            raw_response={},
        )


def _a1_learner(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"wp84-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _printed_french(payload: dict[str, Any]) -> dict[str, Any]:
    """The French a learner reads on the letter: the writer's fields when the
    letter is generated, the authored French lines when it is not."""

    messenger = payload["prompt_payload"]["messenger"]
    fields = {
        "contact_name": messenger.get("contact_name"),
        "opening_message": messenger.get("opening_message"),
        "quick_replies": messenger.get("quick_replies"),
        "success_signal": success_signal_i18n(messenger).get("fr"),
    }
    if messenger.get("success_signal_i18n"):  # generated: every field is French
        fields.update(
            {
                "title": payload["title"],
                "brief": payload["brief"],
                "scene_anchor": messenger.get("scene_anchor"),
                "contact_role": messenger.get("contact_role"),
                "inbox_context": messenger.get("inbox_context"),
                "twist": messenger.get("twist"),
                "ambient_cues": messenger.get("ambient_cues"),
            }
        )
    return fields


def test_the_a1_guard_rejects_geste_commercial(db_session) -> None:
    user = _a1_learner(db_session)
    known = lc.known_word_set(db_session, user=user)
    assert known.band == "A1"
    verdict = letter_level_verdict(known, B1_LETTER)
    assert verdict.rejected and verdict.reason == lc.REJECT_ABOVE_BAND
    assert "geste" in (verdict.hint or "")
    # Even one short line is judged: two words far above A1.
    short = lc.check_copy_level(
        lc.SceneText(text="Quel geste commercial ?"), lc.LearnerLexicon(known=known)
    )
    assert short.rejected
    assert letter_level_verdict(known, A1_LETTER).accepted


def test_every_authored_letter_is_a1(db_session) -> None:
    user = _a1_learner(db_session)
    known = lc.known_word_set(db_session, user=user)
    for domain in REAL_WORLD_MISSION_DOMAINS:
        fields = {
            "contact_name": domain["contact_name"],
            "opening_message": domain["opening_message"],
            "quick_replies": domain["quick_replies"],
            "success_signal": success_signal_i18n({"success_signal": domain["success_signal"]}).get("fr"),
        }
        verdict = letter_level_verdict(known, fields, names=["Buttes-Chaumont"])
        assert verdict.accepted, (domain["domain"], verdict.hint)


def test_fifty_a1_letters_pass_the_lexical_level_check(db_session, monkeypatch) -> None:
    writer = FakeWriter()
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: writer)
    user = _a1_learner(db_session)
    known = lc.known_word_set(db_session, user=user)
    generator = MissionGenerator(db_session)
    kinds = ("a1", "repairable", "b1")
    types = ("message", "explain_plan", "travel_work", "conversation")
    outcomes: dict[str, int] = {"generated": 0, "repaired": 0, "authored": 0}
    recent: list[dict[str, Any]] = []
    for index in range(50):
        writer.kind = kinds[index % 3]
        before = len(writer.calls)
        payload = asyncio.run(
            generator.build_payload(
                user=user,
                mission_type=types[index % 4],
                cadence="ad_hoc",
                use_news=False,
                seed=("wp84", index),
                recent_variety=recent[-3:],
            )
        )
        variety = payload["prompt_payload"]["variety"]
        recent.append({key: variety.get(key) for key in ("domain", "contact", "channel", "tone", "mission_format")})
        calls = len(writer.calls) - before
        messenger = payload["prompt_payload"]["messenger"]
        if messenger.get("success_signal_i18n"):
            outcomes["repaired" if calls == 2 else "generated"] += 1
        else:
            outcomes["authored"] += 1
        verdict = letter_level_verdict(
            known, _printed_french(payload), names=["Buttes-Chaumont"]
        )
        assert verdict.accepted, (index, writer.kind, verdict.hint)
        assert "geste" not in json.dumps(_printed_french(payload), ensure_ascii=False)
        # The objective is in the learner's own language.
        assert payload["prompt_payload"]["slim_payload"]["ask_by_language"].get("en")
    assert outcomes == {"generated": 17, "repaired": 17, "authored": 16}


@pytest.mark.parametrize("missing", ["success_signal_en"])
def test_a_letter_without_the_learners_objective_is_rewritten(db_session, monkeypatch, missing) -> None:
    writer = FakeWriter()
    original = writer.generate_chat_completion

    def without(messages, **kwargs):
        result = original(messages, **kwargs)
        payload = json.loads(messages[-1]["content"])
        if not payload.get("rewrite_because"):
            letter = dict(A1_LETTER)
            letter.pop(missing)
            result.content = _content(letter)
        return result

    writer.generate_chat_completion = without  # type: ignore[method-assign]
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: writer)
    user = _a1_learner(db_session)
    payload = asyncio.run(
        MissionGenerator(db_session).build_payload(
            user=user, mission_type="message", cadence="ad_hoc", use_news=False
        )
    )
    assert len(writer.calls) == 2
    assert "success_signal_en" in writer.calls[1]["rewrite_because"]
    assert payload["prompt_payload"]["slim_payload"]["ask_by_language"]["en"] == A1_LETTER["success_signal_en"]
