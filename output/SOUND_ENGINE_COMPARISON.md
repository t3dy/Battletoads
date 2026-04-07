# NES Sound Engine Comparison: Lessons From Seven Games

A comparative analysis of every music driver we've reverse-engineered or extracted in the ReapNES pipeline. Each game taught something different about how NES developers solved the problem of making music with 4 channels and no dedicated sound CPU.

## The Lineup

| Game | Developer | Year | Driver Family | Mapper | Extraction Route | Validation Rung |
|------|-----------|------|--------------|--------|-----------------|-----------------|
| Castlevania | Konami | 1986 | Maezawa | 2 (UxROM) | NSF + Trace | 4 (trusted) |
| Contra | Konami | 1988 | Maezawa variant | 2 (UxROM) | NSF + Trace | 3+ (partial) |
| Battletoads | Rare | 1991 | Rare custom | 7 (AxROM) | NSF + ROM parser | 1 (parser-aligned) |
| Wizards & Warriors | Rare | 1987 | Rare custom | 7 (AxROM) | NSF + Trace | 2-3 (partial) |
| Castlevania II | Konami | 1987 | Fujio | 1 (MMC1) | ROM trace | Investigation |
| Ultima: Quest of the Avatar | FCI/Origin | 1990 | FCI custom | Bankswitched | NSF only | NSF complete |
| Kid Icarus | Nintendo R&D1 | 1986 | Nintendo custom | 1 (MMC1) | NSF (FDS) + Trace | Trace WIP |

## Engine Architecture Comparison

### Konami Maezawa Family (Castlevania, Contra)

The most well-understood engines in our pipeline. Both games share the same driver codebase with game-specific parameters.

**How notes work:** Flat byte streams with inline commands. DX commands signal configuration changes. Each byte is either a note index (into a shared period table) or a command opcode.

**Envelope model:**
- **Castlevania**: Parametric two-phase decay. Two parameters (fade_start, fade_step) define the envelope shape. Fast 4-step patterns like 32>24>16>8 give CV1 its distinctive percussive attack.
- **Contra**: 54 pre-built lookup tables. Each table is a sequence of per-frame volume bytes, terminated by $FF which triggers a decrescendo phase. The decrescendo uses a multiplication formula: `(mul * dur) >> 4`. This is more flexible than CV1's parametric model but harder to reverse-engineer.

**Key structural difference:** DX commands take 2 extra bytes in CV1 but 3 bytes in Contra. This was the source of our most expensive early mistake --- assuming same driver = same byte format.

**What makes Konami clean:** Song init is a simple pointer-table lookup. No game state involved. The music driver is fully self-contained, making NSF extraction reliable and trace validation straightforward.

### Konami Fujio Family (Castlevania II)

Same company, completely different architecture.

**How notes work:** Phrase library system. 30 short phrases are chained together to form songs. Each phrase is a compact pattern, not a flat stream. This is closer to a tracker module than a linear score.

**Period table:** 32 entries at ROM $01C1D. Same frequencies as Maezawa but with direct indexing (no octave shift byte). Combined note byte format packs duration class and period index into a single byte.

**Unique challenge:** Period write jitter --- the hardware shows periods as N and N+2 on alternating frames because the driver writes the low and high bytes of the period register across two separate frames. This creates phantom "notes" in naive extractors.

**Volume:** Max volume capped at 6 (not the usual 15). Unknown whether this is the envelope system or a deliberate design choice.

### Rare Custom Engines (Battletoads, Wizards & Warriors)

Two games from the same developer with related but distinct engines.

**Battletoads:**
- Note encoding: values >= $81 are notes, $80 is rest, $00-$7F are commands
- Duration: dual-mode system (inline when a flag is clear, persistent via command otherwise)
- 60-note period table at $8E22 (C2-B6)
- Transposition: per-channel register with absolute, relative, and all-channel commands
- Software volume: $0352,X (0-15) ORed into APU register, with ramp and oscillate modes
- Tempo: game-specific per-song values driving a frames-per-tick accumulator
- The most complex command set we've encountered: ~20 distinct opcodes for sweep, vibrato, volume control, transposition, looping

