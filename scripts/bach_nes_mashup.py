#!/usr/bin/env python3
"""Generate Bach × NES mashup REAPER projects and render WAV files.

Takes Bach MIDI files and pairs them with NES synth instrument presets
from various Castlevania 1 and Contra stages. Each stage has a distinct
timbral palette defined by pulse duty cycles.

Usage:
    python scripts/bach_nes_mashup.py --generate-all     # All projects
    python scripts/bach_nes_mashup.py --render-best       # Render top picks
    python scripts/bach_nes_mashup.py --list              # Show all combos
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import wave
import uuid
from pathlib import Path

import numpy as np

try:
    import mido
except ImportError:
    print("pip install mido", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PROJECTS_DIR = REPO_ROOT / "studio" / "reaper_projects" / "bach_mashups"
WAV_DIR = REPO_ROOT / "output" / "bach_mashups"
MIDI_DIR = Path.home() / "Downloads"
MIDI_DIRS = [
    Path.home() / "Downloads",
    REPO_ROOT / "studio" / "midi" / "classical" / "bach_collection",
    REPO_ROOT / "studio" / "midi" / "classical" / "bach",
    REPO_ROOT / "studio" / "midi" / "classical" / "mozart",
    REPO_ROOT / "studio" / "midi" / "classical" / "beethoven",
]
MIDI_DIR_ALT = REPO_ROOT / "studio" / "midi" / "classical" / "bach_collection"

def find_midi(filename: str) -> Path | None:
    """Search all MIDI directories for a file."""
    for d in MIDI_DIRS:
        p = d / filename
        if p.exists():
            return p
    return None


SAMPLE_RATE = 44100
FRAMES_PER_SEC = 60
SAMPLES_PER_FRAME = SAMPLE_RATE // FRAMES_PER_SEC  # 735
CPU_CLK = 1789773.0  # NTSC NES CPU clock

# ──────────────────────────────────────────────────────────────────────
#  Stage presets: each stage has distinct pulse duty cycles
# ──────────────────────────────────────────────────────────────────────

STAGE_PRESETS = [
    # Castlevania 1 stages
    {
        "game": "Castlevania",
        "stage": "VampireKiller",
        "label": "CV1 Vampire Killer",
        "p1_duty": 2,   # 50% square - classic warm lead
        "p2_duty": 1,   # 25% - bright countermelody
        "mood": "heroic",
        "description": "Classic balanced NES sound, warm lead with bright harmony",
    },
    {
        "game": "Castlevania",
        "stage": "Stalker",
        "label": "CV1 Stalker",
        "p1_duty": 2,   # 50% square pad
        "p2_duty": 2,   # 50% square swell
        "mood": "atmospheric",
        "description": "Full square waves on both pulses, atmospheric and dense",
    },
    {
        "game": "Castlevania",
        "stage": "WickedChild",
        "label": "CV1 Wicked Child",
        "p1_duty": 1,   # 25% swell lead
        "p2_duty": 2,   # 50% square pad harmony
        "mood": "bright",
        "description": "Bright punchy lead with warm square harmony",
    },
    {
        "game": "Castlevania",
        "stage": "HeartOfFire",
        "label": "CV1 Heart of Fire",
        "p1_duty": 1,   # 25% square swell
        "p2_duty": 1,   # 25% square pad
        "mood": "intense",
        "description": "Both pulses at 25% duty - bright, intense, cutting",
    },
    {
        "game": "Castlevania",
        "stage": "NothingToLose",
        "label": "CV1 Nothing to Lose",
        "p1_duty": 2,   # 50% square swell
        "p2_duty": 0,   # 12.5% thin pad
        "mood": "dark",
        "description": "Warm square lead against thin buzzy pad - tension",
    },
    # Contra stages
    {
        "game": "Contra",
        "stage": "Jungle",
        "label": "Contra Jungle",
        "p1_duty": 3,   # 75% wide swell (staccato)
        "p2_duty": 1,   # 25% wide swell
        "mood": "aggressive",
        "description": "Wide asymmetric pulses - punchy, military feel",
    },
    {
        "game": "Contra",
        "stage": "Waterfall",
        "label": "Contra Waterfall",
        "p1_duty": 0,   # 12.5% thin swell
        "p2_duty": 0,   # 12.5% thin swell
        "mood": "eerie",
        "description": "Both pulses at 12.5% - thin, metallic, haunting",
    },
    {
        "game": "Contra",
        "stage": "Flame",
        "label": "Contra Flame Fortress",
        "p1_duty": 0,   # 12.5% thin pad
        "p2_duty": 0,   # 12.5% thin pad
        "mood": "tense",
        "description": "Both thin pulses for claustrophobic tension",
    },
    {
        "game": "Contra",
        "stage": "Maze",
        "label": "Contra Maze Fortress",
        "p1_duty": 3,   # 75% wide pad (staccato)
        "p2_duty": 0,   # 12.5% thin swell (attack)
        "mood": "ominous",
        "description": "Wide pad lead vs thin staccato - menacing contrast",
    },
    # Journey to Silius stages (Sunsoft, 1990) - famous for aggressive NES sound
    {
        "game": "JourneyToSilius",
        "stage": "Stage1",
        "label": "JtS Stage 1 & 5",
        "p1_duty": 1,   # 25% bright attack
        "p2_duty": 1,   # 25% bright attack
        "mood": "heroic",
        "description": "Dual bright 25% pulses - classic Sunsoft energy",
    },
    {
        "game": "JourneyToSilius",
        "stage": "Stage2",
        "label": "JtS Stage 2",
        "p1_duty": 0,   # 12.5% thin metallic
        "p2_duty": 0,   # 12.5% thin metallic
        "mood": "eerie",
        "description": "Both pulses at 12.5% - thin, metallic, haunting Sunsoft",
    },
    {
        "game": "JourneyToSilius",
        "stage": "Stage3",
        "label": "JtS Stage 3",
        "p1_duty": 1,   # 25% bright lead
        "p2_duty": 2,   # 50% warm harmony
        "mood": "intense",
        "description": "Bright lead against warm square harmony - driving action",
    },
    {
        "game": "JourneyToSilius",
        "stage": "Stage4",
        "label": "JtS Stage 4",
        "p1_duty": 1,   # 25% bright lead
        "p2_duty": 2,   # 50% warm pad
        "mood": "dark",
        "description": "Bright lead over warm pad - brooding tension",
    },
    {
        "game": "JourneyToSilius",
        "stage": "Ending",
        "label": "JtS Ending Theme",
        "p1_duty": 3,   # 75% wide triumphant
        "p2_duty": 1,   # 25% bright counterpoint
        "mood": "heroic",
        "description": "Wide 75% lead with bright harmony - triumphant resolution",
    },
    # Gradius stages (Konami, 1986) - space shooter with distinct alien timbres
    {
        "game": "Gradius",
        "stage": "Mountains",
        "label": "Gradius Mountains",
        "p1_duty": 3,   # 75% wide swell
        "p2_duty": 3,   # 75% wide swell
        "mood": "heroic",
        "description": "Dual 75% wide pulses - bold space opera feel",
    },
    {
        "game": "Gradius",
        "stage": "Beginning",
        "label": "Gradius Beginning",
        "p1_duty": 1,   # 25% bright
        "p2_duty": 3,   # 75% wide contrast
        "mood": "bright",
        "description": "Bright lead vs wide pad - optimistic launch feel",
    },
    {
        "game": "Gradius",
        "stage": "Boss",
        "label": "Gradius Boss",
        "p1_duty": 0,   # 12.5% thin threat
        "p2_duty": 0,   # 12.5% thin threat
        "mood": "tense",
        "description": "Both pulses thin 12.5% - alien metallic menace",
    },
    # Ghosts 'n' Goblins (Capcom/Micronics, 1986) - horror platformer
    {
        "game": "GhostsNGoblins",
        "stage": "Stage1",
        "label": "GnG Stage 1",
        "p1_duty": 1,   # 25% bright
        "p2_duty": 1,   # 25% bright
        "mood": "dark",
        "description": "Dual bright 25% - Capcom gothic energy",
    },
    # Bionic Commando stages (Capcom, 1988) - military spy action with varied timbres
    {
        "game": "BionicCommando",
        "stage": "EnemyBase",
        "label": "BC Enemy Base",
        "p1_duty": 2,   # 50% warm
        "p2_duty": 2,   # 50% warm
        "mood": "dark",
        "description": "Dual 50% warm squares - dense military infiltration",
    },
    {
        "game": "BionicCommando",
        "stage": "AlbatrossTower",
        "label": "BC Albatross Tower",
        "p1_duty": 3,   # 75% wide aggressive
        "p2_duty": 3,   # 75% wide aggressive
        "mood": "intense",
        "description": "Dual 75% wide pulses - aggressive tower assault",
    },
    {
        "game": "BionicCommando",
        "stage": "MunitionsBase",
        "label": "BC Munitions Base",
        "p1_duty": 1,   # 25% bright lead
        "p2_duty": 3,   # 75% wide pad
        "mood": "heroic",
        "description": "Bright 25% lead against wide 75% pad - action contrast",
    },
    {
        "game": "BionicCommando",
        "stage": "AlbatrossHQ",
        "label": "BC Albatross HQ",
        "p1_duty": 0,   # 12.5% thin
        "p2_duty": 1,   # 25% bright
        "mood": "tense",
        "description": "Thin 12.5% lead + bright 25% harmony - covert tension",
    },
    {
        "game": "BionicCommando",
        "stage": "NeutralZone",
        "label": "BC Neutral Zone",
        "p1_duty": 0,   # 12.5% thin
        "p2_duty": 0,   # 12.5% thin
        "mood": "eerie",
        "description": "Dual 12.5% thin pulses - eerie no-man's-land",
    },
    {
        "game": "BionicCommando",
        "stage": "StaffRoll",
        "label": "BC Staff Roll",
        "p1_duty": 1,   # 25% bright
        "p2_duty": 0,   # 12.5% thin shimmer
        "mood": "heroic",
        "description": "Bright 25% lead with thin shimmer - triumphant finale",
    },
]

# ──────────────────────────────────────────────────────────────────────
#  Bach piece selection with musical metadata
# ──────────────────────────────────────────────────────────────────────

BACH_PIECES = [
    # ── 2-voice Inventions (pulse1 + pulse2 counterpoint) ──
    {"file": "invent1.mid",  "title": "Two-Part Invention No.1 in C",
     "voices": 2, "key": "C major", "mood": "bright", "tempo_feel": "moderate"},
    {"file": "invent2.mid",  "title": "Two-Part Invention No.2 in C minor",
     "voices": 2, "key": "C minor", "mood": "dark", "tempo_feel": "driving"},
    {"file": "invent3.mid",  "title": "Two-Part Invention No.3 in D",
     "voices": 2, "key": "D major", "mood": "bright", "tempo_feel": "fast"},
    {"file": "invent4.mid",  "title": "Two-Part Invention No.4 in D minor",
     "voices": 2, "key": "D minor", "mood": "dark", "tempo_feel": "flowing"},
    {"file": "invent5.mid",  "title": "Two-Part Invention No.5 in Eb",
     "voices": 2, "key": "Eb major", "mood": "heroic", "tempo_feel": "lyrical"},
    {"file": "invent7.mid",  "title": "Two-Part Invention No.7 in E minor",
     "voices": 2, "key": "E minor", "mood": "dark", "tempo_feel": "passionate"},
    {"file": "invent8.mid",  "title": "Two-Part Invention No.8 in F",
     "voices": 2, "key": "F major", "mood": "bright", "tempo_feel": "fast"},
    {"file": "invent9.mid",  "title": "Two-Part Invention No.9 in F minor",
     "voices": 2, "key": "F minor", "mood": "dark", "tempo_feel": "dramatic"},
    {"file": "invent10.mid", "title": "Two-Part Invention No.10 in G",
     "voices": 2, "key": "G major", "mood": "bright", "tempo_feel": "dance"},
    {"file": "invent11.mid", "title": "Two-Part Invention No.11 in G minor",
     "voices": 2, "key": "G minor", "mood": "dark", "tempo_feel": "expressive"},
    {"file": "invent12.mid", "title": "Two-Part Invention No.12 in A",
     "voices": 2, "key": "A major", "mood": "bright", "tempo_feel": "dance"},
    {"file": "invent13.mid", "title": "Two-Part Invention No.13 in A minor",
     "voices": 2, "key": "A minor", "mood": "dark", "tempo_feel": "expressive"},
    {"file": "invent14.mid", "title": "Two-Part Invention No.14 in Bb",
     "voices": 2, "key": "Bb major", "mood": "bright", "tempo_feel": "dance"},
    {"file": "invent15.mid", "title": "Two-Part Invention No.15 in B minor",
     "voices": 2, "key": "B minor", "mood": "dark", "tempo_feel": "dramatic"},

    # ── 2-voice Preludes & Fugues ──
    {"file": "Fugue10.mid",  "title": "WTC Fugue No.10 in E minor",
     "voices": 2, "key": "E minor", "mood": "dark", "tempo_feel": "flowing"},
    {"file": "Prelude2.mid", "title": "WTC Prelude No.2 in C minor",
     "voices": 2, "key": "C minor", "mood": "dark", "tempo_feel": "perpetual"},
    {"file": "Prelude6.mid", "title": "WTC Prelude No.6 in D minor",
     "voices": 2, "key": "D minor", "mood": "dark", "tempo_feel": "lively"},
    {"file": "var5.mid",     "title": "Goldberg Variation 5",
     "voices": 2, "key": "G major", "mood": "bright", "tempo_feel": "fast"},
    {"file": "cou1.mid",     "title": "Cello Suite 1 - Courante",
     "voices": 2, "key": "G major", "mood": "heroic", "tempo_feel": "dance"},
    {"file": "prefug1.mid",  "title": "Prelude & Fugue in A minor BWV 543",
     "voices": 2, "key": "A minor", "mood": "dark", "tempo_feel": "dramatic"},

    # ── 3-voice pieces (pulse1 + pulse2 + triangle bass) ──
    {"file": "Fugue1.mid",   "title": "WTC Fugue No.1 in C",
     "voices": 3, "key": "C major", "mood": "bright", "tempo_feel": "moderate"},
    {"file": "Fugue2.mid",   "title": "WTC Fugue No.2 in C minor",
     "voices": 3, "key": "C minor", "mood": "dark", "tempo_feel": "driving"},
    {"file": "Fugue3.mid",   "title": "WTC Fugue No.3 in C#",
     "voices": 3, "key": "C# major", "mood": "bright", "tempo_feel": "fast"},
    {"file": "Fugue7.mid",   "title": "WTC Fugue No.7 in Eb",
     "voices": 3, "key": "Eb major", "mood": "heroic", "tempo_feel": "majestic"},
    {"file": "Fugue9.mid",   "title": "WTC Fugue No.9 in E",
     "voices": 3, "key": "E major", "mood": "bright", "tempo_feel": "pastoral"},
    {"file": "sinfon1.mid",  "title": "Three-Part Sinfonia No.1 in C",
     "voices": 3, "key": "C major", "mood": "bright", "tempo_feel": "moderate"},
    {"file": "Prelude9.mid", "title": "WTC Prelude No.9 in E",
     "voices": 3, "key": "E major", "mood": "bright", "tempo_feel": "short"},
    {"file": "Prelude10.mid","title": "WTC Prelude No.10 in E minor",
     "voices": 3, "key": "E minor", "mood": "dark", "tempo_feel": "brooding"},
    {"file": "var1.mid",     "title": "Goldberg Variation 1",
     "voices": 3, "key": "G major", "mood": "bright", "tempo_feel": "dance"},
    {"file": "var3c1.mid",   "title": "Goldberg Variation 3 (Canon)",
     "voices": 3, "key": "G major", "mood": "atmospheric", "tempo_feel": "flowing"},
    {"file": "var6c2.mid",   "title": "Goldberg Variation 6 (Canon at 2nd)",
     "voices": 3, "key": "G major", "mood": "bright", "tempo_feel": "fast"},
    {"file": "gig1.mid",     "title": "Cello Suite 1 - Gigue",
     "voices": 3, "key": "G major", "mood": "heroic", "tempo_feel": "fast"},

    # ── 4-voice pieces (full NES: pulse1 + pulse2 + triangle + noise) ──
    {"file": "Fugue4.mid",   "title": "WTC Fugue No.4 in C# minor",
     "voices": 4, "key": "C# minor", "mood": "dark", "tempo_feel": "solemn"},
    {"file": "Fugue5.mid",   "title": "WTC Fugue No.5 in D",
     "voices": 4, "key": "D major", "mood": "heroic", "tempo_feel": "dance"},
    {"file": "Fugue14.mid",  "title": "WTC Fugue No.14 in F# minor",
     "voices": 4, "key": "F# minor", "mood": "dark", "tempo_feel": "solemn"},
    {"file": "Prelude4.mid", "title": "WTC Prelude No.4 in C# minor",
     "voices": 4, "key": "C# minor", "mood": "dark", "tempo_feel": "grave"},
    {"file": "Prelude12.mid","title": "WTC Prelude No.12 in F minor",
     "voices": 4, "key": "F minor", "mood": "dark", "tempo_feel": "intense"},
    {"file": "aria.mid",     "title": "Goldberg Aria",
     "voices": 4, "key": "G major", "mood": "atmospheric", "tempo_feel": "slow"},
    {"file": "var4.mid",     "title": "Goldberg Variation 4",
     "voices": 4, "key": "G major", "mood": "heroic", "tempo_feel": "moderate"},
    {"file": "pre1.mid",     "title": "Cello Suite 1 - Prelude",
     "voices": 4, "key": "G major", "mood": "atmospheric", "tempo_feel": "flowing"},
    {"file": "all1.mid",     "title": "Cello Suite 1 - Allemande",
     "voices": 4, "key": "G major", "mood": "atmospheric", "tempo_feel": "stately"},

    # ── Solo pieces (single arpeggio line through one channel) ──
    {"file": "Prelude1.mid", "title": "WTC Prelude No.1 in C",
     "voices": 1, "key": "C major", "mood": "atmospheric", "tempo_feel": "flowing"},
    {"file": "toccata1.mid", "title": "Toccata in D minor BWV 565",
     "voices": 3, "key": "D minor", "mood": "dark", "tempo_feel": "dramatic"},

    # ── BWV collection (Prelude & Fugue pairs) ──
    {"file": "bach_846.mid", "title": "WTC1 Prelude & Fugue No.1 BWV 846",
     "voices": 4, "key": "C major", "mood": "bright", "tempo_feel": "moderate"},
    {"file": "bach_847.mid", "title": "WTC1 Prelude & Fugue No.2 BWV 847",
     "voices": 3, "key": "C minor", "mood": "dark", "tempo_feel": "driving"},
    {"file": "bach_850.mid", "title": "WTC1 Prelude & Fugue No.5 BWV 850",
     "voices": 4, "key": "D major", "mood": "heroic", "tempo_feel": "dance"},

    # ── Mozart ──
    {"file": "rondo_alla_turca_fixed.mid", "title": "Mozart Rondo alla Turca K.331",
     "voices": 3, "key": "A major", "mood": "bright", "tempo_feel": "fast"},
    {"file": "symphony40_mv1.mid", "title": "Mozart Symphony No.40 Mvt.1",
     "voices": 3, "key": "G minor", "mood": "dark", "tempo_feel": "driving"},

    # ── Beethoven ──
    {"file": "fur_elise.mid", "title": "Beethoven Fur Elise",
     "voices": 3, "key": "A minor", "mood": "atmospheric", "tempo_feel": "moderate"},
    {"file": "moonlight_mv1.mid", "title": "Beethoven Moonlight Sonata Mvt.1",
     "voices": 4, "key": "C# minor", "mood": "dark", "tempo_feel": "slow"},
    {"file": "moonlight_mv3.mid", "title": "Beethoven Moonlight Sonata Mvt.3",
     "voices": 4, "key": "C# minor", "mood": "intense", "tempo_feel": "fast"},
    {"file": "pathetique_mv2.mid", "title": "Beethoven Pathetique Sonata Mvt.2",
     "voices": 3, "key": "Ab major", "mood": "atmospheric", "tempo_feel": "lyrical"},
    {"file": "symphony5_mv1.mid", "title": "Beethoven Symphony No.5 Mvt.1",
     "voices": 4, "key": "C minor", "mood": "heroic", "tempo_feel": "dramatic"},
]

# Mood compatibility scoring
MOOD_COMPAT = {
    ("bright", "heroic"): 9,
    ("bright", "bright"): 8,
    ("bright", "atmospheric"): 6,
    ("bright", "intense"): 7,
    ("bright", "aggressive"): 5,
    ("bright", "eerie"): 3,
    ("bright", "tense"): 4,
    ("bright", "dark"): 4,
    ("bright", "ominous"): 3,
    ("dark", "dark"): 9,
    ("dark", "atmospheric"): 8,
    ("dark", "eerie"): 9,
    ("dark", "tense"): 8,
    ("dark", "ominous"): 9,
    ("dark", "intense"): 7,
    ("dark", "heroic"): 5,
    ("dark", "bright"): 4,
    ("dark", "aggressive"): 7,
    ("heroic", "heroic"): 9,
    ("heroic", "intense"): 8,
    ("heroic", "bright"): 7,
    ("heroic", "aggressive"): 8,
    ("heroic", "atmospheric"): 6,
    ("heroic", "dark"): 5,
    ("heroic", "eerie"): 3,
    ("heroic", "tense"): 5,
    ("heroic", "ominous"): 4,
    ("atmospheric", "atmospheric"): 9,
    ("atmospheric", "eerie"): 8,
    ("atmospheric", "dark"): 7,
    ("atmospheric", "heroic"): 6,
    ("atmospheric", "tense"): 7,
    ("atmospheric", "ominous"): 7,
    ("atmospheric", "bright"): 5,
    ("atmospheric", "intense"): 4,
    ("atmospheric", "aggressive"): 3,
}


def mood_score(bach_mood: str, stage_mood: str) -> int:
    """Score mood compatibility 0-10."""
    return max(
        MOOD_COMPAT.get((bach_mood, stage_mood), 5),
        MOOD_COMPAT.get((stage_mood, bach_mood), 5),
    )


# ──────────────────────────────────────────────────────────────────────
#  NES APU Synthesis (from MIDI)
# ──────────────────────────────────────────────────────────────────────

DUTY_TABLES = {
    0: [0, 1, 0, 0, 0, 0, 0, 0],  # 12.5%
    1: [0, 1, 1, 0, 0, 0, 0, 0],  # 25%
    2: [0, 1, 1, 1, 1, 0, 0, 0],  # 50%
    3: [1, 0, 0, 1, 1, 1, 1, 1],  # 75%
}

TRIANGLE_WAVE = [
    15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0,
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
]


def midi_note_to_freq(note: int) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def midi_note_to_nes_period(note: int, is_triangle: bool = False) -> int:
    """Convert MIDI note to NES timer period."""
    freq = midi_note_to_freq(note)
    if is_triangle:
        period = int(round(CPU_CLK / (32.0 * freq) - 1))
    else:
        period = int(round(CPU_CLK / (16.0 * freq) - 1))
    return max(0, period)


def render_pulse_samples(freq: float, duty: int, volume: float,
                         num_samples: int, phase: float) -> tuple[np.ndarray, float]:
    """Render pulse wave samples."""
    if volume <= 0 or freq <= 0:
        return np.zeros(num_samples, dtype=np.float32), phase

    duty_table = DUTY_TABLES.get(duty, DUTY_TABLES[2])
    inc = 8.0 * freq / SAMPLE_RATE

    out = np.empty(num_samples, dtype=np.float32)
    p = phase
    for i in range(num_samples):
        step = int(p) & 7
        out[i] = (duty_table[step] * 2.0 - 1.0) * volume
        p += inc
        while p >= 8.0:
            p -= 8.0

    return out, p


def render_triangle_samples(freq: float, num_samples: int,
                            phase: float) -> tuple[np.ndarray, float]:
    """Render triangle wave samples."""
    if freq <= 0:
        return np.zeros(num_samples, dtype=np.float32), phase

    inc = 32.0 * freq / SAMPLE_RATE
    out = np.empty(num_samples, dtype=np.float32)
    p = phase
    for i in range(num_samples):
        step = int(p) & 31
        out[i] = TRIANGLE_WAVE[step] / 15.0 * 2.0 - 1.0
        p += inc
        while p >= 32.0:
            p -= 32.0

    return out, p


def render_noise_hit(num_samples: int, volume: float = 0.6,
                     decay: float = 12.0) -> np.ndarray:
    """Render a noise percussion hit."""
    out = np.random.uniform(-1, 1, num_samples).astype(np.float32)
    env = np.exp(-np.arange(num_samples) * decay / SAMPLE_RATE)
    return out * env * volume


# ──────────────────────────────────────────────────────────────────────
#  MIDI → NES WAV Renderer
# ──────────────────────────────────────────────────────────────────────

class MidiNesRenderer:
    """Render a MIDI file through NES APU synthesis."""

    def __init__(self, p1_duty: int = 2, p2_duty: int = 1):
        self.p1_duty = p1_duty
        self.p2_duty = p2_duty

    def render(self, midi_path: Path) -> np.ndarray:
        """Render MIDI file to audio samples."""
        mid = mido.MidiFile(str(midi_path))
        duration_s = mid.length + 1.0  # +1s tail
        total_samples = int(duration_s * SAMPLE_RATE)
        mix = np.zeros(total_samples, dtype=np.float32)

        # Analyze channels
        channel_stats = {}
        for track in mid.tracks:
            for msg in track:
                if msg.type == "note_on" and msg.velocity > 0:
                    ch = msg.channel
                    if ch not in channel_stats:
                        channel_stats[ch] = {"notes": [], "count": 0, "is_drum": ch == 9}
                    channel_stats[ch]["notes"].append(msg.note)
                    channel_stats[ch]["count"] += 1

        for ch, stats in channel_stats.items():
            stats["avg_note"] = sum(stats["notes"]) / len(stats["notes"])

        # Auto-map channels to NES roles
        drums = [ch for ch, s in channel_stats.items() if s["is_drum"]]
        melodic = sorted(
            [ch for ch, s in channel_stats.items() if not s["is_drum"]],
            key=lambda c: channel_stats[c]["avg_note"],
        )

        role_map = {}  # original_ch -> role
        if melodic:
            role_map[melodic[0]] = "triangle"  # lowest = bass
            if len(melodic) >= 2:
                # Sort remaining by note count (busiest = lead)
                rest = sorted(melodic[1:],
                              key=lambda c: channel_stats[c]["count"], reverse=True)
                role_map[rest[0]] = "pulse1"
                if len(rest) >= 2:
                    role_map[rest[1]] = "pulse2"
            if len(melodic) == 1:
                # Single channel → pulse1 (more musical than triangle alone)
                role_map[melodic[0]] = "pulse1"
            if len(melodic) == 2:
                # 2 channels: higher = pulse1, lower stays triangle
                higher = melodic[1]
                role_map[higher] = "pulse1"

        for ch in drums:
            role_map[ch] = "noise"

        # Flatten all tracks to absolute-time events
        events = []
        for track in mid.tracks:
            abs_time = 0.0
            for msg in track:
                abs_time += mido.tick2second(msg.time, mid.ticks_per_beat,
                                              self._get_tempo(mid))
                if msg.type in ("note_on", "note_off"):
                    events.append((abs_time, msg))

        events.sort(key=lambda x: x[0])

        # Per-channel state
        active_notes = {}  # (ch, note) -> (start_sample, velocity)
        phases = {"pulse1": 0.0, "pulse2": 0.0, "triangle": 0.0}

        # Process events and render
        for abs_time, msg in events:
            ch = msg.channel
            role = role_map.get(ch)
            if role is None:
                continue

            sample_pos = int(abs_time * SAMPLE_RATE)
            sample_pos = min(sample_pos, total_samples - 1)
            key = (ch, msg.note)

            if msg.type == "note_on" and msg.velocity > 0:
                # End previous note on same channel+note if any
                if key in active_notes:
                    self._render_note(mix, active_notes.pop(key), sample_pos,
                                      msg.note, role, phases, total_samples)
                active_notes[key] = (sample_pos, msg.velocity)

            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                if key in active_notes:
                    self._render_note(mix, active_notes.pop(key), sample_pos,
                                      msg.note, role, phases, total_samples)

        # Render remaining active notes to end
        for key, (start, vel) in active_notes.items():
            ch, note = key
            role = role_map.get(ch)
            if role:
                self._render_note(mix, (start, vel), total_samples,
                                  note, role, phases, total_samples)

        # Normalize
        peak = np.max(np.abs(mix))
        if peak > 0:
            mix = mix / peak * 0.85

        return mix

    def _get_tempo(self, mid) -> int:
        """Extract tempo from MIDI file."""
        for track in mid.tracks:
            for msg in track:
                if msg.type == "set_tempo":
                    return msg.tempo
        return 500000  # 120 BPM default

    def _render_note(self, mix: np.ndarray, note_info: tuple,
                     end_sample: int, midi_note: int, role: str,
                     phases: dict, total_samples: int) -> None:
        """Render a single note into the mix buffer."""
        start_sample, velocity = note_info
        num_samples = end_sample - start_sample
        if num_samples <= 0:
            return

        vol = velocity / 127.0

        if role == "pulse1":
            freq = midi_note_to_freq(midi_note)
            audio, phases["pulse1"] = render_pulse_samples(
                freq, self.p1_duty, vol, num_samples, phases["pulse1"])
            end = min(start_sample + num_samples, total_samples)
            mix[start_sample:end] += audio[:end - start_sample] * 0.28

        elif role == "pulse2":
            freq = midi_note_to_freq(midi_note)
            audio, phases["pulse2"] = render_pulse_samples(
                freq, self.p2_duty, vol, num_samples, phases["pulse2"])
            end = min(start_sample + num_samples, total_samples)
            mix[start_sample:end] += audio[:end - start_sample] * 0.25

        elif role == "triangle":
            freq = midi_note_to_freq(midi_note)
            audio, phases["triangle"] = render_triangle_samples(
                freq, num_samples, phases["triangle"])
            end = min(start_sample + num_samples, total_samples)
            mix[start_sample:end] += audio[:end - start_sample] * 0.22

        elif role == "noise":
            # Simple drum hit
            hit_len = min(num_samples, SAMPLE_RATE // 4)  # max 0.25s
            audio = render_noise_hit(hit_len, vol * 0.5, 15.0)
            end = min(start_sample + hit_len, total_samples)
            mix[start_sample:end] += audio[:end - start_sample]


def write_wav(samples: np.ndarray, path: Path) -> None:
    """Write float32 samples to 16-bit WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    s16 = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(s16.tobytes())


