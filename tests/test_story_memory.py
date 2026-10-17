"""Story engine Phase 3 — ``story_memory``, the ledger of what the learner said.

Pure functions: these tests build days by hand. The days the engine settles, and what
each model is then sent, are in tests/test_story_memory_days.py.
"""

from __future__ import annotations

import pytest

GUS, MARGAUX, LILA, CAMILLE = "augustin_de_roncourt", "margaux_barman", "lila_bonnet", "camille_marchand"


@pytest.fixture
def memory():
    """The module, imported when a test runs (``scripts/loop/red_green.py`` runs these
    tests on the code before the module existed: an error there, never a collection
    stop for the whole run)."""

    from app.services import story_memory

    return story_memory


@pytest.fixture
def lexicon(memory):
    return memory.word_check({"pas", "perdu", "allemand", "italien", "fatigué", "ici", "content"})


@pytest.fixture
def day(memory, lexicon):
    def one_day(n: int, *lines: str, speaker: str = GUS, witnesses=(), **extra):
        """One settled day of single exchanges with ``speaker`` (each line answers the one before)."""

        exchanges = [{"learner": line, "character": f"Réponse {i}. Et toi ?"} for i, line in enumerate(lines)]
        return memory.Day(
            event_id=f"journey:{n}:story",
            day=n,
            date=f"2026-11-{n:02d}",
            speaker=speaker,
            witnesses=tuple(witnesses),
            exchanges=tuple(exchanges),
            opening_fr=extra.pop("opening_fr", "Vous êtes qui, exactement ?"),
            task=extra.pop("task", "Say who you are."),
            not_names=frozenset({"Camille", "Gus", "Margaux", "Lila"}),
            is_word=lexicon,
            **extra,
        )

    return one_day


# ---------------------------------------------------------------------------
# The learner's name, without a model
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "asked", "name"),
    [
        ("Je m'appelle Lena.", None, "Lena"),
        ("Bonjour ! je m'apelle lena et je suis là pour ma grand-mère", None, "Lena"),
        ("Mon prénom, c'est Jonas.", None, "Jonas"),
        ("Moi, c'est Paul.", None, "Paul"),
        ("Appelle-moi Fred, tout le monde le fait.", None, "Fred"),
        # A French word after «je m'appelle» is no name.
        ("Je m'appelle pas comme ça.", None, None),
        # «Je suis Lena.» names only the answer to who the learner is ...
        ("Je suis Lena.", "Vous êtes qui, exactement ?", "Lena"),
        ("Je suis Lena, la petite-fille d'Odile.", "C'est qui, vous ?", "Lena"),
        ("Je suis Lena.", "Tu veux un café ?", None),
        # ... and never an adjective or a clause that goes on.
        ("Je suis Allemande.", "Tu es qui ?", None),
        ("Je suis perdu.", "Vous êtes qui ?", None),
        ("Je suis Lena Müller.", "Vous êtes qui ?", None),
        # Never a name of the story's own cast.
        ("Je m'appelle Camille, comme vous.", None, None),
    ],
)
def test_the_name_a_learner_gives_is_read_from_their_own_words(text, asked, name, memory, lexicon):
    assert memory.stated_name(text, asked=asked, not_names={"Camille"}, is_word=lexicon) == name


# ---------------------------------------------------------------------------
# Writing a day
# ---------------------------------------------------------------------------


def test_a_day_keeps_each_line_with_what_it_answered_and_who_heard_it(memory, day):
    after = memory.after_day(None, day(1, "Je m'appelle Lena.", "Je viens de Hambourg.", witnesses=[GUS, LILA]))
    first, second = after["said"]
    assert first["quote"] == "Je m'appelle Lena." and first["asked_fr"] == "Vous êtes qui, exactement ?"
    assert first["task"] == "Say who you are." and "task" not in second
    assert second["asked_fr"] == "Et toi ?", "a later line answered the character's last question"
    assert first["heard_by"] == sorted([GUS, LILA])
    name = after["facts"][0]
    assert (name["key"], name["value"], name["known_by"]) == ("name", "Lena", sorted([GUS, LILA]))


def test_a_settled_day_is_written_once(memory, day):
    once = memory.after_day(None, day(1, "Je m'appelle Lena."))
    assert memory.after_day(once, day(1, "Je m'appelle Lena.")) == once


