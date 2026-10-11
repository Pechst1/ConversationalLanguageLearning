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

The voices are OpenAI speech voices — the provider the journey's audio is pinned
to (``episode_audio.TTS_PROVIDER``). Seven people, seven different voices: the
five of the world bible's cast (their voices unchanged from the bible), M.
Marchand, and the narrator, who has a voice no character uses so narration is
never mistaken for a line.

WP-103 T1 «l'accent anglais» — *how* a voice speaks, in the same place
----------------------------------------------------------------------
The owner's first test: «everywhere the horrible English accent». The stock
``tts-1``/``tts-1-hd`` voices read French with an anglophone accent and cannot be
told otherwise. ``gpt-4o-mini-tts`` accepts an ``instructions`` field on the
speech endpoint, so each person now carries **instructions**: native French of
France with a neutral Paris accent and *no English accent*, plus the persona's
age, warmth and register — and a **pace** per CEFR band (A1 posé, A2 naturel un
peu lent, B1 and above naturel), because the radio was «too fast».

Romy is a Québécoise and is the one voice whose instructions ask for an accent:
a light Montréal accent, natural and easy to understand. That is the accent she
would have, it is not an English one, and the world bible says she «gets the
language but not the codes». Everyone else speaks neutral Paris French; Marin
(Brittany), Lila (Marseille) and Gus (Créteil) are given a persona, not a
regional accent, because a beginner's ear should not be asked to decode two
things at once.

A clip is therefore identified by its **speech spec** — model, instructions
version, pace and a digest of the instructions and speed actually sent
(:attr:`SpeechSpec.cache_key`) — so a change to any of them means the old audio
is simply never asked for again. Bump :data:`SPEECH_INSTRUCTIONS_VERSION` whenever
the wording below changes on purpose; the digest also catches a change that
forgot to.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

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
# WP-103 T1 — how a voice speaks: model, instructions, pace
# ---------------------------------------------------------------------------

#: Bump when the instruction wording below (or the pace table) changes on
#: purpose: it is part of every clip's cache key, so the old audio is never
#: served again. (The key also carries a digest of the exact text sent, so a
#: change that forgot the bump still cannot serve stale audio.)
SPEECH_INSTRUCTIONS_VERSION = "2026-09-29.1"

#: The steerable model (``instructions`` accepted on ``/audio/speech``).
STEERABLE_SPEECH_MODEL = "gpt-4o-mini-tts"

#: What the speech call falls back to if the steerable model errors. It cannot
#: be steered (no ``instructions``), which is the whole reason it is only a
#: fallback: a foreign accent is better than a silent character.
FALLBACK_SPEECH_MODEL = "tts-1-hd"

#: Models whose speech endpoint takes ``instructions``. Prefix match, so a
#: dated snapshot (``gpt-4o-mini-tts-2025-12-15``) is steerable too.
_STEERABLE_PREFIXES = ("gpt-4o-mini-tts",)

#: Models on which the ``speed`` field is known to change the pace: the
#: ``tts-1`` family, where OpenAI documents it (0.25–4.0). On ``gpt-4o-mini-tts``
#: OpenAI's team said in May 2025 that ``speed`` is not supported (a later
#: forum reply says it works again), so it is **not sent by default** and a
#: steerable model takes its pace from the instructions. The listening sheet
#: (2026-09-29) accepted ``speed=0.9`` without error and it ran 21 % longer than
#: the same clip without it (one pair — suggestive, not proof; the pace
#: *instructions* alone were inconsistent: A1 came out slower than B1 for five of
#: seven voices and faster for two). ``FEUILLETON_AUDIO_STEERABLE_A1_SPEED`` turns
#: it on for A1 on a steerable model without a code change, once the owner's ear
#: has judged clip 15 against clip 01.
SPEED_HONOURING_MODELS: frozenset[str] = frozenset({"tts-1", "tts-1-hd"})

#: The pace of each CEFR band's voice. A1 is «posé, articulé, sans traîner» (and
#: 0.9× where ``speed`` works), A2 «naturel, un peu lent», B1 and above «naturel».
PACES: tuple[str, ...] = ("a1", "a2", "b1")
PACE_SPEED: dict[str, float | None] = {"a1": 0.9, "a2": None, "b1": None}

