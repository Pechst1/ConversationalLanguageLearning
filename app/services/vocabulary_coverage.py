"""Coverage map rollups for vocabulary, verbs/conjugation, and grammar."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import UserConjugationProgress, VerbConjugation, VocabularyWord
from app.services.conjugation import CEFR_ORDER, CORE_TENSES, DISPLAY_TENSES
from app.services.glosses import gloss_map, word_gloss

NAILED_RETRIEVABILITY = 0.9
NAILED_MIN_REVIEWS = 2
NAILED_MIN_PROFICIENCY = 90
TEXT_FOLD_TRANSLATION = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "œ": "oe", "æ": "ae"})

VOCAB_TAXONOMY = [
    ("people_relationships", "People & relationships"),
    ("body_health", "Body & health"),
    ("food_drink", "Food & drink"),
    ("home_objects", "Home & objects"),
    ("clothing", "Clothing"),
    ("time_calendar", "Time & calendar"),
    ("transport_travel", "Transport & travel"),
    ("places_infrastructure", "Places & infrastructure"),
    ("nature_weather", "Nature & weather"),
    ("work_money", "Work & money"),
    ("education", "Education"),
    ("technology_media", "Technology & media"),
    ("society_politics", "Society & politics"),
    ("emotions_abstract", "Emotions & abstract"),
    ("arts_leisure", "Arts & leisure"),
    ("communication", "Communication"),
    ("verbs", "Verb lexicon"),
    ("adjectives_adverbs", "Adjectives & adverbs"),
    ("function_words", "Function words"),
    ("uncategorized", "Uncategorized"),
]
TAXONOMY_LABELS = dict(VOCAB_TAXONOMY)
TAXONOMY_ALIASES = {
    "people & relationships": "people_relationships",
    "people": "people_relationships",
    "relationships": "people_relationships",
    "body & health": "body_health",
    "health": "body_health",
    "food & drink": "food_drink",
    "food": "food_drink",
    "drink": "food_drink",
    "home & objects": "home_objects",
    "home": "home_objects",
    "objects": "home_objects",
    "time & calendar": "time_calendar",
    "time": "time_calendar",
    "calendar": "time_calendar",
    "transport & travel": "transport_travel",
    "travel": "transport_travel",
    "transport": "transport_travel",
    "places & infrastructure": "places_infrastructure",
    "places": "places_infrastructure",
    "infrastructure": "places_infrastructure",
    "nature & weather": "nature_weather",
    "nature": "nature_weather",
    "weather": "nature_weather",
    "work & money": "work_money",
    "work": "work_money",
    "money": "work_money",
    "technology & media": "technology_media",
    "technology": "technology_media",
    "media": "technology_media",
    "society & politics": "society_politics",
    "society": "society_politics",
    "politics": "society_politics",
    "emotions & abstract": "emotions_abstract",
    "emotions": "emotions_abstract",
    "abstract": "emotions_abstract",
    "arts & leisure": "arts_leisure",
    "arts": "arts_leisure",
    "leisure": "arts_leisure",
    "verbs": "verbs",
    "verb": "verbs",
    "adjectives": "adjectives_adverbs",
    "adverbs": "adjectives_adverbs",
    "function": "function_words",
    "function words": "function_words",
}
VERB_GRAMMAR_CATEGORIES = {"tenses", "tense", "verbs", "verben", "conditionals", "conditionnel"}
FUNCTION_POS = {"adp", "det", "pron", "conj", "cconj", "sconj", "part", "aux", "interjection"}
FUNCTION_WORDS = {
    "a",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "cette",
    "de",
    "des",
    "du",
    "elle",
    "en",
    "et",
    "il",
    "je",
    "la",
    "le",
    "les",
    "mais",
    "nous",
    "ou",
    "par",
    "pour",
    "que",
    "qui",
    "se",
    "sur",
    "tu",
    "un",
    "une",
    "vous",
}
COMMON_VERBS = {
    "aller",
    "avoir",
    "dire",
    "etre",
    "faire",
    "falloir",
    "mettre",
    "partir",
    "pouvoir",
    "prendre",
    "savoir",
    "tenir",
    "venir",
    "voir",
    "vouloir",
}
CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "people_relationships": {
        "ami",
        "baby",
        "bruder",
        "child",
        "daughter",
        "enfant",
        "familie",
        "famille",
        "father",
        "femme",
        "freund",
        "frau",
        "girl",
        "homme",
        "kind",
        "mann",
        "mere",
        "mutter",
        "person",
        "personne",
        "père",
        "schwester",
        "soeur",
        "son",
    },
    "body_health": {
        "arzt",
        "body",
        "corps",
        "douleur",
        "gesund",
        "hand",
        "health",
        "kopf",
        "krank",
        "main",
        "malade",
        "medecin",
        "médecin",
        "sante",
        "santé",
        "tete",
        "tête",
    },
    "food_drink": {
        "apfel",
        "beer",
        "boire",
        "bread",
        "cafe",
        "café",
        "drink",
        "eau",
        "erdbeere",
        "essen",
        "food",
        "fromage",
        "fruit",
        "kaffee",
        "lait",
        "legume",
        "légume",
        "manger",
        "market",
        "marché",
        "pain",
        "pomme",
        "restaurant",
        "trinken",
        "viande",
        "vin",
        "water",
    },
    "home_objects": {
        "appartement",
        "bed",
        "chaise",
        "door",
        "fenetre",
        "fenêtre",
        "haus",
        "home",
        "house",
        "maison",
        "object",
        "porte",
        "room",
        "stuhl",
        "table",
        "thing",
        "wohnung",
        "zimmer",
    },
    "clothing": {
        "chaussure",
        "chemise",
        "clothes",
        "kleid",
        "manteau",
        "pantalon",
        "robe",
        "schuh",
        "shirt",
        "shoe",
    },
    "time_calendar": {
        "annee",
        "année",
        "calendar",
        "day",
        "demain",
        "gestern",
        "heure",
        "hier",
        "jahr",
        "jour",
        "matin",
        "mois",
        "morgen",
        "month",
        "semaine",
        "soir",
        "temps",
        "time",
        "uhr",
        "week",
    },
    "transport_travel": {
        "arriver",
        "auto",
        "bus",
        "car",
        "gare",
        "metro",
        "métro",
        "partir",
        "reise",
        "station",
        "train",
        "transport",
        "travel",
        "trip",
        "voiture",
        "voyage",
        "zug",
    },
    "places_infrastructure": {
        "bureau",
        "city",
        "ecole",
        "école",
        "hotel",
        "hôtel",
        "office",
        "ort",
        "place",
        "platz",
        "road",
        "rue",
        "stadt",
        "straße",
        "street",
        "ville",
    },
    "nature_weather": {
        "arbre",
        "baum",
        "berg",
        "fleur",
        "flower",
        "mer",
        "montagne",
        "nature",
        "pluie",
        "rain",
        "sea",
        "soleil",
        "sun",
        "tree",
        "wetter",
        "weather",
    },
    "work_money": {
        "argent",
        "arbeit",
        "business",
        "client",
        "company",
        "entreprise",
        "geld",
        "job",
        "money",
        "payer",
        "preis",
        "price",
        "prix",
        "travail",
        "work",
    },
    "education": {
        "apprendre",
        "book",
        "course",
        "cours",
        "ecole",
        "école",
        "education",
        "etudiant",
        "étudiant",
        "frage",
        "learn",
        "lesson",
        "livre",
        "question",
        "schule",
        "student",
    },
    "technology_media": {
        "computer",
        "email",
        "internet",
        "message",
        "ordinateur",
        "phone",
        "site",
        "tech",
        "telephone",
        "téléphone",
    },
    "society_politics": {
        "droit",
        "etat",
        "état",
        "government",
        "gouvernement",
        "law",
        "loi",
        "politics",
        "politique",
        "recht",
        "society",
        "société",
    },
    "emotions_abstract": {
        "aimer",
        "besorgnis",
        "feeling",
        "gefühl",
        "idea",
        "idée",
        "joie",
        "peur",
        "raison",
        "sentiment",
        "unruhe",
        "envie",
    },
    "arts_leisure": {
        "art",
        "danser",
        "film",
        "jeu",
        "kunst",
        "lire",
        "music",
        "musique",
        "spiel",
    },
    "communication": {
        "answer",
        "demander",
        "dire",
        "lettre",
        "message",
        "parler",
        "repondre",
        "répondre",
        "sagen",
        "sprechen",
        "talk",
    },
}


@dataclass(slots=True)
class WordCoverageItem:
    """Dedupe unit for vocabulary map counting."""

    key: str
    word_id: int
    word: str
    category: str
    cefr_band: str
    part_of_speech: str | None
    frequency_rank: int | None
    progress: UserVocabularyProgress | None


def cefr_from_difficulty(value: int | None) -> str:
    return {1: "A1", 2: "A2", 3: "B1", 4: "B2", 5: "C1"}.get(int(value or 1), "A1")


def percent(nailed: int, total: int) -> int:
    return int(round((nailed / total) * 100)) if total else 0


def normalize_category(value: str | None) -> str:
    raw = " ".join(str(value or "").strip().lower().replace("_", " ").split())
    if not raw:
        return "uncategorized"
    return TAXONOMY_ALIASES.get(raw, raw.replace(" ", "_"))


def _folded_text(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    german_folded = raw.translate(TEXT_FOLD_TRANSLATION)
    ascii_folded = unicodedata.normalize("NFKD", german_folded).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9à-öø-ÿ]+", " ", f"{raw} {ascii_folded}")


def _compact_text(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    german_folded = raw.translate(TEXT_FOLD_TRANSLATION)
    ascii_folded = unicodedata.normalize("NFKD", german_folded).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_folded)


def _contains_signal(haystack: str, needle: str) -> bool:
    raw = str(needle or "").strip().lower()
    german_folded = raw.translate(TEXT_FOLD_TRANSLATION)
    ascii_folded = unicodedata.normalize("NFKD", german_folded).encode("ascii", "ignore").decode("ascii")
    variants = {
        re.sub(r"[^a-z0-9à-öø-ÿ]+", " ", value).strip()
        for value in (raw, german_folded, ascii_folded)
        if value
    }
    return any(
        bool(re.search(rf"(^|\s){re.escape(variant)}($|\s)", haystack))
        for variant in variants
        if variant
    )


def _word_haystack(word: VocabularyWord) -> str:
    fields = [
        word.word,
        word.normalized_word,
        word.french_translation,
        word.german_translation,
        word.english_translation,
        word.definition,
    ]
    return _folded_text(" ".join(str(value) for value in fields if value))


#: Surfaces the suffix rule gets wrong, curated from `scripts/audit_pos_heuristic.py`.
POS_OVERRIDES_PATH = Path(__file__).resolve().parents[2] / "app" / "data" / "pos_overrides.json"

#: spaCy's universal tags, folded to the vocabulary we store on the card.
_SPACY_POS_MAP = {
    "verb": "verb",
    "aux": "verb",
    "noun": "noun",
    "propn": "noun",
    "adj": "adjective",
    "adv": "adverb",
    "pron": "function",
    "det": "function",
    "adp": "function",
    "cconj": "function",
    "sconj": "function",
    "part": "function",
    "num": "function",
    "intj": "function",
}


def normalize_pos_tag(value: Any) -> str:
    """One spelling for a part of speech, whatever spelled it.

    The deck's own column, spaCy and the heuristic each have their own names for
    the same thing ("VERB", "v", "verbe"); the card and the coverage map only
    ever want one of them.
    """
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text in _SPACY_POS_MAP:
        return _SPACY_POS_MAP[text]
    if text in {"v", "verbe"}:
        return "verb"
    if text in {"n", "nom", "substantive"}:
        return "noun"
    if text in {"adj", "adjectif", "adjective"}:
        return "adjective"
    if text in {"adverb", "adverbe"}:
        return "adverb"
    return text


def _load_pos_overrides() -> dict[str, str]:
    try:
        payload = json.loads(POS_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    raw = payload.get("overrides") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {}
    resolved: dict[str, str] = {}
    for surface, tag in raw.items():
        normalized = normalize_pos_tag(tag)
        if normalized:
            resolved[str(surface).strip().lower()] = normalized
    return resolved


_POS_OVERRIDES: dict[str, str] | None = None


def pos_overrides() -> dict[str, str]:
    """The curated list, read once. `reload_pos_overrides()` re-reads it."""
    global _POS_OVERRIDES
    if _POS_OVERRIDES is None:
        _POS_OVERRIDES = _load_pos_overrides()
    return _POS_OVERRIDES


def reload_pos_overrides() -> dict[str, str]:
    """Drop the cache — for the audit script and for tests that write the file."""
    global _POS_OVERRIDES
    _POS_OVERRIDES = None
    return pos_overrides()


def heuristic_part_of_speech(word: VocabularyWord) -> str:
    """The suffix guess, on its own.

    Kept separate so `scripts/audit_pos_heuristic.py` can measure exactly this
    rule against a tagger, without the overrides that were derived from it.
    """
    surface = str(getattr(word, "word", None) or getattr(word, "normalized_word", None) or "").strip().lower()
    compact = _compact_text(surface)
    if compact in FUNCTION_WORDS:
        return "function"
    if compact in COMMON_VERBS or (compact.endswith(("er", "ir", "re", "oir")) and len(compact) > 4):
        return "verb"
    if compact.endswith(("able", "ible", "eux", "euse", "if", "ive")):
        return "adjective"
    if compact.endswith(("age", "eur", "euse", "isme", "ment", "tion", "te")):
        return "noun"
    return ""


def inferred_part_of_speech(word: VocabularyWord) -> str:
    """The part of speech shown to a learner, best source first.

    1. the curated override file — the ~11 % the suffix rule gets wrong;
    2. a real tagger's answer, when a caller attached one as `spacy_pos`;
    3. the deck's own `part_of_speech` column, which the Anki import filled;
    4. the suffix heuristic, which is a guess and is treated as one.

    The order matters because step 4 confidently prints `plaisir` and `avenir`
    as verbs, and the review card used to repeat that to the learner.
    """
    surface = str(getattr(word, "word", None) or getattr(word, "normalized_word", None) or "").strip().lower()
    override = pos_overrides().get(surface)
    if override:
        return override

    tagged = normalize_pos_tag(getattr(word, "spacy_pos", None))
    if tagged:
        return tagged

    explicit = normalize_pos_tag(getattr(word, "part_of_speech", None))
    if explicit:
        return explicit

    return heuristic_part_of_speech(word)


def primary_category(word: VocabularyWord) -> str:
    pos = inferred_part_of_speech(word)
    if pos in {"verb", "verbe", "v"}:
        return "verbs"
    if pos in {"adj", "adjective", "adv", "adverb"}:
        return "adjectives_adverbs"
    if pos in FUNCTION_POS or pos in {"function", "pronoun", "determiner", "preposition", "conjunction"}:
        return "function_words"
    for tag in word.topic_tags or []:
        category = normalize_category(tag)
        if category in TAXONOMY_LABELS and category not in {"verbs", "adjectives_adverbs", "function_words"}:
            return category
    haystack = _word_haystack(word)
    for category, needles in CATEGORY_KEYWORDS.items():
        if any(_contains_signal(haystack, needle) for needle in needles):
            return category
    return "uncategorized"


def _retrievability(progress: UserVocabularyProgress | UserConjugationProgress, *, now: datetime) -> float | None:
    stability = progress.stability or getattr(progress, "interval_days", None) or progress.scheduled_days
    last_review = progress.last_review_date
    if not stability or stability <= 0 or last_review is None:
        return None
    if last_review.tzinfo is None:
        last_review = last_review.replace(tzinfo=UTC)
    elapsed_days = max(0.0, (now - last_review).total_seconds() / 86_400)
    decay = -0.5
    factor = 0.9 ** (1 / decay) - 1
    return max(0.0, min(1.0, (1 + factor * elapsed_days / stability) ** decay))


def is_vocab_nailed(progress: UserVocabularyProgress | None, *, now: datetime | None = None) -> bool:
    if progress is None:
        return False
    now = now or datetime.now(UTC)
    state = (progress.state or "").lower()
    if progress.mastered_date or state in {"mastered", "gemeistert"}:
        return True
    if (progress.proficiency_score or 0) >= NAILED_MIN_PROFICIENCY and (progress.reps or 0) >= NAILED_MIN_REVIEWS:
        return True
    retrievability = _retrievability(progress, now=now)
    return bool(
        retrievability is not None
        and retrievability >= NAILED_RETRIEVABILITY
        and (progress.reps or 0) >= NAILED_MIN_REVIEWS
        and (progress.lapses or 0) == 0
    )


def is_conjugation_nailed(progress: UserConjugationProgress | None) -> bool:
    if progress is None:
        return False
    return bool(
        progress.mastered_date
        or (progress.state or "").lower() in {"mastered", "gemeistert"}
        or ((progress.reps or 0) >= NAILED_MIN_REVIEWS and (progress.proficiency_score or 0) >= NAILED_MIN_PROFICIENCY)
    )


def is_grammar_nailed(progress: UserGrammarProgress | None) -> bool:
    if progress is None:
        return False
    return (progress.state or "").lower() in {"gemeistert", "mastered"} or (progress.score or 0) >= 8.5


class VocabularyCoverageService:
    """Build the three-axis learner coverage map."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def coverage(self, *, user: User) -> dict[str, Any]:
        now = datetime.now(UTC)
        words = self._word_items(user=user)
        categories = self._category_rollups(words=words, now=now)
        verb_lexicon = self._verb_lexicon_rollup(words=words, now=now)
        grammar_patterns = self._grammar_rollups(user_id=user.id, verb_only=True)
        grammar_tracks = self._grammar_rollups(user_id=user.id, verb_only=False)
        irregulars = self._irregular_rollup(user_id=user.id)
        cefr_bar = self._cefr_rollup(words=words, grammar_tracks=grammar_patterns + grammar_tracks, irregulars=irregulars, now=now)
        next_best = self._next_best_set(categories=categories, verb_lexicon=verb_lexicon, irregulars=irregulars)
        return {
            "cefr_bar": cefr_bar,
            "categories": categories,
            "verb_tracks": [verb_lexicon, grammar_patterns[0], irregulars] if grammar_patterns else [verb_lexicon, irregulars],
            "grammar_tracks": grammar_tracks,
            "next_best_set": next_best,
            "nailed_rule": {
                "retrievability": NAILED_RETRIEVABILITY,
                "min_reviews": NAILED_MIN_REVIEWS,
                "min_proficiency": NAILED_MIN_PROFICIENCY,
            },
        }

    def recently_nailed_vocabulary(
        self,
        *,
        user: User,
        limit: int = 6,
        category: str | None = None,
        include_due: bool = True,
    ) -> list[dict[str, Any]]:
        """Return words the learner just nailed, plus a few due words if requested."""

        now = datetime.now(UTC)
        target_language = (user.target_language or "fr").strip() or "fr"
        query = (
            self.db.query(UserVocabularyProgress, VocabularyWord)
            .join(VocabularyWord, UserVocabularyProgress.word_id == VocabularyWord.id)
            .filter(UserVocabularyProgress.user_id == user.id, VocabularyWord.language == target_language)
            .filter(or_(VocabularyWord.direction == "fr_to_de", VocabularyWord.direction.is_(None)))
            .order_by(
                UserVocabularyProgress.mastered_date.desc().nullslast(),
                UserVocabularyProgress.last_review_date.desc().nullslast(),
                VocabularyWord.frequency_rank.asc().nullslast(),
            )
            .limit(max(limit * 6, 24))
        )
        selected: list[dict[str, Any]] = []
        seen: set[int] = set()
        wanted_category = normalize_category(category) if category else None
        for progress, word in query.all():
            word_category = primary_category(word)
            if wanted_category and word_category != wanted_category:
                continue
            due = self._is_due(progress, now=now)
            if not is_vocab_nailed(progress, now=now) and not (include_due and due):
                continue
            if word.id in seen:
                continue
            selected.append(self._serialize_word(
                    word,
                    progress,
                    "recently_nailed" if is_vocab_nailed(progress, now=now) else "due",
                    user.native_language,
                ))
            seen.add(word.id)
            if len(selected) >= limit:
                break
        return selected

    def _word_items(self, *, user: User) -> list[WordCoverageItem]:
        target_language = (user.target_language or "fr").strip() or "fr"
        progress_by_word = {
            progress.word_id: progress
            for progress in self.db.query(UserVocabularyProgress).filter(UserVocabularyProgress.user_id == user.id).all()
        }
        query = (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.language == target_language)
            .filter(VocabularyWord.is_anki_card.is_(True))
            .filter(or_(VocabularyWord.direction == "fr_to_de", VocabularyWord.direction.is_(None)))
            .order_by(VocabularyWord.frequency_rank.asc().nullslast(), VocabularyWord.id.asc())
        )
        deduped: dict[str, WordCoverageItem] = {}
        for word in query.all():
            key = _compact_text(word.word) or _compact_text(word.normalized_word) or str(word.id)
            if not key:
                key = str(word.id)
            item = WordCoverageItem(
                key=key,
                word_id=word.id,
                word=word.word,
                category=primary_category(word),
                cefr_band=cefr_from_difficulty(word.difficulty_level),
                part_of_speech=inferred_part_of_speech(word) or word.part_of_speech,
                frequency_rank=word.frequency_rank,
                progress=progress_by_word.get(word.id),
            )
            if key not in deduped:
                deduped[key] = item
                continue
            existing = deduped[key]
            existing_rank = existing.frequency_rank or 999999
            next_rank = item.frequency_rank or 999999
            if next_rank < existing_rank:
                deduped[key] = item
        return list(deduped.values())

    def _category_rollups(self, *, words: list[WordCoverageItem], now: datetime) -> list[dict[str, Any]]:
        bucket: dict[str, list[WordCoverageItem]] = defaultdict(list)
        for item in words:
            if item.category in {"verbs", "uncategorized"}:
                continue
            bucket[item.category].append(item)
        rollups: list[dict[str, Any]] = []
        for category, label in VOCAB_TAXONOMY:
            if category in {"verbs", "uncategorized"}:
                continue
            rows = bucket.get(category, [])
            if not rows:
                continue
            nailed = sum(1 for row in rows if is_vocab_nailed(row.progress, now=now))
            by_band = self._bands_for_words(rows, now=now)
            rollups.append(
                {
                    "id": category,
                    "label": label,
                    "track": "vocabulary",
                    "nailed": nailed,
                    "total": len(rows),
                    "percent": percent(nailed, len(rows)),
                    "cefr_bands": by_band,
                    "example_words": [row.word for row in rows[:5]],
                    "href": f"/vocabulary?category={category}",
                }
            )
        rollups.sort(key=lambda item: (item["percent"], -item["total"], item["label"]))
        return rollups

    def _verb_lexicon_rollup(self, *, words: list[WordCoverageItem], now: datetime) -> dict[str, Any]:
        verbs = [row for row in words if row.category == "verbs"]
        nailed = sum(1 for row in verbs if is_vocab_nailed(row.progress, now=now))
        return {
            "id": "verb_lexicon",
            "label": "Verb lexicon",
            "track": "verbs",
            "unit": "verb meanings",
            "nailed": nailed,
            "total": len(verbs),
            "percent": percent(nailed, len(verbs)),
            "cefr_bands": self._bands_for_words(verbs, now=now),
            "href": "/vocabulary?category=verbs",
        }

    def _grammar_rollups(self, *, user_id: UUID, verb_only: bool) -> list[dict[str, Any]]:
        progress_by_concept = {
            progress.concept_id: progress
            for progress in self.db.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user_id).all()
        }
        concepts = (
            self.db.query(GrammarConcept)
            .filter(GrammarConcept.active.is_(True), GrammarConcept.language == "fr")
            .order_by(GrammarConcept.level.asc(), GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
            .all()
        )

        def is_verb_concept(concept: GrammarConcept) -> bool:
            marker = " ".join(
                str(value or "").lower()
                for value in (concept.category, concept.subskill, concept.name, concept.external_id)
            )
            return any(token in marker for token in VERB_GRAMMAR_CATEGORIES) or any(
                token in marker
                for token in ("passé", "compose", "imparfait", "futur", "conditionnel", "subjonctif", "présent")
            )

        filtered = [concept for concept in concepts if is_verb_concept(concept) == verb_only]
        if verb_only:
            total = len(filtered)
            nailed = sum(1 for concept in filtered if is_grammar_nailed(progress_by_concept.get(concept.id)))
            return [
                {
                    "id": "conjugation_patterns",
                    "label": "Conjugation patterns",
                    "track": "verbs",
                    "unit": "grammar concepts",
                    "nailed": nailed,
                    "total": total,
                    "percent": percent(nailed, total),
                    "cefr_bands": self._bands_for_grammar(filtered, progress_by_concept),
                    "href": "/grammar?track=verbs",
                    "auto_credits_regular_verbs": True,
                }
            ]

        by_category: dict[str, list[GrammarConcept]] = defaultdict(list)
        for concept in filtered:
            by_category[concept.category or "Grammar"].append(concept)
        rollups: list[dict[str, Any]] = []
        for category, rows in by_category.items():
            nailed = sum(1 for concept in rows if is_grammar_nailed(progress_by_concept.get(concept.id)))
            rollups.append(
                {
                    "id": normalize_category(category),
                    "label": category,
                    "track": "grammar",
                    "unit": "concepts",
                    "nailed": nailed,
                    "total": len(rows),
                    "percent": percent(nailed, len(rows)),
                    "cefr_bands": self._bands_for_grammar(rows, progress_by_concept),
                    "href": f"/grammar?category={category}",
                }
            )
        rollups.sort(key=lambda item: (item["percent"], item["label"]))
        return rollups

    def _irregular_rollup(self, *, user_id: UUID) -> dict[str, Any]:
        targets = (
            self.db.query(VerbConjugation.normalized_lemma, VerbConjugation.lemma, VerbConjugation.tense, VerbConjugation.cefr_band)
            .filter(VerbConjugation.is_irregular.is_(True))
            .group_by(VerbConjugation.normalized_lemma, VerbConjugation.lemma, VerbConjugation.tense, VerbConjugation.cefr_band)
            .all()
        )
        progress_by_key = {
            (progress.normalized_lemma, progress.tense): progress
            for progress in self.db.query(UserConjugationProgress).filter(UserConjugationProgress.user_id == user_id).all()
        }
        nailed = sum(1 for normalized, _lemma, tense, _band in targets if is_conjugation_nailed(progress_by_key.get((normalized, tense))))
        bands: dict[str, dict[str, int]] = defaultdict(lambda: {"nailed": 0, "total": 0})
        for normalized, _lemma, tense, band in targets:
            key = band or "A1"
            bands[key]["total"] += 1
            if is_conjugation_nailed(progress_by_key.get((normalized, tense))):
                bands[key]["nailed"] += 1
        return {
            "id": "irregular_forms",
            "label": "Irregular forms",
            "track": "verbs",
            "unit": "verb x tense drills",
            "nailed": nailed,
            "total": len(targets),
            "percent": percent(nailed, len(targets)),
            "cefr_bands": self._serialize_bands(bands),
            "href": "/vocabulary/conjugation",
            "tenses": [DISPLAY_TENSES.get(tense, tense) for tense in CORE_TENSES],
        }

    def _cefr_rollup(
        self,
        *,
        words: list[WordCoverageItem],
        grammar_tracks: list[dict[str, Any]],
        irregulars: dict[str, Any],
        now: datetime,
    ) -> list[dict[str, Any]]:
        bands: dict[str, dict[str, int]] = defaultdict(lambda: {"nailed": 0, "total": 0})
        for word in words:
            bands[word.cefr_band]["total"] += 1
            if is_vocab_nailed(word.progress, now=now):
                bands[word.cefr_band]["nailed"] += 1
        for track in grammar_tracks + [irregulars]:
            for band in track.get("cefr_bands") or []:
                bands[band["band"]]["total"] += int(band.get("total") or 0)
                bands[band["band"]]["nailed"] += int(band.get("nailed") or 0)
        return [
            {
                "band": band,
                "label": band,
                "nailed": values["nailed"],
                "total": values["total"],
                "percent": percent(values["nailed"], values["total"]),
            }
            for band, values in sorted(bands.items(), key=lambda item: CEFR_ORDER.get(item[0], 99))
            if values["total"] > 0
        ]

    def _bands_for_words(self, rows: list[WordCoverageItem], *, now: datetime) -> list[dict[str, Any]]:
        bands: dict[str, dict[str, int]] = defaultdict(lambda: {"nailed": 0, "total": 0})
        for row in rows:
            bands[row.cefr_band]["total"] += 1
            if is_vocab_nailed(row.progress, now=now):
                bands[row.cefr_band]["nailed"] += 1
        return self._serialize_bands(bands)

    def _bands_for_grammar(
        self,
        concepts: list[GrammarConcept],
        progress_by_concept: dict[int, UserGrammarProgress],
    ) -> list[dict[str, Any]]:
        bands: dict[str, dict[str, int]] = defaultdict(lambda: {"nailed": 0, "total": 0})
        for concept in concepts:
            band = concept.level or "A1"
            bands[band]["total"] += 1
            if is_grammar_nailed(progress_by_concept.get(concept.id)):
                bands[band]["nailed"] += 1
        return self._serialize_bands(bands)

    @staticmethod
    def _serialize_bands(bands: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
        return [
            {
                "band": band,
                "nailed": values["nailed"],
                "total": values["total"],
                "percent": percent(values["nailed"], values["total"]),
            }
            for band, values in sorted(bands.items(), key=lambda item: CEFR_ORDER.get(item[0], 99))
            if values["total"] > 0
        ]

    @staticmethod
    def _next_best_set(
        *,
        categories: list[dict[str, Any]],
        verb_lexicon: dict[str, Any],
        irregulars: dict[str, Any],
    ) -> dict[str, Any]:
        candidates = [item for item in categories if item["total"] > item["nailed"]]
        if verb_lexicon["total"] > verb_lexicon["nailed"]:
            candidates.append(verb_lexicon)
        if irregulars["total"] > irregulars["nailed"]:
            candidates.append(irregulars)
        if not candidates:
            return {
                "kind": "complete",
                "label": "Coverage map complete",
                "href": "/missions",
                "reason": "All current targets are nailed.",
            }
        candidates.sort(key=lambda item: (item["percent"], -item["total"], item["label"]))
        pick = candidates[0]
        return {
            "kind": pick.get("track", "vocabulary"),
            "id": pick["id"],
            "label": pick["label"],
            "href": pick.get("href") or "/vocabulary/review",
            "nailed": pick["nailed"],
            "total": pick["total"],
            "percent": pick["percent"],
            "reason": "Lowest mastered share among available targets.",
        }

    @staticmethod
    def _is_due(progress: UserVocabularyProgress, *, now: datetime) -> bool:
        def aware(value: datetime | None) -> datetime | None:
            if value is None:
                return None
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        due_at = aware(progress.due_at)
        next_review = aware(progress.next_review_date)
        if due_at and due_at <= now:
            return True
        if next_review and next_review <= now:
            return True
        return bool(progress.due_date and progress.due_date <= now.date())

    @staticmethod
    def _serialize_word(
        word: VocabularyWord,
        progress: UserVocabularyProgress | None,
        bucket: str,
        native_language: str | None = None,
    ) -> dict[str, Any]:
        return {
            "bucket": bucket,
            "word_id": word.id,
            "word": word.word,
            "translation": word_gloss(word, native_language),
            "language": word.language,
            "direction": word.direction,
            "part_of_speech": word.part_of_speech,
            "topic_tags": word.topic_tags or [],
            "scheduler": progress.scheduler if progress else ("anki" if word.is_anki_card else "fsrs"),
            "state": progress.state if progress else "new",
            "phase": progress.phase if progress else None,
            "due_at": progress.due_at if progress else None,
            "next_review": progress.next_review_date if progress else None,
            "proficiency_score": progress.proficiency_score if progress else 0,
            "priority_score": 120 if bucket == "recently_nailed" else 80,
            "is_new": progress is None,
            "deck_name": word.deck_name,
            "translations": gloss_map(word),
            "example_sentence": word.example_sentence,
            "example_translation": word.example_translation,
        }


__all__ = [
    "VOCAB_TAXONOMY",
    "VocabularyCoverageService",
    "is_conjugation_nailed",
    "is_grammar_nailed",
    "is_vocab_nailed",
    "primary_category",
    "normalize_category",
]
