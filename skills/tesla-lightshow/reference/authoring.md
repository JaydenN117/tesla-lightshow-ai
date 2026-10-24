# Authoring a show with tlshow

## Show API (`tlshow.choreo.Show`)

All times in seconds; later calls override earlier ones on the same channel.

| Call | Does |
| --- | --- |
| `on(g, t0, t1)` | instant on for [t0, t1) |
| `flash(g, t, dur=0.12)` | hard blink (min 60 ms) |
| `pluck(g, t, hold=0.06, decay=500)` | instant on, then fade off (500/1000/2000 ms) |
| `fade_in(g, t0, t1, ramp=1000)` | ramp on and hold to t1 |
| `fade_out(g, t, ramp=1000)` | ramp a lit light off |
| `swell(g, t0, t1, ramp, release)` | fade in, hold, fade out ending at t1 |
| `strobe(g, t0, t1, period=0.2)` | repeated flashes |
| `chase([g1, g2, ...], t0, step)` | each group in turn |
| `closure(g, t, "open"/"close"/"dance"/"stop", until=None)` | closure command (dance lasts until `until`) |
| `rgb(t0, t1, "#ff4400", fade_ms=0)` | centre display / accent colour (200-channel shows) |
| `clear(g, t0, t1)` | blank a range before re-writing it |
| `save(path)` | write FSEQ v2 uncompressed |

## Groups (`g`)

`outer inner beams sig drl fturn fog park repeat rturn brake tail reverse license rearfog`,
composites `head` (beams+sig+drl+fturn), `front` (head+fog+park), `rear`, `turns`, `all`,
closures `windows mirrors`, or any raw channel name (`L_TAIL`, `CHARGE_PORT`, ...).
Prefix `L.` / `R.` for one side (`L.rear` keeps shared lights like brake). Combine with `+`
or a list: `"inner+tail"`, `["L.head", "R.rear"]`.

On a Model 3, don't build L/R alternation on `park` (one shared output) or chases across
channels 4/5/6 (one light per side).

## Music data (`tlshow.audio.Analysis`)

`a.beats`, `a.downbeats`, `a.tempo`, `a.kicks`, `a.snares`, `a.hats`, `a.onsets` +
`a.onset_strength` (accents on the 16th grid), `a.sections` (`start end label level energy`),
`a.energy_at(t)`, `a.section_at(t)`, `a.beats_between(t0, t1)`.
Sections are found automatically; listen to the preview and override boundaries in the script
when they are wrong (`a.sections[i].start = ...`) before calling `build()`.

## Per-song script template

```python
from pathlib import Path
from tlshow.audio import Analysis
from tlshow.auto import Options, build

ROOT = Path(__file__).resolve().parents[2]        # the show workspace
BUILD = ROOT / "build" / "<slug>"
a = Analysis.load(BUILD / "analysis.json")
# the car comes from car.json in the workspace; closures follow what it has
show = build(a, opts=Options(palette=("#0040ff", "#00c0ff"), looks={0: "low", 3: "break"}))

# hand-placed moments on top of the draft
drop = a.downbeats[24]
show.clear("all", drop - 0.6, drop)          # silence before the drop
show.on("all", drop, drop + 0.3)
show.fade_out(["inner", "sig", "drl", "fturn"], drop + 0.3, ramp=1000)

show.save(BUILD / "lightshow.fseq")
```

## Section looks (`Options(looks={i: ...})`)

| Look | Use for | What it does |
| --- | --- | --- |
| `low` | quiet intros, bridges | downbeat swells on signature/DRL, front-turn plucks, brake flash |
| `mid` | verses | beat pattern per phrase, park flash on downbeats, accents on the & |
| `high` | choruses, riffs | downbeat hit, beat patterns, every & moving, amber sweep at phrase ends |
| `break` | drum breaks, drops | car dark, hits only on accents, 16th strobe into the next section |
| `solo` | guitar solos | `high` plus L/R signature flicker on 16th accents |
| `hold` | held chords, ring-outs | one slow swell, tails on, downbeat hits only |

Moments worth hand-placing on top of the looks:
- **Blackout through a silence.** Find gaps where `a.energy` drops near zero, `clear("all")` over
  them, set `rgb(..., "#000000")`, then everything on when the music returns.
- **Double hits.** Two strong accents close together (`a.onsets` with strength ≥ 0.9): two short
  `on("all")` blasts.
- **Dead stop.** If the song cuts off, end with everything on until the cut, then instant off.
- **Glitchy or stuttering intros.** Alternate `L.sig`/`R.sig` plucks on every accent.
- **Closures around silences.** Re-time a charge-port or window dance so it starts when the band
  comes back (`clear("CHARGE_PORT", ...)`, then place open/dance/close by hand; 3 commands max).

## Pattern ideas (Model 3 / Y; most also work on S / X)

- Ping-pong: `L.head + L.tail` vs `R.head + R.tail` on alternating beats.
- Front/back: plucks up front on 1 and 3, rear flashes on 2 and 4.
- Inside-out: sig/DRL → inner → outer → fog+front turn, one step per beat.
- Stack: add a layer each beat of the bar, release on the next downbeat.
- Amber sweep: `chase(["fturn", "repeat", "rturn"], t, beat/4)` at phrase ends.
- Breath: `swell(["sig", "drl"], bar_start, bar_end, 1000, 1000)` for quiet intros and bridges.
- Blackout before a drop: `clear("all", drop - beat, drop)`, then everything on.

## Model S / X

Channels 4, 5 and 6 are three separate lights per side, so chases read well:
`chase(["ch4", "ch5", "ch6"], t, beat / 3)`. All three fade with channel 4's fade setting. To
fade channel 5 alone, put the fade command on channel 4 too, even if channel 4 stays dark. The
auto draft adds a 4→5→6 chase at the end of every bar in loud sections. Signature and front turn
signals switch on/off only on S/X.

## Cybertruck

The light bars are full-brightness strips, so they carry the show:

| Call | Does |
| --- | --- |
| `bar_fill("fbar", t0, t1, level=1.0)` | whole bar at a brightness |
| `bar_pulse("rbar", t, decay=0.4)` | full bar dying away (a pluck for bars) |
| `bar_sweep("fbar", t0, t1, "out")` | bright band moving: `out` (centre → ends), `in`, `lr`, `rl` |
| `bar(which, t0, t1, fn)` | anything: `fn(t, x)` → 0..1, `t` through the effect, `x` along the bar |
| `level("BRAKE", t0, t1, 40)` | brake / rear turns at a steady brightness |

Bars: `fbar` (60 LEDs), `rbar` (52), `offroad` (6, optional). The auto draft sweeps the front bar
out from the centre on loud downbeats, pulses it on beats, answers with the rear bar on the &,
breathes in quiet parts and strobes on accents in breaks. Remapped channels: tail = reverse
lights, side repeater = rear side markers, aux park = frunk light, liftgate = powered frunk,
reverse = bed lights.
