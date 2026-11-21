"""«Le micro»: the learner's loop (WP-119 «les rubriques», owner 2026-11-21).

Six screens — read, «Prépare tes questions», «L'interview», «Tes notes», «Relis tes
questions», the page — played from the interview the desk wrote (``micro.py``) and
snapshotted on the session's first ``choice`` event (``mode="micro"``). As «Le titre»
(``titre_loop.py``): the server owns the state, every act is one ``micro`` event in the
append-only log, the step is derived by replay (:func:`step_of`), an act out of order is a
409, and an act that repeats one already recorded records nothing.

Acts, in order (``POST /revue/sessions/{id}/rubrique``):

- ``open``: the learner read the story.
- ``prepare {keys}``: Romy's notes have holes («Combien ? ___»); the learner chooses the
  three to go after.
- ``ask {text}`` (A2: the frame completed, B1+: free) or ``ask {key}`` (A1: a question tile,
  correct by construction): one question per turn, three turns. The match is deterministic
  first (``micro.match``: the question word and the content words, folded, lemma-light,
  against the stored facts); a question that matches a fact gets that fact's answer line and
  spends the turn; a well-formed question that matches nothing gets the witness's shrug and
  does not spend the turn the first time in a turn (nor does asking again for a fact already
  answered); a question with a slip in its form (no inversion or «est-ce que», a question word
  that is not the hole's) gets its answer all the same, the slip collected for «Relis tes
  questions», never shown during the interview. Only when the match is ambiguous between
  facts, ONE model call (``provider.micro_match``) picks among those stored facts or «none»;
  it never writes an answer.
- ``note {key, value | text}``: each hole the interview filled, from the witness's line (A1–A2
  pick, B1+ type); two tries, the value only after the second miss.
- ``review`` then ``review_fix {text | value: "romy"}``: the learner's questions go to Romy
  (one model call from A2, ``rubrique_proof.proofread``): her marks, the learner fixes first;
  A1's tiles are clean.

The close (:func:`close`) makes no model call: «La page» (the interview as Q&A under the
learner's name, each answer's source printed), the dispatch, the ``micro`` artifact, the
vignette, the kept words, Romy's memory and the witness's (``knowledge.remember``).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.schemas.revue import (
    RvClosing,
    RvDispatch,
    RvKept,
    RvMicroHint,
    RvMicroHole,
    RvMicroInterview,
    RvMicroNote,
    RvMicroNotes,
    RvMicroPage,
    RvMicroPageLine,
    RvMicroPageNote,
    RvMicroPrepare,
    RvMicroReview,
    RvMicroTile,
    RvMicroTurn,
    RvMicroView,
    RvRubriqueCast,
    RvRubriqueError,
    RvRubriqueRequest,
)
from app.services.revue import comptoir, knowledge, micro, rubrique_proof, voice
from app.services.revue.dossier import MicroDesk, MicroFact, comptoir_band
from app.services.revue.encounter import (
    Loaded,
    RevueError,
    _closing_of,
    _gloss_language_of,
    _source,
    _week_of,
    colophon_for,
    contribution_spans,
    dateline,
    kept_words,
    meter,
    parse_week,
    rv_claim,
    session_view,
)
from app.services.revue.fil_loop import _rng
from app.services.revue.intox_loop import _ct, _place, read_of

if TYPE_CHECKING:  # pragma: no cover
    from app.services.revue.encounter import RevueEncounter

KIND = "micro"
STEPS: tuple[str, ...] = ("read", "prepare", "interview", "notes", "review", "page")
KEYS: tuple[str, ...] = ("a", "b", "c", "d", "e", "f")
NEED = 3
TURNS = 3
MAX_TRIES = 2
FIX_TRIES = rubrique_proof.FIX_TRIES
QUESTION_MIN_WORDS = 2
QUESTION_MAX_WORDS = 20
NOTE_MAX_CHARS = 120

ROMY_CLOSE_LINE = "Super interview ! Tes questions et ses réponses sont dans le journal."
KICKER = "L'interview"

MATCH_INSTRUCTIONS = """A French learner interviews a witness about a news story. Their question could ask for
more than one of the facts the witness knows. From INPUT (the question and the candidate facts, each with its key,
its question word and its claim) answer with ONE JSON object: {"fact": "<the key of the fact the question asks
for>"} or {"fact": "none"} when it asks for none of them or you cannot tell. Never write an answer, never invent a
fact: pick a key from the candidates or say "none"."""
MATCH_SYSTEM = "You match a learner's question to one stored fact. Answer with one JSON object only."


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class Acts:
    """The learner's acts so far, replayed from the ``micro`` events."""

    def __init__(self, state: Any) -> None:
        self.opened = False
        self.chosen: list[str] = []
        self.asks: list[dict[str, Any]] = []
        self.notes: dict[str, list[dict[str, Any]]] = {}
        self.review: dict[str, Any] | None = None
        self.fixes: list[dict[str, Any]] = []
        for event in state.events:
            if event.kind != KIND:
                continue
            payload = event.payload
            act = payload.get("act")
            if act == "open":
                self.opened = True
            elif act == "prepare" and not self.chosen:
                self.chosen = [str(k) for k in payload.get("keys") or []]
            elif act == "ask" and not self.done:
                self.asks.append(dict(payload))
            elif act == "note":
                key = str(payload.get("key") or "")
                if not self.note_resolved(key):
                    self.notes.setdefault(key, []).append(dict(payload))
            elif act == "review" and self.review is None:
                self.review = dict(payload)
            elif act == "review_fix" and self.review is not None:
                self.fixes.append(dict(payload))

    @property
    def spent(self) -> int:
        return sum(1 for row in self.asks if row.get("spent"))

    @property
    def done(self) -> bool:
        return self.spent >= TURNS

    @property
    def free(self) -> bool:
        """This turn's first shrug (or repeat) is free: none since the last spent turn."""

        for row in reversed(self.asks):
            if row.get("spent"):
                return True
            return False
        return True

    def obtained(self) -> list[str]:
        """The facts' keys the interview answered, in the order they were answered."""

        return [str(row["fact"]) for row in self.asks if row.get("kind") == "answer" and row.get("fact")]

    def note_resolved(self, key: str) -> bool:
        rows = self.notes.get(key) or []
        return any(row.get("correct") for row in rows) or len(rows) >= MAX_TRIES

    def note_correct(self, key: str) -> bool:
        return any(row.get("correct") for row in self.notes.get(key) or [])

    @property
    def trail(self) -> rubrique_proof.Trail:
        return rubrique_proof.Trail(self.review, self.fixes)


def desk_of(loaded: Loaded) -> MicroDesk:
    desk = loaded.dossier.micro
    if desk is None:  # a micro session always snapshots its interview; keep the view total anyway
        raise RevueError(409, "revue_not_micro")
    return desk


def band_of(loaded: Loaded) -> str:
    return str(loaded.plan.learner.band)


def shown_order(seed: str, count: int) -> list[int]:
    order = list(range(count))
    _rng(seed, "micro-order").shuffle(order)
    return order


def key_of(seed: str, count: int) -> dict[int, str]:
    return {index: KEYS[position] for position, index in enumerate(shown_order(seed, count))}


def index_of(seed: str, count: int) -> dict[str, int]:
    return {key: index for index, key in key_of(seed, count).items()}


def step_of(desk: MicroDesk, acts: Acts, *, closed: bool) -> str:
    if closed:
        return "page"
    if not acts.opened:
        return "read"
    if len(acts.chosen) < NEED:
        return "prepare"
    if not acts.done:
        return "interview"
    if not all(acts.note_resolved(key) for key in acts.obtained()):
        return "notes"
    if not acts.trail.settled:
        return "review"
    return "page"


def ask_input(band: str) -> str:
    return "tiles" if band == "A1" else "frame" if band == "A2" else "free"


def note_input(band: str) -> str:
    return "pick" if comptoir_band(band) in {"a1", "a2"} else "write"


# ---------------------------------------------------------------------------
# Matching and grading
# ---------------------------------------------------------------------------


def _model_pick(encounter: RevueEncounter, loaded: Loaded, desk: MicroDesk, text: str, candidates: list[int],
                keys: dict[int, str]) -> tuple[int | None, float]:
    """ONE model call for an ambiguous question: a key among ``candidates``, or ``None``."""

    pick = getattr(encounter.provider, "micro_match", None)
    if not callable(pick):
        return None, 0.0
    claims = loaded.dossier.claims_by_id()
    context = {"question_fr": text,
               "candidates": [{"key": keys[i], "ask": desk.facts[i].ask,
                               "claim_fr": claims[desk.facts[i].claim_id].fr if desk.facts[i].claim_id in claims else ""}
                              for i in candidates]}
    before = meter(encounter.provider)
    try:
        raw = pick(context)
    except Exception as exc:  # noqa: BLE001 - in doubt, the shrug
        logger.bind(session_id=str(loaded.row.id)).warning("revue micro: match failed ({})", exc)
        raw = None
    cost = round(meter(encounter.provider) - before, 6)
    chosen = str((raw or {}).get("fact") or "") if isinstance(raw, dict) else ""
    by_key = {keys[i]: i for i in candidates}
    return by_key.get(chosen), cost


def note_options(desk: MicroDesk, seed: str, index: int) -> list[str]:
    """A1–A2: the hole's value and up to two other facts' values, in a per-session order."""

    value = desk.facts[index].value_fr
    others = [f.value_fr for i, f in enumerate(desk.facts) if i != index and comptoir.ci(f.value_fr) != comptoir.ci(value)]
    _rng(f"{seed}:{index}", "micro-note-others").shuffle(others)
    options = [value, *list(dict.fromkeys(others))[:2]]
    _rng(f"{seed}:{index}", "micro-note-options").shuffle(options)
    return options


def grade_note(fact: MicroFact, *, value: str | None = None, text: str | None = None) -> bool:
    """A pick is the value; a typed note carries it (numbers digit for digit, case and accents
    folded, a leading article or «à / en» may go)."""

    def core(words: str) -> str:
        folded = comptoir.ci(words).strip(" .!?«»")
        return re.sub(r"^(?:le |la |les |l'|un |une |des |du |de la |de l'|de |a |au |aux |en )", "", folded).strip()

    if value is not None:
        return comptoir.ci(value).strip(" .") == comptoir.ci(fact.value_fr).strip(" .")
    typed = str(text or "")
    if not typed.strip():
        return False
    want = comptoir.numbers(fact.value_fr)
    if want and comptoir.numbers(typed) != want:
        return False
    return core(fact.value_fr) in core(typed) if core(fact.value_fr) else False


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------


def _cast(witness: str) -> RvRubriqueCast:
    return RvRubriqueCast(id=witness, name_fr=comptoir.name_fr(witness), role_fr=comptoir.role_fr(witness))


def questions_of(acts: Acts) -> list[str]:
    """The questions that got an answer (the ones the page prints), in order."""

    return [str(row.get("text_fr") or "") for row in acts.asks if row.get("kind") == "answer"]


def split_questions(text: str, count: int) -> list[str] | None:
    """``text`` cut after each «?» into ``count`` questions, or ``None`` when it does not hold
    that many."""

    parts = [p.strip() for p in re.findall(r"[^?]+\?", text or "")]
    return parts if len(parts) == count else None


def micro_view(loaded: Loaded) -> RvMicroView:
    """What the player shows: the current step and only what that step may know."""

    dossier, plan, state, row = loaded.dossier, loaded.plan, loaded.state, loaded.row
    desk = desk_of(loaded)
    band = band_of(loaded)
    language = _gloss_language_of(plan)
    seed = str(row.id)
    count = len(desk.facts)
    keys = key_of(seed, count)
    indices = index_of(seed, count)
    acts = Acts(state)
    step = step_of(desk, acts, closed=state.closed)
    at = STEPS.index(step)
    obtained = acts.obtained()

    def hole(key: str) -> RvMicroHole:
        return RvMicroHole(key=key, hole=_ct(desk.facts[indices[key]].hole, language), filled=key in obtained)

    prepare = None
    if at >= STEPS.index("prepare"):
        prepare = RvMicroPrepare(holes=[hole(keys[i]) for i in shown_order(seed, count)], chosen=list(acts.chosen),
                                 need=NEED)

    interview = None
    if at >= STEPS.index("interview"):
        kind = ask_input(band)
        open_keys = [k for k in acts.chosen if k not in obtained]
        turns = []
        for ask in acts.asks:
            fact_key = str(ask.get("fact") or "") or None
            line = desk.facts[indices[fact_key]].answer.for_band(band) if fact_key in indices else desk.shrug.for_band(band)
            turns.append(RvMicroTurn(question_fr=str(ask.get("text_fr") or ""), answer=_ct(line, language),
                                     kind=str(ask.get("kind") or "shrug"), spent=bool(ask.get("spent")),  # type: ignore[arg-type]
                                     hole_key=fact_key))
        interview = RvMicroInterview(
            witness=_cast(desk.witness), input=kind,  # type: ignore[arg-type]
            phrase=_ct(desk.phrase.for_band(band), language),
            holes=[hole(k) for k in acts.chosen],
            tiles=[RvMicroTile(key=k, text=_ct(desk.facts[indices[k]].tile, language)) for k in open_keys] if kind == "tiles" else [],
            frames=list({f.fr: f for f in (_ct(desk.facts[indices[k]].frame, language) for k in acts.chosen)}.values())
            if kind == "frame" else [],
            turns=turns, spent=acts.spent, total=TURNS, free=acts.free, done=acts.done,
        )

    notes = None
    if at >= STEPS.index("notes"):
        kind = note_input(band)
        items = []
        for key in obtained:
            fact = desk.facts[indices[key]]
            rows = acts.notes.get(key) or []
            resolved = acts.note_resolved(key)
            items.append(RvMicroNote(
                key=key, hole=_ct(fact.hole, language), answer=_ct(fact.answer.for_band(band), language),
                options=note_options(desk, seed, indices[key]) if kind == "pick" else [],
                tries=len(rows), attempts=[str(r.get("value") or r.get("text") or "") for r in rows],
                resolved=resolved, correct=acts.note_correct(key) if resolved else None,
                value_fr=fact.value_fr if resolved else None,
            ))
        notes = RvMicroNotes(input=kind, items=items)  # type: ignore[arg-type]

    review = None
    if at >= STEPS.index("review"):
        questions = questions_of(acts)
        trail = acts.trail
        proof = trail.proof
        hints = [RvMicroHint(index=i, code=code)  # type: ignore[arg-type]
                 for i, ask in enumerate(a for a in acts.asks if a.get("kind") == "answer")
                 for code in ask.get("slips") or [] if code in {"inversion", "question_word"}]
        review = RvMicroReview(
            input="tiles" if ask_input(band) == "tiles" else "write",
            questions=questions,
            hints=hints if ask_input(band) != "tiles" else [],
            draft_fr=proof["draft"] if proof else None,
            proof=proof["proof"] if proof else None,  # type: ignore[arg-type]
            marks=rubrique_proof.marks_view(proof),
            tries=proof["tries"] if proof else 0,
            max_tries=FIX_TRIES,
            printed_fr=proof["printed"] if proof else None,
            notes=rubrique_proof.notes_view(trail) if proof else [],
        )

    return RvMicroView(step=step, steps=list(STEPS), band=comptoir_band(band), title_fr=dossier.title_fr,  # type: ignore[arg-type]
                       read=read_of(loaded, language), prepare=prepare, interview=interview, notes=notes, review=review)


view = micro_view


# ---------------------------------------------------------------------------
# The acts
# ---------------------------------------------------------------------------


def _out_of_order(step: str, act: str) -> RevueError:
    return RevueError(409, "revue_micro_out_of_order", step=step, act=act)


def _bad(act: str) -> RevueError:
    return RevueError(422, "revue_micro_bad_act", act=act)


def _question(text: str) -> str:
    value = voice.french_typography(re.sub(r"\s+", " ", text or "").strip())
    value = value[:1].upper() + value[1:]
    if value and not re.search(r"[?]\s*$", value):
        value = voice.french_typography(value.rstrip(" .!") + " ?")
    return value


def question_problem(text: str) -> RvRubriqueError | None:
    count = comptoir.word_count(text)
    if count < QUESTION_MIN_WORDS:
        return RvRubriqueError(code="too_short", count=QUESTION_MIN_WORDS)
    if count > QUESTION_MAX_WORDS:
        return RvRubriqueError(code="too_long", count=QUESTION_MAX_WORDS)
    if not micro.is_question(text):
        return RvRubriqueError(code="not_a_question")
    return None


def apply_act(encounter: RevueEncounter, loaded: Loaded, body: RvRubriqueRequest) -> RvRubriqueError | None:
    """Record one act (or nothing, when it repeats one already recorded); returns the reason
    for an act the learner can fix on the same screen."""

    state = loaded.state
    desk = desk_of(loaded)
    band = band_of(loaded)
    seed = str(loaded.row.id)
    count = len(desk.facts)
    keys = key_of(seed, count)
    indices = index_of(seed, count)
    acts = Acts(state)
    step = step_of(desk, acts, closed=state.closed)
    act = body.act
    if state.closed:
        raise _out_of_order(step, act)

    if act == "open":
        if not acts.opened:
            state.append(KIND, act="open")
        return None

    if act == "prepare":
        chosen = list(dict.fromkeys(str(k) for k in body.keys or []))
        if any(k not in indices for k in chosen):
            raise _bad(act)
        if acts.chosen:
            return None  # chosen once: a repeat
        if not acts.opened:
            raise _out_of_order(step, act)
        if len(chosen) != NEED:
            return RvRubriqueError(code="pick_three", count=NEED)
        state.append(KIND, act="prepare", keys=chosen)
        return None

    if act == "ask":
        if step != "interview":
            if acts.done and step != "prepare" and step != "read":
                return None  # the interview is over: a late double submit
            raise _out_of_order(step, act)
        kind = ask_input(band)
        if kind == "tiles":
            key = str(body.key or "")
            if key not in acts.chosen:
                raise _bad(act)
            text = desk.facts[indices[key]].tile.fr
            source = "tile"
        else:
            raw = re.sub(r"\s+", " ", body.text or "").strip()
            text = _question(raw)
            why = question_problem(text)
            if why is None and not micro.is_question(raw):
                why = RvRubriqueError(code="not_a_question")  # a «?» the learner did not type makes none
            if why is not None:
                return why
            source = "rule"
        if acts.asks and comptoir.ci(acts.asks[-1].get("text_fr")) == comptoir.ci(text):
            return None  # the same question again: a repeat
        if kind == "tiles":
            found: dict[str, Any] = {"kind": "match", "index": indices[str(body.key)], "qword": micro.question_word(text)}
        else:
            found = micro.match(text, desk.facts, chosen=[indices[k] for k in acts.chosen],
                                generic=micro.generic_words(loaded.dossier))
        cost = 0.0
        if found["kind"] == "ambiguous":
            index, cost = _model_pick(encounter, loaded, desk, text, list(found["candidates"]), keys)
            found = {"kind": "match", "index": index, "qword": found.get("qword")} if index is not None else \
                {"kind": "none", "qword": found.get("qword")}
            source = "model"
        fact_key = keys[found["index"]] if found["kind"] == "match" else None
        obtained = acts.obtained()
        if fact_key is not None and fact_key not in obtained:
            kind_of, spent = "answer", True
        else:
            kind_of, spent = ("again" if fact_key is not None else "shrug"), not acts.free
        slips = micro.formation_slips(text, desk.facts[found["index"]] if fact_key else None, found.get("qword")) \
            if kind != "tiles" and kind_of == "answer" else []
        if kind != "tiles":
            state.append("turn_learner", text_fr=text, mode=body.mode, micro="ask")
        state.append(KIND, act="ask", text_fr=text, typed_fr=text if kind != "tiles" else "", fact=fact_key,
                     kind=kind_of, spent=spent, slips=slips, source=source, cost_usd=cost)
        return None

    if act == "note":
        key = str(body.key or "")
        if step in {"read", "prepare", "interview"}:
            raise _out_of_order(step, act)
        if key not in acts.obtained():
            raise _bad(act)
        if acts.note_resolved(key):
            return None
        fact = desk.facts[indices[key]]
        rows = acts.notes.get(key) or []
        if note_input(band) == "pick":
            value = re.sub(r"\s+", " ", body.value or "").strip()
            if value not in note_options(desk, seed, indices[key]):
                raise _bad(act)
            if rows and rows[-1].get("value") == value:
                return None
            state.append(KIND, act="note", key=key, value=value, correct=grade_note(fact, value=value),
                         attempt=len(rows) + 1)
            return None
        text = re.sub(r"\s+", " ", body.text or "").strip()[:NOTE_MAX_CHARS]
        if not text:
            return RvRubriqueError(code="too_short", key=key, count=1)
        if rows and comptoir.ci(rows[-1].get("text")) == comptoir.ci(text):
            return None
        state.append(KIND, act="note", key=key, text=text, correct=grade_note(fact, text=text), attempt=len(rows) + 1)
        return None

    if act == "review":
        if acts.review is not None:
            return None  # a double submit returns the stored result
        if step != "review":
            raise _out_of_order(step, act)
        return _review(encounter, loaded, acts, band=band)

    if act == "review_fix":
        if acts.review is None:
            raise _out_of_order(step, act)
        return _review_fix(encounter, loaded, acts, band=band, body=body)

    raise _bad(act)


def _extra(acts: Acts) -> dict[str, Any]:
    slips = [{"question": i + 1, "slip": code}
             for i, ask in enumerate(a for a in acts.asks if a.get("kind") == "answer") for code in ask.get("slips") or []]
    return {"slips": slips}


def _review(encounter: RevueEncounter, loaded: Loaded, acts: Acts, *, band: str) -> RvRubriqueError | None:
    """The questions go to Romy: one model call from A2 (A1's tiles are clean)."""

    questions = questions_of(acts)
    draft = " ".join(questions)
    if ask_input(band) == "tiles" or not questions:
        check: dict[str, Any] = {"proof": "clean", "target": draft, "marks": [], "cost": 0.0, "refused": None,
                                 "source": "tiles"}
    else:
        check = rubrique_proof.proofread(encounter, loaded, kind=KIND, band=band, learner_fr=draft, extra=_extra(acts),
                                         refuse=_refuse(len(questions), loaded))
    loaded.state.append(KIND, act="review", learner_fr=draft, typed_fr="", proof=check["proof"],
                        target_fr=check["target"], marks=check["marks"], source=check["source"], cost_usd=check["cost"],
                        refused=check["refused"],
                        prompt_version=rubrique_proof.prompt_version() if check["source"] != "tiles" else None)
    return None


def _refuse(count: int, loaded: Loaded):  # noqa: ANN202
    numbers = rubrique_proof.no_new_number(loaded.dossier)
    return lambda text: numbers(text) or split_questions(text, count) is None


def _review_fix(encounter: RevueEncounter, loaded: Loaded, acts: Acts, *, band: str,
                body: RvRubriqueRequest) -> RvRubriqueError | None:
    trail = acts.trail
    count = len(questions_of(acts))

    def check(text: str) -> RvRubriqueError | None:
        if split_questions(text, count) is None:
            return RvRubriqueError(code="keep_questions", count=count)
        return None

    try:
        row, error = rubrique_proof.fix_row(encounter, loaded, trail, kind=KIND, band=band, text=body.text,
                                            value=body.value, check=check, prepare=voice.french_typography,
                                            extra=_extra(acts), refuse=_refuse(count, loaded))
    except LookupError as exc:
        raise _out_of_order("review", "review_fix") from exc
    if row is None:
        return error
    if row.get("text_fr"):
        loaded.state.append("turn_learner", text_fr=row["text_fr"], mode=body.mode, micro="review_fix")
    loaded.state.append(KIND, act="review_fix", **row)
    rubrique_proof.settle(encounter, loaded, trail, str(row.get("proof")))
    return None


# ---------------------------------------------------------------------------
# The close: «La page»
# ---------------------------------------------------------------------------


def _byline(encounter: RevueEncounter, loaded: Loaded) -> str:
    """«Propos recueillis par {the learner's first name}», else «par toi»."""

    name = ""
    try:
        from app.db.models.user import User  # noqa: PLC0415

        user = encounter.db.get(User, loaded.row.user_id)
        for field in ("display_name", "first_name", "full_name", "name", "username"):
            value = str(getattr(user, field, "") or "").strip()
            if value and "@" not in value:
                name = value.split()[0][:40]
                break
    except Exception as exc:  # noqa: BLE001 - the page says «par toi»
        logger.debug("revue micro: learner name unread ({})", exc)
    return f"Propos recueillis par {name}" if name else "Propos recueillis par toi"


def close(encounter: RevueEncounter, loaded: Loaded) -> tuple[Any, RvClosing]:
    """«La page»: no model call. The notes and the questions must be settled first."""

    from app.services.revue.carte import keep_papier_words

    row, dossier, plan, state = loaded.row, loaded.dossier, loaded.plan, loaded.state
    existing = _closing_of(state)
    if existing is not None:
        return session_view(loaded), existing
    desk = desk_of(loaded)
    band = band_of(loaded)
    seed = str(row.id)
    indices = index_of(seed, len(desk.facts))
    acts = Acts(state)
    step = step_of(desk, acts, closed=False)
    if step != "page":
        raise RevueError(409, "revue_micro_out_of_order", step=step, act="close")
    trail = acts.trail
    proof = trail.proof or {"proof": "clean", "printed": "", "draft": ""}
    obtained = acts.obtained()
    asked = questions_of(acts)
    printed = split_questions(str(proof.get("printed") or ""), len(asked)) or [voice.french_typography(q) for q in asked]
    claims = dossier.claims_by_id()
    lines: list[RvMicroPageLine] = []
    for key, question in zip(obtained, printed, strict=False):
        fact = desk.facts[indices[key]]
        claim = claims.get(fact.claim_id)
        source = _source(dossier, claim.source_id).name if claim is not None else ""
        lines.append(RvMicroPageLine(question_fr=question, answer_fr=fact.answer.for_band(band).fr, source_name=source))
    notes = [RvMicroPageNote(hole_fr=desk.facts[indices[key]].hole.fr, value_fr=desk.facts[indices[key]].value_fr,
                             right=acts.note_correct(key)) for key in obtained]
    witness = RvRubriqueCast(id=desk.witness, name_fr=comptoir.name_fr(desk.witness), role_fr=comptoir.role_fr(desk.witness))
    byline = _byline(encounter, loaded)
    page = RvMicroPage(title_fr=dossier.title_fr, dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "),
                       witness=witness, byline_fr=byline, lines=lines, notes=notes, proof=proof.get("proof"),  # type: ignore[arg-type]
                       phrase_fr=desk.phrase.for_band(band).fr, words=[])
    own = trail.own_words() or " ".join(str(a.get("typed_fr") or "") for a in acts.asks if a.get("kind") == "answer").strip()
    text_fr = " ".join(line.question_fr for line in lines)
    contribution = contribution_spans(own, text_fr) if own else []
    state.append("artifact", kind=KIND, text_fr=text_fr, learner_fr=own, contribution=contribution,
                 proof=proof.get("proof"), witness=desk.witness)
    shown = [claims[cid] for cid in dict.fromkeys(desk.facts[indices[k]].claim_id for k in obtained) if cid in claims]
    sources = [_source(dossier, sid) for sid in dict.fromkeys(c.source_id for c in shown)]
    names = list(dict.fromkeys(source.name for source in sources))
    dispatch = RvDispatch(
        kicker_fr=f"{KICKER} · {witness.name_fr}",
        headline_fr=dossier.title_fr,
        body_fr=[f"{line.question_fr} — {line.answer_fr}" for line in lines],
        contribution=[],
        byline_fr=f"{byline} · d'après " + " et ".join(names) if names else byline,
        sources=sources,
    )
    met = [dossier.lead_for(band).fr, *(line.answer_fr for line in lines), *(c.fr for c in shown)]
    kept = RvKept(words=kept_words(plan, state, met=met, used=[own] if own else []),
                  claims=[rv_claim(dossier, c) for c in shown])
    page.words = [word.fr for word in kept.words]
    closing = RvClosing(romy_line_fr=ROMY_CLOSE_LINE, dispatch=dispatch, kept=kept, question_kept_fr=None,
                        colophon_fr=colophon_for(row.week), micro_page=page)  # type: ignore[arg-type]
    closing.vignette = encounter._mint_vignette(loaded, kind=KIND, kept_contribution=bool(contribution))  # noqa: SLF001
    keep_papier_words(encounter.db, row, dossier=dossier, plan=plan, state=state, kept=kept)

    state.append("turn_romy", beat="close", role="close", text_fr=ROMY_CLOSE_LINE, cost_usd=0.0)
    state.append("closed", closing=closing.model_dump(mode="json"))
    row.status = "closed"
    row.closed_at = datetime.now(UTC)
    encounter._remember(loaded, artifact=state.current_artifact, kind=KIND)  # noqa: SLF001
    _remember_witness(encounter, loaded, desk, lines)
    encounter._record_cost(loaded)  # noqa: SLF001
    encounter._save(loaded)  # noqa: SLF001
    try:
        from app.services.revue import carte as _carte

        _carte.invalidate(row.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("revue: carte invalidate skipped ({})", exc)
    return session_view(loaded), closing


def _remember_witness(encounter: RevueEncounter, loaded: Loaded, desk: MicroDesk, lines: list[RvMicroPageLine]) -> None:
    """The witness remembers being interviewed (the existing NPC memory, as the guests')."""

    row, dossier = loaded.row, loaded.dossier
    try:
        _, number = parse_week(_week_of(row.week))
        content = f"Semaine {number} : tu m'as posé tes questions pour le Papier de Romy, sur « {dossier.title_fr} »."
        if lines:
            content += f" Tu m'as demandé : « {lines[0].question_fr} »."
        knowledge.remember(encounter.db, user_id=row.user_id, cast_id=desk.witness, content=content[:400],
                           scene_id=str(row.id), quote=lines[0].question_fr if lines else None, sentiment="positive")
    except Exception as exc:  # noqa: BLE001 - a memory never costs the close
        logger.bind(session_id=str(row.id)).debug("revue micro: witness memory skipped ({})", exc)


__all__ = [
    "Acts",
    "MATCH_INSTRUCTIONS",
    "apply_act",
    "close",
    "grade_note",
    "micro_view",
    "split_questions",
    "step_of",
    "view",
]
