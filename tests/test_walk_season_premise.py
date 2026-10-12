"""Walk 2026-10-12 (#77): the scene step carries the season's premise in the
learner's language, so «Bisher» can say who they are and what is at stake."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.services import story_archive
from app.services.season.format import load_season


class _Db:
    def __init__(self, thread):
        self.thread = thread

    def get(self, _model, _key):
        return self.thread


def _scene():
    return SimpleNamespace(serial_thread_id=uuid.uuid4())


def test_the_premise_is_the_seasons_question_in_the_learners_language():
    question = load_season("s1").question
    db = _Db(SimpleNamespace(world_bible={"season_script": "s1"}))
    assert story_archive.season_premise(db, _scene(), "de") == question.native["de"]
    assert story_archive.season_premise(db, _scene(), "en") == question.native["en"]
    assert story_archive.season_premise(db, _scene(), "fr") == (question.b1 or question.a2)
    assert "Großmutter" in story_archive.season_premise(db, _scene(), "de")


def test_no_premise_off_a_scripted_season():
    assert story_archive.season_premise(_Db(None), _scene(), "de") is None
    assert story_archive.season_premise(_Db(SimpleNamespace(world_bible={})), _scene(), "de") is None
    assert story_archive.season_premise(_Db(None), None, "de") is None
    unknown = _Db(SimpleNamespace(world_bible={"season_script": "no-such-season"}))
    assert story_archive.season_premise(unknown, _scene(), "de") is None


def test_the_language_is_the_days_chrome_language():
    brief = {"scenario_brief": {"control_language": "de"}}
    journey = SimpleNamespace(steps=[SimpleNamespace(private_task=None), SimpleNamespace(private_task=brief)])
    assert story_archive._journey_language(journey) == "de"
    assert story_archive._journey_language(SimpleNamespace(steps=[])) == "en"