# ──────────────────────────────────────────────────────────────────────
#  REAPER Project Generation
# ──────────────────────────────────────────────────────────────────────

COLORS = {"pulse1": 16576606, "pulse2": 10092441, "triangle": 16744192, "noise": 11184810}
CHANNEL_LABELS = {
    "pulse1": "NES - Pulse 1", "pulse2": "NES - Pulse 2",
    "triangle": "NES - Triangle", "noise": "NES - Noise / Drums",
}
CHANNEL_MODES = {"pulse1": 0, "pulse2": 1, "triangle": 2, "noise": 3}

FULL_APU_DEFAULTS = [2, 15, 1, 1, 15, 1, 1, 0, 0, 15, 1, 0.8, 4]


def make_guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def fmt_slider_values(values: list, total: int = 64) -> str:
    parts = []
    for i in range(total):
        if i < len(values):
            v = values[i]
            if isinstance(v, float) and v != int(v):
                parts.append(f"{v:.6f}")
            else:
                parts.append(f"{int(v)}" if v == int(v) else f"{v}")
        else:
            parts.append("-")
    return " ".join(parts)


def generate_rpp(midi_path: Path, output_path: Path, stage: dict,
                 bach_title: str) -> None:
    """Generate a REAPER project with stage-specific NES instrument settings."""
    mid = mido.MidiFile(str(midi_path))
    tempo_us = 500000
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                tempo_us = msg.tempo
                break
    tempo_bpm = 60_000_000 / tempo_us
    duration = mid.length

    title = f"Bach × {stage['label']} — {bach_title}"

    lines = [f"""<REAPER_PROJECT 0.1 "7.27/win64" 1707000000
  RIPPLE 0
  GROUPOVERRIDE 0 0 0
  AUTOXFADE 129
  TEMPO {tempo_bpm} 4 4
  PLAYRATE 1 0 0.25 4
  MASTERAUTOMODE 0
  MASTER_VOLUME 1 0 -1 -1 1
  MASTER_NCH 2 2
  <NOTES
    |ReapNES Studio — Bach x NES Mashup
    |{title}
    |Stage preset: {stage['description']}
  >"""]

    midi_path_fwd = str(midi_path.resolve()).replace("\\", "/")

    for role in ["pulse1", "pulse2", "triangle", "noise"]:
        vals = list(FULL_APU_DEFAULTS)
        vals[12] = CHANNEL_MODES[role]

        # Apply stage-specific duty cycles
        if role == "pulse1":
            vals[0] = stage["p1_duty"]
        elif role == "pulse2":
            vals[3] = stage["p2_duty"]

        name = f"{CHANNEL_LABELS[role]} [{stage['label']}]"
        params = fmt_slider_values(vals)
        track_guid = make_guid()

        track_lines = f"""  <TRACK {track_guid}
    NAME "{name}"
    PEAKCOL {COLORS[role]}
    BEAT -1
    AUTOMODE 0
    VOLPAN 1 0 -1 -1 1
    MUTESOLO 0 0 0
    IPHASE 0
    PLAYOFFS 0 1
    ISBUS 0 0
    BUSCOMP 0 0 0 0 0
    NCHAN 2
    FX 1
    TRACKID {track_guid}
    PERF 0
    MIDIOUT -1
    MAINSEND 1 0
    REC 0 5088 1 0 0 0 0 0
    VU 2
    <FXCHAIN
      SHOW 0
      LASTSEL 0
      DOCKED 0
      BYPASS 0 0 0
      <JS "ReapNES Studio/ReapNES_APU.jsfx" ""
        {params}
      >
      FLOATPOS 0 0 0 0
      FXID {make_guid()}
      WAK 0 0
    >
    <ITEM
      POSITION 0
      LENGTH {duration}
      LOOP 0
      ALLTAKES 0
      FADEIN 0 0 0 0 0 0 0
      FADEOUT 0 0 0 0 0 0 0
      MUTE 0 0
      SEL 0
      IGUID {make_guid()}
      <SOURCE MIDI
        FILE "{midi_path_fwd}"
      >
    >
  >"""
        lines.append(track_lines)

    lines.append(">")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────
