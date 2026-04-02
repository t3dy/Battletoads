# Data Ontology: NES Music Extraction Pipeline

A comprehensive schema of every data entity, transformation, and
validation point from ROM disassembly to REAPER playback. This is the
single reference for understanding what data exists, where it flows,
and what each stage requires.

## HiroPlantagenet Decomposition

The pipeline has 7 intent atoms:

| # | Goal | Tag |
|---|------|-----|
| 1 | Parse ROM/NSF binary structures into driver-specific events | EXTRACTION |
| 2 | Capture real hardware APU state via Mesen traces | EXTRACTION |
| 3 | Convert per-frame APU state to musical MIDI events | PIPELINE |
| 4 | Build REAPER projects with synth plugins and inline MIDI | PIPELINE |
| 5 | Reproduce NES audio with hardware-accurate fidelity | CLASSIFICATION |
| 6 | Enable keyboard play with NES timbres on new compositions | PIPELINE |
| 7 | Validate output against ground truth at frame resolution | META-CONTROL |

**Conflicts:** Goals 5 (fidelity) and 6 (keyboard play) require
different synth modes. File playback needs CC-driven register replay;
keyboard play needs ADSR envelopes. Resolved by the dual-mode synth
contract (CC bypasses ADSR when file data arrives).

---

## Layer 1: Source Data

### 1.1 ROM File (.nes)

```
ENTITY: NES_ROM
FORMAT: iNES binary (.nes)
FIELDS:
  header.mapper:       int (0-255)   — memory mapper type
  header.prg_rom_size: int (bytes)   — program ROM size
  header.chr_rom_size: int (bytes)   — character ROM size
  header.mirroring:    enum          — horizontal | vertical | four_screen
  header.battery:      bool          — battery-backed SRAM
  header.region:       enum          — ntsc | pal | dual
  prg_data:            bytes         — program ROM (contains sound driver + music data)
  rom_sha256:          str           — identity hash
CREATED_BY: Game cartridge dump
CONSUMED_BY: ROM identification, driver-specific parser
VALIDATION: iNES magic bytes 4E 45 53 1A at offset 0
```

### 1.2 NSF File (.nsf)

```
ENTITY: NSF_FILE
FORMAT: NSF binary (.nsf)
FIELDS:
  total_songs:   int       — number of songs (1-based)
  starting_song: int       — default song number
  load_addr:     uint16    — where to load ROM data in CPU memory
  init_addr:     uint16    — INIT routine address
  play_addr:     uint16    — PLAY routine address (called at 60Hz)
  title:         str[32]   — game title (ASCII, null-padded)
  artist:        str[32]   — composer name
  bankswitch:    byte[8]   — bank mapping for $8000-$FFFF (4KB pages)
  rom_data:      bytes     — sound driver + music data
CREATED_BY: NSF ripper tools or manual extraction from ROM
CONSUMED_BY: NsfEmulator (py65 6502 CPU)
VALIDATION: NESM magic bytes at offset 0
NOTE: NSF playback may diverge from in-game audio (different init,
      missing game state, simplified driver). Mesen trace is ground truth.
```

### 1.3 Mesen APU Trace (.csv)

```
ENTITY: MESEN_TRACE
FORMAT: CSV with header (frame, parameter, value)
FIELDS PER ROW:
  frame:     int     — 60Hz frame number (NTSC)
  parameter: str     — register pseudo-address (e.g., "$4002_period")
  value:     int     — decoded register value
PARAMETERS:
  Pulse 1:   $4000_duty, $4000_vol, $4000_const, $4002_period, $4001_sweep
  Pulse 2:   $4004_duty, $4004_vol, $4004_const, $4006_period, $4005_sweep
  Triangle:  $4008_linear, $400A_period, $400B_length
  Noise:     $400C_vol, $400C_const, $400E_period, $400E_mode
  DPCM:      $4010_rate, $4011_dac, $4012_addr, $4013_len
CREATED_BY: Mesen 2 Lua capture script (polls emu.getState() per frame)
CONSUMED_BY: state_trace_ingest.py, trace_to_midi.py, trace_compare.py
VALIDATION: First row has header. Frame numbers monotonically increase.
GROUND TRUTH: This captures exactly what the NES APU produces during
  real gameplay. Every sweep oscillation, every volume micro-adjustment.
```

### 1.4 Disassembly

