"""#1081: the Journal glued a scene's lines into one quotation and printed the title three times.

Live walk 26 Nov (A1.1, day 44), retell of «Dix heures» at Le Mistral: the dashed card said
«Margaux te regarde. « Il manque quelque chose : Tu as peur de Marchand. Merci. Merci. Et
Marchand signe à dix heures. Oui. »»: several people's lines, glued, in Margaux's mouth.
«What you remember» listed that glued line as one detail, and «The scene as it was» printed
«Dix heures», «Dix heures», «« Dix heures »». The fake stack showed the same on day 1: two
of Margaux's lines in Gus's mouth.

A turn stores who says each of its lines (``lines``, #313); the Journal read only the turn's
words, run together, and gave them to the cue's character. The reveal copied the page's
prompt fields, which an authored page from before #1074 filled with its title.

Done when: from a scene titled «Dix heures» with several spoken lines, the title appears at
most as a heading, no line is printed twice, every quoted line has its own speaker, and the
detail a retell is checked against is one sentence, never lines joined.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.journal import (
    character_reaction,
    scene_facts_for,
    scene_reveal,
    score_content_recall,
    sentence_count,
)

TITLE = "Dix heures"
SPOKEN = [
    ("margaux", "Margaux", "Tu as peur de Marchand."),
    ("romy", "Romy", "Merci."),
    ("romy", "Romy", "Merci."),
    ("camille", "Camille", "Et Marchand signe à dix heures."),
    ("margaux", "Margaux", "Oui."),
]
RETELL = (
    "Hier, Margaux et moi, nous avons parlé de M. Marchand. Il veut me parler du bail. "
    "Je ai dit non, et Romy a ri."
)


def _journey(*, cue_character: str = "Margaux", spoken=SPOKEN):
    lines = [{"speaker_id": who, "speaker_name": name, "text_fr": text} for who, name, text in spoken]
    respond = SimpleNamespace(
        ordinal=1,
        kind="respond",
        public_prompt={},
        private_task={
            "turns": [
                {
                    "learner": "Oui, j'ai peur.",
                    "character": "\n".join(line["text_fr"] for line in lines),
                    "lines": lines,
                    "correction": None,
                }
            ],
            "ledger": {},
        },
    )
    # An authored page planned before #1074: its title stood in for the setup and the line.
    scene = SimpleNamespace(
        ordinal=0,
        kind="scene",
        public_prompt={"setup_fr": TITLE, "character_line_fr": TITLE, "character_id": "margaux"},
        private_task={},
    )
    return SimpleNamespace(
        scenario_snapshot={"title_fr": TITLE, "character_name": cue_character, "location_name": "Le Mistral"},
        recap_snapshot={},
        serial_episode_id="ep-44",
        steps=[scene, respond],
    )


def _printed(reveal: dict) -> list[str]:
    """Every line «The scene as it was» prints under its heading."""
    out = [reveal.get("setup_fr"), reveal.get("character_line_fr"), reveal.get("callback_fr")]
    out += [line.get("text_fr") for line in reveal.get("lines") or []]
    return [str(text) for text in out if text]


def test_title_is_only_a_heading():
    reveal = scene_reveal(_journey())
    assert reveal["title_fr"] == TITLE
    assert TITLE not in _printed(reveal), reveal


def test_reveal_has_the_spoken_lines_once_each_with_its_speaker():
    reveal = scene_reveal(_journey())
    lines = reveal.get("lines") or []
    texts = [line["text_fr"] for line in lines]
    assert "Et Marchand signe à dix heures." in texts, reveal
    assert len(_printed(reveal)) == len(set(_printed(reveal))), f"a line printed twice: {reveal}"
    assert all(line.get("speaker_name") for line in lines), lines
    said_by = {line["text_fr"]: line["speaker_name"] for line in lines}
    assert said_by["Et Marchand signe à dix heures."] == "Camille"
    assert said_by["Tu as peur de Marchand."] == "Margaux"


def test_each_detail_is_one_sentence():
    facts = scene_facts_for(_journey(), story_context={})
    scene = [fact for fact in facts if fact.kind == "scene"]
    assert scene, facts
    for fact in scene:
        assert sentence_count(fact.text_fr) == 1, fact.text_fr
        assert "Merci. Merci." not in fact.text_fr


def test_reaction_quotes_one_detail_and_names_who_said_it():
    facts = [fact.as_dict() for fact in scene_facts_for(_journey(cue_character="Gus"), story_context={})]
    recall = score_content_recall(RETELL, facts)
    line = character_reaction(character_name="Gus", recall=recall)
    assert line is not None and "Il manque quelque chose" in line, line
    assert "Merci. Merci." not in line
    missed = recall["missed"][0]
    assert sentence_count(missed["text_fr"]) == 1, missed
    if missed.get("speaker_name") and missed["speaker_name"] != "Gus":
        assert missed["speaker_name"] in line, f"Gus quotes {missed['speaker_name']}'s line as his own: {line}"
    assert any(item.get("speaker_name") for item in recall["missed"] + recall["matched"]), recall


def test_old_snapshot_drops_the_repeated_title():
    from app.services.journal import reveal_view

    stored = {"title_fr": TITLE, "setup_fr": TITLE, "character_line_fr": TITLE, "callback_fr": None}
    shown = reveal_view(stored)
    assert shown["title_fr"] == TITLE
    assert TITLE not in _printed(shown), shown


def test_details_come_from_different_turns():
    """Review of #1097: two details are two moments of the scene, not two sentences of
    its last reply (often its goodbye)."""

    journey = _journey()
    earlier = journey.steps[1].private_task["turns"][0]
    last_lines = [
        {"speaker_id": "camille", "speaker_name": "Camille", "text_fr": "Le notaire arrive demain matin."},
        {"speaker_id": "camille", "speaker_name": "Camille", "text_fr": "Je garde la clé du bureau."},
    ]
    journey.steps[1].private_task["turns"] = [
        earlier,
        {
            "learner": "Bien.",
            "character": "\n".join(line["text_fr"] for line in last_lines),
            "lines": last_lines,
            "correction": None,
        },
    ]
    scene = [fact for fact in scene_facts_for(journey, story_context={}) if fact.kind == "scene"]
    turns = {fact.key.rsplit(":", 1)[0] for fact in scene}
    assert len(scene) == 2 and len(turns) == 2, [(fact.key, fact.text_fr) for fact in scene]
