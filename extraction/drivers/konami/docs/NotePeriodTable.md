# Konami CV1 Note Period Table

## Location

ROM offset: $079A (CPU address: $878A)
Label in disassembly: `_data_078A_indexed`

## Table Contents

12 entries, one per semitone, 2 bytes each (big-endian 16-bit period values).
These are the base periods for octave 4 (E4, the lowest octave).

| Index | Note | Hex | Decimal | Freq (Hz) | MIDI Note |
|-------|------|-----|---------|-----------|-----------|
| 0 | C | $06AE | 1710 | 65.38 | 36 (C2) |
| 1 | C# | $064E | 1614 | 69.26 | 37 |
| 2 | D | $05F4 | 1524 | 73.35 | 38 |
| 3 | D# | $059E | 1438 | 77.74 | 39 |
| 4 | E | $054E | 1358 | 82.31 | 40 |
| 5 | F | $0501 | 1281 | 87.25 | 41 |
| 6 | F# | $04B9 | 1209 | 92.45 | 42 |
| 7 | G | $0476 | 1142 | 97.87 | 43 |
| 8 | G# | $0436 | 1078 | 103.67 | 44 |
| 9 | A | $03F9 | 1017 | 109.88 | 45 |
| 10 | A# | $03C0 | 960 | 116.40 | 46 |
| 11 | B | $038A | 906 | 123.33 | 47 |

## Frequency Formula

```
frequency_hz = 1789773 / (16 * (period + 1))
```

Where 1789773 is the NTSC CPU clock rate.

## Octave Shifting

The driver uses right-shifting to produce higher octaves from the base table:

```python
actual_period = base_period >> (4 - octave_value)
```

| Octave Cmd | Value | Shifts | C Period | C Freq | C MIDI |
|------------|-------|--------|----------|--------|--------|
| E0 | 0 | >>4 | 106 | 1045.4 Hz | 84 (C6) |
| E1 | 1 | >>3 | 213 | 522.7 Hz | 72 (C5) |
| E2 | 2 | >>2 | 427 | 261.4 Hz | 60 (C4) |
| E3 | 3 | >>1 | 855 | 130.7 Hz | 48 (C3) |
| E4 | 4 | >>0 | 1710 | 65.4 Hz | 36 (C2) |

## Assembly Implementation

At $86C6-$86E3:
```asm
  ; High nibble of note byte (0-B) doubled as index into period table
  asl a              ; multiply by 2 (16-bit entries)
  tay
  lda _data_078A_indexed,y    ; load period high byte
  sta $BC
  iny
  lda _data_078A_indexed,y    ; load period low byte
  sta $BD

  ; Apply octave shift
  ldy $0A,x          ; load octave value
- tya
  cmp #$04           ; reached base octave?
  beq done           ; if yes, stop shifting
  lsr $BC            ; right-shift period high byte
  ror $BD            ; right-shift period low byte (with carry)
  iny                ; increment toward octave 4
  jmp -              ; loop
```

## MIDI Conversion Formula

```python
def cv1_to_midi(pitch_nibble, octave_value):
    """Convert CV1 note to MIDI note number."""
    # pitch_nibble: 0=C through 11=B
    # octave_value: 0-4 (E0-E4)
    base_midi = 36  # C2 at octave 4
    octave_offset = (4 - octave_value) * 12
    return base_midi + pitch_nibble + octave_offset
```

| Octave | C | D | E | F | G | A | B |
|--------|---|---|---|---|---|---|---|
| E0 | 84 | 86 | 88 | 89 | 91 | 93 | 95 |
| E1 | 72 | 74 | 76 | 77 | 79 | 81 | 83 |
| E2 | 60 | 62 | 64 | 65 | 67 | 69 | 71 |
| E3 | 48 | 50 | 52 | 53 | 55 | 57 | 59 |
| E4 | 36 | 38 | 40 | 41 | 43 | 45 | 47 |

## Detuning

Note that the right-shift method produces slightly detuned frequencies compared
to equal temperament. This is characteristic of NES music and is part of the
authentic sound. The period table values were likely hand-tuned by Konami's
programmers.
