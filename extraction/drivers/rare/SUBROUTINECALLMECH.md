# Subroutine Call Mechanism in the Rare Driver

## Why This Matters

The Rare driver doesn't store song data linearly. It uses reusable
subroutine patterns called from a main sequence with different
transpositions. Understanding this mechanism is essential because:

1. The riff pattern is assembled from multiple subroutine calls, not stored as E2-D2-G2
2. Wrong call/return handling desynchronizes the entire data stream
3. The mechanism explains why different song sections share the same raw note bytes

## The Three Flow Control Commands

### CMD 0x1E — Subroutine Call with Loop Count

**Format:** `1E <count> <target_lo> <target_hi>`

**6502 code at $8C6A:**
```
INY                    ; advance to count byte
LDA ($37),Y            ; read loop count
STA $0343,X            ; save to loop counter

INY                    ; advance past count
TYA                    ; A = current stream position
CLC
ADC $37                ; compute absolute address
STA $0341,X            ; save as return address (low)
LDA $38
ADC #$00
STA $0342,X            ; save return address (high)

; Now read the 2-byte target address
LDA ($37),Y            ; target_lo
STA temp
INY
LDA ($37),Y            ; target_hi
STA $38
LDA temp
STA $37                ; data pointer = target address
JMP main_loop_reset    ; start executing from target
```

**What it does:**
1. Saves loop count to $0343,X
2. Saves return address to $0341/$0342,X (points to the target_lo byte
   position within the CMD 0x1E params — this is key!)
3. Reads the 2-byte target address
4. Jumps to that address and starts executing

**Return address detail:** The saved address points to the target_lo/target_hi
bytes, NOT to the byte after CMD 0x1E. This is important for CMD 0x05.

### CMD 0x05 — Loop Decrement

**Format:** `05` (0 params)

**6502 code at $8C8F:**
```
DEC $0343,X            ; decrement loop counter
BEQ loop_done          ; if zero, exit loop

; Loop continues: re-enter subroutine
LDA $0341,X            ; load saved return addr (target_lo position)
STA $37
LDA $0342,X
STA $38
LDY #$00               ; Y = 0
JMP read_target         ; re-read target address and jump there again

loop_done:
; Loop expired: continue past the CMD 0x1E params
LDA $0341,X            ; load saved return addr
STA $37
LDA $0342,X
STA $38
LDY #$02               ; Y = 2 (skip past target_lo and target_hi)
JMP read_target         ; reads bytes at Y=2,3 as next address
```

**When count > 0:** Decrements counter, reloads the saved address (which
points to target_lo/target_hi), re-reads the target, and jumps back into
the subroutine for another iteration.

**When count = 0:** Loads the saved address, but sets Y=2 to skip past
the 2 target bytes. Then the code at $8C7F reads the 2 bytes at this
new position as an address... but wait.

**CRITICAL DETAIL:** When the loop expires, the code reads the 2 bytes
AFTER the target address as a new address to jump to. In our parser,
we handle this by computing: `ptr = return_addr + 2`, which points past
the target address bytes to the next command in the main sequence.

### CMD 0x23 — Call Without Loop

**Format:** `23 <target_lo> <target_hi>`

Similar to CMD 0x1E but without a loop count. Saves the return address
to $03A4/$03A8 (a different register pair than CMD 0x1E uses), reads a
2-byte target address, and jumps to it.

Return mechanism unclear — may use CMD 0x25 or CMD 0x04.

### CMD 0x01 — Absolute Jump (No Return)

**Format:** `01 <addr_lo> <addr_hi>`

Sets the data pointer to the given address. No return address saved.
Used for section transitions and the infinite song loop at the end.

When the target address is before the current position, it's a loop.

## How the Riff is Assembled

Battletoads Level 1, Pulse 2:

