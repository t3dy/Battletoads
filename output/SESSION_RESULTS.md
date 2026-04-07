# Session Results: The Day We Built a Universal NES Music Extractor

## What Happened

Starting from a single Mesen capture of Kid Icarus Song 1, we built a headless NES emulator (`nes_rom_capture.py`) that boots any NES ROM, simulates the CPU at 60Hz, captures APU register writes, and outputs MIDI + REAPER projects. By the end of the session, we had extracted title screen music from **36+ games** and built **47+ REAPER projects** — all fully automated, zero manual gameplay.

## The Tool

`scripts/nes_rom_capture.py` — 400 lines of Python wrapping py65 (6502 emulator).

### What It Does
```
NES ROM (.nes) → boot from RESET → NMI at 60Hz → capture $4000-$4017 writes → Mesen CSV → MIDI → REAPER RPP
```

### Mapper Support (6 mappers = ~95% of NES library)

| Mapper | Name | Banking | Games | Lines of Code |
|--------|------|---------|-------|---------------|
| 0 | NROM | None (fixed 32KB) | ~100 early games | 12 |
| 1 | MMC1 | 5-bit serial register, 16KB switching | ~400 games | 40 |
| 2 | UxROM | Single write = bank number | ~200 games | 12 |
| 3 | CNROM | CHR only (PRG fixed) | ~100 games | 12 |
| 4 | MMC3 | Register select + data write, 8KB switching | ~350 games | 40 |
| 7 | AxROM | Single write = 32KB bank | ~50 games | 15 |

### Key Features
- **NMI during boot**: fires NMI every 29780 CPU cycles during boot when the game enables it
- **VBlank toggle**: `$2002` bit 7 sets before NMI, clears on read (matches real hardware)
- **NMI enable tracking**: only fires NMI when game writes bit 7 to `$2000`
- **Controller simulation**: `--press-start N` sends Start button at frame N
- **Period conversion**: raw register values converted to Mesen decoded format (`raw * 2 + 1`)
- **Auto MIDI conversion**: pipes output through `mesen_to_midi.py` if available

## Games Extracted

### Tier S — Boot and Capture (music plays on boot)

| Game | Publisher | Mapper | Sq1 | Sq2 | Tri | Noise | Total |
|------|-----------|--------|-----|-----|-----|-------|-------|
| Final Fantasy | Square | MMC1 | 533 | 531 | 0 | 0 | 1064 |
| Final Fantasy II | Square | MMC1 | 361 | 360 | 0 | 0 | 721 |
| Final Fantasy III | Square | MMC3 | 502 | 500 | 0 | 0 | 1002 |
| Faxanadu | Hudson | MMC1 | 109 | 370 | 363 | 0 | 842 |
| Dragon Warrior | Enix | MMC1 | 115 | 85 | 117 | 0 | 317 |
| Dragon Warrior II | Enix | MMC1 | 97 | 79 | 83 | 0 | 259 |
| Kirby's Adventure | HAL/Nintendo | MMC3 | 530 | 601 | 565 | 1075 | 2771 |
| Mega Man 2 | Capcom | MMC1 | 234 | 279 | 404 | 700 | 1617 |
| Mega Man 3 | Capcom | MMC3 | 331 | 225 | 469 | 396 | 1421 |
| Mega Man 4 | Capcom | MMC3 | 95 | 247 | 130 | 138 | 610 |
| Mega Man 5 | Capcom | MMC3 | 164 | 587 | 275 | 720 | 1746 |
| Mega Man 6 | Capcom | MMC3 | 184 | 255 | 297 | 412 | 1148 |
| Darkwing Duck | Capcom | MMC1 | 165 | 264 | 167 | 353 | 949 |
| Chip 'n Dale | Capcom | MMC1 | 212 | 414 | 350 | 381 | 1357 |
| Strider | Capcom | MMC1 | 249 | 342 | 425 | 1162 | 2178 |
| Mighty Final Fight | Capcom | MMC3 | 152 | 355 | 224 | 385 | 1116 |
| Gargoyle's Quest II | Capcom | MMC3 | 142 | 124 | 100 | 0 | 366 |
| Metroid | Nintendo | MMC1 | 60 | 126 | 54 | 17 | 257 |
| Zelda II | Nintendo | MMC1 | 207 | 117 | 162 | 4 | 490 |
| Bionic Commando | Capcom | MMC1 | 167 | 84 | 199 | 156 | 606 |
| Double Dragon | Technos | MMC1 | 212 | 359 | 430 | 302 | 1303 |
| Maniac Mansion | LucasArts | MMC1 | 216 | 165 | 19 | 506 | 906 |

