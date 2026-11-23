"""#973 — a slip's rule is decided from what the correction changed.

Walk of 21 Nov 2026 (`a2-en`): the scene correction «sa amie» → «son» was filed
under «Un, une, des» (every determiner swap became the family word «determiner»,
and the family's first concept won), so the Cahier showed articles «shaky» and day
2 drilled them while «Mon, ma, mes» stayed «not met yet» (#974). The same night a
Courrier spelling slip «cafe → café» was filed under the letter's rule, «Passé
composé with avoir», and recall printed that rule over it (#697).

The guard below feeds the issue's exact pairs through every record path (a scene
correction, a Courrier erratum, a La Forge attempt), each lent the day's rule (the
passé composé with avoir), and asserts the rule the slip is filed under.
"""
from __future__ import annotations

import unicodedata
from uuid import uuid4

import pytest

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.error_memory import ErrorMemoryService

#: The catalogue units the pairs land on (external id, name, category, subskill, order).
_UNITS = {
    "UN_UNE": ("FR2_A11_UN_UNE", "Un, une, des: a, an, some (and gender)", "Articles", "indefinite_articles", 40),
    "LE_LA": ("FR2_A11_LE_LA", "Le, la, l', les: the", "Articles", "definite_articles", 50),
    "POSSESSIVES": ("FR2_A11_POSSESSIVES", "Mon, ma, mes: possessives", "Determiners", "possessives", 150),
    "DEMONSTRATIVES": ("FR2_A12_DEMONSTRATIVES", "Ce, cet, cette, ces", "Determiners", "demonstratives", 230),
    "ER_SPELLING": ("FR2_A12_ER_SPELLING", "-er verbs that change spelling", "Verbs", "present_er_spelling_change", 295),
    "PC_AVOIR": ("FR2_A21_PC_AVOIR", "Passé composé with avoir, regular and irregular participles", "Tenses", "passe_compose_avoir", 350),
    "PC_ETRE": ("FR2_A21_PC_ETRE", "Passé composé with être, and agreement", "Tenses", "passe_compose_etre", 360),
    "RELATIVE_OU": ("FR2_A22_RELATIVE_OU", "Relative où: the place where, the day when", "Pronouns", "relative_ou", 420),
    "CONNECTORS": ("FR2_A12_CONNECTORS", "Et, mais, ou, parce que", "Connectors", "connectors", 240),
    "POSSESSIVE_PRONOUNS": ("FR2_B11_POSSESSIVE_PRONOUNS", "Le mien, la tienne", "Pronouns", "possessive_pronouns", 520),
    "QUEL_QUE_SOIT": ("FR2_C11_QUEL_QUE_SOIT", "Quel que soit", "Clauses", "quel_que_soit", 820),
    "SUBJ_IMPARFAIT": ("FR2_C12_SUBJ_IMPARFAIT", "Subjonctif imparfait", "Moods", "subj_imparfait", 880),
    "DAYS_DATES": ("FR2_A12_DAYS_DATES", "Days, months, dates", "Time", "days_dates", 260),
    "CONTRACTIONS": ("FR2_A11_CONTRACTIONS", "Au, aux, du, des: à and de with le/les", "Articles", "contractions_au_du", 140),
}

#: The issue's pairs: (learner span, corrected span, the sentence it sat in, the rule it is filed under).
#: ``None`` is no rule; «j ai → j'ai» may also be the elision rule.
GUARD_PAIRS = [
    ("sa", "son", "Vous etes sa amie ?", {"POSSESSIVES"}),
    ("cafe", "café", "Je prends un cafe au bar.", {None}),
    ("le", "la", "Je cherche le clé.", {"LE_LA"}),
    ("a", "à", "Je dors a l'hôtel.", {None}),
    ("j ai", "j'ai", "Hier j ai vu Margaux.", {None, "LE_LA"}),
    ("ai mange", "ai mangé", "Hier soir, j ai mange une crêpe.", {"PC_AVOIR"}),
    ("est arrive", "est arrivée", "Elle est arrive hier soir.", {"PC_ETRE"}),
    # #1027: à + le melts into «au»; the letter's passé composé is not this slip's rule.
    ("a le", "au", "Apres je vais a le notaire.", {"CONTRACTIONS"}),
]


