"""«Le fil»: the learner's loop (WP-119 «les rubriques», owner 2026-11-20).

Five screens — read, put the wire back in order, the sequence words, tell it, the page —
played from the wire the desk wrote (``fil.py``) and snapshotted on the session's first
``choice`` event (``mode="fil"``). As at the counter (``comptoir_loop.py``) the server owns
the state: every act is one ``fil`` event in the append-only log, the step is derived from
the acts by replay (:func:`step_of`), an act out of order is a 409 with the same view, and an
act that repeats one already recorded records nothing.

Acts, in order:

- ``open``: the learner read the story («Au fil →»).
- ``order {order}``: the strips' keys in the learner's order. Graded deterministically. A wrong
  order names the first strip out of place and the strip it comes after (``hint``), never the
  solution; a second wrong order shows the solution. Two tries at most.
- ``words {picks}``: a sequence word per strip. A1 places its four words; from A2 each strip
  offers three, one per role (first · middle · last). A miss says what the word means and
  where it goes; the second miss shows the right words. Two tries at most.
- ``tell {parts | texts | text}``: the story in two sentences. A1 builds them from a sequence
  word and an event tile each (correct by construction, no model call; an impossible order is
  refused with its reason, nothing recorded). A2 completes the two frames, B1+ write freely
  with at least two sequence words; one model call (``provider.fil_edit``) for Romy's
  correction, kept back: the learner sees her marks on their own words and fixes them
  (``tell_fix {text | value: "romy"}``), as at the counter, with the same marks
  (``comptoir_loop.proof_marks``).

The close (:func:`close_fil`) makes no model call: «La page», the dispatch, the ``fil``
artifact, the vignette, the kept words, Romy's memory, the cost row.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.schemas.revue import (
    RvClosing,
    RvComptoirMark,
    RvComptoirNote,
    RvComptoirRead,
    RvComptoirText,
    RvDispatch,
    RvFilConnector,
    RvFilError,
    RvFilHint,
    RvFilMiss,
    RvFilOrder,
    RvFilPage,
    RvFilPageStrip,
    RvFilRequest,
    RvFilStrip,
    RvFilTell,
    RvFilTile,
    RvFilView,
    RvFilWords,
    RvKept,
)
from app.services.revue import comptoir, comptoir_loop, pourquoi, voice
from app.services.revue.dossier import (
    ComptoirText,
    EditorialDossier,
    FilConnector,
    FilWire,
    comptoir_band,
)
from app.services.revue.encounter import (
    Loaded,
    RevueError,
    _closing_of,
    _gloss_language_of,
    _source,
    colophon_for,
    contribution_spans,
    dateline,
    kept_words,
    meter,
    rv_claim,
    session_view,
)
from app.services.revue.fil import CONNECTORS, role_of

if TYPE_CHECKING:  # pragma: no cover
    from app.services.revue.encounter import RevueEncounter

FIL_EDIT_PROMPT_VERSION = "fil-edit-v1"

STEPS: tuple[str, ...] = ("read", "order", "words", "tell", "page")
KEYS: tuple[str, ...] = ("a", "b", "c", "d")
MAX_TRIES = 2
FIX_TRIES = comptoir_loop.FIX_TRIES
EDIT_MAX_RATIO = comptoir_loop.EDIT_MAX_RATIO
#: The least the learner writes: each A2 frame's end, the whole B1+ telling.
A2_PART_MIN_WORDS = 2
A2_MIN_WORDS = 5
FREE_MIN_WORDS = 12
FREE_MIN_CONNECTORS = 2

ROMY_CLOSE_LINE = "Merci ! Le fil est remis en ordre, et ton récit est dans le journal."
KICKER = "Le fil de Romy"


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class Acts:
    """The learner's acts so far, replayed from the ``fil`` events."""

    def __init__(self, state: Any) -> None:
        self.opened = False
        self.orders: list[dict[str, Any]] = []
        self.words: list[dict[str, Any]] = []
        self.tell: dict[str, Any] | None = None
        self.fixes: list[dict[str, Any]] = []
        for event in state.events:
            if event.kind != "fil":
                continue
            payload = event.payload
            act = payload.get("act")
            if act == "open":
                self.opened = True
            elif act == "order" and len(self.orders) < MAX_TRIES and not self.order_resolved:
                self.orders.append(dict(payload))
            elif act == "words" and len(self.words) < MAX_TRIES and not self.words_resolved:
                self.words.append(dict(payload))
            elif act == "tell" and self.tell is None:
                self.tell = dict(payload)
            elif act == "tell_fix" and self.tell is not None:
                self.fixes.append(dict(payload))

    @property
    def order_resolved(self) -> bool:
        return any(row.get("correct") for row in self.orders) or len(self.orders) >= MAX_TRIES

    @property
    def order_correct(self) -> bool:
        return any(row.get("correct") for row in self.orders)

    @property
    def words_resolved(self) -> bool:
        return any(row.get("correct") for row in self.words) or len(self.words) >= MAX_TRIES

    @property
    def proof(self) -> dict[str, Any] | None:
        """Where the telling stands before print (as ``comptoir_loop.Acts.proof``)."""

        if self.tell is None:
            return None
        latest = self.fixes[-1] if self.fixes else self.tell
        proof = str(latest.get("proof") or "as_written")
        texts = [str(fix.get("text_fr")) for fix in self.fixes if fix.get("text_fr")]
        draft = texts[-1] if texts else str(self.tell.get("learner_fr") or "")
        target = str(latest.get("target_fr") or "")
        printed = None
        if proof in {"clean", "fixed", "corrected"}:
            printed = target or voice.french_typography(comptoir_loop._sentence_end(draft))  # noqa: SLF001
        elif proof == "as_written":
            printed = voice.french_typography(comptoir_loop._sentence_end(draft))  # noqa: SLF001
        return {"proof": proof, "draft": draft, "marks": list(latest.get("marks") or []) if proof == "marked" else [],
                "tries": len(texts), "target": target, "printed": printed}

    @property
    def settled(self) -> bool:
        proof = self.proof
        return proof is not None and proof["proof"] != "marked"

    def own_words(self) -> str:
        """Only what the learner typed or said (never a tile, never a frame)."""

        texts = [str((self.tell or {}).get("typed_fr") or "")]
        texts += [str(fix.get("typed_fr") or "") for fix in self.fixes]
        return " ".join(text for text in texts if text)


