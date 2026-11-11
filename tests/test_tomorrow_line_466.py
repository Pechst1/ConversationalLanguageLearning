"""What a finished scene leaves for tomorrow (#466, #620, #445, #455), read against the walks.

Walk of 9 Nov (#620): the closing panel said «Toi, tu me caches quelque chose… Tu as promis,
hein : « Je pense que je vais vendre la bouillotte de Odile, mais non, je ne vends pas le
café. »». The learner's three replies never mentioned selling. Done and Home repeated it.

Walks of 2, 4, 7 and 8 Nov (#466): Done and Home printed «Tomorrow · Dis, j'y repense…»,
«J'ai rien entendu», «Au fait…»: the first words of a hook, which are a voice opener.

Tomorrow is now a sentence of its own (``open_fr``), and quotes only what the learner wrote
in this scene without a correction. The story's writer may write it from the scene's record.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services import achievement_recap, scene_ledger, story_lanes, story_teaser
from app.services import living_story as engine
from app.services.season import runtime
from app.services.season.closing import SceneClosing
from app.services.season.turns import ReplyChoice
from tests.prompt_regression import harness

#: The walk of 9 Nov (#620), word for word.
WALK_REPLIES = [
    "Non, je ne partage pas la pizza… tu a menti à Margaux",
    "Mon chat Napoleon aime la pizza. Il dort sur le canape. Et toi, tu as un chat ?",
    "Oui Napoleon aime le poisson. Bon, je lis la lettre avec toi, mais dis moi la verité d abord.",
]
STALE_QUOTE = "Je pense que je vais vendre la bouillotte de Odile, mais non, je ne vends pas le café."
STALE_ROW = {
    "id": "old:commitment:0",
    "status": "open",
    "witnesses": ["lila_bonnet"],
    "text_fr": "Je vais vendre la bouillotte d'Odile.",
    "source_quote": STALE_QUOTE,
}
#: The walk of 4 Nov's detail, ten words: the attempt of #530 clipped it mid-fact.
WALK_PLANT = {
    "id": "e2:plant",
    "text_fr": "Margaux range une lettre sans nom dans le tiroir du comptoir.",
    "status": "open",
    "character_id": "margaux_barman",
}
TODAY = "2026-11-09"


def _hook(live, **kwargs):
    defaults = {"character_id": "lila_bonnet", "register": "tu", "date": TODAY, "seed": "walk"}
    return engine.next_teaser(live, {}, **{**defaults, **kwargs})


def test_the_walks_hook_is_not_written():
    """#620: a promise from an earlier day has words nobody said in this scene."""

    hook = _hook({"commitments": [STALE_ROW]}, said=WALK_REPLIES, clean=WALK_REPLIES)
    assert hook is None or "bouillotte" not in str(hook)


def test_a_hook_quotes_nothing_when_the_scene_is_not_given():
    """The default is safe: a caller who forgets the replies quotes nobody."""

    row = {**STALE_ROW, "text_fr": "Apporter du pain dimanche.", "source_quote": "Je vais apporter du pain dimanche."}
    hook = _hook({"commitments": [row]})
    assert hook is not None and "«" not in hook["text_fr"]


@pytest.mark.parametrize(
    ("hook", "said", "holds"),
    [
        ("Tu as promis, hein : « Je viens samedi. »", ["Oui, je viens samedi."], True),
        ("Tu as promis, hein : « Je viens samedi. »", ["Non, je reste chez moi."], False),
        (f"Tu as promis, hein : « {STALE_QUOTE} »", WALK_REPLIES, False),
        ("Je repense à ce détail. La clé est bleue.", [], True),
        # A quote the hook clipped is still the learner's.
        ("Tu as promis : « Je viens samedi… »", ["Je viens samedi avec Gus."], True),
    ],
)
def test_guillemets_hold_only_what_the_learner_wrote_here(hook, said, holds):
    assert story_teaser.teaser_quotes_only_said(hook, said) is holds


