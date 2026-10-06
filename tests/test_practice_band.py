# ruff: noqa: F811 - the journey fixtures are imported by name and requested as arguments
"""Practice band — a scene word above the learner's band is read, never tested.

The forced-outage A1 walk carried a learner into T5 day B, whose bible lexicon
names «adieu» (B1): the day posed it as a listen-and-tap and a gender sort. A
line may still *show* such a word with its gloss; an item never makes it the
answer. The product rule (``practice_band``) and the walk's ``check_level``
(``walk_checks.item_words_above``) read the same bands.
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.session import WordInteraction
from app.db.models.user import User
from app.services import journey_learning
from app.services.kept_words import SCENE_LEXICON_INTERACTION_TYPE
from app.services.practice_band import at_band, words_above
from app.services.scene_items import floor_tasks
from tests.test_journey_end_to_end import assembled_client, learner_id, register  # noqa: F401
from tests.test_journey_planner import _brief, _candidate
from tests.walk_checks import item_words_above

DRAFT = {
    "premise_fr": "Lila lit la carte devant le train.",
    "character_id": "lila_bonnet",
    "opening_line_fr": "Tu prends le train ce soir ?",
    "panels": [
        {
            "narration_fr": "",
            "dialogue": [
                {"character_id": "lila_bonnet", "text_fr": "Ce n'est pas un adieu, Marin."},
                {"character_id": "marin_leveque", "text_fr": "Le train part à huit heures."},
            ],
            "visual_direction": "x",
        },
    ],
    "lexicon": [
        {"surface_fr": "adieu", "lemma": "adieu", "gloss_native": "Abschied",
         "part_of_speech": "noun", "gender": "m", "line_ref": "panel:0:line:0"},
        {"surface_fr": "train", "lemma": "train", "gloss_native": "Zug",
         "part_of_speech": "noun", "gender": "m", "line_ref": "panel:0:line:1"},
        {"surface_fr": "carte", "lemma": "carte", "gloss_native": "Karte",
         "part_of_speech": "noun", "gender": "f", "line_ref": "premise"},
        {"surface_fr": "pas", "lemma": "pas", "gloss_native": "nicht",
         "part_of_speech": "adverb", "line_ref": "panel:0:line:0"},
    ],
}
CAST = [
    {"id": "lila_bonnet", "name": "Lila"},
    {"id": "marin_leveque", "name": "Marin"},
]


def _scene(level: str):
    return _brief(story_context={"draft": DRAFT, "source": {"world": {"cast": CAST}}}, level_band=level)


def _targets():
    rows = [("un adieu", "adieu", "Abschied"), ("le train", "train", "Zug"), ("la carte", "carte", "Karte")]
    return [
        (candidate.target, candidate.metadata)
        for candidate in (
            _candidate(
                identifier=f"pb{index}", label_fr=label, label_native=gloss, priority=0.0,
                due_since_days=0, is_new=True, relevance=1.0,
                metadata={"surface_fr": surface, "anchor": "scene_lexicon"},
            )
            for index, (label, surface, gloss) in enumerate(rows)
        )
    ]


def _answers(task) -> str:
    return " ".join(task.accepted_answers or [])


def test_an_above_band_scene_word_is_never_the_answer_at_a1() -> None:
    tasks = floor_tasks(_scene("A1"), _targets())
    assert tasks, "the at-band words still give the floor items"
    for _target, task in tasks:
        assert "adieu" not in _answers(task).casefold(), task
        assert not item_words_above(_answers(task), "A1"), task
    # The at-band words are still practised: «train» from its own line.
    assert any("train" in _answers(task) for _t, task in tasks)


def test_a_line_may_still_show_the_word_it_does_not_test() -> None:
    # A cloze on «carte» blanks its own sentence; nothing hides the scene's
    # «adieu» line from reading. The rule is about answers, not about text.
    tasks = floor_tasks(_scene("A1"), _targets())
    assert all(task.task_type in {"choice", "unscramble"} for _t, task in tasks)
    assert "adieu" in json.dumps(DRAFT, ensure_ascii=False)


def test_the_same_word_is_practised_at_its_own_band() -> None:
    tasks = floor_tasks(_scene("B1"), _targets())
    assert any("adieu" in _answers(task).casefold() for _t, task in tasks), (
        "a B1 learner is tested on «adieu»: the filter is a band, not a ban"
    )


def test_the_floor_is_not_padded_for_a_dropped_item() -> None:
    a1 = floor_tasks(_scene("A1"), _targets())
    b1 = floor_tasks(_scene("B1"), _targets())
    assert len(a1) < len(b1), "the dropped items are gone, not replaced"
    assert {t.id for t, _task in a1} <= {t.id for t, _task in b1}


def test_scene_lexicon_candidates_drop_the_above_band_word(
    assembled_client: TestClient, db_session: Session
) -> None:
    email = f"band-{uuid.uuid4().hex[:8]}@example.com"
    register(assembled_client, email)
    user = db_session.get(User, learner_id(db_session, email))
    user.native_language = "de"
    db_session.commit()

    def candidates(level: str):
        return journey_learning._scene_lexicon_candidates(
            db_session, user=user, scenario=_scene(level), exclude=set(), history={}
        )

    a1 = candidates("A1")
    labels = [c.target.label_fr for c in a1]
    assert labels and not any("adieu" in label for label in labels), labels
    assert len(a1) == len(DRAFT["lexicon"]) - 1, "one word fewer, nothing looked up in its place"
    assert all(at_band(c.target.label_fr, "A1") for c in a1)
    examples = {c.target.label_fr: c.metadata.get("example_fr") for c in a1}
    assert examples["le train"] == "Le train part à huit heures.", "an at-band line is still rebuilt"
    assert examples["pas"] is None, "an at-band word is not rebuilt from the «adieu» line"
    # The scene still shows it with its gloss (the draft is untouched), but it is
    # not recorded as taught: «met in the story» is what the drill introduces first.
    recorded = {
        row.user_response
        for row in db_session.query(WordInteraction).filter_by(
            user_id=user.id, interaction_type=SCENE_LEXICON_INTERACTION_TYPE
        )
    }
    assert "train" in recorded and "adieu" not in recorded
    b1 = candidates("B1")
    assert any("adieu" in c.target.label_fr for c in b1)


def test_product_rule_and_walk_check_agree_on_the_season_lexicon() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app" / "data" / "season" / "s1"
    surfaces: set[str] = set()
    for path in sorted(root.glob("*.json")):
        stack = [json.loads(path.read_text(encoding="utf-8"))]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if isinstance(node.get("surface_fr"), str):
                    surfaces.add(node["surface_fr"])
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    assert len(surfaces) > 50
    for level in ("A1", "A2", "B1"):
        for surface in sorted(surfaces):
            text = surface.lower()
            assert words_above(text, level) == item_words_above(text, level), (surface, level)


def test_a_verb_form_is_its_verb_s_word_not_its_noun_homograph() -> None:
    # «garde» (noun, B2) and «signe» (noun, B2) are also «garder»/«signer» (A2);
    # «écoute» (noun, C1) is «écouter» (A1). The verb form is in band.
    assert at_band("Je le garde.", "A2")
    assert at_band("Si je ne signe pas, je suis libre.", "A2")
    assert at_band("Écoute, Marin.", "A1")
    assert words_above("Ce n'est pas un adieu.", "A1") == ["adieu"]
    assert words_above("Le matin, au canal.", "A1") == ["canal"]
    assert not words_above("Le matin, au canal.", "B1")
