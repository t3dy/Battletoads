# Environment Fixes: Working Around the Foibles

Concrete changes to the repo, CLAUDE.md, hooks, and session protocol
that compensate for the recurring failure patterns.

## Fix 1: Session Startup Gate

### Problem
Sessions start with "work on [game]" and immediately begin extraction
without verifying the environment works or gathering context.

### Solution
Add to CLAUDE.md as a mandatory first section:

```markdown
## Session Startup (MANDATORY — do this before ANY game work)

1. SYNTH CHECK: Open and read the installed JSFX at
   C:/Users/PC/AppData/Roaming/REAPER/Effects/ReapNES Studio/ReapNES_Console.jsfx
   Grep for empty else branches: ") : (\n" followed by only comments.
   If found, add "0;" to the empty branch.

2. DATA INVENTORY: Ask the user:
   "What do we have for [game]?"
   - NSF file?
   - Mesen trace capture? (which sections?)
   - MP3 references?
   - ROM file?
   - Disassembly?

3. TRACK NAMES: Web search for "[game] NES soundtrack track listing"
   on KHInsider, VGMRips, or Zophar. Create track_names.json BEFORE
   extracting anything.

4. SMOKE TEST: Verify output/test_inline_midi.rpp exists. If not,
   generate it. Tell user to open it in REAPER and confirm sound.
```

### Implementation
Edit CLAUDE.md to add this section. Zero code required.

## Fix 2: Track Name Manifest

### Problem
NSF songs have generic names ("Song 1", "Song 2"). Without a track
listing, the wrong song gets extracted and tested.

### Solution
Create `scripts/fetch_track_names.py`:

```python
"""Fetch track names from community sources and create track_names.json."""
# 1. Web search for game + "NES soundtrack"
# 2. Parse KHInsider or VGMRips track listing
# 3. Write output/{game}/track_names.json
# 4. Rename output files to use track names
```

Also add to CLAUDE.md:
```markdown
## Track Names (MANDATORY before extraction)
Run: python scripts/fetch_track_names.py --game "Game Name"
Or manually create output/{game}/track_names.json from web search.
NEVER use generic "Song N" names in delivered output.
```

## Fix 3: JSFX Validation Hook

### Problem
JSFX syntax errors cause silent failure. The synth receives MIDI
(yellow indicators) but produces no audio. Not caught until the user
opens the FX window.

### Solution
Create `scripts/validate_synth.py`:

```python
"""Validate JSFX files for known error patterns."""
import re, sys

JSFX_PATH = "C:/Users/PC/AppData/Roaming/REAPER/Effects/ReapNES Studio"
CHECKS = [
    # Empty else branches cause @sample compilation failure
    (r'\) : \(\s*\n\s*//[^\n]*\n\s*\);', 'Empty else branch (add "0;")'),
    # CC11 decode should use /8 not /127*15
    (r'msg3 / 127 \* 15', 'CC11 decode uses /127*15 (should be /8)'),
    # CC12 decode should use floor(x/32) not min(3,x)
    (r'min\(3, msg3\)', 'CC12 decode uses min(3,x) (should be floor(x/32))'),
    # @sample must exist
    (None, '@sample section missing'),  # special check
]

def validate(path):
    with open(path) as f:
        content = f.read()
    errors = []
    for pattern, msg in CHECKS:
        if pattern and re.search(pattern, content):
            errors.append(msg)
    if '@sample' not in content:
        errors.append('@sample section missing')
    return errors
```

Add as Claude Code hook:
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "generate_project",
      "command": "python scripts/validate_synth.py"
    }]
  }
}
```

## Fix 4: One-Song-First Protocol

### Problem
21 songs get extracted and delivered before ANY are tested. When the
first one fails, all 21 are wrong.

### Solution
Add to CLAUDE.md:

```markdown
## Extraction Protocol
1. Extract ONE song first — the most recognizable track.
2. Build its RPP. Tell the user to test it.
3. WAIT for user feedback before batch-extracting.
4. If user reports issues, debug on the single song.
5. Only batch-extract after the single song sounds right.
```

This is the "parse ONE track and listen before batch-extracting" rule
from the new-game-parser checklist, applied to the NSF pipeline.

## Fix 5: NSF vs Trace Auto-Compare

### Problem
The NSF extraction for Battletoads produces fundamentally different
data than the Mesen trace (different timing, missing channels, no
sweep vibrato). Nobody compared them until the user said "something
is radically missing."

### Solution
Create `scripts/compare_nsf_trace.py`:

```python
"""Compare NSF extraction against Mesen trace frame-by-frame."""
# For each channel, for each frame:
#   Compare period, volume, duty
#   Report: match %, first mismatch frame, divergence score
# If match < 80%: print "WARNING: Use trace pipeline for this game"
```

Add to the extraction pipeline:
```python
# In nsf_to_reaper.py, after extraction:
if trace_exists(game):
    score = compare_nsf_trace(nsf_frames, trace_path, trace_start)
    if score < 80:
        print(f"*** NSF fidelity {score}% — RECOMMEND trace pipeline ***")