```
ENTITY: DISASSEMBLY
FORMAT: Annotated 6502 assembly text
FIELDS:
  address:     uint16   — ROM address
  opcode:      byte     — 6502 instruction
  operands:    bytes    — instruction operands
  annotation:  str      — human-readable comment
  label:       str      — symbolic label (e.g., "sound_cmd_routine_00")
KEY STRUCTURES TO FIND:
  - Pointer table:      address where song data pointers begin
  - Period table:       12-note frequency lookup (one octave)
  - Envelope tables:    volume decay curves (game-specific)
  - Command dispatch:   how the driver interprets music bytes
  - Percussion table:   drum trigger mappings
CONSUMED_BY: Human analysis, parser design, manifest authoring
NOTE: Not all games have disassemblies available. Check references/ first.
```

### 1.5 Track Listing

```
ENTITY: TRACK_LISTING
FORMAT: JSON (track_names.json per game)
FIELDS:
  game:   str          — game title
  source: str          — URL where listing was found
  tracks: dict[int, str] — NSF song number → track name
EXAMPLE:
  {"1": "Title", "2": "Interlude", "3": "Ragnarok's Canyon", ...}
CREATED_BY: Web search (KHInsider, VGMRips, Zophar's Domain)
CONSUMED_BY: Output file naming, Mesen trace segment matching
MANDATORY: Must be created BEFORE extraction begins. Prevents
  wrong-song mapping (Battletoads Song 2 ≠ Level 1).
```

---

## Layer 2: Extraction Models

### 2.1 Game Manifest

```
ENTITY: GAME_MANIFEST
FORMAT: JSON (extraction/manifests/{game}.json)
FIELDS:
  game:             str
  developer:        str
  year:             int
  mapper:           int
  sound_driver:     str         — driver family name
  driver_version:   str         — specific version
  channels_used:    list[str]   — ["pulse1", "pulse2", "triangle", "noise", "dpcm"]
  pointer_table:    hex_addr    — where song pointers begin in ROM
  command_format:   dict        — per-opcode byte counts and semantics
  period_table:     list[int]   — 12-note period values
  envelope_model:   str         — "parametric" | "lookup_table" | "unknown"
  envelope_tables:  list[list[int]]  — (if lookup_table)
  percussion_type:  str         — "inline" | "separate_channel" | "none"
  known_facts:      list[str]   — verified information
  hypotheses:       list[str]   — unverified assumptions
  fidelity_status:  dict        — per-pipeline-path quality scores
CREATED_BY: ROM analysis + disassembly reading
CONSUMED_BY: Parser initialization, frame IR configuration
VALIDATION: Every hypothesis must cite evidence source
```

### 2.2 Parsed Song Events

```
ENTITY: PARSED_SONG
FORMAT: Python dataclass (in-memory)
FIELDS:
  track_number:  int
  channels:      list[ParsedChannel]
    .name:         str
    .channel_type: str        — "pulse1" | "pulse2" | "triangle" | "noise"
    .events:       list[Event]
EVENT TYPES:
  NoteEvent:       pitch, octave, duration_frames, midi_note
  RestEvent:       duration_frames
  InstrumentChange: tempo, volume, duty, fade_start, fade_step, vol_env_index
  OctaveChange:    octave
  EnvelopeEnable:  enabled (bool)
  DrumEvent:       percussion trigger
  RepeatMarker:    count, target_address
  EndMarker:       (end of stream)
INVARIANT: Parser events use FULL duration. No staccato or envelope
  shaping. All temporal shaping is the frame IR's responsibility.
CREATED_BY: Game-specific parser (e.g., KonamiCV1Parser)
CONSUMED_BY: parser_to_frame_ir()
```

### 2.3 Frame IR

```
ENTITY: SONG_IR
FORMAT: Python dataclass (in-memory)
FIELDS:
  track_number: int
  channels:     list[ChannelIR]
    .name:          str
    .channel_type:  str
    .frames:        dict[int, FrameState]    — absolute frame → state

FRAME_STATE:
  frame:      int        — absolute frame number
  period:     int        — NES APU timer period (0 = silent)
  midi_note:  int        — converted MIDI note number (0 = silent)
  volume:     int        — 0-15 after envelope shaping
  duty:       int        — 0-3 (pulse only)
  sounding:   bool       — whether audio output should occur
CREATED_BY: parser_to_frame_ir() or trace_to_frame_ir()
CONSUMED_BY: midi_export, trace_compare, visualization
KEY PROPERTY: Every frame has a complete state. No gaps, no deltas.
```

### 2.4 State Trace (Parsed Mesen)

