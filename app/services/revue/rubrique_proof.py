"""«La photo» and «Le micro»: Romy's edit, shared (WP-119 «les rubriques», 2026-11-21).

The learner's own French (a caption, three interview questions) goes through the same path as
«Le titre»'s headline (``titre_loop._proofread`` / ``_build_fix``) and «Le fil»'s telling:

- :func:`proofread`: ONE model call (``provider.rubrique_edit``), checked as «Le fil»'s
  (``fil_loop.check_edit``: no new number, no app word, marks on the learner's own words),
  kept back: the learner sees her marks (with «Le pourquoi» on, each opens its rule in the
  mother tongue, never the answer) and fixes them first. The call failing, or its checks,
  leaves the French as written (a learner never sees a wrong correction).
- :class:`Trail`: where the French stands before print, replayed from the first act and the
  fixes (``proof``: ``clean`` | ``marked`` | ``fixed`` | ``corrected`` | ``as_written``).
- :func:`fix_row`: one fix (``{text}``, or ``{value: "romy"}`` after a first try).
- :func:`marks_view`, :func:`notes_view`: what the screen shows of them.
- :func:`settle`: once settled, the slips go to the learner's error memory («Le pourquoi»).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from loguru import logger

from app.schemas.revue import RvComptoirMark, RvComptoirNote, RvRubriqueError
from app.services.revue import comptoir, comptoir_loop, fil_loop, pourquoi, voice
from app.services.revue.encounter import meter

FIX_TRIES = comptoir_loop.FIX_TRIES
EDIT_PROMPT_VERSION = "rubrique-edit-v1"
EDIT_PROMPT_VERSION_POURQUOI = "rubrique-edit-v2"

_WHAT: dict[str, str] = {
    "photo": "a caption for a picture of a news story (what the picture shows, then the news)",
    "micro": "the questions they asked a witness for a news story, one after the other, each ending with « ?»",
}

EDIT_INSTRUCTIONS = """You are Romy Tremblay, a Québécoise journalist. Your trainee, a French learner, just
wrote {what}. You proofread it like an editor who marks the copy and gives it back: the learner fixes it. From INPUT
answer with ONE JSON object:
{"edited_fr": str, "marks": [{"span_fr": str, "kind": str}]}
RULES
- edited_fr: learner_fr with its mistakes corrected and nothing else: grammar, agreement, conjugation, gender,
  spelling, accents, word order, a missing word; for a question, also its form (inversion or «est-ce que» after a
  question word in writing; INPUT.slips names what the app already saw). Keep the learner's words and meaning and
  as many sentences or questions as they wrote. Never fix style, never swap a correct word for a nicer one, never
  add a fact, a number, a name or an idea. If learner_fr is already correct, copy it unchanged. If it is not
  French, put the learner's idea into simple French.
- marks: one per mistake you corrected, at most three, none when nothing changed. span_fr is the learner's wrong
  words exactly as they appear in learner_fr (for a missing word, the word just before the gap); kind is one of
  accord (agreement), conjugaison (verb form or tense), genre (gender), orthographe (spelling or accents), mot
  (wrong word), ordre (word order), manque (a missing word).
- French typography: a space before ? ! : ;"""

EDIT_SYSTEM = ("You proofread learners' French like a kind newspaper editor who marks mistakes for the learner to "
               "fix. Answer with one JSON object only.")


def edit_instructions(context: dict[str, Any] | None) -> str:
    """The ``rubrique_edit`` instructions for ``context`` (its ``kind``: photo | micro):
    v1, or v2 with the marks' ``why_hint`` / ``why_full`` when it carries ``explain_language``."""

    what = _WHAT.get(str((context or {}).get("kind") or ""), _WHAT["photo"])
    text = EDIT_INSTRUCTIONS.replace("{what}", what)
    if not (context or {}).get(pourquoi.EXPLAIN_KEY):
        return text
    extended = text.replace(pourquoi._FIL_SCHEMA_V1, pourquoi._FIL_SCHEMA_V2, 1)  # noqa: SLF001 - the shared schemas
    return extended.replace("\n- French typography:", f"\n{pourquoi._WHY_RULES}\n- French typography:", 1)  # noqa: SLF001


