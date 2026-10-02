"""The encounter: Romy, the learner, one dossier, one week (WP-119 §5, phase 1).

The turn loop between the editorial dossier (what is true), the session plan (this
learner) and the conversation state (what happened). Everything a learner sees is a
**projection of the append-only state** (:func:`thread_items`), so resuming is a
replay and nothing but the next turn is ever generated. The wire is
``docs/implementation/atelier-v2/WP-119-WIRE.md``.

Generation goes through one :class:`RevueProvider` protocol:

* :class:`OpenAIRevueProvider` — the app's ``LLMService`` (OpenAI first, then the
  configured fallback provider), one structured JSON call per task;
* :class:`FakeRevueProvider` — deterministic, dossier-derived French. The tests and the
  walk harness use it, and the service uses it as its *authored* fallback for
  vocabulary, the headline exercise, the reader question and the close when the
  model is down (WP-119-DESIGN §3.7 ``#model-down``). Romy's conversational reply never
  falls back to the fake: it falls back to the authored line :data:`FALLBACK_LINE`.

What the service enforces on every reply, whatever the provider says: cited claims
exist in the dossier (unknown ids are dropped); the reply is at most
``support.reading_target_words / 2`` words (one regeneration, then cut at a sentence
end); no relative date (:data:`app.services.revue.checks.RELATIVE_DATE_PHRASES`); the
season's Knowledge check for the learner's current position
(:func:`app.services.revue.checks.check_knowledge`) — one regeneration, then the
authored line.

**Grading.** ``journey_conversation.evaluate_response`` — the existing respond grading
entry point — needs a planned journey (a ``ScenarioBrief`` and a ``ResponseTask``) and
writes story outcomes to the learner's serial thread, so it cannot be called on a Revue
turn. :func:`grade_turn` is the phase-1 adapter: every turn is ``unscored`` with
``capability_known=False`` (the Credit check's "unknown, never mastery"), and the
evidence event records which plan words the learner used, never as "correct".
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.revue_session import RevueSession
from app.schemas.revue import (
    RvAngle,
    RvAngleRef,
    RvBudget,
    RvClaim,
    RvClaimsItem,
    RvClosedWord,
    RvClosing,
    RvDispatch,
    RvDossierView,
    RvEvidence,
    RvFiled,
    RvGloss,
    RvHeadlineChoiceOffer,
    RvHeadlineEvidence,
    RvHeadlineOption,
    RvHeadlinePickResult,
    RvKept,
    RvLineItem,
    RvMade,
    RvMadeItem,
    RvMakeOffer,
    RvMatchResult,
    RvMineItem,
    RvNarrationItem,
    RvOffer,
    RvPlanView,
    RvQuestionDraft,
    RvQuestionProposeResult,
    RvQuestionSendResult,
    RvQuickReply,
    RvReaderQuestionOffer,
    RvResume,
    RvRoom,
    RvSessionView,
    RvShiftItem,
    RvSource,
    RvStage,
    RvStageMember,
    RvStoryCard,
    RvSummaryItem,
    RvSupport,
    RvTurnResult,
    RvUncertaintyItem,
    RvWeek,
)
from app.services.revue import policy
from app.services.revue.checks import (
    RELATIVE_DATE_PHRASES,
    check_credit,
    check_distinguishable,
    check_knowledge,
    failures,
)
from app.services.revue.dossier import Claim, EditorialDossier, fold, parse_week, week_bounds
from app.services.revue.evergreen import evergreens_for_week, load_evergreens
from app.services.revue.session import (
    ROMY_ID,
    LearnerContext,
    SessionPlan,
    Support,
    VocabItem,
    next_support_level,
    plan_for,
)
from app.services.revue.state import ConversationState, StateEvent

# ---------------------------------------------------------------------------
# Constants: Romy's authored lines, the budget, the grader
# ---------------------------------------------------------------------------

PARIS = ZoneInfo("Europe/Paris")
#: The authored line when the Knowledge check refuses a reply twice or the model is down.
FALLBACK_LINE = "Je ne sais pas encore. On regarde ce que disent les sources ?"
#: A free request matched nothing this week (§5.1).
NOTHING_ELSE_LINE = "Je n'ai que ça cette semaine, désolée. « {title} », ça te dit ?"
#: At 80 % of the budget Romy steers to ``make`` (§5.3).
STEER_LINE = "Il me reste peu de place dans la colonne : on fait le titre, ou la question pour les lecteurs ?"
#: At 100 % she closes with what exists (WP-119-DESIGN §3.8 ``#final``).
FINAL_LINE = "La colonne est pleine ! On boucle avec ce qu'on a : le titre, ou la question pour les lecteurs ?"
#: A turn after the column is full: no model call, the question is kept.
KEPT_LINE = "Bonne question. Je la garde pour la semaine prochaine : on boucle avec ce qu'on a ?"
#: The first words after "simplify on breakdown" (WP-119-DESIGN §3.3 ``#simplify``).
SIMPLIFY_LEAD = "Pardon, je vais trop vite."
COLOPHON = "La suite la semaine prochaine."

GRADER_ID = "revue-unscored-adapter-v1"
CAPABILITY_ID = "revue.conversation"
ROOM_LINES = 7
BOUCLAGE_RATIO = 0.8
#: The provider's only memory of the conversation (§5, the brief): the last six items.
HISTORY_ITEMS = 6
PHASE1_MAKE: tuple[str, ...] = ("headline_choice", "reader_question")
#: How many claims Romy puts on the table in the ``facts`` beat.
FACTS_ON_ENTRY = 2

_MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")

PURPOSE_LINES: dict[str, str] = {
    "understand_change": "Je dois expliquer ça à mes lecteurs de Montréal : « {angle} ». Tu m'aides ?",
    "explain_disagreement": "Les gens ne sont pas d'accord, et je dois l'expliquer : « {angle} ». Tu m'aides ?",
    "choose_angle": "Je ne sais pas par quel bout prendre l'histoire : « {angle} ». Tu m'aides à choisir ?",
    "prepare_dispatch": "Je dois écrire trois lignes là-dessus : « {angle} ». Tu m'aides ?",
}

CLOSE_LINES: dict[str, str] = {
    "reader_question": "J'ai mis ta question dans ma liste pour la rédaction. Je la garde.",
    "headline_choice": "Je garde ton titre. Il part avec mon papier.",
    "none": "Les sources ne m'ont pas tout dit, mais on a de quoi écrire trois lignes.",
}

QR_AGREE = RvQuickReply(label="D'accord, je t'aide.", send_fr="D'accord, je t'aide.")
QR_MORE = RvQuickReply(label="Plus", send_fr="Dis-m'en plus.")
QR_FORMULATE = RvQuickReply(label="On formule la question", send_fr="On formule la question ensemble ?")
QR_UNDERSTOOD = RvQuickReply(label="Ah, d'accord", send_fr="Ah, d'accord.")
QR_SIMPLER = RvQuickReply(label="Encore plus simple", send_fr="Encore plus simple, s'il te plaît.")
#: Quick replies that steer the conversation; never a reader question, never a breakdown signal.
_META_LINES = {QR_FORMULATE.send_fr, QR_AGREE.send_fr, QR_MORE.send_fr, QR_UNDERSTOOD.send_fr}

#: Interest words (``users.interests``, comma-separated, any of en/fr/de) → topics.
INTEREST_TOPICS: dict[str, tuple[str, ...]] = {
    "food": ("food", "cooking", "cuisine", "gastronomie", "kochen", "essen", "vin", "wine", "wein", "restaurant"),
    "culture": ("culture", "kultur", "music", "musique", "musik", "art", "kunst", "cinema", "film", "books", "livres", "history", "histoire"),
    "city": ("city", "ville", "stadt", "shopping", "mode", "fashion", "travel", "voyage", "reisen"),
    "sport": ("sport", "sports", "cyclisme", "cycling", "football", "fussball", "velo"),
    "nature": ("nature", "natur", "environment", "environnement", "climat", "climate", "umwelt", "hiking"),
    "work": ("work", "travail", "arbeit", "business", "economy", "economie", "tech", "career"),
    "politics": ("politics", "politique", "politik", "news", "actualite"),
}

_INCOMPREHENSION = (
    "je ne comprends pas",
    "je comprends pas",
    "j'ai pas compris",
    "je n'ai pas compris",
    "pas compris",
    "comprends rien",
    "plus simple",
    "plus lentement",
    "i don't understand",
    "i do not understand",
    "dont understand",
    "ich verstehe nicht",
    "verstehe nicht",
    "verstehe ich nicht",
)
_BARE_CONFUSION = {"", "?", "??", "???", "quoi", "pardon", "hein", "what", "huh", "wie bitte", "comment"}
_QUESTION_STARTS = ("est-ce que", "est ce que", "pourquoi", "comment", "combien", "qui ", "qu'est-ce", "ou ", "quand", "quel", "quelle")

#: Words that match everything in a dossier (the uncertainties all say "les sources ne disent pas").
_GENERIC = {"source", "disent", "dire", "sait", "savoir", "encore", "romy"}
_STOP = {
    *"""alors apres aussi autre autres avant avec avoir avait avaient bien cela celle celles celui ceci
    ceux cette chez comme comment dans depuis donc dont elle elles encore entre etait etaient etant etre
    fait faire font leur leurs mais meme memes moins notre nous peut peuvent plus pour pourquoi quand quel
    quelle quelles quels sans selon sera seront sont sous suis tous tout toute toutes tres vers votre vous
    ainsi aucun aucune lors puis sinon tant tandis voici voila parce est-ce estce combien quoi what that this
    with from have about there their they does sont avez avons aller allez veux voulez savez""".split(),
}
_WORD = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.UNICODE)
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*\s*")
_RELATIVE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(p) for p in RELATIVE_DATE_PHRASES) + r")(?![\w-])")
_ARTICLES = ("le", "la", "les", "un", "une", "des", "du")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _fold_char(char: str) -> str:
    folded = "".join(c for c in unicodedata.normalize("NFKD", char) if not unicodedata.combining(c))
    folded = folded.replace("’", "'").replace("‘", "'").lower()
    return folded[:1] or char


def fold_keep_length(text: str | None) -> str:
    """Lower-case, accent-free, quote-folded — one character per character, so indices map back."""

    return "".join(_fold_char(char) for char in str(text or ""))


def content_words(text: str | None) -> set[str]:
    """Accent-free content words (≥ 4 letters, not a function word, final plural s/x dropped)."""

    words: set[str] = set()
    for token in _WORD.findall(fold_keep_length(text)):
        for part in re.split(r"['-]", token):
            if len(part) < 4 or part in _STOP or part in _GENERIC:
                continue
            words.add(part[:-1] if len(part) > 4 and part[-1] in "sx" else part)
    return words


def word_count(text: str | None) -> int:
    return len(_WORD.findall(str(text or "")))


def _sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in _SENTENCE.findall(text or "") if chunk.strip()]


def truncate_to_words(text: str, limit: int) -> str:
    """Whole sentences up to ``limit`` words; the first sentence is kept, cut at ``limit`` words if alone."""

    kept: list[str] = []
    total = 0
    for sentence in _sentences(text):
        count = word_count(sentence)
        if kept and total + count > limit:
            break
        kept.append(sentence)
        total += count
    if not kept:
        return ""
    if total > limit:  # one long first sentence
        words = kept[0].split()
        return " ".join(words[: max(1, limit)]).rstrip(",;:") + "…"
    return " ".join(kept)


def relative_dates(text: str | None) -> list[str]:
    """The :data:`RELATIVE_DATE_PHRASES` in ``text`` (quote-folded, case-insensitive, accents kept)."""

    return [match.group(1) for match in _RELATIVE.finditer(fold(text).casefold())]


def drop_relative_sentences(text: str) -> str:
    return " ".join(sentence for sentence in _sentences(text) if not relative_dates(sentence))


def is_incomprehension(text: str) -> bool:
    folded = fold_keep_length(text).strip()
    bare = folded.strip(" ?!.…")
    return bare in _BARE_CONFUSION or any(phrase in folded for phrase in _INCOMPREHENSION)


def is_question(text: str) -> bool:
    stripped = (text or "").strip()
    if stripped in _META_LINES or is_incomprehension(stripped):
        return False
    folded = fold_keep_length(stripped)
    return stripped.endswith("?") or folded.startswith(_QUESTION_STARTS)


def contribution_spans(learner_text: str | None, target: str) -> list[tuple[int, int]]:
    """Spans of ``target`` holding the learner's own content words (accent-insensitive), merged."""

    if not learner_text or not target:
        return []
    wanted = {fold_keep_length(word) for word in _WORD.findall(learner_text)}
    folded = fold_keep_length(target)
    spans: list[tuple[int, int]] = []
    for match in _WORD.finditer(folded):
        if match.group(0) in wanted:
            spans.append((match.start(), match.end()))
    # Neighbouring words of the learner's join into one span (only spaces between them).
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and not folded[merged[-1][1]:start].strip():
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _stem_key(phrase: str) -> str:
    bare = fold_keep_length(_without_article(phrase))
    return bare[:-1] if len(bare) > 4 and bare[-1] in "sx" else bare