#  Combo scoring and generation
# ──────────────────────────────────────────────────────────────────────

def score_combo(bach: dict, stage: dict) -> int:
    """Score a Bach piece × NES stage combination."""
    return mood_score(bach["mood"], stage["mood"])


NEW_GAMES = {"JourneyToSilius", "Gradius", "GhostsNGoblins", "BionicCommando"}


def get_all_combos(voices: int | None = None,
                   new_games_only: bool = False,
                   game: str | None = None,
                   composer: str | None = None) -> list[dict]:
    """Generate all valid Bach × Stage combinations with scores.

    Args:
        voices: If set, filter to Bach pieces with this many voices.
        new_games_only: If True, only include new game stage presets.
        game: If set, only include stages from this game.
        composer: If set, filter pieces by title prefix (e.g. "Mozart", "Beethoven").
    """
    combos = []
    for bach in BACH_PIECES:
        if voices is not None and bach["voices"] != voices:
            continue
        if composer and not bach["title"].lower().startswith(composer.lower()):
            continue
        midi_path = find_midi(bach["file"])
        if midi_path is None:
            continue
        for stage in STAGE_PRESETS:
            if new_games_only and stage["game"] not in NEW_GAMES:
                continue
            if game and stage["game"] != game:
                continue
            s = score_combo(bach, stage)
            combos.append({
                "bach": bach,
                "stage": stage,
                "score": s,
                "name": f"{bach['file'].replace('.mid','')}_{stage['game']}_{stage['stage']}",
            })
    combos.sort(key=lambda x: x["score"], reverse=True)
    return combos


