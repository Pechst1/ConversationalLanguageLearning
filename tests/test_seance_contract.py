"""Séance must teach its own tasks and never certify an unchecked answer."""
import pytest

from app.db.models.grammar import GrammarConcept
from app.services.atelier import (
    AtelierCorrectionService,
    AtelierExerciseGenerator,
    _is_vague_output_prompt,
)
from app.services.grammar_feedback import infer_grammar_profile
from app.services.seance_curriculum import curriculum


def concept_for(key):
    row = curriculum()[key]
    return GrammarConcept(id=1, external_id=key, name=row['name_en'], category=row['category'],
                          subskill=row['subskill'], core_rule=row['core_rule'], level=row['cefr_level'], language='fr')


@pytest.mark.parametrize('key', list(curriculum()))
def test_every_catalog_lesson_has_solvable_focused_material(key):
    concept = concept_for(key)
    generator = AtelierExerciseGenerator(None)
    payload = generator._fallback_payload(concept)
    row = curriculum()[key]
    assert not generator._payload_validation_errors(payload, concept)
    assert payload['rule_panel']['rule'] == row['core_rule']
    assert payload['rule_panel']['pattern'] == row['pattern']
    assert row['focus'] in payload['rule_panel']['examples'][0]
    assert row['source'] != row['sentence']
    for mode in ('fill', 'word_bank', 'classify'):
        assert len(payload['recognize'][mode]['items']) in {1, 3}
    for mode in ('sentence', 'speak', 'conversation'):
        item = payload['output_ladder'][mode]['items'][0]
        assert '?' in item['prompt']
        assert item['requirements'][0]['external_id'] == key


def test_incidental_en_does_not_turn_agreement_into_pronouns():
    concept = concept_for('FR_A1_NOUN_001')
    profile = infer_grammar_profile(concept, task_text="J'en ai visité. Use en.")
    assert profile.key == 'agreement'
    assert profile.pattern == curriculum()['FR_A1_NOUN_001']['pattern']
    en = infer_grammar_profile(concept_for('FR_A2_PRON_002'))
    assert 'en' in en.principle and 'y' in en.principle


@pytest.mark.parametrize('round_name', ['sentence', 'speak', 'conversation', 'produce'])
def test_offline_open_answer_is_unassessed_not_accepted(monkeypatch, round_name):
    service = AtelierCorrectionService(None)
    monkeypatch.setattr(service, '_get_llm_service', lambda: None)
    # Isolate the wrapper from storage and emulate the former unsafe fallback.
    fallback = {'verdict': 'accepted', 'score_0_4': 4, 'corrected_answer': 'there is no question to answer to',
                'errata': [], 'concept_hits': [{'detected_count': 1}], 'correction_debug': {'fallback_used': True}}
    monkeypatch.setattr(service, '_correct_output_ladder', lambda *args, **kwargs: dict(fallback))
    monkeypatch.setattr(service, '_correct_produce', lambda *args, **kwargs: dict(fallback))
    result = service.correct(concept=concept_for('FR_A1_NOUN_001'), round_name=round_name,
                             mode=round_name, exercise_id='test', prompt_payload={},
                             answer_payload={'text': 'there is no question to answer to'})
    assert result['verdict'] == 'needs_review'
    assert result['assessment_status'] == 'unavailable'
    assert result['corrected_answer'] == ''
    assert result['concept_hits'] == []
    assert service._initial_ai_review(round_name=round_name, answer_payload={}, correction=result)['status'] == 'failed'


def test_checker_receives_entire_paragraph_including_errors_at_end():
    text = 'Une phrase correcte. ' * 60 + 'Mais je exercer mon français.'
    assert AtelierCorrectionService._compact_llm_answer({'text': text})['text'] == text


