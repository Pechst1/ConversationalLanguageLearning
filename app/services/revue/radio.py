"""WP-122 A «La Radio» — the week's Papier as a fifty-second bulletin in the cast's voices.

``bulletin_for(db, dossier, band)`` writes and speaks one bulletin (spec §3.1):

1. **Romy's lede** — the dossier's ``summary_fr``, whole sentences up to half the band's
   reading target (``policy.SUPPORT_DEFAULTS[band]["reading_target_words"] // 2``);
2. **three claims, spoken** — facts as they are reported, interpretations (and forecasts)
   with their source said aloud: «D'après <attributed_to>, …». A1 hears facts only
   (the band's depth is «change and who»); A2 and up hear two facts and one view;
3. **the guest's reaction** — the authored line of the topic's guest
   (``evergreen/guests/guest_lines.json``), or the phase-2 line when the caller has one;
4. **Romy's sign-off** — «C'était Le Papier, semaine 41.»

The bulletin is fitted to 45–60 s, estimated from characters at :data:`CHARS_PER_SECOND`
plus a short silence between lines and the «jingle of nothing» at the top. Too long: the
lede loses sentences (never below one). Too short: Romy adds what the sources do not say
(the dossier's first ``uncertainties`` line) — content, never padding.

**The dictée** is the shortest spoken fact (decision 3). It is graded by the journey's own
dictation grader (:func:`app.services.journey_learning.evaluate_dictation`) through the
adapter :func:`grade_dictee`, which wraps the line in a ``RecallTask`` of type
``dictation`` — the same folding (case, punctuation, quotes, apostrophes) and the same
three verdicts (met / accents only / not yet). The target is a radio placeholder, so the
grade is never evidence for a word; it schedules nothing.

**The clips** reuse ``line_audio_clips`` (WP-91) with no migration. A line's clip id is
``cast_voices.clip_id_for(voice, text)`` — a digest of the voice and the exact words, so
``(dossier_id, band, line_index)`` determines it through the text it produces — and the
row's ``model`` column holds the speech spec (model, instructions version, the band's
pace). A row belongs to the learner who heard it (the ``GET
/daily-journeys/line-audio/{clip_id}`` route serves only the caller's rows); a second
learner gets a byte copy of the first learner's row without a call (as WP-91 does), so a
bulletin costs once per story per band and pace. Synthesis goes only through
``episode_audio.speak_text`` (the ``tts`` argument; tests pass a fake), and each paid line
writes the WP-91 priced pilot row (surface ``revue_radio``).

**Silence is a state** (WP-32's rule): if any line cannot be spoken the bulletin is
``audio="unavailable"`` with no clip urls, and the page shows the text at once.

**Heard** is a ``pilot_events`` row (``revue_radio_heard``, entity = the dossier id) per
learner: the ledger the digest already reads, so no table and no migration. The rotation
(:func:`radio_week`) offers the week's live dossiers the learner has not heard, then the
week's evergreens; one bulletin a day (a learner who heard one today gets no chip until
tomorrow, though ``/radio`` still plays).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.line_audio import LineAudioClip
from app.db.models.pilot_event import PilotEvent
from app.services.cast_voices import (
    FALLBACK_SPEECH_MODEL,
    LINE_AUDIO_PATH_PREFIX,
    clip_id_for,
    voice_for_character,
)
from app.services.episode_audio import Synthesizer, speak_text, spec_for
from app.services.pilot_events import PilotEventService
from app.services.revue import knowledge, policy
from app.services.revue.dossier import Claim, EditorialDossier, parse_week

PARIS = ZoneInfo("Europe/Paris")

#: The spoken rate the estimate assumes (French news read for learners).
CHARS_PER_SECOND = 14.0
#: The breath between two lines.
LINE_GAP_SECONDS = 0.6
#: «A jingle of nothing»: silence and the paper texture before Romy speaks.
JINGLE_SECONDS = 1.5
#: The bulletin's target length (spec §3.1).
MIN_SECONDS = 45.0
MAX_SECONDS = 60.0
#: The lede never shrinks below this many words while fitting (one sentence stays anyway).
MIN_LEDE_WORDS = 10
#: Three claims (spec §3.1).
CLAIMS_SPOKEN = 3

ROMY_ID = "romy_tremblay"
#: When a topic names no guest.
DEFAULT_GUEST_ID = "margaux_barman"

#: The pilot-ledger event a learner's «C'est entendu» writes. Free.
HEARD_EVENT_TYPE = "revue_radio_heard"
#: The ``surface`` on the WP-91 priced row of a line synthesized for the radio.
AUDIO_SURFACE = "revue_radio"

LineRole = str  # "lede" | "claim" | "uncertainty" | "guest" | "signoff"
TtsFn = Callable[..., Any]


# ---------------------------------------------------------------------------
# The script
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BulletinLine:
    index: int
    speaker: str
    role: LineRole
    text_fr: str
    claim_id: str | None = None
    claim_kind: str | None = None
    clip_url: str | None = None

    @property
    def voice(self) -> str:
        return voice_for_character(self.speaker)

    @property
    def clip_id(self) -> str:
        return clip_id_for(self.voice, self.text_fr)


@dataclass
class Bulletin:
    dossier_id: str
    title_fr: str
    topic: str
    band: str
    week: str
    guest_id: str
    lines: list[BulletinLine]
    seconds: float
    dictee_index: int
    #: ``ready`` (every line has a clip), ``unavailable`` (none has), ``text_only`` (not asked).
    audio: str = "text_only"
    #: Why ``audio`` is ``unavailable``: ``spend_cap`` (the learner's daily spend cap,
    #: checked before any line is synthesised) or ``tts_failed``; ``None`` otherwise.
    audio_reason: str | None = None
    synthesized_lines: int = 0
    cached_lines: int = 0
    cost_usd: float = 0.0
    voices: list[str] = field(default_factory=list)

    @property
    def dictee(self) -> BulletinLine:
        return self.lines[self.dictee_index]


_SENTENCE = re.compile(r"[^.!?…]+(?:[.!?…]+|$)")
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
#: Words that may lose their capital after «D'après X, …» (never a proper noun).
_LOWERABLE = frozenset(
    "le la les l un une des du de d il elle ils elles on ce cette ces cela ça c "
    "leur leurs son sa ses mon ma mes notre nos pour avec dans en au aux selon "
    "plus moins beaucoup certains certaines tout tous toute toutes chaque".split()
)


_OPENER = re.compile(r"^(pour|selon)\s+([^,]{2,120}),\s*(.+)$", re.IGNORECASE | re.DOTALL)
_DAPRES = re.compile(r"\bd'après\b", re.IGNORECASE)
_SELON = re.compile(r"\bselon\b")


def _words(text: str) -> int:
    return len(_WORD.findall(text or ""))


def _sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in _SENTENCE.findall(text or "") if chunk.strip()]


def lede_for(dossier: EditorialDossier, limit_words: int) -> str:
    """Whole sentences of ``summary_fr`` up to ``limit_words`` (the first one always)."""

    kept: list[str] = []
    total = 0
    for sentence in _sentences(dossier.summary_fr):
        count = _words(sentence)
        if kept and total + count > limit_words:
            break
        kept.append(sentence)
        total += count
    return " ".join(kept)


def _lower_first(text: str) -> str:
    head, _, rest = text.partition(" ")
    bare = re.sub(r"['’].*$", "", head).lower()
    if head[:1].isupper() and bare in _LOWERABLE:
        return head[:1].lower() + head[1:] + (" " + rest if rest else "")
    return text


def spoken_claim(claim: Claim) -> str:
    """A claim as Romy says it: a fact as reported; a view with its source said aloud.

    Most authored views already name their source; Romy says it with «d'après»:
    «Pour ses critiques, le Tour…» → «D'après ses critiques, le Tour…»; a mid-sentence
    «selon X» becomes «d'après X»; a view that names no source is prefixed with its
    ``attributed_to``: «D'après la Ville de Paris, c'est un changement d'échelle…».
    """

    text = " ".join(claim.fr.split())
    if claim.kind == "fact" or not (claim.attributed_to or "").strip():
        return text
    opener = _OPENER.match(text)
    if opener:
        return f"D'après {opener.group(2)}, {opener.group(3)}"
    if _DAPRES.search(text):
        return text
    if _SELON.search(text):
        return _SELON.sub("d'après", text, count=1)
    return f"D'après {' '.join(str(claim.attributed_to).split())}, {_lower_first(text)}"


def pick_claims(dossier: EditorialDossier, band: str) -> list[Claim]:
    """Three claims in the dossier's order: facts only at A1, else two facts and one view."""

    facts = [claim for claim in dossier.claims if claim.kind == "fact"]
    views = [claim for claim in dossier.claims if claim.kind != "fact"]
    if policy.normalize_band(band) == "A1" or not views:
        chosen = (facts + views)[:CLAIMS_SPOKEN]
    else:
        chosen = facts[: CLAIMS_SPOKEN - 1] + views[:1]
        if len(chosen) < CLAIMS_SPOKEN:
            spare = [claim for claim in dossier.claims if claim not in chosen]
            chosen += spare[: CLAIMS_SPOKEN - len(chosen)]
    order = {claim.id: index for index, claim in enumerate(dossier.claims)}
    return sorted(chosen, key=lambda claim: order[claim.id])