def generate_all_projects(voices: int | None = None,
                          new_games_only: bool = False,
                          game: str | None = None,
                          composer: str | None = None) -> list[dict]:
    """Generate REAPER projects for all combinations."""
    combos = get_all_combos(voices=voices, new_games_only=new_games_only,
                            game=game, composer=composer)
    generated = []

    for combo in combos:
        bach = combo["bach"]
        stage = combo["stage"]
        midi_path = find_midi(bach["file"])
        if midi_path is None:
            continue
        rpp_path = PROJECTS_DIR / f"{combo['name']}.rpp"

        generate_rpp(midi_path, rpp_path, stage, bach["title"])
        generated.append(combo)
        print(f"  [{combo['score']}/10] {rpp_path.name}")

    return generated


def render_best_wavs(top_n: int = 12) -> list[Path]:
    """Render WAV files for the top-scoring combinations."""
    combos = get_all_combos()

    # Pick top combos, ensuring variety (max 2 per Bach piece, max 3 per stage)
    selected = []
    bach_count = {}
    stage_count = {}

    for combo in combos:
        bach_key = combo["bach"]["file"]
        stage_key = combo["stage"]["stage"]
        if bach_count.get(bach_key, 0) >= 2:
            continue
        if stage_count.get(stage_key, 0) >= 3:
            continue
        selected.append(combo)
        bach_count[bach_key] = bach_count.get(bach_key, 0) + 1
        stage_count[stage_key] = stage_count.get(stage_key, 0) + 1
        if len(selected) >= top_n:
            break

    rendered = []
    for combo in selected:
        bach = combo["bach"]
        stage = combo["stage"]
        midi_path = MIDI_DIR / bach["file"]
        wav_path = WAV_DIR / f"{combo['name']}.wav"

        print(f"  Rendering [{combo['score']}/10] {wav_path.name} ...")
        renderer = MidiNesRenderer(p1_duty=stage["p1_duty"], p2_duty=stage["p2_duty"])
        samples = renderer.render(midi_path)
        write_wav(samples, wav_path)
        rendered.append(wav_path)
        print(f"    -> {wav_path} ({len(samples)/SAMPLE_RATE:.1f}s)")

    return rendered


