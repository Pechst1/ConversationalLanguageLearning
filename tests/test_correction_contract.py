"""#250: one corrector contract for the scene reply, the Courrier and the Journal.

The corrector's output used to be trusted as-is and a failure was a dead-end line.
These tests feed the exact sentences from the 20 Oct live walk (#193, #251, #252) and
the rule that would have caught them: an edit is accepted only when it is about the
learner's sentence, and a model-free pass finds the real mistakes when the model
fails or is rejected. No model call is made anywhere in this file.
"""

from __future__ import annotations

import re

import pytest

from app.services import living_story as engine
from app.services import story_lanes as lanes

ODILE = "Odile est parti parce que la restaurant était très difficile."
EST_CE_QUE = "Mais est-ce que le gâteau est pour le chat ?"
EST_CE_QUE_WRONG = "Mais est-ce que la gâteau est pour le chat ?"
SONNE = "Je vais sonné la cloche et je vend le gâteau."
JOURNAL = (
    "Hier, Marin Lévêque a donné une bouillotte à Lila. Gus dit qu’il est comte, mais il a "
    "un scooter. Lila a rentré dans le café et elle mange un croissant."
)
TU_NOTE = "With « tu », « est » must be « es »"


def _contract():
    from app.services import correction_contract

    return correction_contract


def _payload(learner_text: str) -> dict:
    return {
        "learner_text": learner_text,
        "history": [],
        "scene": {},
        "story": {"learner": {"address": "neutral"}, "level": "A2", "commitments": [], "control_language": "en"},
        "targets": [],
        "turn_plan": {},
    }


def _pairs(edits):
    return {(e.span, e.replacement) for e in edits}


# ---------------------------------------------------------------------------
# the three 20 Oct sentences: no «tu / es», the real errors present, spans in the input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sentence", [ODILE, EST_CE_QUE, EST_CE_QUE_WRONG, SONNE, JOURNAL])
def test_no_edit_ever_turns_est_into_es_and_every_span_is_in_the_sentence(sentence):
    contract = _contract()
    edits = contract.deterministic_edits(sentence)
    for edit in edits:
        assert edit.replacement.casefold() != "es", f"{edit.span!r} -> {edit.replacement!r}"
        assert edit.span in sentence
        assert sentence[edit.start : edit.end] == edit.span


def test_odile_est_parti_marks_the_real_errors_not_a_tu_es_card():
    edits = _contract().deterministic_edits(ODILE)
    pairs = _pairs(edits)
    assert ("la", "le") in pairs, "la restaurant -> le restaurant"
    assert ("parti", "partie") in pairs, "Odile is a woman in the cast: parti -> partie"
    assert not any("tu" in e.note_for("en") for e in edits)


def test_est_ce_que_is_not_a_verb_form_to_correct():
    contract = _contract()
    assert contract.deterministic_edits(EST_CE_QUE) == []
    assert _pairs(contract.deterministic_edits(EST_CE_QUE_WRONG)) == {("la", "le")}


def test_je_vais_sonne_je_vend_are_both_marked():
    pairs = _pairs(_contract().deterministic_edits(SONNE))
    assert ("sonné", "sonner") in pairs
    assert ("vend", "vends") in pairs


@pytest.mark.parametrize("sentence", [ODILE, EST_CE_QUE])
def test_the_model_est_to_es_card_is_rejected_for_a_sentence_with_no_tu(sentence):
    contract = _contract()
    assert not contract.edit_is_grounded(sentence, "est", "es", TU_NOTE)
    # without the note too: a second-person form needs a «tu» somewhere
    assert not contract.edit_is_grounded(sentence, "est", "es", None)


def test_the_scene_reply_drops_the_tu_es_card_and_shows_a_real_correction():
    """The tutor lane: the model's «est -> es» is replaced by the first real edit."""
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=[ODILE],
        correction_span_fr="est",
        correction_fr="es",
        correction_note_native=TU_NOTE,
    )
    lanes.validate_tutor(verdict, _payload(ODILE))
    assert verdict.correction_fr != "es"
    assert verdict.correction_span_fr in ODILE
    assert verdict.correction_fr in {"partie", "le"}
    assert "tu" not in (verdict.correction_note_native or "")


