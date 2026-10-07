"""WP-149 «Rien de refusé à l'écran»: what a learner sees has passed its checks.

The WP-136 read (``docs/implementation/atelier-v2/evidence/loss-rate-2026-10-07/``)
lost no day, but showed learners nine replies the story-lane critic refused after
release (five a false «met») and served nine pages the story critic refused twice.
What these tests pin, with the fake providers only (never a paid call):

A. **Grading before release.** The met-gate lowers a «met» the learner's words do not
   support before the response is returned. A false «met» the critic still finds
   after release keeps its line on screen, but the ledger, the step's result and the
   ending are corrected; a resolution that contradicts the shown grade is refused.
B. **Correctness is hard, storytelling soft.** ``canon_register`` (Gus «tu» before T3)
   and ``flag_contradiction`` (Margaux holding the letter the learner gave Marin)
   block a draft; a storytelling-only critic refusal is still served and logged; a
   correctness critic refusal is never served — the day falls to the re-read.
C. **Measurement.** The pilot digest's line, and an offline replay of the stored
   WP-136 refusals through the new classifier, gate and correction.
"""

from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db.models.daily_journey import DailyJourneyStep
from app.db.models.pilot_event import PilotEvent
from app.db.models.session import SessionLearningMoment
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.journey_learning import JOURNEY_SOURCE_TYPE
from app.services.met_gate import met_gate, required_slots
from app.services.season.canon_guards import (
    CORRECTNESS,
    STORYTELLING,
    flag_holder_hits,
    issue_class,
    review_class,
)
from app.services.season.director import critic_payload, forbidden_hits
from app.services.season.format import load_season
from app.services.season.reprise import REPRISE_SCENARIO_PREFIX
from tests import learner_walk as walk
from tests import test_journey_end_to_end as support
from tests import test_living_story
from tests.test_learner_walk import production_day  # noqa: F401 - fixture
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.test_wp87_lanes import (  # noqa: F401 - fixtures
    ANSWER,
    LaneProvider,
    _resolution,
    _respond,
    _to_respond,
    inline,
    jobs,
    one_exchange,
    provider,
)
from tests.test_wp124a_season_reprise import A1_DE, CardPicker, _play, _user
from tests.test_wp133b_director_fixes import _register_context, _spoken

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pilot_digest import format_story_correctness_line  # noqa: E402

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled
driver = test_living_story.driver

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/implementation/atelier-v2/evidence/loss-rate-2026-10-07"


def _verdict(outcome="met", quotes=(), targets=()):
    return lanes.TutorVerdict(outcome=outcome, evidence_quotes=list(quotes), demonstrated_target_ids=list(targets))


def _payload(objective: str, learner_text: str, *, history=(), targets=()):
    return {
        "scene": {"objective_native": objective, "objective_semantics": ""},
        "rubric": "",
        "learner_text": learner_text,
        "history": [{"learner": text, "character": "…"} for text in history],
        "targets": list(targets),
    }


# ---------------------------------------------------------------------------
# A.1 The met-gate
# ---------------------------------------------------------------------------


def test_the_met_gate_reads_the_required_slots_off_the_task():
    assert required_slots(["Write a short reply to Margaux saying why you stay."]) == ["reason"]
    assert required_slots(["Dites pourquoi vous restez."]) == ["reason"]
    assert required_slots(["Sag Marin, warum du bleibst."]) == ["reason"]
    assert required_slots(["Proposez une condition claire pour protéger le groupe."]) == ["condition"]
    # Asking why is a question, not a reason owed.
    assert required_slots(["Ask Romy why she left the café."]) == []
    assert required_slots(["Demande à Lila pourquoi elle part."]) == []
    assert required_slots(["Offer your help for the exhibition."]) == []


def test_a_met_without_the_reason_the_task_asks_for_is_partially_met():
    # Run 3 (A1), g1.3, verbatim: the read logged three false «met» on this turn.
    verdict = _verdict(quotes=["C'est gentil."])
    reasons = met_gate(verdict, _payload("Write a short reply to Margaux saying why you stay.",
                                         "C'est gentil. Je suis un peu perdu ici."))
    assert reasons == ["missing_reason"] and verdict.outcome == "partially_met"
    kept = _verdict(quotes=["Je reste parce que j’aime le quartier."])
    assert met_gate(kept, _payload("Write a short reply to Margaux saying why you stay.",
                                   "Je reste parce que j'aime le quartier.")) == []
    assert kept.outcome == "met", "the iOS apostrophe is the learner's apostrophe"
    # The reason may have come in an earlier exchange of the same scene.
    earlier = _verdict(quotes=["Oui."])
    assert met_gate(earlier, _payload("Say why you stay.", "Oui.", history=["Je reste pour aider Margaux."])) == []