def test_a_promise_the_learner_wrote_clean_is_quoted():
    quote = "Je viens samedi avec Gus."
    row = {**STALE_ROW, "text_fr": "Venir samedi avec Gus.", "source_quote": quote}
    hook = _hook({"commitments": [row]}, said=[quote], clean=[quote])
    assert f"« {quote} »" in hook["text_fr"]
    assert hook["open_fr"].endswith("?")


def test_a_promise_that_needed_correcting_is_told_never_quoted():
    """#445: the walk's raw «Je viens tard samedi, ca va» came back in guillemets, a minute
    after the scene had corrected it."""

    raw = "Oui, je parle avec Gus samedi, ca va"
    row = {**STALE_ROW, "text_fr": "Parler avec Gus samedi.", "source_quote": raw}
    hook = _hook({"commitments": [row]}, said=[raw], clean=[])
    assert "«" not in hook["text_fr"] and "ca va" not in hook["text_fr"]
    assert hook["open_fr"] == "Parler avec Gus samedi : c'est toujours d'accord ?"


@pytest.mark.parametrize(
    ("restated", "wrote", "told"),
    [
        ("Apporter du pain dimanche.", "Je vais apporter du pain dimanche", "Apporter du pain dimanche."),
        # A clause, a person, a number the learner never wrote, an invention: not told.
        ("Je serai chez moi après quatorze heures.", "Je rentre après deux heures", None),
        ("Rentrer après quatorze heures.", "Je rentre après deux heures", None),
        ("Rentrer à 14h.", "Je rentre à 2h", None),
        ("Parler à ma mère.", "Je parle à ma mère", None),
        ("Vendre la bouillotte.", "Je viens samedi", None),
    ],
)
def test_a_promise_is_told_only_when_it_is_safe(restated, wrote, told):
    assert story_teaser.told_promise(restated, wrote) == told


def test_tomorrow_is_a_whole_question_and_not_a_prefix_of_the_hook():
    """#466, and the review of #530: the line itself is checked, on a ten-word fact."""

    hook = _hook({"planted": [WALK_PLANT]}, character_id="margaux_barman")
    tomorrow = hook["open_fr"]
    assert tomorrow.endswith("?") and len(tomorrow.split()) > 3
    assert "Margaux range une lettre sans nom dans le tiroir du comptoir." in tomorrow
    assert hook["text_fr"].endswith(tomorrow) and not hook["text_fr"].startswith(tomorrow)


@pytest.mark.parametrize("register", ["tu", "vous"])
@pytest.mark.parametrize("character", ["marin_leveque", "lila_bonnet", "margaux_barman", "romy_tremblay", None])
def test_every_voice_and_every_variant_ends_the_hook_on_its_question(register, character):
    row = {"ref": "p", "kind": "plant", "text_fr": WALK_PLANT["text_fr"], "characters": []}
    thread = {"ref": "s1:0", "kind": "thread", "text_fr": "Qui était Odile, et pourquoi est-elle partie ?", "characters": []}
    for candidate in (row, thread):
        for variant in range(2):
            text = engine.compose_teaser(candidate, character_id=character, register=register, variant=variant)
            assert text.endswith("?"), text


def test_a_detail_too_long_to_say_whole_is_not_the_hook():
    """Never clipped mid-fact: the next open row speaks, or nothing does."""

    long_plant = {**WALK_PLANT, "text_fr": "Margaux range une lettre sans nom dans le tiroir du comptoir, à côté de la caisse, sous les vieux tickets."}
    assert _hook({"planted": [long_plant]}) is None


# ---------------------------------------------------------------------------
# The writer's question
# ---------------------------------------------------------------------------

SCENE = (
    "Lila revient avec une pizza. Margaux, Gus, Camille Marchand, M. Marchand. La lettre, la vérité, le Mistral. "
    "Tu as vu la lettre ? Trois ans. Le 8 mars."
)


