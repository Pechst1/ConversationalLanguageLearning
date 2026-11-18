"""P8 · Today's page answers yesterday's hook (experience review of 17 Nov, finding 5).

Walk of 17 Nov (B1, days 3–6): «Que décideras-tu pour ton vol ?» closed day 3 and day 4
never asked it; «Précédemment» still opened on day 1's «Le mauvais accueil» on day 6;
days 3, 4 and 5 were all headlined «Le Mistral», the café's name.
"""

# ruff: noqa: F811 - pytest fixtures imported from the story-split tests
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.services import living_story as engine
from app.services import story_split
from app.services.journey_contracts import InputMode
from app.services.season.director import StoryReview
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.test_story_split import (  # noqa: F401 - fixtures
    _context,
    _learner_on_gap_day,
    _plan,
    assembled_client,
    clock,
    journey_enabled,
    split_on,
)

HOOK = "Que décideras-tu pour ton vol ?"
TEASER = {
    "text_fr": f"Lila te regarde. {HOOK}",
    "open_fr": HOOK,
    "date": "2026-11-19",
    "character_id": "lila_bonnet",
}


def _played(*dates: str) -> list[dict]:
    return [
        {
            "id": f"journey:j{n}:story",
            "scene_id": f"scene-{n}",
            "summary_fr": f"Jour {n}.",
            "date": date,
        }
        for n, date in enumerate(dates, start=2)
    ]


def _with_hook(context: dict) -> dict:
    live = {"next_teaser": TEASER, "events": _played("2026-11-18", "2026-11-19")}
    return {**context, "yesterday_hook": engine.yesterday_hook(live)}


# -- 1. the hook reaches the writer ------------------------------------------------


def test_the_hook_is_the_last_played_day_s_and_only_that():
    hook = engine.yesterday_hook(
        {"next_teaser": TEASER, "events": _played("2026-11-18", "2026-11-19")}
    )
    assert hook == {
        "text_fr": TEASER["text_fr"],
        "question_fr": HOOK,
        "date": "2026-11-19",
        "character_id": "lila_bonnet",
        "source": "scene",
    }
    # First day: nothing played. A hook older than the last played day: that day ended without one.
    assert engine.yesterday_hook({"next_teaser": TEASER, "events": []}) is None
    assert (
        engine.yesterday_hook(
            {"next_teaser": TEASER, "events": _played("2026-11-19", "2026-11-20")}
        )
        is None
    )
    assert engine.yesterday_hook({"events": _played("2026-11-19")}) is None


def _store_hook(db_session, user) -> None:
    thread = engine._active_thread(db_session, user)
    state = dict(thread.state or {})
    live = dict(state.get(engine.STATE_KEY) or {})
    events = list(live.get("events") or [])
    last = max(
        [str(e.get("date")) for e in events if e.get("scene_id") and e.get("date")]
        or ["2026-11-19"]
    )
    live["events"] = [
        *events,
        {
            "id": "journey:p8:story",
            "scene_id": "scene-p8",
            "summary_fr": "Le vol reste à décider.",
            "date": last,
        },
    ]
    live["next_teaser"] = {**TEASER, "date": last}
    state[engine.STATE_KEY] = live
    thread.state = state
    db_session.commit()


def test_the_planner_and_the_author_read_yesterday_s_hook(
    assembled_client, db_session, journey_enabled, clock, split_on
):
    split_on.critic_refusals_left = 0
    user = _learner_on_gap_day(assembled_client, db_session)
    _store_hook(db_session, user)
    with engine.written_ahead_of_time():
        engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    planner = next(payload for schema, payload in split_on.calls if schema == "PagePlan")
    author = next(payload for schema, payload in split_on.calls if schema == "PageText")
    assert planner.get("yesterday_hook", {}).get("question_fr") == HOOK
    assert author["plan"].get("yesterday_hook", {}).get("question_fr") == HOOK


def test_the_one_call_director_reads_yesterday_s_hook(
    assembled_client, db_session, journey_enabled, clock, split_on
):
    user = _learner_on_gap_day(assembled_client, db_session)
    _store_hook(db_session, user)
    engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    director = next(payload for schema, payload in split_on.calls if schema == "SceneDraft")
    assert (director.get("yesterday_hook") or {}).get("question_fr") == HOOK


def test_a_day_about_yesterday_s_hook_may_come_back_to_yesterday_s_question():
    """Third commit: no plan field and no plan refusal; yesterday's question is the hook's."""

    context = _with_hook(_context())
    yesterday = context["recent_situations"][-1]["objective_native"]
    assert story_split.plan_issue(_plan(task=yesterday), context) is None
    assert "already asked" in (story_split.plan_issue(_plan(task=yesterday), _context()) or "")
    assert "takes_up_hook" not in story_split.PagePlan.model_fields


# -- the critic: back to main's prompt; the hook never refuses a page ----------------


def _page(
    first: str, second: str, last_line: str = "Regarde.", opening: str = "Tu restes ce soir ?"
) -> dict:
    return {
        "title_fr": "Lila et la valise",
        "premise_fr": "Le studio, le matin.",
        "objective_native": "Lila wants to know if you stay tonight.",
        "character_id": "lila_bonnet",
        "location_id": "user_apartment",
        "opening_line_fr": opening,
        "panels": [
            {"narration_fr": first, "dialogue": []},
            {"narration_fr": "", "dialogue": [{"character_id": "lila_bonnet", "text_fr": second}]},
            {"narration_fr": "Il pleut.", "dialogue": []},
            {
                "narration_fr": "",
                "dialogue": [{"character_id": "lila_bonnet", "text_fr": last_line}],
            },
        ],
    }


