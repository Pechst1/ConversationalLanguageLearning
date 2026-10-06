"""WP-34 — «Apportez votre français» : a real document, read once and used.

Everything else the learner reads in this app was written for them. This is the
one thing that was not: the menu of the café downstairs, the letter from the
landlord about the heating, the email from the school. TBLT calls this needs
analysis with authentic materials; the product argument is simpler — a learner
who can read the letter that is actually on their table has been helped in a way
that a generated letter cannot help them.

The shape of the package
------------------------

1. **One call per artefact.** Text or photograph goes to a vision-capable model
   once, and comes back as a *structure*: what kind of document it is, a summary
   at the learner's band, the key facts, and the words the learner is unlikely
   to know. The derived Courrier task comes back in the same call, so a document
   costs exactly one paid request and never two.
2. **Glossing is not the model's job.** The model *nominates* unknown words; the
   gloss comes from :mod:`app.services.glosses` against the app's own vocabulary,
   in the learner's own language, exactly as every other gloss in the app does.
   A word the vocabulary does not have falls back to the model's gloss and says
   so, rather than quietly serving a second, differently-sourced translation.
3. **The task is a Courrier mission, not a new grader.** :mod:`app.services.missions`
   builds a real :class:`RealWorldMission` row from the artefact, and the learner
   answers it through ``POST /missions/{id}/submit`` — the same endpoint, the same
   :class:`MissionCorrectionService`, the same six correction gates fixed on
   2026-09-05. This module grades nothing.
4. **Unknown words are learner-sourced vocabulary.** They enter the normal FSRS
   queue stamped ``provenance="learner_artefact"``, which is what lets WP-29 count
   them as *targets* — words that are meant to be new — instead of accidents to
   be generated away.

Privacy, which is the reason most of this file looks the way it does
-------------------------------------------------------------------

* An artefact is private to one learner and **never becomes story canon**. This
  module imports no serial or living-story writer, and
  ``test_intake.py::test_intake_never_writes_story_canon`` scans this source with
  ``ast`` to keep it that way — the same guard WP-31 put on rehearsals.
* An artefact goes **nowhere but the model call**. No news service, no telemetry
  payload, no digest line carries the document's text: the pilot row records
  tokens, cost and provider, never content.
* An artefact is **deletable**, and deleting it deletes the Courrier task derived
  from it, because that task quotes the document.
* **The photograph itself is never stored.** It is bounded, sent, and dropped.

Honest under failure: a provider that does not answer, answers unusably, or is
handed an illegible photo leaves the artefact ``unread``. The learner reads «Non
lu» and is offered a retry. There is no partial reading and no invented one.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.intake import (
    ARTEFACT_TASK_KINDS,
    ARTEFACT_TYPES,
    LEARNER_SOURCED_PROVENANCE,
    LearnerArtefact,
)
from app.db.models.mission import RealWorldMission
from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.chrome_language import chrome_language, pick
from app.services.glosses import normalize_language, resolve_gloss
from app.services.journey_content import learner_level_band
from app.services.llm_service import LLMProviderError, LLMService
from app.services.pilot_events import PilotEventService

INTAKE_VERSION = "intake-v1"
INTAKE_PROMPT_VERSION = "intake-read-v1"

#: The pilot-ledger event type for the one paid call an artefact costs.
#: ``scripts/pilot_digest.py`` reads event types by name.
INTAKE_EVENT_TYPE = "intake_artefact"

#: Bounds on learner-controlled payloads reaching a paid endpoint. The character
#: budget is generous — a landlord's letter is about 1,500 characters — and it
#: exists so one pasted book cannot size the request.
SOURCE_TEXT_MAX_CHARS = 6000
#: Below this there is no document, only a phrase. Refused before it is paid for.
SOURCE_TEXT_MIN_CHARS = 20

#: Image formats a vision model actually accepts. Anything else is refused
#: locally rather than discovered by paying for a 400.
ALLOWED_IMAGE_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
)

#: How many unknown words one artefact may contribute. A document that produced
#: thirty new cards would bury the learner's queue under one afternoon's menu.
MAX_UNKNOWN_WORDS = 8
#: How many facts a card can carry before it stops being a summary.
MAX_KEY_FACTS = 5

#: The summary is «at the learner's level», and that has to mean something
#: checkable. Word ceilings by band, in the spirit of ``journey_content``'s
#: ``BAND_LIMITS``: an A1 learner is not handed 120 words of French about their
#: own gas bill.
SUMMARY_WORD_LIMITS: dict[str, int] = {
    "A1": 40,
    "A2": 60,
    "B1": 90,
    "B2": 120,
    "C1": 140,
    "C2": 140,
}
DEFAULT_SUMMARY_WORDS = 60

#: What kind of document this is. A label is the app's own words, so it follows
#: the one-language rule (``app/services/chrome_language.py``): the learner's
#: language up to A2, French from B1. ``public_view`` serves the table and the
#: string resolved for the reader; the French entry is what is stored and what
#: the Courrier mission quotes.
_TYPE_LABELS: dict[str, dict[str, str]] = {
    "menu": {"fr": "Un menu", "en": "A menu", "de": "Eine Speisekarte"},
    "lettre": {"fr": "Une lettre", "en": "A letter", "de": "Ein Brief"},
    "courriel": {"fr": "Un courriel", "en": "An email", "de": "Eine E-Mail"},
    "affiche": {"fr": "Une affiche", "en": "A poster", "de": "Ein Aushang"},
    "facture": {"fr": "Une facture", "en": "A bill", "de": "Eine Rechnung"},
    "formulaire": {"fr": "Un formulaire", "en": "A form", "de": "Ein Formular"},
    "message": {"fr": "Un message", "en": "A message", "de": "Eine Nachricht"},
    "autre": {"fr": "Un document", "en": "A document", "de": "Ein Dokument"},
}
_TYPE_LABELS_FR: dict[str, str] = {key: table["fr"] for key, table in _TYPE_LABELS.items()}

#: The three shapes a derived task can take, and the label that introduces each.
_TASK_LABELS: dict[str, dict[str, str]] = {
    "reply": {"fr": "Répondre", "en": "Reply", "de": "Antworten"},
    "decide": {"fr": "Choisir", "en": "Choose", "de": "Auswählen"},
    "ask": {"fr": "Demander", "en": "Ask", "de": "Nachfragen"},
}
_TASK_LABELS_FR: dict[str, str] = {key: table["fr"] for key, table in _TASK_LABELS.items()}

#: Who the learner writes to when the document names nobody. Chrome, not the
#: document's words; the French entry is the mission's contact name.
COUNTERPART_FALLBACK: dict[str, str] = {
    "fr": "votre correspondant",
    "en": "your correspondent",
    "de": "dein Gegenüber",
}

_LANGUAGE_NAMES = {"en": "English", "de": "German (informal du)"}

_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+")


class IntakeRefused(Exception):
    """A refusal the learner should read, not a 500.

    ``code`` is stable and machine-readable; the French sentence lives in the
    router, beside every other sentence a learner sees.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# Normalising what the learner and the model hand over
