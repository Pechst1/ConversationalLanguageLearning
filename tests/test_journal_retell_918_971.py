"""#918 / #971: the Journal's retell is held to the scene's lines and is confirmed only
when it was checked, recalled what the scene kept and invented nothing.

#918 (live walk 19 Nov, A1.1 day 37). Retelling «Marin et le train», the learner wrote
«Marin a dit que Lila quitte Paris. Je ai dit non et il a demandé pourquoi, puis le chat a
mangé un perroquet.» The cat that ate a parrot is from another day. Marin answered «Oui,
c’est bien comme ça que ça s’est passé.» and the screen said «You recalled everything the
scene kept (2/2).»: the two «details» were the learner's own replies in the scene.

#971 (live walk 21 Nov, day 39). «What you remember» listed the learner's own uncorrected
sentence from the scene, «Je pense elle est une femme très fort, mais je ne la connais pas
bien.», as a detail to recall, and Lila confirmed a retell that recalled 1 of 4 while the
check had failed («The checker sent back an answer that could not be used»).

Review of the first attempt (#1009): the learner's own replies are not targets, but they
are what the scene said; a first-person retell of them («Je ne veux pas vendre la carte»)
is a memory and must never be called made up.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.services.journal import character_reaction, scene_facts_for, score_content_recall
from tests.test_journal import (  # noqa: F401 - the module's table fixture is autouse there
    TODAY,
    _concept,
    _FakeCorrector,
    _service,
    _user,
    _write,
    journal_table,
)
from tests.test_journal import _journey as _db_journey

CONFIRMS = "Oui, c’est bien comme ça que ça s’est passé."

# ---------------------------------------------------------------------------
# «Marin et le train» (17 Nov), as the 17 and 19 Nov walks describe it
# ---------------------------------------------------------------------------

MARIN_SETUP = (
    "Au Mistral, Marin pose une grande assiette de far breton sur la table. Il en a fait tous "
    "les jours cette semaine. Près de lui, le dossier bleu reste fermé ; il n'a pas utilisé le plan."
)
MARIN_TURNS = [
    {
        "learner": "Je ne comprend pas. Ton père est mort ?",
        "character": "Oui, il y a un an. Il faisait ce far breton. Tu comprends que je suis triste ?",
        "correction": {"corrected_fr": "Je ne comprends pas. Ton père est mort ?"},
    },
    {
        "learner": "Non, Lila ne quitte pas Paris. Je veux qu'elle reste.",
        "character": "Tu dis non au départ de Lila… Pourquoi ouvrir le dossier ?",
        "correction": None,
    },
    {
        "learner": "Dans le dossier, il y a une photo de ma grand-mère avec un perroquet.",
        "character": "Dans le dossier bleu, une photo montre ta grand-mère avec un perroquet.",
        "correction": None,
    },
]
MARIN_LEDGER = {
    "established": [
        {"key": "refuse_depart", "fact_fr": "L'apprenant refuse le départ de Lila.",
         "quote": "Non, Lila ne quitte pas Paris", "at": 1},
        {"key": "photo", "fact_fr": "L'apprenant parle d'une photo.",
         "quote": "une photo de ma grand-mère avec un perroquet", "at": 2},
    ]
}
MARIN_RETELL = (
    "Marin a dit que Lila quitte Paris. Je ai dit non et il a demandé pourquoi, "
    "puis le chat a mangé un perroquet."
)

# ---------------------------------------------------------------------------
# «Lila et la carte bleue» (20 Nov), as the 21 Nov walk describes it
# ---------------------------------------------------------------------------

SLIP = "Je pense elle est une femme très fort, mais je ne la connais pas bien."
LILA_TURNS = [
    {"learner": SLIP, "character": "Pour Napoléon, c'est bizarre, mais tant mieux.", "correction": None},
    {"learner": "Non, je ne vends pas la carte.",
     "character": "La carte est à toi. Tu ne la vends pas : ça me rassure.", "correction": None},
]
LILA_LEDGER = {
    "established": [
        {"key": "avis_margaux", "fact_fr": "L'apprenant trouve Margaux forte.", "quote": SLIP, "at": 0},
        {"key": "garde_carte", "fact_fr": "L'apprenant garde la carte.",
         "quote": "je ne vends pas la carte", "at": 1},
    ]
}


def _journey(turns, *, ledger, character, place, title, setup, callback=""):
    scene = SimpleNamespace(
        ordinal=0, kind="scene", public_prompt={"setup_fr": setup}, private_task={"rubric": "NEVER PUBLIC"}
    )
    respond = SimpleNamespace(
        ordinal=1, kind="respond", public_prompt={}, private_task={"turns": turns, "ledger": ledger}
    )
    return SimpleNamespace(
        scenario_snapshot={"character_name": character, "location_name": place, "title_fr": title},
        recap_snapshot={"story_outcome": {"callback_fr": callback}} if callback else {},
        serial_episode_id="ep-35",
        steps=[scene, respond],
    )


def _marin():
    return _journey(
        MARIN_TURNS, ledger=MARIN_LEDGER, character="Marin", place="Le Mistral",
        title="Marin et le train", setup=MARIN_SETUP,
    )


def _lila():
    return _journey(
        LILA_TURNS, ledger=LILA_LEDGER, character="Lila", place="Le Mistral",
        title="Lila et la carte bleue",
        setup="Au Mistral, Lila pose la carte bleue restée sous le bol.",
    )


# ---------------------------------------------------------------------------
# #971: what the retell is held to
# ---------------------------------------------------------------------------


def test_a_learner_sentence_with_slips_is_never_a_detail_to_recall():
    held = [fact.text_fr for fact in scene_facts_for(_lila(), story_context={})]
    assert SLIP not in held, f"the learner's uncorrected sentence is listed as what the scene kept: {held}"
    assert "Je ne vends pas la carte" not in " ".join(held), held


def test_the_retell_is_held_to_the_scenes_lines():
    held = [fact.text_fr for fact in scene_facts_for(_lila(), story_context={})]
    assert "La carte est à toi. Tu ne la vends pas : ça me rassure." in held, held


def test_a_learner_reply_counts_only_in_its_corrected_form_from_a_checked_turn():
    """A reply the check corrected is French the learner was shown; one whose check failed
    (#333) was read by nobody, so its «correction» is not a model either."""
    ledger = {"established": [{"key": "a", "fact_fr": "x", "quote": "je a faim beaucoup", "at": 0}]}
    corrected = [{"learner": "Je a faim beaucoup.", "character": "Moi aussi.",
                  "correction": {"corrected_fr": "J'ai très faim."}}]
    unchecked = [{**corrected[0], "check_failure": "model_error"}]
    base = {"ledger": ledger, "character": "Romy", "place": "Le Mistral", "title": "t", "setup": "Romy attend."}
    assert "J'ai très faim." in [f.text_fr for f in scene_facts_for(_journey(corrected, **base), story_context={})]
    held = [f.text_fr for f in scene_facts_for(_journey(unchecked, **base), story_context={})]
    assert "J'ai très faim." not in held and "je a faim beaucoup" not in held, held


# ---------------------------------------------------------------------------
# #918: the walk's retell of «Marin et le train»
# ---------------------------------------------------------------------------


def test_the_learners_own_replies_are_not_what_the_marin_scene_kept():
    held = " ".join(fact.text_fr for fact in scene_facts_for(_marin(), story_context={}))
    assert "Lila ne quitte pas Paris" not in held, held
    assert "photo de ma grand-mère" not in held, held


def _db_scene(db_session, user, concept, *, days, title, character, prompt, turns, ledger):
    """A scene ``days`` before today, stored the way the day stored it."""
    journey = DailyJourney(
        user_id=user.id,
        local_date=TODAY - timedelta(days=days),
        timezone="UTC",
        content_version="journey-content-v1",
        level_band="A1",
        status="completed",
        serial_episode_id="ep-35",
        scenario_snapshot={"title_fr": title, "character_name": character, "location_name": "Le Mistral"},
        recap_snapshot={},
    )
    db_session.add(journey)
    db_session.flush()
    db_session.add(
        DailyJourneyStep(
            journey_id=journey.id, ordinal=0, kind="scene", status="completed",
            public_prompt=prompt, private_task={"rubric": "NEVER PUBLIC"},
        )
    )
    db_session.add(
        DailyJourneyStep(
            journey_id=journey.id, ordinal=1, kind="respond", status="completed",
            target_kind="grammar", target_id=str(concept.id), public_prompt={},
            private_task={"turns": turns, "ledger": ledger},
        )
    )
    db_session.commit()
    return journey


def _db_marin(db_session, user, concept):
    """«Marin et le train», two days before today."""
    return _db_scene(
        db_session, user, concept, days=2, title="Marin et le train", character="Marin Lévêque",
        prompt={"setup_fr": MARIN_SETUP, "character_line_fr": "Tu veux une part de far breton ?"},
        turns=MARIN_TURNS, ledger=MARIN_LEDGER,
    )


def _db_lila(db_session, user, concept):
    """«Lila et la carte bleue», yesterday."""
    return _db_scene(
        db_session, user, concept, days=1, title="Lila et la carte bleue", character="Lila Bonnet",
        prompt={"setup_fr": "Au Mistral, Lila pose la carte bleue restée sous le bol."},
        turns=LILA_TURNS, ledger=LILA_LEDGER,
    )


def test_the_walks_retell_of_marin_is_neither_everything_nor_confirmed(db_session):
    """#918 done-when: the invented «Lila quitte Paris» and «le chat a mangé un perroquet»
    against «Marin et le train» get neither the confirmation nor «2/2»."""
    user = _user(db_session)
    _db_marin(db_session, user, _concept(db_session))
    entry = _write(db_session, user, _FakeCorrector(), MARIN_RETELL)
    assert entry.assessment_status == "checked"
    recall = entry.content_recall
    assert recall["status"] == "scored"
    found, total = len(recall["matched"]), recall["facts_total"]
    assert found < total, f"«{MARIN_RETELL}» was scored {found}/{total}: {recall['matched']}"
    assert CONFIRMS not in (entry.reaction_fr or ""), entry.reaction_fr


def test_an_invented_event_is_never_confirmed_even_when_every_detail_is_there():
    """Every fact recalled, plus a cat that ate a parrot from another day."""
    from app.services.journal import invented_clauses

    facts = [fact.as_dict() for fact in scene_facts_for(_marin(), story_context={})]
    every = " ".join(fact["text_fr"] for fact in facts)
    scene = [MARIN_SETUP, *[turn["character"] for turn in MARIN_TURNS]]
    honest = score_content_recall(every, facts, scene=scene, given={"marin", "mistral"})
    assert honest["missed"] == [] and honest["invented"] == []
    assert CONFIRMS in (character_reaction(character_name="Marin", recall=honest) or "")

    text = every + " Puis le chat a mangé un perroquet."
    recall = score_content_recall(text, facts, scene=scene, given={"marin", "mistral"})
    assert recall["missed"] == []
    assert recall["invented"] == ["le chat a mangé un perroquet"], recall["invented"]
    assert CONFIRMS not in (character_reaction(character_name="Marin", recall=recall) or "")
    assert invented_clauses("Le chat a mangé un perroquet.", scene, given={"marin"}) == [
        "Le chat a mangé un perroquet"
    ]


def test_a_retell_of_what_was_said_is_not_called_invented():
    from app.services.journal import invented_clauses

    scene = [MARIN_SETUP, *[turn["character"] for turn in MARIN_TURNS]]
    retell = (
        "Hier, Marin a fait un far breton pour son père. Il est très triste. "
        "Une photo de ta grand-mère avec un perroquet est dans le dossier bleu."
    )
    assert invented_clauses(retell, scene, given={"marin", "mistral"}) == []


# ---------------------------------------------------------------------------
# #971: a partial or unchecked retell is not confirmed
# ---------------------------------------------------------------------------


def test_a_retell_that_recalls_one_of_four_is_not_confirmed():
    recall = {
        "status": "scored",
        "matched": [{"kind": "scene", "text_fr": "Lila pose la carte bleue."}],
        "missed": [
            {"kind": "scene", "text_fr": "Pour Napoléon, c'est bizarre, mais tant mieux."},
            {"kind": "scene", "text_fr": "La carte est à toi."},
            {"kind": "scene", "text_fr": "Margaux a lu la lettre."},
        ],
    }
    line = character_reaction(character_name="Lila Bonnet", recall=recall) or ""
    assert CONFIRMS not in line, line
    assert "manque" in line


def test_an_unchecked_retell_is_not_confirmed(db_session):
    """The model's answer could not be used: no character says the retell was right."""
    user = _user(db_session)
    concept = _concept(db_session)
    _db_journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=concept, callback=None)
    retell = "Hier, Romy m'attendait au Mistral avec un livre sous le bras."
    entry = _write(db_session, user, _FakeCorrector(fail=True), retell)
    assert entry.assessment_status == "unavailable"
    assert entry.content_recall["missed"] == [], entry.content_recall
    assert CONFIRMS not in (entry.reaction_fr or ""), entry.reaction_fr

    # Once the check runs, the same retell is confirmed.
    checked = _service(db_session, _FakeCorrector()).retry_correction(user, entry)
    assert checked.assessment_status == "checked"
    assert CONFIRMS in (checked.reaction_fr or ""), checked.reaction_fr


