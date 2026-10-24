"""Build a self-contained HTML preview: animated front/rear car, timeline, closures, validator."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np

from .analyze import analyze_show
from .audio import Analysis
from .channels import CHANNELS, Profile
from .fseq import Fseq
from .sim import simulate

TEMPLATE = Path(__file__).with_name("preview_template.html")
MODE_CODE = {"idle": 0, "open": 1, "close": 2, "dance": 3, "stop": 4}
CLOSURE_LABELS = {
    "L_FRONT_WINDOW": "Left front window", "R_FRONT_WINDOW": "Right front window",
    "L_REAR_WINDOW": "Left rear window", "R_REAR_WINDOW": "Right rear window",
    "L_MIRROR": "Left mirror", "R_MIRROR": "Right mirror",
    "LIFTGATE": "Trunk / liftgate", "CHARGE_PORT": "Charge port",
    "L_FALCON_DOOR": "Left falcon door", "R_FALCON_DOOR": "Right falcon door",
    "L_FRONT_DOOR": "Left front door", "R_FRONT_DOOR": "Right front door",
    "L_FRONT_DOOR_HANDLE": "L front handle", "L_REAR_DOOR_HANDLE": "L rear handle",
    "R_FRONT_DOOR_HANDLE": "R front handle", "R_REAR_DOOR_HANDLE": "R rear handle",
}


def _b64(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=np.uint8).tobytes()).decode()


def build(seq: Fseq, profile: Profile, out: str | Path, *, title: str, song: str = "",
          music: Analysis | None = None, messages: list | None = None,
          audio_path: str | Path | None = None, fseq_name: str = "lightshow.fseq") -> Path:
    sim = simulate(seq, profile)
    outputs = []
    for o in profile.outputs:
        v = sim.lights[o.key]
        if o.kind == "bar":
            outputs.append({"key": o.key, "label": o.label, "color": o.color, "nodes": v.shape[1],
                            "data": _b64(np.round(v.max(axis=1) * 255)),
                            "bar": _b64(np.round(v * 255))})
            continue
        chans = ", ".join(str(CHANNELS[c]) for c in o.channels)
        outputs.append({"key": o.key, "label": o.label, "color": o.color, "channels": chans,
                        "data": _b64(np.round(v * 255))})
    closures = []
    for k in profile.closures:
        tr = sim.closures[k]
        closures.append({"key": k, "label": CLOSURE_LABELS.get(k, k),
                         "pos": _b64(np.round(tr.position * 255)),
                         "mode": _b64(np.array([MODE_CODE[m] for m in tr.mode]))})
    stats = analyze_show(seq, music)
    data = {
        "title": title, "song": song, "profile": profile.name, "fseq_name": fseq_name,
        "body": profile.body,
        "n_frames": seq.n_frames, "step_ms": seq.step_ms,
        "outputs": outputs, "closures": closures,
        "rgb": _b64(np.round(sim.rgb * 255)) if sim.rgb is not None else None,
        "sections": [vars(s) for s in music.sections] if music else
                    [{"start": 0, "end": seq.duration_s, "label": "A", "energy": 1, "level": "-"}],
        "beats": music.beats if music else [], "downbeats": music.downbeats if music else [],
        "tempo": music.tempo if music else None,
        "stats": {k: stats.get(k) for k in ("events", "events_per_beat", "dark_fraction")},
        "messages": messages if messages is not None else sim.messages,
        "notes": profile.notes,
        "audio": None,
    }
    if audio_path:
        mime = "audio/mpeg" if str(audio_path).lower().endswith(".mp3") else "audio/wav"
        data["audio"] = f"data:{mime};base64," + base64.b64encode(Path(audio_path).read_bytes()).decode()
    html = TEMPLATE.read_text()
    html = html.replace("__TITLE__", title.replace("<", "&lt;"))
    html = html.replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
    out = Path(out)
    out.write_text(html)
    return out
