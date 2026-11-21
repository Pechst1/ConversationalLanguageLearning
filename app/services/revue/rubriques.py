"""«Le Papier · les rubriques»: what the reading-led assignments share (owner 2026-11-20).

«Le titre» (``titre.py`` / ``titre_loop.py``) and «L'intox express» (``intox.py`` /
``intox_loop.py``) are siblings of «Le fil» (``fil.py`` / ``fil_loop.py``) and are built the
same way; what they would otherwise copy from it lives here, so «Le fil»'s own files stay as
they are:

- :func:`ask_desk`: one JSON call per story through the Revue's provider, a second with the
  problems when the first was refused, then nothing (as ``fil.write_fil``).
- :func:`ensure_desk`: each morning, once per kiosk row, only while
  ``REVUE_ASSIGNMENTS_ENABLED`` is on; a row whose takes the comptoir skipped (a sensitive
  story) is skipped without a call; an evergreen reads what was written for it by hand (as
  ``fil.ensure_fil``).
- :func:`text`: a line checked as the comptoir checks its lines (``comptoir._Checker``: no
  number the claims lack, no relative date, no id, no app word, no rude word) plus a name the
  claims do not carry (``fil.new_names``) and its two translations.
- :data:`LOOPS` and :func:`loop`: the loop module of each assignment the generic act route
  (``POST /revue/sessions/{id}/rubrique``) plays; «Le fil» keeps its own route.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

from loguru import logger

from app.services.revue.comptoir import _Checker, ci, contains
from app.services.revue.dossier import ComptoirText, EditorialDossier
from app.services.revue.fil import new_names

TRANSLATION_MAX_CHARS = 400
DESK_SYSTEM = "You write plain, correct, factual French for language learners. Answer with one JSON object only."

#: Words a line about a person's private life carries: never in a statement or a headline.
PRIVATE_WORDS: tuple[str, ...] = (
    "vie privee", "sa femme", "son mari", "sa compagne", "son compagnon", "sa copine", "son copain", "divorce",
    "divorcer", "enceinte", "grossesse", "liaison", "amoureux", "amoureuse", "sa maladie", "son cancer",
    "ses enfants", "sa fille", "son fils", "sa famille", "sa religion", "orientation sexuelle", "son salaire",
    "sa maison", "son adresse", "son mariage",
)


def private(fr: str | None) -> str | None:
    """The private-life word ``fr`` carries, or ``None``."""

    folded = f" {ci(fr)} "
    return next((w for w in PRIVATE_WORDS if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", folded)), None)


def text(check: _Checker, row: Any, limit: int, *, allow: str | None = None,
         translations: bool = True) -> tuple[ComptoirText | None, str | None]:
    """``row`` (``{"fr", "en", "de"}`` or a bare French string) checked for ``check``'s story."""

    if isinstance(row, str):
        row = {"fr": row}
    if not isinstance(row, dict):
        return None, "missing"
    line, why = check.text(row, limit, allow=allow)
    if line is None:
        return None, why
    if [name for name in new_names(line.fr, check.story) if not contains(allow, name)]:
        return None, "name_not_in_claims"  # a false value («à Lyon») may name what the claims do not
    if private(line.fr):
        return None, "private_life"
    if translations and not (line.en and line.de):
        return None, "translation_missing"
    return ComptoirText(fr=line.fr, en=(line.en or "")[:TRANSLATION_MAX_CHARS] or None,
                        de=(line.de or "")[:TRANSLATION_MAX_CHARS] or None), None


def desk_payload(dossier: EditorialDossier) -> dict[str, Any]:
    """What a desk reads: the story's French and the claims' verbatim quotes."""

    return {
        "title_fr": dossier.title_fr,
        "summary_fr": dossier.summary_fr,
        "claims": [{"id": c.id, "kind": c.kind, "fr": c.fr, "quote": c.quote, "attributed_to": c.attributed_to}
                   for c in dossier.claims],
        "topic": dossier.topic,
        "happening": dossier.time_scope.happening,
    }


def desk_provider(name: str) -> Any:
    """The Revue's own provider and model, with room for three languages."""

    from app.services.revue.encounter import (
        OpenAIRevueProvider,  # noqa: PLC0415 - encounter imports the desks
    )

    return OpenAIRevueProvider(name=name, max_tokens=4000)


