# David Warhol NES Sound Driver

## Source

Information from VGMpf Wiki: David Warhol (NES Driver)

## Overview

David Warhol programmed a custom 6502 sound driver used exclusively by Realtime Associates from 1990-1992. The workflow was unique: composers (George Sanger, David Hayes, Eric Swanson, Warhol himself) created MIDI files in Cakewalk or Performer, which Warhol arranged and converted to a text format the NES could read.

## Key Technical Details

### Output
- Targets RP2A03/RP2A07 (standard NES APU)
- **DPCM never used** — Warhol couldn't figure out how to use it
- Exception: Adventures of Rad Gravity uses raw PCM during ending (may not be Warhol's work)

### Signature Instruments
- **"Echo" instrument**: hardware sweep every 13 frames — the driver's most distinctive sound
- **Duty cycle basses**: timbre changes via duty cycle switching
- **Square drums**: pulse channel percussion, notably in Defenders of Dynatron City

### Games Using This Driver (10 released + 1 unreleased)

| Year | Game | Mapper | Freq Table ROM Address | Status |
|------|------|--------|----------------------|--------|
| 1990 | Total Recall | UxROM (2) | $1824A-$182C9 | Boot fails |
| 1990 | Dick Tracy | UxROM (2) | $025F-$02DE | Boot fails |
| 1990 | Swords & Serpents | UxROM (2) | $14211-$14290 | Boot fails |
| 1990 | Maniac Mansion | MMC1 (1) | $0E2F-$0EAE | **CAPTURED** (216/165/19/506 notes) |
| 1990 | Adventures of Rad Gravity | MMC1 (1) | $C2EC-$C36B | Boot fails |
| 1991 | Fun House | UxROM (2) | $42B9-$4338 | Boot fails |
| 1991 | The Rocketeer | MMC1 (1) | $02AF-$032E | Boot fails |
| 1991 | Monster Truck Rally | CNROM (3) | $34F7-$350E | Boot fails |
| 1992 | Defenders of Dynatron City | MMC3 (4) | $142AE-$1432D | Boot fails |
| 1992 | Caesars Palace | UxROM (2) | $02A9-$0328 | Boot fails |

### Frequency Register Table

The driver uses a non-standard period table format. From VGMpf:

```
C-6 = $34    B-5 = $37    A#5 = $3A    A-5 = $3E
G#5 = $42    G-5 = $46    F#5 = $4A    F-5 = $4F
E-5 = $53    D#5 = $58    D-5 = $5E    C#5 = $63
C-5 = $69    B-4 = $70    A#4 = $76    A-4 = $7E
...
C-1 = $6AE   B-0 = $712   A#0 = $77E   A-0 = $7F0
```

These are standard NES NTSC period values (matching our period table from other games). The table spans 7 octaves (C-0 to C-6), stored as 16-bit little-endian words in descending order.

## Why These Games Fail to Boot

All Warhol driver games except Maniac Mansion produce 0 APU writes in our emulator. The issue is the boot sequence — these games all:

1. Wait for PPU VBlank with `LDA $2002; BPL self` loops
2. Need NMI to be enabled before music starts
3. Have complex title screen animation sequences that require PPU interaction

Maniac Mansion works because its SCUMM interpreter runs independently of PPU state and eventually triggers the sound engine after ~1200 frames.

## Extraction Approach

For Warhol driver games, the recommended approach is:

1. **Use the known frequency table addresses** to locate the sound engine in each ROM
2. **Find the channel output routine** (STA $400x,X pattern near the freq table)
3. **Find the song data pointer** and per-frame tick entry point
4. **Call the tick directly** with poked song data (SMB3 method)

The VGMpf frequency table addresses give us exact ROM offsets for each game, which saves the search step that normally takes the longest.

## What Maniac Mansion Taught Us About Warhol's Driver

From our successful capture:
- **216 Sq1, 165 Sq2, 19 Triangle, 506 Noise** notes in the intro theme
- The driver produces very noise-heavy output (506 drum hits) consistent with the "square drums" documentation
- Triangle is lightly used (19 notes) which matches Warhol's driver being MIDI-focused (MIDI doesn't have a native triangle wave concept)
- The SCUMM engine acts as the host that loads and triggers the Warhol sound driver

## The Echo Instrument

The most distinctive feature of Warhol's driver: a "hardware sweep every 13 frames." On the NES, the sweep unit ($4001/$4005) can be programmed to automatically shift the period register up or down over time. Most NES music drivers use sweep sparingly (for pitch bends or vibrato). Warhol's driver uses it as a core timbral effect — the sweep creates an echo-like decay that gives his music a reverb quality unique among NES games.

This sweep pattern should be visible in our CC12/sweep automation data as periodic STA $4001 writes every 13 frames. The tone database profiles for Maniac Mansion should show this pattern.
