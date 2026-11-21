"""P8 (fifth commit): the story never decides for the learner, and its hook can be read.

Every fixture is what the second real-model walk of 17 Nov (integration branch, Sonnet
5.5 writer) stored in its databases (``graphic_novel_scenes.recap_payload``,
``graphic_novel_panels.overlay_payload``, ``serial_threads.state.living_story``):
A1 learner (German), B1 learner (English). Fake providers only: nothing here calls a model.
"""

from __future__ import annotations

import inspect
from datetime import date
from types import SimpleNamespace

from app.services import living_story as engine
from app.services import story_lanes, story_split

# ---------------------------------------------------------------------------
# 1. The ending writer: A1 day 3 («Chez le notaire, sous la pluie»)
# ---------------------------------------------------------------------------

#: The scene's page_thread: what Lila asked and what the learner answered, verbatim.
A1_DAY3_PAYLOAD = {
    "scene": {"opening_line_fr": "Tu pars toujours mercredi ?"},
    "history": [
        {"learner": "Je ne sais pas. Il a un chat dans le appartement.",
         "character": "Tu ne sais pas encore… D’accord, le chat prend toute la place dans cette histoire !"},
        {"learner": "Oui. Le chat est petit. Je reste peut-être jeudi.",
         "character": "Ah, mercredi, alors… Le chat est petit, mais il décide ?"},
    ],
    "learner_text": "Non, le chat ne decide pas. Demain, je veux parler à Gus.",
    "story": {"control_language": "de"},
}
#: What the ending lane returned (recap_payload) and filed as the day's record (summary_fr).
A1_DAY3_ENDING = SimpleNamespace(
    resolution_fr="Alors, tu pars mercredi. Demain, tu veux parler à Gus. Moi, je garde ce café pour toi.",
    summary_native=(
        "Du fliegst am Mittwoch nach Hause und möchtest morgen mit Gus sprechen. Lila behält das im Kopf "
        "und reste avec toi dans l’attente des prochaines nouvelles."
    ),
    callback_fr="Le chat ne décide pas ; tu pars mercredi.",
)


def test_the_ending_never_says_tu_pars_when_the_learner_said_peut_etre():
    turn = SimpleNamespace(**vars(A1_DAY3_ENDING))
    taken = story_lanes.keep_decisions_theirs(turn, A1_DAY3_PAYLOAD)
    assert taken, "«Alors, tu pars mercredi.» was served"
    assert turn.resolution_fr == "Demain, tu veux parler à Gus. Moi, je garde ce café pour toi."
    assert turn.callback_fr == "Le chat ne décide pas."
    # The summary retells the whole ending; with a decision in it, it says what was said.
    assert turn.summary_native == "Du hast gesagt: „Non, le chat ne decide pas. Demain, je veux parler à Gus.“"
    assert "tu pars" not in engine.what_happened(turn).casefold()


def test_a_decision_the_learner_made_is_kept():
    """B1 day 4 and day 5: «j'ai déjà décidé de ne pas vendre», «je ne les ai pas signés»."""

    payload = {
        "scene": {"opening_line_fr": "Alors, comment tu vas, vraiment ?"},
        "history": [{"learner": "Avant ton arrivée, j'ai déjà décidé de ne pas vendre, alors viens avec moi demain.",
                     "character": "Tu as raison."}],
        "learner_text": "Oui, il me l'a proposé avant-hier. Il avait déjà préparé les papiers, mais je ne les ai pas signés.",
        "story": {"control_language": "en"},
    }
    turn = SimpleNamespace(
        resolution_fr="D'accord, Camille t'a proposé de l'argent et tu as refusé de vendre. Tu n'as pas signé.",
        summary_native="Tu ne veux pas vendre, mais la question de la clé reste à poser.",
        callback_fr="Ta décision de ne pas vendre est claire.",
    )
    before = dict(vars(turn))
    assert story_lanes.keep_decisions_theirs(turn, payload) == []
    assert vars(turn) == before
    # A season fact said as a fact is not a decision.
    fact = SimpleNamespace(resolution_fr="Ton billet de retour est pour mercredi.", summary_native="", callback_fr="")
    assert story_lanes.keep_decisions_theirs(fact, A1_DAY3_PAYLOAD) == []


def test_the_ending_writer_is_told_and_guarded():
    assert "never say the learner will leave, stay, sell, keep, sign or change their date" in story_lanes.STORY
    assert "keep_decisions_theirs(turn, payload)" in inspect.getsource(story_lanes.validate_story)


# ---------------------------------------------------------------------------
# 1. The page's observation: ``decides_for_learner`` (logged false on every page)
# ---------------------------------------------------------------------------

def _page(opening: str, *panels: list[str]) -> dict:
    return {"opening_line_fr": opening,
            "panels": [{"narration_fr": "", "dialogue": [{"text_fr": line} for line in lines]} for lines in panels]}


