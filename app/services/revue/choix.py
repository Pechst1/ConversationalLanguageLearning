"""«Papier · le choix» (owner 2026-11-22): pedagogy picks the story, the learner chooses.

The first real run found the Papier an island: it ignored the day's grammar rule, the
learner's due words and their interests. Here, while ``REVUE_PEDAGOGY_PICK_ENABLED`` is on, a
story scores by what this learner needs today, all of it read from what the app already holds
(no model call, deterministic):

* **due words** — the learner's due cards (``ProgressService.get_vocabulary_due_context``, and
  the words met in earlier Papiers, ``kept_words.words_due_by_place``) that the story's French
  at their band contains (:func:`story_french`);
* **the day's rule** — ``day_rules.for_turn``'s ``today`` (on a Papier day the planner may leave
  none: then the most recent of ``recent``), its detectors run over that same French;
* **interests** — ``users.interests`` against the story's topic (``encounter.INTEREST_TOPICS``)
  and its words: a real weight, not a tie-break;
* **recency** — the topic of the learner's last Papier is set back (the old ranking's one key).

Each scored story carries a small :func:`why` record (which due words, which rule, which
interest): the session keeps it on its dossier choice, the offer carries it so the front page can
say, in the mother tongue, why a story is offered. The assignment dealt prefers the one whose own
material exercises the rule (:func:`prefer`), and the rule's kind (questions → «Le micro», an
opinion or connectors → «Au comptoir»…); the seed decides the rest, as before.

``REVUE_CHOICE_ENABLED``: the offer's :func:`front_page` — up to three stories, the top of the
ranking, different rubrics where possible.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from app.services.revue.dossier import EditorialDossier, comptoir_band

#: How many due cards are matched against the stories.
DUE_SCAN = 40
#: How many due words a story can score (and its ``why`` names).
DUE_CAP = 4
W_DUE = 2
W_RULE = 4
W_RULE_RICH = 1  # three uses of the form or more
W_TOPIC = 5
W_INTEREST_WORD = 2
P_LAST_TOPIC = 3
P_WEEK_TOPIC = 1
WEEK_SECONDS = 7 * 24 * 3600

#: Which assignments suit which kind of rule (substrings of the catalogue's ids, ``FR2_…``).
AFFINITY: dict[str, tuple[str, ...]] = {
    "comptoir": ("OPINION", "CONNECTORS", "CAUSE", "SUBJ", "COMPARATIVE", "SUPERLATIVE", "ADVICE", "SI_TYPE"),
    "micro": ("QUESTION", "INVERSION"),
    "fil": ("PC_", "PASSE", "NARRATION", "IMP_VS_PC", "IMPARFAIT", "PLUS_QUE_PARFAIT", "TEMPORAL", "TIME_PREP"),
    "titre": ("NUMBERS", "DAYS_DATES", "ADJ_AGREEMENT"),
    "intox": ("NEGATION", "NEG_"),
}
W_AFFINITY = 3


def pedagogy_enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "REVUE_ENABLED", False) and getattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", False))


def choice_enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "REVUE_ENABLED", False) and getattr(settings, "REVUE_CHOICE_ENABLED", False))


@dataclass(frozen=True)
class Focus:
    """What this learner needs today: their band (``a1``/``a2``/``b1``), their due words (most
    due first), the rule (``{id, name, rule, detectors}``; ``today`` False when it is the most
    recent of the week's, not the day's own) and their interests."""

    band: str = "a2"
    due: tuple[str, ...] = ()
    rule: dict[str, Any] | None = None
    rule_today: bool = False
    interests: tuple[str, ...] = ()
    language: str = "en"
    last_seen: dict[str, float] = field(default_factory=dict)


def _band_of(user: Any) -> str:
    from app.services.chrome_language import level_band

    return comptoir_band(level_band(getattr(user, "cefr_estimate", None)) or "A1")


def _interests(user: Any) -> tuple[str, ...]:
    return tuple(part.strip().lower() for part in str(getattr(user, "interests", "") or "").split(",") if part.strip())


def _due_words(db: Any, user: Any, now: datetime) -> tuple[str, ...]:
    """The learner's due words, most due first: the due cards, then those met in a Papier."""

    words: list[str] = []
    try:
        from app.services.day_words import card_direction
        from app.services.progress import ProgressService

        with db.begin_nested():
            payload = ProgressService(db).get_vocabulary_due_context(
                user=user, limit=DUE_SCAN, due_limit=DUE_SCAN, fragile_limit=0, new_limit=0,
                topic_limit=0, linked_limit=0, direction=card_direction(user), now=now,
            )
        words += [str(card.get("word") or "") for card in payload.get("due_words") or []]
    except Exception as exc:  # noqa: BLE001 - a missing word costs the score, never the Papier
        logger.warning("revue choix: due words unavailable ({})", type(exc).__name__)
    try:
        from app.services.kept_words import words_due_by_place

        with db.begin_nested():
            by_place = words_due_by_place(db, user_id=user.id, now=now)
        words += [w.word for group in by_place.values() for w in group]
    except Exception as exc:  # noqa: BLE001
        logger.warning("revue choix: Papier words unavailable ({})", type(exc).__name__)
    seen: list[str] = []
    for word in words:
        if word.strip() and word.strip() not in seen:
            seen.append(word.strip())
    return tuple(seen)


