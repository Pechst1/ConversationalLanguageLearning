"""WP-86 — the scene says which words it teaches, and only words it really teaches.

No paid call: the director is ``tests.test_living_story``'s fake, with a lexicon
added the way a compliant model writes one.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine
from app.services.scene_items import validate_lexicon
from tests import test_living_story as story

# The assembled journey fixtures, as the living-story suite imports them.
assembled_client = story.assembled_client
clock = story.clock
journey_enabled = story.journey_enabled
provider = story.provider

GOOD = [
    {"surface_fr": "pluie", "lemma": "pluie", "gloss_native": "rain",
     "part_of_speech": "noun", "gender": "f", "line_ref": "panel:0:narration"},
    {"surface_fr": "vitre", "lemma": "vitre", "gloss_native": "window pane",
     "part_of_speech": "noun", "gender": "f", "line_ref": "premise"},  # wrong ref: repaired
    {"surface_fr": "idée", "lemma": "idée", "gloss_native": "idea",
     "part_of_speech": "noun", "gender": "f", "line_ref": "panel:1:line:0"},
]
BAD = [
    {"surface_fr": "brouillard", "lemma": "brouillard", "gloss_native": "fog",
     "part_of_speech": "noun", "gender": "m"},  # not in the scene
    {"surface_fr": "aider", "lemma": "aider", "gloss_native": "aider",
     "part_of_speech": "verb"},  # the gloss is the French copied
    {"surface_fr": "exposition", "lemma": "exposition", "gloss_native": "exhibition",
     "part_of_speech": "noun"},  # a noun without its gender
]


def _draft(lexicon=None, n=0):
    value = story.draft(story._scene_context(), n)
    if lexicon is not None:
        value["lexicon"] = lexicon
    return value


def test_valid_entries_are_kept_and_normalised():
    kept, dropped = validate_lexicon(GOOD + BAD, _draft(), level="A1")
    assert [entry["lemma"] for entry in kept] == ["pluie", "vitre", "idée"]
    assert kept[1]["line_ref"] == "panel:0:narration", "the wrong line ref is repaired"
    assert {entry["gender"] for entry in kept} == {"f"}
    reasons = " | ".join(dropped)
    assert "brouillard: surface_not_in_scene" in reasons
    assert "aider: gloss_missing_or_copied" in reasons
    assert "exposition: noun_without_gender" in reasons


def test_duplicates_and_overflow_are_dropped_and_band_fit_is_soft():
    many = GOOD + [dict(GOOD[0])] + [
        {"surface_fr": "aider", "lemma": "aider", "gloss_native": "to help", "part_of_speech": "verb"},
        {"surface_fr": "glisse", "lemma": "glisser", "gloss_native": "slides", "part_of_speech": "verb"},
        {"surface_fr": "Vous", "lemma": "vous", "gloss_native": "you", "part_of_speech": "pronoun"},
    ]
    ranks = {"pluie": 900, "vitre": 4200, "idée": 300}
    kept, dropped = validate_lexicon(many, _draft(), level="A1", rank_of=ranks.get)
    assert len(kept) == 5
    assert any("duplicate_lemma" in reason for reason in dropped)
    assert any("over_limit" in reason for reason in dropped)
    fits = {entry["lemma"]: entry["band_fit"] for entry in kept}
    assert fits.get("pluie") == 1.0 and fits.get("idée") == 1.0
    # Out of band is a lower score and a later place, never a refusal by itself.
    assert "vitre" not in fits or fits["vitre"] == 0.5
    assert fits.get("aider", None) is None


def test_the_scene_validator_drops_bad_entries_and_never_refuses_for_them():
    context = story._scene_context()
    proposal = engine.SceneDraft.model_validate(_draft(GOOD + BAD))
    engine._validate_scene(proposal, context)
    assert [entry.lemma for entry in proposal.lexicon] == ["pluie", "vitre", "idée"]
    thin = engine.SceneDraft.model_validate(_draft(BAD))
    engine._validate_scene(thin, context)  # a thin lexicon is not a lost day
    assert thin.lexicon == []


def test_a_richer_lexicon_wins_the_dual_draft_score():
    context = story._scene_context()
    rich = engine.SceneDraft.model_validate(_draft(GOOD))
    bare = engine.SceneDraft.model_validate(_draft([]))
    for proposal in (rich, bare):
        engine._validate_scene(proposal, context)
    assert engine._scene_score(rich, context) > engine._scene_score(bare, context)


def test_the_director_is_told_to_teach_words():
    assert "VOCABULARY" in engine.DIRECTOR
    assert "lexicon" in engine.SceneDraft.model_json_schema()["properties"]


@pytest.fixture
def lexicon_provider(provider):
    def add(schema, value):
        if schema == "SceneDraft":
            return {**value, "lexicon": GOOD + BAD[:1]}
        return value

    provider.transform = add
    return provider


def test_a_generated_scene_carries_three_to_five_validated_words(
    assembled_client, db_session, journey_enabled, clock, lexicon_provider
):
    d = story.driver(assembled_client, db_session)
    d.create()
    assert d.journey["status"] == "active", d.journey
    lemmas = [entry["lemma"] for entry in _stored_lexicon(db_session, d)]
    assert lemmas == ["pluie", "vitre", "idée"]
    first = [p for schema, p in lexicon_provider.calls if schema == "SceneDraft"][-1]
    assert first["kept_words"] == [] and first["lexicon_history"] == []
    assert "rank_of" not in str(first), "the rank lookup never reaches a prompt"

    # The next scene's director is reminded of what this one taught.
    d.play(answer="Je peux apporter les affiches samedi.")
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    d.create()
    later = [p for schema, p in lexicon_provider.calls if schema == "SceneDraft"][-1]
    assert set(later["lexicon_history"]) >= {"pluie", "vitre", "idée"}


def _stored_lexicon(db_session, d) -> list[dict]:
    from uuid import UUID

    from app.db.models.daily_journey import DailyJourney

    row = db_session.get(DailyJourney, UUID(d.journey["id"]))
    for step in row.steps:
        brief = (step.private_task or {}).get("scenario_brief") or {}
        draft = (brief.get("story_context") or {}).get("draft") or {}
        if draft.get("lexicon") is not None:
            return list(draft["lexicon"])
    return []


def test_kept_words_reach_the_director(
    assembled_client, db_session, journey_enabled, clock, lexicon_provider
):
    from app.db.models.user import User
    from app.db.models.vocabulary import VocabularyWord
    from app.services.kept_words import keep_word

    d = story.driver(assembled_client, db_session)
    db_session.add(
        VocabularyWord(language="fr", word="parapluie", normalized_word="parapluie",
                       english_translation="umbrella", difficulty_level=1)
    )
    db_session.flush()
    keep_word(
        db_session,
        user=db_session.get(User, d.user_id),
        term="parapluie",
        sentence="Romy secoue son parapluie sur le seuil.",
    )
    db_session.commit()
    d.create()
    payload = [p for schema, p in lexicon_provider.calls if schema == "SceneDraft"][-1]
    assert payload["kept_words"] == [
        {"word": "parapluie", "gloss": "umbrella", "example_fr": "Romy secoue son parapluie sur le seuil."}
    ]
