# AVOIDBLUNDERS.md — Lessons Learned for REAPER Integration

## Blunder 1: Missing Pin Declarations
**What happened:** All JSFX plugins lacked `in_pin:none` / `out_pin:Left` / `out_pin:Right`.
**Why it matters:** Without pin declarations, REAPER treats JSFX as audio effects, not instruments. No audio input = no audio output = silence.
**Rule:** Every JSFX synthesizer MUST declare pins. Always include:
```
in_pin:none
out_pin:Left
out_pin:Right
```

## Blunder 2: Guessing RPP Token Format
**What happened:** Used tokens like `MASTER_SEND`, `REC_INPUT`, `RECINPUT`, `RECMON` based on assumptions about the RPP format. All were rejected by REAPER v7.27.
**Rule:** Never guess RPP tokens. Either:
- Copy exact token syntax from an existing working .RPP file saved by the same REAPER version
- Reference the Cockos wiki: `wiki.cockos.com/wiki/index.php/RPP`
- When in doubt, omit the token and let REAPER use defaults

## Blunder 3: Trying to Set MIDI Input via RPP
**What happened:** Spent multiple iterations trying to configure MIDI keyboard input in RPP files. No approach worked in v7.27.
**Rule:** MIDI input device configuration is a runtime setting, not a project file setting. Accept that users must set MIDI input manually after opening the project. Document this as a known manual step, not a bug.
**From the user guide (p59-60, p72-73):** MIDI input is configured via the track's record arm context menu or input dropdown. It's a per-session setting tied to the user's hardware, not a project property.

## Blunder 4: Trying to Embed MIDI in RPP Files
**What happened:** Tried two approaches (MIDIPOOL FILE and inline SOURCE MIDI). Neither produced playable MIDI items.
**Why:** REAPER v7 uses an internal `POOLEDEVTS` system for MIDI data that references pooled events by GUID. Raw E/X event lines or external file references don't work the same way.
**Rule:** Don't embed MIDI in generated RPP files. Instead:
1. Generate the project with tracks and plugins ready
2. Import MIDI via drag-and-drop in REAPER's UI
3. Or use ReaScript (REAPER's Lua/Python API) which can insert MIDI items properly
**From the user guide (p266):** MIDI items are stored as "in-project REAPER media items" using REAPER's internal format. External .MID files are noted to have limitations ("overdub/replace recording doesn't work correctly with .MID files").

## Blunder 5: Building Before Verifying
**What happened:** Built song sets, preset catalog, project generator, MIDI mapper, drum kits, sweep unit — then discovered the fundamental plugin didn't produce sound. All that work depends on a foundation that was never tested.
**Rule:** Always verify the simplest possible case before building on top:
1. Can the JSFX plugin produce a beep from one MIDI note? Test manually.
2. Can an RPP file load the plugin and produce sound? Test with minimal RPP.
3. Can MIDI items play back through the plugin? Test with one note.
Only after all three work should you build song sets, catalogs, and automation.

## Blunder 6: JSFX Slider Gap (slider15 → slider20)
**What happened:** ReapNES_Full.jsfx uses sliders 1-15, then jumps to slider20 for Master Gain. RPP files store slider values positionally. This gap may cause REAPER to misassign the gain value or fill intermediate values with 0.
**Rule:** Number JSFX sliders sequentially without gaps, OR verify exactly how REAPER serializes non-sequential slider values in RPP files.

## Blunder 7: Not Reading Working Project Files First
**What happened:** Started generating RPP files from documentation and assumptions instead of examining real working .RPP files saved by the user's REAPER version.
**Rule:** Before generating any REAPER artifact:
1. Create the desired result manually in REAPER
2. Save as .RPP
3. Open the .RPP in a text editor
4. Copy the exact format, tokens, and structure
This reverse-engineering approach is more reliable than any documentation.

## Blunder 8: Unicode Characters in JSFX
**What happened:** Used em dashes (—) and arrows (→, ←) in JSFX file descriptions and comments. While JSFX handles these in comments, it's a risk on Windows systems with cp1252 encoding.
**Rule:** Use only ASCII in JSFX files. Replace — with --, → with ->, ← with <-.

## Blunder 9: Not Understanding REAPER's VSTi vs JSFX Distinction
**What happened:** Assumed JSFX instruments are treated identically to VSTi plugins.
**From the user guide (p73):** "Insert virtual instrument on new track" presents VSTi/DXi plugins. JSFX are not mentioned in this workflow. JSFX instruments may need different track configuration than VSTi.
**Rule:** Test JSFX instrument behavior separately from VSTi. They may have different requirements for MIDI routing, pin configuration, and FX chain placement.

## Blunder 10: Over-Engineering Before Ear-Testing
**What happened:** Built a 54K preset corpus, 6 song sets, a catalog browser, a MIDI auto-mapper, and a drum kit system before ever hearing a single note through the synth in REAPER.
**Rule:** The first milestone is ONE AUDIBLE NOTE. Everything else comes after.

---

## Correct Order of Operations (For Future Work)

1. Write minimal JSFX synth with correct pins → test manually in REAPER → hear sound
2. Save working track as .RPP → examine the file → learn the format
3. Generate minimal RPP matching the examined format → open in REAPER → hear sound
4. Add features to the JSFX (channels, noise, envelopes) → test after each addition
5. Add MIDI items manually in REAPER → save → examine how REAPER stores them
6. Only then build automation scripts that generate RPP files
7. Only then build preset systems, song sets, and catalogs

## Key External References

- JSFX Programming: `https://www.reaper.fm/sdk/js/js.php`
- RPP File Format: `wiki.cockos.com/wiki/index.php/RPP`
- Keith Haydon's JSFX Guide: `https://www.keithhaydon.com/Reaper/JSFX2.pdf`
- REAPER User Guide Section 16.16-16.17: JS Plug-in usage (p330-331)
- REAPER User Guide Section 3.5-3.6: Track input assignment (p59-60)
- REAPER User Guide Section 3.31-3.33: MIDI recording setup (p71-73)
