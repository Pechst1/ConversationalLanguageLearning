"""«Le Papier · les rubriques» (owner 2026-11-20): the desks of «Le titre» (``titre.py``) and
«L'intox express» (``intox.py``).

Each prompt's own example passes every check; a false statement whose wrong element is in a
claim, or whose true value is not in its claim, refuses the round; a true statement carries no
number its claim lacks; never a person's private life; three true and two false. An
exaggerated headline that the claims actually support is refused; the honest one carries no
number or name the claims lack; the stretch is the stated kind; never an outlet's words; the
tiles never say too much. Limits per band; one retry; a sensitive story never asked; the
morning writes each once while the switch is on; the shipped evergreens pass.
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
from app.services.revue import intox, titre
from app.services.revue.dossier import EditorialDossier
from app.services.revue.evergreen import evergreen_intox, evergreen_titre, load_evergreens

WEEK = "2026-W10"
FETE = "evergreen-fete-de-la-musique"
CLAIMS = [
    "Le 3 mars, la mairie du 12e arrondissement annonce des travaux au marché Beauvau.",
    "Le 10 mars, les commerçants quittent le marché couvert et s'installent sur la place d'Aligre.",
    "Après le départ des commerçants, les ouvriers changent le toit du marché.",
    "Une fois les travaux finis, le marché Beauvau rouvre le 14 novembre.",
]
#: The outlet's own words for each claim (verbatim quotes are never our French).
QUOTES = [
    "la mairie du 12e arrondissement a annoncé le 3 mars des travaux au marché Beauvau",
    "Le 10 mars, les commerçants quitteront le marché couvert pour s'installer place d'Aligre",
    "les ouvriers changeront le toit du marché après le départ des commerçants",
    "Une fois les travaux finis, le marché Beauvau rouvrira le 14 novembre",
]


def beauvau(**update: object) -> EditorialDossier:
    """The prompts' example story (the market Beauvau), on an evergreen's sources."""

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
    base["claims"] = [{**claim, "id": f"c{i}", "fr": text, "quote": quote, "kind": "fact", "attributed_to": None}
                      for i, (text, quote) in enumerate(zip(CLAIMS, QUOTES, strict=True), start=1)]
    base.update(update)
    return EditorialDossier.model_validate(base)


def gold_intox() -> dict:
    text = intox.INTOX_RULES.split("each with its quote):\n", 1)[1].rsplit("\nDo not reuse", 1)[0]
    return json.loads(text)


def gold_titre() -> dict:
    text = titre.TITRE_RULES.split("rouvre le 14 novembre.»):\n", 1)[1].rsplit("\nDo not reuse", 1)[0]
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


def _false(raw: dict, swap: str) -> dict:
    return next(s for s in raw["statements"] if s.get("swap") == swap)


# ---------------------------------------------------------------------------
# «L'intox express»
# ---------------------------------------------------------------------------


def test_the_intox_prompts_own_example_passes_every_check() -> None:
    express, problems = intox.repair_intox(gold_intox(), beauvau())
    assert problems == [] and express is not None
    assert [s.true for s in express.statements] == [True, False, True, False, True]
    day = next(s for s in express.statements if s.swap == "day")
    assert (day.wrong_fr, day.right_fr, day.distractor_fr) == ("le 20 mars", "le 10 mars", "le 3 mars")
    assert day.quote_fr == QUOTES[1] and day.settles_fr == "Le 10 mars" and day.source_name
    assert day.fixed.a1.fr == "Les commerçants partent le 10 mars."
    assert intox.audit(express, beauvau()) == []


def test_a_false_statement_whose_wrong_element_is_in_a_claim_is_refused() -> None:
    raw = gold_intox()
    day = _false(raw, "day")
    day["wrong_fr"] = "le 3 mars"  # c1 says it: not false
    for band in ("a1", "a2", "b1"):
        day[band]["fr"] = day[band]["fr"].replace("20 mars", "3 mars")
    assert intox.repair_intox(raw, beauvau()) == (None, ["intox:2:not_false"])
    raw = gold_intox()
    _false(raw, "who")["wrong_fr"] = "La Mairie"  # case-folded
    assert intox.repair_intox(raw, beauvau())[1] == ["intox:4:not_false"]


def test_the_true_value_must_be_in_its_claim_and_of_the_stated_kind() -> None:
    raw = gold_intox()
    _false(raw, "day")["right_fr"] = "le 11 mars"
    assert intox.repair_intox(raw, beauvau()) == (None, ["intox:2:right_not_in_claim"])
    raw = gold_intox()
    _false(raw, "who")["swap"] = "number"
    assert intox.repair_intox(raw, beauvau()) == (None, ["intox:4:swap_kind"])
    raw = gold_intox()
    _false(raw, "day")["distractor_fr"] = "la mairie"  # a who for a day
    assert intox.repair_intox(raw, beauvau()) == (None, ["intox:2:distractor"])
    raw = gold_intox()
    _false(raw, "day")["a1"]["fr"] = "Les commerçants partent le 10 mars."  # the true value, not the false one
    assert "intox:2:a1:wrong_not_in_statement" in intox.repair_intox(raw, beauvau())[1]
    raw = gold_intox()
    _false(raw, "day")["fixed"]["b1"]["fr"] = "Les commerçants quittent le marché couvert pour la place d'Aligre."
    assert "intox:2:fixed:b1:not_true" in intox.repair_intox(raw, beauvau())[1]


def test_numbers_are_compared_digit_for_digit_and_one_change_only() -> None:
    raw = gold_intox()
    raw["statements"][0]["a1"]["fr"] = "Le marché rouvre le 15 novembre."  # a true one with a new number
    assert intox.repair_intox(raw, beauvau())[1] == ["intox:1:a1:number_not_in_claims"]
    raw = gold_intox()
    raw["statements"][0]["a2"]["fr"] = "Après les travaux, le marché rouvre le 3 mars."  # c1's number, not c4's
    assert intox.repair_intox(raw, beauvau())[1] == ["intox:1:a2:number_not_in_claim"]
    raw = gold_intox()
    _false(raw, "day")["b1"]["fr"] = "Le 20 mars, les commerçants quittent le marché couvert du 12e."
    assert intox.repair_intox(raw, beauvau())[1] == ["intox:2:b1:two_changes"]


def test_limits_private_life_and_three_true_two_false() -> None:
    raw = gold_intox()
    raw["statements"][0]["a1"]["fr"] = "Une fois les travaux finis, le marché rouvre le 14 novembre."
    assert intox.repair_intox(raw, beauvau())[1] == ["intox:1:a1:too_long"]
    raw = gold_intox()
    raw["statements"][2]["b1"]["fr"] = "Les ouvriers changent le toit du marché et parlent de leur divorce."
    assert intox.repair_intox(raw, beauvau())[1] == ["intox:3:b1:private_life"]
    raw = gold_intox()
    raw["statements"][4]["a1"]["en"] = ""
    assert intox.repair_intox(raw, beauvau())[1] == ["intox:5:a1:translation_missing"]
    raw = gold_intox()
    raw["statements"][0]["a1"]["fr"] = "Demain, le marché rouvre le 14 novembre."
    assert intox.repair_intox(raw, beauvau())[1] == ["intox:1:a1:relative_date"]
    raw = gold_intox()
    raw["statements"] = raw["statements"][:4]
    assert intox.repair_intox(raw, beauvau()) == (None, ["intox:statements:count"])
    raw = gold_intox()
    raw["statements"][1] = copy.deepcopy(raw["statements"][0])
    raw["statements"][1]["a1"]["fr"] = "Le marché Beauvau rouvre le 14 novembre."
    raw["statements"][1]["a2"]["fr"] = "Le marché Beauvau rouvre ses portes le 14 novembre."
    raw["statements"][1]["b1"]["fr"] = "Après les travaux, le marché Beauvau rouvre ses portes le 14 novembre."
    assert intox.repair_intox(raw, beauvau()) == (None, ["intox:statements:three_true_two_false"])
    assert intox.repair_intox({"fit": "skip"}, beauvau()) == (None, ["skip"])


def test_words_not_in_the_quote_light_nothing() -> None:
    raw = gold_intox()
    raw["statements"][2]["settles_fr"] = "les ouvriers posent un toit"
    express, problems = intox.repair_intox(raw, beauvau())
    assert express is not None and express.statements[2].settles_fr == "" and problems == ["intox:3:settles_not_in_quote"]


def test_the_intox_desk_retries_once_with_the_problems_then_refuses() -> None:
    bad = gold_intox()
    bad["statements"][0]["a1"]["fr"] = "Le marché rouvre le 15 novembre."
    desk = _Desk([bad, gold_intox()])
    express, problems = intox.write_intox(beauvau(), desk)
    assert express is not None and problems == [] and express.prompt_version == intox.INTOX_PROMPT_VERSION
    assert desk.calls[1]["retry_feedback"]["problems"] == ["intox:1:a1:number_not_in_claims"]
    assert intox.write_intox(beauvau(), _Desk([bad, bad])) == (None, ["intox:1:a1:number_not_in_claims"])
    assert intox.write_intox(beauvau(), _Desk([RuntimeError("down")])) == (None, ["intox:desk_failed"])


# ---------------------------------------------------------------------------
# «Le titre»
# ---------------------------------------------------------------------------


def test_the_titre_prompts_own_example_passes_every_check() -> None:
    desk, problems = titre.repair_titre(gold_titre(), beauvau())
    assert problems == [] and desk is not None
    assert [h.role for h in desk.headlines] == ["honest", "exaggerated", "off"]
    assert desk.wrong_fr == "tous les marchés de Paris" and desk.stretch == "place"
    assert desk.headline("honest").why is None and desk.headline("off").why.de
    assert titre.audit(desk, beauvau()) == []


def test_an_exaggerated_headline_that_the_claims_support_is_refused() -> None:
    raw = gold_titre()
    raw["wrong_fr"] = "le marché Beauvau"  # c4 says it: nothing exaggerated
    assert titre.repair_titre(raw, beauvau()) == (None, ["titre:wrong_in_claims"])
    raw = gold_titre()
    raw["wrong_fr"] = "Le 14 Novembre"  # case-folded
    assert titre.repair_titre(raw, beauvau()) == (None, ["titre:wrong_in_claims"])
    raw = gold_titre()
    raw["headlines"][1]["a2"]["fr"] = "Après les travaux, le marché Beauvau rouvre"  # the stretch is gone
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:exaggerated:a2:wrong_not_in_headline"]


def test_the_stretch_is_the_stated_kind() -> None:
    raw = gold_titre()
    raw["stretch"] = "number"
    assert titre.repair_titre(raw, beauvau()) == (None, ["titre:stretch_kind"])
    raw["stretch"] = "certainty"
    assert titre.repair_titre(raw, beauvau()) == (None, ["titre:stretch_kind"])
    assert titre.stretch_problem("always", "tout le monde") is None
    assert titre.stretch_problem("number", "un million de personnes") is None
    assert titre.stretch_problem("certainty", "c'est officiel") is None
    assert titre.stretch_problem("place", "500 personnes") == "stretch_kind"


def test_the_honest_headline_carries_no_number_or_name_the_claims_lack() -> None:
    raw = gold_titre()
    raw["headlines"][0]["a1"]["fr"] = "Le marché Beauvau rouvre le 15 novembre"
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:honest:a1:number_not_in_claims"]
    raw = gold_titre()
    raw["headlines"][0]["a1"]["fr"] = "Anne Hidalgo rouvre le marché Beauvau"
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:honest:a1:name_not_in_claims"]
    raw = gold_titre()
    raw["headlines"][0]["b1"]["fr"] = "Tous les marchés de Paris rouvrent le 14 novembre"
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:honest:b1:says_too_much"]


def test_headlines_are_ours_and_keep_their_limits() -> None:
    raw = gold_titre()
    raw["headlines"][0]["b1"]["fr"] = "le marché Beauvau rouvrira le 14 novembre"  # the outlet's words
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:honest:b1:outlet_words"]
    raw = gold_titre()
    raw["headlines"][2]["a1"]["fr"] = "Dans le 12e, des ouvriers changent le vieux toit"
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:off:a1:too_long"]
    raw = gold_titre()
    del raw["headlines"][2]["why"]
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:off:why:missing"]
    raw = gold_titre()
    raw["headlines"][2]["role"] = "honest"
    assert titre.repair_titre(raw, beauvau()) == (None, ["titre:headlines:roles"])


def test_the_tiles_are_true_and_never_say_too_much() -> None:
    raw = gold_titre()
    raw["build"]["facts"][0]["fr"] = "rouvre comme tous les marchés de Paris"
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:build:fact:0:says_too_much"]
    raw = gold_titre()
    raw["build"]["subjects"][0]["fr"] = "Mon cher, le marché"
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:build:subject:0:vocative"]
    raw = gold_titre()
    raw["build"]["facts"][1]["fr"] = "accueille des touristes"
    assert titre.repair_titre(raw, beauvau())[1] == ["titre:build:fact:1:ungrounded"]
    raw = gold_titre()
    raw["build"]["frame"]["fr"] = "Tous les marchés de Paris"
    desk, problems = titre.repair_titre(raw, beauvau())
    assert desk.build.frame.fr == "Le marché Beauvau" and problems == ["titre:build:frame:says_too_much"]


def test_the_titre_desk_retries_once_then_refuses() -> None:
    bad = gold_titre()
    bad["wrong_fr"] = "le marché Beauvau"
    desk = _Desk([bad, gold_titre()])
    made, problems = titre.write_titre(beauvau(), desk)
    assert made is not None and problems == [] and desk.calls[1]["retry_feedback"]["problems"] == ["titre:wrong_in_claims"]
    assert titre.write_titre(beauvau(), _Desk([bad, bad])) == (None, ["titre:wrong_in_claims"])
    assert titre.write_titre(beauvau(), _Desk([{"fit": "skip"}])) == (None, ["skip"])


# ---------------------------------------------------------------------------
# The evergreens and the morning
# ---------------------------------------------------------------------------


def test_the_shipped_evergreens_pass_every_check() -> None:
    fete = next(d for d in load_evergreens() if d.id == FETE)
    assert intox.audit(evergreen_intox(FETE), fete) == []
    assert titre.audit(evergreen_titre(FETE), fete) == []
    dumped = fete.model_dump(mode="json")
    assert "titre" not in dumped and "intox" not in dumped, "never attached to the loaded evergreen"
    assert evergreen_intox("evergreen-bac") is None and evergreen_titre("evergreen-bac") is None


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


def _row(db: Session, dossier: EditorialDossier, period: str, **checks: str) -> RevueDossier:
    row = RevueDossier(id=f"{period}-{dossier.id}"[:120], week=WEEK, period=period, topic=dossier.topic,
                       payload=dossier.model_dump(mode="json"), source_hashes={}, checks=dict(checks),
                       builder_version="revue-builder-v3")
    db.add(row)
    db.commit()
    return row


def test_each_morning_writes_each_once_per_row_and_skips_what_the_comptoir_skipped(db_session: Session,
                                                                                   revue_tables) -> None:
    db = db_session
    period = "2026-03-10"
    story = beauvau()
    sensitive = beauvau(id="2026-03-10-un-drame")
    _row(db, story, period)
    _row(db, sensitive, period, comptoir="skip")
    desk = _Desk([gold_intox()])
    assert intox.ensure_intox(db, period, provider=desk) == [story.id]
    assert len(desk.calls) == 1, "the sensitive story is never asked"
    desk = _Desk([gold_titre()])
    assert titre.ensure_titre(db, period, provider=desk) == [story.id]
    rows = {r.payload["id"]: r for r in db.scalars(select(RevueDossier).where(RevueDossier.period == period))}
    assert rows[story.id].payload["intox"]["statements"][1]["wrong_fr"] == "le 20 mars"
    assert rows[story.id].payload["titre"]["wrong_fr"] == "tous les marchés de Paris"
    assert rows[sensitive.id].checks["intox"] == "skip" and rows[sensitive.id].checks["titre"] == "skip"
    assert intox.ensure_intox(db, period, provider=_Desk([])) == [], "once per row"
    assert titre.ensure_titre(db, period, provider=_Desk([])) == []
    stored = EditorialDossier.model_validate(rows[story.id].payload)
    assert intox.intox_of(stored) is not None and titre.titre_of(stored) is not None


def test_the_morning_task_runs_both_desks_only_while_the_switch_is_on(monkeypatch) -> None:
    from app.tasks import revue as task

    calls: list[str] = []
    monkeypatch.setattr(task, "intake_now", lambda **_: {"status": "ok", "period": "2026-03-10"})
    monkeypatch.setattr(task, "leads_now", lambda **_: calls.append("leads") or {})
    monkeypatch.setattr(task, "comptoir_now", lambda **_: calls.append("comptoir") or {})
    monkeypatch.setattr(task, "fil_now", lambda **_: calls.append("fil") or {})
    monkeypatch.setattr(task, "rubriques_now", lambda **_: calls.append("rubriques") or {})
    monkeypatch.setattr(task, "_queue_painting", lambda period: {})
    monkeypatch.setattr(settings, "REVUE_COMPTOIR_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", False)
    assert "rubriques" not in task.weekly_intake() and calls == ["leads", "comptoir"]
    calls.clear()
    monkeypatch.setattr(settings, "REVUE_ASSIGNMENTS_ENABLED", True)
    assert "rubriques" in task.weekly_intake() and calls == ["leads", "comptoir", "fil", "rubriques"]
    monkeypatch.undo()
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert task.rubriques_now(period="2026-03-10") == {"status": "disabled"}