```
ENTITY: STATE_TRACE
FORMAT: Python dataclass (in-memory)
FIELDS:
  channel_states: dict[str, list[ChannelFrame]]
  total_frames:   int
  raw_changes:    list[dict]

CHANNEL_FRAME:
  frame:            int
  period:           int | None
  volume:           int | None      — 0-15
  duty:             int | None      — 0-3
  constant_volume:  bool
  sweep:            int | None
  linear_counter:   int | None      — (triangle)
  length_counter:   int | None
  mode:             int | None      — (noise: long/short)
CREATED_BY: load_state_trace()
CONSUMED_BY: trace_to_frame_ir(), trace comparison, analysis
NOTE: Sparse — only frames where something changed. Must interpolate
  for dense frame-by-frame comparison.
```

---

## Layer 3: Musical Encoding

### 3.1 NES APU Register Map

This is the hardware truth. Every other data entity is derived from this.

```
PULSE 1 ($4000-$4003):
  $4000[7:6]  Duty cycle (0-3: 12.5%, 25%, 50%, 75%)
  $4000[5]    Length counter halt / envelope loop
  $4000[4]    Constant volume flag (1=use volume, 0=use envelope divider)
  $4000[3:0]  Volume (if constant) or envelope period
  $4001[7]    Sweep enable
  $4001[6:4]  Sweep period (0-7)
  $4001[3]    Sweep negate
  $4001[2:0]  Sweep shift (0-7)
  $4002       Timer low (period bits 0-7)
  $4003[2:0]  Timer high (period bits 8-10)
  $4003[7:3]  Length counter load (also resets phase + restarts length counter)

PULSE 2 ($4004-$4007): Same layout as Pulse 1

TRIANGLE ($4008-$400B):
  $4008[7]    Length counter halt / linear counter control
  $4008[6:0]  Linear counter reload value
  $400A       Timer low
  $400B[2:0]  Timer high
  $400B[7:3]  Length counter load

NOISE ($400C-$400F):
  $400C[5]    Length counter halt / envelope loop
  $400C[4]    Constant volume flag
  $400C[3:0]  Volume or envelope period
  $400E[7]    Mode (0=long sequence, 1=short/metallic)
  $400E[3:0]  Period index (0-15, lookup table)
  $400F[7:3]  Length counter load

DPCM ($4010-$4013):
  $4010[7]    IRQ enable
  $4010[6]    Loop
  $4010[3:0]  Rate index (0-15)
  $4011[6:0]  Direct DAC load (7-bit, 0-127)
  $4012       Sample address (addr = $C000 + value * 64)
  $4013       Sample length (length = value * 16 + 1)

STATUS ($4015):
  [4] DMC active
  [3] Noise length counter > 0
  [2] Triangle length counter > 0
  [1] Pulse 2 length counter > 0
  [0] Pulse 1 length counter > 0
```

### 3.2 Period-to-Pitch Conversion

```
FORMULA:
  Pulse:    freq = 1789773 / (16 * (period + 1))
  Triangle: freq = 1789773 / (32 * (period + 1))
  MIDI:     note = round(69 + 12 * log2(freq / 440))

CONSTANTS:
  CPU_CLOCK = 1789773 Hz (NTSC)
  PULSE_DIVISOR = 16
  TRIANGLE_DIVISOR = 32 (one octave lower for same period)
  A4_FREQ = 440 Hz
  A4_MIDI = 69

MINIMUM PERIOD:
  Pulse:    period > 8 (below this = ultrasonic/silent)
  Triangle: period > 2

NOTE: Triangle produces frequency HALF that of pulse for same period
  (32-step vs 16-step sequencer). This is hardware fact. Triangle MIDI
  notes are naturally one octave lower.
```

### 3.3 MIDI CC Encoding Contract

```
CC11 (Expression / Volume):
  ENCODE: cc11 = min(127, nes_vol * 8)
  DECODE: nes_vol = min(15, floor(cc11 / 8 + 0.5))
  RANGE:  0-120 (NES 0-15)
  USAGE:  Pulse channels: per-frame volume envelope
          Triangle: always 127 (gate only, no volume control)
          Noise: not used (velocity-driven)

CC12 (Timbre / Duty Cycle):
  ENCODE: cc12 = [16, 32, 64, 96][duty]
  DECODE: duty = floor(cc12 / 32)
  RANGE:  16, 32, 64, 96 (NES duty 0, 1, 2, 3)
  USAGE:  Pulse channels only. Triangle and noise have no duty.

CC121 / CC123 (Reset):
  PURPOSE: Reset CC-driven mode, re-enable ADSR for keyboard play
  USAGE:  Sent at end of file or on channel reset
```

### 3.4 SysEx APU Register Format