def guest_for(dossier: EditorialDossier) -> str:
    """The topic's first guest (``policy.guests_for``), as the Revue's stage would bring."""

    guests = policy.guests_for(dossier.topic)
    return guests[0]["id"] if guests else DEFAULT_GUEST_ID


def signoff_for(week: str) -> str:
    _, number = parse_week(week)
    return f"C'était Le Papier, semaine {number}."


def estimate_seconds(texts: list[str]) -> float:
    """Spoken characters at :data:`CHARS_PER_SECOND`, a breath between lines, the jingle."""

    chars = sum(len(text) for text in texts)
    gaps = max(0, len(texts) - 1) * LINE_GAP_SECONDS
    return round(JINGLE_SECONDS + chars / CHARS_PER_SECOND + gaps, 1)


def _assemble(
    dossier: EditorialDossier,
    claims: list[Claim],
    *,
    lede: str,
    uncertainties: list[str],
    guest_id: str,
    guest_text: str,
    week: str,
) -> list[BulletinLine]:
    rows: list[tuple[str, str, str, str | None, str | None]] = [(ROMY_ID, "lede", lede, None, None)]
    rows += [(ROMY_ID, "claim", spoken_claim(claim), claim.id, claim.kind) for claim in claims]
    rows += [(ROMY_ID, "uncertainty", text, None, None) for text in uncertainties]
    rows.append((guest_id, "guest", guest_text, None, None))
    rows.append((ROMY_ID, "signoff", signoff_for(week), None, None))
    return [
        BulletinLine(index=i, speaker=s, role=r, text_fr=t, claim_id=c, claim_kind=k)
        for i, (s, r, t, c, k) in enumerate(rows)
        if t.strip()
    ]


