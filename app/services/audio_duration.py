"""How long a recording is, read from its container — no decoder, no dependency.

WP-158 sized a spoken story reply by its bytes at an assumed 32 kbit/s. Measured
2026-10-09, the recorders do not agree on any one rate: Chrome's Opus honours the
32 kbit/s the app asks for (3.7 kB/s), iOS 26 Safari's Opus does not (6.2 kB/s,
21.8 kB/s by default) and every AAC encoder ignores it (13.7–20 kB/s). Read by
bytes, a 23-second iPhone answer was «longer than thirty seconds».

The two containers ``MediaRecorder`` writes carry their timing:

* **WebM** (Chrome, Firefox, iOS 26 Safari): clusters of unknown size, each with a
  ``Timecode`` and ``SimpleBlock``s holding a 16-bit offset from it; the
  ``Duration`` header is usually absent while recording.
* **WAV** (a test file, a native recorder): the ``fmt`` byte rate and ``data`` size.
* **Fragmented MP4** (Safari's AAC): ``moov`` with the track's ``mdhd`` timescale
  and ``trex`` defaults, then ``moof``/``traf`` fragments with a ``tfdt`` start and
  ``trun`` sample durations. A plain MP4 (an ``afconvert`` file) has ``mvhd`` duration.

:func:`audio_seconds` returns ``None`` when it cannot read a file; the caller
then falls back to the byte estimate.
"""

from __future__ import annotations

import struct

__all__ = ["audio_seconds"]

#: An Opus or AAC frame the last block's timecode does not include (20 ms Opus).
_LAST_FRAME_S = 0.02

# ---------------------------------------------------------------------------
# WebM / Matroska (EBML)
# ---------------------------------------------------------------------------

_EBML_SEGMENT = 0x18538067
_EBML_INFO = 0x1549A966
_EBML_CLUSTER = 0x1F43B675
_EBML_BLOCK_GROUP = 0xA0
_EBML_MASTERS = {_EBML_SEGMENT, _EBML_INFO, _EBML_CLUSTER, _EBML_BLOCK_GROUP}
_EBML_TIMECODE_SCALE = 0x2AD7B1
_EBML_DURATION = 0x4489
_EBML_CLUSTER_TIMECODE = 0xE7
_EBML_SIMPLE_BLOCK = 0xA3
_EBML_BLOCK = 0xA1


def _vint(data: bytes, pos: int, *, keep_marker: bool) -> tuple[int, int, bool]:
    """(value, length, all-ones) of the EBML variable-size integer at ``pos``."""

    first = data[pos]
    length = 1
    mask = 0x80
    while length <= 8 and not first & mask:
        mask >>= 1
        length += 1
    if length > 8 or pos + length > len(data):
        raise ValueError("bad vint")
    value = first if keep_marker else first & (mask - 1)
    for byte in data[pos + 1 : pos + length]:
        value = (value << 8) | byte
    payload_bits = 7 * length
    all_ones = (value & ((1 << payload_bits) - 1)) == (1 << payload_bits) - 1
    return value, length, all_ones


def _webm_seconds(data: bytes) -> float | None:
    pos = 0
    scale = 1_000_000  # ns per timecode tick
    header_duration: float | None = None
    cluster = 0
    last = -1
    while pos < len(data):
        try:
            element, id_len, _ = _vint(data, pos, keep_marker=True)
            size, size_len, unknown = _vint(data, pos + id_len, keep_marker=False)
        except (ValueError, IndexError):
            break
        start = pos + id_len + size_len
        if element in _EBML_MASTERS:
            pos = start  # descend (clusters are written with unknown size)
            continue
        if unknown or start + size > len(data):
            break
        body = data[start : start + size]
        if element == _EBML_TIMECODE_SCALE and 0 < size <= 8:
            scale = int.from_bytes(body, "big") or scale
        elif element == _EBML_DURATION and size in (4, 8):
            header_duration = struct.unpack(">f" if size == 4 else ">d", body)[0]
        elif element == _EBML_CLUSTER_TIMECODE:
            cluster = int.from_bytes(body, "big")
        elif element in (_EBML_SIMPLE_BLOCK, _EBML_BLOCK) and size >= 4:
            try:
                _, track_len, _ = _vint(body, 0, keep_marker=False)
            except (ValueError, IndexError):
                track_len = 1
            relative = struct.unpack(">h", body[track_len : track_len + 2])[0]
            last = max(last, cluster + relative)
        pos = start + size
    seconds = (last * scale / 1e9 + _LAST_FRAME_S) if last >= 0 else None
    if header_duration and header_duration > 0:
        from_header = header_duration * scale / 1e9
        seconds = max(seconds or 0.0, from_header)
    return seconds