def wire_of(loaded: Loaded) -> FilWire:
    wire = loaded.dossier.fil
    if wire is None:  # a fil session always snapshots its wire; keep the wire total anyway
        raise RevueError(409, "revue_not_fil")
    return wire


def band_of(loaded: Loaded) -> str:
    return str(loaded.plan.learner.band)


def step_of(acts: Acts, *, closed: bool) -> str:
    if closed:
        return "page"
    if not acts.opened:
        return "read"
    if not acts.order_resolved:
        return "order"
    if not acts.words_resolved:
        return "words"
    if not acts.settled:
        return "tell"
    return "page"


# ---------------------------------------------------------------------------
# The order
# ---------------------------------------------------------------------------


def _rng(seed: str, salt: str) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(f"{salt}:{seed}".encode()).digest()[:8], "big"))  # noqa: S311


def shown_order(seed: str) -> list[int]:
    """The strips' true indices in the order the session shows them: shuffled per session,
    never already in order."""

    order = [0, 1, 2, 3]
    _rng(seed, "fil-order").shuffle(order)
    if order == [0, 1, 2, 3]:
        order = order[1:] + order[:1]
    return order


def key_of(seed: str) -> dict[int, str]:
    """True index → the letter the session shows it under."""

    return {index: KEYS[position] for position, index in enumerate(shown_order(seed))}


def index_of(seed: str) -> dict[str, int]:
    return {key: index for index, key in key_of(seed).items()}


def grade_order(seed: str, keys: list[str]) -> dict[str, Any]:
    """``correct`` when ``keys`` put the strips in true order; else the ``hint``: the first
    strip out of place and the strip it comes after (built from the strips, never the order)."""

    indices = index_of(seed)
    order = [indices[key] for key in keys]
    if order == [0, 1, 2, 3]:
        return {"correct": True, "hint": None}
    slot = next(i for i, index in enumerate(order) if index != i)
    return {"correct": False, "hint": {"key": keys[slot], "after_key": key_of(seed)[slot]}}


# ---------------------------------------------------------------------------
# The sequence words
# ---------------------------------------------------------------------------


def connector_id(connector: FilConnector) -> str:
    return re.sub(r"[^a-z]+", "-", comptoir.ci(connector.fr)).strip("-")


def connectors_of(wire: FilWire, band: str) -> list[FilConnector]:
    return wire.connectors_for(band) or list(CONNECTORS[comptoir_band(band)])


def _by_id(wire: FilWire, band: str) -> dict[str, FilConnector]:
    rows = {connector_id(c): c for c in connectors_of(wire, band)}
    for row in CONNECTORS["a2"] + CONNECTORS["b1"] + CONNECTORS["a1"]:
        rows.setdefault(connector_id(row), row)
    return rows


def words_input(band: str) -> str:
    return "place" if band == "A1" else "choose"


def options_for(wire: FilWire, band: str, seed: str) -> list[list[str]]:
    """From A2: three words per strip, one per role, in a per-session order."""

    rng = _rng(seed, "fil-words")
    rows = connectors_of(wire, band)
    by_role = {role: [connector_id(c) for c in rows if c.role == role] for role in ("first", "middle", "last")}
    options = []
    for _position in range(4):
        picked = [rng.choice(by_role[role]) for role in ("first", "middle", "last")]
        rng.shuffle(picked)
        options.append(picked)
    return options