def _units(db_session) -> dict[str, GrammarConcept]:
    units: dict[str, GrammarConcept] = {}
    for key, (external_id, name, category, subskill, order) in _UNITS.items():
        unit = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one_or_none()
        if unit is None:
            unit = GrammarConcept(
                external_id=external_id, language="fr", name=name, level="A1", category=category,
                subskill=subskill, difficulty_order=order, active=True,
            )
            db_session.add(unit)
        else:
            unit.difficulty_order = order
        units[key] = unit
    db_session.commit()
    return units


def _user(db_session) -> User:
    user = User(id=uuid4(), email=f"slip-973-{uuid4().hex[:8]}@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    db_session.commit()
    return user


def _expected_ids(units: dict[str, GrammarConcept], keys: set) -> set:
    return {units[key].id if key else None for key in keys}


def _stored(db_session, user: User) -> list[UserError]:
    return db_session.query(UserError).filter(UserError.user_id == user.id).all()


def _through_scene(db_session, user, units, span, fixed, context):
    from app.services.journey_contracts import Correction, InputMode
    from app.services.journey_learning import (
        _record_correction_erratum,
        ensure_journey_learning_session,
    )

    session = ensure_journey_learning_session(db_session, user=user, journey_id=uuid4(), scenario_key="meet_family")
    _record_correction_erratum(
        db_session, user=user, session=session,
        correction=Correction(span_fr=span, corrected_fr=fixed, note_native="", context_fr=context),
        modality=InputMode.TEXT, source_key="scene-973", foreground=True,
        concept_id_hint=units["PC_AVOIR"].id,
    )


def _letters(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if c.isalpha())


def _through_courrier(db_session, user, units, span, fixed, context):
    _through_courrier_lent(db_session, user, units["PC_AVOIR"].id, span, fixed, context)


def _through_courrier_lent(db_session, user, lent_id, span, fixed, context):
    from app.services.missions import MissionCorrectionService
    from tests.test_missions import _ExplodingMissionLLM, _mission_for_correction

    mission = _mission_for_correction()
    mission.user_id = user.id
    mission.selected_concept_ids = [lent_id]  # the letter's rule
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())
    # The basic check files an accent or apostrophe fix as spelling, with no rule id.
    accent_only = _letters(span) == _letters(fixed)
    erratum = service._normalize_erratum(
        {
            "learner_text": span,
            "corrected_target": fixed,
            "why_wrong": "Une reprise.",
            "external_id": "",
            "task_error_type": "grammar_target",
            "error_category": "spelling" if accent_only else "grammar",
        },
        mission,
        submission_text=context,
    )
    service.persist_errata(
        user=user, mission=mission, correction={"errata": [erratum]}, mode="letter", source_id="letter-973"
    )


def _through_forge(db_session, user, units, span, fixed, context):
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="active", quote_payload={}, recap_payload={})
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=units["PC_AVOIR"].id,  # the séance's rule
        round="production",
        mode="free",
        exercise_id="FR2_A21_PC_AVOIR:production:free-973",
        prompt_payload={"mode": "free", "items": [{"id": "free-973", "type": "free", "prompt": "Raconte ta soirée."}]},
        answer_payload={"answers": {"free-973": context}},
        correction_payload={
            "verdict": "partial",
            "errata": [
                {
                    "item_id": "",
                    "display_label": "Reprise",
                    "learner_text": span,
                    "corrected_target": fixed,
                    "why_wrong": "Une reprise.",
                    "repair_hint": "",
                    "severity": 2,
                    "recurring": True,
                    "task_error_type": "grammar_target",
                }
            ],
        },
        verdict="partial",
        score_0_4=2.0,
    )
    db_session.add(attempt)
    db_session.flush()
    ErrorMemoryService(db_session).record_atelier_attempt(user=user, attempt=attempt)


_PATHS = {"scene": _through_scene, "courrier": _through_courrier, "forge": _through_forge}


