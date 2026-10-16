"""Phase 1, Maßstab: the prose detector (``app.services.season.prose_detector``).

What these tests pin, without a model, a database or a network:

* every machine line the stories plan quotes is found, with the right kind;
* nothing the owner wrote for season 1 is: every French line and caption of the
  tentpoles, the intro, the bridges and the epilogue, at every level the level files
  give it, and the cast's speech samples and refrains in ``world.json``;
* the CLI's counts over the paid live reads of 7 and 8 October are the baseline the
  plan measures against.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.season import prose_detector as detector
from app.services.season.levels import apply_levels, read_levels
from app.services.season.prose_detector import (
    TASK_MAX_WORDS,
    Hit,
    feedback,
    page_hits,
    reply_hits,
    task_words,
)

ROOT = Path(__file__).resolve().parents[1]
SEASON = ROOT / "app" / "data" / "season" / "s1"
EVIDENCE = ROOT / "docs" / "implementation" / "atelier-v2" / "evidence"

#: The kinds that read one line on its own (the rest need the page or the band).
LINE_KINDS = {"quiz_caption", "teacher_talk", "contract_words", "written_connector"}


def _page(*, caption: str = "", line: str = "", task: str = "", premise: str = "") -> dict:
    """The smallest page that puts a text where a reader meets it."""

    return {
        "premise_fr": premise,
        "panels": [
            {
                "narration_fr": caption,
                "dialogue": [{"character_id": "lila_bonnet", "text_fr": line}] if line else [],
            }
        ],
        "objective_native": task,
    }


def _kinds(hits: list[Hit]) -> set[str]:
    return {hit.kind for hit in hits}


# ---------------------------------------------------------------------------
# Every machine line the plan quotes is found
# ---------------------------------------------------------------------------

QUIZ_CAPTIONS = [
    "Tout le monde attend ta réponse.",
    "Le silence: la décision repose maintenant sur toi.",
    "Silence. Ta décision va décider du ton de l'article.",
    "C'est le moment : choisis ta commande habituelle en français.",
]


@pytest.mark.parametrize("text", QUIZ_CAPTIONS)
@pytest.mark.parametrize("place", ["caption", "premise"])
def test_a_caption_that_narrates_the_learners_turn_is_found(text, place):
    hits = page_hits(_page(**{place: text}), level="A1")
    assert "quiz_caption" in _kinds(hits), hits
    assert all(hit.blocking for hit in hits)


TEACHER_LINES = [
    "Dis une phrase avec «J'ai».",
    "Dis une phrase avec J'ai",
    "Dis-le en français, s'il te plaît.",
    "Juste une phrase courte, d'accord ?",
    "Écris une phrase sur la carte.",
]


@pytest.mark.parametrize("text", TEACHER_LINES)
@pytest.mark.parametrize("place", ["line", "caption", "task"])
def test_exercise_talk_is_found_in_a_line_a_caption_or_a_french_task(text, place):
    assert "teacher_talk" in _kinds(page_hits(_page(**{place: text}), level="A2"))


@pytest.mark.parametrize(
    "task",
    [
        "Say why you are staying, with a sentence that starts 'J'ai...'.",
        "Call the airline in French and say you need to move your ticket.",
        "Sag Margaux auf Französisch, warum du bleibst.",
        "Bilde einen Satz mit «J'ai».",
    ],
)
def test_exercise_framing_is_found_in_an_english_or_german_task(task):
    hits = page_hits(_page(task=task), level="A1")
    assert [hit.where for hit in hits if hit.kind == "teacher_talk"] == ["task"], hits


CONTRACT_LINES = [
    "Quelles conditions te rassureraient pour que j'écoute sans écrire ni publier ?",
    "Dis-moi si c'est possible et quelle condition tu veux que je respecte.",
    "Proposez à Romy les conditions pour qu'elle écoute et n'écrive rien, et donnez une "
    "raison brève et convaincante pour ces conditions.",
    "Donne ton avis sur l'avenir de l'appartement (garder/partager/vendre), explique "
    "brièvement pourquoi, et propose une condition claire si tu veux le garder.",
    "J'ai une condition.",
    "Il me faut un engagement concret.",
    "On signe un accord écrit ?",
    "Donne une raison.",
    "Explique brièvement.",
    "Explique pourquoi.",
    "Propose une condition.",
    "Propose un plan.",
    "Propose un accord.",
    "Propose un compromis.",
]


@pytest.mark.parametrize("text", CONTRACT_LINES)
@pytest.mark.parametrize("place", ["line", "caption", "task"])
def test_brief_and_contract_words_are_found_in_a_line_a_caption_or_a_task(text, place):
    assert "contract_words" in _kinds(page_hits(_page(**{place: text}), level="B1"))


@pytest.mark.parametrize(
    ("place", "text", "kind"),
    [
        ("caption", "Maintenant, c'est à toi.", "quiz_caption"),
        ("caption", "Lila attend une réponse avant de partir.", "quiz_caption"),
        ("caption", "Tout le monde attend un compromis concret.", "quiz_caption"),
        ("line", "Alors, réponds en une phrase.", "teacher_talk"),
        ("caption", "Un espace vide t'attend : propose un plan.", "contract_words"),
        (
            "task",
            "Décide maintenant si Lila peut partir et propose un accord précis.",
            "contract_words",
        ),
        ("line", "Tu peux me proposer un plan ?", "contract_words"),
    ],
)
def test_the_narrowed_rules_still_find_the_turn_and_the_brief(place, text, kind):
    assert kind in _kinds(page_hits(_page(**{place: text}), level="B1"))


@pytest.mark.parametrize(
    ("place", "text"),
    [
        # Someone waits, but not for the learner's turn.
        ("caption", "Tout le monde attend Marchand."),
        ("caption", "Lila attend une réponse de Berlin."),
        ("caption", "Marin attend la réponse du médecin."),
        ("caption", "Tu attends ton tour au comptoir."),
        ("caption", "C'est le moment de fermer."),
        ("caption", "Ta voix va trembler."),
        # A character's act, narrated: «propose», «explique» with a subject, told.
        ("caption", "Marin explique pourquoi la soupe est salée."),
        ("caption", "Marin pose la louche, propose un plan."),
        ("caption", "Romy soupire et propose un compromis."),
        ("caption", "Lila répond en expliquant pourquoi elle part."),
        ("line", "Marin résume tout en une phrase."),
        # A character's own words.
        ("line", "Ta phrase d'hier m'a touchée."),
        ("line", "C'est une phrase simple mais vraie."),
        ("line", "Je te le dis en une phrase : je reste."),
        ("line", "J'écris une phrase pour Odile."),
        ("line", "Je te propose un plan."),
        ("line", "Donne-moi une raison de rester."),
        ("line", "Donne une bonne raison de rester."),
        ("line", "Explique-moi pourquoi."),
        ("line", "Dans ces conditions, je pars."),
        ("line", "Je t'aime sans condition."),
    ],
)
def test_plain_french_is_not_a_machine_line(place, text):
    assert page_hits(_page(**{place: text}), level="B1") == []


CONNECTOR_LINES = [
    "La toile doit rester droite, sinon je deviens nerveux — néanmoins, on peut la déplacer.",
    "Toutefois, il faut un plan.",
    "Désormais, j'ai besoin de toi",
    "Tu peux commencer par dire ce que tu voulais protéger, notamment.",
    "Aussitôt qu'on fixe un délai, je ferme la caméra.",
]


@pytest.mark.parametrize("text", CONNECTOR_LINES)
@pytest.mark.parametrize("level", ["A1", "A2.1", "B1", "B1.2"])
def test_a_written_connector_in_speech_below_b2_is_found(text, level):
    hits = page_hits(_page(line=text), level=level)
    assert [hit.kind for hit in hits if hit.kind == "written_connector"] == ["written_connector"]


@pytest.mark.parametrize("text", CONNECTOR_LINES)
@pytest.mark.parametrize("level", ["B2", "C1.1"])
def test_from_b2_the_written_connectors_are_speech(text, level):
    assert "written_connector" not in _kinds(page_hits(_page(line=text), level=level))


def test_narration_may_use_the_written_register():
    """Only speech: a caption is written prose and may say «désormais»."""

    assert page_hits(_page(caption="Désormais, le café ferme le lundi."), level="A1") == []


def test_each_forced_connector_counts():
    hits = page_hits(
        _page(line="Toutefois, si elle veut parler seule, respectons ça. Notamment maintenant."),
        level="B1",
    )
    assert [hit.text for hit in hits if hit.kind == "written_connector"] == [
        "Toutefois, si elle veut parler seule, respectons ça.",
        "Notamment maintenant.",
    ]


def test_the_same_line_twice_on_a_page_is_found_whatever_its_punctuation():
    page = {
        "panels": [
            {
                "dialogue": [
                    {
                        "character_id": "marin_leveque",
                        "text_fr": "Alors ? Tu décides pour nous : on la protège ou on lui demande de parler ?",
                    }
                ]
            },
            {"dialogue": [{"character_id": "lila_bonnet", "text_fr": "Je ne sais pas."}]},
        ],
        "opening_line_fr": "Alors ? Tu décides pour nous : on la protège, ou on lui demande de parler ?",
    }
    hits = page_hits(page, level="B1")
    assert [(hit.kind, hit.where) for hit in hits] == [("repeated_line", "opening")]


def test_signature_phrases_never_count_as_repeated():
    world = json.loads((SEASON / "world.json").read_text(encoding="utf-8"))
    phrases = detector.signature_phrases(world)
    assert "J'ai rien entendu." in phrases and "La même chose ?" in phrases
    for phrase in phrases:
        page = {
            "panels": [
                {"dialogue": [{"character_id": "margaux_barman", "text_fr": phrase}]},
                {"dialogue": [{"character_id": "margaux_barman", "text_fr": phrase.upper()}]},
            ],
            "opening_line_fr": f"{phrase} ",
        }
        assert "repeated_line" not in _kinds(
            page_hits(page, level="A2", signature_phrases=phrases)
        ), phrase
        assert "repeated_line" in _kinds(page_hits(page, level="A2")), phrase


def test_a_task_over_twelve_words_is_found():
    assert TASK_MAX_WORDS == 12
    twelve = "Dis à Lila si tu restes au Mistral ce soir avec elle."
    thirteen = "Dis à Lila si tu restes au Mistral ce soir avec elle, oui."
    assert task_words(twelve) == 12 and task_words(thirteen) == 13
    assert "long_task" not in _kinds(page_hits(_page(task=twelve), level="A2"))
    assert [hit.where for hit in page_hits(_page(task=thirteen), level="A2")] == ["task"]


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("Défends ta décision : dis si Romy peut publier.", 8),  # «:» is not a word
        ("Say why you are staying, with a sentence that starts 'J'ai...'.", 11),
        ("Donne ton avis (garder/partager/vendre) aujourd'hui.", 7),  # three choices, three words
        ("Dis‑moi : tu restes ?", 3),
    ],
)
def test_task_words_count_words_not_punctuation(text, words):
    assert task_words(text) == words


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        (
            "Tu n'as pas encore dit pourquoi tu restes. On reprendra la question demain au Mistral.",
            "deferred_ending",
        ),
        ("Elle reviendra demain pour une phrase claire.", "deferred_ending"),
        ("Ça me touche. Reste ici si tu veux, on verra demain.", "deferred_ending"),
        (
            "Tout le monde attend toujours; la question reste ouverte pour demain.",
            "deferred_ending",
        ),
        (
            "Lila doit partir avant de répondre. La conversation reprendra là où elle s’est arrêtée.",
            "leaves_without_answer",
        ),
        (
            "Ah… ça me touche que tu restes. J'ai peur et je suis soulagé à la fois. Pardon ? Tu peux le redire autrement ?",
            "glued_self_repair",
        ),
        (
            "Oh bon, merci ! On commence tout de suite, alors ? Pardon ? Vous pouvez le redire autrement ?",
            "glued_self_repair",
        ),
    ],
)
def test_reply_side_endings_are_found_and_only_counted(text, kind):
    hits = reply_hits(text, where="resolution")
    assert [hit.kind for hit in hits] == [kind]
    assert not any(hit.blocking for hit in hits)


@pytest.mark.parametrize(
    "text",
    [
        "Pardon ? Tu peux le redire autrement ?",  # the repair alone is the whole turn: not glued
        "Ah, merci — ça me soulage. On commence demain après-midi : dix minutes en privé avec Lila.",
        "Marin hoche la tête, sert un café et note ton nom dans son carnet.",
    ],
)
def test_a_reply_that_closes_or_asks_again_is_not_counted(text):
    assert reply_hits(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "Elle hésite avant de répondre, puis sourit : elle reste.",
        "La porte reste ouverte et Marin éteint la radio.",
        "Lila attend la réponse de la banque, mais elle a choisi : elle part.",
    ],
)
def test_an_ending_that_concludes_is_not_counted(text):
    assert reply_hits(text, where="resolution") == []


def test_waiting_for_the_answer_defers_an_ending_not_a_reply():
    text = "Romy plie la note : elle attend ta réponse écrite avant d'agir."
    assert [hit.kind for hit in reply_hits(text, where="resolution")] == ["deferred_ending"]
    assert reply_hits(text, where="reply") == []


# ---------------------------------------------------------------------------
# A SceneDraft, its places, and the rewrite instructions
# ---------------------------------------------------------------------------


def _scene_draft():
    from app.services.living_story import SceneDraft

    return SceneDraft.model_validate(
        {
            "title_fr": "La décision",
            "premise_fr": "Chez Marin et Lila, on range des toiles.",
            "setup_native": "At Marin and Lila's.",
            "objective_native": "Dis si tu acceptes que Lila parte avant le 15, donne une condition précise et explique pourquoi.",
            "objective_semantics": "The learner says yes or no.",
            "character_id": "lila_bonnet",
            "location_id": "appart_marin_lila",
            "causal_reason": "Lila must answer Berlin.",
            "novelty_key": "lila_depart",
            "chapter": {
                "title_fr": "Le départ",
                "dramatic_question": "Will Lila go?",
                "possible_developments": ["She goes.", "She stays."],
            },
            "panels": [
                {
                    "narration_fr": "Le matin après la dispute.",
                    "visual_direction": "Wide: the kitchen.",
                    "dialogue": [
                        {
                            "character_id": "marin_leveque",
                            "text_fr": "Cette soupe refroidit, hein ?",
                        },
                        {
                            "character_id": "augustin_de_roncourt",
                            "text_fr": "Toutefois, il faut un plan.",
                        },
                    ],
                },
                {
                    "narration_fr": "Le silence: la décision repose maintenant sur toi.",
                    "visual_direction": "Close: the phone face down.",
                    "dialogue": [{"character_id": "lila_bonnet", "text_fr": "Tu peux m'aider ?"}],
                },
            ],
            "opening_line_fr": "Tu peux m'aider ?",
            "suggested_response_fr": "Oui. Néanmoins, je reste.",
            "hint_native": "Say yes or no.",
            "translation_native": "Can you help me?",
        }
    )


def test_a_scene_draft_and_its_dict_give_the_same_hits_with_their_places():
    draft = _scene_draft()
    hits = page_hits(draft, level="B1.1")
    assert hits == page_hits(draft.model_dump(mode="json"), level="B1")
    assert {(hit.kind, hit.where) for hit in hits} == {
        ("quiz_caption", "caption:1"),
        ("contract_words", "task"),
        ("written_connector", "line:0:1"),
        ("written_connector", "answer"),
        ("repeated_line", "opening"),
        ("long_task", "task"),
    }
    assert all(hit.blocking for hit in hits)


def test_feedback_is_one_instruction_per_kind_quoting_the_text():
    assert feedback(
        [Hit("quiz_caption", "caption:3", "Tout le monde attend ta réponse.", True)]
    ) == [
        "caption narrates the learner's turn ('Tout le monde attend ta réponse.'): captions show "
        "what happens, never the answer, a decision or anyone waiting"
    ]
    lines = feedback(page_hits(_scene_draft(), level="B1"))
    assert len(lines) == 5  # quiz, contract, connector, repeated, long task
    assert any(line.startswith("task of 17 words (") for line in lines)
    assert any("'Toutefois, il faut un plan.', 'Néanmoins, je reste.'" in line for line in lines)


# ---------------------------------------------------------------------------
# Nothing the owner wrote is a machine line
# ---------------------------------------------------------------------------

LEVELS = ("a1", "a2", "b1", "b2", "c1")
#: Wordings a character says or a caption narrates besides a line's ``say``: a solve's
#: prompt and objections, a letter in the fiction, a consequence card, the season's
#: question. Option labels and example replies are the learner's words, not the page's.
SPOKEN_WORDINGS = {
    "prompt": "line",
    "objections": "line",
    "document": "line",
    "subtitle": "caption",
    "question": "caption",
}
BIBLE_FILES = (
    "t1",
    "t2",
    "t3",
    "t4",
    "t5",
    "t6",
    "t7",
    "t8",
    "intro",
    "bridges",
    "epilogue",
    "season",
)


def _authored() -> list[tuple[str, str, str, str]]:
    """``(source, role, level, text)``: every French line and caption of season s1, each
    at every level the bible or a level file (``levels_*.json``) writes it."""

    levels = read_levels(SEASON)
    rows: list[tuple[str, str, str, str]] = []

    def wording(source: str, role: str, say: dict) -> None:
        for level in LEVELS:
            if isinstance(say.get(level), str) and say[level].strip():
                rows.append((source, role, level, say[level]))

    def walk(node, source: str) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("say"), dict):
                wording(source, "caption" if node.get("who") == "caption" else "line", node["say"])
            for key, value in node.items():
                if key in SPOKEN_WORDINGS:
                    for item in value if isinstance(value, list) else [value]:
                        if isinstance(item, dict):
                            wording(source, SPOKEN_WORDINGS[key], item)
                elif key == "diegetic":
                    rows.extend((source, "caption", "a2", str(text)) for text in value)
                elif key == "previously":
                    rows.extend(
                        (source, "caption", "a2", str(item.get("label") or "")) for item in value
                    )
                if key != "say":
                    walk(value, source)
        elif isinstance(node, list):
            for value in node:
                walk(value, source)

    for name in BIBLE_FILES:
        raw = json.loads((SEASON / f"{name}.json").read_text(encoding="utf-8"))
        walk(apply_levels(raw, levels, file_id=name), name)
    intro = json.loads((SEASON / "intro.json").read_text(encoding="utf-8"))
    rows += [("intro", "line", "a1", member["line_fr"]) for member in intro["cast"]]
    tasks = json.loads((SEASON / "tasks.json").read_text(encoding="utf-8"))
    for again in tasks["ask_again"].values():  # null: any reply is an answer, nobody asks again
        rows += [
            ("tasks", "line", "a1", again[key])
            for key in ("fr", "fr_named")
            if again and again.get(key)
        ]
    world = json.loads((SEASON / "world.json").read_text(encoding="utf-8"))
    for member in world["cast"]:
        # «A2: «Mais arrête. C'est évident.» «Toi, tu me caches quelque chose.» B1: «…»»
        for level, samples in re.findall(
            r"\b(A1|A2|B1|B2|C1):((?:(?!\b(?:A1|A2|B1|B2|C1):).)*)",
            member.get("speech_pattern") or "",
        ):
            rows += [
                ("world", "line", level.lower(), sample)
                for sample in re.findall(r"«([^«»]+)»", samples)
            ]
    rows += [("world", "line", "a1", phrase) for phrase in detector.signature_phrases(world)]
    return [row for row in rows if row[3].strip()]


AUTHORED = _authored()


def test_the_authored_corpus_is_the_whole_season():
    sources = {source for source, *_ in AUTHORED}
    assert sources == {*BIBLE_FILES, "tasks", "world"}
    levels = {level for _source, _role, level, _text in AUTHORED}
    assert levels == set(LEVELS)
    assert len(AUTHORED) > 3000
    # The level files' variants are in: T5's Gus at A1 and C1 (the plan's level cards).
    texts = {text for *_rest, text in AUTHORED}
    assert "La boulangère donne la monnaie… sans un mot, Marin !" in texts
    assert "Ça, mon vieux, c'est peut-être un signe." in texts


def test_no_authored_line_or_caption_is_a_machine_line():
    """At its own level, in its own place: a caption is read as narration, a line as
    speech. A rule that trips here is narrowed, never this test."""

    tripped = []
    for source, role, level, text in AUTHORED:
        page = _page(caption=text) if role == "caption" else _page(line=text)
        hits = [hit for hit in page_hits(page, level=level) if hit.kind in LINE_KINDS]
        tripped += [f"{source} {level} {role}: {hit.kind} «{hit.text}»" for hit in hits]
    assert tripped == []


def test_no_authored_line_trips_the_narration_rules_either():
    """Stricter than the page: a line read as if it were a caption («C'est à toi.» is
    Lila's line, not narration, so it is allowed to hand over the turn)."""

    handing_over = re.compile(
        r"c'est à toi|à toi de|la décision t'appartient|c'est toi qui décides", re.IGNORECASE
    )
    tripped = [
        f"{source} {level}: «{text}»"
        for source, role, level, text in AUTHORED
        if role == "line"
        and not handing_over.search(text)
        and page_hits(_page(caption=text), level=level)
    ]
    assert tripped == []


# ---------------------------------------------------------------------------
# The baseline: the paid live reads of 7 and 8 October (30 generated days)
# ---------------------------------------------------------------------------

LIVE_READS = {
    "A1": [
        "loss-rate-2026-10-07/run3-a1/A1.1.md",
        "loss-rate-2026-10-07/topup/live-a1/A1.1.md",
        "wp149-confirmation/a1/A1.1.md",
    ],
    "B1": [
        "loss-rate-2026-10-07/run2-b1/B1.1.md",
        "loss-rate-2026-10-07/topup/live-b1/B1.1.md",
        "wp149-confirmation/b1/B1.1.md",
    ],
    "B2": ["loss-rate-2026-10-07/topup/live-b2/B2.1.md"],
    "C1": ["loss-rate-2026-10-07/run1-c1/C1.1.md"],
}

#: Per band: days, hits per kind, tasks over 12 words. The plan's first count
#: (scratch baseline) differs where the detector reads better: quiz 24 → 31, teacher
#: 9 → 13, contract 34 → 38, repeated 20 → 21, deferred 11 → 21 (every added hit is a
#: machine line the first count's patterns missed; nothing it counted is lost).
BASELINE = {
    "A1": {
        "days": 12,
        "quiz_caption": 13,
        "teacher_talk": 13,
        "contract_words": 0,
        "written_connector": 0,
        "repeated_line": 10,
        "deferred_ending": 8,
        "leaves_without_answer": 2,
        "glued_self_repair": 1,
        "over": 2,
    },
    "B1": {
        "days": 11,
        "quiz_caption": 13,
        "teacher_talk": 0,
        "contract_words": 24,
        "written_connector": 11,
        "repeated_line": 7,
        "deferred_ending": 9,
        "leaves_without_answer": 2,
        "glued_self_repair": 4,
        "over": 11,
    },
    "B2": {
        "days": 1,
        "quiz_caption": 0,
        "teacher_talk": 0,
        "contract_words": 0,
        "written_connector": 0,
        "repeated_line": 0,
        "deferred_ending": 1,
        "leaves_without_answer": 0,
        "glued_self_repair": 0,
        "over": 1,
    },
    "C1": {
        "days": 6,
        "quiz_caption": 5,
        "teacher_talk": 0,
        "contract_words": 14,
        "written_connector": 0,
        "repeated_line": 4,
        "deferred_ending": 3,
        "leaves_without_answer": 1,
        "glued_self_repair": 6,
        "over": 6,
    },
}


def _band_counts(paths: list[str]) -> dict[str, int]:
    phrases = detector.signature_phrases(
        json.loads((SEASON / "world.json").read_text(encoding="utf-8"))
    )
    out = {"days": 0, "over": 0}
    for path in paths:
        result = detector.transcript_counts(
            (EVIDENCE / path).read_text(encoding="utf-8"), signature_phrases=phrases
        )
        out["days"] += result["days"]
        out["over"] += sum(1 for words in result["tasks"] if words > TASK_MAX_WORDS)
        for kind in (*detector.PAGE_KINDS, *detector.REPLY_KINDS):
            out[kind] = out.get(kind, 0) + result["counts"].get(kind, 0)
    return out


@pytest.mark.parametrize("band", sorted(LIVE_READS))
def test_the_live_reads_give_the_baseline(band):
    counts = _band_counts(LIVE_READS[band])
    assert {key: counts[key] for key in BASELINE[band]} == BASELINE[band]
    assert counts["long_task"] == counts["over"]


def test_the_cli_prints_one_row_per_transcript_and_the_total(capsys):
    paths = [str(EVIDENCE / path) for band in ("A1", "B1", "B2", "C1") for path in LIVE_READS[band]]
    assert detector.main(paths) == 0
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("| ")]
    assert len(rows) == 1 + len(paths) + 1  # header, files, total
    total = [cell.strip() for cell in rows[-1].strip("|").split("|")]
    # file, level, days, quiz, teacher, contract, connector, repeated, deferred, leaves,
    # glued, task median / longest, tasks over 12 words
    assert total == [
        "total",
        "",
        "30",
        "31",
        "13",
        "38",
        "11",
        "21",
        "21",
        "5",
        "11",
        "19.5 / 37",
        "20 of 30",
    ]


def test_the_cli_reads_only_the_generated_days():
    """Tentpole days are the bible's and a lost day is the fallback's: not counted."""

    level, days = detector.read_transcript(
        (EVIDENCE / LIVE_READS["B1"][0]).read_text(encoding="utf-8")
    )
    assert level == "B1.1"
    assert [day.heading.split(" (")[0] for day in days] == [
        "Jour 27 — g4.1",
        "Jour 28 — g4.2",
        "Jour 29 — g4.3",
        "Jour 30 — g4.4",
        "Jour 31 — g4.5",
    ]
    first = days[0]
    assert first.page["premise_fr"].startswith("Le lendemain de la dispute.")
    assert (
        first.page["panels"][3]["narration_fr"]
        == "Le silence crée un pont. Tout le monde attend ta réponse."
    )
    assert first.page["opening_line_fr"].startswith("Tu as vu ce que le quartier a dit hier.")
    assert first.replies == ["Ah, bon. Ça me rassure d'entendre que tu restes — un peu. Merci."]
    assert first.resolution.startswith("Lila sourit et se détend un peu")
