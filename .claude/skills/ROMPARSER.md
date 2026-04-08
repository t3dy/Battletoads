---
name: rom-parser
description: Reverse engineer a NES ROM's music data by triangulating NSF emulation, Mesen trace captures, and fan MIDI references to locate pitch, rhythm, envelope, and sequence data. Driver-agnostic — adapts to any encoding scheme.
---

# ROMPARSER

Build a ROM song data parser for any NES game by systematically locating
where musical parameters live in the ROM and how the driver interprets them.

Every NES game encodes music differently. This skill does NOT assume a specific
driver format. Instead it triangulates from multiple evidence sources to discover
the encoding, then validates each hypothesis before moving on.

## Evidence Sources (Ranked by Trust)

```
SOURCE              TRUST FOR PITCH    TRUST FOR RHYTHM    TRUST FOR ENVELOPE
Mesen trace         AFTER transpo fix  HIGH (frame-level)  HIGH (per-frame vol)
ROM song data       HIGHEST (intent)   NEEDS DECODING      NEEDS DECODING
NSF emulation       HIGH               HIGH                HIGH
Fan MIDI            HIGH (pitch only)  LOW (human guess)   NONE
Fan MP3/recording   CONFIRMS by ear    CONFIRMS by ear     CONFIRMS by ear
```

**Key rule:** Fan MIDIs have good pitches but unreliable rhythm. Use them to
CONFIRM pitch hypotheses, never as a rhythm source. When a fan MIDI pitch
matches your ROM parse, that's strong evidence your parse is correct.

## Phase 0: Pre-Flight

Before touching any code, gather your evidence sources.

### 0A. Inventory Available Evidence

```
[ ] ROM file path and iNES header (mapper, PRG size, CHR size)
[ ] NSF file (if available) — path and track listing
[ ] Mesen trace capture (if available) — path, frame count, clean/SFX?
[ ] Fan MIDI (if available) — path, track count, which tracks are which
[ ] Fan MP3/YouTube (if available) — for ear-checking
[ ] Existing disassembly (check references/ directory)
[ ] Existing manifest (check extraction/manifests/)
```

### 0B. Record What You Know vs What You're Guessing

Create or update `extraction/manifests/<game>.json` with status markers:

```json
{
  "game": "<name>",
  "status": "DISCOVERY",
  "rom_layout": { "mapper": null, "status": "unknown" },
  "period_table": { "address": null, "status": "unknown" },
  "note_encoding": { "status": "unknown" },
  "transposition": { "status": "unknown" },
  "duration_encoding": { "status": "unknown" },
  "envelope_model": { "status": "unknown" },
  "song_pointers": { "status": "unknown" },
  "command_set": { "status": "unknown" }
}
```

Every field starts as "unknown" and gets promoted to "hypothesis" then
"verified" as evidence accumulates. Never skip from unknown to verified.

## Phase 1: DISCOVERY — Find the Driver

Invoke these finder skills in parallel where possible:

### 1A. LOOKUPTABLEFINDER — Find the Period Table

The period table is the Rosetta Stone. Every driver has one.

```
Method: Scan PRG ROM for sequences of decreasing 16-bit LE values where
adjacent ratios approximate 2^(1/12) = 1.05946.

Expected: 48-72 entries (4-6 octaves), values 56-3420.
NTSC standard: C2=1710, C3=854, C4=427, C5=213, C6=106.

Validation: If you have an NSF, extract a known note's period from the
trace and confirm it appears in the table.
```

Update manifest: `period_table.address`, `period_table.entries`, `period_table.status = "verified"`

### 1B. COMMANDFINDER — Decode the Command Set

Find the driver's dispatch table and decode every command.

```
Method:
1. Find the main play routine (called from NMI)
2. Find where it dispatches on command bytes (ASL A + TAX + LDA table,X pattern)
3. Read the dispatch table to get all handler addresses
4. For each handler, count INY instructions = parameter count
5. Identify target RAM addresses from STA instructions

Output: A table of CMD byte, param count, handler address, effect, category.
```

**Critical:** Get parameter counts RIGHT. A wrong count desynchronizes the
entire data stream (every byte after the error is misinterpreted).

