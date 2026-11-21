"""P4 (experience review, walk of 17 Nov 2026): wrong corrections the walk saw become judge cases.

Each case below was observed with real model output in the walk logs
(``docs/ops/walks/2026-11-17-experience-review/logs/``: a1-part2, a1-part3, b1-part1,
b1-part2). A case is written against the deterministic layer that should have stopped it,
because the model's answer itself is not replayable here: no model call is made in this
file. The tag of each test names the surface and the date.

Where the mechanism is fixed the test is a plain guard. Where it is only documented the
test is ``xfail(strict=True)`` with the reason: it turns red the day someone fixes it, so
the note is updated with it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import correction_contract as cc

WALK = "walk 2026-11-17"


def _pairs(errata) -> list[tuple[str, str]]:
    return [(str(e.get("learner_text")), str(e.get("corrected_target"))) for e in errata]


# ---------------------------------------------------------------------------
# 1 · Journal (A1-de, day 2): «Gus parle beaucoup.» -> «beaucoup → beaucoup et»
# ---------------------------------------------------------------------------

#: a1-part2.md, Journal: the learner's text word for word.
JOURNAL_A1 = "Je suis a Paris. Margaux a un cafe. Camille a la cle. Gus parle beaucoup. Je suis fatigue."
#: The model's corrected sentence as the list implies it: two sentences joined by «et».
JOURNAL_A1_MODEL = "Je suis à Paris. Margaux a un café. Camille a la clé. Gus parle beaucoup et je suis fatigué(e)."


def test_journal_a_word_the_model_added_is_never_a_replacement_of_a_right_word():
    """Journal · 2026-11-17 · case 1. The insertion branch of ``sentence_gaps`` turned the
    «et» the model added into «beaucoup → beaucoup et», with the note «Die richtige Form ist
    « beaucoup et »», and printed «Gus parle beaucoup et. Je suis …»."""

    errata = cc.merge_deterministic_errata(JOURNAL_A1, [], language="de")
    checked = cc.verify_correction(JOURNAL_A1, JOURNAL_A1_MODEL, errata, language="de")

    assert ("beaucoup", "beaucoup et") not in _pairs(checked.errata), WALK
    assert "beaucoup et" not in checked.corrected
    # the real fixes stay
    assert {("a", "à"), ("cafe", "café"), ("cle", "clé")} <= set(_pairs(checked.errata))


def test_forge_gaps_never_join_two_sentences_with_a_word():
    """Any surface · 2026-11-17 · case 1. The Forge reads the same gaps (``held_gaps``):
    a word added across the learner's full stop is refused there too."""

    held = cc.held_gaps("Gus parle beaucoup. Je suis fatigué.", "Gus parle beaucoup et je suis fatigué.")
    assert held is not None
    allowed, refused = held
    assert [(g.wrong, g.fix) for g in allowed] == []
    assert ("beaucoup", "beaucoup et") in _pairs(refused)


def test_a_missing_word_inside_a_clause_is_still_a_gap_on_the_forge():
    """The Forge's gaps still ask for a missing word inside a clause (#574): only the
    list surfaces, which cannot show an insertion, drop it."""

    held = cc.held_gaps("Elle a acheté livre.", "Elle a acheté un livre.")
    assert held is not None
    allowed, _refused = held
    assert [(g.wrong, g.fix) for g in allowed] == [("acheté", "acheté un")]


# ---------------------------------------------------------------------------
# 2 · Scene reply (A1, return day): «pas avec lait» -> «pas avec de lait»
# ---------------------------------------------------------------------------

#: a1-part3.md, scene exchange 1.
SCENE_LAIT = "Un café, mais pas avec lait. Merci."


@pytest.mark.parametrize(("span", "fix"), [("pas avec lait", "pas avec de lait"), ("avec lait", "avec de lait")])
def test_scene_never_prints_a_bare_de_after_a_preposition(span, fix):
    """Scene · 2026-11-17 · case 2. The one edit a scene shows (``first_valid_edit``) is put
    back in the line and settled by the rules (the fixpoint of #860); «avec de lait» is a
    line the rules know is not French, so the edit is not shown."""

    assert not cc.verify_edit(SCENE_LAIT, span, fix).ok, WALK
    shown = cc.first_valid_edit(SCENE_LAIT, span, fix, "On dit « pas avec de lait ».", language="de")
    assert shown[1] != fix


def test_journal_listed_fix_with_a_bare_de_is_refused_too():
    """Journal · 2026-11-17 · case 2 on the list surfaces (``verify_erratum``)."""

    item = {"learner_text": "avec lait", "corrected_target": "avec de lait", "why_wrong": "x", "task_error_type": "grammar"}
    assert cc.verify_erratum(SCENE_LAIT, item) is None


