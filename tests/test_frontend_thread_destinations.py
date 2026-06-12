"""Static regression tests for visible thread context on destination pages."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MISSIONS_PAGE = ROOT / "web-frontend" / "pages" / "missions.tsx"
FEUILLETON_PAGE = ROOT / "web-frontend" / "pages" / "graphic-novel.tsx"


def read_page(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_missions_renders_visible_seeded_thread_context() -> None:
    source = read_page(MISSIONS_PAGE)

    assert "function ThreadContextBanner" in source
    assert 'aria-label="Today\'s Thread context"' in source
    assert "TODAY&apos;S THREAD" in source
    assert "Mission seeded from Atelier" in source
    assert 'aria-label="Seeded mission context"' in source
    assert "label: 'Grammar'" in source
    assert "label: 'Vocabulary'" in source
    assert "label: 'Errata'" in source
    assert "label: 'Atelier Session'" in source
    assert ".thread-chip.grammar" in source
    assert ".thread-chip.vocabulary" in source
    assert ".thread-chip.errata" in source
    assert ".thread-chip.session" in source


def test_missions_preserves_query_context_before_url_replacement() -> None:
    source = read_page(MISSIONS_PAGE)

    assert "const atelierSessionId = typeof router.query.atelier_session_id === 'string'" in source
    assert "const conceptIds = queryNumberList(router.query.concept_id)" in source
    assert "const vocabularyIds = queryNumberList(router.query.vocabulary_id)" in source
    assert "const erratumIds = queryStringList(router.query.erratum_id)" in source
    assert "setThreadSeedContext(nextThreadSeed)" in source
    assert "atelier_session_id: atelierSessionId || undefined" in source
    assert "preferred_concept_ids: conceptIds.length ? conceptIds : undefined" in source
    assert "preferred_errata_ids: erratumIds.length ? erratumIds : undefined" in source
    assert "preferred_vocabulary_ids: vocabularyIds.length ? vocabularyIds : undefined" in source


def test_feuilleton_renders_visible_seeded_thread_context() -> None:
    source = read_page(FEUILLETON_PAGE)

    assert "function TodayThreadBanner" in source
    assert 'aria-label="Today\'s Thread context"' in source
    assert "Today&apos;s Thread" in source
    assert "Scene seeded from Atelier" in source
    assert "today-thread-chips" in source
    assert "key: 'grammar', label: 'Grammar'" in source
    assert "key: 'vocabulary', label: 'Vocabulary'" in source
    assert "key: 'errata', label: 'Errata'" in source
    assert "key: 'mission', label: 'Mission'" in source
    assert "key: 'atelier-session', label: 'Atelier Session'" in source
    assert ".today-thread-chip.red" in source
    assert ".today-thread-chip.blue" in source
    assert ".today-thread-chip.yellow" in source
    assert "{!scene && visibleThreadContext && (" in source


def test_feuilleton_uses_query_context_for_scene_creation_and_banner() -> None:
    source = read_page(FEUILLETON_PAGE)

    assert "function queryFromAsPath" in source
    assert "function mergedRouteQuery" in source
    assert "const routeQuery = useMemo(() => mergedRouteQuery(router.query, router.asPath)" in source
    assert "function feuilletonThreadContextFromQuery" in source
    assert "const grammarCount = queryList(query.concept_id).length" in source
    assert "const errataCount = queryList(query.erratum_id).length" in source
    assert "const vocabularyCount = queryList(query.vocabulary_id).length" in source
    assert "const missionId = typeof query.mission_id === 'string'" in source
    assert "const atelierSessionId = typeof query.atelier_session_id === 'string'" in source
    assert "const keys = ['atelier_session_id', 'mission_id', 'concept_id', 'erratum_id', 'vocabulary_id']" in source
    assert "target_vocabulary_ids: vocabularyIds.length ? vocabularyIds : undefined" in source
    assert "preferred_concept_ids: conceptIds.length ? conceptIds : undefined" in source
    assert "preferred_errata_ids: errataIds.length ? errataIds : undefined" in source
    assert "setThreadContext(feuilletonThreadContextFromQuery(routeQuery))" in source
