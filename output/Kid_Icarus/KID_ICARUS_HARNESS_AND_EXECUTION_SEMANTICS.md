# Kid Icarus: Harness Architecture and Execution Semantics

## What Is a Harness?

A harness is a minimal 6502 program that wraps a game's music engine so it can run outside the game. Think of it like ripping a car engine out of the chassis and bolting it to a test stand — you need to provide fuel (game state), a starter motor (init call), and a way to measure output (APU register captures).

For most NES games, the NSF file IS the harness — someone already extracted the music driver, wrapped it with init/play entry points, and packaged it as a standalone file. For Kid Icarus, the NSF is from the wrong platform (FDS), so we need to build our own harness from the NES cartridge ROM.

## The Kid Icarus Engine Architecture

### Memory Map

The music engine lives entirely in **PRG bank 4** (ROM offset $10000-$13FFF), mapped to CPU $8000-$BFFF. The fixed bank 7 ($C000-$FFFF) contains the NMI handler that calls into the music code.

### Three-Phase Execution Model

Unlike Konami's clean "init once, play per frame" model, Kid Icarus uses three phases:

#### Phase 1: APU Initialization ($A008)

```
$A008: STA $4010    ; silence DMC
$A00B: STA $4011
$A010: STA $4015    ; enable all channels ($0F)
$A015: STA $4017    ; frame counter mode
$A01A: STA $4000    ; mute pulse 1 ($10)
$A01D: STA $4004    ; mute pulse 2 ($10)
$A020: STA $400C    ; mute noise ($10)
$A025: STA $4008    ; mute triangle ($00)
$A028-$A031: Clear $0300-$03FF (channel state)
$A033: Set $EF = $AA (magic flag)
```

This is clean and stateless. Call once.

#### Phase 2: Song Selection and Channel Setup ($81E4 → $855A → $8772 + $A896)

This is where it gets complicated. The game uses a **two-stage song init**:

**Stage A** ($81E4 → $855A → $8772): Reads game state (area index from ZP $3A, progression from ZP $3E/$3F) and writes a block of channel configuration data to $0200-$023F. This block describes which patterns, tempos, and envelopes each channel should use for the current game context.

**Stage B** ($A896): Reads $0350 (a song index set by the game engine), looks up a 13-byte channel config block from the $AC88 table, and copies it into the $0300 working area:

| Offset | Address | Purpose |
|--------|---------|---------|
| $032B | +0 | Transpose value |
| $032C | +1 | Control flags |
| $032D | +2 | Unknown |
| $032E | +3 | Envelope ID channel 0 |
| $032F | +4 | Envelope ID channel 1 |
| $0330-$0331 | +5,+6 | Sq1 music data pointer |
| $0332-$0333 | +7,+8 | Sq2 music data pointer |
| $0334-$0335 | +9,+10 | Triangle music data pointer |
| $0336-$0337 | +11,+12 | Noise music data pointer |

The $ABAB lookup table maps $0350 values to offsets in $AC88. We've identified **12 valid song configs** (indices 0-11).

Additionally, $A8B4-$A8BD sets $0340-$0343 = 1 (duration counters) and $A8C0-$A8CB sets $0338-$033B = 0 (data stream positions).

**This two-stage init is the main obstacle to standalone extraction.** In the real game, Stage A is part of a complex game loop that checks area, level, progression state, and possibly game mode before deciding what to write to $0200. Stage B happens when the actual music playback is triggered. We can bypass Stage A entirely and call Stage B directly with the correct $0350 index.

#### Phase 3: Per-Frame Playback ($A9AF)

Called once per NMI (60 Hz). The routine:

1. **$A8DE**: Checks if duration counters need resetting for envelope timing
2. **$A9B2-$A9B8**: Initialize frame — set X=0 (channel index), clear $0347 (APU register offset)
3. **$A9BE-$A9BF**: Channel loop — process channels 0-3 sequentially
4. **$A9C3-$A9C9**: Advance APU register offset by 4 per channel ($0347: 0→4→8→12 for $4000/$4004/$4008/$400C)
5. **$A9CF-$A9DC**: Load channel data pointer from $0330,X into ZP $E6/$E7. If hi byte is zero, skip channel.
6. **$A9E1-$A9E4**: Decrement duration counter $0340,X. If non-zero, skip to next channel (the note is still sustaining).
7. **$A9E6**: When counter hits zero, call $A988 to **read next byte from music data stream**.
8. **$A9EC-$A9F6**: Decode the byte:
   - `$FF` = loop/repeat marker
   - `$Cx` (top 2 bits = $C0) = set loop counter
   - Otherwise = note + duration data
