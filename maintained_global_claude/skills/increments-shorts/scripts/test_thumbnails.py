#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "pillow>=10", "pydantic>=2.9", "pyyaml>=6", "typer>=0.12", "loguru>=0.7", "static-ffmpeg>=2.7", "httpx>=0.27", "platformdirs>=4"]
# ///
"""Thumbnail spec validation — run: `uv run --script scripts/test_thumbnails.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest
from pydantic import ValidationError

from thumbnails import Spec


def spec(**opt):
    base = {"id": "a", "style": "bw", "lines": ["I DON'T KNOW."], "frame": {"t": 1.0, "tile_x": 0}}
    return Spec.model_validate({"shorts": {"s": {"title": "Does P(doom) make any sense?", "options": [{**base, **opt}]}}})


def test_valid_spec_loads():
    assert spec().shorts["s"].options[0].style == "bw"


def test_text_longer_than_three_words_per_line_is_rejected():
    with pytest.raises(ValidationError, match="1-3 words"):
        spec(lines=["THIS IS WAY TOO LONG"])


def test_text_repeating_the_title_is_rejected():
    with pytest.raises(ValidationError, match="COMPLEMENT"):
        spec(lines=["P(DOOM) MAKE SENSE"])


def test_two_face_styles_need_two_frames_and_two_lines():
    with pytest.raises(ValidationError, match="frame2"):
        spec(style="split", lines=["A", "B"])
    with pytest.raises(ValidationError, match="exactly 2 lines"):
        spec(style="circles", lines=["A"], frame2={"t": 2.0, "tile_x": 640})


def test_quoteshot_needs_quote_image_and_unknown_style_fails():
    with pytest.raises(ValidationError, match="quote_image"):
        spec(style="quoteshot")
    with pytest.raises(ValidationError):
        spec(style="neon")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
