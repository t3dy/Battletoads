# FIXING MARIO 1 — Session Log

Date: 2026-03-31 / 2026-04-01
Game: Super Mario Bros. (Track 01: Running About / Overworld)
Blocker: B14 (Console synth ignores CC11/CC12)

## What We Fixed

### Fix 1: CC11/CC12 Handling in ReapNES_Console.jsfx

**Problem:** The Console synth had no CC handlers. File playback used ADSR
approximation instead of the ground-truth per-frame volume/duty envelopes
baked into the MIDI by NSF extraction.

**Changes to `C:\Dev\ReapNES-Studio\jsfx\ReapNES_Console.jsfx`:**

1. **@init** — Added `cc_active[4]` array (memory offset 600) and
   `cc_file_mode` flag. Tracks whether each channel is driven by
   CC automation or ADSR.

2. **@block** — Added 3 CC handlers ported from ReapNES_APU.jsfx:
   - CC11 (expression) → sets `cc_active[ch]=1`, converts 0-127 to
     NES volume 0-15, writes to `p1_vol`/`p2_vol`/`noi_vol`
   - CC12 (timbre) → sets `cc_active[ch]=1`, writes duty 0-3 to
     `p1_duty`/`p2_duty`
   - CC123/CC121 (reset) → clears all `cc_active[]` and `cc_file_mode`

3. **@block note-on/off** — Gated ADSR trigger: when `cc_active[ch]`
   is set, note-on uses velocity directly (no `trigger_env`), note-off
   kills oscillator immediately (no `release_env`).

4. **@sample** — ADSR `process_env()` calls gated by `!cc_active[ch]`.
   When CC-driven, `env_p1_vol = p1_vol` (set by CC11), `p1_env_duty =
   p1_duty` (set by CC12). ADSR only runs for keyboard-played channels.

**Dual-mode contract preserved:**
- CC data present (file) → CC drives volume/duty, ADSR bypassed
- No CC data (keyboard) → ADSR envelope shapes note
- CC123/CC121 → resets to ADSR mode

### Fix 2: Keyboard Remap vs File Routing Conflict

**Problem:** All 4 tracks share the same multi-channel MIDI file. The
keyboard remap (`kb_mode && ch_mode < 4`) forced ALL incoming MIDI to
the track's channel, bypassing the channel filter. Every track played
every channel's notes and CC data. Symptoms:

