"""WP-119 phase 0 — the checks on meaning (§4.2).

No DB, no network. The Knowledge check runs against the real season 1
(``app/data/season/s1``). See docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.services.revue import checks
from app.services.revue.checks import CHECK_NAMES, CheckResult, failures, passed
from app.services.revue.dossier import Claim, EditorialDossier
from app.services.revue.session import LearnerContext, SessionPlan, StageCast, plan_for
from app.services.season.format import load_season

WEEK = "2026-W40"  # Monday 2026-09-28 .. Sunday 2026-10-04

SOURCE_TEXTS = {
    "le_monde_front": (
        "En Bourgogne, les raisins sont rentrés tôt. Les vendanges ont commencé fin août,\n"
        "deux semaines plus tôt que la moyenne, dans plusieurs domaines de la Côte."
    ),
    "rfi_france": (
        "Sur les coteaux, on parle météo. « C’est le climat qui change », estime un vigneron "
        "de Beaune, qui a vendangé en dix jours."
    ),
}


def _dossier_data() -> dict[str, Any]:
    return {
        "id": "2026-w40-vendanges-bourgogne",
        "week": WEEK,
        "topic": "food",
        "title_fr": "Des vendanges précoces et courtes en Bourgogne",
        "summary_fr": "En Bourgogne, les vendanges ont commencé tôt cette année et ont été courtes.",
        "claims": [
            {
                "id": "c1",
                "kind": "fact",
                "fr": "Les vendanges ont commencé fin août dans plusieurs domaines, deux semaines plus tôt que la moyenne.",
                "quote": "ont commencé fin août, deux semaines plus tôt",
                "source_id": "le_monde_front",
                "url": "https://example-presse.test/le-monde/2026/09/29/vendanges-precoces",
                "published_at": "2026-09-29",
            },
            {
                "id": "c2",
                "kind": "interpretation",
                "fr": "Pour certains vignerons, c'est un signe du climat qui change.",
                "attributed_to": "plusieurs vignerons cités",
                "quote": "« C'est le climat qui change », estime un vigneron de Beaune",
                "source_id": "rfi_france",
                "url": "https://example-presse.test/rfi/2026/09/28/bourgogne-climat",
                "published_at": "2026-09-28",
            },
        ],
        "entities": [{"name": "Bourgogne", "kind": "place"}],
        "uncertainties": ["Les sources ne disent pas si les prix vont changer."],
        "angles": [
            {
                "id": "a1",
                "fr": "Ce que ça change pour qui achète du vin",
                "purpose": "understand_change",
            }
        ],
        "places": [
            {
                "id": "vignoble_bourgogne",
                "name_fr": "Un vignoble en Bourgogne",
                "brief": "rows of vines",
            }
        ],
        "time_scope": {"happening": "2026-08-25/2026-10-05", "relevant_until": "2026-10-20"},
        "sources": [
            {
                "id": "le_monde_front",
                "name": "Le Monde",
                "url": "https://example-presse.test/lm",
                "published_at": "2026-09-29",
            },
            {
                "id": "rfi_france",
                "name": "RFI",
                "url": "https://example-presse.test/rfi",
                "published_at": "2026-09-28",
            },
        ],
    }


def _dossier(**changes: Any) -> EditorialDossier:
    data = copy.deepcopy(_dossier_data())
    for key, value in changes.items():
        data[key] = value
    return EditorialDossier.model_validate(data)


def _with_claim(index: int, **fields: Any) -> EditorialDossier:
    data = copy.deepcopy(_dossier_data())
    data["claims"][index].update(fields)
    return EditorialDossier.model_validate(data)


def _reasons(results: list[CheckResult]) -> list[str | None]:
    return [result.reason for result in failures(results)]


@pytest.fixture
def dossier() -> EditorialDossier:
    return _dossier()


# -- the whole dossier ----------------------------------------------------------


def test_good_dossier_passes_every_dossier_check(dossier: EditorialDossier) -> None:
    results = checks.run_dossier_checks(dossier, source_texts=SOURCE_TEXTS, week=WEEK)
    assert results and all(isinstance(result, CheckResult) for result in results)
    assert failures(results) == []
    assert passed(results)
    assert {result.check for result in results} == {"anchor", "attribution", "temporal"}
    assert all(result.check in CHECK_NAMES for result in results)


def test_failures_and_passed_helpers() -> None:
    good = CheckResult(ok=True, check="anchor")
    bad = CheckResult(ok=False, check="anchor", reason="quote_not_in_source")
    assert failures([good, bad, good]) == [bad]
    assert passed([good]) and passed([]) and not passed([good, bad])


# -- Anchor ---------------------------------------------------------------------


def test_anchor_passes_with_one_ok_result_per_claim(dossier: EditorialDossier) -> None:
    results = checks.check_anchor(dossier, SOURCE_TEXTS)
    assert [(r.ok, r.detail["claim_id"]) for r in results] == [(True, "c1"), (True, "c2")]


def test_anchor_smart_quotes_in_the_source_still_match(dossier: EditorialDossier) -> None:
    # The source has « C’est » (U+2019) and the quote «C'est» (ASCII): both fold to '.
    assert "’" in SOURCE_TEXTS["rfi_france"] and "’" not in dossier.claims[1].quote
    assert passed(checks.check_anchor(dossier, SOURCE_TEXTS))


def test_anchor_refuses_a_changed_word_and_drops_the_dossier() -> None:
    dossier = _with_claim(0, quote="ont commencé fin juillet, deux semaines plus tôt")
    results = checks.check_anchor(dossier, SOURCE_TEXTS)
    assert _reasons(results) == ["quote_not_in_source", "too_few_claims_anchored"]
    assert failures(results)[0].detail["claim_id"] == "c1"
    assert failures(results)[1].detail["anchored"] == 1


def test_anchor_missing_source_text(dossier: EditorialDossier) -> None:
    results = checks.check_anchor(dossier, {"le_monde_front": SOURCE_TEXTS["le_monde_front"]})
    assert _reasons(results) == ["source_text_missing", "too_few_claims_anchored"]
    assert failures(results)[0].detail == {"claim_id": "c2", "source_id": "rfi_france"}


def test_anchor_claim_not_grounded_in_its_quote() -> None:
    dossier = _with_claim(0, fr="Le prix du vin va baisser cette année.")
    results = checks.check_anchor(dossier, SOURCE_TEXTS)
    assert _reasons(results)[0] == "claim_not_grounded_in_quote"


# -- Attribution ----------------------------------------------------------------


def test_attribution_flags_an_opinion_typed_as_fact() -> None:
    dossier = _with_claim(0, fr="C'est scandaleux : les vendanges ont commencé fin août.")
    results = checks.check_attribution(dossier)
    [failure] = failures(results)
    assert failure.reason == "fact_reads_as_opinion"
    assert failure.detail["claim_id"] == "c1"
    assert failure.detail["retype_as"] == "interpretation"
    assert failure.detail["word"] == "scandaleux"


def test_attribution_accepts_the_opinion_as_an_attributed_interpretation() -> None:
    dossier = _with_claim(
        0,
        kind="interpretation",
        attributed_to="un vigneron de Beaune",
        fr="C'est scandaleux : les vendanges ont commencé fin août.",
    )
    assert passed(checks.check_attribution(dossier))


def test_attribution_whole_words_only(dossier: EditorialDossier) -> None:
    # «enfin» is in the lexicon; «enfinement» is not a word, «Enfin» capitalised is.
    assert passed(
        checks.check_attribution(_with_claim(0, fr="Les vendanges ont commencé fin août."))
    )
    flagged = checks.check_attribution(_with_claim(0, fr="Enfin, les vendanges ont commencé."))
    assert _reasons(flagged) == ["fact_reads_as_opinion"]


def test_attribution_honours_the_judge(dossier: EditorialDossier) -> None:
    seen: list[str] = []

    def judge(fr: str) -> bool:
        seen.append(fr)
        return True  # reads as an opinion

    results = checks.check_attribution(dossier, judge=judge)
    assert seen == [dossier.claims[0].fr]  # facts only
    assert _reasons(results) == ["fact_reads_as_opinion"]
    # A judge that says "report" overrides the lexicon.
    opinionated = _with_claim(0, fr="C'est scandaleux : les vendanges ont commencé fin août.")
    assert passed(checks.check_attribution(opinionated, judge=lambda fr: False))


def test_attribution_catches_a_hand_edited_interpretation_without_attribution(
    dossier: EditorialDossier,
) -> None:
    raw = dossier.claims[1].model_dump()
    raw["attributed_to"] = None
    unattributed = Claim.model_construct(**raw)
    edited = dossier.model_copy(update={"claims": [dossier.claims[0], unattributed]})
    results = checks.check_attribution(edited)
    assert _reasons(results) == ["missing_attribution"]
    assert failures(results)[0].detail["claim_id"] == "c2"


# -- Temporal -------------------------------------------------------------------


def test_temporal_happening_ended_the_week_before() -> None:
    dossier = _dossier(
        time_scope={"happening": "2026-09-01/2026-09-27", "relevant_until": "2026-10-20"}
    )
    assert _reasons(checks.check_temporal(dossier, WEEK)) == ["not_this_week"]


def test_temporal_expired_before_sunday() -> None:
    dossier = _dossier(
        time_scope={"happening": "2026-08-25/2026-10-05", "relevant_until": "2026-10-03"}
    )
    results = checks.check_temporal(dossier, WEEK)
    assert _reasons(results) == ["expired"]
    assert failures(results)[0].detail["sunday"] == "2026-10-04"


def test_temporal_relative_weekday_is_refused_absolute_date_passes() -> None:
    relative = _with_claim(0, fr="Les vendanges ont commencé jeudi dans plusieurs domaines.")
    results = checks.check_temporal(relative, WEEK)
    assert _reasons(results) == ["relative_date"]
    assert failures(results)[0].detail == {"claim_id": "c1", "word": "jeudi", "words": ["jeudi"]}
    absolute = _with_claim(
        0, fr="Les vendanges ont commencé jeudi 15 octobre dans plusieurs domaines."
    )
    assert passed(checks.check_temporal(absolute, WEEK))


def test_temporal_relative_words_in_the_summary() -> None:
    dossier = _dossier(summary_fr="Aujourd’hui, les vendanges se terminent en Bourgogne.")
    results = checks.check_temporal(dossier, WEEK)
    assert _reasons(results) == ["relative_date"]
    assert failures(results)[0].detail["field"] == "summary_fr"
    assert failures(results)[0].detail["word"] == "aujourd'hui"


def test_temporal_single_day_scope_pins_weekday_names() -> None:
    data = _dossier_data()
    data["time_scope"] = {"happening": "2026-10-01/2026-10-01", "relevant_until": "2026-10-20"}
    data["claims"][0]["fr"] = "Le marché ouvre jeudi, mais demain il sera fermé."
    results = checks.check_temporal(EditorialDossier.model_validate(data), WEEK)
    assert [f.detail["words"] for f in failures(results)] == [["demain"]]


def test_temporal_stale_and_future_sources() -> None:
    stale = _with_claim(0, published_at="2026-09-04")  # 30 days before Sunday 10-04
    results = checks.check_temporal(stale, WEEK)
    assert _reasons(results) == ["stale_source"]
    assert failures(results)[0].detail["claim_id"] == "c1"
    future = _with_claim(1, published_at="2026-10-05")
    assert _reasons(checks.check_temporal(future, WEEK)) == ["future_source"]


def test_temporal_evergreen_skips_source_age() -> None:
    data = _dossier_data()
    data["evergreen"] = True
    data["claims"][0]["published_at"] = "2024-09-04"
    assert passed(checks.check_temporal(EditorialDossier.model_validate(data), WEEK))
    data["time_scope"] = {"happening": "2026-11-01/2026-11-02", "relevant_until": "2026-11-20"}
    assert _reasons(checks.check_temporal(EditorialDossier.model_validate(data), WEEK)) == [
        "not_this_week"
    ]


# -- Knowledge (real season 1) ---------------------------------------------------


@pytest.fixture(scope="module")
def season():
    return load_season("s1")


def test_knowledge_refuses_a_gap_reveal_and_passes_a_harmless_line(season) -> None:
    assert any(row.id == "berlin" for row in season.gaps["g1"].must_not)
    lines = [
        "Il pleut sur le quai, Margaux essuie les tables.",
        "Odile est partie à Berlin, je crois.",
    ]
    results = checks.check_knowledge(lines, season=season, gap_id="g1", flags={})
    assert [r.ok for r in results] == [True, False]
    failure = failures(results)[0]
    assert failure.reason == "forbidden_reveal"
    assert failure.detail["line_index"] == 1
    assert failure.detail["must_not_id"] == "berlin"
    assert failure.detail["match"].lower() == "berlin"


def test_knowledge_global_list_respects_unless_flags(season) -> None:
    line = "Le prix est de 310 000 euros."
    assert _reasons(checks.check_knowledge([line], season=season, gap_id="g1", flags={})) == [
        "forbidden_reveal"
    ]
    assert passed(
        checks.check_knowledge([line], season=season, gap_id="g1", flags={"s1.price_public": True})
    )
    # An id that is not a gap (a tentpole) still gets the season's global list.
    results = checks.check_knowledge([line], season=season, gap_id="t1", flags={})
    assert _reasons(results) == ["forbidden_reveal"]
    assert failures(results)[0].detail["gap_known"] is False


# -- Distinguishable -------------------------------------------------------------


def _choice(**changes: Any) -> dict[str, Any]:
    exercise: dict[str, Any] = {
        "format": "choice",
        "options": [
            {"id": "o1", "text": "Fin août, deux semaines plus tôt"},
            {"id": "o2", "text": "Fin octobre, comme chaque année"},
            {"id": "o3", "text": "Elles n'ont pas encore commencé"},
        ],
        "answer": "o1",
        "contradicted_by": {"o2": "c1", "o3": "c1"},
    }
    exercise.update(changes)
    return exercise


def test_distinguishable_well_formed_choice_passes(dossier: EditorialDossier) -> None:
    results = checks.check_distinguishable(_choice(), dossier.claims)
    assert [(r.ok, r.detail.get("option_id")) for r in results] == [(True, "o1")]


def test_distinguishable_accepts_the_journey_option_shape(dossier: EditorialDossier) -> None:
    exercise = {
        "task_type": "choice",
        "options": [
            {"id": "opt_a", "text_fr": "fin août"},
            {"id": "opt_b", "text_fr": "fin octobre"},
        ],
        "correct_option_id": "opt_a",
        "contradicted_by": {"opt_b": "c1"},
    }
    assert passed(checks.check_distinguishable(exercise, dossier.claims))


def test_distinguishable_distractor_without_a_contradicting_claim(
    dossier: EditorialDossier,
) -> None:
    results = checks.check_distinguishable(_choice(contradicted_by={"o2": "c1"}), dossier.claims)
    assert _reasons(results) == ["distractor_not_contradicted"]
    assert failures(results)[0].detail["option_id"] == "o3"
    # A mapping to a claim the learner was not shown does not count.
    results = checks.check_distinguishable(_choice(), [dossier.claims[1]])
    assert _reasons(results).count("distractor_not_contradicted") == 2


def test_distinguishable_two_options_equal_to_the_answer(dossier: EditorialDossier) -> None:
    exercise = {
        "format": "choice",
        "options": ["fin août", "Fin août", "fin octobre"],
        "answer": "fin août",
        "contradicted_by": {"fin octobre": "c1"},
    }
    assert _reasons(checks.check_distinguishable(exercise, dossier.claims)) == ["no_single_answer"]


def test_distinguishable_answer_unsupported(dossier: EditorialDossier) -> None:
    exercise = _choice(
        options=[
            {"id": "o1", "text": "Une grève des transports"},
            {"id": "o2", "text": "Fin octobre"},
        ],
        contradicted_by={"o2": "c1"},
    )
    assert _reasons(checks.check_distinguishable(exercise, dossier.claims)) == [
        "answer_unsupported"
    ]
    assert passed(checks.check_distinguishable({**exercise, "supported_by": "c1"}, dossier.claims))


def test_distinguishable_short_answer_needs_rubric_claims(dossier: EditorialDossier) -> None:
    base = {"format": "short_answer", "options": []}
    assert _reasons(checks.check_distinguishable(base, dossier.claims)) == ["rubric_without_claims"]
    empty = {**base, "rubric": {"claim_ids": []}}
    assert _reasons(checks.check_distinguishable(empty, dossier.claims)) == [
        "rubric_without_claims"
    ]
    unshown = {**base, "rubric": {"claim_ids": ["c9"]}}
    assert _reasons(checks.check_distinguishable(unshown, dossier.claims)) == [
        "rubric_without_claims"
    ]
    good = {**base, "rubric": {"claim_ids": ["c1", "c2"]}}
    assert passed(checks.check_distinguishable(good, dossier.claims))


def test_distinguishable_vocabulary_formats_are_not_applicable(dossier: EditorialDossier) -> None:
    exercise = {
        "format": "match_pairs",
        "options": [{"id": "f1", "text_fr": "la vendange", "side": "fr"}],
    }
    [result] = checks.check_distinguishable(exercise, dossier.claims)
    assert result.ok and result.reason == "not_applicable"


# -- Render ---------------------------------------------------------------------

KNOWN = {
    "known_places": {"cafe", "quai"},
    "props": {"notebook", "glass"},
    "cast_ids": {"romy_tremblay", "margaux_barman", "camille_marchand"},
}


@pytest.fixture
def plan(dossier: EditorialDossier) -> SessionPlan:
    learner = LearnerContext(band="A2", ui_language="de")
    built = plan_for(dossier, learner, place_known_plate=lambda place_id: None)
    return built.model_copy(update={"stage": built.stage.model_copy(update={"place_id": "cafe"})})


def _restage(plan: SessionPlan, **stage: Any) -> SessionPlan:
    return plan.model_copy(update={"stage": plan.stage.model_copy(update=stage)})


def test_render_good_plan_passes(plan: SessionPlan) -> None:
    results = checks.check_render(plan, camille_chosen=False, **KNOWN)
    assert [r.ok for r in results] == [True]


def test_render_unknown_outfit_prop_place_and_cast(plan: SessionPlan) -> None:
    assert _reasons(
        checks.check_render(_restage(plan, dress="tuxedo"), camille_chosen=False, **KNOWN)
    ) == ["unknown_outfit"]
    holding = _restage(
        plan, cast=[StageCast(id="romy_tremblay", hold="umbrella"), StageCast(id="user")]
    )
    results = checks.check_render(holding, camille_chosen=False, **KNOWN)
    assert _reasons(results) == ["unknown_prop"]
    assert failures(results)[0].detail == {
        "field": "hold",
        "cast_id": "romy_tremblay",
        "value": "umbrella",
    }
    assert _reasons(
        checks.check_render(_restage(plan, place_id="vignoble"), camille_chosen=False, **KNOWN)
    ) == ["unknown_place"]
    painted = _restage(plan, place_id="vignoble", plate_url="https://example.test/plate.webp")
    assert passed(checks.check_render(painted, camille_chosen=False, **KNOWN))
    stranger = _restage(plan, cast=[StageCast(id="jean_inconnu")])
    assert _reasons(checks.check_render(stranger, camille_chosen=False, **KNOWN)) == [
        "unknown_cast"
    ]


def test_render_camille_needs_her_look(plan: SessionPlan) -> None:
    with_camille = _restage(plan, cast=[*plan.stage.cast, StageCast(id="camille_marchand")])
    assert _reasons(checks.check_render(with_camille, camille_chosen=False, **KNOWN)) == [
        "camille_look_not_chosen"
    ]
    assert passed(checks.check_render(with_camille, camille_chosen=True, **KNOWN))


# -- Credit ---------------------------------------------------------------------


def test_credit_needs_a_rubric_version() -> None:
    results = checks.check_credit({"capability_id": "vocab:la_vendange", "outcome": "correct"})
    assert _reasons(results) == ["evidence_missing_fields"]
    assert failures(results)[0].detail["missing"] == ["rubric_version"]


def test_credit_never_masters_an_unknown_capability() -> None:
    write = {
        "rubric_version": "revue-rubric-v1",
        "capability_id": "vocab:x",
        "outcome": "correct",
        "capability_known": False,
    }
    assert _reasons(checks.check_credit(write)) == ["mastery_claimed_for_unknown_capability"]
    assert passed(checks.check_credit({**write, "outcome": "unscored"}))
    assert passed(checks.check_credit({**write, "capability_known": True}))
    assert _reasons(checks.check_credit({**write, "outcome": "mastered"})) == ["invalid_outcome"]
