# Handover: Battletoads Session 2026-04-02

Paste this into a new Claude Code window opened at C:\Dev\NSFRIPPER.

---

You are a constrained maintainer of an NES-to-MIDI-to-REAPER fidelity pipeline.

## Boot Sequence

1. Read CLAUDE.md (auto-loaded)
2. Read .claude/rules/*.md (auto-loaded)
3. Read docs/ARCHITECTURE_SPEC.md -- the full architectural directive
4. Read docs/PIPELINEOVERHAUL42.md -- pipeline redesign rationale
5. Run `python scripts/session_startup_check.py battletoads`
6. Read this handover document completely before writing any code

## What Happened This Session

### ROM Analysis (CRITICAL FINDINGS)

We found the Battletoads ROM at:
`D:\All NES Roms (GoodNES)\All NES Roms (GoodNES)\USA\Battletoads (U) [!].nes`

Key ROM facts:
- **Mapper 7 (AxROM)**: 32KB bank switching, 8 banks total (256KB PRG)
- **Sound bank**: Bank 3 (ROM offset 0x18000-0x1FFFF), matches NSF data 99.9%
- **Period table**: ROM $8E22, 60 entries (5 octaves C2-B6), standard NTSC values
- **Song table**: ROM $8B7B (indirection through $8060 -> internal ID -> $95B3/$95B4 pointers)
- **Song 3 (Level 1) internal ID**: 4 (NSF song index 2 -> internal ID 4)
- **Channel pointers for Song 3**: P1=$A15E, P2=$A2CF, Tri=$A364, Noise=$A408
- **Driver architecture**: Rare's custom engine, NOT Konami Maezawa. Uses a dispatch table at $8B7B where every data byte (0x00-0x7F) is a command index into a jump table. Bytes >= $81 are notes, $80 is rest.
- **Note encoding**: Byte $81+N maps to period_table[N]. So $81=C2, $82=C#2, ..., $BC=B6.
- **Init routine**: $8054 (TAX, LDA $8060,X to get internal ID, JMP $880E)
- **Play routine**: $8865

### The Opening Melody (GROUND TRUTH FROM ROM)

The user describes it as: **"dink dink di-dunk dink dink di-dee"**

From trace analysis mapped to ROM period table:
- **dink** = E3 (period table entry 16, period 678). Trace shows period 669 (off by 9 -- sweep).
- **dunk** = A2 (period table entry 9, period 1016). Trace shows period 1001 (off by 15 -- sweep).
- **dee** = A#4 (period table entry 34, period 239). Trace shows period 235 oscillating with 231 (sweep vibrato). **User reports this note is an octave too high in our output.**

P2 melody pattern (frames): E3, [silence], E3, A2, E3, [silence], E3, [silence], E3, A#4-vibrato, [silence], repeat.

### Critical Finding: Trace Periods vs ROM Table

**Almost NO trace period matches the ROM table exactly.** Every period is off by 1-15 units because the hardware sweep unit modifies periods after the driver writes them. The correct approach is to SNAP trace periods to the nearest ROM table entry to get the intended note, then use the CC11 volume data as the ground-truth envelope.

| Trace period | Closest table | Note | Offset |
|---|---|---|---|
| 669 | 678 | E3 | -9 |
| 1001 | 1016 | A2 | -15 |
| 235/231/239 | 239 | A#4 | -4/+8/0 |
| 677/673/681 | 678 | E3 | -1/-5/+3 |

### What We Built (v3-v6)

- **v3** (Console synth, raw period->note): "Closest yet" per user, but had trills from sweep artifacts, triangle silence, noise underreporting
- **v4**: Got worse -- over-filtered fake notes, missing real notes
- **v5** (APU2 synth, SysEx register replay): Fixed SysEx embedding and note/SysEx conflict, but SysEx replay produces hardware artifacts the NES smooths through analog output
- **v6** (Console synth, smart note detection with 3-frame stability): Eliminated 299 P2 trills, but music starts 2 beats late, 8th note still too high, phantom notes remain

### Bugs Found and Fixed This Session

1. **APU2 synth never used SysEx for sound** -- only used it for phase reset. Fixed to drive all oscillators from register state.
2. **SysEx never embedded in RPPs** -- generate_project.py silently dropped SysEx messages. Fixed.
3. **MIDI notes fought with SysEx** -- note_on events overwrote SysEx-derived frequency. Fixed with !sx[ch*8] guards.
4. **Smart note detection added** -- build_trace_midi() in trace_to_midi.py now requires 3+ frames of pitch stability before creating a note.

### Remaining Problems

1. **Music starts 2 beats late** -- missing first two notes of the opening phrase
2. **8th note (A#4 "dee") too high by ~1 octave** -- need to verify our period->MIDI conversion against the ROM table
3. **Phantom notes** -- notes appearing that aren't in the game audio
4. **No Frame IR layer** -- we're still going trace -> MIDI directly, skipping the interpretation step that made CV1/Contra work
5. **Rare driver not decoded** -- dispatch table format means we can't read the ROM music data directly yet (unlike Konami's linear command format)
6. **No kitchen_sink.py** -- the multi-route pipeline doesn't exist yet

### What the Next Session Must Do

Read docs/ARCHITECTURE_SPEC.md -- the full architectural directive for rebuilding the pipeline. Key priorities:

1. **Build kitchen_sink.py** -- orchestration kernel that generates all routes, validates, compares, blocks on failure
2. **Build Frame IR layer** -- trace -> frame_ir -> MIDI, never skip this step
3. **Implement period table snapping** -- use ROM period table to interpret trace periods into intended notes
4. **Fix the opening melody** -- match "dink dink di-dunk dink dink di-dee" note-for-note against ROM data
5. **Reverse-engineer Rare's dispatch table** -- decode what each command byte (0x00-0x7F) does to understand track structure, loop points, tempo, envelopes

### Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules with embedded architectural directive |
| `docs/ARCHITECTURE_SPEC.md` | Full pipeline rebuild specification (verbatim from user) |
| `docs/PIPELINEOVERHAUL42.md` | What we learned about the pipeline this session |
| `docs/KITCHENSINKAUDIT.md` | Original gap analysis |
| `.claude/rules/architecture.md` | Structural rules |
| `.claude/rules/session_protocol.md` | Working order |
| `studio/jsfx/ReapNES_APU2.jsfx` | Updated synth with SysEx register replay |
| `scripts/trace_to_midi.py` | Has build_trace_midi() with smart note detection |
| `scripts/generate_project.py` | Updated with SysEx embedding |
| `output/Battletoads_trace_v6/` | Latest output (Console + APU2 RPPs) |

### ROM Reference Data

Period table (ROM $8E22, 60 entries):
```
C2=1710 C#2=1613 D2=1524 D#2=1438 E2=1358 F2=1281
F#2=1208 G2=1141 G#2=1077 A2=1016 A#2=959 B2=905
C3=854 C#3=806 D3=761 D#3=718 E3=678 F3=640
F#3=604 G3=570 G#3=538 A3=508 A#3=479 B3=452
C4=427 C#4=403 D4=380 D#4=359 E4=338 F4=319
F#4=301 G4=284 G#4=268 A4=253 A#4=239 B4=226
C5=213 C#5=201 D5=189 D#5=179 E5=169 F5=159
F#5=150 G5=142 G#5=134 A5=126 A#5=119 B5=112
C6=106 C#6=100 D6=94 D#6=89 E6=84 F6=79
F#6=75 G6=70 G#6=66 A6=63 A#6=59 B6=56
```

Song 3 channel data pointers: P1=$A15E, P2=$A2CF, Tri=$A364, Noise=$A408

Mesen capture: `C:\Users\PC\Documents\Mesen2\capture.csv` (9,495 frames, 158.2s, 2+ loops of Level 1)

---
