# Web Research: Super Mario Bros. ROM Music Engine

Technical research on the SMB1 sound driver internals, relevant to
understanding why py65 NSF emulation diverges from real hardware and
how to interpret the ROM's music data directly.

## SMB1 Sound Engine Architecture

### Note Encoding (two formats)

SMB1 uses indexed lookup tables, NOT direct period values.

**Uncompressed format (Square 2 / Triangle):**
- Bit 7 = flag: 1 = length byte, 0 = note byte
- Length bytes: $80-$87 index into a note-length lookup table (8 durations)
- Note bytes: bits 6-0 are an even offset into FreqRegLookupTbl
- $00 terminates Square 2 data

**Compressed format (Square 1 / Noise):**
- Note ID and length packed into one byte: BCNNNNNA
- 00NNNNN0 = note index (into frequency table)
- ABC = 3-bit length index (into length table)
- $00 terminates

Key insight: this is NOT the same encoding as Konami drivers (CV1,
Contra). Same NES hardware, completely different music data format.

### Sequencing Model

The driver is **streaming/linear**, not pattern-based:

- MusicHeaderData: table of byte offsets to song headers
- Each header contains:
  - Offset to the note length structure (8 duration values)
  - Pointer to track data
  - Fields for where P1, Triangle, Noise data begin
  - P2 data is always first
- Music requested via bit-fields (AreaMusicQueue etc.)
- Event music takes precedence over area music

### Frequency Register Lookup Table (FreqRegLookupTbl)

The period table stores 2-byte entries (high, low) for each note:

- Note value $06 -> bytes $02, $A6 -> period 678 (E3 at 164.7 Hz)
- Formula: freq = 1789773 / ((period + 1) * 16)
- Each note index is an even offset (multiply by 2)

This matches what we found in the ROM at CPU $FF09 — the period
table is byte-identical between the NSF and the World ROM.

### Note Length Lookup Table (SQ_NoteLenLookupTbl)

- 3-bit index (0-7) maps to frame counts
- Multiple length structures exist for different tempos/songs
- Different songs use different length sets
- This explains why Mario overworld notes are all 7 frames: the
  overworld song's length structure has 7 in one of its entries

### Key ROM Addresses

- Sound engine PLAY routine: ~$F2D0
- NoteLenLookupTblOfs: $F0 (zero page)
- FreqRegLookupTbl: in fixed bank ($C000-$FFFF)
- Music data: upper PRG ROM half

## Envelope / Volume Control

**SMB1 is fundamentally different from Konami drivers:**

- Relies on NES **hardware features** rather than software envelopes
- Uses hardware length counter ($4003/$4007/$400B) to time note durations
- Uses $4015 (channel enable) to turn channels on/off
- Only 3 basic channel commands: play note, rest, set note attributes
- Set note attributes controls: duty cycle + length for subsequent notes
- Square channels have portamento (pitch slide) capability
- **No per-frame software volume envelope** like Konami

