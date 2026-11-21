"""P3 after the second walk (18 Nov, B1 «Sarah», `walk2-integration-b1.md`).

Read from the walk's database and server log (no model call here, fake tutor answers):

* **Day 4, no correction all day.** The stored turns carry ``correction: null`` three
  times; the lane ran each time (no error, no timeout). Two guards drop the subjunctive
  corrections a B1 learner needs, whatever note the tutor writes:
  - «que tu me dis» → «que tu me dises»: ``gender_only_change`` reads «dis» → «dises»
    as a feminine-plural «-es» ending and drops it as the learner's own gender;
  - «qu'il ne veut» → «qu'il ne veuille» with the note «Après « avoir peur que », on
    emploie le subjonctif.»: ``note_quotes_hold`` (#250/#772) calls «avoir peur que» a
    quote the learner never wrote (she wrote «J'ai peur qu'il»), the #93 rewrite puts
    «La forme correcte est « … ».» in its place, and P3's restating-note check drops it.
  Day 3 (R3 «que Camille a raison») and day 6 (R2 «que tu me dis») lost the same two.
* **Day 5, a wrong correction.** «Alors je lui dirai que …» (right: a plan) became «je lui
  ai dit»: ``verify_edit`` settles it because the result is French. A change of tense or
  mood now needs evidence in the learner's own sentence.
"""

from __future__ import annotations

import pytest

from app.services import correction_contract
from app.services import story_lanes as lanes
from app.services.tense_change import changed_tenses, unsupported_tense_change

D3_R3 = (
    "Non, je ne sais pas. Quand je suis arrivée, Margaux lui a déjà dit de partir, je crois, "
    "et j'ai peur que Camille a raison. Demain, je veux parler à Gus de la clé."
)
D4_R1 = (
    "Je vais mieux, merci. Quand Lila est partie, j'ai déjà mangé un sandwich, alors je ne veux "
    "pas de soupe. Je suis fatigué, mais je lui parlerai demain."
)
D4_R2 = (
    "Je veux lui demander pourquoi Odile m'a laissé la clé. Quand je suis arrivée au café hier, il a "
    "déjà quitté sa place, et je n'ai pas pu lui parler. J'ai peur qu'il ne veut jamais me répondre."
)
D4_R3 = (
    "Parce qu'il change toujours de sujet. Avant ton arrivée, j'ai déjà décidé de ne pas vendre, alors "
    "viens avec moi demain et je lui poserai la question devant tout le monde. Je veux que tu me dis si "
    "tu as peur de lui."
)
D5_R1 = (
    "Je lui ai dit que ma radiateur ne marchait pas, et que je devais rester. Quand j'ai appelé, il pleut "
    "dehors et j'ai déjà perdu mon parapluie."
)
D5_R3 = (
    "Alors je lui dirai que Camille a déjà me proposé de l'argent. Quand je suis arrivée au Mistral, il "
    "pleuvait et j'ai oublié mon parapluie, mais ce n'est pas important."
)


def _payload(text: str) -> dict:
    return {
        "learner_text": text,
        "history": [],
        "scene": {},
        "story": {"learner": {"address": "neutral"}, "level": "B1", "commitments": [], "control_language": "fr"},
        "targets": [],
        "turn_plan": {},
    }


def _fix(span: str, corrected: str, note: str) -> dict:
    return {"span_fr": span, "corrected_fr": corrected, "note_native": note}


def _kept(text: str, *corrections: dict) -> list[tuple[str, str]]:
    verdict = lanes.TutorVerdict.model_validate(
        {"outcome": "partially_met", "evidence_quotes": [], "corrections": list(corrections)}
    )
    lanes.validate_tutor(verdict, _payload(text))
    return [(c.span_fr, c.corrected_fr) for c in verdict.corrections]


# ---------------------------------------------------------------------------
# Day 4: the tutor's corrections survive the guards
# ---------------------------------------------------------------------------