@pytest.mark.parametrize('payload', [{}, {'verdict': 'accepted', 'score_0_4': 4, 'errata': []}])
def test_incomplete_model_assessment_is_rejected(payload):
    with pytest.raises(ValueError):
        AtelierCorrectionService(None)._normalize_llm_correction(payload, concepts=[], fallback={}, corrected_answer_mode='text')


def test_rejected_verdict_with_empty_errors_cannot_be_promoted():
    result = AtelierCorrectionService(None)._normalize_llm_correction(
        {'verdict': 'incorrect', 'score_0_4': 0, 'errata': [], 'corrected_answer': '', 'concept_hits': [], 'missing_targets': []},
        concepts=[], fallback={}, corrected_answer_mode='text')
    assert result['verdict'] == 'incorrect'


def test_missing_question_placeholder_is_rejected():
    assert _is_vague_output_prompt('Someone asks you a quick real-life question. Say one concrete French response.')


def test_final_writing_checks_only_its_visible_requirements():
    first = concept_for('FR_A1_NOUN_001')
    other = concept_for('FR_A2_PRON_002')
    visible = [{'concept_id': first.id, 'external_id': first.external_id, 'target_count': 1}]
    assert AtelierCorrectionService(None)._integrated_requirements([first, other], {'requirements': visible}) == visible


def test_character_decoration_preserves_real_question():
    from app.api.v1.endpoints.atelier import _with_serial_conversation
    concept = concept_for('FR_A2_PRON_002')
    payload = AtelierExerciseGenerator(None)._fallback_payload(concept)
    original = payload['output_ladder']['conversation']['items'][0]['prompt']
    decorated = _with_serial_conversation(payload, concept=concept, context={
        'character': {'name': 'Lila', 'register': 'vous'}, 'thread_id': 'test',
        'episode_index': 0, 'scene_context': 'Generic scene', 'opener': "J'ai besoin de votre avis.",
    })
    assert decorated['output_ladder']['conversation']['items'][0]['prompt'] == original


def test_whole_sentence_repair_matches_screen_and_queues_retrieval(db_session):
    from uuid import uuid4

    from app.db.models.atelier import AtelierAttempt, AtelierSession
    from app.db.models.user import User

    user = User(id=uuid4(), email=f'{uuid4()}@example.com', hashed_password='test')
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(atelier_session_id=session.id, user_id=user.id,
                             round='sentence', mode='sentence', exercise_id='repair-contract',
                             verdict='partial', score_0_4=2, answer_payload={'text': 'Je acheter deux pomme.'},
                             correction_payload={
                                 'assessment_status': 'checked', 'corrected_answer': "J'achète deux pommes.",
                                 'errata': [{'corrected_target': "J'achète", 'task_error_type': 'verb_form'},
                                            {'corrected_target': 'pommes', 'task_error_type': 'agreement'}],
                             })
    db_session.add(attempt)
    db_session.commit()
    service = AtelierCorrectionService(db_session)
    result = service.record_micro_repair(attempt=attempt, text="J'achète deux pommes.", erratum_index=0)
    assert result.correction_payload['micro_repairs']['0']['status'] == 'ok'
    assert result.correction_payload['retest']['status'] == 'queued'
    assert result.correction_payload['retest']['due_after_completed'] == 3
    assert result.score_0_4 == 2  # copying is not mastery evidence
    with pytest.raises(ValueError):
        service.record_micro_repair(attempt=attempt, text='pommes', erratum_index=-1)


def test_future_drill_feedback_does_not_teach_passe_compose():
    concept = concept_for('FR_B1_TENSE_002')
    payload = AtelierExerciseGenerator(None)._fallback_payload(concept)
    item = payload['recognize']['fill']['items'][0]
    correction = AtelierCorrectionService(None)._correct_recognize(
        concept, 'fill', {'items': [item]}, {'answers': {item['id']: 'avions'}})
    reason = correction['errata'][0]['why_wrong']
    assert 'future' in reason.lower()
    assert 'passé composé' not in reason.lower()