@pytest.mark.parametrize("path", sorted(_PATHS))
def test_guard(db_session, path):
    """Every record path files the slip under what the correction changed."""
    units = _units(db_session)
    wrong: list[str] = []
    for span, fixed, context, keys in GUARD_PAIRS:
        user = _user(db_session)
        _PATHS[path](db_session, user, units, span, fixed, context)
        db_session.flush()
        rows = _stored(db_session, user)
        if not rows:
            wrong.append(f"«{span} → {fixed}» was not recorded at all")
            continue
        filed = {row.concept_id for row in rows}
        if not filed <= _expected_ids(units, keys):
            names = {row.concept_id: (row.concept.name if row.concept else None) for row in rows}
            wrong.append(f"«{span} → {fixed}» filed under {sorted(names.values(), key=str)}, expected {sorted(keys, key=str)}")
    assert not wrong, f"{path} (day rule: passé composé with avoir):\n" + "\n".join(wrong)


# ---------------------------------------------------------------------------
# #974: «sa amie» → «son» is a possessive slip, not «Un, une, des»
# ---------------------------------------------------------------------------

WALK_REPLY = (
    "Non, pas ce soir. Je dors a l hotel. Pourquoi elle ne donnait jamais la cle ? "
    "Vous etes sa amie ? Demain je vais visiter l appartement avec mon frere."
)


def test_possessive_swap(db_session):
    """A possessive swap is the possessives rule; an article swap stays the articles."""
    units = _units(db_session)
    memory = ErrorMemoryService(db_session)
    note = "Before a vowel, «sa» becomes «son»."
    assert memory.infer_concept_id_for_correction(learner_text="sa", corrected_text="son", note=note) == units["POSSESSIVES"].id
    assert memory.infer_concept_id_for_correction(learner_text="sa amie", corrected_text="son amie", note="") == units["POSSESSIVES"].id
    assert memory.infer_concept_id_for_correction(learner_text="le", corrected_text="la", note="") == units["LE_LA"].id
    assert memory.infer_concept_id_for_correction(learner_text="un", corrected_text="une", note="") == units["UN_UNE"].id
    assert memory.infer_concept_id_for_correction(learner_text="ce", corrected_text="cette", note="") == units["DEMONSTRATIVES"].id


def test_walk_reply_974(db_session):
    """The walk's scene reply files «sa → son» under the possessives."""
    from app.services.journey_contracts import Correction, InputMode
    from app.services.journey_learning import (
        _record_correction_erratum,
        ensure_journey_learning_session,
    )

    units = _units(db_session)
    user = _user(db_session)
    session = ensure_journey_learning_session(db_session, user=user, journey_id=uuid4(), scenario_key="meet_family")
    _record_correction_erratum(
        db_session, user=user, session=session,
        correction=Correction(span_fr="sa", corrected_fr="son", note_native="", context_fr=WALK_REPLY),
        modality=InputMode.TEXT, source_key="scene-974", foreground=True,
    )
    row = db_session.query(UserError).filter_by(user_id=user.id).one()
    assert row.concept_id == units["POSSESSIVES"].id, f"filed under {row.concept.name if row.concept else None}"


# ---------------------------------------------------------------------------
# The lent rule keeps a slip that is its own form (reviews of #734 and #759)
# ---------------------------------------------------------------------------


def test_own_form_kept(db_session):
    """A lent rule keeps the accent that is its own form."""
    units = _units(db_session)
    memory = ErrorMemoryService(db_session)
    er_spelling = units["ER_SPELLING"].id
    for span, fixed in (("je les achete", "je les achète"), ("je la leve", "je la lève"), ("j'achete", "j'achète")):
        user = _user(db_session)
        memory.record_erratum(
            user=user,
            erratum={"learner_text": span, "corrected_target": fixed, "why_wrong": "x", "error_category": "spelling"},
            source_type="graphic_novel",
            concept_id=er_spelling,
        )
        assert {row.concept_id for row in _stored(db_session, user)} == {er_spelling}, span
    # A rule the corrector named is never dropped, whatever the change looks like.
    user = _user(db_session)
    memory.record_erratum(
        user=user,
        erratum={"learner_text": "j'achete", "corrected_target": "j'achète", "why_wrong": "x", "concept_id": er_spelling},
        source_type="graphic_novel",
        concept_id=er_spelling,
    )
    assert {row.concept_id for row in _stored(db_session, user)} == {er_spelling}


