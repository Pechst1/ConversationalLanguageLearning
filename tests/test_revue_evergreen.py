"""WP-119 §4.3 — the twelve evergreen editorial dossiers.

Offline: the Anchor comparison runs against the excerpts in
``app/services/revue/evergreen/sources/``. No DB, no network.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.services.revue import policy
from app.services.revue.checks import failures, run_dossier_checks
from app.services.revue.dossier import EditorialDossier, fold
from app.services.revue.evergreen import (
    EVERGREEN_DIR,
    SOURCES_DIR,
    evergreen_for,
    evergreen_source_texts,
    evergreens_for_week,
    load_evergreens,
)

EXPECTED_IDS = {
    "evergreen-bac",
    "evergreen-beaujolais-nouveau",
    "evergreen-fete-de-la-musique",
    "evergreen-galette-des-rois",
    "evergreen-greve-transports",
    "evergreen-marche-du-dimanche",
    "evergreen-noel-au-marche",
    "evergreen-quatorze-juillet",
    "evergreen-rentree",
    "evergreen-soldes-d-hiver",
    "evergreen-tour-de-france",
    "evergreen-toussaint",
}

DOSSIERS = load_evergreens()


def _ids(dossiers: list[EditorialDossier]) -> list[str]:
    return [dossier.id for dossier in dossiers]


def _start_week(dossier: EditorialDossier) -> str:
    year, week, _ = dossier.time_scope.start.isocalendar()
    return f"{year}-W{week:02d}"


def test_all_twelve_load_validate_and_are_sorted() -> None:
    assert len(DOSSIERS) == 12
    assert set(_ids(DOSSIERS)) == EXPECTED_IDS
    assert _ids(DOSSIERS) == sorted(_ids(DOSSIERS))
    for dossier in DOSSIERS:
        assert dossier.evergreen is True
        assert dossier.topic in policy.TOPICS


def test_ids_are_unique_and_match_filenames() -> None:
    files = sorted(EVERGREEN_DIR.glob("*.json"))
    assert len(files) == 12
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["id"] == path.stem
    assert len(set(_ids(DOSSIERS))) == len(DOSSIERS)


def test_stored_week_is_the_week_the_window_starts_in() -> None:
    for dossier in DOSSIERS:
        assert dossier.week == _start_week(dossier), dossier.id


def test_every_source_has_an_excerpt_with_a_header() -> None:
    texts = evergreen_source_texts()
    source_ids = {source.id for dossier in DOSSIERS for source in dossier.sources}
    # source ids are global: one excerpt file per id, no two dossiers share an id by accident
    assert len(source_ids) == sum(len(dossier.sources) for dossier in DOSSIERS)
    assert source_ids == set(texts)
    for dossier in DOSSIERS:
        for source in dossier.sources:
            header = (SOURCES_DIR / f"{source.id}.txt").read_text(encoding="utf-8").splitlines()[0]
            assert header.startswith(f"# {source.url} — fetched "), source.id
            excerpt = texts[source.id]
            assert not excerpt.startswith("#")
            assert len(fold(excerpt).split(" ")) <= 120, source.id
            assert source.url.startswith("https://")


def test_every_quote_is_verbatim_in_its_excerpt() -> None:
    texts = evergreen_source_texts()
    for dossier in DOSSIERS:
        sources = {source.id: source for source in dossier.sources}
        for claim in dossier.claims:
            assert fold(claim.quote) in fold(texts[claim.source_id]), (dossier.id, claim.id)
            assert claim.url == sources[claim.source_id].url, (dossier.id, claim.id)
            assert claim.published_at == sources[claim.source_id].published_at, (
                dossier.id,
                claim.id,
            )


def test_nothing_is_sensitive() -> None:
    for dossier in DOSSIERS:
        for text in (dossier.title_fr, dossier.summary_fr):
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


def test_relevant_until_is_two_weeks_after_the_window() -> None:
    for dossier in DOSSIERS:
        scope = dossier.time_scope
        assert (scope.relevant_until - scope.end).days >= 14, dossier.id


def test_every_week_of_2026_has_an_evergreen() -> None:
    last = date(2026, 12, 28).isocalendar()[1]
    assert last == 53
    for number in range(1, last + 1):
        week = f"2026-W{number:02d}"
        assert evergreens_for_week(week), week


def test_beaujolais_week() -> None:
    assert "evergreen-beaujolais-nouveau" in _ids(evergreens_for_week("2026-W47"))


def test_week_lookup_ignores_the_stored_week_and_prefers_seasonal() -> None:
    # Toussaint is stored as W44 but its window runs into W45.
    assert "evergreen-toussaint" in _ids(evergreens_for_week("2026-W45"))
    # Year-round dossiers come after the seasonal ones.
    first = evergreen_for("2026-W47")
    assert first is not None and first.id == "evergreen-beaujolais-nouveau"
    # A topic filter falls through to the year-round ones.
    work = evergreen_for("2026-W47", topic="work")
    assert work is not None and work.id == "evergreen-greve-transports"
    assert evergreen_for("2026-W47", topic="politics") is None
    # Outside 2026 only nothing matches (the windows are 2026 windows).
    assert evergreens_for_week("2028-W10") == []


def test_load_returns_copies() -> None:
    first = load_evergreens()
    first[0].title_fr = "changé"
    assert load_evergreens()[0].title_fr != "changé"


@pytest.mark.parametrize("dossier", DOSSIERS, ids=_ids(DOSSIERS))
def test_evergreens_pass_run_dossier_checks(dossier: EditorialDossier) -> None:
    results = run_dossier_checks(
        dossier, source_texts=evergreen_source_texts(), week=_start_week(dossier)
    )
    assert results
    assert failures(results) == []


@pytest.mark.parametrize("dossier", DOSSIERS, ids=_ids(DOSSIERS))
def test_evergreen_places_resolve_exact_or_city(dossier: EditorialDossier) -> None:
    # WP-120 phase A: every place has a stored geo, the Geo check holds, and the
    # resolver (gazetteer, then the stored geo as the proposal) keeps exact or city.
    from app.services.revue.checks import check_geo
    from app.services.revue.geo import geocode_dossier, in_france

    assert failures(check_geo(dossier)) == []
    for place in geocode_dossier(dossier).places:
        assert place.geo is not None, place.id
        assert place.geo.precision in {"exact", "city"}, place.id
        assert in_france(place.geo.lat, place.geo.lon), place.id