This explains the Mesen data:
- Pulse volume decays 8->7->6->5->4->0 = hardware envelope decay
  (not software-driven like CV1's per-frame volume writes)
- const_vol=1 during music = direct volume control mode
- But the volume still decays = driver writes decreasing values

### Triangle Specifics

- No volume control (hardware limitation)
- Linear counter ($4008 bits 6-0) controls gate duration
- When linear counter reaches 0, triangle FREEZES at current
  waveform step (does NOT output zero — halts in place)
- Articulation comes entirely from note duration
- This freeze behavior matters: if emulation handles it wrong,
  the triangle will either cut too early or sustain too long

## Why NSF Emulation Diverges

The research identifies six specific factors:

### 1. Hardware Length Counter Timing

SMB1 uses the hardware length counter MORE than most drivers. NSF
emulators that don't perfectly emulate length counter edge cases
produce different note cutoffs.

**This is the most likely cause of the py65 period-halving bug.**
The length counter is loaded by writing to $4003/$4007. The upper 5
bits of that write set the length counter, and the lower 3 bits set
the period high byte. If the length counter interaction is wrong,
the effective period value changes.

### 2. $4017 Frame Counter Mode

The frame counter determines when length counters and envelopes are
clocked. Mode differences between 4-step and 5-step sequences can
cause timing discrepancies. py65 doesn't model the frame counter.

### 3. Write Timing

Real game: APU writes happen at specific CPU cycle positions.
NSF PLAY: called at fixed intervals that may not align with the
game's NMI timing. Register write ordering matters for the APU.

### 4. Sound Effect Interaction

In-game: sound effects preempt music channels. The driver reads
music data but does NOT write to APU when a SFX is active. This
keeps tracks in sync. NSF rips don't have SFX interference.

### 5. RAM State

The game may have residual RAM state (from gameplay, level loading)
that affects the sound engine. NSF initialization zeroes RAM, which
may not match the game's actual state when music starts.

### 6. Triangle Freeze Behavior

Triangle freezes at its current waveform step when the linear counter
reaches 0. If emulation goes to zero instead of freezing, the
triangle sounds different (clicking vs smooth cutoff).

## Implications for Our Pipeline

### The Period-Halving Bug

The research strongly suggests the py65 issue is related to how
$4003/$4007 writes interact with the length counter:

- When writing $4003, bits 7-3 load the length counter, bits 2-0
  are the period high byte
- If the length counter loading has a side effect on the period
  register (or if py65 doesn't properly latch the period), the
  effective period could be wrong
- Since the SAME period table is used (verified byte-identical),
  the error must be in how the driver's register write sequence
  interacts with py65's flat-RAM model

### What py65 Gets Wrong

py65 treats $4000-$4017 as flat RAM. But the real APU:
- Has write-only registers with side effects
- Resets the pulse phase when $4003/$4007 is written
- Reloads the length counter from a lookup table
- Triggers envelope restart
- $4015 read returns channel status bits (active/inactive)

The SMB1 driver checks $4015 to determine channel state. If py65
returns 0 for $4015 reads (because it was never written), the driver
may take a different code path — potentially one that selects a
different octave offset in the period table.

### The $4015 Hypothesis

**This is the strongest candidate for the root cause:**

The SMB1 driver reads $4015 to check if the length counter has
expired. If py65 returns 0 (flat RAM, never written), the driver
thinks the note has already expired and may skip ahead in the music
data, or may use a different register write pattern that produces
halved periods.

Test: intercept $4015 reads in py65 and return the correct status
bits (based on which channels have non-zero length counters).

## Key Sources

### Full Disassemblies

- Doppelganger's canonical disassembly:
  https://gist.github.com/1wErt3r/4048722
- SourceGen browsable HTML:
  https://6502disassembly.com/nes-smb/SuperMarioBros.html
- Isolated sound engine source:
  https://github.com/threecreepio/smb1-practiserom-smbspecial/blob/master/sound.asm

### Music Data Documentation

- Data Crystal SMB1 Notes format:
  https://datacrystal.tcrf.net/wiki/Super_Mario_Bros./Notes
- w7n's SMB Music Hacking Guide:
  https://www.romhacking.net/documents/630/
- NESDev forum frequency conversion:
  https://forums.nesdev.org/viewtopic.php?t=23603

### Tools

- SMBMusEdit (GUI music editor):
  https://github.com/anakrusis/SMBMusEdit
- SMB Music Engine Rewrite:
  https://github.com/danielpiron/SMB-Music-Engine-Rewrite-Prototype

### NES APU / NSF References

- NSF specification: https://www.nesdev.org/wiki/NSF
- APU reference: https://www.nesdev.org/wiki/APU

## Next Steps

1. Read the isolated sound.asm source to understand the exact $4015
   read pattern and how it affects note sequencing
2. Add $4015 read interception to py65 harness — return proper
   length counter status bits
3. Compare the resulting periods against Mesen to see if this
   fixes the halving bug
4. Study the MusicHeaderData to understand how the driver selects
   different length structures per song
