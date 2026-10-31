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
import unicodedata

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


# ---------------------------------------------------------------------------
# WP-155 §1 — the gender scrub on every field the lanes write
# ---------------------------------------------------------------------------

#: Inclusive spellings that mark both genders at once: «engagé·e», «prêt•e»,
#: «engagé.e», «content(e)». Lower-case letters on both sides, so «M. Marchand» and
#: «fini.Et» are prose.
_DOT_FORM = re.compile(r"(?<=[a-zà-ÿ])[·•⋅‧∙](?=[a-zà-ÿ])")
_PERIOD_FORM = re.compile(
    r"(?<=[a-zà-ÿ])\.(?:e|es|ne|nes|le|les|se|ses|te|tes|ve|ves|rice|rices|euse|euses|ère|ères)(?![\wÀ-ÿ])"
)
_PAREN_FORM = re.compile(r"(?<=[a-zà-ÿ])\((?:e|es|ne|le|ve|se|te|trice|euse|ère|ères)\)", re.IGNORECASE)
#: «le·la apprenant·e», «Le apprenant» (what the dot scrub used to leave behind),
#: «la apprenante», «l'apprenant(e)», «l'apprenante» — every gendered way of naming
#: the learner as «apprenant». «L'apprenant» alone is the elided, unmarked form.
_APPRENANT = re.compile(
    r"\b(?:(?:le|la)(?:\s*[·•/.]\s*(?:le|la))?\s+|l['’]\s*)apprenant(?:[·•.]?e|\(e\))?(?![\wÀ-ÿ])",
    re.IGNORECASE,
)


def gender_form_hits(text: str) -> list[str]:
    """The inclusive or gendered spellings aimed at the learner in ``text``: middle-dot,
    period and bracket forms, and «le/la apprenant(e)» (WP-149 read: «tu t'es
    engagé·e», «Le apprenant»)."""

    raw = text or ""
    hits = [m.group(0) for m in _APPRENANT.finditer(raw) if m.group(0).casefold().replace("’", "'") != "l'apprenant"]
    for pattern in (_DOT_FORM, _PERIOD_FORM, _PAREN_FORM):
        for match in pattern.finditer(raw):
            start = raw.rfind(" ", 0, match.start()) + 1
            end = match.end()
            while end < len(raw) and (raw[end].isalpha() or raw[end] in "·•⋅‧∙"):
                end += 1
            hits.append(raw[start:end])
    return list(dict.fromkeys(hits))


#: «il/elle», «elle ou il», «lui/elle»: both pronouns for the learner, as in
#: «L'apprenant veut dire qu'il/elle a faim» (agency pilot 2026-10-12, B4).
_PRONOUN_PAIR = re.compile(
    r"\b(?:il|elle|ils|elles|lui|eux)\s*(?:/|\bou\b|\()\s*(?:il|elle|ils|elles|lui|eux)\b\)?",
    re.IGNORECASE,
)


#: Only a masculine and a feminine form of the same person hedge a gender
#: («elle ou elles» is a number, not a gender).
_GENDER_PAIRS = frozenset(
    frozenset(pair) for pair in (("il", "elle"), ("ils", "elles"), ("lui", "elle"), ("eux", "elles"))
)


def has_pronoun_pair(text: str) -> bool:
    """Does the text name the learner with both pronouns («il/elle», «il ou elle»)?"""

    return any(
        frozenset(word.casefold() for word in re.findall(r"[a-zà-ÿ]+", match.group(0), re.IGNORECASE)) - {"ou"}
        in _GENDER_PAIRS
        for match in _PRONOUN_PAIR.finditer(text or "")
    )


def scrub_learner_gender(text: str) -> str:
    """The deterministic rewrite for a private field (``understood_intent``): every
    «le/la apprenant(e)» becomes «l'apprenant», and an inclusive spelling loses its
    second half. Never applied to a line the learner reads: there a form left behind
    («engagé») would still agree, so those fields are refused instead."""

    def apprenant(match: re.Match) -> str:
        return "L'apprenant" if match.group(0)[:1].isupper() else "l'apprenant"

    scrubbed = _APPRENANT.sub(apprenant, text or "")
    scrubbed = re.sub(r"[·•⋅‧∙][a-zà-ÿ]+", "", scrubbed)
    scrubbed = _PERIOD_FORM.sub("", scrubbed)
    return _PAREN_FORM.sub("", scrubbed)