def prompt_version() -> str:
    return EDIT_PROMPT_VERSION_POURQUOI if pourquoi.enabled() else EDIT_PROMPT_VERSION


def proofread(encounter: Any, loaded: Any, *, kind: str, band: str, learner_fr: str,
              extra: dict[str, Any] | None = None, refuse: Callable[[str], bool] | None = None,
              shape: Callable[[str], str] | None = None) -> dict[str, Any]:
    """One model call; ``as_written`` when the call or its checks fail. ``refuse``: a last
    check on Romy's French (``True`` drops it); ``shape``: how it prints (a headline drops its
    final stop)."""

    out: dict[str, Any] = {"proof": "as_written", "target": "", "marks": [], "source": "fallback", "cost": 0.0,
                           "refused": None}
    edit = getattr(encounter.provider, "rubrique_edit", None)
    if not callable(edit):
        return out
    context: dict[str, Any] = {"kind": kind, "band": band, "learner_fr": learner_fr,
                               "facts": [c.fr for c in loaded.dossier.claims if c.kind == "fact"], **(extra or {})}
    language = pourquoi.explain_language(encounter, loaded) if pourquoi.enabled() else None
    if language:
        context[pourquoi.EXPLAIN_KEY] = language
    before = meter(encounter.provider)
    try:
        raw = edit(context)
    except Exception as exc:  # noqa: BLE001 - the learner's French stands
        logger.bind(session_id=str(loaded.row.id)).warning("revue {}: edit failed ({})", kind, exc)
        raw = None
    out["cost"] = round(meter(encounter.provider) - before, 6)
    if not isinstance(raw, dict):
        return out
    checked = fil_loop.check_edit(raw, learner_fr)
    edited = str(checked.get("edited_fr") or "")
    if shape is not None and edited:
        edited = shape(edited)
    if edited and refuse is not None and refuse(edited):
        checked = {"_problems": [f"edit:{kind}:refused"]}
        edited = ""
    out["refused"] = checked.get("_problems") or None
    if edited:
        edited = voice.french_typography(edited)
        marks = comptoir_loop.proof_marks(learner_fr, edited, checked.get("marks") or [])
        if language and marks:
            marks = pourquoi.explain_marks(marks, raw.get("marks"), learner_fr=learner_fr, target_fr=edited,
                                           dossier=loaded.dossier, takes=None, band=band, language=language)
        out.update(target=edited, marks=marks, proof="marked" if marks else "clean", source="model")
    return out


class Trail:
    """Where the learner's French stands before print, from the first act (``first``: its
    ``learner_fr``, ``proof``, ``target_fr``, ``marks``) and the fixes after it."""

    def __init__(self, first: dict[str, Any] | None, fixes: list[dict[str, Any]]) -> None:
        self.first = first
        self.fixes = fixes

    @property
    def proof(self) -> dict[str, Any] | None:
        if self.first is None:
            return None
        latest = self.fixes[-1] if self.fixes else self.first
        proof = str(latest.get("proof") or "as_written")
        texts = [str(fix.get("text_fr")) for fix in self.fixes if fix.get("text_fr")]
        draft = texts[-1] if texts else str(self.first.get("learner_fr") or "")
        target = str(latest.get("target_fr") or "")
        printed = None
        if proof in {"clean", "fixed", "corrected"}:
            printed = target or voice.french_typography(draft)
        elif proof == "as_written":
            printed = voice.french_typography(draft)
        return {"proof": proof, "draft": draft, "marks": list(latest.get("marks") or []) if proof == "marked" else [],
                "tries": len(texts), "target": target, "printed": printed}

    @property
    def settled(self) -> bool:
        proof = self.proof
        return proof is not None and proof["proof"] != "marked"

    def own_words(self) -> str:
        texts = [str((self.first or {}).get("typed_fr") or "")]
        texts += [str(fix.get("typed_fr") or "") for fix in self.fixes]
        return " ".join(text for text in texts if text)

    def rounds(self) -> list[tuple[str, list[dict[str, Any]]]]:
        return pourquoi.rounds_of(self.first, self.fixes)