@pytest.mark.parametrize(
    "line",
    [
        "Un café avec du lait.",
        "Il part avec de l'eau.",
        "Elle vient avec de bons amis.",
        "C'est pour de vrai.",
        "Il a beaucoup de lait.",
        "Je reviens avec de la soupe.",
        "Il voyage avec de Gaulle en tête.",
    ],
)
def test_the_bare_de_check_leaves_right_french_alone(line):
    """The new check refuses a fix; it never makes one, and never touches these."""

    assert cc.deterministic_edits(line) == []
    assert not cc._bare_de_after_preposition(line, 0, len(line))


# ---------------------------------------------------------------------------
# 3 · Scene reply (B1-en, day 1): «à la notaire» -> «au», «« notaire » est masculin»
# ---------------------------------------------------------------------------

#: b1-part1.md, scene exchange 3 (the learner is a woman; Maître Vasseur is a woman).
SCENE_NOTAIRE = (
    "Oui, je monte ce soir. Je voudrais voir si ma grand-mère a laissé quelque chose à moi dans "
    "l'appartement. Hier je suis allé à la notaire et elle a dit que je dois signer demain."
)


def test_scene_never_regenders_a_profession_noun():
    """Scene · 2026-11-17 · case 3. The rule pass read «notaire» as masculine from the core
    lexicon and wrote «« notaire » est masculin : « le notaire » et non « la notaire »»;
    the story itself says «la notaire» two days later. A noun French uses for a woman too
    is in ``_TWO_GENDER_NOUNS`` and its determiner is never corrected, by a rule or a model."""

    assert [e for e in cc.deterministic_edits(SCENE_NOTAIRE) if e.rule_id == "FR_GENDER_DET"] == [], WALK
    assert not cc.verify_edit(SCENE_NOTAIRE, "à la", "au", "« notaire » est masculin").ok
    span, fix, _note = cc.first_valid_edit(SCENE_NOTAIRE, "à la", "au", "« notaire » est masculin", language="fr")
    assert (span, fix) != ("à la", "au")


def test_a_gender_fix_on_a_one_gender_noun_still_stands():
    assert cc.verify_edit("J'ai le valise.", "le", "la").ok
    assert [e.rule_id for e in cc.deterministic_edits("J'ai le valise.")] == ["FR_GENDER_DET"]


# ---------------------------------------------------------------------------
# 4 · La Forge free sentence (B1, day 2): «… la clé … elle me le rend» judged «Juste»
# ---------------------------------------------------------------------------

FORGE_CLE = "J'ai laissé la clé à Margaux hier soir et elle me le rend ce soir."


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Forge · 2026-11-17 · case 4, documented: the referent of «le» cannot be read without "
        "the meaning (here «la clé», «Margaux» and «soir» all stand before it). The model-free "
        "pass has the nouns' genders but no safe pronoun-antecedent rule; the gate below holds "
        "a «Juste» to whatever the pass does see."
    ),
)
def test_forge_pronoun_antecedent_agreement_is_seen_by_the_rules():
    assert cc.deterministic_edits(FORGE_CLE) != []


def test_forge_free_sentence_is_right_only_when_the_rule_pass_is_silent():
    """Forge · 2026-11-17 · cases 4 and 5. A model «correct» on a free sentence the rule
    pass would correct («le valise») is not «Juste»: the rule's fix is the correction."""

    from app.services.forge_grading import refine_production_correction

    model = {"verdict": "correct", "score_0_4": 4.0, "errata": [], "corrected_answer": "Je prends le valise ce soir."}
    refined = refine_production_correction(
        model, learner_text="Je prends le valise ce soir.", accepted=["Je prends la valise ce soir ?"], language="de"
    )
    assert refined["verdict"] not in {"correct", "accepted"}
    assert ("le", "la") in _pairs(refined["errata"])
    assert "la valise" in refined["corrected_answer"]


def test_forge_free_sentence_with_only_an_accent_slip_stays_right():
    from app.services.forge_grading import refine_production_correction

    model = {"verdict": "correct", "score_0_4": 4.0, "errata": [], "corrected_answer": "Je suis tres content."}
    refined = refine_production_correction(model, learner_text="Je suis tres content.", accepted=[], language="de")
    assert refined["verdict"] == "correct"


# ---------------------------------------------------------------------------
# 5 · Word warm-up after the scene (A1-de, day 5): «le valise» accepted as «Richtig»
# ---------------------------------------------------------------------------


