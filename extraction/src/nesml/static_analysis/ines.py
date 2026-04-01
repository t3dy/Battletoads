"""iNES / NES 2.0 header parser.

Extracts metadata from .nes ROM files: mapper number, PRG/CHR sizes,
mirroring, region, and battery/SRAM flags.

Reference: https://www.nesdev.org/wiki/INES
           https://www.nesdev.org/wiki/NES_2.0
"""

from __future__ import annotations

import hashlib
from pathlib import Path

INES_MAGIC = b"NES\x1a"
HEADER_SIZE = 16


class INESError(Exception):
    """Raised when iNES header parsing fails."""


def parse_header(path: str | Path) -> dict:
    """Parse iNES/NES 2.0 header from a .nes ROM file.

    Returns a dict with:
        format: "ines" or "nes2.0"
        prg_rom_size: PRG ROM size in bytes
        chr_rom_size: CHR ROM size in bytes (0 = CHR RAM)
        mapper: mapper number
        mirroring: "horizontal", "vertical", or "four_screen"
        battery: bool (battery-backed SRAM)
        trainer: bool (512-byte trainer present)
        region: "ntsc", "pal", or "dual"
        rom_sha256: SHA-256 hash of the full file
        prg_sha256: SHA-256 hash of PRG ROM data only
    """
    path = Path(path)
    data = path.read_bytes()

    if len(data) < HEADER_SIZE:
        raise INESError(f"File too small for iNES header: {len(data)} bytes")

    if data[:4] != INES_MAGIC:
        raise INESError(f"Not an iNES file (bad magic): {data[:4]!r}")

    prg_16k = data[4]
    chr_8k = data[5]
    flags6 = data[6]
    flags7 = data[7]

    # Mirroring
    four_screen = bool(flags6 & 0x08)
    if four_screen:
        mirroring = "four_screen"
    elif flags6 & 0x01:
        mirroring = "vertical"
    else:
        mirroring = "horizontal"

    battery = bool(flags6 & 0x02)
    trainer = bool(flags6 & 0x04)

    # Detect NES 2.0 vs iNES
    is_nes20 = (flags7 & 0x0C) == 0x08

    if is_nes20:
        fmt = "nes2.0"
        flags8 = data[8]
        mapper = (flags6 >> 4) | (flags7 & 0xF0) | ((flags8 & 0x0F) << 8)

        flags9 = data[9]
        prg_hi = (flags9 & 0x0F)
        chr_hi = (flags9 >> 4) & 0x0F

        if prg_hi < 0x0F:
            prg_rom_size = (prg_hi << 8 | prg_16k) * 16384
        else:
            prg_rom_size = prg_16k * 16384  # fallback

        if chr_hi < 0x0F:
            chr_rom_size = (chr_hi << 8 | chr_8k) * 8192
        else:
            chr_rom_size = chr_8k * 8192

        flags12 = data[12] if len(data) > 12 else 0
        region_bits = flags12 & 0x03
        if region_bits == 0:
            region = "ntsc"
        elif region_bits == 1:
            region = "pal"
        else:
            region = "dual"
    else:
        fmt = "ines"
        mapper = (flags6 >> 4) | (flags7 & 0xF0)
        prg_rom_size = prg_16k * 16384
        chr_rom_size = chr_8k * 8192
        region = "ntsc"  # iNES doesn't reliably encode region

    # Compute hashes
    rom_sha256 = hashlib.sha256(data).hexdigest()

    prg_offset = HEADER_SIZE + (512 if trainer else 0)
    prg_data = data[prg_offset:prg_offset + prg_rom_size]
    prg_sha256 = hashlib.sha256(prg_data).hexdigest()

    return {
        "format": fmt,
        "prg_rom_size": prg_rom_size,
        "chr_rom_size": chr_rom_size,
        "mapper": mapper,
        "mirroring": mirroring,
        "battery": battery,
        "trainer": trainer,
        "region": region,
        "rom_sha256": rom_sha256,
        "prg_sha256": prg_sha256,
    }


# Known mapper names (common ones)
MAPPER_NAMES = {
    0: "NROM",
    1: "MMC1 (SxROM)",
    2: "UxROM",
    3: "CNROM",
    4: "MMC3 (TxROM)",
    5: "MMC5 (ExROM)",
    7: "AxROM",
    9: "MMC2 (PxROM)",
    10: "MMC4 (FxROM)",
    11: "Color Dreams",
    24: "VRC6a (Konami)",
    25: "VRC4/VRC2 (Konami)",
    26: "VRC6b (Konami)",
    69: "Sunsoft FME-7",
    85: "VRC7 (Konami)",
}


def mapper_name(mapper_num: int) -> str:
    """Return a human-readable name for a mapper number, or 'Unknown (N)'."""
    return MAPPER_NAMES.get(mapper_num, f"Unknown ({mapper_num})")
