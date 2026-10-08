"""EXERCISE-QA 2026-10-03 — the permanent quality gate: a learner walk.

The owner played day 1 as an A1 German learner and met incoherent items while
every suite was green: the suites tested packages, and nobody read a day the way
a learner reads it. This file plays days, in production configuration (season 1
with its level overlays, the practice day, the v2 grammar catalogue, the authored
first day), for five personas and three answer qualities, and runs the automated
checks of :mod:`tests.walk_checks` over every transcript:

* no English in a German learner's day (and no German in an English one's);
* every translation shown next to French is about that French;
* no duplicate or near-duplicate item in a day;
* no item above the learner's band;
* every miss shows what was expected;
* no empty string, no ``{placeholder}``, no machine key;
* no reference to a story event the learner has not seen yet.

Fast tier (default): day 1 of every persona × quality. Long tier (``-m walk``):
one life per persona, days 1, 2, 7, 14 and 30 recorded. ``WALK_TRANSCRIPTS=dir``
writes the transcripts as JSON for a human read.
"""
from __future__ import annotations

import os

import pytest

from app.config import settings
from app.services.core_lexicon import CORE_DECK, ensure_core_lexicon
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from tests import learner_walk as walk
from tests import test_journey_end_to_end as support
from tests import walk_checks
from tests.test_season_one import season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


@pytest.fixture
def production_day(monkeypatch, db_session, season_on):  # noqa: F811
    """What a new learner meets in production (render.yaml + config defaults)."""

    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_FIRST_DAY_AUTHORED_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    # Production syncs the core word list at deploy (docker/entrypoint.sh); the
    # drill introduces it in learning order. Without it the walk measures an
    # empty word supply.
    ensure_core_lexicon(db_session)
    db_session.commit()
    season_on.critic_refusals_left = 0
    season_on.spoil_once = False
    plain_draft = season_on._season_draft
    monkeypatch.setattr(
        season_on,
        "_season_draft",
        lambda context: walk.fit_level(walk.weave_grammar(plain_draft(context), context), context),
    )
    yield season_on
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v1")
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
    _drop_core_lexicon(db_session)


def _drop_core_lexicon(db) -> None:
    """The shared test database goes back to the empty word list other suites expect."""

    from sqlalchemy import delete, select

    from app.db.models.progress import UserVocabularyProgress
    from app.db.models.vocabulary import VocabularyWord

    db.rollback()
    core = select(VocabularyWord.id).where(VocabularyWord.deck_name == CORE_DECK)
    db.execute(delete(UserVocabularyProgress).where(UserVocabularyProgress.word_id.in_(core)))
    db.execute(delete(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK))
    db.commit()


def _assert_clean(transcripts: list[dict], db_session) -> None:
    problems = walk_checks.run_all(transcripts, db=db_session)
    assert not problems, "\n".join(problems[:60]) + (f"\n… {len(problems) - 60} more" if len(problems) > 60 else "")


@pytest.mark.parametrize("quality", walk.QUALITIES)
@pytest.mark.parametrize("persona", walk.PERSONAS, ids=lambda p: p.key)
def test_day_one_reads_clean_for_every_persona(
    persona, quality, assembled_client, db_session, journey_enabled, clock, production_day
):
    headers, _email = walk.register(assembled_client, persona)
    transcript = walk.play_day(
        assembled_client, db_session, headers, persona=persona, quality=quality, day=1, provider=production_day
    )
    walk.write_transcripts([transcript], f"day1-{persona.key}-{quality}")
    assert transcript.get("error") is None, transcript.get("error")
    assert transcript["finish_status"] == 200
    _assert_clean([transcript], db_session)


@pytest.mark.walk
@pytest.mark.parametrize("persona", walk.PERSONAS, ids=lambda p: p.key)
def test_a_month_reads_clean(request, persona, assembled_client, db_session, journey_enabled, clock, production_day):
    """One life per persona: thirty days, the answer quality rotating day by day."""

    selected = "walk" in str(request.config.getoption("-m") or "") or os.environ.get("WALK") == "1"
    if not selected:
        pytest.skip("the long walk runs with `-m walk` (or WALK=1)")

    headers, _email = walk.register(assembled_client, persona)
    recorded: list[dict] = []
    met: set[str] = set()
    last = max(walk.WALK_DAYS)
    for day in range(1, last + 1):
        quality = walk.QUALITIES[(day - 1) % len(walk.QUALITIES)]
        transcript = walk.play_day(
            assembled_client, db_session, headers, persona=persona, quality=quality, day=day, provider=production_day
        )
        assert transcript.get("error") is None, f"day {day}: {transcript.get('error')}"
        transcript["names_met_before"] = sorted(met)
        met |= walk_checks.names_met(transcript)
        if day in walk.WALK_DAYS or os.environ.get("WALK_ALL_DAYS") == "1":
            recorded.append(transcript)
        clock.advance(days=1)
    walk.write_transcripts(recorded, f"month-{persona.key}")
    _assert_clean(recorded, db_session)


def test_the_walk_marker_is_registered():
    """CI runs the long walk separately (``-m walk``); the default run skips it."""

    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert '"walk:' in text