@pytest.mark.parametrize(
    "question",
    [
        # What a writer might well write: all of it must pass. Any firing here is the
        # class of bug that closed #600 and #631.
        "Qui a vraiment écrit cette lettre ?",
        "Et la vérité, c'est pour quand ?",
        "Que va dire Lila à Margaux demain ?",
        "Pourquoi Lila cache-t-elle cette lettre ?",
        "M. Marchand sait-il pour la lettre ?",
        "Le Mistral, tu le gardes ou pas ?",
        "Que va faire Margaux de cette lettre ?",
        "Est-ce que la vérité change quelque chose ?",
        "Le 8 mars, qui sera encore là ?",
    ],
)
def test_a_natural_question_is_kept(question):
    assert story_teaser.question_problem(question, known=SCENE) is None


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("Dis, j'y repense…", "tomorrow_not_a_question"),
        ("La lettre est là.", "tomorrow_not_a_question"),
        ("Tu as vu ? La lettre est là, non ?", "tomorrow_not_one_sentence"),
        ("Et Lila ?", "tomorrow_length"),
        ("Pourquoi est-ce que Lila et Margaux ne disent jamais rien sur cette lettre ?", "tomorrow_length"),
        ("Tu as dit « je pars », et la lettre ?", "tomorrow_quotes"),
        ("La lettre est-elle chez Dupont ce soir ?", "tomorrow_brings_in_new_fact"),
        ("Le 12 avril, que fait Lila ?", "tomorrow_brings_in_new_fact"),
        ("Pourquoi les dragons volent-ils si haut ?", "tomorrow_off_the_scene"),
    ],
)
def test_a_question_that_does_not_hold_is_dropped_with_its_reason(question, code):
    assert story_teaser.question_problem(question, known=SCENE) == code


def test_a_question_the_learner_answered_is_not_tomorrows():
    ledger = scene_ledger.build(
        opening_line_fr="Tu veux partager la pizza avec moi ?",
        history=[{"learner": WALK_REPLIES[0], "character": "D'accord."}],
    )
    known = SCENE + " pizza partager"
    assert story_teaser.question_problem("Tu veux partager la pizza avec moi ?", known=known, ledger=ledger) == "tomorrow_already_answered"


def test_the_writers_question_leads_the_hook():
    hook = _hook(
        {"planted": [WALK_PLANT]}, question="Qui a vraiment écrit cette lettre ?", said=WALK_REPLIES, clean=[]
    )
    assert hook["open_fr"] == "Qui a vraiment écrit cette lettre ?"
    assert hook["text_fr"] == "Toi, tu me caches quelque chose… Qui a vraiment écrit cette lettre ?"
    assert hook["kind"] == "question" and hook["date"] == TODAY


def test_the_same_question_is_not_asked_two_days_running():
    question = "Qui a vraiment écrit cette lettre ?"
    first = _hook({"planted": [WALK_PLANT]}, question=question)
    live = {"planted": [WALK_PLANT], "teasers": engine.teasers_after({}, first)}
    second = _hook(live, question=question, date="2026-11-10")
    assert second is not None and second["kind"] == "plant"


def test_with_no_writer_the_scenes_own_open_question_stands():
    """The model down: what a character asked and nobody answered is still open."""

    ledger = scene_ledger.build(
        opening_line_fr="Bonsoir.", history=[{"learner": "Bonsoir.", "character": "Tu as vu la lettre sur le comptoir ?"}]
    )
    assert story_teaser.question_left_open(ledger) == "Tu as vu la lettre sur le comptoir ?"
    assert story_teaser.question_left_open({"still_open": [{"by": "learner", "kind": "question", "text_fr": "Et toi, tu viens samedi ?"}]}) is None
    assert story_teaser.question_left_open(None) is None


def _ending(question):
    """A story lane's answer on the walk of 4 Nov's real payload, through its own guards."""

    case = next(row for row in harness.load_cases(["story-a1-margaux-off-script"]))
    payload = harness._with_ledger(json.loads(json.dumps(case.input["payload"])))
    tutor = story_lanes.TutorVerdict(**case.input["tutor"])
    voice = story_lanes.VoiceReply(**case.input["voice"])
    story = story_lanes.StoryTurn(
        **{**case.answers["StoryTurn"][0]["content"], "tomorrow_question_fr": question}
    )
    return story_lanes.merged_turn(tutor, voice, story), payload


def test_a_good_question_comes_through_the_ending_guards():
    turn, payload = _ending("Qui a vraiment écrit cette lettre ?")
    story_lanes.validate_story(turn, payload)
    assert turn.tomorrow_question_fr == "Qui a vraiment écrit cette lettre ?"