def test_bookkeeping_is_not_a_reading_of_the_learner(memory):
    exchanges = (
        {"learner": "Oui.", "heard": {"meant": "fallback: authored reply"}},
        {"learner": "Non.", "heard": {"meant": "The learner refuses the key."}},
    )
    after = memory.after_day(None, memory.Day("journey:1:story", 1, None, GUS, (), exchanges))
    assert ["meant" in row for row in after["said"]] == [False, True]


def test_a_reported_fact_is_kept_only_with_the_learners_own_words(memory, day):
    reported = [
        {"key": "Prénom", "fact_fr": "L'apprenant s'appelle Lena.", "quote": "je m'appelle lena", "value": "Lena"},
        {"key": "job", "fact_fr": "L'apprenant est infirmière.", "quote": "je suis infirmière", "value": "médecin"},
        {"key": "from", "fact_fr": "L'apprenant vient de Berlin.", "quote": "Je viens de Berlin", "value": "Berlin"},
        {"key": "", "fact_fr": "x", "quote": "y"},
        "not a row",
    ]
    after = memory.after_day(None, day(1, "Bonjour, je m'appelle lena et je suis infirmière.", learned=tuple(reported)))
    facts = {fact["key"]: fact for fact in after["facts"]}
    assert set(facts) == {"name", "job"}, "the model's key for the name is the name; Berlin was never said"
    assert facts["name"]["value"] == "Lena"
    assert "value" not in facts["job"], "a value the quote does not contain is dropped, the fact kept"


def test_a_name_told_to_two_people_is_known_by_both(memory):
    exchanges = (
        {"learner": "Je m'appelle Lena.", "route": {"turn": "t1"}},
        {"learner": "Moi, c'est Lena !", "route": {"turn": "t2"}},
    )
    turns = ({"id": "t1", "to": GUS, "question_fr": "Vous êtes qui ?"}, {"id": "t2", "to": MARGAUX, "question_fr": "Et toi ?"})
    after = memory.after_day(None, memory.Day("journey:1:story", 1, None, GUS, (), exchanges, turns=turns))
    assert [row["to"] for row in after["said"]] == [GUS, MARGAUX]
    assert after["facts"][0]["known_by"] == sorted([GUS, MARGAUX])


def test_on_a_tentpole_everyone_in_the_room_heard_the_learner(memory):
    """T1 b (paid read, 2026-10-17): the learner told Camille «non» with Lila, Gus and
    Marin at the table; only who spoke before the first question «heard» it, so Lila
    knew nothing of it the next morning."""

    exchanges = ({"learner": "Non, je ne vends pas.", "route": {"turn": "b.turn1", "reply": "d"}},)
    turns = ({"id": "b.turn1", "to": CAMILLE, "question_fr": "Vous allez vendre, non ?", "present": [GUS, LILA, MARGAUX]},)
    after = memory.after_day(None, memory.Day("journey:2:story", 2, None, CAMILLE, (MARGAUX,), exchanges, turns=turns))
    assert after["said"][0]["heard_by"] == sorted([CAMILLE, GUS, LILA, MARGAUX])
    assert [row["quote"] for row in memory.narrow(memory.full_view(after), {LILA})["said"]] == ["Non, je ne vends pas."]


def test_the_same_words_to_the_same_person_twice_are_one_line(memory):
    """Asked again («Pardon ?»), the learner says it again: one line, so the readers'
    tail keeps the days before it (paid read: day 1's name had fallen out of it)."""

    exchanges = (
        {"learner": "Merci. Je ne sais pas encore.", "route": {"turn": "b.letter", "reply": "__ask_again__"}},
        {"learner": "Merci.  Je ne sais pas encore.", "route": {"turn": "b.letter", "reply": "nobody"}},
        {"learner": "Merci. Je ne sais pas encore.", "route": {"turn": "b.turn2"}},
    )
    turns = (
        {"id": "b.letter", "to": LILA, "question_fr": "À qui tu montres la lettre ?", "present": [GUS]},
        {"id": "b.turn2", "to": GUS, "question_fr": "Et toi ?"},
    )
    after = memory.after_day(None, memory.Day("journey:2:story", 2, None, LILA, (), exchanges, turns=turns))
    assert [(row["to"], row["id"]) for row in after["said"]] == [(LILA, "said:2:0"), (GUS, "said:2:1")]
    assert after["said"][0]["heard_by"] == sorted([GUS, LILA])


