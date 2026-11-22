"""«Trois mots» (owner 2026-11-21, ``REVUE_TROIS_MOTS_ENABLED``): the closing round of a Papier.

A thirty-second round on three words of the story the learner met, played as the first block of
«La page» once the session is closed. Deterministic, no model call:

1. **Match.** Each word to its cue: a picture of the story when one of its pictures names the
   word (the painted picture shows the words of its brief, ``dossier.visual.words``; a photo's
   caption names a word), else the word's gloss in the learner's mother tongue. Two tries; a miss
   says which pairs were wrong (never which cue was right); the solution only after the second.
2. **The gap.** One sentence of the story's OWN text — the lead the learner read at their band,
   else the dossier's summary; never invented — with one of the three words taken out; pick it
   among the three. Two tries; a miss says what the picked word means; the solution after two.

**Which three.** The words the close kept (``closing.kept.words``, the ones the learner used
first), then the plan's vocabulary (the dossier's target words at their band), each once, each
with a gloss. A round whose three words never occur in the lead or summary swaps its third word
for the first candidate that does, so the gap has a sentence when one exists.

**Kept once.** The close already filed ``closing.kept.words`` in the learner's words
(``carte.keep_papier_words``). At the round's first act, only the round's words the close did
NOT keep go through the same path, so a word is never kept twice and the three open tomorrow's
deck.

The acts are ``trois_mots`` events on the closed session's log (``state.py``).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from itertools import permutations
from typing import Any

from app.schemas.revue import RvClosedWord, RvPicture
from app.schemas.revue_rendez_vous import (
    RvTmCue,
    RvTmGap,
    RvTmGapMiss,
    RvTmMatch,
    RvTmMiss,
    RvTmWord,
    RvTroisMots,
    RvTroisMotsRequest,
    RvTroisMotsResult,
)
from app.services import sentence_line

WORD_KEYS: tuple[str, str, str] = ("a", "b", "c")
CUE_KEYS: tuple[str, str, str] = ("1", "2", "3")
MAX_TRIES = 2
EVENT = "trois_mots"


@dataclass(frozen=True)
class Word:
    fr: str
    bare: str
    gloss: str
    claim_id: str | None
    kept: bool  # the close already kept it


@dataclass(frozen=True)
class Gap:
    index: int  # which of the three words
    source: str  # lead | summary
    before: str
    after: str
    sentence: str


@dataclass(frozen=True)
class Round:
    words: tuple[Word, Word, Word]
    cues: tuple[RvTmCue, RvTmCue, RvTmCue]
    #: word index → cue key
    answer: dict[int, str]
    gap: Gap | None


def _enc() -> Any:
    from app.services.revue import encounter

    return encounter


def _stem(fr: str) -> str:
    return _enc()._stem_key(fr)  # noqa: SLF001


def bare(fr: str) -> str:
    return _enc()._without_article(fr).strip()  # noqa: SLF001


def _fold(text: str) -> str:
    return _enc().fold_keep_length(text)


def find_word(text: str, word_bare: str) -> tuple[int, int] | None:
    """Where ``word_bare`` stands in ``text`` as a whole word (accent- and case-insensitive)."""

    if not word_bare:
        return None
    match = re.search(r"(?<!\w)" + re.escape(_fold(word_bare)) + r"(?!\w)", _fold(text))
    return (match.start(), match.end()) if match else None


def sentences(text: str) -> list[str]:
    return sentence_line.sentences(text)


# ---------------------------------------------------------------------------
# Choosing the three words and their cues
# ---------------------------------------------------------------------------


def candidates(plan: Any, closing: Any) -> list[Word]:
    """The kept words (used first), then the plan's vocabulary; each once, each with a gloss."""

    from app.services.revue.encounter import _gloss_language_of

    language = _gloss_language_of(plan)
    out: list[Word] = []
    seen: set[str] = set()

    def add(fr: str, gloss: str, claim_id: str | None, kept: bool) -> None:
        fr, gloss = (fr or "").strip(), (gloss or "").strip()
        key = _stem(fr)
        if not fr or not gloss or not key or key in seen or len(bare(fr)) < 2:
            return
        seen.add(key)
        out.append(Word(fr=fr, bare=bare(fr), gloss=gloss, claim_id=claim_id, kept=kept))

    kept_words = list(getattr(getattr(closing, "kept", None), "words", None) or [])
    for word in sorted(kept_words, key=lambda w: not w.used):
        add(word.fr, word.gloss, word.claim_id, True)
    for item in plan.vocabulary:
        add(item.fr, item.gloss.get(language) or next(iter(item.gloss.values()), ""), item.claim_id, False)
    return out


def _texts(dossier: Any, band: str) -> list[tuple[str, str]]:
    lead = dossier.lead_for(band).fr
    out = [("lead", s) for s in sentences(lead)]
    if dossier.summary_fr.strip() != lead.strip():
        out += [("summary", s) for s in sentences(dossier.summary_fr)]
    return out


