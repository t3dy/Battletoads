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

Phase 2: PARSING
  ├── PITCHFINDER        → note bytes + transposition → correct MIDI notes
  ├── RHYTHMFINDER       → duration encoding → correct note lengths
  └── ENVELOPEFINDER     → envelope IDs → per-frame volume/duty shapes

Phase 3: ASSEMBLY
  ├── Combine pitch + rhythm + envelope into MIDI events
  ├── Use trace data for VALIDATION (not as primary source)
  └── Generate REAPER project via generate_project.py

Phase 4: VALIDATION
  ├── Compare ROM-derived MIDI against trace timing (should match)
  ├── Compare ROM-derived pitches against fan MIDI (should match)
  └── Ear-check in REAPER (user confirms)
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

### Step 7: Assemble
```
Combine all parsed data into a MIDI file.
The MIDI should be generated entirely from ROM data,
with trace used only for validation and timing reference.
```

## Key Principle: ROM Data = Authority

The ROM song data contains the composer's INTENT:
- The notes they wrote
- The rhythms they chose
- The envelopes they selected

The Mesen trace contains the HARDWARE REALITY:
- Periods after transposition and arpeggio
- Timing affected by tempo accumulator
- Volume after envelope processing

For MIDI generation, use ROM intent for pitch.
Use trace reality for timing validation and envelope CC data.
Never generate MIDI from trace periods alone — that was the Battletoads mistake.

## Per-Game State

Each game extraction should maintain:
- `extraction/manifests/<game>.json` — driver facts, table locations, command map
- `extraction/drivers/<family>/` — shared driver knowledge
- `output/<Game>/` — generated MIDI, RPP, validation reports

## Anti-Patterns (from ANXIETY.md)

1. **Don't polish trace-derived pitches** — fix the source (ROM parsing), not the symptom
2. **Don't assume one game's encoding works for another** — even same driver family can differ
3. **Don't skip validation against a known reference** — fan MIDI, NSF, or ear-check
4. **Don't generate MIDI before understanding the full command set** — unknown commands may affect pitch/timing
5. **When stuck, read the disassembly** — the 6502 code is the ultimate source of truth

## Current Status: Battletoads

### Completed
- [x] Period table found ($8E22, 60 entries)
- [x] Note encoding found ($81+N with transposition)
- [x] Transposition mechanism found ($0354,X, CMD 0x12/0x13)
- [x] Song table and channel pointers found
- [x] Loop length confirmed (4029 frames via trace)

### In Progress
- [ ] Full command parameter count verification (30 commands)
- [ ] Duration encoding (how note length is specified)
- [ ] Envelope table location and format
- [ ] Subroutine/pattern structure (CMD 0x1E call targets)
- [ ] Complete P2 song data parse with all commands decoded

### Blocked
- [ ] ROM-derived MIDI generation (needs complete command decoding)
- [ ] Multi-channel parsing (P1, Triangle, Noise)
