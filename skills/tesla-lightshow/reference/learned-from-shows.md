# What existing shows do

Measured with `tlshow analyze-show` (beats from librosa on each show's own audio). "Events" are
frames where at least one light turns on, so simultaneous lights count once.

| Show (source) | Len | Events/beat | Pulse p50 / p90 | Dark | L/R same | On 8th grid | Fades used |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Elevator music (Tesla ex. 1) | 45 s | 0.75 | 680 / 700 ms | 12% | 0.89 | 31% | none |
| Auld Lang Syne (Tesla ex. 2) | 115 s | 1.56 | 200 / 880 ms | 9% | 0.97 | 61% | all kinds |
| The Arrival (Tesla ex. 3, car 1) | 110 s | 4.39 | 200 / 1850 ms | 41% | 0.98 | 39% | all kinds |
| Ready for Assault (Tesla ex. 4) | 92 s | 1.34 | 100 / 440 ms | 67% | 0.99 | 52% | mostly off 500 |
| Cyber Symphony (Tesla ex. 5) | 89 s | 4.43 | 180 / 420 ms | 42% | 0.92 | 48% | off 500/1000, on 500/1000 |
| Among Us drip (community) | 73 s | 2.05 | 300 / 320 ms | 28% | 0.71 | 80% | off 500 |
| Happy Birthday (community) | 17 s | 1.14 | 525 / 675 ms | 22% | 0.82 | 61% | none |
| **tlshow auto draft (rock song, 103 bpm)** | 219 s | 1.47 | 120 / 240 ms | 60% | 0.99 | 90% | off 500/1000/2000, on 1000/2000 |

Grid alignment for Tesla's shows looks low because their designers follow melody and orchestral
hits rather than a drum grid, and the beat tracker can lock to half or double tempo on orchestral
tracks. For rock and pop, aim for ≥ 85% on the 8th grid.

## Confirmed on a real car (2022 Model 3, projector headlights)

Checked against phone and drone footage of shows running on the car:
- **Fade-on 70% = 2000 ms.** Signature + DRL set to 70% at 1.08 s climbed steadily and levelled
  off at 3.1 s, within a frame of the predicted 3.08 s. With the README's 500 ms reading they
  would have been at full brightness 0.4 s in. The 20% fade-off (1000 ms) also matched.
- **Sync.** Light changes landed 25 ms late to 15 ms early against the file across three
  clips (one frame is 20 ms), playing MP3 audio from the stick. No offset correction needed.

## Findings

1. **Fade-on levels.** In Tesla's own .xsq files, 90% effects have a median length of ~350 ms
   (Cyber Symphony, n=176) and 70% effects ~1.8-2.2 s. A 500 ms fade fits the first, a 2 s fade
   the second. Tesla's `xlights_keybindings.xml` also maps E (labelled "fade on 500 ms") to 90%.
   The README table says the opposite. tlshow uses 90% = 500 ms, 80% = 1000 ms, 70% = 2000 ms,
   and the 70% = 2000 ms reading is now confirmed on a real car (see above).
2. **The pluck.** The most-used fade in every Tesla show is "off 500 ms" right after an instant
   on: a hit that decays. Ramped fades on are rarer and used for swells into sections.
3. **Short pulses.** Tesla's later shows (Ready for Assault, Cyber Symphony) use 60-200 ms pulses;
   Ready for Assault's median is 100 ms. Sub-60 ms pulses exist but read as flicker.
4. **Darkness is a tool.** The punchier shows are fully dark 40-67% of the time.
5. **Mostly symmetric.** L/R channels match 90-99% of the time; asymmetry (ping-pong, sweeps) is
   an accent, not the base.
6. **Busiest channels.** Turn signals (front, repeaters, rear), outer/inner main beams, tails,
   reverse. On S/X, Cyber Symphony chases channels 4/5/6 at 40-120 ms; on a Model 3 those are one
   light per side, so a 4-5-6 chase just blinks the DRL.
7. **Closures, typical spend.** Mirrors 8-10 open/close pairs (limit 20); windows dance 2-4
   times; liftgate open + 1-2 dances; charge port open → dance → close (exactly its limit of 3).
   The community birthday show sends many "stop" commands, which don't count towards limits.
8. **Activity follows loudness only loosely** (r = 0.1-0.5). Designers change looks at section
   boundaries more than they scale density with volume.

## How tlshow's auto draft applies this

- Low sections: downbeat swells on signature/DRL, front-turn plucks, brake flashes.
- Mid sections: one beat pattern (ping-pong, front/back, in-out, stack) per 4-bar phrase,
  park flash on downbeats, repeater/fog accents on the & when the music has an accent there.
- High sections: downbeat "hit" (beams, fogs, park, rear) + pluck, beat patterns, every & moving,
  amber front → side → rear sweep at each phrase end.
- Section changes: everything on for 250 ms, ramping lights fade 1 s.
- Ending: everything on at the last downbeat, 2 s fade.
- Closures: mirrors fold/unfold per loud section, windows dance ≤ 25 s in the loudest section,
  charge port open/dance/close in the last loud section.
