# Validation Protocol

A build is not deliverable until it passes every gate.

## Gate A — Environment Startup

Before touching any game:

- [ ] JSFX source and REAPER-installed JSFX are identical
- [ ] JSFX has no non-ASCII bytes
- [ ] Track manifest exists for target game
- [ ] Database has game row

Hard fail: any item above. Stop and fix environment first.

## Gate B — Source Integrity

For each game:

- [ ] ROM/NSF/trace file paths recorded with hashes
- [ ] Track number-to-name mapping exists
- [ ] Capture boundaries documented or marked needs_review
- [ ] Melody signature verified (first 5 notes on melody channel)

Hard fail: unknown track identity or ambiguous song segment.

## Gate C — Ground Truth Comparison

Before trusting any extraction route:

- [ ] Dense frame states built for both NSF and trace (if available)
- [ ] Per-channel comparison: period, timing, volume, duty
- [ ] First mismatch per channel recorded (frame, parameter, values)
- [ ] Fidelity metrics computed (period_match_pct, volume_match_pct, etc.)
- [ ] Route decision made and recorded: nsf / trace / hybrid / apu2_sysex

Route rules:
- If trace exists and NSF period match < 80%, reject NSF
- If timing diverges in recognizable material, reject NSF
- Record rationale in session_decisions

## Gate D — Parameter Coverage

For the chosen route, verify each parameter:

### Pulse
- [ ] Period captured and pitch verified
- [ ] Volume captured, CC11 round-trip verified
- [ ] Duty captured (or confirmed constant)
- [ ] Sweep behavior checked
- [ ] Note boundary logic confirmed

### Triangle
- [ ] Period captured, note sequence matches ground truth
- [ ] Gating behavior (linear counter) correctly handled
- [ ] Jitter filtering documented if used

### Noise
- [ ] Volume captured
- [ ] Period index captured
- [ ] Mode bit checked
- [ ] Hit detection method recorded (vol_gate / period_change / hybrid)
- [ ] Verified: does this game use vol=0 gaps or continuous noise?

### DPCM
- [ ] Activity checked
- [ ] Inclusion/exclusion documented

## Gate E — Artifact Build

- [ ] MIDI generated via approved pipeline
- [ ] RPP generated via generate_project.py only
- [ ] WAV preview rendered
- [ ] Artifact paths recorded

## Gate F — Pre-Delivery Release Gate

ALL must pass before describing anything as "ready to test":

- [ ] F1. JSFX deployed to AppData + cache busted + ASCII clean
- [ ] F2. RPP contains expected FX chain
- [ ] F3. MIDI has note events on expected channels
- [ ] F4. WAV preview max amplitude > silence threshold
- [ ] F5. Fidelity report exists
- [ ] F6. Unresolved mismatches documented
- [ ] F7. Route decision recorded
- [ ] F8. Track identity verified
- [ ] F9. Compare first 10 notes per channel against ground truth

Hard fail: any F-check failing blocks delivery.

## Fix Order

Always: pitch -> timing -> volume -> timbre.
One hypothesis per test cycle. Change one thing, rerun comparison.

## Failure Handling

1. Record the failure
2. Stop advancing
3. Isolate first mismatch
4. Form one hypothesis
5. Change one thing
6. Rerun the relevant gate only
7. Rerun downstream gates after upstream pass

Fix the earliest broken layer first.