- Random noises (noise CC/notes applied to pulse tracks)
- Tones off (wrong channel's volume/duty overwriting correct values)
- Notes missing (competing note-on/off from wrong channels)
- No drums (noise track playing pulse/triangle data)

**Fix:** Added `cc_file_mode` flag. Set to 1 when any CC11/CC12 arrives
(indicating file playback). When set, keyboard remap is disabled and the
channel filter routes each channel's data to the correct track. Reset on
CC123/CC121 so keyboard play still works.

```
// Before (broken):
kb_mode && ch_mode < 4 ? ( ch = ch_mode; ... );

// After (fixed):
kb_mode && ch_mode < 4 && !cc_file_mode ? ( ch = ch_mode; ... );
```

## What Remains Broken

### MIDI Extraction Pitch Accuracy (Layer 2 — NSF emulation)

**UPDATE (post-Mesen capture):** The Mesen capture proved the error is
exactly +12 semitones (1 octave) across ALL notes on ALL channels.
The earlier analysis of Pulse 1 showing "~10 semitones" was comparing
against wrong expected values. Pulse 2 carries the melody, and the
comparison is definitive: NSF period is exactly half of Mesen period
for every note (ratio ~2.005 consistently).

See `docs/MARIODISCOVERIES.md` for the full 12-note comparison table.
- The rhythmic pattern is approximately right

**Root cause hypothesis:** The period-to-MIDI conversion in the NSF
emulator (`nsf_to_reaper.py`) may have an incorrect octave offset or
period table. The 6502 CPU emulation drives the NES sound driver, which
writes APU period registers. Converting those periods to MIDI note
numbers requires knowing the CPU clock rate and the channel type (pulse
uses 16-step, triangle uses 32-step sequencer). An error in this
conversion would shift all pitches uniformly.

**However:** The shift is 10 semitones, not 12. This suggests either:
1. The period table lookup has a bug (quantizing to wrong entries)
2. The CPU clock constant is wrong
3. The channel type is being misidentified for some notes

This is NOT a synth problem — the synth faithfully plays what the MIDI
contains. The error is in the NSF extraction pipeline.

### Timbre Quality

Even with correct CC handling, the Console synth timbres may not match
the NES accurately because:

1. **Waveform generation** — The JSFX uses a lookup table for pulse duty
   (8-step) and triangle (32-step). Timing granularity at 44.1kHz vs
   the NES's ~1.789MHz clock means aliasing artifacts.

2. **Mixer model** — The NES DAC has a nonlinear mixing curve. The
   Console synth uses linear mixing (`value / 15.0 * weight`). This
   affects the balance and character of mixed channels.

3. **Volume quantization** — CC11 0-127 mapped to 0-15 (NES range).
   The mapping `floor(msg3 / 127 * 15 + 0.5)` may not match the
   original NES driver's volume table.

### Track Naming

Track 03 in the NSF is "Underground" and Track 05 is "Swimming Around"
(underwater waltz). Names come from the M3U file distributed with the
NSF (tagged by user "Knurek" on Zophar's Domain). These names match the
game's actual levels. The user reported "Underground" sounding like the
waltz — needs ear-check to confirm whether:
- The M3U track numbering is wrong, OR
- The NSF extraction is extracting the wrong track for that slot

## Mysteries and Open Questions

### 1. Why 10 Semitones Off?

The period-to-MIDI formula in `nsf_to_reaper.py` needs inspection. For
NTSC NES pulse channels:

```
freq = CPU_CLK / (16 * (period + 1))
midi_note = 69 + 12 * log2(freq / 440)
```

Where CPU_CLK = 1,789,773 Hz. If the code uses a different constant,
or applies the triangle divisor (32) to pulse channels, pitches shift.
A factor of 32/16 = 2x frequency = 12 semitones (one octave). But we
see 10, not 12, which suggests a more subtle error.

### 2. Are Notes Actually Missing or Just Pitch-Collapsed?

The repeated F#4(66) where we expect both E5 and C5 could mean:
- The NSF driver is outputting periods that are very close, and the
  MIDI quantization maps them to the same note
- The 6502 emulation is not advancing the sound driver's note pointer
  correctly, replaying the same note

A Mesen capture would definitively answer this.

### 3. Drum Channel Silence

Track 4 (Noise) has 67 events with 0 CCs — velocity-driven only. This
is correct for Mario's simple drum pattern. But the user reported no
drums. Possible causes:
- Keyboard remap was routing noise notes to pulse oscillator (FIXED)
- Noise period mapping in Console may differ from APU
- Need to verify after JSFX cache bust (rename file, B04)

### 4. JSFX Cache (B04)

REAPER caches compiled JSFX bytecode. Editing the source does NOT
invalidate the cache. The user may still be hearing the OLD unfixed
synth. **Must rename the file** (e.g., `ReapNES_Console.jsfx` ->
`ReapNES_Console2.jsfx` -> rename back) to force recompilation.

## Recommendation: Mesen Capture

**Yes, a Mesen capture would be extremely valuable.** It would:

1. **Confirm note accuracy** — Compare APU period register values frame
   by frame against what the NSF emulator produces. If the real game
   writes period 170 (E5) but nsf_to_reaper maps it to note 66 (F#4),
   the period-to-MIDI table is wrong.

2. **Validate volume envelopes** — Mario has a characteristic 5-step
   decay (vol 15 -> 12 -> 9 -> 6 -> 3). Compare against CC11 values
   in the extracted MIDI.

3. **Check drum behavior** — Capture the noise channel register writes
   to see what period/mode/volume the game actually uses for kick and
   snare hits.

4. **Establish ground truth** — No existing trace captures for Mario.
   The `extraction/traces/` directory has captures for Castlevania,
   Contra, Bionic Commando, Mega Man 1, Gradius, and Super C, but
   NOT Mario.

### Capture Procedure

Full instructions in `docs/OPERATOR_GUIDE.md`. Summary:

1. Load `mesen_apu_capture.lua` in Mesen 2
2. Load the Mario ROM: `C:\Dev\NESMusicStudio\AllNESRoms\All NES Roms (GoodNES)\World\Super Mario Bros. (W) (V1.0) [!].nes`
3. Start World 1-1, press `[` to begin capture
4. Let the Overworld theme play for ~30 seconds (capture full loop)
5. Press `]` to stop, saves CSV to Mesen directory
6. Convert: `python scripts/convert_trace.py <csv> --rom-name "Super Mario Bros."`
7. Place in `extraction/traces/super_mario_bros/overworld.csv`
8. Compare against MIDI: frame-by-frame period/volume/duty matching

### What the Capture Would Answer

| Question | How Trace Answers It |
|----------|---------------------|
| Why 10 semitones off? | Compare $4002 period values to extracted MIDI notes |
| Are notes collapsed? | Check if C5 and E5 have distinct periods in trace |
| Correct volume envelope? | Compare $4000 volume writes to CC11 values |
| Drum pattern correct? | Check $400E/$400F noise register writes |
| Duty cycle changes? | Compare $4000 duty bits to CC12 values |

## Files Modified

- `C:\Dev\ReapNES-Studio\jsfx\ReapNES_Console.jsfx` — CC handling + file mode routing

## Validation Results

```
Mario Overworld (validate_project.py):
  Routing:       FAIL (pre-existing: missing RPP track fields)
  Pitch/Duration: NOT_IMPLEMENTED (needs mido)
  Envelope/CC:   PASS (922 notes, 3319 CC11, 2 CC12 detected)
  Timbre/Duty:   PASS (Console synth, channel modes correct)
  Noise/Drums:   PASS (67 events in noise track)
```

## Next Steps

1. **Rename JSFX to bust cache** — verify fix is actually loaded
2. **Mesen capture of Mario Overworld** — establish ground truth
3. **Inspect `nsf_to_reaper.py` period-to-MIDI conversion** — find the
   10-semitone offset bug
4. **Compare trace vs extracted MIDI** — frame-level validation
5. **Fix pitch mapping, re-extract Mario, ear-check**
