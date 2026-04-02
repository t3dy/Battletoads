# Handover: Battletoads Session

## What Was Accomplished

### Pipeline Fixes (all committed-ready)
1. **JSFX syntax error fixed** — empty else branches on lines 403/409 of
   ReapNES_Console.jsfx caused @sample to fail. Added `0;` no-ops.
2. **CC11 volume decoding fixed** — was `/127*15` (lost 1 level at vol 10-15),
   now `/8` (exact NES volume recovery).
3. **CC12 duty decoding fixed** — was `min(3,x)` (always duty 3 = 75%),
   now `floor(x/32)` (correct quartile mapping).
4. **nsf_to_reaper.py fixed** — now calls `generate_project.py` for RPP
   generation instead of inline `build_rpp()` skeleton.
5. **generate_project.py fixed** — embeds MIDI inline with HASDATA instead
   of FILE references. Strips X meta events that caused empty items.
6. **Noise duration fixed** — drums capped at 12 frames or <25% of hit
   volume instead of waiting for vol=0 (was causing 500ms+ smear).

### New Tools Built
- **`scripts/trace_to_midi.py`** — Mesen CSV → MIDI+SysEx → REAPER projects
  - Parses Mesen capture into per-frame channel data
  - Builds register state for SysEx APU replay
  - Generates both Console and APU2 REAPER projects
  - Song segmentation, SFX filtering
- **`output/test_inline_midi.rpp`** — smoke test RPP with 5 hardcoded notes
- **Track name mapping** — Song 3 = Ragnarok's Canyon (Level 1), not Song 2

### Files Modified
- `C:/Users/PC/AppData/Roaming/REAPER/Effects/ReapNES Studio/ReapNES_Console.jsfx`
- `scripts/nsf_to_reaper.py` (build_midi params, process_song, drum fix)
- `scripts/generate_project.py` (HASDATA, midi_track_to_events, no X events)
- `scripts/trace_to_midi.py` (new file, with SysEx support)

### Documents Written
- `docs/WHYSUCHABADSTARTWITHBATTLETOADS.md` — full audit of failures
- `docs/WHATWORKEDWITHCONTRAANDCASTLEVANIA.md` — methodology that works
- `docs/LEAVENOTURNUNSTONED.md` — exhaustive parameter checklist + Deckard boundary
- `docs/FRAMEBYFRAME.md` — NSF vs Mesen comparison, data divergence
- `docs/FINDINGTRACKBOUNDARIES.md` — track mapping with names from KHInsider
- `docs/TIPSFORWORKINGWITHTED.md` — vocabulary bridging, collaboration patterns
- `docs/PROMPTENGINEERINGCRITIQUE.md` — honest assessment of session failures
- `docs/BUILDINGTHEENVIRONMENT.md` — 9 concrete environment fixes
- `docs/TEDSPROMPTSTYLE.md` — prompt style strengths and foibles
- `docs/ENVIRONMENTFIXES.md` — infrastructure improvements to prevent recurrence
- `docs/DATAONTOLOGY.md` — comprehensive data schema for entire pipeline

## What Needs to Happen Next

### IMMEDIATE: New Mesen Capture Needed

The existing capture (`C:/Users/PC/Documents/Mesen2/capture.csv`) is
only 6149 frames (102s). The title screen consumed ~97s, leaving only
~1 second of Level 1 music.

**DONE**: New capture recorded — 9496 frames, 158 seconds, 30362 state
changes. Pure Level 1 (Ragnarok's Canyon) gameplay. Saved to:
`C:/Users/PC/Documents/Mesen2/capture.csv` (overwrote the old one).

### NEXT: Run Trace-to-SysEx Pipeline

```bash
python scripts/trace_to_midi.py "C:/Users/PC/Documents/Mesen2/capture.csv" \
  -o output/Battletoads_trace/ --game Battletoads \
  --name "Ragnoraks_Canyon" --seg-num 3
```

This will produce:
- MIDI with CC11/CC12 + SysEx APU register track
- Console RPP (CC-driven)
- APU2 RPP (SysEx register replay — maximum fidelity)

**SFX separation strategy**: The capture has some SFX (enemy hits) mixed
in, but contains more than one full loop of the music. Compare two cycles
frame-by-frame — frames that differ between cycles are SFX, frames that
match are music. Use the clean cycle for the final extraction.

### Key Findings for Next Session

1. **NSF extraction ≠ game audio for Battletoads.** The NSF driver
   produces different timing, missing channels, no sweep vibrato.
   The Mesen trace is the only reliable source.

2. **Track mapping**: Song 1=Title, Song 2=Interlude, **Song 3=Level 1
   (Ragnarok's Canyon)**. Full mapping in `docs/FINDINGTRACKBOUNDARIES.md`.

3. **The "bass slide"** Ted hears is the NES sweep unit (hardware pitch
   bend, ±4 period oscillation per frame). Only captured in SysEx, not
   in MIDI CC. The APU2 synth handles this via the SysEx register replay.

4. **The APU2 synth is the path to fidelity** for file playback. It
   reads raw register state from SysEx and replays it hardware-accurately,
   including sweep, noise mode, phase reset — everything MIDI CCs can't
   encode.

5. **Synth bugs are fixed** but need to be synced to the repo copy:
   ```bash
   cp "C:/Users/PC/AppData/Roaming/REAPER/Effects/ReapNES Studio/ReapNES_Console.jsfx" \
      studio/jsfx/ReapNES_Console.jsfx
   ```

## Session Startup Checklist (For Next Session)

```
[ ] Read this handover doc
[ ] Read docs/MISTAKEBAKED.md (blunder prevention)
[ ] Verify JSFX synth compiles: open FX window, check for error banner
[ ] Verify test_inline_midi.rpp plays sound in REAPER
[ ] Ask user: "Do you have the new Level 1 Mesen capture?"
[ ] If yes: run trace_to_midi.py with --auto-segment
[ ] Test ONE song before batch processing
```

## State of Output Files

```
output/Battletoads/
  nsf/    — NSF file (21 songs)
  midi/   — NSF-extracted MIDIs (all 21, with drum fix)
  reaper/ — NSF-based RPPs (all 21, HASDATA, but NSF fidelity is low)
  wav/    — NSF WAV previews (all 21)
  mp3/    — Reference MP3s from Zophar (all 21)

output/Battletoads_trace/
  midi/   — Trace-extracted MIDIs (title screen + partial level 1)
  reaper/ — Trace-based RPPs (title screen + partial level 1)

Projects/Battletoads/
  midi/   — Copies of NSF MIDIs for self-contained projects
  *.rpp   — All 21 NSF-based RPPs (HASDATA, ready to play)
```
