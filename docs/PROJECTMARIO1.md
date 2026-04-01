# Project Log: Super Mario Bros

## Track Analyzed
`Super_Mario_Bros._01_Running_About_v1.mid` (Overworld Theme)

## What Was Wrong

### RPP Structure (Fixed)
- RPP used minimal header (~10 lines) missing ENVATTACH, SAMPLERATE,
  METRONOME, and 40+ other fields required for MIDI input initialization
- Unarmed tracks had `REC 0 0` which caused REAPER to forget MIDI routing
- Missing PANLAWFLAGS, SHOWINMIX, FIXEDLANES, SEL, TRACKHEIGHT, INQ, WNDRECT
- Used ReapNES_APU.jsfx (15 sliders, no keyboard mode) instead of Console (38 sliders)
- Keyboard Mode was OFF (slider34=0)

### Synth Behavior (Outstanding)
- Console synth ignores CC11/CC12 from the MIDI file
- ADSR envelopes play instead of the ground-truth per-frame volume data
- Result: every note sounds the same instead of having the distinctive
  Mario staccato decay

## How We Fixed It
- Rewrote generate_project.py with full RPP header from Console_Test.rpp
- All tracks now use `REC {0|1} 5088 1 0 0 0 0 0` (MIDI routing preserved)
- Switched to ReapNES_Console.jsfx with Keyboard Mode ON
- Added all missing track fields
- Remaining: port CC11/CC12 handling from APU to Console synth

## What's In The MIDI File

### Envelope Character
Super Mario Bros has a **uniform staccato envelope**. Every single note on
both pulse channels follows the identical 5-step volume decay:

```
CC11: 64 > 56 > 48 > 40 > 32 (over 5 frames)
```

This is the Mario sound — bright attack, quick linear decay, then the note
continues at reduced volume until the period changes. The sound driver
applies the same envelope to every note regardless of pitch or duration.

### Note Durations
**Remarkably uniform.** Both pulse channels have ALL notes at exactly 112
ticks (7 frames, 116ms). This is the sound driver's fixed note length —
Mario's overworld theme plays every note for exactly 7 frames, no
exceptions. The perception of "long" and "short" notes comes entirely from
the volume envelope, not from note duration.

| Channel | Notes | Duration | CC11/note | Envelope Shape |
|---------|-------|----------|-----------|----------------|
| Pulse 1 | 314 | ALL 112t (7f, 116ms) | 5.0 | 64>56>48>40>32 |
| Pulse 2 | 302 | ALL 112t (7f, 116ms) | 5.0 | 64>56>48>40>32 |
| Triangle | 239 | 144-1152t (9-72f) | 1.0 (gate) | CC11=127 always |
| Noise | 67 | 96-37344t (6-2334f) | 0 | velocity=96 |

### Velocity
All pulse notes have velocity 64. All triangle notes have velocity 127.
The Mario driver doesn't vary velocity — all dynamic shaping is through
CC11 volume automation.

### Duty Cycle
Only 1 CC12 message total (duty=50%). Mario uses a single duty cycle for
the entire song. No per-note timbre variation — the iconic Mario sound is
50% square wave throughout.

### Triangle Bass
Highly varied durations (150ms to 1.2 seconds). Triangle carries the bass
line with legato phrasing — long sustained notes under the staccato melody.
No volume control (CC11=127 always) — articulation is pure duration.

### What This Means For Playback Fidelity
The Mario overworld theme is straightforward to reproduce faithfully:
- Fixed envelope (same 5-step decay for every note)
- Fixed duration (7 frames)
- Fixed duty (50%)
- No vibrato, no pitch bends, no duty changes

The ONLY thing preventing accurate playback right now is the Console synth
ignoring CC11. Once CC11 drives the volume, every note will have the
correct 64>56>48>40>32 decay shape, which is what makes it sound like Mario.
