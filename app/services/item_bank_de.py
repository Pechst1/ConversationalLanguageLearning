"""FORGE-DE (2026-10-03) — La Forge's item bank, rendered in German.

Most of the learner base reads German. The bank's frames carry an English gloss
(``en``); this module gives them a German one (``de``) built by rule, so a German
learner sees what a sentence means («Ich wohne seit drei Jahren in Lyon.») where
the form is chosen by meaning (numbers, times, depuis / il y a, parce que / mais).

The German side of the lexicon lives in ``grammar_templates/lexicon_de.json`` and
is merged into the lexicon entries at load time (``deu`` and ``deu_*`` keys; the
key ``de`` is French already: «de Paris»). Frames gain a ``de`` template written
with the ``g_*`` filters below:

``{S|g_cl:V:O:t=perfekt:o=inv:adv=T:neg=nicht}``
    a whole clause: subject, finite verb, middle field (reflexive pronoun,
    adverb, negation, complement), non-finite verbs, separable prefix — in main
    (V2), inverted (after a fronted element, or a yes/no question), subordinate
    (verb-final), ``nosubj`` (the frame wrote the subject) or ``inf`` order.
``{N|g_np:indef:acc}``, ``{N|g_np:def:dat:p}``, ``{N|g_np:indef:acc:adj=A}``
    a noun phrase with its article (der/ein/kein/dies-/bare) in a case, with an
    adjective declined weak, mixed or strong.
``{P|g_at}`` / ``{P|g_to}`` / ``{P|g_from}``
    where something is, where one goes, where one comes from («im Café»,
    «ins Café», «aus dem Café») — authored per place, else built from «in».

Everything is deterministic. A frame whose German cannot be rendered reliably
has its German written out, or none: an item without ``de`` simply carries no
German meaning (never a wrong one). :func:`german_violations` is the checker the
quality gate runs over every rendering (article/gender agreement with the
lexicon, verb-second and verb-final order, the Perfekt auxiliary, English left in).
"""
from __future__ import annotations

import re
from typing import Any


class RenderError(ValueError):
    """A frame cannot be rendered with these bindings; the sampler skips it."""


# --------------------------------------------------------------------------- #
# Persons and pronouns
# --------------------------------------------------------------------------- #

#: German person index (0 ich, 1 du, 2 er/sie/es, 3 wir, 4 ihr, 5 sie).
_NOM = {0: "ich", 1: "du", 3: "wir", 4: "ihr", 5: "sie"}
_ACC = {0: "mich", 1: "dich", 3: "uns", 4: "euch", 5: "sie"}
_DAT = {0: "mir", 1: "dir", 3: "uns", 4: "euch", 5: "ihnen"}
_THIRD = {"m": ("er", "ihn", "ihm"), "f": ("sie", "sie", "ihr"), "n": ("es", "es", "ihm")}
_REFL_ACC = ("mich", "dich", "sich", "uns", "euch", "sich")
_REFL_DAT = ("mir", "dir", "sich", "uns", "euch", "sich")
_POSS_STEM = {0: "mein", 1: "dein", 3: "unser", 4: "euer", 5: "ihr"}


def g_person(entry: dict[str, Any]) -> int:
    """The German person of a subject entry (French «on» is «wir», «vous» is «ihr»)."""

    if "deu_p" in entry:
        return int(entry["deu_p"])
    en_p = entry.get("en_p")
    if not en_p:
        if "p" not in entry:
            raise RenderError(f"slot {entry.get('id')} is not a subject")
        en_p = {0: "1s", 1: "2", 2: "3s", 3: "1p", 4: "2", 5: "3p"}[int(entry["p"])]
    if en_p == "2":
        return 4 if int(entry.get("p", 1)) == 4 else 1
    return {"1s": 0, "3s": 2, "1p": 3, "3p": 5}[en_p]


def _gender(entry: dict[str, Any]) -> str:
    return "f" if entry.get("g") == "f" else "m"


