# Konami CV1 Timing and Tempo System

## Tempo Command

```
DX where X = 1-F (low nibble)
```

The tempo value is stored at channel offset +$09 and controls note duration.
D0 = special case, "extremely slow" per Sliver X (value 0 may cause issues).

## Duration Formula

```
actual_frames = tempo_value * (duration_nibble + 1)
```

Duration nibble is the low nibble of the note/rest byte (0-F).
Duration 0 = 1 unit, Duration F = 16 units.

### Assembly Evidence

At $8667-$8680:
```asm
_loc_0667:
  jsr _func_0743     ; advance read pointer
  dey
  lda ($BA),y        ; reload note byte
  and #$0F           ; get duration nibble
  sta $BC            ; store as loop counter
  beq +              ; if 0, skip multiplication (just use tempo)
  lda $09,x          ; load tempo value
  clc
- adc $09,x          ; add tempo to accumulator
  dec $BC            ; decrement counter
  bne -              ; loop until 0
  beq ++             ; done
+ lda $09,x          ; duration 0: just use tempo directly
++ sta $00,x          ; store as note duration countdown
```

When duration = 0: result = tempo (1 unit)
When duration = 1: result = tempo + tempo = 2 * tempo
When duration = N: result = (N + 1) * tempo

## Duration Table at Tempo D7

Vampire Killer uses tempo 7 throughout:

| Dur Nibble | Frames | Milliseconds | Musical Equivalent (~150 BPM) |
|-----------|--------|--------------|-------------------------------|
| 0 | 7 | 116.7 | 32nd note |
| 1 | 14 | 233.3 | 16th note |
| 2 | 21 | 350.0 | dotted 16th |
| 3 | 28 | 466.7 | 8th note |
| 4 | 35 | 583.3 | |
| 5 | 42 | 700.0 | dotted 8th |
| 6 | 49 | 816.7 | |
| 7 | 56 | 933.3 | quarter note |
| 8 | 63 | 1050.0 | |
| 9 | 70 | 1166.7 | |
| A | 77 | 1283.3 | |
| B | 84 | 1400.0 | dotted quarter |
| C | 91 | 1516.7 | |
| D | 98 | 1633.3 | |
| E | 105 | 1750.0 | |
| F | 112 | 1866.7 | half note |

## BPM Calculation

To determine BPM, you need to know which duration value corresponds to a beat.
This varies by song. For Vampire Killer in 4/4 time:

If duration 0 = 32nd note: BPM = 60 / (7/60 * 8) = ~64.3 (too slow)
If duration 1 = 16th note: BPM = 60 / (14/60 * 4) = ~64.3 (too slow)

Actually, Vampire Killer is approximately 150 BPM. At that speed:
- A 16th note = 100ms = 6 frames
- An 8th note = 200ms = 12 frames

Tempo 7 gives duration 0 = 7 frames (close to a 16th note at ~130 BPM).
The song is slightly slower than perceived 150 BPM, suggesting either:
- The perceived tempo comes from the note pattern, not individual note length
- Or some notes use duration 0 as ornamental (grace notes)

## MIDI Tempo Conversion

For MIDI export, use the formula:
```python
# Frames to seconds: frames / 60.0
# One "beat" in MIDI = one quarter note
# Need to determine which duration = quarter note for the song
# Then: BPM = 60 / (frames_per_quarter / 60)

def frames_to_midi_ticks(frames, ppq=480, tempo_bpm=120):
    """Convert frame count to MIDI ticks."""
    seconds = frames / 60.0
    ticks_per_second = ppq * tempo_bpm / 60.0
    return int(seconds * ticks_per_second)
```

## Tempo Changes Mid-Song

The DX command can appear multiple times within a channel's data.
When it appears, it always introduces a new instrument setting too
(the DX II [FF] format). A tempo change mid-song effectively resets
the instrument as well.
