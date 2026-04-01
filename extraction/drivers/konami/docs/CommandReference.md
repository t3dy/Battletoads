# Konami CV1 Command Byte Reference

Complete command set for the Castlevania 1 (Maezawa variant) sound driver.

## Quick Reference

| Byte Range | Type | Description |
|-----------|------|-------------|
| $00-$BF | NOTE | Pitch + duration in one byte |
| $C0-$CF | REST | Rest with duration |
| $D0-$DF | TEMPO+INST | Set tempo, followed by instrument data |
| $E0-$E4 | OCTAVE | Set octave (0=highest, 4=lowest) |
| $E5-$E7 | INVALID | Causes infinite shift loop (effective silence) |
| $E8 | ENVELOPE | Enable volume fade processing |
| $E9 | DRUM | Trigger snare |
| $EA | DRUM | Trigger hi-hat |
| $EB-$EF | INVALID | Same issue as E5-E7 |
| $F0 | SWEEP | Sweep register setting (context-dependent) |
| $FD | JUMP | Jump to subroutine |
| $FE | REPEAT | Repeat section N times |
| $FF | END | End channel / return from subroutine |

## Detailed Command Descriptions

### $00-$BF: Note

```
[PPPP][DDDD]

PPPP = pitch (0-11 maps to C, C#, D, D#, E, F, F#, G, G#, A, A#, B)
DDDD = duration nibble (0-15)

actual_frames = current_tempo * (DDDD + 1)
MIDI_note = pitch + (4 - current_octave) * 12 + 36
```

### $C0-$CF: Rest

```
[1100][DDDD]

DDDD = duration nibble (same formula as notes)
```

$C0 = shortest rest. $CF = longest rest.

### $D0-$DF: Tempo + Instrument

```
$DX $II [$FF] [$F0 $SS]

X = new tempo value (1-15)
II = instrument/APU register byte (DDLCVVVV)
FF = fade parameters (pulse only): high=start delay, low=step rate
F0 SS = optional sweep (if next byte after FF is $F0)
```

Triangle channel skips the FF fade byte.

### $E0-$E4: Set Octave

```
$EX where X = octave value (0-4)

E0 = highest (period >> 4, C6-B6)
E1 = high (period >> 3, C5-B5)
E2 = middle (period >> 2, C4-B4)
E3 = low (period >> 1, C3-B3)
E4 = base/lowest (no shift, C2-B2)
```

### $E8: Enable Envelope

Sets bit 4 of the channel flags register ($08+X).
When set, per-frame volume fade processing is active.
When clear, notes play at constant volume.

This command takes no arguments and does not advance the read pointer
beyond itself.

### $E9: Snare Drum

Triggers the snare sound effect. Must follow a note byte that defines
the drum hit's duration. The drum sounds simultaneously with the
preceding note.

For drum-only passages, set octave to E4 (silent) first so the
"note" before the drum trigger is inaudible.

### $EA: Hi-Hat

Same as E9 but triggers the hi-hat sound.

### $FD: Jump to Subroutine

```
$FD $LL $HH

Saves current read position as return address.
Jumps to CPU address $HHLL (little-endian).
Returns when $FF is encountered.
```

Used for shared musical phrases between channels or repeated motifs
within a channel.

### $FE: Repeat

```
$FE $CC $LL $HH

CC = repeat count ($FF = infinite loop)
$HHLL = CPU address to jump back to (little-endian)
```

### $FF: End / Return

If inside a subroutine (called via $FD): returns to saved address.
If at top level: ends the channel.

## Pointer Format

All pointers in the data stream are 16-bit little-endian NES CPU addresses.

```
Conversion to ROM file offset:
  rom_offset = cpu_address - $8000 + $10

Conversion from ROM file offset:
  cpu_address = rom_offset + $8000 - $10
```

## Byte Identification Algorithm

```python
def identify_command(byte, context):
    hi = (byte >> 4) & 0xF
    lo = byte & 0xF

    if hi <= 0xB:
        return ('NOTE', pitch=hi, duration=lo)
    elif hi == 0xC:
        return ('REST', duration=lo)
    elif hi == 0xD:
        return ('TEMPO_INSTRUMENT', tempo=lo)
        # Read next 1-3 bytes as instrument data
    elif hi == 0xE:
        if lo <= 4:
            return ('OCTAVE', value=lo)
        elif byte == 0xE8:
            return ('ENVELOPE_ENABLE',)
        elif byte == 0xE9:
            return ('DRUM_SNARE',)
        elif byte == 0xEA:
            return ('DRUM_HIHAT',)
        else:
            return ('INVALID',)
    elif hi == 0xF:
        if byte == 0xFD:
            return ('JUMP_SUB',)  # read 2 more bytes
        elif byte == 0xFE:
            return ('REPEAT',)   # read 3 more bytes
        elif byte == 0xFF:
            return ('END',)
        elif byte == 0xF0:
            return ('SWEEP',)    # context-dependent
        else:
            return ('UNKNOWN_F', value=byte)
```
