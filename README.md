# Tesla Light Show maker for Claude Code

> **🤖 This project was written by AI.** All the code, tests, docs and the Claude skill in this
> repo were written by Claude, Anthropic's AI model, working in
> [Claude Code](https://claude.ai/code). [@JaydenN117](https://github.com/JaydenN117) directed it
> and ran the shows on his own car. See [How this was made](#how-this-was-made).

<iframe width="560" height="315" src="https://www.youtube.com/embed/5bJA9yt8CL0?si=ghNlTIKB_16AsmJ1" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

Turn any song you own into a custom Tesla light show. Claude listens to the track (tempo,
beats, verses and choruses, drops and silences), choreographs your car's lights, mirrors,
windows, trunk and charge port to it, shows you a preview, checks it against Tesla's rules, and
packages it for the USB stick.

Works for **Model 3, Model Y, Model S, Model X and Cybertruck**. Each car's real behaviour is
built in: which lights can fade, which lights share one output, the Model S/X channel 4/5/6
lights, the Cybertruck light bars, falcon doors and the per-show command limits.

## Install

As a Claude Code plugin:

```
/plugin install tesla-lightshow --marketplace JaydenN117/tesla-lightshow-ai
```

On older Claude Code versions, add the marketplace first, then install:

```
/plugin marketplace add JaydenN117/tesla-lightshow-ai
/plugin install tesla-lightshow@tesla-lightshow
```

Or clone this repo and open Claude Code in it; the skill is picked up from `.claude/skills/`
(a symlink, so this route needs macOS or Linux; on Windows use the plugin).

You also need [uv](https://docs.astral.sh/uv/) and [ffmpeg](https://ffmpeg.org/). uv installs the
Python packages on first run. For preview videos, also install Node.js and Playwright
(`npx playwright install chromium`).

## Use it

Make an empty folder for your shows, open Claude Code there, and ask:

> Make a Tesla light show for `~/Music/song.mp3`. I have a 2023 Model Y.

The first time, Claude asks a few questions about your car (headlight type, region, fog lights,
power trunk) and saves the answers to `car.json`. Then, for each song, it:

1. converts the audio to the 44.1 kHz WAV the car wants and analyses it;
2. writes `shows/<song>/show.py`, an automatic draft plus hand-placed moments for that song;
3. validates the result with Tesla's checks plus the car-specific ones;
4. builds a preview (an interactive page, or a video with the song) for you to watch;
5. adjusts it based on what you tell it ("the drop at 1:12 should hit harder");
6. packages `LightShow/<song>.fseq` + audio for the USB stick.

No song handy? Ask for the demo, or run `tlshow demo`. It synthesises a copyright-free track
and builds a show for your car.

### Command line

Everything Claude does is available directly (run from your show folder):

```bash
TL=/path/to/tesla-lightshow-ai
uv run --project $TL tlshow car --model modely --year 2023 --headlights projector --region na
uv run --project $TL tlshow demo
uv run --project $TL tlshow analyze-audio songs/song.mp3 -o build/song   # add --bpm if the tempo is wrong
uv run --project $TL tlshow auto build/song                               # automatic draft
uv run --project $TL tlshow validate build/song/lightshow.fseq
uv run --project $TL tlshow preview build/song/lightshow.fseq --analysis build/song/analysis.json
uv run --project $TL tlshow xsq build/song/lightshow.fseq                 # open/edit in xLights
uv run --project $TL tlshow package build/song --usb /Volumes/USB --name song
uv run --project $TL tlshow analyze-show some/lightshow.fseq              # study an existing show
```

## Your music stays yours

This project never includes or uploads music. Songs stay in your show folder. A `.fseq` file
holds only light timing, so you can share a show without the song: the other person adds their
own copy of the same recording. Keep preview videos and pages with embedded audio to yourself.

## Putting a show on the car

- USB stick formatted exFAT or FAT32 (not NTFS), with no `TeslaCam` folder or update files on it.
- A `LightShow` folder at the root holding `<name>.fseq` plus `<name>.wav` (or `.mp3`) with the
  same name. Several shows can share one stick.
- In the car: Toybox → Light Show → pick your show. If the title says "Light Show" instead of
  "Custom Light Show", the car didn't find the files.
- Park somewhere with room around the car: mirrors, windows, trunk, doors and the charge port
  move during shows. Unplug the charge cable.

## How well does it know each car?

| Car | Source |
| --- | --- |
| Model 3, Model Y (to 2023/2024) | Tesla's light-show guide |
| Model S, Model X (2021+) | Tesla's guide; Model X park-light grouping assumed to match Model S |
| Cybertruck | Tesla's guide (light bars, offroad bar, remapped channels) |
| Model 3 (2024+), Model Y (2025+) | Not in Tesla's guide yet; uses the Model 3/Y rules |

One known discrepancy: Tesla's README lists the fade-on percentages in the opposite order to
Tesla's own example shows and xLights key bindings. This project follows the example shows
(90% = 500 ms fade, 70% = 2000 ms), and footage of a 2022 Model 3 confirmed it.

## Layout

- `tlshow/`: the Python toolkit (FSEQ v2 writer, audio analysis, choreography, per-car simulator,
  validator, preview, xLights export, USB packaging)
- `skills/tesla-lightshow/`: the Claude skill and its reference notes (spec, authoring API, rules
  learned from Tesla's shows)
- `scripts/render_video.js`: renders a preview to MP4 with the song
- `.claude-plugin/`: plugin and marketplace manifests

## How this was made

This repo is an experiment in building a complete tool with an AI coding agent.
[@JaydenN117](https://github.com/JaydenN117) gave the goals in plain language: learn how Tesla
light shows work, make shows for songs he bought, preview them, support other cars, share it.
Claude did the rest in Claude Code:

- read Tesla's [light-show guide](https://github.com/teslamotors/light-show) and its xLights files
  to work out the channel map and per-car rules;
- measured Tesla's example shows and two community shows to learn design rules (pulse lengths,
  how much of the time the car is dark, beat alignment), and spotted that Tesla's README lists
  two fade settings in the wrong order;
- wrote the Python toolkit, the browser preview, the video renderer and the tests;
- made test shows for Jayden's 2022 Model 3, then checked phone and drone footage of them running
  on the car: the fade timing and the sync (within one 20 ms light frame) were confirmed that way.

What a human has and hasn't checked:
- **Tested on a real car:** shows on a 2022 Model 3 with projector headlights.
- **Not tested on a real car:** Model Y, S, X and Cybertruck. Their rules come from Tesla's guide
  and are covered by unit tests, but nobody has run them on those cars yet. Footage and fixes are
  welcome.
- The code hasn't had a line-by-line human review. Read it before you trust it with anything
  important.

## Credits and disclaimer

Built on Tesla's [light-show guide and xLights files](https://github.com/teslamotors/light-show).
Not affiliated with or endorsed by Tesla. Light shows move parts of your car; you use this at
your own risk.

MIT licensed.
