# NES Soundtrack Extraction Tier List

## Tier Definitions

| Tier | Difficulty | Method | What It Means |
|------|-----------|--------|---------------|
| **S** | Boot and capture | `nes_rom_capture.py` direct | Music plays on boot. One command. Done. |
| **A** | Boot + button navigation | Boot + scripted Start/A presses | Music plays after menu navigation. Need button script. |
| **B** | Boot + state pokes | Boot + RAM poke for game mode/song | Need to find the game mode variable and poke it. |
| **C** | Direct engine call | Find sound engine, call channel processor with poked data pointers | Need to reverse-engineer the song pointer table. SMB3 method. |
| **D** | Hot-swap / dual engine | Bank swap technique or combined music systems | Need to understand bank-switching music architecture. Kid Icarus method. |
| **F** | Full game emulation needed | SCUMM/complex scripting engine | Music loaded by game script interpreter, needs full game loop. Maniac Mansion territory. |

## The 30 Most Iconic NES Soundtracks

### Tier S — Boot and Capture (Easiest)

These games play music immediately or within seconds of boot. Our emulator handles them with zero effort.

| # | Game | Mapper | Status | Notes |
|---|------|--------|--------|-------|
| 1 | **Final Fantasy** | MMC1 | CAPTURED (533/531 notes) | Prelude plays on boot |
| 2 | **Final Fantasy II** | MMC1 | CAPTURED (361/360 notes) | Prelude on boot |
| 3 | **Final Fantasy III** | MMC3 | CAPTURED (502/500 notes) | Prelude on boot, JP only |
| 4 | **Dragon Warrior** | MMC1 | CAPTURED (115/85/117 notes) | Title theme ~6s after boot |
| 5 | **Dragon Warrior II** | MMC1 | CAPTURED (97/79/83 notes) | Title theme ~25s (scrolling intro) |
| 6 | **Faxanadu** | MMC1 | CAPTURED (109/370/363 notes) | Plays frame 1 |
| 7 | **Tetris** | MMC1 | Predicted S | Simple game, music on boot |
| 8 | **Dr. Mario** | MMC1 | Predicted S | Music on title screen |
| 9 | **Excitebike** | NROM | Predicted S | Mapper 0, simplest possible |
| 10 | **Balloon Fight** | NROM | Predicted S | Mapper 0 |
| 11 | **Ice Climber** | NROM | Predicted S | Mapper 0 |
| 12 | **Kung Fu** | NROM | Predicted S | Mapper 0 |

### Tier A — Boot + Buttons

These games need a Start press or menu navigation to reach the main music. Our emulator's button scripting handles this.

| # | Game | Mapper | Status | Notes |
|---|------|--------|--------|-------|
| 13 | **Metroid** | MMC1 | TESTING (batch) | May need Start press for title music |
| 14 | **Legend of Zelda** | MMC1 | TESTING (batch) | Title scrolls then music starts |
| 15 | **Zelda II** | MMC1 | TESTING (batch) | Similar to Zelda I |
| 16 | **Ninja Gaiden** | MMC1 | TESTING (batch) | Cinematic intro may play on boot |
| 17 | **Bionic Commando** | MMC1 | TESTING (batch) | Title screen should have music |
| 18 | **Double Dragon** | MMC1 | TESTING (batch) | Title theme after brief intro |
| 19 | **Bubble Bobble** | MMC1 | TESTING (batch) | Title screen music |

### Tier B — Boot + State Pokes

These games have multiple songs accessible through RAM variable pokes after boot. Need to find the game mode or song-request variable.

| # | Game | Mapper | Need | Notes |
|---|------|--------|------|-------|
| 20 | **Mega Man 2** | MMC1 | Find song request register | One of the greatest NES soundtracks. Title plays on boot, but the 8 Robot Master themes need state pokes |
| 21 | **Castlevania** | MMC1 | Already extracted via NSF | Proven pipeline. ROM emulator would be a second validation source |
| 22 | **Contra** | UxROM (2) | Need mapper 2 support (~10 lines) | Already extracted via NSF. Mapper 2 is trivial to add |
| 23 | **Kirby's Adventure** | MMC3 | Find song request register | 512KB, large soundtrack. Title may boot directly |
| 24 | **Ninja Gaiden II** | MMC3 | State pokes for different acts | Each act has unique music |
| 25 | **Ninja Gaiden III** | MMC3 | State pokes for different acts | Same engine as NG2 |
| 26 | **River City Ransom** | MMC3 | Find area music variable | Different zones = different songs |

### Tier C — Direct Engine Call

