# Kid Icarus: Code as Music

## The Discovery

After tracing the song routing through three layers of indirection, we arrived at the dispatch targets expecting to find music data pointers. Instead, we found **6502 machine code**. The dispatch targets at $A47E, $A4A9, $A5B2, $A55E, $A65E, $A69C, $A6F5, etc. are not addresses of note data — they are the addresses of executable subroutines that write to APU registers directly.

Kid Icarus's music isn't stored as data. It's stored as code.

## What This Means

### In Every Other Game We've Ripped

The pattern is the same:

```
Song Data (ROM bytes) → Music Driver (6502 code) → APU Registers (hardware)
```

There's a clear separation between **data** (note streams, period tables, envelope tables) and **code** (the driver that reads data and writes APU registers). The driver is generic — it plays any song by reading from different data pointers. This is why extraction works: find the data pointers, read the data, decode the format.

Castlevania, Contra, Battletoads, Wizards & Warriors — all follow this pattern. The driver code is reused across songs. The song identity lives entirely in the data.

### In Kid Icarus

```
Song Code (6502 subroutines) → APU Registers (hardware)
```

There is no generic driver. Each song IS a subroutine. The "data" and the "code" are the same thing. The subroutine at $A47E doesn't read note data from a table — it has note timing, pitch changes, and envelope shapes encoded as branch instructions, counter checks, and hardcoded register writes.

Here's actual code from the Song 1 area entry point:

```
$A47E: LDA #$02        ; load a config value
$A480: LDY #$16        ; load a timing parameter
$A482: BNE $A461       ; always branch to shared note-writing code
...
$A484: LDA #$06        ; note index
$A486: LDY #$0A        ; duration/envelope selector
$A488: JSR $A36E       ; CALL the note-writing subroutine
$A48B: LDA #$09        ; next state value
$A48D: STA $0360       ; save state for next frame
$A490: RTS             ; return (wait for next frame)
```

The `JSR $A36E` subroutine takes A (note index) and Y (parameter) and writes the appropriate values to $4000-$400B. Then the routine stores a state value ($0360) and returns. On the next frame, the song routine is called again, reads the state from $0360, and picks up where it left off.

Each frame processes one "tick" of the song — loading the next note, checking if a duration counter has expired, and branching to the appropriate section. The song's structure (verse, chorus, bridge, loop) is expressed as **control flow** — JMPs, BNEs, and state comparisons — not as data markers.

## Why This Matters for the Harness

### The Generic Harness Can't Work

Our standard harness approach is:

1. Find the song data pointer
2. Set up the driver with that pointer
3. Call the play routine once per frame
4. Capture APU writes

This doesn't work for Kid Icarus because there IS no data pointer. The "pointer" is the entry address of a subroutine. The "driver" is the subroutine itself. And the per-frame call isn't to a generic play routine — it's to the song's own state machine, which advances by one tick each call.

### What Needs to Change

Instead of feeding data through a generic player, we need to call each song's subroutine directly, once per frame, and let it manage its own state. The harness becomes:

```python
# For each song:
dispatch_addr = song_dispatch_table[song_index]
for frame in range(num_frames):
    call(dispatch_addr)  # the song advances by one tick
    capture_apu_writes()
```

But there are complications:

1. **Which dispatch address?** The $A1B0-$A20C config table has ~24 entries with dispatch vectors. Not all are songs — some are SFX, some are area transitions.

2. **Shared subroutines.** The song code calls shared routines ($A36E for note writing, $A3C3 for timing checks, $A396 for channel setup). These shared routines read and write to a common state area ($0300-$03FF). The harness must not clear this state between frames.

3. **State machine continuity.** Each song stores its "where am I in the melody" state in RAM ($0360, $0349, etc). The per-frame call CONTINUES from where the last call left off. If the harness resets registers between calls, the song loses its place.

4. **The NMI task table.** In the real game, the NMI handler walks a task table at $0200, calling each registered task once per frame. The music song routine is one of those tasks. The harness needs to replicate this — call the song routine once per NMI-equivalent, with the right bank mapped and the right state preserved.

## The Two-Engine Architecture

Kid Icarus actually has TWO music systems:

### System 1: Code-as-Music ($A4xx-$A8xx routines)

Used for in-game music (overworld, underworld, fortress, boss, etc). Each song is a 6502 subroutine. The songs are registered via the $A1B0-$A20C config table and dispatched through the NMI task table. Per-frame updates call the song subroutine directly.

This is the system that produces the music heard during gameplay — and the one our Mesen trace captured.

### System 2: Data-Driven Player ($AC88 configs + $A9AF play routine)

Used for a secondary set of sounds (possibly title screen, game over, ending, or SFX). Has 12 channel config blocks in $AC88, each with 4 data pointers. Uses the $A9AF per-frame player that reads note bytes from a data stream. Controlled by $0350 (computed from $E8 bitmask) and $038D (active flag).

This system works like a conventional music driver and our harness successfully drives it — but it's not the system playing the music we hear in the trace.

## What This Teaches Us

### For Future ROM Rips

1. **Not all music engines separate code from data.** Early games (1986) sometimes encode music directly in 6502 instructions. This is rare but not unique — some Atari 2600 games and early NES titles do this.

2. **The CDL is essential.** The Code/Data Logger showed us that the $A4xx-$A8xx range was executed code, not data. Without the CDL, we would have tried to parse those bytes as note data and gotten nonsense.

3. **Two music systems can coexist.** Kid Icarus has both a code-based and data-based music engine. Each handles different sounds. When one doesn't match the trace, check for the other.

4. **Code-as-music is hostile to standalone extraction.** You can't just "read the data" — you need to run the actual 6502 code. The NSF approach (wrapping the driver in a harness) doesn't work when there's no generic driver to wrap.

### The Practical Path Forward

For Kid Icarus, the most reliable extraction approach is **Mesen trace capture per song**. The music code is too deeply integrated with game state for a standalone harness. Each song needs:

1. Play the game until the target song starts
2. Capture 1-2 minutes of APU state via Mesen
3. Convert trace to MIDI via `mesen_to_midi.py`
4. Generate REAPER project via `generate_project.py`

With ~10 distinct songs and ~2 minutes per capture, the full extraction takes about 20 minutes of gameplay plus 15 minutes of processing. Not as automated as the Castlevania pipeline, but reliable and ground-truth by definition.

The alternative — fully emulating the game engine in py65, including bank switching, NMI dispatch, task tables, and per-song state machines — would take days of reverse engineering for diminishing returns. Sometimes the right answer is to use the emulator that already works (Mesen) instead of building a new one.
