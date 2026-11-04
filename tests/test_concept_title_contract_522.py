"""#522 / #523: a rule's title reaches the learner in the learner's chrome language.

Walk 4 Nov 2026 (`a1-de-fresh`, German chrome): one rule, one day, three names.
The rule card said «Ich bin, du bist: Subjektpronomen und être», La Forge said
«Je suis, tu es : les pronoms et être», and the repair drill said «Regel: I am, you
are: subject pronouns and être», because the drill read the English catalogue
`GrammarConcept.name`. Every learner-facing call site picked its own field.

The contract: `app.services.concept_titles.concept_title(concept, language)` is the
one way to name a rule on a learner's screen. It answers in the chrome language, or
in French (the declared fallback), and never in English for a German or French
learner when a German or French title exists.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.db.models.grammar import GrammarConcept, GrammarConceptLocalization
from app.db.models.user import User
from app.services.journey_contracts import StepKind, TargetKind
from app.services.journey_errata import errata_targets_for_user
from app.services.journey_planner import plan_journey
from tests.test_journey_planner import _brief
from tests.test_repair_shows_the_sentence import _missed_sentence

REPO_ROOT = Path(__file__).resolve().parents[1]

ENGLISH = "I am, you are: subject pronouns and être"
GERMAN = "Ich bin, du bist: Subjektpronomen und être"
FRENCH = "Je suis, tu es : les pronoms et être"


def _learner(db_session, language: str) -> User:
    user = User(
        id=uuid4(),
        email=f"title-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language=language,
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _concept(db_session, *, localized: tuple[str, ...] = ("de", "fr")) -> GrammarConcept:
    concept = GrammarConcept(
        external_id=f"FR_A1_{uuid4().hex[:8]}",
        language="fr",
        name=ENGLISH,
        level="A1",
        category="Verbes",
        active=True,
    )
    db_session.add(concept)
    db_session.flush()
    titles = {"de": GERMAN, "fr": FRENCH}
    for locale in localized:
        db_session.add(GrammarConceptLocalization(concept_id=concept.id, locale=locale, title=titles[locale]))
    db_session.flush()
    db_session.refresh(concept)
    return concept


def _repair_payload(db_session, language: str, concept: GrammarConcept) -> tuple[str, object]:
    user = _learner(db_session, language)
    error = _missed_sentence(db_session, user, concept)
    error.next_review_date = datetime.now(UTC) - timedelta(days=1)
    db_session.flush()
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    assert targets, "the missed sentence was not queued as an erratum"
    plan = plan_journey(scenario=_brief(control_language=language), candidates=[], errata_targets=targets)
    repairs = [
        step
        for step in plan.steps
        if step.kind is StepKind.RECALL and step.target is not None and step.target.kind is TargetKind.ERROR
    ]
    assert repairs, "the stored slip was not planned as a repair"
    return json.dumps(repairs[0].public_prompt, ensure_ascii=False), repairs[0].private_task


@pytest.mark.parametrize(
    ("language", "title", "prefix"),
    [("de", GERMAN, "Regel: "), ("fr", FRENCH, "Règle : ")],
)
def test_the_repair_drill_names_the_rule_in_the_chrome_language(db_session, language, title, prefix) -> None:
    concept = _concept(db_session)
    shown, task = _repair_payload(db_session, language, concept)

    assert prefix + title in shown, f"the repair names the rule in the wrong language: {shown}"
    assert ENGLISH not in shown, f"the English catalogue name reached a {language} learner: {shown}"
    assert ENGLISH not in (task.rule_native or ""), task.rule_native
    assert title in (task.rule_native or "")


def test_a_german_repair_falls_back_to_the_french_title_never_the_english_name(db_session) -> None:
    concept = _concept(db_session, localized=("fr",))
    shown, _task = _repair_payload(db_session, "de", concept)

    assert FRENCH in shown, shown
    assert ENGLISH not in shown, shown


def test_an_english_learner_still_reads_the_catalogue_name(db_session) -> None:
    concept = _concept(db_session, localized=())
    shown, _task = _repair_payload(db_session, "en", concept)

    assert "Rule: " + ENGLISH in shown, shown


def test_one_accessor_answers_for_every_surface(db_session) -> None:
    from app.services.concept_titles import concept_title

    concept = _concept(db_session)
    assert concept_title(concept, "de") == GERMAN
    assert concept_title(concept, "fr") == FRENCH
    assert concept_title(concept, "en") == ENGLISH
    assert concept_title(concept, "de-AT") == GERMAN
    # No Spanish title exists: the declared fallback is French, not the English name.
    assert concept_title(concept, "es") == FRENCH
    assert concept_title(None, "de") == ""

    bare = _concept(db_session, localized=())
    # Nothing authored anywhere: the catalogue name is the floor, never an empty title.
    assert concept_title(bare, "de") == ENGLISH


def test_the_other_surfaces_use_the_accessor(db_session) -> None:
    """The rule card's title helper, the Cahier's `title_fr`, and La Forge's chip all agree."""

    from app.services.atelier import _concept_label, _concept_title_for
    from app.services.concept_titles import concept_title

    concept = _concept(db_session)
    assert _concept_title_for(concept, "de") == concept_title(concept, "de") == GERMAN
    assert _concept_title_for(concept, "fr") == concept_title(concept, "fr") == FRENCH
    # The "French title" label used to read a `title_fr` attribute no concept has, so it
    # answered with the English name.
    assert _concept_label(concept) == FRENCH