def _is_pronoun(entry: dict[str, Any]) -> bool:
    return "pron" in (entry.get("tags") or []) or str(entry.get("fr", "")).lower() in {
        "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    }


def g_subject(entry: dict[str, Any]) -> str:
    """The subject in the nominative: a pronoun by person and gender, else the name."""

    if entry.get("deu") and not _is_pronoun(entry):
        return str(entry["deu"])
    if _is_pronoun(entry) or entry.get("kind") == "person" and "p" in entry and not entry.get("members"):
        person = g_person(entry)
        if person == 2:
            return _THIRD[_gender(entry)][0]
        return _NOM[person]
    if entry.get("deu"):
        return str(entry["deu"])
    if entry.get("members") or entry.get("bible"):
        return str(entry.get("fr"))
    raise RenderError(f"no German subject for {entry.get('id')}")


def g_pronoun(entry: dict[str, Any], case: str = "acc") -> str:
    """The personal pronoun standing for ``entry`` in a case (mich, ihr, ihnen)."""

    if "p" in entry or entry.get("en_p") or entry.get("deu_p") is not None:
        person = g_person(entry)
        gender = _gender(entry)
    else:
        person = 5 if entry.get("n") == "p" else 2
        gender = entry.get("dg") or "m"
    if person == 2:
        index = {"nom": 0, "acc": 1, "dat": 2}[case]
        return _THIRD[gender][index]
    return {"nom": _NOM, "acc": _ACC, "dat": _DAT}[case][person]


# --------------------------------------------------------------------------- #
# Verbs
# --------------------------------------------------------------------------- #

_INSEPARABLE = ("be", "ver", "er", "ent", "emp", "zer", "ge", "miss", "über", "hinter", "wider")
#: German forms of the auxiliaries and modals the clause builder needs.
AUX: dict[str, dict[str, Any]] = {
    "sein": {"inf": "sein", "pres": ["bin", "bist", "ist", "sind", "seid", "sind"], "prt": "war", "pp": "gewesen", "aux": "sein", "konj": "wäre"},
    "haben": {"inf": "haben", "pres": ["habe", "hast", "hat", "haben", "habt", "haben"], "prt": "hatte", "pp": "gehabt", "konj": "hätte"},
    "werden": {"inf": "werden", "pres": ["werde", "wirst", "wird", "werden", "werdet", "werden"], "prt": "wurde", "pp": "geworden", "aux": "sein", "konj": "würde"},
    "können": {"inf": "können", "pres": ["kann", "kannst", "kann", "können", "könnt", "können"], "prt": "konnte", "pp": "gekonnt", "konj": "könnte"},
    "wollen": {"inf": "wollen", "pres": ["will", "willst", "will", "wollen", "wollt", "wollen"], "prt": "wollte", "pp": "gewollt", "konj": "wollte"},
    "müssen": {"inf": "müssen", "pres": ["muss", "musst", "muss", "müssen", "müsst", "müssen"], "prt": "musste", "pp": "gemusst", "konj": "müsste"},
    "sollen": {"inf": "sollen", "pres": ["soll", "sollst", "soll", "sollen", "sollt", "sollen"], "prt": "sollte", "pp": "gesollt", "konj": "sollte"},
    "dürfen": {"inf": "dürfen", "pres": ["darf", "darfst", "darf", "dürfen", "dürft", "dürfen"], "prt": "durfte", "pp": "gedurft", "konj": "dürfte"},
    "mögen": {"inf": "mögen", "pres": ["mag", "magst", "mag", "mögen", "mögt", "mögen"], "prt": "mochte", "pp": "gemocht", "konj": "möchte"},
}
#: German verbs a frame may name directly (``{S|g_v:fahren}``).
EXTRA: dict[str, dict[str, Any]] = {
    "fahren": {"inf": "fahren", "pres2": "fährst", "pres3": "fährt", "prt": "fuhr", "pp": "gefahren", "aux": "sein"},
    "gehen": {"inf": "gehen", "prt": "ging", "pp": "gegangen", "aux": "sein"},
    "kommen": {"inf": "kommen", "prt": "kam", "pp": "gekommen", "aux": "sein"},
    "kosten": {"inf": "kosten"},
    "regnen": {"inf": "regnen"},
    "schneien": {"inf": "schneien"},
}
#: Modal "tenses": a modal (present or Konjunktiv II) + the infinitive.
_MODAL_TENSES = {
    "can": ("können", "pres"), "want": ("wollen", "pres"), "must": ("müssen", "pres"),
    "may": ("dürfen", "pres"), "could": ("können", "konj"), "should": ("sollen", "konj"),
    "would_like": ("mögen", "konj"), "would": ("werden", "konj"),
}


def _sep(gv: dict[str, Any]) -> str:
    return str(gv.get("sep") or "")


def _base_inf(gv: dict[str, Any]) -> str:
    inf = str(gv["inf"])
    prefix = _sep(gv)
    return inf[len(prefix):] if prefix and inf.startswith(prefix) else inf


def _stem(base: str) -> str:
    if base.endswith(("eln", "ern")):
        return base[:-1]
    return base[:-2] if base.endswith("en") else base[:-1]


def _needs_e(stem: str) -> bool:
    return stem.endswith(("t", "d")) or re.search(r"[^aeiouäöülrhmn][mn]$", stem) is not None


def present(gv: dict[str, Any], person: int) -> str:
    """The present form, without a separable prefix (kaufe for einkaufen)."""

    if gv.get("pres"):
        return str(gv["pres"][person])
    base = _base_inf(gv)
    if person in (3, 5):
        return base
    stem = _stem(base)
    if person == 1 and gv.get("pres2"):
        return str(gv["pres2"])
    if person == 2 and gv.get("pres3"):
        return str(gv["pres3"])
    if person == 0:
        return stem + "e" if not base.endswith(("eln", "ern")) else (stem[:-2] + "le" if base.endswith("eln") else stem + "e")
    e = "e" if _needs_e(stem) else ""
    if person == 1:
        return stem + e + ("t" if stem.endswith(("s", "ß", "z", "x")) and not e else "st")
    return stem + e + "t"  # 2 and 4


def praeteritum(gv: dict[str, Any], person: int) -> str:
    prt = gv.get("prt")
    if not prt:
        stem = _stem(_base_inf(gv))
        prt = stem + ("ete" if _needs_e(stem) else "te")
    prt = str(prt)
    if prt.endswith("e"):
        return [prt, prt + "st", prt, prt + "n", prt + "t", prt + "n"][person]
    two = prt + ("est" if prt.endswith(("s", "ß", "z", "t", "d")) else "st")
    return [prt, two, prt, prt + "en", prt + ("et" if prt.endswith(("t", "d")) else "t"), prt + "en"][person]


def participle(gv: dict[str, Any]) -> str:
    if gv.get("pp"):
        return str(gv["pp"])
    base = _base_inf(gv)
    stem = _stem(base)
    tail = stem + ("et" if _needs_e(stem) else "t")
    if base.endswith("ieren") or base.startswith(_INSEPARABLE):
        return _sep(gv) + tail
    return _sep(gv) + "ge" + tail


def konjunktiv(gv: dict[str, Any], person: int) -> str | None:
    konj = gv.get("konj")
    if not konj:
        return None
    konj = str(konj)
    if konj == "wäre":
        return ["wäre", "wärst", "wäre", "wären", "wärt", "wären"][person]
    return [konj, konj + "st", konj, konj + "n", konj + "t", konj + "n"][person]


def infinitive(gv: dict[str, Any], zu: bool = False) -> str:
    if not zu:
        return str(gv["inf"])
    prefix = _sep(gv)
    return f"{prefix}zu{_base_inf(gv)}" if prefix else f"zu {gv['inf']}"


def aux_of(gv: dict[str, Any]) -> dict[str, Any]:
    return AUX["sein" if gv.get("aux") == "sein" else "haben"]


def imperative(gv: dict[str, Any], who: str = "du") -> str:
    """The imperative form (prefix excluded): «nimm», «geht», «nehmen»."""

    if who == "ihr":
        return present(gv, 4)
    if who == "Sie":
        return "seien" if gv.get("inf") == "sein" else present(gv, 5)
    if gv.get("imp"):
        return str(gv["imp"])
    stem = _stem(_base_inf(gv))
    return stem + ("e" if _needs_e(stem) else "")


# --------------------------------------------------------------------------- #
# Noun phrases
# --------------------------------------------------------------------------- #

_DEF = {
    "gen": {"m": "des", "f": "der", "n": "des", "p": "der"},
    "nom": {"m": "der", "f": "die", "n": "das", "p": "die"},
    "acc": {"m": "den", "f": "die", "n": "das", "p": "die"},
    "dat": {"m": "dem", "f": "der", "n": "dem", "p": "den"},
}
_EIN_END = {
    "nom": {"m": "", "f": "e", "n": "", "p": "e"},
    "acc": {"m": "en", "f": "e", "n": "", "p": "e"},
    "dat": {"m": "em", "f": "er", "n": "em", "p": "en"},
}
_DER_END = {
    "gen": {"m": "es", "f": "er", "n": "es", "p": "er"},
    "nom": {"m": "er", "f": "e", "n": "es", "p": "e"},
    "acc": {"m": "en", "f": "e", "n": "es", "p": "e"},
    "dat": {"m": "em", "f": "er", "n": "em", "p": "en"},
}
_WEAK_ADJ = {
    "gen": {"m": "en", "f": "en", "n": "en", "p": "en"},
    "nom": {"m": "e", "f": "e", "n": "e", "p": "en"},
    "acc": {"m": "en", "f": "e", "n": "e", "p": "en"},
    "dat": {"m": "en", "f": "en", "n": "en", "p": "en"},
}
_MIXED_ADJ = {
    "nom": {"m": "er", "f": "e", "n": "es", "p": "en"},
    "acc": {"m": "en", "f": "e", "n": "es", "p": "en"},
    "dat": {"m": "en", "f": "en", "n": "en", "p": "en"},
}
_STRONG_ADJ = {
    "nom": {"m": "er", "f": "e", "n": "es", "p": "e"},
    "acc": {"m": "en", "f": "e", "n": "es", "p": "e"},
    "dat": {"m": "em", "f": "er", "n": "em", "p": "en"},
}
_EIN_DETS = frozenset({"indef", "kein", "poss"})


def noun_word(noun: dict[str, Any], case: str = "nom", plural: bool = False) -> str:
    """The German noun itself, declined (dative plural -n, weak masculines)."""

    word = noun.get("deu")
    if not word:
        raise RenderError(f"noun {noun.get('id')} has no German")
    if plural or noun.get("n") == "p" and not noun.get("dpl"):
        word = str(noun.get("dpl") or word)
        if case == "dat" and not word.endswith(("n", "s")) and not noun.get("dmass"):
            word += "n"
        return word
    if noun.get("dweak") and case in {"acc", "dat", "gen"}:
        return str(noun["dweak"])
    if case == "gen" and noun.get("dg") in {"m", "n"}:
        head, space, rest = str(word).partition(" ")
        head += "es" if head.endswith(("s", "ß", "x", "z")) else "s"
        return head + space + rest
    return str(word)


def _gkey(noun: dict[str, Any], plural: bool) -> str:
    if plural:
        return "p"
    gender = noun.get("dg")
    if gender not in {"m", "f", "n", "p"}:
        raise RenderError(f"noun {noun.get('id')} has no German gender")
    return gender


def adj_attr(adj: dict[str, Any], ending: str) -> str:
    stem = str(adj.get("deu_att") or adj.get("deu") or "")
    if not stem:
        raise RenderError(f"adjective {adj.get('id')} has no German")
    if adj.get("deu_inv"):
        return stem
    return stem + ending


def possessive_stem(owner: dict[str, Any]) -> str:
    person = g_person(owner) if ("p" in owner or owner.get("en_p")) else 2
    if person == 2:
        return "ihr" if _gender(owner) == "f" else "sein"
    return _POSS_STEM[person]


def noun_phrase(
    noun: dict[str, Any],
    det: str = "def",
    case: str = "nom",
    plural: bool = False,
    adj: dict[str, Any] | None = None,
    owner: dict[str, Any] | None = None,
) -> str:
    """«den großen Tisch», «einer Tasse», «keine Äpfel», «meinen Schlüssel»."""

    if noun.get("dproper"):
        name = str(noun["deu"])
        return f"{adj_attr(adj, _STRONG_ADJ[case]['n'])} {name}" if adj else name
    plural = plural or (noun.get("n") == "p")
    key = _gkey(noun, plural)
    word = noun_word(noun, case, plural)
    if det == "def":
        article = _DEF[case][key]
        table = _WEAK_ADJ
    elif det in {"dem", "welch"}:
        article = ("dies" if det == "dem" else "welch") + _DER_END[case][key]
        table = _WEAK_ADJ
    elif det in {"indef", "kein", "poss"}:
        if det == "indef" and plural:
            article, table = "", _STRONG_ADJ
        else:
            stem = {"indef": "ein", "kein": "kein"}.get(det) or possessive_stem(owner or {})
            ending = _EIN_END[case][key]
            if stem == "euer" and ending:
                stem = "eur"
            article, table = stem + ending, _MIXED_ADJ
    elif det == "none":
        article, table = "", _STRONG_ADJ
    else:
        raise RenderError(f"unknown German determiner {det}")
    parts = [article] if article else []
    if adj is not None:
        parts.append(adj_attr(adj, table[case][key]))
    parts.append(word)
    return " ".join(parts)


#: Contractions of a preposition with the definite article.
_CONTRACT = {("in", "dem"): "im", ("in", "das"): "ins", ("an", "dem"): "am", ("an", "das"): "ans",
             ("zu", "dem"): "zum", ("zu", "der"): "zur", ("von", "dem"): "vom", ("bei", "dem"): "beim"}


def prep_phrase(prep: str, noun: dict[str, Any], case: str, plural: bool = False) -> str:
    phrase = noun_phrase(noun, "def", case, plural)
    article, _, rest = phrase.partition(" ")
    short = _CONTRACT.get((prep, article))
    if short and rest and not noun.get("dproper"):
        return f"{short} {rest}"
    return f"{prep} {phrase}"


# --------------------------------------------------------------------------- #
# Negation
# --------------------------------------------------------------------------- #

_PREPOSITIONS = frozenset(
    "zu zum zur in im ins am an ans auf aus bei beim mit nach von vom für um über unter vor hinter neben "
    "zwischen durch gegen ohne bis seit gegenüber entlang wegen".split()
)
_DEFINITE = re.compile(
    r"^(?:der|die|das|den|dem|des|mein\w*|dein\w*|sein\w*|ihr\w*|unser\w*|eur\w*|dies\w*|jede\w*|alle\w*)\b"
)


def _kein(comp: str) -> str | None:
    match = re.match(r"^ein(e[mnrs]?)?\b", comp)
    if not match:
        return None
    return "k" + comp


def negate_comp(comp_entry: dict[str, Any] | None, comp: str, neg: str) -> tuple[str, str, str]:
    """``(before, comp, after)``: where the negation goes around the complement.

    «nicht» goes before a prepositional phrase, an adverb or an adjective
    («nicht zum Markt», «nicht müde»), after a definite object or a name
    («die Zeitung nicht»); an indefinite object turns into «kein».
    """

    if not neg:
        return "", comp, ""
    if comp_entry and comp_entry.get("deu_neg"):
        authored = comp_entry["deu_neg"]
        if isinstance(authored, dict):
            if neg not in authored:
                raise RenderError(f"no authored «{neg}» for {comp}")
            return "", str(authored[neg]), ""
        return "", str(authored).replace("{neg}", neg), ""
    if not comp:
        return "", "", neg
    if neg in {"nicht", "nicht mehr"}:
        k = _kein(comp)
        if k:
            return "", k + (" mehr" if neg == "nicht mehr" else ""), ""
    first = comp.split()[0]
    if first.lower() in _PREPOSITIONS or neg in {"nie", "noch nie"}:
        return neg, comp, ""
    if _DEFINITE.match(comp) or first[:1].isupper():
        return "", comp, neg
    return neg, comp, ""


# --------------------------------------------------------------------------- #
# The filters (a mixin of item_bank.Filters)
# --------------------------------------------------------------------------- #


def _text(value: Any) -> str:
    if isinstance(value, dict):
        text = value.get("deu")
        if text is None:
            raise RenderError(f"{value.get('id') or value.get('fr')} has no German")
        return str(text)
    return "" if value in (None, "_") else str(value)


class GermanFilters:
    """``g_*`` template filters; ``self._verb`` comes from :class:`item_bank.Filters`."""

    # -- verbs ----------------------------------------------------------------
    def _gv(self, verb: Any, comp: Any = None) -> dict[str, Any]:
        if isinstance(comp, dict) and isinstance(comp.get("deu_verb"), dict):
            return comp["deu_verb"]
        if isinstance(verb, str) and verb in AUX:
            return AUX[verb]
        if isinstance(verb, str) and verb in EXTRA:
            return EXTRA[verb]
        if isinstance(verb, dict) and isinstance(verb.get("deu_verb"), dict):
            return verb["deu_verb"]
        entry = self._verb(verb)  # type: ignore[attr-defined]
        gv = entry.get("deu")
        if not isinstance(gv, dict):
            raise RenderError(f"verb {entry.get('inf')} has no German")
        return gv

    def _chain(self, gv: dict[str, Any], person: int, tense: str) -> tuple[str, list[str], str, list[str]]:
        """``(finite, non-finite verbs, separable prefix, extra adverbs)`` for a tense."""

        prefix = _sep(gv)
        if tense == "present":
            return present(gv, person), [], prefix, []
        if tense == "praet":
            return praeteritum(gv, person), [], prefix, []
        if tense in {"perfekt", "recent"}:
            extra = ["gerade"] if tense == "recent" else []
            return present(aux_of(gv), person), [participle(gv)], "", extra
        if tense == "plusq":
            return praeteritum(aux_of(gv), person), [participle(gv)], "", []
        if tense == "futur":
            return present(AUX["werden"], person), [infinitive(gv)], "", []
        if tense == "konj":
            form = konjunktiv(gv, person)
            if form:
                return form, [], prefix, []
            return konjunktiv(AUX["werden"], person) or "", [infinitive(gv)], "", []
        if tense in _MODAL_TENSES:
            modal, mood = _MODAL_TENSES[tense]
            form = present(AUX[modal], person) if mood == "pres" else konjunktiv(AUX[modal], person)
            return str(form), [infinitive(gv)], "", []
        raise RenderError(f"unknown German tense {tense}")

    def _object(self, gv: dict[str, Any], noun: dict[str, Any], spec: str, subject: dict[str, Any]) -> str:
        """A noun as the verb's object: ``def`` («den Film»), ``pro`` («ihn»), ``poss``
        («meinen Schlüssel»), ``all`` («den ganzen Käse»), ``allp`` («alle Bücher»);
        in the verb's case (``ocase``, dative for «helfen») after its preposition
        (``oprep``: «auf den Bus»)."""

        case = str(gv.get("ocase") or "acc")
        if spec == "pro":
            text = g_pronoun(noun, case)
        elif spec == "poss":
            text = noun_phrase(noun, "poss", case, owner=subject)
        elif spec == "all":
            text = noun_phrase(noun, "def", case, adj={"deu": "ganz"})
        elif spec == "allp":
            text = "alle " + noun_word(noun, case, True)
        elif spec in {"def", "indef", "kein", "dem", "none"}:
            text = noun_phrase(noun, spec, case)
        else:
            raise RenderError(f"unknown object spec {spec}")
        return f"{gv['oprep']} {text}" if gv.get("oprep") else text

    def g_cl(
        self,
        subject: dict[str, Any],
        verb: Any,
        comp: Any = None,
        t: Any = "present",
        o: str = "main",
        neg: Any = "",
        adv: Any = "",
        post: Any = "",
        np: str = "",
        at: Any = None,
        obj: Any = None,
        objform: str = "name",
        objnum: str = "",
        advk: str = "",
        advp: str = "",
        advs: str = "",
        pro: str = "",
    ) -> str:
        """A German clause in one word order (see the module docstring)."""

        comp_entry = comp if isinstance(comp, dict) else None
        gv = self._gv(verb, comp_entry)
        if comp in (None, "", "_") and isinstance(gv.get("intrans"), dict):
            gv = gv["intrans"]
        person = g_person(subject)
        if isinstance(t, dict):
            t = (t.get("deu") or {}).get("modal") if isinstance(t.get("deu"), dict) else None
            if not t:
                raise RenderError("the tense slot is not a modal")
        pronoun_comp = ""
        if comp_entry is not None and np:
            comp_text = self._object(gv, comp_entry, np, subject)
            if np == "pro" and " " not in comp_text:
                # «ich sehe ihn morgen» (a bare pronoun leads the middle field);
                # «ich warte morgen auf ihn» (a prepositional one does not)
                pronoun_comp, comp_text = comp_text, ""
            comp_entry = None
        else:
            comp_text = _text(comp_entry) if comp_entry else ("" if comp in (None, "", "_") else str(comp))
        neg = _text(neg) if isinstance(neg, dict) else ("" if neg in (None, "_") else str(neg))
        if neg == "niemanden" and gv.get("nobody"):
            neg = str(gv["nobody"])
        if comp_text == "niemanden" and gv.get("nobody"):
            comp_text = str(gv["nobody"])
        tail = str(gv.get("tail") or "")
        if pronoun_comp and neg:
            if " " in pronoun_comp:  # «nicht auf ihn»
                before, comp_text, after, pronoun_comp = neg, pronoun_comp, "", ""
            else:
                before, after = "", neg
        elif tail and not comp_text and neg:
            # «Ich gehe nicht nach Hause»: the negation goes before the fixed end.
            before, comp_text, after = neg, "", ""
        else:
            before, comp_text, after = negate_comp(comp_entry, comp_text, neg)
        finite, nonfinite, prefix, extra = self._chain(gv, person, str(t))
        adverb = ""
        if adv not in (None, "", "_"):
            adverb = str(adv.get(f"deu_{advk}") or "") if isinstance(adv, dict) and advk else _text(adv)
            if not adverb:
                raise RenderError("the adverb has no German")
            adverb = " ".join(part for part in (advp, adverb, advs) if part)
        object_text = ""
        if isinstance(obj, dict):
            plural = objnum == "p"
            if objform == "pro":
                forms = {"dat": g_pronoun(obj, "dat") if not plural else "ihnen", "acc": g_pronoun(obj, "acc") if not plural else "sie"}
            elif obj.get("dg"):
                forms = {case: noun_phrase(obj, "def", case, plural) for case in ("dat", "acc")}
            else:
                forms = {"dat": g_subject(obj), "acc": g_subject(obj)}
            object_text = str(gv.get("pobj") or "{acc}").format(**forms)
        bare_pronoun = object_text if objform == "pro" and object_text and " " not in object_text else ""
        refl = ""
        if gv.get("refl"):
            refl = (_REFL_DAT if gv["refl"] == "dat" else _REFL_ACC)[person]
        middle = [
            refl, pronoun_comp, bare_pronoun, *extra, adverb, "" if bare_pronoun else object_text,
            self.g_at(at) if isinstance(at, dict) else "",
            before, comp_text, after, tail, _text(post) if post not in (None, "", "_") else "",
        ]
        middle = [part for part in middle if part]
        subj = ""
        if o not in {"inf", "zu", "nosubj"}:
            subj = g_pronoun(subject, "nom") if pro else g_subject(subject)
        if o == "main":
            words = [subj, finite, *middle, *nonfinite, prefix]
        elif o == "nosubj":
            words = [finite, *middle, *nonfinite, prefix]
        elif o == "inv":
            if refl and not _is_pronoun(subject) and not pro:
                middle = [part for part in middle if part != refl]
                words = [finite, refl, subj, *middle, *nonfinite, prefix]
            else:
                words = [finite, subj, *middle, *nonfinite, prefix]
        elif o == "sub":
            end = (prefix + finite) if prefix else finite
            words = [subj, *middle, *nonfinite, end]
        elif o in {"inf", "zu"}:
            if t != "present":
                raise RenderError("an infinitive clause has no tense")
            words = [*middle, infinitive(gv, zu=o == "zu")]
        else:
            raise RenderError(f"unknown German order {o}")
        return re.sub(r"\s+", " ", " ".join(word for word in words if word)).strip()

    def g_vp(self, verb: Any, person: str, comp: Any = None, t: str = "present") -> str:
        """The verb and its middle field for a German person given by number (the frame wrote the subject)."""

        return self.g_cl({"deu_p": int(person), "p": int(person)}, verb, comp, t=t, o="nosubj")

    def g_v(self, subject: dict[str, Any], verb: Any, t: str = "present") -> str:
        """Only the finite verb (the frame writes the rest)."""

        finite, nonfinite, prefix, _ = self._chain(self._gv(verb), g_person(subject), t)
        if nonfinite or prefix:
            raise RenderError("g_v is for a one-word verb")
        return finite

    def g_inf(self, verb: Any, comp: Any = None) -> str:
        """The infinitive with its complement («zum Markt gehen», «sich ausruhen»)."""

        return self.g_cl({"deu_p": 2, "p": 2}, verb, comp, o="inf")

    def g_pp(self, verb: Any) -> str:
        return participle(self._gv(verb))

    def g_obj(self, verb: Any, person: dict[str, Any]) -> str:
        """The object of a verb with an indirect object, as a pronoun («mit ihr», «ihm», «sie»)."""

        gv = self._gv(verb)
        pattern = str(gv.get("pobj") or "{dat}")
        return pattern.format(dat=g_pronoun(person, "dat"), acc=g_pronoun(person, "acc"))

    def g_imp(self, verb: Any, comp: Any = None, who: str = "du", neg: str = "", it: Any = None) -> str:
        """«Nimm den Bus», «Kommt mit», «Warten Sie hier», «Ruf ihn nicht an»."""

        comp_entry = comp if isinstance(comp, dict) else None
        gv = self._gv(verb, comp_entry)
        form = imperative(gv, who)
        refl = ""
        if gv.get("refl"):
            table = {"du": "dich", "ihr": "euch", "Sie": "sich"} if gv["refl"] != "dat" else {"du": "dir", "ihr": "euch", "Sie": "sich"}
            refl = table[who]
        pronoun = self._object(gv, it, "pro", {}) if isinstance(it, dict) else ""
        if pronoun:
            # «Ruf ihn nicht an», but «Warte nicht auf ihn»
            before, comp_text, after = (neg, "", "") if " " in pronoun else ("", "", neg)
        else:
            before, comp_text, after = negate_comp(comp_entry, _text(comp_entry) if comp_entry else "", neg)
        if pronoun and before:
            pronoun, comp_text = "", pronoun
        words = [form, "Sie" if who == "Sie" else "", refl, pronoun, before, comp_text, after, str(gv.get("tail") or ""), _sep(gv)]
        return re.sub(r"\s+", " ", " ".join(word for word in words if word)).strip()

    # -- people ---------------------------------------------------------------
    def g_s(self, entry: dict[str, Any]) -> str:
        return g_subject(entry)

    def g_acc(self, entry: dict[str, Any]) -> str:
        return g_pronoun(entry, "acc") if _is_pronoun(entry) else g_subject(entry)

    def g_dat(self, entry: dict[str, Any]) -> str:
        return g_pronoun(entry, "dat") if _is_pronoun(entry) else g_subject(entry)

    def g_pro(self, entry: dict[str, Any], case: str = "acc") -> str:
        """The personal pronoun for a person or a thing («ihn», «sie», «es»)."""

        return g_pronoun(entry, case)

    def g_gen(self, entry: dict[str, Any]) -> str:
        """A name's possessive: «Lilas», «Gus'»."""

        name = g_subject(entry)
        return name + ("'" if name.endswith(("s", "x", "z", "ß")) else "s")

    # -- nouns ----------------------------------------------------------------
    def g_np(self, noun: dict[str, Any], det: str = "def", case: str = "nom", number: str = "s", adj: Any = None) -> str:
        return noun_phrase(noun, det, case, number == "p", adj if isinstance(adj, dict) else None)

    def g_poss(self, noun: dict[str, Any], owner: dict[str, Any], case: str = "nom", number: str = "s", adj: Any = None) -> str:
        return noun_phrase(noun, "poss", case, number == "p", adj if isinstance(adj, dict) else None, owner=owner)

    def g_n(self, noun: dict[str, Any], number: str = "s", case: str = "nom") -> str:
        """The bare noun (sg or pl), for a quantity or a number before it."""

        return noun_word(noun, case, number == "p")

    def g_at(self, noun: dict[str, Any]) -> str:
        if noun.get("deu_at"):
            return str(noun["deu_at"])
        return prep_phrase("in", noun, "dat")

    def g_to(self, noun: dict[str, Any]) -> str:
        if noun.get("deu_to"):
            return str(noun["deu_to"])
        return prep_phrase("in", noun, "acc")

    def g_from(self, noun: dict[str, Any]) -> str:
        if noun.get("deu_from"):
            return str(noun["deu_from"])
        return prep_phrase("aus", noun, "dat")

    def g_pp_(self, noun: dict[str, Any], prep: str, case: str = "dat", number: str = "s") -> str:
        """A preposition + the definite noun phrase, contracted («zum», «im»)."""

        return prep_phrase(prep, noun, case, number == "p")

    # -- adjectives -----------------------------------------------------------
    def g_adj(self, adj: dict[str, Any]) -> str:
        return _text(adj)

    def g_comp(self, adj: dict[str, Any]) -> str:
        if adj.get("deu_cmp"):
            return str(adj["deu_cmp"])
        base = _text(adj)
        return base + ("r" if base.endswith("e") else "er")

    def g_cmp(self, adj: dict[str, Any], cmp: Any) -> str:
        """«größer als», «weniger groß als», «so groß wie»."""

        kind = cmp.get("id") if isinstance(cmp, dict) else str(cmp)
        if kind == "moins":
            return f"weniger {_text(adj)} als"
        if kind == "aussi":
            return f"so {_text(adj)} wie"
        return f"{self.g_comp(adj)} als"

    def g_sup(self, adj: dict[str, Any], noun: Any = None, case: str = "nom", least: str = "") -> str:
        """Predicative «am größten»; with a noun «der größte Park» (least: «der am wenigsten teure …»)."""

        stem = str(adj.get("deu_sup") or (self.g_comp(adj)[:-2] + ("est" if re.search(r"(?:[dtsßzx]|sch)$", _text(adj)) else "st")))
        if not isinstance(noun, dict):
            return f"am wenigsten {_text(adj)}" if least else f"am {stem}en"
        key = _gkey(noun, False)
        article = _DEF[case][key]
        if least:
            return f"{article} am wenigsten {adj_attr(adj, _WEAK_ADJ[case][key])} {noun_word(noun, case)}"
        return f"{article} {stem}{_WEAK_ADJ[case][key]} {noun_word(noun, case)}"

    def g_job(self, job: dict[str, Any], head: dict[str, Any]) -> str:
        if _gender(head) == "f" and job.get("deu_f"):
            return str(job["deu_f"])
        return _text(job)

    def g_f(self, entry: dict[str, Any], key: str) -> str:
        """A German field of an entry by name (``{G|g_f:in}`` → ``entry["deu_in"]``)."""

        value = entry.get(f"deu_{key}")
        if value is None:
            raise RenderError(f"{entry.get('id') or entry.get('fr')} has no deu_{key}")
        return str(value)

    def g_rel(self, noun: dict[str, Any], case: str = "nom", verb: Any = None) -> str:
        """The relative pronoun for a noun («der», «den», «dem», «auf den»), in the verb's case."""

        prep = ""
        if verb is not None:
            gv = self._gv(verb)
            case = str(gv.get("ocase") or case)
            prep = str(gv.get("oprep") or "")
        key = _gkey(noun, noun.get("n") == "p" and not noun.get("dg"))
        pronoun = {"dat": {"m": "dem", "f": "der", "n": "dem", "p": "denen"}}.get(case, _DEF.get(case, _DEF["nom"]))[key]
        return f"{prep} {pronoun}".strip()

    def g_this(self, noun: dict[str, Any], number: str = "s", where: str = "hier") -> str:
        """«Dieser hier», «Die da» (the demonstrative pronoun standing for the noun)."""

        key = _gkey(noun, number == "p")
        if where == "da":
            return f"{_DEF['nom'][key]} da"
        return f"dies{_DER_END['nom'][key]} hier"

    def g_best(self, noun: dict[str, Any], case: str = "nom") -> str:
        return self.g_sup({"deu": "gut", "deu_sup": "best"}, noun, case)

    def g_attr(self, adj: dict[str, Any], ending: str = "") -> str:
        return adj_attr(adj, ending)

    def g_q(self, noun: dict[str, Any], case: str = "acc") -> str:
        """After a quantity: the plural of a countable noun, else the bare noun («Äpfel», «Käse»)."""

        tags = noun.get("tags") or []
        count = "count" in tags and "mass" not in tags
        return noun_word(noun, case, count and bool(noun.get("dpl")))

    def g_qty(self, qty: dict[str, Any], noun: dict[str, Any]) -> str:
        """«viel Käse», «viele Äpfel», «zu viele Äpfel»."""

        tags = noun.get("tags") or []
        count = "count" in tags and "mass" not in tags and bool(noun.get("dpl"))
        word = str(qty.get("deu_count") if count and qty.get("deu_count") else _text(qty))
        return f"{word} {self.g_q(noun)}"

    def g_loc(self, loc: dict[str, Any], noun: dict[str, Any]) -> str:
        """«neben dem Bahnhof», «gegenüber der Post», «in der Nähe des Parks», «weit weg vom Markt»."""

        prep = _text(loc)
        case = str(loc.get("deu_case") or "dat")
        if case == "gen":
            return f"{prep} {noun_phrase(noun, 'def', 'gen')}"
        if prep.endswith(" von"):
            return f"{prep[:-4]} {prep_phrase('von', noun, 'dat')}"
        return f"{prep} {noun_phrase(noun, 'def', case)}"

    def g_gn(self, entry: dict[str, Any], head: dict[str, Any]) -> str:
        """A German variant by the head's gender (``deu_f`` for a woman)."""

        if _gender(head) == "f" and entry.get("deu_f"):
            return str(entry["deu_f"])
        return _text(entry)


# --------------------------------------------------------------------------- #
# The German side of the lexicon (lexicon_de.json), merged at load time
# --------------------------------------------------------------------------- #

_MONTHS_DE = {
    "January": "Januar", "February": "Februar", "March": "März", "April": "April", "May": "Mai", "June": "Juni",
    "July": "Juli", "August": "August", "September": "September", "October": "Oktober", "November": "November",
    "December": "Dezember",
}
_DAYS_DE = {
    "Monday": "Montag", "Tuesday": "Dienstag", "Wednesday": "Mittwoch", "Thursday": "Donnerstag",
    "Friday": "Freitag", "Saturday": "Samstag", "Sunday": "Sonntag",
}


def _derived(pool: str, entry: dict[str, Any]) -> dict[str, Any]:
    """German for the pools that follow from their English (dates, times, months, days)."""

    en = str(entry.get("en") or "")
    if pool == "month" and en in _MONTHS_DE:
        return {"deu": _MONTHS_DE[en], "deu_in": f"im {_MONTHS_DE[en]}"}
    if pool == "weekday" and en in _DAYS_DE:
        day = _DAYS_DE[en]
        return {"deu": day, "deu_am": f"am {day}", "deu_pl": f"{day.lower()}s"}
    if pool == "date":
        match = re.match(r"^([A-Z][a-z]+) (\d+)$", en)
        if match and match.group(1) in _MONTHS_DE:
            text = f"{int(match.group(2))}. {_MONTHS_DE[match.group(1)]}"
            return {"deu": text, "deu_am": f"am {text}"}
    if pool == "clock":
        special = {"noon": "zwölf Uhr mittags", "midnight": "Mitternacht", "half past midnight": "halb eins in der Nacht"}
        if en in special:
            text = special[en]
            return {"deu": text, "deu_um": "um Mitternacht" if en == "midnight" else f"um {text}"}
        match = re.match(r"^(\d{1,2}):(\d{2})(?:\s*(am|pm))?$", en)
        if match:
            hour, minutes = int(match.group(1)), match.group(2)
            text = f"{hour} Uhr" if minutes == "00" else f"{hour}:{minutes} Uhr"
            return {"deu": text, "deu_um": f"um {text}"}
    return {}


def merge_overlay(
    overlay: dict[str, Any],
    *,
    verbs: dict[str, dict[str, Any]],
    pools: dict[str, list[dict[str, Any]]],
) -> None:
    """Merge ``lexicon_de.json`` into the lexicon entries (in place)."""

    def apply(entry: dict[str, Any], value: Any) -> None:
        if isinstance(value, str):
            entry["deu"] = value
        elif isinstance(value, dict):
            for key, item in value.items():
                if key == "comps" and isinstance(item, dict):
                    for comp in entry.get("comps") or []:
                        if comp.get("fr") in item:
                            apply(comp, item[comp["fr"]])
                else:
                    entry[key] = item

    for verb_id, data in (overlay.get("verbs") or {}).items():
        entry = verbs.get(verb_id)
        if entry is None or not isinstance(data, dict):
            continue
        data = dict(data)
        comps = data.pop("comps", None)
        entry["deu"] = data
        if isinstance(comps, dict):
            for comp in entry.get("comps") or []:
                if comp.get("fr") in comps:
                    apply(comp, comps[comp["fr"]])
    sections = {"nouns": "noun", "adjectives": "adj", "pronouns": "pron", "cast": "subj"}
    for section, pool_name in sections.items():
        table = overlay.get(section) or {}
        for entry in pools.get(pool_name) or []:
            key = entry.get("id")
            if key in table:
                apply(entry, table[key])
    for pool_name, table in (overlay.get("pools") or {}).items():
        for entry in pools.get(pool_name) or []:
            key = entry.get("id") if entry.get("id") in table else entry.get("fr")
            if key in table:
                apply(entry, table[key])
    for pool_name, entries in pools.items():
        for entry in entries:
            for key, value in _derived(pool_name, entry).items():
                entry.setdefault(key, value)


# --------------------------------------------------------------------------- #
# The checker
# --------------------------------------------------------------------------- #


_ENGLISH_WORDS = re.compile(
    r"\b(?:the|you|is|are|were|would|like|with|this|that|have|has|at the|in the|and|of|to|it|he|she|they|"
    r"please|because|when|where|which|there|some|any|not|don't|doesn't|been|can|my|your|his|her|their)\b",
)
_SUBORDINATORS = ("weil", "dass", "wenn", "ob", "als", "obwohl", "da", "sobald", "wo", "bevor", "nachdem")


def _finite_forms(verbs: list[dict[str, Any]]) -> dict[str, set[int]]:
    """Every finite form of every German verb the lexicon knows, with its persons."""

    forms: dict[str, set[int]] = {}
    for gv in [*verbs, *AUX.values(), *EXTRA.values()]:
        prefix = _sep(gv)
        for person in range(6):
            candidates = [present(gv, person), praeteritum(gv, person)]
            konj = konjunktiv(gv, person)
            if konj:
                candidates.append(konj)
            for form in candidates:
                forms.setdefault(form.lower(), set()).add(person)
                if prefix:
                    forms.setdefault((prefix + form).lower(), set()).add(person)
    return forms


def german_violations(
    text: str,
    *,
    nouns: list[dict[str, Any]] = (),  # type: ignore[assignment]
    verbs: list[dict[str, Any]] = (),  # type: ignore[assignment]
    finite: dict[str, set[int]] | None = None,
) -> list[str]:
    """Obvious errors in one German rendering: article/gender agreement with the
    bound nouns, verb-second and verb-final order, the Perfekt auxiliary, English
    or template debris left in. Returns readable reasons (empty when clean)."""

    problems: list[str] = []
    if not text or not text.strip():
        return ["empty"]
    if re.search(r"[{}\[\]|§]|None|\s{2,}|\s[,.?!]", text):
        problems.append("template debris")
    if _ENGLISH_WORDS.search(text):
        problems.append(f"English word: {_ENGLISH_WORDS.search(text).group(0)}")
    if text[:1].islower():
        problems.append("lower-case start")
    finite = finite if finite is not None else _finite_forms(list(verbs))
    words_all = re.findall(r"[\wäöüÄÖÜß'-]+", text)
    # 1. Articles and adjective endings agree with the bound nouns.
    for noun in nouns or []:
        word = noun.get("deu")
        gender = noun.get("dg")
        if not word or not gender or noun.get("dproper"):
            continue
        forms = {str(word)}
        if noun.get("dpl"):
            forms.add(str(noun["dpl"]))
            forms.add(str(noun["dpl"]) + "n")
        if noun.get("dweak"):
            forms.add(str(noun["dweak"]))
        for match in re.finditer(r"\b(der|die|das|den|dem|des|ein|eine|einen|einem|einer|eines|kein|keine|keinen|keinem|keiner|dieser|diese|dieses|diesen|diesem)\s+(?:(?!bisschen\b|paar\b)([a-zäöüß][\wäöüß]*e[nmrs]?)\s+)?(" + "|".join(re.escape(form) for form in sorted(forms, key=len, reverse=True)) + r")\b", text):
            article, adjective, found = match.group(1), match.group(2), match.group(3)
            plural = found != word and found != noun.get("dweak")
            plural_set = {"die", "den", "keine", "keinen", "diese", "diesen", "der", "keiner", "dieser"}
            if found == noun.get("dpl") == word:
                # «die Vermieter»: singular and plural look alike
                allowed = plural_set | {
                    "der", "den", "dem", "des", "das", "ein", "einen", "einem", "eines", "eine", "einer",
                    "kein", "keinen", "keinem", "keines", "dieses", "diesem",
                }
            elif plural and gender in {"m", "n"} and found == word + ("es" if word.endswith(("s", "ß", "x", "z")) else "s"):
                allowed = plural_set | {"des", "eines", "keines", "dieses"}
            elif plural:
                allowed = plural_set
            else:
                allowed = {
                    "m": {"der", "den", "dem", "des", "ein", "einen", "einem", "eines", "kein", "keinen", "keinem", "keines", "dieser", "diesen", "diesem"},
                    "f": {"die", "der", "eine", "einer", "keine", "keiner", "diese", "dieser"},
                    "n": {"das", "dem", "des", "ein", "einem", "eines", "kein", "keinem", "keines", "dieses", "diesem"},
                }[gender]
            if article not in allowed:
                problems.append(f"article «{article} {found}» does not fit gender {gender}{' plural' if plural else ''}")
            if adjective and adjective.lower() not in {"neue", "alte"} and adjective[:1].islower():
                ending = re.search(r"e[nmrs]?$", adjective).group(0)
                ok = {
                    "der": {"e", "en"}, "die": {"e", "en"}, "das": {"e"}, "den": {"en"}, "dem": {"en"}, "des": {"en"},
                    "ein": {"er", "es"}, "kein": {"er", "es"}, "eine": {"e", "en"}, "keine": {"e", "en"},
                    "einen": {"en"}, "keinen": {"en"}, "einem": {"en"}, "keinem": {"en"}, "einer": {"en"}, "keiner": {"en"},
                    "dieser": {"e", "en"}, "diese": {"e", "en"}, "dieses": {"e"}, "diesen": {"en"}, "diesem": {"en"},
                }.get(article, {ending})
                if ending not in ok:
                    problems.append(f"adjective ending «{article} {adjective} {found}»")
    # 2. Verb-final after a subordinator; verb-second after a fronted clause.
    for clause in re.split(r"(?<=[.?!:])\s+", text):
        parts = [part.strip() for part in re.split(r",", clause) if part.strip()]
        for index, part in enumerate(parts):
            tokens = re.findall(r"[\wäöüÄÖÜß'-]+", part)
            if not tokens:
                continue
            head = tokens[0].lower()
            # a clause-initial «Als Kind …» or «Wo wohnst du?» is no subordinate clause:
            # one is only where a main clause follows (or it follows one).
            if head in _SUBORDINATORS and len(tokens) > 2 and (index > 0 or index + 1 < len(parts)) and tokens[1].lower() not in finite:
                last = tokens[-1].lower()
                if last not in finite:
                    problems.append(f"verb not final in «{part}»")
                if index + 1 < len(parts) and index == 0:
                    following = re.findall(r"[\wäöüÄÖÜß'-]+", parts[index + 1])
                    if following and following[0].lower() not in finite and following[0] not in {"dann", "so"}:
                        problems.append(f"no verb-first after «{part}»")
            elif head in {"ich", "du", "er", "sie", "es", "wir", "ihr"} and len(tokens) > 1:
                verb = tokens[1].lower()
                persons = finite.get(verb)
                expected = {"ich": {0}, "du": {1}, "er": {2}, "es": {2}, "wir": {3}, "ihr": {4}, "sie": {2, 5}}[head]
                if persons is not None and not persons & expected and not (head == "sie" and persons & {5}):
                    problems.append(f"«{tokens[0]} {tokens[1]}» does not agree")
            elif head in {"heute", "morgen", "gestern", "jetzt", "dann", "oft", "manchmal", "normalerweise", "früher", "samstags", "sonntags"} and len(tokens) > 2:
                if tokens[1].lower() in {"ich", "du", "er", "sie", "es", "wir", "ihr"}:
                    problems.append(f"no verb-second after «{tokens[0]}»")
    # 3. The Perfekt auxiliary: «ist … gegessen», «hat … gegangen».
    sein_all = {participle(gv) for gv in verbs if gv.get("aux") == "sein"}
    haben_all = {participle(gv) for gv in verbs if gv.get("aux") != "sein"}
    # «Gus' Auto gefahren» (haben) and «nach Lyon gefahren» (sein): only an
    # unambiguous participle is checked.
    sein_pp, haben_pp = sein_all - haben_all, haben_all - sein_all
    for clause in re.split(r"[,.?!:;]", text):
        tokens = re.findall(r"[\wäöüÄÖÜß'-]+", clause)
        lowered = [token.lower() for token in tokens]
        has_sein = any(token in {"bin", "bist", "ist", "sind", "seid", "war", "warst", "waren", "wart"} for token in lowered)
        has_haben = any(token in {"habe", "hast", "hat", "haben", "habt", "hatte", "hattest", "hatten", "hattet"} for token in lowered)
        for token in tokens:
            if token in sein_pp and has_haben and not has_sein:
                problems.append(f"«{token}» takes sein")
            if token in haben_pp and has_sein and not has_haben:
                problems.append(f"«{token}» takes haben")
    del words_all
    return problems


__all__ = ["AUX", "GermanFilters", "RenderError", "g_person", "german_violations", "noun_phrase", "participle", "present"]
