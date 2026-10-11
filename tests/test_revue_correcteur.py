"""WP-122 part B: Le Correcteur (``revue/correcteur.py``, ``/revue/correcteur/*``).

* Seeding picks the learner's own errata first and fills with the band's classiques;
  the quota is 3 at A1–A2 and 4 at B1+.
* The seeded text differs from the unseeded text only inside the spans, and the
  Anchor / Attribution checks give the same verdicts on the unseeded lines (facts
  unchanged) — for every evergreen, at every band.
* A rule with no site moves on to the next candidate; only then one rewrite is asked
  (a fake provider), and a rewrite that moves a fact is refused.
* Marks: noticed / repaired / missed / false alarm; a repair writes the errata memory
  and that erratum is not seeded on the next draft.
* The routes: 404 while the flag is off, 200 on; the draft never carries its key.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints import revue_correcteur as endpoint
from app.config import settings
from app.db.models.error import UserError
from app.db.models.revue_correcteur import RevueCorrection
from app.db.models.user import User
from app.main import create_app
from app.services.revue import correcteur
from app.services.revue.correcteur import (
    CLASSIQUES,
    QUOTA,
    FakeCorrecteurProvider,
    differs_only_in_spans,
    draft_for,
    grade,
    unseed,
)
from app.services.revue.evergreen import load_evergreens

PASSWORD = "securepass123"
GREVE = "evergreen-greve-transports"


@pytest.fixture(scope="module")
def correcteur_tables(db_engine) -> Generator[None, None, None]:
    table = RevueCorrection.__table__
    created = not inspect(db_engine).has_table(table.name)
    if created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        if created:
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, correcteur_tables) -> Session:
    return db_session


def dossier(dossier_id: str = GREVE):
    return next(d for d in load_evergreens() if d.id == dossier_id)


def make_user(db: Session, level: str = "B1.1") -> User:
    user = User(id=uuid.uuid4(), email=f"corr-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate=level)
    db.add(user)
    db.commit()
    return user


def erratum(db: Session, user: User, wrong: str, right: str, label: str, *, lapses: int = 2, occurrences: int = 3) -> UserError:
    row = UserError(
        user_id=user.id,
        error_category="grammar",
        original_text=wrong,
        correction=right,
        display_label=label,
        memory_key=f"grammar:concept-none:{uuid.uuid4().hex[:6]}:{label}",
        why_wrong="",
        state="repairing",
        occurrences=occurrences,
        lapses=lapses,
        next_review_date=None,
    )
    db.add(row)
    db.commit()
    return row


def two_recurring(db: Session, user: User) -> tuple[UserError, UserError]:
    """The B1 fixture of the spec: past-participle agreement and du / de le."""

    pp = erratum(db, user, "la grève est annoncé", "la grève est annoncée", "Accord du participe", lapses=3)
    du = erratum(db, user, "le début de le mois", "le début du mois", "Contraction", lapses=2)
    return pp, du


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def test_the_rules_map_errata_by_their_pairs() -> None:
    class T:
        def __init__(self, wrong, right, label=""):
            self.example_learner, self.example_correct, self.label = wrong, right, label
            self.memory_key, self.payload = None, {}

    assert correcteur.rule_for_target(T("elle est arrivé", "elle est arrivée")) == "pp_agreement"
    assert correcteur.rule_for_target(T("de le pain", "du pain")) == "contraction"
    assert correcteur.rule_for_target(T("a Paris", "à Paris")) == "accent"
    assert correcteur.rule_for_target(T("il va mangé", "il va manger")) == "verb_ending"
    assert correcteur.rule_for_target(T("une grand ville", "une grande ville")) == "adj_gender"
    assert correcteur.rule_for_target(T("les voiture", "les voitures")) == "plural_s"
    assert correcteur.rule_for_target(T("", "", "Accord du participe passé")) == "pp_agreement"
    assert correcteur.rule_for_target(T("je suis d'accord", "je suis d'accord", "Vocabulaire")) is None


def test_seeding_picks_the_learners_errata_first_then_classiques(db: Session) -> None:
    user = make_user(db, "B1.1")
    pp, du = two_recurring(db, user)
    draft = draft_for(db, user, dossier(), "B1")
    errata = [s for s in draft.seeded if s.source == "errata"]
    assert {s.error_id for s in errata} == {str(pp.id), str(du.id)}
    assert {s.rule for s in errata} == {"pp_agreement", "contraction"}
    by_rule = {s.rule: s for s in errata}
    assert (by_rule["contraction"].correct_fr, by_rule["contraction"].wrong_fr) == ("au", "à le")
    assert by_rule["pp_agreement"].wrong_fr.endswith("ée")
    classiques = [s for s in draft.seeded if s.source == "classique"]
    assert classiques and all(s.rule in CLASSIQUES["B1"] for s in classiques)
    assert all(s.error_id is None for s in classiques)
    # Errata come first: no classique sits where an erratum could have.
    assert len(draft.seeded) + draft.short_by == QUOTA["B1"]


def test_a_new_learner_gets_the_three_classiques(db: Session) -> None:
    user = make_user(db, "A1.1")
    draft = draft_for(db, user, dossier(), "A1")
    assert [s.source for s in draft.seeded] == ["classique"] * 3
    assert sorted(s.rule for s in draft.seeded) == sorted(CLASSIQUES["A1"])


@pytest.mark.parametrize("band", ["A1", "A2", "B1", "B2"])
def test_quota_per_band(db: Session, band: str) -> None:
    user = make_user(db, f"{band}.1")
    for index in range(5):  # more errata than any quota
        erratum(db, user, f"mot{index} de le", f"mot{index} du", f"Contraction {index}")
    two_recurring(db, user)
    draft = draft_for(db, user, dossier(), band)
    assert len(draft.seeded) <= QUOTA[band]
    assert len(draft.seeded) + draft.short_by == QUOTA[band]
    assert QUOTA[band] == (3 if band in {"A1", "A2"} else 4)


@pytest.mark.parametrize("band", ["A1", "A2", "B1"])
@pytest.mark.parametrize("dossier_id", [d.id for d in load_evergreens()])
def test_spans_are_the_only_difference_and_facts_are_unchanged(db: Session, band: str, dossier_id: str) -> None:
    user = make_user(db, f"{band}.1")
    draft = draft_for(db, user, dossier(dossier_id), band)
    assert draft.seeded, dossier_id
    assert differs_only_in_spans(draft.base_sentences, draft.sentences, draft.seeded)
    # Character by character: outside the spans the seeded lines are the base lines.
    for index, (seeded, base) in enumerate(zip(draft.sentences, draft.base_sentences, strict=True)):
        spans = sorted(s.span for s in draft.seeded if s.sentence_index == index)
        keep_seeded, keep_base, cursor_s, cursor_b = [], [], 0, 0
        for seed in sorted((s for s in draft.seeded if s.sentence_index == index), key=lambda s: s.span):
            keep_seeded.append(seeded[cursor_s : seed.span[0]])
            keep_base.append(base[cursor_b : seed.base_span[0]])
            cursor_s, cursor_b = seed.span[1], seed.base_span[1]
            assert seeded[seed.span[0] : seed.span[1]] == seed.wrong_fr != seed.correct_fr
        keep_seeded.append(seeded[cursor_s:])
        keep_base.append(base[cursor_b:])
        assert keep_seeded == keep_base, (index, spans)
    assert unseed(draft.sentences, draft.seeded) == draft.base_sentences
    # The base lines state the dossier's claims verbatim (no rewrite without a provider).
    by_id = dossier(dossier_id).claims_by_id()
    for line, claim_id in zip(draft.base_sentences, draft.claim_ids, strict=True):
        if claim_id:
            assert line == by_id[claim_id].fr
    assert draft.checks["spans_only"] is True
    assert draft.checks["unchanged"] is True
    assert draft.checks["anchor"] and all(row["ok"] for row in draft.checks["anchor"])
    assert all(row["ok"] for row in draft.checks["attribution"])


def test_a_point_with_no_site_tries_the_next_erratum(db: Session) -> None:
    user = make_user(db, "A2.1")
    # «aux» is nowhere in the grève dispatch: the verbatim form has no site, and its
    # rule (contraction) takes «au» instead — still the learner's own point.
    odd = erratum(db, user, "il parle à les enfants", "il parle aux enfants", "Contraction", lapses=4)
    vocab = erratum(db, user, "je suis d'accord avec", "je suis d'accord avec toi", "Vocabulaire", lapses=3)
    draft = draft_for(db, user, dossier(), "A2")
    sources = {s.error_id: s for s in draft.seeded if s.error_id}
    assert str(odd.id) in sources and sources[str(odd.id)].rule == "contraction"
    assert str(vocab.id) not in sources  # no rule, no verbatim site: skipped, the next one tried


def test_one_rewrite_only_when_the_quota_is_short(db: Session) -> None:
    user = make_user(db, "B1.1")
    two_recurring(db, user)
    base = draft_for(db, user, dossier(), "B1")
    assert base.short_by == 1  # the grève dispatch has no fourth free site at B1
    line = "La loi a été votée : elle organise les transports pendant une grève, mais elle ne crée pas une vraie obligation de service minimum."
    provider = FakeCorrecteurProvider(script=[{"sentence_fr": line}])
    draft = draft_for(db, user, dossier(), "B1", provider=provider)
    assert len(provider.calls) == 1
    assert provider.calls[0]["point"] in CLASSIQUES["B1"] + ("pp_agreement", "contraction")
    assert draft.rewrite and draft.rewrite["accepted"] is True
    assert len(draft.seeded) == QUOTA["B1"] and draft.short_by == 0
    assert draft.checks["unchanged"] and draft.checks["spans_only"]
    assert line in draft.base_sentences


def test_a_rewrite_that_moves_a_fact_is_refused(db: Session) -> None:
    user = make_user(db, "B1.1")
    two_recurring(db, user)
    moved = "La loi a été votée en 2007 : elle organise les transports pendant une grève."
    provider = FakeCorrecteurProvider(script=[{"sentence_fr": moved}])
    draft = draft_for(db, user, dossier(), "B1", provider=provider)
    assert draft.rewrite and draft.rewrite["accepted"] is False
    assert draft.rewrite["reason"] == "numbers_or_names_moved"
    assert moved not in draft.base_sentences and draft.short_by == 1
    # A full quota never asks.
    quiet = FakeCorrecteurProvider()
    draft_for(db, make_user(db, "A1.1"), dossier(), "A1", provider=quiet)
    assert quiet.calls == []


def test_options_at_a1_include_the_correct_form_and_none_at_b1(db: Session) -> None:
    user = make_user(db, "A1.1")
    draft = draft_for(db, user, dossier(), "A1")
    units = {(u.sentence_index, u.span): u for u in draft.units}
    for seed in draft.seeded:
        unit = units[(seed.sentence_index, seed.span)]
        assert unit.text == seed.wrong_fr
        assert unit.options and seed.correct_fr in unit.options and seed.wrong_fr in unit.options
        assert 2 <= len(unit.options) <= 3
    assert all(u.options is None for u in draft_for(db, user, dossier(), "B1").units)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def _mark(seed, fix=None, **extra):
    return {"sentence_index": seed.sentence_index, "span": list(seed.span), "fix_fr": fix, **extra}


def test_marks_grading_for_the_four_outcomes(db: Session) -> None:
    user = make_user(db, "A1.1")
    draft = draft_for(db, user, dossier(), "A1")
    first, second, third = draft.seeded
    clean_line = 2 if all(s.sentence_index != 2 for s in draft.seeded) else 0
    # A correct word, far from any seed: the first unit of a line, if it is not seeded.
    correct_unit = next(
        u for u in draft.units
        if not any(s.sentence_index == u.sentence_index and correcteur._overlaps(u.span, s.span) for s in draft.seeded)
        and len(u.text) > 3
    )
    result = grade(draft, [
        _mark(first, first.correct_fr),
        _mark(second, "pas ça"),
        {"sentence_index": correct_unit.sentence_index, "span": list(correct_unit.span), "fix_fr": None},
    ])
    outcomes = {o["wrong_fr"]: o["outcome"] for o in result["outcomes"]}
    assert outcomes == {first.wrong_fr: "repaired", second.wrong_fr: "noticed", third.wrong_fr: "missed"}
    assert result["counts"] == {"seeded": 3, "repaired": 1, "noticed": 1, "missed": 1, "false_alarms": 1}
    [alarm] = result["false_alarms"]
    assert alarm["text_fr"] == correct_unit.text
    # Missed spans are revealed with their correction.
    missed = next(o for o in result["outcomes"] if o["outcome"] == "missed")
    assert missed["correct_fr"] == third.correct_fr
    assert result["romy_line_fr"] == correcteur.ROMY_LINES["A"]["most"]
    assert clean_line in {0, 1, 2}


def test_a_fix_typed_over_a_wider_span_still_repairs() -> None:
    draft = correcteur.Draft(
        dossier_id="d", band="B1", title_fr="t", kicker_fr="k", byline_fr="b",
        sentences=["Il est à le moins midi."], base_sentences=["Il est au moins midi."], claim_ids=[None],
        seeded=[correcteur.Seed(0, (7, 11), "à le", "au", None, "contraction", "classique", "contraction", (7, 9))],
        units=[],
    )
    wide = grade(draft, [{"sentence_index": 0, "span": [7, 17], "fix_fr": "au moins"}])
    assert wide["outcomes"][0]["outcome"] == "repaired"
    one_word = grade(draft, [{"sentence_index": 0, "span": [7, 8], "fix_fr": "au"}])
    assert one_word["outcomes"][0]["outcome"] == "repaired"
    nothing = grade(draft, [])
    assert nothing["outcomes"][0]["outcome"] == "missed"
    assert nothing["romy_line_fr"] == correcteur.ROMY_LINES["B"]["none"]


def test_a_repair_writes_evidence_and_is_not_seeded_next_time(db: Session) -> None:
    user = make_user(db, "B1.1")
    pp, du = two_recurring(db, user)
    row = correcteur.create_correction(db, user, dossier(), band="B1")
    draft = correcteur.Draft.from_json(row.draft)
    pp_seed = next(s for s in draft.seeded if s.error_id == str(pp.id))
    du_seed = next(s for s in draft.seeded if s.error_id == str(du.id))
    row = correcteur.grade_marks(db, user, row, [_mark(pp_seed, pp_seed.correct_fr)])
    assert row.result["evidence"] == [str(pp.id)]
    db.refresh(pp)
    db.refresh(du)
    assert pp.reps == 1 and pp.next_review_date is not None
    assert pp.next_review_date.replace(tzinfo=pp.next_review_date.tzinfo or UTC) > datetime.now(UTC)
    assert du.next_review_date is None  # missed: left due
    # Grading twice changes nothing.
    again = correcteur.grade_marks(db, user, row, [])
    assert again.result == row.result
    following = draft_for(db, user, dossier(), "B1")
    assert str(pp.id) not in {s.error_id for s in following.seeded}
    assert str(du.id) in {s.error_id for s in following.seeded}
    assert du_seed.rule == "contraction"


def test_a_noticed_erratum_also_stops_being_seeded(db: Session) -> None:
    user = make_user(db, "B1.1")
    pp, _ = two_recurring(db, user)
    row = correcteur.create_correction(db, user, dossier(), band="B1")
    seed = next(s for s in correcteur.Draft.from_json(row.draft).seeded if s.error_id == str(pp.id))
    correcteur.grade_marks(db, user, row, [_mark(seed, None)])
    assert str(pp.id) not in {s.error_id for s in draft_for(db, user, dossier(), "B1").seeded}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session, correcteur_tables) -> Iterator[TestClient]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[endpoint.get_correcteur_provider] = lambda: FakeCorrecteurProvider()
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> tuple[dict[str, str], str]:
    email = f"corr-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": PASSWORD, "target_language": "fr", "native_language": "de"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def test_routes_are_404_while_the_flag_is_off(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_CORRECTEUR_ENABLED", False)
    assert api.get("/api/v1/revue/correcteur/week").status_code == 404
    headers, _ = login(api)
    assert api.get("/api/v1/revue/correcteur/week", headers=headers).status_code == 404
    assert api.post(f"/api/v1/revue/correcteur/{GREVE}", headers=headers).status_code == 404


def test_routes_draft_and_grade_when_on(api: TestClient, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_CORRECTEUR_ENABLED", True)
    assert api.get("/api/v1/revue/correcteur/week").status_code == 401
    headers, email = login(api)
    week = api.get("/api/v1/revue/correcteur/week", headers=headers)
    assert week.status_code == 200, week.text
    assert week.json()["dossiers"] and week.json()["corrected"] == []

    made = api.post(f"/api/v1/revue/correcteur/{GREVE}", headers=headers)
    assert made.status_code == 200, made.text
    view = made.json()
    assert set(view) == {"id", "dossier_id", "band", "kicker_fr", "title_fr", "byline_fr", "sentences", "units",
                         "errors_count", "options_enabled", "result"}
    assert view["errors_count"] == 3 and view["options_enabled"] is True  # a new account is A1
    # The key never travels with the draft.
    assert "seeded" not in made.text and "base_sentences" not in made.text and "correct_fr" not in made.text

    user = db_session.scalar(select(User).where(User.email == email))
    row = db_session.get(RevueCorrection, uuid.UUID(view["id"]))
    assert row is not None and row.user_id == user.id
    seed = correcteur.Draft.from_json(row.draft).seeded[0]
    graded = api.post(f"/api/v1/revue/correcteur/{view['id']}/marks", headers=headers,
                      json={"marks": [_mark(seed, seed.correct_fr, picked=True)]})
    assert graded.status_code == 200, graded.text
    body = graded.json()
    assert body["counts"]["repaired"] == 1 and body["counts"]["missed"] == 2
    assert body["releve_href"].startswith("/notebook")
    assert all("error_id" not in o for o in body["outcomes"])

    other_headers, _ = login(api)
    assert api.post(f"/api/v1/revue/correcteur/{view['id']}/marks", headers=other_headers,
                    json={"marks": []}).status_code == 404
    assert api.post("/api/v1/revue/correcteur/no-such-dossier", headers=headers).status_code == 404
    bad = api.post(f"/api/v1/revue/correcteur/{view['id']}/marks", headers=headers,
                   json={"marks": [{"sentence_index": 0, "span": [4, 2]}]})
    assert bad.status_code == 422
