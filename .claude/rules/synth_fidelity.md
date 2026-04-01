---
description: Synth plugin fidelity rules — CC automation, ADSR, dual-mode contract
globs:
  - "studio/jsfx/**"
  - "scripts/generate_project.py"
---

# Synth Fidelity Rules

The goal is note-accurate reproduction of original NES game music.
Every design decision serves this goal.

## 1. Dual-Mode Contract: CC vs ADSR

The synth operates in two mutually exclusive modes **per channel**:

**CC-driven mode** (file playback):
- CC11 arrives → volume comes from CC11, ADSR bypassed
- CC12 arrives → duty comes from CC12, ADSR duty ignored
- cc_active[ch] flag set on first CC11/CC12 for that channel
- CC123 or CC121 resets cc_active[] (re-enables ADSR)

**ADSR mode** (keyboard play):
- No CC11/CC12 received → ADSR envelope shapes note
- Attack/Decay/Sustain/Release from slider values
- Game-specific presets in GAME_ADSR dict

Why: NSF-extracted MIDIs contain per-frame volume/duty as CC automation.
This IS the ground-truth envelope from the NES sound driver. The synth
must play it back verbatim. ADSR is only an approximation for live input.

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
