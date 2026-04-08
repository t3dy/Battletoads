---
name: simulator-builder
description: Build a frame-level execution simulator for a NES music driver from parsed ROM events and validate it against Mesen trace captures. Use after structural parser alignment, before trusted MIDI/REAPER export.
---

# SIMULATOR BUILDER

Build a frame-level execution simulator for a NES music driver.
Use after structural parser alignment, before trusted MIDI/REAPER export.

Parser output is hypothesis until this simulator matches ground truth.
See `session_protocol.md` Gate 2 for acceptance criteria and checklist.

## Purpose

Given:
- a parsed event stream from ROM/NSF data
- a driver model hypothesis
- a Mesen capture or NSF emulation of real playback (ground truth)

Produce:
- a frame-by-frame simulated channel state
- a mismatch report against ground truth
- a clear taxonomy of what is still wrong

## What the Simulator Must Model

At minimum, model these layers in the same order the driver applies them:

1. Global frame clock
2. Tempo accumulator / tick gating
3. Per-channel duration counters
4. Event fetch / command dispatch
5. Persistent channel state updates
6. Note attack state
7. Per-frame modulation
8. Final register projection

### 1. Global Frame Clock

Simulation runs in NES frames, not MIDI ticks and not BPM.

Each iteration of the simulator is one driver frame.

### 2. Tempo Accumulator / Tick Gating

Many engines do not advance music on every frame.

Common patterns:

- decrement-and-fire countdown
- 8-bit accumulator overflow
- alternating divider
- per-song tempo reload

The simulator must explicitly model the real driver timing gate.

Do not infer note durations in musical time first and "convert back."
Always simulate the driver's native frame/tick logic.

### 3. Per-Channel Duration Counters

For each channel, track:

- current countdown
- whether duration is inline or persistent
- whether a rest consumes time like a note
- whether control commands consume a tick or are instantaneous

Questions to answer:

- Does the channel advance immediately when counter reaches zero?
- Does it decrement before fetch or after fetch?
- Can one frame consume multiple non-timing commands before landing on a note?

### 4. Event Fetch / Command Dispatch

The simulator must reuse the parser's structural event stream where possible,
but it may need additional metadata:

- raw byte offset
- command parameters
- loop targets
- call stack behavior
- mode flags

The simulator is not a second parser. It is the execution layer for the parser.

### 5. Persistent Channel State Updates

Track channel state that survives across events:

- instrument / register header values
- current volume register template
- duty cycle
- sweep settings
- transposition
- persistent duration
- arpeggio / vibrato flags
- loop state
- subroutine return state

### 6. Note Attack State

When a note event occurs, determine:

- base period
- attack volume
- initial register writes
- note duration load
- whether length counter high bits or restart flags are touched

Separate:

- base note intent
- final hardware period written that frame

### 7. Per-Frame Modulation

This is where many parsers fail.

Model whatever the driver actually does per frame:

- vibrato
- sweep
- arpeggio
- volume envelope
- duty changes
- periodic retriggers
- looped control patterns

If a note looks right only at onset but wrong on sustained frames, the missing
piece is usually here.

### 8. Final Register Projection

For each frame, produce the final observable state that should be comparable
to the trace:

- period low/high
- volume
- duty
- sweep
- linear counter if needed
- noise mode / noise period if needed

The simulator output should be as close as possible to the same ontology used
by the trace ingest path.

## Inputs

Preferred inputs:

- game manifest
- parsed event stream for one track/channel
- raw ROM or NSF image
- clean Mesen state capture
- known start/end frame window

Optional inputs:

- fan MIDI for pitch sanity
- annotated disassembly
- existing driver-family simulator

## Outputs

The simulator builder should produce artifacts like:

- `simulator.py` or game-specific simulator module
- frame-state dump for simulated output
- comparison report against trace
- mismatch summary
- updated manifest status

Recommended report fields:

- frames compared
- exact period matches
- sounding/not-sounding agreement
- volume agreement
- first mismatch frame
- likely mismatch category

## Workflow

