---
name: rom-emulator
description: Extract NES music by booting the ROM in a headless 6502 emulator with mapper support, NMI simulation, and controller scripting. Bypasses the need for NSF files, music format reverse-engineering, or manual Mesen captures. Use when the NSF is missing/wrong, the music engine is too complex to parse, or you want fully automated extraction from any NES ROM.
---

# ROM EMULATOR — Headless NES Music Extraction

## When to Use This Skill

- The NSF file doesn't exist, is from the wrong platform (FDS vs NES), or produces wrong output
- The music engine uses code-as-music architecture (songs are 6502 subroutines, not data tables)
- The music engine is deeply integrated with game state (area-based, progression-dependent)
- You want fully automated extraction without manual Mesen gameplay
- You've spent more than 30 minutes trying to reverse-engineer the music format

## The Core Principle

Don't parse the music data. Run the game's own code. The CPU writes to APU registers ($4000-$4017) to make sound. Capture those writes. Convert to MIDI. Done.

The game's code is the best parser of its own music format.

## Tool

`scripts/nes_rom_capture.py` — headless NES emulator with:
- py65 6502 CPU
- MMC1 mapper (bank switching)
- NMI simulation at 60Hz
- APU register capture
- Controller input scripting
- Mesen-compatible CSV output

## Step-by-Step Procedure

### Phase 1: Boot and Capture Title Screen

The simplest extraction — boot the ROM and capture whatever plays.

```bash
python scripts/nes_rom_capture.py <rom.nes> \
    -o output/<Game>/rom_capture/ \
    --frames 4800 \
    --game "<Game>" --song "title_screen"
```

**Verify output:** Check the CSV has non-zero period writes. Compare first 10 Sq1 periods against a 10-second Mesen capture to confirm accuracy.

**Period encoding:** The emulator outputs raw register periods converted to Mesen format via `decoded = raw * 2 + 1`. This matches what `mesen_to_midi.py` expects. If periods don't match Mesen, check this conversion.

### Phase 2: Map the Game Mode Table

Find the game's mode dispatch table in the fixed bank (bank 7 for MMC1).

```python
# In the NMI handler (vector at $FFFA/$FFFB):
# Look for: LDA $xx (mode variable), ASL A, TAY, LDA table,Y
# The table maps mode numbers to (bank, handler_address) pairs.
```

**What to look for:**
1. NMI handler in fixed bank — follow the dispatch chain
2. A ZP variable that selects the current game mode
3. A table in the fixed bank that maps modes to banks and handler addresses
4. Which bank number corresponds to which game state (title, gameplay, cutscene)

**Kid Icarus example:** ZP `$A0` = mode variable, table at `$C15C`, 10 modes mapping to banks 1-5 with handler addresses.

### Phase 3: Hot-Swap Technique

For games where music code is copied to RAM during init:

```
1. Boot normally (title screen music initializes)
2. Run 5 NMI frames to stabilize
3. Set $BE = target_bank (or equivalent bank-select variable)
4. Set $7F03 = JMP target_handler (or equivalent NMI dispatch vector)
5. Fire ONE NMI frame (target bank's init copies music code to RAM)
6. Set $BE = original_bank, restore $7F03
7. Fire NMI frames and capture (original bank's NMI ticks the NEW music)
```

**How to detect if a game uses RAM-resident music:**
- Diff RAM between two consecutive frames during music playback
- Addresses that change every frame = music state (duration counters, envelope positions)
- Addresses that DON'T change but contain 6502 opcodes ($20=JSR, $4C=JMP, $60=RTS, $A9=LDA) = music tick code in RAM
- If music code is in the $0300-$07FF range, hot-swap will work

**How to verify the swap worked:**
- Snapshot `$03B0-$03FF` (or wherever the music code lives) before and after the swap frame
- If >20 bytes changed, the new song's code was copied
- If 0 bytes changed, the target bank doesn't use RAM-resident music

### Phase 4: Data-Driven Config System

