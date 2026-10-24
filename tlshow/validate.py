"""Validation: Tesla's official checks plus car-specific and design checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from .analyze import _runs
from .channels import CHANNELS, Profile
from .fseq import Fseq, read
from .sim import simulate


def official(path: str | Path) -> list[tuple[str, str]]:
    """Same rules as teslamotors/light-show validator.py."""
    import struct

    b = Path(path).read_bytes()[:32]
    out: list[tuple[str, str]] = []
    start, minor, major = struct.unpack("<HBB", b[4:8])
    n_ch, n_fr, step = struct.unpack("<IIB", b[10:19])
    if b[:4] != b"PSEQ" or start < 24 or n_fr < 1 or step < 15:
        out.append(("error", "Unknown file format, expected FSEQ v2.0"))
    if n_ch not in (48, 200):
        out.append(("error", f"Expected 48 or 200 channels, got {n_ch}"))
    if b[20] & 0x0F != 0:
        out.append(("error", "Expected file format to be V2 Uncompressed"))
    if n_fr * step / 1000 > 4 * 3600:
        out.append(("error", "Show longer than 4 hours"))
    if major != 2 or minor not in (0, 2):
        out.append(("warn", f"FSEQ version {major}.{minor}; only 2.0 and 2.2 have been validated by Tesla"))
    if not out:
        out.append(("ok", f"Found {n_fr} frames, step time of {step} ms for a total duration of "
                          f"{n_fr * step / 1000:.2f} s"))
    return out


def audio_info(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=sample_rate,channels:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    return {"sample_rate": int(d["streams"][0]["sample_rate"]),
            "duration": float(d["format"]["duration"])}


def check(fseq_path: str | Path, profile: Profile, audio: str | Path | None = None) -> list[tuple[str, str]]:
    msgs = official(fseq_path)
    seq: Fseq = read(fseq_path)
    p = Path(fseq_path)
    if audio is None:
        for ext in (".wav", ".mp3"):
            if p.with_suffix(ext).exists():
                audio = p.with_suffix(ext)
                break
        else:
            msgs.append(("warn", f"no {p.stem}.wav/.mp3 next to the fseq - names must match on the USB stick"))
    if audio is not None:
        info = audio_info(Path(audio))
        if info["sample_rate"] != 44100:
            msgs.append(("error", f"audio is {info['sample_rate']} Hz; the car needs 44.1 kHz to stay in sync"))
        diff = seq.duration_s - info["duration"]
        if diff > 1.0:
            msgs.append(("warn", f"sequence runs {diff:.1f}s past the end of the audio"))
        elif diff < -1.0:
            msgs.append(("info", f"audio continues {-diff:.1f}s after the lights end"))
        if Path(audio).stem != p.stem:
            msgs.append(("warn", f"audio name {Path(audio).name} must match {p.stem} on the USB stick"))

    sim = simulate(seq, profile)
    msgs += sim.messages
    dt = seq.step_ms / 1000

    idle = [name for name in profile.unused_channels if seq.channel(CHANNELS[name]).any()]
    if idle:
        msgs.append(("info", f"{len(idle)} channels have effects that do nothing on {profile.name} "
                             f"({', '.join(idle)}); harmless, and they help the show on other cars"))

    # OR'd outputs: a channel blinks but the physical light stays lit
    for o in profile.outputs:
        if len(o.channels) < 2 or o.kind == "bar":
            continue
        rises = 0
        for c in o.channels:
            col = seq.channel(CHANNELS[c]) > 127
            rises += int(np.sum(col[1:] & ~col[:-1]))
        lit = sim.lights[o.key] > 0.5
        real = int(np.sum(lit[1:] & ~lit[:-1]))
        if rises and real < 0.5 * rises / len(o.channels):
            msgs.append(("warn", f"{o.label}: channels switch on {rises}x but the shared light only "
                                 f"blinks {real}x - leave a gap on all OR'd channels"))

    # pulses that are too short to look good
    for o in profile.outputs:
        if o.kind == "bar":
            continue
        lit = sim.lights[o.key] > 0.5
        short = [n for _s, n in _runs(lit) if n * dt < 0.06]
        if short:
            msgs.append(("info", f"{o.label}: {len(short)} pulses shorter than 60 ms (hard to see)"))

    for key, tr in sim.closures.items():
        dance = sum(1 for m in tr.mode if m == "dance") * dt
        if dance > 30:
            msgs.append(("warn", f"{key}: dances {dance:.0f}s - thermal limits may stop it (keep <= ~30 s)"))
        if key == "CHARGE_PORT":
            opens = [t for t, c, ok in tr.commands if c == "open" and ok]
            closes = [t for t, c, ok in tr.commands if c == "close" and ok]
            for t in opens:
                nxt = [x for x in closes if x > t]
                end = nxt[0] if nxt else seq.duration_s
                if end - t > 120:
                    msgs.append(("warn", f"charge port opened at {t:.1f}s stays open >2 min; the car "
                                         "closes it automatically"))
    return msgs


def report(msgs: list[tuple[str, str]]) -> str:
    icon = {"ok": "OK  ", "info": "info", "warn": "WARN", "error": "ERR "}
    return "\n".join(f"[{icon.get(lv, lv)}] {m}" for lv, m in msgs)


def has_errors(msgs) -> bool:
    return any(lv == "error" for lv, _ in msgs)
