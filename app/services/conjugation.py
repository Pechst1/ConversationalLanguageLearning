"""Conjugation data generation, review queues, and SRS credit."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.vocabulary import UserConjugationProgress, VerbConjugation, VocabularyWord
from app.services.srs import FSRSScheduler, SchedulerState


CORE_TENSES = [
    "present",
    "passe_compose",
    "imparfait",
    "futur_simple",
    "conditionnel_present",
    "subjonctif_present",
    "imperatif",
]
DISPLAY_TENSES = {
    "present": "présent",
    "passe_compose": "passé composé",
    "imparfait": "imparfait",
    "futur_simple": "futur simple",
    "conditionnel_present": "conditionnel présent",
    "subjonctif_present": "subjonctif présent",
    "imperatif": "impératif",
}
PERSONS = ["je", "tu", "il/elle", "nous", "vous", "ils/elles"]
IMPERATIVE_PERSONS = ["tu", "nous", "vous"]
CEFR_BAND_BY_DIFFICULTY = {1: "A1", 2: "A2", 3: "B1", 4: "B2", 5: "C1"}
CEFR_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}

ESSENTIAL_IRREGULARS: dict[str, str] = {
    "être": "A1",
    "avoir": "A1",
    "aller": "A1",
    "faire": "A1",
    "venir": "A2",
    "vouloir": "A2",
    "pouvoir": "A2",
    "devoir": "A2",
    "prendre": "A2",
    "voir": "A2",
    "savoir": "B1",
    "dire": "B1",
    "mettre": "B1",
    "sortir": "B1",
    "partir": "B1",
    "tenir": "B1",
    "recevoir": "B1",
    "falloir": "B1",
    "croire": "B2",
    "vivre": "B2",
    "connaître": "B2",
    "naître": "B2",
    "mourir": "B2",
    "écrire": "B2",
}

IRREGULAR_PRESENT: dict[str, list[str]] = {
    "être": ["suis", "es", "est", "sommes", "êtes", "sont"],
    "avoir": ["ai", "as", "a", "avons", "avez", "ont"],
    "aller": ["vais", "vas", "va", "allons", "allez", "vont"],
    "faire": ["fais", "fais", "fait", "faisons", "faites", "font"],
    "venir": ["viens", "viens", "vient", "venons", "venez", "viennent"],
    "vouloir": ["veux", "veux", "veut", "voulons", "voulez", "veulent"],
    "pouvoir": ["peux", "peux", "peut", "pouvons", "pouvez", "peuvent"],
    "devoir": ["dois", "dois", "doit", "devons", "devez", "doivent"],
    "prendre": ["prends", "prends", "prend", "prenons", "prenez", "prennent"],
    "voir": ["vois", "vois", "voit", "voyons", "voyez", "voient"],
    "savoir": ["sais", "sais", "sait", "savons", "savez", "savent"],
    "dire": ["dis", "dis", "dit", "disons", "dites", "disent"],
    "mettre": ["mets", "mets", "met", "mettons", "mettez", "mettent"],
    "sortir": ["sors", "sors", "sort", "sortons", "sortez", "sortent"],
    "partir": ["pars", "pars", "part", "partons", "partez", "partent"],
    "tenir": ["tiens", "tiens", "tient", "tenons", "tenez", "tiennent"],
    "recevoir": ["reçois", "reçois", "reçoit", "recevons", "recevez", "reçoivent"],
    "falloir": ["faut", "faut", "faut", "faut", "faut", "faut"],
    "croire": ["crois", "crois", "croit", "croyons", "croyez", "croient"],
    "vivre": ["vis", "vis", "vit", "vivons", "vivez", "vivent"],
    "connaître": ["connais", "connais", "connaît", "connaissons", "connaissez", "connaissent"],
    "naître": ["nais", "nais", "naît", "naissons", "naissez", "naissent"],
    "mourir": ["meurs", "meurs", "meurt", "mourons", "mourez", "meurent"],
    "écrire": ["écris", "écris", "écrit", "écrivons", "écrivez", "écrivent"],
}

IRREGULAR_FUTURE_STEMS = {
    "être": "ser",
    "avoir": "aur",
    "aller": "ir",
    "faire": "fer",
    "venir": "viendr",
    "vouloir": "voudr",
    "pouvoir": "pourr",
    "devoir": "devr",
    "savoir": "saur",
    "voir": "verr",
    "recevoir": "recevr",
    "falloir": "faudr",
    "tenir": "tiendr",
    "mourir": "mourr",
}
IRREGULAR_PAST_PARTICIPLES = {
    "être": "été",
    "avoir": "eu",
    "aller": "allé",
    "faire": "fait",
    "venir": "venu",
    "vouloir": "voulu",
    "pouvoir": "pu",
    "devoir": "dû",
    "prendre": "pris",
    "voir": "vu",
    "savoir": "su",
    "dire": "dit",
    "mettre": "mis",
    "sortir": "sorti",
    "partir": "parti",
    "tenir": "tenu",
    "recevoir": "reçu",
    "falloir": "fallu",
    "croire": "cru",
    "vivre": "vécu",
    "connaître": "connu",
    "naître": "né",
    "mourir": "mort",
    "écrire": "écrit",
}
ETRE_AUXILIARY_VERBS = {"aller", "venir", "sortir", "partir", "naître", "mourir"}


@dataclass(slots=True)
class ConjugationReviewItem:
    """One conjugation SRS prompt."""

    lemma: str
    tense: str
    person: str
    answer: str
    cefr_band: str
    is_irregular: bool
    progress_id: str | None
    state: str
    reps: int
    lapses: int
    due_at: datetime | None
    table: list[dict[str, Any]]


def normalize_lemma(value: str | None) -> str:
    """Normalize a French verb lemma for joins and cache keys."""

    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_text)


CANONICAL_LEMMAS_BY_NORMALIZED = {
    normalize_lemma(lemma): lemma
    for lemma in set(ESSENTIAL_IRREGULARS)
    | set(IRREGULAR_PRESENT)
    | set(IRREGULAR_FUTURE_STEMS)
    | set(IRREGULAR_PAST_PARTICIPLES)
    | ETRE_AUXILIARY_VERBS
}


def canonicalize_lemma(value: str | None) -> str:
    """Return the accent-preserving lemma for known irregulars."""

    raw = str(value or "").strip().lower()
    normalized = normalize_lemma(raw)
    if not normalized:
        return ""
    return CANONICAL_LEMMAS_BY_NORMALIZED.get(normalized, raw)


def cefr_for_difficulty(value: int | None) -> str:
    return CEFR_BAND_BY_DIFFICULTY.get(int(value or 1), "A1")


def verb_group(lemma: str) -> str:
    if lemma.endswith("er"):
        return "-er"
    if lemma.endswith("ir"):
        return "-ir"
    if lemma.endswith("re"):
        return "-re"
    if lemma.endswith("oir"):
        return "-oir"
    return "other"


def is_irregular_verb(lemma: str) -> bool:
    lemma = canonicalize_lemma(lemma)
    return lemma in ESSENTIAL_IRREGULARS or lemma in IRREGULAR_PRESENT


def auxiliary_for(lemma: str) -> str:
    lemma = canonicalize_lemma(lemma)
    return "être" if lemma in ETRE_AUXILIARY_VERBS else "avoir"


def _regular_present(lemma: str) -> list[str]:
    if lemma.endswith("er"):
        stem = lemma[:-2]
        return [f"{stem}e", f"{stem}es", f"{stem}e", f"{stem}ons", f"{stem}ez", f"{stem}ent"]
    if lemma.endswith("ir"):
        stem = lemma[:-2]
        return [f"{stem}is", f"{stem}is", f"{stem}it", f"{stem}issons", f"{stem}issez", f"{stem}issent"]
    if lemma.endswith("re"):
        stem = lemma[:-2]
        return [f"{stem}s", f"{stem}s", stem, f"{stem}ons", f"{stem}ez", f"{stem}ent"]
    return [lemma for _ in PERSONS]


def _future_stem(lemma: str) -> str:
    if lemma in IRREGULAR_FUTURE_STEMS:
        return IRREGULAR_FUTURE_STEMS[lemma]
    if lemma.endswith("re"):
        return lemma[:-1]
    return lemma


def _past_participle(lemma: str) -> str:
    if lemma in IRREGULAR_PAST_PARTICIPLES:
        return IRREGULAR_PAST_PARTICIPLES[lemma]
    if lemma.endswith("er"):
        return f"{lemma[:-2]}é"
    if lemma.endswith("ir"):
        return f"{lemma[:-2]}i"
    if lemma.endswith("re"):
        return f"{lemma[:-2]}u"
    return lemma


def _present_forms(lemma: str) -> list[str]:
    return IRREGULAR_PRESENT.get(lemma) or _regular_present(lemma)


def _imparfait_forms(lemma: str) -> list[str]:
    if lemma == "être":
        stem = "ét"
    else:
        stem = _present_forms(lemma)[3]
        stem = stem[:-3] if stem.endswith("ons") else stem
    return [f"{stem}ais", f"{stem}ais", f"{stem}ait", f"{stem}ions", f"{stem}iez", f"{stem}aient"]


def _future_forms(lemma: str, *, conditional: bool = False) -> list[str]:
    stem = _future_stem(lemma)
    endings = ["ais", "ais", "ait", "ions", "iez", "aient"] if conditional else ["ai", "as", "a", "ons", "ez", "ont"]
    return [f"{stem}{ending}" for ending in endings]


def _subjunctive_forms(lemma: str) -> list[str]:
    overrides = {
        "être": ["sois", "sois", "soit", "soyons", "soyez", "soient"],
        "avoir": ["aie", "aies", "ait", "ayons", "ayez", "aient"],
        "aller": ["aille", "ailles", "aille", "allions", "alliez", "aillent"],
        "faire": ["fasse", "fasses", "fasse", "fassions", "fassiez", "fassent"],
        "pouvoir": ["puisse", "puisses", "puisse", "puissions", "puissiez", "puissent"],
        "savoir": ["sache", "saches", "sache", "sachions", "sachiez", "sachent"],
        "vouloir": ["veuille", "veuilles", "veuille", "voulions", "vouliez", "veuillent"],
    }
    if lemma in overrides:
        return overrides[lemma]
    present = _present_forms(lemma)
    plural_stem = present[5][:-3] if present[5].endswith("ent") else lemma
    nous_stem = present[3][:-3] if present[3].endswith("ons") else plural_stem
    return [
        f"{plural_stem}e",
        f"{plural_stem}es",
        f"{plural_stem}e",
        f"{nous_stem}ions",
        f"{nous_stem}iez",
        f"{plural_stem}ent",
    ]


def _passe_compose_forms(lemma: str) -> list[str]:
    aux = auxiliary_for(lemma)
    aux_forms = IRREGULAR_PRESENT[aux]
    participle = _past_participle(lemma)
    return [f"{aux_form} {participle}" for aux_form in aux_forms]


def _imperative_forms(lemma: str) -> list[str]:
    present = _present_forms(lemma)
    if lemma == "être":
        return ["sois", "soyons", "soyez"]
    if lemma == "avoir":
        return ["aie", "ayons", "ayez"]
    tu_form = present[1]
    if lemma.endswith("er") and tu_form.endswith("s"):
        tu_form = tu_form[:-1]
    return [tu_form, present[3], present[4]]


def fallback_conjugation_table(lemma: str) -> dict[str, dict[str, str]]:
    """Generate a deterministic French conjugation table without external services."""

    return {
        "present": dict(zip(PERSONS, _present_forms(lemma), strict=False)),
        "passe_compose": dict(zip(PERSONS, _passe_compose_forms(lemma), strict=False)),
        "imparfait": dict(zip(PERSONS, _imparfait_forms(lemma), strict=False)),
        "futur_simple": dict(zip(PERSONS, _future_forms(lemma), strict=False)),
        "conditionnel_present": dict(zip(PERSONS, _future_forms(lemma, conditional=True), strict=False)),
        "subjonctif_present": dict(zip(PERSONS, _subjunctive_forms(lemma), strict=False)),
        "imperatif": dict(zip(IMPERATIVE_PERSONS, _imperative_forms(lemma), strict=False)),
    }


def mlconjug_table(lemma: str) -> dict[str, dict[str, str]] | None:
    """Return forms from mlconjug3 when installed; fall back if its API changes."""

    try:
        import mlconjug3  # type: ignore[import-not-found]
    except Exception:
        return None

    try:
        conjugator = mlconjug3.Conjugator(language="fr")
        verb = conjugator.conjugate(lemma)
    except Exception:
        return None

    table = fallback_conjugation_table(lemma)
    try:
        conjug_info = getattr(verb, "conjug_info", None) or {}
        mapping = {
            ("Indicatif", "Présent"): "present",
            ("Indicatif", "Imparfait"): "imparfait",
            ("Indicatif", "Futur Simple"): "futur_simple",
            ("Conditionnel", "Présent"): "conditionnel_present",
            ("Subjonctif", "Présent"): "subjonctif_present",
            ("Impératif", "Impératif Présent"): "imperatif",
        }
        for (mood, tense_label), tense_key in mapping.items():
            raw_forms = ((conjug_info.get(mood) or {}).get(tense_label) or {})
            if not raw_forms:
                continue
            persons = IMPERATIVE_PERSONS if tense_key == "imperatif" else PERSONS
            extracted: dict[str, str] = {}
            for person in persons:
                candidates = [
                    person,
                    person.replace("il/elle", "il (elle)"),
                    person.replace("ils/elles", "ils (elles)"),
                ]
                for candidate in candidates:
                    if raw_forms.get(candidate):
                        extracted[person] = str(raw_forms[candidate])
                        break
            if extracted:
                table[tense_key] = {**table[tense_key], **extracted}
    except Exception:
        return table
    return table


def build_conjugation_rows(
    lemma: str,
    *,
    cefr_band: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Build normalized rows ready for upsert into ``verb_conjugations``."""

    lemma = canonicalize_lemma(lemma)
    normalized = normalize_lemma(lemma)
    if not lemma or not normalized:
        return []
    table = mlconjug_table(lemma)
    row_source = "mlconjug3" if table else "deterministic"
    table = table or fallback_conjugation_table(lemma)
    cefr = cefr_band or ESSENTIAL_IRREGULARS.get(lemma) or "A1"
    irregular = is_irregular_verb(lemma)
    rows: list[dict[str, Any]] = []
    for tense in CORE_TENSES:
        tense_forms = table.get(tense) or {}
        for person, form in tense_forms.items():
            cleaned = " ".join(str(form or "").split())
            if not cleaned:
                continue
            rows.append(
                {
                    "lemma": lemma,
                    "normalized_lemma": normalized,
                    "tense": tense,
                    "person": person,
                    "form": cleaned,
                    "auxiliary": auxiliary_for(lemma),
                    "verb_group": verb_group(lemma),
                    "regularity": "irregular" if irregular else "regular",
                    "is_irregular": irregular,
                    "cefr_band": cefr,
                    "source": source or row_source,
                    "forms_payload": {"display_tense": DISPLAY_TENSES.get(tense, tense)},
                }
            )
    return rows


