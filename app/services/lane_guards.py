"""WP-133b findings 3 and 4 — the guards a character's live reaction and a day's
ending still lacked.

**Finding 3 (gender agreement).** ``living_story._check_address`` already runs on the
voice lane's reply and on the story lane's ``resolution_fr``, but it only knows the
twenty adjectives of ``_MASCULINE_AGREEMENT`` / ``_FEMININE_AGREEMENT`` after «tu es».
The paid C1 read of 2026-10-06 shipped two lines it cannot see:

* «pauvre toi, **gelé**, mais content» — a participle in apposition to «toi»;
* «tu n'es pas encore **décidé**» — a past participle, not on the list.

:func:`check_agreement` runs the existing check first (same lists, same hint), then
the wider net here: any singular past participle in -é/-ée after a second-person
«être» / «se sentir» / «avoir l'air» / «voilà» frame or in apposition to «toi», plus
a short supplement of common agreeing adjectives and -i/-u participles the shared
lists do not carry. A gender the learner gave (``learner.address``) keeps its own
forms; a form the learner used about themselves («je suis gelé») may be said back.

**Finding 4 (echo, role swap).** :func:`echo_hit` refuses a reaction that repeats the
learner: one of their sentences of three or more words in their own person or speech
act («Merci pour la soupe.», «Je peux rester ?») verbatim, or four consecutive content words of
their reply in the same order. A shared word or a short «Tu restes ?» reprise
passes. The deterministic self-repair choice («Pardon, je reste ou resterai … ?»)
that put the learner's «je» in the character's mouth is handled where it is built
(``journey_conversation.self_repair_question``). Role swaps beyond that — a
character keeping the cactus she has just given away — are prompt-only (the voice
lane now receives who said what and the scene's facts); nothing here detects them.
"""

from __future__ import annotations

import re

from app.services import living_story as engine

# ---------------------------------------------------------------------------
# Finding 3 — agreement with a gender the learner never gave
# ---------------------------------------------------------------------------

#: Agreeing adjectives and -i/-u/-s participles the shared lists do not carry
#: (masculine, feminine). Participles in -é/-ée need no list: they are matched by
#: their ending below.
_SUPPLEMENT_PAIRS: tuple[tuple[str, str], ...] = (
    ("venu", "venue"), ("revenu", "revenue"), ("parti", "partie"), ("sorti", "sortie"),
    ("ravi", "ravie"), ("assis", "assise"), ("déçu", "déçue"), ("convaincu", "convaincue"),
    ("prudent", "prudente"), ("courageux", "courageuse"), ("amoureux", "amoureuse"),
    ("jaloux", "jalouse"), ("fier", "fière"), ("nerveux", "nerveuse"), ("fou", "folle"),
    ("épuisé", "épuisée"), ("mort", "morte"), ("tout seul", "toute seule"),
)
_SUPPLEMENT_MASCULINE = tuple(m for m, _ in _SUPPLEMENT_PAIRS)
_SUPPLEMENT_FEMININE = tuple(f for _, f in _SUPPLEMENT_PAIRS)

#: Words in -é that are not a participle agreeing with anyone.
_NOT_PARTICIPLES = frozenset({"été", "café", "thé", "côté", "bébé", "clé", "dé", "pré", "né"})

#: At most three of these between the frame and the participle («pas encore»,
#: «un peu», «vraiment très»). A free word there would let «tu es en été» through.
_ADVERB = (
    r"(?:pas|plus|encore|déjà|toujours|jamais|très|trop|si|bien|vraiment|assez|"
    r"tellement|un peu|peut être|sans doute|aussi|enfin|donc|quand même|tout|toute|"
    r"complètement|totalement|presque|un|peu)"
)

#: Frames in which the next agreeing word describes the learner. Matched against
#: ``living_story._folded`` text («n'es» reads «n es», «l'air» reads «l air»).
_FRAMES = (
    r"tu (?:ne |n )?(?:es|étais|seras|serais|sembles|as l air|avais l air|te sens|te sentais)"
    r"|t es|t as l air"
    r"|vous (?:ne |n )?(?:êtes|étiez|serez|seriez|semblez|avez l air|vous sentez)"
    r"|te voilà|vous voilà|toi"
)
_FRAME = re.compile(rf"\b(?:{_FRAMES})(?:\s+{_ADVERB}){{0,3}}\s+((?:tout |toute )?\w+)\b")