def test_the_scene_reply_keeps_a_grounded_model_correction():
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=["Tu est gentil."],
        correction_span_fr="est",
        correction_fr="es",
        correction_note_native="After « tu » the verb is « es ».",
    )
    lanes.validate_tutor(verdict, _payload("Tu est gentil."))
    assert (verdict.correction_span_fr, verdict.correction_fr) == ("est", "es")


def test_the_scene_turn_guard_uses_the_same_contract():
    turn = engine.SemanticTurn.model_construct(
        reply_fr="Bien sûr.",
        resolution_fr="",
        understood_intent="",
        evidence_quotes=[],
        outcome="not_yet",
        needs_clarification=True,
        correction_span_fr="est",
        correction_fr="es",
        correction_note_native=TU_NOTE,
    )
    payload = _payload(ODILE)
    engine._validate_turn(turn, payload)
    assert turn.correction_fr != "es"
    assert turn.correction_span_fr in ODILE


# ---------------------------------------------------------------------------
# the reviewer's rejection of the first #193 attempt: object pronouns are not subjects
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "span", "fix"),
    [
        ("Je lui a donné un cadeau.", "a", "ai"),
        ("Je lui est donné un cadeau.", "est", "ai"),
        ("Je vous est vu hier.", "est", "ai"),
        ("Il nous ont donné le livre.", "ont", "a"),
        ("Il vous ont parlé.", "ont", "a"),
        ("Marie et moi suis contents.", "suis", "sommes"),
        ("Toi est gentil.", "est", "es"),
        ("Tu est gentil.", "est", "es"),
    ],
)
def test_a_genuine_person_fix_is_never_dropped(sentence, span, fix):
    assert _contract().edit_is_grounded(sentence, span, fix, None)


@pytest.mark.parametrize(
    ("sentence", "span", "fix"),
    [
        ("Elle est gentille.", "est", "es"),
        ("Ma grand-mère est morte.", "est", "es"),
        ("Il est là.", "est", "suis"),
        ("Tu es gentil.", "es", "est"),
    ],
)
def test_a_form_that_is_right_for_its_subject_is_never_changed(sentence, span, fix):
    assert not _contract().edit_is_grounded(sentence, span, fix, None)


def test_a_quoted_span_that_is_not_in_the_sentence_is_rejected():
    assert not _contract().edit_is_grounded("Je suis content.", "tu es", "tu as", None)
    assert not _contract().edit_is_grounded("Je suis content.", "suis", "suis", None)


@pytest.mark.parametrize(
    "sentence",
    [
        "Je le porte tous les jours.",
        "Il la mange avec plaisir.",
        "J’ai rentré la voiture.",
        "Elle a sorti son téléphone.",
        "Vous êtes disponible jeudi matin ?",
        "Je suis fatigué et il mange.",
        "Ma grand-mère est morte.",
        "Je suis perdu ici.",
        # Night-shift review of #259, problem 1: avoir + rentré/sorti/monté/descendu/
        # retourné with a direct object is French.
        "Elle a rentré tout le linge avant la pluie.",
        "Elle a sorti cette lettre de sa poche.",
        "Il a monté ce meuble hier.",
        "Elle a sorti de l'argent.",
        "Il a sorti du pain.",
        "Nous avons monté tout le matériel.",
        "Il a retourné ce fichier.",
        "Il a descendu les escaliers.",
        "J'ai entré mon mot de passe.",
        "Ils ont monté une entreprise.",
        # Codex on #261: the direct object stands before the auxiliary as a pronoun.
        "Je l'ai sorti.",
        "Je les ai montés hier.",
        "Il en a descendu deux.",
        "Tu m'as monté la valise.",
        # Codex on #261: an acronym in capitals is not «ça».
        "Le CA se réunit demain.",
        # problem 2: a noun that is right with either gender.
        "Il fait le tour de la tour.",
        "Je vais à la poste.",
        "Il a un poste à Lyon.",
        "La mode change vite.",
        "Elle lit une page du livre.",
        "La critique est dure.",
        "Une enfant joue dans le parc.",
        "La ministre arrive demain.",
        "La propriétaire est gentille.",
        "Un crème, s'il vous plaît.",
        "Il fallait bien que quelqu'un veille sur le quartier.",
        "Pour la porte-parole du gouvernement, c'est trop cher.",
        # «le/la» as a pronoun, whatever follows it.
        "Je vais la manger ce soir.",
        "Il a décidé de le vendre.",
        "Lila le porte tous les jours.",
        "Le chat la regarde.",
        "Tu peux la goûter ?",
        # «nous/vous» after a noun is an object, not the subject.
        "Marie nous a invités.",
        "Le chef vous a appelé hier.",
        "Odile nous a donné la clé.",
        # a present after a passé composé is often right.
        "J'ai fini mes devoirs et elle regarde la télé.",
        "Hier, j'ai rencontré Paul et il habite à Lyon.",
        "J'ai vu Lila et elle aime le café.",
        # plain A1 sentences.
        "Je suis froid avec elle.",
        "Il y a un chat sur la table.",
        "C'est le café de Margaux.",
        "Nous sommes contents.",
        "Vous êtes très gentil.",
        "Je lui ai donné un cadeau.",
        "Elle est arrivée hier soir.",
        "Ils sont allés au marché.",
        "On va au cinéma ce soir.",
        "Je vais manger une pomme.",
        "Le restaurant est fermé.",
        "Ma mère est française.",
        "Mon amie Lila est là.",
    ],
)
def test_correct_french_gets_no_model_free_edit(sentence):
    assert _contract().deterministic_edits(sentence) == []


