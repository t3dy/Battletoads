---
layout: default
title: "NES Music Studio -- Invariants Registry"
---

# NES Music Studio -- Invariants Registry

This document catalogs every invariant that the extraction pipeline
depends on. Each invariant has been discovered through trace comparison,
disassembly reading, or hardware specification, and most have cost
multiple prompts to identify when violated. They are organized by layer:
ENGINE (sound driver logic), DATA (ROM layout and parsing), HARDWARE
(NES APU behavior).

Violation of any invariant produces specific, documented symptoms.
When debugging, check invariants in order of layer relevance before
forming hypotheses.

---

## INV-001: Phase 2 envelope decay cannot begin before frame 1

- **Layer**: ENGINE
- **Statement**: In the CV1 two-phase parametric envelope, the release
  phase start frame is clamped to a minimum of 1. Frame 0 always emits
  the initial volume with no decrement applied.
- **Implementation**: `phase2_start = max(1, duration - fade_step)`
  in `_cv1_parametric_envelope()`.
- **Evidence**: CV1 Vampire Killer trace, 1792 frames. Before the fix,
  9 notes where `fade_step > duration` caused `phase2_start` to go
  negative, triggering an extra decrement on frame 0. This produced 45
  volume mismatches on pulse 1 and 50 on pulse 2. After the fix: zero
  mismatches on both pulse channels.
- **Test**: `test_cv1_phase2_start_formula`
- **Violation consequence**: First frame volume is 1 step too low.
  The error is subtle on individual notes (1 out of 15 volume levels)
  but accumulates across short notes with high fade_step values,
  producing a consistently quieter attack than the hardware.

---

## INV-002: Parsers emit full hardware duration, never truncated

- **Layer**: DATA
- **Statement**: `duration_frames` in every `NoteEvent` must equal
  `tempo * (duration_nibble + 1)`. Parsers must not shorten notes for
  staccato or envelope effects. All temporal volume shaping is the
  frame IR's responsibility.
- **Implementation**: `ParsedSong.validate_full_duration()` checks
  every note in every channel and returns a list of violations.
  The `NoteEvent` dataclass docstring encodes this invariant directly.
- **Evidence**: Architectural decision enforced since the frame IR was
  introduced. When parsers truncated notes for perceived staccato, the
  IR could not apply correct envelope shaping because it lacked the
  true duration needed to compute phase 2 start frames and decrescendo
  thresholds.
- **Test**: `test_full_duration_invariant`
- **Violation consequence**: Timing drift between extracted IR and
  trace. The frame IR computes envelope phase boundaries from the full
  duration. If the parser shortens a note by even 1 frame, phase 2
  start shifts, decrescendo thresholds change, and volume mismatches
  cascade through the rest of the note.

---

## INV-003: resume_decrescendo bounces volume at 1, never 0

- **Layer**: ENGINE
- **Statement**: During the tail fade (decrescendo) phase of a note,
  volume decrements to 1 and holds. When the volume counter reaches 0,
  the engine increments it back to 1. Notes never go fully silent
  during decrescendo.
- **Implementation**: `vol = max(1, vol - 1) if vol > 0 else 0` in
  both `_contra_lookup_envelope()` (lookup and auto-decrescendo modes)
  and `_cv1_parametric_envelope()` (phase 2).
- **Evidence**: Contra disassembly line 411 shows the `inc` instruction
  that bumps volume back from 0 to 1 in `resume_decrescendo`. Trace
  confirmed: no pulse note reaches volume 0 during the decrescendo
  window.
- **Test**: `test_contra_bounce_at_1`
- **Violation consequence**: Notes go silent 15 or more frames early.
  The decrescendo window can span a significant portion of long notes.
  Without the bounce, the note disappears audibly before its duration
  ends, producing obvious gaps in sustained passages.

---

## INV-004: Triangle channel plays 1 octave lower than pulse for same period

