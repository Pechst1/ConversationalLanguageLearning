"""WP-115b — the recall ladder: a card's format follows its memory, not a counter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import journey_planner as planner
from app.services.recall_ladder import blank_word, card_ladder, rung


@pytest.mark.parametrize(
    ("stability", "level", "expected"),
    [
        (1.0, "A1", "recognition"),
        (6.0, "A1", "production"),
        (6.0, "B1", "production"),
        (2.0, "B1", "production"),
        (2.0, "A2", "recognition"),
        (12.0, "A2", "audio"),
        (40.0, "A2", "cloze"),
    ],
)
def test_the_rung_follows_stability_and_the_band(stability, level, expected):
    assert rung(stability=stability, reps=3, lapses=0, level=level, has_example=True) == expected


def test_a_word_never_reviewed_is_recognised_first():
    assert rung(stability=50.0, reps=0, lapses=0, level="B1", has_example=True) == "recognition"


def test_a_cloze_needs_a_sentence_to_blank():
    assert rung(stability=40.0, reps=5, lapses=0, level="A2", has_example=False) == "audio"


def test_blanking_keeps_the_article_and_never_invents_a_blank():
    assert blank_word("Tu as vu la serrure ?", "la serrure") == "Tu as vu la _____ ?"
    assert blank_word("Les serrures du quartier.", "la serrure") is None


def _progress(**fields):
    base = {"reps": 1, "lapses": 0, "stability": 2.0, "context": None}
    return SimpleNamespace(**{**base, **fields})


WORD = SimpleNamespace(word="la serrure", example_sentence="Il change la serrure de la porte.")


def test_a_kept_word_first_comes_back_in_its_own_line():
    kept = {"sentence_fr": "Tu as vu la serrure ?", "speaker_id": "margaux_barman", "line_key": "p3:l0"}
    first = card_ladder(_progress(reps=1, context=kept), WORD, level="A2")
    assert first["ladder"] == "scene"
    assert first["scene_cue"] == {"sentence_fr": "Tu as vu la _____ ?", "speaker_id": "margaux_barman", "line_key": "p3:l0"}
    later = card_ladder(_progress(reps=3, stability=40.0, context=kept), WORD, level="A2")
    assert later["ladder"] == "cloze" and later["scene_cue"] is None, "from the third review: new contexts"


def test_a_kept_conjugated_verb_comes_back_in_its_own_line():
    # WP-138: «vends» was tapped, the catalogue row is «vendre»; the line holds the former.
    verb = SimpleNamespace(word="vendre", example_sentence="")
    kept = {"sentence_fr": "Je vends mon vélo demain.", "surface": "vends"}
    card = card_ladder(_progress(reps=1, context=kept), verb, level="A1")
    assert card["ladder"] == "scene"
    assert card["scene_cue"]["sentence_fr"] == "Je _____ mon vélo demain."
    older = {"sentence_fr": "Je vends mon vélo demain."}  # kept before the form was stored
    assert card_ladder(_progress(reps=1, context=older), verb, level="A1")["ladder"] != "scene"


def test_a_leech_changes_method_not_frequency():
    rescued = card_ladder(_progress(reps=9, lapses=5), WORD, level="A2")
    assert rescued["leech"] is True and rescued["ladder"] == "rescue"
    assert rescued["rescue_cue"]["first_letter"] == "s" and rescued["rescue_cue"]["length"] == 7
    assert rescued["rescue_cue"]["sentence_fr"] == "Il change la _____ de la porte."


def test_the_days_practice_recognises_a_fragile_word_and_produces_a_held_one():
    formats = {
        "shape": planner.DayShape.STANDARD, "dice": None, "identity": "v:1",
        "used_today": {}, "used_by_target": set(), "learner_band": "A2",
    }
    fragile = planner._slot_formats("post", rung="recognition", **formats)
    held = planner._slot_formats("post", rung="production", **formats)
    assert fragile[0] in {"choice", "classify", "listen_tap"}
    assert held[0] in {"short_answer", "transform"}


def test_a_word_the_story_taught_reaches_the_drill(client, db_session):
    """Walk finding 2026-09-30: the drill took only Anki-flagged catalogue rows with a
    direction, so a word met in the story (a scene_lexicon row with neither) never came
    back in the drill. The mission phrase bank stays out."""

    from datetime import UTC, datetime, timedelta

    from app.db.models.progress import UserVocabularyProgress
    from app.db.models.vocabulary import VocabularyWord
    from tests.test_wp115a_vocabulary_memory import _login

    headers, user = _login(client, db_session)
    past = datetime.now(UTC) - timedelta(days=2)
    story = VocabularyWord(language="fr", word="appartement", normalized_word="appartement",
                           english_translation="flat", topic_tags=["scene_lexicon"], is_anki_card=False)
    phrase = VocabularyWord(language="fr", word="bonne affaire", normalized_word="bonne affaire",
                            english_translation="a good deal", topic_tags=["mission"], is_anki_card=False)
    db_session.add_all([story, phrase])
    db_session.flush()
    for word in (story, phrase):
        db_session.add(UserVocabularyProgress(
            user_id=user.id, word_id=word.id, scheduler="fsrs", state="reviewing", reps=1,
            stability=2.0, due_at=past, next_review_date=past, due_date=past.date(), last_review_date=past,
        ))
    db_session.commit()
    response = client.get("/api/v1/vocabulary/due-context?due_limit=10", headers=headers)
    assert response.status_code == 200, response.text
    deck = response.json()
    words = [item["word"] for item in deck["due_words"]]
    assert "appartement" in words, words
    assert "bonne affaire" not in words, "the mission phrase bank stays out of the drill"