GOOD_REVIEW = StoryReview.model_validate(
    {
        "hook": True,
        "stakes": True,
        "value_turn": True,
        "meaningful_change": True,
        "advances_thread": True,
    }
)


def _review(monkeypatch, context: dict, page: dict) -> tuple[dict | None, list[dict]]:
    sent: list[dict] = []

    def fake_call(system, payload, schema, record, **kwargs):
        sent.append({"system": system, **payload})
        return GOOD_REVIEW, None

    monkeypatch.setattr(engine, "_json_call", fake_call)
    reviews: list[dict] = []
    review = engine._season_story_review(context, reviews)
    outcome = review(
        SimpleNamespace(**page, model_dump=lambda mode=None: page), deadline=0, record=None
    )
    return outcome, sent


def _season_context() -> dict:
    return _with_hook(_context())


def test_a_page_that_never_touches_the_hook_is_accepted_and_observed_as_no(monkeypatch):
    """Third commit (real-model check 2, 17 Nov): the hook refused five night runs in ten
    and did not buy the behaviour. It never refuses a page; it is counted."""

    page = _page("Le studio est froid.", "Tu as faim ?")
    outcome, sent = _review(monkeypatch, _season_context(), page)
    assert outcome is not None and outcome["accepted"] is True, outcome
    assert "yesterday_hook" not in sent[0], "the critic is not asked about the hook"
    assert "yesterday_hook" not in sent[0]["system"] and "takes_up_hook" not in sent[0]["system"]
    assert "takes_up_hook" not in StoryReview.model_fields
    observed = engine.hook_observation(_season_context()["yesterday_hook"], page)
    assert observed == {"hook_source": "scene", "hook_taken_up": "no", "hook_repeats": False, "decides_for_learner": False}


@pytest.mark.parametrize(
    "page, taken",
    [
        (_page("Lila tient ton billet.", "Alors, ton vol ? Mercredi ou pas ?"), "early"),
        (_page("Le studio est froid.", "Ton vol, on en parle plus tard : d'abord le radiateur."), "set_aside"),
        (_page("Le soir. Marin frappe.", "Tu manges la soupe.", last_line="Lila dit : ton vol de mercredi."), "late"),
        (_page("Le soir.", "Tu manges ?", opening="Ton vol de mercredi : tu le gardes ?"), "early"),
    ],
    ids=["panel-2", "set-aside", "panel-4", "as-the-question"],
)
def test_every_take_up_is_accepted_and_counted(monkeypatch, page, taken):
    outcome, _sent = _review(monkeypatch, _season_context(), page)
    assert outcome is not None and outcome["accepted"] is True
    assert engine.hook_observation(_season_context()["yesterday_hook"], page)["hook_taken_up"] == taken


def test_a_page_that_ignores_the_hook_is_written_once_and_the_observation_says_no(
    assembled_client, db_session, journey_enabled, clock, split_on
):
    """The guard of point 1: on a day with a hook, the fake writer's page (a box of photos,
    never the flight) is accepted on the first attempt: one plan, one page, one reading."""

    split_on.critic_refusals_left = 0
    user = _learner_on_gap_day(assembled_client, db_session)
    _store_hook(db_session, user)
    with engine.written_ahead_of_time():
        brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert not isinstance(brief, engine.ContentUnavailable), brief
    schemas = [schema for schema, _ in split_on.calls]
    assert schemas.count("PagePlan") == 1 and schemas.count("PageText") == 1, schemas
    assert schemas.count("StoryReview") == 1, schemas
    assert brief.story_context[engine.HOOK_OBSERVATION_KEY]["hook_taken_up"] == "no"


def _night_calls(assembled_client, db_session, split_on, *, hook: bool, refusals: int) -> list[str]:
    split_on.calls.clear()
    split_on.plans.clear()
    split_on.critic_refusals_left = refusals
    user = _learner_on_gap_day(assembled_client, db_session)
    if hook:
        _store_hook(db_session, user)
    with engine.written_ahead_of_time():
        engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    model = ("PagePlan", "PageText", "PageAids", "SceneDraft", "StoryReview")
    return [schema for schema, _ in split_on.calls if schema in model]


#: The writer and critic calls of a night run on ``origin/main`` (d1486e6c), measured with
#: this fake provider on a day without a hook: a critic that accepts, and one that refuses
#: every page it reads.
MAIN_NIGHT_CALLS = {0: 4, 99: 8}


@pytest.mark.parametrize("refusals", [0, 99], ids=["critic-accepts", "critic-refuses-everything"])
def test_a_hook_costs_no_writer_or_critic_call(
    assembled_client, db_session, journey_enabled, clock, split_on, refusals
):
    """The guard of point 4 (check 2: a failed night run with a hook cost 2–3 minutes and
    US$0.30–0.45): at most as many writer and critic calls as main makes without one."""

    without = _night_calls(assembled_client, db_session, split_on, hook=False, refusals=refusals)
    with_hook = _night_calls(assembled_client, db_session, split_on, hook=True, refusals=refusals)
    assert len(without) == MAIN_NIGHT_CALLS[refusals], without
    assert len(with_hook) <= MAIN_NIGHT_CALLS[refusals], with_hook


