# Process Adaptations: How to Extract Music From Any NES ROM

## The Decision Tree

```
START: Have a .nes ROM file
  │
  ├─ Check mapper: python -c "with open('rom.nes','rb') as f: h=f.read(16); print((h[6]>>4)|(h[7]&0xF0))"
  │   ├─ Mapper 0,1,2,3,4,7 → SUPPORTED, continue
  │   └─ Other → Add mapper class (~12-40 lines), then continue
  │
  ├─ Try boot-and-capture:
  │   python scripts/nes_rom_capture.py rom.nes -o output/ --frames 4800 --game Name --song title
  │   │
  │   ├─ Got notes? → DONE. Build RPP.
  │   │
  │   └─ No notes? → Try with Start press:
  │       python scripts/nes_rom_capture.py rom.nes --press-start 60 ...
  │       │
  │       ├─ Got notes? → DONE. 
  │       │
  │       └─ Still no notes? → Need deeper investigation:
  │           │
  │           ├─ Check if NMI enabled after boot (interactive test)
  │           │   ├─ NMI=False → Game needs PPU interaction to enable NMI
  │           │   │   ├─ Find and bypass the PPU wait loop
  │           │   │   └─ OR poke the NMI enable flag directly
  │           │   │
  │           │   └─ NMI=True but no music → Game mode isn't triggering music
  │           │       ├─ Find game mode variable, poke it
  │           │       ├─ Find sound engine, call it directly
  │           │       └─ OR let game run longer (SCUMM-style)
  │           │
  │           └─ For multiple songs:
  │               ├─ Find song pointer table → poke data pointers
  │               ├─ Find game mode table → poke mode variable
  │               ├─ Hot-swap banks → copy RAM-resident song code
  │               └─ Call channel processor directly (SMB3 method)
```

## What We Tried and What Worked

### Pattern 1: Boot and Capture (23 games)

**Games:** Final Fantasy I/II/III, Dragon Warrior I/II, Faxanadu, Mega Man 2-6, Kirby's Adventure, Darkwing Duck, Chip 'n Dale, Strider, Mighty Final Fight, Gargoyle's Quest II, Metroid, Zelda II, Bionic Commando, Double Dragon, Maniac Mansion

**What works:** Run `nes_rom_capture.py` with default settings. Music plays during or shortly after boot.

**Why it works:** These games initialize their sound engine as part of the RESET handler. The title screen music starts automatically. No user input needed.

**Adaptation required:** None. One command, one capture.

### Pattern 2: Start Press Required (7 games)

**Games:** Contra, Batman, Journey to Silius, Shadow of the Ninja, Shatterhand, Little Nemo, Ice Climber

**What works:** Add `--press-start 60` to simulate pressing Start at frame 60.

**Why it works:** These games display a static title screen and wait for Start before beginning the title theme (or transitioning to a screen with music). The sound engine is initialized during boot, but the "play song" command waits for user input.

**How to detect:** If boot-and-capture produces 4800 APU writes but they're all `$4014`/`$4017` (OAM DMA and frame counter), the game is waiting for input.

### Pattern 3: Longer Wait Required (1 game)

**Game:** Maniac Mansion

**What works:** Run for 4800 frames (80 seconds) with NMI-during-boot enabled. Music starts at frame ~1200.

**Why it works:** Maniac Mansion's SCUMM script interpreter needs ~20 seconds to process the intro cutscene before triggering the theme music. The interpreter runs each frame between NMIs, gradually advancing the game script until it reaches the "play music" command.

**Adaptation:** Increase `--frames` to 6000+ and check for music starting late in the capture.

### Pattern 4: Game Mode Poke (1 game)

**Game:** Kid Icarus

**What works:** Poke ZP `$A0` (game mode) to different values after boot. Each mode maps to a different PRG bank with different music.

**How we found it:** Traced the NMI handler's dispatch chain. The handler reads `$A0`, looks up a table in the fixed bank that maps modes to (bank_number, handler_address) pairs, switches to that bank, and jumps to the handler. Different modes play different music.

**Adaptation:** For any game with mode-dependent music, find the NMI dispatch table in the fixed bank. It's usually: `LDA mode_var; ASL A; TAY; LDA table,Y → bank; LDA table+1,Y → handler`.

### Pattern 5: Hot-Swap Banks (1 game)

**Game:** Kid Icarus (banks 1-3)

**What works:** Boot normally (bank 1 title screen plays). Switch `$BE` (bank select) to target bank for ONE NMI frame. Target bank's init copies new song code to RAM at `$03B0`. Switch back to bank 1. Bank 1's NMI ticks the new RAM code.