def _forbidden(address: str | None) -> tuple[tuple[str, ...], bool, bool]:
    """(listed forms forbidden, masculine -é forbidden, feminine -ée forbidden)."""

    if address == "masculine":
        return _SUPPLEMENT_FEMININE, False, True
    if address == "feminine":
        return _SUPPLEMENT_MASCULINE, True, False
    return _SUPPLEMENT_MASCULINE + _SUPPLEMENT_FEMININE, True, True


def agreement_hits(text: str, address: str | None, *, own: frozenset[str] = frozenset()) -> list[str]:
    """The words in ``text`` that agree with a gender ``address`` does not give.

    Only the wider net of this module; :func:`check_agreement` runs the shared
    ``living_story`` check as well."""

    folded = f" {engine._folded(text or '')} "
    listed, masculine_e, feminine_e = _forbidden(address)
    hits: list[str] = []
    for match in _FRAME.finditer(folded):
        word = match.group(1)
        bare = word.split()[-1]
        if word in listed or bare in listed:
            hits.append(word)
        elif bare in _NOT_PARTICIPLES or len(bare) < 4:
            continue
        elif bare.endswith("ée"):
            if feminine_e:
                hits.append(bare)
        elif bare.endswith("é") and masculine_e:
            hits.append(bare)
    return [hit for hit in dict.fromkeys(hits) if hit not in own and hit.split()[-1] not in own]


#: «je suis», «j'étais», «je me sens», and the (up to three) words after it.
_SELF_FRAME = re.compile(r"\b(?:je (?:ne )?suis|j etais|je (?:ne )?me sens)((?:\s+\w+){1,3})")


def learner_own_forms(learner_texts: list[str]) -> frozenset[str]:
    """What the learner said about themselves — the shared list's forms plus any word
    after «je suis» / «je me sens» (so «je suis gelé» lets «tu es gelé ?» through)."""

    folded = f" {engine._folded(' '.join(t for t in learner_texts if t))} "
    extra = {
        word
        for match in _SELF_FRAME.finditer(folded)
        for word in match.group(1).split()
    }
    extra |= {f"tout {w}" for w in extra} | {f"toute {w}" for w in extra}
    return engine.learner_self_forms(learner_texts) | frozenset(extra)


def check_agreement(texts: list[str], address: str | None, *, own: frozenset[str] = frozenset()) -> None:
    """The shared address check, then this module's wider agreement net.

    Raises ``StoryUnavailable("gendered_agreement")`` with a hint naming the word,
    so a lane's retry knows what to change."""

    engine._check_address(texts, address, own=own)
    for text in texts:
        hits = agreement_hits(text, address, own=own)
        if hits:
            raise engine.StoryUnavailable(
                "gendered_agreement",
                hint=(
                    f"\"{hits[0]}\" agrees with a gender the learner never gave. Say it "
                    "without agreeing on them: \"tu as froid\", \"tu hésites encore\", "
                    "\"ça te plaît\" — or write the sentence about the thing, the room "
                    "or the other character instead."
                ),
            )


# ---------------------------------------------------------------------------
# Finding 4 — a reaction that hands the learner's words back
# ---------------------------------------------------------------------------

