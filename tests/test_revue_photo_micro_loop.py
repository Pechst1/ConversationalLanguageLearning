"""«La photo» and «Le micro» (owner 2026-11-21): the loops (``photo_loop.py``, ``micro_loop.py``)
on the shared act route.

The dealer rotates six shapes (never the last two) and deals «La photo» only on a story whose
gallery holds the two pictures its desk was written against. «Le micro»: three holes chosen,
three turns; the question's word and content words pick the fact deterministically; a shrug
does not spend the turn the first time; a slip in a question's form gets its answer and waits
for «Relis tes questions», never shown during the interview; only an ambiguous question asks the
model, which picks among the stored facts or none; the notes from the witness's lines; Romy's
edit of the questions, the fix first; «La page» as Q&A with its sources; the witness remembers.
«La photo»: the picture for the headline and what it shows in two tries each, never the answer
before the second; the caption with the wrong fact, then what is wrong; the learner's caption
(A1 tiles without a model call, B1 two sentences with Romy's marks); «La page» with the picture
and its credit. Acts idempotent, 409 out of order, nothing leaks, the switch off changes nothing.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.revue import get_revue_provider
from app.config import settings
from app.db.models.npc import NPC, NPCMemory
from app.db.models.pilot_event import PilotEvent
from app.db.models.revue_session import RevueDossier, RevueSession
from app.db.models.revue_story_media import RevueStoryMedia
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.story import Story
from app.db.models.user import User
from app.main import create_app
from app.schemas.revue import RvRubriqueRequest
from app.services.revue import assignments, comptoir, micro, micro_loop, photo, photo_loop
from app.services.revue import encounter as enc
from app.services.revue import intox as intox_desk
from app.services.revue import titre as titre_desk
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter, RevueError
from app.services.revue.evergreen import evergreen_micro, evergreen_photo, evergreens_for_week
from app.services.revue.pictogram import FakePictogramProvider
from app.services.revue.state import ConversationState

WEEK = "2026-W25"
FETE = "evergreen-fete-de-la-musique"
REVUE_TABLES = (
    Story.__table__,
    NPC.__table__,
    NPCMemory.__table__,
    RevueSession.__table__,
    RevueDossier.__table__,
    RevueStoryMedia.__table__,
    RevuePictogram.__table__,
    RevueVignette.__table__,
    PilotEvent.__table__,
)
SIX = ["comptoir", "fil", "titre", "intox", "photo", "micro"]


@pytest.fixture(scope="module")
def revue_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in REVUE_TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def switches(monkeypatch) -> None:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_PHOTOS_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_PHOTOS_PER_STORY", 3)
    comptoir.forget_cache()


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def seed_photos(db: Session, dossier_id: str = FETE, *, subjects: tuple[tuple[str, str | None], ...] | None = None) -> None:
    """The story's Commons photos as the morning would store them (``photos.store_photos``)."""

    rows = subjects or (("Paris", "Paris"), ("guitare acoustique vue de face", None))
    for position, (subject, caption) in enumerate(rows, start=1):
        db.add(RevueStoryMedia(dossier_id=dossier_id, kind="photo", position=position,
                               image_url=f"https://upload.wikimedia.org/example/{dossier_id}-{position}.jpg",
                               width=1280, height=853, page_url=f"https://commons.wikimedia.org/wiki/File:Ex{position}.jpg",
                               licence="CC BY-SA 4.0", licence_url="https://creativecommons.org/licenses/by-sa/4.0/",
                               author="Camille Exemple", credit_fr="Photo · Camille Exemple · CC BY-SA 4.0 · Wikimedia Commons",
                               caption_fr=caption, subject=subject, cost_usd=0.0, flagged=False))
    db.commit()


def Revue(db: Session, provider: FakeRevueProvider | None = None) -> RevueEncounter:  # noqa: N802
    revue = RevueEncounter(db, provider or FakeRevueProvider())
    revue.pictogram_provider = FakePictogramProvider()
    return revue