def ask_desk(dossier: EditorialDossier, provider: Any, *, key: str, instructions: str,
             repair: Callable[[Any, EditorialDossier], tuple[Any, list[str]]],
             prompt_version: str) -> tuple[Any, list[str]]:
    """One JSON call (a second with the problems when the first was refused), checked by
    ``repair``. ``(None, ["skip"])`` for an unfit story; ``(None, problems)`` when nothing
    passes; ``(None, ["<key>:desk_failed"])`` when the call fails (asked again tomorrow)."""

    provider = provider if provider is not None else desk_provider(f"openai-revue-{key}-desk")
    payload = desk_payload(dossier)
    problems: list[str] = []
    for attempt in range(2):
        ask = payload if attempt == 0 else {**payload, "retry_feedback": {"problems": problems}}
        try:
            raw = provider.ask_json(instructions, ask, system=DESK_SYSTEM, temperature=0.4, label=f"write_{key}")
        except Exception as exc:  # noqa: BLE001 - the story carries another assignment
            logger.bind(dossier=dossier.id).warning("revue {} desk failed ({})", key, exc)
            return None, [f"{key}:desk_failed"]
        made, problems = repair(raw, dossier)
        if problems == ["skip"]:
            return None, problems
        if made is not None:
            model = getattr(provider, "model", None) or ""
            return made.model_copy(update={"model": str(model), "written_at": datetime.now(UTC),
                                           "prompt_version": prompt_version}), problems
    return None, problems


def ensure_desk(db: Any, period: str, *, key: str, write: Callable[[EditorialDossier, Any], tuple[Any, list[str]]],
                evergreen: Callable[[str], Any], provider: Any = None) -> list[str]:
    """Give every dossier in ``period``'s kiosk without ``key`` a try at its desk, once
    (``checks[key]`` records a refusal or ``"skip"``). Returns the ids that got one."""

    from app.services.revue.comptoir import _kiosk_rows  # noqa: PLC0415

    done: list[str] = []
    changed = False
    for row in _kiosk_rows(db, period):
        if (row.payload or {}).get(key) or (row.checks or {}).get(key):
            continue
        try:
            dossier = EditorialDossier.model_validate(row.payload)
        except Exception as exc:  # noqa: BLE001 - an unreadable row is left to the kiosk's own guard
            logger.bind(row=row.id).debug("revue {}: stored dossier unreadable ({})", key, exc)
            continue
        changed = True
        if (row.checks or {}).get("comptoir") == "skip":
            row.checks = {**(row.checks or {}), key: "skip"}
            continue
        if dossier.evergreen:
            made, problems = evergreen(dossier.id), [f"{key}:evergreen_without_{key}"]
        else:
            made, problems = write(dossier, provider)
        if made is None:
            if problems == [f"{key}:desk_failed"]:
                continue  # asked again tomorrow
            row.checks = {**(row.checks or {}), key: "skip" if problems == ["skip"] else ",".join(problems) or "refused"}
            logger.bind(dossier=dossier.id, problems=problems).info("revue {}: none", key)
            continue
        row.payload = {**row.payload, key: made.model_dump(mode="json")}
        done.append(dossier.id)
    if changed:
        db.commit()
    return done


def material_of(dossier: EditorialDossier, key: str, evergreen: Callable[[str], Any]) -> Any:
    """What a session on ``dossier`` plays for ``key``: the dossier's own, else the evergreen's."""

    own = getattr(dossier, key, None)
    if own is not None:
        return own
    return evergreen(dossier.id) if dossier.evergreen else None


#: The loop module of each assignment the generic act route plays.
LOOPS: dict[str, str] = {
    "titre": "app.services.revue.titre_loop",
    "intox": "app.services.revue.intox_loop",
    "photo": "app.services.revue.photo_loop",
    "micro": "app.services.revue.micro_loop",
}


def loop(key: str) -> ModuleType | None:
    path = LOOPS.get(key)
    return importlib.import_module(path) if path else None


__all__ = ["LOOPS", "ask_desk", "desk_payload", "ensure_desk", "loop", "material_of", "private", "text"]
