"""«Au comptoir» (WP-119, owner 2026-10-19): the learner's loop (``comptoir_loop.py``) and its route.

A session starts in comptoir mode only with the switch on and takes to play (an evergreen's
shipped ones, or one desk call at the start); otherwise it is the chat, unchanged. Every act
in order at A1, A2 and B1; every act out of order is a 409; two wrong guesses reveal the liar;
Romy's edit with the fake provider, with a failing one, twice; «La page», the dispatch and the
memories at the close; the view never shows an answer before its time.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator, Iterator

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
from app.schemas.revue import RvComptoirRequest
from app.services.revue import comptoir, comptoir_loop
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter, RevueError
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.pictogram import FakePictogramProvider
from app.services.revue.state import ConversationState
from tests.test_revue_comptoir import _Desk, celine, gold

WEEK = "2026-W43"
MARCHE = "evergreen-marche-du-dimanche"
GREVE = "evergreen-greve-transports"
ROMY, MARGAUX, GUS = "romy_tremblay", "margaux_barman", "augustin_de_roncourt"
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
    comptoir.forget_cache()


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def Revue(db: Session, provider: FakeRevueProvider, **kwargs) -> RevueEncounter:  # noqa: N802 - reads as the class
    revue = RevueEncounter(db, provider, **kwargs)
    revue.pictogram_provider = FakePictogramProvider()  # the vignette's drawing, offline
    return revue


def make_user(db: Session, *, level: str = "A1.1", native: str = "en") -> User:
    user = User(id=uuid.uuid4(), email=f"comptoir-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate=level, native_language=native, interests="")
    db.add(user)
    db.commit()
    return user


def act(revue: RevueEncounter, row: RevueSession, **body):
    return revue.comptoir(row, RvComptoirRequest(**body))


def state_of(row: RevueSession) -> ConversationState:
    return ConversationState.from_json(row.state)


def out_of_order(revue: RevueEncounter, row: RevueSession, **body) -> str:
    with pytest.raises(RevueError) as caught:
        act(revue, row, **body)
    assert caught.value.status == 409, caught.value.detail
    return caught.value.code


def wire(view) -> str:
    return json.dumps(view.model_dump(mode="json"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# The mode
# ---------------------------------------------------------------------------


def test_with_the_switch_off_nothing_changes(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", False)
    revue = Revue(db, FakeRevueProvider())
    user = make_user(db)
    row = revue.start(user, week=WEEK, dossier_id=MARCHE)
    view = revue.view(row)
    assert view.mode == "chat" and view.comptoir is None
    choice = state_of(row).events[0]
    assert "mode" not in choice.payload and "comptoir" not in choice.payload["snapshot"]
    assert any(e.kind == "turn_romy" for e in state_of(row).events), "Romy's arrival, as today"
    ordered, _ = revue.ranked(user, WEEK)
    assert [d.id for d in ordered][:2] == [GREVE, MARCHE], "off: the kiosk's own order"
    card = enc.story_card(ordered[1])
    assert card.question_fr is None and card.cast is None


def test_with_the_switch_on_a_story_with_takes_starts_at_the_counter(db: Session) -> None:
    revue = Revue(db, FakeRevueProvider())
    user = make_user(db)
    ordered, _ = revue.ranked(user, WEEK)
    assert ordered[0].id == MARCHE, "the stories the regulars argue about come first"
    card = enc.story_card(ordered[0])
    assert card.question_fr == "Aligre ouvre six jours sur sept. Bonne idée ?"
    assert card.cast == [ROMY, MARGAUX, GUS]

    row = revue.start(user, week=WEEK)
    choice = state_of(row).events[0]
    assert row.dossier_id == MARCHE and choice.payload["mode"] == "comptoir"
    assert choice.payload["snapshot"]["comptoir"]["question"]["fr"] == card.question_fr
    assert [e.kind for e in state_of(row).events] == ["choice"], "no chat arrival"
    view = revue.view(row)
    assert view.mode == "comptoir" and view.comptoir is not None
    assert view.comptoir.step == "read" and view.comptoir.steps == ["read", "takes", "intox", "opinion", "page"]
    assert view.comptoir.band == "a1" and view.comptoir.has_intox
    assert [c.id for c in view.comptoir.cast] == [ROMY, MARGAUX, GUS]
    assert view.comptoir.cast[2].take.tr, "the translate chip, in the learner's language"
    assert view.comptoir.read.dateline_fr and view.comptoir.read.lead.fr

    # a chat route on a comptoir session
    with pytest.raises(RevueError) as caught:
        revue.turn(row, "Bonjour")
    assert (caught.value.status, caught.value.code) == (409, "revue_comptoir_session")
    with pytest.raises(RevueError):
        revue.make_options(row)


def test_a_story_without_takes_gets_one_desk_call_at_the_start(db: Session, monkeypatch) -> None:
    story = celine()
    monkeypatch.setattr(enc, "available_dossiers", lambda week: [story])
    desk = _Desk([gold()])
    revue = Revue(db, FakeRevueProvider(), desk=desk)
    row = revue.start(make_user(db), week=WEEK)
    assert len(desk.calls) == 1
    choice = state_of(row).events[0]
    assert choice.payload["mode"] == "comptoir" and choice.payload["cost_usd"] == pytest.approx(0.004)
    # the next learner plays the same takes: no second call
    row2 = Revue(db, FakeRevueProvider(), desk=desk).start(make_user(db), week=WEEK)
    assert len(desk.calls) == 1 and revue.view(row2).mode == "comptoir"


def test_a_failing_or_refusing_desk_leaves_the_session_a_chat(db: Session, monkeypatch) -> None:
    story = celine()
    monkeypatch.setattr(enc, "available_dossiers", lambda week: [story])
    revue = Revue(db, FakeRevueProvider(), desk=_Desk([RuntimeError("down")]))
    row = revue.start(make_user(db), week=WEEK)
    assert revue.view(row).mode == "chat"
    assert any(e.kind == "turn_romy" for e in state_of(row).events)

    comptoir.forget_cache()
    revue = Revue(db, FakeRevueProvider(), desk=_Desk([{"fit": "skip"}]))
    row = revue.start(make_user(db), week=WEEK)
    assert revue.view(row).mode == "chat"
    with pytest.raises(RevueError) as caught:
        act(revue, row, act="vote", value="pour")
    assert caught.value.code == "revue_not_comptoir"


def test_beside_the_deterministic_provider_no_desk_is_called(db: Session, monkeypatch) -> None:
    story = celine()
    monkeypatch.setattr(enc, "available_dossiers", lambda week: [story])
    revue = Revue(db, FakeRevueProvider())
    assert revue._comptoir_desk() is None

    def no_desk(*args: object, **kwargs: object) -> None:
        raise AssertionError("no desk call beside the deterministic provider")

    monkeypatch.setattr(comptoir, "desk_provider", no_desk)
    assert revue.view(revue.start(make_user(db), week=WEEK)).mode == "chat"


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def test_a1_every_act_in_order_two_wrong_guesses_and_the_page(db: Session) -> None:
    fake = FakeRevueProvider()
    revue = Revue(db, fake)
    user = make_user(db, level="A1.1", native="en")
    row = revue.start(user, week=WEEK)

    assert out_of_order(revue, row, act="react", guest_id=ROMY, value="agree") == "revue_comptoir_out_of_order"
    view = act(revue, row, act="vote", value="pour").session.comptoir
    assert view.step == "takes" and view.vote == "pour"
    assert out_of_order(revue, row, act="react", guest_id=GUS, value="agree"), "takes are revealed in order"
    assert out_of_order(revue, row, act="intox_who", guest_id=GUS)
    assert out_of_order(revue, row, act="opinion", value="pour", reason_index=0)
    act(revue, row, act="react", guest_id=ROMY, value="agree")
    act(revue, row, act="react", guest_id=MARGAUX, value="disagree")
    view = act(revue, row, act="react", guest_id=GUS, value="disagree").session.comptoir
    assert view.step == "intox" and [c.reaction for c in view.cast] == ["agree", "disagree", "disagree"]

    # the view never tells who lied, nor the answers, before the learner found out
    assert view.intox is not None and view.intox.by is None and view.intox.options == []
    assert view.intox.ask is None and view.intox.hint_claim is None and view.intox.fix is None
    assert '"right_fr"' not in wire(view) and "91 marchés" not in wire(view.intox)
    assert view.opinion is None and view.kit is None
    liar_quote = next(q for q in view.intox.quotes if q.cast_id == GUS)
    assert liar_quote.quote_fr == "Sept jours sur sept ? Mon cher, c'est trop de bruit."

    view = act(revue, row, act="intox_who", guest_id=MARGAUX).session.comptoir
    assert view.intox.resolved is False and view.intox.hint_claim is not None and view.intox.by is None
    view = act(revue, row, act="intox_who", guest_id=ROMY).session.comptoir
    assert view.intox.resolved and view.intox.found is False and view.intox.by == GUS
    assert sorted(view.intox.options) == ["91 marchés", "six jours sur sept"]
    assert view.intox.ask is not None and view.intox.ask.tr
    assert out_of_order(revue, row, act="intox_who", guest_id=GUS), "never more than two tries"

    view = act(revue, row, act="intox_fix", value="91 marchés").session.comptoir
    fix = view.intox.fix
    assert fix is not None and fix.correct is False
    assert fix.line_fr == "C'est faux, Gus ! C'est six jours sur sept, pas sept jours sur sept."
    assert fix.claim is not None and fix.claim.source.name and fix.caught.fr
    assert view.step == "opinion" and view.kit is not None and view.kit.input == "tiles"
    assert view.kit.opponents["pour"] == GUS

    view = act(revue, row, act="opinion", value="pour", reason_index=0).session.comptoir
    opinion = view.opinion
    assert opinion.learner_fr == "Je suis pour, parce que le marché est vivant."
    assert opinion.edited_fr == opinion.learner_fr and opinion.notes == []
    assert opinion.reply.by == GUS and opinion.reply.line.fr == view_reply(row, "pour")
    assert [c.fr for c in opinion.comebacks][:2] == ["Pas du tout !", "Un peu…"] and len(opinion.comebacks) == 3
    assert not [c for c in fake.calls if c[0] == "comptoir_edit"], "A1: no model call"
    assert out_of_order(revue, row, act="vote", value="contre"), "the vote is fixed once the opinion is given"

    view = act(revue, row, act="comeback", index=2).session.comptoir
    assert view.step == "page" and view.opinion.comeback.last_word.fr == "Touché."
    assert view.opinion.comeback.last_word.tr == "Touché."

    view, closing = revue.close(row)
    page = closing.comptoir_page
    assert page is not None and page.question_fr == "Aligre ouvre six jours sur sept. Bonne idée ?"
    assert [q.cast_id for q in page.quotes] == [ROMY, MARGAUX, GUS]
    assert page.mine.quote_fr == opinion.edited_fr and page.mine.stance == "pour"
    assert (page.votes.pour, page.votes.contre, page.votes.nuance) == (2, 1, 1)
    assert page.intox is not None and page.intox.wrong_fr == "sept jours sur sept" and page.intox.source_name
    assert closing.dispatch.kicker_fr == "Le micro-trottoir de Romy"
    assert closing.dispatch.headline_fr == page.question_fr
    assert closing.dispatch.body_fr[-1] == f"Toi : « {opinion.edited_fr} »"
    assert closing.romy_line_fr == "Merci ! Ta voix est dans le micro-trottoir."
    assert view.artifact is not None and view.artifact.kind == "opinion" and view.artifact.learner_fr
    assert view.status == "closed" and view.comptoir.step == "page"
    assert not [c for c in fake.calls if c[0] == "close"], "the close makes no model call"

    memories = db.scalars(select(NPCMemory).where(NPCMemory.user_id == user.id)).all()
    assert sorted(m.npc_id for m in memories) == sorted([ROMY, MARGAUX, GUS])
    romy = next(m for m in memories if m.npc_id == ROMY)
    assert "micro-trottoir" in romy.content and opinion.edited_fr in romy.content
    vignette = db.scalars(select(RevueVignette).where(RevueVignette.session_id == row.id)).first()
    assert vignette is not None and vignette.ring == "report"
    assert db.scalars(select(PilotEvent).where(PilotEvent.entity_id == str(row.id))).first() is not None

    assert revue.close(row)[1] == closing, "the close is idempotent"
    assert out_of_order(revue, row, act="comeback", index=0)


def view_reply(row: RevueSession, stance: str) -> str:
    snapshot = state_of(row).events[0].payload["snapshot"]["comptoir"]
    return snapshot["replies"][stance]["line"]["fr"]


def test_a2_romys_edit_and_the_reply_in_german(db: Session) -> None:
    fake = FakeRevueProvider()
    revue = Revue(db, fake)
    row = revue.start(make_user(db, level="A2.1", native="de"), week=WEEK)
    act(revue, row, act="vote", value="contre")
    for guest in (ROMY, MARGAUX, GUS):
        act(revue, row, act="react", guest_id=guest, value="agree")
    view = act(revue, row, act="intox_who", guest_id=GUS).session.comptoir
    assert view.intox.found is True and view.intox.tries == [GUS] and view.intox.hint_claim is None
    view = act(revue, row, act="intox_fix", value="six jours sur sept").session.comptoir
    assert view.intox.fix.correct and view.kit.input == "frame" and len(view.kit.bank) == 6
    assert view.kit.frames["contre"].tr and "weil" in view.kit.frames["contre"].tr

    result = act(revue, row, act="opinion", value="contre", text="")
    assert result.error_fr and result.session.comptoir.opinion is None, "an empty reason is answered, not recorded"
    view = act(revue, row, act="opinion", value="contre", text="le gens sont content au supermarché").session.comptoir
    opinion = view.opinion
    assert opinion.learner_fr == "À mon avis, ce n'est pas une bonne idée, parce que le gens sont content au supermarché."
    assert opinion.edited_fr == "À mon avis, ce n'est pas une bonne idée, parce que les gens sont contents au supermarché."
    assert [n.span_fr for n in opinion.notes] == ["les gens", "sont contents"]
    assert opinion.notes[0].why == "Plural: les gens"
    assert opinion.reply.by == ROMY and opinion.reply.line.tr, "Romy answers a «contre», in German too"
    edits = [c for c in fake.calls if c[0] == "comptoir_edit"]
    assert len(edits) == 1 and edits[0][1]["notes_language"] == "de"

    again = act(revue, row, act="opinion", value="contre", text="autre chose").session.comptoir
    assert again.opinion.edited_fr == opinion.edited_fr and len([c for c in fake.calls if c[0] == "comptoir_edit"]) == 1
    events = [e for e in state_of(row).events if e.kind == "comptoir" and e.payload["act"] == "opinion"]
    assert len(events) == 1, "a double submit returns the stored result"
    learner_turns = [e for e in state_of(row).events if e.kind == "turn_learner"]
    assert learner_turns and learner_turns[-1].payload["text_fr"] == opinion.learner_fr

    view = act(revue, row, act="comeback", index=0).session.comptoir
    assert view.opinion.comeback.last_word.fr == "Ah bon ? On en reparle demain !"
    assert view.opinion.comeback.last_word.tr == "Ach ja? Darüber reden wir morgen weiter!"


def test_b1_writes_the_correction_and_the_comeback(db: Session) -> None:
    revue = Revue(db, FakeRevueProvider())
    row = revue.start(make_user(db, level="B1.1", native="en"), week=WEEK)
    act(revue, row, act="vote", value="nuance")
    for guest in (ROMY, MARGAUX, GUS):
        act(revue, row, act="react", guest_id=guest, value="disagree")
    view = act(revue, row, act="intox_who", guest_id=GUS).session.comptoir
    assert view.intox.options == [] and view.intox.prefill_fr == "C'est faux, Gus ! C'est …, pas sept jours sur sept."
    result = act(revue, row, act="intox_fix", text=view.intox.prefill_fr)
    assert result.error_fr, "the prefill as it is: complete it first"
    view = act(revue, row, act="intox_fix", text="C'est faux, Gus ! C'est six jours sur sept, pas sept.").session.comptoir
    assert view.intox.fix.correct and view.kit.input == "free" and view.kit.bank == []
    assert view.kit.phrase.fr == "Je ne suis pas d'accord avec…, parce que…"

    view = act(revue, row, act="opinion", value="nuance", text="ça depend, le marché est tres bien mais il y a trop de monde").session.comptoir
    assert view.opinion.edited_fr.startswith("Ça depend, le marché est très bien")
    assert view.opinion.comebacks == []
    assert act(revue, row, act="comeback", text="  ").error_fr
    view = act(revue, row, act="comeback", text="Et toi, tu viens au marché le dimanche ?").session.comptoir
    assert view.opinion.comeback.text_fr.startswith("Et toi") and view.opinion.comeback.last_word.fr.startswith("Touché.")
    _, closing = revue.close(row)
    assert closing.comptoir_page.votes.nuance == 2


def grade(**kwargs) -> bool:
    takes = next(d for d in evergreens_for_week(WEEK) if d.id == MARCHE).comptoir
    return comptoir_loop.grade_fix(takes.intox, **kwargs)


def test_the_correction_is_graded_on_the_true_value() -> None:
    assert grade(value="Six jours sur sept")
    assert not grade(value="91 marchés")
    assert grade(text="C'est faux, Gus ! C'est six jours sur sept, pas sept jours sur sept.")
    assert grade(text="six jours sur sept")
    assert not grade(text="C'est faux, Gus ! C'est sept jours, pas six jours sur sept.")
    numbers = celine().model_copy(deep=True)
    from app.services.revue.comptoir import repair_comptoir

    intox = repair_comptoir(gold(), numbers)[0].intox
    assert comptoir_loop.grade_fix(intox, text="C'est faux, Gus ! C'est 500 000, pas un million.")
    assert comptoir_loop.grade_fix(intox, text="Plus de 500000 personnes !")
    assert not comptoir_loop.grade_fix(intox, text="C'est faux ! C'est un million, pas 500 000.")


def test_a_failing_edit_keeps_the_learners_words_and_the_desks_reply(db: Session) -> None:
    class Broken(FakeRevueProvider):
        def comptoir_edit(self, context):
            raise RuntimeError("down")

    class Wild(FakeRevueProvider):
        def comptoir_edit(self, context):
            return {"edited_fr": "Le marché d'Aligre ouvre 7 jours sur 7 et c'est formidable pour tout le quartier, "
                                 "vraiment, je le dis et je le répète à tout le monde ici.",
                    "notes": [], "reply_fr": "Merde alors !", "reply_en": "", "reply_de": ""}

    for provider in (Broken(), Wild()):
        revue = Revue(db, provider)
        row = revue.start(make_user(db, level="B1.1"), week=WEEK)
        act(revue, row, act="vote", value="pour")
        for guest in (ROMY, MARGAUX, GUS):
            act(revue, row, act="react", guest_id=guest, value="agree")
        act(revue, row, act="intox_who", guest_id=GUS)
        act(revue, row, act="intox_fix", text="C'est six jours sur sept, pas sept jours sur sept.")
        view = act(revue, row, act="opinion", value="pour", text="j'aime le marché").session.comptoir
        assert view.opinion.edited_fr == "j'aime le marché.", type(provider).__name__
        assert view.opinion.notes == []
        assert view.opinion.reply.line.fr == view_reply(row, "pour")


def test_a_band_without_the_intox_has_four_steps(db: Session, monkeypatch) -> None:
    story = celine()
    raw = gold()
    b1 = next(g for g in raw["guests"] if g["id"] == GUS)["b1"]
    b1["fr"] = "Mon cher, tant de monde pour les mêmes chansons, c'est une foule, pas un public. Je préfère le silence."
    monkeypatch.setattr(enc, "available_dossiers", lambda week: [story])
    revue = Revue(db, FakeRevueProvider(), desk=_Desk([raw]))
    row = revue.start(make_user(db, level="B1.1"), week=WEEK)
    view = revue.view(row).comptoir
    assert view.steps == ["read", "takes", "opinion", "page"] and not view.has_intox
    act(revue, row, act="vote", value="pour")
    for guest in (ROMY, MARGAUX, GUS):
        view = act(revue, row, act="react", guest_id=guest, value="agree").session.comptoir
    assert view.step == "opinion" and view.intox is None
    assert out_of_order(revue, row, act="intox_who", guest_id=GUS)
    act(revue, row, act="opinion", value="pour", text="Céline chante bien.")
    _, closing = revue.close(row)
    assert closing.comptoir_page.intox is None, "the close needs the opinion, not the comeback"


def test_the_close_waits_for_the_opinion(db: Session) -> None:
    revue = Revue(db, FakeRevueProvider())
    row = revue.start(make_user(db), week=WEEK)
    act(revue, row, act="vote", value="pour")
    with pytest.raises(RevueError) as caught:
        revue.close(row)
    assert (caught.value.status, caught.value.code) == (409, "revue_comptoir_out_of_order")
    assert caught.value.extra["step"] == "takes"


def test_resume_lands_on_the_same_step(db: Session) -> None:
    revue = Revue(db, FakeRevueProvider())
    row = revue.start(make_user(db), week=WEEK)
    act(revue, row, act="vote", value="contre")
    act(revue, row, act="react", guest_id=ROMY, value="agree")
    db.expire_all()
    again = Revue(db, FakeRevueProvider()).view(db.get(RevueSession, row.id))
    assert again.comptoir.step == "takes" and again.comptoir.vote == "contre"
    assert [c.reaction for c in again.comptoir.cast] == ["agree", None, None]


def test_a1_tiles_elide_and_a2_keeps_a_learner_who_wrote_the_frame() -> None:
    assert comptoir_loop.a1_sentence("contre", "il y a trop de monde") == "Je suis contre, parce qu'il y a trop de monde."
    assert comptoir_loop.a1_sentence("nuance", "c'est beau mais cher") == "Ça dépend, parce que c'est beau mais cher."
    frame = "À mon avis, c'est une bonne idée, parce que"
    assert comptoir_loop.a2_sentence(frame, "les légumes sont frais") == f"{frame} les légumes sont frais."
    assert comptoir_loop.a2_sentence(frame, "À mon avis, c'est une bonne idée parce que j'aime ça !") == (
        "À mon avis, c'est une bonne idée parce que j'aime ça !")


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
    email = f"comptoir-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "securepass123", "target_language": "fr",
                                               "native_language": "en"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_the_route_is_invisible_while_either_switch_is_off(api: TestClient, monkeypatch) -> None:
    headers = login(api)
    session = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK}).json()
    assert session["mode"] == "comptoir" and session["comptoir"]["step"] == "read"
    path = f"/api/v1/revue/sessions/{session['id']}/comptoir"
    response = api.post(path, headers=headers, json={"act": "vote", "value": "pour"})
    assert response.status_code == 200 and response.json()["session"]["comptoir"]["step"] == "takes"
    response = api.post(path, headers=headers, json={"act": "react", "guest_id": GUS, "value": "agree"})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "revue_comptoir_out_of_order"
    assert response.json()["detail"]["step"] == "takes"
    assert api.post(path, headers=headers, json={"act": "dance"}).status_code == 422
    turn = api.post(f"/api/v1/revue/sessions/{session['id']}/turns", headers=headers, json={"text": "Salut"})
    assert turn.status_code == 409 and turn.json()["detail"]["code"] == "revue_comptoir_session"

    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", False)
    assert api.post(path, json={"act": "vote", "value": "pour"}).status_code == 404, "before auth"
    assert api.post(path, headers=headers, json={"act": "vote", "value": "pour"}).status_code == 404
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.post(path, headers=headers, json={"act": "vote", "value": "pour"}).status_code == 404
    assert ("POST", "/revue/sessions/{session_id}/comptoir") in PAID_ROUTES


def test_a_chat_session_answers_409(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", False)
    headers = login(api)
    session = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK}).json()
    assert session["mode"] == "chat" and session["comptoir"] is None
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    response = api.post(f"/api/v1/revue/sessions/{session['id']}/comptoir", headers=headers,
                        json={"act": "vote", "value": "pour"})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "revue_not_comptoir"
