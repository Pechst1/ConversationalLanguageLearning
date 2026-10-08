#!/usr/bin/env python
"""CI: print the test files of one backend shard (``ci_test_shard.py 2 4``).

The suite outgrew one 2-core runner (cancelled at 30 minutes, 80 % done), so
the backend job runs as a matrix. Files are dealt greedily, largest first, to
the lightest shard — a file's size is a fair proxy for its run time, and a
file never splits, so ``--dist loadfile`` module fixtures still build once.
Every file lands in exactly one shard (tests/test_wp85_ci.py checks it).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_files() -> list[Path]:
    return sorted(path.relative_to(ROOT) for path in (ROOT / "tests").rglob("test_*.py"))


def shards(count: int) -> list[list[str]]:
    buckets: list[tuple[int, list[str]]] = [(0, []) for _ in range(count)]
    for path in sorted(test_files(), key=lambda p: (-(ROOT / p).stat().st_size, str(p))):
        index = min(range(count), key=lambda i: (buckets[i][0], i))
        size, files = buckets[index]
        buckets[index] = (size + (ROOT / path).stat().st_size, [*files, str(path)])
    return [sorted(files) for _, files in buckets]


def main(argv: list[str]) -> int:
    shard, count = int(argv[1]), int(argv[2])
    if not 1 <= shard <= count:
        raise SystemExit(f"shard {shard} is not in 1..{count}")
    print(" ".join(shards(count)[shard - 1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