def check_lane_gender(
    texts: list[str], address: str | None, *, own: frozenset[str] = frozenset(), field: str = "the line"
) -> None:
    """WP-155: the page guard's rule on a lane's learner-facing output. An inclusive
    spelling or «le/la apprenant(e)» is refused with a hint (the lane retries), then
    the shared and the wider agreement checks run as before."""

    forms = [
        hit
        for text in texts
        for hit in gender_form_hits(text)
        # «l'apprenante» is the form a learner who gave the feminine reads as theirs.
        if not (address == "feminine" and hit.casefold().replace("’", "'") == "l'apprenante")
    ]
    if forms:
        raise engine.StoryUnavailable(
            "learner_gender_form",
            hint=(
                f"{field} writes «{forms[0]}»: an inclusive or gendered form aimed at the "
                "learner, whose gender is not known here. Never a middle dot, a bracket «(e)» "
                "or «le/la apprenant»: say it without agreeing on them («tu as dit oui», «on y "
                "va ?», «l'apprenant»), or write about the thing, the room or the other character."
            ),
        )
    # A vocative endearment («, mon grand») is cut, not refused, as everywhere else.
    check_agreement([engine._scrub_endearments(text, address) for text in texts if text], address, own=own)


# ---------------------------------------------------------------------------
# WP-155 §2 — an ending never credits the learner with a choice they did not make
# ---------------------------------------------------------------------------

#: Verbs that credit someone with a choice, a proposal or a pledge.
_CHOICE_VERB = (
    r"(?:propos\w*|promet\w*|promis\w*|engag\w*|décid\w*|choisi\w*|accept\w*|offr\w*|offert\w*"
    r"|jur\w*|prévoi\w*|prévu\w*|annonc\w*|organis\w*)"
)
_OBJECT_PRONOUNS = r"(?:lui|leur|nous|vous|me|m|te|t|l|le|la|les|y|en|se|s)"
_AUXILIARY = r"(?:as|avais|auras|es|étais|vas|allais|viens de|venais de)"
#: A word or two a clause may open with before its subject («alors tu acceptes»).
_LEAD = r"(?:(?:alors|donc|ainsi|finalement|enfin|bref|ah|oh|bon|puis|maintenant|ce soir|demain)\s+){0,2}"
#: «tu proposes», «tu lui as promis», «tu t'es engagé», «tu vas organiser» — folded.
_LEARNER_CLAIM = re.compile(
    rf"^{_LEAD}tu\s+(?:{_OBJECT_PRONOUNS}\s+){{0,2}}(?:{_AUXILIARY}\s+)?(?:{_OBJECT_PRONOUNS}\s+){{0,2}}"
    rf"(?P<verb>{_CHOICE_VERB})\b(?P<object>.*)$"
)
#: The same verb after «et» in a chain the learner already heads («Tu offres ton aide
#: et proposes un rendez-vous»).
_CHAINED_CLAIM = re.compile(
    rf"^(?:{_OBJECT_PRONOUNS}\s+){{0,2}}(?:{_AUXILIARY}\s+)?(?:{_OBJECT_PRONOUNS}\s+){{0,2}}"
    rf"(?P<verb>{_CHOICE_VERB})\b(?P<object>.*)$"
)
#: What a learner says to take up a character's offer.
_ACCEPTS = re.compile(
    r"\b(?:oui|ouais|d accord|ok|okay|ça marche|ca marche|volontiers|avec plaisir|je veux bien"
    r"|j accepte|bonne idée|pourquoi pas|entendu|c est parti|allons y)\b"
)
_SUPPORT_SHARE = 0.5


def _stems(text: str) -> set[str]:
    """Content words by their first four letters: «aider» is «aide», «proposes» is
    «propose», «demain» is «demain» — French inflects at the end."""

    return {token[:4] for token in _content(_tokens(text)) if len(token) >= 4}


