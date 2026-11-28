"""#1062: the Journal's failed check showed one slip of several under «Basic check only».

Live walk 25 Nov (A1.1, day 43): «Hier, Camille et moi avons visite la gerance de M.
Marchand. Je ne savais pas, mais sa grand-mere ne ma rien dit.» came back «Basic check only.
The full check did not run.» with one fix, «grand-mere → grand-mère». «visite» (visité),
«gerance» (gérance) and «ne ma» (ne m'a) were left unmarked, and the full check was never
asked again: one failed call was the learner's result.

Done when: the Journal asks the full check once more before it falls back; the basic check
marks «visite», «gerance» and «ne ma»; and the screen says some slips may be missing (the
copy is pinned in ``web-frontend/lib/verdict.test.js``).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.services import correction_contract
from tests.test_journal import (  # noqa: F401 - the module's table fixture is autouse there
    TODAY,
    _concept,
    _FakeCorrector,
    _journey,
    _user,
    _write,
    journal_table,
)

FIRST = (
    "Hier, Camille et moi avons visite la gerance de M. Marchand. "
    "Je ne savais pas, mais sa grand-mere ne ma rien dit."
)
SECOND = (
    "Hier, Marchand a dit : non, ce nest pas possible. Margaux a peur de lui. "
    "Je veux garder le cahier de ma grand-mere."
)


def _fixes(text: str) -> dict[str, str]:
    return {edit.span: edit.replacement for edit in correction_contract.deterministic_edits(text)}


# ---------------------------------------------------------------------------
# the basic check marks every slip it can find
# ---------------------------------------------------------------------------


def test_basic_check_marks_all_four_slips():
    fixes = _fixes(FIRST)
    assert fixes.get("visite") == "visité", fixes
    assert fixes.get("gerance") == "gérance", fixes
    assert fixes.get("ma") == "m'a", fixes
    assert fixes.get("grand-mere") == "grand-mère", fixes
    assert correction_contract.repair_text(FIRST) == (
        "Hier, Camille et moi avons visité la gérance de M. Marchand. "
        "Je ne savais pas, mais sa grand-mère ne m'a rien dit."
    )


def test_second_retell_keeps_both_fixes():
    fixes = _fixes(SECOND)
    assert fixes.get("nest") == "n'est", fixes
    assert fixes.get("grand-mere") == "grand-mère", fixes


@pytest.mark.parametrize(
    ("text", "span", "right"),
    [
        ("Nous avons mange une pomme.", "mange", "mangé"),
        ("Marchand a signe le bail.", "signe", "signé"),
        ("Elle n'a pas regarde la lettre.", "regarde", "regardé"),
        ("J'ai reve de Paris.", "reve", "rêvé"),
        # alone, «ecoute» may be «écoute» or «écouté»; after «j'ai» it is the participle
        ("J'ai ecoute la radio.", "ecoute", "écouté"),
        ("Il a complete le formulaire.", "complete", "complété"),
        ("Il ma dit non.", "ma", "m'a"),
        ("Elle ne ta jamais vu.", "ta", "t'a"),
    ],
)
def test_participle_and_glued_object(text, span, right):
    assert _fixes(text).get(span) == right, _fixes(text)


@pytest.mark.parametrize(
    "right",
    [
        "J'ai envie de partir.",
        "Il a hâte de partir.",
        "Il y a classe demain.",
        "C'est ma maison.",
        "Il ne pense pas à ma mère.",
        "Il a une visite demain.",
        "Nous avons une gérance.",
        "Il en a marre.",
        "Il a affaire à Marchand.",
        "Il a contre lui tout le quartier.",
        "Il ne la voit pas.",
    ],
)
def test_right_french_is_left_alone(right):
    fixes = _fixes(right)
    assert not any(rep.endswith("é") or rep in {"m'a", "t'a"} for rep in fixes.values()), (right, fixes)


# ---------------------------------------------------------------------------
# the Journal asks the full check once more, then shows every slip
# ---------------------------------------------------------------------------


class _FailsOnce(_FakeCorrector):
    """A provider that times out on the first call and answers the second."""

    def generate_error_detection(self, messages, **kwargs):
        self.fail = self.calls == 0
        return super().generate_error_detection(messages, **kwargs)


def test_journal_retries_full_check_once(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    corrector = _FailsOnce({"verdict": "accepted", "score_0_4": 4, "errata": []})
    entry = _write(db_session, user, corrector, FIRST)

    assert corrector.calls == 2, "a failed full check is asked once more before the learner sees a result"
    assert entry.assessment_status == "checked"
    assert entry.correction["checker"] == "model"
    assert entry.correction["paid_calls"] == 1


def test_journal_basic_check_lists_every_slip(db_session):
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    corrector = _FakeCorrector(fail=True)
    entry = _write(db_session, user, corrector, FIRST)

    assert corrector.calls == 2, "retried once, and only once"
    assert entry.correction["checker"] == "deterministic"
    assert entry.correction["retryable"] is True
    spans = {item["span_fr"]: item["corrected_fr"] for item in entry.correction["errata"]}
    for wrong, right in (("visite", "visité"), ("gerance", "gérance"), ("ma", "m'a"), ("grand-mere", "grand-mère")):
        assert any(wrong in span and right in fixed for span, fixed in spans.items()), (wrong, spans)


# ---------------------------------------------------------------------------
# the retry stays inside the time the learner's browser waits (review of #1097)
# ---------------------------------------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _TimesOut(_FakeCorrector):
    """A provider that spends its whole window and then times out, on every call."""

    def __init__(self, clock: _Clock, *, first_takes: float) -> None:
        super().__init__(fail=True)
        self.fail_message = "Request timed out (timeout)"
        self.clock = clock
        self.first_takes = first_takes
        self.windows: list[float] = []

    def generate_error_detection(self, messages, **kwargs):
        window = float(kwargs["request_timeout"])
        self.windows.append(window)
        # the first call takes what the test says (a slow provider can overrun its
        # window a little); every later one spends the whole window it was given
        self.clock.now += self.first_takes if len(self.windows) == 1 else window
        return super().generate_error_detection(messages, **kwargs)


def _client_wait_seconds() -> float:
    import pathlib
    import re

    api = (pathlib.Path(__file__).resolve().parents[1] / "web-frontend" / "services" / "api.ts").read_text()
    match = re.search(r"JOURNAL_CHECK_TIMEOUT_MS\s*=\s*([\d_]+)", api)
    if match:
        return int(match.group(1).replace("_", "")) / 1000
    return float(re.search(r"axios\.create\(\{[^}]*?timeout:\s*(\d+)", api, re.S).group(1)) / 1000


@pytest.mark.parametrize("first_takes", [60.0, 70.0, 2.0])
def test_retry_fits_the_client_wait(db_session, monkeypatch, first_takes):
    """A first call that times out after 60 s may not start a second one the browser
    will stop waiting for: the whole check returns inside the client's wait."""

    clock = _Clock()
    monkeypatch.setattr("app.services.journal._monotonic", clock, raising=False)
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    corrector = _TimesOut(clock, first_takes=first_takes)
    started = clock.now
    entry = _write(db_session, user, corrector, FIRST)

    spent = clock.now - started
    margin = 10.0
    assert spent + margin <= _client_wait_seconds(), (
        f"the check held the write for {spent:.0f} s ({corrector.windows}); the browser gives up at "
        f"{_client_wait_seconds():.0f} s and shows «The entry could not be sent»"
    )
    assert entry.correction["checker"] == "deterministic"