#: Review of #978: an accent, apostrophe, space or capital that is the lent rule's
#: own form keeps that rule (lent unit, learner span, corrected span, sentence).
OWN_FORM_PAIRS = [
    ("RELATIVE_OU", "le bar ou on", "le bar où on", "C'est le bar ou on s'est vus."),
    ("ER_SPELLING", "nous commencons", "nous commençons", "Demain nous commencons à huit heures."),
    ("ER_SPELLING", "nous achètons", "nous achetons", "Le samedi, nous achètons du pain."),
    ("CONNECTORS", "du thé où du café", "du thé ou du café", "Tu veux du thé où du café ?"),
    ("POSSESSIVE_PRONOUNS", "la votre", "la vôtre", "C'est notre voiture, pas la votre."),
    ("QUEL_QUE_SOIT", "Quelque soit", "Quel que soit", "Quelque soit le prix, je l'achète."),
    ("SUBJ_IMPARFAIT", "qu'il fut", "qu'il fût", "Il fallait qu'il fut là."),
    ("DAYS_DATES", "Lundi 3 Mars", "lundi 3 mars", "Le rendez-vous est Lundi 3 Mars."),
]


@pytest.mark.parametrize(
    "lent, span, fixed, context", OWN_FORM_PAIRS, ids=[f"{pair[0]}:{pair[1]}" for pair in OWN_FORM_PAIRS]
)
def test_own_form_lent(db_session, lent, span, fixed, context):
    """An accent-only slip in the lent rule's own form keeps that rule, on every record path."""
    from app.services.answer_acceptance import is_real_correction
    from app.services.journey_contracts import Correction, InputMode
    from app.services.journey_learning import (
        _record_correction_erratum,
        ensure_journey_learning_session,
    )

    units = _units(db_session)
    memory = ErrorMemoryService(db_session)
    lent_id = units[lent].id
    if not is_real_correction(span, fixed):
        # A capital alone is never saved as an error (#93); the decision still holds.
        got = memory.concept_for_slip(span, fixed, lent_concept_id=lent_id, context=context)
        assert got == lent_id, f"«{span} → {fixed}» with {lent} lent: filed under {got}"
        return

    # The scene: the step's rule is lent through ``concept_id_hint``.
    user = _user(db_session)
    session = ensure_journey_learning_session(db_session, user=user, journey_id=uuid4(), scenario_key="meet_family")
    _record_correction_erratum(
        db_session, user=user, session=session,
        correction=Correction(span_fr=span, corrected_fr=fixed, note_native="", context_fr=context),
        modality=InputMode.TEXT, source_key="scene-own-form", foreground=True, concept_id_hint=lent_id,
    )
    db_session.flush()
    assert {row.concept_id for row in _stored(db_session, user)} == {lent_id}, f"scene: «{span} → {fixed}»"

    # La Forge / the Feuilleton: a free-text erratum lent the séance's rule.
    user = _user(db_session)
    memory.record_erratum(
        user=user,
        erratum={"learner_text": span, "corrected_target": fixed, "why_wrong": "x", "context_fr": context},
        source_type="graphic_novel",
        concept_id=lent_id,
    )
    assert {row.concept_id for row in _stored(db_session, user)} == {lent_id}, f"forge: «{span} → {fixed}»"


def test_own_form_courrier(db_session):
    """A letter lent the relative où keeps «le bar ou → où» under it."""
    units = _units(db_session)
    user = _user(db_session)
    _through_courrier_lent(
        db_session, user, units["RELATIVE_OU"].id, "le bar ou on", "le bar où on", "C'est le bar ou on s'est vus."
    )
    db_session.flush()
    assert {row.concept_id for row in _stored(db_session, user)} == {units["RELATIVE_OU"].id}


