"""S3 stage 1: one resolver for the interface language, one for the mother tongue.

#522 / #542: the server had a dozen ways to turn ``User.native_language`` into
a language — ``normalize_control_language``, ``glosses.normalize_language``,
``learner_copy.copy_language``, six private ``_localized`` helpers, three
private ``_language`` helpers and ~22 inline ``[:2]`` slices. They disagreed on
unknown codes and on the B1 switch to French.

Now two questions have two names, both in ``app/services/chrome_language.py``:

* ``user_chrome_language(user)`` — the interface language (en/de/fr, French from B1);
* ``user_mother_tongue(user)`` — the gloss and explanation language (any code).

This guard forbids reading ``native_language`` off a user, a row or a payload
anywhere else in ``app/``. ``_EXEMPT`` is a two-sided ratchet: a file may not
read more than it lists, and an entry that is no longer needed must come off.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = REPO_ROOT / "app"
FRONTEND = REPO_ROOT / "web-frontend"

#: Files allowed to read ``native_language``, with how many reads. May only shrink.
_EXEMPT: dict[str, int] = {
    # The two resolvers (user_chrome_language, user_mother_tongue, user_mother_tongue_raw).
    "app/services/chrome_language.py": 3,
    # Auth / settings: signup reads the language off the registration payload to store it.
    "app/services/auth.py": 2,
}


def _reads(tree: ast.AST) -> int:
    """``x.native_language``, ``getattr(x, "native_language", …)`` and ``x["native_language"]``."""

    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "native_language" and isinstance(node.ctx, ast.Load):
            count += 1
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "hasattr"}
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "native_language"
        ):
            count += 1
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Load)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "native_language"
        ):
            count += 1
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "native_language"
        ):
            count += 1
    return count


def _found() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(("app/db/models/", "app/schemas/")):
            continue  # the column and the wire shape declare it; they do not read it
        count = _reads(ast.parse(path.read_text(encoding="utf-8")))
        if count:
            found[rel] = count
    return found


def test_native_language_is_read_only_by_the_resolvers() -> None:
    found = _found()
    grew = {path: (count, _EXEMPT.get(path, 0)) for path, count in found.items() if count > _EXEMPT.get(path, 0)}
    assert not grew, (
        "These modules read `native_language` themselves (found, allowed). Ask "
        "`chrome_language.user_chrome_language(user)` for the interface language, or "
        "`chrome_language.user_mother_tongue(user)` for the gloss / explanation language: "
        f"{grew}"
    )


def test_exemptions_are_tight() -> None:
    """A read that moved behind a resolver comes off the list, so it cannot creep back."""

    found = _found()
    stale = {path: (found.get(path, 0), allowed) for path, allowed in _EXEMPT.items() if found.get(path, 0) < allowed}
    assert not stale, f"Lower these exemptions (found, allowed): {stale}"
    empty = [path for path, allowed in _EXEMPT.items() if allowed == 0]
    assert not empty, f"Remove these zero entries from _EXEMPT: {empty}"


#: Inline folds of a language code: ``str(language or "en")[:2]``, ``.split("-")[0]``.
_INLINE_FOLD = re.compile(r"lang[a-z_]*\b[^\n]{0,40}\)\s*(?:\.\w+\(\))*\s*\[:2\]|lang[a-z_]*[^\n]{0,40}\.split\(\"-\"\)\[0\]")


def test_no_inline_language_folds() -> None:
    offenders = []
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == "app/services/chrome_language.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _INLINE_FOLD.search(line):
                offenders.append(f"{rel}:{number}: {line.strip()}")
    assert not offenders, "Fold language codes with chrome_language.fold_language / mother_tongue:\n" + "\n".join(
        offenders
    )


@pytest.mark.parametrize(
    ("value", "chrome", "tongue"),
    [
        ("de", "de", "de"),
        ("de-AT", "de", "de"),
        ("EN_gb", "en", "en"),
        ("fr", "fr", "fr"),
        ("es", "en", "es"),
        (None, "en", "en"),
        ("", "en", "en"),
    ],
)
def test_two_questions_two_answers(value, chrome, tongue) -> None:
    from types import SimpleNamespace

    from app.services.chrome_language import user_chrome_language, user_mother_tongue

    beginner = SimpleNamespace(native_language=value, cefr_estimate="A1", proficiency_level="A1")
    assert user_chrome_language(beginner) == chrome
    assert user_mother_tongue(beginner) == tongue
    advanced = SimpleNamespace(native_language=value, cefr_estimate="B1", proficiency_level="B1")
    assert user_chrome_language(advanced) == "fr"
    assert user_mother_tongue(advanced) == tongue, "the mother tongue does not switch at B1"


def test_old_normalisers_are_the_primitives() -> None:
    from app.services import chrome_language, glosses, journey_contracts, learner_copy

    assert journey_contracts.normalize_control_language is chrome_language.fold_language
    assert glosses.normalize_language is chrome_language.mother_tongue
    assert learner_copy.copy_language is chrome_language.fold_language


#: Screens shown before there is an account (no profile to read), allowed to ask the device.
#: May only shrink.
_DEVICE_EXEMPT: frozenset[str] = frozenset(
    {
        # Signup / onboarding: the language is being chosen; the device is the first guess.
        "web-frontend/lib/onboarding-locale.ts",
        # Privacy and terms: reachable signed out; `?lang=` wins over the device.
        "web-frontend/components/legal/LegalPage.tsx",
    }
)


def _device_guessers() -> set[str]:
    found = set()
    for folder in ("pages", "components", "lib", "hooks"):
        root = FRONTEND / folder
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.ts*")):
            if re.search(r"navigator\.languages?\b", path.read_text(encoding="utf-8")):
                found.add(path.relative_to(REPO_ROOT).as_posix())
    return found


def test_no_screen_guesses_from_the_device() -> None:
    """Le Quartier guessed German from the phone; a signed-in screen reads the profile."""

    offenders = sorted(_device_guessers() - _DEVICE_EXEMPT)
    assert not offenders, (
        "Read the learner's language from the profile (useChromeLanguage / useLearnerLanguage "
        f"in lib/learner-language.ts), not the device: {offenders}"
    )
    stale = sorted(_DEVICE_EXEMPT - _device_guessers())
    assert not stale, f"Remove these from _DEVICE_EXEMPT, they no longer ask the device: {stale}"
