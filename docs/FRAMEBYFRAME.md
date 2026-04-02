# Frame-by-Frame Analysis: NSF vs Mesen Ground Truth

## What We Found

Comparing the NSF extraction of Battletoads Song 2 against the Mesen
trace of the actual Level 1 gameplay reveals the data streams are
**fundamentally different**. The problem isn't in the synth — it's in
the source data.

### NSF Extraction (what we've been playing)

```
Frame 0:  P1 silent, P2 silent, Tri silent, Noise silent
Frame 4:  P2 starts immediately (period=1358, vol=6, duty=1)
Frame 9:  P2 decaying (vol=5)
Frame 20: P2 next note (vol=6 restart)
```

NSF Song 2 starts playing pulse 2 at frame 4 with a mid-range note.
No intro, no buildup, no noise crescendo.

### Mesen Trace (what the actual game plays)

```
Frame 0:    All silent
Frame 1-5:  Triangle brief pulse (linear counter 13→1→0, period=0)
Frame 10:   Noise begins very quiet (vol=1, period=4067)
Frame 26:   Noise crescendo (vol=2)
Frame 42:   Noise louder (vol=3)
Frame 508:  Pulse 2 bass line enters (period=2717=E1, vol=6)
Frame 1043: Triangle bass enters (period=678=E2)
```

The real game has a **17-second atmospheric intro** before the bass
line even starts. The NSF extraction skips this entirely because the
NSF driver initializes differently than the ROM's in-game music system.

## Key Discoveries

### 1. Period Oscillation = Sweep Unit Vibrato

The Mesen trace shows pulse periods oscillating every 1-2 frames:
```
frame 508: period=2717
frame 517: period=2713
frame 519: period=2717
frame 521: period=2721
```

This ±4 oscillation is the NES **sweep unit** creating a natural
vibrato effect. Our NSF extraction doesn't capture this — notes have
static periods. This is why the sound lacks "richness."

### 2. Triangle Sub-Frame Period Wobble

The triangle period alternates between 678 and 677 every frame:
```
frame 1044: period=677, linear=29
frame 1046: period=678, linear=22
frame 1048: period=677, linear=16
```

This 1-unit wobble is the sound driver doing fine pitch correction
every frame. Our NSF captures a single period per note — missing
this micro-tuning that gives the bass its warmth.

### 3. Noise Crescendo = Musical Element

The noise channel slowly builds from vol 1 to vol 3+ over the
opening 50+ frames. This is an intentional atmospheric effect —
a rising wash of noise before the bass enters. Our NSF extraction
has zero noise activity in the opening.

### 4. Volume Envelopes Are Game-State Dependent

The Mesen trace captures volume as it's actually heard during gameplay.
The NSF driver may produce different envelope shapes because:
- It doesn't know the game state (cutscene vs gameplay)
- It may use a default tempo/init that differs from in-game
- Sound effects in the game ROM interact with music channels

## What This Means for Our Pipeline

### The NSF Is Not Ground Truth for Battletoads

For CV1 and Contra (Konami), the NSF accurately reproduces the game
audio because those games have well-behaved NSF drivers. Battletoads
(Rare) has a more complex sound system where the NSF playback diverges
from actual in-game audio.

### The Mesen Trace IS Ground Truth

The trace captures exactly what the NES APU produces during real
gameplay. Every period oscillation, every volume micro-adjustment,
every sweep unit modulation.

### The Path Forward

1. **Build from the Mesen trace, not from NSF** — use trace_to_midi.py
   as the primary extraction path for Battletoads
2. **Capture the period oscillation** — the ±4 sweep vibrato needs to
   be encoded as MIDI pitchbend or SysEx
3. **Match timing to the actual game** — the 17s intro, the bass entry
   at 8.5s, the rhythmic feel of the groove
4. **Use APU2 SysEx from TRACE data** — build a trace-to-SysEx path
   that embeds raw register state from Mesen (not from NSF)

## How to Build This Into Infrastructure

### Frame-Level Comparison Script

```bash
python scripts/trace_compare_nsf.py \
  --trace capture.csv --nsf game.nsf --song 2 \
  --start-trace 6085 --frames 300
```

Automatically compares:
- Period values per channel per frame
- Volume values per channel per frame
- Duty cycle values per frame
- Reports first mismatch, total mismatches, divergence score

### Systematic Parameter Scanner

For each frame in the trace, check every parameter:

```python
for frame in range(num_frames):
    for channel in ['pulse1', 'pulse2', 'triangle', 'noise']:
        trace_state = get_trace_frame(frame, channel)
        nsf_state = get_nsf_frame(frame, channel)

        for param in ['period', 'volume', 'duty', 'sweep', 'linear', 'mode']:
            if trace_state[param] != nsf_state[param]:
                log_mismatch(frame, channel, param,
                            trace_state[param], nsf_state[param])
```

This is fully deterministic — no guessing, no LLM judgment. Run it on
every game, every song, and build a mismatch database.

### Per-Game Fidelity Score

```
Game: Battletoads, Song: Level 1
  Period match:  42% (sweep oscillation missing from NSF)
  Volume match:  68% (different envelope initialization)
  Duty match:    95% (mostly correct)
  Timing match:  12% (completely different intro timing)
  Overall score: 54% — USE TRACE PATH, NOT NSF
```

Games scoring <80% on the NSF path should automatically route to the
trace-based pipeline instead.

### The Kitchen Sink Approach

For every new game, run ALL of these before declaring "done":

```
[ ] NSF extraction → MIDI → play → does it sound like the game?
[ ] Mesen trace → frame dump → does it match NSF frame-by-frame?
[ ] If mismatch > 20%: switch to trace-based pipeline
[ ] Check every APU register parameter in trace:
    [ ] $4000 duty, volume, constant_vol, envelope
    [ ] $4001 sweep enable, period, negate, shift
    [ ] $4002/$4003 period (11-bit combined)
    [ ] $4004-$4007 (same as above for pulse 2)
    [ ] $4008 linear counter
    [ ] $400A/$400B triangle period
    [ ] $400C noise volume
    [ ] $400E noise period, mode
    [ ] $4010-$4013 DPCM
[ ] For each parameter that changes in trace but not in MIDI:
    [ ] Can it be encoded as a standard MIDI CC?
    [ ] Does it need SysEx?
    [ ] Does the synth handle it?
[ ] Generate APU2 SysEx from trace data (not NSF)
[ ] A/B test: NSF Console vs Trace Console vs Trace APU2
[ ] Human ear-check against actual game audio (MP3 reference)
```

## The Realization

We've been building our Battletoads output from the NSF driver, which
produces a different (simpler, flatter) version of the music than what
the actual game plays. The Mesen capture IS the game audio — we need
to build from that instead.

The CV1/Contra success worked because those games have faithful NSF
drivers. Battletoads doesn't. The methodology is the same (frame-level
comparison, parameter-by-parameter verification) but the data source
must change.