def dictee_index(lines: list[BulletinLine]) -> int:
    """The shortest spoken fact (decision 3); the shortest claim if no fact is spoken."""

    claims = [line for line in lines if line.role == "claim"]
    facts = [line for line in claims if line.claim_kind == "fact"] or claims
    return min(facts, key=lambda line: (len(line.text_fr), line.index)).index


def bulletin_script(
    dossier: EditorialDossier,
    band: str,
    *,
    week: str | None = None,
    guest_line: str | None = None,
) -> Bulletin:
    """The bulletin's words and timing, without audio (pure: no database, no call)."""

    band = policy.normalize_band(band)
    week = week or current_week()
    claims = pick_claims(dossier, band)
    guest_id = guest_for(dossier)
    guest_text = " ".join((guest_line or knowledge.authored_guest_line(guest_id, dossier.topic)).split())
    limit = int(policy.band_support(band)["reading_target_words"]) // 2

    def build(limit_words: int, uncertainties: list[str]) -> list[BulletinLine]:
        return _assemble(
            dossier,
            claims,
            lede=lede_for(dossier, limit_words),
            uncertainties=uncertainties,
            guest_id=guest_id,
            guest_text=guest_text,
            week=week,
        )

    def seconds(rows: list[BulletinLine]) -> float:
        return estimate_seconds([line.text_fr for line in rows])

    said: list[str] = []
    lines = build(limit, said)
    # Too long: the lede gives up sentences first (it is the part the claims repeat).
    while seconds(lines) > MAX_SECONDS and limit > MIN_LEDE_WORDS:
        limit -= 5
        lines = build(limit, said)
    # Too short: the lede takes back sentences, up to the band's whole reading target...
    full = int(policy.band_support(band)["reading_target_words"])
    while seconds(lines) < MIN_SECONDS and limit < full:
        candidate = build(limit + 5, said)
        if seconds(candidate) > MAX_SECONDS:
            break
        limit += 5
        lines = candidate
    # ...then Romy says what the sources do not know — never silence or filler.
    for extra in dossier.uncertainties:
        if seconds(lines) >= MIN_SECONDS:
            break
        candidate = build(limit, [*said, extra])
        if seconds(candidate) <= MAX_SECONDS:
            said.append(extra)
            lines = candidate
    texts = [line.text_fr for line in lines]
    return Bulletin(
        dossier_id=dossier.id,
        title_fr=dossier.title_fr,
        topic=dossier.topic,
        band=band,
        week=week,
        guest_id=guest_id,
        lines=lines,
        seconds=estimate_seconds(texts),
        dictee_index=dictee_index(lines),
        voices=sorted({line.voice for line in lines}),
    )


