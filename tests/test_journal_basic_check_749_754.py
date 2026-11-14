"""#749 / #754: the Journal's basic check, the model-free floor under every check.

#749 (live walk 13 Nov): «Elle a fait un signe à moi» came back «Nothing to correct in
this text». The stressed pronoun after a verb («à moi» for «m'») is a typical slip for a
German speaker, and the shared model-free pass had no rule for it, so nothing under the
model caught what the model let through.

#754 (walk 13 Nov, no model): «Gus m a demandé qui j étais, et Margaux m a donné un café
crème» showed no correction at all, then «Une faute est notée au Relevé», and offered
«Relancer la correction» on a stack where no model could ever answer. The rules missed
«m a» after a name, the one fix they did find («j étais») was recorded but never drawn
on the card, and the Journal called a missing model a «model_error» worth retrying.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.config import settings
from app.services import correction_contract, verdicts
from tests.test_journal import (  # noqa: F401 - the module's table fixture is autouse there
    TODAY,
    _concept,
    _FakeCorrector,
    _journey,
    _service,
    _user,
    _write,
    journal_table,
)

SIGNE = "Margaux ne parle à personne au Mistral. Elle a fait un signe à moi. Le dossier de Marin est sur son frigo."
RETELL = (
    "Je suis arrivée au Mistral avec la clé de ma grand-mère. Gus m a demandé qui j étais, "
    "et Margaux m a donné un café crème. Puis Camille est arrivée avec une autre clé du premier étage."
)


def _fixes(text: str) -> dict[str, str]:
    return {edit.span: edit.replacement for edit in correction_contract.deterministic_edits(text)}


# ---------------------------------------------------------------------------
# the rules
# ---------------------------------------------------------------------------


def test_a_stressed_pronoun_after_a_verb_becomes_the_object_pronoun_before_it():
    fixes = _fixes(SIGNE)
    assert any("m'a fait un signe" in right for right in fixes.values()), (
        f"«Elle a fait un signe à moi» passed the model-free check: {fixes}"
    )
    assert correction_contract.repair_text(SIGNE).count("Elle m'a fait un signe.") == 1
    assert correction_contract.repair_text("Il parle à toi.") == "Il te parle."
    assert correction_contract.repair_text("Margaux a donné le café à moi.") == "Margaux m'a donné le café."
    assert correction_contract.repair_text("J'ai écrit une lettre à toi.") == "Je t'ai écrit une lettre."


@pytest.mark.parametrize(
    "right",
    [
        "Elle pense à moi.",  # penser à takes the stressed pronoun
        "C'est à moi.",
        "Ce livre est à toi.",
        "Elle a fait attention à moi.",
        "Il parle à moi, pas à toi.",
        "Il a donné un livre à moi et à Lila.",
        "Un ami à moi est venu.",
        "Elle tient à moi.",
        "À moi de jouer.",
        "Elle ne parle pas à moi.",
        # «un ami à moi» is a friend of mine: the possessive, not the object of the verb
        "Elle a présenté un ami à moi.",
        "Il a montré une amie à toi.",
        "Elle a appelé la sœur à moi.",
        "Il a donné les clés du voisin à moi.",
        # the relation noun need not be the last word before «à»
        "Elle a présenté un ami d'enfance à moi.",
        "Elle a présenté un ami proche à moi.",
        "Elle a présenté la fille aînée à moi.",
        # «tout à moi» would come out «Il m'a donné tout», still wrong French
        "Il a donné tout à moi.",
        "Il a dit tout à toi.",
    ],
)
def test_a_stressed_pronoun_that_belongs_after_its_word_is_left_alone(right):
    assert not any("moi" in span or "toi" in span for span in _fixes(right)), right


def test_a_dropped_apostrophe_after_a_name_is_found_like_after_a_pronoun():
    fixes = _fixes(RETELL)
    assert fixes.get("Gus m a") == "Gus m'a" or fixes.get("m a") == "m'a", fixes
    assert "Margaux m'a" in correction_contract.repair_text(RETELL), fixes
    assert fixes.get("j étais") == "j'étais"
    assert correction_contract.repair_text(RETELL).count("m'a") == 2


@pytest.mark.parametrize("right", ["La ligne M a du retard.", "Le plan B a marché.", "Gus a vu la lettre m à la fin."])
def test_a_letter_after_a_name_is_still_a_letter(right):
    assert not any(" a" in span and "'" in rep for span, rep in _fixes(right).items()), right


# ---------------------------------------------------------------------------
# the Journal
# ---------------------------------------------------------------------------


def test_the_journal_names_the_slip_the_model_let_through(db_session):
    """#749 done-when: the model said nothing; the card still names «m'a fait un signe»."""
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    corrector = _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []})
    entry = _write(db_session, user, corrector, SIGNE)

    shown = [entry.correction["foreground"], *entry.correction["errata"]]
    assert any(item and "m'a fait un signe" in item["corrected_fr"] for item in shown), (
        f"«Nothing to correct» for «à moi»: {entry.correction}"
    )
    assert entry.correction["foreground"] is not None


