"""P12 round 3 · Le Quartier as the second integration walk met it (17 Nov, walk2-integration-a1).

1. The end card and the carnet said «Tu as dit que tu viens pour vendre» after «Je suis Jonas.
   Je venir pour la apartement.»: the engine routed that free answer to route b of «a.turn1», and
   the quarter printed route b's authored line as the learner's words. The answer's stage now says
   whether it was one of the turn's cards, word for word (``chosen``); only then is a route
   something the learner said.
2. «Im Quartier spielen» was offered on day 1 only. Day 3 («Chez le notaire») and day 5 («Ton
   appartement») were written at night before Start, in places the quarter has built, and Home
   still said nothing of their place: the headline's planned stage was a tentpole's only.
"""

from __future__ import annotations

import uuid

from app.config import settings
from app.db.models.pilot_event import PilotEvent
from tests import test_journey_end_to_end as support
from tests.test_season_one import _play, season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


def _register(client, db):
    return support.Driver(client, support.register(client, f"r3q-{uuid.uuid4()}@example.com", cefr="A1.1"), db=db)


def test_a_card_answer_is_chosen_a_free_answer_is_not(assembled_client, db_session, journey_enabled, clock, season_on):  # noqa: F811
    provider = season_on
    provider.routes = {"Je suis Jonas. Je venir pour la apartement.": "b"}
    d = _register(assembled_client, db_session)
    d.create()
    cards: list[str] = []

    def answer(step):
        choices = [c.get("label_fr") for c in (step.get("prompt") or {}).get("choices") or [] if c.get("label_fr")]
        if choices:
            cards.append(choices[0])
            return choices[0]
        return "Je suis Jonas. Je venir pour la apartement."

    results = d.play(answer=answer)
    staged = [r["stage"] for r in results if r.get("stage")]
    assert staged, results
    free = [s for s in staged if s["turn_id"] == "a.turn1"]
    assert free and all(s["chosen"] is False for s in free), free
    assert cards, "day 1 has a «Le choix»"
    chosen = [s for s in staged if s.get("chosen")]
    assert chosen and all(s["reply_id"] for s in chosen), staged


def test_a_gap_day_written_at_night_says_where_it_plays_before_start(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    from app.services import journey_latency

    provider = season_on
    d = _register(assembled_client, db_session)
    _play(d, provider, clock, "Odile, c'est ma grand-mère.")
    _play(d, provider, clock, "Oui, je reste une semaine.")
    # day 3, a gap day, before the night has written it: nothing to say of its place
    assert d.today()["headline"]["stage"] is None

    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True)
    from app.db.models.user import User

    user = db_session.query(User).filter(User.email.like("r3q-%")).order_by(User.created_at.desc()).first()
    key = journey_latency.scene_cache_key(db_session, user)
    assert key, "the engine keys a scene for the gap day"
    # what the walk's night run left for day 3 (pilot_events, 20 Nov): a scene at the notary's
    db_session.add(
        PilotEvent(
            user_id=user.id,
            event_type=journey_latency.PREFETCH_EVENT,
            entity_type="journey_scene",
            entity_id=key,
            payload={"cache_key": key, "brief": {"location_id": "notaire", "title_fr": "Chez le notaire, sous la pluie"}},
            cost_usd=0.0,
        )
    )
    db_session.commit()
    stage = d.today()["headline"]["stage"]
    assert stage is not None, "the night wrote the page: Home knows where it plays"
    assert stage["key"].startswith("jour.") and stage["location_id"] == "notaire" and stage["locations"] == [], stage
    # nothing was consumed by reading it
    assert journey_latency.waiting_scene_place(db_session, user) == "notaire"