def _claims(text: str) -> list[str]:
    """Each «tu <choice verb> <what>» the text states (questions are asked, not
    stated), as the folded clause from the verb on."""

    found: list[str] = []
    for sentence in _SENTENCE.findall(text or ""):
        if sentence.strip().endswith("?"):
            continue
        for clause in re.split(r"[,;:—–]|\bmais\b|\bpuis\b|\bcar\b|\bparce que\b|\bsi\b", sentence):
            pieces = re.split(r"\bet\b", engine._folded(clause))
            heading = False
            for piece in (p.strip() for p in pieces):
                match = _LEARNER_CLAIM.match(piece) if not heading else (
                    _LEARNER_CLAIM.match(piece) or _CHAINED_CLAIM.match(piece)
                )
                if match:
                    heading = True
                    found.append(f"{match.group('verb')}{match.group('object')}".strip())
                else:
                    heading = heading and piece.startswith("tu ")
    return found


def invented_choice(ending_texts: list[str], payload: dict) -> str | None:
    """The first claim of an ending that the learner's words do not support, or None.

    A claim («tu proposes un rendez-vous demain après-midi») is supported when at
    least half of what it says the learner proposed, promised or chose is in the
    learner's own words, or when the learner took it up («oui», «d'accord») after a
    character had said it. A claim with no content («tu acceptes») needs the learner
    to have accepted something. A character's own proposal stays the character's.
    """

    scene = payload.get("scene") or {}
    history = [h for h in payload.get("history") or [] if isinstance(h, dict)]
    learner = [str(h.get("learner") or "") for h in history] + [str(payload.get("learner_text") or "")]
    said = set().union(*(_stems(text) for text in learner))
    # A character line offered before each learner turn: the scene's question, then
    # each earlier reply. The reply to the last turn comes after it: never accepted.
    before = [str(scene.get("opening_line_fr") or "")]
    accepted: set[str] = set()
    accepted_any = False
    for index, text in enumerate(learner):
        if _ACCEPTS.search(f" {engine._folded(text)} "):
            accepted_any = True
            accepted |= set().union(*(_stems(line) for line in before))
        if index < len(history):
            before.append(str(history[index].get("character") or ""))
    for text in ending_texts:
        for claim in _claims(text):
            stems = _stems(claim.split(" ", 1)[1] if " " in claim else "")
            if not stems:
                if not accepted_any and not (_stems(claim) & said):
                    return claim
                continue
            if len(stems & (said | accepted)) / len(stems) < _SUPPORT_SHARE:
                return claim
    return None


def check_invented_choice(ending_texts: list[str], payload: dict) -> None:
    claim = invented_choice(ending_texts, payload)
    if claim is None:
        return
    raise engine.StoryUnavailable(
        "invented_learner_choice",
        hint=(
            f"The ending says the learner «{claim[:140]}», but the learner never said or "
            "accepted that. Credit the learner only with what their own words say "
            f"(learner_text and history.learner); a plan or a proposal a character made "
            "stays the character's («Marin propose…»), and an open choice stays open."
        ),
    )


# ---------------------------------------------------------------------------
# WP-155 §3 — a generated day's reply and ending keep the season's reveals
# ---------------------------------------------------------------------------


def check_season_spoiler(texts: list[str], payload: dict) -> None:
    """On a generated day of a season (``story.season_turn``), the reply and the ending
    may not make a reveal the day's gap forbids (T5's Berlin before T5). Same rows,
    same hint as the page guard (``season_spoiler``)."""

    turn = (payload.get("story") or {}).get("season_turn") or {}
    rows = turn.get("must_not") or []
    if not rows or not turn.get("season"):
        return
    from app.services.season.director import pattern_hits, rows_by_id
    from app.services.season.format import load_season

    season = load_season(str(turn["season"]))
    forbidden = rows_by_id(season, str(turn.get("gap") or ""), [str(row.get("id")) for row in rows])
    hits = pattern_hits(forbidden, texts)
    if hits:
        text = {row.id: row.text for row in forbidden}
        raise engine.StoryUnavailable(
            "season_spoiler",
            hint="; ".join(f"«{word}» breaks a rule of the season ({text.get(key, key)})" for key, word in hits)
            + ". Say it without it: hint at most, never reveal.",
        )


# ---------------------------------------------------------------------------
# The ending is the character's own line, and the summary tells the story
# ---------------------------------------------------------------------------