def test_a_refused_plan_logs_its_reason(assembled_client, db_session, journey_enabled, clock, split_on):
    """Check 2's server log read «story_split: plan refused (%s)»: loguru formats with «{}»."""

    from loguru import logger

    lines: list[str] = []
    sink = logger.add(lambda message: lines.append(str(message)), format="{message}")
    try:
        split_on.stranger_once = True
        split_on.critic_refusals_left = 0
        user = _learner_on_gap_day(assembled_client, db_session)
        with engine.written_ahead_of_time():
            engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    finally:
        logger.remove(sink)
    refused = [line for line in lines if "plan refused" in line]
    assert refused and "%s" not in refused[0] and "odile" in refused[0], refused


# -- 2. «Précédemment» --------------------------------------------------------------


def _day_six_live() -> dict:
    events = [
        {
            "id": "journey:j1:story",
            "scene_id": "scene-1",
            "summary_fr": "Tu arrives au Mistral.",
            "date": "2026-11-17",
            "chapter_id": "ch-1",
            "title_fr": "Le mauvais accueil",
        },
        {
            "id": "journey:j2:story",
            "scene_id": "scene-2",
            "summary_fr": "Camille montre la clé.",
            "date": "2026-11-18",
            "chapter_id": "ch-2",
            "title_fr": "La lettre",
        },
        {
            "id": "journey:j3:story",
            "scene_id": "scene-3",
            "summary_fr": "La notaire bloque la vente.",
            "date": "2026-11-19",
            "chapter_id": "ch-2",
            "title_fr": "Chez Maître Vasseur",
        },
        {
            "id": "journey:j4:story",
            "scene_id": "scene-4",
            "summary_fr": "Marin répare le radiateur.",
            "date": "2026-11-20",
            "chapter_id": "ch-2",
            "title_fr": "Le radiateur de Marin",
        },
        {
            "id": "journey:j5:story",
            "scene_id": "scene-5",
            "summary_fr": "Tu soupçonnes Gus ; Lila veut une preuve.",
            "date": "2026-11-21",
            "chapter_id": "ch-2",
            "title_fr": "Lila et Marin aident pour le vol",
        },
    ]
    return {
        "day_index": 5,
        "events": events,
        "chronicle": [
            {
                "id": "ch-1",
                "title_fr": "Le mauvais accueil",
                "resolved_fr": "Ta grand-mère t'a laissé le Mistral.",
                "day": 1,
            },
            {"kind": "season", "season": 1, "facts": ["La clé d'Odile est chez Margaux."]},
        ],
    }


def test_day_six_s_previously_names_the_last_played_day_not_day_one():
    lines = engine.previously_lines(_day_six_live(), chapter_id="ch-2")
    assert lines, "the box has lines"
    assert not lines[0].startswith("Le mauvais accueil")
    assert (
        lines[0] == "Lila et Marin aident pour le vol : Tu soupçonnes Gus ; Lila veut une preuve."
    )
    assert "Marin répare le radiateur." in lines
    assert len(lines) <= engine.PREVIOUSLY_LINES
    assert all(len(line) <= engine.PREVIOUSLY_LINE_CHARS for line in lines)


# -- 3. the page's headline ---------------------------------------------------------


@pytest.mark.parametrize("title", ["Le Mistral", "Au Mistral", "le mistral."])
def test_a_place_name_is_no_headline(title):
    context = _context()
    assert "place" in (engine.title_issue(title, context) or "")
    draft = SimpleNamespace(title_fr=title)
    with pytest.raises(engine.SoftRejection) as refused:
        engine._check_place_title(draft, context)
    assert str(refused.value) == "place_name_title"
    assert engine.title_issue("Margaux ferme le Mistral", context) is None


def test_a_headline_an_earlier_page_wears_after_folding_is_refused():
    context = {
        **_context(),
        "recent_situations": [{"title_fr": "Lila et la valise", "objective_native": "x"}],
    }
    assert "earlier page" in (engine.title_issue("LILA et la valise !", context) or "")


def test_the_author_is_asked_again_for_a_place_headline(
    assembled_client, db_session, journey_enabled, clock, split_on, monkeypatch
):
    split_on.critic_refusals_left = 0
    original = split_on._text
    titles = iter(["Le Mistral"])

    def text(source):
        page = original(source)
        return {**page, "title_fr": next(titles, page["title_fr"])}

    monkeypatch.setattr(split_on, "_text", text)
    user = _learner_on_gap_day(assembled_client, db_session)
    with engine.written_ahead_of_time():
        engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    texts = [payload for schema, payload in split_on.calls if schema == "PageText"]
    assert len(texts) >= 2, "the headline was asked for again"
    assert any("Le Mistral" in hint and "place" in hint for hint in texts[1]["previous_rejections"])
    plans = [schema for schema, _ in split_on.calls if schema == "PagePlan"]
    assert len(plans) == 1, "on the same plan"
    json.dumps(texts[1], ensure_ascii=False)


# ===================================================================================
# Second commit: the real-model check of 17 Nov (Sonnet 5.5, A1 de and B1 en, 5 days)
# ===================================================================================

# -- 1. ONE hook: the end card's promise is Home's, the push's and tomorrow's ---------