#: A1 day 4, «La soupe et le radiateur» (hook: the learner's plan, «Demain, tu veux parler à Gus.»).
A1_DAY4_PAGE = _page(
    "Comment tu vas, vraiment, dans ce studio froid ?",
    ["Vous voulez lui parler de quoi, demain ?", "Il voulait te parler aujourd’hui, Gus."],
    ["La chaleur est partie. Ma soupe, elle, est là.", "Le radiateur a choisi son camp."],
    ["La valise part mercredi. Le radiateur, lui, non.", "Ma grand-mère disait : une soupe réchauffe même les murs."],
)
#: A1 day 5, «Un chauffage et un appel» (hook «Le billet»; the brief's learner_decides: the ticket).
A1_DAY5_PAGE = _page(
    "Pourquoi tu changes la date, Jonas ?",
    ["Un chauffage, Jonas. Du château.", "J'habite à côté. Nous dînons souvent ensemble."],
    [],
    ["Jeudi, 18 h : Camille vient avec Solvel. Maître Vasseur veut te voir.", "Mercredi, c'est fini. On appelle la compagnie."],
)
#: B1 day 5, «Un radiateur et un billet»: the last panel's caption.
B1_DAY5_PAGE = _page(
    "Alors, qu'est-ce que tu as dit à l'agent comme raison ? C'est la vraie ?",
    ["Un radiateur qui meurt le jour du billet. Si ce n'est pas un signe...", "C'est un signe que tu n'es pas plombier, Marin."],
    ["Tu as dit que tu parlerais à Gus devant tout le monde. Il sera au Mistral ce soir. Mais d'abord, la compagnie : appelle aujourd'hui."],
    ["Dis-lui : « Mon billet est fatigué. »", "Dis juste : « Je voudrais changer ma date, s'il vous plaît. »"],
    ["Mercredi 2 décembre. C'est confirmé.", "Douze sur vingt, pour l'appel."],
)
TICKET_OPEN = [{"flag": "user.return_ticket", "now": "mercredi 18 novembre", "if_the_learner_decides_nothing": "mercredi 2 décembre"}]
BEAT_HOOK = {"text_fr": "Le billet", "date": "2026-11-21", "source": "beat"}
PLAN_HOOK = {"text_fr": "Demain, tu veux parler à Gus.", "date": "2026-11-20", "source": "plan"}


def test_the_three_logged_pages_are_counted_as_deciding_for_the_learner():
    assert engine.hook_observation(PLAN_HOOK, A1_DAY4_PAGE)["decides_for_learner"] is True
    assert engine.hook_observation(BEAT_HOOK, A1_DAY5_PAGE, open_choices=TICKET_OPEN)["decides_for_learner"] is True
    assert engine.hook_observation(BEAT_HOOK, B1_DAY5_PAGE, open_choices=TICKET_OPEN)["decides_for_learner"] is True


def test_a_page_that_asks_and_states_facts_does_not_decide():
    """B1 day 4: the ticket said as what it says («ton billet dit encore le 18»), and the
    tentpole's fact («Ton billet de retour est pour mercredi prochain.»)."""

    page = _page(
        "Alors, comment tu vas, vraiment, ici ?",
        ["Je lui ai dit dans l'escalier : tu veux lui parler de la clé.", "Odile ne l'a jamais prêtée, cette clé."],
        ["Et ton billet dit encore le 18. Il faut le changer avant mercredi."],
        ["Ton billet de retour est pour mercredi prochain.", "Tu pars toujours mercredi ?"],
    )
    assert engine.hook_observation(PLAN_HOOK, page, open_choices=TICKET_OPEN)["decides_for_learner"] is False


def test_the_observation_reads_today_s_open_choices_from_the_brief():
    context = {"season_script": {"brief": {"today": {"learner_decides": TICKET_OPEN}}}}
    assert engine._open_choices(context) == TICKET_OPEN


# ---------------------------------------------------------------------------
# 1. The brief: a beat that needs the learner's choice asks for it
# ---------------------------------------------------------------------------

def test_the_ticket_day_s_brief_asks_instead_of_presupposing():
    from app.services.season.director import gap_brief
    from app.services.season.epilogue import position_for
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from tests.test_p8_page_answers_hook import _season_after

    season = load_season("s1")
    state = _season_after(2)
    pos = position_for(season, state, today=date(2026, 11, 22))
    today = gap_brief(season, pos, flags=effective_flags(season, state, seed="p8"), state=state, seed="p8", band="A1")["today"]
    premise, beat = today["required_premise"], today["beat"]
    assert premise["turn"].startswith("The learner decides this in their reply: ask what they want to do about user.return_ticket")
    assert "why you are changing the date" not in premise["turn"]
    assert premise["change"].startswith("Open until the learner answers: user.return_ticket")
    assert beat["after"].startswith("Open until the learner answers: user.return_ticket")
    # Season facts are facts, never intentions: the planner and the director are told.
    assert "never «tu pars mercredi»" in story_split.PLANNER.replace("\n  ", " ")
    assert "never «tu" in engine.DIRECTOR


