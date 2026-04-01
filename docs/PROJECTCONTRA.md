# Project Log: Contra

## Track Analyzed
`contra_02_Jungle_Lvl_1.mid` (Jungle / Level 1)

## What Was Wrong
Same RPP structure issues as all projects. Additionally:
- Contra's envelope uses a wider velocity range (25-127) than any other
  game analyzed, meaning attack dynamics are critical to the sound
- The long sustained opening notes with gradual CC11 decay define the
  Contra "epic" feel — lost entirely with ADSR

## How We Fixed It
- Full RPP rewrite with Console_Test.rpp structure
- No game-specific ADSR preset yet (using defaults)
- Remaining: CC11/CC12 handling in Console synth, Contra ADSR preset

## What's In The MIDI File

### Envelope Character
Contra has the **widest dynamic range** of any game analyzed. Notes start
at full velocity (127) and decay through 6-7 distinct CC11 steps:

```
Pulse 1: CC11: 127 > 51 > 42 > 34 > 25 > 17 > 8 (7 steps)
Pulse 2: CC11: 59 > 51 > 42 > 34 > 25 > 17 (6 steps, lower peak)
```

The initial 127>51 drop is dramatic — a huge attack transient that
immediately pulls back. This creates Contra's aggressive, punchy feel.
The subsequent decay is gradual (each step ~8 units) giving notes a long
tail that sustains into the next phrase.

6.1 CC11 messages per note on Pulse 1 — dense volume automation.

### Note Durations
Moderately varied, leaning toward medium-length notes:

| Channel | Notes | Avg Duration | Range |
|---------|-------|-------------|-------|
| Pulse 1 | 219 | 260t (16.3f, 271ms) | 62ms - 2.0s |
| Pulse 2 | 196 | 218t (13.6f, 227ms) | 21ms - 2.0s |
| Triangle | 348 | 91t (5.7f, 94ms) | 83ms - 499ms |
| Noise | 0 | — | — |

**Duration distribution (Pulse 1):**
- 0 notes under 50ms
- 25 notes 50-100ms (short articulations)
- 136 notes 100-200ms (majority — driving eighth-note rhythm)
- 39 notes 200-500ms (sustained melody)
- 15 notes over 1 second (long dramatic holds)

The bulk of notes (62%) fall in the 100-200ms range, creating the
driving, militaristic rhythmic feel of Contra's music.

### Velocity — Extreme Range
Pulse 1: 25 to 127. Pulse 2: 8 to 127. This is the widest velocity
range in the library. The Konami Contra driver uses velocity expressively:
- 127: Opening power chords, accented beats
- 51-59: Standard melodic notes
- 25-8: Quiet background textures

### Triangle — Fast Rhythmic Bass
348 notes averaging just 5.7 frames (94ms). Unlike Metroid's long
atmospheric bass or Castlevania's moderate legato, Contra's triangle
plays rapid rhythmic patterns that drive the tempo. 83% of notes are
under 100ms — staccato bass hits locked to the beat.

### No Drums (in this extraction)
The Contra v2 MIDI extraction doesn't include noise channel data. The
original game uses DPCM samples for drums, which aren't captured by the
NSF-to-MIDI pipeline.

### Duty Cycle
8 CC12 changes on Pulse 1, 2 on Pulse 2. Contra uses duty shifts
sparingly but deliberately — typically switching from 50% to 75% for
sustained power-chord sections.

### What This Means For Playback Fidelity
Contra requires CC11 for two reasons:
1. **The 127>51 attack transient** is the defining characteristic — a
   massive initial hit that immediately softens. ADSR can approximate
   attack>decay but not this specific shape.
2. **The gradual 6-step tail** (51>42>34>25>17>8) gives notes sustain
   that blends into the next note. Without it, notes either cut off
   abruptly (short release) or sustain at full volume (long sustain).
