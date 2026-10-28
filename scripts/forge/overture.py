"""Read a small box of Paris out of Overture Maps, with HTTP range requests only.

Overture publishes its whole map as GeoParquet on a public S3 bucket (no account, no key).
Each file's footer carries per-row-group bounding boxes, so a survey of a few hundred metres
reads the footers, picks the row groups that touch the box and downloads only those: a few
megabytes for a quarter, in seconds.

Licences: buildings, places, transportation and base are ODbL (OpenStreetMap) or CDLA
Permissive 2.0 depending on the source; the forge keeps the release and the attribution in
every site it writes (``provenance``).
"""
from __future__ import annotations

import io
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pyarrow.parquet as pq
import requests

BUCKET = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
PINNED = "2026-10-21.0"
ATTRIBUTION = "© OpenStreetMap contributors (ODbL), Overture Maps Foundation"

_session = requests.Session()


def _get(url: str, **kw) -> requests.Response:
    for attempt in range(5):
        try:
            r = _session.get(url, timeout=60, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


class RangeFile(io.RawIOBase):
    """A remote file that pyarrow can seek in; reads go out as Range requests in 512 kB blocks."""

    BLOCK = 512 * 1024

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.pos = 0
        r = _session.head(url, timeout=30)
        r.raise_for_status()
        self.size = int(r.headers["Content-Length"])
        self.blocks: dict[int, bytes] = {}

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, off: int, whence: int = 0) -> int:
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _block(self, i: int) -> bytes:
        if i not in self.blocks:
            start = i * self.BLOCK
            end = min(self.size, start + self.BLOCK) - 1
            self.blocks[i] = _get(self.url, headers={"Range": f"bytes={start}-{end}"}).content
        return self.blocks[i]

    def readinto(self, b) -> int:  # type: ignore[override]
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        # one request for a long read, blocks for the small ones pyarrow makes in the footer
        if n > self.BLOCK:
            data = _get(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"}).content
        else:
            out = bytearray()
            p = self.pos
            while len(out) < n:
                i, o = divmod(p, self.BLOCK)
                chunk = self._block(i)[o : o + n - len(out)]
                if not chunk:
                    break
                out += chunk
                p += len(chunk)
            data = bytes(out)
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def _keys(prefix: str, delimiter: str | None = None) -> list[str]:
    keys: list[str] = []
    token = None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if delimiter:
            params["delimiter"] = delimiter
        if token:
            params["continuation-token"] = token
        text = _get(BUCKET + "/", params=params).text
        keys += re.findall(r"<Prefix>([^<]+)</Prefix>", text) if delimiter else re.findall(r"<Key>([^<]+)</Key>", text)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", text)
        if not m:
            return [k for k in keys if k != prefix]
        token = m.group(1)


def latest_release() -> str:
    """The newest release on the bucket (they are named by date), or the pinned one offline."""
    try:
        found = [k.rstrip("/").split("/")[-1] for k in _keys("release/", "/")]
        dated = sorted(r for r in found if re.match(r"\d{4}-\d{2}-\d{2}\.\d+$", r))
        return dated[-1] if dated else PINNED
    except requests.RequestException:
        return PINNED


def _row_group_box(md, rg: int):
    got = {}
    g = md.row_group(rg)
    for c in range(g.num_columns):
        col = g.column(c)
        p = col.path_in_schema
        if p in ("bbox.xmin", "bbox.ymin", "bbox.xmax", "bbox.ymax") and col.statistics is not None and col.statistics.has_min_max:
            got[p] = (col.statistics.min, col.statistics.max)
    if len(got) < 4:
        return None
    return got["bbox.xmin"][0], got["bbox.ymin"][0], got["bbox.xmax"][1], got["bbox.ymax"][1]


def read_box(release: str, theme: str, typ: str, box: tuple[float, float, float, float], columns: list[str] | None = None) -> list[dict]:
    """Every feature of one Overture type whose bbox touches `box` (lon/lat), as dicts."""
    x0, y0, x1, y1 = box
    keys = [k for k in _keys(f"release/{release}/theme={theme}/type={typ}/") if k.endswith(".parquet")]
    t0 = time.time()

    def hits(key: str):
        pf = pq.ParquetFile(RangeFile(f"{BUCKET}/{key}"))
        md = pf.metadata
        out = []
        for rg in range(md.num_row_groups):
            b = _row_group_box(md, rg)
            if b and b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0:
                out.append(rg)
        return key, out

    with ThreadPoolExecutor(24) as ex:
        found = [(k, h) for k, h in ex.map(hits, keys) if h]
    rows: list[dict] = []
    for key, groups in found:
        pf = pq.ParquetFile(RangeFile(f"{BUCKET}/{key}"))
        schema = set(pf.schema_arrow.names)
        cols = [c for c in columns if c in schema] if columns else None
        for r in pf.read_row_groups(groups, columns=cols).to_pylist():
            bb = r.get("bbox")
            if bb and bb["xmin"] <= x1 and bb["xmax"] >= x0 and bb["ymin"] <= y1 and bb["ymax"] >= y0:
                rows.append(r)
    print(f"  {theme}/{typ}: {len(keys)} files, {len(found)} touched, {len(rows)} features in {time.time() - t0:.1f}s", file=sys.stderr)
    return rows