# ---------------------------------------------------------------------------
# The ratchet: no module outside the accessor names a rule from `.name`.
# ---------------------------------------------------------------------------

_NAME_READ = re.compile(r"""\bconcept\.name\b|getattr\(\s*concept\s*,\s*["']name["']""")

#: Files that still read the catalogue name today, and how many times. This list may
#: only shrink: a new learner-facing read of `concept.name` must go through
#: `concept_title`. Reads that are not display (SQL filters, logs, LLM prompts for the
#: author's own tooling, the catalogue importer) are listed here too, until they are
#: moved behind a clearly named non-display accessor (stage 2 of #522).
_BASELINE: dict[str, int] = {
    "app/api/v1/endpoints/atelier.py": 3,
    "app/api/v1/endpoints/grammar.py": 7,
    "app/api/v1/endpoints/session_utils.py": 1,
    "app/core/conversation/generator.py": 1,
    "app/services/atelier.py": 9,
    "app/services/atelier_assets.py": 3,
    "app/services/audio_session_service.py": 1,
    "app/services/brief_exercise_service.py": 2,
    "app/services/eclair.py": 1,
    "app/services/exercise_generation.py": 4,
    "app/services/forge.py": 1,
    "app/services/forge_picker.py": 1,
    "app/services/grammar.py": 3,
    "app/services/grammar_catalog.py": 2,
    "app/services/grammar_feedback.py": 4,
    "app/services/grammar_map.py": 1,
    "app/services/grammar_units.py": 1,
    "app/services/journey_learning.py": 1,
    "app/services/level_plan.py": 1,
    "app/services/missions.py": 2,
    "app/services/seance_curriculum.py": 1,
    "app/services/session_moment_planner.py": 9,
    "app/services/session_service.py": 2,
    "app/services/unified_srs.py": 1,
    "app/services/vocabulary_coverage.py": 1,
}


def _reads() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in sorted((REPO_ROOT / "app").rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative == "app/services/concept_titles.py":
            continue
        count = len(_NAME_READ.findall(path.read_text(encoding="utf-8")))
        if count:
            found[relative] = count
    return found


def test_no_new_module_reads_the_catalogue_name_for_display() -> None:
    found = _reads()
    grew = {
        path: (count, _BASELINE.get(path, 0))
        for path, count in found.items()
        if count > _BASELINE.get(path, 0)
    }
    assert not grew, (
        "These modules read `concept.name` more often than the baseline allows. A rule's "
        "title on a learner's screen comes from app.services.concept_titles.concept_title"
        f"(concept, language): {grew}"
    )
