"""Agent nouns in -eur / -ier are masculine words: their feminine is another word.

«joueur» was marked ``mf`` in the core lexicon, so a card could print «la joueur»;
the feminine is «la joueuse», a word of its own. The owner approved (2 Nov) the
masculine gender for joueur, visiteur, voleur, fermier, sénateur and instituteur
(``gender_overrides`` in ``app/data/lexical/authored_b2_c1.json``, so a rebuild of
the lexicon keeps it).

The guard is narrow on purpose: only nouns ending in -eur / -ier, whose
feminine changes the word (-euse, -rice, -ière). Epicene nouns such as
«artiste» or «élève» are a single word for both and are not looked at.
The -eur / -ier nouns still marked ``mf`` today are listed one by one below,
waiting for the owner's word; any other one is flagged.
"""
from __future__ import annotations

import json
from pathlib import Path

LEXICON = Path(__file__).resolve().parents[1] / "app" / "data" / "lexical" / "fr_core_lexicon.json"

#: Owner decision, 2 Nov: masculine, with the feminine that is a different word.
OWNER_MASCULINE = {
    "joueur": "joueuse",
    "visiteur": "visiteuse",
    "voleur": "voleuse",
    "fermier": "fermière",
    "sénateur": "sénatrice",
    "instituteur": "institutrice",
}

#: -eur / -ier nouns still marked ``mf`` on 2 Nov, not yet decided by the owner.
#: Shrink this list as they are decided; never grow it.
AWAITING_OWNER = frozenset(
    """
    acheteur administrateur amateur banquier boursier collaborateur créateur demandeur
    détenteur dictateur douanier électeur enquêteur entrepreneur exportateur fondateur
    guerrier héritier inspecteur interlocuteur meurtrier négociateur observateur pêcheur
    porteur prisonnier procureur producteur promoteur protecteur rédacteur romancier
    saisonnier sorcier tueur utilisateur
    """.split()
)

AGENT_SUFFIXES = ("eur", "ier")


def _lemmas() -> dict[str, dict]:
    return json.loads(LEXICON.read_text(encoding="utf-8"))["lemmas"]


def test_the_owner_approved_agent_nouns_are_masculine_nouns() -> None:
    lemmas = _lemmas()
    for lemma, feminine in OWNER_MASCULINE.items():
        entry = lemmas[lemma]
        assert entry["pos"] == "noun", lemma
        assert entry["gender"] == "m", f"«{lemma}» is masculine (its feminine is «{feminine}»), not {entry['gender']!r}"


def test_no_other_agent_noun_in_eur_or_ier_is_marked_both_genders() -> None:
    flagged = sorted(
        lemma
        for lemma, entry in _lemmas().items()
        if entry.get("pos") == "noun"
        and entry.get("gender") == "mf"
        and lemma.endswith(AGENT_SUFFIXES)
        and lemma not in AWAITING_OWNER
    )
    assert not flagged, (
        f"marked mf, but the feminine of an -eur/-ier noun is another word: {flagged} "
        "(set gender 'm' through gender_overrides in authored_b2_c1.json)"
    )


def test_the_guard_leaves_epicene_nouns_alone() -> None:
    lemmas = _lemmas()
    for lemma in ("artiste", "élève"):
        if lemma in lemmas:
            assert not lemma.endswith(AGENT_SUFFIXES)
    assert not set(OWNER_MASCULINE) & AWAITING_OWNER
