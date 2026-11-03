#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "pydantic>=2.9", "pyyaml>=6", "typer>=0.12", "loguru>=0.7", "static-ffmpeg>=2.7", "httpx>=0.27", "platformdirs>=4", "pillow>=10"]
# ///
"""Description builder + title/metadata checks — run: `uv run --script scripts/test_deliver.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest

from deliver import build_description, check_title, newest_passed_final


def test_description_is_links_and_hashtags_only():
    d = build_description("https://youtu.be/x", ["Bayes", "#AI", "Podcast"])
    assert d == ("Full episode: https://youtu.be/x\nIncrements Podcast: https://www.incrementspodcast.com\n\n#Bayes #AI #Podcast")


def test_description_adds_blog_line_when_given():
    d = build_description("https://youtu.be/x", ["a", "b", "c"], "https://blog/post")
    assert d.splitlines()[:3] == ["Full episode: https://youtu.be/x", "Blog post: https://blog/post",
                                  "Increments Podcast: https://www.incrementspodcast.com"]


def test_description_requires_exactly_three_hashtags():
    with pytest.raises(ValueError, match="exactly 3"):
        build_description("u", ["a", "b"])


def test_title_length_enforced():
    assert check_title("  Hi  ") == "Hi"
    with pytest.raises(ValueError):
        check_title("x" * 101)


def test_unqced_clip_refuses(tmp_path):
    with pytest.raises(RuntimeError, match="not qc_passed"):
        newest_passed_final({"clip": {"status": "rendered"}, "render": {"versions": []}}, tmp_path, "youtube-shorts")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