def test_a_gender_guess_costs_the_question_and_not_the_ending():
    """Nothing about tomorrow's line may cost the learner their ending."""

    turn, payload = _ending("Tu es prête pour la lettre ?")
    story_lanes.validate_story(turn, payload)
    assert turn.tomorrow_question_fr == ""
    assert turn.resolution_fr == "Bon. Ton dinosaure peut garder la lettre pour ce soir."


def test_a_spoiler_costs_the_question_and_not_the_ending(monkeypatch):
    def spoiler(texts, payload):
        if any("Berlin" in text for text in texts):
            raise engine.StoryUnavailable("season_spoiler")

    monkeypatch.setattr(story_lanes.lane_guards, "check_season_spoiler", spoiler)
    turn, payload = _ending("Lila part-elle pour Berlin ?")
    story_lanes.validate_story(turn, payload)
    assert turn.tomorrow_question_fr == ""
    assert turn.resolution_fr


# ---------------------------------------------------------------------------
# An authored day
# ---------------------------------------------------------------------------


def test_a_tentpole_keeps_its_own_line_and_tomorrow_prints_the_closers_question():
    context = {"season": {"kind": "tentpole", "ending": {"text_fr": "Trois ans de mensonges. Et maintenant, toi. À suivre…"}, "position": {"key": "t4.a"}}}
    plain = runtime.season_teaser(context, date=TODAY)
    assert plain["text_fr"].startswith("Trois ans") and "open_fr" not in plain
    asked = runtime.season_teaser(context, date=TODAY, question="Que fais-tu de ces trois ans ?")
    assert asked["open_fr"] == "Que fais-tu de ces trois ans ?"
    assert asked["text_fr"] == plain["text_fr"]


def test_the_closers_question_reaches_the_settle(monkeypatch):
    from tests.test_authored_closing_558 import _page
    from tests.test_season_story_qa import _scenario

    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    scenario = _scenario(_page("t4", "a"))
    turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    reply = turns[-1]["replies"][0]
    choice = ReplyChoice(reply_id=reply["id"], confidence=0.9, clear=True)
    written = SceneClosing(tomorrow_question_fr="Que fais-tu de ces trois ans ?")

    def proposal(reading):
        return runtime._closing_proposal(
            engine, None, None, scenario, turns=turns, routed=[("Oui.", reply)], final_choice=choice, reading=reading
        )

    assert proposal(written)["tomorrow_question_fr"] == "Que fais-tu de ces trois ans ?"
    # A card tapped, or the model down: the proposal says nothing, the page's line stands.
    assert "tomorrow_question_fr" not in proposal(None)
    # As ``settle_resolution`` reads it.
    details = proposal(written)
    fields = {key: value for key, value in details.items() if key in engine.SemanticTurn.model_fields}
    assert engine.SemanticTurn.model_validate(fields).tomorrow_question_fr == "Que fais-tu de ces trois ans ?"


# ---------------------------------------------------------------------------
# What the surfaces read
# ---------------------------------------------------------------------------


def _recap_of(teaser):
    user = SimpleNamespace(id="u", native_language="en")
    journey = SimpleNamespace(id="j", scenario_snapshot={"character_id": "lila_bonnet", "character_name": "Lila"})
    return achievement_recap.recap_teaser(user, journey, {"next_teaser": teaser})


def test_the_recap_carries_what_stays_open_and_the_whole_hook():
    long_hook = "Toi, tu me caches quelque chose… " + "x" * 170 + " Pourquoi ?"
    recap = _recap_of({"text_fr": long_hook, "open_fr": "Qui a écrit la lettre ?", "character_id": "lila_bonnet"})
    assert recap["open_fr"] == "Qui a écrit la lettre ?"
    assert recap["text_fr"].endswith("Pourquoi ?"), "the clip kept the question"


def test_a_recap_with_nothing_open_says_nothing_about_it():
    assert "open_fr" not in _recap_of({"text_fr": "Deux clés pour la même porte.", "kind": "season"})
