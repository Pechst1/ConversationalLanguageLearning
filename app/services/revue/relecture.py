"""La Relecture (WP-121 B): answer your own question again, six weeks later.

**When** (:func:`eligible`). A closed Papier whose close kept a reader question
(``closing.question_kept_fr``) or a headline the learner wrote (an ``artifact`` of kind
``headline_write``) becomes eligible :data:`RELECTURE_AFTER` (six weeks, owner decision
§5.2) after ``closed_at``, once: a row in ``revue_relectures`` ends it for good.
:func:`offer` deals the oldest eligible one (``GET /revue/relecture/offer``); the pin
card opens it too («Relire ta question»).

**What** (:func:`answer`). The learner answers *the question itself* (or titles the
story again) without seeing their old answer. The new answer is graded with the
phase-2 rubric (``grading.build_rubric`` with the session's own claims and vocabulary,
the encounter's scorer: the critic when a provider is configured, else the deterministic
rubric); the old one with the deterministic rubric (no second model call). Underlined:
the words the rubric flags — ``register`` (tu/vous against the expected one) and
``grammar`` (a target word judged incorrect). Romy says one authored line chosen by band
and flags (:func:`romy_line`). No score, no verdict word.

**Kept** in ``revue_relectures`` (one row per session); :func:`read` shows the pair again
and :func:`marks_for` gives La Carte its «Relire ta question» / «Relue le …» marks.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.models.revue_relecture import RevueRelecture
from app.db.models.revue_session import RevueSession
from app.schemas.revue_carte import CarteRelectureMark
from app.schemas.revue_relecture import RelectureOffer, RelecturePair, RelectureSide, RelectureSpan
from app.services.revue import grading

#: Six weeks, not ten: ten loses too many learners (§4 B.1, decision 2).
RELECTURE_AFTER = timedelta(weeks=6)
#: How many closed Papiers the offer scans (oldest first).
SCAN_LIMIT = 200
HEADLINE_PROMPT_FR = "Quel titre écrirais-tu aujourd'hui pour cette histoire ?"
TODAY_LABEL_FR = "Aujourd'hui"


class RelectureError(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


def _now() -> datetime:
    """The clock (tests shim it)."""

    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _events(row: RevueSession) -> list[dict[str, Any]]:
    from app.services.revue.carte import _events as events

    return events(row.state)


def _week(row: RevueSession) -> str:
    from app.services.revue.carte import _period_week

    return _period_week(row.week)


def _week_label(week: str) -> str:
    number = week.rsplit("W", 1)[-1].lstrip("0") if "W" in week else ""
    return f"Semaine {number}" if number else week


def _material(row: RevueSession) -> dict[str, Any] | None:
    """What the Relecture re-asks for this Papier, and the learner's answer then; None if nothing."""

    from app.services.revue.carte import _closing, _payload, _place, _snapshot

    events = _events(row)
    closing = _closing(events)
    artifacts = [_payload(e) for e in events if e.get("kind") == "artifact"]
    written = next((a for a in reversed(artifacts) if a.get("kind") == "headline_write"), None)
    question = str(closing.get("question_kept_fr") or "").strip()
    learner_turns = [str(_payload(e).get("text_fr") or "") for e in events if e.get("kind") == "turn_learner"]
    if question:
        made = next((a for a in reversed(artifacts) if a.get("kind") == "reader_question"), None)
        asked = next((t for t in reversed(learner_turns) if t.strip().endswith("?")), None)
        then = str((made or {}).get("learner_fr") or asked or question)
        kind, prompt = "question", question
    elif written is not None:
        then = str(written.get("learner_fr") or written.get("text_fr") or "")
        kind, prompt = "headline", HEADLINE_PROMPT_FR
    else:
        return None
    if not then.strip():
        return None
    snapshot = _snapshot(events)
    plan = row.plan if isinstance(row.plan, dict) else {}
    place, geo = _place(plan, snapshot)
    stage = plan.get("stage") if isinstance(plan.get("stage"), dict) else {}
    kept = closing.get("kept") if isinstance(closing.get("kept"), dict) else {}
    return {
        "kind": kind,
        "prompt_fr": prompt,
        "then_fr": then,
        "title_fr": str(snapshot.get("title_fr") or row.dossier_id),
        "place_label_fr": str((geo or {}).get("label_fr") or (place or {}).get("name_fr") or ""),
        "plate_url": str(stage["plate_url"]) if stage.get("plate_url") else None,
        "claims": [c for c in kept.get("claims") or [] if isinstance(c, dict) and c.get("fr")],
        "vocabulary": [v for v in plan.get("vocabulary") or [] if isinstance(v, dict) and v.get("fr")],
        "band": str((plan.get("learner") or {}).get("band") or "A2") if isinstance(plan.get("learner"), dict) else "A2",
        "summary_fr": str(snapshot.get("summary_fr") or ""),
    }


