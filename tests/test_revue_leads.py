"""«La une en trois phrases» (owner, 2026-10-18: «it's not clear what happened»).

The leads (``app/services/revue/leads.py``): the check that keeps a band's lead short, dated
absolutely and true to the claims' numbers; the builder and the morning's lead desk that
write them; and what the learner meets: the story told at their band before Romy speaks,
Romy asking for help without reading out her brief, a dateline instead of a date range,
and Romy telling the story again, never «les sources ne le disent pas», when the learner
says they are lost, or bringing the next fact on «Plus».
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.models.npc import NPC, NPCMemory
from app.db.models.revue_session import RevueDossier, RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.story import Story
from app.db.models.user import User
from app.services.revue import encounter as enc
from app.services.revue import leads as leads_module
from app.services.revue.builder import (
    FakeDossierProvider,
    SourceItem,
    StoryInput,
    build_dossier,
    provider_context,
)
from app.services.revue.dossier import EditorialDossier, StoryLead, StoryLeads
from app.services.revue.encounter import (
    LOST_LEAD,
    MORE_LEAD,
    PURPOSE_LINES,
    FakeRevueProvider,
    RevueEncounter,
)
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.leads import ensure_leads, kiosk_periods, repair_leads

WEEK = "2026-W40"
MARCHE = "evergreen-marche-du-dimanche"
A1_LEAD = "Paris a 91 marchés. Le marché d'Aligre ouvre six matins sur sept. Il y a un marché couvert."
A2_LEAD = ("Paris compte 91 marchés. Le marché d'Aligre, dans le 12e arrondissement, ouvre six matins sur sept. "
           "On y trouve un marché couvert et un marché en plein air.")
GOOD = {
    "headline_fr": "Aligre, six matins sur sept",
    "a1": {"fr": A1_LEAD, "en": "Paris has 91 markets.", "de": "Paris hat 91 Märkte."},
    "a2": {"fr": A2_LEAD, "en": "Paris counts 91 markets.", "de": "Paris zählt 91 Märkte."},
}
REVUE_TABLES = (
    Story.__table__,
    NPC.__table__,
    NPCMemory.__table__,
    RevueSession.__table__,
    RevueDossier.__table__,
    RevuePictogram.__table__,
    RevueVignette.__table__,
)


def marche(**update) -> EditorialDossier:
    dossier = next(d for d in evergreens_for_week(WEEK) if d.id == MARCHE)
    return dossier.model_copy(update=update)


def with_leads() -> EditorialDossier:
    leads, repairs = repair_leads(GOOD, marche())
    assert leads is not None and not repairs, repairs
    return marche(leads=leads)


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def test_good_leads_are_kept_with_their_translations() -> None:
    leads, repairs = repair_leads(GOOD, marche())
    assert repairs == []
    assert leads.headline_fr == "Aligre, six matins sur sept"
    assert leads.a1.fr == A1_LEAD and leads.a1.translation("de") == "Paris hat 91 Märkte."
    assert leads.a2.translation("en") == "Paris counts 91 markets."
    assert leads.a1.translation("fr") is None


@pytest.mark.parametrize(
    ("band", "fr", "reason"),
    [
        ("a1", " ".join(["Le marché ouvre le matin."] * 8), "too_long"),
        ("a1", "Le marché d'Aligre ouvre demain matin.", "relative_date"),
        ("a1", "Le marché d'Aligre ouvre jeudi.", "relative_date"),
        ("a1", "Paris a 120 marchés.", "number_not_in_claims"),
        ("a2", "Le marché c2 ouvre six matins sur sept.", "id_leak"),
        ("a2", "", "empty"),
    ],
)
def test_a_band_whose_lead_fails_is_dropped_and_the_other_kept(band: str, fr: str, reason: str) -> None:
    raw = {**GOOD, band: {"fr": fr, "en": "x", "de": "y"}}
    leads, repairs = repair_leads(raw, marche())
    assert f"leads:{band}:{reason}" in repairs
    assert getattr(leads, band) is None
    other = "a2" if band == "a1" else "a1"
    assert getattr(leads, other) is not None


def test_a_weekday_the_story_names_is_kept() -> None:
    raw = {**GOOD, "a1": {"fr": "Paris a 91 marchés. Le dimanche, on va au marché d'Aligre."}}
    leads, repairs = repair_leads(raw, marche())
    assert repairs == [] and "dimanche" in leads.a1.fr


def test_a_long_headline_is_dropped_and_nothing_valid_is_no_leads() -> None:
    leads, repairs = repair_leads({**GOOD, "headline_fr": "Le grand marché couvert d'Aligre ouvre six matins"}, marche())
    assert leads.headline_fr is None and "leads:headline:too_long" in repairs
    assert repair_leads({"a1": {"fr": "Il y a 7 marchés."}}, marche())[0] is None
    assert repair_leads("leads", marche()) == (None, ["leads:missing"])


def test_each_band_reads_its_lead_and_falls_back_to_the_summary() -> None:
    dossier = with_leads()
    assert dossier.lead_for("A1").fr == A1_LEAD
    assert dossier.lead_for("A2").fr == A2_LEAD
    assert dossier.lead_for("B1").fr == dossier.summary_fr
    assert dossier.simpler_lead("B1").fr == A2_LEAD and dossier.simpler_lead("A2").fr == A1_LEAD
    only_a2 = marche(leads=StoryLeads(a2=StoryLead(fr=A2_LEAD)))
    assert only_a2.lead_for("A1").fr == A2_LEAD
    assert marche().lead_for("A1").fr == marche().summary_fr


# ---------------------------------------------------------------------------
# The builder and the lead desk
# ---------------------------------------------------------------------------


def _story(text: str) -> StoryInput:
    item = SourceItem(
        source_id="s1",
        name="France Info",
        url="https://example.org/a",
        title="Les tomates bio coûtent 4 euros à Lyon",
        summary="",
        published_at=date(2026, 9, 30),
        article_text=text,
    )
    return StoryInput(key="k", week=WEEK, period=WEEK, topic="food", items=(item,), today=date(2026, 10, 1))


ARTICLE = (
    "Au marché de la Croix-Rousse à Lyon, le kilo de tomates bio coûte désormais 4 euros selon les maraîchers. "
    "Les producteurs expliquent que la saison a été courte et que la récolte est plus faible que prévu. "
    "Plusieurs clients disent qu'ils achètent moins de légumes frais à cause des prix plus élevés au marché."
)


def test_the_builder_keeps_the_leads_it_was_given_and_drops_a_number_no_claim_carries() -> None:
    result = build_dossier(_story(ARTICLE), FakeDossierProvider(), geocode=lambda d: d)
    assert result.ok, result.rejected
    leads = result.dossier.leads
    assert leads is not None and leads.a1 is not None and leads.headline_fr

    raw = FakeDossierProvider().build_dossier(provider_context(_story(ARTICLE)))
    raw["leads"] = {"headline_fr": "Les tomates à 9 euros", "a1": {"fr": "Le kilo de tomates coûte 4 euros."}}
    result = build_dossier(_story(ARTICLE), FakeDossierProvider(script={"s1": raw}), geocode=lambda d: d)
    assert result.ok
    assert result.dossier.leads.headline_fr is None, "9 is in no claim"
    assert "leads:headline:number_not_in_claims" in result.check_summary["repairs"]
    assert result.dossier.leads.a1.fr == "Le kilo de tomates coûte 4 euros."


class _Desk:
    def __init__(self, answers: list) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []

    def ask_json(self, instructions: str, payload: dict, **_: object) -> dict:
        self.calls.append(payload)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


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


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def _row(db: Session, dossier: EditorialDossier, period: str) -> RevueDossier:
    row = RevueDossier(id=f"{period}-{dossier.id}", week=WEEK, period=period, topic=dossier.topic,
                       payload=dossier.model_dump(mode="json"), source_hashes={}, checks={},
                       builder_version="revue-builder-v3")
    db.add(row)
    db.commit()
    return row


def test_the_lead_desk_writes_the_kiosks_missing_leads_once(db: Session) -> None:
    today, yesterday, last_week = "2026-10-18", "2026-10-17", "2026-10-10"
    assert kiosk_periods(today)[:2] == [today, yesterday] and last_week not in kiosk_periods(today)
    assert kiosk_periods("2026-W42") == ["2026-W42"]
    fresh = _row(db, marche(id="a"), today)
    refused = _row(db, marche(id="b"), yesterday)
    done = _row(db, with_leads().model_copy(update={"id": "c"}), today)
    old = _row(db, marche(id="d"), last_week)

    desk = _Desk([{"leads": GOOD}, {"leads": {"a1": {"fr": "Il y a 7 marchés."}}}])
    written = ensure_leads(db, today, provider=desk)
    assert written == ["a"]
    assert len(desk.calls) == 2, "the dossier with leads and last week's are not asked"
    assert "claims" in desk.calls[0] and "quote" not in desk.calls[0]["claims"][0], "the desk reads our French only"
    db.refresh(fresh), db.refresh(refused), db.refresh(done), db.refresh(old)
    assert EditorialDossier.model_validate(fresh.payload).lead_for("A1").fr == A1_LEAD
    assert refused.payload.get("leads") is None and refused.checks["leads"]
    assert old.payload.get("leads") is None

    assert ensure_leads(db, today, provider=_Desk([])) == [], "a refused row is not asked again"


def test_a_failing_desk_leaves_the_summary() -> None:
    leads, repairs = leads_module.write_leads(marche(), _Desk([RuntimeError("down")]))
    assert leads is None and repairs == ["leads:desk_failed"]


def test_each_morning_writes_the_leads_before_the_painting(monkeypatch) -> None:
    from app.config import settings
    from app.tasks import revue as task

    real_leads_now = task.leads_now
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    order: list[str] = []
    monkeypatch.setattr(task, "intake_now", lambda refresh=False: {"status": "kept", "period": "2026-10-18"})
    monkeypatch.setattr(task, "leads_now", lambda period=None, now=None: order.append(f"leads:{period}") or {"status": "ok"})
    monkeypatch.setattr(task, "_queue_painting", lambda period: order.append(f"paint:{period}") or {"status": "enqueued"})
    report = task.weekly_intake()
    assert order == ["leads:2026-10-18", "paint:2026-10-18"]
    assert report["leads"] == {"status": "ok"}
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert real_leads_now() == {"status": "disabled"}


# ---------------------------------------------------------------------------
# What the learner meets
# ---------------------------------------------------------------------------


def make_user(db: Session, *, level: str, native: str = "de") -> User:
    user = User(id=uuid.uuid4(), email=f"lead-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate=level, native_language=native, interests="")
    db.add(user)
    db.commit()
    return user


def _kiosk(monkeypatch, dossier: EditorialDossier) -> None:
    monkeypatch.setattr(enc, "available_dossiers", lambda week, db=None: [dossier])


def test_the_story_is_told_before_romy_speaks_at_the_learners_band(db: Session, monkeypatch) -> None:
    news = with_leads().model_copy(update={"evergreen": False})
    news = EditorialDossier.model_validate({**news.model_dump(mode="json"),
                                            "time_scope": {"happening": "2026-09-28/2026-10-02",
                                                           "relevant_until": "2026-10-20"}})
    _kiosk(monkeypatch, news)
    revue = RevueEncounter(db, FakeRevueProvider())
    view = revue.view(revue.start(make_user(db, level="A1.1"), WEEK, dossier_id=MARCHE))

    kinds = [(item.kind, getattr(item, "role", None)) for item in view.thread]
    assert kinds[:2] == [("narration", None), ("summary", None)]
    assert kinds[-1] == ("line", "purpose"), "Romy's question is the last line, under the story"
    narration = [item.text_fr for item in view.thread if item.kind == "narration"]
    assert narration == ["Le marché d'Aligre, un matin, le 23 septembre."]
    summary = next(item for item in view.thread if item.kind == "summary")
    assert summary.text_fr == A1_LEAD and summary.translation == "Paris hat 91 Märkte."
    purpose = next(item for item in view.thread if item.kind == "line" and item.role == "purpose")
    assert purpose.text_fr == PURPOSE_LINES["understand_change"]
    assert "«" not in purpose.text_fr and not any(a.fr in purpose.text_fr for a in news.angles), "no brief read out"
    assert purpose.translation and purpose.translation.startswith("Ich muss")


def test_b1_reads_the_summary_without_a_translation_and_an_evergreen_has_no_date(db: Session, monkeypatch) -> None:
    _kiosk(monkeypatch, with_leads())
    revue = RevueEncounter(db, FakeRevueProvider())
    view = revue.view(revue.start(make_user(db, level="B1.1"), WEEK, dossier_id=MARCHE))
    summary = next(item for item in view.thread if item.kind == "summary")
    assert summary.text_fr == with_leads().summary_fr and summary.translation is None
    assert view.thread[0].text_fr == "Le marché d'Aligre, un matin."
    card = enc.story_card(with_leads())
    assert card.headline_fr == "Aligre, six matins sur sept"
    assert enc.story_card(marche()).headline_fr is None


SILENT = {"reply_fr": "Les sources ne le disent pas.", "claims_cited": [], "uncertainty_cited": None,
          "proposes_question": None, "shift": None}


def test_a_lost_learner_hears_the_story_again_never_that_the_sources_are_silent(db: Session, monkeypatch) -> None:
    _kiosk(monkeypatch, with_leads())
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    fake.script = [dict(SILENT), dict(SILENT)]
    result = revue.turn(row, "Non. Je ne comprends pas. Où est Margaux ?")

    context = fake.calls[-1][1]
    assert context["learner_is_lost"] is True and context["story_lead"] == A1_LEAD, "one band simpler"
    assert context["retry_feedback"]["problems"] == ["silent_when_lost"]
    line = next(item for item in result.items if item.kind == "line")
    assert line.text_fr == f"{LOST_LEAD} {A1_LEAD}"
    assert "ne le disent pas" not in line.text_fr
    assert line.translation == "Ich fange noch mal von vorne an. Paris hat 91 Märkte."
    assert [item.kind for item in result.items].count("claims") == 0, "the story again, nothing new to sort"
    assert not [item for item in result.items if item.kind == "uncertainty"]


def test_a_reply_that_retells_the_story_is_kept(db: Session, monkeypatch) -> None:
    _kiosk(monkeypatch, with_leads())
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    result = revue.turn(row, "Je ne comprends pas.")
    line = next(item for item in result.items if item.kind == "line")
    assert line.text_fr.startswith("Pas de souci. On reprend doucement.") and A1_LEAD in line.text_fr
    assert len(fake.calls[-1][1].get("retry_feedback") or {}) == 0


def test_plus_brings_the_next_fact_even_when_the_model_has_none(db: Session, monkeypatch) -> None:
    _kiosk(monkeypatch, with_leads())
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    none_left = {"reply_fr": "Les sources ne donnent pas d'autres détails pour l'instant, hein.", "claims_cited": [],
                 "uncertainty_cited": None, "proposes_question": None, "shift": None}
    fake.script = [dict(none_left), dict(none_left)]
    result = revue.turn(row, "Dis-m'en plus.")
    assert fake.calls[-1][1]["learner_wants_more"] is True
    line = next(item for item in result.items if item.kind == "line")
    c3 = next(c for c in marche().claims if c.id == "c3")
    assert line.text_fr.startswith(MORE_LEAD) and c3.fr.rstrip(".") in line.text_fr, "the fact is said, not only shown"
    shown = [claim.id for item in result.items if item.kind == "claims" for claim in item.claims]
    assert shown == ["c3"], "the next fact the A2 lead has not told (c1, c2 are in it; c3 adds Beauvau)"
    db.expire_all()
    assert db.scalar(select(RevueSession).where(RevueSession.id == row.id)) is not None


def test_plus_never_counts_what_the_lead_already_told_as_new(db: Session, monkeypatch) -> None:
    beauvau = ("Paris compte 91 marchés. À Aligre, il y a un marché couvert, le marché Beauvau, ouvert toute la "
               "journée, et un marché en plein air, ouvert seulement le matin.")
    _kiosk(monkeypatch, marche(leads=StoryLeads(a2=StoryLead(fr=beauvau))))
    assert [c.id for c in marche().claims if enc.told_in(c.fr, beauvau)] == ["c1", "c3"]
    fake = FakeRevueProvider()
    revue = RevueEncounter(db, fake)
    row = revue.start(make_user(db, level="A2.1"), WEEK, dossier_id=MARCHE)
    revue.turn(row, "D'accord, je t'aide.")
    retold = {"reply_fr": "Il y a aussi le marché Beauvau, couvert, hein.", "claims_cited": ["c3"],
              "uncertainty_cited": None, "proposes_question": None, "shift": None}
    fake.script = [dict(retold), dict(retold)]
    result = revue.turn(row, "Plus")
    assert [(c["id"], c["in_story_lead"]) for c in fake.calls[-1][1]["claims"]] == [("c4", False), ("c3", True)]
    line = next(item for item in result.items if item.kind == "line")
    assert line.text_fr.startswith(MORE_LEAD), "what the lead told is not «something else»"
    assert [claim.id for item in result.items if item.kind == "claims" for claim in item.claims] == ["c4"]
