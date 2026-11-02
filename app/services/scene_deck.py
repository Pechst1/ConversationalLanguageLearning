"""Today's scene words in the day deck, each quoting its scene line.

Owner request, 1 November (scene words in the day deck, quoting their lines),
reworked 2 November: the deck asks *primarily* what the SRS scheduler proposes
next, with today's scene words mixed into the new-word slots
(:mod:`app.services.deck_order`, the one place the deck's mix and order are
decided).

* A **scene word** is a word the deck holds *because of* today's scene: one the
  day's plan dealt as the scene's (``scene`` on the batch item) or one today's
  journey reserved, and not one of the reviews the scheduler had due (a due
  review stays a review, wherever it was printed). It carries ``scene_word``.
* **Any** deck card whose word the scene taught (lexicon), the learner kept from
  today's scene, or a scene word found in the scene's text quotes the scene line
  it appeared in, with the line's translation when the scene carried one
  (``text_native``, A1/A2 learners).
* #472: the line is a line of the scene, never its title. An authored page with
  no caption (every day B) is published with its French title in
  ``premise_fr`` / ``opening_line_fr``, so «la lettre» quoted the episode title
  «La lettre». :func:`quotable_texts` is the scene's text a card may quote:
  :func:`app.services.scene_items.scene_texts` less any text that is the
  draft's (or its chapter's) title.

Where the lines are known: the day's scene draft
(``private_task["scenario_brief"]["story_context"]["draft"]`` on the journey's
steps) holds the lines, their translations and the lexicon (each entry's
``line_ref``); a word kept from today's scene carries its own tapped line in
``progress.context`` (WP-115a). Pure reads, no model call, no write.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

#: The flag a scene word's card carries in the due-context payload.
SCENE_WORD_KEY = "scene_word"


def journey_draft(journey: Any) -> dict[str, Any]:
    """Today's scene draft (panels, lines, lexicon), or ``{}``."""

    if journey is None:
        return {}
    for step in getattr(journey, "steps", None) or []:
        brief = (getattr(step, "private_task", None) or {}).get("scenario_brief")
        context = brief.get("story_context") if isinstance(brief, dict) else None
        draft = context.get("draft") if isinstance(context, dict) else None
        if isinstance(draft, dict):
            return draft
    return {}


def _line_with_meaning(sentence: str, draft: dict[str, Any]) -> tuple[str, str | None]:
    """The line to quote and its translation.

    The scene translates whole lines; a lexicon sentence cut from a longer line
    has no translation of its own, so the whole line is quoted with its
    translation rather than the sentence without one.
    """

    from app.services.scene_items import fold, line_meanings, meaning_of

    meanings = line_meanings(SimpleNamespace(story_context={"draft": draft}))
    own = meaning_of(meanings, sentence)
    if own:
        return sentence, own
    wanted = fold(sentence)
    for line, native in meanings.items():
        if wanted and wanted in fold(line):
            return line.strip(), native
    return sentence, None


def _bare(text: Any) -> str:
    from app.services.scene_items import fold

    return fold(text).strip(" .!?…«»\"'")


def _titles(draft: dict[str, Any]) -> set[str]:
    chapter = draft.get("chapter") if isinstance(draft.get("chapter"), dict) else {}
    return {key for key in (_bare(draft.get("title_fr")), _bare(chapter.get("title_fr"))) if key}


def quotable_texts(draft: dict[str, Any]) -> dict[str, str]:
    """The scene's texts a card may quote: every learner-facing line, never a title (#472)."""

    from app.services.scene_items import scene_texts

    titles = _titles(draft)
    return {ref: text for ref, text in scene_texts(draft).items() if _bare(text) not in titles}


def line_holding(draft: dict[str, Any], surface: str, *, line_ref: str = "") -> str:
    """The sentence of the scene that holds ``surface`` (``line_ref``'s first), or ''.

    The sentence, not the whole text, so a narration of three sentences quotes
    the one with the word; a title's full stop («M. Marchand») ends none (#398).
    """

    from app.services.scene_items import contains_surface
    from app.services.sentence_line import cut_sentences

    if not surface:
        return ""
    texts = quotable_texts(draft)
    titles = _titles(draft)
    ordered = ([texts[line_ref]] if line_ref in texts else []) + list(texts.values())
    for text in ordered:
        if not contains_surface(text, surface):
            continue
        for sentence in cut_sentences(text):
            if contains_surface(sentence, surface) and _bare(sentence) not in titles:
                return sentence.strip()
        return text.strip()
    return ""


