"""Reader and Feuilleton text, night shift 2026-10-21 (#263, #268).

#263  The reader printed the director's scratch note as a panel caption
      («Le Mistral à nous 40 × 1 000 € Margaux Mme Diallo le petit Augustin (!)
      Marin — il dira oui en pleurant M. M. : oui, si Margaux reste.»).
      Root cause: ``Panel.narration_fr`` is one free-text field that the model
      fills with whatever it has; nothing told a line of the scene from a note
      about it before the text was stored and read aloud to the learner.

#268  Two chapters printed the same blurb, cut after «Alors,…». Root cause: the
      chronicle row cut every field at a character limit (``_one_line``), and
      every season tentpole carries the season's one question as its chapter
      question, so each closed tentpole chapter filed the same question.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine
from app.services import story_archive
from tests import test_living_story

NOTE = (
    "Le Mistral à nous 40 × 1 000 € Margaux Mme Diallo le petit Augustin (!) Marin — "
    "il dira oui en pleurant M. M. : oui, si Margaux reste."
)
#: The A1 form of the season's question, as the screenshot cut it.
SEASON_QUESTION = (
    "Ta grand-mère te donne son appartement. Il est sur un café. Dans ce café, il y a "
    "l'histoire d'un feu. Alors, tu gardes l'appartement, tu le partages ou tu le laisses partir ?"
)


def _context():
    return test_living_story._scene_context()


def _draft_with_narration(text: str):
    raw = test_living_story.draft(_context(), 0)
    raw["panels"][0]["narration_fr"] = text
    return engine.SceneDraft.model_validate(raw)


def _every_learner_text(draft) -> list[str]:
    return [
        draft.premise_fr,
        draft.opening_line_fr,
        *[panel.narration_fr for panel in draft.panels],
        *[line.text_fr for panel in draft.panels for line in panel.dialogue],
    ]


def test_a_planning_note_never_becomes_a_panel_caption():
    """#263 done-when: a generated beat carrying notes reaches no reader caption."""

    draft = _draft_with_narration(NOTE)
    engine._validate_scene(draft, _context())
    printed = " ".join(_every_learner_text(draft))
    assert "(!)" not in printed, "the director's note reached the caption"
    assert "40 ×" not in printed and "il dira oui" not in printed


def test_real_narration_is_kept_whole():
    """The guard drops notes, never prose: a normal caption and a figure in a sentence stay."""

    for text in (
        "La pluie glisse sur la vitre.",
        "Margaux compte quarante euros dans la caisse, puis encore quarante.",
        "Le café ouvre à huit heures : Augustin sert le premier crème.",
        "Il est 8 h 30. Lila attend devant la porte.",
    ):
        draft = _draft_with_narration(text)
        engine._validate_scene(draft, _context())
        assert draft.panels[0].narration_fr == text


def test_a_note_in_a_side_field_is_dropped_before_it_can_be_stored():
    """The raw JSON path: a model's extra ``notes`` / ``plan`` key on a panel is repaired away."""

    raw = test_living_story.draft(_context(), 0)
    raw["panels"][0]["notes"] = NOTE
    raw["panels"][0]["plan"] = "Marin dira oui"
    repaired, _notes = engine.tolerant_scene_json(raw)
    draft = engine.SceneDraft.model_validate(repaired)
    assert NOTE not in " ".join(_every_learner_text(draft))


def test_a_chapter_digest_ends_on_a_full_sentence():
    """#268: «Alors,… →» — the digest is never cut mid-sentence."""

    chapter = {"id": "c1", "title_fr": "Le mauvais accueil", "dramatic_question": SEASON_QUESTION}
    draft = engine.SceneDraft.model_validate(test_living_story.draft(_context(), 0))
    turn = engine.SemanticTurn.model_validate(test_living_story.turn_fixture("D'accord."))
    row = engine.chapter_digest(chapter, draft, turn, event_id="e1", day=1)
    line = engine.chapter_digest_line(row)
    question, _arrow, resolved = line.partition(" → ")
    assert question.rstrip().endswith("?"), question
    assert "Alors,…" not in line and ",…" not in line
    assert resolved and not resolved.rstrip().endswith(",…")


def test_two_tentpole_chapters_do_not_file_the_same_question():
    """#268: every tentpole carries the season's question; the second chapter's blurb
    comes from its own scene, so no two chapters read alike."""

    turn = engine.SemanticTurn.model_validate(test_living_story.turn_fixture("D'accord."))
    rows: list[dict] = []
    for index, premise in enumerate(
        ("Tu arrives devant le café, la clé à la main.", "Tu montes l'escalier d'Odile, une marche après l'autre.")
    ):
        raw = test_living_story.draft(_context(), index)
        raw["premise_fr"] = premise
        draft = engine.SceneDraft.model_validate(raw)
        chapter = {
            "id": f"c{index}",
            "title_fr": f"Chapitre {index}",
            "dramatic_question": SEASON_QUESTION,
            "resolved": True,
            "scene_count": 3,
        }
        rows = engine.chronicle_after_chapter(
            rows, chapter=chapter, draft=draft, turn=turn, event_id=f"e{index}", day=index + 1
        )
    lines = [engine.chapter_digest_line(row) for row in rows]
    assert len(lines) == 2
    assert lines[0] != lines[1]
    assert rows[0]["question"] != rows[1]["question"]


def test_a_stored_digest_cut_mid_sentence_is_read_back_whole():
    """#268, rows written before the fix: the cut «Alors,…» half is dropped at read time."""

    stored = (
        "Ta grand-mère te donne son appartement. Il est sur un café. Dans ce café, il y a "
        "l'histoire d'un feu. Alors,… → Odile: un plan. Une question pour Lila. À suivre…"
    )
    chapter = story_archive.chapter_of({"chapter": {"index": 3, "title_fr": "Là-haut", "digest_fr": stored}})
    digest = chapter["digest_fr"]
    assert ",…" not in digest
    assert digest.startswith("Ta grand-mère te donne son appartement.")
    assert digest.endswith("À suivre…")
    assert "Alors" not in digest


@pytest.mark.parametrize("text", ["La clé est retrouvée.", "Qui a pris la clé ?", "À suivre…"])
def test_a_whole_digest_is_left_as_written(text):
    chapter = story_archive.chapter_of({"chapter": {"index": 1, "title_fr": "x", "digest_fr": text}})
    assert chapter["digest_fr"] == text


def test_no_two_archive_chapters_share_a_blurb():
    """#268, rows written before the fix: chapter 3 repeats chapter 1's question; it opens on its title."""

    def chapter(index, title, digest):
        return story_archive._Chapter(key=f"k{index}", season=1, index=index, title_fr=title, digest_fr=digest)

    shared = "Tu gardes l'appartement, tu le partages ou tu le laisses partir ?"
    chapters = [
        chapter(1, "Le mauvais accueil", f"{shared} → Margaux se tait."),
        chapter(2, "Une habitude au zinc", "Quel est ton ordre au Mistral ? → Marin se souvient."),
        chapter(3, "Là-haut", f"{shared} → Odile: un plan. À suivre…"),
    ]
    story_archive._own_questions(chapters)
    digests = [row.digest_fr for row in chapters]
    assert len(set(digests)) == 3
    assert digests[0].startswith(shared), "the first chapter keeps the season's question"
    assert not digests[2].startswith(shared)
    assert digests[2].endswith("Odile: un plan. À suivre…")