def test_accent_outside_lent_form(db_session):
    """The same rules lent, an accent that is not their form still carries no rule."""
    units = _units(db_session)
    memory = ErrorMemoryService(db_session)
    for lent, span, fixed, context in (
        ("RELATIVE_OU", "cafe", "café", "On boit un cafe au bar où on s'est vus."),
        ("ER_SPELLING", "les eleves", "les élèves", "Nous achetons des livres pour les eleves."),
        ("PC_AVOIR", "a", "à", "J'ai mangé a la maison."),
        ("PC_AVOIR", "cafe", "café", "J'ai bu un cafe."),
        ("DAYS_DATES", "tres", "très", "Lundi 3 mars, il fait tres froid."),
    ):
        user = _user(db_session)
        memory.record_erratum(
            user=user,
            erratum={"learner_text": span, "corrected_target": fixed, "why_wrong": "x", "context_fr": context},
            source_type="graphic_novel",
            concept_id=units[lent].id,
        )
        filed = {row.concept_id for row in _stored(db_session, user)}
        assert filed == {None}, f"«{span} → {fixed}» with {lent} lent: filed under {filed}"


def test_journal_slip(db_session):
    """A journal erratum (no rule lent) is filed under what its correction changed."""
    units = _units(db_session)
    memory = ErrorMemoryService(db_session)
    for span, fixed, expected in (
        ("sa amie", "son amie", units["POSSESSIVES"].id),
        ("ai mange", "ai mangé", units["PC_AVOIR"].id),
        ("cafe", "café", None),
    ):
        user = _user(db_session)
        memory.record_erratum(
            user=user,
            erratum={
                "display_label": "Correction", "learner_text": span, "corrected_target": fixed,
                "why_wrong": "", "severity": 2, "recurring": True, "task_error_type": "grammar_target",
            },
            source_type="journal",
            source_payload={"surface": "journal"},
        )
        assert {row.concept_id for row in _stored(db_session, user)} == {expected}, span


def test_accent_no_rule(db_session):
    """An accent outside the lent rule carries no rule."""
    units = _units(db_session)
    memory = ErrorMemoryService(db_session)
    for span, fixed in (
        ("les eleves", "les élèves"),
        ("la regle", "la règle"),
        ("la peinture est seche", "la peinture est sèche"),
        ("A bientot", "A bientôt"),
        ("tres", "très"),
        ("c est", "c'est"),
    ):
        user = _user(db_session)
        memory.record_erratum(
            user=user,
            erratum={"learner_text": span, "corrected_target": fixed, "why_wrong": "x", "error_category": "spelling"},
            source_type="graphic_novel",
            concept_id=units["PC_AVOIR"].id,
        )
        assert {row.concept_id for row in _stored(db_session, user)} == {None}, span


# ---------------------------------------------------------------------------
# #697: a Courrier accent slip carries no rule into recall, and its repair credits none
# ---------------------------------------------------------------------------


def test_recall_697(db_session):
    """A letter's accent slip reaches recall with no rule and moves no rule's schedule."""
    import json
    from datetime import UTC, datetime, timedelta

    from app.db.models.grammar import UserGrammarProgress
    from app.services.journey_contracts import EvidenceKind, StepKind, TargetKind
    from app.services.journey_errata import errata_targets_for_user
    from app.services.journey_learning import _apply_error_credit
    from app.services.journey_planner import plan_journey
    from app.services.missions import MissionCorrectionService
    from tests.test_journey_planner import _brief
    from tests.test_missions import _ExplodingMissionLLM, _mission_for_correction

    units = _units(db_session)
    pc_avoir = units["PC_AVOIR"]
    user = _user(db_session)
    user.native_language, user.target_language = "en", "fr"
    due_at = datetime.now(UTC) + timedelta(days=1)
    reviewed_at = datetime.now(UTC) - timedelta(days=2)
    progress = UserGrammarProgress(
        user_id=user.id, concept_id=pc_avoir.id, notes="[daily_journey] seen", last_review=reviewed_at, next_review=due_at
    )
    db_session.add(progress)
    db_session.commit()

    mission = _mission_for_correction()
    mission.user_id = user.id
    mission.selected_concept_ids = [pc_avoir.id]  # the letter practises the passé composé
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())
    correction = service.correct_submission(
        user=user, mission=mission, text="Salut Marin, hier j'ai mangé une crêpe. A bientot, Sam",
        mode="letter", near_realtime=True,
    )
    service.persist_errata(user=user, mission=mission, correction=correction, mode="letter", source_id="letter-697")
    db_session.flush()
    row = next(r for r in _stored(db_session, user) if "bient" in (r.original_text or ""))
    assert row.concept_id is None, f"«bientot → bientôt» filed under {row.concept.name if row.concept else None}"

    row.next_review_date = datetime.now(UTC) - timedelta(days=1)  # due, as on day 2
    db_session.flush()
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    plan = plan_journey(scenario=_brief(control_language="en"), candidates=[], errata_targets=targets)
    repairs = [
        step for step in plan.steps
        if step.kind is StepKind.RECALL and step.target is not None and step.target.kind is TargetKind.ERROR
        and step.target.id == str(row.id)
    ]
    assert repairs, "the stored slip was not planned as a repair"
    shown = json.dumps(repairs[0].public_prompt, ensure_ascii=False)
    assert "Rule:" not in shown and pc_avoir.name not in shown, shown

    _apply_error_credit(
        db_session, user=user, target=repairs[0].target, evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
        now=datetime.now(UTC),
    )
    db_session.flush()
    db_session.refresh(progress)
    assert progress.notes == "[daily_journey] seen"
    assert progress.last_review.replace(tzinfo=UTC) == reviewed_at
    assert progress.next_review.replace(tzinfo=UTC) == due_at


