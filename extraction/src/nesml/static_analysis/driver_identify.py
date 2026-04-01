"""Driver identification layer.

Classifies ROMs by likely music engine family using multiple evidence sources:
1. Known code signatures (byte patterns at specific offsets)
2. Pointer structures (song table layouts, channel pointer formats)
3. String markers (rare but occasionally present)
4. Mapper + publisher + title heuristics (weak evidence only)
5. Manual override mechanism (highest confidence)

The identifier produces a ranked list of candidate driver families,
each with confidence and supporting evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nesml.models.core import Confidence, SourceType


@dataclass
class DriverCandidate:
    """A candidate driver family identification for a ROM."""
    family: str                 # e.g., "konami_pre_vrc", "capcom_mm"
    variant: str = ""           # e.g., "castlevania_v1", "megaman2"
    confidence: Confidence = field(default_factory=Confidence.provisional)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "variant": self.variant,
            "confidence": self.confidence.to_dict(),
            "evidence": self.evidence,
        }


@dataclass
class IdentificationResult:
    """Result of driver identification for a ROM."""
    rom_name: str
    rom_sha256: str
    candidates: list[DriverCandidate] = field(default_factory=list)
    manual_override: str | None = None
    notes: str = ""

    @property
    def best_candidate(self) -> DriverCandidate | None:
        if self.manual_override:
            for c in self.candidates:
                if c.family == self.manual_override:
                    return c
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda c: c.confidence.score)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "rom_name": self.rom_name,
            "rom_sha256": self.rom_sha256,
            "candidates": [c.to_dict() for c in self.candidates],
        }
        if self.manual_override:
            d["manual_override"] = self.manual_override
        if self.notes:
            d["notes"] = self.notes
        best = self.best_candidate
        if best:
            d["best_match"] = best.family
            d["best_confidence"] = best.confidence.score
        return d


class DriverIdentifier:
    """Identifies the sound driver family used in a ROM.

    Runs a pipeline of identification strategies from strongest to weakest.
    Each strategy can add or modify DriverCandidate entries.
    """

    def __init__(self):
        self._manual_overrides: dict[str, str] = {}
        self._signature_db: list[DriverSignature] = []

    def register_manual_override(self, rom_sha256: str, family: str) -> None:
        """Register a manual driver identification (highest evidence tier)."""
        self._manual_overrides[rom_sha256] = family

    def register_signature(self, sig: DriverSignature) -> None:
        """Register a code signature for detection."""
        self._signature_db.append(sig)

    def identify(self, rom_path: str | Path) -> IdentificationResult:
        """Identify the driver family for a ROM.

        Args:
            rom_path: Path to the .nes ROM file.

        Returns:
            IdentificationResult with ranked candidates.
        """
        from nesml.static_analysis.ines import parse_header
        path = Path(rom_path)
        header = parse_header(path)
        rom_data = path.read_bytes()
        prg_offset = 16 + (512 if header["trainer"] else 0)
        prg_data = rom_data[prg_offset:prg_offset + header["prg_rom_size"]]

        result = IdentificationResult(
            rom_name=path.stem,
            rom_sha256=header["rom_sha256"],
        )

        # Strategy 1: Manual override
        if header["rom_sha256"] in self._manual_overrides:
            family = self._manual_overrides[header["rom_sha256"]]
            result.manual_override = family
            result.candidates.append(DriverCandidate(
                family=family,
                confidence=Confidence.manual("manual override"),
            ))
            return result

        # Strategy 2: Code signature matching
        for sig in self._signature_db:
            match = sig.match(prg_data)
            if match:
                result.candidates.append(match)

        # Strategy 3: Pointer structure analysis (stub)
        # TODO: Implement pointer table scanning for known driver layouts

        # Strategy 4: Mapper/publisher heuristics (weak)
        mapper_hint = _mapper_publisher_heuristic(header)
        if mapper_hint:
            result.candidates.append(mapper_hint)

        # Sort by confidence descending
        result.candidates.sort(key=lambda c: c.confidence.score, reverse=True)

        return result


@dataclass
class DriverSignature:
    """A byte pattern that identifies a specific driver family.

    Signatures are matched against PRG ROM data.
    """
    family: str
    variant: str = ""
    pattern: bytes = b""
    offset: int | None = None       # exact offset to check (None = scan)
    mask: bytes | None = None       # byte mask for partial matching
    description: str = ""
    confidence_score: float = 0.8

    def match(self, prg_data: bytes) -> DriverCandidate | None:
        """Check if this signature matches the PRG data."""
        if not self.pattern:
            return None

        if self.offset is not None:
            # Check at exact offset
            if self.offset + len(self.pattern) > len(prg_data):
                return None
            chunk = prg_data[self.offset:self.offset + len(self.pattern)]
            if self._compare(chunk, self.pattern, self.mask):
                return DriverCandidate(
                    family=self.family,
                    variant=self.variant,
                    confidence=Confidence.static_parse(
                        self.confidence_score,
                        f"signature match at offset 0x{self.offset:X}: {self.description}",
                    ),
                    evidence=[{
                        "type": "code_signature",
                        "offset": self.offset,
                        "description": self.description,
                    }],
                )
        else:
            # Scan for pattern
            idx = self._find_pattern(prg_data)
            if idx >= 0:
                return DriverCandidate(
                    family=self.family,
                    variant=self.variant,
                    confidence=Confidence.static_parse(
                        self.confidence_score * 0.9,  # slight reduction for scan
                        f"signature scan match at 0x{idx:X}: {self.description}",
                    ),
                    evidence=[{
                        "type": "code_signature_scan",
                        "offset": idx,
                        "description": self.description,
                    }],
                )

        return None

    def _compare(self, data: bytes, pattern: bytes, mask: bytes | None) -> bool:
        if mask:
            return all(
                (d & m) == (p & m) for d, p, m in zip(data, pattern, mask)
            )
        return data == pattern

    def _find_pattern(self, data: bytes) -> int:
        if self.mask:
            # Masked scan — slower
            plen = len(self.pattern)
            for i in range(len(data) - plen + 1):
                if self._compare(data[i:i + plen], self.pattern, self.mask):
                    return i
            return -1
        return data.find(self.pattern)


def _mapper_publisher_heuristic(header: dict) -> DriverCandidate | None:
    """Weak heuristic: guess driver family from mapper number.

    This is low-confidence because many publishers share mappers,
    and mapper choice doesn't determine sound driver.
    """
    # VRC6 mappers are strong signals for Konami expansion audio
    if header["mapper"] in (24, 26):
        return DriverCandidate(
            family="konami_vrc6",
            confidence=Confidence.heuristic(
                0.7, "VRC6 mapper implies Konami expansion audio driver"
            ),
            evidence=[{"type": "mapper_heuristic", "mapper": header["mapper"]}],
        )
    if header["mapper"] == 85:
        return DriverCandidate(
            family="konami_vrc7",
            confidence=Confidence.heuristic(
                0.7, "VRC7 mapper implies Konami FM expansion driver"
            ),
            evidence=[{"type": "mapper_heuristic", "mapper": header["mapper"]}],
        )
    # Most mappers are too ambiguous for useful heuristics
    return None
