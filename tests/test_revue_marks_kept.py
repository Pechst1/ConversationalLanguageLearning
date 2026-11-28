"""«Le Papier»: Romy's right marks are kept (real-model run of 2026-11-22, 57 learner texts).

With ``REVUE_TUTOR_MARKS_ENABLED`` every mark passes the scene tutor's verification; the run
found it dropping right marks and printing the error under «corrigé par Romy»:

1. ``living_story.gender_only_change`` read an elision as a gender change («que un» → «qu'un»,
   «je ai» → «j'ai» fold to the same words). Alone, the model-free fallback put it back; next to
   a second mark it was lost and the printed text kept the slip (X-A2-1, X-B1-1).
2. The same guard dropped agreements with a noun subject as «the learner's own gender»: «les
   tomates sont devenu» (shown clean), «le prix … est trop haute» (printed wrong), «franchises
   médical» (shown clean). Only the speaker's own gender (first person) is protected.
3. A sentence whose mark was dropped is rebuilt from the kept edits only; a slip the model-free
   checks know is still corrected and marked there, never printed as «corrigé».
4. The A2 frame «… parce que» was joined to «un prix …» without elision, and Romy marked the
   app's own «parce que un» as the learner's slip (C-A2-G6).
5. Concept names that did not fit: an elision named «Avoir», «j'achetais → j'ai acheté» named
   «Avoir», «avons allé → sommes allés» named «être», «de les → des» named «Un, une, des».
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.services import living_story as engine
from app.services.revue import comptoir_loop, regle, voice
from app.services.story_lanes import TutorCorrection, _accepted_correction


@pytest.fixture(autouse=True)
def switch_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_TUTOR_MARKS_ENABLED", True, raising=False)


def _vet(learner: str, target: str):
    marks = comptoir_loop.proof_marks(learner, target)
    return regle.vet(marks, learner_fr=learner, target_fr=target, language="de", rules=None,
                     shape=voice.french_typography)


# 1 · An elision is not a gender ------------------------------------------------------------


@pytest.mark.parametrize(("span", "corrected"), [
    ("que un", "qu'un"),
    ("je ai", "j'ai"),
    ("Je ai", "J’ai"),
    ("je pense que un prix", "je pense qu’un prix"),
])
def test_an_elision_is_never_a_gender_only_change(span: str, corrected: str) -> None:
    assert engine.gender_only_change(span, corrected) is False


def test_the_scene_tutor_keeps_an_elision() -> None:
    text = "Je pense que un prix est pour les humains."
    kept = _accepted_correction(TutorCorrection(span_fr="que un", corrected_fr="qu'un"), text, rules=None,
                                known=set(), language="de")
    assert kept is not None and kept.corrected_fr.replace("’", "'") == "qu'un"


def test_an_elision_next_to_a_second_mark_is_kept_and_printed() -> None:
    learner = "Je ai vu les prix au marché hier et les fraises sont trop cher pour ma famille."
    target = "J'ai vu les prix au marché hier et les fraises sont trop chères pour ma famille."
    fixed, marks = _vet(learner, target)
    assert [m["span_fr"] for m in marks] == ["Je ai", "cher"]
    assert fixed.replace("’", "'") == target


# 2 · Only the speaker's own gender is theirs to give ---------------------------------------


@pytest.mark.parametrize(("text", "span", "corrected", "gender_only"), [
    ("Les tomates sont devenu très chères.", "devenu", "devenues", False),
    ("Le prix de la viande est trop haute pour nous.", "haute", "haut", False),
    ("Le plafond des franchises médical est fixé à 140 euros.", "médical", "médicales", False),
    ("Je suis un peu perdu ici.", "perdu", "perdue", True),
    ("Je suis allé au marché et fatigué.", "fatigué", "fatiguée", True),
    ("Il me trouve fatigué.", "fatigué", "fatiguée", True),
    ("Nous sommes contents.", "contents", "contentes", True),
])
def test_only_a_first_person_agreement_is_the_learners_gender(text, span, corrected, gender_only) -> None:
    assert engine.gender_only_change(span, corrected, text=text) is gender_only


@pytest.mark.parametrize(("learner", "target", "spans"), [
    ("Les tomates sont devenu très chères cette année.", "Les tomates sont devenues très chères cette année.",
     ["devenu"]),
    ("La prix de la viande est trop haute pour nous.", "Le prix de la viande est trop haut pour nous.",
     ["La", "haute"]),
    ("Le plafond des franchises médical est fixé à 140 euros.",
     "Le plafond des franchises médicales est fixé à 140 euros.", ["médical"]),
])
def test_a_noun_subject_agreement_is_marked(learner: str, target: str, spans: list[str]) -> None:
    fixed, marks = _vet(learner, target)
    assert [m["span_fr"] for m in marks] == spans
    assert fixed == target


def test_the_learners_own_gender_is_still_never_imposed() -> None:
    learner = "Je suis un peu perdu ici. Les gens sont content."
    fixed, marks = _vet(learner, "Je suis un peu perdue ici. Les gens sont contents.")
    assert [m["span_fr"] for m in marks] == ["content"]
    assert fixed == "Je suis un peu perdu ici. Les gens sont contents."


# 3 · A sentence whose mark was dropped never prints a known slip ---------------------------


def test_a_dropped_marks_sentence_keeps_no_slip_the_checks_know() -> None:
    learner = "Je pense que tu as raison et que il est là. Les gens sont content."
    target = "Je pense que vous avez raison et que il est là. Les gens sont contents."
    fixed, marks = _vet(learner, target)
    assert "que il" not in fixed and "qu'il" in fixed.replace("’", "'"), fixed
    assert "tu as raison" in fixed, "the dropped mark's change is still taken out"
    assert [m["span_fr"] for m in marks] == ["que il", "content"]
    assert learner[marks[0]["start"]:].startswith("que il")


# 4 · The A2 frame elides before the learner's reason ---------------------------------------


def test_the_a2_frame_elides_parce_que() -> None:
    frame = "À mon avis, il faut le retirer, parce que"
    reason = "un prix littéraire récompense le travail d'un écrivain"
    sentence = comptoir_loop.a2_sentence(frame, reason)
    assert sentence == f"À mon avis, il faut le retirer, parce qu'{reason}."
    assert comptoir_loop._without_frame(sentence, frame) == f"{reason}."
    assert comptoir_loop.a2_sentence(frame, "les tomates sont chères") == f"{frame} les tomates sont chères."


# 5 · Concept names that fit -----------------------------------------------------------------


@pytest.mark.parametrize(("sentence", "span", "fix", "kind", "concept_id"), [
    ("Je ai vu les prix au marché.", "Je ai", "J'ai", "mot", None),
    ("Je pense que un prix est beau.", "que un", "qu'un", "mot", None),
    ("Les gens vont la utiliser pour payer.", "la utiliser", "l'utiliser", "orthographe", None),
    ("Hier je suis allé au marché et j'achetais trois kilos de pommes.", "j'achetais", "j'ai acheté",
     "conjugaison", "FR2_A21_PC_AVOIR"),
    ("Parce que nous avons allé au marché.", "avons allé", "sommes allés", "conjugaison", "FR2_A21_PC_ETRE"),
    ("En septembre, les prix de les fruits augmentent.", "de les", "des", "mot", "FR2_A11_CONTRACTIONS"),
    ("Les jurés ont devenu des juges.", "ont devenu", "sont devenus", "mot", "FR2_A21_PC_ETRE"),
])
def test_the_concept_named_fits_the_mark(sentence, span, fix, kind, concept_id) -> None:
    from app.services.revue.pourquoi import rule_for

    concept = regle.concept_for(sentence, span, fix, kind=kind, rule=rule_for(kind, span, fix), rules=None,
                                language="de")
    assert (concept or {}).get("concept_id") == concept_id
