---
name: skeleton-key
description: Systematic methodology for identifying and decoding ANY NES ROM music engine. Catalogs all known encoding schemes across 130+ drivers, provides a decision tree for classification, and generates a parser skeleton. Use when encountering an unknown game ROM.
---

# SKELETON KEY — Universal NES Music Driver Decoder

Every NES game encodes music differently, but they all must ultimately
write to the same 22 APU registers ($4000-$4013, $4015, $4017). This
constraint means there are a FINITE number of structural patterns for
how music data flows from ROM bytes to sound. This skill catalogs those
patterns and provides a systematic method to identify which ones a
given ROM uses.

## The Fundamental Question

To decode ANY NES ROM's music, you must answer 7 questions:

```
1. PITCH:     How does a byte become a note frequency?
2. DURATION:  How does the driver know when to stop a note?
3. ENVELOPE:  How does volume/timbre change within a note?
4. COMMANDS:  How does the driver distinguish notes from control?
5. STRUCTURE: How are songs, channels, and sections organized?
6. MEMORY:    Where does the data live (linear, banked, expanded)?
7. PLAYBACK:  How does the NMI-driven play routine process data?
```

## Part 1: The Encoding Taxonomy

### 1.1 Pitch Encoding (6 known schemes)

| Scheme | How It Works | Who Uses It | Identification |
|--------|-------------|-------------|----------------|
| **A: Nibble-packed** | High nibble of note byte = pitch (0-B = C-B) | Konami pre-VRC (CV1, Contra, Gradius) | Note bytes cluster in $00-$BF range; pattern repeats every $10 |
| **B: Byte index** | Entire byte (minus base) indexes into period table | Rare (Battletoads), many others | Notes span wide range; subtract constant gives 0-71 |
| **C: Direct period** | Raw 11-bit period value stored in data stream | Some early/simple drivers | Two consecutive bytes write directly to $4002/$4003 |
| **D: Octave + semitone** | Separate octave state + semitone index | Capcom (Mega Man), some Sunsoft | Octave-set commands followed by 12-value note range |
| **E: Tracker row** | Fixed-width row: note, instrument, volume, effect | FamiTracker exports, homebrew | Uniform row size, order table + pattern table structure |
| **F: MML-compiled** | MML text compiled to bytecode indices | PPMCK, NSD.Lib, some commercial | Regular spacing, MML-like command structure |

**Universal constant:** All schemes ultimately produce an 11-bit period
value for pulse/triangle. The period table is the Rosetta Stone — find
it first.

**Period table signatures (NTSC):**
```
C-2: $06AE (1710)    C-3: $0356 (854)    C-4: $01AB (427)
C-5: $00D5 (213)     C-6: $006A (106)    C-7: $0035 (53)
Adjacent ratio: ~1.05946 (12th root of 2)
Table size: 12 entries (1 octave) to 96 entries (8 octaves)
Byte order: Little-endian 16-bit words, descending values
```

### 1.2 Duration Encoding (5 known schemes)

| Scheme | How It Works | Who Uses It | Identification |
|--------|-------------|-------------|----------------|
| **A: Nibble-packed** | Low nibble of note byte = duration index, frames = tempo * (n+1) | Konami pre-VRC | Note bytes have predictable low nibbles; DX command sets tempo |
| **B: Inline byte** | Separate byte after note = duration | Rare (in inline mode), some Capcom | Notes always followed by a byte in limited range |
| **C: Persistent state** | Command sets duration, applies to all subsequent notes | Rare (CMD 0x06), many Japanese drivers | Duration-set command appears before runs of notes |
| **D: Lookup table** | Duration byte indexes into frame-count table | Some Sunsoft, Hudson | Small table of timing values found near period table |
| **E: Fixed-width row** | Duration encoded in tracker row (speed * row count) | FamiTracker | Uniform row spacing; speed command controls tempo |

**Key insight:** Schemes B and C often coexist in the same driver
(Rare uses both). The driver maintains a state flag for which mode
is active.

### 1.3 Envelope Encoding (5 known schemes)

