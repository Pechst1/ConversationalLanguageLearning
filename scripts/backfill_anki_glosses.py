"""Fill the missing English column on imported Anki vocabulary rows.

The French 5000 deck was imported from a French↔German Anki export, so
`german_translation` is populated and `english_translation` is not. Since
`app/services/glosses.py` resolves a card's gloss by the learner's own language,
an English-speaking learner falls through to the German column and is shown a
word in a language they never claimed to read.

Filling that column needs a translation the deck does not contain, so unlike
`scripts/backfill_anki_examples.py` this one costs money. Everything here exists
to keep that cost visible and bounded:

* **dry run is the default.** `--live` is the only way to spend anything, and it
  refuses to start without both `--max-rows` and `--max-cost-usd` given
  explicitly on the command line — there is no default ceiling to forget.
* **the ceiling is enforced mid-run**, not just checked at the end: the loop
  stops as soon as the accumulated provider cost would exceed it.
* **nothing is ever overwritten.** Only rows where `english_translation` is NULL
  or blank are selected, and a row is skipped again if it gained a value while
  the script was running.
* **provenance is recorded** on every row it writes: the model, this script's
  prompt version, and the run's timestamp go into `usage_notes` so a bad batch
  can be found and reverted.

    # measure, cost nothing (the default)
    .venv/bin/python scripts/backfill_anki_glosses.py --dry-run

    # spend, with both ceilings stated
    .venv/bin/python scripts/backfill_anki_glosses.py --live --max-rows 250 --max-cost-usd 2.00
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, or_, select  # noqa: E402

from app.db.models.vocabulary import VocabularyWord  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

#: Bumped whenever the prompt below changes, so a row's provenance is exact.
GLOSS_PROMPT_VERSION = "anki-gloss-backfill-v1"
PROVENANCE_KEY = "english_gloss_backfill"

#: Rows per provider call. Small enough that a ceiling stop wastes little, large
#: enough that the per-call overhead is not the dominant cost.
DEFAULT_BATCH_SIZE = 25

SYSTEM_PROMPT = (
    "You translate single French vocabulary entries into English for a language-learning "
    "flashcard deck. Answer with the dictionary gloss only: no article unless the French "
    "entry has one, no explanation, no example, no punctuation at the end. Keep a verb in "
    "the infinitive if the French entry is an infinitive. If an entry has several common "
    "senses, give the two most common separated by a comma."
)


def _missing_english_filter():
    return or_(
        VocabularyWord.english_translation.is_(None),
        func.trim(VocabularyWord.english_translation) == "",
    )


def select_rows(
    db, *, limit: int | None, anki_only: bool, language: str | None = "fr"
) -> list[VocabularyWord]:
    """Rows that have no English gloss, most-frequent first.

    Scoped to one deck language (French by default): the table also holds a
    5,000-row German deck whose English glosses nobody reads.
    """
    query = select(VocabularyWord).where(_missing_english_filter())
    if language:
        query = query.where(VocabularyWord.language == language)
    if anki_only:
        query = query.where(VocabularyWord.is_anki_card.is_(True))
    query = query.order_by(
        VocabularyWord.frequency_rank.is_(None),
        VocabularyWord.frequency_rank,
        VocabularyWord.id,
    )
    if limit:
        query = query.limit(limit)
    return list(db.scalars(query))


def build_prompt(rows: list[VocabularyWord]) -> str:
    """One numbered French entry per line, with whatever context the row has."""
    lines = []
    for index, row in enumerate(rows, start=1):
        surface = str(row.word or row.normalized_word or "").strip()
        hints = []
        if row.part_of_speech:
            hints.append(str(row.part_of_speech))
        if row.german_translation:
            hints.append(f"German: {row.german_translation}")
        if row.example_sentence:
            hints.append(f"Used in: {row.example_sentence}")
        suffix = f"  ({'; '.join(hints)})" if hints else ""
        lines.append(f"{index}. {surface}{suffix}")
    return (
        "Translate each French entry into English.\n"
        'Answer with JSON only: {"glosses": {"1": "…", "2": "…"}} keyed by the entry number.\n\n'
        + "\n".join(lines)
    )


def parse_glosses(content: str, count: int) -> dict[int, str]:
    """The provider's answer, keyed by row index. Malformed keys are dropped."""
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return {}
    raw = payload.get("glosses") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {}
    parsed: dict[int, str] = {}
    for key, value in raw.items():
        try:
            index = int(str(key).strip().rstrip("."))
        except ValueError:
            continue
        text = str(value or "").strip()
        if 1 <= index <= count and text:
            parsed[index] = text
    return parsed


