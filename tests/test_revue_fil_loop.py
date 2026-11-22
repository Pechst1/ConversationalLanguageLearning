"""«Le Papier · les rubriques» (owner 2026-11-20): the dealer (``assignments.py``) and «Le fil»'s
loop (``fil_loop.py``) and route.

The dealer: deterministic, never the shape of the last two Papiers, falls back to what exists,
recorded on the first event; switch off = today's session, byte for byte. The loop: the order
graded with a reason and never the solution before the second try, two tries at most; the
sequence words with their glosses on a miss; the telling at A1 (tiles, no model call), A2
(frames, Romy marks, the learner fixes) and B1 (two sequence words); acts idempotent and out of
order answered 409; the view never shows the order before it is resolved; «La page» at the
close with the ``fil`` artifact, the vignette, the memory and the kept words.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.revue import get_revue_provider
from app.config import settings
from app.core.rate_limit import PAID_ROUTES
from app.db.models.npc import NPC, NPCMemory
from app.db.models.pilot_event import PilotEvent
from app.db.models.revue_session import RevueDossier, RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.story import Story
from app.db.models.user import User
from app.main import create_app
from app.schemas.revue import RvFilRequest
from app.services.revue import assignments, comptoir, fil, fil_loop
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter, RevueError
from app.services.revue.evergreen import evergreen_wire, evergreens_for_week
from app.services.revue.pictogram import FakePictogramProvider
from app.services.revue.state import ConversationState

WEEK = "2026-W25"
BAC = "evergreen-bac"
REVUE_TABLES = (
    Story.__table__,
    NPC.__table__,
    NPCMemory.__table__,
    RevueSession.__table__,
    RevueDossier.__table__,
    RevuePictogram.__table__,
    RevueVignette.__table__,
    PilotEvent.__table__,
)


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
    # «Papier · le choix» (2026-11-22): every desk, the parked ones included, is dealt here.
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_OFFERED", "comptoir,fil,titre,intox,photo,micro")
    # These tests pin the shapes they play; «La photo» and «Le micro» (2026-11-21) have their
    # own (tests/test_revue_photo_micro_loop.py) and are kept off the deal here.
    from app.services.revue import micro as _micro
    from app.services.revue import photo as _photo

    monkeypatch.setattr(_micro, "micro_of", lambda dossier: None)
    monkeypatch.setattr(_photo, "photo_of", lambda dossier: None)
    comptoir.forget_cache()


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def Revue(db: Session, provider: FakeRevueProvider | None = None) -> RevueEncounter:  # noqa: N802
    revue = RevueEncounter(db, provider or FakeRevueProvider())
    revue.pictogram_provider = FakePictogramProvider()
    return revue


def make_user(db: Session, *, level: str = "A1.1", native: str = "en", played: tuple[str, ...] = ()) -> User:
    """A learner whose last Papiers (newest first) were played in ``played``'s modes."""

    user = User(id=uuid.uuid4(), email=f"fil-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
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
    return revue.fil(row, RvFilRequest(**body))


def state_of(row: RevueSession) -> ConversationState:
    return ConversationState.from_json(row.state)


def out_of_order(revue: RevueEncounter, row: RevueSession, **body) -> str:
    with pytest.raises(RevueError) as caught:
        act(revue, row, **body)
    assert caught.value.status == 409, caught.value.detail
    return caught.value.code


def fil_events(row: RevueSession) -> list[dict]:
    return [e.payload for e in state_of(row).events if e.kind == "fil"]


def start_fil(db: Session, **user) -> tuple[RevueEncounter, RevueSession]:
    revue = Revue(db)
    row = revue.start(make_user(db, played=("comptoir", "chat"), **user), week=WEEK, dossier_id=BAC)
    assert revue.view(row).mode == "fil"
    return revue, row


def right_order(row: RevueSession) -> list[str]:
    keys = fil_loop.key_of(str(row.id))
    return [keys[i] for i in range(4)]


def solve_order(revue: RevueEncounter, row: RevueSession) -> None:
    act(revue, row, act="open")
    act(revue, row, act="order", order=right_order(row))


def solve_words(revue: RevueEncounter, row: RevueSession) -> None:
    band = str(enc.load(row).plan.learner.band)
    act(revue, row, act="words", picks=fil_loop.solution_words(evergreen_wire(BAC), band, str(row.id)))


# ---------------------------------------------------------------------------
# The dealer
# ---------------------------------------------------------------------------


def test_the_dealer_never_repeats_the_last_two_shapes_and_falls_back_to_what_exists() -> None:
    both = ["comptoir", "fil"]
    assert assignments.deal(both, ["comptoir"], seed="u:d") == "fil"
    assert assignments.deal(both, ["fil", "chat"], seed="u:d") == "comptoir"
    assert assignments.deal(both, ["chat", "fil"], seed="u:d") == "comptoir", "two Papiers back counts too"
    assert assignments.deal(both, ["fil", "comptoir"], seed="u:d") == "comptoir", "both lately: the oldest"
    assert assignments.deal(["comptoir"], ["comptoir", "comptoir"], seed="u:d") == "comptoir", "what exists"
    assert assignments.deal([], ["fil"], seed="u:d") is None, "nothing to carry: the chat"
    assert assignments.deal(both, ["fil", "comptoir", "fil"], seed="u:d") == "comptoir", "only the last two count"


def test_the_dealer_is_deterministic_per_learner_and_story() -> None:
    both = ["comptoir", "fil"]
    picks = {assignments.deal(both, [], seed=f"user-{n}:story") for n in range(20)}
    assert picks == {"comptoir", "fil"}, "a fresh learner can be dealt either"
    assert all(assignments.deal(both, [], seed="user-7:story") == assignments.deal(both, [], seed="user-7:story")
               for _ in range(3))


def test_a_new_assignment_registers_without_touching_the_dealer() -> None:
    # «photo» is a real assignment since 2026-11-21: a made-up key, so the registry is left as it was
    try:
        assignments.register(assignments.Assignment("essai", "L'essai", lambda m: m.dossier.visual is not None))
        assert "essai" in assignments.registered()
        assert assignments.deal(["comptoir", "fil", "essai"], ["comptoir", "fil"], seed="s") == "essai"
    finally:
        assignments._REGISTRY.pop("essai", None)  # noqa: SLF001


def test_a_story_with_both_is_dealt_the_shape_the_learner_did_not_play_lately(db: Session) -> None:
    revue = Revue(db)
    row = revue.start(make_user(db, played=("comptoir",)), week=WEEK, dossier_id=BAC)
    choice = state_of(row).events[0].payload
    assert choice["mode"] == "fil" and "comptoir" not in choice["snapshot"]
    assert choice["snapshot"]["fil"]["strips"][0]["claim_id"] == "c1"
    assert [e.kind for e in state_of(row).events] == ["choice"], "no chat arrival"
    row = Revue(db).start(make_user(db, played=("fil", "chat")), week=WEEK, dossier_id=BAC)
    choice = state_of(row).events[0].payload
    assert choice["mode"] == "comptoir" and "fil" not in choice["snapshot"]
    # a story with takes and no wire: the comptoir, whatever was played
    row = Revue(db).start(make_user(db, played=("comptoir", "comptoir")), week=WEEK,
                          dossier_id="evergreen-marche-du-dimanche")
    assert state_of(row).events[0].payload["mode"] == "comptoir"
    # the session keeps its assignment for life
    revue = Revue(db)
    row = revue.start(make_user(db, played=("comptoir",)), week=WEEK, dossier_id=BAC)
    assert revue.view(row).mode == "fil" and revue.view(row).fil is not None
    with pytest.raises(RevueError) as caught:
        revue.turn(row, "Bonjour")
    assert (caught.value.status, caught.value.code) == (409, "revue_fil_session")
    with pytest.raises(RevueError) as caught:
        revue.comptoir(row, None)
    assert caught.value.code == "revue_not_comptoir"


def test_the_chooser_card_never_promises_the_counter_to_a_learner_dealt_le_fil(db: Session) -> None:
    """Seen in a browser (2026-11-20, A2 de): the card said «La question du jour : Le bac sans
    échec, c'est une bonne idée ?» and «Au comptoir», and the session played «Le fil»."""

    def card(user):
        offer = Revue(db).week_offer(user, WEEK)
        return next(c for c in [offer.recommended, *offer.alternatives] if c and c.dossier_id == BAC)

    dealt_fil = make_user(db, played=("comptoir",))
    assert card(dealt_fil).question_fr is None and card(dealt_fil).cast is None, "no question, no regulars"
    row = Revue(db).start(dealt_fil, week=WEEK, dossier_id=BAC)
    assert state_of(row).events[0].payload["mode"] == "fil", "the card and the session agree"
    dealt_counter = make_user(db, played=("fil", "chat"))
    assert card(dealt_counter).question_fr, "the counter's card keeps its question"
    assert state_of(Revue(db).start(dealt_counter, week=WEEK, dossier_id=BAC)).events[0].payload["mode"] == "comptoir"


def test_with_the_switch_off_the_session_is_todays_byte_for_byte(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False)
    revue = Revue(db)
    row = revue.start(make_user(db, played=("comptoir", "comptoir")), week=WEEK, dossier_id=BAC)
    with_wire = state_of(row).events[0].payload
    monkeypatch.setattr(fil, "wire_of", lambda dossier: None)
    row2 = revue.start(make_user(db, played=("comptoir", "comptoir")), week=WEEK, dossier_id=BAC)
    without = state_of(row2).events[0].payload
    assert with_wire["mode"] == "comptoir" and "fil" not in with_wire["snapshot"]
    assert json.dumps(with_wire, sort_keys=True) == json.dumps(without, sort_keys=True)
    view = revue.view(row)
    assert view.mode == "comptoir" and view.fil is None
    # and the chat, with both switches off
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", False)
    row3 = revue.start(make_user(db), week=WEEK, dossier_id=BAC)
    choice = state_of(row3).events[0].payload
    assert "mode" not in choice and "fil" not in choice["snapshot"] and "comptoir" not in choice["snapshot"]
    assert revue.view(row3).mode == "chat"


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def test_the_order_is_never_shown_before_it_is_resolved(db: Session) -> None:
    revue, row = start_fil(db)
    view = revue.view(row).fil
    assert view.step == "read" and view.order is None and view.words is None
    assert view.steps == ["read", "order", "words", "tell", "page"]
    assert out_of_order(revue, row, act="order", order=list("abcd")) == "revue_fil_out_of_order"
    view = act(revue, row, act="open").session.fil
    assert view.step == "order"
    shown = [s.key for s in view.order.strips]
    assert shown == list("abcd") and right_order(row) != list("abcd"), "shuffled, never already in order"
    assert view.order.solution == [] and view.order.resolved is False and view.words is None
    text = json.dumps(view.model_dump(mode="json"), ensure_ascii=False)
    assert "claim" not in text and "1808" in text
    assert view.order.strips[0].label.tr, "the strip's name, in the learner's language"


def test_a_wrong_order_names_one_misplaced_strip_and_the_second_shows_the_solution(db: Session) -> None:
    revue, row = start_fil(db)
    act(revue, row, act="open")
    right = right_order(row)
    wrong = [right[1], right[0], right[2], right[3]]
    view = act(revue, row, act="order", order=wrong).session.fil
    assert view.step == "order" and view.order.tries == 1 and view.order.resolved is False
    assert (view.order.hint.key, view.order.hint.after_key) == (right[1], right[0]), "the 1809 one comes after 1808"
    assert view.order.solution == [] and view.order.correct is None, "no solution before the retry"
    assert view.order.placed == wrong
    events = len(state_of(row).events)
    act(revue, row, act="order", order=wrong)
    assert len(state_of(row).events) == events, "a repeated act records nothing"
    view = act(revue, row, act="order", order=[right[3], right[2], right[1], right[0]]).session.fil
    assert view.order.resolved and view.order.correct is False and view.order.solution == right
    assert view.step == "words"
    act(revue, row, act="order", order=right)
    assert len(fil_events(row)) == 3, "never more than two tries"


def test_a1_places_the_four_words_and_a_miss_says_what_the_word_means(db: Session) -> None:
    revue, row = start_fil(db)
    solve_order(revue, row)
    view = revue.view(row).fil
    assert view.step == "words" and view.words.input == "place"
    assert all(c.tr is None and c.role is None for c in view.words.connectors), "no answer in the chips"
    chips = [c.id for c in view.words.connectors]
    assert sorted(chips) == ["d-abord", "enfin", "ensuite", "puis"]
    assert out_of_order(revue, row, act="tell", parts=["d-abord", "a", "enfin", "b"]) == "revue_fil_out_of_order"
    view = act(revue, row, act="words", picks=["enfin", "ensuite", "puis", "d-abord"]).session.fil
    assert not view.words.resolved and view.words.solution == []
    misses = {(m.position, m.fr, m.tr, m.role, m.needs) for m in view.words.misses}
    assert misses == {(0, "enfin", "finally", "last", "first"), (3, "d'abord", "first", "first", "last")}
    view = act(revue, row, act="words", picks=["d-abord", "puis", "ensuite", "enfin"]).session.fil
    assert view.words.resolved and view.words.correct and view.step == "tell"
    assert all(c.tr for c in view.words.connectors), "glosses once resolved"


def test_a1_tells_with_tiles_and_an_impossible_order_is_refused_with_its_reason(db: Session) -> None:
    revue, row = start_fil(db)
    provider = revue.provider
    solve_order(revue, row)
    solve_words(revue, row)
    view = revue.view(row).fil
    assert view.tell.input == "tiles" and [t.text.fr for t in view.tell.tiles][0] == "le baccalauréat naît en 1808"
    first, last = right_order(row)[0], right_order(row)[3]
    result = act(revue, row, act="tell", parts=["d-abord", last, "enfin", first])
    assert result.error.code == "tell_order" and (result.error.key, result.error.after_key) == (last, first)
    assert act(revue, row, act="tell", parts=["enfin", first, "puis", last]).error.code == "tell_last_first"
    assert act(revue, row, act="tell", parts=["puis", first, "enfin", last]).error.code == "tell_starts_middle"
    assert act(revue, row, act="tell", parts=["d-abord", first, "d-abord", last]).error.code == "tell_first_second"
    assert not any(e.get("act") == "tell" for e in fil_events(row)), "a refusal records nothing"
    view = act(revue, row, act="tell", parts=["d-abord", first, "enfin", last]).session.fil
    assert view.tell.proof == "clean" and view.step == "page"
    assert view.tell.printed_fr == "D'abord, le baccalauréat naît en 1808. Enfin, le Grand oral compte moins en 2027."
    assert not [c for c in provider.calls if c[0] == "fil_edit"], "A1: no model call"

    view, closing = revue.close(row)
    page = closing.fil_page
    assert page is not None and closing.comptoir_page is None and view.status == "closed"
    words = [s.connector_fr for s in page.strips]
    assert words[0] == "D'abord" and words[3] == "Enfin" and set(words[1:3]) == {"Ensuite", "Puis"}
    assert page.strips[0].text_fr == "Le baccalauréat naît en 1808." and page.mine_fr == view.fil.tell.printed_fr
    assert closing.dispatch.kicker_fr == "Le fil de Romy" and closing.dispatch.byline_fr.startswith("Romy Tremblay ·")
    artifact = state_of(row).current_artifact
    assert artifact["kind"] == "fil" and artifact["learner_fr"] == "", "tiles are not the learner's words"
    assert closing.vignette is not None and closing.vignette.ring == "report"
    memory = db.scalars(select(NPCMemory).where(NPCMemory.scene_id == str(row.id))).all()
    assert any("tu as remis le fil" in m.content for m in memory)
    assert view.artifact.kind == "fil"
    assert revue.close(row)[1] == closing, "idempotent"
    assert out_of_order(revue, row, act="open") == "revue_fil_out_of_order"


def test_a2_completes_the_frames_romy_marks_and_the_learner_fixes(db: Session) -> None:
    revue, row = start_fil(db, level="A2.1", native="de")
    solve_order(revue, row)
    view = revue.view(row).fil
    assert view.words.input == "choose" and all(len(o) == 3 for o in view.words.options)
    solve_words(revue, row)
    view = revue.view(row).fil
    assert view.tell.input == "frames" and [f.fr for f in view.tell.frames] == ["D'abord, le baccalauréat",
                                                                                  "Enfin, le Grand oral"]
    assert view.tell.frames[0].tr == "Zuerst das Abitur", "German below B1"
    assert act(revue, row, act="tell", texts=["naît", "compte moins"]).error.code == "too_short"
    result = act(revue, row, act="tell", texts=["est créé en 1808", "compte moins, il sont contents"])
    tell = result.session.fil.tell
    assert tell.proof == "marked" and tell.printed_fr is None, "nothing printed before the fix"
    assert [(m.span_fr, m.kind) for m in tell.marks] == [("il", "accord")]
    assert "ils sont" not in json.dumps(result.session.model_dump(mode="json"), ensure_ascii=False), "no solution"
    fixed = tell.draft_fr.replace("il sont", "ils sont")
    tell = act(revue, row, act="tell_fix", text=fixed).session.fil.tell
    assert tell.proof == "fixed" and tell.printed_fr.endswith("ils sont contents.")
    assert act(revue, row, act="tell", texts=["x y z", "a b c"]).error is None, "a double submit: the stored result"
    _, closing = revue.close(row)
    assert state_of(row).current_artifact["learner_fr"], "typed words are the learner's"
    assert closing.fil_page.proof == "fixed"


def test_b1_tells_freely_with_two_sequence_words(db: Session) -> None:
    revue, row = start_fil(db, level="B1.1")
    solve_order(revue, row)
    solve_words(revue, row)
    view = revue.view(row).fil
    assert view.tell.input == "free" and view.tell.min_connectors == 2
    short = "Le bac est créé en 1808 et en 2027 le Grand oral compte moins pour les candidats."
    assert act(revue, row, act="tell", text=short).error.code == "need_connectors"
    text = "Tout d'abord, le bac est créé en 1808. Par la suite, en 2027, le Grand oral compte moins pour le bac."
    tell = act(revue, row, act="tell", text=text).session.fil.tell
    assert tell.proof == "clean" and tell.printed_fr
    assert fil_loop.connectors_used(text) == ["tout d'abord", "par la suite"]


def test_a_failing_edit_prints_the_telling_as_written(db: Session) -> None:
    class Down(FakeRevueProvider):
        def fil_edit(self, context):
            raise RuntimeError("down")

    revue = Revue(db, Down())
    row = revue.start(make_user(db, level="B1.1", played=("comptoir",)), week=WEEK, dossier_id=BAC)
    solve_order(revue, row)
    solve_words(revue, row)
    text = "Tout d'abord, le bac est créé en 1808. Ensuite, en 2027, le Grand oral compte moins pour le bac."
    tell = act(revue, row, act="tell", text=text).session.fil.tell
    assert tell.proof == "as_written" and tell.printed_fr == text


def test_with_le_pourquoi_on_the_tellings_marks_explain_their_rule_as_at_the_counter(db: Session, monkeypatch) -> None:
    """Integration (Papier · together): «Raconter» uses the pourquoi's explained marks — the
    hint in the mother tongue before the fix (never the answer), the full why once settled,
    and the slip kept in the error memory for La Forge."""

    from app.db.models.error import UserError
    from app.services.revue import pourquoi

    monkeypatch.setattr(settings, "REVUE_POURQUOI_ENABLED", True, raising=False)
    fake = FakeRevueProvider()
    revue = Revue(db, fake)
    user = make_user(db, level="A2.1", native="de", played=("comptoir", "chat"))
    row = revue.start(user, week=WEEK, dossier_id=BAC)
    solve_order(revue, row)
    solve_words(revue, row)
    result = act(revue, row, act="tell", texts=["est créé en 1808", "compte moins, il sont contents"])
    edit = [c for c in fake.calls if c[0] == "fil_edit"][-1][1]
    assert edit["explain_language"] == "de", "the explanation language is passed as data"
    tell = result.session.fil.tell
    assert tell.proof == "marked" and [(m.span_fr, m.kind) for m in tell.marks] == [("il", "accord")]
    assert tell.marks[0].why and "Nomen" in tell.marks[0].why, "the hint, in German"
    shown = json.dumps(result.session.model_dump(mode="json"), ensure_ascii=False)
    assert "ils sont" not in shown and "why_full" not in shown and "fix_fr" not in shown, "no solution before a retry"
    assert not pourquoi.gives_away(tell.marks[0].why, "il", "ils")
    assert not json.loads(shown)["fil"]["tell"].get("notes"), "the full why waits for the fix"
    event = next(e for e in state_of(row).events if e.payload.get("act") == "tell")
    assert event.payload["prompt_version"] == "fil-edit-v2"

    tell = act(revue, row, act="tell_fix", text=tell.draft_fr.replace("il sont", "ils sont")).session.fil.tell
    assert tell.proof == "fixed"
    assert [(n.span_fr, n.kind) for n in tell.notes] == [("il", "accord")]
    assert tell.notes[0].why and "«ils sont»" in tell.notes[0].why, "the full why may show the fix now"
    kept = list(db.scalars(select(UserError).where(UserError.user_id == user.id)).all())
    assert len(kept) == 1, "the slip comes back in La Forge"


def test_with_le_pourquoi_off_the_telling_is_todays(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_POURQUOI_ENABLED", False, raising=False)
    fake = FakeRevueProvider()
    revue = Revue(db, fake)
    row = revue.start(make_user(db, level="A2.1", native="de", played=("comptoir", "chat")), week=WEEK, dossier_id=BAC)
    solve_order(revue, row)
    solve_words(revue, row)
    tell = act(revue, row, act="tell", texts=["est créé en 1808", "compte moins, il sont contents"]).session.fil.tell
    assert "explain_language" not in [c for c in fake.calls if c[0] == "fil_edit"][-1][1]
    assert tell.marks and all(m.why is None for m in tell.marks)
    event = next(e for e in state_of(row).events if e.payload.get("act") == "tell")
    assert event.payload["prompt_version"] == "fil-edit-v1"
    tell = act(revue, row, act="tell_fix", text=tell.draft_fr.replace("il sont", "ils sont")).session.fil.tell
    assert tell.proof == "fixed" and not getattr(tell, "notes", None)


def test_the_close_waits_for_the_telling(db: Session) -> None:
    revue, row = start_fil(db)
    solve_order(revue, row)
    with pytest.raises(RevueError) as caught:
        revue.close(row)
    assert (caught.value.status, caught.value.code) == (409, "revue_fil_out_of_order")


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
    email = f"fil-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "securepass123", "target_language": "fr",
                                               "native_language": "en"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_the_route_plays_a_fil_session_and_is_a_paid_route(api: TestClient, monkeypatch) -> None:
    assert ("POST", "/revue/sessions/{session_id}/fil") in PAID_ROUTES
    monkeypatch.setattr(assignments, "deal", lambda offered, recent, seed: "fil" if "fil" in offered else None)
    headers = login(api)
    session = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, "dossier_id": BAC}).json()
    assert session["mode"] == "fil" and session["fil"]["step"] == "read" and session["comptoir"] is None
    path = f"/api/v1/revue/sessions/{session['id']}/fil"
    response = api.post(path, headers=headers, json={"act": "words", "picks": ["a", "b", "c", "d"]})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "revue_fil_out_of_order"
    assert response.json()["detail"]["step"] == "read"
    response = api.post(path, headers=headers, json={"act": "open"})
    assert response.status_code == 200 and response.json()["session"]["fil"]["step"] == "order"
    assert api.post(path, headers=headers, json={"act": "order", "order": ["a", "a", "b", "c"]}).status_code == 422
    assert api.post(path, headers=headers, json={"act": "dance"}).status_code == 422
    comptoir_path = f"/api/v1/revue/sessions/{session['id']}/comptoir"
    response = api.post(comptoir_path, headers=headers, json={"act": "vote", "value": "pour"})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "revue_not_comptoir"
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.post(path, headers=headers, json={"act": "open"}).status_code == 404