def test_a_met_whose_quotes_are_not_the_learners_is_partially_met_and_targets_need_their_french():
    verdict = _verdict(quotes=["Je viens samedi."], targets=["7", "9"])
    targets = [{"id": "7", "label_fr": "les affiches"}, {"id": "9", "label_fr": "la clé"}]
    reasons = met_gate(verdict, _payload("Offer your help.", "J'apporte les affiches.", targets=targets))
    assert reasons == ["met_without_evidence"] and verdict.outcome == "partially_met"
    assert verdict.evidence_quotes == [] and verdict.demonstrated_target_ids == ["7"]
    # A grade below «met» is never touched, only its unsupported targets.
    low = _verdict(outcome="not_yet", targets=["9"])
    assert met_gate(low, _payload("Say why you stay.", "Euh.", targets=targets)) == []
    assert low.outcome == "not_yet" and low.demonstrated_target_ids == []


@pytest.fixture
def why_objective(monkeypatch):
    """The scripted scenes ask for a reason (as run 3's g1.1 and g1.3 did)."""

    monkeypatch.setattr(test_living_story, "OBJECTIVES", ["Say why you stay in Paris."])


def test_a_met_without_evidence_is_downgraded_before_release(
    assembled_client, db_session, journey_enabled, clock, provider, jobs, why_objective  # noqa: F811
):
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    result = _respond(assembled_client, d, step)[2].json()
    assert result["character_reply_fr"] == "Merci ! On prépare la salle ensemble."
    assert result["task_outcome"] == "partially_met", "the tutor said met; the learner gave no reason"
    gated = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == lanes.MET_GATED_EVENT, PilotEvent.user_id == d.user_id)
    ).all()
    assert [row.payload["reasons"] for row in gated] == [["missing_reason"]]
    assert "StoryTurn" not in provider.schemas(), "the gate is on the request, before the story lane"
    # The same scene answered with a reason keeps its «met».
    other = driver(assembled_client, db_session)
    step = _to_respond(other)
    kept = _respond(assembled_client, other, step, text="Je reste parce que j'aime le quartier.")[2].json()
    assert kept["task_outcome"] == "met"


# ---------------------------------------------------------------------------
# A.2 / A.3 After release: the record is corrected, the ending agrees
# ---------------------------------------------------------------------------

FALSE_MET = "false_successful_grading: released.outcome is 'met' though the learner did not write the required reason for staying."


def _scripted_reviews(fake, reviews: list[dict]) -> None:
    """The story-lane critic answers ``reviews`` in order, then accepts."""

    original = fake.generate_chat_completion
    queue = list(reviews)

    def scripted(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "TurnReview":
            fake.review = queue.pop(0) if queue else {"released_issues": []}
        return original(messages, **kwargs)

    fake.generate_chat_completion = scripted


def _moments(db, journey_id: str) -> list[SessionLearningMoment]:
    rows = db.scalars(
        select(SessionLearningMoment).where(SessionLearningMoment.source_type == JOURNEY_SOURCE_TYPE)
    ).all()
    return [row for row in rows if (row.prompt_payload or {}).get("journey_id") == journey_id]


def test_a_post_release_false_met_corrects_the_ledger_and_the_ending_never_the_line(
    assembled_client, db_session, journey_enabled, clock, provider, inline  # noqa: F811
):
    _scripted_reviews(provider, [{"released_issues": [FALSE_MET]}])
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    result = _respond(assembled_client, d, step)[2].json()
    assert result["task_outcome"] == "met", "shown before the story lane: the gate found nothing"
    assert result["character_reply_fr"] == "Merci ! On prépare la salle ensemble."
    assert inline == ["done"]

    # The ending was rewritten for the corrected grade.
    stories = [data for schema, data in provider.calls if schema == "StoryTurn"]
    assert [row["released"]["outcome"] for row in stories] == ["met", "partially_met"]
    assert stories[1]["released"]["outcome_corrected_from"] == "met"
    assert any("corrected from met to partially_met" in hint for hint in stories[1]["previous_rejections"])
    # The record: one event, the step's result, the lane, the ledger.
    corrected = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == lanes.GRADING_CORRECTED_EVENT,
                                 PilotEvent.user_id == d.user_id)
    ).all()
    assert [(row.payload["from"], row.payload["to"]) for row in corrected] == [("met", "partially_met")]
    db_session.expire_all()
    steps = db_session.scalars(
        select(DailyJourneyStep).where(DailyJourneyStep.journey_id == UUID(d.journey["id"]))
    ).all()
    respond = next(s for s in steps if s.kind == "respond")
    assert respond.private_task["result"]["outcome"] == "partially_met"
    resolution = next(s for s in steps if s.kind == "resolution")
    assert resolution.private_task["story_lane"]["outcome_key"] == "open"
    assert resolution.private_task["story_lane"]["status"] == "done"
    moments = _moments(db_session, d.journey["id"])
    step_moments = [m for m in moments if m.prompt_payload.get("step_id") == str(respond.id)]
    assert step_moments and {m.prompt_payload["task_outcome"] for m in step_moments} == {"partially_met"}
    assert all(m.prompt_payload["task_outcome_corrected"]["from"] == "met" for m in step_moments)
    # The released line is logged and never retracted.
    logged = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == "reply_refused_after_release",
                                 PilotEvent.user_id == d.user_id)
    ).all()
    assert [row.payload["issue"] for row in logged] == [FALSE_MET]
    d.advance()
    assert _resolution(d.journey)["prompt"]["story_pending"] is False


