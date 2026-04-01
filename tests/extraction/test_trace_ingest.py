"""Tests for trace ingestion."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nesml.trace_ingest import load_trace, TraceIngestError

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_nesml_json():
    trace = load_trace(FIXTURES / "simple_pulse_trace.json")
    assert trace["schema_version"] == "0.1.0"
    assert len(trace["writes"]) == 10
    assert trace["writes"][0]["frame"] == 0
    assert trace["writes"][0]["address"] == "$4015"


def test_load_multi_channel():
    trace = load_trace(FIXTURES / "multi_channel_trace.json")
    assert len(trace["writes"]) == 16


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_trace(FIXTURES / "nonexistent.json")


def test_unknown_format():
    # Create a temp file with unknown extension
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"not a trace")
        path = f.name
    with pytest.raises(TraceIngestError, match="Cannot auto-detect"):
        load_trace(path)
    Path(path).unlink()


def test_mesen_stub():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"some text")
        path = f.name
    with pytest.raises(TraceIngestError, match="not yet implemented"):
        load_trace(path, format="mesen_txt")
    Path(path).unlink()
