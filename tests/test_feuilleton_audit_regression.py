"""Regression coverage for the 23 July 2026 Feuilleton audit.

These tests pin the P0 contract changes so the reported failures cannot silently
regress: no live news in standalone/serial editions, no learner-facing source card,
no inherited grammar concept, narrative choices graded as valid branches, image
prompts free of bubble/overlay wording, whitespace dialogue dropped, and pre-redesign
scenes refused as the current edition.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.graphic_novel import (
    GRAPHIC_NOVEL_PROMPT_VERSION,
    GraphicNovelCorrectionService,
    GraphicNovelStoryGenerator,
    learner_facing_source,
    scene_matches_current_contract,
)

# --- P0.3 learner-facing source sanitisation (checklist #1, #3) -----------------


def test_curated_and_offstage_provenance_never_becomes_a_source_card():
    # Curated stub, personal input, and serial recovery seeds are internal provenance.
    for snapshot in (
        {"mode": "atelier_curated", "title": "A small Paris errand", "source": "Atelier"},
        {"mode": "personal_input", "title": "My note", "source": "Personal"},
        {"mode": "serial_news_seed", "title": "Paris repair hotline", "source": "QA"},
        {},
        None,
    ):
        assert learner_facing_source(snapshot) == {}


def test_optin_news_edition_exposes_trimmed_source_card():
    snapshot = {
        "learner_visible": True,
        "title": "Council debates a new market rule",
        "summary": "The council spent the afternoon " + "arguing about stalls " * 40,
        "source": "Le Quotidien",
        "url": "https://example.com/a",
    }
    card = learner_facing_source(snapshot)
    assert card["title"] == "Council debates a new market rule"
    assert card["source"] == "Le Quotidien"
    # Summary is trimmed to a boundary and never ends mid-word.
    assert len(card["summary"]) <= 221
    assert not card["summary"].endswith("arg")


# --- P0.9 stale-scene gating (checklist #18) ------------------------------------


def test_scene_contract_gate_rejects_pre_redesign_versions():
    assert scene_matches_current_contract(SimpleNamespace(prompt_version=GRAPHIC_NOVEL_PROMPT_VERSION))
    assert not scene_matches_current_contract(SimpleNamespace(prompt_version="feuilleton-visual-gag-v3"))
    assert not scene_matches_current_contract(SimpleNamespace(prompt_version=None))
    assert not scene_matches_current_contract(None)


# --- P0.4 no inherited concept (checklist #4) -----------------------------------


def test_task_without_explicit_concept_does_not_inherit_target_concept(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    overlay = {
        "tasks": [
            {
                "id": "t1",
                "task_type": "cloze",
                "instruction": "Complete the line.",
                "prompt": "Si elle appelle, je ____ tout de suite.",
                "prompt_translation": "If she calls, I ____ right away.",
                "expected_answer": "répondrai",
                "accepted_answers": ["répondrai"],
            }
        ]
    }
    normalized = generator._normalize_overlay(
        overlay,
        panel_index=1,
        targets=[{"concept_id": 4242}],  # an unrelated selected target
    )
    assert normalized["tasks"][0]["concept_id"] is None


def test_authored_concept_outside_targets_is_dropped(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    overlay = {
        "tasks": [
            {
                "id": "t1",
                "task_type": "cloze",
                "concept_id": 999,  # authored but not among the selected targets
                "instruction": "Complete the line.",
                "prompt": "Si elle appelle, je ____.",
                "prompt_translation": "If she calls, I ____.",
                "expected_answer": "répondrai",
                "accepted_answers": ["répondrai"],
            }
        ]
    }
    normalized = generator._normalize_overlay(
        overlay, panel_index=1, targets=[{"concept_id": 4242}]
    )
    assert normalized["tasks"][0]["concept_id"] is None


# --- P0.5 narrative branch grading (checklist #6) -------------------------------


def test_branch_choice_is_accepted_with_no_erratum(db_session):
    service = GraphicNovelCorrectionService(db_session)
    task = {
        "id": "decision",
        "task_type": "choice",
        "grading_mode": "branch",
        "options": [
            {"value": "A", "fr": "On avance sans le tampon."},
            {"value": "B", "fr": "On attend encore un peu."},
        ],
        "branch_target": {
            "A": {"next_panel_beat": "La file approuve."},
            "B": {"next_panel_beat": "Le tampon savoure son pouvoir."},
        },
    }
    for selected in ("A", "B"):
        correction = service._correct(task=task, panel=None, answer_payload={"answer": selected})
        assert correction["verdict"] == "branch"
        assert correction["errata"] == []
        assert correction["score_0_4"] == 4
        assert correction["corrected_answer"] == ""
        # Feedback is a short French story consequence, not a grammar correction.
        assert correction["why"]


# --- P0.5 branch normalisation keeps no expected answer -------------------------


def test_branch_choice_normalises_without_expected_answer(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    overlay = {
        "tasks": [
            {
                "id": "decision",
                "task_type": "choice",
                "grading_mode": "branch",
                "instruction": "Choisissez la suite.",
                "prompt": "Le tampon hésite.",
                "prompt_translation": "The stamp hesitates.",
                "expected_answer": "",
                "options": ["On avance.", "On attend."],
                "branch_target": {"A": {"next_panel_beat": "x"}, "B": {"next_panel_beat": "y"}},
            }
        ]
    }
    normalized = generator._normalize_overlay(overlay, panel_index=2, targets=[])
    assert len(normalized["tasks"]) == 1
    task = normalized["tasks"][0]
    assert task["grading_mode"] == "branch"
    assert task["expected_answer"] == ""
    assert task["concept_id"] is None


# --- P0.5/P0.8 whitespace dialogue never survives (checklist #15) ----------------


def test_whitespace_only_dialogue_is_dropped(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    overlay = {
        "bubbles": [
            {"speaker": "Camille", "fr": "   ", "en": "  "},
            {"speaker": "Marc", "fr": "Bonsoir.", "en": "Good evening."},
        ],
        "tasks": [],
    }
    normalized = generator._normalize_overlay(overlay, panel_index=1, targets=[])
    frs = [bubble["fr"] for bubble in normalized["bubbles"]]
    assert "Bonsoir." in frs
    assert all(fr.strip() for fr in frs)


# --- P0.8 image prompt carries no bubble/overlay wording (checklist #14) ---------


def test_composed_image_prompt_has_no_bubble_or_overlay_wording(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    prompt = generator._compose_image_prompt(
        headline_mechanic="an official stamp takes over an office",
        selected_visual_premise={"anchor_object": "a red stamp", "domain": "a small city office"},
        characters=[{"name": "Elise", "visual_description": "beige coat"}],
        prop_bible=[{"name": "stamp", "visual_description": "oversized red stamp"}],
        panel={"panel_action": "The stamp presides over an empty counter.", "image_prompt_note": "prop gains power"},
        humor_style="dry",
        render_mode="panels",
        public_figure_mode="named_context",
    ).lower()
    assert "no readable text" in prompt
    for forbidden in ("speech bubble", "balloon", "overlay area", "reserve a", "blank shape", "html speech"):
        assert forbidden not in prompt


# --- P1 reader rebuild (checklist #10–#17) --------------------------------------
#
# Static pins on the rebuilt reader. The live read of a generated episode showed
# the presentation, not the story, was the failure: five stacked kickers, six
# repeated press notices, the panel number twice, the reply prompt three times
# (once shouted in uppercase), deck names and an English "YOUR QUEUE" dump.

import re  # noqa: E402
from pathlib import Path  # noqa: E402

WEB = Path(__file__).resolve().parents[1] / "web-frontend"
READER = WEB / "pages" / "graphic-novel.tsx"
SUPPLEMENT = WEB / "components" / "feuilleton" / "Feuilleton.tsx"


def _reader() -> str:
    return READER.read_text(encoding="utf-8")


def _supplement() -> str:
    return SUPPLEMENT.read_text(encoding="utf-8")


def test_reader_header_names_the_season_once_and_never_a_news_kicker_without_news():
    reader = _reader()
    supplement = _supplement()

    # The folio is the only place a season is named; the dateline carries the
    # place and the date, never a second "Saison 1".
    assert 'dateline={[loc, dateLabel].filter(Boolean) as string[]}' in reader
    folio = supplement[supplement.index("export function FeMasthead(") : supplement.index("export function FePreviously(")]
    assert "`Saison ${season}`" in folio
    assert folio.count("Saison") == 1
    # The news kicker (and the helper that fed it) is gone: news is opt-in per
    # authored episode brief, so its label must never render without a panel.
    body = reader[reader.index("export default function GraphicNovelPage()"):]
    for dead in ('<span className="lbl">Cette semaine</span>', "serialNewsLine", 's-news"'):
        assert dead not in body


def test_reader_previously_is_one_quiet_line():
    supplement = _supplement()

    assert 'export function FePreviously({ children }' in supplement
    assert '<p className="fe-previously">' in supplement
    # No boxed strip with its own kicker row and episode chip.
    assert 'className="ph"' not in supplement
    assert "epRef" not in supplement


def test_panel_prints_one_numeral_no_kicker_and_one_press_mark():
    reader = _reader()
    supplement = _supplement()

    # FePanel no longer takes a slug, a direction label or a credit line — the
    # three things that printed "LE FEUILLETON" and the panel title on every
    # plate alongside the numeral.
    fe_panel = supplement[supplement.index("export function FePanel(") : supplement.index("export function FeDialogue(")]
    for dead in ("credit?:", "direction?:", "slug?:", "bubbles", "narration"):
        assert dead not in fe_panel
    for dead in ("FeBubble", "fe-credit", ".fe-narr"):
        assert dead not in supplement
    # One numeral, from one place.
    assert reader.count("capNum={String(panel.panel_index || 1).padStart(2, '0')}") == 1
    # The printing state is one quiet mark, not a sentence repeated per panel.
    assert "'Sous presse'" in supplement
    assert "La planche arrive" not in reader
    # One consistent ratio and focal treatment for every plate.
    assert "ratio = 'square'" in supplement
    assert "aspect-ratio: 1 / 1;" in supplement
    assert "object-fit: cover; object-position: center;" in supplement


def test_dialogue_is_printed_once_with_canonical_short_names():
    reader = _reader()
    supplement = _supplement()

    # One dialogue system: lines under the art. No on-art bubble layer plus a
    # transcript repeating the same lines (audit §9).
    assert "function panelDialogueLines" in reader
    assert reader.count("<FeDialogue") == 2  # the scrolling reader and the page annotation
    assert "fe-bubble" not in supplement
    assert "FeTranscript" not in supplement and "FeTranscript" not in reader
    # Canonical short display names (checklist #13).
    assert "function shortSpeakerName" in reader
    assert "who: shortSpeakerName(bubble.speaker) || undefined" in reader
    # Whitespace-only dialogue cannot render (checklist #15).
    assert ".filter((bubble) => String(bubble?.fr || '').trim())" in reader


def test_caption_renders_only_when_it_adds_something():
    reader = _reader()

    assert "function additivePanelCaption" in reader
    assert "return spoken.includes(normalizeReaderText(caption)) ? '' : caption;" in reader


def test_only_the_next_learning_action_is_live():
    """Checklist #11 — and #10: a panel whose action is not yet due renders none."""
    reader = _reader()

    assert "const activeTaskId = nextPendingTask?.id ? String(nextPendingTask.id) : null;" in reader
    assert ".filter((task) => attemptsByTask[task.id] || String(task.id) === activeTaskId);" in reader