### 1C. SEQUENCEFINDER — Find Song Pointers

```
Method:
1. If NSF exists: trace the init routine (song number in A → channel pointers)
2. If no NSF: search for pointer table patterns near the period table
3. For the target song, extract per-channel data start addresses

Output: Channel pointers for the target song.
```

## Phase 2: TRIANGULATION — Decode Note Encoding

This is the core of the skill. Use multiple evidence sources to figure out
how the driver encodes notes, durations, and envelopes.

### 2A. PITCHFINDER — Hypothesis-Driven Note Decoding

**Step 1: Generate a pitch hypothesis from ROM data**

Read the first ~64 bytes of one channel's song data. Separate commands
(using param counts from Phase 1) from potential note bytes.

Hypothesize: "Bytes in range [X, Y] are notes. Note index = byte - X."

**Step 2: Check hypothesis against fan MIDI**

If a fan MIDI exists, extract the first 8-16 note pitches from the
corresponding track. These are your search targets.

```
Fan MIDI says the bass riff starts: E2 E2 E2 D2 E2 E2 E2 G2

Period table says: E2 = index 4, D2 = index 2, G2 = index 7

Search ROM data for bytes that, when decoded, produce indices 4,4,4,2,4,4,4,7
(or those indices plus some constant transposition offset).

If byte 0x85 appears where E2 should be: 0x85 - 0x81 = 4 = E2. Base = 0x81.
If byte 0x45 appears instead: 0x45 - 0x41 = 4 = E2. Base = 0x41.
```

**Step 3: Check for transposition**

If the raw index doesn't match the expected note, suspect transposition.

```
Trace says period 678 at this position. Period table says 678 = E3 = index 16.
Fan MIDI says E2 = index 4. Difference: 16 - 4 = 12 = one octave transposition.

Search the preceding command bytes for a "set transposition" command that
writes 12 (or 0x0C) to a RAM location. That command is the transposition setter.

Verify: Find all transposition commands in the song data. Apply them while
parsing. Do the resulting notes now match the fan MIDI for ALL positions,
not just the first few?
```

**Step 4: Validate against Mesen trace**

```
Parse your note sequence with transposition applied.
For each note, compute: final_index = raw_index + transposition
Look up period = period_table[final_index]
Compare against trace period at the corresponding time position.

Match? → Hypothesis confirmed.
Mismatch? → Check for arpeggio, vibrato, or sweep modifying the period.
```

Update manifest: `note_encoding.base`, `note_encoding.rest_byte`,
`transposition.register`, `transposition.commands`, all with `status = "verified"`

### 2B. RHYTHMFINDER — Decode Duration Encoding

Duration encoding varies wildly across drivers. Common schemes:

```
Scheme A: Duration byte follows every note (Rare driver, many others)
  note_byte duration_byte note_byte duration_byte ...

Scheme B: Duration command sets "current duration" for subsequent notes
  CMD_DURATION 0x06 note note note CMD_DURATION 0x04 note note ...

Scheme C: Duration encoded in the note byte itself (Konami Maezawa)
  High nibble = pitch, low nibble = duration

Scheme D: Duration lookup table indexed by a nibble or byte
  Duration_frames = table[duration_index] * tempo_multiplier
```

**How to determine which scheme:**

1. Parse a section of note bytes (identified in 2A)
2. Look at the bytes between/after notes
3. If every note is followed by a small value (1-32): Scheme A
4. If notes appear in clusters with no intervening bytes: Scheme B or C
5. Cross-reference with trace timing:
   - Measure frame gaps between note attacks in the trace
   - The duration values you're seeing should, when multiplied by the
     tempo factor, produce those frame gaps

**Tempo system:** Find the play routine's frame accumulator.
```
Common pattern:
  LDA accumulator
  CLC
  ADC speed
  STA accumulator
  BCC skip_music    ; only process music when accumulator overflows

Effective tempo: music ticks per frame = speed / 256
Frames per tick: 256 / speed
```

**Validation:** Parse 10 consecutive notes with durations. Compute expected
frame count for each. Compare against trace note-attack frame gaps.
Tolerance: +/- 1 frame (rounding).

