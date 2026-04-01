# NSF to MIDI Pipeline

## What It Does

Converts any NES NSF file into playable REAPER projects with
full musical scoring — notes, volume envelopes, duty cycle changes,
and drum patterns — using the same ReapNES_APU.jsfx synth plugin
that the Castlevania pipeline produces.

## How It Works

### Stage 1: 6502 Emulation (nsf_player.py / nsf_to_reaper.py)

The NSF file contains the actual NES sound driver code extracted
from the game ROM. We run it on a py65 6502 CPU emulator:

```
1. Load NSF data at the load address ($9000 for Mega Man)
2. Call INIT(song_number) — the driver sets up the song
3. Call PLAY() 60 times per second — the driver processes one frame
4. After each PLAY call, capture all APU register values ($4000-$4017)
5. Record: which frame, which register, what value
```

This produces a frame-level register dump — identical to what
a Mesen APU trace captures, but without needing to run the game.

### Stage 2: Register-to-MIDI Conversion

The APU registers map directly to musical parameters:

```
$4000 bits 7-6: Pulse 1 duty cycle    → CC12 (timbre)
$4000 bits 3-0: Pulse 1 volume        → CC11 (expression)
$4002-$4003:    Pulse 1 period         → MIDI note number
$4004-$4007:    Same for Pulse 2
$4008:          Triangle linear counter → note duration
$400A-$400B:    Triangle period         → MIDI note number
$400C:          Noise volume            → drum velocity
$400E:          Noise period + mode     → drum type (hi-hat/snare/kick)
```

Each frame's register state becomes MIDI events:
- Period changes → note on/off events
- Volume changes → CC11 (expression) automation
- Duty cycle changes → CC12 automation
- Noise hits → drum note events with GM mapping

### Stage 3: MIDI File Assembly

The MIDI file has 5 tracks matching the CV1 format:

```
Track 0: Metadata
  - Tempo, time signature
  - Game name, song name, source info
  - Loop markers

Track 1: Square 1 [lead]
  - Channel 0, Program 80
  - Notes + CC11 (volume envelope) + CC12 (duty cycle)

Track 2: Square 2 [harmony]
  - Channel 1, Program 81
  - Notes + CC11 + CC12

Track 3: Triangle [bass]
  - Channel 2, Program 38
  - Notes + CC11

Track 4: Noise [drums]
  - Channel 3
  - GM drum mapping (36=kick, 38=snare, 42=hi-hat)
```

### Stage 4: REAPER Project Generation (generate_project.py)

The existing project generator creates a proper .rpp file:

```
- RPP v7 format with GUIDs
- 4 named tracks with color coding
- FXCHAIN per track with ReapNES_APU.jsfx loaded
- Slider parameters: duty cycle, volume, enable, channel mode
- MIDI item referencing the generated .mid file
- Correct tempo and time signature
```

## The Command

```bash
# One song:
python scripts/nsf_to_reaper.py game.nsf 3 90 -o output/Game/

# All songs:
python scripts/nsf_to_reaper.py game.nsf --all -o output/Game/ \
    --names "Stage Select,Cut Man,Guts Man,..."

# Then regenerate proper REAPER projects:
for midi in output/Game/midi/*.mid; do
    python scripts/generate_project.py --midi "$midi" --nes-native \
        -o "output/Game/reaper/$(basename ${midi%.mid}.rpp)"
done
```

## What You Get

For each song:
- `.mid` — 4-track MIDI with CC11/CC12 automation
- `.rpp` — REAPER project with ReapNES synth loaded
- `.wav` — Preview render (optional)

Open the .rpp in REAPER → hit play → hear NES-accurate audio
with full per-frame envelope detail. Edit notes in piano roll.
Change duty cycles. Remix.

## Validated On

- **Castlevania 1**: 15 tracks (original ROM parser pipeline)
- **Contra**: 11 tracks (ROM parser pipeline)
- **Mega Man 1**: 16 tracks (NSF emulator pipeline) — NEW
- **Bionic Commando**: 20 tracks (NSF emulator pipeline) — NEW

The NSF pipeline produces output structurally identical to the
ROM parser pipeline. Same MIDI format, same REAPER project format,
same synth plugin. The only difference is the source: ROM parser
reads game data directly, NSF emulator runs the driver code.