def test_the_same_fact_again_widens_who_knows_it_and_a_new_one_keeps_the_old_for_those_who_only_heard_that(memory, day):
    stay = {"key": "stay", "fact_fr": "L'apprenant reste trois semaines.", "quote": "Je reste trois semaines.", "value": "trois semaines"}
    after = memory.after_day(None, day(1, "Je reste trois semaines.", speaker=GUS, learned=(stay,)))
    same = {**stay}
    after = memory.after_day(after, day(2, "Je reste trois semaines.", speaker=LILA, learned=(same,)))
    row = after["facts"][0]
    assert row["known_by"] == sorted([GUS, LILA]) and row["confirmed_day"] == 2
    longer = {"key": "stay", "fact_fr": "L'apprenant reste un an.", "quote": "Finalement je reste un an.", "value": "un an"}
    after = memory.after_day(after, day(3, "Finalement je reste un an.", speaker=MARGAUX, learned=(longer,)))
    row = after["facts"][0]
    assert row["value"] == "un an" and row["known_by"] == [MARGAUX]
    assert row["before"]["known_by"] == sorted([GUS, LILA]) and row["before"]["value"] == "trois semaines"
    # Each reader believes the version they heard.
    view = memory.full_view(after)
    assert memory.narrow(view, {LILA})["facts"][0]["fact_fr"] == "L'apprenant reste trois semaines."
    assert memory.narrow(view, {MARGAUX})["facts"][0]["fact_fr"] == "L'apprenant reste un an."
    assert memory.narrow(view, {CAMILLE}) is None


def test_the_name_outlives_every_other_fact(memory, day):
    after = memory.after_day(None, day(1, "Je m'appelle Lena."))
    for n in range(2, 2 + memory.MAX_FACTS + 3):
        fact = {"key": f"k{n}", "fact_fr": f"Fait {n}.", "quote": f"Phrase {n}.", "value": None}
        after = memory.after_day(after, day(n, f"Phrase {n}.", learned=(fact,)))
    keys = [fact["key"] for fact in after["facts"]]
    assert len(keys) == memory.MAX_FACTS and "name" in keys


def test_a_life_keeps_a_bounded_tail_of_lines(memory, day):
    after = None
    for n in range(1, memory.MAX_SAID + 10):
        after = memory.after_day(after, day(n, f"Ligne {n}."))
    assert len(after["said"]) == memory.MAX_SAID and after["said"][-1]["quote"] == f"Ligne {memory.MAX_SAID + 9}."
    assert len(after["days"]) == memory.MAX_DAYS
    assert len(memory.full_view(after)["said"]) == memory.VIEW_SAID


# ---------------------------------------------------------------------------
# Questions open across days
# ---------------------------------------------------------------------------


def test_a_question_the_learner_asked_stays_open_until_answered(memory, day):
    asked = "Et le chat, il s'appelle comment ?"
    after = memory.after_day(None, day(1, f"Oui. {asked}", speaker=LILA, left_open=(asked, "Une question inventée ?")))
    (row,) = after["open"]
    assert (row["by"], row["to"], row["question_fr"], row["status"]) == ("learner", LILA, asked, "open")
    # The same question asked again is not a second row.
    again = memory.after_day(after, day(2, asked, speaker=LILA, left_open=(asked,)))
    assert len(again["open"]) == 1
    answered = memory.after_day(after, day(2, "Merci !", speaker=LILA, answered_open_ids=(row["id"],)))
    assert answered["open"][0]["status"] == "answered" and answered["open"][0]["closed_by"] == "journey:2:story"
    # A page that comes back to it closes it, however the day ends.
    returned = memory.after_day(after, day(2, "Ah bon.", speaker=LILA, returns_to=row["id"], outcome="not_yet"))
    assert returned["open"][0]["status"] == "answered"