# ---------------------------------------------------------------------------
# The voices: line_audio_clips, keyed by the line's words and the speech spec
# ---------------------------------------------------------------------------


def _model() -> str:
    return str(settings.FEUILLETON_AUDIO_TTS_MODEL)


def _cache_keys(speaker: str, band: str) -> tuple[str, ...]:
    keys = [spec_for(speaker, band, model=_model()).cache_key]
    fallback = spec_for(speaker, band, model=FALLBACK_SPEECH_MODEL).cache_key
    if fallback not in keys:
        keys.append(fallback)
    return tuple(keys)


def _find(db: Session, *, clip_id: str, keys: tuple[str, ...], owner_id: uuid.UUID | None) -> LineAudioClip | None:
    query = select(LineAudioClip).where(LineAudioClip.clip_id == clip_id, LineAudioClip.model.in_(keys))
    if owner_id is not None:
        query = query.where(LineAudioClip.user_id == owner_id)
    rows = list(db.scalars(query.limit(8)))
    for key in keys:
        hit = next((row for row in rows if row.model == key), None)
        if hit is not None:
            return hit
    return None


def _default_synthesizer() -> Synthesizer:
    from app.services.llm_service import LLMService

    return LLMService()


def _speak_line(
    db: Session,
    *,
    owner_id: uuid.UUID,
    line: BulletinLine,
    band: str,
    tts: TtsFn,
    provider: Synthesizer | None,
) -> tuple[LineAudioClip | None, bool, Synthesizer | None]:
    """The learner's clip for one line: theirs, a copy of anyone's, or spoken now.

    Returns ``(clip, synthesized, provider)``; the provider is built on the first call only.
    """

    keys = _cache_keys(line.speaker, band)
    mine = _find(db, clip_id=line.clip_id, keys=keys, owner_id=owner_id)
    if mine is not None:
        return mine, False, provider
    clip = LineAudioClip(
        user_id=owner_id,
        clip_id=line.clip_id,
        voice=line.voice,
        model=keys[0],
        character_id=line.speaker[:80],
        text_fr=line.text_fr,
        char_count=len(line.text_fr),
        content_type="audio/mpeg",
    )
    shared = _find(db, clip_id=line.clip_id, keys=keys, owner_id=None)
    if shared is not None:
        clip.audio = bytes(shared.audio)
        clip.model = shared.model
        clip.content_type = shared.content_type or "audio/mpeg"
        db.add(clip)
        db.flush()
        return clip, False, provider
    try:
        if provider is None:
            provider = _default_synthesizer()
        spoken = tts(
            provider,
            text=line.text_fr,
            voice=line.voice,
            character_id=line.speaker,
            band=band,
            model=_model(),
        )
    except Exception as exc:  # noqa: BLE001 - a silent line silences the bulletin, never the page
        logger.warning("revue radio: line could not be spoken ({})", exc)
        return None, False, provider
    if not spoken.audio:
        return None, False, provider
    clip.audio = bytes(spoken.audio)
    clip.model = spoken.spec.cache_key
    db.add(clip)
    db.flush()
    from app.services.line_audio import record_line_audio_cost

    record_line_audio_cost(db, user_id=owner_id, clip=clip, surface=AUDIO_SURFACE, step_id=None)
    return clip, True, provider


