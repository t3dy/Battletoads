# Solving the Chiptune vs MIDI Problem

How to make a synth plugin that produces sounds close to the NES game
when driven by a MIDI file — and also sounds like the right game
instrument when played live from a keyboard.

---

## The Core Problem

The NES APU is not a MIDI instrument. MIDI was designed for keyboards
and orchestral instruments. The NES was designed for a custom 5-channel
sound chip with behaviors that have no MIDI equivalent:

| NES Hardware | MIDI Equivalent | Gap |
|---|---|---|
| 11-bit period register (continuous) | Note number (12-TET semitones) | Quantization: 1 semitone resolution vs continuous pitch |
| Sweep unit (auto ±period per frame) | Pitchbend (manual) | Sweep is automatic hardware; pitchbend is explicit data |
| 4-bit volume (0-15, written per frame) | CC11 expression (0-127) | Granularity difference, but mappable |
| 2-bit duty cycle (0-3) | No standard equivalent | CC12 works as custom mapping |
| Noise LFSR mode bit (long/short) | No equivalent | Changes noise character entirely |
| Phase reset on period write | Note-on retrigger | NES resets oscillator phase on any $4003 write |
| Linear counter (triangle gate) | Note duration | Triangle has unique gating behavior |
| DPCM sample playback | Sample-based instruments | Completely different mechanism |

**The fundamental tension**: MIDI represents music as discrete events
(note on, note off, controller change). The NES represents music as
continuous register state (every frame, every register, every channel).
These are different models of the same physical phenomenon (sound
changing over time).

---

## The Solution: Two Data Layers, One Synth

### Layer 1: SysEx Register Replay (ROM Accuracy)

Pack the raw NES APU register state into MIDI SysEx messages — one
per channel per frame (60 Hz). The synth reads these and directly
drives its waveform generator from the register values.

```
SysEx format (per channel per frame):
F0 7D 01 <ch> <$4000lo> <$4000hi> <$4001lo> <$4001hi>
              <$4002lo> <$4002hi> <$4003lo> <$4003hi> <enable> F7

ch = 0-3 (Pulse1, Pulse2, Triangle, Noise)
Each register byte split into 7-bit pairs (MIDI-safe)
4 channels × 60 frames/sec = 240 SysEx messages per second
```

**What this captures**: Every register parameter the NES APU uses.
Period, volume, duty, sweep configuration, noise mode, linear counter,
phase reset triggers, DPCM DAC. The synth reconstructs the exact
waveform the NES hardware would produce.

**What this is**: A hardware state replay. The MIDI file is a recording
of what the NES chip does at every frame. The synth is a software NES
APU that reads the same register values.

**Limitation**: DPCM sample playback requires the actual sample ROM
data, which isn't in the register dump. Everything else is captured.

### Layer 2: CC + Notes (Composer Friendly)

Standard MIDI note events with CC automation for the parameters that
map cleanly:

```
Note On/Off     → pitch (from period-to-frequency conversion)
CC11 (volume)   → NES volume 0-15 (encoded as vol × 8)
CC12 (duty)     → NES duty 0-3 (encoded as duty × 32)
Velocity        → initial volume (noise channel)
```

**What this captures**: Pitch, volume envelope, duty cycle, drum hits.
About 70% of the NES sound.

**What this misses**: Sweep vibrato, sub-semitone pitch variation,
noise mode, phase reset, linear counter behavior, DPCM.

**What this is for**: A musical representation. Good enough for
keyboard play, arrangement, remixing. Close but not identical to
the game.

### How They Coexist in One MIDI File

```
Track 0: Metadata (tempo, game name, song name)
Track 1: Pulse 1 — notes + CC11 + CC12 on MIDI ch 0
Track 2: Pulse 2 — notes + CC11 + CC12 on MIDI ch 1
Track 3: Triangle — notes + CC11 (gate) on MIDI ch 2
Track 4: Noise   — drum notes + velocity on MIDI ch 3
Track 5: APU Registers — SysEx for all 4 channels (Layer 1)
```

The synth auto-detects which layer to use:
1. If SysEx arrives → use register replay (maximum fidelity)
2. If CC11/CC12 arrives → use CC-driven mode (good fidelity)
3. If only notes → use ADSR keyboard mode (approximation)

A composer can delete Track 5 and edit the note tracks freely.
The synth degrades gracefully from hardware-exact to approximate.

---

## What the Synth Does With Each Layer

### SysEx Mode (Priority 1): Playing Back the Chip

When SysEx register data arrives, the synth becomes a **software
NES APU**:

```
@block (called once per audio buffer, processes all MIDI):
  for each SysEx message:
    decode channel and 4 register bytes
    write to internal register array: regs[ch][0..3]
    if channel enable bit changed → mute/unmute

@sample (called once per audio sample, generates waveform):
  for each active channel:
    read regs[ch][0..3]
    Pulse:  phase += cpu_clk / (srate * 16 * (period + 1))
            duty_bit = duty_table[duty][floor(phase * 8) % 8]
            output = duty_bit * volume / 15
    Triangle: phase += cpu_clk / (srate * 32 * (period + 1))
              output = triangle_table[floor(phase * 32) % 32] / 15
    Noise:  if LFSR clock triggers →
              feedback = (lfsr ^ (lfsr >> shift)) & 1
              lfsr = (lfsr >> 1) | (feedback << 14)
              output = (1 - (lfsr & 1)) * volume / 15
```

**Every NES behavior comes free** because we're running the same
algorithm the hardware runs:
- Sweep vibrato: the SysEx data contains the period changes the sweep
  unit caused. No special handling needed.