#: The reader prints a generated ending in the character's speech bubble, under their
#: name and face: «Romy sourit à ton « avis », puis regarde Margaux. « Oui… » » read as
#: Romy narrating herself (Vincent, 2026-10-16).
_QUOTED = re.compile(r"[«“\"]([^»”\"]*)[»”\"]")
#: The summary is what happened in the story, never a grade: «Tu n'as pas demandé ce que
#: la lettre annonce» told the learner what they failed to ask.
_GRADER_SUMMARY = re.compile(
    r"\b(?:tu\s+n['’]as\s+pas|tu\s+n['’]as\s+jamais|you\s+did(?:\s+not|n['’]t)|you\s+never"
    r"|du\s+hast\s+(?:nicht|nie|kein\w*))\b[^.!?]{0,60}?"
    r"\b(?:demand\w*|pos\w*\s+(?:la|de)\s+question|ask\w*|gefragt|erfragt)",
    re.IGNORECASE,
)


def ending_voice_issue(resolution_fr: str, summary_native: str, character_name: str | None) -> str | None:
    """Why the ending cannot go in the character's bubble, or ``None``."""

    line = str(resolution_fr or "").strip()
    first = str(character_name or "").split()[0] if str(character_name or "").strip() else ""
    if line and first:
        outside = _QUOTED.sub(" ", line)
        starts_with_name = re.match(rf"{re.escape(first)}\b", line, re.IGNORECASE) is not None
        narrates = _QUOTED.search(line) is not None and re.search(
            rf"\b{re.escape(first)}\b", outside, re.IGNORECASE
        )
        if starts_with_name or narrates:
            return (
                f"resolution_fr is printed in {first}'s speech bubble, so it is {first}'s own "
                f"spoken line in the first person: no narration about {first}, no "
                "«il/elle sourit», no quotation marks around what they say."
            )
    if _GRADER_SUMMARY.search(str(summary_native or "")):
        return (
            "summary_native tells what happened in the story and what the character wants "
            "or will do next, in one or two plain sentences. It never says what the learner "
            "did or did not ask: it is not feedback."
        )
    return None


def check_ending_voice(resolution_fr: str, summary_native: str, character_name: str | None) -> None:
    issue = ending_voice_issue(resolution_fr, summary_native, character_name)
    if issue:
        raise engine.StoryUnavailable("ending_voice", hint=issue)


# ---------------------------------------------------------------------------
# #253 — whose relative it is (root cause #145: the thread's established facts)
# ---------------------------------------------------------------------------

#: The relatives a thread settles the owner of. «Ta grand-mère» said by the character
#: and «ma grand-mère» said by the learner both put the grandmother with the learner;
#: the character then does not say «ma grand-mère» of her own (Courrier 20 Oct:
#: «La boulangerie de ta grand-mère est là aussi.» → «…de ma grand-mère est juste au coin»).
_KIN = (
    r"grand-m[èe]re|grand-p[èe]re|grands-parents|grand-maman|grand-papa|mamie|papi|m[ée]m[ée]|p[ée]p[ée]"
    r"|m[èe]re|p[èe]re|parents|fr[èe]re|s[œo]eur|tante|oncle|cousine|cousin|mari|[ée]pouse|femme|fils|fille"
)
_MINE = r"ma|mon|mes"
_YOURS = r"ta|ton|tes|votre|vos"
_KIN_PHRASE = re.compile(rf"(?<![\w-])({_MINE}|{_YOURS})\s+({_KIN})(?![\w-])", re.IGNORECASE)
_SHARED = re.compile(r"\b(?:aussi|également|egalement|non plus|même chose)\b", re.IGNORECASE)
_TU_MARKER = re.compile(r"\b(?:tu|toi|ton|ta|tes|t')", re.IGNORECASE)
_VOUS_MARKER = re.compile(r"\b(?:vous|votre|vos)\b", re.IGNORECASE)
_TO_TU = {"ma": "ta", "mon": "ton", "mes": "tes"}
_TO_VOUS = {"ma": "votre", "mon": "votre", "mes": "vos"}


def _kin_key(noun: str) -> str:
    return engine._folded(noun).replace("œ", "oe")


def _kin_phrases(texts: list[str]) -> list[tuple[str, str]]:
    return [
        (match.group(1).casefold(), _kin_key(match.group(2)))
        for text in texts
        for match in _KIN_PHRASE.finditer(text or "")
    ]


