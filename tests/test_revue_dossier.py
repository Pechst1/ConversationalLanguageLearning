"""WP-119 phase 0 — the three parts of La Revue: dossier, session plan, conversation state.

No DB, no network. See docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md §3.
"""

from __future__ import annotations

import copy
import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.revue import checks, policy
from app.services.revue.dossier import (
    EditorialDossier,
    fold,
    quote_word_count,
    week_bounds,
)
from app.services.revue.session import (
    LearnerContext,
    SessionPlan,
    Support,
    next_support_level,
    plan_for,
)
from app.services.revue.state import ConversationState


def _dossier_data() -> dict[str, Any]:
    """The §3.1 example, completed with fictional sources."""

    return {
        "id": "2026-w40-vendanges-bourgogne",
        "week": "2026-W40",
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
                "confidence": "reported",
            },
            {
                "id": "c2",
                "kind": "interpretation",
                "fr": "Pour certains vignerons, c'est un signe du climat qui change.",
                "attributed_to": "plusieurs vignerons cités",
                "quote": "« C’est le climat qui change », estime un vigneron de Beaune",
                "source_id": "rfi_france",
                "url": "https://example-presse.test/rfi/2026/09/28/bourgogne-climat",
                "published_at": "2026-09-28T07:30:00Z",
            },
        ],
        "entities": [
            {"name": "Bourgogne", "kind": "place"},
            {"name": "Jeanne Martel", "kind": "person", "role": "présidente du syndicat viticole"},
        ],
        "uncertainties": ["Les sources ne disent pas si les prix vont changer."],
        "angles": [
            {"id": "a1", "fr": "Ce que ça change pour qui achète du vin", "purpose": "understand_change"},
            {"id": "a2", "fr": "Les vignerons sont-ils d'accord entre eux ?", "purpose": "explain_disagreement"},
        ],
        "places": [
            {
                "id": "vignoble_bourgogne",
                "name_fr": "Un vignoble en Bourgogne",
                "brief": "rows of vines on a slope, a stone hut, late-summer light",
                "known": False,
            }
        ],
        "time_scope": {"happening": "2026-08-25/2026-10-05", "relevant_until": "2026-10-20"},
        "sources": [
            {
                "id": "le_monde_front",
                "name": "Le Monde",
                "url": "https://example-presse.test/le-monde/2026/09/29/vendanges-precoces",
                "published_at": "2026-09-29",
            },
            {
                "id": "rfi_france",
                "name": "RFI",
                "url": "https://example-presse.test/rfi/2026/09/28/bourgogne-climat",
                "published_at": "2026-09-28",
            },
        ],
        "evergreen": False,
    }


@pytest.fixture
def dossier() -> EditorialDossier:
    return EditorialDossier.model_validate(_dossier_data())


# -- dossier (§3.1) --------------------------------------------------------------


def test_valid_dossier_parses(dossier: EditorialDossier) -> None:
    assert dossier.dossier_version == "revue-v1"
    assert [claim.id for claim in dossier.facts()] == ["c1"]
    assert [claim.id for claim in dossier.interpretations()] == ["c2"]
    assert dossier.claims_by_id()["c2"].attributed_to == "plusieurs vignerons cités"
    assert dossier.claims_by_id()["c2"].published_at == date(2026, 9, 28)
    assert dossier.claims_by_id()["c2"].confidence == "reported"
    assert dossier.person_names() == ["Jeanne Martel"]


def test_quote_of_41_words_is_rejected() -> None:
    data = _dossier_data()
    data["claims"][0]["quote"] = " ".join(["mot"] * 41)
    with pytest.raises(ValidationError, match="41 words"):
        EditorialDossier.model_validate(data)
    data["claims"][0]["quote"] = "  ".join(["mot"] * 40)
    EditorialDossier.model_validate(data)


def test_interpretation_without_attribution_is_rejected() -> None:
    data = _dossier_data()
    del data["claims"][1]["attributed_to"]
    with pytest.raises(ValidationError, match="attributed_to"):
        EditorialDossier.model_validate(data)
    data = _dossier_data()
    data["claims"][1].update(kind="forecast", attributed_to="  ")
    with pytest.raises(ValidationError, match="attributed_to"):
        EditorialDossier.model_validate(data)


