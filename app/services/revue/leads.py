"""«La une en trois phrases»: the story told before anyone talks (owner, 2026-10-18).

The owner's review of the Papier: «it's not clear what happened». The summary was written
once for every band (B2 grammar at A1) and hidden behind the audio button, and Romy opened
with her brief. A dossier now carries :class:`~app.services.revue.dossier.StoryLeads`: the
story told at A1 (three short present-tense sentences, at most 30 words) and at A2, each
with its English and German for the translate button, and a headline of six words or fewer
for Home's news card. B1 and up read ``summary_fr``.

- The builder asks for ``leads`` in its one call (``builder.BUILDER_INSTRUCTIONS``) and
  keeps what :func:`repair_leads` accepts.
- The lead desk (:func:`write_leads`, one small JSON call) writes them for a stored dossier
  that has none: built before them, an evergreen top-up, or a builder answer the checks
  refused. :func:`ensure_leads` runs it each morning over the kiosk's rows
  (``app/tasks/revue.py``), once per row.

:func:`repair_leads` is the check both share. A lead is dropped (the band falls back, see
``EditorialDossier.lead_for``), never the dossier, when it is empty, too long for its band,
dated relatively («demain», or a «jeudi» the story does not name), carries an id, or has a number no claim carries.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from loguru import logger

from app.services.revue import voice
from app.services.revue.dossier import (
    EditorialDossier,
    StoryLead,
    StoryLeads,
    fold,
    quote_word_count,
)

A1_MAX_WORDS = 35
A2_MAX_WORDS = 60
HEADLINE_MAX_WORDS = 6
TRANSLATION_MAX_CHARS = 600
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

LEADS_SPEC = """{"headline_fr": str (six words or fewer, plain A1 French, no colon: what happened — «Un plat à 5 euros
             à Toulouse»),
            "a1": {"fr": str (three short sentences, 30 words at most, present tense, the most common words: who did
             what, where — «Thélyson Orélien écrit des romans. Des gens disent : il copie d'autres livres. Il dit
             pardon.»), "en": str, "de": str},
            "a2": {"fr": str (three or four sentences, 50 words at most, A2 French: what happened, who, and why
             people talk about it), "en": str, "de": str}}"""

LEAD_RULES = """LEAD RULES (leads): a lead is the story itself, told to a friend who has not heard it: what
happened first, then who and where. Never the angle, never what the learner should do, never «cet article» or
«les sources». Only what the claims say; names and numbers copied from them (numbers in digits); absolute dates or
none, never «demain», «hier», «cette semaine», nor a weekday the claims do not name. "en" and "de" translate the
French faithfully."""

LEAD_DESK_INSTRUCTIONS = (
    """You are the front-page editor of «Le Papier de Romy», a French-learning app. From the INPUT dossier of one
news story, write ONLY the leads as JSON: {"leads": """
    + LEADS_SPEC
    + """}
