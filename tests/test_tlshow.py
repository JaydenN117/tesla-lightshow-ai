import struct

import numpy as np
import pytest

from tlshow import fseq
from tlshow.channels import (CHANNELS, OFF_500, ON, ON_500, decode_closure, decode_light,
                             model3_2022)
from tlshow.choreo import Show, resolve
from tlshow.sim import simulate
from tlshow.validate import official


def test_roundtrip_and_header(tmp_path):
    s = Show(2.0)
    s.flash("front", 0.5, 0.2)
    p = tmp_path / "x.fseq"
    s.save(p)
    b = p.read_bytes()
    assert b[:4] == b"PSEQ"
    off, minor, major = struct.unpack("<HBB", b[4:8])
    assert (major, minor) == (2, 0) and off % 4 == 0
    n_ch, n_fr, step = struct.unpack("<IIB", b[10:19])
    assert (n_ch, n_fr, step) == (200, 100, 20)
    assert b[20] == 0  # uncompressed
    back = fseq.read(p)
    assert np.array_equal(back.frames, s.frames)
    assert official(p)[0][0] == "ok"


def test_value_encoding():
    assert decode_light(ON) == ("on", 0)
    assert decode_light(ON_500) == ("on", 500)
    assert decode_light(178) == ("on", 2000)
    assert decode_light(OFF_500) == ("off", 500)
    assert [decode_closure(v) for v in (0, 63, 127, 191, 255)] == ["idle", "open", "dance", "close", "stop"]


def test_groups_and_sides():
    assert resolve("L.tail") == ["L_TAIL"]
    assert "BRAKE" in resolve("L.rear")
    assert set(resolve("inner+tail")) == {"L_INNER_MAIN", "R_INNER_MAIN", "L_TAIL", "R_TAIL"}
    with pytest.raises(KeyError):
        resolve("nope")


def test_pluck_fades_on_ramping_but_not_boolean():
    s = Show(2.0)
    s.pluck(["inner", "outer"], 0.0, hold=0.1, decay=500)
    sim = simulate(s.to_fseq(), model3_2022())
    inner, outer = sim.lights["L_INNER"], sim.lights["L_OUTER"]
    f = lambda t: int(t / 0.02)
    assert inner[f(0.05)] == 1.0 and outer[f(0.05)] == 1.0
    assert 0.3 < inner[f(0.35)] < 0.7      # half way through a 500 ms fade
    assert outer[f(0.35)] == 0.0           # boolean on projector headlights


def test_model3_or_groups():
    s = Show(1.0)
    s.on("L_AUX_PARK", 0.0, 0.5)
    s.on("R_SIDE_MARKER", 0.5, 1.0)
    sim = simulate(s.to_fseq(), model3_2022())
    assert sim.lights["PARK"][5:45].min() == 1.0  # one shared output stays lit


def test_closure_limits_and_dance_rules():
    s = Show(30.0)
    for k in range(4):
        s.closure("CHARGE_PORT", 1 + 5 * k, "open" if k % 2 == 0 else "close")
    s.closure("LIFTGATE", 25, "dance", until=29)
    sim = simulate(s.to_fseq(), model3_2022())
    cp = sim.closures["CHARGE_PORT"].commands
    assert [ok for _t, _c, ok in cp] == [True, True, True, False]
    assert any("not fully open" in m for _lv, m in sim.messages)


# ---- other cars -----------------------------------------------------------------
from tlshow.channels import build_profile  # noqa: E402


def _sim(show, car):
    return simulate(show.to_fseq(), build_profile(car))


def test_model_s_channel4_leads_fade_for_5_and_6():
    s = Show(3.0)
    s.on("L_CH5", 0.0, 1.0)
    s.set("L_CH4", 1.0, 1.6, 25)          # "fade off 500 ms" placed on channel 4 only
    sim = _sim(s, {"model": "models", "headlights": "projector"})
    ch5 = sim.lights["L_CH5"]
    assert ch5[25] == 1.0
    assert 0.3 < ch5[int(1.25 / 0.02)] < 0.7   # channel 5 fades with channel 4's setting
    assert sim.lights["L_CH4"].max() == 0.0     # channel 4 itself stayed dark


def test_signature_on_off_on_sx_but_fades_on_3y():
    s = Show(2.0)
    s.set("L_SIGNATURE", 0.0, 1.0, 229)       # fade on 500 ms
    f = int(0.2 / 0.02)
    assert _sim(s, {"model": "modelx"}).lights["L_SIG"][f] == 1.0
    assert 0.2 < _sim(s, {"model": "modely"}).lights["L_SIG"][f] < 0.6


def test_reflector_outer_beam_fades():
    s = Show(2.0)
    s.set("L_OUTER_MAIN", 0.0, 1.0, 229)
    f = int(0.2 / 0.02)
    assert 0.2 < _sim(s, {"model": "model3", "headlights": "reflector"}).lights["L_OUTER"][f] < 0.6
    assert _sim(s, {"model": "model3", "headlights": "projector"}).lights["L_OUTER"][f] == 1.0


def test_model_s_park_lights_are_per_side():
    s = Show(1.0)
    s.on("L_AUX_PARK", 0.0, 0.5)
    sim = _sim(s, {"model": "models"})
    assert sim.lights["L_PARK"][10] == 1.0 and sim.lights["R_PARK"][10] == 0.0


def test_cybertruck_bars_and_full_brightness():
    s = Show(2.0)
    s.bar_fill("fbar", 0.0, 1.0, 0.4)
    s.level("BRAKE", 0.0, 1.0, 40)
    s.on("REVERSE", 0.0, 1.0)                 # bed lights: always a 500 ms fade
    sim = _sim(s, {"model": "cybertruck"})
    assert sim.lights["FBAR"].shape[1] == 60
    assert abs(sim.lights["FBAR"][10].mean() - 0.4) < 0.01
    assert abs(sim.lights["BRAKE"][10] - 0.4) < 0.01
    assert 0.3 < sim.lights["BED"][int(0.25 / 0.02)] < 0.7


def test_model_x_doors_and_windows_never_move_together():
    from tlshow.audio import Analysis, Section
    from tlshow.auto import Options, build

    beats = [i * 0.5 for i in range(240)]
    secs = [Section(0, 30, "A", 0.6, "low"), Section(30, 60, "B", 1.0, "high"),
            Section(60, 90, "A", 0.7, "mid"), Section(90, 120, "B", 0.95, "high")]
    a = Analysis(120.0, 120.0, beats, beats[::4], [1.0] * 240, [], [], [], [], [], secs, 0.05,
                 [0.8] * 2400)
    prof = build_profile({"model": "modelx"})
    sim = simulate(build(a, opts=Options(profile=prof)).to_fseq(), prof)
    door = np.array([m != "idle" for m in sim.closures["L_FALCON_DOOR"].mode])
    win = np.array([m != "idle" for m in sim.closures["L_FRONT_WINDOW"].mode])
    assert door.any() and win.any()
    assert not (door & win).any()
    assert not [m for lv, m in sim.messages if lv == "error"]
