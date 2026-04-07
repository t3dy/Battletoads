# Kid Icarus: The Brute Force Approach

## Where We Are

We've reverse-engineered the Kid Icarus NES cart music engine deep enough to know:

1. **The period table** (40 notes, $AAFA-$AB6A, NTSC standard)
2. **The per-frame play routine** ($A9AF → processes 4 channels → writes $4000-$400F)
3. **12 valid channel config blocks** (in $AC88, indexed via $ABAB lookup)
4. **The config format** (13 bytes: transpose, flags, envelope IDs, 4 channel data pointers)
5. **The $0350 → config mapping** (computed from $E8 bitmask via bit-position counting at $AC0D)
6. **The play routine works** (harness produces real APU writes with correct-looking periods)

What we DON'T have: which of the 12 configs is which song. The game's song routing involves three layers of game-state-dependent logic, area tables, and dispatch through a table at $ABB7 with multiple code paths. Fully reverse-engineering that routing is possible but expensive.

## The Brute Force Alternative

There are only 12 configs. That's a tiny search space. Instead of understanding the routing, we test all 12 configs and identify them by matching against known ground truth.

### Step 1: Extract All 12 Configs

For each config index 0-11, set up the harness:

```python
cpu.memory[0x0350] = song_idx
call(0xA896)   # load 13-byte config into $032B-$0337
# Play N frames via call(0xA9AF) per frame
# Capture all APU writes
```

This gives us 12 raw APU capture streams — the same format as a Mesen trace. Each stream contains per-frame period, volume, duty, and sweep writes for all 4 channels.

### Step 2: Convert to Audio-Comparable Format

Feed each capture through `mesen_to_midi.py`'s logic (or directly through the period → MIDI note conversion). This produces 12 MIDI files — one per config. We can also render to WAV for ear-checking.

### Step 3: Identify by Matching

Three matching strategies, from cheapest to most expensive:

**Strategy A: Period Fingerprint (automated, no human needed)**

Each song has a unique melodic fingerprint — the sequence of the first 10-20 Sq1 pitch changes. Compare each config's fingerprint against:
- The Song 1 Mesen trace (we have this — first 5 periods are 105, 141, 105, 83, 105)
- NSF MIDI files (with -12 octave correction for pulse, already verified on Sq1)

For the NSF comparison, the FDS NSF has 34 songs. Many are SFX/jingles. The ~10 real music songs should have Sq1 period sequences that, when octave-corrected, match some of our 12 configs. The arrangement differs on Sq2 (proven by our trace analysis), but Sq1 melody should be the same or similar between FDS and NES versions.

**Strategy B: Ear-Check (human, fast)**

Play each of the 12 WAV renders for 10 seconds. A human who knows the game can identify "that's the underworld theme, that's the overworld, that's the fortress" in about 2 minutes total.

**Strategy C: Multi-Trace (human + automated)**

Capture 2-3 more Mesen traces from different game locations (title screen, fortress, boss). Match those traces against the 12 configs. Combined with the Song 1 trace we already have, this would identify 4 of 12 songs with 100% certainty, and the remaining 8 by process of elimination.

## Why This Works Despite Not Understanding the Routing

The routing logic is just a mapping function: game state → config index. The music data itself is independent of the routing. Once we have config index → channel pointers, we can play any song without the game engine.

Think of it like a jukebox. We don't need to understand the coin mechanism and button wiring to play every record — we just need to know which slot holds which disc. We can figure that out by playing each slot and listening.

## The Current Blocker and How to Fix It

Our harness tests showed that none of the 12 configs produce the trace's period sequence [105, 141, 105, 83, 105]. This means one of:

1. **The init state is wrong.** The play routine reads state variables ($032B transpose, $032E envelope mode, $0340 duration counters, etc.) that need specific values. The $A896 config loader sets some of these, but the dispatch targets at $AC3F/$AC4C/$AC52/$AC58/$AC5E set sweep parameters ($0344/$0345) via $A8CF before calling $A893. We may need to call the full dispatch chain, not just $A896.

2. **The configs 8-11 need the +8 path.** The $AC1D routine adds 8 to $0350 after the initial bit-decode. Configs 8-11 ($0350 = 8,9,10,11) map to $ABAB indices 104, 117, 78, 91 which point to different music data blocks. But our +8 test showed invalid pointers (out of bank 4 range) — meaning configs 8-11 may require a different bank to be loaded.

3. **The song data is in a different bank.** Kid Icarus uses MMC1 (mapper 1) with bank switching. The music engine is in bank 4, but the music DATA for some songs might be in banks 5 or 6. The game normally has the correct bank mapped when the music init runs. Our harness only loads bank 4.

### Fix Plan

**Immediate test**: Load ALL banks (0-7) into a flat memory image, try all configs with the full dispatch chain ($AC3F path), and check if any produce period 105.

**If that fails**: Use Mesen's debugger to set a breakpoint on the $4002 write (period lo register) and check what value is in $0350 when period 105 is written. This directly tells us which config is active during Song 1.

**If we want to skip debugging**: Capture 5 more seconds of Mesen trace for Songs 2 and 3 (just enter the fortress and the shop in-game). Three traces would triangulate the config mapping for at least 3 of 12 songs, which is enough to establish the pattern.

## What 12 Songs Gets Us

The NES cartridge has 10 song entries in the $81F5 pointer table (the game state dispatcher), but the actual music lives in 12 channel config blocks. That's likely:

- Overworld / Underworld / Fortress / Boss themes (~4 main songs)
- Title screen / Game over / Ending (~3 event songs)
- Shop / Sacred Chamber / Treasure Room (~3 location songs)
- Possibly 2 variants or unused entries

The FDS NSF had 34 entries, but only 12 were real music (Songs 1-12 had substantial note counts; 13-34 were SFX/jingles). The NES cart probably has the same musical content, just rearranged.

## Timeline

1. Fix the bank-switching issue (try loading banks 5-6 alongside bank 4): **30 minutes**
2. Run all 12 configs through the fixed harness: **15 minutes**
3. Convert to MIDI/WAV: **15 minutes**
4. Identify songs (ear-check or trace-match): **15 minutes**
5. Build final REAPER projects: **30 minutes**

Total: about 2 hours of machine time to go from "12 unnamed configs" to "12 named, validated REAPER projects with correct NES cartridge audio."