```
PURPOSE: Lossless per-frame register state for APU2 synth replay
FORMAT:  F0 7D 01 <ch> <r0_lo> <r0_hi> <r1_lo> <r1_hi>
              <r2_lo> <r2_hi> <r3_lo> <r3_hi> <enable> F7
FIELDS:
  7D:       Non-commercial SysEx ID
  01:       Message type (APU frame)
  ch:       Channel index (0=P1, 1=P2, 2=Tri, 3=Noise)
  r0-r3:    4 register bytes, split into 7-bit pairs (MIDI safe)
  enable:   Channel enable bit from $4015
TIMING:     One SysEx per channel per frame = 4 messages per frame
            First message gets TICKS_PER_FRAME delta, rest get delta=0
CAPTURES:   ALL register state including sweep, mode, length counter,
            DPCM DAC — everything MIDI CCs cannot encode
```

---

## Layer 4: MIDI Output

### 4.1 MIDI File Structure

```
ENTITY: NES_MIDI
FORMAT: Type 1 MIDI (.mid), PPQ=480
TRACKS:
  Track 0: Metadata
    - set_tempo (128.6 BPM default, or game-specific)
    - time_signature (4/4)
    - text: Game name, song name, source, track number
  Track 1: Pulse 1 (MIDI channel 0)
    - program_change: 80 (Lead 1 Square)
    - note_on/note_off: period-change boundaries
    - CC11: volume envelope (per frame when volume changes)
    - CC12: duty cycle (per frame when duty changes)
  Track 2: Pulse 2 (MIDI channel 1)
    - program_change: 81 (Lead 2 Sawtooth)
    - (same CC structure as Pulse 1)
  Track 3: Triangle (MIDI channel 2)
    - program_change: 38 (Synth Bass 1)
    - CC11: always 127 (gate)
    - note_on/note_off: linear counter boundaries
  Track 4: Noise (MIDI channel 3)
    - Drum mapping: period 0-4→42(hat), 5-8→38(snare), 9+→36(kick)
    - Velocity = vol * 8
    - Duration capped at 12 frames or <25% of initial volume
  Track 5: APU Registers (SysEx)
    - Raw register state per frame per channel
    - Used by APU2 synth for hardware-accurate replay

TIMING:
  TICKS_PER_FRAME = 16 (at 128.6 BPM with PPQ=480)
  Note boundaries = period register changes
  CC11 emitted on every frame where volume changes
  CC12 emitted on every frame where duty changes
```

---

## Layer 5: REAPER Project

### 5.1 RPP Structure

```
ENTITY: REAPER_PROJECT
FORMAT: .rpp (plaintext REAPER v7)
COMPONENTS:
  Header:     Full ~100-line header (tempo, sample rate, routing)
  Per Track:  4 tracks (Pulse 1, Pulse 2, Triangle, Noise)
    - Name, color (PEAKCOL)
    - MIDI routing (REC 5088 = all MIDI devices, all channels)
    - FXCHAIN with ReapNES synth (Console or APU2)
    - Slider values (38 or 19 depending on synth)
    - Channel Mode (slider 33/1): routes MIDI channel to NES channel
    - Keyboard Mode (slider 34/2): remaps keyboard to track channel
    - MIDI item with HASDATA (inline E/X events from midi_track_to_events)

INLINE MIDI FORMAT:
  HASDATA 1 {ppq} QN    — declares inline data, PPQ, quarter note base
  CCINTERP 32            — CC interpolation mode
  E {delta} {hex_bytes}  — channel messages (note, CC, program change)
  E 0 ff 2f 00           — end of track marker

NOTE: Do NOT include X (meta) events — REAPER's parser can choke on
  them, causing empty items. Only emit E lines for channel messages.
```

### 5.2 Synth Configurations

```
CONSOLE SYNTH (ReapNES_Console.jsfx):
  38 sliders — full ADSR per channel, mix controls, sweep unit
  Dual mode: CC-driven (file) + ADSR (keyboard)
  Game-specific presets in GAME_ADSR dict
  USE FOR: Keyboard play, live performance, Bach mashups

APU2 SYNTH (ReapNES_APU2.jsfx):
  19 sliders — channel mode, keyboard mode, ADSR per channel
  SysEx replay: reads Track 5 register data for hardware accuracy
  USE FOR: File playback (maximum fidelity), YouTube renders

SLIDER ASSIGNMENT (Console):
  Index 0-7:   Pulse 1 (duty, vol, enable, ADSR, duty_end)
  Index 8-15:  Pulse 2 (same layout)
  Index 16-18: Triangle (enable, attack, release)
  Index 19-24: Noise (period, mode, vol, enable, attack, decay)
  Index 25-26: Vibrato (rate, depth)
  Index 27-30: Mix (P1, P2, Tri, Noise) — each 0.0-1.0
  Index 31:    Master Gain (0.0-1.0)
  Index 32:    Channel Mode (0-4)
  Index 33:    Keyboard Mode (0-1)
  Index 34-37: P1 Sweep (enable, period, direction, shift)
```

