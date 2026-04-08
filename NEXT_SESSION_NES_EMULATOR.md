# Next Session: NES ROM Emulator Music Extraction

## What Was Built

`scripts/nes_rom_capture.py` — headless NES emulator for automated music extraction.
`scripts/extract_tones.py` — ADSR envelope analyzer for captured MIDIs.
`scripts/build_tone_db.py` — SQLite + HTML tone database generator.

## Current Numbers

- 186+ MIDIs, 160+ REAPER projects, 66+ games, 625+ tone profiles
- Tone database website: `output/tone_database/index.html`

## Multi-Song Extraction Methods (Proven)

### Method 1: ZP Poke (FF1)
Boot → stabilize 5 frames → poke ZP `$4B` = song_number → capture.
Works because the sound engine reads ZP each frame for the current song.

### Method 2: ROM Patch (MM2)
Patch the `LDA #$FE` immediate byte in the boot code to a different song ID.
Each boot plays a different song. No timing issues.

### Method 3: Hot-Swap Banks (Kid Icarus)
Boot bank 1 → switch `$BE` to target bank for 1 NMI → switch back.
Target bank's init copies song code to RAM.

### Method 4: Direct Engine Call (SMB3, Dick Tracy/Warhol)
Find the sound engine's play_song(X) and tick() entry points.
Call play_song with X=song_number, then tick() per frame.

### Method 5: Combined Dual Engine (Kid Icarus bank 4)
Pulse via `$AC88` config table + noise/tri via code-as-music dispatches.

## Games Needing More Songs

| Game | Current | Method to Try | Notes |
|------|---------|--------------|-------|
| MM3 | 1 song | ROM-patch at $CE48+1 | Only 1 unique found — try more call sites |
| MM4 | 1 song | Find play_song pattern | Different from MM3/5/6 |
| MM5 | 1 song | ROM-patch (scanning) | $FF3D = play_song |
| MM6 | 1 song | ROM-patch (scanning) | $C5F6 = play_song |
| Kirby | 1 song | ZP scan (running) | Huge soundtrack |
| Metroid | 1 song | ZP scan (running) | |
| Zelda II | 1 song | ZP scan (running) | |
| Double Dragon | 1 song | ZP scan (running) | |
| Dragon Warrior | 1 song | Need real song ID (not $E6) | |
| All Capcom | 1 song each | Try ROM-patch on each | |
| Warhol games | 1 each (3 games) | Multi-song via X register | |

## Games That Don't Boot

Castlevania, Legend of Zelda, Ninja Gaiden, and ~15 others fail because their boot
sequences check PPU state (sprite-0 hit, nametable data, OAM state) beyond what our
stub provides. Solutions:
1. Find and bypass the specific PPU check in each game
2. Add more PPU stub behavior
3. Use the direct-engine-call method (bypass boot entirely)

## Warhol Driver Info (from VGMpf)

David Warhol's NES driver used by Realtime Associates (1990-1992).
Games: Dick Tracy, Total Recall, Swords & Serpents, Maniac Mansion,
Adventures of Rad Gravity, Fun House, Rocketeer, Monster Truck Rally,
Defenders of Dynatron City, Caesars Palace.

Entry points (Dick Tracy pattern):
- `$8001: JMP tick` — per-frame sound update
- `$8004: JMP play_song` — start song (X = song number)
- `$8029` — actual play_song handler
- `$80A0` — actual tick handler

Captured: Dick Tracy (4 songs), Rocketeer (1), Caesars Palace (1), Maniac Mansion (1).
Not yet: Total Recall, Swords & Serpents, Rad Gravity, Fun House, Monster Truck Rally,
Defenders of Dynatron City (different entry point offsets).

## FF1 Music Format (from rom hacking forum)

Master Music Table at ROM $34010. 23 songs × 6 bytes (3 channel pointers).
Note encoding: first digit = pitch (0-B = C through B), second = duration.
$C = rest, $D0-$D7 = loop/repeat, $D8-$DB = octave shift, $F = control string.
All 23 songs extracted and named via ZP $4B poke.