def make_user(db: Session, *, level: str = "A1.1", native: str = "en", played: tuple[str, ...] = ()) -> User:
    user = User(id=uuid.uuid4(), email=f"pm-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate=level, native_language=native, interests="")
    db.add(user)
    db.commit()
    now = datetime.now(UTC)
    for index, mode in enumerate(played):
        payload = {"kind": "dossier", "dossier_id": "old", **({"mode": mode} if mode != "chat" else {})}
        db.add(RevueSession(id=uuid.uuid4(), user_id=user.id, week=f"2026-W{20 - index}", dossier_id="old", plan={},
                            state={"events": [{"seq": 1, "at": now.isoformat(), "kind": "choice", "payload": payload}]},
                            status="closed", started_at=now - timedelta(days=index + 1),
                            closed_at=now - timedelta(days=index + 1)))
    db.commit()
    return user


def act(revue: RevueEncounter, row: RevueSession, **body):
    return revue.rubrique(row, RvRubriqueRequest(**body))


def state_of(row: RevueSession) -> ConversationState:
    return ConversationState.from_json(row.state)


def events(row: RevueSession, kind: str) -> list[dict]:
    return [e.payload for e in state_of(row).events if e.kind == kind]


def out_of_order(revue: RevueEncounter, row: RevueSession, **body) -> str:
    with pytest.raises(RevueError) as caught:
        act(revue, row, **body)
    assert caught.value.status == 409, caught.value.detail
    return caught.value.code


def start(db: Session, mode: str, provider: FakeRevueProvider | None = None, monkeypatch=None,
          **user) -> tuple[RevueEncounter, RevueSession]:
    """A session dealt ``mode`` on the Fête (the dealer forced; its rotation has its own test)."""

    revue = Revue(db, provider)
    if mode == "photo":
        seed_photos(db)
    monkeypatch.setattr(assignments, "deal", lambda offered, recent, seed: mode if mode in offered else None)
    row = revue.start(make_user(db, **user), week=WEEK, dossier_id=FETE)
    assert revue.view(row).mode == mode
    return revue, row


# ---------------------------------------------------------------------------
# The dealer
# ---------------------------------------------------------------------------


def test_the_dealer_rotates_six_shapes_and_never_repeats_the_last_two() -> None:
    assert assignments.registered() == SIX
    played: list[str] = []
    for day in range(24):
        dealt = assignments.deal(SIX, played, seed=f"u:story-{day}")
        assert dealt not in played[:2]
        played.insert(0, dealt)
    assert set(played) == set(SIX), "every shape comes round"


def test_la_photo_is_dealt_only_on_a_story_with_its_two_pictures(db: Session) -> None:
    revue = Revue(db)
    fete = next(d for d in evergreens_for_week(WEEK) if d.id == FETE)
    material = revue._material(fete, None)  # noqa: SLF001
    assert "photo" not in assignments.available(material), "no pictures: not dealt"
    assert "micro" in assignments.available(material)
    seed_photos(db, subjects=(("Paris", "Paris"),))
    assert "photo" not in assignments.available(revue._material(fete, None)), "one picture: not dealt"  # noqa: SLF001
    db.query(RevueStoryMedia).filter(RevueStoryMedia.dossier_id == FETE).delete()
    seed_photos(db, subjects=(("Paris", "Paris"), ("une scène de concert", None)))
    assert "photo" not in assignments.available(revue._material(fete, None)), "another photo: the desk does not bind"  # noqa: SLF001
    db.query(RevueStoryMedia).filter(RevueStoryMedia.dossier_id == FETE).delete()
    seed_photos(db)
    material = revue._material(fete, None)  # noqa: SLF001
    assert "photo" in assignments.available(material)
    bound = assignments.dealt_material(material, "photo")
    assert [p.url for p in bound.pictures] == [f"https://upload.wikimedia.org/example/{FETE}-{n}.jpg" for n in (1, 2)]
    # a learner who played the four others lately is dealt one of the new shapes
    user = make_user(db, played=("titre", "intox"))
    row = revue.start(user, week=WEEK, dossier_id=FETE)
    choice = state_of(row).events[0].payload
    assert choice["mode"] in {"comptoir", "photo", "micro"}
    if choice["mode"] in {"photo", "micro"}:
        assert choice["mode"] in choice["snapshot"] and not {"titre", "intox", "comptoir"} & set(choice["snapshot"])


def test_with_the_switch_off_nothing_changes(db: Session, monkeypatch) -> None:
    seed_photos(db)
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False)
    revue = Revue(db)
    row = revue.start(make_user(db, played=("titre", "intox")), week=WEEK, dossier_id=FETE)
    with_material = state_of(row).events[0].payload
    for module, name in ((micro, "micro_of"), (photo, "photo_of"), (titre_desk, "titre_of"), (intox_desk, "intox_of")):
        monkeypatch.setattr(module, name, lambda dossier: None)
    row2 = revue.start(make_user(db, played=("titre", "intox")), week=WEEK, dossier_id=FETE)
    without = state_of(row2).events[0].payload
    assert with_material["mode"] == "comptoir"
    assert not {"photo", "micro"} & set(with_material["snapshot"])
    assert json.dumps(with_material, sort_keys=True) == json.dumps(without, sort_keys=True)
    view = revue.view(row)
    assert view.photo is None and view.micro is None
    assert "photo" not in view.model_dump_json() or '"photo":null' in view.model_dump_json()


