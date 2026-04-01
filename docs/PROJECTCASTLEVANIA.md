# Project Log: Castlevania

## Track Analyzed
`Castlevania_02_Vampire_Killer_(Courtyard)_v1.mid`

## What Was Wrong
Same RPP structure issues as all projects (see PROJECTMARIO1.md). Additionally:
- No game-specific ADSR preset was being applied (generic defaults)
- Console synth ignoring CC11 means the distinctive Castlevania "sharp
  attack, fast decay" envelope is replaced by generic ADSR curves

## How We Fixed It
- Full RPP rewrite with Console_Test.rpp structure
- Added Castlevania-specific ADSR preset in GAME_ADSR:
  Pulse 1: duty=1(25%), atk=50ms, sus=4, rel=40ms
  Pulse 2: duty=2(50%), dec=120ms, sus=1, rel=30ms
- Remaining: CC11/CC12 handling in Console synth

## What's In The MIDI File

### Envelope Character
Castlevania has a **fast-decaying envelope** that gives it a percussive,
driving feel. Unlike Mario's uniform decay, Castlevania notes vary in
initial velocity (24-40) and follow a rapid 4-step decay:

```
Pulse 1 typical: CC11: 32 > 24 > 16 > 8 (4 frames)
Pulse 2 longer:  CC11: 40 > 32 > 24 > 16 > 8 (5 frames, some repeat)
```

The low starting velocity (32-40 vs Mario's 64) combined with fast decay
creates the sharp, articulated sound that defines Konami's CV1 driver.

### Note Durations
**Highly varied.** Unlike Mario's fixed 7-frame notes, Castlevania uses
the full range from staccato to sustained:

| Duration | Count | Musical Function |
|----------|-------|-----------------|
| <50ms (1-3 frames) | 97 | Grace notes, ornaments |
| 50-100ms (3-6 frames) | 74 | Fast passages |
| 100-200ms (6-12 frames) | 21 | Standard melody |
| 200-500ms (12-30 frames) | 99 | Sustained phrases |
| 500ms-1s | 12 | Long holds |
| >1s | 6 | Dramatic sustains |

Average duration: 184 ticks (11.5 frames, 191ms) for Pulse 1.

This wide distribution is what makes Castlevania's music feel dynamic.
The same melody has staccato bursts and legato phrases, all driven by
the Maezawa sound driver's per-note envelope control.

### Duty Cycle Changes
13 CC12 messages on Pulse 1, 19 on Pulse 2 — duty changes mid-song.
Castlevania shifts between 25%, 50%, and 75% duty to create timbral
variety. Pulse 2 uses all 4 duty values. This is more timbrally complex
than Mario (which never changes duty).

### Velocity Distribution
Three distinct velocity levels: 40 (132 notes), 24 (102 notes), 32 (75
notes). The Maezawa driver uses velocity to set initial volume, then CC11
takes over for the decay. Higher velocity = louder attack, same decay shape.

### Triangle Bass
Long sustained notes (avg 42.5 frames, 707ms). Bass lines in Castlevania
are legato, providing harmonic foundation under the percussive pulse
channels. Duration range 116ms to 1.9 seconds.

### Drums
468 noise events — heavy drum use. Mostly very short (<50ms, 324 events)
with some longer hits. Two velocity levels: 64 (324, strong beats) and 48
(144, ghost notes). The driving drum pattern is central to Castlevania's
rhythmic intensity.

### What This Means For Playback Fidelity
Castlevania is harder to reproduce than Mario because:
1. Variable note durations require the synth to honor MIDI timing precisely
2. Variable velocity means the attack level matters (not just "on/off")
3. Duty cycle changes affect timbre mid-phrase
4. The fast 4-step decay envelope (32>24>16>8) is THE Castlevania sound

Without CC11, every note sounds sustained instead of percussive. The ADSR
preset (atk=50ms, sus=4) approximates this for keyboard play, but CC11
playback would be frame-accurate to the Maezawa driver.