def _rule(db: Any, user: Any, language: str, now: datetime) -> tuple[dict[str, Any] | None, bool]:
    """The day's rule, else the most recent of the week's (a Papier day may teach none)."""

    from app.services import day_rules

    rules = day_rules.for_turn(db, user, control_language=language, now=now) or {}
    today = rules.get("today")
    if isinstance(today, dict) and today.get("detectors"):
        return today, True
    recent = next((row for row in rules.get("recent") or [] if isinstance(row, dict) and row.get("detectors")), None)
    return recent, False


def focus_for(db: Any, user: Any, *, last_seen: dict[str, float] | None = None, now: datetime | None = None) -> Focus:
    from app.services.chrome_language import user_mother_tongue
    from app.services.journey_contracts import normalize_control_language

    now = now or datetime.now(UTC)
    language = normalize_control_language(user_mother_tongue(user))
    try:
        rule, today = _rule(db, user, language, now)
    except Exception as exc:  # noqa: BLE001 - never lose the Papier to a rule
        logger.warning("revue choix: rule unavailable ({})", type(exc).__name__)
        rule, today = None, False
    return Focus(band=_band_of(user), due=_due_words(db, user, now), rule=rule, rule_today=today,
                 interests=_interests(user), language=language, last_seen=dict(last_seen or {}))


# ---------------------------------------------------------------------------
# The story's French, as this learner will read it
# ---------------------------------------------------------------------------


def _strings(value: Any, band: str) -> list[str]:
    """Every French line of a desk's material at ``band`` (a parked desk: the plain dump)."""

    out: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("a1", "a2", "b1", "b2") and key != band and isinstance(item, dict):
                continue
            if key in ("fr", "wrong_fr", "right_fr") and isinstance(item, str):
                out.append(item)
            else:
                out += _strings(item, band)
    elif isinstance(value, list):
        for item in value:
            out += _strings(item, band)
    return out


def _material_of(key: str, dossier: EditorialDossier) -> Any:
    """What assignment ``key`` plays on ``dossier``: its own desk's, else the evergreen's."""

    if key == "comptoir":
        return dossier.comptoir
    from app.services.revue.fil import wire_of
    from app.services.revue.intox import intox_of
    from app.services.revue.micro import micro_of
    from app.services.revue.photo import photo_of
    from app.services.revue.titre import titre_of

    reader = {"fil": wire_of, "titre": titre_of, "intox": intox_of, "micro": micro_of, "photo": photo_of}.get(key)
    return reader(dossier) if reader is not None else None


