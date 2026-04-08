---
paths:
  - "extraction/drivers/**"
---

# New Game Parser Checklist

Before writing ANY code for a new game, complete these steps IN ORDER:

1. **Mapper** — read rom[6-7] for mapper type. 0=linear, 1/2/4=bank-switched.
2. **Disassembly** — check references/ for annotated disassembly. If exists, READ IT.
3. **Driver ID** — scan for E8+DX and FE+count+addr patterns. No hits = not Maezawa. STOP.
4. **Pointer table** — find from disassembly, NOT by scanning. No disassembly = Mesen debugger.
5. **DX byte count** — how many bytes after DX? CV1=2, Contra=3/1. Read the disassembly.
6. **$C0-$CF** — rest with duration or instantaneous mute? Read sound_cmd_routine_00.
7. **Percussion** — inline E9/EA (CV1) or separate channel with DMC (Contra)?
8. **Parse ONE track, listen** — compare to game before batch-extracting.

See extraction/drivers/konami/spec.md for the per-game differences table.

## After Structural Parsing: Mandatory Next Steps

Completing steps 1-8 gives you **Rung 1 (parser-aligned)** — structural
byte-stream alignment. This is NOT musical correctness.

9. **Build simulator** — frame-level execution model from parsed events.
   Use SIMULATORBUILDER skill.
10. **Compare vs ground truth** — sim output vs NSF emulation (Rung 2)
    then vs Mesen trace (Rung 3).
11. **Document per-channel** — create validation record using
    `templates/reports/GAME_VALIDATION_TEMPLATE.md`.
12. **Noise separately** — noise channel is a separate semantic domain.
    Do not force through melodic pipeline.
13. **Label all output** — hypothesis output until Rung 3+ passes.

See `session_protocol.md` for the Validation Ladder and gate criteria.