For games with a separate note-data player (like Kid Icarus bank 4's `$AC88` system):

```python
# 1. Map the config table: find blocks of channel data pointers
# 2. For each config index:
#    a. Set mapper to the music bank
#    b. Call APU init
#    c. Load config: set $0350 (or equivalent) and call the config loader
#    d. Set the music-active flag ($038D or equivalent)
#    e. Call the per-frame player each frame
#    f. Capture APU writes
```

This handles games where pulse channels use a data-driven player while noise/triangle use a separate code-based system.

### Phase 5: Combined Extraction

Some games use TWO music systems simultaneously:
- **Pulse channels**: data-driven player reading from note tables
- **Noise/Triangle**: code-as-music subroutines called per frame

To extract both:
```python
for frame in range(num_frames):
    call(data_player_addr)          # tick the pulse player
    for dispatch in noise_dispatches:
        call(dispatch)              # tick each noise/tri handler
    capture_apu_writes()
```

### Phase 6: Controller Navigation

If game state can't be poked directly, script button presses:

```python
button_script = [
    (120, 0x08, 3),   # Start at frame 120, hold 3 frames
    (300, 0x01, 2),   # A at frame 300, hold 2 frames
]
# Masks: 0x01=A, 0x02=B, 0x04=Select, 0x08=Start
#        0x10=Up, 0x20=Down, 0x40=Left, 0x80=Right
```

## Mapper Support

Currently implemented: **MMC1 (mapper 1)**

Adding a new mapper requires implementing its bank-switching protocol in the `MMC1` class equivalent. Common mappers:

| Mapper | Mechanism | Effort | Games |
|--------|-----------|--------|-------|
| 0 (NROM) | No switching | None — just load 32KB | SMB, DK |
| 1 (MMC1) | 5-bit serial register | Done | Kid Icarus, Zelda, Metroid |
| 2 (UxROM) | Single write to $8000+ = bank number | ~10 lines | CV1, Contra |
| 3 (CNROM) | CHR only, PRG fixed | ~5 lines | Gradius |
| 4 (MMC3) | Register select ($8000) + data ($8001) | ~30 lines | SMB3, Mega Man 3-6 |
| 7 (AxROM) | Single write = bank number | ~10 lines | Battletoads, W&W |

Template for adding UxROM:
```python
class UxROM:
    def __init__(self, prg_data, num_prg_banks):
        self.prg = prg_data
        self.num_prg_banks = num_prg_banks
        self.prg_bank = 0

    def write(self, addr, value):
        if 0x8000 <= addr <= 0xFFFF:
            self.prg_bank = value % self.num_prg_banks

    def get_prg_banks(self):
        return (self.prg_bank, self.num_prg_banks - 1)
```

## Troubleshooting

### No APU writes at all
- **Check the idle loop:** The boot might hit a `JMP $xxxx` where target = current PC. The emulator detects this and stops. Verify the boot ran long enough.
- **Check $2002 stub:** Games spin-wait on PPU status. Our `$2002 = $80` stub handles VBlank, but some games check sprite-0 hit (bit 6) too. Try returning `$C0`.
- **Check bank mapping:** Verify the mapper is in the right mode and the correct bank is at `$8000`.

### Music starts then stops
- **The game logic needs PPU interaction.** The music init ran (first frame had writes) but subsequent frames crashed because game code tried to read PPU state. Solution: hot-swap technique — init in one frame, switch back.
- **Frame counter dependency:** Some games check ZP `$14`/`$15` (frame counter) for timing. Make sure it increments each frame.

### Wrong pitches (octave off)
- **Period encoding:** Raw APU register values vs Mesen decoded values differ by `raw * 2 + 1`. Ensure `frames_to_mesen_csv` applies the conversion.
- **Different period table:** The game might have multiple period tables for different modes/banks. Verify which table is active.

### Same song for all modes
- **Pokes applied too late:** The boot already initialized music before pokes took effect. Solution: use hot-swap (poke during NMI, not after boot).
- **Wrong variable:** The mode variable you're poking might not control music selection. Check the NMI dispatch chain to find the actual music-select variable.

## Architecture Patterns Encountered

### Pattern A: Data-Driven Player (Castlevania, Contra, W&W)
```
Song pointer table → channel data pointers → note stream → driver → APU
```
**Extraction:** Find pointer table, set song number, call init, call play per frame.

### Pattern B: RAM-Resident Code (Kid Icarus banks 1-3)
```
Game init → copy song code to RAM $03xx → NMI ticks RAM code → APU
```
**Extraction:** Hot-swap banks to copy different song code, tick from original bank.

### Pattern C: Code-as-Music (Kid Icarus bank 4 noise/tri)
```
Song = 6502 subroutine → called directly each frame → writes APU
```
**Extraction:** Call dispatch targets directly each frame with correct ZP state.

### Pattern D: Split Architecture (Kid Icarus bank 4)
```
Pulse: config table → data player ($A9AF)
Noise/Tri: dispatch table → code-as-music ($A1B0)
```
**Extraction:** Combine both systems — init configs AND call dispatches.

### Pattern E: Multi-Bank Songs (Kid Icarus)
```
Bank 1 = title screen, Bank 2 = password, Bank 3 = gameplay,
Bank 4 = gameplay (different engine), Bank 5 = cutscene
```
**Extraction:** Map mode table, try each bank via hot-swap.

## Validation

After extraction, ALWAYS verify against a short Mesen trace:

```bash
# Capture 10 seconds in Mesen
# Compare first 10 Sq1 periods:
python -c "
import csv
rom = [...periods from ROM capture CSV...]
trace = [...periods from Mesen CSV...]
match = sum(1 for a,b in zip(rom[:10], trace[:10]) if a == b)
print(f'Match: {match}/10')
"
```

If periods match, the extraction is correct. If they're off by `*2+1`, the period encoding needs the Mesen conversion. If they don't correlate at all, the wrong bank/song is playing.

## Output Pipeline

```
nes_rom_capture.py → Mesen CSV → mesen_to_midi.py → MIDI → generate_project.py → REAPER RPP
```

All tools already exist. The emulator's CSV output is format-compatible with the Mesen trace pipeline.
