"""2026-09-24 — server-sent chrome follows the one-language rule.

Up to A2 the app's own words are in the learner's language; from B1 French.
"""
from types import SimpleNamespace

from app.services import story_correspondence as courrier
from app.services.chrome_language import chrome_language, user_chrome_language
from app.services.missions import AUTHORED_SUCCESS_SIGNAL_I18N, success_signal_i18n
from app.services.recommendation_reasons import recommendation_reason


def test_chrome_language_mirrors_the_frontend_rule():
    assert chrome_language("en", "A1.1") == "en"
    assert chrome_language("de-DE", "A2") == "de"
    assert chrome_language("en", "B1.2") == "fr"
    assert chrome_language("es", None) == "en"  # unsupported → signup default
    assert user_chrome_language(SimpleNamespace(native_language="de", cefr_estimate="A1.1")) == "de"
    assert user_chrome_language(SimpleNamespace(native_language="de", cefr_estimate="C1")) == "fr"


def test_the_why_this_letter_line_is_served_in_the_learners_language():
    reason = recommendation_reason("mission", language="en")
    assert reason["text"] == "Chosen so you use the words and structures of your edition."
    assert set(reason["text_by_language"]) == {"fr", "en", "de"}
    assert reason["text_by_language"]["fr"].startswith("Choisi pour produire")
    # French stays the default for callers that know no learner.
    assert recommendation_reason("review", bucket="due")["text"].startswith("Choisi")


def test_a_letters_objective_carries_every_control_language():
    generated = {
        "success_signal": "La boutique confirme la bonne taille.",
        "success_signal_i18n": {
            "fr": "La boutique confirme la bonne taille.",
            "en": "The shop confirms the right size.",
            "de": "Der Laden bestätigt die richtige Größe.",
        },
    }
    assert success_signal_i18n(generated)["en"] == "The shop confirms the right size."

    authored = {"success_signal": "The shop can send the correct size or confirm the return."}
    table = success_signal_i18n(authored)
    assert table["en"] == authored["success_signal"]
    assert table["fr"].startswith("La boutique")
    assert table["de"]

    # A custom or overwritten objective no longer matches the writer's French:
    # the labelled fallback keeps it under `fr` only.
    overwritten = {**generated, "success_signal": "Obtenir un rendez-vous."}
    assert success_signal_i18n(overwritten) == {"fr": "Obtenir un rendez-vous."}
    for entry in AUTHORED_SUCCESS_SIGNAL_I18N.values():
        assert entry["fr"] and entry["de"]


def test_every_placement_hint_has_an_english_and_german_version():
    from app.services.placement import PROMPTS_BY_ID, hint_by_language

    for prompt in PROMPTS_BY_ID.values():
        table = hint_by_language(prompt.hint_fr)
        assert table["fr"] == prompt.hint_fr
        assert table.get("en") and table.get("de"), prompt.hint_fr
    assert hint_by_language("Inconnu.") == {"fr": "Inconnu."}


def test_the_journey_letter_objective_is_in_the_chrome_language(monkeypatch):
    mission = SimpleNamespace(
        id="m1",
        correspondent_id="boutique_anais",
        title="Wrong size",
        brief="",
        objectives=[{"required": True, "label": "Écrire un message qu'on pourrait vraiment envoyer"}],
        prompt_payload={
            "messenger": {"contact_name": "Boutique Anaïs", "opening_message": "Bonjour, quelle taille ?"},
            "slim_payload": {"ask_by_language": {"fr": "La boutique confirme.", "en": "The shop confirms."}},
        },
    )
    monkeypatch.setattr(courrier, "awaiting_letter", lambda db, user: mission)
    a1 = SimpleNamespace(native_language="en", cefr_estimate="A1.1")
    b1 = SimpleNamespace(native_language="en", cefr_estimate="B1.1")
    de = SimpleNamespace(native_language="de", cefr_estimate="A2")
    assert courrier.journey_letter_facts(None, user=a1)["objective_native"] == "The shop confirms."
    assert courrier.journey_letter_facts(None, user=b1)["objective_native"] == "La boutique confirme."
    # No German version: the letter's French objective label is the fallback.
    assert courrier.journey_letter_facts(None, user=de)["objective_native"].startswith("Écrire")


def test_mood_value_is_the_clamped_number_behind_the_mood_line():
    thread = SimpleNamespace(state={courrier.STATE_KEY: {"moods": {"anais": {"mood": 5, "trust": 2}}}})
    assert courrier.mood_value(thread, "anais") == 2
    assert courrier.mood_value(thread, "nobody") is None
    assert courrier.mood_value(None, "anais") is None