- Phase reset: when $4003 changes, we can optionally reset the phase
  accumulator (this is what causes the hardware "click").
- Noise mode: bit 7 of $400E selects the LFSR feedback tap.
- Volume envelope: the frame-by-frame register values ARE the envelope.

### CC Mode (Priority 2): Close But Not Exact

When CC11/CC12 arrives instead of SysEx:

```
@block:
  for each CC11: volume[ch] = min(15, floor(cc_value / 8 + 0.5))
  for each CC12: duty[ch] = floor(cc_value / 32)
  for each note_on: period[ch] = midi_note_to_period(note)

@sample:
  same waveform generation as SysEx mode, but:
  - period comes from MIDI note (semitone-quantized, not exact)
  - no sweep oscillation (not in CC data)
  - no phase reset (no $4003 write information)
  - no noise mode changes (not in CC data)
```

The sound is recognizably NES but lacks the sub-semitone detail.

### Keyboard Mode (Priority 3): Composer's NES Instrument

When no file data is present, ADSR envelopes shape each note:

```
@block:
  for each note_on:
    start ADSR envelope for channel
    period = midi_note_to_period(note)
    duty = slider value (selected by composer)

@sample:
  same waveform generation, but:
  - volume comes from ADSR envelope (attack → decay → sustain → release)
  - duty comes from slider (or mod wheel for real-time control)
  - sweep and vibrato come from slider settings
  - composer controls the "character" of the NES sound
```

The per-game presets (Battletoads, Castlevania, Mega Man) set the
ADSR and duty values to approximate each game's characteristic sound.

---

## Do We Need a Second Plugin?

### Short Answer: No

A single plugin with the three-priority cascade handles everything.
The SysEx data and CC data arrive on the same MIDI tracks. The synth
just reads whatever is there.

### Longer Answer: Maybe for Visualization

If we want to show register state on a separate UI panel (like a
hardware register monitor with hex values updating at 60 Hz), that
could be a lightweight second plugin chained after the synth. It
would read the same SysEx data and display it without generating
audio.

```
MIDI → [ReapNES Studio] → audio output
         ↓ (MIDI passthrough)
       [ReapNES Monitor] → no audio, just visual display
```

This is optional. The main synth already has display sliders that
show current NES state. A separate monitor would be for YouTube
videos where you want a full-screen register view.

### What About a Middle Layer?

You mentioned "whatever middle layer it might need." The middle layer
is **the extraction pipeline**, not a plugin:

```
ROM / Mesen Trace → [trace_to_midi.py] → MIDI file with SysEx
NSF File → [nsf_to_reaper.py] → MIDI file with CC11/CC12
```

The pipeline converts hardware state into MIDI. The synth converts
MIDI back into hardware state. The MIDI file is the transport format
that REAPER understands.

---

## The Specific Problems and Their Solutions

### Problem: Sweep Vibrato Trills

**In CC mode**: ±4 period oscillation causes MIDI note to flip between
two semitones at high pitches (A#4↔B4 at ~15 Hz).

**In SysEx mode**: Not a problem. The synth receives the exact period
value (e.g., 231, 235, 231, 235) and generates the correct frequency.
No semitone quantization. Sounds like smooth vibrato.

**For keyboard**: The sweep unit slider lets the composer add hardware
sweep to any note. Rate and shift are controllable in real time.

### Problem: 1-Frame Attack Arpeggios

**In CC mode**: 9 MIDI notes in 150ms, each with its own attack
transient. Sounds like distinct high notes instead of a sweep.

**In SysEx mode**: The synth sees the period register changing rapidly
without note-off events. The waveform frequency changes smoothly frame
by frame. Sounds like the original hardware "thwack."

**For keyboard**: The ADSR attack time controls how the note begins.
A fast attack with duty sweep approximates the effect.

### Problem: Noise Timbre Variety

**In CC mode**: 16 noise periods mapped to 3 drum notes. Timbral
variety lost.

**In SysEx mode**: The synth reads the exact period index AND mode bit
from the register data. All 16 timbres and both LFSR modes are
preserved.

**For keyboard**: Drum mapping sends different noise periods per GM
drum note. The composer can choose which timbre to trigger.

### Problem: Triangle Gating

**In CC mode**: CC11 is always 127 (triangle has no volume). Note
on/off based on linear counter > 0. Duration is approximate.

**In SysEx mode**: The synth reads the linear counter register and
applies the exact gating behavior frame by frame.

**For keyboard**: Triangle attack/release knobs shape the gate.

---

## Summary: How It All Works Together

```
                    ┌─────────────────────────┐
                    │     ReapNES Studio       │
                    │  ┌───────────────────┐   │
MIDI file ─────────→│  │  Input Cascade     │   │
(notes + CC +       │  │  1. SysEx → regs   │   │
 SysEx)             │  │  2. CC → vol/duty  │   │──→ Audio Out
                    │  │  3. ADSR → env     │   │
MIDI keyboard ─────→│  └───────┬───────────┘   │
                    │          ↓               │
                    │  ┌───────────────────┐   │
                    │  │  NES APU Engine    │   │
                    │  │  Pulse × 2        │   │
                    │  │  Triangle         │   │
                    │  │  Noise            │   │
                    │  └───────┬───────────┘   │
                    │          ↓               │
                    │  ┌───────────────────┐   │
                    │  │  Visual Console    │   │
                    │  │  Knobs + Scope    │   │
                    │  │  (animates w/     │   │
                    │  │   register data)  │   │
                    │  └───────────────────┘   │
                    └─────────────────────────┘
```

One plugin. Three input modes. One waveform engine. One visual UI.
The MIDI file carries the data. The synth plays it back. The knobs
move. The camera records.
