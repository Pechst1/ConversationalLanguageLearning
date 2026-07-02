"""Static regression tests for visible thread context on destination pages."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MISSIONS_PAGE = ROOT / "web-frontend" / "pages" / "missions.tsx"
FEUILLETON_PAGE = ROOT / "web-frontend" / "pages" / "graphic-novel.tsx"


def read_page(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_missions_renders_visible_real_moment_context() -> None:
    source = read_page(MISSIONS_PAGE)

    assert "function missionFrame" in source
    assert "function missionMessenger" in source
    assert "className=\"scene-frame\"" in source
    assert "className=\"thread-head\"" in source
    assert "className=\"word-ribbon\"" in source
    assert "TranslateButton text={translatePrompt} label=\"Translate frame\"" in source


def test_missions_preserves_query_context_before_url_replacement() -> None:
    source = read_page(MISSIONS_PAGE)

    assert "function querySeed" in source
    assert "atelierSessionId: firstQuery(routerQuery.atelier_session_id)" in source
    assert "conceptIds: queryNumberList(routerQuery.concept_id)" in source
    assert "vocabularyIds: queryNumberList(routerQuery.vocabulary_id)" in source
    assert "erratumIds: queryStringList(routerQuery.erratum_id)" in source
    assert "serialThreadId: firstQuery(routerQuery.serial_thread_id)" in source
    assert "atelier_session_id: nextSeed.atelierSessionId" in source
    assert "preferred_concept_ids: nextSeed.conceptIds.length ? nextSeed.conceptIds : undefined" in source
    assert "preferred_errata_ids: nextSeed.erratumIds.length ? nextSeed.erratumIds : undefined" in source
    assert "preferred_vocabulary_ids: nextSeed.vocabularyIds.length ? nextSeed.vocabularyIds : undefined" in source


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
    assert "const routeQuery = useMemo(" in source
    assert "() => (router.isReady ? mergedRouteQuery(router.query, router.asPath) : {})" in source
    assert "function feuilletonThreadContextFromQuery" in source
    assert "const grammarCount = queryList(query.concept_id).length" in source
    assert "const errataCount = queryList(query.erratum_id).length" in source
    assert "const vocabularyCount = queryList(query.vocabulary_id).length" in source
    assert "typeof query.mission === 'string'" in source
    assert "typeof query.mission_id === 'string'" in source
    assert "const atelierSessionId = typeof query.atelier_session_id === 'string'" in source
    assert "const keys = ['atelier_session_id', 'mission', 'mission_id', 'concept_id', 'erratum_id', 'vocabulary_id']" in source
    assert "target_vocabulary_ids: vocabularyIds.length ? vocabularyIds : undefined" in source
    assert "preferred_concept_ids: conceptIds.length ? conceptIds : undefined" in source
    assert "preferred_errata_ids: errataIds.length ? errataIds : undefined" in source
    assert "setThreadContext(feuilletonThreadContextFromQuery(routeQuery))" in source