def upsert_conjugation_rows(db: Session, rows: list[dict[str, Any]]) -> int:
    """Idempotently insert/update conjugation rows."""

    changed = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        existing = (
            db.query(VerbConjugation)
            .filter(
                VerbConjugation.normalized_lemma == row["normalized_lemma"],
                VerbConjugation.tense == row["tense"],
                VerbConjugation.person == row["person"],
            )
            .first()
        )
        if existing:
            for key, value in row.items():
                setattr(existing, key, value)
            existing.updated_at = now
        else:
            db.add(VerbConjugation(**row))
        changed += 1
    return changed


class ConjugationService:
    """Queue and review service for irregular verb conjugation drills."""

    def __init__(self, db: Session, *, scheduler: FSRSScheduler | None = None) -> None:
        self.db = db
        self.scheduler = scheduler or FSRSScheduler(maximum_interval_days=365)

    def seed_essential_irregulars(self) -> int:
        """Ensure the curated essential irregular rows exist."""

        changed = 0
        for lemma, cefr in ESSENTIAL_IRREGULARS.items():
            changed += upsert_conjugation_rows(self.db, build_conjugation_rows(lemma, cefr_band=cefr))
        return changed

    def ensure_verb_rows_from_vocabulary(self, *, limit: int | None = None) -> int:
        """Generate conjugation rows for enriched vocabulary verbs."""

        query = (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.language == "fr")
            .filter(or_(VocabularyWord.direction == "fr_to_de", VocabularyWord.direction.is_(None)))
            .filter(func.lower(func.coalesce(VocabularyWord.part_of_speech, "")).in_(["verb", "verbe"]))
            .order_by(VocabularyWord.frequency_rank.asc().nullslast(), VocabularyWord.id.asc())
        )
        if limit:
            query = query.limit(limit)
        seen: set[str] = set()
        changed = 0
        for word in query.all():
            lemma = canonicalize_lemma(word.word or word.normalized_word)
            normalized = normalize_lemma(lemma)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            changed += upsert_conjugation_rows(
                self.db,
                build_conjugation_rows(lemma, cefr_band=cefr_for_difficulty(word.difficulty_level)),
            )
        return changed

    def review_queue(
        self,
        *,
        user: User,
        limit: int = 12,
        cefr_band: str | None = None,
        include_new: bool = True,
    ) -> list[dict[str, Any]]:
        """Return due irregular verb x tense prompts."""

        now = datetime.now(timezone.utc)
        allowed_bands = self._allowed_cefr_bands(cefr_band)
        due_query = (
            self.db.query(UserConjugationProgress)
            .filter(UserConjugationProgress.user_id == user.id)
            .filter(
                or_(
                    UserConjugationProgress.next_review_date <= now,
                    UserConjugationProgress.due_date <= now.date(),
                    UserConjugationProgress.next_review_date.is_(None),
                )
            )
            .order_by(
                UserConjugationProgress.next_review_date.asc().nullsfirst(),
                UserConjugationProgress.lapses.desc(),
                UserConjugationProgress.created_at.asc(),
            )
        )
        if allowed_bands:
            due_query = due_query.filter(UserConjugationProgress.cefr_band.in_(allowed_bands))
        due_query = due_query.limit(limit)
        due_rows = due_query.all()
        items = [self._serialize_progress_item(row) for row in due_rows]
        if len(items) >= limit or not include_new:
            return items[:limit]

        existing = select(UserConjugationProgress.normalized_lemma, UserConjugationProgress.tense).where(
            UserConjugationProgress.user_id == user.id
        )
        existing_keys = {(row[0], row[1]) for row in self.db.execute(existing)}
        query = (
            self.db.query(VerbConjugation.normalized_lemma, VerbConjugation.lemma, VerbConjugation.tense, VerbConjugation.cefr_band)
            .filter(VerbConjugation.is_irregular.is_(True))
            .group_by(VerbConjugation.normalized_lemma, VerbConjugation.lemma, VerbConjugation.tense, VerbConjugation.cefr_band)
            .order_by(VerbConjugation.cefr_band.asc(), VerbConjugation.lemma.asc(), VerbConjugation.tense.asc())
        )
        if allowed_bands:
            query = query.filter(VerbConjugation.cefr_band.in_(allowed_bands))
        query = query.limit(max(limit * 4, 24))

        for normalized, lemma, tense, band in query.all():
            if (normalized, tense) in existing_keys:
                continue
            progress = UserConjugationProgress(
                user_id=user.id,
                verb_lemma=lemma,
                normalized_lemma=normalized,
                tense=tense,
                cefr_band=band,
                state="new",
            )
            items.append(self._serialize_progress_item(progress))
            if len(items) >= limit:
                break
        return items[:limit]

    def review(
        self,
        *,
        user: User,
        lemma: str,
        tense: str,
        rating: int,
        response_time_ms: int | None = None,
    ) -> UserConjugationProgress:
        """Apply an FSRS review to one verb x tense item."""

        if rating < 0 or rating > 3:
            raise ValueError("rating must be between 0 and 3")
        lemma = canonicalize_lemma(lemma)
        normalized = normalize_lemma(lemma)
        if not normalized or tense not in CORE_TENSES:
            raise ValueError("unknown conjugation item")

        progress = (
            self.db.query(UserConjugationProgress)
            .filter(
                UserConjugationProgress.user_id == user.id,
                UserConjugationProgress.normalized_lemma == normalized,
                UserConjugationProgress.tense == tense,
            )
            .first()
        )
        if progress is None:
            row = (
                self.db.query(VerbConjugation)
                .filter(VerbConjugation.normalized_lemma == normalized, VerbConjugation.tense == tense)
                .first()
            )
            progress = UserConjugationProgress(
                user_id=user.id,
                verb_lemma=row.lemma if row else lemma,
                normalized_lemma=normalized,
                tense=tense,
                cefr_band=row.cefr_band if row else ESSENTIAL_IRREGULARS.get(lemma, "A1"),
                state="new",
            )
            self.db.add(progress)
            self.db.flush([progress])

        now = datetime.now(timezone.utc)
        outcome = self.scheduler.review(
            state=SchedulerState(
                stability=progress.stability or 0.0,
                difficulty=progress.difficulty or 5.0,
                reps=progress.reps or 0,
                lapses=progress.lapses or 0,
                scheduled_days=progress.scheduled_days or 1,
                state=progress.state or "new",
            ),
            rating=rating,
            last_review_at=progress.last_review_date,
            now=now,
        )
        progress.stability = outcome.stability
        progress.difficulty = outcome.difficulty
        progress.elapsed_days = outcome.elapsed_days
        progress.scheduled_days = outcome.scheduled_days
        progress.state = outcome.state
        progress.reps = (progress.reps or 0) + 1
        if rating <= 1:
            progress.lapses = (progress.lapses or 0) + 1
        progress.last_review_date = now
        progress.next_review_date = outcome.next_review
        progress.due_date = outcome.next_review.date()
        progress.proficiency_score = self._next_proficiency(progress.proficiency_score or 0, rating)
        if self.is_nailed(progress) and progress.mastered_date is None:
            progress.mastered_date = now
            progress.state = "mastered"
        progress.updated_at = now
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    @staticmethod
    def _next_proficiency(current: int, rating: int) -> int:
        delta = {-1: 0, 0: -15, 1: 4, 2: 14, 3: 22}.get(rating, 0)
        return max(0, min(100, int(current or 0) + delta))

    @staticmethod
    def is_nailed(progress: UserConjugationProgress) -> bool:
        return bool(
            progress.mastered_date
            or (progress.state or "").lower() in {"mastered", "gemeistert"}
            or ((progress.reps or 0) >= 2 and (progress.proficiency_score or 0) >= 90 and (progress.lapses or 0) == 0)
        )

    @staticmethod
    def _allowed_cefr_bands(cefr_band: str | None) -> list[str]:
        if not cefr_band:
            return []
        max_order = CEFR_ORDER.get(cefr_band.upper())
        if max_order is None:
            return []
        return [band for band, order in CEFR_ORDER.items() if order <= max_order]

    def _serialize_progress_item(self, progress: UserConjugationProgress) -> dict[str, Any]:
        table = self.table_for(progress.normalized_lemma, progress.tense)
        if not table:
            table = self.table_for(normalize_lemma(progress.verb_lemma), progress.tense)
        persons = [row["person"] for row in table] or PERSONS
        person = persons[(progress.reps or 0) % len(persons)]
        answer = next((row["form"] for row in table if row["person"] == person), "")
        due_at = progress.next_review_date
        if due_at is None and progress.due_date:
            due_at = datetime.combine(progress.due_date, time.min, tzinfo=timezone.utc)
        return {
            "id": f"{progress.normalized_lemma}:{progress.tense}",
            "lemma": progress.verb_lemma,
            "normalized_lemma": progress.normalized_lemma,
            "tense": progress.tense,
            "tense_label": DISPLAY_TENSES.get(progress.tense, progress.tense),
            "person": person,
            "prompt": f"{progress.verb_lemma} · {DISPLAY_TENSES.get(progress.tense, progress.tense)} · {person}",
            "answer": answer,
            "cefr_band": progress.cefr_band,
            "is_irregular": True,
            "progress_id": str(progress.id) if progress.id else None,
            "state": progress.state or "new",
            "reps": progress.reps or 0,
            "lapses": progress.lapses or 0,
            "due_at": due_at.isoformat() if due_at else None,
            "table": table,
        }

    def table_for(self, normalized_lemma: str, tense: str) -> list[dict[str, Any]]:
        rows = (
            self.db.query(VerbConjugation)
            .filter(
                VerbConjugation.normalized_lemma == normalized_lemma,
                VerbConjugation.tense == tense,
            )
            .order_by(VerbConjugation.id.asc())
            .all()
        )
        if not rows:
            return []
        person_order = IMPERATIVE_PERSONS if tense == "imperatif" else PERSONS
        order = {person: index for index, person in enumerate(person_order)}
        rows.sort(key=lambda row: order.get(row.person, 99))
        return [
            {
                "person": row.person,
                "form": row.form,
                "tense": row.tense,
                "tense_label": DISPLAY_TENSES.get(row.tense, row.tense),
                "auxiliary": row.auxiliary,
            }
            for row in rows
        ]


__all__ = [
    "CEFR_ORDER",
    "CORE_TENSES",
    "DISPLAY_TENSES",
    "ESSENTIAL_IRREGULARS",
    "ConjugationService",
    "build_conjugation_rows",
    "canonicalize_lemma",
    "cefr_for_difficulty",
    "is_irregular_verb",
    "normalize_lemma",
    "upsert_conjugation_rows",
    "verb_group",
]
