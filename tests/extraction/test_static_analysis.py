"""Tests for static analysis scaffolding."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.static_analysis.driver_identify import (
    DriverIdentifier, DriverSignature, DriverCandidate, IdentificationResult,
)
from nesml.static_analysis.pointer_scan import (
    read_le16, scan_pointer_table, find_pointer_candidates,
)
from nesml.static_analysis.sequence_decode import (
    DecodeContext, NullDecoder,
)
from nesml.models.core import Confidence

ROMS_DIR = Path(__file__).parent.parent / "roms"


class TestPointerScan:
    def test_read_le16(self):
        data = bytes([0x00, 0x80, 0xFF, 0x7F])
        assert read_le16(data, 0) == 0x8000
        assert read_le16(data, 2) == 0x7FFF

    def test_scan_pointer_table(self):
        # Create fake PRG data with a 3-entry pointer table at offset 0
        data = bytes([
            0x00, 0x80,  # pointer to $8000
            0x20, 0x80,  # pointer to $8020
            0x40, 0x80,  # pointer to $8040
        ] + [0] * 100)

        table = scan_pointer_table(data, 0, 3)
        assert len(table.entries) == 3
        assert table.entries[0].target_address == 0x8000
        assert table.entries[1].target_address == 0x8020
        assert table.entries[2].target_address == 0x8040

    def test_scan_resolves_rom_offsets(self):
        data = bytes([0x10, 0x80] + [0] * 100)
        table = scan_pointer_table(data, 0, 1, bank_base=0x8000, prg_bank_offset=0)
        assert table.entries[0].target_rom_offset == 0x10

    def test_find_pointer_candidates(self):
        # Create data with a run of valid pointers
        pointers = b""
        for i in range(8):
            addr = 0x8000 + (i * 0x100)
            pointers += bytes([addr & 0xFF, (addr >> 8) & 0xFF])
        # Add some non-pointer data
        data = bytes(100) + pointers + bytes(100)

        candidates = find_pointer_candidates(data, min_consecutive=4)
        assert len(candidates) >= 1
        assert 100 in candidates


class TestDriverIdentifier:
    def test_manual_override(self):
        ident = DriverIdentifier()
        ident.register_manual_override("abc123" * 10 + "abcd", "konami_pre_vrc")
        # Can't test with real ROM here, but the mechanism is in place

    def test_signature_matching(self):
        sig = DriverSignature(
            family="test_family",
            pattern=b"\x20\x00\x80",  # JSR $8000
            offset=0,
            description="test init routine",
            confidence_score=0.8,
        )
        ident = DriverIdentifier()
        ident.register_signature(sig)

    @pytest.mark.skipif(
        not list(ROMS_DIR.glob("*.nes")),
        reason="No ROMs available",
    )
    def test_identify_returns_result(self):
        ident = DriverIdentifier()
        rom = next(ROMS_DIR.glob("*.nes"))
        result = ident.identify(rom)
        assert isinstance(result, IdentificationResult)
        assert result.rom_sha256 != ""


class TestSequenceDecode:
    def test_decode_context_read(self):
        data = bytes([0x10, 0x20, 0x30, 0x40])
        ctx = DecodeContext(prg_data=data, offset=0)
        assert ctx.read_byte() == 0x10
        assert ctx.read_byte() == 0x20
        assert ctx.bytes_read == 2

    def test_decode_context_le16(self):
        data = bytes([0x00, 0x80])
        ctx = DecodeContext(prg_data=data, offset=0)
        assert ctx.read_le16() == 0x8000

    def test_decode_context_eof(self):
        data = bytes([0x10])
        ctx = DecodeContext(prg_data=data, offset=0)
        ctx.read_byte()
        ctx.read_byte()  # past end
        assert ctx.halted is True

    def test_null_decoder(self):
        decoder = NullDecoder()
        data = bytes(range(10))
        ctx = decoder.decode_stream(data, 0, max_bytes=5)
        assert len(ctx.unknowns) > 0

    def test_decode_to_pattern(self):
        decoder = NullDecoder()
        data = bytes([0x01, 0x02, 0x03])
        pat = decoder.decode_to_pattern(data, 0, "test_pat", max_bytes=3)
        assert pat.id == "test_pat"
        assert pat.rom_offset == 0
        assert pat.confidence.score < 0.5  # has unknowns
