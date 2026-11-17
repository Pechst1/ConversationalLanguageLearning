"""P8 · Today's page answers yesterday's hook (experience review of 17 Nov, finding 5).

Walk of 17 Nov (B1, days 3–6): «Que décideras-tu pour ton vol ?» closed day 3 and day 4
never asked it; «Précédemment» still opened on day 1's «Le mauvais accueil» on day 6;
days 3, 4 and 5 were all headlined «Le Mistral», the café's name.
"""

# ruff: noqa: F811 - pytest fixtures imported from the story-split tests
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services import living_story as engine
from app.services import story_split
from app.services.journey_contracts import InputMode
from app.services.season.director import StoryReview, critic_payload
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


def test_the_plan_says_how_it_takes_the_hook_up_and_may_come_back_to_yesterday_s_question():
    context = _with_hook(_context())
    yesterday = context["recent_situations"][-1]["objective_native"]
    # Without a word on the hook the first plan is asked again.
    assert "yesterday_hook" in (story_split.hook_plan_issue(_plan(), context) or "")
    # Taking it up is not «already asked»: yesterday's question is the hook's.
    taking_up = _plan(task=yesterday, takes_up_hook="Beat 1: Lila asks again about the flight.")
    assert story_split.plan_issue(taking_up, context) is None
    assert "already asked" in (story_split.plan_issue(_plan(task=yesterday), _context()) or "")


# -- the critic: takes_up_hook ------------------------------------------------------


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
        sent.append(payload)
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


def test_a_page_that_never_touches_the_flight_is_refused(monkeypatch):
    page = _page("Le studio est froid.", "Tu as faim ?")
    outcome, sent = _review(monkeypatch, _season_context(), page)
    assert sent[0]["yesterday_hook"]["question_fr"] == HOOK, "the critic reads the hook"
    assert outcome is not None and outcome["accepted"] is False
    assert any(HOOK in issue for issue in outcome["issues"])
    assert outcome["class"] == "storytelling", "a reader item: a second refusal is still served"


@pytest.mark.parametrize(
    "page",
    [
        _page("Lila tient ton billet.", "Alors, ton vol ? Mercredi ou pas ?"),
        _page(
            "Le studio est froid.",
            "Tu as faim ?",
            last_line="Ton vol ? On en parle demain, promis.",
        ),
    ],
    ids=["answers-it-in-panel-2", "sets-it-aside-in-a-line"],
)
def test_a_page_that_takes_the_hook_up_or_sets_it_aside_is_accepted(monkeypatch, page):
    outcome, _sent = _review(monkeypatch, _season_context(), page)
    assert outcome is not None and outcome["accepted"] is True


def test_the_critic_never_counts_the_hook_as_a_repeat():
    payload = critic_payload({}, _page("x", "y"), yesterday_hook={"question_fr": HOOK})
    assert payload["yesterday_hook"]["question_fr"] == HOOK
    assert "yesterday_hook" not in critic_payload(
        {}, _page("x", "y"), yesterday_hook={"question_fr": HOOK}, act={"role": "soir"}
    )
    from app.services.season.director import STORY_CRITIC

    moves_on = " ".join(STORY_CRITIC.split("- moves_on:")[1].split("- remembers:")[0].split())
    assert "Taking up yesterday_hook is never a repeat" in moves_on


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
        lines[-1] == "Lila et Marin aident pour le vol : Tu soupçonnes Gus ; Lila veut une preuve."
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
