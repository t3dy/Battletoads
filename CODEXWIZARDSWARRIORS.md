# Wizards & Warriors Project Notes

This document records the current reverse-engineering and extraction state for
`Wizards & Warriors` in this repo.

It is a working project note, not a final spec. Anything labeled
`hypothesis` still needs execution-semantics validation against trace.

## Goal

Build a flexible ROM-to-REAPER pipeline for `Wizards & Warriors` that follows
the repo's architecture:

1. Recover song/channel boundaries from the game driver.
2. Build a structural parser from ROM/NSF data.
3. Promote that parser to frame-level execution semantics.
4. Compare simulated frame state against Mesen capture.
5. Only then treat ROM-derived output as trusted.

## Evidence Sources

- ROM: `C:\Dev\NSFRIPPER\extraction\roms\Wizards & Warriors (U) (V1.0) [!].nes`
- NSF reference: `C:\Dev\NSFRIPPER\state\ww_ref\Wizards & Warriors [Densetsu no Kishi - Elrond] (1987-12)(Rare)(Acclaim).nsf`
- M3U track list: `C:\Dev\NSFRIPPER\state\ww_ref\Wizards & Warriors [Densetsu no Kishi - Elrond] (1987-12)(Rare)(Acclaim).m3u`
- Title trace capture: `C:\Dev\NSFRIPPER\extraction\traces\wizards_and_warriors\title_capture.csv`

## Repo Files Added / Updated

- Manifest: `C:\Dev\NSFRIPPER\extraction\manifests\wizards_and_warriors.json`
- Structural parser: `C:\Dev\NSFRIPPER\extraction\drivers\other\wizards_and_warriors_parser.py`
- Pulse simulator: `C:\Dev\NSFRIPPER\extraction\drivers\other\wizards_and_warriors_simulator.py`

## Key Pipeline Context

The project follows the repo's documented rules in:

- `CLAUDE.md`
- `docs/ARCHITECTURE_SPEC.md`
- `EXECUTIONSEMANTICSVALIDATION.md`
- `.claude/skills/MUSICFINDER_ORCHESTRATOR.md`
- `.claude/skills/SKELETONKEY.md`
- `.claude/skills/ROMPARSER.md`

The most important rule is:

- Structural parsing is not enough.
- Zero desync is not enough.
- Trusted output requires execution-semantics validation.

## Current High-Level Status

### Done

- Located and staged ROM, NSF, M3U, and title trace.
- Identified NSF entry points.
- Disassembled enough of the title driver path to recover:
  - song init behavior
  - play routine
  - command dispatch table
  - period tables
  - all 16 song/channel pointer sets
- Built a discovery-stage parser.
- Built a first pulse-only simulator for the title track.
- Simulator achieves exact scaled-period match against Mesen trace for title pulse channels (Rung 3, 2169 frames).

### Not Done Yet

- Triangle period and sounding semantics are effectively solved for the title,
  but the exact last-frame linear-counter value curve is still approximate.
- Noise semantics are only validated as inactive for the clean title capture.
- Full command meanings are still partial.
- No full execution-semantics validation report yet.
- No trusted ROM-derived MIDI/REAPER export yet.

## Verified Technical Findings

### NSF Header

- Load address: `0x8000`
- Init address: `0xFFC0`
- Play address: `0xEE55`
- Songs: `16`

### ROM / NSF Relationship

- The NSF payload matches the ROM PRG from the start.
- This means discoveries made in the NSF image map directly back to the ROM.

### Driver Family

Initial static signature scanning incorrectly suggested a Konami/Maezawa-like
engine because of repeated FE/FD/E8-like byte patterns.

After disassembly, the current best model is:

- `Wizards & Warriors` uses its own custom driver layout.
- It should not be forced into the existing Battletoads Rare parser.
- It should not be forced into the Konami parser either.

### Play Routine and Dispatch

- Main play routine: `0xEE55`
- Command dispatch table: `0xEEEE`

Recovered handler map so far:

- `0x00 -> 0xEF04`
- `0x01 -> 0xEF74`
- `0x02 -> 0xEF27`
- `0x03 -> 0xEF33`
- `0x04 -> 0xEF5E`
- `0x05 -> 0xEF8C`
- `0x06 -> 0xEFBF`
- `0x07 -> 0xEF4A`
- `0x08 -> 0xEF41`
- `0x09 -> 0xEF37`
- `0x0A -> 0xEF54`

### Song / Channel Pointer Recovery

Song/channel pointers are recovered deterministically by emulating the NSF
init routine and reading channel RAM state after init completes.

Title track (`song 1`) channel pointers:

- Pulse 1: `0xF07B`
- Pulse 2: `0xF0E0`
- Triangle: `0xF1A3`
- Noise: `0xF1E0`

