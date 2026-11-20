"""«Le fil» (WP-119 «les rubriques», owner 2026-11-20): the wire desk (``fil.py``).

Four events in true order, each grounded in a claim, at each band's length, with the
comptoir's checks; the order justified by dates or by the claims' own words, else the wire is
refused; the sequence words authored; one retry; a sensitive story never gets a wire; the
morning writes each row once while the switch is on; the shipped evergreen wire passes.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Generator

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.revue_session import RevueDossier
from app.services.revue import fil
from app.services.revue.dossier import EditorialDossier
from app.services.revue.evergreen import evergreen_wire, load_evergreens

WEEK = "2026-W10"
CLAIMS = [
    "Le 3 mars, la mairie du 12e arrondissement annonce des travaux au marché Beauvau.",
    "Le 10 mars, les commerçants quittent le marché couvert et s'installent sur la place d'Aligre.",
    "Après le départ des commerçants, les ouvriers changent le toit du marché.",
    "Une fois les travaux finis, le marché Beauvau rouvre le 14 novembre.",
]


def beauvau(**update: object) -> EditorialDossier:
    """The prompt example's story (the market Beauvau reopens), on an evergreen's sources."""

    base = next(d for d in load_evergreens() if d.id == "evergreen-marche-du-dimanche").model_dump(mode="json")
    base.update({
        "id": "2026-03-10-le-marche-beauvau-ferme-pour-travaux",
        "week": WEEK,
        "title_fr": "Le marché Beauvau ferme pour travaux",
        "summary_fr": "Le marché couvert Beauvau ferme pour des travaux. Les commerçants s'installent sur la place "
                      "d'Aligre. Le marché rouvre le 14 novembre.",
        "evergreen": False,
        "comptoir": None,
        "leads": None,
        "time_scope": {"happening": "2026-03-03/2026-11-14", "relevant_until": "2026-11-30"},
    })
    claim = base["claims"][0]
    base["claims"] = [{**claim, "id": f"c{i}", "fr": text, "kind": "fact", "attributed_to": None}
                      for i, text in enumerate(CLAIMS, start=1)]
    base.update(update)
    return EditorialDossier.model_validate(base)


def gold() -> dict:
    """The full answer the prompt shows the desk."""

    text = fil.FIL_RULES.split("rouvre le 14 novembre.»):\n", 1)[1].rsplit("\nDo not reuse", 1)[0]
    return json.loads(text)


class _Desk:
    def __init__(self, answers: list) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []
        self.model = "fake-desk"

    def ask_json(self, instructions: str, payload: dict, **_: object) -> dict:
        self.calls.append(payload)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def test_the_prompts_own_example_passes_every_check() -> None:
    wire, problems = fil.repair_fil(gold(), beauvau())
    assert problems == [] and wire is not None
    assert [s.claim_id for s in wire.strips] == ["c1", "c2", "c3", "c4"]
    assert wire.strips[0].label.fr == "l'annonce" and wire.strips[0].tile.fr == "la mairie annonce des travaux"
    assert [c.fr for c in wire.connectors["a1"]] == ["d'abord", "ensuite", "puis", "enfin"]
    assert {c.role for c in wire.connectors["b1"]} == {"first", "middle", "last"}
    assert all(c.en and c.de for band in wire.connectors.values() for c in band), "every word has its gloss"
    assert fil.audit(wire, beauvau()) == []


def test_a_strip_not_grounded_in_its_claim_refuses_the_wire() -> None:
    raw = gold()
    raw["strips"][2]["claim_id"] = "c9"
    assert fil.repair_fil(raw, beauvau()) == (None, ["fil:3:claim_unknown"])
    raw = gold()
    raw["strips"][2]["a1"]["fr"] = "Les touristes dansent dans la rue."
    wire, problems = fil.repair_fil(raw, beauvau())
    assert wire is None and "fil:3:a1:ungrounded" in problems


def test_a_number_or_a_name_the_claims_do_not_carry_refuses_the_wire() -> None:
    raw = gold()
    raw["strips"][3]["a2"]["fr"] = "Le marché Beauvau rouvre le 15 novembre."
    wire, problems = fil.repair_fil(raw, beauvau())
    assert wire is None and "fil:4:a2:number_not_in_claims" in problems
    raw = gold()
    raw["strips"][0]["b1"]["fr"] = "Le 3 mars, la maire Anne Hidalgo annonce des travaux au marché Beauvau."
    wire, problems = fil.repair_fil(raw, beauvau())
    assert wire is None and "fil:1:b1:name_not_in_claims" in problems


def test_each_bands_word_limit_holds() -> None:
    for band, words in (("a1", 10), ("a2", 15), ("b1", 23)):
        raw = gold()
        raw["strips"][1][band]["fr"] = "Les commerçants quittent le marché " + " ".join(["couvert"] * (words - 5)) + "."
        wire, problems = fil.repair_fil(raw, beauvau())
        assert wire is None and f"fil:2:{band}:too_long" in problems, band


def test_a_relative_date_an_app_word_or_a_missing_translation_refuses_the_wire() -> None:
    for text, why in (("Demain, les commerçants quittent le marché.", "relative_date"),
                      ("Les commerçants quittent le marché de la session.", "app_words")):
        raw = gold()
        raw["strips"][1]["a1"]["fr"] = text
        wire, problems = fil.repair_fil(raw, beauvau())
        assert wire is None and f"fil:2:a1:{why}" in problems, text
    raw = gold()
    raw["strips"][1]["a1"]["de"] = ""
    assert "fil:2:a1:translation_missing" in fil.repair_fil(raw, beauvau())[1]


def test_a_strip_never_carries_a_sequence_word() -> None:
    raw = gold()
    raw["strips"][2]["a2"]["fr"] = "Ensuite, les ouvriers changent le toit du marché."
    wire, problems = fil.repair_fil(raw, beauvau())
    assert wire is None and "fil:3:a2:sequence_word" in problems


def test_an_order_the_claims_do_not_justify_refuses_the_wire() -> None:
    # two events with no stated sequence: c3 loses its «Après…», and the basis is a guess
    dossier = beauvau(claims=[*beauvau().model_dump(mode="json")["claims"][:2],
                              {**beauvau().model_dump(mode="json")["claims"][2],
                               "fr": "Les ouvriers changent le toit du marché."},
                              beauvau().model_dump(mode="json")["claims"][3]])
    raw = gold()
    raw["basis"][1] = "Les ouvriers changent le toit"
    assert fil.repair_fil(raw, dossier) == (None, ["order:unjustified:2"])
    raw["basis"][1] = "date"
    assert fil.repair_fil(raw, dossier)[1] == ["order:unjustified:2"]


def test_dates_that_disagree_refuse_whatever_the_words_say() -> None:
    raw = gold()
    raw["strips"][0], raw["strips"][1] = raw["strips"][1], raw["strips"][0]
    raw["basis"][0] = "Après le départ des commerçants"
    assert fil.repair_fil(raw, beauvau())[1] == ["order:dates_disagree:1"]


def test_dates_compare_only_when_they_can() -> None:
    assert fil.when("Le 3 mars, la mairie…") == (None, 3, 3)
    assert fil.when("En 1809, les premiers candidats…") == (1809, None, None)
    assert fil.when("le 1er septembre 2026") == (2026, 9, 1)
    assert fil.date_order((None, 3, 3), (None, 3, 10)) == -1
    assert fil.date_order((1808, None, None), (1809, None, None)) == -1
    assert fil.date_order((1982, None, None), (None, 6, 21)) is None, "a year against a month: no order"
    assert fil.date_order((None, 3, None), (None, 3, 10)) is None


def test_small_pieces_fall_back_and_a_skip_is_a_skip() -> None:
    raw = gold()
    raw["frames"] = [{"fr": "La mairie", "en": "The town hall", "de": "Das Rathaus"}]
    raw["phrase"]["b2"] = {"fr": ""}
    raw["strips"][0]["label"] = {"fr": "l'annonce de la mairie du quartier"}
    raw["strips"][0]["tile"] = {"fr": "ensuite la mairie annonce", "en": "x", "de": "y"}
    wire, problems = fil.repair_fil(raw, beauvau())
    assert wire is not None
    assert [f.fr for f in wire.telling.frames] == ["D'abord,", "Ensuite,"]
    assert wire.telling.phrase.b2.fr == fil.AUTHORED_PHRASE.b2.fr
    assert wire.strips[0].label is None and wire.strips[0].tile.fr == "la mairie annonce des travaux au marché Beauvau"
    assert {"fil:frames:authored", "fil:phrase:b2:empty", "fil:1:tile:sequence_word"} <= set(problems)
    assert fil.repair_fil({"fit": "skip"}, beauvau()) == (None, ["skip"])


def test_the_desk_retries_once_with_the_problems_then_refuses() -> None:
    bad = gold()
    bad["strips"][3]["a1"]["fr"] = "Le marché rouvre le 15 novembre."
    desk = _Desk([bad, gold()])
    wire, problems = fil.write_fil(beauvau(), desk)
    assert wire is not None and problems == [] and wire.prompt_version == fil.FIL_PROMPT_VERSION
    assert desk.calls[1]["retry_feedback"]["problems"] == ["fil:4:a1:number_not_in_claims"]
    desk = _Desk([bad, bad])
    assert fil.write_fil(beauvau(), desk) == (None, ["fil:4:a1:number_not_in_claims"])
    assert fil.write_fil(beauvau(), _Desk([RuntimeError("down")])) == (None, ["fil:desk_failed"])


def test_the_shipped_evergreen_wire_passes_every_check() -> None:
    bac = next(d for d in load_evergreens() if d.id == "evergreen-bac")
    wire = evergreen_wire("evergreen-bac")
    assert wire is not None and fil.audit(wire, bac) == []
    assert "fil" not in bac.model_dump(mode="json"), "never attached to the loaded evergreen"
    assert evergreen_wire("evergreen-toussaint") is None, "a custom, not a sequence: no wire"


# ---------------------------------------------------------------------------
# The morning
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def revue_tables(db_engine) -> Generator[None, None, None]:
    created = not inspect(db_engine).has_table(RevueDossier.__table__.name)
    if created:
        RevueDossier.__table__.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        if created:
            RevueDossier.__table__.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Session:
    return db_session


def _row(db: Session, dossier: EditorialDossier, period: str, **checks: str) -> RevueDossier:
    row = RevueDossier(id=f"{period}-{dossier.id}"[:120], week=WEEK, period=period, topic=dossier.topic,
                       payload=dossier.model_dump(mode="json"), source_hashes={}, checks=dict(checks),
                       builder_version="revue-builder-v3")
    db.add(row)
    db.commit()
    return row


def test_each_morning_writes_the_wire_once_per_row_and_skips_what_the_comptoir_skipped(db: Session) -> None:
    period = "2026-03-10"
    story = beauvau()
    sensitive = beauvau(id="2026-03-10-un-drame")
    _row(db, story, period)
    _row(db, sensitive, period, comptoir="skip")
    desk = _Desk([gold()])
    assert fil.ensure_fil(db, period, provider=desk) == [story.id]
    assert len(desk.calls) == 1, "the sensitive story is never asked"
    rows = {r.payload["id"]: r for r in db.scalars(select(RevueDossier).where(RevueDossier.period == period))}
    assert rows[story.id].payload["fil"]["strips"][0]["claim_id"] == "c1"
    assert rows[sensitive.id].checks["fil"] == "skip" and "fil" not in rows[sensitive.id].payload
    assert fil.ensure_fil(db, period, provider=_Desk([])) == [], "once per row"


def test_the_morning_task_runs_the_desk_only_while_the_switch_is_on(monkeypatch) -> None:
    from app.tasks import revue as task

    calls: list[str] = []
    monkeypatch.setattr(task, "intake_now", lambda **_: {"status": "ok", "period": "2026-03-10"})
    monkeypatch.setattr(task, "leads_now", lambda **_: calls.append("leads") or {})
    monkeypatch.setattr(task, "comptoir_now", lambda **_: calls.append("comptoir") or {})
    monkeypatch.setattr(task, "fil_now", lambda **_: calls.append("fil") or {})
    monkeypatch.setattr(task, "_queue_painting", lambda period: {})
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False)
    assert "fil" not in task.weekly_intake() and calls == ["leads", "comptoir"]
    calls.clear()
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", True)
    assert "fil" in task.weekly_intake() and calls == ["leads", "comptoir", "fil"], "after the takes"
