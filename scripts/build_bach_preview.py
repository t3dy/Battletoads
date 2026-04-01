#!/usr/bin/env python3
"""Build 'Chipped On Bach Preview' MP4 + YouTube description from bach_mashups WAVs."""

import subprocess, os, sys, tempfile

MASHUP_DIR = r"C:\Dev\NESMusicStudio\output\bach_mashups"
IMAGE = r"C:\Dev\Winterart_0003_HorribleTshirt.webp"
OUT_MP4 = r"C:\Dev\Chipped_On_Bach_Preview.mp4"
OUT_TXT = r"C:\Dev\Chipped_On_Bach_Preview.txt"

# --- Bach piece expansion ---
BACH_MAP = {
    "Bach_goldberg_variations_988_x": "Goldberg Variations, BWV 988",
    "Fugue2":  "Well-Tempered Clavier, Fugue No. 2 in C minor, BWV 847",
    "Fugue3":  "Well-Tempered Clavier, Fugue No. 3 in C-sharp major, BWV 848",
    "Fugue4":  "Well-Tempered Clavier, Fugue No. 4 in C-sharp minor, BWV 849",
    "Fugue5":  "Well-Tempered Clavier, Fugue No. 5 in D major, BWV 850",
    "Fugue7":  "Well-Tempered Clavier, Fugue No. 7 in E-flat major, BWV 852",
    "Fugue9":  "Well-Tempered Clavier, Fugue No. 9 in E major, BWV 854",
    "Fugue10": "Well-Tempered Clavier, Fugue No. 10 in E minor, BWV 855",
    "Fugue14": "Well-Tempered Clavier, Fugue No. 14 in F-sharp minor, BWV 859",
    "Prelude2":  "Well-Tempered Clavier, Prelude No. 2 in C minor, BWV 847",
    "Prelude4":  "Well-Tempered Clavier, Prelude No. 4 in C-sharp minor, BWV 849",
    "Prelude10": "Well-Tempered Clavier, Prelude No. 10 in E minor, BWV 855",
    "Prelude12": "Well-Tempered Clavier, Prelude No. 12 in F minor, BWV 857",
    "prefug1": "Well-Tempered Clavier, Prelude & Fugue No. 1 in C major, BWV 846",
    "invent1":  "Two-Part Invention No. 1 in C major, BWV 772",
    "invent2":  "Two-Part Invention No. 2 in C minor, BWV 773",
    "invent3":  "Two-Part Invention No. 3 in D major, BWV 774",
    "invent4":  "Two-Part Invention No. 4 in D minor, BWV 775",
    "invent5":  "Two-Part Invention No. 5 in E-flat major, BWV 776",
    "invent7":  "Two-Part Invention No. 7 in E minor, BWV 778",
    "invent8":  "Two-Part Invention No. 8 in F major, BWV 779",
    "invent9":  "Two-Part Invention No. 9 in F minor, BWV 780",
    "invent10": "Two-Part Invention No. 10 in G major, BWV 781",
    "invent11": "Two-Part Invention No. 11 in G minor, BWV 782",
    "invent12": "Two-Part Invention No. 12 in A major, BWV 783",
    "invent13": "Two-Part Invention No. 13 in A minor, BWV 784",
    "invent14": "Two-Part Invention No. 14 in B-flat major, BWV 785",
    "invent15": "Two-Part Invention No. 15 in B minor, BWV 786",
    "pre1":  "Cello Suite No. 1, Prelude in G major, BWV 1007",
    "all1":  "Cello Suite No. 1, Allemande in G major, BWV 1007",
    "cou1":  "Cello Suite No. 1, Courante in G major, BWV 1007",
    "gig1":  "Cello Suite No. 1, Gigue in G major, BWV 1007",
    "aria":  "Goldberg Variations, Aria, BWV 988",
    "var3c1": "Goldberg Variations, Variation 3 (Canon at the Unison), BWV 988",
    "var4":  "Goldberg Variations, Variation 4, BWV 988",
}