# ---------------------------------------------------------------------------


def normalize_source_text(value: Any) -> str:
    """Collapse whitespace and bound the document. Never truncates silently
    without the caller being able to see it — the bound is a constant."""

    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    cleaned = "\n".join(line for line in lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned[:SOURCE_TEXT_MAX_CHARS]


def normalize_word(value: Any) -> str:
    """Fold a headword for lookup: lowercase, accents stripped, quotes folded."""

    text = str(value or "").strip().lower()
    text = text.replace("’", "'").replace("‘", "'").replace("ʼ", "'")
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join(decomposed.encode("ascii", "ignore").decode("ascii").split())


def summary_word_limit(band: str) -> int:
    return SUMMARY_WORD_LIMITS.get(str(band or "").upper(), DEFAULT_SUMMARY_WORDS)


def bound_summary(value: Any, *, band: str) -> tuple[str, bool]:
    """The summary, cut to the band's word ceiling. Returns ``(text, bounded)``.

    A cut is *declared*, not hidden: the card shows the summary it was given and
    the payload says it was shortened, so nothing pretends a truncated reading is
    the whole reading.
    """

    words = str(value or "").split()
    limit = summary_word_limit(band)
    if len(words) <= limit:
        return " ".join(words), False
    return " ".join(words[:limit]).rstrip(" ,;:") + " …", True


# ---------------------------------------------------------------------------
# The one model call
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You read one real document a French learner has brought in and describe it "
    "for them. You never invent content that is not in the document. If the "
    "document is unreadable or is not a document, you say so with "
    '{"readable": false} and nothing else.'
)


