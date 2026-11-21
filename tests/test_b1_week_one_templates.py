"""P6 · stage 3: a B1 learner's first week in La Forge runs on templates.

Decision proposal 3 says B1 learners are in the pilot once the rules they
meet in week one have sentence templates. Without a unit, La Forge has no
item bank for the rule: the séance falls back to a fixed set of about fifteen
sentences and the Forge's top-up returns nothing, so a learner who practises
the rule on five days sees the same sentences again.

Week one, read from the code (catalogue v2, Normal pace):

* the scheduler's first eight new concepts for a B1.1 learner
  (``AtelierScheduler.next_new_concepts``, one introduction at a time);
* the season's day-2 tentpole rule (``FR2_B11_PREP_INFINITIVE``), which
  ``concept_life.introduction_for_today`` brings forward within its lookahead;
* the subjonctif drill a B1 walk was given on day 4 from its own errors
  (``FR2_B12_SUBJ_FORM``).
"""

from __future__ import annotations

import random
import re
from uuid import uuid4

import pytest

from app.config import settings
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.services import item_bank as ib
from app.services.atelier import AtelierScheduler
from app.services.grammar_catalog import FrenchCoreGrammarCatalog

#: The scheduler's first eight for a B1.1 learner, in order (catalogue v2).
SCHEDULER_FIRST_EIGHT = (
    "FR2_B11_PLUS_QUE_PARFAIT",
    "FR2_B11_NARRATION",
    "FR2_B11_CONDITIONAL",
    "FR2_B11_SI_TYPE1",
    "FR2_B11_SI_TYPE2",
    "FR2_B11_TEMPORAL_FUTURE",
    "FR2_B11_DOUBLE_PRONOUNS",
    "FR2_B11_DONT",
)
WEEK_ONE = (*SCHEDULER_FIRST_EIGHT, "FR2_B11_PREP_INFINITIVE", "FR2_B12_SUBJ_FORM")

DAYS = 5
ITEMS_PER_DAY = 8
VARIETY_WINDOW_DAYS = 7

_CAST = ("Gus", "Lila", "Margaux", "Marin", "Romy")


def _said_to_nobody(sentence: str) -> str:
    """The sentence without a coach's name tacked on («…, Gus.»), folded."""

    bare = re.sub(rf",\s*(?:{'|'.join(_CAST)})\s*([.?!])\s*$", r"\1", sentence)
    return ib.normalize(bare)


@pytest.mark.parametrize("unit", WEEK_ONE)
def test_every_week_one_b1_rule_has_a_unit(unit: str) -> None:
    assert ib.units_for_external_id(unit) == [unit], f"{unit} has no sentence templates"


@pytest.mark.parametrize("unit", WEEK_ONE)
def test_sample_yields_forty_distinct_items_on_every_rung(unit: str) -> None:
    stream = ib.default_bank().sample(unit, random.Random(f"p6:{unit}"), detector=ib.unit_detector(unit))
    items = [item for _, item in zip(range(40), stream, strict=False)]
    assert len(items) == 40, f"{unit}: only {len(items)} items"
    assert len({item.fingerprint for item in items}) == 40
    requirement = {"concept_id": 1, "external_id": unit, "label": unit, "target_count": 1}
    for rung in ib.RUNG_TYPES:
        posed = [item for index, item in enumerate(items) if ib.rung_item(rung, item, index=index, requirement=requirement)]
        assert len(posed) >= 20, f"{unit}: {rung} poses {len(posed)} of 40"


@pytest.mark.parametrize("unit", WEEK_ONE)
def test_five_forge_days_never_repeat_a_sentence(unit: str) -> None:
    """Eight items a day for five days, the seven-day window excluded, as La Forge draws them."""

    bank = ib.default_bank()
    detector = ib.unit_detector(unit)
    served: list[tuple[int, str, str]] = []  # (day, fingerprint, sentence said to nobody)
    for day in range(DAYS):
        window = {fp for served_day, fp, _ in served if day - served_day < VARIETY_WINDOW_DAYS}
        stream = bank.sample(unit, random.Random(f"forge:{unit}:{day}"), exclude=window, detector=detector)
        today = [item for _, item in zip(range(ITEMS_PER_DAY), stream, strict=False)]
        assert len(today) == ITEMS_PER_DAY, f"{unit}: day {day + 1} has {len(today)} items"
        served.extend((day, item.fingerprint, _said_to_nobody(item.sentence)) for item in today)
    sentences = [sentence for _, _, sentence in served]
    twice = sorted({sentence for sentence in sentences if sentences.count(sentence) > 1})
    assert not twice, f"{unit}: served twice in {DAYS} days: {twice[:3]}"


def test_scheduler_first_eight_for_a_b1_learner_all_have_templates(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    try:
        user = User(
            id=uuid4(),
            email=f"{uuid4()}@example.com",
            hashed_password="test",
            native_language="en",
            target_language="fr",
            proficiency_level="B1",
            cefr_estimate="B1.1",
            daily_goal_minutes=15,
        )
        db_session.add(user)
        db_session.commit()
        scheduler = AtelierScheduler(db_session)
        met: list[str] = []
        for _ in range(len(SCHEDULER_FIRST_EIGHT)):
            concept: GrammarConcept = scheduler.next_new_concepts(user, limit=1, language="fr")[0]
            met.append(str(concept.external_id))
            db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id))
            db_session.commit()
        without = [external_id for external_id in met if not ib.units_for_external_id(external_id)]
        assert not without, f"week-one B1 rules without templates: {without} (met: {met})"
        assert tuple(met) == SCHEDULER_FIRST_EIGHT, met
    finally:
        FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
