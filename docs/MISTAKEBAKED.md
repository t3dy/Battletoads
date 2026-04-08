# Mistakes Baked Into System Files

Every mistake that burned 2+ prompts during the CV1, Contra, Battletoads,
and Wizards & Warriors sessions has been written as a warning into the
project's operating files. These are the files Claude reads at the start
of every session — the warnings are positioned to intercept the mistake
BEFORE it happens.

**Validation gates:** `.claude/rules/session_protocol.md` (Gates 1-3, Validation Ladder)
**Architecture rules:** `.claude/rules/architecture.md` (Rules 13-17)

## Where the Warnings Live

### CLAUDE.md — "Reverse Engineering Blunders (NEVER REPEAT)"

8 rules, each derived from a specific incident:

| Rule | Mistake It Prevents | Prompts It Cost |
|------|---------------------|-----------------|
| Dump trace data before modeling | We guessed 3 envelope hypotheses before looking at actual frame data | 5 |
| Same driver ≠ same ROM layout | Ran CV1 parser on 4 other ROMs expecting it to work | 3 |
| Same period table ≠ same driver | Spent rounds scanning CV2 for Maezawa pointer table that doesn't exist | 4 |
| Read the disassembly before guessing | Assumed Contra DX reads 2 bytes (CV1 format) instead of 3 | 3 |
| Check all channels not just one | E8 envelope gate looked correct on Sq1, was wrong for Sq2 | 2 |
| Automated tests can't catch systematic errors | Octave was wrong by exactly 12 semitones but trace comparison showed zero mismatches | 3 |
| Always version output files | Overwrote Contra MIDI/RPP files, user couldn't compare versions | 2 |
| Triangle is one octave lower | Changed BASE_MIDI_OCTAVE4 and broke triangle pitch | 2 |

### extraction/CLAUDE_EXTRACTION.md — Two New Sections

**"Per-Game Parser Checklist"** — 8-step mandatory checklist before
writing ANY code for a new game:
1. Check mapper type
2. Search for existing disassembly
3. Identify the driver (scan for DX/FE/FD patterns)
4. Find pointer table from disassembly (not scanning)
5. Check DX byte count (how many bytes after DX?)
6. Check $C0-$CF semantics (rest vs mute)
7. Check percussion format (inline vs separate channel)
8. Parse ONE track and listen before batch-extracting

**"Debugging Protocol"** — 5-step order of operations when output
doesn't match the game:
1. Identify the symptom precisely (which channel, which aspect)
2. Extract trace data for the exact frames (don't reason abstractly)
3. Compare at frame level (look at FIRST mismatch)
4. Form ONE hypothesis and test it (don't try 3 at once)
5. If trace shows zero mismatches but sounds wrong → octave mapping
   error, user must compare to game

### extraction/drivers/konami/spec.md — Per-Game Differences Table

Added a comparison table showing exactly what differs between CV1
and Contra: mapper, pointer table format, DX byte count, percussion
system, envelope model. Future games should be added to this table
BEFORE writing their parser.

Includes a warning: "Same period table does NOT prove same driver."

### CLAUDE.md + architecture.md + session_protocol.md — "Execution Semantics Validation"

New rule derived from Battletoads parser sessions:

| Rule | Mistake It Prevents | Prompts It Cost |
|------|---------------------|-----------------|
| Zero parse errors ≠ musical correctness | Parser v3 had zero errors but duration was 1.52x wrong and arpeggio was unmodeled | 5+ |
| Execution semantics validation is mandatory | Skipped driver simulation, promoted parser output to MIDI without verifying frame behavior | 3+ |
| Parser output is a hypothesis | Treated "955 notes, 0 errors" as proof of correctness when base notes never actually sounded as parsed | 4+ |

The execution semantics validation phase was added to:
- CLAUDE.md NON-NEGOTIABLE RULES section
- .claude/rules/architecture.md (rules 13-15)
- .claude/rules/session_protocol.md (Gates 1-3 + checklist)
- docs/ARCHITECTURE_SPEC.md (Phase 4B)
- .claude/skills/ROMPARSER.md (Phase 4 rewrite)
- .claude/skills/SKELETONKEY.md (validation protocol)
- SKILLSMANUAL.md (orchestrator pipeline)

## How This Prevents Future Waste

The warnings are positioned at decision points:

- **Starting a new game?** → CLAUDE.md rules 2-3 fire ("check driver
  identity, don't assume same layout")
- **Writing a parser?** → CLAUDE_EXTRACTION.md checklist fires ("read
  disassembly, check DX byte count")
- **Parser reports zero errors?** → architecture.md rule 13 fires
  ("zero parse errors is structural, not semantic — run execution
  semantics validation before claiming musical correctness")
- **Generating MIDI from parsed notes?** → architecture.md rule 14
  fires ("simulate driver frame-by-frame, compare against trace first")
- **Debugging wrong notes?** → CLAUDE_EXTRACTION.md protocol fires
  ("dump trace first, one hypothesis at a time")
- **Changing pitch/octave mapping?** → CLAUDE.md rules 6 and 8 fire
  ("listen to game, account for triangle offset")
- **Generating output?** → CLAUDE.md rule 7 fires ("version the files")
- **Labeling output as "ready"?** → session_protocol.md Gate 2 fires
  ("execution semantics validation must pass before delivery")

Each warning includes the specific incident that caused it, so a
future session can understand WHY the rule exists, not just what it says.
