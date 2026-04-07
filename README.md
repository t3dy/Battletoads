# NES Music Extraction & Synthesis

**Automated extraction of NES game music via headless ROM emulation, with MIDI conversion, REAPER project generation, and a browsable tone database.**

## NES Tone Database

**[Browse the NES Tone Database](output/tone_database/index.html)** — 625+ instrument profiles across 66 games, with ADSR envelope analysis, duty cycle patterns, and SVG waveform sparklines. Includes a Games tab (160+ REAPER projects) and a Documents tab (465 technical documents).

## Headless NES Emulator

`scripts/nes_rom_capture.py` boots any NES ROM, simulates the CPU at 60Hz, captures APU register writes, and outputs MIDI + REAPER projects. Supports 6 mapper types (NROM, MMC1, UxROM, CNROM, MMC3, AxROM) covering ~95% of the NES library.

```bash
# Extract title screen music from any supported ROM
python scripts/nes_rom_capture.py <rom.nes> -o output/ --frames 4800 --game Name --song title

# Multi-song extraction (e.g., Final Fantasy: poke ZP $4B for each song)
python scripts/nes_rom_capture.py <rom.nes> --poke-at "5:0x4B=0x50" --game FF1 --song Battle
```

## The Original Story

This project began as Battletoads NES music reconstruction and grew into a universal NES music extraction pipeline.

**Hardware-accurate reproduction of NES game audio using Mesen APU trace captures, MIDI+SysEx encoding, and custom JSFX synthesizers in REAPER.**

This repository documents reverse engineering, pipeline building, debugging, and hard-won architectural lessons in the pursuit of note-accurate NES music reproduction.

---

## The Story

### Days 1-2: The Pipeline Existed, But Didn't Work

This project began as part of **ReapNES** / **NESMusicStudio** — a broader effort to extract music from NES game ROMs and play it back through custom synthesizers in REAPER. The pipeline had already been proven on Konami titles (Castlevania, Contra) using ROM disassembly and 6502 emulation:

```
NSF file → py65 6502 CPU → APU register captures → MIDI with CC11/CC12 → REAPER + JSFX synth
```

For Castlevania's "Vampire Killer," this achieved **0 pitch mismatches and 0 volume mismatches** across 1,792 frames on both pulse channels. Contra's "Jungle" reached **0 pitch mismatches** across 2,976 frames.

Battletoads was supposed to be the next game through the batch pipeline. Instead, it became a five-day education in why assumptions kill.

### The JSFX Disaster

The automated pipeline (`nsf_to_reaper.py --all`) produced 21 MIDIs, 21 REAPER projects, and 21 WAV previews. The WAVs played sound. The REAPER projects played **nothing**. Multiple rounds of debugging RPP structure, MIDI embedding format, and slider configuration found nothing wrong — because the bug wasn't in the data.

**The ReapNES_Console.jsfx synthesizer had a compile-time syntax error.** Two empty `else` branches contained only comments with no expressions. JSFX requires at least one expression in every branch. The entire `@sample` block failed to compile. The synth received MIDI (visible as activity indicators) but produced zero audio samples.

This was visible the entire time as a red error banner in the FX window. Nobody checked.

### The Wrong Song

While debugging the silence, we compared our NSF extraction against a Mesen hardware trace of actual gameplay. The comparison showed the data streams were "fundamentally different." We spent rounds investigating why.

