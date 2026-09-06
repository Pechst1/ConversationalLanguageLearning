"""WP-03 — bounded scenario briefs and dependable content for the daily journey.

This module answers one question for the state machine (WP-02): *what scene is
this learner walking into today, and is it actually safe to show?*

Design rules this file exists to enforce:

* **Authored first.** Every scenario family ships hand-written A1 and A2 French
  content in ``app/data/journey_scenarios/<content_version>/``. That path costs
  nothing: no model call, no image call, no network. It is the path the
  end-to-end café journey runs on and the path every test exercises by default
  (``ATELIER_LLM_ENABLED=false``).
* **Validated always.** Authored *and* generated briefs go through
  :func:`validate_scenario_brief` before they can leave this module. A brief that
  fails validation is never returned as if it were ready; the caller gets
  :class:`~app.services.journey_contracts.ContentUnavailable` with an honest
  reason instead.
* **Read-only about the serial.** :func:`derive_serial_side_scene` may *bind* a
  journey to the learner's current serial beat, but it never advances an
  episode, never writes, and never reads the beat's ``hook`` (the teaser for the
  *next* beat), so a daily journey cannot leak future plot.
* **Pinned.** ``ScenarioBrief.content_version`` and ``level_band`` identify the
  exact authored text. :func:`resolve_scenario_brief` accepts both, so bumping
  the shipped content version never rewrites or strands an active journey.

Public entry points
-------------------
``build_scenario_context``   the WP-02 domain callable (CONTRACTS §6).
``resolve_scenario_brief``   the pinned lookup (``content_version=``/``level_band=``).
``list_available_scenarios`` every authored family a learner could be offered.
``scenario_content_rules``   the validation rules for one family/level.
``scenario_target_affordances`` French phrases the scene makes natural (WP-05 relevance).
``derive_serial_side_scene`` the read-only serial adapter.
``validate_scenario_brief``  the validator, reusable by callers and tests.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.services.journey_contracts import (
    DEFAULT_BUDGET_SECONDS,
    JOURNEY_CONTENT_VERSION,
    MAX_RESPOND_TURNS,
    CapabilityKey,
    ContentUnavailable,
    ControlLanguage,
    InputMode,
    JourneyEventName,
    ResponseTask,
    ScenarioBrief,
    ScenarioContextResult,
    normalize_control_language,
)
from app.services.llm_service import LLMService
from app.services.pilot_events import PilotEventService
from app.services.serial import WORLD_BIBLE_PATH, SerialThreadService
from app.utils.cache import build_cache_key, cache_backend

# --------------------------------------------------------------------------
# Locations of the authored content this module serves
# --------------------------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = APP_ROOT.parent
SCENARIO_DATA_ROOT = APP_ROOT / "data" / "journey_scenarios"
JOURNEY_PROMPT_ROOT = APP_ROOT / "prompts" / "journey"
#: The backend image does not ship ``web-frontend/public``; when the directory is
#: absent the declared asset path is trusted, when it is present it is verified.
MEDIA_PUBLIC_ROOT = REPO_ROOT / "web-frontend" / "public"

JOURNEY_PROMPT_VERSION = "journey-prompt-v1"
VARIATION_PROMPT_FILE = "scenario_variation_v1.json"
CURRENT_CONTENT_VERSION = JOURNEY_CONTENT_VERSION

#: Deterministic offer order when the caller does not name a scenario.
SCENARIO_PRIORITY: tuple[CapabilityKey, ...] = (
    CapabilityKey.ORDER_AT_CAFE,
    CapabilityKey.ARRANGE_MEETING,
    CapabilityKey.EXPLAIN_DELAY,
)

MAX_GENERATION_ATTEMPTS = 2
CONTENT_CACHE_NAMESPACE = "journey_content"
CONTENT_CACHE_TTL_SECONDS = 6 * 60 * 60

GENERATED_EVENT = "journey_content_generated"

LEVEL_BAND_ORDER: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")

_PROFICIENCY_BANDS: dict[str, str] = {
    "beginner": "A1",
    "novice": "A1",
    "elementary": "A1",
    "a1": "A1",
    "pre-intermediate": "A2",
    "preintermediate": "A2",
    "intermediate": "A2",
    "a2": "A2",
    "upper-intermediate": "B1",
    "b1": "B1",
    "advanced": "B2",
    "b2": "B2",
    "c1": "C1",
    "c2": "C2",
    "fluent": "C1",
}

#: Topic guards. The acceptance criterion is literal: a café conversation must
#: not turn into landlord paperwork.
OFF_TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "landlord_paperwork": (
        "bail",
        "loyer",
        "quittance",
        "propriétaire",
        "caution",
        "état des lieux",
        "assurance habitation",
        "dossier de location",
        "préavis",
        "charges locatives",
        "landlord",
        "lease",
    ),
    "administration": (
        "préfecture",
        "titre de séjour",
        "carte de séjour",
        "récépissé",
        "guichet",
        "dossier administratif",
        "justificatif de domicile",
    ),
}

#: Length envelopes per authored band. Anything above A2 reuses the A2 envelope,
#: because the authored ceiling is A2.
BAND_LIMITS: dict[str, dict[str, int]] = {
    "A1": {"setup_words": 28, "line_words": 16},
    "A2": {"setup_words": 40, "line_words": 24},
}

_TU_MARKERS = re.compile(r"\b(tu|toi|te|ton|ta|tes)\b|\bt'", re.IGNORECASE)
_VOUS_MARKERS = re.compile(r"\b(vous|votre|vos)\b", re.IGNORECASE)
_OUTCOME_KEY = re.compile(r"^[a-z][a-z0-9_]*$")

_LEVEL_NOTE_ABOVE: dict[str, str] = {
    "en": "This scene is written at {band}, below your current level.",
    "de": "Diese Szene ist auf {band} geschrieben, unter deinem aktuellen Niveau.",
    "fr": "Cette scène est écrite au niveau {band}, en dessous de ton niveau actuel.",
}
_LEVEL_NOTE_BELOW: dict[str, str] = {
    "en": "This scene is written at {band}, a step above where you are.",
    "de": "Diese Szene ist auf {band} geschrieben, eine Stufe über deinem Niveau.",
    "fr": "Cette scène est écrite au niveau {band}, un cran au-dessus de ton niveau.",
}
_VOICE_RUBRIC_NOTE: dict[str, str] = {
    "en": "The learner is speaking: judge meaning, not spelling or transcription artefacts.",
    "de": "Es wird gesprochen: Bewerte den Inhalt, nicht Rechtschreibung oder Transkriptionsfehler.",
    "fr": "L'apprenant parle : juge le sens, pas l'orthographe ni les scories de transcription.",
}

#: Serial episode statuses that mean "this beat is playable right now".
_SERIAL_READY_STATUSES = frozenset({"available"})
_SERIAL_DELAYED_STATUSES = frozenset({"delayed", "generation_failed"})
_SERIAL_PENDING_STATUSES = frozenset({"generating", "queued", "generation_queued"})


# --------------------------------------------------------------------------
# Small value objects owned by this package
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContentRules:
    """Everything :func:`validate_scenario_brief` needs that the brief itself
    does not carry: the declared register, the topic guard, and the typed set of
    allowable outcome keys."""

    scenario_key: CapabilityKey
    level_band: str
    register: Literal["tu", "vous"]
    forbidden_terms: tuple[str, ...]
    allowed_outcomes: tuple[str, ...]
    image_asset: str | None


@dataclass(frozen=True, slots=True)
class LevelFit:
    """How honestly the authored band matches the learner's band."""

    learner_band: str
    content_band: str
    is_exact: bool
    note_native: str | None = None


