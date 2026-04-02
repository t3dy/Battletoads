# Ted's Prompt Style: Strengths and Foibles

An honest analysis of recurring patterns in how Ted prompts Claude Code,
what works well, and where the collaboration breaks down.

## Strengths

### 1. Outcome-Oriented Framing

Ted describes what he wants to HEAR, not what code to write:
> "the groove of the rhythm is totally missing"
> "richness of the tones is missing"
> "it sounds noisier than it should"

This is excellent because it keeps Claude focused on the actual goal
(faithful audio reproduction) rather than getting lost in implementation
details. The risk is that Claude may interpret the feedback too narrowly
and tweak one parameter when the real problem is architectural.

### 2. Demanding Exhaustiveness

> "check every music parameter you can think of"
> "leave no turn unstoned"
> "try every approach that might help"

Ted pushes Claude past its tendency to declare victory after one fix.
This is valuable because NES audio has ~25 interacting parameters and
bugs often stack (the Battletoads session had 3 synth bugs + wrong song
+ wrong pipeline source simultaneously).

### 3. Building Institutional Memory

Ted consistently asks for .md output files documenting failures,
methods, and discoveries. This creates a knowledge base that persists
across sessions. The MISTAKEBAKED.md pattern — encoding every blunder
as a rule with its cost — is genuinely excellent prompt engineering.

### 4. Progressive Context Revelation

Ted doesn't dump everything at once. He gives an initial task, tests
the result, reports what's wrong, then adds context:
> First: "work on battletoads"
> Then: "I did a mesen capture" (new data source)
> Then: "the synth is noisier than it should" (perceptual feedback)
> Then: "there are really interesting runs midway through" (specific musical feature)

This iterative refinement is natural and productive — each round gives
Claude a tighter signal to work with.

## Foibles

### 1. Assumes Claude Has Context It Doesn't

Ted references "our initial success" with Castlevania and Contra as
if Claude remembers the specific sessions. Each new Claude session
starts fresh. The CLAUDE.md and rules/ files carry forward RULES but
not the specific debugging narrative.

**Impact**: Claude makes the same mistakes that were already solved
because it doesn't know WHICH rules are critical until it violates them.

**Fix**: The session startup protocol should include "read MISTAKEBAKED.md"
as step 1, not just CLAUDE.md.

### 2. Late Delivery of Critical Information

The Mesen trace existed from the start of the session but wasn't
offered until after the NSF pipeline was already running. The MP3
collection existed but wasn't mentioned until hours in. Track names
were available via web search but nobody searched.

**Impact**: Work proceeds on incomplete information. The wrong song
gets extracted, the wrong pipeline gets used, and debugging focuses
on the wrong layer.

**Fix**: Ted should front-load ALL available data sources at session
start. A simple "here's what I have" inventory:
- NSF file: yes/no
- Mesen trace: yes/no (which sections?)
- MP3 references: yes/no
- Disassembly: yes/no
- Previous working projects: yes/no

### 3. Testing Happens After Delivery, Not During

Ted's workflow is: give task → wait for delivery → test → report
failure. This creates long feedback loops where Claude builds an
entire pipeline before discovering the foundation is broken.

**Impact**: The JSFX syntax error, the wrong song mapping, and the
FILE-vs-HASDATA issue all could have been caught with a 30-second
mid-build smoke test.

**Fix**: Insert smoke tests into the build process. After the FIRST
RPP is generated, Ted opens it and reports whether it plays. Don't
batch-generate 21 files before testing one.

### 4. Colloquial Descriptions Without Technical Anchoring

> "there are some really interesting runs midway through the song
> where it's as if a bass player is sliding his finger up the neck"

This is vivid and useful for conveying the FEEL, but Claude needs to
map it to specific APU parameters. The mapping isn't always obvious:
- "sliding" = pitch bend (sweep unit) OR portamento OR glissando?
- "runs" = arpeggio OR scalar passage OR rapid note sequence?
- "midway through" = which frame range?

**Impact**: Claude may investigate the wrong parameter or the wrong
section of the song.

**Fix**: When Ted describes something in musical metaphor, Claude
should immediately ask: "Which channel? Which time range? Does it
go up or down?" And feed back the technical term: "That sounds like
the NES sweep unit — hardware pitch bend."

### 5. Scope Expansion Via Document Requests

Ted often asks for documentation outputs mid-task:
> "give me FRAMEBYFRAME.md"
> "give me TIPSFORWORKINGWITHTED.md"
> "give me a critique... with two suitably named outputs"

These are valuable long-term artifacts but they interrupt the
immediate task (getting Battletoads to sound right). Claude context
fills with doc-writing instead of debugging.

**Impact**: The actual fidelity work stalls while docs are written.
The session runs long and important fixes (like the correct Song 3
extraction) happen late.

**Fix**: Queue doc requests for after the primary task is working.
Or explicitly say "write this doc AFTER the audio is right." Ted
is aware of this pattern (the /plan-abendsen-parking skill exists
for exactly this purpose) but doesn't always invoke it.

## The Meta-Pattern

Ted's prompt engineering is strongest when he's BUILDING SYSTEMS
(rules, checklists, ontologies, skill definitions) and weakest when
he's DEBUGGING IN REAL TIME (testing, iterating, diagnosing). The
system-building creates excellent institutional memory. The real-time
debugging suffers from late context, long feedback loops, and
vocabulary gaps.

The ideal session structure for Ted:

```
1. Inventory (2 min): What data do we have? What's the target?
2. Smoke test (2 min): Does the synth work? Does a test RPP play?
3. Web search (2 min): What are the track names? What's known?
4. Extract one song (5 min): The most recognizable track.
5. Ted listens (2 min): Does it sound right?
6. Fix cycle (iterate): One fix, one test, one report.
7. Batch (10 min): Apply to all tracks.
8. Docs (10 min): Write the session artifacts.
```

Currently the session looks more like:

```
1. "Work on battletoads" (no inventory)
2. Extract all 21 songs (no smoke test)
3. Deliver (no validation)
4. "No sound" (discover foundation is broken)
5. Debug RPP format (wrong layer)
6. Debug synth (right layer, found after hours)
7. "Still sounds wrong" (wrong song was extracted)
8. Write 6 docs (context fills, fixes delayed)
9. Discover correct song mapping (late)
```

The system-building work (CLAUDE.md, skills, rules, ontologies) is
slowly closing the gap between these two patterns. Each session's
docs make the next session's debugging faster.
