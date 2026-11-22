"""«Papier · la voix» (2026-11-22, ``REVUE_VOIX_ENABLED``): the paper is heard, not only read.

Three things, all from text the session already shows the learner:

* **the lead read aloud** — the story's lead at the learner's band, in the newsroom's voice
  (:data:`NEWSREADER_ID`: the narrator's voice, which no character uses, the same for every
  edition);
* **the counter heard first** — each regular's take (and the reply, and the last word) in that
  regular's own voice (``cast_voices.voice_for_character``); the client shows the words once the
  line has been played or the learner asks to read;
* **«la dictée de Romy»** — one sentence of the lead, spoken once, written by the learner and
  graded by the radio's dictation adapter (:func:`radio.grade_dictee`, the journey's grader),
  the slips shown as Romy's proof marks (:func:`comptoir_loop.proof_marks`), never the answer
  before the second try.

**The clips are the scene's line clips** (``line_audio.speak_line``): one row per learner in
``line_audio_clips``, keyed by the line's voice and words and the band's speech spec, so a clip
is spoken once per story, band and line; the next learner gets a byte copy, no call. The route
speaks only a line of the session (:func:`session_lines`, matched by ``line_audio.match_line``):
never arbitrary text. Synthesis also needs ``ATELIER_EPISODE_AUDIO_ENABLED``; without it, or
near the learner's daily cap, a line answers ``disabled`` and the device voice reads it.

No state is written: the dictée's try number comes with the answer, and the grade is never
evidence for a word (the radio's placeholder target).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.services import cast_voices, sentence_line
from app.services.line_audio import StepLine
from app.services.revue import comptoir_loop, radio
from app.services.revue.encounter import Loaded

#: The newsroom's reading voice: the narrator's (``sage``), which no character speaks with.
NEWSREADER_ID = cast_voices.NARRATOR_ID
#: The ``surface`` on the WP-91 priced row of a line spoken here.
AUDIO_SURFACE = "revue_voix"
#: Two tries at the dictée; the line is shown after the second (or once it is right).
DICTEE_TRIES = 2
DICTEE_MIN_WORDS = 4
#: The longest sentence a band is asked to write from one hearing.
DICTEE_MAX_WORDS: dict[str, int] = {"A1": 10, "A2": 14, "B1": 18, "B2": 22}

_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def enabled() -> bool:
    return bool(getattr(settings, "REVUE_ENABLED", False) and getattr(settings, "REVUE_VOIX_ENABLED", False))


def audio_ready() -> bool:
    """Can this deployment make a clip at all? Off: the device voice, and the text at once."""

    return bool(getattr(settings, "ATELIER_EPISODE_AUDIO_ENABLED", False))


@dataclass(frozen=True)
class VoixLine:
    kind: str  # "lead" | "take" | "reply" | "last_word" | "dictee"
    speaker_id: str
    text_fr: str

    def step_line(self) -> StepLine:
        return StepLine(self.speaker_id, cast_voices.normalize_line_text(self.text_fr).strip())


def band_of(loaded: Loaded) -> str:
    return str(loaded.plan.learner.band)


def _words(text: str) -> int:
    return len(_WORD.findall(text or ""))


def dictee_sentence(lead_fr: str, band: str) -> str | None:
    """The lead's shortest sentence the band can write from one hearing (the first of equals),
    or ``None`` when no sentence fits: never a fragment, never a cut sentence."""

    limit = DICTEE_MAX_WORDS.get(band, DICTEE_MAX_WORDS["B2"])
    fits = [
        sentence.strip()
        for sentence in sentence_line.sentences(lead_fr)
        if DICTEE_MIN_WORDS <= _words(sentence) <= limit and sentence.strip()[-1:] in ".!?…"
    ]
    return min(fits, key=_words) if fits else None


def session_lines(loaded: Loaded) -> list[VoixLine]:
    """Every line of the session the paper may speak, as the learner sees it now."""

    band = band_of(loaded)
    lead = loaded.dossier.lead_for(band).fr
    lines = [VoixLine("lead", NEWSREADER_ID, lead)]
    takes = loaded.dossier.comptoir
    if takes is not None and comptoir_loop.session_mode(loaded.state) == "comptoir":
        lines += [VoixLine("take", guest.id, guest.take.for_band(band).fr) for guest in takes.guests]
        acts = comptoir_loop.Acts(loaded.state)
        reply = (acts.opinion or {}).get("reply") or {}
        if acts.settled and reply.get("by") and reply.get("fr"):
            lines.append(VoixLine("reply", str(reply["by"]), str(reply["fr"])))
            last = str((acts.comeback or {}).get("last_word_fr") or "")
            if last:
                lines.append(VoixLine("last_word", str(reply["by"]), last))
    sentence = dictee_sentence(lead, band)
    if sentence:
        lines.append(VoixLine("dictee", NEWSREADER_ID, sentence))
    return [line for line in lines if len(line.text_fr.strip()) >= 2]


def manifest(loaded: Loaded) -> dict[str, Any]:
    lines = session_lines(loaded)
    dictee = next((line for line in lines if line.kind == "dictee"), None)
    return {
        "audio": "ready" if audio_ready() else "device",
        "newsreader_id": NEWSREADER_ID,
        "lines": [
            {"kind": line.kind, "speaker_id": line.speaker_id, "text_fr": line.text_fr}
            for line in lines
            if line.kind != "dictee"
        ],
        # The dictée needs a real recording: the device voice is not offered for it.
        "dictee": (
            {"text_fr": dictee.text_fr, "words": _words(dictee.text_fr), "max_tries": DICTEE_TRIES}
            if dictee is not None and audio_ready()
            else None
        ),
    }


def _marks(answer: str, expected: str) -> list[dict[str, Any]]:
    """Romy's proof marks on the learner's own words, case aside (the grader ignores it)."""

    lowered = answer.lower()
    if len(lowered) != len(answer):  # a letter whose lower case is longer: mark nothing rather than a wrong span
        return []
    marks = comptoir_loop.proof_marks(lowered, expected.lower())
    return [{**mark, "span_fr": answer[mark["start"]:mark["start"] + len(mark["span_fr"])]} for mark in marks]


def grade(loaded: Loaded, answer: str, attempt: int, language: str) -> dict[str, Any] | None:
    """One try at the dictée: the verdict, the marks, and the line only once it may be shown."""

    sentence = dictee_sentence(loaded.dossier.lead_for(band_of(loaded)).fr, band_of(loaded))
    if sentence is None:
        return None
    attempt = max(1, min(int(attempt or 1), DICTEE_TRIES))
    result = radio.grade_dictee(sentence, answer, language=language)
    met = result.outcome == "met"
    resolved = met or attempt >= DICTEE_TRIES
    return {
        "outcome": result.outcome,
        "attempt": attempt,
        "max_tries": DICTEE_TRIES,
        "resolved": resolved,
        "answer_fr": answer,
        "marks": [] if met else _marks(answer, sentence),
        # No solution before a retry: the line and the grader's note (which carries it) wait.
        "expected_fr": sentence if resolved else None,
        "note": result.note if resolved and not met else None,
    }


__all__ = [
    "AUDIO_SURFACE",
    "DICTEE_TRIES",
    "NEWSREADER_ID",
    "VoixLine",
    "audio_ready",
    "dictee_sentence",
    "enabled",
    "grade",
    "manifest",
    "session_lines",
]
