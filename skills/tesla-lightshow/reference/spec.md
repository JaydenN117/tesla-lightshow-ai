# Tesla light show spec (as used by tlshow)

Sources: github.com/teslamotors/light-show (README, validator.py, xlights_rgbeffects.xml,
xlights_keybindings.xml, example shows). Channel numbers are 1-based.

## File format

FSEQ v2.0, uncompressed (`compression` byte 0), 48 or 200 channels, step 15-100 ms (20 ms
recommended), up to 4 hours. 32-byte header: `PSEQ`, data offset (u16), minor, major (2),
header length 32 (u16), channel count (u32), frame count (u32), step ms (u8), flags, compression,
block count, sparse count, reserved, unique id (u64). Variable headers follow (`mf` media file,
`sp` producer), then frame-major channel data, one byte per channel.

## Channel map

| Ch | Name | Ch | Name |
| --- | --- | --- | --- |
| 1 / 2 | L / R outer main beam | 25 | brake lights (incl. 3rd brake light) |
| 3 / 4 | L / R inner main beam | 26 / 27 | L / R tail |
| 5 / 6 | L / R signature | 28 | reverse |
| 7 / 8 | L / R channel 4 | 29 | rear fog |
| 9 / 10 | L / R channel 5 | 30 | license plate |
| 11 / 12 | L / R channel 6 | 31 / 32 | L / R falcon door (X) |
| 13 / 14 | L / R front turn | 33 / 34 | L / R front door (X) |
| 15 / 16 | L / R front fog | 35 / 36 | L / R mirror |
| 17 / 18 | L / R aux park | 37 / 38 | L front / L rear window |
| 19 / 20 | L / R side marker | 39 / 40 | R front / R rear window |
| 21 / 22 | L / R side repeater | 41 | liftgate (trunk on Model 3) |
| 23 / 24 | L / R rear turn | 42-45 | door handles (S) |
| | | 46 | charge port |

200-channel extras: 47-106 Cybertruck front light bar, 111-162 rear light bar, 167-172 offroad
bar, 175 suspension, 176-178 centre display RGB, 179/182/185/188/191 interior accent RGB
(R rear, R front, centre front, L front, L rear; 3 channels each).

## Light values

| Byte | xLights % | Key | Meaning |
| --- | --- | --- | --- |
| 0 | empty | | off, instant |
| 25 | 10% | W | fade off 500 ms |
| 51 | 20% | S | fade off 1000 ms |
| 76 | 30% | X | fade off 2000 ms |
| 178 | 70% | C | fade on 2000 ms |
| 204 | 80% | D | fade on 1000 ms |
| 229 | 90% | E | fade on 500 ms |
| 255 | 100% | F | on, instant |

The fade-on rows follow Tesla's example shows and key bindings, and 70% = 2000 ms is confirmed
on a real car; the README table has 70% and 90% swapped (see learned-from-shows.md). Boolean lights treat > 50% as on.

## Closure values

| Byte | % | Key | Command |
| --- | --- | --- | --- |
| 0 | empty | | idle (finish a move in progress, then stop) |
| 63 | 25% | Q | open |
| 127 | 50% | A | dance |
| 191 | 75% | Z | close |
| 255 | 100% | F | stop now |

Limits per show (Open/Dance/Close only): liftgate 6, mirrors 20, charge port 3, windows 6, door
handles 20, front doors 6, falcon doors 6. Movement times: liftgate open 14 s / close 4 s, windows
4 s, mirrors/handles/charge port 2 s. Dance needs the closure fully open, except windows. Dance
≤ ~30 s per show for thermal reasons. Charge port Dance = rainbow LED; it auto-closes 2 min after
opening. Avoid closing windows mid-show (the music plays from the cabin speakers).

## Behaviour by model

From Tesla's guide (teslamotors/light-show, Dec 2024). `tlshow car` writes `car.json`, and
`tlshow.channels.build_profile()` turns it into these rules for the simulator, validator and
preview.

| Light (channels) | Model 3 / Y | Model S / X | Cybertruck |
| --- | --- | --- | --- |
| outer main beam (1, 2) | fades on reflector headlights, on/off on projector | same | fades |
| inner main beam (3, 4) | fades | fades | fades |
| signature (5, 6) | fades | on/off | none |
| channels 4/5/6 (7-12) | ONE light per side (on = any of 4/5/6); fade time from ch 4 | three separate lights per side; all share ch 4's fade time | none |
| front turn (13, 14) | fades | on/off | fades |
| front fog (15, 16) | on/off; none on Model 3 SR+/base RWD | on/off | none |
| aux park + side marker (17-20) | ONE output for both sides | one output per side (L = L park or L marker) | aux park = frunk light; side markers fade |
| side repeaters (21, 22) | on/off | on/off | = rear side markers |
| rear turn (23, 24) | on/off | on/off | full brightness |
| brake (25) | on/off | on/off | full brightness |
| tails (26, 27) | on/off; Model 3 before Oct 2020: tails + license are one output | on/off | = reverse lights L/R |
| reverse (28) | on/off | on/off | = bed lights (always 500 ms fade) |
| rear fog (29) | non-NA cars only | non-NA, and every Model X | none |
| license (30) | on/off | on/off | on/off |
| light bars | none | none | front 47-106 (60 LEDs), rear 111-162 (52), offroad 167-172 (option); full brightness |

| Closure | Model 3 / Y | Model S | Model X | Cybertruck |
| --- | --- | --- | --- | --- |
| mirrors (35, 36) | yes | yes | yes | yes |
| windows (37-40) | yes | yes | yes | yes |
| liftgate (41) | power trunk only | yes | yes | powered frunk |
| door handles (42-45) | - | yes | - | - |
| front doors (33, 34) | - | - | yes | - |
| falcon doors (31, 32) | - | - | yes (can dance) | - |
| charge port (46) | yes | yes | yes | yes |

Full brightness means the byte is the brightness (0-255 → 0-100%); use `Show.level()` or the
`bar_*` helpers. On every other light a value is a command (see "Light values").

Interior: the centre display (176-178) is RGB on every car in a 200-channel show and lights the
cabin. Cars with interior accent lights also get five RGB segments at 179-193 (Tesla's guide
doesn't list which cars have them).

Minimum visible on-time 15 ms; 100 ms or more reads better.
