# Konami Sound Driver — Research Notes

## Status: Not Started

## Overview

Konami used a series of related sound drivers across their NES library. The base driver (pre-VRC) appears in titles from ~1986–1990 and shares structural similarities across games.

## Known Characteristics (from community research)

- Frame-based engine: music updates once per NMI (60Hz NTSC).
- Speed/tempo controlled by a tick counter that divides the frame rate.
- Per-channel data streams with inline commands.
- Volume envelopes: short sequences (4–8 entries) applied per-note.
- Duty cycling: some titles alternate duty per-frame for timbral effect.
- Loop support: songs typically loop after a fixed number of rows.

## Data Format Hypotheses

- **Provisional:** Command byte format appears to use high nibble for command type, low nibble for parameter.
- **Provisional:** Note values likely use a lookup table for APU period values.
- **Unverified:** Song header may contain per-channel pointers and a speed byte.

## Target Games for Investigation

1. Castlevania (1986) — simple, well-studied
2. Contra (1988) — builds on the same engine
3. Life Force / Salamander (1988)

## Sources

- (To be added as research proceeds)

## Confidence

All claims in this file are **provisional** (confidence = 0.0) unless marked otherwise.
