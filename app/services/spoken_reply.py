"""WP-158 slice 1 — speaking inside the story.

The learner answers a story character aloud instead of typing. This module is
the server side of that, and it is deliberately small, because nothing about
*grading* changes: the recording is turned into text by the existing
``POST /audio/transcribe`` (surface ``story_reply``), the client shows the
transcript for a moment, and the transcript is sent through **the same reply
endpoint as a typed answer** with ``mode: 'voice'``. The WP-149 met-gate, the
reply lanes and the evidence ledger therefore see exactly what they would have
seen had the learner typed the sentence.

What lives here:

* :func:`authorize_story_upload` — the flag, the ownership of the journey and
  the step, the per-upload length cap and the **per-turn cost ceiling**, all
  checked *before* any provider call. A refusal costs nothing and leaves the
  turn open on the typed path.
* :class:`FakeTranscriber` — a deterministic stand-in for Whisper, used by the
  tests and by dev stacks that set ``ATELIER_FAKE_TRANSCRIBER_ENABLED``.
* :func:`repeat_line_for` — the one useful line the recap offers to repeat once
  the conversation is closed.

No pronunciation scoring, ever (WP-27 owner decision): speech becomes text and
the text is graded like typed text.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.pilot_event import PilotEvent
from app.services import sentence_line
from app.services.learner_facts import (
    content_of,
    contradicts,
    drops_ne,
    facts_of,
    has_verb,
    latest_clash,
    looks_misspelled,
    reads_as_sentence,
)
from app.services.scene_ledger import read_turn
from app.services.transcription_cost import (
    TRANSCRIPTION_EVENT_TYPE,
    estimate_audio_seconds,
    estimate_transcription_cost_usd,
)

#: The transcription surface of a spoken story reply (the ledger reads it by name).
STORY_REPLY_SURFACE = "story_reply"
#: The ledger entity a story-reply transcription is booked against: one turn.
TURN_ENTITY_TYPE = "journey_turn"

#: What the fake transcriber hears when the upload does not say otherwise.
FAKE_DEFAULT_TRANSCRIPT = "Bonjour, je voudrais un café, s'il vous plaît."
#: An upload whose bytes start with this marker is transcribed as the rest of it
#: (UTF-8), so a test or a dev walk can choose the sentence it "said".
FAKE_TRANSCRIPT_MARKER = b"TRANSCRIPT:"


class SpokenReplyRefused(Exception):
    """The upload is refused before transcription; the turn stays open."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class StoryUpload:
    """An authorised story-reply upload: which turn it is booked against."""

    journey_id: uuid.UUID
    step_id: uuid.UUID
    turn_index: int

    @property
    def entity_id(self) -> str:
        return f"{self.step_id}:{self.turn_index}"

    def ledger_fields(self) -> dict[str, Any]:
        return {
            "journey_id": str(self.journey_id),
            "step_id": str(self.step_id),
            "turn_index": self.turn_index,
        }


def spoken_reply_enabled() -> bool:
    return bool(settings.ATELIER_SPOKEN_REPLY_ENABLED)


def offered_on(step_kind: str, prompt: dict[str, Any]) -> bool:
    """Whether a respond prompt offers «Parler» (read at projection time).

    A letter day answers a written letter, so it stays written; every story
    conversation offers it while the flag is on.
    """

    if not spoken_reply_enabled() or str(step_kind) != "respond":
        return False
    return not prompt.get("letter")


