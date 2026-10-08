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
