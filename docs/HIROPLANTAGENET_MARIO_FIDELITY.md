# HiroPlantagenet Analysis: Mario Musical Fidelity

## 1. Intent Atoms

| # | Goal | Tag |
|---|------|-----|
| 1 | Determine the ground truth APU state for each frame | EXTRACTION |
| 2 | Convert APU state to MIDI notes with correct pitch | PIPELINE |
| 3 | Convert APU volume to CC11 with lossless round-trip | PIPELINE |
| 4 | Convert APU duty to CC12 with correct mapping | PIPELINE |
| 5 | Detect drum hits from noise channel state changes | EXTRACTION |
| 6 | Identify song boundaries in a multi-song capture | CLASSIFICATION |
| 7 | Filter hardware jitter from musical intent | EXTRACTION |
| 8 | Deploy synth changes so REAPER loads them | PIPELINE |
| 9 | Synth reads CC11/CC12 and produces correct volume/timbre | PIPELINE |
| 10 | Synth renders triangle with correct gating | PIPELINE |
| 11 | Synth renders noise with correct period/mode/volume | PIPELINE |
| 12 | Triangulate NSF and Mesen data to validate each other | CLASSIFICATION |
| 13 | Document what is proven vs what is still hypothetical | META-CONTROL |

## 2. Conflicts & Gaps

CONFLICTS:
- NSF extraction produces different periods than Mesen for pulse
  (halved) and completely wrong notes for triangle. Cannot use both
  as equivalent sources without reconciliation.
- Noise detection assumed vol=0 gaps between hits; Mario keeps vol>0
  and changes period instead. Two different encoding strategies need
  different detection logic.
- The CC11 mapping `vol * 8` loses precision on round-trip; the synth
  reads back a different volume than was captured.

MISSING DECISIONS:
- Whether to use NSF, Mesen, or both as extraction source per game.
  Currently switching ad-hoc.
- Whether the -12 pulse correction applies to all games or just Mario.
  No second game tested yet.
- How to handle captures that contain multiple songs (title screen +
  gameplay). Manual start-frame is fragile.

IMPLICIT ASSUMPTIONS:
- The Mesen Lua script captures decoded APU state, not raw register
  writes. This is better for our purposes but different from what
  the NSF path captures.
- Mario's noise channel never goes silent during the overworld. This
  may not generalize — other games may use vol-gate drum detection.
- Period jitter of +/-1 is hardware noise, not musical. This is true
  for triangle but may not apply to all channels or all games.

## 3. Layer Architecture

LAYER ARCHITECTURE:

Layer 1: Ground Truth Capture
  Purpose: Obtain frame-accurate APU state from Mesen for the target song.
  Atoms: #1, #6
  Reasoning mode: deterministic
  Verification: first P2 note matches known melody signature

Layer 2: Musical Event Detection
  Purpose: Convert frame-by-frame APU state to discrete musical events.
  Atoms: #2, #3, #4, #5, #7
  Reasoning mode: deterministic + analytical (jitter filter, drum detection)
  Depends on: Layer 1

Layer 3: MIDI Encoding
  Purpose: Write detected events as MIDI with CC automation.
  Atoms: #2, #3, #4
  Reasoning mode: deterministic
  Depends on: Layer 2

Layer 4: Synth Fidelity
  Purpose: Ensure the JSFX synth renders MIDI data faithfully.
  Atoms: #8, #9, #10, #11
  Reasoning mode: deterministic
  Depends on: Layer 3

Layer 5: Triangulation & Validation
  Purpose: Cross-check NSF and Mesen data to identify systematic errors.
  Atoms: #12, #13
  Reasoning mode: analytical
  Depends on: Layers 1-4

## 4. Rewritten Prompts

=== LAYER 1: GROUND TRUTH CAPTURE ===

OBJECTIVE: Obtain a clean Mesen capture of the target song with known
start/end frame boundaries.

SCOPE CONSTRAINTS:
- DO: Capture full loop(s) of the target song from gameplay start
- DO: Record exact frame number where the target song begins
- DO NOT: Assume the capture starts at the song — check for title
  screen, fanfares, or other pre-song audio

INPUTS:
- Mesen 2 with mesen_apu_capture.lua loaded
- Game ROM
- Target song identification (e.g., "World 1-1 Overworld")

OUTPUT CONTRACT:
| Field | Value |
|-------|-------|
| capture_path | absolute path to CSV |
| total_frames | integer |
| song_start_frame | integer (verified by melody signature) |
| song_end_frame | integer (or "end of capture") |
| melody_signature | first 5 P2 notes with periods |
| verification | "matches known melody" or "NEEDS REVIEW" |

DECISION RULES:
- Song start is the first frame where the melody channel (usually P2)
  plays the known opening pitch sequence
- If melody is unknown, use the first frame where 3+ channels are
  simultaneously active
- If capture contains multiple songs, document ALL song boundaries

=== LAYER 2: MUSICAL EVENT DETECTION ===

OBJECTIVE: Convert frame-by-frame APU state into discrete musical
events (note on/off, volume changes, duty changes, drum hits).

SCOPE CONSTRAINTS:
- DO: Detect note boundaries from period changes (pulse, triangle)
- DO: Detect drum hits from BOTH vol-gate AND period-change patterns
- DO: Filter hardware timer jitter (period +/-1 between frames)
- DO NOT: Quantize to musical grid — preserve frame-accurate timing

INPUTS:
- Per-frame APU state from Layer 1
- Song start/end frame boundaries