_PACE_TEXT: dict[str, str] = {
    "a1": (
        "Rythme : posé, articulé, sans traîner. Chaque mot est bien détaché, avec de brèves "
        "pauses entre les groupes de sens, nettement plus lentement qu'en conversation courante."
    ),
    "a2": "Rythme : naturel, un peu lent, avec une articulation nette.",
    "b1": "Rythme : naturel, celui d'une conversation courante.",
}

_ACCENT_PARIS = (
    "Accent : tu parles français de France, en locuteur natif, avec un accent parisien neutre, "
    "sans aucun accent anglais ni étranger. Voyelles nasales et « r » français, liaisons "
    "naturelles, rythme et intonation du français (jamais l'accentuation de l'anglais)."
)

#: Romy alone is asked for an accent, and it is hers: Montréal.
_ACCENT_QUEBEC = (
    "Accent : tu parles français en locutrice native de Montréal, avec un léger accent québécois, "
    "naturel et facile à comprendre, sans en faire trop. Jamais d'accent anglais : c'est du "
    "français, avec les voyelles et l'intonation du français."
)

#: The persona, by cast id (and ``narrator``): age, warmth, register. Each is a
#: short paragraph — the model reads it, it must not be read *out*.
_PERSONA: dict[str, tuple[str, str]] = {
    NARRATOR_ID: (
        _ACCENT_PARIS,
        "Personnage : la voix off du feuilleton, celle qui raconte. Une voix neutre, chaleureuse et "
        "claire, qui raconte sans jouer les personnages.",
    ),
    "romy_tremblay": (
        _ACCENT_QUEBEC,
        "Personnage : Romy, journaliste de télévision québécoise, 32 ans, installée à Paris. "
        "Sèche, précise, pince-sans-rire, jamais larmoyante ; la chaleur ne vient qu'une fois en confiance.",
    ),
    "marin_leveque": (
        _ACCENT_PARIS,
        "Personnage : Marin, 33 ans, employé d'une ONG, un grand gentil. Voix grave, douce et posée, "
        "un peu rêveuse ; sentimental, jamais pressé, il évite le conflit.",
    ),
    "lila_bonnet": (
        _ACCENT_PARIS,
        "Personnage : Lila, 31 ans, institutrice et peintre. Voix claire, vive et lumineuse, "
        "taquine, généreuse ; juste une pointe de chaleur méridionale dans le rythme, sans accent marqué.",
    ),
    "augustin_de_roncourt": (
        _ACCENT_PARIS,
        "Personnage : Augustin, dit « Gus », 35 ans, dandy en costume impeccable qui se raconte comme "
        "une légende. Voix théâtrale, soignée, un brin emphatique et comique, diction parfaite ; "
        "toujours drôle, jamais caricatural.",
    ),
    "margaux_barman": (
        _ACCENT_PARIS,
        "Personnage : Margaux, la patronne du bar Le Mistral, 45 ans, qui a tout vu passer à son comptoir. "
        "Voix basse, sèche, économe ; peu de mots, ironie tranquille, aucun effet.",
    ),
    "landlord_marchand": (
        _ACCENT_PARIS,
        "Personnage : M. Marchand, propriétaire, 65 ans, parisien de la vieille école. Voix un peu rauque, "
        "diction soignée et formelle ; poli mais sec, il vouvoie et ne s'excuse pas.",
    ),
}

#: Anyone else — a generated character, the learner's own line — speaks plain,
#: native, neutral French.
_PERSONA_DEFAULT = (
    _ACCENT_PARIS,
    "Personnage : une personne ordinaire de la vie parisienne, adulte, naturelle et claire.",
)

#: A ``voice:{name}`` id (a planned listening clip only knows its voice) names
#: the cast member who owns that voice.
_CAST_OF_VOICE: dict[str, str] = {
    **{voice: person for person, voice in CAST_VOICES.items()},
    NARRATOR_VOICE: NARRATOR_ID,
}


def _persona_key(character_id: str | None) -> str | None:
    raw = str(character_id or "").strip().lower()
    if not raw or raw == NARRATOR_ID:
        return NARRATOR_ID
    if raw.startswith("voice:"):
        return _CAST_OF_VOICE.get(raw.split(":", 1)[1])
    return cast_id_for(raw)


