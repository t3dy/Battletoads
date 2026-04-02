# Tips for Working with Ted

Notes for Claude Code agents on communication patterns, vocabulary
bridging, and how to get the most productive collaboration.

## Vocabulary Bridging

Ted is a musician and builder with deep domain intuition but not
always the technical audio/synthesis terminology. When he describes
something in everyday language, map it to the technical term AND
teach the term back:

| Ted Says | Technical Term | Explain As |
|----------|---------------|------------|
| "sliding up the neck" | Pitch bend / portamento / glissando | The NES sweep unit bends the pitch smoothly by modifying the period register every frame |
| "fretless bass slide" | Portamento or pitch sweep | A continuous pitch change rather than discrete note steps |
| "groovy" / "groove is missing" | Rhythmic feel / timing pocket | Notes land at specific micro-timings that create a physical feel — quantized MIDI loses this |
| "richness of tones" | Timbre / harmonic content | Determined by duty cycle (waveform shape) and vibrato (pitch modulation) |
| "noisier than it should" | Wrong duty cycle / harmonic distortion | 75% duty has more harmonics than 25% — sounds buzzier/harsher |
| "tones and timbres are off" | Waveform parameters wrong | Duty cycle, volume envelope shape, or vibrato not matching original |
| "durations need work" | Note articulation / envelope decay | How long notes sustain vs when they cut off |
| "doesn't sound like the game" | Fidelity gap | Measurable difference between our output and ground truth |
| "the rhythm" | Tempo + groove + articulation | The combined effect of note timing, duration, and volume envelope |
| "run of notes" | Arpeggio or scalar run | Rapid sequence of ascending/descending pitches |

**Rule: Always feed back the technical term when Ted uses a colloquial
description.** Don't just understand him — teach the vocabulary so
future conversations become more precise.

## Communication Patterns

### Ted Gives Impressionistic Feedback

When Ted says "it sounds somewhat like Battletoads but not right,"
don't wait for a specific diagnosis. Instead, systematically check
every parameter (the LEAVENOTURNUNSTONED checklist) and present
findings ranked by impact.

### Ted Prefers Outputs Over Explanations

Ted often asks for `.md` output files rather than inline explanations.
This is deliberate — he's building a knowledge base that persists
across sessions. Always write the doc as requested rather than
summarizing in chat.

### Ted Tests By Ear First, Then Asks For Data

The workflow is: Ted listens → reports impression → asks Claude to
investigate. Don't skip the investigation step and just guess. Run
the actual comparisons, dump the actual frame data, find the actual
mismatch.

### Ted Asks Questions He Already Partly Knows The Answer To

When Ted says "I wonder if you're missing some filters or tables,"
he's giving you a hint. He suspects something specific. Don't dismiss
the hint — investigate exactly what he's pointing at.

### Ted Values Exhaustiveness

The `/plan-joe-chip-scope` and "leave no turn unstoned" mindset:
Ted would rather you try 10 things and report all findings than
try 2 things and declare victory. When he says "check every music
parameter you can think of," he means ALL of them.

### Ted Tracks Mistakes And Builds Systems

He asks for `.md` docs about failures (WHYSUCHABADSTART, MISTAKEBAKED)
because he wants to prevent future sessions from making the same
mistakes. Write these docs honestly — include what went wrong, why,
and how to prevent it. Don't minimize.

## Prompt Engineering Tendencies

### Ted Describes Goals, Not Steps

"Get us as close as possible to accurate translation of the game ROM
data into a reaper project" — this is an outcome, not a procedure.
Claude should decompose this into concrete steps and checkpoints.

### Ted Uses Metaphors From Music

"the groove of the rhythm" = timing/feel. "richness" = harmonic
content. "like a bass player sliding" = portamento/pitch bend.
When you hear a music metaphor, map it to the specific NES APU
parameter that controls that quality.

### Ted Escalates Progressively

First report: "somewhat like Battletoads"
Second report: "tones and timbres are off"
Third report: "something is radically missing"

Each report is more specific. Pay attention to the escalation —
the third report means the earlier fixes didn't address the core
issue. Don't keep tweaking the same parameters.

### Ted Expects You To Know When You Don't Know

If you're not sure which NSF song corresponds to which level, say
so and propose a way to find out (web search, pattern matching,
listening). Don't guess and deliver wrong output.

## Technical Level

Ted is a polymath builder — comfortable with:
- Python scripts and CLI tools
- REAPER projects and MIDI editing
- Git workflows and file management
- ROM hacking concepts (registers, memory maps)
- High-level music theory (notes, chords, scales, rhythm)

Less comfortable with:
- NES APU register bit layouts (explain the hex)
- Synthesis terminology (duty cycle, oscillator, envelope)
- DSP concepts (sampling rate, quantization, aliasing)
- MIDI protocol details (status bytes, running status)

## Key Behaviors

1. **Always produce the requested output file** — if Ted asks for
   SOMETHING.md, write it. Don't just discuss it in chat.

2. **Feed back technical terms** — when Ted describes something
   colloquially, use and define the proper term.

3. **Don't deliver until confident** — Ted told us "wait to give me
   something to test until you are confident." Respect this.

4. **Check the synth FX window** — the JSFX syntax error was visible
   the entire time. Always verify the tool works before debugging
   the data.

5. **Verify track mappings** — Song 2 ≠ Level 1. Always confirm which
   NSF song corresponds to which game section before extracting.

6. **Run comparisons, don't theorize** — dump trace frames, count
   mismatches, measure divergence. Data beats speculation.

7. **Write mistake docs honestly** — Ted uses these to build systems
   that prevent future failures. Honesty is more valuable than
   face-saving.
