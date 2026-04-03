---
name: envelope-finder
description: Find how a NES music driver controls volume envelopes, duty cycle changes, and amplitude shaping — envelope tables, volume commands, decay patterns.
---

# ENVELOPEFINDER

Determine how the driver shapes each note's volume and timbre over time.

## What to Find

### 1. Volume Envelope System
- Does the driver use envelope lookup tables (indexed by envelope ID)?
- Or does it use per-note ADSR parameters set by commands?
- Or does it use a frame-by-frame volume sequence embedded in song data?

### 2. Envelope Table Format
- Location in ROM
- Number of envelopes, length of each
- Value range (0-15 for NES, possibly scaled)
- Loop points (does the envelope loop after reaching a sustain phase?)
- Release behavior (what happens when the note ends?)

### 3. Duty Cycle Control
- Is duty cycle part of the envelope (changes per frame)?
- Or set once per note by a command?
- Or set per-section and held constant?

### 4. Volume Commands
- What commands set the envelope ID for subsequent notes?
- Can volume be overridden directly (e.g., "set volume to N")?
- Is there a master volume per channel?

### 5. Constant Volume Flag
- The NES APU $4000/$4004 bit 4 controls constant vs envelope mode
- Does the driver use hardware envelopes (rare) or software-driven volume?

## Method

### Step 1: Find envelope table
```
Look for arrays of values 0-15 near the period table.
Cross-reference with driver code that reads from these arrays.
The envelope handler typically runs every frame:
  LDY envelope_index,X
  LDA envelope_table,Y
  STA volume_register
```

### Step 2: Find the envelope command
```
In the song data command handlers, look for writes to an "envelope ID" RAM location.
The handler for the envelope-set command typically:
  LDA (data_ptr),Y   ; read envelope ID from song data
  STA envelope_id,X  ; store per-channel
```

### Step 3: Trace the volume write path
```
Find where the driver writes to APU volume registers ($4000, $4004, $400C).
Trace backwards to find the volume source:
- Direct from envelope table
- Modified by a master volume
- Combined with a note velocity
```

### Step 4: Validate against trace CC11
```
The Mesen trace captures per-frame volume ($4000_vol, $4004_vol, $400C_vol).
Our MIDI uses CC11 for volume envelope.
Parse the envelope from ROM and compare the per-frame values against the trace.
They should match exactly.
```

## Battletoads Findings

### Envelope Commands
- CMD 0x03 takes 3 parameter bytes — likely sets envelope parameters
  - Found at P2 data offset 7: `03 B1 43 9A` and offset 92: `03 0A 43 38`
  - The parameters may encode: envelope ID, decay rate, sustain level

### Volume Write Path
- Driver writes to $4000/$4004 with constant-volume flag set (bit 4 = 1)
- Volume is software-controlled, not using APU hardware envelope
- Per-frame volume comes from the envelope table indexed by current envelope phase

### CC11 Validation
- Trace P2 volume pattern: attack=6 (max), decay over ~10 frames to 0
- This pattern repeats identically for each note in the riff
- The envelope shape is: 6, 5, 5, 4, 4, 3, 3, 2, 1, 0
- Total envelope length: ~10 frames per note

### Duty Cycle
- P2 trace shows duty=1 (25%) constant throughout the riff
- CMD 0x17 may set duty cycle (stores to $0364,X)