# ---------------------------------------------------------------------------
# 3. «Précédemment»: the day's own line, without what the learner never decided
# ---------------------------------------------------------------------------

#: The A1 life's stored events for days 3–5 (``living_story.events``).
A1_EVENTS = [
    {"date": "2026-11-20", "scene_id": "140196c4", "title_fr": "Chez le notaire, sous la pluie",
     "summary_fr": "Le chat ne décide pas ; tu pars mercredi.",
     "source_quotes": ["Je reste peut-être jeudi.", "Non, le chat ne decide pas."]},
    {"date": "2026-11-21", "scene_id": "406da9b1", "title_fr": "La soupe et le radiateur",
     "summary_fr": "Tu hast gesagt, dass dir kalt ist; Marin hat eine Suppe und eine Wärmflasche gebracht.",
     "did_fr": "Tu parleras avec Gus après la soupe."},
]


def test_previously_never_carries_a_decision_forward():
    lines = engine.previously_lines({"events": A1_EVENTS})
    assert lines[0] == "La soupe et le radiateur : Tu parleras avec Gus après la soupe.", lines
    assert lines[1] == "Le chat ne décide pas.", lines
    assert not any("tu pars" in line.casefold() for line in lines)
    # The day before, alone: its own title, its own line.
    assert engine.previously_lines({"events": A1_EVENTS[:1]})[0] == "Chez le notaire, sous la pluie : Le chat ne décide pas."


# ---------------------------------------------------------------------------
# 2. A hook from the beat is a line the learner can read
# ---------------------------------------------------------------------------

def _beat(gap, premise):
    return next(row for row in gap.days if row.premise == premise)


def test_the_three_walk_hooks_are_whole_readable_lines():
    from app.services.season.director import beat_hook
    from app.services.season.format import load_season
    from app.services.story_teaser import readable_hook

    gap = load_season("s1").gaps["g1"]
    not_romy = lambda cast_id: cast_id != "romy_tremblay"  # noqa: E731 - gap 1, before Romy's page

    billet = beat_hook(gap, _beat(gap, "le_billet"), met=not_romy)
    romy = beat_hook(gap, _beat(gap, "romy_enquete"), met=not_romy)
    meme = beat_hook(gap, _beat(gap, "la_meme_chose"), met=not_romy)
    assert billet["text_fr"] == "Demain, Lila te parle du billet."
    assert romy["text_fr"] == "Demain, une journaliste québécoise est là et elle enquête."
    assert meme["text_fr"] == "Demain, Margaux te demande : « La même chose ? »"
    for hook in (billet, romy, meme):
        assert readable_hook(hook["text_fr"]) and len(hook["text_fr"].split()) >= 4, hook
        assert "Romy" not in hook["text_fr"]
    # The bare titles the walk filed are not readable hooks.
    assert not any(readable_hook(title) for title in ("Le billet", "Romy enquête", "La même chose ?"))
    # Once Romy is met, her name.
    assert beat_hook(gap, _beat(gap, "romy_enquete"))["text_fr"] == "Demain, Romy est là et elle enquête."


def test_a_beat_hook_carries_the_mother_tongue_where_the_season_has_every_part():
    from app.services.season.director import beat_hook
    from app.services.season.format import load_season

    gap = load_season("s1").gaps["g1"]
    billet = beat_hook(gap, _beat(gap, "le_billet"))
    assert billet["text_native"] == {
        "de": "Morgen spricht Lila mit dir über „Le billet“.",
        "en": "Tomorrow Lila talks to you about “Le billet”.",
    }
    assert beat_hook(gap, _beat(gap, "la_meme_chose"))["text_native"]["de"] == "Morgen fragt dich Margaux: „La même chose ?“"
    # «enquête» has no translation in the season's data: no native line is made up.
    assert "text_native" not in beat_hook(gap, _beat(gap, "romy_enquete"))


def test_the_filed_beat_hook_keeps_its_native_line(monkeypatch):
    from tests.test_p8_page_answers_hook import NOTARY_DAY, _settle_on_gap_day

    teaser, _rows, _live = _settle_on_gap_day(monkeypatch, gap_days=2, question=None, **NOTARY_DAY)
    assert teaser["text_fr"] == "Demain, Lila te parle du billet."
    assert teaser["text_native"]["en"] == "Tomorrow Lila talks to you about “Le billet”."
    assert teaser["source"] == "beat"
