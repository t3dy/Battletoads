---
paths:
  - "extraction/**"
  - "scripts/trace_compare.py"
---

# Debugging Protocol

When parser output doesn't match the game, follow this order:

1. **Symptom** — pitch? duration? volume? articulation? Which channel? Which frame range?
2. **Dump trace** — extract actual APU register values for the specific frames. Don't reason abstractly.
3. **First mismatch** — run trace_compare.py, look at the FIRST mismatch frame, not aggregates.
4. **One hypothesis** — change ONE thing, rerun, check if first mismatch moved. No multi-hypothesis batches.
5. **Zero mismatches but sounds wrong** — systematic octave/pitch error. User MUST compare to game.

To dump trace frames:
```python
# Show frames N-M for a specific channel
for f in range(N, M):
    print(f'{f}: vol={p1_vol} period={p1_period}')
```