```

## Fix 6: Vocabulary Bridge in CLAUDE.md

### Problem
Ted describes audio in musical metaphor. Claude maps it to the wrong
parameter or doesn't map it at all.

### Solution
Add a vocabulary section to CLAUDE.md:

```markdown
## Audio Vocabulary Bridge
When the user describes something colloquially, map to NES terms:
- "slide" / "sliding" → pitch bend (NES sweep unit, $4001)
- "run" / "runs" → rapid pitch sequence (arpeggio or scalar)
- "groove" / "feel" → timing + articulation (note duration + volume envelope)
- "rich" / "richness" → timbre (duty cycle + vibrato + harmonics)
- "noisy" / "buzzy" → wrong duty cycle (75% is noisiest) or noise bleed
- "thin" / "flat" → missing volume envelope or wrong duty cycle
- "muddy" → overlapping notes or too-long decay
- "punchy" → short attack + fast decay + low sustain

Always feed back the technical term when the user uses a colloquial one.
```

## Fix 7: Pre-Delivery Validation Script

### Problem
RPPs delivered as "ready to test" that produce no sound.

### Solution
Create `scripts/validate_delivery.py`:

```python
"""Validate an RPP before delivering to user."""
import sys

def validate_rpp(path):
    with open(path) as f:
        content = f.read()
    errors = []
    if 'HASDATA' not in content:
        errors.append('No HASDATA — MIDI not embedded inline')
    if 'ReapNES' not in content:
        errors.append('No ReapNES synth in FXCHAIN')
    e_count = content.count('\n        E ')
    if e_count < 10:
        errors.append(f'Only {e_count} MIDI events — likely empty')
    if '        X ' in content:
        errors.append('Contains X meta events — may cause empty items')
    return errors
```

Run automatically after every RPP generation. Block delivery if errors.

## Fix 8: Document Queue (Not Inline)

### Problem
Doc requests during debugging steal context and delay fixes.

### Solution
Add to CLAUDE.md:

```markdown
## Document Requests
When the user asks for .md output during active debugging:
1. Acknowledge the request
2. Add it to the todo list as "pending"
3. Continue the primary task (getting audio right)
4. Write all requested docs AFTER the primary task passes
Exception: If the doc IS the primary task, write it immediately.
```

This is the /plan-abendsen-parking principle applied to docs.

## Fix 9: Sync Repo JSFX to REAPER

### Problem
The JSFX lives in two places (repo and REAPER Effects folder). They
drift apart. Bugs fixed in one aren't fixed in the other.

### Solution
Add a sync script and hook:

```python
# scripts/sync_jsfx.py
"""Sync JSFX files between repo and REAPER Effects folder."""
import shutil, filecmp
REPO = "studio/jsfx/"
REAPER = "C:/Users/PC/AppData/Roaming/REAPER/Effects/ReapNES Studio/"

for name in ["ReapNES_Console.jsfx", "ReapNES_APU2.jsfx"]:
    repo_path = REPO + name
    reaper_path = REAPER + name
    if not filecmp.cmp(repo_path, reaper_path, shallow=False):
        # Copy repo → REAPER (repo is source of truth)
        shutil.copy2(repo_path, reaper_path)
        print(f"Synced {name} to REAPER")
```

Run at session startup.

## Implementation Priority

| Fix | Effort | Impact | Do When |
|-----|--------|--------|---------|
| 1. Startup gate | 5 min (edit CLAUDE.md) | Prevents 80% of issues | NOW |
| 2. Track names | 10 min per game | Prevents wrong-song extraction | Per game |
| 3. JSFX validation | 30 min (script) | Catches synth bugs before user | This week |
| 4. One-song-first | 2 min (edit CLAUDE.md) | Prevents batch-failure | NOW |
| 5. NSF vs trace compare | 2 hours (script) | Auto-routes to correct pipeline | This week |
| 6. Vocabulary bridge | 5 min (edit CLAUDE.md) | Faster debugging | NOW |
| 7. Pre-delivery validation | 30 min (script) | No more silent RPPs | This week |
| 8. Document queue | 2 min (edit CLAUDE.md) | Keeps focus on primary task | NOW |
| 9. JSFX sync | 15 min (script) | Prevents repo/REAPER drift | This week |

Fixes 1, 4, 6, and 8 are CLAUDE.md edits — zero code, immediate effect.
Fixes 3, 5, 7, and 9 are short Python scripts — one afternoon of work.
Fix 2 is per-game web research — 10 minutes at the start of each game.

Total: ~4 hours of setup to prevent ~4 hours of debugging per game.