# ---------------------------------------------------------------------------
# #1027: one row per distinct change; a row's rule is its own change's
# ---------------------------------------------------------------------------

#: The walk's letter to Margaux, 23 Nov 2026 (`a2-en`, day 1 Courrier).
WALK_LETTER_1027 = (
    "Salut Margaux ! Non, j ai pas d echarpe ici, j ai oublie mon echarpe a Leeds. Peut-etre c est a Gus ? "
    "Je passe demain a huit heures, je ne vais pas ailleurs. Apres je vais a le notaire. Merci pour le cafe !"
)


def _fold(text: object) -> str:
    return " ".join(str(text or "").casefold().split())


def _change(row: UserError) -> tuple[str, str]:
    return _fold(row.original_text), _fold(row.correction)


def _letter_1027(db_session, units, user):
    """The walk's letter, corrected by the basic check and saved as the Courrier saves it."""
    from app.services.missions import MissionCorrectionService
    from tests.test_missions import _ExplodingMissionLLM, _mission_for_correction

    mission = _mission_for_correction()
    mission.user_id = user.id
    # The letter's rules, as the walk's `selected_concept_ids [39, 40, 41]`: the passé composé first.
    mission.selected_concept_ids = [units["PC_AVOIR"].id, units["PC_ETRE"].id, units["LE_LA"].id]
    service = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM())
    correction = service.correct_submission(
        user=user, mission=mission, text=WALK_LETTER_1027, mode="letter", near_realtime=True
    )
    service.persist_errata(user=user, mission=mission, correction=correction, mode="letter", source_id="letter-1027")
    db_session.flush()
    return correction


def test_walk_letter_1027(db_session):
    """Each fix of the walk's letter is its own slip, filed under its own change."""
    units = _units(db_session)
    user = _user(db_session)
    correction = _letter_1027(db_session, units, user)
    listed = {(_fold(e["learner_text"]), _fold(e["corrected_target"])) for e in correction["errata"]}
    assert {("cafe", "café"), ("d echarpe", "d'écharpe"), ("a le", "au"), ("apres", "après")} <= listed, listed

    rows = _stored(db_session, user)
    changes = [_change(row) for row in rows]
    assert sorted(changes) == sorted(listed), (
        f"{len(listed)} distinct fixes listed, saved as {len(rows)} rows: "
        + "; ".join(f"«{r.original_text} → {r.correction}» ×{r.occurrences}" for r in rows)
    )
    for row in rows:
        assert (row.occurrences, row.lapses) == (1, 0), f"«{row.original_text}» ×{row.occurrences}, {row.lapses} lapses"
    by_change = {_change(row): row for row in rows}
    assert by_change[("a le", "au")].concept_id == units["CONTRACTIONS"].id, (
        f"«a le → au» filed under {by_change[('a le', 'au')].concept_id}"
    )
    for change, row in by_change.items():
        if change != ("a le", "au"):
            assert row.concept_id is None, f"«{row.original_text} → {row.correction}» filed under rule {row.concept_id}"

    # The same letter again: each slip recurs once, on its own row.
    _letter_1027(db_session, units, user)
    again = _stored(db_session, user)
    assert sorted((_change(row), row.occurrences) for row in again) == sorted((change, 2) for change in changes)


