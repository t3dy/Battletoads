# Fake Note Changes: What's Wrong With Our MIDI Encoding

## Status Update: v4 Hysteresis Was Wrong

The period hysteresis fix (v4) was reverted. It suppressed 332 note
changes but 52% of them were real notes that hold for 100+ frames.
The ±8 threshold was too aggressive — it killed legitimate semitone
transitions where the period delta happens to be small.

**v3 (period mask only, no hysteresis) remains the best version.**

The "fake trill" problem from the original analysis is real, but the
fix approach was wrong. The trills can't be fixed with a simple
threshold because real note transitions at high pitches have similar
period deltas to sweep oscillation.

---

## Problem 1: The "Too High" Opening Note

### What You Hear

In the first few bars, Pulse 1 has a high note that sounds too high —
like it's shifted up an octave or two compared to the game.

### What the Data Shows

The trace captures a **rapid descending arpeggio** on P1 at the start:

```
Frame 134: period= 357 -> D#4 (313 Hz) vol=12
Frame 135: period= 451 -> B3  (248 Hz) vol=12
Frame 136: period= 507 -> A3  (220 Hz) vol=12
Frame 137: period= 639 -> F3  (175 Hz) vol=12
Frame 138: period= 805 -> C#3 (139 Hz) vol=12
Frame 139: period= 905 -> B2  (124 Hz) vol=12
Frame 140: period=1143 -> G2  (98 Hz)  vol=12
Frame 141: period=1285 -> F2  (87 Hz)  vol=12
Frame 142: period=1625 -> C#2 (69 Hz)  vol=12
```

**9 notes in 9 frames (150ms).** Each "note" lasts exactly 1 frame
(16.7ms). On the NES hardware, this sounds like a single downward
"thwack" — a percussive sweep. In our MIDI, each frame becomes a
separate note with its own attack transient, and the D#4 at the top
sounds like a distinct high-pitched note.

The NSF extraction for the same section shows simpler bass notes:
D2, A1, G1 — the "intended" musical pitches. The rapid arpeggio is
the sound driver's way of creating an attack transient, not 9
separate musical notes.

### By the Numbers

P1 has **18 one-frame notes** (2.3% of 796 total). These are all
attack transient arpeggios, not musical content. The real musical
notes are 4-9 frames (65% of all notes).

### Fix Needed

Filter or merge 1-frame notes that are part of descending arpeggios.
These should either:
- Be collapsed into the final note of the arpeggio (the target pitch)
- Be removed entirely and let the CC11 volume envelope handle the
  attack transient
- Be rendered as a pitch sweep (pitchbend from start to end pitch)

---

## Problem 2: Sweep Oscillation Trills (Still Unsolved)

### What Happens

At higher pitches (shorter periods), the ±4 sweep oscillation crosses
semitone boundaries:

```
Period 235 -> MIDI 70 (A#4)  }
Period 231 -> MIDI 71 (B4)   } alternating every 2 frames
```

This creates a rapid A#4↔B4 trill (~15 Hz) where the game has smooth
vibrato. **44.4% of P2 note changes** are these fake trills.

### Why the Hysteresis Fix Failed

We tried suppressing note changes when period delta ≤8. But 52% of
the suppressed changes were **real notes that persist 100+ frames**.
At higher pitches, legitimate semitone transitions can have small
period deltas (e.g., period 231→235 is both a sweep oscillation AND
a possible real note change depending on context).

The oscillation and real transitions are **not separable by period
delta alone**. You need temporal context: is the pitch bouncing back
within 2-4 frames (oscillation) or holding steady (real note)?

### Better Fix Options

