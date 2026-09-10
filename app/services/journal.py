"""WP-30 — «Le journal de bord»: the learner writes the recap.

Every recap in the app so far was written *for* the learner. The evidence says
that is the weakest of the three retrieval formats: free recall beats cued
recall beats recognition, and retrieval practice buys nothing at all over plain
restudy **unless corrective feedback follows**. So this package does both halves
or it does neither — the learner writes 2–4 sentences from memory about
yesterday's scene, with the scene text hidden, and what they wrote is corrected.

Five properties, each with a test:

* **The scene is not on screen while they write.** The offer carries a *cue*
  (who, where, which evening) and no authored line. :class:`JournalCue` has no
  field that could hold one, and the reveal is a separate object the router only
  attaches once ``entry_text`` exists.
* **Two scores, never one.** Content recall — did they remember the commitment
  and how the evening ended — is measured against the scene's stored facts by
  :func:`score_content_recall`, deterministically, and lives in its own column.
  The French is graded by the Séance corrector. Merging them would let good
  grammar hide a forgotten promise, which is precisely the thing worth knowing.
* **One correction in the foreground.** Through the journey's own policy
  (:func:`app.services.journey_learning.select_foreground_correction`), so the
  journal cannot be a second, louder corrector. The full list is returned as
  well and the client shows it on demand; a stored "strict" preference is never
  silently downgraded to nothing.
* **Failure is a state, not a verdict.** No provider, no concept to check
  against, or a provider that does not answer ⇒ ``assessment_status =
  "unavailable"``. The learner's text is kept, no erratum is invented, no
  vocabulary is credited, and the screen says so in French.
* **The story is read, never written.** Scene facts come from the journey's own
  public snapshot fields and from :func:`app.services.living_story.story_context`,
  which is a pure read. Nothing here touches serial state, ``private_task``, or
  the living-story thread.

Spacing follows the same evidence: +1 day for the entry, +7 days for a one-line
follow-up whose answer is the ``used_again_later`` signal — the only number that
says a memory survived a week rather than a sitting.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.grammar import GrammarConcept
from app.db.models.journal import JournalEntry
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier import AtelierCorrectionService
from app.services.atelier_correction_cost import bound_learner_answer
from app.services.daily_journey import local_date_for
from app.services.error_memory import ErrorMemoryService
from app.services.glosses import normalize_language
from app.services.journey_contracts import Correction, JourneyStatus, StepKind
from app.services.journey_learning import (
    build_correction,
    fold_for_comparison,
    select_foreground_correction,
)
from app.services.pilot_events import PilotEventService
from app.services.progress import vocabulary_due_filter
from app.services.vocabulary_credit import VocabularyCreditService

JOURNAL_VERSION = "journal-v1"
RECALL_VERSION = "journal-recall-v1"

#: The pilot-ledger event types. ``scripts/pilot_digest.py`` reads them by name
#: exactly as it reads ``atelier_correction`` and ``placement_grading``.
JOURNAL_EVENT_TYPE = "journal_correction"
JOURNAL_FOLLOWUP_EVENT_TYPE = "journal_followup"

#: The entry is offered the day *after* the scene: the interval is the point.
RECALL_OFFSET_DAYS = 1
#: And the same scene is asked about again a week later, in one line.
FOLLOWUP_OFFSET_DAYS = 7

#: How far back the offer will reach for an un-journalled scene. A learner who
#: comes back after a fortnight is asked about a scene they can plausibly still
#: recall, not about the last one that happens to have no entry.
RECALL_WINDOW_DAYS = 14
#: And how long the +7 follow-up stays askable before it stops being a week.
FOLLOWUP_WINDOW_DAYS = 14

#: Ceiling on the learner text sent to the paid checker, shared with the Séance
#: correction so one pasted document cannot size a paid request.
ENTRY_MAX_CHARS = 1200
#: The follow-up is one line by construction.
FOLLOWUP_MAX_CHARS = 400

#: Below this the entry is not a recap. Two sentences is the brief's floor and
#: this is the word count that reliably carries two.
MIN_ENTRY_WORDS = 8

#: A fact with more cues than this needs two of them to count as recalled; a
#: short fact needs one. Otherwise a single common noun would "prove" a memory.
CUE_THRESHOLD_WIDTH = 2

#: Function words and the auxiliaries carry no evidence of recall. Kept
#: deliberately small: every word removed here is a word a learner cannot get
#: credit for remembering, so the list holds only what any French sentence
#: contains regardless of what happened in the scene.
_STOPWORDS = frozenset(
    """
    a ai as ait aux avec avais avait avez avions avons avoir ayant ce ces cet cette
    chez comme dans de des du elle elles en encore est etaient etais etait etant ete
    etes etre eux fait faire fais font ici il ils je la le les leur leurs lui ma mais
    me mes moi mon ne nos notre nous ont on ou par pas peu peut pour qu que qui quoi
    sa se ses soit son sommes sont suis sur ta te tes toi ton tout tous toute toutes
    tres tu un une vais vas vos votre vous y bien alors apres aussi
    """.split()
)

#: A cue and a written word are the same word when they fold identically, or
#: when one is a prefix of the other by at most this many characters. French
#: inflection is mostly suffixal — *rapporter / rapporté / rapportés* — and a
#: recall check that insisted on the infinitive would fail every learner who
#: wrote the sentence correctly.
CUE_SUFFIX_TOLERANCE = 3
#: Below this length a prefix match is noise (*port* / *portefeuille*).
CUE_STEM_FLOOR = 4


def cue_matches(cue: str, token: str) -> bool:
    """Whether one written token evidences one cue."""
    if not cue or not token:
        return False
    if cue == token:
        return True
    shorter, longer = (cue, token) if len(cue) <= len(token) else (token, cue)
    if len(shorter) < CUE_STEM_FLOOR:
        return False
    if len(longer) - len(shorter) > CUE_SUFFIX_TOLERANCE:
        return False
    return longer.startswith(shorter)


# ---------------------------------------------------------------------------
# Text handling
# ---------------------------------------------------------------------------


def _tokens(value: str | None) -> list[str]:
    """Folded content tokens. Accents, case and iOS smart quotes are gone."""
    return [token for token in fold_for_comparison(value).split() if token]


def content_cues(value: str | None, *, given: set[str] | None = None) -> list[str]:
    """The tokens of ``value`` that could evidence recall.

    ``given`` is what the learner was *told* — the character's name and the
    place. Those are on the prompt, so writing them back proves nothing and they
    are removed rather than counted.
    """
    skip = set(given or ())
    seen: list[str] = []
    for token in _tokens(value):
        if len(token) < 3 or token in _STOPWORDS or token in skip or token in seen:
            continue
        seen.append(token)
    return seen


def word_forms(word: VocabularyWord) -> set[str]:
    """Folded surface forms that count as "the learner used this word"."""
    forms = {
        fold_for_comparison(candidate)
        for candidate in (word.word, word.normalized_word, word.french_translation)
        if candidate
    }
    return {form for form in forms if form}


def sentence_count(text: str) -> int:
    parts = [part for part in re.split(r"[.!?…]+", str(text or "")) if part.strip()]
    return len(parts)


# ---------------------------------------------------------------------------
# Scene facts — read from public paths, snapshotted at offer time
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SceneFact:
    """One thing the scene established that a recap could remember."""

    key: str
    kind: str
    text_fr: str
    cues: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "text_fr": self.text_fr,
            "cues": list(self.cues),
        }

    @property
    def needed_cues(self) -> int:
        return 2 if len(self.cues) > CUE_THRESHOLD_WIDTH else 1


def scene_facts_for(
    journey: DailyJourney, *, story_context: dict[str, Any] | None = None
) -> list[SceneFact]:
    """What this scene established, from public read paths only.

    Three sources, in the order they matter to a recap: the commitments the
    story remembers from this episode, how the evening actually ended, and the
    scene's own objective. ``private_task`` is never read — the rubric and the
    accepted answers are evaluator material and a journal that scored against
    them would be grading the learner's memory of a hidden document.
    """
    scenario = dict(journey.scenario_snapshot or {})
    recap = dict(journey.recap_snapshot or {})
    given = set(
        content_cues(
            " ".join(
                str(scenario.get(key) or "")
                for key in ("character_name", "location_name")
            )
        )
    )

    facts: list[SceneFact] = []

    outcome = recap.get("story_outcome") or {}
    callback = str(outcome.get("callback_fr") or "").strip()
    if callback:
        facts.append(
            SceneFact(
                key="outcome",
                kind="outcome",
                text_fr=callback,
                cues=tuple(content_cues(callback, given=given)),
            )
        )

    episode_id = str(journey.serial_episode_id or "") or None
    for raw in (story_context or {}).get("commitments") or []:
        if not isinstance(raw, dict):
            continue
        summary = str(raw.get("summary_fr") or raw.get("summary") or "").strip()
        if not summary:
            continue
        # Only this scene's commitments. A promise made three evenings ago is
        # not what "did you remember what happened yesterday" is asking about.
        source = str(raw.get("episode_id") or raw.get("source_episode_id") or "")
        if episode_id and source and source != episode_id:
            continue
        cues = tuple(content_cues(summary, given=given))
        if not cues:
            continue
        facts.append(
            SceneFact(
                key=f"commitment:{raw.get('id') or len(facts)}",
                kind="commitment",
                text_fr=summary,
                cues=cues,
            )
        )

    objective = str(scenario.get("objective_native") or "").strip()
    if objective and not facts:
        # Last resort so a scene always has something to be recalled against.
        # Never *in addition* to real story facts: the objective is a paraphrase
        # of them and would double-count.
        cues = tuple(content_cues(objective, given=given))
        if cues:
            facts.append(
                SceneFact(key="objective", kind="objective", text_fr=objective, cues=cues)
            )

    return facts


def scene_cue(journey: DailyJourney, *, today: date) -> dict[str, Any]:
    """What the learner is shown *before* writing. No authored scene text.

    Deliberately three keys wide: who, where, and how long ago. The title, the
    setup and the character's opening line are all scene text, and a free-recall
    prompt that shows them is a copying exercise.
    """
    scenario = dict(journey.scenario_snapshot or {})
    scene_day = journey.local_date
    return {
        "character_name": scenario.get("character_name") or None,
        "location_name": scenario.get("location_name") or None,
        "scene_date": scene_day.isoformat() if scene_day else None,
        "days_ago": (today - scene_day).days if scene_day else None,
    }


def scene_reveal(journey: DailyJourney) -> dict[str, Any]:
    """The scene as it was, shown only after the learner has written."""
    scenario = dict(journey.scenario_snapshot or {})
    recap = dict(journey.recap_snapshot or {})
    setup_fr = ""
    character_line_fr = ""
    for step in sorted(journey.steps or [], key=lambda item: item.ordinal):
        if StepKind(step.kind) is not StepKind.SCENE:
            continue
        prompt = dict(step.public_prompt or {})
        setup_fr = str(prompt.get("setup_fr") or "")
        character_line_fr = str(prompt.get("character_line_fr") or "")
        break
    return {
        "title_fr": scenario.get("title_fr") or None,
        "setup_fr": setup_fr or None,
        "character_line_fr": character_line_fr or None,
        "callback_fr": (recap.get("story_outcome") or {}).get("callback_fr") or None,
    }


# ---------------------------------------------------------------------------
# Content recall — the half that is not grammar
# ---------------------------------------------------------------------------


def score_content_recall(text: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
    """How much of the scene the writing actually remembered.

    Deterministic and cheap on purpose: this is a *content* measure, and paying
    a model to decide whether "le livre" refers to the promised book would make
    the one honest number in the package depend on a provider being up.

    A scene with no stored facts scores ``None``, not zero. "We had nothing to
    check against" and "they remembered nothing" are different sentences.
    """
    written = set(_tokens(text))
    matched: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []
    for raw in facts or []:
        cues = [str(cue) for cue in (raw.get("cues") or []) if cue]
        if not cues:
            continue
        needed = 2 if len(cues) > CUE_THRESHOLD_WIDTH else 1
        hits = [
            cue for cue in cues if any(cue_matches(cue, token) for token in written)
        ]
        entry = {
            "key": raw.get("key"),
            "kind": raw.get("kind"),
            "text_fr": raw.get("text_fr"),
            "cues_hit": hits,
        }
        (matched if len(hits) >= needed else missed).append(entry)

    total = len(matched) + len(missed)
    if total == 0:
        return {
            "version": RECALL_VERSION,
            "status": "no_facts",
            "score": None,
            "matched": [],
            "missed": [],
            "facts_total": 0,
        }
    return {
        "version": RECALL_VERSION,
        "status": "scored",
        "score": round(len(matched) / total, 3),
        "matched": matched,
        "missed": missed,
        "facts_total": total,
    }


# ---------------------------------------------------------------------------
# The character's one line
# ---------------------------------------------------------------------------


def character_reaction(*, character_name: str | None, recall: dict[str, Any]) -> str | None:
    """One line, about the *content*, composed from public story context.

    Authored rather than generated: a second paid call for one sentence would
    double the package's per-entry cost and add a second failure mode to a line
    that has exactly three things to say. What it says is real — it names the
    fact the learner remembered, or the one they did not — and it never praises
    a recap that recalled nothing.

    ``None`` when there is nothing honest to say (no facts, or no name to say it
    with). An empty compliment is worse than silence.
    """
    name = str(character_name or "").strip()
    if not name or recall.get("status") != "scored":
        return None
    matched = list(recall.get("matched") or [])
    missed = list(recall.get("missed") or [])

    def short(fact: dict[str, Any]) -> str:
        text = str(fact.get("text_fr") or "").strip().rstrip(".")
        return text[:90]

    commitments = [item for item in matched if item.get("kind") == "commitment"]
    if commitments:
        return f"{name} hoche la tête. « Vous n’avez pas oublié : {short(commitments[0])}. »"
    if matched:
        return f"{name} sourit. « Oui, c’est bien comme ça que ça s’est passé. »"
    if missed:
        return (
            f"{name} vous regarde. « Il manque quelque chose : "
            f"{short(missed[0])}. »"
        )
    return None


def followup_prompt(character_name: str | None) -> str:
    """The +7-day line. One question, no scene text, no options."""
    name = str(character_name or "").strip()
    if name:
        return f"Et la semaine dernière, avec {name} ?"
    return "Et la semaine dernière, que s’est-il passé ?"


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------


def record_journal_cost(
    db: Session,
    result: Any,
    *,
    user_id: UUID | None,
    entry_id: UUID | None,
    answer_truncated: bool = False,
) -> None:
    """One priced pilot-ledger row per real journal correction call.

    Same policy as :func:`app.services.atelier_correction_cost.record_correction_cost`
    and its placement sibling: the provider's own usage metadata, written
    through the caller's transaction, never committed here, and every telemetry
    failure swallowed — a learner must never lose their entry to a bookkeeping
    error. Its own event type because the digest's cost-per-surface line cannot
    tell a journal entry from a Séance check otherwise.
    """
    try:
        PilotEventService(db).record(
            JOURNAL_EVENT_TYPE,
            user_id=user_id,
            entity_type="journal_entry",
            entity_id=entry_id,
            payload={
                "provider": getattr(result, "provider", None),
                "model": getattr(result, "model", None),
                "prompt_tokens": int(getattr(result, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(result, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(result, "total_tokens", 0) or 0),
                "answer_truncated": bool(answer_truncated),
            },
            cost_usd=float(getattr(result, "cost", 0.0) or 0.0),
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Journal correction cost row could not be written")


class _JournalCorrector(AtelierCorrectionService):
    """The Séance corrector, billed to the journal's own ledger line.

    One overridden hook and nothing else: the correction itself — the prompt,
    the schema, the no-op erratum filter, the ``fallback_used`` honesty rule —
    is the Séance's, so the journal cannot drift into being a second corrector
    with its own opinions about French.
    """

    def __init__(
        self,
        db: Session,
        *,
        user_id: UUID | None,
        entry_id: UUID | None,
        llm_service: Any = None,
    ) -> None:
        super().__init__(db, llm_service=llm_service)
        self._journal_user_id = user_id
        self._journal_entry_id = entry_id
        #: How many real paid calls this instance made. Read by the tests that
        #: pin "one priced event per correction call".
        self.paid_calls = 0

    def _record_correction_cost(self, result: Any) -> None:  # type: ignore[override]
        self.paid_calls += 1
        record_journal_cost(
            self.db,
            result,
            user_id=self._journal_user_id,
            entry_id=self._journal_entry_id,
            answer_truncated=bool(getattr(self, "_answer_truncated", False)),
        )


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


class JournalService:
    """Offer, write, correct and follow up on one learner's journal."""

    def __init__(self, db: Session, *, llm_service: Any = None) -> None:
        self.db = db
        self._llm_service = llm_service

    # -- schedule ---------------------------------------------------------

    def today_for(self, user: User, *, now: datetime | None = None) -> date:
        journey = (
            self.db.query(DailyJourney)
            .filter(DailyJourney.user_id == user.id)
            .order_by(DailyJourney.local_date.desc())
            .first()
        )
        timezone = str(getattr(journey, "timezone", None) or "UTC")
        return local_date_for(timezone, now=now)

    def recallable_journeys(self, user: User, *, today: date) -> list[DailyJourney]:
        """Finished scenes old enough to be recalled and young enough to matter."""
        newest = today - timedelta(days=RECALL_OFFSET_DAYS)
        oldest = today - timedelta(days=RECALL_WINDOW_DAYS)
        return (
            self.db.query(DailyJourney)
            .filter(
                DailyJourney.user_id == user.id,
                DailyJourney.status.in_(
                    [str(JourneyStatus.COMPLETED), str(JourneyStatus.ENDED_EARLY)]
                ),
                DailyJourney.local_date <= newest,
                DailyJourney.local_date >= oldest,
            )
            .order_by(DailyJourney.local_date.desc())
            .all()
        )

    def entry_for_journey(self, user: User, journey_id: UUID) -> JournalEntry | None:
        return (
            self.db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user.id,
                JournalEntry.journey_id == journey_id,
            )
            .first()
        )

    def open_entry(self, user: User) -> JournalEntry | None:
        """The offered-but-unwritten entry, if there is one."""
        return (
            self.db.query(JournalEntry)
            .filter(JournalEntry.user_id == user.id, JournalEntry.status == "offered")
            .order_by(JournalEntry.offered_on.desc())
            .first()
        )

    def offer(self, user: User, *, now: datetime | None = None) -> JournalEntry | None:
        """The entry to write today, creating it on first ask. Idempotent.

        Returns ``None`` when nothing is due: no finished scene old enough, or
        every candidate already has an entry. Nothing is invented to fill the
        tab — an empty journal is a true statement about a learner's week.
        """
        existing = self.open_entry(user)
        if existing is not None:
            return existing
        today = self.today_for(user, now=now)
        for journey in self.recallable_journeys(user, today=today):
            if self.entry_for_journey(user, journey.id) is not None:
                continue
            return self._create(user, journey, today=today)
        return None

    def _create(self, user: User, journey: DailyJourney, *, today: date) -> JournalEntry:
        from app.services.living_story import story_context

        try:
            context = story_context(self.db, user)
        except Exception:  # pragma: no cover - the story is optional context
            logger.warning("Journal could not read story context; facts fall back")
            context = {}
        facts = scene_facts_for(journey, story_context=context)
        scene_day = journey.local_date
        entry = JournalEntry(
            user_id=user.id,
            journey_id=journey.id,
            status="offered",
            version=JOURNAL_VERSION,
            scene_date=scene_day,
            offered_on=scene_day + timedelta(days=RECALL_OFFSET_DAYS),
            followup_due_on=scene_day + timedelta(days=FOLLOWUP_OFFSET_DAYS),
            cue=scene_cue(journey, today=today),
            scene_facts=[fact.as_dict() for fact in facts],
            scene_reveal=scene_reveal(journey),
            correction={},
            content_recall={},
            vocabulary_credit={},
            errata_ids=[],
            followup_recall={},
            followup_prompt_fr=followup_prompt(
                (journey.scenario_snapshot or {}).get("character_name")
            ),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def followup_due(self, user: User, *, now: datetime | None = None) -> JournalEntry | None:
        """The written entry whose week is up and whose line is unanswered."""
        today = self.today_for(user, now=now)
        return (
            self.db.query(JournalEntry)
            .filter(
                JournalEntry.user_id == user.id,
                JournalEntry.status.in_(["written", "unavailable"]),
                JournalEntry.followup_answered_at.is_(None),
                JournalEntry.followup_due_on <= today,
                JournalEntry.followup_due_on >= today - timedelta(days=FOLLOWUP_WINDOW_DAYS),
            )
            .order_by(JournalEntry.followup_due_on.asc())
            .first()
        )

    # -- writing ----------------------------------------------------------

    def skip(self, entry: JournalEntry) -> JournalEntry:
        """The learner declined this scene. Recorded, so it is asked once."""
        if entry.status == "offered":
            entry.status = "skipped"
            self.db.add(entry)
            self.db.commit()
            self.db.refresh(entry)
        return entry

    def write(self, user: User, entry: JournalEntry, *, text: str) -> JournalEntry:
        """Store the recap, correct it, score its content, credit what it used.

        Idempotent: an entry that already carries text is returned untouched, so
        a retried request never buys a second paid correction.
        """
        if entry.status != "offered":
            return entry
        bounded, truncated = bound_learner_answer({"text": text}, max_chars=ENTRY_MAX_CHARS)
        written = str(bounded.get("text") or "").strip()
        if not written:
            return entry

        # Written first, and never rolled back by a grading failure.
        entry.entry_text = written
        entry.written_at = _utcnow()

        correction, corrector = self._correct(user, entry, written, truncated=truncated)
        checked = correction.get("assessment_status") == "checked"
        entry.assessment_status = "checked" if checked else "unavailable"
        entry.status = "written" if checked else "unavailable"

        recall = score_content_recall(written, list(entry.scene_facts or []))
        entry.content_recall = recall
        entry.recall_score = recall.get("score")
        entry.reaction_fr = character_reaction(
            character_name=(entry.cue or {}).get("character_name"), recall=recall
        )

        if checked:
            entry.errata_ids = self._record_errata(user, entry, correction)
            entry.vocabulary_credit = self._credit_vocabulary(user, entry, written, correction)
        else:
            # No verdict, so no erratum and no credit. An uncertified sentence
            # must not move a schedule in either direction.
            entry.errata_ids = []
            entry.vocabulary_credit = {"status": "skipped", "reason": "assessment_unavailable"}

        entry.correction = {
            **correction,
            "paid_calls": int(getattr(corrector, "paid_calls", 0)),
        }
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def answer_followup(self, user: User, entry: JournalEntry, *, text: str) -> JournalEntry:
        """The +7-day line. Its answer is the ``used_again_later`` signal.

        Scored against the *same* stored facts as the entry, so the two numbers
        are comparable: whatever the learner still names a week later is what
        survived a night and then six more. Deterministic — no paid call.
        """
        if entry.followup_answered_at is not None:
            return entry
        bounded, _truncated = bound_learner_answer({"text": text}, max_chars=FOLLOWUP_MAX_CHARS)
        written = str(bounded.get("text") or "").strip()
        if not written:
            return entry

        recall = score_content_recall(written, list(entry.scene_facts or []))
        signal = (
            "used_again_later"
            if recall.get("status") == "scored" and (recall.get("score") or 0) > 0
            else "not_recalled"
        )
        entry.followup_text = written
        entry.followup_recall = recall
        entry.followup_signal = signal
        entry.followup_answered_at = _utcnow()
        try:
            PilotEventService(self.db).record(
                JOURNAL_FOLLOWUP_EVENT_TYPE,
                user_id=user.id,
                entity_type="journal_entry",
                entity_id=entry.id,
                payload={
                    "signal": signal,
                    "days_later": (
                        (entry.followup_due_on - entry.scene_date).days
                        if entry.followup_due_on and entry.scene_date
                        else None
                    ),
                    "facts_total": int(recall.get("facts_total") or 0),
                    "facts_matched": len(recall.get("matched") or []),
                    "version": RECALL_VERSION,
                },
            )
        except Exception:  # pragma: no cover - telemetry never costs an answer
            logger.warning("Journal follow-up event could not be written")
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    # -- correction -------------------------------------------------------

    def concepts_for(self, user: User, entry: JournalEntry) -> GrammarConcept | None:
        """A grammar concept for the checker to anchor on, or ``None``.

        The Séance corrector's paid path needs a concept; without one it returns
        its deterministic fallback and the entry lands honestly on
        ``unavailable`` rather than on a fabricated pass. First choice is what
        the recalled scene itself taught, because that is what the recap is most
        likely to exercise.
        """
        journey = (
            self.db.get(DailyJourney, entry.journey_id) if entry.journey_id else None
        )
        for step in sorted(journey.steps or [], key=lambda item: item.ordinal) if journey else []:
            if str(step.target_kind or "") != "grammar" or not step.target_id:
                continue
            try:
                concept = self.db.get(GrammarConcept, int(step.target_id))
            except (TypeError, ValueError):
                concept = None
            if concept is not None:
                return concept
        return None

    def _correct(
        self, user: User, entry: JournalEntry, text: str, *, truncated: bool
    ) -> tuple[dict[str, Any], Any]:
        concept = self.concepts_for(user, entry)
        corrector = _JournalCorrector(
            self.db,
            user_id=user.id,
            entry_id=entry.id,
            llm_service=self._llm_service,
        )
        corrector.explanation_language = normalize_language(user.native_language)
        corrector._answer_truncated = bool(truncated)
        prompt_payload = {
            "round": "produce",
            "mode": "journal",
            "prompt": (
                "Le journal de bord : la personne raconte de mémoire, en deux à quatre "
                "phrases, ce qui s’est passé dans la scène de la veille. Corrigez le "
                "français ; ne jugez pas ce dont elle se souvient."
            ),
            "items": [
                {
                    "id": f"journal:{entry.id}",
                    "type": "free_recall",
                    "instruction": "Racontez, de mémoire, ce qui s’est passé.",
                }
            ],
        }
        try:
            correction = corrector.correct(
                concept=concept,
                round_name="produce",
                mode="journal",
                exercise_id=f"journal:{entry.id}",
                prompt_payload=prompt_payload,
                answer_payload={"text": text},
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Journal correction failed: {}", exc)
            return {"assessment_status": "unavailable", "errata": []}, corrector
        return self._shape_correction(user, correction, text, truncated=truncated), corrector

    def _shape_correction(
        self, user: User, correction: dict[str, Any], text: str, *, truncated: bool
    ) -> dict[str, Any]:
        """The wire shape: one foreground correction and the full list behind it."""
        errata = [item for item in (correction.get("errata") or []) if isinstance(item, dict)]
        keep = [
            item
            for item in errata
            if str(item.get("task_error_type") or "")
            not in {"task_compliance", "length_compliance"}
        ]
        candidates: list[Correction] = []
        by_span: dict[str, dict[str, Any]] = {}
        for item in keep:
            built = build_correction(
                learner_text=item.get("learner_text"),
                corrected_fr=item.get("corrected_target"),
                note_native=item.get("why_wrong"),
            )
            if built is None:
                continue
            candidates.append(built)
            by_span.setdefault(built.span_fr, item)
        foreground, _background = select_foreground_correction(
            user=user, learner_text=text, candidates=candidates
        )

        def view(item: dict[str, Any]) -> dict[str, Any]:
            return {
                "label": item.get("display_label") or "Correction",
                "span_fr": item.get("learner_text") or "",
                "corrected_fr": item.get("corrected_target") or "",
                "note_native": item.get("why_wrong") or "",
                "repair_hint": item.get("repair_hint") or "",
                "task_error_type": item.get("task_error_type") or "grammar_target",
            }

        foreground_view = None
        if foreground is not None:
            source = by_span.get(foreground.span_fr, {})
            foreground_view = {
                **view(source),
                "span_fr": foreground.span_fr,
                "corrected_fr": foreground.corrected_fr,
                "note_native": foreground.note_native or source.get("why_wrong") or "",
            }
        return {
            "version": JOURNAL_VERSION,
            "assessment_status": str(correction.get("assessment_status") or "unavailable"),
            "assessment_truncated": bool(truncated or correction.get("assessment_truncated")),
            "verdict": correction.get("verdict"),
            "score_0_4": correction.get("score_0_4"),
            "corrected_answer": correction.get("corrected_answer") or "",
            "explanation_language": correction.get("explanation_language"),
            "model": (correction.get("correction_debug") or {}).get("model"),
            "foreground": foreground_view,
            "errata": [view(item) for item in keep],
        }

    # -- what the correction feeds ---------------------------------------

    def _record_errata(
        self, user: User, entry: JournalEntry, correction: dict[str, Any]
    ) -> list[str]:
        """Every grammar error in the recap becomes a WP-24 erratum.

        Through :meth:`ErrorMemoryService.record_erratum`, so the entry's
        mistakes enter the same ``open → repairing → mastered`` lifecycle as the
        Séance's and reach tomorrow's scene through the errata planner. The
        journal owns no second mistake store.
        """
        memory = ErrorMemoryService(self.db)
        ids: list[str] = []
        for item in correction.get("errata") or []:
            span = str(item.get("span_fr") or "").strip()
            corrected = str(item.get("corrected_fr") or "").strip()
            if not span or not corrected:
                continue
            try:
                recorded = memory.record_erratum(
                    user=user,
                    erratum={
                        "display_label": item.get("label") or "Correction",
                        "learner_text": span,
                        "corrected_target": corrected,
                        "why_wrong": item.get("note_native") or "",
                        "repair_hint": item.get("repair_hint") or "",
                        "severity": 2,
                        "recurring": True,
                        "task_error_type": item.get("task_error_type") or "grammar_target",
                    },
                    source_type="journal",
                    source_payload={
                        "surface": "journal",
                        "journal_entry_id": str(entry.id),
                        "journey_id": str(entry.journey_id) if entry.journey_id else None,
                        "version": JOURNAL_VERSION,
                    },
                )
            except Exception:  # pragma: no cover - defensive
                logger.warning("Journal erratum could not be recorded")
                continue
            if recorded and recorded.get("id"):
                ids.append(str(recorded["id"]))
        return ids

    def due_vocabulary(self, user: User, *, limit: int = 60) -> list[VocabularyWord]:
        """The learner's due words, through the shared SRS read path."""
        return (
            self.db.query(VocabularyWord)
            .join(
                UserVocabularyProgress,
                UserVocabularyProgress.word_id == VocabularyWord.id,
            )
            .filter(
                UserVocabularyProgress.user_id == user.id,
                vocabulary_due_filter(),
            )
            .limit(limit)
            .all()
        )

    def _credit_vocabulary(
        self,
        user: User,
        entry: JournalEntry,
        text: str,
        correction: dict[str, Any],
    ) -> dict[str, Any]:
        """Due words the recap used correctly earn ordinary SRS credit.

        Through :class:`VocabularyCreditService`, at the unassisted rate — free
        recall with no text on screen is the strongest production evidence the
        app collects. A word the correction flagged is not credited: it was used
        and used wrongly, and the erratum already says so.
        """
        written = set(_tokens(text))
        flagged = set()
        for item in correction.get("errata") or []:
            flagged.update(_tokens(item.get("span_fr")))

        service = VocabularyCreditService(self.db)
        credited: list[str] = []
        skipped: list[str] = []
        for word in self.due_vocabulary(user):
            forms = word_forms(word)
            used = any(
                all(part in written for part in form.split()) for form in forms if form
            )
            if not used:
                continue
            if any(part in flagged for form in forms for part in form.split()):
                skipped.append(word.word)
                continue
            try:
                service.apply(
                    user=user,
                    word=word,
                    event_type="produced_correct",
                    source_type="journal",
                    learner_text=text,
                    context=str((entry.cue or {}).get("character_name") or ""),
                    source_payload={
                        "surface": "journal",
                        "journal_entry_id": str(entry.id),
                        "version": JOURNAL_VERSION,
                    },
                )
            except Exception:  # pragma: no cover - defensive
                logger.warning("Journal vocabulary credit failed for word {}", word.id)
                continue
            credited.append(word.word)
        return {
            "status": "applied",
            "credited": credited,
            "skipped_flagged": skipped,
            "event_type": "produced_correct",
        }


__all__ = [
    "CUE_STEM_FLOOR",
    "CUE_SUFFIX_TOLERANCE",
    "CUE_THRESHOLD_WIDTH",
    "ENTRY_MAX_CHARS",
    "FOLLOWUP_MAX_CHARS",
    "FOLLOWUP_OFFSET_DAYS",
    "FOLLOWUP_WINDOW_DAYS",
    "JOURNAL_EVENT_TYPE",
    "JOURNAL_FOLLOWUP_EVENT_TYPE",
    "JOURNAL_VERSION",
    "MIN_ENTRY_WORDS",
    "RECALL_OFFSET_DAYS",
    "RECALL_VERSION",
    "RECALL_WINDOW_DAYS",
    "JournalService",
    "SceneFact",
    "character_reaction",
    "content_cues",
    "cue_matches",
    "followup_prompt",
    "record_journal_cost",
    "scene_cue",
    "scene_facts_for",
    "scene_reveal",
    "score_content_recall",
    "sentence_count",
    "word_forms",
]
