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

from datetime import datetime, timedelta, timezone

import typer

from upload_youtube import build_body, parse_publish_at, schedule_body, require_processed

META = {"title": "t", "description": "d", "tags": ["a"]}


def test_default_language_is_en_for_text_and_audio():
    s = build_body(META)["snippet"]
    assert s["defaultLanguage"] == "en" and s["defaultAudioLanguage"] == "en"


def test_language_override_applies_to_both():
    s = build_body(META, "fr")["snippet"]
    assert s["defaultLanguage"] == "fr" and s["defaultAudioLanguage"] == "fr"


def test_still_private():
    assert build_body(META)["status"]["privacyStatus"] == "private"


def _iso(delta, tz="-08:00"):
    return (datetime.now(timezone.utc) + delta).astimezone(timezone(timedelta(hours=-8))).isoformat()


def test_publish_at_converts_to_utc():
    when = parse_publish_at(_iso(timedelta(days=2)))
    assert when.utcoffset() == timedelta(0)


def test_publish_at_naive_rejected_with_fix():
    naive = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()
    with pytest.raises(typer.BadParameter, match="UTC offset"):
        parse_publish_at(naive)


def test_publish_at_past_rejected():
    with pytest.raises(typer.BadParameter, match="future"):
        parse_publish_at(_iso(timedelta(days=-1)))


def test_publish_at_garbage_rejected():
    with pytest.raises(typer.BadParameter, match="ISO 8601"):
        parse_publish_at("tomorrow")


def test_publish_at_z_suffix_ok():
    assert parse_publish_at((datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))


def test_schedule_body():
    when = datetime(2030, 1, 1, 3, 0, tzinfo=timezone.utc)
    b = schedule_body("abc", when, {"madeForKids": True})
    assert b == {"id": "abc", "status": {"privacyStatus": "private", "publishAt": "2030-01-01T03:00:00Z", "selfDeclaredMadeForKids": True}}
    assert schedule_body("abc", when, {})["status"]["selfDeclaredMadeForKids"] is False


def test_build_body_publish_at_stays_private():
    when = datetime(2030, 1, 1, 3, 0, tzinfo=timezone.utc)
    st = build_body(META, "en", when)["status"]
    assert st["privacyStatus"] == "private" and st["publishAt"] == "2030-01-01T03:00:00Z"
    assert "publishAt" not in build_body(META)["status"]


def test_require_processed():
    require_processed({"processingDetails": {"processingStatus": "succeeded"}})
    for item in ({"processingDetails": {"processingStatus": "processing"}}, {}):
        with pytest.raises(RuntimeError, match="processing"):
            require_processed(item)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
