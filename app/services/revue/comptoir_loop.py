"""«Au comptoir»: the learner's loop (WP-119, owner 2026-10-19).

Five screens — read, the takes, the intox, the learner's opinion, the page — played from the
takes the desk wrote (``comptoir.py``) and snapshotted on the session's first ``choice`` event
(``mode="comptoir"``). The server owns the state: every act is one ``comptoir`` event
(``{act, ...}``) in the session's append-only log, the current step is derived from the acts
by replay (:func:`step_of`), so a resume lands on the right screen and an act out of order is
answered with a 409 and the same view.

Acts, in order (spec §3):

- ``vote {value}``: the gut answer to the question (pour | contre | nuance); may change until
  the opinion is given.
- ``react {guest_id, value}``: agree | disagree with a take; the takes are revealed one at a
  time, so a guest is reacted to only after the ones before them.
- ``intox_who {guest_id}``: who said the false thing — two tries at most, then the answer
  is revealed. Only when the takes have an intox at the learner's band.
- ``intox_fix {value | text}``: the true value — a pick of two at A1–A2, a sentence at B1+.
- ``opinion {value: stance, reason_index | text, mode}``: A1 builds «Je suis pour, parce
  que …» from tiles (no model call); A2 writes the reason after a frame, B1+ free text — one
  model call (``provider.comptoir_edit``) for Romy's edit and the reply, checked, with the
  learner's own text and the desk's reply as the fallback. A second submit returns the first.
- ``comeback {index | text}``: the learner's answer to the reply (chips at A1–A2, one free
  line at B1+), then the guest's authored last word.

The close (:func:`close_comptoir`) makes no model call: «La page», the dispatch, the
``opinion`` artifact, the vignette, the kept words, the memories, the cost row.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.schemas.revue import (
    RvClosedWord,
    RvClosing,
    RvComptoirCast,
    RvComptoirComeback,
    RvComptoirFix,
    RvComptoirIntox,
    RvComptoirKit,
    RvComptoirNote,
    RvComptoirOpinion,
    RvComptoirPage,
    RvComptoirPageIntox,
    RvComptoirQuote,
    RvComptoirRead,
    RvComptoirReply,
    RvComptoirRequest,
    RvComptoirText,
    RvComptoirView,
    RvComptoirVotes,
    RvDispatch,
    RvKept,
)
from app.services.revue import comptoir, voice
from app.services.revue.dossier import (
    COMPTOIR_STANCES,
    ComptoirIntox,
    ComptoirTakes,
    ComptoirText,
    EditorialDossier,
    comptoir_band,
)
from app.services.revue.encounter import (
    Loaded,
    RevueError,
    _closing_of,
    _contains_word,
    _gloss_language_of,
    _source,
    colophon_for,
    contribution_spans,
    dateline,
    meter,
    rv_claim,
    session_view,
    word_outcomes,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.services.revue.encounter import RevueEncounter

COMPTOIR_EDIT_PROMPT_VERSION = "comptoir-edit-v1"

STEPS: tuple[str, ...] = ("read", "takes", "intox", "opinion", "page")
REACTIONS: tuple[str, ...] = ("agree", "disagree")
MAX_INTOX_TRIES = 2
EDIT_MAX_RATIO = 1.6
NOTES_MAX = 2
NOTE_WHY_MAX_WORDS = 12
COMEBACK_MAX_CHARS = 200

ROMY_CLOSE_LINE = "Merci ! Ta voix est dans le micro-trottoir."
KICKER = "Le micro-trottoir de Romy"
#: A1's first tile, per side; the sentence goes on «, parce que …».
A1_OPENERS: dict[str, str] = {"pour": "Je suis pour", "contre": "Je suis contre", "nuance": "Ça dépend"}
#: How «La page» and the memories say a side.
STANCE_FR: dict[str, str] = {"pour": "pour", "contre": "contre", "nuance": "partagé"}

_t = comptoir._t  # noqa: SLF001 - the desk's own constructor for authored lines

#: The comeback chips at A1–A2: two authored, then the desk's own for that side.
COMEBACK_CHIPS: tuple[ComptoirText, ...] = (
    _t("Pas du tout !", "Not at all!", "Überhaupt nicht!"),
    _t("Un peu…", "A little…", "Ein bisschen…"),
)
#: The guest's last word, by the kind of comeback (index of the chip; ``"free"`` for B1+).
LAST_WORDS: dict[Any, ComptoirText] = {
    0: _t("Ah bon ? On en reparle demain !", "Really? We'll talk about it again tomorrow!",
          "Ach ja? Darüber reden wir morgen weiter!"),
    1: _t("Ha ! Je le savais.", "Ha! I knew it.", "Ha! Ich wusste es."),
    2: _t("Touché.", "Touché.", "Touché."),
    "free": _t("Touché. On en reparle demain !", "Touché. We'll talk about it again tomorrow!",
               "Touché. Darüber reden wir morgen weiter!"),
}


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def session_mode(state: Any) -> str:
    """``"comptoir"`` when the session's first dossier choice says so, else ``"chat"``."""

    for event in state.events:
        if event.kind == "choice" and event.payload.get("kind") == "dossier":
            return "comptoir" if event.payload.get("mode") == "comptoir" else "chat"
    return "chat"