def test_a_resolution_that_contradicts_the_shown_grade_is_rewritten_not_logged_as_released(
    assembled_client, db_session, journey_enabled, clock, provider, inline  # noqa: F811
):
    contradiction = ("reply_vs_resolution_contradiction: the released outcome is met but the "
                     "resolution says the letter was not answered.")
    _scripted_reviews(provider, [{"released_issues": [contradiction]}])
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    _respond(assembled_client, d, step)
    assert inline == ["done"]
    stories = [data for schema, data in provider.calls if schema == "StoryTurn"]
    assert len(stories) == 2 and contradiction in stories[1]["previous_rejections"]
    assert all(row["released"]["outcome"] == "met" for row in stories), "the shown grade is fixed input"
    logged = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == "reply_refused_after_release",
                                 PilotEvent.user_id == d.user_id)
    ).all()
    assert logged == [], "the ending was not released; it was refused and rewritten"


def test_incompatible_targets_lose_their_credit_and_their_schedule_advance(db_session):
    from datetime import UTC, date, datetime

    from app.db.models.progress import UserVocabularyProgress
    from app.db.models.session import LearningSession
    from app.db.models.user import User
    from app.db.models.vocabulary import VocabularyWord
    from app.services.journey_contracts import TaskOutcome
    from app.services.journey_learning import correct_released_grading, read_journey_evidence

    user = User(email=f"wp149-{uuid4()}@example.com", hashed_password="x")
    db_session.add(user)
    spelled = f"affiche-{uuid4().hex[:6]}"
    word = VocabularyWord(word=spelled, normalized_word=spelled, language="fr", english_translation="poster")
    db_session.add(word)
    db_session.flush()
    later = datetime(2030, 1, 1, tzinfo=UTC)
    progress = UserVocabularyProgress(user_id=user.id, word_id=word.id, due_at=later, next_review_date=later,
                                      due_date=later.date())
    session = LearningSession(user_id=user.id, planned_duration_minutes=0, scenario="story_x", status="completed")
    db_session.add_all([progress, session])
    db_session.flush()
    journey_id, step_id = uuid4(), uuid4()
    common = {"journey_id": str(journey_id), "step_id": str(step_id), "task_outcome": "met",
              "observed_on": date.today().isoformat()}
    credited = SessionLearningMoment(
        session_id=session.id, user_id=user.id, kind="journey_vocabulary", source_type=JOURNEY_SOURCE_TYPE,
        source_id="a", status="completed", srs_credit_applied=True, completed_at=datetime.now(UTC),
        prompt_payload={**common, "source_key": "k1", "target": {"kind": "vocabulary", "id": str(word.id)}},
        result_payload={"evidence_kind": "produced_independent"},
    )
    db_session.add(credited)
    db_session.flush()
    now = datetime.now(UTC)
    changed = correct_released_grading(
        db_session, user=user, journey_id=journey_id, step_id=step_id, outcome=TaskOutcome.PARTIALLY_MET,
        withdrawn_target_ids=[str(word.id)], reason="incompatible_demonstrated_targets", now=now,
    )
    assert changed == {"corrected_rows": 1, "withdrawn_target_ids": [str(word.id)]}
    db_session.refresh(credited)
    db_session.refresh(progress)
    assert credited.srs_credit_applied is False
    assert credited.result_payload["withdrawn"]["reason"] == "incompatible_demonstrated_targets"
    assert credited.prompt_payload["task_outcome"] == "partially_met"
    assert progress.due_date == now.date(), "the false success's schedule advance is given back"
    assert read_journey_evidence(db_session, user=user) == [], "a withdrawn credit is not evidence"