def test_recall_walk_letter_697(db_session):
    """Day 2 recalls the letter's «cafe» with no rule line."""
    import json
    from datetime import UTC, datetime, timedelta

    from app.services.journey_contracts import StepKind, TargetKind
    from app.services.journey_errata import errata_targets_for_user
    from app.services.journey_planner import plan_journey
    from tests.test_journey_planner import _brief

    units = _units(db_session)
    user = _user(db_session)
    user.native_language, user.target_language = "en", "fr"
    _letter_1027(db_session, units, user)
    cafe = next(row for row in _stored(db_session, user) if _change(row) == ("cafe", "café"))
    assert cafe.concept_id is None, f"«cafe → café» filed under {cafe.concept.name if cafe.concept else None}"
    for row in _stored(db_session, user):
        row.next_review_date = datetime.now(UTC) + timedelta(days=5)
    cafe.next_review_date = datetime.now(UTC) - timedelta(days=1)  # due, as on day 2
    db_session.flush()
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    plan = plan_journey(scenario=_brief(control_language="en"), candidates=[], errata_targets=targets)
    repairs = [
        step for step in plan.steps
        if step.kind is StepKind.RECALL and step.target is not None and step.target.kind is TargetKind.ERROR
        and step.target.id == str(cafe.id)
    ]
    assert repairs, "«cafe» was not planned as a repair"
    shown = json.dumps(repairs[0].public_prompt, ensure_ascii=False)
    assert "Rule:" not in shown and units["PC_AVOIR"].name not in shown, shown


def test_two_accents_two_rows(db_session):
    """Two different accent fixes are two slips on every record path, and share no rule."""
    units = _units(db_session)
    for path in sorted(_PATHS):
        user = _user(db_session)
        _PATHS[path](db_session, user, units, "cafe", "café", "Merci pour le cafe et le the.")
        _PATHS[path](db_session, user, units, "Apres", "Après", "Apres je vais au notaire.")
        db_session.flush()
        rows = _stored(db_session, user)
        assert sorted(_change(row) for row in rows) == [("apres", "après"), ("cafe", "café")], (
            f"{path}: " + "; ".join(f"«{r.original_text}» ×{r.occurrences}" for r in rows)
        )
        assert {row.concept_id for row in rows} == {None}, path


def test_old_row_lends_no_rule(db_session):
    """A rule-less row saved before slips were keyed by their change reopens only for
    that same change, and never takes another slip's rule (WP-L1's legacy key)."""
    units = _units(db_session)
    memory = ErrorMemoryService(db_session)
    user = _user(db_session)
    old = UserError(
        user_id=user.id, original_text="cafe", correction="café", error_category="spelling",
        error_pattern="orthography", task_error_type="orthography", display_label="Spelling",
        memory_key="spelling:concept-none:orthography:spelling", occurrences=1, lapses=0, state="open",
    )
    db_session.add(old)
    db_session.flush()
    spelling = {"why_wrong": "x", "task_error_type": "orthography", "display_label": "Spelling"}
    memory.record_erratum(
        user=user, erratum={**spelling, "learner_text": "a le", "corrected_target": "au"},
        source_type="mission", concept_id=units["PC_AVOIR"].id,
    )
    memory.record_erratum(
        user=user, erratum={**spelling, "learner_text": "Apres", "corrected_target": "Après"}, source_type="mission"
    )
    db_session.flush()
    db_session.refresh(old)
    assert (old.original_text, old.concept_id, old.occurrences) == ("cafe", None, 1), (
        f"the old «cafe» row became «{old.original_text}», rule {old.concept_id}, ×{old.occurrences}"
    )
    memory.record_erratum(
        user=user, erratum={**spelling, "learner_text": "cafe", "corrected_target": "café"}, source_type="mission"
    )
    db_session.flush()
    db_session.refresh(old)
    assert old.occurrences == 2, "the same change reopens the row it was saved on"
    assert len(_stored(db_session, user)) == 3
