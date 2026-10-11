"""WP-119 phase 4 «Les planches»: plates for new places (``app/services/revue/plates.py``).

No image call is made here: ``plates._call`` is replaced by a fake that counts calls and
returns a synthetic image. The rules under test: the brief rule (name + three landmarks
+ light, the place entity's name), the Render check's ``brief_without_place_name``, the
plate the stage shows (season plate, painted plate, stand-in with its marker), one paint
per place forever, the flag post-check, and the second view switched at the guest's
entrance or at ``make`` (§12.7).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.revue_place import RevuePlace
from app.services.revue import checks, plates, policy
from app.services.revue import encounter as enc
from app.services.revue.dossier import EditorialDossier, Place
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.session import LearnerContext, plan_for
from app.services.season.world import plate_for
from tests.test_revue_encounter import (
    MARCHE,
    PRICE_QUESTION,
    REVUE_TABLES,
    WEEK,
    make_user,
)

ALIGRE_BRIEF = (
    "le marché d'Aligre, place d'Aligre, 12e: the stalls in the small square, the brocante tables of "
    "books and crockery, the low marché Beauvau hall with its tiled roof and iron-and-glass lantern, "
    "the rue d'Aligre with its cafés, cool morning light"
)


@pytest.fixture(scope="module")
def plate_tables(db_engine) -> Generator[None, None, None]:
    tables = (*REVUE_TABLES, RevuePlace.__table__)
    created = [table for table in tables if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, plate_tables) -> Generator[Session, None, None]:
    yield db_session
    db_session.rollback()
    db_session.query(RevuePlace).delete()
    db_session.commit()


@pytest.fixture(autouse=True)
def clean_memo(monkeypatch) -> Generator[None, None, None]:
    plates._PAINTED.clear()
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    yield
    plates._PAINTED.clear()


class FakeImages:
    """Stands in for ``plates._call``: counts calls, returns the queued images (plain by default)."""

    def __init__(self, *queue: Image.Image) -> None:
        self.queue = list(queue)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> Image.Image:
        self.prompts.append(prompt)
        return self.queue.pop(0) if self.queue else plain_plate()


def plain_plate() -> Image.Image:
    """A calm plate: paper sky, a cobalt facade on the left, a red awning low on the right."""

    image = Image.new("RGB", (1536, 1024), (241, 236, 225))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 300, 500, 1024), fill=(29, 58, 138))
    draw.rectangle((1000, 760, 1536, 860), fill=(216, 50, 26))
    draw.rectangle((0, 900, 1536, 1024), fill=(44, 106, 93))
    return image


def tricolour_plate() -> Image.Image:
    """The press room the feasibility run got: a big tricolour hanging behind the podium."""

    image = Image.new("RGB", (1536, 1024), (194, 137, 15))
    draw = ImageDraw.Draw(image)
    left, top, stripe, height = 560, 120, 140, 360
    draw.rectangle((left, top, left + stripe, top + height), fill=(0, 35, 149))
    draw.rectangle((left + stripe, top, left + 2 * stripe, top + height), fill=(250, 250, 250))
    draw.rectangle((left + 2 * stripe, top, left + 3 * stripe, top + height), fill=(237, 41, 57))
    return image


def marche() -> EditorialDossier:
    dossier = next(d for d in evergreens_for_week(WEEK) if d.id == MARCHE).model_copy(deep=True)
    # The stored brief names the place since 2026-10-03; these tests need the type-only brief.
    place = dossier.places[0]
    generic = place.brief.split(": ", 1)[1] if ": " in place.brief else place.brief
    dossier.places[0] = place.model_copy(update={"brief": generic})
    return dossier


def with_places(dossier: EditorialDossier, *places: Place) -> EditorialDossier:
    copy = dossier.model_copy(deep=True)
    copy.places = list(places)
    return copy


@pytest.fixture()
def flag_on(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "REVUE_PLATE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_STORAGE", "local")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# The prompt and the brief rule (§8.1)
# ---------------------------------------------------------------------------


def test_the_revue_style_carries_the_people_clause_and_the_negative_clause() -> None:
    prompt = plates.prompt_for("le marché d'Aligre, the stalls, the hall, morning light")
    assert "No people" not in prompt
    assert policy.PLATE_PEOPLE_CLAUSE in prompt
    assert prompt.endswith(policy.PLATE_NEGATIVE)
    assert "France, seen from where a visitor would stand." in prompt
    assert plates._art().PALETTE_WORDS in prompt


def test_the_brief_rule_refuses_a_place_entity_without_its_name() -> None:
    dossier = marche()
    generic = dossier.places[0]  # "an open-air market square…": a type, not Aligre
    with pytest.raises(plates.PlateBriefError) as refused:
        plates.brief_for(generic, dossier)
    assert refused.value.reason == "brief_without_place_name"
    assert refused.value.detail["missing"] == ["Marché d'Aligre"]
    named = generic.model_copy(update={"brief": ALIGRE_BRIEF + "."})
    assert plates.brief_for(named, dossier) == ALIGRE_BRIEF  # normalised: no trailing period


@pytest.mark.parametrize(
    ("brief", "reason"),
    [
        ("", "empty_brief"),
        ("le marché d'Aligre, a portrait of a stallholder, morning light", "forbidden_words"),
        ("le marché d'Aligre in the morning light", "brief_too_thin"),
        ("le marché d'Aligre, the stalls, the Beauvau hall, the rue d'Aligre", "brief_without_light"),
    ],
)
def test_the_brief_rule_reasons(brief: str, reason: str) -> None:
    place = marche().places[0].model_copy(update={"brief": brief})
    with pytest.raises(plates.PlateBriefError) as refused:
        plates.brief_for(place, marche())
    assert refused.value.reason == reason


def test_a_typed_private_place_needs_no_name() -> None:
    kitchen = Place(
        id="cuisine_facture_gaz",
        name_fr="Une petite cuisine",
        brief="a small apartment kitchen, an old gas stove and a kettle, an open bill on the table, grey morning light",
    )
    assert plates.brief_for(kitchen, marche()).startswith("a small apartment kitchen")


def test_check_render_emits_brief_without_place_name() -> None:
    dossier = marche()
    plan = plan_for(dossier, LearnerContext(band="A2", ui_language="en"))
    kwargs = {"known_places": {"marche_canal"}, "props": {"notebook"},
              "cast_ids": {"romy_tremblay", "margaux_barman"}, "camille_chosen": False}
    plan.stage.plate_url = "/assets/serial/locations/marche_canal.webp"
    failed = checks.check_render(plan, dossier=dossier, **kwargs)
    assert [r.reason for r in failed] == ["brief_without_place_name"]
    assert failed[0].detail["place_id"] == "marche_aligre"
    assert failed[0].detail["missing"] == ["Marché d'Aligre"]
    fixed = with_places(dossier, dossier.places[0].model_copy(update={"brief": ALIGRE_BRIEF}))
    assert [r.ok for r in checks.check_render(plan, dossier=fixed, **kwargs)] == [True]
    # Without a dossier the check is what it was.
    assert [r.ok for r in checks.check_render(plan, **kwargs)] == [True]


def test_a_glued_name_counts_as_named() -> None:
    longchamp = Place(id="hippodrome_longchamp", name_fr="L'hippodrome de ParisLongchamp",
                      brief="the Paris Longchamp racecourse, the cantilevered grandstand, the moulin, soft afternoon light")
    dossier = marche().model_copy(deep=True)
    dossier.entities = [*dossier.entities, dossier.entities[0].model_copy(update={"name": "ParisLongchamp"})]
    assert checks.brief_missing_place_names(longchamp.id, longchamp.name_fr, longchamp.brief, dossier) == []
    assert checks.brief_missing_place_names(
        longchamp.id, longchamp.name_fr, "an empty racecourse, a grandstand, a windmill, soft light", dossier
    ) == ["ParisLongchamp"]


# ---------------------------------------------------------------------------
# What the stage shows
# ---------------------------------------------------------------------------


def test_plate_for_place_returns_the_season_plate_for_a_known_id(db: Session, monkeypatch) -> None:
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    choice = plates.plate_for_place(db, Place(id="buttes_chaumont", name_fr="Les Buttes-Chaumont"))
    assert choice == plates.PlateChoice(url=plate_for("buttes_chaumont"), plate_place_id="buttes_chaumont", stand_in=False)
    assert fake.prompts == []


def test_plate_for_place_returns_the_cache_for_a_painted_id(db: Session, monkeypatch) -> None:
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    monkeypatch.setattr(settings, "REVUE_PLATE_GENERATION_ENABLED", False)
    db.add(RevuePlace(id="marche_aligre", name_fr="Le marché d'Aligre", brief=ALIGRE_BRIEF,
                      plate_url="/media/graphic-novel/revue-plates/marche_aligre-abc.webp",
                      prompt_version=plates.PROMPT_VERSION))
    db.commit()
    choice = plates.plate_for_place(db, marche().places[0])
    assert choice.url == "/media/graphic-novel/revue-plates/marche_aligre-abc.webp"
    assert choice.stand_in is False and choice.plate_place_id == "marche_aligre"
    assert fake.prompts == [], "a painted plate is served even with the flag off, and never repainted"


def test_plate_for_place_stands_in_with_a_marker_when_the_flag_is_off(db: Session, monkeypatch) -> None:
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    monkeypatch.setattr(settings, "REVUE_PLATE_GENERATION_ENABLED", False)
    choice = plates.plate_for_place(db, marche().places[0])
    assert choice.stand_in is True
    assert choice.plate_place_id == policy.fallback_place_for("market") == "marche_canal"
    assert choice.url == plate_for("marche_canal")
    assert fake.prompts == []
    # The stage says so, and Romy's place_note tells where they really are.
    stage = enc.stage_for(marche(), db=db)
    assert stage.place_is_real is False and stage.plate_place_id == "marche_canal"


def test_paint_refuses_while_the_flag_is_off(db: Session, monkeypatch) -> None:
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    monkeypatch.setattr(settings, "REVUE_PLATE_GENERATION_ENABLED", False)
    with pytest.raises(plates.PlateGenerationOff):
        plates.paint(db, "marche_aligre", ALIGRE_BRIEF)
    assert fake.prompts == []
    assert db.get(RevuePlace, "marche_aligre") is None


def test_paint_stores_a_row_and_never_repaints(db: Session, monkeypatch, flag_on) -> None:
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    url = plates.paint(db, "marche_aligre", ALIGRE_BRIEF, name_fr="Le marché d'Aligre")
    assert url.startswith(settings.GRAPHIC_NOVEL_LOCAL_IMAGE_URL_PREFIX.rstrip("/") + "/revue-plates/marche_aligre-")
    assert url.endswith(".webp")
    stored = list((flag_on / "revue-plates").glob("marche_aligre-*.webp"))
    assert len(stored) == 1 and Image.open(stored[0]).size == (1536, 1024)
    row = db.get(RevuePlace, "marche_aligre")
    assert (row.plate_url, row.brief, row.prompt_version) == (url, ALIGRE_BRIEF, plates.PROMPT_VERSION)
    assert len(fake.prompts) == 1 and ALIGRE_BRIEF in fake.prompts[0]

    plates._PAINTED.clear()  # a fresh process: the row, not the memo, answers
    assert plates.paint(db, "marche_aligre", "another brief, entirely, at night") == url
    assert len(fake.prompts) == 1
    assert plates.plate_for_place(db, marche().places[0]).url == url


def test_a_flag_band_is_dropped_and_painted_once_more(db: Session, monkeypatch, flag_on) -> None:
    fake = FakeImages(tricolour_plate(), plain_plate())
    monkeypatch.setattr(plates, "_call", fake)
    plates.paint(db, "salle_de_presse", "the press room of the Élysée, an empty podium, gilded mouldings, soft daylight")
    assert len(fake.prompts) == 2


def test_paint_dossier_places_refuses_a_brief_without_the_name(db: Session, monkeypatch, flag_on) -> None:
    fake = FakeImages()
    monkeypatch.setattr(plates, "_call", fake)
    out = plates.paint_dossier_places(db, marche())
    assert out == {"marche_aligre": "brief_without_place_name"}
    assert fake.prompts == []


# ---------------------------------------------------------------------------
# The post-check (§8.1 feasibility)
# ---------------------------------------------------------------------------


def test_looks_wrong_fires_on_a_tricolour_band() -> None:
    assert plates.looks_wrong(tricolour_plate()) is True
    assert plates.looks_wrong(tricolour_plate().transpose(Image.Transpose.FLIP_LEFT_RIGHT)) is True


def test_looks_wrong_stays_quiet_on_a_plain_plate() -> None:
    assert plates.looks_wrong(plain_plate()) is False
    assert plates.looks_wrong(Image.new("RGB", (1536, 1024), (241, 236, 225))) is False


def test_a_tricolour_low_and_small_is_not_a_flag() -> None:
    image = Image.new("RGB", (1536, 1024), (241, 236, 225))
    draw = ImageDraw.Draw(image)
    for i, colour in enumerate(((0, 35, 149), (250, 250, 250), (237, 41, 57))):
        draw.rectangle((700 + 20 * i, 940, 720 + 20 * i, 1000), fill=colour)
    assert plates.looks_wrong(image) is False


# ---------------------------------------------------------------------------
# Two places per dossier (§12.7)
# ---------------------------------------------------------------------------

SECOND_VIEW = Place(
    id="cafe_rue_aligre",
    name_fr="Un café de la rue d'Aligre",
    brief="a café terrace on the rue d'Aligre, a zinc counter inside, small round tables, morning light",
)


def two_place_marche() -> EditorialDossier:
    dossier = marche()
    return with_places(dossier, dossier.places[0], SECOND_VIEW)


def test_stage_for_gives_both_plates_and_starts_on_the_site(db: Session) -> None:
    stage = enc.stage_for(two_place_marche(), db=db)
    assert stage.plate_url == plate_for("marche_canal")
    assert stage.plate_url_second == plate_for(policy.fallback_place_for("cafe")) == plate_for("le_mistral")
    assert stage.plate_switched is False
    one = enc.stage_for(marche(), db=db)
    assert one.plate_url_second is None and one.plate_switched is False


def test_the_stage_switches_at_the_guests_entrance(db: Session, monkeypatch) -> None:
    dossier = two_place_marche()
    monkeypatch.setattr(enc, "available_dossiers", lambda week: [dossier])
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    assert revue.view(row).stage.plate_switched is False
    revue.turn(row, "D'accord, je t'aide.")
    assert revue.view(row).stage.plate_switched is False
    revue.turn(row, PRICE_QUESTION)  # Margaux enters on «prix»
    stage = revue.view(row).stage
    assert [m.id for m in stage.cast] == ["romy_tremblay", "margaux_barman", "user"], "the cast keeps its place"
    assert stage.plate_switched is True
    assert stage.plate_url == plate_for("marche_canal") and stage.plate_url_second == plate_for("le_mistral")


def test_the_stage_switches_at_make_when_no_guest_came(db: Session, monkeypatch) -> None:
    dossier = two_place_marche()
    monkeypatch.setattr(enc, "available_dossiers", lambda week: [dossier])
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    assert revue.view(row).stage.plate_switched is False
    offer = revue.make_options(row)
    headline = next(option for option in offer.options if option.kind == "headline_choice")
    revue.make(row, "headline_choice", {"action": "pick", "option_id": headline.options[0].id})
    view = revue.view(row)
    assert not [item for item in view.thread if item.kind == "guest"]
    assert view.stage.plate_switched is True


def test_looks_wrong_on_the_real_plates() -> None:
    """Calibration: the feasibility press room's draped tricolour fires; the season plates
    (blue chairs beside a red box, a red lamp before blue roofs) and the striped market
    awning of the phase-4 evidence do not."""

    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    assert plates.looks_wrong(Image.open(repo / "docs/design-reference/revue/plates/salle_de_presse.webp")) is True
    quiet = sorted((repo / "web-frontend/public/assets/serial/locations").glob("*.webp"))
    quiet += [repo / "docs/design-reference/revue/plates" / f"{name}.webp"
              for name in ("hemicycle_assemblee", "quai_metro_greve", "people_minister_generic", "aligre_generic")]
    evidence = repo / "docs/design-reference/revue/plates/phase4/etal_fruits_legumes.webp"
    if evidence.exists():
        quiet.append(evidence)
    assert [path.name for path in quiet if plates.looks_wrong(Image.open(path))] == []
