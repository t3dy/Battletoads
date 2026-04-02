# Fake Note Changes: The Sweep Oscillation Trill Problem

## The Symptom

When you listen to the Battletoads Level 1 (Ragnarok's Canyon) output
in REAPER, the Pulse 2 channel sounds "off" — notes seem unstable, like
the pitch is wavering between two semitones rapidly. It's not quite the
right pitch, not quite the wrong pitch. It sounds like something between
a trill and a tuning error.

## The Root Cause: Sweep Vibrato vs MIDI Quantization

The NES APU has a **sweep unit** on each pulse channel. It automatically
increments or decrements the period register by a small amount every few
frames, creating a hardware vibrato effect. In Battletoads, Rare uses
this aggressively — the period oscillates by ±4 every 1-2 frames.

Here's what the raw capture shows on Pulse 2 during the bass groove:

```
Frame 408: period=669 -> MIDI 52 (E3)   vol=6
Frame 411: period=665 -> MIDI 52 (E3)   vol=4
Frame 414: period=673 -> MIDI 52 (E3)   vol=2
Frame 425: period=665 -> MIDI 52 (E3)   vol=6
...
```

At low pitches (long periods), the ±4 oscillation stays within the same
MIDI note. Period 665-673 all round to MIDI 52 (E3). This sounds fine.

But at higher pitches (shorter periods), the same ±4 oscillation crosses
a **semitone boundary**:

```
Frame 502: period=239 -> MIDI 70 (A#4)  vol=6
Frame 504: period=239 -> MIDI 70 (A#4)  vol=5
Frame 506: period=231 -> MIDI 71 (B4)   vol=5   <-- NOTE CHANGE!
Frame 508: period=231 -> MIDI 71 (B4)   vol=4
Frame 510: period=239 -> MIDI 70 (A#4)  vol=4   <-- NOTE CHANGE!
Frame 512: period=239 -> MIDI 70 (A#4)  vol=3
Frame 514: period=231 -> MIDI 71 (B4)   vol=3   <-- NOTE CHANGE!
Frame 516: period=231 -> MIDI 71 (B4)   vol=2
Frame 518: period=239 -> MIDI 70 (A#4)  vol=2   <-- NOTE CHANGE!
```

The actual pitch is ~70.5 MIDI — between A#4 and B4. The sweep vibrato
pushes it just above and below the rounding boundary. Our MIDI converter
creates a **new note** every time the rounding flips, producing a rapid
A#4-B4-A#4-B4 trill at ~15 Hz.

On the NES hardware, this sounds like smooth vibrato. In our MIDI, it
sounds like a nervous trill between two semitones.

## The Numbers

**Pulse 2**: 332 out of 747 note changes (44.4%) are fake — caused by
±4 period oscillation crossing semitone boundaries.

**Pulse 1**: Only 3 out of 505 (0.6%) — Pulse 1 in Battletoads Level 1
mostly plays at lower pitches where the oscillation stays within one
semitone.

## Why This Only Affects the CC/MIDI Path

The APU2/SysEx path doesn't have this problem. It sends raw period
register values to the synth, which oscillates smoothly at the exact
hardware frequency. There's no MIDI note quantization step.

The CC/MIDI path (Console synth) has to convert continuous period values
into discrete MIDI notes. MIDI is inherently quantized to semitones.
Sub-semitone pitch variation can only be expressed as pitchbend, which
we don't currently encode.

## The Fix Options

### Option A: Period Hysteresis (simplest, implementing this)

When the period change is small (≤8, the sweep oscillation range), keep
the current MIDI note instead of computing a new one. This prevents the
trill while preserving real note changes (which have much larger period
jumps, typically 50+).

**Pros**: Simple, catches exactly the problem case, no false positives.
**Cons**: Loses the sub-semitone pitch variation (but MIDI can't
represent it anyway).

### Option B: Pitchbend Encoding

Encode the ±4 oscillation as MIDI pitchbend centered on the base note.
This would let the Console synth reproduce the vibrato effect.

**Pros**: Preserves the vibrato in the MIDI path.
**Cons**: More complex, needs pitchbend range configuration in synth,
risk of accumulation errors.

### Option C: Running Average Period

Smooth the period over a 4-8 frame window before computing MIDI note.
The average of the oscillation is the "true" pitch.

**Pros**: Mathematically precise.
**Cons**: Smears legitimate fast pitch changes (arpeggios) that
Battletoads uses intentionally.

### Decision

**Option A for now.** The ±8 threshold cleanly separates sweep vibrato
(delta ≤4) from real note changes (delta ≥50 in this data). The
sub-semitone vibrato is only faithfully preserved in the APU2 path
anyway, and that's the intended fidelity path for file playback.

## Everything Else We Found Along the Way

### 1. The Period Mask Bug (already fixed)

Mesen captures store `$4006_period` as raw `$4007<<8|$4006`, including
length counter bits from $4007[7:3]. NES period register is 11-bit
(max 2047). Without masking with `& 0x7FF`, MIDI notes were 2 octaves
too low and 272 Pulse 2 notes were dropped as out-of-range.

**Impact**: Fixed in v3. E1 → E3 (correct), 651 → 923 P2 notes.

### 2. Triangle Linear Counter: Not a Volume, It's a Gate

The triangle channel has no volume control. CC11 is always 127 when
sounding. But the `$4008_linear` counter has 27 distinct values in
this capture (3,644 changes). It controls HOW LONG the triangle sounds
after being triggered — it's a duration gate, not a volume.

Currently we use `linear > 0` as the sounding condition and CC11=127
as a flat gate signal. This is correct for note-on/note-off, but the
linear counter's reload value affects the triangle's perceived
articulation (staccato vs legato). We're losing this nuance.

**Impact**: Triangle notes may sound too sustained or too clipped
compared to the game. The linear counter's exact behavior determines
the triangle's "feel."

### 3. Noise Period Mapping: 3 Buckets Isn't Enough

The capture has 7 distinct noise period values, but we map them into
only 3 GM drum notes (hi-hat ≤4, snare 5-8, kick 9+). The NES has 16
possible noise periods, each with a distinct timbre. Battletoads uses
at least 7 of them.

Current mapping:
```
period 0-4  → note 42 (closed hi-hat)
period 5-8  → note 38 (snare)
period 9+   → note 36 (kick)
```

Better mapping would use more GM drum notes to preserve timbral variety.
But the Console synth also needs to produce distinct sounds for each —
it currently has a single noise oscillator that doesn't change timbre
based on the MIDI note number.

### 4. Noise Mode Bit: Metallic vs Hiss

`$400E_mode` has only 1 change in this capture (stays at 0 = long
sequence / hiss). If it changed, it would switch the noise character
from white noise to metallic/tonal noise. This IS encoded in the SysEx
track but NOT in the CC/MIDI path. The Console synth has a `noi_mode`
parameter but nothing in the MIDI sets it.

### 5. Sweep Register: 5 Changes, Not Just Oscillation

The `$4001_sweep` register changed 5 times. This is the sweep
configuration (enable, period, direction, shift), not the oscillation
itself. The oscillation is automatic once the sweep is enabled. We're
capturing the EFFECT of the sweep (period changes) in both paths, but
only the SysEx path captures the sweep CONFIGURATION that controls how
the oscillation behaves.

### 6. DPCM: Almost Nothing

Only 1 change each for $4010_rate, $4011_dac, $4012_addr, $4013_len.
Battletoads Level 1 barely uses DPCM. Other tracks (like the title
screen) may use it more. Not a priority for this segment.

### 7. Pulse Duty Cycle: 40 Changes on P1, 39 on P2

Duty cycle changes ARE encoded as CC12. But with only 40 changes across
9,495 frames, duty shifts are relatively rare compared to volume (3,259
changes on P1) and period (4,345 changes on P1). The duty is mostly
stable per musical phrase, changing mainly at note attacks for timbral
brightness.

### 8. Constant Volume Flag: Stays Constant

`$4000_const` and `$4004_const` each change only once (at frame 1, to
value 1). This means Battletoads uses constant volume mode for both
pulse channels — the volume register IS the volume, not an envelope
divider. This is standard for most NES games. Our encoding assumes
this and is correct.

## Priority Order for Fixes

| # | Issue | Impact | Effort | Affects |
|---|-------|--------|--------|---------|
| 1 | Sweep trill (fake notes) | HIGH — 44% of P2 notes are wrong | Low | Console path |
| 2 | Triangle articulation | MEDIUM — feel is off | Medium | Both paths |
| 3 | Noise timbre variety | LOW — drums sound generic | Medium | Console path |
| 4 | Pitchbend encoding | LOW — only matters for Console | High | Console path |
| 5 | Noise mode bit | LOW — mode=0 throughout Level 1 | Low | Console path |

## The "Close Enough for Government Work" Bar

To get from "best yet" to "close enough":

1. **Fix the sweep trills** — this is the single biggest audible problem.
   44% of P2 note changes are phantom. Once stabilized, the bass groove
   should lock in.

2. **Verify by ear** — open the fixed output in REAPER, A/B against the
   reference MP3. If the bass feels right and the melody doesn't wobble,
   we're there for Level 1.

3. **Accept the CC path's limitations** — the Console synth will never
   perfectly reproduce sweep vibrato, noise mode, or sub-semitone pitch.
   That's what the APU2 path is for. The CC path's job is to be "close
   enough" for keyboard play and YouTube renders.

The APU2/SysEx path is already encoding all of this correctly. The
remaining question is whether the APU2 synth is READING it correctly —
that's the next ear-check.
