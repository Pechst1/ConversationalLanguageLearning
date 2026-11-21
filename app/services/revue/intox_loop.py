"""«L'intox express»: the learner's loop (WP-119 «les rubriques», owner 2026-11-20).

Four screens — read, «Vrai ou faux», «Corrige», the page — played from the round the desk
wrote (``intox.py``) and snapshotted on the session's first ``choice`` event
(``mode="intox"``). As «Le fil» (``fil_loop.py``): the server owns the state, every act is one
``intox`` event in the append-only log, the step is derived by replay (:func:`step_of`), an
act out of order is a 409 with the same view, and an act that repeats one already recorded
records nothing. No model call anywhere: every grade is deterministic.

Acts, in order (``POST /revue/sessions/{id}/rubrique``):

- ``open``: the learner read the story. The lead stays reachable during the round.
- ``answer {key, value: vrai | faux}``: the statements one at a time, in the session's order,
  one answer each, no timer. The verdict follows; on a false statement or a miss, the claim's
  verbatim quote (with the outlet's name) and the words in it that settle it, and one line in
  the learner's language. The view never says whether a statement is false before it is answered.
- ``fix {key, value | text}``: each false statement made true. A1–A2 pick between the true
  value and another of the same kind from the claims; B1+ rewrite the statement, graded as
  the comptoir's correction (``comptoir_loop.grade_fix``: the true value, numbers compared
  digit for digit, never the false one). Two tries; the true value only after the second miss.

The close (:func:`close_intox`) makes no model call: «La page», the dispatch, the ``intox``
artifact, the vignette, the kept words, Romy's memory.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.schemas.revue import (
    RvClosing,
    RvComptoirRead,
    RvComptoirText,
    RvDispatch,
    RvIntoxCard,
    RvIntoxFix,
    RvIntoxFixItem,
    RvIntoxPage,
    RvIntoxPageLine,
    RvIntoxRound,
    RvIntoxView,
    RvKept,
    RvRubriqueError,
    RvRubriqueQuote,
    RvRubriqueRequest,
)
from app.services.revue import comptoir, comptoir_loop
from app.services.revue.dossier import ComptoirText, IntoxExpress, IntoxStatement, comptoir_band
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
    rv_claim,
    session_view,
)
from app.services.revue.fil_loop import _rng

if TYPE_CHECKING:  # pragma: no cover
    from app.services.revue.encounter import RevueEncounter

KIND = "intox"
STEPS: tuple[str, ...] = ("read", "round", "fix", "page")
KEYS: tuple[str, ...] = ("a", "b", "c", "d", "e")
MAX_TRIES = 2
ANSWERS: tuple[str, ...] = ("vrai", "faux")
FIX_MAX_CHARS = 300

ROMY_CLOSE_LINE = "Bien joué ! L'intox est démontée, et ta page est dans le journal."
KICKER = "L'intox express de Romy"


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class Acts:
    """The learner's acts so far, replayed from the ``intox`` events."""

    def __init__(self, state: Any) -> None:
        self.opened = False
        self.answers: dict[str, dict[str, Any]] = {}
        self.fixes: dict[str, list[dict[str, Any]]] = {}
        for event in state.events:
            if event.kind != KIND:
                continue
            payload = event.payload
            act = payload.get("act")
            key = str(payload.get("key") or "")
            if act == "open":
                self.opened = True
            elif act == "answer" and key not in self.answers:
                self.answers[key] = dict(payload)
            elif act == "fix" and not self.fix_resolved(key):
                self.fixes.setdefault(key, []).append(dict(payload))

    def fix_resolved(self, key: str) -> bool:
        rows = self.fixes.get(key) or []
        return any(row.get("correct") for row in rows) or len(rows) >= MAX_TRIES

    def fix_correct(self, key: str) -> bool:
        return any(row.get("correct") for row in self.fixes.get(key) or [])

    def score(self) -> int:
        return sum(1 for row in self.answers.values() if row.get("correct"))


def express_of(loaded: Loaded) -> IntoxExpress:
    express = loaded.dossier.intox
    if express is None:  # an intox session always snapshots its round; keep the view total anyway
        raise RevueError(409, "revue_not_intox")
    return express


def band_of(loaded: Loaded) -> str:
    return str(loaded.plan.learner.band)


def shown_order(seed: str) -> list[int]:
    """The statements' indices in the order the session shows them (per session)."""

    order = [0, 1, 2, 3, 4]
    _rng(seed, "intox-order").shuffle(order)
    return order