These need the SMB3 approach: find the sound engine's channel processor, the song pointer table, and call the processor directly with poked data pointers.

| # | Game | Mapper | Need | Notes |
|---|------|--------|------|-------|
| 27 | **Super Mario Bros. 3** | MMC3 | CRACKED (18 songs) | Song pointer table at $A76C, channel processor at $E528 |
| 28 | **Mega Man 3** | MMC3 | Find engine + pointer table | Same Capcom engine family as MM2 but different mapper |
| 29 | **Mega Man 4-6** | MMC3 | Same approach as MM3 | Capcom standardized their engine |
| 30 | **Castlevania III** | MMC3 | VRC6 expansion (JP) vs standard (US) | US version should work with MMC3 support |

### Tier D — Hot-Swap / Complex

| # | Game | Mapper | Need | Notes |
|---|------|--------|------|-------|
| 31 | **Kid Icarus** | MMC1 | CRACKED (10 songs) | Dual engine, hot-swap + $AC88 configs |
| 32 | **Battletoads** | AxROM (7) | Need mapper 7 (~10 lines) | Already partially extracted via NSF/parser |

### Tier F — Full Game Emulation

| # | Game | Mapper | Need | Notes |
|---|------|--------|------|-------|
| 33 | **Maniac Mansion** | MMC1 | CAPTURED (intro theme) | SCUMM engine. Got intro by letting interpreter run 80s. Need more time for character-specific themes |

## Mapper Support Status

| Mapper | Name | Games | Status | Effort to Add |
|--------|------|-------|--------|---------------|
| 0 | NROM | ~100 early games | **Not yet added** | ~5 lines (no banking, fixed 32KB) |
| 1 | MMC1 | ~400 games | **Working** | Done |
| 2 | UxROM | ~200 games (CV1, Contra, MM1) | **Not yet added** | ~10 lines |
| 3 | CNROM | ~100 games | **Not yet added** | ~5 lines (CHR only) |
| 4 | MMC3 | ~350 games | **Working** | Done |
| 7 | AxROM | ~50 games (Battletoads, W&W) | **Not yet added** | ~10 lines |

Adding mappers 0, 2, 3, and 7 would cover **95%+ of the NES library**.

## Quick Wins (Games Most Likely to Work Right Now)

Based on mapper support (MMC1 or MMC3) and likelihood of boot-and-capture:

1. **Tetris** (MMC1) — iconic theme, should boot instantly
2. **Dr. Mario** (MMC1) — Fever/Chill themes on title
3. **Kirby's Adventure** (MMC3, 512KB) — massive soundtrack
4. **Adventures of Lolo** (MMC1) — charming puzzle music
5. **Darkwing Duck** (MMC1) — excellent Capcom soundtrack
6. **Chip 'n Dale Rescue Rangers** (MMC1) — classic Capcom
7. **Journey to Silius** (MMC1) — legendary Sunsoft soundtrack
8. **StarTropics** (MMC3) — underrated soundtrack
9. **Crystalis** (MMC3) — epic RPG soundtrack
10. **Little Nemo** (MMC3) — Capcom quality

## The Dream Pipeline

```
1. Add mapper 0/2/3/7 support (~30 lines total)
2. Batch-run nes_rom_capture.py on every ROM in D:/All NES Roms/
3. Filter: any capture with >50 Sq1 notes = successful extraction
4. Auto-generate MIDI + REAPER projects
5. Result: 500+ NES game title screen soundtracks extracted
```

This is achievable in one more session.

## Games With the Best Soundtracks (Subjective, For Prioritization)

If we had to pick the 10 most musically important NES games to extract COMPLETELY (all songs, not just title screen):

1. **Mega Man 2** — 8 Robot Master themes + Wily stages
2. **Castlevania** — Vampire Killer, Bloody Tears (already done via NSF)
3. **Super Mario Bros. 3** — 18 songs identified, need full captures
4. **Final Fantasy** — Prelude, Overworld, Battle, Dungeon, Town, Victory
5. **Legend of Zelda** — Overworld, Dungeon, Ending
6. **Metroid** — Brinstar, Kraid, Ridley, Escape
7. **Ninja Gaiden** — All act themes + cinematics
8. **Contra** — Jungle, Waterfall, Base (already done via NSF)
9. **Kirby's Adventure** — Huge soundtrack, many worlds
10. **Dragon Warrior** — Overworld, Battle, Castle, Town

For most of these, the title screen is captured. Getting the remaining songs requires either the state-poke technique (Tier B) or the direct-engine-call technique (Tier C).