All 16 songs are now mapped in the manifest.

### Title Capture Boundary

The title trace contains two main music spans:

- `3-2170`
- `2721-4889`

The first one starts late. The clean reference span is:

- `2721-4889`

## Stream Structure Findings

### Per-Channel Stream Header

Each channel stream begins with a 3-byte initialization header loaded by the
init/play setup path before event parsing begins.

For example:

- Pulse 1 starts with `45 0A 21`
- Pulse 2 starts with `43 0A 21`

These are not note events. They seed channel register state.

### Event Classes Observed

After the 3-byte header, the stream contains:

- command bytes below `0x10`
- table-note bytes with bit 7 set
- direct-period note forms in the `0x10-0x7F` range

### Duration Behavior

Important discovery from driver instrumentation:

- `$07E0,X` controls duration mode.
- Negative means inline duration bytes are read from the stream.
- Non-negative means persistent duration is used.

For the title:

- Pulse 1 opening rests are inline-duration driven.
- Pulse 2 melody uses persistent duration `8`.

### Loop Behavior

Loop semantics matter. The opening pulse 1 mismatch was caused by handling the
`0x05` / `0x06` loop pair incorrectly.

Current parser behavior now unfolds the title opening rest loop correctly.

## Period Tables

Two period resources are currently in use:

- Table-note period table at `0xEFD9`
- Direct-period table at `0xF000`

Important detail:

- `0xEFD9` behaves like a little-endian compact table-note lookup.
- `0xF000` is stored big-endian.

This is why naive standard NTSC table scanning initially failed.

## Parser Status

The structural parser is discovery-stage only.

What it can do now:

- emulate NSF init and recover all song pointers
- parse title pulse streams without structural desync
- unfold observed loop structure
- distinguish:
  - channel init header
  - commands
  - table-note events
  - direct-note events

What it cannot honestly claim yet:

- full command semantics
- correct triangle semantics
- correct noise semantics
- trusted musical interpretation for the whole game

## Simulator Status

The current simulator started as a title-focused validator, but it now also
has a generic NSF-ground-truth comparison path for melodic channels:

- title validation against the clean second Mesen capture
- generic `song -> channel -> 512-frame` comparison against direct NSF
  emulation
- supported melodic channels: `pulse1`, `pulse2`, `triangle`

### Current Results

Pulse 2 title:

- exact scaled period alignment: `2169 / 2169`
- sounding agreement: `2168 / 2169`
- only disagreement: final captured frame, where trace volume drops to zero

Pulse 1 title:

- exact scaled period alignment: `2169 / 2169`
- sounding agreement: `2168 / 2169`
- only disagreement: final captured frame, where trace volume drops to zero

Important caveat:

- This is still a pulse-only validation.
- Triangle period path is exact and its gate/release behavior now matches at
  the sounding level.
- Noise is only validated as inactive for this title capture.
- The title track is promising, but the whole game is not yet trusted.

Triangle title:

- exact period alignment: `2169 / 2169`
- sounding agreement: `2169 / 2169`
- only remaining approximation: the exact linear-counter decay values on the
  last few release frames

### Whole-Game NSF Sweep

A second-stage internal validation pass now compares the current simulator
against direct NSF emulation for the first `512` frames of every song's melodic
channels.

Report:

- `C:\Dev\NSFRIPPER\extraction\analysis\reconciled\wizards_and_warriors_nsf_semantics_sweep.md`

Headline results:

- exact melodic-channel matches: `48 / 48`
- songs with all three melodic channels exact for 512 frames: `16 / 16`

What closed the whole-game melodic sweep:

- song-level duration scaling from command `0x09`
  `Ice Cave` uses `3x`; `Initial Registration` uses `2x`
- generic pulse `StopEvent` mute behavior
- title-only triangle release kept scoped to song `1`
- wider loop traversal for simulator-oriented parses

Current implication:

- every song now matches direct NSF emulation for `pulse1`, `pulse2`, and
  `triangle` over the first `512` frames
- this is a strong internal semantics milestone
- it is still not the same as external Mesen-capture validation for the full
  soundtrack

### Noise Status

Noise now has a dedicated survey note:

- `C:\Dev\NSFRIPPER\extraction\analysis\reconciled\wizards_and_warriors_noise_survey.md`
- `C:\Dev\NSFRIPPER\extraction\analysis\reconciled\wizards_and_warriors_noise_partial_semantics.md`
- `C:\Dev\NSFRIPPER\extraction\analysis\reconciled\wizards_and_warriors_track_readiness.md`

Current noise picture:

- common sentinel stream `0xF1E0` is genuinely silent in many songs
- songs `5` and `8` have noise registers primed or changing, but remain muted
  in the sampled window