def _anchors(sentence: str) -> set[str]:
    """What a sentence says about a relative, the relative left out: its content
    words by their first five letters («boulangerie» → «boula»)."""

    return {token[:5] for token in _content(_tokens(_KIN_PHRASE.sub(" ", sentence))) if len(token) >= 4}


def _learner_owned_kin(learner_texts: list[str], speaker_texts: list[str]) -> dict[str, set[str]]:
    """The relatives the thread has put with the learner and not with the speaker,
    each with the anchors of the sentences that put them there."""

    owned: dict[str, set[str]] = {}
    for texts, learners in ((learner_texts, True), (speaker_texts, False)):
        for sentence in (sentence for text in texts for sentence in _SENTENCE.findall(text or "")):
            for match in _KIN_PHRASE.finditer(sentence):
                # The learner's «ma grand-mère», or the speaker's «ta grand-mère».
                if (match.group(1).casefold() in _TO_TU) == learners:
                    owned.setdefault(_kin_key(match.group(2)), set()).update(_anchors(sentence))
    speaker_own = {kin for poss, kin in _kin_phrases(speaker_texts) if poss in _TO_TU}
    return {kin: anchors for kin, anchors in owned.items() if kin not in speaker_own}


def _is_flip(match: re.Match[str], anchors: set[str], owned: dict[str, set[str]]) -> bool:
    kin = _kin_key(match.group(2))
    return match.group(1).casefold() in _TO_TU and kin in owned and bool(anchors & owned[kin])


def kin_owner_flips(reply: str, *, learner_texts: list[str], speaker_texts: list[str]) -> list[str]:
    """The «ma / mon / mes + relative» phrases ``reply`` says of the speaker's own that
    the thread has already put with the learner. A phrase in a sentence that shares it
    («Ma grand-mère aussi…») or in a reply that also names the learner's («Ta
    grand-mère… Ma grand-mère…», a contrast) is not a flip.

    Only a sentence that says again something the thread said of the learner's
    relative is one: «La boulangerie de ma grand-mère…» after «La boulangerie de ta
    grand-mère…». The speaker may have a brother too: «Mon frère est pâtissier.» after
    the learner's «Mon frère habite à Paris.» shares nothing and stays as written."""

    owned = _learner_owned_kin(learner_texts, speaker_texts)
    if not owned or not reply:
        return []
    phrases = list(_KIN_PHRASE.finditer(reply))
    if any(m.group(1).casefold() not in _TO_TU and _kin_key(m.group(2)) in owned for m in phrases):
        return []
    hits = []
    for sentence in _SENTENCE.findall(reply):
        if _SHARED.search(sentence):
            continue
        anchors = _anchors(sentence)
        hits.extend(match.group(0) for match in _KIN_PHRASE.finditer(sentence) if _is_flip(match, anchors, owned))
    return hits


def settle_kin_owner(
    reply: str, *, learner_texts: list[str], speaker_texts: list[str], register: str | None = None
) -> str:
    """``reply`` with every flipped possessive handed back to the learner («ma» → «ta»,
    or «votre» when the thread says vous). Unchanged when nothing flipped.

    ``register`` is how the speaker addresses the learner («tu / …» or «vous / …», as a
    mission's ``target_register`` holds it). It outranks a guess from the earlier lines,
    which may hold no «vous» yet: a polite correspondent's first reply would otherwise
    hand back «ta grand-mère»."""

    if not kin_owner_flips(reply, learner_texts=learner_texts, speaker_texts=speaker_texts):
        return reply
    owned = _learner_owned_kin(learner_texts, speaker_texts)
    declared = (register or "").strip().casefold()
    if declared.startswith(("tu", "vous")):
        mapping = _TO_VOUS if declared.startswith("vous") else _TO_TU
    else:
        said = " ".join(speaker_texts)
        mapping = _TO_VOUS if _VOUS_MARKER.search(said) and not _TU_MARKER.search(said) else _TO_TU

    def settle(sentence: str) -> str:
        if _SHARED.search(sentence):
            return sentence
        anchors = _anchors(sentence)

        def one(match: re.Match[str]) -> str:
            if not _is_flip(match, anchors, owned):
                return match.group(0)
            poss = match.group(1)
            new = mapping[poss.casefold()]
            new = new.capitalize() if poss[:1].isupper() else new
            return new + match.group(0)[len(poss):]

        return _KIN_PHRASE.sub(one, sentence)

    return "".join(settle(sentence) for sentence in _SENTENCE.findall(reply)) or reply


