"""WP-119 §4.1 — the live dossiers of week 2026-W40 and the weekly loader.

Offline: the Anchor comparison runs against the excerpts in
``app/services/revue/weekly/2026-W40/sources/``. No DB, no network.
"""

from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.revue import policy, weekly
from app.services.revue.checks import MAX_SOURCE_AGE_DAYS, failures, run_dossier_checks
from app.services.revue.dossier import EditorialDossier, fold, week_bounds
from app.services.revue.evergreen import evergreen_source_texts, evergreens_for_week
from app.services.revue.weekly import (
    WEEKLY_DIR,
    available_for_week,
    load_week,
    source_texts_for_week,
)

WEEK = "2026-W40"
WEEK_DIR = WEEKLY_DIR / WEEK
SUNDAY = date(2026, 10, 4)

EXPECTED_IDS = {
    "2026-w40-budget-2027",
    "2026-w40-ce-qui-change-1er-octobre",
    "2026-w40-goncourt-roman-retire",
    "2026-w40-paris-plan-canicules",
    "2026-w40-prix-de-l-arc-de-triomphe",
    "2026-w40-prix-produits-frais",
}

DOSSIERS = load_week(WEEK)


def _ids(dossiers: list[EditorialDossier]) -> list[str]:
    return [dossier.id for dossier in dossiers]


def test_week_loads_validates_and_is_sorted() -> None:
    assert week_bounds(WEEK)[1] == SUNDAY
    assert len(DOSSIERS) == 6
    assert set(_ids(DOSSIERS)) == EXPECTED_IDS
    assert _ids(DOSSIERS) == sorted(_ids(DOSSIERS))
    for dossier in DOSSIERS:
        assert dossier.evergreen is False
        assert dossier.week == WEEK
        assert dossier.topic in policy.TOPICS


def test_ids_match_filenames() -> None:
    files = sorted(WEEK_DIR.glob("*.json"))
    assert len(files) == 6
    for path in files:
        assert json.loads(path.read_text(encoding="utf-8"))["id"] == path.stem


def test_topic_mix() -> None:
    topics = [dossier.topic for dossier in DOSSIERS]
    assert len(set(topics)) >= 4
    assert sum(topic in {"food", "culture"} for topic in topics) == 2
    assert sum(topic in {"city", "work"} for topic in topics) == 2
    assert sum(topic in {"sport", "nature"} for topic in topics) == 1
    assert topics.count("politics") == 1


def test_every_source_has_an_excerpt_with_a_header() -> None:
    sources_dir = WEEK_DIR / "sources"
    source_ids = {source.id for dossier in DOSSIERS for source in dossier.sources}
    assert len(source_ids) == sum(len(dossier.sources) for dossier in DOSSIERS)
    assert source_ids == {path.stem for path in sources_dir.glob("*.txt")}
    # never shadowing an evergreen excerpt in the merged map
    assert not source_ids & set(evergreen_source_texts())
    texts = source_texts_for_week(WEEK)
    for dossier in DOSSIERS:
        for source in dossier.sources:
            header = (sources_dir / f"{source.id}.txt").read_text(encoding="utf-8").splitlines()[0]
            assert header == f"# {source.url} — fetched 2026-10-02", source.id
            excerpt = texts[source.id]
            assert not excerpt.startswith("#")
            assert len(fold(excerpt).split(" ")) <= 120, source.id
            assert source.url.startswith("https://")


def test_every_quote_is_verbatim_in_its_excerpt() -> None:
    texts = source_texts_for_week(WEEK)
    for dossier in DOSSIERS:
        sources = {source.id: source for source in dossier.sources}
        for claim in dossier.claims:
            assert fold(claim.quote) in fold(texts[claim.source_id]), (dossier.id, claim.id)
            assert claim.url == sources[claim.source_id].url, (dossier.id, claim.id)
            assert claim.published_at == sources[claim.source_id].published_at, (
                dossier.id,
                claim.id,
            )


def test_every_claim_is_recent() -> None:
    oldest = SUNDAY - timedelta(days=MAX_SOURCE_AGE_DAYS)
    for dossier in DOSSIERS:
        for claim in dossier.claims:
            assert oldest <= claim.published_at <= SUNDAY, (dossier.id, claim.id)
        for source in dossier.sources:
            assert oldest <= source.published_at <= SUNDAY, (dossier.id, source.id)


def test_time_scope_fits_the_week() -> None:
    monday, sunday = week_bounds(WEEK)
    for dossier in DOSSIERS:
        scope = dossier.time_scope
        assert scope.start <= sunday and scope.end >= monday, dossier.id
        assert scope.relevant_until >= date(2026, 10, 18), dossier.id


def test_nothing_is_sensitive() -> None:
    for dossier in DOSSIERS:
        for text in (dossier.title_fr, dossier.summary_fr, *dossier.uncertainty_texts()):
            assert not policy.is_sensitive(text), (dossier.id, text)
        for claim in dossier.claims:
            assert not policy.is_sensitive(claim.fr), (dossier.id, claim.id)
            assert not policy.is_sensitive(claim.quote), (dossier.id, claim.id)


def test_place_briefs_paint_no_people() -> None:
    for dossier in DOSSIERS:
        assert len(dossier.places) == 1
        for place in dossier.places:
            assert place.brief.strip(), (dossier.id, place.id)
            assert policy.plate_forbidden_hits(place.brief) == [], (dossier.id, place.brief)


