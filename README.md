# ReapNES — NES Music Extraction & Synthesis

## [Browse the NES Tone Database](https://t3dy.github.io/Battletoads/output/tone_database/index.html)

> 625+ instrument profiles · 66 games · 160 REAPER projects · 465 technical documents

---

## What This Is

A complete pipeline for extracting music from NES game ROMs, converting it to MIDI, generating REAPER DAW projects, and analyzing the timbral characteristics of every instrument. Built around a headless NES emulator that boots ROMs without graphics and captures the raw audio register writes.

**No manual gameplay required.** The emulator navigates menus, presses buttons, and switches songs automatically.

## The NES Sound Chip (RP2A03)

The NES has 5 sound channels, all synthesized — no samples, no wavetables, just simple waveforms shaped by per-frame register writes at 60Hz:

### Pulse 1 & 2 (Square Wave)
- **4 duty cycles**: 12.5% (thin/buzzy), 25% (bright/hollow), 50% (warm/full), 75% (=25% inverted)
- **11-bit period register** → frequencies from ~55Hz to ~12.4kHz
- **4-bit volume** (0-15) with optional hardware envelope decay
- **Sweep unit** for automatic pitch bends
- Two identical channels allow harmony, echo, or call-and-response

### Triangle (Bass)
- **Fixed triangle waveform** — no duty cycle, no volume control
- Produces frequency **one octave lower** than pulse for the same period value
- Only on/off gating via linear counter — all expression comes from note timing
- The NES's only sub-bass channel

### Noise (Percussion)
- **Linear-feedback shift register** generating pseudo-random noise
- **2 modes**: long (white noise) and short (metallic/tonal)
- **16 selectable periods** control the noise "pitch" (brightness)
- Combined with 4-bit volume for synthesized drums — every kick, snare, and hi-hat is built from filtered noise

### DMC (Delta Modulation)
- 1-bit delta-encoded PCM playback at 16 sample rates
- Used sparingly (bass drums, voice clips) — many drivers skip it entirely

## How Games Encode Music

Every NES game has its own music driver — 6502 assembly code that reads song data from ROM and writes to the APU registers 60 times per second. We've cataloged 8 distinct driver families:

### Konami (Castlevania, Contra, Gradius)
**Nibble-packed notes**: `[PPPP DDDD]` — high 4 bits = pitch (C-B), low 4 bits = duration index. The Maezawa driver family. Dark, atmospheric sound with parametric two-phase envelopes.

### Capcom (Mega Man 2-6, Darkwing Duck, Chip 'n Dale)
**Octave + semitone bytes**: Full note identity in one byte. The most rhythmically dense music on NES — 700+ drum hits per 80 seconds is typical. Bright, driving, band-like sound with dual-duty pulse arrangement (50% lead, 25% harmony).

### Square (Final Fantasy)
**Digit-encoded notes**: First digit = pitch (0-B = C through B), second = duration. Master Music Table at ROM $34010 with 23 songs × 3 channel pointers. Classical, arpeggiated. The Prelude's ascending arpeggio is the most recognizable NES musical motif.

### Nintendo (Kid Icarus, Kirby, Metroid)
**Varies wildly per game**. Kid Icarus uses code-as-music (songs ARE 6502 subroutines), RAM-resident music code, AND a data-driven config table — three engines in one game. Kirby uses standard data-driven. Metroid uses sparse atmospheric drones.

### Rare (Battletoads, Wizards & Warriors)
**Byte-index notes** with 20-command dispatch. Dual-mode duration (inline or persistent). Software volume register with ramp and oscillate modes. Rich harmonies, the most complex command set we've analyzed.