def test_the_reply_prompt_is_said_once_in_sentence_case():
    reader = _reader()

    assert "function taskPromptLine" in reader
    assert reader.count('<p className="task-prompt">{prompt}</p>') == 1
    # The launcher, the shouted intro and the kind/instruction header are gone.
    for dead in (
        "À vous d’écrire la prochaine réplique.",
        "mobile-story-task-launcher",
        "function mobileTaskLauncherCopy",
        "relues",
        "Ouvrir la feuille de tâches",
        "className=\"task-title\"",
        "function taskKindLabel",
    ):
        assert dead not in reader
    # One Envoyer, and the "because" line survives as one small graphite note.
    assert reader.count("{attempt ? submittedLabel : submitting ? 'Relecture…' : 'Envoyer'}") == 1
    assert 'className="task-reason"' in reader
    assert "recommendation_reason" in reader


def test_feedback_is_one_short_french_line_with_no_taxonomy_leak():
    """Checklist #12 and #16 — one response, rendered once."""
    reader = _reader()

    assert "function correctionLine" in reader
    assert reader.count('className={`inline-feedback ') == 1
    # No raw verdict enum, no errata counter, no duplicate sheet correction.
    for dead in (
        "String(correction.verdict || 'submitted').replace(/_/g, ' ')",
        "function MobileCorrectionNote",
        "function MobileTaskFlyIn",
        "+{errataCount} erratum",
        "erratum</em>",
        "VocabularyCreditBadge",
    ):
        assert dead not in reader


