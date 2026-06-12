"""Static regressions for Atelier word-bank chip entry."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"


def read_atelier() -> str:
    return ATELIER_PAGE.read_text(encoding="utf-8")


def test_word_bank_mode_uses_clickable_sentence_tokens_and_answer_field() -> None:
    source = read_atelier()

    assert "{ id: 'word_bank', label: 'Word-bank', short: 'B' }" in source
    assert "mode === 'word_bank'" in source
    assert "sourceTokens.map((token: string, tokenIndex: number) => {" in source
    assert "onClick={() => updateAnswer(item.id, [...wordBankTokens, token])}" in source
    assert "joinWordBankTokens(answers[item.id])" in source
    assert "placeholder=\"Built sentence\"" in source
    assert "onChange={(event) => updateAnswer(item.id, event.target.value)}" in source


def test_word_bank_tokens_can_be_removed_after_tapping() -> None:
    source = read_atelier()

    assert "wordBankTokenIsUsed(wordBankTokens, sourceTokens, token, tokenIndex)" in source
    assert "className={used ? 'used' : ''}" in source
    assert "wordBankTokens.filter((_, index) => index !== selectedIndex)" in source


def test_word_bank_feedback_uses_accent_insensitive_comparison() -> None:
    source = read_atelier()

    assert "function normalizeClient" in source
    assert ".normalize('NFD')" in source
    assert ".replace(/[\\u0300-\\u036f]/g, '')" in source
    assert "normalizeClient(learnerText) === normalizeClient(targetText)" in source


def test_atelier_page_does_not_render_old_hardcoded_exercise_fallbacks() -> None:
    source = read_atelier()

    assert "Si je finis tôt, je t’appellerai." not in source
    assert "Le Tour de France 2026 partira de Barcelone le 4 juillet." not in source
    assert "Use the x-ray and the rule panel as the proofing reference while you answer." not in source
    assert "Session content unavailable." in source
    assert "Writing prompt unavailable." in source


def test_atelier_word_counts_do_not_mask_missing_generated_limits() -> None:
    source = read_atelier()

    assert "function wordRangeLabel" in source
    assert "{item.min_words || 5}-{item.max_words || 28}" not in source
    assert "{produce.min_words || 70}-{produce.max_words || 140}" not in source


def test_atelier_ai_review_is_polled_without_blocking_next_step() -> None:
    source = read_atelier()
    api = (ROOT / "web-frontend" / "services" / "api.ts").read_text(encoding="utf-8")

    assert "getAtelierAttempt" in api
    assert "requestAtelierAttemptAiReview" in api
    assert "scheduleAiReviewPolling(result.attempt_id, key)" in source
    assert "apiService.getAtelierAttempt(attemptId)" in source
    assert "}, 2000)" in source
    assert "AI reviewing" in source
    assert "AI correction ready" in source
    assert "AI correction" in source
    assert "AI unavailable" in source
    assert "disabled={submitting || !submitted || nextDisabled}" in source