def scene_lines(
    *,
    draft: dict[str, Any],
    journey_id: Any,
    words: dict[int, Any],
    progress: dict[int, Any],
    candidates: set[int],
) -> dict[int, dict[str, str | None]]:
    """``{word_id: {sentence_fr, translation}}`` for the deck's words seen in today's scene.

    ``words`` / ``progress`` are the deck's catalogue rows and the learner's rows;
    ``candidates`` the words the day already knows are the scene's (dealt as the
    scene's, reserved by today's journey). A candidate's line is looked for in
    the scene's text; any other word quotes the scene only through the lexicon
    or the learner's own keep, never because a common word happens to be printed.
    A line is always one of :func:`quotable_texts` (never the episode's title):
    an entry whose ``line_ref`` names the title is looked up in the lines.
    """

    from app.services.lexicon_grammar import lemma_key
    from app.services.scene_items import fold, lexicon_of

    lexicon: dict[str, dict[str, Any]] = {}
    if draft:
        for entry in lexicon_of(SimpleNamespace(story_context={"draft": draft})):
            key = fold(lemma_key(entry.get("lemma") or entry.get("surface_fr") or ""))
            if key:
                lexicon.setdefault(key, entry)
    journey_key = str(journey_id) if journey_id else ""
    lines: dict[int, dict[str, str | None]] = {}
    for word_id, word in words.items():
        row = progress.get(word_id)
        context = row.context if row is not None and isinstance(getattr(row, "context", None), dict) else {}
        kept = str(context.get("sentence_fr") or "").strip() if journey_key and str(context.get("journey_id") or "") == journey_key else ""
        head = lemma_key(getattr(word, "word", "") or "")
        entry = lexicon.get(fold(head))
        sentence = kept if kept and _bare(kept) not in _titles(draft) else ""
        if not sentence and entry is not None and draft:
            surface = str(entry.get("surface_fr") or entry.get("lemma") or head)
            sentence = line_holding(draft, surface, line_ref=str(entry.get("line_ref") or "")) or line_holding(
                draft, head
            )
        if not sentence and word_id in candidates and draft:
            sentence = line_holding(draft, head)
        if not sentence:
            continue
        line, translation = _line_with_meaning(sentence, draft) if draft else (sentence, None)
        lines[word_id] = {"sentence_fr": line, "translation": translation}
    return lines


def mark_scene_words(
    payload: dict[str, Any],
    *,
    scene_ids: set[int],
    lines: dict[int, dict[str, str | None]],
) -> dict[str, Any]:
    """Flag the payload's scene words; give every card with a scene line that line as example.

    ``scene_ids`` are the deck's scene words (the mix's scene share,
    :mod:`app.services.deck_order`); ``lines`` may hold other cards too (a review
    the scene featured): those quote the scene but stay what they are. A scene
    word without a line (a reserved word the scene's text no longer prints) keeps
    the catalogue's example.
    """

    from app.services.drill_batch import PAYLOAD_LISTS

    for name in PAYLOAD_LISTS:
        cards = []
        for card in payload.get(name) or []:
            word_id = int(card.get("word_id") or 0)
            if word_id in scene_ids:
                card = {**card, SCENE_WORD_KEY: True}
            line = lines.get(word_id)
            if line and line.get("sentence_fr"):
                card = {
                    **card,
                    "example_sentence": line["sentence_fr"],
                    "example_translation": line.get("translation") or None,
                }
            cards.append(card)
        payload[name] = cards
    return payload


def apply_to_day_deck(db: Any, user: Any, batch: Any, payload: dict[str, Any], *, now: Any) -> dict[str, Any]:
    """The day deck's payload with today's scene words flagged and quoting their lines."""

    from sqlalchemy import select

    from app.db.models.progress import UserVocabularyProgress
    from app.db.models.vocabulary import VocabularyWord
    from app.services.drill_batch import PAYLOAD_LISTS
    from app.services.vocabulary_pace import journey_reservation, todays_journey

    ids = {int(card.get("word_id") or 0) for name in PAYLOAD_LISTS for card in payload.get(name) or []}
    ids.discard(0)
    if not ids:
        return payload
    journey = todays_journey(db, user, now=now)
    if journey is None:
        return payload
    from app.services.day_words import read_plan

    _planned, reserved = journey_reservation(db, user, now=now)
    flagged = {int(item["word_id"]) for item in getattr(batch, "items", None) or [] if item.get("scene")}
    candidates = (set(reserved) | flagged) & ids
    # A word the scheduler had due when the day was planned is a review, scene or not.
    due_reviews = {int(value) for value in (read_plan(batch) or {}).get("reviews") or []}
    words = {int(word.id): word for word in db.scalars(select(VocabularyWord).where(VocabularyWord.id.in_(ids)))}
    progress = {
        int(row.word_id): row
        for row in db.scalars(
            select(UserVocabularyProgress).where(
                UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id.in_(ids)
            )
        )
    }
    lines = scene_lines(
        draft=journey_draft(journey), journey_id=journey.id, words=words, progress=progress, candidates=candidates
    )
    return mark_scene_words(payload, scene_ids=candidates - due_reviews, lines=lines)


__all__ = [
    "SCENE_WORD_KEY",
    "apply_to_day_deck",
    "journey_draft",
    "line_holding",
    "mark_scene_words",
    "quotable_texts",
    "scene_lines",
]
