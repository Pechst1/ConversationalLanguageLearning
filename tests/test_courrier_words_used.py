"""#928 (root cause #143): the Courrier ribbon's «words used» is the server's record.

Walk 19 Nov: the letter asked for «vendre», «clé», «appartement»; the learner wrote
«Je n ai pas vendu l appartement. J ai garde la cle…» and the ribbon said 1/3. The
page recomputed «used» on the client with a lower-case substring test of the raw text
against the lemma («vendre» is not in «vendu», «clé» is not in «cle»), while the
corrector had already recorded, lemma- and accent-aware (`app/services/word_match.py`),
which target words the reply used (`vocabulary_events` on the turn's correction).

The mission now carries that record once, as `used_target_word_ids`, and the page
reads it (`web-frontend/components/courrier/courrier-words-used.test.js`).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.db.models.vocabulary import VocabularyWord
from app.services.news_service import NewsService
from tests.test_missions import _fake_france_context, _token

WALK_REPLY = "Je n ai pas vendu l appartement. J ai garde la cle dans ma poche."


def _word(word: str, rank: int, translation: str) -> VocabularyWord:
    return VocabularyWord(
        language="fr", word=word, normalized_word=word, frequency_rank=rank,
        english_translation=translation, direction="fr_to_en", deck_name="French 5000", is_anki_card=True,
    )


def _letter_with_targets(client: TestClient, db_session, monkeypatch) -> tuple[dict[str, str], str, dict[str, int]]:
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    words = [_word("vendre", 81, "to sell"), _word("clé", 82, "key"), _word("appartement", 83, "flat")]
    db_session.add_all(words)
    db_session.commit()
    headers = {"Authorization": f"Bearer {_token(client)}"}
    created = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "preferred_vocabulary_ids": [word.id for word in words],
            "use_news": False,
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    mission = created.json()["mission"]
    ribbon = {item["word"]: item["word_id"] for item in mission["target_vocabulary"]}
    assert set(ribbon) == {"vendre", "clé", "appartement"}, ribbon
    return headers, mission["id"], ribbon


def test_the_walk_reply_uses_all_three_target_words_in_the_servers_record(client, db_session, monkeypatch):
    headers, mission_id, ribbon = _letter_with_targets(client, db_session, monkeypatch)

    sent = client.post(
        f"/api/v1/missions/{mission_id}/turns", json={"text": WALK_REPLY, "mode": "chat"}, headers=headers
    )
    assert sent.status_code == 200, sent.text

    for mission in (sent.json()["mission"], client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()):
        mission = mission.get("mission", mission)
        used = mission.get("used_target_word_ids")
        assert used is not None and sorted(used) == sorted(ribbon.values()), (
            f"the letter does not say which target words «{WALK_REPLY}» used "
            f"(vendu is vendre, cle is clé): got {used}, expected {sorted(ribbon.values())}"
        )


def test_a_target_word_the_reply_did_not_use_is_not_in_the_record(client, db_session, monkeypatch):
    headers, mission_id, ribbon = _letter_with_targets(client, db_session, monkeypatch)

    # «vendredi» starts like «vendre» and «clef» is not written: only appartement is used.
    sent = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Je visite l'appartement vendredi soir.", "mode": "chat"},
        headers=headers,
    )
    assert sent.status_code == 200, sent.text

    assert sent.json()["mission"].get("used_target_word_ids") == [ribbon["appartement"]]