#: B1 day 4: the ending (end card) promised Gus and the key; Home showed the plan's hook.
B1_DAY4_ENDING = (
    "Je note que vous restez à Paris pour les papiers. Vos amis seront peut-être déçus, mais "
    "vous leur direz la vérité. Et demain, vous parlerez à Gus de la clé."
)
PLANNED = {
    "text_fr": "L'avenir du Mistral : le garder, le changer, ou le laisser partir ?",
    "character_id": "maitre_vasseur",
    "date": "2026-11-20",
    "ref": "contract:g2.notaire",
    "kind": "season",
}


def _respond(*lines: str) -> SimpleNamespace:
    return SimpleNamespace(
        kind="respond", private_task={"turns": [{"learner": line, "character": "…"} for line in lines]}
    )


def _settle_hook(monkeypatch, ending: str, *, live: dict | None = None, said=(), context=None):
    from app.services import scene_record

    monkeypatch.setattr(scene_record, "enabled", lambda: True)
    monkeypatch.setattr(engine, "_contract_hook", lambda *a, **k: dict(PLANNED))
    turn = SimpleNamespace(tomorrow_question_fr="", resolution_fr=ending, reply_fr="D'accord.", commitments=[])
    brief = SimpleNamespace(character_id="maitre_vasseur", story_context=context or {"draft": {"panels": []}})
    journey = SimpleNamespace(local_date=date(2026, 11, 20), steps=[_respond(*said)])
    return engine._hook_after_day(
        None, SimpleNamespace(id=1), live=live or {}, world_after={}, brief=brief, turn=turn,
        journey=journey, act=None, relationships={}, seed="p8",
    )


def test_the_end_card_s_promise_is_the_one_hook(monkeypatch):
    teaser, teasers = _settle_hook(
        monkeypatch, B1_DAY4_ENDING, said=["Demain, je veux parler à Gus de la clé."]
    )
    assert teaser is not None and "Gus" in teaser["text_fr"] and "clé" in teaser["text_fr"], teaser
    assert "avenir du Mistral" not in teaser["text_fr"], "Home's hook is not another line than the end card's"
    assert teasers[-1]["text_fr"] == teaser["text_fr"]
    # Tomorrow's page reads that same stored line.
    live = {"next_teaser": teaser, "events": [{"scene_id": "s4", "date": "2026-11-20", "summary_fr": "x"}]}
    assert engine.yesterday_hook(live)["text_fr"] == teaser["text_fr"]
    # An ending that names no tomorrow keeps the plan's hook.
    planned, _rows = _settle_hook(monkeypatch, "Je note que vous restez à Paris pour les papiers.")
    assert planned["ref"] == PLANNED["ref"]


# -- 2. a hook taken up moves: not the same question the next day --------------------

DAY3_Q = "Que fais-tu de ton vol de mercredi ?"
DAY4_Q = "Tu gardes ton vol de mercredi ?"


def _after_day3() -> dict:
    day3 = engine.next_teaser(
        {}, {}, character_id="lila_bonnet", register="tu", date="2026-11-19", seed="a1", question=DAY3_Q
    )
    assert day3 is not None and day3["open_fr"] == DAY3_Q
    return {"next_teaser": day3, "teasers": engine.teasers_after({}, day3)}


def test_the_flight_is_not_the_hook_a_second_day_running():
    """A1 days 3 and 4 both ended on the Wednesday flight; day 4 never put it off."""

    said = ["Je suis fatigué. Je vais lui dire merci pour la soupe.", "Oui. Demain, je vais lui téléphoner, à Lila."]
    day4 = engine.next_teaser(
        _after_day3(), {}, character_id="marin_leveque", register="tu", date="2026-11-20", seed="a1",
        question=DAY4_Q, said=said,
    )
    assert day4 is None or "vol" not in day4["text_fr"], day4


def test_a_hook_the_learner_put_off_comes_back_once_only():
    said = ["Je ne sais pas encore pour mon vol. Je réfléchis."]
    live = _after_day3()
    day4 = engine.next_teaser(
        live, {}, character_id="marin_leveque", register="tu", date="2026-11-20", seed="a1",
        question=DAY4_Q, said=said,
    )
    assert day4 is not None and day4["open_fr"] == DAY4_Q and day4.get("renewed") == 1, day4
    live5 = {"next_teaser": day4, "teasers": engine.teasers_after(live, day4)}
    day5 = engine.next_teaser(
        live5, {}, character_id="lila_bonnet", register="tu", date="2026-11-21", seed="a1",
        question="Tu prends ton vol mercredi ?", said=said,
    )
    assert day5 is None or "vol" not in day5["text_fr"], day5


# -- 3./4. late, waved away, decided for the learner: counted, never refused -------
# Third commit: commit 2 refused these pages (and marked a set-aside for the next day).
# Check 2 showed the refusals cost the night run and did not change the pages.

MISTRAL = {
    "text_fr": "Il faudra qu'on en parle. L'avenir du Mistral : le garder, le changer, ou le laisser partir ?",
    "question_fr": "L'avenir du Mistral : le garder, le changer, ou le laisser partir ?",
    "date": "2026-11-20",
}


def _marin_page(*second: str) -> dict:
    page = _page("Sixième étage. Le radiateur ne marche plus.", "x")
    page["panels"][1]["dialogue"] = [{"character_id": "marin_leveque", "text_fr": line} for line in second]
    return page


