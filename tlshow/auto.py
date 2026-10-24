"""Automatic first-draft choreography from a music analysis.

The draft follows rules learned from Tesla's own example shows (see
.claude/skills/tesla-lightshow/reference/learned-from-shows.md):
  * hits land on the beat grid; 1.5-4 light events per beat in busy parts
  * the signature move is "pluck": instant on + 500 ms fade off
  * contrast: the car is dark a large share of the time, big moments use everything
  * repeated sections (same label) get the same look so the show feels composed
  * closures are spent sparingly and inside their command limits

It is a starting point: write a per-song script that calls `build()` and then
layers hand-placed moments on top (see shows/*/show.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .audio import Analysis, Section
from .channels import Profile
from .choreo import Show

FIRE = ["#ff2a00", "#ff7a00", "#ffb300", "#ff0040", "#ffd27a"]


@dataclass
class Options:
    closures: bool = True
    trunk: bool | None = None    # None: use the trunk if the car's profile has a powered one
    charge_port: bool = True
    rgb: bool = True
    palette: tuple[str, ...] = tuple(FIRE)
    intro_glow: bool = True
    # per-section overrides by index: "low" | "mid" | "high" | "break" | "solo" | "hold"
    looks: dict[int, str] = field(default_factory=dict)
    profile: Profile | None = None   # default: the car in car.json


class Ctx:
    def __init__(self, show: Show, a: Analysis):
        self.s, self.a = show, a
        self.beats = np.asarray(a.beats)
        db = np.asarray(a.downbeats)
        # position of every beat within its bar (0 = downbeat)
        self.bar_pos = np.zeros(len(self.beats), dtype=int)
        if len(db):
            first = int(np.argmin(np.abs(self.beats - db[0])))
            self.bar_pos = (np.arange(len(self.beats)) - first) % 4
        self.beat_len = float(np.median(np.diff(self.beats))) if len(self.beats) > 1 else 0.5
        self.accents = dict(zip(np.round(a.onsets, 3), a.onset_strength))

    def beats_in(self, sec: Section) -> list[tuple[int, float]]:
        return [(i, float(t)) for i, t in enumerate(self.beats) if sec.start <= t < sec.end - 0.05]

    def accent(self, t: float, tol: float = 0.04) -> float:
        best = 0.0
        for k, v in self.accents.items():
            if abs(k - t) <= tol:
                best = max(best, v)
        return best

    def near(self, times, t0, t1):
        return [float(t) for t in times if t0 <= t < t1]


# --------------------------------------------------------------------------
# beat patterns: (ctx, beat index in section, absolute beat index, time, intensity)
# --------------------------------------------------------------------------

def p_pingpong(c: Ctx, k: int, i: int, t: float, hi: bool) -> None:
    side = "L" if k % 2 == 0 else "R"
    c.s.pluck([f"{side}.inner", f"{side}.sig", f"{side}.drl"], t)
    c.s.flash([f"{side}.tail", f"{side}.repeat"], t, 0.14)
    if hi:
        c.s.flash([f"{side}.outer", f"{side}.rturn"], t, 0.12)


def p_frontback(c: Ctx, k: int, i: int, t: float, hi: bool) -> None:
    if k % 2 == 0:
        c.s.pluck(["inner", "sig", "drl", "fturn"], t)
        if hi:
            c.s.flash("outer", t, 0.12)
    else:
        c.s.flash(["tail", "brake"] + (["rturn", "reverse"] if hi else []), t, 0.14)


def p_inout(c: Ctx, k: int, i: int, t: float, hi: bool) -> None:
    steps = [["sig", "drl"], ["inner"], ["outer"], ["fog", "fturn"]]
    c.s.pluck(steps[k % 4], t) if k % 4 != 2 else c.s.flash(steps[2], t, 0.15)
    if hi:
        c.s.flash(["tail", "license"] if k % 2 else ["rturn"], t, 0.12)


def p_stack(c: Ctx, k: int, i: int, t: float, hi: bool) -> None:
    pos = c.bar_pos[i]
    layers = [["sig", "drl"], ["inner"], ["outer", "fturn"], ["fog", "tail", "rturn"]]
    on = [g for layer in layers[: pos + 1] for g in layer]
    c.s.pluck(on, t, hold=0.12)
    if hi and pos == 3:
        c.s.flash(["brake", "reverse"], t, 0.15)


PATTERNS = [p_pingpong, p_frontback, p_inout, p_stack]


# --------------------------------------------------------------------------
# section looks
# --------------------------------------------------------------------------

def look_low(c: Ctx, sec: Section) -> None:
    s = c.s
    for k, (i, t) in enumerate(c.beats_in(sec)):
        if c.bar_pos[i] == 0:
            bar_end = min(t + 4 * c.beat_len, sec.end)
            s.swell(["sig", "drl"], t, bar_end - 0.02, ramp=1000, release=1000)
            s.pluck("fturn", t, decay=1000)
            s.flash("brake", t, 0.12)
        elif c.bar_pos[i] == 2:
            s.pluck(["inner"], t, decay=1000)
            s.flash("tail", t, 0.12)


def _phrase_patterns(label_idx: int) -> list:
    """Two patterns per section label, alternating every 4-bar phrase.

    Same label -> same sequence, so a repeated chorus looks the same each time.
    """
    a = PATTERNS[label_idx % len(PATTERNS)]
    b = PATTERNS[(label_idx + 1) % len(PATTERNS)]
    return [a, b]


def _bars(c: Ctx, beats: list[tuple[int, float]]) -> list[int]:
    """Bar number (from 0) of each beat inside the section."""
    out, bar = [], -1
    for i, _t in beats:
        if c.bar_pos[i] == 0 or bar < 0:
            bar += 1
        out.append(bar)
    return out


def _offbeats(c: Ctx, sec: Section, t: float, k: int, thresh: float, groups: list,
              always: list | None = None) -> None:
    """Accent the & (and the 16ths around it) when the music has a hit there.

    `always` drives a small light on every & that has no accent (keeps loud parts moving).
    """
    for frac, g in ((0.5, groups[k % len(groups)]), (0.25, ["brake"]), (0.75, ["brake"])):
        x = t + c.beat_len * frac
        if x >= sec.end - 0.05:
            continue
        need = thresh if frac == 0.5 else thresh + 0.25
        if c.accent(x) > need:
            c.s.flash(g, x, 0.07)
        elif frac == 0.5 and always:
            c.s.flash(always[k % len(always)], x, 0.08)


def look_mid(c: Ctx, sec: Section, label_idx: int) -> None:
    s = c.s
    beats = c.beats_in(sec)
    pats = _phrase_patterns(label_idx)
    for k, ((i, t), bar) in enumerate(zip(beats, _bars(c, beats))):
        pats[(bar // 4) % 2](c, k, i, t, False)
        if c.bar_pos[i] == 0:
            s.flash("park", t, 0.2)
        side = "L" if k % 2 else "R"
        _offbeats(c, sec, t, k, 0.35, [[f"{side}.repeat"], [f"{side}.fog", f"{side}.tail"]])


def look_high(c: Ctx, sec: Section, label_idx: int) -> None:
    s = c.s
    beats = c.beats_in(sec)
    pats = _phrase_patterns(label_idx)
    for k, ((i, t), bar) in enumerate(zip(beats, _bars(c, beats))):
        pos = c.bar_pos[i]
        if bar % 4 == 3 and pos >= 2:
            # end of a 4-bar phrase: amber sweep front -> side -> rear on the 16ths
            step = c.beat_len / 4
            s.chase(["fturn", "repeat", "rturn", "repeat"], t, step, dur=step * 0.9)
            continue
        if pos == 0:
            s.flash(["outer", "fog", "park", "brake", "tail", "reverse"], t, 0.14)
            s.pluck(["inner", "sig", "drl", "fturn"], t, hold=0.1)
        else:
            pats[(bar // 4) % 2](c, k, i, t, True)
        _offbeats(c, sec, t, k, 0.3, [["outer"], ["fog", "license"], ["L.repeat", "R.tail"],
                                     ["R.repeat", "L.tail"]], always=[["L.repeat"], ["R.repeat"]])


def look_break(c: Ctx, sec: Section) -> None:
    """Breakdown / drum break: car mostly dark, hard hits only where the music hits,
    16th-note strobe on the last beat to launch the next section."""
    s = c.s
    s.clear("all", sec.start, sec.end)
    accents = [(t, v) for t, v in zip(c.a.onsets, c.a.onset_strength) if sec.start <= t < sec.end - c.beat_len]
    for n, (t, v) in enumerate(accents):
        if v > 0.25:
            s.flash(["outer", "brake"] if n % 2 == 0 else ["fog", "tail"], t, 0.08)
    last = sec.end - c.beat_len
    if last > sec.start:
        s.strobe(["outer", "fog", "tail", "brake"], last, sec.end - 0.04, period=c.beat_len / 4, duty=0.5)


def look_solo(c: Ctx, sec: Section, label_idx: int) -> None:
    """Guitar solo: the high look plus fast L/R signature flicker on 16th accents."""
    look_high(c, sec, label_idx)
    side = 0
    for t in c.near(c.a.hats + c.a.snares, sec.start, sec.end):
        side ^= 1
        c.s.flash(["L.sig" if side else "R.sig"], t, 0.07)


def look_hold(c: Ctx, sec: Section) -> None:
    """Sustained moment (held chord, ring-out): one slow swell, rear glows, downbeat hits only."""
    s = c.s
    s.clear("all", sec.start, sec.end)
    s.swell(["inner", "sig", "drl", "fturn"], sec.start, sec.end, ramp=2000, release=1000)
    s.on("tail", sec.start, sec.end - 0.1)
    for t in c.near(c.a.downbeats, sec.start, sec.end - 0.3):
        s.flash(["outer", "brake"], t, 0.15)


def hit(c: Ctx, t: float, length: float = 0.25) -> None:
    """Section-change accent: everything on, ramping lights fade out."""
    c.s.on("all", t, t + length)
    c.s.fade_out(["inner", "sig", "drl", "fturn"], t + length, ramp=1000)


def ending(c: Ctx, a: Analysis) -> None:
    s = c.s
    last_db = [d for d in a.downbeats if d < a.duration - 2.5]
    if not last_db:
        return
    t = last_db[-1]
    s.clear("all", t, a.duration)
    s.on("all", t, t + 1.0)
    s.fade_out(["inner", "sig", "drl", "fturn"], t + 1.0, ramp=2000)


def plan_closures(c: Ctx, a: Analysis, o: Options) -> None:
    s = c.s
    highs = [x for n, x in enumerate(a.sections) if o.looks.get(n, x.level) in ("high", "solo")]
    if not highs:
        highs = sorted(a.sections, key=lambda x: -x.energy)[:1]
    # mirrors: fold at the start of each loud section, unfold at its end (<= 16 of 20)
    used = 0
    for sec in highs:
        if used + 2 > 16:
            break
        s.closure("mirrors", sec.start, "close")
        s.closure("mirrors", max(sec.start + 2.5, sec.end - 2.2), "open")
        used += 2
    if "L_FRONT_DOOR_HANDLE" in s.profile.closures:
        # Model S: present the handles with the mirrors (20 commands each)
        for sec in highs[:8]:
            s.closure(["L_FRONT_DOOR_HANDLE", "L_REAR_DOOR_HANDLE", "R_FRONT_DOOR_HANDLE",
                       "R_REAR_DOOR_HANDLE"], sec.start, "open")
            s.closure(["L_FRONT_DOOR_HANDLE", "L_REAR_DOOR_HANDLE", "R_FRONT_DOOR_HANDLE",
                       "R_REAR_DOOR_HANDLE"], max(sec.start + 2.5, sec.end - 2.2), "close")
    by_energy = sorted(a.sections, key=lambda x: -x.energy)
    peak = by_energy[0]
    falcon = "L_FALCON_DOOR" in s.profile.closures and len(a.sections) > 1
    if falcon:
        # Model X: falcon doors get the peak; windows dance elsewhere (moving windows while
        # the doors move can trip pinch protection and stop the show)
        f0 = peak.start
        s.closure(["L_FALCON_DOOR", "R_FALCON_DOOR"], f0, "open")
        fd0, fd1 = f0 + 21.0, min(f0 + 31.0, a.duration - 10.0)
        if fd1 - fd0 >= 3.0:
            s.closure(["L_FALCON_DOOR", "R_FALCON_DOOR"], fd0, "dance", until=fd1)
        s.closure(["L_FALCON_DOOR", "R_FALCON_DOOR"], max(fd1, f0 + 21.0), "close")
        busy = (f0, max(fd1, f0 + 21.0) + 9.0)
        peak_w = next((x for x in by_energy[1:] if x.end <= busy[0] or x.start >= busy[1]), None)
    else:
        peak_w = peak
    # windows dance in the loudest free section (thermal: keep <= ~25 s)
    if peak_w is not None:
        w0 = peak_w.start
        w1 = min(peak_w.end, w0 + 25.0, a.duration - 3.0)
        s.closure("windows", w0, "dance", until=w1)
        s.closure("windows", w1, "close")
    # charge port: open -> rainbow dance in the last loud section -> close (3 commands)
    if o.charge_port:
        # last loud section long enough for open -> dance -> close before the song ends
        long_enough = [x for x in highs if min(x.end, a.duration - 3.0) - x.start >= 10.0]
        last = (long_enough or highs)[-1]
        d0 = last.start
        d1 = min(last.end, d0 + 25.0, a.duration - 3.0)
        s.closure("CHARGE_PORT", max(0.0, d0 - 4.0), "open")
        s.closure("CHARGE_PORT", d0, "dance", until=d1)
        s.closure("CHARGE_PORT", d1, "close")
    trunk = o.trunk if o.trunk is not None else "LIFTGATE" in s.profile.closures
    if trunk and not falcon:
        # open at the peak (~14 s to open fully), dance once it is up, close after (3 of 6)
        t_open = peak.start
        d0 = t_open + 15.0
        d1 = min(d0 + 10.0, a.duration - 6.0)
        s.closure("LIFTGATE", t_open, "open")
        if d1 - d0 >= 3.0:
            s.closure("LIFTGATE", d0, "dance", until=d1)
        s.closure("LIFTGATE", max(d1, t_open + 15.0), "close")


def _has(profile: Profile, key: str) -> bool:
    return any(o.key == key for o in profile.outputs)


def bars_layer(c: Ctx, a: Analysis, looks: list[str]) -> None:
    """Cybertruck light bars: animate them from the same music the lights follow.

    high: front bar sweeps out from the centre on downbeats and pulses on beats, rear bar
    answers on the &; mid: softer pulses on beats; low/hold: slow breathing per bar;
    break: pulses on accents only; solo: sweeps alternate left/right every beat.
    """
    s = c.s
    rear = _has(s.profile, "RBAR")
    for sec, look in zip(a.sections, looks):
        beats = c.beats_in(sec)
        if look in ("low", "hold"):
            for i, t in beats:
                if c.bar_pos[i] == 0:
                    end = min(t + 4 * c.beat_len, sec.end)
                    s.bar("fbar", t, end, lambda tt, x: 0.15 + 0.45 * np.sin(np.pi * tt) + 0 * x)
                    if rear:
                        s.bar("rbar", t, end, lambda tt, x: 0.1 + 0.3 * np.sin(np.pi * tt) + 0 * x)
        elif look == "break":
            for t, v in zip(a.onsets, a.onset_strength):
                if sec.start <= t < sec.end and v > 0.25:
                    s.bar_pulse("fbar", t, 0.2)
                    if rear:
                        s.bar_pulse("rbar", t, 0.2)
        else:
            peak = 0.6 if look == "mid" else 1.0
            for k, (i, t) in enumerate(beats):
                if look == "solo":
                    s.bar_sweep("fbar", t, t + c.beat_len, "lr" if k % 2 else "rl")
                elif c.bar_pos[i] == 0 and look == "high":
                    s.bar_sweep("fbar", t, t + c.beat_len, "out", width=0.25)
                else:
                    s.bar_pulse("fbar", t, c.beat_len * 0.8, peak)
                if rear:
                    off = t + c.beat_len / 2
                    if look in ("high", "solo") and off < sec.end:
                        s.bar_pulse("rbar", off, c.beat_len * 0.45, peak)
                    elif c.bar_pos[i] in (0, 2):
                        s.bar_pulse("rbar", t, c.beat_len * 0.8, peak * 0.8)
        if sec.start > 0 and look != "hold":
            s.bar_fill("fbar", sec.start, sec.start + 0.25)
            if rear:
                s.bar_fill("rbar", sec.start, sec.start + 0.25)
    last = [d for d in a.downbeats if d < a.duration - 2.5]
    if last:
        t = last[-1]
        s.bar("fbar", t, a.duration, lambda tt, x: np.clip(1 - tt * 1.2, 0, 1) + 0 * x)
        if rear:
            s.bar("rbar", t, a.duration, lambda tt, x: np.clip(1 - tt * 1.2, 0, 1) + 0 * x)


def ch456_chases(c: Ctx, a: Analysis, looks: list[str]) -> None:
    """Model S/X: channels 4, 5, 6 are separate lights, so chase them on loud phrase ends."""
    for sec, look in zip(a.sections, looks):
        if look not in ("high", "solo"):
            continue
        for i, t in c.beats_in(sec):
            if c.bar_pos[i] == 3:
                step = c.beat_len / 3
                for n, ch in enumerate(("ch4", "ch5", "ch6")):
                    c.s.flash(ch, t + n * step, step * 0.9)
                # channel 4 leads the fade time for all three: keep it instant here
                c.s.set("ch4", t + 3 * step, t + 3 * step + 0.02, 0)


def build(a: Analysis, show: Show | None = None, opts: Options | None = None) -> Show:
    o = opts or Options()
    if show is None:
        from . import car

        show = Show(a.duration, profile=o.profile or car.profile())
    s = show
    c = Ctx(s, a)
    labels = sorted({x.label for x in a.sections})
    looks: list[str] = []
    for n, sec in enumerate(a.sections):
        li = labels.index(sec.label)
        look = o.looks.get(n)
        if look is None:
            look = "low" if (sec.level == "low" or (n == 0 and o.intro_glow and sec.energy < 0.8)) else sec.level
        looks.append(look)
        if look == "low":
            look_low(c, sec)
        elif look == "mid":
            look_mid(c, sec, li)
        elif look == "break":
            look_break(c, sec)
        elif look == "solo":
            look_solo(c, sec, li)
        elif look == "hold":
            look_hold(c, sec)
        else:
            look_high(c, sec, li)
        if n > 0 and look not in ("hold",):
            hit(c, sec.start)
        if o.rgb and s.frames.shape[1] >= 200:
            col = o.palette[labels.index(sec.label) % len(o.palette)]
            s.rgb(sec.start, sec.end, col, fade_ms=600)
    ending(c, a)
    if _has(s.profile, "FBAR"):
        bars_layer(c, a, looks)
    if _has(s.profile, "L_CH5"):
        ch456_chases(c, a, looks)
    if o.closures:
        plan_closures(c, a, o)
    return s
