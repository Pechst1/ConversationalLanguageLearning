"""WP-167 «a news day inside the story»: every second generated day takes a fresh
headline (``app/services/news_day.py``). Offline: the feeds, the picker and the painter
are stubbed; the suite keeps ``ATELIER_NEWS_DAY_ENABLED`` off (``tests/conftest.py``)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from email.utils import format_datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.pilot_event import PilotEvent
from app.services import living_story as engine
from app.services import news_day
from app.services.revue import plates as revue_plates
from app.services.season import plates
from tests import test_season_one as season_suite

assembled_client = season_suite.assembled_client
clock = season_suite.clock
journey_enabled = season_suite.journey_enabled
season_on = season_suite.season_on
support = season_suite.support


def _headlines() -> list[dict]:
    now = datetime.now(UTC).replace(microsecond=0)
    rows = [
        ("Grève à la RATP : le métro presque à l'arrêt mardi", "Franceinfo", "franceinfo_france"),
        ("Le prix de la baguette dépasse 1,50 euro dans plusieurs boulangeries de Paris", "Le Monde", "le_monde_front"),
        ("Le gouvernement présente un budget sous haute tension à l'Assemblée", "RFI", "rfi_france"),
        ("Un chat élu maire honoraire d'un village du Jura", "France 24", "france24_france"),
    ]
    return [
        {
            "id": news_day.headline_id(f"https://news.example.test/{index}", title),
            "title": title,
            "summary": f"Résumé de l'article {index}.",
            "source": source,
            "source_id": source_id,
            "url": f"https://news.example.test/{index}",
            "published_at": (now - timedelta(hours=index + 1)).isoformat(),
        }
        for index, (title, source, source_id) in enumerate(rows)
    ]


# ---------------------------------------------------------------------------
# The cadence
# ---------------------------------------------------------------------------


def test_a_news_day_is_due_every_second_generated_day(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_NEWS_DAY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_NEWS_DAY_EVERY", 2)
    live = lambda since: {news_day.LEDGER_KEY: {"generated": 7, "since_news": since}}  # noqa: E731
    assert [news_day.due(live(since)) for since in range(4)] == [False, True, True, True]
    assert news_day.due({}) is False, "a new life's first generated day is an ordinary one"
    monkeypatch.setattr(settings, "ATELIER_NEWS_DAY_EVERY", 3)
    assert [news_day.due(live(since)) for since in range(3)] == [False, False, True]
    monkeypatch.setattr(settings, "ATELIER_NEWS_DAY_ENABLED", False)
    assert news_day.due(live(5)) is False


def _bound(marker: dict | None, *, tentpole: bool = False, state: dict | None = None):
    brief = SimpleNamespace(story_context={news_day.BRIEF_KEY: marker} if marker is not None else {})
    scene = SimpleNamespace(id=uuid.uuid4(), script_payload={}, panels=[])
    thread = SimpleNamespace(state=state or {})
    news_day.on_bind(None, user=None, brief=brief, scene=scene, thread=thread, tentpole=tentpole)
    return (thread.state.get(engine.STATE_KEY) or {}).get(news_day.LEDGER_KEY), scene


def test_authored_days_never_count_and_generated_days_do():
    assert _bound({"generated": True, "news": None}, tentpole=True)[0] is None, "a tentpole page is never counted"
    assert _bound(None)[0] is None, "a brief the director did not write is never counted"
    ledger, _ = _bound({"generated": True, "news": None})
    assert ledger["generated"] == 1 and ledger["since_news"] == 1


def test_a_served_news_day_resets_the_cadence_and_remembers_its_headline(monkeypatch):
    monkeypatch.setattr(plates, "plate_url_for", lambda db, place, **kw: None)
    headline = _headlines()[0]
    news = {**headline, "keys": news_day.keys_of(headline), "credit_fr": news_day.credit_fr(headline), "plate": None}
    state = {engine.STATE_KEY: {news_day.LEDGER_KEY: {"generated": 3, "since_news": 1}}}
    ledger, scene = _bound({"generated": True, "news": news}, state=state)
    assert ledger["generated"] == 4 and ledger["since_news"] == 0
    assert set(news_day.keys_of(headline)) <= set(ledger["seen"])
    assert scene.script_payload[news_day.SCRIPT_KEY]["credit_fr"].startswith("D'après l'actualité du ")


# ---------------------------------------------------------------------------
# The source: fresh, French, any topic, never twice
# ---------------------------------------------------------------------------


def _rss(items: list[tuple[str, str, datetime]]) -> str:
    rows = "".join(
        f"<item><title>{title}</title><link>https://feed.example.test/{index}</link>"
        f"<description>{summary}</description><pubDate>{format_datetime(when)}</pubDate></item>"
        for index, (title, summary, when) in enumerate(items)
    )
    return f"<?xml version='1.0'?><rss><channel><title>Feed</title>{rows}</channel></rss>"


def test_the_feed_keeps_fresh_french_headlines_of_any_topic():
    now = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
    xml = _rss(
        [
            ("Le Premier ministre engage la responsabilité du gouvernement sur le budget", "Le débat est vif à l'Assemblée.", now - timedelta(hours=3)),
            ("Un meurtre à Marseille : la police lance un appel à témoins", "L'enquête est en cours dans le quartier.", now - timedelta(hours=20)),
            ("La fête des vendanges de Montmartre attire la foule", "Le défilé est passé par la rue.", now - timedelta(days=3)),
            ("Stock markets rally as the central bank cuts rates again", "Investors cheered the news on the day.", now - timedelta(hours=1)),
        ]
    )
    kept = news_day.parse_feed({"id": "le_monde_front", "name": "Le Monde"}, xml, now=now)
    titles = [row["title"] for row in kept]
    assert len(titles) == 2, titles
    assert titles[0].startswith("Le Premier ministre"), "politics is in (owner decision 3)"
    assert titles[1].startswith("Un meurtre"), "no topic filter: a grave story is news too"
    assert all(row["source"] == "Le Monde" and row["published_at"] for row in kept)


def test_candidates_never_offer_a_headline_this_learner_already_had():
    rows = _headlines()
    had = news_day.keys_of(rows[1])
    # The same article under a second outlet's link is the same news.
    twin = {**rows[1], "id": "other-link", "url": "https://elsewhere.example.test/x", "source_id": "rfi_france"}
    offered = news_day.candidates([*rows, twin], {"seen": had}, limit=15)
    assert rows[1]["title"] not in [row["title"] for row in offered]
    assert len(offered) == 3
    crowded = [rows[0], {**rows[1], "source_id": rows[0]["source_id"]}, rows[2]]
    for _ in range(5):
        spread = news_day.candidates(crowded, {"seen": []}, limit=2)
        assert len({row["source_id"] for row in spread}) == 2, "dealt round the outlets, not one outlet's list"


# ---------------------------------------------------------------------------
# The prompt, the plate brief, the credit
# ---------------------------------------------------------------------------


def test_the_director_prompt_changes_on_a_news_day_only():
    assert news_day.NO_NEWS_SENTENCE in engine.DIRECTOR, "the sentence a news day replaces is still there"
    assert news_day.director_prompt(engine.DIRECTOR, {}) is engine.DIRECTOR
    news = news_day.director_prompt(engine.DIRECTOR, {news_day.CONTEXT_KEY: {"headline": {}}})
    assert news_day.NO_NEWS_SENTENCE not in news
    assert "NEWS DAY." in news and "If it could fit any headline" not in engine.DIRECTOR
    assert "if the page could fit any headline, it is wrong" in news


def test_the_plate_brief_is_an_empty_set():
    brief = news_day.plate_brief(
        "Le Mistral's zinc at dusk, a stack of unsold baguettes, a radio on the shelf, "
        "a woman counting coins, a chalkboard reading «1,50 €», rain on the window. A dog sleeps."
    )
    assert "baguettes" in brief and "rain on the window" in brief and "radio" in brief
    assert "woman" not in brief and "reading" not in brief and "dog" not in brief


def test_the_credit_line():
    row = {"title": "Un chat élu maire", "source": "France 24", "published_at": "2026-10-12T09:00:00+00:00"}
    assert news_day.credit_fr(row) == "D'après l'actualité du 12 octobre : Un chat élu maire (France 24)"
    assert news_day.date_fr(date(2026, 11, 1)) == "1er novembre"


# ---------------------------------------------------------------------------
# A season life through the real API
# ---------------------------------------------------------------------------


@pytest.fixture
def news_on(monkeypatch, season_on):
    """The season fixture with news days on: four stubbed headlines, a picker that
    answers, a director that writes its news notes, and plate painting stubbed."""

    provider = season_on
    provider.spoil_once = False
    provider.critic_refusals_left = 0
    monkeypatch.setattr(settings, "ATELIER_NEWS_DAY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_NEWS_DAY_EVERY", 2)
    monkeypatch.setattr(news_day, "fetch_headlines", lambda **kwargs: _headlines())
    record = SimpleNamespace(prompts=[], picks=0, refuse_news=False, jobs=[], painted=[], paint_error=None)
    plain_draft = provider._season_draft

    def draft(context):
        value = plain_draft(context)
        if context.get(news_day.CONTEXT_KEY):
            if record.refuse_news:
                raise engine.StoryUnavailable("news_refused_for_test")
            value["news_day_notes"] = {
                "mechanic_fr": "La grève vide le quai : personne ne vient au Mistral.",
                "entry_fr": "La radio du zinc l'annonce.",
                "plate_brief": "Le Mistral's zinc at dusk, a radio on the shelf, empty stools, a strike notice, rain outside",
            }
            value["season_checklist"]["premise_id"] = "news"
        return value

    monkeypatch.setattr(provider, "_season_draft", draft)
    plain_complete = provider.generate_chat_completion

    def complete(messages, **kwargs):
        import json

        schema = json.loads(messages[0]["content"])["output_schema"]["title"]
        if schema == "NewsPick":
            record.picks += 1
            return SimpleNamespace(
                content=json.dumps({"choice": 1, "mechanic_fr": "Une règle change du jour au lendemain.", "why": "It hits the café."}),
                model="fake-season", provider="test", total_tokens=30, cost=0.0,
            )
        if schema == "SceneDraft":
            record.prompts.append(kwargs.get("system_prompt") or "")
        return plain_complete(messages, **kwargs)

    monkeypatch.setattr(provider, "generate_chat_completion", complete)
    monkeypatch.setattr(news_day, "dispatcher", record.jobs.append)
    monkeypatch.setattr(plates, "generation_unavailable_reason", lambda: None)

    def paint(db, key, brief, *, name_fr=None):
        if record.paint_error is not None:
            raise record.paint_error
        url = f"/var/news-plates/{len(record.painted)}.webp"
        record.painted.append({"key": key, "brief": brief})
        revue_plates._PAINTED[key] = url  # noqa: SLF001 - as paint_plate records it
        return url

    monkeypatch.setattr(plates, "paint_plate", paint)
    return provider, record


def _day(d, provider, clock, db) -> dict:
    journey = season_suite._play(d, provider, clock, "Je voudrais un café, s'il vous plaît.")
    user_id = season_suite._user_id_of(db, journey)
    scene = season_suite._latest_scene(db, user_id)
    payload = scene.script_payload or {}
    return {
        "journey": journey,
        "user_id": user_id,
        "scene": scene,
        "kind": (payload.get("season") or {}).get("kind"),
        "news": payload.get(news_day.SCRIPT_KEY),
        "generated": (scene.source_snapshot or {}).get("journey_id") == journey["id"],
    }


def _ledger(db, user_id) -> dict:
    thread = season_suite._thread(db, user_id)
    return news_day.ledger_of((thread.state or {}).get(engine.STATE_KEY) or {})


def test_a_season_life_gets_a_news_day_every_second_generated_day(assembled_client, db_session, journey_enabled, clock, news_on):
    provider, record = news_on
    d = support.Driver(assembled_client, support.register(assembled_client, f"news-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session)
    days = [_day(d, provider, clock, db_session) for _ in range(6)]
    kinds = [row["kind"] for row in days]
    assert kinds[:2] == ["tentpole", "tentpole"], kinds
    assert all(row["news"] is None for row in days[:2]), "an authored page never carries news"
    generated = [row for row in days if row["kind"] == "gap"]
    assert len(generated) == 4 and all(row["generated"] for row in generated)
    assert [bool(row["news"]) for row in generated] == [False, True, False, True], "every second generated day"
    first, second = generated[1]["news"], generated[3]["news"]
    assert first["title"] != second["title"], "a learner never gets the same headline twice"
    assert first["credit_fr"].startswith("D'après l'actualité du ") and f"({first['source']})" in first["credit_fr"]
    assert record.picks == 2, "one model pick per news day"
    news_prompts = [prompt for prompt in record.prompts if "NEWS DAY." in prompt]
    assert news_prompts and all(news_day.NO_NEWS_SENTENCE not in prompt for prompt in news_prompts)
    assert any(news_day.NO_NEWS_SENTENCE in prompt for prompt in record.prompts), "ordinary days keep the plain prompt"
    ledger = _ledger(db_session, days[-1]["user_id"])
    assert ledger["generated"] == 4 and ledger["since_news"] == 0 and len(ledger["days"]) == 2
    episode = season_suite._episode_of(d, generated[1]["journey"])
    assert episode["news"]["credit_fr"] == first["credit_fr"], "the credit is in the episode payload"
    assert season_suite._episode_of(d, generated[0]["journey"])["news"] is None


def test_the_news_plate_swaps_in_without_blocking_the_day(assembled_client, db_session, journey_enabled, clock, news_on):
    provider, record = news_on
    d = support.Driver(assembled_client, support.register(assembled_client, f"plate-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session)
    days = [_day(d, provider, clock, db_session) for _ in range(4)]
    news = days[3]
    assert news["news"], [row["kind"] for row in days]
    # The day was served at once on the plate there was; the painting waits in the queue.
    (job,) = [job for job in record.jobs if job.scene_id == str(news["scene"].id)]
    assert not record.painted, "nothing is painted before the day is served"
    assert "people" not in job.brief.lower() and "radio on the shelf" in job.brief
    before = season_suite._episode_of(d, news["journey"])
    assert all(panel["image_status"] == "rendering" for panel in before["panels"]), "the reader polls for the plate"
    static = {panel["plate_url"] for panel in before["panels"]}
    assert static and None not in static
    assert news_day.run_plate_job(job) == "painted"
    db_session.expire_all()
    after = season_suite._episode_of(d, news["journey"])
    assert {panel["plate_url"] for panel in after["panels"]} == {"/var/news-plates/0.webp"}
    assert all(panel["image_status"] == "setting_reference" for panel in after["panels"])
    assert news["news"]["plate_key"] == job.key and job.key.startswith(plates.KEY_PREFIX)
    art = db_session.scalars(select(PilotEvent).where(PilotEvent.event_type == "journey_panel_art_cost")).all()
    assert len(art) == 1 and art[0].payload["kind"] == "news_plate", "the plate is paid for in the open"


def test_painting_off_or_failing_keeps_the_static_plate(assembled_client, db_session, journey_enabled, clock, news_on):
    provider, record = news_on
    record.paint_error = plates.SeasonPlateOff("ATELIER_SEASON_PLATES_ENABLED is false")
    d = support.Driver(assembled_client, support.register(assembled_client, f"off-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session)
    days = [_day(d, provider, clock, db_session) for _ in range(4)]
    (job,) = [job for job in record.jobs if job.scene_id == str(days[3]["scene"].id)]
    before = season_suite._episode_of(d, days[3]["journey"])
    assert news_day.run_plate_job(job) == "static"
    db_session.expire_all()
    after = season_suite._episode_of(d, days[3]["journey"])
    assert [panel["plate_url"] for panel in after["panels"]] == [panel["plate_url"] for panel in before["panels"]]
    assert all(panel["image_status"] == "setting_reference" for panel in after["panels"]), "never stuck «rendering»"


def test_a_refused_news_day_is_an_ordinary_generated_day_and_the_news_is_owed(assembled_client, db_session, journey_enabled, clock, news_on):
    provider, record = news_on
    record.refuse_news = True
    d = support.Driver(assembled_client, support.register(assembled_client, f"refused-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session)
    days = [_day(d, provider, clock, db_session) for _ in range(4)]
    refused = days[3]
    assert refused["kind"] == "gap" and refused["generated"], "a generated day, not the authored fallback"
    assert refused["news"] is None
    skipped = db_session.scalars(select(PilotEvent).where(PilotEvent.event_type == "journey_news_day_skipped")).all()
    assert len(skipped) == 1 and skipped[0].payload["title"]
    assert _ledger(db_session, refused["user_id"])["since_news"] == 2
    record.refuse_news = False
    owed = _day(d, provider, clock, db_session)
    assert owed["kind"] == "gap" and owed["news"], "the news is owed: the next generated day takes it"
