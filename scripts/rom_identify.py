#!/usr/bin/env python3
"""Deterministic NES ROM analysis tool.

Replaces 3-4 prompts of manual investigation per new game.
Reports: mapper, PRG layout, period table location, driver signature,
candidate pointer tables, and per-game manifest status.

Usage:
    python scripts/rom_identify.py <rom_path>
    python scripts/rom_identify.py --scan-dir <directory>
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Known Maezawa period table (first 6 entries as bytes for signature matching)
PERIOD_TABLE_SIG = struct.pack("<HHH", 1710, 1614, 1524)

# Mapper names
MAPPER_NAMES = {
    0: "NROM (linear, no banking)",
    1: "MMC1 (bank-switched, 16KB switchable + 16KB fixed)",
    2: "UNROM (bank-switched, 16KB switchable + 16KB fixed last)",
    3: "CNROM (CHR banking only)",
    4: "MMC3 (8KB switchable banks)",
    5: "MMC5 (complex, expansion audio)",
    7: "AxROM (32KB switchable)",
}


def read_ines_header(rom: bytes) -> dict:
    """Parse iNES header. Returns mapper, PRG/CHR bank counts, etc."""
    if rom[:4] != b'NES\x1a':
        return {"error": "Not a valid NES ROM (missing NES header)"}

    prg_banks = rom[4]
    chr_banks = rom[5]
    mapper = ((rom[6] >> 4) & 0xF) | (rom[7] & 0xF0)
    mirroring = "vertical" if rom[6] & 1 else "horizontal"
    battery = bool(rom[6] & 2)

    return {
        "prg_banks": prg_banks,
        "prg_size_kb": prg_banks * 16,
        "chr_banks": chr_banks,
        "chr_size_kb": chr_banks * 8,
        "mapper": mapper,
        "mapper_name": MAPPER_NAMES.get(mapper, f"Unknown mapper {mapper}"),
        "mirroring": mirroring,
        "battery_backed": battery,
        "rom_size": len(rom),
    }


def find_period_table(rom: bytes) -> list[dict]:
    """Search for the NES note period table (12 entries, 16-bit LE).

    Returns list of matches with offset, bank, and all 12 values.
    """
    results = []
    offset = 0
    while True:
        pos = rom.find(PERIOD_TABLE_SIG, offset)
        if pos == -1:
            break

        # Verify all 12 entries are in valid range (100-2000)
        valid = True
        periods = []
        for i in range(12):
            if pos + i * 2 + 1 >= len(rom):
                valid = False
                break
            p = struct.unpack_from("<H", rom, pos + i * 2)[0]
            periods.append(p)
            if p < 100 or p > 2000:
                valid = False

        if valid:
            # Determine which bank this is in
            prg_offset = pos - 16  # subtract iNES header
            bank = prg_offset // 16384
            bank_offset = prg_offset % 16384
            cpu_addr_if_8000 = 0x8000 + bank_offset
            cpu_addr_if_C000 = 0xC000 + bank_offset

            results.append({
                "rom_offset": pos,
                "prg_offset": prg_offset,
                "bank": bank,
                "bank_offset": bank_offset,
                "cpu_if_8000": f"${cpu_addr_if_8000:04X}",
                "cpu_if_C000": f"${cpu_addr_if_C000:04X}",
                "periods": periods,
            })

        offset = pos + 1

    return results


def detect_maezawa_signature(rom: bytes) -> dict:
    """Scan for Maezawa driver command patterns.

    Looks for:
    - E8 followed by DX (envelope enable + instrument) clusters
    - FE + count + 16-bit addr (repeat commands)
    - FD + 16-bit addr (subroutine calls)

    Returns confidence score and evidence.
    """
    e8_dx_count = 0
    fe_repeat_count = 0
    fd_sub_count = 0

    for i in range(16, len(rom) - 4):
        # E8 + DX pattern
        if rom[i] == 0xE8 and (rom[i + 1] >> 4) == 0xD and (rom[i + 1] & 0xF) > 0:
            e8_dx_count += 1

        # FE + reasonable count + valid pointer
        if rom[i] == 0xFE and i + 3 < len(rom):
            count = rom[i + 1]
            ptr = struct.unpack_from("<H", rom, i + 2)[0]
            if 1 <= count <= 20 and 0x8000 <= ptr <= 0xFFFF:
                fe_repeat_count += 1

        # FD + valid pointer
        if rom[i] == 0xFD and i + 2 < len(rom):
            ptr = struct.unpack_from("<H", rom, i + 1)[0]
            if 0x8000 <= ptr <= 0xFFFF:
                fd_sub_count += 1

    # Scoring
    # Real Maezawa ROMs have dozens of FE/FD patterns in the music data
    # and E8+DX at channel starts. Non-Maezawa ROMs may have scattered
    # coincidental matches but far fewer.
    score = 0.0
    evidence = []

    if fe_repeat_count >= 20:
        score += 0.4
        evidence.append(f"{fe_repeat_count} FE repeat patterns (strong)")
    elif fe_repeat_count >= 5:
        score += 0.2
        evidence.append(f"{fe_repeat_count} FE repeat patterns (moderate)")
    else:
        evidence.append(f"{fe_repeat_count} FE repeat patterns (weak)")

    if fd_sub_count >= 10:
        score += 0.3
        evidence.append(f"{fd_sub_count} FD subroutine patterns (strong)")
    elif fd_sub_count >= 3:
        score += 0.15
        evidence.append(f"{fd_sub_count} FD subroutine patterns (moderate)")
    else:
        evidence.append(f"{fd_sub_count} FD subroutine patterns (weak)")

    if e8_dx_count >= 5:
        score += 0.3
        evidence.append(f"{e8_dx_count} E8+DX clusters (strong)")
    elif e8_dx_count >= 2:
        score += 0.1
        evidence.append(f"{e8_dx_count} E8+DX clusters (weak)")
    else:
        evidence.append(f"{e8_dx_count} E8+DX clusters (none)")

    verdict = "LIKELY MAEZAWA" if score >= 0.6 else \
              "POSSIBLE MAEZAWA" if score >= 0.3 else \
              "NOT MAEZAWA"

    return {
        "verdict": verdict,
        "confidence": round(score, 2),
        "evidence": evidence,
        "counts": {
            "e8_dx": e8_dx_count,
            "fe_repeat": fe_repeat_count,
            "fd_subroutine": fd_sub_count,
        },
    }


def check_manifest(rom_path: Path) -> dict | None:
    """Check if a per-game manifest exists for this ROM."""
    manifest_dir = REPO_ROOT / "extraction" / "manifests"
    if not manifest_dir.exists():
        return None

    # Try matching by filename stem
    stem = rom_path.stem.lower()
    for mf in manifest_dir.glob("*.json"):
        manifest = json.loads(mf.read_text(encoding="utf-8"))
        for alias in manifest.get("rom_aliases", []):
            if alias.lower() in stem:
                return manifest

    return None


def identify_rom(rom_path: str) -> dict:
    """Full ROM identification report."""
    path = Path(rom_path)
    if not path.exists():
        return {"error": f"File not found: {path}"}

    with open(path, "rb") as f:
        rom = f.read()

    report = {"file": str(path), "filename": path.name}

    # Header
    header = read_ines_header(rom)
    report["header"] = header
    if "error" in header:
        return report

    # Period table
    period_tables = find_period_table(rom)
    report["period_tables"] = period_tables

    # Driver signature
    signature = detect_maezawa_signature(rom)
    report["driver_signature"] = signature

    # Manifest
    manifest = check_manifest(path)
    report["manifest"] = manifest

    return report


def print_report(report: dict):
    """Pretty-print the identification report."""
    print(f"=== {report['filename']} ===\n")

    if "error" in report:
        print(f"ERROR: {report['error']}")
        return

    h = report["header"]
    print(f"Mapper:  {h['mapper']} — {h['mapper_name']}")
    print(f"PRG:     {h['prg_banks']} banks ({h['prg_size_kb']}KB)")
    print(f"CHR:     {h['chr_banks']} banks ({h['chr_size_kb']}KB)")
    print(f"ROM:     {h['rom_size']} bytes")
    print()

    pts = report["period_tables"]
    if pts:
        print(f"Period table: {len(pts)} match(es)")
        for pt in pts:
            print(f"  ROM ${pt['rom_offset']:04X} (bank {pt['bank']}, "
                  f"CPU {pt['cpu_if_8000']} or {pt['cpu_if_C000']})")
    else:
        print("Period table: NOT FOUND")
    print()

    sig = report["driver_signature"]
    print(f"Driver:  {sig['verdict']} (confidence {sig['confidence']})")
    for ev in sig["evidence"]:
        print(f"  {ev}")
    print()

    manifest = report["manifest"]
    if manifest:
        print(f"Manifest: {manifest['game']} — {manifest.get('status', 'unknown')}")
        vt = manifest.get("validated_tracks", [])
        if vt:
            print(f"  Validated tracks: {', '.join(str(t) for t in vt)}")
    else:
        print("Manifest: none (new game, needs investigation)")


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Identify NES ROM for music extraction")
    ap.add_argument("rom_path", nargs="?", help="Path to NES ROM")
    ap.add_argument("--scan-dir", help="Scan directory for all .nes files")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    if args.scan_dir:
        scan_dir = Path(args.scan_dir)
        for rom_file in sorted(scan_dir.rglob("*.nes")):
            report = identify_rom(str(rom_file))
            sig = report.get("driver_signature", {})
            verdict = sig.get("verdict", "ERROR")
            conf = sig.get("confidence", 0)
            if verdict != "NOT MAEZAWA":
                h = report.get("header", {})
                mapper = h.get("mapper", "?")
                print(f"  {verdict:20s} ({conf:.1f}) mapper={mapper:2} {rom_file.name}")
    elif args.rom_path:
        report = identify_rom(args.rom_path)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
