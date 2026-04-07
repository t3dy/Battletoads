# NES Music Encoding Taxonomy

A catalog of every music encoding architecture we've encountered across 9+ games, organized by how notes get from ROM to speaker.

## The Universal Constraint

Every NES game must ultimately write to the same 22 APU registers ($4000-$4017) to produce sound. The CPU has no DSP, no MIDI interface, no audio RAM. It writes raw timer periods, volume levels, and duty cycles to memory-mapped hardware registers, 60 times per second.

Everything in this taxonomy is about the path between "bytes in ROM" and "writes to $4000-$4017."

## Architecture Taxonomy

### Type 1: Data-Driven Player

```
ROM data (note tables) → Generic driver code → APU registers
```

The most common architecture. A generic driver reads note data from a pointer, decodes it according to a fixed format, and writes the resulting period/volume/duty values to APU registers. Different songs are different data pointers fed to the same driver.

**How to extract:** Find the song pointer table, set the pointer, call the driver's per-frame tick.

#### Subtype 1A: Flat Stream

Notes are stored as a sequential byte stream. The driver reads one byte at a time, decodes it as a note or command, advances the pointer, and repeats next frame.

| Game | Driver | Note Format | Duration | Commands |
|------|--------|------------|----------|----------|
| **Castlevania** | Konami Maezawa | High nibble = pitch, low nibble = duration index | `tempo * (nibble + 1)` frames | DX (config), E8 (envelope gate) |
| **Contra** | Konami Maezawa variant | Same nibble-packed format | Same formula | DX (3 bytes vs CV1's 2), EC (pitch adjust) |
| **Wizards & Warriors** | Rare custom | Bit 7 = table-note vs direct-period | Persistent via command | 10 commands (0x00-0x0A) |

**Characteristics:** Variable-width instructions. The driver has a command dispatch table. Notes and commands share the byte space, distinguished by value range.

#### Subtype 1B: Config-Table System

Songs are selected by an index into a config table. Each config entry contains data pointers for all channels, plus envelope IDs, transpose values, and tempo settings.

| Game | Table Address | Entry Size | Channels | Notes |
|------|-------------|-----------|----------|-------|
| **Kid Icarus (bank 4)** | $AC88 via $ABAB | 13 bytes | 4 (Sq1, Sq2, Tri, Noise) | $0350 selects config, $A9AF plays |
| **SMB3** | $A76C + secondary index at $A73F | 7 bytes | Per-channel-group | Two tables for two channel groups |

**Characteristics:** Self-contained configs. Setting the config index and calling the loader initializes all channels. The per-frame tick is generic.

#### Subtype 1C: Phrase Library

Songs are built from short reusable patterns chained together, similar to a tracker module.

| Game | Phrase Count | Chain Method | Notes |
|------|-------------|-------------|-------|
| **Castlevania II** | 30 phrases | FF (end), FE (repeat), F0-F7 (chain next) | Combined note byte: bit7 flag + duration class + period index |

**Characteristics:** Compact storage (phrases reused across songs). More complex parser needed. Period write jitter from split hi/lo writes across frames.

### Type 2: Code-as-Music

```
Song = 6502 subroutine → APU registers directly
```

Each song is a state machine encoded as 6502 assembly. The subroutine is called once per frame. It uses branch instructions for song structure, counter decrements for timing, and direct STA to APU registers for note output.

| Game | Location | How It Works |
|------|----------|-------------|
| **Kid Icarus (banks 1-3)** | RAM $03B0-$03FF | Song code copied to RAM during bank switch. NMI ticks RAM code. Different songs = different code blocks. |
| **Kid Icarus (bank 4 noise/tri)** | $A4xx-$A8xx dispatch targets | Each channel has its own subroutine called per frame |

**Characteristics:** No data tables to parse. Notes are hardcoded as `LDA #period; STA $4002` sequences. Duration is controlled by `DEC counter; BNE skip_next_note`. Song structure is JMP/BNE/BEQ control flow.

**How to extract:** Call the subroutine each frame and capture APU writes. Don't try to parse the "data" — there is no data, only code.

**Identification:** CDL analysis shows the "data" region as executed code. Disassembly reveals STA $40xx patterns with branch-based control flow instead of data-pointer-based sequential reads.

### Type 3: Split Architecture

```
Pulse channels: Data-driven player
Noise/Triangle: Code-as-music subroutines
```

Two independent music systems running simultaneously, each handling different channels.

| Game | Pulse System | Noise/Tri System |
|------|-------------|-----------------|
| **Kid Icarus (bank 4)** | $AC88 config table → $A9AF per-frame player | $A1B0 dispatch table → per-frame subroutine calls |

**How to extract:** Initialize BOTH systems, call BOTH per-frame ticks each frame.

### Type 4: RAM-Resident Music

```
Init: copy song code to RAM
Play: NMI ticks RAM code (bank-independent)
```

The music tick routine lives in RAM, not in a ROM bank. During song init, the game copies a song-specific code block from the current ROM bank into a fixed RAM area. The NMI handler calls the RAM code regardless of which bank is currently mapped.

| Game | RAM Area | Init Mechanism | Swap Method |
|------|----------|---------------|-------------|
| **Kid Icarus (banks 1-3)** | $03B0-$03FF (80 bytes) | Bank init copies code to RAM | Hot-swap: switch bank for one NMI, switch back |

**How to extract:** Boot normally (title screen installs one song in RAM). Switch to target bank for one frame (its init copies new code). Switch back to original bank for playback.

**Identification:** Diff RAM between frames during music playback. The tick code region (e.g., $03B0) doesn't change frame-to-frame but contains 6502 opcodes. The state region ($0340 etc.) changes every frame.

### Type 5: Script-Loaded Music

```
Game script interpreter → loads song resource to RAM → sound engine reads RAM
```

The music data is embedded in the game's script resource system. A virtual machine (script interpreter) runs each frame, processing game logic. Music starts when the script executes a "play song" command, which loads compressed sound data from ROM into a RAM work area.

| Game | Script Engine | Sound Engine | Notes |
|------|-------------|-------------|-------|
| **Maniac Mansion** | SCUMM (NES port) | Bank 0 ($8C07 tick) | Sound data loaded by SCUMM resource manager |

**How to extract:** Let the script interpreter run. After enough frames (~1200 for Maniac Mansion), the interpreter processes the intro script and starts music. No ROM hacking needed — just patience.

**Identification:** The sound engine's data pointers are in RAM (not pointing to ROM). The song data changes when the script interpreter runs. The NMI handler calls a script VM, not the sound engine directly.

### Type 6: Immediate-Play

```
Boot → RESET handler → sound init → music plays
```

The simplest case. The game's RESET handler initializes the APU and starts playing music as part of the boot sequence. No user input, no game state transitions, no script interpreters.

| Game | Boot-to-Music | Notes |
|------|--------------|-------|
| **Final Fantasy I/II/III** | 3-6 frames | Prelude arpeggio starts immediately |
| **Faxanadu** | 1 frame | Music from first NMI |
| **Dragon Warrior I/II** | 6-25 seconds | Scrolling intro then title music |

**How to extract:** `nes_rom_capture.py <rom> --frames 4800`. Done.

## Note Encoding Schemes

How individual notes are represented in the data stream (for Type 1 architectures):

### Scheme A: Nibble-Packed (Konami)

```
Byte: [PPPP DDDD]
  P = pitch index (0-11 = C-B within current octave)
  D = duration index (frames = tempo * (D + 1))
```

One byte = one note. Compact. Octave set by separate command (DX). Used by Castlevania, Contra, Gradius.

### Scheme B: Byte Index + Persistent Duration (Rare)

```
Note byte: full period table index (>= $81)
Duration: set by command, persists until changed
Rest: $80
Commands: $00-$7F
```

Notes and commands separated by value range. Duration is modal (set once, applies to all subsequent notes). Used by Battletoads.

### Scheme C: Combined Flag Byte (CV2)

```
Byte: [F DD PPPPP]
  F = flag bit
  DD = duration class (2 bits)
  PPPPP = period table index (5 bits, 32 notes)
```

Very compact — pitch + duration in one byte with a flag. Used by Castlevania II's phrase library system.

### Scheme D: Table Lookup + Inline Parameters (SMB3)

```
Song data read via ($6B),Y
First byte decoded through command dispatch
Subsequent bytes are parameters
```

Variable-width instructions. The first byte determines whether it's a note, rest, or command, and how many parameter bytes follow. Complex but flexible. Used by SMB3's sound engine.

### Scheme E: Direct APU Values (Code-as-Music)

```
LDA #$69    ; period lo = $69 (105 decimal)
STA $4002   ; write to Sq1 period lo
LDA #$00
STA $4003   ; write to Sq1 period hi
```

No encoding. The note IS the machine code. Period values are hardcoded as immediate operands. Duration is controlled by counter decrements and branch instructions. Used by Kid Icarus banks 1-3.

## Period Table Formats

How the frequency lookup table is stored:

| Format | Games | Layout | Size |
|--------|-------|--------|------|
| **Split lo/hi arrays** | Castlevania, Contra | Two separate byte arrays: periods_lo[N], periods_hi[N] | 2 × N bytes |
| **Interleaved hi/lo pairs** | Kid Icarus | Alternating: hi0, lo0, hi1, lo1, ... | 2 × N bytes |
| **Contiguous 16-bit LE** | Battletoads | Sequential little-endian words | 2 × N bytes |
| **Big-endian pairs** | Wizards & Warriors (one table) | hi, lo per entry | 2 × N bytes |
| **Combined with driver code** | Kid Icarus $AAFA | Table overlaps with surrounding code, indexed by large Y values | Variable |
| **Standard NTSC values** | All games | C2=1710, C3=854, C4=427, C5=213, C6=106 (±1) | 12-96 entries |

Every game uses the same underlying NTSC frequencies (derived from the 1.789773 MHz CPU clock). The tables differ only in storage format and range (how many octaves).

## Envelope Systems

How volume changes within a note:

| System | Games | How It Works |
|--------|-------|-------------|
| **Parametric 2-phase** | Castlevania | Two parameters (fade_start, fade_step) define attack-sustain-release |
| **Lookup table** | Contra | 54 pre-built per-frame volume sequences, $FF terminates and triggers decrescendo |
| **Software register** | Battletoads | Per-channel volume variable ($0352,X), modified by ramp/oscillate commands |
| **Hardware envelope** | Some simple games | NES APU's built-in decay envelope (set-and-forget via $4000 bits 0-5) |
| **CC11 per-frame** | NSF extraction | Volume captured as MIDI CC11 at 60Hz — the ground truth of what the hardware outputs |
| **RAM code** | Kid Icarus | Envelope shape is 6502 code that modifies APU registers per frame |

## Duration Systems

How note timing works:

| System | Games | How It Works |
|--------|-------|-------------|
| **Nibble + tempo** | Konami (CV1, Contra) | Duration = tempo_register * (low_nibble + 1) frames |
| **Persistent command** | Rare (Battletoads) | Duration set by command, applies until changed |
| **Frame counter** | Kid Icarus $AC88 | Counter loaded from lookup table, decremented each frame |
| **Inline byte** | Some Capcom | Separate byte after note = duration |
| **Branch timing** | Code-as-music | `DEC counter; BNE same_note` — duration IS control flow |

## What This Means for Extraction

The encoding scheme determines the extraction approach:

| If you find... | It's probably... | Extraction method |
|---------------|-----------------|-------------------|
| Descending 16-bit values in ROM | Period table (Type 1) | Parse the data stream, follow pointers |
| `STA $4002,Y` in a loop | Channel output routine | Find who calls it, trace back to song selection |
| Song data pointer in ZP | Data-driven player | Poke the pointer, call the tick |
| 6502 code writing to $40xx | Code-as-music (Type 2) | Call the subroutine each frame |
| RAM code that changes between songs | RAM-resident music (Type 4) | Hot-swap banks to load different songs |
| Data pointers in RAM (not ROM) | Script-loaded (Type 5) | Let the script interpreter run |
| Music on boot | Immediate-play (Type 6) | Just boot the ROM |

Or skip all of that: **boot the ROM in the headless emulator and capture whatever plays.**
