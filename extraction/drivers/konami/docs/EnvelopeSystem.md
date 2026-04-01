# Konami CV1 Envelope System

## Key Discovery: No Envelope Tables

Unlike FamiTracker or modern chiptune tools that store instrument envelopes as
lookup tables (arrays of volume values per frame), **Castlevania 1's sound driver
uses a simple parametric decay system.** There are no envelope tables stored in ROM.

## How It Works

Each instrument's "envelope" is defined by exactly 3 parameters:

```
1. INSTRUMENT byte (II): Contains initial volume in bits 0-3
2. FADE_START byte (FF high nibble): Frames to wait before fade begins
3. FADE_STEP byte (FF low nibble): Volume decrement rate
```

### Per-Frame Processing

When the envelope flag is set (via E8 command) and a note is playing:

```
every frame:
  if fade_counter > duration:
    fade_counter -= 1
  else if fade_counter == duration:
    fade_counter -= fade_step
    if fade_counter < 0: silence channel
  else:
    fade_counter -= 1
    (double-speed decay after start point)

  write current volume to APU register
```

The assembly at $8562-$85BE implements this:
```asm
_loc_0562:
  ; Skip if noise channel or no envelope flag
  cpx #$B0
  beq rts
  lda $08,x         ; load flags
  and #$01          ; check SFX active flag
  bne rts

  ; Main fade loop
  lda $0B,x         ; fade_counter
  sec
  sbc #$01          ; decrement
  sta $0B,x
  cmp $00,x         ; compare to duration
  bne @not_at_start
  sec
  sbc $0D,x         ; subtract fade_step
  bcc @silence      ; if underflow, silence
  beq @silence
  rts

@not_at_start:
  sec
  sbc #$01          ; decrement again (double speed)
  sta $0B,x

@update_volume:
  lda $07,x         ; load volume state
  and #$0F          ; isolate volume bits
  sec
  sbc #$01          ; decrement volume by 1
  bpl @write
  rts               ; stop at 0

@write:
  lda $07,x
  sbc #$01
  sta $07,x
  jsr _func_076B    ; SFX priority check
  bcs rts
  ldx $AC           ; APU register offset
  sta $4000,x       ; write to APU
  rts
```

## Envelope Shapes Produced

With this system, all envelopes are **linear decays** from initial volume to 0:

```
Volume
  15 |████████
  14 |████████████
  13 |████████████████
   . |    ........
   1 |████████████████████████████████████████
   0 |____________________________________________
     0   start                               time ->
          |<-->|
        fade_start delay
```

### Example: Instrument $F4, Fade $41

```
Initial volume: 4 (from instrument byte low nibble)
Fade start: 4 frames delay
Fade step: 1 per frame

Frame 0-3: volume = 4 (waiting for fade start)
Frame 4: volume = 3
Frame 5: volume = 2
Frame 6: volume = 1
Frame 7: volume = 0 (silent)
```

### Example: Instrument $F5, Fade $82

```
Initial volume: 5
Fade start: 8 frames delay
Fade step: 2 per frame

Frame 0-7: volume = 5 (waiting)
Frame 8: volume = 3 (decremented by 2)
Frame 9: volume = 1
Frame 10: volume = 0 (silent, underflow clamped)
```

## Implications for Extraction

Since envelopes are parametric (not table-based), our extraction output should:

1. **Store the 3 raw parameters** (instrument byte, fade start, fade step) as the "instrument definition"
2. **Compute the envelope curve** at extraction time for MIDI CC11 output
3. **For REAPER integration**, either:
   a. Encode as MIDI CC11 automation (one CC event per frame during decay)
   b. Build the parametric decay into the JSFX synth plugin
   c. Use REAPER envelope lanes with computed breakpoints

Option (b) is most faithful — the JSFX plugin should implement the same
3-parameter decay, and the extraction just passes through the parameters.

## Comparison to Other NES Drivers

| Driver | Envelope System |
|--------|----------------|
| **Konami CV1** | Parametric decay (3 bytes: APU reg + fade start + fade step) |
| **FamiTracker** | Table-based (array of volume values, loopable, with release) |
| **Capcom** | Envelope index ($19 command), tables stored in ROM |
| **Contra** | Same Maezawa driver, likely identical parametric system |

This is simpler than most other NES drivers, which is consistent with
Castlevania being an early Konami title (1986) before the driver evolved.

## E8 Command: Envelope Enable Flag

The E8 command sets bit 4 of the channel's flags register ($08,x).
When this bit is set, the per-frame volume fade processing runs.
When clear, the volume stays constant until the next note.

Vampire Killer starts with E8 at the very first byte, meaning the
entire song uses volume fade on every note.

Some tracks may NOT use E8, meaning all notes play at constant volume
with no decay. This would sound more "organ-like" vs the "plucked" quality
that fade gives.