def test_the_foreground_never_shows_a_fix_the_validator_refuses(db_session):
    """Review of #763: the card's one correction passes the same validator as every
    surface. A rewrite into a gender the learner never gave is no correction of their
    French, so it is neither up front nor in the list, nor noted in the Relevé."""
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    corrector = _FakeCorrector(
        {
            "verdict": "partial",
            "score_0_4": 3,
            "errata": [
                {
                    "item_id": "a",
                    "display_label": "Accord",
                    "learner_text": "Je suis content",
                    "corrected_target": "Je suis contente",
                    "why_wrong": "Agreement.",
                    "repair_hint": "contente",
                    "severity": 2,
                    "recurring": True,
                    "task_error_type": "gender_agreement",
                }
            ],
        }
    )
    entry = _write(db_session, user, corrector, "Je suis content de voir Margaux au Mistral.")
    assert entry.correction["foreground"] is None, entry.correction["foreground"]
    assert not any("contente" in item["corrected_fr"] for item in entry.correction["errata"]), entry.correction
    assert entry.errata_ids == []


def test_a_written_apostrophe_fix_is_the_one_up_front(db_session):
    """A dropped apostrophe is a mistake in a written text, not punctuation noise: the
    speech fold reads «j étais» and «j'étais» as one word, the written check does not."""
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    entry = _write(
        db_session, user, _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []}),
        "Gus a demandé qui j étais.",
    )
    assert (entry.correction["foreground"] or {}).get("corrected_fr") == "j'étais", entry.correction


@pytest.fixture(params=["switched_off", "no_provider"])
def no_model(request, monkeypatch):
    """No model to ask: the checker switched off, or no provider key on the stack (the walk)."""
    if request.param == "switched_off":
        monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_ENABLED", False)
    else:
        def no_provider(*_args, **_kwargs):
            raise ValueError("LLMService requires at least one provider")

        monkeypatch.setattr("app.services.atelier.LLMService", no_provider)


def test_with_no_model_the_basic_check_shows_every_fix_it_counts(db_session, no_model):
    """#754 done-when: «m a → m'a», «j étais → j'étais» under «Vérification de base
    seulement», and the «faute(s) notée(s)» count is never more than the card shows."""
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    entry = _write(db_session, user, None, RETELL)

    correction = entry.correction
    assert correction["checker"] == "deterministic"
    rights = [item["corrected_fr"] for item in correction["errata"]]
    assert sum("m'a" in right for right in rights) == 2, rights
    assert "j'étais" in rights, rights
    assert correction["foreground"] is not None, "one fix up front, as the card promises"
    assert len(entry.errata_ids) <= len(correction["errata"])


def test_with_no_model_the_check_is_not_offered_again(db_session, no_model):
    """#754 / #735: no model to ask is ``no_model`` and not retryable."""
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    entry = _write(db_session, user, None, RETELL)

    assert entry.correction["failure_reason"] == "no_model"
    assert entry.correction["retryable"] is False
    check = verdicts.from_journal(entry.correction, text=entry.entry_text)
    assert check.failure is not None and check.failure.value == "no_model"
    assert check.retryable is False

    before = dict(entry.correction)
    good = _FakeCorrector({"verdict": "accepted", "score_0_4": 4, "errata": []})
    after = _service(db_session, good).retry_correction(user, entry)
    assert good.calls == 0 and after.correction == before


def test_a_model_that_failed_is_still_worth_asking_again(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    entry = _write(db_session, user, _FakeCorrector(fail=True), RETELL)
    assert entry.correction["failure_reason"] == "model_error"
    assert entry.correction["retryable"] is True
