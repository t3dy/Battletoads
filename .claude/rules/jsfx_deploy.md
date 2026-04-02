# JSFX Deployment Rules

After ANY edit to a JSFX file, run:

```bash
python scripts/sync_jsfx.py
```

This handles: ASCII check, copy to AppData, cache bust, hash verify.

NEVER ask the user to do any of these steps.
NEVER deliver a test project without running sync_jsfx.py.

# Session Startup Rules

Before starting work on any game, run:

```bash
python scripts/session_startup_check.py <game_slug>
```

This verifies: JSFX sync, ASCII clean, DB ready, track names exist.
If it fails, fix the environment before touching extraction code.

# Pre-Delivery Rules

Before describing ANY project as "ready to test":

1. Run session_startup_check.py
2. Compare first 10 notes per channel against ground truth
3. Verify CC11 envelope matches frame data
4. Verify noise hits are present and correctly timed
5. Check WAV preview is non-silent

See docs/VALIDATION.md for the full gate protocol.