#: The day-4 replies with the corrections a tutor writes for them (the plus-que-parfait
#: of day 3's rule, the subjunctive), and the notes as it words them.
DAY4 = [
    (
        D4_R1,
        _fix(
            "j'ai déjà mangé",
            "j'avais déjà mangé",
            "Le repas a eu lieu avant le départ de Lila : le plus-que-parfait marque cette antériorité.",
        ),
    ),
    (
        D4_R2,
        _fix(
            "il a déjà quitté",
            "il avait déjà quitté",
            "Pour une action antérieure à un autre moment passé, on emploie le plus-que-parfait.",
        ),
    ),
    (D4_R2, _fix("qu'il ne veut", "qu'il ne veuille", "Après « avoir peur que », on emploie le subjonctif.")),
    (
        D4_R3,
        _fix(
            "j'ai déjà décidé",
            "j'avais déjà décidé",
            "La décision est antérieure à ton arrivée ; le plus-que-parfait marque cette antériorité.",
        ),
    ),
    (D4_R3, _fix("que tu me dis", "que tu me dises", "Après « vouloir que », on emploie le subjonctif.")),
    (D4_R3, _fix("Je veux que tu me dis", "Je veux que tu me dises", "Après un verbe de volonté, le subjonctif.")),
    (D3_R3, _fix("que Camille a raison", "que Camille ait raison", "Après « avoir peur que », on emploie le subjonctif.")),
]


@pytest.mark.parametrize(("text", "fix"), DAY4, ids=[f"{f['span_fr']}" for _t, f in DAY4])
def test_a_day4_correction_reaches_the_learner(text, fix):
    assert _kept(text, fix) == [(fix["span_fr"], fix["corrected_fr"])]


def test_the_note_keeps_its_rule_when_it_names_the_construction_by_its_infinitive():
    note = "Après « avoir peur que », on emploie le subjonctif."
    assert correction_contract.note_for_form("qu'il ne veut", "qu'il ne veuille", note, language="fr", context=D4_R2) == note
    note = "Après « vouloir que », on emploie le subjonctif."
    assert correction_contract.note_for_form("que tu me dis", "que tu me dises", note, language="fr", context=D4_R3) == note


def test_a_day4_reply_with_two_errors_keeps_both():
    assert _kept(D4_R3, DAY4[3][1], DAY4[4][1]) == [
        ("j'ai déjà décidé", "j'avais déjà décidé"),
        ("que tu me dis", "que tu me dises"),
    ]


def test_an_invented_quote_is_still_rewritten():
    """#250/#772 stay: a quote the learner did not write, and no verb of hers named."""

    note = "Après « avoir envie que », on emploie le subjonctif."
    assert correction_contract.note_for_form("qu'il ne veut", "qu'il ne veuille", note, language="fr", context=D4_R2) != note
    note = "Avec « tu », le verbe prend -s."
    assert correction_contract.note_for_form("est", "es", note, language="fr", context="Ma grand-mère est mort.") != note


@pytest.mark.parametrize(
    ("text", "span", "corrected"),
    [
        ("Je suis fatigué, mais je lui parlerai demain.", "fatigué", "fatiguée"),
        ("Je suis perdu.", "perdu", "perdue"),
        ("Je suis contente.", "contente", "content"),
    ],
)
def test_the_learners_own_gender_is_still_never_corrected(text, span, corrected):
    assert _kept(text, _fix(span, corrected, "Le participe s'accorde avec le sujet.")) == []


# ---------------------------------------------------------------------------
# Day 5: a correct tense is never changed without evidence
# ---------------------------------------------------------------------------

#: Corrections that change a correct tense or mood. Each one is dropped.
WRONG_TENSE_SWAPS = [
    (
        D5_R3,
        "je lui dirai",
        "je lui ai dit",
        "Tu racontes la raison que tu as déjà donnée à l'agent, donc il faut le passé composé plutôt que le futur.",
    ),
    ("Je pars à huit heures.", "Je pars", "Je partirai", "Pour une action à venir, on emploie le futur."),
    ("Je mange une pomme.", "Je mange", "J'ai mangé", "Pour une action terminée, on emploie le passé composé."),
    ("Je pense qu'il vient.", "qu'il vient", "qu'il vienne", "Après « que », on emploie le subjonctif."),
]


@pytest.mark.parametrize(("text", "span", "corrected", "note"), WRONG_TENSE_SWAPS, ids=[s for _t, s, _c, _n in WRONG_TENSE_SWAPS])
def test_a_tense_swap_the_sentence_does_not_ask_for_is_dropped(text, span, corrected, note):
    assert changed_tenses(span, corrected)
    assert unsupported_tense_change(text, span, corrected)
    assert _kept(text, _fix(span, corrected, note)) == []


