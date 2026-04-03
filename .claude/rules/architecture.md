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

## 9. Frame IR Is Mandatory (NON-NEGOTIABLE)

No trace -> MIDI conversion without Frame IR generation.
Trace-derived exports must follow:
  Trace -> canonical frame state -> Frame IR -> MIDI/CC/SysEx/project

Raw register changes are not yet musical events. Directly
opening a new MIDI note on every period change is a known
failure mode (Battletoads v3-v5 proved this). The Frame IR
layer interprets hardware behavior into stable musical events.

Anti-regression: any script that converts trace directly to
note events without Frame IR is a regression against the
proven CV1/Contra approach and must be rejected.

## 10. Different ROMs Use Different Music Engines

Do not hard-code one universal decoding model. Konami uses
Maezawa commands. Rare uses a dispatch table. Other engines
may be entirely different. The system must:
- Support per-game/per-engine profiles
- Attach route assumptions explicitly
- Record which assumptions succeeded or failed
- Allow adaptation without ad hoc improvisation

## 11. Snap Trace Periods to ROM Period Table

When the ROM period table is known, trace periods should be
snapped to the nearest table entry to determine the driver's
intended note. Raw trace periods include sweep unit modifications
and are typically 1-15 units off from the table value.

This is an interpretation decision that belongs in Frame IR,
not in the MIDI builder.

## 12. Three Layers Must Never Be Conflated

1. Observed hardware state (registers, counters, flags)
2. Inferred musical interpretation (Frame IR: notes, events, continuity)
3. Downstream projection (MIDI, RPP, synth, keyboard abstractions)

Each layer has different semantics and different debugging needs.
Skipping a layer or merging two creates bugs that are invisible
until the user hears the output.
