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

1. **Observed** (ground truth): raw register writes, per-frame channel state.
   Authoritative. From Mesen trace or NSF emulation.
2. **Intent** (parser interpretation): parsed events, simulated driver state,
   Frame IR. HYPOTHESIS until validated against Observed.
3. **Projection** (generated output): MIDI, CC, SysEx, RPP, synth, musical
   claims. PROVISIONAL until Intent passes execution semantics gate.

Execution semantics validation is the gate between Intent and Projection.
If the gate is not passed, all Projection outputs are **hypothesis output**.

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

## ROM Parsing Pipeline Gates (mandatory for ROM-parsing routes)

### Gate 1: Parser Alignment (STRUCTURAL — not musical)

Parser alignment is confirmed when:
- All command boundaries, control flow, and variable-width events
  align with zero desync across all channels
- Subroutine calls nest and return correctly
- Loop points are detected and consistent

**"Zero parse errors" is a structural milestone only.**
It proves byte-stream alignment. It does NOT prove pitches, durations,
envelopes, or timing are correct. Parser output is a hypothesis.

### Gate 2: Execution Semantics Validation (SEMANTIC — required)

After parser alignment, simulate the driver frame by frame:
1. Tempo accumulator (exact 8-bit overflow logic)
2. Duration counters per channel (decrement per tick, advance on zero)
3. Pitch modulation (arpeggio, vibrato, sweep offsets per frame)
4. Volume envelopes (per-frame volume from envelope model)
5. Duty cycle state

Compare simulated per-frame output against Mesen trace.

Passes when:
- Period matches trace on 90%+ of sounding frames
- Volume matches trace on 80%+ of frames
- Note boundaries align within ±1 frame of trace attacks

Required artifacts:
- Parsed event stream
- Simulated frame-state trace
- Comparison report against Mesen trace
- Mismatch taxonomy (tempo drift / duration error / arpeggio error /
  envelope error / transposition error / alignment shift)

**No pitch/rhythm/timbre claims are valid until this gate passes.**

### Gate 3: Frame IR + Projection

Only after Gate 2 passes:
- Generate Frame IR from validated events
- Project to MIDI/REAPER
- Ear-check against game audio

## Validation Ladder (trust levels)

| Rung | Name | What it proves | May claim |
|------|------|---------------|-----------|
| 0 | Unexamined | Nothing | Nothing |
| 1 | Parser-aligned | Byte-stream structure | "command boundaries identified" — NOT pitches/durations/musicality |
| 2 | Internal semantics | Sim matches NSF within thresholds | "simulator agrees with emulator on [channels] for [N] frames" |
| 3 | External trace | Sim matches Mesen trace within thresholds | "execution semantics validated against hardware" |
| 4 | Trusted projection | Rung 3 + Frame IR + ear-check | "trusted output for [scope]" |
| 5 | Full-game trusted | All songs, all channels at Rung 4 | "complete validated extraction" |

Partial trust is normal. Different channels and songs may be at different rungs.
Noise channels are a separate semantic domain — document their rung separately.
Always state the scope: which channels, songs, frame range.

## Delivery Gate

Nothing is "ready to test" unless:
- kitchen_sink.py ran successfully
- At least one fidelity route passed all blocking validations
- Report artifacts were produced
- Route assumptions are explicit
- SysEx/APU2 route was evaluated for fidelity
- Frame IR artifact exists and was inspected
- For ROM-parsing routes: execution semantics validation passed (Gate 2)
- Parser alignment alone (Gate 1) is NOT sufficient for delivery
- Every delivered artifact is labeled with its Validation Ladder rung
- Artifacts below Rung 3 are labeled "hypothesis output" in delivery notes
- Noise channel status documented separately from melodic channels
- Per-game validation record updated (see `templates/reports/GAME_VALIDATION_TEMPLATE.md`)

Run session_startup_check.py + sync_jsfx.py before every delivery.

### Trust labeling in delivery

When describing output to the user, always state:
1. Which Validation Ladder rung the output has reached
2. Which channels and songs are validated at that rung
3. Whether the output is "trusted" or "hypothesis output"
4. What scope the trust covers (frame range, channels, songs)

Never describe hypothesis output as "done," "correct," "ready,"
or "the music." Use: "working draft," "practical artifact,"
"hypothesis output pending validation."

## Execution Semantics Checklist (for ROM-parsing sessions)

```
[ ] 1. Parser alignment — zero desync across all channels
[ ] 2. Command semantics verified — param counts, effects confirmed
[ ] 3. Frame simulator built — tempo, duration, modulation modeled
[ ] 4. Tempo/tick scheduling validated — accumulator overflow matches trace
[ ] 5. Duration boundaries validated — note attacks align with trace
[ ] 6. Modulation/arpeggio modeled — per-frame period offsets correct
[ ] 7. Envelope/volume behavior modeled — per-frame volume matches trace
[ ] 8. Simulated vs trace comparison run — mismatch report produced
[ ] 9. Mismatch categories explained — no unexplained divergences
[ ] 10. Only THEN: export MIDI / generate REAPER project
```
