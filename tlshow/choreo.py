"""Authoring API: place light/closure effects on a timeline and render an FSEQ.

Times are in seconds. Later writes override earlier ones on the same channel
(like stacking effects in xLights), so lay down backgrounds first, accents last.

    show = Show(duration=219.06)
    show.pluck("front", 12.40)               # instant on, 500 ms fade off
    show.fade_in("sig", 0.0, 4.0, ramp=2000)
    show.closure("L_MIRROR", 30.0, "close")
    show.save("lightshow.fseq")
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from . import fseq
from .channels import (CHANNELS, CLOSE, DANCE, FBAR, OFF, OFFROAD, ON, OPEN, RAMP_OFF, RAMP_ON,
                       RBAR, STOP, Profile, model3_2022)

# --------------------------------------------------------------------------
# Groups of channels. "L." / "R." prefixes select one side of any group.
# --------------------------------------------------------------------------
_PAIRS = {
    "outer": "OUTER_MAIN", "inner": "INNER_MAIN", "sig": "SIGNATURE", "fturn": "FRONT_TURN",
    "fog": "FRONT_FOG", "repeat": "SIDE_REPEATER", "rturn": "REAR_TURN", "tail": "TAIL",
}
GROUPS: dict[str, list[str]] = {k: [f"L_{v}", f"R_{v}"] for k, v in _PAIRS.items()}
GROUPS["drl"] = ["L_CH4", "L_CH5", "L_CH6", "R_CH4", "R_CH5", "R_CH6"]
GROUPS["park"] = ["L_AUX_PARK", "R_AUX_PARK", "L_SIDE_MARKER", "R_SIDE_MARKER"]
GROUPS["brake"] = ["BRAKE"]
GROUPS["reverse"] = ["REVERSE"]
GROUPS["license"] = ["LICENSE"]
GROUPS["rearfog"] = ["REAR_FOG"]
GROUPS["beams"] = GROUPS["outer"] + GROUPS["inner"]
GROUPS["head"] = GROUPS["beams"] + GROUPS["sig"] + GROUPS["drl"] + GROUPS["fturn"]
GROUPS["front"] = GROUPS["head"] + GROUPS["fog"] + GROUPS["park"]
GROUPS["rear"] = GROUPS["rturn"] + GROUPS["brake"] + GROUPS["tail"] + GROUPS["reverse"] + GROUPS["license"]
GROUPS["turns"] = GROUPS["fturn"] + GROUPS["repeat"] + GROUPS["rturn"]
GROUPS["all"] = GROUPS["front"] + GROUPS["repeat"] + GROUPS["rear"]
for _n in (4, 5, 6):
    GROUPS[f"ch{_n}"] = [f"L_CH{_n}", f"R_CH{_n}"]     # separate lights on Model S/X only
GROUPS["markers"] = ["L_SIDE_MARKER", "R_SIDE_MARKER"]  # Cybertruck: front side markers
GROUPS["fbar"] = list(FBAR)                             # Cybertruck light bars (full brightness)
GROUPS["rbar"] = list(RBAR)
GROUPS["offroad"] = list(OFFROAD)
GROUPS["windows"] = ["L_FRONT_WINDOW", "L_REAR_WINDOW", "R_FRONT_WINDOW", "R_REAR_WINDOW"]
GROUPS["mirrors"] = ["L_MIRROR", "R_MIRROR"]

SHARED = {"BRAKE", "REVERSE", "LICENSE", "REAR_FOG", "LIFTGATE", "CHARGE_PORT"}


def resolve(spec: str | Iterable[str]) -> list[str]:
    """'front', 'L.rear', 'L_TAIL', 'inner+tail' or a list of those -> channel names."""
    if not isinstance(spec, str):
        out: list[str] = []
        for s in spec:
            out += [c for c in resolve(s) if c not in out]
        return out
    if "+" in spec:
        return resolve(spec.split("+"))
    if spec in CHANNELS:
        return [spec]
    side = None
    if spec[:2] in ("L.", "R."):
        side, spec = spec[0], spec[2:]
    if spec not in GROUPS:
        raise KeyError(f"unknown group/channel {spec!r}; groups: {sorted(GROUPS)}")
    chans = GROUPS[spec]
    if side:
        chans = [c for c in chans if c.startswith(side + "_") or c in SHARED]
    return chans


class Show:
    def __init__(self, duration: float, step_ms: int = 20, n_channels: int = 200,
                 profile: Profile | None = None):
        self.step_ms = step_ms
        self.duration = duration
        self.n = int(np.ceil(duration * 1000 / step_ms))
        self.frames = np.zeros((self.n, n_channels), dtype=np.uint8)
        self.profile = profile or model3_2022()

    # ---- low level -------------------------------------------------------
    def f(self, t: float) -> int:
        return int(np.clip(round(t * 1000 / self.step_ms), 0, self.n))

    def set(self, spec, t0: float, t1: float, value: int) -> None:
        a, b = self.f(t0), self.f(t1)
        if b <= a:
            b = min(a + 1, self.n)
        for c in resolve(spec):
            self.frames[a:b, CHANNELS[c] - 1] = value

    def clear(self, spec, t0: float, t1: float) -> None:
        self.set(spec, t0, t1, OFF)

    # ---- lights ----------------------------------------------------------
    def on(self, spec, t0: float, t1: float) -> None:
        """Instant on for [t0, t1), instant off after."""
        self.set(spec, t0, t1, ON)

    def flash(self, spec, t: float, dur: float = 0.12) -> None:
        """Short hard blink. Keep >= 60 ms; ~100-200 ms reads best."""
        self.set(spec, t, t + max(dur, 0.06), ON)

    def pluck(self, spec, t: float, hold: float = 0.06, decay: int = 500) -> None:
        """Instant on, then fade off over `decay` ms - Tesla's most-used move.

        Only ramping lights fade; boolean ones simply switch off after `hold`.
        """
        self.set(spec, t, t + hold, ON)
        self.set(spec, t + hold, t + hold + decay / 1000 + 0.06, RAMP_OFF[decay])

    def fade_in(self, spec, t0: float, t1: float, ramp: int = 1000) -> None:
        """Ramp up over `ramp` ms and hold until t1 (needs t1 - t0 >= ramp + 50 ms to reach 100%)."""
        self.set(spec, t0, t1, RAMP_ON[ramp])

    def fade_out(self, spec, t: float, ramp: int = 1000) -> None:
        """Ramp a light that is already on down to off."""
        self.set(spec, t, t + ramp / 1000 + 0.06, RAMP_OFF[ramp])

    def swell(self, spec, t0: float, t1: float, ramp: int = 1000, release: int = 500) -> None:
        """Fade in, hold, fade out ending at t1."""
        r = release / 1000 + 0.06
        self.fade_in(spec, t0, max(t0 + 0.02, t1 - r), ramp)
        self.set(spec, max(t0 + 0.02, t1 - r), t1, RAMP_OFF[release])

    def strobe(self, spec, t0: float, t1: float, period: float = 0.2, duty: float = 0.5) -> None:
        t = t0
        while t < t1 - 0.03:
            self.flash(spec, t, max(0.06, period * duty))
            t += period

    def chase(self, specs: Sequence, t0: float, step: float, mode: str = "flash",
              dur: float | None = None) -> float:
        """Light each group in turn, `step` seconds apart. Returns end time."""
        for i, s in enumerate(specs):
            t = t0 + i * step
            if mode == "pluck":
                self.pluck(s, t)
            else:
                self.flash(s, t, dur or step * 0.9)
        return t0 + len(specs) * step

    # ---- full-brightness lights (Cybertruck bars, brake, rear turns) -----
    def level(self, spec, t0: float, t1: float, pct: float) -> None:
        """Hold a brightness 0-100%. Only full-brightness lights show in-between levels;
        everything else reads > 50% as on (and ramping lights would read it as a fade command)."""
        self.set(spec, t0, t1, int(np.clip(pct, 0, 100) * 2.55))

    def bar(self, which: str, t0: float, t1: float, fn) -> None:
        """Paint a light bar ('fbar', 'rbar', 'offroad') with fn(t, x) -> 0..1, where t is
        0..1 through the effect and x is 0..1 along the bar (left to right as seen)."""
        nodes = [CHANNELS[c] - 1 for c in GROUPS[which]]
        a, b = self.f(t0), self.f(t1)
        if b <= a:
            return
        t = np.linspace(0, 1, b - a, endpoint=False)[:, None]
        x = np.linspace(0, 1, len(nodes))[None, :]
        v = np.clip(np.broadcast_to(fn(t, x), (b - a, len(nodes))), 0, 1)
        self.frames[a:b, nodes] = np.maximum(self.frames[a:b, nodes], (v * 255).astype(np.uint8))

    def bar_fill(self, which: str, t0: float, t1: float, level: float = 1.0) -> None:
        self.bar(which, t0, t1, lambda t, x: level + 0 * x)

    def bar_pulse(self, which: str, t: float, decay: float = 0.4, peak: float = 1.0) -> None:
        """Full bar that dies away over `decay` seconds."""
        self.bar(which, t, t + decay, lambda tt, x: peak * (1 - tt) ** 1.5 + 0 * x)

    def bar_sweep(self, which: str, t0: float, t1: float, direction: str = "out",
                  width: float = 0.18) -> None:
        """A bright band travelling along the bar: out (centre to ends), in, lr, rl."""
        def fn(t, x):
            if direction in ("out", "in"):
                d = np.abs(x - 0.5) * 2
                pos = t if direction == "out" else 1 - t
            else:
                d = x if direction == "lr" else 1 - x
                pos = t
            return np.clip(1 - np.abs(d - pos) / width, 0, 1)
        self.bar(which, t0, t1, fn)

    # ---- closures --------------------------------------------------------
    def closure(self, spec, t: float, action: str, until: float | None = None) -> None:
        """open / close / dance / stop. Open/close only need a short pulse; dance lasts until `until`."""
        val = {"open": OPEN, "close": CLOSE, "dance": DANCE, "stop": STOP}[action]
        end = until if until is not None else t + 0.5
        self.set(spec, t, end, val)

    # ---- interior --------------------------------------------------------
    def rgb(self, t0: float, t1: float, color: str | tuple, fade_ms: int = 0) -> None:
        """Centre display (and accent lights if fitted) colour. color '#rrggbb' or (r,g,b) 0-255."""
        if self.frames.shape[1] < 200:
            raise ValueError("RGB needs a 200-channel show")
        if isinstance(color, str):
            color = tuple(int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        a, b = self.f(t0), self.f(t1)
        ramp = np.ones(b - a)
        k = min(int(fade_ms / self.step_ms), b - a)
        if k > 0:
            ramp[:k] = np.linspace(0, 1, k)
        for base in (176, 179, 182, 185, 188, 191):
            for j in range(3):
                self.frames[a:b, base - 1 + j] = (np.asarray(color[j]) * ramp).astype(np.uint8)

    # ---- output ----------------------------------------------------------
    def to_fseq(self) -> fseq.Fseq:
        return fseq.Fseq(self.frames.copy(), self.step_ms)

    def save(self, path, media_file: str = "lightshow.wav") -> None:
        fseq.write(path, self.to_fseq(), media_file)