def test_the_correction_names_the_targets_the_issue_names():
    tutor = _verdict(quotes=["x"], targets=["4", "12"])
    released = {"outcome": "met"}
    corrected, record = lanes.grading_correction(
        ['incompatible_demonstrated_targets: released.demonstrated_target_ids = ["4"] is not supported '
         'by the learner_text.'], tutor, released,
    )
    assert corrected.outcome == "met" and corrected.demonstrated_target_ids == ["12"]
    assert record["withdrawn_target_ids"] == ["4"] and record["to"] == "met"
    assert lanes.grading_correction(["attributing_a_learner_choice_to_the_character"], tutor, released) is None
    # A released partial stays partial: there is no false «met» to correct.
    assert lanes.grading_correction([FALSE_MET], tutor, {"outcome": "partially_met"}) is None


# ---------------------------------------------------------------------------
# B.1 The two deterministic guards
# ---------------------------------------------------------------------------


def test_a_gus_tu_draft_before_t3_is_blocked():
    context = _register_context()
    gus_tu = _spoken(context, "augustin_de_roncourt", ("Tu viens ce soir ?", "Tu es en retard."), "Tu prends quoi ?")
    with pytest.raises(engine.StoryUnavailable, match="canon_register") as refused:
        engine._check_canon_register(gus_tu, context)
    assert "Gus" in refused.value.hint and "vous" in refused.value.hint
    with pytest.raises(engine.StoryUnavailable, match="canon_register"):
        engine._validate_scene(deepcopy(gus_tu), context)
    # T3 moved him to tu: served.
    after_t3 = _register_context({"register.augustin_de_roncourt": "tu"})
    engine._check_canon_register(
        _spoken(after_t3, "augustin_de_roncourt", ("Tu viens ce soir ?",), "Tu prends quoi ?"), after_t3
    )
    # The canon's own slip — «first accidental tu, followed by a panicked return to vous».
    engine._check_canon_register(
        _spoken(context, "augustin_de_roncourt", ("Tu… pardon. Vous venez ce soir ?",), "Vous prenez quoi ?"),
        context,
    )
    # His vous, and a tu character's tu: nothing to say.
    engine._check_canon_register(_spoken(context, "augustin_de_roncourt", ("Vous êtes en retard.",), "Vous venez ?"), context)
    engine._check_canon_register(_spoken(context, "margaux_barman", ("La même chose ?",), "Tu es où ?"), context)


def _letter_context(flags: dict, gap: str = "g1") -> dict:
    context = _register_context(flags)
    context["season_script"] = {"id": "s1", "brief": {"gap": {"id": gap}}}
    return context


def _with_visual(context: dict, visual: str, narration: str = "") -> engine.SceneDraft:
    value = deepcopy(test_living_story.draft(context, 0))
    value["character_id"] = "margaux_barman"
    value["panels"][1]["visual_direction"] = visual
    value["panels"][1]["narration_fr"] = narration
    value["panels"][1]["dialogue"] = [{"character_id": "margaux_barman", "text_fr": "Tu as une idée ?"}]
    value["opening_line_fr"] = "Tu peux nous aider ?"
    return engine.SceneDraft.model_validate(value)


