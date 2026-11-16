"""The one way to name a grammar rule on a learner's screen (#522).

`GrammarConcept.name` is the English catalogue name. It is a key for authors, not
copy for learners. Reading it straight into a payload put the English name in front
of German and French learners, and because every call site picked its own field the
same rule was called three things in one German day (walk 4 Nov 2026: the rule card,
La Forge and the repair drill each named «être» differently).

`concept_title(concept, language)` answers in the learner's chrome language. The
order is a contract, not a convenience:

1. the title authored for that language (`grammar_concept_localizations`, then the
   v2 syllabus `names`);
2. French, the declared fallback: it is the language being learned, so a rule title
   in French is never wrong on a learner's screen;
3. the catalogue name, the floor, only when nothing else exists (and, for an English
   learner, the English name is the answer, not a fallback).

A surface that wants the French publication title (La Forge's header, a dossier
objective) asks for `"fr"`; a surface that follows the learner's chrome asks for the
learner's language. Neither reads `concept.name`.
"""
from __future__ import annotations

from typing import Any

from app.services.glosses import normalize_language

#: What a learner reads when no title exists in their own language.
FALLBACK_LANGUAGE = "fr"


def _localization_titles(concept: Any) -> dict[str, str]:
    titles: dict[str, str] = {}
    for row in getattr(concept, "localizations", None) or []:
        title = str(getattr(row, "title", "") or "").strip()
        if title:
            titles[normalize_language(getattr(row, "locale", None))] = title
    return titles


def concept_titles(concept: Any, localizations: dict[str, str] | None = None) -> dict[str, str]:
    """Every authored title of a rule, ``{locale: title}``; the catalogue name is only the ``en`` default.

    ``localizations`` lets a caller that already holds the rows (a batched query) hand
    them in instead of loading ``concept.localizations``.
    """

    if concept is None:
        return {}
    from app.services.grammar_units import localized_titles

    rows = _localization_titles(concept) if localizations is None else {
        normalize_language(locale): str(title).strip() for locale, title in localizations.items() if title
    }
    return {locale: title for locale, title in localized_titles(concept, rows).items() if title}


def concept_title(concept: Any, language: Any, *, localizations: dict[str, str] | None = None) -> str:
    """The title of ``concept`` in ``language`` (see the module doc for the order)."""

    if concept is None:
        return ""
    titles = concept_titles(concept, localizations)
    name = str(getattr(concept, "name", "") or "").strip()
    wanted = normalize_language(language)
    if wanted == "en":
        return titles.get("en") or titles.get(FALLBACK_LANGUAGE) or name
    return titles.get(wanted) or titles.get(FALLBACK_LANGUAGE) or titles.get("en") or name


def concept_title_fr(concept: Any, localization: Any = None) -> str:
    """The French publication title, for a caller that batch-loaded the ``fr`` row.

    Passing the row (or its absence) keeps a list of rules from loading
    ``concept.localizations`` once per rule.
    """

    title = str(getattr(localization, "title", "") or "").strip()
    return concept_title(concept, "fr", localizations={"fr": title} if title else {})


def localizations_by_concept_id(db: Any, concept_ids: Any) -> dict[int, dict[str, str]]:
    """``{concept_id: {locale: title}}`` for many rules in one query (every locale).

    The batch twin of ``concept.localizations``: hand a rule's entry to
    ``concept_title(..., localizations=)`` so a list of rules (the Cahier, a day's
    concepts) does not load the rows once per rule.
    """

    from app.db.models.grammar import GrammarConceptLocalization

    ids = [concept_id for concept_id in set(concept_ids) if concept_id is not None]
    found: dict[int, dict[str, str]] = {concept_id: {} for concept_id in ids}
    if not ids:
        return found
    rows = db.query(GrammarConceptLocalization).filter(GrammarConceptLocalization.concept_id.in_(ids)).all()
    for row in rows:
        title = str(row.title or "").strip()
        if title:
            found[row.concept_id][normalize_language(row.locale)] = title
    return found


__all__ = [
    "FALLBACK_LANGUAGE",
    "concept_title",
    "concept_title_fr",
    "concept_titles",
    "localizations_by_concept_id",
]