- **Layer**: HARDWARE
- **Statement**: The NES triangle channel uses a 32-step waveform
  sequencer versus the pulse channel's 16-step sequencer. For the same
  timer period value, the triangle produces a frequency one octave lower
  than pulse. The pitch mapping must subtract 12 from the MIDI note
  number for triangle.
- **Implementation**: `midi -= 12` applied when channel type is
  triangle in `parser_to_frame_ir()`.
- **Evidence**: NES APU hardware specification. The 2A03 triangle
  sequencer steps through 32 values per cycle versus 16 for pulse,
  halving the output frequency for any given period register value.
- **Test**: `test_pitch_to_midi_triangle_offset`
- **Violation consequence**: Triangle notes sound 1 octave too high.
  Because the triangle has no volume control (it is either on or off
  at full amplitude), an octave error is immediately audible as the
  bass line playing in the wrong register. This was one of the first
  bugs caught by ear comparison to the game.

---

## INV-005: BASE_MIDI_OCTAVE4 = 36 (C2)

- **Layer**: DATA
- **Statement**: The Konami driver's octave 4 (the lowest E4 octave)
  maps to MIDI note 36 (C2). This is the anchor point for all pitch
  computation. Octave 0 (highest) maps to C6 = 84, descending by 12
  per octave number.
- **Implementation**: `BASE_MIDI_OCTAVE4 = 36` constant in
  `frame_ir.py`. MIDI note = `BASE_MIDI_OCTAVE4 + (4 - octave) * 12 + pitch`.
- **Evidence**: CV1 Vampire Killer trace comparison shows zero pitch
  mismatches across all 1792 frames at this value. Previous value of
  24 produced correct intervals but wrong absolute pitch (everything
  12 semitones too low). The trace comparison tool was itself fixed
  to compare MIDI notes rather than raw periods, which exposed the
  error.
- **Test**: `test_pitch_to_midi_base_octave4`
- **Violation consequence**: All notes shifted by a fixed number of
  semitones. Because the shift is systematic (every note is wrong by
  the same amount), automated trace comparison against period values
  shows zero mismatches. Only comparison against MIDI notes or human
  listening against the game catches this. This is the canonical
  example of a systematic error that self-referential testing cannot
  detect.

---

## INV-006: EC pitch adjustment shifts period table index by N semitones

- **Layer**: DATA
- **Statement**: The EC command adjusts the period table lookup index
  by a signed offset, effectively transposing all subsequent notes by
  N semitones. It must be parsed and applied, not skipped.
- **Implementation**: Parser tracks `pitch_adjust` state, adds it to
  the period table index during note lookup.
- **Evidence**: Contra Jungle trace. Before implementing EC parsing,
  every note on affected channels was off by +1 semitone. After the
  fix, pitch mismatches dropped to zero for those channels.
- **Test**: N/A (integration-level; verified through trace comparison).
- **Violation consequence**: All notes on the affected channel are
  shifted by a constant number of semitones from the point where the
  EC command appears. The shift persists until the next EC command or
  track restart. Because the offset is constant, the melody sounds
  "in tune with itself" but in the wrong key, making it easy to
  dismiss as correct without trace comparison.

---

## INV-007: Triangle linear counter sounding frames = (reload + 3) // 4

- **Layer**: HARDWARE
- **Status**: APPROXIMATE
- **Statement**: The NES APU triangle linear counter, loaded with
  reload value R, causes the triangle to sound for approximately
  `(R + 3) // 4` frames before silencing. This is an integer
  approximation of the real APU behavior.
- **Implementation**: `sounding_frames = min(duration, (tri_reload + 3) // 4)`
  in `parser_to_frame_ir()`, applied when triangle control bit is 0.
- **Evidence**: CV1 Vampire Killer trace. This formula produces 195
  sounding mismatches on the triangle channel across 1792 frames.
  The real APU clocks the linear counter at 240Hz (quarter-frame
  ticks), which does not divide evenly into 60Hz frame boundaries.
  The approximation is off by 1 frame on roughly 8 notes per loop.
