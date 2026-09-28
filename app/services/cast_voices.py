"""WP-91 «Les voix» — one fixed voice per cast member, in one place.

Learners come to know voices the way they know faces, so a character must sound
the same in the radio episode, in a tapped portrait, in a reply and in a
listening item. Before this module the episode radio pinned its own table
(``episode_audio.PINNED_VOICES``) while the world bible listed different voices
for the same people (Romy was ``shimmer`` in one and ``nova`` in the other, and
Margaux and Augustin shared ``alloy``). This is now the single source of truth:
the world bible's ``cast[].voice.voice`` must agree with :data:`CAST_VOICES`
(``tests/test_wp91_voices.py`` pins the parity), and every speaking surface asks
:func:`voice_for_character`.

The voices are OpenAI speech voices available on ``tts-1``/``tts-1-hd`` — the
provider the journey's audio is pinned to (``episode_audio.TTS_PROVIDER``).
Seven people, seven different voices: the five of the world bible's cast (their
voices unchanged from the bible), M. Marchand, and the narrator, who has a
voice no character uses so narration is never mistaken for a line.
"""
from __future__ import annotations

import hashlib

#: The id narration lines carry, in the episode manifest and in the cache.
NARRATOR_ID = "narrator"

#: The narrator's voice. No cast member speaks with it.
NARRATOR_VOICE = "sage"

#: The recurring cast, by full id. The world bible (``world_bible_paris_v2.json``)
#: lists the same voice under each cast member's ``voice``.
CAST_VOICES: dict[str, str] = {
    "romy_tremblay": "nova",
    "marin_leveque": "onyx",
    "lila_bonnet": "shimmer",
    "augustin_de_roncourt": "fable",
    "margaux_barman": "alloy",
    "landlord_marchand": "echo",
}

#: Short ids and nicknames a scene may use for the same person. Matching also
#: falls back to the id's first token, so ``marin`` and ``marin_leveque`` are
#: one voice.
CAST_ALIASES: dict[str, str] = {
    "romy": "romy_tremblay",
    "marin": "marin_leveque",
    "lila": "lila_bonnet",
    "augustin": "augustin_de_roncourt",
    "gus": "augustin_de_roncourt",
    "margaux": "margaux_barman",
    "marchand": "landlord_marchand",
    "landlord": "landlord_marchand",
}

#: The learner's own line in a script («toi»), when one is ever spoken.
LEARNER_VOICE = "coral"
LEARNER_IDS: frozenset[str] = frozenset({"toi", "learner", "you", "user"})

#: Where a generated (non-recurring) character's voice is hashed into. The
#: narrator's voice is never in it. A generated character may share a voice
#: with a cast member — that is why the listening surfaces show the speaker's
#: *name*: the voice is a cue, never the only carrier of who is talking.
CHARACTER_VOICES: tuple[str, ...] = ("alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "shimmer")

#: The legacy name the episode radio exported: every pinned id → its voice.
PINNED_VOICES: dict[str, str] = {
    **CAST_VOICES,
    **{alias: CAST_VOICES[full] for alias, full in CAST_ALIASES.items()},
    **dict.fromkeys(LEARNER_IDS, LEARNER_VOICE),
}


def cast_id_for(character_id: str | None) -> str | None:
    """The recurring cast member's full id for any id or alias, or ``None``."""

    raw = str(character_id or "").strip().lower()
    if not raw:
        return None
    if raw in CAST_VOICES:
        return raw
    if raw in CAST_ALIASES:
        return CAST_ALIASES[raw]
    head = raw.split("_", 1)[0]
    return CAST_ALIASES.get(head) or (head if head in CAST_VOICES else None)


def voice_for_character(character_id: str | None) -> str:
    """The voice a speaker keeps, for the life of the cast.

    Deterministic in every branch: the narrator (or no speaker) gets the
    narrator's voice, the recurring cast their pinned voice, the learner theirs,
    and anyone else hashes into :data:`CHARACTER_VOICES` — so a generated
    character also keeps one voice across days.
    """

    raw = str(character_id or "").strip().lower()
    if not raw or raw == NARRATOR_ID:
        return NARRATOR_VOICE
    if raw in LEARNER_IDS:
        return LEARNER_VOICE
    cast = cast_id_for(raw)
    if cast is not None:
        return CAST_VOICES[cast]
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return CHARACTER_VOICES[digest[0] % len(CHARACTER_VOICES)]


# ---------------------------------------------------------------------------
# A spoken line's identity: who says it, and exactly what
# ---------------------------------------------------------------------------

#: The authenticated route a clip is fetched from (``GET``), as a public
#: ``RecallPrompt.audio_url`` carries it.
LINE_AUDIO_PATH_PREFIX = "/api/v1/daily-journeys/line-audio/"

#: Bumped only if the digest's inputs ever change; old clips are then simply
#: never asked for again.
LINE_AUDIO_KEY_VERSION = "line-audio-v1"

_QUOTE_FOLD = {
    "\u2018": "'", "\u2019": "'", "\u201b": "'", "\u2032": "'", "\u00b4": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u00a0": " ", "\u202f": " ", "\u2009": " ",
}


def normalize_line_text(text: str | None) -> str:
    """The form a line is cached and matched under: smart quotes and exotic
    spaces folded, whitespace collapsed. Case and accents are kept — they are
    what is spoken."""

    value = str(text or "")
    for source, replacement in _QUOTE_FOLD.items():
        value = value.replace(source, replacement)
    return " ".join(value.split())


def clip_id_for(voice: str, text: str | None) -> str:
    """``"{voice}-{digest}"`` — one line in one voice, the same id every day.

    The voice leads so the ``GET`` route can speak a planned listening item on
    its first request knowing only the id and the step's own private text; the
    digest covers both, so an id can never be pointed at other words.
    """

    clean_voice = str(voice or NARRATOR_VOICE).strip().lower() or NARRATOR_VOICE
    digest = hashlib.sha256(
        f"{LINE_AUDIO_KEY_VERSION}|{clean_voice}|{normalize_line_text(text)}".encode()
    ).hexdigest()[:32]
    return f"{clean_voice}-{digest}"


def voice_of_clip_id(clip_id: str | None) -> str | None:
    """The voice a clip id names, or ``None`` for a malformed id."""

    voice, sep, digest = str(clip_id or "").partition("-")
    if not sep or not voice or len(digest) != 32:
        return None
    if not voice.isalpha() or any(char not in "0123456789abcdef" for char in digest):
        return None
    return voice


def line_audio_url(voice: str, text: str | None) -> str:
    """The public path of one line's clip."""

    return LINE_AUDIO_PATH_PREFIX + clip_id_for(voice, text)


__all__ = [
    "LINE_AUDIO_KEY_VERSION",
    "LINE_AUDIO_PATH_PREFIX",
    "clip_id_for",
    "line_audio_url",
    "normalize_line_text",
    "voice_of_clip_id",
    "CAST_ALIASES",
    "CAST_VOICES",
    "CHARACTER_VOICES",
    "LEARNER_IDS",
    "LEARNER_VOICE",
    "NARRATOR_ID",
    "NARRATOR_VOICE",
    "PINNED_VOICES",
    "cast_id_for",
    "voice_for_character",
]
