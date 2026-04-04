---
name: musicfinder-orchestrator
description: Orchestrate the finder skills to extract complete music data from a NES ROM. Coordinates PITCHFINDER, RHYTHMFINDER, ENVELOPEFINDER, SEQUENCEFINDER, LOOKUPTABLEFINDER, and COMMANDFINDER.
---

# MUSICFINDER ORCHESTRATOR

Coordinate all finder skills to extract a complete, accurate MIDI from NES ROM data.

## Extraction Pipeline

```
Phase 1: DISCOVERY
  ├── LOOKUPTABLEFINDER  → period table, envelope tables, arpeggio tables
  ├── COMMANDFINDER      → full command reference with param counts
  └── SEQUENCEFINDER     → song table, channel pointers, loop structure

Phase 2: PARSING (produces STRUCTURAL alignment only)
  ├── PITCHFINDER        → note bytes + transposition → base note indices
  ├── RHYTHMFINDER       → duration encoding → duration values (raw)
  └── ENVELOPEFINDER     → envelope IDs → envelope table references
  ★ "Zero parse errors" at this stage means byte-stream alignment.
    Parser output is a HYPOTHESIS, not musical truth.

Phase 3: EXECUTION SEMANTICS VALIDATION (MANDATORY before assembly)
  ├── Build frame-level simulator from parsed events + driver model
  ├── Simulate tempo accumulator, duration counters, pitch modulation,
  │   volume envelopes, duty cycle per frame
  ├── Compare simulated per-frame state against Mesen trace
  ├── Classify mismatches (tempo/duration/arpeggio/envelope/transpo)
  └── Block assembly until sim matches trace within thresholds
  ★ Only after this phase passes are parsed events "semantics-validated."

Phase 4: ASSEMBLY (only after Phase 3 passes)
  ├── Combine validated pitch + rhythm + envelope into Frame IR
  ├── Project Frame IR to MIDI events
  └── Generate REAPER project via generate_project.py

Phase 5: VALIDATION
  ├── Compare ROM-derived MIDI against trace timing (should match)
  ├── Compare ROM-derived pitches against fan MIDI (should match)
  └── Ear-check in REAPER (user confirms)
  ★ Only after ear-check passes may output be labeled "trusted."
```

## Invocation

When starting extraction for a new game:

### Step 1: Identify the driver
```
Run COMMANDFINDER to map the dispatch table.
This tells us the driver family (Konami, Rare, Capcom, etc.)
and reveals the command vocabulary.
```

### Step 2: Find the tables
```
Run LOOKUPTABLEFINDER to locate period tables, envelope tables, etc.
These are the "dictionaries" the driver uses.
```

### Step 3: Find the song structure
```
Run SEQUENCEFINDER to find how songs are organized.
Get the channel data pointers for the target song.
```

### Step 4: Parse pitches
```
Run PITCHFINDER to decode note bytes with transposition.
Verify against a known reference (fan MIDI, NSF, ear).
```

### Step 5: Parse timing
```
Run RHYTHMFINDER to decode note durations.
Verify against Mesen trace (frame-count between attacks).
```

### Step 6: Parse envelopes
```
Run ENVELOPEFINDER to decode volume envelopes.
Verify against trace CC11 data.
```

### Step 7: Execution Semantics Validation (MANDATORY before assembly)
```
Before assembling MIDI, validate parsed data against trace:
1. Build frame-level simulator from parsed events + driver model
2. Simulate tempo accumulator, duration counters, pitch modulation,
   volume envelopes, duty cycle per frame
3. Compare simulated per-frame state against Mesen trace
4. Produce mismatch taxonomy report
5. Block assembly until comparison passes thresholds

PASS: Period 90%+ match, volume 80%+ match, boundaries ±1 frame
FAIL: Diagnose by category, fix parser or model, rerun

★ Parser output is a hypothesis. This step validates it.
  Zero parse errors (Step 2-6) is structural; this is semantic.
```

### Step 8: Assemble
```
Only after Step 7 passes:
Combine validated data into Frame IR, then project to MIDI.
The MIDI should be generated from semantics-validated events,
with trace used for validation reference.
```

## Key Principle

ROM data = composer's intent (pitch source). Trace = hardware reality (validation target).
For MIDI generation, use ROM intent for pitch, trace for timing/envelope validation.
Never generate MIDI from trace periods alone. Parser output is hypothesis until
execution semantics validation passes (see `session_protocol.md` Gate 2).

## Per-Game State

Each game extraction should maintain:
- `extraction/manifests/<game>.json` — driver facts, table locations, command map
- `extraction/drivers/<family>/` — shared driver knowledge
- `output/<Game>/` — generated MIDI, RPP, validation reports
- Per-game validation record (use `templates/reports/GAME_VALIDATION_TEMPLATE.md`)
  with sections for: verified, approximate, hypothesis, unvalidated, artifact trust levels
- Noise channel documented separately (separate semantic domain)

See `.claude/rules/architecture.md` for anti-patterns and enforcement rules.
See `CLAUDE.md` Game Extraction Status table for per-game progress.