OUTPUT CONTRACT (per channel):
| Field | Type |
|-------|------|
| channel | pulse1/pulse2/triangle/noise |
| note_events | list of (frame, midi_note, velocity) |
| cc11_events | list of (frame, cc_value) |
| cc12_events | list of (frame, cc_value) |
| drum_events | list of (frame, gm_note, velocity, period, mode) |
| total_notes | integer |
| total_cc11 | integer |
| jitter_filtered | integer (how many 1-unit changes were suppressed) |

DECISION RULES:
- Pulse/triangle note boundary: period changes by > 2 units
- Noise drum hit: period changes while vol > 0, OR vol rises from 0
- CC11 mapping: round(vol * 127 / 15) for lossless round-trip
- CC12 mapping: [16, 32, 64, 96][duty] (unchanged)
- Triangle always vel=127, CC11=127 (no hardware volume control)
- If uncertain whether a period change is jitter or intentional,
  check if the MIDI note number changes — if not, it's jitter

=== LAYER 3: MIDI ENCODING ===

OBJECTIVE: Write detected events as a multi-track MIDI file with CC
automation matching the pipeline format.

SCOPE CONSTRAINTS:
- DO: Produce 5-track MIDI (meta + 4 channels)
- DO: Include source metadata (game, song, capture source)
- DO: Preserve frame-accurate timing (16 ticks per frame)
- DO NOT: Add any musical interpretation (quantization, humanization)

INPUTS:
- Event lists from Layer 2

OUTPUT CONTRACT:
| Field | Value |
|-------|-------|
| midi_path | absolute path to .mid file |
| track_0 | metadata (tempo, time sig, game, song, source) |
| track_1 | pulse1 (ch 0, notes + CC11 + CC12) |
| track_2 | pulse2 (ch 1, notes + CC11 + CC12) |
| track_3 | triangle (ch 2, notes + CC11=127 gate) |
| track_4 | noise (ch 3, drum notes + velocity) |
| note_counts | P1=N P2=N Tri=N Noise=N |
| cc_counts | P1=N P2=N Tri=N |

DECISION RULES:
- Tempo: 128.6 BPM, PPQ=480 (16 ticks per NES frame)
- Velocity from vol: round(vol * 127 / 15)
- No CC11 for noise (velocity-driven)

=== LAYER 4: SYNTH FIDELITY ===

OBJECTIVE: Verify the JSFX synth correctly renders the MIDI data.

SCOPE CONSTRAINTS:
- DO: Verify CC11 drives volume in CC mode
- DO: Verify CC12 drives duty in CC mode
- DO: Verify triangle renders when CC-driven (env_level = 15)
- DO: Verify noise renders with correct period/mode
- DO: Deploy to AppData, cache bust, ASCII check
- DO NOT: Modify MIDI data to compensate for synth limitations

INPUTS:
- MIDI file from Layer 3
- RPP project from generate_project.py
- ReapNES_Console.jsfx (installed copy)

OUTPUT CONTRACT:
| Check | Status |
|-------|--------|
| JSFX deployed to AppData | YES/NO |
| Cache busted | YES/NO |
| ASCII clean | YES/NO |
| CC11 handler present | YES/NO |
| CC12 handler present | YES/NO |
| tri_env_level set in CC mode | YES/NO |
| noi_env_level set in CC mode | YES/NO |
| cc_file_mode disables kb remap | YES/NO |

=== LAYER 5: TRIANGULATION & VALIDATION ===

OBJECTIVE: Cross-check NSF extraction against Mesen capture to
identify which extraction source is correct for each parameter.

SCOPE CONSTRAINTS:
- DO: Compare note sequences on all 4 channels
- DO: Compare volume envelopes on pulse channels
- DO: Compare duty cycle values
- DO: Compare noise hit timing and period values
- DO NOT: Assume either source is correct without evidence

INPUTS:
- Mesen MIDI from Layer 3
- NSF-extracted MIDI from nsf_to_reaper.py
- Mesen raw capture CSV

OUTPUT CONTRACT:
| Channel | Parameter | NSF correct? | Mesen correct? | Evidence |
|---------|-----------|-------------|----------------|----------|
| pulse1 | pitch | NO (-12) | YES | period ratio 2.0 |
| pulse2 | pitch | NO (-12) | YES | period ratio 2.0 |
| triangle | pitch | NO (wrong melody) | YES | bass line matches |
| noise | timing | PARTIAL (67/460 hits) | YES | period-change detection |
| pulse | volume | CLOSE | YES | CC11 values match |
| pulse | duty | CLOSE | YES | values match |

DECISION RULES:
- If NSF and Mesen agree on a parameter, it's proven correct
- If they disagree, Mesen is authoritative (higher in fidelity hierarchy)
- If Mesen data is ambiguous, use NSF as supporting evidence
- Document every disagreement with frame numbers and values

## 5. Execution Notes

- Layer 1 is HUMAN (requires Mesen capture from gameplay)
- Layers 2-3 are DETERMINISTIC (scripts)
- Layer 4 is DETERMINISTIC (file operations + grep verification)
- Layer 5 is ANALYTICAL (comparison scripts + judgment)
- Layer 1 must be repeated for each new song; Layers 2-4 are reusable
- The triangulation in Layer 5 should be run on every new game to check
  whether NSF extraction can be trusted for that game's sound driver
- JSFX deploy (Layer 4) must happen BEFORE any user testing — never
  skip this step
