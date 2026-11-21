"""#777: «New letter» repeated a played situation, and its «Use:» words did not fit it.

Live walk 14 Nov 2026 (A1.1, day 33): «New letter» opened «Boutique Anaïs · Pas la bonne
taille», the situation the learner had already played on 4 Nov, with «Use: restaurant,
marche, quarante» on a clothes-size letter.

Two mechanisms, one cause (#146: the words were picked apart from the situation, and the
situation apart from what the learner had already played):

* a situation was kept out only while it sat in the last eight letters, or, for a canned
  letter, the reprint window. A letter the model wrote on the same situation (same shop,
  same size problem, same title) came back as soon as eight other letters had passed;
* the «Use:» words came from the learner's coverage category (food) and the situation from
  wherever the catalogue fell back to (a clothes shop); nothing tied the two.

No provider is called: the model's letter is a stub that keeps the situation it is given,
as the model did on 14 Nov.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

import app.services.missions as missions_module
from app.config import settings
from app.db.models.mission import RealWorldMission
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.missions import (
    LETTER_FIT_KEY,
    REAL_WORLD_MISSION_DOMAINS,
    MissionGenerator,
    MissionScheduler,
)

CANNED = {item["domain"]: item for item in REAL_WORLD_MISSION_DOMAINS}


@pytest.fixture(autouse=True)
def model_writes_the_given_situation(monkeypatch):
    """The model is on, and keeps the domain, contact and title it is handed (14 Nov)."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "")
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)

    def fake_scenario(self, *, variety, **_kwargs):
        return {
            "title": variety.get("title"),
            "brief": variety.get("brief"),
            "messenger": {
                "contact_name": variety.get("contact_name"),
                "contact_role": variety.get("contact_role"),
                "opening_message": variety.get("opening_message"),
                "scene_anchor": variety.get("scene_anchor"),
            },
            "variety": {"domain": variety.get("domain"), "channel": variety.get("channel")},
        }

    monkeypatch.setattr(MissionGenerator, "_llm_scenario", fake_scenario)


