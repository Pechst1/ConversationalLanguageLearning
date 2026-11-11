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
import re
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

# Serve the checkout this script lives in. Run as `python scripts/…`, Python puts
# scripts/ (not the repository) first on the path, so `import app` found an
# installed copy instead — in CI a non-editable wheel without the package data
# (the season world, the alembic directory): every scene was refused as "not in
# this world" and the schema guard saw no migration heads.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    # WP-158: the provider keys are fake, so a spoken reply is transcribed by the
    # deterministic fake transcriber rather than sent to Whisper with a dud key.
    os.environ.setdefault("ATELIER_FAKE_TRANSCRIBER_ENABLED", "true")


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


def _suggested(context: dict, answer: str) -> str:
    """From B1 the situation invites a move: the short answer, with a reason and a
    condition. Since 15 Oct 2026 no answer has a floor; this is just a natural one."""

    if str(context.get("level") or "")[:2] in {"B1", "B2", "C1", "C2"}:
        return answer.rstrip(".") + ", mais seulement le matin, parce que je travaille tard le soir."
    return answer


def _refuses(text: object) -> bool:
    """How the fake reads a refusal: the scene ledger's own reading of a turn (#145)."""

    from app.services import scene_ledger

    return scene_ledger.read_turn(text)["intent"] == "no"


def _name_in(memory: object, speaker: str | None = None) -> str | None:
    """The learner's name in a memory view, when the reader knows it: a character's view
    holds it as a plain string, the writers' view as ``{value, known_by}`` (then only
    ``speaker``, when given, must be one who knows it)."""

    name = memory.get("learner_name") if isinstance(memory, dict) else None
    if isinstance(name, dict):
        name = name.get("value") if speaker is None or speaker in (name.get("known_by") or []) else None
    return str(name) if name else None


def _said(context: dict, speaker: str | None = None) -> list[dict]:
    """The learner's remembered lines (``memory.said``), only those ``speaker`` heard."""

    memory = context.get("memory") if isinstance(context.get("memory"), dict) else {}
    return [
        row
        for row in memory.get("said") or []
        if isinstance(row, dict)
        and row.get("quote")
        and (speaker is None or speaker == row.get("to") or speaker in (row.get("heard_by") or []))
    ]


def _declined(row: dict) -> bool:
    """The ledger's intent for a remembered line: the fake actor understood a refusal as
    «The learner declines.»; a line nobody read is read by its words."""

    meant = str(row.get("meant") or "")
    return "declines" in meant.lower() if meant else _refuses(row.get("quote"))


def _follow_up(context: dict, lead: str, *, allowed: set[str]) -> str:
    """Story engine Phase 3 (#145): after the learner said «non» to someone, that person
    comes back to it the next day (never a third day running); otherwise the cast
    rotates as before."""

    said = _said(context)
    if not said or not _declined(said[-1]):
        return lead
    person = str(said[-1].get("to") or "")
    leads = [str(row.get("character_id") or "") for row in context.get("recent_situations") or []]
    return person if person in allowed and leads[-2:] != [person, person] else lead


def _remembering(context: dict, speaker: str, *, tu: bool) -> dict:
    """A page that remembers what ``speaker`` heard: the opening line answers the
    learner's last «non» or «oui» to them and uses the learner's name when they know
    it, the callback cites that line (the callback ledger), and the page comes back to a
    question the learner left open with them."""

    said = _said(context, speaker)
    memory = context.get("memory") if isinstance(context.get("memory"), dict) else {}
    name = _name_in(memory, speaker)
    asked = [
        row
        for row in memory.get("open") or []
        if isinstance(row, dict) and row.get("by") == "learner" and speaker in (row.get("known_by") or [])
    ]
    value: dict = {}
    if said:
        last = said[-1]
        you, word = ("tu as" if tu else "vous avez"), ("non" if _declined(last) else "oui")
        if word == "non":
            line = f"La dernière fois, {you} dit non. " + ("Tu m'aides aujourd'hui ?" if tu else "Vous pouvez m'aider aujourd'hui ?")
        else:
            line = f"La dernière fois, {you} dit oui. Merci ! " + ("Tu m'aides encore ?" if tu else "Vous pouvez encore m'aider ?")
        value.update(
            opening_line_fr=line,
            callback_fr=f"La dernière fois, {you} dit {word}.",
            callback_ref=last.get("id"),
        )
    if name:
        line = value.get("opening_line_fr") or ("Tu m'aides ?" if tu else "Vous pouvez m'aider ?")
        value["opening_line_fr"] = f"{name}, {line[:1].lower()}{line[1:]}"
    if asked:
        value["returns_to"] = asked[0].get("id")
    return value


