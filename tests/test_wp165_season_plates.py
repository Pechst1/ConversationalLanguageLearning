"""WP-165: every season place has its own plate; light and weather variants are looked up,
painted lazily in the background and served once painted; the style check re-rolls a
plate that is not a flat print. No image call is made: the painter is replaced."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.models.revue_place import RevuePlace
from app.services.revue import plates as revue_plates
from app.services.season import plates
from app.services.season.world import (
    PUBLIC_ROOT,
    SEASON_ONE_LOCATIONS,
    SEASON_ONE_PLATE_BRIEFS,
    place_brief,
    place_light,
    plate_for,
)

INKS = ["#f1ece1", "#14110d", "#1d3a8a", "#d8321a", "#f3c318", "#2c6a5d", "#c2890f"]


def flat_print(seed: int = 0) -> Image.Image:
    """A synthetic flat screen print: blocks of brand ink, hard edges."""

    image = Image.new("RGB", (1536, 1024), INKS[0])
    draw = ImageDraw.Draw(image)
    for i in range(12):
        x, y = (i * 211 + seed * 37) % 1300, (i * 157 + seed * 53) % 820
        draw.rectangle((x, y, x + 240, y + 200), fill=INKS[1 + (i + seed) % 6])
    return image


def soft_gradient() -> Image.Image:
    """A photographic sky: one smooth ramp from cobalt to amber."""

    image = Image.new("RGB", (1536, 1024))
    draw = ImageDraw.Draw(image)
    for y in range(1024):
        t = y / 1023
        draw.line((0, y, 1535, y), fill=(int(29 + 211 * t), int(58 + 122 * t), int(138 - 48 * t)))
    return image


@pytest.fixture(autouse=True)
def clean_state(monkeypatch) -> Generator[None, None, None]:
    plates.reset_for_tests()
    monkeypatch.setattr(plates, "dispatcher", None)
    yield
    plates.reset_for_tests()


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    RevuePlace.__table__.create(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def painting_on(monkeypatch, tmp_path):
    """Painting allowed, the image call and the store replaced; returns the call log."""

    monkeypatch.setattr(settings, "ATELIER_SEASON_PLATES_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key-not-a-real-credential")
    calls: list[dict] = []
    queue: list[Image.Image] = []

    def fake_call(prompt: str, reference=None):
        calls.append({"prompt": prompt, "reference": reference})
        return queue.pop(0) if queue else flat_print(len(calls))

    def fake_store(place_id: str, content: bytes) -> str:
        return f"/media/graphic-novel/revue-plates/{place_id}-{len(calls)}.webp"

    monkeypatch.setattr(plates, "_call", fake_call)
    monkeypatch.setattr(revue_plates, "_store", fake_store)
    return SimpleNamespace(calls=calls, queue=queue)


# ---------------------------------------------------------------------------
# Step 1: every place has its own plate
# ---------------------------------------------------------------------------


def test_all_22_season_places_have_their_own_plate_file():
    assert len(SEASON_ONE_LOCATIONS) == 22
    plates_seen = {}
    for place_id, row in SEASON_ONE_LOCATIONS.items():
        assert row["own"] is True, f"{place_id} still borrows {row['plate']}"
        path = PUBLIC_ROOT / row["plate"]
        assert path.is_file(), f"{place_id}: {path} is missing"
        with Image.open(path) as image:
            assert image.size == (1536, 1024), place_id
        assert row["plate"] not in plates_seen, f"{place_id} shares {plates_seen.get(row['plate'])}'s plate"
        plates_seen[row["plate"]] = place_id
    for place_id in ("odile_flat", "quai_de_valmy", "stairwell", "mairie", "notaire", "toit"):
        assert plate_for(place_id) == f"/assets/serial/locations/{place_id}.webp"


def test_every_place_has_a_brief_with_its_light():
    assert set(SEASON_ONE_PLATE_BRIEFS) == set(SEASON_ONE_LOCATIONS)
    for place_id in SEASON_ONE_LOCATIONS:
        brief = place_brief(place_id)
        assert brief and len(brief.split(",")) >= 3, place_id  # name + landmarks
        time_of_day, weather = place_light(place_id)
        assert time_of_day in plates.TIMES_OF_DAY and weather in plates.WEATHERS
        assert "people" not in brief.lower()
    assert place_light("quai_de_valmy") == ("night", "rain"), "T1 opens on the quai at night in the rain"


# ---------------------------------------------------------------------------
# Step 2: light and weather
# ---------------------------------------------------------------------------


def test_light_is_closed_and_completed():
    assert plates.normalise_light(None, None) == (None, None)
    assert plates.normalise_light("teatime", "snow") == (None, None)
    assert plates.normalise_light("NIGHT", None) == ("night", "dry")
    assert plates.normalise_light(None, "rain") == ("day", "rain")


def test_variant_key_skips_the_plates_own_light_and_underground_places():
    assert plates.variant_key("quai_de_valmy", "night", "rain") is None, "the base plate is that light"
    assert plates.variant_key("quai_de_valmy", "morning", "dry") == "season:quai_de_valmy:morning:dry"
    assert plates.variant_key("metro_platform", "night", "rain") is None, "light never changes underground"
    assert plates.variant_key("odile_flat") is None
    assert plates.variant_key(None, "night", "rain") is None


def test_lookup_serves_the_base_until_the_variant_is_painted(db):
    base = "/assets/serial/locations/odile_flat.webp"
    assert plates.plate_url_for(db, "odile_flat", time_of_day="night") == base
    db.add(RevuePlace(id="season:odile_flat:night:dry", name_fr="x", brief="x", plate_url="/media/v.webp", prompt_version="t"))
    db.commit()
    plates.reset_for_tests()  # the miss above is remembered for a minute
    assert plates.plate_url_for(db, "odile_flat", time_of_day="night") == "/media/v.webp"
    assert plates.plate_url_for(db, "odile_flat", time_of_day="day") == base


def test_a_missing_variant_is_queued_once_and_never_waited_for(db, painting_on, monkeypatch):
    queued: list[plates.VariantJob] = []
    monkeypatch.setattr(plates, "dispatcher", queued.append)

    url = plates.scene_plate_url(db, "le_mistral", time_of_day="day", weather="dry")
    assert url == "/assets/serial/locations/le_mistral-counter.webp", "the base serves meanwhile"
    assert [job.key for job in queued] == ["season:le_mistral:day:dry"]
    assert painting_on.calls == [], "nothing is painted in the request"

    plates.scene_plate_url(db, "le_mistral", time_of_day="day", weather="dry")
    assert len(queued) == 1, "in flight: not queued twice"
    plates.scene_plate_url(db, "le_mistral", time_of_day="night", weather="rain")
    assert len(queued) == 1, "the counter plate is night and rain already"

    assert plates.paint_variant(queued[0]) is not None
    assert len(painting_on.calls) == 1
    assert painting_on.calls[0]["reference"] is not None, "a variant is an edit of the place's own plate"
    assert "Change only the light" in painting_on.calls[0]["prompt"]
    assert "No people" in painting_on.calls[0]["prompt"]
    painted = plates.plate_url_for(db, "le_mistral", time_of_day="day", weather="dry")
    assert painted.startswith("/media/graphic-novel/revue-plates/season-le_mistral-day-dry")
    assert db.get(RevuePlace, "season:le_mistral:day:dry") is not None

    plates.scene_plate_url(db, "le_mistral", time_of_day="day", weather="dry")
    assert len(queued) == 1, "painted: nothing more to queue"


def test_a_failed_variant_waits_an_hour_and_painting_off_queues_nothing(db, painting_on, monkeypatch):
    queued: list[plates.VariantJob] = []
    monkeypatch.setattr(plates, "dispatcher", queued.append)

    def broken(prompt, reference=None):
        raise RuntimeError("image API 500")

    monkeypatch.setattr(plates, "_call", broken)
    plates.schedule_variant(db, "toit", time_of_day="day", weather="rain")
    assert plates.paint_variant(queued[0]) is None
    assert plates.schedule_variant(db, "toit", time_of_day="day", weather="rain") is None, "not again within the hour"

    plates.reset_for_tests()
    monkeypatch.setattr(settings, "ATELIER_SEASON_PLATES_ENABLED", False)
    assert plates.schedule_variant(db, "toit", time_of_day="day", weather="rain") is None
    assert len(queued) == 1


def test_a_read_serves_the_variant_once_painted():
    from app.api.v1.endpoints.story_engine import panel_plate_url

    base = "/assets/serial/locations/quai_de_valmy.webp"
    meta = {"image_source": "setting_reference", "plate_url": base, **plates.plate_meta("quai_de_valmy", "morning", None)}
    assert meta["time_of_day"] == "morning" and meta["weather"] == "dry"
    panel = SimpleNamespace(image_url=base, generation_metadata=meta)
    assert panel_plate_url(panel) == base
    revue_plates._PAINTED["season:quai_de_valmy:morning:dry"] = "/media/morning.webp"
    assert panel_plate_url(panel) == "/media/morning.webp"


def test_an_authored_page_carries_the_light_its_direction_names():
    import json

    from app.services.season.format import SEASON_ROOT
    from app.services.season.page import project
    from app.services.season.runtime import panel_images

    assert plates.light_from_text("Night rain on the quai de Valmy.") == {"time_of_day": "night", "weather": "rain"}
    assert plates.light_from_text("Inside Le Mistral.", {"time_of_day": "night"}) == {"time_of_day": "night"}
    assert plates.light_from_text("The morning after; sunlit kitchen.") == {"time_of_day": "morning", "weather": "dry"}

    page = json.loads((SEASON_ROOT / "s1" / "t1.json").read_text(encoding="utf-8"))["days"][0]
    images = panel_images(page, project(page)["scene_panels"])
    assert images[0]["location_id"] == "quai_de_valmy"
    assert (images[0]["time_of_day"], images[0]["weather"]) == ("night", "rain")


def test_the_director_sets_light_and_weather_from_closed_sets():
    from app.services.living_story import SceneDraft

    fields = SceneDraft.model_fields
    assert "time_of_day" in fields and "weather" in fields
    validate_tod = SceneDraft._time_of_day.__func__  # type: ignore[attr-defined]
    validate_weather = SceneDraft._weather.__func__  # type: ignore[attr-defined]
    assert validate_tod(SceneDraft, "Night ") == "night"
    assert validate_tod(SceneDraft, "teatime") is None
    assert validate_weather(SceneDraft, "RAIN") == "rain"
    assert validate_weather(SceneDraft, "snow") is None


# ---------------------------------------------------------------------------
# Step 3: the style check
# ---------------------------------------------------------------------------


def test_style_check_passes_a_flat_print_and_the_committed_plates():
    assert plates.style_problem(flat_print()) is None
    for place_id in ("odile_flat", "quai_de_valmy", "le_mistral", "marche_canal"):
        with Image.open(PUBLIC_ROOT / SEASON_ONE_LOCATIONS[place_id]["plate"]) as image:
            assert plates.style_problem(image.convert("RGB")) is None, place_id


def test_style_check_catches_gradients_and_photographic_colour():
    gradient = soft_gradient()
    assert plates.style_problem(revue_plates.palette_lock(gradient), gradient) == "gradients"
    grey_green = Image.new("RGB", (1536, 1024), (120, 160, 120))
    assert plates.style_problem(grey_green) == "off_palette"


def test_a_drifted_plate_is_painted_once_more_and_the_flatter_kept(painting_on):
    painting_on.queue.extend([soft_gradient(), flat_print(3)])
    image, info = plates.paint_checked("a prompt", label="test")
    assert info["calls"] == 2 and info["problem"] == "gradients" and info["kept"] == "second"
    assert plates.style_problem(image) is None

    painting_on.calls.clear()
    painting_on.queue.extend([flat_print(1)])
    _image, info = plates.paint_checked("a prompt", label="test")
    assert info["calls"] == 1 and info["problem"] is None