def _user(db_session, level: str = "A1") -> User:
    user = User(
        id=uuid4(),
        email=f"issue777-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level=level,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _played(db_session, user: User, domain: str, *, days_ago: float, source: str = "generated") -> RealWorldMission:
    """A letter the learner has played and answered, served ``days_ago``."""

    item = CANNED[domain]
    served = datetime.now(UTC) - timedelta(days=days_ago)
    row = RealWorldMission(
        user_id=user.id,
        status="completed",
        cadence="ad_hoc",
        mission_type="message",
        title=item["title"],
        brief=item["brief"],
        completed_at=served,
        created_at=served,
        prompt_payload={
            "variety": {
                "domain": domain,
                "contact": item["contact_name"],
                "channel": item["channel"],
                "tone": item["tone"],
            },
            "messenger": {"contact_name": item["contact_name"]},
            LETTER_FIT_KEY: {
                "source": source,
                "request_key": domain,
                "served_at": served.isoformat(),
                "level": item["level"],
            },
        },
    )
    db_session.add(row)
    db_session.commit()
    return row


def _new_letter(db_session, user: User) -> RealWorldMission:
    """What the Courrier's «New letter» press asks for (POST /missions, no seed)."""

    return asyncio.run(
        MissionScheduler(db_session).create(user=user, mission_type="message", cadence="ad_hoc", use_news=False)
    )


def _domain(mission: RealWorldMission) -> str:
    return str((mission.prompt_payload or {}).get("variety", {}).get("domain"))


#: Eight letters after 4 Nov, none of them the shop: the 4 Nov letter has left the
#: last-eight window the catalogue used to read.
LATER = ("housing", "neighbours", "deliveries_admin", "transport", "services", "bureaucracy", "food_dining", "social_plans")


def test_shop_not_repeated(db_session, monkeypatch):
    """«New letter» on 14 Nov does not reprint the shop letter the learner played on 4 Nov."""

    user = _user(db_session)
    _played(db_session, user, "shopping", days_ago=10)  # 4 Nov: «Pas la bonne taille»
    for offset, domain in enumerate(LATER):
        _played(db_session, user, domain, days_ago=9 - offset)
    # The learner's coverage points at clothes, as the shop letter does.
    monkeypatch.setattr(MissionScheduler, "_active_coverage_category", lambda self, *, user: "clothing")

    letter = _new_letter(db_session, user)

    assert (_domain(letter), letter.title) != ("shopping", "Pas la bonne taille"), (
        "«New letter» reprinted «Boutique Anaïs · Pas la bonne taille», played on 4 Nov"
    )
    assert _domain(letter) not in {"shopping", *LATER}


def test_oldest_comes_back(db_session, monkeypatch):
    """When every situation in reach was played this month, the one played longest ago
    comes back, never a recent one."""

    user = _user(db_session)
    beginner = [item["domain"] for item in REAL_WORLD_MISSION_DOMAINS if item["level"] in {"A1", "A2"}]
    # Every situation at the learner's reach, played this month; «transport» longest ago.
    order = ["transport", *[domain for domain in beginner if domain != "transport"]]
    for offset, domain in enumerate(order):
        _played(db_session, user, domain, days_ago=20 - offset)
    monkeypatch.setattr(MissionScheduler, "_active_coverage_category", lambda self, *, user: "clothing")

    letter = _new_letter(db_session, user)

    assert _domain(letter) == "transport"


def _word(db_session, word: str, rank: int, tags: list[str]) -> VocabularyWord:
    row = VocabularyWord(
        language="fr",
        word=word,
        normalized_word=word,
        frequency_rank=rank,
        english_translation=word,
        direction="fr_to_de",
        deck_name="French 5000",
        topic_tags=tags,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _use_words(payload: dict) -> list[str]:
    return [str(item.get("word")) for item in payload["prompt_payload"]["target_vocabulary"]]


def test_shop_words_not_food(db_session):
    """The exact 14 Nov letter: coverage on food, the situation fell to the clothes shop,
    and «restaurant», «marche» were printed under «Use:»."""

    user = _user(db_session)
    _word(db_session, "restaurant", 300, ["food_drink"])
    _word(db_session, "marche", 310, ["food_drink"])
    _word(db_session, "taille", 400, ["clothing"])
    _word(db_session, "robe", 410, ["clothing"])
    # Every other A1/A2 situation was played lately: the catalogue falls to the shop.
    recent = [
        {"domain": item["domain"], "contact": item["contact_name"], "channel": item["channel"]}
        for item in REAL_WORLD_MISSION_DOMAINS
        if item["level"] in {"A1", "A2"} and item["domain"] != "shopping"
    ]

    payload = asyncio.run(
        MissionGenerator(db_session).build_payload(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            active_category="food_drink",
            recent_variety=recent,
            fuel_source="theme",
        )
    )

    assert payload["prompt_payload"]["variety"]["domain"] == "shopping"
    words = _use_words(payload)
    assert not {"restaurant", "marche"} & set(words), f"a clothes-size letter says «Use: {', '.join(words)}»"
    assert "taille" in words
    focus = [str(item.get("word")) for item in payload["prompt_payload"]["messenger"].get("vocabulary_focus") or []]
    assert not {"restaurant", "marche"} & set(focus)


def test_seeded_words_lead(db_session):
    """Words the learner asked to use (a seeded «New letter») choose the situation; they are
    not printed on a letter from another one."""

    user = _user(db_session)
    taille = _word(db_session, "taille", 400, ["clothing"])
    robe = _word(db_session, "robe", 410, ["clothing"])

    payload = asyncio.run(
        MissionGenerator(db_session).build_payload(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            active_category="food_drink",
            preferred_vocabulary_ids=[taille.id, robe.id],
            fuel_source="vocab",
        )
    )

    domain = payload["prompt_payload"]["variety"]["domain"]
    assert "clothing" in CANNED[domain]["categories"], f"«Use: taille, robe» printed on the «{domain}» letter"
    assert _use_words(payload)[:2] == ["taille", "robe"]