def _reported(text: str) -> dict:
    """What the fake ending reports for the memory: the name the learner gave and a
    question they asked, each copied from their words."""

    from app.services.story_memory import stated_name

    name = stated_name(text)
    questions = [part.strip() for part in text.replace("?", "?\n").splitlines() if part.strip().endswith("?")]
    return {
        "learned": [{"key": "name", "fact_fr": f"L'apprenant s'appelle {name}.", "quote": text, "value": name}]
        if name
        else [],
        "left_open": questions[:1],
    }


#: What the fake character asks next, one per exchange: a line said twice in one
#: scene is refused as a repeat of the thread (#349), and a scene is three
#: exchanges from Régulier up (#378).
_NEXT_QUESTIONS = ("Et après, on fait quoi ?", "Et à quelle heure, alors ?", "Et qui d'autre vient ?")


#: How the fake voice takes each reading of the learner's turn (#145): the opening of its
#: reply, and how it closes when the scene ends on this exchange.
_TAKES = {
    "no": ("Dommage", "une autre fois alors."),
    "yes": ("Merci", "on fait ça ensemble."),
    "question": ("Bonne question", "je te réponds samedi."),
    "other": ("Ah bon", "on en reparle."),
}
_MEANT = {
    "no": "The learner declines.",
    "yes": "The learner offers help.",
    "question": "The learner asks something.",
    "other": "The learner says something else.",
}


def _intent_of(source: dict) -> str:
    """The learner's turn as the fake voice reads it: the ledger's reading when the
    payload carries one, the words otherwise."""

    from app.services import scene_ledger

    last = ((source.get("ledger") or {}).get("last_turn") or {}) if isinstance(source.get("ledger"), dict) else {}
    return str(last.get("intent") or scene_ledger.read_turn(source.get("learner_text"))["intent"])


def _ack_for(said: str, intent: str) -> str:
    """The fake reader's first line back on an authored day: it takes up a word of what the
    learner wrote, neither «tu» nor «vous», so any addressee can say it."""

    # A hyphenated word is one word: «grand-mère» is not taken up as «Grand» (walk of 9 Nov).
    words = [
        word
        for word in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", said)
        if len(word) >= 5 and word.lower() not in {"parce", "pourquoi"}
    ]
    word = (words[-1] if words else said.strip(" .?!") or "Bon").capitalize()
    return {
        "no": f"Non, alors. {word} : c'est noté.",
        "yes": f"Oui. {word}, bien.",
        "question": f"{word} ? Bonne question.",
    }.get(intent, f"{word} ? Ah bon.")


def _word_of(said: str) -> str:
    # A hyphenated word is one word: «grand-mère» is not taken up as «Grand» (walk of 9 Nov).
    words = [
        word
        for word in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", said)
        if len(word) >= 5 and word.lower() not in {"parce", "pourquoi"}
    ]
    return (words[-1] if words else "Bon").capitalize()


def _listen_for(said: str) -> str:
    return f"{_word_of(said)} : pourquoi ?"


def _close_for(said: str) -> str:
    return f"{_word_of(said)}. On en reste là pour ce soir."