def record_provenance(row: VocabularyWord, *, model: str, ran_at: str) -> None:
    """Say on the row where its English column came from."""
    stamp = f"[{PROVENANCE_KEY}: {GLOSS_PROMPT_VERSION}; model={model}; at={ran_at}]"
    existing = str(row.usage_notes or "").strip()
    row.usage_notes = f"{existing}\n{stamp}".strip() if existing else stamp


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill English glosses on Anki vocabulary rows")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="Default. Costs nothing.")
    mode.add_argument("--live", action="store_true", help="Call the provider and write rows")
    parser.add_argument("--max-rows", type=int, default=None, help="Required with --live")
    parser.add_argument(
        "--language", type=str, default="fr", help="Deck language to gloss (default fr; 'all' for every deck)"
    )
    parser.add_argument("--max-cost-usd", type=float, default=None, help="Required with --live")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--model", type=str, default=None, help="Override the configured model")
    parser.add_argument(
        "--all-rows",
        action="store_true",
        help="Include rows that did not come from the Anki import",
    )
    args = parser.parse_args()

    live = bool(args.live)
    if live:
        if args.max_rows is None or args.max_cost_usd is None:
            parser.error("--live requires both --max-rows and --max-cost-usd; there is no default ceiling")
        if args.max_rows <= 0 or args.max_cost_usd <= 0:
            parser.error("--max-rows and --max-cost-usd must be positive")

    db = SessionLocal()
    try:
        total_missing = db.scalar(
            select(func.count()).select_from(VocabularyWord).where(_missing_english_filter())
        )
        anki_missing = db.scalar(
            select(func.count())
            .select_from(VocabularyWord)
            .where(_missing_english_filter(), VocabularyWord.is_anki_card.is_(True))
        )
        with_german = db.scalar(
            select(func.count())
            .select_from(VocabularyWord)
            .where(
                _missing_english_filter(),
                VocabularyWord.german_translation.isnot(None),
                func.trim(VocabularyWord.german_translation) != "",
            )
        )
        print(f"rows missing english_translation : {total_missing}")
        print(f"  of those, Anki-imported        : {anki_missing}")
        print(f"  of those, with a German gloss  : {with_german}")

        language = None if args.language == "all" else args.language
        rows = select_rows(db, limit=args.max_rows, anki_only=not args.all_rows, language=language)
        print(f"rows this run would translate    : {len(rows)}")

        if not live:
            print("\nDRY RUN — nothing was called and nothing was written.")
            if rows:
                preview = ", ".join(str(row.word) for row in rows[:10])
                print(f"first rows: {preview}")
            print(
                "To spend: scripts/backfill_anki_glosses.py --live "
                "--max-rows <N> --max-cost-usd <USD>"
            )
            return 0

        # Imported lazily so a dry run never needs provider configuration.
        from app.services.llm_service import LLMService

        llm = LLMService()
        ran_at = datetime.now(UTC).isoformat(timespec="seconds")
        spent = 0.0
        written = 0
        skipped = 0
        model_used = args.model or ""

        for start in range(0, len(rows), args.batch_size):
            batch = rows[start : start + args.batch_size]
            if spent >= args.max_cost_usd:
                print(f"cost ceiling reached at ${spent:.4f}; stopping before batch {start // args.batch_size + 1}")
                break
            try:
                result: Any = llm.generate_chat_completion(
                    [{"role": "user", "content": build_prompt(batch)}],
                    system_prompt=SYSTEM_PROMPT,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    # gpt-5 reasoning models return empty content when the output
                    # budget is small and no reasoning_effort is set (starvation).
                    max_tokens=4000,
                    reasoning_effort="low",
                    model=args.model,
                )
            except Exception as exc:  # provider outage must not lose earlier work
                print(f"provider call failed on batch {start // args.batch_size + 1}: {exc}")
                break

            spent += float(getattr(result, "cost", 0.0) or 0.0)
            model_used = getattr(result, "model", "") or model_used
            glosses = parse_glosses(getattr(result, "content", "") or "", len(batch))
            for index, row in enumerate(batch, start=1):
                gloss = glosses.get(index)
                if not gloss:
                    skipped += 1
                    continue
                # Re-check: never overwrite, even if the column was filled since
                # the batch was selected.
                if str(row.english_translation or "").strip():
                    skipped += 1
                    continue
                row.english_translation = gloss
                record_provenance(row, model=model_used or "unknown", ran_at=ran_at)
                written += 1
            db.commit()
            print(
                f"batch {start // args.batch_size + 1}: written={written} skipped={skipped} "
                f"spent=${spent:.4f} / ${args.max_cost_usd:.2f}"
            )

        print(
            f"\nLIVE run finished: rows_written={written}, rows_skipped={skipped}, "
            f"cost=${spent:.4f}, model={model_used or 'unknown'}, "
            f"prompt_version={GLOSS_PROMPT_VERSION}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