### Phase 1: Minimize Scope

Start with:

- one track
- one clean capture
- one or two channels

Best first target is usually:

- the title track
- or a looped stage theme with minimal SFX contamination

Do not try to simulate the whole game first.

### Phase 2: Build the Narrowest Useful Simulator

Implement only what is already evidenced.

Example:

- pulse channels only
- note timing only
- period projection only
- no envelope yet

Then compare.

This is allowed as long as the missing layers are labeled clearly.

### Phase 3: Compare Immediately

Do not keep expanding the simulator without running trace comparison.

After every meaningful addition:

1. simulate frames
2. compare to trace
3. locate first divergence
4. explain it

### Phase 4: Classify Mismatches

Every mismatch should be classified into one of these buckets:

- timing gate mismatch
- duration load mismatch
- command arity mismatch
- loop/control-flow mismatch
- transposition mismatch
- envelope mismatch
- modulation mismatch
- channel-state initialization mismatch
- trace alignment mismatch

Do not say "simulator is off" without naming the category.

### Phase 5: Promote Carefully

Promotion ladder:

1. parser-aligned
2. simulator partially aligned
3. semantics-validated
4. trusted / production-ready

Only advance when evidence supports it.

## Design Rules

### Rule 1: Reuse Parser Artifacts

The simulator should consume parser output, not re-decode bytes from scratch
unless the parser lacks essential state.

If the simulator has to rediscover structure, fix the parser interface.

### Rule 2: Keep Channel State Explicit

Use a real channel-state object or dataclass with fields for every tracked
piece of state.

Do not hide important state in scattered locals once the simulator grows.

### Rule 3: Preserve Raw Offsets

Every simulated note/control action should be traceable back to:

- parser event index
- ROM/NSF offset
- frame number

This is essential for debugging first mismatch.

### Rule 4: Compare Against Trace Ontology

If the trace uses decoded values like:

- `$4006_period`
- `$4004_vol`

then produce simulated values in the same terms.

Do not compare incompatible layers like:

- MIDI notes vs APU periods
- intended note index vs post-modulation trace period

### Rule 5: First Mismatch Matters Most

The most valuable debugging datum is the first real divergence.

Always report:

- first mismatching frame
- simulated state at that frame
- trace state at that frame
- active parser event
- likely cause

### Rule 6: One Missing Layer at a Time

If timing is wrong, do not tune envelopes.
If control flow is wrong, do not tune vibrato.
If onset is wrong, do not polish sustain.

Fix the earliest causal layer first.

## Recommended File Pattern

For a new game:

- manifest: `extraction/manifests/<game>.json`
- parser: `extraction/drivers/<family or other>/<game>_parser.py`
- simulator: `extraction/drivers/<family or other>/<game>_simulator.py`

If the driver family is still uncertain, prefer `other/` until proven shared.

## Recommended Simulator API

Suggested shape:

```python
simulate_track(track_id, channel_name, num_frames) -> SimResult
compare_sim_to_trace(sim_result, trace_path, frame_window) -> CompareResult
```

Useful result fields:

- per-frame states
- note start frames
- event index active on each frame
- current counters / mode flags

## Anti-Patterns

1. Building MIDI first and calling it validation
2. Comparing parser note names directly to trace periods
3. Ignoring loop/control-flow because the opening bars sound right
4. Treating silence mismatch as harmless
5. Folding triangle/noise into pulse logic without evidence
6. Rewriting the parser inside the simulator
7. Marking output trusted because one channel matches

## Success Criteria

The simulator is useful when it can do all of the following:

- reproduce at least one channel's title or stage timing in frames
- report first mismatch deterministically
- prove whether the current parser/event model is semantically plausible
- guide the next reverse-engineering step

The simulator is semantics-validated when:

- simulated frame state matches the trace within agreed thresholds
- mismatch categories are understood for anything remaining
- parser + simulator together explain the audible result

## Short Version

The parser says what the bytes appear to mean.
The simulator proves whether the driver behaves that way.

Build the simulator as the bridge between those two claims.