**Wizards & Warriors:**
- Much simpler command set (10 handlers via dispatch at $EEEE)
- Two compact period tables (one for table-note lookup, one for direct-period)
- NSF payload maps directly to ROM PRG (unusual --- most NSFs are rearranged)
- Title screen validation: 2169/2169 frames matched on all channels (the best score in our pipeline)

**Key Rare trait:** Both Rare games use mapper 7 (AxROM) with 256KB/128KB PRG and no CHR. Sound lives in a specific PRG bank (bank 3 for Battletoads). The engines are game-specific --- unlike Konami, Rare didn't standardize a driver across titles.

### Nintendo Custom (Kid Icarus)

The most unusual engine in our collection.

**Architecture:** Deeply integrated with game state. Song init routines contain game logic (area checks, progression flags, conditional branching). Music is organized by area, not by song number. The same playback code serves different musical content depending on game state.

**Period table:** 40 entries (C#3-E6) in interleaved hi/lo format at $AB18. Neither split-table (like Konami) nor single-byte index (like Rare).

**The FDS problem:** The NSF is from the Famicom Disk System version, which has 5 channels. The NES cartridge port has 4 channels with a completely different arrangement. The NSF's period values are half the NES cart's (one octave high) due to different sound hardware clocks. This is the only game in our pipeline where the NSF and the target ROM represent fundamentally different music.

**Unique discovery:** Only 10 songs in the NES cart (vs 34 in the FDS NSF). The game uses 4 area-based music lookup tables, with channel data structures that configure which patterns play in each area.

### FCI Custom (Ultima: Quest of the Avatar)

The least-explored engine. NSF extraction works cleanly with 30 identified tracks. No ROM-level reverse engineering has been attempted. The NSF matches gameplay audio, so there's been no need to dig deeper.

## Extraction Difficulty Ranking

From easiest to hardest:

1. **Ultima** --- NSF just works. No issues found.
2. **Castlevania** --- Clean Konami driver, simple pointer table, fully validated. The template for how extraction should go.
3. **Wizards & Warriors** --- NSF maps to ROM, clean validation against trace. Best frame-match score in the pipeline (100% on 2169 frames).
4. **Contra** --- Same driver family as CV1 but 54 envelope tables and a 3-byte DX format burned multiple sessions before the differences were understood.
5. **Battletoads** --- Complex Rare engine with dual-mode duration, software volume, transposition, and ~20 commands. Parser-aligned but execution semantics validation still in progress. NSF vs trace shows bass note discrepancies.
6. **Castlevania II** --- Phrase-chaining architecture requires fundamentally different parsing approach. Period jitter creates false note boundaries. Still in investigation.
7. **Kid Icarus** --- The NSF is from a different platform. Game-integrated music engine resists standalone harness extraction. Requires building a py65 driver from the NES ROM code directly.

## Cross-Cutting Patterns

### What Every Engine Has in Common
- Period table lookup (note index to timer value)
- Per-channel state machines driven by NMI (60 Hz frame tick)
- Duration counters that decrement each tick
- Some form of volume envelope (hardware or software)

### What Differs Most
- **Envelope strategy**: parametric (CV1), lookup table (Contra), software register (Battletoads), hardware-only (W&W)
- **Data format**: flat stream (Konami), phrase library (CV2), area-indexed blocks (Kid Icarus)
- **Game integration**: none (Konami, Rare), deep (Kid Icarus)
- **Command complexity**: 5-8 opcodes (Konami), ~20 opcodes (Battletoads), 10 handlers (W&W)

### Biggest Lessons Learned

1. **Same driver family != same byte format.** CV1 and Contra are both Maezawa, but DX byte counts differ. Cost: 3+ prompts.
2. **Zero parse errors != musical correctness.** Battletoads parser v3 had zero errors with 955 notes while being 1.52x wrong on duration. Cost: 5+ prompts.
3. **NSF != ROM.** Kid Icarus proved that the NSF can represent an entirely different version of the music. The ROM code is the ultimate source of truth.
4. **Read the disassembly before guessing.** Every time we assumed an opcode's meaning instead of checking, it cost rounds. The disassembly (when available) is always faster than hypothesis-testing.
5. **Trace is ground truth.** When NSF and trace disagree, trace wins. When parser output and trace disagree, trace wins. This has been true for every game without exception.