def gap_for(words: list[Word], dossier: Any, band: str) -> Gap | None:
    """The first sentence of the lead, then the summary, that holds one of ``words`` and none of
    the others; that word taken out. ``None`` when none does."""

    for source, sentence in _texts(dossier, band):
        for index, word in enumerate(words):
            span = find_word(sentence, word.bare)
            if span is None:
                continue
            if any(find_word(sentence, other.bare) for j, other in enumerate(words) if j != index):
                continue
            start, end = span
            return Gap(index=index, source=source, before=sentence[:start], after=sentence[end:], sentence=sentence)
    return None


def _seed(session_id: str) -> int:
    return int(hashlib.sha256(f"trois-mots:{session_id}".encode()).hexdigest(), 16)


def _cue_order(session_id: str) -> tuple[int, int, int]:
    """A fixed permutation for the session, never the identity (cue 1 is not word a's)."""

    orders = [p for p in permutations(range(3)) if p != (0, 1, 2)]
    return orders[_seed(session_id) % len(orders)]  # type: ignore[return-value]


def picture_cues(words: list[Word], dossier: Any, pictures: list[RvPicture]) -> dict[int, RvPicture]:
    """A picture for a word it names: the painted picture for the words its brief shows, a photo
    whose caption names it. Each picture serves one word."""

    out: dict[int, RvPicture] = {}
    used: set[str] = set()
    shown = {_stem(w.fr) for w in (dossier.visual.words if dossier.visual is not None else [])}
    for index, word in enumerate(words):
        for picture in pictures:
            if picture.url in used:
                continue
            names = (
                _stem(word.fr) in shown if picture.kind == "illustration"
                else bool(picture.caption_fr) and find_word(picture.caption_fr or "", word.bare) is not None
            )
            if names:
                out[index] = picture
                used.add(picture.url)
                break
    return out


def build(loaded: Any, pictures: list[RvPicture] | None = None) -> Round | None:
    """The session's round, or ``None`` (not closed, or fewer than three words with a gloss)."""

    from app.services.revue.encounter import _closing_of

    closing = _closing_of(loaded.state)
    if closing is None:
        return None
    band = str(loaded.plan.learner.band)
    pool = candidates(loaded.plan, closing)
    if len(pool) < 3:
        return None
    chosen = pool[:3]
    gap = gap_for(chosen, loaded.dossier, band)
    if gap is None:  # the latest word the gap can use stands in for the least wanted of the three
        for extra in pool[3:]:
            for position in (2, 1, 0):
                trial = list(chosen)
                trial[position] = extra
                gap = gap_for(trial, loaded.dossier, band)
                if gap is not None:
                    chosen = trial
                    break
            if gap is not None:
                break
    if pictures is None:
        from sqlalchemy.orm import object_session

        from app.services.revue.photos import gallery_for

        try:
            pictures = gallery_for(object_session(loaded.row), loaded.dossier)
        except Exception:  # noqa: BLE001 - glosses stand in for pictures
            pictures = []
    by_picture = picture_cues(chosen, loaded.dossier, pictures)
    order = _cue_order(str(loaded.row.id))
    cues: list[RvTmCue] = []
    answer: dict[int, str] = {}
    for position, word_index in enumerate(order):
        key = CUE_KEYS[position]
        answer[word_index] = key
        picture = by_picture.get(word_index)
        cues.append(RvTmCue(key=key, kind="picture", picture=picture) if picture is not None
                    else RvTmCue(key=key, kind="gloss", text=chosen[word_index].gloss))
    return Round(words=(chosen[0], chosen[1], chosen[2]), cues=(cues[0], cues[1], cues[2]), answer=answer, gap=gap)


# ---------------------------------------------------------------------------
# Replay and view
# ---------------------------------------------------------------------------


class Acts:
    def __init__(self, state: Any) -> None:
        self.matches: list[dict[str, Any]] = []
        self.gaps: list[dict[str, Any]] = []
        self.kept: list[str] | None = None
        for event in state.events:
            if event.kind != EVENT:
                continue
            act = event.payload.get("act")
            if act == "match":
                self.matches.append(dict(event.payload))
            elif act == "gap":
                self.gaps.append(dict(event.payload))
            elif act == "kept" and self.kept is None:
                self.kept = [str(w) for w in event.payload.get("words") or []]

    @property
    def match_resolved(self) -> bool:
        return any(m.get("correct") for m in self.matches) or len(self.matches) >= MAX_TRIES

    @property
    def gap_resolved(self) -> bool:
        return any(g.get("correct") for g in self.gaps) or len(self.gaps) >= MAX_TRIES


