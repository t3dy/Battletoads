# Konami CV1 Channel Memory Map

## Overview

The sound engine uses 6 channel slots, each occupying 16 bytes in zero-page RAM.
Higher-numbered slots have priority over lower slots on the same APU channel.

## Slot Assignments

| Slot | Base Address | APU Channel | Purpose |
|------|-------------|-------------|---------|
| 0 | $80 | Pulse 1 ($4000) | Music |
| 1 | $90 | Pulse 2 ($4004) | Music |
| 2 | $A0 | Triangle ($4008) | Music |
| 3 | $B0 | Noise ($400C) | Music percussion |
| 4 | $C0 | Pulse 1 ($4000) | Sound effects (overrides slot 0) |
| 5 | $D0 | Pulse 2 ($4004) | Sound effects (overrides slot 1) |

The X register holds the slot base address during processing.
The channel index register ($AC) maps to APU register offsets:
$00 -> $4000 (Pulse 1), $04 -> $4004 (Pulse 2), $08 -> $4008 (Triangle), $0C -> $400C (Noise).

## Per-Channel Memory Layout

| Offset | Size | Label | Description |
|--------|------|-------|-------------|
| +$00 | 1 | DURATION | Remaining frames for current note |
| +$01 | 1 | PREV_PERIOD_HI | Previous note's period high byte (for portamento detection) |
| +$02 | 1 | ACTIVE | Channel active flag (non-zero = playing) |
| +$03 | 1 | DATA_PTR_LO | Current data stream pointer (low byte) |
| +$04 | 1 | DATA_PTR_HI | Current data stream pointer (high byte) |
| +$05 | 1 | INSTRUMENT | APU register 0 value (DDLCVVVV) |
| +$06 | 1 | (unknown) | Possibly reserved |
| +$07 | 1 | VOLUME_STATE | Current volume with envelope flags in high nibble |
| +$08 | 1 | FLAGS | Bit flags (see below) |
| +$09 | 1 | TEMPO | Current tempo value (from DX command) |
| +$0A | 1 | OCTAVE | Current octave value (0-4) |
| +$0B | 1 | FADE_COUNTER | Volume fade countdown timer |
| +$0C | 1 | FADE_START | Fade start delay (high nibble of FF byte) |
| +$0D | 1 | FADE_STEP | Volume decrement rate (low nibble of FF byte) |
| +$0E | 1 | RETURN_PTR_LO | Subroutine return address (low byte) |
| +$0F | 1 | RETURN_PTR_HI | Subroutine return address (high byte) |

## FLAGS Register ($08+X) Bit Definitions

| Bit | Mask | Name | Description |
|-----|------|------|-------------|
| 0 | $01 | SFX_ACTIVE | Set when a sound effect is overriding this music channel |
| 1 | $02 | (unknown) | |
| 2 | $04 | (unknown) | |
| 3 | $08 | IN_SUBROUTINE | Set when executing a $FD subroutine call |
| 4 | $10 | ENVELOPE_ENABLE | Set by E8 command; enables per-frame volume fade |
| 5 | $20 | (unknown) | |
| 6 | $40 | MUTED | Channel is muted |
| 7 | $80 | SWEEP_ACTIVE | Set when sweep register has been configured |

## Global Variables

| Address | Name | Description |
|---------|------|-------------|
| $22 | PAUSE_FLAG | Non-zero = game paused, music paused |
| $60 | SOUND_REQUEST | Sound/music number to play |
| $AB | CURRENT_SLOT | Current slot base address being processed |
| $AC | APU_OFFSET | APU register offset for current channel |
| $BA-$BB | DATA_READ_PTR | Working copy of current data pointer |
| $BC-$BD | TEMP_PERIOD | Temporary 16-bit period value during note setup |
| $E2 | FADEOUT_ACTIVE | Global music fade-out flag |
| $E3 | FADEOUT_TIMER | Global fade-out countdown |
| $EE | DRUM_FLAG | Set during drum trigger processing |
| $EF | PAUSE_MUSIC | Music pause flag |

## Update Loop Flow

```
UpdateMusic ($838A):
  1. Check global fadeout ($E2)
     - If active, decrement volumes globally
  2. Initialize slot loop: X = $80, APU_offset = $00
  3. For each slot:
     a. Store X to $AB (current slot)
     b. Store APU_offset to $AC
     c. Check if slot active ($02+X)
     d. If active: call _func_03D3 (process slot)
     e. Advance: X += $10, APU_offset += $04
     f. If X == $E0: return (all 6 slots processed)
  4. Processing order: $80, $90, $A0, $B0, $C0, $D0

_func_03D3 (process slot):
  1. Load data pointer from $03+X, $04+X into $BA/$BB
  2. Decrement DURATION ($00+X)
  3. If DURATION expired (== 0):
     -> Jump to _loc_047D (read next command)
  4. If DURATION not expired:
     -> Check pause flag
     -> Process volume fade (if envelope flag set)
     -> Return
```

## SFX Priority System

When a sound effect starts on slot $C0 (pulse 1 SFX):
- It sets the SFX_ACTIVE flag ($01) on slot $80 (pulse 1 music)
- The music slot's volume writes are blocked by _func_076B
- When the SFX finishes, the flag is cleared and music resumes

This is checked by _func_076B ($876B):
```asm
  ldx $AB            ; current slot
  cpx #$80           ; pulse 1 music?
  bne check_pulse2
  ldx $C2            ; check SFX slot active
  beq ok             ; if 0, no SFX, proceed
  jmp blocked        ; SFX active, skip APU write

check_pulse2:
  cpx #$90           ; pulse 2 music?
  bne ok
  ldx $D2            ; check SFX slot active
  beq ok
  jmp blocked
```