def _reply(*, intent: str, keep: bool, name: str | None, exchange: int = 0) -> str:
    """The fake character's answer, one per reading of the learner's turn; a character
    who was told the learner's name uses it."""

    opener, close = _TAKES.get(intent, _TAKES["other"])
    called = f"{opener}, {name}" if name else opener
    return f"{called}. {_NEXT_QUESTIONS[exchange % len(_NEXT_QUESTIONS)]}" if keep else f"{called}, {close}"


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
        # #333: the walk with its provider down. The day's content still comes; nothing
        # can read what the learner writes, the way a real outage looks.
        if os.environ.get("WALK_PROVIDER_DOWN") and schema in {"TutorVerdict", "VoiceReply", "StoryTurn", "AppealRuling"}:
            from app.services.llm_service import LLMProviderError

            raise LLMProviderError("walk: provider forced down")
        source = data["data"]
        with self._lock:
            self.calls += 1
            if schema == "SceneDraft" and (source.get("season_script") or {}).get("brief"):
                value = self._season_draft(source, self.scenes)
                self.scenes += 1
            elif schema == "SceneDraft":
                value = self._draft(source, self.scenes)
                self.scenes += 1
                # WP-92: the fake says the day's new form twice and asks for it. Since 15 Oct
                # 2026 the director says it once and never asks for it; twice still passes.
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
                intent = _intent_of(source)
                keep = bool((source.get("turn_plan") or {}).get("keep_talking"))
                value = {
                    "reply_fr": _reply(
                        intent=intent, keep=keep, name=_name_in(source.get("memory")),
                        exchange=len(source.get("history") or []),
                    ),
                    "understood_intent": _MEANT.get(intent, _MEANT["other"]),
                    "learner_intent": intent,
                    "learned": _reported(str(source.get("learner_text") or ""))["learned"],
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
                    "tomorrow_question_fr": "Et demain, qu'est-ce qu'on fait au Mistral ?",
                    **_reported(str(source.get("learner_text") or "")),
                }
            elif schema == "AppealRuling":
                # Package V stage 5: the walk's appeal is upheld, in the learner's language.
                reasons = {
                    "en": "[dev fake] Your answer says what the exercise asks.",
                    "de": "[dev fake] Deine Antwort sagt, was die Übung verlangt.",
                    "fr": "[dev fake] Ta réponse dit ce que l'exercice demande.",
                }
                value = {"upheld": True, "reason_native": reasons.get(str(source.get("reason_language")), reasons["en"])}
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
                said = str(source.get("learner_text") or "")
                reply_id, _ = match_reply(turn, said)
                value = {
                    "reply_id": reply_id,
                    "expresses": "none",
                    "value": None,
                    "confidence": 0.6,
                    "learned": _reported(said)["learned"],
                    "learner_intent": _intent_of(source),
                    "ack_fr": _ack_for(said, _intent_of(source)),
                    # On a page that asks once, the scene asks one more from what was written.
                    "listen_fr": _listen_for(said) if (source.get("scene") or {}).get("one_exchange") else None,
                }
            elif schema == "SceneClosing":
                # #558: the conversation's last words, by the first person in the room.
                said = str(source.get("learner_text") or "")
                room = source.get("in_the_room") or []
                value = {
                    "lines": [{"who": room[0]["id"], "text_fr": _close_for(said)}] if room else [],
                    "learner_intent": _intent_of(source),
                    "learned": _reported(said)["learned"],
                    # #466: what stays open, for «Tomorrow». Held to the scene like any written one.
                    "tomorrow_question_fr": "Et demain, qu'est-ce qu'on fait au Mistral ?",
                }
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
        # Story engine Phase 3: the person the learner said «non» to comes back to it.
        character = _follow_up(context, character, allowed={member["id"] for member in cast})
        chapter = context.get("chapter") or {}
        events = context.get("events") or []
        # ``n`` is a process counter, and the drain verifier restarts this server
        # between its phases: on 7–8 October the fresh process dealt day 2 the
        # premise day 1 had used and a room outside the bottle chapter, every
        # attempt was refused, and the day fell to the authored fallback. The
        # guards' own inputs are in the context, so honour them here: a bottle
        # chapter keeps its room, and a premise the recent situations already
        # used is skipped.
        if chapter and not chapter.get("resolved") and str(chapter.get("shape") or "") == "bottle" and chapter.get("location_id"):
            location = str(chapter["location_id"])
        used_objectives = {
            str(item.get("objective_native") or "") for item in (context.get("recent_situations") or [])
        }
        order = [PREMISES[(n + k) % len(PREMISES)] for k in range(len(PREMISES))]
        premise, objective, semantics, novelty = next(
            (entry for entry in order if entry[1] not in used_objectives), order[0]
        )
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
            "novelty_key": f"{novelty}-{len(events)}-{n}",
            "chapter": chapter_value,
            "panels": [
                {"narration_fr": f"Panneau 1 : {premise}", "dialogue": [], "visual_direction": "Wide establishing shot of the location."},
                {"narration_fr": "", "dialogue": [{"character_id": character, "text_fr": "Alors, qu'est-ce que vous en pensez ?"}], "visual_direction": "Medium shot, the character turns to the learner."},
                {"narration_fr": "Panneau 3 : un silence, puis un sourire.", "dialogue": [{"character_id": character, "text_fr": "Dites-moi."}], "visual_direction": "Close-up, waiting."},
                # The engine draws a page of four panels at least (MIN_SCENE_PANELS).
                {"narration_fr": "Panneau 4 : la pluie sur la vitre.", "dialogue": [], "visual_direction": "Wide shot of the window, rain."},
            ],
            "opening_line_fr": "Vous pouvez m'aider ?",
            "suggested_response_fr": _suggested(context, "Oui, je peux vous aider samedi."),
            "hint_native": "Say yes or no, and when.",
            "translation_native": "Can you help me?",
            "capability_key": None,
            **_remembering(context, character, tu=False),
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
        # A compliant director sets the page at a place it was offered: a season's
        # generated page is offered only the places Le Quartier has built
        # (``on_built_stage``). From 8 Nov the fake still dealt the bakery, Marin and
        # Lila's flat or the NGO office, the engine refused those drafts as places not
        # in the world, and «Walk · season × 10 days» failed on every push to main.
        offered = {str(place.get("id")) for place in (context.get("world") or {}).get("locations") or []}
        places = [place for place in SEASON_PLACES if place in offered] or list(SEASON_PLACES)
        location = places[n % len(places)]
        shape = str((context.get("chapter_shape") or {}).get("shape") or chapter.get("shape") or "")
        if shape == "bottle" and keeps and chapter.get("location_id"):
            location = str(chapter["location_id"])
        must_change = (context.get("variety") or {}).get("must_change") or {}
        if must_change.get("character_id") == character and must_change.get("location_id") == location:
            character = SEASON_CAST[(n + 1) % len(SEASON_CAST)]
        # This page speaks «tu». ``n`` is shared by every learner of the walk, so under
        # concurrency all three attempts of one day could land on Gus while he is still
        # on «vous» (canon_register), and the day was lost: honour the brief's registers.
        registers = (brief.get("address") or {}).get("registers") or {}
        if registers.get(character) == "vous":
            character = next(
                (
                    SEASON_CAST[(n + k) % len(SEASON_CAST)]
                    for k in range(1, len(SEASON_CAST))
                    if registers.get(SEASON_CAST[(n + k) % len(SEASON_CAST)]) != "vous"
                    and SEASON_CAST[(n + k) % len(SEASON_CAST)] != must_change.get("character_id")
                ),
                character,
            )
        # Story engine Phase 3: the person the learner said «non» to comes back to it,
        # when they say «tu» to the learner and may lead today.
        character = _follow_up(
            context,
            character,
            allowed={
                member
                for member in SEASON_CAST
                if registers.get(member) != "vous"
                and not (member == must_change.get("character_id") and location == must_change.get("location_id"))
            },
        )
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
            # #621: the state ``scene_unity`` compares: one person, one place.
            "scene_cast": [character],
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
                {"location_id": location, "narration_fr": SEASON_PREMISES[(n + 1) % len(SEASON_PREMISES)], "dialogue": [], "visual_direction": "Wide shot: two friends at work in the place.", "alt_native": "Two friends at work."},
                {"location_id": location, "narration_fr": "", "dialogue": [{"character_id": character, "text_fr": "Tu as une minute ?"}], "visual_direction": "Medium shot, the character turns to Toi.", "alt_native": "A friend turns to you."},
                {"location_id": location, "narration_fr": "Un silence.", "dialogue": [], "visual_direction": "Close-up of a glass on the zinc.", "alt_native": "A glass on the counter."},
                {"location_id": location, "narration_fr": "", "dialogue": [{"character_id": character, "text_fr": "Alors, on fait quoi ?"}], "visual_direction": "Close-up, waiting.", "alt_native": "A friend, waiting."},
            ],
            "opening_line_fr": "Tu m'aides ?",
            "suggested_response_fr": _suggested(context, "Oui, je peux t'aider samedi."),
            "hint_native": "Say yes or no, and when.",
            "translation_native": "Can you help me?",
            "capability_key": None,
            **_remembering(context, character, tu=True),
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
        refused = _refuses(text)
        return {
            "outcome": "met",
            "understood_intent": "The learner declines." if refused else "The learner offers help.",
            "evidence_quotes": [text],
            "reply_fr": _reply(
                intent="no" if refused else "yes", keep=False, name=_name_in((payload.get("story") or {}).get("memory"))
            ),
            "needs_clarification": False,
            "resolution_fr": "Vous refusez poliment." if refused else "Vous promettez de venir aider.",
            "summary_native": "You declined." if refused else "You offered to help.",
            "callback_fr": "Vous avez refusé cette fois." if refused else "Vous avez promis d'aider samedi.",
            "commitments": [] if refused else [{"text_fr": "Aider samedi.", "source_quote": text}],
            "resolved_commitment_ids": [],
            "chapter_resolved": (n % 3 == 2),
            "demonstrated_target_ids": [],
            **_reported(text),
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
    from app.services import verdict_appeal

    provider = FakeStoryProvider()
    engine._client = lambda: provider
    verdict_appeal._client = lambda: provider
    print(
        f"[dev-story-engine] fake provider installed; DATABASE_URL={os.environ['DATABASE_URL']}; "
        "no model call can leave this process",
        flush=True,
    )
    uvicorn.run(app, host=args.host, port=args.port, timeout_keep_alive=75)


if __name__ == "__main__":
    main()
