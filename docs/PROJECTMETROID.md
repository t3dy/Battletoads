# Project Log: Metroid

## Track Analyzed
`Metroid_03_Brinstar_v1.mid`

## What Was Wrong
Same RPP structure issues as all projects. Additionally:
- Metroid's atmospheric, slow-evolving envelopes are particularly
  ill-served by ADSR approximation — the volume "breathes" over many
  frames in a pattern no standard ADSR can reproduce
- Without CC11, Brinstar sounds static instead of alive

## How We Fixed It
- Full RPP rewrite with Console_Test.rpp structure
- Added Metroid ADSR preset: atk=20ms, sus=6, rel=80ms
- Remaining: CC11/CC12 handling in Console synth

## What's In The MIDI File

### Envelope Character
Metroid has the most complex and unusual envelope of any game analyzed.
**The volume oscillates up AND down within a single note:**

```
Pulse 1: CC11: 32 > 40 > 48 > 56 > 64 > 56 > 48 > 40 > 32
                (crescendo then decrescendo — a "breathing" pattern)
```

This is a **crescendo-decrescendo envelope** — the note fades IN, peaks,
then fades OUT. No other game in the library does this. It's what gives
Metroid's Brinstar theme its eerie, pulsing quality.

8.2 CC11 messages per note on Pulse 1 — the highest ratio of any game.
The driver is actively sculpting volume throughout the entire note.

### Note Durations — Long and Atmospheric
Metroid notes are dramatically longer than other games:

| Channel | Notes | Avg Duration | Range |
|---------|-------|-------------|-------|
| Pulse 1 | 141 | 613t (38.3f, 637ms) | 133ms - 3.2s |
| Pulse 2 | 170 | 508t (31.8f, 529ms) | 100ms - 3.2s |
| Triangle | 219 | 338t (21.2f, 352ms) | 133ms - 3.2s |
| Noise | 0 | — | — |

**Duration distribution (Pulse 1):**
- 0 notes under 100ms (no staccato at all)
- 41 notes 100-200ms (short phrases)
- 29 notes 200-500ms (medium)
- 52 notes 500ms-1s (long sustained)
- 19 notes over 1 second (very long atmospheric holds)

Average note duration is 637ms — over 6x longer than Mega Man 2's 92ms.
This is ambient, atmospheric music with long tones and slow modulation.

### Velocity
Pulse 1: constant 32 (quiet). Pulse 2: constant 104 (loud).
The two pulse channels operate at very different volume levels, with
Pulse 2 as the dominant voice and Pulse 1 as a quiet atmospheric layer.
The crescendo-decrescendo envelope on Pulse 1 makes quiet notes seem
to breathe in and out of audibility.

### Pulse 2 Envelope
Different from Pulse 1 — a standard fast decay:
```
CC11: 104 > 72 > 56 > 48 > 40 > 32 (rapid 6-step decay)
```
Then on longer notes, the pattern REPEATS (retriggering the decay within
the same note). This creates a pulsing, rhythmic effect on sustained
notes — the volume decays, jumps back up, decays again.

### No Drums
Brinstar has no noise channel activity. The rhythm comes entirely from
the pulsing volume envelopes and the triangle bass pattern. This is rare
among NES tracks and contributes to Metroid's atmospheric character.

### Duty Cycle
Minimal — only 1 CC12 message each channel (12.5% duty). Metroid uses
the thinnest duty cycle, producing a reedy, hollow tone. Combined with
the breathing envelope, this creates the distinctive "alien" quality.

### What This Means For Playback Fidelity
Metroid is where the CC11 gap hurts the most:
1. **The crescendo-decrescendo envelope is impossible to approximate with
   standard ADSR.** ADSR goes attack>decay>sustain>release. Metroid goes
   crescendo>peak>decrescendo. These are fundamentally different shapes.
2. **The volume retriggering on Pulse 2** (repeating decay within one note)
   has no ADSR equivalent.
3. **Long note durations** mean the envelope shape is clearly audible —
   there's no rapid note-switching to mask envelope inaccuracy.

For keyboard play, the ADSR preset (atk=20ms, sus=6, rel=80ms) gives
a vaguely atmospheric feel. But for file playback, ONLY the CC11 data
can reproduce the breathing crescendo that defines Metroid's sound.
