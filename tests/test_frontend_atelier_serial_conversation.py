from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_atelier_conversation_prints_character_byline_and_world_reply():
    page = (ROOT / "web-frontend" / "pages" / "atelier.tsx").read_text(encoding="utf-8")
    assert 'className="ep-character-byline"' in page
    # WP-82: the byline follows the chrome language (epreuve-copy.ts).
    assert "fill(t.conversation_with, { name: character.name })" in page
    copy = (ROOT / "web-frontend" / "components" / "epreuve" / "epreuve-copy.ts").read_text(encoding="utf-8")
    assert "conversation_with: 'Conversation avec {name}'" in copy
    assert "worldReply.character?.name || character.name" in page
    assert 'className="ep-world-reply"' in page