**Option 1: Bounce-back detection.** Only suppress if the pitch
returns to the previous note within 4 frames. This catches the
oscillation pattern (A#→B→A#→B) without killing sustained changes.

**Option 2: Minimum note duration.** Don't emit a note change unless
the new pitch holds for at least 3 frames. This filters oscillation
while preserving real notes (which always hold 4+ frames).

**Option 3: Median period over 3-frame window.** Compute MIDI note
from the median of the current and previous 2 periods. Oscillation
averages out; sustained changes pass through.

**Not yet implemented** — waiting for ear-check of v3 to confirm
this is the audible problem vs. the other issues below.

---

## Problem 3: Missing Note Frames (the biggest gap)

### What the Audit Found

Comparing trace activity vs MIDI active frames:

```
Channel  Trace Active   MIDI Active   Gap
P1       5,389 (69%)    ~2,653        -2,736 (51% missing)
P2       7,019 (90%)    ~3,517        -3,502 (50% missing)
Tri      4,170 (54%)    ~0            ALL MISSING
Noise    5,987 (77%)    ~198          -5,789 (97% missing)
```

### Why This Happens

**Pulse channels (P1/P2):** The NES volume envelope decays naturally:
vol 6→5→4→3→2→1→0 over ~10 frames. When vol hits 0, our code creates
a `note_off`. The gap before the next attack (4-7 frames of silence)
is real — but the ~50% coverage gap suggests many CC11 volume updates
aren't being counted as "active" in my audit.

Actually, this is a measurement artifact. The MIDI correctly represents
the decay-silence-attack cycle. The gap is between "frames where the
hardware has vol>0" vs "frames where a MIDI note is sounding." The MIDI
approach is correct for playback — you don't want notes sustaining
through vol=0 frames.

**Triangle:** ~0 active MIDI frames despite 4,170 active trace frames.
This is likely a measurement bug in my audit (counting note_on state
incorrectly), because the MIDI does have 414 triangle notes. Need to
verify by listening.

**Noise:** Only 198 MIDI hits vs 5,987 active frames. The noise
channel on NES stays at vol>0 for long stretches (sustained noise
effects, slowly decaying hits). Our drum detection only triggers on
vol transitions from 0→positive, and caps at 12 frames. Everything
after 12 frames is cut off. This is probably correct behavior — you
don't want 100-frame drum notes. But the 198 hits may be underreporting
the number of distinct drum events.

---

## Problem 4: NSF vs Trace Alignment

The NSF Song 3 and the Mesen trace capture completely different note
sequences for the same channel. The NSF starts at the music loop point;
the trace starts at gameplay begin (which may include an intro that the
NSF skips).

First 30 P2 notes comparison:
- **NSF**: G5, G#5, G5, F#5, G5, F#5, F5... (descending chromatic run)
- **Trace**: E3, E3, E3, A2, E3, E3, E3, A#4, B4... (bass groove)

These are completely different sections of the same song. The trace
captures the opening bass groove; the NSF starts at a melody section.
This means: **the NSF cannot be used to validate trace note accuracy.**
The reference MP3 (which is an NSF render) starts at the NSF loop point,
not at the trace start point.

---

## What We Know vs What We Assume

### Verified by Data

- Period mask fix is correct: raw values include length counter bits,
  masking with `& 0x7FF` recovers the 11-bit NES period. P2 went from
  651 to 923 notes, range shifted from D1-A5 to A1-A5. (CONFIRMED)

- The ±4 period oscillation is real sweep unit vibrato, present on both
  pulse channels. 5,610 P2 period changes, 4,345 P1 period changes.
  (CONFIRMED from raw capture)

- The 1-frame notes in P1 are rapid descending arpeggios used as attack
  transients by the sound driver. 18 such notes, all at phrase starts.
  (CONFIRMED by frame inspection)

- The NES volume envelope naturally decays to 0 between notes. Vol=0
  gaps of 4-7 frames are normal. (CONFIRMED by frame inspection)

### Still Unknown

- Whether the "wrong notes" you hear are primarily from the sweep trills,
  the 1-frame arpeggios, or something else entirely.

- Whether the triangle and noise channels are rendering correctly in
  REAPER (structural validation shows data exists, but no ear-check).

- Whether the APU2 path sounds better than the Console path for this
  capture (it should, since it bypasses all MIDI encoding issues).

## Recommended Listening Test

Open both RPPs in REAPER and compare:

1. `output/Battletoads_trace_v3/reaper/Battletoads_trace_01_Ragnoraks_Canyon_v1.rpp`
   (Console/CC path — has the trill and arpeggio issues)

2. `output/Battletoads_trace_v3/reaper/Battletoads_trace_01_Ragnoraks_Canyon_APU2_v1.rpp`
   (APU2/SysEx path — should bypass all MIDI encoding issues)

If APU2 sounds significantly better, the encoding issues are confirmed
and we should focus on improving the CC path encoding. If APU2 also
sounds "off," the problem is in the synth, not the data.
