"""ROM manifest generator.

Scans the roms/ directory, parses iNES headers, and produces a manifest
JSON file with metadata for each ROM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nesml.static_analysis.ines import parse_header, mapper_name, INESError


def scan_roms(rom_dir: str | Path) -> list[dict]:
    """Scan a directory for .nes files and extract metadata.

    Returns a list of ROM info dicts sorted by filename.
    """
    rom_dir = Path(rom_dir)
    results = []

    for nes_file in sorted(rom_dir.glob("*.nes")):
        try:
            header = parse_header(nes_file)
            info = {
                "filename": nes_file.name,
                "file_size": nes_file.stat().st_size,
                **header,
                "mapper_name": mapper_name(header["mapper"]),
            }
            results.append(info)
        except INESError as e:
            results.append({
                "filename": nes_file.name,
                "error": str(e),
            })

    return results


def write_manifest(rom_dir: str | Path, output_path: str | Path) -> list[dict]:
    """Scan ROMs and write manifest JSON.

    Returns the manifest data.
    """
    roms = scan_roms(rom_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"roms": roms}, f, indent=2)

    return roms


if __name__ == "__main__":
    import sys
    rom_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("roms")
    manifest_path = rom_dir / "manifest.json"
    roms = write_manifest(rom_dir, manifest_path)
    for r in roms:
        if "error" in r:
            print(f"  ERROR: {r['filename']}: {r['error']}")
        else:
            print(
                f"  {r['filename']}: mapper={r['mapper']} ({r['mapper_name']}), "
                f"PRG={r['prg_rom_size']//1024}K, CHR={r['chr_rom_size']//1024}K, "
                f"{r['region'].upper()}"
            )
    print(f"\nManifest written to {manifest_path}")