def test_a_margaux_holds_the_letter_draft_is_blocked_when_marin_was_trusted_with_it():
    context = _letter_context({"s1.letter_trusted_to": "marin"})
    holds = _with_visual(context, "Close-up: Margaux holds the letter behind the zinc, unopened.")
    with pytest.raises(engine.StoryUnavailable, match="flag_contradiction") as refused:
        engine._check_flag_contradiction(holds, context, [])
    assert "Marin" in refused.value.hint and "Margaux" in refused.value.hint
    with pytest.raises(engine.StoryUnavailable, match="flag_contradiction"):
        engine._check_flag_contradiction(
            _with_visual(context, "Wide shot of the café."), context, ["Margaux range la lettre sous la caisse."]
        )
    # Marin holding it, a new letter, and a day past the gap that reads the flag: served.
    engine._check_flag_contradiction(_with_visual(context, "Marin holds the letter, worried."), context, [])
    # The A1 g1.3 page of the read: «Margaux tient une lettre timbrée» — a new letter.
    engine._check_flag_contradiction(
        _with_visual(context, "Margaux is behind the zinc with a stamped envelope in hand."), context,
        ["Margaux tient une lettre timbrée."],
    )
    later = _letter_context({"s1.letter_trusted_to": "marin"}, gap="g2")
    engine._check_flag_contradiction(_with_visual(later, "Margaux holds the letter."), later, [])
    # Gus read it aloud to the café: nobody's holding is a contradiction.
    public = _letter_context({"s1.letter_trusted_to": "gus"})
    engine._check_flag_contradiction(_with_visual(public, "Margaux holds the letter."), public, [])


def test_flag_holder_hits_reads_french_and_english():
    cast = load_season("s1").cast
    texts = ["La lettre est entre les mains de Lila.", "Lila lit une lettre de sa mère.", "Odile's letter is in Lila's hands."]
    hits = flag_holder_hits(texts, flags={"s1.letter_trusted_to": "margaux"}, gap_id="g1", cast=cast)
    assert [hit["holder"] for hit in hits] == ["Lila"]
    assert flag_holder_hits(texts, flags={}, gap_id="g1", cast=cast) == [], "an unset flag says nothing"


def test_the_invented_date_is_a_negative_example_of_the_director():
    season = load_season("s1")
    hits = forbidden_hits(season, "g7", ["Tu te souviens de la nuit du 14 mars ?"], flags={})
    assert [key for key, _ in hits] == ["invented_dates"]


# ---------------------------------------------------------------------------
# B.2 Critic refusals: storytelling served and logged, correctness never served
# ---------------------------------------------------------------------------


def test_critic_issues_are_classified_correctness_or_storytelling():
    assert issue_class("Make Gus use 'vous' (he still uses 'vous' until T3).") == CORRECTNESS
    assert issue_class("Replace Margaux holding the letter with Marin (who was trusted with the letter).") == CORRECTNESS
    assert issue_class("Make a visible change by the end of the page.") == STORYTELLING
    # «tu» as an ordinary word in a French hint is not a register issue.
    assert issue_class("Montre la coach Lila qui complique l'appel (si tu keep the airline beat).") == STORYTELLING
    assert issue_class("Lila révèle une nouvelle information.") == STORYTELLING
    from app.services.season.director import StoryReview

    assert review_class(StoryReview(meaningful_change=True, honours_choices=False)) == CORRECTNESS
    assert review_class(StoryReview(spoils_next_tentpole=True)) == CORRECTNESS
    assert review_class(StoryReview(issues=["Nothing changes by the end of the day."])) == STORYTELLING


def _review_events(db, user_id, event_type: str) -> list[PilotEvent]:
    return db.scalars(select(PilotEvent).where(PilotEvent.event_type == event_type, PilotEvent.user_id == user_id)).all()


def _first_gap_day(client, db, clock, fake):
    headers, email = walk.register(client, A1_DE)
    _play(client, db, headers, A1_DE, 1, fake)
    clock.advance(days=1)
    _play(client, db, headers, A1_DE, 2, fake, CardPicker("marin"))
    clock.advance(days=1)
    return headers, _user(db, email)