def _line_cost(clip: LineAudioClip) -> float:
    from app.services.cast_voices import model_of_cache_key
    from app.services.episode_audio import estimate_synthesis_cost_usd
    from app.services.llm_service import estimate_tts_cost_usd

    used = model_of_cache_key(clip.model)
    if used == _model():
        return estimate_synthesis_cost_usd(int(clip.char_count))
    return estimate_tts_cost_usd(used, int(clip.char_count))


def over_spend_cap(db: Session, owner_id: uuid.UUID, *, user: Any = None) -> bool:
    """The learner's daily spend cap, read the way the line-audio route reads it
    (``line_audio._cap_near``: at :data:`~app.services.line_audio.CAP_NEAR_SHARE` of
    ``USER_DAILY_SPEND_CAP_USD``, the learner's own day). A cap of 0 is off; a ledger
    read that fails never silences the bulletin."""

    from app.services.line_audio import CAP_NEAR_SHARE
    from app.services.spend_guard import daily_cap_usd, learner_zone, spend_today_usd

    cap = daily_cap_usd()
    if cap <= 0:
        return False
    try:
        if user is None:
            from app.db.models.user import User

            user = db.get(User, owner_id)
        spent = spend_today_usd(db, owner_id, zone=learner_zone(user))
    except Exception as exc:  # noqa: BLE001 - a ledger read never costs the bulletin
        logger.warning("revue radio: spend ledger unreadable ({})", exc)
        return False
    return spent >= cap * CAP_NEAR_SHARE


def _cached_everywhere(db: Session, owner_id: uuid.UUID, lines: list[BulletinLine], band: str) -> bool:
    """Would every line be served from a clip (the learner's or anyone's) — no TTS call?"""

    for line in lines:
        keys = _cache_keys(line.speaker, band)
        if _find(db, clip_id=line.clip_id, keys=keys, owner_id=owner_id) is None and _find(
            db, clip_id=line.clip_id, keys=keys, owner_id=None
        ) is None:
            return False
    return True