def test_fast_failure_is_retried_with_the_time_left(db_session, monkeypatch):
    from app.services.journal import CHECK_BUDGET_SECONDS

    clock = _Clock()
    monkeypatch.setattr("app.services.journal._monotonic", clock)
    user = _user(db_session)
    _journey(db_session, user, local_date=TODAY - timedelta(days=1), concept=_concept(db_session))
    corrector = _TimesOut(clock, first_takes=5.0)
    _write(db_session, user, corrector, FIRST)

    assert len(corrector.windows) == 2, "a fast failure is asked once more"
    assert corrector.windows[1] <= CHECK_BUDGET_SECONDS - 5.0


def test_client_wait_holds_the_server_budget():
    """Source contract: the browser waits longer than the server's whole check, and the
    server's single-call window fits inside that budget."""

    from app.config import settings
    from app.services.journal import CHECK_BUDGET_SECONDS, RETRY_FLOOR_SECONDS

    assert settings.ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS <= CHECK_BUDGET_SECONDS
    assert RETRY_FLOOR_SECONDS < CHECK_BUDGET_SECONDS
    assert _client_wait_seconds() >= CHECK_BUDGET_SECONDS + 10, (
        "the browser must wait for the whole check (both calls) with room for the save"
    )
    import pathlib

    api = (pathlib.Path(__file__).resolve().parents[1] / "web-frontend" / "services" / "api.ts").read_text()
    for method in ("writeJournalEntry", "retryJournalCorrection"):
        body = api.split(f"async {method}(")[1].split("\n  }\n")[0]
        assert "JOURNAL_CHECK_TIMEOUT_MS" in body, f"{method} waits on the client's shared deadline"
