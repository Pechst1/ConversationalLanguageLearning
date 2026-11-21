"""A La Forge bank top-up never seats a second item under an id the set holds.

The browser walks of 17-18 Nov stood 30 s on a late «Build» / «Dictation» card of La
Forge (main run 44074384470, en day 4, 22/24 «Build: "They are hungry tonight."»; the fr
and de walks of PRs 877, 879, 885, 887, 888, 889). The screen: every chip placed, then
«Not this answer — You left this item blank», the corrected line printed, and its
«Copy the correction» refused with «Not quite — try the line again.» for an exact copy.
A learner on that card is stuck too (only «Skip this exercise» leads on).

The mechanism: an item's id names its sentence said to nobody, while the top-up's
``blocked`` set holds the bank's own fingerprints, the vocative included. «Tu as froid
ce soir, Romy ?» passes a set that holds «Tu as froid ce soir ?» (from «…, Marin ?») and
is seated under the same id. Two items of one id break the set's shape
(``_payload_validation_errors``: the appended id no longer counts the base item), so
the séance's next read (``session_exercise_set``) builds a different set, and the item on
screen is graded against sentences the learner never saw: no item of the set has its id,
each of them is «blank», and the copy is compared with all of their keys joined.
"""

from __future__ import annotations

import random
from uuid import UUID

import pytest

from app.core.forge import Rung
from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services import item_bank as ib
from app.services.atelier import (
    AtelierCorrectionService,
    AtelierExerciseGenerator,
    served_fingerprints,
    session_exercise_set,
)
from app.services.forge import BankItemProvider
from app.services.grammar_catalog import FrenchCoreGrammarCatalog

UNIT = "FR2_A11_AVOIR"
#: The séance's set is drawn from the learner's and the séance's ids: fixed, so the set
#: holds a build whose vocative twin the bank has.
USER_ID = UUID("6f1c2a52-0d55-4d0e-9a4c-1f7a52c0e001")
SESSION_ID = UUID("6f1c2a52-0d55-4d0e-9a4c-1f7a52c0e002")


@pytest.fixture()
def seance(db_session):
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    user = User(id=USER_ID, email="forge-same-id@example.com", hashed_password="test", target_language="fr")
    db_session.add(user)
    db_session.commit()
    concept = db_session.query(GrammarConcept).filter_by(external_id=UNIT).one()
    session = AtelierSession(id=SESSION_ID, user_id=user.id, selected_concept_ids=[concept.id], status="in_progress", quote_payload={})
    db_session.add(session)
    db_session.commit()
    exercise_set = session_exercise_set(db_session, user=user, session=session, concept=concept)
    return user, concept, session, exercise_set


def _bank_items():
    for seed in range(400):
        yield from ib.default_bank().generate(UNIT, 12, seed=seed)


def _twin_and_fresh(db_session, user, exercise_set):
    """A bank item that builds under an id the set holds, and one that builds a new id."""

    held = {item["id"] for item in exercise_set.payload["recognize"]["word_bank"]["items"]}
    served = served_fingerprints(db_session, user)
    twin = fresh = None
    for candidate in _bank_items():
        built = ib.word_bank_item(candidate, lesson_external_id=UNIT)
        if not built or candidate.fingerprint in served:
            continue
        # The twin says the held sentence to someone: its own fingerprint is not the id's.
        if twin is None and built["id"] in held and not built["id"].endswith(candidate.fingerprint[:10]):
            twin = candidate
        elif fresh is None and built["id"] not in held:
            fresh = candidate
        if twin and fresh:
            return twin, fresh
    raise AssertionError("no vocative twin of the set's builds in the bank")


def _stream(monkeypatch, *candidates):
    monkeypatch.setattr(ib.ItemBank, "sample", lambda self, unit, rng, **kwargs: iter(candidates))


def test_a_top_up_skips_an_item_whose_id_the_set_holds(db_session, seance, monkeypatch):
    user, concept, session, exercise_set = seance
    twin, fresh = _twin_and_fresh(db_session, user, exercise_set)
    held = [item["correct_answer"] for item in exercise_set.payload["recognize"]["word_bank"]["items"]]
    _stream(monkeypatch, twin, fresh)
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    made = provider.top_up_many(concept_id=concept.id, rung=Rung.BUILD, drill="dictation")
    assert [item.item_id for item in made] == [ib.word_bank_item(fresh, lesson_external_id=UNIT)["id"]], (
        f"seated {[item.payload['correct_answer'] for item in made]} beside {held}"
    )

    db_session.expire_all()
    owned = provider.sets[concept.id]
    db_session.refresh(owned)
    ids = [item["id"] for item in owned.payload["recognize"]["word_bank"]["items"]]
    assert len(ids) == len(set(ids)), "two items under one id"
    assert AtelierExerciseGenerator._payload_validation_errors(owned.payload, concept=concept) == []
    session = db_session.get(AtelierSession, session.id)
    again = session_exercise_set(db_session, user=user, session=session, concept=concept)
    assert again.id == owned.id, "the séance's next read built a new set: the item on screen is in none"


def test_the_posed_build_is_graded_by_its_own_key_and_its_copy_is_accepted(db_session, seance, monkeypatch):
    """The walk's build (every chip in the order shown, the spare one too), then its copy."""

    user, concept, session, exercise_set = seance
    twin, fresh = _twin_and_fresh(db_session, user, exercise_set)
    _stream(monkeypatch, twin, fresh)
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    [posed] = provider.top_up_many(concept_id=concept.id, rung=Rung.BUILD, drill="dictation")
    db_session.expire_all()
    session = db_session.get(AtelierSession, session.id)

    item = posed.payload
    chips = list(item["tokens"])
    random.Random(4).shuffle(chips)
    attempt = AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id=f"forge:{concept.id}:recognize:word_bank:{posed.item_id}",
        answer_payload={"answers": {posed.item_id: chips}},
    )
    assert [entry["id"] for entry in attempt.prompt_payload["items"]] == [posed.item_id], (
        "graded against other sentences than the one on screen"
    )
    errata = attempt.correction_payload["errata"]
    assert errata and all(entry.get("item_id") == posed.item_id for entry in errata)
    assert all(entry.get("task_error_type") != "task_compliance" for entry in errata), "«You left this item blank»"

    copied = AtelierCorrectionService(db_session).record_micro_repair(
        attempt=attempt, text=item["correct_answer"], erratum_index=0
    )
    assert copied.correction_payload["micro_repairs"]["0"]["status"] == "ok", "an exact copy refused"