def test_claim_with_unknown_source_is_rejected() -> None:
    data = _dossier_data()
    data["claims"][0]["source_id"] = "le_figaro"
    with pytest.raises(ValidationError, match="le_figaro"):
        EditorialDossier.model_validate(data)


def test_person_entity_needs_a_role() -> None:
    data = _dossier_data()
    data["entities"][1].pop("role")
    with pytest.raises(ValidationError, match="role"):
        EditorialDossier.model_validate(data)


def test_structure_minimums() -> None:
    data = _dossier_data()
    data["claims"] = data["claims"][:1]
    with pytest.raises(ValidationError):
        EditorialDossier.model_validate(data)
    data = _dossier_data()
    data["topic"] = "weather"
    with pytest.raises(ValidationError, match="topic"):
        EditorialDossier.model_validate(data)


def test_fold_quote_marks_and_whitespace() -> None:
    assert fold("l’homme") == "l'homme"
    assert fold("‘a’ ‛b `c ´d") == "'a' 'b 'c 'd"
    assert fold("“bonjour”") == '"bonjour"'
    assert fold("  deux  mots\n") == "deux mots"
    assert quote_word_count("  l’homme   qui  marche ") == 3
    assert quote_word_count("") == 0


@pytest.mark.parametrize("week", ["2026-40", "2026-W4", "2026-W54", "2026-w40", "W40-2026"])
def test_week_format_is_validated(week: str) -> None:
    data = _dossier_data()
    data["week"] = week
    with pytest.raises(ValidationError):
        EditorialDossier.model_validate(data)


def test_week_bounds() -> None:
    assert week_bounds("2026-W40") == (date(2026, 9, 28), date(2026, 10, 4))


def test_time_scope_parses(dossier: EditorialDossier) -> None:
    assert dossier.time_scope.start == date(2026, 8, 25)
    assert dossier.time_scope.end == date(2026, 10, 5)
    assert dossier.time_scope.relevant_until == date(2026, 10, 20)
    for bad in ("2026-08-25", "2026-10-05/2026-08-25", "25/08/2026-05/10/2026"):
        data = _dossier_data()
        data["time_scope"]["happening"] = bad
        with pytest.raises(ValidationError):
            EditorialDossier.model_validate(data)


# -- policy (§4, §6, §7, §8) -----------------------------------------------------


def test_policy_fallbacks_and_guests_are_real() -> None:
    from app.services.season.world import SEASON_ONE_LOCATIONS

    assert set(policy.PLACE_FALLBACKS.values()) <= set(SEASON_ONE_LOCATIONS)
    assert set(policy.GUEST_AFFINITY) == set(policy.TOPICS)
    assert set(policy.DRESS_FOR_PLACE.values()) <= set(policy.OUTFITS)
    assert [row["id"] for row in policy.GUEST_AFFINITY["city"]] == ["camille_marchand", "landlord_marchand"]
    assert [row["id"] for row in policy.GUEST_AFFINITY["politics"]] == [
        "marin_leveque",
        "augustin_de_roncourt",
    ]


def test_place_kinds_and_dress() -> None:
    assert policy.place_kind("cave_beaune Une cave à Beaune vaulted cellar") == "cellar"
    assert policy.dress_for(policy.place_kind("cave_beaune")) == "apron"
    assert policy.dress_for(policy.place_kind("hemicycle Assemblée nationale")) == "suit"
    assert policy.dress_for(policy.place_kind("stade_de_france")) == "sport"
    assert policy.dress_for(policy.place_kind("quai sous la pluie")) == "raincoat"
    assert policy.place_kind("quai sous la pluie") == "quay_rain"
    assert policy.dress_for(policy.place_kind("chantier du métro")) == "hi_vis"
    assert policy.dress_for(policy.place_kind("une chaise au soleil")) == "coat"
    assert policy.dress_for("nowhere") == "coat"


def test_plate_forbidden_and_sensitive() -> None:
    assert policy.plate_forbidden_hits("a market square, a crowd, a party flag, no Visage") == [
        "crowd",
        "flag",
        "visage",
    ]
    assert policy.plate_forbidden_hits("rows of vines on a slope, a stone hut") == []
    assert policy.is_sensitive("Un attentat à Paris")


