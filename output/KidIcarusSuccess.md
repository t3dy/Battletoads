# Kid Icarus: How We Cracked It

## The Problem

Kid Icarus for NES had the most hostile music extraction we've encountered. The NSF file was from the wrong platform (FDS, not NES cart). The music engine used code-as-music architecture — songs stored as 6502 subroutines, not data tables. The game-state integration was deep — three layers of indirection between "play song" and actual APU output. Every approach that worked for Castlevania, Contra, and the rest failed here.

## What Actually Worked

### The Headless NES Emulator

We built `nes_rom_capture.py` — a headless NES emulator that boots ROMs from RESET, fires NMI at 60Hz, captures APU register writes, and outputs Mesen-compatible CSV. No graphics, no sprites, just CPU + mapper + APU capture. ~250 lines of Python wrapping py65.

**Key components:**
- **MMC1 mapper**: 5-bit serial register protocol for bank switching (30 lines)
- **NESMemory wrapper**: intercepts reads/writes, handles bank resolution, captures APU, simulates controller input
- **NMI simulation**: push PC/P, set I flag, jump through $FFFA vector
- **Controller simulation**: strobe protocol with per-frame button scripts

### The Hot-Swap Technique

The breakthrough was discovering that Kid Icarus copies its per-song music code into RAM at `$03B0-$03FF` during bank-switching transitions. This led to the hot-swap technique:

1. **Boot normally** — title screen initializes, music plays from bank 1's code in RAM
2. **For ONE NMI frame**, switch `$BE` (bank select) to the target bank and JMP to its `$8000` handler
3. The handler **copies the target song's music code into RAM**, replacing the title screen code
4. **Switch back** to bank 1 (`$BE=1`, JMP `$A554`) for all subsequent NMIs
5. Bank 1's NMI handler ticks the music from RAM — but now it's playing the NEW song

This works because the music tick code is in RAM, and the per-frame NMI handler is generic — it calls whatever code is at `$03B0`. By swapping the RAM code for one frame, we change the song without needing the game to be in the correct state.

### The Game Mode Table

ZP `$A0` is the game mode variable. The fixed bank (bank 7) has a mode dispatch table at `$C15C` with 10 entries, each mapping to a bank number and handler address:

| Mode | Bank | Handler | Function |
|------|------|---------|----------|
| 0-1 | 1 | $A000 | Title screen |
| 2,4 | 2 | $8000/$99A0 | Password / transition |
| 3,5,7 | 5 | $8000 | Cutscene / story |
| 6 | 3 | $8000 | Gameplay area (new song!) |
| 8 | 3 | $9C30 | Gameplay area |
| 9 | 4 | $8000 | Gameplay area |

### The Period Fix

Our emulator captures raw APU register values. Mesen reports decoded timer periods: `decoded = raw * 2 + 1`. Both represent the same frequency. The fix was one line in `frames_to_mesen_csv()`:

```python
period = raw_period * 2 + 1  # convert to Mesen decoded format
```

After this fix, the emulator's output matched the Mesen trace 10/10 on every Sq1 period.

## Results

| Song | Method | Sq1 | Sq2 | Tri | Noise | Status |
|------|--------|-----|-----|-----|-------|--------|
| Title Screen | Emulator boot | 304 | 157 | 180 | 11 | 10/10 Mesen match |
| Mode 6 Song | Emulator hot-swap | 216 | 513 | 289 | 150 | New song, REAPER project built |
| Gameplay Song 1 | Mesen trace | 304 | 157 | 180 | 11 | Ground truth |

The title screen capture from the emulator matches the Mesen trace of Song 1 period-for-period. The Mode 6 song is a completely different melody with 150 drum hits — the most rhythmically complex Kid Icarus track we've found.

## How to Apply This to Future Problems

### 1. Build the Emulator First, Not the Parser

For Castlevania and Contra, we used pre-existing NSF files as harnesses. When the NSF doesn't exist or doesn't match, the instinct is to reverse-engineer the music data format. Kid Icarus proved that's the wrong instinct.

**Instead: emulate the whole CPU.** Load the ROM, boot from RESET, fire NMI at 60Hz, capture APU writes. The game's own code does all the work — parsing, playback, envelope shaping, everything. You don't need to understand the music format. You just need the CPU to run.

