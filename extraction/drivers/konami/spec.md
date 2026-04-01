# Konami Pre-VRC Sound Driver — Specification

## Status: SUBSTANTIALLY DECODED (Castlevania 1)

Primary sources:
- "Castlevania Music Format v1.0" by Sliver X (romhacking.net #150)
- Contra (US) fully annotated disassembly (vermiceli/nes-contra-us)
- Castlevania (U) labelled disassembly + direct ROM analysis (this project)

## Driver Identity
- **Family name**: konami_pre_vrc (Maezawa variant)
- **Active period**: ~1986-1990
- **Primary target**: Castlevania (U) (V1.0) -- UxROM, mapper 2
- **Same driver family**: Contra, Super C, TMNT, Goonies II, Gradius II
- **Different driver**: Castlevania II uses Fujio variant (NOT compatible)
- **WARNING**: Same period table does NOT prove same driver. CV2 has
  identical period values but a completely different sound engine.

## Per-Game Differences (CRITICAL — read before adding a game)

The note/octave/repeat commands are shared, but these aspects VARY:

| Aspect | CV1 | Contra |
|--------|-----|--------|
| Mapper | 0 (NROM, 32KB) | 2 (UNROM, 128KB bank-switched) |
| Sound bank | N/A (linear) | Bank 1 ($4010-$8010) |
| Pointer table format | 9 bytes/track (3 ptrs + 3 seps) | Flat sound_table_00 (3 bytes/entry) |
| Pointer table addr | ROM $0825 | ROM $48F8 (CPU $88E8 in bank 1) |
| DX extra bytes (pulse) | 2 (instrument + fade) | 3 (config + vol_env + decrescendo) |
| DX extra bytes (triangle) | 0 | 1 (triangle config) |
| $C0-$CF | Rest with duration | Rest with duration (same) |
| Percussion | Inline E9/EA triggers | Separate channel, DMC samples |
| Volume envelopes | Parametric (fade_start/fade_step) | Lookup tables per level |
| Period table addr | ROM $079A | ROM $46E5 (bank 1) |

**BEFORE writing a parser for a new game**: complete the checklist in
`extraction/CLAUDE_EXTRACTION.md` section "Per-Game Parser Checklist."

---

## Complete Command Byte Format

### Note Commands (high nibble 0x0-0xB)

Each byte encodes pitch and duration:
```
Byte = [PITCH][DURATION]

Pitch (high nibble):
  0=C  1=C#  2=D  3=D#  4=E  5=F  6=F#  7=G  8=G#  9=A  A=A#  B=B

Duration (low nibble): 0-F
  actual_frames = tempo_value * (duration_nibble + 1)
  Duration 0 = 1 unit (shortest), Duration F = 16 units (longest)
```

MIDI note = pitch + (4 - octave) * 12 + 36

### Rest Command (high nibble 0xC)

```
CX = rest for duration X (same frame calculation as notes)
```

### Tempo + Instrument Command (high nibble 0xD)

The D command sets tempo AND is followed by instrument/envelope data:
```
DX II [FF] [F0 SS]

DX = set tempo to X (low nibble, 1-15)
II = instrument byte (APU register $4000 format: DDLCVVVV)
     DD = duty cycle: 0=12.5%, 1=25%, 2=50%, 3=75%
     L  = length counter halt (usually 1)
     C  = constant volume flag (usually 1)
     VVVV = volume (0-15)
FF = fade parameters (pulse channels only, NOT triangle)
     High nibble = fade start delay (frames before fade begins)
     Low nibble = fade step (volume decrement per frame after start)
F0 SS = optional sweep (if next byte == $F0, read SS as sweep register value)
```

**The instrument byte IS the raw APU register 0 value.** Examples:
| Byte | Duty | Volume | Description |
|------|------|--------|-------------|
| $F4 | 75% | 4 | Bright, medium volume |
| $F3 | 75% | 3 | Bright, soft |
| $F5 | 75% | 5 | Bright, louder |
| $B4 | 50% | 4 | Standard, medium |
| $74 | 25% | 4 | Thin, medium |
| $34 | 12.5% | 4 | Thinnest, medium |

### Octave Commands (0xE0-0xE4)

```
E0 = highest octave (C6-B6, period >> 4)
E1 = high octave (C5-B5, period >> 3)
E2 = mid octave (C4-B4, period >> 2)
E3 = low octave (C3-B3, period >> 1)
E4 = base octave (C2-B2, no shift)
```

Octave controls how many times the base period is right-shifted.
Higher shift = shorter period = higher frequency.

### Special E-Commands

```
E8 = enable volume fade processing (sets bit 4 of flags register)
     When enabled, volume decrements per the fade parameters
     set by the instrument command's FF byte.

E9 = trigger snare drum (calls sound routine with value 2)
EA = trigger hi-hat drum (calls sound routine with value 1)
```

E5-E7, EB-EF: **Invalid.** Would cause infinite-loop right-shift producing
silence. Sliver X's observation that E5-E7 are "silent" is confirmed.

### Control Commands (0xFD-0xFF)

```
FD XX YY = jump to subroutine at address YYXX (little-endian)
           Saves return address; returns after $FF

FE XX YY ZZ = repeat section at address ZZYY, count XX
              XX = $FF for infinite loop

FF = end of channel / return from subroutine
```

### Low Commands (0x10-0x2F, used in SFX and some music contexts)

From Contra disassembly (confirmed in CV1):
```
10 XX = set sweep register ($4001/$4005) to XX; 00 = disable sweep
11    = set alternate sweep/flag (bit 4 of flags)
20-2F = set duration multiplier AND APU config high nibble
        Low nibble (if not F) = duration multiplier
        Low nibble = F: next byte = duration multiplier
        Following byte = APU config high nibble
```

---

## Duration and Timing

### Duration Formula

```
actual_frames = tempo_value * (duration_nibble + 1)
```

Where tempo_value is the low nibble of the most recent DX command.

### Tempo to BPM (assuming duration 3 = quarter note)

| Command | Tempo | Quarter (dur 3) | BPM |
|---------|-------|-----------------|-----|
| D1 | 1 | 4 frames | 900 |
| D3 | 3 | 12 frames | 300 |
| D5 | 5 | 20 frames | 180 |
| D6 | 6 | 24 frames | 150 |
| D7 | 7 | 28 frames | 128.6 |
| D8 | 8 | 32 frames | 112.5 |
| DA | 10 | 40 frames | 90 |
| DF | 15 | 60 frames | 60 |

Vampire Killer uses tempo D7 throughout.

---

## Volume Fade System

The fade system is NOT a lookup table of predefined envelopes. It's a simple
parametric decay:

1. Note starts at the volume set by the instrument byte (VVVV field)
2. After `fade_start` frames, volume begins decrementing
3. Each subsequent frame, volume decreases by 1
4. The `fade_step` controls how many ticks between decrements
5. Volume stops at 0

From disassembly at $8562-$85BE:
```
per frame (if envelope flag set and note still playing):
  decrement fade counter ($0B,x)
  if counter == duration value ($00,x):
    subtract fade_step ($0D,x) from volume
    if volume <= 0: stop
  else:
    decrement counter again (double-speed decay after start point)
  write new volume to APU register $4000,x
```

**This means there are no envelope tables in ROM to extract.**
The "instrument" is fully defined by three bytes: the APU register value,
the fade start delay, and the fade step rate.

---

## Note Period Table

Located at ROM offset $079A (CPU $878A), 12 entries of 16-bit big-endian
period values for octave 4 (base octave, no shift):

| Index | Note | Period | Freq (Hz) | MIDI |
|-------|------|--------|-----------|------|
| 0 | C | $06AE (1710) | 65.38 | 36 (C2) |
| 1 | C# | $064E (1614) | 69.26 | 37 |
| 2 | D | $05F4 (1524) | 73.35 | 38 |
| 3 | D# | $059E (1438) | 77.74 | 39 |
| 4 | E | $054E (1358) | 82.31 | 40 |
| 5 | F | $0501 (1281) | 87.25 | 41 |
| 6 | F# | $04B9 (1209) | 92.45 | 42 |
| 7 | G | $0476 (1142) | 97.87 | 43 |
| 8 | G# | $0436 (1078) | 103.67 | 44 |
| 9 | A | $03F9 (1017) | 109.88 | 45 |
| 10 | A# | $03C0 (960) | 116.40 | 46 |
| 11 | B | $038A (906) | 123.33 | 47 |

Octave adjustment: period = base_period >> (4 - octave_value)

| Octave | Shift | C note MIDI | Range |
|--------|-------|-------------|-------|
| E0 | >>4 | 84 (C6) | C6-B6 |
| E1 | >>3 | 72 (C5) | C5-B5 |
| E2 | >>2 | 60 (C4) | C4-B4 |
| E3 | >>1 | 48 (C3) | C3-B3 |
| E4 | >>0 | 36 (C2) | C2-B2 |

---

## Master Pointer Table

15 tracks, 3 channels each (Sq1, Sq2, Tri), starting at ROM offset $0825.
Each entry is a 2-byte little-endian CPU address pointer.
Pointers are grouped by channel: Sq1 ptr, gap byte, Sq2 ptr, gap byte, Tri ptr.
9 bytes per track (3 pointers x 2 bytes + 3 separator bytes).

### Decoded Track Pointers

| Track | Sq1 (CPU) | Sq2 (CPU) | Tri (CPU) | Likely Song |
|-------|-----------|-----------|-----------|-------------|
| 1 | $9B80 | $9BCE | $9BF1 | Title? |
| 2 | $9C83 | $9D18 | $9DB5 | Vampire Killer (Stage 1) |
| 3 | $8DD0 | $8E3A | $8EA2 | Stalker? |
| 4 | $A10F | $9FC1 | $A2BE | |
| 5 | $AABE | $AB1D | $AB82 | |
| ... | ... | ... | ... | (13 more) |

Pointer conversion: CPU -> ROM = subtract $8000, add $10

---

## Sound Engine Architecture (from disassembly)

### Channel Memory Layout (zero-page RAM)

Each channel occupies 16 bytes at base address $80, $90, $A0, $B0, $C0, $D0:

| Offset | Name | Description |
|--------|------|-------------|
| +$00 | DURATION | Current note remaining frames |
| +$01 | PREV_PERIOD_HI | Previous period high byte |
| +$02 | ACTIVE | Channel active flag |
| +$03-$04 | DATA_PTR | Current read pointer (lo/hi) |
| +$05 | INSTRUMENT | APU register 0 value (duty/vol) |
| +$07 | VOLUME_STATE | Current volume with flags |
| +$08 | FLAGS | Bit flags: b0=SFX active, b3=subroutine, b4=envelope, b7=sweep |
| +$09 | TEMPO | Current tempo value |
| +$0A | OCTAVE | Current octave (0-4) |
| +$0B | FADE_COUNTER | Volume fade countdown |
| +$0C | FADE_START | Fade start delay value |
| +$0D | FADE_STEP | Volume decrement rate |
| +$0E-$0F | RETURN_PTR | Subroutine return address |

### Channels

| X Register | Channel | APU Base |
|-----------|---------|----------|
| $80 | Pulse 1 (music) | $4000 |
| $90 | Pulse 2 (music) | $4004 |
| $A0 | Triangle (music) | $4008 |
| $B0 | Noise (music) | $400C |
| $C0 | Pulse 1 (SFX) | $4000 |
| $D0 | Pulse 2 (SFX) | $4004 |

### Update Loop (per frame)

1. Check if music is active ($E2)
2. Handle global fade-out if active
3. Loop through channels: X = $80, $90, $A0, $B0, $C0, $D0
4. For each active channel:
   a. Decrement duration counter
   b. If expired: read next command byte and execute
   c. If not expired: process volume fade (if envelope flag set)
5. SFX channels ($C0, $D0) override music channels ($80, $90)

---

## Remaining Unknowns

| Question | Confidence in Answer | Status |
|----------|---------------------|--------|
| Whether the fade byte (FF) is always present after instrument | 0.7 | Need to verify with more song data |
| Exact behavior of $20-$2F commands in music context | 0.5 | Documented for SFX, unclear in music |
| Noise channel command differences from pulse | 0.6 | Triangle skips fade; noise may have differences |
| Track-to-song-name mapping for all 15 tracks | 0.3 | Only Track 2 = Vampire Killer confirmed |
| Whether D0 command has different behavior than D1-DF | 0.5 | Sliver X says "extremely slow" |

---

## Confidence Summary

| Component | Confidence | Source |
|-----------|-----------|--------|
| Note encoding (pitch+duration) | 0.95 | Sliver X + ROM verification |
| Octave commands and period shift | 0.95 | Disassembly + ROM verification |
| Tempo = low nibble of DX, duration = tempo*(dur+1) | 0.95 | Disassembly verified |
| Instrument byte = APU register 0 (DDLCVVVV) | 0.90 | Disassembly analysis |
| Fade system (parametric, not table-based) | 0.85 | Disassembly analysis |
| Note period table at $878A | 0.95 | ROM hex + frequency verification |
| E8 = enable envelope fade flag | 0.85 | Disassembly bit analysis |
| E5-E7, EB-EF = invalid/silent | 0.90 | Disassembly loop analysis |
| FD/FE/FF control flow | 0.95 | Sliver X + Contra disassembly |
| Channel memory layout | 0.80 | Disassembly + Data Crystal RAM map |
| Master pointer table at $0825 | 0.95 | Sliver X + ROM verification |