def read_prompt(
    *, band: str, native_language: str, has_image: bool, chrome: str | None = None
) -> str:
    """The instruction half of the one call. Kept in one place so the tests can
    assert what a learner's document is and is not asked to be used for.

    ``chrome`` is the learner's chrome language (one-language rule). When it is
    not French, the task's instruction and success line — the app's own words
    to the learner — are also asked for in it (``instruction_native`` /
    ``success_native``). The document's reading stays French.
    """

    limit = summary_word_limit(band)
    language = normalize_language(native_language)
    native_name = _LANGUAGE_NAMES.get(str(chrome or ""))
    native_keys = ', "instruction_native": "...", "success_native": "..."' if native_name else ""
    native_rule = (
        f' "instruction_native" and "success_native" are the same two sentences in {native_name}, '
        "for a beginner's interface; French words from the document stay in French."
        if native_name
        else ""
    )
    return (
        "Read the document and answer with JSON only, no prose around it.\n\n"
        "Fields:\n"
        '  "readable": true or false. False if you cannot read it at all.\n'
        f'  "transcript": the document\'s own words, verbatim, at most {SOURCE_TEXT_MAX_CHARS} '
        "characters."
        + (
            " Transcribe what you can see in the photograph.\n"
            if has_image
            else " Repeat the text you were given, tidied of layout noise.\n"
        )
        + f'  "type": one of {", ".join(ARTEFACT_TYPES)}.\n'
        '  "title_fr": a short French label for this document, at most 8 words.\n'
        f'  "summary_fr": what the document says, in French at CEFR {band}, at most '
        f"{limit} words. Simple sentences. Do not add advice or opinion.\n"
        '  "key_facts": up to '
        f"{MAX_KEY_FACTS} objects "
        '{"label_fr": "...", "value_fr": "..."} — the concrete things the learner '
        "needs (a price, a date, a deadline, a phone number, a name). Only facts "
        "that are actually in the document.\n"
        '  "unknown_words": up to '
        f"{MAX_UNKNOWN_WORDS} objects "
        '{"word": "...", "lemma": "...", "gloss": "...", "example_fr": "..."} — words '
        f"in the document a CEFR {band} learner is unlikely to know. \"word\" is the form "
        'as it appears; "lemma" is its dictionary form; "gloss" is a short '
        f'translation in the language with code "{language}"; "example_fr" is the '
        "phrase from the document that contains it.\n"
        '  "task": one object {"kind": "reply" | "decide" | "ask", '
        '"instruction_fr": "...", "counterpart_fr": "...", "register": "tu" | "vous", '
        '"success_fr": "..."' + native_keys + '} — ONE thing the learner should now do in French '
        "*because of* this document. \"reply\" when the document expects an answer, "
        '"decide" when it offers a choice (a menu, options), "ask" when something '
        "in it is missing or unclear. \"instruction_fr\" is one French sentence "
        "addressed to the learner. \"counterpart_fr\" is who they are writing or "
        "speaking to. \"success_fr\" is one French sentence saying what a good "
        "answer achieves." + native_rule + "\n\n"
        "Rules: never invent a price, a date or a name. Never quote a person's "
        "contact details back into summary_fr. Write every *_fr field in French."
    )


def text_messages(
    *, document: str, band: str, native_language: str, chrome: str | None = None
) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": (
                read_prompt(
                    band=band, native_language=native_language, has_image=False, chrome=chrome
                )
                + "\n\nDOCUMENT:\n"
                + document
            ),
        }
    ]


def vision_messages(
    *,
    image_bytes: bytes,
    content_type: str,
    band: str,
    native_language: str,
    chrome: str | None = None,
) -> list[dict[str, Any]]:
    """OpenAI-shaped multimodal content blocks.

    ``LLMService`` passes ``messages`` through to the provider unchanged, so a
    list-valued ``content`` reaches OpenAI as written. Anthropic's block shape
    differs; an Anthropic-primary deployment therefore cannot read a photograph
    until the adapter written out in ``WP-34-INTAKE.md`` lands in
    ``llm_service.py`` (not this package's lease). Until then a photo on such a
    deployment fails the call and the learner is told «non lu» — which is wrong
    in a boring, honest way rather than in an invented one.
    """

    encoded = base64.b64encode(image_bytes).decode("ascii")
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": read_prompt(
                        band=band, native_language=native_language, has_image=True, chrome=chrome
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                },
            ],
        }
    ]