**We were comparing the wrong song.** NSF Song 2 is "Interlude" (a cutscene track). Level 1 (Ragnarok's Canyon) is **Song 3**. A 30-second web search for the track listing would have caught this immediately.

### NSF Is Not Ground Truth for Battletoads

Even after fixing the song mapping, the NSF extraction doesn't match in-game audio. Unlike the well-behaved Konami NSF drivers, Battletoads (Rare) has a complex sound system where NSF playback diverges from actual in-game audio:

| Aspect | NSF Extraction | Mesen Trace (Real Game) |
|--------|---------------|------------------------|
| Level 1 intro | No intro, bass starts at frame 4 | 17-second atmospheric noise crescendo |
| Pulse periods | Static per note | ±4 oscillation every frame (sweep unit vibrato) |
| Triangle pitch | Single period per note | 1-unit wobble every frame (micro-tuning) |
| Noise channel | Zero activity in opening | Slow build from vol 1→3+ (atmospheric wash) |

**The Mesen trace captures exactly what the NES APU produces during real gameplay.** Every sweep oscillation, every volume micro-adjustment, every frame.

### Day 3: Building the Trace Pipeline

With NSF ruled out as ground truth, we built `scripts/trace_to_midi.py` — a new pipeline that reads Mesen CSV captures and produces:

- **MIDI files** with CC11 (volume), CC12 (duty cycle), and note events
- **SysEx APU register track** — raw per-frame register state for the APU2 synth
- **Console REAPER projects** (CC-driven, good for keyboard play)
- **APU2 REAPER projects** (SysEx register replay, maximum fidelity)

The SysEx path is critical. MIDI can encode pitch, volume, and duty cycle, but **cannot encode the sweep unit** — the hardware pitch bend that gives Battletoads its signature bass slides. The APU2 synth reads raw register state from SysEx messages and replays it hardware-accurately, including sweep, noise mode, and phase reset.

### Day 4: Fixing Everything That Was Silently Broken

- **CC11 volume decoding** was wrong: `/127*15` instead of `/8` — lost 1 level at volumes 10-15
- **CC12 duty decoding** was wrong: `min(3,x)` instead of `floor(x/32)` — always gave duty 3 (75%)
- **Noise duration** was wrong: waited for vol=0 instead of capping at 12 frames — caused 500ms+ drum smear
- **RPP generator** was using `SOURCE MIDI FILE` references instead of inline `HASDATA` embedding
- **nsf_to_reaper.py** had an inline `build_rpp()` skeleton that bypassed the real project generator

Each independently fixable. Together they meant even a compiling synth would produce wrong audio.

### Day 5: The Architecture Crystallizes

The core realization: two fundamentally different playback modes need different synths:

| Mode | Synth | Data Source | Fidelity |
|------|-------|-------------|----------|
| File playback (archival) | APU2 | SysEx register replay from Mesen trace | ~95% |
| File playback (portable) | Console | CC11/CC12 from MIDI | ~70% |
| Keyboard play (live) | Console | ADSR envelopes, no file data | Approximate |

The **dual-mode contract**: when CC11/CC12 arrives, bypass ADSR and let file data drive volume/duty directly. When no CC data (keyboard play), use ADSR envelopes. Controlled by a per-channel `cc_active[]` flag.

---

## What's Here

### Pipeline Scripts
| Script | Purpose |
|--------|---------|
| `scripts/trace_to_midi.py` | Mesen CSV → MIDI+SysEx → REAPER projects (trace path) |
| `scripts/nsf_to_reaper.py` | NSF → 6502 emulation → MIDI → REAPER (NSF path) |
| `scripts/generate_project.py` | MIDI → REAPER RPP with synth, routing, inline data |
| `scripts/sync_jsfx.py` | Deploy JSFX to REAPER effects directory with validation |
| `scripts/session_startup_check.py` | Pre-session environment verification |
| `scripts/mesen_to_midi.py` | Mesen trace to MIDI converter |

### Synthesizers (JSFX for REAPER)
| Synth | Sliders | Purpose |
|-------|---------|---------|
| `ReapNES_Console.jsfx` | 38 | ADSR + CC dual mode, keyboard play, mixing |
| `ReapNES_APU2.jsfx` | 19 | Hardware-accurate SysEx register replay |
| `ReapNES_APU.jsfx` | 15 | Original CC-only synth (legacy) |

### Output
```
output/Battletoads/
  nsf/    — NSF file (21 songs)
  midi/   — NSF-extracted MIDIs (all 21)
  reaper/ — NSF-based RPPs (all 21, low fidelity)
  wav/    — NSF WAV previews (all 21)
  mp3/    — Reference MP3s from Zophar (all 21)

output/Battletoads_trace/
  midi/   — Trace-extracted MIDIs (Title Screen + Level 1 segments)
  reaper/ — Trace-based RPPs (Console + APU2 variants)

Projects/Battletoads/
  *.rpp   — Ready-to-open REAPER projects
```

### Documentation
| Doc | What It Covers |
|-----|----------------|
| `docs/HANDOVER_BATTLETOADS.md` | Complete session handover — state, fixes, next steps |
| `docs/FRAMEBYFRAME.md` | NSF vs Mesen comparison proving NSF is inadequate |
| `docs/FINDINGTRACKBOUNDARIES.md` | NSF song# → game level mapping with sources |
| `docs/LEAVENOTURNUNSTONED.md` | Exhaustive parameter checklist for every APU register |
| `docs/DATAONTOLOGY.md` | Complete data schema: ROM to REAPER playback |
| `docs/WHYSUCHABADSTARTWITHBATTLETOADS.md` | Honest failure audit |
| `docs/WHATWORKEDWITHCONTRAANDCASTLEVANIA.md` | Methodology that achieved 0 mismatches |
| `docs/MISTAKEBAKED.md` | 8 rules from blunders, with prompt costs |
| `docs/BUILDINGTHEENVIRONMENT.md` | Infrastructure fixes to prevent recurrence |
| `docs/TIPSFORWORKINGWITHTED.md` | Collaboration patterns, vocabulary bridging |
| `docs/PROMPTENGINEERINGCRITIQUE.md` | Session failure assessment |
| `docs/HIROPLANTAGENET_MARIO_FIDELITY.md` | Mario fidelity decomposition |
| `docs/HACKINGMARIOWEB.md` | SMB1 sound engine research |
| `docs/MARIODISCOVERIES.md` | Mario-specific NSF/Mesen divergence findings |
| `docs/ROM_MUSIC_MYSTERIES.md` | Open questions in NES music reverse engineering |
| `docs/VALIDATION.md` | Gate protocol for pre-delivery quality assurance |

---

## Fidelity Hierarchy

Truth flows downhill. Never let a lower layer override a higher one.

1. **ROM/Trace** — Mesen APU register dumps. Frame-level ground truth.
2. **NSF emulation** — 6502 CPU runs the sound driver. May diverge from game.
3. **MIDI file** — CC automation IS the envelope. Synth plays it back verbatim.
4. **ADSR approximation** — Only for live keyboard when no CC data exists.

---

## Architecture

```
Mesen Trace (.csv)                     NSF File (.nsf)
     │                                      │
     ▼                                      ▼
trace_to_midi.py                    nsf_to_reaper.py (py65 6502)
     │                                      │
     ├── MIDI (CC11/CC12/notes)            MIDI (CC11/CC12/notes)
     │        │                                │
     │        ▼                                ▼
     │   generate_project.py ─────── REAPER RPP (Console synth)
     │
     └── SysEx (raw APU registers per frame)
              │
              ▼
         generate_project.py ─────── REAPER RPP (APU2 synth)
                                          │
                                   Hardware-accurate replay
                                   (sweep, noise mode, phase reset)
```

---

## Track Listing: Battletoads (Rare, 1991)

| NSF # | Track Name | Game Context |
|-------|-----------|--------------|
| 1 | Title | Title screen |
| 2 | Interlude | Between-level cutscene |
| **3** | **Ragnarok's Canyon** | **Level 1** |
| 4 | Level Complete | Victory jingle |
| 5 | Wookie Hole | Level 2 |
| 6 | Turbo Tunnel | Level 3 (walk section) |
| 7 | Turbo Tunnel Bike Race | Level 3 (bike section) |
| 8 | Arctic Caverns | Level 4 |
| 9 | Surf City & Terra Tubes | Levels 5 & 9 |
| 10 | Karnath's Lair | Level 6 |
| 11 | Volkmire's Inferno | Level 7 |
| 12 | Jet Turbo | Level 7 (jet section) |
| 13 | Intruder Excluder | Level 8 |
| 14 | Rat Race | Level 10 |
| 15 | Clinger-Winger | Level 11 |
| 16 | The Revolution | Level 12 (Dark Queen) |
| 17 | Boss Battle / Ending | Boss fights + ending |
| 18 | Unused | Cut content |
| 19 | Continue & Game Over | Short jingle |
| 20 | Pause Beat | Pause screen |
| 21 | Unused 2 | Cut content |

---

## Key Commands

```bash
# Trace pipeline (Battletoads fidelity path)
python scripts/trace_to_midi.py "C:/Users/PC/Documents/Mesen2/capture.csv" \
  -o output/Battletoads_trace/ --game Battletoads \
  --name "Ragnoraks_Canyon" --seg-num 3

# NSF pipeline (batch, lower fidelity)
python scripts/nsf_to_reaper.py output/Battletoads/nsf/Battletoads.nsf --all -o output/Battletoads/

# Generate REAPER project from any MIDI
python scripts/generate_project.py --midi <file.mid> --nes-native -o <output.rpp>

# Sync JSFX synth to REAPER
python scripts/sync_jsfx.py
```

---

## Lessons Learned

See `docs/MISTAKEBAKED.md` for the full list. The expensive ones:

1. **Check the synth compiles before debugging data.** Cost: ~15 prompts.
2. **Look up the track listing before comparing songs.** Cost: ~5 prompts.
3. **Dump trace data before modeling envelopes.** Cost: 5 prompts per guess.
4. **Same driver family does not mean same byte format.** Cost: 3+ prompts per game.
5. **Test one variable at a time.** Changing RPP format + MIDI encoding + synth simultaneously made it impossible to isolate failures.

---

## Current Status

- **NSF pipeline**: 21 songs extracted. Fidelity is low — Rare's NSF driver diverges from in-game audio.
- **Trace pipeline**: Script built, Mesen capture exists (9,495 frames / 158s of Level 1). Golden-path end-to-end run needed.
- **APU2 SysEx path**: Code exists. Synth exists. Not yet verified end-to-end.
- **Console synth**: Syntax error fixed, CC decoders fixed.

---

## Related Projects

Part of the **ReapNES** ecosystem:
- Pipeline engine: NSFRIPPER — NSF/ROM → MIDI → REAPER for all NES games
- Website: [ReapNES](https://t3dy.github.io/ReapNES/) — per-game pages
- Synth R&D: ReapNES-Studio — JSFX synthesizer development

## Requirements

- **Python 3.10+** with `mido`, `numpy`, `py65`
- **Mesen 2** — NES emulator with Lua scripting for APU trace capture
- **REAPER v7+** (optional) — for production renders using JSFX synths

## License

Educational / archival use. Battletoads is a trademark of Rare Ltd. This project reconstructs audio data for preservation and study purposes.