def chips_for(wire: FilWire, band: str, seed: str) -> list[str]:
    """A1: its four words, in a per-session order (never already the right one)."""

    ids = [connector_id(c) for c in connectors_of(wire, "A1")][:4]
    shuffled = list(ids)
    _rng(seed, "fil-chips").shuffle(shuffled)
    if [_by_id(wire, band)[i].role for i in shuffled] == list(_roles()):
        shuffled = shuffled[1:] + shuffled[:1]
    return shuffled


def _roles() -> tuple[str, ...]:
    return tuple(role_of(position) for position in range(4))


def solution_words(wire: FilWire, band: str, seed: str) -> list[str]:
    """The right word per strip: for A1 its four words in role order; from A2 the option
    whose role fits each position."""

    rows = _by_id(wire, band)
    if words_input(band) == "place":
        ids = chips_for(wire, band, seed)
        out: list[str] = []
        for role in _roles():
            out.append(next(i for i in ids if rows[i].role == role and i not in out))
        return out
    return [next(i for i in options if rows[i].role == role_of(p)) for p, options in enumerate(options_for(wire, band, seed))]


def grade_words(wire: FilWire, band: str, seed: str, picks: list[str]) -> dict[str, Any] | None:
    """``None`` when ``picks`` are not this session's words; else ``correct`` and the misses
    (each wrong word with the role it has and the role the strip needs)."""

    rows = _by_id(wire, band)
    if len(picks) != 4:
        return None
    if words_input(band) == "place":
        if sorted(picks) != sorted(chips_for(wire, band, seed)):
            return None
    elif any(pick not in options for pick, options in zip(picks, options_for(wire, band, seed), strict=True)):
        return None
    misses = [{"position": p, "id": pick, "role": rows[pick].role, "needs": role_of(p)}
              for p, pick in enumerate(picks) if rows[pick].role != role_of(p)]
    return {"correct": not misses, "misses": misses}


# ---------------------------------------------------------------------------
# The telling
# ---------------------------------------------------------------------------


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def tile_of(wire: FilWire, index: int) -> ComptoirText:
    strip = wire.strips[index]
    return strip.tile or ComptoirText(fr=comptoir._lower_start(strip.a1.fr.rstrip(" .!…")))  # noqa: SLF001


def a1_telling(first: FilConnector, first_tile: str, second: FilConnector, second_tile: str) -> str:
    """A1's two sentences, correct by construction: «D'abord, la mairie annonce des travaux.
    Enfin, le marché rouvre le 14 novembre.»"""

    one = f"{_cap(first.fr)}, {first_tile.strip().rstrip(' .!…')}."
    two = f"{_cap(second.fr)}, {second_tile.strip().rstrip(' .!…')}."
    return voice.french_typography(f"{one} {two}")


def tiles_problem(wire: FilWire, band: str, seed: str, parts: list[str]) -> RvFilError | None:
    """Why A1's two sentences do not tell the story in order, or ``None`` (never a solution:
    the reason names the learner's own pieces)."""

    rows = _by_id(wire, band)
    indices = index_of(seed)
    if len(parts) != 4 or parts[0] not in rows or parts[2] not in rows or parts[1] not in indices or parts[3] not in indices:
        return RvFilError(code="tell_pick_all")
    first, second = rows[parts[0]], rows[parts[2]]
    one, two = indices[parts[1]], indices[parts[3]]
    if one == two:
        return RvFilError(code="tell_same", key=parts[1])
    if one > two:
        return RvFilError(code="tell_order", key=parts[1], after_key=parts[3])
    if first.role == "last":
        return RvFilError(code="tell_last_first", key=parts[0])
    if first.role == "middle" and one == 0:
        return RvFilError(code="tell_starts_middle", key=parts[0])
    if second.role == "first":
        return RvFilError(code="tell_first_second", key=parts[2])
    return None


def connectors_used(text: str) -> list[str]:
    """The distinct sequence words ``text`` uses (any band's)."""

    folded = f" {comptoir.ci(text)} "
    seen: list[str] = []
    for band in ("b1", "a2", "a1"):
        for connector in CONNECTORS[band]:
            word = comptoir.ci(connector.fr)
            if word not in seen and re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", folded):
                seen.append(word)
    # «tout d'abord» counts once, not also as «d'abord»
    return [w for w in seen if not any(w != other and w in other for other in seen)]


def a2_telling(frames: list[ComptoirText], texts: list[str]) -> str:
    parts = []
    for frame, text in zip(frames, texts, strict=True):
        body = re.sub(r"\s+", " ", text).strip().rstrip(" .!…")
        head = frame.fr.rstrip(" .…")
        if comptoir.ci(body).startswith(comptoir.ci(head)[:10]):
            parts.append(f"{_cap(body)}.")
        else:
            parts.append(f"{head} {body}.")
    return voice.french_typography(" ".join(parts))


