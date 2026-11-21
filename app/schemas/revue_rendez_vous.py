"""Wire schemas for «Papier · les rendez-vous» (owner 2026-11-21): reasons to come back tomorrow.

Four read models and one request, each behind its own switch in ``app/config.py``:

* :class:`RvSouvenir` (``REVUE_MEMORY_ENABLED``): ONE authored line a regular says to the
  learner about what the learner did in an earlier Papier — slots filled only from stored facts;
* :class:`RvTroisMots` (``REVUE_TROIS_MOTS_ENABLED``): «Trois mots», the closing round on three
  words of the story (match each to its cue, then one gap sentence from the story's own text);
* :class:`RvUneSemaine` (``REVUE_UNE_ENABLED``): «La une de la semaine», a front page composed
  only from what the learner filed that week, text as printed;
* :class:`RvCarteDePresse` (``REVUE_UNE_ENABLED``): the learner's press card on the Relevé.

They live on their own routes (``app/api/v1/endpoints/revue_rendez_vous.py``), so with every
switch off no existing payload gains a field. As in ``app/schemas/revue.py``: real models,
and no field for anything private (the round's solution is ``None`` until it may be shown).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.revue import RevueModel, RevueRequest, RvPicture, RvWeek

#: The rubriques a Papier can be filed under (the artifact's ``kind``); «La photo» and «Le micro»
#: are being built on another branch and count once they file.
Rubrique = Literal["opinion", "fil", "titre", "intox", "photo", "micro"]
RUBRIQUES: tuple[str, ...] = ("opinion", "fil", "titre", "intox", "photo", "micro")


# ---------------------------------------------------------------------------
# «Les habitués se souviennent»
# ---------------------------------------------------------------------------


class RvSouvenir(RevueModel):
    """One line in the mouth of a regular: French at the learner's band, with its translations."""

    template_id: str
    speaker_id: str
    speaker_fr: str
    fr: str
    en: str
    de: str
    #: The stored fact the line rests on (``session_id`` of the earlier Papier and what it holds),
    #: so the claim can be audited: the app never says something the learner did not do.
    about_session_id: str
    fact: Literal["stance", "headline", "intox_score", "fil", "count", "opinion", "photo", "micro"]


class RvSouvenirResult(RevueModel):
    #: ``None``: no memory to speak of (a first Papier, or nothing a line can rest on).
    line: RvSouvenir | None = None


# ---------------------------------------------------------------------------
# «Trois mots»
# ---------------------------------------------------------------------------


TroisMotsStep = Literal["match", "gap", "done"]


class RvTmWord(RevueModel):
    key: Literal["a", "b", "c"]
    #: The word as the story's vocabulary carries it (with its article: «la fête»).
    fr: str
    #: Without its article («fête»): the gap's options.
    bare_fr: str
    #: The word's gloss in the learner's mother tongue: shown only once the match is resolved.
    gloss: str | None = None


class RvTmCue(RevueModel):
    key: Literal["1", "2", "3"]
    kind: Literal["picture", "gloss"]
    #: ``gloss``: the meaning in the mother tongue; ``picture``: ``None`` (the picture is the cue).
    text: str | None = None
    picture: RvPicture | None = None


class RvTmMiss(RevueModel):
    word_key: Literal["a", "b", "c"]
    cue_key: Literal["1", "2", "3"]


class RvTmMatch(RevueModel):
    tries: int = 0
    resolved: bool = False
    correct: bool | None = None
    #: The pairs of the last wrong try (never which cue was right).
    misses: list[RvTmMiss] = Field(default_factory=list)
    #: word key → cue key, only once resolved.
    solution: dict[str, str] | None = None


class RvTmGapMiss(RevueModel):
    word_key: Literal["a", "b", "c"]
    #: What the picked word means (mother tongue): why it does not fit.
    gloss: str


class RvTmGap(RevueModel):
    """One sentence of the story's own text (its lead or its summary) with the word taken out."""

    source: Literal["lead", "summary"]
    before_fr: str
    after_fr: str
    tries: int = 0
    resolved: bool = False
    correct: bool | None = None
    miss: RvTmGapMiss | None = None
    #: The word key, only once resolved.
    solution: str | None = None
    #: The sentence whole, only once resolved.
    sentence_fr: str | None = None


class RvTroisMots(RevueModel):
    session_id: str
    step: TroisMotsStep
    words: list[RvTmWord]
    cues: list[RvTmCue]
    match: RvTmMatch
    #: ``None`` when no sentence of the story's own text holds one of the three words.
    gap: RvTmGap | None = None
    #: How many of the three words this round added to the learner's words (the others were
    #: already kept at the close: never kept twice).
    kept_now: int = 0


class RvTroisMotsResult(RevueModel):
    #: ``None``: the session has no round (not closed, or too few words).
    round: RvTroisMots | None = None
    error: Literal["pair_all", "unknown_key", "out_of_order"] | None = None


class RvTroisMotsRequest(RevueRequest):
    act: Literal["match", "gap"]
    #: match: word key → cue key, all three.
    pairs: dict[Literal["a", "b", "c"], Literal["1", "2", "3"]] | None = None
    #: gap: the word key picked.
    word: Literal["a", "b", "c"] | None = None


# ---------------------------------------------------------------------------
# «La une de la semaine» and «La carte de presse»
# ---------------------------------------------------------------------------


UneRole = Literal["headline", "caption", "quote", "vox", "brief", "rectificatif"]


class RvUneItem(RevueModel):
    session_id: str
    rubrique: Rubrique
    #: How the page prints it: the learner's headline over the story («headline»), their caption
    #: under its picture, their interview as a pull quote, their opinion as the vox-pop line, their
    #: retelling as a brief, their intox score and right corrections as «rectificatif».
    role: UneRole
    #: The story's own title (the dossier's), always.
    story_title_fr: str
    #: The learner's text AS PRINTED (corrected or checked); never their raw draft.
    text_fr: str
    #: «L'intox express»: the score and the corrections printed as theirs.
    score: int | None = None
    total: int | None = None
    corrections_fr: list[str] = Field(default_factory=list)
    #: «Au comptoir»: the side taken.
    stance: Literal["pour", "contre", "nuance"] | None = None
    picture: RvPicture | None = None
    filed_on: str
    filed_weekday_fr: str


class RvUneSemaine(RevueModel):
    week: RvWeek
    #: «Semaine 47 · du 16 au 22 novembre».
    dateline_fr: str
    items: list[RvUneItem]
    lexique: list[str]
    #: Distinct rubriques filed this week, of :data:`RUBRIQUES`.
    rubriques_filed: int
    rubriques_total: int = len(RUBRIQUES)
    pieces: int
    #: Today is the last day of this (current) week and it holds two Papiers or more: Home's chip.
    due_today: bool = False


class RvCarteRubrique(RevueModel):
    rubrique: Rubrique
    pieces: int
    first_on: str | None = None


class RvCarteDePresse(RevueModel):
    rubriques: list[RvCarteRubrique]
    pieces: int
    #: The day of the learner's first filed Papier (ISO date), ``None`` before it.
    since: str | None = None


__all__ = [name for name in dir() if name.startswith("Rv")] + ["RUBRIQUES", "Rubrique"]