def _json_block(content: Any) -> dict[str, Any] | None:
    text = str(content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except (TypeError, ValueError):
            return None
    return parsed if isinstance(parsed, dict) else None


@dataclass(frozen=True)
class Reading:
    """A usable reading of one document. Anything short of this is ``unread``."""

    type: str
    title_fr: str
    summary_fr: str
    summary_bounded: bool
    transcript: str
    key_facts: tuple[dict[str, str], ...] = ()
    unknown_words: tuple[dict[str, str], ...] = ()
    task: dict[str, str] = field(default_factory=dict)

    def as_artefact(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "type_label_fr": _TYPE_LABELS_FR.get(self.type, _TYPE_LABELS_FR["autre"]),
            "title_fr": self.title_fr,
            "summary_fr": self.summary_fr,
            "summary_bounded": self.summary_bounded,
            "key_facts": [dict(fact) for fact in self.key_facts],
        }


def parse_reading(
    raw: Any, *, band: str, fallback_text: str = "", chrome: str | None = None
) -> Reading | None:
    """Validate the model's answer. ``None`` means «non lu» — never a partial card.

    Every required field is checked here rather than at render time, because a
    half-read document is exactly the thing this package must not show: a
    plausible French summary of a letter nobody actually read is worse than no
    summary at all.
    """

    payload = _json_block(raw)
    if not payload:
        return None
    if payload.get("readable") is False:
        return None

    artefact_type = str(payload.get("type") or "").strip().lower()
    if artefact_type not in ARTEFACT_TYPES:
        artefact_type = "autre"

    summary_fr, bounded = bound_summary(payload.get("summary_fr"), band=band)
    if len(summary_fr.split()) < 3:
        return None

    transcript = normalize_source_text(payload.get("transcript") or fallback_text)
    if not transcript:
        return None

    title_fr = " ".join(str(payload.get("title_fr") or "").split()[:8]).strip()
    if not title_fr:
        title_fr = _TYPE_LABELS_FR.get(artefact_type, _TYPE_LABELS_FR["autre"])

    facts: list[dict[str, str]] = []
    for raw_fact in payload.get("key_facts") or []:
        if not isinstance(raw_fact, dict):
            continue
        label = " ".join(str(raw_fact.get("label_fr") or "").split())[:60]
        value = " ".join(str(raw_fact.get("value_fr") or "").split())[:120]
        if label and value:
            facts.append({"label_fr": label, "value_fr": value})
        if len(facts) >= MAX_KEY_FACTS:
            break

    words: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_word in payload.get("unknown_words") or []:
        if not isinstance(raw_word, dict):
            continue
        surface = " ".join(str(raw_word.get("word") or "").split())[:60]
        key = normalize_word(surface)
        if not key or key in seen:
            continue
        # A "word" the document does not contain is a hallucination, and it would
        # become a vocabulary card the learner never met. Grounded or dropped.
        if key not in normalize_word(transcript).split():
            if key not in normalize_word(transcript):
                continue
        seen.add(key)
        words.append(
            {
                "word": surface,
                "lemma": " ".join(str(raw_word.get("lemma") or surface).split())[:60],
                "gloss": " ".join(str(raw_word.get("gloss") or "").split())[:120],
                "example_fr": " ".join(str(raw_word.get("example_fr") or "").split())[:200],
            }
        )
        if len(words) >= MAX_UNKNOWN_WORDS:
            break

    task = _parse_task(payload.get("task"), artefact_type=artefact_type, chrome=chrome)
    if task is None:
        return None

    return Reading(
        type=artefact_type,
        title_fr=title_fr,
        summary_fr=summary_fr,
        summary_bounded=bounded,
        transcript=transcript,
        key_facts=tuple(facts),
        unknown_words=tuple(words),
        task=task,
    )


def _parse_task(
    raw: Any, *, artefact_type: str, chrome: str | None = None
) -> dict[str, Any] | None:
    """The derived Courrier task. Without one there is no package, so a missing
    or unusable task is «non lu» rather than a document with nothing to do."""

    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "").strip().lower()
    if kind not in ARTEFACT_TASK_KINDS:
        # A menu is a choice; anything that arrived addressed to the learner
        # expects an answer. Only these two are safe to infer.
        kind = "decide" if artefact_type == "menu" else "reply"
    instruction = " ".join(str(raw.get("instruction_fr") or "").split())[:280]
    if len(instruction.split()) < 3:
        return None
    counterpart = " ".join(str(raw.get("counterpart_fr") or "").split())[:80]
    register = str(raw.get("register") or "").strip().lower()
    if register not in {"tu", "vous"}:
        register = "vous"
    success = " ".join(str(raw.get("success_fr") or "").split())[:200]
    # The instruction and the success line are the app's words to the learner:
    # kept as {fr, <chrome>} so the card can say them in the chrome language.
    instruction_by_language = {"fr": instruction}
    success_by_language = {"fr": success} if success else {}
    if chrome in _LANGUAGE_NAMES:
        native_instruction = " ".join(str(raw.get("instruction_native") or "").split())[:280]
        native_success = " ".join(str(raw.get("success_native") or "").split())[:200]
        if native_instruction:
            instruction_by_language[chrome] = native_instruction
        if native_success and success:
            success_by_language[chrome] = native_success
    return {
        "kind": kind,
        "kind_label_fr": _TASK_LABELS_FR[kind],
        "instruction_fr": instruction,
        "instruction_by_language": instruction_by_language,
        "counterpart_fr": counterpart or COUNTERPART_FALLBACK["fr"],
        "register": register,
        "success_fr": success,
        "success_by_language": success_by_language,
    }


# ---------------------------------------------------------------------------
# Glossing — the app's own resolver, in the learner's own language
# ---------------------------------------------------------------------------


def resolve_glosses(
    db: Session, *, user: User, words: tuple[dict[str, str], ...]
) -> list[dict[str, Any]]:
    """Gloss each nominated word through :mod:`app.services.glosses`.

    The app's own vocabulary wins, because that is the gloss the learner will see
    again on the card tomorrow and two different translations of one word is how
    a learner stops trusting the app. ``gloss_source`` says where the gloss came
    from, so a model fallback is labelled rather than passed off as the app's.
    """

    native = normalize_language(getattr(user, "native_language", None))
    language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
    resolved: list[dict[str, Any]] = []
    for item in words:
        key = normalize_word(item.get("lemma") or item.get("word"))
        row = _vocabulary_row(db, key=key, surface=item.get("word", ""), language=language)
        gloss, gloss_language = ("", None)
        if row is not None:
            gloss, gloss_language = resolve_gloss(row, native)
        source = "vocabulary"
        if not gloss:
            gloss = str(item.get("gloss") or "").strip()
            gloss_language = native if gloss else None
            source = "model" if gloss else "none"
        resolved.append(
            {
                "word": item.get("word", ""),
                "lemma": item.get("lemma") or item.get("word", ""),
                "gloss": gloss,
                "gloss_language": gloss_language,
                "gloss_source": source,
                "example_fr": item.get("example_fr", ""),
                "word_id": int(row.id) if row is not None else None,
            }
        )
    return resolved


