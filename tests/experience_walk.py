"""EXPERIENCE-REVIEW 2026-10-04 — «la vie de l'apprenant»: thirty days of a whole life.

The learner walk (:mod:`tests.learner_walk`) plays the daily journey. A learner's
month is more than that: the sign-up question, the placement when it is offered,
the vocabulary check, La Une every morning, the word drill, the letters of the
Courrier and the Cahier where the level is read. This module plays all of them
through the real HTTP surface, for one persona and one learner *quality*, and
moves **every** clock of the app a day at a time (``app.core.test_clock``: the
word scheduler, a unit's «Tenue», the intake throttle and the forecast read the
shifted «now»; the journey's own clock fixture moved only the journey).

Qualities (deterministic, seeded per learner and day):

* ``strong`` — right on ≈95 % of items, the season's own example replies, the drill
  every day, letters answered the day they arrive;
* ``average`` — phone typography and accent slips on typed answers, one tap in four
  wrong, clumsy-but-French replies, the drill every day;
* ``struggling`` — about half the items right, a first reply in the native language
  now and then, the hint before replying, the drill every other day, one letter
  in two left unanswered.

Nothing calls a model: the story runs on the season suite's scripted provider, the
placement on a grader that scores by the persona's *true* level, the Courrier on
its authored fallbacks. :func:`time_day` turns a recorded day into seconds — what
the learner spends reading French, producing French, reading explanations and
moving through the app — so the review can count the minutes that teach French.
"""
from __future__ import annotations

import json
import random
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import learner_walk as walk
from tests import test_journey_end_to_end as support

# ---------------------------------------------------------------------------
# Who plays
# ---------------------------------------------------------------------------

#: What each persona ticks at sign-up («Votre français ?»). WP-126: five starting
#: points, so every persona declares its true band (B2 and C1 used to tick
#: «comfortable» and live their first days at B1.1).
STARTING_POINT = {"A1": "new", "A2": "some", "B1": "comfortable", "B2": "confident", "C1": "advanced"}
LIFE_QUALITIES: tuple[str, ...] = ("strong", "average", "struggling")
LIFE_DAYS = int(__import__("os").environ.get("LIFE_DAYS", "30"))


def band_number(cefr: str | None) -> int:
    return {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}.get(str(cefr or "")[:2].upper(), 1)


def register_as_onboarding(client: TestClient, persona: walk.Persona) -> tuple[dict[str, str], str]:
    """The sign-up the app actually offers: one question, no level typed in."""

    email = f"life-{persona.key}-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": walk.PASSWORD,
            "native_language": persona.native,
            "starting_point": STARTING_POINT[persona.cefr[:2]],
            "full_name": "Alex",
        },
    )
    assert response.status_code in (200, 201), response.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": walk.PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, email


# ---------------------------------------------------------------------------
# How each quality answers
# ---------------------------------------------------------------------------

#: Share of items a quality gets right (taps; typed answers a little lower).
ACCURACY = {"strong": 0.95, "average": 0.78, "struggling": 0.5}


