---
description: RPP generation rules — Console synth, keyboard input, CC fidelity
globs:
  - "scripts/generate_project.py"
  - "scripts/build_projects.py"
  - "Projects/**"
  - "studio/reaper_projects/**"
---

# REAPER Project Requirements

## The Only Way to Make RPP Files

```bash
python scripts/generate_project.py --midi <midi_file> --nes-native -o <output.rpp>
python scripts/build_projects.py --force   # rebuild all Projects/
```

NEVER write RPP files manually. NEVER edit RPP files by hand.

## Synth Plugin

Target: `ReapNES Studio/ReapNES_Studio.jsfx` (unified synth, ~40 sliders).
Until the merge is complete, use `ReapNES Studio/ReapNES_Console.jsfx`.

The unified synth design (docs/SYNTHMERGE.md):
- Three-priority input cascade: SysEx → CC11/CC12 → ADSR keyboard
- Visual console UI with animated knobs for video recording
- Per-game presets (Battletoads, Castlevania, Contra, etc.)
- One plugin for all modes — auto-detects input type

## RPP Structure (derived from known-good Console_Test.rpp)

### Full Header Required

The RPP header MUST include ~100 lines matching REAPER's own saved format:
ENVATTACH, SAMPLERATE 44100, METRONOME, RECORD_CFG, RENDER_CFG,
MASTERPLAYSPEEDENV, TEMPOENVEX, PROJBAY, etc.

Do NOT use a minimal header. The full header is required for proper
audio/MIDI graph initialization. Without it, keyboard input silently fails.

### Track Fields (ALL required)

```
PANLAWFLAGS 3         — pan law (missing = broken panning)
SHOWINMIX 1 0.6667 0.5 1 0.5 0 0 0  — mixer visibility
FIXEDLANES 9 0 0 0 0  — lane config
SEL {0|1}             — track selection (first track = 1)
REC {0|1} 5088 1 0 0 0 0 0  — MIDI input (see below)
TRACKHEIGHT 0 0 0 0 0 0 0
INQ 0 0 0 0.5 100 0 0 100
WNDRECT 24 52 700 560  — in FXCHAIN (FX window size)
```

### REC Line: CRITICAL

```
REC {armed} 5088 1 0 0 0 0 0
```

- 5088 = 4096 (MIDI) + (31 << 5) (all devices) + 0 (all channels)
- **ALWAYS use 5088**, even when armed=0.
- If input=0 on an unarmed track, REAPER forgets MIDI routing.
  When the user later arms it, it defaults to audio input. Keyboard broken.

### Per-Track Slider Config (Console, 38 sliders)

```
Slider 33 (index 32): Channel Mode — 0=P1, 1=P2, 2=Tri, 3=Noise
Slider 34 (index 33): Keyboard Mode — ALWAYS 1 (ON)
```

Multi-track projects: each track gets its own channel mode (0-3).
NEVER use Full APU (4) in multi-track. Full APU is for single-track generic only.

## What the MIDI Must Contain

NSF-extracted MIDIs (ground truth):
- Track 0: metadata (tempo 128.6 BPM, game name, song name)
- Track 1: Square 1 (ch 0) with CC11 (volume 0-127) and CC12 (duty 0-3)
- Track 2: Square 2 (ch 1) with CC11 and CC12
- Track 3: Triangle (ch 2) with CC11 (gate only, always 127)
- Track 4: Noise (ch 3) with velocity-driven envelope (no CC11)

CC11 provides per-frame volume (4-5 updates per note). This IS the envelope.
CC12 provides per-frame duty cycle. This IS the timbre.

## What Breaks Projects (learned from CV1, Contra, ReapNES-Studio)

- Minimal RPP header → keyboard silently fails
- REC 0 0 on unarmed tracks → keyboard broken when user arms later
- Missing PANLAWFLAGS/SHOWINMIX/FIXEDLANES → REAPER layout glitches
- ReapNES_APU instead of Console → no ADSR, no keyboard mode
- Full APU mode on multi-track → all 4 channels play on every track
- ADSR overriding CC11 → file playback ignores ground-truth envelopes
- SOURCE MIDIPOOL → items appear but produce no audio (use SOURCE MIDI)