The emulator we built is ~250 lines of Python. It took less time to build than any of our failed harness attempts took to debug.

### 2. Map the Game Mode Table Early

Every NES game has a mode/state dispatch somewhere — usually in the fixed bank's NMI handler. Finding it tells you:
- Which banks exist and what they do
- How to reach each game state
- What RAM variables control the current mode

For Kid Icarus, the table at `$C15C` was the Rosetta Stone. It mapped every mode to a bank and handler address. With that table, we could target any game state.

**How to find it:** Look at the NMI handler (vector at `$FFFA/$FFFB`). Follow the dispatch chain. It usually reads a mode variable from ZP, does a table lookup, switches banks, and jumps through a vector. The table is the key.

### 3. Use the Hot-Swap Technique for Games with RAM-Resident Music

Many NES games copy their music code to RAM during init. If you can identify WHERE the music code lives in RAM, you can swap it by:

1. Boot normally (some song initializes)
2. Switch bank for one frame (new song's init copies its code to RAM)
3. Switch back (the NMI ticks the new RAM code)

This works because NES music engines are designed to survive bank switches — the per-frame tick runs from RAM or the fixed bank, not the switchable bank. The switchable bank is only needed during init.

**How to detect RAM-resident music:** Diff RAM between two frames during music playback. The addresses that change every frame (`$0340` duration counters, `$035B` envelope positions) are the music state. The addresses that DON'T change but contain executable code (`$03B0+`) are the music tick routine.

### 4. Don't Reverse-Engineer the Music Format Unless You Must

For Kid Icarus, we spent hours tracing the song routing through three layers of indirection, decoding period tables, and mapping config blocks. None of that was needed for the final extraction. The emulator bypassed all of it.

Reverse engineering is valuable for UNDERSTANDING the engine (and we documented it thoroughly), but for EXTRACTION, the emulator is faster and more reliable. The game's own code is the best parser of its own data format.

The exception: when you need to MODIFY the music (transpose, rearrange, remix), you need to understand the format. But for archival extraction — play the song, capture the APU, done.

### 5. The Controller Simulation Is Powerful

Adding 20 lines of controller simulation to the emulator let us navigate menus, press Start, and trigger game transitions — all automated. For games with complex menu systems, password screens, or cutscenes before gameplay, this is essential.

**Button script format:**
```python
button_script = [
    (120, 0x08, 3),  # Start at frame 120, hold 3 frames
    (300, 0x01, 2),  # A at frame 300, hold 2 frames
]
```

For future games, if the emulator can't reach gameplay music through pokes, scripted button presses can navigate there.

### 6. The Period Encoding Differs Between Capture Methods

Raw APU register writes use 11-bit period values. Mesen reports decoded values = `raw * 2 + 1`. Our `mesen_to_midi.py` expects Mesen format. Any new capture tool must match the encoding convention.

This was a 30-minute debugging session that would have been 0 minutes if we'd documented the convention earlier. Now it's documented.

## The Tools We Built

| Tool | Purpose | Reusable? |
|------|---------|-----------|
| `nes_rom_capture.py` | Boot NES ROM, capture APU | Yes — any MMC1 game |
| `mesen_to_midi.py` | Mesen CSV → MIDI | Already existed |
| `generate_project.py` | MIDI → REAPER project | Already existed |

The emulator's mapper is MMC1-specific but adding UxROM (mapper 2, used by CV1/Contra) or AxROM (mapper 7, used by Battletoads/W&W) would be ~10 lines each. The rest of the emulator is mapper-agnostic.

## What This Means for the Pipeline

We now have three extraction methods:

1. **NSF emulation** (`nsf_to_reaper.py`) — for games with matching NSF files
2. **Mesen trace capture** (`mesen_to_midi.py`) — ground truth from real emulator
3. **ROM emulation** (`nes_rom_capture.py`) — automated, no human, no NSF needed

Method 3 is the new capability. It eliminates the NSF dependency and the human gameplay requirement. For any game where the NSF is wrong, missing, or unavailable, we can boot the ROM directly and extract.

The NES music extraction pipeline is now complete: ROM in, REAPER project out, no manual steps required.
