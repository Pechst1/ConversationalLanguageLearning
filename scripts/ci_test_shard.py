#!/usr/bin/env python
"""CI: print the test files of one backend shard (``ci_test_shard.py 2 4``).

The suite outgrew one 2-core runner (cancelled at 30 minutes, 80 % done), so
the backend job runs as a matrix. Files are dealt greedily, slowest first, to
the lightest shard. A file never splits, so ``--dist loadfile`` module
fixtures still build once. Every file lands in exactly one shard
(tests/test_wp85_ci.py checks it).

A file's weight is its measured run time from ``tests/ci_durations.json``.
File size alone dealt shards that ran 3 and 5.5 minutes on the same commit;
the slowest shard is the backend job's time. A file not in the table (new
since the last refresh) is weighed by its size at the table's median seconds
per byte. Each CI shard prints its files' times (the ``Test timings`` step,
``--print``); refresh the table from the four shards' reports with:

    python scripts/ci_test_shard.py --record report-1.xml report-2.xml ...

Times measured on a developer machine do not carry over: per file, the CI
runner is up to twice as slow, and not by the same factor for every file.
"""
from __future__ import annotations

import json
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DURATIONS = ROOT / "tests" / "ci_durations.json"


def test_files() -> list[Path]:
    return sorted(path.relative_to(ROOT) for path in (ROOT / "tests").rglob("test_*.py"))


def weights(files: list[Path]) -> dict[str, float]:
    measured = json.loads(DURATIONS.read_text()) if DURATIONS.exists() else {}
    sizes = {str(path): (ROOT / path).stat().st_size for path in files}
    rates = [measured[name] / sizes[name] for name in sizes if name in measured and sizes[name]]
    per_byte = statistics.median(rates) if rates else 1.0
    return {name: measured.get(name, size * per_byte) for name, size in sizes.items()}


def shards(count: int) -> list[list[str]]:
    weight = weights(test_files())
    buckets: list[tuple[float, list[str]]] = [(0.0, []) for _ in range(count)]
    for name in sorted(weight, key=lambda n: (-weight[n], n)):
        index = min(range(count), key=lambda i: (buckets[i][0], i))
        total, files = buckets[index]
        buckets[index] = (total + weight[name], [*files, name])
    return [sorted(files) for _, files in buckets]


def _file_of(classname: str) -> str | None:
    """``tests.services.test_x.TestY`` -> ``tests/services/test_x.py``."""
    parts = classname.split(".")
    for end in range(len(parts), 0, -1):
        name = "/".join(parts[:end]) + ".py"
        if (ROOT / name).is_file():
            return name
    return None


def record(reports: list[str]) -> dict[str, float]:
    """Seconds per test file, summed over the testcases of JUnit reports."""
    seconds: dict[str, float] = defaultdict(float)
    for report in reports:
        for case in ET.parse(report).getroot().iter("testcase"):  # noqa: S314 - our own pytest reports
            name = _file_of(case.get("classname", ""))
            if name:
                seconds[name] += float(case.get("time") or 0)
    return {name: round(value, 2) for name, value in sorted(seconds.items())}


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "--record":
        DURATIONS.write_text(json.dumps(record(argv[2:]), indent=0) + "\n")
        return 0
    if len(argv) > 1 and argv[1] == "--print":
        print(json.dumps(record(argv[2:]), separators=(",", ":")))
        return 0
    shard, count = int(argv[1]), int(argv[2])
    if not 1 <= shard <= count:
        raise SystemExit(f"shard {shard} is not in 1..{count}")
    print(" ".join(shards(count)[shard - 1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
