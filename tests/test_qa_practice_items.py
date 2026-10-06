"""QA-PRACTICE (owner test, 2026-10-03, German native, A1): the journey's practice
items said things a learner could not use. One regression per finding."""

from __future__ import annotations

from types import SimpleNamespace

from app.db.models.vocabulary import VocabularyWord
from app.services import journey_learning
from app.services import journey_planner as planner
from app.services.daily_journey import DailyJourneyService
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    RecallTask,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from app.services.scene_items import (
    SceneLine,
    build_line_unscramble_task,
    floor_tasks,
    line_meanings,
    meaning_of,
)
from tests.test_journey_planner import _brief, _candidate

GERMAN_A1 = SimpleNamespace(native_language="de", cefr_estimate="A1.1", proficiency_level="A1")


def _vocab(label_fr: str, label_native: str | None, identifier: str = "w1") -> TargetRef:
    return TargetRef(kind=TargetKind.VOCABULARY, id=identifier, label_fr=label_fr, label_native=label_native)


# -- 1. «Wer hat das gesagt?» is no longer dealt --------------------------------

SEASON_DRAFT = {
    "premise_fr": "Marin regarde la lettre.",
    "character_id": "marin_leveque",
    "opening_line_fr": "Vous êtes la petite-fille d'Odile ?",
    "panels": [
        {
            "narration_fr": "",
            "dialogue": [
                {
                    "character_id": "marin_leveque",
                    "text_fr": "L'appartement d'Odile, pour Solvel ? C'est vrai ?",
                    # Translated from the same served line — what an A1 page carries.
                    "text_native": "Odiles Wohnung, für Solvel? Stimmt das?",
                },
                {
                    "character_id": "lila_bonnet",
                    "text_fr": "Je vends l'appartement demain.",
                    "text_native": None,
                },
            ],
            "visual_direction": "x",
        }
    ],
    "lexicon": [
        {"surface_fr": "appartement", "lemma": "appartement", "gloss_native": "Wohnung",
         "part_of_speech": "noun", "gender": "m", "line_ref": "panel:0:line:0"},
        {"surface_fr": "lettre", "lemma": "lettre", "gloss_native": "Brief",
         "part_of_speech": "noun", "gender": "f", "line_ref": "premise"},
    ],
}
CAST = [{"id": "marin_leveque", "name": "Marin Lévêque"}, {"id": "lila_bonnet", "name": "Lila"}]


def _season_brief(**overrides):
    return _brief(
        story_context={"draft": SEASON_DRAFT, "source": {"world": {"cast": CAST}}},
        control_language="de",
        **overrides,
    )


def test_the_scene_floor_never_deals_who_said_any_more() -> None:
    targets = [(_vocab("un appartement", "Wohnung", "a"), {"surface_fr": "appartement"}),
               (_vocab("une lettre", "Brief", "l"), {"surface_fr": "lettre"})]
    tasks = floor_tasks(_season_brief(), targets)
    kinds = [task.task_type for _t, task in tasks]
    assert kinds and "who_said" not in kinds
    assert "unscramble" in kinds


# -- 2. A wrong unscramble shows the sentence, and only its own translation -------

def _line_task(meaning: str | None) -> RecallTask:
    line = SceneLine("marin_leveque", "L'appartement d'Odile, pour Solvel ? C'est vrai ?", "panel:0:line:0")
    task = build_line_unscramble_task(
        target=_vocab("un appartement", "Wohnung"), line=line, speaker_name="Marin Lévêque",
        optional=True, control_language="de", meaning=meaning,
    )
    assert task is not None
    return task


def test_a_wrong_unscramble_is_corrected_with_the_sentence_and_where_it_went_wrong() -> None:
    task = _line_task(None)
    order = list(task.correct_tile_order)
    wrong = [order[1], order[0], *order[2:]]
    answer = AttemptAnswer(mode=InputMode.TEXT, text="", tile_ids=wrong)
    evaluation = journey_learning.evaluate_recall(
        None, user=GERMAN_A1, task=task, answer=answer, assistance=AssistanceLevel.NONE
    )
    assert evaluation.outcome is TaskOutcome.NOT_YET
    correction = evaluation.correction
    assert correction is not None
    assert correction.corrected_fr == "L'appartement d'Odile, pour Solvel ? C'est vrai ?"
    # The words the learner placed, never tile ids.
    assert "tile_" not in correction.span_fr and correction.span_fr.startswith("d'Odile,")
    assert correction.note_native == (
        "Der Satz beginnt nicht mit „d'Odile,“. Oben steht die richtige Reihenfolge."
    )
    # And it survives the public filter the attempt response goes through.
    shown = DailyJourneyService._public_correction(
        correction, journey_learning.recall_learner_text(task, answer)
    )
    assert shown is not None and shown.corrected_fr == correction.corrected_fr
    # A shuffle is not the learner's own French: no erratum is made of it.
    assert all(o.task_format == "unscramble" for o in evaluation.observations)