def key_of(seed: str) -> dict[int, str]:
    return {index: KEYS[position] for position, index in enumerate(shown_order(seed))}


def index_of(seed: str) -> dict[str, int]:
    return {key: index for index, key in key_of(seed).items()}


def false_keys(express: IntoxExpress, seed: str) -> list[str]:
    """The false statements' keys, in the order they were shown."""

    keys = key_of(seed)
    return [keys[i] for i in shown_order(seed) if not express.statements[i].true]


def step_of(express: IntoxExpress, seed: str, acts: Acts, *, closed: bool) -> str:
    if closed:
        return "page"
    if not acts.opened:
        return "read"
    if len(acts.answers) < len(KEYS):
        return "round"
    if not all(acts.fix_resolved(key) for key in false_keys(express, seed)):
        return "fix"
    return "page"


def current_key(seed: str, acts: Acts) -> str | None:
    """The statement to answer next: the first unanswered one in the session's order."""

    return next((key for key in KEYS if key not in acts.answers), None)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def grade_answer(statement: IntoxStatement, value: str) -> bool:
    return (value == "vrai") == statement.true


def fix_input(band: str) -> str:
    return "pick" if comptoir_band(band) in {"a1", "a2"} else "write"


def options_for(statement: IntoxStatement, seed: str, key: str) -> list[str]:
    """A1–A2: the true value and the distractor, in a per-session order."""

    options = [str(statement.right_fr), str(statement.distractor_fr)]
    _rng(f"{seed}:{key}", "intox-options").shuffle(options)
    return options


def grade_fix(statement: IntoxStatement, *, value: str | None = None, text: str | None = None) -> bool:
    """As the comptoir's correction (``comptoir_loop.grade_fix``): a pick is the true value; a
    sentence carries the true value (numbers digit for digit, with what they count) and not
    the false one."""

    value_of = SimpleNamespace(right_fr=statement.right_fr, wrong_fr=statement.wrong_fr)
    if text is not None:
        head, folded = str(text), comptoir.ci(text)
        cut = folded.rfind(", pas ")
        cut = cut if cut >= 0 else folded.rfind(" pas ")
        if cut > 0:
            head = head[:cut]
        if comptoir.contains(head, str(statement.wrong_fr)):
            return False  # the false value still stands («…, pas le 14 juillet» is fine)
    return comptoir_loop.grade_fix(value_of, value=value, text=text)  # type: ignore[arg-type]


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


def read_of(loaded: Loaded, language: str) -> RvComptoirRead:
    dossier = loaded.dossier
    lead = dossier.lead_for(band_of(loaded))
    return RvComptoirRead(
        dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "),
        lead=RvComptoirText(fr=lead.fr, tr=lead.translation(language) if language != "fr" else None),
        sources=[_source(dossier, s.id) for s in dossier.sources[:1]],
    )


def quote_of(statement: IntoxStatement) -> RvRubriqueQuote:
    return RvRubriqueQuote(quote_fr=statement.quote_fr, settles_fr=statement.settles_fr,
                           source_name=statement.source_name)


def intox_view(loaded: Loaded) -> RvIntoxView:
    """What the player shows: the current step and only what that step may know."""

    dossier, plan, state, row = loaded.dossier, loaded.plan, loaded.state, loaded.row
    express = express_of(loaded)
    band = band_of(loaded)
    language = _gloss_language_of(plan)
    seed = str(row.id)
    acts = Acts(state)
    step = step_of(express, seed, acts, closed=state.closed)
    at = STEPS.index(step)
    keys = key_of(seed)

    round_ = None
    if at >= STEPS.index("round"):
        cards = []
        for index in shown_order(seed):
            statement, key = express.statements[index], keys[index]
            answer = acts.answers.get(key)
            card = RvIntoxCard(key=key, text=_ct(statement.for_band(band), language))
            if answer is not None:
                correct = bool(answer.get("correct"))
                card.answer = answer.get("value")
                card.true, card.correct = statement.true, correct
                card.why = _ct(statement.why, language)
                if not statement.true or not correct:
                    card.quote = quote_of(statement)
                card.wrong_fr = statement.wrong_fr
            cards.append(card)
        round_ = RvIntoxRound(cards=cards, current=current_key(seed, acts), score=acts.score(),
                              answered=len(acts.answers), total=len(KEYS))

    fix = None
    if at >= STEPS.index("fix"):
        indices = index_of(seed)
        kind = fix_input(band)
        items = []
        for key in false_keys(express, seed):
            statement = express.statements[indices[key]]
            rows = acts.fixes.get(key) or []
            resolved = acts.fix_resolved(key)
            items.append(RvIntoxFixItem(
                key=key,
                text=_ct(statement.for_band(band), language),
                wrong_fr=str(statement.wrong_fr),
                options=options_for(statement, seed, key) if kind == "pick" else [],
                quote=quote_of(statement),
                tries=len(rows),
                attempts=[str(r.get("value") or r.get("text") or "") for r in rows],
                resolved=resolved,
                correct=acts.fix_correct(key) if resolved else None,
                right_fr=statement.right_fr if resolved else None,
                fixed=_ct(statement.fixed.for_band(band), language) if resolved and statement.fixed else None,
            ))
        fix = RvIntoxFix(input=kind, phrase=_ct(express.phrase.for_band(band), language), items=items)  # type: ignore[arg-type]

    return RvIntoxView(step=step, steps=list(STEPS), band=comptoir_band(band), title_fr=dossier.title_fr,  # type: ignore[arg-type]
                       read=read_of(loaded, language), round=round_, fix=fix)