def test_a_hook_waved_away_in_one_line_is_served_and_counted_as_set_aside(monkeypatch):
    """B1 day 5: «Son avenir, tout ça. Pas ce soir.»"""

    page = _marin_page(
        "Margaux voulait que je te parle du Mistral. Son avenir, tout ça. Pas ce soir. Quand tu auras chaud, et tes papiers.",
        "Mange d'abord. Moi, je m'assieds après.",
    )
    outcome, _sent = _review(monkeypatch, {**_context(), "yesterday_hook": MISTRAL}, page)
    assert outcome is not None and outcome["accepted"] is True
    assert engine.hook_observation(MISTRAL, page)["hook_taken_up"] == "set_aside"


FLIGHT = {"text_fr": f"Marin te regarde. {DAY4_Q}", "question_fr": DAY4_Q, "date": "2026-11-20"}


def test_a_page_that_decides_for_the_learner_is_served_and_counted(monkeypatch):
    """A1 day 5: the panels narrated the airline call and «Mercredi 2 décembre. C'est noté.»"""

    page = _page(
        "Jeudi matin. Il fait froid dans le studio.",
        "Marin dit que tu appelles aujourd'hui. Mercredi, c'est fini.",
        last_line="Mercredi 2 décembre. C'est noté.",
        opening="L'agent demande pourquoi tu changes la date. Tu lui dis quoi ?",
    )
    outcome, _sent = _review(monkeypatch, {**_context(), "yesterday_hook": FLIGHT}, page)
    assert outcome is not None and outcome["accepted"] is True
    assert engine.hook_observation(FLIGHT, page)["decides_for_learner"] is True
    asked = _page(
        "Jeudi matin. Il fait froid dans le studio.",
        "Lila pose le téléphone sur la table.",
        opening="Tu gardes ton vol de mercredi ?",
    )
    observed = engine.hook_observation(FLIGHT, asked)
    assert observed == {"hook_source": "scene", "hook_taken_up": "early", "hook_repeats": True, "decides_for_learner": False}


# -- 5. «Précédemment»: the last played day first, never the stake ------------------


def test_previously_opens_on_what_the_learner_did_and_never_repeats_the_stake():
    live = _day_six_live()
    live["events"][-1]["did_fr"] = "Tu parleras à Gus de la clé."
    live["chronicle"].insert(0, {"id": "ch-0", "title_fr": "Le mauvais accueil", "question": "Ou tu dis au revoir à tout ça ?"})
    live["chronicle"][1]["resolved_fr"] = ""
    lines = engine.previously_lines(live, chapter_id="ch-2")
    assert lines[0] == "Lila et Marin aident pour le vol : Tu parleras à Gus de la clé.", lines
    assert lines[1] == "Marin répare le radiateur.", "then the day before"
    assert not any(line.endswith("?") for line in lines), "the stake block says the season's question"
    commitment = SimpleNamespace(text_fr="Tu parleras à Gus de la clé.")
    assert engine._learner_did(SimpleNamespace(commitments=[commitment])) == "Tu parleras à Gus de la clé."


# ===================================================================================
# Third commit: one hook, really one (check 2 of 17 Nov)
# ===================================================================================


def _settle(monkeypatch, *, ending: str, opening: str, exchanges, question: str | None, character="marin_leveque"):
    from app.services import scene_record

    monkeypatch.setattr(scene_record, "enabled", lambda: True)
    monkeypatch.setattr(engine, "_contract_hook", lambda *a, **k: None)
    monkeypatch.setattr(engine, "_tomorrow_question", lambda *a, **k: question)
    turn = SimpleNamespace(tomorrow_question_fr=question or "", resolution_fr=ending, reply_fr="", commitments=[])
    step = SimpleNamespace(
        kind="respond",
        private_task={"turns": [{"learner": learner, "character": said} for learner, said in exchanges]},
    )
    brief = SimpleNamespace(character_id=character, story_context={"draft": {"opening_line_fr": opening, "panels": []}})
    journey = SimpleNamespace(local_date=date(2026, 11, 20), steps=[step])
    return engine._hook_after_day(
        None, SimpleNamespace(id=1), live={}, world_after={}, brief=brief, turn=turn,
        journey=journey, act=None, relationships={"marin_leveque": {"register": "tu"}}, seed="p8",
    )


#: A1 day 4 of check 2: the hook asked what the learner had just answered.
A1_DAY4 = {
    "opening": "Jonas, tu vas comment, vraiment ?",
    "exchanges": [
        ("Fatigué.", "Je comprends. Qu'est-ce qui t'a fatigué ?"),
        ("Le froid et le avion. Je ne sais pas si je reste.", "Le froid et le voyage, oui… Qu'est-ce qui te ferait rester ?"),
        (
            "Un ami et un radiateur chaud. Demain, je veux voir Lila.",
            "Un ami et un radiateur chaud… je comprends. Tiens, « demain » ! Alors, demain, tu verras Lila.",
        ),
    ],
    "ending": (
        "Je comprends mieux. Un ami et un radiateur chaud te feraient du bien. Je ne peux pas tout "
        "réparer aujourd'hui, mais je reste un peu avec toi."
    ),
    "question": "Qu'est-ce qui te ferait rester à Paris ?",
}


