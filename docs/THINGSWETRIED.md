# Things We Tried — Mario Overworld Session

A chronicle of every fix attempted, in order, with what each one
actually solved. Written as a post-mortem on why quality was so
low at first delivery.

## Attempt 1: Port CC11/CC12 handling to Console synth (B14 fix)

**What:** Added cc_active[] array, CC11/CC12/CC123 handlers, and
ADSR bypass logic to ReapNES_Console.jsfx.

**Result:** Correct in isolation — the code was right. But we edited
the SOURCE file (C:\Dev\ReapNES-Studio\jsfx\) while REAPER loads
from INSTALLED path (C:\Users\PC\AppData\Roaming\REAPER\Effects\).
The fix never reached the running synth.

**Should have known:** B04 (JSFX cache) was already documented in
blunders.json. Should have checked the install path immediately.

## Attempt 2: Fix keyboard remap vs file routing conflict

**What:** The keyboard remap (`kb_mode && ch_mode < 4`) forced ALL
MIDI messages to the track's channel, including CC data from other
channels. Added cc_file_mode flag to disable remap during file
playback.

**Result:** Fixed the "every track plays every channel" bug. But
still no sound because of Attempt 1 failure (wrong install path).

**Should have known:** The remap issue was the same class of bug as
B11 (every track plays every channel), already documented.

## Attempt 3: Copy JSFX to correct install location

**What:** Discovered REAPER loads from AppData, not the source repo.
Copied the fixed file.

**Result:** Got pulse sound working. Triangle and drums still missing.

**Should have done first:** Check where REAPER actually loads JSFX
from. This is basic REAPER knowledge.

## Attempt 4: JSFX cache bust (rename trick)

**What:** Renamed the JSFX file and back to force recompilation.

**Result:** REAPER loaded the new code. Pulse worked.

**Should have known:** B04 was documented. Should have been step 1
after any JSFX edit.

## Attempt 5: Fix Unicode em-dash in JSFX comment

**What:** An em-dash (U+2014) in a comment silently broke the JSFX
compiler on Windows.

**Result:** Fixed. ASCII only.

**Should have known:** B03 was documented. Should have run the
ASCII check automatically after every JSFX edit.

## Attempt 6: Fix triangle env_level in CC mode

**What:** In CC mode, process_env() was skipped for triangle, so
tri_env_level stayed at 0. The rendering code checked
`tri_env_level <= 0 && env_st[16] == 0` and killed every triangle
note immediately.

**Result:** Triangle became audible but playing wrong notes (because
the MIDI data itself was wrong — see Attempt 9).

**Should have caught:** When writing the CC bypass in @sample, should
have traced what variables the rendering code depends on and ensured
all of them had valid values in CC mode.

## Attempt 7: Fix noise env_level in CC mode

**What:** Same pattern as triangle. noi_env_level never set in CC
mode, so noise rendering produced silence.

**Result:** Noise path unblocked, but drums still mostly absent due
to MIDI data issues (see Attempt 10).

## Attempt 8: Apply -12 semitone correction for pulse octave bug

**What:** Mesen capture proved NSF emulator produces pulse periods
exactly half of ground truth (ratio ~2.005 for every note). Applied
-12 correction in period_to_midi().

**Result:** Pulse melody now correct (E4, C4, E4, G4 matches Mesen).
Triangle was confirmed NOT needing this correction (periods matched
between NSF and Mesen — or so we thought).

**The mistake:** We tested triangle period equality by comparing 10
ABSOLUTE period values, which appeared to match. But the note
SEQUENCES were completely different — the NSF triangle was playing
the pulse melody, not the bass line. We didn't compare the actual
musical content until Attempt 9.

## Attempt 9: Discover triangle plays wrong melody entirely

**What:** Deep comparison revealed NSF triangle note sequence
(D3, G4, G3, E3, C3...) is completely different from Mesen
(E2, E2, E2, E2... — the correct bass line).

**Root cause:** py65 6502 emulation runs the SMB sound driver on
wrong code paths. The triangle channel receives what appears to be
a transposed version of the pulse melody instead of the bass.

**Result:** No downstream fix possible. The NSF emulator is
fundamentally producing wrong data for triangle on this game.