view = intox_view


# ---------------------------------------------------------------------------
# The acts
# ---------------------------------------------------------------------------


def _out_of_order(step: str, act: str) -> RevueError:
    return RevueError(409, "revue_intox_out_of_order", step=step, act=act)


def _bad(act: str) -> RevueError:
    return RevueError(422, "revue_intox_bad_act", act=act)


def apply_act(encounter: RevueEncounter, loaded: Loaded, body: RvRubriqueRequest) -> RvRubriqueError | None:
    """Record one act (or nothing, when it repeats one already recorded); returns the reason
    for an act the learner can fix on the same screen. Raises
    :class:`~app.services.revue.encounter.RevueError` for an act out of order or a bad value."""

    state = loaded.state
    express = express_of(loaded)
    band = band_of(loaded)
    seed = str(loaded.row.id)
    acts = Acts(state)
    step = step_of(express, seed, acts, closed=state.closed)
    act = body.act
    if state.closed:
        raise _out_of_order(step, act)

    if act == "open":
        if not acts.opened:
            state.append(KIND, act="open")
        return None

    if act == "answer":
        key = str(body.key or "")
        value = str(body.value or "").strip().lower()
        if key not in KEYS or value not in ANSWERS:
            raise _bad(act)
        if key in acts.answers:
            return None  # one answer each: a repeat
        if not acts.opened or key != current_key(seed, acts):
            raise _out_of_order(step, act)
        statement = express.statements[index_of(seed)[key]]
        state.append(KIND, act="answer", key=key, value=value, correct=grade_answer(statement, value),
                     position=len(acts.answers) + 1)
        return None

    if act == "fix":
        key = str(body.key or "")
        if key not in KEYS:
            raise _bad(act)
        if step == "round" or step == "read":
            raise _out_of_order(step, act)
        if key not in false_keys(express, seed):
            raise _bad(act)
        if acts.fix_resolved(key):
            return None
        statement = express.statements[index_of(seed)[key]]
        rows = acts.fixes.get(key) or []
        if fix_input(band) == "pick":
            value = re.sub(r"\s+", " ", body.value or "").strip()
            if value not in options_for(statement, seed, key):
                raise _bad(act)
            if rows and rows[-1].get("value") == value:
                return None
            correct = grade_fix(statement, value=value)
            state.append(KIND, act="fix", key=key, value=value, correct=correct, attempt=len(rows) + 1)
            return None
        text = re.sub(r"\s+", " ", body.text or "").strip()[:FIX_MAX_CHARS]
        if comptoir.word_count(text) < comptoir_loop.FIX_MIN_WORDS:
            return RvRubriqueError(code="too_short", key=key, count=comptoir_loop.FIX_MIN_WORDS)
        if rows and comptoir.ci(rows[-1].get("text")) == comptoir.ci(text):
            return None
        correct = grade_fix(statement, text=text)
        state.append("turn_learner", text_fr=text, mode=body.mode, intox="fix")
        state.append(KIND, act="fix", key=key, text=text, correct=correct, attempt=len(rows) + 1)
        return None

    raise _bad(act)


# ---------------------------------------------------------------------------
# The close: «La page»
# ---------------------------------------------------------------------------