def fix_row(encounter: Any, loaded: Any, trail: Trail, *, kind: str, band: str, text: str | None, value: str | None,
            check: Callable[[str], RvRubriqueError | None], prepare: Callable[[str], str],
            extra: dict[str, Any] | None = None, refuse: Callable[[str], bool] | None = None,
            shape: Callable[[str], str] | None = None) -> tuple[dict[str, Any] | None, RvRubriqueError | None]:
    """The event row of one fix (``None`` with nothing to record: settled, a repeat), or the
    reason it was refused. Raises ``LookupError`` for «Romy» before any try."""

    proof = trail.proof
    if proof is None or proof["proof"] != "marked":
        return None, None
    if value == "romy":
        if proof["tries"] < 1:
            raise LookupError("romy before a try")
        return {"by": "romy", "proof": "corrected", "target_fr": proof["target"]}, None
    learner = prepare(re.sub(r"\s+", " ", text or "").strip())
    why = check(learner)
    if why is not None:
        return None, why
    if comptoir_loop._proof_key(learner) == comptoir_loop._proof_key(proof["draft"]):  # noqa: SLF001
        return None, RvRubriqueError(code="nothing_changed")
    tries = proof["tries"] + 1
    row: dict[str, Any] = {"text_fr": learner, "typed_fr": learner, "try": tries, "cost_usd": 0.0}
    if comptoir_loop._proof_key(learner) == comptoir_loop._proof_key(proof["target"]):  # noqa: SLF001
        row.update(proof="fixed", target_fr=proof["target"])
        return row, None
    checked = proofread(encounter, loaded, kind=kind, band=band, learner_fr=learner, extra=extra, refuse=refuse,
                        shape=shape)
    row.update(cost_usd=checked["cost"], refused=checked["refused"], prompt_version=prompt_version())
    if checked["proof"] == "as_written":
        row.update(proof="as_written", target_fr="")
    elif checked["proof"] == "clean":
        row.update(proof="fixed", target_fr=checked["target"])
    elif tries >= FIX_TRIES:
        row.update(proof="corrected", target_fr=checked["target"])
    else:
        row.update(proof="marked", target_fr=checked["target"], marks=checked["marks"])
    return row, None


def settle(encounter: Any, loaded: Any, trail: Trail, proof: str) -> None:
    """«Le pourquoi»: once settled, the slips go to the learner's error memory."""

    if pourquoi.enabled() and proof in {"fixed", "corrected"}:
        pourquoi.remember(encounter.db, loaded.row.user_id, trail.rounds(), proof,
                          session_id=str(loaded.row.id), dossier_id=loaded.dossier.id)


def marks_view(proof: dict[str, Any] | None) -> list[RvComptoirMark]:
    return [RvComptoirMark(span_fr=str(m.get("span_fr")), start=int(m.get("start") or 0), kind=str(m.get("kind")),  # type: ignore[arg-type]
                           why=pourquoi.hint_of(m))
            for m in (proof["marks"] if proof else []) if isinstance(m, dict) and m.get("kind") in comptoir_loop.MARK_KINDS]


def notes_view(trail: Trail) -> list[RvComptoirNote]:
    proof = trail.proof
    if proof is None:
        return []
    return [RvComptoirNote(**note) for note in pourquoi.notes_of(trail.rounds(), proof["proof"])
            if note["kind"] in comptoir_loop.MARK_KINDS]


def no_new_number(dossier: Any) -> Callable[[str], bool]:
    """A check for Romy's French: it carries no number the claims lack."""

    known = comptoir.numbers(" ".join([dossier.title_fr, dossier.summary_fr, *(c.fr for c in dossier.claims)]))
    return lambda text: bool(comptoir.numbers(text) - known)


__all__ = [
    "EDIT_INSTRUCTIONS",
    "EDIT_SYSTEM",
    "FIX_TRIES",
    "Trail",
    "edit_instructions",
    "fix_row",
    "marks_view",
    "notes_view",
    "prompt_version",
    "proofread",
    "settle",
]
