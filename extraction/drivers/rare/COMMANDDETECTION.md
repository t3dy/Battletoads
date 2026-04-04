# Command Detection in the Rare Driver

## How the Driver Dispatches Commands

The Rare driver processes song data one byte at a time in a loop. Each
byte is classified by bit 7:

```
$88D1: INY                ; advance to next byte
$88D2: LDA ($37),Y        ; read byte from song data
$88D4: BMI note_handler   ; if bit 7 set (>= $80), it's a note/rest
$88D6: JMP cmd_dispatch   ; if bit 7 clear (< $80), it's a command
```

**Classification:**
- `$80` = rest (silence)
- `$81-$FF` = note (index = byte - $81 + transposition)
- `$00-$7F` = command (dispatched through jump table)

### Command Dispatch ($8B68)

```
$8B68: STX $39            ; save channel index
$8B6A: ASL A              ; command * 2 (for 2-byte table entries)
$8B6B: TAX                ; X = offset into table
$8B6C: LDA $8B7B,X        ; handler address low byte
$8B6F: STA $3A
$8B71: LDA $8B7C,X        ; handler address high byte
$8B74: STA $3B
$8B76: LDX $39            ; restore channel index
$8B78: JMP ($003A)         ; indirect jump to handler
```

**No range check.** The dispatch does ASL A + TAX + table lookup with no
CMP/BCC guard. Bytes 0x00-0x26 have valid handler addresses. Bytes 0x27+
would read past the table into code/data, producing garbage handler addresses.

In practice, the song data only uses 0x00-0x26.

## Complete Command Reference (39 Commands)

### Flow Control

| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x00 | 0 | $8BC9 | Channel off. Sets $0301,X = 0. Stops channel processing. |
| 0x01 | 2 | $8C19 | Absolute jump. Sets data pointer to addr_lo:addr_hi. Used for section transitions and song loop. |
| 0x04 | 0 | $8B59 | Save current position to $0313/$0314,X and RTS (exit frame handler). NOT subroutine return. |
| 0x05 | 0 | $8C8F | Loop decrement. Decrements $0343,X. If > 0, re-enter subroutine. If = 0, continue past CMD 0x1E params. |
| 0x1E | 3 | $8C6A | Subroutine call with loop. Params: count, target_lo, target_hi. Saves return addr to $0341/$0342,X. |
| 0x23 | 2 | $8C2A | Subroutine call (no loop). Saves addr to $03A4/$03A8. Params: target_lo, target_hi. |
| 0x24 | 1 | $8C3B | Save address context. Stores to $03AC/$03B0. |
| 0x25 | 0 | $8C4C | Restore address from $03A4/$03A8. |
| 0x26 | 0 | $8C5B | Restore address from $03AC/$03B0. |

### Pitch Control

| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x12 | 1 | $8DCD | Set transposition absolute. $0354,X = 0 + param. |
| 0x13 | 1 | $8DD9 | Add to transposition (signed). $0354,X += param. |
| 0x14 | 1 | $8DDF | Set transposition ALL channels. Writes param to $0354, $0358, $035C, $0360. |

### Duration Control

| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x06 | 1 | $8BE5 | Set persistent duration. $0351,X = param. All subsequent notes use this duration (no inline byte). |
| 0x07 | 0 | $8BDD | Clear persistent duration. $0351,X = 0. Notes revert to inline duration bytes. |

### Envelope & Volume

| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x03 | 3 | $8BEE | Set envelope parameters. Stores to $0321, $0322, $0324,X. |
| 0x08 | 3 | $8CBE | Set instrument (via $8CC4 subroutine). Stores to $0361, $0362, $0363, $0364,X. |
| 0x09 | 0 | $8CE6 | Clear instrument. $0361,X = 0. |
| 0x0C | 1 | $8D46 | Volume mode. Clears $0393,X, sets param via $8C08 subroutine. |
| 0x0F | 0 | $8DB5 | Clear arpeggio/volume mode. $0393,X = 0. |
| 0x1F | 2 | $8D37 | Set envelope override flags. Param1 -> $03A2,X, param2 -> $03A3,X. When $03A2 bit 7 is set, notes consume an extra byte. |
| 0x20 | 0 | $8D2F | Clear envelope override. $03A2,X = 0. |
| 0x21 | 0 | $8D24 | Clear persistent duration AND clear envelope override. |
| 0x22 | 0 | $8D2B | Enable per-note envelope byte. $03A2,X = $80. |

### Instrument & Timbre

| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x17 | 4 | $8CB2 | Full instrument setup. 3 bytes via $8CC4 subroutine + 1 byte duty to $0364,X. |

### Modulation

| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x0D | 3 | $8D66 | Arpeggio/tremolo mode 1. $0393,X = 1. 3 params to $0353, $0394/$0373, $0391,X. |
| 0x0E | 3 | $8D91 | Arpeggio/tremolo mode 2. $0393,X = 2. 3 params similar to 0x0D. |
| 0x16 | 3 | $8D5E | Vibrato + arpeggio. Sets $0371,X | $80, then falls into 0x0D body. |
| 0x15 | 0 | $8D56 | Clear vibrato. $0371,X = 0. |

