"""Static analysis of all .jsfx files to catch the bugs from BLOOPERS.md.

Catches:
- Blunder 1: //tags:instrument (comment, not a tag)
- Blunder 2: Missing in_pin:none / out_pin:Left / out_pin:Right
- Blunder 3: Unicode characters in JSFX
- Blunder 9: ^ between single-bit expressions (XOR vs power trap)
- Sequential slider numbering (no gaps)
- desc: line exists
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
JSFX_DIR = REPO_ROOT / "studio" / "jsfx"


def all_jsfx_files() -> list[Path]:
    """Collect all .jsfx files in jsfx/ directory (not libs)."""
    return sorted(JSFX_DIR.glob("*.jsfx"))


def jsfx_ids() -> list[str]:
    return [f.name for f in all_jsfx_files()]


# ---------------------------------------------------------------------------
#  Lint engine (reusable from validate.py)
# ---------------------------------------------------------------------------

def lint_jsfx(path: Path) -> list[str]:
    """Run all JSFX lint checks on a single file. Returns list of error strings."""
    errors: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # --- desc: line exists ---
    has_desc = any(line.strip().startswith("desc:") for line in lines)
    if not has_desc:
        errors.append("Missing 'desc:' line")

    # --- tags:instrument present (not //tags:) ---
    has_tags = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//tags:"):
            errors.append(f"Line {i}: Commented-out tag '//tags:' found — should be 'tags:' without '//'")
        if stripped.startswith("tags:"):
            has_tags = True
    if not has_tags:
        errors.append("Missing 'tags:' directive (needed for REAPER to classify the plugin)")

    # --- in_pin:none for instrument plugins ---
    is_instrument = any("instrument" in line.lower() for line in lines
                        if line.strip().startswith("tags:"))
    has_in_pin_none = any(line.strip() == "in_pin:none" for line in lines)
    has_out_left = any(line.strip() == "out_pin:Left" for line in lines)
    has_out_right = any(line.strip() == "out_pin:Right" for line in lines)

    if is_instrument:
        if not has_in_pin_none:
            errors.append("Instrument plugin missing 'in_pin:none' — REAPER will produce SILENCE")
        if not has_out_left:
            errors.append("Missing 'out_pin:Left'")
        if not has_out_right:
            errors.append("Missing 'out_pin:Right'")

    # --- No unicode characters (only ASCII 32-126 plus newlines/tabs) ---
    for i, line in enumerate(lines, 1):
        for j, ch in enumerate(line):
            code = ord(ch)
            if code > 126 or (code < 32 and code not in (9, 10, 13)):
                errors.append(
                    f"Line {i}, col {j + 1}: Non-ASCII character U+{code:04X} "
                    f"('{ch}') — JSFX compiler may silently fail"
                )

    # --- Slider numbers sequential with no gaps ---
    slider_nums: list[int] = []
    slider_pattern = re.compile(r"^slider(\d+):")
    for line in lines:
        m = slider_pattern.match(line.strip())
        if m:
            slider_nums.append(int(m.group(1)))

    if slider_nums:
        slider_nums_sorted = sorted(slider_nums)
        expected = list(range(slider_nums_sorted[0], slider_nums_sorted[0] + len(slider_nums_sorted)))
        if slider_nums_sorted != expected:
            gaps = set(expected) - set(slider_nums_sorted)
            extras = set(slider_nums_sorted) - set(expected)
            msg = f"Slider numbering has gaps: found {slider_nums_sorted}"
            if gaps:
                msg += f", missing: {sorted(gaps)}"
            if extras:
                msg += f", unexpected: {sorted(extras)}"
            errors.append(msg)

    # --- No use of ^ between single-bit expressions (XOR vs power trap) ---
    # Matches patterns like (expr & 1) ^ (expr & 1) or var ^ var where context
    # suggests single-bit XOR usage. This is a heuristic — it flags ^ usage
    # near bitwise AND masks as suspicious.
    xor_pattern = re.compile(r"\b\w+\s*&\s*\d+\)\s*\^\s*\(")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if xor_pattern.search(stripped):
            errors.append(
                f"Line {i}: Suspicious '^' between masked expressions — "
                f"in JSFX '^' is POWER not XOR. Use ((a + b) & 1) for single-bit XOR."
            )

    return errors


# ---------------------------------------------------------------------------
#  Pytest tests — run against actual repo files
# ---------------------------------------------------------------------------

class TestJsfxLintAllFiles:
    """Run lint checks on every .jsfx file in the repo."""

    @pytest.fixture(params=all_jsfx_files(), ids=jsfx_ids())
    def jsfx_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_no_lint_errors(self, jsfx_path: Path) -> None:
        errors = lint_jsfx(jsfx_path)
        if errors:
            msg = f"\n{jsfx_path.name} has {len(errors)} lint error(s):\n"
            msg += "\n".join(f"  - {e}" for e in errors)
            pytest.fail(msg)


class TestJsfxDescPresent:
    """Every JSFX must have a desc: line."""

    @pytest.fixture(params=all_jsfx_files(), ids=jsfx_ids())
    def jsfx_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_desc_exists(self, jsfx_path: Path) -> None:
        text = jsfx_path.read_text(encoding="utf-8", errors="replace")
        assert any(line.strip().startswith("desc:") for line in text.splitlines()), \
            f"{jsfx_path.name}: Missing 'desc:' line"


class TestJsfxTagsNotCommented:
    """Blunder 1: tags must not be commented out."""

    @pytest.fixture(params=all_jsfx_files(), ids=jsfx_ids())
    def jsfx_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_no_commented_tags(self, jsfx_path: Path) -> None:
        text = jsfx_path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            assert not line.strip().startswith("//tags:"), (
                f"{jsfx_path.name} line {i}: '//tags:' is a comment, not a tag directive. "
                f"Remove the '//' prefix."
            )


class TestJsfxInstrumentPins:
    """Blunder 2: instrument plugins must have in_pin:none and out_pin:Left/Right."""

    @pytest.fixture(params=all_jsfx_files(), ids=jsfx_ids())
    def jsfx_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_instrument_has_correct_pins(self, jsfx_path: Path) -> None:
        text = jsfx_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        # Check if this is an instrument plugin
        is_instrument = any(
            "instrument" in line.lower()
            for line in lines
            if line.strip().startswith("tags:")
        )
        if not is_instrument:
            pytest.skip("Not an instrument plugin")

        has_in_none = any(l.strip() == "in_pin:none" for l in lines)
        has_out_left = any(l.strip() == "out_pin:Left" for l in lines)
        has_out_right = any(l.strip() == "out_pin:Right" for l in lines)

        errors = []
        if not has_in_none:
            errors.append("Missing 'in_pin:none'")
        if not has_out_left:
            errors.append("Missing 'out_pin:Left'")
        if not has_out_right:
            errors.append("Missing 'out_pin:Right'")

        assert not errors, f"{jsfx_path.name}: {'; '.join(errors)} — plugin will be SILENT"


class TestJsfxAsciiOnly:
    """Blunder 3: JSFX compiler doesn't support Unicode."""

    @pytest.fixture(params=all_jsfx_files(), ids=jsfx_ids())
    def jsfx_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_ascii_only(self, jsfx_path: Path) -> None:
        text = jsfx_path.read_text(encoding="utf-8", errors="replace")
        bad_chars = []
        for i, line in enumerate(text.splitlines(), 1):
            for j, ch in enumerate(line):
                code = ord(ch)
                if code > 126 or (code < 32 and code not in (9, 10, 13)):
                    bad_chars.append(f"  line {i}, col {j + 1}: U+{code:04X} ('{ch}')")
        assert not bad_chars, (
            f"{jsfx_path.name}: Non-ASCII characters found:\n" + "\n".join(bad_chars)
        )