## Attempt 10: Build Mesen-to-MIDI converter

**What:** Wrote scripts/mesen_to_midi.py to bypass NSF emulation
entirely and convert Mesen APU capture CSV directly to MIDI.

**Result:** Correct notes on all 4 channels:
- Pulse: 886 + 549 notes (correct pitch, no hack needed)
- Triangle: 605 notes (correct E2 bass line)
- Noise: 103 drum hits (vs 67 from NSF)
- Period jitter filtered (hardware timer +/-1 noise removed)

## What the first test project should have had

Before giving the user anything to test, I should have:

1. **Checked the JSFX install path** (takes 10 seconds)
2. **Copied to AppData + cache bust** (takes 5 seconds)
3. **Run the ASCII check** (takes 2 seconds)
4. **Traced the @sample rendering path** for all 4 channels in CC
   mode, verified every variable has a valid value
5. **Compared the extracted MIDI against the Mesen capture** on at
   least Pulse 2 melody and Triangle bass before declaring pitch
   "fixed"
6. **Used the Mesen capture** (which was already available!) as the
   extraction source instead of the NSF emulator, since we already
   knew the NSF emulator had the octave bug
7. **Listened to the WAV output** from render_wav() — the pipeline
   already generates WAV previews, I should have checked them
8. **Run validate_project.py** with all 5 dimensions and treated
   the routing FAIL as a real issue, not "pre-existing"

## Tools and techniques that were available but not used soon enough

### From Castlevania/Contra sessions (already proven)

- **Mesen capture + trace_compare.py** — frame-level validation
  existed but wasn't used on Mario until the user ran the capture
- **Per-game PROJECT*.md logs** — the pattern of documenting per-note
  analysis was established but not followed for Mario v2
- **validate_project.py 5-dimension check** — was run but failures
  were dismissed instead of investigated
- **render_wav()** — built-in WAV preview was generated but never
  listened to for quality checking

### From blunders.json (already documented)

- **B03 (Unicode)** — should auto-check after every JSFX edit
- **B04 (JSFX cache)** — should auto-bust after every JSFX edit
- **B11 (every track plays all channels)** — the keyboard remap bug
  was the same class; should have been caught in code review
- **B14 (Console ignores CC)** — the fix was right but deployment
  was wrong

### From the fidelity hierarchy (CLAUDE.md)

The authority hierarchy says ROM/Mesen is ground truth. I should
have started with the Mesen capture and only fallen back to NSF
extraction if no capture was available. Instead I spent multiple
rounds patching the NSF path before finally using the ground truth
data that was sitting right there.

## Timeline of waste

| Attempt | What happened | Time cost | Avoidable? |
|---------|--------------|-----------|------------|
| 1-2 | Wrote correct CC code, deployed to wrong path | ~20 min | YES — check install path |
| 3-5 | Fixed deployment, cache, Unicode | ~10 min | YES — automate these checks |
| 6-7 | Fixed env_level for tri/noise in CC mode | ~15 min | YES — trace rendering path |
| 8 | Octave fix (pulse only) | ~10 min | Partly — needed Mesen data |
| 9 | Discovered triangle is fundamentally wrong | ~20 min | YES — compare melodies, not just periods |
| 10 | Built Mesen converter | ~15 min | Should have been step 1 |

Total: ~90 minutes of iteration that could have been ~20 minutes if
I had:
1. Deployed to the right path + cache bust (2 min)
2. Traced all rendering paths in CC mode (5 min)
3. Compared Mesen capture to NSF extraction on all channels (5 min)
4. Built the Mesen converter immediately when the capture arrived (8 min)

## Rules for next time

1. **After ANY JSFX edit:** copy to AppData, rename-bust cache, check ASCII
2. **Before giving user a test project:** compare MIDI output against
   ground truth (Mesen or trace) on ALL channels, not just the one
   that was just fixed
3. **When Mesen capture exists:** use it as extraction source, don't
   try to fix the NSF emulator
4. **When a fix touches @sample:** trace every variable the rendering
   code reads and verify it has a valid value in all modes
5. **Render the WAV and spot-check** before delivering a project
