"""WP-L2 · The syllabus: grammar catalogue v2, v1→v2 migration, prerequisites, lexicon, can-dos.

Acceptance (docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-23-learning.md, WP-L2):
(a) the v2 catalogue loads; every unit has a sub-band, a localized name and rule in en/de/fr,
    a detector, and valid, acyclic prerequisites;
(b) prerequisites are consistent with the teaching order;
(c) the v1→v2 mapping covers every v1 concept and migrating progress preserves scores;
(d) ``AtelierScheduler.select_today`` never introduces a unit before its prerequisites;
plus the data files the later packages read: the lexicon's sub-bands and the can-do list.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.config import settings
from app.db.models.grammar import (
    GrammarConcept,
    GrammarConceptArchive,
    GrammarConceptLocalization,
    UserGrammarProgress,
)
from app.db.models.user import User
from app.services.atelier import AtelierScheduler
from app.services.grammar_catalog import (
    FRENCH_CORE_CATALOG_V2_VERSION,
    FRENCH_CORE_CATALOG_VERSION,
    SUB_BANDS,
    FrenchCoreGrammarCatalog,
    active_catalog_version,
    catalog_rows,
    detector_matches,
    load_v1_to_v2_mapping,
)

ROOT = Path(__file__).resolve().parents[1]
CAN_DOS_PATH = ROOT / "app" / "data" / "syllabus" / "fr_core_can_dos_v2.json"
LEXICON_PATH = ROOT / "app" / "data" / "lexical" / "fr_core_lexicon.json"

#: WP-L2's targets (≈): A1 30, A2 35, B1 40, B2 45.
BAND_TARGETS = {"A1": 30, "A2": 35, "B1": 40, "B2": 45}

#: Words the rule may not use at A1–A2 (due diligence §3, problem 2).
A1_A2_JARGON = re.compile(
    r"determiner|noun phrase|mass noun|past participle|auxiliary|bounded|"
    r"partizip|hilfsverb|akkusativ|dativ|déterminant|auxiliaire|participe passé",
    re.IGNORECASE,
)


def _v2_rows() -> list[dict]:
    return catalog_rows(FRENCH_CORE_CATALOG_V2_VERSION)


def _order(sub_band: str) -> int:
    return SUB_BANDS.index(sub_band)


# ---------------------------------------------------------------------------
# (a) the catalogue loads and every unit is complete
# ---------------------------------------------------------------------------


def test_default_catalogue_is_still_v1() -> None:
    assert settings.ATELIER_GRAMMAR_CATALOG_VERSION == "v1"
    assert active_catalog_version() == FRENCH_CORE_CATALOG_VERSION


def test_v2_catalogue_loads_about_150_units_in_every_sub_band() -> None:
    rows = _v2_rows()
    ids = [row["external_id"] for row in rows]
    assert len(ids) == len(set(ids))
    assert 140 <= len(rows) <= 165
    per_band = Counter(row["level"] for row in rows)
    for band, target in BAND_TARGETS.items():
        assert abs(per_band[band] - target) <= 6, (band, per_band[band])
    per_sub_band = Counter(row["syllabus"]["sub_band"] for row in rows)
    assert set(per_sub_band) == set(SUB_BANDS)
    assert all(12 <= count <= 25 for count in per_sub_band.values()), per_sub_band
    assert all(row["catalog_version"] == FRENCH_CORE_CATALOG_V2_VERSION for row in rows)


def test_every_unit_has_sub_band_names_rules_and_detector_in_three_languages() -> None:
    for row in _v2_rows():
        syllabus = row["syllabus"]
        unit = row["external_id"]
        assert syllabus["sub_band"] in SUB_BANDS, unit
        assert row["level"] == syllabus["sub_band"][:2], unit
        assert syllabus["review_status"] == "draft", unit
        names = syllabus["names"]
        rules = syllabus["rule_short"]
        for locale in ("en", "de", "fr"):
            assert names[locale].strip(), (unit, locale)
            assert rules[locale].strip(), (unit, locale)
            assert len(rules[locale].split()) <= 20, (unit, locale, rules[locale])
        # The de/fr rules are real translations, not the English sentence again
        # (the v1 localizations were English in all three).
        assert rules["de"] != rules["en"] and rules["fr"] != rules["en"], unit
        if row["level"] in ("A1", "A2"):
            for locale in ("en", "de", "fr"):
                assert not A1_A2_JARGON.search(rules[locale]), (unit, locale, rules[locale])
        assert len(row["anchor_examples"].split(" | ")) >= 2, unit
        assert row["core_rule"] and row["description"], unit


def test_every_detector_is_usable() -> None:
    kinds = Counter()
    for row in _v2_rows():
        detector = row["syllabus"]["detector"]
        unit = row["external_id"]
        assert detector and detector["kind"] in {"regex", "llm"}, unit
        kinds[detector["kind"]] += 1
        if detector["kind"] == "llm":
            assert len(detector["description"]) >= 20, unit
            continue
        re.compile(detector["pattern"])
        texts = row["anchor_examples"].split(" | ") + [row["source_refs"]["blueprint_seed"]["sentence_xray"]["sentence"]]
        assert any(detector_matches(detector, text) for text in texts), unit
    # A deterministic pattern wherever one exists: most units have one.
    assert kinds["regex"] >= 0.75 * sum(kinds.values()), kinds


def test_detector_folds_ios_apostrophes() -> None:
    avoir = next(row for row in _v2_rows() if row["external_id"] == "FR2_A11_AVOIR")
    assert detector_matches(avoir["syllabus"]["detector"], "J’ai vingt ans.")
    assert not detector_matches(avoir["syllabus"]["detector"], "Je suis content.")


def test_prerequisites_and_contrast_partners_are_valid_and_acyclic() -> None:
    rows = _v2_rows()
    ids = {row["external_id"] for row in rows}
    graph = {row["external_id"]: row["syllabus"]["prerequisites"] for row in rows}
    for row in rows:
        unit = row["external_id"]
        assert unit not in graph[unit]
        assert set(graph[unit]) <= ids, unit
        partners = row["syllabus"]["contrast_partners"]
        assert unit not in partners and set(partners) <= ids, unit

    state: dict[str, int] = {}

    def visit(node: str, path: tuple[str, ...]) -> None:
        if state.get(node) == 2:
            return
        assert state.get(node) != 1, f"prerequisite cycle: {' -> '.join(path + (node,))}"
        state[node] = 1
        for prerequisite in graph[node]:
            visit(prerequisite, path + (node,))
        state[node] = 2

    for node in graph:
        visit(node, ())


def test_foundation_flag_marks_units_that_others_depend_on() -> None:
    rows = _v2_rows()
    depended_on = {p for row in rows for p in row["syllabus"]["prerequisites"]}
    for row in rows:
        assert row["is_foundation"] == (row["external_id"] in depended_on), row["external_id"]


def test_due_diligence_placements() -> None:
    """The moves every reference agreed on (GRAMMAR-DUE-DILIGENCE §2.3–2.4)."""

    by_id = {row["external_id"]: row["syllabus"]["sub_band"] for row in _v2_rows()}
    assert by_id["FR2_A11_ETRE"] == "A1.1"
    assert by_id["FR2_A11_NEGATION"] == "A1.1"  # pas de moved to A1
    assert by_id["FR2_A11_JE_VOUDRAIS"] == "A1.1"  # the polite formula
    assert by_id["FR2_A22_FUTUR_SIMPLE"].startswith("A2")
    assert by_id["FR2_B11_PLUS_QUE_PARFAIT"].startswith("B1")
    assert by_id["FR2_B12_PASSIVE"].startswith("B1")
    rows = _v2_rows()
    first_a1 = [row["external_id"] for row in rows][:3]
    assert first_a1[0] == "FR2_A11_ETRE"  # a verb before the noun-phrase units
    # One imparfait-vs-passé-composé concept, not two rows counted twice.
    assert sum("imparfait_vs_passe_compose" == row["subskill"] for row in rows) == 1


# ---------------------------------------------------------------------------
# (b) prerequisites follow the teaching order
# ---------------------------------------------------------------------------


def test_prerequisites_come_earlier_in_teaching_order_and_never_in_a_later_sub_band() -> None:
    rows = _v2_rows()
    by_id = {row["external_id"]: row for row in rows}
    orders = [row["difficulty_order"] for row in rows]
    assert orders == sorted(orders) and len(set(orders)) == len(orders)
    sub_band_order = [_order(row["syllabus"]["sub_band"]) for row in rows]
    assert sub_band_order == sorted(sub_band_order), "rows are listed in sub-band order"
    for row in rows:
        for prerequisite in row["syllabus"]["prerequisites"]:
            before = by_id[prerequisite]
            assert before["difficulty_order"] < row["difficulty_order"], (prerequisite, row["external_id"])
            assert _order(before["syllabus"]["sub_band"]) <= _order(row["syllabus"]["sub_band"])


# ---------------------------------------------------------------------------
# (c) v1 → v2 mapping and progress migration
# ---------------------------------------------------------------------------


def test_mapping_covers_every_v1_concept_with_existing_v2_units() -> None:
    mapping = load_v1_to_v2_mapping()
    v1_ids = {row["external_id"] for row in catalog_rows(FRENCH_CORE_CATALOG_VERSION)}
    v2_ids = {row["external_id"] for row in _v2_rows()}
    assert set(mapping) == v1_ids
    for v1_id, targets in mapping.items():
        assert targets, v1_id
        assert set(targets) <= v2_ids, (v1_id, set(targets) - v2_ids)


def _user(db_session, *, cefr: str = "A1.1") -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
        cefr_estimate=cefr,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _by_external(db_session, external_id: str) -> GrammarConcept:
    return db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()


def _progress(db_session, user: User, concept: GrammarConcept, **fields) -> UserGrammarProgress:
    row = UserGrammarProgress(user_id=user.id, concept_id=concept.id, **fields)
    db_session.add(row)
    db_session.commit()
    return row


def _progress_on(db_session, user: User, external_id: str) -> UserGrammarProgress | None:
    concept = _by_external(db_session, external_id)
    return (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one_or_none()
    )


def test_switching_to_v2_carries_every_learner_score_over(db_session) -> None:
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
    learner = _user(db_session)
    other = _user(db_session)
    reviewed = datetime.now(UTC) - timedelta(days=2)
    due = datetime.now(UTC) + timedelta(days=5)
    _progress(db_session, learner, _by_external(db_session, "FR_A1_VERB_001"),
              score=6.5, reps=4, state="in_arbeit", last_review=reviewed, next_review=due)
    # A merge: the A2 «intro» and the B1 row both become one v2 concept.
    _progress(db_session, learner, _by_external(db_session, "FR_A2_TENSE_004"), score=4.0, reps=2)
    _progress(db_session, learner, _by_external(db_session, "FR_B1_TENSE_001"), score=8.0, reps=3)
    _progress(db_session, other, _by_external(db_session, "FR_A2_PRON_002"), score=9.0, reps=7, state="gefestigt")
    v1_rows_before = db_session.query(UserGrammarProgress).count()

    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()

    er_verbs = _progress_on(db_session, learner, "FR2_A11_ER_VERBS")
    assert er_verbs is not None
    assert (er_verbs.score, er_verbs.reps, er_verbs.state) == (6.5, 4, "in_arbeit")
    assert er_verbs.next_review.replace(tzinfo=UTC) == due.replace(microsecond=due.microsecond)
    assert "FR_A1_VERB_001" in (er_verbs.notes or "")
    # Only the foundation child inherits; the other children are new to the learner.
    assert _progress_on(db_session, learner, "FR2_A11_ALLER_VENIR") is None
    # Merge: the strongest row wins.
    assert _progress_on(db_session, learner, "FR2_A22_IMP_VS_PC").score == 8.0
    assert _progress_on(db_session, other, "FR2_A21_Y_PLACE").score == 9.0
    # v1 rows are copied, not moved; the v1 concepts are archived with their replacement.
    assert db_session.query(UserGrammarProgress).count() == v1_rows_before + 3
    v1 = _by_external(db_session, "FR_A1_VERB_001")
    assert v1.active is False
    archive = db_session.query(GrammarConceptArchive).filter(GrammarConceptArchive.concept_id == v1.id).one()
    assert archive.replacement_external_id == "FR2_A11_ER_VERBS"

    # Idempotent, and it never overwrites progress made on v2.
    er_verbs.score = 9.5
    db_session.commit()
    assert FrenchCoreGrammarCatalog(db_session, "v2").migrate_progress_to_v2() == 0
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    assert _progress_on(db_session, learner, "FR2_A11_ER_VERBS").score == 9.5

    # Switching back to v1 finds v1 untouched.
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
    assert _by_external(db_session, "FR_A1_VERB_001").active is True
    assert _by_external(db_session, "FR2_A11_ER_VERBS").active is False
    assert _progress_on(db_session, learner, "FR_A1_VERB_001").score == 6.5


def test_v2_seed_stores_prerequisites_and_localized_rules(db_session) -> None:
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    rows = {row["external_id"]: row for row in _v2_rows()}
    active = (
        db_session.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True), GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_V2_VERSION)
        .all()
    )
    assert len(active) == len(rows)
    external_by_id = {concept.id: concept.external_id for concept in active}
    for concept in active:
        expected = rows[concept.external_id]["syllabus"]["prerequisites"]
        assert [external_by_id[pid] for pid in concept.prerequisites] == expected
        assert concept.source_refs["syllabus"]["sub_band"] == rows[concept.external_id]["syllabus"]["sub_band"]
    etre = _by_external(db_session, "FR2_A11_ETRE")
    localizations = {
        row.locale: row
        for row in db_session.query(GrammarConceptLocalization).filter(GrammarConceptLocalization.concept_id == etre.id)
    }
    assert set(localizations) == {"en", "de", "fr"}
    for locale in ("en", "de", "fr"):
        assert localizations[locale].short_description == rows["FR2_A11_ETRE"]["syllabus"]["rule_short"][locale]
    assert localizations["de"].category_label == "Verben"


# ---------------------------------------------------------------------------
# (d) select_today respects prerequisites
# ---------------------------------------------------------------------------


@pytest.fixture()
def v2_active(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    yield


def _assert_prerequisites_met(db_session, user: User, selections) -> None:
    introduced = {
        row.concept_id for row in db_session.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user.id)
    }
    for selection in selections:
        concept = selection.concept
        if concept.id in introduced:
            continue
        missing = [pid for pid in concept.prerequisites or [] if pid not in introduced]
        assert not missing, (concept.external_id, missing)


def test_a_newcomer_starts_with_etre_and_never_meets_a_unit_before_its_prerequisites(db_session, v2_active) -> None:
    user = _user(db_session)
    user.daily_goal_minutes = 20
    db_session.commit()
    scheduler = AtelierScheduler(db_session)
    first = scheduler.select_today(user)
    assert first and first[0].concept.external_id == "FR2_A11_ETRE"
    assert all(selection.concept.catalog_version == FRENCH_CORE_CATALOG_V2_VERSION for selection in first)
    _assert_prerequisites_met(db_session, user, first)

    # Walk the ladder: introduce whatever is served, day after day.
    served: list[str] = []
    for _ in range(12):
        picks = scheduler.select_today(user)
        _assert_prerequisites_met(db_session, user, picks)
        for selection in picks:
            if selection.progress is None and _progress_on(db_session, user, selection.concept.external_id) is None:
                _progress(db_session, user, selection.concept, score=8.0, reps=1,
                          next_review=datetime.now(UTC) + timedelta(days=30))
                served.append(selection.concept.external_id)
    assert "FR2_A11_ETRE" in served
    order = {row["external_id"]: row["difficulty_order"] for row in _v2_rows()}
    rows = {row["external_id"]: row for row in _v2_rows()}
    for position, unit in enumerate(served):
        for prerequisite in rows[unit]["syllabus"]["prerequisites"]:
            assert prerequisite in served[:position], (unit, prerequisite)
        assert order[unit] > 0


def test_an_a2_placed_learner_starts_in_a2_not_back_at_a1(db_session, v2_active) -> None:
    user = _user(db_session, cefr="A2.1")
    user.daily_goal_minutes = 20
    db_session.commit()
    picks = AtelierScheduler(db_session).select_today(user)
    new_picks = [selection for selection in picks if selection.role == "new"]
    assert new_picks
    for selection in new_picks:
        assert selection.concept.level == "A2"
        # A1 prerequisites count as known at A2; A2 ones must be introduced first.
        a2_prerequisites = [
            pid for pid in selection.concept.prerequisites or []
            if db_session.get(GrammarConcept, pid).level == "A2"
        ]
        assert not a2_prerequisites, selection.concept.external_id


def test_a_unit_whose_prerequisite_is_missing_is_skipped(db_session, v2_active) -> None:
    user = _user(db_session)
    scheduler = AtelierScheduler(db_session)
    scheduler.ensure_catalog()
    # ETRE introduced; AVOIR (needs ETRE) is now ready, IL_Y_A (needs AVOIR) is not.
    _progress(db_session, user, _by_external(db_session, "FR2_A11_ETRE"), score=8.0, reps=1,
              next_review=datetime.now(UTC) + timedelta(days=30))
    user.daily_goal_minutes = 20
    db_session.commit()
    picks = [selection.concept.external_id for selection in scheduler.select_today(user)]
    assert "FR2_A11_IL_Y_A" not in picks
    assert "FR2_A11_AVOIR" in picks or "FR2_A11_UN_UNE" in picks


# ---------------------------------------------------------------------------
# Lexicon and can-dos
# ---------------------------------------------------------------------------


def _lexicon() -> dict:
    return json.loads(LEXICON_PATH.read_text(encoding="utf-8"))


def test_lexicon_reaches_b1_with_sub_bands() -> None:
    lemmas = _lexicon()["lemmas"]
    assert len(lemmas) >= 2400
    per_sub_band = Counter(entry["sub_band"] for entry in lemmas.values())
    assert set(per_sub_band) == {"A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2"}
    for lemma, entry in lemmas.items():
        assert entry["sub_band"].startswith(entry["band"]), lemma
    assert sum(count for band, count in per_sub_band.items() if band.startswith("A1")) >= 600


def test_can_dos_cover_every_sub_band_with_known_units_and_words() -> None:
    doc = json.loads(CAN_DOS_PATH.read_text(encoding="utf-8"))
    assert doc["catalog_version"] == FRENCH_CORE_CATALOG_V2_VERSION
    units = {row["external_id"]: row["syllabus"]["sub_band"] for row in _v2_rows()}
    lemmas = _lexicon()["lemmas"]
    lexicon_bands = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2")
    ids: set[str] = set()
    assert set(doc["sub_bands"]) == set(SUB_BANDS)
    for sub_band, tasks in doc["sub_bands"].items():
        assert 6 <= len(tasks) <= 10, sub_band
        for task in tasks:
            assert task["id"] not in ids
            ids.add(task["id"])
            for key in ("title_fr", "title_en", "title_de"):
                assert task[key].strip(), (task["id"], key)
            assert task["units"] and task["words"], task["id"]
            for unit in task["units"]:
                assert unit in units, (task["id"], unit)
                assert _order(units[unit]) <= _order(sub_band), (task["id"], unit)
            for word in task["words"]:
                assert word in lemmas, (task["id"], word)
                if sub_band in lexicon_bands:
                    assert lexicon_bands.index(lemmas[word]["sub_band"]) <= lexicon_bands.index(sub_band), (
                        task["id"], word)