def assignment_french(key: str, dossier: EditorialDossier, band: str) -> str:
    """The French the learner reads and writes in assignment ``key`` of ``dossier`` at ``band``."""

    material = _material_of(key, dossier)
    if material is None:
        return ""
    if key == "comptoir":
        lines = [material.question.fr, *(guest.take.for_band(band).fr for guest in material.guests),
                 material.phrase.for_band(band).fr]
        return " ".join(lines)
    if key == "titre":
        return " ".join([*(h.for_band(band).fr for h in material.headlines), material.build.frame.fr,
                         material.phrase.for_band(band).fr])
    return " ".join(_strings(material.model_dump(mode="json"), band))


def story_french(dossier: EditorialDossier, band: str, *, keys: Sequence[str] = ()) -> str:
    """The story at ``band``: its title, its lead at A1/A2 (B1 reads the summary), and the
    material of the assignments ``keys`` it carries."""

    leads = dossier.leads
    lead = getattr(leads, band, None) if leads is not None and band in ("a1", "a2") else None
    parts = [dossier.title_fr, (leads.headline_fr if leads is not None else None) or "",
             lead.fr if lead is not None else dossier.summary_fr]
    parts += [assignment_french(key, dossier, band) for key in keys]
    return " ".join(part for part in parts if part)


def rule_uses(rule: dict[str, Any] | None, text: str) -> int:
    from app.services.grammar_units import detector_spans

    if not rule:
        return 0
    return len(detector_spans(list(rule.get("detectors") or []), text))


def interest_hit(dossier: EditorialDossier, interests: Sequence[str]) -> dict[str, str] | None:
    """The learner's interest this story meets: its topic (``{"topic": …, "word": …}``), else
    one of their words in its title or summary; ``None`` otherwise."""

    from app.services.revue.encounter import INTEREST_TOPICS, content_words, fold_keep_length

    folded = [fold_keep_length(item) for item in interests]
    topic_words = INTEREST_TOPICS.get(dossier.topic, ())
    for raw, item in zip(interests, folded, strict=False):
        if item in topic_words:
            return {"topic": dossier.topic, "word": raw}
    story = content_words(f"{dossier.title_fr} {dossier.summary_fr}")
    for raw in interests:
        if content_words(raw) & story:
            return {"topic": "", "word": raw}
    return None


@dataclass(frozen=True)
class Scored:
    dossier: EditorialDossier
    score: int
    why: dict[str, Any]


def score(dossier: EditorialDossier, focus: Focus, *, keys: Sequence[str] = (), last_topic: str | None = None,
          now: datetime | None = None) -> Scored:
    """How much ``dossier`` gives this learner today, and why (:data:`Focus`)."""

    from app.services.revue.encounter import appears_in

    text = story_french(dossier, focus.band, keys=keys)
    due = [word for word in focus.due if appears_in(text, word)][:DUE_CAP]
    uses = rule_uses(focus.rule, text)
    interest = interest_hit(dossier, focus.interests)
    points = W_DUE * len(due)
    if uses:
        points += W_RULE + (W_RULE_RICH if uses >= 3 else 0)
    if interest is not None:
        points += W_TOPIC if interest["topic"] else W_INTEREST_WORD
    stamp = focus.last_seen.get(dossier.topic)
    if last_topic and dossier.topic == last_topic:
        points -= P_LAST_TOPIC
    elif stamp is not None and (now or datetime.now(UTC)).timestamp() - stamp < WEEK_SECONDS:
        points -= P_WEEK_TOPIC
    return Scored(dossier, points, why(due, focus if uses else None, interest, points))


