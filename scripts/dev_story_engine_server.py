#!/usr/bin/env python
"""Run the API locally with the living-story engine on a FAKE provider.

Development and verification only. This exists so the WP-14 reader integration and
the story writer's PostgreSQL locking can be driven end to end through the real
HTTP surface without a paid model call:

* every provider credential is overwritten with an obviously fake value **before**
  ``app.config`` loads ``.env``, so nothing in this process can bill anyone;
* ``living_story._client`` is replaced by an in-process provider that answers the
  director / interpreter / critic schemas with valid, varied, canon-safe JSON;
* the daily-journey gate is opened for this process only (nothing persisted);
* ``DATABASE_URL`` must be given explicitly and may never be the owner's live
  ``language_learning`` database — use ``createdb`` and drop it afterwards.

Usage (from the repository root):

    DATABASE_URL=postgresql://localhost/atelier_story_pg_XXXX \
        venv/bin/python scripts/dev_story_engine_server.py --port 8010

The generated prose here is deliberately mechanical. It proves plumbing, ownership,
locking and the reader contract — never model quality. Real-provider review is
``scripts/review_living_story.py --live``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from types import SimpleNamespace

FAKE_CREDENTIAL = "dev-fake-key-not-a-real-credential"


def _guard_environment() -> None:
    for variable in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "PERPLEXITY_API_KEY",
        "ELEVENLABS_API_KEY",
    ):
        os.environ[variable] = FAKE_CREDENTIAL
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit("DATABASE_URL must be set explicitly to a throwaway database (createdb ...).")
    if "language_learning" in url:
        sys.exit("Refusing to run against the owner's live language_learning database.")
    os.environ.setdefault("ATELIER_DAILY_JOURNEY_ENABLED", "true")
    os.environ.setdefault("ATELIER_STORY_ENGINE_ENABLED", "true")
    # The fake client below bypasses the provider flag on purpose; keep the real
    # provider path (and every other LLM feature) switched off.
    os.environ.setdefault("ATELIER_LLM_ENABLED", "false")
    os.environ.setdefault("APP_ENV", "development")


PREMISES = [
    ("Romy cherche une idée pour une exposition dans le quartier.", "Suggest how you can help, or explain that you cannot.", "Clearly express an offer or a refusal of help with the exhibition.", "exhibition-help"),
    ("Le four du café est en panne le jour du marché.", "Propose an alternative for the market morning, or decline.", "Express a concrete alternative plan or a clear refusal.", "broken-oven"),
    ("Un voisin veut vendre son vieux vélo et demande un prix.", "Negotiate a price or say the bike does not interest you.", "State a price, a counter-offer or a refusal.", "bike-price"),
    ("Le facteur a livré un colis pour quelqu'un d'autre.", "Explain what happened to the parcel.", "Describe the mistaken delivery and propose what to do.", "wrong-parcel"),
    ("Une affiche annonce une soirée jeux vendredi.", "Say whether you come on Friday and what you bring.", "Accept or decline the invitation and mention a contribution.", "game-night"),
    ("La pluie a inondé la cave de l'immeuble.", "Ask a neighbour for help, or offer yours.", "Request or offer help with the flooded cellar.", "flooded-cellar"),
    ("Margaux cherche quelqu'un pour garder son chat ce week-end.", "Accept or decline, and say when you are free.", "Give an answer about cat-sitting with a time.", "cat-sitting"),
]
# Seven premises: the engine rejects a premise that overlaps one of the last five.


class FakeStoryProvider:
    """Deterministic, canon-safe answers for the engine's three schemas."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.scenes = 0
        self.turns = 0
        self.calls = 0

    def generate_chat_completion(self, messages, **kwargs):  # noqa: D401 - provider shape
        data = json.loads(messages[0]["content"])
        schema = data["output_schema"]["title"]
        source = data["data"]
        with self._lock:
            self.calls += 1
            if schema == "SceneDraft":
                value = self._draft(source, self.scenes)
                self.scenes += 1
            elif schema == "SemanticTurn":
                value = self._turn(source, self.turns)
                self.turns += 1
            else:
                value = {"accepted": True, "issues": []}
        return SimpleNamespace(
            content=json.dumps(value, ensure_ascii=False),
            model="fake-story-provider",
            provider="dev-fake",
            total_tokens=0,
            cost=0.0,
        )

    @staticmethod
    def _draft(context: dict, n: int) -> dict:
        world = context.get("world") or {}
        cast = [c for c in world.get("cast", []) if c.get("id")] or [{"id": "romy_tremblay"}]
        locations = [place for place in world.get("locations", []) if place.get("id")] or [{"id": "le_mistral"}]
        character = cast[n % len(cast)]["id"]
        location = locations[n % len(locations)]["id"]
        premise, objective, semantics, novelty = PREMISES[n % len(PREMISES)]
        chapter = context.get("chapter") or {}
        events = context.get("events") or []
        if chapter and not chapter.get("resolved"):
            chapter_value = {k: chapter[k] for k in ("title_fr", "dramatic_question", "possible_developments")}
        else:
            chapter_value = {
                "title_fr": f"Chapitre {n + 1}",
                "dramatic_question": f"Que va devenir ce projet numéro {n + 1} ?",
                "possible_developments": ["Trouver une solution.", "Demander de l'aide.", "Changer de plan."],
            }
        return {
            "title_fr": f"Scène {n + 1} — {novelty}",
            "premise_fr": premise,
            "setup_native": f"[dev fake] {premise}",
            "objective_native": objective,
            "objective_semantics": semantics,
            "character_id": character,
            "location_id": location,
            "causal_reason": "Suite directe de l'échange précédent." if events else "Première rencontre du quartier.",
            "source_event_ids": [e["id"] for e in events[-1:]],
            "novelty_key": f"{novelty}-{n}",
            "chapter": chapter_value,
            "panels": [
                {"narration_fr": f"Panneau 1 : {premise}", "dialogue": [], "visual_direction": "Wide establishing shot of the location."},
                {"narration_fr": "", "dialogue": [{"character_id": character, "text_fr": "Alors, qu'est-ce que vous en pensez ?"}], "visual_direction": "Medium shot, the character turns to the learner."},
                {"narration_fr": "Panneau 3 : un silence, puis un sourire.", "dialogue": [{"character_id": character, "text_fr": "Dites-moi."}], "visual_direction": "Close-up, waiting."},
            ],
            "opening_line_fr": "Vous pouvez m'aider ?",
            "suggested_response_fr": "Oui, je peux vous aider samedi.",
            "hint_native": "Say yes or no, and when.",
            "translation_native": "Can you help me?",
            "capability_key": None,
        }

    @staticmethod
    def _turn(payload: dict, n: int) -> dict:
        text = payload["learner_text"]
        lowered = text.lower()
        refused = any(marker in lowered for marker in ("non", "ne peux pas", "pas possible", "désolé"))
        return {
            "outcome": "met",
            "understood_intent": "The learner declines." if refused else "The learner offers help.",
            "evidence_quotes": [text],
            "reply_fr": "Dommage, une autre fois alors." if refused else "Merci ! On fait ça ensemble.",
            "needs_clarification": False,
            "resolution_fr": "Vous refusez poliment." if refused else "Vous promettez de venir aider.",
            "summary_native": "You declined." if refused else "You offered to help.",
            "callback_fr": "Vous avez refusé cette fois." if refused else "Vous avez promis d'aider samedi.",
            "commitments": [] if refused else [{"text_fr": "Aider samedi.", "source_quote": text}],
            "resolved_commitment_ids": [],
            "chapter_resolved": (n % 3 == 2),
            "demonstrated_target_ids": [],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    _guard_environment()

    import uvicorn

    from app.main import app
    from app.services import living_story as engine

    provider = FakeStoryProvider()
    engine._client = lambda: provider
    print(
        f"[dev-story-engine] fake provider installed; DATABASE_URL={os.environ['DATABASE_URL']}; "
        "no model call can leave this process",
        flush=True,
    )
    uvicorn.run(app, host=args.host, port=args.port, timeout_keep_alive=75)


if __name__ == "__main__":
    main()