def _contains_word(text: str, phrase: str) -> bool:
    bare = _without_article(phrase)
    if not bare:
        return False
    return re.search(r"(?<!\w)" + re.escape(fold_keep_length(bare)), fold_keep_length(text)) is not None


def _without_article(phrase: str) -> str:
    value = (phrase or "").strip()
    lowered = value.lower()
    if lowered.startswith(("l'", "l’")):
        return value[2:]
    head, _, rest = value.partition(" ")
    return rest if head.lower() in _ARTICLES and rest else value


def _lower_first(text: str) -> str:
    head = text.split(" ", 1)[0]
    if head in {"Le", "La", "Les", "Un", "Une", "Des"} or text.startswith(("L'", "L’")):
        return text[:1].lower() + text[1:]
    return text


def _french_day(day: date) -> str:
    return f"{'1er' if day.day == 1 else day.day} {_MONTHS[day.month - 1]}"


# ---------------------------------------------------------------------------
# Weeks and dossiers
# ---------------------------------------------------------------------------


def current_week(now: datetime | None = None) -> str:
    local = (now or datetime.now(UTC)).astimezone(PARIS)
    year, number, _ = local.isocalendar()
    return f"{year}-W{number:02d}"


def week_view(week: str) -> RvWeek:
    _, number = parse_week(week)
    monday, sunday = week_bounds(week)
    if monday.month == sunday.month:
        span = f"du {'1er' if monday.day == 1 else monday.day} au {_french_day(sunday)}"
    else:
        span = f"du {_french_day(monday)} au {_french_day(sunday)}"
    return RvWeek(iso=week, label=f"Semaine {number}", range=span)


def available_dossiers(week: str) -> list[EditorialDossier]:
    """The week's dossiers: ``weekly.available_for_week`` when it exists, else the evergreens."""

    try:
        from app.services.revue import weekly  # sibling module, being written in parallel

        provider = getattr(weekly, "available_for_week", None)
        if callable(provider):
            dossiers = list(provider(week))
            if dossiers:
                return dossiers
    except Exception as exc:  # noqa: BLE001 - the week must still have evergreens
        logger.bind(week=week).warning("revue: weekly dossiers unavailable ({}); evergreens only", exc)
    return evergreens_for_week(week)


def find_dossier(dossier_id: str, week: str) -> EditorialDossier | None:
    for dossier in available_dossiers(week):
        if dossier.id == dossier_id:
            return dossier
    return None


# ---------------------------------------------------------------------------
# The stage (phase 1: known plates only)
# ---------------------------------------------------------------------------


def stage_for(dossier: EditorialDossier, plan: SessionPlan | None = None) -> RvStage:
    from app.services.season.world import SEASON_ONE_LOCATIONS, plate_for

    place = next((p for p in dossier.places if plan is None or p.id == plan.stage.place_id), dossier.places[0])
    real = place.id in SEASON_ONE_LOCATIONS
    kind = policy.place_kind(f"{place.id} {place.name_fr} {place.brief}")
    plate_place = place.id if real else policy.fallback_place_for(kind)
    dress = plan.stage.dress if plan is not None else policy.dress_for(kind)
    cast = (
        [RvStageMember(id=member.id, hold=member.hold) for member in plan.stage.cast]
        if plan is not None
        else [RvStageMember(id=ROMY_ID, hold="notebook"), RvStageMember(id="user", hold=None)]
    )
    return RvStage(
        place_id=place.id,
        place_fr=place.name_fr,
        plate_url=plate_for(plate_place),
        plate_place_id=plate_place,
        place_is_real=real,
        dress=dress,  # type: ignore[arg-type]
        cast=cast,
    )


def _known_plate(place_id: str) -> str | None:
    from app.services.season.world import SEASON_ONE_LOCATIONS, plate_for

    if place_id in SEASON_ONE_LOCATIONS:
        return plate_for(place_id)
    return None


def story_card(dossier: EditorialDossier) -> RvStoryCard:
    stage = stage_for(dossier)
    return RvStoryCard(
        dossier_id=dossier.id,
        title_fr=dossier.title_fr,
        summary_fr=dossier.summary_fr,
        topic=dossier.topic,  # type: ignore[arg-type]
        place_fr=stage.place_fr,
        plate_url=stage.plate_url,
        evergreen=dossier.evergreen,
        stage=stage,
    )


def _source(dossier: EditorialDossier, source_id: str) -> RvSource:
    source = dossier.source_by_id(source_id)
    if source is None:  # the dossier model guarantees it; keep the wire total anyway
        return RvSource(id=source_id, name=source_id, url="", published_at="")
    return RvSource(id=source.id, name=source.name, url=source.url, published_at=source.published_at.isoformat())


def rv_claim(dossier: EditorialDossier, claim: Claim) -> RvClaim:
    return RvClaim(
        id=claim.id,
        kind=claim.kind,
        fr=claim.fr,
        quote=claim.quote,
        attributed_to=claim.attributed_to,
        source=_source(dossier, claim.source_id),
    )


# ---------------------------------------------------------------------------
# The provider
# ---------------------------------------------------------------------------


class RevueProviderError(RuntimeError):
    pass


class RevueProvider(Protocol):
    """One structured call per task; each returns a plain dict (see the fake for the shapes)."""

    name: str

    def vocabulary(self, *, claims: list[dict[str, str]], count: int, language: str) -> list[dict[str, str]]: ...

    def reply(self, context: dict[str, Any]) -> dict[str, Any]: ...

    def headline(self, context: dict[str, Any]) -> dict[str, Any]: ...

    def question(self, context: dict[str, Any]) -> dict[str, Any]: ...

    def close(self, context: dict[str, Any]) -> dict[str, Any]: ...