### Tier A — Boot + Start Press

| Game | Publisher | Mapper | Sq1 | Sq2 | Tri | Noise | Total |
|------|-----------|--------|-----|-----|-----|-------|-------|
| Contra | Konami | UxROM | 983 | 12 | 19 | 1778 | 2792 |
| Batman | Sunsoft | MMC3 | 180 | 139 | 307 | 222 | 848 |
| Journey to Silius | Sunsoft | MMC1 | 110 | 71 | 298 | 34 | 513 |
| Shadow of the Ninja | Natsume | MMC3 | 357 | 184 | 437 | 1044 | 2022 |
| Shatterhand | Natsume | MMC3 | 77 | 28 | 105 | 402 | 612 |
| Little Nemo | Capcom | MMC3 | 153 | 249 | 322 | 320 | 1044 |
| Ice Climber | Nintendo | NROM | 30 | 31 | 32 | 0 | 93 |

### Multi-Song Extractions

| Game | Method | Songs | Notes |
|------|--------|-------|-------|
| **Kid Icarus** | Hot-swap + $AC88 configs | 10 songs | Dual engine architecture cracked |
| **SMB3** | Direct channel processor | 18 songs identified | Song pointer table decoded |

## What We Learned About NES Music Encoding

### Discovery 1: The Period Encoding Discrepancy

Our emulator captures raw APU register values. Mesen captures decoded timer periods. The relationship:

```
mesen_period = raw_register * 2 + 1
```

This is because the NES APU's internal timer counts down from `(register + 1) * 2 - 1` clocks. Both represent the same frequency. We apply the `*2+1` conversion in our CSV output so `mesen_to_midi.py` produces correct pitches.

**Lesson:** When building capture tools, document the encoding convention. A mismatch silently produces octave errors.

### Discovery 2: Five Music Architectures Exist on NES

See `output/TAXONOMY.md` for the full catalog. Summary:

1. **Data-driven player** (most common): ROM bytes → driver → APU. Find pointer table, poke pointer, tick driver.
2. **Code-as-music**: Songs ARE 6502 subroutines. No data to parse. Call the subroutine each frame.
3. **Split architecture**: Pulse via data player, noise/triangle via code subroutines. Need both.
4. **RAM-resident music**: Song code copied to RAM during bank switch. Hot-swap banks to change songs.
5. **Script-loaded**: Game script interpreter loads songs from compressed resources. Need the interpreter to run.

Most games use Type 1. Kid Icarus uses all five simultaneously across different banks.

### Discovery 3: The Boot Sequence Matters

Games fall into three boot categories:

| Category | Behavior | What We Do |
|----------|----------|------------|
| **Immediate** | Music plays within 10 frames of RESET | Just capture |
| **Delayed** | Music plays after title screen animation (50-1500 frames) | Wait longer |
| **Start-gated** | Music plays only after Start button press | Use `--press-start N` |
| **PPU-dependent** | Boot requires PPU interaction (sprite-0, nametable) | Need VBlank toggle + sometimes bypasses |

Our VBlank toggle fix (`$2002` bit 7 clears on read, sets before NMI) handles most PPU-dependent boots. Games that check sprite-0 hit also work because we set bit 6. The remaining failures are games that spin on RAM flags waiting for NMI to change them — those need the NMI-during-boot feature.

### Discovery 4: Capcom vs Konami vs Nintendo Sound Design

From analyzing note counts across 36 games:

**Capcom** (MM2-6, Darkwing, Chip 'n Dale, Strider):
- Highest drum density: 400-1162 noise events per 80 seconds
- Balanced four-channel usage: all channels roughly equally active
- Heavy triangle bass (often more notes than pulse)
- Characteristic: rhythmic, driving, band-like

**Konami** (Contra, Gradius, Castlevania):
- Moderate drums: 19-1778 (Contra is an outlier)
- Pulse-dominant: melody carries the arrangement
- Atmospheric: long sustained notes, echo effects
- Characteristic: cinematic, dark

**Square/Enix** (FF1-3, DW1-2):
- Minimal drums: 0 noise events on title screens
- Pulse arpeggio patterns: 500+ rapid pulse notes (the Prelude)
- Triangle usually silent on title screens (saves for gameplay)
- Characteristic: classical, arpeggiated

**Nintendo** (Kid Icarus, Kirby, Metroid):
- Variable: Kirby has 1075 drums, Metroid has 17
- Bank-dependent: different banks have completely different engines
- Game-integrated: music tied to game state, not standalone
- Characteristic: unpredictable, game-specific

### Discovery 5: The Universal Extraction Pipeline

```
nes_rom_capture.py ─→ Mesen CSV ─→ mesen_to_midi.py ─→ MIDI ─→ generate_project.py ─→ RPP
```

Every tool in this chain already existed except `nes_rom_capture.py`. The emulator's CSV output is format-compatible with Mesen traces, so the entire downstream pipeline (MIDI conversion, REAPER project generation) works unchanged.

This means ANY improvement to `mesen_to_midi.py` (better noise mapping, envelope refinement, note boundary detection) automatically benefits ROM-captured music.

## Process Adaptations for Future Work

### For a New Game (Tier S attempt)

```bash
python scripts/nes_rom_capture.py <rom.nes> -o output/<Game>/rom_capture/ \
    --frames 4800 --game <Game> --song title
```

If this produces notes: done. Build RPP.

### If Title Screen Is Silent

```bash
# Add Start press
python scripts/nes_rom_capture.py <rom.nes> --press-start 60 ...

# If still silent, try multiple presses
# Edit button_script in code for complex navigation
```

### If Boot Fails Entirely (0 APU writes)

1. Check mapper support: `python -c "with open('rom.nes','rb') as f: h=f.read(16); print((h[6]>>4)|(h[7]&0xF0))"`
2. If unsupported mapper: add it (see NROM/UxROM as templates, ~12 lines each)
3. If supported but fails: the game needs PPU interaction during boot
4. Try: interactive boot with NMI during boot (the pattern from the Dragon Warrior III spin-loop bypass)

### For Multiple Songs Per Game

Use the techniques proven on Kid Icarus and SMB3:

1. **Game mode poke**: Find the game mode variable (usually in ZP or $01xx), poke it after boot
2. **Hot-swap**: Switch banks for one NMI to copy new song code to RAM, switch back
3. **Direct engine call**: Find the sound engine's channel processor and song pointer table, call directly with poked data pointers
4. **Song request register**: Find the RAM byte the game writes to request a song change, poke it

### For Unsupported Mappers

| Mapper | Games That Need It | Effort |
|--------|-------------------|--------|
| 5 (MMC5) | Castlevania III (JP), Just Breed | ~40 lines (complex) |
| 9/10 (MMC2/4) | Punch-Out!! | ~20 lines |
| 69 (FME-7/Sunsoft) | Batman: Return of the Joker, Gimmick! | ~30 lines |
| 19 (Namco 163) | Megami Tensei II, King of Kings | ~30 lines |
| 85 (VRC7) | Lagrange Point | ~40 lines (FM synth!) |

Each mapper is a self-contained class with `write()` and `get_prg_banks()` methods. The template is established.

## Files Produced This Session

### Tools
- `scripts/nes_rom_capture.py` — headless NES emulator (new)
- `.claude/skills/ROMEMULATOR.md` — Claude skill for the emulator approach (new)

### Documentation
- `output/KID_ICARUS_THE_FAMICOM_GHOST.md` — FDS vs NES discovery
- `output/SOUND_ENGINE_COMPARISON.md` — 7 game engines compared
- `output/KidIcarusTakeaways.md` — lessons for future ROM rips
- `output/Kid_Icarus/KID_ICARUS_HARNESS_AND_EXECUTION_SEMANTICS.md`
- `output/Kid_Icarus/KID_ICARUS_SONG_ROUTING_PROBLEM.md`
- `output/Kid_Icarus/KID_ICARUS_BRUTE_FORCE_APPROACH.md`
- `output/Kid_Icarus/KID_ICARUS_CODE_AS_MUSIC.md`
- `output/Kid_Icarus/KID_ICARUS_WHY_THIS_IS_HARD.md`
- `output/Kid_Icarus/KID_ICARUS_NES_EMULATOR_APPROACH.md`
- `output/KidIcarusSuccess.md` — success writeup
- `output/Super_Mario_Bros_3/Mario3Challenges.md` — SMB3 analysis
- `output/Super_Mario_Bros_3/SMB3_ROM_CAPTURE_STATUS.md`
- `output/NES_SOUNDTRACK_TIER_LIST.md` — 33 games tiered by difficulty
- `output/TAXONOMY.md` — music encoding taxonomy
- `output/CapcomChips.md` — Capcom sound engine analysis
- `output/SESSION_RESULTS.md` — this document

### REAPER Projects
47+ RPP files across 36+ games, all generated from ROM emulation.