# ---------------------------------------------------------------------------
# «Le micro»
# ---------------------------------------------------------------------------


def facts_by_key(row: RevueSession) -> dict[str, object]:
    desk = evergreen_micro(FETE)
    keys = micro_loop.key_of(str(row.id), len(desk.facts))
    return {keys[i]: fact for i, fact in enumerate(desk.facts)}


def key_for(row: RevueSession, ask: str, claim: str | None = None) -> str:
    return next(k for k, f in facts_by_key(row).items() if f.ask == ask and (claim is None or f.claim_id == claim))


def test_le_micro_a2_the_interview_end_to_end(db: Session, monkeypatch) -> None:
    fake = FakeRevueProvider()
    revue, row = start(db, "micro", fake, monkeypatch, level="A2.1", native="de")
    view = revue.view(row).micro
    assert view.step == "read" and view.prepare is None and view.interview is None
    assert out_of_order(revue, row, act="prepare", keys=["a", "b", "c"]) == "revue_micro_out_of_order"
    act(revue, row, act="open")
    view = revue.view(row).micro
    assert view.step == "prepare" and len(view.prepare.holes) == 6
    shown = view.model_dump_json()
    for fact in evergreen_micro(FETE).facts:
        assert fact.answer.a2.fr not in shown and fact.tile.fr not in shown, "no answer before it is asked"
    assert act(revue, row, act="prepare", keys=["a", "b"]).error.code == "pick_three"
    chosen = [key_for(row, "quand"), key_for(row, "combien"), key_for(row, "quoi")]
    act(revue, row, act="prepare", keys=chosen)
    act(revue, row, act="prepare", keys=list("def"))  # a repeat records nothing
    assert revue.view(row).micro.prepare.chosen == chosen

    # a shrug does not spend the turn the first time; a second one in the same turn does
    assert act(revue, row, act="ask", text="La fête").error.code in {"not_a_question", "too_short"}
    act(revue, row, act="ask", text="Qui organise la fête ?")
    interview = revue.view(row).micro.interview
    assert interview.turns[-1].kind == "shrug" and not interview.turns[-1].spent and interview.spent == 0
    assert interview.turns[-1].answer.fr == evergreen_micro(FETE).shrug.a2.fr and not interview.free
    # a slip in the form still gets its answer, and is never shown during the interview
    act(revue, row, act="ask", text="Pourquoi elle est gratuite ?")
    interview = revue.view(row).micro.interview
    assert interview.turns[-1].kind == "answer" and interview.turns[-1].spent and interview.spent == 1
    assert interview.turns[-1].hole_key == key_for(row, "combien") and interview.free
    assert events(row, "micro")[-1]["slips"] == ["inversion", "question_word"]
    assert "inversion" not in revue.view(row).model_dump_json() and "slips" not in revue.view(row).model_dump_json()
    count = len(events(row, "micro"))
    act(revue, row, act="ask", text="Pourquoi elle est gratuite ?")
    assert len(events(row, "micro")) == count, "the same question again records nothing"
    # ambiguous: ONE model call, which may only pick among the stored candidates
    fake.micro_script = [{"fact": "zz"}]
    act(revue, row, act="ask", text="Pourquoi la fête ?")
    calls = [c for c in fake.calls if c[0] == "micro_match"]
    assert len(calls) == 1 and {c["ask"] for c in calls[0][1]["candidates"]} == {"pourquoi"}
    assert "answer" not in json.dumps(calls[0][1]), "the model sees claims, never writes an answer"
    assert revue.view(row).micro.interview.turns[-1].kind == "shrug", "a key outside the candidates is none"
    act(revue, row, act="ask", text="Pourquoi est-ce qu'il y a des plaintes ?")
    assert len([c for c in fake.calls if c[0] == "micro_match"]) == 1, "a clear question asks no model"
    assert revue.view(row).micro.interview.spent == 2
    assert out_of_order(revue, row, act="note", key=chosen[0], value="x") == "revue_micro_out_of_order"
    act(revue, row, act="ask", text="Quand est-ce que la première fête a eu lieu ?")
    view = revue.view(row).micro
    assert view.step == "notes" and view.interview.done and len(view.notes.items) == 3
    assert view.notes.input == "pick" and all(item.value_fr is None for item in view.notes.items)

    # the notes: two tries, the value only after the second miss
    facts = facts_by_key(row)
    first, second, third = (item.key for item in view.notes.items)
    wrong = next(o for o in view.notes.items[0].options if o != facts[first].value_fr)
    act(revue, row, act="note", key=first, value=wrong)
    item = revue.view(row).micro.notes.items[0]
    assert item.tries == 1 and not item.resolved and item.value_fr is None
    act(revue, row, act="note", key=first, value=wrong)
    assert revue.view(row).micro.notes.items[0].tries == 1, "the same pick again records nothing"
    other = next(o for o in item.options if o not in {facts[first].value_fr, wrong})
    act(revue, row, act="note", key=first, value=other)
    item = revue.view(row).micro.notes.items[0]
    assert item.resolved and item.correct is False and item.value_fr == facts[first].value_fr
    act(revue, row, act="note", key=second, value=facts[second].value_fr)
    act(revue, row, act="note", key=third, value=facts[third].value_fr)

    # «Relis tes questions»: the slips are the rule now, Romy's edit is ONE model call
    view = revue.view(row).micro
    assert view.step == "review" and len(view.review.questions) == 3
    assert [h.code for h in view.review.hints] == ["inversion", "question_word"]
    before = len([c for c in fake.calls if c[0] == "rubrique_edit"])
    act(revue, row, act="review")
    edits = [c for c in fake.calls if c[0] == "rubrique_edit"]
    assert len(edits) == before + 1 and edits[-1][1]["kind"] == "micro"
    assert {"question": 1, "slip": "inversion"} in edits[-1][1]["slips"]
    review = revue.view(row).micro.review
    assert review.proof in {"clean", "as_written", "marked"}
    if review.proof == "marked":
        act(revue, row, act="review_fix", value="romy")
    view, closing = revue.close(row)
    page = closing.micro_page
    assert page and [line.question_fr for line in page.lines] and len(page.lines) == 3
    assert all(line.source_name for line in page.lines), "every answer's source is printed"
    assert page.witness.id == "lila_bonnet" and page.byline_fr.startswith("Propos recueillis par")
    assert [n.right for n in page.notes] == [False, True, True]
    artifact = state_of(row).current_artifact
    assert artifact["kind"] == "micro" and "gratuite" in artifact["learner_fr"]
    memory = db.query(NPCMemory).filter(NPCMemory.user_id == row.user_id, NPCMemory.npc_id == "lila_bonnet").all()
    assert memory and "questions" in memory[-1].content, "the witness remembers being interviewed"
    calls = len(fake.calls)
    revue.close(row)
    assert len(fake.calls) == calls, "no model call at close, and a second close is the same page"
    assert out_of_order(revue, row, act="ask", text="Encore une question ?") == "revue_micro_out_of_order"