def too_short(band: str, *, texts: list[str] | None = None, text: str | None = None) -> RvFilError | None:
    if band == "A2":
        counts = [comptoir.word_count(t) for t in texts or []]
        if len(counts) != 2 or min(counts) < A2_PART_MIN_WORDS or sum(counts) < A2_MIN_WORDS:
            return RvFilError(code="too_short", count=A2_MIN_WORDS)
        return None
    if comptoir.word_count(text) < FREE_MIN_WORDS:
        return RvFilError(code="too_short", count=FREE_MIN_WORDS)
    if len(connectors_used(text or "")) < FREE_MIN_CONNECTORS:
        return RvFilError(code="need_connectors", count=FREE_MIN_CONNECTORS)
    return None


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------


def _ct(text: ComptoirText | None, language: str) -> RvComptoirText:
    if text is None:
        return RvComptoirText(fr="")
    return RvComptoirText(fr=text.fr, tr=text.translation(language) if language != "fr" else None)


def _place(loaded: Loaded) -> Any:
    dossier, plan = loaded.dossier, loaded.plan
    return next((p for p in dossier.places if p.id == plan.stage.place_id), dossier.places[0])


def _connector_view(connector: FilConnector, language: str, *, open_: bool) -> RvFilConnector:
    return RvFilConnector(id=connector_id(connector), fr=connector.fr,
                          tr=connector.translation(language) if open_ and language != "fr" else None,
                          role=connector.role if open_ else None)  # type: ignore[arg-type]


def fil_view(loaded: Loaded) -> RvFilView:
    """What the player shows: the current step and only what that step may know."""

    dossier, plan, state, row = loaded.dossier, loaded.plan, loaded.state, loaded.row
    wire = wire_of(loaded)
    band = band_of(loaded)
    language = _gloss_language_of(plan)
    seed = str(row.id)
    acts = Acts(state)
    step = step_of(acts, closed=state.closed)
    at = STEPS.index(step)
    lead = dossier.lead_for(band)
    read = RvComptoirRead(
        dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "),
        lead=RvComptoirText(fr=lead.fr, tr=lead.translation(language) if language != "fr" else None),
        sources=[_source(dossier, s.id) for s in dossier.sources[:1]],
    )
    keys = key_of(seed)

    order = None
    if at >= STEPS.index("order"):
        last = acts.orders[-1] if acts.orders else None
        resolved = acts.order_resolved
        order = RvFilOrder(
            strips=[RvFilStrip(key=keys[index], text=_ct(wire.strips[index].for_band(band), language),
                               label=_ct(wire.strips[index].label, language) if wire.strips[index].label else None)
                    for index in shown_order(seed)],
            tries=len(acts.orders),
            placed=list(last.get("order") or []) if last else [],
            hint=RvFilHint(**last["hint"]) if last and last.get("hint") and not acts.order_correct else None,
            resolved=resolved,
            correct=acts.order_correct if resolved else None,
            solution=[keys[index] for index in range(4)] if resolved else [],
        )

    words = None
    if at >= STEPS.index("words"):
        rows = _by_id(wire, band)
        resolved = acts.words_resolved
        last = acts.words[-1] if acts.words else None
        ids = chips_for(wire, band, seed) if words_input(band) == "place" else list(
            dict.fromkeys(i for options in options_for(wire, band, seed) for i in options))
        misses = []
        if last and not last.get("correct"):
            for miss in last.get("misses") or []:
                connector = rows[miss["id"]]
                misses.append(RvFilMiss(position=int(miss["position"]), id=miss["id"], fr=connector.fr,
                                        tr=connector.translation(language) if language != "fr" else None,
                                        role=miss["role"], needs=miss["needs"]))
        words = RvFilWords(
            input=words_input(band),  # type: ignore[arg-type]
            strips=[_ct(strip.for_band(band), language) for strip in wire.strips],
            connectors=[_connector_view(rows[i], language, open_=resolved) for i in ids],
            options=options_for(wire, band, seed) if words_input(band) == "choose" else [],
            tries=len(acts.words),
            picked=list(last.get("picks") or []) if last else [],
            misses=misses,
            resolved=resolved,
            correct=any(r.get("correct") for r in acts.words) if resolved else None,
            solution=solution_words(wire, band, seed) if resolved else [],
        )

    tell = None
    if at >= STEPS.index("tell"):
        tell = _tell_view(wire, band, seed, language, acts)

    return RvFilView(step=step, steps=list(STEPS), band=comptoir_band(band), title_fr=dossier.title_fr,  # type: ignore[arg-type]
                     read=read, order=order, words=words, tell=tell)


def tell_input(band: str) -> str:
    return "tiles" if band == "A1" else "frames" if band == "A2" else "free"