def test_editorial_shape() -> None:
    for dossier in DOSSIERS:
        assert 3 <= len(dossier.claims) <= 4, dossier.id
        assert dossier.facts(), dossier.id
        attributed = [
            claim for claim in dossier.interpretations() if (claim.attributed_to or "").strip()
        ]
        assert attributed, dossier.id
        assert 1 <= len(dossier.uncertainties) <= 2, dossier.id
        assert 1 <= len(dossier.entities) <= 3, dossier.id
        assert len(dossier.angles) == 2, dossier.id
        assert len({angle.purpose for angle in dossier.angles}) == 2, dossier.id


def test_vignette_object_and_angle_staging() -> None:
    """WP-119 §10c / WP-120 §4.1: one vignette object per story; every angle names its
    participation and a guest of the topic's affinity (``policy.GUEST_AFFINITY``)."""

    for dossier in DOSSIERS:
        assert (dossier.vignette_object_fr or "").strip(), dossier.id
        affinity = {row["id"] for row in policy.GUEST_AFFINITY.get(dossier.topic, [])}
        for angle in dossier.angles:
            assert angle.participation in {"none", "helps", "works", "formal"}, (dossier.id, angle.id)
            assert angle.guest_fit in policy.GUEST_CAST_IDS, (dossier.id, angle.id)
            assert angle.guest_fit in affinity, (dossier.id, angle.id)
    raw = [json.loads(path.read_text()) for path in sorted(WEEK_DIR.glob("*.json"))]
    for data in raw:  # explicit in the files, not left to the model default
        assert all("participation" in a and "guest_fit" in a for a in data["angles"]), data["id"]


@pytest.mark.parametrize("dossier", DOSSIERS, ids=_ids(DOSSIERS))
def test_week_passes_run_dossier_checks(dossier: EditorialDossier) -> None:
    results = run_dossier_checks(dossier, source_texts=source_texts_for_week(WEEK), week=WEEK)
    assert results
    assert failures(results) == []


def test_the_same_dossiers_fail_temporal_a_month_later() -> None:
    # The window is real: three weeks after W40 every claim is stale.
    dossier = next(d for d in DOSSIERS if d.id == "2026-w40-prix-de-l-arc-de-triomphe")
    reasons = {
        result.reason
        for result in failures(
            run_dossier_checks(dossier, source_texts=source_texts_for_week(WEEK), week="2026-W44")
        )
    }
    assert {"not_this_week", "expired", "stale_source"} <= reasons


def test_source_texts_merge_week_and_evergreens() -> None:
    texts = source_texts_for_week(WEEK)
    assert set(evergreen_source_texts()) <= set(texts)
    assert "w40_budget_lfpt" in texts
    # a week without a folder still anchors the evergreens
    assert source_texts_for_week("2031-W01") == evergreen_source_texts()


def test_available_lists_live_dossiers_first() -> None:
    available = available_for_week(WEEK)
    assert len(available) >= 3
    assert _ids(available) == _ids(DOSSIERS)
    assert all(not dossier.evergreen for dossier in available)


def test_available_falls_back_to_evergreens() -> None:
    available = available_for_week("2026-W02")
    assert available
    assert all(dossier.evergreen for dossier in available)
    assert _ids(available) == _ids(evergreens_for_week("2026-W02"))


def test_missing_week_is_empty_and_bad_week_raises() -> None:
    assert load_week("2031-W01") == []
    with pytest.raises(ValueError):
        load_week("2026-40")


def test_load_returns_copies() -> None:
    first = load_week(WEEK)
    first[0].title_fr = "changé"
    assert load_week(WEEK)[0].title_fr != "changé"


def _copy_week(tmp_path: Path, ids: list[str]) -> None:
    target = tmp_path / WEEK
    (target / "sources").mkdir(parents=True)
    for dossier_id in ids:
        shutil.copy(WEEK_DIR / f"{dossier_id}.json", target / f"{dossier_id}.json")
    for path in (WEEK_DIR / "sources").glob("*.txt"):
        shutil.copy(path, target / "sources" / path.name)


def test_a_thin_week_is_topped_up_with_evergreens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_week(tmp_path, ["2026-w40-budget-2027"])
    monkeypatch.setattr(weekly, "WEEKLY_DIR", tmp_path)
    available = available_for_week(WEEK)
    assert len(available) == 3
    assert available[0].id == "2026-w40-budget-2027"
    assert all(dossier.evergreen for dossier in available[1:])
    assert _ids(available[1:]) == _ids(evergreens_for_week(WEEK))[:2]


def test_a_dossier_filed_under_the_wrong_week_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_week(tmp_path, [])
    data = json.loads((WEEK_DIR / "2026-w40-budget-2027.json").read_text(encoding="utf-8"))
    data["week"] = "2026-W41"
    (tmp_path / WEEK / "stray.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(weekly, "WEEKLY_DIR", tmp_path)
    with pytest.raises(ValueError):
        load_week(WEEK)


@pytest.mark.parametrize("dossier", DOSSIERS, ids=_ids(DOSSIERS))
def test_week_places_resolve_exact_or_city(dossier: EditorialDossier) -> None:
    # WP-120 phase A: every place has a stored geo, the Geo check holds, and the
    # resolver (gazetteer, then the stored geo as the proposal) keeps exact or city.
    from app.services.revue.checks import check_geo
    from app.services.revue.geo import geocode_dossier, in_france

    assert failures(check_geo(dossier)) == []
    for place in geocode_dossier(dossier).places:
        assert place.geo is not None, place.id
        assert place.geo.precision in {"exact", "city"}, place.id
        assert in_france(place.geo.lat, place.geo.lon), place.id
