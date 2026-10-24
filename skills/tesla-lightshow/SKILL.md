---
name: tesla-lightshow
description: Create, preview, validate and package Tesla custom light shows (xLights FSEQ v2) from the user's own songs, for Model 3, Model Y, Model S, Model X and Cybertruck. Use when the user wants a light show for a song, wants to preview or check a .fseq, asks why a show looks wrong on their car, wants to put shows on a USB stick, or wants to learn from an existing show. Covers car setup, audio analysis (tempo, beats, sections), choreography in Python, a browser/video preview of the car, Tesla's validator rules, the .xsq export for xLights, and the USB layout.
---

# Tesla light shows

## Where things are

- **Toolkit root** (`$TL` below): the folder two levels above this skill's folder, the one
  holding `pyproject.toml` and `tlshow/`. Resolve it from this skill's base directory once and
  use the absolute path in every command.
- **Show workspace**: the folder the user works in, which is the current directory. It holds `car.json`,
  `songs/` (their audio), `shows/<slug>/show.py` (one script per song) and `build/` (outputs).
  If the session was opened in a clone of the toolkit repo, make the workspace a sibling folder
  (e.g. `../tesla-shows`). Never put audio, videos or the user's shows inside the toolkit:
  installing the plugin from a local folder copies everything in it.
- Run every command from the workspace: `uv run --project "$TL" tlshow ...` and
  `uv run --project "$TL" python shows/<slug>/show.py`.
- Requirements: `uv` (it installs the Python packages on first run) and `ffmpeg`. Video previews
  also need Node.js with Playwright (`npx playwright install chromium`).

Reference files in this skill folder (read `spec.md` before hand-writing choreography):
- `reference/spec.md`: file format, channel map, value encoding, closures, per-model behaviour
- `reference/authoring.md`: the `Show` API, groups, section looks, per-car pattern ideas, script template
- `reference/learned-from-shows.md`: measurements from Tesla's example shows and the design rules drawn from them

## First run: the car

If the workspace has no `car.json`, ask the user these questions, all at once, then write the file:

1. Model and year (Model 3, Model Y, Model S, Model X, Cybertruck).
2. Headlights: **projector** (a round lens visible behind the glass; most 2021+ cars) or
   **reflector** (no lens, faceted mirror). Model 3/Y before ~2021 are usually reflector.
3. Region: North America (side markers, no rear fog except Model X) or elsewhere.
4. Model 3/Y: front fog lights? (Model 3 Standard Range Plus / base RWD have none.) Power trunk?
   Model 3 built before October 2020? (Its tails and license plate light are combined.)
5. Cybertruck: offroad light bar fitted?

```
uv run --project "$TL" tlshow car --model model3 --year 2022 --headlights projector --region na \
    --fogs yes --power-trunk yes
```

It prints the car's rules. Pass them on in plain words, especially the ones that change design:
which lights only switch on and off, which lights are shared, and which doors and closures move.
2024+ Model 3 and 2025+ Model Y lighting is not in Tesla's guide yet. Say so, and say that their
shows use the Model 3/Y rules.

Want to show the whole flow without a song? `uv run --project "$TL" tlshow demo` synthesises a
copyright-free track, builds a show for the user's car and writes `build/demo/preview.html`.

## Workflow

1. **Audio.** Save the user's file as `songs/<slug>.mp3` (or .wav/.m4a). Never commit or upload
   their music anywhere. Keep a running list in `songs/QUEUE.md`.
   ```
   uv run --project "$TL" tlshow analyze-audio songs/<slug>.mp3 -o build/<slug>
   ```
   This writes `build/<slug>/lightshow.wav` (44.1 kHz, exact timing) and `analysis.json`
   (tempo, beats, downbeats, accents, sections). Time everything against this WAV.
   - **Check the tempo.** Beat trackers lock to the wrong multiple on dense rock and metal (one
     song came out 126 instead of ~96, another 120 instead of ~180). Compare against the
     tempogram's top candidates (`librosa.feature.tempogram`). Score each candidate by how many
     strong onsets land on its 8th-note grid, and re-run with `--bpm <hint>` when another tempo
     fits clearly better. Half time is fine for very fast songs.
   - **Check the sections.** Modern masters are loud throughout, so loudness alone separates
     sections poorly. Also compare, per section, accent density, spectral flatness (distorted
     guitars → chorus), and sub-bass share (bass drops → chorus). Find silences and stops in
     `a.energy` at 0.1 s resolution; those make the best hand-placed moments.
2. **Draft.** Write `shows/<slug>/show.py` from the template in `reference/authoring.md`. Call
   `auto.build()` with `Options(looks={section_index: "low|mid|high|break|solo|hold"},
   palette=...)`, then layer hand-placed moments: the opening hit, a blackout during silences,
   double hits, the ending cut. Re-time closures that would move during a silence.