def _offer_of(row: RevueSession, material: dict[str, Any]) -> RelectureOffer:
    closed = _aware(row.closed_at)
    return RelectureOffer(
        session_id=str(row.id),
        week=_week(row),
        kind=material["kind"],
        dossier_title_fr=material["title_fr"],
        prompt_fr=material["prompt_fr"],
        place_label_fr=material["place_label_fr"],
        plate_url=material["plate_url"],
        closed_at=closed.isoformat() if closed else None,
    )


def _has_table(db: Session) -> bool:
    try:
        return inspect(db.get_bind()).has_table(RevueRelecture.__tablename__)
    except Exception:  # noqa: BLE001
        return False


def _done(db: Session, session_ids: list[uuid.UUID]) -> dict[str, RevueRelecture]:
    if not session_ids or not _has_table(db):
        return {}
    rows = db.scalars(select(RevueRelecture).where(RevueRelecture.session_id.in_(session_ids)))
    return {str(row.session_id): row for row in rows}


def eligible(row: RevueSession, *, now: datetime | None = None, done: bool = False) -> bool:
    """Closed six weeks ago or more, with a kept question or a written headline, never re-asked."""

    now = now or _now()
    closed = _aware(row.closed_at)
    if done or row.status != "closed" or closed is None or now - closed < RELECTURE_AFTER:
        return False
    return _material(row) is not None


def _closed(db: Session, user_id: Any) -> list[RevueSession]:
    return list(
        db.scalars(
            select(RevueSession)
            .where(RevueSession.user_id == user_id, RevueSession.status == "closed")
            .order_by(RevueSession.closed_at.asc(), RevueSession.started_at.asc())
            .limit(SCAN_LIMIT)
        )
    )


def offer(db: Session, user: Any, *, now: datetime | None = None) -> RelectureOffer | None:
    """The oldest eligible Papier, or None."""

    rows = _closed(db, user.id)
    done = _done(db, [row.id for row in rows])
    for row in rows:
        if eligible(row, now=now, done=str(row.id) in done):
            material = _material(row)
            if material is not None:
                return _offer_of(row, material)
    return None


def marks_for(db: Session, user_id: Any, *, now: datetime | None = None) -> dict[str, CarteRelectureMark]:
    """La Carte's marks: ``eligible`` («Relire ta question»), ``read`` («Relue le …»)."""

    rows = _closed(db, user_id)
    done = _done(db, [row.id for row in rows])
    marks: dict[str, CarteRelectureMark] = {}
    for row in rows:
        key = str(row.id)
        if key in done:
            asked = _aware(done[key].asked_at)
            marks[key] = CarteRelectureMark(state="read", read_at=asked.isoformat() if asked else None)
        elif eligible(row, now=now):
            marks[key] = CarteRelectureMark(state="eligible")
    return marks


# ---------------------------------------------------------------------------
# Grading and the pair
# ---------------------------------------------------------------------------

_VOUS = re.compile(r"(?<!\w)(vous|votre|vos|pouvez|savez)(?!\w)", re.IGNORECASE)
_TU = re.compile(r"(?<!\w)(tu|toi|ton|ta|tes|t'as)(?!\w)", re.IGNORECASE)


