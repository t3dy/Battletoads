---
name: sequence-finder
description: Find song structure — how patterns/sections are organized, loop points, subroutine calls, song tables, channel pointers.
---

# SEQUENCEFINDER

Determine the high-level song structure: how the driver organizes music into songs, sections, patterns, and loops.

## What to Find

### 1. Song Table
- Where is the master song list?
- How does an NSF song number map to the driver's internal song data?
- What indirection layers exist? (song ID → pointer table → channel pointers)

### 2. Channel Pointers
- For a given song, where does each channel's data begin?
- Are pointers absolute (16-bit addresses) or relative (offsets from a base)?
- How many channels? (typically 4: pulse1, pulse2, triangle, noise; sometimes DMC)

### 3. Pattern/Subroutine System
- Does the driver support reusable patterns called from a main sequence?
- What command initiates a subroutine call? What command returns?
- How deep can calls nest?
- Are patterns shared between channels?

### 4. Loop Structure
- What command implements song looping?
- Is there a loop counter (play N times then continue)?
- Where is the loop-back address stored?
- Is there an infinite loop at the end of the song?

### 5. Section Transitions
- How does the driver transition between song sections (verse, chorus, bridge)?
- Are sections sequential in the data, or does the driver jump between addresses?
- Do transposition/envelope settings carry across section boundaries?

## Method

### Step 1: Find the init routine
```
The NSF init routine (called with song number in A register) sets up channel pointers.
Trace from the init address to find:
  - Song number → internal ID mapping
  - Internal ID → pointer table lookup
  - Channel pointer storage locations in RAM
```

### Step 2: Map the song data flow
```
Starting from a channel's data pointer, follow the byte stream:
- Track all jump/call/loop commands
- Build a graph of which addresses are visited
- Identify pattern boundaries (where calls happen and return)
```

### Step 3: Find loop points
```
A song loop is typically:
  CMD_JUMP <address_of_song_start>
at the end of the song data.
The jump target = loop point.
Measure the data between loop start and loop end to get the loop length.
```

### Step 4: Validate against trace
```
The Mesen trace of 2+ loops should show identical note patterns
repeating at the loop boundary.
Measure the loop length in frames and verify it matches the
data length computed from ROM parsing.
```

## Battletoads Findings

### Song Table
- Init routine: $8054 (TAX, LDA $8060,X → internal ID, JMP $880E)
- Song number → internal ID mapping at $8060
- NSF song index 2 → internal ID 4 → Level 1 (Ragnarok's Canyon)

### Channel Pointers (Song 3 / Internal ID 4)
- P1: $A15E
- P2: $A2CF
- Triangle: $A364
- Noise: $A408

### Subroutine System
- CMD 0x1E (2 params): subroutine/loop call — jumps to a relative address
  - Stores loop counter and return address at $0341-$0343,X
  - Used extensively in the song data (appears dozens of times)

- CMD 0x04 (0 params): return from subroutine
  - Restores the data pointer from saved return address

- CMD 0x01 (2 params): absolute jump — sets data pointer to a new address
  - Used for section transitions and song loops

### Loop Structure
- Song loop length: 4029 frames (67.1 seconds), confirmed by 5 repetitions in trace
- Loop mechanism: CMD 0x01 at end of song data jumps back to start
- CMD 0x01 at P2 offset 89: `01 D6 A2` → jump to $A2D6 (near start of P2 data)

### Data Organization
- Early P2 data (offsets 0-97): initialization + complex arpeggio patterns with rapid transposition changes
- Mid data (offsets 98-130): G2 and D2 note patterns (the bass riff components)
- The riff is assembled from subroutine calls, not stored linearly
