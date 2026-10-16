"""WP-119 §8.4: the story's own picture in the Papier's learning loop.

The picture is painted once at intake (``plates.paint_story``; here a ``revue_story_pictures``
row, no image call). A learner then starts the Papier, and the picture carries the loop:

* the stage shows it with the words it shows, glossed (never the desk's caption: that is the
  answer of «La légende»);
* Romy points at it on arrival («Regarde : …», a ``look`` line with those words glossed);
* its words lead the plan's vocabulary, so the close keeps them in the learner's review,
  where the plan's plate (``plan.stage.plate_url``, La Carte, the review card) is the picture;
* «La légende» is a make option: A1–A2 choose the caption the picture shows among three, B1+
  write it, graded by the rubric with the picture's words as target words;
* the dispatch prints the picture under the learner's caption, Le Relevé keeps both, and
  Romy remembers it.

Without a painted picture nothing changes (the place plate, no look line, no caption).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from pydantic import TypeAdapter
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.models.npc import NPCMemory
from app.db.models.revue_place import RevuePlace
from app.db.models.revue_session import RevueDossier, RevueSession
from app.db.models.revue_story_picture import RevueStoryPicture
from app.schemas.revue import RvCaptionMake, RvMakeRequest
from app.services.revue import encounter as enc
from app.services.revue import grading, plates, policy
from app.services.revue.dossier import EditorialDossier, Place, StoryVisual, VisualWord
from app.services.revue.encounter import MAKE_DONE_LINES, FakeRevueProvider, RevueEncounter
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.releve import releve_for
from app.services.revue.vignette import ring_for
from app.services.season.world import plate_for
from tests.test_revue_encounter import MARCHE, PRICE_QUESTION, REVUE_TABLES, WEEK, make_user

PICTURE_URL = "/media/graphic-novel/revue-stories/evergreen-marche-du-dimanche-0123456789abcdef.webp"
VISUAL = StoryVisual(
    moment="a busy morning at the open-air market: stallholders weigh vegetables while shoppers wait with baskets",
    symbol="a single wooden crate of clementines glowing in the middle of the square",
    viewpoint="from the corner of the square, behind the last stall",
    light="cool early morning light",
    words=[
        VisualWord(fr="le marché en plein air", shows="the stalls under striped awnings in the square"),
        VisualWord(fr="le marché couvert", shows="the old covered market hall behind the stalls"),
    ],
    caption_fr="Le marché d'Aligre, un matin, à Paris.",
    look_fr="Regarde : le marché en plein air, et derrière, le marché couvert.",
    decoys_fr=["Le marché d'Aligre, fermé, un soir de pluie.", "Un supermarché vide, le soir."],
)
PICTURE_WORDS = ["le marché en plein air", "le marché couvert"]


@pytest.fixture(scope="module")
def tables(db_engine) -> Generator[None, None, None]:
    wanted = (*REVUE_TABLES, RevuePlace.__table__, RevueStoryPicture.__table__, RevueDossier.__table__)
    created = [table for table in wanted if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, tables) -> Generator[Session, None, None]:
    yield db_session
    db_session.rollback()
    db_session.query(RevueStoryPicture).delete()
    db_session.query(RevueDossier).delete()
    db_session.commit()


def pictured(**update) -> EditorialDossier:
    dossier = next(d for d in evergreens_for_week(WEEK) if d.id == MARCHE).model_copy(deep=True)
    return dossier.model_copy(update={"visual": VISUAL.model_copy(update=update)})


@pytest.fixture()
def dossier(monkeypatch) -> EditorialDossier:
    plates._STORIES.clear()
    story = pictured()
    monkeypatch.setattr(enc, "available_dossiers", lambda week, db=None: [story])
    yield story
    plates._STORIES.clear()


def paint(db: Session, dossier: EditorialDossier) -> None:
    """What ``plates.paint_story`` leaves behind, without the image call."""

    db.add(RevueStoryPicture(dossier_id=dossier.id, place_id=dossier.places[0].id, picture_url=PICTURE_URL,
                             caption_fr=VISUAL.caption_fr, prompt="(the story prompt)",
                             prompt_version=plates.STORY_PROMPT_VERSION))
    db.commit()


# ---------------------------------------------------------------------------
# Arrival: the stage, Romy's look line, the vocabulary
# ---------------------------------------------------------------------------


def test_the_stage_shows_the_picture_with_its_words_and_romy_points_at_it(db: Session, dossier) -> None:
    paint(db, dossier)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    view = revue.view(row)

    stage = view.stage
    assert (stage.plate_url, stage.plate_kind) == (PICTURE_URL, "story")
    assert VISUAL.caption_fr not in view.model_dump_json(), "the caption is the answer of «La légende»: never sent before"
    assert stage.place_is_real is True
    assert [w.fr for w in stage.picture_words] == PICTURE_WORDS
    assert all(w.gloss.endswith("(de)") for w in stage.picture_words), "glossed in the learner's language"

    kinds = [(item.kind, getattr(item, "role", None)) for item in view.thread]
    look_at = kinds.index(("line", "look"))
    assert kinds[:look_at] == [("narration", None), ("narration", None)], "Romy points at it once the scene is set"
    assert kinds.index(("line", "purpose")) > look_at
    look = view.thread[look_at]
    assert look.text_fr == "Regarde : le marché en plein air, et derrière, le marché couvert."
    assert {g.fr for g in look.glosses} >= set(PICTURE_WORDS)

    assert [w.fr for w in view.plan.vocabulary][:2] == PICTURE_WORDS, "the picture's words lead the vocabulary"
    assert "caption" in view.plan.make_options
    assert RevueSession.plan.property.columns  # (the plan below is the stored one)
    stored = db.get(RevueSession, row.id).plan
    assert stored["stage"]["plate_url"] == PICTURE_URL, "La Carte and the review show the picture"


def test_the_band_moves_on_before_the_picture_is_printed(db: Session, dossier) -> None:
    """«La légende» and the dispatch print the picture in full, so by then the band above them
    shows the site's own plate (§12.7's switch, at make here): the picture never shows twice."""
    paint(db, dossier)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    stage = revue.view(row).stage
    assert (stage.plate_url, stage.plate_url_second, stage.plate_switched) == (PICTURE_URL, plate_for("marche_canal"), False)
    revue.turn(row, "D'accord, je t'aide.")
    assert revue.view(row).stage.plate_switched is False, "the picture stays on while Romy reports"
    caption = next(option for option in revue.make_options(row).options if option.kind == "caption")
    revue.make(row, "caption", {"action": "caption", "option_id": caption.options[0].id})
    stage = revue.view(row).stage
    assert (stage.plate_url, stage.plate_switched) == (PICTURE_URL, True), "the site is still the picture"

    # A second place stays the second view.
    cafe = Place(id="cafe_rue_aligre", name_fr="Un café de la rue d'Aligre", brief="a café terrace, a zinc counter inside")
    two = dossier.model_copy(update={"places": [dossier.places[0], cafe]})
    assert enc.stage_for(two, db=db).plate_url_second == plate_for(policy.fallback_place_for("cafe"))


def test_without_the_picture_nothing_changes(db: Session, dossier) -> None:
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    view = revue.view(row)
    assert view.stage.plate_kind == "stand_in" and view.stage.picture_words == []
    assert not [item for item in view.thread if getattr(item, "role", None) == "look"]
    assert "caption" not in view.plan.make_options
    assert all(option.kind != "caption" for option in revue.make_options(row).options)


def test_a_look_line_is_made_from_the_words_when_the_builder_wrote_none(db: Session, monkeypatch) -> None:
    plates._STORIES.clear()
    story = pictured(look_fr=None)
    monkeypatch.setattr(enc, "available_dossiers", lambda week, db=None: [story])
    paint(db, story)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    look = next(item for item in revue.view(row).thread if getattr(item, "role", None) == "look")
    assert look.text_fr == "Regarde : le marché en plein air, le marché couvert."
    plates._STORIES.clear()


# ---------------------------------------------------------------------------
# «La légende»
# ---------------------------------------------------------------------------


def test_a2_chooses_the_caption_the_picture_shows(db: Session, dossier) -> None:
    paint(db, dossier)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    offer = revue.make_options(row)
    assert offer.recommended == "caption", "the story's own picture: its caption leads"
    assert offer.intro is not None and offer.intro.text_fr == enc.MAKE_INTRO_LINES["caption"]
    caption = next(option for option in offer.options if option.kind == "caption")
    assert caption.format == "choice" and caption.picture_url == PICTURE_URL
    assert sorted(o.text_fr for o in caption.options) == sorted([VISUAL.caption_fr, *VISUAL.decoys_fr])
    assert [w.fr for w in caption.words] == PICTURE_WORDS
    assert "answer" not in caption.model_dump(), "the answer never leaves the server"
    # Built from the session id: the same three, in the same order, on every read.
    assert revue.make_options(row).options[-1].options == caption.options

    wrong = next(o.id for o in caption.options if o.text_fr != VISUAL.caption_fr)
    result = revue.make(row, "caption", {"action": "caption", "option_id": wrong})
    assert (result.format, result.accepted, result.correct) == ("choice", True, False)
    assert result.made.text_fr == VISUAL.caption_fr and result.made.contribution == []
    assert result.line.text_fr == MAKE_DONE_LINES["caption_wrong"]
    assert next(o.text_fr for o in caption.options if o.id == result.answer_id) == VISUAL.caption_fr

    _, closing = revue.close(row)
    dispatch = closing.dispatch
    assert (dispatch.picture_url, dispatch.caption_fr) == (PICTURE_URL, VISUAL.caption_fr)
    assert dispatch.caption_by_learner is False, "a wrong pick prints the desk's caption"
    assert dispatch.headline_fr != VISUAL.caption_fr, "a caption is not a headline"
    assert closing.vignette is None or closing.vignette.ring == "headline"


def test_a_right_pick_is_the_learners_caption(db: Session, dossier) -> None:
    paint(db, dossier)
    revue = RevueEncounter(db, FakeRevueProvider())
    user = make_user(db, level="A1.2")
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    caption = next(option for option in revue.make_options(row).options if option.kind == "caption")
    right = next(o.id for o in caption.options if o.text_fr == VISUAL.caption_fr)
    result = revue.make(row, "caption", {"action": "caption", "option_id": right})
    assert result.correct is True and result.made.contribution == [(0, len(VISUAL.caption_fr))]
    assert result.line.text_fr == MAKE_DONE_LINES["caption"]
    _, closing = revue.close(row)
    assert closing.dispatch.caption_by_learner is True
    assert closing.romy_line_fr
    memory = db.scalars(select(NPCMemory).where(NPCMemory.user_id == user.id)).all()[-1]
    assert f"Tu as choisi la légende de l'image : « {VISUAL.caption_fr} »." in memory.content


def test_b1_writes_the_caption_graded_with_the_picture_words(db: Session, dossier) -> None:
    paint(db, dossier)
    revue = RevueEncounter(db, FakeRevueProvider())
    user = make_user(db, level="B1.1")
    row = revue.start(user, WEEK, dossier_id=MARCHE)
    caption = next(option for option in revue.make_options(row).options if option.kind == "caption")
    assert caption.format == "write" and caption.options == []
    assert caption.max_words == grading.CAPTION_WORDS["B1"][1]

    text = "Le marché en plein air d'Aligre, un matin, devant le marché couvert."
    result = revue.make(row, "caption", {"action": "caption", "text_fr": text})
    assert (result.format, result.accepted) == ("write", True)
    assert result.evidence is not None and result.evidence.fact_fit != "contradicted"
    assert result.made.text_fr == text and result.made.learner_fr == text
    assert set(PICTURE_WORDS) <= {w.fr for w in result.evidence.words}
    critic_rubric, _ = revue.scorer.calls[-1] if getattr(revue.scorer, "calls", None) else (None, None)
    if critic_rubric is not None:
        assert critic_rubric.kind == "caption"
        assert {"id": "picture", "kind": "fact", "fr": VISUAL.caption_fr} in critic_rubric.claims

    _, closing = revue.close(row)
    assert (closing.dispatch.caption_fr, closing.dispatch.caption_by_learner) == (text, True)
    kept = {w.fr: w for w in closing.kept.words}
    assert set(PICTURE_WORDS) <= set(kept), "the picture's words are kept for the review"
    assert kept["le marché couvert"].used is True
    memory = db.scalars(select(NPCMemory).where(NPCMemory.user_id == user.id)).all()[-1]
    assert f"Tu as écrit la légende de l'image : « {text} »." in memory.content

    entry = releve_for(db, user).entries[0]
    assert (entry.picture_url, entry.caption_fr, entry.caption_by_learner) == (PICTURE_URL, text, True), "Le Relevé keeps it"


def test_a_caption_a_claim_contradicts_is_refused_and_nothing_is_filed(db: Session, dossier) -> None:
    paint(db, dossier)
    scorer = grading.FakeRubricScorer(script=[{"words": [], "fact_fit": "contradicted", "register": "ok", "band_fit": "at"}])
    revue = RevueEncounter(db, FakeRevueProvider(), scorer=scorer)
    row = revue.start(make_user(db, level="B2.1"), WEEK, dossier_id=MARCHE)
    result = revue.make(row, "caption", {"action": "caption", "text_fr": "Le marché d'Aligre est fermé le matin."})
    assert (result.accepted, result.made) == (False, None)
    assert result.line.text_fr == MAKE_DONE_LINES["caption_refused"]
    assert revue.view(row).artifact is None


def test_the_caption_needs_the_picture_and_at_a1_a2_the_two_decoys(db: Session, monkeypatch) -> None:
    plates._STORIES.clear()
    story = pictured(decoys_fr=[])
    monkeypatch.setattr(enc, "available_dossiers", lambda week, db=None: [story])
    paint(db, story)
    revue = RevueEncounter(db, FakeRevueProvider())
    a2 = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    assert "caption" not in revue.view(a2).plan.make_options
    with pytest.raises(enc.RevueError) as refused:
        revue.make(a2, "caption", {"action": "caption", "option_id": "l1"})
    assert refused.value.code == "revue_make_unavailable"
    b1 = revue.start(make_user(db, level="B1.2"), WEEK, dossier_id=MARCHE)
    assert "caption" in revue.view(b1).plan.make_options
    plates._STORIES.clear()


def test_the_caption_does_not_lead_twice_in_a_row(db: Session, dossier) -> None:
    paint(db, dossier)
    revue = RevueEncounter(db, FakeRevueProvider())
    user = make_user(db, level="A2.1")
    first = revue.start(user, WEEK, dossier_id=MARCHE)
    caption = next(option for option in revue.make_options(first).options if option.kind == "caption")
    revue.make(first, "caption", {"action": "caption", "option_id": caption.options[0].id})
    revue.close(first)

    second = revue.start(user, "2026-W41", dossier_id=MARCHE)
    revue.turn(second, "D'accord, je t'aide.")
    offer = revue.make_options(second)
    assert any(option.kind == "caption" for option in offer.options), "still offered"
    assert offer.recommended == "headline_choice", "the last Papier was a caption: something else leads"


def test_an_open_question_still_leads(db: Session, dossier) -> None:
    paint(db, dossier)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    revue.turn(row, PRICE_QUESTION)
    assert revue.make_options(row).recommended == "reader_question"


def test_a_picture_painted_during_the_session_is_printed_and_becomes_the_plan_plate(db: Session, dossier) -> None:
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(make_user(db), WEEK, dossier_id=MARCHE)
    assert db.get(RevueSession, row.id).plan["stage"]["plate_url"] != PICTURE_URL
    paint(db, dossier)
    _, closing = revue.close(row)
    assert (closing.dispatch.picture_url, closing.dispatch.caption_fr) == (PICTURE_URL, VISUAL.caption_fr)
    db.expire_all()
    assert db.get(RevueSession, row.id).plan["stage"]["plate_url"] == PICTURE_URL


# ---------------------------------------------------------------------------
# The wire
# ---------------------------------------------------------------------------


def test_the_caption_request_parses_and_rings_like_a_headline() -> None:
    request = TypeAdapter(RvMakeRequest).validate_python({"kind": "caption", "action": "caption", "option_id": "l2"})
    assert isinstance(request, RvCaptionMake) and request.option_id == "l2" and request.text_fr is None
    written = TypeAdapter(RvMakeRequest).validate_python({"kind": "caption", "action": "caption", "text_fr": "Le marché."})
    assert written.text_fr == "Le marché."
    assert ring_for("caption") == "headline"


# ---------------------------------------------------------------------------
# §8.4 v2: dossiers briefed under the old picture rules get a fresh brief before painting
# ---------------------------------------------------------------------------


class Desk:
    def __init__(self) -> None:
        self.calls = 0

    def ask_json(self, *_: object, **__: object) -> dict:
        self.calls += 1
        return {"visual": {**VISUAL.model_dump(mode="json"), "kind": "editorial",
                           "symbol": "a crate of clementines on a scale tipping into the red"}}


def stored(db: Session, dossier: EditorialDossier, *, version: str, period: str = "2026-W42") -> RevueDossier:
    row = RevueDossier(id=f"{period.lower()}-{dossier.id}"[:120], week=period, period=period, topic=dossier.topic,
                       payload=dossier.model_dump(mode="json"), source_hashes={}, checks={}, builder_version=version)
    db.add(row)
    db.commit()
    return row


def test_a_dossier_briefed_under_the_old_rules_is_rebriefed_once_before_painting(db: Session) -> None:
    from app.services.revue.builder import BUILDER_VERSION

    plates._STORIES.clear()
    built = pictured().model_copy(update={"id": "2026-w42-marche", "evergreen": False})
    row = stored(db, built, version="revue-builder-v2")
    desk = Desk()
    assert plates.rebrief_stale_visuals(db, "2026-W42", provider=desk) == ["2026-w42-marche"]
    db.refresh(row)
    assert row.builder_version == BUILDER_VERSION and row.payload["visual"]["kind"] == "editorial"
    # Briefed under the current rules now: never asked again.
    assert plates.rebrief_stale_visuals(db, "2026-W42", provider=desk) == [] and desk.calls == 1


def test_a_painted_story_keeps_the_brief_its_picture_was_painted_from(db: Session) -> None:
    plates._STORIES.clear()
    built = pictured().model_copy(update={"id": "2026-w42-marche", "evergreen": False})
    stored(db, built, version="revue-builder-v2")
    paint(db, built)
    desk = Desk()
    assert plates.rebrief_stale_visuals(db, "2026-W42", provider=desk) == [] and desk.calls == 0
    plates._STORIES.clear()
