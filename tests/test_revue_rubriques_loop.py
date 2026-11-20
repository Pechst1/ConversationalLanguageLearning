"""«Le Papier · les rubriques» (owner 2026-11-20): «Le titre» and «L'intox express», the loops
(``titre_loop.py``, ``intox_loop.py``) and their shared act route.

The dealer rotates four shapes (never the last two); the switch off leaves today's session
byte for byte. «L'intox express»: five statements one at a time, nothing in the view says
which is false before it is answered, the quote and the line after a false one or a miss, the
two corrections graded deterministically (numbers digit for digit), the true value only after
the second miss, acts idempotent, 409 out of order, no model call, «La page». «Le titre»: the
honest headline in two tries with the why and the claim of a wrong pick and never the solution
before the second, the trap graded against the stored words, the learner's headline (A1 tiles
without a model call; A2/B1 Romy marks, the learner fixes; the words that said too much
refused), «La page» under the learner's headline.
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
from app.schemas.revue import RvRubriqueRequest
from app.services.revue import assignments, comptoir, intox_loop, titre_loop
from app.services.revue import encounter as enc
from app.services.revue import intox as intox_desk
from app.services.revue import titre as titre_desk
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter, RevueError
from app.services.revue.evergreen import evergreen_intox, evergreen_titre, evergreens_for_week
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

    user = User(id=uuid.uuid4(), email=f"rub-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
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


def start(db: Session, mode: str, provider: FakeRevueProvider | None = None, **user) -> tuple[RevueEncounter, RevueSession]:
    revue = Revue(db, provider)
    other = {"titre": "intox", "intox": "titre"}[mode]
    row = revue.start(make_user(db, played=("comptoir", other), **user), week=WEEK, dossier_id=FETE)
    assert revue.view(row).mode == mode
    return revue, row


# ---------------------------------------------------------------------------
# The dealer
# ---------------------------------------------------------------------------


def test_the_dealer_rotates_four_shapes_and_never_repeats_the_last_two() -> None:
    four = ["comptoir", "fil", "titre", "intox"]
    assert assignments.registered()[:4] == four
    for recent in (["comptoir", "fil"], ["titre", "intox"], ["fil", "titre"], ["intox", "comptoir"]):
        dealt = assignments.deal(four, recent, seed="u:d")
        assert dealt in four and dealt not in recent, recent
    # a learner playing one story a day never sees the same shape twice in three days
    played: list[str] = []
    for day in range(12):
        dealt = assignments.deal(four, played, seed=f"u:story-{day}")
        assert dealt not in played[:2]
        played.insert(0, dealt)
    assert set(played) == set(four), "every shape comes round"
    assert assignments.deal(["titre", "intox"], ["intox", "titre"], seed="s") == "titre", "both lately: the oldest"


def test_a_story_with_headlines_and_statements_is_dealt_one_the_learner_did_not_play_lately(db: Session) -> None:
    revue = Revue(db)
    row = revue.start(make_user(db, played=("comptoir", "intox")), week=WEEK, dossier_id=FETE)
    choice = state_of(row).events[0].payload
    assert choice["mode"] == "titre"
    assert "titre" in choice["snapshot"] and not {"comptoir", "fil", "intox"} & set(choice["snapshot"])
    assert [e.kind for e in state_of(row).events] == ["choice"], "no chat arrival"
    row = revue.start(make_user(db, played=("titre", "comptoir")), week=WEEK, dossier_id=FETE)
    choice = state_of(row).events[0].payload
    assert choice["mode"] == "intox" and "intox" in choice["snapshot"] and "titre" not in choice["snapshot"]
    with pytest.raises(RevueError) as caught:
        revue.turn(row, "Bonjour")
    assert (caught.value.status, caught.value.code) == (409, "revue_intox_session")
    with pytest.raises(RevueError) as caught:
        revue.fil(row, None)
    assert caught.value.code == "revue_not_fil"
    # a fil session is not played through the generic route
    bac = revue.start(make_user(db, played=("comptoir", "chat")), week=WEEK, dossier_id="evergreen-bac")
    assert revue.view(bac).mode == "fil"
    assert out_of_order(revue, bac, act="open") == "revue_not_rubrique"


def test_with_the_switch_off_nothing_changes(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False)
    revue = Revue(db)
    row = revue.start(make_user(db, played=("comptoir", "intox")), week=WEEK, dossier_id=FETE)
    with_material = state_of(row).events[0].payload
    monkeypatch.setattr(titre_desk, "titre_of", lambda dossier: None)
    monkeypatch.setattr(intox_desk, "intox_of", lambda dossier: None)
    row2 = revue.start(make_user(db, played=("comptoir", "intox")), week=WEEK, dossier_id=FETE)
    without = state_of(row2).events[0].payload
    assert with_material["mode"] == "comptoir"
    assert not {"titre", "intox", "fil"} & set(with_material["snapshot"])
    assert json.dumps(with_material, sort_keys=True) == json.dumps(without, sort_keys=True)
    assert revue.view(row).titre is None and revue.view(row).intox is None
    assert "titre" not in next(d for d in evergreens_for_week(WEEK) if d.id == FETE).model_dump(mode="json")


# ---------------------------------------------------------------------------
# «L'intox express»
# ---------------------------------------------------------------------------


def _truth(row: RevueSession) -> dict[str, bool]:
    express = evergreen_intox(FETE)
    keys = intox_loop.key_of(str(row.id))
    return {keys[i]: s.true for i, s in enumerate(express.statements)}


def _statement(row: RevueSession, key: str):
    return evergreen_intox(FETE).statements[intox_loop.index_of(str(row.id))[key]]


def answer_all(revue: RevueEncounter, row: RevueSession, *, wrong: tuple[str, ...] = ()) -> None:
    truth = _truth(row)
    for key in intox_loop.KEYS:
        right = "vrai" if truth[key] else "faux"
        act(revue, row, act="answer", key=key, value=({"vrai": "faux", "faux": "vrai"}[right] if key in wrong else right))


def test_the_round_never_says_which_statement_is_false_before_it_is_answered(db: Session) -> None:
    revue, row = start(db, "intox")
    view = revue.view(row).intox
    assert view.step == "read" and view.round is None and view.steps == ["read", "round", "fix", "page"]
    assert out_of_order(revue, row, act="answer", key="a", value="vrai") == "revue_intox_out_of_order"
    view = act(revue, row, act="open").session.intox
    assert view.step == "round" and view.round.current == "a" and view.round.total == 5
    assert view.read.lead.fr, "the story stays one tap away during the round"
    for card in view.round.cards:
        assert card.true is None and card.why is None and card.quote is None and card.wrong_fr is None
    text = json.dumps(view.round.model_dump(mode="json"), ensure_ascii=False)
    for secret in ("21 juin", "ministère", "musiciens"):  # the true values and the distractors
        assert secret not in text, secret
    text = json.dumps(view.model_dump(mode="json"), ensure_ascii=False)
    assert "right_fr" not in text and "distractor" not in text and '"true": true' not in text
    assert out_of_order(revue, row, act="answer", key="b", value="vrai") == "revue_intox_out_of_order", "one at a time"


def test_each_answer_shows_its_verdict_and_the_quote_on_a_false_one_or_a_miss(db: Session) -> None:
    revue, row = start(db, "intox")
    act(revue, row, act="open")
    truth = _truth(row)
    first_true = next(k for k in intox_loop.KEYS if truth[k])
    answer_all(revue, row, wrong=(first_true,))
    view = revue.view(row).intox
    assert view.step == "fix" and view.round.score == 4 and view.round.answered == 5
    for card in view.round.cards:
        assert card.true == truth[card.key] and card.why.tr, "the line in the learner's language"
        shown = card.quote is not None
        assert shown == (not card.true or card.key == first_true)
        if not card.true:
            assert card.wrong_fr and card.wrong_fr in card.text.fr and card.quote.source_name
            assert card.quote.settles_fr in card.quote.quote_fr
    miss = next(c for c in view.round.cards if c.key == first_true)
    assert miss.correct is False and miss.answer == "faux"
    count = len(events(row, "intox"))
    act(revue, row, act="answer", key=first_true, value="vrai")
    assert len(events(row, "intox")) == count, "one answer each: a repeat records nothing"
    assert not [c for c in revue.provider.calls if "edit" in c[0]], "no model call"


def test_a1_corrects_by_picking_and_never_sees_the_true_value_before_the_retry(db: Session) -> None:
    revue, row = start(db, "intox")
    assert out_of_order(revue, row, act="fix", key="a", value="x") == "revue_intox_out_of_order"
    act(revue, row, act="open")
    answer_all(revue, row)
    fix = revue.view(row).intox.fix
    assert fix.input == "pick" and len(fix.items) == 2
    first, second = fix.items
    statement = _statement(row, first.key)
    assert sorted(first.options) == sorted([statement.right_fr, statement.distractor_fr])
    assert first.right_fr is None and first.fixed is None
    wrong = statement.distractor_fr
    item = act(revue, row, act="fix", key=first.key, value=wrong).session.intox.fix.items[0]
    assert item.tries == 1 and not item.resolved and item.right_fr is None and item.fixed is None, "no solution"
    item = act(revue, row, act="fix", key=first.key, value=wrong).session.intox.fix.items[0]
    assert item.tries == 1, "the same pick again records nothing"
    item = act(revue, row, act="fix", key=first.key, value=statement.right_fr).session.intox.fix.items[0]
    assert item.resolved and item.correct and item.fixed.fr and item.right_fr == statement.right_fr
    true_key = next(k for k, v in _truth(row).items() if v)
    with pytest.raises(RevueError) as caught:
        act(revue, row, act="fix", key=true_key, value=statement.right_fr)
    assert caught.value.status == 422, "a true statement is not corrected"
    other = _statement(row, second.key)
    act(revue, row, act="fix", key=second.key, value=other.distractor_fr)
    view = act(revue, row, act="fix", key=second.key, value=other.distractor_fr).session.intox
    assert view.fix.items[1].tries == 1
    with pytest.raises(RevueError):
        act(revue, row, act="fix", key=second.key, value="le 1er mai")
    alt = [o for o in view.fix.items[1].options if o != other.distractor_fr]
    view = act(revue, row, act="fix", key=second.key, value=alt[0]).session.intox
    assert view.step == "page"


def test_b1_rewrites_and_numbers_are_compared_digit_for_digit(db: Session) -> None:
    revue, row = start(db, "intox", level="B1.1", native="de")
    act(revue, row, act="open")
    answer_all(revue, row)
    fix = revue.view(row).intox.fix
    assert fix.input == "write" and fix.items[0].options == []
    day = next(i for i in fix.items if _statement(row, i.key).swap == "day")
    who = next(i for i in fix.items if _statement(row, i.key).swap == "who")
    assert act(revue, row, act="fix", key=day.key, text="le 21").error.code == "too_short"
    item = act(revue, row, act="fix", key=day.key, text="La fête a lieu le 12 juin.").session.intox.fix
    item = next(i for i in item.items if i.key == day.key)
    assert item.tries == 1 and not item.resolved and item.right_fr is None, "21 ≠ 12: digit for digit"
    item = act(revue, row, act="fix", key=day.key, text="La fête a lieu le 21 juin, pas le 14 juillet.").session.intox.fix
    item = next(i for i in item.items if i.key == day.key)
    assert item.resolved and item.correct
    assert intox_loop.grade_fix(_statement(row, day.key), text="La fête a lieu le 14 juillet et le 21 juin.") is False
    act(revue, row, act="fix", key=who.key, text="Selon les voisins, c'est un succès.")
    view = act(revue, row, act="fix", key=who.key, text="Selon les musiciens, c'est un succès.").session.intox
    item = next(i for i in view.fix.items if i.key == who.key)
    assert item.resolved and item.correct is False and item.right_fr == "le ministère de la Culture", "after two"
    assert view.step == "page"

    _, closing = revue.close(row)
    page = closing.intox_page
    assert page is not None and page.score == 5 and page.fixed == 1 and page.total == 5
    assert all("14 juillet" not in line.text_fr and "voisins" not in line.text_fr for line in page.lines), \
        "the five statements as they should read"
    mine = [line.learner_fr for line in page.lines if line.learner_fr]
    assert mine == ["La fête a lieu le 21 juin, pas le 14 juillet."], "only a right correction is printed as theirs"
    artifact = state_of(row).current_artifact
    assert artifact["kind"] == "intox" and artifact["score"] == 5
    assert closing.dispatch.kicker_fr == "L'intox express de Romy" and closing.vignette.ring == "report"
    memory = db.scalars(select(NPCMemory).where(NPCMemory.scene_id == str(row.id))).all()
    assert any("tu as démonté l'intox" in m.content for m in memory)
    assert revue.close(row)[1] == closing, "idempotent"
    assert out_of_order(revue, row, act="open") == "revue_intox_out_of_order"
    assert not [c for c in revue.provider.calls if "edit" in c[0]], "no model call at the close"


def test_the_close_waits_for_both_corrections(db: Session) -> None:
    revue, row = start(db, "intox")
    act(revue, row, act="open")
    answer_all(revue, row)
    with pytest.raises(RevueError) as caught:
        revue.close(row)
    assert (caught.value.status, caught.value.code) == (409, "revue_intox_out_of_order")


# ---------------------------------------------------------------------------
# «Le titre»
# ---------------------------------------------------------------------------


def _key(row: RevueSession, role: str) -> str:
    desk = evergreen_titre(FETE)
    return titre_loop.key_of(str(row.id))[titre_loop.role_index(desk, role)]


def solve_three(revue: RevueEncounter, row: RevueSession) -> None:
    act(revue, row, act="open")
    act(revue, row, act="pick", key=_key(row, "honest"))


def solve_trap(revue: RevueEncounter, row: RevueSession) -> None:
    desk = evergreen_titre(FETE)
    band = str(enc.load(row).plan.learner.band)
    text = desk.headline("exaggerated").for_band(band).fr
    act(revue, row, act="trap", words=titre_loop.wrong_span(text, desk.wrong_fr))


def test_three_headlines_two_tries_the_why_of_a_wrong_pick_and_no_solution_before_the_retry(db: Session) -> None:
    revue, row = start(db, "titre")
    view = revue.view(row).titre
    assert view.step == "read" and view.three is None and view.steps == ["read", "three", "trap", "build", "page"]
    assert out_of_order(revue, row, act="pick", key="a") == "revue_titre_out_of_order"
    view = act(revue, row, act="open").session.titre
    three = view.three
    assert three.by.name_fr and three.by.id == comptoir.GUS_ID, "Gus proposes all three"
    assert all(h.role is None and h.why is None for h in three.headlines) and three.solution is None
    text = json.dumps(view.model_dump(mode="json"), ensure_ascii=False)
    assert "honest" not in text and "exaggerated" not in text and "wrong_fr" not in text
    off, exaggerated = _key(row, "off"), _key(row, "exaggerated")
    three = act(revue, row, act="pick", key=off).session.titre.three
    picked = next(h for h in three.headlines if h.key == off)
    assert picked.role == "off" and picked.why.tr and picked.claim.id == "c1", "the why in English, with its claim"
    assert three.solution is None and not three.resolved and three.correct is None, "no solution before the retry"
    assert all(h.role is None for h in three.headlines if h.key != off)
    count = len(events(row, "titre"))
    act(revue, row, act="pick", key=off)
    assert len(events(row, "titre")) == count, "a repeat records nothing"
    view = act(revue, row, act="pick", key=exaggerated).session.titre
    assert view.three.resolved and view.three.correct is False and view.three.solution == _key(row, "honest")
    assert view.step == "trap"
    act(revue, row, act="pick", key=_key(row, "honest"))
    assert len(events(row, "titre")) == count + 1, "never more than two tries"


def test_the_trap_is_graded_against_the_stored_words(db: Session) -> None:
    revue, row = start(db, "titre")
    solve_three(revue, row)
    trap = revue.view(row).titre.trap
    words = [w.fr for w in trap.words]
    assert words == ["La", "fête", "plaît", "à", "tout", "le", "monde"] and trap.solution == []
    assert act(revue, row, act="trap", words=[]).error.code == "pick_words"
    trap = act(revue, row, act="trap", words=[1, 4]).session.titre.trap
    assert not trap.resolved and trap.fine == [1] and trap.solution == [] and trap.why is None, "fête is true"
    assert titre_loop.grade_trap("La fête plaît à tout le monde", "tout le monde", [5])["correct"] is False, "«le» alone"
    assert titre_loop.grade_trap("La fête plaît à tout le monde", "tout le monde", [4, 6])["correct"] is True
    view = act(revue, row, act="trap", words=[4, 5, 6]).session.titre
    assert view.trap.resolved and view.trap.correct and view.trap.solution == [4, 5, 6]
    assert view.trap.why.fr.startswith("Pas tout le monde") and view.trap.claim.id == "c3"
    assert view.step == "build"


def test_a1_builds_from_tiles_without_a_model_call(db: Session) -> None:
    revue, row = start(db, "titre")
    assert out_of_order(revue, row, act="build", parts=[0, 0]) == "revue_titre_out_of_order"
    solve_three(revue, row)
    solve_trap(revue, row)
    build = revue.view(row).titre.build
    assert build.input == "tiles" and build.avoid_fr == "tout le monde" and len(build.subjects) == 2
    assert act(revue, row, act="build", parts=[5, 0]).error.code == "pick_tiles"
    view = act(revue, row, act="build", parts=[0, 0]).session.titre
    assert view.build.proof == "clean" and view.build.printed_fr == "La Fête de la musique est gratuite"
    assert view.step == "page"
    assert not [c for c in revue.provider.calls if c[0] == "titre_edit"], "A1: no model call"

    view, closing = revue.close(row)
    page = closing.titre_page
    assert page is not None and page.headline_fr == "La Fête de la musique est gratuite" and page.lead_fr
    assert closing.dispatch.headline_fr == page.headline_fr and closing.dispatch.byline_fr.startswith("Romy Tremblay, avec toi")
    artifact = state_of(row).current_artifact
    assert artifact["kind"] == "titre" and artifact["learner_fr"] == "", "tiles are not the learner's words"
    assert closing.vignette is not None and closing.vignette.ring == "headline"
    assert view.artifact.kind == "titre"
    assert revue.close(row)[1] == closing


def test_a2_completes_the_frame_romy_marks_and_the_learner_fixes(db: Session) -> None:
    revue, row = start(db, "titre", level="A2.1", native="de")
    solve_three(revue, row)
    solve_trap(revue, row)
    build = revue.view(row).titre.build
    assert build.input == "frame" and build.frame.fr == "La Fête de la musique" and build.frame.tr
    assert act(revue, row, act="build", text="plaît à tout le monde").error.code == "says_too_much"
    assert act(revue, row, act="build", text="dure 30 heures").error.code == "number_not_in_claims"
    assert not events(row, "titre")[-1].get("act") == "build", "a refusal records nothing"
    result = act(revue, row, act="build", text="est gratuite et le gens sont content")
    build = result.session.titre.build
    assert build.proof == "marked" and build.printed_fr is None, "nothing printed before the fix"
    assert {m.kind for m in build.marks} == {"accord"}
    assert "les gens" not in json.dumps(result.session.model_dump(mode="json"), ensure_ascii=False), "no solution"
    build = act(revue, row, act="build_fix", text="La Fête de la musique est gratuite et les gens sont contents").session.titre.build
    assert build.proof == "fixed" and build.printed_fr == "La Fête de la musique est gratuite et les gens sont contents"
    _, closing = revue.close(row)
    assert closing.titre_page.proof == "fixed" and state_of(row).current_artifact["learner_fr"]


def test_b1_writes_freely_and_a_failing_edit_prints_it_as_written(db: Session) -> None:
    class Down(FakeRevueProvider):
        def titre_edit(self, context):
            raise RuntimeError("down")

    revue, row = start(db, "titre", provider=Down(), level="B1.1")
    solve_three(revue, row)
    solve_trap(revue, row)
    assert act(revue, row, act="build", text="Une fête gratuite qui fait aussi du bruit et beaucoup de plaintes chez "
                                              "les voisins du quartier").error.code == "too_long"
    build = act(revue, row, act="build", text="Une fête gratuite, mais du bruit pour les voisins.").session.titre.build
    assert build.proof == "as_written" and build.printed_fr == "Une fête gratuite, mais du bruit pour les voisins"


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
    email = f"rub-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "securepass123", "target_language": "fr",
                                               "native_language": "en"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_one_route_plays_both_assignments_and_is_a_paid_route(api: TestClient, monkeypatch) -> None:
    assert ("POST", "/revue/sessions/{session_id}/rubrique") in PAID_ROUTES
    for mode in ("intox", "titre"):
        headers = login(api)
        monkeypatch.setattr(assignments, "deal", lambda offered, recent, seed, mode=mode: mode)
        session = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, "dossier_id": FETE}).json()
        assert session["mode"] == mode and session[mode]["step"] == "read" and session["comptoir"] is None
        path = f"/api/v1/revue/sessions/{session['id']}/rubrique"
        first = {"intox": {"act": "answer", "key": "a", "value": "vrai"}, "titre": {"act": "pick", "key": "a"}}[mode]
        response = api.post(path, headers=headers, json=first)
        assert response.status_code == 409 and response.json()["detail"]["code"] == f"revue_{mode}_out_of_order"
        assert response.json()["detail"]["step"] == "read"
        response = api.post(path, headers=headers, json={"act": "open"})
        assert response.status_code == 200 and response.json()["session"][mode]["step"] != "read"
        assert api.post(path, headers=headers, json={"act": "dance"}).status_code == 422
    response = api.post(path, headers=headers, json={"act": "pick", "key": "z"})
    assert response.status_code == 422
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.post(path, headers=headers, json={"act": "open"}).status_code == 404
