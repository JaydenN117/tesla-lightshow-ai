"""The user's car, described in car.json in the show workspace.

Lookup order: $TLSHOW_CAR, then car.json in the current folder or any parent. Create it
with `tlshow car ...` (see `tlshow car --help`). Without one, the defaults below are used
and commands print a reminder.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .channels import MODELS, Profile, build_profile

DEFAULTS = {"model": "model3", "headlights": "projector", "region": "na", "fogs": True,
            "power_trunk": False}


def find() -> Path | None:
    env = os.environ.get("TLSHOW_CAR")
    if env:
        return Path(env)
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / "car.json").exists():
            return d / "car.json"
    return None


def load() -> dict:
    car = dict(DEFAULTS)
    path = find()
    if path:
        car.update(json.loads(path.read_text()))
    car["model"] = str(car["model"]).lower().replace(" ", "").replace("-", "")
    if car["model"] not in MODELS:
        raise ValueError(f"car.json model must be one of {sorted(MODELS)}")
    if car["model"] in ("models", "modelx", "modely", "cybertruck") and "power_trunk" not in (
            json.loads(path.read_text()) if path else {}):
        car["power_trunk"] = True
    return car


def profile(car: dict | None = None) -> Profile:
    return build_profile(car or load())


def save(car: dict, path: str | Path = "car.json") -> Path:
    path = Path(path)
    path.write_text(json.dumps(car, indent=2) + "\n")
    return path
