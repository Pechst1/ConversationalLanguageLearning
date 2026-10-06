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
    # WP-108: a throwaway server must never queue into the owner's Redis (the walk
    # harness put warm-up jobs there). Tasks run inline; the broker is in memory.
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["CELERY_BROKER_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
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

# WP-111: the season's generated days. Canon-safe, «tu» (the season's register), and
# never one of a gap's forbidden reveals; the objective stays one of the English
# strings the walk's language check already knows.
SEASON_CAST = ("margaux_barman", "lila_bonnet", "marin_leveque", "romy_tremblay", "augustin_de_roncourt")
SEASON_PLACES = ("le_mistral", "boulangerie", "quai_de_valmy", "user_apartment", "marin_lila_flat", "stairwell", "ngo_office")
SEASON_PREMISES = (
    "Il pleut sur le canal, et le radiateur du studio refuse encore de chauffer.",
    "Au comptoir, Margaux essuie un verre déjà sec et attend ta commande.",
    "Mme Diallo sort les baguettes du four ; Lila compte ses pièces.",
    "Marin arrive avec une soupe et une bouillotte, trempé jusqu'aux os.",
    "Gus répète un discours sur des fiches, qui tombent une à une.",
    "Romy allume sa caméra, puis l'éteint en te regardant.",
    "Une lettre de la gérance attend sur le paillasson.",
)


#: Distinct chapter questions (the engine refuses a question that repeats a closed one).
SEASON_QUESTIONS = (
    "Le billet de retour va-t-il bouger encore ?",
    "Qui osera parler à Margaux du quartier ?",
    "La boulangère connaîtra-t-elle bientôt ta commande ?",
    "Marin trouvera-t-il le courage de demander ?",
    "Gus acceptera-t-il enfin un tutoiement ?",
    "Romy publiera-t-elle son enquête sur Solvel ?",
    "Le radiateur du studio survivra-t-il à l'hiver ?",
    "Lila montrera-t-elle ses toiles au groupe ?",
    "Qui paiera l'addition du vendredi soir ?",
    "La lettre de Solvel restera-t-elle sans réponse ?",
    "Le voisin du troisième ouvrira-t-il sa porte ?",
    "Que cache vraiment la cave de l'immeuble ?",
    "Le marché du dimanche aura-t-il lieu sous la pluie ?",
    "Qui gagnera la dispute sur la playlist du café ?",
)


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
            if schema == "SceneDraft" and (source.get("season_script") or {}).get("brief"):
                value = self._season_draft(source, self.scenes)
                self.scenes += 1
            elif schema == "SceneDraft":
                value = self._draft(source, self.scenes)
                self.scenes += 1
                # WP-92: a compliant director says the day's new form twice and asks for it.
                examples = ((source.get("grammar_plan") or {}).get("introduce") or {}).get("examples") or []
                if examples and len(value["panels"]) >= 3:
                    speaker = value["character_id"]
                    for panel, example in zip(value["panels"][1:3], [examples[0], examples[-1]], strict=True):
                        panel["dialogue"].append({"character_id": speaker, "text_fr": example})
                    value["suggested_response_fr"] = examples[0]
                # WP-95: the can-do the scene exercises, an unstamped one first.
                menu = source.get("can_dos") or {}
                value["can_do_id"] = (menu.get("prefer") or [None])[0]
                # WP-94 «Numéro spécial»: everyone comes, and the host's two lines.
                epreuve = source.get("epreuve")
                if epreuve and len(value["panels"]) >= 2:
                    value["can_do_id"] = epreuve["can_do_ids"][0]
                    value["panels"][-1]["dialogue"] = [
                        {"character_id": member["id"], "text_fr": "Bonsoir !"}
                        for member in epreuve.get("cast") or []
                    ][:3]
                    value["epreuve_pass_line_fr"] = "Bravo ! On est tous très fiers."  # noqa: S105
                    value["epreuve_fail_line_fr"] = "On se revoit la semaine prochaine, d'accord ?"
            elif schema == "SemanticTurn":
                value = self._turn(source, self.turns)
                self.turns += 1
            elif schema == "TutorVerdict":
                # WP-87 lanes: the tutor grades, the voice answers, the story lane ends.
                text = str(source.get("learner_text") or "")
                value = {"outcome": "met", "evidence_quotes": [text] if text.strip() else [], "demonstrated_target_ids": []}
            elif schema == "VoiceReply":
                text = str(source.get("learner_text") or "").lower()
                refused = any(marker in text for marker in ("non", "ne peux pas", "pas possible", "désolé"))
                keep = bool((source.get("turn_plan") or {}).get("keep_talking"))
                value = {
                    "reply_fr": ("Dommage. Et demain, alors ?" if refused else "Merci ! Et après, on fait quoi ?")
                    if keep
                    else ("Dommage, une autre fois alors." if refused else "Merci ! On fait ça ensemble."),
                    "understood_intent": "The learner declines." if refused else "The learner offers help.",
                    "needs_clarification": False,
                    "feeling_shift": "steady",
                }
            elif schema == "StoryTurn":
                value = {
                    "resolution_fr": "La journée se termine au Mistral.",
                    "summary_native": "[dev fake] The day ends at Le Mistral.",
                    "callback_fr": "Vous avez répondu.",
                    "commitments": [],
                    "resolved_commitment_ids": [],
                    "chapter_resolved": False,
                    "development_index": 0,
                }
            elif schema == "TurnReview":
                value = {"accepted": True, "issues": [], "released_issues": []}
            elif schema == "StoryReview":
                # WP-114: the story critic, satisfied (the fake director's day changes something).
                value = {
                    "hook": True, "stakes": True, "value_turn": True, "meaningful_change": True,
                    "advances_thread": True, "in_character": True, "spoils_next_tentpole": False,
                    "change_summary": "avant → après", "issues": [], "accepted": True,
                }
            elif schema == "ReplyChoice":
                # WP-111: which of the bible's likely replies a learner line expresses.
                from app.services.season.turns import match_reply

                turn = {"replies": source.get("replies") or [], "fallback": source.get("fallback")}
                reply_id, _ = match_reply(turn, str(source.get("learner_text") or ""))
                value = {"reply_id": reply_id, "expresses": "none", "value": None, "confidence": 0.6}
            elif schema == "CoulissesDraft":
                # WP-93 «Coulisses»: the same evening, from another cast member's eyes.
                pov = source.get("pov_character_id") or "romy_tremblay"
                value = {
                    "title_fr": "Le même soir, en coulisses",
                    "pov_character_id": pov,
                    "panels": [
                        {
                            "narration_fr": text,
                            "dialogue": [{"character_id": pov, "text_fr": line, "mood": "moved"}],
                            "visual_direction": "Close-up of the character, later that evening.",
                            "alt_native": "The character, alone, later that evening.",
                        }
                        for text, line in (
                            ("Plus tard, le café est calme.", "Quelle soirée !"),
                            ("Dehors, il pleut encore.", "Je pense à tout ça."),
                            ("La lumière s'éteint.", "Demain, on verra."),
                        )
                    ],
                }
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
                # The engine draws a page of four panels at least (MIN_SCENE_PANELS).
                {"narration_fr": "Panneau 4 : la pluie sur la vitre.", "dialogue": [], "visual_direction": "Wide shot of the window, rain."},
            ],
            "opening_line_fr": "Vous pouvez m'aider ?",
            "suggested_response_fr": "Oui, je peux vous aider samedi.",
            "hint_native": "Say yes or no, and when.",
            "translation_native": "Can you help me?",
            "capability_key": None,
        }

    @staticmethod
    def _season_draft(context: dict, n: int) -> dict:
        """A generated day inside the season's gap: its scheduled moment (or the first
        premise on offer), the checklist, «tu», and a hook."""

        brief = context["season_script"]["brief"]
        today = brief.get("today") or {}
        premise = today.get("required_premise") or (today.get("premises") or [{}])[0]
        chapter = context.get("chapter") or {}
        keeps = bool(chapter) and not (chapter.get("resolved") or chapter.get("exhausted"))
        character = SEASON_CAST[n % len(SEASON_CAST)]
        location = SEASON_PLACES[n % len(SEASON_PLACES)]
        shape = str((context.get("chapter_shape") or {}).get("shape") or chapter.get("shape") or "")
        if shape == "bottle" and keeps and chapter.get("location_id"):
            location = str(chapter["location_id"])
        must_change = (context.get("variety") or {}).get("must_change") or {}
        if must_change.get("character_id") == character and must_change.get("location_id") == location:
            character = SEASON_CAST[(n + 1) % len(SEASON_CAST)]
        text, objective, semantics, novelty = PREMISES[n % len(PREMISES)]
        retired = {str(q).casefold() for q in context.get("resolved_chapter_questions") or []}
        question = next(
            (
                SEASON_QUESTIONS[(n + k) % len(SEASON_QUESTIONS)]
                for k in range(len(SEASON_QUESTIONS))
                if SEASON_QUESTIONS[(n + k) % len(SEASON_QUESTIONS)].casefold() not in retired
            ),
            SEASON_QUESTIONS[n % len(SEASON_QUESTIONS)],
        )
        moment = (today.get("small_moments") or [{}])[0]
        return {
            "title_fr": f"{premise.get('title_fr') or 'Entre deux jours'} ({n + 1})",
            "premise_fr": SEASON_PREMISES[n % len(SEASON_PREMISES)],
            "setup_native": f"[dev fake] {premise.get('text') or text}"[:600],
            "objective_native": objective,
            "objective_semantics": semantics,
            "character_id": character,
            "location_id": location,
            "causal_reason": "Suite de la saison, dans les règles de l'entre-deux.",
            "source_event_ids": [e["id"] for e in (context.get("events") or [])[-1:]],
            "novelty_key": f"season-{novelty}-{n}",
            "chapter": {k: chapter[k] for k in ("title_fr", "dramatic_question", "possible_developments")}
            if keeps
            else {
                "title_fr": f"Entre deux jours {n + 1}",
                "dramatic_question": question,
                "possible_developments": ["Quelque chose change.", "Rien ne bouge encore."],
            },
            "panels": [
                {"narration_fr": SEASON_PREMISES[(n + 1) % len(SEASON_PREMISES)], "dialogue": [], "visual_direction": "Wide shot: two friends at work in the place.", "alt_native": "Two friends at work."},
                {"narration_fr": "", "dialogue": [{"character_id": character, "text_fr": "Tu as une minute ?"}], "visual_direction": "Medium shot, the character turns to Toi.", "alt_native": "A friend turns to you."},
                {"narration_fr": "Un silence.", "dialogue": [], "visual_direction": "Close-up of a glass on the zinc.", "alt_native": "A glass on the counter."},
                {"narration_fr": "", "dialogue": [{"character_id": character, "text_fr": "Alors, on fait quoi ?"}], "visual_direction": "Close-up, waiting.", "alt_native": "A friend, waiting."},
            ],
            "opening_line_fr": "Tu m'aides ?",
            "suggested_response_fr": "Oui, je peux t'aider samedi.",
            "hint_native": "Say yes or no, and when.",
            "translation_native": "Can you help me?",
            "capability_key": None,
            "season_checklist": {
                "premise_id": premise.get("id"),
                "threads": [],
                "change_before": "avant",
                "change_after": "après",
                "turn_want": "say what you want",
                "small_moment_id": moment.get("id"),
                "hook_fr": "À suivre…",
                "forbidden_respected": True,
            },
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