@dataclass
class LifeAnswerer(walk.Answerer):
    """A learner of one quality on one day (see the module docstring)."""

    native: str = "de"
    help_used: list[str] = field(default_factory=list)

    def recall(self, driver: support.Driver, step: dict[str, Any]) -> tuple[dict[str, Any], str]:
        task = driver.recall_key(step) or {}
        task_type = str(task.get("task_type") or "")
        typed = task_type in {"short_answer", "transform", "dictation"}
        accuracy = ACCURACY[self.quality] - (0.08 if typed else 0.0)
        right = self.rng.random() < accuracy
        if not right:
            return driver.recall_answer(step, correct=False), "wrong"
        if task_type == "short_answer" and not (step.get("prompt") or {}).get("prompt_fr") and task.get("accepted_answers"):
            # WP-130 B: a free sentence («Écrivez une phrase à vous…») is written in the
            # learner's own words: the model is never shown before the answer.
            own = str(task["accepted_answers"][0]).rstrip(" .!?") + ", je crois."
            return {"mode": "text", "text": own}, "right-own-sentence"
        if typed and self.quality != "strong":
            accepted = list(task.get("accepted_answers") or [])
            if accepted and self.rng.random() < 0.6:
                return {"mode": "text", "text": walk._accent_slip(walk._smart_quotes(accepted[0]))}, "right-with-slip"
        return driver.recall_answer(step, correct=True), "right"

    def help_before_reply(self, step: dict[str, Any], asked_in_french: bool) -> list[str]:
        if self.quality != "struggling":
            return []
        if asked_in_french or self.rng.random() < 0.5:
            return ["hint", "suggested_response"]
        return []

    def after_help(self, helps: list[dict[str, Any]], text: str) -> str:
        """A struggling learner leans on the suggested reply, a word or two changed."""

        for got in helps:
            if got.get("kind") == "suggested_response" and got.get("content_fr"):
                return str(got["content_fr"]).replace("Je ", "Moi, je ", 1)
        return text

    def reply(self, step: dict[str, Any], examples: list[str], native: str) -> str:
        if self.quality == "strong" and examples:
            return examples[0]
        if self.quality == "average":
            base = examples[0] if examples else "Je suis d'accord, je reste."
            return walk._smart_quotes(base.lower().replace("é", "e").replace("è", "e"))
        if self.rng.random() < 0.35:
            return "Ich weiß nicht." if native == "de" else "I don't know."
        base = examples[-1] if examples else "Oui. Je reste."
        return base.lower().replace("é", "e").replace("è", "e").replace("à", "a")

    def enrich_reply(self, step: dict[str, Any], text: str, db: Session) -> str:
        """A learner who does what the reply asks: when it targets a grammar unit, the
        strong learner (always) and the average one (one reply in two) add a sentence
        that uses it — the unit's own first example — so «Tenue» can be observed."""

        from app.db.models.grammar import GrammarConcept
        from app.services import grammar_units
        from app.services.grammar_items import plain

        if self.quality == "struggling" or (self.quality == "average" and self.rng.random() < 0.5):
            return text
        if re.search(r"[äöüß]|\bich\b|\bI don't\b", text):
            return text
        for target in (step.get("prompt") or {}).get("targets") or []:
            if target.get("kind") != "grammar":
                continue
            try:
                concept = db.get(GrammarConcept, int(target.get("id")))
            except (TypeError, ValueError):
                continue
            examples = grammar_units.examples(concept) if concept is not None else []
            if examples:
                return f"{text.rstrip()} {plain(examples[0])}"
        return text

    def pick_card(self, cards: list[dict[str, Any]], examples: list[str]) -> str:
        """«Le choix» is answered by tapping a card."""

        labels = [str(card.get("label_fr") or "") for card in cards]
        if self.quality == "strong" and examples and examples[0] in labels:
            return examples[0]
        return labels[self.rng.randrange(len(labels))] if labels else (examples[0] if examples else "Oui.")


# ---------------------------------------------------------------------------
# The surfaces around the day
# ---------------------------------------------------------------------------


