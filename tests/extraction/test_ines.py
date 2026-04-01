"""Tests for iNES header parser using actual ROMs in roms/ directory.

These tests require ROMs to be present — they are skipped if roms/ is empty.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.ines import parse_header, mapper_name, INESError

ROMS_DIR = Path(__file__).parent.parent / "roms"

# Skip all tests in this module if no ROMs are present
pytestmark = pytest.mark.skipif(
    not list(ROMS_DIR.glob("*.nes")),
    reason="No ROMs in roms/ directory",
)


def _find_rom(pattern: str) -> Path | None:
    """Find a ROM matching a pattern (case-insensitive)."""
    for p in ROMS_DIR.glob("*.nes"):
        if pattern.lower() in p.name.lower():
            return p
    return None


class TestCastlevania:
    """Castlevania (U) — Konami, UxROM mapper."""

    @pytest.fixture
    def rom_path(self):
        p = _find_rom("castlevania (u)")
        if p is None:
            pytest.skip("Castlevania ROM not found")
        return p

    def test_header_parses(self, rom_path):
        info = parse_header(rom_path)
        assert info["mapper"] == 2  # UxROM
        assert info["prg_rom_size"] == 128 * 1024
        assert info["region"] == "ntsc"
        assert len(info["rom_sha256"]) == 64

    def test_mapper_name(self, rom_path):
        info = parse_header(rom_path)
        assert "UxROM" in mapper_name(info["mapper"])


class TestCastlevaniaIII:
    """Castlevania III (U) — Konami, MMC5 mapper."""

    @pytest.fixture
    def rom_path(self):
        p = _find_rom("castlevania iii")
        if p is None:
            pytest.skip("Castlevania III ROM not found")
        return p

    def test_header_parses(self, rom_path):
        info = parse_header(rom_path)
        assert info["mapper"] == 5  # MMC5
        assert info["prg_rom_size"] == 256 * 1024
        assert info["chr_rom_size"] == 128 * 1024

    def test_mirroring(self, rom_path):
        info = parse_header(rom_path)
        assert info["mirroring"] == "horizontal"


class TestDarkwingDuck:
    """Darkwing Duck (U) — Capcom, MMC1."""

    @pytest.fixture
    def rom_path(self):
        p = _find_rom("darkwing")
        if p is None:
            pytest.skip("Darkwing Duck ROM not found")
        return p

    def test_header_parses(self, rom_path):
        info = parse_header(rom_path)
        assert info["mapper"] == 1  # MMC1
        assert info["chr_rom_size"] == 128 * 1024


class TestFinalFantasy:
    """Final Fantasy (U) — Square, MMC1 with battery."""

    @pytest.fixture
    def rom_path(self):
        p = _find_rom("final fantasy")
        if p is None:
            pytest.skip("Final Fantasy ROM not found")
        return p

    def test_battery_sram(self, rom_path):
        info = parse_header(rom_path)
        assert info["battery"] is True

    def test_no_chr_rom(self, rom_path):
        info = parse_header(rom_path)
        assert info["chr_rom_size"] == 0  # uses CHR RAM


def test_all_roms_parse():
    """Every .nes file in roms/ should parse without errors."""
    for nes_file in ROMS_DIR.glob("*.nes"):
        info = parse_header(nes_file)
        assert "rom_sha256" in info, f"Failed to parse: {nes_file.name}"
        assert info["prg_rom_size"] > 0


def test_bad_file():
    """Non-NES file should raise INESError."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".nes", delete=False) as f:
        f.write(b"not a nes rom at all")
        path = f.name
    with pytest.raises(INESError, match="bad magic"):
        parse_header(path)
    Path(path).unlink()
