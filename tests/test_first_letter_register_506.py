"""#506 / #147: the first Courrier letter speaks in the register the scene uses.

Margaux says «Tu vas monter ?» in the scene; her first letter said «Vous avez oublié
votre écharpe» under a card titled «Ton écharpe au Mistral». Cause: the register was
read from the Courrier's own thread, which does not exist yet on a first letter, and the
authored title carried one register while the body carried the other. The cast's own
register answers with or without a thread; the thread can only confirm it.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import settings
from app.db.models.user import User

TU_MARKERS = ("tu ", "ton ", "ta ", "tes ", "toi", "salut")
VOUS_MARKERS = ("vous", "votre", "vos ", "bonsoir")


def _learner(db_session):  # noqa: ANN001
    user = User(
        id=uuid4(),
        email=f"first-letter-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _margaux_letter(db_session):  # noqa: ANN001
    from app.services.missions import MissionScheduler

    story_letter, authored = MissionScheduler(db_session)._first_letter(_learner(db_session), story=False)
    assert story_letter is None
    assert authored["character_id"] == "margaux_barman"
    return authored


def _other_register(text: str, register: str) -> list[str]:
    """The markers of the *other* register found in ``text``."""

    low = f" {text.lower()} "
    wrong = VOUS_MARKERS if register == "tu" else TU_MARKERS
    return [marker for marker in wrong if marker in low]


def test_season_learner_first_letter_is_tu_506(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    letter = _margaux_letter(db_session)
    opening = letter["opening_message"]
    assert "Tu as oublié ton écharpe" in opening, f"Margaux says tu in the scene; her first letter reads: {opening}"
    assert opening.startswith("Salut ! C'est Margaux")


@pytest.mark.parametrize("season,register", [("s1", "tu"), ("", "vous")])
def test_first_letter_card_uses_one_register_506(db_session, monkeypatch, season, register) -> None:
    """The card's title, brief and letter are one register (4 Nov: «Ton écharpe» over «Vous avez oublié»)."""

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", season)
    letter = _margaux_letter(db_session)
    for field in ("title", "opening_message"):
        stray = _other_register(str(letter[field]), register)
        assert not stray, f"{field} «{letter[field]}» mixes registers ({register} expected, found {stray})"
    assert letter["register"].startswith(register)


def test_no_thread_register_506(monkeypatch) -> None:
    from app.services import story_correspondence as courrier

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    found = courrier.learner_register(None, "margaux_barman")
    assert found == "tu", f"Margaux opens on tu in the season, the Courrier read {found} with no thread"
    assert courrier.learner_register(None, "landlord_marchand") == "vous"
    assert courrier.learner_register(None, None) == "vous"
    # Letter generation: the last resort with nothing known is «vous».
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "")
    assert courrier.learner_register(None, "margaux_barman") == "vous"


def _margaux_mission(register: str = "tu"):
    return SimpleNamespace(
        user_id=uuid4(),
        correspondent_id=None,
        prompt_payload={
            "serial_character_id": "margaux_barman",
            "messenger": {"contact_name": "Margaux", "target_register": register},
        },
    )


def test_live_register_without_thread_follows_the_season_506(monkeypatch) -> None:
    from app.services import missions
    from app.services import story_correspondence as courrier

    monkeypatch.setattr(courrier, "active_thread", lambda db, user: None)
    user = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    found = missions.live_register(object(), user, _margaux_mission())
    assert found == "tu", f"the season opens Margaux on tu; a reply with no thread read {found}"


def test_live_register_without_thread_or_season_lets_the_letter_decide_506(monkeypatch) -> None:
    """Reviewer of #516: with no season and no thread the cast knows nothing, so the answer is
    None (the letter's own «tu»), never the «vous» default that holds a «tu» reply to formal."""

    from app.services import missions
    from app.services import story_correspondence as courrier

    monkeypatch.setattr(courrier, "active_thread", lambda db, user: None)
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "")
    user = SimpleNamespace(id=uuid4())
    found = missions.live_register(object(), user, _margaux_mission())
    assert found is None, f"nothing known about Margaux: the letter decides, but live_register said {found}"


def test_authored_titles_name_no_register_506() -> None:
    """An authored letter has a «vous» and a «tu» opening but one title: it may name neither."""

    from app.services.missions import FIRST_LETTERS

    for band, letter in FIRST_LETTERS.items():
        if "opening_message_tu" not in letter:
            continue
        title = f" {letter['title'].lower()} "
        stray = [marker for marker in (*TU_MARKERS, *VOUS_MARKERS) if marker in title]
        assert not stray, f"band {band}: the title «{letter['title']}» is shown with both openings but says {stray}"