def test_recall_with_a_bare_noun_key_refuses_the_wrong_article():
    """Recall drill · 2026-11-17 · case 5. Not La Forge, as the review says: the «Wiederholung»
    word item «Wie sagt man „der Koffer" auf Französisch?». Its accept-list holds the bare
    noun «valise» (``_accepted_answers``, article optional) and ``answer_matches`` accepted
    any answer that holds the noun as a run of words, whatever article stood before it."""

    from app.services.journey_learning import answer_matches

    # The prompt «der Koffer» names the article: it is part of the question.
    assert not answer_matches("le valise", ["la valise", "valise"]), WALK
    assert not answer_matches("un valise", ["valise"])
    for optional in (False, True):
        assert answer_matches("la valise", ["la valise", "valise"], article_optional=optional)
        assert answer_matches("une valise", ["valise"], article_optional=optional)
        assert answer_matches("valise", ["valise"], article_optional=optional)
    # #174 (owner, 2 Nov): a noun asked without its article («Koffer») keeps any article
    # as a hit; the right one is named on it (tests/test_article_named_on_hit_174.py).
    assert answer_matches("le valise", ["la valise", "valise"], article_optional=True)
    # a noun with two genders keeps both
    assert answer_matches("la livre", ["livre"])


# ---------------------------------------------------------------------------
# 6 · La Forge repair (B1, day 4): «je le remercie» refused, the stored fix was «l'en»
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Forge · 2026-11-17 · case 6, documented: a repair gap accepts the one fix the model "
        "chose (record_micro_repair: target, key line, the line rebuilt from the erratum). There "
        "is no list of other right fixes for a model-made gap, the memo (answer_memo) settles "
        "keyed items only and the appeal (verdict_appeal) reads journey drills only, so neither "
        "can learn «le» for «l'en»."
    ),
)
def test_forge_repair_accepts_another_right_fix():
    from app.services.atelier import AtelierCorrectionService, repair_line_from_parts

    source = "Marin m'a apporté une soupe et je lui en remercie beaucoup, mais la clé me fait toujours peur."
    errata = [{"learner_text": "lui en", "corrected_target": "l'en", "task_error_type": "pronouns"}]
    accepted = ["l'en", None, repair_line_from_parts(source, errata)]
    assert AtelierCorrectionService._repair_is_right("le", source, accepted)


# ---------------------------------------------------------------------------
# 7 · La Forge (A1-de, day 6): «Ils vont dans le métro» refused, the item wanted «entrer»
# ---------------------------------------------------------------------------


def test_forge_german_prompt_of_entrer_is_not_the_prompt_of_aller():
    """Forge · 2026-11-17 · case 7. «Sie (alle) gehen in die U-Bahn.» was rendered for
    «Ils entrent dans le métro.» (unit -er verbs): the German overlay gave «entrer» the
    verb «gehen» of «aller», so the right translation «Ils vont …» was refused for a hidden
    constraint. The prompt now says «hineingehen»."""

    path = Path(__file__).resolve().parents[1] / "app" / "data" / "grammar_templates" / "lexicon_de.json"
    verbs = json.loads(path.read_text(encoding="utf-8"))["verbs"]

    def german(verb: str) -> tuple:
        entry = verbs[verb]
        return entry.get("inf"), entry.get("sep"), entry.get("tail")

    assert german("entrer") != german("aller"), WALK


def test_forge_entrer_item_renders_hinein():
    from app.services import item_bank as ib

    bank = ib.ItemBank()
    seen = []
    for unit in ib.template_units():
        for item in bank.generate(unit, 60, seed=f"p4:{unit}", detector=ib.unit_detector(unit)):
            verbs = {entry.get("id") for _slot, entry in item.bindings if isinstance(entry, dict)}
            if item.de and "entrer" in verbs:
                seen.append(item.de)
    assert seen
    for de in seen:
        assert "hinein" in de, de


# ---------------------------------------------------------------------------
# 8 · Journal and scene (A1-de): «fatigue → fatigué(e)», and «fatigué» flagged «fatigué(e)»
# ---------------------------------------------------------------------------


def test_a_fix_never_writes_a_bracket_gender():
    """Journal and scene · 2026-11-17 · case 8. The learner's gender is theirs to give: a
    fix that writes «fatigué(e)» is not shown on any surface (the scene's rule since
    2026-09-30, now in the one check every surface runs). The scene's flag on a right
    «fatigué» came from a stored Journal fault re-fed to the tutor (draft PR 870); the
    edit itself is refused here as well."""

    reply = "Non, pas froid. Je suis fatigué et j ai peur de le vol."
    assert not cc.verify_edit(reply, "fatigué", "fatigué(e)").ok, WALK
    span, fix, _note = cc.first_valid_edit(reply, "fatigué", "fatigué(e)", "die Endung richtet sich nach deinem Geschlecht", language="de")
    assert fix is None or "(e)" not in fix

    listed = [
        {
            "learner_text": "fatigue",
            "corrected_target": "fatigué(e)",
            "why_wrong": "Als Adjektiv braucht „fatigue“ einen Akut; die Endung richtet sich nach deinem Geschlecht.",
            "task_error_type": "grammar",
        }
    ]
    checked = cc.verify_correction(JOURNAL_A1, None, cc.merge_deterministic_errata(JOURNAL_A1, listed, language="de"))
    assert all("(e)" not in fix for _span, fix in _pairs(checked.errata))
    assert "(e)" not in checked.corrected
