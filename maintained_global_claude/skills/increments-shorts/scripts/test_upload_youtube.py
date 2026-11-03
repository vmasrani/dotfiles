#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "typer>=0.12", "loguru>=0.7", "platformdirs>=4", "rich>=13.7"]
# ///
"""upload_youtube body — run: `uv run --script scripts/test_upload_youtube.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest

from upload_youtube import build_body

META = {"title": "t", "description": "d", "tags": ["a"]}


def test_default_language_is_en_for_text_and_audio():
    s = build_body(META)["snippet"]
    assert s["defaultLanguage"] == "en" and s["defaultAudioLanguage"] == "en"


def test_language_override_applies_to_both():
    s = build_body(META, "fr")["snippet"]
    assert s["defaultLanguage"] == "fr" and s["defaultAudioLanguage"] == "fr"


def test_still_private():
    assert build_body(META)["status"]["privacyStatus"] == "private"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
