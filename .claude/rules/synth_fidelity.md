---
description: Synth plugin fidelity rules — CC automation, ADSR, dual-mode contract
globs:
  - "studio/jsfx/**"
  - "scripts/generate_project.py"
---

# Synth Fidelity Rules

The goal is note-accurate reproduction of original NES game music.
Every design decision serves this goal.

## 0. One Synth Plugin (ReapNES Studio)

All functionality lives in ONE JSFX file. Not multiple plugins for
different modes. The user opens one synth, it auto-detects what to do.
See docs/SYNTHMERGE.md for the full design.

## 1. Three-Priority Input Cascade

The synth operates in three modes per channel, auto-selected by
incoming data (highest available priority wins):

**Priority 1: SysEx register replay** (maximum fidelity):
- SysEx F0 7D 01 arrives → raw APU register state drives waveform
- All NES behaviors reproduced: sweep, phase reset, noise mode
- Volume, duty, period come from register bytes, not MIDI
- This IS the NES hardware running in software

**Priority 2: CC-driven mode** (file playback, no SysEx):
- CC11 arrives → volume from CC11, ADSR bypassed
- CC12 arrives → duty from CC12
- Period from MIDI note number (semitone-quantized)
- Misses: sweep vibrato, sub-semitone pitch, noise mode, phase reset

**Priority 3: ADSR keyboard mode** (live composing):
- No file data received → ADSR envelope shapes note
- Sweep, vibrato, duty from knob/slider positions
- Game-specific presets capture each game's characteristic sound
- CC123 or CC121 resets back to this mode

Why: SysEx register replay bypasses all MIDI encoding limitations.
CC mode is a fallback for files without SysEx. ADSR is for live play.
The cascade ensures the best available data always drives the sound.

## 2. CC11 = Volume (Expression)

- MIDI CC11 maps to NES volume: `nes_vol = floor(msg3 * 15 / 127)`
- Applied directly to channel output level
- Typical: 4-5 CC11 changes per note (per-frame updates from NSF)
- Pulse channels: full 0-15 range with decay/release ramps
- Triangle: always 127 (gate signal — triangle has no hardware volume)
- Noise: no CC11 (velocity-driven)

## 3. CC12 = Duty Cycle (Timbre)

- MIDI CC12 maps to NES duty: values 0-3 (12.5%, 25%, 50%, 75%)
- Mapping: 0-31→0, 32-63→1, 64-95→2, 96-127→3
- Applied to pulse waveform lookup table index
- Changes per-frame alongside CC11 (synchronized by NSF extraction)
- Only applies to pulse channels (triangle/noise have no duty)

## 4. Note Duration = Period Change

In NSF-extracted MIDIs, note boundaries are NOT arbitrary MIDI decisions.
They occur when the NES APU period register changes value:

- Period changes from X to Y → note_off for old, note_on for new
- Duration = number of frames the driver held the period constant
- Minimum: 32-48 ticks (2-3 frames, ~33-50ms)
- Typical: 96-200 ticks (6-12 frames, ~100-200ms)
- Maximum: 1344+ ticks (84+ frames, ~1.4s)
- Granularity: 16 ticks per frame (TICKS_PER_FRAME = 16 at 128.6 BPM)

The MIDI note duration and CC11 envelope are independent:
- Duration = when period changes (pitch boundary)
- CC11 = volume shape within that duration (amplitude envelope)

A note can be "silent" for its last N frames if CC11 decays to 0
before the period changes. This is correct NES behavior.

## 5. What Each Channel Sounds Like (CV1/Contra reference)

**Pulse 1 (lead melody):**
- ~309 notes in Vampire Killer, ~4 CC11 updates per note
- Typical pattern: attack at vol 15, decay over 3-4 frames, sustain at vol 4-8
- Duty shifts during attack phase (brighter attack, mellower sustain)

**Pulse 2 (harmony/countermelody):**
- Similar density to Pulse 1 but slightly different envelope shape
- Castlevania uses duty=2 (50%) for Pulse 2 vs duty=1 (25%) for Pulse 1

**Triangle (bass):**
- CC11 = 127 always (no hardware volume control, only gate on/off)
- Duration alone controls articulation (staccato = short note, legato = long)
- 1 octave lower than pulse for same period value (32-step sequencer)

**Noise (drums):**
- No CC11. Velocity on note_on sets initial volume.
- Self-decaying: drums decay naturally via the ADSR in keyboard mode
- Note mapping: kick=36, snare=38, hi-hat=42, etc.

## 6. Never Do This

- Override CC11 volume with ADSR when CC data is present
- Use ADSR envelopes for file playback (that's what CC automation is for)
- Assume all games have the same envelope shape (CV1 ≠ Contra ≠ Mega Man)
- Ignore CC12 duty changes (they contribute to the per-frame timbre)
- Truncate notes based on volume (duration = period change, not volume=0)
- Use a flat synth (no envelope) for keyboard play (sounds lifeless)