"""
    + LEAD_RULES
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _numbers_known(dossier: EditorialDossier) -> set[str]:
    text = " ".join([dossier.title_fr, dossier.summary_fr, *(c.fr for c in dossier.claims),
                     *(c.quote for c in dossier.claims)])
    return {n.replace(",", ".") for n in _NUMBER.findall(fold(text).replace(" ", ""))}


def _weekdays(text: str) -> set[str]:
    from app.services.revue.checks import _WEEKDAY  # noqa: PLC0415 - checks imports geo

    return {match.group(1) for match in _WEEKDAY.finditer(fold(text).casefold())}


def _weekdays_known(dossier: EditorialDossier) -> set[str]:
    """The weekdays a lead may name: those the story's own French carries («le marché du
    dimanche»), or any when it happens on one day (the Temporal rule, ``checks``)."""

    from app.services.revue.checks import WEEKDAYS  # noqa: PLC0415

    if dossier.time_scope.start == dossier.time_scope.end:
        return set(WEEKDAYS)
    return _weekdays(" ".join([dossier.title_fr, dossier.summary_fr, *(c.fr for c in dossier.claims)]))


def _problem(text: str, dossier: EditorialDossier, limit: int, known: set[str]) -> str | None:
    """Why ``text`` cannot be a lead, or ``None``."""

    from app.services.revue.checks import _relative_dates  # noqa: PLC0415 - the Temporal rule

    if not text:
        return "empty"
    if quote_word_count(text) > limit:
        return "too_long"
    if _relative_dates(text, weekdays_allowed=True) or _weekdays(text) - _weekdays_known(dossier):
        return "relative_date"
    if voice.id_leaks(text):
        return "id_leak"
    if any(n.replace(",", ".") not in known for n in _NUMBER.findall(text.replace(" ", ""))):
        return "number_not_in_claims"
    return None


def repair_leads(raw: Any, dossier: EditorialDossier) -> tuple[StoryLeads | None, list[str]]:
    """The leads a provider wrote, checked against ``dossier``; with the repairs made. A
    band whose French fails is dropped with its translations; a headline over
    :data:`HEADLINE_MAX_WORDS` words is dropped (the card shows the title)."""

    if not isinstance(raw, dict):
        return None, ["leads:missing"]
    repairs: list[str] = []
    known = _numbers_known(dossier)
    headline: str | None = _clean(raw.get("headline_fr")).rstrip(" .")
    why = _problem(headline, dossier, HEADLINE_MAX_WORDS, known) if headline else None
    if why:
        repairs.append(f"leads:headline:{why}")
        headline = None
    bands: dict[str, StoryLead] = {}
    for band, limit in (("a1", A1_MAX_WORDS), ("a2", A2_MAX_WORDS)):
        row = raw.get(band)
        if isinstance(row, str):
            row = {"fr": row}
        if not isinstance(row, dict):
            repairs.append(f"leads:{band}:missing")
            continue
        fr = _clean(row.get("fr"))
        why = _problem(fr, dossier, limit, known)
        if why:
            repairs.append(f"leads:{band}:{why}")
            continue
        translations = {lang: (_clean(row.get(lang))[:TRANSLATION_MAX_CHARS] or None) for lang in ("en", "de")}
        bands[band] = StoryLead(fr=voice.french_typography(fr), **translations)
    if not headline and not bands:
        return None, repairs
    return StoryLeads(headline_fr=voice.french_typography(headline) if headline else None, **bands), repairs


def desk_payload(dossier: EditorialDossier) -> dict[str, Any]:
    """What the lead desk reads: the story's French, never its sources' text."""

    return {
        "title_fr": dossier.title_fr,
        "summary_fr": dossier.summary_fr,
        "claims": [{"fr": c.fr, "kind": c.kind, "attributed_to": c.attributed_to} for c in dossier.claims],
        "entities": [e.model_dump(exclude_none=True) for e in dossier.entities],
        "places": [p.name_fr for p in dossier.places],
        "happening": dossier.time_scope.happening,
    }


def write_leads(dossier: EditorialDossier, provider: Any = None) -> tuple[StoryLeads | None, list[str]]:
    """The lead desk: fresh leads for a built dossier (one small JSON call), repaired and
    checked like the builder's. ``None`` when the call fails or nothing passes."""

    if provider is None:
        from app.services.revue.encounter import OpenAIRevueProvider

        provider = OpenAIRevueProvider(name="openai-revue-lead-desk", max_tokens=900)
    try:
        raw = provider.ask_json(
            LEAD_DESK_INSTRUCTIONS,
            desk_payload(dossier),
            system="You write the plainest possible French news leads for language learners. Answer with JSON only.",
            temperature=0.3,
            label="write_leads",
        )
    except Exception as exc:  # noqa: BLE001 - the dossier keeps its summary
        logger.bind(dossier=dossier.id).warning("revue lead desk failed ({})", exc)
        return None, ["leads:desk_failed"]
    return repair_leads(raw.get("leads", raw) if isinstance(raw, dict) else raw, dossier)


def kiosk_periods(period: str) -> list[str]:
    """The periods whose dossiers today's kiosk shows: the week, or the last seven days."""

    from app.services.revue.weekly import DAILY_KIOSK_DAYS, is_daily_period

    if not is_daily_period(period):
        return [period]
    end = date.fromisoformat(period)
    return [(end - timedelta(days=offset)).isoformat() for offset in range(DAILY_KIOSK_DAYS)]


def ensure_leads(db: Any, period: str, *, provider: Any = None) -> list[str]:
    """Give every dossier in ``period``'s kiosk that has no leads a try at the lead desk, once
    (``checks["leads"]`` records a refusal so a refused row is not asked again). Returns the
    ids that got leads."""

    from sqlalchemy import select

    from app.db.models.revue_session import RevueDossier

    done: list[str] = []
    changed = False
    rows = list(db.scalars(
        select(RevueDossier)
        .where(RevueDossier.period.in_(kiosk_periods(period)))
        .order_by(RevueDossier.period.desc(), RevueDossier.id.asc())  # today's first
    ))
    for row in rows:
        if (row.payload or {}).get("leads") or (row.checks or {}).get("leads"):
            continue
        try:
            dossier = EditorialDossier.model_validate(row.payload)
        except Exception as exc:  # noqa: BLE001 - an unreadable row is left to the kiosk's own guard
            logger.bind(row=row.id).debug("revue leads: stored dossier unreadable ({})", exc)
            continue
        leads, repairs = write_leads(dossier, provider)
        if leads is None:
            row.checks = {**(row.checks or {}), "leads": ",".join(repairs) or "refused"}
            changed = True
            logger.bind(dossier=dossier.id, repairs=repairs).info("revue leads: refused; the summary stays")
            continue
        row.payload = {**row.payload, "leads": leads.model_dump(mode="json")}
        done.append(dossier.id)
        changed = True
    if changed:
        db.commit()
    return done


__all__ = [
    "A1_MAX_WORDS",
    "A2_MAX_WORDS",
    "HEADLINE_MAX_WORDS",
    "LEAD_DESK_INSTRUCTIONS",
    "LEAD_RULES",
    "LEADS_SPEC",
    "ensure_leads",
    "kiosk_periods",
    "repair_leads",
    "write_leads",
]