class Acts:
    """The learner's acts so far, replayed from the ``comptoir`` events."""

    def __init__(self, state: Any) -> None:
        self.vote: str | None = None
        self.reactions: dict[str, str] = {}
        self.tries: list[str] = []
        self.found = False
        self.fix: dict[str, Any] | None = None
        self.opinion: dict[str, Any] | None = None
        self.comeback: dict[str, Any] | None = None
        for event in state.events:
            if event.kind != "comptoir":
                continue
            payload = event.payload
            act = payload.get("act")
            if act == "vote":
                self.vote = str(payload.get("value"))
            elif act == "react":
                self.reactions[str(payload.get("guest_id"))] = str(payload.get("value"))
            elif act == "intox_who":
                self.tries.append(str(payload.get("guest_id")))
                self.found = self.found or bool(payload.get("correct"))
            elif act == "intox_fix" and self.fix is None:
                self.fix = dict(payload)
            elif act == "opinion" and self.opinion is None:
                self.opinion = dict(payload)
            elif act == "comeback" and self.comeback is None:
                self.comeback = dict(payload)

    @property
    def who_resolved(self) -> bool:
        return self.found or len(self.tries) >= MAX_INTOX_TRIES


def takes_of(loaded: Loaded) -> ComptoirTakes:
    takes = loaded.dossier.comptoir
    if takes is None:  # a comptoir session always snapshots its takes; keep the wire total anyway
        raise RevueError(409, "revue_not_comptoir")
    return takes


def band_of(loaded: Loaded) -> str:
    return str(loaded.plan.learner.band)


def intox_of(takes: ComptoirTakes, band: str) -> ComptoirIntox | None:
    return takes.intox_for(band)


def steps_for(takes: ComptoirTakes, band: str) -> list[str]:
    """The dots: five, or four when the learner's band has no intox (spec §6.2)."""

    return [step for step in STEPS if step != "intox" or intox_of(takes, band) is not None]


def step_of(takes: ComptoirTakes, band: str, acts: Acts, *, closed: bool) -> str:
    if closed:
        return "page"
    if acts.vote is None:
        return "read"
    if len(acts.reactions) < len(takes.guests):
        return "takes"
    if intox_of(takes, band) is not None and acts.fix is None:
        return "intox"
    if acts.opinion is None or acts.comeback is None:
        return "opinion"
    return "page"


# ---------------------------------------------------------------------------
# Texts
# ---------------------------------------------------------------------------


def _ct(text: ComptoirText | None, language: str) -> RvComptoirText:
    if text is None:
        return RvComptoirText(fr="")
    return RvComptoirText(fr=text.fr, tr=text.translation(language) if language != "fr" else None)


def elide_parce_que(reason: str) -> str:
    """«parce que» + ``reason``, elided before a vowel («parce qu'il»)."""

    reason = reason.strip()
    if re.match(r"[aeiouyàâäéèêëîïôöûü]", reason, flags=re.IGNORECASE):
        return f"parce qu'{reason}"
    return f"parce que {reason}"


def a1_sentence(stance: str, reason: str) -> str:
    """A1's sentence, correct by construction: «Je suis pour, parce que sa voix est belle.»"""

    body = re.sub(r"[\s.!…]+$", "", reason.strip())
    return voice.french_typography(f"{A1_OPENERS[stance]}, {elide_parce_que(body)}.")