def test_le_micro_a1_plays_tiles_without_a_model_call(db: Session, monkeypatch) -> None:
    fake = FakeRevueProvider()
    revue, row = start(db, "micro", fake, monkeypatch, level="A1.1", native="de")
    act(revue, row, act="open")
    chosen = [revue.view(row).micro.prepare.holes[i].key for i in range(3)]
    act(revue, row, act="prepare", keys=chosen)
    interview = revue.view(row).micro.interview
    assert interview.input == "tiles" and [t.key for t in interview.tiles] == chosen
    assert all(t.text.fr.endswith("?") for t in interview.tiles)
    with pytest.raises(RevueError):
        act(revue, row, act="ask", key=next(k for k in "abcdef" if k not in chosen))
    for key in chosen:
        act(revue, row, act="ask", key=key)
    view = revue.view(row).micro
    assert view.step == "notes" and all(t.kind == "answer" for t in view.interview.turns)
    for item in view.notes.items:
        act(revue, row, act="note", key=item.key, value=facts_by_key(row)[item.key].value_fr)
    act(revue, row, act="review")
    assert revue.view(row).micro.review.proof == "clean" and revue.view(row).micro.review.hints == []
    revue.close(row)
    assert not [c for c in fake.calls if c[0] in {"rubrique_edit", "micro_match"}], "A1: no model call"
    assert state_of(row).current_artifact["learner_fr"] == "", "tiles are not the learner's words"