def test_a_later_slip_names_the_first_misplaced_word() -> None:
    task = _line_task(None)
    order = list(task.correct_tile_order)
    wrong = [order[0], order[2], order[1], *order[3:]]
    note = journey_learning.tile_order_note(task, wrong, "de")
    texts = {o["id"]: o["text_fr"] for o in task.options}
    assert note == f"Ab „{texts[order[2]]}“ stimmt die Reihenfolge nicht mehr. Oben steht die richtige."
    assert journey_learning.tile_order_note(task, wrong, "en").startswith("From “")


def test_a_scene_line_takes_only_its_own_translation() -> None:
    brief = _season_brief()
    meanings = line_meanings(brief)
    line = "L'appartement d'Odile, pour Solvel ? C'est vrai ?"
    assert meaning_of(meanings, line) == "Odiles Wohnung, für Solvel? Stimmt das?"
    # A line the page did not translate gets none — never a neighbour's.
    assert meaning_of(meanings, "Je vends l'appartement demain.") is None
    assert meaning_of(meanings, "Vous voulez vraiment vendre l'appartement d'Odile ?") is None
    task = _line_task(meaning_of(meanings, line))
    assert "Odiles Wohnung, für Solvel? Stimmt das?" in (task.goal_native or "")
    assert "Bau nach, was Marin gesagt hat" in task.goal_native


def test_a_translation_that_is_the_french_itself_is_no_translation() -> None:
    draft = {**SEASON_DRAFT, "translation_native": SEASON_DRAFT["opening_line_fr"]}
    brief = _brief(story_context={"draft": draft}, control_language="de")
    assert meaning_of(line_meanings(brief), SEASON_DRAFT["opening_line_fr"]) is None


# -- 3. «Wie sagt man „Wohnung“?» -------------------------------------------------

def _short_answer(label_fr: str, label_native: str) -> RecallTask:
    task = planner.build_recall_task(
        target=_vocab(label_fr, label_native), scenario=_brief(control_language="de"),
        affordances=[], optional=False,
    )
    assert task is not None and task.task_type == "short_answer"
    return task


def _grade(task: RecallTask, text: str) -> TaskOutcome:
    return journey_learning.evaluate_recall(
        None, user=GERMAN_A1, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text), assistance=AssistanceLevel.NONE,
    ).outcome


def test_a_noun_asked_without_an_article_is_right_with_any_article_or_none() -> None:
    task = _short_answer("un appartement", "Wohnung")
    for typed in ("appartement", "l'appartement", "L’appartement", "l‘appartement",
                  "un appartement", "Appartement", "le appartement", "  APPARTEMENT "):
        assert _grade(task, typed) is TaskOutcome.MET, typed
    assert _grade(task, "L'appar") is TaskOutcome.NOT_YET
    assert _grade(task, "maison") is TaskOutcome.NOT_YET


def test_a_gloss_that_names_its_article_still_asks_for_one() -> None:
    task = _short_answer("un appartement", "eine Wohnung")
    assert _grade(task, "un appartement") is TaskOutcome.MET
    assert _grade(task, "appartement") is TaskOutcome.NOT_YET


def test_the_hint_names_the_noun_and_counts_words_in_proper_german() -> None:
    noun = planner._hint_for(_vocab("un appartement", "Wohnung"), "de")
    assert noun == "Ein Nomen, das mit „a“ beginnt (der Artikel ist freiwillig)."
    assert "„u“" not in noun
    assert planner._hint_for(_vocab("un appartement", "Wohnung"), "en").startswith('A noun starting with "a"')
    phrase = planner._hint_for(_vocab("je voudrais", "ich möchte"), "de")
    assert phrase == "Es ist 2 Wörter lang und beginnt mit „j“."
    assert planner._hint_for(_vocab("vendre", "verkaufen"), "de") == "Es ist 1 Wort lang und beginnt mit „v“."
    assert planner._hint_for(_vocab("je voudrais", "I would like"), "en") == 'It is 2 words long and starts with "j".'
    assert planner._hint_for(_vocab("vendre", "to sell"), "en") == 'It is 1 word long and starts with "v".'
    assert planner._hint_for(_vocab("je voudrais", "je voudrais"), "fr").startswith("C'est 2 mots")
    for language in ("en", "de", "fr"):
        for count in (1, 2, 5):
            assert "(" not in planner.word_count_phrase(count, language)
            assert "/" not in planner.word_count_phrase(count, language)


# -- 4. The rest of an A1 day ------------------------------------------------------