#: Real tense and mood errors of the walk, each with its evidence in the sentence.
RIGHT_TENSE_FIXES = [
    (D5_R1, "il pleut", "il pleuvait"),  # «Quand j'ai appelé»: the décor of a past
    (D5_R1, "j'ai déjà perdu", "j'avais déjà perdu"),
    ("Quand je suis arrivée, mon frère a déjà réservé le billet.", "a déjà réservé", "avait déjà réservé"),
    ("Quand je suis arrivée au café, il est déjà parti.", "il est déjà parti", "il était déjà parti"),
    ("Oui, si je le trouvera au café.", "si je le trouvera", "si je le trouve"),
    ("Il faut que Gus vient ce soir.", "Il faut que Gus vient", "Il faut que Gus vienne"),
    ("Je voudrais que tu reviens avant que je prends le train.", "avant que je prends", "avant que je prenne"),
    ("Avant son offre, j'ai déjà décidé de garder le Mistral.", "j'ai déjà décidé", "j'avais déjà décidé"),
    ("Hier, je mange une pomme.", "je mange", "j'ai mangé"),
    ("Demain je pars à huit heures.", "je pars", "je partirai"),
]


@pytest.mark.parametrize(("text", "span", "corrected"), RIGHT_TENSE_FIXES, ids=[s for _t, s, _c in RIGHT_TENSE_FIXES])
def test_a_tense_fix_the_sentence_asks_for_stands(text, span, corrected):
    assert not unsupported_tense_change(text, span, corrected)


@pytest.mark.parametrize(
    ("span", "corrected"),
    [("ils m'a dit", "ils m'ont dit"), ("fatigué", "fatiguée"), ("parler", "parlé"), ("un lettre", "une lettre")],
)
def test_a_fix_that_keeps_the_tense_is_not_a_tense_change(span, corrected):
    assert changed_tenses(span, corrected) == []


# ---------------------------------------------------------------------------
# The Courrier's corrector is told the same rules (walk 2: the plus-que-parfait of
# day 3 passed four letters in a row)
# ---------------------------------------------------------------------------


def test_the_courrier_corrector_is_told_the_days_rules(db_session, monkeypatch):
    import json
    from uuid import uuid4

    from app.db.models.user import User
    from app.services import day_rules
    from app.services.llm_service import LLMResult
    from app.services.missions import MissionCorrectionService
    from tests.test_missions import _mission_for_correction

    rules = {
        "today": None,
        "recent": [{"id": "FR2_B11_PLUS_QUE_PARFAIT", "name": "Le plus-que-parfait", "rule": "had done", "detectors": ["x"]}],
    }
    asked: list[dict] = []
    monkeypatch.setattr(day_rules, "for_turn", lambda db, user, **kwargs: rules)

    class _Corrector:
        def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            asked.append({"payload": json.loads(messages[0]["content"]), "system": kwargs.get("system_prompt")})
            body = {"verdict": "accepted", "score_0_4": 4, "corrected_answer": "", "errata": []}
            return LLMResult(provider="stub", model="stub", content=json.dumps(body), prompt_tokens=1,
                             completion_tokens=1, total_tokens=2, cost=0, raw_response={})

    user = User(id=uuid4(), email="p3-courrier@example.com", hashed_password="x", proficiency_level="B1",
                native_language="en")
    MissionCorrectionService(db_session, llm_service=_Corrector()).correct_submission(
        user=user, mission=_mission_for_correction(),
        text="Quand j'ai envoyé le papier ce matin, j'ai déjà corrigé l'adresse.", mode="chat",
    )
    assert asked, "the corrector was asked"
    # The rules as the tutor reads them: id, name and rule, never the app's own detectors.
    assert asked[0]["payload"]["rules"] == {
        "today": None,
        "recent": [{"id": "FR2_B11_PLUS_QUE_PARFAIT", "name": "Le plus-que-parfait", "rule": "had done"}],
    }
    assert "rules, when present, is what this learner is being taught" in asked[0]["system"]