Update manifest: `duration_encoding.scheme`, `duration_encoding.tempo_address`,
`duration_encoding.status = "verified"`

### 2C. ENVELOPEFINDER — Decode Volume Envelopes

```
Method:
1. Find the command that sets envelope parameters (usually 1-3 param bytes)
2. Find where the driver writes to APU volume registers ($4000, $4004, $400C)
3. Trace backwards: is the volume coming from a lookup table or computed?

If lookup table:
  - Find the table in ROM (array of values 0-15)
  - Determine how the envelope command's parameter indexes into this table
  - Extract all envelopes

If parametric:
  - Determine the parameters (attack level, decay rate, sustain level, release)
  - Find the per-frame update routine
  - Document the math

Validation: Extract the envelope for one note. Compute per-frame volume
values. Compare against Mesen trace $4000 volume bits for that note.
Should match exactly.
```

Update manifest: `envelope_model.type`, `envelope_model.table_address` or
`envelope_model.parameters`, `envelope_model.status = "verified"`

## Phase 3: PARSING — Build the Parser

Only after Phases 1-2 have produced verified hypotheses for note encoding,
duration, and basic envelope.

### 3A. Parser Architecture

Follow the proven CV1/Contra pattern:

```python
class RareParser:  # or CapcomParser, SunsoftParser, etc.
    """Parse ROM song data for <game> using the <family> driver."""

    def parse_track(self, song_id: int) -> ParsedSong:
        """Parse all channels for the given song."""
        pointers = self._get_channel_pointers(song_id)
        channels = []
        for ch_name, addr in pointers.items():
            events = self._parse_channel(addr, ch_name)
            channels.append(ChannelData(name=ch_name, events=events))
        return ParsedSong(track_number=song_id, channels=channels)

    def _parse_channel(self, start_addr, channel) -> list[Event]:
        """Walk the byte stream, dispatch commands, emit events."""
        ptr = start_addr
        transposition = 0
        current_duration = 0  # or whatever the scheme uses
        call_stack = []       # for subroutine calls
        events = []

        while not halted:
            byte = self.rom[ptr]; ptr += 1

            if byte >= NOTE_BASE:
                # Note event
                raw_index = byte - NOTE_BASE
                final_index = raw_index + transposition
                midi_note = period_index_to_midi(final_index)
                duration = self._read_duration(ptr)  # scheme-dependent
                events.append(NoteEvent(...))

            elif byte == REST_BYTE:
                duration = self._read_duration(ptr)
                events.append(RestEvent(...))

            else:
                # Command
                self._handle_command(byte, ptr, ...)

        return events
```

**Invariants:**
- Parser emits **full-duration events**. No staccato, no envelope shaping.
- All temporal shaping is the Frame IR's responsibility.
- Parser tracks transposition, current envelope, current duration state.
- Parser follows subroutine calls (push return address, jump to target).
- Parser follows jumps (unconditional pointer change).
- Parser detects loops (jump back to earlier address = song loop point).

### 3B. Subroutine/Pattern Handling

Many drivers (including Rare) use subroutine calls to reuse patterns.

```
CMD_CALL target_addr:
  push current_ptr + param_size to call_stack
  ptr = target_addr

CMD_RETURN:
  ptr = call_stack.pop()

CMD_JUMP target_addr:
  ptr = target_addr  (no push, this is a goto)
```

**Loop detection:** If a JUMP targets an address we've already visited,
that's the song loop point. Record it and stop parsing (or parse one
more iteration to confirm).

**Nesting depth:** Most drivers support 1-2 levels. Track call depth
and bail if it exceeds 4 (probable parse error).

### 3C. Frame IR Generation

After parsing, convert events to per-frame state:

```
ParsedSong
  → parser_to_frame_ir(song, driver_capability)
  → SongIR with FrameState per frame per channel

FrameState:
  frame: int
  period: int          (from period table lookup)
  midi_note: int       (computed from period)
  volume: int (0-15)   (from envelope model)
  duty: int (0-3)      (from duty command or envelope)
  sounding: bool       (volume > 0 and note active)
```