def kin_owner_hint(hits: list[str]) -> str:
    return (
        f"The reply says «{hits[0]}» of the speaker's own, but the thread has already put that "
        "person with the learner (they said «ma …», or the character said «ta …»). Speak of "
        "the learner's relative as «ta … / ton …» and never claim them."
    )


# ---------------------------------------------------------------------------
# #254 — a reasoned reply is picked up
# ---------------------------------------------------------------------------

#: A learner turn that GIVES A REASON («…parce que la restaurant était très difficile»)
#: with at least this many content words is a reasoned reply: the character's line has
#: to take at least one of them up. Only reasons: «Oui, je viens samedi» is rightly
#: answered by «Merci ! On prépare la salle», sharing no word, and a retry on every
#: such reaction would double the voice lane's cost for nothing.
REASONED_REPLY_CONTENT_WORDS = 2
_STEM = 5
_REASON = re.compile(
    r"\b(?:parce qu|parce que|puisque|puisqu|car|[àa] cause|gr[âa]ce [àa])\b", re.IGNORECASE
)
#: Compared without accents: «était» and «très» are filler as much as «etait».
_FILLER = frozenset(
    "parce beaucoup etait etais sera serait tres peut etre vraiment pense crois sais comprends "
    "pourquoi faire avoir cela cette alors aussi encore toujours jamais souvent quelque quelques "
    "puisque cause grace".split()
)


def _bare(token: str) -> str:
    return unicodedata.normalize("NFKD", token).encode("ascii", "ignore").decode()


def _reason_stems(text: str) -> set[str]:
    return {
        token[:_STEM]
        for token in _content(_tokens(text))
        if len(token) >= 4 and _bare(token) not in _FILLER
    }


#: «car» after one of these is the noun, the coach: «le car était en retard».
_CAR_NOUN_BEFORE = frozenset(
    "le un du au ce mon ton son notre votre leur des les aux ces mes tes ses nos vos leurs "
    "quel en par dans".split()
)
_WORD = re.compile(r"\w+")


def _reason_start(sentence: str) -> int | None:
    """Where a sentence's reason starts, or None when it gives none."""

    for match in _REASON.finditer(sentence):
        before = _WORD.findall(sentence[: match.start()])[-1:]
        if match.group(0).casefold() == "car" and before and before[0].casefold() in _CAR_NOUN_BEFORE:
            continue
        return match.start()
    return None


def _reasons(text: str) -> str:
    """The reasons a turn gives: each sentence from its «parce que», «car», … on."""

    return " ".join(
        sentence[start:]
        for sentence in _SENTENCE.findall(text or "")
        if (start := _reason_start(sentence)) is not None
    )


def ignored_reply_hint(reply: str, learner_text: str) -> str | None:
    """A hint when ``reply`` takes up none of a reason the learner just gave, else None.

    Live walk 20 Oct (#254): «Odile est parti parce que la restaurant était très
    difficile» was answered «Fatiguée. Ici : « courageuse ».» — nothing in it refers to
    the difficulty, the restaurant or the guess. Shared stems are the test (the first
    five letters of a content word, so «restaurant» meets «restaurants»), taken from
    the reason itself: «Elle était fatiguée» shares «était» with the turn and «Odile ?
    Elle aimait les chats.» shares «Odile», and neither takes up why. A turn without a
    stated reason has nothing the reply must take up and passes."""

    reasons = _reasons(learner_text)
    if not reasons:
        return None
    learner = _reason_stems(reasons)
    if len(learner) < REASONED_REPLY_CONTENT_WORDS or not (reply or "").strip():
        return None
    if learner & _reason_stems(reply):
        return None
    words = ", ".join(sorted({t for t in _content(_tokens(reasons)) if t[:_STEM] in learner})[:6])
    return (
        "The reply does not pick up the reason the learner just gave. Answer it: take up one "
        f"thing from it (for instance: {words}) before you move on."
    )


# ---------------------------------------------------------------------------
# #315 — a person nobody introduced
# ---------------------------------------------------------------------------