def close(encounter: RevueEncounter, loaded: Loaded) -> tuple[Any, RvClosing]:
    """«La page»: no model call. The round and both corrections must be settled first."""

    from app.services.revue.carte import keep_papier_words

    row, dossier, plan, state = loaded.row, loaded.dossier, loaded.plan, loaded.state
    existing = _closing_of(state)
    if existing is not None:
        return session_view(loaded), existing
    express = express_of(loaded)
    band = band_of(loaded)
    seed = str(row.id)
    acts = Acts(state)
    step = step_of(express, seed, acts, closed=False)
    if step != "page":
        raise RevueError(409, "revue_intox_out_of_order", step=step, act="close")
    keys = key_of(seed)
    lines: list[RvIntoxPageLine] = []
    own: list[str] = []
    for index in shown_order(seed):
        statement, key = express.statements[index], keys[index]
        answer = acts.answers.get(key) or {}
        text = (statement.fixed.for_band(band) if statement.fixed else statement.for_band(band)).fr
        learner = None
        if not statement.true and acts.fix_correct(key):
            right = next((r for r in acts.fixes.get(key) or [] if r.get("correct")), {})
            learner = str(right.get("text") or "") or None
        if learner:
            own.append(learner)
        lines.append(RvIntoxPageLine(text_fr=text, was_false=not statement.true, wrong_fr=statement.wrong_fr,
                                     answered_right=bool(answer.get("correct")), learner_fr=learner,
                                     fixed_right=acts.fix_correct(key) if not statement.true else None))
    score = acts.score()
    fixed = sum(1 for key in false_keys(express, seed) if acts.fix_correct(key))
    page = RvIntoxPage(title_fr=dossier.title_fr, dateline_fr=dateline(dossier, _place(loaded)).rstrip(". "),
                       lines=lines, score=score, total=len(KEYS), fixed=fixed,
                       phrase_fr=express.phrase.for_band(band).fr, words=[])
    learner_fr = " ".join(own)
    summary = f"{score} sur {len(KEYS)}, {fixed} intox corrigée{'s' if fixed > 1 else ''}"
    contribution = contribution_spans(learner_fr, learner_fr) if learner_fr else []
    state.append("artifact", kind=KIND, text_fr=summary, learner_fr=learner_fr, contribution=contribution,
                 score=score, fixed=fixed)
    claims = dossier.claims_by_id()
    shown = [claims[cid] for cid in dict.fromkeys(s.claim_id for s in express.statements) if cid in claims]
    sources = [_source(dossier, sid) for sid in dict.fromkeys(c.source_id for c in shown)]
    names = list(dict.fromkeys(source.name for source in sources))
    byline = "Romy Tremblay, avec toi" if own else "Romy Tremblay"
    dispatch = RvDispatch(
        kicker_fr=KICKER,
        headline_fr=dossier.title_fr,
        body_fr=[line.text_fr for line in lines],
        contribution=[],
        byline_fr=f"{byline} · d'après " + " et ".join(names) if names else byline,
        sources=sources,
    )
    met = [dossier.lead_for(band).fr, *(line.text_fr for line in lines), *(c.fr for c in shown)]
    kept = RvKept(words=kept_words(plan, state, met=met, used=own), claims=[rv_claim(dossier, c) for c in shown])
    page.words = [word.fr for word in kept.words]
    closing = RvClosing(romy_line_fr=ROMY_CLOSE_LINE, dispatch=dispatch, kept=kept, question_kept_fr=None,
                        colophon_fr=colophon_for(row.week), intox_page=page)  # type: ignore[arg-type]
    closing.vignette = encounter._mint_vignette(loaded, kind=KIND, kept_contribution=bool(own))  # noqa: SLF001
    keep_papier_words(encounter.db, row, dossier=dossier, plan=plan, state=state, kept=kept)

    state.append("turn_romy", beat="close", role="close", text_fr=ROMY_CLOSE_LINE, cost_usd=0.0)
    state.append("closed", closing=closing.model_dump(mode="json"))
    row.status = "closed"
    row.closed_at = datetime.now(UTC)
    encounter._remember(loaded, artifact=state.current_artifact, kind=KIND)  # noqa: SLF001
    encounter._record_cost(loaded)  # noqa: SLF001
    encounter._save(loaded)  # noqa: SLF001
    try:
        from app.services.revue import carte as _carte

        _carte.invalidate(row.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("revue: carte invalidate skipped ({})", exc)
    return session_view(loaded), closing


__all__ = ["Acts", "apply_act", "close", "grade_answer", "grade_fix", "intox_view", "shown_order", "step_of", "view"]