def _rubric(material: dict[str, Any]) -> grading.Rubric:
    claims = [SimpleNamespace(id=str(c.get("id") or f"c{i}"), kind=str(c.get("kind") or "fact"), fr=str(c["fr"]))
              for i, c in enumerate(material["claims"])]
    vocabulary = [SimpleNamespace(fr=str(v["fr"]), claim_id=str(v.get("claim_id") or "")) for v in material["vocabulary"]]
    return grading.build_rubric(
        kind="respond" if material["kind"] == "question" else "headline_write",
        band=material["band"],
        claims=claims,
        vocabulary=vocabulary,
        summary_fr=material["summary_fr"],
    )


def spans_for(text: str, evidence: dict[str, Any]) -> list[RelectureSpan]:
    """The rubric's flags as underlines in ``text``: the incorrect target words (grammar)
    and the tu/vous words that broke the expected register."""

    from app.services.revue.encounter import _without_article, fold_keep_length

    folded = fold_keep_length(text)
    spans: list[RelectureSpan] = []
    for row in evidence.get("word_outcomes") or []:
        if row.get("outcome") != "incorrect":
            continue
        bare = fold_keep_length(_without_article(str(row.get("fr") or "")))
        stem = bare[: max(3, len(bare) - 2)]
        match = re.search(r"(?:(?<=\s)|^)(?:\w+\s|l')?" + re.escape(stem) + r"\w*", folded) if stem else None
        if match:
            spans.append(RelectureSpan(start=match.start(), end=match.end(), flag="grammar"))
    register = evidence.get("register")
    pattern = _VOUS if register == "vous_to_tu" else _TU if register == "tu_to_vous" else None
    if pattern is not None:
        spans += [RelectureSpan(start=m.start(), end=m.end(), flag="register") for m in pattern.finditer(text)]
    spans.sort(key=lambda s: s.start)
    merged: list[RelectureSpan] = []
    for span in spans:
        if merged and span.start < merged[-1].end:
            continue
        merged.append(span)
    return merged


#: Romy's one line (§4 B.2): what she notices, one thing, kindly. By band (A = A1/A2,
#: B = B1 and up) and the first flag that applies.
ROMY_LINES: dict[str, dict[str, str]] = {
    "register": {
        "A": "Avec moi, c'est « tu », pas « vous ». Le reste, je le comprends.",
        "B": "Juste une chose : entre nous, c'est « tu ». Ta pensée, elle, est claire.",
    },
    "grammar": {
        "A": "Un mot à revoir, je l'ai souligné. Ton idée est là.",
        "B": "Un petit mot souligné, à revoir. L'idée tient debout.",
    },
    "cleared": {
        "A": "Tu vois ? Le mot souligné en semaine {week} a disparu.",
        "B": "Ce que j'avais souligné en semaine {week}, tu ne le fais plus.",
    },
    "longer": {
        "A": "Tu en dis plus qu'en semaine {week}.",
        "B": "Tu en dis davantage qu'en semaine {week}, et ça se lit.",
    },
    "same": {
        "A": "C'est la même idée, avec tes mots d'aujourd'hui.",
        "B": "La même pensée, dite autrement. C'est ça, relire.",
    },
}


def romy_line(*, band: str, week: str, then_spans: list[RelectureSpan], now_spans: list[RelectureSpan],
              then_fr: str, now_fr: str) -> str:
    tier = "A" if str(band or "").upper().startswith("A") else "B"
    flags = {span.flag for span in now_spans}
    if "register" in flags:
        key = "register"
    elif "grammar" in flags:
        key = "grammar"
    elif then_spans:
        key = "cleared"
    elif len(now_fr.split()) > len(then_fr.split()) + 2:
        key = "longer"
    else:
        key = "same"
    number = week.rsplit("W", 1)[-1].lstrip("0") if "W" in week else week
    return ROMY_LINES[key][tier].format(week=number)