- songs `2`, `6`, and `16` have genuinely active noise and still need dedicated
  semantics work

Important discovery:

- the noise channel does not share the melodic meaning of table-note bytes even
  when the raw stream shape looks similar
- current structural parsing is still useful for boundaries and durations, but
  not yet trustworthy for noise note-value interpretation

Partial noise semantics now established:

- song `2` uses a simple gated-noise voice that alternates between active and
  muted instrument states
- song `6` uses a fixed-period percussion layer with two volume/instrument
  intensities
- song `16` has confirmed raw-byte-to-noise-register mappings for several
  active bytes (`0x99`, `0x8D`, `0x8F`, `0x90`, `0x92`, `0x93`, `0x94`)

Provisional noise-simulator milestone:

- song `2` noise: exact NSF-register match for first `512` frames
- song `6` noise: exact NSF-register match for first `512` frames
- song `16` noise: exact NSF-register match for first `512` frames

So the strongest current internal claim is now:

- songs `1-16` all have working whole-track **hypothesis output** artifacts
- melodic channels are internally locked across the whole soundtrack (Rung 2)
- the active-noise songs now also have first-`512`-frame NSF-simulator matches (Rung 2 partial)
- title melodic channels validated against Mesen trace (Rung 3)

**Trust labeling (per Validation Ladder):**
- Title melodic: **Rung 3** (external trace validation, 2169 frames)
- All 16 melodic: **Rung 2** (internal NSF match, 512 frames)
- Noise (3 active songs): **Rung 2 partial** (NSF match, 512 frames)
- Noise (11 inactive songs): **Rung 1** (structural only)

Full validation record: `extraction/analysis/reconciled/wizards_and_warriors_validation_record.md`

### Whole-Soundtrack Practical Status

All 16 tracks are already present as `.mid` and `.rpp` **hypothesis output** in:

- `C:\Dev\NSFRIPPER\Projects\Wizards_and_Warriors`

Best current practical reading:

- songs `1`, `3`, `4`, `5`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`
  are strong working outputs right now (Rung 2 melodic)
- songs `2`, `6`, and `16` are also usable, but still carry active-noise
  decoding caveats (Rung 2 partial noise)
- **All output is hypothesis output** — usable for practical work but not
  claimable as fully validated. External Mesen captures exist only for the title.

Noise title:

- no active events in the clean second-pass capture
- inactive-path validation: `2169 / 2169`

## Existing Output Artifacts

There are already two useful output sets in the repo:

- NSF-derived game-wide output:
  `C:\Dev\NSFRIPPER\output\Wizards_and_Warriors`
- Trace-derived title output:
  `C:\Dev\NSFRIPPER\output\Wizards_and_Warriors_trace`

There are also ready-to-open REAPER projects in:

- `C:\Dev\NSFRIPPER\Projects\Wizards_and_Warriors`
- `C:\Dev\NSFRIPPER\Projects\Wizards_and_Warriors_trace`

## Whole-Game Structural Survey

A song-by-song structural survey now exists at:

- `C:\Dev\NSFRIPPER\extraction\analysis\static\wizards_and_warriors_song_survey.md`

Main takeaways:

- `0xF1E0` is a common inactive/sentinel stream.
- song 16 appears structurally derived from song 2.
- several short jingles are available for quick validation.
- the strongest next full-track target is probably song 2 (`Forest of Elrond`).

These are useful working artifacts, but they are not yet the same thing as a
fully semantics-validated ROM parser route.

## Open Questions

1. What are the full semantics of commands `0x03`, `0x07`, `0x08`, `0x09`, and `0x0A`?
2. Is the late pulse 1 mismatch a remaining loop/control-flow issue, a channel
   state issue, or a register interpretation issue?
3. What is the full triangle event model for the title?
4. What special behavior does the noise channel use, given its sentinel-like
   `0xF1E0` stream?
5. Can the title pulse simulator be promoted into a general per-song driver
   simulator for all 16 tracks?

## Recommended Next Steps

1. Decode noise-channel semantics separately instead of forcing it through the
   pulse/table-note assumptions.
2. Emit a first formal execution-semantics report for the title track.
3. After title validation passes for all relevant channels, apply the same init-pointer + parser +
   simulator workflow to the remaining 15 songs.

Recommended first non-title target:

- song 2 `Forest of Elrond`

## Short Summary

The project has moved past vague driver guessing and into concrete,
reproducible reverse engineering.

We now have:

- a verified title trace window
- verified NSF init/play entry points
- a verified song/channel map for all 16 tracks
- a discovery-stage parser
- a first real pulse-title simulator with strong trace agreement

The remaining work is to turn that promising title pulse alignment into full
execution-semantics validation, then extend the method across triangle, noise,
and the rest of the soundtrack.
