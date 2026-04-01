# Konami CV1 Drum / Percussion System

## Overview

Castlevania 1 has only 2 drum sounds, triggered by inline commands within
any channel's data stream. There is no dedicated drum/noise channel track
in the pointer table — drums are embedded within the melodic channel data.

## Drum Commands

| Command | Sound | APU Value |
|---------|-------|-----------|
| $E9 | Snare | Calls sound routine with A=2 |
| $EA | Hi-hat (closed) | Calls sound routine with A=1 |

## How Drums Work

Drum triggers follow a note byte that defines the drum hit's duration:

```
[NOTE_BYTE] [E9 or EA]

The preceding note determines:
- Duration of the drum hit (from the note's duration nibble)
- The note itself also plays simultaneously on the current channel
```

### Drum-Only Passages

For sections that should be drums only (no pitched notes):
1. Set octave to E4 (effectively silent for melodic notes)
2. Write a note byte for timing (the pitch is inaudible at octave E4)
3. Follow with E9 or EA

```
E4           ; set octave to silent
B0 E9        ; very fast snare (B0 = B note, dur 0 = shortest)
BF E9        ; snare followed by long pause
B0 EA        ; very fast hi-hat
```

### Restrictions

- The drum command MUST be preceded by a note byte
- If E9/EA appears without a preceding note, "things will get VERY badly
  messed up" (Sliver X)
- Drums cannot be the last command before a FE repeat — the repeat must
  follow a note, not a drum

## Assembly Implementation

At $862E-$865B:
```asm
  lda ($BA),y        ; load current byte
  cmp #$E8           ; E8?
  beq handle_E8      ; -> envelope enable
  cmp #$E9           ; E9?
  beq handle_E9      ; -> snare
  cmp #$EA           ; EA?
  beq handle_EA      ; -> hi-hat
  and #$F0           ; mask high nibble
  cmp #$E0           ; octave command?
  bne note_handler   ; if not E-command, it's a note

handle_EA:
  lda #$01           ; hi-hat = sound 1
  jmp play_drum

handle_E9:
  lda #$02           ; snare = sound 2
  jmp play_drum

play_drum:
  jsr $8187          ; call sound loading routine
  iny                ; advance past drum command byte
  jmp $862E          ; continue reading (may have more drums/commands)
```

## Sound Routine ($8187)

The drum trigger calls a general sound-loading routine at $8187.
This routine is the same one used to start any sound effect in the game.
The accumulator value (1 or 2) selects which pre-defined drum sound to play.

The drum sounds themselves are defined elsewhere in ROM as short noise
channel sequences with specific period, mode, and volume decay settings.

## MIDI Mapping

For extraction to MIDI:

| CV1 Drum | MIDI Note | GM Drum Name |
|----------|-----------|--------------|
| E9 (snare) | 38 | Acoustic Snare |
| EA (hi-hat) | 42 | Closed Hi-Hat |

Use MIDI channel 3 (noise channel) for drum events.
Velocity should be 100-127 (drums in CV1 are always at full volume).
Duration from the preceding note byte determines the MIDI note length.

## Limitations

- Only 2 drum sounds (snare + hi-hat)
- No kick drum in CV1's music engine (later Konami games added more)
- Drum volume is not controllable (always plays at the sound effect's
  predefined volume)
- No DPCM drum samples (CV1 doesn't use the DMC channel for drums)

## Comparison to Contra

Contra (same Maezawa driver) has a more developed percussion system:
- 8 percussion sounds (0-7) mapped to different combinations of
  noise channel + DPCM samples
- Dedicated percussion command parser (`parse_percussion_cmd`)
- DPCM samples for kick, snare, and hi-hat

CV1's simpler 2-drum system reflects its earlier development (1986 vs
Contra's 1988).