def test_band_support_follows_the_section_6_table() -> None:
    assert policy.band_support("A1")["glosses"] == "shown"
    assert policy.band_support("a2")["translation"] == "on_request"
    assert policy.band_support("B1")["reading_target_words"] == 140
    assert policy.band_support("B2+")["glosses"] == "none"
    assert policy.band_support("C1")["vocab_target"] == 7


# -- session plan (§3.2) ---------------------------------------------------------


def test_plan_for_a1(dossier: EditorialDossier) -> None:
    plan = plan_for(
        dossier,
        LearnerContext(band="A1", ui_language="de", interests=["cuisine"]),
        place_known_plate=lambda place_id: None,
    )
    assert plan.plan_version == "revue-plan-v1"
    assert plan.angle_id == "a1" and plan.purpose == "understand_change"
    assert plan.chosen_by == "recommended"
    assert plan.support.glosses == "shown"
    assert plan.support.translation == "one_tap"
    assert plan.support.reading_target_words == 60
    assert plan.activities.make_options == ["headline_choice", "reader_question", "tell_margaux"]
    assert plan.activities.default == ["arrive", "facts", "pursue", "make", "close"]
    assert plan.stage.place_id == "vignoble_bourgogne"
    assert plan.stage.dress == "apron"
    assert plan.stage.plate_url is None
    assert [(cast.id, cast.hold) for cast in plan.stage.cast] == [
        ("romy_tremblay", "notebook"),
        ("user", None),
    ]
    assert [guest.id for guest in plan.stage.guests_available] == ["margaux_barman"]
    assert "Un vignoble en Bourgogne" in plan.stage.guests_available[0].reason
    assert plan.budget.turns == 14 and plan.budget.minutes == 8
    assert plan.vocabulary == []


def test_plan_for_b1(dossier: EditorialDossier) -> None:
    plan = plan_for(
        dossier,
        LearnerContext(band="B1", ui_language="en"),
        angle_id="a2",
        chosen_by="learner",
        place_known_plate=lambda place_id: f"/plates/{place_id}.webp",
    )
    assert plan.support.glosses == "tap"
    assert plan.activities.make_options == [
        "headline_write",
        "reader_question",
        "tell_margaux",
        "short_report",
    ]
    assert plan.angle_id == "a2" and plan.purpose == "explain_disagreement"
    assert plan.chosen_by == "learner"
    assert plan.stage.plate_url == "/plates/vignoble_bourgogne.webp"
    with pytest.raises(ValueError, match="a9"):
        plan_for(dossier, LearnerContext(band="B1", ui_language="en"), angle_id="a9")


def test_cellar_place_dresses_in_an_apron() -> None:
    data = _dossier_data()
    data["places"] = [
        {"id": "cave_meursault", "name_fr": "Une cave à Meursault", "brief": "a vaulted stone cellar, barrels"}
    ]
    plan = plan_for(EditorialDossier.model_validate(data), LearnerContext(band="A2", ui_language="fr"))
    assert plan.stage.dress == "apron"


def test_plan_vocabulary_is_validated_against_the_dossier(dossier: EditorialDossier) -> None:
    plan = plan_for(dossier, LearnerContext(band="A2", ui_language="de"))
    data = plan.model_dump(mode="json")
    data["vocabulary"] = [{"fr": "la vendange", "gloss": {"de": "die Weinlese"}, "claim_id": "c1"}]
    assert SessionPlan.model_validate(data, context={"dossier": dossier}).vocabulary[0].claim_id == "c1"
    data["vocabulary"][0]["claim_id"] = "c7"
    SessionPlan.model_validate(data)  # without a dossier only the structure is checked
    with pytest.raises(ValidationError, match="c7"):
        SessionPlan.model_validate(data, context={"dossier": dossier})
    data["stage"]["dress"] = "tuxedo"
    with pytest.raises(ValidationError, match="dress"):
        SessionPlan.model_validate(data)


