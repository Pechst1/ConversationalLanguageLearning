"""Static regressions for Atelier word-bank chip entry."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATELIER_PAGE = ROOT / "web-frontend" / "pages" / "atelier.tsx"


def read_atelier() -> str:
    return ATELIER_PAGE.read_text(encoding="utf-8")


def test_word_bank_mode_uses_clickable_sentence_tokens_and_answer_field() -> None:
    source = read_atelier()

    # The word-bank chips are now the L'Épreuve "movable type" set line
    # (EpSetLine/EpSlug) instead of a plain button grid + joined-text input.
    assert "{ id: 'word_bank', label: 'Banque de mots', short: 'C' }" in source
    assert "mode === 'word_bank'" in source
    assert "sourceTokens.map((token: string, tokenIndex: number) => {" in source
    assert "onClick={() => updateAnswer(item.id, [...wordBankTokens, token])}" in source
    assert "<EpSetLine empty={wordBankTokens.length === 0}>" in source
    assert "wordBankTokens.map((token, selectedIndex) => (" in source


def test_word_bank_tokens_can_be_removed_after_tapping() -> None:
    source = read_atelier()

    # "used" state is now the EpSlug `spent` prop, not a plain className toggle.
    assert "wordBankTokenIsUsed(wordBankTokens, sourceTokens, token, tokenIndex)" in source
    assert "spent={used}" in source
    assert "wordBankTokens.filter((_, tokenIndex) => tokenIndex !== selectedIndex)" in source


def test_word_bank_feedback_trusts_server_errata_not_client_string_compare() -> None:
    source = read_atelier()

    assert "function normalizeClient" in source
    assert ".normalize('NFD')" in source
    assert ".replace(/[\\u0300-\\u036f]/g, '')" in source
    # Correctness comes from the server's per-item errata, not a client-side
    # normalizeClient(learner) === normalizeClient(target) compare: a word-bank
    # answer built from tokens like "J'" + "ai" joins with a plain space ("J' ai"),
    # and normalizeClient doesn't collapse that the way the backend's
    # French-elision-aware normalizer does, so a correct answer with an elidable
    # apostrophe (j', c', l', ...) would otherwise be flagged wrong.
    assert "const assessment = seanceAssessment(correction);" in source
    assert "const correct = matchingErrata.length === 0 &&" in source
    assert "assessment === 'correct'" in source
    assert "error.item_id !== item.id" in source


def test_atelier_page_does_not_render_old_hardcoded_exercise_fallbacks() -> None:
    source = read_atelier()

    assert "Si je finis tôt, je t’appellerai." not in source
    assert "Le Tour de France 2026 partira de Barcelone le 4 juillet." not in source
    assert "Use the x-ray and the rule panel as the proofing reference while you answer." not in source
    # The unavailable notice lives on the load-error shell since the 2026-08-31
    # dead-code excision removed the unused AtelierLoadNotice duplicate.
    # WP-82: the notice and the missing-task line follow the language rule;
    # their words live in the copy modules, never inline French.
    assert "atelierErrorText(loadError" in source
    errors = (ROOT / "web-frontend" / "lib" / "atelier-errors.ts").read_text(encoding="utf-8")
    assert "L’Atelier ne répond pas." in errors and "The Atelier is not answering." in errors
    copy = (ROOT / "web-frontend" / "components" / "epreuve" / "epreuve-copy.ts").read_text(encoding="utf-8")
    assert "{promptText || t.produce_missing}" in source
    assert "produce_missing: 'La consigne est indisponible.'" in copy


def test_atelier_word_counts_do_not_mask_missing_generated_limits() -> None:
    source = read_atelier()

    assert "wordRangeText(t, wordCount(answer), item.min_words, item.max_words)" in source
    copy = (ROOT / "web-frontend" / "components" / "epreuve" / "epreuve-copy.ts").read_text(encoding="utf-8")
    assert "export function wordRangeText" in copy
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
    # WP-S1: the second look is quiet; a note appears only when it changed the verdict.
    assert "secondCheckChange(correction)" in source
    assert "t.second_check_better" in source and "t.second_check_worse" in source
    # WP-82/83: the second look is announced inline, in the chrome language.
    assert "say(pageCopy.say_review_started)" in source
    assert "say(pageCopy.say_review_unavailable, 'alert')" in source
    copy = (ROOT / "web-frontend" / "components" / "epreuve" / "epreuve-copy.ts").read_text(encoding="utf-8")
    assert "say_review_started: 'Relecture automatique lancée.'" in copy
    assert "say_review_unavailable: 'La relecture automatique est indisponible.'" in copy
    assert "disabled={submitting || nextDisabled}" in source
