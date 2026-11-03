#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "static-ffmpeg>=2.7", "typer>=0.12", "loguru>=0.7", "httpx>=0.27", "platformdirs>=4"]
# ///
"""End-tag timing math — run: `uv run --script scripts/test_endtag.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest

from endtag import audio_delay_ms, build_filter


def test_audio_starts_when_speech_ends():
    assert audio_delay_ms(41.7) == 41700
    assert audio_delay_ms(0.0019) == 1


def test_vertical_filter_holds_last_frame_and_offsets_tag():
    f = build_filter(41.7, 2.333, 1080, 1920)
    assert "tpad=stop_mode=clone:stop_duration=2.333" in f
    assert "setpts=PTS-STARTPTS+41.700/TB" in f and "scale" not in f and "adelay=41700|41700" in f


def test_horizontal_filter_scales_tag_to_height_and_centres():
    f = build_filter(300.0, 2.333, 1920, 1080)
    assert "scale=-2:1080" in f and "x=(W-w)/2" in f


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
