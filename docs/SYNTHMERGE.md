# Synth Merge Plan: One Plugin To Rule Them All

## The Vision

One JSFX synthesizer plugin that:

1. **Plays NES game music from MIDI files at ROM-level accuracy** —
   reads SysEx register data for hardware-exact reproduction, falls
   back to CC11/CC12 when SysEx isn't available
2. **Works with a MIDI keyboard for modern composers** — ADSR envelopes,
   pitch bend, mod wheel, per-game presets that capture each game's
   "sound"
3. **Looks like a vintage analog synth** — knobs, sliders, oscilloscope,
   visual design inspired by Mini Moog / Sequential Circuits Six-Trak /
   classic hardware synths
4. **Shows parameter changes in real time** — sliders and knobs move as
   automation data plays, so you can record video of the synth "performing"
5. **Makes game-to-game differences visible** — the knob positions tell
   you what makes Battletoads sound different from Castlevania

## What Exists Today (6 Separate Files)

```
ReapNES_Console.jsfx  (964 lines, 38 sliders)
  ✓ Best UI (CRT oscilloscope, knobs, faders, ADSR visualization)
  ✓ Sweep unit, vibrato LFO, duty sweep
  ✓ Full ADSR per channel
  ✓ Drum mode with GM mapping
  ✗ NO SysEx register replay
  ✗ NO CC11/CC12 file playback mode

ReapNES_APU2.jsfx  (519 lines, 19 sliders)
  ✓ SysEx register replay (hardware-accurate)
  ✓ CC11/CC12 dual-mode (file vs keyboard)
  ✓ Phase reset from register data
  ✗ NO graphics UI
  ✗ NO sweep unit
  ✗ NO vibrato LFO

ReapNES_APU.jsfx  (914 lines, 24 sliders)
  ✓ Best envelope system (Live Patch auto-detect)
  ✓ CC11/CC12 with cc_active tracking
  ✓ Debug counters
  ✗ NO SysEx replay
  ✗ NO sweep or vibrato

ReapNES_Full.jsfx  (252 lines, 17 sliders)
  ✓ Modular library architecture
  ✓ Sweep via CC74
  ✗ NO envelope, NO CC handling

ReapNES_Instrument.jsfx  (310 lines, 10 sliders)
  ✓ Preset file loading (per-game envelopes)
  ✓ Envelope visualizer with loop markers
  ✗ NO CC handling, NO SysEx

ReapNES_Pulse.jsfx  (170 lines, 11 sliders)
  ✓ Clean minimal pulse-only design
  ✗ Pulse only, no other channels
```

## The Unified Synth: ReapNES Studio

### Architecture

One monolithic JSFX file (~1200-1500 lines) that combines:

**From APU2**: SysEx register replay engine, CC11/CC12 dual-mode,
phase reset, cc_active[] auto-detection

**From Console**: Sweep unit, vibrato LFO, ADSR envelopes, duty
sweep, drum mapping, oscilloscope, visual UI design

**From APU**: Live Patch hybrid detection (most robust cc_active
logic), debug counters, dual sustain modes

**From Instrument**: Per-game preset concept (future — game-specific
knob positions loaded from files)

### Three-Priority Input Cascade

The synth automatically selects its data source per channel:

```
Priority 1: SysEx register data (if present)
  → Raw APU register replay. Hardware-exact.
  → All knobs driven by register state (visible automation).
  → Sweep, phase reset, noise mode — everything.

Priority 2: CC11/CC12 automation (if present, no SysEx)
  → Volume from CC11, duty from CC12.
  → ADSR bypassed. CC data IS the envelope.
  → Knobs show CC-derived values.

Priority 3: ADSR keyboard (no file data)
  → Full ADSR envelope shapes each note.
  → Sweep, vibrato, duty from knob positions.
  → Composer mode — design your own NES sound.
```

**Auto-detection**: First SysEx message on a channel → priority 1.
First CC11/CC12 → priority 2. No file data → priority 3. CC123/CC121
resets back to priority 3.

### Slider Layout (~40 sliders)