def _tell_view(wire: FilWire, band: str, seed: str, language: str, acts: Acts) -> RvFilTell:
    keys = key_of(seed)
    kind = tell_input(band)
    proof = acts.proof
    rows = connectors_of(wire, band)
    return RvFilTell(
        input=kind,  # type: ignore[arg-type]
        phrase=_ct(wire.telling.phrase.for_band(band), language),
        tiles=[RvFilTile(key=keys[index], text=_ct(tile_of(wire, index), language)) for index in range(4)]
        if kind == "tiles" else [],
        connectors=[_connector_view(c, language, open_=True) for c in rows],
        frames=[_ct(frame, language) for frame in wire.telling.frames] if kind == "frames" else [],
        min_words=A2_MIN_WORDS if kind == "frames" else FREE_MIN_WORDS if kind == "free" else 0,
        min_connectors=FREE_MIN_CONNECTORS if kind == "free" else 0,
        learner_fr=str(acts.tell.get("learner_fr")) if acts.tell else None,
        draft_fr=proof["draft"] if proof else None,
        proof=proof["proof"] if proof else None,  # type: ignore[arg-type]
        marks=[RvComptoirMark(span_fr=str(m.get("span_fr")), start=int(m.get("start") or 0), kind=str(m.get("kind")),  # type: ignore[arg-type]
                              why=pourquoi.hint_of(m))
               for m in (proof["marks"] if proof else []) if isinstance(m, dict) and m.get("kind") in comptoir_loop.MARK_KINDS],
        tries=proof["tries"] if proof else 0,
        max_tries=FIX_TRIES,
        printed_fr=proof["printed"] if proof else None,
        # «Le pourquoi», once settled: the counter's notes, from the same rounds of marks.
        notes=[RvComptoirNote(**note) for note in pourquoi.notes_of(pourquoi.rounds_of(acts.tell, acts.fixes),
                                                                     proof["proof"])
               if note["kind"] in comptoir_loop.MARK_KINDS] if proof else [],
    )


# ---------------------------------------------------------------------------
# The acts
# ---------------------------------------------------------------------------


def _out_of_order(step: str, act: str) -> RevueError:
    return RevueError(409, "revue_fil_out_of_order", step=step, act=act)


def _bad(act: str) -> RevueError:
    return RevueError(422, "revue_fil_bad_act", act=act)


def apply_act(encounter: RevueEncounter, loaded: Loaded, body: RvFilRequest) -> RvFilError | None:
    """Record one act (or nothing, when it repeats one already recorded); returns the reason
    for an act the learner can fix on the same screen. Raises
    :class:`~app.services.revue.encounter.RevueError` for an act out of order or a bad value."""

    state = loaded.state
    wire = wire_of(loaded)
    band = band_of(loaded)
    seed = str(loaded.row.id)
    acts = Acts(state)
    step = step_of(acts, closed=state.closed)
    act = body.act
    if state.closed:
        raise _out_of_order(step, act)

    if act == "open":
        if not acts.opened:
            state.append("fil", act="open")
        return None

    if act == "order":
        keys = list(body.order or [])
        if sorted(keys) != sorted(KEYS):
            raise _bad(act)
        if acts.order_resolved or (acts.orders and acts.orders[-1].get("order") == keys):
            return None  # a repeat, or the order is settled
        if not acts.opened:
            raise _out_of_order(step, act)
        graded = grade_order(seed, keys)
        state.append("fil", act="order", order=keys, correct=graded["correct"], hint=graded["hint"],
                     attempt=len(acts.orders) + 1)
        return None

    if act == "words":
        picks = list(body.picks or [])
        if acts.words_resolved or (acts.words and acts.words[-1].get("picks") == picks):
            return None
        if not acts.order_resolved:
            raise _out_of_order(step, act)
        graded = grade_words(wire, band, seed, picks)
        if graded is None:
            if len(picks) != 4:
                return RvFilError(code="pick_all")
            raise _bad(act)
        state.append("fil", act="words", picks=picks, correct=graded["correct"], misses=graded["misses"],
                     attempt=len(acts.words) + 1)
        return None

    if act == "tell":
        if acts.tell is not None:
            return None  # a double submit returns the stored result
        if not acts.words_resolved:
            raise _out_of_order(step, act)
        return _tell(encounter, loaded, wire, band=band, seed=seed, body=body)

    if act == "tell_fix":
        return _tell_fix(encounter, loaded, wire, acts, step=step, body=body)

    raise _bad(act)


