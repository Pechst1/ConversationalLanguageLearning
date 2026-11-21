"""«Le bilan» — the learner's week, computed on read from what the app already stores.

One read, no model call, no table of its own. A week is Monday to Sunday in the
learner's own zone (``app.services.streak.user_timezone``): the days come from the
journeys' own ``local_date`` (the learner-local day the journey was played on), and
every timestamped row (Forge verdicts, words, rules) is read between the local
midnights of Monday and the next Monday, each converted to UTC on its own date, so a
week that crosses a DST change is still seven local days (167 or 169 hours).

What it says, in order of the page:

1. **Ce que tu sais dire maintenant** — at most :data:`MAX_LINES` French sentences the
   learner produced this week, in their corrected form. Issues #949 and #971: a
   learner's raw line is never an achievement. A line is shown only when its check is
   settled — a live verdict record that counts (``verdict_records``: Forge, Journal,
   Courrier, Feuilleton) or a scene reply the tutor read (no ``check_failure``) and
   corrected with an ``edit`` on the learner's own sentence, with nothing else left to
   fix (no ``more``) and no solution withheld. A scene reply with no correction is left
   out: «nothing flagged» is not a check of the whole sentence.
2. **Words** — new words met (progress rows created this week, the learner's own
   imports left out) and words held (reviewed this week, last answer recalled), with a
   few shown with their gloss in the learner's language.
3. **Rules** — the Cahier's own states (``concept_life.progress_stage`` and its labels,
   WP-130): a rule introduced this week, or held this week, with where it stands now.
4. **The story** — episodes played (titles), the learner's decisions described (the
   «Le choix» card's own label; the day's commitment as the engine filed it), and the
   one hook that is still open when nothing was played after the week.
   A chapter question settled this week is said as the chronicle filed its answer.
5. **Days** — which of the seven days were played.

Owner scoping: every query filters on the learner's id; a word is read only through the
learner's own progress row (``user_vocabulary_progress.user_id``), never the catalogue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.serial import SerialThread
from app.db.models.verdict_record import VerdictRecord
from app.db.models.vocabulary import VocabularyWord
from app.services.streak import local_today, user_timezone

#: At most this many sentences on the page («three to five»).
MAX_LINES = 5
#: A sentence longer than this is not a line to say aloud (#949: a 21-word reply).
MAX_LINE_WORDS = 14
#: Words shown by name under the counts.
MAX_WORDS_SHOWN = 6
#: Rules listed.
MAX_RULES = 5
#: Decisions described.
MAX_DECISIONS = 3
#: Past weeks offered in the week list.
MAX_PAST_WEEKS = 12
#: The journey statuses that count as a played day (``story_archive.LIVED_STATUSES``
#: plus an open day whose scene was answered).
PLAYED_STATUSES = ("completed", "ended_early")
OPEN_STATUSES = ("active", "paused")
#: A capitalised word between commas in the middle of a line is a name said to someone
#: («Maintenant, Lila, je pense…»): owner rule of 12 Nov, no vocatives in the
#: learner's built lines; such a line is left out rather than cut.
_VOCATIVE = re.compile(r",\s*[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'-]+\s*(?:[,.!?…]|$)")


def bilan_enabled() -> bool:
    return bool(getattr(settings, "BILAN_ENABLED", False))


# ---------------------------------------------------------------------------
# The week
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Week:
    start: date  # Monday, learner-local
    zone: str

    @property
    def end(self) -> date:  # Sunday
        return self.start + timedelta(days=6)

    @property
    def days(self) -> list[date]:
        return [self.start + timedelta(days=offset) for offset in range(7)]

    def utc_bounds(self) -> tuple[datetime, datetime]:
        """Local Monday 00:00 and next Monday 00:00, each in UTC (DST-safe)."""

        zone = ZoneInfo(self.zone)
        start = datetime.combine(self.start, time.min, tzinfo=zone).astimezone(UTC)
        end = datetime.combine(self.start + timedelta(days=7), time.min, tzinfo=zone).astimezone(
            UTC
        )
        return start, end


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def current_week(user: Any, now: datetime | None = None) -> Week:
    return Week(start=monday_of(local_today(user, now)), zone=user_timezone(user))


def week_for(user: Any, start: date | None, now: datetime | None = None) -> Week:
    """The week that holds ``start`` (any day of it), never one after the current week."""

    this_week = current_week(user, now)
    if start is None:
        return this_week
    asked = monday_of(start)
    return Week(start=min(asked, this_week.start), zone=this_week.zone)


def last_closed_week(user: Any, now: datetime | None = None) -> Week:
    this_week = current_week(user, now)
    return Week(start=this_week.start - timedelta(days=7), zone=this_week.zone)


# ---------------------------------------------------------------------------
# Days and episodes
# ---------------------------------------------------------------------------


def _played_journeys(db: Session, user: Any, first: date, last: date) -> list[DailyJourney]:
    rows = db.scalars(
        select(DailyJourney)
        .where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date >= first,
            DailyJourney.local_date <= last,
            DailyJourney.status.in_(PLAYED_STATUSES + OPEN_STATUSES),
        )
        .order_by(DailyJourney.local_date.asc(), DailyJourney.created_at.asc())
    ).all()
    return [journey for journey in rows if _was_played(journey)]


def _was_played(journey: DailyJourney) -> bool:
    if journey.status in PLAYED_STATUSES:
        return True
    # An open day counts once the learner answered in its scene.
    for step in journey.steps or []:
        if step.kind in {"respond", "resolution"} and step.status == "completed":
            return True
        turns = (step.private_task or {}).get("turns") if step.kind == "respond" else None
        if isinstance(turns, list) and turns:
            return True
    return False


def days_played(db: Session, user: Any, week: Week) -> int:
    return len({journey.local_date for journey in _played_journeys(db, user, week.start, week.end)})


def _scene_of(db: Session, journey: DailyJourney):
    from app.services.story_archive import _journey_scene

    try:
        return _journey_scene(db, journey)
    except Exception:  # noqa: BLE001 - a scene that cannot be read only loses its title
        logger.exception("bilan: a day's scene could not be read")
        return None


def _story(db: Session, user: Any, week: Week, journeys: list[DailyJourney]) -> dict[str, Any]:
    from app.services.season.reprise import is_reprise_journey
    from app.services.story_archive import choices_of

    episodes: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for journey in journeys:
        if is_reprise_journey(journey):
            continue
        scene = _scene_of(db, journey)
        title = " ".join(str(getattr(scene, "title", "") or "").split())
        if title and title.casefold() not in seen_titles:
            seen_titles.add(title.casefold())
            episodes.append({"date": journey.local_date.isoformat(), "title_fr": title})
        for choice in (
            choices_of(getattr(scene, "script_payload", None)) if scene is not None else []
        ):
            label = " ".join(str(choice.get("label_fr") or "").split())
            if label:
                decisions.append(
                    {"date": journey.local_date.isoformat(), "label_fr": label, "kind": "choice"}
                )

    live = _live(db, user)
    for event in live.get("events") or []:
        if not isinstance(event, dict):
            continue
        day = _iso_day(event.get("date"))
        if day is None or not (week.start <= day <= week.end):
            continue
        did = _described(event.get("did_fr"))
        if did:
            decisions.append({"date": day.isoformat(), "label_fr": did, "kind": "promise"})

    # A chapter's question the learner settled this week, as the chronicle filed its
    # answer («Tu ne sais pas encore quelle porte la clé ouvre.»). Never its ``quote``
    # (the learner's raw words) and never the question itself.
    for row in live.get("chronicle") or []:
        if not isinstance(row, dict):
            continue
        day = _iso_day(row.get("date"))
        if day is None or not (week.start <= day <= week.end):
            continue
        resolved = _described(row.get("resolved_fr"))
        if resolved and not resolved.endswith("?"):
            decisions.append({"date": day.isoformat(), "label_fr": resolved, "kind": "resolved"})

    unique: list[dict[str, Any]] = []
    folded: set[str] = set()
    for row in sorted(decisions, key=lambda r: r["date"]):
        key = row["label_fr"].casefold()
        if key not in folded:
            folded.add(key)
            unique.append(row)

    return {
        "episodes": episodes,
        "decisions": unique[-MAX_DECISIONS:],
        "next_fr": _open_hook(db, user, week, live),
    }


def _live(db: Session, user: Any) -> dict[str, Any]:
    from app.services.living_story import STATE_KEY

    thread = db.scalars(
        select(SerialThread)
        .where(SerialThread.user_id == user.id)
        .order_by(SerialThread.created_at.desc())
    ).first()
    state = thread.state if thread is not None and isinstance(thread.state, dict) else {}
    live = state.get(STATE_KEY)
    return live if isinstance(live, dict) else {}


def _described(value: Any) -> str:
    from app.services.story_memory import address_placeholder

    text = " ".join(str(value or "").split())
    if not text:
        return ""
    # #917: never the prompts' role word; «tu», or nothing.
    return address_placeholder(text) or ""


def _open_hook(db: Session, user: Any, week: Week, live: dict[str, Any]) -> str | None:
    """The one hook still open, only for the latest played week (an older week's hook
    was answered by the days after it)."""

    from app.services.story_teaser import TEASER_KEY, hook_line, readable_hook

    later = db.scalar(
        select(func.count(DailyJourney.id)).where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date > week.end,
            DailyJourney.status.in_(PLAYED_STATUSES),
        )
    )
    if later:
        return None
    teaser = live.get(TEASER_KEY)
    line = hook_line(teaser) if isinstance(teaser, dict) else ""
    return line if line and readable_hook(line) else None


def _iso_day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Ce que tu sais dire maintenant
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Line:
    text_fr: str
    day: date
    source: str
    corrected: bool


def _one_sentence(text: str, anchor: str | None = None) -> str | None:
    """The sentence of ``text`` that carries ``anchor`` (else the first), when it is a
    whole short sentence with a verb, spelled as the lexicon knows it, said to nobody."""

    from app.services.learner_facts import looks_misspelled, reads_as_sentence
    from app.services.sentence_line import sentences

    parts = sentences(text)
    if not parts:
        return None
    pick = parts[0]
    if anchor:
        found = next((part for part in parts if anchor.casefold() in part.casefold()), None)
        if found is None:
            return None
        pick = found
    pick = " ".join(pick.split())
    if not pick or len(pick.split()) > MAX_LINE_WORDS:
        return None
    if not reads_as_sentence(pick) or looks_misspelled(pick) or _VOCATIVE.search(pick):
        return None
    if pick[-1] not in ".!?…":
        pick = f"{pick}."
    return pick[0].upper() + pick[1:]


def _ledger_lines(
    db: Session, user: Any, start: datetime, end: datetime, zone: ZoneInfo
) -> list[_Line]:
    """Rows of the verdict ledger whose live verdict counts (a settled, checked read)."""

    rows = db.scalars(
        select(VerdictRecord).where(
            VerdictRecord.user_id == user.id,
            VerdictRecord.superseded_by_id.is_(None),
            VerdictRecord.counts.is_(True),
            VerdictRecord.created_at >= start,
            VerdictRecord.created_at < end,
        )
    ).all()
    free_forge = _free_forge_ids(
        db, user, [row.subject_id for row in rows if row.subject_type == "forge_attempt"]
    )
    out: list[_Line] = []
    for row in rows:
        # A Forge drill's answer (a recognised form, a transformed sentence) is the
        # exercise's sentence, not the learner's: only free production counts here
        # (real walk of 21–22 Nov: «Tu es à l'hôtel ?», «Tu es à l'école ?»…).
        if row.subject_type == "forge_attempt" and row.subject_id not in free_forge:
            continue
        shown = (row.verdict or {}).get("shown") if isinstance(row.verdict, dict) else None
        if not isinstance(shown, dict) or shown.get("counts") is False:
            continue
        corrected = str(shown.get("corrected") or "").strip()
        anchor: str | None = None
        if corrected:
            edits = [e for e in shown.get("edits") or [] if isinstance(e, dict)]
            anchor = next(
                (str(e.get("replacement") or "").strip() for e in edits if e.get("replacement")),
                None,
            )
            text = corrected
        elif shown.get("outcome") == "right":
            text = str(row.answer_text or "").strip()
        else:
            # partly / not yet with no corrected sentence: nothing settled to show.
            continue
        line = _one_sentence(text, anchor or None)
        if line:
            stamp = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
            out.append(
                _Line(line, stamp.astimezone(zone).date(), row.subject_type, bool(corrected))
            )
    return out


def _free_forge_ids(db: Session, user: Any, subject_ids: list[str]) -> set[str]:
    import uuid

    from app.db.models.atelier import AtelierAttempt
    from app.services.forge_grading import FREE_PRODUCTION_ROUNDS

    ids = []
    for value in subject_ids:
        try:
            ids.append(uuid.UUID(str(value)))
        except ValueError:
            continue
    if not ids:
        return set()
    rows = db.execute(
        select(AtelierAttempt.id).where(
            AtelierAttempt.user_id == user.id,
            AtelierAttempt.id.in_(ids),
            AtelierAttempt.round.in_(tuple(FREE_PRODUCTION_ROUNDS)),
        )
    ).scalars()
    return {str(value) for value in rows}


#: Which line comes first when there are more than five: what the learner said in the
#: story, then wrote, then built in the Forge.
_SOURCE_RANK = {
    "scene": 0,
    "journal_entry": 1,
    "courrier_turn": 2,
    "courrier_attempt": 2,
    "feuilleton_attempt": 3,
}


def _scene_lines(journeys: list[DailyJourney]) -> list[_Line]:
    out: list[_Line] = []
    for journey in journeys:
        for step in journey.steps or []:
            if step.kind != "respond":
                continue
            for turn in (step.private_task or {}).get("turns") or []:
                line = _scene_line(turn)
                if line:
                    out.append(_Line(line, journey.local_date, "scene", True))
    return out


def _scene_line(turn: Any) -> str | None:
    if (
        not isinstance(turn, dict)
        or turn.get("free")
        or turn.get("check_failure")
        or turn.get("stock_exit")
    ):
        return None
    correction = turn.get("correction")
    if not isinstance(correction, dict) or (correction.get("kind") or "edit") != "edit":
        return None
    if correction.get("more") or correction.get("solution"):
        return None
    span = str(correction.get("span_fr") or "")
    fixed = str(correction.get("corrected_fr") or "")
    said = " ".join(str(turn.get("learner") or "").split())
    if not span or not fixed or not said or said.count(span) != 1:
        return None
    at = said.index(span)
    if at > 0 and fixed[:1].isupper() and not re.search(r"[.!?…]\s*$", said[:at]):
        # The tutor wrote the fix as a sentence of its own («je monter» → «Je monte»);
        # inside the learner's sentence it is lower case («Oui, je monte.»). A name stays.
        head = fixed.split()[0]
        if head.casefold() in _FUNCTION_WORDS:
            fixed = fixed[:1].lower() + fixed[1:]
    line = _one_sentence(said.replace(span, fixed), fixed)
    return line if line and _reads_french(line) else None


#: Words a fix may open with that are never a name.
_FUNCTION_WORDS = frozenset(
    "je j'ai j’ai tu il elle on nous vous ils elles le la les l' un une des du de ce c'est c’est ça "
    "mon ma mes ton ta tes son sa ses notre votre leur leurs ne n'est n’est qu'il qu’il".split()
)


#: A lone elidable letter written without its apostrophe («j ai», «c est»).
_LOST_APOSTROPHE = re.compile(
    r"(?<![\w'’])(?:[jlcdnmts]|qu)\s+(?=[aeiouhéèêàâîôûy])", re.IGNORECASE
)


def _reads_french(line: str) -> bool:
    """A scene reply is corrected one issue at a time, so the rest of its sentence was
    not looked at as closely as a ledger check: keep it only when every word is one the
    lexicon knows (a name, capitalised, is let through) and no apostrophe was lost.
    Real walk of 21–27 Nov: «Je suis müde» and «j ai» sat next to the corrected span."""

    from app.services.learner_facts import _lexicon_verb
    from app.services.lexical_coverage import CuratedResolver, load_lexicon, tokenize

    if _LOST_APOSTROPHE.search(line):
        return False
    lexicon = load_lexicon()
    resolver = CuratedResolver()

    def known(key: str) -> bool:
        if (
            key in lexicon.elisions
            or any(char.isdigit() for char in key)
            or _lexicon_verb(key, lexicon)
        ):
            return True
        candidates = list(resolver.candidates(key))
        # «secrète» → «secret», «première» → «premier»: feminines the table does not fold.
        for suffix, stem in (("ète", "et"), ("ère", "er"), ("ètes", "et"), ("ères", "er")):
            if key.endswith(suffix):
                candidates.append(key[: -len(suffix)] + stem)
        return any(c in lexicon.lemmas or c in lexicon.forms for c in candidates)

    for token in tokenize(line):
        if known(token.key):
            continue
        surface = token.surface
        if (
            surface[:1].isupper()
            and not _GERMANIC.search(surface)
            and surface.casefold() not in _NOT_NAMES
        ):
            # a name («Odile», «Margaux»), wherever it stands
            continue
        return False
    return True


#: Letters French never writes: a word with them is not French («müde», «weiß»).
_GERMANIC = re.compile(r"[äöüßÄÖÜẞ]")
#: Capitalised words a learner mixes in that are not names.
_NOT_NAMES = frozenset(
    "ich du er wir ihr sie es das der die den und nicht ist bin hallo ja nein".split()
)


def _fold(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.casefold()).strip()


def _choose_lines(lines: list[_Line]) -> list[dict[str, Any]]:
    unique: dict[str, _Line] = {}
    for line in lines:
        unique.setdefault(_fold(line.text_fr), line)
    # Prefer a corrected line (the week's progress), the story's over the Forge's, one
    # of a day not yet used, then a fuller sentence; print them in the week's order.
    ranked = sorted(
        unique.values(),
        key=lambda row: (
            not row.corrected,
            _SOURCE_RANK.get(row.source, 4),
            -len(row.text_fr.split()),
        ),
    )
    chosen: list[_Line] = []
    days: set[date] = set()
    for line in ranked:
        if line.day not in days:
            chosen.append(line)
            days.add(line.day)
    for line in ranked:
        if len(chosen) >= MAX_LINES:
            break
        if line not in chosen:
            chosen.append(line)
    chosen = sorted(chosen[:MAX_LINES], key=lambda row: row.day)
    return [
        {"text_fr": row.text_fr, "date": row.day.isoformat(), "source": row.source}
        for row in chosen
    ]


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------


def _words(
    db: Session, user: Any, start: datetime, end: datetime, language: str, zone: ZoneInfo
) -> dict[str, Any]:
    from app.services.glosses import word_gloss

    new_rows = (
        db.execute(
            select(VocabularyWord)
            .join(UserVocabularyProgress, UserVocabularyProgress.word_id == VocabularyWord.id)
            .where(
                UserVocabularyProgress.user_id == user.id,
                UserVocabularyProgress.created_at >= start,
                UserVocabularyProgress.created_at < end,
                # the learner's own Anki imports were not met in the app this week
                VocabularyWord.is_anki_card.isnot(True),
                VocabularyWord.language == "fr",
            )
            .order_by(UserVocabularyProgress.created_at.asc())
        )
        .scalars()
        .all()
    )

    reviews = db.execute(
        select(
            UserVocabularyProgress.word_id,
            ReviewLog.rating,
            ReviewLog.review_date,
            UserVocabularyProgress.created_at,
        )
        .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
        .where(
            UserVocabularyProgress.user_id == user.id,
            ReviewLog.review_date >= start,
            ReviewLog.review_date < end,
        )
    ).all()
    # «Held»: the word's last review this week was recalled, and it was a review on a
    # later local day than the day the word was met — a retry inside the lesson that
    # introduced it is not retention (real walk of 21–27 Nov: every drill miss was
    # retried until right the same minute, so «last answer right» alone held them all).
    last: dict[int, tuple[Any, int, bool]] = {}
    for word_id, rating, stamp, met in reviews:
        if word_id is None or stamp is None:
            continue
        later_day = (
            met is None
            or _aware(stamp).astimezone(zone).date() > _aware(met).astimezone(zone).date()
        )
        previous = last.get(word_id)
        if previous is None or stamp >= previous[0]:
            last[word_id] = (stamp, int(rating or 0), later_day)
    held_ids = {
        word_id for word_id, (_stamp, rating, later) in last.items() if rating > 0 and later
    }

    shown: list[dict[str, str]] = []
    for word in new_rows:
        gloss = word_gloss(word, language)
        if gloss and len(shown) < MAX_WORDS_SHOWN:
            shown.append({"word": word.word, "gloss": gloss})
    return {
        "new_count": len({word.id for word in new_rows}),
        "reviewed_count": len(last),
        "held_count": len(held_ids),
        "shown": shown,
    }


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _rules(
    db: Session, user: Any, start: datetime, end: datetime, language: str
) -> list[dict[str, Any]]:
    from app.services.concept_life import STAGE_HELD, STAGE_NEW, progress_stage, stage_label
    from app.services.concept_titles import (
        concept_title,
        localizations_by_concept_id,
    )

    rows = db.execute(
        select(UserGrammarProgress, GrammarConcept)
        .join(GrammarConcept, GrammarConcept.id == UserGrammarProgress.concept_id)
        .where(UserGrammarProgress.user_id == user.id)
    ).all()
    moved: list[tuple[datetime, UserGrammarProgress, GrammarConcept, str]] = []
    for progress, concept in rows:
        if getattr(progress, "tested_out_at", None) is not None:
            continue
        introduced = _aware(progress.introduced_at)
        held = _aware(progress.held_at)
        if held is not None and start <= held < end:
            # Held this week: it was on its way before (or met this same week).
            origin = (
                STAGE_NEW if introduced is not None and start <= introduced < end else "practising"
            )
            moved.append((held, progress, concept, origin))
        elif introduced is not None and start <= introduced < end:
            moved.append((introduced, progress, concept, STAGE_NEW))
    if not moved:
        return []
    moved.sort(key=lambda row: (progress_stage(row[1]) != STAGE_HELD, row[0]))
    moved = moved[:MAX_RULES]
    titles = localizations_by_concept_id(db, [concept.id for _, _, concept, _ in moved])
    out: list[dict[str, Any]] = []
    for _stamp, progress, concept, origin in sorted(moved, key=lambda row: row[0]):
        stage = progress_stage(progress)
        if stage == STAGE_NEW:
            continue
        localizations = titles.get(concept.id, {})
        out.append(
            {
                "concept_id": concept.id,
                "title": concept_title(concept, language, localizations=localizations),
                "title_fr": concept_title(concept, "fr", localizations=localizations),
                "from_stage": origin,
                "from_label": stage_label(origin, language),
                "stage": stage,
                "stage_label": stage_label(stage, language),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Past weeks
# ---------------------------------------------------------------------------


def _past_weeks(db: Session, user: Any, this_week: Week) -> list[dict[str, Any]]:
    since = this_week.start - timedelta(days=7 * MAX_PAST_WEEKS)
    rows = db.scalars(
        select(DailyJourney).where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date >= since,
            DailyJourney.local_date < this_week.start,
            DailyJourney.status.in_(PLAYED_STATUSES + OPEN_STATUSES),
        )
    ).all()
    by_week: dict[date, set[date]] = {}
    for journey in rows:
        if _was_played(journey):
            by_week.setdefault(monday_of(journey.local_date), set()).add(journey.local_date)
    return [
        {"week_start": monday.isoformat(), "days_played": len(days)}
        for monday, days in sorted(by_week.items(), reverse=True)
    ]


# ---------------------------------------------------------------------------
# The read
# ---------------------------------------------------------------------------


def build_bilan(
    db: Session, user: Any, *, week_start: date | None = None, now: datetime | None = None
) -> dict[str, Any]:
    from app.services.chrome_language import user_chrome_language, user_mother_tongue
    from app.services.journey_content import learner_level_band

    now = now or datetime.now(UTC)
    this_week = current_week(user, now)
    week = week_for(user, week_start, now)
    today = local_today(user, now)
    start, end = week.utc_bounds()
    zone = ZoneInfo(week.zone)
    chrome = user_chrome_language(user)

    journeys = _played_journeys(db, user, week.start, week.end)
    played = {journey.local_date for journey in journeys}
    lines = _choose_lines(_ledger_lines(db, user, start, end, zone) + _scene_lines(journeys))
    words = _words(db, user, start, end, user_mother_tongue(user), zone)
    rules = _rules(db, user, start, end, chrome)
    story = _story(db, user, week, journeys)
    past = _past_weeks(db, user, this_week)
    previous = next(
        (row["week_start"] for row in past if row["week_start"] < week.start.isoformat()), None
    )
    later = [row["week_start"] for row in past if row["week_start"] > week.start.isoformat()]
    following = (
        min(later)
        if later
        else (this_week.start.isoformat() if week.start < this_week.start else None)
    )

    return {
        "week_start": week.start.isoformat(),
        "week_end": week.end.isoformat(),
        "timezone": week.zone,
        "is_current": week.start == this_week.start,
        "closed": week.end < today,
        "language": chrome,
        "level": learner_level_band(user),
        "days": [
            {"date": day.isoformat(), "played": day in played, "future": day > today}
            for day in week.days
        ],
        "days_played": len(played),
        "lines": lines,
        "words": words,
        "rules": rules,
        "story": story,
        "weeks": [
            {
                "week_start": this_week.start.isoformat(),
                "days_played": days_played(db, user, this_week),
            },
            *past,
        ],
        "previous_week_start": previous,
        "next_week_start": following,
    }


def home_card(db: Session, user: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """The last closed week, for Home's card: shown only when that week had a played day."""

    week = last_closed_week(user, now)
    played = days_played(db, user, week)
    return {"week_start": week.start.isoformat() if played else None, "days_played": played}


__all__ = [
    "MAX_LINES",
    "Week",
    "bilan_enabled",
    "build_bilan",
    "current_week",
    "days_played",
    "home_card",
    "last_closed_week",
    "monday_of",
    "week_for",
]