class TestJsfxSliderSequence:
    """Slider numbers must be sequential with no gaps."""

    @pytest.fixture(params=all_jsfx_files(), ids=jsfx_ids())
    def jsfx_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_sliders_sequential(self, jsfx_path: Path) -> None:
        text = jsfx_path.read_text(encoding="utf-8", errors="replace")
        nums: list[int] = []
        for line in text.splitlines():
            m = re.match(r"^slider(\d+):", line.strip())
            if m:
                nums.append(int(m.group(1)))

        if not nums:
            pytest.skip("No sliders found")

        nums_sorted = sorted(nums)
        expected = list(range(nums_sorted[0], nums_sorted[0] + len(nums_sorted)))
        assert nums_sorted == expected, (
            f"{jsfx_path.name}: Slider numbering has gaps. "
            f"Found: {nums_sorted}, expected: {expected}"
        )


class TestJsfxXorTrap:
    """Blunder 9: ^ is POWER in JSFX, not XOR."""

    @pytest.fixture(params=all_jsfx_files(), ids=jsfx_ids())
    def jsfx_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_no_xor_power_trap(self, jsfx_path: Path) -> None:
        text = jsfx_path.read_text(encoding="utf-8", errors="replace")
        pattern = re.compile(r"\b\w+\s*&\s*\d+\)\s*\^\s*\(")
        bad_lines = []
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if pattern.search(stripped):
                bad_lines.append(f"  line {i}: {stripped}")

        assert not bad_lines, (
            f"{jsfx_path.name}: Suspicious '^' (power, not XOR) usage:\n"
            + "\n".join(bad_lines)
        )
