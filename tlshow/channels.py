"""Tesla light show channel map, value encoding and vehicle profiles.

Channel numbers are 1-based, matching the xLights "Model S" controller in
Tesla's official show folder (teslamotors/light-show, xlights_rgbeffects.xml).
A 48-channel show covers lights and closures; a 200-channel show adds the
Cybertruck light bars, suspension and the interior RGB channels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Raw channel map (1-based)
# --------------------------------------------------------------------------

CHANNELS: dict[str, int] = {
    "L_OUTER_MAIN": 1,
    "R_OUTER_MAIN": 2,
    "L_INNER_MAIN": 3,
    "R_INNER_MAIN": 4,
    "L_SIGNATURE": 5,
    "R_SIGNATURE": 6,
    "L_CH4": 7,
    "R_CH4": 8,
    "L_CH5": 9,
    "R_CH5": 10,
    "L_CH6": 11,
    "R_CH6": 12,
    "L_FRONT_TURN": 13,
    "R_FRONT_TURN": 14,
    "L_FRONT_FOG": 15,
    "R_FRONT_FOG": 16,
    "L_AUX_PARK": 17,
    "R_AUX_PARK": 18,
    "L_SIDE_MARKER": 19,
    "R_SIDE_MARKER": 20,
    "L_SIDE_REPEATER": 21,
    "R_SIDE_REPEATER": 22,
    "L_REAR_TURN": 23,
    "R_REAR_TURN": 24,
    "BRAKE": 25,
    "L_TAIL": 26,
    "R_TAIL": 27,
    "REVERSE": 28,
    "REAR_FOG": 29,
    "LICENSE": 30,
    "L_FALCON_DOOR": 31,
    "R_FALCON_DOOR": 32,
    "L_FRONT_DOOR": 33,
    "R_FRONT_DOOR": 34,
    "L_MIRROR": 35,
    "R_MIRROR": 36,
    "L_FRONT_WINDOW": 37,
    "L_REAR_WINDOW": 38,
    "R_FRONT_WINDOW": 39,
    "R_REAR_WINDOW": 40,
    "LIFTGATE": 41,  # trunk on Model 3, frunk on Cybertruck
    "L_FRONT_DOOR_HANDLE": 42,
    "L_REAR_DOOR_HANDLE": 43,
    "R_FRONT_DOOR_HANDLE": 44,
    "R_REAR_DOOR_HANDLE": 45,
    "CHARGE_PORT": 46,
    # 200-channel extensions
    "SUSPENSION": 175,
    "DISPLAY_R": 176,
    "DISPLAY_G": 177,
    "DISPLAY_B": 178,
    "R_REAR_RGB_R": 179,
    "R_FRONT_RGB_R": 182,
    "CENTER_FRONT_RGB_R": 185,
    "L_FRONT_RGB_R": 188,
    "L_REAR_RGB_R": 191,
}
FRONT_LIGHT_BAR = range(47, 107)  # Cybertruck, 60 single-colour nodes, left to right seen from the front
REAR_LIGHT_BAR = range(111, 163)  # Cybertruck, 52 nodes on the tailgate, left to right seen from behind
OFFROAD_LIGHT_BAR = range(167, 173)
FBAR = [f"FBAR_{i:02d}" for i in range(1, 61)]
RBAR = [f"RBAR_{i:02d}" for i in range(1, 53)]
OFFROAD = [f"OFFROAD_{i}" for i in range(1, 7)]
CHANNELS.update(zip(FBAR, FRONT_LIGHT_BAR))
CHANNELS.update(zip(RBAR, REAR_LIGHT_BAR))
CHANNELS.update(zip(OFFROAD, OFFROAD_LIGHT_BAR))

NAMES: dict[int, str] = {v: k for k, v in CHANNELS.items()}

# xLights model names, used when writing .xsq files that open in Tesla's show folder.
XLIGHTS_MODEL_NAMES: dict[str, str] = {
    "L_OUTER_MAIN": "Left Outer Main Beam",
    "R_OUTER_MAIN": "Right Outer Main Beam",
    "L_INNER_MAIN": "Left Inner Main Beam",
    "R_INNER_MAIN": "Right Inner Main Beam",
    "L_SIGNATURE": "Left Signature",
    "R_SIGNATURE": "Right Signature",
    "L_CH4": "Left Channel 4",
    "R_CH4": "Right Channel 4",
    "L_CH5": "Left Channel 5",
    "R_CH5": "Right Channel 5",
    "L_CH6": "Left Channel 6",
    "R_CH6": "Right Channel 6",
    "L_FRONT_TURN": "Left Front Turn",
    "R_FRONT_TURN": "Right Front Turn",
    "L_FRONT_FOG": "Left Front Fog",
    "R_FRONT_FOG": "Right Front Fog",
    "L_AUX_PARK": "Left Aux Park",
    "R_AUX_PARK": "Right Aux Park",
    "L_SIDE_MARKER": "Left Side Marker",
    "R_SIDE_MARKER": "Right Side Marker",
    "L_SIDE_REPEATER": "Left Side Repeater",
    "R_SIDE_REPEATER": "Right Side Repeater",
    "L_REAR_TURN": "Left Rear Turn",
    "R_REAR_TURN": "Right Rear Turn",
    "BRAKE": "Brake Lights",
    "L_TAIL": "Left Tail",
    "R_TAIL": "Right Tail",
    "REVERSE": "Reverse Lights",
    "REAR_FOG": "Rear Fog Lights",
    "LICENSE": "License Plate",
    "L_FALCON_DOOR": "Left Falcon Door",
    "R_FALCON_DOOR": "Right Falcon Door",
    "L_FRONT_DOOR": "Left Front Door",
    "R_FRONT_DOOR": "Right Front Door",
    "L_MIRROR": "Left Mirror",
    "R_MIRROR": "Right Mirror",
    "L_FRONT_WINDOW": "Left Front Window",
    "L_REAR_WINDOW": "Left Rear Window",
    "R_FRONT_WINDOW": "Right Front Window",
    "R_REAR_WINDOW": "Right Rear Window",
    "LIFTGATE": "Liftgate",
    "L_FRONT_DOOR_HANDLE": "Left Front Door Handle",
    "L_REAR_DOOR_HANDLE": "Left Rear Door Handle",
    "R_FRONT_DOOR_HANDLE": "Right Front Door Handle",
    "R_REAR_DOOR_HANDLE": "Right Rear Door Handle",
    "CHARGE_PORT": "Charge Port",
    "DISPLAY_R": "Center Front Display",
}

CLOSURES = [
    "L_FALCON_DOOR", "R_FALCON_DOOR", "L_FRONT_DOOR", "R_FRONT_DOOR",
    "L_MIRROR", "R_MIRROR", "L_FRONT_WINDOW", "L_REAR_WINDOW",
    "R_FRONT_WINDOW", "R_REAR_WINDOW", "LIFTGATE", "L_FRONT_DOOR_HANDLE",
    "L_REAR_DOOR_HANDLE", "R_FRONT_DOOR_HANDLE", "R_REAR_DOOR_HANDLE", "CHARGE_PORT",
]

# Open/Dance/Close commands allowed per closure per show (Stop and Idle are free).
CLOSURE_LIMITS: dict[str, int] = {
    "LIFTGATE": 6, "L_MIRROR": 20, "R_MIRROR": 20, "CHARGE_PORT": 3,
    "L_FRONT_WINDOW": 6, "L_REAR_WINDOW": 6, "R_FRONT_WINDOW": 6, "R_REAR_WINDOW": 6,
    "L_FRONT_DOOR_HANDLE": 20, "L_REAR_DOOR_HANDLE": 20,
    "R_FRONT_DOOR_HANDLE": 20, "R_REAR_DOOR_HANDLE": 20,
    "L_FRONT_DOOR": 6, "R_FRONT_DOOR": 6, "L_FALCON_DOOR": 6, "R_FALCON_DOOR": 6,
}

# Approximate seconds for a full movement (official table; trunk is a guess for Model 3).
CLOSURE_MOVE_S: dict[str, float] = {
    "LIFTGATE": 14.0, "L_MIRROR": 2.0, "R_MIRROR": 2.0, "CHARGE_PORT": 2.0,
    "L_FRONT_WINDOW": 4.0, "L_REAR_WINDOW": 4.0, "R_FRONT_WINDOW": 4.0, "R_REAR_WINDOW": 4.0,
    "L_FALCON_DOOR": 20.0, "R_FALCON_DOOR": 20.0, "L_FRONT_DOOR": 22.0, "R_FRONT_DOOR": 22.0,
    "L_FRONT_DOOR_HANDLE": 2.0, "L_REAR_DOOR_HANDLE": 2.0, "R_FRONT_DOOR_HANDLE": 2.0,
    "R_REAR_DOOR_HANDLE": 2.0,
}

# --------------------------------------------------------------------------
# Value encoding
# --------------------------------------------------------------------------
# xLights writes brightness b% as floor(b * 2.55). The car decodes the level as
# a command. Ramp durations below follow Tesla's own example shows and the
# official xlights_keybindings.xml (E=90%, D=80%, C=70%), NOT the README table,
# which lists the fade-on percentages in the opposite order. Evidence: in Tesla's
# example .xsq files 90% effects have a median length of ~350 ms (a 500 ms fade
# is the only thing that makes sense there) while 70% effects are ~1.8-2.2 s. Confirmed on a
# 2022 Model 3 from video: a 70% effect ramped for 2.0 s (see learned-from-shows.md).

OFF = 0
OFF_500 = 25    # 10%  W
OFF_1000 = 51   # 20%  S
OFF_2000 = 76   # 30%  X
ON_2000 = 178   # 70%  C
ON_1000 = 204   # 80%  D
ON_500 = 229    # 90%  E
ON = 255        # 100% F

RAMP_ON = {500: ON_500, 1000: ON_1000, 2000: ON_2000}
RAMP_OFF = {500: OFF_500, 1000: OFF_1000, 2000: OFF_2000}

# closure commands
IDLE = 0
OPEN = 63       # 25%  Q
DANCE = 127     # 50%  A
CLOSE = 191     # 75%  Z
STOP = 255      # 100% F

LIGHT_LEVELS = [(OFF, "off", 0), (OFF_500, "off", 500), (OFF_1000, "off", 1000),
                (OFF_2000, "off", 2000), (ON_2000, "on", 2000), (ON_1000, "on", 1000),
                (ON_500, "on", 500), (ON, "on", 0)]


def decode_light(value: int) -> tuple[str, int]:
    """Map a raw channel byte to (direction, ramp_ms) using the nearest level."""
    best = min(LIGHT_LEVELS, key=lambda lv: abs(lv[0] - value))
    return best[1], best[2]


def decode_closure(value: int) -> str:
    if value == 0:
        return "idle"
    best = min([(OPEN, "open"), (DANCE, "dance"), (CLOSE, "close"), (STOP, "stop")],
               key=lambda lv: abs(lv[0] - value))
    return best[1]


# --------------------------------------------------------------------------
# Vehicle profiles: what the physical car does with the channels
# --------------------------------------------------------------------------


@dataclass
class Output:
    """One physical light (or light group) on the car, driven by channel(s)."""

    key: str
    label: str
    channels: list[str]          # OR'd together (for "bar": one channel per node)
    kind: str = "ramp"           # ramp | bool | level (full brightness) | ramp500 | bar
    ramp_leader: str | None = None  # channel whose ramp level sets the fade (CH4 rule)
    color: str = "#ffffff"
    view: str = "front"          # front | rear | side


@dataclass
class Profile:
    key: str
    name: str
    outputs: list[Output]
    closures: list[str]
    notes: list[str] = field(default_factory=list)
    unused_channels: list[str] = field(default_factory=list)
    body: str = "sedan"          # sedan | suv | cybertruck (preview drawing)

    def output(self, key: str) -> Output:
        return next(o for o in self.outputs if o.key == key)


WHITE = "#f4f8ff"
AMBER = "#ffae1a"
RED = "#ff2a1a"

MODELS = {"model3": "Model 3", "modely": "Model Y", "models": "Model S", "modelx": "Model X",
          "cybertruck": "Cybertruck"}
LIGHT_CHANNELS = [k for k, v in CHANNELS.items() if v <= 30]


def _pair(key, label, ch, kind="ramp", color=WHITE, view="front", leader=None):
    """L and R outputs for a channel pair like ('INNER', 'inner main beam', 'INNER_MAIN')."""
    return [Output(f"{s}_{key}", f"{s} {label}", [f"{s}_{ch}"], kind,
                   f"{s}_{leader}" if leader else None, color, view) for s in ("L", "R")]


def build_profile(car: dict) -> Profile:
    """Turn a car.json description into the list of physical lights and closures.

    car keys: model (model3|modely|models|modelx|cybertruck), year, headlights
    (projector|reflector), region (na|eu), fogs, power_trunk, tails_combined
    (Model 3 built before Oct 2020), offroad_bar (Cybertruck option).
    Rules come from Tesla's light-show guide (teslamotors/light-show, Dec 2024).
    """
    model = car.get("model", "model3")
    if model == "cybertruck":
        return _cybertruck(car)
    region = car.get("region", "na")
    projector = car.get("headlights", "projector") == "projector"
    fogs = car.get("fogs", True)
    sx = model in ("models", "modelx")
    outs: list[Output] = []
    notes: list[str] = []
    unused: list[str] = []

    outs += _pair("OUTER", "outer main beam", "OUTER_MAIN", "bool" if projector else "ramp")
    outs += _pair("INNER", "inner main beam", "INNER_MAIN")
    outs += _pair("SIG", "signature", "SIGNATURE", "bool" if sx else "ramp")
    if sx:
        # three separate lights per side, all sharing channel 4's fade time
        for n in (4, 5, 6):
            outs += _pair(f"CH{n}", f"channel {n}", f"CH{n}", leader="CH4")
        outs += _pair("FTURN", "front turn", "FRONT_TURN", "bool", AMBER)
    else:
        outs += [Output(f"{s}_DRL", f"{s} DRL (ch 4-6)", [f"{s}_CH4", f"{s}_CH5", f"{s}_CH6"],
                        "ramp", f"{s}_CH4", WHITE) for s in ("L", "R")]
        outs += _pair("FTURN", "front turn", "FRONT_TURN", "ramp", AMBER)
    if fogs:
        outs += _pair("FOG", "front fog", "FRONT_FOG", "bool")
    else:
        unused += ["L_FRONT_FOG", "R_FRONT_FOG"]

    park_l = (["L_AUX_PARK"] if fogs else []) + (["L_SIDE_MARKER"] if region == "na" else [])
    park_r = [c.replace("L_", "R_") for c in park_l]
    if not fogs:
        unused += ["L_AUX_PARK", "R_AUX_PARK"]
    if region != "na":
        unused += ["L_SIDE_MARKER", "R_SIDE_MARKER"]
    if park_l and sx:
        outs += [Output("L_PARK", "L aux park + side marker", park_l, "bool", color=AMBER),
                 Output("R_PARK", "R aux park + side marker", park_r, "bool", color=AMBER)]
    elif park_l:
        outs.append(Output("PARK", "aux park + side markers (all OR'd)", park_l + park_r, "bool",
                           color=AMBER))

    outs += _pair("REPEAT", "side repeater", "SIDE_REPEATER", "bool", AMBER, "side")
    outs += _pair("RTURN", "rear turn", "REAR_TURN", "bool", AMBER, "rear")
    outs.append(Output("BRAKE", "brake (incl. 3rd brake light)", ["BRAKE"], "bool", color=RED, view="rear"))
    if car.get("tails_combined"):
        outs.append(Output("TAILS", "tails + license plate (one output)", ["L_TAIL", "R_TAIL"], "bool",
                           color=RED, view="rear"))
        unused.append("LICENSE")
    else:
        outs += _pair("TAIL", "tail", "TAIL", "bool", RED, "rear")
        outs.append(Output("LICENSE", "license plate", ["LICENSE"], "bool", view="rear"))
    outs.append(Output("REVERSE", "reverse", ["REVERSE"], "bool", view="rear"))
    if region != "na" or model == "modelx":
        outs.append(Output("REAR_FOG", "rear fog", ["REAR_FOG"], "bool", color=RED, view="rear"))
    else:
        unused.append("REAR_FOG")

    closures = ["L_MIRROR", "R_MIRROR", "L_FRONT_WINDOW", "L_REAR_WINDOW", "R_FRONT_WINDOW",
                "R_REAR_WINDOW", "CHARGE_PORT"]
    if car.get("power_trunk", sx or model == "modely"):
        closures.append("LIFTGATE")
    else:
        unused.append("LIFTGATE")
    doors = ["L_FALCON_DOOR", "R_FALCON_DOOR", "L_FRONT_DOOR", "R_FRONT_DOOR"]
    handles = ["L_FRONT_DOOR_HANDLE", "L_REAR_DOOR_HANDLE", "R_FRONT_DOOR_HANDLE", "R_REAR_DOOR_HANDLE"]
    if model == "modelx":
        closures += doors
        unused += handles
    elif model == "models":
        closures += handles
        unused += doors
    else:
        unused += doors + handles

    name = MODELS[model]
    year = car.get("year")
    head = "projector" if projector else "reflector"
    title = f"{name}{f' {year}' if year else ''}, {head} headlights, {region.upper()}"
    notes.append(f"Outer main beam {'switches on/off only' if projector else 'can fade'} "
                 f"({head} headlights).")
    if sx:
        notes.append("Channels 4, 5 and 6 are separate lights per side, but all three use the fade "
                     "time set on channel 4.")
        notes.append("Signature and front turn signals switch on/off only.")
        if park_l:
            notes.append("Aux park + side marker are one light per side: blink them with a gap on "
                         "both channels of that side.")
    else:
        notes.append("Channels 4/5/6 are one light per side; fade time comes from channel 4.")
        if park_l:
            notes.append("Aux park and side markers on both sides are ONE light: leave a gap on all "
                         "four channels to make it blink.")
    if car.get("tails_combined"):
        notes.append("Built before Oct 2020: tails and license plate are one output.")
    if model == "modelx":
        notes.append("Falcon/front doors: 6 commands each; moving windows while doors move can "
                     "trigger pinch protection and stop the show.")
        notes.append("Model X aux park/side marker grouping is assumed to match Model S (not "
                     "documented by Tesla).")
    if "LIFTGATE" in closures:
        notes.append("Liftgate/trunk: 6 commands; it must be fully open (~14 s) before it can dance.")
    notes.append("Charge port: 3 commands; it closes itself 2 min after opening; Dance = rainbow LED.")
    if model in ("model3", "modely") and (year or 0) >= 2024:
        notes.append("2024+ Model 3 / 2025+ Model Y lighting is not in Tesla's guide yet; this uses "
                     "the Model 3/Y rules and is unverified.")
    body = "suv" if model in ("modely", "modelx") else "sedan"
    return Profile(f"{model}_{head}_{region}", title, outs, closures, notes, unused, body)


def _cybertruck(car: dict) -> Profile:
    outs = [
        *_pair("OUTER", "outer main beam", "OUTER_MAIN"),
        *_pair("INNER", "inner main beam", "INNER_MAIN"),
        *_pair("FTURN", "front turn", "FRONT_TURN", "ramp", AMBER),
        *_pair("FMARK", "front side marker", "SIDE_MARKER", "ramp", AMBER),
        Output("FBAR", "front light bar (60 LEDs)", list(FBAR), "bar"),
        Output("FRUNK_LIGHT", "frunk light (aux park ch)", ["L_AUX_PARK", "R_AUX_PARK"], "bool"),
        *_pair("RMARK", "rear side marker (repeater ch)", "SIDE_REPEATER", "bool", AMBER, "rear"),
        *_pair("RTURN", "rear turn", "REAR_TURN", "level", RED, "rear"),
        Output("BRAKE", "brake", ["BRAKE"], "level", color=RED, view="rear"),
        *_pair("REV", "reverse (tail ch)", "TAIL", "bool", WHITE, "rear"),
        Output("BED", "bed lights (reverse ch)", ["REVERSE"], "ramp500", view="rear"),
        Output("LICENSE", "license plate", ["LICENSE"], "bool", view="rear"),
        Output("RBAR", "rear light bar (52 LEDs)", list(RBAR), "bar", color=RED, view="rear"),
    ]
    if car.get("offroad_bar"):
        outs.append(Output("OFFROAD", "offroad light bar", list(OFFROAD), "bar"))
    closures = ["L_MIRROR", "R_MIRROR", "L_FRONT_WINDOW", "L_REAR_WINDOW", "R_FRONT_WINDOW",
                "R_REAR_WINDOW", "LIFTGATE", "CHARGE_PORT"]
    unused = ["L_SIGNATURE", "R_SIGNATURE", "L_CH4", "R_CH4", "L_CH5", "R_CH5", "L_CH6", "R_CH6",
              "L_FRONT_FOG", "R_FRONT_FOG", "REAR_FOG", "L_FALCON_DOOR", "R_FALCON_DOOR",
              "L_FRONT_DOOR", "R_FRONT_DOOR", "L_FRONT_DOOR_HANDLE", "L_REAR_DOOR_HANDLE",
              "R_FRONT_DOOR_HANDLE", "R_REAR_DOOR_HANDLE"]
    notes = [
        "Light bars, brake and rear turn have full brightness control: any level 0-100% holds.",
        "Bed lights (reverse channel) always fade over 500 ms.",
        "Remapped channels: tail = reverse lights, side repeater = rear side markers, aux park = "
        "frunk light, liftgate = powered frunk.",
        "Use 200-channel shows; the light bars live in channels 47-172.",
        "Charge port: 3 commands; Dance = rainbow LED.",
    ]
    year = car.get("year")
    return Profile("cybertruck", f"Cybertruck{f' {year}' if year else ''}", outs, closures, notes,
                   unused, "cybertruck")


def model3_2022(region: str = "na", fogs: bool = True) -> Profile:
    """The original test car: 2022 Model 3, projector headlights."""
    return build_profile({"model": "model3", "year": 2022, "headlights": "projector",
                          "region": region, "fogs": fogs, "power_trunk": True})
