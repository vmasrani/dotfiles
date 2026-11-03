#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["static-ffmpeg>=2.7", "platformdirs>=4", "pytest>=8", "pydantic>=2.9", "pyyaml>=6.0", "typer>=0.12", "loguru>=0.7", "rich>=13.7", "pysubs2>=1.7", "opencv-python-headless>=4.10,<5", "numpy>=1.26"]
# ///
"""clamp_windows must survive .ass centisecond rounding — run: `uv run --script scripts/test_clamp_windows.py -q`."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest

import align_subtitles as asub


def item(i, start, end, text="comparing"):
    return SimpleNamespace(index=i, line=SimpleNamespace(text=text), start=start, end=end)


def stored(seconds):  # what the .ass keeps
    return round(seconds * 100) / 100


def test_min_display_survives_centisecond_rounding():
    cards = [item(0, 37.735, 38.535)]  # exactly 0.80 s as floats, 0.79 s once written to centiseconds
    asub.clamp_windows(cards, 0.8, 100.0)
    assert stored(cards[0].end) - stored(cards[0].start) >= 0.8 - 1e-9


def test_next_card_never_starts_before_previous_end():
    cards = [item(0, 1.004, 1.2), item(1, 1.5, 2.0)]
    asub.clamp_windows(cards, 0.8, 100.0)
    assert cards[1].start >= cards[0].end - 1e-9


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