def test_next_support_level_progression() -> None:
    support = Support(
        glosses="none",
        translation="none",
        simplify_on_breakdown=True,
        reading_target_words=200,
        vocab_target=7,
    )
    first = next_support_level(support)
    assert (first.glosses, first.translation, first.reading_target_words) == ("tap", "on_request", 140)
    second = next_support_level(first)
    assert (second.glosses, second.translation, second.reading_target_words) == ("shown", "one_tap", 98)
    third = next_support_level(next_support_level(second))
    assert (third.glosses, third.translation) == ("shown", "one_tap")
    assert third.reading_target_words == 48
    assert next_support_level(third).reading_target_words == 40
    assert next_support_level(next_support_level(third)).reading_target_words == 40
    assert third.vocab_target == 7
    assert support.glosses == "none"  # the original is not mutated


# -- conversation state (§3.3) ---------------------------------------------------


def test_state_replay_and_round_trip() -> None:
    state = ConversationState()
    assert state.closed is False and state.current_artifact is None and state.guest_on_stage is None
    state.append("claim_shown", claim_id="c1")
    state.append("turn_learner", text="Et les prix ?")
    state.append("question_raised", text="Les prix vont-ils monter ?", answerable=False)
    state.append("claim_shown", claim_ids=["c2", "c1"])
    state.append("guest_enter", id="margaux_barman")
    state.append("evidence", word="la vendange", correct=True)
    state.append("evidence", word="le vigneron", correct=False)
    state.append("evidence", words=["précoce"], correct=True)
    state.append("choice", activity="reader_question")
    state.append("artifact", kind="reader_question", text="Les prix vont-ils changer ?", revision=1)
    state.append("artifact", kind="reader_question", text="Est-ce que les prix vont changer ?", revision=2)
    state.append("support_changed", reason="breakdown")
    state.append("turn_learner", text="Oui.")
    last = state.append("closed", outcome="reader_question")

    assert [event.seq for event in state.events] == list(range(1, 15))
    assert last.seq == 14
    assert state.claims_shown == {"c1", "c2"}
    assert state.words_used_correctly == {"la vendange", "précoce"}
    assert state.current_artifact == {
        "kind": "reader_question",
        "text": "Est-ce que les prix vont changer ?",
        "revision": 2,
    }
    assert state.questions[0]["answerable"] is False
    assert state.choices[0]["activity"] == "reader_question"
    assert state.guest_on_stage == "margaux_barman"
    assert state.support_level == 1
    assert state.turns_used == 2
    assert state.closed is True

    stored = state.to_json()
    json.dumps(stored)  # JSON-safe for the journey row
    again = ConversationState.from_json(copy.deepcopy(stored))
    assert again == state
    assert ConversationState.from_json(json.dumps(stored)).claims_shown == {"c1", "c2"}
    assert ConversationState.from_json(None).events == []
    assert again.append("turn_romy", text="Merci !").seq == 15


def test_state_rejects_unknown_kinds_and_out_of_order_events() -> None:
    state = ConversationState()
    with pytest.raises(ValidationError):
        state.append("teleport")  # type: ignore[arg-type]
    stored = ConversationState().to_json()
    stored["events"] = [
        {"seq": 2, "at": "2026-10-02T10:00:00Z", "kind": "closed", "payload": {}},
        {"seq": 1, "at": "2026-10-02T10:00:01Z", "kind": "closed", "payload": {}},
    ]
    with pytest.raises(ValidationError, match="seq"):
        ConversationState.from_json(stored)


# -- checks contract and the news_service move -----------------------------------


def test_check_stubs_exist(dossier: EditorialDossier) -> None:
    result = checks.CheckResult(ok=False, check="anchor", reason="quote_not_in_source")
    assert result.detail == {}
    results = checks.run_dossier_checks(dossier, source_texts={}, week="2026-W40")
    assert results and all(isinstance(row, checks.CheckResult) for row in results)
    assert {row.check for row in results} <= set(checks.CHECK_NAMES)
    for name in (
        "check_anchor",
        "check_attribution",
        "check_temporal",
        "check_knowledge",
        "check_distinguishable",
        "check_render",
        "check_credit",
    ):
        assert callable(getattr(checks, name))


def test_news_service_imports_the_sensitive_list_from_policy() -> None:
    from app.services.news_service import NewsService

    assert NewsService.FEUILLETON_SENSITIVE_TERMS is policy.SENSITIVE_TERMS
    assert "attentat" in policy.SENSITIVE_TERMS and "viol " in policy.SENSITIVE_TERMS