def test_le_micro_b1_types_its_notes_and_fixes_romy_s_marks(db: Session, monkeypatch) -> None:
    fake = FakeRevueProvider()
    revue, row = start(db, "micro", fake, monkeypatch, level="B1.1", native="en")
    act(revue, row, act="open")
    chosen = [key_for(row, "quand"), key_for(row, "combien"), key_for(row, "quoi")]
    act(revue, row, act="prepare", keys=chosen)
    act(revue, row, act="ask", text="Quand est-ce que la première fête, tres attendue, a eu lieu ?")  # Romy marks «tres»
    act(revue, row, act="ask", text="Combien coûte la fête ?")
    act(revue, row, act="ask", text="Quelles musiques est-ce qu'on peut écouter ?")
    view = revue.view(row).micro
    assert view.notes.input == "write" and view.notes.items[0].options == []
    first = view.notes.items[0].key
    assert act(revue, row, act="note", key=first, text="le 21 juin 1983").session.micro.notes.items[0].correct is None
    act(revue, row, act="note", key=first, text="Le 21 juin 1982")
    assert revue.view(row).micro.notes.items[0].correct is True
    for item in revue.view(row).micro.notes.items[1:]:
        act(revue, row, act="note", key=item.key, text=facts_by_key(row)[item.key].value_fr)
    act(revue, row, act="review")
    review = revue.view(row).micro.review
    assert review.proof == "marked" and review.marks, review
    assert "très" not in json.dumps([m.model_dump() for m in review.marks]), "never the answer before the fix"
    assert act(revue, row, act="review_fix", text="Une seule question ?").error.code == "keep_questions"
    act(revue, row, act="review_fix", text=review.draft_fr.replace("tres", "très"))
    assert revue.view(row).micro.review.proof in {"fixed", "corrected", "as_written"}
    _, closing = revue.close(row)
    assert "première fête" in closing.micro_page.lines[0].question_fr


# ---------------------------------------------------------------------------
# «La photo»
# ---------------------------------------------------------------------------


def lead_key(row: RevueSession) -> str:
    desk = evergreen_photo(FETE)
    return photo_loop.picture_keys(desk, str(row.id))[desk.lead]