def bulletin_for(
    db: Session,
    dossier: EditorialDossier,
    band: str,
    *,
    guest_line: str | None = None,
    tts: TtsFn = speak_text,
    owner_id: uuid.UUID | None = None,
    provider: Synthesizer | None = None,
    week: str | None = None,
    user: Any = None,
    respect_cap: bool = True,
) -> Bulletin:
    """The bulletin, spoken for ``owner_id`` (the learner who will hear it).

    Without an owner the script comes back ``text_only`` (a clip row needs one). Every
    line is cached (see the module docstring), so a second call makes no TTS call.

    Before anything is synthesised, the learner's daily spend cap is checked
    (:func:`over_spend_cap`); over it, the bulletin is ``unavailable`` with
    ``audio_reason="spend_cap"`` and the page shows the text. A bulletin served
    wholly from cached clips costs nothing and is never capped.
    """

    bulletin = bulletin_script(dossier, band, week=week, guest_line=guest_line)
    if owner_id is None:
        return bulletin
    if (
        respect_cap
        and not _cached_everywhere(db, owner_id, bulletin.lines, bulletin.band)
        and over_spend_cap(db, owner_id, user=user)
    ):
        bulletin.audio = "unavailable"
        bulletin.audio_reason = "spend_cap"
        return bulletin
    clips: list[LineAudioClip] = []
    for line in bulletin.lines:
        clip, synthesized, provider = _speak_line(
            db, owner_id=owner_id, line=line, band=bulletin.band, tts=tts, provider=provider
        )
        if clip is None:
            bulletin.audio = "unavailable"
            bulletin.audio_reason = "tts_failed"
            return bulletin
        clips.append(clip)
        if synthesized:
            bulletin.synthesized_lines += 1
            bulletin.cost_usd = round(bulletin.cost_usd + _line_cost(clip), 6)
        else:
            bulletin.cached_lines += 1
    bulletin.lines = [
        BulletinLine(
            index=line.index,
            speaker=line.speaker,
            role=line.role,
            text_fr=line.text_fr,
            claim_id=line.claim_id,
            claim_kind=line.claim_kind,
            clip_url=LINE_AUDIO_PATH_PREFIX + clip.clip_id,
        )
        for line, clip in zip(bulletin.lines, clips, strict=True)
    ]
    bulletin.audio = "ready"
    db.flush()  # the last line's priced row too
    return bulletin


# ---------------------------------------------------------------------------
# The dictée: the journey's dictation grader, through a RecallTask adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DicteeGrade:
    outcome: str  # "met" | "partially_met" | "not_yet"
    expected_fr: str
    note: str | None


def grade_dictee(expected_fr: str, answer_text: str, *, language: str = "en") -> DicteeGrade:
    """Grade a typed dictée with :func:`journey_learning.evaluate_dictation`.

    The grader takes a ``RecallTask``; this adapter builds one of type ``dictation``
    whose solution is the line, with the planner's own instruction in the learner's
    language (which is how the grader picks the note's language) and a radio
    placeholder target — so the line never counts as evidence for a word.
    """

    from app.services.journey_contracts import (
        AssistanceLevel,
        AttemptAnswer,
        InputMode,
        RecallTask,
        TargetKind,
        TargetRef,
    )
    from app.services.journey_learning import evaluate_dictation
    from app.services.journey_planner import _DICTATION_INSTRUCTION

    task = RecallTask(
        task_type="dictation",
        instruction_native=_DICTATION_INSTRUCTION.get(language, _DICTATION_INSTRUCTION["en"]),
        prompt_fr=None,
        options=[],
        target=TargetRef(kind=TargetKind.VOCABULARY, id="revue-radio", label_fr=""),
        optional=False,
        solution_fr=expected_fr,
    )
    result = evaluate_dictation(
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=answer_text or ""),
        assistance=AssistanceLevel.NONE,
    )
    return DicteeGrade(
        outcome=str(result.outcome),
        expected_fr=expected_fr,
        note=result.correction.note_native if result.correction is not None else None,
    )


# ---------------------------------------------------------------------------
# The rotation and «C'est entendu»
# ---------------------------------------------------------------------------


def current_week(now: datetime | None = None) -> str:
    local = (now or datetime.now(UTC)).astimezone(PARIS)
    year, number, _ = local.isocalendar()
    return f"{year}-W{number:02d}"