def _sentence_end(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if text and not re.search(r"[.!?…»]$", text):
        text += "."
    return text


def a2_sentence(frame: str, text: str) -> str:
    """The frame and the learner's reason; a learner who wrote the frame too keeps theirs."""

    text = re.sub(r"\s+", " ", text).strip()
    frame = re.sub(r"\s+", " ", frame).strip()
    if comptoir.ci(text).startswith(comptoir.ci(frame)[:12]):
        return _sentence_end(text)
    return _sentence_end(f"{frame} {text}")


def compact_quote(take: str, planted: str | None) -> str:
    """What the intox step shows of a take: the sentence with the false detail for the liar,
    else the first sentence of four words or more (else the whole take); a sentence under six
    words takes the next one along («Sept jours sur sept ? Mon cher, c'est trop de bruit.»)."""

    rows = comptoir.sentences(take)
    if not rows:
        return take
    index = next((i for i, s in enumerate(rows) if planted and comptoir.contains(s, planted)), None)
    if index is None:
        index = next((i for i, s in enumerate(rows) if comptoir.word_count(s) >= 4), 0)
    quote = rows[index]
    if comptoir.word_count(quote) < 6 and index + 1 < len(rows):
        quote = f"{quote} {rows[index + 1]}"
    return quote


def fix_line(name: str, intox: ComptoirIntox) -> str:
    return voice.french_typography(f"C'est faux, {name} ! C'est {intox.right_fr}, pas {intox.wrong_fr}.")


def fix_prefill(name: str, intox: ComptoirIntox) -> str:
    return voice.french_typography(f"C'est faux, {name} ! C'est …, pas {intox.wrong_fr}.")


def options_for(intox: ComptoirIntox, seed: str) -> list[str]:
    """The A1–A2 pick: the true value and the distractor, in a per-session order."""

    flip = hashlib.sha256(seed.encode("utf-8")).digest()[0] % 2 == 1
    pair = [intox.right_fr, intox.distractor_fr]
    return pair[::-1] if flip else pair


def grade_fix(intox: ComptoirIntox, *, value: str | None = None, text: str | None = None) -> bool:
    """A pick is right when it is ``right_fr``; a sentence when the part before its «, pas …»
    carries the true value (numbers digit-only, else the words, case and accents folded)."""

    if value is not None:
        return comptoir.ci(value).strip(" .!") == comptoir.ci(intox.right_fr).strip(" .!")
    head = str(text or "")
    folded = comptoir.ci(head)
    cut = folded.rfind(", pas ")
    if cut < 0:
        cut = folded.rfind(" pas ")
    if cut > 0:
        head = head[:cut]
    right_numbers = comptoir.numbers(intox.right_fr)
    if right_numbers:
        found = comptoir.numbers(head)
        return right_numbers <= found and not (found - right_numbers) & comptoir.numbers(intox.wrong_fr)
    if comptoir.contains(head, intox.right_fr):
        return True
    # the words that tell the true value from the false one («nord» against «sud», «six» against «sept»)
    right, wrong = _value_words(intox.right_fr), _value_words(intox.wrong_fr)
    key = (right - wrong) or right
    said = _value_words(head)
    return bool(key) and key <= said and not ((wrong - right) & said)


_VALUE_STOP = frozenset("le la les l de du des d un une a au aux en dans sur par et c est ce pas".split())


def _value_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", comptoir.ci(text)) if word not in _VALUE_STOP}


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------


def _place(loaded: Loaded) -> Any:
    dossier, plan = loaded.dossier, loaded.plan
    return next((p for p in dossier.places if p.id == plan.stage.place_id), dossier.places[0])


def _claim_view(dossier: EditorialDossier, claim_id: str) -> Any:
    claim = dossier.claims_by_id().get(claim_id)
    return rv_claim(dossier, claim) if claim is not None else None


def comptoir_view(loaded: Loaded) -> RvComptoirView:
    """What the player shows: the current step and only what that step may know (spec §4)."""

    dossier, plan, state, row = loaded.dossier, loaded.plan, loaded.state, loaded.row
    takes = takes_of(loaded)
    band = band_of(loaded)
    language = _gloss_language_of(plan)
    acts = Acts(state)
    step = step_of(takes, band, acts, closed=state.closed)
    order = STEPS.index(step)
    intox = intox_of(takes, band)
    lead = dossier.lead_for(band)

    cast = [
        RvComptoirCast(
            id=guest.id,
            name_fr=comptoir.name_fr(guest.id),
            role_fr=comptoir.role_fr(guest.id),
            stance=guest.stance,
            take=_ct(guest.take.for_band(band), language),
            reaction=acts.reactions.get(guest.id),  # type: ignore[arg-type]
        )
        for guest in takes.guests
    ]
    read = RvComptoirRead(
        dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "),
        lead=RvComptoirText(fr=lead.fr, tr=lead.translation(language) if language != "fr" else None),
        sources=[_source(dossier, s.id) for s in dossier.sources[:1]],
    )

    intox_view = None
    if intox is not None and order >= STEPS.index("intox") and len(acts.reactions) >= len(takes.guests):
        liar = comptoir.name_fr(intox.by)
        resolved = acts.who_resolved
        wrong_tries = [guest for guest in acts.tries if guest != intox.by]
        fix = None
        if acts.fix is not None:
            fix = RvComptoirFix(
                correct=bool(acts.fix.get("correct")),
                answer_fr=str(acts.fix.get("answer_fr") or ""),
                line_fr=fix_line(liar, intox),
                wrong_fr=intox.wrong_fr,
                right_fr=intox.right_fr,
                claim=_claim_view(dossier, intox.claim_id),
                caught=_ct(intox.caught, language),
            )
        lower = band in {"A1", "A2"}
        intox_view = RvComptoirIntox(
            quotes=[
                RvComptoirQuote(cast_id=guest.id, name_fr=comptoir.name_fr(guest.id),
                                role_fr=comptoir.role_fr(guest.id), stance=guest.stance,
                                quote_fr=compact_quote(guest.take.for_band(band).fr,
                                                       intox.wrong_fr if guest.id == intox.by else None))
                for guest in takes.guests
            ],
            tries=acts.tries,
            resolved=resolved,
            found=acts.found if resolved else None,
            by=intox.by if resolved else None,
            hint_claim=_claim_view(dossier, intox.claim_id) if wrong_tries else None,
            ask=_ct(intox.ask, language) if resolved else None,
            options=options_for(intox, str(row.id)) if resolved and lower else [],
            prefill_fr=fix_prefill(liar, intox) if resolved and not lower else None,
            fix=fix,
        )

    kit = None
    if order >= STEPS.index("opinion"):
        kit = RvComptoirKit(
            input="tiles" if band == "A1" else "frame" if band == "A2" else "free",
            phrase=_ct(takes.phrase.for_band(band), language),
            reasons={stance: [_ct(text, language) for text in takes.reasons.get(stance) or []]  # type: ignore[misc]
                     for stance in COMPTOIR_STANCES},
            frames={stance: _ct(takes.frames.get(stance), language) for stance in COMPTOIR_STANCES},  # type: ignore[misc]
            bank=[_ct(text, language) for text in takes.bank] if band == "A2" else [],
            opponents={stance: comptoir.reply_for(takes, stance).by for stance in COMPTOIR_STANCES},  # type: ignore[misc]
        )

    opinion = None
    if acts.opinion is not None:
        stance = str(acts.opinion.get("stance"))
        reply = acts.opinion.get("reply") or {}
        chips: list[RvComptoirText] = []
        if band in {"A1", "A2"}:
            desk = comptoir.reply_for(takes, stance)
            chips = [_ct(text, language) for text in (*COMEBACK_CHIPS, desk.comeback)]
        comeback = None
        if acts.comeback is not None:
            comeback = RvComptoirComeback(
                text_fr=str(acts.comeback.get("text_fr") or ""),
                index=acts.comeback.get("index"),
                last_word=RvComptoirText(fr=str(acts.comeback.get("last_word_fr") or ""),
                                         tr=(acts.comeback.get("last_word_tr") or {}).get(language)),
            )
        opinion = RvComptoirOpinion(
            stance=stance,  # type: ignore[arg-type]
            learner_fr=str(acts.opinion.get("learner_fr") or ""),
            edited_fr=str(acts.opinion.get("edited_fr") or ""),
            notes=[RvComptoirNote(span_fr=str(n.get("span_fr")), why=str(n.get("why")))
                   for n in acts.opinion.get("notes") or [] if isinstance(n, dict)],
            reply=RvComptoirReply(
                by=str(reply.get("by") or ""),
                name_fr=comptoir.name_fr(str(reply.get("by") or "")),
                line=RvComptoirText(fr=str(reply.get("fr") or ""), tr=reply.get(language) if language != "fr" else None),
            ),
            comebacks=chips,
            comeback=comeback,
        )

    return RvComptoirView(
        step=step,  # type: ignore[arg-type]
        steps=steps_for(takes, band),  # type: ignore[arg-type]
        band=comptoir_band(band),  # type: ignore[arg-type]
        question=_ct(takes.question, language),
        read=read,
        cast=cast,
        has_intox=intox is not None,
        vote=acts.vote,  # type: ignore[arg-type]
        intox=intox_view,
        kit=kit,
        opinion=opinion,
    )


# ---------------------------------------------------------------------------
# The acts
# ---------------------------------------------------------------------------


def _out_of_order(step: str, act: str) -> RevueError:
    return RevueError(409, "revue_comptoir_out_of_order", step=step, act=act)


def apply_act(encounter: RevueEncounter, loaded: Loaded, body: RvComptoirRequest) -> str | None:
    """Record one act (or nothing, when it repeats one already recorded); returns an
    ``error_fr`` for an act the learner can fix on the same screen. Raises
    :class:`~app.services.revue.encounter.RevueError` for an act out of order or a bad value."""

    state = loaded.state
    takes = takes_of(loaded)
    band = band_of(loaded)
    acts = Acts(state)
    step = step_of(takes, band, acts, closed=state.closed)
    act = body.act
    if state.closed:
        raise _out_of_order(step, act)
    intox = intox_of(takes, band)
    ids = [guest.id for guest in takes.guests]

    if act == "vote":
        if body.value not in COMPTOIR_STANCES:
            raise RevueError(422, "revue_comptoir_bad_act", act=act)
        if acts.opinion is not None:
            raise _out_of_order(step, act)
        if acts.vote != body.value:
            state.append("comptoir", act="vote", value=body.value)
        return None

    if act == "react":
        if body.guest_id not in ids or body.value not in REACTIONS:
            raise RevueError(422, "revue_comptoir_bad_act", act=act)
        index = ids.index(body.guest_id)
        if acts.vote is None or acts.opinion is not None or any(g not in acts.reactions for g in ids[:index]):
            raise _out_of_order(step, act)
        if acts.reactions.get(body.guest_id) != body.value:
            state.append("comptoir", act="react", guest_id=body.guest_id, value=body.value)
        return None

    if act == "intox_who":
        if body.guest_id not in ids:
            raise RevueError(422, "revue_comptoir_bad_act", act=act)
        if step != "intox" or intox is None or acts.who_resolved:
            raise _out_of_order(step, act)
        state.append("comptoir", act="intox_who", guest_id=body.guest_id, correct=body.guest_id == intox.by,
                     attempt=len(acts.tries) + 1)
        return None

    if act == "intox_fix":
        if acts.fix is not None:
            return None  # the first answer stands
        if step != "intox" or intox is None or not acts.who_resolved:
            raise _out_of_order(step, act)
        if band in {"A1", "A2"}:
            if body.value is None or comptoir.ci(body.value) not in {comptoir.ci(o) for o in options_for(intox, str(loaded.row.id))}:
                raise RevueError(422, "revue_comptoir_bad_act", act=act)
            answer, correct = body.value, grade_fix(intox, value=body.value)
        else:
            text = re.sub(r"\s+", " ", body.text or "").strip()
            if not text or "…" in text:
                return "Complète la phrase : c'est quoi, en vrai ?"
            answer, correct = text, grade_fix(intox, text=text)
            state.append("turn_learner", text_fr=text, mode=body.mode, comptoir="intox_fix")
        state.append("comptoir", act="intox_fix", answer_fr=answer, correct=correct)
        return None

    if act == "opinion":
        if acts.opinion is not None:
            return None  # a double submit returns the stored result
        if acts.vote is None or len(acts.reactions) < len(ids) or (intox is not None and acts.fix is None):
            raise _out_of_order(step, act)
        stance = body.value or acts.vote
        if stance not in COMPTOIR_STANCES:
            raise RevueError(422, "revue_comptoir_bad_act", act=act)
        return _opinion(encounter, loaded, takes, stance=stance, body=body)

    if act == "comeback":
        if acts.comeback is not None:
            return None
        if acts.opinion is None:
            raise _out_of_order(step, act)
        stance = str(acts.opinion.get("stance"))
        desk = comptoir.reply_for(takes, stance)
        if band in {"A1", "A2"}:
            chips = [*COMEBACK_CHIPS, desk.comeback]
            if body.index is None or not 0 <= body.index < len(chips):
                raise RevueError(422, "revue_comptoir_bad_act", act=act)
            text_fr, key = chips[body.index].fr, body.index
        else:
            text_fr = re.sub(r"\s+", " ", body.text or "").strip()[:COMEBACK_MAX_CHARS]
            if not text_fr:
                return "Écris une phrase pour répondre."
            key = "free"
        last = LAST_WORDS[key]
        state.append("turn_learner", text_fr=text_fr, mode=body.mode, comptoir="comeback")
        state.append("comptoir", act="comeback", index=body.index if key != "free" else None, text_fr=text_fr,
                     by=desk.by, last_word_fr=last.fr, last_word_tr={"en": last.en, "de": last.de})
        return None

    raise RevueError(422, "revue_comptoir_bad_act", act=act)


def _opinion(encounter: RevueEncounter, loaded: Loaded, takes: ComptoirTakes, *, stance: str,
             body: RvComptoirRequest) -> str | None:
    state, plan, dossier = loaded.state, loaded.plan, loaded.dossier
    band = band_of(loaded)
    desk_reply = comptoir.reply_for(takes, stance)
    reply = {"by": desk_reply.by, "fr": desk_reply.line.fr, "en": desk_reply.line.en, "de": desk_reply.line.de}
    notes: list[dict[str, str]] = []
    cost = 0.0
    source = "tiles"
    raw = None
    if band == "A1":
        reasons = takes.reasons.get(stance) or comptoir.AUTHORED_REASONS[stance]  # type: ignore[call-overload]
        if body.reason_index is None or not 0 <= body.reason_index < len(reasons):
            if body.text and body.text.strip():
                learner = _sentence_end(body.text)  # an A1 learner who typed: no edit, the desk's reply
            else:
                return "Choisis une raison."
        else:
            learner = a1_sentence(stance, reasons[body.reason_index].fr)
        edited = voice.french_typography(learner)
    else:
        text = re.sub(r"\s+", " ", body.text or "").strip()
        if not comptoir.word_count(text):
            return "Écris ta raison : quelques mots suffisent."
        if band == "A2":
            frame = (takes.frames.get(stance) or comptoir.AUTHORED_FRAMES[stance]).fr  # type: ignore[call-overload]
            learner = a2_sentence(frame, text)
        else:
            learner = _sentence_end(text)
        edited = voice.french_typography(learner)
        source = "fallback"
        edit = getattr(encounter.provider, "comptoir_edit", None)
        if callable(edit):
            language = _gloss_language_of(plan)
            context = edit_context(dossier, takes, band=band, stance=stance, learner_fr=learner,
                                   notes_language=plan.learner.ui_language if language == "fr" else language)
            before = meter(encounter.provider)
            try:
                raw = edit(context)
            except Exception as exc:  # noqa: BLE001 - the learner's text and the desk's reply stand
                logger.bind(session_id=str(loaded.row.id)).warning("revue comptoir: edit failed ({})", exc)
                raw = None
            cost = round(meter(encounter.provider) - before, 6)
        if isinstance(raw, dict):
            checked = check_edit(raw, learner, dossier, takes)
            if checked.get("edited_fr"):
                edited, notes, source = checked["edited_fr"], checked["notes"], "model"
            if checked.get("reply_fr"):
                reply = {"by": desk_reply.by, "fr": checked["reply_fr"], "en": checked.get("reply_en"),
                         "de": checked.get("reply_de")}
    state.append("turn_learner", text_fr=learner, mode=body.mode, comptoir="opinion")
    state.append("comptoir", act="opinion", stance=stance, mode=body.mode, reason_index=body.reason_index,
                 learner_fr=learner, edited_fr=edited, notes=notes, reply=reply, source=source, cost_usd=cost,
                 prompt_version=COMPTOIR_EDIT_PROMPT_VERSION if band != "A1" else None,
                 refused=(raw or {}).get("_problems") if isinstance(raw, dict) else None)
    return None


# ---------------------------------------------------------------------------
# Romy's edit (one model call at A2+)
# ---------------------------------------------------------------------------

COMPTOIR_EDIT_INSTRUCTIONS = """You are Romy Tremblay, a Québécoise journalist at Le Mistral, a Paris café. You are
writing a vox pop («micro-trottoir») for your paper, and a French learner just gave you their opinion on the
question of the day. From INPUT answer with ONE JSON object:
{"edited_fr": str, "notes": [{"span_fr": str, "why": str}], "reply_fr": str, "reply_en": str, "reply_de": str}
RULES
- edited_fr: a light journalist's edit of learner_fr, ready to print: fix grammar, agreement, conjugation,
  spelling, accents, word order, capitals and punctuation. Keep the learner's meaning, side, person («je») and
  words; never add a fact, a number, a name or an idea; never make it much longer. If it is already correct,
  copy it unchanged. At band B2 you may also improve the register and the connectors. If it is not French, put
  the learner's idea into simple French.
- notes: at most two, for the most useful fixes only, none when nothing changed: span_fr is the corrected words
  exactly as they appear in edited_fr; why is a very short reason (at most eight words) written in the language
  notes_language names (en: English, de: German, fr: French).
- reply_fr: what the guest named in INPUT.reply_by says back to the learner, in character (their sheet), to
  «tu», answering what the learner actually said (not a generic line; the guest disagrees with the learner's
  side), plain French at the learner's band, 20 words at most, ending on a question or a jab. No insult, no
  swearing, no number, nothing about the app; nothing that INPUT's facts do not say. French typography: a space
  before ? ! : ;
- reply_en and reply_de: faithful translations of reply_fr."""

COMPTOIR_EDIT_SYSTEM = "You edit learners' French like a kind newspaper editor and write lively in-character replies. Answer with one JSON object only."


def edit_context(dossier: EditorialDossier, takes: ComptoirTakes, *, band: str, stance: str, learner_fr: str,
                 notes_language: str) -> dict[str, Any]:
    reply = comptoir.reply_for(takes, stance)
    guest = takes.guest(reply.by)
    sheet = comptoir.character_sheets().get(reply.by, {})
    return {
        "question_fr": takes.question.fr,
        "band": band,
        "learner_side": stance,
        "learner_fr": learner_fr,
        "notes_language": notes_language,
        "reply_by": {"id": reply.by, "name": comptoir.name_fr(reply.by), **{k: sheet.get(k) for k in
                     ("personality", "speech_pattern", "signature_phrases")}},
        "reply_by_take_fr": guest.take.for_band(band).fr if guest is not None else None,
        "reply_by_side": guest.stance if guest is not None else None,
        "example_reply_fr": reply.line.fr,
        "example_reply_en": reply.line.en,
        "example_reply_de": reply.line.de,
        "facts": [c.fr for c in dossier.claims if c.kind == "fact"],
    }


def check_edit(raw: dict[str, Any], learner_fr: str, dossier: EditorialDossier, takes: ComptoirTakes) -> dict[str, Any]:
    """Romy's edit and the reply, checked (spec §3 step 4): an edit at most 1.6× the
    learner's length with no new number and no app words; a reply of 22 words at most that
    passes the desk's checks. What fails is left out (the caller keeps the fallback)."""

    out: dict[str, Any] = {"_problems": []}
    edited = re.sub(r"\s+", " ", str(raw.get("edited_fr") or "")).strip()
    learner_words = comptoir.word_count(learner_fr)
    problem = None
    if not edited:
        problem = "edit:empty"
    elif comptoir.word_count(edited) > max(4, int(EDIT_MAX_RATIO * learner_words)):
        problem = "edit:too_long"
    elif comptoir.numbers(edited) - comptoir.numbers(learner_fr):
        problem = "edit:new_number"
    elif voice.app_words(edited) or voice.meta_words(edited) or voice.id_leaks(edited):
        problem = "edit:app_words"
    if problem:
        out["_problems"].append(problem)
    else:
        out["edited_fr"] = voice.french_typography(edited)
        notes = []
        for row in raw.get("notes") or []:
            if not isinstance(row, dict) or len(notes) >= NOTES_MAX:
                continue
            span = re.sub(r"\s+", " ", str(row.get("span_fr") or "")).strip(" .")
            why = re.sub(r"\s+", " ", str(row.get("why") or "")).strip()
            if span and why and comptoir.contains(out["edited_fr"], span) and comptoir.word_count(why) <= NOTE_WHY_MAX_WORDS:
                notes.append({"span_fr": span, "why": why})
        out["notes"] = notes if comptoir.ci(out["edited_fr"]) != comptoir.ci(voice.french_typography(learner_fr)) else []
    check = comptoir._Checker(dossier)  # noqa: SLF001 - the desk's own checks
    reply, why = check.text({"fr": raw.get("reply_fr"), "en": raw.get("reply_en"), "de": raw.get("reply_de")},
                            comptoir.REPLY_MAX_WORDS)
    planted = takes.intox.wrong_fr if takes.intox is not None else None
    if reply is None:
        out["_problems"].append(f"reply:{why}")
    elif planted and comptoir.contains(reply.fr, planted):
        out["_problems"].append("reply:intox")
    else:
        out.update({"reply_fr": reply.fr, "reply_en": reply.en, "reply_de": reply.de})
    return out


# ---------------------------------------------------------------------------
# The close: «La page»
# ---------------------------------------------------------------------------


def close_comptoir(encounter: RevueEncounter, loaded: Loaded) -> tuple[Any, RvClosing]:
    """«La page» (spec §3 step 5): no model call. The opinion must be given first."""

    from app.services.revue.carte import keep_papier_words

    row, dossier, plan, state = loaded.row, loaded.dossier, loaded.plan, loaded.state
    existing = _closing_of(state)
    if existing is not None:
        return session_view(loaded), existing
    takes = takes_of(loaded)
    band = band_of(loaded)
    acts = Acts(state)
    if acts.opinion is None:
        raise RevueError(409, "revue_comptoir_out_of_order", step=step_of(takes, band, acts, closed=False),
                            act="close")
    intox = intox_of(takes, band)
    opinion = acts.opinion
    stance = str(opinion.get("stance"))
    edited = str(opinion.get("edited_fr") or opinion.get("learner_fr") or "")
    learner = str(opinion.get("learner_fr") or "")

    lead = dossier.lead_for(band).fr
    standfirst = (comptoir.sentences(lead) or [lead])[0]
    votes = dict.fromkeys(COMPTOIR_STANCES, 0)
    for guest in takes.guests:
        votes[guest.stance] += 1
    votes[stance] += 1
    claim = dossier.claims_by_id().get(intox.claim_id) if intox is not None else None
    page = RvComptoirPage(
        question_fr=takes.question.fr,
        dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "),
        standfirst_fr=standfirst,
        quotes=[RvComptoirQuote(cast_id=g.id, name_fr=comptoir.name_fr(g.id), role_fr=comptoir.role_fr(g.id),
                                stance=g.stance, quote_fr=g.quote.fr) for g in takes.guests],
        mine=RvComptoirQuote(cast_id="user", name_fr="Toi", role_fr="", stance=stance, quote_fr=edited),  # type: ignore[arg-type]
        votes=RvComptoirVotes(**votes),
        intox=RvComptoirPageIntox(by=intox.by, name_fr=comptoir.name_fr(intox.by), wrong_fr=intox.wrong_fr,
                                  right_fr=intox.right_fr,
                                  source_name=_source(dossier, claim.source_id).name if claim else "")
        if intox is not None and acts.fix is not None else None,
        phrase_fr=takes.phrase.for_band(band).fr,
        words=[],
    )

    contribution = contribution_spans(learner, edited)
    state.append("artifact", kind="opinion", text_fr=edited, learner_fr=learner, contribution=contribution,
                 stance=stance)
    shown = list(dossier.facts()[:2])
    if claim is not None and claim not in shown:
        shown.append(claim)
    sources = [_source(dossier, sid) for sid in dict.fromkeys(c.source_id for c in shown)]
    names = list(dict.fromkeys(source.name for source in sources))
    mine_line = f"Toi : « {edited} »"
    dispatch = RvDispatch(
        kicker_fr=KICKER,
        headline_fr=takes.question.fr,
        body_fr=[standfirst, mine_line],
        contribution=[],
        byline_fr="Romy Tremblay, avec toi · d'après " + " et ".join(names) if names else "Romy Tremblay, avec toi",
        sources=sources,
    )
    language = _gloss_language_of(plan)
    learner_texts = " ".join(str(e.payload.get("text_fr") or "") for e in state.events if e.kind == "turn_learner")
    outcomes = word_outcomes(state)
    kept = RvKept(
        words=[
            RvClosedWord(fr=item.fr, gloss=item.gloss.get(language, ""), claim_id=item.claim_id,
                         used=_contains_word(learner_texts, item.fr),
                         outcome=outcomes.get(item.fr.strip().casefold()))
            for item in plan.vocabulary
        ],
        claims=[rv_claim(dossier, c) for c in shown],
    )
    page.words = [word.fr for word in kept.words]
    closing = RvClosing(romy_line_fr=ROMY_CLOSE_LINE, dispatch=dispatch, kept=kept, question_kept_fr=None,
                        colophon_fr=colophon_for(row.week), comptoir_page=page)  # type: ignore[arg-type]
    closing.vignette = encounter._mint_vignette(loaded, kind="opinion", kept_contribution=bool(contribution))  # noqa: SLF001
    keep_papier_words(encounter.db, row, dossier=dossier, plan=plan, state=state, kept=kept)

    state.append("turn_romy", beat="close", role="close", text_fr=ROMY_CLOSE_LINE, cost_usd=0.0)
    state.append("closed", closing=closing.model_dump(mode="json"))
    row.status = "closed"
    row.closed_at = datetime.now(UTC)
    artifact = state.current_artifact
    encounter._remember(loaded, artifact=artifact, kind="opinion")  # noqa: SLF001
    remember_guests(encounter, loaded, takes, stance=stance, edited=edited)
    encounter._record_cost(loaded)  # noqa: SLF001
    encounter._save(loaded)  # noqa: SLF001
    try:  # WP-120 §8: the new pin shows at once
        from app.services.revue import carte as _carte

        _carte.invalidate(row.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("revue: carte invalidate skipped ({})", exc)
    return session_view(loaded), closing


def remember_guests(encounter: RevueEncounter, loaded: Loaded, takes: ComptoirTakes, *, stance: str, edited: str) -> None:
    """Each regular but Romy (hers is the session's own memory) remembers the argument."""

    from app.services.revue import knowledge

    row, dossier = loaded.row, loaded.dossier
    for guest in takes.guests:
        if guest.id == comptoir.ROMY_ID:
            continue
        agree = guest.stance == stance
        content = (f"Au Mistral, on a parlé de « {dossier.title_fr} ». Tu étais {STANCE_FR[stance]}, "
                   f"moi {STANCE_FR[guest.stance]}." + (" On était d'accord." if agree else ""))
        knowledge.remember(encounter.db, user_id=row.user_id, cast_id=guest.id, content=content[:400],
                           scene_id=str(row.id), quote=edited, sentiment="positive" if agree else "neutral")


__all__ = [
    "Acts",
    "COMPTOIR_EDIT_INSTRUCTIONS",
    "a1_sentence",
    "apply_act",
    "close_comptoir",
    "comptoir_view",
    "grade_fix",
    "session_mode",
    "step_of",
    "steps_for",
]