```
=== MODE (always visible) ===
Slider 1:  Channel Mode    (P1 / P2 / Tri / Noise / Full APU)
Slider 2:  Input Mode      (Auto / SysEx / CC / Keyboard)
           [Auto is the default — detects from incoming data]

=== PULSE 1 ===
Slider 3:  P1 Duty         (12.5% / 25% / 50% / 75%)
Slider 4:  P1 Volume       (0-15, shows current NES volume)
Slider 5:  P1 Attack       (0-500ms, keyboard mode)
Slider 6:  P1 Decay        (0-500ms)
Slider 7:  P1 Sustain      (0-15)
Slider 8:  P1 Release      (0-500ms)

=== PULSE 2 ===
Slider 9-14: [same layout as P1]

=== TRIANGLE ===
Slider 15: Tri Attack      (0-500ms)
Slider 16: Tri Release     (0-500ms)

=== NOISE / DRUMS ===
Slider 17: Noise Attack    (0-500ms)
Slider 18: Noise Decay     (0-500ms)

=== SWEEP UNIT (affects current pulse channel) ===
Slider 19: Sweep Enable    (Off / On)
Slider 20: Sweep Period    (0-7)
Slider 21: Sweep Direction (Up / Down)
Slider 22: Sweep Shift     (0-7)

=== VIBRATO ===
Slider 23: Vibrato Rate    (0-10 Hz)
Slider 24: Vibrato Depth   (0-100 cents)

=== MIX ===
Slider 25: P1 Level        (0.0-1.0)
Slider 26: P2 Level        (0.0-1.0)
Slider 27: Tri Level       (0.0-1.0)
Slider 28: Noise Level     (0.0-1.0)
Slider 29: Master Gain     (0.0-1.0)

=== DISPLAY ===
Slider 30: Current NES Period  (read-only, shows hardware value)
Slider 31: Current NES Volume  (read-only, 0-15)
Slider 32: Current Duty        (read-only, 0-3)
Slider 33: Input Source        (read-only: SysEx / CC / Keyboard)
```

**Key design**: Sliders 30-33 are **read-only display sliders** that
show what the synth is currently doing. When SysEx data drives the
synth, these sliders move in real time. REAPER can record this as
automation, and the FX window shows the knobs turning — exactly what
Ted wants for video recording.

### Visual UI Design

```
+----------------------------------------------------------+
|  R E A P N E S   S T U D I O                      v2.0  |
|  ═══════════════════════════════════════════════════════  |
|                                                          |
|  ┌─────────────────────────────────────────────────────┐ |
|  │              ╔══ OSCILLOSCOPE ══╗                    │ |
|  │              ║  ~∿~∿~∿~∿~∿~∿  ║                    │ |
|  │              ║  waveform view   ║                    │ |
|  │              ╚══════════════════╝                    │ |
|  └─────────────────────────────────────────────────────┘ |
|                                                          |
|  ┌── PULSE 1 ──┐ ┌── PULSE 2 ──┐ ┌─ TRI ─┐ ┌─ NOISE ─┐|
|  │ [D] [V] [E] │ │ [D] [V] [E] │ │[E]    │ │[A] [D]  │|
|  │  A  D  S  R │ │  A  D  S  R │ │ A   R │ │         │|
|  │ ○○ ○○ ○○ ○○│ │ ○○ ○○ ○○ ○○│ │ ○○ ○○│ │ ○○ ○○  │|
|  └─────────────┘ └─────────────┘ └───────┘ └─────────┘|
|                                                          |
|  ┌── SWEEP ────┐ ┌── VIBRATO ──┐ ┌────── MIX ─────────┐|
|  │ [E] [P][D][S]│ │ [Rate][Dep] │ │ P1  P2  Tri Noi  M│|
|  │ ○○  ○○ ○ ○○ │ │  ○○   ○○   │ │ ▮▮  ▮▮  ▮▮  ▮▮  ▮▮│|
|  └──────────────┘ └─────────────┘ └────────────────────┘|
|                                                          |
|  [SysEx] [CC] [KB]    Game: Battletoads    Song: Lvl 1  |
|  ●        ○    ○       NES Vol: 12  Duty: 50%  Per: 669 |
+----------------------------------------------------------+

Legend:
  [D] = Duty knob   [V] = Volume   [E] = Enable
  A/D/S/R = ADSR knobs (small, grouped)
  ○○ = rotary knob
  ▮▮ = vertical fader
  ● = active input source indicator (lit LED)
```

