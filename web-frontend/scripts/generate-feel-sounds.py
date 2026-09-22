"""WP-76 — synthesise the three feedback sounds (correct, wrong, complete).

Original tones, generated here so there is no licence to track: soft
marimba-like notes (a sine plus a quiet octave, a 6 ms attack and an
exponential decay), mono 16 kHz 16-bit WAV, each under 20 KB, peak at about
-9 dBFS so they sit under speech rather than over it.

Run: `python3 web-frontend/scripts/generate-feel-sounds.py`
"""

from __future__ import annotations

import math
import pathlib
import struct
import wave

RATE = 16_000
PEAK = 0.35  # ≈ -9 dBFS
OUT = pathlib.Path(__file__).resolve().parent.parent / "public" / "sounds"


def note(freq: float, start: float, length: float, decay: float, gain: float = 1.0):
    return (freq, start, length, decay, gain)


def render(notes, duration: float) -> list[float]:
    samples = [0.0] * int(RATE * duration)
    attack = 0.006
    for freq, start, length, decay, gain in notes:
        first = int(start * RATE)
        count = min(int(length * RATE), len(samples) - first)
        for i in range(count):
            t = i / RATE
            env = min(1.0, t / attack) * math.exp(-t / decay)
            # fade the tail to zero so no note ends in a click
            tail = min(1.0, (count - i) / (0.012 * RATE))
            value = math.sin(2 * math.pi * freq * t) + 0.18 * math.sin(4 * math.pi * freq * t)
            samples[first + i] += gain * env * tail * value
    peak = max(1e-9, max(abs(s) for s in samples))
    return [s / peak * PEAK for s in samples]


def write(name: str, samples: list[float]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))
    return path.stat().st_size


SOUNDS = {
    # a rising major third: E5 → G#5, light and quick
    "correct": render([note(659.25, 0.0, 0.16, 0.07), note(830.61, 0.07, 0.19, 0.09)], 0.26),
    # a soft falling step, low and short — a "hm", not a buzzer
    "wrong": render([note(392.0, 0.0, 0.14, 0.06, 0.9), note(329.63, 0.09, 0.2, 0.08, 0.9)], 0.29),
    # the day is done: C5 E5 G5 C6, arpeggiated
    "complete": render(
        [
            note(523.25, 0.0, 0.3, 0.1),
            note(659.25, 0.08, 0.3, 0.1),
            note(783.99, 0.16, 0.3, 0.11),
            note(1046.5, 0.24, 0.34, 0.14),
        ],
        0.58,
    ),
}

if __name__ == "__main__":
    for name, samples in SOUNDS.items():
        size = write(name, samples)
        assert size < 20_000, (name, size)
        print(f"{name}.wav {size} bytes")