def _tell(encounter: RevueEncounter, loaded: Loaded, wire: FilWire, *, band: str, seed: str,
          body: RvFilRequest) -> RvFilError | None:
    state = loaded.state
    typed = ""
    check: dict[str, Any] = {"proof": "clean", "target": "", "marks": [], "cost": 0.0, "refused": None, "source": "tiles"}
    kind = tell_input(band)
    if kind == "tiles":
        parts = list(body.parts or [])
        why = tiles_problem(wire, band, seed, parts)
        if why is not None:
            return why
        rows, indices = _by_id(wire, band), index_of(seed)
        learner = a1_telling(rows[parts[0]], tile_of(wire, indices[parts[1]]).fr,
                             rows[parts[2]], tile_of(wire, indices[parts[3]]).fr)
        check["target"] = learner
    elif kind == "frames":
        texts = [re.sub(r"\s+", " ", t or "").strip() for t in (body.texts or [])]
        why = too_short(band, texts=texts)
        if why is not None:
            return why
        typed = " ".join(texts)
        learner = a2_telling(list(wire.telling.frames), texts)
        check = _proofread(encounter, loaded, wire, band=band, learner_fr=learner)
    else:
        typed = re.sub(r"\s+", " ", body.text or "").strip()
        why = too_short(band, text=typed)
        if why is not None:
            return why
        learner = comptoir_loop._sentence_end(typed)  # noqa: SLF001
        check = _proofread(encounter, loaded, wire, band=band, learner_fr=learner)
    state.append("turn_learner", text_fr=learner, mode=body.mode, fil="tell")
    state.append("fil", act="tell", learner_fr=learner, typed_fr=typed, parts=list(body.parts or []),
                 proof=check["proof"], target_fr=check["target"], marks=check["marks"], source=check["source"],
                 cost_usd=check["cost"], refused=check["refused"],
                 prompt_version=edit_prompt_version() if kind != "tiles" else None)
    return None


def _tell_fix(encounter: RevueEncounter, loaded: Loaded, wire: FilWire, acts: Acts, *, step: str,
              body: RvFilRequest) -> RvFilError | None:
    """The learner's fix of Romy's marks: as ``comptoir_loop._opinion_fix``."""

    state = loaded.state
    band = band_of(loaded)
    proof = acts.proof
    if proof is None:
        raise _out_of_order(step, "tell_fix")
    if proof["proof"] != "marked":
        return None  # settled: a repeat
    if body.value == "romy":
        if proof["tries"] < 1:
            raise _out_of_order(step, "tell_fix")
        state.append("fil", act="tell_fix", by="romy", proof="corrected", target_fr=proof["target"])
        _settle(encounter, loaded, acts, "corrected")
        return None
    text = re.sub(r"\s+", " ", body.text or "").strip()
    if comptoir.word_count(text) < (A2_MIN_WORDS if band == "A2" else FREE_MIN_WORDS):
        return RvFilError(code="too_short", count=A2_MIN_WORDS if band == "A2" else FREE_MIN_WORDS)
    learner = comptoir_loop._sentence_end(text)  # noqa: SLF001
    if comptoir_loop._proof_key(learner) == comptoir_loop._proof_key(proof["draft"]):  # noqa: SLF001
        return RvFilError(code="nothing_changed")
    tries = proof["tries"] + 1
    state.append("turn_learner", text_fr=learner, mode=body.mode, fil="tell_fix")
    row: dict[str, Any] = {"text_fr": learner, "typed_fr": text, "try": tries, "cost_usd": 0.0}
    if comptoir_loop._proof_key(learner) == comptoir_loop._proof_key(proof["target"]):  # noqa: SLF001
        row.update(proof="fixed", target_fr=proof["target"])
    else:
        check = _proofread(encounter, loaded, wire, band=band, learner_fr=learner)
        row.update(cost_usd=check["cost"], refused=check["refused"], prompt_version=edit_prompt_version())
        if check["proof"] == "as_written":
            row.update(proof="as_written", target_fr="")
        elif check["proof"] == "clean":
            row.update(proof="fixed", target_fr=check["target"])
        elif tries >= FIX_TRIES:
            row.update(proof="corrected", target_fr=check["target"])
        else:
            row.update(proof="marked", target_fr=check["target"], marks=check["marks"])
    state.append("fil", act="tell_fix", **row)
    _settle(encounter, loaded, acts, str(row.get("proof")))
    return None


def _settle(encounter: RevueEncounter, loaded: Loaded, acts: Acts, proof: str) -> None:
    """«Le pourquoi», as at the counter (``comptoir_loop._settle``): once the marks are settled
    the slips go to the learner's error memory (``acts`` as they were before this fix)."""

    if pourquoi.enabled() and proof in {"fixed", "corrected"}:
        pourquoi.remember(encounter.db, loaded.row.user_id, pourquoi.rounds_of(acts.tell, acts.fixes), proof,
                          session_id=str(loaded.row.id), dossier_id=loaded.dossier.id)


def edit_prompt_version() -> str:
    """The ``fil_edit`` prompt in use: v2 with «Le pourquoi» on (``pourquoi.py``), else v1."""

    return pourquoi.FIL_PROMPT_VERSION if pourquoi.enabled() else FIL_EDIT_PROMPT_VERSION


