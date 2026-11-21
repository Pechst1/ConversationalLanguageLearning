"""S6 stage 3 · native release has a status, not only a procedure.

`docs/ops/release-status.md` holds one table: every row has a state, a date and who can
change it, and a state the repository cannot prove is written «unknown». The fastlane
`beta` lane appends the build it uploaded to the same file.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs" / "ops" / "release-status.md"
FASTLANE = ROOT / "web-frontend" / "fastlane"

ROWS = (
    "Apple Developer enrolment",
    "App Store Connect record",
    "APNs environment on Render",
    "Sentry DSNs",
    "Legal text",
    "Last archive",
    "Last TestFlight build",
)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _status_rows() -> dict[str, list[str]]:
    text = STATUS.read_text(encoding="utf-8")
    section = text.split("## Status", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith("| Item") or set(line) <= {"|", "-", " "}:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows[cells[0]] = cells[1:]
    return rows


def test_every_row_has_a_state_a_date_and_who_can_change_it():
    rows = _status_rows()
    assert list(rows) == list(ROWS)
    for item, (state, as_of, who, _source) in rows.items():
        assert state, item
        assert who, item
        if state.lower().startswith("unknown"):
            assert as_of in {"—", ""} or DATE.match(as_of), item
        else:
            assert DATE.match(as_of), f"{item}: a known state carries the date it was true"


def test_the_beta_lane_records_what_it_uploaded():
    fastfile = (FASTLANE / "Fastfile").read_text(encoding="utf-8")
    lane = fastfile[fastfile.index("lane :beta do") :]
    assert lane.index("upload_to_testflight(") < lane.index("record_testflight_build(")
    assert 'require_relative "release_status"' in fastfile
    assert "## TestFlight builds" in STATUS.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("ruby") is None, reason="needs ruby")
def test_the_appender_adds_one_row_at_the_end(tmp_path: Path):
    status = tmp_path / "release-status.md"
    status.write_text(STATUS.read_text(encoding="utf-8"), encoding="utf-8")
    script = (
        f'require "{FASTLANE / "release_status.rb"}"\n'
        f'ReleaseStatus.append_testflight_build("{status}", build: "202611101630", '
        'commit: "abc1234", version: "1.0", uploaded_at: Time.utc(2026, 11, 10, 16, 30))\n'
    )
    subprocess.run([shutil.which("ruby"), "-e", script], check=True)  # noqa: S603
    lines = status.read_text(encoding="utf-8").rstrip("\n").splitlines()
    assert lines[-1] == "| 2026-11-10 16:30 UTC | 1.0 | 202611101630 | abc1234 |"
    # The status table is untouched.
    assert status.read_text(encoding="utf-8").startswith(STATUS.read_text(encoding="utf-8").rstrip("\n"))