### David Warhol / Realtime Associates (Dick Tracy, Maniac Mansion, Rocketeer)
**MIDI-derived format**. Composers wrote in Cakewalk/Performer, Warhol converted to NES format. Signature "echo" instrument uses hardware sweep every 13 frames. Never uses DMC (Warhol couldn't figure it out).

### Sunsoft (Batman, Journey to Silius, Blaster Master)
**Aggressive duty cycling** for bass tones and rapid arpeggios for pseudo-polyphony. Blaster Master's 1063 triangle notes in 80 seconds is the most bass-dense capture in our collection. Punchy, funk-influenced.

### Enix (Dragon Warrior)
**Orchestral-influenced** three-channel compositions by Koichi Sugiyama. Minimal percussion. Stately overworld themes.

## The Headless NES Emulator

`scripts/nes_rom_capture.py` — boots any NES ROM, simulates the 6502 CPU at 60Hz, captures APU register writes, and outputs MIDI + REAPER projects.

### Supported Mappers (6 types, ~95% of NES library)

| Mapper | Name | Banking | Key Games |
|--------|------|---------|-----------|
| 0 | NROM | None (32KB fixed) | Donkey Kong, Ice Climber, Excitebike |
| 1 | MMC1 | 16KB switching, 5-bit serial | Zelda, Metroid, Final Fantasy, Mega Man 2 |
| 2 | UxROM | Single register write | Castlevania, Contra, Duck Tales |
| 3 | CNROM | CHR only (PRG fixed) | Gradius |
| 4 | MMC3 | 8KB switching, register select | SMB3, Kirby, Mega Man 3-6, TMNT |
| 7 | AxROM | 32KB switching | Battletoads, Wizards & Warriors |

### Multi-Song Extraction Methods

| Method | How It Works | Games |
|--------|-------------|-------|
| **Boot & Capture** | Music plays on boot | 50+ games |
| **ZP Poke** | Write song ID to a zero-page variable | Final Fantasy ($4B), Zelda II ($E0) |
| **ROM Patch** | Patch the `LDA #song_id` byte in the boot code | Mega Man 2 ($9F53) |
| **Hot-Swap** | Switch banks for 1 frame to copy new song code to RAM | Kid Icarus |
| **Direct Engine Call** | Call the sound engine's play/tick routines directly | SMB3, Dick Tracy (Warhol) |

### Usage

```bash
# Title screen
python scripts/nes_rom_capture.py rom.nes -o output/ --frames 4800 --game Name --song title

# With Start button press
python scripts/nes_rom_capture.py rom.nes --press-start 60 --game Name --song title

# Multi-song: poke song variable at frame 5
python scripts/nes_rom_capture.py rom.nes --poke-at "5:0x4B=0x50" --game FF1 --song Battle
```

## Complete Soundtracks Extracted

| Game | Songs | Method | Highlight |
|------|-------|--------|-----------|
| **Final Fantasy** | 25 | ZP $4B poke | Prelude, Overworld, Battle, all 6 Dungeons, Town, Shop, Victory |
| **Mega Man 2** | 14 | ROM patch | All 8 Robot Masters, Wily stages, Boss, Password |
| **Kid Icarus** | 12 | Hot-swap + config | 3 banks × multiple songs, dual-engine architecture |
| **Dick Tracy** | 5 | Warhol driver direct call | Warhol "echo" instrument showcase |
| **Zelda II** | Multi | ZP $E0 poke | Extracting now |

## The Tone Database

The [NES Tone Database](https://t3dy.github.io/Battletoads/output/tone_database/index.html) catalogs every instrument extracted from every game:

- **Tones tab**: 625 instrument profiles with SVG envelope sparklines, ADSR values, duty cycle analysis
- **Games tab**: 66 games with track counts and note totals
- **Documents tab**: 465 searchable technical documents from 4 NES project repositories
- **Per-game pages**: Detailed breakdowns of each game's sound driver, encoding format, and instrument characteristics

## Tools

| Script | Purpose |
|--------|---------|
| `scripts/nes_rom_capture.py` | Headless NES emulator with 6 mapper types |
| `scripts/mesen_to_midi.py` | Mesen APU capture CSV → MIDI |
| `scripts/nsf_to_reaper.py` | NSF file → MIDI + REAPER project |
| `scripts/generate_project.py` | MIDI → REAPER project with ReapNES synth |
| `scripts/extract_tones.py` | MIDI → ADSR envelope analysis JSON |
| `scripts/build_tone_db.py` | JSON → SQLite database + HTML website |
| `scripts/generate_game_pages.py` | Per-game HTML pages with instrument descriptions |

## Project History

This project started as Battletoads NES music reconstruction (see [BattletoadsOLDreadme.md](BattletoadsOLDreadme.md)) and grew into a universal NES music extraction pipeline. The original work on Castlevania, Contra, and Battletoads established the trace validation methodology. The headless emulator approach was developed during the Kid Icarus session when the NSF file turned out to be from the wrong platform (FDS vs NES cartridge).

## Sheet Music

All extracted MIDIs are being converted to MusicXML format using music21.
MusicXML files can be opened in:
- **MuseScore** (free) — standard notation + guitar tablature view
- **Finale** / **Sibelius** — professional notation
- **Any MusicXML-compatible editor**

Sheet music files are in `output/sheet_music/<Game>/`.

The NES channels map naturally to standard instruments:
- **Square 1/2** → Lead/harmony melody (treble clef)
- **Triangle** → Bass line (bass clef / bass guitar tab)
- **Noise** → Drum notation