def test_the_hook_is_the_learner_s_plan_never_the_question_just_answered(monkeypatch):
    teaser, _rows = _settle(monkeypatch, **A1_DAY4)
    assert teaser is not None and teaser["text_fr"] == "Demain, tu verras Lila.", teaser
    # Without the learner's «demain», the answered question is still never the hook.
    exchanges = [*A1_DAY4["exchanges"][:2], ("Un ami et un radiateur chaud.", "Un ami… je comprends.")]
    teaser, _rows = _settle(monkeypatch, **{**A1_DAY4, "exchanges": exchanges})
    assert teaser is None or "rester" not in teaser["text_fr"], teaser


def test_the_learner_s_plan_said_back_in_a_clause_of_the_ending_is_the_hook(monkeypatch):
    """B1 day 3: «Demain, je veux parler à Gus de la clé.»; the ending said it back in its
    second clause, and the hook was «Que feras-tu de l'appartement ?»."""

    teaser, _rows = _settle(
        monkeypatch,
        opening="Votre billet est pour le 18 novembre. Qu'est-ce que vous en faites ?",
        exchanges=[
            ("Je reste à Paris parce que je dois attendre les papiers.", "Votre mère sait-elle que le dossier prendra plusieurs semaines ?"),
            (
                "Le plus difficile sera de leur dire que je ne sais pas encore. Demain, je veux parler à Gus de la clé.",
                "C'est juste. Gus pourra vous parler de la clé.",
            ),
        ],
        ending=(
            "Je note que vous restez à Paris plusieurs semaines. Vous n'avez pas à choisir tout de suite "
            "pour l'appartement ; demain, vous pourrez parler de la clé avec Gus."
        ),
        question="Que feras-tu de l'appartement ?",
        character="maitre_vasseur",
    )
    assert teaser is not None and teaser["text_fr"] == "Demain, vous pourrez parler de la clé avec Gus.", teaser


def test_every_surface_reads_the_one_stored_hook_unmodified(monkeypatch):
    """The guard of point 5. Check 2: the end card printed «Au fait… Que feras-tu de
    l'appartement ?», Home and «Done» «Que feras-tu de l'appartement ?»; the end card had
    two sentences («… mercredi prochain. Le jour où Lila n'a pas classe.»), Home one."""

    from app.services import achievement_recap, serial_notifications
    from app.services.story_page import HOOK_PAYLOAD_KEY, hook_of
    from app.services.story_teaser import hook_line

    teaser, rows = _settle(
        monkeypatch,
        opening="Tu restes ?",
        exchanges=[("Oui, je reste.", "Bien.")],
        ending="Je note que tu restes.",
        question="Que feras-tu de l'appartement ?",
    )
    line = "Que feras-tu de l'appartement ?"
    assert teaser["text_fr"] == teaser["open_fr"] == line, teaser
    assert rows[-1]["text_fr"] == rows[-1]["open_fr"] == line
    # The end card (the scene's «À suivre…»), the push, the recap («Done» and Home).
    assert hook_of({HOOK_PAYLOAD_KEY: teaser["text_fr"]}) == line
    live = {"next_teaser": teaser}
    thread = SimpleNamespace(state={"living_story": live})
    pushed = serial_notifications.engine_teaser(SimpleNamespace(scalar=lambda *_a, **_k: thread), SimpleNamespace(id=1))
    assert pushed["text_fr"] == line
    journey = SimpleNamespace(id="j", scenario_snapshot={}, recap_snapshot={})
    recap = achievement_recap.recap_teaser(SimpleNamespace(id=1), journey, live)
    assert recap["text_fr"] == recap["open_fr"] == line
    # Tomorrow's page reads the same line.
    played = {**live, "events": [{"scene_id": "s", "date": teaser["date"], "summary_fr": "x"}]}
    assert engine.yesterday_hook(played)["text_fr"] == line
    # Too long for one line: clipped once, here, to whole sentences, for every surface.
    tentpole = {"text_fr": "Ton billet de retour est pour mercredi prochain. Le jour où Lila n'a pas classe, elle viendra. À suivre…"}
    assert hook_line(tentpole) == "Ton billet de retour est pour mercredi prochain."
    assert hook_line({"text_fr": "Deux clés pour la même porte. À suivre…"}) == "Deux clés pour la même porte."


# ===================================================================================
# Fourth commit: the hook is decided where the day is decided (real play of 17 Nov,
# third commit: taken up early 1, late 1, not at all 5 of 7; one page decided for the
# learner). The brief follows its planned beat; the hook now comes from that beat.
# ===================================================================================

GAP1 = ["plusieurs_semaines", "soupe_de_marin", "le_billet", "romy_enquete", "la_meme_chose"]
SEASON_LINES = (
    "Qui était Odile, et pourquoi est-elle partie ?",
    "Lila et Berlin : peut-on vouloir quelqu'un ici, et vouloir son départ pour elle ?",
    "L'avenir du Mistral : le garder, le changer, ou le laisser partir ?",
)
WORLD = {
    "cast": [
        {"id": "lila_bonnet", "name": "Lila Bonnet"},
        {"id": "marin_leveque", "name": "Marin Lévêque"},
        {"id": "augustin_de_roncourt", "name": "Augustin « Gus » de Roncourt"},
        {"id": "odile", "name": "Odile"},
    ],
    "season_one_situation": {
        "open_threads": ["Who was Odile?", "Lila and Berlin?", "The future of Le Mistral?"],
        "open_threads_fr": list(SEASON_LINES),
    },
}


