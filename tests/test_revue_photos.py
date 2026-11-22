"""«Papier · photos» (owner, 2026-11-20): a news story shows several pictures, real photos among them.

No network and no image call here. The Commons API is answered by ``httpx.MockTransport`` from the
JSON under ``tests/fixtures/commons`` (shaped like the API's answer, written by hand); the painter
is ``plates._call`` replaced by the fake of ``test_revue_plates``. Under test:

* the photo filter: the licence allow-list (CC0, public domain, CC BY, CC BY-SA; never fair use,
  NC or ND), never a picture of a person (portrait words, personality rights, a person the dossier
  names), JPEG/WebP, landscape or square, ≥ 1024 px, an author, the French credit line;
* the subjects (places first, then the story's object; never a person, never a typed place);
* the fetch: one request per subject, a generic User-Agent, failure = no photos; stored once;
* the stage's ``pictures``: with the default switches nothing changes (the painted picture alone,
  or none); photos only while ``REVUE_PHOTOS_ENABLED``; never the desk's caption;
* ``REVUE_PICTURES_PER_STORY``: 1 paints as before; 3 paints two more shots, each once, final, priced;
* the RSS parser records that the outlet has a photo and its credit, and nothing else.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.db.models.pilot_event import PilotEvent
from app.db.models.revue_place import RevuePlace
from app.db.models.revue_session import RevueDossier
from app.db.models.revue_story_media import RevueStoryMedia
from app.db.models.revue_story_picture import RevueStoryPicture
from app.services.revue import encounter as enc
from app.services.revue import photos, plates
from app.services.revue.dossier import EditorialDossier, Entity, Place
from app.services.revue.evergreen import evergreens_for_week
from tests.test_revue_encounter import MARCHE, REVUE_TABLES, WEEK
from tests.test_revue_plates import (  # noqa: F401 - flag_on is a fixture
    MARKET_VISUAL,
    FakeImages,
    flag_on,
    pictured,
)

FIXTURES = Path(__file__).parent / "fixtures" / "commons"
ALIGRE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Marché_d'Aligre,_Paris_12e.jpg/1280px-Marché_d'Aligre,_Paris_12e.jpg"
CAGEOT_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Cageot_de_légumes_au_marché.jpg/"
    "1280px-Cageot_de_légumes_au_marché.jpg"
)


def answer(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class Commons:
    """A recorded Commons: answers each search from a fixture, records every request."""

    def __init__(self, *, fail: Exception | None = None, status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.fail = fail
        self.status = status

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        search = request.url.params.get("gsrsearch", "")
        body = answer("search_marche_aligre.json") if "Aligre" in search else answer("search_cageot.json") if "cageot" in search else {}
        return httpx.Response(self.status, json=body)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def marche() -> EditorialDossier:
    return next(d for d in evergreens_for_week(WEEK) if d.id == MARCHE).model_copy(deep=True)


def page_of(name: str, title_part: str) -> dict:
    return next(page for page in answer(name)["query"]["pages"] if title_part in page["title"])


def info_with(**meta: str) -> dict:
    return {"extmetadata": {key: {"value": value} for key, value in meta.items()}}


@pytest.fixture(scope="module")
def photo_tables(db_engine) -> Generator[None, None, None]:
    tables = (*REVUE_TABLES, RevuePlace.__table__, RevueStoryPicture.__table__, RevueStoryMedia.__table__,
              RevueDossier.__table__, PilotEvent.__table__)
    created = [table for table in tables if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, photo_tables) -> Generator[Session, None, None]:
    plates._PAINTED.clear()
    plates._STORIES.clear()
    yield db_session
    db_session.rollback()
    for model in (RevueStoryMedia, RevueStoryPicture, RevuePlace, RevueDossier):
        db_session.query(model).delete()
    db_session.query(PilotEvent).filter(PilotEvent.event_type == plates.PICTURE_COST_EVENT).delete()
    db_session.commit()
    plates._PAINTED.clear()
    plates._STORIES.clear()


@pytest.fixture()
def photos_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_PHOTOS_ENABLED", True)


# ---------------------------------------------------------------------------
# The switches
# ---------------------------------------------------------------------------


def test_the_switches_default_to_todays_behaviour() -> None:
    fields = Settings.model_fields
    assert fields["REVUE_PHOTOS_ENABLED"].default is False
    assert fields["REVUE_PHOTOS_PER_STORY"].default == 3
    assert fields["REVUE_PICTURES_PER_STORY"].default == 1
    with pytest.raises(ValueError):
        Settings(REVUE_PICTURES_PER_STORY=4)


# ---------------------------------------------------------------------------
# The filter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({"LicenseShortName": "CC0", "License": "cc0"}, ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/")),
        ({"LicenseShortName": "Public domain", "License": "pd"}, ("Domaine public", None)),
        ({"LicenseShortName": "CC BY 4.0", "License": "cc-by-4.0", "LicenseUrl": "https://creativecommons.org/licenses/by/4.0"},
         ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0")),
        ({"LicenseShortName": "CC BY-SA 3.0 de", "License": "cc-by-sa-3.0-de"}, ("CC BY-SA 3.0 de", None)),
        ({"LicenseShortName": "CC BY-SA 2.0 fr"}, ("CC BY-SA 2.0 fr", None)),
        ({"LicenseShortName": "CC BY-NC-SA 2.0", "License": "cc-by-nc-sa-2.0"}, None),
        ({"LicenseShortName": "CC BY-ND 4.0", "License": "cc-by-nd-4.0"}, None),
        ({"LicenseShortName": "CC BY-NC 4.0"}, None),
        ({"LicenseShortName": "Fair use", "License": "fair use"}, None),
        ({"LicenseShortName": "CC BY 4.0", "License": "cc-by-4.0", "NonFree": "true"}, None),
        ({"LicenseShortName": "GFDL", "License": "gfdl"}, None),
        ({"LicenseShortName": "All rights reserved"}, None),
        ({}, None),
    ],
)
def test_only_the_licence_allow_list_passes(meta: dict, expected) -> None:
    assert photos.licence_of(info_with(**meta)) == expected


def test_a_picture_of_a_person_is_refused() -> None:
    dossier = marche()
    market = page_of("search_marche_aligre.json", "Paris 12e")
    info = market["imageinfo"][0]
    assert photos.is_person_picture(market, info, dossier) is False
    portrait = page_of("search_marche_aligre.json", "Marchand")
    assert photos.is_person_picture(portrait, portrait["imageinfo"][0], dossier) is True
    for categories in ("Portraits of politicians", "1958 births", "People of Paris", "Ministers of France", "Selfies"):
        assert photos.is_person_picture({"title": "File:X.jpg"}, info_with(Categories=categories)) is True, categories
    # Commons' personality-rights mark.
    assert photos.is_person_picture({"title": "File:X.jpg"}, info_with(Restrictions="personality|trademarked")) is True
    # A person the story names, even without a portrait word.
    about = dossier.model_copy(update={"entities": [*dossier.entities, Entity(name="Rachida Lambert", kind="person", role="maraîchère")]})
    named = {"title": "File:Rachida Lambert au marché d'Aligre, 2024.jpg"}
    assert photos.is_person_picture(named, info_with(Categories="Marché d'Aligre"), about) is True


def test_the_filter_keeps_a_wide_free_credited_photo_and_says_why_it_refuses() -> None:
    subject = photos.Subject(query="Marché d'Aligre", kind="place", caption_fr="Marché d'Aligre")
    reasons = {}
    for page in answer("search_marche_aligre.json")["query"]["pages"]:
        reasons[page["title"]] = photos.photo_from_page(page, subject, marche())[1]
    assert reasons == {
        "File:Marché d'Aligre, Paris 12e.jpg": "ok",
        "File:Halle Beauvau vue verticale.jpg": "portrait_orientation",
        "File:Marché d'Aligre étals.jpg": "licence",
        "File:Marchand au marché d'Aligre.jpg": "person",
    }
    object_subject = photos.Subject(query="cageot de légumes", kind="object")
    reasons = {page["title"]: photos.photo_from_page(page, object_subject)[1] for page in answer("search_cageot.json")["query"]["pages"]}
    assert reasons == {
        "File:Cageot de légumes.png": "not_a_photo",
        "File:Cageot petit.jpg": "too_small",
        "File:Logo maraîcher.jpg": "licence",
        "File:Vieux cageot.jpg": "no_author",
        "File:Cageot de légumes au marché.jpg": "ok",
    }


def test_the_credit_line_and_the_caption() -> None:
    page = page_of("search_marche_aligre.json", "Paris 12e")
    photo, _ = photos.photo_from_page(page, photos.Subject(query="Marché d'Aligre", kind="place", caption_fr="Marché d'Aligre"))
    assert photo is not None
    assert photo.credit_fr == "Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons"
    assert photo.author == "Camille Exemple", "the HTML of Commons' Artist field is stripped"
    assert (photo.image_url, photo.width, photo.height) == (ALIGRE_URL, 1280, 960), "the sized thumbnail, not the original"
    assert photo.page_url == "https://commons.wikimedia.org/wiki/File:Marché_d'Aligre,_Paris_12e.jpg"
    assert photo.licence_url == "https://creativecommons.org/licenses/by-sa/4.0"
    assert photo.caption_fr == "Marché d'Aligre", "the file names the place the dossier names"
    # A file that does not name the place gets no caption: nothing is stated the dossier cannot back.
    unnamed = {**page, "title": "File:Un marché.jpg", "imageinfo": [{**page["imageinfo"][0], "extmetadata": {
        key: value for key, value in page["imageinfo"][0]["extmetadata"].items()
        if key not in {"Categories", "ImageDescription", "ObjectName"}}}]}
    photo, _ = photos.photo_from_page(unnamed, photos.Subject(query="Marché d'Aligre", kind="place", caption_fr="Marché d'Aligre"))
    assert photo is not None and photo.caption_fr is None


# ---------------------------------------------------------------------------
# What to search for
# ---------------------------------------------------------------------------


def test_subjects_are_the_named_places_first_then_the_object_never_a_person() -> None:
    dossier = marche()
    assert photos.subjects_for(dossier) == [
        photos.Subject(query="Marché d'Aligre", kind="place", caption_fr="Marché d'Aligre"),
        photos.Subject(query="cageot de légumes", kind="object"),
    ]
    assert photos.subjects_for(dossier, 1) == photos.subjects_for(dossier)[:1]
    # A person is never searched, even when the builder put the name in the object.
    about = dossier.model_copy(update={
        "entities": [*dossier.entities, Entity(name="Rachida Lambert", kind="person", role="maraîchère")],
        "vignette_object_fr": "Rachida Lambert",
    })
    assert [s.query for s in photos.subjects_for(about)] == ["Marché d'Aligre"]
    # A typed private place (no entity names it, no exact map point) is not searched.
    typed = dossier.model_copy(update={
        "entities": [],
        "places": [Place(id="vignoble", name_fr="Un vignoble en Bourgogne", brief="rows of vines, a stone hut, late-summer light")],
        "vignette_object_fr": "une grappe de raisin",
    })
    assert [s.query for s in photos.subjects_for(typed)] == ["grappe de raisin"]
    # The picture's words come after the object.
    assert [s.query for s in photos.subjects_for(pictured())][-2:] == ["marché en plein air", "marché couvert"]


# ---------------------------------------------------------------------------
# The fetch
# ---------------------------------------------------------------------------


def test_find_photos_asks_commons_once_per_subject_and_keeps_one_photo_each() -> None:
    commons = Commons()
    with commons.client() as client:
        found = photos.find_photos(marche(), client=client)
    assert [photo.image_url for photo in found] == [ALIGRE_URL, CAGEOT_URL]
    assert [photo.credit_fr for photo in found] == [
        "Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons",
        "Photo · Alex Exemple · CC0 · Wikimedia Commons",
    ]
    assert [photo.subject for photo in found] == ["Marché d'Aligre", "cageot de légumes"]
    assert found[1].licence_url == "https://creativecommons.org/publicdomain/zero/1.0/deed.en", "an http deed is upgraded"
    assert len(commons.requests) == 2
    request = commons.requests[0]
    assert (request.url.host, request.url.path) == ("commons.wikimedia.org", "/w/api.php")
    params = request.url.params
    assert (params["generator"], params["gsrnamespace"], params["prop"]) == ("search", "6", "imageinfo")
    assert params["iiprop"] == "url|extmetadata|size|mime" and params["iiurlwidth"] == "1280"
    agent = request.headers["user-agent"]
    assert agent == photos.USER_AGENT and "@" not in agent and "http" not in agent.split(";")[0]
    # The limit holds.
    with Commons().client() as client:
        assert len(photos.find_photos(marche(), client=client, limit=1)) == 1


@pytest.mark.parametrize("trouble", ["network", "http", "budget"])
def test_any_failure_means_no_photos(trouble: str) -> None:
    commons = Commons(fail=httpx.ConnectError("no route") if trouble == "network" else None, status=503 if trouble == "http" else 200)
    ticks = iter([0.0, 0.0, 7.0, 7.0])
    clock = (lambda: next(ticks)) if trouble == "budget" else photos.time.monotonic
    with commons.client() as client:
        assert photos.find_photos(marche(), client=client, clock=clock) == []
    assert len(commons.requests) == 1, "one try, no retry"


def test_ensure_photos_searches_each_story_once_and_stores_the_credit(db: Session, photos_on) -> None:
    dossier = marche()
    db.add(RevueDossier(id=f"{WEEK}:{dossier.id}", week=WEEK, period=WEEK, topic=dossier.topic,
                        payload=dossier.model_dump(mode="json"), source_hashes={}, checks={}, builder_version="t"))
    db.commit()
    commons = Commons()
    with commons.client() as client:
        assert photos.ensure_photos(db, WEEK, client=client) == {dossier.id: 2}
        assert photos.ensure_photos(db, WEEK, client=client) == {}, "searched once"
    assert len(commons.requests) == 2
    rows = db.query(RevueStoryMedia).order_by(RevueStoryMedia.position).all()
    assert [(row.kind, row.position, row.licence, row.author) for row in rows] == [
        ("photo", 1, "CC BY-SA 4.0", "Camille Exemple"), ("photo", 2, "CC0", "Alex Exemple"),
    ]
    assert rows[0].page_url.startswith("https://commons.wikimedia.org/wiki/File:")
    assert db.get(RevueDossier, f"{WEEK}:{dossier.id}").checks["photos"] == 2


def test_ensure_photos_is_off_by_default(db: Session) -> None:
    commons = Commons()
    with commons.client() as client:
        assert photos.ensure_photos(db, WEEK, client=client) == {}
    assert commons.requests == []


def test_the_morning_task_adds_photos_only_with_the_switch(monkeypatch) -> None:
    from app.tasks import revue as task

    monkeypatch.setattr(task, "intake_now", lambda refresh=False: {"status": "kept", "period": WEEK})
    monkeypatch.setattr(task, "leads_now", lambda period=None: {"status": "ok"})
    monkeypatch.setattr(task, "_queue_painting", lambda period: {"status": "enqueued"})
    monkeypatch.setattr(task, "photos_now", lambda period=None: {"status": "ok", "photos": {}})
    assert "photos" not in task.weekly_intake()
    monkeypatch.setattr(settings, "REVUE_PHOTOS_ENABLED", True)
    assert task.weekly_intake()["photos"] == {"status": "ok", "photos": {}}


# ---------------------------------------------------------------------------
# The stage's pictures
# ---------------------------------------------------------------------------


def _paint_first(db: Session, dossier: EditorialDossier) -> None:
    db.add(RevueStoryPicture(dossier_id=dossier.id, place_id=dossier.places[0].id, picture_url="/media/story.webp",
                             caption_fr=MARKET_VISUAL.caption_fr, prompt="p", prompt_version=plates.STORY_PROMPT_VERSION))
    db.commit()


def _photo_rows(db: Session, dossier_id: str) -> None:
    with Commons().client() as client:
        photos.store_photos(db, dossier_id, photos.find_photos(marche(), client=client))
    db.commit()


def test_with_the_default_switches_the_stage_shows_what_it_showed(db: Session) -> None:
    dossier = pictured()
    assert enc.stage_for(dossier, db=db).pictures == [], "not painted: no pictures"
    _photo_rows(db, dossier.id)
    assert enc.stage_for(dossier, db=db).pictures == [], "photos stay hidden while the switch is off"
    _paint_first(db, dossier)
    stage = enc.stage_for(dossier, db=db)
    assert stage.plate_url == "/media/story.webp" and stage.plate_kind == "story"
    (only,) = stage.pictures
    assert (only.kind, only.url, only.credit_fr, only.caption_fr, only.alt_fr) == (
        "illustration", "/media/story.webp", "Illustration · Le Papier", None, "",
    ), "never the desk's caption: it is the answer of «La légende»"


def test_with_photos_on_the_gallery_follows_the_painted_picture(db: Session, photos_on, monkeypatch) -> None:
    dossier = pictured()
    _paint_first(db, dossier)
    _photo_rows(db, dossier.id)
    pictures = enc.stage_for(dossier, db=db).pictures
    assert [(p.kind, p.url) for p in pictures] == [
        ("illustration", "/media/story.webp"), ("photo", ALIGRE_URL), ("photo", CAGEOT_URL),
    ]
    photo = pictures[1]
    assert photo.credit_fr == "Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons"
    assert (photo.licence, photo.licence_url) == ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0")
    assert photo.source_url == "https://commons.wikimedia.org/wiki/File:Marché_d'Aligre,_Paris_12e.jpg"
    assert (photo.caption_fr, photo.alt_fr) == ("Marché d'Aligre", "Marché d'Aligre")
    # The Une card carries the same list (it is the stage's).
    assert enc.story_card(dossier, db).stage.pictures == pictures
    monkeypatch.setattr(settings, "REVUE_PHOTOS_PER_STORY", 1)
    assert [p.kind for p in enc.stage_for(dossier, db=db).pictures] == ["illustration", "photo"]


def test_the_session_payload_carries_the_pictures_over_http(db: Session, photos_on, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.api.deps import get_db
    from app.main import create_app
    from tests.test_revue_api import login

    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    for dossier in evergreens_for_week(WEEK):  # whichever story the chooser recommends
        _photo_rows(db, dossier.id)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        headers = login(client)
        body = client.get("/api/v1/revue/week", headers=headers, params={"week": WEEK}).json()
    pictures = body["recommended"]["stage"]["pictures"]
    assert [p["kind"] for p in pictures] == ["photo", "photo"]
    assert set(pictures[0]) == {"kind", "url", "width", "height", "alt_fr", "caption_fr", "credit_fr", "licence",
                                "licence_url", "source_url"}


# ---------------------------------------------------------------------------
# More than one illustration (REVUE_PICTURES_PER_STORY)
# ---------------------------------------------------------------------------


def test_one_picture_per_story_paints_as_before(db: Session, monkeypatch, flag_on) -> None:  # noqa: F811
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    out = plates.paint_dossier_pictures(db, pictured())
    assert set(out) == {"story"} and len(fake.prompts) == 1
    assert db.query(RevueStoryMedia).count() == 0


def test_three_pictures_per_story_paint_two_more_shots_once_each(db: Session, monkeypatch, flag_on) -> None:  # noqa: F811
    monkeypatch.setattr(settings, "REVUE_PICTURES_PER_STORY", 3)
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    dossier = pictured()
    out = plates.paint_dossier_pictures(db, dossier)
    assert set(out) == {"story", "story_2", "story_3"}
    assert all("/revue-stories/" in out[key] for key in out)
    assert len(fake.prompts) == 3 and len(set(fake.prompts)) == 3, "three different shots"
    story, wide, near = fake.prompts
    assert wide.startswith(plates.REVUE_STORY_STYLE + "This is a second, different picture of the same story")
    assert near.startswith(plates.REVUE_STORY_STYLE + "This is a third, different picture of the same story")
    for prompt in (wide, near):
        assert prompt.endswith(story[len(plates.REVUE_STORY_STYLE):]), "the same story, checks and negative clause"
    rows = db.query(RevueStoryMedia).order_by(RevueStoryMedia.position).all()
    assert [(r.kind, r.position, r.subject, r.prompt_version) for r in rows] == [
        ("illustration", 2, "wide", plates.STORY_SHOT_PROMPT_VERSION),
        ("illustration", 3, "near", plates.STORY_SHOT_PROMPT_VERSION),
    ]
    costs = db.query(PilotEvent).filter(PilotEvent.event_type == plates.PICTURE_COST_EVENT).all()
    assert sorted(c.entity_type for c in costs) == ["revue_story", "revue_story_shot", "revue_story_shot"]
    assert all(c.cost_usd == pytest.approx(settings.REVUE_PICTURE_COST_USD) for c in costs)
    # Final: a second run paints nothing.
    again = plates.paint_dossier_pictures(db, dossier)
    assert (again["story_2"], again["story_3"]) == ("kept", "kept") and len(fake.prompts) == 3
    # The gallery: the painted picture, then the two shots (all credited as illustrations).
    pictures = enc.stage_for(dossier, db=db).pictures
    assert [(p.kind, p.credit_fr) for p in pictures] == [("illustration", "Illustration · Le Papier")] * 3
    monkeypatch.setattr(settings, "REVUE_PICTURES_PER_STORY", 2)
    assert len(enc.stage_for(dossier, db=db).pictures) == 2


def test_the_cap_holds_the_extra_shots(db: Session, monkeypatch, flag_on) -> None:  # noqa: F811
    monkeypatch.setattr(settings, "REVUE_PICTURES_PER_STORY", 3)
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    calls = iter([None, "budget"])
    out = plates.paint_dossier_pictures(db, pictured(), gate=lambda: next(calls, "budget"))
    assert out["story_2"] == "budget" and "story_3" not in out and len(fake.prompts) == 1


# ---------------------------------------------------------------------------
# The outlet's own photo: recorded, never stored or shown
# ---------------------------------------------------------------------------

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Exemple</title>
<item><title>Le marché d'Aligre rouvre ses portes</title><link>https://exemple.fr/a</link>
<description>Le marché couvert rouvre ce samedi.</description>
<media:content url="https://exemple.fr/photo.jpg" medium="image" width="1200"><media:credit>Photo Agence Exemple</media:credit></media:content>
</item>
<item><title>Une enclosure sans crédit</title><link>https://exemple.fr/b</link>
<description>Rien.</description><enclosure url="https://exemple.fr/b.jpg" type="image/jpeg" length="1"/></item>
<item><title>Un podcast</title><link>https://exemple.fr/c</link>
<description>Rien.</description><enclosure url="https://exemple.fr/c.mp3" type="audio/mpeg" length="1"/></item>
</channel></rss>"""


def test_the_rss_parser_records_the_press_photo_and_its_credit_only() -> None:
    from app.services.news_service import NewsService

    service = NewsService.__new__(NewsService)
    items = service._parse_rss_items(FEED, source_hint="exemple", language="fr", limit=5)
    assert [(i.get("press_photo"), i.get("press_photo_credit")) for i in items] == [
        ("yes", "Photo Agence Exemple"), ("yes", None), (None, None),
    ]
    assert not any("photo.jpg" in value or "b.jpg" in value for item in items for value in item.values()), "no URL kept"