def pace_for_band(band: str | None) -> str:
    """``"A1.2"`` → ``a1``, ``"a2"`` → ``a2``, B1 and above → ``b1``.

    An unreadable band is A1: the slowest voice is the safe error for a learner
    whose level is unknown.
    """

    match = re.match(r"^\s*([ABC][12])", str(band or "").upper())
    if match is None:
        return "a1"
    return {"A1": "a1", "A2": "a2"}.get(match.group(1), "b1")


def is_steerable_model(model: str | None) -> bool:
    """Does this speech model take ``instructions``?"""

    return str(model or "").strip().lower().startswith(_STEERABLE_PREFIXES)


def speech_instructions(character_id: str | None, band: str | None) -> str:
    """The full instruction text for one person at one band's pace."""

    accent, persona = _PERSONA.get(_persona_key(character_id) or "", _PERSONA_DEFAULT)
    return "\n".join((accent, persona, _PACE_TEXT[pace_for_band(band)]))


@dataclass(frozen=True, slots=True)
class SpeechSpec:
    """Everything that decides how one line sounds, and so what its clip is.

    ``instructions`` is ``None`` on a model that cannot be steered and ``speed``
    is ``None`` where the pace is not sent as a number.
    """

    model: str
    pace: str
    instructions: str | None
    speed: float | None

    @property
    def cache_key(self) -> str:
        """``model|instructions-version|pace|digest`` — short enough for the
        60-character ``model`` column it is stored in.

        The digest covers the instruction text and the speed actually sent, so
        two people with different personas never share a clip and an edited
        wording never serves the old one.
        """

        digest = hashlib.sha256(
            f"{self.instructions or ''}|{self.speed if self.speed is not None else ''}".encode()
        ).hexdigest()[:6]
        return f"{self.model}|{SPEECH_INSTRUCTIONS_VERSION}|{self.pace}|{digest}"


def speech_spec(
    character_id: str | None,
    band: str | None,
    *,
    model: str,
    steerable_a1_speed: float | None = None,
) -> SpeechSpec:
    """How this person speaks at this band on this model.

    ``instructions`` only where the model takes them. ``speed`` only where it is
    known to change the pace (:data:`SPEED_HONOURING_MODELS`: 0.9 at A1), or at
    A1 on a steerable model when ``steerable_a1_speed`` is given — the opt-in
    the listening sheet's evidence leaves to the owner's ear.
    """

    pace = pace_for_band(band)
    steerable = is_steerable_model(model)
    speed: float | None = None
    if str(model).strip().lower() in SPEED_HONOURING_MODELS:
        speed = PACE_SPEED[pace]
    elif steerable and pace == "a1" and steerable_a1_speed is not None:
        speed = float(steerable_a1_speed)
    return SpeechSpec(
        model=str(model),
        pace=pace,
        instructions=speech_instructions(character_id, band) if steerable else None,
        speed=speed,
    )


def parse_cache_key(key: str | None) -> tuple[str, str, str, str] | None:
    """``(model, version, pace, digest)`` of a :attr:`SpeechSpec.cache_key`, or
    ``None`` for anything else — in particular a legacy clip stored under a
    bare model name, which is therefore never current."""

    parts = str(key or "").split("|")
    if len(parts) != 4 or not all(parts):
        return None
    return parts[0], parts[1], parts[2], parts[3]


def cache_key_is_current(key: str | None, *, models: tuple[str, ...]) -> bool:
    """Was this clip made at today's instructions version by one of ``models``?"""

    parsed = parse_cache_key(key)
    return parsed is not None and parsed[0] in models and parsed[1] == SPEECH_INSTRUCTIONS_VERSION


def model_of_cache_key(key: str | None) -> str:
    """The speech model a cache key (or a legacy bare model name) names."""

    return str(key or "").split("|", 1)[0]


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
    "FALLBACK_SPEECH_MODEL",
    "PACES",
    "PACE_SPEED",
    "SPEECH_INSTRUCTIONS_VERSION",
    "SPEED_HONOURING_MODELS",
    "STEERABLE_SPEECH_MODEL",
    "SpeechSpec",
    "cache_key_is_current",
    "is_steerable_model",
    "model_of_cache_key",
    "pace_for_band",
    "parse_cache_key",
    "speech_instructions",
    "speech_spec",
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