def _vocabulary_row(
    db: Session, *, key: str, surface: str, language: str
) -> VocabularyWord | None:
    if not key:
        return None
    stmt = (
        select(VocabularyWord)
        .where(VocabularyWord.language == language, VocabularyWord.normalized_word == key)
        .limit(1)
    )
    row = db.scalars(stmt).first()
    if row is not None:
        return row
    other = normalize_word(surface)
    if other and other != key:
        stmt = (
            select(VocabularyWord)
            .where(VocabularyWord.language == language, VocabularyWord.normalized_word == other)
            .limit(1)
        )
        return db.scalars(stmt).first()
    return None


# ---------------------------------------------------------------------------
# The cost bound
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapState:
    """The weekly bound, as the learner sees it."""

    limit: int
    used: int
    spent_usd: float
    ceiling_usd: float
    enabled: bool

    @property
    def remaining(self) -> int:
        if self.limit <= 0:
            return 0
        return max(0, self.limit - self.used)

    @property
    def blocked_by(self) -> str | None:
        if not self.enabled or self.limit <= 0:
            return "intake_disabled"
        if self.used >= self.limit:
            return "weekly_cap_reached"
        if self.ceiling_usd > 0 and self.spent_usd >= self.ceiling_usd:
            return "cost_ceiling_reached"
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "spent_usd": round(self.spent_usd, 4),
            "ceiling_usd": self.ceiling_usd,
            "enabled": self.enabled,
        }


def cap_state(db: Session, user: User, *, now: datetime | None = None) -> CapState:
    """Both halves of the bound, counted over the same rolling seven days.

    The count bounds how often; the money bounds how much. A refusal names which
    one it was, because "you have used your five" and "this week's reading budget
    is spent" are different sentences and the learner deserves the right one.
    """

    now = now or datetime.now(UTC)
    since = now - timedelta(days=7)
    rows = list(
        db.scalars(
            select(LearnerArtefact).where(
                LearnerArtefact.user_id == user.id,
                LearnerArtefact.created_at >= since,
            )
        )
    )
    events = list(
        db.scalars(
            select(PilotEvent).where(
                PilotEvent.user_id == user.id,
                PilotEvent.event_type == INTAKE_EVENT_TYPE,
                PilotEvent.occurred_at >= since,
            )
        )
    )
    return CapState(
        limit=int(settings.ATELIER_INTAKE_WEEKLY_CAP),
        # An unread artefact still counts: the call was already paid for.
        used=len(rows),
        spent_usd=float(sum(float(event.cost_usd or 0.0) for event in events)),
        ceiling_usd=float(settings.ATELIER_INTAKE_WEEKLY_COST_CEILING_USD),
        enabled=bool(settings.ATELIER_INTAKE_ENABLED),
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _chrome_task_view(task: dict[str, Any], language: str) -> dict[str, Any]:
    """The task's chrome — its label, instruction, success line and a fallback
    counterpart — as ``*_by_language`` tables plus the string for ``language``.
    Rows written before the tables existed get them from what they stored."""

    if not task:
        return {}
    view = dict(task)
    kind = str(task.get("kind") or "reply")
    labels = _TASK_LABELS.get(kind, _TASK_LABELS["reply"])
    instruction = task.get("instruction_by_language")
    if not isinstance(instruction, dict) or not instruction:
        instruction = {"fr": str(task.get("instruction_fr") or "")}
    success = task.get("success_by_language")
    if not isinstance(success, dict):
        success = {"fr": str(task.get("success_fr") or "")} if task.get("success_fr") else {}
    view["kind_label_by_language"] = dict(labels)
    view["kind_label"] = pick(labels, language)
    view["instruction_by_language"] = dict(instruction)
    view["instruction"] = pick(instruction, language)
    view["success_by_language"] = dict(success)
    view["success"] = pick(success, language)
    if str(task.get("counterpart_fr") or "").strip() == COUNTERPART_FALLBACK["fr"]:
        view["counterpart_by_language"] = dict(COUNTERPART_FALLBACK)
    return view


def _chrome_artefact_view(payload: dict[str, Any], language: str) -> dict[str, Any]:
    if not payload:
        return {}
    view = dict(payload)
    labels = _TYPE_LABELS.get(str(payload.get("type") or "autre"), _TYPE_LABELS["autre"])
    view["type_label_by_language"] = dict(labels)
    view["type_label"] = pick(labels, language)
    return view


def public_view(
    artefact: LearnerArtefact | None, *, language: str = "fr"
) -> dict[str, Any] | None:
    """The only serializer. There is no other way for an artefact to reach the
    wire, which is how the source document stays out of anything but its owner's
    own page.

    ``language`` is the reader's chrome language: the labels and the task's
    instruction arrive as ``{fr, en, de}`` tables plus the resolved string.
    """

    if artefact is None:
        return None
    return {
        "id": str(artefact.id),
        "version": artefact.version,
        "status": artefact.status,
        "source_kind": artefact.source_kind,
        "source_text": artefact.source_text,
        "artefact": _chrome_artefact_view(artefact.artefact or {}, language),
        "task": _chrome_task_view(artefact.task or {}, language),
        "mission_id": str(artefact.mission_id) if artefact.mission_id else None,
        "queued_word_count": len(artefact.queued_word_ids or []),
        "created_at": artefact.created_at.isoformat() if artefact.created_at else None,
    }


# ---------------------------------------------------------------------------
# WP-29 — what a learner-sourced word is, seen from the coverage guard
# ---------------------------------------------------------------------------


def learner_sourced_targets(db: Session, user: User) -> frozenset[str]:
    """Every word this learner brought in themselves and has not yet nailed.

    WP-29's :func:`~app.services.lexical_coverage.check_scene_coverage` splits a
    scene's unknown words into *targets* (meant to be new) and *accidents* (to be
    generated away). A word off the learner's own landlord letter is the most
    target-like word there is, so it is fed to that guard the same way due
    vocabulary is — see ``docs/implementation/atelier-v2/WP-34-INTAKE.md`` §5 for
    the exact call site, which lives in a file this package does not lease.
    """

    rows = db.execute(
        select(VocabularyWord.word, VocabularyWord.normalized_word)
        .join(UserVocabularyProgress, UserVocabularyProgress.word_id == VocabularyWord.id)
        .where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.provenance == LEARNER_SOURCED_PROVENANCE,
        )
    ).all()
    targets: set[str] = set()
    for word, normalized in rows:
        for surface in (word, normalized):
            value = str(surface or "").strip()
            if value:
                targets.add(value)
    return frozenset(targets)


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------


