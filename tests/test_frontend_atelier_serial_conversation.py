from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_atelier_conversation_prints_character_byline_and_world_reply():
    page = (ROOT / "web-frontend" / "pages" / "atelier.tsx").read_text(encoding="utf-8")
    assert 'className="ep-character-byline"' in page
    assert "Conversation avec ${character.name}" in page
    assert "worldReply.character?.name || character.name" in page
    assert 'className="ep-world-reply"' in page

