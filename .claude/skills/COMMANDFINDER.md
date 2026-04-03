---
name: command-finder
description: Decode a NES music driver's command dispatch table — find every command, its parameter count, and its effect on driver state.
---

# COMMANDFINDER

Fully decode the music driver's command set: what each command byte does, how many parameters it takes, and what driver state it modifies.

## What to Find

For each command (0x00 through max_cmd):
1. **Handler address** — where in ROM the code lives
2. **Parameter count** — how many bytes follow the command byte
3. **Effect** — what RAM locations it modifies
4. **Category** — pitch, timing, envelope, flow control, channel control

## Method

### Step 1: Read the dispatch/jump table
```
The dispatch table contains 2-byte handler addresses for each command.
Table address is typically found in the main play loop where it does:
  ASL A           ; command * 2
  TAX
  LDA table,X    ; handler address low
  STA ptr
  LDA table+1,X  ; handler address high
  STA ptr+1
  JMP (ptr)       ; indirect jump
```

### Step 2: For each handler, determine parameter count
```
Count INY instructions before the handler jumps back to the main loop.
Each INY advances the data stream pointer by one byte.
The main loop entry does one INY itself, so:
  params = (number of INY in handler)
```

### Step 3: Categorize by effect
```
Examine what the handler writes to:
- $0354,X area → pitch (transposition)
- $0302,X area → timing (duration counter)
- $0361-$0364,X → envelope/duty
- $0303-$0304,X → flow control (data pointer)
- $0341-$0343,X → loop/subroutine state
- $0301,X → channel enable
- APU registers ($4000-$400F) → direct hardware control
```

### Step 4: Build the command reference
```
For each command, document:
  CMD 0xNN (P params): CATEGORY — description
  Handler: $XXXX
  Params: byte1 = ..., byte2 = ...
  Effect: writes to $XXXX
```

## Battletoads Command Reference (Partial)

### Dispatch Table: $8B7B (128 entries)

### Flow Control
| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x00 | 0 | $8BC9 | Channel off — sets $0301,X = 0 |
| 0x01 | 2 | $8C19 | Absolute jump — sets data pointer to param1:param2 |
| 0x04 | 0 | $8B59 | Return from subroutine — restores saved data pointer |
| 0x1E | 2 | $8C6A | Subroutine call — saves return addr, jumps to relative target |

### Pitch Control
| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x12 | 1 | $8DCD | Set transposition = param (absolute) |
| 0x13 | 1 | $8DD9 | Transposition += param (relative, signed) |

### Envelope/Timbre
| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x03 | 3 | $8BEE | Set envelope params (3 bytes: ID?, decay?, sustain?) |
| 0x17 | 1 | $8CB2 | Set value at $0364,X (duty cycle?) |

### Timing
| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x02 | 0 | $8BD1 | Toggle flag at $0311,X (possibly note-off or articulation) |

### Unknown (need investigation)
| CMD | Params | Handler | Notes |
|-----|--------|---------|-------|
| 0x05 | 1 | $8C8F | |
| 0x06 | 1 | $8BE5 | |
| 0x07 | 1 | $8BDD | |
| 0x08 | 1 | $8CBE | |
| 0x09 | 1 | $8CE6 | |
| 0x0A | 1 | $8CF4 | |
| 0x0B | 1 | $8CEE | |
| 0x0C | 1 | $8D46 | |
| 0x0D | 1 | $8D66 | |
| 0x0E | 1 | $8D91 | |
| 0x0F | 1 | $8DB5 | |
| 0x10 | 1 | $8DBD | |
| 0x11 | 1 | $8DC8 | |
| 0x14 | 0 | $8DDF | |
| 0x15 | 1 | $8D56 | |
| 0x16 | 1 | $8D5E | |

### Priority: Commands to decode next
1. **CMD 0x03** — envelope setup (3 params, very common)
2. **CMD 0x0C** — appears before note sections
3. **CMD 0x05/0x06** — appear near envelope changes
4. **CMD 0x1E** — subroutine call (need to verify parameter encoding)
5. **Duration encoding** — how note length is determined after a note byte

## How to Continue Decoding

For each unknown command:
1. Read 24-32 bytes at the handler address
2. Disassemble the 6502 code
3. Count INY instructions to determine param count
4. Identify the target RAM addresses (STA instructions)
5. Cross-reference: where else in the driver is that RAM address used?
6. Name the command based on its effect
