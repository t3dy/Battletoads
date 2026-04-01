# Project Log: Mega Man 2

## Track Analyzed
`Mega_Man_2_06_Heat_Man_v1.mid`

## What Was Wrong
Same RPP structure issues as all projects. Additionally:
- Mega Man 2's sound driver uses extremely short notes and rapid arpeggios
  that are especially sensitive to envelope handling
- Without CC11, the signature "buzzing arpeggio" texture disappears into
  flat sustained chords

## How We Fixed It
- Full RPP rewrite with Console_Test.rpp structure
- Added MegaMan ADSR preset: duty=3(75%), dec=300ms, sus=12, rel=50ms
- Remaining: CC11/CC12 handling in Console synth

## What's In The MIDI File

### Envelope Character
Mega Man 2 has a **minimal-decay envelope** — notes hit hard and drop
immediately. The CC11 pattern is striking in its simplicity:

```
Pulse 1: CC11: 64 > 16 (2 steps — attack then immediate drop)
Pulse 2: CC11: 56 (single value, often just 1 frame)
```

Only 1.4 CC11 messages per note on Pulse 1 (vs 5.0 for Mario, 4.1 for
Castlevania). The Mega Man driver barely shapes the volume — it relies
on extremely rapid note changes for texture instead.

### Note Durations — The Arpeggio Engine
This is where Mega Man 2 is unique. **Pulse 2 has 2,294 notes averaging
just 1.5 frames (25ms) each.** This is not melody — it's an arpeggio
engine that rapidly cycles through chord tones to create the illusion of
harmony on a single monophonic channel.

| Channel | Notes | Avg Duration | Character |
|---------|-------|-------------|-----------|
| Pulse 1 | 702 | 88t (5.5f, 92ms) | Lead melody, short staccato |
| Pulse 2 | 2294 | 24t (1.5f, 25ms) | Arpeggio engine, 1-frame notes |
| Triangle | 928 | 76t (4.7f, 79ms) | Bass, short punchy |
| Noise | 675 | 46t (2.9f, 48ms) | Fast drum patterns |

**Duration distribution (Pulse 2):**
- 2,086 notes under 50ms (91%) — single-frame arpeggios
- 189 notes 50-100ms — brief melody fragments
- Only 19 notes above 100ms

This arpeggio technique is Mega Man 2's sonic signature. Each "chord"
you hear is actually 3-6 individual notes played in rapid succession,
each lasting 1 frame (16.7ms).

### Velocity Levels
Pulse 1: 64 (485 notes) and 80 (217 notes) — two-level dynamics.
Pulse 2: 56 (1149 notes), 8 (934 notes), 48 (181 notes) — the low-
velocity notes (vel=8) are the quiet arpeggio tones that create the
"background shimmer" effect.

### Duty Cycle
Multiple CC12 changes (17 on Pulse 1, 14 on Pulse 2). Mega Man 2 cycles
between 12.5%, 25%, and 50% duty during the song. The duty changes
contribute to the brightness variation in the arpeggio texture.

### Triangle Bass
928 notes averaging just 4.7 frames (79ms) — very short, punchy bass.
Unlike Castlevania's sustained bass or Mario's moderate bass, Mega Man 2's
triangle plays rapid staccato patterns that lock in with the drum track.

### Drums
675 events, fast and dense. Two velocity levels: 80 (479, standard) and
120 (196, accented beats). Average 48ms per hit. This is one of the
busiest drum tracks in the NES library.

### What This Means For Playback Fidelity
Mega Man 2 is the most demanding game for synth accuracy because:
1. **1-frame notes** — any latency or attack time destroys the arpeggio
2. **Minimal CC11 data** — only 2 values per note, so envelope must be
   nearly instantaneous (attack=0, decay immediate to held level)
3. **Rapid pitch changes** — 2,294 notes in 84 seconds means notes change
   every 36ms on average for Pulse 2
4. **Low-velocity arpeggio tones** — vel=8 notes must be audible but quiet

The ADSR preset for keyboard (duty=3, dec=300ms, sus=12) is a reasonable
approximation of the sustained arpeggio texture. But for file playback,
the CC11 data (64>16 two-step drop) combined with the rapid 1-frame notes
is what creates the authentic Mega Man 2 sound.