- **Test**: N/A (known approximation; tracked as residual mismatch).
- **Violation consequence**: Triangle notes are gated 1 frame too
  early or too late on some notes. The error is inaudible in
  isolation (1/60th of a second) but shows up as sounding mismatches
  in the trace comparison report. A precise fix would require
  modeling quarter-frame clocking, which adds complexity for minimal
  audible benefit.

---

## INV-008: DX byte count is game-specific AND channel-specific

- **Layer**: DATA
- **Statement**: The DX instrument change command reads a different
  number of bytes depending on both the game and the channel type.
  CV1 always reads 2 bytes after DX. Contra reads 3 bytes for pulse
  channels and 1 byte for triangle.
- **Implementation**: `contra_parser.py` and `parser.py` have
  separate DX handling. The per-game manifest records the byte count.
- **Evidence**: Contra disassembly. The pulse DX handler reads
  volume envelope index, decrescendo multiplier, and duty cycle
  (3 bytes). The triangle DX handler reads only the linear counter
  reload value (1 byte). Using CV1's 2-byte assumption on Contra
  caused the parser to desynchronize from the data stream after the
  first instrument change.
- **Test**: N/A (enforced by parser structure; each parser hardcodes
  the correct byte count for its game).
- **Violation consequence**: Parser desynchronization. Reading too
  few bytes causes the parser to interpret instrument data as note
  commands. Reading too many bytes causes it to skip real note
  commands. Both produce cascading errors that corrupt every
  subsequent note in the channel. This is not a subtle bug -- the
  entire channel becomes garbage after the first wrong DX.

---

## INV-009: DECRESCENDO_END_PAUSE = (mul * duration) >> 4

- **Layer**: ENGINE
- **Status**: PROVISIONAL
- **Statement**: In the Contra decrescendo model, the tail fade
  begins when the remaining frames in the note fall below a threshold
  computed as `(decrescendo_multiplier * total_duration) >> 4`. This
  determines what fraction of the note gets the fade-out treatment.
- **Implementation**: `decrescendo_end_pause = (decrescendo_mul * duration) >> 4`
  in `_contra_lookup_envelope()`.
- **Evidence**: Derived from Contra disassembly `resume_decrescendo`
  routine. The multiplier byte is read from the DX instrument data.
  Not yet fully validated against an APU trace for Contra (trace
  capture pending).
- **Test**: N/A (provisional; awaiting trace validation).
- **Violation consequence**: Notes either fade too early (threshold
  too high, producing premature volume drop) or too late (threshold
  too low, producing an abrupt cutoff instead of a smooth fade).
  The audible effect depends on the multiplier value -- high
  multipliers make the error more obvious because the decrescendo
  window is a larger fraction of the note.

---

## INV-010: Derived timing indices must be clamped to valid execution domains

- **Layer**: ENGINE
- **Statement**: Any index or frame number derived from arithmetic
  on note parameters (duration, fade_step, fade_start, decrescendo
  multiplier) must be clamped to the valid range before use.
  Negative indices, indices beyond the note duration, and zero-length
  phases must all be handled explicitly. This is the general form of
  INV-001.
- **Implementation**: `max()` and `min()` calls at every derived
  timing computation. Examples: `phase2_start = max(1, ...)`,
  `sounding_frames = min(duration, ...)`.
- **Evidence**: INV-001 is the specific instance that cost the most
  debugging time. The general principle applies to every place where
  subtraction on unsigned-like quantities can produce out-of-range
  values.
- **Test**: N/A (design principle; specific instances have their own
  tests).
- **Violation consequence**: Varies by location. Common symptoms
  include volume applied to wrong frames, notes sounding longer or
  shorter than intended, and index-out-of-range crashes in envelope
  table lookups. The unifying pattern is that unclamped arithmetic
  on frame indices produces values outside the note's time domain,
  and the resulting behavior is undefined.
