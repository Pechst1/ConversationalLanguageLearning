"""La Revue de Romy — editorial policy as data (WP-119 §4, §6, §7, §8).

Pure data and tiny helpers, no I/O: the topics a week covers, the sensitive first
filter at intake (§4.1, also imported by ``news_service`` for the feuilleton), what a
painted plate may never show (§8.1), the ``outfit`` catalogue and which place calls
for which dress (§8.2), the known plate a new place falls back to (§8.1), the support
each band starts with (§6), and which cast member has a reason to care about a topic
(§7).

See ``docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

#: The topics a week of dossiers spreads over (§4.1).
TOPICS: tuple[str, ...] = ("food", "culture", "city", "sport", "nature", "work", "politics")

#: The sensitive first filter at intake (§4.1): about subject matter, not level.
#: Moved verbatim from ``NewsService.FEUILLETON_SENSITIVE_TERMS``, which now imports it.
#: Matched as substrings of lower-cased text, hence the trailing spaces in "mort " and "viol ".
SENSITIVE_TERMS: tuple[str, ...] = (
    "abus",
    "agression sexuelle",
    "assassinat",
    "attentat",
    "décès",
    "disparition",
    "fusillade",
    "guerre",
    "meurtre",
    "mort ",
    "mortel",
    "otage",
    "pédocriminalité",
    "suicide",
    "terrorisme",
    "viol ",
    "violence conjugale",
)

#: Words a plate brief may never contain (§8.1 staging rule: places drawn, people told).
#: Matched as whole words after accent folding (see :func:`plate_forbidden_hits`).
PLATE_FORBIDDEN: tuple[str, ...] = (
    # WP-119 §12.4 (owner, 2026-10-02): people, crowds and real places are allowed on a plate.
    # What stays forbidden is what clashes with the drawn cast or misleads: portraits and close-ups
    # (a painted face at the cast's scale), party emblems and logos, readable text.
    "portrait",
    "portraits",
    "close-up",
    "closeup",
    "gros plan",
    "selfie",
    "emblem",
    "emblems",
    "embleme",
    "emblemes",
    "logo",
    "logos",
    "banner",
    "banners",
    "banderole",
    "banderoles",
    "slogan",
    "slogans",
    "caption",
    "headline",
    "lettering",
    "texte",
    "text",
)

#: The ``outfit`` catalogue of the Revue stage (§8.2). ``coat`` is the canon default.
OUTFITS: tuple[str, ...] = ("coat", "suit", "apron", "raincoat", "sport", "scarf_only", "chef", "hi_vis")

DEFAULT_OUTFIT = "coat"

#: Place kind → the work outfit Toi wears there once the learner takes part (§8.2,
#: phase 2: :func:`dress_for_angle`). Anything else: ``coat``.
DRESS_FOR_PLACE: dict[str, str] = {
    # WP-119 §12.5 (owner): Toi changes clothes only when the learner takes part in the place's
    # work, never for the setting alone. Phase 2 decides it per dossier angle; until then only the
    # two cases that are always work: a kitchen or cellar (apron) and a worksite (hi-vis).
    "cellar": "apron",
    "kitchen": "apron",
    "worksite": "hi_vis",
    "default": DEFAULT_OUTFIT,
}

#: Words in a place's id, name or brief → its kind. Order is priority: the first kind
#: with a matching word wins (indoor places before weather, weather before outdoor
#: places). Words match accent-folded tokens exactly; a trailing ``*`` makes the word a
#: prefix (``"stade*"`` matches ``"stades"``) — kept for stems that cannot collide with
#: an ordinary word ("chai" must not match "chaise", nor "marche" "marcher").
PLACE_KIND_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hemicycle", ("hemicycle", "assemblee", "senat", "parliament", "parlement")),
    ("chamber", ("chamber", "chambre", "council", "conseil")),
    ("ministry", ("ministry", "ministere", "elysee", "matignon", "prefecture")),
    ("cellar", ("cellar", "cellars", "cave", "caves", "chai", "chais", "winery")),
    ("kitchen", ("kitchen", "kitchens", "cuisine", "cuisines", "restaurant*", "brasserie*", "bistro*")),
    ("bakery", ("bakery", "boulangerie*", "patisserie*", "fournil")),
    ("worksite", ("worksite", "chantier*", "construction", "scaffold*", "echafaud*", "factory", "usine*")),
    ("rain", ("rain", "rainy", "raining", "pluie*", "pluvieu*", "orage*", "storm*", "averse*")),
    ("stadium", ("stadium*", "stade*", "arena")),
    ("track", ("track", "tracks", "piste", "pistes", "velodrome")),
    ("market", ("market", "markets", "marche", "marches", "halles", "stall", "stalls", "etal", "etals")),
    ("vineyard", ("vineyard*", "vignoble*", "vigne", "vignes", "vine", "vines", "vendange*")),
    ("quay", ("quay*", "quai", "quais", "canal", "riverbank", "berge*", "seine")),
    ("station", ("station", "gare", "railway")),
    ("metro", ("metro", "subway", "rer")),
    ("school", ("school*", "ecole*", "classroom*", "college", "lycee")),
    (
        "park",
        ("park", "parks", "parc", "parcs", "jardin*", "garden*", "forest*", "foret*", "field",
         "fields", "champ", "champs", "mountain*", "montagne*"),
    ),
    ("city_hall", ("mairie", "townhall")),
    ("office", ("office", "offices", "bureau", "bureaux")),
    ("cafe", ("cafe", "cafes", "bar", "bars", "comptoir")),
    ("newsroom", ("newsroom", "redaction", "journal")),
    ("street", ("street*", "rue", "rues", "ruelle", "avenue", "boulevard", "square")),
)

#: Place kind → a known ``SEASON_ONE_LOCATIONS`` id whose plate stands in while plate
#: generation is off (§8.1); Romy then says where they really are.
PLACE_FALLBACKS: dict[str, str] = {
    "hemicycle": "mairie",
    "chamber": "mairie",
    "ministry": "mairie",
    "city_hall": "mairie",
    "office": "ngo_office",
    "cellar": "mistral_back_room",
    "kitchen": "le_mistral",
    "cafe": "le_mistral",
    "bakery": "boulangerie",
    "market": "marche_canal",
    "worksite": "rue_de_lancry",
    "street": "rue_de_lancry",
    "rain": "quai_de_valmy",
    "quay_rain": "quai_de_valmy",
    "quay": "quai_de_valmy",
    "stadium": "buttes_chaumont",
    "track": "buttes_chaumont",
    "vineyard": "buttes_chaumont",
    "park": "buttes_chaumont",
    "station": "gare_de_lest",
    "metro": "metro_platform",
    "school": "ecole",
    "newsroom": "newsroom",
    "default": "newsroom",
}

#: The support and depth each band starts with (§6). Targets are planning targets, not
#: caps. ``simplify_on_breakdown`` is on at every band (§5.3 applies to all);
#: ``repeat_simpler`` is A1's "Romy repeats in simpler words unasked".
SUPPORT_DEFAULTS: dict[str, dict[str, Any]] = {
    "A1": {
        "glosses": "shown",
        "translation": "one_tap",
        "simplify_on_breakdown": True,
        "repeat_simpler": True,
        "reading_target_words": 60,
        "vocab_target": 5,
        "depth": "change_and_who",
    },
    "A2": {
        "glosses": "tap",
        "translation": "on_request",
        "simplify_on_breakdown": True,
        "repeat_simpler": False,
        "reading_target_words": 90,
        "vocab_target": 5,
        "depth": "plus_one_interpretation",
    },
    "B1": {
        "glosses": "tap",
        "translation": "none",
        "simplify_on_breakdown": True,
        "repeat_simpler": False,
        "reading_target_words": 140,
        "vocab_target": 7,
        "depth": "plus_disagreement",
    },
    "B2": {
        "glosses": "none",
        "translation": "none",
        "simplify_on_breakdown": True,
        "repeat_simpler": False,
        "reading_target_words": 200,
        "vocab_target": 7,
        "depth": "procedure_and_actors",
    },
}

BANDS: tuple[str, ...] = tuple(SUPPORT_DEFAULTS)

#: Topic → cast members with a reason to care, in order of preference (§7). The
#: ``reason`` is a template filled with ``{place}`` (the place's French name) and
#: ``{title}`` (the dossier's French title); it is spoken on the guest's entry.
GUEST_AFFINITY: dict[str, list[dict[str, str]]] = {
    "food": [
        {
            "id": "margaux_barman",
            "reason": "she runs the café counter and cares where what she serves comes from ({place})",
            "reason_fr": "Ce que je sers au comptoir, ça vient de quelque part. Alors ça me regarde.",
        },
    ],
    "culture": [
        {
            "id": "lila_bonnet",
            "reason": "her pupils asked her about it in class ({title})",
            "reason_fr": "Mes élèves m'ont posé la question en classe. Je veux leur répondre juste.",
        },
    ],
    "city": [
        {
            "id": "camille_marchand",
            "reason": "it is her quartier, and she has an opinion about {place}",
            "reason_fr": "C'est mon quartier. J'ai des chiffres là-dessus, si vous voulez.",
        },
        {
            "id": "landlord_marchand",
            "reason": "he manages buildings in the 10e and anything about {place} touches his business",
            "reason_fr": "Je gère des immeubles dans le dixième. Tout cela me concerne, voyez-vous.",
        },
    ],
    "work": [
        {
            "id": "marin_leveque",
            "reason": "the NGO he works for deals with people this affects ({title})",
            "reason_fr": "À l'association, on voit des gens que ça touche. Je peux dire un mot ?",
        },
    ],
    "sport": [
        {
            "id": "augustin_de_roncourt",
            "reason": "there is money in it, and Gus always knows who is paying ({title})",
            "reason_fr": "Il y a de l'argent là-dedans. Je sais toujours qui paie, croyez-moi.",
        },
    ],
    "politics": [
        {
            "id": "marin_leveque",
            "reason": "the NGO he works for follows this closely ({title})",
            "reason_fr": "À l'association, on suit ça de très près. Je peux dire un mot ?",
        },
        {
            "id": "augustin_de_roncourt",
            "reason": "he dines with people on the other side of it ({title})",
            "reason_fr": "Je dîne avec des gens de l'autre camp. C'est passionnant. Non : fascinant.",
        },
    ],
    "nature": [
        {
            "id": "marin_leveque",
            "reason": "the NGO he works for campaigns on it ({place})",
            "reason_fr": "Mon association fait campagne là-dessus. Ça me tient à cœur.",
        },
    ],
}


#: WP-119 phase 2: the cast members who can be a Revue guest (Romy is the host).
GUEST_CAST_IDS: tuple[str, ...] = (
    "margaux_barman",
    "lila_bonnet",
    "camille_marchand",
    "landlord_marchand",
    "marin_leveque",
    "augustin_de_roncourt",
)

#: A guest's own French reason when the angle's ``guest_fit`` names them outside the
#: topic's affinity (§7: they enter because they have a reason to care, spoken on entry).
GUEST_REASON_FR: dict[str, str] = {
    "margaux_barman": "Ça se discute au comptoir. Alors j'écoute.",
    "lila_bonnet": "Mes élèves vont me poser la question. Je préfère savoir.",
    "camille_marchand": "J'ai regardé les chiffres. Je peux préciser ?",
    "landlord_marchand": "Permettez. Cela touche mes immeubles, voyez-vous.",
    "marin_leveque": "À l'association, on en parle beaucoup. Je peux dire un mot ?",
    "augustin_de_roncourt": "Permettez-moi. J'ai un avis. Un avis magnifique.",
}

#: WP-119 phase 2 (§7): when an angle names no ``guest_fit``, a guest of the topic's
#: affinity enters during ``pursue``/``make`` when the learner's turn touches one of their
#: words (accent-folded, a trailing ``*`` is a prefix — the same rule as the place kinds).
GUEST_TOPIC_WORDS: dict[str, tuple[str, ...]] = {
    "margaux_barman": (
        "cafe", "comptoir", "bar", "boire", "vin*", "biere*", "servir", "sert", "client*", "produit*",
        "manger", "cuisine*", "pain", "fromage*", "legume*", "fruit*", "acheter", "achete*", "prix",
    ),
    "lila_bonnet": (
        "ecole*", "eleve*", "classe*", "enfant*", "professeur*", "prof", "profs", "apprendre", "musique*",
        "peinture*", "peindre", "art", "artiste*", "livre*", "lire", "histoire*",
    ),
    "camille_marchand": (
        "quartier*", "rue*", "ville*", "velo*", "piste*", "urbanisme", "logement*", "immeuble*",
        "habitant*", "voisin*", "chiffre*", "metro", "transport*",
    ),
    "landlord_marchand": (
        "immeuble*", "loyer*", "proprietaire*", "logement*", "appartement*", "locataire*", "escalier*",
        "batiment*", "vendre", "vente*",
    ),
    "marin_leveque": (
        "association*", "ong", "salarie*", "travail*", "travailleur*", "droit*", "syndicat*", "climat*",
        "environnement*", "nature", "ecolog*", "mer", "peche*", "pecheur*", "planete",
    ),
    "augustin_de_roncourt": (
        "argent", "payer", "paie", "paye*", "cout*", "coute*", "cher*", "budget*", "sponsor*",
        "entreprise*", "euro*", "million*", "investi*", "riche*", "contrat*",
    ),
}

#: WP-119 §12.5 and phase 2: how the learner takes part in the angle (``Angle.participation``,
#: set by the builder) decides Toi's dress; the place alone never does.
PARTICIPATION_DRESS: dict[str, str] = {
    "none": DEFAULT_OUTFIT,
    "formal": "suit",
}


def dress_for_angle(participation: str | None, kind: str | None) -> str:
    """Toi's outfit for an angle (phase 2): ``none`` → coat, ``formal`` → suit, ``helps`` or
    ``works`` → the place's work outfit (:data:`DRESS_FOR_PLACE`: apron in a kitchen or a
    cellar, hi-vis on a worksite), and an apron wherever the place names no work outfit.
    :data:`DRESS_FOR_PLACE` is only consulted once the learner takes part.
    """

    value = str(participation or "none")
    if value in {"helps", "works"}:
        dress = DRESS_FOR_PLACE.get(str(kind or ""), DEFAULT_OUTFIT)
        return dress if dress != DEFAULT_OUTFIT else "apron"
    return PARTICIPATION_DRESS.get(value, DEFAULT_OUTFIT)


def guest_words_hit(cast_id: str, text: str | None) -> str | None:
    """The first of ``cast_id``'s :data:`GUEST_TOPIC_WORDS` that ``text`` touches, or None."""

    tokens = _tokens(text or "")
    for word in GUEST_TOPIC_WORDS.get(cast_id, ()):
        if _word_matches(word, tokens):
            return word.rstrip("*")
    return None


