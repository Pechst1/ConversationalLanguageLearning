"""WP-130 A — consistent, visible grammar progress.

Pins:
1. «Tenue» is unchanged: two correct free uses ≥ 7 days apart plus a correct
   spaced item ≥ 14 days after the introduction (the held conditions);
2. one vocabulary — introduced / practising / held — with one word per state
   in en/de/fr (German «gefestigt» is held and nothing else), mirrored by the
   frontend's table;
3. the notebook and the level count the same units per state, band by band,
   from the same function (and the level reads them live);
4. no notebook label says held/tenue/acquis for a unit the level does not hold;
5. the missing «Tenue» evidence is explained from the same fields;
6. the life-walk check (tests/walk_checks_wp130a.py) fires on a disagreement.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.core.srs.memory import Evidence, EvidenceFormat
from app.db.models.grammar import UserGrammarProgress
from app.db.models.user import User
from app.services import concept_life
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.level_coverage import band_unit_ids, unit_bands
from tests.walk_checks_wp130a import check_progress_labels_agree

ROOT = Path(__file__).resolve().parents[1]
DAY0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
HELD_WORDS = re.compile(r"\b(tenue?s?|acquise?s?|maîtrisée?s?|held|mastered|gefestigt|gemeistert|solide)\b", re.I)


# ---------------------------------------------------------------------------
# 1. The held conditions, unchanged
# ---------------------------------------------------------------------------


class _Row:
    reps = 1
    created_at = None
    introduced_at = DAY0
    free_use_first_at = free_use_last_at = spaced_success_at = held_at = None
    state = "in_arbeit"


def test_held_conditions_are_unchanged() -> None:
    assert concept_life.HELD_FREE_USE_GAP_DAYS == 7
    assert concept_life.HELD_SPACED_AFTER_DAYS == 14
    assert concept_life.SPACED_ITEM_FORMATS == frozenset(
        {EvidenceFormat.RECOGNISE, EvidenceFormat.GUIDED, EvidenceFormat.TRANSFORM, EvidenceFormat.RATED}
    )
    row = _Row()
    free = Evidence(EvidenceFormat.PRODUCE, correct=True)
    assert concept_life.progress_stage(row) == concept_life.STAGE_PRACTISING
    assert [m["code"] for m in concept_life.held_missing(row)] == ["free_use_first", "spaced"]

    concept_life.note_concept_evidence(row, free, now=DAY0)
    assert concept_life.held_missing(row) == [
        {"code": "free_use_second", "not_before": "2026-09-08"},
        {"code": "spaced", "not_before": "2026-09-15"},
    ]
    concept_life.note_concept_evidence(row, free, now=DAY0 + timedelta(days=6))
    concept_life.note_concept_evidence(
        row, Evidence(EvidenceFormat.PRODUCE, correct=True, assisted=True), now=DAY0 + timedelta(days=8)
    )
    assert concept_life.held_conditions(row) == (False, False), "6 days apart, and a helped reply, are not enough"
    concept_life.note_concept_evidence(row, free, now=DAY0 + timedelta(days=7))
    concept_life.note_concept_evidence(row, Evidence(EvidenceFormat.RECOGNISE), now=DAY0 + timedelta(days=13))
    assert concept_life.held_conditions(row) == (True, False), "13 days is not yet spaced"
    assert [m["code"] for m in concept_life.held_missing(row)] == ["spaced"]
    assert concept_life.progress_stage(row) == concept_life.STAGE_PRACTISING
    concept_life.note_concept_evidence(row, Evidence(EvidenceFormat.TRANSFORM), now=DAY0 + timedelta(days=14))
    assert row.held_at == DAY0 + timedelta(days=14)
    assert concept_life.progress_stage(row) == concept_life.STAGE_HELD
    assert concept_life.held_missing(row) == []


def test_progress_stage_follows_the_recorded_tenue_only() -> None:
    row = _Row()
    row.reps = 0
    assert concept_life.progress_stage(None) == concept_life.STAGE_NEW
    assert concept_life.progress_stage(row) == concept_life.STAGE_INTRODUCED
    row.reps = 4
    row.state = "gemeistert"  # a top practice score is not «held»
    assert concept_life.progress_stage(row) == concept_life.STAGE_PRACTISING
    row.held_at = DAY0  # a test-out writes held_at too: the level counts it, so does the notebook
    assert concept_life.progress_stage(row) == concept_life.STAGE_HELD


# ---------------------------------------------------------------------------
# 2. One vocabulary
# ---------------------------------------------------------------------------


def test_one_word_per_state_in_every_language() -> None:
    for language, table in concept_life.STAGE_LABELS.items():
        singulars = [table[stage][0] for stage in concept_life.VISIBLE_STAGES]
        assert len(set(singulars)) == 3, language
        for stage in (concept_life.STAGE_INTRODUCED, concept_life.STAGE_PRACTISING):
            assert not HELD_WORDS.search(" ".join(table[stage])), (language, stage)
    assert concept_life.STAGE_LABELS["de"][concept_life.STAGE_HELD] == ("gefestigt", "gefestigt")
    assert concept_life.stage_label("held", "fr", count=0) == "tenue"
    assert concept_life.stage_label("held", "fr", count=2) == "tenues"
    assert concept_life.stage_label("new", "fr") is None


def test_the_frontend_table_mirrors_the_server_words() -> None:
    source = (ROOT / "web-frontend/lib/grammar-stages.ts").read_text(encoding="utf-8")
    for table in concept_life.STAGE_LABELS.values():
        for stage in concept_life.VISIBLE_STAGES:
            one, many = table[stage]
            assert f"{stage}: ['{one}', '{many}']" in source, (stage, one, many)
    # German: «gefestigt» only for held, on the level and the notebook copy alike.
    for path in ("web-frontend/lib/grammar-stages.ts", "web-frontend/components/cahiers/cahier-copy.ts"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "status_solid" not in text
    dossier = (ROOT / "web-frontend/components/atelier-v2/dossier/dossier-copy.ts").read_text(encoding="utf-8")
    assert "Sichere Regeln" not in dossier and "Regeln sicher beherrschen" not in dossier


# ---------------------------------------------------------------------------
# 3–5. The notebook and the level, through the API
# ---------------------------------------------------------------------------


def _signed_in(client: TestClient, db_session) -> tuple[dict[str, str], User]:
    email = f"{uuid4()}@example.com"
    password = "wp130a-secure"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    user = db_session.get(User, UUID(decode_token(token)["sub"]))
    return {"Authorization": f"Bearer {token}"}, user


def _progress(db_session, user: User, concept_id: int, **fields) -> UserGrammarProgress:
    row = UserGrammarProgress(user_id=user.id, concept_id=concept_id, **fields)
    db_session.add(row)
    db_session.commit()
    return row


def _notebook_counts(items: list[dict], band: str) -> dict[str, int]:
    counts = dict.fromkeys(concept_life.VISIBLE_STAGES, 0)
    for item in items:
        if item.get("level_band") == band and item.get("stage") in counts:
            counts[item["stage"]] += 1
    return counts


def test_notebook_and_level_count_the_same_units_per_state(client: TestClient, db_session) -> None:
    FrenchCoreGrammarCatalog(db_session).ensure_catalog(archive_legacy=True)
    headers, user = _signed_in(client, db_session)
    level = client.get("/api/v1/progress/cefr", headers=headers).json()
    band = level["coverage"]["band"]
    units = band_unit_ids(db_session, band)
    assert len(units) >= 5, band
    now = datetime.now(UTC)
    # introduced (rule read, nothing practised) · practising · practising with a
    # top score («Solide» / «Acquis» before WP-130) · held
    _progress(db_session, user, units[0], reps=0, introduced_at=now - timedelta(days=1))
    _progress(db_session, user, units[1], reps=3, score=6.0, state="in_arbeit", introduced_at=now - timedelta(days=9),
              free_use_first_at=now - timedelta(days=9), free_use_last_at=now - timedelta(days=9))
    _progress(db_session, user, units[2], reps=6, score=8.5, state="gefestigt", introduced_at=now - timedelta(days=20))
    _progress(db_session, user, units[3], reps=8, score=9.6, state="gemeistert", introduced_at=now - timedelta(days=25))
    _progress(db_session, user, units[4], reps=7, score=8.0, state="gefestigt", introduced_at=now - timedelta(days=24),
              held_at=now - timedelta(days=2))

    level = client.get("/api/v1/progress/cefr", headers=headers).json()
    notebook = client.get("/api/v1/grammar/notebook", params={"limit": 500, "locale": "de"}, headers=headers).json()
    expected = {"introduced": 1, "practising": 3, "held": 1}
    assert _notebook_counts(notebook, band) == expected
    units_payload = level["coverage"]["units"]
    # The snapshot held 0; a unit held since is read live and the level follows.
    assert {key: units_payload[key] for key in expected} == expected
    assert len([item for item in notebook if item.get("level_band") == band]) == units_payload["total"]

    # Every unit carries the band the level counts it for (v1 included).
    bands = unit_bands(db_session)
    assert all(item["level_band"] == bands.get(item["id"]) for item in notebook)

    by_id = {item["id"]: item for item in notebook}
    for item in notebook:
        if item["stage"] != "held":
            assert not HELD_WORDS.search(item["state_label"].replace("solide à l’entraînement", "")), item
            assert not HELD_WORDS.search(item["stage_label"] or ""), item
    assert by_id[units[2]]["state_label"] == "En route · solide à l’entraînement"
    assert by_id[units[3]]["state_label"] == "En route · solide à l’entraînement"
    assert by_id[units[4]]["state_label"] == "Tenue"
    assert by_id[units[2]]["stage_label"] == "in Übung"
    assert by_id[units[4]]["stage_label"] == "gefestigt"
    # The missing evidence, from the held fields.
    assert [m["code"] for m in by_id[units[1]]["held_missing"]] == ["free_use_second", "spaced"]
    assert by_id[units[4]]["held_missing"] == []

    detail = client.get(f"/api/v1/grammar/notebook/{units[3]}", params={"locale": "fr"}, headers=headers).json()
    assert detail["stage"] == "practising" and detail["stage_label"] == "en route"
    assert detail["progress"]["state_label"] == "En route · solide à l’entraînement"
    assert detail["level_band"] == band

    # The Relevé's register counts by the same stages.
    summary = client.get("/api/v1/grammar/summary", headers=headers).json()
    assert summary["stage_counts"]["held"] == 1
    assert summary["stage_counts"]["practising"] >= 3

    # The walk check agrees on the same records.
    record = {"days": [{"day": 1, "cahier": {"cefr": {"coverage": level["coverage"]}, "notebook": notebook}}]}
    assert check_progress_labels_agree(record) == []


# ---------------------------------------------------------------------------
# 6. The life-walk check
# ---------------------------------------------------------------------------


def _day(notebook: list[dict], units: dict, *, day: int = 30) -> dict:
    return {"day": day, "cahier": {"cefr": {"coverage": {"band": "A1.1", "units": units}}, "notebook": notebook}}


def _item(stage: str, label: str, band: str = "A1.1") -> dict:
    return {"display_title": "Je suis, tu es", "stage": stage, "state_label": label, "stage_label": None, "level_band": band}


def test_walk_check_is_quiet_when_the_surfaces_agree() -> None:
    notebook = [
        _item("practising", "En route · solide à l’entraînement"),
        _item("held", "Tenue"),
        _item("new", "Nouveau"),
        _item("practising", "En route", band="A1.2"),
    ]
    units = {"held": 1, "practising": 1, "introduced": 0, "total": 3}
    assert check_progress_labels_agree({"days": [_day(notebook, units), {"day": 2, "cahier": {}}]}) == []


def test_walk_check_fires_on_day_30_solide_against_zero_held() -> None:
    # The review's day 30: «Solide» in the notebook, «units held: 0» in the level.
    notebook = [_item("practising", "Solide"), _item("practising", "En route"), _item("new", "Nouveau")]
    units = {"held": 0, "practising": 2, "introduced": 0, "total": 3}
    problems = check_progress_labels_agree({"days": [_day(notebook, units)]})
    assert len(problems) == 1 and "Solide" in problems[0], problems


def test_walk_check_fires_when_counts_differ_or_the_record_is_unpatched() -> None:
    notebook = [_item("practising", "En route"), _item("practising", "En route"), _item("new", "Nouveau")]
    units = {"held": 1, "practising": 1, "introduced": 0, "total": 3}
    problems = check_progress_labels_agree({"days": [_day(notebook, units)]})
    assert problems and "≠ level" in problems[0], problems
    short = check_progress_labels_agree({"days": [_day(notebook[:2], units)]})
    assert short and "shows 2 units" in short[0], short
    unpatched = [{"display_title": "x", "state_label": "Solide", "mastery": 8.5}]
    assert "not patched" in check_progress_labels_agree({"days": [_day(unpatched, units)]})[0]