def test_a_storytelling_only_critic_refusal_is_still_served_and_logged(
    assembled_client, db_session, journey_enabled, clock, production_day  # noqa: F811
):
    fake = production_day
    headers, user = _first_gap_day(assembled_client, db_session, clock, fake)
    fake.critic_refusals_left = 10  # «Nothing changes by the end of the day.», every time
    transcript = _play(assembled_client, db_session, headers, A1_DE, 3, fake)
    assert not transcript["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX), "the day is served"
    overrides = _review_events(db_session, user.id, "journey_story_critic_override")
    assert len(overrides) == 1 and overrides[0].payload["class"] == STORYTELLING
    readings = _review_events(db_session, user.id, "journey_story_critic_review")
    assert readings and all(row.payload["class"] == STORYTELLING for row in readings)


CONTINUITY = {
    "hook": True, "stakes": True, "value_turn": True, "meaningful_change": True, "advances_thread": True,
    "in_character": True, "spoils_next_tentpole": False, "honours_choices": False, "obstacle_faced": True,
    "change_summary": "avant → après",
    "issues": ["Replace Margaux holding the letter with Marin (who was trusted with the letter); it contradicts the flags."],
    "accepted": False,
}


def test_a_correctness_critic_refusal_falls_to_the_reread(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    # The plain season drafts carry their reading aids, so no WP-90 soft fallback
    # (a draft the critic never read) stands between the refusals and the re-read.
    fake = season_on
    fake.critic_refusals_left = 0
    fake.spoil_once = False
    headers, user = _first_gap_day(assembled_client, db_session, clock, fake)
    original = fake.generate_chat_completion

    def continuity_refusals(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "StoryReview":
            return SimpleNamespace(content=json.dumps(CONTINUITY), model="fake", fake="test", total_tokens=30, cost=0.0)
        return original(messages, **kwargs)

    monkeypatch.setattr(fake, "generate_chat_completion", continuity_refusals)
    transcript = _play(assembled_client, db_session, headers, A1_DE, 3, fake)
    assert transcript["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX), transcript["scenario"]
    assert _review_events(db_session, user.id, "journey_story_critic_override") == [], "never served"
    readings = _review_events(db_session, user.id, "journey_story_critic_review")
    assert len(readings) >= 2 and all(row.payload["class"] == CORRECTNESS for row in readings)


def test_the_critic_reads_the_page_with_its_learner_turn():
    payload = critic_payload(
        {"today": {}},
        {
            "objective_native": "Say why you stay.",
            "character_id": "margaux_barman",
            "opening_line_fr": "Pourquoi tu restes ?",
            "season_checklist": {"change_after": "The café knows why you stay.", "turn_want": "a reason"},
        },
    )
    assert payload["learner_turn"] == {
        "page_ends_on_learner_turn": True,
        "task": "Say why you stay.",
        "answers": "margaux_barman",
        "character_asks_fr": "Pourquoi tu restes ?",
        "turn_want": "a reason",
        "planned_change": "The café knows why you stay.",
    }
    from app.services.season.director import STORY_CRITIC

    assert "Never ask\nfor the learner's reply" in STORY_CRITIC or "Never ask for the learner's reply" in " ".join(
        STORY_CRITIC.split()
    )


# ---------------------------------------------------------------------------
# C. The digest and the offline replay of WP-136
# ---------------------------------------------------------------------------


def test_the_digest_splits_served_overrides_by_class_and_counts_corrections(db_session):
    from datetime import UTC, datetime

    from app.services.pilot_events import PilotEventService

    user_id = uuid4()
    stamp = datetime.now(UTC)
    events = PilotEventService(db_session)
    for event_type, payload in [
        ("journey_story_critic_override", {"class": "storytelling"}),
        ("journey_story_critic_override", {}),
        ("journey_story_critic_review", {"class": "correctness"}),
        ("reply_met_gated", {"reasons": ["missing_reason"]}),
        ("reply_grading_corrected", {"from": "met", "to": "partially_met"}),
        ("reply_refused_after_release", {"issue": FALSE_MET}),
        ("reply_refused_after_release", {"issue": "attributing_a_learner_choice_to_the_character"}),
    ]:
        events.record(event_type, user_id=user_id, entity_type="living_story", payload=payload, cost_usd=0.0, occurred_at=stamp)
    db_session.flush()
    assert format_story_correctness_line(db_session, stamp.date(), str(user_id)) == (
        "Story correctness (WP-149): 2 critic override(s) served [storytelling 1 (50 %), unclassified 1 (50 %)] · "
        "1 correctness refusal(s), never served · 1 «met» lowered by the met-gate before release · "
        "1 after-release grading correction(s) of 2 after-release issue(s)"
    )
    assert format_story_correctness_line(db_session, stamp.date(), str(uuid4())) == "Story correctness (WP-149): none"


#: The nine after-release issues of the WP-136 read, verbatim from the runs'
#: ``pytest.log`` (gitignored): run 2 (B1) g4.5, run 3 (A1) g1.1 and g1.3.
AFTER_RELEASE = {
    ("run2-b1", "g4.5"): [
        "attributing_a_learner_choice_to_the_character",
        "unsupported_commitment_resolution",
        "false_successful_grading",
    ],
    ("run3-a1", "g1.1"): ["false_successful_grading"],
    ("run3-a1", "g1.3"): [
        "false_successful_grading: The released proposal and outcome shown to the learner claim the task was 'met' despite the learner not giving the required reason for staying.",
        "reply_vs_resolution_contradiction: The released materials present both a met outcome and a resolution saying the letter was not answered; this contradiction was already shown to the learner.",
        "false_successful_grading: released.outcome = 'met' is inconsistent with the learner's reply and the scene objective.",
        'incompatible_demonstrated_targets: released.demonstrated_target_ids = ["4"] is not supported by the learner_text.',
        "false_successful_grading: released.outcome is 'met' though the learner did not write the required reason for staying.",
    ],
}


def _turns(band_file: Path, position: str) -> tuple[str, list[str]]:
    """The day's task and every learner line, from the run's own transcript."""

    text = band_file.read_text(encoding="utf-8")
    section = re.search(rf"^## Jour \d+ — {re.escape(position)} .*?(?=^## )", text, re.S | re.M).group(0)
    task = re.search(r"\*Ta tâche : (.+?)\*", section).group(1)
    return task, re.findall(r"^\*\*Toi\*\* — «(.+?)»$", section, re.M)


def test_the_offline_replay_of_the_stored_wp136_refusals():
    """No paid call: the stored refusal records through the new classifier, gate and
    correction. The numbers are the WP-149 report's."""

    # --- The story critic's refusals (run*/ and topup/live-*/, ``refusals[]``) ---
    critic = []
    for path in sorted([*EVIDENCE.glob("run*/*.1.json"), *EVIDENCE.glob("topup/live-*/*.1.json")]):
        for row in json.loads(path.read_text(encoding="utf-8"))["refusals"]:
            if row["reason"] == "story_critic_refused":
                critic.append((path.parent.name, row["position"], row["hint"].split(" | ")))
    assert len(critic) == 10
    classes = {(run, position): review_class(None, issues) for run, position, issues in critic}
    assert sorted(key for key, kind in classes.items() if kind == CORRECTNESS) == [
        ("run1-c1", "g1.2"),  # «Make Gus use 'vous' (he still uses 'vous' until T3)»
        ("run3-a1", "g1.3"),  # «Replace Margaux holding the letter with Marin»
    ]
    # Calibration's target: refusals that ask for the learner's own words on the page.
    on_page = re.compile(r"\b(?:lecteur|joueur|learner)\b.{0,40}\b(?:parole|r[ée]ponse|dise|speaking|writing|action)\b"
                         r"|\b(?:parole|r[ée]ponse|action)\b.{0,12}\b(?:du lecteur|du joueur)\b", re.I)
    asking = [(run, position) for run, position, issues in critic if any(on_page.search(i) for i in issues)]
    assert len(asking) == 5, asking

    # --- The nine after-release issues: what the met-gate and the correction do ---
    files = {"run2-b1": EVIDENCE / "run2-b1/B1.1.md", "run3-a1": EVIDENCE / "run3-a1/A1.1.md"}
    caught_before_release = 0
    corrected_after = 0
    ending_refused = 0
    for (run, position), issues in AFTER_RELEASE.items():
        task, said = _turns(files[run], position)
        verdict = _verdict(quotes=[said[-1]], targets=["4"])
        reasons = met_gate(verdict, {**_payload(task, said[-1], history=said[:-1]), "targets": []})
        codes = [lanes.issue_code(issue) for issue in issues]
        if reasons:
            caught_before_release += codes.count("false_successful_grading")
        tutor = _verdict(quotes=[said[-1]], targets=["4"])
        correction = lanes.grading_correction(issues, tutor, {"outcome": "met"})
        if correction is not None:
            corrected_after += sum(code in lanes.GRADING_ISSUES for code in codes)
        ending_refused += sum(code in lanes.ENDING_ISSUES for code in codes)
    assert sum(len(issues) for issues in AFTER_RELEASE.values()) == 9
    assert caught_before_release == 5, "every false «met» of the read is lowered before release"
    assert corrected_after == 6, "5 false «met» + 1 unsupported target, had any reached release"
    assert ending_refused == 2, "the contradiction and the unsupported commitment resolution"