def why(due: Sequence[str], focus: Focus | None, interest: dict[str, str] | None, points: int) -> dict[str, Any]:
    """The pick's reasons, small and explainable: ``due_words`` (forms as the cards write them),
    ``rule`` (``{id, name, today}``: the story gives occasion to use it) and ``interest``."""

    rule = None
    if focus is not None and focus.rule:
        rule = {"id": str(focus.rule.get("id") or ""), "name": str(focus.rule.get("name") or ""),
                "today": focus.rule_today}
    return {"due_words": list(due), "rule": rule, "interest": interest, "score": points}


def rank(dossiers: Sequence[EditorialDossier], focus: Focus, *, keys_of: Callable[[EditorialDossier], list[str]],
         playable: Callable[[EditorialDossier], bool] | None = None, now: datetime | None = None) -> list[Scored]:
    """``dossiers`` best first: the ones that can be played, then by score, then the topic seen
    longest ago, then the kiosk's order. Deterministic."""

    last_topic = max(focus.last_seen, key=lambda topic: focus.last_seen[topic]) if focus.last_seen else None
    scored = [score(d, focus, keys=keys_of(d), last_topic=last_topic, now=now) for d in dossiers]
    order = {d.id: index for index, d in enumerate(dossiers)}
    return sorted(scored, key=lambda s: (
        not (playable(s.dossier) if playable else True), -s.score, focus.last_seen.get(s.dossier.topic, 0.0),
        order[s.dossier.id]))


def prefer(keys: Sequence[str], dossier: EditorialDossier, focus: Focus) -> list[str]:
    """The assignments of ``keys`` whose material exercises the rule, best first: the rule's own
    uses in that material, plus its kind's affinity («Le micro» for questions…)."""

    if not focus.rule:
        return []
    rule_id = str(focus.rule.get("id") or "").upper()
    fits: list[tuple[int, int, str]] = []
    for index, key in enumerate(keys):
        fit = rule_uses(focus.rule, assignment_french(key, dossier, focus.band))
        if any(part in rule_id for part in AFFINITY.get(key, ())):
            fit += W_AFFINITY
        if fit > 0:
            fits.append((-fit, index, key))
    return [key for _, _, key in sorted(fits)]


def front_page(ordered: Sequence[Any], *, rubric: Callable[[Any], str | None], topic: Callable[[Any], str],
               count: int = 3, identity: Callable[[Any], Any] | None = None) -> list[Any]:
    """Up to ``count`` of ``ordered`` (best first): the best, then each time the best one whose
    rubric and topic are both new, else whose rubric is, else whose topic is, else the next.
    ``identity``: items that are the same story in another rubric — one of them at most."""

    chosen: list[Any] = []
    rest = list(ordered)
    while rest and len(chosen) < count:
        if identity is not None:
            taken = {identity(item) for item in chosen}
            rest = [item for item in rest if identity(item) not in taken]
            if not rest:
                break
        rubrics = {rubric(item) for item in chosen}
        topics = {topic(item) for item in chosen}

        def novelty(item: Any, rubrics: set = rubrics, topics: set = topics) -> int:
            return 2 * (rubric(item) in rubrics) + (topic(item) in topics)

        best = min(rest, key=lambda item: (novelty(item), rest.index(item)))
        chosen.append(best)
        rest.remove(best)
    if identity is not None and len(chosen) > 1 and len({rubric(item) for item in chosen}) == 1:
        # One rubric for the whole page while a chosen story carries another: the lowest one
        # shown is printed in that other rubric (one desk three times is no front page).
        for index in range(len(chosen) - 1, -1, -1):
            other = next((item for item in ordered if identity(item) == identity(chosen[index])
                          and rubric(item) != rubric(chosen[index])), None)
            if other is not None:
                chosen[index] = other
                break
    return chosen


__all__ = [
    "Focus",
    "Scored",
    "assignment_french",
    "choice_enabled",
    "focus_for",
    "front_page",
    "interest_hit",
    "pedagogy_enabled",
    "prefer",
    "rank",
    "rule_uses",
    "score",
    "story_french",
    "why",
]