def grade_match(round_: Round, pairs: dict[str, str]) -> tuple[bool, list[RvTmMiss]]:
    misses = [RvTmMiss(word_key=key, cue_key=pairs[key])  # type: ignore[arg-type]
              for index, key in enumerate(WORD_KEYS) if pairs.get(key) != round_.answer[index]]
    return not misses, misses


def view(loaded: Any, round_: Round) -> RvTroisMots:
    acts = Acts(loaded.state)
    match_done = acts.match_resolved
    last = acts.matches[-1] if acts.matches else None
    match = RvTmMatch(
        tries=len(acts.matches),
        resolved=match_done,
        correct=(bool(last.get("correct")) if match_done and last else None),
        misses=[RvTmMiss.model_validate(m) for m in (last or {}).get("misses") or []] if last and not last.get("correct") else [],
        solution={WORD_KEYS[i]: key for i, key in round_.answer.items()} if match_done else None,
    )
    gap = None
    if round_.gap is not None:
        g = round_.gap
        done = acts.gap_resolved
        last_gap = acts.gaps[-1] if acts.gaps else None
        miss = None
        if last_gap and not last_gap.get("correct"):
            picked = WORD_KEYS.index(str(last_gap.get("word")))
            miss = RvTmGapMiss(word_key=WORD_KEYS[picked], gloss=round_.words[picked].gloss)  # type: ignore[arg-type]
        gap = RvTmGap(source=g.source, before_fr=g.before, after_fr=g.after, tries=len(acts.gaps), resolved=done,  # type: ignore[arg-type]
                      correct=(bool(last_gap.get("correct")) if done and last_gap else None), miss=miss,
                      solution=WORD_KEYS[g.index] if done else None, sentence_fr=g.sentence if done else None)
    step = "match" if not match_done else ("gap" if gap is not None and not gap.resolved else "done")
    return RvTroisMots(
        session_id=str(loaded.row.id),
        step=step,  # type: ignore[arg-type]
        words=[RvTmWord(key=WORD_KEYS[i], fr=w.fr, bare_fr=w.bare, gloss=w.gloss if match_done else None)  # type: ignore[arg-type]
               for i, w in enumerate(round_.words)],
        cues=list(round_.cues),
        match=match,
        gap=gap,
        kept_now=len(acts.kept or []),
    )


# ---------------------------------------------------------------------------
# Acts
# ---------------------------------------------------------------------------


def _keep(db: Any, loaded: Any, round_: Round) -> list[str]:
    """The round's words the close did not keep, through the close's own path (once)."""

    from types import SimpleNamespace

    from app.services.revue.carte import keep_papier_words

    fresh = [w for w in round_.words if not w.kept]
    if not fresh:
        return []
    claims = loaded.dossier.claims_by_id()
    words = [RvClosedWord(fr=w.fr, gloss=w.gloss, claim_id=w.claim_id or next(iter(claims), ""), used=False)
             for w in fresh]
    keep_papier_words(db, loaded.row, dossier=loaded.dossier, plan=loaded.plan, state=loaded.state,
                      kept=SimpleNamespace(words=words))
    return [w.fr for w in fresh]


def act(encounter: Any, loaded: Any, body: RvTroisMotsRequest) -> RvTroisMotsResult:
    round_ = build(loaded)
    if round_ is None:
        return RvTroisMotsResult(round=None, error="out_of_order")
    acts = Acts(loaded.state)
    state = loaded.state
    if body.act == "match":
        if acts.match_resolved:
            return RvTroisMotsResult(round=view(loaded, round_), error="out_of_order")
        pairs = {str(k): str(v) for k, v in (body.pairs or {}).items()}
        if set(pairs) != set(WORD_KEYS) or len(set(pairs.values())) != 3:
            return RvTroisMotsResult(round=view(loaded, round_), error="pair_all")
        correct, misses = grade_match(round_, pairs)
        state.append(EVENT, act="match", pairs=pairs, correct=correct,  # type: ignore[arg-type]
                     misses=[m.model_dump() for m in misses])
        if acts.kept is None:
            state.append(EVENT, act="kept", words=_keep(encounter.db, loaded, round_))  # type: ignore[arg-type]
    else:
        if not acts.match_resolved or round_.gap is None or acts.gap_resolved:
            return RvTroisMotsResult(round=view(loaded, round_), error="out_of_order")
        if body.word not in WORD_KEYS:
            return RvTroisMotsResult(round=view(loaded, round_), error="unknown_key")
        correct = WORD_KEYS.index(body.word) == round_.gap.index
        state.append(EVENT, act="gap", word=body.word, correct=correct)  # type: ignore[arg-type]
    encounter._save(loaded)  # noqa: SLF001
    return RvTroisMotsResult(round=view(loaded, round_))


__all__ = ["Acts", "Round", "act", "build", "candidates", "find_word", "gap_for", "grade_match", "picture_cues", "view"]
