# Kid Icarus Takeaways: What This Rip Teaches Us About Future ROMs

## The Core Lesson

Kid Icarus broke an assumption we didn't know we were making: that the NSF file and the game ROM contain the same music. Every previous game in our pipeline confirmed that assumption. Kid Icarus destroyed it. The takeaway isn't just "check for FDS games" --- it's that **every assumption about how a ROM encodes music is a hypothesis until the trace confirms it.**

## Pre-Flight Checks We Should Always Run

### 1. Compare the NSF Against a Trace Before Trusting It

We built 34 REAPER projects from the Kid Icarus NSF before anyone listened critically. A 30-second Mesen capture of Song 1 would have revealed the octave error and the wrong Sq2 arrangement immediately.

**New rule:** For every new game, capture 10 seconds of one song in Mesen and cross-correlate the pulse periods against the NSF output before batch-extracting. This takes 5 minutes and catches:
- Platform mismatches (FDS vs NES, PAL vs NTSC, JP vs US)
- Octave errors from wrong clock divisors
- Channel arrangement differences
- Broken noise extraction

The cross-correlation is simple: extract the first 10 period changes from the trace, convert to MIDI notes, compare against the first 10 notes in the NSF MIDI. If they're off by a constant (like +12), you have a systematic error. If they don't correlate at all, you have a different arrangement.

### 2. Check the NSF Header for Expansion Audio

```
Expansion byte ($7B in header):
  bit 0: VRC6
  bit 1: VRC7
  bit 2: FDS
  bit 3: MMC5
  bit 4: Namco 163
  bit 5: Sunsoft 5B
```

If any expansion bit is set, the NSF uses hardware the standard NES doesn't have. The music was written for a different sound chip configuration. The NES cartridge version (if one exists) will have a different arrangement.

Kid Icarus had bit 2 (FDS) set. We could have caught this from the filename alone: `(FDS)` was right there in the NSF title. Future workflow: **read the NSF header before extracting. If expansion != 0, flag it.**

### 3. Count Songs in Both Sources

The FDS NSF had 34 songs. The NES ROM's pointer table has 10 entries. That 3.4x ratio is a red flag --- even accounting for SFX entries, the numbers should be in the same ballpark if they're the same music. A large discrepancy means different content.

### 4. Check the ROM's Mapper and Origin

Mapper 1 (MMC1) with 128KB PRG and 0KB CHR, plus a CDL showing all music code in one switchable bank --- that's a specific hardware profile. More importantly, Kid Icarus (UE) is a known port from a different platform. Many NES games have this history:

- **FDS to NES**: Kid Icarus, Metroid, Zelda, Castlevania (JP FDS version differs)
- **Arcade to NES**: Contra, Ghosts 'n Goblins, Gradius
- **JP to US**: Castlevania III (VRC6 expansion in JP, standard APU in US)

Any of these transitions can change the music encoding, arrangement, or channel count. **When you know a game has platform variants, always verify which version the NSF represents.**

## What the ROM Taught Us About Engine Diversity

### Period Table Formats We've Now Seen

| Game | Format | Location | Notes |
|------|--------|----------|-------|
| Castlevania | Split lo/hi arrays | Inline | Standard Konami |
| Contra | Split lo/hi arrays | Bank 1 | Same family as CV1 |
| Battletoads | Contiguous 16-bit LE | $8E22 | 60 entries, C2-B6 |
| Wizards & Warriors | Two separate tables | $EFD9, $F000 | One big-endian! |
| Castlevania II | Direct 16-bit | $01C1D | 32 entries |
| Kid Icarus | Interleaved hi/lo pairs | $AB18 | 40 entries, C#3-E6 |

Every game is different. Don't assume the next game's period table will look like any of these. The search strategy that works:

1. Find APU register writes ($4002/$4003 for pulse period) in the code
2. Trace backwards to find where the period value comes from
3. That leads to the table (or to a calculation, in rare cases)

### Song Organization Models