def la_une(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    """What the home tab shows before the day begins."""

    response = client.get("/api/v1/daily-journeys/today", headers=headers, params={"timezone": support.TZ})
    if response.status_code != 200:
        return {"status_code": response.status_code}
    body = response.json()
    available = body.get("available") or {}
    headline = body.get("headline") or {}
    return {
        "headline": {key: headline.get(key) for key in ("edition_no", "title_fr", "teaser_fr", "season_title_fr")},
        "available": {key: available.get(key) for key in ("title_fr", "objective_native", "character_name", "estimated_seconds", "level_band")},
        "streak": body.get("streak"),
        "because": body.get("because"),
        "missed_days": body.get("missed_days"),
        "season_premiere": body.get("season_premiere"),
        "interlude": body.get("interlude"),
        "learner_level": body.get("learner_level"),
        # Régulier and Léger get La Forge as an after-day chip (WP-S4).
        "forge": body.get("forge"),
        # WP-128: the one estimate Home shows (core + each extension's own).
        "time_estimate": body.get("time_estimate"),
    }


def day_time_estimate(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    """WP-128: after the day — the plan's estimate as the journey and Home carry it."""

    response = client.get("/api/v1/daily-journeys/today", headers=headers, params={"timezone": support.TZ})
    if response.status_code != 200:
        return {"status_code": response.status_code}
    body = response.json()
    plan = (body.get("journey") or {}).get("time_estimate") or {}
    return {
        **plan,
        "home": body.get("time_estimate"),
        "recap_core_seconds": (((body.get("journey") or {}).get("recap")) or {}).get("estimated_core_seconds"),
    }


class LevelGrader:
    """The placement's grader for a persona whose real level is ``true_band``."""

    def __init__(self, true_band: str, quality: str) -> None:
        self.true_band = true_band
        self.quality = quality
        self.calls = 0

    def generate_error_detection(self, messages, **kwargs):
        from types import SimpleNamespace

        from app.services.placement import band_index

        payload = json.loads(messages[0]["content"])
        prompt_band = str(payload.get("prompt_band") or "A1.1")
        gap = band_index(self.true_band) - band_index(prompt_band)
        score = 3.6 if gap > 0 else 2.8 if gap == 0 else 1.2
        if self.quality == "struggling":
            score -= 0.6
        self.calls += 1
        return SimpleNamespace(
            content=json.dumps(
                {
                    "score_0_4": round(score, 1),
                    "demonstrated_band": self.true_band,
                    "dimensions": {"range": round(score), "accuracy": round(score), "coherence": round(score), "task": round(score)},
                    "evidence_fr": "réponse au niveau",
                    "off_task": False,
                }
            ),
            model="walk-grader",
            provider="test",
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            cost=0.0,
        )


#: A placement answer a learner of each band could write (the grader does not read it).
PLACEMENT_ANSWERS = {
    1: "Je m'appelle Alex. J'habite à Berlin. J'aime le café.",
    2: "Le week-end dernier, je suis allé au marché avec ma sœur et nous avons acheté des fruits.",
    3: "Si j'avais plus de temps, je voyagerais davantage, parce que j'aime découvrir d'autres cultures et parler avec les gens.",
    4: "Bien que le télétravail présente des avantages évidents, je crains qu'il n'isole les salariés les plus jeunes, qui ont besoin d'apprendre auprès de leurs collègues.",
    5: "À supposer que la réforme aboutisse, encore faudrait-il qu'elle s'accompagne de moyens à la hauteur des ambitions affichées, faute de quoi elle resterait lettre morte.",
}


def take_placement(client: TestClient, headers: dict[str, str], monkeypatch: Any, *, true_band: str, quality: str) -> dict[str, Any]:
    from app.services import placement as placement_module

    grader = LevelGrader(true_band, quality)
    monkeypatch.setattr(placement_module.PlacementService, "_get_llm_service", lambda self: grader)
    started = client.post("/api/v1/placement/start", headers=headers, json={"restart": False})
    if started.status_code != 200:
        return {"status_code": started.status_code, "error": started.text[:200]}
    envelope = started.json()
    turns: list[dict[str, Any]] = []
    for _ in range(8):
        prompt = envelope.get("prompt")
        if not prompt or envelope.get("status") != "in_progress":
            break
        answer = PLACEMENT_ANSWERS[min(5, band_number(true_band))]
        turns.append({"band": prompt.get("band"), "prompt_fr": prompt.get("prompt_fr"), "hint_fr": prompt.get("hint_fr"), "answer": answer})
        response = client.post(
            f"/api/v1/placement/{envelope['session_id']}/respond",
            headers=headers,
            json={"answer": answer, "turn_index": prompt.get("index", 0)},
        )
        if response.status_code != 200:
            break
        envelope = response.json()
    return {
        "status": envelope.get("status"),
        "level": envelope.get("level"),
        "confidence": envelope.get("confidence"),
        "turns": turns,
        "estimate": {key: (envelope.get("estimate") or {}).get(key) for key in ("status", "level", "confidence", "graded_turns")},
    }


def take_band_checks(client: TestClient, db: Session, headers: dict[str, str], email: str, *, quality: str, rng: random.Random) -> list[dict[str, Any]]:
    """One visit of the top-down vocabulary check (WP-127), as the screen drives it.

    The ladder says which sub-band to check; the learner answers at the quality's
    accuracy and follows it down after a miss, until it stops (a pass), pauses (the
    visit's two checks are spent) or runs out."""

    from app.db.models.user import User
    from app.services import band_check

    user = db.query(User).filter(User.email == email).one()
    results: list[dict[str, Any]] = []
    accuracy = {"strong": 0.97, "average": 0.92, "struggling": 0.78}[quality]
    for _ in range(band_check.MAX_CHECKS_PER_VISIT + 1):
        ladder = client.get("/api/v1/vocabulary/band-check/ladder", headers=headers)
        if ladder.status_code != 200:
            results.append({"status_code": ladder.status_code})
            break
        band = ladder.json().get("next")
        if not band:
            break
        start = client.get(f"/api/v1/vocabulary/band-check/{band}", headers=headers)
        if start.status_code != 200:
            results.append({"sub_band": band, "status_code": start.status_code})
            break
        body = start.json()
        attempt = band_check.next_attempt(db, user, band)
        key = {item["id"]: item["answer"] for item in band_check._items(user, band, attempt=attempt)}
        items = body.get("items") or []
        answers = {}
        for item in items:
            right = key.get(item["id"])
            if right is None:
                answers[item["id"]] = None
            elif rng.random() < accuracy:
                answers[item["id"]] = right
            else:
                answers[item["id"]] = (right + 1) % max(1, len(item.get("options") or [1]))
        submitted = client.post(
            f"/api/v1/vocabulary/band-check/{band}",
            headers=headers,
            json={"answers": answers, "attempt_id": body.get("attempt_id")},
        )
        result = submitted.json() if submitted.status_code == 200 else {}
        results.append(
            {
                "sub_band": band,
                "items": [{"fr": item.get("fr"), "options": item.get("options")} for item in items[:3]],
                "item_count": len(items),
                "attempt_id": body.get("attempt_id"),
                "correct": result.get("correct"),
                "total": result.get("total"),
                "passed": result.get("passed"),
                "credited_words": result.get("credited_words"),
                "credited_sampled": result.get("credited_sampled"),
                "credited_inferred": result.get("credited_inferred"),
                "ladder_status": result.get("ladder_status"),
                "status_code": None if submitted.status_code == 200 else submitted.status_code,
            }
        )
    return results


def drill(client: TestClient, db: Session, headers: dict[str, str], *, quality: str, rng: random.Random) -> dict[str, Any]:
    """One session of the word drill, as ``pages/vocabulary/review.tsx`` asks for it."""

    from app.db.models.vocabulary import VocabularyWord
    from app.services.vocab_fsrs import card_french

    params = {"limit": 50, "due_limit": 30, "fragile_limit": 12, "new_limit": 8, "topic_limit": 8, "linked_limit": 8}
    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=params)
    if response.status_code != 200:
        return {"status_code": response.status_code}
    context = response.json()
    seen: set[int] = set()
    cards: list[dict[str, Any]] = []
    for bucket in ("due_words", "fragile_words", "new_words", "topic_compatible_words", "linked_words"):
        for item in context.get(bucket) or []:
            if item["word_id"] in seen:
                continue
            seen.add(item["word_id"])
            cards.append(item)
    reviewed: list[dict[str, Any]] = []
    accuracy = {"strong": 0.92, "average": 0.8, "struggling": 0.62}[quality]
    for item in cards:
        word = db.get(VocabularyWord, item["word_id"])
        french = (card_french(word) or [item.get("word")])[0] if word is not None else item.get("word")
        is_new = bool(item.get("is_new")) or item.get("bucket") == "new"
        right = is_new or rng.random() < accuracy
        answer = french if right else "je sais pas"
        submitted = client.post(
            "/api/v1/anki/review",
            headers=headers,
            json={
                "word_id": item["word_id"],
                "rating": 2,
                # A new card is shown first, then turned: a self-rated flashcard.
                "format": "flashcard" if is_new else "typed",
                "answer_text": None if is_new else answer,
            },
        )
        body = submitted.json() if submitted.status_code == 200 else {}
        reviewed.append(
            {
                "word": item.get("word"),
                "translation": item.get("translation"),
                "bucket": item.get("bucket"),
                "ladder": item.get("ladder"),
                "new": is_new,
                "answer": answer,
                "correct": body.get("correct"),
                "note_native": body.get("note_native"),
                "interval_days": body.get("interval_days"),
                "status_code": submitted.status_code,
            }
        )
    # WP-131: what the day's allowance still held after this deck (the drill's
    # «Encore N mots» continuation; the walk records it, it does not take it).
    return {"summary": context.get("summary"), "cards": reviewed, "new_words_left_today": context.get("new_words_left_today")}


#: What each quality writes back to a correspondent.
LETTER_REPLIES = {
    "strong": {
        1: "Bonjour ! Merci pour ton message. Je suis à Paris pour une semaine. J'aime le café du Mistral. À bientôt !",
        2: "Merci pour ta lettre ! Hier, je suis allé au Mistral et j'ai parlé avec Lila. Je reste encore un peu à Paris.",
        3: "Merci pour ta lettre. Depuis que je suis arrivé, je découvre le quartier et j'ai l'impression que les gens me font confiance. Je te raconterai la suite.",
        4: "Merci pour ta lettre, qui m'a fait sourire. Bien que je n'aie pas encore décidé ce que je ferai de l'appartement, je commence à comprendre ce qu'il représentait pour Odile.",
        5: "Ta lettre tombe à pic : j'hésitais justement à t'écrire. Quoi que j'en dise, je m'attache à ce quartier, et il se pourrait bien que je reste plus longtemps que prévu.",
    },
    "average": {
        1: "bonjour, merci pour ton message. je suis a paris, j'aime le cafe",
        2: "merci pour ta lettre. hier je suis alle au mistral et je parle avec lila",
        3: "merci pour ta lettre. depuis que je suis arrive je decouvre le quartier, les gens sont gentil",
        4: "merci pour ta lettre. bien que je n'ai pas decide, je comprend ce que l'appartement represente",
        5: "ta lettre tombe bien. je m'attache au quartier, et peut-etre je reste plus longtemps",
    },
    "struggling": {
        1: "bonjour. merci. je suis a paris",
        2: "merci. je suis au mistral. c'est bien",
        3: "merci pour la lettre. je reste a paris, je pense",
        4: "merci pour la lettre. je ne sais pas encore pour l'appartement",
        5: "merci pour ta lettre. je reste peut-etre",
    },
}


def courrier(client: TestClient, headers: dict[str, str], *, quality: str, band: int, rng: random.Random, answered: set[str]) -> dict[str, Any]:
    """Open the Courrier; answer a waiting letter once (struggling: one in two)."""

    response = client.get("/api/v1/missions/today", headers=headers)
    if response.status_code != 200:
        return {"status_code": response.status_code}
    body = response.json()
    waiting = [m for m in (body.get("active_mission"), body.get("weekly_mission")) if m and m.get("status") not in ("completed",)]
    record: dict[str, Any] = {"waiting": len(waiting), "letters": []}
    for mission in waiting:
        if mission["id"] in answered:
            continue
        messenger = (mission.get("prompt_payload") or {}).get("messenger") or {}
        letter = {
            "id": mission["id"],
            "cadence": mission.get("cadence"),
            "title": mission.get("title"),
            "brief": mission.get("brief"),
            "contact_name": messenger.get("contact_name"),
            "opening_message": messenger.get("opening_message"),
            "objectives": [o.get("label") or o.get("text") for o in mission.get("objectives") or []],
            "target_vocabulary": [t.get("word") or t.get("lemma") for t in mission.get("target_vocabulary") or []],
            # WP-125B: what the letter is (level, reach, request, follow-up) and what it costs.
            "letter_fit": mission.get("letter_fit"),
            "estimated_seconds": mission.get("estimated_seconds"),
            "chain_note": messenger.get("chain_note"),
            "follow_up_of": (mission.get("letter_fit") or {}).get("follow_up_of"),
        }
        record["letters"].append(letter)
        if quality == "struggling" and rng.random() < 0.5:
            letter["skipped"] = True
            continue
        text = LETTER_REPLIES[quality][min(5, band)]
        turn = client.post(f"/api/v1/missions/{mission['id']}/turns", headers=headers, json={"text": text, "mode": "chat"})
        letter["reply"] = text
        if turn.status_code == 200:
            turn_body = turn.json()
            correction = turn_body.get("correction") or {}
            letter["answer_back"] = (turn_body.get("assistant_turn") or {}).get("text")
            letter["correction"] = {
                key: correction.get(key)
                for key in ("verdict", "score_0_4", "corrected_answer", "objective_progress", "missing_targets", "errata")
            }
        else:
            letter["turn_status"] = turn.status_code
        done = client.post(f"/api/v1/missions/{mission['id']}/complete", headers=headers)
        if done.status_code == 200:
            recap = done.json().get("recap") or {}
            letter["recap"] = {key: recap.get(key) for key in ("outcome", "measured", "saved_to_srs", "correspondent_mood_after")}
        answered.add(mission["id"])
    return record


def cahier(client: TestClient, headers: dict[str, str], *, full: bool) -> dict[str, Any]:
    """The level and its forecast every day; the grammar notebook and can-dos on review days."""

    out: dict[str, Any] = {}
    cefr = client.get("/api/v1/progress/cefr", headers=headers)
    if cefr.status_code == 200:
        body = cefr.json()
        out["cefr"] = {
            key: body.get(key)
            for key in ("estimate", "estimate_source", "declared_level", "level_label", "coverage", "forecast", "checkpoint", "next_can_do")
        }
    if full:
        # WP-130 A: the whole catalogue, with each unit's stage and the band it
        # counts for in the level, so the notebook and the level can be compared.
        notebook = client.get("/api/v1/grammar/notebook", params={"limit": 500}, headers=headers)
        if notebook.status_code == 200:
            items = notebook.json().get("items") if isinstance(notebook.json(), dict) else notebook.json()
            out["notebook"] = [
                {
                    key: item.get(key)
                    for key in (
                        "id", "display_title", "level", "level_band", "stage", "stage_label", "state_label",
                        "mastery", "next_review", "due_errata_count", "held_missing",
                    )
                }
                for item in (items or [])
            ]
        can_dos = client.get("/api/v1/can-dos", headers=headers)
        if can_dos.status_code == 200:
            out["can_dos"] = can_dos.json()
    return out


def grammar_life(db: Session, email: str) -> list[dict[str, Any]]:
    """Every introduced unit's «Tenue» evidence (WP-L4): what holds it, and what is missing."""

    from app.db.models.grammar import GrammarConcept, UserGrammarProgress
    from app.db.models.user import User

    user = db.query(User).filter(User.email == email).one()
    rows = (
        db.query(UserGrammarProgress, GrammarConcept)
        .join(GrammarConcept, GrammarConcept.id == UserGrammarProgress.concept_id)
        .filter(UserGrammarProgress.user_id == user.id)
        .all()
    )

    def iso(value: Any) -> str | None:
        return value.isoformat()[:10] if value is not None else None

    return [
        {
            "unit": concept.external_id,
            "level": concept.level,
            "introduced": iso(getattr(progress, "introduced_at", None)),
            "free_use_first": iso(getattr(progress, "free_use_first_at", None)),
            "free_use_last": iso(getattr(progress, "free_use_last_at", None)),
            "spaced_success": iso(getattr(progress, "spaced_success_at", None)),
            "held": iso(getattr(progress, "held_at", None)),
            "reps": getattr(progress, "reps", None),
            "stability": round(float(getattr(progress, "stability", 0) or 0), 1),
        }
        for progress, concept in rows
    ]


def season_cursor(db: Session, email: str) -> dict[str, Any]:
    """WP-124b: where the learner's season stands after the day (``{}`` off a season):
    how many season days were played, the last one, and the gaps cut short."""

    from app.db.models.user import User
    from app.services import living_story as engine
    from app.services.season.clock import SEASON_KEY, played_log, shortened_gaps

    user = db.query(User).filter(User.email == email).one()
    thread = engine._active_thread(db, user)
    if thread is not None:
        db.refresh(thread)
    state = (((thread.state or {}) if thread else {}).get(engine.STATE_KEY) or {}).get(SEASON_KEY) or {}
    if not isinstance(state, dict) or not state.get("id"):
        return {}
    log = played_log(state)
    return {
        "id": state["id"],
        "played": len(log),
        "last": log[-1].get("key") if log else None,
        "shortened": sorted(shortened_gaps(state)),
        "premises": len(state.get("premises") or []),
    }


def outage_days(persona_key: str, quality: str, days: int, rate: float) -> set[int]:
    """WP-124b: the days a forced outage loses (deterministic per life). ``rate`` ≥ 1
    loses every generated day; 0 none. Read from ``WALK_FAIL_RATE`` by the life walk."""

    if rate <= 0:
        return set()
    return {
        day
        for day in range(1, days + 1)
        if rate >= 1 or random.Random(f"outage-{persona_key}-{quality}-{day}").random() < rate
    }


def director_down(provider: Any, monkeypatch: Any) -> None:
    """Every scene draft refused for the rest of ``monkeypatch``'s context (the
    WP-124a test's forced failure: a guard refuses the draft)."""

    from app.services import living_story as engine

    original = provider.generate_chat_completion

    def refused(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "SceneDraft":
            raise engine.StoryUnavailable("walk outage: forced")
        return original(messages, **kwargs)

    monkeypatch.setattr(provider, "generate_chat_completion", refused)


# ---------------------------------------------------------------------------
# Time: what a minute of each step costs this learner
# ---------------------------------------------------------------------------

#: Reading French at the learner's own level, words a minute (A1 … C1).
FR_READ_WPM = {1: 45, 2: 70, 3: 100, 4: 140, 5: 180}
#: Reading the learner's own language.
NATIVE_READ_WPM = 220
#: Composing French on a phone, words a minute, thinking included.
FR_COMPOSE_WPM = {1: 5, 2: 8, 3: 11, 4: 15, 5: 19}
#: A tap: seeing the options and deciding (seconds), before reading time.
TAP_DECIDE_SECONDS = 2.0
#: Moving on: «Weiter», a page turn, waiting for the next screen.
NAV_SECONDS = 1.5
SLOWER = {"strong": 1.0, "average": 1.12, "struggling": 1.4}

_WORDS = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


def words(text: Any) -> int:
    return len(_WORDS.findall(str(text or "")))


@dataclass
class Clockwork:
    """Seconds by kind: French in, French out (retrieval/production), explanation
    (rules and corrections in the learner's language), support (instructions,
    tasks, translations) and overhead (navigation)."""

    fr_input: float = 0.0
    fr_output: float = 0.0
    explanation: float = 0.0
    support: float = 0.0
    overhead: float = 0.0

    def add(self, other: Clockwork) -> None:
        for key in self.__dataclass_fields__:
            setattr(self, key, getattr(self, key) + getattr(other, key))

    @property
    def total(self) -> float:
        return self.fr_input + self.fr_output + self.explanation + self.support + self.overhead

    @property
    def french(self) -> float:
        return self.fr_input + self.fr_output

    def as_dict(self) -> dict[str, float]:
        return {key: round(getattr(self, key), 1) for key in (*self.__dataclass_fields__, "total", "french")}


class Timer:
    def __init__(self, cefr: str, quality: str) -> None:
        self.band = min(5, band_number(cefr))
        self.slow = SLOWER[quality]
        self.translated = self.band <= 2

    def read_fr(self, text: Any) -> float:
        return words(text) / FR_READ_WPM[self.band] * 60 * self.slow

    def read_native(self, text: Any) -> float:
        return words(text) / NATIVE_READ_WPM * 60 * self.slow

    def compose(self, text: Any) -> float:
        return max(4.0, words(text) / FR_COMPOSE_WPM[self.band] * 60 * self.slow)

    def recall(self, event: dict[str, Any]) -> Clockwork:
        prompt = event["step"].get("prompt") or {}
        clock = Clockwork()
        clock.support += self.read_native(prompt.get("instruction_native")) + self.read_native(prompt.get("goal_native"))
        clock.fr_input += self.read_fr(prompt.get("prompt_fr")) + self.read_fr(prompt.get("source_fr"))
        options = prompt.get("options") or []
        task = prompt.get("task_type")
        answer = ((event.get("answer") or {}).get("input")) or {}
        if task in ("short_answer", "transform", "dictation"):
            clock.fr_output += 3.0 * self.slow + len(str(answer.get("text") or "")) * 0.35 * self.slow
        elif task in ("tiles", "word_bank", "unscramble", "match_pairs"):
            clock.fr_input += sum(self.read_fr(o.get("text_fr")) for o in options if o.get("side") != "native")
            clock.support += sum(self.read_native(o.get("text_fr")) for o in options if o.get("side") == "native")
            clock.fr_output += (1.6 * len(options) if task == "match_pairs" else 1.8 * len(options)) * self.slow
        else:
            clock.fr_input += sum(self.read_fr(o.get("text_fr")) for o in options if o.get("side") != "native")
            clock.support += sum(self.read_native(o.get("text_fr")) for o in options if o.get("side") == "native")
            clock.fr_output += TAP_DECIDE_SECONDS * self.slow
        result = event.get("result") or {}
        correction = result.get("correction") or {}
        if correction:
            clock.fr_input += self.read_fr(correction.get("corrected_fr"))
            clock.explanation += self.read_native(correction.get("note_native"))
        if result.get("slip_note_native"):
            clock.explanation += self.read_native(result.get("slip_note_native"))
        clock.overhead += NAV_SECONDS
        return clock

    def scene(self, event: dict[str, Any]) -> Clockwork:
        prompt = event["step"].get("prompt") or {}
        clock = Clockwork()
        clock.fr_input += self.read_fr(prompt.get("setup_fr"))
        clock.support += self.read_native(prompt.get("objective_native"))
        if self.translated:
            clock.support += 0.5 * self.read_native(prompt.get("setup_native"))
        page = event.get("page") or []
        for panel in page:
            clock.fr_input += self.read_fr(panel.get("narration_fr"))
            for line in panel.get("dialogue") or []:
                clock.fr_input += self.read_fr(line.get("text_fr"))
                if self.translated:
                    clock.support += 0.5 * self.read_native(line.get("text_native"))
            clock.overhead += 2.0  # looking at the drawing, turning the panel
        if not page:
            clock.fr_input += self.read_fr(prompt.get("character_line_fr"))
        clock.overhead += NAV_SECONDS
        return clock

    def respond(self, event: dict[str, Any]) -> Clockwork:
        prompt = event["step"].get("prompt") or {}
        result = event.get("result") or {}
        clock = Clockwork()
        if int(prompt.get("turn_index") or 0) == 0:
            clock.fr_input += self.read_fr(prompt.get("character_line_fr"))
        clock.support += self.read_native(prompt.get("objective_native"))
        for got in event.get("help") or []:
            clock.support += self.read_native(got.get("content_native"))
            clock.fr_input += self.read_fr(got.get("content_fr"))
            clock.overhead += NAV_SECONDS
        text = ((event.get("answer") or {}).get("input") or {}).get("text")
        if prompt.get("choices"):
            clock.fr_input += sum(self.read_fr(c.get("label_fr")) for c in prompt["choices"])
            clock.fr_output += TAP_DECIDE_SECONDS * 2 * self.slow
        elif re.search(r"[äöüß]|\bich\b|\bI don't\b", str(text or "")):
            clock.support += 6.0 * self.slow  # typed in the native language: no French practised
        else:
            clock.fr_output += self.compose(text)
        for line in result.get("character_lines") or []:
            clock.fr_input += self.read_fr(line.get("text_fr"))
        if not result.get("character_lines"):
            clock.fr_input += self.read_fr(result.get("character_reply_fr"))
        correction = result.get("correction") or {}
        if correction:
            clock.explanation += self.read_native(correction.get("note_native"))
        clock.overhead += NAV_SECONDS
        return clock

    def rule(self, event: dict[str, Any], native: str, chrome: str) -> Clockwork:
        prompt = event["step"].get("prompt") or {}
        card = prompt.get("rule_card") or {}
        clock = Clockwork()
        language = chrome if chrome in ("en", "de", "fr") else native
        clock.explanation += self.read_native(prompt.get("title_native"))
        clock.explanation += self.read_native((card.get("rule") or {}).get(language))
        clock.fr_input += self.read_fr((card.get("example") or {}).get("fr"))
        if self.translated:
            clock.support += self.read_native(((card.get("example") or {}).get("tr") or {}).get(native))
        pattern = card.get("pattern") or {}
        for row in pattern.get("rows") or []:
            clock.fr_input += self.read_fr(row.get("fr"))
        contrast = card.get("contrast") or {}
        clock.fr_input += self.read_fr(contrast.get("wrong")) + self.read_fr(contrast.get("right"))
        if self.slow > 1.0:
            # Average and struggling learners open «Mehr» once.
            clock.explanation += self.read_native((card.get("more") or {}).get(language))
        clock.overhead += NAV_SECONDS * 2
        return clock

    def resolution(self, event: dict[str, Any]) -> Clockwork:
        prompt = event["step"].get("prompt") or {}
        clock = Clockwork()
        clock.fr_input += self.read_fr(prompt.get("character_line_fr")) + self.read_fr(prompt.get("register_note_fr"))
        clock.support += self.read_native(prompt.get("summary_native")) + self.read_native(prompt.get("register_reason_native"))
        clock.overhead += NAV_SECONDS
        return clock


def time_journey(transcript: dict[str, Any], *, quality: str) -> tuple[Clockwork, list[dict[str, Any]]]:
    """``(the day's clockwork, per step: kind, seconds, the planner's estimate)``."""

    timer = Timer(transcript.get("learner_level") or transcript["cefr"], quality)
    chrome = "fr" if timer.band >= 3 else transcript["native"]
    total = Clockwork()
    steps: list[dict[str, Any]] = []
    for event in transcript["events"]:
        kind = event["step"]["kind"]
        if kind == "recall":
            clock = timer.recall(event)
        elif kind == "scene":
            clock = timer.scene(event)
        elif kind == "respond":
            clock = timer.respond(event)
        elif kind == "rule":
            clock = timer.rule(event, transcript["native"], chrome)
        elif kind == "resolution":
            clock = timer.resolution(event)
        else:
            clock = Clockwork(overhead=NAV_SECONDS)
        total.add(clock)
        steps.append({"kind": kind, "task": (event["step"].get("prompt") or {}).get("task_type"), "seconds": round(clock.total, 1), "estimated": event.get("estimated_seconds")})
    return total, steps


def time_drill(record: dict[str, Any], cefr: str, quality: str) -> Clockwork:
    timer = Timer(cefr, quality)
    clock = Clockwork()
    for card in record.get("cards") or []:
        clock.support += timer.read_native(card.get("translation"))
        if card.get("new"):
            clock.fr_input += timer.read_fr(card.get("word")) + 4.0 * timer.slow  # meet the word, hear it, turn it
        else:
            clock.fr_output += 4.0 * timer.slow + len(str(card.get("answer") or "")) * 0.35 * timer.slow
            clock.fr_input += timer.read_fr(card.get("word"))
            clock.explanation += timer.read_native(card.get("note_native"))
        clock.overhead += NAV_SECONDS
    return clock


def time_letters(record: dict[str, Any], cefr: str, quality: str) -> Clockwork:
    timer = Timer(cefr, quality)
    clock = Clockwork()
    for letter in record.get("letters") or []:
        clock.fr_input += timer.read_fr(letter.get("opening_message")) + timer.read_fr(letter.get("brief"))
        clock.support += sum(timer.read_native(o) for o in letter.get("objectives") or [])
        if letter.get("reply"):
            clock.fr_output += timer.compose(letter["reply"])
            clock.fr_input += timer.read_fr(letter.get("answer_back"))
            correction = letter.get("correction") or {}
            clock.fr_input += timer.read_fr(correction.get("corrected_answer"))
        clock.overhead += NAV_SECONDS * 3
    return clock


def time_onboarding(day: dict[str, Any], cefr: str, quality: str) -> Clockwork:
    timer = Timer(cefr, quality)
    clock = Clockwork()
    placement = day.get("placement") or {}
    for turn in placement.get("turns") or []:
        clock.fr_input += timer.read_fr(turn.get("prompt_fr")) + timer.read_fr(turn.get("hint_fr"))
        clock.fr_output += timer.compose(turn.get("answer"))
        clock.overhead += NAV_SECONDS
    for check in day.get("band_check") or []:
        count = int(check.get("item_count") or 0)
        clock.fr_input += count * timer.read_fr("le mot")
        clock.support += count * timer.read_native("eins zwei drei vier")
        clock.fr_output += count * TAP_DECIDE_SECONDS * timer.slow
        clock.overhead += NAV_SECONDS * 2
    return clock


__all__ = [
    "LIFE_DAYS",
    "LIFE_QUALITIES",
    "Clockwork",
    "LifeAnswerer",
    "Timer",
    "cahier",
    "courrier",
    "day_time_estimate",
    "director_down",
    "drill",
    "la_une",
    "outage_days",
    "register_as_onboarding",
    "season_cursor",
    "take_band_checks",
    "take_placement",
    "time_drill",
    "time_journey",
    "time_letters",
    "time_onboarding",
]
