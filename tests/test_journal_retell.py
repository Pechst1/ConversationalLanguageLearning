"""#622 (root cause #145) — the Journal's retell target is an event of that scene.

Explore walk 10 Nov 2026, fake stack: day 2 Journal, «Gestern · Le Mistral · mit
Gus». The learner wrote «Margaux garde la clé», which is what day 1 established (they
left the key with Margaux), and was scored 0/1 against the opening panel's stage line
«Il pleut. Tu as une valise, une lettre, une clé.». Live, the target was a hook that
belonged to no event of the scene («L'appartement est un souvenir de ta grand-mère»),
or another scene's hook altogether.

This file plays S1 day 1 «Le mauvais accueil» with the choice «Garde-la pour moi.»,
then opens the Journal on day 2 as the learner would.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User
from app.services.journal import JournalService
from tests import test_journey_end_to_end as support
from tests import test_season_one as season_one
from tests.test_journal import _FakeCorrector, journal_table  # noqa: F401 - fixture
from tests.test_living_story_longitudinal import TurnScript
from tests.test_quartier_phase1 import FAMILY, _play_day

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled
season_on = season_one.season_on

STAGE_LINE = "Il pleut. Tu as une valise, une lettre, une clé."
RETELL = "Je suis au Mistral. Gus est là. Margaux garde la clé. Camille a une clé aussi."


def _day_one_then_journal(assembled_client, db_session, clock, provider):
    provider.routes = {FAMILY: "a", "Oui. Ce soir.": "tonight"}
    provider.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La journée se termine.", callback_fr="Vous avez parlé.")
    d = support.Driver(
        assembled_client,
        support.register(assembled_client, f"retell-{uuid.uuid4()}@example.com", cefr="A1.1"),
        db=db_session,
    )
    d.create()
    answers = iter([FAMILY, "Non merci.", "Oui. Ce soir.", "Garde-la pour moi."])
    staged = [row.get("stage") or {} for row in _play_day(d, lambda step: next(answers))]
    assert staged[-1].get("reply_id") == "leave", staged
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    journey = db_session.scalars(
        select(DailyJourney).where(DailyJourney.id == uuid.UUID(d.journey["id"]))
    ).one()
    user = db_session.get(User, journey.user_id)
    service = JournalService(db_session, llm_service=_FakeCorrector(fail=True))
    entry = service.offer(user, now=clock.moment)
    assert entry is not None and entry.journey_id == journey.id
    return service, user, entry


def test_day2_target(
    assembled_client, db_session, journey_enabled, clock, season_on
):
    service, user, entry = _day_one_then_journal(assembled_client, db_session, clock, season_on)
    kept = [fact["text_fr"] for fact in entry.scene_facts]
    assert STAGE_LINE not in kept and not any("pleut" in line for line in kept), (
        f"the retell target is the first panel's stage line, not an event of the scene: {kept}"
    )
    assert not any("suivre" in line.lower() for line in kept), kept
    assert any("caisse" in line or "Garde-la" in line for line in kept), (
        f"no kept fact comes from what was said in the scene (the key left with Margaux): {kept}"
    )

    written = service.write(user, entry, text=RETELL)
    recall = written.content_recall
    assert recall["status"] == "scored", recall
    assert recall["score"] == 1.0, (
        f"a retell that names «Margaux garde la clé» scored {recall['score']}: {recall}"
    )
    assert "Il manque quelque chose" not in (written.reaction_fr or ""), written.reaction_fr