@pytest.mark.parametrize(
    ("sentence", "span", "fix"),
    [
        # The 20 Oct Journal: an être-verb with avoir before a place.
        ("Lila a rentré dans le café.", "a rentré", "est rentrée"),
        ("Il a sorti dans la rue.", "a sorti", "est sorti"),
        ("Elle a entré dans le café.", "a entré", "est entrée"),
        ("Gus a monté.", "a monté", "est monté"),
        ("Odile a parti hier.", "a parti", "est partie"),
        # gender, still caught where the noun has one gender.
        ("Odile est partie parce que la restaurant était difficile.", "la", "le"),
        ("Je mange une croissant.", "une", "un"),
        # #193 on every surface.
        ("Je suis froid.", "Je suis froid", "J'ai froid"),
        ("Ce soir je suis faim.", "je suis faim", "j'ai faim"),
        # a conjunction does not hide the subject.
        ("Mais nous est contents.", "est", "sommes"),
        # contraction, but never in front of an infinitive.
        ("Je parle de le restaurant.", "de le", "du"),
        # «ça» without its cedilla, also in a line typed in capitals.
        ("Ca va ?", "Ca", "Ça"),
        ("CA VA ?", "CA", "ÇA"),
    ],
)
def test_the_model_free_pass_still_marks_real_mistakes(sentence, span, fix):
    assert (span, fix) in _pairs(_contract().deterministic_edits(sentence))


# ---------------------------------------------------------------------------
# a model that fails or is rejected leaves the model-free corrections
# ---------------------------------------------------------------------------


def test_merge_keeps_grounded_model_edits_and_adds_the_ones_it_missed():
    contract = _contract()
    model = [
        {
            "learner_text": "la restaurant",
            "corrected_target": "le restaurant",
            "why_wrong": "restaurant is masculine",
            "task_error_type": "gender_agreement",
        },
        {"learner_text": "est", "corrected_target": "es", "why_wrong": TU_NOTE, "task_error_type": "verb_conjugation"},
    ]
    merged = contract.merge_deterministic_errata(ODILE, model, language="en")
    targets = {(e["learner_text"], e["corrected_target"]) for e in merged}
    assert ("est", "es") not in targets
    assert ("la restaurant", "le restaurant") in targets
    assert ("parti", "partie") in targets
    # the model's quote of «la restaurant» already covers the gender edit: no second card
    assert ("la", "le") not in targets


# ---------------------------------------------------------------------------
# #93: an intonation question is correct French, on every surface that corrects
# ---------------------------------------------------------------------------

INTONATION = "Vous êtes disponible jeudi matin ?"


def test_an_intonation_question_gets_no_edit_from_the_model_free_pass():
    assert _contract().deterministic_edits(INTONATION) == []


def test_the_contract_rejects_an_inversion_as_a_correction_of_an_intonation_question():
    contract = _contract()
    assert not contract.edit_is_grounded(INTONATION, INTONATION, "Êtes-vous disponible jeudi matin ?", "Inversion is required.")
    assert not contract.edit_is_grounded(
        INTONATION, "Est-ce que vous", "Êtes-vous", "Use inversion."
    )


