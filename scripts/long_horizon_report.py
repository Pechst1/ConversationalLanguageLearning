"""WP-68 — a season at a glance, so the owner can *read* whether it has an arc.

``tests/test_long_horizon_evidence.py`` proves the six packages of 2026-09-21
hold together over four months. Proving it is not the same as being able to see
it, and no assertion can answer the only question that matters about a serial:
does this life go anywhere?

This script plays **the same harness** — the real router, planner, living-story
engine and Courrier against a scripted model — and writes one readable timeline
per learner: chapter by chapter with its shape, its arc and whether it moved the
season, the cast's off-screen weeks, every letter and how it ended, and the
shape of each day underneath. It is the reading copy of the evidence, not a
second implementation of it.

Run from the repository root::

    python -m scripts.long_horizon_report                 # both learners, 126 days
    python -m scripts.long_horizon_report --days 60 --seeds A
    python -m scripts.long_horizon_report --out-dir var/reviews

**No provider is ever constructed and nothing is spent.** The model is the
scripted fake the test suite uses; there is no ``--live`` and there is nothing to
pay for. The paid review of the *prose* is a different tool
(``scripts/review_living_story.py``), and it is the one that costs money.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The harness refuses to run without these, exactly as the test suite does: no
# credential is read, the story engine's client is a scripted fake, and the
# Courrier takes its authored fallback path.
os.environ.setdefault("SECRET_KEY", "long-horizon-report")
os.environ.setdefault("ATELIER_LLM_ENABLED", "false")
os.environ.setdefault("ATELIER_STORY_ENGINE_ENABLED", "false")
os.environ.setdefault("GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED", "false")
os.environ.setdefault("AUTO_CREATE_USERS_ON_LOGIN", "false")


# ---------------------------------------------------------------------------
# A throwaway database, built and dropped with the run
# ---------------------------------------------------------------------------


def build_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from app.db import models  # noqa: F401  — imported for the mapper side effects
    from app.db.base import Base

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return engine


# ---------------------------------------------------------------------------
# The timeline
# ---------------------------------------------------------------------------


SHAPE_FR = {
    "standard": "journée ordinaire",
    "listening": "jour d'écoute",
    "reprise": "jour de reprise",
    "letter": "jour de lettre",
    "short": "jour court",
}

OUTCOME_FR = {
    "kept": "parole tenue",
    "partial": "en partie",
    "missed": "manqué cette fois",
    "ignored": "restée sans réponse",
}


def _bar(counted: Counter, total: int) -> list[str]:
    rows = []
    for name, count in counted.most_common():
        share = round(100 * count / total) if total else 0
        rows.append(f"| {name} | {count} | {share} % | {'█' * max(1, share // 4)} |")
    return rows


def _chapter_lines(life: Any) -> list[str]:
    """One row per chapter: what it was, what it cost the season, who was in it."""

    lines = [
        "| # | jour | chapitre | forme | ce qu'il a fait | comment ça s'est fini |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    detailed = [row for row in life.live.get("chronicle") or [] if row.get("kind") != "season"]
    by_id = {str(row.get("id")): row for row in detailed}
    for index, chapter in enumerate(life.chapters, start=1):
        digest = by_id.get(str(chapter.get("id"))) or {}
        kind = (
            "FINALE"
            if chapter.get("finale")
            else "interlude"
            if chapter.get("interlude")
            else "side story"
            if chapter.get("side_story")
            else "arc"
        )
        # Only the last ten chapters keep a digest; the rest are folded into the
        # season row below, which is WP-62's design and not a missing record.
        when = f"j{digest['day']}" if digest.get("day") else "replié"
        lines.append(
            "| {n} | {when} | {title} | {shape} | {kind} | {question} |".format(
                n=index,
                when=when,
                title=str(chapter.get("title_fr") or "—")[:40],
                shape=chapter.get("shape") or "standard",
                kind=kind,
                question=str(
                    digest.get("resolved_fr") or chapter.get("dramatic_question") or "—"
                )[:60],
            )
        )
    return lines


def _letter_lines(life: Any) -> list[str]:
    lines = [
        "| jour | correspondant·e | lettre | échéance | issue |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in life.letters:
        events = row.get("events") or []
        day = min((entry["day"] for entry in events), default=None)
        index = int(row.get("chain_index") or 1)
        # «1ʳᵉ lettre sur 3», «2ᵉ lettre sur 3» — the ordinals WP-65's
        # `crChainLabel` prints on the Courrier page.
        ordinal = "1ʳᵉ" if index == 1 else f"{index}ᵉ"
        chain = f"{ordinal} sur {row['chain_total']}" if row.get("chain_id") else "lettre seule"
        outcome = OUTCOME_FR.get(str(row.get("outcome")), "—")
        if row.get("answered_in_journey"):
            outcome += " (dans la journée)"
        lines.append(
            "| {day} | {who} | {chain} | {due} | {outcome} |".format(
                day=f"j{day}" if day else "—",
                who=row.get("correspondent_id") or "—",
                chain=chain,
                due=(row.get("expires_at") or "—")[:10],
                outcome=outcome,
            )
        )
    return lines


def _meanwhile_lines(life: Any) -> list[str]:
    from tests import test_living_story_longitudinal as story

    lines = ["| personnage | étape | ce qui s'est passé | témoins |", "| --- | --- | --- | --- |"]
    for row in story.meanwhile(life.live.get("events") or []):
        parts = str(row.get("id") or "").split(":")
        lines.append(
            "| {who} | {step} | {what} | {witnesses} |".format(
                who=parts[1] if len(parts) > 1 else "—",
                step=parts[2] if len(parts) > 2 else "—",
                what=str(row.get("summary_fr") or "")[:70],
                witnesses=", ".join(row.get("witnesses") or []),
            )
        )
    return lines


def _day_strip(life: Any) -> list[str]:
    """One line per week: the shape of each day, so a month is readable at a glance."""

    letters = {"standard": "·", "listening": "é", "reprise": "r", "letter": "L", "short": "c"}
    rows: list[str] = []
    week: list[str] = []
    for day in life.days:
        week.append("_" if not day.played else letters.get(day.day_shape, "?"))
        if len(week) == 7:
            rows.append("".join(week))
            week = []
    if week:
        rows.append("".join(week))
    return rows


def render(life: Any, *, days: int, generated: date) -> str:
    played = life.played
    shapes = Counter(life.shapes())
    phases = [row.context["season"]["phase"] for row in played]
    finale = phases.index("finale") + 1 if "finale" in phases else None
    interlude = phases.index("interlude") + 1 if "interlude" in phases else None
    lapsed = [row for row in life.letters if row["status"] == "lapsed"]

    out: list[str] = [
        f"# La saison de l'apprenant·e {life.label} — {days} jours",
        "",
        f"*Généré le {generated.isoformat()} par `scripts/long_horizon_report.py`. "
        "Modèle simulé, aucune requête payante, base jetable.*",
        "",
        "## En un coup d'œil",
        "",
        f"- **{len(played)} journées jouées** sur {days} (les autres sont des jours manqués).",
        f"- **{len(life.chapters)} chapitres**, dont "
        f"{sum(1 for row in life.chapters if row.get('side_story'))} en marge de la saison.",
        f"- **Finale** au jour {finale or '—'}, **interlude** au jour {interlude or '—'}, "
        f"saison atteinte : **{life.live.get('season_index') or 1}**.",
        f"- **{len(life.letters)} lettres**, dont {len(lapsed)} restée(s) sans réponse et "
        f"{sum(1 for row in life.letters if row['answered_in_journey'])} répondue(s) "
        "pendant la journée.",
        f"- **{len(life.live.get('consequences') or [])} conséquences** au registre, "
        f"**{len(life.live.get('planted') or [])} détails plantés**, "
        f"**{len(life.live.get('threads') or {})} fils de saison**.",
        "",
        "## Le rythme des journées",
        "",
        "| forme | jours | part | |",
        "| --- | --- | --- | --- |",
        *_bar(shapes, len(played)),
        "",
        "Semaine par semaine (`·` ordinaire · `é` écoute · `r` reprise · `L` lettre · "
        "`c` court · `_` jour manqué) :",
        "",
        "```",
        *_day_strip(life),
        "```",
        "",
        "| format de rappel | fois |",
        "| --- | --- |",
        *(f"| {name} | {count} |" for name, count in Counter(life.formats()).most_common()),
        "",
        "## Les chapitres",
        "",
        *_chapter_lines(life),
        "",
        "## Ce que la saison a retenu du tout début",
        "",
    ]
    folded = [row for row in life.live.get("chronicle") or [] if row.get("kind") == "season"]
    if not folded:
        out.append(
            "*Rien n'est encore replié : cette vie tient toujours dans les "
            "dix chapitres détaillés ci-dessus.*"
        )
        out.append("")
    for row in folded:
        out.append(
            f"**Saison {row.get('season')}** — {row.get('chapters')} chapitres, "
            f"des jours {row.get('from_day')} à {row.get('to_day')} :"
        )
        out.extend(f"- {fact}" for fact in row.get("facts") or [])
        out.append("")

    out += [
        "## Les fils de la saison",
        "",
        *(
            f"- `{key}` — **{value.get('state')}** (jour {value.get('day')})"
            for key, value in sorted((life.live.get("threads") or {}).items())
        ),
        "",
        "## La vie du casting entre les chapitres",
        "",
        *_meanwhile_lines(life),
        "",
        "## Le courrier",
        "",
        *_letter_lines(life),
        "",
        "## Ce que l'apprenant·e a rendu vrai",
        "",
        "| jour | sorte | poids | ce que c'était |",
        "| --- | --- | --- | --- |",
        *(
            "| j{day} | {kind} | {weight} | {text} |".format(
                day=row.get("day"),
                kind=row.get("kind"),
                weight=row.get("weight"),
                text=str(row.get("text_fr") or "")[:70],
            )
            for row in sorted(
                life.live.get("consequences") or [],
                key=lambda item: -int(item.get("weight") or 0),
            )[:15]
        ),
        "",
    ]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days", type=int, default=None, help="Simulated days per learner (default: the test's)."
    )
    parser.add_argument(
        "--seeds",
        default="A,B",
        help="Comma-separated learner labels. Each is a separate life with its own dice.",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("var/reviews"))
    args = parser.parse_args()

    from tests.test_long_horizon_evidence import HORIZON_DAYS, horizon_run

    days = args.days or HORIZON_DAYS
    labels = [part.strip() for part in args.seeds.split(",") if part.strip()]
    engine = build_engine()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()

    with horizon_run(engine, days=days, labels=labels) as record:
        for life in record.lives:
            path = args.out_dir / f"long-horizon-{life.label}.md"
            path.write_text(render(life, days=days, generated=today), encoding="utf-8")
            print(f"wrote {path}")
    print("No provider was called and nothing was spent.")


if __name__ == "__main__":
    main()
