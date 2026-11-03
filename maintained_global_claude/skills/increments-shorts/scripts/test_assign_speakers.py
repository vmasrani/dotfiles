#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "pydantic>=2.9", "pyyaml>=6", "typer>=0.12", "loguru>=0.7", "static-ffmpeg>=2.7", "platformdirs>=4"]
# ///
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest

from assign_speakers import segments, stamp

W = [{"w": "hi", "start": 0.0, "end": 0.4}, {"w": "there", "start": 0.5, "end": 0.9}, {"w": "yes", "start": 5.0, "end": 5.3}]


def test_stamp_assigns_by_midpoint_and_builds_segments():
    out = stamp(W, [{"start": 0, "end": 2, "speaker": "a"}, {"start": 2, "end": 9, "speaker": "b"}], {"a", "b"})
    assert [w["speaker"] for w in out] == ["a", "a", "b"]
    assert [(s["speaker"], s["text"]) for s in segments(out)] == [("a", "hi there"), ("b", "yes")]


def test_gaps_and_unknown_speakers_fail_loud():
    with pytest.raises(ValueError, match="0 or >1 turns"):
        stamp(W, [{"start": 0, "end": 2, "speaker": "a"}], {"a"})
    with pytest.raises(ValueError, match="not in episode.yaml"):
        stamp(W, [{"start": 0, "end": 9, "speaker": "zz"}], {"a"})


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
