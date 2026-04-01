#!/usr/bin/env python3
import sys
from pathlib import Path
from bach_render_mashup import render_mashup
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent

JOBS = [
    ("c:/Users/PC/Downloads/sinfon3.mid", "studio/song_sets/MegaMan2_13WoodManStage.json", "studio/reaper_projects/Bach_Sinfonia3_MM2_WoodMan.wav", "studio/reaper_projects/Bach_Sinfonia3_MM2_WoodMan.rpp"),
    ("c:/Users/PC/Downloads/sinfon4.mid", "studio/song_sets/MegaMan2_08BubbleManStage.json", "studio/reaper_projects/Bach_Sinfonia4_MM2_BubbleMan.wav", "studio/reaper_projects/Bach_Sinfonia4_MM2_BubbleMan.rpp"),
    ("c:/Users/PC/Downloads/BRAND2.MID", "studio/song_sets/MegaMan2_18DrWilyStage1.json", "studio/reaper_projects/Bach_Brandenburg2_MM2_Wily1.wav", "studio/reaper_projects/Bach_Brandenburg2_MM2_Wily1.rpp"),
    ("c:/Users/PC/Downloads/BRAND3.MID", "studio/song_sets/smb1_overworld.json", "studio/reaper_projects/Bach_Brandenburg3_SMB1_Overworld.wav", "studio/reaper_projects/Bach_Brandenburg3_SMB1_Overworld.rpp"),
    ("c:/Users/PC/Downloads/var4.mid", "studio/song_sets/Metroid_01TitleBGM.json", "studio/reaper_projects/Bach_GoldbergVar4_Metroid_Title.wav", "studio/reaper_projects/Bach_GoldbergVar4_Metroid_Title.rpp"),
    ("c:/Users/PC/Downloads/var5.mid", "studio/song_sets/MegaMan2_21Boss.json", "studio/reaper_projects/Bach_GoldbergVar5_MM2_Boss.wav", "studio/reaper_projects/Bach_GoldbergVar5_MM2_Boss.rpp"),
]

for midi, palette, output_wav, output_rpp in JOBS:
    print(f"[{midi}] -> [{palette}]")
    
    # First, generate the RPP project
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/generate_project.py"),
        "--midi", midi,
        "--palette", Path(palette).stem,
        "-o", str(REPO_ROOT / output_rpp)
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to generate project for {midi}. Error: {e}")
        continue
    except OSError as e:
        print(f"Warning: Unexpected OS Error parsing {midi}. Skipping. Error: {e}")
        continue
    
    # Then render the WAV
    render_mashup(Path(midi), REPO_ROOT / palette, REPO_ROOT / output_wav)

print("Batch rendering completed.")
