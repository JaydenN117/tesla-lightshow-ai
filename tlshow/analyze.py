"""Reverse-engineer an existing show: what lights it uses, how long pulses are,
how tightly it follows the music. Used to learn design rules from good shows."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from .audio import Analysis
from .channels import CHANNELS, CLOSURES, NAMES, decode_closure, decode_light
from .fseq import Fseq


def _runs(on: np.ndarray) -> list[tuple[int, int]]:
    """(start, length) of True runs."""
    d = np.diff(np.r_[0, on.astype(np.int8), 0])
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return list(zip(starts, ends - starts))


def light_events(seq: Fseq, max_ch: int = 30) -> np.ndarray:
    """Times (s) where any light channel switches on / starts a ramp (unique frames)."""
    rises = set()
    for ch in range(1, max_ch + 1):
        col = seq.channel(ch).astype(int)
        prev = np.r_[0, col[:-1]]
        rises.update(np.flatnonzero((col != prev) & (col > 127)).tolist())
    return np.array(sorted(rises)) * seq.step_ms / 1000


def alignment(events: np.ndarray, targets: list[float], tol: float = 0.05) -> float:
    if len(events) == 0 or len(targets) == 0:
        return 0.0
    t = np.asarray(targets)
    idx = np.clip(np.searchsorted(t, events), 1, len(t) - 1)
    d = np.minimum(np.abs(events - t[idx - 1]), np.abs(events - t[idx]))
    return float((d <= tol).mean())


def analyze_show(seq: Fseq, music: Analysis | None = None) -> dict:
    dt = seq.step_ms / 1000
    rep: dict = {"duration_s": round(seq.duration_s, 2), "step_ms": seq.step_ms,
                 "channels": seq.n_channels, "lights": {}, "closures": {}}
    pulses_all: list[float] = []
    ramp_use: Counter = Counter()
    for ch in range(1, 31):
        col = seq.channel(ch)
        if not col.any():
            continue
        on = col > 127
        runs = _runs(on)
        lens = [n * dt for _s, n in runs]
        pulses_all += lens
        for v, c in Counter(col.tolist()).items():
            if v not in (0, 255):
                d, r = decode_light(v)
                ramp_use[f"{d}_{r}ms"] += c
        rep["lights"][NAMES[ch]] = {
            "duty": round(float(on.mean()), 3), "pulses": len(runs),
            "median_pulse_ms": round(float(np.median(lens)) * 1000) if lens else 0,
        }
    for name in CLOSURES:
        col = seq.channel(CHANNELS[name])
        if not col.any():
            continue
        prev = np.r_[0, col[:-1]]
        cmds = [decode_closure(int(v)) for v in col[(col != prev) & (col != 0)]]
        rep["closures"][name] = dict(Counter(cmds))
    p = np.array(pulses_all) if pulses_all else np.array([0.0])
    rep["pulse_ms"] = {q: round(float(np.percentile(p, q)) * 1000) for q in (10, 25, 50, 75, 90)}
    rep["ramp_frames"] = dict(ramp_use)
    # symmetry: how often L and R twins hold the same value
    pairs = [(k, "R" + k[1:]) for k in CHANNELS if k.startswith("L_") and "R" + k[1:] in CHANNELS
             and CHANNELS[k] <= 46]
    same = [float((seq.channel(CHANNELS[a]) == seq.channel(CHANNELS[b])).mean()) for a, b in pairs
            if seq.channel(CHANNELS[a]).any() or seq.channel(CHANNELS[b]).any()]
    rep["lr_symmetry"] = round(float(np.mean(same)), 3) if same else None
    ev = light_events(seq)
    rep["events"] = len(ev)
    rep["events_per_s"] = round(len(ev) / max(seq.duration_s, 1e-3), 2)
    lights_on = np.stack([seq.channel(c) > 127 for c in range(1, 31)], axis=1)
    rep["avg_lights_on"] = round(float(lights_on.sum(axis=1).mean()), 2)
    rep["dark_fraction"] = round(float((lights_on.sum(axis=1) == 0).mean()), 3)
    if music is not None:
        grid8 = sorted(music.beats + [(a + b) / 2 for a, b in zip(music.beats, music.beats[1:])])
        rep["music"] = {"tempo": music.tempo}
        rep["align_beat"] = round(alignment(ev, music.beats), 3)
        rep["align_8th"] = round(alignment(ev, grid8), 3)
        rep["align_accent"] = round(alignment(ev, music.onsets), 3)
        # chance baseline: same events shifted by a quarter beat
        shift = 60 / music.tempo / 4 if music.tempo else 0.1
        rep["align_beat_chance"] = round(alignment(ev + shift, music.beats), 3)
        rep["events_per_beat"] = round(len(ev) / max(len(music.beats), 1), 2)
        # how activity follows loudness
        if len(ev):
            e = np.array([music.energy_at(t) for t in np.arange(0, seq.duration_s, 1.0)])
            hist, _ = np.histogram(ev, bins=np.arange(0, seq.duration_s + 1.0, 1.0))
            k = min(len(e), len(hist))
            if k > 3 and np.std(hist[:k]) > 0 and np.std(e[:k]) > 0:
                rep["activity_vs_energy_corr"] = round(float(np.corrcoef(e[:k], hist[:k])[0, 1]), 3)
    return rep


def format_report(name: str, rep: dict) -> str:
    lines = [f"## {name}", "",
             f"- {rep['duration_s']} s, {rep['step_ms']} ms frames, {rep['channels']} channels",
             f"- light events: {rep['events']} ({rep['events_per_s']}/s)"
             + (f", {rep.get('events_per_beat')} per beat" if 'events_per_beat' in rep else ""),
             f"- pulse length percentiles (ms): {rep['pulse_ms']}",
             f"- avg lights on: {rep['avg_lights_on']}/30, fully dark {rep['dark_fraction']*100:.0f}% of the time",
             f"- L/R symmetry: {rep['lr_symmetry']}",
             f"- ramp levels used (frames): {rep['ramp_frames'] or 'none'}",
             f"- closures: {rep['closures'] or 'none'}"]
    if "align_beat" in rep:
        lines.append(f"- events within 50 ms of: beat {rep['align_beat']:.0%} (chance "
                     f"{rep['align_beat_chance']:.0%}), 8th {rep['align_8th']:.0%}, accent "
                     f"{rep['align_accent']:.0%}; activity~loudness r={rep.get('activity_vs_energy_corr')}")
    top = sorted(rep["lights"].items(), key=lambda kv: -kv[1]["pulses"])[:8]
    lines.append("- busiest channels: " + ", ".join(f"{k} ({v['pulses']}x, {v['median_pulse_ms']}ms)" for k, v in top))
    return "\n".join(lines) + "\n"


def find_audio(fseq_path: Path) -> Path | None:
    for ext in (".wav", ".mp3"):
        p = fseq_path.with_suffix(ext)
        if p.exists():
            return p
    return None