| Scheme | How It Works | Who Uses It | Identification |
|--------|-------------|-------------|----------------|
| **A: Parametric** | 2-3 bytes define initial vol + fade_start + fade_step | Konami CV1 | DX command followed by 2 bytes; no envelope tables in ROM |
| **B: Lookup table** | Byte indexes into ROM table of per-frame volume sequences | Konami Contra (54 tables), Capcom | Tables of ascending byte sequences terminated by sentinel |
| **C: APU register direct** | Single byte written to $4000 (DDLCVVVV packed) | Many simple drivers | Instrument = one byte matching APU register format |
| **D: Macro sequence** | Instrument = list of (vol, duty, pitch-offset) per frame | FamiTracker, advanced drivers | Instrument definitions contain variable-length sequences |
| **E: Hardware envelope** | Length counter + decay (C=0 in $4000) | Early Nintendo (SMB), some others | Constant-volume flag clear; hardware handles decay |

**Warning:** Scheme A (parametric) and Scheme B (lookup) can look
similar in ROM — both follow a DX-like command. Distinguish by checking
whether the bytes after DX are a table index or inline parameters.

### 1.4 Command Dispatch (4 known architectures)

| Architecture | How Note vs Command Is Determined | Who Uses It |
|-------------|----------------------------------|-------------|
| **A: Range partition** | Byte ranges map to categories: $00-$BF=notes, $C0-$CF=rest, $D0-$DF=tempo, $E0-$EF=control, $F0-$FF=flow | Konami pre-VRC |
| **B: Bit-flag** | Bit 7 set = note/rest, bit 7 clear = command | Rare, some others |
| **C: Opcode table** | All values dispatched through jump table (ASL+TAX) | Some Capcom, advanced drivers |
| **D: Fixed-width** | No dispatch — every row is same width, columns have fixed meaning | FamiTracker, tracker-style |

**Critical for B and C:** You MUST get parameter counts right. One
wrong parameter count desynchronizes the entire data stream. Count
INY instructions in each handler. Watch for branch-always tricks
and shared handler tails.

### 1.5 Song Structure (4 known patterns)

| Pattern | Organization | Who Uses It |
|---------|-------------|-------------|
| **A: Pointer table** | Table of addresses → per-channel data streams | Konami, Rare, most commercial |
| **B: Order + Pattern** | Order table lists pattern indices; patterns contain rows | FamiTracker, tracker-style |
| **C: Hierarchical** | Songs → sections → phrases → notes (multi-level pointers) | Some Capcom, Sunsoft |
| **D: Inline linear** | Single stream per song, all channels interleaved | Some early/simple games |

**Subroutine support varies:**
- Konami: FD=call, FE=repeat, FF=end/return
- Rare: Commands 0x0C (call) and 0x0D (return)
- Some drivers have no subroutine support at all

### 1.6 Memory Architecture (4 configurations)

| Config | Details | Implications |
|--------|---------|-------------|
| **Linear (mapper 0)** | 32KB PRG, all addresses direct | Simple: ROM offset = CPU address - $8000 |
| **Banked (mapper 1/2/4)** | 128-512KB, bank-switched windows | Must identify which bank holds music data; pointer addresses are bank-relative |
| **Expansion audio** | VRC6, VRC7, Sunsoft 5B, N163, MMC5 | Extra channels with own registers; data stream includes expansion commands |
| **FDS** | Famicom Disk System wavetable channel | Extra channel with 64-sample wavetable |

**Bank switching is the #1 cause of wrong addresses.** A pointer table
at CPU $88E8 might be at ROM offset $48F8 (bank 1 of mapper 2). Always
resolve bank context before reading pointer values.

### 1.7 Playback Architecture (2 core patterns)

| Pattern | How It Works | Implications |
|---------|-------------|-------------|
| **NMI-driven** | VBlank interrupt calls play routine once per frame (~60Hz NTSC) | Most games. Each call processes one frame of all channels. |
| **Timer-driven** | IRQ timer calls play at variable rate | Rare. Some FDS games, VRC6/VRC7 games. |

Both patterns ultimately write to APU registers. The play routine is
the most important code to find — trace backward from APU register
writes to locate the data it reads.

---

## Part 2: The Decision Tree

### Step 0: Gather Evidence

Before any analysis:

```
[ ] Read iNES header → mapper, PRG size, battery, region
[ ] Check extraction/manifests/ for existing manifest
[ ] Check references/ for existing disassembly
[ ] Check if NSF exists (can run rom_identify.py)
[ ] Search for fan MIDI of target song
[ ] Run: PYTHONPATH=. python scripts/rom_identify.py <rom>
```

### Step 1: Find the Period Table

This is ALWAYS step 1. No exceptions.