# ──────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bach × NES Mashup Generator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--generate-all", action="store_true",
                       help="Generate all REAPER projects")
    group.add_argument("--render-best", action="store_true",
                       help="Render WAV files for top-scoring combos")
    group.add_argument("--list", action="store_true",
                       help="List all combinations with scores")
    group.add_argument("--all", action="store_true",
                       help="Generate projects AND render best WAVs")
    parser.add_argument("--top", type=int, default=12,
                        help="Number of WAVs to render (default: 12)")
    parser.add_argument("--voices", type=int, default=None,
                        help="Filter to N-voice Bach pieces (e.g. --voices 3)")
    parser.add_argument("--new-games", action="store_true",
                        help="Only use new game presets (Gradius, JtS, GnG, BC)")
    parser.add_argument("--game", type=str, default=None,
                        help="Filter to specific game (e.g. BionicCommando)")
    parser.add_argument("--composer", type=str, default=None,
                        help="Filter pieces by composer prefix (e.g. Mozart, Beethoven)")

    args = parser.parse_args()
    filt = dict(voices=args.voices, new_games_only=args.new_games,
                game=args.game, composer=args.composer)

    if args.list:
        combos = get_all_combos(**filt)
        print(f"{'Score':>5}  {'Bach Piece':<45} {'NES Stage':<25} {'Moods'}")
        print("-" * 100)
        for c in combos:
            print(f"  {c['score']:>3}   {c['bach']['title']:<45} "
                  f"{c['stage']['label']:<25} "
                  f"{c['bach']['mood']} × {c['stage']['mood']}")
        print(f"\nTotal: {len(combos)} combinations")

    elif args.generate_all:
        print("Generating REAPER projects...")
        generated = generate_all_projects(**filt)
        print(f"\nGenerated {len(generated)} projects in {PROJECTS_DIR}")

    elif args.render_best:
        print("Rendering top WAV files...")
        rendered = render_best_wavs(args.top)
        print(f"\nRendered {len(rendered)} WAV files in {WAV_DIR}")

    elif args.all:
        print("=== Generating REAPER projects ===")
        generated = generate_all_projects(**filt)
        print(f"\nGenerated {len(generated)} projects in {PROJECTS_DIR}")
        print(f"\n=== Rendering top {args.top} WAV files ===")
        rendered = render_best_wavs(args.top)
        print(f"\nRendered {len(rendered)} WAV files in {WAV_DIR}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