# --- Game/stage expansion ---
STAGE_MAP = {
    "Castlevania_VampireKiller": ("Castlevania", "Vampire Killer (Stage 1)"),
    "Castlevania_Stalker":      ("Castlevania", "Stalker (Stage 2)"),
    "Castlevania_WickedChild":  ("Castlevania", "Wicked Child (Stage 3)"),
    "Castlevania_NothingToLose":("Castlevania", "Nothing to Lose (Stage 4)"),
    "Castlevania_HeartOfFire":  ("Castlevania", "Heart of Fire (Stage 5)"),
    "Contra_Jungle":   ("Contra", "Jungle (Stage 1)"),
    "Contra_Waterfall": ("Contra", "Waterfall (Stage 3)"),
    "Contra_Maze":      ("Contra", "Energy Zone (Stage 6)"),
    "Contra_Flame":     ("Contra", "Base (Stages 2/4)"),
    "Metroid":          ("Metroid", ""),
}


def parse_filename(fname):
    """Return (bach_key, stage_key, notes) from filename without extension."""
    name = os.path.splitext(fname)[0]
    # Try each bach key (longest first to avoid partial matches)
    bach_key = None
    remainder = name
    for key in sorted(BACH_MAP.keys(), key=len, reverse=True):
        if name.startswith(key + "_"):
            bach_key = key
            remainder = name[len(key) + 1:]
            break
        elif name == key:
            bach_key = key
            remainder = ""
            break

    if not bach_key:
        return None, None, name

    # Try each stage key (longest first)
    stage_key = None
    notes = ""
    for key in sorted(STAGE_MAP.keys(), key=len, reverse=True):
        if remainder.startswith(key):
            stage_key = key
            leftover = remainder[len(key):].strip(" _")
            notes = leftover
            break

    if not stage_key:
        stage_key = remainder
        notes = ""

    return bach_key, stage_key, notes


def format_title(bach_key, stage_key, notes):
    bach_name = BACH_MAP.get(bach_key, bach_key)
    if stage_key in STAGE_MAP:
        game, stage = STAGE_MAP[stage_key]
        synth_part = f"{game} — {stage}" if stage else game
    else:
        synth_part = stage_key
    title = f"{bach_name} × {synth_part}"
    if notes:
        title += f" [{notes}]"
    return title


def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    return float(r.stdout.strip())


def seconds_to_ts(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def main():
    wavs = sorted(f for f in os.listdir(MASHUP_DIR) if f.lower().endswith(".wav"))
    if not wavs:
        print("No WAV files found"); sys.exit(1)

    print(f"Found {len(wavs)} WAV files")

    # Build tracklist with timestamps
    tracks = []
    offset = 0.0
    for wav in wavs:
        path = os.path.join(MASHUP_DIR, wav)
        dur = get_duration(path)
        bach_key, stage_key, notes = parse_filename(wav)
        title = format_title(bach_key, stage_key, notes)
        tracks.append((offset, title, dur, path))
        offset += dur

    total_dur = offset
    print(f"Total duration: {seconds_to_ts(total_dur)}")

    # Write YouTube description
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write("Chipped On Bach Preview\n")
        f.write("=" * 40 + "\n\n")
        f.write("J.S. Bach performed on NES synthesizers — each track pairs a Bach composition\n")
        f.write("with NES APU timbres extracted from classic Konami game soundtracks.\n\n")
        f.write("Tracklist\n")
        f.write("-" * 40 + "\n\n")
        for i, (ts, title, dur, _) in enumerate(tracks, 1):
            f.write(f"{seconds_to_ts(ts)} {title}\n")
        f.write(f"\nTotal runtime: {seconds_to_ts(total_dur)}\n")
        f.write("\nAll synthesis uses the NES Audio Processing Unit (2A03) via ReapNES JSFX.\n")
        f.write("MIDI sources: Classical MIDI archives. NES timbres: Castlevania, Contra, Metroid.\n")

    print(f"Wrote {OUT_TXT}")

    # Concat WAVs using ffmpeg concat demuxer
    concat_list = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    for _, _, _, path in tracks:
        concat_list.write(f"file '{path}'\n")
    concat_list.close()

    concat_wav = tempfile.mktemp(suffix=".wav")
    print("Concatenating WAVs...")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list.name, "-c", "copy", concat_wav
    ], check=True)

    # Build MP4: static image + concatenated audio
    print("Building MP4...")
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", IMAGE,
        "-i", concat_wav,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        OUT_MP4
    ], check=True)

    # Cleanup
    os.unlink(concat_list.name)
    os.unlink(concat_wav)

    print(f"\nDone!\n  MP4: {OUT_MP4}\n  TXT: {OUT_TXT}")


if __name__ == "__main__":
    main()
