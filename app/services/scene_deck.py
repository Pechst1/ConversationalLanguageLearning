"""Owner request, 1 November — the day deck opens on today's scene words.

The day's word deck (``review.tsx?day=1``, dealt by :mod:`app.services.day_words`)
had the scene's words somewhere in it: a scene word the learner had already met
in the Lexique's eight kept that place, one the scene met after the deck was
dealt joined at the end, and the drill re-sorted the cards on the device by its
own tiers. Each card quoted the catalogue's example, not the line the learner had
just read.

Now a word that appeared in today's scene is a *scene word* of the deck:

* one the day's plan dealt as the scene's (``scene`` on the batch item), one
  today's journey reserved, one the learner kept from today's scene, or one the
  scene's lexicon taught;
* its card quotes the scene line it appeared in, with the line's translation
  when the scene carried one (``text_native``, A1/A2 learners);
* it comes first in the deck (:mod:`app.services.deck_order`, the one place the
  deck's order is decided, for every client).

Where the lines are known: the day's scene draft
(``private_task["scenario_brief"]["story_context"]["draft"]`` on the journey's
steps) holds the lines, their translations and the lexicon (each entry's line,
:func:`app.services.scene_items.sentence_of`); a word kept from today's scene
carries its own tapped line in ``progress.context`` (WP-115a). Pure reads, no
model call, no write.
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


def _found_in_texts(draft: dict[str, Any], head: str) -> str:
    """The first sentence of the scene that holds ``head``, or ''."""

    from app.services.scene_items import contains_surface, scene_texts
    from app.services.sentence_line import cut_sentences

    if not head:
        return ""
    for text in scene_texts(draft).values():
        if not contains_surface(text, head):
            continue
        for sentence in cut_sentences(text):
            if contains_surface(sentence, head):
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
    the scene's text; any other word is a scene word only through the lexicon
    or the learner's own keep, never because a common word happens to be printed.
    """

    from app.services.lexicon_grammar import lemma_key
    from app.services.scene_items import fold, lexicon_of, sentence_of

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
        if kept:
            sentence = kept
        elif entry is not None:
            sentence = sentence_of(draft, entry)
        elif word_id in candidates and draft:
            sentence = _found_in_texts(draft, head)
        else:
            continue
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
    """Flag the payload's scene words and give each its scene line as the example.

    A scene word without a line (a reserved word the scene's text no longer
    prints) is still first in the deck; its card keeps the catalogue's example.
    """

    from app.services.drill_batch import PAYLOAD_LISTS

    for name in PAYLOAD_LISTS:
        cards = []
        for card in payload.get(name) or []:
            word_id = int(card.get("word_id") or 0)
            if word_id in scene_ids or word_id in lines:
                card = {**card, SCENE_WORD_KEY: True}
                line = lines.get(word_id)
                if line and line.get("sentence_fr"):
                    card["example_sentence"] = line["sentence_fr"]
                    card["example_translation"] = line.get("translation") or None
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
    _planned, reserved = journey_reservation(db, user, now=now)
    flagged = {int(item["word_id"]) for item in getattr(batch, "items", None) or [] if item.get("scene")}
    candidates = (set(reserved) | flagged) & ids
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
    return mark_scene_words(payload, scene_ids=candidates, lines=lines)


__all__ = ["SCENE_WORD_KEY", "apply_to_day_deck", "journey_draft", "mark_scene_words", "scene_lines"]