# ---------------------------------------------------------------------------
# Review of #1009: the learner's own lines in the scene are memories, not inventions
# ---------------------------------------------------------------------------

GIVEN = {"marin", "lila", "mistral"}
LILA_RETELL = (
    "Hier, Lila a posé la carte bleue sur la table. Je ne veux pas vendre la carte. "
    "Elle est rassurée. Pour Napoléon c'est bizarre."
)
MARIN_TRUE_RETELL = (
    "J'ai dit non au départ de Lila. Une photo de ma grand-mère avec un perroquet est dans "
    "le dossier bleu. J'ai demandé à Marin si son père est mort."
)


def _support(journey):
    from app.services.journal import scene_lines

    return scene_lines(journey)


def test_a_retell_of_the_learners_own_line_is_not_called_invented():
    """A first-person retell tells what the learner said in the scene; each of these is
    true of its scene and was called made up, losing its words and the confirmation."""
    from app.services.journal import invented_clauses

    true_retells = [
        (_lila(), LILA_RETELL),
        (_marin(), MARIN_TRUE_RETELL),
        (_marin(), "Je lui ai dit que Lila ne quitte pas Paris parce que je veux qu'elle reste."),
        (_marin(), "Marin était très triste à cause de son père décédé l'année dernière."),
    ]
    for journey, retell in true_retells:
        invented = invented_clauses(retell, _support(journey), given=GIVEN)
        assert invented == [], f"«{retell}» is true of its scene, called made up: {invented}"


