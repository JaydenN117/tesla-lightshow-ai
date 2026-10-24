"""Simulate what a specific car does with an FSEQ: light intensities and closure motion.

This is the engine behind the preview and the validator. It applies the vehicle
rules from Tesla's guide: boolean vs ramping lights, OR'd outputs (Model 3 aux
park/side markers, channels 4-6), channel 4 as ramp leader, closure command
limits and "dance only once open".
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .channels import (CHANNELS, CLOSURE_LIMITS, CLOSURE_MOVE_S, Profile, decode_closure,
                       decode_light)
from .fseq import Fseq

WINDOW_KEYS = {"L_FRONT_WINDOW", "L_REAR_WINDOW", "R_FRONT_WINDOW", "R_REAR_WINDOW"}
DANCERS = WINDOW_KEYS | {"LIFTGATE", "CHARGE_PORT", "L_FALCON_DOOR", "R_FALCON_DOOR"}


@dataclass
class ClosureTrack:
    position: np.ndarray            # 0 closed .. 1 open
    mode: list[str]                 # idle/open/close/dance/stop per frame (effective)
    commands: list[tuple[float, str, bool]] = field(default_factory=list)  # (t, cmd, accepted)


@dataclass
class Simulation:
    step_ms: int
    n_frames: int
    lights: dict[str, np.ndarray]           # output key -> 0..1 per frame ((n, leds) for bars)
    closures: dict[str, ClosureTrack]
    rgb: np.ndarray | None                  # (n, 3) 0..1 centre display colour
    messages: list[tuple[str, str]]         # (level, text)


def _light_track(cols: list[np.ndarray], kind: str, leader: np.ndarray | None, dt: float) -> np.ndarray:
    """Intensity 0..1 per frame for one physical light.

    ramp: the byte is a command (instant/fade on/off). With a leader channel (channel 4
    on every Tesla), on/off comes from the light's own channels and the fade time from
    the leader alone. bool: > 50% is on. level: the byte is the brightness (Cybertruck
    bars, brake, rear turns). ramp500: on/off, always fading over 500 ms (Cybertruck bed).
    """
    n = len(cols[0])
    if kind == "level":
        return np.max(np.stack(cols), axis=0).astype(np.float32) / 255
    out = np.zeros(n, dtype=np.float32)
    level = 0.0
    lut = [decode_light(v) for v in range(256)]
    for i in range(n):
        vals = [int(c[i]) for c in cols]
        if kind == "bool":
            level = 1.0 if max(vals) > 127 else 0.0
        else:
            if kind == "ramp500":
                direction, ramp = ("on" if max(vals) > 127 else "off"), 500
            elif leader is None and len(cols) == 1:
                direction, ramp = lut[vals[0]]
            else:
                direction = "on" if any(lut[v][0] == "on" for v in vals) else "off"
                lv = int(leader[i]) if leader is not None else 0
                ramp = lut[lv][1] if lv != 0 else 0
            if direction == "on":
                level = 1.0 if ramp == 0 else min(1.0, level + dt / ramp)
            else:
                level = 0.0 if ramp == 0 else max(0.0, level - dt / ramp)
        out[i] = level
    return out


def _closure_track(key: str, col: np.ndarray, dt: float, msgs: list) -> ClosureTrack:
    n = len(col)
    move = CLOSURE_MOVE_S.get(key, 3.0) * 1000
    limit = CLOSURE_LIMITS.get(key, 6)
    pos = np.zeros(n, dtype=np.float32)
    modes: list[str] = []
    cmds: list[tuple[float, str, bool]] = []
    # mirrors start unfolded (open); everything else starts closed
    p = 1.0 if key.endswith("MIRROR") else 0.0
    mode, prev, used, dance_t = "idle", "idle", 0, 0.0
    base = 0.0
    for i in range(n):
        cmd = decode_closure(int(col[i]))
        t = i * dt / 1000
        if cmd != prev and cmd != "idle":
            accepted = True
            if cmd in ("open", "close", "dance"):
                if used >= limit:
                    accepted = False
                    msgs.append(("error", f"{key}: {cmd} at {t:.2f}s ignored - limit of {limit} "
                                          "open/dance/close commands reached"))
                else:
                    used += 1
            if cmd == "dance" and accepted:
                if key not in DANCERS:
                    accepted = False
                    msgs.append(("warn", f"{key}: dance at {t:.2f}s - this closure cannot dance"))
                elif key not in WINDOW_KEYS and p < 0.95:
                    accepted = False
                    msgs.append(("warn", f"{key}: dance at {t:.2f}s ignored - closure is not fully "
                                         "open yet (open it first and wait for it to finish)"))
            cmds.append((t, cmd, accepted))
            if accepted:
                mode = cmd
                base = p
                dance_t = 0.0
        elif cmd == "idle" and prev != "idle":
            # idle: finish an open/close in progress, otherwise stop
            mode = mode if mode in ("open", "close") else "idle"
        prev = cmd
        if mode == "open":
            p = min(1.0, p + dt / move)
            if p >= 1.0:
                mode = "idle"
        elif mode == "close":
            p = max(0.0, p - dt / move)
            if p <= 0.0:
                mode = "idle"
        elif mode == "dance":
            dance_t += dt / 1000
            if key in WINDOW_KEYS:
                p = base + 0.3 * (0.5 - 0.5 * np.cos(2 * np.pi * dance_t / 1.6))
            elif key == "CHARGE_PORT":
                p = 1.0
            else:
                p = 1.0 - 0.25 * (0.5 - 0.5 * np.cos(2 * np.pi * dance_t / 2.0))
        pos[i] = p
        modes.append(mode)
    return ClosureTrack(pos, modes, cmds)


def simulate(seq: Fseq, profile: Profile) -> Simulation:
    dt = float(seq.step_ms)
    msgs: list[tuple[str, str]] = []
    lights: dict[str, np.ndarray] = {}
    for o in profile.outputs:
        cols = [seq.channel(CHANNELS[c]) for c in o.channels]
        leader = seq.channel(CHANNELS[o.ramp_leader]) if o.ramp_leader else None
        if o.kind == "bar":
            # one column per LED, brightness = byte value
            lights[o.key] = np.stack(cols, axis=1).astype(np.float32) / 255
        else:
            lights[o.key] = _light_track(cols, o.kind, leader, dt)
    closures = {k: _closure_track(k, seq.channel(CHANNELS[k]), dt, msgs) for k in profile.closures}
    rgb = None
    if seq.n_channels >= 178:
        rgb = seq.frames[:, 175:178].astype(np.float32) / 255
        if not rgb.any():
            rgb = None
    return Simulation(seq.step_ms, seq.n_frames, lights, closures, rgb, msgs)
