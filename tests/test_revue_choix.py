"""«Papier · le choix» (owner 2026-11-22): cut the scope, let pedagogy and the learner choose.

1. Scope: only the assignments ``REVUE_ASSIGNMENTS_OFFERED`` names (default «Au comptoir» and
   «Le titre») are dealt, and only their desks run each morning.
2. ``REVUE_PEDAGOGY_PICK_ENABLED``: the stories rank by the learner's due words, the day's rule
   and their interests (a real weight); the pick carries a ``why``; the deal prefers the
   assignment whose material exercises the rule.
3. ``REVUE_CHOICE_ENABLED``: the offer carries a front page of up to three stories, different
   rubrics where possible, each with its ``why``; the start takes the chosen one.
Every switch off: nothing changes.
"""

from __future__ import annotations

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
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.story import Story
from app.db.models.user import User
from app.main import create_app
from app.services.revue import assignments, choix, comptoir
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.state import ConversationState

WEEK = "2026-W25"
FETE = "evergreen-fete-de-la-musique"
BAC = "evergreen-bac"
MARCHE = "evergreen-marche-du-dimanche"
GREVE = "evergreen-greve-transports"
ALL = "comptoir,fil,titre,intox,photo,micro"
REVUE_TABLES = (Story.__table__, NPC.__table__, NPCMemory.__table__, RevueSession.__table__, RevueDossier.__table__,
                RevuePictogram.__table__, RevueVignette.__table__, PilotEvent.__table__)

OPINION = {"id": "FR2_B11_OPINION", "name": "Meinung sagen", "rule": "À mon avis …",
           "detectors": [r"\bà\s+mon\s+avis\b"]}
QUESTIONS = {"id": "FR2_A11_QUESTIONS", "name": "Fragen", "rule": "Est-ce que …", "detectors": [r"\best-ce qu(?:e|')"]}
NUMBERS = {"id": "FR2_A11_NUMBERS", "name": "Zahlen", "rule": "…", "detectors": [r"\bjuin\b"]}
STRIKE = {"id": "FR2_TEST_STRIKE", "name": "Streik", "rule": "…", "detectors": [r"\bgrève"]}


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
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_OFFERED", "comptoir,titre")
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", False)
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", False)
    comptoir.forget_cache()


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def focus(monkeypatch, *, due: tuple[str, ...] = (), rule: dict | None = None, today: bool = True) -> None:
    """The learner's due words and rule, as the app would read them."""

    monkeypatch.setattr(choix, "_due_words", lambda db, user, now: due)
    monkeypatch.setattr(choix, "_rule", lambda db, user, language, now: (rule, today if rule else False))