# ---------------------------------------------------------------------------
# MP4 (ISO BMFF), plain or fragmented
# ---------------------------------------------------------------------------

_MP4_CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"mvex", b"moof", b"traf", b"edts"}


def _boxes(data: bytes, start: int, end: int):
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack(">I4s", data[pos : pos + 8])
        header = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack(">Q", data[pos + 8 : pos + 16])[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            return
        yield kind, pos + header, pos + size
        pos += size


def _mp4_seconds(data: bytes) -> float | None:
    timescale: int | None = None
    movie_scale: int | None = None
    movie_duration = 0
    default_duration = 0
    fragments_end = 0
    running = 0  # decode time when a fragment has no tfdt

    def walk(start: int, end: int) -> None:
        nonlocal timescale, movie_scale, movie_duration, default_duration, fragments_end, running
        for kind, body, stop in _boxes(data, start, end):
            if kind in _MP4_CONTAINERS:
                if kind == b"traf":
                    traf(body, stop)
                else:
                    walk(body, stop)
            elif kind == b"mvhd":
                version = data[body]
                if version == 1:
                    movie_scale, movie_duration = struct.unpack(">IQ", data[body + 20 : body + 32])
                else:
                    movie_scale, movie_duration = struct.unpack(">II", data[body + 12 : body + 20])
            elif kind == b"mdhd":
                version = data[body]
                offset = body + (20 if version == 1 else 12)
                timescale = struct.unpack(">I", data[offset : offset + 4])[0]
            elif kind == b"trex":
                default_duration = struct.unpack(">I", data[body + 12 : body + 16])[0]

    def traf(start: int, end: int) -> None:
        nonlocal fragments_end, running
        duration_default = default_duration
        base: int | None = None
        total = 0
        for kind, body, stop in _boxes(data, start, end):
            if kind == b"tfhd":
                flags = int.from_bytes(data[body + 1 : body + 4], "big")
                offset = body + 8  # version/flags, track_ID
                if flags & 0x01:
                    offset += 8
                if flags & 0x02:
                    offset += 4
                if flags & 0x08:
                    duration_default = struct.unpack(">I", data[offset : offset + 4])[0]
            elif kind == b"tfdt":
                version = data[body]
                base = (
                    struct.unpack(">Q", data[body + 4 : body + 12])[0]
                    if version == 1
                    else struct.unpack(">I", data[body + 4 : body + 8])[0]
                )
            elif kind == b"trun":
                flags = int.from_bytes(data[body + 1 : body + 4], "big")
                count = struct.unpack(">I", data[body + 4 : body + 8])[0]
                offset = body + 8
                if flags & 0x01:
                    offset += 4
                if flags & 0x04:
                    offset += 4
                per_sample = 4 * sum(bool(flags & bit) for bit in (0x100, 0x200, 0x400, 0x800))
                if not flags & 0x100:
                    # No per-sample durations: the count is a number, not a loop —
                    # a forged 2^32 count must not pin the worker (fuzzed 2026-10-09).
                    total += count * duration_default
                    continue
                # Never more samples than the box holds bytes for.
                count = min(count, max(0, (stop - offset) // per_sample))
                for index in range(count):
                    at = offset + index * per_sample
                    total += struct.unpack(">I", data[at : at + 4])[0]
        begin = running if base is None else base
        running = begin + total
        fragments_end = max(fragments_end, running)

    walk(0, len(data))
    if fragments_end and timescale:
        return fragments_end / timescale
    if movie_duration and movie_scale:
        return movie_duration / movie_scale
    return None


def _wav_seconds(data: bytes) -> float | None:
    byte_rate = 0
    for kind, body, stop in _riff_chunks(data):
        if kind == b"fmt " and stop - body >= 12:
            byte_rate = struct.unpack("<I", data[body + 8 : body + 12])[0]
        elif kind == b"data" and byte_rate:
            return (stop - body) / byte_rate
    return None


def _riff_chunks(data: bytes):
    pos = 12
    while pos + 8 <= len(data):
        kind = data[pos : pos + 4]
        size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        body = pos + 8
        yield kind, body, min(body + size, len(data))
        pos = body + size + (size & 1)


def audio_seconds(data: bytes) -> float | None:
    """The recording's length in seconds, or ``None`` when the container is not
    one of the two above or cannot be read."""

    if not data or len(data) < 12:
        return None
    try:
        if data[:4] == b"\x1a\x45\xdf\xa3":
            seconds = _webm_seconds(data)
        elif data[4:8] == b"ftyp":
            seconds = _mp4_seconds(data)
        elif data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            seconds = _wav_seconds(data)
        else:
            return None
    except (struct.error, IndexError, ValueError, OverflowError):
        return None
    if seconds is None or not (0 <= seconds < 24 * 3600):
        return None
    return float(seconds)