# ---------------------------------------------------------------------------
# Romy's check (one model call at A2+, one more per fix)
# ---------------------------------------------------------------------------

FIL_EDIT_INSTRUCTIONS = """You are Romy Tremblay, a Québécoise journalist. Your trainee, a French learner, just
retold a news story in two sentences with sequence words («d'abord», «ensuite», «enfin»…). You proofread it like
an editor who marks the copy and gives it back: the learner fixes it. From INPUT answer with ONE JSON object:
{"edited_fr": str, "marks": [{"span_fr": str, "kind": str}]}
RULES
- edited_fr: learner_fr with its mistakes corrected and nothing else: grammar, agreement, conjugation, gender,
  spelling, accents, word order, a missing word. Keep the learner's words, meaning, order of events and sequence
  words; never fix style, never swap a correct word for a nicer one, never add a fact, a number, a name or an
  idea. If learner_fr is already correct, copy it unchanged. If it is not French, put the learner's idea into
  simple French.
- marks: one per mistake you corrected, at most three, none when nothing changed. span_fr is the learner's wrong
  words exactly as they appear in learner_fr (for a missing word, the word just before the gap); kind is one of
  accord (agreement), conjugaison (verb form or tense), genre (gender), orthographe (spelling or accents), mot
  (wrong word), ordre (word order), manque (a missing word).
- French typography: a space before ? ! : ;"""

FIL_EDIT_SYSTEM = ("You proofread learners' French like a kind newspaper editor who marks mistakes for the "
                   "learner to fix. Answer with one JSON object only.")


def edit_context(dossier: EditorialDossier, wire: FilWire, *, band: str, learner_fr: str) -> dict[str, Any]:
    return {
        "band": band,
        "learner_fr": learner_fr,
        "events_fr": [strip.for_band(band).fr for strip in wire.strips],
        "facts": [c.fr for c in dossier.claims if c.kind == "fact"],
    }


def check_edit(raw: dict[str, Any], learner_fr: str) -> dict[str, Any]:
    """Romy's correction, checked like the counter's (``comptoir_loop.check_edit``): at most
    1.6× the learner's length, no new number, no app words; marks whose words are the learner's."""

    out: dict[str, Any] = {"_problems": []}
    edited = re.sub(r"\s+", " ", str(raw.get("edited_fr") or "")).strip()
    learner_words = comptoir.word_count(learner_fr)
    if not edited:
        out["_problems"].append("edit:empty")
    elif comptoir.word_count(edited) > max(4, int(EDIT_MAX_RATIO * learner_words)):
        out["_problems"].append("edit:too_long")
    elif comptoir.numbers(edited) - comptoir.numbers(learner_fr):
        out["_problems"].append("edit:new_number")
    elif voice.app_words(edited) or voice.meta_words(edited) or voice.id_leaks(edited):
        out["_problems"].append("edit:app_words")
    else:
        out["edited_fr"] = voice.french_typography(edited)
        marks = []
        for row in raw.get("marks") or []:
            if not isinstance(row, dict) or len(marks) >= 2 * comptoir_loop.MARKS_MAX:
                continue
            span = re.sub(r"\s+", " ", str(row.get("span_fr") or "")).strip(" .,!?")
            kind = str(row.get("kind") or "").strip().lower()
            if span and kind in comptoir_loop.MARK_KINDS and span.lower() in learner_fr.lower():
                marks.append({"span_fr": span, "kind": kind})
        out["marks"] = marks
    return out


def _proofread(encounter: RevueEncounter, loaded: Loaded, wire: FilWire, *, band: str, learner_fr: str) -> dict[str, Any]:
    """One model call (``provider.fil_edit``): Romy's corrected telling, kept back as the
    target, and her marks (``comptoir_loop.proof_marks``). ``as_written`` when the call or its
    checks fail: the telling then prints as the learner wrote it, said so."""

    out: dict[str, Any] = {"proof": "as_written", "target": "", "marks": [], "source": "fallback", "cost": 0.0,
                           "refused": None}
    edit = getattr(encounter.provider, "fil_edit", None)
    if not callable(edit):
        return out
    context = edit_context(loaded.dossier, wire, band=band, learner_fr=learner_fr)
    language = pourquoi.explain_language(encounter, loaded) if pourquoi.enabled() else None
    if language:
        context[pourquoi.EXPLAIN_KEY] = language
    before = meter(encounter.provider)
    try:
        raw = edit(context)
    except Exception as exc:  # noqa: BLE001 - the learner's text stands
        logger.bind(session_id=str(loaded.row.id)).warning("revue fil: edit failed ({})", exc)
        raw = None
    out["cost"] = round(meter(encounter.provider) - before, 6)
    if not isinstance(raw, dict):
        return out
    checked = check_edit(raw, learner_fr)
    out["refused"] = checked.get("_problems") or None
    if checked.get("edited_fr"):
        marks = comptoir_loop.proof_marks(learner_fr, checked["edited_fr"], checked.get("marks") or [])
        if language and marks:  # «Le pourquoi»: the counter's checked whys; no regulars' takes here
            marks = pourquoi.explain_marks(marks, raw.get("marks"), learner_fr=learner_fr, target_fr=checked["edited_fr"],
                                           dossier=loaded.dossier, takes=None, band=band, language=language)
        out.update(target=checked["edited_fr"], marks=marks, proof="marked" if marks else "clean", source="model")
    return out