The Frame IR is where envelope shaping happens. The parser gives you
"E2 for 16 ticks with envelope 3". The Frame IR says "frame 0: vol=15,
frame 1: vol=12, frame 2: vol=9, ..." using the envelope table.

## Phase 4: VALIDATION — Prove It Works

> **CRITICAL: Zero parse errors is a STRUCTURAL milestone, not a SEMANTIC one.**
> Parser output is a hypothesis until execution semantics validation passes.
> Do not promote parsed notes to MIDI or claim musical correctness from
> parser alignment alone.

### Gate A: Parser Alignment (STRUCTURAL)

```
All channels parse with zero desync.
Command boundaries, subroutine calls, and variable-width events are
correctly partitioned. Loop points detected.

This gate proves: bytes are correctly read.
This gate does NOT prove: pitches, durations, or envelopes are correct.

Label: "parser-aligned" (structural milestone only)
```

### Gate B: Execution Semantics Validation (SEMANTIC — required)

**This gate MUST pass before any musical claims are made.**

Build a frame-level simulator from parsed events + driver semantics:

```
1. Simulate tempo accumulator (exact 8-bit overflow, carry-triggers-tick)
2. Simulate duration counters (decrement per tick, advance on zero)
3. Simulate pitch modulation (arpeggio, vibrato, sweep per frame)
4. Simulate volume envelopes (per-frame volume from envelope model)
5. Simulate duty cycle state
6. Compare simulated per-frame state against Mesen trace
7. Produce mismatch taxonomy report

Required artifacts:
  - Parsed event stream
  - Simulated frame-state trace
  - Comparison report against Mesen trace
  - Mismatch taxonomy (tempo drift / duration error / arpeggio /
    envelope / transposition / alignment)

PASS: Period matches trace on 90%+ sounding frames,
      volume matches 80%+, note boundaries within ±1 frame
FAIL: Diagnose by mismatch category, fix simulator or parser, rerun

Label: "semantics-validated" (semantic milestone)
```

Anti-patterns this gate catches:
- Parsed G6 that never sounds as G6 (arpeggio transposes it down)
- Duration totals off by 1.5x (tempo accumulator not modeled)
- Notes that parse correctly but play at wrong times
- Envelopes that parse as IDs but produce wrong volume shapes

### Gate C: Pitch Triangulation (Fan MIDI cross-check)

```
Compare parsed+validated pitches against fan MIDI track.
PASS: 90%+ pitch match on first 20-30 notes
FAIL: < 80% → recheck transposition, note encoding base, period table
```

### Gate D: Frame IR + Full Comparison

```
Generate Frame IR from validated events.
Run trace_compare.py:
  PYTHONPATH=. python scripts/trace_compare.py \
    --game <game> --track <n> --frames <range>

Reports: pitch_match%, volume_match%, sounding_match% per channel.
First mismatch location for debugging.
```

### Gate E: Ear Check (User)

```
Export MIDI from Frame IR.
Generate REAPER project via generate_project.py.
Play in REAPER with ReapNES synth.
User compares against game audio (NSF or recording).

PASS: "Sounds right" from user
FAIL: Note which aspect is wrong (pitch, rhythm, volume, timbre)
      and return to the appropriate finder skill

Label: "trusted" / "production-ready"
```

See `session_protocol.md` Execution Semantics Checklist for the 10-step validation checklist.

## Phase 5: MULTI-CHANNEL — Extend to All Channels

Once one channel passes all gates:

1. Parse remaining melodic channels (pulse 1, pulse 2, triangle)
2. Each may have different transposition, different envelope assignments
3. Triangle has hardware differences (no volume control, 1 octave lower)
4. Parse noise/drums channel (often different encoding entirely)
5. Run validation gates on each channel independently

## Triangulation Strategies

When you're stuck, use these strategies to triangulate:

### Strategy 1: Known-Pitch Search

```
You know (from fan MIDI) that position N should be G2 (period 1141).
Trace confirms period 1141 appears at frame F.
Search the ROM data near the channel pointer for bytes that could
produce index 7 (G2) after some transformation.

If you find 0x88 and 0x88 - 0x81 = 7 → note base is 0x81.
If you find 0x47 and 0x47 - 0x40 = 7 → note base is 0x40.
```

