"""E-1 landing: slice the release candidate into area commits on top of main.

    python scripts/e1_landing_areas.py list  [--base main] [--tip release/rc-2026-10-06]
    python scripts/e1_landing_areas.py build --worktree <path> [--base main] [--tip ...]

``list`` assigns every path that differs between BASE and TIP to one area (the
first rule that matches) and prints files, commits and dates per area.

``build`` needs a worktree checked out on a fresh branch at BASE (create it with
``git worktree add <path> -b land/rc-2026-10-06 main``). For each area in order it
takes TIP's version of the area's paths (deleting what TIP deleted) and commits
them as one squashed commit. It refuses to finish unless the result's tree is
TIP's tree byte for byte, so nothing can be lost or added on the way.

It never pushes and never touches the checkout it is run from.
See docs/implementation/atelier-v2/E1-LANDING-PLAN.md.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import OrderedDict

# Matching order (first match wins). Landing order is the sorted area name.
AREAS: OrderedDict[str, str] = OrderedDict(
    [
        (
            "01-infra-ci",
            r"^(\.github/|docker/|render\.yaml$|Dockerfile|\.dockerignore$|pyproject\.toml$|conftest\.py$"
            r"|tests/conftest\.py$|\.claude/|\.gitignore$|Makefile$|\.env[^/]*example"
            r"|scripts/(restore_drill|production_compose|verify_restored_database|ci_|check_|e1_landing)"
            r"|tests/test_(wp85_ci|production_release|rollout_scripts)|README\.md$|docs/production-hardening"
            r"|web-frontend/(package(-lock)?\.json|next\.config\.js|launch-flags\.json|tsconfig|\.eslintrc))",
        ),
        (
            "02-platform-schema",
            r"^(alembic/|app/db/|app/schemas/|app/config\.py$|app/main\.py$|app/celery_app\.py$"
            r"|app/api/(deps|openapi|legal|v1/api)\.py$|app/core/(?!conversation)"
            r"|app/services/(llm_service|spend_guard|transcription_cost|notification_service|book_parser)\.py$"
            r"|app/tasks/(health|notifications)\.py$|app/data/legal/|constraints\.txt$|scripts/export_openapi"
            r"|tests/test_(sqlite_uuid|schema|migration|wp69|wp70_|wp72_|wp73_|wp108_no_real|celery))",
        ),
        (
            "03-auth-accounts",
            r"(/auth[/._-]|auth\.(py|ts)$|auth-copy|native-auth|authStorage|RouteAuthGate|password_reset|gdpr"
            r"|/users?\.py$|anki|uploads|production_(auth|recovery|uploads)|production-boundaries"
            r"|wp71_accounts|wp75_a_win|settings_language)",
        ),
        (
            "12-docs",
            r"^(docs/(?!story/|art/|design-reference/drawn-cast/)"
            r"|scripts/(audit_|calibrate_|long_horizon|pilot_digest|simulate_workload|dev_walk))",
        ),
        (
            "04-story-engine",
            r"(season|living_story|story_|stories\.py|serial|graphic_novel|panel_art|director|epilogue|lanes"
            r"|lane_guards|coulisses|scene|tentpole|loss_rate|wp13[0-4]|wp12[3-9]|app/prompts/|docs/story/"
            r"|docs/art/|scripts/art/|art_set|drawn-cast)",
        ),
        (
            "05-journey-planner",
            r"(atelier|rule_card|practice_|learner_model|learner_copy|conjugation|word_order|item_semantics"
            r"|recommendation|chrome_language|seals|seance|rehearsal|dossier|journal|journey|daily_|vocabulary"
            r"|vocab|level_|grammar|can_do|core_lexicon|lexic|srs|progress|forecast|cefr|placement|intake"
            r"|rhythm|recall|kept_words|band_check|concept|error_memory|item_bank|eclair|pace|coverage"
            r"|analytics|achievement|pilot_event|streak|notebook|wpl\d)",
        ),
        (
            "06-conversation",
            r"(conversation|npcs|mission|pragmatic|answer_acceptance|correction|errata|session|courrier"
            r"|correspondence|letter|spontaneous|wp36|exercise)",
        ),
        ("07-reader-voices", r"(reader|feuilleton|cast|voice|audio|tts|mouth|listening|line_audio|episode|archive|wp91)"),
        ("08-forge", r"(forge|wp_s\d|wps\d)"),
        (
            "09-papier-revue",
            r"(revue|gazetteer|news_service|carte|correcteur|radio|relecture|kiosk|papier|vignette|plates)",
        ),
        ("10-frontend-shell-ios", r"^(web-frontend/|mobile/)"),
        ("11-walks-and-tests", r"^tests/"),
        ("99-other", r"."),
    ]
)


def git(*args: str, cwd: str | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout  # noqa: S603, S607 - fixed git argv


def assign(base: str, tip: str) -> dict[str, list[str]]:
    paths = git("diff", "--name-only", "--no-renames", base, tip).split()
    areas: dict[str, list[str]] = {name: [] for name in AREAS}
    for path in paths:
        for name, rule in AREAS.items():
            if re.search(rule, path):
                areas[name].append(path)
                break
    return dict(sorted(areas.items()))


def cmd_list(base: str, tip: str) -> None:
    for name, paths in assign(base, tip).items():
        if not paths:
            continue
        commits: set[str] = set()
        for start in range(0, len(paths), 200):
            commits |= set(git("rev-list", "--no-merges", f"{base}..{tip}", "--", *paths[start : start + 200]).split())
        print(f"{name:24s} {len(paths):5d} files {len(commits):4d} commits")


def cmd_build(base: str, tip: str, worktree: str) -> None:
    if git("rev-parse", "HEAD", cwd=worktree).strip() != git("rev-parse", base).strip():
        sys.exit(f"{worktree} must be a fresh branch at {base}")
    deleted = set(git("diff", "--name-only", "--no-renames", "--diff-filter=D", base, tip).split())
    for name, paths in assign(base, tip).items():
        if not paths:
            continue
        keep = [p for p in paths if p not in deleted]
        gone = [p for p in paths if p in deleted]
        for start in range(0, len(keep), 200):
            git("checkout", tip, "--", *keep[start : start + 200], cwd=worktree)
        for start in range(0, len(gone), 200):
            git("rm", "-q", "--", *gone[start : start + 200], cwd=worktree)
        message = (
            f"land({name[3:]}): {name} from {tip}\n\n"
            f"Squashed per ED-1; full history on the archived release branch.\n"
            f"{len(paths)} paths. See docs/implementation/atelier-v2/E1-LANDING-PLAN.md.\n\n"
            "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        )
        git("commit", "-q", "-m", message, cwd=worktree)
        print(f"committed {name}: {len(paths)} paths")
    if git("rev-parse", "HEAD^{tree}", cwd=worktree).strip() != git("rev-parse", f"{tip}^{{tree}}").strip():
        sys.exit("the landing branch's tree is not the tip's tree — do not push it")
    print("tree identical to", tip)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["list", "build"])
    parser.add_argument("--base", default="main")
    parser.add_argument("--tip", default="release/rc-2026-10-06")
    parser.add_argument("--worktree")
    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args.base, args.tip)
    else:
        if not args.worktree:
            parser.error("build needs --worktree")
        cmd_build(args.base, args.tip, args.worktree)


if __name__ == "__main__":
    main()
