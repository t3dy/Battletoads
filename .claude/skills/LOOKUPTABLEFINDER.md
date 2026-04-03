---
name: lookuptable-finder
description: Find and decode lookup tables in NES ROM data — period tables, envelope tables, arpeggio tables, noise period maps, duty cycle tables.
---

# LOOKUPTABLEFINDER

Find all lookup tables used by a NES music driver.

## What to Find

1. **Period table** — maps note indices to 11-bit APU timer periods
   - Standard NTSC tables have 60-72 entries (5-6 octaves)
   - Each entry is 2 bytes (little-endian), decreasing values (low notes = high periods)
   - First entry is typically C2 (period ~1710) or C1 (~3420)
   - Verify: entries should follow the 2^(1/12) ratio between adjacent semitones

2. **Envelope tables** — volume shapes applied per-frame to notes
   - Typically 4-16 bytes per envelope
   - Values 0-15 (NES volume range)
   - Common patterns: attack-decay (15,12,9,6), sustain (8,8,8,8), staccato (15,8,0,0)

3. **Arpeggio tables** — semitone offsets applied per-frame for chord effects
   - Typically 3-8 bytes per arpeggio pattern
   - Values are signed semitone offsets (0, 4, 7 = major chord)
   - Look for repeating small values near other music data

4. **Noise period map** — maps drum note indices to noise channel periods
   - 16 possible noise periods (4-bit, 0-15)
   - Often stored as a simple byte array

5. **Duty cycle table** — maps duty indices to the 2-bit duty value
   - Values 0-3 (12.5%, 25%, 50%, 75%)

## Method

### Step 1: Find the period table
```
Scan PRG ROM for sequences of decreasing 16-bit values where:
- Adjacent ratio is ~1.059 (2^(1/12))
- Values range from ~56 (B6) to ~1710 (C2) or ~3420 (C1)
- Sequence length is a multiple of 12
```

### Step 2: Cross-reference with driver code
```
Search for LDA/STA instructions that index into the table address.
The period table is typically accessed via:
  LDA table_addr,Y  or  LDA (ptr),Y
where Y = note_index * 2 (since entries are 2 bytes)
```

### Step 3: Find envelope tables
```
Near the period table or song data, look for:
- Arrays of values 0-15
- Referenced by envelope command handlers
- Indexed by envelope ID from song data
```

### Step 4: Verify against trace
```
For each table entry, compute the expected frequency:
  freq = 1789773 / (16 * (period + 1))  [pulse]
  freq = 1789773 / (32 * (period + 1))  [triangle]
Compare against Mesen trace periods to confirm the table is correct.
```

## Battletoads Reference

- Period table: ROM $8E22, 60 entries (C2-B6), standard NTSC
- Accessed at $88EE: `LDA $8E20,Y` (Y = processed note index * 2, offset by 2 for the $81 base)
- The table itself is confirmed correct — the interpretation error was in the transposition, not the table
- Extended range: the driver uses notes below C2 (B1=period 1812, A1=period 2034) — these are computed by the driver, not stored in the table