**Method:** Scan PRG ROM for sequences of descending 16-bit LE values
where adjacent ratios approximate 2^(1/12).

```python
# Pseudocode for period table finder
for offset in range(0, prg_size - 24, 2):
    values = [read_16le(prg, offset + i*2) for i in range(12)]
    if all(v > 50 for v in values) and all(v < 4000 for v in values):
        ratios = [values[i] / values[i+1] for i in range(11)]
        if all(1.03 < r < 1.08 for r in ratios):
            print(f"Period table candidate at ROM ${offset:04X}")
```

**Expected results:**
- 1-3 candidates (one per octave range or one full table)
- Values should include recognizable NTSC reference pitches
- Table address tells you which ROM bank holds music data

**If no period table found:**
- Game may use direct period values (scheme 1.1.C)
- Game may use expansion audio with different tuning
- PRG may be encrypted or compressed (very rare on NES)

### Step 2: Find the Play Routine

**Method A (with NSF):** The NSF header gives you the PLAY address directly.
Set a breakpoint in Mesen, trace execution.

**Method B (with Mesen, no NSF):** Set write breakpoints on $4000-$4003.
The code that writes to APU registers IS the play routine (or called by it).
Trace backward to find the data source.

**Method C (static, no emulator):** Search for STA $4000/STA $4002/STA $4003
instruction sequences. The surrounding code is the play routine.

### Step 3: Classify Command Dispatch

From the play routine, identify how it reads and dispatches bytes:

```
Does it check bit 7?
  YES → Architecture B (bit-flag). bit7=note, bit6-0=command
  NO  →
    Does it use a jump table (ASL A + TAX + LDA table,X)?
      YES → Architecture C (opcode table). Read the table.
      NO  →
        Does it use CMP/BCC/BCS to partition byte ranges?
          YES → Architecture A (range partition). Map the ranges.
          NO  → Architecture D (fixed-width) or unknown.
```

### Step 4: Decode Note Encoding

**With period table + play routine identified:**

1. Set breakpoint where period value is written to $4002/$4003
2. Trace back: where did the period value come from?
   - Loaded from table[index]? → Index = note pitch
   - Where did the index come from? → That's your pitch encoding
3. Is pitch nibble-packed (high nibble of data byte)?
4. Is pitch a full byte minus a base constant?
5. Is there a separate octave state (shift applied to base period)?

**Triangulate with fan MIDI:** If you know the melody starts E2-E2-D2-G2,
search for the corresponding index sequence in the ROM data stream.

### Step 5: Decode Duration Encoding

1. In the play routine, find the frame counter decrement
2. Where is the counter loaded from when a new note starts?
   - From low nibble of note byte? → Scheme A (nibble-packed)
   - From next byte in data stream? → Scheme B (inline)
   - From a persistent variable? → Scheme C (persistent state)
   - From a table lookup? → Scheme D (table)

### Step 6: Decode Envelope Model

1. Find where $4000 (volume/duty) is written during note sustain
2. Is volume coming from:
   - A decrementing counter with configurable start/step? → Scheme A (parametric)
   - A table read that advances each frame? → Scheme B (lookup)
   - The original instrument byte unchanged? → Scheme C (direct)
   - A multi-field macro? → Scheme D (macro sequence)
   - Hardware decay (constant-volume bit = 0)? → Scheme E (hardware)

### Step 7: Map Song Structure

1. Find where the data pointer is initialized (the INIT routine in NSF)
2. Song number → pointer table → per-channel start addresses
3. How many channels per song? (Usually 4: Sq1, Sq2, Tri, Noise; sometimes 5+ with expansion)
4. Do channels share data via subroutine calls?
5. Is there a loop point (jump back to earlier address)?

---

## Part 3: Known Driver Signatures

Quick identification patterns for major commercial drivers:

### Konami Pre-VRC (Maezawa)
```
Signature: DX + 2-3 bytes, E0-E4 octave commands, E8/E9/EA specials,
           FD/FE/FF flow control
Period table: 12 entries (single octave), octave via shift
Games: CV1, Contra, Super C, TMNT, Gradius, Goonies II
Variants: CV1 (2 DX bytes pulse), Contra (3 DX bytes pulse)
WARNING: Same period table ≠ same variant. Check DX byte count.
```

### Konami VRC6
```
Signature: Extra registers at $9000-$B002 for 2 pulse + 1 sawtooth
Period table: May have extended entries for expansion channels
Games: CV3 (JP), Madara, Esper Dream 2
```