def test_a_true_retell_with_the_learners_own_lines_scores_everything_and_is_confirmed():
    for journey, retell in ((_lila(), LILA_RETELL), (_marin(), MARIN_TRUE_RETELL)):
        facts = [fact.as_dict() for fact in scene_facts_for(journey, story_context={})]
        recall = score_content_recall(retell, facts, scene=_support(journey), given=GIVEN)
        assert recall["invented"] == [] and recall["missed"] == [], recall
        line = character_reaction(character_name="Lila", recall=recall) or ""
        assert CONFIRMS in line, f"«{retell}» recalled everything and heard: {line!r}"


def test_the_walks_invention_is_still_invented_with_the_learners_lines_as_support():
    """Only «perroquet» of the cat's clause is in the scene, the learner's replies included."""
    from app.services.journal import invented_clauses

    assert invented_clauses(MARIN_RETELL, _support(_marin()), given=GIVEN) == [
        "le chat a mangé un perroquet"
    ]


def test_the_full_lila_and_marin_retells_are_confirmed_when_checked(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _db_lila(db_session, user, concept)
    entry = _write(db_session, user, _FakeCorrector(), LILA_RETELL)
    assert entry.assessment_status == "checked"
    assert not entry.content_recall.get("invented"), entry.content_recall
    assert CONFIRMS in (entry.reaction_fr or ""), entry.reaction_fr

    other = _user(db_session)
    _db_marin(db_session, other, concept)
    entry = _write(db_session, other, _FakeCorrector(), MARIN_TRUE_RETELL)
    assert entry.assessment_status == "checked"
    assert not entry.content_recall.get("invented"), entry.content_recall
    assert CONFIRMS in (entry.reaction_fr or ""), entry.reaction_fr