---

## Layer 6: Dual-Mode Usage

### 6.1 File Playback Path (Fidelity)

```
INPUT:  MIDI file with CC11/CC12 + SysEx
SYNTH:  APU2 (preferred) or Console
MODE:   CC-driven — ADSR bypassed when CC11/CC12 arrives
GOAL:   Reproduce original game audio as accurately as possible
OUTPUT: Audio matching NES hardware within quantization limits
```

### 6.2 Keyboard Play Path (Composition)

```
INPUT:  MIDI keyboard or controller
SYNTH:  Console (preferred — has full ADSR controls)
MODE:   ADSR — shapes notes with attack/decay/sustain/release
GOAL:   NES-authentic timbres for new compositions
OUTPUT: NES-style audio responsive to live performance dynamics
PRESETS: GAME_ADSR dict provides per-game starting points
  Castlevania: punchy attack, short decay, low sustain
  Mega Man:    bright duty, long decay, high sustain
  Metroid:     slow attack, wide duty, ambient release
```

### 6.3 Bach Mashup Path (Hybrid)

```
INPUT:  Classical MIDI (Bach BWV scores) + NES stage presets
SYNTH:  Console with per-stage duty/mood configuration
MODE:   ADSR for keyboard-style playback of classical scores
GOAL:   "What if Bach wrote for the NES?"
OUTPUT: Chiptune arrangements of classical music
```

---

## Layer 7: Validation & Quality

### 7.1 Trace Comparison

```
ENTITY: FIDELITY_REPORT
FIELDS:
  game:           str
  song:           str
  frames_compared: int
  per_channel:    dict[str, ChannelReport]
    .pitch_mismatches:    int
    .volume_mismatches:   int
    .duty_mismatches:     int
    .sounding_mismatches: int
    .first_mismatch_frame: int
  overall_score:  float (0-100%)
  recommendation: str   — "USE NSF" | "USE TRACE" | "NEEDS DRIVER WORK"
CREATED_BY: trace_compare.py
CONSUMED_BY: Pipeline routing decision
THRESHOLD: <80% → switch to trace pipeline
```

### 7.2 Pre-Delivery Checklist

```
[ ] JSFX synth compiles without errors
[ ] RPP has HASDATA (not FILE reference)
[ ] MIDI has notes on all expected channels
[ ] CC11/CC12 values decode correctly (round-trip test)
[ ] WAV preview is non-silent (amplitude > threshold)
[ ] Track names match game (not generic Song_N)
[ ] Human ear-check against MP3 reference or game audio
```

### 7.3 Per-Game Fidelity Matrix

```
ENTITY: FIDELITY_MATRIX
PER PARAMETER:
  period:          captured? | encoded how? | synth handles? | lossless?
  volume:          captured? | encoded how? | synth handles? | lossless?
  duty:            captured? | encoded how? | synth handles? | lossless?
  sweep:           captured? | encoded how? | synth handles? | lossless?
  noise_mode:      captured? | encoded how? | synth handles? | lossless?
  length_counter:  captured? | encoded how? | synth handles? | lossless?
  phase_reset:     captured? | encoded how? | synth handles? | lossless?
  dpcm_dac:        captured? | encoded how? | synth handles? | lossless?
  dpcm_sample:     captured? | encoded how? | synth handles? | lossless?
COVERAGE SCORE: (parameters_captured * lossless_factor) / total_parameters
```

---

## Data Flow Summary

```
ROM/NSF/Trace ──→ Extraction ──→ Frame IR ──→ MIDI+SysEx ──→ RPP ──→ REAPER
     │                │              │              │            │
     │                │              │              │            ├─ File playback
     │                │              │              │            │  (APU2 SysEx)
     │                │              │              │            │
     │                │              │              │            └─ Keyboard play
     │                │              │              │               (Console ADSR)
     │                │              │              │
     │                │              │              └─ Bach mashups
     │                │              │                 (Console + classical MIDI)
     │                │              │
     │                │              └─ trace_compare (validation)
     │                │
     │                └─ Manifest (game-specific knowledge)
     │
     └─ Track listing (web search, community sources)
```

Every arrow is a testable transformation. Every entity has a defined
schema. Every parameter has a known capture/encode/decode path. When
something sounds wrong, trace the data through each arrow until you
find the mismatch.
