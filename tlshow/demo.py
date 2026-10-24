"""A copyright-free demo song, synthesised from scratch, for trying the whole workflow.

120 bpm, 56 bars (~1:54): pad intro, verse (kick/snare/hats), chorus (adds bass and
chords), a one-beat silence before the last chorus, and a final hit.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SR = 44100
BPM = 120.0
BEAT = 60 / BPM
BAR = 4 * BEAT
# (name, bars)
FORM = [("intro", 8), ("verse", 8), ("chorus", 8), ("verse", 8), ("chorus", 8),
        ("break", 4), ("chorus", 8), ("outro", 4)]


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _kick(n=int(0.35 * SR)):
    t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.12)


def _snare(rng, n=int(0.25 * SR)):
    t = np.arange(n) / SR
    return (0.6 * rng.standard_normal(n) + 0.4 * np.sin(2 * np.pi * 190 * t)) * _env(n, 0.001, 0.07)


def _hat(rng, n=int(0.06 * SR)):
    x = rng.standard_normal(n)
    x = np.diff(np.r_[0, x])  # crude high-pass
    return x * _env(n, 0.0005, 0.015)


def _tone(freqs, dur, kind="saw"):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in freqs:
        ph = (t * f) % 1.0
        out += (2 * ph - 1) if kind == "saw" else np.sin(2 * np.pi * f * t)
    return out / max(len(freqs), 1)


def render(path: str | Path) -> Path:
    import soundfile as sf

    rng = np.random.default_rng(7)
    total = sum(b for _n, b in FORM) * BAR + 2.0
    mix = np.zeros(int(total * SR) + SR)
    kick, snare = _kick(), _snare(rng)
    chords = [[110, 130.8, 164.8], [87.3, 110, 130.8], [98, 123.5, 146.8], [82.4, 103.8, 123.5]]

    def add(sig, t, gain):
        i = int(t * SR)
        mix[i:i + len(sig)] += gain * sig[: len(mix) - i]

    t = 0.0
    for name, bars in FORM:
        for b in range(bars):
            bar_t = t + b * BAR
            ch = chords[b % 4]
            if name in ("intro", "outro", "chorus", "verse"):
                pad = _tone([f * 2 for f in ch], BAR, "sine") * _env(int(BAR * SR), 0.4, 3.0)
                add(pad, bar_t, 0.18 if name == "intro" else 0.1)
            if name == "break":
                if b == bars - 1:
                    continue  # one bar of silence before the last chorus
                add(_tone([f * 2 for f in ch], BAR, "sine") * _env(int(BAR * SR), 0.05, 0.6), bar_t, 0.25)
                continue
            for k in range(4):
                bt = bar_t + k * BEAT
                if name != "intro" or b >= 4:
                    add(_hat(rng), bt + BEAT / 2, 0.25)
                if name == "intro":
                    if b >= 6:
                        add(kick, bt, 0.7)
                    continue
                if name == "outro" and b > 0:
                    continue
                add(kick, bt, 0.9 if k in (0, 2) or name == "chorus" else 0.0)
                if k in (1, 3):
                    add(snare, bt, 0.6)
                add(_hat(rng), bt, 0.2)
                if name == "chorus":
                    add(_tone([ch[0] / 2], BEAT * 0.9, "saw") * _env(int(BEAT * 0.9 * SR), 0.005, 0.25), bt, 0.35)
            if name == "chorus":
                add(_tone(ch, BAR, "saw") * _env(int(BAR * SR), 0.01, 1.5), bar_t, 0.12)
        t += bars * BAR
    add(kick, t, 1.0)
    add(_tone(chords[0], 2.0, "saw") * _env(int(2.0 * SR), 0.005, 0.6), t, 0.3)
    mix = mix[: int((t + 2.0) * SR)]
    mix = 0.9 * mix / np.max(np.abs(mix))
    stereo = np.stack([mix, mix], axis=1)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, stereo, SR, subtype="PCM_16")
    return path