### Strategy 2: Duration Bracketing

```
Trace says note N lasts 17 frames, note N+1 lasts 9 frames.
If tempo tick = 1 frame: look for duration bytes 17, 9.
If tempo tick = 2 frames: look for bytes ~8, ~4.
If tick = 3 frames: ~6, ~3.

Try each hypothesis. Only one will produce consistent results across
multiple notes.
```

### Strategy 3: Command Boundary Detection

```
You know notes are bytes >= 0x81. Between note clusters, you see
bytes < 0x80 that are commands.

Unknown: does byte 0x05 take 0 or 1 parameters?
Test both: parse forward with 0 params and with 1 param.
Only one interpretation will leave the stream aligned so that the
next note byte falls where the trace says a note should start.
```

### Strategy 4: Cross-Channel Correlation

```
If P1 and P2 play in unison for a section, their note bytes should
be the same (or differ by a constant transposition offset).
Parse both channels and check if their note patterns align where
the trace shows unison passages.
```

### Strategy 5: Envelope Shape Fingerprinting

```
The trace shows volume shape: 15, 12, 9, 6, 3, 0 (linear 3-step decay).
Search ROM for the byte sequence: 0F 0C 09 06 03 00.
If found: that's the envelope table. The command that references this
table's index is the envelope-set command.
```

### Strategy 6: NSF A/B Comparison

```
Play the NSF in an emulator. Record the first 10 seconds of audio.
Parse your ROM data and synthesize the same section.
A/B compare the waveforms. Any pitch or timing difference reveals
a parsing error in that specific region of the data.
```

## Artifact Formats

### Manifest (extraction/manifests/<game>.json)

Every field has a `status` marker: `"unknown"`, `"hypothesis"`, `"verified"`.
Hypotheses include evidence notes. Verified fields include validation method.

### Frame IR (output/<game>/frame_ir.json)

Per-frame, per-channel state: frame, period, midi_note, volume, duty, sounding.
This is the canonical intermediate representation.

### Parser Events (internal)

Full-duration NoteEvent, RestEvent, InstrumentChange, ControlFlow events.
Parser emits these; Frame IR consumes them.

### MIDI (output/<game>/midi/<song>.mid)

Type 1 MIDI. Track 0 = meta. Tracks 1-4 = channels.
CC11 = volume. CC12 = duty. Note durations from Frame IR sounding_frames.

### REAPER Project (output/<game>/reaper/<song>.rpp)

Generated ONLY via `python scripts/generate_project.py --midi <f> --nes-native -o <out>`.
Never written by hand.

## Anti-Patterns

1. **Guessing byte formats without evidence** — read the 6502 code or triangulate
2. **Trusting fan MIDI rhythm** — pitch yes, rhythm no
3. **Generating MIDI from trace periods alone** — misses transposition (Battletoads lesson)
4. **Assuming one game's driver works for another** — even same company, different games
5. **Debugging MIDI before confirming Frame IR** — wrong layer
6. **Changing multiple things at once** — one hypothesis, one test, one change
7. **Polishing wrong data** — if the base note is wrong, stabilizing it produces a stable wrong note
8. **Skipping the call stack** — subroutine calls are common; ignoring them desynchronizes the stream

See `.claude/rules/architecture.md` Rules 13-15 for additional anti-patterns
(zero parse errors ≠ correctness, execution semantics mandatory, five layers distinct).

## Invoking Other Skills

This skill orchestrates the finder skills. Invoke them as needed:

```
"The period table hasn't been found yet"    → LOOKUPTABLEFINDER
"I don't know the command param counts"     → COMMANDFINDER
"I can't find the song data pointers"       → SEQUENCEFINDER
"The note encoding is wrong"                → PITCHFINDER
"The durations don't match the trace"       → RHYTHMFINDER
"The volume envelope is wrong"              → ENVELOPEFINDER
"I need to coordinate a full extraction"    → MUSICFINDER_ORCHESTRATOR
```

When all finders have produced verified results, the MUSICFINDER_ORCHESTRATOR
assembles the final MIDI and REAPER project.