#: Titles that make the next capitalised word a person («M. Delmas», «Mme Diallo»).
_TITLES = r"(?:M\.|Mme|Mlle|Monsieur|Madame|Mademoiselle|Maître|Docteur|Dr)"
_TITLED_PERSON = re.compile(rf"(?<![\w'’])({_TITLES})\s+([A-ZÀ-ÖØ-Þ][\w\-]+)")
#: A capitalised word of three letters or more; elisions («d'Odile») are opened first.
_CAPITALISED = re.compile(r"(?<![\w\-])([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]{2,}(?:-[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+)?)")
_ELISION = re.compile(r"\b[dDlLjJ]['’](?=[A-ZÀ-ÖØ-Þ])")
#: After such a character a capital opens a sentence, not a name.
_SENTENCE_OPENERS = ".!?…:«\"“”—–\n"
#: A capitalised word right after one of these is a place or a thing («au Mistral», «le
#: Café du Canal»), not a person: a person takes no article and no place preposition.
_PLACE_CUES = frozenset("le la les au aux en dans vers sur devant derrière".split())
#: Capitalised words that are not a person the scene has to introduce.
_COMMON_PROPER = frozenset(
    "dieu noël paris france berlin bretagne seine europe français française anglais allemand "
    "merci bonjour bonsoir salut madame monsieur mademoiselle maître mme mlle docteur".split()
)
_NAME_WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def _name_key(word: str) -> str:
    return engine._folded(word).replace(" ", "")


def established_words(texts: list[str]) -> frozenset[str]:
    """Every word of three letters or more the scene has already put in front of the
    learner (folded): names, places, things. A name in this set is established."""

    return frozenset(_name_key(word) for text in texts for word in _NAME_WORD.findall(str(text or "")))


def unintroduced_people(text: str, established: frozenset[str]) -> tuple[list[str], list[str]]:
    """``(titled, bare)``: the people ``text`` names that nothing established.

    ``titled`` are «M. Delmas»-style names (a title and a capitalised surname the scene
    never held: certain). ``bare`` are capitalised words in the middle of a sentence that
    the scene never held and that are no common proper noun (likely a first name: a
    softer signal, a place is the usual false positive)."""

    titled: list[str] = []
    for title, surname in _TITLED_PERSON.findall(text or ""):
        if _name_key(surname) not in established:
            titled.append(f"{title} {surname}")
    opened = _ELISION.sub(" ", text or "")
    bare: list[str] = []
    for found in _CAPITALISED.finditer(opened):
        word = found.group(1)
        before = opened[: found.start()].rstrip("   ")
        if not before or before[-1] in _SENTENCE_OPENERS:
            continue
        previous = re.findall(r"[^\W\d_]+$", before)
        if previous and previous[0].casefold() in _PLACE_CUES:
            continue
        if _name_key(word) in established or word.casefold() in _COMMON_PROPER:
            continue
        if any(word in item.split() for item in titled):
            continue
        bare.append(word)
    return list(dict.fromkeys(titled)), list(dict.fromkeys(bare))


# ---------------------------------------------------------------------------
# #349 — a reply that pastes the thread back
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


def _sentences_of(texts: list[str]) -> list[str]:
    """Folded sentences of ``texts`` (duplicates dropped, order kept)."""

    found: list[str] = []
    for text in texts:
        for part in _SENTENCE_SPLIT.split(str(text or "")):
            folded = engine._folded(part)
            if folded and folded not in found:
                found.append(folded)
    return found


def echoed_thread(reply: str, earlier: list[str]) -> list[str]:
    """The earlier lines of the scene that ``reply`` says again, or ``[]``.

    #349 (root cause #145): handed its past as text, the model pasted it into the new
    line. An echo is one earlier sentence of five words or more repeated whole, or two
    different earlier sentences of three words or more. A short habit («Merci.»,
    «Et Gus ?») and a shared word are no echo. ``earlier`` is what the characters
    said (never the learner's words: ``check_echo`` owns those), labels already removed.
    """

    said = f" {engine._folded(reply)} "
    repeated = [
        sentence
        for sentence in _sentences_of(earlier)
        if len(sentence.split()) >= 3 and f" {sentence} " in said
    ]
    if any(len(sentence.split()) >= 5 for sentence in repeated) or len(repeated) >= 2:
        return repeated
    return []