| Model | Games | How It Works |
|-------|-------|-------------|
| Flat pointer table | CV1, Contra, W&W | Song N → address of channel data |
| Area-indexed blocks | Kid Icarus | Area → block of channel configs → patterns |
| Phrase library | CV2 | Songs chain short reusable phrases |
| Unknown | Ultima, Battletoads | Not fully mapped yet |

The flat pointer table is the easiest to work with, but don't expect it. Kid Icarus's area-based system means the "same song" can use different patterns depending on game state. Any game with environmental music (different dungeon themes, area variations) might use a similar scheme.

### Game Integration Levels

| Level | Games | Implication |
|-------|-------|------------|
| **Isolated** | CV1, Contra, W&W, Ultima | Music driver is self-contained. NSF works perfectly. Standalone harness is trivial. |
| **Lightly coupled** | Battletoads | Driver reads a few game state bytes but is mostly independent |
| **Deeply integrated** | Kid Icarus | Song init contains game logic (area checks, progression flags, conditional branching). Standalone harness must simulate game state. |

When you see game logic mixed into the music init routines, you know the NSF might not tell the full story. The NSF's init routine is a simplified wrapper --- it can't replicate the game state that the real init reads.

## Practical Workflow Changes

### The 5-Minute Smoke Test

Before batch-extracting any new game:

```
1. Run NSF extraction for Song 1 (30 seconds)
2. Open the game in Mesen, start Song 1
3. Capture 10 seconds of APU state
4. Compare first 10 Sq1 period changes:
   - Match? NSF is good. Proceed with batch.
   - Off by constant? Systematic error (octave, clock). Investigate.
   - No correlation? Different arrangement. NSF is wrong version.
5. Check noise: does the NSF have noise events? Does the trace?
```

This catches Kid Icarus-class problems in 5 minutes instead of after 34 REAPER projects are built.

### The NSF Header Checklist

```
[ ] Expansion byte == 0? (If not, flag platform mismatch risk)
[ ] Song count reasonable for game? (10-20 for most action games)
[ ] Region byte matches ROM? (NTSC vs PAL)
[ ] Bankswitch bytes present? (Complex memory layout = harder to harness)
[ ] Title matches the ROM you have? (JP vs US vs EU naming)
```

### When to Abandon NSF and Go ROM-First

- NSF has expansion audio but your ROM doesn't
- NSF song count differs wildly from expected
- Smoke test shows wrong pitches or missing channels
- The game is known to have platform-variant music
- NSF noise/drum extraction fails (common with games that use the noise channel sparingly)

### ROM Investigation Order

When you do need to crack the ROM's music engine:

```
1. CDL first — find which code actually runs during gameplay
2. Find APU writes — STA $4000-$4015 in the executed code regions
3. Cluster the writes — they'll group into init, play, and envelope routines
4. Find the period table — search for descending sequences near the APU write cluster
5. Find the song pointer table — look for ASL A; TAX; LDA table,X patterns
6. Check how songs are organized — flat table? area-indexed? phrase-based?
7. Build the harness — only after you understand the init and play entry points
```

Don't disassemble everything. The CDL tells you which code matters. For Kid Icarus, this eliminated 3KB of code ($AE00-$BB00) that looked relevant from static analysis but was never executed during gameplay.

## The Meta-Lesson

Every ROM rip starts with assumptions borrowed from the last successful rip. The more games you crack, the more assumptions accumulate. Kid Icarus broke the biggest one (NSF = ROM) and several smaller ones (period table format, song organization, game integration level).

The defense against accumulated assumptions is **always verify against the trace before claiming anything works.** The trace is the hardware telling you what actually happens. Everything else --- NSF output, parser output, your mental model of how the engine works --- is hypothesis until the trace confirms it.

The engines will keep surprising us. Castlevania III (JP) uses VRC6 expansion with 6 channels. Mega Man games might use a completely different driver per title. Some games generate music algorithmically instead of reading from tables. The only constant is that the APU registers at $4000-$4017 are where the rubber meets the road. Whatever the engine does internally, it has to write to those registers to make sound. Start there, work backwards, and let the trace tell you if you got it right.
