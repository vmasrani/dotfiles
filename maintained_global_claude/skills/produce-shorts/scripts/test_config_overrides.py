#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "pydantic>=2.9", "pyyaml>=6.0", "loguru>=0.7", "typer>=0.12", "rich>=13.7"]
# ///
"""episode.yaml `config_overrides:` merge — run: `uv run --script scripts/test_config_overrides.py`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from psmedia import load_config


def _episode(tmp_path: Path, text: str) -> Path:
    (tmp_path / "episode.yaml").write_text(text)
    return tmp_path


def test_episode_value_wins_and_other_keys_keep_defaults(tmp_path):
    base = load_config()
    root = _episode(tmp_path, "config_overrides:\n  subtitles:\n    max_chars_per_second: 99\n")
    cfg = load_config(None, root)
    assert cfg.subtitles.max_chars_per_second == 99
    assert base.subtitles.max_chars_per_second != 99
    assert cfg.model_dump(exclude={"subtitles"}) == base.model_dump(exclude={"subtitles"})
    assert cfg.subtitles.model_dump(exclude={"max_chars_per_second"}) == base.subtitles.model_dump(exclude={"max_chars_per_second"})


def test_no_overrides_equals_defaults(tmp_path):
    assert load_config(None, _episode(tmp_path, "episode: {}\n")) == load_config()


def test_unknown_key_fails_loud(tmp_path):
    root = _episode(tmp_path, "config_overrides:\n  subtitles:\n    not_a_real_key: 1\n")
    with pytest.raises(ValueError, match="not_a_real_key"):
        load_config(None, root)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))


def test_new_name_in_a_mapping_field_is_accepted(tmp_path):
    root = _episode(tmp_path, "config_overrides:\n  broll:\n    text:\n      placements:\n"
                              "        title-center: {x: 960, y: 700, anchor: center, max_width: 1600}\n")
    placements = load_config(None, root).broll.text.placements
    assert placements["title-center"].anchor == "center"
    assert "lowerthird" in placements


def test_unknown_key_inside_a_mapping_value_fails_loud(tmp_path):
    root = _episode(tmp_path, "config_overrides:\n  broll:\n    text:\n      placements:\n"
                              "        title-center: {x: 960, y: 700, anchr: center, max_width: 1600}\n")
    with pytest.raises(ValueError, match="title-center.anchr"):
        load_config(None, root)