def test_la_photo_a1_planche_legende_tiles_and_the_page(db: Session, monkeypatch) -> None:
    fake = FakeRevueProvider()
    revue, row = start(db, "photo", fake, monkeypatch, level="A1.1", native="de")
    act(revue, row, act="open")
    planche = revue.view(row).photo.planche
    assert planche.headline_fr == "La Fête de la musique" and len(planche.pictures) == 2
    assert planche.solution is None and planche.seen is None
    assert all(p.credit_fr.startswith("Photo · ") and p.url for p in planche.pictures), "credits printed"
    assert out_of_order(revue, row, act="caption", key="a") == "revue_photo_out_of_order"
    lead = lead_key(row)
    other = next(p.key for p in planche.pictures if p.key != lead)
    act(revue, row, act="choose", key=other)
    planche = revue.view(row).photo.planche
    assert not planche.resolved and planche.solution is None
    assert [s.fr for s in planche.shows] == ["Paris"] and planche.shows[0].tr == "Paris", "what the picked one shows"
    act(revue, row, act="choose", key=other)
    assert revue.view(row).photo.planche.tries == 1, "a repeat records nothing"
    act(revue, row, act="choose", key=lead)
    planche = revue.view(row).photo.planche
    assert planche.resolved and planche.correct and planche.solution == lead and planche.seen is not None
    words = {w.index: w.text.fr for w in planche.seen.words}
    assert sorted(words.values()) == ["Paris", "une guitare", "une guitare acoustique"]
    paris = next(i for i, fr in words.items() if fr == "Paris")
    guitar = next(i for i, fr in words.items() if fr == "une guitare")
    act(revue, row, act="seen", words=[paris, guitar])
    seen = revue.view(row).photo.planche.seen
    assert seen.elsewhere == [paris] and seen.missing == 1 and seen.solution == [] and not seen.resolved
    act(revue, row, act="seen", words=[guitar])
    seen = revue.view(row).photo.planche.seen
    assert seen.resolved and seen.correct is False and sorted(seen.solution) == sorted(i for i in words if i != paris)

    view = revue.view(row).photo
    assert view.step == "legende" and all(c.role is None for c in view.legende.captions), "no role before a pick"
    desk = evergreen_photo(FETE)
    ckeys = photo_loop.caption_key_of(str(row.id))
    by_role = {desk.captions[i].role: k for i, k in ckeys.items()}
    act(revue, row, act="caption", key=by_role["other"])
    legende = revue.view(row).photo.legende
    picked = next(c for c in legende.captions if c.key == by_role["other"])
    assert picked.role == "other" and picked.why.tr.startswith("Diese Bildunterschrift")
    assert legende.solution is None and next(c for c in legende.captions if c.key == by_role["wrong"]).role is None
    act(revue, row, act="caption", key=by_role["wrong"])
    legende = revue.view(row).photo.legende
    assert legende.resolved and legende.correct and legende.fix.input == "pick" and legende.fix.right_fr is None
    act(revue, row, act="caption_fix", value="en 1982")
    fix = revue.view(row).photo.legende.fix
    assert fix.tries == 1 and not fix.resolved and fix.right_fr is None
    act(revue, row, act="caption_fix", value="le 21 juin")
    fix = revue.view(row).photo.legende.fix
    assert fix.resolved and fix.correct and fix.right_fr == "le 21 juin"

    build = revue.view(row).photo.build
    assert build.input == "tiles" and len(build.choices) == 2 and len(build.facts) == 3
    assert act(revue, row, act="build", key=lead, parts=[9, 0]).error.code == "pick_tiles"
    act(revue, row, act="build", key=lead, parts=[0, 0])
    build = revue.view(row).photo.build
    assert build.proof == "clean" and build.printed_fr == "Sur la photo, on voit une guitare. La fête est gratuite."
    _, closing = revue.close(row)
    page = closing.photo_page
    assert page.caption_fr == build.printed_fr and page.picture.key == lead and page.picture.credit_fr
    assert closing.dispatch.byline_fr.startswith("Romy Tremblay, avec toi · d'après ")
    assert state_of(row).current_artifact["kind"] == "photo"
    assert not [c for c in fake.calls if c[0] == "rubrique_edit"], "A1: no model call"