def test_reader_shows_no_deck_names_or_english_vocabulary_dump():
    """Checklist #17 and the audit's P1 §4: the words stay linked to the deck."""
    reader = _reader()

    for dead in (
        "French 5000",
        "your queue",
        "YOUR QUEUE",
        "function vocabularySourceLabel",
        "function PostSceneVocabularySummary",
        "Bilan lexical",
        "Revoir les mots attendus",
        "context-vocabulary-marker",
        "task-vocabulary-marker",
    ):
        assert dead not in reader
    # If a credit is needed after the last panel it is exactly one sentence.
    assert "function feuilletonCreditLine" in reader
    assert "mots de cette édition rejoignent votre révision." in reader


def test_option_translations_stay_hidden_until_requested():
    reader = _reader()

    # The option button prints the French line only; the English gloss that used
    # to render unconditionally beside it is gone.
    assert "<button\n              key={option.value}" in reader
    assert "{option.en && <small>{option.en}</small>}" not in reader
    # Translation is one explicit affordance.
    assert "function TaskTranslate" in reader
    assert "{open ? 'Masquer la traduction' : 'Traduire'}" in reader


def test_a_suivre_teaser_is_not_shouted():
    supplement = _supplement()

    demain = supplement[supplement.index(".fe-cliff .demain {"):]
    demain = demain[: demain.index("}")]
    assert "text-transform: uppercase" not in demain
    assert "font-style: italic" in demain


def test_sticky_bar_carries_one_action_and_no_counters():
    reader = _reader()

    bar = reader[reader.index("function MobileReadingBar") : reader.index("function SerialSceneReader")]
    assert "Quitter" in bar
    assert "Votre réplique" in bar
    for dead in ("planches", "tâches", "submittedCount", "taskCount"):
        assert dead not in bar


def test_reader_uses_tokens_only_and_resolves_media_urls():
    reader = _reader()
    supplement = _supplement()

    css = reader[reader.index("function FeuilletonStyles()") :]
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", css) is None
    # The supplement's only literals are the documented --char-* spot inks from
    # the serial world bible (lifted a step in dark); everything else is a token.
    supplement_css = re.sub(r"\s+--char-[a-z]+: #[0-9a-fA-F]{3,8};", "", _supplement_css(supplement))
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", supplement_css) is None
    # Panel art is served from the API origin, not the app bundle.
    assert "resolveMediaUrl(panelImageUrl(panel))" in reader
    assert "resolveMediaUrl(scene.script_payload?.page_image?.url)" in reader


def _supplement_css(supplement: str) -> str:
    return supplement[supplement.index("export function FeuilletonStyles()") :]