### Tempo

| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x10 | 1 | $8DBD | Set tempo absolute. $33 = 0 + param. Higher = faster music. |
| 0x11 | 1 | $8DC8 | Add to tempo. $33 = $33 + param. Signed relative change. |

### Complex/Uncommon

| CMD | Params | Handler | Effect |
|-----|--------|---------|--------|
| 0x02 | 0 | $8BD1 | Clear bit 0 of $0311,X. Advances stream and re-enters via $8B02 alternate path. |
| 0x0A | 5 | $8CF4 | Complex setup via $8D08 (4 bytes) + 1 byte. Writes to $0382-$0384,X. |
| 0x0B | 5 | $8CEE | Same as 0x0A but with different initial computation. |
| 0x18 | 1 | $8DF1 | Set zp $40 = $81, zp $3F = param. SFX/special trigger. |
| 0x19 | 1 | $8DFD | Set zp $40 = $82, zp $3F = param. Shares 0x18 body. |
| 0x1A | 1 | $8E01 | Set zp $40 = $83, zp $3F = param. |
| 0x1B | 1 | $8E05 | Set zp $40 = $84, zp $3F = param. |
| 0x1C | 3 | $8E0D | Set zp $42, $4F, call $855E. 3 params. |
| 0x1D | 1 | $8E09 | Set zp $40 = $85, zp $3F = param. |

## How Parameter Counts Were Verified

### Method: Count INY in Handlers

Each INY instruction advances the song data stream pointer by 1 byte.
The number of INY instructions in a handler = number of parameter bytes consumed.

### Complications Found

1. **Subroutine calls within handlers.** CMD 0x08/0x17 call $8CC4 which
   has its own INY instructions. CMD 0x0A/0x0B call $8D08. The total param
   count = handler INY + subroutine INY.

2. **DEY undoing INY.** CMD 0x1F has 3 INY but also a DEY, making the
   effective count 2. A naive INY count gives the wrong answer.

3. **Shared handler tails.** CMD 0x13 jumps into CMD 0x12's code (sharing
   the INY there). CMD 0x11 jumps into CMD 0x10. CMD 0x16 falls through
   to CMD 0x0D. The effective param count depends on where in the shared
   code the jump lands.

4. **Branch-always patterns.** CMD 0x19-0x1D all load different values into A
   then BNE back to $8DF3 (CMD 0x18's body). BNE is always taken since
   A is non-zero. A linear disassembler would continue past the BNE and
   count INY from the next command's handler, giving a wrong count.

### Verification by Parsing

The ultimate verification: if all param counts are correct, parsing the
P2 data produces 0 errors and a clean song loop. Wrong counts cause the
stream to desynchronize — commands get misinterpreted as notes or vice versa.

**Result: 0 errors on P2 parse confirms all 39 parameter counts are correct.**

## Relevance to Our Project

### For the Parser

Every command's param count must be exact. One wrong count shifts the
stream and every subsequent byte is misinterpreted. The errors cascade
because a "note" byte (e.g., 0x83) consumed as a command parameter means
the next real command byte is interpreted as a note, and so on.

### For the ROMPARSER Skill

This is an example of "Command Boundary Detection" (Triangulation Strategy 3
from ROMPARSER.md). When the parser produces errors like "Unknown byte 0x22",
it means either:
- There are commands we don't know about (→ extend the dispatch table)
- A command's param count is wrong (→ stream desynchronized)
- The note handler consumes extra bytes we're not tracking (→ envelope override)

### For Other Games

Different Rare games may use the same driver but with a different number
of commands. The dispatch table size is not fixed. Always read beyond the
expected end to check for more entries. The table ends when the handler
address points to garbage (zero page, uninstrumented code, etc.).

## The Note Handler's Hidden State

The note handler at $88D9 consumes 1-3 bytes depending on state:

```
Base:      [note_byte]                        (1 byte, persistent duration)
Inline:    [note_byte] [duration_byte]        (2 bytes, no persistent dur)
Override:  [note_byte] [envelope_byte]        (2 bytes, persistent dur + override)
Both:      [note_byte] [envelope_byte] [dur]  (3 bytes, inline dur + override)
```

The envelope override is controlled by $03A2,X bit 7:
- CMD 0x22 sets it ($03A2,X = $80)
- CMD 0x20 clears it ($03A2,X = 0)
- CMD 0x21 clears it AND clears persistent duration
- CMD 0x1F param1 sets it directly (bit 7 of param1)

**Missing this state causes the parser to silently misalign.** The D2 riff
subroutine ($A34C) uses CMD 0x22 to enable per-note envelope bytes. Without
tracking this, every note after CMD 0x22 is misaligned by 1 byte.