def _fold_ascii(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", _fold_ascii(text)) if token]


def _word_matches(word: str, tokens: list[str]) -> bool:
    if word.endswith("*"):
        stem = word[:-1]
        return any(token.startswith(stem) for token in tokens)
    return word in tokens


def normalize_band(band: str | None) -> str:
    """``"a2"`` → ``"A2"``; ``"B2+"``, ``"C1"``, ``"C2"`` → ``"B2"``; unknown → ``"A1"``."""

    raw = str(band or "").strip().upper().rstrip("+")
    if raw in SUPPORT_DEFAULTS:
        return raw
    if raw in {"C1", "C2"}:
        return "B2"
    return "A1"


def band_support(band: str | None) -> dict[str, Any]:
    """A copy of the §6 defaults for ``band`` (normalised with :func:`normalize_band`)."""

    return dict(SUPPORT_DEFAULTS[normalize_band(band)])


def place_kind(text: str | None) -> str:
    """Guess a place's kind from its id, name or brief words (``"default"`` if none match).

    ``quay`` with a rain word anywhere becomes ``quay_rain``.
    """

    tokens = _tokens(str(text or "").replace("_", " "))
    kinds = [
        kind for kind, words in PLACE_KIND_KEYWORDS if any(_word_matches(word, tokens) for word in words)
    ]
    if not kinds:
        return "default"
    if "quay" in kinds and "rain" in kinds:
        return "quay_rain"
    return kinds[0]


def dress_for(kind: str | None) -> str:
    """The outfit for a place kind (§8.2); ``coat`` when the kind calls for nothing special."""

    return DRESS_FOR_PLACE.get(str(kind or ""), DEFAULT_OUTFIT)


def fallback_place_for(kind: str | None) -> str:
    """The known season-1 location whose plate stands in for a place of this kind (§8.1)."""

    return PLACE_FALLBACKS.get(str(kind or ""), PLACE_FALLBACKS["default"])


def plate_forbidden_hits(text: str | None) -> list[str]:
    """The :data:`PLATE_FORBIDDEN` words a plate brief contains (whole words, accent-folded)."""

    forbidden = {_fold_ascii(word) for word in PLATE_FORBIDDEN}
    seen: list[str] = []
    for token in _tokens(text or ""):
        if token in forbidden and token not in seen:
            seen.append(token)
    return seen


def is_sensitive(text: str | None) -> bool:
    """Whether lower-cased ``text`` contains a :data:`SENSITIVE_TERMS` entry (§4.1)."""

    lowered = str(text or "").lower()
    return any(term in lowered for term in SENSITIVE_TERMS)


def guests_for(topic: str, **fill: str) -> list[dict[str, str]]:
    """The topic's preferred guests with their ``reason`` (English, for the plan and the
    provider) and ``reason_fr`` (spoken on entry) filled (missing keys left as ``…``)."""

    class _Blank(dict):
        def __missing__(self, key: str) -> str:
            return "…"

    values = _Blank(fill)
    return [
        {
            "id": row["id"],
            "reason": row["reason"].format_map(values),
            "reason_fr": row.get("reason_fr", "").format_map(values) or GUEST_REASON_FR.get(row["id"], ""),
        }
        for row in GUEST_AFFINITY.get(topic, [])
    ]