def _pair(row: RevueSession, material: dict[str, Any], stored: RevueRelecture) -> RelecturePair:
    evidence = stored.evidence if isinstance(stored.evidence, dict) else {}
    asked = _aware(stored.asked_at)
    return RelecturePair(
        session_id=str(row.id),
        offer=_offer_of(row, material),
        then=RelectureSide(label_fr=_week_label(_week(row)), text_fr=material["then_fr"],
                           spans=[RelectureSpan(**s) for s in evidence.get("then_spans") or []]),
        now=RelectureSide(label_fr=TODAY_LABEL_FR, text_fr=stored.answer_fr,
                          spans=[RelectureSpan(**s) for s in evidence.get("now_spans") or []]),
        romy_line_fr=str(evidence.get("romy_line_fr") or ROMY_LINES["same"]["A"]),
        asked_at=asked.isoformat() if asked else "",
    )


def _owned(db: Session, user: Any, session_id: str) -> RevueSession:
    try:
        key = uuid.UUID(str(session_id))
    except ValueError as exc:
        raise RelectureError(404, "relecture_session_not_found") from exc
    row = db.scalar(select(RevueSession).where(RevueSession.id == key, RevueSession.user_id == user.id))
    if row is None:
        raise RelectureError(404, "relecture_session_not_found")
    return row


def answer(
    db: Session,
    user: Any,
    session_id: str,
    *,
    answer_fr: str,
    mode: str = "text",
    scorer: grading.RubricScorer | None = None,
    now: datetime | None = None,
) -> RelecturePair:
    """Store the learner's second answer and return the pair. 409 when not (or no longer) eligible."""

    now = now or _now()
    row = _owned(db, user, session_id)
    text = " ".join(str(answer_fr or "").split())[:600]
    if not text:
        raise RelectureError(422, "relecture_empty")
    if _done(db, [row.id]):
        raise RelectureError(409, "relecture_done")
    material = _material(row)
    if material is None:
        raise RelectureError(409, "relecture_nothing_to_reread")
    if not eligible(row, now=now):
        raise RelectureError(409, "relecture_not_yet")
    rubric = _rubric(material)
    fake = grading.FakeRubricScorer()
    now_evidence = grading.grade(text, rubric, scorer or fake, fallback=fake, force=True)
    then_evidence = grading.grade(material["then_fr"], rubric, grading.FakeRubricScorer(), force=True)
    now_spans = spans_for(text, now_evidence)
    then_spans = spans_for(material["then_fr"], then_evidence)
    line = romy_line(band=material["band"], week=_week(row), then_spans=then_spans, now_spans=now_spans,
                     then_fr=material["then_fr"], now_fr=text)
    stored = RevueRelecture(
        user_id=user.id,
        session_id=row.id,
        asked_at=now,
        answer_fr=text,
        mode=mode if mode in {"text", "voice"} else "text",
        evidence={
            "rubric_version": rubric.rubric_id,
            "now": {k: now_evidence.get(k) for k in ("outcome", "word_outcomes", "fact_fit", "register", "band_fit", "scorer", "cost_usd")},
            "then": {k: then_evidence.get(k) for k in ("outcome", "word_outcomes", "fact_fit", "register", "band_fit")},
            "now_spans": [s.model_dump() for s in now_spans],
            "then_spans": [s.model_dump() for s in then_spans],
            "romy_line_fr": line,
        },
    )
    db.add(stored)
    db.flush()
    return _pair(row, material, stored)


def read(db: Session, user: Any, session_id: str) -> RelecturePair:
    """The stored pair, again (the pin card's «Relue le …»)."""

    row = _owned(db, user, session_id)
    stored = _done(db, [row.id]).get(str(row.id))
    material = _material(row)
    if stored is None or material is None:
        raise RelectureError(404, "relecture_not_found")
    return _pair(row, material, stored)


__all__ = [
    "RELECTURE_AFTER",
    "ROMY_LINES",
    "RelectureError",
    "answer",
    "eligible",
    "marks_for",
    "offer",
    "read",
    "romy_line",
    "spans_for",
]
