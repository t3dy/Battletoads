# Too Lazy To Check

Things we should have verified before delivering ANY test project,
and didn't. Each entry describes what was skipped, how long it would
have taken, and what it cost us.

## 1. Where does REAPER load JSFX from?

**Check:** `find AppData/Roaming/REAPER -name "ReapNES_Console*"`
**Time:** 10 seconds
**What happened:** Edited the source file, never copied to install path.
Delivered a project that used the old un-fixed synth. User got silence.
**Cost:** 2 round-trips of "it doesn't work" / "try this".

## 2. Does the JSFX have Unicode?

**Check:** `python -c "any(b>127 for b in open(f,'rb').read())"`
**Time:** 2 seconds
**What happened:** Wrote an em-dash in a comment. JSFX compiler silently
failed. Already documented as B03.
**Cost:** 1 round-trip.

## 3. What does the @sample rendering code READ?

**Check:** Grep for every variable used in the Pulse/Triangle/Noise
rendering sections, verify each has a valid value in both CC and ADSR modes.
**Time:** 5 minutes
**What happened:** Added CC bypass for ADSR processing but didn't check
that `tri_env_level` and `noi_env_level` were still being set. They
defaulted to 0, which killed triangle and noise instantly.
**Cost:** 1 round-trip, user heard pulse but no triangle or drums.

## 4. Is the triangle playing the right melody?

**Check:** Compare first 10 notes of extracted triangle MIDI against the
known Mario bass line (D-E-A repeated).
**Time:** 30 seconds
**What happened:** Assumed triangle was correct because "periods matched"
in an earlier spot-check. Never compared the actual note SEQUENCE. The NSF
emulator was outputting a transposed version of the pulse melody on triangle.
**Cost:** User heard wrong notes on triangle. Multiple debug rounds.

## 5. Where in the capture does the Overworld start?

**Check:** Search for the E4-E4-C4-E4-G4 signature on P2. Or just look
at the capture frame range and check what game state was active.
**Time:** 1 minute
**What happened:** Used `find_music_start()` which triggered on the TITLE
SCREEN music at frame 213. The actual Overworld starts at frame 1626. The
first MIDI output contained 27 seconds of title screen and intro jingles
mixed with the overworld.
**Cost:** 1 round-trip. User heard wrong music, wrong triangle, wrong
everything for the opening.

## 6. Are drums actually present in this section of the capture?

**Check:** Count noise hits in the overworld section (frame 1626+).
**Time:** 30 seconds
**What happened:** Only 1 drum hit in the first 66 seconds of the overworld
section. The Mesen capture was from gameplay where the drum channel was
mostly silent (possibly underground→overworld transition, or the player was
in a section without drums).
**Status:** Still not fixed. Need a fresh capture from World 1-1 start.

## 7. Does the NSF emulation even produce correct data for this game?

**Check:** Compare 5 notes on each channel between NSF extraction and
Mesen capture BEFORE building any pipeline around the NSF data.
**Time:** 5 minutes
**What happened:** Spent 90 minutes patching the NSF path (octave fix,
CC handling, ADSR bypass) before discovering that triangle was fundamentally
wrong. Should have run the Mesen comparison first and gone straight to
Mesen-based extraction.
**Cost:** ~70 minutes of wasted NSF debugging.

## 8. What does the PROJECTMARIO1.md log already tell us?

**Check:** Read the existing analysis before starting work.
**Time:** 2 minutes
**What happened:** The log already documented the uniform 5-step decay
envelope (64>56>48>40>32) and fixed 7-frame note duration. This is the
NSF extraction's view. We should have immediately compared this against
the Mesen capture to check if it matched. It doesn't — the Mesen capture
shows vol starting at 4-5, not 8, and the note durations are different.
**Cost:** Misplaced confidence in the NSF data.

## 9. Does the volume mapping round-trip correctly?

**Check:** NES vol 5 -> CC11 = 5*8 = 40. Synth reads CC11=40 ->
floor(40 * 15 / 127) = floor(4.72) = 4. Original was 5, synth gets 4.
**Time:** 1 minute to verify the formula.
**What happened:** Never checked. The CC11 mapping loses precision at
every value. vol=8 -> CC=64 -> floor(7.56) = 7. Every volume level
except 0 and 15 is reduced by 1 in the round-trip. This makes the pulse
sound thinner than it should.
**Status:** Not yet fixed. The formula `min(127, vol * 8)` should be
`round(vol * 127 / 15)` for lossless round-trip.

## 10. Is the Mesen capture from World 1-1 start, or mid-game?

**Check:** Look at the first 200 frames. If P1/P2 are silent, the game
hasn't started yet. Check when P2 period=339 (E4) first appears.
**Time:** 30 seconds
**What happened:** Assumed the capture started at the overworld. It
actually started on the title screen. The overworld doesn't begin until
frame 1626 (~27 seconds in). Everything before that is title screen
jingles, fanfares, and silence.
**Cost:** First Mesen-based MIDI contained title screen music mixed in.

## What should be on the pre-delivery checklist

Before giving the user ANY test project:

1. JSFX deployed to AppData + cache busted + ASCII verified
2. Compare first 10 notes on EVERY channel against ground truth
3. Compare first CC11 envelope against ground truth
4. Verify noise/drum hits are present and correctly timed
5. Verify the capture section matches the intended song
6. Check the CC11 round-trip formula for precision loss
7. Run validate_project.py and treat ALL failures as blockers
8. Listen to the rendered WAV (or at least check its waveform isn't flat)
