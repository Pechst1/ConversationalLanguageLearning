import pytest

from app.core.conversation import (
    build_error_detection_prompt,
    build_error_detection_schema,
    build_few_shot_examples,
    build_system_prompt,
)


def test_build_system_prompt_known_style():
    prompt = build_system_prompt("travel", "B1")

    assert "Camille" in prompt
    assert "CEFR level B1" in prompt


def test_build_system_prompt_unknown_style():
    with pytest.raises(KeyError):
        build_system_prompt("unknown", "A2")


def test_build_few_shot_examples_includes_vocabulary():
    examples = build_few_shot_examples(["hôtel", "train"], "A2")

    assert examples[0]["role"] == "system"
    assert "hôtel" in examples[0]["content"]
    assert len(examples) == 3


def test_build_error_detection_prompt_lists_targets():
    prompt = build_error_detection_prompt("Je suis aller au marché.", ["aller", "marché"], "B1")

    assert "Je suis aller" in prompt
    assert "- aller" in prompt
    assert "learner level is B1" in prompt


def test_error_detection_schema_structure():
    schema = build_error_detection_schema()

    assert schema["type"] == "object"
    assert "errors" in schema["properties"]
    error_item = schema["properties"]["errors"]["items"]
    assert "category" in error_item["properties"]
    assert "summary" in schema["required"]
