---
description: Architectural rules for the extraction pipeline
globs:
  - "extraction/**"
  - "scripts/**"
---

# Architecture Rules

These rules enforce the engine/data/hardware separation and prevent
the structural bugs that cost the most debugging time.

## 1. Parsers Emit Full-Duration Events

Parser note events MUST have `duration_frames = tempo * (nibble + 1)`.
No staccato, envelope shaping, or volume-based truncation in the parser.
All temporal shaping is the frame IR's responsibility.

Validation: `ParsedSong.validate_full_duration()` must return empty.

Why: Contra v1-v4 had incorrect note splitting that prevented the
frame IR from applying correct envelope shaping. Moving all shaping
to the IR fixed both the volume model and the duration accuracy.

## 2. Manifests Before Code

Every new game MUST have a manifest JSON in `extraction/manifests/`
BEFORE any parser code is written. The manifest declares:
- mapper and ROM layout
- pointer table location and format
- command format (DX byte count, percussion type)
- known facts vs hypotheses

Why: Without a manifest, assumptions get baked into code. The
CV1-to-Contra transition wasted 3+ prompts because DX byte count
was assumed, not checked.

## 3. DriverCapability Dispatches Envelope Strategy

The frame IR uses `DriverCapability` to select the volume model.
Never use isinstance checks on game name or parser class to branch
envelope logic.

Correct: `driver.volume_model == "lookup_table"`
Wrong: `isinstance(parser, ContraParser)`

Why: Implicit branching creates hidden coupling.

## 4. Status Labels Are Mandatory

Every driver module must have a STATUS comment block after the
module docstring. See parser.py for the format.

## 5. Triangle Is Always 1 Octave Lower

For the same NES timer period, the triangle channel produces
frequency half that of pulse (32-step vs 16-step sequencer).
`pitch_to_midi` subtracts 12 for triangle. This is HARDWARE fact.

## 6. Trace Is Ground Truth

After any change to parser or frame_ir code:
`PYTHONPATH=. python scripts/trace_compare.py --frames 1792`
Must show 0 pitch mismatches on CV1 pulse.

## 7. Derived Timing Must Be Clamped

Any timing value computed from parameters must use explicit
`max()` / `min()` to prevent negative or overflow values.
Example: `phase2_start = max(1, duration - fade_step)`.

## 8. Same Opcode Does Not Mean Same Semantics

DX reads 2 bytes in CV1, 3/1 in Contra. E8 means different
things. EC is unused in CV1 but shifts pitch in Contra.
Never copy command handling without checking the target game.
