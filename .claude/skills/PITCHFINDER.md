---
name: pitch-finder
description: Find how a NES music driver encodes note pitches — period table location, note byte encoding, transposition mechanism, arpeggio tables.
---

# PITCHFINDER

Determine the complete pitch pipeline: how a note byte in ROM becomes a period value in the APU register.

## The Pitch Pipeline

Every NES music driver follows this chain:
```
ROM song data (note byte)
  → decode note index
  → apply transposition (if any)
  → apply arpeggio offset (if any, per-frame)
  → look up period table
  → write to APU $4002/$4003 (pulse) or $400A/$400B (triangle)
```

Each step can introduce a pitch shift. To get the INTENDED note, you must understand all steps.

## What to Find

### 1. Note Byte Encoding
- What byte range represents notes? (common: $80-$FF, or $81-$FF with $80=rest)
- How does the byte map to a table index? (common: byte - base = index)
- What is the base value? ($80? $81? $00?)

### 2. Transposition Register
- Does the driver add a per-channel offset before table lookup?
- Where is it stored? (RAM address, e.g., $0354,X)
- What commands set it? (absolute set, relative add)
- Does it change mid-song? (key changes, section transitions)

### 3. Arpeggio/Pitch Modulation
- Does the driver cycle through pitch offsets per frame?
- Where is the arpeggio table?
- How many frames per arpeggio step?
- Is it additive to the table index or to the period value?

### 4. Vibrato/Sweep
- Software vibrato: driver oscillates period ±N per frame
- Hardware sweep: $4001/$4005 register configured
- Both produce trace periods that differ from the base note

## Method

### Step 1: Find the period table (use LOOKUPTABLEFINDER)

### Step 2: Find code that writes to APU period registers
```
Search for STA $4002, STA $4006, STA $400A in the driver code.
Trace backwards to find where the period value came from.
This reveals the table lookup instruction (e.g., LDA $8E22,Y).
```

### Step 3: Trace the index computation
```
From the table lookup, trace backwards to find how Y was computed:
- Was it loaded directly from song data?
- Was a transposition value added?
- Was an arpeggio offset applied?
```

### Step 4: Find transposition commands
```
Search for STA to the transposition register address.
Find which command handlers write there.
Map those commands in the song data to track transposition changes.
```

### Step 5: Validate against known reference
```
Parse a known phrase from ROM song data.
Apply the pitch pipeline.
Compare resulting notes against a fan MIDI or NSF extraction.
All notes should match.
```

## Battletoads Findings

### Period Table
- Location: $8E22, 60 entries, C2-B6
- Standard NTSC values (1710, 1613, 1524, ... 56)

### Note Encoding
- Bytes >= $81 are notes
- $80 = rest
- Raw index = byte - $81
- Actual index = raw_index + transposition[$0354+X]
- Table lookup: LDA $8E20,Y where Y = (byte + transposition) * 2

### Transposition Mechanism
- Register: $0354,X (per-channel, X = 0/4/8/C)
- CMD 0x12 nn: transposition = nn (absolute set)
- CMD 0x13 nn: transposition += nn (signed relative add)
- Changes frequently within a song (section transitions, key changes)

### Critical Lesson
The Mesen trace captures periods AFTER transposition. Converting trace periods back to notes gives the TRANSPOSED note (e.g., E3 instead of E2). The ROM data has the INTENDED note. Always parse ROM data for pitch, use trace only for timing/envelope.

### Validation
Fan MIDI riff: E2(40) E2 E2 D2(38) E2 E2 E2 G2(43)
ROM data confirms: $88 = G2 (index 7), $83 = D2 (index 2) present in P2 song data
Trace riff: E3(52) E3 E3 A2(45) E3 E3 E3 A#4(70) — these are transposed values
