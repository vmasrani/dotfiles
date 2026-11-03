#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "typer>=0.12", "loguru>=0.7", "platformdirs>=4", "rich>=13.7"]
# ///
"""Upload body/meta parsing (no network) — run: `uv run --script scripts/test_upload_youtube.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest

from upload_youtube import build_body, parse_meta

META = "TITLE:\nIraq was not a war for oil\n\nDESCRIPTION:\nFull episode: https://youtu.be/x\n\n#a #b #c\n\nTAGS:\nIncrements Podcast, podcast\n"


def test_parse_meta_and_body_is_always_private_not_for_kids():
    m = parse_meta(META)
    assert m["title"] == "Iraq was not a war for oil" and m["tags"] == ["Increments Podcast", "podcast"]
    b = build_body(m)
    assert b["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False}
    assert b["snippet"]["categoryId"] == "22"


def test_malformed_meta_fails_loud():
    with pytest.raises(ValueError, match="TITLE"):
        parse_meta("just text")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