def _season_after(gap_days: int) -> dict:
    """The season's state once T1 and ``gap_days`` days of gap 1 are played (the settle
    files the day's hook after the season's own settle)."""

    played = [
        {"segment": "t1", "kind": "tentpole", "day_in_segment": d, "season_day": d, "key": f"t1.{d}",
         "flex": 0, "date": f"2026-11-{17 + d}", "event_id": f"t1-{d}"}
        for d in (1, 2)
    ]
    played += [
        {"segment": "g1", "kind": "gap", "day_in_segment": d, "season_day": 2 + d, "key": f"g1.{d}",
         "flex": 0, "date": f"2026-11-{19 + d}", "event_id": f"g1-{d}"}
        for d in range(1, gap_days + 1)
    ]
    return {
        "id": "s1",
        "played": played,
        "premises": [{"gap": "g1", "premise": GAP1[d - 1], "day": d} for d in range(1, gap_days + 1)],
    }


def _settle_on_gap_day(monkeypatch, *, gap_days: int, ending: str, exchanges, question: str | None, kind="gap"):
    from app.services import scene_record
    from app.services.season.clock import SEASON_KEY

    monkeypatch.setattr(scene_record, "enabled", lambda: True)
    monkeypatch.setattr(engine, "_contract_hook", lambda *a, **k: None)
    monkeypatch.setattr(engine, "_tomorrow_question", lambda *a, **k: question)
    turn = SimpleNamespace(tomorrow_question_fr=question or "", resolution_fr=ending, reply_fr="", commitments=[])
    step = SimpleNamespace(
        kind="respond",
        private_task={"turns": [{"learner": learner, "character": said} for learner, said in exchanges]},
    )
    season = {"id": "s1", "kind": kind, "seed": "p8", "position": {"segment": "g1", "key": f"g1.{gap_days}"}}
    if kind == "tentpole":
        season = {**season, "position": {"segment": "t1", "key": "t1.2"},
                  "ending": {"text_fr": "Ton billet de retour est pour mercredi prochain."}}
    brief = SimpleNamespace(
        character_id="lila_bonnet",
        story_context={"draft": {"opening_line_fr": "Alors ?", "panels": []}, "season": season},
    )
    played = date(2026, 11, 19 + gap_days)
    journey = SimpleNamespace(local_date=played, steps=[step])
    live = {SEASON_KEY: _season_after(gap_days)}
    teaser, rows = engine._hook_after_day(
        None, SimpleNamespace(id=1), live=live, world_after=WORLD, brief=brief, turn=turn,
        journey=journey, act=None, relationships={"lila_bonnet": {"register": "tu"}}, seed="p8",
    )
    return teaser, rows, live


#: B1 day 3 (g1.1, the notary): the stored hook was the writer's question about the key,
#: and day 4 (Marin's soup) never touched it.
NOTARY_DAY = {
    "ending": "Tu restes quelques semaines, alors. On verra pour le reste.",
    "exchanges": [("Je reste. Je ne peux pas vendre avant les papiers.", "D'accord. Tu restes.")],
}


@pytest.mark.parametrize(
    "question", ["Pourquoi Odile t'a-t-elle laissé la clé ?", None], ids=["writer-question", "no-question"]
)
def test_the_hook_before_a_planned_day_is_tomorrow_s_beat(monkeypatch, question):
    teaser, rows, _live = _settle_on_gap_day(monkeypatch, gap_days=1, question=question, **NOTARY_DAY)
    assert teaser is not None
    assert teaser["text_fr"] == "La soupe de Marin", teaser
    assert teaser["source"] == "beat"
    assert teaser["text_fr"] not in SEASON_LINES
    assert rows[-1]["source"] == "beat"


def test_no_generic_season_line_on_any_day_of_gap_one_whose_next_day_is_planned(monkeypatch):
    for gap_days, beat in [(1, "La soupe de Marin"), (2, "Le billet"), (3, "Romy enquête"), (4, "La même chose ?")]:
        teaser, _rows, _live = _settle_on_gap_day(monkeypatch, gap_days=gap_days, question=None, **NOTARY_DAY)
        assert teaser["text_fr"] == beat, (gap_days, teaser)
        assert teaser["text_fr"] not in SEASON_LINES


def test_the_gap_s_last_day_falls_back_to_today_s_scene(monkeypatch):
    """Before a tentpole nothing is planned: the old order holds, and the source says so."""

    teaser, _rows, _live = _settle_on_gap_day(
        monkeypatch, gap_days=5, question="Tu commandes la même chose demain ?", **NOTARY_DAY
    )
    assert teaser["source"] == "scene", teaser


def test_a_tentpole_before_a_planned_day_keeps_its_own_line_not_the_writer_s_question(monkeypatch):
    """B1 day 2 (T1's last day): «Que dira Lila en voyant la clé ?» was filed over the
    tentpole's own line, and g1.1 (the notary, the flight) never touched it."""

    teaser, _rows, _live = _settle_on_gap_day(
        monkeypatch, gap_days=0, question="Que dira Lila en voyant la clé ?", kind="tentpole", **NOTARY_DAY
    )
    assert teaser["text_fr"] == "Ton billet de retour est pour mercredi prochain.", teaser
    assert teaser["source"] == "tentpole"


#: B1 day 3 of the integration walk: the learner's plan, said back by the ending.
GUS_PLAN = "Demain, je veux parler à Gus de la clé."


