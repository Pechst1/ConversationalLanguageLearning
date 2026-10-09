"""The recording's length is read from its container (2026-10-09).

Fixtures are real ``MediaRecorder`` output of a 440 Hz tone, recorded with the
app's 32 kbit/s request: Chrome (WebM/Opus) and iOS 26 Safari in the simulator
(WebM/Opus and fragmented MP4/AAC), once as one chunk and once sliced every
second (``start(1000)``). iOS Safari's Opus ran at 6.2 kB/s and its AAC at
~20 kB/s against the 4 kB/s the byte estimate assumed.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.services.audio_duration import audio_seconds
from app.services.transcription_cost import (
    MAX_PLAUSIBLE_BYTES_PER_SECOND,
    estimate_audio_seconds,
    estimate_transcription_cost_usd,
)

AUDIO = Path(__file__).parent / "fixtures" / "audio"


@pytest.mark.parametrize(
    ("name", "seconds"),
    [
        ("chrome-webm-3s.webm", 3.0),
        ("chrome-webm-4s-sliced.webm", 4.0),
        ("ios-webm-3s.webm", 3.0),
        ("ios-webm-4s-sliced.webm", 4.0),
        ("ios-mp4-3s.mp4", 3.0),
        ("ios-mp4-4s-sliced.mp4", 4.0),
    ],
)
def test_real_recordings_read_their_own_length(name, seconds):
    assert audio_seconds((AUDIO / name).read_bytes()) == pytest.approx(seconds, abs=0.15)


def test_a_wav_reads_its_byte_rate():
    rate, secs = 16000, 2
    data = b"\x00\x00" * rate * secs
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    wav = (
        b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
        + b"fmt " + struct.pack("<I", len(fmt)) + fmt
        + b"data" + struct.pack("<I", len(data)) + data
    )
    assert audio_seconds(wav) == pytest.approx(2.0)


@pytest.mark.parametrize("junk", [b"", b"abc", b"\x1a\x45\xdf\xa3\xff\xff", b"\x00\x00\x00\x08ftyp", b"x" * 400])
def test_what_cannot_be_read_is_none(junk):
    assert audio_seconds(junk) is None


def test_a_measured_length_wins_over_the_byte_rate_but_not_below_the_floor():
    # 25 s of iOS Opus (6.2 kB/s): by bytes at 4 kB/s it read as 38.5 s.
    ios = 25 * 6164
    assert estimate_audio_seconds(ios, "audio/webm", measured_seconds=25.0) == 25.0
    assert estimate_audio_seconds(ios, "audio/webm") > 35
    # A large file that declares itself short is sized by the fastest recorder.
    big = 30 * MAX_PLAUSIBLE_BYTES_PER_SECOND
    assert estimate_audio_seconds(big, "audio/webm", measured_seconds=1.0) == pytest.approx(30.0)
    assert estimate_transcription_cost_usd(ios, "audio/webm", measured_seconds=25.0) == pytest.approx(
        0.0025
    )


def test_an_m4a_branded_upload_is_named_m4a_for_whisper(monkeypatch):
    import httpx

    from app.services import llm_service

    sent = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, files=None, data=None, headers=None):
            sent["name"] = files["file"][0]
            return httpx.Response(200, json={"text": "ok"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm_service.httpx, "Client", FakeClient)
    provider = llm_service.OpenAIProvider(api_key="k", model="gpt-5-mini")
    m4a = b"\x00\x00\x00\x1cftypM4A \x00\x00\x00\x00" + b"\x00" * 32
    provider.transcribe_audio(m4a, filename="blob", content_type="audio/mp4")
    assert sent["name"] == "audio.m4a"
    iso5 = (AUDIO / "ios-mp4-3s.mp4").read_bytes()
    provider.transcribe_audio(iso5, filename="blob", content_type="audio/mp4")
    assert sent["name"] == "audio.mp4"


def _forged_trun_count(data: bytes, count: int) -> bytes:
    """The first trun's sample_count set to ``count`` and its per-sample duration flag cleared."""

    at = data.index(b"trun")
    flags = int.from_bytes(data[at + 5 : at + 8], "big") & ~0x100
    return data[: at + 5] + flags.to_bytes(3, "big") + count.to_bytes(4, "big") + data[at + 12 :]


def test_a_forged_sample_count_neither_hangs_nor_raises():
    import time

    data = _forged_trun_count((AUDIO / "ios-mp4-3s.mp4").read_bytes(), 0xFFFFFFFF)
    started = time.perf_counter()
    audio_seconds(data)  # an implausible length is None; the point is it returns
    assert time.perf_counter() - started < 0.5


def test_an_oversized_webm_timecode_scale_is_ignored():
    data = (AUDIO / "chrome-webm-3s.webm").read_bytes()
    at = data.index(bytes.fromhex("2ad7b1"))
    # Size vint 0x88 = 8 bytes → 0xff: a 127-byte scale integer of 0xff.
    forged = data[: at + 3] + b"\xff" + b"\xff" * 127 + data[at + 3 + 1 + data[at + 3] - 0x80 :]
    assert audio_seconds(forged) is None or audio_seconds(forged) >= 0


def test_mutated_recordings_never_raise_and_stay_fast():
    import random
    import time

    rng = random.Random(20261009)
    for path in sorted(AUDIO.iterdir()):
        base = path.read_bytes()
        for _ in range(150):
            data = bytearray(base)
            for _ in range(rng.randint(1, 30)):
                data[rng.randrange(len(data))] = rng.randrange(256)
            started = time.perf_counter()
            result = audio_seconds(bytes(data))
            assert result is None or 0 <= result < 86400
            assert time.perf_counter() - started < 0.5, path.name
