# Kid Icarus: The Famicom Ghost in the NES Machine

## The Problem Nobody Warned Us About

Kid Icarus looked like a straightforward NSF extraction. 34 songs came out, REAPER projects built, everything ran. The user listened and said "it starts well but then gets weird." That launched an investigation that uncovered something none of our previous games had presented: **the NSF and the ROM are from two different versions of the game.**

## What We Found

### The FDS/NES Split

Kid Icarus was originally a **Famicom Disk System** game (1986), later ported to a **NES cartridge** for the Western market. The NSF file in our library is ripped from the FDS original. The user's ROM is the NES cartridge port. These are not the same music.

The FDS version has 5 audio channels (4 standard APU + 1 FDS wavetable). The NES cartridge has 4. When Nintendo ported the game, they **rearranged the music** to fit 4 channels. The NSF we extracted is playing the FDS arrangement through FDS sound hardware, not the NES arrangement the user actually hears in-game.

### The Octave Problem

The first symptom: Mesen trace showed period 105 where the NSF emulator produced period 52. Every pulse note was exactly **half the period** --- one octave too high. This isn't a bug in our pipeline; it's a fundamental difference between the FDS and NES sound hardware clocks.

Cross-correlating the full trace against the corrected NSF output:

| Channel | Match Rate | Issue |
|---------|-----------|-------|
| **Sq1** | 100% (with -12 correction) | Same melody, wrong octave |
| **Sq2** | 24.7% (no offset fixes it) | **Completely different part** |
| **Triangle** | 100% | Already correct |
| **Noise** | 0% (NSF: 1 note; Trace: 11 hits) | NSF noise extraction broken |

Square 2 isn't an octave problem --- the FDS and NES versions have **genuinely different Sq2 arrangements**. The FDS version used its 5th wavetable channel for material that the NES port redistributed across the standard 4 channels.

### The Noise Channel

The NSF extraction captured exactly 1 noise note spanning 75 seconds. The Mesen trace shows 11 clean drum hits, all at period 15, vol 6, spaced ~96 frames apart. The NSF's py65 emulator runs the FDS driver code, which apparently handles noise differently (or not at all) compared to the NES cart driver.

## Novel Challenges (Things We Haven't Seen Before)

### 1. Cross-Platform NSF Mismatch

Every previous game in our pipeline --- Castlevania, Contra, Battletoads, Wizards & Warriors --- used the same ROM for both NSF extraction and trace validation. The NSF *is* the ROM's sound driver running in isolation. For Kid Icarus, the NSF is from a **different platform entirely**. The NSF runs FDS 6502 code; the cartridge runs NES 6502 code. Same CPU, different sound hardware, different music data, different arrangement.

This is the first time our "NSF is ground truth" assumption has been fundamentally wrong --- not due to emulation inaccuracy, but because the NSF represents a different product.

### 2. The Music Engine Is Deeply Game-Integrated

When we started reverse-engineering the NES cart ROM, we found the music engine in bank 4 ($A008-$AAB1). But unlike Konami's clean music drivers (Castlevania, Contra) where song init is a simple pointer-table lookup, Kid Icarus's song init routines contain **game logic**. Song 1's init at $8365 reads area state from ZP $3A, adjusts counters at $3E/$3F, checks game progression, and conditionally modifies the music. Song 7's init checks multiple game flags before deciding what to play.

The music isn't just "play song N" --- it's "play the appropriate music for the current game state." This makes it much harder to drive from a standalone harness.

### 3. Area-Based Music Lookup

The music data is organized by game area, not by song number. The table at $9370 has 4 entries (areas 0-3), each pointing to a block of channel data structures. The init routine at $855A uses the area index to select which set of channel patterns to load. This means the same "song" might sound different depending on which area the player is in --- a level of musical dynamism we haven't seen in our other games.

### 4. Interleaved Period Table

The period table at $AB18 uses interleaved hi/lo byte pairs (40 entries, C#3 to E6), which is different from the split lo-table/hi-table format used by Konami games, and different from the single-byte index tables used by Rare games.

## Familiar Challenges (Things We've Seen Before)

### Triangle Octave

Triangle being 1 octave lower than pulse for the same period --- hardware fact, same as every other NES game. The NSF extraction already handles this correctly.

### CDL-Guided Code Discovery

Using Mesen's Code/Data Logger to identify which code actually executes during gameplay --- same technique we used for Battletoads. The CDL showed that only $A001-$AAB1 contains executed music code; the $AE00-$BB00 range (which looked promising from static analysis) was never touched.

### The "Zero Parse Errors" Trap (Avoided)

We didn't fall into the trap of assuming the NSF extraction was correct just because it ran without errors. The 34 MIDIs all looked structurally fine --- correct note counts, proper CC11/CC12 automation, clean REAPER projects. But they were playing the wrong music. This is exactly the failure mode our execution semantics validation protocol was designed to catch.

## Current State

- **Song 1 Mesen capture**: validated, MIDI and REAPER project built from trace (`Kid_Icarus_01_Song_1_mesen_v1.mid`)
- **ROM analysis**: Music engine identified in bank 4, period table decoded, song pointer table found (10 songs for NES cart vs 34 in FDS NSF)
- **Next step**: Build a py65 harness that loads the NES ROM's music bank and drives it directly, extracting all 10 songs without needing manual Mesen captures

## The Lesson

**Never assume the NSF matches the ROM.** For most games, the NSF IS the ROM's sound driver code running in an emulated sandbox --- same bytes, same behavior. But for games that exist in multiple platform versions (FDS/NES, PAL/NTSC, JP/US), the NSF may represent a completely different version of the music. The trace is the only ground truth. The ROM code is the ultimate source.