def make_user(db: Session, *, level: str = "A2.1", native: str = "de", interests: str = "",
              played: tuple[tuple[str, str], ...] = ()) -> User:
    """A learner whose last Papiers (newest first) were ``(mode, topic)``."""

    user = User(id=uuid.uuid4(), email=f"choix-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate=level, native_language=native, interests=interests)
    db.add(user)
    db.commit()
    now = datetime.now(UTC)
    for index, (mode, topic) in enumerate(played):
        payload = {"kind": "dossier", "dossier_id": "old", "snapshot": {"topic": topic},
                   **({"mode": mode} if mode != "chat" else {})}
        db.add(RevueSession(id=uuid.uuid4(), user_id=user.id, week=f"2026-W{20 - index}", dossier_id="old", plan={},
                            state={"events": [{"seq": 1, "at": now.isoformat(), "kind": "choice", "payload": payload}]},
                            status="closed", started_at=now - timedelta(days=index + 1),
                            closed_at=now - timedelta(days=index + 1)))
    db.commit()
    return user


def dossier_choice(row: RevueSession) -> dict:
    state = ConversationState.from_json(row.state)
    return next(e.payload for e in state.events if e.kind == "choice" and e.payload.get("kind") == "dossier")


# ---------------------------------------------------------------------------
# 1. The scope
# ---------------------------------------------------------------------------


def test_only_the_offered_assignments_are_dealt_and_the_default_is_the_cut(monkeypatch) -> None:
    default = type(settings).model_fields["REVUE_ASSIGNMENTS_OFFERED"].default
    assert default == "comptoir,titre", "the default itself is the cut"
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_OFFERED", default)
    assert assignments.offered_keys() == ["comptoir", "titre"]
    everything = assignments.Material(dossier=evergreens_for_week(WEEK)[0], takes=object(), wire=object(),
                                      titre=object(), intox=object(), micro=object())
    assert assignments.available(everything) == ["comptoir", "titre"]
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_OFFERED", " titre , micro, nonsense")
    assert assignments.available(everything) == ["titre", "micro"], "an unknown key is ignored"
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_OFFERED", ALL)
    assert assignments.available(everything) == ["comptoir", "fil", "titre", "intox", "micro"]
    assert "fil" in assignments.registered(), "parked code stays registered (a dealt session plays on)"


def test_the_morning_builds_only_the_offered_desks(monkeypatch) -> None:
    from app.services.revue import fil, intox, micro, photo, titre
    from app.tasks import revue as task

    calls: list[str] = []
    monkeypatch.setattr(task, "intake_now", lambda **_: {"status": "ok", "period": "2026-03-10"})
    monkeypatch.setattr(task, "leads_now", lambda **_: calls.append("leads") or {})
    monkeypatch.setattr(task, "comptoir_now", lambda **_: calls.append("comptoir") or {})
    monkeypatch.setattr(task, "_queue_painting", lambda period: {})
    for module, name in ((titre, "ensure_titre"), (intox, "ensure_intox"), (photo, "ensure_photo"),
                         (micro, "ensure_micro"), (fil, "ensure_fil")):
        monkeypatch.setattr(module, name, lambda db, period, name=name: calls.append(name) or [])
    report = task.weekly_intake()
    assert calls == ["leads", "comptoir", "ensure_titre"], "fil, intox, photo, micro cost nothing"
    assert "fil" not in report and report["rubriques"]["intox"] == {"status": "parked"}
    assert task.fil_now(period="2026-03-10") == {"status": "parked"}
    calls.clear()
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_OFFERED", "comptoir")
    report = task.weekly_intake()
    assert calls == ["leads", "comptoir"] and "rubriques" not in report
    calls.clear()
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_OFFERED", ALL)
    task.weekly_intake()
    assert calls == ["leads", "comptoir", "ensure_fil", "ensure_titre", "ensure_intox", "ensure_photo", "ensure_micro"]


def test_a_parked_assignment_is_never_dealt_at_start(db: Session, monkeypatch) -> None:
    from app.services.revue import micro

    monkeypatch.setattr(micro, "micro_of", lambda dossier: object())  # the story could carry an interview
    for _ in range(4):
        row = RevueEncounter(db, FakeRevueProvider()).start(make_user(db), week=WEEK, dossier_id=FETE)
        assert dossier_choice(row).get("mode") in ("comptoir", "titre")


# ---------------------------------------------------------------------------
# 2. Pedagogy chooses
# ---------------------------------------------------------------------------


def test_switch_off_the_ranking_and_the_payload_are_as_before(db: Session, monkeypatch) -> None:
    focus(monkeypatch, due=("lycéens",), rule=OPINION)
    user = make_user(db, interests="food")
    before, reason = RevueEncounter(db, FakeRevueProvider()).ranked(user, WEEK)
    assert [d.id for d in before][:1] != [BAC], "the due word does not move the old ranking"
    row = RevueEncounter(db, FakeRevueProvider()).start(user, week=WEEK)
    assert "why" not in dossier_choice(row)
    view = RevueEncounter(db, FakeRevueProvider()).view(row).model_dump(mode="json")
    assert "why" not in view
    offer = RevueEncounter(db, FakeRevueProvider()).week_offer(make_user(db), WEEK).model_dump(mode="json")
    assert "choices" not in offer and "why_language" not in offer
    assert all("why" not in card for card in [offer["recommended"], *offer["alternatives"]])


def test_due_words_put_their_story_first_and_say_so(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    focus(monkeypatch, due=("le lycéen", "la philosophie", "un mot absent"))
    revue = RevueEncounter(db, FakeRevueProvider())
    ordered, _ = revue.ranked(make_user(db), WEEK)
    assert ordered[0].id == BAC
    assert revue.why_for(BAC)["due_words"] == ["le lycéen", "la philosophie"]
    row = revue.start(make_user(db), week=WEEK)
    assert row.dossier_id == BAC and dossier_choice(row)["why"]["due_words"] == ["le lycéen", "la philosophie"]
    assert revue.view(row).why is not None and revue.view(row).why.due_words == ["le lycéen", "la philosophie"]


def test_the_rule_counts_in_the_story_french_at_the_band_and_the_recent_one_stands_in(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", False)
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False)
    focus(monkeypatch, rule=STRIKE, today=False)
    revue = RevueEncounter(db, FakeRevueProvider())
    ordered, _ = revue.ranked(make_user(db), WEEK)
    assert ordered[0].id == GREVE
    assert revue.why_for(GREVE)["rule"] == {"id": "FR2_TEST_STRIKE", "name": "Streik", "today": False}
    assert revue.why_for(FETE)["rule"] is None, "a story without the form gives no occasion"


def test_the_recent_rule_is_used_when_the_day_has_none(db: Session, monkeypatch) -> None:
    from app.services import day_rules

    monkeypatch.setattr(day_rules, "for_turn", lambda db, user, **_: {"today": None, "recent": [{"id": "x"}, OPINION]})
    assert choix._rule(db, None, "de", datetime.now(UTC)) == (OPINION, False)  # noqa: SLF001
    monkeypatch.setattr(day_rules, "for_turn", lambda db, user, **_: {"today": QUESTIONS, "recent": [OPINION]})
    assert choix._rule(db, None, "de", datetime.now(UTC)) == (QUESTIONS, True)  # noqa: SLF001
    monkeypatch.setattr(day_rules, "for_turn", lambda db, user, **_: None)
    assert choix._rule(db, None, "de", datetime.now(UTC)) == (None, False)  # noqa: SLF001


def test_interests_are_a_real_weight_not_a_tie_break(db: Session, monkeypatch) -> None:
    focus(monkeypatch)
    # The last Papier was about food: the old ranking sets food back, whatever the learner likes.
    user = make_user(db, interests="kochen", played=(("comptoir", "food"),))
    off, _ = RevueEncounter(db, FakeRevueProvider()).ranked(user, WEEK)
    assert off[0].id != MARCHE
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    revue = RevueEncounter(db, FakeRevueProvider())
    on, reason = revue.ranked(user, WEEK)
    assert on[0].id == MARCHE and reason == "interests"
    assert revue.why_for(MARCHE)["interest"] == {"topic": "food", "word": "kochen"}


def test_the_ranking_is_deterministic(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    focus(monkeypatch, due=("la musique",), rule=OPINION)
    user = make_user(db, interests="musique")
    first = [d.id for d in RevueEncounter(db, FakeRevueProvider()).ranked(user, WEEK)[0]]
    assert all([d.id for d in RevueEncounter(db, FakeRevueProvider()).ranked(user, WEEK)[0]] == first for _ in range(3))
    assert GREVE == first[-1], "a story no offered assignment carries comes last"


def test_the_deal_prefers_the_assignment_whose_material_exercises_the_rule() -> None:
    fete = next(d for d in evergreens_for_week(WEEK) if d.id == FETE)
    rule_focus = choix.Focus(band="a2", rule=OPINION)
    assert choix.prefer(["comptoir", "titre"], fete, rule_focus)[0] == "comptoir"
    assert choix.prefer(["comptoir", "titre", "micro"], fete, choix.Focus(band="a2", rule=QUESTIONS))[0] == "micro"
    assert choix.prefer(["comptoir", "titre"], fete, choix.Focus(band="a2")) == [], "no rule: the seed decides"
    both = ["comptoir", "titre"]
    seeded = {assignments.deal(both, [], seed=f"u{n}:d") for n in range(20)}
    assert seeded == {"comptoir", "titre"}
    assert {assignments.deal(both, [], seed=f"u{n}:d", prefer=["titre"]) for n in range(20)} == {"titre"}
    assert assignments.deal(both, ["titre"], seed="s", prefer=["titre"]) == "comptoir", "never the last shape again"
    assert assignments.deal(both, ["comptoir", "titre"], seed="s", prefer=["titre"]) == "titre"


def test_the_rule_steers_the_deal_at_start(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    for rule, mode in ((OPINION, "comptoir"), (NUMBERS, "titre")):
        focus(monkeypatch, rule=rule)
        for _ in range(3):
            row = RevueEncounter(db, FakeRevueProvider()).start(make_user(db), week=WEEK, dossier_id=FETE)
            assert dossier_choice(row).get("mode") == mode, rule["id"]


def test_focus_reads_the_app_and_never_raises(db: Session) -> None:
    got = choix.focus_for(db, make_user(db, level="B1.1", interests="Sport, Kunst"))
    assert got.band == "b1" and got.due == () and got.rule is None and got.interests == ("sport", "kunst")
    assert got.language == "de"


# ---------------------------------------------------------------------------
# 3. The learner chooses
# ---------------------------------------------------------------------------


def test_the_front_page_mixes_rubrics_and_topics() -> None:
    rows = [("a", "comptoir", "culture"), ("b", "comptoir", "culture"), ("c", "comptoir", "food"),
            ("d", "titre", "culture"), ("e", "titre", "sport")]
    picked = choix.front_page(rows, rubric=lambda r: r[1], topic=lambda r: r[2])
    assert [r[0] for r in picked] == ["a", "e", "c"]
    assert [r[0] for r in choix.front_page(rows[:2], rubric=lambda r: r[1], topic=lambda r: r[2])] == ["a", "b"]


def test_the_offer_carries_up_to_three_choices_with_their_why(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", True)
    focus(monkeypatch, due=("le lycéen",), rule=OPINION)
    offer = RevueEncounter(db, FakeRevueProvider()).week_offer(make_user(db, native="de"), WEEK)
    dumped = offer.model_dump(mode="json")
    assert dumped["why_language"] == "de"
    choices = dumped["choices"]
    assert 1 <= len(choices) <= 3 and choices[0]["dossier_id"] == BAC
    assert choices[0]["why"]["due_words"] == ["le lycéen"]
    assert len({c["dossier_id"] for c in choices}) == len(choices)
    assert all(c.get("assignment") for c in choices), "each names its rubric"


def test_the_learner_starts_the_story_they_chose(db: Session, monkeypatch, revue_tables) -> None:
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", True)
    focus(monkeypatch, due=("le lycéen",), rule=OPINION)
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_revue_provider] = lambda: FakeRevueProvider()
    with TestClient(app) as api:
        email = f"choix-{uuid.uuid4().hex[:10]}@example.com"
        api.post("/api/v1/auth/register", json={"email": email, "password": "securepass123", "target_language": "fr",
                                                "native_language": "en"})
        token = api.post("/api/v1/auth/login", json={"email": email, "password": "securepass123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        offer = api.get(f"/api/v1/revue/week?week={WEEK}", headers=headers).json()
        choices = offer["choices"]
        assert len(choices) >= 2 and offer["why_language"] == "en"
        chosen = choices[1]
        session = api.post("/api/v1/revue/sessions", headers=headers,
                           json={"week": WEEK, "dossier_id": chosen["dossier_id"]}).json()
        assert session["dossier"]["id"] == chosen["dossier_id"]
        assert session["plan"]["chosen_by"] == "learner"
        assert session["mode"] == chosen["assignment"]["key"], "the rubric shown is the one played"
        assert session.get("why") == chosen.get("why")


# ---------------------------------------------------------------------------
# Integration 2026-11-22 (the real stack): honest whys, mixed desks, the server's day
# ---------------------------------------------------------------------------


def test_a_fresh_learner_gets_no_empty_why_and_the_page_says_nothing(db: Session, monkeypatch) -> None:
    """Found on the real stack: the why record of a fresh learner is empty (no due card, no
    rule yet, no interest) — nothing was lost between the ranking and the payload. A card then
    carries no ``why`` at all, so the page says nothing rather than an empty promise."""

    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", True)
    focus(monkeypatch)
    choices = RevueEncounter(db, FakeRevueProvider()).week_offer(make_user(db), WEEK).model_dump(mode="json")["choices"]
    assert choices and all("why" not in card for card in choices)
    focus(monkeypatch, due=("le lycéen",))
    choices = RevueEncounter(db, FakeRevueProvider()).week_offer(make_user(db), WEEK).model_dump(mode="json")["choices"]
    assert choices[0]["why"]["due_words"] == ["le lycéen"], "a real reason survives to the payload"


def test_the_front_page_mixes_desks_when_a_story_carries_le_titre(db: Session, monkeypatch) -> None:
    """On the real stack all three were «Au comptoir»: each story is dealt on its own, and the
    counter came up three times. A story that carries «Le titre» is shown in it then."""

    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", True)
    focus(monkeypatch)
    # every story dealt the counter when it has takes (the real stack's draw)
    dealt = assignments.deal
    monkeypatch.setattr(assignments, "deal", lambda offered, recent, **kw: "comptoir" if "comptoir" in offered
                        else dealt(offered, recent, **kw))
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    choices = revue.week_offer(user, WEEK).model_dump(mode="json")["choices"]
    carry_titre = [d.id for d in evergreens_for_week(WEEK)
                   if "titre" in assignments.available(revue._material(d, d.comptoir))]
    assert carry_titre, "the evergreens carry «Le titre» material"
    rubrics = [card["assignment"]["key"] for card in choices]
    assert len(set(rubrics)) >= 2, rubrics
    assert len({card["dossier_id"] for card in choices}) == len(choices)


def test_the_story_starts_in_the_rubric_the_front_page_showed(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", True)
    focus(monkeypatch)
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    choices = revue.week_offer(user, WEEK).model_dump(mode="json")["choices"]
    chosen = next(card for card in choices if card["assignment"]["key"] == "titre")
    row = revue.start(user, week=WEEK, dossier_id=chosen["dossier_id"], assignment="titre")
    assert dossier_choice(row)["mode"] == "titre"
    with pytest.raises(enc.RevueError):
        RevueEncounter(db, FakeRevueProvider()).start(make_user(db), week=WEEK, dossier_id=chosen["dossier_id"],
                                                       assignment="photo")


def test_the_front_page_carries_the_servers_day_for_its_edition(db: Session, monkeypatch) -> None:
    from app.services.revue.weekly import PARIS

    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", True)
    focus(monkeypatch)
    offer = RevueEncounter(db, FakeRevueProvider()).week_offer(make_user(db), enc.current_period())
    assert offer.model_dump(mode="json")["edition_date"] == datetime.now(UTC).astimezone(PARIS).date().isoformat()
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", False)
    assert "edition_date" not in RevueEncounter(db, FakeRevueProvider()).week_offer(make_user(db), WEEK).model_dump(mode="json")


# ---------------------------------------------------------------------------
# 4. True reasons (real-data run 2026-11-22: 5 of 17 front-page reasons were false)
# ---------------------------------------------------------------------------


def test_a_card_promises_only_the_words_of_the_rubric_it_deals(db: Session, monkeypatch) -> None:
    """D1: Anna's produce card dealt «Le titre» promised 3 of her words, but «caisse» and
    «panier» were only in the counter's takes. The reason is scored over the card's own rubric."""

    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_CHOICE_ENABLED", True)
    fete = next(d for d in evergreens_for_week(WEEK) if d.id == FETE)
    assert not enc.appears_in(choix.story_french(fete, "a2", keys=["titre"]), "le silence"), "only in the takes"
    assert enc.appears_in(choix.story_french(fete, "a2", keys=["comptoir"]), "le silence")
    focus(monkeypatch, due=("le silence",))
    revue = RevueEncounter(db, FakeRevueProvider())
    revue.ranked(make_user(db), WEEK)
    assert revue.why_for(FETE, key="titre")["due_words"] == []
    assert revue.why_for(FETE, key="comptoir")["due_words"] == ["le silence"]
    dealt = assignments.deal
    for forced in ("titre", "comptoir"):
        monkeypatch.setattr(assignments, "deal", lambda offered, recent, _k=forced, **kw:
                            _k if _k in offered else dealt(offered, recent, **kw))
        choices = RevueEncounter(db, FakeRevueProvider()).week_offer(make_user(db), WEEK).model_dump(mode="json")["choices"]
        assert any(card["dossier_id"] == FETE for card in choices)
        for card in choices:
            dossier = next(d for d in evergreens_for_week(WEEK) if d.id == card["dossier_id"])
            text = choix.story_french(dossier, "a2", keys=[card["assignment"]["key"]])
            for word in (card.get("why") or {}).get("due_words") or []:
                assert enc.appears_in(text, word), (card["dossier_id"], card["assignment"]["key"], word)


def test_the_session_keeps_the_reason_of_the_rubric_it_plays(db: Session, monkeypatch) -> None:
    """D1: the reason kept on the dossier choice is the dealt rubric's, not the story's sum."""

    monkeypatch.setattr(settings, "REVUE_PEDAGOGY_PICK_ENABLED", True)
    focus(monkeypatch, due=("le silence",))
    row = RevueEncounter(db, FakeRevueProvider()).start(make_user(db), week=WEEK, dossier_id=FETE, assignment="titre")
    assert dossier_choice(row)["mode"] == "titre"
    assert dossier_choice(row)["why"]["due_words"] == []


def test_the_story_is_scored_on_the_lead_the_learner_reads() -> None:
    """D6: a story without an A2 lead scored its summary, while the A2 learner reads its A1 lead."""

    from app.services.revue.dossier import StoryLead, StoryLeads

    bac = next(d for d in evergreens_for_week(WEEK) if d.id == BAC)
    only_a1 = bac.model_copy(update={"leads": StoryLeads(a1=StoryLead(fr="Le lycéen mange une pomme."))})
    assert only_a1.lead_for("A2").fr == "Le lycéen mange une pomme."
    text = choix.story_french(only_a1, "a2")
    assert "pomme" in text and bac.summary_fr not in text
    assert bac.summary_fr in choix.story_french(only_a1, "b1"), "B1 reads the summary"