def extract_vocabulary(claims: Sequence[dict[str, str]], count: int) -> list[dict[str, str]]:
    """Deterministic content words from the claims' French, with their article when it precedes them."""

    picked: list[dict[str, str]] = []
    seen: set[str] = set()
    for claim in claims:
        tokens = re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*|['’]", claim["fr"])
        previous: str | None = None
        for index, token in enumerate(tokens):
            if token in {"'", "’"}:
                continue
            folded = fold_keep_length(token)
            key = folded[:-1] if len(folded) > 4 and folded[-1] in "sx" else folded
            elided = index >= 2 and tokens[index - 1] in {"'", "’"} and tokens[index - 2].lower() == "l"
            capitalised = token[:1].isupper()  # proper nouns, and the odd sentence-initial word
            if len(token) >= 5 and folded not in _STOP and not capitalised and key not in seen:
                if elided:
                    fr = f"l'{token}"
                elif previous and previous.lower() in _ARTICLES[:5]:
                    fr = f"{previous.lower()} {token}"
                else:
                    fr = token
                picked.append({"fr": fr, "claim_id": claim["id"]})
                seen.add(key)
                if len(picked) >= count:
                    return picked
            previous = token
    return picked


@dataclass
class FakeRevueProvider:
    """Deterministic, dossier-derived French. ``script`` (reply dicts) and ``headline_script``
    are consumed first, one per call — the tests inject forced replies through them."""

    name: str = "fake-revue"
    script: list[dict[str, Any]] = field(default_factory=list)
    headline_script: list[dict[str, Any]] = field(default_factory=list)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    spent_usd: float = 0.0

    def vocabulary(self, *, claims: list[dict[str, str]], count: int, language: str) -> list[dict[str, str]]:
        self.calls.append(("vocabulary", {"count": count, "language": language}))
        return [
            {**row, "gloss": f"{_without_article(row['fr'])} ({language})"}
            for row in extract_vocabulary(claims, count)
        ]

    def reply(self, context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("reply", context))
        if self.script:
            return dict(self.script.pop(0))
        text = str(context.get("learner_text") or "")
        claims: list[dict[str, Any]] = list(context.get("claims") or [])
        shown = set(context.get("claims_shown") or [])
        if is_incomprehension(text):
            first = next((c for c in claims if c["kind"] == "fact"), claims[0] if claims else None)
            reply = "Pas de souci. On reprend doucement."
            if first:
                reply += f" {first['fr']}"
            return {"reply_fr": reply, "claims_cited": [first["id"]] if first else [], "uncertainty_cited": None,
                    "proposes_question": None, "shift": "simplify"}
        if "dis-m'en plus" in fold_keep_length(text) or fold_keep_length(text).strip(" .!") == "plus":
            unshown = [c for c in claims if c["id"] not in shown]
            if unshown:
                return {"reply_fr": f"Il y a autre chose. {unshown[0]['fr']}", "claims_cited": [unshown[0]["id"]],
                        "uncertainty_cited": None, "proposes_question": None, "shift": None}
        words = content_words(text)
        uncertainties = list(context.get("uncertainties") or [])
        best_u = max(range(len(uncertainties)), key=lambda i: len(words & content_words(uncertainties[i])), default=None)
        score_u = len(words & content_words(uncertainties[best_u])) if best_u is not None else 0
        best_c = max(claims, key=lambda c: len(words & content_words(c["fr"])), default=None)
        score_c = len(words & content_words(best_c["fr"])) if best_c else 0
        if is_question(text) and score_u and score_u >= score_c:
            return {"reply_fr": "Et là, je n'ai rien. Les sources ne le disent pas. On formule la question ensemble ?",
                    "claims_cited": [], "uncertainty_cited": best_u, "proposes_question": text.strip(), "shift": None}
        if best_c and score_c:
            return {"reply_fr": f"D'après mes sources, oui. {best_c['fr']}", "claims_cited": [best_c["id"]],
                    "uncertainty_cited": None, "proposes_question": None, "shift": None}
        if not shown:
            return {"reply_fr": "Merci ! Voilà ce que j'ai de sûr. Regarde.", "claims_cited": [],
                    "uncertainty_cited": None, "proposes_question": None, "shift": None}
        return {"reply_fr": "Je ne sais pas, mes sources n'en parlent pas. Tu veux savoir autre chose ?",
                "claims_cited": [], "uncertainty_cited": None, "proposes_question": None, "shift": None}

    def headline(self, context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("headline", context))
        if self.headline_script:
            return dict(self.headline_script.pop(0))
        shown: list[dict[str, Any]] = list(context.get("claims_shown") or [])
        facts = [c for c in shown if c["kind"] == "fact"] or shown
        if not facts:
            return {"answer": {"text_fr": context.get("title_fr", ""), "supported_by": None}, "distractors": []}
        answer = {"text_fr": context.get("title_fr") or facts[0]["fr"], "supported_by": facts[0]["id"]}
        distractors = []
        others = [c for c in shown if c["id"] != facts[0]["id"]] or facts
        for index in range(2):
            claim = others[index % len(others)]
            distractors.append({"text_fr": _fake_contradiction(claim["fr"], index), "contradicted_by": claim["id"]})
        return {"answer": answer, "distractors": distractors}

    def question(self, context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("question", context))
        learner = re.sub(r"\s+", " ", str(context.get("learner_text") or "")).strip().rstrip(" ?.!")
        learner = learner[:1].upper() + learner[1:] if learner else "Que disent les sources"
        return {"proposal_fr": f"{learner} ?", "why_native": None}

    def close(self, context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("close", context))
        made = context.get("artifact") or {}
        shown = [c["fr"] for c in context.get("claims_shown") or []]
        body = (shown + _sentences(str(context.get("summary_fr") or "")))[:3]
        return {
            "romy_line_fr": CLOSE_LINES.get(str(made.get("kind") or "none"), CLOSE_LINES["none"]),
            "headline_fr": made.get("text_fr") or context.get("title_fr"),
            "body_lines": body,
        }


def _fake_contradiction(fr: str, index: int) -> str:
    number = re.search(r"\d+", fr)
    if number:
        value = int(number.group(0))
        return fr[: number.start()] + str(value * 2 + 1 + index) + fr[number.end():]
    return f"Ce n'est plus vrai : {_lower_first(fr[:1].lower() + fr[1:] if fr[:1].isupper() else fr)}"


_SYSTEM = (
    "You write for «Le Papier de Romy», a French-learning app. Romy Tremblay is a Québécoise journalist; "
    "she speaks French only, tu, short concrete sentences, a little wry («hein»), professional about sources. "
    "She never praises like a teacher. She only states what the dossier's claims say, names interpretations as "
    "such («d'après…»), and says plainly when the sources are silent. Never use relative dates (demain, hier, "
    "cette semaine, aujourd'hui…). Never mention anything that is not in the dossier. Answer with one JSON object."
)

_TASKS: dict[str, str] = {
    "vocabulary": (
        "Pick {count} content words (nouns with their article, or infinitive verbs) a learner needs to read these "
        "claims. Each must appear in its claim's French. Gloss each in language '{language}'. "
        'JSON: {{"items": [{{"fr": str, "gloss": str, "claim_id": str}}]}}'
    ),
    "reply": (
        "Write Romy's next reply to the learner (max {max_words} words, CEFR {band}). Cite claims by id when you use "
        "them; if the learner asks something the claims cannot answer and an uncertainty covers it, cite its index and "
        "say the sources do not say; propose to phrase a reader question when useful. shift is 'simplify' when the "
        "learner is lost, 'angle' when the learner's interest fits another angle better, else null. "
        "Give a translation of reply_fr in '{translation_language}' when it is not null. Do NOT add a steer to "
        "the ending; the app adds it. "
        'JSON: {{"reply_fr": str, "translation": str|null, "claims_cited": [str], "uncertainty_cited": int|null, '
        '"proposes_question": str|null, "shift": "angle"|"simplify"|null}}'
    ),
    "headline": (
        "Write three headlines in French for Romy's piece: exactly one supported by the shown claims (supported_by = "
        "its claim id) and two distractors, each contradicted by one shown claim (contradicted_by = that claim id). "
        'JSON: {{"answer": {{"text_fr": str, "supported_by": str}}, "distractors": [{{"text_fr": str, "contradicted_by": str}}]}}'
    ),
    "question": (
        "The learner wants to ask the readers or the desk a question the sources cannot answer. Rewrite the learner's "
        "words as one short, correct French question at CEFR {band}, keeping as many of the learner's own words as "
        "possible. why_native: one line in '{language}' explaining the main change, or null. "
        'JSON: {{"proposal_fr": str, "why_native": str|null}}'
    ),
    "close": (
        "Romy closes the session. Say in one line what she does with the learner's contribution (no praise). "
        "headline_fr: keep the learner's artifact text when there is one. body_lines: exactly three short French "
        "lines from the shown claims. "
        'JSON: {{"romy_line_fr": str, "headline_fr": str, "body_lines": [str, str, str]}}'
    ),
}


@dataclass
class OpenAIRevueProvider:
    """The app's LLM service (``app.services.llm_service.LLMService``), one JSON call per task."""

    name: str = "openai-revue"
    max_tokens: int = 1600
    spent_usd: float = 0.0
    _service: Any = None

    def _llm(self) -> Any:
        if self._service is None:
            from app.services.llm_service import LLMService

            self._service = LLMService()
        return self._service

    def _ask(self, task: str, payload: dict[str, Any], **fmt: Any) -> dict[str, Any]:
        instructions = _TASKS[task].format(**fmt)
        try:
            result = self._llm().generate_chat_completion(
                [{"role": "user", "content": f"{instructions}\n\nINPUT:\n{json.dumps(payload, ensure_ascii=False)}"}],
                system_prompt=_SYSTEM,
                temperature=0.4,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                reasoning_effort="low",
            )
        except Exception as exc:  # noqa: BLE001 - the service falls back to authored lines
            raise RevueProviderError(str(exc)) from exc
        self.spent_usd += float(getattr(result, "cost", 0.0) or 0.0)
        try:
            data = json.loads(result.content or "")
        except (TypeError, ValueError) as exc:
            raise RevueProviderError(f"{task}: not JSON") from exc
        if not isinstance(data, dict):
            raise RevueProviderError(f"{task}: not an object")
        return data

    def vocabulary(self, *, claims: list[dict[str, str]], count: int, language: str) -> list[dict[str, str]]:
        data = self._ask("vocabulary", {"claims": claims}, count=count, language=language)
        return [row for row in data.get("items") or [] if isinstance(row, dict)]

    def reply(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._ask(
            "reply",
            context,
            max_words=context.get("max_words"),
            band=context.get("band"),
            translation_language=context.get("translation_language"),
        )

    def headline(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._ask("headline", context)

    def question(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._ask("question", context, band=context.get("band"), language=context.get("language"))

    def close(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._ask("close", context)


#: The authored fallback for everything but Romy's reply (see the module docstring).
AUTHORED = FakeRevueProvider(name="authored-revue")


def default_provider() -> RevueProvider:
    """The real provider when an LLM is configured, else the deterministic one (dev, walk harness)."""

    from app.config import settings

    if getattr(settings, "OPENAI_API_KEY", None) or getattr(settings, "ANTHROPIC_API_KEY", None):
        return OpenAIRevueProvider()
    logger.warning("revue: no LLM provider configured; Romy speaks from the deterministic provider")
    return FakeRevueProvider()


# ---------------------------------------------------------------------------
# Grading adapter and the learner's season position
# ---------------------------------------------------------------------------


def grade_turn(text: str, *, vocabulary: Iterable[VocabItem]) -> dict[str, Any]:
    """The phase-1 grading adapter: always ``unscored`` (see the module docstring)."""

    return {
        "rubric_version": GRADER_ID,
        "capability_id": CAPABILITY_ID,
        "outcome": "unscored",
        "capability_known": False,
        "correct": None,
        "words_used": [item.fr for item in vocabulary if _contains_word(text, item.fr)],
    }


@dataclass(frozen=True)
class SeasonPosition:
    season: Any
    gap_id: str
    flags: dict[str, Any]


def season_position(db: Session, user: Any) -> SeasonPosition | None:
    """Where the learner stands in their season, for the Knowledge check.

    The learner's active serial thread → ``state["living_story"]`` → the season
    runtime's ``today_for`` (the same call ``living_story.story_context`` makes, seed =
    the learner's id): the segment id of the next day to play (a gap id on a generated
    day, a tentpole id otherwise — then ``check_knowledge`` applies the season's global
    list only) and the learner's effective flags. A learner not on a season is checked
    against the enabled season (else ``s1``) from its start, global list only: Romy is
    the season's Romy either way.
    """

    try:
        from app.services import living_story
        from app.services.season import runtime as season_runtime
        from app.services.season.flags import effective_flags
        from app.services.season.format import load_season

        thread = living_story._active_thread(db, user)
        live = ((thread.state or {}).get(living_story.STATE_KEY) or {}) if thread is not None else {}
        today = season_runtime.today_for(live, user=user, seed=str(user.id))
        if today is not None:
            segment = today.pos.segment
            return SeasonPosition(today.season, segment.id if segment is not None else "", dict(today.flags))
        season = load_season(season_runtime.enabled_season() or "s1")
        return SeasonPosition(season, "", effective_flags(season, {"id": season.id}, seed=str(user.id)))
    except Exception as exc:  # noqa: BLE001 - a broken season must not cost the Revue
        logger.bind(user_id=str(getattr(user, "id", ""))).warning("revue: season position unavailable ({})", exc)
        return None


def knowledge_hits(lines: list[str], position: SeasonPosition | None) -> list[dict[str, Any]]:
    if position is None:
        return []
    results = check_knowledge(lines, season=position.season, gap_id=position.gap_id, flags=position.flags)
    return [dict(result.detail) for result in failures(results)]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RevueError(Exception):
    def __init__(self, status: int, code: str, **extra: Any) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.extra = extra

    @property
    def detail(self) -> dict[str, Any]:
        return {"code": self.code, **self.extra}


# ---------------------------------------------------------------------------
# Loading a session
# ---------------------------------------------------------------------------


@dataclass
class Loaded:
    row: RevueSession
    dossier: EditorialDossier
    plan: SessionPlan
    state: ConversationState


def _dossier_of(row: RevueSession, state: ConversationState) -> EditorialDossier:
    for event in state.events:
        if event.kind == "choice" and event.payload.get("kind") == "dossier" and event.payload.get("snapshot"):
            return EditorialDossier.model_validate(event.payload["snapshot"])
    dossier = find_dossier(row.dossier_id, row.week) or next(
        (d for d in load_evergreens() if d.id == row.dossier_id), None
    )
    if dossier is None:
        raise RevueError(404, "revue_dossier_not_found", dossier_id=row.dossier_id)
    return dossier


def load(row: RevueSession) -> Loaded:
    state = ConversationState.from_json(row.state)
    dossier = _dossier_of(row, state)
    plan = SessionPlan.model_validate(row.plan)
    return Loaded(row=row, dossier=dossier, plan=plan, state=state)


def current_support(plan: SessionPlan, state: ConversationState) -> Support:
    support = plan.support
    for _ in range(state.support_level):
        support = next_support_level(support)
    return support


def current_angle(dossier: EditorialDossier, plan: SessionPlan, state: ConversationState):
    angle_id = plan.angle_id
    for event in state.events:
        if event.kind == "choice" and event.payload.get("kind") == "angle" and event.payload.get("angle_id"):
            angle_id = str(event.payload["angle_id"])
    return dossier.angle_by_id(angle_id) or dossier.angles[0]


def _choices(state: ConversationState, kind: str) -> list[StateEvent]:
    return [e for e in state.events if e.kind == "choice" and e.payload.get("kind") == kind]


# ---------------------------------------------------------------------------
# The projection: state → what the learner sees (resume = replay)
# ---------------------------------------------------------------------------


def _glosses(text: str, plan: SessionPlan) -> list[RvGloss]:
    language = _gloss_language_of(plan)
    return [
        RvGloss(fr=item.fr, gloss=item.gloss.get(language) or next(iter(item.gloss.values()), ""), claim_id=item.claim_id)
        for item in plan.vocabulary
        if _contains_word(text, item.fr)
    ]


def _gloss_language_of(plan: SessionPlan) -> str:
    for item in plan.vocabulary:
        if item.gloss:
            return next(iter(item.gloss))
    return plan.learner.ui_language


def _line(event: StateEvent, plan: SessionPlan, *, suffix: str = "", role: str, text: str, translation: str | None = None) -> RvLineItem:
    return RvLineItem(
        id=f"{event.seq}{suffix}",
        seq=event.seq,
        at=event.at.isoformat(),
        role=role,  # type: ignore[arg-type]
        text_fr=text,
        translation=translation,
        glosses=_glosses(text, plan),
    )


def thread_items(dossier: EditorialDossier, plan: SessionPlan, state: ConversationState) -> list[Any]:
    items: list[Any] = []
    claims = dossier.claims_by_id()
    for event in state.events:
        payload = event.payload
        at = event.at.isoformat()
        if event.kind == "turn_learner":
            items.append(RvMineItem(id=str(event.seq), seq=event.seq, at=at, text_fr=str(payload.get("text_fr") or ""),
                                    mode=payload.get("mode") or "text"))
        elif event.kind == "turn_romy" and payload.get("beat") == "arrive":
            for index, sentence in enumerate(payload.get("narration") or []):
                items.append(RvNarrationItem(id=f"{event.seq}.n{index}", seq=event.seq, at=at, text_fr=str(sentence)))
            if payload.get("place_note"):
                items.append(_line(event, plan, suffix=".p", role="place_note", text=str(payload["place_note"])))
            if payload.get("request_miss"):
                items.append(_line(event, plan, suffix=".m", role="fallback", text=str(payload["request_miss"])))
            items.append(_line(event, plan, role="purpose", text=str(payload.get("text_fr") or "")))
            if payload.get("summary_fr"):
                items.append(RvSummaryItem(id=f"{event.seq}.s", seq=event.seq, at=at, text_fr=str(payload["summary_fr"])))
        elif event.kind == "turn_romy":
            items.append(_line(event, plan, role=str(payload.get("role") or "reply"), text=str(payload.get("text_fr") or ""),
                               translation=payload.get("translation")))
            if payload.get("uncertainty_text"):
                items.append(RvUncertaintyItem(id=f"{event.seq}.u", seq=event.seq, at=at, text_fr=str(payload["uncertainty_text"])))
        elif event.kind == "claim_shown":
            ids = [str(payload["claim_id"])] if payload.get("claim_id") else [str(i) for i in payload.get("claim_ids") or []]
            shown = [rv_claim(dossier, claims[i]) for i in ids if i in claims]
            if shown:
                items.append(RvClaimsItem(id=str(event.seq), seq=event.seq, at=at, claims=shown))
        elif event.kind == "support_changed":
            items.append(RvShiftItem(id=str(event.seq), seq=event.seq, at=at, reason="simplify"))
        elif event.kind == "choice" and payload.get("kind") == "angle":
            angle = dossier.angle_by_id(str(payload.get("angle_id") or ""))
            items.append(RvShiftItem(id=str(event.seq), seq=event.seq, at=at, reason="angle",
                                     angle=RvAngleRef(id=angle.id, fr=angle.fr) if angle else None))
        elif event.kind == "choice" and payload.get("kind") == "room":
            items.append(RvShiftItem(id=str(event.seq), seq=event.seq, at=at, reason=payload.get("phase") or "bouclage"))
        elif event.kind == "artifact":
            items.append(RvMadeItem(id=str(event.seq), seq=event.seq, at=at, made=_made(payload)))
    return items


def _made(payload: dict[str, Any]) -> RvMade:
    return RvMade(
        kind=payload.get("kind") or "headline_choice",
        text_fr=str(payload.get("text_fr") or ""),
        contribution=[tuple(span) for span in payload.get("contribution") or []],
        learner_fr=payload.get("learner_fr"),
    )


def room_for(plan: SessionPlan, state: ConversationState) -> RvRoom:
    turns = max(1, plan.budget.turns)
    used = state.turns_used
    ratio = used / turns
    phase = "boucle" if ratio >= 1 else "bouclage" if ratio >= BOUCLAGE_RATIO else "open"
    return RvRoom(used=min(ROOM_LINES, (used * ROOM_LINES) // turns), phase=phase, remaining_turns=max(0, turns - used))


def beat_for(state: ConversationState) -> str:
    if state.closed:
        return "close"
    if state.current_artifact or _choices(state, "make") or _choices(state, "question_draft"):
        return "make"
    used = state.turns_used
    return "arrive" if used == 0 else "facts" if used == 1 else "pursue"


def support_view(plan: SessionPlan, state: ConversationState) -> RvSupport:
    support = current_support(plan, state)
    return RvSupport(
        glosses=support.glosses,
        translation=support.translation,
        reading_target_words=support.reading_target_words,
        vocab_target=support.vocab_target,
        level=state.support_level,
    )


def quick_replies(state: ConversationState, room: RvRoom) -> list[RvQuickReply]:
    if state.closed:
        return []
    if state.turns_used == 0:
        return [QR_AGREE]
    if room.phase != "open":
        return [] if state.current_artifact else [QR_MORE]
    recent = [e for e in state.events if e.seq > _last_learner_seq(state)]
    if any(e.kind == "support_changed" for e in recent):
        return [QR_UNDERSTOOD, QR_SIMPLER]
    romy = [e for e in recent if e.kind == "turn_romy"]
    if romy and (romy[-1].payload.get("uncertainty_text") or romy[-1].payload.get("proposes_question")):
        return [QR_FORMULATE, QR_MORE]
    return [QR_MORE]


def _last_learner_seq(state: ConversationState) -> int:
    learner = [e.seq for e in state.events if e.kind == "turn_learner"]
    return learner[-1] if learner else 0


def open_question(state: ConversationState) -> dict[str, Any] | None:
    unanswerable = [q for q in state.questions if not q.get("answerable")]
    return unanswerable[-1] if unanswerable else None


def _closing_of(state: ConversationState) -> RvClosing | None:
    closed = [e for e in state.events if e.kind == "closed"]
    if not closed or not closed[-1].payload.get("closing"):
        return None
    return RvClosing.model_validate(closed[-1].payload["closing"])


def session_view(loaded: Loaded) -> RvSessionView:
    row, dossier, plan, state = loaded.row, loaded.dossier, loaded.plan, loaded.state
    room = room_for(plan, state)
    angle = current_angle(dossier, plan, state)
    artifact = state.current_artifact
    language = _gloss_language_of(plan)
    return RvSessionView(
        id=str(row.id),
        week=week_view(row.week),
        status=row.status,  # type: ignore[arg-type]
        started_at=_iso(row.started_at),
        closed_at=_iso(row.closed_at) if row.closed_at else None,
        dossier=RvDossierView(
            id=dossier.id,
            title_fr=dossier.title_fr,
            summary_fr=dossier.summary_fr,
            topic=dossier.topic,  # type: ignore[arg-type]
            evergreen=dossier.evergreen,
            sources=[_source(dossier, s.id) for s in dossier.sources],
        ),
        plan=RvPlanView(
            band=plan.learner.band,  # type: ignore[arg-type]
            ui_language=plan.learner.ui_language,  # type: ignore[arg-type]
            gloss_language=language,  # type: ignore[arg-type]
            chosen_by=plan.chosen_by,
            angle=RvAngle(id=angle.id, fr=angle.fr, purpose=angle.purpose),
            support=support_view(plan, state),
            vocabulary=[
                RvGloss(fr=item.fr, gloss=item.gloss.get(language, ""), claim_id=item.claim_id) for item in plan.vocabulary
            ],
            # Phase 1 builds exactly two make options at every band (§10); phase-2 kinds never travel.
            make_options=list(PHASE1_MAKE),  # type: ignore[arg-type]
            budget=RvBudget(turns=plan.budget.turns, minutes=plan.budget.minutes),
        ),
        stage=stage_for(dossier, plan),
        beat=beat_for(state),  # type: ignore[arg-type]
        room=room,
        thread=thread_items(dossier, plan, state),
        quick_replies=quick_replies(state, room),
        steer_to_make=room.phase != "open" and artifact is None and not state.closed,
        artifact=_made(artifact) if artifact else None,
        closing=_closing_of(state),
    )


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------


def _interests(user: Any) -> list[str]:
    return [part.strip().lower() for part in str(getattr(user, "interests", "") or "").split(",") if part.strip()]


def _interest_score(dossier: EditorialDossier, interests: list[str]) -> int:
    if not interests:
        return 0
    folded = {fold_keep_length(i) for i in interests}
    score = 2 * sum(1 for word in INTEREST_TOPICS.get(dossier.topic, ()) if word in folded)
    score += len(content_words(" ".join(interests)) & content_words(f"{dossier.title_fr} {dossier.summary_fr}"))
    return score


def _match_score(text: str, dossier: EditorialDossier) -> int:
    words = content_words(text)
    haystack = " ".join([dossier.title_fr, dossier.summary_fr, *(a.fr for a in dossier.angles),
                         *(p.name_fr for p in dossier.places)])
    return len(words & content_words(haystack))


class RevueEncounter:
    """One learner's Revue, end to end. Every method commits what it appends."""

    def __init__(self, db: Session, provider: RevueProvider | None = None) -> None:
        self.db = db
        self.provider = provider or default_provider()

    # -- entry -------------------------------------------------------------

    def _sessions(self, user: Any, *, week: str | None = None, status: str | None = None) -> list[RevueSession]:
        query = select(RevueSession).where(RevueSession.user_id == user.id)
        if week is not None:
            query = query.where(RevueSession.week == week)
        if status is not None:
            query = query.where(RevueSession.status == status)
        return list(self.db.scalars(query.order_by(RevueSession.started_at.desc())))

    def _topic_last_seen(self, user: Any) -> dict[str, float]:
        seen: dict[str, float] = {}
        for row in self._sessions(user, status="closed")[:60]:
            topic = None
            for event in (row.state or {}).get("events") or []:
                payload = event.get("payload") or {}
                if event.get("kind") == "choice" and payload.get("kind") == "dossier":
                    topic = (payload.get("snapshot") or {}).get("topic")
                    break
            stamp = (row.closed_at or row.started_at)
            if topic and stamp is not None:
                ts = (stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)).timestamp()
                seen[topic] = max(seen.get(topic, 0.0), ts)
        return seen

    def ranked(self, user: Any, week: str) -> tuple[list[EditorialDossier], str]:
        dossiers = available_dossiers(week)
        if not dossiers:
            return [], "first"
        last_seen = self._topic_last_seen(user)
        interests = _interests(user)
        keyed = [
            ((last_seen.get(d.topic, 0.0), -_interest_score(d, interests), index), d)
            for index, d in enumerate(dossiers)
        ]
        keyed.sort(key=lambda pair: pair[0])
        ordered = [d for _, d in keyed]
        reason = "first"
        if len(keyed) > 1:
            (seen_a, interest_a, _), (seen_b, interest_b, _) = keyed[0][0], keyed[1][0]
            if seen_a < seen_b:
                reason = "topic_least_recent"
            elif interest_a < interest_b:
                reason = "interests"
        return ordered, reason

    def week_offer(self, user: Any, week: str | None = None) -> RvOffer:
        week = week or current_week()
        ordered, reason = self.ranked(user, week)
        cards = [story_card(d) for d in ordered[:3]]
        resume = None
        filed = None
        for row in self._sessions(user, week=week):
            loaded = load(row)
            if row.status == "active" and resume is None:
                question = open_question(loaded.state)
                resume = RvResume(
                    session_id=str(row.id),
                    dossier_id=row.dossier_id,
                    title_fr=loaded.dossier.title_fr,
                    started_at=_iso(row.started_at),
                    beat=beat_for(loaded.state),  # type: ignore[arg-type]
                    open_question_fr=str(question["text"]) if question else None,
                )
            elif row.status == "closed" and filed is None:
                closing = _closing_of(loaded.state)
                artifact = loaded.state.current_artifact
                filed = RvFiled(
                    session_id=str(row.id),
                    dossier_id=row.dossier_id,
                    title_fr=loaded.dossier.title_fr,
                    closed_at=_iso(row.closed_at),
                    made=_made(artifact) if artifact else None,
                    dispatch=closing.dispatch if closing else None,
                )
        return RvOffer(
            week=week_view(week),
            recommended=cards[0] if cards else None,
            recommended_reason=reason,  # type: ignore[arg-type]
            alternatives=cards[1:3],
            evergreen_only=bool(cards) and all(d.evergreen for d in ordered[:3]),
            resume=resume,
            filed=filed,
        )

    def match(self, user: Any, text: str, week: str | None = None) -> RvMatchResult:
        week = week or current_week()
        ordered, _ = self.ranked(user, week)
        best = self._best_match(text, ordered)
        if best is not None:
            return RvMatchResult(match=best.id)
        title = ordered[0].title_fr if ordered else ""
        return RvMatchResult(match=None, romy_line_fr=NOTHING_ELSE_LINE.format(title=title) if title else None)

    @staticmethod
    def _best_match(text: str, dossiers: list[EditorialDossier]) -> EditorialDossier | None:
        scored = [(_match_score(text, d), -index, d) for index, d in enumerate(dossiers)]
        scored = [row for row in scored if row[0] > 0]
        return max(scored, key=lambda row: (row[0], row[1]))[2] if scored else None

    # -- start ---------------------------------------------------------------

    def start(
        self,
        user: Any,
        week: str | None = None,
        dossier_id: str | None = None,
        free_request: str | None = None,
        angle_id: str | None = None,
    ) -> RevueSession:
        week = week or current_week()
        for row in self._sessions(user, week=week):
            if row.status == "active":
                raise RevueError(409, "revue_session_active", session_id=str(row.id))
            if row.status == "closed":
                raise RevueError(409, "revue_week_filed", session_id=str(row.id))

        ordered, _ = self.ranked(user, week)
        request_miss: str | None = None
        chosen_by = "recommended"
        if dossier_id:
            dossier = next((d for d in ordered if d.id == dossier_id), None)
            if dossier is None:
                raise RevueError(404, "revue_dossier_not_found", dossier_id=dossier_id)
            chosen_by = "learner"
        elif free_request and free_request.strip():
            dossier = self._best_match(free_request, ordered)
            if dossier is not None:
                chosen_by = "learner"
            elif ordered:
                dossier = ordered[0]
                request_miss = NOTHING_ELSE_LINE.format(title=dossier.title_fr)
            else:
                dossier = None
        else:
            dossier = ordered[0] if ordered else None
        if dossier is None:
            raise RevueError(404, "revue_dossier_not_found", dossier_id=dossier_id or "")
        if angle_id and dossier.angle_by_id(angle_id) is None:
            raise RevueError(404, "revue_dossier_not_found", dossier_id=dossier.id, angle_id=angle_id)

        plan = self._plan(user, dossier, angle_id=angle_id, chosen_by=chosen_by)
        state = ConversationState()
        state.append("choice", kind="dossier", dossier_id=dossier.id, chosen_by=chosen_by,
                     free_request=(free_request or None), snapshot=dossier.model_dump(mode="json"))
        self._arrive(state, dossier, plan, request_miss=request_miss)

        row = RevueSession(
            id=uuid.uuid4(),
            user_id=user.id,
            week=week,
            dossier_id=dossier.id,
            plan=plan.model_dump(mode="json"),
            state=state.to_json(),
            status="active",
            started_at=datetime.now(UTC),
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError as exc:  # a concurrent start won the partial unique index
            self.db.rollback()
            existing = next((r for r in self._sessions(user, week=week) if r.status == "active"), None)
            raise RevueError(409, "revue_session_active", session_id=str(existing.id) if existing else "") from exc
        self.db.refresh(row)
        return row

    def _plan(self, user: Any, dossier: EditorialDossier, *, angle_id: str | None, chosen_by: str) -> SessionPlan:
        from app.services.chrome_language import level_band, user_chrome_language
        from app.services.journey_contracts import normalize_control_language

        band = policy.normalize_band(level_band(getattr(user, "cefr_estimate", None)) or "A1")
        learner = LearnerContext(band=band, ui_language=user_chrome_language(user), interests=_interests(user))
        plan = plan_for(dossier, learner, angle_id=angle_id, chosen_by=chosen_by,  # type: ignore[arg-type]
                        place_known_plate=_known_plate)
        if plan.stage.plate_url is None:
            # Phase 1: known plates only — the place's nearest season plate stands in (§8.1).
            plan.stage.plate_url = stage_for(dossier).plate_url
        gloss_language = normalize_control_language(getattr(user, "native_language", None))
        plan.vocabulary = self._vocabulary(dossier, plan.support.vocab_target, gloss_language)
        return plan.validate_against(dossier)

    def _vocabulary(self, dossier: EditorialDossier, count: int, language: str) -> list[VocabItem]:
        claims = [{"id": c.id, "fr": c.fr} for c in [*dossier.facts(), *dossier.interpretations(), *dossier.forecasts()]]
        by_id = dossier.claims_by_id()
        rows: list[dict[str, str]] = []
        try:
            rows = list(self.provider.vocabulary(claims=claims, count=count, language=language))
        except Exception as exc:  # noqa: BLE001
            logger.warning("revue: vocabulary provider failed ({}); authored extraction", exc)
        items: list[VocabItem] = []
        seen: set[str] = set()

        def add(fr: str, gloss: str, claim_id: str) -> None:
            key = _stem_key(fr)
            claim = by_id.get(claim_id)
            if not fr or key in seen or claim is None or not _contains_word(claim.fr, fr) or len(items) >= count:
                return
            seen.add(key)
            items.append(VocabItem(fr=fr.strip(), gloss={language: gloss.strip()} if gloss.strip() else {}, claim_id=claim_id))

        for row in rows:
            add(str(row.get("fr") or ""), str(row.get("gloss") or ""), str(row.get("claim_id") or ""))
        if len(items) < count:
            for row in extract_vocabulary(claims, count * 2):
                add(row["fr"], "", row["claim_id"])
        return items

    def _arrive(self, state: ConversationState, dossier: EditorialDossier, plan: SessionPlan, *, request_miss: str | None) -> None:
        place = next((p for p in dossier.places if p.id == plan.stage.place_id), dossier.places[0])
        stage = stage_for(dossier, plan)
        scope = dossier.time_scope
        if (scope.end - scope.start).days > 60:
            when = "une histoire de tous les jours."
        else:
            when = f"ça se passe du {_french_day(scope.start)} au {_french_day(scope.end)}."
        narration = [f"{place.name_fr.rstrip('.')}.", f"Romy est déjà là, son carnet à la main : {when}"]
        place_note = None if stage.place_is_real else f"Ce n'est pas vraiment {_lower_first(place.name_fr)}, hein… mais on fait comme si."
        angle = dossier.angle_by_id(plan.angle_id) or dossier.angles[0]
        purpose = PURPOSE_LINES.get(angle.purpose, PURPOSE_LINES["understand_change"]).format(angle=angle.fr)
        state.append("turn_romy", beat="arrive", role="purpose", narration=narration, place_note=place_note,
                     request_miss=request_miss, text_fr=purpose, summary_fr=dossier.summary_fr)

    # -- a turn ----------------------------------------------------------------

    def _owner(self, row: RevueSession) -> Any:
        from app.db.models.user import User

        return self.db.get(User, row.user_id)

    def _save(self, loaded: Loaded) -> None:
        loaded.row.state = loaded.state.to_json()
        loaded.row.updated_at = datetime.now(UTC)
        self.db.add(loaded.row)
        self.db.commit()

    def turn(self, row: RevueSession, learner_text: str, *, mode: str = "text", client_turn_id: str | None = None) -> RvTurnResult:
        loaded = load(row)
        state, plan, dossier = loaded.state, loaded.plan, loaded.dossier
        if row.status != "active" or state.closed:
            raise RevueError(409, "revue_session_closed")

        learner_turns = [e for e in state.events if e.kind == "turn_learner"]
        if client_turn_id and learner_turns and learner_turns[-1].payload.get("client_turn_id") == client_turn_id:
            return self._turn_result(loaded, since=learner_turns[-1].seq)

        text = re.sub(r"\s+", " ", learner_text or "").strip()
        before = state.turns_used
        budget = max(1, plan.budget.turns)
        phase_before = room_for(plan, state).phase
        learner_event = state.append("turn_learner", text_fr=text, mode=mode, client_turn_id=client_turn_id)
        question = is_question(text)
        lexical_breakdown = is_incomprehension(text)

        # Simplify on breakdown (§5.3), decided before the reply when the learner says so.
        simplified = False
        if lexical_breakdown and plan.support.simplify_on_breakdown and self._breakdown_streak(state) >= 1:
            state.append("support_changed", level=state.support_level + 1, reason="breakdown")
            simplified = True

        shift = None
        if before >= budget:
            # The column is full: no model call, the question is kept for next week.
            state.append("turn_romy", beat="pursue", role="reply", text_fr=KEPT_LINE, kept=True)
            answerable = False
            uncertainty_text = None
        else:
            position = season_position(self.db, self._owner(row))
            outcome = self._reply(loaded, text, position=position, simplified=simplified)
            shift = outcome["shift"]
            new_claims = [cid for cid in outcome["claims_cited"] if cid not in state.claims_shown]
            if not state.claims_shown and not new_claims:
                # The facts beat: Romy puts what she is sure of on the table (§5.3). The facts
                # need no generation, so they come even when her line is the authored one.
                new_claims = [c.id for c in dossier.facts()[:FACTS_ON_ENTRY]] or [c.id for c in dossier.claims[:FACTS_ON_ENTRY]]
            uncertainty_text = outcome["uncertainty_text"]
            state.append(
                "turn_romy",
                beat="facts" if before == 0 else "pursue",
                role=outcome["role"],
                text_fr=outcome["text_fr"],
                translation=outcome["translation"],
                claims_cited=outcome["claims_cited"],
                uncertainty_index=outcome["uncertainty_index"],
                uncertainty_text=uncertainty_text,
                proposes_question=outcome["proposes_question"],
                shift=shift,
                attempts=outcome["attempts"],
                refused=outcome["refused"],
                cost_usd=outcome["cost_usd"],
            )
            if new_claims:
                state.append("claim_shown", claim_ids=new_claims)
            answerable = bool(outcome["claims_cited"]) and not uncertainty_text and outcome["role"] != "fallback"
            if shift == "angle":
                current = current_angle(dossier, plan, state)
                other = next((a for a in dossier.angles if a.id != current.id), None)
                if other is not None:
                    state.append("choice", kind="angle", angle_id=other.id, reason="learner_interest")

        if question:
            state.append("question_raised", text=text, answerable=answerable, uncertainty_text=uncertainty_text,
                         turn_seq=learner_event.seq, kept=before >= budget)

        evidence = grade_turn(text, vocabulary=plan.vocabulary)
        breakdown = lexical_breakdown or shift == "simplify"
        if failures(check_credit(evidence)):
            evidence = {**evidence, "outcome": "unscored", "capability_known": False}
        # ``counts``: a breakdown already answered by a simplification this turn starts a new streak.
        state.append("evidence", **evidence, breakdown=breakdown, counts=breakdown and not simplified,
                     turn_seq=learner_event.seq)
        if (
            not simplified
            and shift == "simplify"
            and plan.support.simplify_on_breakdown
            and self._breakdown_streak(state) >= 2
        ):
            state.append("support_changed", level=state.support_level + 1, reason="breakdown")

        phase_after = room_for(plan, state).phase
        if phase_after != phase_before and phase_after in {"bouclage", "boucle"}:
            state.append("choice", kind="room", phase=phase_after)
        if phase_after != "open" and state.current_artifact is None and before < budget:
            state.append("turn_romy", beat="pursue", role="steer", text_fr=FINAL_LINE if phase_after == "boucle" else STEER_LINE)

        self._save(loaded)
        return self._turn_result(loaded, since=learner_event.seq)

    @staticmethod
    def _breakdown_streak(state: ConversationState) -> int:
        """Consecutive breakdown turns since the last support change (this turn's evidence excluded until written)."""

        streak = 0
        for event in reversed(state.events):
            if event.kind == "support_changed":
                break
            if event.kind == "evidence":
                if event.payload.get("counts"):
                    streak += 1
                else:
                    break
        return streak

    def _turn_result(self, loaded: Loaded, *, since: int) -> RvTurnResult:
        state, plan = loaded.state, loaded.plan
        items = [item for item in thread_items(loaded.dossier, plan, state) if item.seq >= since]
        room = room_for(plan, state)
        evidence_event = next((e for e in state.events if e.kind == "evidence" and e.payload.get("turn_seq") == since), None)
        payload = evidence_event.payload if evidence_event else {}
        return RvTurnResult(
            items=items,
            beat=beat_for(state),  # type: ignore[arg-type]
            room=room,
            support=support_view(plan, state),
            quick_replies=quick_replies(state, room),
            steer_to_make=room.phase != "open" and state.current_artifact is None and not state.closed,
            evidence=RvEvidence(
                outcome=payload.get("outcome") or "unscored",
                capability_known=bool(payload.get("capability_known")),
                grader=str(payload.get("rubric_version") or GRADER_ID),
            ),
        )

    def _history(self, loaded: Loaded) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in thread_items(loaded.dossier, loaded.plan, loaded.state):
            if isinstance(item, RvMineItem):
                rows.append({"who": "learner", "text": item.text_fr})
            elif isinstance(item, RvLineItem):
                rows.append({"who": "romy", "text": item.text_fr})
            elif isinstance(item, RvNarrationItem):
                rows.append({"who": "narrator", "text": item.text_fr})
            elif isinstance(item, RvClaimsItem):
                rows.append({"who": "claims_shown", "text": ", ".join(c.id for c in item.claims)})
            elif isinstance(item, RvUncertaintyItem):
                rows.append({"who": "uncertainty_named", "text": item.text_fr})
        # The learner's current line is the last item; it travels as ``learner_text``.
        return rows[:-1][-HISTORY_ITEMS:]

    def _reply(self, loaded: Loaded, text: str, *, position: SeasonPosition | None, simplified: bool) -> dict[str, Any]:
        dossier, plan, state = loaded.dossier, loaded.plan, loaded.state
        support = current_support(plan, state)
        limit = max(8, support.reading_target_words // 2)
        if simplified:
            limit = max(8, limit - word_count(SIMPLIFY_LEAD))
        angle = current_angle(dossier, plan, state)
        translation_language = _gloss_language_of(plan) if support.translation != "none" else None
        context: dict[str, Any] = {
            "task": "reply",
            "learner_text": text,
            "claims": [
                {"id": c.id, "kind": c.kind, "fr": c.fr, "attributed_to": c.attributed_to} for c in dossier.claims
            ],
            "uncertainties": list(dossier.uncertainties),
            "angle": {"id": angle.id, "fr": angle.fr, "purpose": angle.purpose},
            "angles": [{"id": a.id, "fr": a.fr, "purpose": a.purpose} for a in dossier.angles],
            "support": {**support.model_dump(), "level": state.support_level},
            "band": plan.learner.band,
            "max_words": limit,
            "claims_shown": sorted(state.claims_shown),
            "history": self._history(loaded),
            "translation_language": translation_language,
        }
        known = dossier.claims_by_id()
        spent_before = float(getattr(self.provider, "spent_usd", 0.0) or 0.0)
        parsed: dict[str, Any] | None = None
        problems: list[str] = []
        attempts = 0
        model_down = False
        for _attempt in range(2):
            attempts += 1
            try:
                raw = self.provider.reply(context)
            except Exception as exc:  # noqa: BLE001 - the model is down: the authored line
                logger.bind(session_id=str(loaded.row.id)).warning("revue: reply provider failed ({})", exc)
                model_down = True
                break
            parsed = self._parse_reply(raw, known, dossier)
            problems = []
            if not parsed["text_fr"]:
                problems.append("empty")
            if word_count(parsed["text_fr"]) > limit:
                problems.append("too_long")
            if relative_dates(parsed["text_fr"]):
                problems.append("relative_date")
            hits = knowledge_hits([parsed["text_fr"]], position)
            if hits:
                problems.append("knowledge")
            if not problems:
                break
            context = {**context, "retry_feedback": {
                "problems": problems,
                "max_words": limit,
                "relative_dates": relative_dates(parsed["text_fr"]),
                "forbidden": [hit.get("must_not_id") for hit in hits],
            }}
        cost = float(getattr(self.provider, "spent_usd", 0.0) or 0.0) - spent_before
        base = {"translation": None, "claims_cited": [], "uncertainty_index": None, "uncertainty_text": None,
                "proposes_question": None, "shift": None, "attempts": attempts, "refused": problems, "cost_usd": round(cost, 6)}
        if model_down or parsed is None or "knowledge" in problems or "empty" in problems:
            return {**base, "role": "fallback", "text_fr": FALLBACK_LINE, "refused": problems or ["model_down"]}
        reply = parsed["text_fr"]
        if "relative_date" in problems:
            reply = drop_relative_sentences(reply)
        if word_count(reply) > limit:
            reply = truncate_to_words(reply, limit)
        if not reply:
            return {**base, "role": "fallback", "text_fr": FALLBACK_LINE}
        if simplified:
            reply = f"{SIMPLIFY_LEAD} {reply}"
        translation = parsed["translation"] if translation_language and reply == parsed["text_fr"] else None
        return {**base, **{k: parsed[k] for k in ("claims_cited", "uncertainty_index", "uncertainty_text",
                                                  "proposes_question", "shift")},
                "role": "reply", "text_fr": reply, "translation": translation}

    @staticmethod
    def _parse_reply(raw: Any, known: dict[str, Claim], dossier: EditorialDossier) -> dict[str, Any]:
        raw = raw if isinstance(raw, dict) else {}
        cited = [str(c) for c in raw.get("claims_cited") or [] if str(c) in known]
        cited = list(dict.fromkeys(cited))
        index = raw.get("uncertainty_cited")
        uncertainty_index = index if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(dossier.uncertainties) else None
        shift = raw.get("shift") if raw.get("shift") in {"angle", "simplify"} else None
        proposes = raw.get("proposes_question")
        translation = raw.get("translation")
        return {
            "text_fr": re.sub(r"\s+", " ", str(raw.get("reply_fr") or "")).strip(),
            "claims_cited": cited,
            "uncertainty_index": uncertainty_index,
            "uncertainty_text": dossier.uncertainties[uncertainty_index] if uncertainty_index is not None else None,
            "proposes_question": str(proposes).strip() if isinstance(proposes, str) and proposes.strip() else None,
            "shift": shift,
            "translation": str(translation).strip() if isinstance(translation, str) and translation.strip() else None,
        }

    # -- make ------------------------------------------------------------------

    def _shown_claims(self, loaded: Loaded) -> list[Claim]:
        shown = loaded.state.claims_shown
        return [c for c in loaded.dossier.claims if c.id in shown]

    def _headline_exercise(self, loaded: Loaded) -> dict[str, Any] | None:
        cached = _choices(loaded.state, "headline_exercise")
        if cached:
            payload = cached[-1].payload
            return None if payload.get("dropped") else payload.get("exercise")
        shown = self._shown_claims(loaded)
        context = {
            "task": "headline",
            "title_fr": loaded.dossier.title_fr,
            "angle": current_angle(loaded.dossier, loaded.plan, loaded.state).fr,
            "claims_shown": [{"id": c.id, "kind": c.kind, "fr": c.fr} for c in shown],
            "band": loaded.plan.learner.band,
        }
        reasons: list[str] = []
        exercise = None
        for _attempt in range(2):
            try:
                raw = self.provider.headline(context)
            except Exception as exc:  # noqa: BLE001 - authored (deterministic) headline when the model is down
                logger.warning("revue: headline provider failed ({}); authored headline", exc)
                raw = AUTHORED.headline(context)
            candidate = self._exercise_from(raw, seed=str(loaded.row.id))
            results = check_distinguishable(candidate, shown) if candidate else []
            reasons = [r.reason or "" for r in failures(results)] if candidate else ["malformed"]
            if candidate and not reasons:
                exercise = candidate
                break
        if exercise is None:
            loaded.state.append("choice", kind="headline_exercise", dropped=True, reasons=reasons)
        else:
            loaded.state.append("choice", kind="headline_exercise", dropped=False, exercise=exercise)
        self._save(loaded)
        return exercise

    @staticmethod
    def _exercise_from(raw: Any, *, seed: str) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        answer = raw.get("answer") if isinstance(raw.get("answer"), dict) else {}
        distractors = [d for d in raw.get("distractors") or [] if isinstance(d, dict)]
        answer_text = str(answer.get("text_fr") or "").strip()
        if not answer_text or len(distractors) != 2:
            return None
        rows = [("answer", answer_text, None)] + [
            ("distractor", str(d.get("text_fr") or "").strip(), d.get("contradicted_by")) for d in distractors
        ]
        if any(not text for _, text, _ in rows) or len({fold_keep_length(t) for _, t, _ in rows}) != 3:
            return None
        order = sorted(range(3), key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
        options = []
        contradicted: dict[str, str] = {}
        answer_id = ""
        for position_index, row_index in enumerate(order):
            option_id = f"h{position_index + 1}"
            role, text, claim_id = rows[row_index]
            options.append({"id": option_id, "text_fr": text})
            if role == "answer":
                answer_id = option_id
            elif claim_id:
                contradicted[option_id] = str(claim_id)
        return {
            "format": "choice",
            "options": options,
            "answer": answer_id,
            "supported_by": answer.get("supported_by"),
            "contradicted_by": contradicted,
        }

    def make_options(self, row: RevueSession) -> RvMakeOffer:
        loaded = load(row)
        if row.status != "active" or loaded.state.closed:
            raise RevueError(409, "revue_session_closed")
        exercise = self._headline_exercise(loaded)
        options: list[Any] = []
        if exercise is not None:
            options.append(RvHeadlineChoiceOffer(options=[RvHeadlineOption(**o) for o in exercise["options"]]))
        question = open_question(loaded.state)
        options.append(RvReaderQuestionOffer(
            seed_fr=str(question["text"]) if question else None,
            uncertainty_fr=question.get("uncertainty_text") if question else None,
        ))
        recommended = "reader_question" if question or exercise is None else "headline_choice"
        return RvMakeOffer(recommended=recommended, options=options)  # type: ignore[arg-type]

    def make(self, row: RevueSession, option: str, payload: dict[str, Any]) -> Any:
        loaded = load(row)
        state = loaded.state
        if row.status != "active" or state.closed:
            raise RevueError(409, "revue_session_closed")
        action = payload.get("action")
        if option == "headline_choice" and action == "pick":
            return self._pick_headline(loaded, str(payload.get("option_id") or ""))
        if option == "reader_question" and action == "propose":
            return self._propose_question(loaded, payload.get("text"))
        if option == "reader_question" and action == "send":
            return self._send_question(loaded, str(payload.get("text_fr") or ""))
        raise RevueError(422, "revue_unknown_option")

    def _pick_headline(self, loaded: Loaded, option_id: str) -> RvHeadlinePickResult:
        exercise = self._headline_exercise(loaded)
        if exercise is None:
            raise RevueError(409, "revue_make_unavailable", kind="headline_choice")
        texts = {o["id"]: o["text_fr"] for o in exercise["options"]}
        if option_id not in texts:
            raise RevueError(422, "revue_unknown_option")
        answer_id = exercise["answer"]
        correct = option_id == answer_id
        dossier = loaded.dossier
        shown = self._shown_claims(loaded)
        support_id = exercise.get("supported_by")
        claim = dossier.claims_by_id().get(str(support_id)) if support_id else None
        if claim is None:
            answer_words = content_words(texts[answer_id])
            claim = max(shown, key=lambda c: len(answer_words & content_words(c.fr)), default=dossier.claims[0])
        text = texts[answer_id]
        loaded.state.append("choice", kind="make", option="headline_choice")
        made_payload = {"kind": "headline_choice", "text_fr": text, "contribution": [[0, len(text)]] if correct else [],
                        "learner_fr": None, "picked": option_id, "correct": correct}
        loaded.state.append("artifact", **made_payload)
        self._save(loaded)
        return RvHeadlinePickResult(
            correct=correct,
            answer_id=answer_id,
            evidence=RvHeadlineEvidence(claim_id=claim.id, quote=claim.quote, source=_source(dossier, claim.source_id)),
            made=_made(made_payload),
        )

    def _propose_question(self, loaded: Loaded, text: str | None) -> RvQuestionProposeResult:
        state = loaded.state
        question = open_question(state)
        learner = re.sub(r"\s+", " ", str(text or "")).strip() or (str(question["text"]) if question else "")
        if not learner:
            raise RevueError(422, "revue_unknown_option", reason="no_question")
        context = {
            "task": "question",
            "learner_text": learner,
            "uncertainty": question.get("uncertainty_text") if question else None,
            "title_fr": loaded.dossier.title_fr,
            "band": loaded.plan.learner.band,
            "language": _gloss_language_of(loaded.plan),
        }
        try:
            raw = self.provider.question(context)
        except Exception as exc:  # noqa: BLE001
            logger.warning("revue: question provider failed ({}); the learner's words stand", exc)
            raw = AUTHORED.question(context)
        proposal = re.sub(r"\s+", " ", str((raw or {}).get("proposal_fr") or "")).strip()
        position = season_position(self.db, self._owner(loaded.row))
        if not proposal or knowledge_hits([proposal], position) or relative_dates(proposal):
            proposal = AUTHORED.question(context)["proposal_fr"]
        why = (raw or {}).get("why_native")
        draft = RvQuestionDraft(
            learner_fr=learner,
            proposal_fr=proposal,
            contribution=contribution_spans(learner, proposal),
            why_native=str(why).strip() if isinstance(why, str) and why.strip() else None,
        )
        if not _choices(state, "make"):
            state.append("choice", kind="make", option="reader_question")
        state.append("choice", kind="question_draft", **draft.model_dump(mode="json"))
        self._save(loaded)
        return RvQuestionProposeResult(draft=draft)

    def _send_question(self, loaded: Loaded, text_fr: str) -> RvQuestionSendResult:
        state = loaded.state
        text = re.sub(r"\s+", " ", text_fr).strip()
        if not text:
            raise RevueError(422, "revue_unknown_option", reason="empty")
        drafts = _choices(state, "question_draft")
        question = open_question(state)
        learner = (drafts[-1].payload.get("learner_fr") if drafts else None) or (question["text"] if question else None)
        made_payload = {
            "kind": "reader_question",
            "text_fr": text,
            "contribution": [list(span) for span in contribution_spans(learner or text, text)],
            "learner_fr": learner,
        }
        if not _choices(state, "make"):
            state.append("choice", kind="make", option="reader_question")
        state.append("artifact", **made_payload)
        self._save(loaded)
        return RvQuestionSendResult(made=_made(made_payload))

    # -- close -------------------------------------------------------------------

    def close(self, row: RevueSession) -> tuple[RvSessionView, RvClosing]:
        loaded = load(row)
        state, dossier, plan = loaded.state, loaded.dossier, loaded.plan
        existing = _closing_of(state)
        if existing is not None:
            return session_view(loaded), existing

        artifact = state.current_artifact
        shown = self._shown_claims(loaded) or dossier.facts()[:FACTS_ON_ENTRY]
        question = open_question(state)
        context = {
            "task": "close",
            "title_fr": dossier.title_fr,
            "summary_fr": dossier.summary_fr,
            "angle": current_angle(dossier, plan, state).fr,
            "artifact": {k: artifact.get(k) for k in ("kind", "text_fr", "learner_fr")} if artifact else None,
            "claims_shown": [{"id": c.id, "kind": c.kind, "fr": c.fr} for c in shown],
            "open_question": question["text"] if question else None,
            "band": plan.learner.band,
        }
        try:
            raw = self.provider.close(context)
        except Exception as exc:  # noqa: BLE001 - an authored close with whatever exists
            logger.warning("revue: close provider failed ({}); authored close", exc)
            raw = AUTHORED.close(context)
        raw = raw if isinstance(raw, dict) else {}
        position = season_position(self.db, self._owner(row))
        kind = str(artifact.get("kind")) if artifact else "none"

        romy_line = re.sub(r"\s+", " ", str(raw.get("romy_line_fr") or "")).strip()
        if not romy_line or knowledge_hits([romy_line], position) or relative_dates(romy_line):
            romy_line = CLOSE_LINES.get(kind, CLOSE_LINES["none"])

        if artifact:
            headline = str(artifact.get("text_fr") or dossier.title_fr)
            contribution = [tuple(span) for span in artifact.get("contribution") or []]
        else:
            headline = re.sub(r"\s+", " ", str(raw.get("headline_fr") or "")).strip() or dossier.title_fr
            if knowledge_hits([headline], position) or relative_dates(headline):
                headline = dossier.title_fr
            contribution = []

        body: list[str] = []
        for line in raw.get("body_lines") or []:
            line = re.sub(r"\s+", " ", str(line or "")).strip()
            if line and not knowledge_hits([line], position) and not relative_dates(line):
                body.append(line)
        for claim in shown:
            if len(body) >= 3:
                break
            if claim.fr not in body:
                body.append(claim.fr)
        body = body[:3]

        source_names = list(dict.fromkeys(_source(dossier, c.source_id).name for c in shown))
        sources = [_source(dossier, sid) for sid in dict.fromkeys(c.source_id for c in shown)]
        _, number = parse_week(row.week)
        dispatch = RvDispatch(
            kicker_fr=f"Le Papier de Romy · semaine {number}",
            headline_fr=headline,
            body_fr=body,
            contribution=contribution,
            byline_fr="Romy Tremblay, avec toi · d'après " + " et ".join(source_names) if source_names else "Romy Tremblay, avec toi",
            sources=sources,
        )
        learner_texts = " ".join(str(e.payload.get("text_fr") or "") for e in state.events if e.kind == "turn_learner")
        language = _gloss_language_of(plan)
        kept = RvKept(
            words=[
                RvClosedWord(fr=item.fr, gloss=item.gloss.get(language, ""), claim_id=item.claim_id,
                             used=_contains_word(learner_texts, item.fr))
                for item in plan.vocabulary
            ],
            claims=[rv_claim(dossier, c) for c in shown],
        )
        if kind == "reader_question":
            question_kept = str(artifact.get("text_fr")) if artifact else None
        else:
            question_kept = str(question["text"]) if question else None
        closing = RvClosing(romy_line_fr=romy_line, dispatch=dispatch, kept=kept, question_kept_fr=question_kept)

        state.append("turn_romy", beat="close", role="close", text_fr=romy_line)
        state.append("closed", closing=closing.model_dump(mode="json"))
        row.status = "closed"
        row.closed_at = datetime.now(UTC)
        self._remember(loaded, artifact=artifact, kind=kind)
        self._save(loaded)
        return session_view(loaded), closing

    def _remember(self, loaded: Loaded, *, artifact: dict[str, Any] | None, kind: str) -> None:
        """Romy's ``NPCMemory`` of the Revue (§7 "writing back"; guests are phase 2)."""

        from app.db.models.npc import NPC, NPCMemory

        row, dossier = loaded.row, loaded.dossier
        _, number = parse_week(row.week)
        place = stage_for(dossier, loaded.plan).place_fr
        content = f"Semaine {number}, {_lower_first(place)} : on a travaillé ensemble sur « {dossier.title_fr} »."
        if kind == "reader_question" and artifact:
            content += f" Tu as posé la question : « {artifact.get('text_fr')} »."
        elif kind == "headline_choice" and artifact:
            content += f" Tu as choisi le titre : « {artifact.get('text_fr')} »."
        else:
            content += " On n'a rien bouclé de plus."
        learner_turns = [e for e in loaded.state.events if e.kind == "turn_learner"]
        quote = (artifact or {}).get("learner_fr") or (learner_turns[-1].payload.get("text_fr") if learner_turns else None)
        if self.db.get(NPC, ROMY_ID) is None:
            # The npc_memories FK needs the cast member's row; the season cast has no NPC rows of its own.
            self.db.add(NPC(id=ROMY_ID, name="Romy Tremblay", role="journaliste", backstory="Le Papier de Romy (WP-119)"))
            self.db.flush()
        self.db.add(NPCMemory(
            user_id=row.user_id,
            npc_id=ROMY_ID,
            memory_type="interaction",
            content=content,
            scene_id=str(row.id),
            sentiment="neutral",
            importance=5,
            player_quote=str(quote)[:1000] if quote else None,
        ))

    # -- read ----------------------------------------------------------------------

    def view(self, row: RevueSession) -> RvSessionView:
        return session_view(load(row))


def owned_session(db: Session, user: Any, session_id: str | uuid.UUID, *, lock: bool = False) -> RevueSession:
    try:
        key = session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
    except ValueError as exc:
        raise RevueError(404, "revue_session_not_found") from exc
    query = select(RevueSession).where(RevueSession.id == key, RevueSession.user_id == user.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise RevueError(404, "revue_session_not_found")
    return row


__all__ = [
    "AUTHORED",
    "FALLBACK_LINE",
    "FakeRevueProvider",
    "OpenAIRevueProvider",
    "RevueEncounter",
    "RevueError",
    "RevueProvider",
    "RevueProviderError",
    "STEER_LINE",
    "available_dossiers",
    "current_week",
    "default_provider",
    "grade_turn",
    "owned_session",
    "season_position",
    "session_view",
    "thread_items",
    "week_view",
]
