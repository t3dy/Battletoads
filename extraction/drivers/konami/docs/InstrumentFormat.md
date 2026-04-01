# Konami CV1 Instrument Format

## The DX II FF Sequence

Instruments are not standalone definitions — they're always set as part of a
tempo command:

```
DX II [FF] [F0 SS]

DX = tempo command (X = speed value 1-15)
II = instrument byte (APU register $4000/$4004 format)
FF = fade parameters (pulse channels only)
F0 SS = optional sweep setting
```

## Instrument Byte (II)

The instrument byte is the **raw APU register 0 value**. Format: `DDLCVVVV`

| Bits | Field | Values | Description |
|------|-------|--------|-------------|
| 7-6 | DD | 0-3 | Duty cycle |
| 5 | L | 0-1 | Length counter halt (usually 1) |
| 4 | C | 0-1 | Constant volume flag (usually 1) |
| 3-0 | VVVV | 0-15 | Volume / envelope divider |

### Duty Cycle Values

| DD | Waveform | Sound Character |
|----|----------|----------------|
| 0 (00) | 12.5% pulse | Very thin, reedy, nasal |
| 1 (01) | 25% pulse | Thin, classic chiptune |
| 2 (10) | 50% pulse | Hollow, square wave |
| 3 (11) | 75% pulse | Same as 25% inverted, slightly different timbre |

### Common Instrument Bytes in Castlevania

| Byte | Duty | Vol | Description |
|------|------|-----|-------------|
| $F4 | 75% | 4 | Main melody (Vampire Killer intro) |
| $F3 | 75% | 3 | Softer melody |
| $F5 | 75% | 5 | Louder melody |
| $B4 | 50% | 4 | Square wave lead |
| $74 | 25% | 4 | Thin lead |
| $34 | 12.5% | 4 | Thinnest lead |
| $30 | 12.5% | 0 | Silent (mute) |

## Fade Parameter Byte (FF)

Only present for pulse channels (Sq1, Sq2). Triangle channel skips this byte.

```
FF = [SSSS][DDDD]

High nibble (S): Fade start delay — frames before volume begins decrementing
Low nibble (D): Fade step — controls decay rate
```

### How Fade Works

1. Note starts at volume VVVV from instrument byte
2. For `S` frames, volume remains constant (attack/sustain phase)
3. After start delay, volume decrements by 1 each frame
4. The fade_step value `D` controls the timing of decrements
5. When volume reaches 0, channel silences

### Common Fade Values

| Byte | Start | Step | Effect |
|------|-------|------|--------|
| $41 | 4 frames | 1 | Quick attack, moderate decay |
| $31 | 3 frames | 1 | Shorter attack |
| $21 | 2 frames | 1 | Quick pluck |
| $11 | 1 frame | 1 | Very quick pluck |
| $01 | 0 frames | 1 | Immediate decay |
| $82 | 8 frames | 2 | Long sustain, fast decay |
| $F1 | 15 frames | 1 | Very long sustain |

## Sweep Setting (Optional F0 SS)

If the byte after the fade parameter is $F0, the next byte is loaded as
the APU sweep register ($4001 or $4005):

```
Sweep register format: EPPPNSSS
  E = enable (1 bit)
  PPP = period (3 bits)
  N = negate (1 bit)
  SSS = shift count (3 bits)
```

This creates pitch bend effects. Not commonly used in Castlevania BGM
but available for sound effects.

## Triangle Channel

The triangle channel has **no volume control** (APU hardware limitation).
When the driver processes a DX command for the triangle channel:
- The tempo value is set from DX
- The instrument byte is read (but only the duty bits matter for the
  linear counter control, not volume)
- **No fade parameter byte is read** (the triangle can't fade)

## Extracting Instruments for MIDI/REAPER

For each DX II FF sequence encountered:

```python
instrument = {
    "duty_cycle": (II >> 6) & 3,      # 0-3
    "volume": II & 0x0F,               # 0-15
    "length_halt": (II >> 5) & 1,
    "constant_vol": (II >> 4) & 1,
    "fade_start": (FF >> 4) & 0xF,    # frames before decay
    "fade_step": FF & 0xF,             # decay rate
    "raw_apu_reg": II,                  # original byte for direct playback
    "raw_fade": FF,                     # original byte
}
```

### MIDI Output

- **Duty cycle** -> CC12 (timbre, nesmdb standard, value 0-3)
- **Volume** -> Note velocity (scaled: NES vol 0-15 -> MIDI vel 0-127)
- **Fade envelope** -> CC11 automation (one event per frame during decay)

### JSFX Synth

The JSFX plugin should accept these 3 parameters directly:
- slider for duty cycle (0-3)
- slider for initial volume (0-15)
- sliders for fade start and fade step
- Implement the same per-frame decay loop as the NES driver