def test_choice_cards_share_the_answers_shape() -> None:
    target = _vocab("une lettre", "ein Brief")
    task = planner.build_recall_task(
        target=target, scenario=_season_brief(), affordances=["appartement", "clé", "vendre", "une maison"], optional=False
    )
    assert task is not None and task.task_type == "choice"
    texts = sorted(option["text_fr"] for option in task.options)
    # «clé» has no gender in the scene's lexicon and «vendre» is a verb: dropped,
    # not shown bare beside «une lettre». WP-137 C-3: at A1 the other cards are
    # core nouns of the band, in the answer's shape.
    assert "une lettre" in texts and len(texts) == 3
    assert not {"clé", "vendre"} & set(texts)
    assert all(text.split()[0] in {"un", "une"} for text in texts), texts

    # Above A2 the scene's own phrases are the cards, as before.
    task = planner.build_recall_task(
        target=target, scenario=_season_brief(level_band="B1"),
        affordances=["appartement", "clé", "vendre", "une maison"], optional=False,
    )
    assert task is not None and task.task_type == "choice"
    assert sorted(option["text_fr"] for option in task.options) == ["un appartement", "une lettre", "une maison"]


def test_a_matching_grid_never_holds_one_word_twice() -> None:
    target = _vocab("un appartement", "eine Wohnung", "a1")
    pool = [
        _vocab("appartement", "Wohnung", "a2"),
        _vocab("une lettre", "ein Brief", "l1"),
        _vocab("la lettre", "Brief", "l2"),
        _vocab("une clé", "ein Schlüssel", "k1"),
        _vocab("je voudrais", "ich möchte", "j1"),
    ]
    partners = planner._gloss_partners(target, pool, 3)
    labels = [p.label_fr for p in partners]
    assert "appartement" not in labels
    assert not {"une lettre", "la lettre"} <= set(labels)
    assert len(partners) == 3


def test_tu_or_vous_is_not_asked_when_the_pronoun_is_printed() -> None:
    printed = planner.build_classify_task(
        target=_vocab("s'il vous plaît", "bitte"), optional=False, control_language="de"
    )
    assert printed is None


def test_a_german_learner_never_gets_an_english_gloss(db_session) -> None:
    english_only = VocabularyWord(language="fr", word="une lettre", normalized_word="une lettre",
                                  english_translation="a letter", difficulty_level=1)
    both = VocabularyWord(language="fr", word="une clé", normalized_word="une clé",
                          english_translation="a key", german_translation="ein Schlüssel", difficulty_level=1)
    db_session.add_all([english_only, both])
    db_session.flush()
    candidates = [
        _candidate(identifier=str(english_only.id), label_fr="une lettre", label_native="a letter"),
        _candidate(identifier=str(both.id), label_fr="une clé", label_native="a key"),
        _candidate(identifier="lexicon-x", label_fr="appartement", label_native="Wohnung"),
    ]
    checked = journey_learning._glosses_in_language(db_session, candidates, "de")
    glosses = [c.target.label_native for c in checked]
    assert glosses == [None, "ein Schlüssel", "Wohnung"]


def test_one_word_is_one_target_a_day() -> None:
    kept = journey_learning._one_target_per_word(
        [
            _candidate(identifier="deck", label_fr="un appartement", label_native="Wohnung"),
            _candidate(identifier="scene", label_fr="appartement", label_native="Wohnung"),
            _candidate(identifier="l1", label_fr="la lettre", label_native="Brief"),
            _candidate(identifier="l2", label_fr="lettre", label_native="Brief"),
            _candidate(identifier="l3", label_fr="l'eau", label_native="Wasser"),
        ]
    )
    assert [c.target.id for c in kept] == ["deck", "l1", "l3"]


def test_a_lone_question_mark_is_not_a_tile() -> None:
    from app.services.scene_items import tile_words

    assert tile_words("Vous allez vendre, non ?") == ["Vous", "allez", "vendre,", "non ?"]
    assert tile_words("« Bonjour ! » dit-il.") == ["Bonjour !", "dit-il."]
    task = planner.build_unscramble_task(
        target=_vocab("vendre", "verkaufen"), sentences=["Vous allez vendre, non ?"],
        optional=True, control_language="de",
    )
    assert task is not None
    assert "?" not in [option["text_fr"] for option in task.options]
    assert task.solution_fr == "Vous allez vendre, non ?"


def test_split_article_never_cuts_a_word() -> None:
    assert journey_learning.split_article("lettre") == (None, "lettre")
    assert journey_learning.split_article("une lettre") == ("une", "lettre")
    assert journey_learning.split_article("l’eau") == ("l'", "eau")
    assert journey_learning.split_article("lune") == (None, "lune")
    assert planner._hint_for(_vocab("lettre", "Brief"), "de") == "Es ist 1 Wort lang und beginnt mit „l“."


def test_german_transform_copy_uses_german_quotes() -> None:
    task = planner.build_transform_task(
        target=_vocab("s'il vous plaît", "bitte"), optional=False, control_language="de"
    )
    if task is not None:
        assert '"' not in task.instruction_native and '"' not in (task.hint_native or "")