**How we found it:** Diffed RAM between frames during music playback. Found that `$03B0-$03FF` contains 6502 code (JSR/JMP/LDA opcodes) that doesn't change between frames — it's the music tick routine in RAM. Switching banks copies different code there.

**When to use:** When the game has per-bank music engines that copy their tick code to a fixed RAM area. Detectable by finding executed code in the `$0300-$07FF` RAM range.

### Pattern 6: Direct Channel Processor Call (1 game)

**Game:** Super Mario Bros. 3

**What works:** 
1. Boot normally
2. Map the music data bank (bank 28) to `$A000` slot
3. Read the song config from the pointer table at `$A76C` (indexed via `$A73F`)
4. Poke `$6B/$6C` (ZP data pointer) to the song's data address
5. Poke config values (`$04D0`, `$04FF`, etc.) from the song entry
6. Call `$E528` (the channel processor) directly each frame
7. Capture APU writes

**How we found it:**
1. Searched all banks for `STA $4000-$4013` patterns → found engine in banks 28 (data) and 31 (code)
2. Found `STA $6B`/`STA $6C` in the fixed bank → identified the song data pointer
3. Traced backwards to find the table that loads `$6B/$6C` → song pointer table at `$A76C`
4. Decoded the table: secondary index at `$A73F` maps song numbers to config offsets; each config is 7 bytes with data pointer + channel parameters

**When to use:** When the game's sound engine is in the fixed bank but needs a switchable data bank mapped, and the NMI handler's game mode dispatch is too complex to fake. Bypass the NMI entirely and call the engine directly.

### Pattern 7: Combined Dual Engine (1 game)

**Game:** Kid Icarus (bank 4)

**What works:** Initialize the `$AC88` config system for pulse channels AND call the `$A1B0` dispatch targets for noise/triangle. Tick both systems per frame.

**How we found it:** The `$AC88` config system only wrote to pulse registers (`$4002/$4003`). The `$A1B0` dispatch targets only wrote to noise/triangle (`$400C-$400F`, `$400A/$400B`). Combining both gives all four channels.

**When to use:** When APU writes from one approach only cover some channels. Check which registers are being written and look for a second music system handling the missing channels.

## The Failure Modes (What Doesn't Work Yet)

### PPU-Dependent Boot

**Games affected:** Legend of Zelda, Ninja Gaiden, Castlevania, Dragon Warrior III/IV, most complex RPGs

**Problem:** The game's boot sequence checks PPU state (sprite-0 hit, nametable data, scroll registers) before enabling NMI or starting music. Our PPU stub (`$2002` returns `$C0`, all other PPU reads return 0) isn't sufficient.

**Potential fixes:**
1. Trace the boot to find the specific PPU check and bypass it (poke the flag)
2. Add more PPU stub behavior (return plausible values for `$2007` reads)
3. Use the spin-loop bypass: detect `CMP $xxxx; BEQ self` patterns and force the comparison to fail

### Deeply Integrated Game State

**Games affected:** Dragon Warrior III/IV, some Konami games

**Problem:** The game has multi-stage initialization that requires game logic to progress through multiple states before music starts. Each state change depends on the previous state completing correctly.

**Potential fix:** Find and poke ALL the state variables that the music init checks. This requires tracing the full init path and identifying every conditional branch.

### Unsupported Mappers

**Games affected:** Batman: Return of the Joker (mapper 69/Sunsoft FME-7), Castlevania III JP (mapper 5/MMC5)

**Fix:** Add the mapper class. Each mapper is ~12-40 lines. The template is established.

## The Numbers

| Metric | Count |
|--------|-------|
| Games attempted | ~50 |
| Games with music extracted | 37+ |
| REAPER projects built | 47+ |
| Mapper types supported | 6 |
| Tool size | ~400 lines Python |
| Session duration | 1 day |
| Lines of documentation | ~3000 |
| Manual Mesen captures needed | 0 (for title screens) |

## What Comes Next

1. **Add mappers 5, 9, 69, 85** → unlock another ~100 games
2. **Auto-multi-press**: try Start at frames 30, 60, 120, 240 automatically if first attempt fails
3. **PPU spin-loop bypass**: detect and skip `LDA $2002; BPL/BNE self` patterns during boot
4. **Batch all 700+ NROM/MMC1/UxROM/MMC3/AxROM games** from the D: drive library
5. **Multi-song extraction**: generalize the Kid Icarus/SMB3 techniques into a reusable script
6. **Validation**: compare every ROM-extracted title screen against its NSF equivalent