Design principles:
- Dark background (charcoal/navy), warm amber text and indicators
- Knobs are small circles with position lines (like Moog knobs)
- Faders are vertical strips with luminous caps
- Oscilloscope shows the actual waveform being generated
- Input source LEDs light up to show SysEx/CC/Keyboard mode
- Bottom status bar shows current NES register values in real time

### What Moves During Playback (For Video Recording)

When SysEx data plays:
- **Volume knobs** (P1, P2) track NES volume 0-15 per frame
- **Duty knobs** rotate to show duty cycle changes
- **Period display** shows the raw NES period value
- **Sweep knobs** change when sweep configuration changes
- **Mix faders** could be driven by per-channel enable bits
- **Input source LED** shows "SysEx" lit

When CC11/CC12 data plays:
- **Volume knobs** track CC11 → NES volume conversion
- **Duty knobs** track CC12 → duty conversion
- **Input source LED** shows "CC" lit

When keyboard is played:
- **ADSR envelope visualization** shows the current envelope phase
- **Input source LED** shows "KB" lit

### Implementation Strategy

Phase 1: **Merge audio engine** (~800 lines)
- Start from APU2 (has the most accurate audio engine)
- Add Console's sweep unit and vibrato LFO
- Add APU's Live Patch cc_active detection (most robust version)
- Add Console's ADSR envelopes for keyboard mode
- Wire up the three-priority input cascade
- Test: file playback sounds identical to current APU2

Phase 2: **Add visual UI** (~400 lines)
- Port Console's @gfx section
- Add read-only display sliders that track internal state
- Add input source indicators
- Add oscilloscope (already in Console)
- Test: open FX window, play file, see knobs moving

Phase 3: **Video-ready automation**
- Ensure REAPER can record slider movements as automation lanes
- Verify that screen-recording the FX window captures knob movement
- Test with one full Battletoads song: record video, check it looks good

Phase 4: **Per-game presets**
- Port Instrument's preset loading concept
- Save/load ADSR + sweep + vibrato settings per game
- Load preset from game name in MIDI metadata track
- "Battletoads preset" vs "Castlevania preset" vs "Mega Man preset"

### Files to Produce

```
studio/jsfx/ReapNES_Studio.jsfx     — the unified synth
studio/presets/Battletoads.json      — game-specific knob positions
studio/presets/Castlevania.json
studio/presets/Contra.json
studio/presets/MegaMan.json
```

### What Happens to the Old Files

Keep them for reference but they are superseded:
```
studio/jsfx/ReapNES_Console.jsfx    → merged into Studio
studio/jsfx/ReapNES_APU2.jsfx       → merged into Studio
studio/jsfx/ReapNES_APU.jsfx        → merged into Studio
studio/jsfx/ReapNES_Full.jsfx       → library approach abandoned
studio/jsfx/ReapNES_Instrument.jsfx → preset concept kept
studio/jsfx/ReapNES_Pulse.jsfx      → subsumed
```

### The Two Problems This Solves

**Problem 1: "Which synth do I use?"**

Answer: ReapNES Studio. Always. It auto-detects the input and does
the right thing. Load a trace-derived MIDI with SysEx → hardware-
accurate playback. Load an NSF-derived MIDI with CC11/CC12 → CC-driven
playback. Plug in a keyboard → ADSR envelopes.

**Problem 2: "The notes sound wrong"**

The SysEx path bypasses all MIDI encoding issues (sweep trills,
1-frame arpeggios, semitone quantization). The period register goes
directly from the Mesen capture → SysEx bytes → synth waveform
generator. No intermediate MIDI note conversion needed. The knobs
show you what's happening at every frame.

### Open Questions

1. **JSFX slider limit**: REAPER JSFX supports up to 64 sliders.
   We need ~35-40. Should be fine.

2. **@gfx performance**: Console's oscilloscope + knob drawing is
   already working. Adding more elements may slow down the UI refresh.
   May need to throttle visual updates to 30fps.

3. **Automation recording**: Need to test whether REAPER records
   slider changes driven by @block (MIDI processing) as automation.
   If not, may need to use slider_automate() or similar JSFX API.

4. **Per-game preset loading**: JSFX can read files via
   file_open/file_string. Need to design a simple preset format
   that captures the knob positions for each game.