def test_la_photo_b1_two_sentences_and_romy_s_marks(db: Session, monkeypatch) -> None:
    fake = FakeRevueProvider()
    revue, row = start(db, "photo", fake, monkeypatch, level="B1.1", native="en")
    act(revue, row, act="open")
    lead = lead_key(row)
    act(revue, row, act="choose", key=lead)
    seen = revue.view(row).photo.planche.seen
    act(revue, row, act="seen", words=[w.index for w in seen.words if w.text.fr != "Paris"])
    assert revue.view(row).photo.planche.seen.correct is True
    ckeys = photo_loop.caption_key_of(str(row.id))
    desk = evergreen_photo(FETE)
    act(revue, row, act="caption", key=next(k for i, k in ckeys.items() if desk.captions[i].role == "wrong"))
    assert revue.view(row).photo.legende.fix.input == "write"
    assert act(revue, row, act="caption_fix", text="21 juin").error.code == "too_short"
    act(revue, row, act="caption_fix", text="La fête a lieu le 14 juillet, pas le 21 juin.")
    assert revue.view(row).photo.legende.fix.correct is None, "the false value still stands"
    act(revue, row, act="caption_fix", text="La première fête a eu lieu le 21 juin 1982.")
    assert revue.view(row).photo.legende.fix.correct is True
    assert act(revue, row, act="build", key=lead, text="Une guitare acoustique.").error.code == "two_sentences"
    assert act(revue, row, act="build", key=lead,
               text="On voit un piano. La fête est gratuite.").error.code == "name_what_you_see"
    assert act(revue, row, act="build", key=lead,
               text="On voit une guitare acoustique. Elle est belle.").error.code == "say_the_news"
    assert act(revue, row, act="build", key=lead,
               text="On voit une guitare. La fête a 40 ans.").error.code == "number_not_in_claims"
    act(revue, row, act="build", key=lead, text="On voit une guitare acoustique, tres belle. La fête est gratuite.")
    edits = [c for c in fake.calls if c[0] == "rubrique_edit"]
    assert len(edits) == 1 and edits[0][1]["kind"] == "photo"
    build = revue.view(row).photo.build
    assert build.proof == "marked" and build.marks and build.printed_fr is None
    act(revue, row, act="build_fix", text="On voit une guitare acoustique, très belle. La fête est gratuite.")
    build = revue.view(row).photo.build
    assert build.proof in {"fixed", "corrected"} and build.printed_fr
    _, closing = revue.close(row)
    assert closing.photo_page.caption_fr == build.printed_fr
    assert state_of(row).current_artifact["learner_fr"]


# ---------------------------------------------------------------------------
# The route
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session, revue_tables) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_revue_provider] = lambda: FakeRevueProvider()
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> dict[str, str]:
    email = f"pm-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "securepass123", "target_language": "fr",
                                               "native_language": "en"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_the_rubrique_route_plays_la_photo_and_le_micro(api: TestClient, db_session: Session, monkeypatch) -> None:
    seed_photos(db_session)
    for mode in ("photo", "micro"):
        headers = login(api)
        monkeypatch.setattr(assignments, "deal", lambda offered, recent, seed, mode=mode: mode)
        session = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, "dossier_id": FETE}).json()
        assert session["mode"] == mode and session[mode]["step"] == "read"
        path = f"/api/v1/revue/sessions/{session['id']}/rubrique"
        first = {"photo": {"act": "choose", "key": "a"}, "micro": {"act": "prepare", "keys": ["a", "b", "c"]}}[mode]
        response = api.post(path, headers=headers, json=first)
        assert response.status_code == 409 and response.json()["detail"]["code"] == f"revue_{mode}_out_of_order"
        response = api.post(path, headers=headers, json={"act": "open"})
        body = response.json()["session"][mode]
        assert response.status_code == 200 and body["step"] != "read"
        text = json.dumps(body)
        assert '"lead": "photo' not in text and '"role": "wrong"' not in text and "value_fr" not in text
        assert api.post(path, headers=headers, json={"act": "dance"}).status_code == 422


def test_the_chooser_names_the_assignment_the_start_deals(db: Session, monkeypatch) -> None:
    """Fault seen in the browser (evidence README, 2026-11-20): the chooser must name the
    assignment dealt. The card and the start ask the same dealer over the same material."""

    seed_photos(db)
    for played in (("titre", "intox"), ("photo", "micro"), ("comptoir", "photo")):
        user = make_user(db, played=played)
        offer = Revue(db).week_offer(user, WEEK)
        card = next(c for c in [offer.recommended, *offer.alternatives] if c and c.dossier_id == FETE)
        mode = Revue(db).view(Revue(db).start(user, week=WEEK, dossier_id=FETE)).mode
        assert card.assignment is not None and card.assignment.key == mode, (played, card.assignment, mode)
        assert card.assignment.name_fr == assignments.assignment(mode).name_fr
        assert (card.question_fr is not None) == (mode == "comptoir")
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False)
    offer = Revue(db).week_offer(make_user(db), WEEK)
    card = next(c for c in [offer.recommended, *offer.alternatives] if c and c.dossier_id == FETE)
    assert card.assignment is None and "assignment" not in card.model_dump(mode="json"), "switch off: today's card"