#: Function words: never content, so «la», «de», «tu» shared with the learner are
#: not an echo.
_FUNCTION_WORDS = frozenset(
    """a à au aux avec c ça ce ces cet cette d dans de des du elle elles en est et eu
    il ils j je l la le les leur lui m ma mais me mes moi mon n ne ni nous on ou où par
    pas pour qu que qui quoi quand s sa se ses si son sur t ta te tes toi ton tu un une
    vous y oui non bon ah oh eh bien très plus comme alors donc encore aussi ici là
    est es suis sont être ai as avons avez ont va vas vais quand comment pourquoi
    combien""".split()
)
#: Words that belong to whoever says them: the learner's own person and their own
#: speech acts. A learner sentence carrying one, said back verbatim by the character,
#: is the learner's line in the character's mouth («Merci pour la soupe.»,
#: «Je peux rester ?»). A bare noun phrase said back is a confirmation and passes
#: («Un thé en terrasse.» → «Un thé en terrasse, tout de suite.»).
_SPEAKER_WORDS = frozenset(
    {"je", "j", "me", "m", "moi", "mon", "ma", "mes", "merci", "pardon", "excuse", "excusez",
     "plaît"}
)
ECHO_SENTENCE_MIN_WORDS = 3
ECHO_CONTENT_RUN = 4
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")


def _tokens(text: str) -> list[str]:
    return engine._folded(text or "").split()


def _contains_run(haystack: list[str], needle: list[str]) -> bool:
    size = len(needle)
    return bool(size) and any(haystack[i : i + size] == needle for i in range(len(haystack) - size + 1))


def _content(tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in _FUNCTION_WORDS and len(token) > 1]


def echo_hit(reply: str, learner_text: str) -> str | None:
    """The span of ``learner_text`` that ``reply`` repeats, or None.

    Fires on: a learner sentence of ≥ 3 words in the learner's own person or speech
    act (``_SPEAKER_WORDS``), verbatim — «Merci pour la soupe.», or the learner's own
    question asked back («Je peux rester ?»); four consecutive content words of the
    learner's reply, in order. A shared word, a name, a confirmation of a noun phrase
    («Un thé en terrasse, tout de suite.»), a reprise in the character's own person
    («Tu restes ?» after «Je reste») or of a short question before answering it
    («On commence quand ? Demain.») passes."""

    said = _tokens(reply)
    if not said:
        return None
    for sentence in _SENTENCE.findall(learner_text or ""):
        tokens = _tokens(sentence)
        if len(tokens) < ECHO_SENTENCE_MIN_WORDS:
            continue
        if _SPEAKER_WORDS & set(tokens) and _contains_run(said, tokens):
            return sentence.strip()
    learner_content = _content(_tokens(learner_text))
    reply_content = _content(said)
    for start in range(len(learner_content) - ECHO_CONTENT_RUN + 1):
        run = learner_content[start : start + ECHO_CONTENT_RUN]
        if _contains_run(reply_content, run):
            return " ".join(run)
    return None


def check_echo(reply: str, learner_text: str, *, character_name: str | None = None) -> None:
    span = echo_hit(reply, learner_text)
    if span is None:
        return
    who = f"You are {character_name}; " if character_name else ""
    raise engine.StoryUnavailable(
        "reply_echoes_learner",
        hint=(
            f"The reply repeats the learner's words («{span[:120]}»). {who}the learner "
            "said that, not you. React to it in your own words — never repeat their "
            "sentence, never ask their question back, never speak their line."
        ),
    )


# ---------------------------------------------------------------------------
# Who said what (finding 4b): the voice lane's view of the scene's roles
# ---------------------------------------------------------------------------


def who_is_who(scene: dict, character: dict) -> dict:
    """The roles of the exchange and the scene's facts, spelled out for the voice
    lane: whose words ``learner_text`` and ``history[].learner`` are, who the
    character is, and what the scene established (the premise, the director's
    before → after, the task the learner was given)."""

    name = str(character.get("name") or character.get("id") or "the character")
    checklist = scene.get("season_checklist") or {}
    facts = [str(scene.get("premise_fr") or "").strip()]
    before, after = str(checklist.get("change_before") or ""), str(checklist.get("change_after") or "")
    if before or after:
        facts.append(f"{before} → {after}".strip(" →"))
    return {
        "you_are": name,
        "the_learner_is": "the visitor you are talking to (the second person of the scene)",
        "learner_text_and_history_learner_are": "the learner's words, never yours",
        "history_character_is": f"what you, {name}, already said",
        "learner_task": scene.get("objective_native"),
        "scene_facts": [fact for fact in facts if fact],
    }