### Rare
```
Signature: Bit-7 dispatch, 39 commands via ASL+TAX table,
           dual duration mode (inline + persistent)
Period table: Multi-octave (48-72 entries)
Games: Battletoads, Wizards & Warriors, RC Pro-Am
NOTE: Hidden state flags control parameter consumption per note
```

### Capcom (Sakaguchi)
```
Signature: Multi-speed tempo, complex envelope tables,
           separate octave + semitone commands
Period table: Full range, possibly multiple tables for different speeds
Games: Mega Man 1-6, DuckTales, Chip 'n Dale
Versions: At least 3 known variants
```

### Nintendo (Kondo)
```
Signature: Title-specific, varies enormously
Games: Super Mario Bros, Zelda, Metroid
WARNING: Nintendo used different drivers per title/composer.
         SMB driver ≠ Zelda driver ≠ Metroid driver.
```

### Sunsoft
```
Signature: Aggressive DPCM usage, complex duty cycling,
           pitched bass via DPCM channel
Period table: Standard NTSC
Games: Batman, Blaster Master, Journey to Silius
```

### FamiTracker Export
```
Signature: Order table at known offset, pattern table,
           instrument macro definitions, uniform row width
Games: Homebrew, modern NES releases
Identification: Often has "FamiTracker" or version string in ROM
```

---

## Part 4: The Skeleton Parser Template

Once you've classified a driver along all 7 dimensions, generate
a parser skeleton:

```python
"""
Parser for <GAME> (<DRIVER_FAMILY>)
Generated by SKELETONKEY analysis.

Encoding Profile:
  Pitch:     Scheme <X> — <description>
  Duration:  Scheme <X> — <description>
  Envelope:  Scheme <X> — <description>
  Dispatch:  Architecture <X> — <description>
  Structure: Pattern <X> — <description>
  Memory:    <mapper type> — <bank details>
  Playback:  <NMI/timer>-driven

STATUS: SKELETON — not yet validated
"""

from extraction.core.frame_state import FrameState
from extraction.core.frame_ir import FrameIR

class GameParser:
    """Parse <GAME> ROM music data."""

    # ROM layout (from manifest)
    PERIOD_TABLE_ADDR = 0x____
    SONG_POINTER_ADDR = 0x____
    MUSIC_BANK = ____  # None for mapper 0

    # Period table (extracted from ROM)
    PERIOD_TABLE = []  # Fill from ROM scan

    # Command classification
    # (fill based on dispatch architecture)

    def __init__(self, rom_data: bytes):
        self.rom = rom_data
        self.period_table = self._read_period_table()

    def _read_period_table(self) -> list:
        """Read period table from ROM."""
        addr = self.PERIOD_TABLE_ADDR
        entries = []
        for i in range(12):  # Adjust count per driver
            lo = self.rom[addr + i*2]
            hi = self.rom[addr + i*2 + 1]
            entries.append(lo | (hi << 8))
        return entries

    def _resolve_bank_address(self, cpu_addr: int) -> int:
        """Convert CPU address to ROM offset."""
        # Mapper 0: direct
        # Mapper 2: bank * 0x4000 + (cpu_addr - 0x8000)
        # Adjust per mapper type
        raise NotImplementedError("Fill per mapper")

    def parse_song(self, song_index: int) -> list:
        """Parse all channels for a song. Returns list of FrameState."""
        pointers = self._read_song_pointers(song_index)
        channels = []
        for ch, ptr in enumerate(pointers):
            events = self._parse_channel(ptr, ch)
            channels.append(events)
        return channels

    def _read_song_pointers(self, song_index: int) -> list:
        """Read per-channel data pointers for song."""
        raise NotImplementedError("Fill per structure pattern")

    def _parse_channel(self, start_addr: int, channel: int) -> list:
        """Parse a single channel's data stream."""
        addr = start_addr
        events = []

        while True:
            byte = self.rom[addr]
            addr += 1

            if self._is_end(byte):
                break
            elif self._is_note(byte):
                pitch, duration = self._decode_note(byte, addr)
                addr += self._note_extra_bytes(byte)
                events.append({
                    'type': 'note',
                    'pitch_index': pitch,
                    'duration_frames': duration,
                    'period': self.period_table[pitch % len(self.period_table)],
                })
            elif self._is_rest(byte):
                duration = self._decode_rest_duration(byte)
                events.append({
                    'type': 'rest',
                    'duration_frames': duration,
                })
            elif self._is_command(byte):
                cmd, params, addr = self._decode_command(byte, addr)
                events.append({
                    'type': 'command',
                    'opcode': cmd,
                    'params': params,
                })

        return events

    # --- Fill these per driver classification ---

    def _is_note(self, byte: int) -> bool:
        raise NotImplementedError

    def _is_rest(self, byte: int) -> bool:
        raise NotImplementedError

    def _is_command(self, byte: int) -> bool:
        raise NotImplementedError

    def _is_end(self, byte: int) -> bool:
        raise NotImplementedError

    def _decode_note(self, byte: int, addr: int) -> tuple:
        """Returns (pitch_index, duration_frames)."""
        raise NotImplementedError

    def _note_extra_bytes(self, byte: int) -> int:
        """How many additional bytes does this note consume?"""
        raise NotImplementedError

    def _decode_rest_duration(self, byte: int) -> int:
        raise NotImplementedError

    def _decode_command(self, byte: int, addr: int) -> tuple:
        """Returns (command_id, params_list, new_addr)."""
        raise NotImplementedError
```

