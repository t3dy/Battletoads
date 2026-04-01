# ReapNES -- NES Music Reverse Engineering Studio

**Extract, validate, and reproduce NES game music at frame-level fidelity**

**[Browse the documentation site →](https://t3dy.github.io/ReapNES/)**

---

## What This Project Does

ReapNES extracts music data directly from NES ROM files and converts it through a multi-stage pipeline: ROM parser to frame-level intermediate representation to MIDI with per-frame volume automation to REAPER projects, WAV audio, and MP4 video. Every extraction is validated against Mesen 2 APU traces -- frame-by-frame comparison against actual hardware register writes recorded from the emulator. Two complete Konami game soundtracks have been extracted so far, with a methodology designed to generalize across the NES library.

## Current Status

| Game | Tracks | Pulse Fidelity | Status |
|------|--------|----------------|--------|
| Castlevania 1 (1986) | 15/15 | 0 mismatches / 1792 frames | COMPLETE |
| Contra (1988) | 11/11 | 96.6% volume match | IN PROGRESS |
| 15+ Konami titles | 0 | Untested | OPEN |

## Architecture

```
 .nes ROM file
      |
      v
 +-----------+     +-----------+     +-------------+
 |  Parser   | --> |  Frame IR | --> | MIDI Export  |
 | (per-game)|     | (envelope |     | (CC11 auto-  |
 |           |     |  shaping) |     |  mation)     |
 +-----------+     +-----------+     +-------------+
                                           |
                              +------------+------------+
                              |            |            |
                              v            v            v
                          WAV render   REAPER .rpp   MP4 video
                          (APU synth)  (JSFX plugin) (w/ YouTube)
```

Three layers make up the system:

- **Engine layer** -- per-game parsers read the sound driver command stream from ROM. Each game gets its own parser because even games sharing a driver family differ in byte counts, percussion format, and ROM layout.
- **Data layer** -- the frame IR converts parsed events into per-frame hardware state (period, volume, duty cycle). Volume envelope shaping is dispatched through a `DriverCapability` schema so each game declares its own model (parametric, lookup table, or future types).
- **Hardware layer** -- output stages (MIDI export, WAV synth, REAPER project generator) consume the frame IR without needing to know which game produced it.

## Documentation

| Document | What It Covers |
|----------|----------------|
| [DRIVER_MODEL.md](docs/DRIVER_MODEL.md) | Konami Maezawa sound driver internals |
| [GAME_MATRIX.md](docs/GAME_MATRIX.md) | Per-game parameter matrix (mapper, DX bytes, percussion, envelopes) |
| [COMMAND_MANIFEST.md](docs/COMMAND_MANIFEST.md) | Full command byte reference ($00-$FF) |
| [INVARIANTS.md](docs/INVARIANTS.md) | Hard rules that must never be violated |
| [TRACE_WORKFLOW.md](docs/TRACE_WORKFLOW.md) | Step-by-step: capture a Mesen trace, validate, iterate |
| [RESEARCH_LOG.md](docs/RESEARCH_LOG.md) | Chronological record of discoveries and dead ends |
| [UNKNOWNS.md](docs/UNKNOWNS.md) | Open questions and unexplained behaviors |
| [CHECKLIST.md](docs/CHECKLIST.md) | Every musical parameter: what we model, what we skip, how to check |
| [NOTEDURATIONS.md](docs/NOTEDURATIONS.md) | Five systems that affect perceived note length |
| [CONTRAGOALLINE.md](docs/CONTRAGOALLINE.md) | How close the Contra extraction is and what remains |
| [CONTRACOMPARISON.md](docs/CONTRACOMPARISON.md) | What the Mesen trace proved vs pre-capture assumptions |
| [CONTRALESSONSTOCV1.md](docs/CONTRALESSONSTOCV1.md) | Lessons from Contra applied back to the CV1 pipeline |
| [KONAMITAKEAWAY.md](docs/KONAMITAKEAWAY.md) | High-level takeaways from two games on the same driver family |
| [MESENCAPTURE.md](docs/MESENCAPTURE.md) | Full Mesen 2 trace capture workflow |
| [HOWTOBEMOREFLEXIBLE.md](docs/HOWTOBEMOREFLEXIBLE.md) | Lessons for anticipating the unexpected in NES RE |
| [HOWTOREADACAPTURE.md](docs/HOWTOREADACAPTURE.md) | Guide to reading APU capture files (human and agentic) |

## Quick Start

```bash
# Identify a ROM -- reports mapper, period table, driver signature
PYTHONPATH=. python scripts/rom_identify.py <rom>

# Validate extraction against Mesen APU trace (CV1, 1792 frames)
PYTHONPATH=. python scripts/trace_compare.py --frames 1792

# Run the full pipeline: ROM to MIDI to WAV to MP4
PYTHONPATH=. python scripts/full_pipeline.py <rom> --game-name X

# Generate a REAPER project from extracted MIDI
python scripts/generate_project.py --midi <file> --nes-native -o <out>
```

## For ROM Hackers

### How to start on a new game

The methodology is trace-first: capture hardware ground truth before writing any parser code, then iterate against it. The full walkthrough is in [TRACE_WORKFLOW.md](docs/TRACE_WORKFLOW.md). The short version: identify the ROM, find a disassembly, capture a Mesen trace, parse one track, compare frame-by-frame, fix, repeat. Do not batch-extract until the reference track passes validation.

### Pick an unknown

There are dozens of Konami NES titles using variants of the Maezawa sound driver that no one has documented. The [UNKNOWNS.md](docs/UNKNOWNS.md) file lists open questions -- unexplained engine behaviors, untested games, and partially understood subsystems. If you have a Mesen trace or a disassembly for any Konami title from 1986-1992, that data is immediately useful.

### What we learned the hard way

Two complete extractions produced a detailed record of mistakes, false assumptions, and hard-won corrections. The [RESEARCH_LOG.md](docs/RESEARCH_LOG.md) covers the full chronology. The short version: the same driver family does not mean the same ROM layout; the same period table does not prove the same driver; automated tests miss systematic errors (an octave off shows zero mismatches); and surface similarity between games is the trap, not the shortcut.

## Project Structure

```
extraction/
  drivers/konami/           Parsers, frame IR, MIDI export, spec
  manifests/                Per-game structured state (JSON)
  traces/                   Mesen APU trace CSVs
  exports/midi/             Extracted MIDI files
scripts/
  rom_identify.py           ROM analysis and driver detection
  trace_compare.py          Frame-level validation vs APU trace
  full_pipeline.py          ROM to MIDI to WAV to MP4
  render_wav.py             Python NES APU synthesizer
  generate_project.py       REAPER .rpp project generator
studio/
  jsfx/                     ReapNES_APU.jsfx synth plugin
  reaper_projects/          Generated .RPP files
docs/                       Full documentation (see table above)
references/                 Annotated disassemblies
output/                     Rendered WAV and MP4 files
```

## Requirements

- **Python 3.10+**
- **mido** -- MIDI file I/O
- **numpy** -- WAV rendering and signal processing
- **Mesen 2** -- NES emulator with Lua scripting for APU trace capture
- **REAPER** (optional) -- for production-quality renders using the JSFX NES APU synth

## The Bigger Picture

The NES library contains hundreds of games with undocumented sound engines. Most NES music preservation relies on NSF rips that play back through the original code -- useful for listening, but opaque for analysis, arrangement, or remix. Extracting the actual musical data (notes, durations, envelopes, timing) requires reverse engineering each game's sound driver, and every driver has its own command format, byte layout, and volume model.

This project demonstrates a methodology that can generalize: trace-first validation against emulator hardware captures, per-game manifests that track verified facts separately from hypotheses, invariant-aware pipelines that catch systematic errors, and driver capability schemas that isolate per-game differences without accumulating hidden coupling. The Konami Maezawa family alone covers a significant portion of the late-1980s NES catalog. The tools and workflow documented here are designed to make each subsequent game faster than the last.