9. **$AA21-$AA3F**: Process note byte. If top nibble = $B0, it's a **volume/envelope command** — look up from $AB86 table, store as duration in $0320,X. Otherwise proceed to note output.
10. **$AA46-$AA56**: Look up the note value Y in the period table at $AAFA/$AAFB. Store period lo to $0300,X and period hi (OR'd with $08 for length counter) to $0301,X.
11. **$AA8E-$AAA5**: Write to APU registers:
    - `STA $4000,Y` — volume/duty (from $E0, which is either $10=mute, $00=triangle-on, or envelope value from $0328,X)
    - `STA $4002,Y` — period lo (from $0300,Y)
    - `STA $4003,Y` — period hi + length (from $0301,Y)
    - `STA $4001,Y` — sweep (from $0344,X)
12. **$AAA8-$AAAE**: Load duration from $0320,X into $0340,X (next note's countdown), jump back to $A9BD for next channel.

### The Period Table

40 entries at $AAFA (as a combined hi/lo interleaved table), covering MIDI notes 33-73+ (A1 to C#6). The table uses the standard NES NTSC CPU clock (1,789,773 Hz). Period = CPU_CLK / (16 * frequency) - 1.

| Index (Y) | Period | Note | MIDI |
|-----------|--------|------|------|
| 0 | 2032 | A1 | 33 |
| 4 | 1710 | C2 | 36 |
| 28 | 855 | C3 | 48 |
| 52 | 427 | C4 | 60 |
| 70 | 253 | A4 | 69 |
| 98 | 105 | C6 | 84 |

The table is indexed by even values of Y (2 bytes per entry: hi at $AAFA,Y, lo at $AAFB,Y).

### Music Data Format

Each channel's music data is a byte stream starting at the pointer in $0330/$0331. Bytes are consumed by the $A988 subroutine which advances the stream position ($0338,X) and handles page crossings.

Byte encoding (preliminary — not fully validated):

| Byte Range | Meaning |
|-----------|---------|
| $00-$7F | Note value (Y index into period table) + duration |
| $B0-$BF | Volume/envelope command — low nibble + $032B (transpose) indexes into $AB86 table |
| $C0-$CF | Set loop counter ($0324,X) to low 6 bits |
| $F0 | Mute channel |
| $FF | Loop/repeat — if $0324,X > 0, decrement and reset stream position |

Duration bytes appear to be stored separately from note bytes (the $0320,X register holds the note's sustain time in frames, loaded from the $AB86 envelope lookup).

### Envelope System

$A922-$A92C handles per-frame envelope updates for the two pulse channels. It calls $A92C for X=0 and X=1, which:
- Checks $032E,X (envelope mode flag)
- Reads envelope shape data from a table indexed by $035B,X
- Applies per-frame volume changes to $035D,X
- Writes the result to $4000/$4004 via $A8F3 when $0307 flag is set

This is a **software envelope** system — the driver manually steps through volume values each frame, similar to Contra's lookup-table envelopes but with a different indexing scheme.

## Harness Construction

### What Works

```python
from py65.devices.mpu6502 import MPU

# Load ROM bank 4 at $8000 and bank 7 at $C000
# Call $A008 (APU init) — works, verified
# Call $81E4 (song select) — works, writes to $0200
# Call $A896 (channel setup) — works, loads $0330-$0337 with data pointers
# Call $A9AF per frame — PRODUCES APU WRITES with correct periods
```

### What's Still Missing

1. **Song routing**: The $0350 index that selects which of the 12 configs to use doesn't map obviously to the game's visible song numbers. The game's song-selection logic ($81E4) sets $0350 through a chain of area/level/state lookups. We need to either:
   - Map $0350 values to song names by playing each one and ear-matching
   - Trace the game's song-selection code to build a lookup table
   - Use Mesen to capture which $0350 value is active during each song

2. **Noise channel routing**: Song configs with Noise pointer = $0000 have no percussion. When the pointer is non-null, the noise channel is processed as channel X=3, but the playback code at $AA41-$AA43 branches to $AA1B (JMP $AADE) for noise, which uses a separate decode path.

3. **Triangle handling**: The code at $AA64: `CMP #$02; BEQ $AA73` and $AA83-$AA85: `CMP #$02; BEQ $AA8C` show triangle (channel 2) gets special-cased. Instead of the envelope value from $0328,X, triangle gets either $00 (on) or $10 (mute) — matching the hardware reality that triangle has no volume control.

4. **Envelope validation**: The envelope tables at $AB86 and $AC64 need to be decoded and validated against the trace to confirm the per-frame volume curves match.

## Execution Semantics: What We Mean and Why It Matters

### The Concept

"Execution semantics" is the bridge between **what the code says** (parsed bytes) and **what the hardware does** (APU register writes producing sound). Two things can go wrong:

1. **Parse error**: You read the bytes wrong (wrong command boundaries, wrong byte count). This is a structural problem — the stream doesn't align.
2. **Semantics error**: You read the bytes right but simulate them wrong (wrong tempo, wrong duration counter behavior, wrong envelope model). The notes look correct on paper but sound wrong.

Kid Icarus has both challenges:
- The music data format isn't fully decoded yet (parse phase in progress)
- The envelope system, duration model, and loop semantics need validation (semantics phase not started)

### The Validation Protocol

For each song extracted via the harness:

1. **Capture trace**: Play the song in Mesen, capture APU state (we have Song 1 already)
2. **Run harness**: Play the same song through py65, capture APU writes per frame
3. **Compare frame-by-frame**:
   - Period register ($4002/$4003): Do the harness and trace agree on which note is playing each frame?
   - Volume register ($4000 bits 0-3): Do the per-frame volume envelopes match?
   - Duration: Do note boundaries (period changes) happen at the same frame in both?
4. **Classify mismatches**:
   - Tempo drift: notes are right but timing diverges over time (accumulator error)
   - Duration error: notes are right length but off by ±N frames (counter model wrong)
   - Pitch error: wrong note entirely (period table index wrong, transpose wrong)
   - Envelope error: right note, wrong volume shape (envelope table misread)
   - Missing notes: harness drops notes the trace has (stream parsing error)

### Where Kid Icarus Is on the Validation Ladder

| Rung | Status | Evidence |
|------|--------|----------|
| 0 - Unexamined | Passed | We've looked at it |
| 1 - Parser-aligned | **In progress** | Harness produces APU writes but song routing and data format not fully decoded |
| 2 - Internal semantics | Not started | Need to match harness output against Mesen trace |
| 3 - External trace | Not started | Song 1 trace captured, comparison not yet run |
| 4 - Trusted projection | Not started | No MIDI/REAPER from harness yet |
| 5 - Full-game trusted | Not started | Only 1 of 12 songs traced |

The Mesen-based MIDI (`Kid_Icarus_01_Song_1_mesen_v1.mid`) is Rung 3 for Song 1 — it's built directly from the trace. But it only covers one song for the duration of the capture. The harness approach, once validated, would give us all 12 songs at whatever duration we want.

## Comparison: Kid Icarus vs Other Engines

| Aspect | Castlevania | Contra | Battletoads | Kid Icarus |
|--------|------------|--------|-------------|------------|
| Init complexity | 1 call | 1 call | 1 call | 3 calls + game state |
| Song selection | Pointer table | Pointer table | Pointer + music code | Area-indexed + game logic |
| Data format | Flat stream | Flat stream | Flat stream | Flat stream + command bytes |
| Envelope | 2-param decay | 54 lookup tables | Software vol register | Software vol + table lookup |
| Duration model | Nibble + tempo | Nibble + tempo | Dual-mode | Counter from lookup |
| Noise | Inline percussion | Inline percussion | Separate channel | Separate decode path |
| Game integration | None | None | Minimal | Deep (area, level, progression) |

### The Fundamental Difference

Konami and Rare engines are **music-first** — the game tells the driver "play song N" and the driver handles everything. The game code never touches music state after init.

Kid Icarus is **game-first** — the music engine is subordinate to game logic. The game decides what to play based on where the player is, what's happening, and how far they've progressed. The music init routines contain conditional branches, counter checks, and state comparisons. This makes standalone extraction harder because you need to provide (or fake) the game state that the init code expects.

This is likely a consequence of Kid Icarus being an early Nintendo title (1986) before the "clean driver" architecture pattern was widely adopted. Later Nintendo games (including Metroid, which shares some DNA with Kid Icarus) may or may not have the same characteristic.

## Next Steps

1. **Map $0350 to songs**: Play each of the 12 configs through the harness for 5 seconds, record the first 10 Sq1 period changes, then match against game audio (by ear or via additional Mesen captures)
2. **Decode the full music data format**: Parse the byte streams pointed to by $0330-$0337, identifying note bytes, duration bytes, loop markers, and command bytes
3. **Validate against trace**: Run Song 1 through the harness and compare frame-by-frame against the existing Mesen capture
4. **Build MIDI export**: Once semantics are validated, feed the harness output into mesen_to_midi.py to generate MIDI and REAPER projects for all 12 songs
5. **Noise decode**: Reverse-engineer the separate noise decode path at $AADE to capture drum hits
