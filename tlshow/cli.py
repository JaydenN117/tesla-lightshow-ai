"""tlshow command line.

  tlshow car --model model3 --year 2022 --headlights projector --region na  # describe your car once
  tlshow demo                                           # try everything on a built-in demo song
  tlshow analyze-audio SONG.mp3 -o build/song/          # wav + analysis.json
  tlshow auto build/song/ -o build/song/lightshow.fseq  # first-draft show
  tlshow validate build/song/lightshow.fseq
  tlshow preview build/song/lightshow.fseq --analysis build/song/analysis.json
  tlshow analyze-show some/lightshow.fseq               # learn from an existing show
  tlshow xsq build/song/lightshow.fseq                  # open/edit in xLights
  tlshow package build/song/ --usb /media/USB           # LightShow/ folder for the car
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import car as car_cfg
from . import fseq
from .channels import MODELS, build_profile


def _yes(v: str) -> bool:
    return v.lower() in ("y", "yes", "true", "1")


def _profile(args, car: dict):
    car = dict(car)
    if args.region:
        car["region"] = args.region
    if args.no_fogs:
        car["fogs"] = False
    return build_profile(car)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tlshow")
    ap.add_argument("--region", choices=["na", "eu"], help="override car.json")
    ap.add_argument("--no-fogs", action="store_true", help="override car.json: no front fogs / aux park")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("car", help="write car.json describing your car (run once per workspace)")
    p.add_argument("--model", required=True, choices=sorted(MODELS))
    p.add_argument("--year", type=int)
    p.add_argument("--headlights", choices=["projector", "reflector"], default="projector",
                   help="projector = round lens behind clear glass (most 2021+ cars)")
    p.add_argument("--region", dest="car_region", choices=["na", "eu"], default="na",
                   help="na = North America (side markers, no rear fog except Model X)")
    p.add_argument("--fogs", default="yes", help="front fog lights fitted (no on Model 3 RWD/SR+)")
    p.add_argument("--power-trunk", default=None, help="powered trunk/liftgate (yes/no)")
    p.add_argument("--tails-combined", default="no", help="Model 3 built before Oct 2020: yes")
    p.add_argument("--offroad-bar", default="no", help="Cybertruck offroad light bar fitted")
    p.add_argument("-o", "--out", default="car.json")

    p = sub.add_parser("demo", help="build a show for a built-in, copyright-free demo song")
    p.add_argument("-o", "--out", default="build/demo")

    p = sub.add_parser("analyze-audio")
    p.add_argument("song")
    p.add_argument("-o", "--out", required=True, help="folder for lightshow.wav + analysis.json")
    p.add_argument("--sections", type=int, default=None)
    p.add_argument("--bpm", type=float, default=None, help="tempo hint if the detected tempo is a wrong multiple")

    p = sub.add_parser("auto")
    p.add_argument("folder", help="folder from analyze-audio")
    p.add_argument("-o", "--out")
    p.add_argument("--no-closures", action="store_true")
    p.add_argument("--no-trunk", action="store_true", help="leave the trunk out even if car.json has one")

    p = sub.add_parser("validate")
    p.add_argument("fseq")
    p.add_argument("--audio")

    p = sub.add_parser("preview")
    p.add_argument("fseq")
    p.add_argument("--analysis")
    p.add_argument("--audio", help="embed this audio file in the HTML")
    p.add_argument("--title", default=None)
    p.add_argument("--song", default="")
    p.add_argument("-o", "--out")

    p = sub.add_parser("analyze-show")
    p.add_argument("fseq", nargs="+")
    p.add_argument("--no-audio", action="store_true")

    p = sub.add_parser("xsq")
    p.add_argument("fseq")
    p.add_argument("-o", "--out")

    p = sub.add_parser("package")
    p.add_argument("folder")
    p.add_argument("--usb", required=True, help="USB root (or any folder); writes LightShow/ inside")
    p.add_argument("--name", default="lightshow", help="file stem; several shows can share one stick")

    args = ap.parse_args(argv)
    if args.cmd == "car":
        c = {"model": args.model, "headlights": args.headlights, "region": args.car_region,
             "fogs": _yes(args.fogs), "tails_combined": _yes(args.tails_combined),
             "offroad_bar": _yes(args.offroad_bar)}
        if args.year:
            c["year"] = args.year
        if args.power_trunk is not None:
            c["power_trunk"] = _yes(args.power_trunk)
        path = car_cfg.save(c, args.out)
        prof = build_profile({**car_cfg.DEFAULTS, **c, "power_trunk": c.get(
            "power_trunk", args.model in ("models", "modelx", "modely", "cybertruck"))})
        print(f"wrote {path}: {prof.name}")
        for n in prof.notes:
            print(f"  - {n}")
        return 0
    if car_cfg.find() is None:
        print("note: no car.json found - using a default Model 3. Run `tlshow car --help`.",
              file=sys.stderr)
    car = car_cfg.load()
    prof = _profile(args, car)

    if args.cmd == "analyze-audio":
        from .audio import analyze, prepare_audio

        out = Path(args.out)
        wav = prepare_audio(args.song, out / "lightshow.wav")
        a = analyze(wav, args.sections, args.bpm)
        a.save(out / "analysis.json")
        print(f"{a.duration:.1f}s, {a.tempo:.1f} bpm, {len(a.beats)} beats")
        for s in a.sections:
            print(f"  {s.start:7.2f}-{s.end:7.2f}  {s.label}  {s.level:4s} energy {s.energy:.2f}")
    elif args.cmd == "auto":
        from .audio import Analysis
        from .auto import Options, build

        folder = Path(args.folder)
        a = Analysis.load(folder / "analysis.json")
        show = build(a, opts=Options(closures=not args.no_closures, profile=prof,
                                     trunk=False if args.no_trunk else None))
        out = Path(args.out or folder / "lightshow.fseq")
        show.save(out)
        print(f"wrote {out}")
    elif args.cmd == "validate":
        from .validate import check, has_errors, report

        msgs = check(args.fseq, prof, args.audio)
        print(report(msgs))
        return 1 if has_errors(msgs) else 0
    elif args.cmd == "preview":
        from .audio import Analysis
        from .preview import build
        from .validate import check

        path = Path(args.fseq)
        music = Analysis.load(args.analysis) if args.analysis else None
        out = Path(args.out or path.with_name("preview.html"))
        build(fseq.read(path), prof, out, title=args.title or path.parent.name, song=args.song,
              music=music, messages=check(path, prof), audio_path=args.audio, fseq_name=path.name)
        print(f"wrote {out}")
    elif args.cmd == "analyze-show":
        from .analyze import analyze_show, find_audio, format_report
        from .audio import analyze

        for f in args.fseq:
            path = Path(f)
            a = find_audio(path)
            music = analyze(a) if a and not args.no_audio else None
            print(format_report(str(path), analyze_show(fseq.read(path), music)))
    elif args.cmd == "xsq":
        from .xsq import export

        path = Path(args.fseq)
        out = export(fseq.read(path), args.out or path.with_suffix(".xsq"))
        print(f"wrote {out}")
    elif args.cmd == "demo":
        from .audio import analyze
        from .auto import Options, build
        from .demo import render
        from .preview import build as build_preview
        from .validate import check, report

        out = Path(args.out)
        wav = render(out / "lightshow.wav")
        a = analyze(wav, bpm=120)
        a.save(out / "analysis.json")
        show = build(a, opts=Options(profile=prof))
        show.save(out / "lightshow.fseq")
        msgs = check(out / "lightshow.fseq", prof)
        print(report(msgs))
        build_preview(fseq.read(out / "lightshow.fseq"), prof, out / "preview.html", title="tlshow demo",
                      song="Synthesised demo track · 120 bpm", music=a, messages=msgs,
                      audio_path=wav)
        print(f"demo show for {prof.name}: {out / 'lightshow.fseq'}; open {out / 'preview.html'}")
    elif args.cmd == "package":
        from .validate import check, has_errors, report

        folder = Path(args.folder)
        dest = Path(args.usb) / "LightShow"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(folder / "lightshow.fseq", dest / f"{args.name}.fseq")
        shutil.copy(folder / "lightshow.wav", dest / f"{args.name}.wav")
        msgs = check(dest / f"{args.name}.fseq", prof)
        print(report(msgs))
        print(f"copied to {dest}")
        return 1 if has_errors(msgs) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