def test_the_learner_s_plan_is_the_hook_and_opens_tomorrow_s_beat(monkeypatch):
    from app.services.season.clock import SEASON_KEY
    from app.services.season.director import PLAN_KEY, gap_brief
    from app.services.season.epilogue import position_for
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season

    teaser, _rows, live = _settle_on_gap_day(
        monkeypatch,
        gap_days=2,
        question=None,
        ending="D'accord. Demain, tu parleras de la clé avec Gus.",
        exchanges=[(f"Je reste deux semaines. {GUS_PLAN}", "Avec Gus ? Bonne idée.")],
    )
    assert teaser["text_fr"] == "Demain, tu parleras de la clé avec Gus.", teaser
    assert teaser["source"] == "plan"
    state = live[SEASON_KEY]
    stored = state[PLAN_KEY]
    assert stored["said_fr"] == GUS_PLAN and stored["with"] == "augustin_de_roncourt"
    assert (stored["gap"], stored["day"]) == ("g1", 3)

    season = load_season("s1")
    pos = position_for(season, state, today=date(2026, 11, 22))
    brief = gap_brief(season, pos, flags=effective_flags(season, state, seed="p8"), state=state, seed="p8", band="B1")
    today = brief["today"]
    assert today["picked"]["plan_fr"] == GUS_PLAN
    assert today["picked"]["with"] == "augustin_de_roncourt"
    # The opening situation is the plan, with Gus on the page; the question is its next step.
    assert today["beat"]["before"].startswith(f"Yesterday the learner said what they want to do today: «{GUS_PLAN}» Gus is there")
    assert today["required_premise"]["turn"].startswith(f"First, Gus asks the learner the next step of their own plan («{GUS_PLAN}»)")
    # The season's own beat is kept, after it.
    assert "The ticket still says Wednesday 18 November." in today["beat"]["before"]
    assert "Tell the agent why you are changing the date." in today["required_premise"]["turn"]
    # A day without a plan keeps its beat as written, and drops yesterday's plan.
    teaser, _rows, live = _settle_on_gap_day(monkeypatch, gap_days=2, question=None, **NOTARY_DAY)
    assert PLAN_KEY not in live[SEASON_KEY]


def test_the_planner_may_cast_the_person_the_plan_names_again():
    context = _context(picked={"plan_fr": GUS_PLAN, "with": "marin_leveque"})
    plan = _plan(lead_id="marin_leveque", cast=["marin_leveque"], location_id="le_mistral",
                 task="Marin asks what you want to tell Gus.")
    assert story_split.plan_issue(plan, context) is None
    unnamed = _context()
    assert "carried the last days" in (story_split.plan_issue(plan, unnamed) or "")


def test_an_undecided_learner_choice_is_presented_as_open():
    """A1/B1 day 5 (g1.3, the ticket): the brief carried «settles: mercredi 2 décembre»
    beside «The ticket moves to 2 December»; the page narrated the new date and asked
    why the learner changed it before they chose to."""

    from app.services.season.director import gap_brief
    from app.services.season.epilogue import position_for
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season

    season = load_season("s1")
    state = _season_after(2)
    pos = position_for(season, state, today=date(2026, 11, 22))
    today = gap_brief(season, pos, flags=effective_flags(season, state, seed="p8"), state=state, seed="p8", band="A1")["today"]
    assert today["required_premise"]["id"] == "le_billet"
    assert today["learner_decides"] == [
        {"flag": "user.return_ticket", "now": None, "if_the_learner_decides_nothing": "mercredi 2 décembre"}
    ]
    assert "user.return_ticket" not in today["required_premise"]["settles"], "a default is not a fact"
    # Once the learner said it in their own words, it is theirs and no longer open.
    decided = {**state, "learner_set": {"user.return_ticket": "g1"}}
    today = gap_brief(season, pos, flags=effective_flags(season, decided, seed="p8"), state=decided, seed="p8", band="A1")["today"]
    assert "learner_decides" not in today
    # The planner and the one-call director are told what the field means.
    assert "brief.today.learner_decides" in story_split.PLANNER
    assert "brief.today.learner_decides" in engine.DIRECTOR


def test_the_hook_s_source_is_stored_and_logged_with_the_observation(monkeypatch, caplog):
    teaser, _rows, _live = _settle_on_gap_day(monkeypatch, gap_days=1, question=None, **NOTARY_DAY)
    live = {"next_teaser": teaser, "events": [{"scene_id": "s", "date": teaser["date"], "summary_fr": "x"}]}
    hook = engine.yesterday_hook(live)
    assert hook["source"] == "beat"
    page = {"opening_line_fr": "Ça va, vraiment ?", "panels": [
        {"narration_fr": "Le radiateur est mort.", "dialogue": [{"text_fr": "Marin : J'ai de la soupe."}]},
    ]}
    observed = engine.hook_observation(hook, page)
    assert observed["hook_source"] == "beat" and observed["hook_taken_up"] == "early", observed
    # Rows filed before this commit say where they came from by their ref and kind.
    from app.services.story_teaser import hook_source

    assert hook_source({"ref": "thread:odile", "kind": "thread"}) == "generic"
    assert hook_source({"ref": "contract:g3.cartes", "kind": "season"}) == "contract"
    assert hook_source({"ref": "scene:2026-11-20", "kind": "question"}) == "scene"