def test_two_near_duplicate_notes_on_one_fragment_collapse_to_one():
    contract = _contract()
    text = "Mon carte est jolie."
    errata = [
        {"learner_text": "Mon carte", "corrected_target": "Ma carte", "why_wrong": "carte is feminine.", "task_error_type": "gender_agreement"},
        {"learner_text": "mon carte", "corrected_target": "ma carte", "why_wrong": "Use ma.", "task_error_type": "gender_agreement"},
    ]
    kept = contract.merge_deterministic_errata(text, errata, language="en")
    assert [item["corrected_target"] for item in kept] == ["Ma carte"]


def test_the_tutor_lane_never_corrects_the_intonation_question():
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=[INTONATION],
        correction_span_fr=INTONATION,
        correction_fr="Êtes-vous disponible jeudi matin ?",
        correction_note_native="Inversion is required in a formal question.",
    )
    lanes.validate_tutor(verdict, _payload(INTONATION))
    assert verdict.correction_span_fr is None and verdict.correction_fr is None
    assert verdict.correction_note_native is None


# ---------------------------------------------------------------------------
# #318: a replacement is never itself wrong French (le/la/de + vowel)
# ---------------------------------------------------------------------------

ELISION_LINES = [
    ("je veux vendre la appartement", "la appartement", "l'appartement"),
    ("Voici le ami de Marie.", "le ami", "l'ami"),
    ("C'est le livre de Odile.", "de Odile", "d'Odile"),
    ("La école est grande.", "La école", "L'école"),
]

_HIATUS = re.compile(r"\b(?:le|la|de|ce)\s+[aeiouéèêâîôû]\w*", re.IGNORECASE)


@pytest.mark.parametrize(("sentence", "span", "fix"), ELISION_LINES)
def test_le_la_de_before_a_vowel_is_elided(sentence, span, fix):
    pairs = _pairs(_contract().deterministic_edits(sentence))
    assert (span, fix) in pairs, f"{sentence!r} -> {sorted(pairs)}"


@pytest.mark.parametrize(
    "sentence",
    [
        "je regarde la appartement de ma grand mere",
        "cette appartement est grand",
        "le école est fermée",
        "Elle a vendu le hôtel de Odile.",
        "Il a un grand ami et une amie.",
        "le haricot, la honte, le héros et la hauteur",
    ],
)
def test_no_model_free_replacement_is_itself_flagged(sentence):
    """The guard: re-run the pass on its own output. Nothing it wrote may be flagged
    again, and no replacement may put le/la/de/ce in front of a vowel."""
    contract = _contract()
    edits = contract.deterministic_edits(sentence)
    fixed = contract.apply_edits(sentence, edits)
    again = contract.deterministic_edits(fixed)
    assert not [e for e in again if e.rule_id in {"FR_GENDER_DET", "FR_ELISION"}], (fixed, again)
    assert not _HIATUS.search(fixed), fixed


@pytest.mark.parametrize(
    "sentence",
    ["le huit mai, le onze juin et la une du journal", "le haricot, la honte, le héros et la hauteur", "Elle aime le yaourt."],
)
def test_elision_leaves_h_aspire_and_the_numbers_alone(sentence):
    assert not [e for e in _contract().deterministic_edits(sentence) if e.rule_id == "FR_ELISION"]


def test_the_validity_guard_names_an_invalid_replacement():
    from app.services.correction_contract import Edit, replacement_is_valid_french

    source = "je veux vendre la appartement"
    bad = Edit(span="la", replacement="le", rule_id="FR_GENDER_DET", label={"en": "x"}, note={"en": "x"}, start=15, end=17)
    good = Edit(span="la appartement", replacement="l'appartement", rule_id="FR_ELISION", label={"en": "x"}, note={"en": "x"}, start=15, end=29)
    assert not replacement_is_valid_french(source, bad)
    assert replacement_is_valid_french(source, good)


def test_the_scene_reply_shows_the_elision_not_le_appartement():
    span, fix, note = _contract().first_valid_edit("je veux vendre la appartement", None, None, language="de")
    assert (span, fix) == ("la appartement", "l'appartement"), (span, fix, note)


def test_a_model_replacement_that_is_wrong_french_is_not_grounded():
    contract = _contract()
    assert not contract.edit_is_grounded(
        "je veux vendre la appartement", "la", "le", "« appartement » ist maskulin"
    )
    assert not contract.edit_is_grounded("je veux vendre la maison blanche", "la maison", "le appartement")