@dataclass(frozen=True, slots=True)
class SerialSideScene:
    """Result of the read-only serial adapter.

    ``is_fallback`` is ``True`` whenever the journey could not be bound to a real
    current beat. In that case ``thread_id``/``episode_id`` stay ``None`` and the
    authored side scene is used — the journey never claims to have played, let
    alone completed, a serial episode.
    """

    reason: str
    is_fallback: bool
    thread_id: str | None = None
    episode_id: str | None = None
    location_id: str | None = None


# --------------------------------------------------------------------------
# World bible + authored content loading
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _world_bible() -> dict[str, Any]:
    return json.loads(WORLD_BIBLE_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _world_cast() -> dict[str, str]:
    cast = _world_bible().get("cast") or []
    return {
        str(member["id"]): str(member.get("name") or "")
        for member in cast
        if isinstance(member, dict) and member.get("id")
    }


@lru_cache(maxsize=1)
def _world_locations() -> dict[str, str]:
    setting = _world_bible().get("setting") or {}
    rows = setting.get("recurring_locations") or []
    return {
        str(row["id"]): str(row.get("name") or "")
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }


@lru_cache(maxsize=1)
def _world_location_assets() -> dict[str, tuple[str, ...]]:
    visual = _world_bible().get("visual_design") or {}
    locations = visual.get("locations") or {}
    resolved: dict[str, tuple[str, ...]] = {}
    for location_id, payload in locations.items():
        if not isinstance(payload, dict):
            continue
        images = payload.get("reference_images") or []
        resolved[str(location_id)] = tuple(str(item) for item in images if item)
    return resolved


def world_bible_version() -> str:
    return str(_world_bible().get("world_bible_version") or "")


_SPEC_CACHE: dict[tuple[str, str, str], dict[str, Any] | None] = {}


def available_content_versions() -> list[str]:
    """Every content version present on disk, oldest directory name first.

    Retired versions stay on disk on purpose: an active journey pinned to an
    older version must keep resolving after a bump.
    """

    root = SCENARIO_DATA_ROOT
    if not root.is_dir():
        return []
    return sorted(child.name for child in root.iterdir() if child.is_dir())


def _load_scenario_spec(
    scenario_key: CapabilityKey | str,
    content_version: str,
) -> dict[str, Any] | None:
    key = (str(SCENARIO_DATA_ROOT), str(content_version), str(scenario_key))
    if key in _SPEC_CACHE:
        return _SPEC_CACHE[key]
    path = SCENARIO_DATA_ROOT / str(content_version) / f"{scenario_key}.json"
    spec: dict[str, Any] | None
    if not path.is_file():
        spec = None
    else:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            spec = loaded if isinstance(loaded, dict) else None
        except (OSError, ValueError) as exc:  # pragma: no cover - unreadable file
            logger.warning("journey scenario {} unreadable: {}", path, exc)
            spec = None
    _SPEC_CACHE[key] = spec
    return spec


def reset_content_cache() -> None:
    """Drop the in-process authored-content cache (used by tests and reloads)."""

    _SPEC_CACHE.clear()


# --------------------------------------------------------------------------
# Level bands
# --------------------------------------------------------------------------


def _band_index(band: str) -> int:
    try:
        return LEVEL_BAND_ORDER.index(band)
    except ValueError:
        return 0


def learner_level_band(user: User) -> str:
    """The learner's CEFR band, from ``cefr_estimate`` with ``proficiency_level``
    as backup. Unknown values fall back to ``A1`` — the honest floor."""

    raw = str(getattr(user, "cefr_estimate", "") or "").strip().upper()
    match = re.match(r"^(A1|A2|B1|B2|C1|C2)", raw)
    if match:
        return match.group(1)
    fallback = str(getattr(user, "proficiency_level", "") or "").strip().lower()
    mapped = _PROFICIENCY_BANDS.get(fallback)
    if mapped:
        return mapped
    upper = fallback.upper()
    if upper in LEVEL_BAND_ORDER:
        return upper
    return "A1"


def _select_variant(
    spec: dict[str, Any],
    band: str,
    control_language: ControlLanguage,
) -> tuple[dict[str, Any] | None, LevelFit]:
    variants = [row for row in (spec.get("variants") or []) if isinstance(row, dict)]
    by_band = {str(row.get("level_band") or ""): row for row in variants}
    if not by_band:
        return None, LevelFit(learner_band=band, content_band=band, is_exact=False)

    if band in by_band:
        return by_band[band], LevelFit(learner_band=band, content_band=band, is_exact=True)

    authored = sorted(by_band, key=_band_index)
    lowest, highest = authored[0], authored[-1]
    if _band_index(band) > _band_index(highest):
        note = _LEVEL_NOTE_ABOVE.get(control_language, _LEVEL_NOTE_ABOVE["en"])
        return by_band[highest], LevelFit(
            learner_band=band,
            content_band=highest,
            is_exact=False,
            note_native=note.format(band=highest),
        )
    note = _LEVEL_NOTE_BELOW.get(control_language, _LEVEL_NOTE_BELOW["en"])
    return by_band[lowest], LevelFit(
        learner_band=band,
        content_band=lowest,
        is_exact=False,
        note_native=note.format(band=lowest),
    )


#: ``{slot}`` / ``{slot|authored fallback}`` in an authored line or summary.
#: The slot is filled with something the learner actually did (the drink they
#: ordered, the day they proposed); the fallback is the authored wording that
#: claims nothing, used whenever that detail is unknown.
_SLOT_RE = re.compile(r"\{([a-z][a-z0-9_]*)(?:\|([^{}]*))?\}")


def render_authored_text(
    text: str | None, values: dict[str, str] | None = None
) -> str:
    """Fill the ``{slot|fallback}`` placeholders of one authored string.

    WP-12 defect D-2: an ending that hardcodes "café" tells a learner who
    ordered a tea that they were served a coffee. The authored ending therefore
    names the choice through a slot, and this is the *only* way that text
    becomes learner-visible — a caller that knows nothing about the learner
    still gets a complete, brace-free sentence, because every slot carries its
    own authored fallback.
    """

    if not text:
        return ""
    filled = {
        str(name): str(value).strip()
        for name, value in (values or {}).items()
        if str(value or "").strip()
    }

    def _substitute(match: re.Match[str]) -> str:
        return filled.get(match.group(1), match.group(2) or "")

    rendered = _SLOT_RE.sub(_substitute, text)
    return re.sub(r"\s{2,}", " ", rendered).strip()


def _localized(value: Any, control_language: ControlLanguage) -> str:
    """Resolve a ``{en, de, fr}`` block, always falling back to English."""

    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    for candidate in (control_language, "en"):
        text = value.get(candidate)
        if isinstance(text, str) and text.strip():
            return text
    return ""


# --------------------------------------------------------------------------
# Media
# --------------------------------------------------------------------------


def resolve_media_url(asset_path: str | None) -> str | None:
    """Turn a world-bible asset path into the URL convention already used by the
    serial (``/assets/serial/...``).

    Returns ``None`` — never a broken URL and never a blocked scene — when the
    public asset root is present locally and the file is missing.
    """

    if not asset_path:
        return None
    cleaned = str(asset_path).strip().lstrip("/")
    if not cleaned:
        return None
    if cleaned.startswith(("http://", "https://", "data:")):
        return None if cleaned.startswith("data:") else cleaned
    root = MEDIA_PUBLIC_ROOT
    if root.is_dir() and not (root / cleaned).is_file():
        return None
    return f"/{cleaned}"


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def _words(text: str | None) -> int:
    return len((text or "").split())


def _forbidden_terms(spec: dict[str, Any]) -> tuple[str, ...]:
    terms: list[str] = []
    for group in spec.get("forbidden_topic_groups") or []:
        terms.extend(OFF_TOPIC_TERMS.get(str(group), ()))
    terms.extend(str(item) for item in (spec.get("forbidden_terms") or []) if item)
    return tuple(dict.fromkeys(terms))


def _contains_term(haystack: str, term: str) -> bool:
    pattern = r"\b" + r"\s+".join(re.escape(part) for part in term.split()) + r"\b"
    return re.search(pattern, haystack, re.IGNORECASE) is not None


def _name_is_consistent(display_name: str, canonical: str) -> bool:
    """Reject invented names without demanding the world bible's exact styling.

    ``"Romy Tremblay"`` is fine for ``"Romane « Romy » Tremblay"``;
    ``"Monsieur Dupont"`` is not.
    """

    tokens = re.findall(r"[^\W\d_]{2,}", display_name, re.UNICODE)
    if not tokens:
        return False
    lowered = canonical.lower()
    return all(token.lower() in lowered for token in tokens)


def validate_scenario_brief(brief: ScenarioBrief, *, rules: ContentRules) -> list[str]:
    """Return the list of problems with ``brief``. Empty means it may be served.

    Covers the WP-03 acceptance surface: level-appropriate length, real cast and
    locations, real asset URLs, target/register relevance, typed outcome keys,
    contradiction guards, and answer integrity (no assistance text leaking into a
    field the learner reads before answering).
    """

    problems: list[str] = []
    task = brief.response_task

    if brief.scenario_key != rules.scenario_key:
        problems.append(
            f"scenario_key {brief.scenario_key!r} does not match rules {rules.scenario_key!r}"
        )

    cast = _world_cast()
    canonical_name = cast.get(brief.character_id)
    if canonical_name is None:
        problems.append(f"unknown world-bible character id {brief.character_id!r}")
    elif not _name_is_consistent(brief.character_name, canonical_name):
        problems.append(
            f"character_name {brief.character_name!r} is not a form of {canonical_name!r}"
        )
    if task.character_id != brief.character_id:
        problems.append("response task speaks as a different character than the scene")

    locations = _world_locations()
    if brief.location_id not in locations:
        problems.append(f"unknown world-bible location id {brief.location_id!r}")
    if not brief.location_name.strip():
        problems.append("location_name is empty")

    if rules.image_asset:
        declared = _world_location_assets().get(brief.location_id, ())
        if rules.image_asset.lstrip("/") not in declared:
            problems.append(
                f"image asset {rules.image_asset!r} is not a world-bible plate for "
                f"{brief.location_id!r}"
            )
        elif brief.image_url is not None and brief.image_url != f"/{rules.image_asset.lstrip('/')}":
            problems.append(f"image_url {brief.image_url!r} does not match the declared asset")
    if brief.image_url is not None and brief.image_url.startswith("data:"):
        problems.append("inline base64 image URLs are not allowed")

    limits = BAND_LIMITS.get(brief.level_band, BAND_LIMITS["A2"])
    for label, text in (
        ("title_fr", brief.title_fr),
        ("setup_fr", brief.setup_fr),
        ("setup_native", brief.setup_native),
        ("objective_native", brief.objective_native),
        ("objective_key", brief.objective_key),
        ("response_task.objective_native", task.objective_native),
        ("response_task.opening_line_fr", task.opening_line_fr),
        ("response_task.rubric_native", task.rubric_native),
    ):
        if not str(text or "").strip():
            problems.append(f"{label} is empty")

    if _words(brief.setup_fr) > limits["setup_words"]:
        problems.append(
            f"setup_fr is {_words(brief.setup_fr)} words, over the {brief.level_band} "
            f"limit of {limits['setup_words']}"
        )
    character_lines: list[tuple[str, str]] = [
        ("response_task.opening_line_fr", task.opening_line_fr),
    ]
    if brief.opening_line_fr:
        character_lines.append(("opening_line_fr", brief.opening_line_fr))
    # Endings are validated in the shape a learner can actually read: every
    # ``{slot|fallback}`` resolved to its authored fallback, never as raw text.
    for outcome_key, line in sorted(brief.resolution_lines.items()):
        character_lines.append(
            (f"resolution_lines[{outcome_key}]", render_authored_text(line))
        )
    for label, line in character_lines:
        if _words(line) > limits["line_words"]:
            problems.append(
                f"{label} is {_words(line)} words, over the {brief.level_band} "
                f"limit of {limits['line_words']}"
            )

    allowed = tuple(rules.allowed_outcomes)
    if not allowed:
        problems.append("no allowable outcome keys declared")
    for key in allowed:
        if not _OUTCOME_KEY.match(key):
            problems.append(f"outcome key {key!r} is not a typed snake_case key")
    if set(task.allowed_outcomes) != set(allowed):
        problems.append("response task outcome keys diverge from the declared set")
    if set(brief.resolution_lines) != set(allowed):
        problems.append("resolution lines do not cover exactly the allowable outcomes")
    if set(brief.resolution_summaries) != set(allowed):
        problems.append("resolution summaries do not cover exactly the allowable outcomes")
    for key, line in brief.resolution_lines.items():
        if not render_authored_text(line):
            problems.append(f"resolution line for {key!r} is empty")
    for key, summary in brief.resolution_summaries.items():
        if not render_authored_text(summary):
            problems.append(f"resolution summary for {key!r} is empty")

    if not 1 <= task.max_turns <= MAX_RESPOND_TURNS:
        problems.append(f"max_turns {task.max_turns} is outside 1..{MAX_RESPOND_TURNS}")
    if not task.required_intents:
        problems.append("the response task declares no required intent")

    # Register consistency: character speech only. Narration always addresses the
    # learner informally, so setup_fr is deliberately excluded.
    opposite = _TU_MARKERS if rules.register == "vous" else _VOUS_MARKERS
    expected = _VOUS_MARKERS if rules.register == "vous" else _TU_MARKERS
    spoken = [line for _, line in character_lines]
    if task.suggested_response_fr:
        spoken.append(task.suggested_response_fr)
    for line in spoken:
        if opposite.search(line or ""):
            problems.append(
                f"register break: a {rules.register} scene contains {line!r}"
            )
    if spoken and not any(expected.search(line or "") for line in spoken):
        problems.append(f"no line carries the declared {rules.register} register")

    # Topic guard: the café must not become landlord paperwork.
    guarded = [
        brief.title_fr,
        brief.setup_fr,
        brief.setup_native,
        brief.objective_native,
        brief.opening_line_fr or "",
        task.objective_native,
        task.opening_line_fr,
        task.suggested_response_fr or "",
        task.hint_native or "",
        *(render_authored_text(line) for line in brief.resolution_lines.values()),
        *(render_authored_text(text) for text in brief.resolution_summaries.values()),
    ]
    for term in rules.forbidden_terms:
        for text in guarded:
            if _contains_term(text or "", term):
                problems.append(
                    f"off-topic term {term!r} for scenario {rules.scenario_key} in {text!r}"
                )
                break

    # Answer integrity: assistance text must not appear in anything the learner
    # reads before answering.
    suggestion = (task.suggested_response_fr or "").strip()
    if suggestion:
        pre_answer = [
            brief.setup_fr,
            brief.setup_native,
            brief.objective_native,
            brief.opening_line_fr or "",
            task.objective_native,
            task.opening_line_fr,
        ]
        needle = _fold(suggestion)
        for text in pre_answer:
            if needle and needle in _fold(text or ""):
                problems.append("the suggested reply leaks into a pre-answer field")
                break

    if brief.estimated_seconds > DEFAULT_BUDGET_SECONDS:
        problems.append(
            f"estimated_seconds {brief.estimated_seconds} exceeds the "
            f"{DEFAULT_BUDGET_SECONDS}s budget"
        )
    if task.estimated_seconds >= brief.estimated_seconds:
        problems.append("the response task alone claims the whole journey estimate")

    return problems


def _fold(text: str) -> str:
    lowered = " ".join(str(text or "").split()).lower()
    for source, replacement in (("’", "'"), ("‘", "'"), ("´", "'")):
        lowered = lowered.replace(source, replacement)
    return lowered


# --------------------------------------------------------------------------
# Rules / affordances lookups
# --------------------------------------------------------------------------


def _variant_for(
    scenario_key: CapabilityKey | str,
    *,
    content_version: str | None,
    level_band: str | None,
    control_language: ControlLanguage = "en",
) -> tuple[dict[str, Any], dict[str, Any], LevelFit] | None:
    spec = _load_scenario_spec(scenario_key, content_version or CURRENT_CONTENT_VERSION)
    if spec is None:
        return None
    variant, fit = _select_variant(spec, level_band or "A1", control_language)
    if variant is None:
        return None
    return spec, variant, fit


def scenario_content_rules(
    scenario_key: CapabilityKey | str,
    *,
    level_band: str | None = None,
    content_version: str | None = None,
) -> ContentRules | None:
    """The validation rules for one authored family/level, or ``None``."""

    found = _variant_for(
        scenario_key, content_version=content_version, level_band=level_band
    )
    if found is None:
        return None
    spec, variant, _fit = found
    return _rules_from(spec, variant)


def _rules_from(spec: dict[str, Any], variant: dict[str, Any]) -> ContentRules:
    register = str(spec.get("register") or "vous")
    outcomes = tuple(
        str(row.get("key"))
        for row in (variant.get("outcomes") or [])
        if isinstance(row, dict) and row.get("key")
    )
    return ContentRules(
        scenario_key=CapabilityKey(str(spec["scenario_key"])),
        level_band=str(variant.get("level_band") or "A1"),
        register="tu" if register == "tu" else "vous",
        forbidden_terms=_forbidden_terms(spec),
        allowed_outcomes=outcomes,
        image_asset=str(spec.get("image_asset") or "") or None,
    )


def scenario_target_affordances(
    scenario_key: CapabilityKey | str,
    *,
    level_band: str | None = None,
    content_version: str | None = None,
) -> list[str]:
    """French phrases this scene makes it natural to produce.

    WP-05 can score ``LearningCandidate.relevance`` against this list instead of
    guessing which due items suit the scenario.
    """

    found = _variant_for(
        scenario_key, content_version=content_version, level_band=level_band
    )
    if found is None:
        return []
    _spec, variant, _fit = found
    return [str(item) for item in (variant.get("target_affordances_fr") or []) if item]


def scenario_required_facts(
    scenario_key: CapabilityKey | str,
    *,
    level_band: str | None = None,
    content_version: str | None = None,
) -> list[str]:
    """The facts the scene guarantees. WP-06 grades consequences against these."""

    found = _variant_for(
        scenario_key, content_version=content_version, level_band=level_band
    )
    if found is None:
        return []
    _spec, variant, _fit = found
    return [str(item) for item in (variant.get("required_facts_fr") or []) if item]


# --------------------------------------------------------------------------
# Serial adapter — read only
# --------------------------------------------------------------------------


def _active_serial_thread(db: Session, user: User) -> SerialThread | None:
    return (
        db.query(SerialThread)
        .filter(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.created_at.desc())
        .first()
    )


def derive_serial_side_scene(
    db: Session,
    *,
    user: User,
    scenario_key: CapabilityKey | str,
    location_id: str | None = None,
    compatible_locations: tuple[str, ...] | None = None,
    content_version: str | None = None,
) -> SerialSideScene:
    """Bind today's journey to the learner's *current* serial beat, or fall back.

    Read-only by construction:

    * it issues ``SELECT`` only, through :meth:`SerialThreadService.current_episode`;
    * it never touches ``thread.current_episode_index`` or ``episode.status``;
    * it never reads ``episode.hook`` / ``hook_from_previous``, which carry the
      teaser for the *next* beat — so no future plot can reach the journey;
    * an unbindable source is reported, never papered over: the caller marks the
      brief ``is_authored_fallback`` and no serial ids are attached.

    ``location_id`` and ``compatible_locations`` default to the authored
    scenario's own location and its declared ``serial_locations`` list.
    """

    spec = _load_scenario_spec(scenario_key, content_version or CURRENT_CONTENT_VERSION)
    if location_id is None:
        location_id = str((spec or {}).get("location_id") or "")
    if compatible_locations is None:
        compatible_locations = tuple(
            str(item) for item in ((spec or {}).get("serial_locations") or [])
        )

    thread = _active_serial_thread(db, user)
    if thread is None:
        return SerialSideScene(reason="no_serial_thread", is_fallback=True)

    world = thread.world_bible if isinstance(thread.world_bible, dict) else {}
    thread_world_version = str(world.get("world_bible_version") or "")
    if thread_world_version and thread_world_version != world_bible_version():
        return SerialSideScene(reason="world_bible_superseded", is_fallback=True)

    episode: SerialEpisode | None = SerialThreadService(db).current_episode(thread)
    if episode is None:
        return SerialSideScene(
            reason="no_current_episode", is_fallback=True, thread_id=str(thread.id)
        )

    status = str(episode.status or "")
    if status in _SERIAL_DELAYED_STATUSES:
        return SerialSideScene(
            reason="serial_episode_delayed", is_fallback=True, thread_id=str(thread.id)
        )
    if status in _SERIAL_PENDING_STATUSES:
        return SerialSideScene(
            reason="serial_episode_not_ready", is_fallback=True, thread_id=str(thread.id)
        )
    if status == "completed":
        return SerialSideScene(
            reason="serial_episode_completed", is_fallback=True, thread_id=str(thread.id)
        )
    if status not in _SERIAL_READY_STATUSES:
        return SerialSideScene(
            reason="serial_episode_incompatible", is_fallback=True, thread_id=str(thread.id)
        )

    allowed = {location_id, *compatible_locations}
    episode_location = str(episode.location_id or "")
    if episode_location and episode_location not in allowed:
        return SerialSideScene(
            reason="serial_location_mismatch",
            is_fallback=True,
            thread_id=str(thread.id),
            location_id=episode_location,
        )

    return SerialSideScene(
        reason="bound_to_current_beat",
        is_fallback=False,
        thread_id=str(thread.id),
        episode_id=str(episode.id),
        location_id=episode_location or location_id,
    )


# --------------------------------------------------------------------------
# Authored brief assembly
# --------------------------------------------------------------------------


def _build_authored_brief(
    spec: dict[str, Any],
    variant: dict[str, Any],
    *,
    fit: LevelFit,
    control_language: ControlLanguage,
    input_mode: InputMode,
    image_url: str | None,
    serial: SerialSideScene | None,
) -> ScenarioBrief:
    raw_task = variant.get("response_task") or {}
    outcomes = [row for row in (variant.get("outcomes") or []) if isinstance(row, dict)]
    outcome_keys = [str(row["key"]) for row in outcomes if row.get("key")]

    rubric = _localized(raw_task.get("rubric_native"), control_language)
    if input_mode is InputMode.VOICE:
        note = _VOICE_RUBRIC_NOTE.get(control_language, _VOICE_RUBRIC_NOTE["en"])
        rubric = f"{rubric} {note}".strip()

    objective_native = _localized(variant.get("objective_native"), control_language)
    if fit.note_native:
        objective_native = f"{objective_native} {fit.note_native}".strip()

    task = ResponseTask(
        objective_native=_localized(raw_task.get("objective_native"), control_language),
        character_id=str(spec["character_id"]),
        character_name=str(spec["character_name"]),
        opening_line_fr=str(raw_task.get("opening_line_fr") or ""),
        max_turns=int(raw_task.get("max_turns") or MAX_RESPOND_TURNS),
        repair_allowed=bool(raw_task.get("repair_allowed", True)),
        targets=[],
        required_intents=[str(item) for item in (raw_task.get("required_intents") or [])],
        optional_intents=[str(item) for item in (raw_task.get("optional_intents") or [])],
        allowed_outcomes=list(outcome_keys),
        rubric_native=rubric,
        suggested_response_fr=(
            str(raw_task["suggested_response_fr"])
            if raw_task.get("suggested_response_fr")
            else None
        ),
        hint_native=_localized(raw_task.get("hint_native"), control_language) or None,
        translation_native=_localized(raw_task.get("translation_native"), control_language)
        or None,
        estimated_seconds=int(raw_task.get("estimated_seconds") or 120),
    )

    return ScenarioBrief(
        scenario_key=CapabilityKey(str(spec["scenario_key"])),
        content_version=str(spec.get("content_version") or CURRENT_CONTENT_VERSION),
        title_fr=str(variant.get("title_fr") or ""),
        objective_key=str(variant.get("objective_key") or ""),
        objective_native=objective_native,
        level_band=str(variant.get("level_band") or "A1"),
        character_id=str(spec["character_id"]),
        character_name=str(spec["character_name"]),
        location_id=str(spec["location_id"]),
        location_name=str(spec["location_name"]),
        image_url=image_url,
        setup_fr=str(variant.get("setup_fr") or ""),
        setup_native=_localized(variant.get("setup_native"), control_language),
        opening_line_fr=str(variant.get("opening_line_fr") or "") or None,
        response_task=task,
        resolution_lines={str(row["key"]): str(row.get("line_fr") or "") for row in outcomes},
        resolution_summaries={
            str(row["key"]): _localized(row.get("summary_native"), control_language)
            for row in outcomes
        },
        serial_thread_id=serial.thread_id if serial and not serial.is_fallback else None,
        serial_episode_id=serial.episode_id if serial and not serial.is_fallback else None,
        estimated_seconds=int(variant.get("estimated_seconds") or DEFAULT_BUDGET_SECONDS),
        is_authored_fallback=bool(serial.is_fallback) if serial else True,
        control_language=control_language,
    )


# --------------------------------------------------------------------------
# Bounded generation on top of an authored, validated base
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _variation_prompt() -> dict[str, Any] | None:
    """The re-dressing prompt, or ``None`` when it is not deployed.

    A missing prompt template degrades to the authored scene; it never raises
    into the journey-creation path.
    """

    path = JOURNEY_PROMPT_ROOT / VARIATION_PROMPT_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - undeployed template
        logger.warning("journey variation prompt {} unusable: {}", path, exc)
        return None
    return payload if isinstance(payload, dict) and payload.get("user_template") else None


def _generation_llm() -> LLMService | None:
    """Mirror the existing Atelier guard: no flag, no key, no model call."""

    if not settings.ATELIER_LLM_ENABLED:
        return None
    try:
        return LLMService()
    except ValueError:
        return None


def _record_event(
    db: Session,
    event_type: str,
    *,
    user_id: UUID | None,
    scenario_key: str,
    payload: dict[str, Any],
    cost_usd: float = 0.0,
) -> None:
    try:
        PilotEventService(db).record(
            event_type,
            user_id=user_id,
            entity_type="daily_journey_content",
            entity_id=scenario_key,
            payload=payload,
            cost_usd=cost_usd,
        )
    except Exception as exc:  # pragma: no cover - instrumentation must never break content
        logger.warning("journey content event {} not recorded: {}", event_type, exc)


def _render_user_prompt(
    template: str,
    *,
    spec: dict[str, Any],
    variant: dict[str, Any],
    brief: ScenarioBrief,
    rules: ContentRules,
    control_language: ControlLanguage,
) -> str:
    replacements = {
        "scenario_key": str(brief.scenario_key),
        "level_band": brief.level_band,
        "control_language": control_language,
        "character_name": brief.character_name,
        "character_id": brief.character_id,
        "location_name": brief.location_name,
        "location_id": brief.location_id,
        "register": rules.register,
        "objective_native": brief.objective_native,
        "required_facts": "\n".join(
            f"- {item}" for item in (variant.get("required_facts_fr") or [])
        ),
        "target_affordances": "\n".join(
            f"- {item}" for item in (variant.get("target_affordances_fr") or [])
        ),
        "allowed_outcomes": "\n".join(f"- {key}" for key in rules.allowed_outcomes),
        "suggested_response_fr": brief.response_task.suggested_response_fr or "",
        "setup_fr": brief.setup_fr,
        "opening_line_fr": brief.opening_line_fr or "",
        "response_opening_line_fr": brief.response_task.opening_line_fr,
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered


def _parse_variation(content: str, rules: ContentRules) -> dict[str, Any] | None:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    required = (
        "setup_fr",
        "setup_native",
        "opening_line_fr",
        "response_opening_line_fr",
    )
    for key in required:
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            return None
    lines = payload.get("resolution_lines")
    if not isinstance(lines, dict) or set(lines) != set(rules.allowed_outcomes):
        return None
    if any(not isinstance(value, str) or not value.strip() for value in lines.values()):
        return None
    return payload


def _apply_variation(base: ScenarioBrief, payload: dict[str, Any]) -> ScenarioBrief:
    return replace(
        base,
        setup_fr=payload["setup_fr"].strip(),
        setup_native=payload["setup_native"].strip(),
        opening_line_fr=payload["opening_line_fr"].strip(),
        response_task=replace(
            base.response_task,
            opening_line_fr=payload["response_opening_line_fr"].strip(),
        ),
        resolution_lines={key: str(value).strip() for key, value in payload["resolution_lines"].items()},
    )


def _variation_cache_key(
    *,
    user: User,
    brief: ScenarioBrief,
    input_mode: InputMode,
) -> str:
    return build_cache_key(
        user_id=str(user.id),
        scenario_key=str(brief.scenario_key),
        level_band=brief.level_band,
        content_version=brief.content_version,
        control_language=brief.control_language,
        input_mode=str(input_mode),
        prompt_version=JOURNEY_PROMPT_VERSION,
    )


def _generate_variation(
    db: Session,
    *,
    user: User,
    base: ScenarioBrief,
    spec: dict[str, Any],
    variant: dict[str, Any],
    rules: ContentRules,
    input_mode: InputMode,
) -> ScenarioBrief | None:
    """Bounded re-dressing of an already-validated authored scene.

    Returns ``None`` whenever generation is disabled, fails, or produces content
    the validator rejects. The caller then serves the authored brief — the
    learner never sees an unvalidated candidate.
    """

    cache_key = _variation_cache_key(user=user, brief=base, input_mode=input_mode)
    cached = cache_backend.get(CONTENT_CACHE_NAMESPACE, cache_key)
    if isinstance(cached, dict):
        parsed = _parse_variation(json.dumps(cached), rules)
        if parsed is not None:
            candidate = _apply_variation(base, parsed)
            if not validate_scenario_brief(candidate, rules=rules):
                return candidate
        cache_backend.invalidate(CONTENT_CACHE_NAMESPACE, key=cache_key)

    llm = _generation_llm()
    if llm is None:
        return None

    template = _variation_prompt()
    if template is None:
        return None
    defaults = template.get("model_defaults") or {}
    user_prompt = _render_user_prompt(
        template["user_template"],
        spec=spec,
        variant=variant,
        brief=base,
        rules=rules,
        control_language=base.control_language,
    )

    rejections: list[str] = []
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        try:
            result = llm.generate_chat_completion(
                [{"role": "user", "content": user_prompt}],
                system_prompt=template["system"],
                temperature=float(defaults.get("temperature", 0.6)),
                max_tokens=int(defaults.get("max_tokens", 900)),
                response_format=defaults.get("response_format"),
                reasoning_effort=defaults.get("reasoning_effort"),
            )
        except Exception as exc:
            rejections.append(f"attempt {attempt}: provider error {exc.__class__.__name__}")
            _record_event(
                db,
                JourneyEventName.PROVIDER_FAILED,
                user_id=user.id,
                scenario_key=str(base.scenario_key),
                payload={"attempt": attempt, "error": exc.__class__.__name__},
            )
            continue

        _record_event(
            db,
            GENERATED_EVENT,
            user_id=user.id,
            scenario_key=str(base.scenario_key),
            payload={
                "attempt": attempt,
                "provider": result.provider,
                "model": result.model,
                "prompt_version": JOURNEY_PROMPT_VERSION,
                "content_version": base.content_version,
                "total_tokens": result.total_tokens,
            },
            cost_usd=float(result.cost or 0.0),
        )

        parsed = _parse_variation(result.content, rules)
        if parsed is None:
            rejections.append(f"attempt {attempt}: unusable model output")
            continue
        candidate = _apply_variation(base, parsed)
        problems = validate_scenario_brief(candidate, rules=rules)
        if problems:
            rejections.append(f"attempt {attempt}: {problems[0]}")
            continue
        cache_backend.set(
            CONTENT_CACHE_NAMESPACE, cache_key, parsed, CONTENT_CACHE_TTL_SECONDS
        )
        return candidate

    _record_event(
        db,
        JourneyEventName.GENERATION_FALLBACK,
        user_id=user.id,
        scenario_key=str(base.scenario_key),
        payload={
            "attempts": MAX_GENERATION_ATTEMPTS,
            "rejections": rejections,
            "content_version": base.content_version,
        },
    )
    return None


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def resolve_scenario_brief(
    db: Session,
    *,
    user: User,
    scenario_key: CapabilityKey | str,
    content_version: str | None = None,
    level_band: str | None = None,
    input_mode: InputMode = InputMode.TEXT,
    allow_generation: bool = True,
    bind_serial: bool = True,
) -> ScenarioContextResult:
    """Resolve one scenario family into a validated brief.

    ``content_version`` and ``level_band`` are the pinning arguments: WP-02
    stores both on the journey row and passes them back on every reopen, so a
    shipped content bump can never rewrite or strand an active journey.
    """

    version = content_version or CURRENT_CONTENT_VERSION
    control_language = normalize_control_language(user.native_language)
    spec = _load_scenario_spec(scenario_key, version)
    if spec is None:
        reason = (
            "scenario_not_authored"
            if version == CURRENT_CONTENT_VERSION
            else "content_version_unavailable"
        )
        return ContentUnavailable(reason=reason, retry_allowed=False)

    band = level_band or learner_level_band(user)
    variant, fit = _select_variant(spec, band, control_language)
    if variant is None:
        return ContentUnavailable(reason="scenario_has_no_variant", retry_allowed=False)

    rules = _rules_from(spec, variant)
    serial: SerialSideScene | None = None
    if bind_serial:
        serial = derive_serial_side_scene(
            db,
            user=user,
            scenario_key=spec["scenario_key"],
            location_id=str(spec["location_id"]),
            compatible_locations=tuple(
                str(item) for item in (spec.get("serial_locations") or [])
            ),
            content_version=version,
        )
    else:
        serial = SerialSideScene(reason="serial_binding_skipped", is_fallback=True)

    brief = _build_authored_brief(
        spec,
        variant,
        fit=fit,
        control_language=control_language,
        input_mode=input_mode,
        image_url=resolve_media_url(spec.get("image_asset")),
        serial=serial,
    )

    problems = validate_scenario_brief(brief, rules=rules)
    if problems:
        logger.error(
            "authored journey scenario {} @ {} is invalid: {}",
            spec.get("scenario_key"),
            version,
            problems,
        )
        return ContentUnavailable(reason="authored_content_invalid", retry_allowed=False)

    if allow_generation:
        generated = _generate_variation(
            db,
            user=user,
            base=brief,
            spec=spec,
            variant=variant,
            rules=rules,
            input_mode=input_mode,
        )
        if generated is not None:
            return generated

    return brief


def build_scenario_context(
    db: Session,
    *,
    user: User,
    scenario_key: CapabilityKey | None = None,
    input_mode: InputMode = InputMode.TEXT,
) -> ScenarioContextResult:
    """The WP-02 domain callable: today's scene for this learner.

    With no ``scenario_key`` the families are tried in :data:`SCENARIO_PRIORITY`
    order and the first resolvable one wins — deterministic, so a retried create
    cannot silently swap the scene under an in-flight journey.
    """

    keys: tuple[CapabilityKey, ...] = (
        (scenario_key,) if scenario_key is not None else SCENARIO_PRIORITY
    )
    first_reason: str | None = None
    for key in keys:
        result = resolve_scenario_brief(db, user=user, scenario_key=key, input_mode=input_mode)
        if isinstance(result, ScenarioBrief):
            return result
        if first_reason is None:
            first_reason = result.reason
    return ContentUnavailable(
        reason=first_reason or "no_scenario_content", retry_allowed=False
    )


def list_available_scenarios(
    db: Session,
    *,
    user: User,
    input_mode: InputMode = InputMode.TEXT,
    content_version: str | None = None,
) -> list[ScenarioBrief]:
    """Every authored family this learner could be offered, in priority order.

    Costs nothing: generation is off and no image is produced. Invalid families
    are dropped rather than returned in a broken state.
    """

    briefs: list[ScenarioBrief] = []
    for key in SCENARIO_PRIORITY:
        result = resolve_scenario_brief(
            db,
            user=user,
            scenario_key=key,
            content_version=content_version,
            input_mode=input_mode,
            allow_generation=False,
        )
        if isinstance(result, ScenarioBrief):
            briefs.append(result)
    return briefs


def resolve_level_fit(*, user: User, brief: ScenarioBrief) -> LevelFit:
    """How the served band compares with the learner's own band.

    ``ScenarioBrief.level_band`` always reports the band the content was written
    at, never the learner's — the journey never claims a level match it does not
    have. This helper exposes the difference so a surface can say so explicitly.
    """

    band = learner_level_band(user)
    control_language = normalize_control_language(user.native_language)
    if band == brief.level_band:
        return LevelFit(learner_band=band, content_band=brief.level_band, is_exact=True)
    template = (
        _LEVEL_NOTE_ABOVE
        if _band_index(band) > _band_index(brief.level_band)
        else _LEVEL_NOTE_BELOW
    )
    note = template.get(control_language, template["en"]).format(band=brief.level_band)
    return LevelFit(
        learner_band=band,
        content_band=brief.level_band,
        is_exact=False,
        note_native=note,
    )


__all__ = [
    "BAND_LIMITS",
    "CONTENT_CACHE_NAMESPACE",
    "CURRENT_CONTENT_VERSION",
    "JOURNEY_PROMPT_VERSION",
    "MAX_GENERATION_ATTEMPTS",
    "MEDIA_PUBLIC_ROOT",
    "OFF_TOPIC_TERMS",
    "SCENARIO_DATA_ROOT",
    "SCENARIO_PRIORITY",
    "ContentRules",
    "LevelFit",
    "SerialSideScene",
    "available_content_versions",
    "build_scenario_context",
    "derive_serial_side_scene",
    "learner_level_band",
    "list_available_scenarios",
    "reset_content_cache",
    "resolve_level_fit",
    "resolve_media_url",
    "resolve_scenario_brief",
    "scenario_content_rules",
    "scenario_required_facts",
    "scenario_target_affordances",
    "validate_scenario_brief",
    "world_bible_version",
]