3. **Validate.** `uv run --project "$TL" tlshow validate build/<slug>/lightshow.fseq`. Fix every
   ERR and read every WARN. Also check the closure plan (`tlshow.sim.simulate(...).closures`) for
   rejected commands.
4. **Preview.**
   `uv run --project "$TL" tlshow preview build/<slug>/lightshow.fseq --analysis build/<slug>/analysis.json --title "<Song>" --song "<Artist · year>"`
   writes `preview.html`: front and rear of the user's car, a light-lane timeline with beats and
   sections, closure states and validator messages. `--audio build/<slug>/lightshow.wav` embeds
   the song, for a local file only. Never publish a page or video with the user's music to a
   public or shared place. A hosted preview page must be built without `--audio`; it has a
   "Load song" button.
   For a check with sound, render a video and send it to the user (about 2 s of rendering per
   second of song):
   `node "$TL/scripts/render_video.js" build/<slug>/preview.html build/<slug>/lightshow.wav build/<slug>/<slug>-preview.mp4`
   Before handing it over, screenshot a busy moment and compare stats
   (`tlshow.analyze.analyze_show`) with `reference/learned-from-shows.md`.
5. **Iterate** on what the user says after watching: re-run the script, validate, preview.
6. **Edit in xLights (optional).** `uv run --project "$TL" tlshow xsq build/<slug>/lightshow.fseq`
   writes an .xsq that opens in Tesla's `tesla_xlights_show_folder`. In xLights, Render All, then
   save the .fseq.
7. **Package.** `uv run --project "$TL" tlshow package build/<slug> --usb <folder> --name <slug>`
   writes `<folder>/LightShow/<slug>.fseq` + `.wav`. For several shows, give each its slug. To
   keep a download small, use the user's original MP3 (check `ffprobe` reports 44100 Hz) as
   `<slug>.mp3` instead. MP3 adds ~25 ms of decoder delay, about one frame. Zip the `LightShow/`
   folder with a short HOW-TO-USE.txt.
   USB rules: `LightShow` folder at the root, `<name>.fseq` with a matching `<name>.wav/.mp3`,
   exFAT/FAT32/ext3/ext4 (not NTFS), no `TeslaCam` folder and no update files on the stick. In
   the car: Toybox → Light Show → pick the show. A cloud session can't write to the user's USB
   stick; send the zip.

## Hard rules (the car rejects or misplays the show otherwise)

- FSEQ **V2 uncompressed**, 48 or 200 channels, frame step 15-100 ms (use 20). Audio 44.1 kHz.
  Up to 4 hours.
- Closure limits per show (open/dance/close each count; stop does not): charge port 3, windows,
  trunk/liftgate/frunk, front and falcon doors 6, mirrors and door handles 20. Only windows dance
  from closed. Everything else must be fully open first (liftgate ~14 s, falcon doors ~20 s).
  Keep each dance under ~30 s. The charge port closes itself 2 min after opening. On a Model X,
  never move windows while doors move (pinch protection stops the show).
- Fades: fade-off only works on a lit light. An effect must last ramp + 50 ms to reach its end
  level. Channel 4 sets the fade time for channels 4-6 on every model.
- Shared outputs: on Model 3/Y, aux park and side markers on both sides are one light. On S/X
  they're one light per side. Blink them with a gap on every channel of the group.

## Design rules (details in reference)

- Put changes on the beat grid: ≥ 85% of light events within 50 ms of an 8th note.
- Busy sections: 1.3-4.5 light events per beat. Quiet sections: downbeats and slow fades.
- Default move is the **pluck** (instant on, 500 ms fade off). Hard flashes 60-200 ms.
- Contrast: fully dark 40-65% of the time. Save "everything on" for section changes, drops and
  the ending.
- Same section label → same look. Vary the pattern every 4-bar phrase.
- Spend closures on big moments: mirrors fold in loud sections, windows and the liftgate or falcon
  doors dance at the peak, charge port open → rainbow → close in the last loud section.
- Cybertruck: the light bars carry the show (sweeps, pulses, fills; see `authoring.md`).
  Model S/X: chase channels 4 → 5 → 6, which are separate lights there.

## Learning from more shows

`uv run --project "$TL" tlshow analyze-show path/to/lightshow.fseq` reports channel use, pulse
lengths, fades, closures and beat alignment, using the matching .wav/.mp3 next to it. Tesla's
example shows: `git clone https://github.com/teslamotors/light-show`. Add new findings to
`reference/learned-from-shows.md`.

## Known uncertainties (say so when relevant)

- Settled: Tesla's README lists fade-on as 70% = 500 ms and 90% = 2000 ms, but 70% = 2000 ms
  (as in Tesla's example shows and key bindings) is confirmed on a 2022 Model 3. If a user's
  footage disagrees on another model, update the notes.
- Model X aux park/side-marker grouping is assumed to match Model S. 2024+ Model 3 and 2025+
  Model Y lighting is undocumented.
- The preview is a simulation: fades are linear, closure motion is approximate, the drawing is
  stylised. The car is the final check.
