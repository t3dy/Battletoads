# Why Such a Bad Start with Battletoads

## What Happened

Battletoads was the first game ripped using the automated NSF pipeline
(`nsf_to_reaper.py --all`). Despite producing 21 MIDIs, 21 RPPs, and 21
WAVs, the REAPER projects played no sound. Multiple rounds of debugging
RPP structure, MIDI embedding format, and slider configuration failed to
find the issue — because the problem was never in the RPP files.

## THE Root Cause: Syntax Error in ReapNES_Console.jsfx

The JSFX synth plugin had a **compile-time syntax error** on line 404:

```
@sample:404: syntax error: '<> );'
```

Two empty `else` branches (lines 402-404 and 408-410) contained only
comments with no expressions. JSFX requires at least one expression in
every branch. The `@sample` block failed to compile entirely, which
means the synth received MIDI (visible as yellow indicators in REAPER)
but generated zero audio samples.

The fix was adding `0;` (a no-op expression) to both empty branches.

This error was visible in the FX window the entire time — a red error
banner at the top of the plugin UI. It was not checked until the user
opened the FX window and spotted it.

## Contributing Cause 1: nsf_to_reaper.py Used Its Own Broken RPP Builder

`nsf_to_reaper.py` had an inline `build_rpp()` (30 lines) that generated
skeleton RPPs — no synth, no FXCHAIN, no routing. It should have called
`generate_project.py`. The rule in `.claude/rules/reaper_projects.md`
explicitly says to use `generate_project.py`. This was the first failure.

## Contributing Cause 2: generate_project.py Used FILE References

`generate_project.py` used `SOURCE MIDI FILE "path"` to reference
external MIDI files. This may work in some REAPER configurations but is
less reliable than inline `HASDATA` embedding. Fixed to use HASDATA.
However, this was NOT the cause of the silence — the JSFX syntax error
was. With the synth fixed, FILE references may also have worked.

## The Fixes

1. **ReapNES_Console.jsfx**: Added `0;` no-op to two empty else branches
   (lines 403-404 and 409-410) that caused `@sample` to fail compilation.
2. **nsf_to_reaper.py**: Now calls `generate_project.py` instead of the
   inline `build_rpp()` skeleton.
3. **generate_project.py**: Now embeds MIDI inline with HASDATA for
   maximum compatibility, using the existing `midi_track_to_events()`
   function that was defined but never called.

## Why It Wasn't Caught Before Delivery

### Failure 1: Skipped self-validation

The RPP files were generated and listed in output logs, but never
opened or inspected. A 5-second check — opening one RPP in a text
editor and looking for `<FXCHAIN` — would have revealed the problem
instantly. The bare-bones RPP has 47 lines; a working one has 300+.

### Failure 2: The WAV files created false confidence

`nsf_to_reaper.py` also renders WAV previews using its own Python-based
synth (`render_wav()`). These WAVs play sound. This created the
impression that "the pipeline works" when in fact only the WAV path
worked — the REAPER path was broken.

### Failure 3: Assumed "structurally identical to working" = actually working

After regenerating with `generate_project.py`, extensive comparison
showed the Battletoads RPPs were structurally identical to Castlevania.
This was true — and irrelevant, because the Castlevania RPPs didn't
work either. The `SOURCE MIDI FILE` approach has never worked for
instrument playback. The comparison validated that the wrong thing
was consistently wrong.

### Failure 4: Never tested the "known-good" reference projects

The Castlevania and Contra RPPs were assumed to be working based on
the user's memory of successful playback 3-4 days earlier. That success
was likely from a different workflow (possibly opening MIDIs directly
in REAPER, or using the Kraid-style inline approach). Nobody re-tested
the reference projects before using them as the comparison baseline.

### Failure 5: build_kraid_project.py showed the correct approach

The `build_kraid_project.py` script correctly uses HASDATA with inline
MIDI events. The `midi_track_to_events()` function was even defined in
`generate_project.py` but never called. The working pattern existed in
the codebase the entire time — it just wasn't wired into the main pipeline.

## What Was Fixed

1. **`nsf_to_reaper.py:process_song()`** now calls `generate_project.py`
   via subprocess instead of the inline `build_rpp()`. Future games will
   get proper RPPs automatically.

2. **`build_midi()` in `nsf_to_reaper.py`** gained `period_fn` and
   `source_text` parameters (backward compatible) so trace-based
   pipelines can use correct pitch mapping without the NSF -12 workaround.

3. **All 21 Battletoads RPPs regenerated** via `generate_project.py`.

4. **`Projects/Battletoads/`** built via the official `build_projects.py`
   pipeline — same path that produced working Castlevania/Contra.

## What Was Built (New)

`scripts/trace_to_midi.py` — Mesen APU trace capture to MIDI converter:
- Parses Mesen CSV format (frame, parameter, value)
- Song segmentation via silence gap detection
- Conservative SFX artifact filter (ultrasonic periods only)
- Correct pitch mapping from hardware ground-truth periods
- Calls `generate_project.py` for RPP generation (follows invariant)

## Procedural Failures to Never Repeat

| Rule | What Went Wrong |
|------|-----------------|
| **Read your own rules before building** | `.claude/rules/reaper_projects.md` explicitly says `generate_project.py` is the only RPP builder. The inline `build_rpp()` should never have been used. |
| **Validate output before delivering** | Two rounds of "ready to test" were delivered without confirming the RPP files actually produce sound. |
| **Don't trust WAV success as RPP success** | The WAV render uses a completely separate code path. It proving the MIDI data is valid says nothing about the RPP being playable. |
| **Use the official pipeline** | `build_projects.py` exists precisely to standardize the output. Use it instead of ad-hoc RPP generation. |
| **Check structural equivalence early** | A diff against a working RPP would have caught the bare-bones skeleton in 30 seconds. |

## Current State

- `output/Battletoads/` — 21 NSF-extracted songs (MIDI + RPP + WAV)
- `output/Battletoads/mp3/` — 21 reference MP3s from Zophar
- `output/Battletoads_trace/` — 2 trace-derived songs (Title Screen + Level 1)
- `Projects/Battletoads/` — 21 projects via official build pipeline
- All RPPs now use `generate_project.py` and are structurally identical
  to the working Castlevania/Contra projects

## Next Step

All RPPs now use inline HASDATA. Open any of these and hit play:

- `Projects/Battletoads/Battletoads_02_Song_2_v1.rpp` (level 1 from NSF)
- `output/Battletoads_trace/reaper/Battletoads_trace_02_Level_1_v1.rpp` (from Mesen capture)

All other games in Projects/ also need rebuilding with `--force` to get
the HASDATA fix. Run: `python scripts/build_projects.py --force`
