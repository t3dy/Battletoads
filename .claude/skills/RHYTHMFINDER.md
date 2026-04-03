---
name: rhythm-finder
description: Find how a NES music driver encodes note durations, tempo, and timing — duration tables, frame counts, tempo registers.
---

# RHYTHMFINDER

Determine how the driver controls note timing: when notes start, how long they last, and what sets the tempo.

## What to Find

### 1. Tempo System
- Does the driver use a frame counter with a tempo divider?
- Is tempo set by a command (e.g., "set speed N")?
- Is there a master tempo register in RAM?
- What is the relationship between the tempo value and actual BPM?

### 2. Note Duration Encoding
- Are durations embedded in the song data (byte after note)?
- Or does a duration command set a "current duration" that applies to subsequent notes?
- Are durations in frames, ticks, or driver-specific units?
- Is there a duration lookup table?

### 3. Frame Timing
- NES runs at ~60.0988 fps (NTSC)
- The music driver's play routine is called once per frame (typically via NMI)
- Each "tick" of the driver = 1 frame = ~16.64ms
- At 128.6 BPM with 4/4 time: 1 beat ≈ 28.6 frames

### 4. Rest/Silence Duration
- How does the driver encode silence between notes?
- Is $80 (rest) followed by a duration?
- Or does the volume envelope naturally decay to 0?

## Method

### Step 1: Find the duration counter
```
In the play routine, look for a countdown:
  DEC duration_counter,X
  BNE skip_next_note
This reveals the RAM address used for note duration.
```

### Step 2: Find where duration is loaded
```
Trace backwards from where the duration counter is set:
  LDA (data_ptr),Y   ; load duration from song data
  STA duration_counter,X
Or:
  LDA duration_table,Y  ; load from a lookup table
```

### Step 3: Find tempo control
```
Look for a frame accumulator pattern:
  LDA tempo_acc
  CLC
  ADC tempo_speed
  STA tempo_acc
  BCC skip_music_update  ; only update music when accumulator overflows
```

### Step 4: Validate against trace
```
Measure note durations in the Mesen trace (frame count between attacks).
Compare to values parsed from ROM song data.
They should match exactly.
```

## Battletoads Findings

### Tempo Accumulator
At $8865-$886D:
```
LDA $32       ; tempo accumulator
CLC
ADC $33       ; tempo speed value
STA $32       ; store back
ROR A         ; carry into bit 7
STA $34       ; $34 bit 7 = "process music this frame"
```
The driver uses a tempo accumulator. Music only advances on frames where the accumulator overflows. This means not every frame processes a new music tick.

### Duration Counter
At $8891:
```
DEC $0302,X   ; decrement duration counter for channel X
BNE done      ; if not zero, keep playing current note
```
Duration is stored at $0302,X (per-channel).

### Duration Source
Note durations come from the song data stream. After processing a note or command, the next byte(s) determine how long to wait. The exact encoding needs further investigation of how the counter gets loaded.

### Trace Validation
Trace note durations (frame gaps between P2 attacks):
- E3→E3: ~17 frames
- E3→A2: ~9 frames
- A2→E3: ~17 frames
- E3→A#4: ~9 frames
These are consistent across repetitions, confirming the timing is deterministic.