def test_only_someone_who_knows_a_question_can_answer_it(memory, day):
    """Paid read, 2026-10-17: Lila's page «returned» to what the learner had asked Marin
    the day before, and the question closed with nobody answering it."""

    asked = "On commence quand ?"
    after = memory.after_day(None, day(1, f"D'accord. {asked}", speaker=GUS, left_open=(asked,)))
    (row,) = after["open"]
    elsewhere = memory.after_day(after, day(2, "Oui.", speaker=LILA, witnesses=[MARGAUX], returns_to=row["id"]))
    assert elsewhere["open"][0]["status"] == "open"
    told = memory.after_day(after, day(2, "Oui.", speaker=LILA, answered_open_ids=(row["id"],)))
    assert told["open"][0]["status"] == "open"
    view = memory.full_view(after)
    assert memory.returnable(view, row["id"], [LILA, MARGAUX]) is None
    assert memory.returnable(view, row["id"], [LILA, GUS])["question_fr"] == asked
    assert memory.returnable(view, "open:9:9", [GUS]) is None
    back = memory.after_day(after, day(2, "Ah.", speaker=LILA, witnesses=[GUS], returns_to=row["id"]))
    assert back["open"][0]["status"] == "answered"


def test_a_question_nobody_comes_back_to_lapses(memory, day):
    after = memory.after_day(None, day(1, "Qui est Solvel ?", left_open=("Qui est Solvel ?",)))
    after = memory.after_day(after, day(1 + memory.OPEN_DAYS - 1, "Bonjour."))
    assert after["open"][0]["status"] == "open"
    after = memory.after_day(after, day(1 + memory.OPEN_DAYS, "Bonjour."))
    assert after["open"][0]["status"] == "lapsed"
    assert memory.full_view(after).get("open") is None


def test_a_page_keeps_its_own_question_open_only_when_the_day_did_not_settle_it(memory, day):
    kept = memory.after_day(
        None, day(1, "Je ne sais pas.", opening_fr="Bon. Tu vends ou tu restes ?", carries_over=True, outcome="not_yet")
    )
    (row,) = kept["open"]
    assert (row["by"], row["to"], row["question_fr"]) == (GUS, "learner", "Tu vends ou tu restes ?")
    settled = memory.after_day(None, day(1, "Je reste.", opening_fr="Tu vends ou tu restes ?", carries_over=True))
    assert settled["open"] == []
    # The character's own question is answered only by a day the learner settles.
    waiting = memory.after_day(kept, day(2, "Toujours pas.", returns_to=row["id"], outcome="not_yet"))
    assert waiting["open"][0]["status"] == "open"
    done = memory.after_day(kept, day(2, "Je reste.", returns_to=row["id"]))
    assert done["open"][0]["status"] == "answered"


# ---------------------------------------------------------------------------
# Reading: the writers see who knows what, a character only what they heard
# ---------------------------------------------------------------------------


def test_a_character_sees_only_what_they_heard_without_the_who_knows_lists(memory, day):
    after = memory.after_day(None, day(1, "Je m'appelle Lena.", speaker=GUS))
    after = memory.after_day(after, day(2, "Je cherche ma sœur.", speaker=LILA, witnesses=[MARGAUX]))
    view = memory.full_view(after)
    assert view["learner_name"] == {"value": "Lena", "known_by": [GUS]}
    gus = memory.narrow(view, {GUS})
    assert gus["learner_name"] == "Lena" and [row["quote"] for row in gus["said"]] == ["Je m'appelle Lena."]
    assert all("heard_by" not in row for row in gus["said"]) and all("known_by" not in row for row in gus["facts"])
    margaux = memory.narrow(view, {MARGAUX})
    assert "learner_name" not in margaux and [row["quote"] for row in margaux["said"]] == ["Je cherche ma sœur."]
    # A page with several people keeps who knows what.
    both = memory.narrow(view, {GUS, MARGAUX})
    assert both["learner_name"]["known_by"] == [GUS] and len(both["said"]) == 2
    assert memory.known_to(view, GUS) == {"learner_name": "Lena", "facts": ["L'apprenant s'appelle Lena."]}
    assert memory.known_to(view, CAMILLE) is None
    assert memory.view(None) is None and memory.view({}) is None


def test_a_remembered_line_is_a_past_a_page_may_cite(memory, day):
    after = memory.after_day(None, day(1, "Non, je ne vends pas.", speaker=CAMILLE))
    rows = dict(memory.ledger_rows(after))
    assert rows["said:1:0"].endswith("Non, je ne vends pas.")
    assert memory.row_by_id(after, "said:1:0")["quote"] == "Non, je ne vends pas."
    assert memory.row_by_id(after, "said:9:9") is None and memory.row_by_id(after, None) is None