def week_dossiers(week: str) -> tuple[list[EditorialDossier], list[EditorialDossier]]:
    """``(live, evergreens)`` for ``week``: the authored/built week, then its evergreens."""

    from app.services.revue import weekly
    from app.services.revue.evergreen import evergreens_for_week

    try:
        live = weekly.load_week(week)
    except Exception as exc:  # noqa: BLE001 - a broken week still has its evergreens
        logger.warning("revue radio: week {} unreadable ({})", week, exc)
        live = []
    return live, evergreens_for_week(week)


def find_dossier(dossier_id: str, week: str | None = None) -> EditorialDossier | None:
    """A dossier of the week (live or evergreen), or any evergreen by id."""

    from app.services.revue.evergreen import load_evergreens

    live, evergreens = week_dossiers(week or current_week())
    for dossier in [*live, *evergreens, *load_evergreens()]:
        if dossier.id == dossier_id:
            return dossier
    return None


def heard_events(db: Session, user_id: uuid.UUID) -> list[PilotEvent]:
    return list(
        db.scalars(
            select(PilotEvent)
            .where(PilotEvent.user_id == user_id, PilotEvent.event_type == HEARD_EVENT_TYPE)
            .order_by(PilotEvent.occurred_at.desc())
        )
    )


def _paris_date(moment: datetime) -> Any:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(PARIS).date()


@dataclass
class RadioWeek:
    week: str
    #: The next bulletin to hear (the chip's target), or ``None`` when the week is heard.
    current: EditorialDossier | None
    queue: list[EditorialDossier]
    heard: list[str]
    heard_today: bool

    @property
    def chip(self) -> bool:
        """La Une's chip: an unheard bulletin, and none heard today (one a day)."""

        return self.current is not None and not self.heard_today


def radio_week(db: Session, user_id: uuid.UUID, *, week: str | None = None, now: datetime | None = None) -> RadioWeek:
    """The rotation: the week's live dossiers not yet heard, then the week's evergreens."""

    week = week or current_week(now)
    events = heard_events(db, user_id)
    heard = {str(event.entity_id) for event in events if event.entity_id}
    today = _paris_date(now or datetime.now(UTC))
    heard_today = any(_paris_date(event.occurred_at) == today for event in events if event.occurred_at)
    live, evergreens = week_dossiers(week)
    queue = [dossier for dossier in live if dossier.id not in heard]
    queue += [dossier for dossier in evergreens if dossier.id not in heard and all(d.id != dossier.id for d in queue)]
    return RadioWeek(
        week=week,
        current=queue[0] if queue else None,
        queue=queue,
        heard=sorted(heard),
        heard_today=heard_today,
    )


def mark_heard(
    db: Session,
    user_id: uuid.UUID,
    dossier: EditorialDossier,
    *,
    band: str,
    week: str,
    dictee_outcome: str | None = None,
    now: datetime | None = None,
) -> None:
    """«C'est entendu»: one free ledger row; the rotation moves on."""

    PilotEventService(db).record(
        HEARD_EVENT_TYPE,
        user_id=user_id,
        entity_type="revue_dossier",
        entity_id=dossier.id,
        payload={
            "week": week,
            "band": policy.normalize_band(band),
            "evergreen": bool(dossier.evergreen),
            "dictee": dictee_outcome,
        },
        occurred_at=now,
    )


def learner_band(user: Any) -> str:
    from app.services.chrome_language import level_band

    return policy.normalize_band(level_band(getattr(user, "cefr_estimate", None)) or "A1")


__all__ = [
    "AUDIO_SURFACE",
    "Bulletin",
    "BulletinLine",
    "DicteeGrade",
    "HEARD_EVENT_TYPE",
    "RadioWeek",
    "bulletin_for",
    "bulletin_script",
    "estimate_seconds",
    "find_dossier",
    "grade_dictee",
    "learner_band",
    "mark_heard",
    "radio_week",
    "spoken_claim",
]