```
Main sequence at $A2CF:
  CMD 0x12 0x00          ; transposition = 0
  CMD 0x17 ...           ; instrument setup
  CMD 0x03 ...           ; envelope setup
  ...init...
  CMD 0x13 0xFD          ; transposition += -3 (now = -3)
  CMD 0x1E 0x02 $A2B1   ; call arpeggio pattern 2 times
  CMD 0x12 0x0C          ; transposition = 12
  CMD 0x1E 0x08 $A2B1   ; call SAME pattern 8 times (now at octave+1)
  CMD 0x1E 0x10 $A34C   ; call D2 riff 16 times
  CMD 0x13 0xFB          ; transposition += -5
  CMD 0x1E 0x01 $A232   ; call another pattern
  ...more calls with different transpositions...
  CMD 0x01 $A2D6         ; jump back to loop point

Subroutine at $A2B1 (arpeggio chord):
  CMD 0x03 ...           ; envelope
  CMD 0x06 0x02          ; persistent duration = 2
  NOTE 0x8F              ; raw index 14
  CMD 0x1F 0x04 0x02     ; envelope modifier
  NOTE 0x8A              ; raw index 9
  NOTE 0x8F              ; raw index 14
  NOTE 0x8F              ; 14
  NOTE 0x8A              ; 9
  NOTE 0x88              ; raw index 7
  NOTE 0x8F              ; 14
  CMD 0x1F 0x02 0x03     ; different envelope
  NOTE 0x88              ; 7
  NOTE 0x8A              ; 9
  NOTE 0x8F              ; 14
  NOTE 0x8F              ; 14
  NOTE 0x8A              ; 9
  NOTE 0x88              ; 7
  NOTE 0x8F              ; 14
  CMD 0x07               ; back to inline duration
  CMD 0x05               ; loop decrement (return or repeat)

Subroutine at $A34C (D2 riff):
  CMD 0x03 ...           ; envelope
  CMD 0x06 0x02          ; persistent duration = 2
  NOTE 0x83              ; raw index 2
  CMD 0x22               ; enable envelope override
  NOTE 0x83 0x04         ; index 2 + envelope byte
  NOTE 0x83 0x02
  NOTE 0x83 0x01
  NOTE 0x83 0x02
  NOTE 0x83 0x04
  NOTE 0x83 0x06
  NOTE 0x83 0x08
  CMD 0x21               ; clear override + duration
  CMD 0x05               ; loop decrement
```

**The key insight:** Raw bytes 0x8F/0x8A/0x88 are always indices 14/9/7
in the period table. But with transposition:

| Transposition | 0x8F (idx 14) | 0x8A (idx 9) | 0x88 (idx 7) |
|---------------|---------------|--------------|--------------|
| -3            | B2            | F#2          | E2           |
| 0             | D3            | A2           | G2           |
| 12            | D4            | A3           | G3           |

The SAME subroutine produces three different sections of the song just
by changing the transposition register before calling it.

## Relevance to Our Project

1. **Parser must follow calls:** Without subroutine handling, most of the song
   is missed. The main P2 sequence is only ~90 bytes of commands and jumps.
   The actual note data is in subroutines.

2. **Transposition tracking is critical:** The same raw note bytes produce
   different pitches depending on when they're called. The parser MUST track
   CMD 0x12/0x13 state changes between subroutine calls.

3. **Loop count drives song structure:** CMD 0x1E's count parameter determines
   how many times a pattern repeats. 16 iterations of the D2 riff at 8 notes
   each = 128 D2 notes.

4. **Subroutine data is shared:** The arpeggio pattern at $A2B1 is called
   from multiple points in the main sequence with different transpositions.
   This is efficient ROM storage but means the parser can't just read linearly.

5. **Return address points to CMD params, not past them:** The 6502 saves
   the return address at the target_lo byte position WITHIN the CMD 0x1E
   params. When the loop expires, it skips past these bytes (Y=2) to
   continue execution. Getting this wrong causes the parser to read the
   target address bytes as commands.
