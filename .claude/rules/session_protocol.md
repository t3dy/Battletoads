# Session Protocol

## Working Order (mandatory)

1. Environment validity (session_startup_check.py)
2. Source identity and track mapping (DB + track_names)
3. Ground-truth comparison (Mesen vs NSF if both exist)
4. Route choice (nsf / trace / hybrid / apu2_sysex)
5. Run kitchen_sink.py — generates ALL routes, validates, compares
6. Inspect report — test fidelity route (SysEx/APU2) FIRST
7. If fidelity route sounds wrong: inspect Frame IR, then raw frame state
8. If fidelity route sounds right: compare CC/Console route for playability
9. Batch build (only after one song passes all gates)

Do not skip ahead. Do not change multiple layers at once.

## NON-NEGOTIABLE: Never Skip Frame IR

Trace-derived exports must follow:
Trace -> canonical frame state -> Frame IR -> MIDI/CC/SysEx/project projection.
Raw register changes are not yet musical events.
Direct period-change-to-note conversion is a known failure mode.
Validation should fail if a trace route bypasses Frame IR.

## Fix Order (mandatory)

Always: pitch -> timing -> volume -> timbre.
One hypothesis per test cycle.
Change one thing, rerun comparison.

## Debugging Order (mandatory)

1. Check SysEx/register replay first
2. If SysEx sounds correct -> problem is in CC encoding / projection
3. If SysEx sounds wrong -> problem is in source extraction or synth
4. NEVER debug MIDI before confirming FrameState is correct
5. Inspect Frame IR decisions before MIDI note events
6. Jump from raw trace straight to MIDI debugging is PROHIBITED

## Canonical Representation

Dense per-frame APU state is the source of truth.
Frame IR is the interpreted musical representation.
MIDI is a downstream projection, not the canonical form.
Debug by inspecting frame state and Frame IR, not MIDI events.

## Three Layers (never conflate)

1. **Observed data**: raw register writes, per-frame channel state
2. **Musical interpretation**: Frame IR with note boundaries, continuity, modulation
3. **Playback projection**: MIDI notes, CC, SysEx, RPP, synth

## Three Use-Cases (never collapse)

1. **Archival fidelity**: SysEx/register replay for ROM-accurate playback
2. **Editable project**: CC-driven REAPER project for DAW work
3. **Live keyboard**: ADSR-based synth for modern composing

## Data Tier Rules

- SQLite (data/pipeline.db): operational truth
- JSON: structured config, game profiles, route learnings
- Markdown: reasoning, postmortems, session notes
- Raw files (CSV, ROM, NSF): stay on disk, indexed by DB
- Frame IR (frame_ir.json): per-run interpretation artifact

## Ground Truth Priority

1. Mesen trace (actual APU hardware state)
2. ROM music data (driver's intended notes, from period table)
3. NSF extraction (6502 emulation -- may diverge from game)
4. Frame IR (interpreted musical events)
5. MIDI/CC encoding (downstream projection)
6. Synth interpretation (playback approximation)

When Mesen and NSF disagree, Mesen wins.
When MIDI and frame state disagree, frame state wins.
When trace period doesn't match ROM table, snap to nearest table entry.

## Delivery Gate

Nothing is "ready to test" unless:
- kitchen_sink.py ran successfully
- At least one fidelity route passed all blocking validations
- Report artifacts were produced
- Route assumptions are explicit
- SysEx/APU2 route was evaluated for fidelity
- Frame IR artifact exists and was inspected

Run session_startup_check.py + sync_jsfx.py before every delivery.