# ---------------------------------------------------------------------------
# The close: «La page»
# ---------------------------------------------------------------------------


def page_connectors(wire: FilWire, band: str, seed: str, acts: Acts) -> list[str]:
    """The sequence word printed before each strip: the learner's when they were right, else
    the right ones."""

    rows = _by_id(wire, band)
    right = next((r.get("picks") for r in acts.words if r.get("correct")), None)
    ids = list(right) if right else solution_words(wire, band, seed)
    return [rows[i].fr for i in ids]


def close_fil(encounter: RevueEncounter, loaded: Loaded) -> tuple[Any, RvClosing]:
    """«La page»: no model call. The telling must be settled first."""

    from app.services.revue.carte import keep_papier_words

    row, dossier, plan, state = loaded.row, loaded.dossier, loaded.plan, loaded.state
    existing = _closing_of(state)
    if existing is not None:
        return session_view(loaded), existing
    wire = wire_of(loaded)
    band = band_of(loaded)
    seed = str(row.id)
    acts = Acts(state)
    proof = acts.proof
    if proof is None or not acts.settled:
        raise RevueError(409, "revue_fil_out_of_order", step=step_of(acts, closed=False), act="close")
    printed = str(proof["printed"] or "")
    own = acts.own_words()
    connectors = page_connectors(wire, band, seed, acts)
    texts = [strip.for_band(band).fr for strip in wire.strips]
    page = RvFilPage(
        title_fr=dossier.title_fr,
        dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "),
        strips=[RvFilPageStrip(connector_fr=_cap(word), text_fr=text) for word, text in zip(connectors, texts, strict=True)],
        mine_fr=printed,
        proof=proof["proof"],
        phrase_fr=wire.telling.phrase.for_band(band).fr,
        words=[],
    )
    contribution = contribution_spans(own, printed)
    state.append("artifact", kind="fil", text_fr=printed, learner_fr=own, contribution=contribution,
                 proof=proof["proof"])
    claims = dossier.claims_by_id()
    shown = [claims[cid] for cid in dict.fromkeys(strip.claim_id for strip in wire.strips) if cid in claims]
    sources = [_source(dossier, sid) for sid in dict.fromkeys(c.source_id for c in shown)]
    names = list(dict.fromkeys(source.name for source in sources))
    byline = "Romy Tremblay, avec toi" if contribution else "Romy Tremblay"
    dispatch = RvDispatch(
        kicker_fr=KICKER,
        headline_fr=dossier.title_fr,
        body_fr=[*texts, f"Toi : « {printed} »"],
        contribution=[],
        byline_fr=f"{byline} · d'après " + " et ".join(names) if names else byline,
        sources=sources,
    )
    met = [dossier.lead_for(band).fr, *texts, *(c.fr for c in shown)]
    kept = RvKept(words=kept_words(plan, state, met=met, used=[own]), claims=[rv_claim(dossier, c) for c in shown])
    page.words = [word.fr for word in kept.words]
    closing = RvClosing(romy_line_fr=ROMY_CLOSE_LINE, dispatch=dispatch, kept=kept, question_kept_fr=None,
                        colophon_fr=colophon_for(row.week), fil_page=page)  # type: ignore[arg-type]
    closing.vignette = encounter._mint_vignette(loaded, kind="fil", kept_contribution=bool(contribution))  # noqa: SLF001
    keep_papier_words(encounter.db, row, dossier=dossier, plan=plan, state=state, kept=kept)

    state.append("turn_romy", beat="close", role="close", text_fr=ROMY_CLOSE_LINE, cost_usd=0.0)
    state.append("closed", closing=closing.model_dump(mode="json"))
    row.status = "closed"
    row.closed_at = datetime.now(UTC)
    encounter._remember(loaded, artifact=state.current_artifact, kind="fil")  # noqa: SLF001
    encounter._record_cost(loaded)  # noqa: SLF001
    encounter._save(loaded)  # noqa: SLF001
    try:
        from app.services.revue import carte as _carte

        _carte.invalidate(row.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("revue: carte invalidate skipped ({})", exc)
    return session_view(loaded), closing


__all__ = [
    "Acts",
    "FIL_EDIT_INSTRUCTIONS",
    "a1_telling",
    "apply_act",
    "close_fil",
    "connectors_used",
    "fil_view",
    "grade_order",
    "grade_words",
    "shown_order",
    "step_of",
]