class IntakeService:
    """Read one document, queue its words, and hand the task to Le Courrier."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- provider ---------------------------------------------------------

    def _get_llm_service(self) -> LLMService | None:
        """Patched wholesale in tests. A missing provider is «non lu», not a 500."""

        try:
            return LLMService()
        except Exception:  # pragma: no cover - defensive; no key configured
            logger.warning("Intake has no LLM provider configured")
            return None

    # -- reads ------------------------------------------------------------

    def list_for(self, user: User, *, limit: int = 20) -> list[LearnerArtefact]:
        return list(
            self.db.scalars(
                select(LearnerArtefact)
                .where(LearnerArtefact.user_id == user.id)
                .order_by(LearnerArtefact.created_at.desc())
                .limit(max(1, min(100, limit)))
            )
        )

    def get(self, user: User, artefact_id: UUID) -> LearnerArtefact | None:
        artefact = self.db.get(LearnerArtefact, artefact_id)
        if artefact is None or artefact.user_id != user.id:
            return None
        return artefact

    # -- the one write that costs money -----------------------------------

    def submit_text(self, user: User, *, text: str) -> LearnerArtefact:
        document = normalize_source_text(text)
        if len(document) < SOURCE_TEXT_MIN_CHARS:
            raise IntakeRefused("document_too_short")
        return self._submit(user, source_kind="text", document=document)

    def submit_image(
        self, user: User, *, data: bytes, content_type: str
    ) -> LearnerArtefact:
        media_type = str(content_type or "").split(";", 1)[0].strip().lower()
        if media_type not in ALLOWED_IMAGE_TYPES:
            raise IntakeRefused("image_type_unsupported")
        if not data:
            raise IntakeRefused("image_empty")
        if len(data) > int(settings.ATELIER_INTAKE_MAX_IMAGE_BYTES):
            raise IntakeRefused("image_too_large")
        return self._submit(
            user, source_kind="image", document="", image=(data, media_type)
        )

    def submit_image_base64(
        self, user: User, *, data_base64: str, content_type: str
    ) -> LearnerArtefact:
        try:
            raw = base64.b64decode(str(data_base64 or ""), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise IntakeRefused("image_undecodable") from exc
        return self.submit_image(user, data=raw, content_type=content_type)

    def _submit(
        self,
        user: User,
        *,
        source_kind: str,
        document: str,
        image: tuple[bytes, str] | None = None,
    ) -> LearnerArtefact:
        state = cap_state(self.db, user)
        blocked = state.blocked_by
        if blocked:
            raise IntakeRefused(blocked)

        band = learner_level_band(user)
        native = normalize_language(getattr(user, "native_language", None))
        reading, failure = self._read(
            user=user,
            band=band,
            native=native,
            document=document,
            image=image,
            chrome=chrome_language(getattr(user, "native_language", None), band),
        )

        artefact = LearnerArtefact(
            user_id=user.id,
            version=INTAKE_VERSION,
            status="read" if reading else "unread",
            source_kind=source_kind,
            # On the unread path a pasted document is kept, so the learner can
            # retry without pasting it again. A photograph has nothing to keep:
            # the bytes were never stored, which is the point.
            source_text=reading.transcript if reading else document,
            artefact={},
            task={},
            queued_word_ids=[],
            failure_reason=None if reading else failure,
        )
        self.db.add(artefact)
        self.db.flush([artefact])

        if reading is None:
            self.db.commit()
            self.db.refresh(artefact)
            return artefact

        glossed = resolve_glosses(self.db, user=user, words=reading.unknown_words)
        payload = reading.as_artefact()
        payload["glossed_words"] = glossed
        payload["band"] = band
        payload["gloss_language"] = native
        artefact.artefact = payload
        artefact.task = dict(reading.task)

        queued = self._queue_unknown_words(user=user, artefact=artefact, glossed=glossed)
        artefact.queued_word_ids = queued

        # The task becomes a real Courrier mission, graded by the existing
        # corrector at the existing endpoint. This module grades nothing.
        from app.services.missions import create_artefact_mission

        mission = create_artefact_mission(
            self.db,
            user=user,
            artefact_payload=payload,
            task=artefact.task,
            source_text=artefact.source_text,
            target_word_ids=queued,
        )
        artefact.mission_id = mission.id
        self.db.add(artefact)
        self.db.commit()
        self.db.refresh(artefact)
        return artefact

    def _read(
        self,
        *,
        user: User,
        band: str,
        native: str,
        document: str,
        image: tuple[bytes, str] | None,
        chrome: str | None = None,
    ) -> tuple[Reading | None, str | None]:
        llm = self._get_llm_service()
        if llm is None:
            return None, "no_provider"

        if image is not None:
            messages = vision_messages(
                image_bytes=image[0],
                content_type=image[1],
                band=band,
                native_language=native,
                chrome=chrome,
            )
            model = settings.ATELIER_INTAKE_VISION_MODEL
        else:
            messages = text_messages(
                document=document, band=band, native_language=native, chrome=chrome
            )
            model = settings.ATELIER_INTAKE_TEXT_MODEL

        try:
            result = llm.generate_chat_completion(
                messages,
                system_prompt=_SYSTEM_PROMPT,
                model=model,
                temperature=0.2,
                max_tokens=int(settings.ATELIER_INTAKE_MAX_TOKENS),
                response_format={"type": "json_object"},
                request_timeout=float(settings.ATELIER_INTAKE_TIMEOUT_SECONDS),
                # One call per artefact. A second provider attempt would be a
                # second paid read of the same document.
                disable_retries=True,
                max_provider_attempts=1,
            )
        except (LLMProviderError, Exception) as exc:  # noqa: BLE001 - never 500 a learner
            logger.warning("Intake read failed: {}", exc)
            self._record_cost(user=user, result=None, band=band, has_image=image is not None)
            return None, "provider_failed"

        self._record_cost(user=user, result=result, band=band, has_image=image is not None)
        reading = parse_reading(
            getattr(result, "content", ""), band=band, fallback_text=document, chrome=chrome
        )
        return reading, None if reading else "unreadable"

    def _record_cost(
        self, *, user: User, result: Any, band: str, has_image: bool
    ) -> None:
        """One priced pilot row per model call, including the call that failed.

        A failed paid call still cost the request; a row with zero cost and a
        ``failed`` flag keeps it visible instead of letting it vanish. Nothing
        about the document's content is written here — tokens, model and provider
        only. Telemetry must never cost a learner their reading, so every failure
        is swallowed.
        """

        try:
            PilotEventService(self.db).record(
                INTAKE_EVENT_TYPE,
                user_id=user.id,
                entity_type="learner_artefact",
                entity_id=None,
                payload={
                    "prompt_version": INTAKE_PROMPT_VERSION,
                    "provider": getattr(result, "provider", None),
                    "model": getattr(result, "model", None),
                    "prompt_tokens": int(getattr(result, "prompt_tokens", 0) or 0),
                    "completion_tokens": int(getattr(result, "completion_tokens", 0) or 0),
                    "total_tokens": int(getattr(result, "total_tokens", 0) or 0),
                    "band": band,
                    "modality": "image" if has_image else "text",
                    "failed": result is None,
                },
                cost_usd=float(getattr(result, "cost", 0.0) or 0.0),
            )
        except Exception:  # pragma: no cover - defensive
            logger.warning("Intake cost row could not be written")

    # -- the vocabulary queue ---------------------------------------------

    def _queue_unknown_words(
        self, *, user: User, artefact: LearnerArtefact, glossed: list[dict[str, Any]]
    ) -> list[int]:
        """Put the artefact's unknown words into the learner's own SRS queue.

        They enter as ``new`` and due now — a word off today's letter is worth
        meeting today — and are stamped with a provenance so that WP-29 can tell
        a word the learner *chose* from a word the generator let slip.

        A word already in the learner's queue keeps its schedule: an artefact
        must never reset a card the learner has been building for weeks. It does
        gain the provenance, because the learner has now met it in their own life
        and that is exactly what makes it a target.
        """

        now = datetime.now(UTC)
        language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
        native = normalize_language(getattr(user, "native_language", None))
        queued: list[int] = []
        for item in glossed:
            surface = str(item.get("word") or "").strip()
            key = normalize_word(item.get("lemma") or surface)
            if not surface or not key:
                continue
            word = self._get_or_create_word(
                language=language,
                surface=str(item.get("lemma") or surface),
                key=key,
                gloss=str(item.get("gloss") or ""),
                gloss_language=native,
                example=str(item.get("example_fr") or ""),
            )
            progress = self.db.scalars(
                select(UserVocabularyProgress).where(
                    UserVocabularyProgress.user_id == user.id,
                    UserVocabularyProgress.word_id == word.id,
                )
            ).first()
            if progress is None:
                progress = UserVocabularyProgress(
                    user_id=user.id,
                    word_id=word.id,
                    state="new",
                    phase="new",
                    scheduler="fsrs",
                    due_at=now,
                    next_review_date=now,
                    due_date=now.date(),
                )
            progress.provenance = LEARNER_SOURCED_PROVENANCE
            progress.provenance_ref = str(artefact.id)
            self.db.add(progress)
            queued.append(int(word.id))
        return queued

    def _get_or_create_word(
        self,
        *,
        language: str,
        surface: str,
        key: str,
        gloss: str,
        gloss_language: str,
        example: str,
    ) -> VocabularyWord:
        existing = self.db.scalars(
            select(VocabularyWord)
            .where(VocabularyWord.language == language, VocabularyWord.normalized_word == key)
            .limit(1)
        ).first()
        if existing is not None:
            return existing
        column = {"de": "german_translation", "fr": "french_translation"}.get(
            gloss_language, "english_translation"
        )
        word = VocabularyWord(
            language=language,
            word=surface,
            normalized_word=key,
            definition=gloss or None,
            example_sentence=example or None,
            usage_notes="Relevé dans un document apporté par l'apprenant.",
            difficulty_level=2,
            topic_tags=["learner_artefact", "bring_your_own"],
            **{column: gloss or None},
        )
        self.db.add(word)
        self.db.flush([word])
        return word

    # -- deletion ---------------------------------------------------------

    def delete(self, user: User, artefact_id: UUID) -> bool:
        """Remove the artefact **and** the Courrier task derived from it.

        The derived mission quotes the learner's own document in its brief and in
        its messenger payload, so deleting only the artefact would leave the
        document readable in Le Courrier. The vocabulary the learner has since
        been studying is deliberately *kept*: the words are theirs now, and the
        provenance reference is cleared so nothing points back at a document that
        no longer exists.
        """

        artefact = self.get(user, artefact_id)
        if artefact is None:
            return False

        if artefact.mission_id:
            mission = self.db.get(RealWorldMission, artefact.mission_id)
            if mission is not None and mission.user_id == user.id:
                self.db.delete(mission)

        for progress in self.db.scalars(
            select(UserVocabularyProgress).where(
                UserVocabularyProgress.user_id == user.id,
                UserVocabularyProgress.provenance_ref == str(artefact.id),
            )
        ):
            progress.provenance_ref = None
            self.db.add(progress)

        self.db.delete(artefact)
        self.db.commit()
        return True


def intake_digest_line(db: Session, *, since: datetime, until: datetime) -> str:
    """One digest line: how many documents were brought in, and how many were read.

    Reads counts and money, never content. An empty window says nothing happened
    rather than reporting 0 % of nothing.
    """

    rows = list(
        db.scalars(
            select(LearnerArtefact).where(
                LearnerArtefact.created_at >= since, LearnerArtefact.created_at < until
            )
        )
    )
    if not rows:
        return "Bring your own French: nothing to report."
    read = sum(1 for row in rows if row.status == "read")
    spend = float(
        sum(
            float(event.cost_usd or 0.0)
            for event in db.scalars(
                select(PilotEvent).where(
                    PilotEvent.event_type == INTAKE_EVENT_TYPE,
                    PilotEvent.occurred_at >= since,
                    PilotEvent.occurred_at < until,
                )
            )
        )
    )
    share = round(100 * read / len(rows))
    return (
        f"Bring your own French: {read}/{len(rows)} documents read ({share} %), "
        f"US${spend:.2f}."
    )


__all__ = [
    "ALLOWED_IMAGE_TYPES",
    "INTAKE_EVENT_TYPE",
    "INTAKE_PROMPT_VERSION",
    "INTAKE_VERSION",
    "MAX_KEY_FACTS",
    "MAX_UNKNOWN_WORDS",
    "SOURCE_TEXT_MAX_CHARS",
    "SOURCE_TEXT_MIN_CHARS",
    "SUMMARY_WORD_LIMITS",
    "CapState",
    "IntakeRefused",
    "IntakeService",
    "Reading",
    "bound_summary",
    "cap_state",
    "intake_digest_line",
    "learner_sourced_targets",
    "normalize_source_text",
    "normalize_word",
    "parse_reading",
    "public_view",
    "read_prompt",
    "resolve_glosses",
    "summary_word_limit",
    "text_messages",
    "vision_messages",
]