def _parse_uuid(value: str | None, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise SpokenReplyRefused(
            422, "spoken_reply_bad_reference", f"A spoken story reply needs a valid {field}."
        ) from exc


def turn_spend_usd(db: Session, *, user_id: uuid.UUID, entity_id: str) -> float:
    """What this learner's transcriptions of one turn have cost so far (estimated)."""

    total = db.scalar(
        select(func.coalesce(func.sum(PilotEvent.cost_usd), 0.0)).where(
            PilotEvent.user_id == user_id,
            PilotEvent.event_type == TRANSCRIPTION_EVENT_TYPE,
            PilotEvent.entity_type == TURN_ENTITY_TYPE,
            PilotEvent.entity_id == entity_id,
        )
    )
    return float(total or 0.0)


def authorize_story_upload(
    db: Session,
    *,
    user_id: uuid.UUID,
    journey_id: str | None,
    step_id: str | None,
    byte_count: int,
    content_type: str | None = None,
    measured_seconds: float | None = None,
) -> StoryUpload:
    """Every check a spoken story turn must pass before a provider is called.

    Order matters for what the learner is told: a switched-off feature first,
    then a reference that is not theirs, then a step that is not open for a
    reply, then length, then money.
    """

    if not spoken_reply_enabled():
        raise SpokenReplyRefused(404, "spoken_reply_disabled", "Spoken story replies are off.")
    journey_uuid = _parse_uuid(journey_id, "journey_id")
    step_uuid = _parse_uuid(step_id, "step_id")
    journey = db.scalar(
        select(DailyJourney).where(
            DailyJourney.id == journey_uuid, DailyJourney.user_id == user_id
        )
    )
    if journey is None:
        raise SpokenReplyRefused(404, "spoken_reply_not_found", "Journey not found.")
    step = db.scalar(
        select(DailyJourneyStep).where(
            DailyJourneyStep.id == step_uuid, DailyJourneyStep.journey_id == journey.id
        )
    )
    if step is None:
        raise SpokenReplyRefused(404, "spoken_reply_not_found", "Step not found.")
    prompt = step.public_prompt if isinstance(step.public_prompt, dict) else {}
    if not offered_on(str(step.kind), prompt):
        raise SpokenReplyRefused(
            409, "spoken_reply_not_offered", "This step does not take a spoken reply."
        )
    if str(step.status) == "completed":
        raise SpokenReplyRefused(
            409, "spoken_reply_turn_closed", "This conversation is already closed."
        )
    seconds = estimate_audio_seconds(byte_count, content_type, measured_seconds=measured_seconds)
    if seconds > float(settings.ATELIER_SPOKEN_REPLY_MAX_SECONDS):
        raise SpokenReplyRefused(
            413, "spoken_reply_too_long", "A spoken reply is at most thirty seconds."
        )
    upload = StoryUpload(
        journey_id=journey.id,
        step_id=step.id,
        # The server's turn, never the client's: the ceiling is per turn.
        turn_index=int(prompt.get("turn_index") or getattr(step, "turn_index", 0) or 0),
    )
    spent = turn_spend_usd(db, user_id=user_id, entity_id=upload.entity_id)
    ceiling = float(settings.ATELIER_SPOKEN_REPLY_MAX_USD_PER_TURN)
    if spent + estimate_transcription_cost_usd(
        byte_count, content_type, measured_seconds=measured_seconds
    ) > ceiling + 1e-9:
        raise SpokenReplyRefused(
            429,
            "spoken_reply_turn_ceiling",
            "This turn has used its spoken attempts; please type the reply.",
        )
    return upload


class FakeTranscriber:
    """Deterministic transcription, no network, no money.

    ``TRANSCRIPT:<utf-8 text>`` uploads come back as that text (up to a NUL, so
    a test can pad the upload to a length); anything else
    comes back as :data:`FAKE_DEFAULT_TRANSCRIPT`. It has the provider's call
    shape so the endpoint does not care which one it holds.
    """

    def __init__(self, default: str = FAKE_DEFAULT_TRANSCRIPT) -> None:
        self.default = default
        self.calls = 0

    def transcribe_audio(
        self,
        file: Any,
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        self.calls += 1
        content = file if isinstance(file, (bytes, bytearray)) else b""
        if bytes(content).startswith(FAKE_TRANSCRIPT_MARKER):
            said = bytes(content)[len(FAKE_TRANSCRIPT_MARKER):].split(b"\x00", 1)[0]
            return said.decode("utf-8", "ignore").strip()
        return self.default


def fake_transcriber_active() -> bool:
    """The dev/test switch; never honoured in production."""

    return bool(settings.ATELIER_FAKE_TRANSCRIBER_ENABLED) and (
        str(settings.APP_ENV).lower() != "production"
    )


def _last_route(private: dict[str, Any]) -> dict[str, Any] | None:
    """The route of the learner's last real answer (a free «ask again» does not count)."""

    for exchange in reversed(private.get("turns") or []):
        if not isinstance(exchange, dict) or exchange.get("free"):
            continue
        route = exchange.get("route")
        return route if isinstance(route, dict) else None
    return None


def repeat_line_for(step: DailyJourneyStep, correction: Any = None) -> str | None:
    """The one useful line the recap offers to repeat, once the reply is closed.

    The line the current question was written to elicit, while it goes along with what
    the learner said (:func:`_turn_it_goes_against`); otherwise what the learner said,
    as a correct sentence (:func:`_own_line`); otherwise none, and the card hides. So it
    is never a line they would refuse, a sentence with their mistakes in it, or a fragment
    (#379, #535, #556, #558). Whatever its source, the line leaves through :func:`_as_line`,
    which holds it to one sentence of at most :data:`SAY_ALOUD_MAX_WORDS` words, a main
    clause, about the question's line where the learner's words allow (#949). ``None``
    while the flag is off.
    """

    from app.services import scene_record

    if not scene_record.enabled():
        return _main_repeat_line_for(step, correction)
    if not spoken_reply_enabled():
        return None
    private = step.private_task if isinstance(step.private_task, dict) else {}
    task = private.get("response_task") if isinstance(private.get("response_task"), dict) else {}
    turns = _learner_turns(private)
    routed = _last_route(private)
    # An authored page routes the learner's answer. What they meant is the route's own
    # sentence; the question's scripted example is one of the *other* answers as often as
    # not («Donner une clé à Lila» after «Pas encore»), so a routed turn never falls back to it.
    written = (routed or {}).get("say_fr") if routed is not None else task.get("suggested_response_fr")
    written = str(written or "").strip()
    if written:
        # The page's lines are written whole, and some are whole without a verb («Merci pour
        # tout.»), so they need only be long enough to practise; a long one is cut like any
        # other text (#949). A generated one is held to the sentence rule like any other text.
        line = _as_line(written, authored=routed is not None)
        if line:
            # Read whole: a written line that goes along with the learner still does once cut
            # (the cut says less, nothing else); one that goes against them never stands.
            against = _turn_it_goes_against([said for said, _ in turns], written)
            if against is None:
                return line
            return _own_line(turns, correction, first=against, about=written)
        return _own_line(turns, correction, first=len(turns) - 1, about=written)
    if routed is not None and routed.get("tap"):
        # #535: a clue's tap target is not a sentence (the neon's label, the pan). The recap
        # offers what the learner wrote, but only as the corrected sentence they were shown,
        # and only when it keeps their facts. Their uncorrected words are never offered as a
        # model (#445); a route the page did not understand carries no ``tap``.
        if turns:
            said, stored = turns[-1]
            return _corrected_sentence(said, correction or stored)
        return None
    return _corrected_sentence(turns[-1][0] if turns else "", correction)


def _turn_it_goes_against(said: list[str], line: str) -> int | None:
    """The turn a line written beforehand goes against, or ``None`` when it may stand.

    Written before the learner spoke, it may state another date or reason (#379), say yes
    to what they refused (#556, 9 Nov: «Oui, on partage.»), or be about something they
    never brought up (7 Nov: «Ça va, merci. Un peu triste.» after «je vais bien»,
    «fatigué»). A reply with nothing in it («Oui.») has nothing to go against."""

    if not said:
        return None
    # The facts' own rule: the latest turn that states a fact decides, so a learner who
    # corrected themselves keeps the corrected fact.
    clash = latest_clash(said, line)
    if clash is not None:
        return clash
    last = len(said) - 1
    answers = {read_turn(said[last]).get("intent"), read_turn(line).get("intent")}
    if answers == {"yes", "no"}:
        return last
    spoken = [content_of(turn) for turn in said]
    if any(spoken) and not any(content_of(line) & words for words in spoken):
        return last
    return None


def _own_line(turns: list[tuple[str, Any]], correction: Any, *, first: int, about: str = "") -> str | None:
    """What the learner said on the turn that counts, as a correct sentence; failing that,
    on their latest turn that gives one. It never goes against what they said since: a line
    cut from their words may leave a fact out, never state one they took back.
    ``about`` is the line the question was written to elicit: of a long reply, the clause
    about the same thing is the one offered (#949)."""

    said = [text for text, _ in turns]
    order = [first, *[index for index in reversed(range(len(turns))) if index != first]]
    for index in order:
        if not 0 <= index < len(turns):
            continue
        text, stored = turns[index]
        # The correction handed in is the last turn's; the one the learner was shown is kept
        # with the turn, so the recap and its audio door read the same sentence.
        own = _own_sentence(text, (correction if index == len(turns) - 1 else None) or stored, about=about)
        if own and latest_clash(said, own, stated_only=True) is None:
            return own
    return None


def _main_repeat_line_for(step: DailyJourneyStep, correction: Any = None) -> str | None:
    """``repeat_line_for`` as main had it, while ``STORY_SCENE_RECORD`` is off.

    The line the current question was written to elicit (the task's
    ``suggested_response_fr``, kept private until now because it would have been
    the answer); failing that, the corrected form of the learner's own sentence
    when it is a sentence. ``None`` while the flag is off.
    """

    if not spoken_reply_enabled():
        return None
    private = step.private_task if isinstance(step.private_task, dict) else {}
    task = private.get("response_task") if isinstance(private.get("response_task"), dict) else {}
    routed = _last_route(private)
    if routed is not None:
        # An authored page routes the learner's answer. What they meant is the
        # route's own sentence; the question's scripted example is one of the
        # *other* answers as often as not («Donner une clé à Lila» after «Pas
        # encore»), so a routed turn never falls back to it.
        line = str(routed.get("say_fr") or "").strip()
        if line:
            return line
    else:
        line = str(task.get("suggested_response_fr") or "").strip()
        # #379: that example was written before the learner spoke. It is offered
        # only while it keeps every date, number and reason they gave; otherwise
        # it would be their sentence with someone else's facts in it.
        # A scene has several exchanges (#378): the date and the reason are often
        # given on the first turn and never repeated, so every real turn counts.
        turns = _learner_turns(private)
        # Per kind of fact the latest turn that states it decides: a learner who
        # corrected themselves («finalement le 5 mars») keeps the corrected fact.
        clash = latest_clash([said for said, _ in turns], line)
        if line and clash is None:
            return line
        if line:
            said, stored = turns[clash]
            # The recap and its audio door both ask: the correction the learner was
            # shown is kept with the turn, so both read the same sentence. The
            # correction handed in is the last turn's.
            last = clash == len(turns) - 1
            return _main_own_sentence(said, (correction if last else None) or stored)
    corrected = str(getattr(correction, "corrected_fr", "") or "").strip()
    return corrected if len(corrected.split()) >= 3 else None


def _learner_turns(private: dict[str, Any]) -> list[tuple[str, Any]]:
    """What the learner wrote on each real turn, in order, with the correction they were
    shown for it (a free «ask again» does not count)."""

    turns: list[tuple[str, Any]] = []
    for exchange in private.get("turns") or []:
        if isinstance(exchange, dict) and not exchange.get("free") and str(exchange.get("learner") or "").strip():
            shown = exchange.get("correction")
            stored = SimpleNamespace(corrected_fr=shown.get("corrected_fr")) if isinstance(shown, dict) else None
            turns.append((str(exchange["learner"]).strip(), stored))
    return turns


def _corrected_sentence(said: str, correction: Any, *, about: str = "") -> str | None:
    """The correction the learner was shown, when it is a sentence that keeps their facts.
    A correction can be partial (8 Nov: only «lappartement» was fixed), so it is read too."""

    corrected = str(getattr(correction, "corrected_fr", "") or "").strip()
    if not reads_as_sentence(corrected) or looks_misspelled(corrected) or contradicts(said, corrected):
        return None
    return _as_line(corrected, about=about)


def _own_sentence(said: str, correction: Any, *, about: str = "") -> str | None:
    """The learner's sentence: the correction they were shown, or their own words when none
    was needed. Words the margin corrected hold a mistake, so they are never offered, not
    even when the correction itself cannot be (#445, #558)."""

    if str(getattr(correction, "corrected_fr", "") or "").strip():
        return _corrected_sentence(said, correction, about=about)
    return _as_line(said, about=about) if reads_as_sentence(said) and not looks_misspelled(said) else None


# ---------------------------------------------------------------------------------------
# One line to say aloud (#949). Every source of the card's line (the learner's words, the
# correction they were shown, a generated example, the page's own line) has no length, and
# until #949 each was returned as it came: 20 Nov, a 21-word reply of two sentences went on
# the card. The line is cut here, once, for all of them.
# ---------------------------------------------------------------------------------------

#: The most words «One line to say aloud» offers: one breath, said once, at A1 (#949).
SAY_ALOUD_MAX_WORDS = 10
#: Where a sentence divides into clauses: a comma, a «…» inside it, «mais», or «et» before a
#: new subject («Je garde la banquette et je dis à Bastien de partir»); «toi et moi» stays whole.
_CLAUSE_BREAK = re.compile(
    r"\s*(?:[,;:]|…(?=\s)|\bmais\b|\bet\b(?=\s+(?:je|j['’]|tu|il|elle|on|nous|vous|ils|elles)\b))\s*",
    re.IGNORECASE,
)
#: What a clause that cannot stand alone opens on: «Parce que je suis fatigué.», «Si tu veux
#: savoir.», «Quand Lila arrive.», «qui habite à Paris» (review of #1014). «Si,» alone is a yes.
_SUBORDINATE = re.compile(
    r"^(?:et\s+|ou\s+)?(?:parce\s+qu|puisqu|car\b|si\b(?!\s*[,.!?])|s['’]ils?\b(?!\s+(?:te|vous)\s+pla)|quand\b|lorsqu|comme\b"
    r"|que\b|qu['’]|pour\s+qu|bien\s+qu|afin\s+qu|avant\s+qu|pendant\s+qu|dès\s+qu|alors\s+qu"
    r"|même\s+si\b|tandis\s+qu|sans\s+qu|jusqu['’]à\s+ce\s+qu|qui\b|où\b|dont\b)",
    re.IGNORECASE,
)
#: «Je pense que …», «je crois que …»: a hedge in front of the decision, not the decision.
_HEDGE = re.compile(r"^(?:je\s+pense|je\s+crois|je\s+trouve)\s+qu(?:e\s+|['’])", re.IGNORECASE)
#: Where a clause too long to say can end early: before its complements («Je pars le 5 mars
#: | avec ma sœur …»). Never before «de», which holds the clause's own object («la carte de …»).
_COMPLEMENT = frozenset(
    "avec pour dans chez sur sous à au aux en depuis pendant après avant sans vers par contre entre".split()
)
#: Words a line never ends on: what they open is in the part cut away.
_OPENS_MORE = frozenset(
    "le la les l' un une des du de d' mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs "
    "ce cet cette ces et ou mais que qu' qui ne n' très".split()
)
#: «Je suis content pour toi. / Je suis contente pour toi.»: the page's two forms of one line.
_ALTERNATIVE = re.compile(r"\s+/\s+")
#: A stop inside a form: it would be two sentences on the card.
_INNER_STOP = re.compile(r"[.!?]" + sentence_line.NOT_AFTER_TITLE + r"\s|\s/\s")
#: A clause whose subject is the learner: the line that says what they decide.
_FIRST_PERSON = re.compile(r"^(?:je\b|j['’])", re.IGNORECASE)


def _clauses(body: str) -> list[tuple[int, int]]:
    """Where each clause of a sentence starts and stops, the breaks between them left out."""

    breaks = list(_CLAUSE_BREAK.finditer(body))
    starts = [0, *(match.end() for match in breaks)]
    stops = [*(match.start() for match in breaks), len(body)]
    return [(start, stop) for start, stop in zip(starts, stops, strict=True) if body[start:stop].strip()]


def _is_main(clause: str) -> bool:
    return has_verb(clause) and not _SUBORDINATE.match(clause.strip())


def _forms(sentence: str) -> list[str]:
    """One sentence, then shorter forms of it to try: the sentence cut after a clause («Non,
    je ne partage pas la pizza»), the sentence from its first main clause on (without
    «Maintenant, Lila,» or «Si tu veux savoir,»), each main clause on its own, each of those
    without «je pense que», and, for one still too long, the part before its complements
    («Je pars le 5 mars»). A clause that opens on «parce que», «si», «quand»… is never a
    form of its own (review of #1014)."""

    body = sentence.strip().rstrip(" .!?…")
    if not body:
        return []
    spans = _clauses(body)
    main = [index for index, (start, stop) in enumerate(spans) if _is_main(body[start:stop])]
    forms = [body, *(body[: spans[index][1]] for index in reversed(range(len(spans) - 1)))]
    if main and spans[main[0]][0] > 0:
        forms.append(body[spans[main[0]][0] :])
    forms.extend(body[spans[index][0] : spans[index][1]] for index in main)
    # «Je ne sais pas pourquoi, mais je garde la clé»: what comes after «mais» is the point.
    turn = max((match.end() for match in _CLAUSE_BREAK.finditer(body) if "mais" in match.group(0).lower()), default=0)
    forms.sort(key=lambda form: body.rfind(form) < turn)
    forms = [*(_HEDGE.sub("", form) for form in forms if _HEDGE.match(form)), *forms]
    for form in list(forms):
        words = form.split()
        if len(words) <= SAY_ALOUD_MAX_WORDS:
            continue
        for cut in reversed(range(3, len(words))):
            if words[cut].lower() in _COMPLEMENT and words[cut - 1].lower().strip(",") not in _OPENS_MORE:
                forms.append(" ".join(words[:cut]).rstrip(","))
    # A form that ends where the sentence ends keeps its «?» or «!».
    end = sentence.strip()[len(body) :]
    forms = [form.strip() + end if body.endswith(form) else form for form in forms]
    return [form for form in dict.fromkeys(form.strip() for form in forms) if form]


def _stands_alone(form: str, *, authored: bool) -> bool:
    """A form is a line when it reads as a sentence, keeps its «ne», does not open on a
    subordinate clause and holds a main clause («Oui, je reste», «Non, je ne partage pas»).
    The page's own line is written to be said: it needs only be long enough to practise."""

    if authored:
        return len(form.split()) >= 3
    if not reads_as_sentence(form) or drops_ne(form) or _SUBORDINATE.match(form.strip()):
        return False
    return any(_is_main(form[start:stop]) for start, stop in _clauses(form))


def _lead_stripped(form: str) -> str:
    """The form from its first clause with a verb on («Oui, je reste» → «je reste»)."""

    start = next((start for start, stop in _clauses(form) if has_verb(form[start:stop])), 0)
    return form[start:]


def _as_line(text: str, *, about: str = "", authored: bool = False) -> str | None:
    """Written as one line to say aloud: «je vais bien» is shown as «Je vais bien.»

    A reply is often longer than a line (20 Nov: two sentences, a vocative, a joke about a
    cat, 21 words). The line is one sentence of at most :data:`SAY_ALOUD_MAX_WORDS` words
    and a main clause: never a clause that opens on «parce que» or «si» on its own, never
    one that drops «ne» (21 Nov: «Bastien est pas un ami»). Of the forms that fit, the one
    about what ``about`` is about comes first (the question's line names the decision),
    then the one that keeps most of the dates, numbers and reasons the text gives (#379),
    then one the learner says as «je», then the text's own order. ``None`` when no form
    fits: the card hides rather than offer a long line or a fragment.

    ``authored``: the page's own line, written whole to be said, stands as it is while it
    is short enough; a long one is cut to a sentence of it."""

    text = " ".join(str(text or "").split())
    if authored and 3 <= len(text.split()) <= SAY_ALOUD_MAX_WORDS:
        return text
    topic = content_of(about) if about else frozenset()
    given = facts_of(text)
    best: tuple[tuple[int, int, int, int], str] | None = None
    forms = [
        form
        for sentence in sentence_line.sentences(text)
        for part in _ALTERNATIVE.split(sentence)
        for form in _forms(part)
    ]
    for order, form in enumerate(forms):
        words = form.split()
        if len(words) > SAY_ALOUD_MAX_WORDS or words[-1].lower() in _OPENS_MORE or _INNER_STOP.search(form):
            continue
        if not _stands_alone(form, authored=authored) or contradicts(text, form, stated_only=True):
            continue
        kept = facts_of(form)
        rank = (
            -len(content_of(form) & topic),
            -sum(len(kept.get(kind, frozenset()) & value) for kind, value in given.items()),
            0 if _FIRST_PERSON.match(_HEDGE.sub("", _lead_stripped(form))) else 1,
            order,
        )
        if best is None or rank < best[0]:
            best = (rank, form)
    return _written(best[1]) if best else None


def _written(form: str) -> str:
    """Capitalised and stopped: «je vais bien» is shown as «Je vais bien.»"""

    line = form[:1].upper() + form[1:]
    return line if line[-1:] in ".!?…»\"" else f"{line}."


def _main_own_sentence(said: str, correction: Any) -> str | None:
    """The learner's sentence, corrected when the correction is a sentence that keeps their facts."""

    corrected = str(getattr(correction, "corrected_fr", "") or "").strip()
    if len(corrected.split()) >= 3 and not contradicts(said, corrected):
        return corrected
    return said if len(said.split()) >= 3 else None


__all__ = [
    "FAKE_DEFAULT_TRANSCRIPT",
    "FAKE_TRANSCRIPT_MARKER",
    "SAY_ALOUD_MAX_WORDS",
    "STORY_REPLY_SURFACE",
    "TURN_ENTITY_TYPE",
    "FakeTranscriber",
    "SpokenReplyRefused",
    "StoryUpload",
    "authorize_story_upload",
    "fake_transcriber_active",
    "offered_on",
    "repeat_line_for",
    "spoken_reply_enabled",
    "turn_spend_usd",
]
