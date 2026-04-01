"""Tests for trace format conversion."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.trace_convert import convert_mesen_csv, ConvertError
from nesml.schema_validator import validate_trace


def _write_csv(content: str) -> Path:
    """Write CSV content to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return Path(f.name)


def test_mesen_csv_basic():
    csv_path = _write_csv(
        "frame,address,value\n"
        "0,$4015,15\n"
        "0,$4000,191\n"
        "0,$4002,253\n"
        "0,$4003,0\n"
        "10,$4002,212\n"
        "10,$4003,0\n"
    )
    out_path = Path(tempfile.mktemp(suffix=".json"))

    trace = convert_mesen_csv(
        csv_path, out_path, rom_name="test", region="ntsc"
    )

    assert len(trace["writes"]) == 6
    assert trace["writes"][0]["address"] == "$4015"
    assert trace["metadata"]["rom_name"] == "test"

    # Validate schema
    errors = validate_trace(trace)
    assert errors == []

    # Check file was written
    with open(out_path) as f:
        loaded = json.load(f)
    assert loaded["schema_version"] == "0.1.0"

    csv_path.unlink()
    out_path.unlink()


def test_mesen_csv_frame_range():
    csv_path = _write_csv(
        "frame,address,value\n"
        "100,$4000,191\n"
        "200,$4000,48\n"
    )
    out_path = Path(tempfile.mktemp(suffix=".json"))

    trace = convert_mesen_csv(csv_path, out_path, rom_name="test")
    assert trace["metadata"]["capture_start_frame"] == 100
    assert trace["metadata"]["capture_end_frame"] == 200

    csv_path.unlink()
    out_path.unlink()


def test_mesen_csv_empty():
    csv_path = _write_csv("")
    out_path = Path(tempfile.mktemp(suffix=".json"))

    with pytest.raises(ConvertError, match="Empty CSV"):
        convert_mesen_csv(csv_path, out_path)

    csv_path.unlink()


def test_mesen_csv_bad_header():
    csv_path = _write_csv("time,reg,val\n0,$4000,191\n")
    out_path = Path(tempfile.mktemp(suffix=".json"))

    with pytest.raises(ConvertError, match="Unexpected CSV header"):
        convert_mesen_csv(csv_path, out_path)

    csv_path.unlink()


def test_mesen_csv_bad_row():
    csv_path = _write_csv("frame,address,value\n0,$4000\n")
    out_path = Path(tempfile.mktemp(suffix=".json"))

    with pytest.raises(ConvertError, match="expected 3 columns"):
        convert_mesen_csv(csv_path, out_path)

    csv_path.unlink()