---

## Part 5: Validation Protocol

After generating a parser skeleton and filling in the specifics:

> **CRITICAL PRINCIPLE: Zero parse errors is NOT musical correctness.**
> Parser alignment proves byte-stream structure only. Parser output is a
> hypothesis until execution semantics validation passes. Do not skip
> from Gate 2 to Gate 6 — Gate 4 (execution semantics) is mandatory.

### Gate 1: Period Table Verification
- Extract period table from ROM at identified address
- Compare values against NTSC standard reference
- Confirm values match what Mesen trace shows in $4002/$4003

### Gate 2: Single-Channel Parse (STRUCTURAL milestone)
- Parse ONE channel of ONE song
- Count total notes + rests + commands
- Check: does the stream terminate cleanly (no runaway)?
- Check: are all note pitch indices within period table range?
- **Label this "parser-aligned" — it is structural, not semantic**

### Gate 3: Pitch Triangulation (initial cross-check)
- Compare parsed pitches against fan MIDI (if available)
- Compare parsed periods against Mesen trace (if available)
- First 10 notes must match. If not, re-examine encoding.
- **Note: this checks base notes only, not sounding notes after modulation**

### Gate 4: Execution Semantics Validation (MANDATORY)

Use SIMULATORBUILDER skill. See `session_protocol.md` Gate 2 for full
criteria and checklist. Parser output is hypothesis until this passes.

### Gate 5: Envelope Verification
- Compare volume contour against Mesen trace $4000 writes
- Duty cycle changes should match trace $4000 upper bits

### Gate 6: Full Song Parse + Frame IR
- Parse all channels
- Run through Frame IR pipeline (consumes semantics-validated events)
- Generate MIDI
- Listen and compare to game

### Gate 7: Multi-Song Validation
- Parse 3+ songs from same game
- All should complete without stream desync
- Total track counts should match known song list
- **Label final output "trusted" / "production-ready" only after ear-check**

---

See `.claude/rules/architecture.md` and `session_protocol.md` for anti-patterns
and validation gates. See `docs/MISTAKEBAKED.md` for the full mistake catalog.

---

## Quick Reference: Running This Skill

```bash
# Step 0: Identify the ROM
PYTHONPATH=. python scripts/rom_identify.py <rom_file>

# Step 1: Find period table (rom_identify.py does this)
# Step 2: Check for existing disassembly
ls references/<game>*

# Step 3: Check for existing manifest
ls extraction/manifests/<game>*.json

# Step 4: If Mesen trace available, capture it
# Step 5: Classify along 7 dimensions (use decision tree above)
# Step 6: Create manifest with classifications
# Step 7: Generate parser skeleton
# Step 8: Fill in specifics, validate through gates 1-7
# Step 9: Run through Frame IR → MIDI pipeline
# Step 10: Listen and iterate
```

## When To Use This Skill vs ROMPARSER

- **SKELETONKEY**: Unknown game, unknown driver. Need to CLASSIFY first.
- **ROMPARSER**: Driver family identified. Need to TRIANGULATE specific parameters.

SKELETONKEY answers "what kind of engine is this?"
ROMPARSER answers "what are the exact byte formats?"