# ---------------------------------------------------------------------------
# A memory is never the reason a turn or a page is lost
# ---------------------------------------------------------------------------


def test_malformed_reports_are_dropped_never_refused():
    from app.services.living_story import SceneDraft, SemanticTurn
    from app.services.season.turns import ReplyChoice
    from app.services.story_split import PagePlan

    turn = SemanticTurn.model_validate(
        {
            "outcome": "met",
            "understood_intent": "x",
            "reply_fr": "D'accord.",
            "needs_clarification": False,
            "learned": [{"key": "name"}, "Lena", {"key": "name", "fact_fr": "L'apprenant s'appelle Lena.", "quote": "Lena"}],
            "left_open": "Qui est Solvel ?",
            "answered_open_ids": None,
        }
    )
    assert [fact.key for fact in turn.learned] == ["name"]
    assert turn.left_open == ["Qui est Solvel ?"] and turn.answered_open_ids == []
    assert ReplyChoice.model_validate({"reply_id": "a", "learned": "nothing"}).learned == []
    plan = {
        "location_id": "le_mistral",
        "cast": [LILA],
        "lead_id": LILA,
        "beats": ["Lila waits.", "She asks."],
        "change": {"before": "Nothing is decided.", "after": "The learner decides."},
        "question": "So?",
        "task": "Answer Lila.",
    }
    # A model that copies the schema's own words back keeps today's question closing today.
    plan = PagePlan.model_validate({**plan, "returns_to": "null", "stays_open": "true only when it needs time"})
    assert plan.returns_to is None and plan.stays_open is False
    assert SceneDraft.model_fields["carries_over"].default is False


def test_every_reader_of_the_name_is_told_a_name_is_not_a_gender(memory):
    """Paid read, 2026-10-17: once the story knew «Lena», a summary for a learner with a
    neutral address read «elle va» and «she is staying», and spoke of «Lena» instead of
    to them."""

    from app.services import living_story, story_lanes, story_split
    from app.services.season import turns

    readers = {
        "director": living_story.DIRECTOR,
        "actor": living_story.ACTOR,
        "voice": story_lanes.VOICE,
        "story lane": story_lanes.STORY,
        "planner": story_split.PLANNER,
        "writer": story_split.AUTHOR,
        "tentpole classifier": turns.CLASSIFIER,
    }
    for reader, prompt in readers.items():
        assert prompt.count(memory.NAME_NOTE) == 1, reader
    for reader in ("actor", "story lane"):
        assert "summary_native still speaks to the learner as you, never by their name" in readers[reader], reader


def test_a_page_that_forgets_what_the_learner_said_is_refused_as_storytelling():
    from app.services.season.canon_guards import STORYTELLING, review_class
    from app.services.season.director import StoryReview, review_verdict

    review = StoryReview(meaningful_change=True, remembers=False, issues=["Gus asks the learner's name again."])
    assert review_verdict(review) is False
    assert review_class(review) == STORYTELLING, "a second refusal for it alone is still served"
    assert review_verdict(StoryReview(meaningful_change=True)) is True, "a reply that leaves it out refuses nothing"


def test_the_cast_pronoun_comes_from_the_registry_and_camille_from_this_lifes_choice():
    from app.services.cast_registry import pronoun_for

    assert pronoun_for(CAMILLE) is None, "nobody has decided: the name, never a guess"
    assert pronoun_for(CAMILLE, flags={"s1.camille_gender": "m"}) == "il"
    assert pronoun_for("camille", flags={"s1.camille_gender": "f"}) == "elle"
    assert pronoun_for(GUS) == "il" and pronoun_for(LILA) == "elle"
    assert pronoun_for("someone_new", gender="f") == "elle" and pronoun_for("someone_new") is None


def test_the_learners_name_is_a_known_word_on_a_page():
    from app.services.lexical_coverage import world_proper_nouns

    assert world_proper_nouns({"world": {"cast": []}, "memory": {"learner_name": {"value": "Lena", "known_by": [GUS]}}})
    assert world_proper_nouns({"world": {"cast": []}, "memory": {"learner_name": "Lena"}})
    assert not world_proper_nouns({"world": {"cast": []}})
